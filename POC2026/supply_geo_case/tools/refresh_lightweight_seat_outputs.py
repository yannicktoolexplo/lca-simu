"""Refresh the lightweight-seat artifacts and tab without rerunning SDD."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (  # noqa: E402
    CASE_ROOT,
    LIGHTWEIGHT_SEAT_CONFIG,
    BW_TRISTAN_ROOT,
    brightway_runtime_status,
    read_csv_rows,
    write_csv,
    write_enriched_base_map_html,
    write_json,
)
from POC2026.supply_geo_case.lightweight_seat import (  # noqa: E402
    build_lightweight_scenario,
    is_exact_brightway_rows,
    load_scenario_config,
)
from POC2026.supply_geo_case.supplier_alternatives import build_supplier_alternative_scenarios  # noqa: E402


def embedded_json(html: str, variable: str, next_variable: str) -> dict:
    start_marker = f"const {variable} = "
    end_marker = f";\nconst {next_variable} = "
    start = html.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing embedded variable: {variable}")
    start += len(start_marker)
    end = html.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing embedded variable boundary: {next_variable}")
    return json.loads(html[start:end])


def main() -> int:
    output_root = CASE_ROOT / "outputs"
    data = output_root / "data"
    summaries = output_root / "summaries"
    maps = output_root / "maps"
    map_path = maps / "supply_geo_base_results_map.html"
    dashboard_path = summaries / "general_kpis.json"
    if not map_path.exists() or not dashboard_path.exists():
        raise RuntimeError("Existing base map and general KPI payload are required")

    units = read_csv_rows(data / "brightway_indicator_unit_views.csv")
    for row in units:
        row["include_in_person_equivalent"] = str(row.get("include_in_person_equivalent", "")).lower() == "true"
    lightweight_config = load_scenario_config(LIGHTWEIGHT_SEAT_CONFIG)
    supplier_alternatives = build_supplier_alternative_scenarios(
        source_json_path=REPO_ROOT / "supply_geo" / "analysis" / "output8_GEO_normalized_simulation_ready_researched.json",
        path_rows=read_csv_rows(data / "primary_supply_paths.csv"),
        site_rows=read_csv_rows(data / "primary_supply_sites.csv"),
        context_rows=read_csv_rows(data / "supplier_context_summary.csv"),
        target_mass_kg=float(lightweight_config.get("target_mass_kg") or 0.0),
    )
    result = build_lightweight_scenario(
        config_path=LIGHTWEIGHT_SEAT_CONFIG,
        masterboard_path=BW_TRISTAN_ROOT / "STELIA Masterboard LCA SEATS 6.0.xlsx",
        runtime=brightway_runtime_status(),
        runner_path=CASE_ROOT / "tools" / "run_lightweight_seat_scenario.py",
        impact_rows=read_csv_rows(data / "brightway_component_impacts.csv"),
        indicator_unit_views=units,
        reference_person_equivalent_results=read_csv_rows(data / "brightway_reference_person_equivalent_results.csv"),
        reference_weighting_factors=read_csv_rows(data / "brightway_reference_weighting_factors.csv"),
        localization_runner_path=CASE_ROOT / "tools" / "run_lightweight_localization_scenarios.py",
        regional_scenarios=read_csv_rows(data / "brightway_parametric_regional_scenarios.csv"),
        supplier_alternative_payload=supplier_alternatives,
        supplier_runner_path=CASE_ROOT / "tools" / "run_lightweight_named_supplier_scenarios.py",
    )

    write_csv(data / "lightweight_seat_mass_budget.csv", result.get("mass_budget", []))
    write_csv(data / "lightweight_seat_indicator_results.csv", result.get("indicator_results", []))
    write_csv(data / "lightweight_seat_certification_gates.csv", result.get("certification_gates", []))
    exact_rows = result.get("exact_runtime_rows", [])
    if is_exact_brightway_rows(exact_rows):
        write_csv(data / "lightweight_seat_exact_lcia.csv", exact_rows)
    localization_exact_rows = result.get("localization_exact_runtime_rows", [])
    if localization_exact_rows:
        write_csv(data / "lightweight_seat_localization_exact_lcia.csv", localization_exact_rows)
    write_csv(data / "lightweight_seat_localization_indicators.csv", result.get("localization_indicator_results", []))
    write_csv(data / "lightweight_seat_localization_scenarios.csv", result.get("localization_scenarios", []))
    named_exact_rows = result.get("named_supplier_exact_runtime_rows", [])
    if named_exact_rows:
        write_csv(data / "lightweight_seat_named_supplier_exact_lcia.csv", named_exact_rows)
    write_csv(data / "lightweight_seat_named_supplier_indicators.csv", result.get("named_supplier_indicator_results", []))
    write_csv(data / "lightweight_seat_named_supplier_scenarios.csv", result.get("named_supplier_scenarios", []))
    write_csv(data / "lightweight_seat_named_supplier_assignments.csv", result.get("named_supplier_assignments", []))
    write_csv(data / "lightweight_seat_named_supplier_routes.csv", result.get("named_supplier_routes", []))
    write_csv(data / "lightweight_seat_named_supplier_candidate_audit.csv", result.get("named_supplier_candidate_audit", []))
    write_csv(data / "lightweight_seat_named_supplier_loads.csv", result.get("named_supplier_loads", []))
    write_json(summaries / "lightweight_seat_scenario.json", result)

    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    dashboard.setdefault("brightway_model", {})["lightweight_seat"] = result
    write_json(dashboard_path, dashboard)

    old_html = map_path.read_text(encoding="utf-8")
    map_payload = embedded_json(old_html, "SDD_MAP_PAYLOAD", "BASE_DASHBOARD_PAYLOAD")
    source_map = REPO_ROOT / "supply_geo" / "analysis" / "maps" / "output8_GEO_simulation_ready_researched_map.html"
    write_enriched_base_map_html(
        map_path,
        source_map=source_map,
        site_rows=[],
        sdd_results={},
        dashboard_payload=dashboard,
        prebuilt_map_payload=map_payload,
    )
    print(
        "Lightweight seat refreshed: "
        f"{result['summary']['target_mass_kg']:.3f} kg, "
        f"{result['summary']['indicator_count']} EF indicators, "
        f"{map_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
