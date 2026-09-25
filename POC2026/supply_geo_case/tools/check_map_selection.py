"""Offline browser regression: compare rendered membership with source CSVs."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "POC2026" / "supply_geo_case"
HTML = CASE / "outputs/maps/supply_geo_base_results_map.html"
VENDOR = ROOT / "etudecas/visualization/maps/vendor"
VIEWS = ["sites", "lanes", "weather", "operations", "impact", "acv", "criticality", "context"]


def rows(name):
    with (CASE / "outputs/data" / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = CASE / "outputs/checks" / f"map_selection_{uuid4().hex}"
    evidence.mkdir(parents=True)
    inputs = [HTML, CASE / "adapter.py", Path(__file__), *[
        CASE / "outputs/data" / name for name in (
            "primary_supply_paths.csv", "primary_supply_lanes.csv", "primary_supply_sites.csv",
            "lightweight_seat_named_supplier_assignments.csv", "lightweight_seat_named_supplier_routes.csv")]]
    hashes = {str(p.relative_to(ROOT)): fingerprint(p) for p in inputs}
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "inputs": hashes, "checks": [], "status": "failed"}
    paths = rows("primary_supply_paths.csv")
    lanes = rows("primary_supply_lanes.csv")
    known_sites = {r["site_uid"] for r in rows("primary_supply_sites.csv")}
    assignments = rows("lightweight_seat_named_supplier_assignments.csv")
    supplier_routes = rows("lightweight_seat_named_supplier_routes.csv")
    system, component = paths[0]["system"], paths[0]["component"]
    selections = [("All", "All"), (system, "All"), (system, component), ("All", component), ("All", "All")]
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 1000})

                def route(request):
                    url = request.request.url
                    if url.startswith("file:"):
                        request.continue_()
                    elif "plotly-2.32.0.min.js" in url:
                        request.fulfill(path=str(VENDOR / "plotly-2.32.0.min.js"), content_type="application/javascript")
                    elif "world_110m.json" in url:
                        request.fulfill(path=str(VENDOR / "world_110m.json"), content_type="application/json")
                    else:
                        request.abort()

                page.route("**/*", route)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(HTML.as_uri(), wait_until="load")
                page.wait_for_selector("#sddViewTabs")

                def select(sys, comp):
                    page.select_option("#systemSel", sys)
                    page.select_option("#componentSel", comp)
                    page.wait_for_timeout(100)

                def expect_membership(sys, comp, view):
                    selected = [r for r in paths if (sys == "All" or r["system"] == sys) and (comp == "All" or r["component"] == comp)]
                    ids = {r["path_id"] for r in selected}
                    expected_sites = {r[f"{role}_site_uid"] for r in selected for role in ("t4", "t3", "t2", "t1", "oem")} & known_sites
                    expected_lanes = {"|".join(r[k] for k in ("from_site_uid", "to_site_uid", "edge")) for r in lanes if r["path_id"] in ids}
                    actual = page.evaluate("""() => ({
                        data: document.getElementById('chart').data.flatMap(t => t.customdata || []).filter(Boolean),
                        active: document.querySelector('[data-sdd-view].active')?.dataset.sddView
                    })""")
                    actual_sites = {v[1] for v in actual["data"] if v[0] == "site"}
                    actual_lanes = {v[1] for v in actual["data"] if v[0] == "lane"}
                    assert actual_sites == expected_sites, (view, sys, comp, actual_sites ^ expected_sites)
                    assert actual_lanes <= expected_lanes, (view, "out-of-scope lanes")
                    assert actual_lanes == expected_lanes, (view, "missing lanes")
                    assert actual["active"] == view, (view, actual["active"])
                    report["checks"].append({"view": view, "system": sys, "component": comp, "sites": len(actual_sites), "lanes": len(actual_lanes)})

                def check_flow_toggle(view):
                    before = page.evaluate("() => document.getElementById('chart').data.filter(t => t.mode === 'lines').reduce((n,t) => n+t.lon.length,0)")
                    assert before > 0, (view, "no visible flows")
                    page.uncheck('#showFlows')
                    assert page.evaluate("() => document.getElementById('chart').data.filter(t => t.mode === 'lines').every(t => !t.lon.length)")
                    assert page.locator(f'[data-sdd-view="{view}"].active').count() == 1
                    page.check('#showFlows')
                    after = page.evaluate("() => document.getElementById('chart').data.filter(t => t.mode === 'lines').reduce((n,t) => n+t.lon.length,0)")
                    assert after == before, (view, "flows not restored")
                    report["checks"].append({"view": view, "flow_toggle": "passed", "flow_points": after})

                for view in VIEWS:
                    page.click(f'[data-sdd-view="{view}"]')
                    for sys, comp in selections:
                        select(sys, comp)
                        expect_membership(sys, comp, view)
                    check_flow_toggle(view)

                page.click('[data-sdd-view="source"]')
                select(system, component)
                source_count = page.evaluate("""() => document.getElementById('chart').data
                    .filter(t => t.mode === 'markers').reduce((n,t) => n + t.lon.length, 0)""")
                expected_source = page.evaluate("""() => DATA.records.filter(r =>
                    r.system === document.getElementById('systemSel').value &&
                    r.component === document.getElementById('componentSel').value)
                    .flatMap(r => Object.values(r.tiers).flat()).filter(s => getLatLon(s)).length""")
                assert source_count == expected_source and source_count > 0
                report["checks"].append({"view": "source", "markers": source_count})
                check_flow_toggle("source")

                page.click('[data-sdd-view="supplier_alternatives"]')
                for scenario in ("france_named_alternatives", "europe_named_alternatives"):
                    page.select_option("#sddAlternativeScenarioSelect", scenario)
                    for sys, comp in selections:
                        select(sys, comp)
                        selected = [r for r in assignments if r["scenario_id"] == scenario and
                                    (sys == "All" or r["system"] == sys) and (comp == "All" or r["component"] == comp)]
                        unique = {(r["selected_supplier"], r["selected_lat"], r["selected_lon"], r["role"]) for r in selected}
                        expected = Counter((round(float(r[2]), 6), round(float(r[1]), 6)) for r in unique)
                        actual = page.evaluate("""() => document.getElementById('chart').data
                            .filter(t => t.mode === 'markers').flatMap(t => t.lon.map((lon,i) => [lon,t.lat[i]]))""")
                        assert Counter(tuple(round(v, 6) for v in xy) for xy in actual) == expected
                        path_ids = {r["path_id"] for r in selected}
                        expected_routes = [r for r in supplier_routes if r["scenario_id"] == scenario and r["path_id"] in path_ids]
                        expected_segments = Counter(tuple(round(float(r[k]), 6) for k in ("from_lon", "from_lat", "to_lon", "to_lat")) for r in expected_routes)
                        segments = page.evaluate("""() => document.getElementById('chart').data
                            .filter(t => t.mode === 'lines').flatMap(t => {
                                const segments = [];
                                for (let i=0; i<t.lon.length; i+=3) segments.push([t.lon[i],t.lat[i],t.lon[i+1],t.lat[i+1]]);
                                return segments;
                            })""")
                        assert Counter(tuple(round(v, 6) for v in segment) for segment in segments) == expected_segments
                        assert page.locator('[data-sdd-view="supplier_alternatives"].active').count() == 1
                        report["checks"].append({"view": "supplier_alternatives", "scenario": scenario, "system": sys, "component": comp, "nodes": len(actual), "routes": len(segments)})
                    check_flow_toggle("supplier_alternatives")

                select("All", "All")
                page.click('[data-sdd-view="cascades"]')
                page.click('#sddCascadeShowMap')
                for sys, comp in selections:
                    select(sys, comp)
                    expect_membership(sys, comp, "cascades")
                check_flow_toggle("cascades")

                # Chronology is checked against the cached rows, not their previous order.
                select("All", "All")
                def assert_months(values):
                    positions = [float(v) if str(v).strip() and float(v) > 0 else float('inf') for v in values]
                    assert positions == sorted(positions), values

                site_uid = page.evaluate("""() => Object.entries(SDD_MAP_PAYLOAD.click_details.sites)
                    .find(([,d]) => d.event_rows.length > 1 && d.inventory_rows.length > 1 && d.exchange_rows.length > 1)[0]""")
                for view in ("context", "sites", "operations"):
                    page.click(f'[data-sdd-view="{view}"]')
                    page.wait_for_timeout(100)
                    page.evaluate("""uid => document.getElementById('chart').emit('plotly_click',
                        {points: [{customdata: ['site', uid]}]})""", site_uid)
                    tables = page.evaluate("""() => [...document.querySelectorAll('#sddClickPanelBody table')]
                        .filter(t => t.querySelector('th')?.textContent === 'Mois')
                        .map(t => [...t.querySelectorAll('tbody tr')].map(r => [...r.cells].map(c => c.textContent)))""")
                    assert len(tables) == 3
                    expected = page.evaluate("""uid => {
                        const d = SDD_MAP_PAYLOAD.click_details.sites[uid];
                        return [
                            [d.event_rows, ['month_index','role','cause','decision','service_level_pct','backlog_kg','surimpact_kgco2e']],
                            [d.inventory_rows, ['month_index','role','mechanism','effect','delta_kgco2e','confidence']],
                            [d.exchange_rows, ['month_index','mechanism','exchange_category','exchange_name','status','delta_kgco2e']]
                        ].map(([rows,keys]) => rows.map(r => keys.map(k => String(r[k] ?? ''))));
                    }""", site_uid)
                    for actual_rows, expected_rows in zip(tables, expected):
                        assert Counter(map(tuple, actual_rows)) == Counter(map(tuple, expected_rows)), "Chronology changed row contents"
                        assert_months([r[0] for r in actual_rows])
                    page.click('#sddClickPanelClose')
                    report["checks"].append({"view": view, "chronological_detail_tables": 3, "rows_preserved": True})

                # Deliberately unordered string months, ties and an undated row.
                snapshot = page.evaluate("""uid => {
                    const d = SDD_MAP_PAYLOAD.click_details.sites[uid];
                    const saved = d.event_rows;
                    d.event_rows = ['10','2','2',null].map((m,i) => ({month_index:m,role:'test-'+i}));
                    return saved;
                }""", site_uid)
                page.evaluate("uid => document.getElementById('chart').emit('plotly_click',{points:[{customdata:['site',uid]}]})", site_uid)
                ordered = page.evaluate("""() => [...document.querySelectorAll('#sddClickPanelBody table')]
                    .find(t => t.querySelector('th')?.textContent === 'Mois')
                    .querySelector('tbody').textContent""")
                assert ordered.index('test-1') < ordered.index('test-2') < ordered.index('test-0') < ordered.index('test-3')
                page.evaluate("([uid,saved]) => {SDD_MAP_PAYLOAD.click_details.sites[uid].event_rows = saved;}", [site_uid, snapshot])
                page.click('#sddClickPanelClose')
                report["checks"].append({"chronology_numeric_stable_undated_last": "passed"})

                page.click('[data-sdd-view="dashboard"]')
                for kind in ("echanges", "inventaire", "evenements"):
                    page.select_option('#ledgerKindFilter', kind)
                    months = page.locator('#baseMapKpiLedgerTable tbody tr td:first-child').all_text_contents()
                    assert_months(months)
                    report["checks"].append({"dashboard_chronology": kind, "rows": len(months)})
                page.click('[data-sdd-view="cascades"]')
                cascade_ids = page.locator('#sddCascadeList [data-cascade-id]').evaluate_all('(els) => els.map(e => e.dataset.cascadeId)')
                months = page.evaluate("ids => ids.map(id => SDD_MAP_PAYLOAD.risk_cascades.cascades.find(r => r.cascade_id === id).month_index)", cascade_ids)
                assert_months(months)
                timeline = page.locator('.sdd-cascade-timeline tbody tr td:first-child').all_text_contents()
                assert_months([v.removeprefix('M') for v in timeline])
                report["checks"].append({"cascade_chronology": "passed", "rows": len(months)})
                page.click('#sddCascadeShowMap')

                # Empty selection must clear a previously populated cascade map.
                page.evaluate("""() => {
                    const el = document.getElementById('systemSel');
                    el.add(new Option('No matching system', '__empty__'));
                    el.value = '__empty__'; el.dispatchEvent(new Event('change', {bubbles: true}));
                }""")
                assert page.evaluate("() => document.getElementById('chart').data.every(t => !t.lon.length)")
                page.click('[data-sdd-view="supplier_alternatives"]')
                assert page.evaluate("() => document.getElementById('chart').data.every(t => !t.lon.length)")
                report["checks"].append({"view": "empty_cascade_and_alternatives", "nodes": 0})

                select(system, component)
                page.screenshot(path=str(evidence / "filtered_alternatives.png"))
                page.set_viewport_size({"width": 390, "height": 844})
                page.click('[data-sdd-view="sites"]')
                expect_membership(system, component, "sites")
                page.screenshot(path=str(evidence / "filtered_sites_mobile.png"))
                assert not errors, errors
            finally:
                browser.close()
        assert hashes == {str(p.relative_to(ROOT)): fingerprint(p) for p in inputs}, "Inputs changed during verification"
        report["status"] = "passed"
    finally:
        report["browser_errors"] = errors
        (evidence / "manifest.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": report["status"], "checks": len(report["checks"]), "manifest": str(evidence / "manifest.json")}))


if __name__ == "__main__":
    main()
