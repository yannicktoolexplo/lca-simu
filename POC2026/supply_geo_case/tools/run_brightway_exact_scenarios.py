"""Run exact Brightway LCIA calculations for POC2026 sourcing scenarios."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import bw2calc as bc
import bw2data as bd


METHOD_CLIMATE_EF30 = (
    "ecoinvent-3.10",
    "EF v3.0",
    "climate change",
    "global warming potential (GWP100)",
)

SCENARIOS = (
    {
        "scenario_id": "current_export",
        "label": "Baseline Brightway OPERA",
        "elec_switch_param": "",
        "al_switch_param": "",
        "transport_amount_factor": 1.0,
    },
    {
        "scenario_id": "france_first",
        "label": "100% francais si disponible",
        "elec_switch_param": "fr",
        "al_switch_param": "eu",
        "transport_amount_factor": 0.45,
    },
    {
        "scenario_id": "europe_first",
        "label": "100% europeen si disponible",
        "elec_switch_param": "eu",
        "al_switch_param": "eu",
        "transport_amount_factor": 0.70,
    },
    {
        "scenario_id": "fully_globalized",
        "label": "Totalement mondialise",
        "elec_switch_param": "cn",
        "al_switch_param": "row",
        "transport_amount_factor": 1.35,
    },
)

ROOT_ACTIVITIES = (
    ("production", "production du siege", "production_only"),
    ("lifecycle", "siege cycle de vie", "lifecycle_usage_not_excel_aligned"),
)

PASSIVE_USE_ACTIVITY_NAME = "consommation passive siege tkm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--source-db", default="OPERA_siege")
    parser.add_argument("--scenario-db-prefix", default="POC2026_OPERA_scenario")
    parser.add_argument("--normalization-factor", type=float, default=8095.525063944057)
    parser.add_argument("--excel-use-phase-pe", type=float, default=56.92001)
    parser.add_argument("--output-csv")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def one_activity(db_name: str, name: str, location: str | None = None):
    matches = [
        act
        for act in bd.Database(db_name)
        if act.get("name") == name and (location is None or act.get("location") == location)
    ]
    if not matches:
        raise LookupError(f"Activity not found: {db_name} / {name} / {location or '*'}")
    return matches[0]


def ecoinvent_targets() -> dict[tuple[str, str], Any]:
    db_name = "ecoinvent-3.10-cutoff"
    return {
        ("electricity_low", "fr"): one_activity(db_name, "market for electricity, low voltage", "FR"),
        ("electricity_low", "eu"): one_activity(db_name, "market group for electricity, low voltage", "RER"),
        ("electricity_low", "us"): one_activity(db_name, "market group for electricity, low voltage", "US"),
        ("electricity_low", "cn"): one_activity(db_name, "market group for electricity, low voltage", "CN"),
        ("electricity_medium", "fr"): one_activity(db_name, "market for electricity, medium voltage", "FR"),
        ("electricity_medium", "eu"): one_activity(db_name, "market group for electricity, medium voltage", "RER"),
        ("electricity_medium", "us"): one_activity(db_name, "market group for electricity, medium voltage", "US"),
        ("electricity_medium", "cn"): one_activity(db_name, "market group for electricity, medium voltage", "CN"),
        ("aluminium", "eu"): one_activity(db_name, "market for aluminium, primary, ingot", "IAI Area, EU27 & EFTA"),
        ("aluminium", "us"): one_activity(db_name, "market for aluminium, primary, ingot", "IAI Area, North America"),
        ("aluminium", "cn"): one_activity(db_name, "aluminium production, primary, ingot", "CN"),
        ("aluminium", "row"): one_activity(db_name, "market for aluminium, primary, ingot", "RoW"),
    }


def is_market_electricity(name: str) -> bool:
    text = name.lower()
    return text.startswith("market for electricity") or text.startswith("market group for electricity")


def electricity_voltage_key(name: str) -> str:
    text = name.lower()
    if "medium voltage" in text:
        return "electricity_medium"
    return "electricity_low"


def is_primary_aluminium(name: str) -> bool:
    text = name.lower()
    return text == "market for aluminium, primary, ingot" or text == "aluminium production, primary, ingot"


def is_foreground_transport_exchange(activity_name: str, input_name: str, input_unit: str) -> bool:
    if activity_name in {"consommation passive siege tkm", "consommation passive siege pkm"}:
        return False
    text = input_name.lower()
    if "transport, freight" in text:
        return True
    return input_unit in {"ton kilometer"} and "kerosene" not in text


def replace_exchange_input(exchange, target) -> None:
    exchange["input"] = target.key
    exchange["database"] = target.get("database")
    exchange["name"] = target.get("name")
    exchange["location"] = target.get("location")
    exchange["unit"] = target.get("unit")
    exchange.save()


def drop_database_if_exists(name: str) -> None:
    if name not in bd.databases:
        return
    bd.Database(name).delete(warn=False)
    try:
        del bd.databases[name]
    except KeyError:
        pass
    bd.databases.flush()


def prepare_scenario_database(source_db: str, scenario_db: str, scenario: dict[str, Any], targets: dict[tuple[str, str], Any]) -> dict[str, int]:
    drop_database_if_exists(scenario_db)
    bd.Database(source_db).copy(scenario_db)

    counts = {
        "electricity_replacements": 0,
        "aluminium_replacements": 0,
        "transport_scaled_exchanges": 0,
    }
    elec_switch = scenario.get("elec_switch_param") or ""
    al_switch = scenario.get("al_switch_param") or ""
    transport_factor = float(scenario.get("transport_amount_factor") or 1.0)

    for activity in bd.Database(scenario_db):
        activity_name = activity.get("name", "")
        for exchange in activity.exchanges():
            if exchange.get("type") != "technosphere":
                continue
            input_activity = exchange.input
            input_name = input_activity.get("name", "")
            input_unit = input_activity.get("unit", "")
            if input_activity.get("database") != "ecoinvent-3.10-cutoff":
                continue
            if elec_switch and is_market_electricity(input_name):
                target = targets[(electricity_voltage_key(input_name), elec_switch)]
                replace_exchange_input(exchange, target)
                counts["electricity_replacements"] += 1
                continue
            if al_switch and is_primary_aluminium(input_name):
                target = targets[("aluminium", al_switch)]
                replace_exchange_input(exchange, target)
                counts["aluminium_replacements"] += 1
                continue
            if not abs(transport_factor - 1.0) < 1e-12 and is_foreground_transport_exchange(activity_name, input_name, input_unit):
                exchange["amount"] = float(exchange.get("amount") or 0.0) * transport_factor
                exchange.save()
                counts["transport_scaled_exchanges"] += 1

    bd.Database(scenario_db).process()
    return counts


def lcia_score(db_name: str, activity_name: str, method: tuple[str, ...]) -> float:
    activity = one_activity(db_name, activity_name)
    lca = bc.LCA({activity: 1}, method)
    lca.lci()
    lca.lcia()
    return float(lca.score)


def passive_use_amount(db_name: str) -> float:
    activity = one_activity(db_name, "siege cycle de vie")
    amount = 0.0
    for exchange in activity.exchanges():
        if exchange.get("type") != "technosphere":
            continue
        input_activity = exchange.input
        if input_activity.get("name") == PASSIVE_USE_ACTIVITY_NAME:
            amount += float(exchange.get("amount") or 0.0)
    return amount


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    bd.projects.set_current(args.project)
    missing = [name for name in ("biosphere3", "ecoinvent-3.10-cutoff", args.source_db) if name not in bd.databases]
    if missing:
        raise RuntimeError(f"Missing Brightway databases: {', '.join(missing)}")
    if METHOD_CLIMATE_EF30 not in bd.methods:
        raise RuntimeError(f"Missing Brightway method: {METHOD_CLIMATE_EF30}")

    targets = ecoinvent_targets()
    baseline_scores: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    excel_use_phase_kgco2e = float(args.excel_use_phase_pe or 0.0) * float(args.normalization_factor or 0.0)
    passive_unit_score = lcia_score(args.source_db, PASSIVE_USE_ACTIVITY_NAME, METHOD_CLIMATE_EF30)
    baseline_passive_amount = passive_use_amount(args.source_db)
    baseline_passive_score = baseline_passive_amount * passive_unit_score
    baseline_aligned_lifecycle_score: float | None = None

    for root_id, activity_name, status in ROOT_ACTIVITIES:
        baseline_scores[root_id] = lcia_score(args.source_db, activity_name, METHOD_CLIMATE_EF30)
    if baseline_scores.get("lifecycle") is not None:
        baseline_lifecycle_without_raw_usage = baseline_scores["lifecycle"] - baseline_passive_score
        baseline_aligned_lifecycle_score = baseline_lifecycle_without_raw_usage + excel_use_phase_kgco2e

    for scenario in SCENARIOS:
        scenario_id = scenario["scenario_id"]
        if scenario_id == "current_export":
            scenario_db = args.source_db
            counts = {
                "electricity_replacements": 0,
                "aluminium_replacements": 0,
                "transport_scaled_exchanges": 0,
            }
        else:
            scenario_db = f"{args.scenario_db_prefix}_{scenario_id}"
            counts = prepare_scenario_database(args.source_db, scenario_db, scenario, targets)

        try:
            for root_id, activity_name, validation_status in ROOT_ACTIVITIES:
                score = lcia_score(scenario_db, activity_name, METHOD_CLIMATE_EF30)
                baseline = baseline_scores[root_id]
                delta = score - baseline
                rows.append(
                    {
                        "scenario_id": scenario_id,
                        "label": scenario["label"],
                        "root_activity_id": root_id,
                        "root_activity_name": activity_name,
                        "validation_status": validation_status,
                        "method": " | ".join(METHOD_CLIMATE_EF30),
                        "score_kgco2e": round(score, 9),
                        "score_person_equivalent": round(score / args.normalization_factor, 9),
                        "baseline_kgco2e": round(baseline, 9),
                        "delta_kgco2e": round(delta, 9),
                        "delta_person_equivalent": round(delta / args.normalization_factor, 9),
                        "relative_delta_pct": round(100.0 * delta / baseline, 6) if baseline else "",
                        "elec_switch_param": scenario.get("elec_switch_param") or "",
                        "al_switch_param": scenario.get("al_switch_param") or "",
                        "transport_amount_factor": scenario.get("transport_amount_factor"),
                        **counts,
                    }
                )
            raw_lifecycle_score = lcia_score(scenario_db, "siege cycle de vie", METHOD_CLIMATE_EF30)
            scenario_passive_score = passive_use_amount(scenario_db) * passive_unit_score
            aligned_score = raw_lifecycle_score - scenario_passive_score + excel_use_phase_kgco2e
            aligned_baseline = baseline_aligned_lifecycle_score if baseline_aligned_lifecycle_score is not None else aligned_score
            aligned_delta = aligned_score - aligned_baseline
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "label": f"{scenario['label']} - usage STELIA calibre",
                    "root_activity_id": "lifecycle_excel_aligned",
                    "root_activity_name": "siege cycle de vie corrige usage STELIA",
                    "validation_status": "excel_usage_calibrated",
                    "method": " | ".join(METHOD_CLIMATE_EF30),
                    "score_kgco2e": round(aligned_score, 9),
                    "score_person_equivalent": round(aligned_score / args.normalization_factor, 9),
                    "baseline_kgco2e": round(aligned_baseline, 9),
                    "delta_kgco2e": round(aligned_delta, 9),
                    "delta_person_equivalent": round(aligned_delta / args.normalization_factor, 9),
                    "relative_delta_pct": round(100.0 * aligned_delta / aligned_baseline, 6) if aligned_baseline else "",
                    "elec_switch_param": scenario.get("elec_switch_param") or "",
                    "al_switch_param": scenario.get("al_switch_param") or "",
                    "transport_amount_factor": scenario.get("transport_amount_factor"),
                    **counts,
                    "raw_lifecycle_kgco2e": round(raw_lifecycle_score, 9),
                    "raw_passive_usage_kgco2e_removed": round(scenario_passive_score, 9),
                    "excel_use_phase_kgco2e_added": round(excel_use_phase_kgco2e, 9),
                    "passive_usage_activity_score_kgco2e_per_unit": round(passive_unit_score, 12),
                    "raw_passive_usage_amount": round(passive_use_amount(scenario_db), 9),
                }
            )
        finally:
            if scenario_id != "current_export" and scenario_db in bd.databases:
                drop_database_if_exists(scenario_db)

    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    rows = run(args)
    if args.output_csv:
        write_csv(Path(args.output_csv), rows)
    if args.json:
        print(json.dumps(rows, ensure_ascii=True))
    else:
        for row in rows:
            print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
