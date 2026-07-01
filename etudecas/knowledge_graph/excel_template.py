from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .excel_io import write_xlsx


EXCEL_COLUMNS: dict[str, list[str]] = {
    "README": ["section", "field", "description"],
    "nodes": ["id", "type", "name", "location_ID", "lat", "lon", "country", "active", "notes"],
    "items": ["item_id", "name", "family", "uom", "unit_value", "description"],
    "edges": [
        "id",
        "type",
        "from",
        "to",
        "item_ids",
        "mode",
        "lead_time_days",
        "distance_km",
        "quantity_unit",
        "min_order_qty",
        "standard_order_qty",
        "lot_multiple_qty",
        "sell_price",
        "price_base",
        "service_level",
    ],
    "bom": [
        "node_id",
        "process_id",
        "output_item_id",
        "batch_size",
        "batch_size_unit",
        "input_item_id",
        "ratio_per_batch",
        "ratio_unit",
        "capacity_max_rate",
        "capacity_uom",
        "wip_days",
        "fixed_lot_qty",
        "min_lot_qty",
        "max_lot_qty",
        "max_lots_per_week",
    ],
    "initial_inventory": ["node_id", "item_id", "quantity", "uom", "stock_type", "notes"],
    "demand": ["scenario_id", "customer_id", "item_id", "day", "quantity", "uom", "notes"],
    "risks": [
        "node_id",
        "item_id",
        "risk_family",
        "severity",
        "probability",
        "lead_time_delta_days",
        "capacity_scale",
        "stock_scale",
        "active",
        "notes",
    ],
    "logistics": [
        "item_id",
        "unit_label",
        "units_per_case",
        "central_cases_per_pallet",
        "min_cases_per_pallet",
        "max_cases_per_pallet",
        "truck_pallet_slots",
        "pallet_envelope_m3",
        "identifiable_mass_kg_per_unit",
    ],
    "case_config": ["section", "key", "value_json", "notes"],
}


LOGISTICS_EXCEL_TO_JSON_KEYS = {
    "unit_label": "unitLabel",
    "units_per_case": "unitsPerCase",
    "central_cases_per_pallet": "centralCasesPerPallet",
    "min_cases_per_pallet": "minCasesPerPallet",
    "max_cases_per_pallet": "maxCasesPerPallet",
    "truck_pallet_slots": "truckPalletSlots",
    "pallet_envelope_m3": "palletEnvelopeM3",
    "identifiable_mass_kg_per_unit": "identifiableMassKgPerUnit",
}

MATERIALIZED_CASE_CONFIG_SECTIONS = {"logistics_assumptions"}


README_ROWS = [
    {
        "section": "principle",
        "field": "json_contract",
        "description": "This workbook enriches a supply graph JSON. Empty cells do not erase existing data.",
    },
    {
        "section": "nodes",
        "field": "id/type/name/location",
        "description": "Defines supply-chain actors: supplier_dc, factory, distribution_center, customer.",
    },
    {
        "section": "edges",
        "field": "item_ids",
        "description": "Use item ids separated by semicolons. Example: item:268967;item:268091.",
    },
    {
        "section": "bom",
        "field": "ratio_per_batch",
        "description": "Component quantity consumed for one process batch_size.",
    },
    {
        "section": "case_config",
        "field": "value_json",
        "description": "JSON value merged under graph.case_config[section][key].",
    },
]


