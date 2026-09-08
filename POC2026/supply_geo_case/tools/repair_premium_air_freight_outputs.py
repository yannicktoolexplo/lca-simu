"""Repair legacy premium-transport rows that incorrectly fell back to road freight."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


AIR_VIRTUAL_NAME = (
    "market for transport, freight, aircraft, medium haul (virtual SDD)"
)
AIR_MARKET_NAME = "market for transport, freight, aircraft, medium haul"
AIR_REFERENCE_PRODUCT = "transport, freight, aircraft"
AIR_DATABASE = "SDD proxy"
AIR_LOCATION = "GLO"
AIR_UNIT = "ton kilometer"
NORMALIZATION_FACTOR = 8095.525063944057
COUPLING_VERSION = "physical_regional_energy_v2_air_freight"
LORRY_PATTERN = re.compile(
    r"market for transport, freight, lorry 16-32 metric ton, EURO\d",
    re.IGNORECASE,
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def open_text(path: Path, mode: str):
    if path.suffix == ".gz":
        return gzip.open(path, mode, encoding="utf-8", newline="")
    return path.open(mode, encoding="utf-8", newline="")


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open_text(path, "rt") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with open_text(path, "wt") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def iter_rows(path: Path) -> Iterator[dict[str, str]]:
    with open_text(path, "rt") as handle:
        yield from csv.DictReader(handle)


def atomic_transform_csv(
    path: Path,
    transform: Callable[[dict[str, str]], dict[str, str]],
    consume: Callable[[dict[str, str]], None],
) -> int:
    temp = path.with_name(path.name + ".air-repair.tmp")
    count = 0
    target_open = (
        gzip.open(temp, "wt", encoding="utf-8", newline="")
        if path.suffix == ".gz"
        else temp.open("w", encoding="utf-8", newline="")
    )
    with open_text(path, "rt") as source, target_open as target:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise RuntimeError(f"Missing CSV header: {path}")
        writer = csv.DictWriter(target, fieldnames=reader.fieldnames)
        writer.writeheader()
        for source_row in reader:
            row = transform(dict(source_row))
            writer.writerow(row)
            consume(row)
            count += 1
    os.replace(temp, path)
    return count


def is_wrong_premium_lorry(row: dict[str, Any]) -> bool:
    return (
        clean(row.get("mechanism")) == "premium_transport"
        and bool(LORRY_PATTERN.search(clean(row.get("exchange_name"))))
    )


def repair_exchange_row(row: dict[str, str]) -> dict[str, str]:
    if not is_wrong_premium_lorry(row):
        return row
    row.update(
        {
            "exchange_name": AIR_VIRTUAL_NAME,
            "exchange_reference_product": AIR_REFERENCE_PRODUCT,
            "exchange_category": "transport",
            "exchange_unit": AIR_UNIT,
            "exchange_database": AIR_DATABASE,
            "exchange_location": AIR_LOCATION,
            "mapping_status": "virtual_exchange_proxy",
            "mapping_rule_id": "virtual_air_freight_market_fallback",
            "regionalization_status": "global_air_freight_market",
            "brightway_exact_eligible": "True",
        }
    )
    return row


def aircraft_factor(factors: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in factors
        if clean(row.get("exchange_name")) == AIR_MARKET_NAME
        and clean(row.get("exchange_location")) == AIR_LOCATION
        and clean(row.get("exchange_unit")) == AIR_UNIT
        and clean(row.get("exchange_reference_product"))
        == AIR_REFERENCE_PRODUCT
        and clean(row.get("lcia_status")) == "exact_lcia_factor"
    ]
    if not candidates:
        raise RuntimeError("Exact Brightway aircraft freight factor is missing")
    return candidates[0]


def repair_lcia_row(
    row: dict[str, str],
    factor: dict[str, str],
) -> dict[str, str]:
    if not is_wrong_premium_lorry(row):
        return row
    unit_score = number(factor.get("unit_score_kgco2e_per_exchange_unit"))
    quantity = number(row.get("quantity_delta_amount"))
    allocated = number(row.get("allocated_delta_kgco2e"))
    exact = quantity * unit_score
    row.update(
        {
            "exchange_name": AIR_VIRTUAL_NAME,
            "exchange_category": "transport",
            "exchange_unit": AIR_UNIT,
            "exchange_database": AIR_DATABASE,
            "exchange_location": AIR_LOCATION,
            "exchange_reference_product": AIR_REFERENCE_PRODUCT,
            "exact_unit_score_kgco2e_per_exchange_unit": str(
                round(unit_score, 12)
            ),
            "exact_delta_kgco2e": str(round(exact, 9)),
            "retained_delta_kgco2e": str(round(exact, 9)),
            "retained_result_method": "exact_brightway",
            "exact_delta_person_equivalent": str(
                round(exact / NORMALIZATION_FACTOR, 12)
            ),
            "exact_minus_allocated_kgco2e": str(
                round(exact - allocated, 9)
            ),
            "exact_to_allocated_ratio": str(
                round(exact / allocated, 9) if abs(allocated) > 1e-12 else ""
            ),
            "mapping_status": "virtual_exchange_proxy",
            "lcia_status": "exact_lcia_factor",
            "brightway_activity_key": clean(
                factor.get("brightway_activity_key")
            ),
            "factor_match_status": clean(factor.get("match_status")),
            "factor_match_count": clean(factor.get("match_count")),
            "regionalization_status": "global_air_freight_market",
            "brightway_exact_eligible": "True",
        }
    )
    return row


def exchange_aggregator():
    categories: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    top: dict[tuple[str, str, str, str], dict[str, Any]] = defaultdict(
        lambda: defaultdict(float)
    )

    def consume(row: dict[str, str]) -> None:
        category_key = (
            clean(row.get("scenario_id")),
            clean(row.get("exchange_category")),
            clean(row.get("mapping_status")),
        )
        values = categories[category_key]
        values["delta_kgco2e"] += number(row.get("delta_kgco2e"))
        values["abs_delta_amount"] += abs(number(row.get("delta_amount")))
        values["row_count"] += number(row.get("row_count"))
        values["exchange_count"] += 1
        top_key = (
            clean(row.get("scenario_id")),
            clean(row.get("activity_name")),
            clean(row.get("exchange_name")),
            clean(row.get("exchange_category")),
        )
        top_values = top[top_key]
        top_values["delta_kgco2e"] += number(row.get("delta_kgco2e"))
        top_values["abs_delta_amount"] += abs(number(row.get("delta_amount")))
        top_values["row_count"] += number(row.get("row_count"))
        top_values["exchange_unit"] = clean(row.get("exchange_unit"))
        top_values["mapping_status"] = clean(row.get("mapping_status"))

    def finish() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        category_rows = [
            {
                "scenario_id": scenario,
                "exchange_category": category,
                "mapping_status": mapping,
                "label": f"{category} / {mapping}",
                "value": round(values["delta_kgco2e"], 9),
                "delta_kgco2e": round(values["delta_kgco2e"], 9),
                "abs_delta_amount": round(values["abs_delta_amount"], 9),
                "row_count": int(values["row_count"]),
                "exchange_row_count": int(values["exchange_count"]),
            }
            for (scenario, category, mapping), values in categories.items()
        ]
        category_rows.sort(key=lambda row: -abs(number(row["delta_kgco2e"])))
        top_rows = [
            {
                "scenario_id": scenario,
                "activity_name": activity,
                "exchange_name": exchange,
                "exchange_category": category,
                "label": f"{activity} -> {exchange}",
                "value": round(values["delta_kgco2e"], 9),
                "delta_kgco2e": round(values["delta_kgco2e"], 9),
                "abs_delta_amount": round(values["abs_delta_amount"], 9),
                "exchange_unit": clean(values.get("exchange_unit")),
                "mapping_status": clean(values.get("mapping_status")),
                "row_count": int(values["row_count"]),
            }
            for (scenario, activity, exchange, category), values in top.items()
        ]
        top_rows.sort(key=lambda row: -abs(number(row["delta_kgco2e"])))
        return category_rows, top_rows[:30]

    return consume, finish


def lcia_aggregator():
    categories: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    months: dict[tuple[str, int], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    top: dict[tuple[str, str, str, str], dict[str, Any]] = defaultdict(
        lambda: defaultdict(float)
    )
    stats: dict[str, float] = defaultdict(float)

    def consume(row: dict[str, str]) -> None:
        allocated = number(row.get("allocated_delta_kgco2e"))
        retained = number(row.get("retained_delta_kgco2e"))
        has_exact = clean(row.get("exact_delta_kgco2e")) != ""
        exact = number(row.get("exact_delta_kgco2e")) if has_exact else 0.0
        scenario = clean(row.get("scenario_id"))
        key = (
            scenario,
            clean(row.get("exchange_category")),
            clean(row.get("mapping_status")),
            clean(row.get("lcia_status")),
        )
        month_key = (scenario, int(number(row.get("month_index"))))
        for values in (categories[key], months[month_key]):
            values["allocated_delta_kgco2e"] += allocated
            values["allocated_abs_delta_kgco2e"] += abs(allocated)
            values["exact_delta_kgco2e"] += exact
            values["retained_delta_kgco2e"] += retained
            values["covered_abs"] += abs(allocated) if has_exact else 0.0
            values["row_count"] += 1
            values["exact_row_count"] += 1 if has_exact else 0
        if has_exact:
            top_key = (
                scenario,
                clean(row.get("activity_name")),
                clean(row.get("exchange_name")),
                clean(row.get("exchange_category")),
            )
            values = top[top_key]
            values["exact_delta_kgco2e"] += exact
            values["allocated_delta_kgco2e"] += allocated
            values["quantity_delta_abs"] += abs(
                number(row.get("quantity_delta_amount"))
            )
            values["row_count"] += 1
            values["exchange_unit"] = clean(row.get("exchange_unit"))
            values["mapping_status"] = clean(row.get("mapping_status"))
        stats["rows"] += 1
        stats["allocated_abs"] += abs(allocated)
        stats["exact_covered_abs"] += abs(allocated) if has_exact else 0.0
        stats["exact_retained_abs"] += abs(retained) if has_exact else 0.0
        stats["retained_abs"] += abs(retained)
        if clean(row.get("physical_quantity_status")) not in {
            "",
            "calibrated_not_yet_physical",
        }:
            stats["physical_rows"] += 1

    def common_row(values: dict[str, float]) -> dict[str, Any]:
        allocated = values["allocated_delta_kgco2e"]
        exact = values["exact_delta_kgco2e"]
        allocated_abs = values["allocated_abs_delta_kgco2e"]
        return {
            "allocated_delta_kgco2e": round(allocated, 9),
            "allocated_abs_delta_kgco2e": round(allocated_abs, 9),
            "exact_delta_kgco2e": round(exact, 9),
            "retained_delta_kgco2e": round(
                values["retained_delta_kgco2e"], 9
            ),
            "exact_minus_allocated_kgco2e": round(exact - allocated, 9),
            "exact_coverage_allocated_pct": round(
                100.0 * values["covered_abs"] / allocated_abs, 6
            )
            if allocated_abs
            else "",
            "row_count": int(values["row_count"]),
            "exact_row_count": int(values["exact_row_count"]),
        }

    def finish(
        factor_count: int,
        exact_factor_count: int,
    ) -> tuple[list, list, list, list]:
        category_rows = []
        for (scenario, category, mapping, lcia_status), values in categories.items():
            row = {
                "scenario_id": scenario,
                "exchange_category": category,
                "mapping_status": mapping,
                "lcia_status": lcia_status,
                "label": f"{category} / {mapping} / {lcia_status}",
            }
            row.update(common_row(values))
            row["value"] = row["exact_delta_kgco2e"]
            category_rows.append(row)
        category_rows.sort(
            key=lambda row: -abs(number(row["exact_delta_kgco2e"]))
        )
        monthly_rows = []
        for (scenario, month), values in sorted(months.items()):
            row = {"scenario_id": scenario, "month_index": month}
            row.update(common_row(values))
            monthly_rows.append(row)
        top_rows = []
        for (scenario, activity, exchange, category), values in top.items():
            exact = values["exact_delta_kgco2e"]
            allocated = values["allocated_delta_kgco2e"]
            top_rows.append(
                {
                    "scenario_id": scenario,
                    "activity_name": activity,
                    "exchange_name": exchange,
                    "exchange_category": category,
                    "label": f"{activity} -> {exchange}",
                    "exact_delta_kgco2e": round(exact, 9),
                    "allocated_delta_kgco2e": round(allocated, 9),
                    "exact_minus_allocated_kgco2e": round(
                        exact - allocated, 9
                    ),
                    "quantity_delta_abs": round(
                        values["quantity_delta_abs"], 9
                    ),
                    "exchange_unit": clean(values.get("exchange_unit")),
                    "mapping_status": clean(values.get("mapping_status")),
                    "row_count": int(values["row_count"]),
                    "value": round(exact, 9),
                }
            )
        top_rows.sort(
            key=lambda row: -abs(number(row["exact_delta_kgco2e"]))
        )
        rows = stats["rows"]
        status_rows = [
            {
                "status": "ok",
                "input_rows": int(rows),
                "output_rows": int(rows),
                "unique_exchange_signatures": factor_count,
                "exact_factor_count": exact_factor_count,
                "exact_factor_coverage_pct": round(
                    100.0 * exact_factor_count / factor_count,
                    6,
                )
                if factor_count
                else "",
                "exact_impact_coverage_pct": round(
                    100.0
                    * stats["exact_covered_abs"]
                    / stats["allocated_abs"],
                    6,
                )
                if stats["allocated_abs"]
                else "",
                "exact_retained_impact_share_pct": round(
                    100.0
                    * stats["exact_retained_abs"]
                    / stats["retained_abs"],
                    6,
                )
                if stats["retained_abs"]
                else "",
                "physical_inventory_row_count": int(stats["physical_rows"]),
                "physical_inventory_row_coverage_pct": round(
                    100.0 * stats["physical_rows"] / rows, 6
                )
                if rows
                else "",
                "method": (
                    "ecoinvent-3.10 | EF v3.0 | climate change | "
                    "global warming potential (GWP100)"
                ),
            }
        ]
        return category_rows, monthly_rows, top_rows[:40], status_rows

    return consume, finish


def repair_dataset(data_dir: Path, compressed: bool) -> dict[str, Any]:
    def named(stem: str) -> Path:
        return data_dir / f"{stem}.csv.gz" if compressed else data_dir / f"{stem}.csv"

    exchange_path = named("sdd_brightway_exchange_delta")
    lcia_path = named("sdd_brightway_exchange_lcia")

    factor_path = named("sdd_brightway_exchange_lcia_factors")
    factors = read_rows(factor_path)
    factor = aircraft_factor(factors)
    filtered_factors = [
        row
        for row in factors
        if not LORRY_PATTERN.search(clean(row.get("exchange_name")))
    ]
    write_rows(factor_path, filtered_factors)

    exchange_consume, exchange_finish = exchange_aggregator()
    exchange_rows = atomic_transform_csv(
        exchange_path,
        repair_exchange_row,
        exchange_consume,
    )
    exchange_categories, top_exchanges = exchange_finish()

    lcia_consume, lcia_finish = lcia_aggregator()
    lcia_rows = atomic_transform_csv(
        lcia_path,
        lambda row: repair_lcia_row(row, factor),
        lcia_consume,
    )
    exact_factor_count = sum(
        1
        for row in filtered_factors
        if clean(row.get("lcia_status")) == "exact_lcia_factor"
    )
    categories, monthly, top, status = lcia_finish(
        len(filtered_factors),
        exact_factor_count,
    )
    write_rows(named("sdd_brightway_exchange_lcia_category_totals"), categories)
    write_rows(named("sdd_brightway_exchange_lcia_monthly"), monthly)
    write_rows(named("sdd_brightway_exchange_lcia_top"), top)
    write_rows(named("sdd_brightway_exchange_lcia_status"), status)
    if not compressed:
        write_rows(named("sdd_brightway_exchange_category_totals"), exchange_categories)
        write_rows(named("sdd_brightway_top_exchanges"), top_exchanges)
    return {
        "exchange_rows": exchange_rows,
        "lcia_rows": lcia_rows,
        "exchange_category_totals": exchange_categories,
        "top_exchanges": top_exchanges,
        "lcia_category_totals": categories,
        "lcia_monthly": monthly,
        "lcia_top": top,
        "lcia_status": status,
    }


def replace_lorry_labels(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: replace_lorry_labels(item) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_lorry_labels(item) for item in value]
    if isinstance(value, str):
        return LORRY_PATTERN.sub(AIR_VIRTUAL_NAME, value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run(output_root: Path) -> dict[str, Any]:
    main = repair_dataset(output_root / "data", compressed=False)
    scenarios: dict[str, Any] = {}
    for scenario_dir in sorted((output_root / "scenarios").glob("*")):
        if not scenario_dir.is_dir():
            continue
        result = repair_dataset(scenario_dir / "data", compressed=True)
        manifest_path = scenario_dir / "scenario_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["sdd_brightway_coupling_version"] = COUPLING_VERSION
        manifest["brightway_lcia_status"] = result["lcia_status"]
        write_json(manifest_path, manifest)
        cascade_path = scenario_dir / "risk_cascades.json"
        if cascade_path.exists():
            cascades = json.loads(cascade_path.read_text(encoding="utf-8"))
            write_json(cascade_path, replace_lorry_labels(cascades))
        scenarios[scenario_dir.name] = result["lcia_status"][0]

    dashboard_path = output_root / "summaries" / "general_kpis.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    dashboard = replace_lorry_labels(dashboard)
    brightway = dashboard.setdefault("sdd_brightway", {})
    brightway["exchange_category_totals"] = main["exchange_category_totals"]
    brightway["top_exchanges"] = main["top_exchanges"]
    brightway["exchange_lcia_category_totals"] = main[
        "lcia_category_totals"
    ]
    brightway["exchange_lcia_monthly"] = main["lcia_monthly"]
    brightway["exchange_lcia_top"] = main["lcia_top"]
    brightway["exchange_lcia_status"] = main["lcia_status"]
    dashboard["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(dashboard_path, dashboard)
    return {"main": main["lcia_status"][0], "scenarios": scenarios}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
    )
    args = parser.parse_args()
    result = run(args.output_root.resolve())
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
