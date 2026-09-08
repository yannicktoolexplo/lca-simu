from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from etudecas.case_config import (
    display_node_id as case_display_node_id,
    is_upstream_internal_site as case_is_upstream_internal_site,
    standard_order_override,
)


NODE_TYPE_STYLES = {
    "supplier_dc": {"name": "Supplier DC", "color": "#1f77b4", "symbol": "circle"},
    "factory": {"name": "Factory", "color": "#d62728", "symbol": "square"},
    "distribution_center": {"name": "Distribution Center", "color": "#ff7f0e", "symbol": "diamond"},
    "customer": {"name": "Customer", "color": "#2ca02c", "symbol": "star"},
}

PILOTAGE_HIDDEN_NODE_IDS = {"M-1450"}
SIMULATION_HIDDEN_ITEM_IDS: set[str] = set()

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


GENERIC_PAYLOAD_KEYS = {
    "nodes",
    "edges",
    "time_series",
    "events",
    "lots",
    "diagnostics",
}


def _to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def is_pilotage_hidden_node(node_id: str) -> bool:
    return bool(node_id) and node_id in PILOTAGE_HIDDEN_NODE_IDS


def is_pilotage_hidden_edge(src: str, dst: str) -> bool:
    return is_pilotage_hidden_node(src) or is_pilotage_hidden_node(dst)


def is_upstream_internal_site(node_id: str) -> bool:
    return case_is_upstream_internal_site(node_id)


def display_node_label(node_id: str) -> str:
    return case_display_node_id(node_id)


def is_simulation_hidden_item(item_id: str) -> bool:
    return bool(item_id) and item_id in SIMULATION_HIDDEN_ITEM_IDS


def standard_order_override_for_edge(edge: dict[str, Any]) -> dict[str, Any] | None:
    src = str(edge.get("from") or "")
    dst = str(edge.get("to") or "")
    for item_id in edge.get("items") or []:
        override = standard_order_override(src, dst, item_id)
        if override:
            return override
    return None


def display_standard_order_qty(edge: dict[str, Any]) -> float:
    override = standard_order_override_for_edge(edge)
    if override:
        return max(0.0, float(override["qty"]))
    return max(0.0, _to_float(((edge.get("attrs") or {}).get("standard_order_qty")) or 0.0) or 0.0)


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
                "planned_lead_days": max(1.0, _to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0),
                "distance_km": max(0.0, _to_float(edge.get("distance_km")) or 0.0),
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
        fourth = primary_payload.get("fourth") or fallback_payload.get("fourth")
        compare = primary_payload.get("compare") or fallback_payload.get("compare")
        if incoming or outgoing or third or fourth or compare:
            merged[node_id] = {
                "incoming": incoming,
                "outgoing": outgoing,
                "third": third,
                "fourth": fourth,
                "compare": compare,
            }
    return merged


@dataclass(frozen=True)
class PayloadSection:
    """Named business payload section consumed by the map shell."""

    key: str
    value: Any


def payload_section(key: str, value: Any) -> PayloadSection:
    if not key or not isinstance(key, str):
        raise ValueError("Payload section key must be a non-empty string.")
    return PayloadSection(key=key, value=value)


def merge_payload_sections(
    base_payload: dict[str, Any],
    sections: Iterable[PayloadSection],
) -> dict[str, Any]:
    """Return a payload copy with named sections applied in order."""

    payload = dict(base_payload)
    for section in sections:
        payload[section.key] = section.value
    return payload


def build_payload_layers_manifest(manifests: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a lightweight domain manifest for the map payload."""

    domains: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        domain = str(manifest.get("domain") or "")
        if not domain:
            raise ValueError("Payload layer manifest is missing a domain.")
        domains[domain] = manifest
    return {
        "version": 1,
        "domains": domains,
    }


def build_generic_payload_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """Expose a stable lightweight generic view for future renderers/APIs.

    Existing maps still consume the rich legacy top-level sections.  The generic
    contract must not duplicate those heavy structures; it exposes references,
    counts and the run package metadata so future viewers can migrate without
    making autonomous HTML files much larger.
    """

    lot_trace = payload.get("lot_trace", {}) or {}
    run_contract = payload.get("run_contract", {}) or {}
    artifacts = run_contract.get("artifacts") if isinstance(run_contract, dict) else []
    if not isinstance(artifacts, list):
        artifacts = []
    return {
        "schema_version": "etudecas.map_viewer_payload.v1",
        "nodes": payload.get("nodes", []) or [],
        "edges": payload.get("edges", []) or [],
        "run_contract": run_contract,
        "artifact_domains": sorted(
            {
                str(row.get("domain"))
                for row in artifacts
                if isinstance(row, dict) and str(row.get("domain") or "")
            }
        ),
        "counts": {
            "nodes": len(payload.get("nodes", []) or []),
            "edges": len(payload.get("edges", []) or []),
            "lot_events": len(lot_trace.get("events", []) or []),
            "lot_nodes": len(lot_trace.get("lots", {}) or {}),
            "simulation_diagnostics_sections": len(payload.get("simulation_diagnostics", {}) or {}),
            "scenario_comparison_figures": len((payload.get("scenario_comparison", {}) or {}).get("figures", {}) or {}),
        },
    }


def attach_generic_payload_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a payload copy with the generic contract under `generic`."""

    out = dict(payload)
    out["generic"] = build_generic_payload_contract(payload)
    return out
