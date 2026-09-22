"""Offline acceptance review: identity access, viewport and CSV-derived dated balances."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def review(html,data,graph,output):
    output.mkdir(parents=True,exist_ok=True)
    def read(name):
        with (data/name).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
    events,links=read('production_lot_events.csv'),read('production_lot_genealogy.csv')
    report=dict(html=str(html),sha256=hashlib.sha256(html.read_bytes()).hexdigest(),checks=[],javascript_errors=[])
    def check(name,ok,**details):
        report['checks'].append(dict(name=name,ok=bool(ok),**details));print(json.dumps({'check':name,'ok':bool(ok)}),flush=True)
    nodes={n['id']:n for n in json.loads(graph.read_text(encoding='utf-8-sig'))['nodes']}
    folder=Path(__file__).parents[1]/'visualization/maps'
    pure=(folder/'lot_journey.js').read_text(encoding='utf-8').split('function journeyLotSummaryHtml')[0]
    pure+=(folder/'lot_journey_timeline.js').read_text(encoding='utf-8').split('function journeyNetworkHtml')[0]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(offline=True,viewport={'width':1366,'height':768})
        page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
        try:
            page.goto(html.resolve().as_uri(),timeout=90000)
            page.wait_for_selector('#lotJourneyOpenBtn',state='attached',timeout=90000)
            page.locator('#modeOps').click();page.locator('#lotTraceSelect').select_option('LOT-00002658');page.locator('#lotJourneyOpenBtn').click()
            expected_searches={'PBATCH-411EC755D7110AE0':{'LOT-00002658','LOT-00002673','LOT-00002738','LOT-00002742'},'LOCC-00002658':{'LOT-00002658'},'STOCKLOT-00002658':{'LOT-00002658'}}
            for query,expected in expected_searches.items():
                page.locator('#journeySearch').fill(query)
                actual=set(page.locator('#journeySearchResults [data-journey-focus]').evaluate_all('els=>els.map(e=>e.dataset.journeyFocus)'))
                check('search_'+query,actual==expected,actual=sorted(actual))
            page.locator('#journeySearch').fill('338929')
            first=page.locator('#journeySearchResults [data-journey-focus]').evaluate_all('els=>els.map(e=>e.dataset.journeyFocus)')
            page.locator('[data-journey-search-page="1"]').click()
            second=page.locator('#journeySearchResults [data-journey-focus]').evaluate_all('els=>els.map(e=>e.dataset.journeyFocus)')
            check('pagination_distinct_pages',len(first)==len(second)==30 and not set(first)&set(second))
            page.locator('#journeyFilters summary').click();page.locator('[data-journey-filter="site"]').select_option('M-1810')
            page.locator('[data-journey-filter="from"]').fill('65');page.locator('[data-journey-filter="from"]').dispatch_event('change')
            page.locator('[data-journey-filter="to"]').fill('65');page.locator('[data-journey-filter="to"]').dispatch_event('change')
            actual=set(page.locator('#journeySearchResults [data-journey-focus]').evaluate_all('els=>els.map(e=>e.dataset.journeyFocus)'))
            expected={r['lot_id'] for r in events if r['event_type']=='lane_receipt' and r['day']=='65' and r['item_id']=='item:338929' and r['node_id']=='M-1810'}
            check('site_date_filter_matches_csv',actual==expected and bool(expected),actual=sorted(actual))
            page.locator('[data-journey-search-clear]').click()
            viewport=page.locator('.journeyNode').evaluate_all('els=>els.map(e=>{const r=e.getBoundingClientRect();return {id:e.dataset.journeyLot,left:r.left,right:r.right,top:r.top,bottom:r.bottom};})')
            check('four_pf_steps_visible_without_scroll',len(viewport)==4 and all(0<=r['left']<r['right']<=1366 and 0<=r['top']<r['bottom']<=768 for r in viewport),positions=viewport)
            page.screenshot(path=str(output/'explorer-1366.png'))
            page.locator('[data-journey-lot="LOT-00002738"]').click()
            check('inspection_distinct_from_root',page.locator('.journeyInspected').get_attribute('data-journey-lot')=='LOT-00002738' and page.locator('#lotJourney').get_attribute('data-journey-root')=='LOT-00002658' and page.locator('[data-journey-summary-lot]').get_attribute('data-journey-summary-lot')=='LOT-00002738')
            page.locator('[data-journey-tab="identity"]').click()
            identity=page.locator('.journeyIdentities').inner_text()
            check('identity_mixed_quality_unknown_and_scenario',all(s in identity for s in ['PBATCH-411EC755D7110AE0','Non documentées','scn:BASE']))
            # Independent balance for this PF: one homogeneous depot, two mixed customer receipts.
            root='LOT-00002658';depot='LOT-00002673'
            source=next(e for e in events if e['lot_id']==root and e['event_type']=='production_output')
            inbound=next(l for l in links if l['parent_lot_id']==root and l['child_lot_id']==depot)
            out=[l for l in links if l['parent_lot_id']==depot and l['link_type']=='transport']
            departure=lambda link:float(next(e for e in events if e['lot_id']==link['parent_lot_id'] and e['shipment_id']==link['shipment_id'] and e['event_type']=='lane_ship')['day'])
            def expected_at(day):
                quantities={k:[0.,0.] for k in ['factory','depot','transit','customer','served']}
                qty=float(source['qty']);received=0.
                if day<float(source['day']):return quantities,received
                if day<departure(inbound):quantities['factory']=[qty,qty]
                elif day<float(inbound['day']):quantities['transit']=[qty,qty]
                else:
                    quantities['depot']=[qty,qty]
                    for link in out:
                        q=float(link['parent_qty'])
                        if day<departure(link):continue
                        quantities['depot']=[v-q for v in quantities['depot']]
                        if day<float(link['day']):quantities['transit']=[v+q for v in quantities['transit']];continue
                        received+=q
                        receipt=next(e for e in events if e['lot_id']==link['child_lot_id'] and e['event_type']=='lane_receipt')
                        served=sum(float(e['qty']) for e in events if e['lot_id']==link['child_lot_id'] and e['event_type']=='demand_service' and float(e['day'])<=day)
                        total=float(receipt['qty']);bounds=[max(0,q-served),min(q,total-served)]
                        quantities['customer']=[a+b for a,b in zip(quantities['customer'],bounds)]
                        quantities['served']=[a+b for a,b in zip(quantities['served'],[q-bounds[1],q-bounds[0]])]
                return quantities,received
            for day in [278,279,280,281,282,291,292,293,294,305,306,308,309]:
                page.locator('#journeyDay').fill(str(day));page.locator('#journeyDay').dispatch_event('change')
                actual=page.locator('[data-network-category]').evaluate_all('els=>Object.fromEntries(els.map(e=>[e.dataset.networkCategory,[Number(e.dataset.low),Number(e.dataset.high)]]))')
                expected,received=expected_at(day)
                actual_received=page.locator('[data-network-received]').get_attribute('data-low') if page.locator('[data-network-received]').count() else None
                check('network_csv_day_'+str(day),all(actual.get(k,[0,0])==v for k,v in expected.items()) and actual_received is not None and float(actual_received)==received,expected=expected,actual=actual)
            page.locator('#journeyDay').fill('291');page.locator('#journeyDay').dispatch_event('change')
            page.screenshot(path=str(output/'day-291.png'))
            page.locator('[data-journey-all-days]').click()
            before=page.locator('.journeyCanvas').evaluate('e=>e.getBoundingClientRect().width')
            page.locator('[data-journey-zoom="-0.15"]').click()
            check('zoom_changes_geometry',page.locator('.journeyCanvas').evaluate('e=>e.getBoundingClientRect().width')<before)
            page.locator('[data-journey-fit]').click()
            page.locator('.journeyEdges path[data-journey-shipment-open]').first.focus()
            page.keyboard.press('Enter')
            check('edge_keyboard_opens_transport',page.locator('[data-journey-shipment-detail]').is_visible())
            results=page.evaluate("""({pure,nodes})=>{
              const t=DATA.lot_trace,api=new Function('LOT_TRACE','nodeById','lotTraceLotInfo','escapeTableHtml',pure+';return {local:journeyLotBalance,network:journeyNetworkBalance};')(t,nodes,id=>t.lots[id],String);
              const counts={},invalid=[];
              for(const id of Object.keys(t.lots)){const b=api.local(id);counts[b.status]=(counts[b.status]||0)+1;if(b.status!=='balanced')invalid.push({id,...b});}
              const network={},failures=[];
              for(const id of Object.keys(t.lots)){const b=api.network(id,null);network[b.status]=(network[b.status]||0)+1;if(b.status!=='balanced')failures.push({id,...b});}
              return {local:counts,local_failures:invalid,network,network_failures:failures};
            }""",dict(pure=pure,nodes=nodes))
            report['all_occurrences']=results
            check('all_local_ledgers_reconciled',not results['local_failures'],counts=results['local'])
            check('all_network_ledgers_supported',not results['network_failures'],counts=results['network'],examples=results['network_failures'][:10])
        except Exception as exc:check('execution',False,error=str(exc))
        finally:browser.close()
    report['ok']=bool(report['checks']) and all(c['ok'] for c in report['checks']) and not report['javascript_errors']
    (output/'explorer-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('html','data','graph','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(0 if review(args.html,args.data,args.graph,args.output)['ok'] else 1)
