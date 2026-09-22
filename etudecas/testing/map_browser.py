"""Exercise a standalone map in Chromium offline and keep a review report.

Requires Playwright and its Chromium browser, not needed by the simulator.
This checks selected UI journeys, not the scientific validity of the model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


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
            page = browser.new_page(offline=True, viewport=report["viewport"])
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
            original = slider.input_value()
            slider.focus()
            slider.press("Home")
            page.wait_for_function('document.querySelector(".js-plotly-plot") !== null')
            report["checks"].append({"name": "timeline_control", "ok": slider.input_value() != original})
            slider.press("End")
            page.screenshot(path=str(output / "final-nominal.png"))
            decision_link = page.locator("#decisionSupportLink")
            if decision_link.count():
                decision_link.click()
                page.wait_for_load_state("load")
                page.locator("h1").wait_for(state="visible")
                dashboard = {"name": "decision_dashboard", "ok": False}
                headings = page.locator("h2").all_text_contents()
                from urllib.parse import urlsplit
                from urllib.request import url2pathname
                local_links = page.locator("a").evaluate_all("links => links.map(a => a.href)")
                missing = [url for url in local_links if urlsplit(url).scheme != "file"
                           or not Path(url2pathname(urlsplit(url).path)).exists()]
                dashboard.update(ok=len(headings) == 5 and not missing,
                                 headings=headings, missing_links=missing)
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
