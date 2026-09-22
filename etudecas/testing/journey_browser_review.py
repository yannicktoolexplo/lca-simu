"""Verify the simple lot journey against independent CSV paths in offline Chromium."""
import argparse
from collections import defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import re


def review(html, data, output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    with (data/'production_lot_events.csv').open(encoding='utf-8-sig', newline='') as f:
        events=list(csv.DictReader(f))
    with (data/'production_lot_genealogy.csv').open(encoding='utf-8-sig', newline='') as f:
        links=list(csv.DictReader(f))
    children,parents=defaultdict(set),defaultdict(set)
    for link in links:
        if link['link_type'] in ('production','transport') and float(link['parent_qty'])>0:
            children[link['parent_lot_id']].add(link['child_lot_id'])
            parents[link['child_lot_id']].add(link['parent_lot_id'])

    def reachable(root, mapping):
        found={root}; queue=deque([root])
        while queue:
            for other in mapping[queue.popleft()]-found:
                found.add(other);queue.append(other)
        return found

    report=dict(html=str(html),html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),checks=[],javascript_errors=[])

    def check(name, ok, **details):
        report['checks'].append(dict(name=name,ok=bool(ok),**details))
        print(json.dumps({'check':name,'ok':bool(ok)}),flush=True)

    def check_summary(page, lot_id):
        rows=[r for r in events if r['lot_id']==lot_id]
        sums=defaultdict(float)
        for row in rows:
            sums[row['event_type']]+=float(row['qty'])
        reserved_ships={r['shipment_id'] for r in rows if r['event_type']=='shipment_reserve'}
        dispatched_reserved=sum(float(r['qty']) for r in rows if r['event_type']=='lane_ship' and r['shipment_id'] in reserved_ships)
        expected=dict(entered=float(rows[0]['qty']),consumed=sums['production_consume']+sums['production_consume_reference_transition'],
                      shipped=sums['lane_ship'],served=sums['demand_service'],written_off=sums['writeoff']+sums['stock_writeoff'],
                      pending=sums['shipment_reserve']-dispatched_reserved,remaining=float(rows[-1]['qty_after']))
        panel=page.locator(f'[data-journey-summary-lot="{lot_id}"]')
        actual={r['key']:float(r['qty']) for r in panel.locator('[data-journey-metric]').evaluate_all("els=>els.map(e=>({key:e.dataset.journeyMetric,qty:e.dataset.quantity}))")}
        for key in ('pending','written_off'):
            actual.setdefault(key,0)
        ok=panel.locator('[data-journey-balance-status]').get_attribute('data-journey-balance-status')=='balanced' and all(abs(actual.get(k,float('inf'))-v)<0.00002 for k,v in expected.items())
        check('summary_matches_csv_'+lot_id,ok,expected=expected,actual=actual)
        text=panel.locator('[data-journey-metric="remaining"]').inner_text() if ok else ''
        check('summary_unit_and_last_day_'+lot_id,rows[-1]['uom'] in text and 'J'+rows[-1]['day'] in text)

    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page(offline=True,viewport={'width':1800,'height':1100})
            page.on('pageerror',lambda err:report['javascript_errors'].append(str(err)))
            page.goto(html.resolve().as_uri(),timeout=60000)
            page.wait_for_function('typeof DATA !== "undefined" && DATA.lot_trace && document.querySelector(".js-plotly-plot")',timeout=60000)
            page.locator('#modeOps').click();page.locator('#lotTraceOpenBtn').click()
            root='LOT-00002658'
            page.locator('#lotTraceModalSelect').select_option(root)
            legacy = page.locator('#lotTraceGraphWrap').inner_html()
            check('legacy_has_no_simplified_journey',page.locator('#lotTraceModal #lotJourney').count()==0)
            page.locator('#lotTraceModalCloseBtn').click()
            page.locator('#lotJourneyOpenBtn').click()
            check('separate_dialog',page.locator('#lotJourneyModal').is_visible() and not page.locator('#lotTraceModal').is_visible())
            journey=page.locator('#lotJourney')
            check_summary(page,root)
            scope=lambda:set(json.loads(journey.get_attribute('data-journey-scope')))
            check('pf_downstream_matches_csv',scope()==reachable(root,children),actual=sorted(scope()))
            check('compact_pf_diagram',journey.locator('.journeyNode').count()==4 and journey.locator('svg > path').count()==3)
            customer_links=[l for l in links if l['parent_lot_id'] in reachable(root,children) and l['child_node_id']=='C-XXXXX']
            contributions=[]
            for link in customer_links:
                card=journey.locator(f'[data-journey-lot="{link["child_lot_id"]}"]')
                text=card.inner_text()
                match=re.search(r'Part du PF suivi\s*:\s*([\d\s,.]+)',text)
                qty=float(re.sub(r'\s','',match.group(1)).replace(',','.')) if match else None
                contributions.append(qty)
                check('customer_contribution_'+link['shipment_id'],qty==float(link['parent_qty']),quantity=qty)
                check('shipment_on_card_'+link['shipment_id'],link['shipment_id'] in text)
            check('selected_pf_customer_conservation',sorted(contributions)==[3473,10927] and sum(contributions)==14400)
            page.locator('#lotJourneyBody').evaluate('(el)=>el.scrollTop=0')
            page.screenshot(path=str(output/'pf-destinations.png'))
            first=customer_links[0]
            journey.locator(f'[data-journey-lot="{first["child_lot_id"]}"]').click()
            check_summary(page,first['child_lot_id'])
            detail=journey.locator('.journeyDetails')
            check('shipment_dates_and_quantities_in_detail',first['shipment_id'] in detail.inner_text() and 'Départ :' in detail.inner_text() and 'Réception totale :' in detail.inner_text())
            journey.locator('[data-journey-tab="links"]').click()
            detail.locator(f'[data-journey-focus="{first["child_lot_id"]}"]').first.click()
            check('reverse_from_customer_matches_csv',scope()==reachable(first['child_lot_id'],parents))
            check('reverse_preserves_original_pf',root in scope())
            journey.locator('#journeySearch').fill('SHIP-00000203')
            results=journey.locator('#journeySearchResults button')
            check('shipment_search_returns_receipt',results.count()==1)
            receipt=next(e for e in events if e['event_type']=='lane_receipt' and e['shipment_id']=='SHIP-00000203')
            results.first.click()
            check_summary(page,receipt['lot_id'])
            journey.locator('button[data-journey-direction="downstream"]').click()
            check('material_receipt_downstream_matches_csv',scope()==reachable(receipt['lot_id'],children))
            production_ids={e['lot_id'] for e in events if e['event_type']=='production_output' and e['lot_id'] in scope()}
            check('receipt_reaches_exactly_two_productions',production_ids=={'LOT-00002653','LOT-00002658'})
            check('no_material_to_pf_quantity_invented','Part du PF suivi' not in journey.inner_text())
            page.locator('#lotJourneyBody').evaluate('(el)=>el.scrollTop=0')
            page.screenshot(path=str(output/'material-destinations.png'))
            from .journey_operations_browser import check_operations
            check_operations(page,events,links,check,output)
            reservation_lot=next(e['lot_id'] for e in events if e['event_type']=='shipment_reserve')
            kg_lot=next(e['lot_id'] for e in events if e['event_type']=='production_consume' and e['uom']=='KG')
            for extra in [reservation_lot,kg_lot]:
                journey.locator('#journeySearch').fill(extra)
                journey.locator(f'#journeySearchResults button[data-journey-focus="{extra}"]').click()
                check_summary(page,extra)
            journey.locator(f'button[data-journey-focus="{root}"]').first.click()
            check('return_to_main_lot',journey.get_attribute('data-journey-root')==root and page.locator('#lotTraceModalSelect').input_value()==root)
            check('legacy_content_unchanged_by_navigation',page.locator('#lotTraceGraphWrap').inner_html()==legacy)
            page.locator('#lotJourneyCloseBtn').click()
            page.locator('#lotTraceOpenBtn').click()
            check('legacy_reopens_independently',page.locator('#lotTraceModal').is_visible() and not page.locator('#lotJourneyModal').is_visible() and page.locator('#lotTraceModal #lotJourney').count()==0)
        except Exception as exc:
            check('browser_execution',False,error=str(exc))
        finally:
            browser.close()
    report['ok']=bool(report['checks']) and all(c['ok'] for c in report['checks']) and not report['javascript_errors']
    (output/'journey-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('html','data','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    report=review(args.html,args.data,args.output)
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['ok'] else 1


if __name__=='__main__':
    raise SystemExit(main())
