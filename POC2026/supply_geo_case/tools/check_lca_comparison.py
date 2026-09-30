"""Read-only offline browser checks; only new evidence files are written."""
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
    out = CASE / 'outputs/checks' / ('lca_comparison_' + uuid4().hex)
    out.mkdir(parents=True)
    report = {'status': 'failed', 'html_sha256': hashlib.sha256(HTML.read_bytes()).hexdigest(), 'checks': []}
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            def route(r):
                url = r.request.url
                if url.startswith('file:'):
                    r.continue_()
                elif 'plotly-2.32.0.min.js' in url:
                    r.fulfill(path=str(VENDOR / 'plotly-2.32.0.min.js'))
                elif 'world_110m.json' in url:
                    r.fulfill(path=str(VENDOR / 'world_110m.json'))
                else:
                    r.abort()
            page.route('**/*', route)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(HTML.as_uri(), wait_until='load')
            page.click('[data-sdd-view="aircraft_use"]')
            for metric in ['climate_kgco2e', 'weighted_score_excel']:
                page.select_option('#sddAircraftUseMetric', metric)
                data = page.evaluate("() => document.getElementById('sddAircraftUsePerSeatPlot').data.map(t=>Array.from(t.y))")
                assert 0 < data[1][1] < data[0][1], data
                curves = page.evaluate("() => document.getElementById('sddAircraftUseMassMonthlyPlot').data.map(t=>Array.from(t.y))")
                assert len(curves[0]) > 100 and max(curves[0]) > 0
                ratios = [b/a for a,b in zip(*curves) if a>0]
                assert all(abs(r-data[1][1]/data[0][1])<1e-9 for r in ratios)
                report['checks'].append({'metric':metric,'per_seat':data,'months':len(curves[0])})
            page.screenshot(path=str(out/'usage_desktop.png'))
            for tab, panel in [('lightweight_seat','sddLightweightScoreComparison'),('dashboard','sddLcaScoreComparison')]:
                page.click(f'[data-sdd-view="{tab}"]')
                for phase in ['production','use','production_use']:
                    page.select_option(f'#{panel} select',phase)
                    scores = page.evaluate('(id)=>Array.from(document.getElementById(id+"Plot").data[0].y)',panel)
                    assert len(scores)>=2 and 0<scores[1]<scores[0], scores
                    assert page.locator(f'#{panel} tbody tr').count() >= 32
                    report['checks'].append({'tab':tab,'phase':phase,'scores':scores})
            page.set_viewport_size({'width':390,'height':844})
            page.click('[data-sdd-view="aircraft_use"]')
            page.wait_for_timeout(500)
            page.locator('#sddAircraftUseMassMonthlyPlot').scroll_into_view_if_needed()
            page.screenshot(path=str(out/'usage_mobile.png'))
            assert not errors, errors
            browser.close()
        assert hashlib.sha256(HTML.read_bytes()).hexdigest()==report['html_sha256']
        report['status']='passed'
    finally:
        report['browser_errors']=errors
        (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(out/'manifest.json')


if __name__=='__main__':
    main()
