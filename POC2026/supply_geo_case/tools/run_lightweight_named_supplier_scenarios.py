"""Run EF 3.0 LCIA using transport factors from named supplier assignments."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import bw2data as bd
import yaml

from run_brightway_exact_scenarios import ecoinvent_targets
from run_lightweight_localization_scenarios import apply_sourcing_scenario
from run_lightweight_seat_scenario import (
    METHOD_SPECS,
    drop_database,
    kerosene_mass_per_unit,
    one_activity,
    prepare_scenario as prepare_lightweight_scenario,
    scores_for_methods,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--source-db", default="OPERA_siege")
    parser.add_argument("--scenario-db-prefix", default="POC2026_OPERA_lightweight_named")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--supplier-scenarios-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    supplier_scenarios = read_csv(args.supplier_scenarios_csv)
    if not supplier_scenarios:
        raise RuntimeError("No named supplier scenario supplied")
    bd.projects.set_current(args.project)
    missing_methods = [method for _, method in METHOD_SPECS if method not in bd.methods]
    if missing_methods:
        raise RuntimeError(f"Missing EF methods: {missing_methods}")

    source_activity = one_activity(args.source_db, "production du siege")
    fuel_activity = one_activity(args.source_db, "kerosene, production et combustion, 1tkm eq")
    baseline_scores = scores_for_methods(source_activity, METHOD_SPECS)
    fuel_scores = scores_for_methods(fuel_activity, METHOD_SPECS)
    fuel_mass = kerosene_mass_per_unit(fuel_activity)
    targets = ecoinvent_targets()
    rows: list[dict[str, Any]] = []

    for supplier_scenario in supplier_scenarios:
        sourcing_id = str(supplier_scenario.get("scenario_id") or "")
        if not sourcing_id:
            continue
        scenario_db = f"{args.scenario_db_prefix}_{sourcing_id}"
        sourcing = {
            "elec_switch_param": supplier_scenario.get("electricity_scope") or "",
            "al_switch_param": supplier_scenario.get("aluminium_scope") or "",
            "transport_amount_factor": float(supplier_scenario.get("transport_amount_factor") or 1.0),
        }
        lightweight_counts = prepare_lightweight_scenario(args.source_db, scenario_db, config)
        try:
            sourcing_counts = apply_sourcing_scenario(scenario_db, sourcing, targets)
            scenario_activity = one_activity(scenario_db, "production du siege")
            scenario_scores = scores_for_methods(scenario_activity, METHOD_SPECS)
            for indicator_id, method in METHOD_SPECS:
                rows.append({
                    "scenario_id": f"{config.get('scenario_id')}__{sourcing_id}",
                    "sourcing_scenario_id": sourcing_id,
                    "label": supplier_scenario.get("label"),
                    "target_scope": supplier_scenario.get("target_scope"),
                    "localization_status": "named_supplier_routes_component_qualification_required",
                    "indicator_id": indicator_id,
                    "method": " | ".join(method),
                    "raw_unit": bd.Method(method).metadata.get("unit", ""),
                    "baseline_production_raw": baseline_scores[indicator_id],
                    "lightweight_production_raw": scenario_scores[indicator_id],
                    "production_delta_raw": scenario_scores[indicator_id] - baseline_scores[indicator_id],
                    "fuel_factor_raw_per_kg": fuel_scores[indicator_id] / fuel_mass,
                    "kerosene_exchange_kg_per_activity_unit": fuel_mass,
                    "elec_switch_param": sourcing["elec_switch_param"],
                    "al_switch_param": sourcing["al_switch_param"],
                    "transport_amount_factor": sourcing["transport_amount_factor"],
                    "named_alternative_assignment_count": supplier_scenario.get("named_alternative_assignment_count"),
                    "unique_named_alternative_supplier_count": supplier_scenario.get("unique_named_alternative_supplier_count"),
                    "strict_target_role_mass_pct": supplier_scenario.get("strict_target_role_mass_pct"),
                    "fully_localized_path_mass_pct": supplier_scenario.get("fully_localized_path_mass_pct"),
                    "foreground_mapping_status": "named_sites_and_routes_with_generic_regional_process_markets",
                    "calculation_status": "brightway_exact_named_supplier_scenario_screening",
                    **lightweight_counts,
                    **sourcing_counts,
                })
        finally:
            drop_database(scenario_db)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    write_csv(args.output_csv, run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
