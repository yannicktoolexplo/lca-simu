"""Check a real scenario explorer against its own events, not nominal IDs."""
import argparse
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from etudecas.simulation.lot_trace.io import read_csv_rows


def review(html,data,output):
    events=read_csv_rows(data/'production_lot_events.csv')
    links=read_csv_rows(data/'production_lot_genealogy.csv')
    target=next(r for r in events if r['event_type']=='lane_receipt' and r.get('risk_event_ids'))
    report={'html':str(html),'sha256':hashlib.sha256(html.read_bytes()).hexdigest(),'checks':[],'javascript_errors':[]}
    output.mkdir(parents=True,exist_ok=True)
    def check(name,ok,**details):report['checks'].append(dict(name=name,ok=bool(ok),**details))
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(offline=True,viewport={'width':1366,'height':768})
        page.on('pageerror',lambda error:report['javascript_errors'].append(str(error)))
        try:
            page.goto(html.resolve().as_uri(),timeout=90000);page.wait_for_selector('#lotJourneyModal.visible',timeout=90000)
            check('scenario_identified',target['scenario_id'] in page.locator('#lotJourneyTitle').inner_text())
            actual=page.evaluate('({events:DATA.lot_trace.events.length,links:DATA.lot_trace.genealogy.length,lots:Object.keys(DATA.lot_trace.lots).length,scenarios:[...new Set(DATA.lot_trace.events.map(r=>r.scenario_id))]})')
            check('only_this_scenario_embedded',actual==dict(events=len(events),links=len(links),lots=len({r['lot_id'] for r in events}),scenarios=[target['scenario_id']]),actual=actual)
            page.locator('[data-journey-tab="identity"]').click()
            text=page.locator('.journeyIdentities').inner_text()
            check('native_risks_visible',all(risk in text for risk in target['risk_event_ids'].split(',')))
            page.locator('#journeyDay').fill(str(target['day']));page.locator('#journeyDay').dispatch_event('change')
            page.locator('[data-journey-tab="summary"]').click()
            remaining=float(page.locator('[data-journey-metric="remaining"]').get_attribute('data-quantity'))
            rows=[r for r in events if r['lot_id']==target['lot_id'] and float(r['day'])<=float(target['day'])]
            check('dated_local_balance_matches_scenario_csv',remaining==float(rows[-1]['qty_after']))
            check('network_balance_available',page.locator('[data-journey-network-status]').get_attribute('data-journey-network-status')=='exact')
            page.locator('[data-journey-tab="operations"]').click();page.locator('#journeyTransports > summary').click()
            page.locator(f'#journeyTransports [data-journey-shipment-open="{target["shipment_id"]}"]').click()
            actual_events=set(page.locator('[data-shipment-event]').evaluate_all('els=>els.map(e=>e.dataset.shipmentEvent)'))
            expected={r['event_id'] for r in events if r['shipment_id']==target['shipment_id'] and r['event_type'] in ('lane_ship','lane_receipt','shipment_reserve')}
            check('shipment_uses_scenario_events',actual_events==expected)
            check('scenario_transport_graph_matches',page.evaluate('!DATA.lot_trace.truck_consolidation.error && DATA.lot_trace.truck_consolidation.groups.length>0'))
            page.locator('[data-journey-tab="identity"]').click();page.screenshot(path=str(output/'risk-scenario.png'))
        except Exception as exc:check('execution',False,error=str(exc))
        finally:browser.close()
    report['ok']=all(c['ok'] for c in report['checks']) and not report['javascript_errors']
    (output/'scenario-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('html','data','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();report=review(args.html,args.data,args.output)
    print(json.dumps(report,ensure_ascii=True));raise SystemExit(0 if report['ok'] else 1)
