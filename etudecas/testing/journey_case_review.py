"""Round-trip investigations and exported reports in real offline delivered maps."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def review(html,scenario_html,data,output):
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


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('html','scenario-html','data','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();raise SystemExit(0 if review(a.html,a.scenario_html,a.data,a.output)['ok'] else 1)
