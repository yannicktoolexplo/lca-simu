"""Historical browser regressions grouped by the investigation they exercise.

These checks contain fixed historical lot identities and quantities. Use them
with their matching dataset. Current delivery qualification uses map_browser
and lot_browser_review, whose selected lot is reconciled with the supplied CSVs.
"""
import argparse
from collections import defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import re
from playwright.sync_api import sync_playwright
from etudecas.simulation.lot_trace.schema import read_csv_rows
import time


def review_journey(html, data, output):
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


def review_case(html,scenario_html,data,output):
    output.mkdir(parents=True,exist_ok=True)
    with (data/'production_lot_genealogy.csv').open(encoding='utf-8-sig',newline='') as f:links=list(csv.DictReader(f))
    report=dict(html=str(html),html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),scenario_html=str(scenario_html),scenario_html_sha256=hashlib.sha256(scenario_html.read_bytes()).hexdigest(),checks=[],javascript_errors=[])
    def check(name,ok,**details):
        report['checks'].append(dict(name=name,ok=bool(ok),**details));print(json.dumps(dict(check=name,ok=bool(ok))),flush=True)
    def open_case_controls(page):
        if not page.locator('.journeyCaseTools').evaluate('e=>e.open'):page.locator('.journeyCaseTools summary').click()
    def download(page,selector,path):
        open_case_controls(page)
        with page.expect_download(timeout=90000) as pending:page.locator(selector).click()
        pending.value.save_as(path)
    def open_map(page):
        page.goto(html.resolve().as_uri(),timeout=90000);page.wait_for_selector('#lotJourneyOpenBtn',state='attached',timeout=90000)
        page.locator('#modeOps').click();page.locator('#lotTraceSelect').select_option('LOT-00002658');page.locator('#lotJourneyOpenBtn').click()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(offline=True,viewport={'width':1366,'height':768});page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
        try:
            open_map(page)
            page.locator('#journeyDay').fill('291');page.locator('#journeyDay').dispatch_event('change')
            full_scope=page.locator('#lotJourney').get_attribute('data-journey-scope')
            network=lambda:page.locator('[data-network-category]').evaluate_all('els=>els.map(e=>[e.dataset.networkCategory,e.dataset.low,e.dataset.high])')
            before=network();page.locator('#journeyDepth').select_option('1')
            visible=lambda:page.locator('.journeyNode').evaluate_all('els=>els.map(e=>e.dataset.journeyLot)')
            check('depth_one_hides_only_distant_cards',set(visible())=={'LOT-00002658','LOT-00002673'} and page.locator('#lotJourney').get_attribute('data-journey-scope')==full_scope)
            check('network_not_truncated_by_neighbourhood',before==network() and ['depot','10927','10927'] in before and ['transit','3473','3473'] in before)
            page.locator('[data-journey-lot="LOT-00002673"]').click()
            download(page,'[data-journey-case-save]',output/'enquete-pf-j291.json')
            doc=json.loads((output/'enquete-pf-j291.json').read_text(encoding='utf-8'))
            check('case_contains_only_navigation_and_dataset_binding',set(doc)=={'format','saved_at','dataset','view'} and doc['view']['day']==291 and doc['view']['depth']==1 and doc['dataset']['scenarios']==['scn:BASE'])
            download(page,'[data-journey-case-report]',output/'fiche-pf-j291.html')
            printed=browser.new_page(offline=True);printed.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
            printed.goto((output/'fiche-pf-j291.html').resolve().as_uri());text=printed.locator('body').inner_text()
            check('report_is_readable_offline_without_script',printed.locator('script').count()==0 and 'Fin de J291' in text and 'scn:BASE' in text and doc['dataset']['sha256'] in text)
            expected_links=[l for l in links if l['link_type']=='transport' and l['parent_lot_id'] in {'LOT-00002658','LOT-00002673'}]
            check('report_full_links_despite_reduced_graph',len(expected_links)==3 and all(l['shipment_id'] in text for l in expected_links) and 'Liens du parcours complet (3)' in text)
            row=printed.locator('tr').filter(has=printed.locator('td',has_text='Stock dépôt')).inner_text()
            check('report_network_matches_csv',row.split('\t')[-1].replace('\u202f','').replace('\xa0','').replace(' ','').replace(',0','')=='10927')
            printed.emulate_media(media='print');printed.pdf(path=str(output/'fiche-pf-j291.pdf'),format='A4',print_background=True);printed.close()
            open_map(page);legacy=page.locator('#lotTraceSelect').input_value()
            open_case_controls(page);page.locator('#journeyCaseFile').set_input_files(output/'enquete-pf-j291.json')
            page.wait_for_function("document.getElementById('journeyCaseMessage').textContent.includes('restaurée')",timeout=90000)
            check('reopen_after_full_reload_restores_view',page.locator('#journeyDay').input_value()=='291' and page.locator('#journeyDepth').input_value()=='1' and page.locator('.journeyInspected').get_attribute('data-journey-lot')=='LOT-00002673' and len(visible())==2)
            check('reopen_preserves_legacy_selection',page.locator('#lotTraceSelect').input_value()==legacy)
            page.locator('[data-journey-expand]').click()
            check('expanding_depot_recovers_two_client_receipts',set(visible())=={'LOT-00002658','LOT-00002673','LOT-00002738','LOT-00002742'})
            page.locator('[data-journey-fit]').click();page.screenshot(path=str(output/'enquete-restauree.png'))
            page.locator('#journeySearch').fill('LOT-00000003');page.locator('#journeySearchResults [data-journey-focus="LOT-00000003"]').click()
            full=json.loads(page.locator('#lotJourney').get_attribute('data-journey-scope'));shown=visible()
            check('large_scope_has_explicit_reduced_neighbourhood',len(full)>300 and len(shown)<len(full),full=len(full),visible=len(shown))
            check('no_fabricated_lots_in_neighbourhood',set(shown)<=set(full))
            page.screenshot(path=str(output/'grand-parcours.png'))
            # A nominal case must fail even though the risk scenario reuses LOT IDs.
            risk=browser.new_page(offline=True,viewport={'width':1366,'height':768});risk.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
            risk.goto(scenario_html.resolve().as_uri(),timeout=90000);risk.wait_for_selector('#lotJourneyModal.visible',timeout=90000)
            risk_root=risk.locator('#lotJourney').get_attribute('data-journey-root');open_case_controls(risk)
            risk.locator('#journeyCaseFile').set_input_files(output/'enquete-pf-j291.json')
            risk.wait_for_function("document.getElementById('journeyCaseMessage').textContent.includes('différentes')",timeout=90000)
            check('nominal_case_rejected_by_risk_without_navigation_change',risk.locator('#lotJourney').get_attribute('data-journey-root')==risk_root)
            download(risk,'[data-journey-case-save]',output/'enquete-risque.json')
            risk_doc=json.loads((output/'enquete-risque.json').read_text(encoding='utf-8'))
            check('risk_case_has_own_identity',risk_doc['dataset']['sha256']!=doc['dataset']['sha256'] and risk_doc['dataset']['scenarios']==['scn:STATE_DEPENDENT_FULL'])
            risk.close()
        except Exception as exc:check('execution',False,error=str(exc))
        finally:browser.close()
    report['ok']=bool(report['checks']) and all(c['ok'] for c in report['checks']) and not report['javascript_errors']
    (output/'case-browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def review_explorer(html,data,graph,output):
    output.mkdir(parents=True,exist_ok=True)
    def read(name):
        with (data/name).open(encoding='utf-8-sig',newline='') as stream:return list(csv.DictReader(stream))
    events,links=read('production_lot_events.csv'),read('production_lot_genealogy.csv')
    report=dict(html=str(html),sha256=hashlib.sha256(html.read_bytes()).hexdigest(),checks=[],javascript_errors=[])
    def check(name,ok,**details):
        report['checks'].append(dict(name=name,ok=bool(ok),**details));print(json.dumps({'check':name,'ok':bool(ok)}),flush=True)
    nodes={n['id']:n for n in json.loads(graph.read_text(encoding='utf-8-sig'))['nodes']}
    folder=Path(__file__).parents[1]/'visualization/maps'
    script=(folder/'lot_journey.js').read_text(encoding='utf-8')
    pure=script.split('function journeyLotSummaryHtml')[0]
    pure+='function journeyNetworkBalance'+script.split('function journeyNetworkBalance',1)[1].split('function journeyNetworkHtml',1)[0]
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


def check_operations(page, events, links, check, output):
    def fingerprint():
        return page.evaluate("""async () => {
          const hashes=[], encoder=new TextEncoder(),trace=DATA.lot_trace;
          const collections=[trace.events,trace.genealogy,Object.values(trace.lots).map(l=>[l.lot_id,l.qty,l.uom,l.node_id,l.item_id,l.created_day])];
          for (const rows of collections) for (let start=0;start<rows.length;start+=500) {
            const digest=await crypto.subtle.digest('SHA-256',encoder.encode(JSON.stringify(rows.slice(start,start+500))));
            hashes.push(Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join(''));
          }
          return hashes;
        }""")
    before=fingerprint()
    journey=page.locator('#lotJourney')
    seed='LOT-00000838'
    assert journey.get_attribute('data-journey-root')==seed
    descendants=defaultdict(set)
    for link in links:
        if link['link_type'] in ('production','transport') and float(link['parent_qty'])>0:
            descendants[link['parent_lot_id']].add(link['child_lot_id'])
    expected={seed};queue=deque([seed])
    while queue:
        for child in descendants[queue.popleft()]-expected:
            expected.add(child);queue.append(child)
    journey.locator('[data-journey-tab="operations"]').click()
    journey.locator('#journeyImpacts > summary').click()
    journey.locator('[data-journey-impact-occurrence]').click()
    actual=set(json.loads(journey.locator('[data-journey-impact-scope]').get_attribute('data-journey-impact-scope')))
    check('impact_exact_descendants_from_csv',actual==expected,occurrences=len(actual))
    check('impact_all_visible_descendants_highlighted',journey.locator('.journeyImpacted').count()==len(expected))
    check('impact_unknown_supplier_lot_explicit',journey.locator('#journeyOriginSelect').count()==0 and 'Aucun lot fabricant' in journey.locator('#journeyImpacts').inner_text())
    shipments={e['shipment_id'] for e in events if e['lot_id'] in expected and e['shipment_id'] and e['event_type'] in ('lane_ship','lane_receipt','shipment_reserve')}
    actual_ships=set(journey.locator('#journeyImpacts [data-journey-shipment-open]').evaluate_all('els=>els.map(e=>e.dataset.journeyShipmentOpen)'))
    check('impact_shipments_match_csv',actual_ships==shipments)
    page.screenshot(path=str(output/'impact-scope.png'))
    # A customer shipment mixes the selected PF and another PF. Inspect its
    # full physical cargo, not just the selected PF's contribution.
    ship='SHIP-00001396'
    journey.locator('#journeyTransports > summary').click()
    journey.locator('#journeyTransports [data-journey-shipment-open="SHIP-00000203"]').first.click()
    # Inspect the inbound supplier planning group, with its current estimates.
    group_ids=page.evaluate("id=>DATA.lot_trace.truck_consolidation.groups.filter(g=>g.shipment_ids.includes(id)).map(g=>g.id)",'SHIP-00000203')
    actual_groups=journey.locator('[data-journey-truck-group]').evaluate_all('els=>els.map(e=>e.dataset.journeyTruckGroup)')
    check('transport_reuses_existing_planning_groups',sorted(actual_groups)==sorted(group_ids) and bool(actual_groups))
    check('transport_marks_estimates_and_no_actual_vehicle','camion(s) estimé(s)' in journey.locator('#journeyTransports').inner_text() and 'Aucun camion réel identifié' in journey.locator('#journeyTransports').inner_text())
    page.screenshot(path=str(output/'supplier-transport.png'))
    # Reveal the shipment list inside the impact panel before using its link.
    journey.locator('#journeyImpacts details').filter(has=page.locator(f'[data-journey-shipment-open="{ship}"]')).locator('summary').click()
    journey.locator(f'#journeyImpacts [data-journey-shipment-open="{ship}"]').click()
    panel=journey.locator(f'[data-journey-shipment-detail="{ship}"]')
    expected_events={e['event_id'] for e in events if e['shipment_id']==ship and e['event_type'] in ('lane_ship','lane_receipt','shipment_reserve')}
    actual_events=set(panel.locator('[data-shipment-event]').evaluate_all('els=>els.map(e=>e.dataset.shipmentEvent)'))
    check('transport_all_cargo_events_match_csv',actual_events==expected_events)
    expected_total=sum(float(e['qty']) for e in events if e['shipment_id']==ship and e['event_type']=='lane_ship')
    check('transport_total_not_selected_pf_portion',float(panel.locator('[data-journey-shipped-item="item:268091"]').get_attribute('data-quantity'))==expected_total==13251)
    expected_sources={e['lot_id'] for e in events if e['shipment_id']==ship and e['event_type']=='lane_ship'}
    actual_sources=set(panel.locator('[data-journey-focus]').evaluate_all('els=>els.map(e=>e.dataset.journeyFocus)'))
    check('transport_contains_both_source_lots',len(expected_sources)==2 and expected_sources<=actual_sources)
    check('transport_inspection_preserves_impact_scope',set(json.loads(journey.locator('[data-journey-impact-scope]').get_attribute('data-journey-impact-scope')))==expected)
    page.screenshot(path=str(output/'customer-transport.png'))
    journey.locator('[data-journey-impact-clear]').click()
    check('impact_reset_removes_highlights',journey.locator('.journeyImpacted').count()==0 and journey.locator('[data-journey-impact-scope]').count()==0)
    journey.locator('[data-journey-shipment-close]').click()
    check('transport_and_impact_preserve_physical_ledger',before==fingerprint())


def review_scenario(html,data,output):
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


def review_material(html, data, output):
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with (data / "production_lot_genealogy.csv").open(encoding="utf-8-sig", newline="") as handle:
        links = list(csv.DictReader(handle))
    with (data / "production_lot_events.csv").open(encoding="utf-8-sig", newline="") as handle:
        events = list(csv.DictReader(handle))
    # Independent expectation, from the CSVs rather than the display builder.
    receipt = next(e for e in events if e["event_type"] == "lane_receipt" and e["shipment_id"] == "SHIP-00000203")
    adjacency = defaultdict(set)
    for link in links:
        if link["link_type"] in {"production", "transport"} and float(link["parent_qty"]) > 0:
            adjacency[link["parent_lot_id"]].add(link["child_lot_id"])
    reached = {receipt["lot_id"]}
    queue = deque(reached)
    while queue:
        for child in adjacency[queue.popleft()] - reached:
            reached.add(child)
            queue.append(child)
    expected_outputs = sorted({e["lot_id"] for e in events if e["event_type"] == "production_output" and e["lot_id"] in reached})
    report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                  checks=[], javascript_errors=[], scope="Receipt quantities, unknown origin, independent recall scope, unrelated branch exclusion, UI reset and source immutability.")

    def check(name, ok, **evidence):
        report["checks"].append(dict(name=name, ok=bool(ok), **evidence))
        print(json.dumps({"check": name, "ok": bool(ok)}), flush=True)

    def physical_fingerprint(page):
        return page.evaluate("""async () => {
          const trace=DATA.lot_trace, hashes=[], encoder=new TextEncoder();
          const collections=[trace.events, trace.genealogy,
            Object.values(trace.lots).map(l=>[l.lot_id,l.qty,l.uom,l.node_id,l.item_id,l.created_day])];
          for (const rows of collections) {
            for (let start=0; start<rows.length; start+=500) {
              const digest=await crypto.subtle.digest('SHA-256',encoder.encode(JSON.stringify(rows.slice(start,start+500))));
              hashes.push(Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join(''));
            }
          }
          return hashes;
        }""")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(offline=True, viewport={"width": 1800, "height": 1100})
            page.on("pageerror", lambda err: report["javascript_errors"].append(str(err)))
            page.goto(html.resolve().as_uri(), timeout=60000)
            page.wait_for_function('typeof DATA !== "undefined" && DATA.lot_trace && document.querySelector(".js-plotly-plot")', timeout=60000)
            print('Page loaded; fingerprinting physical data in bounded chunks.', flush=True)
            before = physical_fingerprint(page)
            print('Physical fingerprint complete.', flush=True)
            page.locator("#modeOps").click()
            page.locator("#lotTraceOpenBtn").click()
            page.locator("#lotTraceModalSelect").select_option("LOT-00002658")
            page.locator('#lotTraceModal [data-lot-trace-direction="both"]').click()
            article = page.locator('[data-material-article="item:338929"]')
            article.locator("summary").click()
            quantities = article.locator("[data-material-consumed]").evaluate_all("nodes => nodes.map(n => Number(n.dataset.materialConsumed)).sort((a,b)=>a-b)")
            check("four_receipts_consumed_quantities", quantities == [2000, 2400, 5000, 5000], quantities=quantities)
            check("unknown_origins_not_fabricated", article.inner_text().count("Lot fournisseur inconnu") == 4)
            check("containers_not_invented", article.inner_text().count("Contenants non renseignés") == 4)
            check("truck_estimate_label", article.inner_text().count("camion(s) estimé(s)") == 4)
            article.scroll_into_view_if_needed()
            page.screenshot(path=str(output / "receipts-338929.png"))
            page.locator(f'[data-material-target="{receipt["event_id"]}"]').click()
            panel = page.locator('.lotTraceMaterialIncidents')
            actual = dict(potential_production_lot_ids=json.loads(panel.get_attribute('data-production-lots')),
                          potential_lot_ids=json.loads(panel.get_attribute('data-potential-lots')))
            check("recall_matches_independent_csv", actual["potential_production_lot_ids"] == expected_outputs
                  and sorted(actual["potential_lot_ids"]) == sorted(reached), expected_outputs=expected_outputs,
                  actual_outputs=actual["potential_production_lot_ids"])
            check("selected_root_marked", page.locator('.lotTraceGraphNode.root.materialExposed').count() == 1)
            panel_text = page.locator(".lotTraceMaterialIncidents").inner_text()
            check("hypothesis_and_no_replay_visible", "Exploration hypothétique" in panel_text and "restent inchangés" in panel_text)
            page.screenshot(path=str(output / "recall-receipt.png"))
            other = next(id for id in expected_outputs if id != "LOT-00002658")
            page.locator('[data-material-affected-select]').select_option(other)
            check("navigate_affected_lot", page.locator('#lotTraceModalSelect').input_value() == other
                  and page.locator('#lotTraceSelect').input_value() == other)
            unrelated = page.evaluate("ids => Object.values(DATA.lot_trace.lots).find(l=>l.created_event_type==='production_output' && !ids.includes(l.lot_id)).lot_id", actual['potential_lot_ids'])
            page.locator('#lotTraceModalSelect').select_option(unrelated)
            check("unrelated_lot_excluded", "hors de ce périmètre" in page.locator('.lotTraceMaterialIncidents').inner_text()
                  and page.locator('.lotTraceGraphNode.root.materialExposed').count() == 0)
            page.locator('[data-material-clear]').click()
            check("reset_exploration", panel.get_attribute('data-preview-active') == 'false' and page.locator('.materialIncidentCard').count() == 0)
            after = physical_fingerprint(page)
            check("physical_payload_unchanged", before == after)
            # Two hypothetical receipt mappings in browser memory only. Never
            # written into the delivered nominal HTML or its input data.
            page.evaluate("""() => {
              const context=DATA.lot_trace.material_traceability;
              const chosen=Object.values(context.receipts).filter(r=>['SHIP-00000203','SHIP-00000251'].includes(r.shipment_id));
              context.origins['TEST-SUPPLIER-LOT']={id:'TEST-SUPPLIER-LOT', batch_number:'TEST ONLY', manufacturer_id:'TEST', status:'simulated',source_reference:'browser-test'};
              chosen.forEach(r=>r.origins=[{origin_id:'TEST-SUPPLIER-LOT', quantity:r.quantity}]);
            }""")
            page.locator('#lotTraceModalSelect').select_option('LOT-00002658')
            page.locator('[data-material-article="item:338929"] summary').click()
            page.locator('[data-material-preview="supplier_lot"]').first.click()
            check("supplier_lot_groups_receipts_only_when_explicit", len(json.loads(panel.get_attribute('data-receipt-ids'))) == 2)
        except Exception as exc:
            check("browser_execution", False, error=str(exc))
        finally:
            browser.close()
    report["ok"] = bool(report["checks"]) and all(c["ok"] for c in report["checks"]) and not report["javascript_errors"]
    (output / "material-browser.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def audit_usability(html, output):
    output.mkdir(parents=True, exist_ok=True)
    script=(Path(__file__).parents[1]/'visualization/maps/lot_journey.js').read_text(encoding='utf-8')
    pure=script[:script.index('function journeyLotSummaryHtml')]
    report={'html':str(html),'sha256':hashlib.sha256(html.read_bytes()).hexdigest(),'javascript_errors':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(offline=True,viewport={'width':1366,'height':768})
        page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
        start=time.perf_counter()
        page.goto(html.resolve().as_uri(),timeout=90000)
        page.wait_for_function('typeof DATA!=="undefined" && DATA.lot_trace && document.querySelector(".js-plotly-plot")',timeout=90000)
        report['load_seconds']=round(time.perf_counter()-start,2)
        report['data']=page.evaluate("""pure=>{
          const t=DATA.lot_trace,lots=Object.values(t.lots),counts={},bad=[];
          const inspect=new Function('LOT_TRACE','nodeById','lotTraceLotInfo','escapeTableHtml',pure+';return {balance:journeyLotBalance,scope:journeyScope};');
          const api=inspect(t,{},id=>t.lots[id],String);
          for (const lot of lots) {const r=api.balance(lot.lot_id);counts[r.status]=(counts[r.status]||0)+1;if(r.status!=='balanced')bad.push({id:lot.lot_id,...r});}
          const s=api.scope('LOT-00000003','downstream');
          const m=t.material_traceability || {},g=t.truck_consolidation?.groups || [];
          return {keys:Object.keys(DATA),lot_count:lots.length,event_count:t.events.length,link_count:t.genealogy.length,
            balance_status:counts,balance_exceptions:bad.slice(0,30),business_mixed:lots.filter(l=>l.business_identity_status==='mixed').length,
            opening_stock:lots.filter(l=>l.created_event_type==='opening_stock').length,manufacturer_origins:Object.keys(m.origins || {}).length,
            inbound_handling_units:Object.values(m.receipts || {}).reduce((n,r)=>n+r.handling_units.length,0),
            transport_groups:g.length,estimated_groups:g.filter(r=>r.estimated_truck_count!=null).length,proposed_groups:g.filter(r=>r.truck_count!=null).length,
            unknown_groups:g.filter(r=>r.truck_count==null && r.estimated_truck_count==null).length,
            broad_scope:{root:'LOT-00000003',lots:s.lot_ids.length,links:s.links.length},
            signaled:lots.filter(l=>l.business_lot_id==='PBATCH-411EC755D7110AE0' || (l.business_lot_ids || []).includes('PBATCH-411EC755D7110AE0')).map(l=>({id:l.lot_id,business:l.business_lot_id,occurrence:l.stock_occurrence_id,status:l.business_identity_status,node:l.node_id}))};
        }""",pure)
        page.locator('#modeOps').click()
        page.locator('#lotTraceSelect').select_option('LOT-00002658')
        page.locator('#lotJourneyOpenBtn').click()
        page.screenshot(path=str(output/'overview-1366.png'))
        searches=[]
        for query in ['PBATCH-411EC755D7110AE0','LOCC-00002658','LOT-00002658','SHIP-00001396','338929']:
            start=time.perf_counter();page.locator('#journeySearch').fill(query)
            searches.append({'query':query,'text':page.locator('#journeySearchResults').inner_text(),'buttons':page.locator('#journeySearchResults button').count(),'seconds':round(time.perf_counter()-start,3)})
        report['searches']=searches
        page.locator('#journeySearch').fill('')
        page.locator('[data-journey-lot="LOT-00002738"]').click()
        report['after_card_click']={
            'graph_focus':page.locator('#lotJourney').get_attribute('data-journey-root'),
            'summary_lot':page.locator('[data-journey-summary-lot]').get_attribute('data-journey-summary-lot'),
            'direction':page.locator('#lotJourney').get_attribute('data-journey-direction')}
        page.locator('.journeyDetails [data-journey-focus="LOT-00002738"]').first.click()
        report['reverse_customer_scope']=json.loads(page.locator('#lotJourney').get_attribute('data-journey-scope'))
        page.locator('#journeySearch').fill('LOT-00000003')
        page.locator('#journeySearchResults button').first.click()
        start=time.perf_counter();page.locator('button[data-journey-direction="downstream"]').click()
        report['broad_view']={'seconds':round(time.perf_counter()-start,2),'cards':page.locator('.journeyNode').count(),
                             'notice':page.locator('#lotJourney').inner_text()[-1800:]}
        page.screenshot(path=str(output/'broad-scope-1366.png'))
        report['controls']=page.locator('#lotJourney').evaluate("e=>({scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,buttons:[...e.querySelectorAll('button')].map(b=>b.textContent),inputs:[...e.querySelectorAll('input')].map(i=>({id:i.id,type:i.type}))})")
        browser.close()
    (output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['load_seconds','data','after_card_click','broad_view','javascript_errors']},ensure_ascii=True))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='mode', required=True)
    signatures = {
        'journey': (review_journey, ('html', 'data', 'output')),
        'case': (review_case, ('html', 'scenario_html', 'data', 'output')),
        'explorer': (review_explorer, ('html', 'data', 'graph', 'output')),
        'scenario': (review_scenario, ('html', 'data', 'output')),
        'material': (review_material, ('html', 'data', 'output')),
        'usability': (audit_usability, ('html', 'output')),
    }
    for mode, (_, names) in signatures.items():
        command = commands.add_parser(mode)
        for name in names:
            command.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    args = parser.parse_args(argv)
    function, names = signatures[args.mode]
    result = function(*(getattr(args, name) for name in names))
    print(json.dumps(result, ensure_ascii=True))
    # Usability is an observation report; it has no scientific pass/fail field.
    return 0 if args.mode == 'usability' or result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
