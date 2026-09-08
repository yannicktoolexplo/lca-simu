"""Run exact EF 3.0 LCIA for the 50 percent lightweight seat foreground."""

from __future__ import annotations

import argparse
import csv
import unicodedata
from pathlib import Path
from typing import Any

import bw2calc as bc
import bw2data as bd
import yaml


METHOD_SPECS = (
    ("Acidification", ("ecoinvent-3.10", "EF v3.0", "acidification", "accumulated exceedance (AE)")),
    ("Climate Change - total", ("ecoinvent-3.10", "EF v3.0", "climate change", "global warming potential (GWP100)")),
    ("Ecotoxicity, freshwater - total", ("ecoinvent-3.10", "EF v3.0", "ecotoxicity: freshwater", "comparative toxic unit for ecosystems (CTUe)")),
    ("Resource use, fossils", ("ecoinvent-3.10", "EF v3.0", "energy resources: non-renewable", "abiotic depletion potential (ADP): fossil fuels")),
    ("Eutrophication, freshwater", ("ecoinvent-3.10", "EF v3.0", "eutrophication: freshwater", "fraction of nutrients reaching freshwater end compartment (P)")),
    ("Eutrophication, marine", ("ecoinvent-3.10", "EF v3.0", "eutrophication: marine", "fraction of nutrients reaching marine end compartment (N)")),
    ("Eutrophication, terrestrial", ("ecoinvent-3.10", "EF v3.0", "eutrophication: terrestrial", "accumulated exceedance (AE)")),
    ("Human toxicity, cancer - total", ("ecoinvent-3.10", "EF v3.0", "human toxicity: carcinogenic", "comparative toxic unit for human (CTUh)")),
    ("Human toxicity, non-cancer - total", ("ecoinvent-3.10", "EF v3.0", "human toxicity: non-carcinogenic", "comparative toxic unit for human (CTUh)")),
    ("Ionising radiation, human health", ("ecoinvent-3.10", "EF v3.0", "ionising radiation: human health", "human exposure efficiency relative to u235")),
    ("Land Use", ("ecoinvent-3.10", "EF v3.0", "land use", "soil quality index")),
    ("Resource use, mineral and metals", ("ecoinvent-3.10", "EF v3.0", "material resources: metals/minerals", "abiotic depletion potential (ADP): elements (ultimate reserves)")),
    ("Ozone depletion", ("ecoinvent-3.10", "EF v3.0", "ozone depletion", "ozone depletion potential (ODP)")),
    ("Particulate matter", ("ecoinvent-3.10", "EF v3.0", "particulate matter formation", "impact on human health")),
    ("Photochemical ozone formation, human health", ("ecoinvent-3.10", "EF v3.0", "photochemical oxidant formation: human health", "tropospheric ozone concentration increase")),
    ("Water use", ("ecoinvent-3.10", "EF v3.0", "water use", "user deprivation potential (deprivation-weighted water consumption)")),
)


def ascii_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char))
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--source-db", default="OPERA_siege")
    parser.add_argument("--scenario-db", default="POC2026_OPERA_lightweight_50")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    return parser.parse_args()


def one_activity(db_name: str, name: str):
    matches = [activity for activity in bd.Database(db_name) if activity.get("name") == name]
    if not matches:
        raise LookupError(f"Activity not found: {db_name} / {name}")
    return matches[0]


def drop_database(name: str) -> None:
    if name not in bd.databases:
        return
    bd.Database(name).delete(warn=False)
    try:
        del bd.databases[name]
    except KeyError:
        pass
    bd.databases.flush()


def activity_scales(config: dict[str, Any]) -> dict[str, tuple[str, float]]:
    result: dict[str, tuple[str, float]] = {}
    for family_id, spec in config.get("families", {}).items():
        retained = 1.0 - float(spec.get("reduction_fraction") or 0.0)
        complexity = float(spec.get("process_complexity_multiplier") or 1.0)
        for name in spec.get("activity_names", []):
            result[ascii_key(name)] = (family_id, retained * complexity)
    for name, scale in config.get("overhead_scales", {}).items():
        result[ascii_key(name)] = ("overhead", float(scale))
    return result


