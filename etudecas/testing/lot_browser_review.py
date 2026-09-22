"""Check business lot counts in the delivered HTML, including nondefault lots.

Offline Chromium; the simulator is never run. Unlike a panel-opening smoke
test, a successful opening is not sufficient. Evidence is written on failure.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re


def business_batch_csv_oracle(run, batch_id):
    """Read the supplied run's physical customer contributions, never a historical split."""
    def rows(name):
        with (run / 'data' / name).open(encoding='utf-8-sig', newline='') as stream:
            return list(csv.DictReader(stream))
    summary = json.loads((run / 'summaries/first_simulation_summary.json').read_text(encoding='utf-8'))
    horizon = int(summary['sim_days'])
    clients = {row['node_id'] for row in rows('production_demand_service_daily.csv')}
    creations = [row for row in rows('production_lot_events.csv')
                 if row['event_type'] == 'production_output' and row.get('business_batch_id') == batch_id]
    if len(creations) != 1:
        raise ValueError(f'Expected one physical production event for {batch_id}, got {len(creations)}')
    links = [row for row in rows('production_lot_genealogy.csv') if row['link_type'] == 'transport'
             and row.get('parent_business_batch_id') == batch_id and row['child_node_id'] in clients
             and row.get('arrival_day') and 0 <= int(float(row['arrival_day'])) < horizon]
    contributions = {tuple(row[key] for key in ('parent_lot_id', 'child_lot_id', 'shipment_id')): float(row['parent_qty']) for row in links}
    if len(contributions) != len(links):
        raise ValueError('Ambiguous duplicate customer contribution key')
    root_qty = float(creations[0]['qty'])
    if sum(contributions.values()) > root_qty + 1e-6:
        raise ValueError('CSV contributions exceed production quantity')
    return dict(root_lot_id=creations[0]['lot_id'], root_qty=root_qty, contributions=contributions,
                horizon=horizon, remaining_not_received_qty=root_qty - sum(contributions.values()))


