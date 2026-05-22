#!/usr/bin/env python3
"""Very simple topology-based stress simulation for the cleaned seat supply graph.

This is intentionally not a full MRP/capacity simulation. It answers:
- if a primary node is unavailable, which components/mass are impacted?
- is there at least one secondary path that avoids the disrupted node/lane?
- which validation class would gate the fallback path?
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
OUT_SUPPLIER = BASE_DIR / "output8_GEO_simple_stress_supplier_disruptions.csv"
OUT_LANE = BASE_DIR / "output8_GEO_simple_stress_lane_disruptions.csv"
OUT_MODE = BASE_DIR / "output8_GEO_simple_stress_transport_mode_disruptions.csv"
OUT_COMPONENT = BASE_DIR / "output8_GEO_simple_stress_component_impacts.csv"
OUT_MD = BASE_DIR / "output8_GEO_simple_stress_simulation_report.md"

ROLES = ["t4", "t3", "t2", "t1"]
EDGES = [
    ("T4->T3", "t4", "t3", "t4_t3_km", "t4_t3_modes"),
    ("T3->T2", "t3", "t2", "t3_t2_km", "t3_t2_modes"),
    ("T2->T1", "t2", "t1", "t2_t1_km", "t2_t1_modes"),
    ("T1->OEM", "t1", "oem", "t1_oem_km", "t1_oem_modes"),
]
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


def path_nodes(row: dict[str, str]) -> set[str]:
    return {clean(row.get(role)) for role in ROLES if clean(row.get(role))}


def edge_key(row: dict[str, str], edge: tuple[str, str, str, str, str]) -> tuple[str, str, str]:
    edge_name, src_role, dst_role, _, _ = edge
    return (edge_name, clean(row.get(src_role)), clean(row.get(dst_role)))


def path_edges(row: dict[str, str]) -> set[tuple[str, str, str]]:
    return {edge_key(row, edge) for edge in EDGES if clean(row.get(edge[1])) and clean(row.get(edge[2]))}


def mode_set(row: dict[str, str]) -> set[str]:
    modes: set[str] = set()
    for _, _, _, _, mode_col in EDGES:
        modes.update(part for part in clean(row.get(mode_col)).split("|") if part)
    return modes


MASS_POLICY = load_mass_policy()


def model_mass(row: dict[str, str]) -> float:
    policy = MASS_POLICY.get(clean(row.get("record_index")))
    if policy:
        return safe_float(policy.get("recommended_additive_mass_kg"))
    return safe_float(row.get("mass_kg"))


def best_class(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "no_topology_fallback"
    return min((clean(row.get("switch_class")) for row in rows), key=lambda c: CLASS_RANK.get(c, 99))


def class_counts(rows: list[dict[str, str]]) -> str:
    counts = Counter(clean(row.get("switch_class")) for row in rows)
    return ";".join(f"{key}={value}" for key, value in counts.most_common())


def summarize_impacted_records(
    impacted: list[dict[str, str]],
    secondary_by_record: dict[str, list[dict[str, str]]],
    *,
    avoid_node: str | None = None,
    avoid_edge: tuple[str, str, str] | None = None,
    avoid_mode: str | None = None,
) -> dict[str, Any]:
    impacted_records = {clean(row.get("record_index")): row for row in impacted}
    impacted_mass = sum(model_mass(row) for row in impacted_records.values())
    covered = 0
    pair_required = 0
    no_fallback = 0
    class_counter: Counter[str] = Counter()
    examples: list[str] = []
    component_rows: list[dict[str, Any]] = []

    for record_index, primary in impacted_records.items():
        candidates = []
        for candidate in secondary_by_record.get(record_index, []):
            if avoid_node and avoid_node in path_nodes(candidate):
                continue
            if avoid_edge and avoid_edge in path_edges(candidate):
                continue
            if avoid_mode and avoid_mode in mode_set(candidate):
                continue
            candidates.append(candidate)
        cls = best_class(candidates)
        if candidates:
            covered += 1
            if cls == "candidate_requires_t1_t2_pairing":
                pair_required += 1
            class_counter[cls] += 1
        else:
            no_fallback += 1
            class_counter["no_topology_fallback"] += 1
        if len(examples) < 8:
            examples.append(f"{record_index}:{clean(primary.get('component'))}")
        component_rows.append(
            {
                "record_index": record_index,
                "system": primary.get("system"),
                "component": primary.get("component"),
                "family": primary.get("family"),
                "mass_kg": round(model_mass(primary), 6),
                "source_mass_kg": primary.get("mass_kg"),
                "fallback_path_count": len(candidates),
                "best_fallback_class": cls,
                "fallback_class_counts": class_counts(candidates),
            }
        )

    return {
        "impacted_component_count": len(impacted_records),
        "impacted_mass_kg": round(impacted_mass, 4),
        "components_with_topology_fallback": covered,
        "components_without_topology_fallback": no_fallback,
        "components_requiring_t1_t2_pair_switch": pair_required,
        "fallback_coverage_pct": round(100 * covered / len(impacted_records), 1) if impacted_records else 0.0,
        "best_fallback_classes": ";".join(f"{key}={value}" for key, value in class_counter.most_common()),
        "example_components": " | ".join(examples),
        "_component_rows": component_rows,
    }


def build_supplier_scenarios(
    primary: list[dict[str, str]], secondary_by_record: dict[str, list[dict[str, str]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenarios: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in primary:
        for role in ROLES:
            node = clean(row.get(role))
            if node:
                scenarios[(role.upper(), node)].append(row)

    out: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    for (role, supplier), impacted in scenarios.items():
        summary = summarize_impacted_records(impacted, secondary_by_record, avoid_node=supplier)
        component_rows.extend(
            {
                **row,
                "scenario_type": "supplier_disruption",
                "scenario_id": f"supplier::{role}::{supplier}",
                "disrupted_role": role,
                "disrupted_supplier": supplier,
            }
            for row in summary.pop("_component_rows")
        )
        out.append(
            {
                "scenario_type": "supplier_disruption",
                "disrupted_role": role,
                "disrupted_supplier": supplier,
                **summary,
            }
        )
    out.sort(key=lambda r: (-safe_float(r["impacted_mass_kg"]), -safe_float(r["impacted_component_count"])))
    return out, component_rows


def build_lane_scenarios(
    primary: list[dict[str, str]], secondary_by_record: dict[str, list[dict[str, str]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scenarios: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    lane_meta: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in primary:
        for edge in EDGES:
            key = edge_key(row, edge)
            edge_name, _, _, km_col, mode_col = edge
            scenarios[key].append(row)
            lane_meta[key] = {
                "edge": edge_name,
                "from_name": key[1],
                "to_name": key[2],
                "distance_km": safe_float(row.get(km_col)),
                "modes": row.get(mode_col),
            }
    out: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    for key, impacted in scenarios.items():
        summary = summarize_impacted_records(impacted, secondary_by_record, avoid_edge=key)
        meta = lane_meta[key]
        component_rows.extend(
            {
                **row,
                "scenario_type": "lane_disruption",
                "scenario_id": f"lane::{key[0]}::{key[1]}->{key[2]}",
                "disrupted_edge": key[0],
                "from_name": key[1],
                "to_name": key[2],
            }
            for row in summary.pop("_component_rows")
        )
        out.append({"scenario_type": "lane_disruption", **meta, **summary})
    out.sort(key=lambda r: (-safe_float(r["impacted_mass_kg"]), -safe_float(r["distance_km"])))
    return out, component_rows


def build_mode_scenarios(
    primary: list[dict[str, str]], secondary_by_record: dict[str, list[dict[str, str]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    modes = sorted({mode for row in primary for mode in mode_set(row)})
    out: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    for mode in modes:
        impacted = [row for row in primary if mode in mode_set(row)]
        summary = summarize_impacted_records(impacted, secondary_by_record, avoid_mode=mode)
        component_rows.extend(
            {
                **row,
                "scenario_type": "transport_mode_disruption",
                "scenario_id": f"mode::{mode}",
                "disrupted_mode": mode,
            }
            for row in summary.pop("_component_rows")
        )
        out.append({"scenario_type": "transport_mode_disruption", "disrupted_mode": mode, **summary})
    out.sort(key=lambda r: (-safe_float(r["impacted_mass_kg"]), r["disrupted_mode"]))
    return out, component_rows


def write_report(
    supplier_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    mode_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
) -> None:
    lines = [
        "# Simple Supply Stress Simulation",
        "",
        f"- Generated at: `{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}`",
        "- Model: static topology only, no inventory, no capacity, no dynamic MRP.",
        f"- Mass policy: recommended additive ACV mass from `{MASS_POLICY_CSV.as_posix()}`.",
        "- Fallback means: at least one secondary path avoids the disrupted node/lane/mode.",
        "- Fallback is not automatically qualified; its validation class is retained.",
        "",
        "## Summary",
        "",
        f"- Supplier disruption scenarios: **{len(supplier_rows)}**",
        f"- Lane disruption scenarios: **{len(lane_rows)}**",
        f"- Transport mode scenarios: **{len(mode_rows)}**",
        f"- Component impact rows: **{len(component_rows)}**",
        "",
        "## Top Supplier Disruptions By Mass",
        "",
    ]
    for row in supplier_rows[:12]:
        lines.append(
            f"- `{row['disrupted_role']}` `{row['disrupted_supplier']}`: "
            f"{row['impacted_component_count']} components, {row['impacted_mass_kg']} kg, "
            f"fallback coverage {row['fallback_coverage_pct']}%, classes `{row['best_fallback_classes']}`"
        )
    lines.extend(["", "## Top Lane Disruptions By Mass", ""])
    for row in lane_rows[:12]:
        lines.append(
            f"- `{row['edge']}` {row['from_name']} -> {row['to_name']}: "
            f"{row['impacted_component_count']} components, {row['impacted_mass_kg']} kg, "
            f"fallback coverage {row['fallback_coverage_pct']}%, modes `{row['modes']}`"
        )
    lines.extend(["", "## Transport Mode Shocks", ""])
    for row in mode_rows:
        lines.append(
            f"- `{row['disrupted_mode']}` unavailable: {row['impacted_component_count']} components, "
            f"{row['impacted_mass_kg']} kg, fallback coverage {row['fallback_coverage_pct']}%, "
            f"classes `{row['best_fallback_classes']}`"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Supplier scenarios: `{OUT_SUPPLIER.as_posix()}`",
            f"- Lane scenarios: `{OUT_LANE.as_posix()}`",
            f"- Mode scenarios: `{OUT_MODE.as_posix()}`",
            f"- Component impacts: `{OUT_COMPONENT.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    paths = read_csv(PATHS_CSV)
    switches = read_csv(SWITCH_CSV)
    primary = [row for row in paths if row.get("path_type") == "primary"]
    secondary_by_record: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in switches:
        if clean(row.get("switch_verdict")) == "blocked":
            continue
        secondary_by_record[clean(row.get("record_index"))].append(row)

    supplier_rows, supplier_components = build_supplier_scenarios(primary, secondary_by_record)
    lane_rows, lane_components = build_lane_scenarios(primary, secondary_by_record)
    mode_rows, mode_components = build_mode_scenarios(primary, secondary_by_record)
    component_rows = supplier_components + lane_components + mode_components

    write_csv(OUT_SUPPLIER, supplier_rows)
    write_csv(OUT_LANE, lane_rows)
    write_csv(OUT_MODE, mode_rows)
    write_csv(OUT_COMPONENT, component_rows)
    write_report(supplier_rows, lane_rows, mode_rows, component_rows)

    print(f"Wrote {OUT_SUPPLIER}")
    print(f"Wrote {OUT_LANE}")
    print(f"Wrote {OUT_MODE}")
    print(f"Wrote {OUT_COMPONENT}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
