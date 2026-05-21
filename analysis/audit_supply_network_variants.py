#!/usr/bin/env python3
"""
Audit supply-network variants from Tier 4 to OEM.

Inputs:
  analysis/output8_GEO_normalized_final_corrected.json

Outputs:
  - primary-only network nodes/edges
  - all-enabled network nodes/edges
  - component/tier gap audit
  - supplier switch options
  - local-restructuring scenario summary
  - Markdown synthesis
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_corrected.json"
OUT_MD = ROOT / "analysis" / "output8_GEO_supply_network_audit.md"
OUT_PRIMARY_NODES = ROOT / "analysis" / "output8_GEO_network_primary_nodes.csv"
OUT_PRIMARY_EDGES = ROOT / "analysis" / "output8_GEO_network_primary_edges.csv"
OUT_ALL_NODES = ROOT / "analysis" / "output8_GEO_network_all_nodes.csv"
OUT_ALL_EDGES = ROOT / "analysis" / "output8_GEO_network_all_edges.csv"
OUT_GAPS = ROOT / "analysis" / "output8_GEO_network_component_gaps.csv"
OUT_REDUNDANCY = ROOT / "analysis" / "output8_GEO_network_component_redundancy.csv"
OUT_SWITCHES = ROOT / "analysis" / "output8_GEO_supplier_switch_options.csv"
OUT_SCENARIOS = ROOT / "analysis" / "output8_GEO_restructuring_scenarios.csv"

ROLES = ["tier4_raw_material", "tier3_first_transformation", "tier2_second_transformation", "tier1", "oem"]
ROLE_LABELS = {
    "tier4_raw_material": "Tier 4 raw material",
    "tier3_first_transformation": "Tier 3 first transformation",
    "tier2_second_transformation": "Tier 2 second transformation",
    "tier1": "Tier 1",
    "oem": "OEM / final integrator",
}
EUROPE_COUNTRIES = {
    "Austria",
    "Belgium",
    "Czech Republic",
    "Denmark",
    "Finland",
    "France",
    "Germany",
    "Ireland",
    "Italy",
    "Lithuania",
    "Luxembourg",
    "Netherlands",
    "Norway",
    "Poland",
    "Portugal",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
}
LOCAL_COUNTRY = "France"


def numeric(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def haversine_km(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> float | None:
    a_lat = numeric(lat1)
    a_lon = numeric(lon1)
    b_lat = numeric(lat2)
    b_lon = numeric(lon2)
    if a_lat is None or a_lon is None or b_lat is None or b_lon is None:
        return None
    radius = 6371.0
    phi1 = math.radians(a_lat)
    phi2 = math.radians(b_lat)
    d_phi = math.radians(b_lat - a_lat)
    d_lambda = math.radians(b_lon - a_lon)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def region(country: str | None) -> str:
    if not country:
        return "unknown"
    if country == LOCAL_COUNTRY:
        return "France"
    if country in EUROPE_COUNTRIES:
        return "Europe_non_FR"
    return "Outside_Europe"


def supplier_key(supplier: dict[str, Any]) -> str:
    return str(supplier.get("site_id") or f"{supplier.get('supplier_id') or supplier.get('name')}@{supplier.get('location')}")


def clean_name(value: Any) -> str:
    return str(value or "").strip()


def suppliers_by_role(record: dict[str, Any], variant: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    for supplier in record.get("suppliers") or []:
        role = supplier.get("role_hint")
        if role in grouped:
            if variant == "all" or supplier.get("is_primary"):
                grouped[role].append(supplier)
    for supplier in record.get("oem_sites") or []:
        if variant == "all" or supplier.get("is_primary"):
            grouped["oem"].append(supplier)
    return grouped


def node_row(supplier: dict[str, Any], role: str, variant: str) -> dict[str, Any]:
    country = clean_name(supplier.get("location"))
    return {
        "variant": variant,
        "node_id": supplier_key(supplier),
        "supplier": clean_name(supplier.get("name")),
        "role_hint": role,
        "country": country,
        "region": region(country),
        "lat": supplier.get("lat", ""),
        "lon": supplier.get("lon", ""),
        "is_primary": bool(supplier.get("is_primary")),
        "supplier_status": supplier.get("supplier_status", ""),
        "source_ids": ";".join(supplier.get("source_ids") or []),
        "geocode_status": supplier.get("geocode_status", ""),
    }


def edge_row(
    record_index: int,
    record: dict[str, Any],
    from_role: str,
    to_role: str,
    src: dict[str, Any],
    dst: dict[str, Any],
    variant: str,
) -> dict[str, Any]:
    distance = haversine_km(src.get("lat"), src.get("lon"), dst.get("lat"), dst.get("lon"))
    mass = numeric(record.get("mass_kg")) or 0.0
    src_country = clean_name(src.get("location"))
    dst_country = clean_name(dst.get("location"))
    return {
        "variant": variant,
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "mass_kg": mass,
        "mass_confidence": record.get("mass_confidence", ""),
        "from_role": from_role,
        "to_role": to_role,
        "from_supplier": clean_name(src.get("name")),
        "to_supplier": clean_name(dst.get("name")),
        "from_node_id": supplier_key(src),
        "to_node_id": supplier_key(dst),
        "from_country": src_country,
        "to_country": dst_country,
        "from_region": region(src_country),
        "to_region": region(dst_country),
        "distance_km": "" if distance is None else round(distance, 3),
        "mass_distance_kg_km": "" if distance is None else round(distance * mass, 3),
        "edge_scope": "intra_country" if src_country and src_country == dst_country else "cross_country",
    }


def build_variant(records: list[dict[str, Any]], variant: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        grouped = suppliers_by_role(record, variant)
        present = {role: bool(grouped[role]) for role in ROLES}
        for role in ROLES:
            for supplier in grouped[role]:
                nodes.setdefault(supplier_key(supplier), node_row(supplier, role, variant))
        missing_roles = [role for role in ROLES if not present[role]]
        if missing_roles:
            gaps.append(
                {
                    "variant": variant,
                    "record_index": record_index,
                    "system": record.get("system", ""),
                    "component": record.get("component", ""),
                    "mass_kg": record.get("mass_kg", ""),
                    "missing_roles": ";".join(missing_roles),
                    "present_roles": ";".join(role for role in ROLES if present[role]),
                    "tier4_count": len(grouped["tier4_raw_material"]),
                    "tier3_count": len(grouped["tier3_first_transformation"]),
                    "tier2_count": len(grouped["tier2_second_transformation"]),
                    "tier1_count": len(grouped["tier1"]),
                    "oem_count": len(grouped["oem"]),
                }
            )
        for from_role, to_role in zip(ROLES, ROLES[1:]):
            if not grouped[from_role] or not grouped[to_role]:
                continue
            for src in grouped[from_role]:
                for dst in grouped[to_role]:
                    edges.append(edge_row(record_index, record, from_role, to_role, src, dst, variant))
    return list(nodes.values()), edges, gaps


def edge_distance_stats(edges: list[dict[str, Any]]) -> dict[str, Any]:
    distances = [float(edge["distance_km"]) for edge in edges if edge["distance_km"] != ""]
    mass_distances = [float(edge["mass_distance_kg_km"]) for edge in edges if edge["mass_distance_kg_km"] != ""]
    return {
        "edges": len(edges),
        "edges_with_distance": len(distances),
        "avg_distance_km": statistics.mean(distances) if distances else None,
        "median_distance_km": statistics.median(distances) if distances else None,
        "p90_distance_km": statistics.quantiles(distances, n=10)[8] if len(distances) >= 10 else None,
        "total_mass_distance_kg_km": sum(mass_distances),
    }


def component_redundancy(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        grouped_all = suppliers_by_role(record, "all")
        grouped_primary = suppliers_by_role(record, "primary")
        counts = {role: len(grouped_all[role]) for role in ROLES}
        primary_counts = {role: len(grouped_primary[role]) for role in ROLES}
        min_candidates = min(counts[role] for role in ROLES if role != "oem")
        weak_roles = [role for role in ROLES[:-1] if counts[role] <= 1]
        rows.append(
            {
                "record_index": record_index,
                "system": record.get("system", ""),
                "component": record.get("component", ""),
                "mass_kg": record.get("mass_kg", ""),
                "mass_confidence": record.get("mass_confidence", ""),
                "tier4_candidates": counts["tier4_raw_material"],
                "tier3_candidates": counts["tier3_first_transformation"],
                "tier2_candidates": counts["tier2_second_transformation"],
                "tier1_candidates": counts["tier1"],
                "oem_candidates": counts["oem"],
                "tier4_primary": primary_counts["tier4_raw_material"],
                "tier3_primary": primary_counts["tier3_first_transformation"],
                "tier2_primary": primary_counts["tier2_second_transformation"],
                "tier1_primary": primary_counts["tier1"],
                "weak_roles": ";".join(weak_roles),
                "minimum_non_oem_candidates": min_candidates,
            }
        )
    return rows


def nearest_downstream(record: dict[str, Any], role: str, supplier: dict[str, Any], downstream_variant: str = "primary") -> tuple[float | None, str, str]:
    grouped = suppliers_by_role(record, downstream_variant)
    role_index = ROLES.index(role)
    for downstream_role in ROLES[role_index + 1 :]:
        candidates = grouped[downstream_role]
        if not candidates:
            continue
        distances: list[tuple[float, dict[str, Any]]] = []
        for candidate in candidates:
            distance = haversine_km(supplier.get("lat"), supplier.get("lon"), candidate.get("lat"), candidate.get("lon"))
            if distance is not None:
                distances.append((distance, candidate))
        if distances:
            distance, best = min(distances, key=lambda item: item[0])
            return distance, clean_name(best.get("name")), downstream_role
    return None, "", ""


def switch_options(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        grouped_all = suppliers_by_role(record, "all")
        grouped_primary = suppliers_by_role(record, "primary")
        for role in ROLES[:-1]:
            primaries = grouped_primary[role]
            primary = primaries[0] if primaries else None
            primary_distance = None
            primary_downstream = ""
            primary_downstream_role = ""
            if primary is not None:
                primary_distance, primary_downstream, primary_downstream_role = nearest_downstream(record, role, primary, "primary")
            for supplier in grouped_all[role]:
                if supplier.get("is_primary"):
                    continue
                alt_distance, downstream_supplier, downstream_role = nearest_downstream(record, role, supplier, "primary")
                delta = None
                if alt_distance is not None and primary_distance is not None:
                    delta = alt_distance - primary_distance
                supplier_country = clean_name(supplier.get("location"))
                primary_country = clean_name(primary.get("location")) if primary else ""
                rows.append(
                    {
                        "record_index": record_index,
                        "system": record.get("system", ""),
                        "component": record.get("component", ""),
                        "mass_kg": record.get("mass_kg", ""),
                        "role_hint": role,
                        "primary_supplier": clean_name(primary.get("name")) if primary else "",
                        "primary_country": primary_country,
                        "primary_region": region(primary_country),
                        "primary_distance_to_downstream_km": "" if primary_distance is None else round(primary_distance, 3),
                        "alternate_supplier": clean_name(supplier.get("name")),
                        "alternate_country": supplier_country,
                        "alternate_region": region(supplier_country),
                        "alternate_distance_to_downstream_km": "" if alt_distance is None else round(alt_distance, 3),
                        "distance_delta_vs_primary_km": "" if delta is None else round(delta, 3),
                        "downstream_supplier": downstream_supplier or primary_downstream,
                        "downstream_role": downstream_role or primary_downstream_role,
                        "locality_gain_flag": "yes" if region(supplier_country) in {"France", "Europe_non_FR"} and region(primary_country) == "Outside_Europe" else "no",
                        "distance_gain_flag": "yes" if delta is not None and delta < 0 else "no",
                        "coordinate_status": "ok" if supplier.get("lat") is not None and supplier.get("lon") is not None else "missing_coordinates",
                    }
                )
    rows.sort(
        key=lambda row: (
            row["coordinate_status"] != "ok",
            row["locality_gain_flag"] != "yes",
            float(row["distance_delta_vs_primary_km"]) if row["distance_delta_vs_primary_km"] != "" else 10**9,
        )
    )
    return rows


def scenario_choices(records: list[dict[str, Any]], scenario: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        grouped_all = suppliers_by_role(record, "all")
        chosen: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
        chosen["oem"] = suppliers_by_role(record, "primary")["oem"] or grouped_all["oem"][:1]
        for role in ROLES[:-1]:
            candidates = grouped_all[role]
            if not candidates:
                continue
            primary = [supplier for supplier in candidates if supplier.get("is_primary")]
            if scenario == "primary_baseline":
                selected = primary[0] if primary else candidates[0]
            elif scenario == "max_france":
                selected = min(candidates, key=lambda supplier: (region(clean_name(supplier.get("location"))) != "France", not supplier.get("is_primary")))
            elif scenario == "max_europe":
                selected = min(candidates, key=lambda supplier: (region(clean_name(supplier.get("location"))) == "Outside_Europe", not supplier.get("is_primary")))
            elif scenario == "nearest_downstream":
                scored = []
                for supplier in candidates:
                    distance, _, _ = nearest_downstream(record, role, supplier, "primary")
                    scored.append((distance if distance is not None else 10**9, not supplier.get("is_primary"), supplier))
                selected = min(scored, key=lambda item: item[:2])[2]
            else:
                selected = primary[0] if primary else candidates[0]
            chosen[role] = [selected]
        for role in ROLES:
            for supplier in chosen[role]:
                nodes.setdefault(supplier_key(supplier), node_row(supplier, role, scenario))
        for from_role, to_role in zip(ROLES, ROLES[1:]):
            if not chosen[from_role] or not chosen[to_role]:
                continue
            edges.append(edge_row(record_index, record, from_role, to_role, chosen[from_role][0], chosen[to_role][0], scenario))
    return list(nodes.values()), edges


def scenario_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in ["primary_baseline", "max_france", "max_europe", "nearest_downstream"]:
        nodes, edges = scenario_choices(records, scenario)
        stats = edge_distance_stats(edges)
        role_country = Counter()
        role_region = Counter()
        for node in nodes:
            role_country[(node["role_hint"], node["country"])] += 1
            role_region[(node["role_hint"], node["region"])] += 1
        rows.append(
            {
                "scenario": scenario,
                "unique_nodes": len(nodes),
                "edges": stats["edges"],
                "edges_with_distance": stats["edges_with_distance"],
                "avg_distance_km": "" if stats["avg_distance_km"] is None else round(stats["avg_distance_km"], 3),
                "median_distance_km": "" if stats["median_distance_km"] is None else round(stats["median_distance_km"], 3),
                "p90_distance_km": "" if stats["p90_distance_km"] is None else round(stats["p90_distance_km"], 3),
                "total_mass_distance_kg_km": round(stats["total_mass_distance_kg_km"], 3),
                "france_nodes": sum(1 for node in nodes if node["region"] == "France"),
                "europe_non_fr_nodes": sum(1 for node in nodes if node["region"] == "Europe_non_FR"),
                "outside_europe_nodes": sum(1 for node in nodes if node["region"] == "Outside_Europe"),
                "unknown_region_nodes": sum(1 for node in nodes if node["region"] == "unknown"),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def top_counter(counter: Counter, limit: int = 12) -> str:
    return ", ".join(f"{key}={value}" for key, value in counter.most_common(limit)) or "none"


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return str(value)


def markdown_report(
    records: list[dict[str, Any]],
    primary_nodes: list[dict[str, Any]],
    primary_edges: list[dict[str, Any]],
    all_nodes: list[dict[str, Any]],
    all_edges: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    redundancy: list[dict[str, Any]],
    switches: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> None:
    primary_stats = edge_distance_stats(primary_edges)
    all_stats = edge_distance_stats(all_edges)
    primary_roles = Counter(node["role_hint"] for node in primary_nodes)
    all_roles = Counter(node["role_hint"] for node in all_nodes)
    primary_regions = Counter(node["region"] for node in primary_nodes)
    all_regions = Counter(node["region"] for node in all_nodes)
    gap_roles = Counter()
    for row in gaps:
        if row["variant"] == "primary":
            for role in row["missing_roles"].split(";"):
                if role:
                    gap_roles[role] += 1
    weak = Counter()
    for row in redundancy:
        for role in row["weak_roles"].split(";"):
            if role:
                weak[role] += 1

    top_switches = [
        row
        for row in switches
        if row["coordinate_status"] == "ok" and (row["distance_gain_flag"] == "yes" or row["locality_gain_flag"] == "yes")
    ][:15]

    lines = [
        "# Supply network audit - Tier4 to OEM",
        "",
        f"- Source JSON: `{INPUT_JSON.as_posix()}`",
        f"- Primary nodes: `{OUT_PRIMARY_NODES.as_posix()}`",
        f"- Primary edges: `{OUT_PRIMARY_EDGES.as_posix()}`",
        f"- All-enabled nodes: `{OUT_ALL_NODES.as_posix()}`",
        f"- All-enabled edges: `{OUT_ALL_EDGES.as_posix()}`",
        f"- Component gaps: `{OUT_GAPS.as_posix()}`",
        f"- Component redundancy: `{OUT_REDUNDANCY.as_posix()}`",
        f"- Switch options: `{OUT_SWITCHES.as_posix()}`",
        f"- Restructuring scenarios: `{OUT_SCENARIOS.as_posix()}`",
        "",
        "## Network sizes",
        "",
        f"- Records/components/material lines: {len(records)}",
        f"- Primary-only unique nodes: {len(primary_nodes)}",
        f"- Primary-only implied edges: {len(primary_edges)}",
        f"- All-enabled unique nodes: {len(all_nodes)}",
        f"- All-enabled possible edges: {len(all_edges)}",
        f"- Supplier switch candidates: {len(switches)}",
        "",
        "## Primary-only network",
        "",
        f"- Nodes by role: {top_counter(primary_roles)}",
        f"- Nodes by region: {top_counter(primary_regions)}",
        f"- Edges with distance: {primary_stats['edges_with_distance']}/{primary_stats['edges']}",
        f"- Median edge distance: {fmt(primary_stats['median_distance_km'])} km",
        f"- P90 edge distance: {fmt(primary_stats['p90_distance_km'])} km",
        f"- Total mass-distance proxy: {fmt(primary_stats['total_mass_distance_kg_km'])} kg.km",
        f"- Missing-role counts on primary chains: {top_counter(gap_roles)}",
        "",
        "## All-enabled network",
        "",
        f"- Nodes by role: {top_counter(all_roles)}",
        f"- Nodes by region: {top_counter(all_regions)}",
        f"- Edges with distance: {all_stats['edges_with_distance']}/{all_stats['edges']}",
        f"- Median possible edge distance: {fmt(all_stats['median_distance_km'])} km",
        f"- P90 possible edge distance: {fmt(all_stats['p90_distance_km'])} km",
        f"- Total mass-distance over all possible edges: {fmt(all_stats['total_mass_distance_kg_km'])} kg.km",
        "",
        "## Redundancy risks",
        "",
        f"- Weak roles with <=1 candidate: {top_counter(weak)}",
        "- Primary chains are not always full Tier4->Tier3->Tier2->Tier1->OEM; missing Tier2 is the dominant structural gap.",
        "- All-enabled mode increases optionality, but many alternates have no allocation share, capacity, lead time, qualification status or recovery assumption yet.",
        "",
        "## Scenario comparison",
        "",
        "| Scenario | Nodes | Edges | Median km | P90 km | France nodes | Europe non-FR | Outside Europe | Mass-distance kg.km |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in scenarios:
        lines.append(
            f"| {row['scenario']} | {row['unique_nodes']} | {row['edges']} | {row['median_distance_km']} | "
            f"{row['p90_distance_km']} | {row['france_nodes']} | {row['europe_non_fr_nodes']} | "
            f"{row['outside_europe_nodes']} | {row['total_mass_distance_kg_km']} |"
        )
    lines += [
        "",
        "## Switch options to review first",
        "",
    ]
    if top_switches:
        for row in top_switches:
            delta = row["distance_delta_vs_primary_km"]
            lines.append(
                f"- R{row['record_index']} `{row['role_hint']}` {row['primary_supplier']} ({row['primary_country']}) "
                f"-> {row['alternate_supplier']} ({row['alternate_country']}), delta distance={delta} km, "
                f"component={row['component']}"
            )
    else:
        lines.append("- No coordinate-backed switch with distance/locality gain found.")
    lines += [
        "",
        "## Recommended stress-test setup",
        "",
        "- Start with `primary_baseline` as the reference network.",
        "- Use `all_enabled` only as the option universe, not as simultaneous purchasing.",
        "- For local restructuring, compare `max_france`, `max_europe`, and `nearest_downstream` scenarios.",
        "- Add missing scenario parameters before quantitative simulation: supplier capacity, allocation share, lead time, MOQ/lot size, qualification status, recovery time, and switching penalty.",
        "- Treat record-level masses carefully: material/detail rows and aggregate `Siege` rows coexist, so do not sum all records as a seat total without choosing one aggregation level.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    primary_nodes, primary_edges, primary_gaps = build_variant(records, "primary")
    all_nodes, all_edges, all_gaps = build_variant(records, "all")
    gaps = primary_gaps + all_gaps
    redundancy = component_redundancy(records)
    switches = switch_options(records)
    scenarios = scenario_summary(records)

    write_csv(OUT_PRIMARY_NODES, primary_nodes)
    write_csv(OUT_PRIMARY_EDGES, primary_edges)
    write_csv(OUT_ALL_NODES, all_nodes)
    write_csv(OUT_ALL_EDGES, all_edges)
    write_csv(OUT_GAPS, gaps)
    write_csv(OUT_REDUNDANCY, redundancy)
    write_csv(OUT_SWITCHES, switches)
    write_csv(OUT_SCENARIOS, scenarios)
    markdown_report(records, primary_nodes, primary_edges, all_nodes, all_edges, gaps, redundancy, switches, scenarios)

    print(f"[OK] wrote {OUT_MD}")
    print(f"[OK] primary nodes={len(primary_nodes)} edges={len(primary_edges)}")
    print(f"[OK] all-enabled nodes={len(all_nodes)} edges={len(all_edges)}")
    print(f"[OK] switches={len(switches)} scenarios={len(scenarios)}")


if __name__ == "__main__":
    main()