def review(html, output, source_run=None):
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    report = {"html": str(html.resolve()), "checks": [], "javascript_errors": [],
              "scope": "All selectable lots have causal models; sampled DOM counters, campaign causality, creation dates, stock lifecycle and label geometry. Physical customer contributions require the explicit source run. Not scientific calibration."}
    if source_run is not None:
        report['source_run'] = str(source_run.resolve())
        report['source_hashes'] = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [source_run/'data'/name for name in ('production_lot_events.csv', 'production_lot_genealogy.csv', 'production_demand_service_daily.csv')]
            + [source_run/'summaries/first_simulation_summary.json']}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(offline=True, viewport={"width": 1800, "height": 1100})
            page.on("pageerror", lambda err: report["javascript_errors"].append(str(err)))
            page.goto(html.resolve().as_uri(), timeout=60000)
            page.wait_for_function('typeof DATA !== "undefined" && DATA.lot_trace && document.querySelector(".js-plotly-plot")', timeout=60000)
            inventory = page.evaluate('''() => {
                const t=DATA.lot_trace, all=Object.values(t.lots), finished=all.filter(l=>l.created_event_type==='production_output');
                const selected=[t.default_lot,
                    ...finished.filter(l=>l.business_lot_id==='PBATCH-411EC755D7110AE0').map(l=>l.lot_id),
                    finished[Math.floor(finished.length/2)]?.lot_id, finished.at(-1)?.lot_id];
                return {lots:all.length, finished:finished.length, default_model:t.default_view_model?.lot_id,
                    explicit_models:Object.keys(t.view_models||{}).length,
                    selected:[...new Set(selected.filter(Boolean))].map(id=>t.lots[id]).filter(Boolean)};
            }''')
            report["inventory"] = inventory
            page.locator('#modeOps').click()
            page.locator('#lotTraceOpenBtn').click()
            for lot in inventory["selected"]:
                page.locator('#lotTraceModalSelect').select_option(lot['lot_id'])
                page.locator('#lotTraceModal [data-lot-trace-direction="both"]').click()
                meta = page.locator('#lotTraceModalMeta').inner_text()
                match = re.search(r'(\d+)\s+lot\(s\)', meta)
                count = int(match.group(1)) if match else None
                identified = bool(lot.get('business_lot_id') or lot.get('business_lot_ids'))
                report['checks'].append({'lot_id': lot['lot_id'], 'business_lot_id': lot.get('business_lot_id'),
                    'name': 'identified_root_requires_positive_business_count', 'actual_count': count,
                    'ok': count is not None and (not identified or count >= 1), 'header': meta})
                causal = page.evaluate("""id => {
                  const p = DATA.lot_trace;
                  const model = (p.view_models || {})[id] || p.default_view_model;
                  const eventIds = JSON.parse(document.getElementById('lotTraceGraphWrap').dataset.causalEventIds || '[]');
                  const events = p.events.filter(row => eventIds.includes(row.event_id));
                  const links = model.links || [];
                  const campaigns = new Set(links.filter(row => row.link_type === 'production').map(row => row.production_campaign_id));
                  const upstream = new Set(model.snapshot.upstream_lot_ids);
                  const root = p.lots[id];
                  const unrelated = events.filter(row => String(row.event_type).includes('production_consume') && row.production_campaign_id && !campaigns.has(row.production_campaign_id));
                  const futureAncestors = events.filter(row => upstream.has(row.lot_id) && ['opening_stock','production_output','lane_receipt','external_procurement_receipt','estimated_source_receipt','estimated_capacity_receipt'].includes(row.event_type) && Number(row.day) > Number(root.created_day));
                  const overflow = [...document.querySelectorAll('#lotTraceGraphWrap .lotTraceGraphNode text')].filter(text => {
                    const rect = text.parentElement.querySelector('rect');
                    return rect && text.getBBox().x + text.getBBox().width > Number(rect.getAttribute('width')) + 1;
                  }).length;
                  const missingModels = (p.lot_options || []).filter(lot => !(p.view_models || {})[lot.lot_id]).length;
                  return {event_count: events.length, unrelated_campaign_events: unrelated.length, future_ancestor_creations: futureAncestors.length,
                          overflowing_labels: overflow, missing_models: missingModels, status: root.pf_availability_status};
                }""", lot['lot_id'])
                report['checks'].append({'lot_id': lot['lot_id'], 'name': 'causal_selection_and_readable_labels', **causal,
                    'ok': causal['event_count'] > 0 and all(causal[k] == 0 for k in ('unrelated_campaign_events','future_ancestor_creations','overflowing_labels','missing_models'))
                          and causal['status'] not in ('inputs_available','input_shortage')})
                page.screenshot(path=str(output / (lot['lot_id'] + '.png')))
                if lot.get('business_lot_id') == 'PBATCH-411EC755D7110AE0':
                    page.locator('#lotTraceModal [data-lot-trace-direction="downstream"]').click()
                    page.locator('#lotTraceFitBtn').click()
                    oracle = business_batch_csv_oracle(source_run, lot['business_lot_id']) if source_run is not None else None
                    quantities = page.evaluate("""arg => {
                        const id = arg.id;
                        const model = DATA.lot_trace.view_models[id];
                        const customer = model.links.filter(l => l.link_type === 'transport' && l.child_node_id === 'C-XXXXX' && Number(l.arrival_day ?? l.day) < arg.horizon);
                        return {contributions: customer.map(l => l.contribution_qty).sort((a,b)=>a-b),
                                links:customer.map(l=>({key:[l.parent_lot_id,l.child_lot_id,l.shipment_id],qty:l.contribution_qty})),
                                total: customer.reduce((sum,l)=>sum+l.contribution_qty,0),
                                root_qty: DATA.lot_trace.lots[id].qty};
                    }""", {'id': lot['lot_id'], 'horizon': oracle['horizon'] if oracle else float(10**9)})
                    actual = {tuple(row['key']): row['qty'] for row in quantities['links']}
                    matched = oracle is not None and oracle['root_lot_id'] == lot['lot_id'] and math.isclose(quantities['root_qty'], oracle['root_qty'], abs_tol=1e-6)
                    matched = matched and actual.keys() == oracle['contributions'].keys() and all(math.isclose(qty, oracle['contributions'][key], abs_tol=1e-6) for key, qty in actual.items())
                    report['checks'].append({'lot_id': lot['lot_id'], 'name': 'known_lot_customer_conservation_against_csv',
                        **quantities, 'expected_contributions': sorted(oracle['contributions'].values()) if oracle else None,
                        'remaining_not_received_qty': oracle['remaining_not_received_qty'] if oracle else None,
                        'ok': bool(matched), 'note': 'Explicit source run required; received amounts may change between scenarios.'})
                    page.screenshot(path=str(output / (lot['lot_id'] + '-downstream.png')))

        except Exception as exc:
            report['checks'].append({'name': 'browser_execution', 'ok': False, 'error': str(exc)})
        finally:
            browser.close()
    report['ok'] = bool(report['checks']) and all(c['ok'] for c in report['checks']) and not report['javascript_errors']
    (output/'lot-browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-run', type=Path)
    args = parser.parse_args()
    result = review(args.html, args.output, args.source_run)
    print(json.dumps({'ok': result['ok'], 'checks': result['checks']}, ensure_ascii=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