def prepare_scenario(source_db: str, scenario_db: str, config: dict[str, Any]) -> dict[str, Any]:
    drop_database(scenario_db)
    bd.Database(source_db).copy(scenario_db)
    scales = activity_scales(config)
    matched_activities: set[str] = set()
    scaled_exchanges = 0
    for activity in bd.Database(scenario_db):
        activity_key = ascii_key(activity.get("name"))
        match = scales.get(activity_key)
        if not match:
            continue
        matched_activities.add(activity_key)
        _, scale = match
        for exchange in activity.exchanges():
            if exchange.get("type") != "technosphere":
                continue
            exchange["amount"] = float(exchange.get("amount") or 0.0) * scale
            exchange.save()
            scaled_exchanges += 1
    expected = {key for key in scales if key != "recyclage siege"}
    unmatched = sorted(expected - matched_activities)
    if unmatched:
        raise RuntimeError(f"Unmatched lightweight activities: {unmatched}")
    bd.Database(scenario_db).process()
    return {
        "matched_activity_count": len(matched_activities),
        "scaled_exchange_count": scaled_exchanges,
    }


def scores_for_methods(activity, methods: tuple[tuple[str, tuple[str, ...]], ...]) -> dict[str, float]:
    first_method = methods[0][1]
    lca = bc.LCA({activity: 1}, first_method)
    lca.lci()
    scores: dict[str, float] = {}
    for label, method in methods:
        lca.switch_method(method)
        lca.lcia()
        scores[label] = float(lca.score)
    return scores


def kerosene_mass_per_unit(activity) -> float:
    amounts = [
        float(exchange.get("amount") or 0.0)
        for exchange in activity.exchanges()
        if exchange.get("type") == "technosphere"
        and "market for kerosene" in ascii_key(exchange.input.get("name"))
    ]
    amount = sum(amounts)
    if amount <= 0.0:
        raise RuntimeError("No kerosene mass exchange found in OPERA use activity")
    return amount


def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    bd.projects.set_current(args.project)
    missing_methods = [method for _, method in METHOD_SPECS if method not in bd.methods]
    if missing_methods:
        raise RuntimeError(f"Missing EF methods: {missing_methods}")
    counts = prepare_scenario(args.source_db, args.scenario_db, config)
    try:
        baseline_activity = one_activity(args.source_db, "production du siege")
        scenario_activity = one_activity(args.scenario_db, "production du siege")
        fuel_activity = one_activity(args.source_db, "kerosene, production et combustion, 1tkm eq")
        baseline_scores = scores_for_methods(baseline_activity, METHOD_SPECS)
        scenario_scores = scores_for_methods(scenario_activity, METHOD_SPECS)
        fuel_scores = scores_for_methods(fuel_activity, METHOD_SPECS)
        fuel_mass = kerosene_mass_per_unit(fuel_activity)
        rows = []
        for label, method in METHOD_SPECS:
            method_metadata = bd.Method(method).metadata
            rows.append({
                "scenario_id": config.get("scenario_id"),
                "indicator_id": label,
                "method": " | ".join(method),
                "raw_unit": method_metadata.get("unit", ""),
                "baseline_production_raw": baseline_scores[label],
                "lightweight_production_raw": scenario_scores[label],
                "production_delta_raw": scenario_scores[label] - baseline_scores[label],
                "fuel_factor_raw_per_kg": fuel_scores[label] / fuel_mass,
                "kerosene_exchange_kg_per_activity_unit": fuel_mass,
                "calculation_status": "brightway_exact_foreground_scaled_screening",
                **counts,
            })
        return rows
    finally:
        drop_database(args.scenario_db)


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
