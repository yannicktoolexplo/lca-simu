#!/usr/bin/env python3
"""
Build an interactive HTML world map from a geocoded supply graph.

Includes two hover-panel modes:
- Simulation: current operational stock / production PNGs
- Sensitivity: low/base/high comparisons built from sensitivity case outputs
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import math
import re
import sys
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

NODE_TYPE_STYLES = {
    "supplier_dc": {"name": "Supplier DC", "color": "#1f77b4", "symbol": "circle"},
    "factory": {"name": "Factory", "color": "#d62728", "symbol": "square"},
    "distribution_center": {"name": "Distribution Center", "color": "#ff7f0e", "symbol": "diamond"},
    "customer": {"name": "Customer", "color": "#2ca02c", "symbol": "star"},
}

PILOTAGE_HIDDEN_NODE_IDS = {"M-1450"}
UPSTREAM_INTERNAL_SITE_IDS = {"SDC-1450"}
UPSTREAM_INTERNAL_SITE_DISPLAY_LABEL = "D-1450"
SIMULATION_HIDDEN_ITEM_IDS: set[str] = set()
ITEM_DISPLAY_REFERENCE_NOTES = {
    "item:007923": "007923 (ancienne ref 693710)",
}
STANDARD_ORDER_OVERRIDES = {
    ("SDC-VD0520115A", "M-1430", "item:708073"): {
        "qty": 5000.0,
        "note": "corrige: valeur source 5 000 000 interpretee comme g, soit 5 000 kg",
    },
}
MANUAL_GEO_OVERRIDES = {
    # Fournisseurs 021081: le geocodage automatique retombait au centroide USA.
    "SDC-VD0949099A": {
        "lat": 36.2168,
        "lon": -81.6746,
        "location_ID": "USA - BOONE NC - 28607",
        "country": "United States",
    },
    "SDC-VD0960508A": {
        "lat": 36.0307,
        "lon": -78.9000,
        "location_ID": "USA - DURHAM NC - 27704",
        "country": "United States",
    },
    "SDC-VD0972460A": {
        "lat": 26.5387,
        "lon": -81.4356,
        "location_ID": "USA - FELDA FL - 33930",
        "country": "United States",
    },
    "SDC-VD0975221A": {
        "lat": 27.4467,
        "lon": -80.3256,
        "location_ID": "USA - FORT PIERCE FL - 34947",
        "country": "United States",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        "-i",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Input geocoded supply graph JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="etudecas/simulation/result/maps/supply_graph_poc_geocoded_map_with_factory_hover.html",
        help="Output HTML file.",
    )
    parser.add_argument(
        "--title",
        default="Supply Graph POC - Geocoded Map",
        help="HTML page title.",
    )
    parser.add_argument(
        "--sim-input-stocks-csv",
        default="etudecas/simulation/result/data/production_input_stocks_daily.csv",
        help="Simulation CSV for input material stocks.",
    )
    parser.add_argument(
        "--sim-output-products-csv",
        default="etudecas/simulation/result/data/production_output_products_daily.csv",
        help="Simulation CSV for output products production.",
    )
    parser.add_argument(
        "--demand-service-csv",
        default="etudecas/simulation/result/data/production_demand_service_daily.csv",
        help="Simulation CSV for customer demand / served / backlog time series.",
    )
    parser.add_argument(
        "--sim-input-stocks-png-dir",
        default="etudecas/simulation/result/plots",
        help="Directory containing input/supplier/DC PNG files.",
    )
    parser.add_argument(
        "--sim-output-products-png-dir",
        default="etudecas/simulation/result/plots",
        help="Directory containing production_output_products_by_factory_<factory>.png files.",
    )
    parser.add_argument(
        "--sensitivity-cases-csv",
        default="etudecas/simulation/sensibility/result/sensitivity_cases.csv",
        help="Sensitivity cases summary CSV.",
    )
    parser.add_argument(
        "--supplier-shipments-csv",
        default="etudecas/simulation/result/data/production_supplier_shipments_daily.csv",
        help="Baseline supplier shipments CSV.",
    )
    parser.add_argument(
        "--supplier-stocks-csv",
        default="etudecas/simulation/result/data/production_supplier_stocks_daily.csv",
        help="Baseline supplier stocks CSV.",
    )
    parser.add_argument(
        "--supplier-capacity-csv",
        default="etudecas/simulation/result/data/production_supplier_capacity_daily.csv",
        help="Baseline supplier capacity utilization CSV.",
    )
    parser.add_argument(
        "--input-arrivals-csv",
        default="etudecas/simulation/result/data/production_input_replenishment_arrivals_daily.csv",
        help="Baseline input replenishment arrivals CSV.",
    )
    parser.add_argument(
        "--dc-stocks-csv",
        default="etudecas/simulation/result/data/production_dc_stocks_daily.csv",
        help="Baseline distribution center stocks CSV.",
    )
    parser.add_argument(
        "--production-constraint-csv",
        default="etudecas/simulation/result/data/production_constraint_daily.csv",
        help="Production constraint CSV used to detect critical supplied items.",
    )
    parser.add_argument(
        "--safety-reference-csv",
        default="",
        help="Optional MRP safety stock reference CSV generated by the simulation.",
    )
    parser.add_argument(
        "--daily-kpi-csv",
        default="",
        help="Optional daily KPI CSV generated by the simulation. Defaults to first_simulation_daily.csv next to simulation data.",
    )
    parser.add_argument(
        "--structural-sensitivity-cases-csv",
        default="etudecas/simulation/sensibility/structural_result/sensitivity_cases.csv",
        help="Structural sensitivity cases summary CSV.",
    )
    parser.add_argument(
        "--supplier-local-criticality-csv",
        default="etudecas/simulation/result/data/supplier_local_criticality_ranking.csv",
        help="Output CSV ranking for supplier local criticality.",
    )
    parser.add_argument(
        "--supplier-local-criticality-json",
        default="etudecas/simulation/result/summaries/supplier_local_criticality_summary.json",
        help="Output JSON summary for supplier local criticality.",
    )
    parser.add_argument(
        "--realistic-sensitivity-summary-json",
        default="",
        help="Optional realistic annual sensitivity summary JSON.",
    )
    parser.add_argument(
        "--realistic-local-elasticities-csv",
        default="",
        help="Optional realistic annual local elasticities CSV.",
    )
    parser.add_argument(
        "--realistic-stress-impacts-csv",
        default="",
        help="Optional realistic annual stress impacts CSV.",
    )
    parser.add_argument(
        "--threshold-sensitivity-summary-json",
        default="",
        help="Optional threshold-oriented annual sensitivity summary JSON.",
    )
    parser.add_argument(
        "--threshold-parameter-summary-csv",
        default="",
        help="Optional threshold-oriented annual parameter summary CSV.",
    )
    parser.add_argument(
        "--threshold-sweep-cases-csv",
        default="",
        help="Optional threshold-oriented annual sweep cases CSV.",
    )
    return parser.parse_args()


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def is_pilotage_hidden_node(node_id: str) -> bool:
    return bool(node_id) and node_id in PILOTAGE_HIDDEN_NODE_IDS


def is_pilotage_hidden_edge(src: str, dst: str) -> bool:
    return is_pilotage_hidden_node(src) or is_pilotage_hidden_node(dst)


def is_upstream_internal_site(node_id: str) -> bool:
    return bool(node_id) and node_id in UPSTREAM_INTERNAL_SITE_IDS


def display_node_label(node_id: str) -> str:
    if is_upstream_internal_site(node_id):
        return UPSTREAM_INTERNAL_SITE_DISPLAY_LABEL
    return node_id


def is_simulation_hidden_item(item_id: str) -> bool:
    return bool(item_id) and item_id in SIMULATION_HIDDEN_ITEM_IDS


def standard_order_override_for_edge(edge: dict[str, Any]) -> dict[str, Any] | None:
    src = str(edge.get("from") or "")
    dst = str(edge.get("to") or "")
    for item_id in edge.get("items") or []:
        override = STANDARD_ORDER_OVERRIDES.get((src, dst, str(item_id or "")))
        if override:
            return override
    return None


def display_standard_order_qty(edge: dict[str, Any]) -> float:
    override = standard_order_override_for_edge(edge)
    if override:
        return max(0.0, float(override["qty"]))
    return max(0.0, to_float(((edge.get("attrs") or {}).get("standard_order_qty")) or 0.0) or 0.0)


def compact_graph_payload(raw: dict[str, Any]) -> dict[str, Any]:
    nodes_in = raw.get("nodes", [])
    edges_in = raw.get("edges", [])
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        raise ValueError("Expected JSON with list fields: nodes and edges.")

    connected_node_ids: set[str] = set()
    for edge in edges_in:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if is_pilotage_hidden_edge(src, dst):
            continue
        if src:
            connected_node_ids.add(src)
        if dst:
            connected_node_ids.add(dst)

    nodes: list[dict[str, Any]] = []
    for node in nodes_in:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if is_pilotage_hidden_node(node_id):
            continue
        inventory_states = (((node.get("inventory") or {}).get("states")) or [])
        processes = node.get("processes") or []
        if (
            node_id
            and node_id not in connected_node_ids
            and not inventory_states
            and not processes
        ):
            # Skip pure orphans in the exported map payload.
            continue
        geo = node.get("geo", {}) or {}
        lat = node.get("lat", geo.get("lat"))
        lon = node.get("lon", geo.get("lon"))
        location_id = node.get("location_ID")
        country = geo.get("country")
        geo_override = MANUAL_GEO_OVERRIDES.get(node_id)
        if geo_override:
            lat = geo_override["lat"]
            lon = geo_override["lon"]
            location_id = geo_override["location_ID"]
            country = geo_override["country"]
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            lat = None
            lon = None
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("type", "unknown"),
                "name": node.get("name", ""),
                "location_ID": location_id,
                "country": country,
                "lat": lat,
                "lon": lon,
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in edges_in:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if is_pilotage_hidden_edge(src, dst):
            continue
        items = edge.get("items", [])
        if not isinstance(items, list):
            items = []
        edges.append(
            {
                "id": edge.get("id"),
                "type": edge.get("type", "unknown"),
                "from": src,
                "to": dst,
                "items": items,
                "planned_lead_days": max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0),
                "distance_km": max(0.0, to_float(edge.get("distance_km")) or 0.0),
                "standard_order_qty": display_standard_order_qty(edge),
            }
        )

    node_types = sorted({n.get("type", "unknown") for n in nodes})
    return {
        "schema_version": raw.get("schema_version"),
        "meta": raw.get("meta", {}),
        "nodes": nodes,
        "edges": edges,
        "node_types": node_types,
        "node_type_styles": NODE_TYPE_STYLES,
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * max(0.0, min(1.0, q))
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def build_edge_metrics(raw: dict[str, Any], supplier_shipments_csv: Path) -> dict[str, dict[str, Any]]:
    rows = read_csv_rows(supplier_shipments_csv)
    shipment_rows_by_triplet: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        shipment_rows_by_triplet[
            (
                str(row.get("src_node_id") or ""),
                str(row.get("dst_node_id") or ""),
                str(row.get("item_id") or ""),
            )
        ].append(row)

    safety_time_by_pair: dict[tuple[str, str], float] = {}
    for node in (raw.get("nodes", []) or []):
        node_id = str(node.get("id") or "")
        for state in (((node.get("inventory") or {}).get("states") or [])):
            item_id = str(state.get("item_id") or "")
            mrp_policy = state.get("mrp_policy") or {}
            safety_time = max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0)
            if node_id and item_id and safety_time > 0.0:
                safety_time_by_pair[(node_id, item_id)] = safety_time

    edge_metrics: dict[str, dict[str, Any]] = {}
    for edge in (raw.get("edges", []) or []):
        edge_id = str(edge.get("id") or "")
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        items = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        if not edge_id or not src or not dst or not items:
            continue
        lead_values: list[float] = []
        qty_values: list[float] = []
        safety_times: list[float] = []
        active_items: list[str] = []
        for item_id in items:
            scoped_rows = shipment_rows_by_triplet.get((src, dst, item_id), [])
            if scoped_rows:
                active_items.append(item_id)
            for row in scoped_rows:
                lead_values.append(max(0.0, to_float(row.get("lead_days")) or 0.0))
                qty_values.append(max(0.0, to_float(row.get("shipped_qty")) or 0.0))
            safety = max(0.0, safety_time_by_pair.get((dst, item_id), 0.0))
            if safety > 0.0:
                safety_times.append(safety)
        planned_lead_days = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
        avg_lead_days = statistics.mean(lead_values) if lead_values else planned_lead_days
        min_lead_days = min(lead_values) if lead_values else planned_lead_days
        max_lead_days = max(lead_values) if lead_values else planned_lead_days
        lead_std_days = statistics.pstdev(lead_values) if len(lead_values) > 1 else 0.0
        qty_distinct = len({round(v, 6) for v in qty_values}) if qty_values else 0
        safety_time_days = max(safety_times) if safety_times else 0.0
        edge_metrics[edge_id] = {
            "shipment_rows": len(qty_values),
            "active_items": active_items,
            "avg_lead_days": round(avg_lead_days, 2),
            "min_lead_days": round(min_lead_days, 2),
            "max_lead_days": round(max_lead_days, 2),
            "lead_std_days": round(lead_std_days, 2),
            "lead_p50_days": round(percentile(lead_values, 0.5), 2) if lead_values else round(planned_lead_days, 2),
            "lead_p90_days": round(percentile(lead_values, 0.9), 2) if lead_values else round(planned_lead_days, 2),
            "distinct_lead_days": len({round(v, 6) for v in lead_values}) if lead_values else 1,
            "planned_lead_days": round(planned_lead_days, 2),
            "avg_shipped_qty": round(statistics.mean(qty_values), 4) if qty_values else 0.0,
            "distinct_shipped_qty": qty_distinct,
            "qty_constant_flag": bool(qty_values) and qty_distinct <= 1,
            "safety_time_days": round(safety_time_days, 2),
            "effective_lead_days": round(avg_lead_days + safety_time_days, 2),
        }
    return edge_metrics


def factory_like_node_ids(raw: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if not node_id:
            continue
        if is_pilotage_hidden_node(node_id):
            continue
        if node_type == "factory" or (node_type == "supplier_dc" and (node.get("processes") or [])):
            ids.add(node_id)
    return ids


def build_factory_hover_series(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    items = raw.get("items", []) or []

    factory_ids = factory_like_node_ids(raw)
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}

    item_label: dict[str, str] = {}
    for it in items:
        iid = str(it.get("id"))
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        item_label[iid] = code if code else (name if name else iid)

    in_unit_by_node_item: dict[tuple[str, str], str] = {}
    out_unit_by_node_item: dict[tuple[str, str], str] = {}
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            item_id = str(st.get("item_id"))
            uom = str(st.get("uom") or "").strip()
            if item_id and uom:
                in_unit_by_node_item[(nid, item_id)] = uom
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                uom = str(inp.get("ratio_unit") or "").strip()
                if item_id and uom and (nid, item_id) not in in_unit_by_node_item:
                    in_unit_by_node_item[(nid, item_id)] = uom
            for out in (p.get("outputs") or []):
                item_id = str(out.get("item_id"))
                uom = str(out.get("uom") or "").strip()
                if item_id and uom:
                    out_unit_by_node_item[(nid, item_id)] = uom

    incoming_raw: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_input_stocks_csv.exists():
        with sim_input_stocks_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                if day == 0:
                    # Day 0 should reflect the seeded source snapshot before any
                    # same-day consumption, so the graph starts from the true
                    # initial stock photo rather than the post-day state.
                    val = to_float(row.get("stock_before_production"))
                    if val is None:
                        val = to_float(row.get("stock_end_of_day")) or 0.0
                else:
                    val = to_float(row.get("stock_end_of_day"))
                    if val is None:
                        val = to_float(row.get("stock_before_production")) or 0.0
                incoming_raw[node_id][item_id].append((day, val))

    outgoing_raw: dict[str, dict[str, list[tuple[int, float, float, float | None]]]] = defaultdict(lambda: defaultdict(list))
    if sim_output_products_csv.exists():
        with sim_output_products_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                prod = float(to_float(row.get("produced_qty")) or 0.0)
                cum = float(to_float(row.get("cum_produced_qty")) or 0.0)
                stock_end = to_float(row.get("stock_end_of_day"))
                outgoing_raw[node_id][item_id].append((day, prod, cum, stock_end))

    out: dict[str, Any] = {}
    for node_id in sorted(factory_ids):
        incoming = []
        for item_id, pts in sorted(incoming_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            incoming.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": in_unit_by_node_item.get((node_id, item_id), ""),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                }
            )

        outgoing = []
        for item_id, pts in sorted(outgoing_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            outgoing.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": out_unit_by_node_item.get((node_id, item_id), "unit/day"),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                    "cum_values": [p[2] for p in pts_sorted],
                    "stock_values": [p[3] for p in pts_sorted],
                }
            )

        if incoming or outgoing:
            out[node_id] = {
                "node_id": node_id,
                "node_name": node_name.get(node_id, node_id),
                "incoming": incoming,
                "outgoing": outgoing,
            }

    return out


def png_payload_from_bytes(png_bytes: bytes, filename: str) -> dict[str, Any]:
    return {
        "mime": "image/png",
        "data_b64": base64.b64encode(png_bytes).decode("ascii"),
        "filename": filename,
    }


def load_png_payload(png_path: Path) -> dict[str, Any] | None:
    if not png_path.exists():
        return None
    try:
        return png_payload_from_bytes(png_path.read_bytes(), png_path.name)
    except Exception:
        return None


def resolve_plot_payload(base_dir: Path, relative_path: Path, legacy_name: str) -> dict[str, Any] | None:
    candidates = [
        base_dir / relative_path,
        base_dir / legacy_name,
    ]
    for candidate in candidates:
        payload = load_png_payload(candidate)
        if payload is not None:
            return payload
    return None


def build_factory_hover_images(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    input_arrivals_csv: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    input_png_dir: Path,
    output_png_dir: Path,
    demand_service_csv: Path,
    production_constraint_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    _ = demand_service_csv
    constraint_rows = read_csv_rows(production_constraint_csv)
    input_arrival_rows = read_csv_rows(input_arrivals_csv)
    supplier_shipment_rows = read_csv_rows(supplier_shipments_csv)
    factory_ids = sorted(factory_like_node_ids(raw))
    node_by_id = {str(n.get("id")): n for n in nodes}
    item_labels = item_label_lookup(raw)
    out: dict[str, Any] = {}
    for factory_id in factory_ids:
        node_type = str((node_by_id.get(factory_id) or {}).get("type") or "")
        safe_factory = re.sub(r"[^A-Za-z0-9_-]+", "_", factory_id)
        detail = build_factory_hover_series(raw, sim_input_stocks_csv, sim_output_products_csv).get(factory_id) or {}
        incoming = resolve_plot_payload(
            input_png_dir,
            Path("factories") / "input_stocks" / f"production_input_stocks_by_material_{safe_factory}.png",
            f"production_input_stocks_by_material_{safe_factory}.png",
        )
        if incoming is None:
            incoming = descriptor_series_to_figure(
                detail.get("incoming") or [],
                title=f"{factory_id} - stocks intrants",
                y_label="Quantite",
            )
        outgoing = descriptor_series_to_figure(
            detail.get("outgoing") or [],
            title=f"{factory_id} - stock produits finis",
            y_label="Quantite",
            value_key="stock_values",
        )
        if outgoing is None:
            outgoing = resolve_plot_payload(
                output_png_dir,
                Path("factories") / "output_products" / f"production_output_products_by_factory_{safe_factory}.png",
                f"production_output_products_by_factory_{safe_factory}.png",
            )
        if outgoing is None:
            outgoing = resolve_plot_payload(
                output_png_dir,
                Path("factories") / "output_products" / "production_output_products.png",
                "production_output_products.png",
            )
        if incoming is None and detail:
            incoming = descriptor_series_to_figure(
                detail.get("incoming") or [],
                title=f"{factory_id} - stocks intrants",
                y_label="Quantite",
            )
        incoming_descriptors = detail.get("incoming") or []
        incoming_stock_series = {
            f"{str(descriptor.get('item_label') or descriptor.get('item_id') or '').strip()} - stock": list(
                zip(descriptor.get("days") or [], descriptor.get("values") or [])
            )
            for descriptor in incoming_descriptors
            if str(descriptor.get("item_label") or descriptor.get("item_id") or "").strip()
        }
        incoming_stock_series = {label: pts for label, pts in incoming_stock_series.items() if pts}
        incoming_arrival_series: dict[str, list[tuple[int, float]]] = {}
        if input_arrival_rows:
            item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in input_arrival_rows
                    if str(row.get("node_id") or "") == factory_id
                }
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                arrival_pts = aggregate_daily_series(
                    input_arrival_rows,
                    value_field="arrived_qty",
                    node_field="node_id",
                    node_id=factory_id,
                    item_ids={item_id},
                )
                if arrival_pts:
                    item_label = item_labels.get(item_id, compact_item_label(item_id))
                    incoming_arrival_series[f"{item_label} - reception"] = arrival_pts
        display_factory_id = display_node_label(factory_id)
        incoming_title = f"{display_factory_id} - stocks et receptions intrants"
        bottom_title = f"{display_factory_id} - receptions intrants"
        if is_upstream_internal_site(factory_id):
            incoming_title = f"{display_factory_id} - stocks et arrivages intrants"
            bottom_title = f"{display_factory_id} - arrivages intrants"
        if incoming_stock_series or incoming_arrival_series:
            figure = build_dual_line_multi_panel_figure(
                title=incoming_title,
                top_title=f"{display_factory_id} - stock intrants",
                top_y_label="Stock",
                top_series_map=incoming_stock_series,
                bottom_title=bottom_title,
                bottom_y_label="Receptions",
                bottom_series_map=incoming_arrival_series,
                bottom_step_like=True,
            )
            if figure is not None:
                incoming = {"figure": figure}
        if is_upstream_internal_site(factory_id) and supplier_shipment_rows:
            outbound_series: dict[str, list[tuple[int, float]]] = {}
            outbound_item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in supplier_shipment_rows
                    if str(row.get("src_node_id") or "") == factory_id
                }
            )
            for item_id in outbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                shipped_pts = aggregate_daily_series(
                    supplier_shipment_rows,
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=factory_id,
                    item_ids={item_id},
                )
                if shipped_pts:
                    item_label = item_labels.get(item_id, compact_item_label(item_id))
                    outbound_series[item_label] = shipped_pts
            if outbound_series:
                figure = build_line_chart_figure(
                    outbound_series,
                    title=f"{display_factory_id} - expeditions PFI par item",
                    y_label="Quantite",
                    step_like=True,
                )
                if figure is not None:
                    outgoing = {"figure": figure}
        factory_rows = [row for row in constraint_rows if str(row.get("node_id") or "") == factory_id]
        desired_series = aggregate_daily_series(factory_rows, value_field="desired_qty")
        actual_series = aggregate_daily_series(factory_rows, value_field="actual_qty")
        capacity_series = aggregate_daily_series(factory_rows, value_field="cap_qty")
        shortfall_series = aggregate_daily_series(factory_rows, value_field="shortfall_vs_desired_qty")
        inbound_lead_days = {}
        for edge in raw.get("edges", []) or []:
            if str(edge.get("to") or "") != factory_id:
                continue
            supplier_id = str(edge.get("from") or "")
            lead_days = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
            prev = inbound_lead_days.get(supplier_id)
            inbound_lead_days[supplier_id] = min(prev, lead_days) if prev is not None else lead_days
        auxiliary = None
        if node_type == "supplier_dc":
            site_stock_payload = build_site_stock_payload(
                raw,
                supplier_stocks_csv,
                factory_id,
                title=f"{factory_id} - stocks complets du site",
            )
            if site_stock_payload is not None:
                if incoming is None:
                    incoming = site_stock_payload
                else:
                    auxiliary = site_stock_payload
        if not incoming and not outgoing and not auxiliary:
            continue
        out[factory_id] = {"incoming": incoming, "outgoing": outgoing, "third": auxiliary}
    return out


def descriptor_series_to_figure(
    descriptors: list[dict[str, Any]],
    *,
    title: str,
    y_label: str,
    value_key: str = "values",
) -> dict[str, Any] | None:
    series_map: dict[str, list[tuple[int, float]]] = {}
    for descriptor in descriptors:
        label = str(descriptor.get("item_label") or descriptor.get("item_id") or "").strip()
        if is_simulation_hidden_item(str(descriptor.get("item_id") or "")):
            continue
        days = descriptor.get("days") or []
        values = descriptor.get(value_key) or []
        if not label or not days or not values:
            continue
        points = []
        for day, value in zip(days, values):
            if value is None:
                continue
            try:
                points.append((int(day), float(value)))
            except Exception:
                continue
        if points:
            series_map[label] = points
    figure = build_line_chart_figure(series_map, title=title, y_label=y_label)
    if figure is None:
        return None
    return {"figure": figure}


def item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code if code else (name if name else item_id)
        lookup[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return lookup


def build_supplier_hover_images(
    raw: dict[str, Any],
    png_dir: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_capacity_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    supplier_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "supplier_dc" and not is_pilotage_hidden_node(str(n.get("id") or ""))
    )
    out: dict[str, Any] = {}
    item_labels = item_label_lookup(raw)
    inbound_lead_days_by_supplier: dict[str, dict[str, float]] = defaultdict(dict)
    for edge in raw.get("edges", []) or []:
        dst = str(edge.get("to") or "")
        src = str(edge.get("from") or "")
        if dst not in supplier_ids or not src:
            continue
        lead_days = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
        prev = inbound_lead_days_by_supplier[dst].get(src)
        inbound_lead_days_by_supplier[dst][src] = min(prev, lead_days) if prev is not None else lead_days

    for supplier_id in supplier_ids:
        safe_supplier = re.sub(r"[^A-Za-z0-9_-]+", "_", supplier_id)
        incoming = resolve_plot_payload(
            png_dir,
            Path("suppliers") / "input_stocks" / f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
            f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
        )
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_stocks_by_material_{safe_supplier}.png")
        outgoing = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        third = None
        shipped_series: list[tuple[int, float]] = []
        shipment_rows = read_csv_rows(supplier_shipments_csv)
        capacity_rows = read_csv_rows(supplier_capacity_csv)
        if shipment_rows:
            shipped_series = aggregate_daily_series(
                shipment_rows,
                value_field="shipped_qty",
                node_field="src_node_id",
                node_id=supplier_id,
            )
        stock_rows = read_csv_rows(supplier_stocks_csv)
        if incoming is None and stock_rows:
            per_item_stock: dict[str, list[tuple[int, float]]] = {}
            item_ids = sorted({str(row.get("item_id") or "") for row in stock_rows if str(row.get("node_id") or "") == supplier_id})
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    stock_rows,
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                if pts:
                    per_item_stock[item_labels.get(item_id, compact_item_label(item_id))] = pts
            stock_title = f"{supplier_id} - stock fournisseur par item"
            if len(per_item_stock) == 1:
                stock_title = f"{stock_title} - {next(iter(per_item_stock.keys()))}"
            figure = build_line_chart_figure(
                per_item_stock,
                title=stock_title,
                y_label="Quantite",
                step_like=True,
            )
            if figure is not None:
                incoming = {"figure": figure}
        if outgoing is None and shipment_rows:
            combined_flow: dict[str, list[tuple[int, float]]] = {}
            item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in shipment_rows
                    if str(row.get("src_node_id") or "") == supplier_id
                }
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                item_label = item_labels.get(item_id, compact_item_label(item_id))
                ship_pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                receipt_pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    day_field="arrival_day",
                    node_field="src_node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                if ship_pts:
                    combined_flow[f"{item_label} - expedition"] = ship_pts
                if receipt_pts:
                    combined_flow[f"{item_label} - reception"] = receipt_pts
            shipment_title = f"{supplier_id} - expeditions vs receptions associees"
            if len(item_ids) == 1 and item_ids:
                single_label = item_labels.get(item_ids[0], compact_item_label(item_ids[0]))
                shipment_title = f"{shipment_title} - {single_label}"
            figure = build_line_chart_figure(
                combined_flow,
                title=shipment_title,
                y_label="Quantite",
                step_like=True,
            )
            if figure is not None:
                outgoing = {"figure": figure}
        if incoming or outgoing or third:
            out[supplier_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
    return out


def build_distribution_center_hover_images(
    raw: dict[str, Any],
    png_dir: Path,
    dc_stocks_csv: Path,
    shipments_csv: Path,
    mrp_trace_csv: Path | None = None,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    dc_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "distribution_center" and not is_pilotage_hidden_node(str(n.get("id") or ""))
    )
    out: dict[str, Any] = {}
    item_labels = item_label_lookup(raw)
    dc_stock_rows = read_csv_rows(dc_stocks_csv)
    shipment_rows = read_csv_rows(shipments_csv)
    mrp_trace_rows = read_csv_rows(mrp_trace_csv) if mrp_trace_csv is not None else []
    for dc_id in dc_ids:
        safe_dc = re.sub(r"[^A-Za-z0-9_-]+", "_", dc_id)
        incoming = resolve_plot_payload(
            png_dir,
            Path("distribution_centers") / "factory_outputs" / f"production_dc_factory_outputs_by_material_{safe_dc}.png",
            f"production_dc_factory_outputs_by_material_{safe_dc}.png",
        )
        outgoing = None
        third = None
        if incoming is None and dc_stock_rows:
            per_item_stock: dict[str, list[tuple[int, float]]] = {}
            item_ids = sorted(
                {str(row.get("item_id") or "") for row in dc_stock_rows if str(row.get("node_id") or "") == dc_id}
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    dc_stock_rows,
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=dc_id,
                    item_ids={item_id},
                )
                if pts:
                    label = item_labels.get(item_id, compact_item_label(item_id))
                    per_item_stock[f"{label} - stock"] = pts
                    target_pts = aggregate_daily_series(
                        mrp_trace_rows,
                        value_field="target_stock_qty",
                        node_field="node_id",
                        node_id=dc_id,
                        item_ids={item_id},
                    )
                    if target_pts:
                        per_item_stock[f"{label} - cible MRP / delai securite"] = target_pts
            figure = build_line_chart_figure(
                per_item_stock,
                title=f"{dc_id} - stock DC vs cible MRP",
                y_label="Quantite",
            )
            if figure is not None:
                incoming = {"figure": figure}
        if shipment_rows:
            inbound_by_item: dict[str, list[tuple[int, float]]] = {}
            inbound_item_ids = sorted(
                {str(row.get("item_id") or "") for row in shipment_rows if str(row.get("dst_node_id") or "") == dc_id}
            )
            for item_id in inbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    day_field="arrival_day",
                    node_field="dst_node_id",
                    node_id=dc_id,
                    item_ids={item_id},
                )
                if pts:
                    inbound_by_item[item_labels.get(item_id, compact_item_label(item_id))] = pts
            if inbound_by_item:
                figure = build_line_chart_figure(
                    inbound_by_item,
                    title=f"{dc_id} - receptions journalieres par item",
                    y_label="Quantite",
                    step_like=True,
                )
                if figure is not None:
                    outgoing = {"figure": figure}

            outbound_by_item: dict[str, list[tuple[int, float]]] = {}
            outbound_item_ids = sorted(
                {str(row.get("item_id") or "") for row in shipment_rows if str(row.get("src_node_id") or "") == dc_id}
            )
            for item_id in outbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=dc_id,
                    item_ids={item_id},
                )
                if pts:
                    outbound_by_item[item_labels.get(item_id, compact_item_label(item_id))] = pts
            if outbound_by_item:
                figure = build_line_chart_figure(
                    outbound_by_item,
                    title=f"{dc_id} - expeditions journalieres par item",
                    y_label="Quantite",
                    step_like=True,
                )
                if figure is not None:
                    third = {"figure": figure}
        if incoming or outgoing or third:
            out[dc_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
    return out


def build_site_stock_payload(
    raw: dict[str, Any],
    supplier_stocks_csv: Path,
    node_id: str,
    *,
    title: str,
) -> dict[str, Any] | None:
    rows = read_csv_rows(supplier_stocks_csv)
    if not rows:
        return None
    item_labels = item_label_lookup(raw)
    per_item_stock: dict[str, list[tuple[int, float]]] = {}
    item_ids = sorted({str(row.get("item_id") or "") for row in rows if str(row.get("node_id") or "") == node_id})
    for item_id in item_ids:
        if is_simulation_hidden_item(item_id):
            continue
        pts = aggregate_daily_series(
            rows,
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
            item_ids={item_id},
        )
        if pts:
            per_item_stock[item_labels.get(item_id, compact_item_label(item_id))] = pts
    if not per_item_stock:
        return None
    figure = build_line_chart_figure(
        per_item_stock,
        title=title,
        y_label="Quantite",
    )
    if figure is None:
        return None
    return {"figure": figure}


def build_customer_hover_images(
    raw: dict[str, Any],
    demand_service_csv: Path,
    shipments_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = read_csv_rows(demand_service_csv)
    if not rows:
        return {}, {}
    shipment_rows = read_csv_rows(shipments_csv)

    customer_ids = sorted(
        str(n.get("id"))
        for n in (raw.get("nodes", []) or [])
        if str(n.get("type") or "") == "customer"
    )
    customer_hover: dict[str, Any] = {}
    customer_metrics: dict[str, Any] = {}
    for customer_id in customer_ids:
        customer_rows = [row for row in rows if str(row.get("node_id") or "") == customer_id]
        if not customer_rows:
            continue
        demand_series = aggregate_daily_series(customer_rows, value_field="demand_qty")
        demand_series_by_item: dict[str, dict[int, float]] = {}
        for item_id in sorted({str(row.get("item_id") or "") for row in customer_rows if str(row.get("item_id") or "")}):
            if is_simulation_hidden_item(item_id):
                continue
            scoped_rows = [row for row in customer_rows if str(row.get("item_id") or "") == item_id]
            scoped_series = aggregate_daily_series(scoped_rows, value_field="demand_qty")
            if scoped_series:
                demand_series_by_item[compact_item_label(item_id)] = scoped_series
        served_series = aggregate_daily_series(customer_rows, value_field="served_qty")
        backlog_series = aggregate_daily_series(customer_rows, value_field="backlog_end_qty")
        incoming_series = {"Demande totale": demand_series}
        incoming_series.update(demand_series_by_item)
        incoming = build_line_chart_payload(
            incoming_series,
            title=f"{customer_id} - demande dans le temps",
            y_label="Quantite",
            filename=f"{safe_case_token(customer_id)}_customer_demand.png",
        )
        if incoming is None:
            figure = build_line_chart_figure(
                incoming_series,
                title=f"{customer_id} - demande dans le temps",
                y_label="Quantite",
            )
            if figure is not None:
                incoming = {"figure": figure}
        outgoing = build_line_chart_payload(
            {
                "Servi": served_series,
                "Backlog": backlog_series,
            },
            title=f"{customer_id} - servi et backlog dans le temps",
            y_label="Quantite",
            filename=f"{safe_case_token(customer_id)}_customer_service_backlog.png",
        )
        if outgoing is None:
            figure = build_line_chart_figure(
                {
                    "Servi": served_series,
                    "Backlog": backlog_series,
                },
                title=f"{customer_id} - servi et backlog dans le temps",
                y_label="Quantite",
            )
            if figure is not None:
                outgoing = {"figure": figure}

        latest_day = max((int(to_float(row.get("day")) or 0) for row in customer_rows), default=0)
        latest_rows = [row for row in customer_rows if int(to_float(row.get("day")) or 0) == latest_day]
        latest_demand_by_item: dict[str, float] = defaultdict(float)
        latest_backlog_total = 0.0
        latest_served_total = 0.0
        latest_demand_total = 0.0
        for row in latest_rows:
            item_id = str(row.get("item_id") or "")
            demand_value = float(to_float(row.get("demand_qty")) or 0.0)
            latest_demand_by_item[item_id] += demand_value
            latest_demand_total += demand_value
            latest_served_total += float(to_float(row.get("served_qty")) or 0.0)
            latest_backlog_total += float(to_float(row.get("backlog_end_qty")) or 0.0)
        inbound_by_item: dict[str, list[tuple[int, float]]] = {}
        if shipment_rows:
            inbound_item_ids = sorted(
                {str(row.get("item_id") or "") for row in shipment_rows if str(row.get("dst_node_id") or "") == customer_id}
            )
            for item_id in inbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                scoped_rows = [
                    row
                    for row in shipment_rows
                    if str(row.get("dst_node_id") or "") == customer_id and str(row.get("item_id") or "") == item_id
                ]
                pts = aggregate_daily_series(
                    scoped_rows,
                    value_field="shipped_qty",
                    day_field="arrival_day",
                )
                if pts:
                    inbound_by_item[compact_item_label(item_id)] = pts
        third = None
        if inbound_by_item:
            third = build_line_chart_payload(
                inbound_by_item,
                title=f"{customer_id} - receptions client par item",
                y_label="Quantite",
                filename=f"{safe_case_token(customer_id)}_customer_receipts.png",
            )
            if third is None:
                figure = build_line_chart_figure(
                    inbound_by_item,
                    title=f"{customer_id} - receptions client par item",
                    y_label="Quantite",
                    step_like=True,
                )
                if figure is not None:
                    third = {"figure": figure}
        if third is None:
            third = build_bar_chart_payload(
                {compact_item_label(item_id): value for item_id, value in latest_demand_by_item.items()},
                title=f"{customer_id} - demande du dernier jour par produit",
                y_label="Demande jour courant",
                filename=f"{safe_case_token(customer_id)}_customer_latest_demand.png",
            )
        if third is None:
            figure = build_bar_chart_figure(
                {compact_item_label(item_id): value for item_id, value in latest_demand_by_item.items()},
                title=f"{customer_id} - demande du dernier jour par produit",
                y_label="Demande jour courant",
            )
            if figure is not None:
                third = {"figure": figure}
        if incoming or outgoing or third:
            customer_hover[customer_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
        customer_metrics[customer_id] = {
            "summary_lines": [
                metric_label_value("Jour courant", str(latest_day)),
                metric_label_value("Demande jour courant", f"{latest_demand_total:,.1f}".replace(",", " ")),
                metric_label_value("Servi jour courant", f"{latest_served_total:,.1f}".replace(",", " ")),
                metric_label_value("Backlog courant", f"{latest_backlog_total:,.1f}".replace(",", " ")),
                metric_label_value(
                    "Produits demandes",
                    ", ".join(
                        f"{compact_item_label(item_id)}={value:.1f}"
                        for item_id, value in sorted(latest_demand_by_item.items())
                    )
                    or "n/a",
                ),
            ]
        }
    return customer_hover, customer_metrics


def build_global_kpi_tree_payload(
    daily_kpi_csv: Path,
    demand_service_csv: Path,
    production_constraint_csv: Path,
) -> dict[str, Any] | None:
    daily_rows = read_csv_rows(daily_kpi_csv)
    demand_rows = read_csv_rows(demand_service_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    if not daily_rows and not demand_rows and not constraint_rows:
        return None

    daily_by_day: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in daily_rows:
        day = int(to_float(row.get("day")) or 0)
        for field in [
            "demand",
            "served",
            "backlog_end",
            "inventory_total",
            "holding_cost_day",
            "warehouse_operating_cost_day",
            "inventory_risk_cost_day",
            "transport_cost_day",
            "purchase_cost_day",
            "external_procured_ordered_qty",
            "supplier_capacity_binding_qty",
        ]:
            daily_by_day[day][field] += max(0.0, to_float(row.get(field)) or 0.0)

    production_by_day: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in constraint_rows:
        day = int(to_float(row.get("day")) or 0)
        production_by_day[day]["desired_qty"] += max(0.0, to_float(row.get("desired_qty")) or 0.0)
        production_by_day[day]["actual_qty"] += max(0.0, to_float(row.get("actual_qty")) or 0.0)
        production_by_day[day]["shortfall_qty"] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        if str(row.get("binding_cause") or "") == "input_shortage":
            production_by_day[day]["input_shortage_day"] = 1.0
        if str(row.get("binding_cause") or "") == "capacity":
            production_by_day[day]["capacity_day"] = 1.0

    demand_by_day: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in demand_rows:
        day = int(to_float(row.get("day")) or 0)
        demand_by_day[day]["demand_qty"] += max(0.0, to_float(row.get("demand_qty")) or 0.0)
        demand_by_day[day]["served_qty"] += max(0.0, to_float(row.get("served_qty")) or 0.0)
        demand_by_day[day]["backlog_end_qty"] += max(0.0, to_float(row.get("backlog_end_qty")) or 0.0)

    days = sorted(set(daily_by_day) | set(production_by_day) | set(demand_by_day))
    if not days:
        return None

    def series_from_map(values: dict[int, float]) -> dict[str, Any]:
        return {
            "days": days,
            "values": [round(float(values.get(day, 0.0)), 6) for day in days],
        }

    demand_qty = {day: demand_by_day[day].get("demand_qty", daily_by_day[day].get("demand", 0.0)) for day in days}
    served_qty = {day: demand_by_day[day].get("served_qty", daily_by_day[day].get("served", 0.0)) for day in days}
    backlog_qty = {day: demand_by_day[day].get("backlog_end_qty", daily_by_day[day].get("backlog_end", 0.0)) for day in days}
    service_score = {
        day: (100.0 * served_qty[day] / demand_qty[day] if demand_qty[day] > 0 else 100.0)
        for day in days
    }

    desired_qty = {day: production_by_day[day].get("desired_qty", 0.0) for day in days}
    actual_qty = {day: production_by_day[day].get("actual_qty", 0.0) for day in days}
    shortfall_qty = {day: production_by_day[day].get("shortfall_qty", 0.0) for day in days}
    adherence_score = {
        day: (100.0 * actual_qty[day] / desired_qty[day] if desired_qty[day] > 0 else 100.0)
        for day in days
    }

    inventory_cost = {
        day: daily_by_day[day].get("holding_cost_day", 0.0)
        + daily_by_day[day].get("warehouse_operating_cost_day", 0.0)
        + daily_by_day[day].get("inventory_risk_cost_day", 0.0)
        for day in days
    }
    transport_cost = {day: daily_by_day[day].get("transport_cost_day", 0.0) for day in days}
    purchase_cost = {day: daily_by_day[day].get("purchase_cost_day", 0.0) for day in days}
    logistics_cost = {day: inventory_cost[day] + transport_cost[day] for day in days}
    positive_costs = [value for value in logistics_cost.values() if value > 0]
    avg_logistics_cost = sum(positive_costs) / len(positive_costs) if positive_costs else 1.0
    cost_index = {day: 100.0 * logistics_cost[day] / avg_logistics_cost for day in days}

    total_demand = sum(demand_qty.values())
    total_served = sum(served_qty.values())
    total_desired = sum(desired_qty.values())
    total_actual = sum(actual_qty.values())
    total_shortfall = sum(shortfall_qty.values())
    backlog_days = sum(1 for value in backlog_qty.values() if value > 1e-9)
    input_shortage_days = sum(1 for day in days if production_by_day[day].get("input_shortage_day", 0.0) > 0)
    capacity_days = sum(1 for day in days if production_by_day[day].get("capacity_day", 0.0) > 0)
    total_logistics_cost = sum(logistics_cost.values())
    total_inventory_cost = sum(inventory_cost.values())
    total_transport_cost = sum(transport_cost.values())
    total_purchase_cost = sum(purchase_cost.values())

    def summary(label: str, value: str) -> dict[str, str]:
        return {"label": label, "value": value}

    return {
        "kind": "kpi_tree",
        "title": "Arborescence KPI management supply",
        "subtitle": "Clique une courbe KPI principale pour afficher ses KPI secondaires.",
        "main": {
            "days": days,
            "series": [
                {
                    "id": "availability",
                    "label": "Disponibilite produit",
                    "values": [round(service_score[day], 6) for day in days],
                    "color": "#0f766e",
                    "note": "Score service journalier: servi / demande. Objectif: 100% et backlog quotidien nul.",
                },
                {
                    "id": "production",
                    "label": "Adherence production",
                    "values": [round(adherence_score[day], 6) for day in days],
                    "color": "#2563eb",
                    "note": "Score adherence: production reelle / production demandee.",
                },
                {
                    "id": "cost",
                    "label": "Pression cout supply",
                    "values": [round(cost_index[day], 6) for day in days],
                    "color": "#d97706",
                    "note": "Indice cout logistique journalier, base 100 = moyenne du run. Plus bas est meilleur.",
                },
            ],
            "y_label": "Score / indice",
        },
        "groups": [
            {
                "id": "availability",
                "label": "Disponibilite produit",
                "objective": "Suppression des ruptures pour les patients.",
                "summary": [
                    summary("Fill rate cumule", fmt_pct(100.0 * total_served / total_demand if total_demand else 100.0)),
                    summary("Jours avec backlog", str(backlog_days)),
                    summary("Backlog max", fmt_qty(max(backlog_qty.values()) if backlog_qty else 0.0)),
                    summary("Demande cumulee", fmt_qty(total_demand)),
                ],
                "secondary": [
                    {"label": "Demande", **series_from_map(demand_qty), "color": "#475569"},
                    {"label": "Servi", **series_from_map(served_qty), "color": "#0f766e"},
                    {"label": "Backlog fin de jour", **series_from_map(backlog_qty), "color": "#dc2626"},
                ],
                "secondary_y_label": "Quantite",
            },
            {
                "id": "production",
                "label": "Adherence production usine",
                "objective": "Reduire la nervosite usine et les replanifications dues aux ruptures composants.",
                "summary": [
                    summary("Adherence cumulee", fmt_pct(100.0 * total_actual / total_desired if total_desired else 100.0)),
                    summary("Manque production", fmt_qty(total_shortfall)),
                    summary("Jours input shortage", str(input_shortage_days)),
                    summary("Jours capacite", str(capacity_days)),
                ],
                "secondary": [
                    {"label": "Production demandee", **series_from_map(desired_qty), "color": "#475569"},
                    {"label": "Production reelle", **series_from_map(actual_qty), "color": "#2563eb"},
                    {"label": "Manque production", **series_from_map(shortfall_qty), "color": "#dc2626"},
                ],
                "secondary_y_label": "Quantite",
            },
            {
                "id": "cost",
                "label": "Couts stock / transport",
                "objective": "Eviter les stocks excessifs et les transports d'urgence pour compenser les risques.",
                "summary": [
                    summary("Cout logistique", fmt_qty(total_logistics_cost)),
                    summary("Cout stock", fmt_qty(total_inventory_cost)),
                    summary("Cout transport", fmt_qty(total_transport_cost)),
                    summary("Cout achat", fmt_qty(total_purchase_cost)),
                ],
                "secondary": [
                    {"label": "Cout stock", **series_from_map(inventory_cost), "color": "#7c3aed"},
                    {"label": "Cout transport", **series_from_map(transport_cost), "color": "#d97706"},
                    {"label": "Cout achat", **series_from_map(purchase_cost), "color": "#475569"},
                ],
                "secondary_y_label": "Cout / quantite",
            },
        ],
    }


def normalize_unit_label(unit: Any) -> str:
    value = str(unit or "").strip().upper()
    aliases = {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITS": "UN",
    }
    return aliases.get(value, value)


def convert_unit_quantity(value: float, from_unit: str, to_unit: str) -> float:
    src = normalize_unit_label(from_unit)
    dst = normalize_unit_label(to_unit)
    if not src or not dst or src == dst:
        return value
    if src == "G" and dst == "KG":
        return value / 1000.0
    if src == "KG" and dst == "G":
        return value * 1000.0
    return value


def build_material_balance_table_rows(
    raw: dict[str, Any],
    *,
    demand_service_csv: Path,
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    supplier_shipments_csv: Path,
    safety_reference_csv: Path | None = None,
) -> list[dict[str, Any]]:
    item_labels = build_item_label_lookup(raw)
    node_type_by_id = build_node_type_lookup(raw)
    demand_rows = read_csv_rows(demand_service_csv)
    input_rows = read_csv_rows(sim_input_stocks_csv)
    output_rows = read_csv_rows(sim_output_products_csv)
    shipment_rows = read_csv_rows(supplier_shipments_csv)
    safety_reference_rows = read_csv_rows(safety_reference_csv) if safety_reference_csv else []
    safety_reference_by_pair: dict[tuple[str, str], dict[str, Any]] = {
        (str(row.get("node_id") or ""), str(row.get("item_id") or "")): row
        for row in safety_reference_rows
        if str(row.get("node_id") or "") and str(row.get("item_id") or "")
    }
    max_day = max(
        [
            int(to_float(row.get("day")) or 0)
            for dataset in (demand_rows, input_rows, output_rows, shipment_rows)
            for row in dataset
        ]
        or [0]
    )
    sim_days = max(1, max_day + 1)

    demand_total_by_item: dict[str, float] = defaultdict(float)
    served_total_by_item: dict[str, float] = defaultdict(float)
    for row in demand_rows:
        if str(row.get("node_id") or "") not in {
            node_id for node_id, node_type in node_type_by_id.items() if node_type == "customer"
        }:
            continue
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        demand_total_by_item[item_id] += max(0.0, to_float(row.get("demand_qty")) or 0.0)
        served_total_by_item[item_id] += max(0.0, to_float(row.get("served_qty")) or 0.0)

    produced_total_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    latest_output_stock_by_pair: dict[tuple[str, str], tuple[int, float]] = {}
    for row in output_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        produced_total_by_pair[(node_id, item_id)] += max(0.0, to_float(row.get("produced_qty")) or 0.0)
        day = int(to_float(row.get("day")) or 0)
        stock_value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        key = (node_id, item_id)
        prev = latest_output_stock_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_output_stock_by_pair[key] = (day, stock_value)

    latest_input_stock_by_pair: dict[tuple[str, str], tuple[int, float]] = {}
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        stock_value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        key = (node_id, item_id)
        prev = latest_input_stock_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_input_stock_by_pair[key] = (day, stock_value)

    shipped_total_to_pair: dict[tuple[str, str], float] = defaultdict(float)
    shipped_total_from_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in shipment_rows:
        src_node_id = str(row.get("src_node_id") or "")
        node_id = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        shipped_qty = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        shipped_total_to_pair[(node_id, item_id)] += shipped_qty
        if src_node_id:
            shipped_total_from_pair[(src_node_id, item_id)] += shipped_qty

    initial_stock_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    unit_by_pair: dict[tuple[str, str], str] = {}
    pf_initial_by_item: dict[str, float] = defaultdict(float)
    pf_unit_by_item: dict[str, str] = {}
    safety_policy_by_pair: dict[tuple[str, str], dict[str, float]] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        for state in (((node.get("inventory") or {}).get("states") or [])):
            item_id = str(state.get("item_id") or "")
            if not item_id:
                continue
            initial_qty = max(0.0, to_float(state.get("initial")) or 0.0)
            key = (node_id, item_id)
            initial_stock_by_pair[key] += initial_qty
            unit = normalize_unit_label(state.get("uom"))
            if unit and key not in unit_by_pair:
                unit_by_pair[key] = unit
            if node_type in {"distribution_center", "customer"}:
                pf_initial_by_item[item_id] += initial_qty
                if unit and item_id not in pf_unit_by_item:
                    pf_unit_by_item[item_id] = unit
            mrp_policy = state.get("mrp_policy") or {}
            safety_time_days = max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0)
            safety_stock_qty = 0.0
            if safety_time_days > 0.0:
                safety_policy_by_pair[key] = {
                    "safety_time_days": safety_time_days,
                    "safety_stock_qty": safety_stock_qty,
                }

    material_rows_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        for proc in (node.get("processes") or []):
            batch_size = max(1.0, to_float(proc.get("batch_size")) or 1.0)
            outputs = [out for out in (proc.get("outputs") or []) if str(out.get("item_id") or "")]
            inputs = [inp for inp in (proc.get("inputs") or []) if str(inp.get("item_id") or "")]
            if not outputs or not inputs:
                continue
            for out in outputs:
                out_item = str(out.get("item_id") or "")
                full_demand_qty = demand_total_by_item.get(out_item, 0.0)
                actual_prod_qty = produced_total_by_pair.get((node_id, out_item), 0.0)
                if full_demand_qty <= 0.0 and actual_prod_qty <= 0.0:
                    continue
                for inp in inputs:
                    input_item = str(inp.get("item_id") or "")
                    if is_simulation_hidden_item(input_item):
                        continue
                    ratio_qty = max(0.0, to_float(inp.get("ratio_per_batch")) or 0.0)
                    ratio_unit = normalize_unit_label(inp.get("ratio_unit"))
                    pair_key = (node_id, input_item)
                    unit = unit_by_pair.get(pair_key) or ratio_unit or ""
                    need_qty = convert_unit_quantity((ratio_qty / batch_size) * full_demand_qty, ratio_unit, unit)
                    consumed_qty = convert_unit_quantity((ratio_qty / batch_size) * actual_prod_qty, ratio_unit, unit)
                    bucket = material_rows_by_pair.setdefault(
                        pair_key,
                        {
                            "scope": "material",
                            "scope_label": "Matiere",
                            "node_id": node_id,
                            "item_id": input_item,
                            "item_label": item_labels.get(input_item, compact_item_label(input_item)),
                            "node_label": display_node_label(node_id),
                            "planned_qty": 0.0,
                            "initial_qty": initial_stock_by_pair.get(pair_key, 0.0),
                            "delivered_qty": shipped_total_to_pair.get(pair_key, 0.0),
                            "consumed_qty": 0.0,
                            "final_stock_qty": (latest_input_stock_by_pair.get(pair_key) or (0, 0.0))[1],
                            "unit": unit or ratio_unit or "",
                        },
                    )
                    bucket["planned_qty"] += need_qty
                    bucket["consumed_qty"] += consumed_qty

    rows: list[dict[str, Any]] = []
    for item_id in sorted(demand_total_by_item):
        pf_policy_pair = next(
            (
                pair
                for pair in sorted(safety_policy_by_pair)
                if pair[1] == item_id and node_type_by_id.get(pair[0]) in {"distribution_center", "customer"}
            ),
            ("DC / client final", item_id),
        )
        rows.append(
            {
                "scope": "pf",
                "scope_label": "PF",
                "node_id": pf_policy_pair[0],
                "item_id": item_id,
                "item_label": item_labels.get(item_id, compact_item_label(item_id)),
                "node_label": "DC / client final",
                "planned_qty": demand_total_by_item.get(item_id, 0.0),
                "initial_qty": pf_initial_by_item.get(item_id, 0.0),
                "delivered_qty": served_total_by_item.get(item_id, 0.0),
                "consumed_qty": served_total_by_item.get(item_id, 0.0),
                "unit": pf_unit_by_item.get(item_id, ""),
                "gap_vs_need_qty": served_total_by_item.get(item_id, 0.0) - demand_total_by_item.get(item_id, 0.0),
                "diagnostic": "demande finale issue du scenario courant",
            }
        )

    upstream_pfi_rows_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not is_upstream_internal_site(node_id):
            continue
        output_item_ids: set[str] = set()
        for proc in (node.get("processes") or []):
            for out in (proc.get("outputs") or []):
                item_id = str(out.get("item_id") or "")
                if item_id:
                    output_item_ids.add(item_id)
        for pair_key in list(shipped_total_from_pair.keys()):
            pair_node_id, item_id = pair_key
            if pair_node_id == node_id and item_id:
                output_item_ids.add(item_id)
        for item_id in sorted(output_item_ids):
            pair_key = (node_id, item_id)
            produced_qty = produced_total_by_pair.get(pair_key, 0.0)
            shipped_qty = shipped_total_from_pair.get(pair_key, 0.0)
            initial_qty = initial_stock_by_pair.get(pair_key, 0.0)
            final_stock_qty = (latest_output_stock_by_pair.get(pair_key) or (0, 0.0))[1]
            if produced_qty <= 0.0 and shipped_qty <= 0.0 and initial_qty <= 0.0 and final_stock_qty <= 0.0:
                continue
            upstream_pfi_rows_by_pair[pair_key] = {
                "scope": "pfi",
                "scope_label": "PFI",
                "node_id": node_id,
                "item_id": item_id,
                "item_label": item_labels.get(item_id, compact_item_label(item_id)),
                "node_label": display_node_label(node_id),
                "planned_qty": max(produced_qty, shipped_qty),
                "initial_qty": initial_qty,
                "delivered_qty": shipped_qty,
                "consumed_qty": produced_qty,
                "final_stock_qty": final_stock_qty,
                "unit": unit_by_pair.get(pair_key, ""),
                "gap_vs_need_qty": shipped_qty - max(produced_qty, shipped_qty),
                "diagnostic": "sortie PFI du centre interne D-1450 vers les usines aval",
            }
    rows.extend(
        row for _, row in sorted(upstream_pfi_rows_by_pair.items(), key=lambda item: (item[0][0], item[0][1]))
    )

    for pair_key, row in sorted(material_rows_by_pair.items(), key=lambda item: (item[0][0], item[0][1])):
        if is_simulation_hidden_item(str(row.get("item_id") or "")):
            continue
        initial_qty = max(0.0, row.get("initial_qty") or 0.0)
        delivered_qty = max(0.0, row.get("delivered_qty") or 0.0)
        consumed_qty = max(0.0, row.get("consumed_qty") or 0.0)
        final_stock_qty = max(0.0, row.get("final_stock_qty") or 0.0)
        planned_qty = max(0.0, row.get("planned_qty") or 0.0)
        gap_vs_need_qty = consumed_qty - planned_qty
        balance_gap = (initial_qty + delivered_qty) - consumed_qty - final_stock_qty
        tol = max(1.0, abs(consumed_qty) * 0.02)
        if consumed_qty <= 1e-9 and delivered_qty <= 1e-9 and initial_qty > 0:
            diagnostic = "coherent dormant: stock initial couvre le run"
        elif abs(balance_gap) > tol:
            diagnostic = "stock balance mismatch vs BOM consumption"
        elif delivered_qty > 0.0 or consumed_qty > 0.0:
            diagnostic = "active on current run"
        else:
            diagnostic = "inactive on current run"
        rows.append(
            {
                **row,
                "gap_vs_need_qty": gap_vs_need_qty,
                "diagnostic": diagnostic,
            }
        )

    for row in rows:
        pair = (str(row.get("node_id") or ""), str(row.get("item_id") or ""))
        safety_reference = safety_reference_by_pair.get(pair) or {}
        safety_policy = safety_policy_by_pair.get(pair) or {}
        safety_days = max(
            0.0,
            (
                to_float(safety_reference.get("safety_time_days"))
                if safety_reference
                else to_float(safety_policy.get("safety_time_days"))
            )
            or 0.0,
        )
        explicit_safety_stock = max(
            0.0,
            (
                to_float(safety_reference.get("explicit_safety_stock_qty"))
                if safety_reference
                else to_float(safety_policy.get("safety_stock_qty"))
            )
            or 0.0,
        )
        avg_daily_need = max(
            0.0,
            (
                to_float(safety_reference.get("planned_avg_daily_demand_qty"))
                if safety_reference
                else (max(0.0, to_float(row.get("planned_qty")) or 0.0) / float(sim_days))
            )
            or 0.0,
        )
        stock_equiv_safety = max(
            0.0,
            (
                to_float(safety_reference.get("stock_equiv_safety_time_qty"))
                if safety_reference
                else avg_daily_need * safety_days
            )
            or 0.0,
        )
        row["avg_daily_need_qty"] = avg_daily_need
        row["safety_time_days"] = safety_days
        row["stock_equiv_safety_time_qty"] = stock_equiv_safety
        row["explicit_safety_stock_qty"] = explicit_safety_stock
        row["effective_reference_stock_qty"] = max(
            explicit_safety_stock,
            stock_equiv_safety,
            (to_float(safety_reference.get("effective_reference_stock_qty")) if safety_reference else 0.0) or 0.0,
        )
    return rows


def render_material_balance_table_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan='13'>Aucune ligne de bilan disponible.</td></tr>"
    html_rows: list[str] = []
    for row in rows:
        scope = str(row.get("scope") or "")
        if scope == "pf":
            badge_class = "scopeBadge scopeFinal"
        elif scope == "pfi":
            badge_class = "scopeBadge scopeIntermediate"
        else:
            badge_class = "scopeBadge"
        html_rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td><span class=\"{badge_class}\">{html.escape(str(row.get('scope_label') or ''))}</span></td>",
                    f"<td>{html.escape(compact_item_label(str(row.get('item_id') or '')))}</td>",
                    f"<td>{html.escape(str(row.get('node_label') or ''))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('planned_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('avg_daily_need_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('safety_time_days'), 1))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('stock_equiv_safety_time_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('initial_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('delivered_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('consumed_qty'), 3))}</td>",
                    f"<td class=\"num\">{html.escape(fmt_qty(row.get('gap_vs_need_qty'), 3))}</td>",
                    f"<td>{html.escape(str(row.get('unit') or ''))}</td>",
                    f"<td>{html.escape(str(row.get('diagnostic') or ''))}</td>",
                    "</tr>",
                ]
            )
        )
    return "".join(html_rows)


def render_order_ledger_html(
    node_id: str,
    node_orders: list[dict[str, str]],
    item_labels: dict[str, str],
    empty_reason: str | None = None,
) -> str:
    if not node_orders:
        reason_html = (
            f"<div class=\"orderLedgerStatus\">{html.escape(empty_reason)}</div>"
            if empty_reason else ""
        )
        return (
            "<div class=\"factoryHtmlPanelContent\">"
            f"{reason_html}"
            "<div class=\"panelEmptyState\">Aucun ordre MRP journalise pour ce noeud.</div>"
            "</div>"
        )

    sorted_orders = sorted(
        node_orders,
        key=lambda r: (
            int(to_float(r.get("day")) or 0),
            str(r.get("item_id") or ""),
            str(r.get("edge_id") or ""),
        ),
        reverse=True,
    )
    status_counts: dict[str, int] = defaultdict(int)
    for row in sorted_orders:
        status_parts = [
            f"plan={str(row.get('planning_status') or 'n/a')}",
            f"release={str(row.get('release_status') or 'n/a')}",
            f"receipt={str(row.get('receipt_status') or 'n/a')}",
            f"run={str(row.get('order_status_end_of_run') or 'n/a')}",
        ]
        status_counts[" | ".join(status_parts)] += 1

    recent_lines: list[str] = []
    for row in sorted_orders[:120]:
        day = int(to_float(row.get("day")) or 0)
        item_id = str(row.get("item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        mode_label = str(row.get("source_mode") or row.get("order_type") or "n/a")
        exception_flags = [
            flag
            for flag in [
                str(row.get("planning_status") or ""),
                str(row.get("release_status") or ""),
                str(row.get("receipt_status") or ""),
                str(row.get("order_status_end_of_run") or ""),
            ]
            if flag and flag not in {"planned_and_released", "released", "firm_receipt", "received"}
        ]
        recent_lines.append(
            " | ".join(
                [
                    f"j{day}",
                    item_label,
                    mode_label,
                    f"release={fmt_qty(row.get('release_qty'), 1)}",
                    f"receipt={fmt_qty(row.get('planned_receipt_qty'), 1)}",
                    f"arrival={row.get('arrival_day') or 'n/a'}",
                    f"status={row.get('order_status_end_of_run') or 'n/a'}",
                    f"exceptions={','.join(exception_flags) if exception_flags else 'none'}",
                ]
            )
        )

    title_suffix = "carnet d'ordres fournisseur" if node_id.startswith("SDC-") else "carnet d'ordres"
    statuses_text = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items())) or "aucun"
    recent_orders_html = html.escape("\n".join(recent_lines) if recent_lines else "aucun ordre journalise")

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - {html.escape(title_suffix)}</div>",
            f"<div class=\"orderLedgerStatus\">Statuses: {html.escape(statuses_text)}</div>",
            "<div class=\"orderLedgerSectionTitle\">Derniers ordres:</div>",
            "<div class=\"orderLedgerTextWrap\">",
            f"<pre class=\"orderLedgerLines\">{recent_orders_html}</pre>",
            "</div>",
            "</div>",
        ]
    )


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_edge_item_sets(raw: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incoming_items: dict[str, set[str]] = defaultdict(set)
    outgoing_items: dict[str, set[str]] = defaultdict(set)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        for item_id in edge.get("items") or []:
            item = str(item_id)
            if src:
                outgoing_items[src].add(item)
            if dst:
                incoming_items[dst].add(item)
    return incoming_items, outgoing_items


def build_node_type_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        out[node_id] = str(node.get("type") or "")
    return out


def build_node_relationships(raw: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incoming_sources: dict[str, set[str]] = defaultdict(set)
    outgoing_targets: dict[str, set[str]] = defaultdict(set)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if not src or not dst:
            continue
        incoming_sources[dst].add(src)
        outgoing_targets[src].add(dst)
    return incoming_sources, outgoing_targets


def sensitivity_row_scope(
    parameter_key: str,
    node_id: str,
    node_item_ids: dict[str, set[str]],
    node_types: dict[str, str],
    incoming_sources: dict[str, set[str]],
    outgoing_targets: dict[str, set[str]],
) -> str | None:
    if parameter_key.endswith(f"::{node_id}"):
        return "direct"
    if parameter_key.startswith("demand_item::"):
        item_id = parameter_key.split("::", 1)[1]
        if item_id in node_item_ids.get(node_id, set()):
            return "item"
        return None

    if "::" not in parameter_key:
        return None
    _, target = parameter_key.split("::", 1)
    node_type = node_types.get(node_id, "")

    if node_type == "factory" and target in incoming_sources.get(node_id, set()):
        if parameter_key.startswith("edge_src_lead_time_scale::") or parameter_key.startswith("supplier_lead_time_node::"):
            return "upstream_lead_time"
        if parameter_key.startswith("edge_src_reliability_scale::") or parameter_key.startswith(
            "supplier_reliability_node::"
        ):
            return "upstream_reliability"
        if parameter_key.startswith("supplier_capacity_node::"):
            return "upstream_supplier_capacity"
        if parameter_key.startswith("supplier_node_scale::"):
            return "upstream_supplier_stock"

    if node_type == "distribution_center" and target in incoming_sources.get(node_id, set()):
        if parameter_key.startswith("capacity_node::"):
            return "upstream_factory_capacity"
        if parameter_key.startswith("edge_src_lead_time_scale::"):
            return "upstream_factory_lead_time"
        if parameter_key.startswith("edge_src_reliability_scale::"):
            return "upstream_factory_reliability"

    if node_type == "supplier_dc" and target in outgoing_targets.get(node_id, set()):
        if parameter_key.startswith("demand_item::"):
            return "downstream_demand"

    return None


def aggregate_daily_series(
    rows: list[dict[str, str]],
    *,
    value_field: str,
    day_field: str = "day",
    node_field: str | None = None,
    node_id: str | None = None,
    item_ids: set[str] | None = None,
) -> list[tuple[int, float]]:
    by_day: dict[int, float] = defaultdict(float)
    for row in rows:
        if node_field and node_id is not None and str(row.get(node_field) or "") != node_id:
            continue
        item_id = str(row.get("item_id") or "")
        if item_ids is not None and item_id not in item_ids:
            continue
        day = int(to_float(row.get(day_field)) or 0)
        value = float(to_float(row.get(value_field)) or 0.0)
        by_day[day] += value
    return sorted(by_day.items(), key=lambda it: it[0])


def densify_daily_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    if not points:
        return []
    by_day = {int(day): float(value) for day, value in points}
    start_day = min(by_day)
    end_day = max(by_day)
    return [(day, by_day.get(day, 0.0)) for day in range(start_day, end_day + 1)]


def build_line_chart_payload(
    series_map: dict[str, list[tuple[int, float]]],
    *,
    title: str,
    y_label: str,
    filename: str,
) -> dict[str, Any] | None:
    usable = {label: pts for label, pts in series_map.items() if pts}
    if not usable:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    colors = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569"]
    fig, ax = plt.subplots(figsize=(9.8, 4.8))
    for idx, (label, points) in enumerate(usable.items()):
        days = [p[0] for p in points]
        values = [p[1] for p in points]
        ax.plot(
            days,
            values,
            label=label,
            linewidth=2.1,
            color=colors[idx % len(colors)],
        )

    ax.set_title(title, fontsize=12, pad=10)
    ax.set_xlabel("Jour")
    ax.set_ylabel(y_label)
    ax.grid(True, which="major", color="#e2e8f0", linewidth=0.9)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    ax.legend(loc="best", fontsize=8.5, frameon=False)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_line_chart_figure(
    series_map: dict[str, list[tuple[int, float]]],
    *,
    title: str,
    y_label: str,
    step_like: bool = False,
    note: str | None = None,
    series_styles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    usable = {
        label: (densify_daily_series(pts) if step_like else pts)
        for label, pts in series_map.items()
        if pts
    }
    if not usable:
        return None
    return {
        "kind": "line_multi",
        "title": title,
        "y_label": y_label,
        "step_like": step_like,
        "note": note or "",
        "series": [
            {
                "label": label,
                "days": [int(day) for day, _ in points],
                "values": [float(value) for _, value in points],
                **(series_styles.get(label, {}) if isinstance(series_styles, dict) else {}),
            }
            for label, points in usable.items()
        ],
    }


def build_dual_line_multi_panel_figure(
    *,
    title: str,
    top_title: str,
    top_y_label: str,
    top_series_map: dict[str, list[tuple[int, float]]],
    bottom_title: str,
    bottom_y_label: str,
    bottom_series_map: dict[str, list[tuple[int, float]]],
    bottom_step_like: bool = False,
) -> dict[str, Any] | None:
    top_figure = build_line_chart_figure(top_series_map, title=top_title, y_label=top_y_label)
    bottom_figure = build_line_chart_figure(
        bottom_series_map,
        title=bottom_title,
        y_label=bottom_y_label,
        step_like=bottom_step_like,
    )
    if top_figure is None and bottom_figure is None:
        return None
    return {
        "kind": "dual_panel_multi",
        "title": title,
        "top": top_figure,
        "bottom": bottom_figure,
    }


def build_bar_chart_figure(
    value_map: dict[str, float | None],
    *,
    title: str,
    y_label: str,
) -> dict[str, Any] | None:
    usable = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    if not usable:
        return None
    return {
        "kind": "bar",
        "title": title,
        "y_label": y_label,
        "labels": [label for label, _ in usable],
        "values": [float(value) for _, value in usable],
    }


def build_dual_panel_figure(
    *,
    title: str,
    top_title: str,
    top_x_label: str,
    top_y_label: str,
    top_kind: str,
    top_x: list[Any],
    top_y: list[float],
    bottom_title: str,
    bottom_x_label: str,
    bottom_y_label: str,
    bottom_kind: str,
    bottom_x: list[Any],
    bottom_y: list[float],
) -> dict[str, Any] | None:
    if not top_x and not bottom_x:
        return None
    return {
        "kind": "dual_panel",
        "title": title,
        "top": {
            "title": top_title,
            "x_label": top_x_label,
            "y_label": top_y_label,
            "kind": top_kind,
            "x": top_x,
            "y": top_y,
        },
        "bottom": {
            "title": bottom_title,
            "x_label": bottom_x_label,
            "y_label": bottom_y_label,
            "kind": bottom_kind,
            "x": bottom_x,
            "y": bottom_y,
        },
    }


def case_rows_by_id(case_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        str(row.get("case_id") or ""): row
        for row in case_rows
        if str(row.get("status") or "").lower() == "ok"
    }


def first_case_row(
    by_case_id: dict[str, dict[str, str]],
    *case_ids: str,
) -> dict[str, str] | None:
    for case_id in case_ids:
        row = by_case_id.get(case_id)
        if row is not None:
            return row
    return None


def baseline_sensitivity_row(by_case_id: dict[str, dict[str, str]]) -> dict[str, str] | None:
    return first_case_row(
        by_case_id,
        "baseline",
        "baseline_baseline_base",
    )


def case_multiplier_value(case_row: dict[str, str] | None) -> float | None:
    if not case_row:
        return None
    return to_float(case_row.get("value")) or to_float(case_row.get("factor_value"))


def case_output_dir(case_row: dict[str, str] | None) -> Path | None:
    if not case_row:
        return None
    raw = str(case_row.get("case_output_dir") or "").strip()
    return Path(raw) if raw else None


def safe_case_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def compact_item_label(item_id: str) -> str:
    raw = str(item_id or "").strip()
    if raw.startswith("item:"):
        return raw.split(":", 1)[1]
    return raw or "n/a"


def kpi_from_case(case_row: dict[str, str] | None, kpi_name: str) -> float | None:
    if not case_row:
        return None
    value = to_float(case_row.get(f"kpi::{kpi_name}"))
    if value is None or math.isnan(value):
        return None
    return value


def build_bar_chart_payload(
    value_map: dict[str, float | None],
    *,
    title: str,
    y_label: str,
    filename: str,
) -> dict[str, Any] | None:
    usable = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    if not usable:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    labels = [label for label, _ in usable]
    values = [float(value) for _, value in usable]
    colors = []
    for label in labels:
        if label == "Base":
            colors.append("#2563eb")
        elif "-" in label:
            colors.append("#d97706")
        else:
            colors.append("#0f766e")

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    bars = ax.bar(labels, values, color=colors, width=0.62)
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_ylabel(y_label)
    ax.grid(True, axis="y", color="#e2e8f0", linewidth=0.9)
    ax.set_axisbelow(True)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    ax.tick_params(axis="x", labelrotation=18)

    ymax = max(values) if values else 0.0
    ymin = min(values) if values else 0.0
    span = max(abs(ymax - ymin), abs(ymax), 1.0)
    pad = span * 0.08
    ax.set_ylim(ymin - pad, ymax + pad)
    for bar, value in zip(bars, values):
        label = f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (pad * 0.15 if value >= 0 else -pad * 0.4),
            label,
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=8.5,
            color="#0f172a",
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_factory_industrial_payload(
    desired_series: list[tuple[int, float]],
    actual_series: list[tuple[int, float]],
    capacity_series: list[tuple[int, float]],
    shortfall_series: list[tuple[int, float]],
    *,
    factory_id: str,
) -> dict[str, Any] | None:
    series_map = {
        "Production demandee": desired_series,
        "Production reelle": actual_series,
        "Capacite": capacity_series,
        "Manque de production": shortfall_series,
    }
    if not any(series_map.values()):
        return None
    payload = build_line_chart_payload(
        series_map,
        title=f"{factory_id} - production desiree / reelle / capacite / manque de production",
        y_label="Quantite",
        filename=f"{safe_case_token(factory_id)}_industrial_constraints.png",
    )
    if payload is not None:
        return payload
    figure = build_line_chart_figure(
        series_map,
        title=f"{factory_id} - production desiree / reelle / capacite / manque de production",
        y_label="Quantite",
    )
    if figure is None:
        return None
    return {"figure": figure}


def build_factory_current_metrics(
    raw: dict[str, Any],
    production_constraint_csv: Path,
) -> dict[str, Any]:
    rows = read_csv_rows(production_constraint_csv)
    if not rows:
        return {}

    inbound_lead_days_by_factory: dict[str, list[float]] = defaultdict(list)
    for edge in raw.get("edges", []) or []:
        dst = str(edge.get("to") or "")
        if not dst:
            continue
        inbound_lead_days_by_factory[dst].append(max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0))

    out: dict[str, Any] = {}
    for factory_id in sorted(factory_like_node_ids(raw)):
        factory_rows = [row for row in rows if str(row.get("node_id") or "") == factory_id]
        if not factory_rows:
            continue
        by_day: dict[int, dict[str, float]] = defaultdict(
            lambda: {
                "desired_qty": 0.0,
                "actual_qty": 0.0,
                "shortfall_qty": 0.0,
                "capacity_binding": 0.0,
            }
        )
        for row in factory_rows:
            day = int(to_float(row.get("day")) or 0)
            by_day[day]["desired_qty"] += max(0.0, to_float(row.get("desired_qty")) or 0.0)
            by_day[day]["actual_qty"] += max(0.0, to_float(row.get("actual_qty")) or 0.0)
            by_day[day]["shortfall_qty"] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
            if str(row.get("binding_cause") or "") == "capacity":
                by_day[day]["capacity_binding"] = 1.0
        total_desired = sum(max(0.0, to_float(row.get("desired_qty")) or 0.0) for row in factory_rows)
        total_actual = sum(max(0.0, to_float(row.get("actual_qty")) or 0.0) for row in factory_rows)
        total_shortfall = sum(max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0) for row in factory_rows)
        peak_shortfall = max((max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0) for row in factory_rows), default=0.0)
        capacity_days = sum(1 for row in factory_rows if str(row.get("binding_cause") or "") == "capacity")
        avg_inbound_lead = (
            sum(inbound_lead_days_by_factory.get(factory_id, [])) / len(inbound_lead_days_by_factory.get(factory_id, []))
            if inbound_lead_days_by_factory.get(factory_id)
            else 0.0
        )
        out[factory_id] = {
            "avg_inbound_lead_days": round(avg_inbound_lead, 4),
            "daily_metrics": [
                {
                    "day": day,
                    "desired_qty": round(values["desired_qty"], 6),
                    "actual_qty": round(values["actual_qty"], 6),
                    "shortfall_qty": round(values["shortfall_qty"], 6),
                    "capacity_binding": int(values["capacity_binding"] > 0),
                }
                for day, values in sorted(by_day.items())
            ],
            "summary_lines": [
                metric_label_value("Production demandee cumulee", f"{total_desired:,.1f}".replace(",", " ")),
                metric_label_value("Production reelle cumulee", f"{total_actual:,.1f}".replace(",", " ")),
                metric_label_value("Manque de production cumule", f"{total_shortfall:,.1f}".replace(",", " ")),
                metric_label_value("Pic de manque de production", f"{peak_shortfall:,.1f}".replace(",", " ")),
                metric_label_value("Jours contraints capacite", str(capacity_days)),
                metric_label_value("Lead time entrant moyen", f"{avg_inbound_lead:.1f} j"),
            ]
        }
    return out


def build_supplier_site_detail_payload(
    supplier_id: str,
    shipped_series: list[tuple[int, float]],
    inbound_lead_days: dict[str, float],
) -> dict[str, Any] | None:
    if not shipped_series and not inbound_lead_days:
        return None
    return {
        "figure": build_dual_panel_figure(
            title=f"{supplier_id} - expeditions et lead times entrants",
            top_title=f"{supplier_id} - expeditions journalieres",
            top_x_label="Jour",
            top_y_label="Expedie",
            top_kind="line",
            top_x=[day for day, _ in shipped_series],
            top_y=[float(value) for _, value in shipped_series],
            bottom_title=f"{supplier_id} - lead time moyen entrants",
            bottom_x_label="Fournisseur amont",
            bottom_y_label="Jours",
            bottom_kind="bar",
            bottom_x=list(inbound_lead_days.keys()),
            bottom_y=[float(inbound_lead_days[label]) for label in inbound_lead_days],
        )
    }


def multiplier_label(value: float | None, fallback: str) -> str:
    if value is None:
        return fallback
    if abs(value - 1.0) <= 1e-9:
        return "Base"
    return f"x{value:.2f}"


def align_series(
    baseline_points: list[tuple[int, float]],
    scenario_points: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    base_map = {day: value for day, value in baseline_points}
    scen_map = {day: value for day, value in scenario_points}
    days = sorted(set(base_map) | set(scen_map))
    return [(day, scen_map.get(day, 0.0) - base_map.get(day, 0.0)) for day in days]


def build_combo_bar_line_payload(
    value_map: dict[str, float | None],
    delta_series_map: dict[str, list[tuple[int, float]]],
    *,
    bar_title: str,
    bar_y_label: str,
    line_title: str,
    line_y_label: str,
    filename: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    usable_bars = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    usable_lines = {label: pts for label, pts in delta_series_map.items() if pts}
    if not usable_bars and not usable_lines:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(9.2, 7.2), gridspec_kw={"height_ratios": [1.0, 1.15]})
    fig.patch.set_facecolor("#ffffff")
    colors = ["#d97706", "#0f766e", "#dc2626", "#7c3aed", "#475569"]

    ax_bar = axes[0]
    if usable_bars:
        labels = [label for label, _ in usable_bars]
        values = [float(value) for _, value in usable_bars]
        bar_colors = []
        for label in labels:
            if label == "Base":
                bar_colors.append("#2563eb")
            elif any(token in label for token in ["x0.", "x0,", "-"]):
                bar_colors.append("#d97706")
            else:
                bar_colors.append("#0f766e")
        bars = ax_bar.bar(labels, values, color=bar_colors, width=0.62)
        ymax = max(values) if values else 0.0
        ymin = min(values) if values else 0.0
        span = max(abs(ymax - ymin), abs(ymax), 1.0)
        pad = span * 0.10
        ax_bar.set_ylim(ymin - pad, ymax + pad)
        for bar, value in zip(bars, values):
            label = f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                value + (pad * 0.10 if value >= 0 else -pad * 0.35),
                label,
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8.3,
                color="#0f172a",
            )
        ax_bar.set_ylabel(bar_y_label)
        ax_bar.tick_params(axis="x", labelrotation=18)
        ax_bar.grid(True, axis="y", color="#e2e8f0", linewidth=0.9)
        ax_bar.set_axisbelow(True)
    else:
        ax_bar.axis("off")
    ax_bar.set_title(bar_title, fontsize=12, pad=10)
    ax_bar.set_facecolor("#ffffff")

    ax_line = axes[1]
    if usable_lines:
        for idx, (label, points) in enumerate(usable_lines.items()):
            days = [p[0] for p in points]
            values = [p[1] for p in points]
            ax_line.plot(
                days,
                values,
                label=label,
                linewidth=2.1,
                color=colors[idx % len(colors)],
            )
        ax_line.axhline(0.0, color="#94a3b8", linewidth=1.0, linestyle="--")
        ax_line.set_xlabel("Jour")
        ax_line.set_ylabel(line_y_label)
        ax_line.grid(True, which="major", color="#e2e8f0", linewidth=0.9)
        ax_line.legend(loc="best", fontsize=8.2, frameon=False)
    else:
        ax_line.axis("off")
    ax_line.set_title(line_title, fontsize=11, pad=8)
    ax_line.set_facecolor("#ffffff")

    if note:
        fig.text(0.5, 0.012, note, ha="center", va="bottom", fontsize=9.5, color="#475569")

    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_note_payload(title: str, message: str, filename: str) -> dict[str, Any] | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.axis("off")
    ax.text(0.5, 0.68, title, ha="center", va="center", fontsize=13, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.38, message, ha="center", va="center", fontsize=11, color="#475569")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def local_signal_strength(
    baseline_row: dict[str, str] | None,
    low_row: dict[str, str] | None,
    high_row: dict[str, str] | None,
) -> tuple[float, float]:
    base_fill = kpi_from_case(baseline_row, "fill_rate") or 0.0
    base_backlog = kpi_from_case(baseline_row, "ending_backlog") or 0.0
    fill_impact = max(
        abs((kpi_from_case(low_row, "fill_rate") or base_fill) - base_fill),
        abs((kpi_from_case(high_row, "fill_rate") or base_fill) - base_fill),
    )
    backlog_impact = max(
        abs((kpi_from_case(low_row, "ending_backlog") or base_backlog) - base_backlog),
        abs((kpi_from_case(high_row, "ending_backlog") or base_backlog) - base_backlog),
    )
    return fill_impact, backlog_impact


def cumulative_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    total = 0.0
    out: list[tuple[int, float]] = []
    for day, value in points:
        total += value
        out.append((day, total))
    return out


def select_best_supplier_case_pair(
    by_case_id: dict[str, dict[str, str]],
    baseline_row: dict[str, str] | None,
    node_id: str,
) -> tuple[str, str, dict[str, str] | None, dict[str, str] | None, float, float]:
    safe_node = safe_case_token(node_id)
    candidates: list[tuple[str, str, dict[str, str] | None, dict[str, str] | None]] = [
        (
            "stock fournisseur local",
            "Stock four.",
            first_case_row(by_case_id, f"supplier_stock_node_{safe_node}_low", f"local_supplier_stock_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_stock_node_{safe_node}_high", f"local_supplier_stock_node_{safe_node}_high"),
        ),
        (
            "lead time sortant local",
            "Lead time",
            first_case_row(by_case_id, f"supplier_lead_time_node_{safe_node}_low", f"local_supplier_lead_time_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_lead_time_node_{safe_node}_high", f"local_supplier_lead_time_node_{safe_node}_high"),
        ),
        (
            "fiabilite locale",
            "OTIF",
            first_case_row(
                by_case_id,
                f"supplier_reliability_node_{safe_node}_low",
                f"local_supplier_reliability_node_{safe_node}_low",
                f"local_supplier_reliability_node_{safe_node}_adverse",
            ),
            first_case_row(by_case_id, f"supplier_reliability_node_{safe_node}_high", f"local_supplier_reliability_node_{safe_node}_high"),
        ),
        (
            "capacite fournisseur locale",
            "Cap. four.",
            first_case_row(by_case_id, f"supplier_capacity_node_{safe_node}_low", f"local_supplier_capacity_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_capacity_node_{safe_node}_high", f"local_supplier_capacity_node_{safe_node}_high"),
        ),
        (
            "capacite process locale",
            "Cap. proc.",
            first_case_row(by_case_id, f"capacity_{safe_node}_low", f"local_capacity_node_{safe_node}_low"),
            first_case_row(by_case_id, f"capacity_{safe_node}_high", f"local_capacity_node_{safe_node}_high"),
        ),
    ]
    best_label = ""
    best_short = ""
    best_low: dict[str, str] | None = None
    best_high: dict[str, str] | None = None
    best_score = -1.0
    best_fill_impact = 0.0
    best_backlog_impact = 0.0
    for label, short_label, low_row, high_row in candidates:
        if low_row is None and high_row is None:
            continue
        fill_impact, backlog_impact = local_signal_strength(baseline_row, low_row, high_row)
        score = fill_impact * 100.0 + backlog_impact / 25.0
        if score > best_score:
            best_label = label
            best_short = short_label
            best_low = low_row
            best_high = high_row
            best_score = score
            best_fill_impact = fill_impact
            best_backlog_impact = backlog_impact
    return best_label, best_short, best_low, best_high, best_fill_impact, best_backlog_impact


def build_factory_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory":
            continue

        safe_node = safe_case_token(node_id)
        low_row = first_case_row(by_case_id, f"capacity_{safe_node}_low", f"local_capacity_node_{safe_node}_low")
        high_row = first_case_row(by_case_id, f"capacity_{safe_node}_high", f"local_capacity_node_{safe_node}_high")
        if low_row is None and high_row is None:
            continue
        low_label = multiplier_label(case_multiplier_value(low_row), "Low")
        high_label = multiplier_label(case_multiplier_value(high_row), "High")
        low_dir = case_output_dir(low_row)
        high_dir = case_output_dir(high_row)

        base_input_csv = baseline_dir / "production_input_stocks_daily.csv"
        base_output_csv = baseline_dir / "production_output_products_daily.csv"
        if base_input_csv not in csv_cache:
            csv_cache[base_input_csv] = read_csv_rows(base_input_csv)
        if base_output_csv not in csv_cache:
            csv_cache[base_output_csv] = read_csv_rows(base_output_csv)
        base_input_series = aggregate_daily_series(
            csv_cache[base_input_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        base_output_series = aggregate_daily_series(
            csv_cache[base_output_csv],
            value_field="cum_produced_qty",
            node_field="node_id",
            node_id=node_id,
        )
        input_deltas: dict[str, list[tuple[int, float]]] = {}
        output_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            input_csv = root / "production_input_stocks_daily.csv"
            output_csv = root / "production_output_products_daily.csv"
            if input_csv not in csv_cache:
                csv_cache[input_csv] = read_csv_rows(input_csv)
            if output_csv not in csv_cache:
                csv_cache[output_csv] = read_csv_rows(output_csv)
            input_deltas[label] = align_series(
                base_input_series,
                aggregate_daily_series(
                    csv_cache[input_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
            output_deltas[label] = align_series(
                base_output_series,
                aggregate_daily_series(
                    csv_cache[output_csv],
                    value_field="cum_produced_qty",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(high_row, "fill_rate"),
            },
            input_deltas,
            bar_title=f"{node_id} - impact capacite sur fill rate systeme",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - ecart de stock intrants vs baseline",
            line_y_label="Delta stock total",
            filename=f"{node_id}_sensitivity_fill_rate.png",
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(high_row, "ending_backlog"),
            },
            output_deltas,
            bar_title=f"{node_id} - impact capacite sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de production cumulee vs baseline",
            line_y_label="Delta production cumulee",
            filename=f"{node_id}_sensitivity_backlog.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "supplier_dc":
            continue

        best_label, best_short, best_low, best_high, best_fill_impact, best_backlog_impact = (
            select_best_supplier_case_pair(by_case_id, baseline_row, node_id)
        )
        if best_low is None and best_high is None:
            continue
        low_label = multiplier_label(case_multiplier_value(best_low), "Low")
        high_label = multiplier_label(case_multiplier_value(best_high), "High")
        low_dir = case_output_dir(best_low)
        high_dir = case_output_dir(best_high)
        base_ship_csv = baseline_dir / "production_supplier_shipments_daily.csv"
        base_stock_csv = baseline_dir / "production_supplier_stocks_daily.csv"
        if base_ship_csv not in csv_cache:
            csv_cache[base_ship_csv] = read_csv_rows(base_ship_csv)
        if base_stock_csv not in csv_cache:
            csv_cache[base_stock_csv] = read_csv_rows(base_stock_csv)
        base_ship_series = aggregate_daily_series(
            csv_cache[base_ship_csv],
            value_field="shipped_qty",
            node_field="src_node_id",
            node_id=node_id,
        )
        base_stock_series = aggregate_daily_series(
            csv_cache[base_stock_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        ship_deltas: dict[str, list[tuple[int, float]]] = {}
        stock_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            ship_csv = root / "production_supplier_shipments_daily.csv"
            stock_csv = root / "production_supplier_stocks_daily.csv"
            if ship_csv not in csv_cache:
                csv_cache[ship_csv] = read_csv_rows(ship_csv)
            if stock_csv not in csv_cache:
                csv_cache[stock_csv] = read_csv_rows(stock_csv)
            ship_deltas[label] = align_series(
                base_ship_series,
                aggregate_daily_series(
                    csv_cache[ship_csv],
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=node_id,
                ),
            )
            stock_deltas[label] = align_series(
                base_stock_series,
                aggregate_daily_series(
                    csv_cache[stock_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
        note = None
        if best_fill_impact < 0.002 and best_backlog_impact < 5.0:
            note = "Impact faible: le nœud bouge peu sur le système malgré un choc local fort."

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(best_high, "fill_rate"),
            },
            ship_deltas,
            bar_title=f"{node_id} - impact {best_label} sur fill rate systeme",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - ecart d'expeditions vs baseline",
            line_y_label="Delta expeditions / jour",
            filename=f"{node_id}_sensitivity_fill_rate.png",
            note=note,
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(best_high, "ending_backlog"),
            },
            stock_deltas,
            bar_title=f"{node_id} - impact {best_label} sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de stock disponible vs baseline",
            line_y_label="Delta stock fin de journee",
            filename=f"{node_id}_sensitivity_backlog.png",
            note=note,
        )
        out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "distribution_center":
            continue

        dc_item_ids = set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
        base_demand_csv = baseline_dir / "production_demand_service_daily.csv"
        if base_demand_csv not in csv_cache:
            csv_cache[base_demand_csv] = read_csv_rows(base_demand_csv)
        fill_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "fill_rate")}
        backlog_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "ending_backlog")}
        backlog_deltas: dict[str, list[tuple[int, float]]] = {}
        served_deltas: dict[str, list[tuple[int, float]]] = {}
        for item_id in sorted(dc_item_ids):
            code = item_id.split(":", 1)[-1]
            base_backlog_series = aggregate_daily_series(
                csv_cache[base_demand_csv],
                value_field="backlog_end_qty",
                item_ids={item_id},
            )
            base_served_series = cumulative_series(
                aggregate_daily_series(
                    csv_cache[base_demand_csv],
                    value_field="served_qty",
                    item_ids={item_id},
                )
            )
            low_row = first_case_row(by_case_id, f"demand_item_{code}_low", f"local_demand_item_item_{code}_low")
            high_row = first_case_row(by_case_id, f"demand_item_{code}_high", f"local_demand_item_item_{code}_high")
            low_label = multiplier_label(case_multiplier_value(low_row), f"{code} low")
            high_label = multiplier_label(case_multiplier_value(high_row), f"{code} high")
            fill_values[f"{code} {low_label}"] = kpi_from_case(low_row, "fill_rate")
            fill_values[f"{code} {high_label}"] = kpi_from_case(high_row, "fill_rate")
            backlog_values[f"{code} {low_label}"] = kpi_from_case(low_row, "ending_backlog")
            backlog_values[f"{code} {high_label}"] = kpi_from_case(high_row, "ending_backlog")
            for label, row in ((f"{code} {low_label}", low_row), (f"{code} {high_label}", high_row)):
                root = case_output_dir(row)
                if root is None:
                    continue
                demand_csv = root / "production_demand_service_daily.csv"
                if demand_csv not in csv_cache:
                    csv_cache[demand_csv] = read_csv_rows(demand_csv)
                backlog_deltas[label] = align_series(
                    base_backlog_series,
                    aggregate_daily_series(
                        csv_cache[demand_csv],
                        value_field="backlog_end_qty",
                        item_ids={item_id},
                    ),
                )
                served_deltas[label] = align_series(
                    base_served_series,
                    cumulative_series(
                        aggregate_daily_series(
                            csv_cache[demand_csv],
                            value_field="served_qty",
                            item_ids={item_id},
                        )
                    ),
                )

        incoming = build_combo_bar_line_payload(
            fill_values,
            backlog_deltas,
            bar_title=f"{node_id} - impact demande sur fill rate systeme",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - ecart de backlog client vs baseline",
            line_y_label="Delta backlog",
            filename=f"{node_id}_sensitivity_fill_rate.png",
        )
        outgoing = build_combo_bar_line_payload(
            backlog_values,
            served_deltas,
            bar_title=f"{node_id} - impact demande sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de servi cumule vs baseline",
            line_y_label="Delta servi cumule",
            filename=f"{node_id}_sensitivity_backlog.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_sensitivity_hover_payloads(
    raw: dict[str, Any],
    sensitivity_cases_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case_rows = read_csv_rows(sensitivity_cases_csv)
    if not case_rows:
        return {}, {}, {}

    csv_cache: dict[Path, list[dict[str, str]]] = {}
    return (
        build_factory_sensitivity_hover_images(raw, case_rows, csv_cache),
        build_supplier_sensitivity_hover_images(raw, case_rows, csv_cache),
        build_distribution_center_sensitivity_hover_images(raw, case_rows, csv_cache),
    )


def build_factory_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(by_case_id.get("baseline"))
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory":
            continue
        safe_node = safe_case_token(node_id)
        low_dir = case_output_dir(by_case_id.get(f"capacity_{safe_node}_low"))
        high_dir = case_output_dir(by_case_id.get(f"capacity_{safe_node}_high"))
        low_row = by_case_id.get(f"capacity_{safe_node}_low")
        high_row = by_case_id.get(f"capacity_{safe_node}_high")
        if low_dir is None and high_dir is None:
            continue

        low_label = multiplier_label(to_float(low_row.get("value")) if low_row else None, "Low")
        high_label = multiplier_label(to_float(high_row.get("value")) if high_row else None, "High")
        base_input_csv = baseline_dir / "production_input_stocks_daily.csv"
        base_output_csv = baseline_dir / "production_output_products_daily.csv"
        if base_input_csv not in csv_cache:
            csv_cache[base_input_csv] = read_csv_rows(base_input_csv)
        if base_output_csv not in csv_cache:
            csv_cache[base_output_csv] = read_csv_rows(base_output_csv)
        base_input_series = aggregate_daily_series(
            csv_cache[base_input_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        base_output_series = aggregate_daily_series(
            csv_cache[base_output_csv],
            value_field="cum_produced_qty",
            node_field="node_id",
            node_id=node_id,
        )
        input_deltas: dict[str, list[tuple[int, float]]] = {}
        output_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            input_csv = root / "production_input_stocks_daily.csv"
            output_csv = root / "production_output_products_daily.csv"
            if input_csv not in csv_cache:
                csv_cache[input_csv] = read_csv_rows(input_csv)
            if output_csv not in csv_cache:
                csv_cache[output_csv] = read_csv_rows(output_csv)
            input_deltas[label] = align_series(
                base_input_series,
                aggregate_daily_series(
                    csv_cache[input_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
            output_deltas[label] = align_series(
                base_output_series,
                aggregate_daily_series(
                    csv_cache[output_csv],
                    value_field="cum_produced_qty",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(high_row, "fill_rate"),
            },
            input_deltas,
            bar_title=f"{node_id} - structurel: impact capacite sur fill rate",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - structurel: ecart de stock intrants vs baseline",
            line_y_label="Delta stock total",
            filename=f"{node_id}_structural_input.png",
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(high_row, "ending_backlog"),
            },
            output_deltas,
            bar_title=f"{node_id} - structurel: impact capacite sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de production cumulee vs baseline",
            line_y_label="Delta production cumulee",
            filename=f"{node_id}_structural_output.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(baseline_row)
    if baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "supplier_dc":
            continue

        best_label, best_short, best_low_row, best_high_row, best_fill_impact, best_backlog_impact = (
            select_best_supplier_case_pair(by_case_id, baseline_row, node_id)
        )
        if best_low_row is None and best_high_row is None:
            continue

        low_dir = case_output_dir(best_low_row)
        high_dir = case_output_dir(best_high_row)
        low_label = multiplier_label(to_float(best_low_row.get("value")) if best_low_row else None, "Low")
        high_label = multiplier_label(to_float(best_high_row.get("value")) if best_high_row else None, "High")
        base_ship_csv = baseline_dir / "production_supplier_shipments_daily.csv"
        base_stock_csv = baseline_dir / "production_supplier_stocks_daily.csv"
        if base_ship_csv not in csv_cache:
            csv_cache[base_ship_csv] = read_csv_rows(base_ship_csv)
        if base_stock_csv not in csv_cache:
            csv_cache[base_stock_csv] = read_csv_rows(base_stock_csv)
        base_ship_series = aggregate_daily_series(
            csv_cache[base_ship_csv],
            value_field="shipped_qty",
            node_field="src_node_id",
            node_id=node_id,
        )
        base_stock_series = aggregate_daily_series(
            csv_cache[base_stock_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        ship_deltas: dict[str, list[tuple[int, float]]] = {}
        stock_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            shipments_csv = root / "production_supplier_shipments_daily.csv"
            stocks_csv = root / "production_supplier_stocks_daily.csv"
            if shipments_csv not in csv_cache:
                csv_cache[shipments_csv] = read_csv_rows(shipments_csv)
            if stocks_csv not in csv_cache:
                csv_cache[stocks_csv] = read_csv_rows(stocks_csv)
            ship_deltas[label] = align_series(
                base_ship_series,
                aggregate_daily_series(
                    csv_cache[shipments_csv],
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=node_id,
                ),
            )
            stock_deltas[label] = align_series(
                base_stock_series,
                aggregate_daily_series(
                    csv_cache[stocks_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        note = None
        if best_fill_impact < 0.002 and best_backlog_impact < 5.0:
            note = "Impact faible mais courbes affichees pour comparaison structurelle."

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(best_high_row, "fill_rate"),
            },
            ship_deltas,
            bar_title=f"{node_id} - structurel: impact {best_label} sur fill rate",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - structurel: ecart d'expeditions vs baseline",
            line_y_label="Delta expeditions / jour",
            filename=f"{node_id}_structural_shipments.png",
            note=note,
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(best_high_row, "ending_backlog"),
            },
            stock_deltas,
            bar_title=f"{node_id} - structurel: impact {best_label} sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de stock disponible vs baseline",
            line_y_label="Delta stock fin de journee",
            filename=f"{node_id}_structural_stock.png",
            note=note,
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(by_case_id.get("baseline"))
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "distribution_center":
            continue

        dc_item_ids = set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
        base_demand_csv = baseline_dir / "production_demand_service_daily.csv"
        if base_demand_csv not in csv_cache:
            csv_cache[base_demand_csv] = read_csv_rows(base_demand_csv)
        fill_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "fill_rate")}
        backlog_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "ending_backlog")}
        backlog_deltas: dict[str, list[tuple[int, float]]] = {}
        served_deltas: dict[str, list[tuple[int, float]]] = {}
        for item_id in sorted(dc_item_ids):
            code = item_id.split(":", 1)[-1]
            base_backlog_series = aggregate_daily_series(
                csv_cache[base_demand_csv],
                value_field="backlog_end_qty",
                item_ids={item_id},
            )
            base_served_series = cumulative_series(
                aggregate_daily_series(
                    csv_cache[base_demand_csv],
                    value_field="served_qty",
                    item_ids={item_id},
                )
            )
            low_row = by_case_id.get(f"demand_item_{code}_low")
            high_row = by_case_id.get(f"demand_item_{code}_high")
            low_label = multiplier_label(to_float(low_row.get("value")) if low_row else None, f"{code} low")
            high_label = multiplier_label(to_float(high_row.get("value")) if high_row else None, f"{code} high")
            fill_values[f"{code} {low_label}"] = kpi_from_case(low_row, "fill_rate")
            fill_values[f"{code} {high_label}"] = kpi_from_case(high_row, "fill_rate")
            backlog_values[f"{code} {low_label}"] = kpi_from_case(low_row, "ending_backlog")
            backlog_values[f"{code} {high_label}"] = kpi_from_case(high_row, "ending_backlog")
            for label, row in ((f"{code} {low_label}", low_row), (f"{code} {high_label}", high_row)):
                root = case_output_dir(row)
                if root is None:
                    continue
                demand_csv = root / "production_demand_service_daily.csv"
                if demand_csv not in csv_cache:
                    csv_cache[demand_csv] = read_csv_rows(demand_csv)
                backlog_deltas[label] = align_series(
                    base_backlog_series,
                    aggregate_daily_series(
                        csv_cache[demand_csv],
                        value_field="backlog_end_qty",
                        item_ids={item_id},
                    ),
                )
                served_deltas[label] = align_series(
                    base_served_series,
                    cumulative_series(
                        aggregate_daily_series(
                            csv_cache[demand_csv],
                            value_field="served_qty",
                            item_ids={item_id},
                        )
                    ),
                )

        incoming = build_combo_bar_line_payload(
            fill_values,
            backlog_deltas,
            bar_title=f"{node_id} - structurel: impact demande sur fill rate",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - structurel: ecart de backlog client vs baseline",
            line_y_label="Delta backlog",
            filename=f"{node_id}_structural_backlog.png",
        )
        outgoing = build_combo_bar_line_payload(
            backlog_values,
            served_deltas,
            bar_title=f"{node_id} - structurel: impact demande sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de servi cumule vs baseline",
            line_y_label="Delta servi cumule",
            filename=f"{node_id}_structural_served.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_structural_sensitivity_hover_payloads(
    raw: dict[str, Any],
    structural_cases_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case_rows = read_csv_rows(structural_cases_csv)
    if not case_rows:
        return {}, {}, {}

    csv_cache: dict[Path, list[dict[str, str]]] = {}
    return (
        build_factory_structural_hover_images(raw, case_rows, csv_cache),
        build_supplier_structural_hover_images(raw, case_rows, csv_cache),
        build_distribution_center_structural_hover_images(raw, case_rows, csv_cache),
    )


def metric_label_value(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def metric_section(title: str) -> dict[str, str]:
    return {"label": title, "value": ""}


def fmt_qty(value: Any, digits: int = 1) -> str:
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    return f"{numeric:,.{digits}f}".replace(",", " ")


def fmt_days(value: Any, digits: int = 1) -> str:
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    return f"{numeric:.{digits}f} j"


def fmt_pct(value: Any, digits: int = 1) -> str:
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    return f"{numeric:.{digits}f}%"


def output_root_from_csv(csv_path: Path) -> Path:
    if csv_path.parent.name == "data":
        return csv_path.parent.parent
    return csv_path.parent


def write_mrp_safety_arrival_reports(
    raw: dict[str, Any],
    *,
    output_root: Path,
    mrp_trace_rows: list[dict[str, str]],
    mrp_order_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    input_arrival_rows: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    factory_ids = factory_like_node_ids(raw)
    analysis_node_ids = set(factory_ids)
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "").strip().lower() == "distribution_center":
            analysis_node_ids.add(node_id)
    item_labels = build_item_label_lookup(raw)

    initial_stock_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        for state in (((node.get("inventory") or {}).get("states")) or []):
            item_id = str(state.get("item_id") or "")
            if node_id and item_id:
                initial_stock_by_pair[(node_id, item_id)] += max(0.0, to_float(state.get("initial")) or 0.0)

    relevant_input_pairs: set[tuple[str, str]] = set()
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if node_id in factory_ids:
            for process in (node.get("processes") or []):
                for raw_input in (process.get("inputs") or []):
                    item_id = str(raw_input.get("item_id") or "")
                    if node_id and item_id:
                        relevant_input_pairs.add((node_id, item_id))
        elif node_id in analysis_node_ids:
            for state in (((node.get("inventory") or {}).get("states")) or []):
                item_id = str(state.get("item_id") or "")
                mrp_policy = state.get("mrp_policy") or {}
                if node_id and item_id:
                    if max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0) > 0.0:
                        relevant_input_pairs.add((node_id, item_id))

    day0_stock_before_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if int(to_float(row.get("day")) or 0) != 0:
            continue
        if node_id and item_id:
            day0_stock_before_by_pair[(node_id, item_id)] += max(0.0, to_float(row.get("stock_before_production")) or 0.0)

    day0_arrivals_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    first_actual_arrival_day_by_pair: dict[tuple[str, str], int] = {}
    for row in input_arrival_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        qty = max(0.0, to_float(row.get("arrived_qty")) or 0.0)
        if qty <= 0.0:
            continue
        day = int(to_float(row.get("day")) or 0)
        key = (node_id, item_id)
        if day == 0:
            day0_arrivals_by_pair[key] += qty
        prev = first_actual_arrival_day_by_pair.get(key)
        if prev is None or day < prev:
            first_actual_arrival_day_by_pair[key] = day

    trace_rows_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if node_id in analysis_node_ids and item_id:
            trace_rows_by_pair[(node_id, item_id)].append(row)

    order_rows_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in mrp_order_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if node_id in analysis_node_ids and item_id and max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0) > 0.0:
            order_rows_by_pair[(node_id, item_id)].append(row)

    report_rows: list[dict[str, Any]] = []
    summary_by_node: dict[str, dict[str, Any]] = {}
    for pair in sorted((set(trace_rows_by_pair) | set(order_rows_by_pair)) & relevant_input_pairs):
        node_id, item_id = pair
        trace_rows = sorted(trace_rows_by_pair.get(pair, []), key=lambda row: int(to_float(row.get("day")) or 0))
        order_rows = sorted(order_rows_by_pair.get(pair, []), key=lambda row: int(to_float(row.get("release_day")) or 0))

        safety_time_days = max(
            [max(0.0, to_float(row.get("safety_time_days")) or 0.0) for row in order_rows + trace_rows] or [0.0]
        )
        review_period_days = max([int(to_float(row.get("review_period_days")) or 0) for row in trace_rows] or [0])
        first_arrival_day = min([int(to_float(row.get("arrival_day")) or 0) for row in order_rows], default=None)
        first_need_day = min([int(to_float(row.get("implied_cover_need_day")) or 0) for row in order_rows], default=None)
        first_planned_receipt_day = min(
            [
                int(to_float(row.get("planned_receipt_min_day")) or 0)
                for row in trace_rows
                if str(row.get("planned_receipt_min_day") or "").strip() != ""
            ],
            default=None,
        )
        deltas = []
        for row in order_rows:
            arrival = to_float(row.get("arrival_day"))
            need = to_float(row.get("implied_cover_need_day"))
            if arrival is None or need is None:
                continue
            deltas.append(float(need) - float(arrival))
        min_delta = min(deltas) if deltas else None
        is_safety_respected = bool(deltas and all(delta + 1e-9 >= safety_time_days for delta in deltas))

        max_bn_qty = max([max(0.0, to_float(row.get("bn_qty")) or 0.0) for row in trace_rows] or [0.0])
        max_target_stock_qty = max([max(0.0, to_float(row.get("target_stock_qty")) or 0.0) for row in trace_rows] or [0.0])
        max_target_with_backlog_qty = max(
            [max(0.0, to_float(row.get("target_with_backlog_qty")) or 0.0) for row in trace_rows] or [0.0]
        )

        if order_rows and is_safety_respected:
            comment = "conforme: reception planifiee avant le jour de besoin de couverture"
        elif order_rows and not is_safety_respected:
            comment = "non conforme: reception planifiee trop tard vs safety time"
        elif max_bn_qty <= 1e-9:
            comment = "pas d'ordre: pas de besoin net observe"
        elif day0_stock_before_by_pair.get(pair, 0.0) + day0_arrivals_by_pair.get(pair, 0.0) >= max_target_with_backlog_qty - 1e-9:
            comment = "pas d'ordre: couverture initiale suffisante via stock seed + arrivages jour 0"
        else:
            comment = "attention: besoin net observe sans ordre planifie visible"

        report_rows.append(
            {
                "node_id": node_id,
                "item_id": item_id,
                "item_label": item_labels.get(item_id, compact_item_label(item_id)),
                "safety_time_days": round(safety_time_days, 6),
                "review_period_days": review_period_days,
                "first_arrival_day": "" if first_arrival_day is None else first_arrival_day,
                "first_need_day": "" if first_need_day is None else first_need_day,
                "first_planned_receipt_day": "" if first_planned_receipt_day is None else first_planned_receipt_day,
                "first_actual_arrival_day": "" if pair not in first_actual_arrival_day_by_pair else first_actual_arrival_day_by_pair[pair],
                "min_delta_need_minus_arrival_days": "" if min_delta is None else round(min_delta, 6),
                "is_safety_respected": int(is_safety_respected),
                "order_count": len(order_rows),
                "initial_stock_source_qty": round(initial_stock_by_pair.get(pair, 0.0), 6),
                "day0_stock_before_production_qty": round(day0_stock_before_by_pair.get(pair, 0.0), 6),
                "day0_arrivals_qty": round(day0_arrivals_by_pair.get(pair, 0.0), 6),
                "max_bn_qty": round(max_bn_qty, 6),
                "max_target_stock_qty": round(max_target_stock_qty, 6),
                "max_target_with_backlog_qty": round(max_target_with_backlog_qty, 6),
                "comment": comment,
            }
        )

        bucket = summary_by_node.setdefault(
            node_id,
            {"total": 0, "conform": 0, "non_conform": 0, "no_orders": 0, "worst_delta_days": None},
        )
        bucket["total"] += 1
        if order_rows:
            if is_safety_respected:
                bucket["conform"] += 1
            else:
                bucket["non_conform"] += 1
        else:
            bucket["no_orders"] += 1
        if min_delta is not None:
            prev = bucket.get("worst_delta_days")
            bucket["worst_delta_days"] = min_delta if prev is None else min(prev, min_delta)

    csv_path = reports_dir / "mrp_safety_arrival_compliance.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "node_id",
                "item_id",
                "item_label",
                "safety_time_days",
                "review_period_days",
                "first_arrival_day",
                "first_need_day",
                "first_planned_receipt_day",
                "first_actual_arrival_day",
                "min_delta_need_minus_arrival_days",
                "is_safety_respected",
                "order_count",
                "initial_stock_source_qty",
                "day0_stock_before_production_qty",
                "day0_arrivals_qty",
                "max_bn_qty",
                "max_target_stock_qty",
                "max_target_with_backlog_qty",
                "comment",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    md_path = reports_dir / "mrp_safety_arrival_compliance.md"
    lines = [
        "# MRP Safety Arrival Compliance",
        "",
        f"- Rows analysed: `{len(report_rows)}`",
        f"- Factory/DC nodes analysed: `{len(summary_by_node)}`",
        "",
        "## Summary by node",
    ]
    for node_id in sorted(summary_by_node):
        bucket = summary_by_node[node_id]
        lines.append(
            f"- {node_id}: total=`{bucket['total']}` ; conformes=`{bucket['conform']}` ; non conformes=`{bucket['non_conform']}` ; sans ordres=`{bucket['no_orders']}` ; pire delta=`{bucket['worst_delta_days'] if bucket['worst_delta_days'] is not None else 'n/a'}`"
        )
    lines.extend(["", "## Attention points"])
    flagged = [row for row in report_rows if row["order_count"] == 0 or not row["is_safety_respected"]]
    if flagged:
        for row in flagged:
            lines.append(
                f"- {row['node_id']} / {row['item_id']}: safety=`{row['safety_time_days']}` ; arrival=`{row['first_arrival_day'] or 'n/a'}` ; need=`{row['first_need_day'] or 'n/a'}` ; delta=`{row['min_delta_need_minus_arrival_days'] or 'n/a'}` ; comment=`{row['comment']}`"
            )
    else:
        lines.append("- Aucun point non conforme detecte sur les ordres MRP traces.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_by_node


def build_item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code or name or compact_item_label(item_id)
        out[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return out


def latest_value_map(
    rows: list[dict[str, str]],
    *,
    node_field: str,
    value_field: str,
) -> dict[tuple[str, str], float]:
    latest: dict[tuple[str, str], tuple[int, float]] = {}
    for row in rows:
        node_id = str(row.get(node_field) or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        value = float(to_float(row.get(value_field)) or 0.0)
        key = (node_id, item_id)
        prev = latest.get(key)
        if prev is None or day >= prev[0]:
            latest[key] = (day, value)
    return {key: value for key, (_day, value) in latest.items()}


def unique_preserve(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in seq:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def preview_join(values: list[str], *, limit: int = 8) -> str:
    usable = [v for v in values if v]
    if not usable:
        return "n/a"
    if len(usable) <= limit:
        return ", ".join(usable)
    return ", ".join(usable[:limit]) + f" ... (+{len(usable) - limit})"


def metric_multiline_value(label: str, values: list[str], *, limit: int = 8) -> dict[str, str]:
    usable = [v for v in values if v]
    if not usable:
        return metric_label_value(label, "n/a")
    shown = usable[:limit]
    value = "\n".join(shown)
    if len(usable) > limit:
        value += f"\n... (+{len(usable) - limit})"
    return metric_label_value(label, value)


def latest_rows_by_pair(rows: list[dict[str, str]], *, node_field: str) -> dict[tuple[str, str], dict[str, str]]:
    latest: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
    for row in rows:
        node_id = str(row.get(node_field) or "")
        item_id = str(row.get("item_id") or row.get("output_item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        key = (node_id, item_id)
        prev = latest.get(key)
        if prev is None or day >= prev[0]:
            latest[key] = (day, row)
    return {key: value for key, (_day, value) in latest.items()}


def describe_processes(
    processes: list[dict[str, Any]],
    item_labels: dict[str, str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    process_labels: list[str] = []
    io_rules: list[str] = []
    lot_rules: list[str] = []
    source_refs: list[str] = []
    for proc in processes:
        proc_id = str(proc.get("id") or "")
        inputs = [
            item_labels.get(str(inp.get("item_id") or ""), compact_item_label(str(inp.get("item_id") or "")))
            for inp in (proc.get("inputs") or [])
            if str(inp.get("item_id") or "")
        ]
        outputs = [
            item_labels.get(str(out.get("item_id") or ""), compact_item_label(str(out.get("item_id") or "")))
            for out in (proc.get("outputs") or [])
            if str(out.get("item_id") or "")
        ]
        if proc_id or inputs or outputs:
            process_labels.append(
                f"{proc_id or 'process'}: {preview_join(inputs, limit=4)} -> {preview_join(outputs, limit=4)}"
            )
        for inp in (proc.get("inputs") or []):
            item_id = str(inp.get("item_id") or "")
            if not item_id:
                continue
            ratio = to_float(inp.get("ratio_per_batch"))
            ratio_unit = str(inp.get("ratio_unit") or "").strip()
            io_rules.append(
                f"{item_labels.get(item_id, compact_item_label(item_id))}: {fmt_qty(ratio, 3)} {ratio_unit or ''}".strip()
            )
        lot_sizing = proc.get("lot_sizing") or {}
        lot_exec = proc.get("lot_execution") or {}
        lot_parts = []
        if to_float(lot_sizing.get("fixed_lot_qty")):
            lot_parts.append(f"fixe={fmt_qty(lot_sizing.get('fixed_lot_qty'), 0)}")
        if to_float(lot_sizing.get("min_lot_qty")):
            lot_parts.append(f"min={fmt_qty(lot_sizing.get('min_lot_qty'), 0)}")
        if to_float(lot_sizing.get("max_lot_qty")):
            lot_parts.append(f"max={fmt_qty(lot_sizing.get('max_lot_qty'), 0)}")
        if to_float(lot_sizing.get("lot_multiple_qty")):
            lot_parts.append(f"multiple={fmt_qty(lot_sizing.get('lot_multiple_qty'), 0)}")
        if to_float(lot_exec.get("max_lots_per_week")):
            lot_parts.append(f"max_lots/sem={fmt_qty(lot_exec.get('max_lots_per_week'), 0)}")
        if lot_parts:
            lot_rules.append(f"{proc_id or 'process'}: " + " ; ".join(lot_parts))
        source_parts = [
            str((proc.get("attrs") or {}).get("source_workbook") or ""),
            str((proc.get("attrs") or {}).get("source_sheet") or ""),
        ]
        source_ref = " / ".join(part for part in source_parts if part)
        if source_ref:
            source_refs.append(f"{proc_id or 'process'}: {source_ref}")
    return (
        unique_preserve(process_labels),
        unique_preserve(io_rules),
        unique_preserve(lot_rules),
        unique_preserve(source_refs),
    )


def build_model_panel_metrics(
    raw: dict[str, Any],
    *,
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    input_arrivals_csv: Path,
    demand_service_csv: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_capacity_csv: Path,
    dc_stocks_csv: Path,
    production_constraint_csv: Path,
) -> dict[str, Any]:
    item_labels = build_item_label_lookup(raw)
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)
    node_types = build_node_type_lookup(raw)
    node_by_id = {
        str(node.get("id") or ""): node
        for node in (raw.get("nodes") or [])
        if isinstance(node, dict) and node.get("id") is not None and not is_pilotage_hidden_node(str(node.get("id") or ""))
    }
    output_root = output_root_from_csv(demand_service_csv)
    summary_file = output_root / "summaries" / "first_simulation_summary.json"
    data_root = output_root / "data"
    summary = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.exists() else {}
    policy = (summary.get("policy") or {}) if isinstance(summary, dict) else {}
    init_policy = (policy.get("initialization_policy") or {}) if isinstance(policy, dict) else {}
    mrp_trace_rows = read_csv_rows(data_root / "mrp_trace_daily.csv")
    mrp_order_rows = read_csv_rows(data_root / "mrp_orders_daily.csv")
    assumptions_ledger_rows = read_csv_rows(data_root / "assumptions_ledger.csv")

    input_rows = read_csv_rows(sim_input_stocks_csv)
    output_rows = read_csv_rows(sim_output_products_csv)
    input_arrival_rows = read_csv_rows(input_arrivals_csv)
    demand_rows = read_csv_rows(demand_service_csv)
    supplier_ship_rows = read_csv_rows(supplier_shipments_csv)
    supplier_stock_rows = read_csv_rows(supplier_stocks_csv)
    supplier_capacity_rows = read_csv_rows(supplier_capacity_csv)
    dc_stock_rows = read_csv_rows(dc_stocks_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    mrp_safety_summary_by_node = write_mrp_safety_arrival_reports(
        raw,
        output_root=output_root,
        mrp_trace_rows=mrp_trace_rows,
        mrp_order_rows=mrp_order_rows,
        input_rows=input_rows,
        input_arrival_rows=input_arrival_rows,
    )

    latest_input_stock = latest_value_map(input_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_output_stock = latest_value_map(output_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_supplier_stock = latest_value_map(supplier_stock_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_dc_stock = latest_value_map(dc_stock_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_output_rows = latest_rows_by_pair(output_rows, node_field="node_id")
    latest_dc_rows = latest_rows_by_pair(dc_stock_rows, node_field="node_id")
    latest_supplier_rows = latest_rows_by_pair(supplier_stock_rows, node_field="node_id")
    latest_input_arrival_rows = latest_rows_by_pair(input_arrival_rows, node_field="node_id")

    constraint_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in constraint_rows:
        constraint_by_node[str(row.get("node_id") or "")].append(row)

    demand_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in demand_rows:
        demand_by_node[str(row.get("node_id") or "")].append(row)

    supplier_ship_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    supplier_ship_by_edge: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in supplier_ship_rows:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        supplier_ship_by_node[src].append(row)
        supplier_ship_by_edge[(src, dst, item_id)].append(row)

    supplier_cap_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    supplier_cap_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in supplier_capacity_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        supplier_cap_by_node[node_id].append(row)
        supplier_cap_by_pair[(node_id, item_id)].append(row)

    input_arrivals_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_arrival_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            input_arrivals_by_node[node_id].append(row)

    latest_mrp_trace_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    mrp_trace_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        mrp_trace_by_node[node_id].append(row)
        key = (node_id, item_id)
        day = int(to_float(row.get("day")) or 0)
        prev = latest_mrp_trace_by_pair.get(key)
        if prev is None or day >= int(to_float(prev.get("day")) or 0):
            latest_mrp_trace_by_pair[key] = row

    supplier_ids = {
        str(node.get("id") or "")
        for node in raw.get("nodes", []) or []
        if str(node.get("type") or "") == "supplier_dc"
    }
    outgoing_edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming_edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if is_pilotage_hidden_edge(src, dst):
            continue
        if src:
            outgoing_edges_by_node[src].append(edge)
        if dst:
            incoming_edges_by_node[dst].append(edge)

    mrp_orders_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    mrp_orders_by_edge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_order_rows:
        node_id = str(row.get("node_id") or "")
        src_node_id = str(row.get("src_node_id") or "")
        dst_node_id = str(row.get("dst_node_id") or "")
        edge_id = str(row.get("edge_id") or "")

        linked_node_ids: list[str] = []
        if node_id:
            linked_node_ids.append(node_id)
        if src_node_id in supplier_ids:
            linked_node_ids.append(src_node_id)
        if dst_node_id in supplier_ids:
            linked_node_ids.append(dst_node_id)

        for linked_node_id in dict.fromkeys(linked_node_ids):
            mrp_orders_by_node[linked_node_id].append(row)
        if edge_id:
            mrp_orders_by_edge[edge_id].append(row)

    assumptions_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    assumptions_by_edge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assumptions_ledger_rows:
        node_id = str(row.get("node_id") or "")
        edge_id = str(row.get("edge_id") or "")
        if node_id:
            assumptions_by_node[node_id].append(row)
        if edge_id:
            assumptions_by_edge[edge_id].append(row)

    def aggregate_trace_series(rows: list[dict[str, str]], field: str) -> list[tuple[int, float]]:
        by_day: dict[int, float] = defaultdict(float)
        for row in rows:
            day = int(to_float(row.get("day")) or 0)
            by_day[day] += max(0.0, to_float(row.get(field)) or 0.0)
        return sorted(by_day.items())

    def aggregate_order_series(
        rows: list[dict[str, str]],
        field: str,
        *,
        day_field: str = "day",
    ) -> list[tuple[int, float]]:
        by_day: dict[int, float] = defaultdict(float)
        for row in rows:
            day = int(to_float(row.get(day_field)) or 0)
            by_day[day] += max(0.0, to_float(row.get(field)) or 0.0)
        return sorted(by_day.items())

    def average_order_series(rows: list[dict[str, str]], field: str) -> list[tuple[int, float]]:
        sums: dict[int, float] = defaultdict(float)
        counts: dict[int, int] = defaultdict(int)
        for row in rows:
            day = int(to_float(row.get("day")) or 0)
            value = to_float(row.get(field))
            if value is None or math.isnan(value):
                continue
            sums[day] += float(value)
            counts[day] += 1
        return [(day, sums[day] / counts[day]) for day in sorted(sums) if counts[day] > 0]

    def status_bar_figure(rows: list[dict[str, str]], *, field: str, title: str) -> dict[str, Any] | None:
        counts: dict[str, float] = defaultdict(float)
        for row in rows:
            key = str(row.get(field) or "n/a")
            counts[key] += 1.0
        if not counts:
            return None
        return build_bar_chart_figure(counts, title=title, y_label="Nombre d'ordres")

    customer_latest_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for row in demand_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        key = (node_id, item_id)
        prev = customer_latest_by_pair.get(key)
        if prev is None or day >= int(to_float(prev.get("day")) or 0):
            customer_latest_by_pair[key] = row

    edge_metrics = build_edge_metrics(raw, supplier_shipments_csv)
    factory_like_ids = factory_like_node_ids(raw)
    nodes_payload: dict[str, Any] = {}
    edges_payload: dict[str, Any] = {}

    for node_id, node in sorted(node_by_id.items()):
        if is_pilotage_hidden_node(node_id):
            continue
        node_type = str(node.get("type") or "")
        role_raw = str(node.get("role_raw") or "")
        location = str(node.get("location_ID") or "n/a")
        attrs = node.get("attrs") or {}
        inv_states = ((node.get("inventory") or {}).get("states") or [])
        processes = node.get("processes") or []
        review_period = (((node.get("policies") or {}).get("simulation_policy") or {}).get("review_period_days"))
        process_labels, io_rules, process_lot_rules, process_source_refs = describe_processes(processes, item_labels)
        inventory_lines: list[str] = []
        state_var_lines: list[str] = []
        assumption_lines: list[str] = []
        source_refs: list[str] = []
        interaction_lines: list[str] = []
        if attrs.get("source_workbook") or attrs.get("source_sheet"):
            source_refs.append(
                " / ".join(
                    part for part in [str(attrs.get("source_workbook") or ""), str(attrs.get("source_sheet") or "")] if part
                )
            )
        source_refs.extend(process_source_refs)
        for state in inv_states:
            item_id = str(state.get("item_id") or "")
            if not item_id:
                continue
            if is_simulation_hidden_item(item_id):
                continue
            label = item_labels.get(item_id, compact_item_label(item_id))
            initial = fmt_qty(state.get("initial"), 1)
            uom = str(state.get("uom") or "").strip()
            mrp_policy = state.get("mrp_policy") or {}
            safety_time = to_float(mrp_policy.get("safety_time_days"))
            safety_stock = to_float(mrp_policy.get("safety_stock_qty"))
            policy_bits = []
            if safety_time and safety_time > 0:
                policy_bits.append(f"safety_time={fmt_days(safety_time, 0)}")
            if safety_stock and safety_stock > 0:
                policy_bits.append(f"safety_stock={fmt_qty(safety_stock, 0)}")
            inventory_lines.append(
                f"{label}: initial={initial} {uom}".strip() + (f" ; {' ; '.join(policy_bits)}" if policy_bits else "")
            )
            if mrp_policy.get("source"):
                source_refs.append(f"{label}: {mrp_policy.get('source')}")
        interaction_lines.append(
            f"amont={len(incoming_sources.get(node_id, set()))} noeuds ; aval={len(outgoing_targets.get(node_id, set()))} noeuds"
        )
        if incoming_items.get(node_id):
            interaction_lines.append(
                "items amont: " + preview_join(
                    [
                        item_labels.get(i, compact_item_label(i))
                        for i in sorted(incoming_items.get(node_id, set()))
                        if not is_simulation_hidden_item(i)
                    ],
                    limit=10,
                )
            )
        if outgoing_items.get(node_id):
            interaction_lines.append(
                "items aval: " + preview_join(
                    [
                        item_labels.get(i, compact_item_label(i))
                        for i in sorted(outgoing_items.get(node_id, set()))
                        if not is_simulation_hidden_item(i)
                    ],
                    limit=10,
                )
            )
        summary_lines: list[dict[str, str]] = [
            metric_section("Element"),
            metric_label_value("Type", node_type or "n/a"),
            metric_label_value("Role", role_raw or "n/a"),
            metric_label_value("Localisation", location),
            metric_label_value("Id", node_id),
        ]

        if node_type == "customer":
            rows = demand_by_node.get(node_id, [])
            total_demand = sum(max(0.0, to_float(r.get("demand_qty")) or 0.0) for r in rows)
            total_served = sum(max(0.0, to_float(r.get("served_qty")) or 0.0) for r in rows)
            ending_backlog = 0.0
            by_item = sorted(
                {
                    str(r.get("item_id") or "")
                    for r in rows
                    if str(r.get("item_id") or "") and not is_simulation_hidden_item(str(r.get("item_id") or ""))
                }
            )
            if rows:
                latest_day = max(int(to_float(r.get("day")) or 0) for r in rows)
                ending_backlog = sum(
                    max(0.0, to_float(r.get("backlog_end_qty")) or 0.0)
                    for r in rows
                    if int(to_float(r.get("day")) or 0) == latest_day
                )
            state_var_lines.extend(
                [
                    "Demande_pf(t): demande exogene du jour par produit",
                    "besoin brut client BB_pf(t): required_with_backlog_qty = demande + backlog precedent",
                    "Servi_pf(t): served_qty = min(stock_disponible, besoin_brut_client)",
                    "Backlog_pf(t): backlog_end_qty = besoin_brut_client - Servi_pf(t)",
                ]
            )
            assumption_lines.extend(
                [
                    "la demande est fournie en entree et lue jour par jour",
                    "le client ne produit rien ; il consomme le stock aval disponible",
                    "la cible de couverture est portee par le systeme aval via demand_stock_target_days",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Variables d'etat"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Equations simulateur"),
                    metric_label_value("Eq sim 1", "besoin brut client BB_pf(t): demande_jour + backlog_precedent"),
                    metric_label_value("Eq sim 2", "Servi_pf(t): quantite servie au client = min(stock_disponible_pf, besoin_brut_client)"),
                    metric_label_value("Eq sim 3", "Backlog_pf(t): retard client fin de journee = besoin_brut_client - Servi_pf(t)"),
                    metric_section("Equations IMT (slide)"),
                    metric_label_value("Eq IMT 1", "besoin brut BB(t) = forecast(t) si t = t_deb ; sinon backlog[product]"),
                    metric_section("Comparaison IMT vs simulateur"),
                    metric_label_value("IMT", "la slide exprime le besoin brut et le backlog comme objets de planification explicites"),
                    metric_label_value("Simulateur", "le simulateur recalcule le besoin brut client et le backlog dynamiquement chaque jour a partir du stock et de la demande"),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Produits demandes", ", ".join(item_labels.get(i, compact_item_label(i)) for i in by_item) or "n/a"),
                    metric_label_value("Horizon demande", f"{len({int(to_float(r.get('day')) or 0) for r in rows})} jours" if rows else "n/a"),
                    metric_label_value("Cible couverture demandee", fmt_days(policy.get("demand_stock_target_days"), 1)),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Demande cumulee", fmt_qty(total_demand)),
                    metric_label_value("Servi cumule", fmt_qty(total_served)),
                    metric_label_value("Backlog final", fmt_qty(ending_backlog)),
                ]
            )
        elif node_type == "distribution_center":
            state_pairs = [
                (node_id, str(state.get("item_id") or ""))
                for state in inv_states
                if str(state.get("item_id") or "") and not is_simulation_hidden_item(str(state.get("item_id") or ""))
            ]
            final_stock_total = sum(max(0.0, latest_dc_stock.get(pair, 0.0)) for pair in state_pairs)
            latest_dc_lines = []
            safety_items = []
            for state in inv_states:
                item_id = str(state.get("item_id") or "")
                if is_simulation_hidden_item(item_id):
                    continue
                mrp_policy = state.get("mrp_policy") or {}
                safety_days = max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0)
                if item_id and safety_days > 0:
                    safety_items.append(f"{item_labels.get(item_id, compact_item_label(item_id))}={safety_days:.0f}j")
                latest_row = latest_dc_rows.get((node_id, item_id))
                if latest_row is not None:
                    latest_dc_lines.append(
                        f"{item_labels.get(item_id, compact_item_label(item_id))}: stock_fin={fmt_qty(latest_row.get('stock_end_of_day'))}"
                    )
            state_var_lines.extend(
                [
                    "StockProj_dc(t): stock fin de journee au DC",
                    "RecvPrev_dc(t): receptions futures implicites via in_transit",
                    "BN_dc(t): besoin net du DC = cible - stock - in_transit",
                ]
            )
            assumption_lines.extend(
                [
                    "le DC est pilote en base_stock / couverture et non en plan de production",
                    "les safety times MRP des PF sont portes sur les etats de stock du DC",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Variables d'etat"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Equations simulateur"),
                    metric_label_value("Eq sim 1", "StockProj_dc(t): stock projete DC = stock_debut + receptions - expeditions"),
                    metric_label_value("Eq sim 2", "SS_dc: stock de securite / cible DC = max(base_stock, safety_stock, couverture * signal)"),
                    metric_label_value("Eq sim 3", "BN_dc(t): besoin net DC = max(0, SS_dc - stock_dc - in_transit_dc)"),
                    metric_section("Equations IMT (slide)"),
                    metric_label_value("Eq IMT 1", "StockProj[t] += receptions_prevues(t) - BB(t)"),
                    metric_section("Comparaison IMT vs simulateur"),
                    metric_label_value("IMT", "la slide raisonne en StockProj et RecvPrev explicites"),
                    metric_label_value("Simulateur", "le simulateur tient StockProj via stock + in_transit et prend BN_dc jour par jour"),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Items entrants", str(len([i for i in incoming_items.get(node_id, set()) if not is_simulation_hidden_item(i)]))),
                    metric_label_value("Items sortants", str(len([i for i in outgoing_items.get(node_id, set()) if not is_simulation_hidden_item(i)]))),
                    metric_label_value("Review period", f"{review_period} j" if review_period is not None else "n/a"),
                    metric_label_value("Safety times MRP", ", ".join(safety_items[:6]) or "n/a"),
                    metric_multiline_value("Stocks suivis", latest_dc_lines, limit=8),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_multiline_value("Etats stock initiaux", inventory_lines, limit=8),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Stock final total", fmt_qty(final_stock_total)),
                    metric_label_value("Sources amont", str(len(incoming_sources.get(node_id, set())))),
                    metric_label_value("Destinations aval", str(len(outgoing_targets.get(node_id, set())))),
                ]
            )
        elif node_type == "supplier_dc" and node_id not in factory_like_ids:
            ship_rows = supplier_ship_by_node.get(node_id, [])
            cap_rows = supplier_cap_by_node.get(node_id, [])
            node_orders_preview = mrp_orders_by_node.get(node_id, [])
            final_stock_total = sum(
                max(0.0, latest_supplier_stock.get((node_id, str(state.get("item_id") or "")), 0.0))
                for state in inv_states
            )
            total_shipped = sum(max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in ship_rows)
            avg_util = (
                sum(max(0.0, to_float(r.get("utilization")) or 0.0) for r in cap_rows) / len(cap_rows)
                if cap_rows else 0.0
            )
            sim_constraints = node.get("simulation_constraints") or {}
            cap_map = sim_constraints.get("supplier_item_capacity_qty_per_day") or {}
            basis_map = sim_constraints.get("supplier_item_capacity_basis") or {}
            cap_preview = []
            for item_id, cap_qty in list(sorted(cap_map.items()))[:5]:
                if is_simulation_hidden_item(str(item_id)):
                    continue
                basis = str(basis_map.get(item_id) or "")
                cap_preview.append(f"{item_labels.get(item_id, compact_item_label(item_id))}={to_float(cap_qty) or 0.0:.2f}/j ({basis or 'n/a'})")
            latest_supplier_lines = []
            for state in inv_states:
                item_id = str(state.get("item_id") or "")
                if is_simulation_hidden_item(item_id):
                    continue
                latest_row = latest_supplier_rows.get((node_id, item_id))
                if item_id and latest_row is not None:
                    latest_supplier_lines.append(
                        f"{item_labels.get(item_id, compact_item_label(item_id))}: stock_fin={fmt_qty(latest_row.get('stock_end_of_day'))}"
                    )
            has_estimated_replenishment = any(
                str(row.get("category") or "") == "unmodeled_supplier_source_policy"
                and str(row.get("source") or "") == "estimated_replenishment"
                for row in assumptions_by_node.get(node_id, [])
            )
            is_dormant_supplier = not ship_rows and not cap_rows and not node_orders_preview
            supplier_diagnostic_lines = []
            if is_dormant_supplier:
                supplier_diagnostic_lines.append("Dormant: aucun flux observe sur l'horizon.")
            if has_estimated_replenishment:
                supplier_diagnostic_lines.append("Stock synthetique / estimated replenishment actif sur ce noeud.")
            if not supplier_diagnostic_lines:
                supplier_diagnostic_lines.append("Source active sur le run courant.")
            state_var_lines.extend(
                [
                    "Stock_source(t): stock source expediable",
                    "besoin net matiere BN_mp(t): besoin net destination porte par la lane",
                    "OA_mp(t): quantite demandee a la source apres normalisation lot standard",
                    "Pull_mp(t): quantite physiquement prelevee sur source",
                    "RecvPrev_mp(t): quantite livree a destination a t + lead_time",
                ]
            )
            assumption_lines.extend(
                [
                    "le fournisseur est simule comme source de stock + capacite ; pas comme atelier detaille",
                    "standard_order_qty agit comme multiple cible de commande sur la lane",
                    "la commande reste forward ; il n'y a pas encore de backward scheduling explicite order_date",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Variables d'etat"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Equations simulateur"),
                    metric_label_value("Eq sim 1", "besoin net matiere BN_mp(t): max(0, cible_dest - stock_dest - in_transit_dest)"),
                    metric_label_value("Eq sim 2", "OA_mp(t): ordre amont source = quantite tiree, normalisee par quantite standard si applicable"),
                    metric_label_value("Eq sim 3", "Pull_mp(t): prelevement source = min(stock_source, capacite_source, besoin_net_matiere / fiabilite)"),
                    metric_label_value("Eq sim 4", "RecvPrev_mp: reception planifiee = Pull_mp(t) * fiabilite a t + lead_time"),
                    metric_section("Equations IMT (slide)"),
                    metric_label_value("Eq IMT 1", "besoin net matiere BN_mp(t) = max(0, besoin_brut_matiere BB_mp(t) + SS_mp - StockProj_mp(t-1) - RecvPrev_mp(t))"),
                    metric_label_value("Eq IMT 2", "OA_mp(t) = CEIL(besoin_net_matiere / lot_size) * lot_size"),
                    metric_label_value("Eq IMT 3", "order_date = t - lt_fournisseur[mp] - delai_securite_mp"),
                    metric_section("Comparaison IMT vs simulateur"),
                    metric_label_value("IMT", "OA_mp est calcule en reculant la date de commande avec lead time et delai de securite"),
                    metric_label_value("Simulateur", "le simulateur reste forward: il detecte le besoin net matiere au jour t, tire OA_mp, puis pose une arrivee future a t + lead_time"),
                    metric_section("Donnees et interactions"),
                    metric_label_value(
                        "Items sortants",
                        ", ".join(
                            item_labels.get(i, compact_item_label(i))
                            for i in sorted(outgoing_items.get(node_id, set()))
                            if not is_simulation_hidden_item(i)
                        ) or "n/a"
                    ),
                    metric_label_value("Clients aval", ", ".join(sorted(outgoing_targets.get(node_id, set()))[:6]) or "n/a"),
                    metric_label_value("Review period", f"{review_period} j" if review_period is not None else "n/a"),
                    metric_label_value("Capacites nominales", " | ".join(cap_preview) or "n/a"),
                    metric_multiline_value("Diagnostic source", supplier_diagnostic_lines, limit=4),
                    metric_multiline_value("Stocks suivis", latest_supplier_lines, limit=8),
                    metric_multiline_value("Etats stock initiaux", inventory_lines, limit=8),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Expedie cumule", fmt_qty(total_shipped)),
                    metric_label_value("Stock final total", fmt_qty(final_stock_total)),
                    metric_label_value("Utilisation moyenne", fmt_pct(avg_util * 100.0)),
                    metric_label_value(
                        "Items actifs expedies",
                        str(
                            len(
                                {
                                    str(r.get('item_id') or '')
                                    for r in ship_rows
                                    if max(0.0, to_float(r.get('shipped_qty')) or 0.0) > 0
                                    and not is_simulation_hidden_item(str(r.get('item_id') or ''))
                                }
                            )
                        ),
                    ),
                ]
            )
        else:
            output_labels = []
            input_count = 0
            for proc in processes:
                outputs = proc.get("outputs") or []
                if outputs:
                    output_labels.extend(
                        item_labels.get(str(out.get("item_id") or ""), compact_item_label(str(out.get("item_id") or "")))
                        for out in outputs
                        if not is_simulation_hidden_item(str(out.get("item_id") or ""))
                    )
                input_count += len(
                    [
                        inp
                        for inp in (proc.get("inputs") or [])
                        if not is_simulation_hidden_item(str(inp.get("item_id") or ""))
                    ]
                )
            final_input_total = sum(
                max(0.0, latest_input_stock.get((node_id, str(state.get("item_id") or "")), 0.0))
                for state in inv_states
                if not is_simulation_hidden_item(str(state.get("item_id") or ""))
            )
            final_output_total = sum(
                max(0.0, latest_output_stock.get((node_id, str((proc.get("outputs") or [{}])[0].get("item_id") or "")), 0.0))
                for proc in processes
                if (proc.get("outputs") or []) and not is_simulation_hidden_item(str((proc.get("outputs") or [{}])[0].get("item_id") or ""))
            )
            factory_rows = constraint_by_node.get(node_id, [])
            desired_total = sum(max(0.0, to_float(r.get("desired_qty")) or 0.0) for r in factory_rows)
            actual_total = sum(max(0.0, to_float(r.get("actual_qty")) or 0.0) for r in factory_rows)
            shortfall_total = sum(max(0.0, to_float(r.get("shortfall_vs_desired_qty")) or 0.0) for r in factory_rows)
            capacity_days = sum(1 for r in factory_rows if str(r.get("binding_cause") or "") == "capacity")
            input_shortage_days = sum(1 for r in factory_rows if str(r.get("binding_cause") or "") == "input_shortage")
            cap_values = []
            for proc in processes:
                cap = (proc.get("capacity") or {}).get("max_rate")
                if cap is not None:
                    cap_values.append(str(cap))
            latest_output_lines = []
            latest_input_arrival_lines = []
            latest_constraint_rows: dict[str, dict[str, str]] = {}
            for row in factory_rows:
                item_id = str(row.get("output_item_id") or "")
                if not item_id:
                    continue
                if is_simulation_hidden_item(item_id):
                    continue
                latest_constraint_rows[item_id] = row
            latest_arrival_rows: dict[str, dict[str, str]] = {}
            for row in input_arrivals_by_node.get(node_id, []):
                item_id = str(row.get("item_id") or "")
                if not item_id:
                    continue
                if is_simulation_hidden_item(item_id):
                    continue
                latest_arrival_rows[item_id] = row
            for item_id in sorted(latest_arrival_rows):
                row = latest_arrival_rows[item_id]
                latest_input_arrival_lines.append(
                    f"{item_labels.get(item_id, compact_item_label(item_id))}: arrivage_jour={fmt_qty(row.get('arrived_qty'))} ; jour={int(to_float(row.get('day')) or 0)}"
                )
            for item_id in sorted(latest_constraint_rows):
                row = latest_constraint_rows[item_id]
                latest_out = latest_output_rows.get((node_id, item_id))
                latest_output_lines.append(
                    f"{item_labels.get(item_id, compact_item_label(item_id))}: desire={fmt_qty(row.get('desired_qty'))} ; plan_lot={fmt_qty(row.get('planned_qty_after_lot_rule'))} ; reel={fmt_qty(row.get('actual_qty'))} ; stock_fin={fmt_qty((latest_out or {}).get('stock_end_of_day'))}"
                )
            special_flow_lines: list[str] = []
            component_reference_lines: list[str] = []
            output_item_ids = {
                str(out.get("item_id") or "")
                for proc in processes
                for out in (proc.get("outputs") or [])
                if str(out.get("item_id") or "")
            }
            input_item_ids = {
                str(inp.get("item_id") or "")
                for proc in processes
                for inp in (proc.get("inputs") or [])
                if str(inp.get("item_id") or "")
            }
            if "item:268091" in output_item_ids and "item:007923" in input_item_ids:
                component_reference_lines.append(
                    "268091: composant actif BOM = 007923 ; ancienne ref encore visible dans Data_poc.xlsx = 693710."
                )
                component_reference_lines.append(
                    "007923: reference active retenue dans la simulation ; pas de lane FIA active fournie dans les donnees source."
                )
            if is_upstream_internal_site(node_id):
                actual_output_qty_by_item: dict[str, float] = defaultdict(float)
                for row in factory_rows:
                    item_id = str(row.get("output_item_id") or "")
                    if item_id and not is_simulation_hidden_item(item_id):
                        actual_output_qty_by_item[item_id] += max(0.0, to_float(row.get("actual_qty")) or 0.0)
                external_procurement_qty_by_item: dict[str, float] = defaultdict(float)
                for row in mrp_orders_by_node.get(node_id, []):
                    if str(row.get("order_type") or "") != "external_procurement":
                        continue
                    item_id = str(row.get("item_id") or "")
                    if item_id and not is_simulation_hidden_item(item_id):
                        external_procurement_qty_by_item[item_id] += max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
                upstream_output_labels = [
                    item_labels.get(item_id, compact_item_label(item_id))
                    for item_id in sorted(outgoing_items.get(node_id, set()))
                    if not is_simulation_hidden_item(item_id)
                ]
                if upstream_output_labels:
                    special_flow_lines.append(
                        f"Sorties PFI modelisees: {', '.join(upstream_output_labels)}."
                    )
                if aggregate_daily_series(
                    input_arrivals_by_node.get(node_id, []),
                    value_field="arrived_qty",
                    node_field="node_id",
                    node_id=node_id,
                    item_ids={"item:021081"},
                ):
                    special_flow_lines.append(
                        "021081: arrivages intrants observes dans production_input_replenishment_arrivals_daily.csv."
                    )
                if actual_output_qty_by_item.get("item:773474", 0.0) > 0:
                    special_flow_lines.append(
                        f"773474: PFI produit en interne, cumul reel={fmt_qty(actual_output_qty_by_item.get('item:773474', 0.0))}."
                    )
                if external_procurement_qty_by_item.get("item:693055", 0.0) > 0 and actual_output_qty_by_item.get("item:693055", 0.0) <= 0:
                    special_flow_lines.append(
                        f"693055: PFI aval confirme, mais pas de production interne explicite observee ; reappro courant via external_procurement={fmt_qty(external_procurement_qty_by_item.get('item:693055', 0.0))}."
                    )
            state_var_lines.extend(
                [
                    "besoin brut produit fini BB_pf(t): signal aval dynamique du produit fini",
                    "SS_pf(t): cible PF / couverture dynamique",
                    "SP_pf(t): stock PF courant observe dans la boucle",
                    "besoin net produit fini BN_pf(t): commande dynamique avant regles de lot",
                    "LP_pf(t): plan lance apres lot fixe/min/max/multiple",
                    "Prod_pf(t): production reelle bornee par capacite et intrants",
                    "StockProj_site(t): stock site fin de journee",
                ]
            )
            assumption_lines.extend(
                [
                    "la production est pilotee forward jour par jour et non par retroplanification explicite",
                    "les campagnes et regles de lot industrialisent le besoin net produit fini avant execution",
                    "les causes de binding observees viennent des contraintes reelles du run",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Variables d'etat"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Equations simulateur"),
                    metric_label_value("Eq sim 1", "besoin brut produit fini BB_pf(t): signal aval dynamique = max(demande propagee, besoin process aval)"),
                    metric_label_value("Eq sim 2", "SS_pf(t): cible PF = fg_target_days * besoin_brut_produit_fini ; ici surtout logique dynamique de couverture"),
                    metric_label_value("Eq sim 3", "SP_pf(t): stock projete PF observe dans la boucle = stock PF courant"),
                    metric_label_value("Eq sim 4", "besoin net produit fini BN_pf(t): commande dynamique = besoin_brut_produit_fini + gain * (SS_pf(t) - SP_pf(t))"),
                    metric_label_value("Eq sim 5", "LP_pf(t): plan lance = normalisation_lot(besoin_net_produit_fini) avec lot fixe/min/max/multiple + max lots / semaine"),
                    metric_label_value("Eq sim 6", "Prod_pf(t): production reelle = min(capacite, limite_intrants, LP_pf(t))"),
                    metric_label_value("Eq sim 7", "StockProj_site(t): stock fin de site = stock debut + arrivages + production - consommations - expeditions"),
                    metric_section("Equations IMT (slide)"),
                    metric_label_value("Eq IMT 1", "besoin net BN(t+tl) = max(0, besoin_brut BB(t+tl) + SS - StockProj(t+tl-1) - RecPrev(t+tl))"),
                    metric_label_value("Eq IMT 2", "LP_fp(t) = CEIL(besoin_net / batch_size) * batch_size"),
                    metric_label_value("Eq IMT 3", "StockProj[t+lead_time][product] += LP(t) ; StockProj[t][product] -= besoin_brut"),
                    metric_section("Comparaison IMT vs simulateur"),
                    metric_label_value("IMT", "la slide ecrit LP_pf a partir du besoin brut, du stock de securite, du stock projete et des receptions prevues sur un horizon planifie"),
                    metric_label_value("Simulateur", "le simulateur calcule le besoin net produit fini et le plan lance dynamiquement avec lissage, campagnes et contraintes de lot, sans boucle de retroplanification explicite"),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Sorties process", ", ".join(sorted(set(output_labels))) or "n/a"),
                    metric_label_value(
                        "Sorties PFI",
                        ", ".join(
                            item_labels.get(item_id, compact_item_label(item_id))
                            for item_id in sorted(outgoing_items.get(node_id, set()))
                            if not is_simulation_hidden_item(item_id)
                        ) or "n/a",
                    ),
                    metric_label_value("Nb intrants modelises", str(input_count)),
                    metric_label_value("Capacite max_rate", " | ".join(cap_values) or "n/a"),
                    metric_multiline_value("Process modelises", process_labels, limit=6),
                    metric_multiline_value("Consommations BOM", io_rules, limit=10),
                    metric_multiline_value("Refs composants", component_reference_lines, limit=4),
                    metric_multiline_value("Regles de lot", process_lot_rules, limit=6),
                    metric_label_value("Review period", f"{review_period} j" if review_period is not None else "n/a"),
                    metric_multiline_value("Etats stock initiaux", inventory_lines, limit=10),
                    metric_multiline_value("Arrivages intrants observes", latest_input_arrival_lines, limit=8),
                    metric_multiline_value("Sorties observees", latest_output_lines, limit=8),
                    metric_multiline_value("Diagnostic PFI", special_flow_lines, limit=6),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Stock intrants final", fmt_qty(final_input_total)),
                    metric_label_value("Stock sorties final", fmt_qty(final_output_total)),
                    metric_label_value("Production demandee", fmt_qty(desired_total)),
                    metric_label_value("Production reelle", fmt_qty(actual_total)),
                    metric_label_value("Manque de production", fmt_qty(shortfall_total)),
                    metric_label_value("Jours input shortage", str(input_shortage_days)),
                    metric_label_value("Jours capacite", str(capacity_days)),
                ]
            )

        node_item_candidates = {
            str(state.get("item_id") or "")
            for state in inv_states
            if str(state.get("item_id") or "") and not is_simulation_hidden_item(str(state.get("item_id") or ""))
        }
        for proc in processes:
            for inp in (proc.get("inputs") or []):
                item_id = str(inp.get("item_id") or "")
                if item_id and not is_simulation_hidden_item(item_id):
                    node_item_candidates.add(item_id)
            for out in (proc.get("outputs") or []):
                item_id = str(out.get("item_id") or "")
                if item_id and not is_simulation_hidden_item(item_id):
                    node_item_candidates.add(item_id)
        node_item_candidates |= {
            item_id
            for item_id in set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
            if not is_simulation_hidden_item(item_id)
        }

        mrp_trace_lines = []
        for item_id in sorted(node_item_candidates):
            latest_trace = latest_mrp_trace_by_pair.get((node_id, item_id))
            if latest_trace is None:
                continue
            mrp_trace_lines.append(
                f"{item_labels.get(item_id, compact_item_label(item_id))}: "
                f"besoin brut={fmt_qty(latest_trace.get('bb_qty'))} ; "
                f"besoin net={fmt_qty(latest_trace.get('bn_qty'))} ; "
                f"StockProj={fmt_qty(latest_trace.get('stock_proj_qty'))} ; "
                f"RecvPrev={fmt_qty(latest_trace.get('recv_prev_future_qty'))} ; "
                f"OA={fmt_qty(latest_trace.get('planned_release_qty'))} ; "
                f"PR={fmt_qty(latest_trace.get('planned_receipt_qty'))}"
            )

        node_orders = mrp_orders_by_node.get(node_id, [])
        order_status_counts: dict[str, int] = defaultdict(int)
        for row in node_orders:
            status_key = " | ".join(
                [
                    f"plan={str(row.get('planning_status') or 'n/a')}",
                    f"release={str(row.get('release_status') or 'n/a')}",
                    f"receipt={str(row.get('receipt_status') or 'n/a')}",
                    f"run={str(row.get('order_status_end_of_run') or 'n/a')}",
                ]
            )
            order_status_counts[status_key] += 1
        order_lines = []
        for row in sorted(
            node_orders,
            key=lambda r: (
                int(to_float(r.get("day")) or 0),
                str(r.get("item_id") or ""),
                str(r.get("edge_id") or ""),
            ),
            reverse=True,
        ):
            if is_simulation_hidden_item(str(row.get("item_id") or "")):
                continue
            order_lines.append(
                f"{item_labels.get(str(row.get('item_id') or ''), compact_item_label(str(row.get('item_id') or '')))}: "
                f"{row.get('order_type') or 'n/a'} ; "
                f"release={row.get('release_day') or 'n/a'} ; "
                f"order_date_IMT={row.get('order_date_imt') or 'n/a'} ; "
                f"arrival={row.get('arrival_day') or 'n/a'} ; "
                f"status={row.get('order_status_end_of_run') or 'n/a'}"
            )
            if len(order_lines) >= 8:
                break

        mrp_industrial_validation_lines: list[str] = []
        for item_id in sorted({str(row.get("item_id") or "") for row in node_orders if str(row.get("item_id") or "")}):
            item_rows = [row for row in node_orders if str(row.get("item_id") or "") == item_id]
            if not item_rows or is_simulation_hidden_item(item_id):
                continue
            release_by_imt: dict[int, float] = defaultdict(float)
            total_qty = 0.0
            standard_qty = 0.0
            for row in item_rows:
                if str(row.get("order_type") or "") != "lane_release":
                    continue
                day = int(to_float(row.get("order_date_imt")) or 0)
                qty = max(0.0, to_float(row.get("release_qty")) or 0.0)
                release_by_imt[day] += qty
                total_qty += qty
                standard_qty = max(standard_qty, max(0.0, to_float(row.get("standard_order_qty")) or 0.0))
            if not release_by_imt:
                continue
            peak_day, peak_qty = max(release_by_imt.items(), key=lambda it: it[1])
            label = item_labels.get(item_id, compact_item_label(item_id))
            if standard_qty >= 1_000_000.0:
                mrp_industrial_validation_lines.append(
                    f"{label}: lot FIA tres eleve a valider ({fmt_qty(standard_qty, 0)}), pic MRP={fmt_qty(peak_qty, 0)} a J{peak_day}."
                )
            elif 0.0 < standard_qty <= 1.0 and total_qty >= 100_000.0:
                mrp_industrial_validation_lines.append(
                    f"{label}: quantite standard=1 non interpretable comme lot industriel; renseigner le lot/campagne interne."
                )
            elif standard_qty > 1.0 and peak_qty > 10.0 * standard_qty:
                mrp_industrial_validation_lines.append(
                    f"{label}: concentration MRP a valider, pic={fmt_qty(peak_qty, 0)} a J{peak_day} soit {peak_qty / standard_qty:.1f} lots de {fmt_qty(standard_qty, 0)}."
                )

        assumption_lines_node = []
        for row in assumptions_by_node.get(node_id, [])[:8]:
            category = str(row.get("category") or "n/a")
            source = str(row.get("source") or "n/a")
            item_id = str(row.get("item_id") or "")
            if is_simulation_hidden_item(item_id):
                continue
            item_prefix = f"{item_labels.get(item_id, compact_item_label(item_id))}: " if item_id else ""
            assumption_lines_node.append(f"{item_prefix}{category} [{source}]")

        node_trace_rows = mrp_trace_by_node.get(node_id, [])
        node_trace_asset = None
        node_flow_asset = None
        node_order_asset = None
        node_ledger_asset = None
        dormant_reason: str | None = None
        if not node_orders:
            if node_type == "supplier_dc":
                outgoing_edges = outgoing_edges_by_node.get(node_id, [])
                observed_shipment_rows = sum(
                    int(to_float(((edge.get("edge_metrics") or {}).get("shipment_rows"))) or 0)
                    for edge in outgoing_edges
                )
                scoped_items = sorted(
                    {
                        compact_item_label(str(item_id))
                        for edge in outgoing_edges
                        for item_id in (edge.get("items") or [])
                        if str(item_id or "") and not is_simulation_hidden_item(str(item_id))
                    }
                )
                scoped_dests = sorted(
                    {str(edge.get("to") or "") for edge in outgoing_edges if str(edge.get("to") or "")}
                )
                if outgoing_edges and observed_shipment_rows == 0 and not supplier_ship_by_node.get(node_id):
                    dormant_reason = (
                        "Diagnostic: source dormante dans ce baseline. "
                        "Aucune expedition observee sur les lanes source et aucun tirage simule."
                    )
                    if any(
                        str(row.get("category") or "") == "unmodeled_supplier_source_policy"
                        and str(row.get("source") or "") == "estimated_replenishment"
                        for row in assumptions_by_node.get(node_id, [])
                    ):
                        dormant_reason += " Stock synthetique / estimated replenishment actif."
                    if scoped_dests or scoped_items:
                        dormant_reason += " "
                        dormant_reason += (
                            f"Aval={', '.join(scoped_dests) or 'n/a'} ; "
                            f"items={', '.join(scoped_items) or 'n/a'}."
                        )
                elif not outgoing_edges and not inv_states and not processes:
                    dormant_reason = "Diagnostic: noeud fournisseur orphelin, sans flux, sans stock et sans process dans le graphe actif."
            elif node_type == "distribution_center":
                if not outgoing_edges_by_node.get(node_id) and not incoming_edges_by_node.get(node_id) and not inv_states and not processes:
                    dormant_reason = "Diagnostic: noeud DC orphelin, sans flux, sans stock et sans process dans le graphe actif."
        trace_series = {
            "Besoin brut": aggregate_trace_series(node_trace_rows, "bb_qty"),
            "Besoin net": aggregate_trace_series(node_trace_rows, "bn_qty"),
            "StockProj": aggregate_trace_series(node_trace_rows, "stock_proj_qty"),
            "RecvPrev": aggregate_trace_series(node_trace_rows, "recv_prev_future_qty"),
        }
        trace_figure = build_line_chart_figure(
            trace_series,
            title=f"{node_id} - trace MRP explicite",
            y_label="Quantite",
        )
        if trace_figure is not None:
            node_trace_asset = {"figure": trace_figure}
        safety_summary = mrp_safety_summary_by_node.get(node_id, {})
        flow_series = {
            "Besoin net a couvrir": aggregate_trace_series(node_trace_rows, "bn_qty"),
            "Ordres planifies (release)": aggregate_trace_series(node_trace_rows, "planned_release_qty"),
            "Receptions planifiees": aggregate_trace_series(node_trace_rows, "planned_receipt_qty"),
            "Objectif securite souple": aggregate_trace_series(node_trace_rows, "soft_safety_target_qty"),
            "Plancher securite source": aggregate_trace_series(node_trace_rows, "safety_floor_qty"),
        }
        actual_input_arrival_series = aggregate_daily_series(
            input_arrivals_by_node.get(node_id, []),
            value_field="arrived_qty",
            node_field="node_id",
            node_id=node_id,
        )
        if actual_input_arrival_series:
            flow_series["Arrivages reels intrants"] = actual_input_arrival_series
        flow_figure = build_line_chart_figure(
            flow_series,
            title=f"{node_id} - disponibilite matiere vs delai de securite",
            y_label="Quantite",
            note=(
                "Pilotage retenu: disponibilite a temps. "
                "Le point de controle est l'arrivee avant le jour de besoin couvert moins le delai de securite source. "
                "Les cibles stock MRP restent calculees en interne mais ne sont plus le signal principal de cette vue."
            ),
            series_styles={
                "Besoin net a couvrir": {"color": "#dc2626", "width": 2.0},
                "Ordres planifies (release)": {"color": "#0f766e", "width": 2.2},
                "Receptions planifiees": {"color": "#2563eb", "width": 2.2},
                "Arrivages reels intrants": {"color": "#0891b2", "width": 2.0, "dash": "dot"},
                "Objectif securite souple": {"color": "#f59e0b", "width": 1.9, "dash": "dash"},
                "Plancher securite source": {"color": "#7c3aed", "width": 1.8, "dash": "dot"},
            },
        )
        if flow_figure is not None:
            node_flow_asset = {"figure": flow_figure}
        node_order_series: dict[str, list[tuple[int, float]]] = {}
        node_order_styles: dict[str, dict[str, Any]] = {}
        item_palette = [
            "#0f766e",
            "#2563eb",
            "#dc2626",
            "#d97706",
            "#7c3aed",
            "#475569",
            "#0891b2",
            "#be123c",
            "#65a30d",
            "#b45309",
        ]
        node_order_item_ids = sorted({str(row.get("item_id") or "") for row in node_orders if str(row.get("item_id") or "")})
        for idx, item_id in enumerate(node_order_item_ids):
            item_rows = [row for row in node_orders if str(row.get("item_id") or "") == item_id]
            if not item_rows:
                continue
            item_label = item_labels.get(item_id, compact_item_label(item_id))
            color = item_palette[idx % len(item_palette)]
            release_label = f"{item_label} - ordre"
            receipt_label = f"{item_label} - reception"
            release_series = aggregate_order_series(item_rows, "release_qty", day_field="order_date_imt")
            receipt_series = aggregate_order_series(item_rows, "planned_receipt_qty", day_field="arrival_day")
            if release_series:
                node_order_series[release_label] = release_series
                node_order_styles[release_label] = {"color": color, "width": 2.0}
            if receipt_series:
                node_order_series[receipt_label] = receipt_series
                node_order_styles[receipt_label] = {"color": color, "width": 2.0, "dash": "dash"}
        node_orders_figure = build_line_chart_figure(
            node_order_series,
            title=f"{node_id} - reappro amont par item",
            y_label="Quantite",
            note="Meme couleur par item. Trait plein = date de commande MRP/IMT ; pointille = reception attendue a l'arrivee.",
            series_styles=node_order_styles,
        )
        if node_orders_figure is not None:
            node_order_asset = {"figure": node_orders_figure}
        node_ledger_asset = {"html": render_order_ledger_html(node_id, node_orders, item_labels, dormant_reason)}

        summary_lines.extend(
            [
                metric_section("Trace MRP explicite"),
                metric_multiline_value(
                    "Besoin brut / besoin net / StockProj / RecvPrev / OA",
                    mrp_trace_lines if mrp_trace_lines else ["aucune trace MRP explicite disponible pour ce noeud"],
                    limit=10,
                ),
                metric_label_value(
                    "Conformite arrivee vs delai securite source",
                    (
                        f"conformes={safety_summary.get('conform', 0)} ; "
                        f"non conformes={safety_summary.get('non_conform', 0)} ; "
                        f"sans ordres={safety_summary.get('no_orders', 0)} ; "
                        f"pire delta={fmt_days(safety_summary.get('worst_delta_days'), 1) if safety_summary.get('worst_delta_days') is not None else 'n/a'}"
                    ),
                ),
                metric_section("Carnet d'ordres"),
                metric_label_value(
                    "Statuts fin de run",
                    ", ".join(f"{status}={count}" for status, count in sorted(order_status_counts.items()))
                    or "aucun ordre relie a ce noeud",
                ),
                metric_multiline_value(
                    "Remarques validation industrielle",
                    mrp_industrial_validation_lines
                    if mrp_industrial_validation_lines
                    else ["aucune concentration MRP ou lot atypique detecte sur ce noeud"],
                    limit=8,
                ),
                metric_multiline_value(
                    "Derniers ordres",
                    order_lines if order_lines else ["aucun ordre journalise sur ce noeud"],
                    limit=8,
                ),
                metric_label_value(
                    "Diagnostic carnet",
                    dormant_reason or ("actif" if node_orders else "aucun ordre sur le run courant"),
                ),
                metric_section("Ledger hypotheses / derives"),
                metric_multiline_value(
                    "Elements traces",
                    assumption_lines_node if assumption_lines_node else ["aucun element derive/assume journalise pour ce noeud"],
                    limit=8,
                ),
                metric_section("Sources et parametres globaux"),
                metric_multiline_value("Sources structure / MRP", unique_preserve(source_refs), limit=10),
                metric_label_value("Warm-up", f"{summary.get('warmup_days', 'n/a')} j"),
                metric_label_value("Mode init", str(init_policy.get("mode") or "n/a")),
                metric_label_value("Demand stock target", fmt_days(policy.get("demand_stock_target_days"), 1)),
                metric_label_value("Safety stock global", fmt_days(policy.get("safety_stock_days"), 1)),
            ]
        )
        nodes_payload[node_id] = {
            "title": "Modele du noeud",
            "summary_lines": summary_lines,
            "incoming": node_trace_asset,
            "outgoing": node_flow_asset,
            "third": node_ledger_asset,
            "fourth": node_order_asset,
        }

    for edge in raw.get("edges", []) or []:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if is_pilotage_hidden_edge(src, dst):
            continue
        items = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        attrs = edge.get("attrs") or {}
        planned_lead = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
        standard_order_qty = display_standard_order_qty(edge)
        standard_order_override = standard_order_override_for_edge(edge)
        metric = edge_metrics.get(edge_id, {})
        total_shipped = 0.0
        avg_util = None
        state_var_lines = [
            "BN_dst(t): besoin net porte par la destination sur cette lane",
            "OA_src(t): quantite demandee a la source apres normalisation lane",
            "Pull_src(t): quantite physiquement prelevee a la source",
            "RecvPrev_dst(t): quantite qui arrivera a destination a t + lead_time",
            "lead_effectif(t): lead observe + safety time destination",
        ]
        assumption_lines = [
            "la lane est simulee forward ; la date de commande reste implicite",
            "standard_order_qty joue comme multiple cible de commande quand disponible",
            "le lead time observe peut varier d'une expedition a l'autre",
        ]
        for item_id in items:
            total_shipped += sum(max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in supplier_ship_by_edge.get((src, dst, item_id), []))
            pair_cap_rows = supplier_cap_by_pair.get((src, item_id), [])
            if pair_cap_rows:
                util = sum(max(0.0, to_float(r.get("utilization")) or 0.0) for r in pair_cap_rows) / len(pair_cap_rows)
                avg_util = util if avg_util is None else max(avg_util, util)
        lane_data_lines = []
        for item_id in items:
            rows = supplier_ship_by_edge.get((src, dst, item_id), [])
            qty_values = [max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in rows]
            if rows:
                lane_data_lines.append(
                    f"{item_labels.get(item_id, compact_item_label(item_id))}: rows={len(rows)} ; qte_unique={len(set(round(v, 6) for v in qty_values))} ; expedie={fmt_qty(sum(qty_values))}"
                )
        edge_order_lines = []
        edge_order_rows = mrp_orders_by_edge.get(edge_id, [])
        for row in sorted(
            edge_order_rows,
            key=lambda r: (int(to_float(r.get("day")) or 0), str(r.get("item_id") or "")),
            reverse=True,
        )[:8]:
            edge_order_lines.append(
                f"{item_labels.get(str(row.get('item_id') or ''), compact_item_label(str(row.get('item_id') or '')))}: "
                f"release={row.get('release_day') or 'n/a'} ; "
                f"order_date_IMT={row.get('order_date_imt') or 'n/a'} ; "
                f"arrival={row.get('arrival_day') or 'n/a'} ; "
                f"lead={row.get('lead_days') or 'n/a'} ; "
                f"lead_cover={row.get('lead_cover_days') or 'n/a'} ; "
                f"status={row.get('order_status_end_of_run') or 'n/a'}"
            )
        edge_assumption_lines = []
        for row in assumptions_by_edge.get(edge_id, [])[:6]:
            edge_assumption_lines.append(
                f"{str(row.get('category') or 'n/a')} [{str(row.get('source') or 'n/a')}]"
            )
        edge_order_asset = None
        edge_lead_asset = None
        edge_status_asset = None
        edge_flow_figure = build_line_chart_figure(
            {
                "Release": aggregate_order_series(edge_order_rows, "release_qty", day_field="order_date_imt"),
                "Planned receipt": aggregate_order_series(edge_order_rows, "planned_receipt_qty", day_field="arrival_day"),
            },
            title=f"{edge_id} - releases / receipts",
            y_label="Quantite",
        )
        if edge_flow_figure is not None:
            edge_order_asset = {"figure": edge_flow_figure}
        edge_lead_figure = build_line_chart_figure(
            {
                "Lead observe": average_order_series(edge_order_rows, "lead_days"),
                "Lead cover": average_order_series(edge_order_rows, "lead_cover_days"),
                "Order date IMT": average_order_series(edge_order_rows, "order_date_imt"),
            },
            title=f"{edge_id} - lead / lead cover / order_date IMT",
            y_label="Jours",
        )
        if edge_lead_figure is not None:
            edge_lead_asset = {"figure": edge_lead_figure}
        edge_status_figure = status_bar_figure(
            edge_order_rows,
            field="order_status_end_of_run",
            title=f"{edge_id} - statuts du carnet d'ordres",
        )
        if edge_status_figure is not None:
            edge_status_asset = {"figure": edge_status_figure}
        source_refs = [
            " / ".join(part for part in [str(attrs.get("source_workbook") or ""), str(attrs.get("source_sheet") or "")] if part)
        ]
        summary_lines = [
            metric_section("Element"),
            metric_label_value("Flux", f"{src} -> {dst}"),
            metric_label_value("Items", ", ".join(item_labels.get(i, compact_item_label(i)) for i in items) or "n/a"),
            metric_label_value("Id lane", edge_id),
            metric_section("Variables d'etat"),
            *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
            metric_section("Equations simulateur"),
            metric_label_value("Eq sim 1", "BN_dst(t): besoin net destination porte par ce flux = max(0, cible_dst - stock_dst - in_transit_dst)"),
            metric_label_value("Eq sim 2", "OA_src(t): ordre amont sur la lane = quantite demandee a la source, normalisee si quantite standard"),
            metric_label_value("Eq sim 3", "RecvPrev_dst: reception planifiee destination = OA_src(t) * fiabilite"),
            metric_label_value("Eq sim 4", "arrival_date: date d'arrivee = t + lead_time echantillonne"),
            metric_label_value("Eq sim 5", "lead_effectif: lead observe + delai de securite destination"),
            metric_section("Equations IMT (slide)"),
            metric_label_value("Eq IMT 1", "order_date = t - lt_fournisseur - delai_securite"),
            metric_label_value("Eq IMT 2", "arrival_date = t"),
            metric_section("Comparaison IMT vs simulateur"),
            metric_label_value("IMT", "le flux est pilote par lt_fournisseur et delai_securite avec une order_date explicite"),
            metric_label_value("Simulateur", "le flux est pilote par une lane forward avec date d'arrivee explicite; la logique de date de commande reste implicite dans la boucle de simulation"),
            metric_section("Donnees et interactions"),
            metric_label_value("Lead time planifie", fmt_days(planned_lead, 1)),
            metric_label_value("Distance", f"{to_float(edge.get('distance_km')) or 0.0:.0f} km"),
            metric_label_value("Quantite standard", fmt_qty(standard_order_qty, 0) if standard_order_qty > 0 else "n/a"),
            metric_label_value("Correction quantite", str((standard_order_override or {}).get("note") or "n/a")),
            metric_label_value("Product code source", str(attrs.get("product_code") or "n/a")),
            metric_label_value("Compte fournisseur", str(attrs.get("supplier_account") or "n/a")),
            metric_multiline_value(
                "Donnees observees lane",
                lane_data_lines if lane_data_lines else ["aucune expedition observee sur cette lane"],
                limit=8,
            ),
            metric_section("Trace MRP explicite"),
            metric_multiline_value(
                "Carnet d'ordres lane",
                edge_order_lines if edge_order_lines else ["aucun ordre MRP direct sur ce flux ; flux probablement aval ou non pilote par appro"],
                limit=8,
            ),
            metric_section("Hypotheses"),
            *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
            metric_multiline_value(
                "Ledger hypotheses",
                edge_assumption_lines if edge_assumption_lines else ["aucune hypothese lane specifique journalisee"],
                limit=6,
            ),
            metric_section("KPI run courant"),
            metric_label_value("Expedie cumule", fmt_qty(total_shipped)),
            metric_label_value("Lignes expedition", str(metric.get("shipment_rows", 0))),
            metric_label_value("Lead observe moyen", fmt_days(metric.get("avg_lead_days"), 1)),
            metric_label_value("Lead observe p50/p90", f"{metric.get('lead_p50_days', 'n/a')} / {metric.get('lead_p90_days', 'n/a')} j"),
            metric_label_value("Lead observe min-max", f"{metric.get('min_lead_days', 'n/a')} - {metric.get('max_lead_days', 'n/a')} j"),
            metric_label_value("Quantites distinctes", str(metric.get("distinct_shipped_qty", 0))),
            metric_label_value("Utilisation source max", fmt_pct((avg_util or 0.0) * 100.0) if avg_util is not None else "n/a"),
            metric_section("Sources et parametres"),
            metric_multiline_value("Sources lane", unique_preserve(source_refs), limit=4),
        ]
        edges_payload[edge_id] = {
            "title": "Modele du flux",
            "summary_lines": summary_lines,
            "incoming": edge_order_asset,
            "outgoing": edge_lead_asset,
            "third": edge_status_asset,
        }

    return {"nodes": nodes_payload, "edges": edges_payload}


def build_realistic_sensitivity_panel_metrics(
    raw: dict[str, Any],
    summary_json: Path,
    local_elasticities_csv: Path,
    stress_impacts_csv: Path,
) -> dict[str, Any]:
    local_rows = read_csv_rows(local_elasticities_csv)
    stress_rows = read_csv_rows(stress_impacts_csv)
    if not local_rows and not stress_rows and not summary_json.exists():
        return {"nodes": {}, "global": {}}

    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.exists() else {}
    except Exception:
        summary = {}

    nodes = raw.get("nodes", []) or []
    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)

    def is_global_parameter(parameter_key: str) -> bool:
        return "::" not in parameter_key

    def row_scope(parameter_key: str, node_id: str) -> str | None:
        return sensitivity_row_scope(
            parameter_key,
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )

    def safe_abs(value: Any) -> float:
        num = to_float(value)
        if num is None or math.isnan(num):
            return 0.0
        return abs(num)

    def choose_local_global(kpi: str) -> dict[str, str] | None:
        candidates = [
            row
            for row in local_rows
            if str(row.get("kpi") or "") == kpi and is_global_parameter(str(row.get("parameter_key") or ""))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: safe_abs(row.get("abs_elasticity")))

    def choose_stress_global(kpi: str) -> dict[str, str] | None:
        delta_field = f"delta::{kpi}"
        candidates = [
            row
            for row in stress_rows
            if is_global_parameter(str(row.get("parameter_key") or ""))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: safe_abs(row.get(delta_field)))

    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_factory_capacity": 1,
        "upstream_reliability": 2,
        "upstream_factory_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_factory_lead_time": 3,
        "upstream_supplier_stock": 4,
        "item": 5,
        "downstream_demand": 6,
    }

    def choose_node_local(
        node_id: str,
        kpi: str,
        *,
        allowed_scopes: tuple[str, ...] | None = None,
        parameter_groups: tuple[str, ...] | None = None,
    ) -> dict[str, str] | None:
        candidates = []
        for row in local_rows:
            if str(row.get("kpi") or "") != kpi:
                continue
            if parameter_groups and str(row.get("parameter_group") or "") not in parameter_groups:
                continue
            scope = row_scope(str(row.get("parameter_key") or ""), node_id)
            if not scope:
                continue
            if allowed_scopes and scope not in allowed_scopes:
                continue
            candidates.append((scope_order.get(scope, 9), safe_abs(row.get("abs_elasticity")), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], -item[1], str(item[2].get("parameter_label") or "")))
        return candidates[0][2]

    def choose_node_stress(
        node_id: str,
        kpi: str,
        *,
        allowed_scopes: tuple[str, ...] | None = None,
        parameter_groups: tuple[str, ...] | None = None,
    ) -> dict[str, str] | None:
        delta_field = f"delta::{kpi}"
        candidates = []
        for row in stress_rows:
            if parameter_groups and str(row.get("parameter_group") or "") not in parameter_groups:
                continue
            scope = row_scope(str(row.get("parameter_key") or ""), node_id)
            if not scope:
                continue
            if allowed_scopes and scope not in allowed_scopes:
                continue
            candidates.append((scope_order.get(scope, 9), safe_abs(row.get(delta_field)), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], -item[1], str(item[2].get("parameter_label") or "")))
        return candidates[0][2]

    baseline = summary.get("baseline", {}) if isinstance(summary, dict) else {}
    baseline_fill = to_float((baseline or {}).get("fill_rate"))
    baseline_backlog = to_float((baseline or {}).get("ending_backlog"))
    baseline_cost = to_float((baseline or {}).get("total_cost"))

    def fmt_fill(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.1f}%"

    def fmt_backlog(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:,.0f}".replace(",", " ")

    def fmt_money(value: float | None) -> str:
        if value is None:
            return "n/a"
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f} k"
        return f"{value:.0f}"

    local_test_ranges: dict[str, tuple[float, float] | float] = {
        "lead_time": (0.9, 1.1),
        "transport_cost": (0.9, 1.1),
        "supplier_stock": (0.9, 1.1),
        "production_stock": (0.9, 1.1),
        "capacity_global": (0.95, 1.05),
        "supplier_capacity_global": (0.95, 1.05),
        "safety_stock": (0.9, 1.1),
        "supplier_reliability_global": 0.95,
        "demand_item": (0.9, 1.1),
        "capacity_node": (0.95, 1.05),
        "supplier_stock_node": (0.9, 1.1),
        "supplier_capacity_node": (0.9, 1.1),
        "supplier_lead_time_node": (0.9, 1.1),
        "supplier_reliability_node": 0.95,
    }

    def fmt_factor(value: float | None) -> str:
        if value is None or math.isnan(value):
            return "n/a"
        return f"x{value:.2f}"

    def local_test_label(row: dict[str, str] | None) -> str:
        if not row:
            return "amplitude n/a"
        group = str(row.get("parameter_group") or "")
        spec = local_test_ranges.get(group)
        if isinstance(spec, tuple):
            return f"test {fmt_factor(spec[0])} / {fmt_factor(spec[1])}"
        if isinstance(spec, float):
            return f"test {fmt_factor(spec)}"
        return "test n/a"

    def stress_test_label(row: dict[str, str] | None) -> str:
        if not row:
            return "choc n/a"
        factor_value = to_float(row.get("factor_value"))
        if factor_value is None or math.isnan(factor_value):
            return "choc n/a"
        return f"choc x1.00 -> {fmt_factor(factor_value)}"

    def describe_local(row: dict[str, str] | None, *, kpi: str) -> str:
        if not row:
            return "n/a"
        label = str(row.get("parameter_label") or row.get("parameter_key") or "").strip()
        elasticity = to_float(row.get("abs_elasticity"))
        if elasticity is None or math.isnan(elasticity):
            return label or "n/a"
        suffix = ""
        if str(row.get("parameter_key") or "").startswith("demand_item::"):
            suffix = " (via produit)"
        return f"{label}{suffix} | {local_test_label(row)} | e={elasticity:.3f}"

    def describe_stress(row: dict[str, str] | None, *, kpi: str) -> str:
        if not row:
            return "n/a"
        label = str(row.get("parameter_label") or row.get("parameter_key") or "").strip()
        delta = to_float(row.get(f"delta::{kpi}"))
        if delta is None or math.isnan(delta):
            return label or "n/a"
        if kpi == "fill_rate":
            value = f"{delta * 100:+.1f} pts"
        elif kpi == "ending_backlog":
            value = f"{delta:+,.0f}".replace(",", " ")
        else:
            value = f"{fmt_money(delta)}"
            if not value.startswith("-") and not value.startswith("+"):
                value = f"+{value}"
        suffix = ""
        if str(row.get("parameter_key") or "").startswith("demand_item::"):
            suffix = " (via produit)"
        return f"{label}{suffix} | {stress_test_label(row)} | {value}"

    global_fill_local = choose_local_global("fill_rate")
    global_fill_stress = choose_stress_global("fill_rate")
    global_cost_local = choose_local_global("total_cost")
    global_cost_stress = choose_stress_global("total_cost")

    def classify_node(node_id: str) -> str:
        node_type = node_types.get(node_id, "")
        service_stress = safe_abs((choose_node_stress(node_id, "fill_rate") or {}).get("delta::fill_rate"))
        backlog_stress = safe_abs((choose_node_stress(node_id, "ending_backlog") or {}).get("delta::ending_backlog"))
        cost_stress = safe_abs((choose_node_stress(node_id, "total_cost") or {}).get("delta::total_cost"))
        service_elasticity = safe_abs((choose_node_local(node_id, "fill_rate") or {}).get("abs_elasticity"))
        if node_type == "factory":
            upstream_rel = safe_abs(
                (
                    choose_node_stress(
                        node_id,
                        "fill_rate",
                        allowed_scopes=("upstream_reliability",),
                    )
                    or {}
                ).get("delta::fill_rate")
            )
            upstream_lt = safe_abs(
                (
                    choose_node_stress(
                        node_id,
                        "fill_rate",
                        allowed_scopes=("upstream_lead_time",),
                    )
                    or {}
                ).get("delta::fill_rate")
            )
            if service_stress >= 0.05 or backlog_stress >= 200_000 or upstream_rel >= 0.03:
                return "Usine critique pour le service"
            if upstream_lt >= 0.01 or service_elasticity >= 0.03:
                return "Usine sensible aux flux amont"
            return "Usine robuste localement"
        if node_type == "supplier_dc":
            if service_stress >= 0.03 or backlog_stress >= 100_000:
                return "Fournisseur critique"
            if cost_stress >= 250_000:
                return "Fournisseur critique cout"
            return "Impact fournisseur limite"
        if node_type == "distribution_center":
            if service_stress >= 0.02 or backlog_stress >= 100_000:
                return "DC sensible a la demande"
            return "DC plutot robuste"
        if service_stress >= 0.05 or backlog_stress >= 1000 or service_elasticity >= 0.05:
            return "Critique service"
        if cost_stress >= 250_000:
            return "Critique cout"
        if service_stress >= 0.01 or backlog_stress >= 250 or cost_stress >= 25_000:
            return "Surveiller"
        return "Impact local faible"

    def node_summary_lines(node_id: str) -> list[dict[str, str]]:
        node_type = node_types.get(node_id, "")
        service_line = metric_label_value(
            "Service lie",
            describe_stress(choose_node_stress(node_id, "fill_rate"), kpi="fill_rate"),
        )
        backlog_line = metric_label_value(
            "Backlog lie",
            describe_stress(choose_node_stress(node_id, "ending_backlog"), kpi="ending_backlog"),
        )
        cost_line = metric_label_value(
            "Cout lie",
            describe_stress(choose_node_stress(node_id, "total_cost"), kpi="total_cost"),
        )
        baseline_line = metric_label_value(
            "Baseline",
            f"FR {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
        )
        if node_type == "factory":
            return [
                baseline_line,
                service_line,
                backlog_line,
                metric_label_value(
                    "Capacite usine",
                    describe_local(
                        choose_node_local(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("capacity_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Backlog usine",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "ending_backlog",
                            allowed_scopes=("direct",),
                            parameter_groups=("capacity_node",),
                        ),
                        kpi="ending_backlog",
                    ),
                ),
                metric_label_value(
                    "Fiabilite amont",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("upstream_reliability",),
                            parameter_groups=("supplier_reliability_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Lead time amont",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("upstream_lead_time",),
                            parameter_groups=("supplier_lead_time_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                cost_line,
                metric_label_value("Statut", classify_node(node_id)),
            ]
        if node_type == "supplier_dc":
            return [
                baseline_line,
                service_line,
                backlog_line,
                metric_label_value(
                    "Fiabilite locale",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("supplier_reliability_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Lead time local",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("supplier_lead_time_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Debit local",
                    describe_local(
                        choose_node_local(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("supplier_capacity_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                cost_line,
                metric_label_value("Statut", classify_node(node_id)),
            ]
        if node_type == "distribution_center":
            return [
                baseline_line,
                service_line,
                backlog_line,
                metric_label_value(
                    "Demande liee",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("item",),
                            parameter_groups=("demand_item",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Usine amont",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("upstream_factory_capacity",),
                            parameter_groups=("capacity_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                cost_line,
                metric_label_value("Statut", classify_node(node_id)),
            ]
        return [
            baseline_line,
            metric_label_value("Service global", describe_stress(global_fill_stress, kpi="fill_rate")),
            service_line,
            metric_label_value(
                "Elasticite service",
                describe_local(choose_node_local(node_id, "fill_rate"), kpi="fill_rate"),
            ),
            backlog_line,
            metric_label_value("Cout global", describe_stress(global_cost_stress, kpi="total_cost")),
            cost_line,
            metric_label_value(
                "Elasticite cout",
                describe_local(choose_node_local(node_id, "total_cost"), kpi="total_cost"),
            ),
            metric_label_value("Statut", classify_node(node_id)),
        ]

    nodes_payload: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        nodes_payload[node_id] = {
            "title": "Sensibilite realiste annuelle",
            "summary_lines": node_summary_lines(node_id),
        }

    global_payload = {
        "title": "Sensibilite realiste annuelle",
        "summary_lines": [
            metric_label_value(
                "Baseline",
                f"FR {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
            ),
            metric_label_value("Service global", describe_stress(global_fill_stress, kpi="fill_rate")),
            metric_label_value("Elasticite service", describe_local(global_fill_local, kpi="fill_rate")),
            metric_label_value("Cout global", describe_stress(global_cost_stress, kpi="total_cost")),
            metric_label_value("Elasticite cout", describe_local(global_cost_local, kpi="total_cost")),
        ],
    }
    selected_suppliers = summary.get("selected_suppliers", []) if isinstance(summary, dict) else []
    return {"nodes": nodes_payload, "global": global_payload, "selected_suppliers": selected_suppliers}


def build_threshold_sensitivity_panel_metrics(
    raw: dict[str, Any],
    summary_json: Path,
    parameter_summary_csv: Path,
) -> dict[str, Any]:
    rows = read_csv_rows(parameter_summary_csv)
    if not rows and not summary_json.exists():
        return {"nodes": {}, "global": {}, "selected_suppliers": []}

    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.exists() else {}
    except Exception:
        summary = {}

    nodes = raw.get("nodes", []) or []
    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)

    def metric(label: str, value: Any, *, section: bool = False) -> dict[str, Any]:
        return {"label": label, "value": str(value), "section": section}

    def safe_float(value: Any) -> float | None:
        num = to_float(value)
        if num is None or math.isnan(num):
            return None
        return float(num)

    def fmt_fill(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.1f}%"

    def fmt_backlog(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:,.0f}".replace(",", " ")

    def fmt_money(value: float | None) -> str:
        if value is None:
            return "n/a"
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f} k"
        return f"{value:.0f}"

    def fmt_level(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"x{value:.2f}"

    def side_label(row: dict[str, str]) -> str:
        mono = str(row.get("fill_rate_monotonicity") or "").strip().lower()
        cross = safe_float(row.get("fill_rate_cross_service_threshold_at"))
        if cross is None:
            return "pas de rupture dans le sweep"
        if mono == "increasing":
            return f"rupture si < {fmt_level(cross)}"
        if mono == "decreasing":
            return f"rupture si > {fmt_level(cross)}"
        return f"rupture autour de {fmt_level(cross)}"

    def safe_band_label(row: dict[str, str]) -> str:
        low = safe_float(row.get("safe_band_low"))
        high = safe_float(row.get("safe_band_high"))
        if low is None and high is None:
            return "aucune bande sure identifiee"
        if low is None:
            return f"<= {fmt_level(high)}"
        if high is None:
            return f">= {fmt_level(low)}"
        return f"{fmt_level(low)} a {fmt_level(high)}"

    def max_fill_drop_pts(row: dict[str, str]) -> str:
        value = safe_float(row.get("max_fill_rate_drop"))
        if value is None:
            return "n/a"
        return f"{value * 100:.1f} pts"

    def steepest_segment_label(row: dict[str, str]) -> str:
        raw_segment = str(row.get("steepest_fill_segment") or "").strip()
        if not raw_segment:
            return "n/a"
        try:
            values = json.loads(raw_segment)
            if isinstance(values, list) and len(values) == 2:
                return f"{fmt_level(safe_float(values[0]))} -> {fmt_level(safe_float(values[1]))}"
        except Exception:
            pass
        return raw_segment

    def is_global_parameter(parameter_key: str) -> bool:
        return "::" not in parameter_key

    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_factory_capacity": 1,
        "upstream_reliability": 2,
        "upstream_factory_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_factory_lead_time": 3,
        "upstream_supplier_stock": 4,
        "item": 5,
        "downstream_demand": 6,
    }

    def row_scope(row: dict[str, str], node_id: str) -> str | None:
        return sensitivity_row_scope(
            str(row.get("parameter_key") or ""),
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )

    def row_rank(row: dict[str, str], node_id: str) -> tuple[float, int, float]:
        cross = safe_float(row.get("fill_rate_cross_service_threshold_at"))
        max_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        scope = row_scope(row, node_id)
        scope_rank = scope_order.get(scope, 9)
        if cross is None:
            return (999.0, scope_rank, -max_drop)
        return (abs(cross - 1.0), scope_rank, -max_drop)

    def choose_global_best() -> dict[str, str] | None:
        candidates = [row for row in rows if is_global_parameter(str(row.get("parameter_key") or ""))]
        if not candidates:
            return None
        candidates.sort(
            key=lambda row: (
                999.0 if safe_float(row.get("fill_rate_cross_service_threshold_at")) is None else abs(
                    (safe_float(row.get("fill_rate_cross_service_threshold_at")) or 1.0) - 1.0
                ),
                -(safe_float(row.get("max_fill_rate_drop")) or 0.0),
                str(row.get("parameter_label") or ""),
            )
        )
        return candidates[0]

    def choose_node_best(node_id: str) -> dict[str, str] | None:
        candidates = [row for row in rows if row_scope(row, node_id)]
        if not candidates:
            return None
        candidates.sort(key=lambda row: row_rank(row, node_id))
        return candidates[0]

    def classify(row: dict[str, str] | None) -> str:
        if not row:
            return "Pas de signal seuil"
        cross = safe_float(row.get("fill_rate_cross_service_threshold_at"))
        max_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        if cross is not None and abs(cross - 1.0) <= 0.10:
            return "Critique"
        if cross is not None and abs(cross - 1.0) <= 0.25:
            return "Sensible"
        if max_drop >= 0.05:
            return "A surveiller"
        return "Robuste localement"

    baseline = summary.get("baseline", {}) if isinstance(summary, dict) else {}
    baseline_fill = safe_float((baseline or {}).get("kpi::fill_rate"))
    baseline_backlog = safe_float((baseline or {}).get("kpi::ending_backlog"))
    baseline_cost = safe_float((baseline or {}).get("kpi::total_cost"))
    service_threshold = safe_float(summary.get("service_threshold")) or 0.95
    selected_suppliers = summary.get("selected_suppliers", []) if isinstance(summary, dict) else []

    global_best = choose_global_best()
    global_payload = {
        "title": "Seuils annuels",
        "summary_lines": [
            metric(
                "Baseline",
                f"FR {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
            ),
            metric("Service cible", fmt_fill(service_threshold)),
            metric("Levier global critique", str((global_best or {}).get("parameter_label") or "n/a")),
            metric("Point de bascule", side_label(global_best or {})),
            metric("Bande sure", safe_band_label(global_best or {})),
            metric("Max fill drop", max_fill_drop_pts(global_best or {})),
            metric("Segment le plus raide", steepest_segment_label(global_best or {})),
            metric("Statut", classify(global_best)),
        ],
    }

    nodes_payload: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        best_row = choose_node_best(node_id)
        if best_row is None:
            continue
        nodes_payload[node_id] = {
            "title": "Seuils annuels",
            "summary_lines": [
                metric(
                    "Baseline",
                    f"FR {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
                ),
                metric("Service cible", fmt_fill(service_threshold)),
                metric("Driver critique", str(best_row.get("parameter_label") or "n/a")),
                metric("Point de bascule", side_label(best_row)),
                metric("Bande sure", safe_band_label(best_row)),
                metric("Max fill drop", max_fill_drop_pts(best_row)),
                metric("Segment le plus raide", steepest_segment_label(best_row)),
                metric("Statut", classify(best_row)),
            ],
        }

    return {"nodes": nodes_payload, "global": global_payload, "selected_suppliers": selected_suppliers}


def build_node_item_ids(raw: dict[str, Any]) -> dict[str, set[str]]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    node_item_ids: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        node_item_ids[node_id].update(incoming_items.get(node_id, set()))
        node_item_ids[node_id].update(outgoing_items.get(node_id, set()))
        inventory = node.get("inventory") or {}
        for state in (inventory.get("states") or []):
            item_id = str((state or {}).get("item_id") or "")
            if item_id:
                node_item_ids[node_id].add(item_id)
        for process in (node.get("processes") or []):
            for inp in (process.get("inputs") or []):
                item_id = str((inp or {}).get("item_id") or "")
                if item_id:
                    node_item_ids[node_id].add(item_id)
            for out in (process.get("outputs") or []):
                item_id = str((out or {}).get("item_id") or "")
                if item_id:
                    node_item_ids[node_id].add(item_id)
    return node_item_ids


def threshold_row_scope(
    row: dict[str, str],
    node_id: str,
    node_item_ids: dict[str, set[str]],
    node_types: dict[str, str],
    incoming_sources: dict[str, set[str]],
    outgoing_targets: dict[str, set[str]],
) -> str | None:
    return sensitivity_row_scope(
        str(row.get("parameter_key") or ""),
        node_id,
        node_item_ids,
        node_types,
        incoming_sources,
        outgoing_targets,
    )


def select_best_threshold_parameter_row(
    summary_rows: list[dict[str, str]],
    node_id: str,
    node_item_ids: dict[str, set[str]],
    node_types: dict[str, str],
    incoming_sources: dict[str, set[str]],
    outgoing_targets: dict[str, set[str]],
) -> dict[str, str] | None:
    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_factory_capacity": 1,
        "upstream_reliability": 2,
        "upstream_factory_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_factory_lead_time": 3,
        "upstream_supplier_stock": 4,
        "item": 5,
        "downstream_demand": 6,
    }
    candidates = []
    for row in summary_rows:
        scope = threshold_row_scope(
            row,
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )
        if not scope:
            continue
        cross = to_float(row.get("fill_rate_cross_service_threshold_at"))
        max_drop = to_float(row.get("max_fill_rate_drop")) or 0.0
        scope_rank = scope_order.get(scope, 9)
        cross_rank = 999.0 if cross is None or math.isnan(cross) else abs(cross - 1.0)
        candidates.append((cross_rank, scope_rank, -max_drop, str(row.get("parameter_label") or ""), row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return candidates[0][4]


def build_threshold_metric_curve_payload(
    parameter_rows: list[dict[str, str]],
    *,
    parameter_label: str,
    filename: str,
    service_threshold: float | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    usable_rows = []
    for row in parameter_rows:
        level = to_float(row.get("level"))
        if level is None or math.isnan(level):
            continue
        usable_rows.append((float(level), row))
    usable_rows.sort(key=lambda item: item[0])
    if len(usable_rows) < 2:
        return None, None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None, None

    x = [level for level, _ in usable_rows]
    fill = [float(to_float(row.get("kpi::fill_rate")) or 0.0) for _, row in usable_rows]
    backlog = [float(to_float(row.get("kpi::ending_backlog")) or 0.0) for _, row in usable_rows]
    total_cost = [float(to_float(row.get("kpi::total_cost")) or 0.0) for _, row in usable_rows]
    avg_inventory = [float(to_float(row.get("kpi::avg_inventory")) or 0.0) for _, row in usable_rows]

    base_fill = None
    base_backlog = None
    base_cost = None
    base_inventory = None
    for level, row in usable_rows:
        if abs(level - 1.0) <= 1e-9:
            base_fill = float(to_float(row.get("kpi::fill_rate")) or 0.0)
            base_backlog = float(to_float(row.get("kpi::ending_backlog")) or 0.0)
            base_cost = float(to_float(row.get("kpi::total_cost")) or 0.0)
            base_inventory = float(to_float(row.get("kpi::avg_inventory")) or 0.0)
            break

    def format_level(value: float) -> str:
        return f"x{value:.2f}"

    incoming_fig, incoming_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    incoming_fig.patch.set_facecolor("#ffffff")
    ax_fill = incoming_axes[0]
    ax_fill.plot(x, fill, color="#2563eb", marker="o", linewidth=2.2)
    if service_threshold is not None and not math.isnan(service_threshold):
        ax_fill.axhline(service_threshold, color="#dc2626", linestyle="--", linewidth=1.2)
    ax_fill.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_fill is not None:
        ax_fill.axhline(base_fill, color="#0f766e", linestyle=":", linewidth=1.0)
    ax_fill.set_ylabel("Fill rate")
    ax_fill.set_title(f"{parameter_label} - service", fontsize=12, pad=10)
    ax_fill.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_fill.set_facecolor("#ffffff")

    ax_backlog = incoming_axes[1]
    ax_backlog.plot(x, backlog, color="#d97706", marker="o", linewidth=2.2)
    ax_backlog.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_backlog is not None:
        ax_backlog.axhline(base_backlog, color="#0f766e", linestyle=":", linewidth=1.0)
    ax_backlog.set_ylabel("Backlog")
    ax_backlog.set_xlabel("Niveau du parametre")
    ax_backlog.set_xticks(x)
    ax_backlog.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_backlog.set_title(f"{parameter_label} - backlog final", fontsize=11, pad=8)
    ax_backlog.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_backlog.set_facecolor("#ffffff")
    incoming_fig.tight_layout()
    incoming_buf = io.BytesIO()
    incoming_fig.savefig(incoming_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(incoming_fig)
    incoming_payload = png_payload_from_bytes(incoming_buf.getvalue(), filename.replace(".png", "_service.png"))

    outgoing_fig, outgoing_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    outgoing_fig.patch.set_facecolor("#ffffff")
    ax_cost = outgoing_axes[0]
    ax_cost.plot(x, total_cost, color="#7c3aed", marker="o", linewidth=2.2)
    ax_cost.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_cost is not None:
        ax_cost.axhline(base_cost, color="#0f766e", linestyle=":", linewidth=1.0)
    ax_cost.set_ylabel("Cout total")
    ax_cost.set_title(f"{parameter_label} - cout", fontsize=12, pad=10)
    ax_cost.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_cost.set_facecolor("#ffffff")

    ax_inv = outgoing_axes[1]
    ax_inv.plot(x, avg_inventory, color="#0f766e", marker="o", linewidth=2.2)
    ax_inv.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_inventory is not None:
        ax_inv.axhline(base_inventory, color="#2563eb", linestyle=":", linewidth=1.0)
    ax_inv.set_ylabel("Inventaire moyen")
    ax_inv.set_xlabel("Niveau du parametre")
    ax_inv.set_xticks(x)
    ax_inv.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_inv.set_title(f"{parameter_label} - inventaire", fontsize=11, pad=8)
    ax_inv.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_inv.set_facecolor("#ffffff")
    outgoing_fig.tight_layout()
    outgoing_buf = io.BytesIO()
    outgoing_fig.savefig(outgoing_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(outgoing_fig)
    outgoing_payload = png_payload_from_bytes(outgoing_buf.getvalue(), filename.replace(".png", "_economic.png"))

    return incoming_payload, outgoing_payload


def read_supplier_case_metrics(
    case_output_dir: Path,
    node_id: str,
    cache: dict[tuple[str, str], dict[str, float]],
) -> dict[str, float]:
    cache_key = (str(case_output_dir), node_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data_dir = case_output_dir / "data"
    shipped_total = 0.0
    stock_values: list[float] = []
    util_values: list[float] = []

    shipments_csv = data_dir / "production_supplier_shipments_daily.csv"
    if shipments_csv.exists():
        try:
            for row in read_csv_rows(shipments_csv):
                if str(row.get("src_node_id") or "") != node_id:
                    continue
                shipped_total += float(to_float(row.get("shipped_qty")) or 0.0)
        except Exception:
            shipped_total = 0.0

    stocks_csv = data_dir / "production_supplier_stocks_daily.csv"
    if stocks_csv.exists():
        try:
            for row in read_csv_rows(stocks_csv):
                if str(row.get("node_id") or "") != node_id:
                    continue
                stock_values.append(float(to_float(row.get("stock_end_of_day")) or 0.0))
        except Exception:
            stock_values = []

    capacity_csv = data_dir / "production_supplier_capacity_daily.csv"
    if capacity_csv.exists():
        try:
            for row in read_csv_rows(capacity_csv):
                if str(row.get("node_id") or "") != node_id:
                    continue
                util_values.append(float(to_float(row.get("utilization")) or 0.0))
        except Exception:
            util_values = []

    metrics = {
        "total_shipped": shipped_total,
        "avg_stock": (sum(stock_values) / len(stock_values)) if stock_values else 0.0,
        "ending_stock": stock_values[-1] if stock_values else 0.0,
        "avg_utilization": (sum(util_values) / len(util_values)) if util_values else 0.0,
    }
    cache[cache_key] = metrics
    return metrics


def build_supplier_threshold_metric_curve_payload(
    parameter_rows: list[dict[str, str]],
    *,
    node_id: str,
    parameter_label: str,
    filename: str,
    metrics_cache: dict[tuple[str, str], dict[str, float]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    usable_rows = []
    for row in parameter_rows:
        level = to_float(row.get("level"))
        case_output_dir = str(row.get("case_output_dir") or "").strip()
        if level is None or math.isnan(level) or not case_output_dir:
            continue
        usable_rows.append((float(level), row, Path(case_output_dir)))
    usable_rows.sort(key=lambda item: item[0])
    if len(usable_rows) < 2:
        return None, None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None, None

    x = [level for level, _, _ in usable_rows]
    shipped = []
    avg_stock = []
    ending_stock = []
    avg_utilization = []
    for _, _, case_output_dir in usable_rows:
        metrics = read_supplier_case_metrics(case_output_dir, node_id, metrics_cache)
        shipped.append(float(metrics.get("total_shipped") or 0.0))
        avg_stock.append(float(metrics.get("avg_stock") or 0.0))
        ending_stock.append(float(metrics.get("ending_stock") or 0.0))
        avg_utilization.append(float(metrics.get("avg_utilization") or 0.0))

    def format_level(value: float) -> str:
        return f"x{value:.2f}"

    incoming_fig, incoming_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    incoming_fig.patch.set_facecolor("#ffffff")

    ax_ship = incoming_axes[0]
    ax_ship.plot(x, shipped, color="#2563eb", marker="o", linewidth=2.2)
    ax_ship.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_ship.set_ylabel("Expedie total")
    ax_ship.set_title(f"{parameter_label} - flux fournisseur", fontsize=12, pad=10)
    ax_ship.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_ship.set_facecolor("#ffffff")

    ax_avg_stock = incoming_axes[1]
    ax_avg_stock.plot(x, avg_stock, color="#0f766e", marker="o", linewidth=2.2)
    ax_avg_stock.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_avg_stock.set_ylabel("Stock moyen")
    ax_avg_stock.set_xlabel("Niveau du parametre")
    ax_avg_stock.set_xticks(x)
    ax_avg_stock.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_avg_stock.set_title(f"{parameter_label} - stock moyen fournisseur", fontsize=11, pad=8)
    ax_avg_stock.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_avg_stock.set_facecolor("#ffffff")
    incoming_fig.tight_layout()
    incoming_buf = io.BytesIO()
    incoming_fig.savefig(incoming_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(incoming_fig)
    incoming_payload = png_payload_from_bytes(
        incoming_buf.getvalue(),
        filename.replace(".png", "_supplier_local_flow.png"),
    )

    outgoing_fig, outgoing_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    outgoing_fig.patch.set_facecolor("#ffffff")

    ax_util = outgoing_axes[0]
    ax_util.plot(x, avg_utilization, color="#7c3aed", marker="o", linewidth=2.2)
    ax_util.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_util.set_ylabel("Utilisation moy.")
    ax_util.set_title(f"{parameter_label} - utilisation capacite", fontsize=12, pad=10)
    ax_util.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_util.set_facecolor("#ffffff")

    ax_end_stock = outgoing_axes[1]
    ax_end_stock.plot(x, ending_stock, color="#d97706", marker="o", linewidth=2.2)
    ax_end_stock.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_end_stock.set_ylabel("Stock final")
    ax_end_stock.set_xlabel("Niveau du parametre")
    ax_end_stock.set_xticks(x)
    ax_end_stock.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_end_stock.set_title(f"{parameter_label} - stock final fournisseur", fontsize=11, pad=8)
    ax_end_stock.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_end_stock.set_facecolor("#ffffff")
    outgoing_fig.tight_layout()
    outgoing_buf = io.BytesIO()
    outgoing_fig.savefig(outgoing_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(outgoing_fig)
    outgoing_payload = png_payload_from_bytes(
        outgoing_buf.getvalue(),
        filename.replace(".png", "_supplier_local_state.png"),
    )

    return incoming_payload, outgoing_payload


def build_threshold_hover_payloads(
    raw: dict[str, Any],
    threshold_parameter_summary_csv: Path,
    threshold_sweep_cases_csv: Path,
    threshold_summary_json: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    summary_rows = read_csv_rows(threshold_parameter_summary_csv)
    case_rows = read_csv_rows(threshold_sweep_cases_csv)
    if not summary_rows or not case_rows:
        return {}, {}, {}

    try:
        summary = json.loads(threshold_summary_json.read_text(encoding="utf-8")) if threshold_summary_json.exists() else {}
    except Exception:
        summary = {}
    service_threshold = to_float(summary.get("service_threshold"))

    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)
    case_rows_by_param: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in case_rows:
        if str(row.get("status") or "").lower() != "ok":
            continue
        parameter_key = str(row.get("parameter_key") or "")
        if not parameter_key or parameter_key == "baseline":
            continue
        case_rows_by_param[parameter_key].append(row)

    factory_out: dict[str, Any] = {}
    supplier_out: dict[str, Any] = {}
    dc_out: dict[str, Any] = {}
    supplier_metrics_cache: dict[tuple[str, str], dict[str, float]] = {}

    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if node_type not in {"factory", "supplier_dc", "distribution_center"}:
            continue
        best_row = select_best_threshold_parameter_row(
            summary_rows,
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )
        if best_row is None:
            continue
        parameter_key = str(best_row.get("parameter_key") or "")
        parameter_label = str(best_row.get("parameter_label") or parameter_key)
        parameter_cases = case_rows_by_param.get(parameter_key, [])
        if node_type == "supplier_dc" and parameter_key.endswith(f"::{node_id}"):
            incoming, outgoing = build_supplier_threshold_metric_curve_payload(
                parameter_cases,
                node_id=node_id,
                parameter_label=parameter_label,
                filename=f"{safe_case_token(node_id)}_threshold.png",
                metrics_cache=supplier_metrics_cache,
            )
        else:
            incoming, outgoing = build_threshold_metric_curve_payload(
                parameter_cases,
                parameter_label=parameter_label,
                filename=f"{safe_case_token(node_id)}_threshold.png",
                service_threshold=service_threshold,
            )
        if not incoming and not outgoing:
            continue
        payload = {"incoming": incoming, "outgoing": outgoing}
        if node_type == "factory":
            factory_out[node_id] = payload
        elif node_type == "supplier_dc":
            supplier_out[node_id] = payload
        else:
            dc_out[node_id] = payload

    return factory_out, supplier_out, dc_out


def merge_hover_payload_maps(
    primary: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    node_ids = set(primary) | set(fallback)
    for node_id in node_ids:
        primary_payload = primary.get(node_id) or {}
        fallback_payload = fallback.get(node_id) or {}
        incoming = primary_payload.get("incoming") or fallback_payload.get("incoming")
        outgoing = primary_payload.get("outgoing") or fallback_payload.get("outgoing")
        third = primary_payload.get("third") or fallback_payload.get("third")
        if incoming or outgoing or third:
            merged[node_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
    return merged


def build_supplier_local_criticality(
    raw: dict[str, Any],
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_capacity_csv: Path,
    production_constraint_csv: Path,
    sensitivity_cases_csv: Path,
    structural_sensitivity_cases_csv: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    nodes = raw.get("nodes", []) or []
    edges = raw.get("edges", []) or []
    supplier_ids = sorted(str(n.get("id")) for n in nodes if str(n.get("type") or "") == "supplier_dc")
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}
    supplier_has_explicit_capacity = {
        str(n.get("id")): any(
            to_float(((proc.get("capacity") or {}).get("max_rate"))) not in (None, 0.0)
            and (to_float(((proc.get("capacity") or {}).get("max_rate"))) or 0.0) > 0.0
            for proc in (n.get("processes") or [])
        )
        for n in nodes
        if str(n.get("type") or "") == "supplier_dc"
    }
    supplier_nominal_capacity_by_supplier: dict[str, float] = {}
    supplier_capacity_basis_by_supplier: dict[str, str] = {}
    supplier_capacity_scale_by_supplier: dict[str, float] = {}
    for n in nodes:
        if str(n.get("type") or "") != "supplier_dc":
            continue
        supplier_id = str(n.get("id") or "")
        constraints = n.get("simulation_constraints") or {}
        item_caps = constraints.get("supplier_item_capacity_qty_per_day") or {}
        item_basis = constraints.get("supplier_item_capacity_basis") or {}
        capacity_scale = max(0.0, to_float(constraints.get("supplier_capacity_scale")) or 0.0)
        supplier_capacity_scale_by_supplier[supplier_id] = capacity_scale
        if isinstance(item_caps, dict) and item_caps:
            supplier_nominal_capacity_by_supplier[supplier_id] = max(
                max(0.0, to_float(value) or 0.0) for value in item_caps.values()
            )
        if isinstance(item_basis, dict) and item_basis:
            basis_values = sorted({str(value) for value in item_basis.values() if str(value).strip()})
            supplier_capacity_basis_by_supplier[supplier_id] = ", ".join(basis_values)
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    edges_by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    suppliers_for_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    target_share_by_supplier_pair: dict[tuple[str, tuple[str, str]], float] = {}
    supplier_initial_total: dict[str, float] = {}
    for n in nodes:
        if str(n.get("type") or "") != "supplier_dc":
            continue
        supplier_initial_total[str(n.get("id"))] = sum(
            max(0.0, to_float((st or {}).get("initial")) or 0.0)
            for st in ((n.get("inventory") or {}).get("states") or [])
        )
    for e in edges:
        src = str(e.get("from") or "")
        dst = str(e.get("to") or "")
        if src:
            edges_by_src[src].append(e)
        for item_id in e.get("items") or []:
            suppliers_for_pair[(dst, str(item_id))].add(src)

    def edge_transport_cost(edge: dict[str, Any]) -> float:
        tc = edge.get("transport_cost") or {}
        val = to_float((tc or {}).get("value"))
        if val is not None and val > 0:
            return val
        distance = to_float(edge.get("distance_km"))
        return max(0.02, (distance or 0.0) * 0.00008)

    def edge_lead_days(edge: dict[str, Any]) -> float:
        return max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)

    def mrp_split_shares(count: int) -> list[float]:
        if count <= 0:
            return []
        if count == 1:
            return [1.0]
        if count == 2:
            return [0.7, 0.3]
        if count == 3:
            return [0.7, 0.2, 0.1]
        tail = 0.1 / float(count - 2)
        return [0.7, 0.2] + [tail] * (count - 2)

    edges_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        dst = str(edge.get("to") or "")
        src = str(edge.get("from") or "")
        if not dst or not src:
            continue
        for item_id in edge.get("items") or []:
            edges_by_pair[(dst, str(item_id))].append(edge)
    for pair, pair_edges in edges_by_pair.items():
        sorted_edges = sorted(
            pair_edges,
            key=lambda edge: (
                edge_transport_cost(edge),
                edge_lead_days(edge),
                str(edge.get("from") or ""),
            ),
        )
        shares = mrp_split_shares(len(sorted_edges))
        for edge, share in zip(sorted_edges, shares):
            target_share_by_supplier_pair[(str(edge.get("from") or ""), pair)] = share

    avg_procurement_lead_days_by_supplier: dict[str, float] = {}
    for supplier_id, supplier_edges in edges_by_src.items():
        lead_values = [edge_lead_days(edge) for edge in supplier_edges if str(edge.get("from") or "") == supplier_id]
        avg_procurement_lead_days_by_supplier[supplier_id] = (
            sum(lead_values) / len(lead_values) if lead_values else 0.0
        )

    shipment_rows = read_csv_rows(supplier_shipments_csv)
    stock_rows = read_csv_rows(supplier_stocks_csv)
    capacity_rows = read_csv_rows(supplier_capacity_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    sensitivity_case_rows = read_csv_rows(sensitivity_cases_csv)
    structural_case_rows = read_csv_rows(structural_sensitivity_cases_csv)
    by_case_std = case_rows_by_id(sensitivity_case_rows)
    by_case_struct = case_rows_by_id(structural_case_rows)
    baseline_std = by_case_std.get("baseline")
    baseline_struct = by_case_struct.get("baseline")

    shipped_qty_by_supplier: dict[str, float] = defaultdict(float)
    shipped_qty_by_supplier_pair: dict[tuple[str, tuple[str, str]], float] = defaultdict(float)
    total_pair_flow_qty: dict[tuple[str, str], float] = defaultdict(float)
    active_days_by_supplier: dict[str, set[int]] = defaultdict(set)
    first_day_by_supplier: dict[str, int] = {}
    last_day_by_supplier: dict[str, int] = {}
    for row in shipment_rows:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        qty = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        day = int(to_float(row.get("day")) or 0)
        if not src:
            continue
        shipped_qty_by_supplier[src] += qty
        if dst and item_id:
            pair = (dst, item_id)
            shipped_qty_by_supplier_pair[(src, pair)] += qty
            total_pair_flow_qty[pair] += qty
        if qty > 0:
            active_days_by_supplier[src].add(day)
            first_day_by_supplier[src] = min(first_day_by_supplier.get(src, day), day)
            last_day_by_supplier[src] = max(last_day_by_supplier.get(src, day), day)

    avg_stock_by_supplier: dict[str, float] = defaultdict(float)
    min_stock_by_supplier: dict[str, float] = {}
    stock_count_by_supplier: dict[str, int] = defaultdict(int)
    for row in stock_rows:
        node_id = str(row.get("node_id") or "")
        val = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        avg_stock_by_supplier[node_id] += val
        stock_count_by_supplier[node_id] += 1
        min_stock_by_supplier[node_id] = min(min_stock_by_supplier.get(node_id, val), val)
    for supplier_id, total in list(avg_stock_by_supplier.items()):
        count = max(1, stock_count_by_supplier.get(supplier_id, 0))
        avg_stock_by_supplier[supplier_id] = total / count

    avg_capacity_utilization_by_supplier: dict[str, float] = defaultdict(float)
    max_capacity_utilization_by_supplier: dict[str, float] = defaultdict(float)
    capacity_count_by_supplier: dict[str, int] = defaultdict(int)
    for row in capacity_rows:
        node_id = str(row.get("node_id") or "")
        util = max(0.0, to_float(row.get("utilization")) or 0.0)
        avg_capacity_utilization_by_supplier[node_id] += util
        capacity_count_by_supplier[node_id] += 1
        max_capacity_utilization_by_supplier[node_id] = max(
            max_capacity_utilization_by_supplier.get(node_id, 0.0),
            util,
        )
    for supplier_id, total in list(avg_capacity_utilization_by_supplier.items()):
        count = max(1, capacity_count_by_supplier.get(supplier_id, 0))
        avg_capacity_utilization_by_supplier[supplier_id] = total / count

    shortage_qty_by_item: dict[str, float] = defaultdict(float)
    shortage_events_by_item: dict[str, int] = defaultdict(int)
    for row in constraint_rows:
        if str(row.get("binding_cause") or "") != "input_shortage":
            continue
        item_id = str(row.get("binding_input_item_id") or "")
        if not item_id:
            continue
        shortage_qty_by_item[item_id] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        shortage_events_by_item[item_id] += 1

    total_shipped_all = sum(shipped_qty_by_supplier.values())
    max_active_days = max((len(days) for days in active_days_by_supplier.values()), default=1)

    def normalize_map(values: dict[str, float], log_scale: bool = False) -> dict[str, float]:
        transformed: dict[str, float] = {}
        for key, value in values.items():
            transformed[key] = math.log1p(value) if log_scale else value
        max_value = max(transformed.values(), default=0.0)
        if max_value <= 0:
            return {key: 0.0 for key in values}
        return {key: transformed.get(key, 0.0) / max_value for key in values}

    raw_metrics: dict[str, dict[str, float]] = {}
    for supplier_id in supplier_ids:
        supplied_items = sorted(outgoing_items.get(supplier_id, set()))
        dest_nodes = sorted({str(e.get("to") or "") for e in edges_by_src.get(supplier_id, []) if e.get("to") is not None})
        sole_source_pairs = 0
        shared_source_pairs = 0
        for e in edges_by_src.get(supplier_id, []):
            dst = str(e.get("to") or "")
            for item_id in e.get("items") or []:
                pair_suppliers = suppliers_for_pair.get((dst, str(item_id)), set())
                if len(pair_suppliers) <= 1:
                    sole_source_pairs += 1
                else:
                    shared_source_pairs += 1
        shortage_supported_qty = sum(shortage_qty_by_item.get(item_id, 0.0) for item_id in supplied_items)
        shortage_supported_events = sum(shortage_events_by_item.get(item_id, 0) for item_id in supplied_items)
        std_label, std_short, std_low, std_high, std_fill_impact, std_backlog_impact = select_best_supplier_case_pair(
            by_case_std,
            baseline_std,
            supplier_id,
        )
        struct_label, struct_short, struct_low, struct_high, struct_fill_impact, struct_backlog_impact = (
            select_best_supplier_case_pair(by_case_struct, baseline_struct, supplier_id)
        )
        raw_metrics[supplier_id] = {
            "total_shipped_qty": shipped_qty_by_supplier.get(supplier_id, 0.0),
            "active_days": float(len(active_days_by_supplier.get(supplier_id, set()))),
            "sole_source_pairs": float(sole_source_pairs),
            "shared_source_pairs": float(shared_source_pairs),
            "shortage_supported_qty": shortage_supported_qty,
            "shortage_supported_events": float(shortage_supported_events),
            "standard_fill_impact": std_fill_impact,
            "structural_fill_impact": struct_fill_impact,
            "standard_backlog_impact": std_backlog_impact,
            "structural_backlog_impact": struct_backlog_impact,
        }

    volume_score = normalize_map({k: v["total_shipped_qty"] for k, v in raw_metrics.items()}, log_scale=True)
    shortage_score = normalize_map({k: v["shortage_supported_qty"] for k, v in raw_metrics.items()}, log_scale=True)
    sole_source_score = normalize_map({k: v["sole_source_pairs"] for k, v in raw_metrics.items()})
    standard_system_score = normalize_map(
        {k: v["standard_fill_impact"] * 100.0 + v["standard_backlog_impact"] / 100.0 for k, v in raw_metrics.items()}
    )
    structural_system_score = normalize_map(
        {k: v["structural_fill_impact"] * 100.0 + v["structural_backlog_impact"] / 100.0 for k, v in raw_metrics.items()}
    )

    metrics_by_supplier: dict[str, Any] = {}
    ranking_rows: list[dict[str, Any]] = []
    for supplier_id in supplier_ids:
        supplied_items = sorted(outgoing_items.get(supplier_id, set()))
        dest_nodes = sorted({str(e.get("to") or "") for e in edges_by_src.get(supplier_id, []) if e.get("to") is not None})
        item_labels = ", ".join(item.split(":", 1)[-1] for item in supplied_items[:5])
        if len(supplied_items) > 5:
            item_labels += ", ..."
        total_shipped_qty = shipped_qty_by_supplier.get(supplier_id, 0.0)
        active_days = len(active_days_by_supplier.get(supplier_id, set()))
        served_pairs = sorted(
            {
                pair
                for (src, pair), qty in shipped_qty_by_supplier_pair.items()
                if src == supplier_id and qty > 1e-9
            }
        )
        all_supported_pairs = sorted(
            {
                (str(e.get("to") or ""), str(item_id))
                for e in edges_by_src.get(supplier_id, [])
                for item_id in (e.get("items") or [])
                if e.get("to") is not None
            }
        )
        observed_share_den = sum(total_pair_flow_qty.get(pair, 0.0) for pair in all_supported_pairs)
        observed_share_num = sum(shipped_qty_by_supplier_pair.get((supplier_id, pair), 0.0) for pair in all_supported_pairs)
        observed_sourcing_share = (observed_share_num / observed_share_den) if observed_share_den > 1e-9 else 0.0
        target_share_weighted_num = sum(
            target_share_by_supplier_pair.get((supplier_id, pair), 0.0) * total_pair_flow_qty.get(pair, 0.0)
            for pair in all_supported_pairs
        )
        target_sourcing_share = (target_share_weighted_num / observed_share_den) if observed_share_den > 1e-9 else 0.0
        local_score = (
            0.35 * volume_score.get(supplier_id, 0.0)
            + 0.20 * (active_days / max_active_days if max_active_days > 0 else 0.0)
            + 0.25 * sole_source_score.get(supplier_id, 0.0)
            + 0.20 * shortage_score.get(supplier_id, 0.0)
        )
        system_score = 0.5 * standard_system_score.get(supplier_id, 0.0) + 0.5 * structural_system_score.get(supplier_id, 0.0)
        overall_score = 0.55 * local_score + 0.45 * system_score
        std_label, _std_short, _std_low, _std_high, std_fill_impact, std_backlog_impact = select_best_supplier_case_pair(
            by_case_std,
            baseline_std,
            supplier_id,
        )
        struct_label, _struct_short, _struct_low, _struct_high, struct_fill_impact, struct_backlog_impact = (
            select_best_supplier_case_pair(by_case_struct, baseline_struct, supplier_id)
        )
        row = {
            "supplier_id": supplier_id,
            "supplier_name": node_name.get(supplier_id, supplier_id),
            "items_supplied_count": len(supplied_items),
            "dest_nodes_count": len(dest_nodes),
            "sole_source_pairs": int(raw_metrics[supplier_id]["sole_source_pairs"]),
            "shared_source_pairs": int(raw_metrics[supplier_id]["shared_source_pairs"]),
            "total_shipped_qty": round(total_shipped_qty, 4),
            "active_days": active_days,
            "first_shipment_day": first_day_by_supplier.get(supplier_id, ""),
            "last_shipment_day": last_day_by_supplier.get(supplier_id, ""),
            "initial_stock_total": round(supplier_initial_total.get(supplier_id, 0.0), 4),
            "avg_stock_end_of_day": round(avg_stock_by_supplier.get(supplier_id, 0.0), 4),
            "min_stock_end_of_day": round(min_stock_by_supplier.get(supplier_id, 0.0), 4),
            "avg_capacity_utilization": round(avg_capacity_utilization_by_supplier.get(supplier_id, 0.0), 6),
            "max_capacity_utilization": round(max_capacity_utilization_by_supplier.get(supplier_id, 0.0), 6),
            "observed_sourcing_share": round(observed_sourcing_share, 6),
            "target_sourcing_share": round(target_sourcing_share, 6),
            "avg_procurement_lead_days": round(avg_procurement_lead_days_by_supplier.get(supplier_id, 0.0), 4),
            "capacity_metric_mode": "explicit_capacity" if supplier_has_explicit_capacity.get(supplier_id, False) else "sourcing_share",
            "shortage_supported_qty": round(raw_metrics[supplier_id]["shortage_supported_qty"], 4),
            "shortage_supported_events": int(raw_metrics[supplier_id]["shortage_supported_events"]),
            "standard_best_driver": std_label,
            "standard_fill_impact": round(std_fill_impact, 6),
            "standard_backlog_impact": round(std_backlog_impact, 4),
            "structural_best_driver": struct_label,
            "structural_fill_impact": round(struct_fill_impact, 6),
            "structural_backlog_impact": round(struct_backlog_impact, 4),
            "local_criticality_score": round(local_score, 6),
            "system_criticality_score": round(system_score, 6),
            "overall_criticality_score": round(overall_score, 6),
            "top_items_preview": item_labels,
            "destinations_preview": ", ".join(dest_nodes[:4]) + (", ..." if len(dest_nodes) > 4 else ""),
        }
        ranking_rows.append(row)
        metrics_by_supplier[supplier_id] = {
            "summary_lines": [
                metric_label_value("Rang local/systeme", ""),
                metric_label_value("Flux expedie total", f"{row['total_shipped_qty']:.2f}"),
                metric_label_value("Jours actifs", str(row["active_days"])),
                metric_label_value("Lead time moyen", f"{row['avg_procurement_lead_days']:.1f} j"),
                metric_label_value("Paires mono-source", str(row["sole_source_pairs"])),
                metric_label_value("Exposition shortage", f"{row['shortage_supported_qty']:.2f}"),
                metric_label_value("Driver standard", std_label or "n/a"),
                metric_label_value("Driver structurel", struct_label or "n/a"),
                metric_label_value("Score criticite locale", f"{local_score:.3f}"),
                metric_label_value("Score criticite systeme", f"{system_score:.3f}"),
            ],
            "items": supplied_items,
            "destinations": dest_nodes,
            "scores": {
                "local": round(local_score, 6),
                "system": round(system_score, 6),
                "overall": round(overall_score, 6),
            },
        }
        if supplier_has_explicit_capacity.get(supplier_id, False):
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                4,
                metric_label_value("Utilisation cap. moy.", f"{row['avg_capacity_utilization']:.2%}"),
            )
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                5,
                metric_label_value("Utilisation cap. max", f"{row['max_capacity_utilization']:.2%}"),
            )
        else:
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                4,
                metric_label_value("Part sourcing observee", f"{row['observed_sourcing_share']:.1%}"),
            )
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                5,
                metric_label_value("Part cible MRP", f"{row['target_sourcing_share']:.1%}"),
            )
            nominal_capacity = supplier_nominal_capacity_by_supplier.get(supplier_id, 0.0)
            if nominal_capacity > 0:
                metrics_by_supplier[supplier_id]["summary_lines"].insert(
                    6,
                    metric_label_value("Capacite nominale", f"{nominal_capacity:,.2f}/j".replace(",", " ")),
                )
            basis_label = supplier_capacity_basis_by_supplier.get(supplier_id, "")
            if basis_label:
                scale = supplier_capacity_scale_by_supplier.get(supplier_id, 0.0)
                suffix = f" x{scale:.0f}" if scale > 0 else ""
                metrics_by_supplier[supplier_id]["summary_lines"].insert(
                    7 if nominal_capacity > 0 else 6,
                    metric_label_value("Base capacite", f"{basis_label}{suffix}"),
                )

    ranking_rows.sort(key=lambda row: (-float(row["overall_criticality_score"]), -float(row["total_shipped_qty"]), row["supplier_id"]))
    for rank, row in enumerate(ranking_rows, start=1):
        row["rank"] = rank
        supplier_metrics = metrics_by_supplier.get(str(row["supplier_id"]), {})
        if supplier_metrics:
            supplier_metrics["rank"] = rank
            for entry in supplier_metrics.get("summary_lines", []):
                if entry.get("label") == "Rang local/systeme":
                    entry["value"] = f"{rank}"
                    break

    summary = {
        "supplier_count": len(ranking_rows),
        "top_local_criticality": ranking_rows[:10],
        "methodology": {
            "local_score_weights": {
                "volume": 0.35,
                "active_days": 0.20,
                "sole_source_pairs": 0.25,
                "shortage_exposure": 0.20,
            },
            "overall_score_weights": {
                "local": 0.55,
                "system": 0.45,
            },
        },
    }
    return metrics_by_supplier, ranking_rows, summary


def html_template(title: str, data_json: str, material_table_html: str, material_table_count: int) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .title {{
      font-weight: 700;
      font-size: 14px;
      margin-right: 8px;
    }}
    .meta {{
      font-size: 12px;
      color: #475569;
      margin-right: 14px;
    }}
    .box {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .modeTabs {{
      display: inline-flex;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      overflow: hidden;
      background: #f8fafc;
    }}
    .modeBtn {{
      border: 0;
      background: transparent;
      color: #334155;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 12px;
      cursor: pointer;
    }}
    .modeBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    #typeFilters label {{
      margin-right: 8px;
      font-size: 12px;
      white-space: nowrap;
    }}
    .timelineWindowBox {{
      display: none;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .timelineWindowBox.visible {{
      display: flex;
    }}
    .timelineWindowBox label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: #334155;
      white-space: nowrap;
    }}
    .timelineWindowBox input[type="range"] {{
      width: 108px;
      accent-color: #2563eb;
    }}
    .timelineWindowValue {{
      font-size: 12px;
      font-weight: 700;
      color: #0f172a;
      white-space: nowrap;
    }}
    #chart {{
      width: 100%;
      height: calc(100vh - 64px);
    }}
    #factoryHoverPanel {{
      position: fixed;
      right: 16px;
      top: 88px;
      width: min(760px, calc(100vw - 32px));
      max-height: calc(100vh - 110px);
      background: rgba(255,255,255,0.98);
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
      z-index: 20;
      overflow: auto;
      display: none;
      padding: 10px;
    }}
    #factoryHoverPanel.visible {{
      display: block;
    }}
    .panelHeader {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }}
    #factoryHoverTitle {{
      font-size: 13px;
      font-weight: 700;
      margin: 0;
      color: #0f172a;
      min-width: 0;
    }}
    .panelHeaderRight {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }}
    .panelStatePill {{
      display: none;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      background: #e2e8f0;
      color: #0f172a;
    }}
    .panelStatePill.visible {{
      display: inline-flex;
    }}
    .panelClearBtn {{
      display: none;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 600;
      padding: 5px 8px;
      border-radius: 8px;
      cursor: pointer;
    }}
    .panelClearBtn.visible {{
      display: inline-flex;
    }}
    .factoryHoverGrid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .panelMeta {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #f8fafc;
      padding: 10px 12px;
    }}
    .panelMetaTitle {{
      font-size: 11px;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    .panelMetaGrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px 12px;
    }}
    .panelMetaRow {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      color: #334155;
    }}
    .panelMetaLabel {{
      color: #64748b;
    }}
    .panelMetaValue {{
      font-weight: 600;
      color: #0f172a;
      text-align: right;
      white-space: pre-wrap;
    }}
    .factoryPlotBlock {{
      display: block;
    }}
    .factoryPlotLabel {{
      font-size: 11px;
      color: #334155;
      margin: 0 0 4px 2px;
      font-weight: 600;
    }}
    .panelSubTabs {{
      display: none;
      flex-wrap: wrap;
      gap: 6px;
      margin: 0 0 8px 2px;
    }}
    .panelSubTab {{
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 999px;
      cursor: pointer;
    }}
    .panelSubTab.active {{
      background: #dbeafe;
      border-color: #93c5fd;
      color: #1d4ed8;
    }}
    .factoryPlotHelp {{
      display: none;
      font-size: 11px;
      color: #475569;
      margin: 0 0 8px 2px;
      line-height: 1.45;
    }}
    .tableBtn {{
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #0f172a;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 10px;
      border-radius: 999px;
      cursor: pointer;
    }}
    .tableModal {{
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.45);
      z-index: 30;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .tableModal.visible {{
      display: flex;
    }}
    .tableModalCard {{
      width: min(1280px, calc(100vw - 48px));
      max-height: calc(100vh - 48px);
      overflow: hidden;
      background: #ffffff;
      border-radius: 14px;
      box-shadow: 0 20px 50px rgba(15, 23, 42, 0.28);
      border: 1px solid #cbd5e1;
      display: flex;
      flex-direction: column;
    }}
    .tableModalHeader {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }}
    .tableModalTitle {{
      font-size: 14px;
      font-weight: 700;
      color: #0f172a;
    }}
    .tableModalMeta {{
      font-size: 12px;
      color: #64748b;
      margin-top: 2px;
    }}
    .tableModalBody {{
      overflow: auto;
      padding: 0;
    }}
    .materialTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .materialTable th,
    .materialTable td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    .materialTable thead th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      z-index: 1;
      color: #334155;
    }}
    .materialTable .num {{
      text-align: right;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}
    .scopeBadge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 8px;
      background: #e2e8f0;
      color: #0f172a;
      font-size: 11px;
      font-weight: 700;
    }}
    .scopeBadge.scopeFinal {{
      background: #dbeafe;
      color: #1d4ed8;
    }}
    .scopeBadge.scopeIntermediate {{
      background: #dcfce7;
      color: #166534;
    }}
    .factoryPlot {{
      width: 100%;
      height: clamp(300px, 42.5vh, 425px);
      object-fit: contain;
      object-position: center top;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
    }}
    .factoryPlotOutgoing {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    .factoryPlotThird {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    .factoryPlotFourth {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    .factoryPlotFigure {{
      display: none;
      width: 100%;
      height: clamp(300px, 42.5vh, 425px);
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
    }}
    .factoryPlotFigure.factoryPlotOutgoing {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    .factoryPlotFigure.factoryPlotThird {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    .factoryPlotFigure.factoryPlotFourth {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    .factoryPlotFigure.factoryHtmlPanel {{
      overflow: hidden;
    }}
    .factoryPlotFigure.factoryKpiTreePanel {{
      height: auto;
      min-height: 680px;
      overflow: visible;
      border: 0;
      background: transparent;
    }}
    .kpiTreePanel {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 660px;
      padding: 10px;
      overflow: visible;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
    }}
    .kpiTreeHeader {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 8px;
    }}
    .kpiTreeTitle {{
      font-size: 13px;
      font-weight: 800;
      color: #0f172a;
    }}
    .kpiTreeSubtitle {{
      font-size: 11px;
      color: #64748b;
      margin-top: 2px;
    }}
    .kpiTreeControls {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
      color: #475569;
      font-size: 11px;
      font-weight: 700;
    }}
    .kpiTreeSmoothBtn {{
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 700;
      padding: 5px 9px;
      cursor: pointer;
    }}
    .kpiTreeSmoothBtn.active {{
      background: #dbeafe;
      border-color: #93c5fd;
      color: #1d4ed8;
    }}
    .kpiTreeControlGroup {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-left: 8px;
    }}
    .kpiTreeCards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }}
    .kpiTreeCard {{
      border: 1px solid #dbe4ef;
      border-radius: 12px;
      padding: 9px 10px;
      background: #f8fafc;
      cursor: pointer;
      text-align: left;
    }}
    .kpiTreeCard.active {{
      border-color: #2563eb;
      background: #eff6ff;
      box-shadow: inset 0 0 0 1px #bfdbfe;
    }}
    .kpiTreeCardTitle {{
      font-size: 12px;
      font-weight: 800;
      color: #0f172a;
    }}
    .kpiTreeCardObjective {{
      margin-top: 4px;
      color: #64748b;
      font-size: 10.5px;
      line-height: 1.25;
    }}
    .kpiTreeChart {{
      min-height: 230px;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: #ffffff;
    }}
    .kpiTreeDetail {{
      display: grid;
      grid-template-columns: 0.9fr 1.7fr;
      gap: 10px;
      min-height: 295px;
      overflow: visible;
    }}
    .kpiTreeSummary {{
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      background: #f8fafc;
      padding: 10px;
      overflow: auto;
    }}
    .kpiTreeSummaryRow {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 7px 0;
      border-bottom: 1px solid #e2e8f0;
      font-size: 11px;
    }}
    .kpiTreeSummaryRow:last-child {{
      border-bottom: none;
    }}
    .kpiTreeSummaryLabel {{
      color: #64748b;
      font-weight: 600;
    }}
    .kpiTreeSummaryValue {{
      color: #0f172a;
      font-weight: 800;
      text-align: right;
    }}
    .factoryPlotFigure.factoryFigureStackContainer {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      height: auto;
      border: 0;
      background: transparent;
      overflow: visible;
    }}
    .factoryFigureStackItem {{
      width: 100%;
      height: clamp(220px, 30vh, 300px);
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
    }}
    .factoryHtmlPanelContent {{
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 0;
      background: #ffffff;
    }}
    .panelEmptyState {{
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      padding: 16px;
      color: #475569;
      font-size: 12px;
      text-align: center;
    }}
    .orderLedgerMetaBar {{
      padding: 10px 12px 8px;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
      color: #475569;
      font-size: 11px;
      font-weight: 600;
      flex: 0 0 auto;
    }}
    .orderLedgerTableWrap {{
      flex: 1 1 auto;
      min-height: 0;
      overflow-y: auto;
      overflow-x: auto;
      scrollbar-gutter: stable;
    }}
    .orderLedgerTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
    }}
    .orderLedgerTable th,
    .orderLedgerTable td {{
      padding: 7px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    .orderLedgerTable thead th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #475569;
    }}
    .orderLedgerTable .num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .orderLedgerTextHeader {{
      padding: 16px 16px 8px;
      color: #1e293b;
      font-size: 14px;
      font-weight: 700;
      flex: 0 0 auto;
    }}
    .orderLedgerStatus {{
      padding: 0 16px 8px;
      color: #475569;
      font-size: 12px;
      flex: 0 0 auto;
    }}
    .orderLedgerSectionTitle {{
      padding: 10px 16px 4px;
      color: #475569;
      font-size: 12px;
      font-weight: 600;
      flex: 0 0 auto;
    }}
    .orderLedgerTextWrap {{
      flex: 1 1 auto;
      min-height: 0;
      overflow-y: scroll;
      overflow-x: auto;
      padding: 0 16px 16px;
      scrollbar-gutter: stable both-edges;
    }}
    .orderLedgerLines {{
      margin: 0;
      color: #475569;
      font-size: 11px;
      line-height: 1.55;
      white-space: pre;
      font-family: Consolas, "Courier New", monospace;
    }}
    #factoryHoverNoImage {{
      font-size: 12px;
      color: #475569;
      padding: 8px 2px;
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div class="title">{html.escape(title)}</div>
    <div class="meta" id="stats"></div>
    <div class="box">
      <div class="modeTabs">
        <button id="modeOps" class="modeBtn active" type="button">Simulation</button>
        <button id="modeModel" class="modeBtn" type="button">Modele</button>
        <button id="modeSensitivity" class="modeBtn" type="button">Sensibilite</button>
        <button id="modeStructural" class="modeBtn" type="button">Structurel</button>
      </div>
    </div>
    <div class="box">
      <label><input type="checkbox" id="showEdges" checked> Afficher flux</label>
    </div>
    <div class="box">
      <button id="materialTableBtn" class="tableBtn" type="button">Tableau demande / stock / securite</button>
    </div>
    <div class="box">
      <button id="kpiTreeBtn" class="tableBtn" type="button">Arbres KPI</button>
    </div>
    <div class="box timelineWindowBox" id="timelineWindowBox">
      <label>Debut
        <input type="range" id="yearStart" min="1" max="1" value="1" step="1">
      </label>
      <label>Fin
        <input type="range" id="yearEnd" min="1" max="1" value="1" step="1">
      </label>
      <div class="meta timelineWindowValue" id="yearWindowValue">annee 1 -> 1</div>
    </div>
    <div class="box" id="typeFilters"></div>
  </div>
  <div id="chart"></div>

  <div id="materialTableModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Tableau demande / stock / securite</div>
          <div id="materialTableMeta" class="tableModalMeta">{material_table_count} lignes</div>
        </div>
        <button id="materialTableCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody">
        <table class="materialTable">
          <thead>
            <tr>
              <th>Type</th>
              <th>Item</th>
              <th>Noeud</th>
              <th>Demande / besoin prévu</th>
              <th>Demande moy. / j</th>
              <th>Delai secu. j</th>
              <th>Stock equiv. delai</th>
              <th>Stock initial</th>
              <th>Livré / servi</th>
              <th>Consommé simulé</th>
              <th>Ecart vs besoin</th>
              <th>Unité</th>
              <th>Diagnostic</th>
            </tr>
          </thead>
          <tbody>{material_table_html}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div id="kpiTreeModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Arbres KPI supply</div>
          <div class="tableModalMeta">Vue globale du scénario courant</div>
        </div>
        <button id="kpiTreeCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody">
        <div id="globalKpiTreeFigure"></div>
      </div>
    </div>
  </div>

  <div id="factoryHoverPanel">
    <div class="panelHeader">
      <div id="factoryHoverTitle"></div>
      <div class="panelHeaderRight">
        <div id="factoryHoverState" class="panelStatePill"></div>
        <button id="factoryHoverClearSelection" class="panelClearBtn" type="button">Effacer</button>
      </div>
    </div>
    <div class="factoryHoverGrid">
      <div id="panelMeta" class="panelMeta" style="display:none;">
        <div id="panelMetaTitle" class="panelMetaTitle">Synthese site</div>
        <div id="panelMetaGrid" class="panelMetaGrid"></div>
      </div>
      <div id="incomingBlock" class="factoryPlotBlock">
        <div id="incomingLabel" class="factoryPlotLabel">Stock matieres premieres (entree)</div>
        <img id="factoryIncomingImage" class="factoryPlot" alt="Node incoming chart"/>
        <div id="factoryIncomingFigure" class="factoryPlotFigure"></div>
      </div>
      <div id="outgoingBlock" class="factoryPlotBlock">
        <div id="outgoingLabel" class="factoryPlotLabel">Production produits finis (sortie)</div>
        <img id="factoryOutgoingImage" class="factoryPlot factoryPlotOutgoing" alt="Node outgoing chart"/>
        <div id="factoryOutgoingFigure" class="factoryPlotFigure factoryPlotOutgoing"></div>
      </div>
      <div id="thirdBlock" class="factoryPlotBlock">
        <div id="thirdLabel" class="factoryPlotLabel">Analyse complementaire</div>
        <img id="factoryThirdImage" class="factoryPlot factoryPlotThird" alt="Node additional chart"/>
        <div id="factoryThirdFigure" class="factoryPlotFigure factoryPlotThird"></div>
      </div>
      <div id="fourthBlock" class="factoryPlotBlock">
        <div id="fourthLabel" class="factoryPlotLabel">MRP / risque</div>
        <div id="fourthHelp" class="factoryPlotHelp">Synthese en haut. Puis lis : stock, flux aval. Le bloc pilotage sert a l'analyse : reappro amont, carnet, risque, details MRP.</div>
        <div id="fourthTabs" class="panelSubTabs"></div>
        <img id="factoryFourthImage" class="factoryPlot factoryPlotFourth" alt="Node fourth chart"/>
        <div id="factoryFourthFigure" class="factoryPlotFigure factoryPlotFourth"></div>
      </div>
      <div id="factoryHoverNoImage" style="display:none;">Aucun PNG disponible pour ce noeud.</div>
    </div>
  </div>

  <script>
    const DATA = {data_json};
    const STYLES = DATA.node_type_styles || {{}};
    const FACTORY_HOVER_IMAGES = DATA.factory_hover_images || {{}};
    const SUPPLIER_HOVER_IMAGES = DATA.supplier_hover_images || {{}};
    const DC_HOVER_IMAGES = DATA.distribution_center_hover_images || {{}};
    const CUSTOMER_HOVER_IMAGES = DATA.customer_hover_images || {{}};
    const FACTORY_SENSITIVITY_HOVER_IMAGES = DATA.factory_sensitivity_hover_images || {{}};
    const SUPPLIER_SENSITIVITY_HOVER_IMAGES = DATA.supplier_sensitivity_hover_images || {{}};
    const DC_SENSITIVITY_HOVER_IMAGES = DATA.distribution_center_sensitivity_hover_images || {{}};
    const FACTORY_STRUCTURAL_HOVER_IMAGES = DATA.factory_structural_hover_images || {{}};
    const SUPPLIER_STRUCTURAL_HOVER_IMAGES = DATA.supplier_structural_hover_images || {{}};
    const DC_STRUCTURAL_HOVER_IMAGES = DATA.distribution_center_structural_hover_images || {{}};
    const FACTORY_CURRENT_METRICS = DATA.factory_current_metrics || {{}};
    const SUPPLIER_LOCAL_METRICS = DATA.supplier_local_metrics || {{}};
    const CUSTOMER_CURRENT_METRICS = DATA.customer_current_metrics || {{}};
    const GLOBAL_KPI_TREE = DATA.global_kpi_tree || null;
    const MODEL_PANEL = DATA.model_panel || {{ nodes: {{}}, edges: {{}} }};
    const EDGE_BY_ID = Object.fromEntries((DATA.edges || []).map(e => [e.id, e]));
    const FACTORY_LIKE_NODE_IDS = new Set(DATA.factory_like_node_ids || []);
    const REALISTIC_SENSITIVITY = DATA.realistic_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const THRESHOLD_SENSITIVITY = DATA.threshold_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const nodeById = Object.fromEntries((DATA.nodes || []).map(n => [n.id, n]));
    const defaultPalette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"];
    let currentFactoryHoverId = null;
    let currentFactoryHoverType = null;
    let currentHoveredPanelId = null;
    let currentHoveredPanelType = null;
    let selectedPanelNodeId = null;
    let selectedPanelNodeType = null;
    let currentPanelMode = "ops";
    let hoverHandlersBound = false;
    const panelBundleSelection = {{}};
    let selectedYearStart = 1;
    let selectedYearEnd = 1;

    function visitTimelineFigures(payload, visitor) {{
      if (!payload || typeof payload !== "object") return;
      Object.values(payload).forEach((panel) => {{
        if (!panel || typeof panel !== "object") return;
        Object.values(panel).forEach((asset) => {{
          if (!asset || typeof asset !== "object") return;
          const figure = asset.figure || null;
          if (!figure || typeof figure !== "object") return;
          visitor(figure);
          if (figure.tabs && typeof figure.tabs === "object") {{
            Object.values(figure.tabs).forEach((tabFigure) => {{
              if (tabFigure && typeof tabFigure === "object") visitor(tabFigure);
            }});
          }}
        }});
      }});
    }}

    function extractFigureMaxDay(figure) {{
      if (!figure || typeof figure !== "object") return 0;
      let maxDay = 0;
      if (figure.kind === "line_multi") {{
        (figure.series || []).forEach((series) => {{
          (series.days || []).forEach((day) => {{
            const value = Number(day);
            if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
          }});
        }});
      }} else if (figure.kind === "dual_panel_multi") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel || panel.kind !== "line_multi") return;
          (panel.series || []).forEach((series) => {{
            (series.days || []).forEach((day) => {{
              const value = Number(day);
              if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
            }});
          }});
        }});
      }} else if (figure.kind === "dual_panel") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel) return;
          (panel.x || []).forEach((day) => {{
            const value = Number(day);
            if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
          }});
        }});
      }}
      return maxDay;
    }}

    function computeTimelineMaxYear() {{
      let maxDay = 0;
      [FACTORY_HOVER_IMAGES, SUPPLIER_HOVER_IMAGES, DC_HOVER_IMAGES, CUSTOMER_HOVER_IMAGES].forEach((payload) => {{
        visitTimelineFigures(payload, (figure) => {{
          maxDay = Math.max(maxDay, extractFigureMaxDay(figure));
        }});
      }});
      return Math.max(1, Math.ceil((maxDay + 1) / 365));
    }}

    const timelineMaxYear = computeTimelineMaxYear();
    selectedYearEnd = timelineMaxYear;

    function syncYearInputs() {{
      const yearStartInput = document.getElementById("yearStart");
      const yearEndInput = document.getElementById("yearEnd");
      if (!yearStartInput || !yearEndInput) return;
      yearStartInput.max = String(timelineMaxYear);
      yearEndInput.max = String(timelineMaxYear);
      selectedYearStart = Math.min(Math.max(1, selectedYearStart), timelineMaxYear);
      selectedYearEnd = Math.min(Math.max(1, selectedYearEnd), timelineMaxYear);
      if (selectedYearStart > selectedYearEnd) {{
        selectedYearEnd = selectedYearStart;
      }}
      yearStartInput.value = String(selectedYearStart);
      yearEndInput.value = String(selectedYearEnd);
    }}

    function updateTimelineWindowLabel() {{
      const valueEl = document.getElementById("yearWindowValue");
      if (!valueEl) return;
      valueEl.textContent = `annee ${{selectedYearStart}} -> ${{selectedYearEnd}}`;
    }}

    function applyTimelineWindowUi() {{
      const box = document.getElementById("timelineWindowBox");
      if (!box) return;
      const visible = currentPanelMode === "ops" && timelineMaxYear > 1;
      box.classList.toggle("visible", visible);
    }}

    function currentTimelineDayRange() {{
      return {{
        startDay: (selectedYearStart - 1) * 365,
        endDay: (selectedYearEnd * 365) - 1,
      }};
    }}

    function filterSeriesByTimeline(days, values) {{
      if (currentPanelMode !== "ops" || timelineMaxYear <= 1) {{
        return {{
          days: (days || []).slice(),
          values: (values || []).slice(),
        }};
      }}
      const {{ startDay, endDay }} = currentTimelineDayRange();
      const filteredDays = [];
      const filteredValues = [];
      const inputDays = days || [];
      const inputValues = values || [];
      for (let idx = 0; idx < inputDays.length; idx += 1) {{
        const day = Number(inputDays[idx]);
        if (!Number.isFinite(day)) continue;
        if (day < startDay || day > endDay) continue;
        filteredDays.push(day);
        filteredValues.push(inputValues[idx]);
      }}
      return {{ days: filteredDays, values: filteredValues }};
    }}

    function filterXYByTimeline(x, y) {{
      if (currentPanelMode !== "ops" || timelineMaxYear <= 1) {{
        return {{
          x: (x || []).slice(),
          y: (y || []).slice(),
        }};
      }}
      const {{ startDay, endDay }} = currentTimelineDayRange();
      const filteredX = [];
      const filteredY = [];
      const inputX = x || [];
      const inputY = y || [];
      for (let idx = 0; idx < inputX.length; idx += 1) {{
        const value = Number(inputX[idx]);
        if (!Number.isFinite(value)) {{
          filteredX.push(inputX[idx]);
          filteredY.push(inputY[idx]);
          continue;
        }}
        if (value < startDay || value > endDay) continue;
        filteredX.push(inputX[idx]);
        filteredY.push(inputY[idx]);
      }}
      return {{ x: filteredX, y: filteredY }};
    }}

    function fmtPanelQty(value, digits = 1) {{
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return "n/a";
      return numeric.toLocaleString("fr-FR", {{
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }});
    }}

    function buildFactoryWindowSummaryLines(metrics) {{
      if (!metrics || !Array.isArray(metrics.daily_metrics) || !metrics.daily_metrics.length) {{
        return (metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : [];
      }}
      const range = currentTimelineDayRange();
      const rows = (currentPanelMode === "ops")
        ? metrics.daily_metrics.filter((row) => Number(row.day) >= range.startDay && Number(row.day) <= range.endDay)
        : metrics.daily_metrics.slice();
      if (!rows.length) {{
        return (metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : [];
      }}
      const totalDesired = rows.reduce((sum, row) => sum + (Number(row.desired_qty) || 0), 0);
      const totalActual = rows.reduce((sum, row) => sum + (Number(row.actual_qty) || 0), 0);
      const totalShortfall = rows.reduce((sum, row) => sum + (Number(row.shortfall_qty) || 0), 0);
      const peakShortfall = rows.reduce((peak, row) => Math.max(peak, Number(row.shortfall_qty) || 0), 0);
      const capacityDays = rows.reduce((count, row) => count + ((Number(row.capacity_binding) || 0) > 0 ? 1 : 0), 0);
      const leadDays = Number(metrics.avg_inbound_lead_days);
      const windowLabel = timelineMaxYear > 1
        ? `annee ${{selectedYearStart}} -> ${{selectedYearEnd}}`
        : `jours ${{rows[0].day}} -> ${{rows[rows.length - 1].day}}`;
      return [
        {{ label: "Fenetre analysee", value: windowLabel }},
        {{ label: "Production demandee cumulee", value: fmtPanelQty(totalDesired, 1) }},
        {{ label: "Production reelle cumulee", value: fmtPanelQty(totalActual, 1) }},
        {{ label: "Manque de production cumule", value: fmtPanelQty(totalShortfall, 1) }},
        {{ label: "Pic de manque de production", value: fmtPanelQty(peakShortfall, 1) }},
        {{ label: "Jours contraints capacite", value: String(capacityDays) }},
        {{ label: "Lead time entrant moyen", value: Number.isFinite(leadDays) ? `${{leadDays.toFixed(1)}} j` : "n/a" }},
      ];
    }}

    function styleForType(nodeType, idx) {{
      const s = STYLES[nodeType] || {{}};
      return {{
        name: s.name || nodeType,
        color: s.color || defaultPalette[idx % defaultPalette.length],
        symbol: s.symbol || "circle",
      }};
    }}

    function initFilters() {{
      const container = document.getElementById("typeFilters");
      container.innerHTML = "<strong style='font-size:12px;'>Types:</strong>";
      (DATA.node_types || []).forEach((t, idx) => {{
        const style = styleForType(t, idx);
        const lbl = document.createElement("label");
        lbl.innerHTML = `<input class="typeChk" type="checkbox" value="${{t}}" checked> ${{style.name}}`;
        container.appendChild(lbl);
      }});
    }}

    function selectedTypes() {{
      return new Set(Array.from(document.querySelectorAll(".typeChk"))
        .filter(x => x.checked)
        .map(x => x.value));
    }}

    function nodeText(n) {{
      const loc = n.location_ID ? n.location_ID : "n/a";
      const country = n.country ? n.country : "n/a";
      const customerMetrics = CUSTOMER_CURRENT_METRICS[n.id] || null;
      const extra = [];
      if (customerMetrics && Array.isArray(customerMetrics.summary_lines)) {{
        customerMetrics.summary_lines.slice(0, 3).forEach((entry) => {{
          extra.push(`${{entry.label}}: ${{entry.value}}`);
        }});
      }}
      const extraHtml = extra.length ? `<br>${{extra.join("<br>")}}` : "";
      return `${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}<br>Country: ${{country}}<br>Location: ${{loc}}${{extraHtml}}`;
    }}

    function edgeLeadColor(e) {{
      const m = e.edge_metrics || {{}};
      const lead = Number.isFinite(m.avg_lead_days) ? m.avg_lead_days : (Number.isFinite(e.planned_lead_days) ? e.planned_lead_days : 1);
      if (lead <= 14) return "#2ca02c";
      if (lead <= 30) return "#ffb000";
      if (lead <= 60) return "#ff7f0e";
      return "#d62728";
    }}

    function edgeText(e) {{
      const itemCount = Array.isArray(e.items) ? e.items.length : 0;
      const itemPreview = itemCount ? e.items.join(", ") : "n/a";
      const m = e.edge_metrics || null;
      if (!m) {{
        return `Edge: ${{e.id}}<br>${{e.from}} -> ${{e.to}}<br>Items (${{itemCount}}): ${{itemPreview}}`;
      }}
      const qtyBehavior = m.qty_constant_flag ? "quantite tres constante" : `${{m.distinct_shipped_qty}} niveaux de quantite`;
      return [
        `Edge: ${{e.id}}`,
        `${{e.from}} -> ${{e.to}}`,
        `Items (${{itemCount}}): ${{itemPreview}}`,
        `Lead time planifie: ${{e.planned_lead_days ?? 'n/a'}} j`,
        `Lead time observe moyen: ${{m.avg_lead_days}} j`,
        `Lead observe min-max: ${{m.min_lead_days}} - ${{m.max_lead_days}} j`,
        `Lead observe p50 / p90: ${{m.lead_p50_days}} / ${{m.lead_p90_days}} j`,
        `Variabilite lead (ecart-type): ${{m.lead_std_days}} j`,
        `Safety time destination: ${{m.safety_time_days}} j`,
        `Lead effectif moyen: ${{m.effective_lead_days}} j`,
        `Lignes d'expedition observees: ${{m.shipment_rows}}`,
        `Profil quantite: ${{qtyBehavior}}`,
      ].join("<br>");
    }}

    function toRad(deg) {{
      return deg * Math.PI / 180.0;
    }}

    function toDeg(rad) {{
      return rad * 180.0 / Math.PI;
    }}

    function edgeHitboxPoints(src, dst) {{
      const steps = 28;
      const startFrac = 0.18;
      const endFrac = 0.82;
      const lat1 = toRad(src.lat);
      const lon1 = toRad(src.lon);
      const lat2 = toRad(dst.lat);
      const lon2 = toRad(dst.lon);
      const p1 = [
        Math.cos(lat1) * Math.cos(lon1),
        Math.cos(lat1) * Math.sin(lon1),
        Math.sin(lat1),
      ];
      const p2 = [
        Math.cos(lat2) * Math.cos(lon2),
        Math.cos(lat2) * Math.sin(lon2),
        Math.sin(lat2),
      ];
      const dot = Math.min(1, Math.max(-1, p1[0] * p2[0] + p1[1] * p2[1] + p1[2] * p2[2]));
      const omega = Math.acos(dot);
      const pts = [];
      for (let i = 0; i < steps; i += 1) {{
        const t = startFrac + ((endFrac - startFrac) * i / (steps - 1));
        let x, y, z;
        if (Math.abs(omega) < 1e-9) {{
          x = p1[0] + t * (p2[0] - p1[0]);
          y = p1[1] + t * (p2[1] - p1[1]);
          z = p1[2] + t * (p2[2] - p1[2]);
        }} else {{
          const sinOmega = Math.sin(omega);
          const a = Math.sin((1 - t) * omega) / sinOmega;
          const b = Math.sin(t * omega) / sinOmega;
          x = a * p1[0] + b * p2[0];
          y = a * p1[1] + b * p2[1];
          z = a * p1[2] + b * p2[2];
        }}
        const norm = Math.sqrt(x * x + y * y + z * z) || 1;
        x /= norm;
        y /= norm;
        z /= norm;
        pts.push({{
          lon: toDeg(Math.atan2(y, x)),
          lat: toDeg(Math.atan2(z, Math.sqrt(x * x + y * y))),
        }});
      }}
      return pts;
    }}

    function clamp(value, min, max) {{
      return Math.min(Math.max(value, min), max);
    }}

    function computeGeoView(visibleNodes) {{
      if (!visibleNodes.length) {{
        return {{ scale: 1 }};
      }}
      const lats = visibleNodes.map(n => n.lat);
      const lons = visibleNodes.map(n => n.lon);

      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLon = Math.min(...lons);
      let maxLon = Math.max(...lons);

      const latSpan = Math.max(maxLat - minLat, 0.5);
      const lonSpan = Math.max(maxLon - minLon, 0.5);
      const padLat = Math.max(latSpan * 0.25, 2.0);
      const padLon = Math.max(lonSpan * 0.25, 2.0);

      minLat = clamp(minLat - padLat, -85, 85);
      maxLat = clamp(maxLat + padLat, -85, 85);
      minLon = clamp(minLon - padLon, -180, 180);
      maxLon = clamp(maxLon + padLon, -180, 180);

      const spanLat = Math.max(maxLat - minLat, 1);
      const spanLon = Math.max(maxLon - minLon, 1);
      const effectiveSpan = Math.max(spanLat, spanLon * 0.55);
      const scale = clamp(120 / effectiveSpan, 1.1, 25);

      return {{
        scale: scale,
        center: {{
          lat: (minLat + maxLat) / 2,
          lon: (minLon + maxLon) / 2,
        }}
      }};
    }}

    function buildTraces() {{
      const traces = [];
      const visibleTypes = selectedTypes();
      const showEdges = document.getElementById("showEdges").checked;

      const visibleNodes = (DATA.nodes || []).filter(n =>
        visibleTypes.has(n.type) &&
        Number.isFinite(n.lat) &&
        Number.isFinite(n.lon)
      );
      const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

      (DATA.node_types || []).forEach((nodeType, idx) => {{
        if (!visibleTypes.has(nodeType)) return;
        const style = styleForType(nodeType, idx);
        const subset = visibleNodes.filter(n => n.type === nodeType);
        if (!subset.length) return;
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: style.name,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          text: subset.map(nodeText),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 9,
            color: style.color,
            symbol: style.symbol,
            line: {{ width: 0.6, color: "#111827" }}
          }}
        }});
      }});

      let drawnEdges = 0;
      if (showEdges) {{
        for (const e of (DATA.edges || [])) {{
          const src = nodeById[e.from];
          const dst = nodeById[e.to];
          if (!src || !dst) continue;
          if (!visibleNodeIds.has(src.id) || !visibleNodeIds.has(dst.id)) continue;
          if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) continue;
          if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) continue;
          const itemCount = Array.isArray(e.items) ? e.items.length : 0;
          const width = 1 + Math.min(itemCount, 4);
          traces.push({{
            type: "scattergeo",
            mode: "lines",
            showlegend: false,
            lon: [src.lon, dst.lon],
            lat: [src.lat, dst.lat],
            line: {{ width, color: edgeLeadColor(e) }},
            opacity: 0.65,
            hoverinfo: "skip",
          }});
          const hitboxPts = edgeHitboxPoints(src, dst);
          traces.push({{
            type: "scattergeo",
            mode: "markers",
            showlegend: false,
            lon: hitboxPts.map(p => p.lon),
            lat: hitboxPts.map(p => p.lat),
            marker: {{
              size: Math.max(width + 5, 10),
              color: "#111827",
              opacity: 0.001,
            }},
            customdata: hitboxPts.map(() => [e.id, "edge", `${{e.from}} -> ${{e.to}}`]),
            hoverinfo: "none",
          }});
          drawnEdges += 1;
        }}
      }}

      document.getElementById("stats").textContent =
        `${{visibleNodes.length}} nodes visibles / ${{(DATA.nodes || []).length}} | ` +
        `${{showEdges ? drawnEdges : 0}} flux affiches / ${{(DATA.edges || []).length}}`;
      return {{ traces, visibleNodes }};
    }}

    function hideFactoryPanel() {{
      function purgePlotlyNode(node) {{
        if (!window.Plotly || !node) return;
        const plots = node.matches && node.matches(".js-plotly-plot")
          ? [node, ...Array.from(node.querySelectorAll(".js-plotly-plot"))]
          : Array.from(node.querySelectorAll(".js-plotly-plot"));
        plots.forEach((plotNode) => {{
          try {{ Plotly.purge(plotNode); }} catch (e) {{}}
        }});
      }}
      const panel = document.getElementById("factoryHoverPanel");
      const incomingBlock = document.getElementById("incomingBlock");
      const outgoingBlock = document.getElementById("outgoingBlock");
      const thirdBlock = document.getElementById("thirdBlock");
      const metaBlock = document.getElementById("panelMeta");
      const metaGrid = document.getElementById("panelMetaGrid");
      const incomingLabel = document.getElementById("incomingLabel");
      const outgoingLabel = document.getElementById("outgoingLabel");
      const thirdLabel = document.getElementById("thirdLabel");
      const incomingImg = document.getElementById("factoryIncomingImage");
      const outgoingImg = document.getElementById("factoryOutgoingImage");
      const thirdImg = document.getElementById("factoryThirdImage");
      const incomingFigure = document.getElementById("factoryIncomingFigure");
      const outgoingFigure = document.getElementById("factoryOutgoingFigure");
      const thirdFigure = document.getElementById("factoryThirdFigure");
      const fourthHelp = document.getElementById("fourthHelp");
      const noImg = document.getElementById("factoryHoverNoImage");
      const statePill = document.getElementById("factoryHoverState");
      const clearBtn = document.getElementById("factoryHoverClearSelection");
      incomingBlock.style.display = "block";
      outgoingBlock.style.display = "block";
      thirdBlock.style.display = "none";
      incomingLabel.textContent = "Stock matieres premieres (entree)";
      outgoingLabel.textContent = "Production produits finis (sortie)";
      thirdLabel.textContent = "Analyse complementaire";
      incomingImg.removeAttribute("src");
      incomingImg.style.display = "none";
      outgoingImg.removeAttribute("src");
      outgoingImg.style.display = "none";
      thirdImg.removeAttribute("src");
      thirdImg.style.display = "none";
      purgePlotlyNode(incomingFigure);
      purgePlotlyNode(outgoingFigure);
      purgePlotlyNode(thirdFigure);
      incomingFigure.innerHTML = "";
      outgoingFigure.innerHTML = "";
      thirdFigure.innerHTML = "";
      incomingFigure.style.display = "none";
      outgoingFigure.style.display = "none";
      thirdFigure.style.display = "none";
      incomingFigure.classList.remove("factoryFigureStackContainer");
      outgoingFigure.classList.remove("factoryFigureStackContainer");
      thirdFigure.classList.remove("factoryFigureStackContainer");
      fourthHelp.style.display = "block";
      metaGrid.innerHTML = "";
      metaBlock.style.display = "none";
      noImg.style.display = "none";
      statePill.textContent = "";
      statePill.classList.remove("visible");
      clearBtn.classList.remove("visible");
      panel.classList.remove("visible");
      currentFactoryHoverId = null;
      currentFactoryHoverType = null;
    }}

    function isFactoryLikeNode(nodeId, nodeType) {{
      return nodeType === "factory" || (nodeType === "supplier_dc" && FACTORY_LIKE_NODE_IDS.has(nodeId));
    }}

    function isPanelSelectableType(nodeType) {{
      return nodeType === "factory" || nodeType === "supplier_dc" || nodeType === "distribution_center" || nodeType === "customer" || nodeType === "edge";
    }}

    function currentPanelTarget() {{
      if (selectedPanelNodeId && selectedPanelNodeType) {{
        return {{
          nodeId: selectedPanelNodeId,
          nodeType: selectedPanelNodeType,
          state: "Selection",
        }};
      }}
      if (currentHoveredPanelId && currentHoveredPanelType) {{
        return {{
          nodeId: currentHoveredPanelId,
          nodeType: currentHoveredPanelType,
          state: "Survol",
        }};
      }}
      return null;
    }}

    function selectablePointFromEvent(ev) {{
      const points = ev && Array.isArray(ev.points) ? ev.points : [];
      for (const point of points) {{
        if (!Array.isArray(point.customdata)) continue;
        const nodeType = point.customdata[1];
        if (!isPanelSelectableType(nodeType)) continue;
        return point;
      }}
      return null;
    }}

    function refreshFactoryPanel() {{
      const target = currentPanelTarget();
      if (!target) {{
        hideFactoryPanel();
        return;
      }}
      showFactoryPanel(target.nodeId, target.nodeType, target.state);
    }}

    function clearPanelSelection() {{
      selectedPanelNodeId = null;
      selectedPanelNodeType = null;
      refreshFactoryPanel();
    }}

    function syncPanelStateWithVisibleNodes(visibleNodes) {{
      const visibleNodeIds = new Set((visibleNodes || []).map(n => n.id));
      if (selectedPanelNodeId && !visibleNodeIds.has(selectedPanelNodeId)) {{
        selectedPanelNodeId = null;
        selectedPanelNodeType = null;
      }}
      if (currentHoveredPanelId && !visibleNodeIds.has(currentHoveredPanelId)) {{
        currentHoveredPanelId = null;
        currentHoveredPanelType = null;
      }}
    }}

    function renderPanelMeta(nodeId, nodeType) {{
      const metaBlock = document.getElementById("panelMeta");
      const metaTitle = document.getElementById("panelMetaTitle");
      const metaGrid = document.getElementById("panelMetaGrid");
      metaGrid.innerHTML = "";
      if (currentPanelMode === "model") {{
        const details = nodeType === "edge"
          ? (((MODEL_PANEL.edges || {{}})[nodeId]) || null)
          : (((MODEL_PANEL.nodes || {{}})[nodeId]) || null);
        const lines = details && Array.isArray(details.summary_lines) ? details.summary_lines : [];
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = (details && details.title) || "Modele";
        lines.forEach((entry) => {{
          const row = document.createElement("div");
          row.className = "panelMetaRow";
          const label = document.createElement("div");
          label.className = "panelMetaLabel";
          label.textContent = entry.label || "";
          const value = document.createElement("div");
          value.className = "panelMetaValue";
          value.textContent = entry.value || "";
          if (!entry.value) {{
            row.style.gridColumn = "1 / span 2";
            label.style.fontWeight = "700";
            label.style.color = "#0f172a";
            value.style.display = "none";
          }}
          row.appendChild(label);
          row.appendChild(value);
          metaGrid.appendChild(row);
        }});
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "sensitivity") {{
        const thresholdNodeMetrics = (THRESHOLD_SENSITIVITY.nodes || {{}})[nodeId] || null;
        const thresholdMetrics = thresholdNodeMetrics || THRESHOLD_SENSITIVITY.global || null;
        const realisticNodeMetrics = (REALISTIC_SENSITIVITY.nodes || {{}})[nodeId] || null;
        const realisticMetrics = realisticNodeMetrics || REALISTIC_SENSITIVITY.global || null;
        const thresholdLines = (thresholdMetrics && Array.isArray(thresholdMetrics.summary_lines)) ? thresholdMetrics.summary_lines : [];
        const realisticLines = (realisticMetrics && Array.isArray(realisticMetrics.summary_lines)) ? realisticMetrics.summary_lines : [];
        if (!thresholdLines.length && !realisticLines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent =
          (thresholdMetrics && thresholdMetrics.title) ||
          (realisticMetrics && realisticMetrics.title) ||
          "Sensibilite";
        const entries = [];
        if (thresholdLines.length) {{
          entries.push({{ label: "Analyse seuil", value: "" }});
          thresholdLines.forEach((entry) => entries.push(entry));
        }}
        if (realisticLines.length) {{
          entries.push({{ label: "Analyse locale", value: "" }});
          realisticLines.forEach((entry) => entries.push(entry));
        }}
        entries.forEach((entry) => {{
          const row = document.createElement("div");
          row.className = "panelMetaRow";
          const label = document.createElement("div");
          label.className = "panelMetaLabel";
          label.textContent = entry.label || "";
          const value = document.createElement("div");
          value.className = "panelMetaValue";
          value.textContent = entry.value || "";
          if (!entry.value) {{
            row.style.gridColumn = "1 / span 2";
            label.style.fontWeight = "700";
            label.style.color = "#0f172a";
            value.style.display = "none";
          }}
          row.appendChild(label);
          row.appendChild(value);
          metaGrid.appendChild(row);
        }});
        metaBlock.style.display = "block";
        return true;
      }}
      const metrics = isFactoryLikeNode(nodeId, nodeType)
        ? (FACTORY_CURRENT_METRICS[nodeId] || null)
        : (nodeType === "supplier_dc"
            ? (SUPPLIER_LOCAL_METRICS[nodeId] || null)
            : (nodeType === "customer"
                ? (CUSTOMER_CURRENT_METRICS[nodeId] || null)
                : (nodeType === "edge" ? (EDGE_BY_ID[nodeId] || null) : null)));
      if (nodeType === "edge") {{
        const edge = EDGE_BY_ID[nodeId] || null;
        const edgeMetrics = edge && edge.edge_metrics ? edge.edge_metrics : null;
        if (!edge || !edgeMetrics) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = "Flux et delais observes";
        const edgeSummary = [
          {{ label: "Flux", value: `${{edge.from}} -> ${{edge.to}}` }},
          {{ label: "Items", value: Array.isArray(edge.items) ? edge.items.join(", ") : "n/a" }},
          {{ label: "Lead planifie", value: `${{edge.planned_lead_days ?? 'n/a'}} j` }},
          {{ label: "Lead moyen observe", value: `${{edgeMetrics.avg_lead_days}} j` }},
          {{ label: "Lead min-max", value: `${{edgeMetrics.min_lead_days}} - ${{edgeMetrics.max_lead_days}} j` }},
          {{ label: "Lead p50 / p90", value: `${{edgeMetrics.lead_p50_days}} / ${{edgeMetrics.lead_p90_days}} j` }},
          {{ label: "Ecart-type lead", value: `${{edgeMetrics.lead_std_days}} j` }},
          {{ label: "Safety time destination", value: `${{edgeMetrics.safety_time_days}} j` }},
          {{ label: "Lead effectif moyen", value: `${{edgeMetrics.effective_lead_days}} j` }},
          {{ label: "Lignes d'expedition", value: `${{edgeMetrics.shipment_rows}}` }},
          {{ label: "Quantites distinctes", value: `${{edgeMetrics.distinct_shipped_qty}}` }},
        ];
        edgeSummary.forEach((entry) => {{
          const row = document.createElement("div");
          row.className = "panelMetaRow";
          const label = document.createElement("div");
          label.className = "panelMetaLabel";
          label.textContent = entry.label || "";
          const value = document.createElement("div");
          value.className = "panelMetaValue";
          value.textContent = entry.value || "";
          row.appendChild(label);
          row.appendChild(value);
          metaGrid.appendChild(row);
        }});
        metaBlock.style.display = "block";
        return true;
      }}
      const summaryLines = (isFactoryLikeNode(nodeId, nodeType) && currentPanelMode === "ops")
        ? buildFactoryWindowSummaryLines(metrics)
        : ((metrics && Array.isArray(metrics.summary_lines)) ? metrics.summary_lines : []);
      if (!summaryLines.length) {{
        metaBlock.style.display = "none";
        return false;
      }}
      metaTitle.textContent = nodeType === "customer"
        ? "Demande client courante"
        : (isFactoryLikeNode(nodeId, nodeType) ? "Performance industrielle courante" : "Criticite locale fournisseur");
      summaryLines.forEach((entry) => {{
        const row = document.createElement("div");
        row.className = "panelMetaRow";
        const label = document.createElement("div");
        label.className = "panelMetaLabel";
        label.textContent = entry.label || "";
        const value = document.createElement("div");
        value.className = "panelMetaValue";
        value.textContent = entry.value || "";
        row.appendChild(label);
        row.appendChild(value);
        metaGrid.appendChild(row);
      }});
      metaBlock.style.display = "block";
      return true;
    }}

    function panelLabels(nodeId, nodeType) {{
      if (currentPanelMode === "model") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "Modele du flux",
            outgoing: "Caracteristiques du flux",
            third: "KPI du flux",
            fourth: "MRP / risque"
          }};
        }}
        return {{
          incoming: "Modele du noeud",
          outgoing: "Caracteristiques du noeud",
          third: "KPI du noeud",
          fourth: "MRP / risque"
        }};
      }}
      if (currentPanelMode === "sensitivity") {{
        if (nodeType === "supplier_dc") {{
          return {{
            incoming: "Courbe fournisseur - flux et stock moyen",
            outgoing: "Courbe fournisseur - utilisation et stock final"
          }};
        }}
        if (nodeType === "factory") {{
          return {{
            incoming: "Usine - capacite vs fill rate et stock intrants",
            outgoing: "Usine - capacite vs backlog et delta production"
          }};
        }}
        if (nodeType === "distribution_center") {{
          return {{
            incoming: "DC - driver critique vs service et backlog",
            outgoing: "DC - driver critique vs cout et inventaire"
          }};
        }}
        if (nodeType === "customer") {{
          return {{
            incoming: "Client - synthese sensibilite",
            outgoing: "Client - demande courante"
          }};
        }}
        return {{
          incoming: "Courbe de seuil - service et backlog",
          outgoing: "Courbe de seuil - cout et inventaire"
        }};
      }}
      if (currentPanelMode === "structural") {{
        return {{
          incoming: "Structurel - KPI + courbe delta vs baseline",
          outgoing: "Structurel - KPI + courbe delta vs baseline"
        }};
      }}
      if (nodeType === "supplier_dc") {{
        return {{
          incoming: "Stock fournisseur",
          outgoing: "Expeditions vs receptions",
          third: "Capacite",
          fourth: "Pilotage MRP"
        }};
      }}
      if (nodeId === "SDC-1450" && isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          incoming: "Stock intrants / PFI",
          outgoing: "Expeditions PFI",
          third: "",
          fourth: "Pilotage MRP"
        }};
      }}
      if (isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          incoming: "Stock matieres",
          outgoing: "Flux aval",
          third: "",
          fourth: "Pilotage MRP"
        }};
      }}
      if (nodeType === "distribution_center") {{
        return {{
          incoming: "Stock DC",
          outgoing: "Receptions DC",
          third: "Expeditions DC",
          fourth: "Pilotage MRP"
        }};
      }}
      if (nodeType === "customer") {{
        return {{
          incoming: "Demande client",
          outgoing: "Servi et backlog",
          third: "Receptions client",
          fourth: "Pilotage MRP"
        }};
      }}
      if (nodeType === "edge") {{
        return {{
          incoming: "Flux - delais observes",
          outgoing: "Flux - synthese",
          third: "Flux - distribution",
          fourth: "Flux - MRP / carnet"
        }};
      }}
      return {{
        incoming: "Stock matieres",
        outgoing: "Flux aval",
        third: "Capacite",
        fourth: "MRP / risque"
      }};
    }}

    function panelImages(nodeId, nodeType) {{
      if (currentPanelMode === "model") {{
        return null;
      }}
      if (currentPanelMode === "sensitivity") {{
        if (nodeType === "factory") return FACTORY_SENSITIVITY_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "supplier_dc") return SUPPLIER_SENSITIVITY_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "distribution_center") return DC_SENSITIVITY_HOVER_IMAGES[nodeId] || null;
        return null;
      }}
      if (currentPanelMode === "structural") {{
        if (nodeType === "factory") return FACTORY_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "supplier_dc") return SUPPLIER_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "distribution_center") return DC_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        return null;
      }}
      const modelDetails = nodeType === "edge"
        ? (((MODEL_PANEL.edges || {{}})[nodeId]) || null)
        : (((MODEL_PANEL.nodes || {{}})[nodeId]) || null);
      const modelBundleEntries = modelDetails ? [
        {{ label: "Carnet", asset: modelDetails.third || null }},
        {{ label: "Flux MRP", asset: modelDetails.outgoing || null }},
        {{ label: "Exceptions / risque", asset: modelDetails.incoming || null }},
      ] : [];
      if (nodeType !== "supplier_dc" && nodeType !== "customer") {{
        modelBundleEntries.unshift({{ label: "Reappro amont", asset: modelDetails ? (modelDetails.fourth || null) : null }});
      }}
      const modelBundle = modelDetails ? {{
        bundle: modelBundleEntries.filter(entry => !!entry.asset)
      }} : null;
      const modelFourth = modelBundle && modelBundle.bundle.length ? modelBundle : null;
      if (nodeType === "supplier_dc") {{
        return {{ ...(SUPPLIER_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (isFactoryLikeNode(nodeId, nodeType)) {{
        return {{ ...(FACTORY_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (nodeType === "distribution_center") {{
        return {{ ...(DC_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (nodeType === "customer") {{
        return {{ ...(CUSTOMER_HOVER_IMAGES[nodeId] || {{}}), fourth: modelFourth }};
      }}
      if (nodeType === "edge") {{
        if (!modelDetails) return null;
        return {{
          incoming: modelDetails.incoming || null,
          outgoing: modelDetails.outgoing || null,
          third: modelDetails.third || null,
          fourth: null,
        }};
      }}
      return modelFourth ? {{ fourth: modelFourth }} : null;
    }}

    function applyModeUi() {{
      document.getElementById("modeOps").classList.toggle("active", currentPanelMode === "ops");
      document.getElementById("modeModel").classList.toggle("active", currentPanelMode === "model");
      document.getElementById("modeSensitivity").classList.toggle("active", currentPanelMode === "sensitivity");
      document.getElementById("modeStructural").classList.toggle("active", currentPanelMode === "structural");
      applyTimelineWindowUi();
    }}

    function setPanelMode(mode) {{
      currentPanelMode = mode;
      applyModeUi();
      refreshFactoryPanel();
    }}

    function showFactoryPanel(nodeId, nodeType, panelState) {{
      const images = panelImages(nodeId, nodeType) || {{}};

      const panel = document.getElementById("factoryHoverPanel");
      const title = document.getElementById("factoryHoverTitle");
      const incomingBlock = document.getElementById("incomingBlock");
      const outgoingBlock = document.getElementById("outgoingBlock");
      const thirdBlock = document.getElementById("thirdBlock");
      const fourthBlock = document.getElementById("fourthBlock");
      const incomingLabel = document.getElementById("incomingLabel");
      const outgoingLabel = document.getElementById("outgoingLabel");
      const thirdLabel = document.getElementById("thirdLabel");
      const fourthLabel = document.getElementById("fourthLabel");
      const fourthHelp = document.getElementById("fourthHelp");
      const incomingImg = document.getElementById("factoryIncomingImage");
      const outgoingImg = document.getElementById("factoryOutgoingImage");
      const thirdImg = document.getElementById("factoryThirdImage");
      const fourthImg = document.getElementById("factoryFourthImage");
      const incomingFigure = document.getElementById("factoryIncomingFigure");
      const outgoingFigure = document.getElementById("factoryOutgoingFigure");
      const thirdFigure = document.getElementById("factoryThirdFigure");
      const fourthFigure = document.getElementById("factoryFourthFigure");
      const fourthTabs = document.getElementById("fourthTabs");
      const noImg = document.getElementById("factoryHoverNoImage");
      const statePill = document.getElementById("factoryHoverState");
      const clearBtn = document.getElementById("factoryHoverClearSelection");
      const nodeInfo = nodeType === "edge" ? (EDGE_BY_ID[nodeId] || {{}}) : (nodeById[nodeId] || {{}});
      const displayNodeId = nodeId === "SDC-1450" ? "D-1450" : nodeId;
      const nodeName = nodeId === "SDC-1450"
        ? "D-1450"
        : (nodeType === "edge"
        ? `${{nodeInfo.from || "n/a"}} -> ${{nodeInfo.to || "n/a"}}`
        : (nodeInfo.name || nodeId));
      const nodeTitle = nodeId === "SDC-1450" ? "Internal PFI Site" :
        (nodeType === "supplier_dc" ? "Supplier" :
        (isFactoryLikeNode(nodeId, nodeType) ? "Industrial Site" :
        (nodeType === "distribution_center" ? "Distribution Center" : (nodeType === "factory" ? "Factory" : (nodeType === "customer" ? "Customer" : "Edge")))));
      const modeTitle = currentPanelMode === "sensitivity" ? "Sensibilite" :
        (currentPanelMode === "structural" ? "Structurel" : (currentPanelMode === "model" ? "Modele" : "Simulation"));
      title.textContent = `${{nodeTitle}}: ${{nodeName}} (${{displayNodeId}}) | ${{modeTitle}}`;
      if (panelState) {{
        statePill.textContent = panelState;
        statePill.classList.add("visible");
      }} else {{
        statePill.textContent = "";
        statePill.classList.remove("visible");
      }}
      clearBtn.classList.toggle("visible", !!selectedPanelNodeId);

      const labels = panelLabels(nodeId, nodeType);
      incomingLabel.textContent = labels.incoming;
      outgoingLabel.textContent = labels.outgoing;
      thirdLabel.textContent = labels.third || "Analyse complementaire";
      fourthLabel.textContent = labels.fourth || "Analyse MRP";
      const hasMeta = renderPanelMeta(nodeId, nodeType);

      const incomingImageInfo = images.incoming || null;
      const outgoingImageInfo = images.outgoing || null;
      const thirdImageInfo = images.third || null;
      const fourthImageInfo = images.fourth || null;
      fourthHelp.style.display = fourthImageInfo ? "block" : "none";

      incomingBlock.style.display = incomingImageInfo ? "block" : "none";
      outgoingBlock.style.display = outgoingImageInfo ? "block" : "none";
      thirdBlock.style.display = thirdImageInfo ? "block" : "none";
      fourthBlock.style.display = fourthImageInfo ? "block" : "none";

      function buildPlotlyFigure(figure) {{
        if (!figure || !figure.kind) return null;
        if (figure.kind === "line_multi") {{
          const palette = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569"];
          return {{
            data: (figure.series || []).map((series, idx) => {{
              const filtered = filterSeriesByTimeline(series.days || [], series.values || []);
              return {{
                type: "scatter",
                mode: "lines",
                name: series.label || `Serie ${{idx + 1}}`,
                x: filtered.days,
                y: filtered.values,
                line: {{
                  width: Number(series.width || 2.2),
                  color: series.color || palette[idx % palette.length],
                  dash: series.dash || "solid",
                  shape: figure.step_like ? "hv" : "linear",
                }},
              }};
            }}),
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: {{ l: 56, r: 18, t: 44, b: 42 }},
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              xaxis: {{ title: figure.x_label || "Jour", gridcolor: "#e2e8f0" }},
              yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
              legend: {{ orientation: "h", y: -0.22 }},
              annotations: figure.note ? [{{
                text: figure.note,
                xref: "paper",
                yref: "paper",
                x: 0,
                y: 1.12,
                xanchor: "left",
                yanchor: "bottom",
                showarrow: false,
                font: {{ size: 10, color: "#475569" }},
                align: "left",
              }}] : [],
            }},
          }};
        }}
        if (figure.kind === "bar") {{
          return {{
            data: [{{
              type: "bar",
              x: figure.labels || [],
              y: figure.values || [],
              marker: {{ color: "#2563eb" }},
            }}],
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: {{ l: 56, r: 18, t: 44, b: 72 }},
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              xaxis: {{ tickangle: -20 }},
              yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
            }},
          }};
        }}
        if (figure.kind === "dual_panel") {{
          const top = figure.top || {{}};
          const bottom = figure.bottom || {{}};
          const topFiltered = top.kind === "line" ? filterXYByTimeline(top.x || [], top.y || []) : {{ x: top.x || [], y: top.y || [] }};
          const bottomFiltered = bottom.kind === "line" ? filterXYByTimeline(bottom.x || [], bottom.y || []) : {{ x: bottom.x || [], y: bottom.y || [] }};
          const traces = [];
          traces.push(top.kind === "bar"
            ? {{
                type: "bar",
                x: top.x || [],
                y: top.y || [],
                marker: {{ color: "#dc2626" }},
                xaxis: "x",
                yaxis: "y",
                name: top.title || "Panel 1",
              }}
            : {{
                type: "scatter",
                mode: "lines",
                x: topFiltered.x,
                y: topFiltered.y,
                line: {{ width: 2.2, color: "#dc2626" }},
                xaxis: "x",
                yaxis: "y",
                name: top.title || "Panel 1",
              }});
          traces.push(bottom.kind === "line"
            ? {{
                type: "scatter",
                mode: "lines",
                x: bottomFiltered.x,
                y: bottomFiltered.y,
                line: {{ width: 2.2, color: "#2563eb" }},
                xaxis: "x2",
                yaxis: "y2",
                name: bottom.title || "Panel 2",
              }}
            : {{
                type: "bar",
                x: bottom.x || [],
                y: bottom.y || [],
                marker: {{ color: "#2563eb" }},
                xaxis: "x2",
                yaxis: "y2",
                name: bottom.title || "Panel 2",
              }});
          return {{
            data: traces,
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: {{ l: 60, r: 20, t: 48, b: 46 }},
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              grid: {{ rows: 2, columns: 1, pattern: "independent", roworder: "top to bottom" }},
              xaxis: {{ title: top.x_label || "", gridcolor: "#e2e8f0" }},
              yaxis: {{ title: top.y_label || "", gridcolor: "#e2e8f0" }},
              xaxis2: {{ title: bottom.x_label || "", tickangle: -20, gridcolor: "#e2e8f0" }},
              yaxis2: {{ title: bottom.y_label || "", gridcolor: "#e2e8f0" }},
              annotations: [
                {{
                  text: top.title || "",
                  x: 0,
                  xref: "paper",
                  y: 1.0,
                  yref: "paper",
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 11, color: "#0f172a" }},
                }},
                {{
                  text: bottom.title || "",
                  x: 0,
                  xref: "paper",
                  y: 0.44,
                  yref: "paper",
                  xanchor: "left",
                  yanchor: "bottom",
                  showarrow: false,
                  font: {{ size: 11, color: "#0f172a" }},
                }},
              ],
              showlegend: false,
            }},
          }};
        }}
        return null;
      }}

      function renderKpiTreeAsset(asset, figureEl) {{
        if (!asset || asset.kind !== "kpi_tree" || !window.Plotly) return false;
        const groups = asset.groups || [];
        const main = asset.main || {{}};
        if (!groups.length || !(main.series || []).length) return false;
        figureEl.style.display = "block";
        figureEl.classList.add("factoryKpiTreePanel");
        figureEl.innerHTML = `
          <div class="kpiTreePanel">
            <div class="kpiTreeHeader">
              <div>
                <div class="kpiTreeTitle">${{asset.title || "Arborescence KPI"}}</div>
                <div class="kpiTreeSubtitle">${{asset.subtitle || "Clique un KPI principal pour afficher les KPI secondaires."}}</div>
              </div>
            </div>
            <div class="kpiTreeCards"></div>
            <div class="kpiTreeChart kpiTreeMainChart"></div>
            <div class="kpiTreeDetail">
              <div class="kpiTreeSummary"></div>
              <div class="kpiTreeChart kpiTreeSecondaryChart"></div>
            </div>
          </div>
        `;
        const cardsEl = figureEl.querySelector(".kpiTreeCards");
        const mainChartEl = figureEl.querySelector(".kpiTreeMainChart");
        const summaryEl = figureEl.querySelector(".kpiTreeSummary");
        const secondaryChartEl = figureEl.querySelector(".kpiTreeSecondaryChart");
        let selectedId = groups[0].id;

        function groupById(groupId) {{
          return groups.find(group => group.id === groupId) || groups[0];
        }}
        function renderCards() {{
          cardsEl.innerHTML = "";
          groups.forEach(group => {{
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = group.id === selectedId ? "kpiTreeCard active" : "kpiTreeCard";
            btn.innerHTML = `
              <div class="kpiTreeCardTitle">${{group.label || group.id}}</div>
              <div class="kpiTreeCardObjective">${{group.objective || ""}}</div>
            `;
            btn.onclick = () => {{
              selectedId = group.id;
              renderCards();
              renderSecondary();
            }};
            cardsEl.appendChild(btn);
          }});
        }}
        function renderMain() {{
          const palette = ["#0f766e", "#2563eb", "#d97706"];
          const traces = (main.series || []).map((series, idx) => {{
            const filtered = filterSeriesByTimeline(main.days || [], series.values || []);
            return {{
              type: "scatter",
              mode: "lines",
              name: series.label || series.id,
              x: filtered.days,
              y: filtered.values,
              customdata: (filtered.days || []).map(() => series.id),
              line: {{ width: 2.6, color: series.color || palette[idx % palette.length] }},
              hovertemplate: `${{series.label || series.id}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
            }};
          }});
          Plotly.react(mainChartEl, traces, {{
            title: {{ text: "KPI principaux - vue management", font: {{ size: 12 }} }},
            margin: {{ l: 54, r: 18, t: 42, b: 42 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: "Jour", gridcolor: "#e2e8f0" }},
            yaxis: {{ title: main.y_label || "Score / indice", gridcolor: "#e2e8f0" }},
            legend: {{ orientation: "h", y: -0.22 }},
          }}, {{ displayModeBar: false, responsive: true }});
          mainChartEl.on("plotly_click", (ev) => {{
            const point = ev && ev.points && ev.points[0];
            const groupId = point && point.customdata;
            if (groupId) {{
              selectedId = groupId;
              renderCards();
              renderSecondary();
            }}
          }});
        }}
        function renderSecondary() {{
          const group = groupById(selectedId);
          summaryEl.innerHTML = "";
          (group.summary || []).forEach(row => {{
            const div = document.createElement("div");
            div.className = "kpiTreeSummaryRow";
            div.innerHTML = `<span class="kpiTreeSummaryLabel">${{row.label || ""}}</span><span class="kpiTreeSummaryValue">${{row.value || ""}}</span>`;
            summaryEl.appendChild(div);
          }});
          const traces = (group.secondary || []).map(series => {{
            const filtered = filterSeriesByTimeline(series.days || [], series.values || []);
            return {{
              type: "scatter",
              mode: "lines",
              name: series.label || "KPI secondaire",
              x: filtered.days,
              y: filtered.values,
              line: {{ width: 2.2, color: series.color || "#2563eb" }},
            }};
          }});
          Plotly.react(secondaryChartEl, traces, {{
            title: {{ text: `KPI secondaires - ${{group.label || selectedId}}`, font: {{ size: 12 }} }},
            margin: {{ l: 58, r: 18, t: 42, b: 42 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: {{ title: "Jour", gridcolor: "#e2e8f0" }},
            yaxis: {{ title: group.secondary_y_label || "Valeur", gridcolor: "#e2e8f0" }},
            legend: {{ orientation: "h", y: -0.24 }},
          }}, {{ displayModeBar: false, responsive: true }});
        }}
        renderCards();
        renderMain();
        renderSecondary();
        return true;
      }}

      function renderAsset(asset, imgEl, figureEl, tabsEl, bundleKey) {{
        function purgePlotlyNode(node) {{
          if (!window.Plotly || !node) return;
          const plots = node.matches && node.matches(".js-plotly-plot")
            ? [node, ...Array.from(node.querySelectorAll(".js-plotly-plot"))]
            : Array.from(node.querySelectorAll(".js-plotly-plot"));
          plots.forEach((plotNode) => {{
            try {{ Plotly.purge(plotNode); }} catch (e) {{}}
          }});
        }}

        imgEl.removeAttribute("src");
        imgEl.style.display = "none";
        figureEl.innerHTML = "";
        figureEl.style.display = "none";
        figureEl.classList.remove("factoryHtmlPanel");
        figureEl.classList.remove("factoryKpiTreePanel");
        figureEl.classList.remove("factoryFigureStackContainer");
        if (tabsEl) {{
          tabsEl.innerHTML = "";
          tabsEl.style.display = "none";
        }}
        purgePlotlyNode(figureEl);
        if (!asset) return false;
        if (Array.isArray(asset.bundle) && asset.bundle.length) {{
          const entries = asset.bundle.filter(entry => entry && entry.asset);
          if (!entries.length) return false;
          const selectionKey = bundleKey || "bundle";
          const hasSavedSelection = Object.prototype.hasOwnProperty.call(panelBundleSelection, selectionKey);
          let selectedIdx = panelBundleSelection[selectionKey] ?? 0;
          if (!hasSavedSelection && selectionKey.includes(":supplier_dc:")) {{
            const carnetIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "carnet");
            if (carnetIdx >= 0) {{
              selectedIdx = carnetIdx;
              panelBundleSelection[selectionKey] = carnetIdx;
            }}
          }}
          if (selectedIdx >= entries.length) selectedIdx = 0;
          if (tabsEl && entries.length > 1) {{
            tabsEl.style.display = "flex";
            entries.forEach((entry, idx) => {{
              const btn = document.createElement("button");
              btn.type = "button";
              btn.className = idx === selectedIdx ? "panelSubTab active" : "panelSubTab";
              btn.textContent = entry.label || `Vue ${{idx + 1}}`;
              btn.onclick = () => {{
                panelBundleSelection[selectionKey] = idx;
                renderAsset(asset, imgEl, figureEl, tabsEl, selectionKey);
              }};
              tabsEl.appendChild(btn);
            }});
          }}
          return renderAsset(entries[selectedIdx].asset, imgEl, figureEl, null, selectionKey);
        }}
        if (asset.data_b64) {{
          imgEl.src = `data:${{asset.mime || "image/png"}};base64,${{asset.data_b64}}`;
          imgEl.style.display = "block";
          return true;
        }}
        if (asset.html) {{
          figureEl.style.display = "block";
          figureEl.classList.add("factoryHtmlPanel");
          figureEl.innerHTML = asset.html;
          return true;
        }}
        if (asset.kind === "kpi_tree") {{
          return renderKpiTreeAsset(asset, figureEl);
        }}
        if (asset.figure && asset.figure.kind === "dual_panel_multi" && window.Plotly) {{
          const panels = [asset.figure.top || null, asset.figure.bottom || null].filter(Boolean);
          if (!panels.length) return false;
          figureEl.style.display = "flex";
          figureEl.classList.add("factoryFigureStackContainer");
          panels.forEach((panelFigure) => {{
            const child = document.createElement("div");
            child.className = "factoryFigureStackItem";
            figureEl.appendChild(child);
            const plotlyFigure = buildPlotlyFigure(panelFigure);
            if (plotlyFigure) {{
              Plotly.react(child, plotlyFigure.data, plotlyFigure.layout, {{ displayModeBar: false, responsive: true }});
            }}
          }});
          return true;
        }}
        const plotlyFigure = buildPlotlyFigure(asset.figure || null);
        if (plotlyFigure && window.Plotly) {{
          figureEl.style.display = "block";
          Plotly.react(figureEl, plotlyFigure.data, plotlyFigure.layout, {{ displayModeBar: false, responsive: true }});
          return true;
        }}
        return false;
      }}

      let visibleCount = 0;
      if (renderAsset(incomingImageInfo, incomingImg, incomingFigure, null, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:incoming`)) visibleCount += 1;
      if (renderAsset(outgoingImageInfo, outgoingImg, outgoingFigure, null, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:outgoing`)) visibleCount += 1;
      if (renderAsset(thirdImageInfo, thirdImg, thirdFigure, null, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:third`)) visibleCount += 1;
      if (renderAsset(fourthImageInfo, fourthImg, fourthFigure, fourthTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:fourth`)) visibleCount += 1;

      if (!visibleCount && !hasMeta) {{
        hideFactoryPanel();
        return;
      }}
      if (!visibleCount) {{
        if (
          currentPanelMode === "sensitivity" &&
          nodeType === "supplier_dc" &&
          Array.isArray(REALISTIC_SENSITIVITY.selected_suppliers) &&
          !REALISTIC_SENSITIVITY.selected_suppliers.includes(nodeId)
        ) {{
          noImg.textContent = "Pas de courbe locale: fournisseur hors perimetre top actifs de l'etude.";
        }} else {{
          noImg.textContent = "Aucun PNG disponible pour ce noeud.";
        }}
      }}
      noImg.style.display = visibleCount ? "none" : "block";
      currentFactoryHoverId = nodeId;
      currentFactoryHoverType = nodeType;
      panel.classList.add("visible");
    }}

    function bindHoverHandlers() {{
      if (hoverHandlersBound) return;
      const gd = document.getElementById("chart");
      gd.on("plotly_hover", (ev) => {{
        const p = selectablePointFromEvent(ev);
        if (!p) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (!isPanelSelectableType(nodeType)) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
          return;
        }}
        currentHoveredPanelId = nodeId;
        currentHoveredPanelType = nodeType;
        refreshFactoryPanel();
      }});
      gd.on("plotly_unhover", () => {{
        currentHoveredPanelId = null;
        currentHoveredPanelType = null;
        refreshFactoryPanel();
      }});
      gd.on("plotly_click", (ev) => {{
        const p = selectablePointFromEvent(ev);
        if (!p) {{
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (!isPanelSelectableType(nodeType)) {{
          return;
        }}
        if (selectedPanelNodeId === nodeId && selectedPanelNodeType === nodeType) {{
          selectedPanelNodeId = null;
          selectedPanelNodeType = null;
        }} else {{
          selectedPanelNodeId = nodeId;
          selectedPanelNodeType = nodeType;
        }}
        refreshFactoryPanel();
      }});
      hoverHandlersBound = true;
    }}

    function draw() {{
      const {{ traces, visibleNodes }} = buildTraces();
      syncPanelStateWithVisibleNodes(visibleNodes);
      const geoView = computeGeoView(visibleNodes);
      const geoLayout = {{
        scope: "world",
        projection: {{type: "natural earth", scale: geoView.scale || 1}},
        showland: true,
        landcolor: "#eef2f7",
        showcountries: true,
        countrycolor: "#cbd5e1",
        showocean: true,
        oceancolor: "#f8fbff"
      }};
      if (geoView.center) {{
        geoLayout.center = geoView.center;
      }}

      const layout = {{
        margin: {{l: 0, r: 0, t: 0, b: 0}},
        showlegend: true,
        legend: {{orientation: "h"}},
        geo: geoLayout
      }};

      Plotly.newPlot("chart", traces, layout, {{displayModeBar: true, responsive: true}});
      bindHoverHandlers();
      refreshFactoryPanel();
    }}

    function renderGlobalKpiTree() {{
      const figureEl = document.getElementById("globalKpiTreeFigure");
      if (!figureEl) return false;
      figureEl.innerHTML = "";
      if (!GLOBAL_KPI_TREE || GLOBAL_KPI_TREE.kind !== "kpi_tree" || !window.Plotly) {{
        figureEl.innerHTML = '<div class="panelEmptyState">Aucun arbre KPI global disponible pour ce run.</div>';
        return false;
      }}
      const asset = GLOBAL_KPI_TREE;
      const groups = asset.groups || [];
      const main = asset.main || {{}};
      if (!groups.length || !(main.series || []).length) {{
        figureEl.innerHTML = '<div class="panelEmptyState">Arbre KPI incomplet.</div>';
        return false;
      }}
      figureEl.className = "factoryPlotFigure factoryKpiTreePanel";
      figureEl.style.display = "block";
      figureEl.innerHTML = `
        <div class="kpiTreePanel">
          <div class="kpiTreeHeader">
            <div>
              <div class="kpiTreeTitle">${{asset.title || "Arborescence KPI"}}</div>
              <div class="kpiTreeSubtitle">${{asset.subtitle || "Clique un KPI principal pour afficher les KPI secondaires."}}</div>
            </div>
            <div class="kpiTreeControls">
              <span class="kpiTreeControlGroup">
                <span>Lissage</span>
                <button type="button" class="kpiTreeSmoothBtn" data-smooth="none">Sans</button>
                <button type="button" class="kpiTreeSmoothBtn active" data-smooth="week">7 j</button>
                <button type="button" class="kpiTreeSmoothBtn" data-smooth="month">30 j</button>
              </span>
              <span class="kpiTreeControlGroup">
                <span>Demarrage</span>
                <button type="button" class="kpiTreeSmoothBtn active" data-start="all">Tout</button>
                <button type="button" class="kpiTreeSmoothBtn" data-start="no_j0">Sans J0</button>
                <button type="button" class="kpiTreeSmoothBtn" data-start="no_30">Sans 30 j</button>
              </span>
            </div>
          </div>
          <div class="kpiTreeCards"></div>
          <div class="kpiTreeChart kpiTreeMainChart"></div>
          <div class="kpiTreeDetail">
            <div class="kpiTreeSummary"></div>
            <div class="kpiTreeChart kpiTreeSecondaryChart"></div>
          </div>
        </div>
      `;
      const cardsEl = figureEl.querySelector(".kpiTreeCards");
      const mainChartEl = figureEl.querySelector(".kpiTreeMainChart");
      const summaryEl = figureEl.querySelector(".kpiTreeSummary");
      const secondaryChartEl = figureEl.querySelector(".kpiTreeSecondaryChart");
      const smoothButtons = Array.from(figureEl.querySelectorAll(".kpiTreeSmoothBtn"));
      const startButtons = Array.from(figureEl.querySelectorAll("[data-start]"));
      let selectedId = groups[0].id;
      let smoothingMode = "week";
      let startupMode = "all";

      function groupById(groupId) {{
        return groups.find(group => group.id === groupId) || groups[0];
      }}
      function smoothingWindow() {{
        if (smoothingMode === "week") return 7;
        if (smoothingMode === "month") return 30;
        return 1;
      }}
      function smoothingSuffix() {{
        if (smoothingMode === "week") return " - moy. 7 j";
        if (smoothingMode === "month") return " - moy. 30 j";
        return "";
      }}
      function startupCutoffDay() {{
        if (startupMode === "no_j0") return 1;
        if (startupMode === "no_30") return 30;
        return null;
      }}
      function startupSuffix() {{
        if (startupMode === "no_j0") return " - hors J0";
        if (startupMode === "no_30") return " - hors 30 premiers jours";
        return "";
      }}
      function smoothValues(values) {{
        const windowSize = smoothingWindow();
        const numeric = (values || []).map(value => {{
          const num = Number(value);
          return Number.isFinite(num) ? num : 0;
        }});
        if (windowSize <= 1) return numeric;
        return numeric.map((_, idx) => {{
          const start = Math.max(0, idx - windowSize + 1);
          const slice = numeric.slice(start, idx + 1);
          const sum = slice.reduce((acc, value) => acc + value, 0);
          return slice.length ? sum / slice.length : 0;
        }});
      }}
      function filterStartupAndTimeline(days, values) {{
        const cutoff = startupCutoffDay();
        const filteredDays = [];
        const filteredValues = [];
        (days || []).forEach((day, idx) => {{
          const dayNum = Number(day);
          if (cutoff !== null && Number.isFinite(dayNum) && dayNum < cutoff) return;
          filteredDays.push(day);
          filteredValues.push((values || [])[idx] ?? 0);
        }});
        return filterSeriesByTimeline(filteredDays, filteredValues);
      }}
      function bindSmoothingControls() {{
        smoothButtons.filter(btn => btn.dataset.smooth).forEach(btn => {{
          btn.onclick = () => {{
            smoothingMode = btn.dataset.smooth || "none";
            smoothButtons.filter(other => other.dataset.smooth).forEach(other => other.classList.toggle("active", other === btn));
            renderMain();
            renderSecondary();
          }};
        }});
        startButtons.forEach(btn => {{
          btn.onclick = () => {{
            startupMode = btn.dataset.start || "all";
            startButtons.forEach(other => other.classList.toggle("active", other === btn));
            renderMain();
            renderSecondary();
          }};
        }});
      }}
      function renderCards() {{
        cardsEl.innerHTML = "";
        groups.forEach(group => {{
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = group.id === selectedId ? "kpiTreeCard active" : "kpiTreeCard";
          btn.innerHTML = `
            <div class="kpiTreeCardTitle">${{group.label || group.id}}</div>
            <div class="kpiTreeCardObjective">${{group.objective || ""}}</div>
          `;
          btn.onclick = () => {{
            selectedId = group.id;
            renderCards();
            renderSecondary();
          }};
          cardsEl.appendChild(btn);
        }});
      }}
      function renderMain() {{
        const palette = ["#0f766e", "#2563eb", "#d97706"];
        const traces = (main.series || []).map((series, idx) => {{
          const values = smoothValues(series.values || []);
          const filtered = filterStartupAndTimeline(main.days || [], values);
          const label = `${{series.label || series.id}}${{smoothingSuffix()}}${{startupSuffix()}}`;
          return {{
            type: "scatter",
            mode: "lines",
            name: label,
            x: filtered.days,
            y: filtered.values,
            customdata: (filtered.days || []).map(() => series.id),
            line: {{ width: 2.6, color: series.color || palette[idx % palette.length] }},
            hovertemplate: `${{label}}<br>Jour=%{{x}}<br>Valeur=%{{y:.2f}}<extra></extra>`,
          }};
        }});
        Plotly.react(mainChartEl, traces, {{
          title: {{ text: "KPI principaux - vue management", font: {{ size: 12 }} }},
          margin: {{ l: 54, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: {{ title: "Jour", gridcolor: "#e2e8f0" }},
          yaxis: {{ title: main.y_label || "Score / indice", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.22 }},
        }}, {{ displayModeBar: false, responsive: true }});
        mainChartEl.on("plotly_click", (ev) => {{
          const point = ev && ev.points && ev.points[0];
          const groupId = point && point.customdata;
          if (groupId) {{
            selectedId = groupId;
            renderCards();
            renderSecondary();
          }}
        }});
      }}
      function renderSecondary() {{
        const group = groupById(selectedId);
        summaryEl.innerHTML = "";
        (group.summary || []).forEach(row => {{
          const div = document.createElement("div");
          div.className = "kpiTreeSummaryRow";
          div.innerHTML = `<span class="kpiTreeSummaryLabel">${{row.label || ""}}</span><span class="kpiTreeSummaryValue">${{row.value || ""}}</span>`;
          summaryEl.appendChild(div);
        }});
        const traces = (group.secondary || []).map(series => {{
          const values = smoothValues(series.values || []);
          const filtered = filterStartupAndTimeline(series.days || [], values);
          const label = `${{series.label || "KPI secondaire"}}${{smoothingSuffix()}}${{startupSuffix()}}`;
          return {{
            type: "scatter",
            mode: "lines",
            name: label,
            x: filtered.days,
            y: filtered.values,
            line: {{ width: 2.2, color: series.color || "#2563eb" }},
          }};
        }});
        Plotly.react(secondaryChartEl, traces, {{
          title: {{ text: `KPI secondaires - ${{group.label || selectedId}}`, font: {{ size: 12 }} }},
          margin: {{ l: 58, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: {{ title: "Jour", gridcolor: "#e2e8f0" }},
          yaxis: {{ title: group.secondary_y_label || "Valeur", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.24 }},
        }}, {{ displayModeBar: false, responsive: true }});
      }}
      bindSmoothingControls();
      renderCards();
      renderMain();
      renderSecondary();
      return true;
    }}

    function init() {{
      initFilters();
      syncYearInputs();
      updateTimelineWindowLabel();
      applyModeUi();
      const materialTableModal = document.getElementById("materialTableModal");
      document.getElementById("materialTableBtn").addEventListener("click", () => {{
        materialTableModal.classList.add("visible");
      }});
      document.getElementById("materialTableCloseBtn").addEventListener("click", () => {{
        materialTableModal.classList.remove("visible");
      }});
      materialTableModal.addEventListener("click", (ev) => {{
        if (ev.target === materialTableModal) {{
          materialTableModal.classList.remove("visible");
        }}
      }});
      const kpiTreeModal = document.getElementById("kpiTreeModal");
      document.getElementById("kpiTreeBtn").addEventListener("click", () => {{
        kpiTreeModal.classList.add("visible");
        renderGlobalKpiTree();
      }});
      document.getElementById("kpiTreeCloseBtn").addEventListener("click", () => {{
        kpiTreeModal.classList.remove("visible");
      }});
      kpiTreeModal.addEventListener("click", (ev) => {{
        if (ev.target === kpiTreeModal) {{
          kpiTreeModal.classList.remove("visible");
        }}
      }});
      document.getElementById("showEdges").addEventListener("change", draw);
      document.getElementById("modeOps").addEventListener("click", () => setPanelMode("ops"));
      document.getElementById("modeModel").addEventListener("click", () => setPanelMode("model"));
      document.getElementById("modeSensitivity").addEventListener("click", () => setPanelMode("sensitivity"));
      document.getElementById("modeStructural").addEventListener("click", () => setPanelMode("structural"));
      document.getElementById("yearStart").addEventListener("input", (ev) => {{
        selectedYearStart = Number(ev.target.value || 1);
        if (selectedYearStart > selectedYearEnd) {{
          selectedYearEnd = selectedYearStart;
        }}
        syncYearInputs();
        updateTimelineWindowLabel();
        refreshFactoryPanel();
      }});
      document.getElementById("yearEnd").addEventListener("input", (ev) => {{
        selectedYearEnd = Number(ev.target.value || 1);
        if (selectedYearEnd < selectedYearStart) {{
          selectedYearStart = selectedYearEnd;
        }}
        syncYearInputs();
        updateTimelineWindowLabel();
        refreshFactoryPanel();
      }});
      document.getElementById("factoryHoverClearSelection").addEventListener("click", clearPanelSelection);
      for (const chk of document.querySelectorAll(".typeChk")) {{
        chk.addEventListener("change", draw);
      }}
      draw();
    }}

    window.addEventListener("load", init);
  </script>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    sim_input = Path(args.sim_input_stocks_csv)
    sim_output = Path(args.sim_output_products_csv)
    demand_service_csv = Path(args.demand_service_csv)
    sim_input_png_dir = Path(args.sim_input_stocks_png_dir)
    sim_output_png_dir = Path(args.sim_output_products_png_dir)
    sensitivity_cases_csv = Path(args.sensitivity_cases_csv)
    supplier_shipments_csv = Path(args.supplier_shipments_csv)
    supplier_stocks_csv = Path(args.supplier_stocks_csv)
    supplier_capacity_csv = Path(args.supplier_capacity_csv)
    input_arrivals_csv = Path(args.input_arrivals_csv)
    production_constraint_csv = Path(args.production_constraint_csv)
    daily_kpi_csv = Path(args.daily_kpi_csv) if args.daily_kpi_csv else sim_input.parent / "first_simulation_daily.csv"
    structural_sensitivity_cases_csv = Path(args.structural_sensitivity_cases_csv)
    supplier_local_criticality_csv = Path(args.supplier_local_criticality_csv)
    supplier_local_criticality_json = Path(args.supplier_local_criticality_json)
    realistic_sensitivity_summary_json = (
        Path(args.realistic_sensitivity_summary_json)
        if args.realistic_sensitivity_summary_json
        else Path("__missing_realistic_sensitivity_summary__.json")
    )
    realistic_local_elasticities_csv = (
        Path(args.realistic_local_elasticities_csv)
        if args.realistic_local_elasticities_csv
        else Path("__missing_realistic_local_elasticities__.csv")
    )
    realistic_stress_impacts_csv = (
        Path(args.realistic_stress_impacts_csv)
        if args.realistic_stress_impacts_csv
        else Path("__missing_realistic_stress_impacts__.csv")
    )
    threshold_sensitivity_summary_json = (
        Path(args.threshold_sensitivity_summary_json)
        if args.threshold_sensitivity_summary_json
        else Path("__missing_threshold_sensitivity_summary__.json")
    )
    threshold_parameter_summary_csv = (
        Path(args.threshold_parameter_summary_csv)
        if args.threshold_parameter_summary_csv
        else Path("__missing_threshold_parameter_summary__.csv")
    )
    threshold_sweep_cases_csv = (
        Path(args.threshold_sweep_cases_csv)
        if args.threshold_sweep_cases_csv
        else Path("__missing_threshold_sweep_cases__.csv")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    supplier_local_criticality_csv.parent.mkdir(parents=True, exist_ok=True)
    supplier_local_criticality_json.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        payload = compact_graph_payload(raw)
        payload["factory_like_node_ids"] = sorted(factory_like_node_ids(raw))
        payload["factory_hover_series"] = build_factory_hover_series(raw, sim_input, sim_output)
        payload["factory_hover_images"] = build_factory_hover_images(
            raw,
            sim_input,
            sim_output,
            input_arrivals_csv,
            supplier_shipments_csv,
            supplier_stocks_csv,
            sim_input_png_dir,
            sim_output_png_dir,
            demand_service_csv,
            production_constraint_csv,
        )
        payload["factory_current_metrics"] = build_factory_current_metrics(
            raw,
            production_constraint_csv,
        )
        payload["supplier_hover_images"] = build_supplier_hover_images(
            raw,
            sim_input_png_dir,
            supplier_shipments_csv,
            supplier_stocks_csv,
            supplier_capacity_csv,
        )
        payload["distribution_center_hover_images"] = build_distribution_center_hover_images(
            raw,
            sim_input_png_dir,
            Path(args.dc_stocks_csv),
            supplier_shipments_csv,
            Path(args.dc_stocks_csv).parent / "mrp_trace_daily.csv",
        )
        edge_metrics = build_edge_metrics(raw, supplier_shipments_csv)
        for edge_payload in payload.get("edges", []) or []:
            edge_id = str(edge_payload.get("id") or "")
            if edge_id in edge_metrics:
                edge_payload["edge_metrics"] = edge_metrics[edge_id]
        payload["model_panel"] = build_model_panel_metrics(
            raw,
            sim_input_stocks_csv=sim_input,
            sim_output_products_csv=sim_output,
            input_arrivals_csv=input_arrivals_csv,
            demand_service_csv=demand_service_csv,
            supplier_shipments_csv=supplier_shipments_csv,
            supplier_stocks_csv=supplier_stocks_csv,
            supplier_capacity_csv=supplier_capacity_csv,
            dc_stocks_csv=Path(args.dc_stocks_csv),
            production_constraint_csv=production_constraint_csv,
        )
        payload["customer_hover_images"], payload["customer_current_metrics"] = build_customer_hover_images(
            raw,
            demand_service_csv,
            supplier_shipments_csv,
        )
        payload["global_kpi_tree"] = build_global_kpi_tree_payload(
            daily_kpi_csv,
            demand_service_csv,
            production_constraint_csv,
        )
        (
            payload["factory_sensitivity_hover_images"],
            payload["supplier_sensitivity_hover_images"],
            payload["distribution_center_sensitivity_hover_images"],
        ) = build_sensitivity_hover_payloads(raw, sensitivity_cases_csv)
        (
            factory_threshold_hover_images,
            supplier_threshold_hover_images,
            dc_threshold_hover_images,
        ) = build_threshold_hover_payloads(
            raw,
            threshold_parameter_summary_csv,
            threshold_sweep_cases_csv,
            threshold_sensitivity_summary_json,
        )
        payload["factory_sensitivity_hover_images"] = merge_hover_payload_maps(
            factory_threshold_hover_images,
            payload["factory_sensitivity_hover_images"],
        )
        payload["supplier_sensitivity_hover_images"] = merge_hover_payload_maps(
            supplier_threshold_hover_images,
            payload["supplier_sensitivity_hover_images"],
        )
        payload["distribution_center_sensitivity_hover_images"] = merge_hover_payload_maps(
            dc_threshold_hover_images,
            payload["distribution_center_sensitivity_hover_images"],
        )
        (
            payload["factory_structural_hover_images"],
            payload["supplier_structural_hover_images"],
            payload["distribution_center_structural_hover_images"],
        ) = build_structural_sensitivity_hover_payloads(raw, structural_sensitivity_cases_csv)
        (
            payload["supplier_local_metrics"],
            supplier_local_ranking_rows,
            supplier_local_summary,
        ) = build_supplier_local_criticality(
            raw,
            supplier_shipments_csv,
            supplier_stocks_csv,
            supplier_capacity_csv,
            production_constraint_csv,
            sensitivity_cases_csv,
            structural_sensitivity_cases_csv,
        )
        payload["realistic_sensitivity"] = build_realistic_sensitivity_panel_metrics(
            raw,
            realistic_sensitivity_summary_json,
            realistic_local_elasticities_csv,
            realistic_stress_impacts_csv,
        )
        payload["threshold_sensitivity"] = build_threshold_sensitivity_panel_metrics(
            raw,
            threshold_sensitivity_summary_json,
            threshold_parameter_summary_csv,
        )
        material_table_rows = build_material_balance_table_rows(
            raw,
            demand_service_csv=demand_service_csv,
            sim_input_stocks_csv=sim_input,
            sim_output_products_csv=sim_output,
            supplier_shipments_csv=supplier_shipments_csv,
            safety_reference_csv=Path(args.safety_reference_csv) if args.safety_reference_csv else None,
        )
    except Exception as exc:
        print(f"[ERROR] Unable to read/parse input JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    csv_columns = sorted({key for row in supplier_local_ranking_rows for key in row.keys()})
    with supplier_local_criticality_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(supplier_local_ranking_rows)
    supplier_local_criticality_json.write_text(
        json.dumps(
            {
                "summary": supplier_local_summary,
                "ranking": supplier_local_ranking_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    html_str = html_template(
        args.title,
        json.dumps(payload, ensure_ascii=False),
        render_material_balance_table_html(material_table_rows),
        len(material_table_rows),
    )
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
