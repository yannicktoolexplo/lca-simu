"""Exercise a standalone map in Chromium offline and keep a review report.

Requires Playwright and its Chromium browser, not needed by the simulator.
This checks selected UI journeys, not the scientific validity of the model.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path


def review_source_comparison(page, output: Path) -> dict:
    """Check an optional source panel through its actual controls and displayed data."""
    page.locator('#sourceComparisonOpenBtn').click()
    frame = page.frame_locator('#sourceComparisonFrame')
    root = frame.locator('#sourceComparisonRoot')
    root.wait_for(state='visible', timeout=60000)
    tabs = frame.locator('[role=tab][data-tab]').evaluate_all('xs => xs.map(x=>x.dataset.tab)')
    empirical_rows_checked = 0
    for tab in tabs:
        frame.locator(f'[data-tab="{tab}"]').click()
        if not frame.locator('#sourceComparisonPanel').inner_text().strip():
            raise ValueError(f'Empty source comparison tab: {tab}')
        if tab == 'flows' and frame.locator('#sourceComparisonEmpiricalDelivery').count():
            frame.locator('#sourceComparisonEmpiricalDelivery summary').click()
            empirical_rows_checked = frame.locator('#sourceComparisonEmpiricalOrders tbody tr').count()
            if empirical_rows_checked < 1 or 'historique encore insuffisant' not in frame.locator('#sourceComparisonEmpiricalOrders').inner_text():
                raise ValueError('Expected empirical delivery fallback explanation is missing')
    details = {'tabs': tabs, 'empirical_order_rows_checked': empirical_rows_checked}
    if 'gaillac' in tabs:
        frame.locator('[data-tab="gaillac"]').click()
        table = frame.locator('#sourceComparisonSiteStocks')
        ids = table.locator('tbody tr td:first-child').all_text_contents()
        if set(ids) != {'001893', '002612', '021081', '693055', '773474'}:
            raise ValueError('Gaillac stock view does not contain the five source articles')
        frame.locator('#sourceComparisonSitePhoto').select_option('0')
        opening_rows = table.locator('tbody tr').evaluate_all('xs=>xs.map(x=>[...x.cells].map(c=>c.textContent))')
        if any(any(value != '—' for value in row[5:9]) for row in opening_rows):
            raise ValueError('Opening photo was compared to a fabricated previous-day stock')
        frame.locator('#sourceComparisonSitePhoto').select_option('362')
        page.screenshot(path=str(output / 'gaillac-stocks.png'))
        details['gaillac_rows'] = table.locator('tbody tr').count()
    frame.locator('[data-tab="stocks"]').click()
    if frame.locator('#sourceComparisonPair option[value="039668/1810"]').count():
        frame.locator('#sourceComparisonPair').select_option('039668/1810')
    frame.locator('#sourceComparisonReset').click()
    if frame.locator('#sourceComparisonBasis option[value="physical"]').count():
        frame.locator('#sourceComparisonBasis').select_option('physical')
    state = root.evaluate('()=>SOURCE_COMPARISON_VIEW.getState()')
    raw = frame.locator('#sourceComparisonPayload').evaluate('el=>{const d=JSON.parse(el.textContent);return d.pairs[SOURCE_COMPARISON_VIEW.getState().pair]}')
    count = 0
    for run in state['runs']:
        actual = root.evaluate('(el,key)=>SOURCE_COMPARISON_VIEW.getComparisonRows(key)', run)
        column = {'physical': 5, 'available': 1, 'onsite': 3, 'held': 4, 'reserved': 2}.get(state['basis'], 5)
        stocks = {r[0]: r[column] for r in raw['simulations'][run]['stock']}
        expected = [(d, q, stocks[d - 1]) for d, q, _ in raw['observed']
                    if d > 0 and isinstance(stocks.get(d - 1), (int, float))]
        if len(actual) != len(expected):
            raise ValueError('Rendered photo comparison count differs from the payload')
        for row, (day, observed, simulated) in zip(actual, expected):
            if row['day'] != day or abs(row['observed'] - observed) > 1e-6 or abs(row['simulated'] - simulated) > 1e-6:
                raise ValueError('Rendered photo comparison values differ from the payload')
            count += 1
    frame.locator('#sourceComparisonZoomIn').click()
    zoomed = root.evaluate('()=>SOURCE_COMPARISON_VIEW.getState()')
    if zoomed['end'] - zoomed['start'] >= state['end'] - state['start']:
        raise ValueError('Comparison zoom did not reduce the time window')
    frame.locator('#sourceComparisonReset').click()
    page.screenshot(path=str(output / 'source-comparison-stocks.png'))
    page.locator('#sourceComparisonCloseBtn').click()
    page.locator('#sourceComparisonModal').wait_for(state='hidden')
    return {'name': 'source_comparison', 'ok': True, 'photo_values_checked': count,
            'pair': state['pair'], **details,
            'scope': 'Tabs, Gaillac dates, selected stock photo values and zoom; no claim of exhaustive interaction coverage.'}


def review_map(html: Path, output: Path) -> dict:
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": "etudecas.map_browser_review.v1", "html": str(html.resolve()),
              "html_sha256": hashlib.sha256(html.read_bytes()).hexdigest(),
              "offline": True, "viewport": {"width": 1440, "height": 960},
              "javascript_errors": [], "checks": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(offline=True, accept_downloads=True, viewport=report["viewport"])
            page.on("pageerror", lambda error: report["javascript_errors"].append(str(error)))
            page.goto(html.resolve().as_uri(), wait_until="load", timeout=60000)
            page.wait_for_function(
                'typeof DATA !== "undefined" && Object.keys(DATA).length > 0 && '
                'document.querySelectorAll(".js-plotly-plot").length > 0', timeout=60000)
            report["title"] = page.title()
            report["payload"] = page.evaluate('''() => ({
                horizon_days: DATA.timeline_horizon_days,
                node_ids: (DATA.nodes || []).map(n => n.id),
                edge_ids: (DATA.edges || []).map(e => e.id),
                lot_count: Object.keys(DATA.lot_trace?.lots || {}).length,
                run_contract: DATA.run_contract,
                generic_keys: Object.keys(DATA.generic || {}),
                comparison: (DATA.scenario_comparison?.scenarios || []).map(s => ({
                    id:s.id, label:s.label, is_reference:s.is_reference, horizon_days:s.horizon_days,
                    kpis:s.kpis})),
                uncertainty_available: DATA.montecarlo_uncertainty?.available,
                risk_available: DATA.simulated_risk_global_diagnostic?.available
            })''')
            report["checks"].append({"name": "offline_map_loaded", "ok": True})
            close = page.locator("#lotTracePanelCloseBtn")
            if close.is_visible():
                close.click()
            page.screenshot(path=str(output / "nominal.png"))
            journeys = [
                ("material_balance", "modeOps", "materialTableBtn", "materialTableModal", "materialTableCloseBtn"),
                ("kpi_tree", "modeOps", "kpiTreeBtn", "kpiTreeModal", "kpiTreeCloseBtn"),
                ("lot_trace", "modeOps", "lotTraceOpenBtn", "lotTraceModal", "lotTraceModalCloseBtn"),
                ("scenario_comparison", "modeSimulatedRisk", "scenarioComparisonBtn", "scenarioComparisonModal", "scenarioComparisonCloseBtn"),
                ("injected_risk", "modeSimulatedRisk", "simulatedRiskGlobalBtn", "simulatedRiskGlobalModal", "simulatedRiskGlobalCloseBtn"),
                ("uncertainty", "modeUncertainty", "monteCarloBtn", "monteCarloModal", "monteCarloCloseBtn"),
            ]
            for name, mode, button, modal, close_button in journeys:
                check = {"name": name, "ok": False}
                try:
                    page.locator(f"#{mode}").click(timeout=10000)
                    page.locator(f"#{button}").click(timeout=10000)
                    panel = page.locator(f"#{modal}")
                    panel.wait_for(state="visible", timeout=15000)
                    text = panel.inner_text()
                    if not text.strip():
                        raise ValueError("Empty panel")
                    if name == "scenario_comparison":
                        ranking = page.evaluate('''() => {
                            const selected = new Set(Array.from(document.querySelectorAll('.scenarioComparisonChk:checked')).map(c => c.value));
                            const rows = DATA.scenario_comparison.scenarios.filter(s => selected.has(s.id));
                            const winner = rows.reduce((a,b) =>
                                Number(b.kpis.observed_impact_score) > Number(a.kpis.observed_impact_score) ? b : a);
                            return {label:winner.label, score:winner.kpis.observed_impact_score,
                                expected:'Score descriptif ' + Number(winner.kpis.observed_impact_score).toLocaleString('fr-FR', {minimumFractionDigits:1, maximumFractionDigits:1})};
                        }''')
                        if ranking["expected"] not in text or ranking["label"] not in text:
                            raise ValueError("Displayed impact score differs from observed ranking")
                        check["observed_ranking"] = ranking
                    check.update(ok=True, text_excerpt=text[:1600], bounds=panel.bounding_box())
                    page.screenshot(path=str(output / f"{name}.png"))
                    page.locator(f"#{close_button}").click()
                    panel.wait_for(state="hidden", timeout=5000)
                except Exception as exc:
                    check.update(ok=False, error=str(exc))
                    page.screenshot(path=str(output / f"{name}-failure.png"))
                    panel = page.locator(f"#{close_button}")
                    if panel.is_visible():
                        panel.click(force=True)
                report["checks"].append(check)
            page.locator("#modeOps").click()
            slider = page.locator("#yearEnd")
            minimum = float(slider.get_attribute("min") or "0")
            maximum = float(slider.get_attribute("max") or "100")
            slider.focus()
            slider.press("Home")
            page.wait_for_function('document.querySelector(".js-plotly-plot") !== null')
            observed_minimum = float(slider.input_value())
            slider.press("End")
            observed_maximum = float(slider.input_value())
            report["checks"].append({
                "name": "timeline_control",
                "ok": observed_minimum == minimum and observed_maximum == maximum,
                "minimum": minimum, "maximum": maximum,
                "observed_minimum": observed_minimum, "observed_maximum": observed_maximum,
                "scope": "Annual range endpoints; a single-year horizon has one position.",
            })
            page.screenshot(path=str(output / "final-nominal.png"))
            if page.locator('#sourceComparisonOpenBtn').count():
                report['checks'].append(review_source_comparison(page, output))
            decision_link = page.locator("#decisionSupportLink")
            if decision_link.count():
                dashboard = {"name": "decision_dashboard", "ok": False}
                if decision_link.get_attribute("data-portable-file") == "diagnostic":
                    with page.expect_popup() as opened:
                        decision_link.click()
                    diagnostic = opened.value
                    diagnostic.on("pageerror", lambda error: report["javascript_errors"].append(str(error)))
                    try:
                        diagnostic.locator("h1").wait_for(state="visible", timeout=60000)
                        headings = diagnostic.locator("h2").all_text_contents()
                        script = diagnostic.locator('script[data-portable-support="1"]').text_content()
                        marker = "const files = "
                        attachments = json.JSONDecoder().raw_decode(script[script.index(marker) + len(marker):])[0]
                        expected_names = ("decision-report.json", "constraint-evidence.csv", "lot-causal-evidence.csv", "delivery.json")
                        downloads = []
                        for name in expected_names:
                            entry = attachments[name]
                            expected = gzip.decompress(base64.b64decode(entry["gzip"], validate=True))
                            with diagnostic.expect_download() as downloaded:
                                diagnostic.locator(f'[data-portable-file="{name}"]').click()
                            download = downloaded.value
                            actual = Path(download.path()).read_bytes()
                            digest = hashlib.sha256(actual).hexdigest()
                            downloads.append({"name": name, "bytes": len(actual), "sha256": digest,
                                              "ok": actual == expected and len(actual) == entry["bytes"]
                                              and digest == entry["sha256"] and download.suggested_filename == name})
                        dashboard.update(ok=len(headings) == 5 and diagnostic.url.startswith("blob:")
                                         and set(attachments) == set(expected_names) and all(row["ok"] for row in downloads),
                                         format="portable", headings=headings, downloads=downloads,
                                         scope="Offline diagnostic popup and exact embedded download bytes; CSV/model reconciliation is separate.")
                        diagnostic.screenshot(path=str(output / "decision-dashboard.png"), full_page=True)
                    finally:
                        diagnostic.close()
                else:
                    decision_link.click()
                    page.wait_for_load_state("load")
                    page.locator("h1").wait_for(state="visible")
                    headings = page.locator("h2").all_text_contents()
                    from urllib.parse import urlsplit
                    from urllib.request import url2pathname
                    local_links = page.locator("a").evaluate_all("links => links.map(a => a.href)")
                    missing = [url for url in local_links if urlsplit(url).scheme != "file"
                               or not Path(url2pathname(urlsplit(url).path)).exists()]
                    dashboard.update(ok=len(headings) == 5 and not missing,
                                     format="multipage", headings=headings, missing_links=missing)
                    page.screenshot(path=str(output / "decision-dashboard.png"), full_page=True)
                report["checks"].append(dashboard)
        except Exception as exc:
            report["checks"].append({"name": "browser_execution", "ok": False, "error": str(exc)})
        finally:
            browser.close()
    report["ok"] = bool(report["checks"]) and all(c["ok"] for c in report["checks"]) and not report["javascript_errors"]
    (output / "browser-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report = review_map(args.html, args.output_dir)
    print(json.dumps({"ok": report["ok"], "checks": [{"name": c["name"], "ok": c["ok"]} for c in report["checks"]]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
