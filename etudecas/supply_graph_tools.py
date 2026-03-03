"""Utilities to derive simulation-ready parameters from supply graph JSON files."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any


@dataclass
class SupplyGraphSummary:
    actor_count: int
    product_count: int
    supply_edge_count: int
    role_counts: dict[str, int]
    flow_counts: dict[str, int]
    median_distance_km_by_flow: dict[str, float]
    suggested_transport_days: dict[str, int]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius_km * math.asin(math.sqrt(a))


def _extract_code(actor_id: str) -> str | None:
    if actor_id.startswith("Actor:"):
        return actor_id.split(":", 1)[1].strip()
    if " - " in actor_id:
        return actor_id.rsplit(" - ", 1)[-1].strip()
    return None


def _canonical_coord_keys(actor_id: str, role: str | None) -> list[str]:
    code = _extract_code(actor_id)
    if code is None:
        return []
    keys: list[str] = []

    if actor_id.startswith("Actor:"):
        base = actor_id.split(":", 1)[1].strip()
        keys.append(base)
    if role == "Manufacturer":
        keys.append(f"M - {code}")
    elif role == "Distribution Center":
        keys.append(f"DC - {code}")
    elif role == "Supplier Distribution Center":
        keys.append(f"SDC - {code}")
    elif role == "Customer":
        keys.append(f"C - {code}")

    # Fallbacks for placeholder nodes and minor naming differences.
    keys.extend(
        [
            f"DC - {code}",
            f"SDC - {code}",
            f"M - {code}",
            f"C - {code}",
            code,
        ]
    )
    # Preserve order and remove duplicates.
    return list(dict.fromkeys(keys))


def _infer_role(actor_id: str, role: str | None) -> str:
    if role:
        return role
    if actor_id.startswith("Actor:DC -"):
        return "Distribution Center"
    if actor_id.startswith("Actor:C -"):
        return "Customer"
    if actor_id.startswith("Actor:SDC -"):
        return "Supplier Distribution Center"
    if actor_id.startswith("Actor:M -"):
        return "Manufacturer"
    return "Unknown"


def _flow_key(source_role: str, target_role: str) -> str:
    return f"{source_role} -> {target_role}"


def _median(values: list[float]) -> float:
    if not values:
        return float("nan")
    values_sorted = sorted(values)
    mid = len(values_sorted) // 2
    if len(values_sorted) % 2:
        return values_sorted[mid]
    return 0.5 * (values_sorted[mid - 1] + values_sorted[mid])


def derive_supply_graph_summary(
    knowledge_graph_path: str | Path,
    actor_coords_path: str | Path,
    km_per_day: float = 250.0,
) -> SupplyGraphSummary:
    with open(knowledge_graph_path, encoding="utf-8") as f:
        graph = json.load(f)
    with open(actor_coords_path, encoding="utf-8") as f:
        coords = json.load(f)

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    node_by_id = {node["id"]: node for node in nodes}
    actor_nodes = [
        n
        for n in nodes
        if n.get("layer") in ("actor", "actor_placeholder")
    ]
    product_nodes = [n for n in nodes if n.get("layer") == "product"]

    actor_role_map: dict[str, str] = {}
    role_counts: dict[str, int] = {}
    actor_coord_map: dict[str, tuple[float, float] | None] = {}

    for actor in actor_nodes:
        actor_id = actor["id"]
        role = _infer_role(actor_id, actor.get("role"))
        actor_role_map[actor_id] = role
        role_counts[role] = role_counts.get(role, 0) + 1

        coord = None
        for key in _canonical_coord_keys(actor_id, role):
            if key in coords:
                lat, lon = coords[key]
                coord = (float(lat), float(lon))
                break
        actor_coord_map[actor_id] = coord

    supply_edges = []
    flow_counts: dict[str, int] = {}
    flow_distances: dict[str, list[float]] = {}

    for edge in edges:
        if edge.get("relation") != "SUPPLIES":
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source not in actor_role_map or target not in actor_role_map:
            continue

        source_role = actor_role_map[source]
        target_role = actor_role_map[target]
        flow = _flow_key(source_role, target_role)
        flow_counts[flow] = flow_counts.get(flow, 0) + 1

        distance = float("nan")
        source_coord = actor_coord_map.get(source)
        target_coord = actor_coord_map.get(target)
        if source_coord is not None and target_coord is not None:
            distance = _haversine_km(source_coord[0], source_coord[1], target_coord[0], target_coord[1])
            flow_distances.setdefault(flow, []).append(distance)

        supply_edges.append(
            {
                "source": source,
                "target": target,
                "flow": flow,
                "distance_km": distance,
                "product": edge.get("product"),
            }
        )

    median_distance_km_by_flow = {
        flow: _median(distances) for flow, distances in flow_distances.items()
    }

    # Build transport suggestions aligned with current SD/DES 3-transport template.
    supplier_to_manu = median_distance_km_by_flow.get(
        "Supplier Distribution Center -> Manufacturer", float("nan")
    )
    manu_to_dc = median_distance_km_by_flow.get(
        "Manufacturer -> Distribution Center", float("nan")
    )
    dc_to_customer = median_distance_km_by_flow.get(
        "Distribution Center -> Customer", float("nan")
    )

    def _to_days(distance_km: float, default_days: int) -> int:
        if math.isnan(distance_km):
            return default_days
        return max(1, int(math.ceil(distance_km / km_per_day)))

    suggested_transport_days = {
        "transport_1_days": _to_days(supplier_to_manu, 5),
        "transport_2_days": _to_days(manu_to_dc, 4),
        "transport_3_days": _to_days(dc_to_customer, 3),
    }

    return SupplyGraphSummary(
        actor_count=len(actor_nodes),
        product_count=len(product_nodes),
        supply_edge_count=len(supply_edges),
        role_counts=role_counts,
        flow_counts=flow_counts,
        median_distance_km_by_flow=median_distance_km_by_flow,
        suggested_transport_days=suggested_transport_days,
    )


def summary_to_dict(summary: SupplyGraphSummary) -> dict[str, Any]:
    return {
        "actor_count": summary.actor_count,
        "product_count": summary.product_count,
        "supply_edge_count": summary.supply_edge_count,
        "role_counts": summary.role_counts,
        "flow_counts": summary.flow_counts,
        "median_distance_km_by_flow": summary.median_distance_km_by_flow,
        "suggested_transport_days": summary.suggested_transport_days,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Derive simulation inputs from supply graph files")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json", help="Path to knowledge_graph.json")
    parser.add_argument("--coords", type=str, default="actor_coords.json", help="Path to actor_coords.json")
    parser.add_argument(
        "--out",
        type=str,
        default="derived_supply_summary.json",
        help="Output JSON summary path",
    )
    parser.add_argument("--km-per-day", type=float, default=250.0, help="Assumed transport speed")
    args = parser.parse_args()

    summary = derive_supply_graph_summary(args.graph, args.coords, km_per_day=args.km_per_day)
    payload = summary_to_dict(summary)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=True, indent=2)

    print("=== Supply Graph Summary ===")
    print(f"Actors: {summary.actor_count}")
    print(f"Products: {summary.product_count}")
    print(f"Supply edges: {summary.supply_edge_count}")
    print("Roles:")
    for role, count in sorted(summary.role_counts.items()):
        print(f"- {role}: {count}")
    print("Flows:")
    for flow, count in sorted(summary.flow_counts.items()):
        print(f"- {flow}: {count}")
    print("Suggested transport days:")
    for key, value in summary.suggested_transport_days.items():
        print(f"- {key}: {value}")
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
