#!/usr/bin/env python3
"""Experimental simulation over secondary candidate paths.

This is not procurement truth. It lets the model "run" all secondary candidates
as topology scenarios, then compares them to the primary baseline by component.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PATHS_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv"
SWITCH_CSV = BASE_DIR / "output8_GEO_secondary_switch_path_audit.csv"
MASS_POLICY_CSV = BASE_DIR / "output8_GEO_lca_mass_reaudit_records.csv"

OUT_PATHS = BASE_DIR / "output8_GEO_secondary_test_candidate_path_flows.csv"
OUT_COMPONENTS = BASE_DIR / "output8_GEO_secondary_test_component_summary.csv"
OUT_CLASSES = BASE_DIR / "output8_GEO_secondary_test_switch_class_summary.csv"
OUT_SUPPLIERS = BASE_DIR / "output8_GEO_secondary_test_supplier_exposure.csv"
OUT_MD = BASE_DIR / "output8_GEO_secondary_test_simulation_report.md"

DISTANCE_COLS = ["t4_t3_km", "t3_t2_km", "t2_t1_km", "t1_oem_km"]
MODE_COLS = ["t4_t3_modes", "t3_t2_modes", "t2_t1_modes", "t1_oem_modes"]
ROLES = ["t4", "t3", "t2", "t1"]
CLASS_RANK = {
    "candidate_requires_allocation_and_qualification": 1,
    "candidate_requires_t1_t2_pairing": 2,
    "candidate_requires_material_certificate": 3,
    "candidate_requires_material_source": 4,
    "candidate_requires_site_validation": 5,
    "candidate_scenario_only_mass_review": 6,
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_mass_policy() -> dict[str, dict[str, str]]:
    if not MASS_POLICY_CSV.exists():
        return {}
    return {clean(row.get("record_index")): row for row in read_csv(MASS_POLICY_CSV)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def route_km(row: dict[str, str]) -> float:
    return sum(safe_float(row.get(col)) for col in DISTANCE_COLS)


def modes(row: dict[str, str]) -> str:
    values: set[str] = set()
    for col in MODE_COLS:
        values.update(part for part in clean(row.get(col)).split("|") if part)
    return "|".join(sorted(values))


MASS_POLICY = load_mass_policy()


def model_mass(row: dict[str, str]) -> float:
    policy = MASS_POLICY.get(clean(row.get("record_index")))
    if policy:
        return safe_float(policy.get("recommended_additive_mass_kg"))
    return safe_float(row.get("mass_kg"))


def mass_policy_label(row: dict[str, str]) -> str:
    policy = MASS_POLICY.get(clean(row.get("record_index")))
    return clean(policy.get("mass_policy")) if policy else "raw_mass_kg"


def primary_routes(paths: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    primary: dict[str, dict[str, Any]] = {}
    for row in paths:
        if clean(row.get("path_type")) != "primary":
            continue
        record_index = clean(row.get("record_index"))
        if record_index in primary:
            continue
        distance = route_km(row)
        mass = model_mass(row)
        primary[record_index] = {
            "record_index": record_index,
            "path_id": row.get("path_id"),
            "route_km": distance,
            "kg_km": mass * distance,
            "mass_kg": mass,
            "t4": row.get("t4"),
            "t3": row.get("t3"),
            "t2": row.get("t2"),
            "t1": row.get("t1"),
        }
    return primary


def test_bucket(switch_class: str) -> str:
    if switch_class == "candidate_requires_allocation_and_qualification":
        return "preferred_topology_test"
    if switch_class == "candidate_requires_t1_t2_pairing":
        return "paired_t1_t2_test"
    if switch_class == "candidate_requires_material_certificate":
        return "material_certificate_test"
    if switch_class in {"candidate_requires_material_source", "candidate_requires_site_validation"}:
        return "source_or_site_review_test"
    if switch_class == "candidate_scenario_only_mass_review":
        return "mass_review_only_test"
    return "other_validation_test"


def candidate_path_rows(paths: list[dict[str, str]], switches: list[dict[str, str]]) -> list[dict[str, Any]]:
    switch_by_path = {clean(row.get("path_id")): row for row in switches}
    primaries = primary_routes(paths)
    rows: list[dict[str, Any]] = []
    for row in paths:
        if clean(row.get("path_type")) != "secondary_candidate":
            continue
        sw = switch_by_path.get(clean(row.get("path_id")), {})
        if clean(sw.get("switch_verdict")) == "blocked":
            continue
        record_index = clean(row.get("record_index"))
        mass = model_mass(row)
        distance = route_km(row)
        kg_km = mass * distance
        primary = primaries.get(record_index, {})
        primary_kg_km = safe_float(primary.get("kg_km"))
        primary_route_km = safe_float(primary.get("route_km"))
        switch_class = clean(sw.get("switch_class")) or "unknown"
        rows.append(
            {
                "record_index": record_index,
                "system": row.get("system"),
                "component": row.get("component"),
                "family": row.get("family"),
                "mass_kg": round(mass, 6),
                "source_mass_kg": row.get("mass_kg"),
                "mass_policy": mass_policy_label(row),
                "lca_use_class": row.get("lca_use_class"),
                "path_id": row.get("path_id"),
                "switch_class": switch_class,
                "test_bucket": test_bucket(switch_class),
                "class_rank": CLASS_RANK.get(switch_class, 99),
                "route_km": round(distance, 1),
                "kg_km": round(kg_km, 1),
                "primary_route_km": round(primary_route_km, 1),
                "primary_kg_km": round(primary_kg_km, 1),
                "delta_route_km_vs_primary": round(distance - primary_route_km, 1),
                "delta_kg_km_vs_primary": round(kg_km - primary_kg_km, 1),
                "delta_kg_km_pct_vs_primary": round(100 * safe_div(kg_km - primary_kg_km, primary_kg_km), 1),
                "modes": modes(row),
                "t4": row.get("t4"),
                "t3": row.get("t3"),
                "t2": row.get("t2"),
                "t1": row.get("t1"),
                "issue_codes": row.get("issue_codes"),
            }
        )
    rows.sort(key=lambda r: (int(r["class_rank"]), safe_float(r["kg_km"])))
    return rows


def component_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_record[clean(row.get("record_index"))].append(row)
    out: list[dict[str, Any]] = []
    for record_index, items in by_record.items():
        items_sorted_by_rank = sorted(items, key=lambda r: (int(r["class_rank"]), safe_float(r["kg_km"])))
        items_sorted_by_distance = sorted(items, key=lambda r: safe_float(r["kg_km"]))
        best = items_sorted_by_rank[0]
        shortest = items_sorted_by_distance[0]
        count_by_class = Counter(clean(row.get("switch_class")) for row in items)
        lower_kgkm = sum(1 for row in items if safe_float(row.get("delta_kg_km_vs_primary")) < 0)
        much_lower_kgkm = sum(1 for row in items if safe_float(row.get("delta_kg_km_pct_vs_primary")) <= -20)
        pair_required = sum(1 for row in items if row.get("switch_class") == "candidate_requires_t1_t2_pairing")
        out.append(
            {
                "record_index": record_index,
                "system": best.get("system"),
                "component": best.get("component"),
                "family": best.get("family"),
                "mass_kg": best.get("mass_kg"),
                "candidate_count": len(items),
                "preferred_topology_count": count_by_class.get("candidate_requires_allocation_and_qualification", 0),
                "paired_t1_t2_count": pair_required,
                "material_certificate_count": count_by_class.get("candidate_requires_material_certificate", 0),
                "mass_review_only_count": count_by_class.get("candidate_scenario_only_mass_review", 0),
                "lower_kgkm_than_primary_count": lower_kgkm,
                "at_least_20pct_lower_kgkm_count": much_lower_kgkm,
                "best_validation_path_id": best.get("path_id"),
                "best_validation_class": best.get("switch_class"),
                "best_validation_kg_km": best.get("kg_km"),
                "best_validation_delta_pct": best.get("delta_kg_km_pct_vs_primary"),
                "shortest_path_id": shortest.get("path_id"),
                "shortest_class": shortest.get("switch_class"),
                "shortest_kg_km": shortest.get("kg_km"),
                "shortest_delta_pct": shortest.get("delta_kg_km_pct_vs_primary"),
                "class_counts": ";".join(f"{k}={v}" for k, v in count_by_class.most_common()),
            }
        )
    out.sort(key=lambda r: (-safe_float(r["mass_kg"]), -safe_float(r["candidate_count"])))
    return out


def class_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[clean(row.get("switch_class"))].append(row)
    out: list[dict[str, Any]] = []
    for cls, items in groups.items():
        kg_km = sum(safe_float(row.get("kg_km")) for row in items)
        delta = sum(safe_float(row.get("delta_kg_km_vs_primary")) for row in items)
        out.append(
            {
                "switch_class": cls,
                "test_bucket": test_bucket(cls),
                "path_count": len(items),
                "component_count": len({row.get("record_index") for row in items}),
                "mass_kg_scenario_sum": round(sum(safe_float(row.get("mass_kg")) for row in items), 4),
                "kg_km_scenario_sum": round(kg_km, 1),
                "avg_delta_kg_km_vs_primary": round(safe_div(delta, len(items)), 1),
                "lower_kgkm_than_primary_count": sum(1 for row in items if safe_float(row.get("delta_kg_km_vs_primary")) < 0),
            }
        )
    out.sort(key=lambda r: CLASS_RANK.get(clean(r["switch_class"]), 99))
    return out


def supplier_exposure(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        for role in ROLES:
            supplier = clean(row.get(role))
            if not supplier:
                continue
            key = (role.upper(), supplier)
            item = stats.setdefault(
                key,
                {
                    "role": role.upper(),
                    "supplier": supplier,
                    "candidate_path_count": 0,
                    "component_ids": set(),
                    "mass_kg_scenario_sum": 0.0,
                    "kg_km_scenario_sum": 0.0,
                    "classes": Counter(),
                    "families": Counter(),
                },
            )
            item["candidate_path_count"] += 1
            item["component_ids"].add(row.get("record_index"))
            item["mass_kg_scenario_sum"] += safe_float(row.get("mass_kg"))
            item["kg_km_scenario_sum"] += safe_float(row.get("kg_km"))
            item["classes"][clean(row.get("switch_class"))] += 1
            item["families"][clean(row.get("family"))] += 1
    out: list[dict[str, Any]] = []
    for item in stats.values():
        out.append(
            {
                "role": item["role"],
                "supplier": item["supplier"],
                "candidate_path_count": item["candidate_path_count"],
                "component_count": len(item["component_ids"]),
                "mass_kg_scenario_sum": round(item["mass_kg_scenario_sum"], 4),
                "kg_km_scenario_sum": round(item["kg_km_scenario_sum"], 1),
                "class_counts": ";".join(f"{k}={v}" for k, v in item["classes"].most_common()),
                "families": ";".join(f"{k}={v}" for k, v in item["families"].most_common()),
            }
        )
    out.sort(key=lambda r: (-safe_float(r["candidate_path_count"]), -safe_float(r["mass_kg_scenario_sum"])))
    return out


def write_report(paths: list[dict[str, Any]], components: list[dict[str, Any]], classes: list[dict[str, Any]], suppliers: list[dict[str, Any]]) -> None:
    candidate_components = len({row["record_index"] for row in paths})
    lower_components = sum(1 for row in components if safe_float(row.get("lower_kgkm_than_primary_count")) > 0)
    preferred_components = sum(1 for row in components if safe_float(row.get("preferred_topology_count")) > 0)
    paired_components = sum(1 for row in components if safe_float(row.get("paired_t1_t2_count")) > 0)
    lines = [
        "# Secondary Candidate Test Simulation",
        "",
        f"- Generated at: `{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}`",
        "- Scenario: secondary candidates as topology-only test alternatives.",
        f"- Mass policy: recommended additive ACV mass from `{MASS_POLICY_CSV.as_posix()}`.",
        "- Important: candidate mass is counted once per scenario path; totals are scenario-universe metrics, not physical BOM totals.",
        "",
        "## Summary",
        "",
        f"- Secondary candidate paths tested: **{len(paths)}**",
        f"- Components with at least one secondary candidate: **{candidate_components}**",
        f"- Components with a preferred topology candidate: **{preferred_components}**",
        f"- Components requiring at least one paired T1/T2 option: **{paired_components}**",
        f"- Components with at least one lower kg.km candidate than primary: **{lower_components}**",
        "",
        "## Switch Classes",
        "",
    ]
    for row in classes:
        lines.append(
            f"- `{row['switch_class']}`: {row['path_count']} paths, "
            f"{row['component_count']} components, lower kg.km count {row['lower_kgkm_than_primary_count']}"
        )
    lines.extend(["", "## Top Components By Candidate Count", ""])
    for row in sorted(components, key=lambda r: -int(r["candidate_count"]))[:14]:
        lines.append(
            f"- record `{row['record_index']}` `{row['component']}`: {row['candidate_count']} candidates, "
            f"best `{row['best_validation_class']}` delta {row['best_validation_delta_pct']}%, "
            f"shortest `{row['shortest_class']}` delta {row['shortest_delta_pct']}%"
        )
    lines.extend(["", "## Top Supplier Exposure In Secondary Universe", ""])
    for row in suppliers[:12]:
        lines.append(
            f"- `{row['role']}` `{row['supplier']}`: {row['candidate_path_count']} candidate paths, "
            f"{row['component_count']} components, classes `{row['class_counts']}`"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Candidate paths: `{OUT_PATHS.as_posix()}`",
            f"- Component summary: `{OUT_COMPONENTS.as_posix()}`",
            f"- Switch class summary: `{OUT_CLASSES.as_posix()}`",
            f"- Supplier exposure: `{OUT_SUPPLIERS.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    paths = read_csv(PATHS_CSV)
    switches = read_csv(SWITCH_CSV)
    path_rows = candidate_path_rows(paths, switches)
    component_rows = component_summary(path_rows)
    class_rows = class_summary(path_rows)
    supplier_rows = supplier_exposure(path_rows)

    write_csv(OUT_PATHS, path_rows)
    write_csv(OUT_COMPONENTS, component_rows)
    write_csv(OUT_CLASSES, class_rows)
    write_csv(OUT_SUPPLIERS, supplier_rows)
    write_report(path_rows, component_rows, class_rows, supplier_rows)

    print(f"Wrote {OUT_PATHS}")
    print(f"Wrote {OUT_COMPONENTS}")
    print(f"Wrote {OUT_CLASSES}")
    print(f"Wrote {OUT_SUPPLIERS}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
