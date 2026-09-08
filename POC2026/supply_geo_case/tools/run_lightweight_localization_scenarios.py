"""Run exact EF 3.0 LCIA for lightweight-seat sourcing variants."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import bw2data as bd
import yaml

from run_brightway_exact_scenarios import (
    SCENARIOS as SOURCING_SCENARIOS,
    ecoinvent_targets,
    electricity_voltage_key,
    is_foreground_transport_exchange,
    is_market_electricity,
    is_primary_aluminium,
    replace_exchange_input,
)
from run_lightweight_seat_scenario import (
    METHOD_SPECS,
    drop_database,
    kerosene_mass_per_unit,
    one_activity,
    prepare_scenario as prepare_lightweight_scenario,
    scores_for_methods,
)


SCENARIO_DETAILS = {
    "current_export": {
        "label": "Siege allege - supply actuelle",
        "target_scope": "current",
        "localization_status": "current_supply",
    },
    "france_first": {
        "label": "Siege allege - France prioritaire",
        "target_scope": "france",
        "localization_status": "maximum_disponible_modele_non_garanti_100_pct",
    },
    "europe_first": {
        "label": "Siege allege - Europe prioritaire",
        "target_scope": "europe",
        "localization_status": "maximum_disponible_modele_non_garanti_100_pct",
    },
    "fully_globalized": {
        "label": "Siege allege - supply mondialisee",
        "target_scope": "world",
        "localization_status": "stress_test_mondialise",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--source-db", default="OPERA_siege")
    parser.add_argument("--scenario-db-prefix", default="POC2026_OPERA_lightweight_local")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def apply_sourcing_scenario(
    scenario_db: str,
    scenario: dict[str, Any],
    targets: dict[tuple[str, str], Any],
) -> dict[str, int]:
    counts = {
        "electricity_replacements": 0,
        "aluminium_replacements": 0,
        "transport_scaled_exchanges": 0,
    }
    electricity = str(scenario.get("elec_switch_param") or "")
    aluminium = str(scenario.get("al_switch_param") or "")
    transport_factor = float(scenario.get("transport_amount_factor") or 1.0)

    for activity in bd.Database(scenario_db):
        activity_name = str(activity.get("name") or "")
        for exchange in activity.exchanges():
            if exchange.get("type") != "technosphere":
                continue
            input_activity = exchange.input
            if input_activity.get("database") != "ecoinvent-3.10-cutoff":
                continue
            input_name = str(input_activity.get("name") or "")
            input_unit = str(input_activity.get("unit") or "")
            if electricity and is_market_electricity(input_name):
                replace_exchange_input(
                    exchange,
                    targets[(electricity_voltage_key(input_name), electricity)],
                )
                counts["electricity_replacements"] += 1
                continue
            if aluminium and is_primary_aluminium(input_name):
                replace_exchange_input(exchange, targets[("aluminium", aluminium)])
                counts["aluminium_replacements"] += 1
                continue
            if (
                abs(transport_factor - 1.0) > 1e-12
                and is_foreground_transport_exchange(activity_name, input_name, input_unit)
            ):
                exchange["amount"] = float(exchange.get("amount") or 0.0) * transport_factor
                exchange.save()
                counts["transport_scaled_exchanges"] += 1

    bd.Database(scenario_db).process()
    return counts


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
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

    for sourcing in SOURCING_SCENARIOS:
        sourcing_id = str(sourcing["scenario_id"])
        details = SCENARIO_DETAILS[sourcing_id]
        scenario_db = f"{args.scenario_db_prefix}_{sourcing_id}"
        lightweight_counts = prepare_lightweight_scenario(args.source_db, scenario_db, config)
        try:
            sourcing_counts = apply_sourcing_scenario(scenario_db, sourcing, targets)
            scenario_activity = one_activity(scenario_db, "production du siege")
            scenario_scores = scores_for_methods(scenario_activity, METHOD_SPECS)
            for indicator_id, method in METHOD_SPECS:
                rows.append({
                    "scenario_id": f"{config.get('scenario_id')}__{sourcing_id}",
                    "sourcing_scenario_id": sourcing_id,
                    "label": details["label"],
                    "target_scope": details["target_scope"],
                    "localization_status": details["localization_status"],
                    "indicator_id": indicator_id,
                    "method": " | ".join(method),
                    "raw_unit": bd.Method(method).metadata.get("unit", ""),
                    "baseline_production_raw": baseline_scores[indicator_id],
                    "lightweight_production_raw": scenario_scores[indicator_id],
                    "production_delta_raw": scenario_scores[indicator_id] - baseline_scores[indicator_id],
                    "fuel_factor_raw_per_kg": fuel_scores[indicator_id] / fuel_mass,
                    "kerosene_exchange_kg_per_activity_unit": fuel_mass,
                    "elec_switch_param": sourcing.get("elec_switch_param") or "",
                    "al_switch_param": sourcing.get("al_switch_param") or "",
                    "transport_amount_factor": sourcing.get("transport_amount_factor"),
                    "calculation_status": "brightway_exact_lightweight_and_localized_screening",
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
