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
from typing import Any, Callable, Iterable

try:
    from etudecas.simulation.kpi_engine import (
        DEFAULT_PHYSICS_KPI_DEFINITIONS,
        KpiDefinition,
        compute_kpi_rows,
        write_kpi_rows_csv,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from etudecas.simulation.kpi_engine import (
        DEFAULT_PHYSICS_KPI_DEFINITIONS,
        KpiDefinition,
        compute_kpi_rows,
        write_kpi_rows_csv,
    )

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

DEBUG_PANEL_ENABLED = False


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
        "--supplier-stock-flows-csv",
        default="",
        help="Baseline supplier stock flow CSV with incoming/outgoing stock movements.",
    )
    parser.add_argument(
        "--supplier-capacity-csv",
        default="etudecas/simulation/result/data/production_supplier_capacity_daily.csv",
        help="Baseline supplier capacity utilization CSV.",
    )
    parser.add_argument(
        "--supplier-nominal-parameters-csv",
        default="",
        help="Optional supplier nominal parameter CSV generated by the simulation.",
    )
    parser.add_argument(
        "--factory-nominal-capacities-csv",
        default="",
        help="Optional factory/process nominal capacity CSV generated by the simulation.",
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


def collect_node_item_ids(node: dict[str, Any]) -> list[str]:
    item_ids: set[str] = set()
    for state in (((node.get("inventory") or {}).get("states")) or []):
        if isinstance(state, dict):
            item_id = str(state.get("item_id") or "").strip()
            if item_id:
                item_ids.add(item_id)
    for proc in node.get("processes") or []:
        if not isinstance(proc, dict):
            continue
        for entry in (proc.get("inputs") or []) + (proc.get("outputs") or []):
            if not isinstance(entry, dict):
                continue
            item_id = str(entry.get("item_id") or "").strip()
            if item_id:
                item_ids.add(item_id)
    return sorted(item_ids)


def json_edge_summary(edge: dict[str, Any], item_labels: dict[str, str]) -> dict[str, Any]:
    items = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
    return {
        "id": edge.get("id"),
        "type": edge.get("type"),
        "from": edge.get("from"),
        "to": edge.get("to"),
        "items": [
            {
                "id": item_id,
                "label": item_labels.get(item_id, compact_item_label(item_id)),
            }
            for item_id in items
        ],
        "lead_time": edge.get("lead_time"),
        "distance_km": edge.get("distance_km"),
        "transport_cost": edge.get("transport_cost"),
        "standard_order_qty": display_standard_order_qty(edge),
        "attrs": edge.get("attrs") or {},
    }


def render_json_panel_html(title: str, description: str, data: Any) -> str:
    pretty = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent jsonPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(title)}</div>",
            f"<div class=\"orderLedgerStatus\">{html.escape(description)}</div>",
            "<div class=\"jsonPanelPreWrap\">",
            f"<pre class=\"jsonPanelPre\">{html.escape(pretty)}</pre>",
            "</div>",
            "</div>",
        ]
    )


def json_html_asset(title: str, description: str, data: Any) -> dict[str, str]:
    return {
        "html": render_json_panel_html(title, description, data),
    }


def build_json_panel_payload(raw: dict[str, Any]) -> dict[str, Any]:
    item_labels = item_label_lookup(raw)
    item_by_id = {
        str(item.get("id") or ""): item
        for item in raw.get("items", []) or []
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    node_by_id = {
        str(node.get("id") or ""): node
        for node in raw.get("nodes", []) or []
        if isinstance(node, dict) and str(node.get("id") or "") and not is_pilotage_hidden_node(str(node.get("id") or ""))
    }
    visible_edges = [
        edge
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict)
        and not is_pilotage_hidden_edge(str(edge.get("from") or ""), str(edge.get("to") or ""))
    ]
    inbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in visible_edges:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        summary = json_edge_summary(edge, item_labels)
        if dst:
            inbound_by_node[dst].append(summary)
        if src:
            outbound_by_node[src].append(summary)

    node_payload: dict[str, Any] = {}
    for node_id, node in sorted(node_by_id.items()):
        item_ids = collect_node_item_ids(node)
        inventory_states = (((node.get("inventory") or {}).get("states")) or [])
        processes = node.get("processes") or []
        item_definitions = [item_by_id.get(item_id, {"id": item_id}) for item_id in item_ids]
        connected_flux = {
            "flux_entrants": inbound_by_node.get(node_id, []),
            "flux_sortants": outbound_by_node.get(node_id, []),
        }
        full_payload = {
            "node": node,
            "items_identifies": item_definitions,
            **connected_flux,
        }
        node_payload[node_id] = {
            "title": f"{display_node_label(node_id)} - donnees JSON",
            "summary_lines": [
                {"label": "Noeud", "value": display_node_label(node_id)},
                {"label": "Type", "value": str(node.get("type") or "n/a")},
                {"label": "Nom", "value": str(node.get("name") or "")},
                {"label": "Stocks declares", "value": str(len(inventory_states))},
                {"label": "Processus declares", "value": str(len(processes))},
                {"label": "Items identifies", "value": str(len(item_ids))},
                {"label": "Flux entrants / sortants", "value": f"{len(inbound_by_node.get(node_id, []))} / {len(outbound_by_node.get(node_id, []))}"},
            ],
            "incoming": json_html_asset(
                f"{display_node_label(node_id)} - noeud brut",
                "Objet noeud tel qu'il est disponible dans le JSON scenario.",
                node,
            ),
            "outgoing": json_html_asset(
                f"{display_node_label(node_id)} - stocks et processus",
                "Stocks initiaux/politiques MRP et processus de production declares sur le noeud.",
                {
                    "inventory": node.get("inventory") or {},
                    "processes": processes,
                },
            ),
            "third": json_html_asset(
                f"{display_node_label(node_id)} - flux connectes",
                "Flux entrants et sortants visibles dans la carte pour ce noeud.",
                connected_flux,
            ),
            "fourth": {
                "bundle": [
                    {
                        "label": "Noeud complet",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - JSON complet",
                            "Vue consolidee: noeud, items identifies et flux connectes.",
                            full_payload,
                        ),
                    },
                    {
                        "label": "Items",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - items",
                            "Definitions des items references par les stocks/processus du noeud.",
                            item_definitions,
                        ),
                    },
                    {
                        "label": "Flux entrants",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - flux entrants",
                            "Flux amont qui alimentent ce noeud.",
                            connected_flux["flux_entrants"],
                        ),
                    },
                    {
                        "label": "Flux sortants",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - flux sortants",
                            "Flux aval expedies depuis ce noeud.",
                            connected_flux["flux_sortants"],
                        ),
                    },
                ]
            },
        }

    edge_payload: dict[str, Any] = {}
    for edge in visible_edges:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        item_ids = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        item_definitions = [item_by_id.get(item_id, {"id": item_id}) for item_id in item_ids]
        source_node = node_by_id.get(src, {"id": src})
        destination_node = node_by_id.get(dst, {"id": dst})
        summary = json_edge_summary(edge, item_labels)
        full_payload = {
            "flux": edge,
            "resume_flux": summary,
            "source_node": source_node,
            "destination_node": destination_node,
            "items": item_definitions,
        }
        edge_payload[edge_id] = {
            "title": f"{src} -> {dst} - donnees JSON",
            "summary_lines": [
                {"label": "Flux", "value": f"{src} -> {dst}"},
                {"label": "Type", "value": str(edge.get("type") or "n/a")},
                {"label": "Items", "value": ", ".join(item_labels.get(item_id, compact_item_label(item_id)) for item_id in item_ids) or "n/a"},
                {"label": "Delai prev.", "value": f"{max(1.0, to_float(((edge.get('lead_time') or {}).get('mean'))) or 1.0):.1f} j"},
                {"label": "Distance", "value": f"{max(0.0, to_float(edge.get('distance_km')) or 0.0):.0f} km"},
                {"label": "Commande standard", "value": fmt_qty(display_standard_order_qty(edge), 1)},
            ],
            "incoming": json_html_asset(
                f"{src} -> {dst} - flux brut",
                "Objet flux tel qu'il est disponible dans le JSON scenario.",
                edge,
            ),
            "outgoing": json_html_asset(
                f"{src} -> {dst} - source et destination",
                "Noeuds source et destination associes a ce flux.",
                {
                    "source_node": source_node,
                    "destination_node": destination_node,
                },
            ),
            "third": json_html_asset(
                f"{src} -> {dst} - items",
                "Definitions des items transportes par ce flux.",
                item_definitions,
            ),
            "fourth": {
                "bundle": [
                    {
                        "label": "Flux complet",
                        "asset": json_html_asset(
                            f"{src} -> {dst} - JSON complet",
                            "Vue consolidee: flux, source, destination et items.",
                            full_payload,
                        ),
                    },
                    {
                        "label": "Resume flux",
                        "asset": json_html_asset(
                            f"{src} -> {dst} - resume flux",
                            "Resume lisible des principales proprietes du flux.",
                            summary,
                        ),
                    },
                ]
            },
        }

    return {
        "nodes": node_payload,
        "edges": edge_payload,
    }


def render_data_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "<div class=\"panelEmptyState dataEmptyState\">Aucune donnee disponible.</div>"
    header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
    body_html = "".join(
        "<tr>"
        + "".join(f"<td>{html.escape(str(cell if cell is not None else 'n/a'))}</td>" for cell in row)
        + "</tr>"
        for row in rows
    )
    return (
        "<div class=\"dataSummaryTableWrap\">"
        "<table class=\"dataSummaryTable\">"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        "</table>"
        "</div>"
    )


def render_data_kv(rows: list[tuple[str, Any]]) -> str:
    if not rows:
        return ""
    return "".join(
        [
            "<div class=\"dataKvGrid\">",
            *(
                f"<div class=\"dataKvLabel\">{html.escape(str(label))}</div>"
                f"<div class=\"dataKvValue\">{html.escape(str(value if value not in (None, '') else 'n/a'))}</div>"
                for label, value in rows
            ),
            "</div>",
        ]
    )


def render_data_panel_html(title: str, subtitle: str, sections: list[tuple[str, str]]) -> str:
    section_parts: list[str] = []
    for section_title, content in sections:
        section_parts.extend(
            [
                "<section class=\"dataSummarySection\">",
                f"<div class=\"dataSummarySectionTitle\">{html.escape(section_title)}</div>",
                content,
                "</section>",
            ]
        )
    section_html = "".join(section_parts)
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent dataSummaryPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(title)}</div>",
            f"<div class=\"orderLedgerStatus\">{html.escape(subtitle)}</div>",
            "<div class=\"dataSummaryScroll\">",
            section_html,
            "</div>",
            "</div>",
        ]
    )


def data_html_asset(title: str, subtitle: str, sections: list[tuple[str, str]]) -> dict[str, str]:
    return {
        "html": render_data_panel_html(title, subtitle, sections),
    }


def item_display(item_id: str, item_labels: dict[str, str]) -> str:
    return item_labels.get(item_id, compact_item_label(item_id))


def format_policy_value(value: Any, decimals: int = 1) -> str:
    numeric = to_float(value)
    if numeric is None:
        return str(value) if value not in (None, "") else "n/a"
    return fmt_qty(numeric, decimals)


def summarize_inventory_rows(node: dict[str, Any], item_labels: dict[str, str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for state in (((node.get("inventory") or {}).get("states")) or []):
        if not isinstance(state, dict):
            continue
        item_id = str(state.get("item_id") or "")
        mrp_policy = state.get("mrp_policy") or {}
        holding = state.get("holding_cost") or {}
        rows.append(
            [
                item_display(item_id, item_labels),
                format_policy_value(state.get("initial"), 1),
                str(state.get("uom") or "n/a"),
                format_policy_value(mrp_policy.get("safety_stock_qty"), 1),
                format_policy_value(mrp_policy.get("safety_time_days"), 1),
                format_policy_value(holding.get("unit_value_basis"), 4),
                str(state.get("initial_source") or mrp_policy.get("source") or "n/a"),
            ]
        )
    return rows


def summarize_process_rows(node: dict[str, Any], item_labels: dict[str, str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for proc in node.get("processes") or []:
        if not isinstance(proc, dict):
            continue
        outputs = [
            item_display(str(out.get("item_id") or ""), item_labels)
            for out in proc.get("outputs") or []
            if isinstance(out, dict)
        ]
        inputs = []
        for inp in proc.get("inputs") or []:
            if not isinstance(inp, dict):
                continue
            item_id = str(inp.get("item_id") or "")
            ratio = format_policy_value(inp.get("ratio_per_batch"), 4)
            unit = str(inp.get("uom") or inp.get("ratio_uom") or "").strip()
            inputs.append(f"{item_display(item_id, item_labels)}={ratio} {unit}".strip())
        lot_sizing = proc.get("lot_sizing") or {}
        lot_exec = proc.get("lot_execution") or {}
        capacity = proc.get("capacity") or {}
        rows.append(
            [
                str(proc.get("id") or "n/a"),
                ", ".join(outputs) or "n/a",
                ", ".join(inputs) or "n/a",
                format_policy_value(proc.get("batch_size"), 1),
                format_policy_value(lot_sizing.get("fixed_lot_qty") or lot_sizing.get("min_lot_qty") or lot_sizing.get("lot_multiple_qty"), 1),
                format_policy_value(lot_exec.get("max_lots_per_week"), 1),
                format_policy_value(capacity.get("max_rate"), 1),
            ]
        )
    return rows


def summarize_flux_rows(edges: list[dict[str, Any]], item_labels: dict[str, str], *, direction: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for edge in edges:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        peer = src if direction == "in" else dst
        item_ids = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        lead_time = edge.get("lead_time") or {}
        rows.append(
            [
                peer or "n/a",
                ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a",
                format_policy_value(lead_time.get("mean"), 1),
                str(lead_time.get("type") or "n/a"),
                format_policy_value(display_standard_order_qty(edge), 1),
                format_policy_value(edge.get("distance_km"), 0),
            ]
        )
    return rows


def build_data_panel_payload(raw: dict[str, Any]) -> dict[str, Any]:
    item_labels = item_label_lookup(raw)
    item_by_id = {
        str(item.get("id") or ""): item
        for item in raw.get("items", []) or []
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    nodes = [
        node
        for node in raw.get("nodes", []) or []
        if isinstance(node, dict) and not is_pilotage_hidden_node(str(node.get("id") or ""))
    ]
    node_by_id = {str(node.get("id") or ""): node for node in nodes if str(node.get("id") or "")}
    edges = [
        edge
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict)
        and not is_pilotage_hidden_edge(str(edge.get("from") or ""), str(edge.get("to") or ""))
    ]
    inbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        inbound_by_node[str(edge.get("to") or "")].append(edge)
        outbound_by_node[str(edge.get("from") or "")].append(edge)

    node_payload: dict[str, Any] = {}
    for node in sorted(nodes, key=lambda row: str(row.get("id") or "")):
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        item_ids = collect_node_item_ids(node)
        geo = node.get("geo") or {}
        inventory_rows = summarize_inventory_rows(node, item_labels)
        process_rows = summarize_process_rows(node, item_labels)
        inbound_rows = summarize_flux_rows(inbound_by_node.get(node_id, []), item_labels, direction="in")
        outbound_rows = summarize_flux_rows(outbound_by_node.get(node_id, []), item_labels, direction="out")
        summary_rows = [
            ("Noeud", display_node_label(node_id)),
            ("Type", node.get("type") or "n/a"),
            ("Nom", node.get("name") or "n/a"),
            ("Pays", geo.get("country") or node.get("country") or "n/a"),
            ("Items", ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a"),
            ("Stocks / processus", f"{len(inventory_rows)} / {len(process_rows)}"),
            ("Flux entrants / sortants", f"{len(inbound_rows)} / {len(outbound_rows)}"),
        ]
        node_payload[node_id] = {
            "title": f"{display_node_label(node_id)} - synthese donnees",
            "summary_lines": [
                {"label": "Noeud", "value": display_node_label(node_id)},
                {"label": "Type", "value": str(node.get("type") or "n/a")},
                {"label": "Items", "value": str(len(item_ids))},
                {"label": "Stocks / processus", "value": f"{len(inventory_rows)} / {len(process_rows)}"},
                {"label": "Flux entrants / sortants", "value": f"{len(inbound_rows)} / {len(outbound_rows)}"},
            ],
            "incoming": data_html_asset(
                f"{display_node_label(node_id)} - fiche noeud",
                "Resume des champs utiles presents dans le JSON du scenario.",
                [("Identite", render_data_kv(summary_rows))],
            ),
            "outgoing": data_html_asset(
                f"{display_node_label(node_id)} - stocks et processus",
                "Stocks initiaux, politique MRP et processus declares.",
                [
                    (
                        "Stocks / politiques MRP",
                        render_data_table(
                            ["Item", "Stock initial", "UoM", "Stock secu", "Delai secu j", "Valeur unite", "Source"],
                            inventory_rows,
                        ),
                    ),
                    (
                        "Processus",
                        render_data_table(
                            ["Process", "Sorties", "Intrants", "Batch", "Lot", "Lots/sem", "Cap/j"],
                            process_rows,
                        ),
                    ),
                ],
            ),
            "third": data_html_asset(
                f"{display_node_label(node_id)} - flux connectes",
                "Flux entrants et sortants disponibles pour ce noeud.",
                [
                    (
                        "Flux entrants",
                        render_data_table(
                            ["Source", "Items", "Delai j", "Type delai", "Commande std", "Distance km"],
                            inbound_rows,
                        ),
                    ),
                    (
                        "Flux sortants",
                        render_data_table(
                            ["Destination", "Items", "Delai j", "Type delai", "Commande std", "Distance km"],
                            outbound_rows,
                        ),
                    ),
                ],
            ),
            "fourth": data_html_asset(
                f"{display_node_label(node_id)} - items references",
                "Definitions courtes des items rattaches au noeud.",
                [
                    (
                        "Items",
                        render_data_table(
                            ["Item", "Code", "Nom", "Type", "UoM"],
                            [
                                [
                                    item_display(item_id, item_labels),
                                    (item_by_id.get(item_id) or {}).get("code") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("name") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("kind") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("uom_default") or "n/a",
                                ]
                                for item_id in item_ids
                            ],
                        ),
                    )
                ],
            ),
        }

    edge_payload: dict[str, Any] = {}
    for edge in edges:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        item_ids = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        lead_time = edge.get("lead_time") or {}
        order_terms = edge.get("order_terms") or {}
        transport_cost = edge.get("transport_cost") or {}
        summary_rows = [
            ("Flux", f"{src} -> {dst}"),
            ("Type", edge.get("type") or "n/a"),
            ("Items", ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a"),
            ("Delai previsionnel", f"{format_policy_value(lead_time.get('mean'), 1)} j"),
            ("Type delai", lead_time.get("type") or "n/a"),
            ("Source delai", lead_time.get("source") or "n/a"),
            ("Distance", f"{format_policy_value(edge.get('distance_km'), 0)} km"),
            ("Commande standard", format_policy_value(display_standard_order_qty(edge), 1)),
            ("Cout transport", f"{format_policy_value(transport_cost.get('value'), 4)} / {transport_cost.get('per') or 'n/a'}"),
            ("Prix achat", f"{format_policy_value(order_terms.get('sell_price'), 4)} / {order_terms.get('price_base') or 'n/a'} {order_terms.get('quantity_unit') or ''}".strip()),
        ]
        edge_payload[edge_id] = {
            "title": f"{src} -> {dst} - synthese donnees",
            "summary_lines": [
                {"label": "Flux", "value": f"{src} -> {dst}"},
                {"label": "Items", "value": ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a"},
                {"label": "Delai prev.", "value": f"{format_policy_value(lead_time.get('mean'), 1)} j"},
                {"label": "Commande std", "value": format_policy_value(display_standard_order_qty(edge), 1)},
            ],
            "incoming": data_html_asset(
                f"{src} -> {dst} - fiche flux",
                "Resume des champs utiles presents dans le JSON du scenario.",
                [("Identite et parametres", render_data_kv(summary_rows))],
            ),
            "outgoing": data_html_asset(
                f"{src} -> {dst} - source / destination",
                "Resume court des noeuds relies par le flux.",
                [
                    (
                        "Noeuds",
                        render_data_table(
                            ["Role", "Noeud", "Type", "Nom", "Pays"],
                            [
                                [
                                    "Source",
                                    src,
                                    (node_by_id.get(src) or {}).get("type") or "n/a",
                                    (node_by_id.get(src) or {}).get("name") or "n/a",
                                    ((node_by_id.get(src) or {}).get("geo") or {}).get("country") or "n/a",
                                ],
                                [
                                    "Destination",
                                    dst,
                                    (node_by_id.get(dst) or {}).get("type") or "n/a",
                                    (node_by_id.get(dst) or {}).get("name") or "n/a",
                                    ((node_by_id.get(dst) or {}).get("geo") or {}).get("country") or "n/a",
                                ],
                            ],
                        ),
                    )
                ],
            ),
            "third": data_html_asset(
                f"{src} -> {dst} - items transportes",
                "Definitions courtes des items transportes par ce flux.",
                [
                    (
                        "Items",
                        render_data_table(
                            ["Item", "Code", "Nom", "Type", "UoM"],
                            [
                                [
                                    item_display(item_id, item_labels),
                                    (item_by_id.get(item_id) or {}).get("code") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("name") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("kind") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("uom_default") or "n/a",
                                ]
                                for item_id in item_ids
                            ],
                        ),
                    )
                ],
            ),
            "fourth": data_html_asset(
                f"{src} -> {dst} - couts et delais",
                "Champs economiques et delai utilises par le simulateur.",
                [
                    ("Delai", render_data_kv([
                        ("Moyenne", f"{format_policy_value(lead_time.get('mean'), 1)} j"),
                        ("Type", lead_time.get("type") or "n/a"),
                        ("Stages", lead_time.get("stages") or "n/a"),
                        ("Source", lead_time.get("source") or "n/a"),
                    ])),
                    ("Economique", render_data_kv([
                        ("Prix achat", f"{format_policy_value(order_terms.get('sell_price'), 4)} / {order_terms.get('price_base') or 'n/a'} {order_terms.get('quantity_unit') or ''}".strip()),
                        ("Cout transport", f"{format_policy_value(transport_cost.get('value'), 4)} / {transport_cost.get('per') or 'n/a'}"),
                        ("Source cout", transport_cost.get("source") or order_terms.get("source") or "n/a"),
                    ])),
                ],
            ),
        }

    return {
        "nodes": node_payload,
        "edges": edge_payload,
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


def build_edge_metrics(
    raw: dict[str, Any],
    supplier_shipments_csv: Path,
    *,
    horizon_days: int | None = None,
) -> dict[str, dict[str, Any]]:
    rows = read_csv_rows(supplier_shipments_csv)
    if horizon_days and horizon_days > 0:
        horizon_end = horizon_days - 1
        rows = [
            row
            for row in rows
            if 0 <= int(to_float(row.get("day")) or 0) <= horizon_end
        ]
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
        incoming_item_labels: set[str] = set()
        for descriptor in incoming_descriptors:
            item_label = str(descriptor.get("item_label") or descriptor.get("item_id") or "").strip()
            if item_label:
                incoming_item_labels.add(item_label)
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
                    incoming_item_labels.add(item_label)
                    incoming_arrival_series[f"{item_label} - reception"] = arrival_pts
        display_factory_id = display_node_label(factory_id)
        incoming_title = f"{display_factory_id} - stocks et receptions intrants"
        top_title = f"{display_factory_id} - stock intrants"
        bottom_title = f"{display_factory_id} - receptions intrants"
        if is_upstream_internal_site(factory_id):
            sorted_incoming_items = sorted(incoming_item_labels)
            if len(sorted_incoming_items) == 1:
                incoming_item_label = sorted_incoming_items[0]
                incoming_title = f"{display_factory_id} - intrant {incoming_item_label}: stock et arrivages"
                top_title = f"{display_factory_id} - stock intrant {incoming_item_label}"
                bottom_title = f"{display_factory_id} - arrivages intrant {incoming_item_label}"
            else:
                incoming_title = f"{display_factory_id} - stocks et arrivages intrants"
                bottom_title = f"{display_factory_id} - arrivages intrants"
        if incoming_stock_series or incoming_arrival_series:
            figure = build_dual_line_multi_panel_figure(
                title=incoming_title,
                top_title=top_title,
                top_y_label="Stock",
                top_series_map=incoming_stock_series,
                bottom_title=bottom_title,
                bottom_y_label="Receptions",
                bottom_series_map=incoming_arrival_series,
                bottom_step_like=True,
            )
            if figure is not None:
                incoming = {"figure": figure}
        outgoing_descriptors = detail.get("outgoing") or []
        outgoing_stock_series = {
            f"{str(descriptor.get('item_label') or descriptor.get('item_id') or '').strip()} - stock": list(
                zip(descriptor.get("days") or [], descriptor.get("stock_values") or [])
            )
            for descriptor in outgoing_descriptors
            if str(descriptor.get("item_label") or descriptor.get("item_id") or "").strip()
        }
        outgoing_stock_series = {label: pts for label, pts in outgoing_stock_series.items() if pts}
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
                if outgoing_stock_series:
                    figure = build_dual_line_multi_panel_figure(
                        title=f"{display_factory_id} - stock et expeditions PFI",
                        top_title=f"{display_factory_id} - stock PFI produits",
                        top_y_label="Stock",
                        top_series_map=outgoing_stock_series,
                        bottom_title=f"{display_factory_id} - expeditions PFI par item",
                        bottom_y_label="Expeditions",
                        bottom_series_map=outbound_series,
                        bottom_step_like=True,
                    )
                else:
                    figure = build_line_chart_figure(
                        outbound_series,
                        title=f"{display_factory_id} - expeditions PFI par item",
                        y_label="Quantite",
                        step_like=True,
                    )
                if figure is not None:
                    outgoing = {"figure": figure}
        factory_rows = [row for row in constraint_rows if str(row.get("node_id") or "") == factory_id]
        production_gantt_figure = build_factory_production_gantt_figure(raw, factory_id, factory_rows, item_labels)
        production_gantt = {"figure": production_gantt_figure} if production_gantt_figure is not None else None
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
            if production_gantt is not None:
                auxiliary = production_gantt
            elif site_stock_payload is not None:
                if incoming is None:
                    incoming = site_stock_payload
                else:
                    auxiliary = site_stock_payload
        elif production_gantt is not None:
            auxiliary = production_gantt
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


def build_factory_production_gantt_figure(
    raw: dict[str, Any],
    factory_id: str,
    factory_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> dict[str, Any] | None:
    process_tau_by_item: dict[str, float] = {}
    node = next((n for n in (raw.get("nodes") or []) if str(n.get("id") or "") == factory_id), None)
    for proc in (node or {}).get("processes") or []:
        tau_process = max(0.0, to_float(((proc.get("wip") or {}).get("tau_process"))) or 0.0)
        for out in proc.get("outputs") or []:
            item_id = str(out.get("item_id") or "")
            if item_id:
                process_tau_by_item[item_id] = tau_process

    rows: list[dict[str, Any]] = []
    for row in sorted(factory_rows, key=lambda r: (int(to_float(r.get("day")) or 0), str(r.get("output_item_id") or ""))):
        item_id = str(row.get("output_item_id") or "")
        if not item_id or is_simulation_hidden_item(item_id):
            continue
        lot_starts = max(0.0, to_float(row.get("actual_lot_starts")) or 0.0)
        if lot_starts <= 1e-9:
            continue
        started_qty = max(0.0, to_float(row.get("campaign_started_qty")) or 0.0)
        if started_qty <= 1e-9:
            started_qty = max(0.0, to_float(row.get("actual_qty")) or 0.0)
        if started_qty <= 1e-9:
            continue
        day = int(to_float(row.get("day")) or 0)
        cap_qty = max(0.0, to_float(row.get("cap_qty")) or 0.0)
        capacity_mode = str(row.get("capacity_limit_mode") or "")
        if cap_qty > 1e-9:
            duration = max(1.0, float(math.ceil(started_qty / cap_qty)))
            duration_basis = "quantite / capacite journaliere"
        else:
            duration = 0.6
            duration_basis = "jalon de lancement (capacite non modelisee)"
        label = item_labels.get(item_id, compact_item_label(item_id))
        rows.append(
            {
                "lane": label,
                "item_id": item_id,
                "item_label": label,
                "start": day,
                "end": day + duration,
                "duration": duration,
                "duration_basis": duration_basis,
                "capacity_mode": capacity_mode,
                "cap_qty": round(cap_qty, 6),
                "tau_process": round(process_tau_by_item.get(item_id, 0.0), 6),
                "qty": round(started_qty, 6),
                "lots": round(lot_starts, 6),
                "lot_policy": str(row.get("lot_policy_mode") or ""),
                "binding_cause": str(row.get("binding_cause") or "none"),
            }
        )
    if not rows:
        return None
    return {
        "kind": "gantt",
        "title": f"{display_node_label(factory_id)} - planning production lots",
        "x_label": "Jour",
        "y_label": "Produit",
        "note": "Barres = lots lances. Duree = quantite/capacite si capacite modelisee; sinon jalon court. Ce n'est pas une charge usine complete.",
        "rows": rows,
    }


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
    supplier_stock_flows_csv: Path | None,
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
        incoming = None
        outgoing = None
        third = None
        shipped_series: list[tuple[int, float]] = []
        per_item_stock: dict[str, list[tuple[int, float]]] = {}
        combined_flow: dict[str, list[tuple[int, float]]] = {}
        shipment_rows = read_csv_rows(supplier_shipments_csv)
        flow_rows = (
            read_csv_rows(supplier_stock_flows_csv)
            if supplier_stock_flows_csv is not None and supplier_stock_flows_csv.exists()
            else []
        )
        capacity_rows = read_csv_rows(supplier_capacity_csv)
        if shipment_rows:
            shipped_series = aggregate_daily_series(
                shipment_rows,
                value_field="shipped_qty",
                node_field="src_node_id",
                node_id=supplier_id,
            )
        stock_rows = read_csv_rows(supplier_stocks_csv)
        if stock_rows:
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
        if flow_rows:
            item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in flow_rows
                    if str(row.get("node_id") or "") == supplier_id
                }
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                item_label = item_labels.get(item_id, compact_item_label(item_id))
                incoming_pts = aggregate_daily_series(
                    flow_rows,
                    value_field="incoming_qty",
                    node_field="node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                outgoing_pts = aggregate_daily_series(
                    flow_rows,
                    value_field="outgoing_pulled_qty",
                    node_field="node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                if incoming_pts:
                    combined_flow[f"{item_label} - entree stock"] = incoming_pts
                if outgoing_pts:
                    combined_flow[f"{item_label} - sortie stock"] = outgoing_pts
        elif shipment_rows:
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
        stock_title = f"{supplier_id} - stock fournisseur par item"
        if len(per_item_stock) == 1:
            stock_title = f"{stock_title} - {next(iter(per_item_stock.keys()))}"
        shipment_title = f"{supplier_id} - entrees et sorties de stock fournisseur"
        shipment_item_ids = sorted(
            {
                str(row.get("item_id") or "")
                for row in shipment_rows
                if str(row.get("src_node_id") or "") == supplier_id
            }
        )
        if len(shipment_item_ids) == 1 and shipment_item_ids:
            single_label = item_labels.get(shipment_item_ids[0], compact_item_label(shipment_item_ids[0]))
            shipment_title = f"{shipment_title} - {single_label}"
        figure = build_dual_line_multi_panel_figure(
            title=f"{supplier_id} - stock et flux fournisseur",
            top_title=stock_title,
            top_y_label="Quantite",
            top_series_map=per_item_stock,
            bottom_title=shipment_title,
            bottom_y_label="Quantite",
            bottom_series_map=combined_flow,
            top_step_like=True,
            bottom_event_like=True,
        )
        has_dynamic_supplier_panel = figure is not None
        if figure is not None:
            incoming = {"figure": figure}
        if incoming is None:
            incoming = resolve_plot_payload(
                png_dir,
                Path("suppliers") / "input_stocks" / f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
                f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
            )
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_stocks_by_material_{safe_supplier}.png")
        if outgoing is None and not has_dynamic_supplier_panel:
            outgoing = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
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
    mrp_orders_csv: Path | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    daily_rows = read_csv_rows(daily_kpi_csv)
    demand_rows = read_csv_rows(demand_service_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    mrp_order_rows = read_csv_rows(mrp_orders_csv) if mrp_orders_csv else []
    input_consumption_csv = production_constraint_csv.parent / "production_input_consumption_daily.csv"
    input_consumption_rows = read_csv_rows(input_consumption_csv) if input_consumption_csv.exists() else []
    input_stocks_csv = production_constraint_csv.parent / "production_input_stocks_daily.csv"
    input_stock_rows = read_csv_rows(input_stocks_csv) if input_stocks_csv.exists() else []
    if not daily_rows and not demand_rows and not constraint_rows:
        return None

    finished_good_item_ids: set[str] = set()
    if raw:
        item_labels = item_label_lookup(raw)
        node_type_by_id = {str(node.get("id") or ""): str(node.get("type") or "") for node in raw.get("nodes", []) or []}
        for edge in raw.get("edges", []) or []:
            if node_type_by_id.get(str(edge.get("to") or "")) != "customer":
                continue
            for edge_item_id in edge.get("items") or []:
                finished_good_item_ids.add(str(edge_item_id))
    else:
        item_labels = {}

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
            "opening_open_order_transport_cost_day",
            "external_procurement_transport_cost_day",
            "operational_transport_cost_day",
            "purchase_cost_day",
            "opening_open_order_purchase_cost_day",
            "external_procurement_purchase_cost_day",
            "operational_purchase_cost_day",
            "production_cost_day",
            "total_supply_cost_day",
            "external_procured_ordered_qty",
            "supplier_capacity_binding_qty",
        ]:
            daily_by_day[day][field] += max(0.0, to_float(row.get(field)) or 0.0)

    production_by_day: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    production_line_by_day: dict[tuple[str, str], dict[int, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for row in constraint_rows:
        day = int(to_float(row.get("day")) or 0)
        node_id = str(row.get("node_id") or "")
        output_item_id = str(row.get("output_item_id") or "")
        line_key = (node_id, output_item_id)
        desired = max(0.0, to_float(row.get("desired_qty")) or 0.0)
        planned = max(0.0, to_float(row.get("planned_qty_after_lot_rule")) or 0.0)
        actual = max(0.0, to_float(row.get("actual_qty")) or 0.0)
        shortfall = max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        overproduction = max(0.0, actual - desired)
        production_by_day[day]["desired_qty"] += desired
        production_by_day[day]["planned_qty"] += planned
        production_by_day[day]["actual_qty"] += actual
        production_by_day[day]["shortfall_qty"] += shortfall
        production_by_day[day]["overproduction_qty"] += overproduction
        production_by_day[day]["requested_lot_starts"] += max(0.0, to_float(row.get("requested_lot_starts")) or 0.0)
        production_by_day[day]["actual_lot_starts"] += max(0.0, to_float(row.get("actual_lot_starts")) or 0.0)
        production_line_by_day[line_key][day]["desired_qty"] += desired
        production_line_by_day[line_key][day]["planned_qty"] += planned
        production_line_by_day[line_key][day]["actual_qty"] += actual
        production_line_by_day[line_key][day]["shortfall_qty"] += shortfall
        production_line_by_day[line_key][day]["lot_starts"] += max(0.0, to_float(row.get("actual_lot_starts")) or 0.0)
        if desired > 1e-9:
            production_by_day[day]["active_line_count"] += 1.0
            production_by_day[day]["execution_score_sum"] += min(100.0, 100.0 * actual / desired)
            production_by_day[day]["shortfall_rate_sum"] += min(100.0, 100.0 * shortfall / desired)
            production_by_day[day]["plan_gap_rate_sum"] += min(100.0, 100.0 * abs(actual - desired) / desired)
            production_by_day[day]["overproduction_rate_sum"] += 100.0 * overproduction / desired
            if shortfall > 1e-9:
                production_by_day[day]["shortfall_line_count"] += 1.0
            if actual + 1e-9 < desired:
                production_by_day[day]["under_plan_line_count"] += 1.0
            if actual > desired * 1.05 + 1e-9:
                production_by_day[day]["over_plan_line_count"] += 1.0
        production_by_day[day]["plan_gap_qty"] += abs(
            actual
            - planned
        )
        if str(row.get("binding_cause") or "") == "input_shortage":
            production_by_day[day]["input_shortage_day"] = 1.0
            production_by_day[day]["input_shortage_line_count"] += 1.0
        if str(row.get("binding_cause") or "") == "capacity":
            production_by_day[day]["capacity_day"] = 1.0
            production_by_day[day]["capacity_line_count"] += 1.0
        if str(row.get("binding_cause") or "") == "weekly_lot_limit":
            production_by_day[day]["weekly_lot_limit_day"] = 1.0
            production_by_day[day]["weekly_lot_limit_line_count"] += 1.0

    demand_by_day: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    demand_by_item_day: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in demand_rows:
        day = int(to_float(row.get("day")) or 0)
        item_id = str(row.get("item_id") or "")
        demand_qty_row = max(0.0, to_float(row.get("demand_qty")) or 0.0)
        demand_by_day[day]["demand_qty"] += demand_qty_row
        demand_by_day[day]["required_qty"] += max(0.0, to_float(row.get("required_with_backlog_qty")) or 0.0)
        demand_by_day[day]["served_qty"] += max(0.0, to_float(row.get("served_qty")) or 0.0)
        demand_by_day[day]["backlog_end_qty"] += max(0.0, to_float(row.get("backlog_end_qty")) or 0.0)
        if item_id:
            demand_by_item_day[item_id][day] += demand_qty_row

    consumption_by_item_day: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in input_consumption_rows:
        day = int(to_float(row.get("day")) or 0)
        item_id = str(row.get("item_id") or "")
        if item_id:
            consumption_by_item_day[item_id][day] += max(0.0, to_float(row.get("consumed_qty")) or 0.0)
    items_with_consumption_signal = set(consumption_by_item_day)

    days = sorted(set(daily_by_day) | set(production_by_day) | set(demand_by_day))
    if not days:
        return None

    def series_from_map(values: dict[int, float]) -> dict[str, Any]:
        return {
            "days": days,
            "values": [round(float(values.get(day, 0.0)), 6) for day in days],
        }

    demand_qty = {day: demand_by_day[day].get("demand_qty", daily_by_day[day].get("demand", 0.0)) for day in days}
    required_qty = {day: demand_by_day[day].get("required_qty", demand_qty[day]) for day in days}
    served_qty = {day: demand_by_day[day].get("served_qty", daily_by_day[day].get("served", 0.0)) for day in days}
    backlog_qty = {day: demand_by_day[day].get("backlog_end_qty", daily_by_day[day].get("backlog_end", 0.0)) for day in days}
    service_score = {
        day: min(100.0, 100.0 * served_qty[day] / required_qty[day]) if required_qty[day] > 0 else 100.0
        for day in days
    }

    desired_qty = {day: production_by_day[day].get("desired_qty", 0.0) for day in days}
    actual_qty = {day: production_by_day[day].get("actual_qty", 0.0) for day in days}
    shortfall_qty = {day: production_by_day[day].get("shortfall_qty", 0.0) for day in days}
    planned_qty = {day: production_by_day[day].get("planned_qty", 0.0) for day in days}
    active_line_count = {day: production_by_day[day].get("active_line_count", 0.0) for day in days}
    execution_score_avg = {
        day: (
            production_by_day[day].get("execution_score_sum", 0.0) / active_line_count[day]
            if active_line_count[day] > 0
            else 100.0
        )
        for day in days
    }
    shortfall_rate_avg = {
        day: (
            production_by_day[day].get("shortfall_rate_sum", 0.0) / active_line_count[day]
            if active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    plan_gap_rate_avg = {
        day: (
            production_by_day[day].get("plan_gap_rate_sum", 0.0) / active_line_count[day]
            if active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    overproduction_rate_avg = {
        day: (
            production_by_day[day].get("overproduction_rate_sum", 0.0) / active_line_count[day]
            if active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    overproduction_rate_capped = {day: min(500.0, overproduction_rate_avg[day]) for day in days}
    strict_adherence_score = {
        day: max(0.0, 100.0 - plan_gap_rate_avg[day])
        for day in days
    }
    def rolling_strict_adherence(window_days: int) -> dict[int, float]:
        out: dict[int, float] = {}
        for idx, day in enumerate(days):
            window = days[max(0, idx - window_days + 1) : idx + 1]
            window_desired = sum(desired_qty.get(wday, 0.0) for wday in window)
            window_actual = sum(actual_qty.get(wday, 0.0) for wday in window)
            if window_desired <= 1e-9:
                out[day] = 100.0
            else:
                out[day] = max(0.0, 100.0 - 100.0 * abs(window_actual - window_desired) / window_desired)
        return out

    def production_line_reference_qty(line_key: tuple[str, str], day: int) -> float:
        _node_id, item_id = line_key
        if item_id in finished_good_item_ids:
            return demand_by_item_day[item_id].get(day, 0.0)
        if item_id in items_with_consumption_signal:
            return consumption_by_item_day[item_id].get(day, 0.0)
        return production_line_by_day[line_key][day].get("desired_qty", 0.0)

    line_keys = sorted(production_line_by_day)
    reference_qty = {day: 0.0 for day in days}
    reference_covered_qty = {day: 0.0 for day in days}
    reference_gap_rate_sum = {day: 0.0 for day in days}
    reference_coverage_rate_sum = {day: 0.0 for day in days}
    reference_overproduction_rate_sum = {day: 0.0 for day in days}
    reference_active_line_count = {day: 0.0 for day in days}
    reference_under_line_count = {day: 0.0 for day in days}
    reference_over_line_count = {day: 0.0 for day in days}
    reference_overproduction_qty = {day: 0.0 for day in days}
    reference_shortfall_qty = {day: 0.0 for day in days}
    for day in days:
        for line_key in line_keys:
            ref_qty = max(0.0, production_line_reference_qty(line_key, day))
            actual_line_qty = max(0.0, production_line_by_day[line_key][day].get("actual_qty", 0.0))
            if ref_qty <= 1e-9:
                continue
            reference_qty[day] += ref_qty
            reference_covered_qty[day] += min(actual_line_qty, ref_qty)
            reference_shortfall_qty[day] += max(0.0, ref_qty - actual_line_qty)
            reference_overproduction_qty[day] += max(0.0, actual_line_qty - ref_qty)
            reference_active_line_count[day] += 1.0
            reference_gap_rate_sum[day] += min(100.0, 100.0 * abs(actual_line_qty - ref_qty) / ref_qty)
            reference_coverage_rate_sum[day] += min(100.0, 100.0 * actual_line_qty / ref_qty)
            reference_overproduction_rate_sum[day] += 100.0 * max(0.0, actual_line_qty - ref_qty) / ref_qty
            if actual_line_qty + 1e-9 < ref_qty:
                reference_under_line_count[day] += 1.0
            if actual_line_qty > ref_qty * 1.05 + 1e-9:
                reference_over_line_count[day] += 1.0

    def production_line_display_label(line_key: tuple[str, str]) -> str:
        node_id, item_id = line_key
        return f"{display_node_label(node_id)} / {item_labels.get(item_id, compact_item_label(item_id))}"

    line_nervousness = {day: 0.0 for day in days}
    production_replanning_count = {day: 0.0 for day in days}
    previous_planned_by_line: dict[tuple[str, str], float | None] = {line_key: None for line_key in line_keys}
    for day in days:
        nervousness_values: list[float] = []
        replanning_count = 0
        for line_key in line_keys:
            current_planned = max(0.0, production_line_by_day[line_key][day].get("planned_qty", 0.0))
            previous_planned = previous_planned_by_line.get(line_key)
            if previous_planned is None:
                delta_pct = 0.0
            else:
                reference = max(abs(previous_planned), abs(current_planned), 1.0)
                delta_pct = min(500.0, 100.0 * abs(current_planned - previous_planned) / reference)
                if abs(current_planned - previous_planned) > max(1.0, reference * 0.01):
                    replanning_count += 1
            if current_planned > 1e-9 or (previous_planned or 0.0) > 1e-9:
                nervousness_values.append(delta_pct)
            previous_planned_by_line[line_key] = current_planned
        line_nervousness[day] = (
            sum(nervousness_values) / len(nervousness_values)
            if nervousness_values
            else 0.0
        )
        production_replanning_count[day] = float(replanning_count)

    def forward_line_variance_rates(window_days: int) -> tuple[dict[int, float], dict[int, float], dict[tuple[str, str], dict[int, float]], dict[tuple[str, str], dict[int, float]]]:
        avg_coverage_by_day: dict[int, float] = {}
        avg_over_by_day: dict[int, float] = {}
        under_by_line: dict[tuple[str, str], dict[int, float]] = {line_key: {} for line_key in line_keys}
        over_by_line: dict[tuple[str, str], dict[int, float]] = {line_key: {} for line_key in line_keys}
        for idx, day in enumerate(days):
            window = days[idx : min(len(days), idx + window_days)]
            coverage_scores: list[float] = []
            over_scores: list[float] = []
            for line_key in line_keys:
                window_reference = sum(production_line_reference_qty(line_key, wday) for wday in window)
                window_actual = sum(production_line_by_day[line_key][wday].get("actual_qty", 0.0) for wday in window)
                if window_reference <= 1e-9 and window_actual <= 1e-9:
                    under_by_line[line_key][day] = 0.0
                    over_by_line[line_key][day] = 0.0
                    continue
                if window_reference <= 1e-9:
                    under_by_line[line_key][day] = 0.0
                    over_by_line[line_key][day] = 500.0
                    over_scores.append(500.0)
                else:
                    coverage_scores.append(min(100.0, 100.0 * window_actual / window_reference))
                    under_rate = min(500.0, 100.0 * max(0.0, window_reference - window_actual) / window_reference)
                    over_rate = min(500.0, 100.0 * max(0.0, window_actual - window_reference) / window_reference)
                    under_by_line[line_key][day] = under_rate
                    over_by_line[line_key][day] = over_rate
                    over_scores.append(over_rate)
            avg_coverage_by_day[day] = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 100.0
            avg_over_by_day[day] = sum(over_scores) / len(over_scores) if over_scores else 0.0
        return avg_coverage_by_day, avg_over_by_day, under_by_line, over_by_line

    def net_delay_catchup_rate(window_days: int) -> tuple[dict[int, float], dict[int, float]]:
        net_delay_by_line_day: dict[tuple[str, str], dict[int, float]] = {line_key: {} for line_key in line_keys}
        for line_key in line_keys:
            cumulative_balance = 0.0
            for day in days:
                reference = max(0.0, production_line_reference_qty(line_key, day))
                actual = max(0.0, production_line_by_day[line_key][day].get("actual_qty", 0.0))
                cumulative_balance += actual - reference
                net_delay_by_line_day[line_key][day] = max(0.0, -cumulative_balance)

        rate_by_day: dict[int, float] = {}
        net_delay_qty_by_day: dict[int, float] = {}
        for idx, day in enumerate(days):
            future_days = days[idx + 1 : min(len(days), idx + 1 + window_days)]
            total_net_delay = 0.0
            total_caught_up = 0.0
            for line_key in line_keys:
                current_delay = net_delay_by_line_day[line_key].get(day, 0.0)
                if current_delay <= 1e-9:
                    continue
                min_future_delay = (
                    min(net_delay_by_line_day[line_key].get(future_day, current_delay) for future_day in future_days)
                    if future_days
                    else current_delay
                )
                total_net_delay += current_delay
                total_caught_up += max(0.0, current_delay - min_future_delay)
            net_delay_qty_by_day[day] = total_net_delay
            rate_by_day[day] = 100.0 * total_caught_up / total_net_delay if total_net_delay > 1e-9 else 100.0
        return rate_by_day, net_delay_qty_by_day

    def rolling_line_adherence(window_days: int) -> dict[int, float]:
        out: dict[int, float] = {}
        for idx, day in enumerate(days):
            window = days[max(0, idx - window_days + 1) : idx + 1]
            scores = []
            for line_key in line_keys:
                window_reference = sum(production_line_reference_qty(line_key, wday) for wday in window)
                window_actual = sum(production_line_by_day[line_key][wday].get("actual_qty", 0.0) for wday in window)
                if window_reference > 1e-9:
                    scores.append(max(0.0, 100.0 - 100.0 * abs(window_actual - window_reference) / window_reference))
                elif window_actual > 1e-9:
                    scores.append(0.0)
            out[day] = sum(scores) / len(scores) if scores else 100.0
        return out

    def rolling_lot_plan_adherence(window_days: int) -> dict[int, float]:
        out: dict[int, float] = {}
        for idx, day in enumerate(days):
            window = days[max(0, idx - window_days + 1) : idx + 1]
            scores = []
            for line_key in line_keys:
                window_planned = sum(production_line_by_day[line_key][wday].get("planned_qty", 0.0) for wday in window)
                window_actual = sum(production_line_by_day[line_key][wday].get("actual_qty", 0.0) for wday in window)
                if window_planned > 1e-9:
                    scores.append(max(0.0, 100.0 - 100.0 * abs(window_actual - window_planned) / window_planned))
                elif window_actual > 1e-9:
                    scores.append(0.0)
            out[day] = sum(scores) / len(scores) if scores else 100.0
        return out

    weekly_adherence_score = rolling_strict_adherence(7)
    monthly_adherence_score = rolling_strict_adherence(30)
    weekly_line_adherence_score = rolling_line_adherence(7)
    monthly_line_adherence_score = rolling_line_adherence(30)
    monthly_lot_plan_adherence_score = rolling_lot_plan_adherence(30)
    (
        forward_30d_coverage_rate,
        forward_30d_overproduction_rate,
        forward_30d_underproduction_by_line,
        forward_30d_overproduction_by_line,
    ) = forward_line_variance_rates(30)
    net_delay_catchup_30d_rate, net_delay_catchup_30d_qty = net_delay_catchup_rate(30)
    reference_gap_rate_avg = {
        day: (
            reference_gap_rate_sum[day] / reference_active_line_count[day]
            if reference_active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    reference_coverage_rate_avg = {
        day: (
            reference_coverage_rate_sum[day] / reference_active_line_count[day]
            if reference_active_line_count[day] > 0
            else 100.0
        )
        for day in days
    }
    reference_overproduction_rate_avg = {
        day: (
            reference_overproduction_rate_sum[day] / reference_active_line_count[day]
            if reference_active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    reference_overproduction_rate_capped = {day: min(500.0, reference_overproduction_rate_avg[day]) for day in days}
    reference_strict_adherence_score = {
        day: max(0.0, 100.0 - reference_gap_rate_avg[day])
        for day in days
    }
    shortfall_line_count = {day: production_by_day[day].get("shortfall_line_count", 0.0) for day in days}
    under_plan_line_count = {day: production_by_day[day].get("under_plan_line_count", 0.0) for day in days}
    over_plan_line_count = {day: production_by_day[day].get("over_plan_line_count", 0.0) for day in days}
    capacity_line_count = {day: production_by_day[day].get("capacity_line_count", 0.0) for day in days}
    input_shortage_line_count = {day: production_by_day[day].get("input_shortage_line_count", 0.0) for day in days}
    weekly_lot_limit_line_count = {day: production_by_day[day].get("weekly_lot_limit_line_count", 0.0) for day in days}
    requested_lot_starts = {day: production_by_day[day].get("requested_lot_starts", 0.0) for day in days}
    actual_lot_starts = {day: production_by_day[day].get("actual_lot_starts", 0.0) for day in days}
    overproduction_qty = {day: production_by_day[day].get("overproduction_qty", 0.0) for day in days}
    shortfall_line_share = {
        day: (100.0 * shortfall_line_count[day] / active_line_count[day] if active_line_count[day] > 0 else 0.0)
        for day in days
    }
    under_plan_line_share = {
        day: (100.0 * under_plan_line_count[day] / active_line_count[day] if active_line_count[day] > 0 else 0.0)
        for day in days
    }
    over_plan_line_share = {
        day: (100.0 * over_plan_line_count[day] / active_line_count[day] if active_line_count[day] > 0 else 0.0)
        for day in days
    }
    capacity_line_share = {
        day: (100.0 * capacity_line_count[day] / active_line_count[day] if active_line_count[day] > 0 else 0.0)
        for day in days
    }
    input_shortage_line_share = {
        day: (100.0 * input_shortage_line_count[day] / active_line_count[day] if active_line_count[day] > 0 else 0.0)
        for day in days
    }
    weekly_lot_limit_line_share = {
        day: (100.0 * weekly_lot_limit_line_count[day] / active_line_count[day] if active_line_count[day] > 0 else 0.0)
        for day in days
    }
    constrained_line_share = {
        day: min(
            100.0,
            capacity_line_share[day] + input_shortage_line_share[day] + weekly_lot_limit_line_share[day],
        )
        for day in days
    }
    reference_under_line_share = {
        day: (
            100.0 * reference_under_line_count[day] / reference_active_line_count[day]
            if reference_active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    reference_over_line_share = {
        day: (
            100.0 * reference_over_line_count[day] / reference_active_line_count[day]
            if reference_active_line_count[day] > 0
            else 0.0
        )
        for day in days
    }
    startup_cutoff_days = 30
    startup_shortfall_qty = {
        day: shortfall_qty[day] if day < startup_cutoff_days else 0.0
        for day in days
    }
    operational_shortfall_qty = {
        day: 0.0 if day < startup_cutoff_days else shortfall_qty[day]
        for day in days
    }
    production_execution_score = monthly_line_adherence_score

    inventory_cost = {
        day: daily_by_day[day].get("holding_cost_day", 0.0)
        + daily_by_day[day].get("warehouse_operating_cost_day", 0.0)
        + daily_by_day[day].get("inventory_risk_cost_day", 0.0)
        for day in days
    }
    transport_cost_raw = {
        day: max(0.0, daily_by_day[day].get("operational_transport_cost_day", daily_by_day[day].get("transport_cost_day", 0.0)))
        for day in days
    }
    transport_cost = transport_cost_raw
    opening_transport_cost = {day: daily_by_day[day].get("opening_open_order_transport_cost_day", 0.0) for day in days}
    gross_transport_cost = {day: daily_by_day[day].get("transport_cost_day", 0.0) for day in days}
    purchase_cost = {
        day: max(0.0, daily_by_day[day].get("operational_purchase_cost_day", daily_by_day[day].get("purchase_cost_day", 0.0)))
        for day in days
    }
    production_cost = {
        day: max(0.0, daily_by_day[day].get("production_cost_day", 0.0))
        for day in days
    }
    opening_purchase_cost = {day: daily_by_day[day].get("opening_open_order_purchase_cost_day", 0.0) for day in days}
    logistics_cost = {day: inventory_cost[day] + transport_cost[day] for day in days}
    total_supply_cost = {
        day: (
            daily_by_day[day].get("total_supply_cost_day", 0.0)
            if daily_by_day[day].get("total_supply_cost_day", 0.0) > 1e-9
            else logistics_cost[day] + purchase_cost[day] + production_cost[day]
        )
        for day in days
    }
    positive_costs = [value for value in total_supply_cost.values() if value > 0]
    avg_total_supply_cost = sum(positive_costs) / len(positive_costs) if positive_costs else 1.0
    cost_index = {day: 100.0 * total_supply_cost[day] / avg_total_supply_cost for day in days}
    logistics_cost_index = {day: 100.0 * logistics_cost[day] / avg_total_supply_cost for day in days}
    inventory_cost_index = {day: 100.0 * inventory_cost[day] / avg_total_supply_cost for day in days}
    transport_cost_index = {day: 100.0 * transport_cost[day] / avg_total_supply_cost for day in days}
    purchase_cost_index = {day: 100.0 * purchase_cost[day] / avg_total_supply_cost for day in days}

    raw_material_stockout_flag = {day: 0.0 for day in days}
    for row in input_stock_rows:
        item_id = str(row.get("item_id") or "")
        if is_simulation_hidden_item(item_id):
            continue
        day = int(to_float(row.get("day")) or 0)
        if day not in raw_material_stockout_flag:
            continue
        stock_end = to_float(row.get("stock_end_of_day"))
        if stock_end is not None and not math.isnan(stock_end) and stock_end <= 1e-9:
            raw_material_stockout_flag[day] = 1.0

    raw_material_stockout_days_30d: dict[int, float] = {}
    for idx, day in enumerate(days):
        window = days[max(0, idx - 29): idx + 1]
        raw_material_stockout_days_30d[day] = float(sum(1 for wday in window if raw_material_stockout_flag.get(wday, 0.0) > 0.0))

    material_delay_sum_by_day: dict[int, float] = defaultdict(float)
    material_delay_count_by_day: dict[int, int] = defaultdict(int)
    for row in mrp_order_rows:
        item_id = str(row.get("item_id") or "")
        if is_simulation_hidden_item(item_id):
            continue
        effective_receipt = effective_order_receipt_day(row)
        planned_lead = planned_procurement_lead_days(row)
        effective_lead = effective_procurement_lead_days(row)
        if effective_receipt is None or planned_lead is None or effective_lead is None:
            continue
        delay = max(0.0, effective_lead - planned_lead)
        day = int(round(effective_receipt))
        if day not in daily_by_day and day not in production_by_day and day not in demand_by_day:
            continue
        material_delay_sum_by_day[day] += delay
        material_delay_count_by_day[day] += 1
    material_delay_days = {
        day: (
            material_delay_sum_by_day.get(day, 0.0) / material_delay_count_by_day.get(day, 0)
            if material_delay_count_by_day.get(day, 0) > 0
            else 0.0
        )
        for day in days
    }

    positive_inventory_costs = [value for value in inventory_cost.values() if value > 0.0]
    baseline_inventory_cost = (
        sum(positive_inventory_costs) / len(positive_inventory_costs)
        if positive_inventory_costs
        else 1.0
    )
    physics_kpi_definitions = tuple(
        KpiDefinition(
            name=definition.name,
            target=baseline_inventory_cost if definition.name == "inventory_cost" else definition.target,
            catastrophic_value=(
                max(baseline_inventory_cost * 3.0, baseline_inventory_cost + 1.0)
                if definition.name == "inventory_cost"
                else definition.catastrophic_value
            ),
            optimization=definition.optimization,
            multiplying_factor=definition.multiplying_factor,
        )
        for definition in DEFAULT_PHYSICS_KPI_DEFINITIONS
    )
    physics_actual_series = {
        "product_availability": {day: service_score[day] / 100.0 for day in days},
        "line_adherence": {day: monthly_lot_plan_adherence_score[day] / 100.0 for day in days},
        "line_nervousness": line_nervousness,
        "production_replanning_count": production_replanning_count,
        "raw_material_stockout_days": raw_material_stockout_days_30d,
        "material_delay_days": material_delay_days,
        "inventory_cost": inventory_cost,
    }
    physics_kpi_rows = compute_kpi_rows(days, physics_actual_series, physics_kpi_definitions)
    physics_kpi_csv = daily_kpi_csv.parent / "physics_of_decision_kpi_daily.csv"
    if physics_kpi_rows:
        write_kpi_rows_csv(physics_kpi_rows, physics_kpi_csv)

    total_demand = sum(demand_qty.values())
    total_required = sum(required_qty.values())
    total_served = sum(served_qty.values())
    total_desired = sum(desired_qty.values())
    total_reference = sum(reference_qty.values())
    total_reference_covered = sum(reference_covered_qty.values())
    total_actual = sum(actual_qty.values())
    total_shortfall = sum(shortfall_qty.values())
    total_overproduction = sum(overproduction_qty.values())
    total_reference_shortfall = sum(reference_shortfall_qty.values())
    total_reference_overproduction = sum(reference_overproduction_qty.values())
    total_startup_shortfall = sum(startup_shortfall_qty.values())
    total_operational_shortfall = sum(operational_shortfall_qty.values())
    active_production_days = sum(1 for value in active_line_count.values() if value > 0)
    avg_execution_score = (
        sum(execution_score_avg[day] for day in days if active_line_count[day] > 0) / active_production_days
        if active_production_days
        else 100.0
    )
    all_active_lines = sum(active_line_count[day] for day in days if active_line_count[day] > 0)
    all_reference_active_lines = sum(reference_active_line_count[day] for day in days if reference_active_line_count[day] > 0)
    all_score_sum = sum(production_by_day[day].get("execution_score_sum", 0.0) for day in days)
    all_gap_score_sum = sum(production_by_day[day].get("plan_gap_rate_sum", 0.0) for day in days)
    all_under_lines = sum(under_plan_line_count[day] for day in days)
    all_over_lines = sum(over_plan_line_count[day] for day in days)
    avg_gap_score_all = (
        sum(reference_gap_rate_sum[day] for day in days) / all_reference_active_lines
        if all_reference_active_lines > 0
        else 0.0
    )
    strict_adherence_score_all = max(0.0, 100.0 - avg_gap_score_all)
    coverage_score_all = min(100.0, 100.0 * total_reference_covered / total_reference) if total_reference > 1e-9 else 100.0
    overproduction_share_all = 100.0 * total_reference_overproduction / total_reference if total_reference > 1e-9 else 0.0
    avg_forward_30d_underproduction = (
        sum(
            value
            for line_map in forward_30d_underproduction_by_line.values()
            for day, value in line_map.items()
            if active_line_count.get(day, 0.0) > 0
        )
        / max(
            1,
            sum(
                1
                for line_map in forward_30d_underproduction_by_line.values()
                for day in line_map
                if active_line_count.get(day, 0.0) > 0
            ),
        )
    )
    avg_forward_30d_coverage = (
        sum(forward_30d_coverage_rate[day] for day in days if active_line_count[day] > 0) / active_production_days
        if active_production_days
        else 100.0
    )
    avg_forward_30d_overproduction = (
        sum(forward_30d_overproduction_rate[day] for day in days if active_line_count[day] > 0) / active_production_days
        if active_production_days
        else 0.0
    )
    catchup_deficit_days = [day for day in days if net_delay_catchup_30d_qty.get(day, 0.0) > 1e-9]
    avg_net_delay_catchup_30d_rate = (
        sum(net_delay_catchup_30d_rate[day] for day in catchup_deficit_days) / len(catchup_deficit_days)
        if catchup_deficit_days
        else 100.0
    )
    avg_weekly_adherence = (
        sum(weekly_line_adherence_score[day] for day in days if active_line_count[day] > 0) / active_production_days
        if active_production_days
        else 100.0
    )
    avg_monthly_adherence = (
        sum(monthly_line_adherence_score[day] for day in days if active_line_count[day] > 0) / active_production_days
        if active_production_days
        else 100.0
    )
    under_plan_share_all = (
        100.0 * sum(reference_under_line_count[day] for day in days) / all_reference_active_lines
        if all_reference_active_lines > 0
        else 0.0
    )
    over_plan_share_all = (
        100.0 * sum(reference_over_line_count[day] for day in days) / all_reference_active_lines
        if all_reference_active_lines > 0
        else 0.0
    )
    post_startup_days = [day for day in days if day >= startup_cutoff_days and active_line_count[day] > 0]
    post_startup_active_lines = sum(active_line_count[day] for day in post_startup_days)
    post_startup_score_sum = sum(
        production_by_day[day].get("execution_score_sum", 0.0)
        for day in post_startup_days
    )
    post_startup_gap_score_sum = sum(
        production_by_day[day].get("plan_gap_rate_sum", 0.0)
        for day in post_startup_days
    )
    post_startup_under_lines = sum(under_plan_line_count[day] for day in post_startup_days)
    post_startup_over_lines = sum(over_plan_line_count[day] for day in post_startup_days)
    avg_execution_score_post_startup = (
        post_startup_score_sum / post_startup_active_lines
        if post_startup_active_lines > 0
        else avg_execution_score
    )
    avg_gap_score_post_startup = (
        post_startup_gap_score_sum / post_startup_active_lines
        if post_startup_active_lines > 0
        else 0.0
    )
    strict_adherence_score_post_startup = max(0.0, 100.0 - avg_gap_score_post_startup)
    under_plan_share_post_startup = (
        100.0 * post_startup_under_lines / post_startup_active_lines
        if post_startup_active_lines > 0
        else 0.0
    )
    over_plan_share_post_startup = (
        100.0 * post_startup_over_lines / post_startup_active_lines
        if post_startup_active_lines > 0
        else 0.0
    )
    backlog_days = sum(1 for value in backlog_qty.values() if value > 1e-9)
    shortfall_days = sum(1 for value in shortfall_qty.values() if value > 1e-9)
    operational_shortfall_days = sum(1 for value in operational_shortfall_qty.values() if value > 1e-9)
    input_shortage_days = sum(1 for day in days if production_by_day[day].get("input_shortage_day", 0.0) > 0)
    capacity_days = sum(1 for day in days if production_by_day[day].get("capacity_day", 0.0) > 0)
    weekly_lot_limit_days = sum(1 for day in days if production_by_day[day].get("weekly_lot_limit_day", 0.0) > 0)
    total_requested_lot_starts = sum(requested_lot_starts.values())
    total_actual_lot_starts = sum(actual_lot_starts.values())
    total_logistics_cost = sum(logistics_cost.values())
    total_supply_cost_value = sum(total_supply_cost.values())
    total_inventory_cost = sum(inventory_cost.values())
    total_transport_cost = sum(transport_cost.values())
    total_opening_transport_cost = sum(opening_transport_cost.values())
    total_purchase_cost = sum(purchase_cost.values())
    total_production_cost = sum(production_cost.values())
    total_opening_purchase_cost = sum(opening_purchase_cost.values())
    total_opening_cost = total_opening_transport_cost + total_opening_purchase_cost
    total_scenario_cost_excluding_external = (
        total_supply_cost_value + total_opening_cost
    )
    top_transport_day = max(days, key=lambda day: transport_cost.get(day, 0.0)) if days else None
    transport_spike_driver = "n/a"
    if top_transport_day is not None and mrp_order_rows and raw:
        node_type_by_id = {str(node.get("id") or ""): str(node.get("type") or "") for node in raw.get("nodes", []) or []}
        edge_by_id = {str(edge.get("id") or ""): edge for edge in raw.get("edges", []) or []}
        finished_good_item_ids: set[str] = set()
        for edge in raw.get("edges", []) or []:
            if node_type_by_id.get(str(edge.get("to") or "")) != "customer":
                continue
            for edge_item_id in edge.get("items") or []:
                finished_good_item_ids.add(str(edge_item_id))
        production_lot_reference_qty_by_pair: dict[tuple[str, str], float] = {}
        for node in raw.get("nodes", []) or []:
            node_id = str(node.get("id") or "")
            for proc in node.get("processes") or []:
                lot_sizing = proc.get("lot_sizing") or {}
                ref_qty = 0.0
                for key in ("fixed_lot_qty", "max_lot_qty", "min_lot_qty", "lot_multiple_qty"):
                    ref_qty = max(0.0, to_float(lot_sizing.get(key)) or 0.0)
                    if ref_qty > 1e-9:
                        break
                if ref_qty <= 1e-9:
                    continue
                for out in proc.get("outputs") or []:
                    out_item_id = str((out or {}).get("item_id") or "")
                    if out_item_id:
                        production_lot_reference_qty_by_pair[(node_id, out_item_id)] = max(
                            production_lot_reference_qty_by_pair.get((node_id, out_item_id), 0.0),
                            ref_qty,
                        )
        driver_rows: list[tuple[float, dict[str, str], dict[str, Any]]] = []
        for row in mrp_order_rows:
            if str(row.get("order_type") or "") != "lane_release":
                continue
            release_day = int(to_float(row.get("release_day")) or 0)
            if release_day != top_transport_day:
                continue
            edge = edge_by_id.get(str(row.get("edge_id") or "")) or {}
            explicit_transport = max(0.0, to_float(((edge.get("transport_cost") or {}).get("value"))) or 0.0)
            distance_km = max(0.0, to_float(edge.get("distance_km")) or 0.0)
            unit_transport = explicit_transport if explicit_transport > 0 else max(0.02, distance_km * 0.00008)
            item_id = str(row.get("item_id") or "")
            release_qty = max(0.0, to_float(row.get("release_qty")) or 0.0)
            receipt_qty = max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
            standard_order_qty = max(0.0, to_float(row.get("standard_order_qty")) or display_standard_order_qty(edge))
            if item_id not in finished_good_item_ids and standard_order_qty > 1e-9:
                effective_lot_qty = standard_order_qty
                if effective_lot_qty <= 1.0 + 1e-9:
                    effective_lot_qty = max(
                        effective_lot_qty,
                        production_lot_reference_qty_by_pair.get((str(row.get("src_node_id") or ""), item_id), 0.0),
                    )
                cost_qty = release_qty / effective_lot_qty
            else:
                cost_qty = receipt_qty
            driver_rows.append((cost_qty * unit_transport, row, edge))
        if driver_rows:
            raw_cost, row, edge = max(driver_rows, key=lambda item: item[0])
            attrs = edge.get("attrs") or {}
            item_id = str(row.get("item_id") or "")
            standard_order_qty = max(0.0, to_float(row.get("standard_order_qty")) or display_standard_order_qty(edge))
            display_lot_qty = standard_order_qty
            if item_id not in finished_good_item_ids and display_lot_qty <= 1.0 + 1e-9:
                display_lot_qty = max(
                    display_lot_qty,
                    production_lot_reference_qty_by_pair.get((str(row.get("src_node_id") or ""), item_id), 0.0),
                )
            cost_basis = "lot" if item_id not in finished_good_item_ids and display_lot_qty > 1e-9 else "unite"
            transport_spike_driver = (
                f"J{top_transport_day}: {compact_item_label(item_id)} "
                f"{fmt_qty(row.get('planned_receipt_qty'), 0)} via {row.get('src_node_id') or 'n/a'} -> "
                f"{row.get('dst_node_id') or 'n/a'} ; cout par {cost_basis} ; "
                f"lot std {fmt_qty(display_lot_qty, 0)} ; "
                f"source {attrs.get('source_workbook') or 'n/a'}"
            )

    def summary(label: str, value: str) -> dict[str, str]:
        return {"label": label, "value": value}

    def cost_share(value: float, total: float = total_supply_cost_value) -> str:
        if total <= 1e-9:
            return "0.0%"
        return fmt_pct(100.0 * value / total)

    line_palette = ["#0f766e", "#2563eb", "#d97706", "#7c3aed", "#0891b2", "#be123c"]
    delay_deficit_line_series = []
    overproduction_line_series = []
    for idx, line_key in enumerate(line_keys):
        line_label = production_line_display_label(line_key)
        color = line_palette[idx % len(line_palette)]
        delay_deficit_line_series.append(
            {
                "label": f"Retard/deficit production {line_label}",
                **series_from_map(forward_30d_underproduction_by_line.get(line_key, {})),
                "color": color,
                "dash": "dot",
            }
        )
        overproduction_line_series.append(
            {
                "label": f"Avance/exces production {line_label}",
                **series_from_map(forward_30d_overproduction_by_line.get(line_key, {})),
                "color": color,
                "dash": "solid",
            }
        )

    kpi_definitions = [
        {
            "family": "Disponibilite produit",
            "level": "KPI principal",
            "name": "Disponibilite produit",
            "formula": "100 x Servi(t) / Besoin_avec_backlog(t), plafonne a 100",
            "terms": "Servi(t)=served_qty client. Besoin_avec_backlog(t)=required_with_backlog_qty=demande du jour + backlog entrant.",
            "interpretation": "Mesure la capacite a servir le besoin patient. Objectif: 100% et backlog nul.",
        },
        {
            "family": "Disponibilite produit",
            "level": "KPI secondaire",
            "name": "Demande",
            "formula": "Somme des demandes client du jour",
            "terms": "Demande=Σ demand_qty sur les clients et produits finis.",
            "interpretation": "Besoin brut client, sans rattrapage du retard passe.",
        },
        {
            "family": "Disponibilite produit",
            "level": "KPI secondaire",
            "name": "Besoin avec backlog",
            "formula": "Demande du jour + backlog restant a servir",
            "terms": "Besoin_avec_backlog=Σ required_with_backlog_qty. Backlog entrant=retard non servi des jours precedents.",
            "interpretation": "Charge totale a satisfaire pour revenir au service complet.",
        },
        {
            "family": "Disponibilite produit",
            "level": "KPI secondaire",
            "name": "Servi",
            "formula": "Quantite effectivement livree au client",
            "terms": "Servi=Σ served_qty, limite par le stock disponible au point client.",
            "interpretation": "Flux client reellement couvert par les stocks disponibles.",
        },
        {
            "family": "Disponibilite produit",
            "level": "KPI secondaire",
            "name": "Backlog fin de jour",
            "formula": "max(0, Besoin_avec_backlog(t) - Servi(t))",
            "terms": "Backlog fin de jour=Σ backlog_end_qty apres service client.",
            "interpretation": "Reste a servir en fin de jour. C'est le signal de rupture patient.",
        },
        {
            "family": "Production",
            "level": "KPI principal",
            "name": "Adherence lignes mensuelle",
            "formula": "Moyenne lignes de max(0, 100 - |Production_30j - Reference_30j| / Reference_30j x 100)",
            "terms": "Ligne=couple site/produit. Production_30j=Σ actual_qty sur 30 jours. Reference_jour: PF=demande client du produit; semi-fini/intermediaire=quantite consommee par les sites aval dans production_input_consumption_daily.csv; sinon fallback=desired_qty, c.-a-d. besoin de production demande par le simulateur. Reference_30j=Σ Reference_jour sur 30 jours.",
            "interpretation": "Adherence mensuelle par site/produit, calculee ligne par ligne pour ne pas melanger UN et G.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Adherence plan lotifiee mensuelle",
            "formula": "Moyenne lignes de max(0, 100 - |Production_reelle_30j - Plan_lotifie_30j| / Plan_lotifie_30j x 100)",
            "terms": "Plan_lotifie=planned_qty_after_lot_rule; Production_reelle=actual_qty. Calcule par ligne site/produit sur 30 jours.",
            "interpretation": "Mesure l'execution du plan industriel deja lotifie. C'est la reference retenue par la surcouche Physics of Decision pour eviter de penaliser artificiellement les campagnes pharma.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Adherence lignes hebdo",
            "formula": "Moyenne lignes de max(0, 100 - |Production_7j - Reference_7j| / Reference_7j x 100)",
            "terms": "Production_7j=Σ actual_qty sur 7 jours. Reference_7j=Σ Reference_jour sur 7 jours, avec PF=demande client, semi-fini/intermediaire=consommation aval observee, fallback=desired_qty si l'aval direct n'est pas observable.",
            "interpretation": "Vision plus nerveuse que le mensuel, utile pour detecter des decalages court terme.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Alignement quotidien strict lots vs reference aval",
            "formula": "100 - moyenne lignes min(100, |Production_jour - Reference_jour| / Reference_jour x 100)",
            "terms": "Production_jour=actual_qty. Reference_jour=demande client pour PF, consommation aval observee pour semi-finis/intermediaires, puis fallback desired_qty si l'aval n'est pas observable. Lignes sans reference active exclues.",
            "interpretation": "Tres strict; penalise fortement les lots. A lire comme nervosite journaliere face a la reference aval, pas comme performance seule.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Couverture demande horizon 30j",
            "formula": "Moyenne lignes min(100, Production_30j_prospectif / Reference_30j_prospectif x 100)",
            "terms": "Calculee par ligne site/produit sur J..J+29, puis moyennee. Reference=demande client pour PF, consommation aval pour semi-finis/intermediaires, fallback desired_qty.",
            "interpretation": "Lecture simple: 100% signifie que la demande de l'horizon est couverte; sous 100%, il y a un retard/deficit sur l'horizon.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Retard/deficit de production par ligne",
            "formula": "max(0, Reference_30j_prospectif - Production_30j_prospectif) / Reference_30j_prospectif x 100",
            "terms": "Calcule par ligne site/produit sur J..J+29. Reference=demande client pour PF, consommation aval pour semi-finis/intermediaires, fallback desired_qty.",
            "interpretation": "Montre les lignes qui ne couvrent pas encore leur demande sur l'horizon de campagne. Si c'est rattrape ensuite, c'est un retard; sinon c'est un deficit definitif.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Taux de rattrapage retard net 30j",
            "formula": "Si Retard_net_J > 0: 100 x (Retard_net_J - min(Retard_net_J+1..J+30)) / Retard_net_J",
            "terms": "Retard_net=max(0, cumul Reference - cumul Production) par ligne site/produit. L'avance de production cumulee est consommee avant de compter un retard. Les lignes sans retard net sont exclues du denominateur.",
            "interpretation": "Indique si un vrai retard cumule est reduit dans les 30 jours suivants. Plus robuste qu'un deficit journalier brut pour une production par lots.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Avance/exces de production par ligne",
            "formula": "Moyenne lignes max(0, Production_30j_prospectif - Reference_30j_prospectif) / Reference_30j_prospectif x 100, affichage plafonne a 500%",
            "terms": "Production_30j_prospectif=production de la ligne sur J..J+29. Reference_30j_prospectif=demande aval correspondante sur J..J+29.",
            "interpretation": "Mesure l'avance ou l'exces de production sur l'horizon couvert par une campagne. Evite de comparer un lot complet a la seule demande du jour.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Ecart moyen a la reference journaliere",
            "formula": "Moyenne lignes min(100, |Production_jour - Reference_jour| / Reference_jour x 100)",
            "terms": "Production_jour=actual_qty. Reference_jour=demande aval pertinente. Ecart plafonne a 100% par ligne avant moyenne.",
            "interpretation": "Ecart strict au jour. Complement de l'alignement quotidien.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Part lignes sous-plan",
            "formula": "100 x nombre de lignes avec Production_jour < Reference_jour / lignes avec reference active",
            "terms": "Reference_jour=demande client, consommation aval observee ou fallback desired_qty. Sous-plan=actual_qty < Reference_jour.",
            "interpretation": "Detecte les lignes qui ne couvrent pas la reference aval du jour.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Part lignes sur-plan >5%",
            "formula": "100 x nombre de lignes avec Production_jour > 105% de Reference_jour / lignes avec reference active",
            "terms": "Sur-plan >5%=actual_qty > 1.05 x Reference_jour.",
            "interpretation": "Detecte les jours ou la production depasse fortement la reference aval, souvent a cause des lots.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Part lignes contraintes capacite",
            "formula": "100 x lignes dont binding_cause = capacity / lignes actives",
            "terms": "binding_cause vient de production_constraint_daily.csv. capacity signifie limite par une capacite modelisee.",
            "interpretation": "Part de production limitee par une capacite modelisee.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Part lignes input shortage",
            "formula": "100 x lignes dont binding_cause = input_shortage / lignes actives",
            "terms": "input_shortage signifie que la production demandee n'a pas pu etre executee faute de composant disponible.",
            "interpretation": "Part de production limitee par manque de composant.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Part lignes bloquees lots/semaine",
            "formula": "100 x lignes dont binding_cause = weekly_lot_limit / lignes actives",
            "terms": "weekly_lot_limit signifie que la ligne est limitee par la regle max lots/semaine.",
            "interpretation": "Part de production limitee par la regle max lots/semaine.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI principal",
            "name": "Pression cout supply",
            "formula": "100 x (Cout_stock(t) + Cout_transport(t) + Cout_achat(t) + Cout_production(t)) / moyenne_run(Cout_total_operationnel)",
            "terms": "Cout_stock=holding_cost + warehouse_operating_cost + inventory_risk_cost. Cout_transport=transport operationnel des commandes du scenario, hors carnet initial. Cout_achat=cout d'achat matiere/fournisseur. Cout_production=cout de conversion alloue sur la production reelle. moyenne_run=moyenne des jours avec cout total operationnel positif.",
            "interpretation": "Indice base 100. Au-dessus de 100, la journee coute plus cher que la moyenne du scenario.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution cout d'achat matiere - indice",
            "formula": "100 x Cout_achat(t) / moyenne_run(Cout_total_operationnel)",
            "terms": "Cout_achat=operational_purchase_cost_day, c.-a-d. cout d'achat des matieres/fournisseurs sur les flux commandes par la politique simulee, hors carnet initial deja engage.",
            "interpretation": "Part de la pression cout due au cout d'achat des matieres/fournisseurs.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution cout de production - indice",
            "formula": "100 x Cout_production(t) / moyenne_run(Cout_total_operationnel)",
            "terms": "Cout_production=production_cost_day, proxy de cout de conversion pharma: fabrication, main-d'oeuvre, utilites, qualite, nettoyage, maintenance et depreciation.",
            "interpretation": "Part de la pression cout due aux operations de fabrication, separee des achats matieres.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution stock - indice",
            "formula": "100 x Cout_stock(t) / moyenne_run(Cout_total_pilotable)",
            "terms": "Cout_stock=holding_cost_day + warehouse_operating_cost_day + inventory_risk_cost_day.",
            "interpretation": "Part de la pression cout due au stock: immobilisation, stockage, risque inventaire.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution transport pilotable - indice",
            "formula": "100 x Cout_transport_pilotable(t) / moyenne_run(Cout_total_pilotable)",
            "terms": "Cout_transport_pilotable exclut le transport du carnet initial deja engage.",
            "interpretation": "Part de la pression cout due aux flux transport decidables par la politique simulee.",
        },
        {
            "family": "Couts stock / transport",
            "level": "Definition",
            "name": "Pilotable",
            "formula": "Flux/cout genere par les decisions de reapprovisionnement du scenario, hors carnet initial",
            "terms": "Exemple pilotable: une commande MRP lancee pendant la simulation. Exemple non pilotable: open order deja en transit au 01/01.",
            "interpretation": "Pilotable signifie que le KPI peut changer si on change la politique supply. Le carnet initial est affiche a part car il est deja engage au demarrage.",
        },
    ]
    kpi_definitions.extend(
        [
            {
                "family": "Production",
                "level": "KPI secondaire",
                "name": "Contraintes sur ligne",
                "formula": "Part des lignes avec binding_cause capacity, input_shortage ou weekly_lot_limit",
                "terms": "Calcule sur les lignes actives du jour et plafonne a 100%.",
                "interpretation": "Si ce signal est nul, les ecarts de production viennent surtout des tailles de lots/campagnes, pas d'un blocage operationnel.",
            },
            {
                "family": "Couts supply",
                "level": "KPI principal",
                "name": "Cout supply operationnel",
                "formula": "Indice base 100 du cout operationnel journalier total",
                "terms": "Cout operationnel = cout d'achat matiere + cout de production + cout stock + cout de transport. Les montants reels sont affiches dans les KPI secondaires.",
                "interpretation": "Permet de voir les jours plus chers que la moyenne du scenario, tout en gardant le detail en euros/quantite dans les secondaires.",
            },
            {
                "family": "Couts supply",
                "level": "KPI secondaire",
                "name": "Cout d'achat matiere",
                "formula": "operational_purchase_cost_day",
                "terms": "Cout d'achat matiere/fournisseur declenche par les commandes du scenario, hors carnet initial deja engage.",
                "interpretation": "Driver economique principal quand les prix matiere dominent.",
            },
            {
                "family": "Couts supply",
                "level": "KPI secondaire",
                "name": "Cout de production",
                "formula": "production_cost_day",
                "terms": "Proxy de cout de conversion pharma alloue aux quantites reellement produites. La repartition standard est parametrable par ligne: medicament gelule, creme dermato, semi-fini/extraction.",
                "interpretation": "Isole le cout industriel de fabrication, distinct des achats matieres.",
            },
            {
                "family": "Couts supply",
                "level": "KPI secondaire",
                "name": "Cout stock",
                "formula": "holding_cost_day + warehouse_operating_cost_day + inventory_risk_cost_day",
                "terms": "Immobilisation, stockage operationnel et risque inventaire.",
                "interpretation": "Montre le prix paye pour maintenir plus de couverture et securiser la production.",
            },
            {
                "family": "Couts supply",
                "level": "KPI secondaire",
                "name": "Cout de transport pilotable",
                "formula": "operational_transport_cost_day",
                "terms": "Transport des commandes simulees, hors carnet initial deja engage.",
                "interpretation": "Montre si la politique cree des expeditions couteuses ou concentrees.",
            },
        ]
    )
    visible_definition_names = {
        "Disponibilite produit",
        "Demande",
        "Besoin avec backlog",
        "Servi",
        "Backlog fin de jour",
        "Adherence lignes mensuelle",
        "Adherence plan lotifiee mensuelle",
        "Couverture demande horizon 30j",
        "Retard/deficit de production par ligne",
        "Taux de rattrapage retard net 30j",
        "Avance/exces de production par ligne",
        "Contraintes sur ligne",
        "Cout supply operationnel",
        "Cout d'achat matiere",
        "Cout de production",
        "Cout stock",
        "Cout de transport pilotable",
        "Pilotable",
    }

    physics_kpi_display = [
        ("product_availability", "Disponibilite produit", "#0f766e", "served_qty / required_with_backlog_qty"),
        ("line_adherence", "Adherence plan lotifie", "#2563eb", "actual_qty vs planned_qty_after_lot_rule, moyenne glissante 30j"),
        ("line_nervousness", "Nervosite lignes", "#d97706", "Variation moyenne journaliere du plan par ligne (%)"),
        ("production_replanning_count", "Replanifications production", "#7c3aed", "Nombre de lignes dont le plan change vs jour precedent"),
        ("raw_material_stockout_days", "Jours rupture MP 30j", "#dc2626", "Nombre de jours avec rupture MP dans la fenetre glissante 30j"),
        ("material_delay_days", "Retard matiere", "#0891b2", "Moyenne des retards reception: delai effectif - delai previsionnel"),
        ("inventory_cost", "Cout stock", "#be123c", "Cout stock journalier; cible=cout stock moyen baseline"),
    ]
    physics_label_by_name = {name: label for name, label, _color, _source in physics_kpi_display}
    physics_color_by_name = {name: color for name, _label, color, _source in physics_kpi_display}
    physics_source_by_name = {name: source for name, _label, _color, source in physics_kpi_display}
    physics_rows_by_day = {int(row.get("day") or 0): row for row in physics_kpi_rows}

    def physics_row_values(field: str, *, scale: float = 1.0) -> list[float]:
        return [
            round(float(to_float(physics_rows_by_day.get(day, {}).get(field)) or 0.0) * scale, 6)
            for day in days
        ]

    physics_factor_by_name = {
        definition.name: max(0.0, float(definition.multiplying_factor))
        for definition in physics_kpi_definitions
    }

    def physics_weighted_term_values(name: str) -> list[float]:
        factor = physics_factor_by_name.get(name, 1.0)
        return [
            round(
                (factor * float(to_float(physics_rows_by_day.get(day, {}).get(f"{name}__distance")) or 0.0)) ** 2,
                10,
            )
            for day in days
        ]

    physics_distance_series = [
        {
            "id": name,
            "label": label,
            "values": physics_row_values(f"{name}__distance"),
            "color": physics_color_by_name[name],
        }
        for name, label, _color, _source in physics_kpi_display
    ]
    physics_contribution_series = [
        {
            "id": name,
            "label": label,
            "values": physics_row_values(f"{name}__contribution", scale=100.0),
            "color": physics_color_by_name[name],
        }
        for name, label, _color, _source in physics_kpi_display
    ]
    physics_weighted_term_series = [
        {
            "id": name,
            "label": label,
            "values": physics_weighted_term_values(name),
            "color": physics_color_by_name[name],
        }
        for name, label, _color, _source in physics_kpi_display
    ]
    physics_weighted_term_total = {
        series["id"]: sum(float(value) for value in series["values"])
        for series in physics_weighted_term_series
    }
    total_physics_weighted_term = sum(physics_weighted_term_total.values())
    latest_physics_row = physics_kpi_rows[-1] if physics_kpi_rows else {}
    physics_contributors = []
    for definition in physics_kpi_definitions:
        name = definition.name
        distances = [float(to_float(row.get(f"{name}__distance")) or 0.0) for row in physics_kpi_rows]
        contributions = [float(to_float(row.get(f"{name}__contribution")) or 0.0) for row in physics_kpi_rows]
        weighted_term_total = physics_weighted_term_total.get(name, 0.0)
        physics_contributors.append(
            {
                "id": name,
                "label": physics_label_by_name.get(name, name),
                "avg_distance": round(sum(distances) / len(distances), 6) if distances else 0.0,
                "max_distance": round(max(distances), 6) if distances else 0.0,
                "avg_contribution_pct": round(100.0 * sum(contributions) / len(contributions), 6) if contributions else 0.0,
                "impact_share_pct": (
                    round(100.0 * weighted_term_total / total_physics_weighted_term, 6)
                    if total_physics_weighted_term > 1e-12
                    else 0.0
                ),
                "weighted_term_total": round(weighted_term_total, 6),
                "latest_distance": round(float(to_float(latest_physics_row.get(f"{name}__distance")) or 0.0), 6),
                "latest_actual": round(float(to_float(latest_physics_row.get(f"{name}__actual")) or 0.0), 6),
                "target": round(float(definition.target), 6),
                "catastrophic_value": round(float(definition.catastrophic_value), 6),
                "optimization": definition.optimization,
                "multiplying_factor": round(float(definition.multiplying_factor), 6),
                "source": physics_source_by_name.get(name, ""),
            }
        )
    physics_contributors.sort(key=lambda row: (row["impact_share_pct"], row["max_distance"]), reverse=True)
    avg_physics_global = (
        sum(float(to_float(row.get("global_score")) or 0.0) for row in physics_kpi_rows) / len(physics_kpi_rows)
        if physics_kpi_rows
        else 0.0
    )
    max_physics_global = max((float(to_float(row.get("global_score")) or 0.0) for row in physics_kpi_rows), default=0.0)
    physics_payload = {
        "kind": "physics_kpi",
        "title": "Physics of Decision - trajectoire KPI",
        "subtitle": "Distances normalisees: 0 = cible atteinte, 1 = catastrophe. Score global = aggregation euclidienne ponderee.",
        "csv_path": str(physics_kpi_csv),
        "startup_cutoff_day": None,
        "days": days,
        "main": {
            "series": [
                {
                    "id": "global_score",
                    "label": "Derive globale normalisee",
                    "values": physics_row_values("global_score"),
                    "color": "#111827",
                },
            ],
            "y_label": "Distance normalisee",
        },
        "distance_series": physics_distance_series,
        "contribution_series": physics_contribution_series,
        "weighted_term_series": physics_weighted_term_series,
        "contributors": physics_contributors,
        "summary": [
            summary("Score derive moyen", f"{avg_physics_global:.3f}"),
            summary("Score derive max", f"{max_physics_global:.3f}"),
            summary("Lecture", "0=cible ; 1=catastrophe"),
            summary("Top contributeur", physics_contributors[0]["label"] if physics_contributors else "n/a"),
            summary("Table generee", str(physics_kpi_csv.name)),
        ],
        "definitions": [
            {
                "id": definition.name,
                "label": physics_label_by_name.get(definition.name, definition.name),
                "target": round(float(definition.target), 6),
                "catastrophic_value": round(float(definition.catastrophic_value), 6),
                "optimization": definition.optimization,
                "multiplying_factor": round(float(definition.multiplying_factor), 6),
                "source": physics_source_by_name.get(definition.name, ""),
            }
            for definition in physics_kpi_definitions
        ],
    }
    kpi_definitions.extend(
        [
            {
                "family": "Physics of Decision",
                "level": "KPI distance",
                "name": physics_label_by_name.get(definition.name, definition.name),
                "formula": (
                    "d=(target-actual)/(target-catastrophic) si higher_is_better ; "
                    "d=(actual-target)/(catastrophic-target) si lower_is_better ; d borne entre 0 et 1"
                ),
                "terms": (
                    f"target={definition.target:.6g} ; catastrophe={definition.catastrophic_value:.6g} ; "
                    f"sens={definition.optimization} ; mf={definition.multiplying_factor:.3g} ; "
                    f"source={physics_source_by_name.get(definition.name, 'n/a')}"
                ),
                "interpretation": (
                    "Distance normalisee a la cible. Le score global est sqrt(sum((mf_i*d_i)^2)/sum(mf_i^2))."
                ),
            }
            for definition in physics_kpi_definitions
        ]
    )

    return {
        "kind": "kpi_tree",
        "title": "Arborescence KPI management supply",
        "subtitle": "Clique une courbe KPI principale pour afficher ses KPI secondaires. Le bouton Physics of Decision bascule vers les distances normalisees.",
        "definitions": [
            definition
            for definition in kpi_definitions
            if str(definition.get("name") or "") in visible_definition_names
            or str(definition.get("family") or "") == "Physics of Decision"
        ],
        "physics": physics_payload,
        "main": {
            "days": days,
            "series": [
                {
                    "id": "availability",
                    "label": "Disponibilite produit",
                    "values": [round(service_score[day], 6) for day in days],
                    "color": "#0f766e",
                    "note": "Score service journalier plafonne: servi / besoin avec backlog. Objectif: 100% et backlog quotidien nul.",
                },
                {
                    "id": "production",
                    "label": "Adherence lignes mensuelle",
                    "values": [round(production_execution_score[day], 6) for day in days],
                    "color": "#2563eb",
                    "note": "Adherence mensuelle par ligne produit/site. Les secondaires affichent couverture, retard/deficit, avance/exces et contraintes sur ligne.",
                },
                {
                    "id": "cost",
                    "label": "Cout supply operationnel",
                    "values": [round(cost_index[day], 6) for day in days],
                    "color": "#d97706",
                    "note": "Indice journalier base 100 du cout operationnel. Les secondaires affichent les montants achat, production, stock et transport par jour.",
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
                    summary("Service besoin+backlog", fmt_pct(100.0 * total_served / total_required if total_required else 100.0)),
                    summary("Jours avec backlog", str(backlog_days)),
                    summary("Backlog max", fmt_qty(max(backlog_qty.values()) if backlog_qty else 0.0)),
                    summary("Besoin cumule", fmt_qty(total_required)),
                ],
                "secondary": [
                    {"label": "Demande", **series_from_map(demand_qty), "color": "#475569"},
                    {"label": "Besoin avec backlog", **series_from_map(required_qty), "color": "#64748b"},
                    {"label": "Servi", **series_from_map(served_qty), "color": "#0f766e"},
                    {"label": "Backlog fin de jour", **series_from_map(backlog_qty), "color": "#dc2626"},
                ],
                "secondary_y_label": "Quantite",
            },
            {
                "id": "production",
                "label": "Adherence lignes mensuelle usine",
                "objective": "Reduire la nervosite usine et les replanifications dues aux ruptures composants.",
                "summary": [
                    summary("Adherence lignes mensuelle", fmt_pct(avg_monthly_adherence)),
                    summary("Couverture demande horizon 30j", fmt_pct(avg_forward_30d_coverage)),
                    summary("Retard/deficit horizon 30j", fmt_pct(avg_forward_30d_underproduction)),
                    summary("Rattrapage retard net 30j", fmt_pct(avg_net_delay_catchup_30d_rate)),
                    summary("Avance/exces horizon 30j", fmt_pct(avg_forward_30d_overproduction)),
                    summary("Reference aval cumulee", fmt_qty(total_reference)),
                    summary("Manque vs demande", fmt_qty(total_reference_shortfall)),
                    summary("Avance/exces journalier brut", fmt_qty(total_reference_overproduction)),
                    summary("Jours avec manque", str(shortfall_days)),
                    summary("Jours input shortage", str(input_shortage_days)),
                    summary("Jours capacite bloquante", str(capacity_days)),
                    summary("Jours limite lots/semaine", str(weekly_lot_limit_days)),
                    summary("Lots demandes / lances", f"{fmt_qty(total_requested_lot_starts, 0)} / {fmt_qty(total_actual_lot_starts, 0)}"),
                ],
                "secondary": [
                    {"label": "Adherence lignes mensuelle (%)", **series_from_map(monthly_line_adherence_score), "color": "#2563eb"},
                    {"label": "Adherence plan lotifie mensuelle (%)", **series_from_map(monthly_lot_plan_adherence_score), "color": "#65a30d", "dash": "dash"},
                    {"label": "Couverture demande horizon 30j (%)", **series_from_map(forward_30d_coverage_rate), "color": "#0f766e"},
                    {"label": "Taux de rattrapage retard net 30j (%)", **series_from_map(net_delay_catchup_30d_rate), "color": "#0891b2"},
                    *delay_deficit_line_series,
                    *overproduction_line_series,
                    {"label": "Contraintes sur ligne capacite / input / lots semaine (%)", **series_from_map(constrained_line_share), "color": "#dc2626"},
                ],
                "secondary_y_label": "%",
            },
            {
                "id": "cost",
                "label": "Couts supply",
                "objective": "Comprendre le cout operationnel: achat matiere, production, stock et transport.",
                "summary": [
                    summary("Cout operationnel total", fmt_qty(total_supply_cost_value)),
                    summary("Cout d'achat matiere", f"{fmt_qty(total_purchase_cost)} ({cost_share(total_purchase_cost)})"),
                    summary("Cout de production", f"{fmt_qty(total_production_cost)} ({cost_share(total_production_cost)})"),
                    summary("Cout stock", f"{fmt_qty(total_inventory_cost)} ({cost_share(total_inventory_cost)})"),
                    summary("Cout de transport pilotable", f"{fmt_qty(total_transport_cost)} ({cost_share(total_transport_cost)})"),
                    summary("Carnet initial deja engage", fmt_qty(total_opening_cost)),
                    summary("Cout total scenario", fmt_qty(total_scenario_cost_excluding_external)),
                    summary("Principal pic transport", transport_spike_driver),
                ],
                "secondary": [
                    {"label": "Cout operationnel total", **series_from_map(total_supply_cost), "color": "#d97706"},
                    {"label": "Cout d'achat matiere", **series_from_map(purchase_cost), "color": "#0f766e"},
                    {"label": "Cout de production", **series_from_map(production_cost), "color": "#be123c"},
                    {"label": "Cout stock", **series_from_map(inventory_cost), "color": "#7c3aed"},
                    {"label": "Cout de transport pilotable", **series_from_map(transport_cost), "color": "#f97316"},
                ],
                "secondary_y_label": "Cout / jour",
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
    sim_dc_stocks_csv: Path | None = None,
    supplier_shipments_csv: Path,
    safety_reference_csv: Path | None = None,
) -> list[dict[str, Any]]:
    item_labels = build_item_label_lookup(raw)
    node_type_by_id = build_node_type_lookup(raw)
    demand_rows = read_csv_rows(demand_service_csv)
    input_rows = read_csv_rows(sim_input_stocks_csv)
    output_rows = read_csv_rows(sim_output_products_csv)
    dc_stock_rows = read_csv_rows(sim_dc_stocks_csv) if sim_dc_stocks_csv else []
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
            for dataset in (demand_rows, input_rows, output_rows, dc_stock_rows, shipment_rows)
            for row in dataset
        ]
        or [0]
    )
    sim_days = max(1, max_day + 1)
    year_count = max(1, int(math.ceil(sim_days / 365.0)))

    def year_for_day(day: int) -> int:
        return max(1, min(year_count, int(day // 365) + 1))

    def year_days(year: int) -> int:
        start_day = (year - 1) * 365
        if start_day >= sim_days:
            return 0
        return max(0, min(365, sim_days - start_day))

    def new_yearly_payload() -> dict[str, dict[str, float]]:
        return {
            str(year): {
                "days": float(year_days(year)),
                "planned_qty": 0.0,
                "delivered_qty": 0.0,
                "consumed_qty": 0.0,
                "initial_qty": 0.0,
                "final_stock_qty": 0.0,
            }
            for year in range(1, year_count + 1)
        }

    def ensure_yearly(row: dict[str, Any]) -> dict[str, dict[str, float]]:
        yearly = row.get("yearly")
        if not isinstance(yearly, dict):
            yearly = new_yearly_payload()
            row["yearly"] = yearly
        return yearly

    def add_yearly(row: dict[str, Any], year: int, field: str, value: float) -> None:
        yearly = ensure_yearly(row)
        bucket = yearly.setdefault(str(year), {"days": float(year_days(year))})
        bucket[field] = max(0.0, float(bucket.get(field, 0.0) or 0.0) + max(0.0, value))

    demand_total_by_item: dict[str, float] = defaultdict(float)
    served_total_by_item: dict[str, float] = defaultdict(float)
    demand_by_item_year: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    served_by_item_year: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in demand_rows:
        if str(row.get("node_id") or "") not in {
            node_id for node_id, node_type in node_type_by_id.items() if node_type == "customer"
        }:
            continue
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        year = year_for_day(day)
        demand_qty = max(0.0, to_float(row.get("demand_qty")) or 0.0)
        served_qty = max(0.0, to_float(row.get("served_qty")) or 0.0)
        demand_total_by_item[item_id] += max(0.0, to_float(row.get("demand_qty")) or 0.0)
        served_total_by_item[item_id] += max(0.0, to_float(row.get("served_qty")) or 0.0)
        demand_by_item_year[item_id][year] += demand_qty
        served_by_item_year[item_id][year] += served_qty

    produced_total_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    produced_by_pair_year: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    latest_output_stock_by_pair: dict[tuple[str, str], tuple[int, float]] = {}
    output_stock_end_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in output_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        year = year_for_day(day)
        produced_qty = max(0.0, to_float(row.get("produced_qty")) or 0.0)
        produced_total_by_pair[(node_id, item_id)] += produced_qty
        produced_by_pair_year[(node_id, item_id)][year] += produced_qty
        stock_value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        key = (node_id, item_id)
        output_stock_end_by_pair_day[key][day] = stock_value
        prev = latest_output_stock_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_output_stock_by_pair[key] = (day, stock_value)

    latest_input_stock_by_pair: dict[tuple[str, str], tuple[int, float]] = {}
    input_stock_before_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    input_stock_end_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        before_value = max(0.0, to_float(row.get("stock_before_production")) or 0.0)
        stock_value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        key = (node_id, item_id)
        input_stock_before_by_pair_day[key][day] = before_value
        input_stock_end_by_pair_day[key][day] = stock_value
        prev = latest_input_stock_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_input_stock_by_pair[key] = (day, stock_value)

    dc_stock_end_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in dc_stock_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        dc_stock_end_by_pair_day[(node_id, item_id)][day] = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)

    shipped_total_to_pair: dict[tuple[str, str], float] = defaultdict(float)
    shipped_total_from_pair: dict[tuple[str, str], float] = defaultdict(float)
    shipped_to_pair_year: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    shipped_from_pair_year: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in shipment_rows:
        src_node_id = str(row.get("src_node_id") or "")
        node_id = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        year = year_for_day(day)
        shipped_qty = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        shipped_total_to_pair[(node_id, item_id)] += shipped_qty
        shipped_to_pair_year[(node_id, item_id)][year] += shipped_qty
        if src_node_id:
            shipped_total_from_pair[(src_node_id, item_id)] += shipped_qty
            shipped_from_pair_year[(src_node_id, item_id)][year] += shipped_qty

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

    def start_stock_for_year(
        pair: tuple[str, str],
        year: int,
        *,
        initial_qty: float,
        before_by_pair_day: dict[tuple[str, str], dict[int, float]] | None = None,
        end_by_pair_day: dict[tuple[str, str], dict[int, float]] | None = None,
    ) -> float:
        start_day = (year - 1) * 365
        if before_by_pair_day:
            before_by_day = before_by_pair_day.get(pair, {})
            if start_day in before_by_day:
                return max(0.0, before_by_day[start_day])
        if start_day <= 0:
            return max(0.0, initial_qty)
        end_by_day = (end_by_pair_day or {}).get(pair, {})
        if (start_day - 1) in end_by_day:
            return max(0.0, end_by_day[start_day - 1])
        previous_days = [day for day in end_by_day if day < start_day]
        if previous_days:
            return max(0.0, end_by_day[max(previous_days)])
        return max(0.0, initial_qty)

    def end_stock_for_year(
        pair: tuple[str, str],
        year: int,
        *,
        fallback_qty: float,
        end_by_pair_day: dict[tuple[str, str], dict[int, float]] | None = None,
    ) -> float:
        end_day = min(sim_days - 1, year * 365 - 1)
        end_by_day = (end_by_pair_day or {}).get(pair, {})
        if end_day in end_by_day:
            return max(0.0, end_by_day[end_day])
        previous_days = [day for day in end_by_day if day <= end_day]
        if previous_days:
            return max(0.0, end_by_day[max(previous_days)])
        return max(0.0, fallback_qty)

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
                            "yearly": new_yearly_payload(),
                        },
                    )
                    bucket["planned_qty"] += need_qty
                    bucket["consumed_qty"] += consumed_qty
                    for year in range(1, year_count + 1):
                        year_demand_qty = demand_by_item_year[out_item].get(year, 0.0)
                        year_produced_qty = produced_by_pair_year[(node_id, out_item)].get(year, 0.0)
                        add_yearly(
                            bucket,
                            year,
                            "planned_qty",
                            convert_unit_quantity((ratio_qty / batch_size) * year_demand_qty, ratio_unit, unit),
                        )
                        add_yearly(
                            bucket,
                            year,
                            "consumed_qty",
                            convert_unit_quantity((ratio_qty / batch_size) * year_produced_qty, ratio_unit, unit),
                        )

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
        pf_yearly = new_yearly_payload()
        for year in range(1, year_count + 1):
            year_planned = demand_by_item_year[item_id].get(year, 0.0)
            year_served = served_by_item_year[item_id].get(year, 0.0)
            pf_yearly[str(year)]["planned_qty"] = year_planned
            pf_yearly[str(year)]["delivered_qty"] = year_served
            pf_yearly[str(year)]["consumed_qty"] = year_served
            initial_total = 0.0
            final_total = 0.0
            for pair, initial_qty in initial_stock_by_pair.items():
                node_id, pair_item_id = pair
                if pair_item_id != item_id or node_type_by_id.get(node_id) not in {"distribution_center", "customer"}:
                    continue
                if node_type_by_id.get(node_id) == "distribution_center":
                    initial_total += start_stock_for_year(
                        pair,
                        year,
                        initial_qty=initial_qty,
                        end_by_pair_day=dc_stock_end_by_pair_day,
                    )
                    final_total += end_stock_for_year(
                        pair,
                        year,
                        fallback_qty=initial_qty,
                        end_by_pair_day=dc_stock_end_by_pair_day,
                    )
                elif year == 1:
                    initial_total += max(0.0, initial_qty)
                    final_total += max(0.0, initial_qty)
            pf_yearly[str(year)]["initial_qty"] = initial_total
            pf_yearly[str(year)]["final_stock_qty"] = final_total
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
                "yearly": pf_yearly,
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
            pfi_yearly = new_yearly_payload()
            for year in range(1, year_count + 1):
                year_produced = produced_by_pair_year[pair_key].get(year, 0.0)
                year_shipped = shipped_from_pair_year[pair_key].get(year, 0.0)
                pfi_yearly[str(year)]["planned_qty"] = max(year_produced, year_shipped)
                pfi_yearly[str(year)]["delivered_qty"] = year_shipped
                pfi_yearly[str(year)]["consumed_qty"] = year_produced
                pfi_yearly[str(year)]["initial_qty"] = start_stock_for_year(
                    pair_key,
                    year,
                    initial_qty=initial_qty,
                    end_by_pair_day=output_stock_end_by_pair_day,
                )
                pfi_yearly[str(year)]["final_stock_qty"] = end_stock_for_year(
                    pair_key,
                    year,
                    fallback_qty=initial_qty,
                    end_by_pair_day=output_stock_end_by_pair_day,
                )
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
                "yearly": pfi_yearly,
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
        yearly = ensure_yearly(row)
        for year in range(1, year_count + 1):
            bucket = yearly[str(year)]
            bucket["delivered_qty"] = shipped_to_pair_year[pair_key].get(year, 0.0)
            bucket["initial_qty"] = start_stock_for_year(
                pair_key,
                year,
                initial_qty=initial_qty,
                before_by_pair_day=input_stock_before_by_pair_day,
                end_by_pair_day=input_stock_end_by_pair_day,
            )
            bucket["final_stock_qty"] = end_stock_for_year(
                pair_key,
                year,
                fallback_qty=initial_qty,
                end_by_pair_day=input_stock_end_by_pair_day,
            )
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


def is_display_order_row(row: dict[str, str]) -> bool:
    order_type = str(row.get("order_type") or "").strip()
    source_mode = str(row.get("source_mode") or "").strip()
    return not order_type.startswith("external_procurement") and not source_mode.startswith("external_procurement")


def display_order_type(order_type: Any) -> str:
    raw = str(order_type or "").strip()
    labels = {
        "lane_release": "ordre_flux",
        "opening_purchase_order": "ordre_achat_ouvert",
        "opening_production_order": "ordre_production_ouvert",
    }
    return labels.get(raw, raw or "n/a")


def compact_order_status(value: Any) -> str:
    raw = str(value or "").strip()
    labels = {
        "planned_and_released": "planifie",
        "opening_firm_order": "ouvert",
        "released_before_or_at_j0": "rel<=J0",
        "released": "lance",
        "firm_receipt": "recu ferme",
        "received": "recu",
        "n/a": "n/a",
    }
    return labels.get(raw, raw or "n/a")


def fmt_order_day(value: Any) -> str:
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    day = int(round(numeric))
    return f"J{day:+d}".replace("+0", "0").replace("+", "")


def fmt_order_day_range(min_value: Any, max_value: Any) -> str:
    min_day = fmt_order_day(min_value)
    max_day = fmt_order_day(max_value)
    if min_day == max_day:
        return min_day
    return f"{min_day}..{max_day}"


def order_week_start(day: int) -> int:
    return (day // 7) * 7


def order_placed_day(row: dict[str, str]) -> float | None:
    value = to_float(row.get("order_date_imt"))
    if value is None or math.isnan(value):
        value = to_float(row.get("day"))
    if value is None or math.isnan(value):
        return None
    return float(value)


def is_opening_order_row(row: dict[str, str]) -> bool:
    return str(row.get("order_type") or "").startswith("opening_")


def reference_transport_lead_days(row: dict[str, str]) -> float | None:
    value = to_float(row.get("lead_reference_days"))
    if value is None or math.isnan(value) or value <= 0:
        value = to_float(row.get("lead_cover_days"))
    if value is None or math.isnan(value) or value <= 0:
        return None
    return float(value)


def source_planned_material_lead_days(row: dict[str, str]) -> float | None:
    value = to_float(row.get("lead_reference_days"))
    if value is not None and not math.isnan(value) and value > 0:
        return float(value)
    if is_opening_order_row(row):
        value = to_float(row.get("lead_days"))
        if value is not None and not math.isnan(value) and value >= 0:
            return float(value)
    return None


def planned_order_receipt_day(row: dict[str, str]) -> float | None:
    order_day = order_placed_day(row)
    planned_lead_days = planned_procurement_lead_days(row)
    if (
        order_day is not None
        and planned_lead_days is not None
        and not math.isnan(order_day)
        and not math.isnan(planned_lead_days)
        and planned_lead_days >= 0
    ):
        return float(order_day + planned_lead_days)

    release_day = to_float(row.get("release_day"))
    transport_lead_days = to_float(row.get("lead_reference_days"))
    if transport_lead_days is None or math.isnan(transport_lead_days) or transport_lead_days <= 0:
        transport_lead_days = to_float(row.get("lead_cover_days"))
    if (
        release_day is not None
        and transport_lead_days is not None
        and not math.isnan(release_day)
        and not math.isnan(transport_lead_days)
        and transport_lead_days > 0
    ):
        return float(release_day + transport_lead_days)
    arrival_day = to_float(row.get("arrival_day"))
    if arrival_day is not None and not math.isnan(arrival_day):
        return float(arrival_day)
    order_day = order_placed_day(row)
    if order_day is not None and transport_lead_days is not None:
        return float(order_day + transport_lead_days)
    return None


def effective_order_receipt_day(row: dict[str, str]) -> float | None:
    value = to_float(row.get("actual_receipt_day"))
    if value is None or math.isnan(value):
        value = to_float(row.get("arrival_day"))
    if value is None or math.isnan(value):
        return None
    return float(value)


def planned_procurement_lead_days(row: dict[str, str]) -> float | None:
    return source_planned_material_lead_days(row)


def planned_order_to_receipt_days(row: dict[str, str]) -> float | None:
    order_day = order_placed_day(row)
    receipt_day = planned_order_receipt_day(row)
    if order_day is None or receipt_day is None:
        return None
    return max(0.0, float(receipt_day - order_day))


def effective_procurement_lead_days(row: dict[str, str]) -> float | None:
    order_day = order_placed_day(row)
    receipt_day = effective_order_receipt_day(row)
    if (
        order_day is not None
        and receipt_day is not None
        and not math.isnan(order_day)
        and not math.isnan(receipt_day)
    ):
        return max(0.0, float(receipt_day - order_day))

    release_day = to_float(row.get("release_day"))
    if (
        release_day is not None
        and receipt_day is not None
        and not math.isnan(release_day)
        and not math.isnan(receipt_day)
    ):
        return max(0.0, float(receipt_day - release_day))

    value = to_float(row.get("lead_days"))
    if value is not None and not math.isnan(value) and value >= 0:
        return float(value)
    return None


def resolved_order_day(row: dict[str, str], day_field: str = "day") -> int:
    if day_field == "planned_arrival_day":
        planned_day = planned_order_receipt_day(row)
        return int(round(planned_day)) if planned_day is not None else 0
    return int(to_float(row.get(day_field)) or 0)


def consolidate_order_rows_weekly(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        order_day = int(round(order_placed_day(row) or 0))
        release_day = int(to_float(row.get("release_day")) or 0)
        lead_reference_days = planned_procurement_lead_days(row)
        planned_arrival = planned_order_receipt_day(row)
        planned_arrival_day = int(round(planned_arrival)) if planned_arrival is not None else 0
        effective_arrival = effective_order_receipt_day(row)
        effective_arrival_day = int(round(effective_arrival)) if effective_arrival is not None else planned_arrival_day
        item_id = str(row.get("item_id") or "")
        key = (
            order_week_start(order_day),
            str(row.get("src_node_id") or ""),
            str(row.get("dst_node_id") or ""),
            item_id,
            str(row.get("order_type") or ""),
        )
        group = groups.get(key)
        if group is None:
            group = {
                "week_start": key[0],
                "src_node_id": key[1],
                "dst_node_id": key[2],
                "item_id": item_id,
                "order_type": key[4],
                "line_count": 0,
                "release_qty": 0.0,
                "receipt_qty": 0.0,
                "order_min": order_day,
                "order_max": order_day,
                "release_min": release_day,
                "release_max": release_day,
                "planned_arrival_min": planned_arrival_day,
                "planned_arrival_max": planned_arrival_day,
                "effective_arrival_min": effective_arrival_day,
                "effective_arrival_max": effective_arrival_day,
                "lead_reference_sum": 0.0,
                "lead_reference_count": 0,
                "statuses": defaultdict(int),
                "exceptions": set(),
            }
            groups[key] = group
        group["line_count"] += 1
        group["release_qty"] += max(0.0, to_float(row.get("release_qty")) or 0.0)
        group["receipt_qty"] += max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
        group["order_min"] = min(group["order_min"], order_day)
        group["order_max"] = max(group["order_max"], order_day)
        group["release_min"] = min(group["release_min"], release_day)
        group["release_max"] = max(group["release_max"], release_day)
        group["planned_arrival_min"] = min(group["planned_arrival_min"], planned_arrival_day)
        group["planned_arrival_max"] = max(group["planned_arrival_max"], planned_arrival_day)
        group["effective_arrival_min"] = min(group["effective_arrival_min"], effective_arrival_day)
        group["effective_arrival_max"] = max(group["effective_arrival_max"], effective_arrival_day)
        if lead_reference_days is not None and not math.isnan(lead_reference_days):
            group["lead_reference_sum"] += float(lead_reference_days)
            group["lead_reference_count"] += 1
        status_key = str(row.get("order_status_end_of_run") or "n/a")
        group["statuses"][status_key] += 1
        for flag in [
            str(row.get("planning_status") or ""),
            str(row.get("release_status") or ""),
            str(row.get("receipt_status") or ""),
            str(row.get("order_status_end_of_run") or ""),
        ]:
            if flag and flag not in {"planned_and_released", "released", "firm_receipt", "received"}:
                group["exceptions"].add(flag)
    return sorted(
        groups.values(),
        key=lambda group: (
            int(group["week_start"]),
            str(group["item_id"]),
            str(group["src_node_id"]),
            str(group["dst_node_id"]),
        ),
        reverse=True,
    )


def render_order_ledger_html(
    node_id: str,
    node_orders: list[dict[str, str]],
    item_labels: dict[str, str],
    empty_reason: str | None = None,
) -> str:
    node_orders = [row for row in node_orders if is_display_order_row(row)]
    if not node_orders:
        reason_html = (
            f"<div class=\"orderLedgerStatus\">{html.escape(empty_reason)}</div>"
            if empty_reason else ""
        )
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"{reason_html}"
            "<div class=\"panelEmptyState\">Aucun ordre MRP journalise pour ce noeud.</div>"
            "</div>"
        )

    sorted_orders = sorted(
        node_orders,
        key=lambda r: (
            int(to_float(r.get("order_date_imt")) or to_float(r.get("day")) or 0),
            int(to_float(r.get("release_day")) or 0),
            int(to_float(r.get("arrival_day")) or 0),
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

    edge_window_size = 500
    if len(sorted_orders) > edge_window_size * 2:
        display_orders = sorted_orders[:edge_window_size] + sorted_orders[-edge_window_size:]
        display_note = f"{edge_window_size} plus recents + {edge_window_size} plus anciens"
        separator_after = edge_window_size
    else:
        display_orders = sorted_orders
        display_note = "tous les ordres"
        separator_after = None

    recent_rows: list[str] = []
    for row_idx, row in enumerate(display_orders):
        if separator_after is not None and row_idx == separator_after:
            recent_rows.append(
                '<tr class="orderLedgerSliceSeparator">'
                '<td colspan="13">500 premiers ordres chronologiques affiches ci-dessous</td>'
                '</tr>'
            )
        item_id = str(row.get("item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        mode_label = display_order_type(row.get("order_type"))
        order_day_value = order_placed_day(row)
        planned_arrival_day = planned_order_receipt_day(row)
        actual_arrival_day_value = effective_order_receipt_day(row)
        planned_lead_days_value = planned_procurement_lead_days(row)
        effective_lead_days_value = effective_procurement_lead_days(row)
        exceptions = [
            str(row.get(field) or "").strip()
            for field in ["exception_reason", "exception_type", "exception_code"]
            if str(row.get(field) or "").strip()
        ]
        status_text = " | ".join(
            part
            for part in [
                f"plan={str(row.get('planning_status') or 'n/a')}",
                f"release={str(row.get('release_status') or 'n/a')}",
                f"receipt={str(row.get('receipt_status') or 'n/a')}",
                f"run={str(row.get('order_status_end_of_run') or 'n/a')}",
            ]
            if part
        )
        status_short = " / ".join(
            [
                compact_order_status(row.get("planning_status")),
                compact_order_status(row.get("release_status")),
                compact_order_status(row.get("receipt_status")),
                compact_order_status(row.get("order_status_end_of_run")),
            ]
        )
        release_qty = to_float(row.get("release_qty"))
        receipt_qty = to_float(row.get("receipt_qty"))
        if receipt_qty is None or math.isnan(receipt_qty):
            receipt_qty = to_float(row.get("planned_receipt_qty"))
        src_node_id = str(row.get("src_node_id") or "n/a")
        dst_node_id = str(row.get("dst_node_id") or "n/a")
        edge_id = str(row.get("edge_id") or "n/a")
        flux_text = f"{src_node_id} -> {dst_node_id}"
        exceptions_text = ", ".join(exceptions) if exceptions else "none"
        row_cells = [
            (fmt_order_day(order_day_value), ""),
            (item_label, f"Item complet: {item_label}"),
            (mode_label, mode_label),
            (flux_text, f"{flux_text} | edge={edge_id}"),
            (fmt_order_day(row.get("release_day")), ""),
            (f"{fmt_qty(planned_lead_days_value, 1)} j", "Delai previsionnel matiere source: champ FIA 'Delai previsionnel de livraison en jours' quand disponible; sinon delai derive du carnet d'ouverture."),
            (fmt_order_day(planned_arrival_day), ""),
            (fmt_order_day(actual_arrival_day_value), ""),
            (f"{fmt_qty(effective_lead_days_value, 1)} j", "Delai effectif matiere metier: arrivee effective - ordre passe fournisseur."),
            (fmt_qty(release_qty, 1), ""),
            (fmt_qty(receipt_qty, 1), ""),
            (status_short, status_text or "n/a"),
            (exceptions_text, exceptions_text),
        ]
        numeric_columns = {5, 8, 9, 10}
        row_tds: list[str] = []
        for idx, (value, title) in enumerate(row_cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(title), quote=True)}"' if title else ""
            row_tds.append(
                f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>'
            )
        recent_rows.append("<tr>" + "".join(row_tds) + "</tr>")

    title_suffix = "carnet d'ordres fournisseur" if node_id.startswith("SDC-") else "carnet d'ordres"
    statuses_text = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items())) or "aucun"
    table_header = "".join(
        f"<th>{html.escape(label)}</th>"
        for label in [
            "Ordre passe",
            "Item",
            "Type",
            "Flux",
            "Envoi",
            "Delai prev. mat.",
            "Arrivee prev.",
            "Arrivee effective",
            "Delai eff. mat.",
            "Qte envoyee",
            "Qte recue",
            "Statut",
            "Exceptions",
        ]
    )
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [90, 90, 130, 270, 80, 95, 115, 125, 105, 115, 115, 330, 145]
    )
    recent_rows_body = "".join(recent_rows) if recent_rows else "<tr><td colspan=\"13\">Aucun ordre journalise</td></tr>"
    recent_orders_html = (
        "<div class=\"orderLedgerFrame\">"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau du carnet MRP avec barre de defilement horizontale native en bas.\">"
        "<table class=\"orderLedgerTable orderLedgerWideTable\">"
        f"<colgroup>{table_cols}</colgroup>"
        f"<thead><tr>{table_header}</tr></thead>"
        f"<tbody>{recent_rows_body}</tbody>"
        "</table>"
        "</div>"
        "</div>"
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - {html.escape(title_suffix)}</div>",
            f"<div class=\"orderLedgerStatus\">Ordres MRP journalises: {len(sorted_orders)} ; lignes affichees: {len(display_orders)} ({html.escape(display_note)})</div>",
            f"<div class=\"orderLedgerStatus\">Statuses lignes brutes: {html.escape(statuses_text)}</div>",
            "<div class=\"orderLedgerStatus\">Jalons: ordre_passe=order_date_imt | envoi=release_day | arrivee_previsionnelle=ordre_passe+delai_previsionnel_source | arrivee_effective=actual_receipt_day/arrival_day | delai_previsionnel_matiere=delai source donnees FIA/Extract | delai_effectif_matiere=arrivee_effective-ordre_passe</div>",
            "<div class=\"orderLedgerSectionTitle\">Ordres passes affiches: 500 derniers puis 500 premiers si le carnet depasse 1000 lignes.</div>",
            recent_orders_html,
            "</div>",
        ]
    )


def render_supplier_stock_flows_html(
    node_id: str,
    flow_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    order_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_flow_rows = [
        row for row in flow_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_order_rows = [
        row for row in order_rows
        if str(row.get("src_node_id") or "") == node_id
        and not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    if not visible_flow_rows and not visible_shipment_rows and not visible_order_rows:
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - flux stock fournisseur</div>"
            "<div class=\"panelEmptyState\">Aucun flux stock fournisseur, envoi physique ou ordre previsionnel disponible pour ce noeud.</div>"
            "</div>"
        )

    stats_by_item: dict[str, dict[str, Any]] = {}

    def stats_for(item_id: str, uom: str = "") -> dict[str, Any]:
        stats = stats_by_item.get(item_id)
        if stats is None:
            stats = {
                "uom": uom,
                "first_day": None,
                "last_day": None,
                "stock_start": 0.0,
                "stock_end": 0.0,
                "min_stock": None,
                "max_stock": 0.0,
                "incoming": 0.0,
                "incoming_external": 0.0,
                "incoming_estimated": 0.0,
                "incoming_upstream": 0.0,
                "stock_writeoff": 0.0,
                "outgoing_pulled": 0.0,
                "outgoing_shipped": 0.0,
                "physical_shipped": 0.0,
                "planned_received": 0.0,
                "loss": 0.0,
                "incoming_days": 0,
                "outgoing_days": 0,
                "physical_send_days": set(),
                "planned_receipt_days": set(),
                "max_balance_gap": 0.0,
            }
            stats_by_item[item_id] = stats
        elif uom and not stats.get("uom"):
            stats["uom"] = uom
        return stats

    for row in visible_flow_rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        stats = stats_for(item_id, str(row.get("uom") or ""))
        day = int(to_float(row.get("day")) or 0)
        start = max(0.0, to_float(row.get("stock_start_of_day")) or 0.0)
        end = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        incoming = max(0.0, to_float(row.get("incoming_qty")) or 0.0)
        outgoing = max(0.0, to_float(row.get("outgoing_pulled_qty")) or 0.0)
        if stats["first_day"] is None or day < stats["first_day"]:
            stats["first_day"] = day
            stats["stock_start"] = start
        if stats["last_day"] is None or day >= stats["last_day"]:
            stats["last_day"] = day
            stats["stock_end"] = end
        stats["min_stock"] = end if stats["min_stock"] is None else min(stats["min_stock"], end)
        stats["max_stock"] = max(stats["max_stock"], end, start)
        stats["incoming"] += incoming
        stats["incoming_external"] += max(0.0, to_float(row.get("incoming_external_market_qty")) or 0.0)
        stats["incoming_estimated"] += max(0.0, to_float(row.get("incoming_estimated_source_qty")) or 0.0)
        stats["incoming_upstream"] += max(0.0, to_float(row.get("incoming_upstream_pipeline_qty")) or 0.0)
        stats["stock_writeoff"] += max(0.0, to_float(row.get("stock_writeoff_qty")) or 0.0)
        stats["outgoing_pulled"] += outgoing
        stats["outgoing_shipped"] += max(0.0, to_float(row.get("outgoing_shipped_qty")) or 0.0)
        stats["loss"] += max(0.0, to_float(row.get("outgoing_unreliable_loss_qty")) or 0.0)
        if incoming > 1e-9:
            stats["incoming_days"] += 1
        if outgoing > 1e-9:
            stats["outgoing_days"] += 1
        stats["max_balance_gap"] = max(
            stats["max_balance_gap"],
            abs(to_float(row.get("balance_check_gap_qty")) or 0.0),
        )

    for row in visible_shipment_rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        stats = stats_for(item_id, str(row.get("uom") or ""))
        shipped = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        if shipped <= 1e-9:
            continue
        stats["physical_shipped"] += shipped
        send_day = to_float(row.get("day"))
        if send_day is not None and not math.isnan(send_day):
            stats["physical_send_days"].add(int(round(send_day)))

    for row in visible_order_rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        stats = stats_for(item_id, str(row.get("uom") or ""))
        planned_received = max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
        if planned_received <= 1e-9:
            continue
        stats["planned_received"] += planned_received
        planned_receipt_day = planned_order_receipt_day(row)
        if planned_receipt_day is not None and not math.isnan(planned_receipt_day):
            stats["planned_receipt_days"].add(int(round(planned_receipt_day)))

    rows_html: list[str] = []
    for item_id, stats in sorted(stats_by_item.items(), key=lambda kv: item_labels.get(kv[0], kv[0])):
        title = (
            "Stock fin = stock debut + entrees - sorties stock. "
            "Sorties stock = quantite prelevee chez fournisseur; expedie aval = quantite utile apres fiabilite."
        )
        cells = [
            (item_labels.get(item_id, compact_item_label(item_id)), f"Item complet: {item_id}"),
            (stats.get("uom") or "n/a", ""),
            (fmt_qty(stats.get("stock_start"), 1), title),
            (fmt_qty(stats.get("incoming"), 1), "entrees reelles dans le stock fournisseur"),
            (fmt_qty(stats.get("incoming_external"), 1), "dont arrivees EXTERNAL_MARKET"),
            (fmt_qty(stats.get("stock_writeoff"), 1), "pertes de stock fournisseur appliquees par evenement de risque"),
            (fmt_qty(stats.get("outgoing_pulled"), 1), "sorties reelles du stock fournisseur"),
            (fmt_qty(stats.get("outgoing_shipped"), 1), "quantite utile expediee aval apres fiabilite"),
            (fmt_qty(stats.get("physical_shipped"), 1), "envois physiques issus de production_supplier_shipments_daily.day"),
            (fmt_qty(stats.get("planned_received"), 1), "receptions aval previsionnelles issues du carnet MRP, datees a ordre_passe + delai previsionnel source"),
            (
                fmt_qty((stats.get("physical_shipped") or 0.0) - (stats.get("outgoing_shipped") or 0.0), 1),
                "ecart entre envois physiques et expedie aval du bilan stock; les commandes d'ouverture/historiques peuvent etre hors bilan stock quotidien",
            ),
            (fmt_qty(stats.get("loss"), 1), "ecart entre stock preleve et quantite utile aval"),
            (fmt_qty(stats.get("stock_end"), 1), title),
            (fmt_qty(stats.get("min_stock"), 1), "stock fin de jour minimum observe"),
            (fmt_qty(stats.get("max_stock"), 1), "stock maximum observe"),
            (str(stats.get("incoming_days") or 0), "jours avec entree fournisseur"),
            (str(stats.get("outgoing_days") or 0), "jours avec sortie fournisseur"),
            (str(len(stats.get("physical_send_days") or [])), "jours avec envoi physique"),
            (str(len(stats.get("planned_receipt_days") or [])), "jours avec reception aval previsionnelle"),
            (fmt_qty(stats.get("max_balance_gap"), 6), "ecart max du bilan stock quotidien"),
        ]
        numeric_columns = set(range(2, len(cells)))
        row_tds: list[str] = []
        for idx, (value, cell_title) in enumerate(cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(cell_title), quote=True)}"' if cell_title else ""
            row_tds.append(f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>')
        rows_html.append("<tr>" + "".join(row_tds) + "</tr>")

    headers = [
        "Item",
        "UOM",
        "Stock debut",
        "Entrees total",
        "Dont marche ext.",
        "Pertes stock",
        "Sorties stock",
        "Expedie aval",
        "Envois phys.",
        "Receptions prev.",
        "Ecart phys/stock",
        "Ecart fiabilite",
        "Stock fin",
        "Stock min",
        "Stock max",
        "Jours entree",
        "Jours sortie",
        "Jours envoi phys.",
        "Jours recept. prev.",
        "Ecart bilan",
    ]
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [105, 70, 115, 125, 125, 115, 120, 120, 120, 120, 125, 120, 115, 115, 115, 100, 100, 120, 120, 110]
    )
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - flux stock fournisseur</div>",
            "<div class=\"orderLedgerStatus\">Bilan quotidien consolide par item: stock debut + entrees fournisseur - pertes stock - sorties stock = stock fin.</div>",
            "<div class=\"orderLedgerStatus\">Entrees = arrivees dans le stock fournisseur; sorties stock = quantite prelevee chez le fournisseur; expedie aval tient compte de la fiabilite.</div>",
            "<div class=\"orderLedgerStatus\">Envois phys. = production_supplier_shipments_daily.day. Receptions prev. = carnet MRP date a ordre_passe + delai previsionnel source; pas arrival_day simule.</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau des flux de stock fournisseur avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            f"<colgroup>{table_cols}</colgroup>",
            f"<thead><tr>{''.join(f'<th>{html.escape(label)}</th>' for label in headers)}</tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )


def render_supplier_risk_catalog_html(
    node_id: str,
    *,
    applied_rows: list[dict[str, str]],
    configured_events: list[dict[str, Any]],
    economic_policy: dict[str, Any],
) -> str:
    def configured_events_for(types: set[str]) -> list[dict[str, Any]]:
        return [
            event
            for event in configured_events
            if str(event.get("risk_type") or "") in types
        ]

    def field_values(field: str, default: float = 1.0) -> list[float]:
        vals: list[float] = []
        for row in applied_rows:
            raw = row.get(field)
            if raw is None or str(raw).strip() == "":
                continue
            value = to_float(raw)
            if value is None or math.isnan(value):
                value = default
            vals.append(float(value))
        return vals

    def has_factor_effect(fields: list[str]) -> bool:
        return any(
            abs(value - 1.0) > 1e-9
            for field in fields
            for value in field_values(field, 1.0)
        )

    def has_positive_effect(fields: list[str]) -> bool:
        return any(
            value > 1e-9
            for field in fields
            for value in field_values(field, 0.0)
        )

    def row_has_factor_effect(row: dict[str, str], fields: list[str]) -> bool:
        for field in fields:
            raw = row.get(field)
            if raw is None or str(raw).strip() == "":
                continue
            value = to_float(raw)
            if value is not None and not math.isnan(value) and abs(value - 1.0) > 1e-9:
                return True
        return False

    def row_has_positive_effect(row: dict[str, str], fields: list[str]) -> bool:
        for field in fields:
            raw = row.get(field)
            if raw is None or str(raw).strip() == "":
                continue
            value = to_float(raw)
            if value is not None and not math.isnan(value) and value > 1e-9:
                return True
        return False

    def event_ids_for(types: set[str], applied_field_names: list[str]) -> list[str]:
        ids: set[str] = set()
        for event in configured_events_for(types):
            event_id = str(event.get("event_id") or "").strip()
            if event_id:
                ids.add(event_id)
        if applied_field_names:
            for row in applied_rows:
                factor_fields = [field for field in applied_field_names if "multiplier" in field]
                positive_fields = [field for field in applied_field_names if "multiplier" not in field]
                row_has_effect = row_has_factor_effect(row, factor_fields) or row_has_positive_effect(row, positive_fields)
                if not row_has_effect:
                    continue
                for event_id in str(row.get("event_ids") or "").split(","):
                    event_id = event_id.strip()
                    if event_id:
                        ids.add(event_id)
        return sorted(ids)

    def configured_text(events: list[dict[str, Any]]) -> str:
        if not events:
            return "aucun"
        parts = []
        for event in events[:4]:
            event_id = str(event.get("event_id") or "event")
            start_day = event.get("start_day", "")
            end_day = event.get("end_day", "")
            multiplier = event.get("multiplier", "")
            item_id = str(event.get("item_id") or "*")
            parts.append(f"{event_id}: item={item_id}, J{start_day}-J{end_day}, val={multiplier}")
        if len(events) > 4:
            parts.append(f"+{len(events) - 4} autre(s)")
        return " ; ".join(parts)

    def factor_intensity(fields: list[str], *, mode: str) -> str:
        vals = [
            value
            for field in fields
            for value in field_values(field, 1.0)
        ]
        if not vals:
            return "1.00x"
        if mode == "max":
            return f"max={max(vals):.2f}x"
        return f"min={min(vals):.2f}x"

    def days_intensity(fields: list[str]) -> str:
        vals = [
            value
            for field in fields
            for value in field_values(field, 0.0)
        ]
        if not vals:
            return "0.0 j"
        return f"max={fmt_days(max(vals), 1)}"

    def pct_intensity(fields: list[str]) -> str:
        vals = [
            value
            for field in fields
            for value in field_values(field, 0.0)
        ]
        if not vals:
            return "0.0%"
        return f"max={fmt_pct(max(vals) * 100.0)}"

    catalog = [
        {
            "category": "Stock fournisseur",
            "types": {"stock"},
            "factor_fields": ["stock_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Part de stock fournisseur accessible aux commandes.",
        },
        {
            "category": "Perte stock / write-off",
            "types": {"stock_writeoff"},
            "factor_fields": [],
            "day_fields": [],
            "pct_fields": ["stock_writeoff_fraction"],
            "mode": "max",
            "reading": "Destruction, quarantaine definitive ou perte physique du stock fournisseur.",
        },
        {
            "category": "Capacite fournisseur",
            "types": {"capacity"},
            "factor_fields": ["capacity_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Debit journalier disponible chez le fournisseur.",
        },
        {
            "category": "Disponibilite fournisseur",
            "types": {"availability"},
            "factor_fields": ["availability_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Indisponibilite temporaire du fournisseur ou d'une ligne amont.",
        },
        {
            "category": "Lead time fournisseur",
            "types": {"lead_time", "lead_time_extra_days"},
            "factor_fields": ["lead_time_multiplier"],
            "day_fields": ["lead_time_extra_days"],
            "pct_fields": [],
            "mode": "max",
            "reading": "Allongement du delai reel simule avant reception.",
        },
        {
            "category": "Qualite / release",
            "types": {"quality_delay"},
            "factor_fields": [],
            "day_fields": ["quality_delay_days"],
            "pct_fields": [],
            "mode": "max",
            "reading": "Retard de liberation qualite ajoute au lead time.",
        },
        {
            "category": "Fiabilite / OTIF",
            "types": {"reliability"},
            "factor_fields": ["reliability_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Part utile expediee apres alea de fiabilite fournisseur.",
        },
        {
            "category": "Rendement qualite / rejets",
            "types": {"quality_yield"},
            "factor_fields": ["quality_yield_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Rendement utile apres rejet, scrap ou non-conformite.",
        },
        {
            "category": "Cout achat",
            "types": {"purchase_cost"},
            "factor_fields": ["purchase_cost_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "max",
            "reading": "Inflation prix achat ou surcharge fournisseur.",
        },
        {
            "category": "Cout transport",
            "types": {"transport_cost"},
            "factor_fields": ["transport_cost_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "max",
            "reading": "Inflation fret, urgence, changement de mode transport.",
        },
        {
            "category": "EXTERNAL_MARKET - capacite",
            "types": {"external_capacity", "external_availability"},
            "factor_fields": ["external_capacity_multiplier", "external_availability_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Plafond et disponibilite du marche externe quand il sert de source amont.",
        },
        {
            "category": "EXTERNAL_MARKET - delai",
            "types": {"external_lead_time", "external_lead_time_extra_days"},
            "factor_fields": ["external_lead_time_multiplier"],
            "day_fields": ["external_lead_time_extra_days"],
            "pct_fields": [],
            "mode": "max",
            "reading": "Allongement du delai marche externe.",
        },
        {
            "category": "EXTERNAL_MARKET - qualite",
            "types": {"external_quality_yield"},
            "factor_fields": ["external_quality_yield_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Rendement utile du marche externe apres rejet.",
        },
        {
            "category": "EXTERNAL_MARKET - cout",
            "types": {"external_cost"},
            "factor_fields": ["external_cost_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "max",
            "reading": "Surcout du marche externe, achat et transport d'urgence.",
        },
    ]

    rows_html: list[str] = []
    for entry in catalog:
        types = set(entry["types"])
        factor_fields = list(entry["factor_fields"])
        day_fields = list(entry["day_fields"])
        pct_fields = list(entry["pct_fields"])
        configured = configured_events_for(types)
        applied = (
            has_factor_effect(factor_fields)
            or has_positive_effect(day_fields)
            or has_positive_effect(pct_fields)
        )
        status = "APPLIQUE" if applied else ("CONFIGURE" if configured else "NEUTRE")
        intensity_parts: list[str] = []
        if factor_fields:
            intensity_parts.append(factor_intensity(factor_fields, mode=str(entry["mode"])))
        if day_fields:
            intensity_parts.append(days_intensity(day_fields))
        if pct_fields:
            intensity_parts.append(pct_intensity(pct_fields))
        intensity = " ; ".join(intensity_parts) if intensity_parts else "n/a"
        events_text = ", ".join(event_ids_for(types, factor_fields + day_fields + pct_fields)) or "aucun"
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(status)}</td>"
            f"<td>{html.escape(str(entry['category']))}</td>"
            f"<td>{html.escape(intensity)}</td>"
            f"<td>{html.escape(events_text)}</td>"
            f"<td>{html.escape(str(entry['reading']))}</td>"
            f"<td>{html.escape(configured_text(configured))}</td>"
            "</tr>"
        )

    external_enabled = bool(economic_policy.get("external_procurement_enabled"))
    external_proactive = bool(economic_policy.get("external_procurement_proactive_replenishment"))
    external_lead_mode = str(economic_policy.get("external_procurement_lead_mode") or "policy_fixed")
    if external_lead_mode == "supplier_material":
        external_lead_label = (
            "lead=delai matiere fournisseur "
            f"(fallback {fmt_days(economic_policy.get('external_procurement_lead_days'), 0)})"
        )
    else:
        external_lead_label = f"lead fixe={fmt_days(economic_policy.get('external_procurement_lead_days'), 0)}"
    external_capacity_mode = str(economic_policy.get("external_procurement_capacity_mode") or "policy_cap")
    if external_capacity_mode == "supplier_nominal":
        external_capacity_label = (
            "cap=fournisseur nominal par item "
            f"(scale={fmt_qty(economic_policy.get('external_procurement_nominal_capacity_scale', 1.0), 2)} ; "
            f"pipeline init={'oui' if economic_policy.get('external_procurement_seed_upstream_pipeline') else 'non'}, "
            f"fill={fmt_qty(economic_policy.get('external_procurement_upstream_pipeline_fill_ratio', 0.0), 2)})"
        )
    else:
        external_capacity_label = (
            f"cap/j=max({fmt_qty(economic_policy.get('external_procurement_min_daily_cap_qty'), 0)}, "
            f"{fmt_qty(economic_policy.get('external_procurement_daily_cap_days'), 1)} jours de demande)"
        )
    external_policy_text = (
        f"EXTERNAL_MARKET: {'actif' if external_enabled else 'inactif'} ; "
        f"proactif={'oui' if external_proactive else 'non'} ; "
        f"{external_lead_label} ; "
        f"scale={fmt_qty(economic_policy.get('external_procurement_lead_time_scale', 1.0), 2)} ; "
        f"{external_capacity_label} ; "
        f"cout={fmt_qty(economic_policy.get('external_procurement_cost_multiplier'), 1)}x"
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - risques fournisseur</div>",
            "<div class=\"orderLedgerStatus\">Catalogue des risques fournisseur: statut, intensite appliquee et evenements configures. Sans evenement, les facteurs restent neutres et la baseline ne bouge pas.</div>",
            f"<div class=\"orderLedgerStatus\">{html.escape(external_policy_text)}</div>",
            "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
            "<thead><tr><th>Statut</th><th>Categorie</th><th>Intensite appliquee</th><th>Evenements</th><th>Lecture</th><th>Configuration</th></tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table></div>",
            "</div>",
        ]
    )


def finite_numeric_values(values: Iterable[Any], *, positive_only: bool = False) -> list[float]:
    out: list[float] = []
    for value in values:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            continue
        if positive_only and numeric <= 0:
            continue
        out.append(float(numeric))
    return out


def coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = statistics.mean(values)
    if abs(mean_value) <= 1e-12:
        return None
    return statistics.pstdev(values) / abs(mean_value)


def uncertainty_level(cv: float | None) -> str:
    if cv is None:
        return "non estimee"
    if cv < 0.05:
        return "faible"
    if cv < 0.20:
        return "moderee"
    return "elevee"


def fmt_uncertainty_band(values: list[float], *, kind: str = "qty", digits: int = 1) -> str:
    if not values:
        return "n/a"
    p10 = percentile(values, 0.10)
    p50 = percentile(values, 0.50)
    p90 = percentile(values, 0.90)

    def fmt_value(value: float) -> str:
        if kind == "days":
            return fmt_days(value, digits)
        if kind == "pct":
            return fmt_pct(value * 100.0, digits)
        return fmt_qty(value, digits)

    return f"P10={fmt_value(p10)} ; P50={fmt_value(p50)} ; P90={fmt_value(p90)}"


def render_passive_uncertainty_html(
    scope_id: str,
    *,
    scope_label: str,
    order_rows: list[dict[str, str]],
    stock_rows: list[dict[str, str]],
    capacity_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    nominal_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_order_rows = [
        row for row in order_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_stock_rows = [
        row for row in stock_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_capacity_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_nominal_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]

    planned_leads = finite_numeric_values(
        (planned_procurement_lead_days(row) for row in visible_order_rows),
        positive_only=True,
    )
    if not planned_leads:
        planned_leads = finite_numeric_values(
            (row.get("planned_lead_time_days") for row in visible_nominal_rows),
            positive_only=True,
        )
    effective_leads = finite_numeric_values(
        (effective_procurement_lead_days(row) for row in visible_order_rows),
        positive_only=True,
    )
    if not effective_leads:
        effective_leads = finite_numeric_values(
            (row.get("lead_days") for row in visible_shipment_rows),
            positive_only=True,
        )
    comparable_lead_pairs: list[tuple[float, float]] = []
    for row in visible_order_rows:
        planned = planned_procurement_lead_days(row)
        effective = effective_procurement_lead_days(row)
        if planned is None or effective is None or planned <= 0 or effective < 0:
            continue
        comparable_lead_pairs.append((float(planned), float(effective)))
    late_pairs = [
        (planned, effective)
        for planned, effective in comparable_lead_pairs
        if effective > planned + 1e-9
    ]
    delay_probability = len(late_pairs) / len(comparable_lead_pairs) if comparable_lead_pairs else None
    avg_delay = (
        statistics.mean(max(0.0, effective - planned) for planned, effective in comparable_lead_pairs)
        if comparable_lead_pairs
        else None
    )
    lead_cv = coefficient_of_variation(effective_leads)
    lead_cv_suggested = max(0.05, min(0.35, lead_cv if lead_cv is not None else 0.10))

    capacity_values = finite_numeric_values(
        (row.get("capacity_qty_per_day") for row in visible_capacity_rows),
        positive_only=True,
    )
    utilization_values = finite_numeric_values((row.get("utilization") for row in visible_capacity_rows))
    nominal_capacity_values = finite_numeric_values(
        (
            row.get("industrial_nominal_capacity_qty_per_day")
            or row.get("effective_capacity_qty_per_day")
            or row.get("nominal_capacity_qty_per_day")
            for row in visible_nominal_rows
        ),
        positive_only=True,
    )
    capacity_cv = coefficient_of_variation(capacity_values)
    capacity_cv_suggested = max(0.05, min(0.30, capacity_cv if capacity_cv is not None else 0.10))
    max_utilization = max(utilization_values) if utilization_values else None
    avg_active_utilization_values = [value for value in utilization_values if value > 1e-9]
    avg_active_utilization = statistics.mean(avg_active_utilization_values) if avg_active_utilization_values else None

    stock_values = finite_numeric_values((row.get("stock_end_of_day") for row in visible_stock_rows))
    stock_cv = coefficient_of_variation(stock_values)
    stock_cv_suggested = max(0.05, min(0.40, stock_cv if stock_cv is not None else 0.15))
    stock_zero_days = sum(1 for value in stock_values if value <= 1e-9)
    stock_zero_probability = stock_zero_days / len(stock_values) if stock_values else None

    reliability_values = finite_numeric_values((row.get("reliability") for row in visible_shipment_rows))
    loss_ratios: list[float] = []
    for row in visible_shipment_rows:
        pulled = to_float(row.get("pulled_qty"))
        shipped = to_float(row.get("shipped_qty"))
        if pulled is None or shipped is None or math.isnan(pulled) or math.isnan(shipped) or pulled <= 0:
            continue
        loss_ratios.append(max(0.0, min(1.0, (pulled - shipped) / pulled)))
    reliability_cv = coefficient_of_variation(reliability_values)
    reliability_mean = statistics.mean(reliability_values) if reliability_values else None
    loss_mean = statistics.mean(loss_ratios) if loss_ratios else None
    reliability_cv_suggested = max(0.002, min(0.05, reliability_cv if reliability_cv is not None else 0.005))

    item_ids = sorted(
        {
            str(row.get("item_id") or "")
            for row in visible_order_rows
            + visible_stock_rows
            + visible_capacity_rows
            + visible_shipment_rows
            + visible_nominal_rows
            if str(row.get("item_id") or "")
        }
    )
    item_text = ", ".join(item_labels.get(item_id, compact_item_label(item_id)) for item_id in item_ids[:8])
    if len(item_ids) > 8:
        item_text += f" +{len(item_ids) - 8}"
    if not item_text:
        item_text = "n/a"

    def fmt_optional_mean(values: list[float], *, kind: str = "qty", digits: int = 1) -> str:
        if not values:
            return "n/a"
        value = statistics.mean(values)
        if kind == "days":
            return fmt_days(value, digits)
        if kind == "pct":
            return fmt_pct(value * 100.0, digits)
        return fmt_qty(value, digits)

    def fmt_optional_pct_fraction(value: float | None, digits: int = 1) -> str:
        return "n/a" if value is None else fmt_pct(value * 100.0, digits)

    table_rows = [
        (
            "Lead time",
            "mrp_orders_daily: order_date_imt, actual_receipt_day, lead_reference_days",
            fmt_optional_mean(planned_leads, kind="days"),
            f"{uncertainty_level(lead_cv)} ; CV={lead_cv:.3f}" if lead_cv is not None else "non estimee",
            fmt_uncertainty_band(effective_leads, kind="days"),
            f"P(retard)={fmt_optional_pct_fraction(delay_probability)} ; retard moyen={fmt_days(avg_delay, 1)}",
            f"lead_time_cv={lead_cv_suggested:.3f} (inactif)",
        ),
        (
            "Capacite",
            "production_supplier_capacity_daily.csv",
            fmt_optional_mean(nominal_capacity_values or capacity_values),
            f"{uncertainty_level(capacity_cv)} ; CV cap={capacity_cv:.3f}" if capacity_cv is not None else "non estimee",
            fmt_uncertainty_band(capacity_values),
            f"util active={fmt_optional_pct_fraction(avg_active_utilization)} ; util max={fmt_optional_pct_fraction(max_utilization)}",
            f"capacity_cv={capacity_cv_suggested:.3f} (inactif)",
        ),
        (
            "Stock fournisseur",
            "production_supplier_stocks_daily.csv",
            fmt_optional_mean(stock_values),
            f"{uncertainty_level(stock_cv)} ; CV={stock_cv:.3f}" if stock_cv is not None else "non estimee",
            fmt_uncertainty_band(stock_values),
            f"P(stock=0)={fmt_optional_pct_fraction(stock_zero_probability)} ; jours zero={stock_zero_days}",
            f"stock_availability_cv={stock_cv_suggested:.3f} (inactif)",
        ),
        (
            "Fiabilite / qualite",
            "production_supplier_shipments_daily.csv",
            fmt_optional_pct_fraction(reliability_mean),
            f"{uncertainty_level(reliability_cv)} ; CV={reliability_cv:.3f}" if reliability_cv is not None else "non estimee",
            fmt_uncertainty_band(reliability_values, kind="pct", digits=2),
            f"perte moyenne={fmt_optional_pct_fraction(loss_mean, 2)} ; lignes={len(visible_shipment_rows)}",
            f"reliability_cv={reliability_cv_suggested:.3f} (inactif)",
        ),
    ]
    rows_html = []
    for dim, source, nominal, uncertainty, band, risk, inactive_param in table_rows:
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(dim)}</td>"
            f"<td>{html.escape(source)}</td>"
            f"<td>{html.escape(nominal)}</td>"
            f"<td>{html.escape(uncertainty)}</td>"
            f"<td>{html.escape(band)}</td>"
            f"<td>{html.escape(risk)}</td>"
            f"<td>{html.escape(inactive_param)}</td>"
            "</tr>"
        )

    config_preview = {
        "uncertainty_enabled": False,
        "mode": "passive_calibration_only",
        "scope": scope_id,
        "lead_time_cv": round(lead_cv_suggested, 4),
        "capacity_cv": round(capacity_cv_suggested, 4),
        "stock_availability_cv": round(stock_cv_suggested, 4),
        "reliability_cv": round(reliability_cv_suggested, 4),
    }

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(scope_id)} - incertitude passive {html.escape(scope_label)}</div>",
            "<div class=\"orderLedgerStatus\">Lecture seule: aucune valeur aleatoire n'est injectee dans la simulation courante et aucun KPI du run n'est recalcule.</div>",
            "<div class=\"orderLedgerStatus\">Objectif: preparer une future couche Monte Carlo en estimant des dispersions a partir des delais, stocks, capacites et expeditions deja produits.</div>",
            f"<div class=\"orderLedgerStatus\">Items couverts: {html.escape(item_text)}</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau incertitude passive avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            "<colgroup>"
            "<col style=\"width:135px\"><col style=\"width:245px\"><col style=\"width:130px\"><col style=\"width:145px\">"
            "<col style=\"width:235px\"><col style=\"width:235px\"><col style=\"width:185px\">"
            "</colgroup>",
            "<thead><tr><th>Dimension</th><th>Source</th><th>Nominal</th><th>Dispersion</th><th>Bande observee</th><th>Signal risque</th><th>Parametre futur</th></tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "<div class=\"orderLedgerSectionTitle\">Configuration Monte Carlo proposee mais inactive</div>",
            f"<pre class=\"jsonPanelPre\">{html.escape(json.dumps(config_preview, indent=2, ensure_ascii=False))}</pre>",
            "</div>",
        ]
    )


def clamp01(value: float | None) -> float:
    if value is None or math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def risk_level(score: float) -> str:
    if score >= 0.50:
        return "fort"
    if score >= 0.25:
        return "modere"
    return "faible"


def render_supplier_risk_prediction_html(
    node_id: str,
    *,
    order_rows: list[dict[str, str]],
    stock_rows: list[dict[str, str]],
    capacity_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    nominal_rows: list[dict[str, str]],
    criticality_row: dict[str, str] | None,
    economic_policy: dict[str, Any],
    item_labels: dict[str, str],
) -> str:
    visible_order_rows = [
        row for row in order_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_stock_rows = [
        row for row in stock_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_capacity_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_nominal_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]

    comparable_lead_pairs: list[tuple[float, float]] = []
    for row in visible_order_rows:
        planned = planned_procurement_lead_days(row)
        effective = effective_procurement_lead_days(row)
        if planned is None or effective is None or planned <= 0 or effective < 0:
            continue
        comparable_lead_pairs.append((float(planned), float(effective)))
    effective_leads = [effective for _, effective in comparable_lead_pairs]
    lead_cv = coefficient_of_variation(effective_leads)
    late_pairs = [(planned, effective) for planned, effective in comparable_lead_pairs if effective > planned + 1e-9]
    delay_probability = len(late_pairs) / len(comparable_lead_pairs) if comparable_lead_pairs else None
    avg_delay_days = (
        statistics.mean(max(0.0, effective - planned) for planned, effective in comparable_lead_pairs)
        if comparable_lead_pairs
        else None
    )

    capacity_utils = finite_numeric_values((row.get("utilization") for row in visible_capacity_rows))
    max_util = max(capacity_utils) if capacity_utils else None
    avg_active_util_values = [value for value in capacity_utils if value > 1e-9]
    avg_active_util = statistics.mean(avg_active_util_values) if avg_active_util_values else None
    util_cv = coefficient_of_variation(capacity_utils)

    stock_values = finite_numeric_values((row.get("stock_end_of_day") for row in visible_stock_rows))
    stock_cv = coefficient_of_variation(stock_values)
    stock_zero_probability = (
        sum(1 for value in stock_values if value <= 1e-9) / len(stock_values)
        if stock_values
        else None
    )
    stock_p10 = percentile(stock_values, 0.10) if stock_values else None

    reliability_values = finite_numeric_values((row.get("reliability") for row in visible_shipment_rows))
    reliability_mean = statistics.mean(reliability_values) if reliability_values else None
    reliability_cv = coefficient_of_variation(reliability_values)
    loss_ratios: list[float] = []
    for row in visible_shipment_rows:
        pulled = to_float(row.get("pulled_qty"))
        shipped = to_float(row.get("shipped_qty"))
        if pulled is None or shipped is None or math.isnan(pulled) or math.isnan(shipped) or pulled <= 0:
            continue
        loss_ratios.append(max(0.0, min(1.0, (pulled - shipped) / pulled)))
    loss_mean = statistics.mean(loss_ratios) if loss_ratios else None

    local_criticality = clamp01(to_float((criticality_row or {}).get("local_criticality_score")))
    overall_criticality = clamp01(to_float((criticality_row or {}).get("overall_criticality_score")))
    observed_share = clamp01(to_float((criticality_row or {}).get("observed_sourcing_share")))
    sole_source_pairs = int(to_float((criticality_row or {}).get("sole_source_pairs")) or 0)
    shortage_events = int(to_float((criticality_row or {}).get("shortage_supported_events")) or 0)
    impact_score = max(
        overall_criticality,
        0.75 * local_criticality,
        0.60 * observed_share if sole_source_pairs > 0 else 0.35 * observed_share,
        0.25 if shortage_events > 0 else 0.0,
    )
    if impact_score <= 1e-9 and visible_nominal_rows:
        impact_score = max(0.25, max((to_float(row.get("mrp_share")) or 0.0) for row in visible_nominal_rows))
    impact_score = clamp01(impact_score)

    def confidence(row_count: int, *, has_criticality: bool = True) -> float:
        value = 0.25 + math.log1p(max(0, row_count)) / 8.0
        if not has_criticality:
            value -= 0.08
        return clamp01(min(0.95, value))

    lead_occurrence = clamp01(
        0.04
        + 0.55 * (delay_probability or 0.0)
        + 0.25 * min(1.0, (avg_delay_days or 0.0) / 30.0)
        + 0.20 * min(1.0, (lead_cv or 0.0) / 0.30)
    )
    capacity_occurrence = clamp01(
        0.03
        + 0.70 * (max_util or 0.0)
        + 0.20 * (avg_active_util or 0.0)
        + 0.10 * min(1.0, (util_cv or 0.0) / 0.30)
    )
    stock_occurrence = clamp01(
        0.03
        + 0.65 * (stock_zero_probability or 0.0)
        + (0.15 if stock_p10 is not None and stock_p10 <= 1e-9 else 0.0)
        + 0.20 * min(1.0, (stock_cv or 0.0) / 1.0)
    )
    reliability_occurrence = clamp01(
        0.02
        + 1.50 * max(0.0, 1.0 - (reliability_mean if reliability_mean is not None else 1.0))
        + 3.00 * (loss_mean or 0.0)
        + 0.20 * min(1.0, (reliability_cv or 0.0) / 0.05)
    )
    dependency_occurrence = clamp01(0.04 + 0.20 * local_criticality + (0.08 if sole_source_pairs > 0 else 0.0))
    external_enabled = bool(economic_policy.get("external_procurement_enabled"))
    external_occurrence = clamp01((0.08 + 0.20 * impact_score) if external_enabled else 0.0)

    categories = [
        {
            "category": "Derive lead time",
            "occurrence": lead_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(comparable_lead_pairs), has_criticality=criticality_row is not None),
            "evidence": (
                f"retards={len(late_pairs)}/{len(comparable_lead_pairs)} ; "
                f"P(retard)={fmt_pct((delay_probability or 0.0) * 100.0)} ; "
                f"retard moyen={fmt_days(avg_delay_days, 1)} ; CV={lead_cv:.3f}" if lead_cv is not None
                else f"retards={len(late_pairs)}/{len(comparable_lead_pairs)} ; donnees lead insuffisantes"
            ),
            "sensitivity": "lead_time x1.0/x1.1/x1.25/x1.5",
        },
        {
            "category": "Stress capacite",
            "occurrence": capacity_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_capacity_rows), has_criticality=criticality_row is not None),
            "evidence": (
                f"util max={fmt_pct((max_util or 0.0) * 100.0)} ; "
                f"util active={fmt_pct((avg_active_util or 0.0) * 100.0)} ; "
                f"CV util={util_cv:.3f}" if util_cv is not None
                else f"util max={fmt_pct((max_util or 0.0) * 100.0)} ; donnees capacite limitees"
            ),
            "sensitivity": "capacity x1.0/x0.9/x0.8/x0.7/x0.5",
        },
        {
            "category": "Fragilite stock fournisseur",
            "occurrence": stock_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_stock_rows), has_criticality=criticality_row is not None),
            "evidence": (
                f"P(stock=0)={fmt_pct((stock_zero_probability or 0.0) * 100.0)} ; "
                f"P10 stock={fmt_qty(stock_p10, 1)} ; CV={stock_cv:.3f}" if stock_cv is not None
                else f"P(stock=0)={fmt_pct((stock_zero_probability or 0.0) * 100.0)} ; donnees stock limitees"
            ),
            "sensitivity": "stock x1.0/x0.75/x0.5/x0.25/x0",
        },
        {
            "category": "Fiabilite / qualite",
            "occurrence": reliability_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_shipment_rows), has_criticality=criticality_row is not None),
            "evidence": (
                f"reliability moyenne={fmt_pct((reliability_mean or 0.0) * 100.0)} ; "
                f"perte moyenne={fmt_pct((loss_mean or 0.0) * 100.0, 2)} ; "
                f"CV={reliability_cv:.3f}" if reliability_cv is not None
                else f"reliability moyenne={fmt_pct((reliability_mean or 0.0) * 100.0)} ; donnees qualite limitees"
            ),
            "sensitivity": "reliability x1.0/x0.99/x0.97/x0.95",
        },
        {
            "category": "Dependance / criticite locale",
            "occurrence": dependency_occurrence,
            "impact": max(impact_score, local_criticality),
            "confidence": confidence(1 if criticality_row else 0, has_criticality=criticality_row is not None),
            "evidence": (
                f"local={local_criticality:.3f} ; overall={overall_criticality:.3f} ; "
                f"sourcing={fmt_pct(observed_share * 100.0)} ; sole_source={sole_source_pairs}"
            ),
            "sensitivity": "desactiver fournisseur / doubler source / share alternative",
        },
        {
            "category": "Contrainte external market",
            "occurrence": external_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_nominal_rows), has_criticality=criticality_row is not None),
            "evidence": (
                "external procurement actif dans la politique" if external_enabled
                else "external procurement non actif pour ce diagnostic passif"
            ),
            "sensitivity": "external cap x1/x0.75/x0.5 ; external lead x1/x1.5",
        },
    ]
    for row in categories:
        row["expected"] = clamp01(float(row["occurrence"]) * float(row["impact"]) * float(row["confidence"]))
    categories.sort(key=lambda row: float(row["expected"]), reverse=True)

    rows_html = []
    for row in categories:
        expected = float(row["expected"])
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(row['category']))}</td>"
            f"<td>{fmt_pct(float(row['occurrence']) * 100.0)}</td>"
            f"<td>{fmt_pct(float(row['impact']) * 100.0)}</td>"
            f"<td>{fmt_pct(float(row['confidence']) * 100.0)}</td>"
            f"<td>{fmt_pct(expected * 100.0)}</td>"
            f"<td>{html.escape(risk_level(expected))}</td>"
            f"<td>{html.escape(str(row['evidence']))}</td>"
            f"<td>{html.escape(str(row['sensitivity']))}</td>"
            "</tr>"
        )

    sensitivity_rows = [
        ("1", "Capacite fournisseur", "x1.0, x0.9, x0.8, x0.7, x0.5", "tester le seuil de saturation sans changer le nominal"),
        ("2", "Stock fournisseur", "x1.0, x0.75, x0.5, x0.25, x0", "identifier le stock minimum qui preserve service, backlog et cibles"),
        ("3", "Lead time", "x1.0, x1.1, x1.25, x1.5", "mesurer la sensibilite aux retards et derive de delai"),
        ("4", "Fiabilite / qualite", "x1.0, x0.99, x0.97, x0.95", "simuler pertes, retours, release qualite et quantite utile"),
        ("5", "External market", "cap x1/x0.75/x0.5 ; lead x1/x1.5", "contraindre la source externe avant activation productive"),
    ]
    sensitivity_html = "".join(
        "<tr>"
        f"<td>{html.escape(priority)}</td>"
        f"<td>{html.escape(parameter)}</td>"
        f"<td>{html.escape(grid)}</td>"
        f"<td>{html.escape(reason)}</td>"
        "</tr>"
        for priority, parameter, grid, reason in sensitivity_rows
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - prediction passive des risques fournisseur</div>",
            "<div class=\"orderLedgerStatus\">Lecture seule: les probabilites ci-dessous ne pilotent pas la simulation courante.</div>",
            "<div class=\"orderLedgerStatus\">Principe: occurrence estimee x impact local x confiance donne un score attendu, puis la grille de sensibilite propose les premiers stress tests a lancer.</div>",
            "<div class=\"orderLedgerSectionTitle\">Introduction - etude de sensibilite recommandee</div>",
            "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
            "<thead><tr><th>Priorite</th><th>Parametre</th><th>Grille proposee</th><th>Objectif</th></tr></thead>",
            f"<tbody>{sensitivity_html}</tbody>",
            "</table></div>",
            "<div class=\"orderLedgerSectionTitle\">Prediction passive par categorie</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau de prediction passive des risques fournisseur avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            "<colgroup>"
            "<col style=\"width:175px\"><col style=\"width:105px\"><col style=\"width:95px\"><col style=\"width:105px\">"
            "<col style=\"width:105px\"><col style=\"width:85px\"><col style=\"width:320px\"><col style=\"width:260px\">"
            "</colgroup>",
            "<thead><tr><th>Categorie</th><th>Occurrence</th><th>Impact</th><th>Confiance</th><th>Score attendu</th><th>Niveau</th><th>Preuves / signaux</th><th>Sensibilite a lancer</th></tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )


def render_supplier_nominal_parameters_html(
    node_id: str,
    nominal_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    if not visible_rows:
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - parametres nominaux fournisseur</div>"
            "<div class=\"panelEmptyState\">Aucun parametre nominal fournisseur disponible pour ce noeud.</div>"
            "</div>"
        )

    sorted_rows = sorted(
        visible_rows,
        key=lambda row: (
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("edge_id") or ""),
        ),
    )
    rows_html: list[str] = []
    for row in sorted_rows:
        item_id = str(row.get("item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        dst_node_id = str(row.get("dst_node_id") or "n/a")
        uom = str(row.get("uom") or "n/a")
        cap_scale = to_float(row.get("applied_capacity_scale"))
        cap_scale_text = f"x{fmt_qty(cap_scale, 1)}" if cap_scale is not None and not math.isnan(cap_scale) else "n/a"
        neutral_cap = to_float(row.get("neutral_capacity_floor_qty_per_day"))
        tested_cap = to_float(row.get("tested_capacity_floor_qty_per_day"))
        displayed_cap_floor = tested_cap if tested_cap is not None and not math.isnan(tested_cap) and tested_cap > 0.0 else neutral_cap
        neutral_cap_scale = to_float(row.get("neutral_capacity_scale_if_nominal"))
        neutral_cap_scale_text = (
            f"x{fmt_qty(neutral_cap_scale, 1)}"
            if neutral_cap_scale is not None and not math.isnan(neutral_cap_scale) and neutral_cap_scale > 0.0
            else "n/a"
        )
        current_headroom = to_float(row.get("current_capacity_headroom_vs_tested_floor"))
        if current_headroom is None or math.isnan(current_headroom):
            current_headroom = to_float(row.get("current_capacity_headroom_factor"))
        current_headroom_text = (
            f"x{fmt_qty(current_headroom, 1)}"
            if current_headroom is not None and not math.isnan(current_headroom)
            else "n/a"
        )
        industrial_cap = to_float(row.get("industrial_nominal_capacity_qty_per_day"))
        industrial_util = to_float(row.get("industrial_peak_utilization_if_nominal"))
        industrial_target = to_float(row.get("industrial_capacity_target_utilization"))
        industrial_headroom = to_float(row.get("current_capacity_headroom_vs_industrial_nominal"))
        industrial_target_text = (
            fmt_pct(industrial_target * 100.0)
            if industrial_target is not None and not math.isnan(industrial_target)
            else "n/a"
        )
        industrial_headroom_text = (
            f"x{fmt_qty(industrial_headroom, 1)}"
            if industrial_headroom is not None and not math.isnan(industrial_headroom)
            else "n/a"
        )
        upstream_cap = to_float(row.get("external_procurement_nominal_capacity_qty_per_day"))
        upstream_need = to_float(row.get("external_procurement_daily_need_qty"))
        upstream_target = to_float(row.get("external_procurement_target_utilization"))
        upstream_seed = to_float(row.get("external_procurement_initial_pipeline_seed_qty"))
        upstream_target_text = (
            fmt_pct(upstream_target * 100.0)
            if upstream_target is not None and not math.isnan(upstream_target) and upstream_target > 0.0
            else "n/a"
        )
        stock_scale = to_float(row.get("neutral_opening_stock_scale"))
        stock_scale_text = (
            f"x{fmt_qty(stock_scale, 2)}"
            if stock_scale is not None and not math.isnan(stock_scale)
            else "n/a"
        )
        util_pct = to_float(row.get("max_capacity_utilization"))
        otif = to_float(row.get("nominal_reliability_otif"))
        mrp_share = to_float(row.get("mrp_share"))
        lead_title = " | ".join(
            part
            for part in [
                f"type={row.get('lead_time_type') or 'n/a'}",
                f"source={row.get('lead_time_source') or 'n/a'}",
                f"stages={row.get('lead_time_stages') or 'n/a'}",
            ]
            if part
        )
        reliability_title = f"source={row.get('reliability_source') or 'n/a'}"
        capacity_title = (
            f"basis={row.get('capacity_basis') or 'n/a'} | "
            f"explicit={fmt_qty(row.get('explicit_capacity_qty_per_day'), 1)} | "
            f"process={fmt_qty(row.get('process_capacity_qty_per_day'), 1)} | "
            f"downstream_req={fmt_qty(row.get('downstream_requirement_qty_per_day'), 1)}"
        )
        neutral_capacity_title = (
            f"Seuil neutre: {row.get('capacity_floor_basis') or 'n/a'} | "
            f"cap min observee={fmt_qty(neutral_cap, 1)} | "
            f"profil industriel={row.get('industrial_capacity_profile') or 'n/a'} | "
            f"scale actuel={cap_scale_text} | "
            f"capacite actuelle={fmt_qty(row.get('effective_capacity_qty_per_day'), 1)}"
        )
        upstream_capacity_title = (
            "Contrainte amont EXTERNAL_MARKET: besoin journalier baseline / taux cible; "
            f"besoin={fmt_qty(upstream_need, 1)}/j | "
            f"profil={row.get('external_procurement_capacity_profile') or 'n/a'} | "
            f"base={row.get('external_procurement_capacity_basis') or 'n/a'} | "
            f"pipeline ouvert={fmt_qty(upstream_seed, 1)}"
        )
        neutral_stock_title = (
            "Stock initial minimal analytique pour garder les expeditions observees faisables; "
            f"reductible={fmt_qty(row.get('neutral_opening_stock_reducible_qty'), 1)}"
        )
        cells = [
            (item_label, f"Item complet: {item_label} ({item_id})"),
            (dst_node_id, f"Destination: {dst_node_id} | edge={row.get('edge_id') or 'n/a'}"),
            (uom, ""),
            (fmt_qty(row.get("simulated_opening_stock_qty"), 1), "stock source au demarrage simule"),
            (fmt_qty(row.get("neutral_opening_stock_floor_qty"), 1), neutral_stock_title),
            (stock_scale_text, neutral_stock_title),
            (fmt_qty(row.get("effective_capacity_qty_per_day"), 1), capacity_title),
            (fmt_qty(industrial_cap, 1), neutral_capacity_title),
            (industrial_target_text, neutral_capacity_title),
            (fmt_qty(upstream_cap, 1), upstream_capacity_title),
            (upstream_target_text, upstream_capacity_title),
            (fmt_days(row.get("external_procurement_lead_days"), 1), upstream_capacity_title),
            (fmt_qty(upstream_seed, 1), upstream_capacity_title),
            (fmt_pct((industrial_util or 0.0) * 100.0) if industrial_util is not None and not math.isnan(industrial_util) else "n/a", neutral_capacity_title),
            (industrial_headroom_text, neutral_capacity_title),
            (fmt_qty(displayed_cap_floor, 1), neutral_capacity_title),
            (neutral_cap_scale_text, neutral_capacity_title),
            (current_headroom_text, neutral_capacity_title),
            (str(row.get("capacity_basis") or "n/a"), capacity_title),
            (fmt_pct((util_pct or 0.0) * 100.0) if util_pct is not None and not math.isnan(util_pct) else "n/a", "utilisation capacite max observee"),
            (fmt_days(row.get("planned_lead_time_days"), 1), lead_title),
            (fmt_pct((otif or 0.0) * 100.0) if otif is not None and not math.isnan(otif) else "n/a", reliability_title),
            (fmt_pct((mrp_share or 0.0) * 100.0) if mrp_share is not None and not math.isnan(mrp_share) else "n/a", "part de sourcing MRP nominale"),
            (fmt_qty(row.get("total_shipped_qty"), 1), "quantite totale expediee sur le run"),
        ]
        numeric_columns = set(range(3, 18)) | {19, 20, 21, 22, 23}
        row_tds: list[str] = []
        for idx, (value, title) in enumerate(cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(title), quote=True)}"' if title else ""
            row_tds.append(f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>')
        rows_html.append("<tr>" + "".join(row_tds) + "</tr>")

    headers = [
        "Item",
        "Destination",
        "UOM",
        "Stock ouv.",
        "Stock min neutre",
        "Scale stock",
        "Cap actuelle/j",
        "Cap nominale cible/j",
        "Taux cible",
        "Cap amont/j",
        "Util amont",
        "Delai amont",
        "Pipeline amont ouv.",
        "Util pic cible",
        "Marge cible",
        "Cap validee baseline/j",
        "Facteur validation",
        "Marge actuelle",
        "Base capacite",
        "Util max",
        "Delai prev.",
        "OTIF",
        "Share MRP",
        "Expedie total",
    ]
    table_header = "".join(f"<th>{html.escape(label)}</th>" for label in headers)
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [
            95, 110, 70, 115, 125, 95, 130, 125, 90, 125, 95, 105,
            135, 105, 115, 135, 95, 120, 175, 95, 105, 90, 95, 130,
        ]
    )
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - parametres nominaux fournisseur</div>",
            f"<div class=\"orderLedgerStatus\">Lignes fournisseur affichees: {len(sorted_rows)}. Cap actuelle/j = limite utilisee par le run actif; Cap nominale cible/j = pic observe / taux cible; Cap validee baseline/j = plus petite capacite testee qui conserve la baseline sans binding.</div>",
            "<div class=\"orderLedgerStatus\">Profils cible: raw material qualifie ~= 70%, high lead ~= 65%, packaging qualifie ~= 75%. Cap amont/j contraint EXTERNAL_MARKET avec le meme taux cible, et le pipeline amont ouvre les commandes deja en route au demarrage.</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau des parametres nominaux fournisseur avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            f"<colgroup>{table_cols}</colgroup>",
            f"<thead><tr>{table_header}</tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )


def render_factory_nominal_capacities_html(
    node_id: str,
    capacity_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("output_item_id") or ""))
    ]
    if not visible_rows:
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - capacites nominales usine</div>"
            "<div class=\"panelEmptyState\">Aucune capacite nominale usine disponible pour ce noeud.</div>"
            "</div>"
        )

    rows_html: list[str] = []
    for row in sorted(visible_rows, key=lambda r: (str(r.get("output_item_id") or ""), str(r.get("process_id") or ""))):
        item_id = str(row.get("output_item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        target_util = to_float(row.get("industrial_capacity_target_utilization"))
        peak_util_indus = to_float(row.get("industrial_peak_utilization_if_nominal"))
        current_max_util = to_float(row.get("current_max_utilization"))
        headroom = to_float(row.get("current_capacity_headroom_vs_industrial_nominal"))
        current_capacity = to_float(row.get("current_capacity_qty_per_day"))
        industrial_capacity = to_float(row.get("industrial_nominal_capacity_qty_per_day"))
        current_capacity_text = (
            fmt_qty(current_capacity, 1)
            if current_capacity is not None and not math.isnan(current_capacity) and current_capacity > 0.0
            else "non modelisee"
        )
        headroom_text = (
            f"x{fmt_qty(headroom, 2)}"
            if headroom is not None and not math.isnan(headroom)
            else "n/a"
        )
        title = (
            f"profil={row.get('industrial_capacity_profile') or 'n/a'} | "
            f"source={row.get('capacity_source') or 'n/a'} | "
            f"mode={row.get('current_capacity_limit_mode') or 'n/a'}"
        )
        cells = [
            (item_label, f"Item complet: {item_label} ({item_id})"),
            (str(row.get("process_id") or "n/a"), title),
            (str(row.get("uom") or "n/a"), ""),
            (current_capacity_text, title),
            (fmt_qty(industrial_capacity, 1), title),
            (fmt_pct((target_util or 0.0) * 100.0) if target_util is not None and not math.isnan(target_util) else "n/a", title),
            (fmt_pct((peak_util_indus or 0.0) * 100.0) if peak_util_indus is not None and not math.isnan(peak_util_indus) else "n/a", title),
            (headroom_text, title),
            (fmt_qty(row.get("max_actual_qty_per_day"), 1), "pic journalier produit observe"),
            (fmt_qty(row.get("total_actual_qty"), 1), "production totale observee"),
            (fmt_pct((current_max_util or 0.0) * 100.0) if current_max_util is not None and not math.isnan(current_max_util) else "n/a", "utilisation max de la capacite actuelle"),
            (str(row.get("capacity_binding_days") or "0"), "jours ou la capacite usine est cause de binding"),
            (str(row.get("input_shortage_days") or "0"), "jours ou les intrants limitent l'execution"),
            (str(row.get("lot_policy_mode") or "n/a"), "politique de lot observee"),
        ]
        numeric_columns = {3, 4, 5, 6, 7, 8, 9, 10, 11, 12}
        row_tds: list[str] = []
        for idx, (value, cell_title) in enumerate(cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(cell_title), quote=True)}"' if cell_title else ""
            row_tds.append(f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>')
        rows_html.append("<tr>" + "".join(row_tds) + "</tr>")

    headers = [
        "Output",
        "Process",
        "UOM",
        "Cap actuelle/j",
        "Cap nominale cible/j",
        "Taux cible",
        "Util pic cible",
        "Marge actuelle",
        "Pic produit/j",
        "Produit total",
        "Util max actuelle",
        "Jours capacite",
        "Jours intrants",
        "Lot",
    ]
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [110, 140, 80, 130, 130, 95, 105, 115, 120, 125, 120, 105, 105, 95]
    )
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - capacites nominales usine</div>",
            "<div class=\"orderLedgerStatus\">Cap actuelle/j = limite du JSON actif; Cap nominale cible/j = pic journalier produit / taux cible pharma. Le taux cible par defaut est 70% pour une usine GMP multi-produits ou un site interne semi-fini.</div>",
            "<div class=\"orderLedgerStatus\">Pour les usines, appliquer directement la capacite nominale cible peut changer le cadencement interne; elle est donc affichee comme lecture de sensibilite, pas comme remplacement automatique de la baseline.</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau des capacites nominales usine avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            f"<colgroup>{table_cols}</colgroup>",
            f"<thead><tr>{''.join(f'<th>{html.escape(label)}</th>' for label in headers)}</tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
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


def densify_event_spike_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    if not points:
        return []
    by_day: dict[int, float] = defaultdict(float)
    for day, value in points:
        by_day[int(day)] += float(value)
    spike_points: list[tuple[int, float]] = []
    for day, value in sorted(by_day.items()):
        spike_points.extend([(day, 0.0), (day, value), (day, 0.0)])
    return spike_points


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
    event_like: bool = False,
    note: str | None = None,
    series_styles: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    usable = {
        label: (densify_event_spike_series(pts) if event_like else densify_daily_series(pts) if step_like else pts)
        for label, pts in series_map.items()
        if pts
    }
    if not usable:
        return None
    series_payload = []
    for label, points in usable.items():
        style = series_styles.get(label, {}) if isinstance(series_styles, dict) else {}
        show_markers = bool(style.get("show_markers")) or len(points) <= 2
        series_payload.append(
            {
                "label": label,
                "days": [int(day) for day, _ in points],
                "values": [float(value) for _, value in points],
                "show_markers": show_markers,
                **style,
            }
        )
    return {
        "kind": "line_multi",
        "title": title,
        "y_label": y_label,
        "step_like": step_like and not event_like,
        "note": note or "",
        "series": series_payload,
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
    top_step_like: bool = False,
    top_event_like: bool = False,
    bottom_step_like: bool = False,
    bottom_event_like: bool = False,
) -> dict[str, Any] | None:
    top_figure = build_line_chart_figure(
        top_series_map,
        title=top_title,
        y_label=top_y_label,
        step_like=top_step_like,
        event_like=top_event_like,
    )
    bottom_figure = build_line_chart_figure(
        bottom_series_map,
        title=bottom_title,
        y_label=bottom_y_label,
        step_like=bottom_step_like,
        event_like=bottom_event_like,
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
    top_extra_traces: list[dict[str, Any]] | None = None,
    bottom_extra_traces: list[dict[str, Any]] | None = None,
    show_legend: bool = False,
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
            "extra_traces": top_extra_traces or [],
        },
        "bottom": {
            "title": bottom_title,
            "x_label": bottom_x_label,
            "y_label": bottom_y_label,
            "kind": bottom_kind,
            "x": bottom_x,
            "y": bottom_y,
            "extra_traces": bottom_extra_traces or [],
        },
        "show_legend": show_legend,
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


def read_timeline_horizon_days(output_root: Path) -> int | None:
    summary_file = output_root / "summaries" / "first_simulation_summary.json"
    if not summary_file.exists():
        return None
    try:
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(summary, dict):
        return None
    for key in ("timeline_days", "sim_days", "total_simulated_timeline_days"):
        value = to_float(summary.get(key))
        if value is not None and value > 0:
            return int(math.ceil(value))
    return None


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

def render_global_model_equations_html() -> str:
    def table(rows: list[tuple[str, str, str]]) -> str:
        body = "".join(
            "<tr>"
            f"<td>{html.escape(label)}</td>"
            f"<td><code>{html.escape(equation)}</code></td>"
            f"<td>{html.escape(reading)}</td>"
            "</tr>"
            for label, equation, reading in rows
        )
        return (
            "<div class=\"modelEquationTableWrap\">"
            "<table class=\"modelEquationTable\">"
            "<thead><tr><th>Objet</th><th>Equation / definition</th><th>Lecture</th></tr></thead>"
            f"<tbody>{body}</tbody>"
            "</table>"
            "</div>"
        )

    sections = [
        (
            "1. Lecture du modele",
            table(
                [
                    ("1. Demande client", "D[c,i](t)", "Le simulateur lit chaque jour la demande client par produit fini."),
                    ("2. Service aval", "Served[c,i](t)", "Le stock disponible sert la demande ; ce qui n'est pas servi devient backlog."),
                    ("3. Signal production", "ReqProd[p,s](t)", "La demande aval et les besoins des process aval creent un signal de production par site et produit."),
                    ("4. Plan de production", "MPS[p,s](t) puis PlanLot[p,s](t)", "Le signal est transforme en commande de production, lissee, puis arrondie par regles de lot/campagne."),
                    ("5. Besoin composant", "Req_BOM[s,i](t)", "La BOM transforme le plan de production en besoin de matieres ou semi-finis."),
                    ("6. Decision MRP", "T[n,i](t), IP[n,i](t), Gap[n,i](t), BN[n,i](t)", "Le MRP compare cible, stock et receptions futures pour savoir s'il faut commander."),
                    ("7. Ordre fournisseur", "Q[f,i](t)", "Le besoin net est reparti sur les flux d'approvisionnement puis normalise par lot ou quantite standard."),
                    ("8. Transport et reception", "Ship[f,i](t), Recv[f,i](t)", "La source expedie ce qu'elle peut ; la destination recoit apres le delai simule."),
                    ("9. Etat suivant", "Etat(t+1)", "Stocks, transit, carnet ouvert et backlog sont mis a jour ; le jour suivant repart de ce nouvel etat."),
                ]
            ),
        ),
        (
            "2. Indices",
            table(
                [
                    ("t", "jour courant ; t+1 = etat apres execution du jour t", "Le simulateur avance au pas journalier."),
                    ("c", "client", "Noeud aval qui porte la demande exogene."),
                    ("n", "noeud", "Fournisseur, usine, centre de distribution ou client."),
                    ("s", "site industriel", "Usine ou site de production."),
                    ("i", "item", "Matiere premiere, semi-fini ou produit fini."),
                    ("p", "produit/process", "Produit fabrique par un process."),
                    ("f", "flux source -> destination", "Arc logistique qui transporte un item."),
                ]
            ),
        ),
        (
            "3. Parametres et constantes du scenario",
            table(
                [
                    ("alpha", "production_smoothing", "Coefficient de lissage de la commande de production. Plus alpha est haut, plus la production reagit lentement."),
                    ("production_gap_gain", "gain applique a GapProd[p,s](t)", "Part de l'ecart de stock que l'on cherche a rattraper dans la commande brute."),
                    ("fg_target_days", "jours de couverture produits finis", "Transforme le signal de production en cible de stock sortie usine."),
                    ("SS_qty[n,i]", "stock securite explicite", "Quantite de securite issue des donnees MRP quand elle existe."),
                    ("ST_days[n,i]", "delai de securite MRP", "Nombre de jours de signal MRP a couvrir en securite."),
                    ("Cover_days[n,i]", "couverture appro", "Nombre de jours de signal MRP a maintenir en stock cible pour couvrir le delai previsionnel d'approvisionnement."),
                    ("LotPolicy[p,s]", "lot fixe, min, max, multiple, max lots/semaine", "Regles industrielles qui transforment une commande continue en campagne lotifiee."),
                    ("SourcingShare[f,i]", "part de sourcing du flux", "Part du besoin net affectee a chaque source amont active."),
                    ("LT_ref[f]", "delai previsionnel MRP", "Delai utilise pour lire les dates previsionnelles du carnet."),
                    ("LT_sim[f,t]", "delai simule", "Delai effectivement applique a l'expedition pour calculer la reception reelle."),
                    ("Capacite", "capacite fournisseur ou usine", "Borne physique appliquee a l'expedition ou a la production si elle est modelisee."),
                ]
            ),
        ),
        (
            "4. Variables d'etat portees d'un jour a l'autre",
            table(
                [
                    ("S[n,i](t)", "stock disponible au noeud n pour l'item i", "Variable d'etat principale: elle est recalculee en t+1."),
                    ("B[n,i](t)", "backlog ou besoin non servi au noeud n", "Retard reporte d'un jour au suivant."),
                    ("IT[f,i](t)", "quantite en transit sur le flux f", "Quantite deja expediee mais pas encore disponible a destination."),
                    ("OO[f,i](t)", "carnet ouvert sur le flux f", "Ordres crees mais pas encore completement recus."),
                    ("OC[p,s](t)", "reste de campagne ouverte pour le produit p sur le site s", "Quantite deja lancee en campagne mais pas encore executee."),
                ]
            ),
        ),
        (
            "5. Demande et service client",
            table(
                [
                    ("Demande", "D[c,i](t)", "Demande client exogene de l'item i au client c le jour t."),
                    ("Besoin client", "Need[c,i](t) = D[c,i](t) + B[c,i](t)", "Demande du jour plus backlog entrant."),
                    ("Service", "Served[c,i](t) = min(S[c,i](t), Need[c,i](t))", "Quantite livree au client selon le stock disponible."),
                    ("Backlog", "B[c,i](t+1) = Need[c,i](t) - Served[c,i](t)", "Retard client reporte au jour suivant."),
                    ("Signal aval", "Req[c,i](t) = Need[c,i](t)", "Point de depart de la propagation du besoin vers l'amont."),
                ]
            ),
        ),
        (
            "6. Variables auxiliaires de production",
            table(
                [
                    ("ReqProd[p,s](t)", "signal aval retenu pour produire p sur le site s", "Maximum entre demande propagee et besoin des process aval."),
                    ("TProd[p,s](t)", "cible stock du produit fabrique", "Stock que le site cherche a maintenir pour le produit p."),
                    ("GapProd[p,s](t)", "ecart sortie = cible - stock", "Positif: manque a rattraper ; negatif: avance de stock."),
                    ("RawProd[p,s](t)", "commande brute avant lissage", "Besoin courant corrige par l'ecart de stock."),
                    ("MPS[p,s](t)", "commande de production simulee lissee", "Signal de production apres lissage temporel."),
                    ("LotRef[p,s]", "taille de lot de reference", "Lot fixe si present, sinon max/min/multiple selon la politique."),
                    ("OC[p,s](t)", "reste de campagne ouverte", "Quantite deja lancee en campagne mais pas encore fabriquee."),
                    ("IntrantsDisponibles[p,s](t)", "maximum produisible avec les stocks entrants", "Limite calculee a partir des stocks intrants et des coefficients BOM."),
                ]
            ),
        ),
        (
            "7. Equations de production et propagation BOM",
            table(
                [
                    ("Signal production", "ReqProd[p,s](t) = max(Req_aval[p,s](t), Req_process_aval[p,s](t))", "Signal aval retenu pour produire: demande client propagee ou besoin d'un process aval."),
                    ("Cible sortie", "TProd[p,s](t) = max(BaseStock[s,p], fg_target_days * ReqProd[p,s](t))", "Stock cible du produit fabrique par le site."),
                    ("Ecart sortie", "GapProd[p,s](t) = TProd[p,s](t) - S[s,p](t)", "Manque ou avance de stock sur le produit fabrique."),
                    ("Commande brute", "RawProd[p,s](t) = ReqProd[p,s](t) + production_gap_gain * GapProd[p,s](t)", "Production demandee avant lissage: besoin courant plus correction de stock."),
                    ("Commande lissee", "MPS[p,s](t) = max(0, alpha * MPS[p,s](t-1) + (1-alpha) * RawProd[p,s](t))", "alpha est production_smoothing ; cela evite des a-coups trop forts."),
                    ("Declenchement lot", "si S[s,p](t) > TProd[p,s](t) - LotRef[p,s] alors nouveau lot differe", "On evite de lancer un lot complet si le stock est encore dans la bande cible."),
                    ("Plan lotifie", "PlanLot[p,s](t) = CampaignRule(MPS[p,s](t), LotPolicy[p,s], OC[p,s](t), LotsWeek[p,s])", "Application des lots fixes, minimums, multiples, campagnes ouvertes et limite de lots/semaine."),
                    ("Intrants disponibles", "IntrantsDisponibles[p,s](t) = min_i S[s,i](t) / BOM[i,p]", "Maximum produisible compte tenu des intrants modelises et des ratios BOM."),
                    ("Production executable", "Prod[p,s](t) = min(PlanLot[p,s](t), Capacite[p,s](t), IntrantsDisponibles[p,s](t))", "Production reellement faite selon capacite et intrants disponibles."),
                    ("Besoin composant MRP", "Req_BOM[s,i](t) = somme_p BOM[i,p] * PlanLot[p,s](t)", "Signal composant utilise pour commander l'amont."),
                    ("Consommation physique", "Cons[s,i](t) = somme_p BOM[i,p] * Prod[p,s](t)", "Consommation qui decremente vraiment le stock intrant."),
                ]
            ),
        ),
        (
            "8. Variables auxiliaires et decision MRP",
            table(
                [
                    ("Signal MRP", "Req[n,i](t)", "Signal journalier utilise pour dimensionner la cible: demande client, MPS/BOM ou demande propagee."),
                    ("Receptions futures", "RecvPrev[n,i](t) = somme_tau>t Recv[n,i](tau)", "Quantites deja commandees ou en transit vers le noeud."),
                    ("Position inventaire", "IP[n,i](t) = S[n,i](t) + RecvPrev[n,i](t)", "Stock disponible plus receptions futures deja planifiees."),
                    ("Cible MRP", "T[n,i](t) = max(SS_qty[n,i], ST_days[n,i] * Req[n,i](t), Cover_days[n,i] * Req[n,i](t), Target_business[n,i])", "On retient la cible active la plus contraignante."),
                    ("Ecart", "Gap[n,i](t) = T[n,i](t) + B[n,i](t) - IP[n,i](t)", "Quantite restant a couvrir apres stock et commandes deja prevues."),
                    ("Besoin net", "BN[n,i](t) = Gap[n,i](t) si Gap[n,i](t) > 0 ; sinon 0", "Le MRP ne commande que si la position inventaire ne couvre pas la cible."),
                ]
            ),
        ),
        (
            "9. Sourcing, ordre et transport",
            table(
                [
                    ("Ordre flux", "Q[f,i](t) = LotRule(SourcingShare[f,i] * BN[dst(f),i](t))", "Besoin net affecte au flux puis normalise par lot ou quantite standard."),
                    ("Expedition", "Ship[f,i](t) = min(Q[f,i](t), S[src(f),i](t), Capacite[src(f),i](t))", "Quantite sortie du stock source et envoyee vers la destination."),
                    ("Transit", "IT[f,i](t+1) = IT[f,i](t) + Ship[f,i](t) - Recv[f,i](t)", "Quantite en route entre source et destination."),
                    ("Reception", "Recv[f,i](t + LT_sim[f,t]) = Ship[f,i](t)", "Reception effective apres delai simule; le carnet affiche aussi t + LT_ref[f]."),
                    ("Carnet ouvert", "OO[f,i](t+1) = OO[f,i](t) + Q[f,i](t) - Recv[f,i](t)", "Ordres encore non recus en fin de jour."),
                ]
            ),
        ),
        (
            "10. Exemple numerique MRP simple",
            table(
                [
                    ("Hypothese", "T[n,i](t)=180 ; S[n,i](t)=100 ; RecvPrev[n,i](t)=30 ; B[n,i](t)=0", "La cible est 180, mais 100 sont deja en stock et 30 sont deja prevus en reception."),
                    ("Position inventaire", "IP[n,i](t)=100+30=130", "Stock + receptions futures deja planifiees."),
                    ("Ecart", "Gap[n,i](t)=180+0-130=50", "Il manque 50 pour couvrir la cible."),
                    ("Besoin net", "BN[n,i](t)=50", "Comme l'ecart est positif, le MRP peut creer une commande de 50 avant regles de lot/sourcing."),
                    ("Cas inverse", "si IP[n,i](t)=190 alors Gap=-10 et BN=0", "Le simulateur ne commande pas si le stock et les receptions futures couvrent deja la cible."),
                ]
            ),
        ),
        (
            "11. Flux journaliers qui modifient les stocks",
            table(
                [
                    ("Recv[n,i](t)", "receptions[n,i](t)", "Quantite de l'item i qui devient disponible au noeud n le jour t apres transport ou ordre ouvert."),
                    ("Prod[n,i](t)", "production[n,i](t)", "Quantite de l'item i fabriquee par le noeud n le jour t. C'est la production reelle executee, pas le signal MPS."),
                    ("Cons[n,i](t)", "consommations[n,i](t)", "Quantite de l'item i consommee comme intrant BOM par la production reelle du jour."),
                    ("Ship[n,i](t)", "expeditions[n,i](t)", "Quantite de l'item i sortie du stock du noeud n et envoyee vers un autre noeud ou le client."),
                    ("Served[c,i](t)", "service client", "Cas particulier de sortie aval: quantite livree au client depuis le stock disponible."),
                    ("Req_BOM[s,i](t)", "besoin composant MRP", "Signal de commande amont calcule sur le plan lotifie ; ce n'est pas une consommation physique tant que la production n'est pas executee."),
                ]
            ),
        ),
        (
            "12. Equations de la dynamique et mise a jour",
            table(
                [
                    ("Stock general", "S[n,i](t+1) = S[n,i](t) + receptions[n,i](t) + production[n,i](t) - consommations[n,i](t) - expeditions[n,i](t)", "Les termes sont definis juste avant: receptions=Recv, production=Prod, consommations=Cons, expeditions=Ship."),
                    ("Campagne ouverte", "OC[p,s](t+1) = OC[p,s](t) + CampaignStart[p,s](t) - Prod[p,s](t)", "Reste de campagne a executer apres production du jour."),
                    ("Simulation chronologique", "Etat(t) -> decisions(t) -> Etat(t+1)", "Pas de solveur global: les regles locales sont appliquees jour apres jour dans le sens du temps."),
                ]
            ),
        ),
        (
            "13. Sorties CSV utiles pour verifier le modele",
            table(
                [
                    ("data/mrp_trace_daily.csv", "T, IP, Gap, BN, RecvPrev, basis", "Permet de verifier les calculs MRP par noeud/item/jour."),
                    ("data/mrp_orders_daily.csv", "Q, source, destination, release_day, arrival_day", "Permet de verifier les ordres lances et leurs dates."),
                    ("data/production_constraint_daily.csv", "desired_qty, planned_qty_after_lot_rule, actual_qty, binding_cause", "Permet de verifier MPS, lotification, contraintes et production reelle."),
                    ("data/production_input_consumption_daily.csv", "Cons[s,i](t)", "Permet de verifier les consommations physiques issues de la BOM."),
                    ("data/production_supplier_shipments_daily.csv", "Ship[f,i](t)", "Permet de verifier les expeditions fournisseurs/source."),
                    ("data/production_input_replenishment_arrivals_daily.csv", "Recv[n,i](t)", "Permet de verifier les receptions d'intrants chez les usines."),
                    ("data/production_demand_service_daily.csv", "D, Served, Backlog", "Permet de verifier demande client, service et retard."),
                ]
            ),
        ),
        (
            "14. Limites du modele global",
            table(
                [
                    ("Optimisation", "pas de solveur APS global", "Les decisions viennent de regles MRP/production locales appliquees chronologiquement."),
                    ("Calendrier atelier", "pas de planning machine detaille", "Les lots et campagnes existent, mais pas encore les equipes, changements de format et indisponibilites fines."),
                    ("Fournisseurs", "stock/capacite/delai modelises", "Les contrats, MOQ reels, allocations et arbitrages fournisseurs restent a valider."),
                    ("Couts", "achats reels + production proxy + couts logistiques hypotheses", "La production est un proxy de cout de conversion pharma alloue sur volumes reels; transport, stockage et urgence restent parametrables tant que les couts industriels reels ne sont pas fournis."),
                ]
            ),
        ),
    ]
    section_html = "".join(
        "<section class=\"modelEquationSection\">"
        f"<h3>{html.escape(title)}</h3>"
        f"{content}"
        "</section>"
        for title, content in sections
    )
    return (
        "<div class=\"modelEquationPanel\">"
        "<p class=\"modelEquationIntro\">"
        "Cette vue decrit le modele complet, pas seulement le noeud selectionne. Elle part de la demande client, transforme cette demande en production, propage les besoins par la BOM, lance les ordres MRP vers l'amont, puis met a jour les stocks, le transit, le carnet ouvert et le backlog."
        "</p>"
        f"{section_html}"
        "</div>"
    )


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
    supplier_stock_flows_csv: Path | None,
    supplier_capacity_csv: Path,
    supplier_nominal_parameters_csv: Path | None,
    factory_nominal_capacities_csv: Path | None,
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
    horizon_days = int(
        to_float(
            summary.get("timeline_days")
            or summary.get("sim_days")
            or summary.get("total_simulated_timeline_days")
            or read_timeline_horizon_days(output_root)
            or 0
        )
        or 0
    )
    horizon_end_day = horizon_days - 1 if horizon_days > 0 else None

    def in_run_horizon(row: dict[str, str], day_field: str = "day") -> bool:
        if horizon_end_day is None:
            return True
        day = int(to_float(row.get(day_field)) or 0)
        return 0 <= day <= horizon_end_day

    mrp_trace_rows = read_csv_rows(data_root / "mrp_trace_daily.csv")
    mrp_order_rows = read_csv_rows(data_root / "mrp_orders_daily.csv")
    assumptions_ledger_rows = read_csv_rows(data_root / "assumptions_ledger.csv")
    supplier_risk_applied_rows = read_csv_rows(data_root / "supplier_risk_events_applied_daily.csv")

    input_rows = read_csv_rows(sim_input_stocks_csv)
    output_rows = read_csv_rows(sim_output_products_csv)
    input_arrival_rows = read_csv_rows(input_arrivals_csv)
    demand_rows = read_csv_rows(demand_service_csv)
    supplier_ship_rows = [row for row in read_csv_rows(supplier_shipments_csv) if in_run_horizon(row)]
    supplier_stock_rows = read_csv_rows(supplier_stocks_csv)
    supplier_stock_flow_rows = (
        read_csv_rows(supplier_stock_flows_csv)
        if supplier_stock_flows_csv is not None and supplier_stock_flows_csv.exists()
        else []
    )
    supplier_local_criticality_rows = (
        read_csv_rows(data_root / "supplier_local_criticality_ranking.csv")
        if (data_root / "supplier_local_criticality_ranking.csv").exists()
        else []
    )
    supplier_capacity_rows = read_csv_rows(supplier_capacity_csv)
    supplier_nominal_rows = (
        read_csv_rows(supplier_nominal_parameters_csv)
        if supplier_nominal_parameters_csv is not None and supplier_nominal_parameters_csv.exists()
        else []
    )
    factory_nominal_capacity_rows = (
        read_csv_rows(factory_nominal_capacities_csv)
        if factory_nominal_capacities_csv is not None and factory_nominal_capacities_csv.exists()
        else []
    )
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

    supplier_nominal_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_nominal_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id:
            supplier_nominal_by_node[node_id].append(row)

    factory_nominal_capacity_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in factory_nominal_capacity_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            factory_nominal_capacity_by_node[node_id].append(row)

    input_arrivals_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_arrival_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            input_arrivals_by_node[node_id].append(row)

    input_stocks_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            input_stocks_by_node[node_id].append(row)

    dc_stocks_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in dc_stock_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            dc_stocks_by_node[node_id].append(row)

    supplier_stocks_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_stock_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            supplier_stocks_by_node[node_id].append(row)

    supplier_stock_flows_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_stock_flow_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            supplier_stock_flows_by_node[node_id].append(row)

    supplier_risk_applied_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_risk_applied_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id:
            supplier_risk_applied_by_node[node_id].append(row)

    supplier_risk_config_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assumptions_ledger_rows:
        if str(row.get("category") or "") != "supplier_risk_event":
            continue
        payload_text = str(row.get("payload_json") or "").strip()
        payload: dict[str, Any] = {}
        if payload_text:
            try:
                decoded = json.loads(payload_text)
                if isinstance(decoded, dict):
                    payload = decoded
            except json.JSONDecodeError:
                payload = {}
        node_id = str(payload.get("supplier_id") or row.get("node_id") or "")
        if node_id:
            supplier_risk_config_by_node[node_id].append(payload)

    supplier_local_criticality_by_node: dict[str, dict[str, str]] = {}
    for row in supplier_local_criticality_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id and node_id not in supplier_local_criticality_by_node:
            supplier_local_criticality_by_node[node_id] = row

    def rows_by_node_item(rows: list[dict[str, str]], *, node_field: str = "node_id") -> dict[tuple[str, str], list[dict[str, str]]]:
        out: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            node_id = str(row.get(node_field) or "")
            item_id = str(row.get("item_id") or "")
            if node_id and item_id:
                out[(node_id, item_id)].append(row)
        return out

    input_rows_by_pair = rows_by_node_item(input_rows)
    output_rows_by_pair = rows_by_node_item(output_rows)
    input_arrivals_by_pair = rows_by_node_item(input_arrival_rows)
    supplier_stock_rows_by_pair = rows_by_node_item(supplier_stock_rows)
    dc_stock_rows_by_pair = rows_by_node_item(dc_stock_rows)

    latest_mrp_trace_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    mrp_trace_rows_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    mrp_trace_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        mrp_trace_by_node[node_id].append(row)
        mrp_trace_rows_by_pair[(node_id, item_id)].append(row)
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
        if not is_display_order_row(row):
            continue
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
        bucket_days: int = 1,
    ) -> list[tuple[int, float]]:
        by_day: dict[int, float] = defaultdict(float)
        for row in rows:
            day = resolved_order_day(row, day_field)
            if bucket_days > 1:
                day = (day // bucket_days) * bucket_days
            by_day[day] += max(0.0, to_float(row.get(field)) or 0.0)
        return sorted(by_day.items())

    def bucket_series_points(points: list[tuple[int, float]], bucket_days: int = 7) -> list[tuple[int, float]]:
        if bucket_days <= 1:
            return points
        by_bucket: dict[int, float] = defaultdict(float)
        for point_day, point_value in points:
            bucket_day = (int(point_day) // bucket_days) * bucket_days
            by_bucket[bucket_day] += float(point_value)
        return sorted(by_bucket.items())

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

    def average_derived_order_series(
        rows: list[dict[str, str]],
        derive_value: Callable[[dict[str, str]], float | None],
    ) -> list[tuple[int, float]]:
        sums: dict[int, float] = defaultdict(float)
        counts: dict[int, int] = defaultdict(int)
        for row in rows:
            day_value = order_placed_day(row)
            if day_value is None:
                continue
            value = derive_value(row)
            if value is None or math.isnan(value):
                continue
            day = int(round(day_value))
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

    def lead_distribution_figure(
        rows: list[dict[str, str]],
        *,
        title: str,
        planned_lead_days: float | None,
    ) -> dict[str, Any] | None:
        lead_qty_rows: list[tuple[float, float]] = []
        for row in rows:
            lead = to_float(row.get("lead_days"))
            if lead is None or math.isnan(lead):
                continue
            lead_qty_rows.append((max(0.0, lead), max(0.0, to_float(row.get("shipped_qty")) or 0.0)))
        if not lead_qty_rows:
            return None
        lead_values = [lead for lead, _ in lead_qty_rows]
        min_lead = min(lead_values)
        max_lead = max(lead_values)
        distinct_leads = sorted({round(lead, 1) for lead in lead_values})
        bucket_width = 1.0
        if len(distinct_leads) > 18:
            bucket_width = max(1.0, math.ceil((max_lead - min_lead + 1.0) / 14.0))

        def bucket_key(lead: float) -> float:
            if bucket_width <= 1.0:
                return float(round(lead))
            bucket_start = math.floor(lead / bucket_width) * bucket_width
            return float(bucket_start + (bucket_width / 2.0))

        counts: dict[float, float] = defaultdict(float)
        qty_by_bucket: dict[float, float] = defaultdict(float)
        for lead, qty in lead_qty_rows:
            key = bucket_key(lead)
            counts[key] += 1.0
            qty_by_bucket[key] += qty
        ordered_keys = sorted(counts)
        x_values = [float(key) for key in ordered_keys]
        top_y = [counts[key] for key in ordered_keys]
        bottom_y = [qty_by_bucket[key] for key in ordered_keys]
        planned_lead = planned_lead_days
        has_planned_lead = planned_lead is not None and not math.isnan(planned_lead) and planned_lead >= 0.0
        top_extra_traces: list[dict[str, Any]] = []
        bottom_extra_traces: list[dict[str, Any]] = []
        if has_planned_lead:
            planned_label = f"Delai transport prevu ({planned_lead:g} j)"
            top_extra_traces.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "name": planned_label,
                    "x": [planned_lead, planned_lead],
                    "y": [0.0, max(top_y) if top_y else 1.0],
                    "line": {"color": "#111827", "dash": "dot", "width": 2.6},
                    "showlegend": True,
                }
            )
            bottom_extra_traces.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "name": planned_label,
                    "x": [planned_lead, planned_lead],
                    "y": [0.0, max(bottom_y) if bottom_y else 1.0],
                    "line": {"color": "#111827", "dash": "dot", "width": 2.6},
                    "showlegend": False,
                }
            )
        return build_dual_panel_figure(
            title=title,
            top_title="Nombre d'expeditions par delai transport simule",
            top_x_label="Delai transport simule (jours)",
            top_y_label="Expeditions",
            top_kind="bar",
            top_x=x_values,
            top_y=top_y,
            bottom_title="Quantite expediee par delai transport simule",
            bottom_x_label="Delai transport simule (jours)",
            bottom_y_label="Quantite",
            bottom_kind="bar",
            bottom_x=x_values,
            bottom_y=bottom_y,
            top_extra_traces=top_extra_traces,
            bottom_extra_traces=bottom_extra_traces,
            show_legend=has_planned_lead,
        )

    def render_mrp_risk_summary_html(
        node_id: str,
        node_type: str,
        *,
        safety_summary: dict[str, Any],
        node_trace_rows: list[dict[str, str]],
        node_orders: list[dict[str, str]],
        stock_rows: list[dict[str, str]],
        supplier_stock_rows_node: list[dict[str, str]],
        supplier_capacity_rows_node: list[dict[str, str]],
        supplier_risk_rows_node: list[dict[str, str]],
        dormant_reason: str | None,
    ) -> str:
        risk_rows: list[tuple[str, str, str, str]] = []

        def add(severity: str, topic: str, signal: str, interpretation: str) -> None:
            risk_rows.append((severity, topic, signal, interpretation))

        total_safety = int(to_float(safety_summary.get("total")) or 0)
        non_conform = int(to_float(safety_summary.get("non_conform")) or 0)
        no_orders = int(to_float(safety_summary.get("no_orders")) or 0)
        conform = int(to_float(safety_summary.get("conform")) or 0)
        if total_safety > 0:
            if non_conform > 0:
                add(
                    "RISQUE",
                    "Arrivees vs delai securite",
                    f"{non_conform}/{total_safety} non conformes",
                    "Des receptions planifiees arrivent trop tard par rapport au delai de securite.",
                )
            elif no_orders > 0:
                add(
                    "ATTENTION",
                    "Arrivees vs delai securite",
                    f"{no_orders}/{total_safety} sans ordre",
                    "Un besoin couvert par safety time n'a pas d'ordre MRP trace.",
                )
            else:
                add(
                    "OK",
                    "Arrivees vs delai securite",
                    f"{conform}/{total_safety} conformes",
                    "Les premieres receptions planifiees respectent le delai de securite.",
                )

        trace_by_item: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        trace_days_by_item: dict[str, set[int]] = defaultdict(set)
        for row in node_trace_rows:
            item_id = str(row.get("item_id") or "")
            if not item_id:
                continue
            day = int(to_float(row.get("day")) or 0)
            bn_qty = max(0.0, to_float(row.get("bn_qty")) or 0.0)
            safety_floor = max(0.0, to_float(row.get("safety_floor_qty")) or 0.0)
            target_stock = max(0.0, to_float(row.get("target_stock_qty")) or 0.0)
            inventory_position = max(0.0, to_float(row.get("inventory_position_qty")) or 0.0)
            trace_by_item[item_id]["max_bn_qty"] = max(trace_by_item[item_id]["max_bn_qty"], bn_qty)
            trace_by_item[item_id]["max_safety_floor_qty"] = max(
                trace_by_item[item_id]["max_safety_floor_qty"],
                safety_floor,
            )
            trace_by_item[item_id]["max_target_stock_qty"] = max(
                trace_by_item[item_id]["max_target_stock_qty"],
                target_stock,
            )
            trace_by_item[item_id]["worst_inventory_gap_qty"] = min(
                trace_by_item[item_id].get("worst_inventory_gap_qty", 0.0),
                inventory_position - target_stock,
            )
            if bn_qty > 1e-9:
                trace_days_by_item[item_id].add(day)

        bn_items = [
            (item_id, stats.get("max_bn_qty", 0.0), len(trace_days_by_item.get(item_id, set())))
            for item_id, stats in trace_by_item.items()
            if stats.get("max_bn_qty", 0.0) > 1e-9
        ]
        if bn_items:
            item_id, max_bn, bn_days = max(bn_items, key=lambda row: (row[1], row[2]))
            severity = "ATTENTION" if bn_days >= 30 else "INFO"
            add(
                severity,
                "Besoin net MRP",
                f"{item_labels.get(item_id, compact_item_label(item_id))}: max={fmt_qty(max_bn, 0)} ; jours={bn_days}",
                "La position inventaire passe sous la cible MRP; c'est un signal de commande, pas forcement une rupture.",
            )
        elif node_trace_rows:
            add("OK", "Besoin net MRP", "aucun besoin net positif", "La position inventaire couvre les cibles MRP tracees.")

        stock_min_by_item: dict[str, float] = {}
        for row in stock_rows:
            item_id = str(row.get("item_id") or "")
            if not item_id:
                continue
            value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
            stock_min_by_item[item_id] = min(stock_min_by_item.get(item_id, value), value)
        below_safety: list[tuple[float, str, float, float]] = []
        for item_id, min_stock in stock_min_by_item.items():
            safety_floor = trace_by_item.get(item_id, {}).get("max_safety_floor_qty", 0.0)
            if safety_floor <= 1e-9:
                continue
            ratio = min_stock / safety_floor
            if ratio < 1.0:
                below_safety.append((ratio, item_id, min_stock, safety_floor))
        if below_safety:
            ratio, item_id, min_stock, safety_floor = min(below_safety, key=lambda row: row[0])
            add(
                "RISQUE",
                "Stock physique vs securite",
                f"{item_labels.get(item_id, compact_item_label(item_id))}: min={fmt_qty(min_stock, 0)} / cible={fmt_qty(safety_floor, 0)} ({ratio:.2f}x)",
                "Le stock reel simule passe sous le stock equivalent au delai de securite.",
            )
        elif stock_min_by_item and any(stats.get("max_safety_floor_qty", 0.0) > 1e-9 for stats in trace_by_item.values()):
            add("OK", "Stock physique vs securite", "pas de passage sous plancher detecte", "Le stock reel reste au-dessus des planchers de securite traces.")

        non_received = [row for row in node_orders if str(row.get("order_status_end_of_run") or "") != "received"]
        if non_received:
            add(
                "ATTENTION",
                "Carnet fin d'horizon",
                f"{len(non_received)} ordre(s) non recus en fin de run",
                "Souvent normal pres de la fin d'horizon, mais a controler si cela concerne un item critique.",
            )
        elif node_orders:
            add("OK", "Carnet fin d'horizon", "tous les ordres traces sont recus", "Pas d'ordre ouvert restant sur le run courant.")

        if dormant_reason:
            add("INFO", "Diagnostic noeud", dormant_reason, "Point de modelisation a valider si le noeud devrait etre actif.")

        if not risk_rows:
            add("INFO", "Risque MRP", "aucun signal disponible", "Aucune trace MRP ou donnee stock/carnet exploitable pour ce noeud.")

        severity_rank = {"RISQUE": 0, "ATTENTION": 1, "INFO": 2, "OK": 3}
        risk_rows.sort(key=lambda row: (severity_rank.get(row[0], 9), row[1]))
        rows_html = []
        for severity, topic, signal, interpretation in risk_rows:
            rows_html.append(
                "<tr>"
                f"<td>{html.escape(severity)}</td>"
                f"<td>{html.escape(topic)}</td>"
                f"<td>{html.escape(signal)}</td>"
                f"<td>{html.escape(interpretation)}</td>"
                "</tr>"
            )
        return "".join(
            [
                "<div class=\"factoryHtmlPanelContent\">",
                f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - risques MRP explicites</div>",
                "<div class=\"orderLedgerStatus\">Un risque ici est un signal actionnable: non-respect safety time, stock sous plancher, besoin net durable, ordre ouvert ou fournisseur fragile. Une trace MRP normale n'est pas une exception.</div>",
                "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
                "<thead><tr><th>Niveau</th><th>Sujet</th><th>Signal</th><th>Lecture</th></tr></thead>",
                "<tbody>",
                "".join(rows_html),
                "</tbody></table></div>",
                "</div>",
            ]
        )

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

    edge_metrics = build_edge_metrics(raw, supplier_shipments_csv, horizon_days=horizon_days or None)
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
            metric_section("Vue metier"),
            metric_label_value("Principe", "Le simulateur cherche a maintenir les stocks autour d'une cible MRP, sans commander ce qui est deja couvert par le stock ou les receptions futures."),
            metric_label_value("Decision", "A chaque revue, il calcule l'ecart a couvrir. Si cet ecart est positif, il cree un besoin net ; sinon il ne commande rien."),
            metric_label_value("Execution", "Le besoin net devient un ordre lotifie ou normalise par flux d'approvisionnement, puis il arrive selon les delais et les stocks/capacites disponibles."),
            metric_label_value("Modele complet", "Le bouton Equations du modele complet detaille les indices, les variables d'etat et les equations dynamiques globales."),
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
                    metric_section("Application client - lecture metier"),
                    metric_label_value("1. Demande", "Le client porte une demande exogene lue dans le scenario, par jour et par produit."),
                    metric_label_value("2. Service", "Le stock aval disponible sert cette demande dans la limite des quantites disponibles."),
                    metric_label_value("3. Backlog", "La part non servie devient un retard client reporte au jour suivant."),
                    metric_label_value("4. Signal aval", "La demande et le backlog alimentent ensuite le besoin propage vers les DC, usines et composants."),
                    metric_section("Application client - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application client - regles locales"),
                    metric_label_value("Eq sim 1", "besoin brut client BB_pf(t): demande_jour + backlog_precedent"),
                    metric_label_value("Eq sim 2", "Servi_pf(t): quantite servie au client = min(stock_disponible_pf, besoin_brut_client)"),
                    metric_label_value("Eq sim 3", "Backlog_pf(t): retard client fin de journee = besoin_brut_client - Servi_pf(t)"),
                    metric_section("Application client - correspondance modele global"),
                    metric_label_value("D[c,i](t)", "Demande_pf(t): demande client exogene du jour."),
                    metric_label_value("Served[c,i](t)", "Servi_pf(t): quantite livree depuis le stock disponible."),
                    metric_label_value("B[c,i](t+1)", "Backlog_pf(t): besoin non servi reporte au jour suivant."),
                    metric_section("Lecture simulateur"),
                    metric_label_value("Demande", "D_pf(t) est une entree exogene du scenario."),
                    metric_label_value("Backlog", "Le backlog n'est pas une entree: il est recalcule chaque jour si le stock aval ne couvre pas le besoin client."),
                    metric_label_value("Signal aval", "La demande servie/non servie alimente ensuite la propagation de besoin vers les usines et composants."),
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
                    "T_dc(t): cible MRP du DC pour l'item suivi",
                    "Gap_dc(t): ecart a couvrir = T_dc(t) + Backlog_dc(t) - StockProj_dc(t) - RecvPrev_dc(t)",
                    "BN_dc(t): besoin net du DC = Gap_dc(t) si l'ecart est positif ; sinon 0",
                ]
            )
            assumption_lines.extend(
                [
                    "le DC est pilote par cible stock / couverture et non par plan de production",
                    "les safety times MRP des PF sont portes sur les etats de stock du DC",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Application DC - lecture metier"),
                    metric_label_value("1. Stock disponible", "Le DC observe son stock par item apres receptions et sorties aval."),
                    metric_label_value("2. Cible MRP", "La cible est calculee avec stock securite, delai securite, couverture appro ou cible active."),
                    metric_label_value("3. Receptions futures", "Les quantites deja en transit vers le DC sont deduites avant de commander."),
                    metric_label_value("4. Besoin net", "Si la cible reste non couverte, le DC cree un besoin net vers ses sources amont."),
                    metric_section("Application DC - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application DC - regles locales"),
                    metric_label_value("Eq sim 1", "StockProj_dc(t+1) = StockProj_dc(t) + Recv_dc(t) - Ship_dc(t) - Served_dc(t)"),
                    metric_label_value("Eq sim 2", "T_dc(t): cible DC = plus haute valeur entre stock_securite explicite, delai_securite * signal MRP, couverture * signal MRP et cible stock active si definie"),
                    metric_label_value("Eq sim 3", "Gap_dc(t) = T_dc(t) + Backlog_dc(t) - StockProj_dc(t) - RecvPrev_dc(t)"),
                    metric_label_value("Eq sim 4", "BN_dc(t) = Gap_dc(t) si Gap_dc(t) > 0 ; sinon 0"),
                    metric_section("Application DC - correspondance modele global"),
                    metric_label_value("S[n,i](t)", "StockProj_dc(t): stock disponible/projete au DC pour l'item."),
                    metric_label_value("T[n,i](t)", "T_dc(t): cible MRP du DC."),
                    metric_label_value("IP[n,i](t)", "StockProj_dc(t) + RecvPrev_dc(t): position inventaire du DC."),
                    metric_label_value("BN[n,i](t)", "BN_dc(t): besoin net commandable vers l'amont."),
                    metric_section("Lecture simulateur"),
                    metric_label_value("Stock projete", "StockProj_dc(t) est le stock DC simule apres receptions, expeditions et service aval."),
                    metric_label_value("Receptions prevues", "RecvPrev_dc(t) est porte par les quantites deja en transit vers le DC."),
                    metric_label_value("Besoin net", "On calcule d'abord l'ecart a couvrir. Si cet ecart est negatif, le stock et les receptions futures couvrent deja la cible: il n'y a donc pas de nouvelle commande."),
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
            nominal_lines = []
            seen_nominal_keys: set[tuple[str, str, str]] = set()
            for row in supplier_nominal_by_node.get(node_id, []):
                item_id = str(row.get("item_id") or "")
                dst_node_id = str(row.get("dst_node_id") or "")
                edge_id = str(row.get("edge_id") or "")
                key = (item_id, dst_node_id, edge_id)
                if key in seen_nominal_keys or is_simulation_hidden_item(item_id):
                    continue
                seen_nominal_keys.add(key)
                nominal_lines.append(
                    (
                        f"{item_labels.get(item_id, compact_item_label(item_id))}"
                        f" -> {dst_node_id or 'n/a'}: "
                        f"stock_ouv={fmt_qty(row.get('simulated_opening_stock_qty'), 0)}, "
                        f"cap={fmt_qty(row.get('effective_capacity_qty_per_day'), 0)}/j, "
                        f"delai={format_policy_value(row.get('planned_lead_time_days'), 1)}j, "
                        f"OTIF={fmt_pct((to_float(row.get('nominal_reliability_otif')) or 0.0) * 100.0)}, "
                        f"base={row.get('capacity_basis') or 'n/a'}"
                    )
                )
                if len(nominal_lines) >= 8:
                    break
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
            supplier_equation_mapping_lines = [
                "Stock_source(t) = S[src(f),i](t): stock disponible chez le fournisseur source.",
                "Stock_dest(t) = S[dst(f),i](t): stock disponible chez le noeud receveur.",
                "Req_dest(t) = Req[dst(f),i](t): signal MRP qui dimensionne la cible destination.",
                "T_dest(t) = T[dst(f),i](t): cible MRP destination.",
                "RecvPrev_dest(t) = RecvPrev[dst(f),i](t): receptions futures deja planifiees vers la destination.",
                "Gap_mp(t) = Gap[dst(f),i](t): ecart a couvrir chez la destination.",
                "BN_mp(t) = BN[dst(f),i](t): besoin net commandable si l'ecart est positif.",
                "OA_mp(t) = Q[f,i](t): quantite commandee sur le flux apres regles de lot/sourcing.",
                "Ship_mp(t) = Ship[f,i](t): quantite sortie du stock source et expediee vers la destination.",
                "RecvPrev_mp(t) = reception planifiee issue de Ship_mp(t) a t + lead_time.",
            ]
            state_var_lines.extend(
                [
                    "Stock_source(t): stock source expediable",
                    "Req_dest(t): signal MRP journalier de la destination pour cette matiere",
                    "T_dest(t): cible MRP de la destination pour cette matiere",
                    "Stock_dest(t): stock matiere projete chez la destination, donc chez l'usine ou le DC receveur",
                    "RecvPrev_dest(t): receptions futures deja planifiees vers cette destination",
                "Gap_mp(t): ecart matiere a couvrir = T_dest(t) + Backlog_dest(t) - Stock_dest(t) - RecvPrev_dest(t)",
                    "BN_mp(t): besoin net matiere = Gap_mp(t) si l'ecart est positif ; sinon 0",
                    "OA_mp(t): quantite demandee a la source apres normalisation lot standard",
                    "Ship_mp(t): quantite sortie du stock source et expediee vers la destination",
                    "RecvPrev_mp(t): quantite planifiee en reception destination a t + lead_time",
                ]
            )
            assumption_lines.extend(
                [
                    "le fournisseur est simule comme source de stock + capacite ; pas comme atelier detaille",
                    "standard_order_qty agit comme multiple cible de commande sur le flux d'approvisionnement",
                    "la commande est simulee dans le sens du temps ; il n'y a pas encore de retroplanning explicite de la date d'ordre",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Application fournisseur - lecture metier"),
                    metric_label_value("1. Besoin destination", "Le noeud receveur du flux, par exemple une usine ou un DC, calcule son besoin MRP pour l'item."),
                    metric_label_value("2. Stock deja couvert", "Son stock disponible et ses receptions futures deja planifiees sont deduits avant toute nouvelle commande."),
                    metric_label_value("3. Ecart a couvrir", "Si la cible MRP reste superieure a la position inventaire, l'ecart devient un besoin net commandable."),
                    metric_label_value("4. Ordre fournisseur", "Le besoin net est affecte au flux source -> destination puis normalise par lot, quantite standard ou regle de sourcing."),
                    metric_label_value("5. Expedition source", "Le fournisseur source reduit son stock de la quantite expediee, sous reserve de stock et capacite."),
                    metric_label_value("6. Reception destination", "La quantite expediee devient une reception future, puis augmente le stock destination apres le delai simule."),
                    metric_section("Application fournisseur - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application fournisseur - regles locales"),
                    metric_label_value("Eq sim 1", "T_dest(t): plus haute valeur entre stock securite, delai securite * Req_dest(t), couverture appro * Req_dest(t) et cible stock active"),
                    metric_label_value("Eq sim 2", "Gap_mp(t) = T_dest(t) + Backlog_dest(t) - Stock_dest(t) - RecvPrev_dest(t)"),
                    metric_label_value("Eq sim 3", "BN_mp(t) = Gap_mp(t) si Gap_mp(t) > 0 ; sinon 0"),
                    metric_label_value("Eq sim 4", "OA_mp(t): ordre amont source = quantite commandee, normalisee par quantite standard si applicable"),
                    metric_label_value("Eq sim 5", "Ship_mp(t) = min(Stock_source(t), Capacite_source(t), OA_mp(t)): quantite vraiment expediee"),
                    metric_label_value("Eq sim 6", "RecvPrev_mp(t + lead_time) = Ship_mp(t): reception future creee par l'expedition"),
                    metric_section("Application fournisseur - correspondance modele global"),
                    metric_multiline_value(
                        "Mapping",
                        supplier_equation_mapping_lines,
                        limit=10,
                    ),
                    metric_section("Lecture metier fournisseur"),
                    metric_label_value("Besoin matiere", "On lit d'abord l'ecart a couvrir. Si l'ecart est negatif ou nul, BN_mp(t)=0 et aucun ordre supplementaire n'est cree."),
                    metric_label_value("Destination", "La destination est le noeud receveur du flux d'approvisionnement: son stock et ses receptions futures sont deduits avant de commander au fournisseur."),
                    metric_label_value("Ordre fournisseur", "OA_mp(t) est la quantite commandee apres normalisation par quantite standard, lot ou capacite source."),
                    metric_label_value("Expedition fournisseur", "Ship_mp(t) est une sortie du stock source envoyee vers la destination ; ce n'est pas une consommation BOM."),
                    metric_label_value("Reception", "La reception planifiee est datee a arrival_day source pour les ordres d'ouverture, sinon envoi + delai previsionnel source; le delai matiere previsionnel affiche reste la valeur source."),
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
                    metric_multiline_value("Parametres nominaux", nominal_lines, limit=8),
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
                    "007923: reference active retenue dans la simulation ; pas de flux FIA actif fourni dans les donnees source."
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
                        f"693055: PFI aval confirme, mais pas de production interne explicite observee ; flux amont simule non detaille={fmt_qty(external_procurement_qty_by_item.get('item:693055', 0.0))}."
                    )
            state_var_lines.extend(
                [
                    "besoin brut produit fini BB_pf(t): signal aval dynamique du produit fini",
                    "T_pf(t): cible stock produit fini/intermediaire active dans la boucle",
                    "SP_pf(t): stock PF courant observe dans la boucle",
                    "Gap_pf(t): ecart stock cible = T_pf(t) - SP_pf(t)",
                    "besoin net produit fini BN_pf(t): commande dynamique avant regles de lot",
                    "LP_pf(t): plan lance apres lot fixe/min/max/multiple",
                    "Prod_pf(t): production reelle bornee par capacite et intrants",
                    "StockProj_site(t): stock site fin de journee",
                ]
            )
            assumption_lines.extend(
                [
                    "la production est pilotee chronologiquement jour par jour et non par retroplanification explicite",
                    "les campagnes et regles de lot industrialisent le besoin net produit fini avant execution",
                    "les causes de binding observees viennent des contraintes reelles du run",
                ]
            )
            outgoing_flow_label = "Sorties PFI" if is_upstream_internal_site(node_id) else "Sorties aval"
            summary_lines.extend(
                [
                    metric_section("Application usine - lecture metier"),
                    metric_label_value("1. Signal aval", "L'usine recoit un signal de besoin depuis la demande finale, les DC ou les process aval."),
                    metric_label_value("2. Cible sortie", "Elle compare son stock de produit fabrique a une cible de couverture ou cible metier."),
                    metric_label_value("3. Commande de production", "Le signal aval et l'ecart de stock produisent une commande de production simulee, lissee dans le temps."),
                    metric_label_value("4. Lotification", "La commande est transformee en campagne selon les lots fixes/min/max/multiples et le maximum de lots par semaine."),
                    metric_label_value("5. Execution", "La production reelle est bornee par la capacite et les intrants disponibles."),
                    metric_label_value("6. Propagation BOM", "Le plan lotifie cree un besoin MRP amont ; la production reelle consomme physiquement les intrants."),
                    metric_section("Application usine - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application usine - regles locales"),
                    metric_label_value("Eq sim 1", "besoin brut produit fini BB_pf(t): signal aval dynamique = max(demande propagee, besoin process aval)"),
                    metric_label_value("Eq sim 2", "T_pf(t): cible PF = plus haute valeur entre cible stock active et fg_target_days * signal aval"),
                    metric_label_value("Eq sim 3", "SP_pf(t): stock projete PF observe dans la boucle = stock PF courant"),
                    metric_label_value("Eq sim 4", "Gap_pf(t) = T_pf(t) - SP_pf(t)"),
                    metric_label_value("Eq sim 5", "BN_pf(t): commande dynamique = besoin_brut_produit_fini + gain * Gap_pf(t), bornee a 0 si le calcul devient negatif"),
                    metric_label_value("Eq sim 6", "LP_pf(t): plan lance = normalisation_lot(BN_pf(t)) avec lot fixe/min/max/multiple + max lots / semaine"),
                    metric_label_value("Eq sim 7", "Prod_pf(t): production reelle = min(capacite, limite_intrants, LP_pf(t))"),
                    metric_label_value("Eq sim 8", "StockProj_site(t+1) = StockProj_site(t) + Recv_site(t) + Prod_site(t) - Cons_site(t) - Ship_site(t)"),
                    metric_section("Application usine - correspondance modele global"),
                    metric_label_value("ReqProd[p,s](t)", "besoin brut produit fini BB_pf(t): signal aval retenu pour la production."),
                    metric_label_value("TProd[p,s](t)", "T_pf(t): cible du produit fabrique par l'usine."),
                    metric_label_value("MPS[p,s](t)", "BN_pf(t): commande de production simulee avant lotification."),
                    metric_label_value("PlanLot[p,s](t)", "LP_pf(t): plan lance apres regles de lot et campagne."),
                    metric_label_value("Prod[p,s](t)", "Prod_pf(t): production reelle executee."),
                    metric_label_value("Cons[s,i](t)", "Consommations BOM: intrants physiquement decrementes par la production reelle."),
                    metric_label_value("Recv[s,i](t)", "Arrivages intrants observes: quantites devenues disponibles sur le site."),
                    metric_label_value("Ship[s,i](t)", "Sorties aval: quantites expediees ou servies depuis le site."),
                    metric_section("Lecture simulateur"),
                    metric_label_value("Signal production", "Le besoin usine vient du signal aval: demande finale, consommation aval observee ou MPS lotifie propage."),
                    metric_label_value("Plan lotifie", "LP_pf(t) est le besoin usine transforme par les regles de lot: fixe, min/max, multiple et limite lots/semaine."),
                    metric_label_value("Execution", "Prod_pf(t) est le plan lotifie borne par la capacite modelisee et les intrants disponibles."),
                    metric_label_value("Req_BOM vs Cons", "Req_BOM sert a commander l'amont a partir du plan lotifie ; Cons decremente reellement les stocks intrants selon la production executee."),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Sorties process", ", ".join(sorted(set(output_labels))) or "n/a"),
                    metric_label_value(
                        outgoing_flow_label,
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
                f"signal brut={fmt_qty(latest_trace.get('bb_demand_signal_raw_qty'))} ; "
                f"signal MRP={fmt_qty(latest_trace.get('bb_demand_signal_qty'))} ; "
                f"base={latest_trace.get('gross_requirement_basis') or 'n/a'} ; "
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
            planned_arrival_day = fmt_order_day(planned_order_receipt_day(row))
            planned_lead = planned_procurement_lead_days(row)
            effective_lead = effective_procurement_lead_days(row)
            order_lines.append(
                f"{item_labels.get(str(row.get('item_id') or ''), compact_item_label(str(row.get('item_id') or '')))}: "
                f"{display_order_type(row.get('order_type'))} ; "
                f"release={row.get('release_day') or 'n/a'} ; "
                f"ordre_passe={fmt_order_day(row.get('order_date_imt'))} ; "
                f"arrival_previsionnelle={planned_arrival_day} ; "
                f"arrival_effective={fmt_order_day(row.get('actual_receipt_day'))} ; "
                f"delai_prev_matiere={fmt_days(planned_lead, 1)} ; "
                f"delai_effectif_matiere={fmt_days(effective_lead, 1)} ; "
                f"status={row.get('order_status_end_of_run') or 'n/a'}"
            )
            if len(order_lines) >= 8:
                break

        mrp_industrial_validation_lines: list[str] = []
        for item_id in sorted({str(row.get("item_id") or "") for row in node_orders if str(row.get("item_id") or "")}):
            item_rows = [row for row in node_orders if str(row.get("item_id") or "") == item_id]
            if not item_rows or is_simulation_hidden_item(item_id):
                continue
            release_by_order_day: dict[int, float] = defaultdict(float)
            total_qty = 0.0
            standard_qty = 0.0
            for row in item_rows:
                if str(row.get("order_type") or "") != "lane_release":
                    continue
                day = int(to_float(row.get("order_date_imt")) or 0)
                qty = max(0.0, to_float(row.get("release_qty")) or 0.0)
                release_by_order_day[day] += qty
                total_qty += qty
                standard_qty = max(standard_qty, max(0.0, to_float(row.get("standard_order_qty")) or 0.0))
            if not release_by_order_day:
                continue
            peak_day, peak_qty = max(release_by_order_day.items(), key=lambda it: it[1])
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
        node_risk_asset = None
        node_flow_asset = None
        node_order_asset = None
        node_ledger_asset = None
        node_nominal_asset = None
        node_supplier_stock_flow_asset = None
        node_supplier_order_send_asset = None
        node_supplier_risk_catalog_asset = None
        node_uncertainty_asset = None
        node_supplier_risk_prediction_asset = None
        node_capacity_nominal_asset = None
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
                        "Aucune expedition observee sur les flux source et aucun tirage simule."
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
            "Besoin propage brut": aggregate_trace_series(node_trace_rows, "bb_demand_signal_raw_qty"),
            "Besoin MRP lisse": aggregate_trace_series(node_trace_rows, "bb_demand_signal_qty"),
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
        node_stock_rows_for_risk = dc_stocks_by_node.get(node_id, []) if node_type == "distribution_center" else input_stocks_by_node.get(node_id, [])
        node_risk_asset = {
            "html": render_mrp_risk_summary_html(
                node_id,
                node_type,
                safety_summary=safety_summary,
                node_trace_rows=node_trace_rows,
                node_orders=node_orders,
                stock_rows=node_stock_rows_for_risk,
                supplier_stock_rows_node=supplier_stocks_by_node.get(node_id, []),
                supplier_capacity_rows_node=supplier_cap_by_node.get(node_id, []),
                supplier_risk_rows_node=supplier_risk_applied_by_node.get(node_id, []),
                dormant_reason=dormant_reason,
            )
        }
        if node_type == "supplier_dc":
            node_supplier_stock_flow_asset = {
                "html": render_supplier_stock_flows_html(
                    node_id,
                    supplier_stock_flows_by_node.get(node_id, []),
                    supplier_ship_by_node.get(node_id, []),
                    node_orders,
                    item_labels,
                )
            }
            node_nominal_asset = {
                "html": render_supplier_nominal_parameters_html(
                    node_id,
                    supplier_nominal_by_node.get(node_id, []),
                    item_labels,
                )
            }
            node_supplier_risk_catalog_asset = {
                "html": render_supplier_risk_catalog_html(
                    node_id,
                    applied_rows=supplier_risk_applied_by_node.get(node_id, []),
                    configured_events=supplier_risk_config_by_node.get(node_id, []),
                    economic_policy=(policy.get("economic_policy") or {}) if isinstance(policy, dict) else {},
                )
            }
            supplier_ship_rows_node = supplier_ship_by_node.get(node_id, [])
            supplier_source_orders = [
                row for row in node_orders
                if str(row.get("src_node_id") or "") == node_id
            ]
            node_uncertainty_asset = {
                "html": render_passive_uncertainty_html(
                    node_id,
                    scope_label="fournisseur",
                    order_rows=supplier_source_orders,
                    stock_rows=supplier_stocks_by_node.get(node_id, []),
                    capacity_rows=supplier_cap_by_node.get(node_id, []),
                    shipment_rows=supplier_ship_rows_node,
                    nominal_rows=supplier_nominal_by_node.get(node_id, []),
                    item_labels=item_labels,
                )
            }
            node_supplier_risk_prediction_asset = {
                "html": render_supplier_risk_prediction_html(
                    node_id,
                    order_rows=supplier_source_orders,
                    stock_rows=supplier_stocks_by_node.get(node_id, []),
                    capacity_rows=supplier_cap_by_node.get(node_id, []),
                    shipment_rows=supplier_ship_rows_node,
                    nominal_rows=supplier_nominal_by_node.get(node_id, []),
                    criticality_row=supplier_local_criticality_by_node.get(node_id),
                    economic_policy=(policy.get("economic_policy") or {}) if isinstance(policy, dict) else {},
                    item_labels=item_labels,
                )
            }
            supplier_order_received_series = aggregate_order_series(
                supplier_source_orders,
                "release_qty",
                day_field="order_date_imt",
                bucket_days=7,
            )
            supplier_order_send_plan_series = aggregate_order_series(
                supplier_source_orders,
                "release_qty",
                day_field="release_day",
                bucket_days=7,
            )
            supplier_planned_receipt_series = aggregate_order_series(
                supplier_source_orders,
                "planned_receipt_qty",
                day_field="planned_arrival_day",
                bucket_days=7,
            )
            supplier_actual_send_series = aggregate_daily_series(
                supplier_ship_rows_node,
                value_field="shipped_qty",
                day_field="day",
                node_field="src_node_id",
                node_id=node_id,
            )

            supplier_order_send_top = build_line_chart_figure(
                {
                    "Commandes recues fournisseur": supplier_order_received_series,
                    "Envois planifies MRP": supplier_order_send_plan_series,
                },
                title=f"{node_id} - commandes recues et envois planifies",
                y_label="Quantite / semaine",
                event_like=True,
                note=(
                    "Commande recue = ordre MRP date a order_date_imt. "
                    "Envoi planifie = release_day, donc date a laquelle le fournisseur doit expedier."
                ),
                series_styles={
                    "Commandes recues fournisseur": {"color": "#0f766e", "width": 2.2},
                    "Envois planifies MRP": {"color": "#2563eb", "width": 2.2, "dash": "dash"},
                },
            )
            supplier_order_send_bottom = build_line_chart_figure(
                {
                    "Envois physiques simules": bucket_series_points(supplier_actual_send_series, 7),
                    "Receptions aval previsionnelles": supplier_planned_receipt_series,
                },
                title=f"{node_id} - envois physiques et receptions previsionnelles aval",
                y_label="Quantite / semaine",
                event_like=True,
                note=(
                    "Envois physiques = production_supplier_shipments_daily.day. "
                    "Receptions aval previsionnelles = carnet MRP date a ordre_passe + delai previsionnel source; pas arrival_day simule."
                ),
                series_styles={
                    "Envois physiques simules": {"color": "#dc2626", "width": 2.2},
                    "Receptions aval previsionnelles": {"color": "#7c3aed", "width": 2.2, "dash": "dot"},
                },
            )
            if supplier_order_send_top is not None or supplier_order_send_bottom is not None:
                node_supplier_order_send_asset = {
                    "figure": {
                        "kind": "dual_panel_multi",
                        "title": f"{node_id} - commandes, envois et receptions",
                        "top": supplier_order_send_top,
                        "bottom": supplier_order_send_bottom,
                    }
                }
        if node_type in {"factory", "supplier_dc"} and factory_nominal_capacity_by_node.get(node_id):
            node_capacity_nominal_asset = {
                "html": render_factory_nominal_capacities_html(
                    node_id,
                    factory_nominal_capacity_by_node.get(node_id, []),
                    item_labels,
                )
            }
        actual_input_arrival_series = aggregate_daily_series(
            input_arrivals_by_node.get(node_id, []),
            value_field="arrived_qty",
            node_field="node_id",
            node_id=node_id,
        )
        if node_type == "factory":
            supplier_order_rows = [
                row
                for row in node_orders
                if str(row.get("dst_node_id") or "") == node_id
                and str(row.get("src_node_id") or "") in supplier_ids
            ]
            if not supplier_order_rows:
                supplier_order_rows = [
                    row
                    for row in node_orders
                    if str(row.get("dst_node_id") or "") == node_id
                    and str(row.get("src_node_id") or "")
                    and str(row.get("src_node_id") or "") != node_id
                ]
            flow_series = {
                "Ordres passes fournisseurs": aggregate_order_series(
                    supplier_order_rows,
                    "release_qty",
                    day_field="order_date_imt",
                    bucket_days=7,
                ),
                "Receptions entree usine": bucket_series_points(actual_input_arrival_series, 7),
            }
            flow_title = f"{node_id} - ordres fournisseurs et receptions entree usine"
            flow_note = (
                "Ordres passes fournisseurs = date order_date_imt du carnet MRP vers les fournisseurs. "
                "Receptions entree usine = arrivees physiques dans production_input_replenishment_arrivals_daily."
            )
            flow_styles = {
                "Ordres passes fournisseurs": {"color": "#0f766e", "width": 2.3},
                "Receptions entree usine": {"color": "#2563eb", "width": 2.3, "dash": "dash"},
            }
        else:
            order_release_series = aggregate_order_series(
                node_orders,
                "release_qty",
                day_field="order_date_imt",
                bucket_days=7,
            )
            order_receipt_series = aggregate_order_series(
                node_orders,
                "planned_receipt_qty",
                day_field="planned_arrival_day",
                bucket_days=7,
            )
            flow_series = {
                "Ordres MRP hebdo": order_release_series,
                "Receptions previsionnelles hebdo": order_receipt_series,
            }
            if actual_input_arrival_series:
                flow_series["Arrivages reels intrants"] = actual_input_arrival_series
            flow_title = f"{node_id} - flux MRP intrants"
            flow_note = (
                "Flux entrants comparables: ordres MRP, receptions previsionnelles et arrivages reels. "
                "Le besoin net MRP n'est pas affiche ici car c'est un ecart de stock a cible, pas un flux journalier. "
                "Les ordres sont affiches a leur date d'ordre calculee pour eviter de faire apparaitre le carnet initial comme un ordre massif au 1er janvier."
            )
            flow_styles = {
                "Ordres MRP hebdo": {"color": "#0f766e", "width": 2.2},
                "Receptions previsionnelles": {"color": "#2563eb", "width": 2.2},
                "Arrivages reels intrants": {"color": "#0891b2", "width": 2.0, "dash": "dot"},
            }
        flow_top_figure = build_line_chart_figure(
            flow_series,
            title=flow_title,
            y_label="Quantite / semaine" if node_type == "factory" else "Quantite / jour",
            event_like=True,
            note=flow_note,
            series_styles=flow_styles,
        )
        actual_input_stock_series = aggregate_daily_series(
            input_stocks_by_node.get(node_id, []),
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        stock_target_series = {
            "Stock reel simule": actual_input_stock_series,
            "Stock projete MRP": aggregate_trace_series(node_trace_rows, "stock_proj_qty"),
            "Position inventaire MRP": aggregate_trace_series(node_trace_rows, "inventory_position_qty"),
            "Besoin net MRP": aggregate_trace_series(node_trace_rows, "bn_qty"),
            "Stock equiv. delai securite": aggregate_trace_series(node_trace_rows, "safety_floor_qty"),
            "Cible securite souple": aggregate_trace_series(node_trace_rows, "soft_safety_target_qty"),
            "Cible MRP totale": aggregate_trace_series(node_trace_rows, "target_stock_qty"),
        }
        flow_bottom_figure = build_line_chart_figure(
            stock_target_series,
            title=f"{node_id} - stock reel / position MRP vs cibles",
            y_label="Stock / cible",
            note=(
                "Niveaux comparables: stock reel simule, stock projete MRP, position inventaire MRP et cibles exprimees en quantite de stock. "
                "Position inventaire MRP = stock projete + receptions futures deja prevues; le besoin net MRP vient de l'ecart entre cette position et la cible totale."
            ),
            series_styles={
                "Stock reel simule": {"color": "#0f172a", "width": 2.4},
                "Stock projete MRP": {"color": "#2563eb", "width": 2.0, "dash": "dot"},
                "Position inventaire MRP": {"color": "#0f766e", "width": 2.1},
                "Besoin net MRP": {"color": "#dc2626", "width": 1.8, "dash": "dash"},
                "Stock equiv. delai securite": {"color": "#7c3aed", "width": 1.8, "dash": "dot"},
                "Cible securite souple": {"color": "#f59e0b", "width": 1.9, "dash": "dash"},
                "Cible MRP totale": {"color": "#64748b", "width": 1.4, "dash": "longdash"},
            },
        )
        if flow_top_figure is not None or flow_bottom_figure is not None:
            node_flow_asset = {
                "figure": {
                    "kind": "dual_panel_multi",
                    "title": f"{node_id} - pilotage MRP intrants",
                    "top": flow_top_figure,
                    "bottom": flow_bottom_figure,
                }
            }
        node_order_series: dict[str, list[tuple[int, float]]] = {}
        node_order_styles: dict[str, dict[str, Any]] = {}
        node_order_labels_by_item: dict[str, list[str]] = defaultdict(list)
        node_order_peak_by_item: dict[str, float] = defaultdict(float)
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
            release_label = f"{item_label} - ordre hebdo"
            receipt_label = f"{item_label} - reception prev. hebdo"
            release_series = aggregate_order_series(
                item_rows,
                "release_qty",
                day_field="order_date_imt",
                bucket_days=7,
            )
            receipt_series = aggregate_order_series(
                item_rows,
                "planned_receipt_qty",
                day_field="planned_arrival_day",
                bucket_days=7,
            )
            if release_series:
                node_order_series[release_label] = release_series
                node_order_styles[release_label] = {"color": color, "width": 2.0}
                node_order_labels_by_item[item_id].append(release_label)
                node_order_peak_by_item[item_id] = max(node_order_peak_by_item[item_id], max(v for _d, v in release_series))
            if receipt_series:
                node_order_series[receipt_label] = receipt_series
                node_order_styles[receipt_label] = {"color": color, "width": 2.0, "dash": "dash"}
                node_order_labels_by_item[item_id].append(receipt_label)
                node_order_peak_by_item[item_id] = max(node_order_peak_by_item[item_id], max(v for _d, v in receipt_series))
        dominant_order_labels: set[str] = set()
        if node_order_peak_by_item:
            global_peak = max(node_order_peak_by_item.values())
            if global_peak > 0:
                dominant_item_ids = {
                    item_id
                    for item_id, peak in node_order_peak_by_item.items()
                    if peak >= global_peak * 0.20
                }
                if 0 < len(dominant_item_ids) < len(node_order_peak_by_item):
                    for item_id in dominant_item_ids:
                        dominant_order_labels.update(node_order_labels_by_item.get(item_id, []))
        if dominant_order_labels:
            dominant_order_series = {
                label: pts for label, pts in node_order_series.items() if label in dominant_order_labels
            }
            other_order_series = {
                label: pts for label, pts in node_order_series.items() if label not in dominant_order_labels
            }
            dominant_order_figure = build_line_chart_figure(
                dominant_order_series,
                title=f"{node_id} - reappro amont volumes dominants",
                y_label="Quantite",
                event_like=True,
                note="Commandes MRP consolidees par semaine/flux/item pour eviter de lire les lignes MRP comme des PO unitaires.",
                series_styles={label: node_order_styles.get(label, {}) for label in dominant_order_series},
            )
            other_order_figure = build_line_chart_figure(
                other_order_series,
                title=f"{node_id} - reappro amont autres items",
                y_label="Quantite",
                event_like=True,
                note="Agregation hebdo. Meme couleur par item. Trait plein = ordre MRP ; pointille = reception previsionnelle.",
                series_styles={label: node_order_styles.get(label, {}) for label in other_order_series},
            )
            node_orders_figure = {
                "kind": "dual_panel_multi",
                "title": f"{node_id} - reappro amont par item",
                "top": dominant_order_figure,
                "bottom": other_order_figure,
            }
        else:
            node_orders_figure = build_line_chart_figure(
                node_order_series,
                title=f"{node_id} - reappro amont par item",
                y_label="Quantite",
                event_like=True,
                note="Commandes MRP consolidees par semaine/flux/item. Trait plein = ordre MRP ; pointille = reception previsionnelle.",
                series_styles=node_order_styles,
            )
        if node_orders_figure is not None:
            node_order_asset = {"figure": node_orders_figure}
        node_ledger_asset = {"html": render_order_ledger_html(node_id, node_orders, item_labels, dormant_reason)}

        summary_lines.extend(
            [
                metric_section("Limites du modele"),
                metric_label_value("Optimisation", "Ce n'est pas un solveur APS global: les decisions sont calculees par regles MRP et simulation chronologique jour apres jour."),
                metric_label_value("Calendrier industriel", "Les campagnes et lots sont modelises, mais pas encore un calendrier atelier complet avec equipes, changements de format et disponibilites machines fines."),
                metric_label_value("Fournisseurs", "Les fournisseurs sont modelises comme stocks/capacites/delais; les contrats, MOQ reels, allocations et arbitrages fournisseurs restent a valider."),
                metric_label_value("Couts", "Les achats viennent des prix matieres; la production est un proxy de cout de conversion pharma; transport, stockage et urgence restent parametrables tant que les couts industriels reels ne sont pas fournis."),
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
                metric_section("Sources locales"),
                metric_multiline_value(
                    "Sources structure / MRP du noeud",
                    unique_preserve(source_refs) or ["source structure locale non renseignee dans le JSON enrichi"],
                    limit=10,
                ),
            ]
        )
        nodes_payload[node_id] = {
            "title": "Modele du noeud",
            "summary_lines": summary_lines,
            "incoming": node_trace_asset,
            "risk": node_risk_asset,
            "outgoing": node_flow_asset,
            "third": node_ledger_asset,
            "fourth": node_order_asset,
            "stock_flow": node_supplier_stock_flow_asset,
            "supplier_order_send": node_supplier_order_send_asset,
            "nominal": node_nominal_asset,
            "supplier_risk_catalog": node_supplier_risk_catalog_asset,
            "uncertainty": node_uncertainty_asset,
            "risk_prediction": node_supplier_risk_prediction_asset,
            "capacity_nominal": node_capacity_nominal_asset,
        }

    def node_role_label(node_id: str) -> str:
        node = node_by_id.get(node_id) or {}
        node_type = str(node_types.get(node_id) or node.get("type") or "n/a")
        role_raw = str(node.get("role_raw") or (node.get("attrs") or {}).get("description") or "")
        type_label = {
            "supplier_dc": "fournisseur",
            "factory": "producteur/usine",
            "distribution_center": "centre de distribution",
            "customer": "client",
        }.get(node_type, node_type or "n/a")
        return f"{type_label}" + (f" - {role_raw}" if role_raw else "")

    def stock_rows_for_source(node_id: str, item_id: str) -> tuple[str, list[dict[str, str]]]:
        node_type = str(node_types.get(node_id) or "")
        if node_type == "supplier_dc":
            return "stock fournisseur", supplier_stock_rows_by_pair.get((node_id, item_id), [])
        if node_type == "distribution_center":
            return "stock DC source", dc_stock_rows_by_pair.get((node_id, item_id), [])
        rows = output_rows_by_pair.get((node_id, item_id), [])
        if rows:
            return "stock produit source", rows
        return "stock source", input_rows_by_pair.get((node_id, item_id), [])

    def stock_rows_for_destination(node_id: str, item_id: str) -> tuple[str, list[dict[str, str]]]:
        node_type = str(node_types.get(node_id) or "")
        if node_type == "distribution_center":
            rows = dc_stock_rows_by_pair.get((node_id, item_id), [])
            if rows:
                return "stock DC destination", rows
        rows = input_rows_by_pair.get((node_id, item_id), [])
        if rows:
            return "stock matiere destination", rows
        rows = output_rows_by_pair.get((node_id, item_id), [])
        if rows:
            return "stock produit destination", rows
        return "stock destination", []

    def stock_stats(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
        if not rows:
            return {"latest": None, "min": None, "max": None, "zero_days": 0}
        sorted_rows = sorted(rows, key=lambda r: int(to_float(r.get("day")) or 0))
        values = [max(0.0, to_float(row.get("stock_end_of_day")) or 0.0) for row in sorted_rows]
        return {
            "latest": values[-1],
            "min": min(values),
            "max": max(values),
            "zero_days": sum(1 for value in values if value <= 1e-9),
        }

    def capacity_stats(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
        if not rows:
            return {"max_util": None, "avg_active_util": None, "active_days": 0, "max_capacity": None}
        utilizations = [max(0.0, to_float(row.get("utilization")) or 0.0) for row in rows]
        active_utils = [value for value in utilizations if value > 1e-9]
        capacities = [max(0.0, to_float(row.get("capacity_qty_per_day")) or 0.0) for row in rows]
        return {
            "max_util": max(utilizations) if utilizations else None,
            "avg_active_util": statistics.mean(active_utils) if active_utils else 0.0,
            "active_days": len(active_utils),
            "max_capacity": max(capacities) if capacities else None,
        }

    def fmt_optional_qty_value(value: float | int | None, digits: int = 0) -> str:
        return "n/a" if value is None else fmt_qty(float(value), digits)

    def fmt_optional_pct_value(value: float | int | None) -> str:
        return "n/a" if value is None else fmt_pct(float(value) * 100.0)

    def render_edge_context_html(
        edge_id: str,
        src: str,
        dst: str,
        context_rows: list[dict[str, str]],
    ) -> str:
        table_rows: list[str] = []
        for row in context_rows:
            table_rows.append(
                "<tr>"
                f"<td>{html.escape(row.get('item') or '')}</td>"
                f"<td>{html.escape(row.get('source') or '')}</td>"
                f"<td>{html.escape(row.get('destination') or '')}</td>"
                f"<td>{html.escape(row.get('mrp') or '')}</td>"
                f"<td>{html.escape(row.get('flow') or '')}</td>"
                "</tr>"
            )
        if not table_rows:
            table_rows.append("<tr><td colspan=\"5\">Aucune donnee contexte exploitable pour ce flux.</td></tr>")
        return "".join(
            [
                "<div class=\"factoryHtmlPanelContent\">",
                f"<div class=\"orderLedgerTextHeader\">{html.escape(edge_id)} - contexte source / destination</div>",
                f"<div class=\"orderLedgerStatus\">Lecture du flux {html.escape(src)} -> {html.escape(dst)}: ce tableau relie ce que commande la destination a ce que peut expedier la source.</div>",
                "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
                "<thead><tr><th>Item</th><th>Source</th><th>Destination</th><th>MRP destination</th><th>Flux</th></tr></thead>",
                "<tbody>",
                "".join(table_rows),
                "</tbody></table></div>",
                "</div>",
            ]
        )

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
        edge_shipment_rows: list[dict[str, str]] = []
        state_var_lines = [
            "Req_dst(t): signal MRP journalier de la destination pour cet item",
            "T_dst(t): cible MRP de la destination pour l'item transporte",
            "Stock_dst(t): stock projete a destination",
            "RecvPrev_dst(t): receptions futures deja planifiees sur cette destination",
            "Gap_dst(t): ecart a couvrir a destination = T_dst(t) + Backlog_dst(t) - Stock_dst(t) - RecvPrev_dst(t)",
            "BN_dst(t): besoin net porte par la destination sur ce flux = Gap_dst(t) si l'ecart est positif ; sinon 0",
            "OA_src(t): quantite demandee a la source apres normalisation du flux",
            "Ship_src(t): quantite sortie du stock source et expediee sur le flux",
            "RecvPrev_dst(t): quantite qui arrivera a destination a t + lead_time",
            "Lead_ref: delai previsionnel MRP du flux",
            "LT_effectif: delai metier entre ordre passe fournisseur et reception effective",
            "Delai_retroplanning: delai total utilise pour positionner la date d'ordre previsionnelle",
        ]
        assumption_lines = [
            "le flux est simule chronologiquement au jour d'envoi ; la date d'ordre previsionnelle est un jalon calcule pour lire le carnet",
            "standard_order_qty joue comme multiple cible de commande quand disponible",
            "le delai previsionnel matiere vient des donnees source; le delai effectif metier est mesure entre ordre passe fournisseur et reception effective",
        ]
        for item_id in items:
            item_shipment_rows = supplier_ship_by_edge.get((src, dst, item_id), [])
            edge_shipment_rows.extend(item_shipment_rows)
            total_shipped += sum(max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in item_shipment_rows)
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
            planned_arrival_day = fmt_order_day(planned_order_receipt_day(row))
            planned_lead = planned_procurement_lead_days(row)
            effective_lead = effective_procurement_lead_days(row)
            edge_order_lines.append(
                f"{item_labels.get(str(row.get('item_id') or ''), compact_item_label(str(row.get('item_id') or '')))}: "
                f"{display_order_type(row.get('order_type'))} ; "
                f"release={row.get('release_day') or 'n/a'} ; "
                f"ordre_passe={fmt_order_day(row.get('order_date_imt'))} ; "
                f"arrival_previsionnelle={planned_arrival_day} ; "
                f"arrival_effective={fmt_order_day(row.get('actual_receipt_day'))} ; "
                f"delai_prev_matiere={fmt_days(planned_lead, 1)} ; "
                f"delai_effectif_matiere={fmt_days(effective_lead, 1)} ; "
                f"status={row.get('order_status_end_of_run') or 'n/a'}"
            )
        source_role = node_role_label(src)
        destination_role = node_role_label(dst)
        edge_context_rows: list[dict[str, str]] = []
        edge_context_summary_lines: list[str] = []
        for item_id in items:
            item_label = item_labels.get(item_id, compact_item_label(item_id))
            source_stock_label, source_stock_rows = stock_rows_for_source(src, item_id)
            destination_stock_label, destination_stock_rows = stock_rows_for_destination(dst, item_id)
            src_stock = stock_stats(source_stock_rows)
            dst_stock = stock_stats(destination_stock_rows)
            cap = capacity_stats(supplier_cap_by_pair.get((src, item_id), []))
            trace_latest = latest_mrp_trace_by_pair.get((dst, item_id), {})
            trace_rows = mrp_trace_rows_by_pair.get((dst, item_id), [])
            max_bn = max((max(0.0, to_float(row.get("bn_qty")) or 0.0) for row in trace_rows), default=0.0)
            bn_days = sum(1 for row in trace_rows if (to_float(row.get("bn_qty")) or 0.0) > 1e-9)
            shipped_rows = supplier_ship_by_edge.get((src, dst, item_id), [])
            shipped_qty = sum(max(0.0, to_float(row.get("shipped_qty")) or 0.0) for row in shipped_rows)
            arrival_qty = sum(
                max(0.0, to_float(row.get("arrived_qty")) or 0.0)
                for row in input_arrivals_by_pair.get((dst, item_id), [])
            )
            item_order_rows = [row for row in edge_order_rows if str(row.get("item_id") or "") == item_id]
            received_orders = sum(1 for row in item_order_rows if str(row.get("order_status_end_of_run") or "") == "received")
            open_orders = len(item_order_rows) - received_orders
            produced_source_qty = sum(
                max(0.0, to_float(row.get("produced_qty")) or 0.0)
                for row in output_rows_by_pair.get((src, item_id), [])
            )
            source_parts = [
                f"{source_stock_label}: fin={fmt_optional_qty_value(src_stock.get('latest'))}",
                f"min={fmt_optional_qty_value(src_stock.get('min'))}",
            ]
            if (src_stock.get("zero_days") or 0) > 0:
                source_parts.append(f"jours a zero={src_stock.get('zero_days')}")
            if cap.get("max_util") is not None:
                source_parts.append(
                    f"util max={fmt_optional_pct_value(cap.get('max_util'))}"
                )
                source_parts.append(f"jours actifs capacite={cap.get('active_days')}")
            if produced_source_qty > 1e-9:
                source_parts.append(f"produit source cumule={fmt_qty(produced_source_qty, 0)}")

            target_qty = to_float(trace_latest.get("target_stock_qty"))
            inventory_position_qty = to_float(trace_latest.get("inventory_position_qty"))
            safety_floor_qty = to_float(trace_latest.get("safety_floor_qty"))
            destination_parts = [
                f"{destination_stock_label}: fin={fmt_optional_qty_value(dst_stock.get('latest'))}",
                f"min={fmt_optional_qty_value(dst_stock.get('min'))}",
            ]
            if target_qty is not None and not math.isnan(target_qty):
                destination_parts.append(f"cible MRP fin={fmt_qty(target_qty, 0)}")
            if inventory_position_qty is not None and not math.isnan(inventory_position_qty):
                destination_parts.append(f"position inv fin={fmt_qty(inventory_position_qty, 0)}")
            if safety_floor_qty is not None and not math.isnan(safety_floor_qty):
                destination_parts.append(f"plancher secu={fmt_qty(safety_floor_qty, 0)}")

            mrp_parts = [
                f"BN max={fmt_qty(max_bn, 0)}",
                f"jours BN>0={bn_days}",
            ]
            flow_parts = [
                f"expedie={fmt_qty(shipped_qty, 0)}",
                f"arrive destination={fmt_qty(arrival_qty, 0)}",
                f"ordres={len(item_order_rows)}",
                f"recus={received_orders}",
                f"ouverts={open_orders}",
            ]
            edge_context_rows.append(
                {
                    "item": item_label,
                    "source": " ; ".join(source_parts),
                    "destination": " ; ".join(destination_parts),
                    "mrp": " ; ".join(mrp_parts),
                    "flow": " ; ".join(flow_parts),
                }
            )
            edge_context_summary_lines.append(
                f"{item_label}: src fin={fmt_optional_qty_value(src_stock.get('latest'))} ; "
                f"dst fin={fmt_optional_qty_value(dst_stock.get('latest'))} ; "
                f"cible={fmt_qty(target_qty, 0) if target_qty is not None and not math.isnan(target_qty) else 'n/a'} ; "
                f"BN max={fmt_qty(max_bn, 0)} ; ordres={len(item_order_rows)}"
            )
        edge_assumption_lines = []
        for row in assumptions_by_edge.get(edge_id, [])[:6]:
            edge_assumption_lines.append(
                f"{str(row.get('category') or 'n/a')} [{str(row.get('source') or 'n/a')}]"
            )
        edge_order_asset = None
        edge_lead_asset = None
        edge_status_asset = None
        edge_sent_series = aggregate_daily_series(
            edge_shipment_rows,
            value_field="shipped_qty",
            day_field="day",
        )
        edge_received_series = aggregate_daily_series(
            edge_shipment_rows,
            value_field="shipped_qty",
            day_field="arrival_day",
        )
        edge_flow_figure = build_line_chart_figure(
            {
                "Envois physiques": bucket_series_points(edge_sent_series, 7),
                "Receptions physiques": bucket_series_points(edge_received_series, 7),
            },
            title=f"{edge_id} - envois et receptions physiques",
            y_label="Quantite / semaine",
            event_like=True,
            note=(
                "Envoi = sortie de stock source datee par production_supplier_shipments_daily.day. "
                "Reception = meme quantite datee a arrival_day chez la destination."
            ),
            series_styles={
                "Envois physiques": {"color": "#dc2626", "width": 2.2},
                "Receptions physiques": {"color": "#2563eb", "width": 2.2, "dash": "dash"},
            },
        )
        if edge_flow_figure is not None:
            edge_order_asset = {"figure": edge_flow_figure}
        edge_lead_figure = build_line_chart_figure(
            {
                "Delai prev. source donnees": average_derived_order_series(edge_order_rows, planned_procurement_lead_days),
                "Delai effectif metier": average_derived_order_series(edge_order_rows, effective_procurement_lead_days),
            },
            title=f"{edge_id} - delais matiere du flux",
            y_label="Jours",
            note=(
                "Delai prev. = reference source donnees. "
                "Delai effectif = reception effective - ordre passe fournisseur."
            ),
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
        edge_lead_distribution_figure = lead_distribution_figure(
            edge_shipment_rows,
            title=f"{edge_id} - distribution des delais transport envoi-reception",
            planned_lead_days=planned_lead,
        )
        edge_capacity_rows = [
            row
            for item_id in items
            for row in supplier_cap_by_pair.get((src, item_id), [])
        ]
        edge_stock_rows = [
            row
            for item_id in items
            for row in supplier_stock_rows_by_pair.get((src, item_id), [])
        ]
        edge_nominal_rows = [
            row
            for row in supplier_nominal_by_node.get(src, [])
            if str(row.get("item_id") or "") in set(items)
            and (not str(row.get("dst_node_id") or "") or str(row.get("dst_node_id") or "") == dst)
        ]
        edge_context_html_asset = {
            "html": render_edge_context_html(edge_id, src, dst, edge_context_rows)
        }
        edge_uncertainty_html_asset = {
            "html": render_passive_uncertainty_html(
                edge_id,
                scope_label="flux",
                order_rows=edge_order_rows,
                stock_rows=edge_stock_rows,
                capacity_rows=edge_capacity_rows,
                shipment_rows=edge_shipment_rows,
                nominal_rows=edge_nominal_rows,
                item_labels=item_labels,
            )
        }
        edge_context_bundle = [
            {"label": "Source / destination", "asset": edge_context_html_asset},
            {"label": "Incertitude flux", "asset": edge_uncertainty_html_asset},
        ]
        if edge_lead_distribution_figure is not None:
            edge_context_bundle.append(
                {"label": "Distribution delais transport", "asset": {"figure": edge_lead_distribution_figure}}
            )
        edge_context_asset = {"bundle": edge_context_bundle}
        source_refs = [
            " / ".join(part for part in [str(attrs.get("source_workbook") or ""), str(attrs.get("source_sheet") or "")] if part)
        ]
        summary_lines = [
            metric_section("Element"),
            metric_label_value("Flux", f"{src} -> {dst}"),
            metric_label_value("Items", ", ".join(item_labels.get(i, compact_item_label(i)) for i in items) or "n/a"),
            metric_label_value("Id flux", edge_id),
            metric_section("Contexte source / destination"),
            metric_label_value("Source", f"{src} ({source_role})"),
            metric_label_value("Destination", f"{dst} ({destination_role})"),
            metric_label_value(
                "Topologie",
                f"source aval={len(outgoing_edges_by_node.get(src, []))} flux ; destination amont={len(incoming_edges_by_node.get(dst, []))} flux",
            ),
            metric_multiline_value("Synthese item", edge_context_summary_lines, limit=4),
            metric_section("Vue metier du flux"),
            metric_label_value("Role", "Ce flux transporte un besoin MRP depuis une source amont vers une destination aval."),
            metric_label_value("Decision", "La destination commande seulement l'ecart que son stock et ses receptions futures ne couvrent pas deja."),
            metric_label_value("Execution", "La source expedie selon son stock, sa capacite, la quantite standard du flux et le delai simule."),
            metric_section("Application flux - lecture metier"),
            metric_label_value("1. Destination", "Le noeud receveur calcule son besoin net pour l'item transporte."),
            metric_label_value("2. Affectation sourcing", "Le besoin net est affecte a ce flux selon sa part de sourcing MRP."),
            metric_label_value("3. Normalisation", "La quantite demandee est arrondie ou normalisee par quantite standard/lot si applicable."),
            metric_label_value("4. Expedition", "La source envoie la quantite possible selon son stock et sa capacite."),
            metric_label_value("5. Transit", "La quantite expediee reste en transit pendant le delai simule."),
            metric_label_value("6. Reception", "A l'arrivee, le stock destination augmente et le carnet ouvert diminue."),
            metric_section("Glossaire flux"),
            metric_label_value("T_dst(t)", "Cible MRP du noeud receveur pour l'item transporte."),
            metric_label_value("Stock_dst(t)", "Stock projete de l'item chez le receveur."),
            metric_label_value("RecvPrev_dst(t)", "Receptions futures deja planifiees vers le receveur."),
            metric_label_value("OA_src(t)", "Ordre amont demande a la source sur ce flux."),
            metric_label_value("LT prev. / LT effectif", "LT prev. est le delai previsionnel source; LT effectif est le delai metier entre ordre passe fournisseur et reception effective."),
            metric_section("Application flux - variables locales"),
            *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
            metric_section("Application flux - regles locales"),
            metric_label_value("Eq sim 1", "T_dst(t): plus haute valeur entre stock securite, delai securite * Req_dst(t), couverture appro * Req_dst(t) et cible stock active"),
            metric_label_value("Eq sim 2", "Gap_dst(t) = T_dst(t) + Backlog_dst(t) - Stock_dst(t) - RecvPrev_dst(t)"),
            metric_label_value("Eq sim 3", "BN_dst(t) = Gap_dst(t) si Gap_dst(t) > 0 ; sinon 0"),
            metric_label_value("Eq sim 4", "OA_src(t): ordre amont sur le flux = quantite demandee a la source, normalisee si quantite standard"),
            metric_label_value("Eq sim 5", "Reception_prevue = ordre_passe + LT_prev ; Delai_effectif = reception_effective - ordre_passe"),
            metric_label_value("Eq sim 6", "date_ordre_prevue = date_besoin - delai_securite - LT_ref"),
            metric_section("Application flux - correspondance modele global"),
            metric_label_value("Q[f,i](t)", "OA_src(t): quantite commandee sur ce flux apres sourcing et normalisation."),
            metric_label_value("Ship[f,i](t)", "release_day / expedition: quantite sortie de la source et mise en transit."),
            metric_label_value("Recv[f,i](t)", "arrivee_effective: quantite disponible chez la destination apres delai simule."),
            metric_label_value("IT[f,i](t)", "quantite en transit entre release_day et arrivee_effective."),
            metric_label_value("OO[f,i](t)", "carnet ouvert du flux jusqu'a reception."),
            metric_section("Lecture simulateur"),
            metric_label_value("Date d'ordre", "ordre_passe est une date calculee pour lire le carnet: besoin a couvrir - delai securite - delai d'appro."),
            metric_label_value("Date d'envoi", "release_day est le jour ou la quantite est envoyee sur le flux."),
            metric_label_value("Date reception", "arrivee_previsionnelle = ordre_passe + delai previsionnel source ; arrivee_effective = reception simulee ; delai matiere effectif = arrivee_effective - ordre_passe."),
            metric_section("Limites lecture flux"),
            metric_label_value("Granularite", "Les ordres sont consolides pour la lecture, mais la simulation reste journaliere et peut generer plusieurs evenements par item/flux."),
            metric_label_value("Capacite source", "Si la capacite fournisseur n'est pas connue, elle est une hypothese ou n'est pas limitante selon le parametrage du scenario."),
            metric_section("Donnees et interactions"),
            metric_label_value("Lead transport planifie", fmt_days(planned_lead, 1)),
            metric_label_value("Distance", f"{to_float(edge.get('distance_km')) or 0.0:.0f} km"),
            metric_label_value("Quantite standard", fmt_qty(standard_order_qty, 0) if standard_order_qty > 0 else "non renseignee"),
            metric_label_value("Correction quantite", str((standard_order_override or {}).get("note") or "aucune correction appliquee")),
            metric_label_value("Product code source", str(attrs.get("product_code") or "non renseigne")),
            metric_label_value("Compte fournisseur", str(attrs.get("supplier_account") or "non renseigne")),
            metric_multiline_value(
                "Donnees observees flux",
                lane_data_lines if lane_data_lines else ["aucune expedition observee sur ce flux"],
                limit=8,
            ),
            metric_section("Trace MRP explicite"),
            metric_multiline_value(
                "Carnet d'ordres flux",
                edge_order_lines if edge_order_lines else ["aucun ordre MRP direct sur ce flux ; flux probablement aval ou non pilote par appro"],
                limit=8,
            ),
            metric_section("Hypotheses"),
            *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
            metric_multiline_value(
                "Ledger hypotheses",
                edge_assumption_lines if edge_assumption_lines else ["aucune hypothese specifique au flux journalisee"],
                limit=6,
            ),
            metric_section("KPI run courant"),
            metric_label_value("Expedie cumule", fmt_qty(total_shipped)),
            metric_label_value("Lignes expedition", str(metric.get("shipment_rows", 0))),
            metric_label_value("Transit observe moyen", fmt_days(metric.get("avg_lead_days"), 1)),
            metric_label_value("Transit observe p50/p90", f"{metric.get('lead_p50_days', 'n/a')} / {metric.get('lead_p90_days', 'n/a')} j"),
            metric_label_value("Transit observe min-max", f"{metric.get('min_lead_days', 'n/a')} - {metric.get('max_lead_days', 'n/a')} j"),
            metric_label_value("Transits distincts observes", str(metric.get("distinct_lead_days", "n/a"))),
            metric_label_value("Quantites distinctes", str(metric.get("distinct_shipped_qty", 0))),
            metric_label_value("Utilisation source max", fmt_pct((avg_util or 0.0) * 100.0) if avg_util is not None else "non calculee"),
            metric_section("Sources et parametres"),
            metric_multiline_value(
                "Sources flux",
                unique_preserve(source_refs) or ["source flux non renseignee dans le JSON enrichi"],
                limit=4,
            ),
        ]
        edges_payload[edge_id] = {
            "title": "Modele du flux",
            "summary_lines": summary_lines,
            "incoming": edge_order_asset,
            "outgoing": edge_lead_asset,
            "third": edge_status_asset,
            "fourth": edge_context_asset,
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
        first_day = row["first_shipment_day"]
        last_day = row["last_shipment_day"]
        shipment_window = f"J{first_day} -> J{last_day}" if first_day != "" and last_day != "" else "aucun flux"
        summary_lines = [
            metric_label_value("Rang local", ""),
            metric_label_value("Statut flux", "actif" if total_shipped_qty > 1e-9 else "sans expedition simulee"),
            metric_label_value("Flux expedie total", f"{row['total_shipped_qty']:.2f}"),
            metric_label_value("Fenetre expeditions", shipment_window),
            metric_label_value("Jours avec expedition", str(row["active_days"])),
            metric_label_value("Items / destinations", f"{row['items_supplied_count']} / {row['dest_nodes_count']}"),
            metric_label_value("Items principaux", item_labels or "n/a"),
            metric_label_value("Lead prevu moyen", f"{row['avg_procurement_lead_days']:.1f} j"),
        ]
        if supplier_has_explicit_capacity.get(supplier_id, False):
            summary_lines.extend(
                [
                    metric_label_value("Capacite modelisee", "explicite"),
                    metric_label_value("Utilisation cap. moy.", f"{row['avg_capacity_utilization']:.2%}"),
                    metric_label_value("Utilisation cap. max", f"{row['max_capacity_utilization']:.2%}"),
                ]
            )
        else:
            summary_lines.append(metric_label_value("Capacite modelisee", "non explicite"))
        if observed_share_den > 1e-9:
            summary_lines.append(metric_label_value("Part du flux observee", f"{row['observed_sourcing_share']:.1%}"))
            if row["target_sourcing_share"] > 0.0:
                summary_lines.append(metric_label_value("Split MRP theorique", f"{row['target_sourcing_share']:.1%}"))
        else:
            summary_lines.append(metric_label_value("Part du flux observee", "n/a"))
        nominal_capacity = supplier_nominal_capacity_by_supplier.get(supplier_id, 0.0)
        if nominal_capacity > 0:
            summary_lines.append(metric_label_value("Capacite nominale", f"{nominal_capacity:,.2f}/j".replace(",", " ")))
        basis_label = supplier_capacity_basis_by_supplier.get(supplier_id, "")
        if basis_label:
            scale = supplier_capacity_scale_by_supplier.get(supplier_id, 0.0)
            suffix = f" x{scale:.0f}" if scale > 0 else ""
            summary_lines.append(metric_label_value("Base capacite", f"{basis_label}{suffix}"))
        summary_lines.append(metric_label_value("Paires mono-source", str(row["sole_source_pairs"])))
        if row["shortage_supported_qty"] > 0 or row["shortage_supported_events"] > 0:
            summary_lines.append(
                metric_label_value(
                    "Shortage soutenu",
                    f"{row['shortage_supported_qty']:.2f} sur {row['shortage_supported_events']} evenements",
                )
            )
        else:
            summary_lines.append(metric_label_value("Shortage soutenu", "aucun detecte"))
        summary_lines.append(metric_label_value("Indice local", f"{local_score:.3f}"))
        if std_label or struct_label or system_score > 1e-9:
            if std_label:
                summary_lines.append(metric_label_value("Driver sensibilite", std_label))
            if struct_label:
                summary_lines.append(metric_label_value("Driver structurel", struct_label))
            summary_lines.append(metric_label_value("Indice systeme", f"{system_score:.3f}"))
        metrics_by_supplier[supplier_id] = {
            "summary_lines": summary_lines,
            "items": supplied_items,
            "destinations": dest_nodes,
            "scores": {
                "local": round(local_score, 6),
                "system": round(system_score, 6),
                "overall": round(overall_score, 6),
            },
        }

    ranking_rows.sort(key=lambda row: (-float(row["overall_criticality_score"]), -float(row["total_shipped_qty"]), row["supplier_id"]))
    for rank, row in enumerate(ranking_rows, start=1):
        row["rank"] = rank
        supplier_metrics = metrics_by_supplier.get(str(row["supplier_id"]), {})
        if supplier_metrics:
            supplier_metrics["rank"] = rank
            for entry in supplier_metrics.get("summary_lines", []):
                if entry.get("label") == "Rang local":
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


def html_template(
    title: str,
    data_json: str,
    material_table_html: str,
    material_table_count: int,
    global_model_equations_html: str,
) -> str:
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
      width: min(900px, calc(100vw - 32px));
      max-height: calc(100vh - 110px);
      background: rgba(255,255,255,0.98);
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
      z-index: 20;
      box-sizing: border-box;
      overflow-x: hidden;
      overflow-y: auto;
      display: none;
      padding: 10px;
    }}
    #factoryHoverPanel.visible {{
      display: block;
    }}
    #factoryHoverPanel.hoverPreview {{
      pointer-events: auto;
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
      overflow-wrap: anywhere;
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
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
      min-width: 0;
      max-width: 100%;
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
      min-width: 0;
    }}
    .panelMetaRow {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      color: #334155;
      min-width: 0;
    }}
    .panelMetaLabel {{
      color: #64748b;
      min-width: 0;
    }}
    .panelMetaValue {{
      font-weight: 600;
      color: #0f172a;
      text-align: right;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      min-width: 0;
    }}
    .panelMetaRow.multiline {{
      grid-column: 1 / span 2;
      display: block;
      min-width: 0;
    }}
    .panelMetaRow.multiline .panelMetaLabel {{
      margin-bottom: 4px;
      color: #0f172a;
      font-weight: 700;
    }}
    .panelMetaRow.multiline .panelMetaValue {{
      display: block;
      max-width: 100%;
      overflow-x: scroll;
      overflow-y: hidden;
      padding-bottom: 4px;
      text-align: left;
      white-space: pre;
      overflow-wrap: normal;
      scrollbar-gutter: stable both-edges;
      font-family: Consolas, "Courier New", monospace;
      font-weight: 500;
    }}
    .factoryPlotBlock {{
      display: block;
      min-width: 0;
      max-width: 100%;
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
    .modelEquationPanel {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      background: #ffffff;
    }}
    .modelEquationIntro {{
      margin: 0;
      padding: 12px 14px;
      border: 1px solid #dbeafe;
      border-radius: 12px;
      background: #eff6ff;
      color: #1e3a8a;
      font-size: 13px;
      line-height: 1.45;
    }}
    .modelEquationSection {{
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      overflow: hidden;
      background: #ffffff;
    }}
    .modelEquationSection h3 {{
      margin: 0;
      padding: 10px 12px;
      background: #f8fafc;
      border-bottom: 1px solid #e2e8f0;
      color: #0f172a;
      font-size: 13px;
    }}
    .modelEquationTableWrap {{
      overflow-x: auto;
    }}
    .modelEquationTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    .modelEquationTable th,
    .modelEquationTable td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    .modelEquationTable th {{
      background: #f8fafc;
      color: #334155;
      font-weight: 800;
    }}
    .modelEquationTable td:first-child {{
      width: 160px;
      color: #0f172a;
      font-weight: 700;
    }}
    .modelEquationTable code {{
      color: #0f172a;
      font-family: Consolas, "Courier New", monospace;
      white-space: nowrap;
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
      height: 380px;
      object-fit: contain;
      object-position: center top;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
    }}
    .factoryPlotOutgoing {{
      height: 320px;
    }}
    .factoryPlotThird {{
      height: 320px;
    }}
    .factoryPlotFourth {{
      height: 320px;
    }}
    .factoryPlotFigure {{
      display: none;
      width: 100%;
      max-width: 100%;
      height: 380px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      box-sizing: border-box;
      min-width: 0;
    }}
    .factoryPlotFigure .plot-container,
    .factoryPlotFigure .svg-container {{
      width: 100% !important;
      max-width: 100% !important;
    }}
    .factoryPlotInner {{
      width: 100%;
      height: 100%;
    }}
    .factoryPlotFigure.factoryPlotOutgoing {{
      height: 320px;
    }}
    .factoryPlotFigure.factoryPlotThird {{
      height: 320px;
    }}
    .factoryPlotFigure.factoryPlotFourth {{
      height: 320px;
    }}
    .factoryPlotFigure.factoryHtmlPanel {{
      overflow: hidden;
    }}
    .factoryPlotFigure.factoryOrderLedgerPanel {{
      height: auto;
      min-height: 320px;
      overflow: hidden;
    }}
    .factoryPlotFigure.factoryOrderLedgerPanel .factoryHtmlPanelContent {{
      height: auto;
      min-height: 320px;
      max-width: 100%;
    }}
    .jsonPanelContent {{
      min-height: 100%;
    }}
    .jsonPanelPreWrap {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 0 12px 12px;
      scrollbar-gutter: stable both-edges;
    }}
    .jsonPanelPre {{
      margin: 0;
      padding: 10px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #f8fafc;
      color: #0f172a;
      font-family: Consolas, "Courier New", monospace;
      font-size: 11px;
      line-height: 1.45;
      white-space: pre;
    }}
    .dataSummaryPanelContent {{
      min-height: 100%;
      background: #ffffff;
    }}
    .dataSummaryScroll {{
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 0 12px 12px;
      scrollbar-gutter: stable both-edges;
    }}
    .dataSummarySection {{
      margin-bottom: 12px;
    }}
    .dataSummarySectionTitle {{
      font-size: 12px;
      font-weight: 800;
      color: #0f172a;
      margin: 4px 0 6px;
    }}
    .dataKvGrid {{
      display: grid;
      grid-template-columns: minmax(120px, 0.42fr) 1fr;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      overflow: hidden;
      background: #ffffff;
      font-size: 11px;
    }}
    .dataKvLabel,
    .dataKvValue {{
      padding: 7px 9px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .dataKvLabel {{
      background: #f8fafc;
      color: #475569;
      font-weight: 800;
    }}
    .dataKvValue {{
      color: #0f172a;
      overflow-wrap: anywhere;
    }}
    .dataKvLabel:nth-last-child(2),
    .dataKvValue:last-child {{
      border-bottom: 0;
    }}
    .dataSummaryTableWrap {{
      overflow: auto;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #ffffff;
    }}
    .dataSummaryTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
    }}
    .dataSummaryTable th,
    .dataSummaryTable td {{
      padding: 7px 8px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    .dataSummaryTable th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      color: #334155;
      font-weight: 800;
      z-index: 1;
    }}
    .dataSummaryTable tbody tr:last-child td {{
      border-bottom: 0;
    }}
    .dataEmptyState {{
      min-height: 80px;
      border: 1px dashed #cbd5e1;
      border-radius: 10px;
      background: #f8fafc;
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
    .kpiTreeViewTabs {{
      display: inline-flex;
      align-self: flex-start;
      gap: 6px;
      padding: 3px;
      border: 1px solid #dbe4ef;
      border-radius: 999px;
      background: #f8fafc;
    }}
    .kpiTreeViewBtn {{
      border: 0;
      border-radius: 999px;
      background: transparent;
      color: #334155;
      font-size: 11px;
      font-weight: 800;
      padding: 6px 12px;
      cursor: pointer;
    }}
    .kpiTreeViewBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    .kpiTreeView {{
      display: none;
    }}
    .kpiTreeView.active {{
      display: flex;
      flex-direction: column;
      gap: 10px;
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
    .kpiPhysicsGrid {{
      display: grid;
      grid-template-columns: 0.8fr 1.2fr;
      gap: 10px;
    }}
    .kpiPhysicsStack {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .kpiFormulaIntro {{
      color: #475569;
      font-size: 12px;
      line-height: 1.45;
      padding: 2px 4px;
    }}
    .kpiFormulaTableWrap {{
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      overflow: auto;
      background: #ffffff;
      max-height: 560px;
    }}
    .kpiFormulaTable {{
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
    }}
    .kpiFormulaTable th,
    .kpiFormulaTable td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
    }}
    .kpiFormulaTable thead th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #334155;
      font-weight: 800;
    }}
    .kpiFormulaTable td:nth-child(4) {{
      font-family: Consolas, "Courier New", monospace;
      color: #0f172a;
    }}
    .kpiFormulaTerms {{
      margin-top: 6px;
      padding-top: 6px;
      border-top: 1px dashed #cbd5e1;
      color: #475569;
      font-family: inherit;
      line-height: 1.35;
    }}
    .kpiFormulaTermsLabel {{
      color: #0f172a;
      font-weight: 800;
    }}
    .kpiFormulaFamily {{
      font-weight: 800;
      color: #0f172a;
      white-space: nowrap;
    }}
    .kpiFormulaLevel {{
      display: inline-flex;
      border-radius: 999px;
      padding: 3px 7px;
      background: #e2e8f0;
      color: #334155;
      font-weight: 800;
      white-space: nowrap;
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
      height: 360px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #ffffff;
      overflow: hidden;
    }}
    .factoryHtmlPanelContent {{
      display: flex;
      flex-direction: column;
      height: 100%;
      width: 100%;
      min-height: 0;
      min-width: 0;
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
    .orderLedgerFrame {{
      flex: 0 0 auto;
      min-width: 0;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      border-top: 1px solid #e2e8f0;
      background: #ffffff;
      overflow: hidden;
    }}
    .orderLedgerTableWrap {{
      min-height: 128px;
      max-height: 260px;
      min-width: 0;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      overflow-y: auto;
      overflow-x: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable both-edges;
    }}
    .orderLedgerTable {{
      width: 1805px;
      min-width: 1805px;
      border-collapse: collapse;
      font-size: 11px;
      table-layout: fixed;
    }}
    .orderLedgerWideTable {{
      min-width: 1805px;
      max-width: none;
    }}
    .orderLedgerTable th,
    .orderLedgerTable td {{
      padding: 7px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
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
    .orderLedgerSliceSeparator td {{
      background: #f1f5f9;
      color: #334155;
      font-weight: 800;
      text-align: center;
      white-space: normal;
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
      min-width: 0;
      max-width: 100%;
      box-sizing: border-box;
      overflow-wrap: anywhere;
      word-break: break-word;
      white-space: normal;
      line-height: 1.35;
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
      min-width: 0;
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      overflow-y: scroll;
      overflow-x: auto;
      padding: 0 16px 16px;
      scrollbar-gutter: stable both-edges;
    }}
    .orderLedgerLines {{
      margin: 0;
      display: block;
      width: max-content;
      min-width: 100%;
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
        <button id="modeData" class="modeBtn" type="button">Donnees</button>
        <button id="modeModel" class="modeBtn" type="button">Modele</button>
        <button id="modeJson" class="modeBtn" type="button"{'' if DEBUG_PANEL_ENABLED else ' style="display:none;"'}>DEBUG</button>
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
    <div class="box">
      <button id="modelEquationsBtn" class="tableBtn" type="button">Equations modele</button>
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

  <div id="modelEquationsModal" class="tableModal">
    <div class="tableModalCard">
      <div class="tableModalHeader">
        <div>
          <div class="tableModalTitle">Equations du modele complet</div>
          <div class="tableModalMeta">Vue globale: demande -> production -> BOM -> MRP -> fournisseur -> stock</div>
        </div>
        <button id="modelEquationsCloseBtn" class="tableBtn" type="button">Fermer</button>
      </div>
      <div class="tableModalBody">
        {global_model_equations_html}
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
        <div id="incomingTabs" class="panelSubTabs"></div>
        <img id="factoryIncomingImage" class="factoryPlot" alt="Node incoming chart"/>
        <div id="factoryIncomingFigure" class="factoryPlotFigure"></div>
      </div>
      <div id="outgoingBlock" class="factoryPlotBlock">
        <div id="outgoingLabel" class="factoryPlotLabel">Production produits finis (sortie)</div>
        <div id="outgoingTabs" class="panelSubTabs"></div>
        <img id="factoryOutgoingImage" class="factoryPlot factoryPlotOutgoing" alt="Node outgoing chart"/>
        <div id="factoryOutgoingFigure" class="factoryPlotFigure factoryPlotOutgoing"></div>
      </div>
      <div id="thirdBlock" class="factoryPlotBlock">
        <div id="thirdLabel" class="factoryPlotLabel">Analyse complementaire</div>
        <div id="thirdTabs" class="panelSubTabs"></div>
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
    const MATERIAL_BALANCE_ROWS = DATA.material_balance_rows || [];
    const MODEL_PANEL = DATA.model_panel || {{ nodes: {{}}, edges: {{}} }};
    const DATA_PANEL = DATA.data_panel || {{ nodes: {{}}, edges: {{}} }};
    const JSON_PANEL = DATA.json_panel || {{ nodes: {{}}, edges: {{}} }};
    const TIMELINE_HORIZON_DAYS = Number(DATA.timeline_horizon_days || 0);
    const EDGE_BY_ID = Object.fromEntries((DATA.edges || []).map(e => [e.id, e]));
    const FACTORY_LIKE_NODE_IDS = new Set(DATA.factory_like_node_ids || []);
    const REALISTIC_SENSITIVITY = DATA.realistic_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const THRESHOLD_SENSITIVITY = DATA.threshold_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const nodeById = Object.fromEntries((DATA.nodes || []).map(n => [n.id, n]));
    const defaultPalette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"];
    const STANDARD_PLOT_MARGIN = {{ l: 64, r: 24, t: 48, b: 92 }};
    const GANTT_PLOT_MARGIN = {{ l: 128, r: 24, t: 54, b: 92 }};
    const STANDARD_LEGEND = {{ orientation: "h", y: -0.34 }};
    const PLOTLY_PANEL_CONFIG = {{ displayModeBar: false, responsive: false, scrollZoom: true }};
    const PLOTLY_RESPONSIVE_CONFIG = {{ displayModeBar: false, responsive: true, scrollZoom: true }};
    const PLOTLY_MAP_CONFIG = {{ displayModeBar: true, responsive: true, scrollZoom: true }};
    let currentFactoryHoverId = null;
    let currentFactoryHoverType = null;
    let currentHoveredPanelId = null;
    let currentHoveredPanelType = null;
    let selectedPanelNodeId = null;
    let selectedPanelNodeType = null;
    let panelAnchorClientX = null;
    let panelAnchorClientY = null;
    let currentPanelMode = "ops";
    let pendingPanelPlotRenderToken = 0;
    let lastFactoryPanelRenderKey = "";
    let hoverHandlersBound = false;
    let panelPointerInside = false;
    let hoverClearTimeout = null;
    const panelBundleSelection = {{}};
    let selectedYearStart = 1;
    let selectedYearEnd = 1;
    let globalKpiTreeState = {{ selectedId: null, smoothingMode: "month", viewMode: "graphs" }};

    function installCtrlScrollZoomGate(plotNode) {{
      if (!plotNode || plotNode.__ctrlScrollZoomGateInstalled) return;
      plotNode.__ctrlScrollZoomGateInstalled = true;
      plotNode.addEventListener("wheel", (ev) => {{
        if (ev.ctrlKey) return;
        ev.stopImmediatePropagation();
      }}, true);
    }}

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
      }} else if (figure.kind === "gantt") {{
        (figure.rows || []).forEach((row) => {{
          const value = Number(row.end || row.start || 0);
          if (Number.isFinite(value)) maxDay = Math.max(maxDay, value);
        }});
      }}
      return maxDay;
    }}

    function extractFigureMinDay(figure) {{
      if (!figure || typeof figure !== "object") return 0;
      let minDay = 0;
      function inspectValue(rawValue) {{
        const value = Number(rawValue);
        if (Number.isFinite(value)) minDay = Math.min(minDay, value);
      }}
      if (figure.kind === "line_multi") {{
        (figure.series || []).forEach((series) => {{
          (series.days || []).forEach(inspectValue);
        }});
      }} else if (figure.kind === "dual_panel_multi") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel || panel.kind !== "line_multi") return;
          (panel.series || []).forEach((series) => {{
            (series.days || []).forEach(inspectValue);
          }});
        }});
      }} else if (figure.kind === "dual_panel") {{
        [figure.top, figure.bottom].forEach((panel) => {{
          if (!panel) return;
          (panel.x || []).forEach(inspectValue);
        }});
      }} else if (figure.kind === "gantt") {{
        (figure.rows || []).forEach((row) => {{
          inspectValue(row.start || 0);
        }});
      }}
      return minDay;
    }}

    function computeTimelineMaxYear() {{
      if (Number.isFinite(TIMELINE_HORIZON_DAYS) && TIMELINE_HORIZON_DAYS > 0) {{
        return Math.max(1, Math.ceil(TIMELINE_HORIZON_DAYS / 365));
      }}
      let maxDay = 0;
      [FACTORY_HOVER_IMAGES, SUPPLIER_HOVER_IMAGES, DC_HOVER_IMAGES, CUSTOMER_HOVER_IMAGES].forEach((payload) => {{
        visitTimelineFigures(payload, (figure) => {{
          maxDay = Math.max(maxDay, extractFigureMaxDay(figure));
        }});
      }});
      return Math.max(1, Math.ceil((maxDay + 1) / 365));
    }}

    function computeTimelineMinDay() {{
      let minDay = 0;
      [FACTORY_HOVER_IMAGES, SUPPLIER_HOVER_IMAGES, DC_HOVER_IMAGES, CUSTOMER_HOVER_IMAGES].forEach((payload) => {{
        visitTimelineFigures(payload, (figure) => {{
          minDay = Math.min(minDay, extractFigureMinDay(figure));
        }});
      }});
      return Math.min(0, minDay);
    }}

    const timelineMaxYear = computeTimelineMaxYear();
    const timelineMinDay = computeTimelineMinDay();
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
      valueEl.textContent = selectedTimelineWindowLabel();
    }}

    function selectedTimelineWindowLabel() {{
      return timelineMaxYear > 1
        ? `annee ${{selectedYearStart}} -> ${{selectedYearEnd}}`
        : "run complet";
    }}

    function applyTimelineWindowUi() {{
      const box = document.getElementById("timelineWindowBox");
      if (!box) return;
      const visible = currentPanelMode === "ops" && timelineMaxYear > 1;
      box.classList.toggle("visible", visible);
    }}

    function currentTimelineDayRange() {{
      const startDay = selectedYearStart <= 1
        ? Math.min(0, timelineMinDay)
        : (selectedYearStart - 1) * 365;
      let endDay = (selectedYearEnd * 365) - 1;
      if (Number.isFinite(TIMELINE_HORIZON_DAYS) && TIMELINE_HORIZON_DAYS > 0) {{
        endDay = Math.min(endDay, Math.max(0, TIMELINE_HORIZON_DAYS - 1));
      }}
      return {{
        startDay: Math.min(startDay, endDay),
        endDay,
      }};
    }}

    function dayAxisTickStep(spanDays) {{
      const span = Math.max(1, Number(spanDays) || 1);
      if (span <= 31) return 5;
      if (span <= 90) return 10;
      if (span <= 200) return 25;
      if (span <= 450) return 50;
      if (span <= 900) return 100;
      if (span <= 2200) return 200;
      return 500;
    }}

    function dayAxisLayout(title = "Jour", extra = {{}}) {{
      const range = currentTimelineDayRange();
      const startDay = Number(range.startDay) || 0;
      const endDay = Math.max(startDay, Number(range.endDay) || 0);
      const visualPaddingDays = Math.max(5, (endDay - startDay) * 0.02);
      const axisStart = startDay - visualPaddingDays;
      const axisEnd = endDay + visualPaddingDays;
      const step = dayAxisTickStep(endDay - startDay);
      const firstTick = Math.ceil(startDay / step) * step;
      const tickvals = [];
      const ticktext = [];
      for (let day = firstTick; day <= endDay; day += step) {{
        tickvals.push(day);
        ticktext.push(day < 0 ? `J${{day}}` : String(day));
      }}
      if (startDay < 0 && endDay >= 0 && !tickvals.includes(0)) {{
        tickvals.push(0);
        ticktext.push("0");
      }}
      if (!tickvals.length) {{
        tickvals.push(startDay);
        ticktext.push(String(startDay));
      }}
      return {{
        title,
        gridcolor: "#e2e8f0",
        range: [axisStart, axisEnd],
        tickmode: "array",
        tickvals,
        ticktext,
        ...extra,
      }};
    }}

    function filterSeriesByTimeline(days, values, forceWindow = false) {{
      if ((!forceWindow && currentPanelMode !== "ops") || timelineMaxYear <= 1) {{
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

    function escapeTableHtml(value) {{
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }}[ch]));
    }}

    function scopeBadgeClass(scope) {{
      if (scope === "pf") return "scopeBadge scopeFinal";
      if (scope === "pfi") return "scopeBadge scopeIntermediate";
      return "scopeBadge";
    }}

    function selectedMaterialYears() {{
      const start = Math.max(1, Math.min(selectedYearStart, selectedYearEnd));
      const end = Math.max(start, Math.max(selectedYearStart, selectedYearEnd));
      const years = [];
      for (let year = start; year <= end; year += 1) {{
        years.push(year);
      }}
      return years;
    }}

    function aggregateMaterialRow(row) {{
      const years = selectedMaterialYears();
      const yearly = row.yearly || {{}};
      let days = 0;
      let planned = 0;
      let delivered = 0;
      let consumed = 0;
      let initial = null;
      let finalStock = 0;
      let foundYear = false;
      years.forEach((year) => {{
        const bucket = yearly[String(year)];
        if (!bucket) return;
        foundYear = true;
        days += Number(bucket.days) || 0;
        planned += Number(bucket.planned_qty) || 0;
        delivered += Number(bucket.delivered_qty) || 0;
        consumed += Number(bucket.consumed_qty) || 0;
        const bucketInitial = Number(bucket.initial_qty);
        if (initial === null && Number.isFinite(bucketInitial)) {{
          initial = bucketInitial;
        }}
        const bucketFinal = Number(bucket.final_stock_qty);
        if (Number.isFinite(bucketFinal)) {{
          finalStock = bucketFinal;
        }}
      }});
      if (!foundYear) {{
        days = Math.max(1, Number(row.days) || 0);
        planned = Number(row.planned_qty) || 0;
        delivered = Number(row.delivered_qty) || 0;
        consumed = Number(row.consumed_qty) || 0;
        initial = Number(row.initial_qty) || 0;
        finalStock = Number(row.final_stock_qty) || 0;
      }}
      if (row.scope === "pfi") {{
        planned = Math.max(consumed, delivered);
      }}
      const safetyDays = Math.max(0, Number(row.safety_time_days) || 0);
      const avgDaily = days > 0 ? planned / days : Math.max(0, Number(row.avg_daily_need_qty) || 0);
      const stockEquivSafety = avgDaily * safetyDays;
      let gap = consumed - planned;
      if (row.scope === "pf") {{
        gap = delivered - planned;
      }} else if (row.scope === "pfi") {{
        gap = delivered - Math.max(consumed, delivered);
      }}
      let diagnostic = row.diagnostic || "";
      const tol = Math.max(1, Math.abs(planned) * 0.01);
      if (row.scope === "pf") {{
        diagnostic = Math.abs(gap) <= tol ? "demande servie sur la fenetre" : "ecart service sur la fenetre";
      }} else if (row.scope === "material") {{
        if (consumed <= 1e-9 && delivered <= 1e-9 && (initial || 0) > 0) {{
          diagnostic = "coherent dormant sur la fenetre";
        }} else if (delivered > 0 || consumed > 0) {{
          diagnostic = "actif sur la fenetre";
        }} else {{
          diagnostic = "inactif sur la fenetre";
        }}
      }} else if (row.scope === "pfi") {{
        diagnostic = (delivered > 0 || consumed > 0) ? "PFI actif sur la fenetre" : "PFI inactif sur la fenetre";
      }}
      return {{
        ...row,
        planned_qty: planned,
        avg_daily_need_qty: avgDaily,
        stock_equiv_safety_time_qty: stockEquivSafety,
        initial_qty: initial === null ? 0 : initial,
        delivered_qty: delivered,
        consumed_qty: consumed,
        final_stock_qty: finalStock,
        gap_vs_need_qty: gap,
        diagnostic,
        selected_days: days,
      }};
    }}

    function renderMaterialTable() {{
      const tbody = document.querySelector("#materialTableModal .materialTable tbody");
      const meta = document.getElementById("materialTableMeta");
      if (!tbody || !meta || !Array.isArray(MATERIAL_BALANCE_ROWS) || !MATERIAL_BALANCE_ROWS.length) return;
      const rows = MATERIAL_BALANCE_ROWS.map(aggregateMaterialRow);
      tbody.innerHTML = rows.map((row) => `
        <tr>
          <td><span class="${{scopeBadgeClass(row.scope)}}">${{escapeTableHtml(row.scope_label || "")}}</span></td>
          <td>${{escapeTableHtml(String(row.item_id || "").replace(/^item:/, ""))}}</td>
          <td>${{escapeTableHtml(row.node_label || "")}}</td>
          <td class="num">${{fmtPanelQty(row.planned_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.avg_daily_need_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.safety_time_days, 1)}}</td>
          <td class="num">${{fmtPanelQty(row.stock_equiv_safety_time_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.initial_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.delivered_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.consumed_qty, 3)}}</td>
          <td class="num">${{fmtPanelQty(row.gap_vs_need_qty, 3)}}</td>
          <td>${{escapeTableHtml(row.unit || "")}}</td>
          <td>${{escapeTableHtml(row.diagnostic || "")}}</td>
        </tr>
      `).join("");
      const years = selectedMaterialYears();
      const totalDays = rows.reduce((maxDays, row) => Math.max(maxDays, Number(row.selected_days) || 0), 0);
      meta.textContent = `${{rows.length}} lignes - annee ${{years[0]}} -> ${{years[years.length - 1]}} - ${{totalDays}} j`;
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
        `Transit planifie envoi-reception: ${{e.planned_lead_days ?? 'n/a'}} j`,
        `Transit observe moyen: ${{m.avg_lead_days}} j`,
        `Transit observe min-max: ${{m.min_lead_days}} - ${{m.max_lead_days}} j`,
        `Transit observe p50 / p90: ${{m.lead_p50_days}} / ${{m.lead_p90_days}} j`,
        `Variabilite transit (ecart-type): ${{m.lead_std_days}} j`,
        `Safety time destination: ${{m.safety_time_days}} j`,
        `Transit + safety moyen: ${{m.effective_lead_days}} j`,
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

    function edgeSelectionPoints(src, dst) {{
      const lonDelta = Math.abs(dst.lon - src.lon);
      const wrappedLonDelta = Math.min(lonDelta, 360 - lonDelta);
      const approxDeg = Math.hypot(dst.lat - src.lat, wrappedLonDelta);
      const steps = Math.max(96, Math.min(720, Math.ceil(approxDeg * 8)));
      const europeCountries = new Set([
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic", "Denmark",
        "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy",
        "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal",
        "Romania", "Slovakia", "Slovenia", "Spain", "Sweden", "Switzerland", "United Kingdom",
      ]);
      const srcCountry = String(src.country || "");
      const dstCountry = String(dst.country || "");
      const isUsToEurope = srcCountry === "United States" && europeCountries.has(dstCountry);
      const startFrac = isUsToEurope ? 0.02 : 0.08;
      const endFrac = isUsToEurope ? 0.98 : 0.92;
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
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          showlegend: false,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hoverinfo: "none",
          marker: {{
            size: 24,
            color: "#111827",
            opacity: 0.001,
            line: {{ width: 0 }}
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
          const selectionPts = edgeSelectionPoints(src, dst);
          traces.push({{
            type: "scattergeo",
            mode: "markers",
            showlegend: false,
            lon: selectionPts.map(p => p.lon),
            lat: selectionPts.map(p => p.lat),
            text: selectionPts.map(() => edgeText(e)),
            customdata: selectionPts.map(() => [e.id, "edge", `${{e.from}} -> ${{e.to}}`]),
            marker: {{
              size: 1,
              color: "#111827",
              opacity: 0.001,
              line: {{ width: 0 }},
            }},
            hovertemplate: "%{{text}}<extra></extra>",
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
      pendingPanelPlotRenderToken += 1;
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
      const incomingTabs = document.getElementById("incomingTabs");
      const outgoingTabs = document.getElementById("outgoingTabs");
      const thirdTabs = document.getElementById("thirdTabs");
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
      incomingTabs.innerHTML = "";
      incomingTabs.style.display = "none";
      outgoingTabs.innerHTML = "";
      outgoingTabs.style.display = "none";
      thirdTabs.innerHTML = "";
      thirdTabs.style.display = "none";
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
      panel.classList.remove("hoverPreview");
      panel.style.left = "";
      panel.style.right = "";
      panel.style.top = "";
      panel.style.maxHeight = "";
      currentFactoryHoverId = null;
      currentFactoryHoverType = null;
      lastFactoryPanelRenderKey = "";
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

    function updatePanelAnchorFromEvent(ev) {{
      const source = ev && ev.event ? ev.event : null;
      if (!source) return;
      const x = Number(source.clientX);
      const y = Number(source.clientY);
      if (Number.isFinite(x)) panelAnchorClientX = x;
      if (Number.isFinite(y)) panelAnchorClientY = y;
    }}

    function positionFactoryPanel() {{
      const panel = document.getElementById("factoryHoverPanel");
      if (!panel || !panel.classList.contains("visible")) return;
      const margin = 14;
      const gap = 18;
      const defaultTop = 88;
      const panelWidth = Math.min(panel.offsetWidth || 760, Math.max(320, window.innerWidth - margin * 2));
      const anchorX = Number.isFinite(panelAnchorClientX) ? panelAnchorClientX : null;
      let left = window.innerWidth - panelWidth - margin;
      if (anchorX !== null) {{
        const rightCandidate = anchorX + gap;
        const leftCandidate = anchorX - panelWidth - gap;
        const fitsRight = rightCandidate + panelWidth <= window.innerWidth - margin;
        const fitsLeft = leftCandidate >= margin;
        if (fitsRight && (!fitsLeft || anchorX < window.innerWidth / 2)) {{
          left = rightCandidate;
        }} else if (fitsLeft) {{
          left = leftCandidate;
        }} else if (anchorX > window.innerWidth / 2) {{
          left = margin;
        }}
      }}
      left = clamp(left, margin, Math.max(margin, window.innerWidth - panelWidth - margin));
      const top = clamp(defaultTop, margin, Math.max(margin, window.innerHeight - 260));
      panel.style.left = `${{left}}px`;
      panel.style.right = "auto";
      panel.style.top = `${{top}}px`;
      panel.style.maxHeight = `${{Math.max(260, window.innerHeight - top - margin)}}px`;
    }}

    function placeAndResizeFactoryPanel() {{
      positionFactoryPanel();
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

    function appendPanelMetaEntry(metaGrid, entry) {{
      const row = document.createElement("div");
      row.className = "panelMetaRow";
      const label = document.createElement("div");
      label.className = "panelMetaLabel";
      label.textContent = (entry && entry.label) || "";
      const value = document.createElement("div");
      value.className = "panelMetaValue";
      const rawValue = (entry && entry.value !== undefined && entry.value !== null)
        ? String(entry.value)
        : "";
      value.textContent = rawValue;
      if (!rawValue) {{
        row.style.gridColumn = "1 / span 2";
        label.style.fontWeight = "700";
        label.style.color = "#0f172a";
        value.style.display = "none";
      }} else if (rawValue.includes("\\n") || rawValue.length > 120) {{
        row.classList.add("multiline");
      }}
      row.appendChild(label);
      row.appendChild(value);
      metaGrid.appendChild(row);
    }}

    function renderPanelMeta(nodeId, nodeType) {{
      const metaBlock = document.getElementById("panelMeta");
      const metaTitle = document.getElementById("panelMetaTitle");
      const metaGrid = document.getElementById("panelMetaGrid");
      metaGrid.innerHTML = "";
      if (currentPanelMode === "data") {{
        const details = nodeType === "edge"
          ? (((DATA_PANEL.edges || {{}})[nodeId]) || null)
          : (((DATA_PANEL.nodes || {{}})[nodeId]) || null);
        const lines = details && Array.isArray(details.summary_lines) ? details.summary_lines : [];
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = (details && details.title) || "Donnees";
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
      if (currentPanelMode === "json") {{
        const details = nodeType === "edge"
          ? (((JSON_PANEL.edges || {{}})[nodeId]) || null)
          : (((JSON_PANEL.nodes || {{}})[nodeId]) || null);
        const lines = details && Array.isArray(details.summary_lines) ? details.summary_lines : [];
        if (!lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = (details && details.title) || "JSON";
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
        metaBlock.style.display = "block";
        return true;
      }}
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
        lines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
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
        entries.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
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
        metaTitle.textContent = "Flux et transits observes";
        const edgeSummary = [
          {{ label: "Flux", value: `${{edge.from}} -> ${{edge.to}}` }},
          {{ label: "Items", value: Array.isArray(edge.items) ? edge.items.join(", ") : "n/a" }},
          {{ label: "Transit planifie", value: `${{edge.planned_lead_days ?? 'n/a'}} j` }},
          {{ label: "Transit moyen observe", value: `${{edgeMetrics.avg_lead_days}} j` }},
          {{ label: "Transit min-max", value: `${{edgeMetrics.min_lead_days}} - ${{edgeMetrics.max_lead_days}} j` }},
          {{ label: "Transit p50 / p90", value: `${{edgeMetrics.lead_p50_days}} / ${{edgeMetrics.lead_p90_days}} j` }},
          {{ label: "Ecart-type transit", value: `${{edgeMetrics.lead_std_days}} j` }},
          {{ label: "Safety time destination", value: `${{edgeMetrics.safety_time_days}} j` }},
          {{ label: "Transit + safety moyen", value: `${{edgeMetrics.effective_lead_days}} j` }},
          {{ label: "Lignes d'expedition", value: `${{edgeMetrics.shipment_rows}}` }},
          {{ label: "Quantites distinctes", value: `${{edgeMetrics.distinct_shipped_qty}}` }},
        ];
        edgeSummary.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
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
        : (isFactoryLikeNode(nodeId, nodeType) ? "Performance industrielle courante" : "Synthese fournisseur");
      summaryLines.forEach((entry) => appendPanelMetaEntry(metaGrid, entry));
      metaBlock.style.display = "block";
      return true;
    }}

    function panelLabels(nodeId, nodeType) {{
      if (currentPanelMode === "data") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "Fiche flux",
            outgoing: "Source / destination",
            third: "Items transportes",
            fourth: "Couts et delais"
          }};
        }}
        return {{
          incoming: "Fiche noeud",
          outgoing: "Stocks / processus",
          third: "Flux connectes",
          fourth: "Items references"
        }};
      }}
      if (currentPanelMode === "json") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "JSON flux brut",
            outgoing: "JSON source / destination",
            third: "JSON items du flux",
            fourth: "JSON complet"
          }};
        }}
        return {{
          incoming: "JSON noeud brut",
          outgoing: "JSON stocks / processus",
          third: "JSON flux connectes",
          fourth: "JSON complet"
        }};
      }}
      if (currentPanelMode === "model") {{
        if (nodeType === "edge") {{
          return {{
            incoming: "Modele du flux",
            outgoing: "Caracteristiques du flux",
            third: "KPI du flux",
            fourth: "Source / destination"
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
      if (nodeId === "SDC-1450" && isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          incoming: "Stock intrants / PFI",
          outgoing: "Stock et expeditions PFI",
          third: "Planning lots production",
          fourth: "Pilotage MRP"
        }};
      }}
      if (nodeType === "supplier_dc") {{
        return {{
          incoming: "Fournisseur - flux physiques, stock, capacite, risques, incertitude, prediction",
          outgoing: "Expeditions fournisseur",
          third: "Planning lots production",
          fourth: "Pilotage MRP"
        }};
      }}
      if (isFactoryLikeNode(nodeId, nodeType)) {{
        return {{
          incoming: "Stock matieres",
          outgoing: "Flux aval",
          third: "Planning lots production",
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
          incoming: "Envois / receptions",
          outgoing: "Delais du flux",
          third: "Statuts carnet",
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
      if (currentPanelMode === "data") {{
        const details = nodeType === "edge"
          ? (((DATA_PANEL.edges || {{}})[nodeId]) || null)
          : (((DATA_PANEL.nodes || {{}})[nodeId]) || null);
        if (!details) return null;
        return {{
          incoming: details.incoming || null,
          outgoing: details.outgoing || null,
          third: details.third || null,
          fourth: details.fourth || null,
        }};
      }}
      if (currentPanelMode === "json") {{
        const details = nodeType === "edge"
          ? (((JSON_PANEL.edges || {{}})[nodeId]) || null)
          : (((JSON_PANEL.nodes || {{}})[nodeId]) || null);
        if (!details) return null;
        return {{
          incoming: details.incoming || null,
          outgoing: details.outgoing || null,
          third: details.third || null,
          fourth: details.fourth || null,
        }};
      }}
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
      if (nodeType === "supplier_dc") {{
        const supplierBase = SUPPLIER_HOVER_IMAGES[nodeId] || {{}};
        const supplierDirectEntries = modelDetails ? [
          {{ label: "Commandes / envois physiques", asset: modelDetails.supplier_order_send || null }},
          {{ label: "Graph stock fournisseur", asset: supplierBase.incoming || null }},
          {{ label: "Bilan stock fournisseur", asset: modelDetails.stock_flow || null }},
          {{ label: "Nominal fournisseur", asset: modelDetails.nominal || null }},
          {{ label: "Nominal capacite", asset: modelDetails.capacity_nominal || null }},
          {{ label: "Risques fournisseur", asset: modelDetails.supplier_risk_catalog || null }},
          {{ label: "Incertitude", asset: modelDetails.uncertainty || null }},
          {{ label: "Prediction risque", asset: modelDetails.risk_prediction || null }},
        ] : [
          {{ label: "Graph stock fournisseur", asset: supplierBase.incoming || null }},
        ];
        const supplierDirectBundle = {{
          bundle: supplierDirectEntries.filter(entry => !!entry.asset)
        }};
        const supplierDirectTop = supplierDirectBundle.bundle.length ? supplierDirectBundle : (supplierBase.incoming || null);
        const supplierMrpEntries = modelDetails ? [
          {{ label: "Carnet", asset: modelDetails.third || null }},
          {{ label: "Flux MRP", asset: modelDetails.outgoing || null }},
          {{ label: "Risques MRP", asset: modelDetails.risk || null }},
          {{ label: "Trace MRP", asset: modelDetails.incoming || null }},
        ] : [];
        const supplierMrpBundle = {{
          bundle: supplierMrpEntries.filter(entry => !!entry.asset)
        }};
        const supplierMrpFourth = supplierMrpBundle.bundle.length ? supplierMrpBundle : null;
        return {{ ...supplierBase, incoming: supplierDirectTop, fourth: supplierMrpFourth }};
      }}
      const modelBundleEntries = modelDetails ? [
        {{ label: "Nominal capacite", asset: modelDetails.capacity_nominal || null }},
        {{ label: "Carnet", asset: modelDetails.third || null }},
        {{ label: nodeType === "factory" ? "Ordres fournisseurs / receptions" : "Flux MRP", asset: modelDetails.outgoing || null }},
        {{ label: "Risques MRP", asset: modelDetails.risk || null }},
        {{ label: "Trace MRP", asset: modelDetails.incoming || null }},
      ] : [];
      if (nodeType !== "supplier_dc" && nodeType !== "customer") {{
        modelBundleEntries.unshift({{ label: "Reappro amont", asset: modelDetails ? (modelDetails.fourth || null) : null }});
      }}
      const modelBundle = modelDetails ? {{
        bundle: modelBundleEntries.filter(entry => !!entry.asset)
      }} : null;
      const modelFourth = modelBundle && modelBundle.bundle.length ? modelBundle : null;
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
          fourth: modelDetails.fourth || null,
        }};
      }}
      return modelFourth ? {{ fourth: modelFourth }} : null;
    }}

    function applyModeUi() {{
      document.getElementById("modeOps").classList.toggle("active", currentPanelMode === "ops");
      document.getElementById("modeData").classList.toggle("active", currentPanelMode === "data");
      document.getElementById("modeModel").classList.toggle("active", currentPanelMode === "model");
      document.getElementById("modeJson").classList.toggle("active", currentPanelMode === "json");
      document.getElementById("modeSensitivity").classList.toggle("active", currentPanelMode === "sensitivity");
      document.getElementById("modeStructural").classList.toggle("active", currentPanelMode === "structural");
      applyTimelineWindowUi();
    }}

    function setPanelMode(mode) {{
      currentPanelMode = mode;
      lastFactoryPanelRenderKey = "";
      applyModeUi();
      refreshFactoryPanel();
    }}

    function showFactoryPanel(nodeId, nodeType, panelState) {{
      const images = panelImages(nodeId, nodeType) || {{}};

      const panel = document.getElementById("factoryHoverPanel");
      const renderKey = [
        currentPanelMode,
        nodeType,
        nodeId,
        panelState || "",
        selectedYearStart,
        selectedYearEnd,
      ].join("|");
      if (panel.classList.contains("visible") && lastFactoryPanelRenderKey === renderKey) {{
        positionFactoryPanel();
        return;
      }}
      lastFactoryPanelRenderKey = renderKey;
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
      const incomingTabs = document.getElementById("incomingTabs");
      const outgoingTabs = document.getElementById("outgoingTabs");
      const thirdTabs = document.getElementById("thirdTabs");
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
        (isFactoryLikeNode(nodeId, nodeType) ? "Industrial Site" :
        (nodeType === "supplier_dc" ? "Supplier" :
        (nodeType === "distribution_center" ? "Distribution Center" : (nodeType === "factory" ? "Factory" : (nodeType === "customer" ? "Customer" : "Edge")))));
      const modeTitle = currentPanelMode === "sensitivity" ? "Sensibilite" :
        (currentPanelMode === "structural" ? "Structurel" : (currentPanelMode === "json" ? "DEBUG" : (currentPanelMode === "data" ? "Donnees" : (currentPanelMode === "model" ? "Modele" : "Simulation"))));
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
      fourthHelp.textContent = currentPanelMode === "json"
        ? "DEBUG: donnees brutes du scenario, enrichies avec items et flux connectes pour faciliter l'audit."
        : (currentPanelMode === "data"
          ? "Donnees: vue synthetique des champs JSON utiles au noeud ou au flux selectionne."
          : "Synthese en haut. Puis lis : stock, flux aval. Le bloc pilotage sert a l'analyse : reappro amont, carnet, risque, details MRP.");
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
              const showMarkers = Boolean(series.show_markers) || (filtered.days || []).length <= 2;
              const trace = {{
                type: "scatter",
                mode: showMarkers ? "lines+markers" : "lines",
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
              if (showMarkers) {{
                trace.marker = {{
                  size: Number(series.marker_size || 7),
                  color: series.color || palette[idx % palette.length],
                }};
              }}
              return trace;
            }}),
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: STANDARD_PLOT_MARGIN,
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              xaxis: dayAxisLayout(figure.x_label || "Jour"),
              yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
              legend: STANDARD_LEGEND,
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
              margin: STANDARD_PLOT_MARGIN,
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              xaxis: {{ tickangle: -20 }},
              yaxis: {{ title: figure.y_label || "", gridcolor: "#e2e8f0" }},
            }},
          }};
        }}
        if (figure.kind === "gantt") {{
          const palette = ["#0f766e", "#2563eb", "#d97706", "#7c3aed", "#0891b2", "#be123c"];
          const range = currentTimelineDayRange();
          const rows = (figure.rows || []).filter((row) => {{
            const start = Number(row.start) || 0;
            const end = Number(row.end) || start + Math.max(1, Number(row.duration) || 1);
            if (currentPanelMode !== "ops" || timelineMaxYear <= 1) return true;
            return end >= range.startDay && start <= range.endDay;
          }});
          const grouped = new Map();
          rows.forEach((row) => {{
            const lane = row.lane || row.item_label || row.item_id || "Lot";
            if (!grouped.has(lane)) grouped.set(lane, []);
            grouped.get(lane).push(row);
          }});
          const laneLabels = Array.from(grouped.keys()).reverse();
          const traces = Array.from(grouped.entries()).map(([lane, laneRows], idx) => {{
            return {{
              type: "bar",
              orientation: "h",
              name: lane,
              y: laneRows.map(() => lane),
              x: laneRows.map(row => Math.max(0.2, Number(row.duration) || Math.max(1, (Number(row.end) || 0) - (Number(row.start) || 0)))),
              base: laneRows.map(row => Number(row.start) || 0),
              marker: {{ color: palette[idx % palette.length], opacity: 0.82 }},
              customdata: laneRows.map(row => [
                Number(row.start) || 0,
                Number(row.duration) || 0,
                Number(row.qty) || 0,
                Number(row.lots) || 0,
                row.lot_policy || "",
                row.binding_cause || "none",
                row.duration_basis || "",
                row.capacity_mode || "",
                Number(row.cap_qty) || 0,
                Number(row.tau_process) || 0,
              ]),
              hovertemplate: `${{lane}}<br>lancement=J%{{customdata[0]}}<br>duree visuelle=%{{customdata[1]:.1f}} j<br>quantite=%{{customdata[2]:,.0f}}<br>lots=%{{customdata[3]:.2f}}<br>base duree=%{{customdata[6]}}<br>mode capacite=%{{customdata[7]}}<br>capacite/j=%{{customdata[8]:,.0f}}<br>tau_process info=%{{customdata[9]:.1f}} j<br>politique=%{{customdata[4]}}<br>contrainte=%{{customdata[5]}}<extra></extra>`,
            }};
          }});
          return {{
            data: traces,
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: GANTT_PLOT_MARGIN,
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              barmode: "overlay",
              bargap: 0.32,
              xaxis: dayAxisLayout(figure.x_label || "Jour"),
              yaxis: {{
                title: figure.y_label || "",
                categoryorder: "array",
                categoryarray: laneLabels,
                gridcolor: "#f1f5f9",
              }},
              legend: STANDARD_LEGEND,
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
        if (figure.kind === "dual_panel") {{
          const top = figure.top || {{}};
          const bottom = figure.bottom || {{}};
          const topFiltered = top.kind === "line" ? filterXYByTimeline(top.x || [], top.y || []) : {{ x: top.x || [], y: top.y || [] }};
          const bottomFiltered = bottom.kind === "line" ? filterXYByTimeline(bottom.x || [], bottom.y || []) : {{ x: bottom.x || [], y: bottom.y || [] }};
          const topXAxis = top.kind === "line"
            ? dayAxisLayout(top.x_label || "")
            : {{ title: top.x_label || "", gridcolor: "#e2e8f0" }};
          const bottomXAxis = bottom.kind === "line"
            ? dayAxisLayout(bottom.x_label || "")
            : {{ title: bottom.x_label || "", tickangle: -20, gridcolor: "#e2e8f0" }};
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
                showlegend: false,
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
                showlegend: false,
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
                showlegend: false,
              }}
            : {{
                type: "bar",
                x: bottom.x || [],
                y: bottom.y || [],
                marker: {{ color: "#2563eb" }},
                xaxis: "x2",
                yaxis: "y2",
                name: bottom.title || "Panel 2",
                showlegend: false,
              }});
          (top.extra_traces || []).forEach((trace) => {{
            traces.push({{
              ...trace,
              xaxis: "x",
              yaxis: "y",
            }});
          }});
          (bottom.extra_traces || []).forEach((trace) => {{
            traces.push({{
              ...trace,
              xaxis: "x2",
              yaxis: "y2",
            }});
          }});
          return {{
            data: traces,
            layout: {{
              title: {{ text: figure.title || "", font: {{ size: 12 }} }},
              margin: {{ l: 60, r: 20, t: 48, b: 46 }},
              paper_bgcolor: "#ffffff",
              plot_bgcolor: "#ffffff",
              grid: {{ rows: 2, columns: 1, pattern: "independent", roworder: "top to bottom" }},
              xaxis: topXAxis,
              yaxis: {{ title: top.y_label || "", gridcolor: "#e2e8f0" }},
              xaxis2: bottomXAxis,
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
              showlegend: Boolean(figure.show_legend),
              legend: {{ orientation: "h", y: -0.18 }},
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
          installCtrlScrollZoomGate(mainChartEl);
          Plotly.react(mainChartEl, traces, {{
            title: {{ text: "KPI principaux - vue management", font: {{ size: 12 }} }},
            margin: {{ l: 54, r: 18, t: 42, b: 42 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: dayAxisLayout("Jour"),
            yaxis: {{ title: main.y_label || "Score / indice", gridcolor: "#e2e8f0" }},
            legend: {{ orientation: "h", y: -0.22 }},
          }}, PLOTLY_RESPONSIVE_CONFIG);
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
              line: {{ width: 2.2, color: series.color || "#2563eb", dash: series.dash || "solid" }},
            }};
          }});
          installCtrlScrollZoomGate(secondaryChartEl);
          Plotly.react(secondaryChartEl, traces, {{
            title: {{ text: `KPI secondaires - ${{group.label || selectedId}}`, font: {{ size: 12 }} }},
            margin: {{ l: 58, r: 18, t: 42, b: 42 }},
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            xaxis: dayAxisLayout("Jour"),
            yaxis: {{ title: group.secondary_y_label || "Valeur", gridcolor: "#e2e8f0" }},
            legend: {{ orientation: "h", y: -0.24 }},
          }}, PLOTLY_RESPONSIVE_CONFIG);
        }}
        renderCards();
        renderMain();
        renderSecondary();
        return true;
      }}

      const plotRenderJobs = [];

      function runQueuedPanelPlotRenderJobs() {{
        const jobs = plotRenderJobs.splice(0, plotRenderJobs.length);
        jobs.forEach((renderJob) => {{
          try {{ renderJob(); }} catch (e) {{}}
        }});
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

        function sizedPlotlyLayout(layout, targetEl) {{
          const panel = document.getElementById("factoryHoverPanel");
          const holder = (targetEl.classList && targetEl.classList.contains("factoryFigureStackItem"))
            ? targetEl
            : (targetEl.closest(".factoryFigureStackItem") || targetEl.closest(".factoryPlotFigure") || targetEl.parentElement || targetEl);
          const panelWidth = panel ? panel.clientWidth : 900;
          const width = Math.max(320, Math.min(840, Math.floor((panelWidth || 900) - 28)));
          const isStackItem = holder.classList && holder.classList.contains("factoryFigureStackItem");
          const isCompactFigure = holder.classList && (
            holder.classList.contains("factoryPlotOutgoing") ||
            holder.classList.contains("factoryPlotThird") ||
            holder.classList.contains("factoryPlotFourth")
          );
          const height = isStackItem ? 360 : (isCompactFigure ? 320 : 380);
          return {{
            ...(layout || {{}}),
            autosize: false,
            width,
            height,
            showlegend: (layout || {{}}).showlegend ?? true,
          }};
        }}

        imgEl.removeAttribute("src");
        imgEl.style.display = "none";
        figureEl.innerHTML = "";
        figureEl.style.display = "none";
        figureEl.classList.remove("factoryHtmlPanel");
        figureEl.classList.remove("factoryOrderLedgerPanel");
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
            const graphIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "graph stock fournisseur");
            const physicalFlowIdx = entries.findIndex(entry => (entry.label || "").toLowerCase().includes("envois physiques"));
            const carnetIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "carnet");
            const nominalIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "nominal fournisseur");
            const preferredIdx = selectionKey.endsWith(":incoming")
              ? (physicalFlowIdx >= 0 ? physicalFlowIdx : (graphIdx >= 0 ? graphIdx : 0))
              : (selectionKey.endsWith(":fourth") ? (carnetIdx >= 0 ? carnetIdx : 0) : (nominalIdx >= 0 ? nominalIdx : 0));
            if (preferredIdx >= 0) {{
              selectedIdx = preferredIdx;
              panelBundleSelection[selectionKey] = preferredIdx;
            }}
          }} else if (!hasSavedSelection && selectionKey.includes(":factory:")) {{
            const capacityIdx = entries.findIndex(entry => (entry.label || "").toLowerCase() === "nominal capacite");
            if (capacityIdx >= 0) {{
              selectedIdx = capacityIdx;
              panelBundleSelection[selectionKey] = capacityIdx;
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
                requestAnimationFrame(() => {{
                  placeAndResizeFactoryPanel();
                  requestAnimationFrame(runQueuedPanelPlotRenderJobs);
                }});
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
          if (figureEl.querySelector(".orderLedgerPanelContent")) {{
            figureEl.classList.add("factoryOrderLedgerPanel");
          }}
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
              plotRenderJobs.push(() => {{
                installCtrlScrollZoomGate(child);
                Plotly.react(child, plotlyFigure.data, sizedPlotlyLayout(plotlyFigure.layout, child), PLOTLY_PANEL_CONFIG);
              }});
            }}
          }});
          return true;
        }}
        const plotlyFigure = buildPlotlyFigure(asset.figure || null);
        if (plotlyFigure && window.Plotly) {{
          figureEl.style.display = "block";
          const plotHost = document.createElement("div");
          plotHost.className = "factoryPlotInner";
          figureEl.appendChild(plotHost);
          plotRenderJobs.push(() => {{
            installCtrlScrollZoomGate(plotHost);
            Plotly.react(plotHost, plotlyFigure.data, sizedPlotlyLayout(plotlyFigure.layout, plotHost), PLOTLY_PANEL_CONFIG);
          }});
          return true;
        }}
        return false;
      }}

      panel.classList.add("visible");
      panel.classList.toggle("hoverPreview", panelState === "Survol");
      positionFactoryPanel();

      let visibleCount = 0;
      if (renderAsset(incomingImageInfo, incomingImg, incomingFigure, incomingTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:incoming`)) visibleCount += 1;
      if (renderAsset(outgoingImageInfo, outgoingImg, outgoingFigure, outgoingTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:outgoing`)) visibleCount += 1;
      if (renderAsset(thirdImageInfo, thirdImg, thirdFigure, thirdTabs, `${{currentPanelMode}}:${{nodeType}}:${{nodeId}}:third`)) visibleCount += 1;
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
      const panelRenderToken = ++pendingPanelPlotRenderToken;
      requestAnimationFrame(() => {{
        if (panelRenderToken !== pendingPanelPlotRenderToken) return;
        placeAndResizeFactoryPanel();
        requestAnimationFrame(() => {{
          if (panelRenderToken !== pendingPanelPlotRenderToken) return;
          if (!panel.classList.contains("visible")) return;
          runQueuedPanelPlotRenderJobs();
        }});
      }});
    }}

    function bindHoverHandlers() {{
      if (hoverHandlersBound) return;
      const gd = document.getElementById("chart");
      gd.on("plotly_hover", (ev) => {{
        if (hoverClearTimeout) {{
          clearTimeout(hoverClearTimeout);
          hoverClearTimeout = null;
        }}
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
        if (!selectedPanelNodeId) {{
          updatePanelAnchorFromEvent(ev);
        }}
        currentHoveredPanelId = nodeId;
        currentHoveredPanelType = nodeType;
        refreshFactoryPanel();
      }});
      gd.on("plotly_unhover", () => {{
        if (hoverClearTimeout) clearTimeout(hoverClearTimeout);
        hoverClearTimeout = setTimeout(() => {{
          hoverClearTimeout = null;
          if (panelPointerInside || selectedPanelNodeId) return;
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
        }}, 180);
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
        updatePanelAnchorFromEvent(ev);
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
        hoverdistance: 1,
        spikedistance: -1,
        geo: geoLayout
      }};

      const chartEl = document.getElementById("chart");
      Plotly.newPlot(chartEl, traces, layout, PLOTLY_MAP_CONFIG);
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
              <div class="kpiTreeSubtitle">Fenetre: ${{selectedTimelineWindowLabel()}}</div>
            </div>
            <div class="kpiTreeControls">
              <span class="kpiTreeControlGroup">
                <span>Lissage</span>
                <button type="button" class="kpiTreeSmoothBtn" data-smooth="none">Sans</button>
                <button type="button" class="kpiTreeSmoothBtn" data-smooth="week">7 j</button>
                <button type="button" class="kpiTreeSmoothBtn active" data-smooth="month">30 j</button>
              </span>
            </div>
          </div>
          <div class="kpiTreeViewTabs">
            <button type="button" class="kpiTreeViewBtn active" data-kpi-view="graphs">Graphes</button>
            <button type="button" class="kpiTreeViewBtn" data-kpi-view="formulas">Formules</button>
            <button type="button" class="kpiTreeViewBtn" data-kpi-view="physics">Physics of Decision</button>
          </div>
          <div class="kpiTreeView kpiTreeGraphView active">
            <div class="kpiTreeCards"></div>
            <div class="kpiTreeChart kpiTreeMainChart"></div>
            <div class="kpiTreeDetail">
              <div class="kpiTreeSummary"></div>
              <div class="kpiTreeChart kpiTreeSecondaryChart"></div>
            </div>
          </div>
          <div class="kpiTreeView kpiTreeFormulaView">
            <div class="kpiFormulaIntro">
              Tableau de reference des KPI. Le terme <b>pilotable</b> designe la partie generee par les decisions de reapprovisionnement du scenario; le carnet initial deja engage est affiche separement.
              Pour l'adherence lignes mensuelle, la <b>Reference</b> est reconstruite par ligne site/produit: produit fini = demande client; semi-fini/intermediaire = consommation aval observee; si cette consommation aval n'est pas disponible, fallback = <code>desired_qty</code>, c'est-a-dire le besoin de production demande par le simulateur.
            </div>
            <div class="kpiFormulaTableWrap">
              <table class="kpiFormulaTable">
                <thead>
                  <tr>
                    <th>Famille</th>
                    <th>Niveau</th>
                    <th>KPI</th>
                    <th>Formule</th>
                    <th>Definition / lecture</th>
                  </tr>
                </thead>
                <tbody></tbody>
              </table>
            </div>
          </div>
          <div class="kpiTreeView kpiTreePhysicsView">
            <div class="kpiFormulaIntro">
              Surcouche independante inspiree de la Physics of Decision: chaque KPI est converti en distance normalisee a sa cible, puis les distances sont agregees par norme euclidienne ponderee.
            </div>
            <div class="kpiPhysicsGrid">
              <div class="kpiPhysicsStack">
                <div class="kpiTreeSummary kpiPhysicsSummary"></div>
                <div class="kpiTreeChart kpiPhysicsContributionChart"></div>
              </div>
              <div class="kpiPhysicsStack">
                <div class="kpiTreeChart kpiPhysicsScoreChart"></div>
                <div class="kpiTreeChart kpiPhysicsDistanceChart"></div>
              </div>
            </div>
          </div>
        </div>
      `;
      const cardsEl = figureEl.querySelector(".kpiTreeCards");
      const mainChartEl = figureEl.querySelector(".kpiTreeMainChart");
      const summaryEl = figureEl.querySelector(".kpiTreeSummary");
      const secondaryChartEl = figureEl.querySelector(".kpiTreeSecondaryChart");
      const graphViewEl = figureEl.querySelector(".kpiTreeGraphView");
      const formulaViewEl = figureEl.querySelector(".kpiTreeFormulaView");
      const physicsViewEl = figureEl.querySelector(".kpiTreePhysicsView");
      const formulaBodyEl = figureEl.querySelector(".kpiFormulaTable tbody");
      const physicsSummaryEl = figureEl.querySelector(".kpiPhysicsSummary");
      const physicsScoreChartEl = figureEl.querySelector(".kpiPhysicsScoreChart");
      const physicsDistanceChartEl = figureEl.querySelector(".kpiPhysicsDistanceChart");
      const physicsContributionChartEl = figureEl.querySelector(".kpiPhysicsContributionChart");
      const viewButtons = Array.from(figureEl.querySelectorAll("[data-kpi-view]"));
      const smoothButtons = Array.from(figureEl.querySelectorAll(".kpiTreeSmoothBtn"));
      let selectedId = globalKpiTreeState.selectedId && groups.some(group => group.id === globalKpiTreeState.selectedId)
        ? globalKpiTreeState.selectedId
        : groups[0].id;
      let smoothingMode = globalKpiTreeState.smoothingMode || "month";
      let viewMode = globalKpiTreeState.viewMode || "graphs";

      function groupById(groupId) {{
        return groups.find(group => group.id === groupId) || groups[0];
      }}
      function escapeKpiHtml(value) {{
        return String(value ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }}
      function renderFormulaTable() {{
        if (!formulaBodyEl) return;
        const definitions = asset.definitions || [];
        formulaBodyEl.innerHTML = definitions.map(row => `
          <tr>
            <td><span class="kpiFormulaFamily">${{escapeKpiHtml(row.family || "")}}</span></td>
            <td><span class="kpiFormulaLevel">${{escapeKpiHtml(row.level || "")}}</span></td>
            <td>${{escapeKpiHtml(row.name || "")}}</td>
            <td>
              <div>${{escapeKpiHtml(row.formula || "")}}</div>
              ${{row.terms ? `<div class="kpiFormulaTerms"><span class="kpiFormulaTermsLabel">Termes:</span> ${{escapeKpiHtml(row.terms)}}</div>` : ""}}
            </td>
            <td>${{escapeKpiHtml(row.interpretation || "")}}</td>
          </tr>
        `).join("") || '<tr><td colspan="5">Definitions KPI non disponibles.</td></tr>';
      }}
      function renderKpiView() {{
        viewButtons.forEach(btn => btn.classList.toggle("active", (btn.dataset.kpiView || "graphs") === viewMode));
        if (graphViewEl) graphViewEl.classList.toggle("active", viewMode === "graphs");
        if (formulaViewEl) formulaViewEl.classList.toggle("active", viewMode === "formulas");
        if (physicsViewEl) physicsViewEl.classList.toggle("active", viewMode === "physics");
        if (viewMode === "graphs") {{
          renderMain();
          renderSecondary();
        }} else if (viewMode === "formulas") {{
          renderFormulaTable();
        }} else {{
          renderPhysicsView();
        }}
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
        return null;
      }}
      function startupSuffix() {{
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
        return filterSeriesByTimeline(filteredDays, filteredValues, true);
      }}
      function finiteValues(values) {{
        return (values || [])
          .map(value => Number(value))
          .filter(value => Number.isFinite(value));
      }}
      function sumValues(values) {{
        return finiteValues(values).reduce((acc, value) => acc + value, 0);
      }}
      function averageValues(values) {{
        const numeric = finiteValues(values);
        return numeric.length ? numeric.reduce((acc, value) => acc + value, 0) / numeric.length : 0;
      }}
      function maxValue(values) {{
        const numeric = finiteValues(values);
        return numeric.length ? Math.max(...numeric) : 0;
      }}
      function countPositive(values) {{
        return finiteValues(values).filter(value => value > 1e-9).length;
      }}
      function pctText(value) {{
        return `${{fmtPanelQty(value, 1)}}%`;
      }}
      function qtyText(value, digits = 1) {{
        return fmtPanelQty(value, digits);
      }}
      function findSeries(seriesList, expectedLabel) {{
        const expected = String(expectedLabel || "").toLowerCase();
        return (seriesList || []).find(series => String(series.label || "").toLowerCase() === expected) || null;
      }}
      function seriesWindowValues(series, smooth = false) {{
        if (!series) return [];
        const values = smooth ? smoothValues(series.values || []) : (series.values || []);
        return filterStartupAndTimeline(series.days || [], values).values;
      }}
      function seriesWindowValuesByPrefix(seriesList, prefix, smooth = false) {{
        const expected = String(prefix || "").toLowerCase();
        return (seriesList || [])
          .filter(series => String(series.label || "").toLowerCase().startsWith(expected))
          .flatMap(series => seriesWindowValues(series, smooth));
      }}
      function summaryEntry(label, value) {{
        return {{ label, value }};
      }}
      function buildWindowSummary(group) {{
        const secondary = group.secondary || [];
        if (group.id === "availability") {{
          const demand = seriesWindowValues(findSeries(secondary, "Demande"));
          const required = seriesWindowValues(findSeries(secondary, "Besoin avec backlog"));
          const served = seriesWindowValues(findSeries(secondary, "Servi"));
          const backlog = seriesWindowValues(findSeries(secondary, "Backlog fin de jour"));
          const totalDemand = sumValues(demand);
          const totalRequired = sumValues(required);
          const totalServed = sumValues(served);
          return [
            summaryEntry("Fenetre", selectedTimelineWindowLabel()),
            summaryEntry("Fill rate cumule", pctText(totalDemand ? 100 * totalServed / totalDemand : 100)),
            summaryEntry("Service besoin+backlog", pctText(totalRequired ? 100 * totalServed / totalRequired : 100)),
            summaryEntry("Jours avec backlog", String(countPositive(backlog))),
            summaryEntry("Backlog max", qtyText(maxValue(backlog), 1)),
            summaryEntry("Besoin cumule", qtyText(totalRequired, 1)),
          ];
        }}
        if (group.id === "production") {{
          return [
            summaryEntry("Fenetre", selectedTimelineWindowLabel()),
            summaryEntry("Adherence lignes mensuelle", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Adherence lignes mensuelle (%)"), true)))),
            summaryEntry("Adherence plan lotifie", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Adherence plan lotifie mensuelle (%)"), true)))),
            summaryEntry("Couverture demande horizon 30j", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Couverture demande horizon 30j (%)"), true)))),
            summaryEntry("Rattrapage retard net 30j", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Taux de rattrapage retard net 30j (%)"), true)))),
            summaryEntry("Retard/deficit moyen lignes", pctText(averageValues(seriesWindowValuesByPrefix(secondary, "Retard/deficit production", true)))),
            summaryEntry("Avance/exces moyen lignes", pctText(averageValues(seriesWindowValuesByPrefix(secondary, "Avance/exces production", true)))),
            summaryEntry("Contraintes sur ligne", pctText(averageValues(seriesWindowValues(findSeries(secondary, "Contraintes sur ligne capacite / input / lots semaine (%)"), true)))),
          ];
        }}
        if (group.id === "cost") {{
          const total = sumValues(seriesWindowValues(findSeries(secondary, "Cout operationnel total")));
          const purchase = sumValues(seriesWindowValues(findSeries(secondary, "Cout d'achat matiere")));
          const production = sumValues(seriesWindowValues(findSeries(secondary, "Cout de production")));
          const inventory = sumValues(seriesWindowValues(findSeries(secondary, "Cout stock")));
          const transport = sumValues(seriesWindowValues(findSeries(secondary, "Cout de transport pilotable")));
          const share = (value) => total > 1e-9 ? pctText(100 * value / total) : "0,0%";
          return [
            summaryEntry("Fenetre", selectedTimelineWindowLabel()),
            summaryEntry("Cout operationnel total", qtyText(total, 1)),
            summaryEntry("Cout d'achat matiere", `${{qtyText(purchase, 1)}} (${{share(purchase)}})`),
            summaryEntry("Cout de production", `${{qtyText(production, 1)}} (${{share(production)}})`),
            summaryEntry("Cout stock", `${{qtyText(inventory, 1)}} (${{share(inventory)}})`),
            summaryEntry("Cout de transport pilotable", `${{qtyText(transport, 1)}} (${{share(transport)}})`),
          ];
        }}
        return group.summary || [];
      }}
      function physicsWindowValues(values, smooth = true) {{
        const physics = asset.physics || {{}};
        const sourceValues = smooth ? smoothValues(values || []) : (values || []);
        return filterPhysicsSeriesByTimeline(physics.days || [], sourceValues).values;
      }}
      function physicsWindowDays(values, smooth = true) {{
        const physics = asset.physics || {{}};
        const sourceValues = smooth ? smoothValues(values || []) : (values || []);
        return filterPhysicsSeriesByTimeline(physics.days || [], sourceValues).days;
      }}
      function filterPhysicsSeriesByTimeline(days, values) {{
        const physics = asset.physics || {{}};
        const cutoff = Number(physics.startup_cutoff_day);
        const shouldFilterStartup = Number.isFinite(cutoff) && cutoff > 0;
        const filteredDays = [];
        const filteredValues = [];
        (days || []).forEach((day, idx) => {{
          const dayNum = Number(day);
          if (shouldFilterStartup && Number.isFinite(dayNum) && dayNum < cutoff) return;
          filteredDays.push(day);
          filteredValues.push((values || [])[idx] ?? 0);
        }});
        return filterSeriesByTimeline(filteredDays, filteredValues, true);
      }}
      function renderPhysicsSummary(physics) {{
        if (!physicsSummaryEl) return;
        const scoreSeries = ((physics.main || {{}}).series || []).find(series => series.id === "global_score") || null;
        const scoreValues = scoreSeries ? physicsWindowValues(scoreSeries.values || [], true) : [];
        const impactRows = (physics.weighted_term_series || []).map(series => {{
          const values = physicsWindowValues(series.values || [], false);
          return {{
            label: series.label || series.id,
            total: sumValues(values),
          }};
        }}).sort((a, b) => b.total - a.total);
        const totalImpact = impactRows.reduce((acc, row) => acc + row.total, 0);
        const summaryRows = [
          summaryEntry("Fenetre", selectedTimelineWindowLabel()),
          summaryEntry("Jours exclus", Number.isFinite(Number(physics.startup_cutoff_day)) && Number(physics.startup_cutoff_day) > 0 ? `J0 -> J${{Number(physics.startup_cutoff_day) - 1}}` : "aucun"),
          summaryEntry("Score derive moyen", averageValues(scoreValues).toFixed(3)),
          summaryEntry("Score derive max", maxValue(scoreValues).toFixed(3)),
          summaryEntry("Lecture", "0=cible ; 1=catastrophe"),
          summaryEntry("CSV derive", physics.csv_path ? String(physics.csv_path).split(/[\\\\/]/).pop() : "n/a"),
        ];
        impactRows.slice(0, 5).forEach((row, idx) => {{
          const share = totalImpact > 1e-12 ? 100 * row.total / totalImpact : 0;
          summaryRows.push(summaryEntry(`Impact ${{idx + 1}}`, `${{row.label}} - ${{fmtPanelQty(share, 1)}}% cumule`));
        }});
        physicsSummaryEl.innerHTML = "";
        summaryRows.forEach(row => {{
          const div = document.createElement("div");
          div.className = "kpiTreeSummaryRow";
          div.innerHTML = `<span class="kpiTreeSummaryLabel">${{row.label || ""}}</span><span class="kpiTreeSummaryValue">${{row.value || ""}}</span>`;
          physicsSummaryEl.appendChild(div);
        }});
      }}
      function renderPhysicsChart(targetEl, seriesList, title, yLabel, yRange = null) {{
        if (!targetEl) return;
        const palette = ["#111827", "#0f766e", "#2563eb", "#d97706", "#7c3aed", "#dc2626", "#0891b2", "#be123c"];
        const traces = (seriesList || []).map((series, idx) => {{
          const values = smoothValues(series.values || []);
          const filtered = filterPhysicsSeriesByTimeline((asset.physics || {{}}).days || [], values);
          return {{
            type: "scatter",
            mode: "lines",
            name: `${{series.label || series.id}}${{smoothingSuffix()}}`,
            x: filtered.days,
            y: filtered.values,
            line: {{
              width: idx === 0 ? 2.8 : 2.0,
              color: series.color || palette[idx % palette.length],
              dash: series.dash || "solid",
            }},
            hovertemplate: `${{series.label || series.id}}<br>Jour=%{{x}}<br>Valeur=%{{y:.3f}}<extra></extra>`,
          }};
        }});
        const layout = {{
          title: {{ text: `${{title}} (${{selectedTimelineWindowLabel()}})`, font: {{ size: 12 }} }},
          margin: {{ l: 58, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout("Jour"),
          yaxis: {{ title: yLabel, gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.25 }},
        }};
        if (Array.isArray(yRange)) {{
          layout.yaxis.range = yRange;
        }}
        installCtrlScrollZoomGate(targetEl);
        Plotly.react(targetEl, traces, layout, PLOTLY_RESPONSIVE_CONFIG);
      }}
      function renderPhysicsView() {{
        const physics = asset.physics || null;
        if (!physics || physics.kind !== "physics_kpi") {{
          if (physicsSummaryEl) physicsSummaryEl.innerHTML = '<div class="panelEmptyState">Vue Physics of Decision non disponible pour ce run.</div>';
          return;
        }}
        renderPhysicsSummary(physics);
        renderPhysicsChart(
          physicsScoreChartEl,
          ((physics.main || {{}}).series || []),
          "Trajectoire du score global",
          "Score 0 cible / 1 catastrophe",
          [0, 1]
        );
        renderPhysicsChart(
          physicsDistanceChartEl,
          physics.distance_series || [],
          "Distances normalisees par KPI",
          "Distance normalisee",
          [0, 1]
        );
        renderPhysicsChart(
          physicsContributionChartEl,
          physics.contribution_series || [],
          "Parts journalieres de derive",
          "Contribution (%)",
          [0, 100]
        );
      }}
      function syncSmoothingButtons() {{
        smoothButtons.filter(btn => btn.dataset.smooth).forEach(btn => {{
          btn.classList.toggle("active", (btn.dataset.smooth || "none") === smoothingMode);
        }});
      }}
      function bindSmoothingControls() {{
        viewButtons.forEach(btn => {{
          btn.onclick = () => {{
            viewMode = btn.dataset.kpiView || "graphs";
            globalKpiTreeState.viewMode = viewMode;
            renderKpiView();
          }};
        }});
        smoothButtons.filter(btn => btn.dataset.smooth).forEach(btn => {{
          btn.onclick = () => {{
            smoothingMode = btn.dataset.smooth || "none";
            globalKpiTreeState.smoothingMode = smoothingMode;
            syncSmoothingButtons();
            if (viewMode === "physics") {{
              renderPhysicsView();
            }} else {{
              renderMain();
              renderSecondary();
            }}
          }};
        }});
        syncSmoothingButtons();
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
            globalKpiTreeState.selectedId = selectedId;
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
        installCtrlScrollZoomGate(mainChartEl);
        Plotly.react(mainChartEl, traces, {{
            title: {{ text: `KPI principaux - vue management (${{selectedTimelineWindowLabel()}})`, font: {{ size: 12 }} }},
          margin: {{ l: 54, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout("Jour"),
          yaxis: {{ title: main.y_label || "Score / indice", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.22 }},
        }}, PLOTLY_RESPONSIVE_CONFIG);
        mainChartEl.on("plotly_click", (ev) => {{
          const point = ev && ev.points && ev.points[0];
          const groupId = point && point.customdata;
          if (groupId) {{
            selectedId = groupId;
            globalKpiTreeState.selectedId = selectedId;
            renderCards();
            renderSecondary();
          }}
        }});
      }}
      function renderSecondary() {{
        const group = groupById(selectedId);
        summaryEl.innerHTML = "";
        buildWindowSummary(group).forEach(row => {{
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
            line: {{ width: 2.2, color: series.color || "#2563eb", dash: series.dash || "solid" }},
          }};
        }});
        installCtrlScrollZoomGate(secondaryChartEl);
        Plotly.react(secondaryChartEl, traces, {{
          title: {{ text: `KPI secondaires - ${{group.label || selectedId}} (${{selectedTimelineWindowLabel()}})`, font: {{ size: 12 }} }},
          margin: {{ l: 58, r: 18, t: 42, b: 42 }},
          paper_bgcolor: "#ffffff",
          plot_bgcolor: "#ffffff",
          xaxis: dayAxisLayout("Jour"),
          yaxis: {{ title: group.secondary_y_label || "Valeur", gridcolor: "#e2e8f0" }},
          legend: {{ orientation: "h", y: -0.24 }},
        }}, PLOTLY_RESPONSIVE_CONFIG);
      }}
      bindSmoothingControls();
      renderCards();
      renderFormulaTable();
      renderKpiView();
      return true;
    }}

    function renderGlobalKpiTreeIfVisible() {{
      const modal = document.getElementById("kpiTreeModal");
      if (modal && modal.classList.contains("visible")) {{
        renderGlobalKpiTree();
      }}
    }}

    function init() {{
      initFilters();
      syncYearInputs();
      updateTimelineWindowLabel();
      applyModeUi();
      const materialTableModal = document.getElementById("materialTableModal");
      document.getElementById("materialTableBtn").addEventListener("click", () => {{
        renderMaterialTable();
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
      const modelEquationsModal = document.getElementById("modelEquationsModal");
      document.getElementById("modelEquationsBtn").addEventListener("click", () => {{
        modelEquationsModal.classList.add("visible");
      }});
      document.getElementById("modelEquationsCloseBtn").addEventListener("click", () => {{
        modelEquationsModal.classList.remove("visible");
      }});
      modelEquationsModal.addEventListener("click", (ev) => {{
        if (ev.target === modelEquationsModal) {{
          modelEquationsModal.classList.remove("visible");
        }}
      }});
      document.getElementById("showEdges").addEventListener("change", draw);
      document.getElementById("modeOps").addEventListener("click", () => setPanelMode("ops"));
      document.getElementById("modeData").addEventListener("click", () => setPanelMode("data"));
      document.getElementById("modeModel").addEventListener("click", () => setPanelMode("model"));
      document.getElementById("modeJson").addEventListener("click", () => setPanelMode("json"));
      document.getElementById("modeSensitivity").addEventListener("click", () => setPanelMode("sensitivity"));
      document.getElementById("modeStructural").addEventListener("click", () => setPanelMode("structural"));
      const hoverPanel = document.getElementById("factoryHoverPanel");
      hoverPanel.addEventListener("mouseenter", () => {{
        panelPointerInside = true;
        if (hoverClearTimeout) {{
          clearTimeout(hoverClearTimeout);
          hoverClearTimeout = null;
        }}
      }});
      hoverPanel.addEventListener("mouseleave", () => {{
        panelPointerInside = false;
        if (!selectedPanelNodeId) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
        }}
      }});
      document.getElementById("yearStart").addEventListener("input", (ev) => {{
        selectedYearStart = Number(ev.target.value || 1);
        if (selectedYearStart > selectedYearEnd) {{
          selectedYearEnd = selectedYearStart;
        }}
        syncYearInputs();
        updateTimelineWindowLabel();
        renderMaterialTable();
        refreshFactoryPanel();
        renderGlobalKpiTreeIfVisible();
      }});
      document.getElementById("yearEnd").addEventListener("input", (ev) => {{
        selectedYearEnd = Number(ev.target.value || 1);
        if (selectedYearEnd < selectedYearStart) {{
          selectedYearStart = selectedYearEnd;
        }}
        syncYearInputs();
        updateTimelineWindowLabel();
        renderMaterialTable();
        refreshFactoryPanel();
        renderGlobalKpiTreeIfVisible();
      }});
      document.getElementById("factoryHoverClearSelection").addEventListener("click", clearPanelSelection);
      window.addEventListener("resize", placeAndResizeFactoryPanel);
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
    supplier_stock_flows_csv = (
        Path(args.supplier_stock_flows_csv)
        if args.supplier_stock_flows_csv
        else supplier_stocks_csv.parent / "production_supplier_stock_flows_daily.csv"
    )
    supplier_capacity_csv = Path(args.supplier_capacity_csv)
    supplier_nominal_parameters_csv = (
        Path(args.supplier_nominal_parameters_csv)
        if args.supplier_nominal_parameters_csv
        else supplier_capacity_csv.parent / "supplier_nominal_parameters.csv"
    )
    factory_nominal_capacities_csv = (
        Path(args.factory_nominal_capacities_csv)
        if args.factory_nominal_capacities_csv
        else supplier_capacity_csv.parent / "production_capacity_nominal_parameters.csv"
    )
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
        payload["data_panel"] = build_data_panel_payload(raw)
        payload["json_panel"] = build_json_panel_payload(raw)
        payload["timeline_horizon_days"] = read_timeline_horizon_days(output_root_from_csv(demand_service_csv))
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
            supplier_stock_flows_csv,
            supplier_capacity_csv,
        )
        payload["distribution_center_hover_images"] = build_distribution_center_hover_images(
            raw,
            sim_input_png_dir,
            Path(args.dc_stocks_csv),
            supplier_shipments_csv,
            Path(args.dc_stocks_csv).parent / "mrp_trace_daily.csv",
        )
        edge_metrics = build_edge_metrics(
            raw,
            supplier_shipments_csv,
            horizon_days=read_timeline_horizon_days(output_root_from_csv(demand_service_csv)),
        )
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
            supplier_stock_flows_csv=supplier_stock_flows_csv,
            supplier_capacity_csv=supplier_capacity_csv,
            supplier_nominal_parameters_csv=supplier_nominal_parameters_csv,
            factory_nominal_capacities_csv=factory_nominal_capacities_csv,
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
            Path(args.dc_stocks_csv).parent / "mrp_orders_daily.csv",
            raw,
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
            sim_dc_stocks_csv=Path(args.dc_stocks_csv),
            supplier_shipments_csv=supplier_shipments_csv,
            safety_reference_csv=Path(args.safety_reference_csv) if args.safety_reference_csv else None,
        )
        payload["material_balance_rows"] = material_table_rows
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
        render_global_model_equations_html(),
    )
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
