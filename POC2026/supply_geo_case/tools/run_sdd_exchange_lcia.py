"""Compute exact Brightway marginal LCIA factors for SDD exchange deltas."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
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

VIRTUAL_EXCHANGE_TARGETS = {
    "market for transport, freight, aircraft, medium haul (virtual SDD)": {
        "database": "ecoinvent-3.10-cutoff",
        "name": "market for transport, freight, aircraft, medium haul",
        "location": "GLO",
        "unit": "ton kilometer",
        "reference_product": "transport, freight, aircraft",
    }
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="bw25-ecoinvent310")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--factor-csv", required=True)
    parser.add_argument("--category-csv", required=True)
    parser.add_argument("--monthly-csv", required=True)
    parser.add_argument("--top-csv", required=True)
    parser.add_argument("--status-csv", required=True)
    parser.add_argument("--normalization-factor", type=float, default=8095.525063944057)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def clean(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


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


def normalized_signature(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    name = clean(row.get("exchange_name"))
    database = clean(row.get("exchange_database"))
    location = clean(row.get("exchange_location"))
    unit = clean(row.get("exchange_unit"))
    reference_product = clean(row.get("exchange_reference_product"))
    if clean(row.get("mapping_status")) == "virtual_exchange_proxy":
        target = VIRTUAL_EXCHANGE_TARGETS.get(name)
        if target:
            database = target["database"]
            name = target["name"]
            location = target["location"]
            unit = target["unit"]
            reference_product = target["reference_product"]
    return database, name, location, unit, reference_product


def find_activity(
    database: str,
    name: str,
    location: str,
    unit: str,
    reference_product: str,
) -> tuple[Any | None, str, int]:
    if database not in bd.databases:
        return None, "database_missing", 0
    matches = [act for act in bd.Database(database) if act.get("name") == name]
    if location:
        location_matches = [act for act in matches if clean(act.get("location")) == location]
        if location_matches:
            matches = location_matches
    if unit:
        unit_matches = [act for act in matches if clean(act.get("unit")) == unit]
        if unit_matches:
            matches = unit_matches
    if reference_product:
        rp_matches = [
            act
            for act in matches
            if clean(act.get("reference product")) == reference_product or clean(act.get("reference_product")) == reference_product
        ]
        if rp_matches:
            matches = rp_matches
    if not matches:
        return None, "activity_not_found", 0
    status = "exact_activity_match" if len(matches) == 1 else "ambiguous_activity_first_match"
    return matches[0], status, len(matches)


def lcia_score(activity: Any, method: tuple[str, ...]) -> float:
    lca = bc.LCA({activity: 1.0}, method)
    lca.lci()
    lca.lcia()
    return float(lca.score)


def factor_rows_for_signatures(rows: list[dict[str, Any]], method: tuple[str, ...]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    signatures = {
        normalized_signature(row)
        for row in rows
        if clean(row.get("mapping_status")) in {"mapped_exchange", "virtual_exchange_proxy"}
    }
    factors: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    matched_activities: list[tuple[tuple[str, str, str, str, str], Any]] = []
    for signature in sorted(signatures):
        database, name, location, unit, reference_product = signature
        if database == "SDD proxy":
            factors[signature] = {
                "exchange_database": database,
                "exchange_name": name,
                "exchange_location": location,
                "exchange_unit": unit,
                "exchange_reference_product": reference_product,
                "brightway_activity_key": "",
                "match_status": "sdd_calibrated_proxy",
                "match_count": 0,
                "lcia_status": "calibrated_sdd_proxy_not_exact",
                "unit_score_kgco2e_per_exchange_unit": "",
                "method": " | ".join(method),
                "error": "",
            }
            continue
        activity, match_status, match_count = find_activity(database, name, location, unit, reference_product)
        activity_key = ""
        lcia_status = match_status
        if activity is not None:
            activity_key = "|".join(str(part) for part in activity.key)
            matched_activities.append((signature, activity))
        factors[signature] = {
            "exchange_database": database,
            "exchange_name": name,
            "exchange_location": location,
            "exchange_unit": unit,
            "exchange_reference_product": reference_product,
            "brightway_activity_key": activity_key,
            "match_status": match_status,
            "match_count": match_count,
            "lcia_status": lcia_status,
            "unit_score_kgco2e_per_exchange_unit": "",
            "method": " | ".join(method),
            "error": "",
        }
    if matched_activities:
        first_signature, first_activity = matched_activities[0]
        try:
            lca = bc.LCA({first_activity: 1.0}, method)
            lca.lci()
            lca.lcia()
            factors[first_signature]["unit_score_kgco2e_per_exchange_unit"] = round(float(lca.score), 12)
            factors[first_signature]["lcia_status"] = "exact_lcia_factor"
            for signature, activity in matched_activities[1:]:
                try:
                    lca.redo_lcia({activity: 1.0})
                    factors[signature]["unit_score_kgco2e_per_exchange_unit"] = round(float(lca.score), 12)
                    factors[signature]["lcia_status"] = "exact_lcia_factor"
                except Exception:
                    score = lcia_score(activity, method)
                    factors[signature]["unit_score_kgco2e_per_exchange_unit"] = round(score, 12)
                    factors[signature]["lcia_status"] = "exact_lcia_factor"
        except Exception as exc:
            for signature, activity in matched_activities:
                try:
                    score = lcia_score(activity, method)
                    factors[signature]["unit_score_kgco2e_per_exchange_unit"] = round(score, 12)
                    factors[signature]["lcia_status"] = "exact_lcia_factor"
                except Exception as inner_exc:
                    factors[signature]["lcia_status"] = "lcia_error"
                    factors[signature]["error"] = f"{type(inner_exc).__name__}: {inner_exc}"
            factors[first_signature]["error"] = clean(factors[first_signature].get("error")) or f"{type(exc).__name__}: {exc}"
    return factors


def exact_rows(
    rows: list[dict[str, Any]],
    factors: dict[tuple[str, str, str, str, str], dict[str, Any]],
    normalization_factor: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        signature = normalized_signature(row)
        factor = factors.get(signature, {})
        unit_score = safe_float(factor.get("unit_score_kgco2e_per_exchange_unit"), float("nan"))
        allocated = safe_float(row.get("delta_kgco2e"))
        amount = safe_float(row.get("delta_amount"))
        has_exact = math.isfinite(unit_score)
        exact = amount * unit_score if has_exact else ""
        exact_value = safe_float(exact)
        out.append(
            {
                "exchange_delta_id": row.get("exchange_delta_id", ""),
                "month_index": row.get("month_index", ""),
                "role": row.get("role", ""),
                "role_count": row.get("role_count", ""),
                "site_uid": row.get("site_uid", ""),
                "site_count": row.get("site_count", ""),
                "mechanism": row.get("mechanism", ""),
                "inventory_delta_type": row.get("inventory_delta_type", ""),
                "activity_name": row.get("activity_name", ""),
                "exchange_name": row.get("exchange_name", ""),
                "exchange_category": row.get("exchange_category", ""),
                "exchange_unit": row.get("exchange_unit", ""),
                "exchange_database": row.get("exchange_database", ""),
                "exchange_location": row.get("exchange_location", ""),
                "exchange_reference_product": row.get("exchange_reference_product", ""),
                "quantity_delta_amount": row.get("delta_amount", ""),
                "allocated_delta_kgco2e": round(allocated, 9),
                "exact_unit_score_kgco2e_per_exchange_unit": round(unit_score, 12) if has_exact else "",
                "exact_delta_kgco2e": round(exact_value, 9) if has_exact else "",
                "exact_delta_person_equivalent": round(exact_value / normalization_factor, 12) if has_exact and normalization_factor else "",
                "exact_minus_allocated_kgco2e": round(exact_value - allocated, 9) if has_exact else "",
                "exact_to_allocated_ratio": round(exact_value / allocated, 9) if has_exact and abs(allocated) > 1e-12 else "",
                "mapping_status": row.get("mapping_status", ""),
                "activity_match_status": row.get("activity_match_status", ""),
                "lcia_status": factor.get("lcia_status", "not_calculated_proxy"),
                "brightway_activity_key": factor.get("brightway_activity_key", ""),
                "factor_match_status": factor.get("match_status", ""),
                "factor_match_count": factor.get("match_count", ""),
                "lcia_allocation_method": row.get("lcia_allocation_method", ""),
                "source_row_count": row.get("row_count", ""),
                "confidence": row.get("confidence", ""),
            }
        )
    return out


def aggregate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    category_groups: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    monthly_groups: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    top_groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        allocated = safe_float(row.get("allocated_delta_kgco2e"))
        exact_raw = row.get("exact_delta_kgco2e")
        has_exact = clean(exact_raw) != ""
        exact = safe_float(exact_raw) if has_exact else 0.0
        key = (clean(row.get("exchange_category")), clean(row.get("mapping_status")), clean(row.get("lcia_status")))
        category_groups[key]["allocated_delta_kgco2e"] += allocated
        category_groups[key]["allocated_abs_delta_kgco2e"] += abs(allocated)
        category_groups[key]["exact_delta_kgco2e"] += exact
        category_groups[key]["exact_calculated_allocated_kgco2e"] += allocated if has_exact else 0.0
        category_groups[key]["exact_calculated_allocated_abs_kgco2e"] += abs(allocated) if has_exact else 0.0
        category_groups[key]["row_count"] += 1
        category_groups[key]["exact_row_count"] += 1 if has_exact else 0

        month = int(safe_float(row.get("month_index")))
        monthly_groups[month]["allocated_delta_kgco2e"] += allocated
        monthly_groups[month]["allocated_abs_delta_kgco2e"] += abs(allocated)
        monthly_groups[month]["exact_delta_kgco2e"] += exact
        monthly_groups[month]["exact_calculated_allocated_kgco2e"] += allocated if has_exact else 0.0
        monthly_groups[month]["exact_calculated_allocated_abs_kgco2e"] += abs(allocated) if has_exact else 0.0
        monthly_groups[month]["row_count"] += 1
        monthly_groups[month]["exact_row_count"] += 1 if has_exact else 0

        if has_exact:
            top_key = (clean(row.get("activity_name")), clean(row.get("exchange_name")), clean(row.get("exchange_category")))
            top_groups[top_key]["exact_delta_kgco2e"] += exact
            top_groups[top_key]["allocated_delta_kgco2e"] += allocated
            top_groups[top_key]["quantity_delta_abs"] += abs(safe_float(row.get("quantity_delta_amount")))
            top_groups[top_key]["row_count"] += 1
            top_groups[top_key]["exchange_unit"] = clean(row.get("exchange_unit"))
            top_groups[top_key]["mapping_status"] = clean(row.get("mapping_status"))

    category_rows = []
    for (category, mapping_status, lcia_status), values in category_groups.items():
        allocated = safe_float(values.get("allocated_delta_kgco2e"))
        allocated_abs = safe_float(values.get("allocated_abs_delta_kgco2e"))
        exact = safe_float(values.get("exact_delta_kgco2e"))
        covered = safe_float(values.get("exact_calculated_allocated_kgco2e"))
        covered_abs = safe_float(values.get("exact_calculated_allocated_abs_kgco2e"))
        category_rows.append(
            {
                "exchange_category": category,
                "mapping_status": mapping_status,
                "lcia_status": lcia_status,
                "label": f"{category} / {mapping_status} / {lcia_status}",
                "allocated_delta_kgco2e": round(allocated, 9),
                "allocated_abs_delta_kgco2e": round(allocated_abs, 9),
                "exact_delta_kgco2e": round(exact, 9),
                "exact_minus_allocated_kgco2e": round(exact - allocated, 9),
                "exact_coverage_allocated_pct": round(100.0 * covered_abs / allocated_abs, 6) if allocated_abs else "",
                "row_count": int(safe_float(values.get("row_count"))),
                "exact_row_count": int(safe_float(values.get("exact_row_count"))),
                "value": round(exact, 9),
            }
        )
    category_rows.sort(key=lambda row: -abs(safe_float(row.get("exact_delta_kgco2e"))))

    monthly_rows = []
    for month, values in sorted(monthly_groups.items()):
        allocated = safe_float(values.get("allocated_delta_kgco2e"))
        allocated_abs = safe_float(values.get("allocated_abs_delta_kgco2e"))
        exact = safe_float(values.get("exact_delta_kgco2e"))
        covered = safe_float(values.get("exact_calculated_allocated_kgco2e"))
        covered_abs = safe_float(values.get("exact_calculated_allocated_abs_kgco2e"))
        monthly_rows.append(
            {
                "month_index": month,
                "allocated_delta_kgco2e": round(allocated, 9),
                "allocated_abs_delta_kgco2e": round(allocated_abs, 9),
                "exact_delta_kgco2e": round(exact, 9),
                "exact_minus_allocated_kgco2e": round(exact - allocated, 9),
                "exact_coverage_allocated_pct": round(100.0 * covered_abs / allocated_abs, 6) if allocated_abs else "",
                "row_count": int(safe_float(values.get("row_count"))),
                "exact_row_count": int(safe_float(values.get("exact_row_count"))),
            }
        )

    top_rows = []
    for (activity_name, exchange_name, category), values in top_groups.items():
        exact = safe_float(values.get("exact_delta_kgco2e"))
        allocated = safe_float(values.get("allocated_delta_kgco2e"))
        top_rows.append(
            {
                "activity_name": activity_name,
                "exchange_name": exchange_name,
                "exchange_category": category,
                "label": f"{activity_name} -> {exchange_name}",
                "exact_delta_kgco2e": round(exact, 9),
                "allocated_delta_kgco2e": round(allocated, 9),
                "exact_minus_allocated_kgco2e": round(exact - allocated, 9),
                "quantity_delta_abs": round(safe_float(values.get("quantity_delta_abs")), 9),
                "exchange_unit": clean(values.get("exchange_unit")),
                "mapping_status": clean(values.get("mapping_status")),
                "row_count": int(safe_float(values.get("row_count"))),
                "value": round(exact, 9),
            }
        )
    top_rows.sort(key=lambda row: -abs(safe_float(row.get("exact_delta_kgco2e"))))
    return category_rows, monthly_rows, top_rows[:40]


def run(args: argparse.Namespace) -> dict[str, Any]:
    bd.projects.set_current(args.project)
    if METHOD_CLIMATE_EF30 not in bd.methods:
        raise RuntimeError(f"Missing Brightway method: {METHOD_CLIMATE_EF30}")
    source_rows = read_csv(Path(args.input_csv))
    factors = factor_rows_for_signatures(source_rows, METHOD_CLIMATE_EF30)
    output_rows = exact_rows(source_rows, factors, args.normalization_factor)
    category_rows, monthly_rows, top_rows = aggregate_rows(output_rows)
    factor_rows = list(factors.values())
    factor_rows.sort(key=lambda row: (row["lcia_status"], row["exchange_database"], row["exchange_name"], row["exchange_location"]))
    exact_factor_count = sum(1 for row in factor_rows if row.get("lcia_status") == "exact_lcia_factor")
    status_rows = [
        {
            "status": "ok",
            "input_rows": len(source_rows),
            "output_rows": len(output_rows),
            "unique_exchange_signatures": len(factor_rows),
            "exact_factor_count": exact_factor_count,
            "exact_factor_coverage_pct": round(100.0 * exact_factor_count / len(factor_rows), 6) if factor_rows else "",
            "method": " | ".join(METHOD_CLIMATE_EF30),
        }
    ]
    write_csv(Path(args.output_csv), output_rows)
    write_csv(Path(args.factor_csv), factor_rows)
    write_csv(Path(args.category_csv), category_rows)
    write_csv(Path(args.monthly_csv), monthly_rows)
    write_csv(Path(args.top_csv), top_rows)
    write_csv(Path(args.status_csv), status_rows)
    return {
        "status": status_rows,
        "factor_rows": len(factor_rows),
        "exact_factor_count": exact_factor_count,
        "category_rows": len(category_rows),
        "monthly_rows": len(monthly_rows),
        "top_rows": len(top_rows),
    }


def main() -> int:
    args = parse_args()
    summary = run(args)
    if args.json:
        print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
