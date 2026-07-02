#!/usr/bin/env python3
"""Re-audit LCA masses against quantity_material.xlsx and primary paths.

The current supply graph contains both detailed component/material rows and
top-down "Siège" aggregate rows. This script separates additive component
masses from top-down reference masses so simulations do not silently double
count the same ACV basis.
"""

from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_simulation_ready_researched.json"
PRIMARY_PATHS_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv"
ESTIMATE_SCRIPT = BASE_DIR / "estimate_output8_masses.py"
WORKBOOK = ROOT / "data" / "quantity_material.xlsx"

OUT_RECORDS = BASE_DIR / "output8_GEO_lca_mass_reaudit_records.csv"
OUT_EQUIPMENT = BASE_DIR / "output8_GEO_lca_mass_reaudit_equipment_summary.csv"
OUT_FAMILIES = BASE_DIR / "output8_GEO_lca_mass_reaudit_family_summary.csv"
OUT_POLICY = BASE_DIR / "output8_GEO_lca_mass_policy_summary.csv"
OUT_MD = BASE_DIR / "output8_GEO_lca_mass_reaudit_report.md"


def clean(value: Any) -> str:
    return str(value or "").strip()


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean(value).lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_mass_module():
    spec = importlib.util.spec_from_file_location("estimate_output8_masses", ESTIMATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {ESTIMATE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workbook_reference() -> dict[str, Any]:
    module = load_mass_module()
    sheets = module.xlsx_rows(WORKBOOK)
    by_equipment_material, by_equipment_total, by_material_total, equipment_display = module.parse_bom(sheets)
    total_non_packaging = module.seat_total(by_material_total)
    family_totals: dict[str, float] = {}
    for family in module.MATERIAL_FAMILIES:
        value, _hits = module.family_sum(None, family, by_equipment_material, by_material_total)
        if value:
            family_totals[family] = value
    return {
        "total_non_packaging": total_non_packaging,
        "by_equipment_total": by_equipment_total,
        "by_material_total": by_material_total,
        "family_totals": family_totals,
        "equipment_display": equipment_display,
    }


def collapse_primary(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    primary = [row for row in rows if clean(row.get("path_type")) == "primary"]
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, str]] = []
    duplicates = 0
    for row in primary:
        key = (
            clean(row.get("record_index")),
            clean(row.get("t4")),
            clean(row.get("t3")),
            clean(row.get("t2")),
            clean(row.get("t1")),
            clean(row.get("oem")),
        )
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        out.append(row)
    return out, duplicates


def is_seat_aggregate(row: dict[str, str], lca: dict[str, Any], method: str) -> bool:
    system = norm(row.get("system"))
    equipment = norm(lca.get("equipment_match"))
    if system == "siege" or equipment == "seat total":
        return True
    return method in {
        "percentage_of_bom_material_total",
        "bom_global_material_family_sum",
        "bom_global_material_total",
    }


def policy_for(row: dict[str, str], lca: dict[str, Any]) -> tuple[str, str, float, float]:
    mass = safe_float(row.get("mass_kg") or lca.get("mass_kg"))
    method = clean(lca.get("mass_method"))
    use_class = clean(lca.get("simulation_use_class"))
    aggregate = is_seat_aggregate(row, lca, method)
    if aggregate:
        return (
            "topdown_reference_only",
            "Do not add to component-level nominal mass; use as a top-down seat reference or option package.",
            0.0,
            mass,
        )
    if method == "bom_exact_system_material":
        return ("include_exact_component", "Exact equipment/material mass from quantity_material.xlsx.", mass, 0.0)
    if use_class == "usable_for_baseline":
        return (
            "include_baseline_estimate",
            "Equipment/material-family estimate; usable for baseline sizing but not as exact BOM proof.",
            mass,
            0.0,
        )
    if use_class == "usable_with_review":
        return (
            "include_with_review",
            "Non-aggregate medium-confidence component estimate; keep visible and review against equipment subtotal.",
            mass,
            0.0,
        )
    return (
        "scenario_only_mass",
        "Low-confidence non-aggregate fallback; keep for topology/scenario sizing, exclude from strict quantitative baseline.",
        0.0,
        mass,
    )


def duplicate_signature(row: dict[str, str], lca: dict[str, Any]) -> str:
    return "|".join(
        [
            norm(row.get("system")),
            norm(row.get("component")),
            norm(row.get("family")),
            clean(lca.get("mass_method")),
            clean(lca.get("material_match")),
            str(round(safe_float(row.get("mass_kg")), 9)),
        ]
    )


def build_record_rows(primary_rows: list[dict[str, str]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signature_counts: Counter[str] = Counter()
    for row in primary_rows:
        idx = int(clean(row.get("record_index")) or 0)
        lca = (records[idx - 1].get("lca_traceability") or {}) if 0 < idx <= len(records) else {}
        signature_counts[duplicate_signature(row, lca)] += 1

    out: list[dict[str, Any]] = []
    for row in primary_rows:
        idx = int(clean(row.get("record_index")) or 0)
        record = records[idx - 1] if 0 < idx <= len(records) else {}
        lca = record.get("lca_traceability") or {}
        method = clean(lca.get("mass_method"))
        policy, action, additive_mass, reference_mass = policy_for(row, lca)
        signature = duplicate_signature(row, lca)
        duplicate_count = signature_counts[signature]
        aggregate = is_seat_aggregate(row, lca, method)
        out.append(
            {
                "record_index": row.get("record_index"),
                "system": row.get("system"),
                "component": row.get("component"),
                "family": row.get("family"),
                "current_mass_kg": row.get("mass_kg"),
                "recommended_additive_mass_kg": round(additive_mass, 9),
                "topdown_reference_mass_kg": round(reference_mass, 9),
                "mass_policy": policy,
                "mass_policy_action": action,
                "is_seat_aggregate": "yes" if aggregate else "no",
                "duplicate_signature_count": duplicate_count,
                "duplicate_mass_warning": "yes" if duplicate_count > 1 and aggregate else "no",
                "lca_use_class": lca.get("simulation_use_class"),
                "lca_confidence": lca.get("confidence"),
                "mass_method": method,
                "match_level": lca.get("match_level"),
                "equipment_match": lca.get("equipment_match"),
                "material_match": lca.get("material_match"),
                "raw_materials_status": lca.get("raw_materials_status"),
                "primary_path_id": row.get("path_id"),
                "t4": row.get("t4"),
                "t3": row.get("t3"),
                "t2": row.get("t2"),
                "t1": row.get("t1"),
            }
        )
    return out


def equipment_summary(record_rows: list[dict[str, Any]], workbook: dict[str, Any]) -> list[dict[str, Any]]:
    by_equipment: dict[str, dict[str, Any]] = {}
    by_equipment_total = workbook["by_equipment_total"]
    for row in record_rows:
        equipment = clean(row.get("equipment_match")) or "unknown"
        item = by_equipment.setdefault(
            equipment,
            {
                "equipment_match": equipment,
                "record_count": 0,
                "current_mass_kg": 0.0,
                "recommended_additive_mass_kg": 0.0,
                "topdown_reference_mass_kg": 0.0,
                "policies": Counter(),
            },
        )
        item["record_count"] += 1
        item["current_mass_kg"] += safe_float(row.get("current_mass_kg"))
        item["recommended_additive_mass_kg"] += safe_float(row.get("recommended_additive_mass_kg"))
        item["topdown_reference_mass_kg"] += safe_float(row.get("topdown_reference_mass_kg"))
        item["policies"][clean(row.get("mass_policy"))] += 1

    rows: list[dict[str, Any]] = []
    for item in by_equipment.values():
        equipment_key = norm(item["equipment_match"])
        reference = by_equipment_total.get(equipment_key, 0.0)
        delta = item["recommended_additive_mass_kg"] - reference if reference else 0.0
        rows.append(
            {
                "equipment_match": item["equipment_match"],
                "record_count": item["record_count"],
                "workbook_equipment_mass_kg": round(reference, 9),
                "current_mass_kg": round(item["current_mass_kg"], 9),
                "recommended_additive_mass_kg": round(item["recommended_additive_mass_kg"], 9),
                "topdown_reference_mass_kg": round(item["topdown_reference_mass_kg"], 9),
                "delta_additive_vs_workbook_kg": round(delta, 9) if reference else "",
                "delta_additive_vs_workbook_pct": round(100 * delta / reference, 1) if reference else "",
                "policies": ";".join(f"{k}={v}" for k, v in item["policies"].most_common()),
            }
        )
    rows.sort(key=lambda r: -safe_float(r["current_mass_kg"]))
    return rows


def family_summary(record_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for row in record_rows:
        family = clean(row.get("family")) or "unknown"
        item = stats.setdefault(
            family,
            {
                "family": family,
                "record_count": 0,
                "current_mass_kg": 0.0,
                "recommended_additive_mass_kg": 0.0,
                "topdown_reference_mass_kg": 0.0,
                "policies": Counter(),
            },
        )
        item["record_count"] += 1
        item["current_mass_kg"] += safe_float(row.get("current_mass_kg"))
        item["recommended_additive_mass_kg"] += safe_float(row.get("recommended_additive_mass_kg"))
        item["topdown_reference_mass_kg"] += safe_float(row.get("topdown_reference_mass_kg"))
        item["policies"][clean(row.get("mass_policy"))] += 1
    rows = []
    for item in stats.values():
        rows.append(
            {
                "family": item["family"],
                "record_count": item["record_count"],
                "current_mass_kg": round(item["current_mass_kg"], 9),
                "recommended_additive_mass_kg": round(item["recommended_additive_mass_kg"], 9),
                "topdown_reference_mass_kg": round(item["topdown_reference_mass_kg"], 9),
                "policies": ";".join(f"{k}={v}" for k, v in item["policies"].most_common()),
            }
        )
    rows.sort(key=lambda r: -safe_float(r["current_mass_kg"]))
    return rows


def policy_summary(record_rows: list[dict[str, Any]], workbook: dict[str, Any], duplicate_primary_rows: int) -> list[dict[str, Any]]:
    total_current = sum(safe_float(row.get("current_mass_kg")) for row in record_rows)
    total_additive = sum(safe_float(row.get("recommended_additive_mass_kg")) for row in record_rows)
    total_reference = sum(safe_float(row.get("topdown_reference_mass_kg")) for row in record_rows)
    exact = sum(safe_float(row.get("current_mass_kg")) for row in record_rows if row.get("mass_policy") == "include_exact_component")
    baseline = sum(
        safe_float(row.get("current_mass_kg"))
        for row in record_rows
        if row.get("mass_policy") in {"include_exact_component", "include_baseline_estimate"}
    )
    review = sum(
        safe_float(row.get("current_mass_kg"))
        for row in record_rows
        if row.get("mass_policy") in {"include_exact_component", "include_baseline_estimate", "include_with_review"}
    )
    wb_total = workbook["total_non_packaging"]
    policies = Counter(clean(row.get("mass_policy")) for row in record_rows)
    return [
        {
            "metric": "workbook_non_packaging_total_kg",
            "value": round(wb_total, 9),
            "interpretation": "Reference total from quantity_material.xlsx excluding packaging materials.",
        },
        {
            "metric": "current_primary_nominal_mass_kg",
            "value": round(total_current, 9),
            "interpretation": "Current primary-path additive sum; overcounts because seat-level aggregate rows are mixed with detailed components.",
        },
        {
            "metric": "exact_component_mass_kg",
            "value": round(exact, 9),
            "interpretation": "Strict exact equipment/material BOM matches only.",
        },
        {
            "metric": "exact_plus_baseline_estimates_kg",
            "value": round(baseline, 9),
            "interpretation": "Recommended conservative component baseline: exact rows plus non-aggregate medium/high family/equipment estimates.",
        },
        {
            "metric": "recommended_additive_with_review_kg",
            "value": round(total_additive, 9),
            "interpretation": "All non-aggregate component masses, including medium review rows; excludes top-down seat aggregate rows.",
        },
        {
            "metric": "topdown_reference_mass_excluded_from_additive_kg",
            "value": round(total_reference, 9),
            "interpretation": "Seat-level/global reference rows retained for checks but not added to component baseline.",
        },
        {
            "metric": "duplicate_identical_primary_rows_collapsed",
            "value": duplicate_primary_rows,
            "interpretation": "Identical primary rows removed before mass audit.",
        },
        {
            "metric": "policy_counts",
            "value": ";".join(f"{k}={v}" for k, v in policies.most_common()),
            "interpretation": "Record count by recommended mass policy.",
        },
    ]


def write_report(
    record_rows: list[dict[str, Any]],
    equipment_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    policy_rows: list[dict[str, Any]],
) -> None:
    policy = {row["metric"]: row["value"] for row in policy_rows}
    wb_total = safe_float(policy.get("workbook_non_packaging_total_kg"))
    current = safe_float(policy.get("current_primary_nominal_mass_kg"))
    conservative = safe_float(policy.get("exact_plus_baseline_estimates_kg"))
    review = safe_float(policy.get("recommended_additive_with_review_kg"))
    overcount = current - wb_total
    lines = [
        "# LCA Mass Re-Audit",
        "",
        f"- Generated at: `{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}`",
        f"- Source workbook: `{WORKBOOK.as_posix()}`",
        f"- Primary path source: `{PRIMARY_PATHS_CSV.as_posix()}`",
        "",
        "## Main Result",
        "",
        f"- Workbook non-packaging mass: **{wb_total:.3f} kg**",
        f"- Current primary nominal mass: **{current:.3f} kg**",
        f"- Apparent overcount vs workbook: **{overcount:.3f} kg**",
        f"- Conservative component baseline: **{conservative:.3f} kg**",
        f"- Additive baseline with review rows: **{review:.3f} kg**",
        "",
        "Interpretation: the current nominal total is not a valid additive mass because top-down `Siège`/global ACV rows coexist with detailed component rows. Those rows should remain as reference/scenario rows, not be summed with the detailed baseline.",
        "",
        "## Recommended Policy",
        "",
        "- Use `exact_plus_baseline_estimates_kg` for conservative nominal simulations.",
        "- Use `recommended_additive_with_review_kg` for exploratory simulations when medium-confidence non-aggregate component rows are acceptable.",
        "- Keep `topdown_reference_only` rows visible, but do not add them to component-level baseline totals.",
        "- Keep `scenario_only_mass` rows out of quantitative baseline unless manually validated.",
        "",
        "## Policy Counts",
        "",
    ]
    counts = Counter(clean(row.get("mass_policy")) for row in record_rows)
    for key, count in counts.most_common():
        mass = sum(safe_float(row.get("current_mass_kg")) for row in record_rows if row.get("mass_policy") == key)
        lines.append(f"- `{key}`: {count} records, current mass {mass:.3f} kg")
    lines.extend(["", "## Families After Re-Audit", ""])
    for row in family_rows:
        lines.append(
            f"- `{row['family']}`: current {safe_float(row['current_mass_kg']):.3f} kg, "
            f"recommended additive {safe_float(row['recommended_additive_mass_kg']):.3f} kg, "
            f"top-down reference {safe_float(row['topdown_reference_mass_kg']):.3f} kg"
        )
    lines.extend(["", "## Largest Equipment Deltas", ""])
    deltas = [
        row for row in equipment_rows if clean(row.get("delta_additive_vs_workbook_kg")) not in {"", "0", "0.0"}
    ]
    deltas.sort(key=lambda r: abs(safe_float(r.get("delta_additive_vs_workbook_kg"))), reverse=True)
    for row in deltas[:12]:
        lines.append(
            f"- `{row['equipment_match']}`: workbook {row['workbook_equipment_mass_kg']} kg, "
            f"recommended additive {row['recommended_additive_mass_kg']} kg, "
            f"delta {row['delta_additive_vs_workbook_kg']} kg ({row['delta_additive_vs_workbook_pct']}%)"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Record audit: `{OUT_RECORDS.as_posix()}`",
            f"- Equipment summary: `{OUT_EQUIPMENT.as_posix()}`",
            f"- Family summary: `{OUT_FAMILIES.as_posix()}`",
            f"- Policy summary: `{OUT_POLICY.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    workbook = workbook_reference()
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    primary_rows, duplicate_primary_rows = collapse_primary(read_csv(PRIMARY_PATHS_CSV))
    record_rows = build_record_rows(primary_rows, data.get("records") or [])
    equipment_rows = equipment_summary(record_rows, workbook)
    family_rows = family_summary(record_rows)
    policy_rows = policy_summary(record_rows, workbook, duplicate_primary_rows)

    write_csv(OUT_RECORDS, record_rows)
    write_csv(OUT_EQUIPMENT, equipment_rows)
    write_csv(OUT_FAMILIES, family_rows)
    write_csv(OUT_POLICY, policy_rows)
    write_report(record_rows, equipment_rows, family_rows, policy_rows)

    print(f"Wrote {OUT_RECORDS}")
    print(f"Wrote {OUT_EQUIPMENT}")
    print(f"Wrote {OUT_FAMILIES}")
    print(f"Wrote {OUT_POLICY}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
