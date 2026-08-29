#!/usr/bin/env python3
"""Refresh aircraft-use cohorts without rerunning SDD or exchange-level LCIA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    SDD_BRIGHTWAY_COUPLING_VERSION,
    aircraft_use_profile,
    build_aircraft_use_trajectory,
    build_usage_calibration_rows,
    clean,
    climate_normalization_factor,
    full_scenario_summary,
    read_csv_gzip,
    read_csv_rows,
    safe_float,
    write_csv,
    write_csv_gzip,
    write_json,
)


SCENARIO_ORDER = (
    "climat_stationnaire",
    "climat_2026_2046_modere",
    "climat_degrade",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
    )
    return parser.parse_args()


def scenario_metadata(
    scenario_id: str,
    existing_summary: dict[str, dict],
) -> dict:
    row = existing_summary.get(scenario_id, {})
    return {
        "scenario_id": scenario_id,
        "label": clean(row.get("label")) or scenario_id,
        "description": clean(row.get("description")),
    }


def update_run_metadata(output_root: Path, row_counts: dict[str, int]) -> None:
    run_dir = output_root / "run"
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("capabilities", {})["aircraft_use_cohorts"] = True
        manifest.setdefault("counts", {})["sdd_aircraft_use_monthly_rows"] = row_counts.get(
            "sdd_aircraft_use_monthly.csv",
            0,
        )
        entrypoints = manifest.setdefault("entrypoints", {})
        for stem in (
            "sdd_aircraft_use_profile",
            "sdd_aircraft_use_components",
            "sdd_aircraft_use_monthly",
            "sdd_aircraft_use_cumulative",
        ):
            entrypoints[stem] = f"../data/{stem}.csv"
        write_json(manifest_path, manifest)

    artifact_path = run_dir / "artifact_index.json"
    if not artifact_path.exists():
        return
    artifacts = json.loads(artifact_path.read_text(encoding="utf-8"))
    existing = {clean(row.get("name")) for row in artifacts}
    definitions = (
        ("sdd_aircraft_use_profile.csv", "sdd_aircraft_use_profile", "use_profile"),
        ("sdd_aircraft_use_components.csv", "sdd_aircraft_use_components", "use_component"),
        ("sdd_aircraft_use_monthly.csv", "sdd_aircraft_use_monthly", "month"),
        ("sdd_aircraft_use_cumulative.csv", "sdd_aircraft_use_cumulative", "month"),
    )
    for name, domain, grain in definitions:
        if name in existing:
            continue
        path = output_root / "data" / name
        rows = read_csv_rows(path)
        artifacts.append(
            {
                "name": name,
                "group": "data",
                "domain": domain,
                "grain": grain,
                "required": True,
                "path": f"data/{name}",
                "format": "csv",
                "exists": path.exists(),
                "row_count": len(rows),
                "columns": list(rows[0]) if rows else [],
            }
        )
    write_json(artifact_path, artifacts)


def main() -> int:
    args = parse_args()
    output_root = args.output_root
    data_dir = output_root / "data"
    summaries_dir = output_root / "summaries"
    dashboard_path = summaries_dir / "general_kpis.json"
    suite_path = summaries_dir / "scenario_suite.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    brightway_model = dashboard.get("brightway_model") or {}

    rebuilt_usage = build_usage_calibration_rows(
        brightway_model.get("reference_use_phase_components", []),
        brightway_model.get("parameters", []),
        brightway_model.get("exact_scenario_lcia", []),
        climate_normalization_factor(
            brightway_model.get("indicator_unit_views", [])
        ),
    )
    brightway_model["usage_calibration"] = rebuilt_usage
    profile = aircraft_use_profile(brightway_model)
    profile_rows = [
        {key: value for key, value in profile.items() if key != "components"}
    ]
    component_rows = profile.get("components", [])

    existing_summary = {
        clean(row.get("scenario_id")): row
        for row in suite.get("summary", [])
    }
    summaries: list[dict] = []
    monthly_suite: list[dict] = []
    moderate_outputs: dict[str, list[dict]] = {}

    for scenario_id in SCENARIO_ORDER:
        scenario_dir = output_root / "scenarios" / scenario_id
        scenario_data = scenario_dir / "data"
        sdd_monthly = read_csv_gzip(
            scenario_data / "sdd_monthly_impacts.csv.gz"
        )
        production_monthly = read_csv_gzip(
            scenario_data / "sdd_brightway_monthly.csv.gz"
        )
        max_month = max(
            (
                int(safe_float(row.get("month_index")))
                for row in production_monthly
            ),
            default=0,
        )
        use_monthly, use_cumulative = build_aircraft_use_trajectory(
            scenario_id=scenario_id,
            sdd_monthly_rows=sdd_monthly,
            production_monthly_rows=production_monthly,
            profile=profile,
            max_month=max_month,
        )
        outputs = {
            "sdd_aircraft_use_profile.csv.gz": profile_rows,
            "sdd_aircraft_use_components.csv.gz": component_rows,
            "sdd_aircraft_use_monthly.csv.gz": use_monthly,
            "sdd_aircraft_use_cumulative.csv.gz": use_cumulative,
        }
        for filename, rows in outputs.items():
            write_csv_gzip(scenario_data / filename, rows)

        sdd_results = {
            "sdd_monthly_impacts": sdd_monthly,
            "sdd_resilience_resources": read_csv_gzip(
                scenario_data / "sdd_resilience_resources.csv.gz"
            ),
        }
        sdd_brightway = {
            "monthly": production_monthly,
            "aircraft_use_monthly": use_monthly,
        }
        summary, monthly = full_scenario_summary(
            scenario_metadata(scenario_id, existing_summary),
            read_csv_gzip(
                scenario_data / "supplier_risk_event_seed.csv.gz"
            ),
            read_csv_gzip(
                scenario_data / "node_operational_state.csv.gz"
            ),
            sdd_results,
            sdd_brightway,
        )
        old_summary = existing_summary.get(scenario_id, {})
        for key in (
            "scenario_order_index",
            "scenario_comparison_status",
            "service_loss_vs_stationary_last60_pp",
        ):
            if key in old_summary:
                summary[key] = old_summary[key]
        summaries.append(summary)
        monthly_suite.extend(monthly)

        manifest_path = scenario_dir / "scenario_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sdd_brightway_coupling_version"] = SDD_BRIGHTWAY_COUPLING_VERSION
        manifest["aircraft_use_accounting_version"] = "cohortes_mensuelles_stelia_v1"
        manifest["scenario_summary"] = summary
        counts = manifest.setdefault("counts", {})
        for filename, rows in outputs.items():
            counts[filename] = len(rows)
        write_json(manifest_path, manifest)

        if scenario_id == "climat_2026_2046_modere":
            moderate_outputs = {
                "aircraft_use_profile": profile_rows,
                "aircraft_use_components": component_rows,
                "aircraft_use_monthly": use_monthly,
                "aircraft_use_cumulative": use_cumulative,
            }

    summaries.sort(
        key=lambda row: SCENARIO_ORDER.index(clean(row.get("scenario_id")))
    )
    suite["summary"] = summaries
    suite["monthly"] = monthly_suite
    write_json(suite_path, suite)

    main_files = {
        "sdd_aircraft_use_profile.csv": moderate_outputs["aircraft_use_profile"],
        "sdd_aircraft_use_components.csv": moderate_outputs["aircraft_use_components"],
        "sdd_aircraft_use_monthly.csv": moderate_outputs["aircraft_use_monthly"],
        "sdd_aircraft_use_cumulative.csv": moderate_outputs["aircraft_use_cumulative"],
    }
    for filename, rows in main_files.items():
        write_csv(data_dir / filename, rows)
    write_csv(data_dir / "brightway_usage_calibration.csv", rebuilt_usage)

    dashboard["brightway_model"] = brightway_model
    dashboard["scenario_resilience"] = {
        "summary": summaries,
        "monthly": monthly_suite,
        "order_ok": suite.get("order_ok"),
    }
    sdd_brightway_dashboard = dashboard.setdefault("sdd_brightway", {})
    sdd_brightway_dashboard.update(moderate_outputs)
    summary_rows = [
        row
        for row in sdd_brightway_dashboard.get("summary", [])
        if clean(row.get("label"))
        not in {
            "Utilisation calendaire de la flotte",
            "Utilisation complete attribuee aux livraisons",
            "Sieges equivalents actifs en fin d'horizon",
        }
    ]
    final_use = moderate_outputs["aircraft_use_monthly"][-1]
    final_cumulative = moderate_outputs["aircraft_use_cumulative"][-1]
    summary_rows.extend(
        [
            {
                "label": "Utilisation calendaire de la flotte",
                "value": final_cumulative["calendar_use_cumulative_kgco2e"],
                "unit": "kgCO2e",
            },
            {
                "label": "Utilisation complete attribuee aux livraisons",
                "value": final_cumulative[
                    "full_lifetime_use_attributed_cumulative_kgco2e"
                ],
                "unit": "kgCO2e",
            },
            {
                "label": "Sieges equivalents actifs en fin d'horizon",
                "value": final_use["active_seat_equivalent"],
                "unit": "seat eq.",
            },
        ]
    )
    sdd_brightway_dashboard["summary"] = summary_rows
    write_json(dashboard_path, dashboard)
    update_run_metadata(
        output_root,
        {name: len(rows) for name, rows in main_files.items()},
    )
    print(
        "Aircraft use refreshed: "
        f"{len(monthly_suite)} scenario-months, "
        f"{profile['full_lifetime_use_kgco2e_per_seat']:.3f} kgCO2e/seat"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
