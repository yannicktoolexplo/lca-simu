#!/usr/bin/env python3
"""Nominal baseline simulation for the cleaned aeronautical seat supply graph.

This is the "everything goes well" run: only primary paths are used, duplicate
identical primary paths are collapsed per component, and no disruption is
applied. It produces simple mass and transport flow KPIs.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PATHS_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv"
MASS_POLICY_CSV = BASE_DIR / "output8_GEO_lca_mass_reaudit_records.csv"

OUT_COMPONENTS = BASE_DIR / "output8_GEO_nominal_baseline_component_flows.csv"
OUT_FAMILIES = BASE_DIR / "output8_GEO_nominal_baseline_family_summary.csv"
OUT_SUPPLIERS = BASE_DIR / "output8_GEO_nominal_baseline_supplier_load.csv"
OUT_LANES = BASE_DIR / "output8_GEO_nominal_baseline_lane_flows.csv"
OUT_MODES = BASE_DIR / "output8_GEO_nominal_baseline_transport_modes.csv"
OUT_MD = BASE_DIR / "output8_GEO_nominal_baseline_simulation_report.md"

ROLES = [
    ("T4", "t4", "t4_status"),
    ("T3", "t3", "t3_status"),
    ("T2", "t2", "t2_status"),
    ("T1", "t1", "t1_status"),
    ("OEM", "oem", "oem_status"),
]
EDGES = [
    ("T4->T3", "t4", "t3", "t4_t3_km", "t4_t3_modes"),
    ("T3->T2", "t3", "t2", "t3_t2_km", "t3_t2_modes"),
    ("T2->T1", "t2", "t1", "t2_t1_km", "t2_t1_modes"),
    ("T1->OEM", "t1", "oem", "t1_oem_km", "t1_oem_modes"),
]


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


def primary_route_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        clean(row.get("record_index")),
        clean(row.get("t4")),
        clean(row.get("t3")),
        clean(row.get("t2")),
        clean(row.get("t1")),
        clean(row.get("oem")),
    )


def collapse_primary(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    primary = [row for row in rows if row.get("path_type") == "primary"]
    seen: set[tuple[str, ...]] = set()
    unique: list[dict[str, str]] = []
    duplicates = 0
    for row in primary:
        key = primary_route_key(row)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(row)
    return unique, duplicates


def path_distance(row: dict[str, str]) -> float:
    return sum(safe_float(row.get(edge[3])) for edge in EDGES)


MASS_POLICY = load_mass_policy()


def model_mass(row: dict[str, str]) -> float:
    policy = MASS_POLICY.get(clean(row.get("record_index")))
    if policy:
        return safe_float(policy.get("recommended_additive_mass_kg"))
    return safe_float(row.get("mass_kg"))


def mass_policy_label(row: dict[str, str]) -> str:
    policy = MASS_POLICY.get(clean(row.get("record_index")))
    return clean(policy.get("mass_policy")) if policy else "raw_mass_kg"


def path_modes(row: dict[str, str]) -> set[str]:
    modes: set[str] = set()
    for _, _, _, _, mode_col in EDGES:
        modes.update(part for part in clean(row.get(mode_col)).split("|") if part)
    return modes


def component_rows(primary: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in primary:
        mass = model_mass(row)
        total_distance = path_distance(row)
        rows.append(
            {
                "record_index": row.get("record_index"),
                "system": row.get("system"),
                "component": row.get("component"),
                "family": row.get("family"),
                "mass_kg": round(mass, 6),
                "source_mass_kg": row.get("mass_kg"),
                "mass_policy": mass_policy_label(row),
                "lca_use_class": row.get("lca_use_class"),
                "lca_confidence": row.get("lca_confidence"),
                "readiness": row.get("readiness"),
                "issue_codes": row.get("issue_codes"),
                "total_route_km": round(total_distance, 1),
                "kg_km": round(mass * total_distance, 1),
                "modes": "|".join(sorted(path_modes(row))),
                "t4": row.get("t4"),
                "t3": row.get("t3"),
                "t2": row.get("t2"),
                "t1": row.get("t1"),
                "oem": row.get("oem"),
            }
        )
    rows.sort(key=lambda r: -safe_float(r["kg_km"]))
    return rows


def family_rows(primary: list[dict[str, str]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for row in primary:
        family = clean(row.get("family"))
        mass = model_mass(row)
        distance = path_distance(row)
        item = stats.setdefault(
            family,
            {
                "family": family,
                "component_count": 0,
                "mass_kg": 0.0,
                "kg_km": 0.0,
                "route_km_sum": 0.0,
                "quantitative_ready_count": 0,
                "needs_validation_count": 0,
            },
        )
        item["component_count"] += 1
        item["mass_kg"] += mass
        item["kg_km"] += mass * distance
        item["route_km_sum"] += distance
        if clean(row.get("lca_use_class")) == "quantitative_ready":
            item["quantitative_ready_count"] += 1
        if "needs_validation" in clean(row.get("readiness")):
            item["needs_validation_count"] += 1
    rows = []
    total_mass = sum(item["mass_kg"] for item in stats.values()) or 1.0
    total_kg_km = sum(item["kg_km"] for item in stats.values()) or 1.0
    for item in stats.values():
        rows.append(
            {
                "family": item["family"],
                "component_count": item["component_count"],
                "mass_kg": round(item["mass_kg"], 4),
                "mass_share_pct": round(100 * item["mass_kg"] / total_mass, 1),
                "kg_km": round(item["kg_km"], 1),
                "kg_km_share_pct": round(100 * item["kg_km"] / total_kg_km, 1),
                "avg_route_km": round(item["route_km_sum"] / item["component_count"], 1),
                "quantitative_ready_count": item["quantitative_ready_count"],
                "needs_validation_count": item["needs_validation_count"],
            }
        )
    rows.sort(key=lambda r: -safe_float(r["mass_kg"]))
    return rows


def supplier_rows(primary: list[dict[str, str]]) -> list[dict[str, Any]]:
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for row in primary:
        mass = model_mass(row)
        kg_km = mass * path_distance(row)
        for role, field, status_field in ROLES:
            supplier = clean(row.get(field))
            if not supplier:
                continue
            key = (role, supplier)
            item = stats.setdefault(
                key,
                {
                    "role": role,
                    "supplier": supplier,
                    "status_examples": Counter(),
                    "component_count": 0,
                    "mass_kg": 0.0,
                    "kg_km_context": 0.0,
                    "families": Counter(),
                    "components": [],
                },
            )
            item["component_count"] += 1
            item["mass_kg"] += mass
            item["kg_km_context"] += kg_km
            item["families"][clean(row.get("family"))] += 1
            item["status_examples"][clean(row.get(status_field))] += 1
            if len(item["components"]) < 16:
                item["components"].append(f"{row.get('record_index')}:{row.get('component')}")
    rows = []
    for item in stats.values():
        rows.append(
            {
                "role": item["role"],
                "supplier": item["supplier"],
                "component_count": item["component_count"],
                "mass_kg": round(item["mass_kg"], 4),
                "kg_km_context": round(item["kg_km_context"], 1),
                "families": ";".join(f"{k}={v}" for k, v in item["families"].most_common()),
                "status_examples": ";".join(f"{k}={v}" for k, v in item["status_examples"].most_common() if k),
                "example_components": " | ".join(item["components"]),
            }
        )
    rows.sort(key=lambda r: (-safe_float(r["mass_kg"]), r["role"], r["supplier"]))
    return rows


def lane_rows(primary: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lanes: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    mode_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"mode": "", "segment_count": 0, "mass_kg": 0.0, "kg_km_equal_split": 0.0})
    combo_stats: Counter[str] = Counter()
    for row in primary:
        mass = model_mass(row)
        for edge_name, src_col, dst_col, km_col, mode_col in EDGES:
            src = clean(row.get(src_col))
            dst = clean(row.get(dst_col))
            distance = safe_float(row.get(km_col))
            modes = clean(row.get(mode_col))
            kg_km = mass * distance
            key = (edge_name, src, dst, modes)
            item = lanes.setdefault(
                key,
                {
                    "edge": edge_name,
                    "from_name": src,
                    "to_name": dst,
                    "modes": modes,
                    "component_count": 0,
                    "mass_kg": 0.0,
                    "distance_km": distance,
                    "kg_km": 0.0,
                    "families": Counter(),
                    "components": [],
                },
            )
            item["component_count"] += 1
            item["mass_kg"] += mass
            item["kg_km"] += kg_km
            item["families"][clean(row.get("family"))] += 1
            if len(item["components"]) < 14:
                item["components"].append(f"{row.get('record_index')}:{row.get('component')}")
            combo_stats[modes or "unknown"] += 1
            split_modes = [part for part in modes.split("|") if part] or ["unknown"]
            for mode in split_modes:
                mode_item = mode_stats[mode]
                mode_item["mode"] = mode
                mode_item["segment_count"] += 1
                mode_item["mass_kg"] += mass
                mode_item["kg_km_equal_split"] += kg_km / len(split_modes)
    lane_out = []
    for item in lanes.values():
        lane_out.append(
            {
                "edge": item["edge"],
                "from_name": item["from_name"],
                "to_name": item["to_name"],
                "distance_km": round(item["distance_km"], 1),
                "modes": item["modes"],
                "component_count": item["component_count"],
                "mass_kg": round(item["mass_kg"], 4),
                "kg_km": round(item["kg_km"], 1),
                "families": ";".join(f"{k}={v}" for k, v in item["families"].most_common()),
                "example_components": " | ".join(item["components"]),
            }
        )
    lane_out.sort(key=lambda r: -safe_float(r["kg_km"]))
    mode_out = []
    total_mode_kg_km = sum(item["kg_km_equal_split"] for item in mode_stats.values()) or 1.0
    for item in mode_stats.values():
        mode_out.append(
            {
                "mode": item["mode"],
                "segment_count": item["segment_count"],
                "mass_kg_on_segments": round(item["mass_kg"], 4),
                "kg_km_equal_split": round(item["kg_km_equal_split"], 1),
                "kg_km_equal_split_share_pct": round(100 * item["kg_km_equal_split"] / total_mode_kg_km, 1),
            }
        )
    mode_out.sort(key=lambda r: -safe_float(r["kg_km_equal_split"]))
    return lane_out, mode_out


def write_report(
    primary: list[dict[str, str]],
    duplicate_count: int,
    comp: list[dict[str, Any]],
    fam: list[dict[str, Any]],
    suppliers: list[dict[str, Any]],
    lanes: list[dict[str, Any]],
    modes: list[dict[str, Any]],
) -> None:
    total_mass = sum(safe_float(row["mass_kg"]) for row in comp)
    total_kg_km = sum(safe_float(row["kg_km"]) for row in comp)
    avg_route = sum(safe_float(row["total_route_km"]) for row in comp) / len(comp)
    readiness = Counter(row.get("readiness") for row in primary)
    lca_classes = Counter(row.get("lca_use_class") for row in primary)
    lines = [
        "# Nominal Baseline Simulation",
        "",
        f"- Generated at: `{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}`",
        "- Scenario: `nominal_baseline`, no disruption, primary paths only.",
        f"- Mass policy: recommended additive ACV mass from `{MASS_POLICY_CSV.as_posix()}`.",
        f"- Unique primary component flows: **{len(comp)}**",
        f"- Duplicate identical primary rows collapsed: **{duplicate_count}**",
        f"- Total modeled mass: **{round(total_mass, 4)} kg**",
        f"- Total transport proxy: **{round(total_kg_km, 1)} kg.km**",
        f"- Average route length: **{round(avg_route, 1)} km**",
        "",
        "## Readiness",
        "",
    ]
    for key, count in readiness.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## LCA Classes", ""])
    for key, count in lca_classes.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## Mass By Family", ""])
    for row in fam:
        lines.append(
            f"- `{row['family']}`: {row['mass_kg']} kg ({row['mass_share_pct']}%), "
            f"{row['component_count']} components, kg.km share {row['kg_km_share_pct']}%"
        )
    lines.extend(["", "## Transport Mode Proxy", ""])
    for row in modes:
        lines.append(
            f"- `{row['mode']}`: {row['kg_km_equal_split']} kg.km equal-split "
            f"({row['kg_km_equal_split_share_pct']}%), {row['segment_count']} segments"
        )
    lines.extend(["", "## Top Suppliers By Nominal Mass", ""])
    for row in suppliers[:12]:
        lines.append(
            f"- `{row['role']}` `{row['supplier']}`: {row['mass_kg']} kg, "
            f"{row['component_count']} components, families `{row['families']}`"
        )
    lines.extend(["", "## Top Lanes By kg.km", ""])
    for row in lanes[:12]:
        lines.append(
            f"- `{row['edge']}` {row['from_name']} -> {row['to_name']}: "
            f"{row['kg_km']} kg.km, {row['mass_kg']} kg, {row['distance_km']} km, modes `{row['modes']}`"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Component flows: `{OUT_COMPONENTS.as_posix()}`",
            f"- Family summary: `{OUT_FAMILIES.as_posix()}`",
            f"- Supplier load: `{OUT_SUPPLIERS.as_posix()}`",
            f"- Lane flows: `{OUT_LANES.as_posix()}`",
            f"- Transport modes: `{OUT_MODES.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = read_csv(PATHS_CSV)
    primary, duplicates = collapse_primary(rows)
    comp = component_rows(primary)
    fam = family_rows(primary)
    suppliers = supplier_rows(primary)
    lanes, modes = lane_rows(primary)

    write_csv(OUT_COMPONENTS, comp)
    write_csv(OUT_FAMILIES, fam)
    write_csv(OUT_SUPPLIERS, suppliers)
    write_csv(OUT_LANES, lanes)
    write_csv(OUT_MODES, modes)
    write_report(primary, duplicates, comp, fam, suppliers, lanes, modes)

    print(f"Wrote {OUT_COMPONENTS}")
    print(f"Wrote {OUT_FAMILIES}")
    print(f"Wrote {OUT_SUPPLIERS}")
    print(f"Wrote {OUT_LANES}")
    print(f"Wrote {OUT_MODES}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
