"""Offline audit-view checks, preserving source files and simulated values."""
import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / 'POC2026/supply_geo_case'
HTML = CASE / 'outputs/maps/supply_geo_base_results_map.html'
VENDOR = ROOT / 'etudecas/visualization/maps/vendor'


def main():
    evidence = CASE / 'outputs/checks' / ('supplier_role_browser_' + uuid4().hex)
    evidence.mkdir(parents=True)
    report = {'status':'failed', 'checks':[], 'html_sha256':hashlib.sha256(HTML.read_bytes()).hexdigest()}
    audit = json.loads((CASE/'outputs/summaries/supplier_role_audit.json').read_text(encoding='utf-8'))
    with (CASE/'outputs/data/primary_supply_sites.csv').open(encoding='utf-8-sig',newline='') as f:
        original = list(csv.DictReader(f))
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':1000})
                def route(r):
                    url = r.request.url
                    if url.startswith('file:'):
                        r.continue_()
                    elif 'plotly-2.32.0.min.js' in url:
                        r.fulfill(path=str(VENDOR/'plotly-2.32.0.min.js'),content_type='application/javascript')
                    elif 'world_110m.json' in url:
                        r.fulfill(path=str(VENDOR/'world_110m.json'),content_type='application/json')
                    else:
                        r.abort()
                page.route('**/*',route)
                page.on('pageerror',lambda err:errors.append(str(err)))
                page.goto(HTML.as_uri(),wait_until='load')
                page.click('[data-sdd-view="context"]')
                for name in ['Euralliage Ile de France','Mitsubishi Chemical','Alcoa']:
                    row = next(r for r in audit['rows'] if r['name']==name)
                    page.evaluate("uid=>document.getElementById('chart').emit('plotly_click',{points:[{customdata:['site',uid]}]})",row['site_uid'])
                    body = page.locator('#sddClickPanelBody').inner_text()
                    assert row['status_label'] in body and row['proposed_role'] in body, name
                    assert 'pas des relations commerciales prouvees' in body
                    if name=='Mitsubishi Chemical':
                        assert 'plusieurs localisations' in body
                    report['checks'].append({'site':name,'status':row['status_label']})
                    if name=='Euralliage Ile de France':
                        page.screenshot(path=str(evidence/'euralliage.png'))
                    page.click('#sddClickPanelClose')
                page.click('[data-sdd-view="dashboard"]')
                assert page.locator('#sddSupplierRoleAudit tbody tr').count()==len(original)==103
                page.fill('#sddSupplierRoleAudit input','euralliage')
                assert page.locator('#sddSupplierRoleAudit tbody tr').count() >= 1
                report['checks'].append({'audit_rows':103,'search':'passed'})
                embedded = page.evaluate('() => SDD_MAP_PAYLOAD.sites.map(s=>[s.site_uid,s.roles])')
                assert dict(embedded)=={r['site_uid']:r['roles'] for r in original}
                assert not errors, errors
                report['checks'].append({'modeled_roles_unchanged':True})
            finally:
                browser.close()
        assert hashlib.sha256(HTML.read_bytes()).hexdigest()==report['html_sha256']
        report['status']='passed'
    finally:
        report['browser_errors']=errors
        (evidence/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(evidence/'manifest.json')


if __name__=='__main__':
    main()