def build_excel_template_rows(graph: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    graph = graph or {}
    rows: dict[str, list[dict[str, Any]]] = {sheet: [] for sheet in EXCEL_COLUMNS}
    rows["README"] = README_ROWS
    rows["nodes"] = _node_rows(graph)
    rows["items"] = _item_rows(graph)
    rows["edges"] = _edge_rows(graph)
    rows["bom"] = _bom_rows(graph)
    rows["initial_inventory"] = _inventory_rows(graph)
    rows["demand"] = _demand_rows(graph)
    rows["risks"] = _risk_rows(graph)
    rows["logistics"] = _logistics_rows(graph)
    rows["case_config"] = _case_config_rows(graph)
    return rows


def write_excel_template(path: str | Path, graph: dict[str, Any] | None = None) -> None:
    write_xlsx(path, build_excel_template_rows(graph), EXCEL_COLUMNS)


def _node_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for node in graph.get("nodes") or []:
        geo = node.get("geo") or {}
        out.append(
            {
                "id": node.get("id", ""),
                "type": node.get("type", ""),
                "name": node.get("name", ""),
                "location_ID": node.get("location_ID", ""),
                "lat": geo.get("lat", ""),
                "lon": geo.get("lon", ""),
                "country": node.get("country", "") or geo.get("country", ""),
                "active": True,
                "notes": "",
            }
        )
    return out


def _item_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    items = graph.get("items")
    if isinstance(items, dict):
        iterator = items.items()
    else:
        iterator = [(row.get("id") or row.get("item_id"), row) for row in (items or []) if isinstance(row, dict)]
    for item_id, item in iterator:
        out.append(
            {
                "item_id": item_id or item.get("item_id", ""),
                "name": item.get("name", ""),
                "family": item.get("family", ""),
                "uom": item.get("uom", ""),
                "unit_value": item.get("unit_value", ""),
                "description": item.get("description", ""),
            }
        )
    return out


def _edge_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for edge in graph.get("edges") or []:
        terms = edge.get("order_terms") or {}
        out.append(
            {
                "id": edge.get("id", ""),
                "type": edge.get("type", ""),
                "from": edge.get("from", ""),
                "to": edge.get("to", ""),
                "item_ids": ";".join(str(item) for item in edge.get("items") or []),
                "mode": edge.get("mode", ""),
                "lead_time_days": _first_nested(edge, [("lead_time", "value"), ("lead_time", "mean")]),
                "distance_km": edge.get("distance_km", ""),
                "quantity_unit": terms.get("quantity_unit", ""),
                "min_order_qty": terms.get("min_order_qty", ""),
                "standard_order_qty": terms.get("standard_order_qty", ""),
                "lot_multiple_qty": terms.get("lot_multiple_qty", ""),
                "sell_price": terms.get("sell_price", ""),
                "price_base": terms.get("price_base", ""),
                "service_level": edge.get("service_level", ""),
            }
        )
    return out


def _bom_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for node in graph.get("nodes") or []:
        node_id = node.get("id", "")
        for process in node.get("processes") or []:
            output_items = process.get("outputs") or []
            output_item_id = output_items[0].get("item_id", "") if output_items else ""
            for component in process.get("inputs") or []:
                out.append(
                    {
                        "node_id": node_id,
                        "process_id": process.get("id", ""),
                        "output_item_id": output_item_id,
                        "batch_size": process.get("batch_size", ""),
                        "batch_size_unit": process.get("batch_size_unit", ""),
                        "input_item_id": component.get("item_id", ""),
                        "ratio_per_batch": component.get("ratio_per_batch", ""),
                        "ratio_unit": component.get("ratio_unit", ""),
                        "capacity_max_rate": _nested(process, "capacity", "max_rate"),
                        "capacity_uom": _nested(process, "capacity", "uom"),
                        "wip_days": _nested(process, "wip", "tau_process"),
                        "fixed_lot_qty": _nested(process, "lot_sizing", "fixed_lot_qty"),
                        "min_lot_qty": _nested(process, "lot_sizing", "min_lot_qty"),
                        "max_lot_qty": _nested(process, "lot_sizing", "max_lot_qty"),
                        "max_lots_per_week": _nested(process, "lot_execution", "max_lots_per_week"),
                    }
                )
    return out


def _inventory_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for node in graph.get("nodes") or []:
        node_id = node.get("id", "")
        inv = node.get("inventory") or {}
        for stock_type, rows in inv.items():
            if isinstance(rows, list):
                for row in rows:
                    out.append(
                        {
                            "node_id": node_id,
                            "item_id": row.get("item_id", ""),
                            "quantity": row.get("initial", row.get("quantity", "")),
                            "uom": row.get("uom", ""),
                            "stock_type": stock_type,
                            "notes": "",
                        }
                    )
    return out


def _demand_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for scenario in graph.get("scenarios") or []:
        scenario_id = scenario.get("id", "")
        demand = scenario.get("demand") or {}
        if isinstance(demand, dict):
            for row in demand.get("daily") or []:
                out.append(
                    {
                        "scenario_id": scenario_id,
                        "customer_id": row.get("customer_id", ""),
                        "item_id": row.get("item_id", ""),
                        "day": row.get("day", ""),
                        "quantity": row.get("quantity", ""),
                        "uom": row.get("uom", ""),
                        "notes": "",
                    }
                )
        elif isinstance(demand, list):
            for row in demand:
                customer_id = row.get("node_id", "")
                item_id = row.get("item_id", "")
                for profile in row.get("profile") or []:
                    for point in profile.get("points") or []:
                        out.append(
                            {
                                "scenario_id": scenario_id,
                                "customer_id": customer_id,
                                "item_id": item_id,
                                "day": point.get("t", ""),
                                "quantity": point.get("value", ""),
                                "uom": profile.get("uom", ""),
                                "notes": "piecewise_profile_point",
                            }
                        )
    return out


def _risk_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    risks = graph.get("risks") or graph.get("risk_events") or []
    return [dict(row) for row in risks if isinstance(row, dict)]


def _logistics_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = graph.get("case_config") or graph.get("lot_trace_config") or {}
    logistics = cfg.get("logistics_assumptions") if isinstance(cfg, dict) else {}
    if not isinstance(logistics, dict):
        return []
    out = []
    for item_id, policy in logistics.items():
        if isinstance(policy, dict):
            row = {"item_id": item_id}
            for excel_key, json_key in LOGISTICS_EXCEL_TO_JSON_KEYS.items():
                row[excel_key] = policy.get(excel_key, policy.get(json_key, ""))
            out.append(row)
    return out


def _case_config_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    config = graph.get("case_config") or graph.get("lot_trace_config") or {}
    out = []
    if isinstance(config, dict):
        for section, value in config.items():
            if section in MATERIALIZED_CASE_CONFIG_SECTIONS:
                continue
            if isinstance(value, dict):
                for key, child in value.items():
                    out.append({"section": section, "key": key, "value_json": json.dumps(child, ensure_ascii=False), "notes": ""})
            else:
                out.append({"section": "root", "key": section, "value_json": json.dumps(value, ensure_ascii=False), "notes": ""})
    return out


def _nested(row: dict[str, Any], *keys: str) -> Any:
    cur: Any = row
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return "" if cur is None else cur


def _first_nested(row: dict[str, Any], paths: list[tuple[str, ...]]) -> Any:
    for path in paths:
        value = _nested(row, *path)
        if value != "":
            return value
    return ""
