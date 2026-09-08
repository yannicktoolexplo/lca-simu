#!/usr/bin/env python3
"""Refresh Excel/Brightway comparison outputs without rerunning the SDD engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    artifact_record,
    build_excel_original_indicator_comparison,
    build_excel_runtime_comparison,
    build_indicator_unit_views,
    climate_normalization_factor,
    indicator_summary_rows,
    load_brightway_component_impacts,
    load_stelia_raw_climate_reference,
    read_csv_rows,
    write_csv,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def main() -> int:
    args = parse_args()
    output_root = args.output_root.resolve(strict=False)
    data = output_root / "data"
    summaries = output_root / "summaries"
    run = output_root / "run"

    reference_pe = read_csv_rows(data / "brightway_reference_person_equivalent_results.csv")
    reference_weighted = read_csv_rows(data / "brightway_reference_weighted_results.csv")
    component_impacts, _ = load_brightway_component_impacts(
        REPO_ROOT / "bw_tristan" / "STELIALCASEATS.xlsx"
    )
    indicator_summary = indicator_summary_rows(component_impacts)
    indicator_views = build_indicator_unit_views(indicator_summary)
    write_csv(data / "brightway_component_impacts.csv", component_impacts)
    write_csv(data / "brightway_indicator_summary.csv", indicator_summary)
    write_csv(data / "brightway_indicator_unit_views.csv", indicator_views)
    exact_lcia = read_csv_rows(data / "brightway_exact_scenario_lcia.csv")
    normalization_factor = climate_normalization_factor(indicator_views)

    climate_comparison = build_excel_runtime_comparison(
        reference_pe,
        exact_lcia,
        normalization_factor,
        load_stelia_raw_climate_reference(
            REPO_ROOT / "bw_tristan" / "STELIA LCA SEATS v14022022v2.xlsx"
        ),
    )
    indicator_comparison = build_excel_original_indicator_comparison(
        reference_pe,
        reference_weighted,
        indicator_views,
    )
    climate_path = data / "brightway_excel_runtime_comparison.csv"
    indicator_path = data / "brightway_excel_original_indicator_comparison.csv"
    write_csv(climate_path, climate_comparison)
    write_csv(indicator_path, indicator_comparison)

    dashboard_path = summaries / "general_kpis.json"
    dashboard = load_json(dashboard_path)
    brightway_dashboard = dashboard.setdefault("brightway_model", {})
    brightway_dashboard["component_impacts"] = component_impacts
    brightway_dashboard["indicator_summary"] = indicator_summary
    brightway_dashboard["indicator_unit_views"] = indicator_views
    brightway_dashboard["excel_runtime_comparison"] = climate_comparison
    brightway_dashboard["excel_original_indicator_comparison"] = indicator_comparison
    brightway_counts = brightway_dashboard.setdefault("counts", {})
    brightway_counts["component_impacts"] = len(component_impacts)
    brightway_counts["indicator_summary"] = len(indicator_summary)
    brightway_counts["indicator_unit_views"] = len(indicator_views)
    brightway_counts["excel_runtime_comparison"] = len(climate_comparison)
    brightway_counts["excel_original_indicator_comparison"] = len(indicator_comparison)
    write_json(dashboard_path, dashboard)

    brightway_summary_path = summaries / "brightway_model_summary.json"
    brightway_summary = load_json(brightway_summary_path)
    brightway_summary["component_impacts"] = component_impacts
    brightway_summary["indicator_summary"] = indicator_summary
    brightway_summary["indicator_unit_views"] = indicator_views
    brightway_summary["excel_runtime_comparison"] = climate_comparison
    brightway_summary["excel_original_indicator_comparison"] = indicator_comparison
    summary_counts = brightway_summary.setdefault("counts", {})
    summary_counts["excel_runtime_comparison"] = len(climate_comparison)
    summary_counts["excel_original_indicator_comparison"] = len(indicator_comparison)
    write_json(brightway_summary_path, brightway_summary)

    primary_summary_path = summaries / "primary_supply_case_summary.json"
    primary_summary = load_json(primary_summary_path)
    primary_counts = primary_summary.setdefault("counts", {})
    primary_counts["brightway_excel_runtime_comparison"] = len(climate_comparison)
    primary_counts["brightway_excel_original_indicator_comparison"] = len(indicator_comparison)
    write_json(primary_summary_path, primary_summary)

    manifest_path = run / "run_manifest.json"
    manifest = load_json(manifest_path)
    manifest_counts = manifest.setdefault("counts", {})
    manifest_counts["brightway_excel_runtime_comparison"] = len(climate_comparison)
    manifest_counts["brightway_excel_original_indicator_comparison"] = len(indicator_comparison)
    manifest.setdefault("capabilities", {})["brightway_excel_original_indicator_comparison"] = bool(indicator_comparison)
    manifest.setdefault("entrypoints", {})["brightway_excel_original_indicator_comparison"] = "../data/brightway_excel_original_indicator_comparison.csv"
    write_json(manifest_path, manifest)

    artifact_index_path = run / "artifact_index.json"
    artifacts = json.loads(artifact_index_path.read_text(encoding="utf-8")) if artifact_index_path.exists() else []
    artifacts = [
        row
        for row in artifacts
        if row.get("domain") != "brightway_excel_original_indicator_comparison"
    ]
    artifacts.append(
        artifact_record(
            output_root,
            indicator_path,
            group="data",
            domain="brightway_excel_original_indicator_comparison",
            grain="indicator_reference_comparison",
            required=True,
        )
    )
    write_json(artifact_index_path, artifacts)

    print(
        f"Excel comparisons refreshed: {len(climate_comparison)} climate scopes, "
        f"{len(indicator_comparison)} EF indicators"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
