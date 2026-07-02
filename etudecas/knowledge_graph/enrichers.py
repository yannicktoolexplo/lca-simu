from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .excel_io import read_xlsx
from .excel_template import LOGISTICS_EXCEL_TO_JSON_KEYS
from .io import append_provenance
from .schema import ensure_graph_shape, normalize_item_id, validate_graph_contract


MATERIALIZED_CASE_CONFIG_SECTIONS = {"logistics_assumptions"}


def enrich_graph_from_excel(graph: dict[str, Any], excel_path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = ensure_graph_shape(graph)
    workbook = read_xlsx(excel_path)
    report = {"workbook": str(excel_path), "applied": {}, "issues": []}

    _apply_items(graph, workbook.get("items") or [], report)
    _apply_nodes(graph, workbook.get("nodes") or [], report)
    _apply_edges(graph, workbook.get("edges") or [], report)
    _apply_bom(graph, workbook.get("bom") or [], report)
    _apply_inventory(graph, workbook.get("initial_inventory") or [], report)
    _apply_demand(graph, workbook.get("demand") or [], report)
    _apply_risks(graph, workbook.get("risks") or [], report)
    _apply_logistics(graph, workbook.get("logistics") or [], report)
    _apply_case_config(graph, workbook.get("case_config") or [], report)

    issues = validate_graph_contract(graph)
    report["issues"].extend(issues)
    append_provenance(graph, step="excel_enrichment", source=str(excel_path), details=report["applied"])
    return graph, report


def _apply_items(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    if not rows:
        return
    existing = _items_as_dict(graph)
    count = 0
    for row in rows:
        item_id = normalize_item_id(row.get("item_id"))
        if not item_id:
            continue
        item = existing.setdefault(item_id, {"id": item_id})
        _set_if_present(item, "name", row.get("name"))
        _set_if_present(item, "family", row.get("family"))
        _set_if_present(item, "uom", row.get("uom"))
        _set_if_present(item, "unit_value", _num(row.get("unit_value")))
        _set_if_present(item, "description", row.get("description"))
        count += 1
    graph["items"] = list(existing.values())
    report["applied"]["items"] = count


def _apply_nodes(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    nodes = {str(node.get("id")): node for node in graph.get("nodes") or [] if node.get("id")}
    count = 0
    for row in rows:
        if _is_false(row.get("active")):
            continue
        node_id = str(row.get("id") or "").strip()
        if not node_id:
            continue
        node = nodes.setdefault(node_id, {"id": node_id})
        _set_if_present(node, "type", row.get("type"))
        _set_if_present(node, "name", row.get("name"))
        _set_if_present(node, "location_ID", row.get("location_ID"))
        lat = _num(row.get("lat"))
        lon = _num(row.get("lon"))
        if lat is not None or lon is not None:
            geo = node.setdefault("geo", {})
            if lat is not None:
                geo["lat"] = lat
            if lon is not None:
                geo["lon"] = lon
        _set_if_present(node, "country", row.get("country"))
        count += 1
    graph["nodes"] = list(nodes.values())
    report["applied"]["nodes"] = count


def _apply_edges(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    edges = {str(edge.get("id") or _edge_key(edge)): edge for edge in graph.get("edges") or []}
    count = 0
    for row in rows:
        src = str(row.get("from") or "").strip()
        dst = str(row.get("to") or "").strip()
        if not src or not dst:
            continue
        item_ids = [normalize_item_id(part) for part in str(row.get("item_ids") or "").replace(",", ";").split(";")]
        item_ids = [item for item in item_ids if item]
        edge_id = str(row.get("id") or "").strip() or f"edge:{src}_TO_{dst}_{'_'.join(item_ids) or 'items'}"
        edge = edges.setdefault(edge_id, {"id": edge_id})
        edge["from"] = src
        edge["to"] = dst
        edge["items"] = item_ids
        _set_if_present(edge, "type", row.get("type"))
        _set_if_present(edge, "mode", row.get("mode"))
        _set_if_present(edge, "distance_km", _num(row.get("distance_km")))
        _set_if_present(edge, "service_level", _num(row.get("service_level")))
        lead_time = _num(row.get("lead_time_days"))
        if lead_time is not None:
            _update_lead_time(edge, lead_time)
        order_terms = edge.setdefault("order_terms", {})
        for target, source in [
            ("quantity_unit", "quantity_unit"),
            ("min_order_qty", "min_order_qty"),
            ("standard_order_qty", "standard_order_qty"),
            ("lot_multiple_qty", "lot_multiple_qty"),
            ("sell_price", "sell_price"),
            ("price_base", "price_base"),
        ]:
            value = row.get(source)
            value = _num(value) if target != "quantity_unit" else value
            _set_if_present(order_terms, target, value)
        count += 1
    graph["edges"] = list(edges.values())
    report["applied"]["edges"] = count


def _apply_bom(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    nodes = {str(node.get("id")): node for node in graph.get("nodes") or [] if node.get("id")}
    count = 0
    for row in rows:
        node_id = str(row.get("node_id") or "").strip()
        output_item = normalize_item_id(row.get("output_item_id"))
        input_item = normalize_item_id(row.get("input_item_id"))
        if not node_id or not output_item or not input_item:
            continue
        node = nodes.setdefault(node_id, {"id": node_id, "type": "factory"})
        process_id = str(row.get("process_id") or "").strip() or f"proc:MAKE_{output_item.replace('item:', '')}"
        process = _find_process(node, process_id, output_item)
        process["id"] = process_id
        process["type"] = "transform"
        _set_if_present(process, "batch_size", _num(row.get("batch_size")))
        _set_if_present(process, "batch_size_unit", row.get("batch_size_unit"))
        _ensure_process_output(process, output_item)
        inputs = process.setdefault("inputs", [])
        component = next((item for item in inputs if item.get("item_id") == input_item), None)
        if component is None:
            component = {"item_id": input_item}
            inputs.append(component)
        _set_if_present(component, "ratio_per_batch", _num(row.get("ratio_per_batch")))
        _set_if_present(component, "ratio_unit", row.get("ratio_unit"))
        capacity_rate = _num(row.get("capacity_max_rate"))
        if capacity_rate is not None:
            capacity = process.setdefault("capacity", {})
            capacity["max_rate"] = capacity_rate
            _set_if_present(capacity, "uom", row.get("capacity_uom"))
            capacity["source"] = "excel_enrichment"
        wip_days = _num(row.get("wip_days"))
        if wip_days is not None:
            wip = process.setdefault("wip", {})
            wip["tau_process"] = wip_days
            wip.setdefault("time_unit", "day")
            wip["source"] = "excel_enrichment"
        lot_values = {
            "fixed_lot_qty": _num(row.get("fixed_lot_qty")),
            "min_lot_qty": _num(row.get("min_lot_qty")),
            "max_lot_qty": _num(row.get("max_lot_qty")),
        }
        if any(value is not None for value in lot_values.values()):
            lot_sizing = process.setdefault("lot_sizing", {})
            for key, value in lot_values.items():
                if value is not None:
                    lot_sizing[key] = value
            lot_sizing["source"] = "excel_enrichment"
        max_lots = _num(row.get("max_lots_per_week"))
        if max_lots is not None:
            process.setdefault("lot_execution", {})["max_lots_per_week"] = max_lots
        count += 1
    graph["nodes"] = list(nodes.values())
    report["applied"]["bom_rows"] = count


def _apply_inventory(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    nodes = {str(node.get("id")): node for node in graph.get("nodes") or [] if node.get("id")}
    count = 0
    for row in rows:
        node_id = str(row.get("node_id") or "").strip()
        item_id = normalize_item_id(row.get("item_id"))
        quantity = _num(row.get("quantity"))
        if not node_id or not item_id or quantity is None:
            continue
        node = nodes.setdefault(node_id, {"id": node_id})
        inventory = node.setdefault("inventory", {})
        stock_type = str(row.get("stock_type") or "initial_stock").strip()
        stocks = inventory.setdefault(stock_type, [])
        existing = next((stock for stock in stocks if stock.get("item_id") == item_id), None)
        if existing is None:
            existing = {"item_id": item_id}
            stocks.append(existing)
        existing["initial"] = quantity
        existing["quantity"] = quantity
        existing["source"] = "excel_enrichment"
        _set_if_present(existing, "uom", row.get("uom"))
        count += 1
    graph["nodes"] = list(nodes.values())
    report["applied"]["initial_inventory"] = count


def _apply_demand(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    if not rows:
        return
    scenarios = {str(row.get("id")): row for row in graph.get("scenarios") or [] if row.get("id")}
    count = 0
    for row in rows:
        scenario_id = str(row.get("scenario_id") or "baseline").strip()
        customer_id = str(row.get("customer_id") or "").strip()
        item_id = normalize_item_id(row.get("item_id"))
        day = _num(row.get("day"))
        quantity = _num(row.get("quantity"))
        if not customer_id or not item_id or day is None or quantity is None:
            continue
        scenario = scenarios.setdefault(scenario_id, {"id": scenario_id})
        demand = scenario.get("demand")
        if not isinstance(demand, dict):
            if demand:
                scenario.setdefault("demand_profile_original", demand)
            demand = {}
            scenario["demand"] = demand
        daily = demand.setdefault("daily", [])
        entry = {
            "customer_id": customer_id,
            "item_id": item_id,
            "day": int(day),
            "quantity": quantity,
            "uom": row.get("uom") or "UN",
        }
        _upsert_demand_row(daily, entry)
        count += 1
    graph["scenarios"] = list(scenarios.values())
    report["applied"]["demand"] = count


def _apply_risks(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    risks = []
    for row in rows:
        if _is_false(row.get("active")):
            continue
        if not row.get("node_id") and not row.get("risk_family"):
            continue
        risk = {key: value for key, value in row.items() if value not in ("", None)}
        if risk.get("item_id"):
            risk["item_id"] = normalize_item_id(risk["item_id"])
        risks.append(risk)
    if risks:
        graph["risks"] = risks
        report["applied"]["risks"] = len(risks)


def _apply_logistics(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    config = graph.setdefault("case_config", {})
    assumptions = config.setdefault("logistics_assumptions", {})
    count = 0
    for row in rows:
        item_id = normalize_item_id(row.get("item_id"))
        if not item_id:
            continue
        policy = assumptions.setdefault(item_id, {})
        applied = False
        for excel_key, json_key in LOGISTICS_EXCEL_TO_JSON_KEYS.items():
            value = row.get(excel_key)
            if value in ("", None):
                continue
            numeric = _num(value)
            policy[json_key] = numeric if numeric is not None else value
            applied = True
        if applied:
            count += 1
    if count:
        report["applied"]["logistics"] = count


def _apply_case_config(graph: dict[str, Any], rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    config = graph.setdefault("case_config", {})
    count = 0
    for row in rows:
        section = str(row.get("section") or "").strip()
        key = str(row.get("key") or "").strip()
        if not section or not key:
            continue
        if section in MATERIALIZED_CASE_CONFIG_SECTIONS:
            continue
        value = _parse_json(row.get("value_json"))
        target = config if section == "root" else config.setdefault(section, {})
        if isinstance(target, dict):
            target[key] = value
            count += 1
    if count:
        report["applied"]["case_config"] = count


def _find_process(node: dict[str, Any], process_id: str, output_item: str) -> dict[str, Any]:
    processes = node.setdefault("processes", [])
    for process in processes:
        if process.get("id") == process_id:
            return process
        if any(row.get("item_id") == output_item for row in process.get("outputs") or []):
            return process
    process: dict[str, Any] = {"id": process_id}
    processes.append(process)
    return process


def _ensure_process_output(process: dict[str, Any], output_item: str) -> None:
    outputs = process.setdefault("outputs", [])
    if not isinstance(outputs, list):
        process["outputs"] = []
        outputs = process["outputs"]
    if any(row.get("item_id") == output_item for row in outputs if isinstance(row, dict)):
        return
    outputs.append({"item_id": output_item})


def _update_lead_time(edge: dict[str, Any], lead_time_days: float) -> None:
    lead_time = edge.get("lead_time")
    if not isinstance(lead_time, dict):
        edge["lead_time"] = {"value": lead_time_days, "time_unit": "day", "source": "excel_enrichment"}
        return
    if "mean" in lead_time:
        lead_time["mean"] = lead_time_days
    else:
        lead_time["value"] = lead_time_days
    lead_time.setdefault("time_unit", "day")
    lead_time["source"] = "excel_enrichment"


def _upsert_demand_row(rows: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    key = _demand_key(entry)
    for idx, row in enumerate(rows):
        if _demand_key(row) == key:
            merged = dict(row)
            merged.update(entry)
            rows[idx] = merged
            return
    rows.append(entry)


def _demand_key(row: dict[str, Any]) -> tuple[str, str, int | None]:
    day = _num(row.get("day"))
    return (
        str(row.get("customer_id") or row.get("node_id") or "").strip(),
        normalize_item_id(row.get("item_id")),
        int(day) if day is not None else None,
    )


def _items_as_dict(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = graph.get("items") or []
    if isinstance(items, dict):
        return {str(item_id): dict(value) for item_id, value in items.items() if isinstance(value, dict)}
    return {
        str(row.get("id") or row.get("item_id")): dict(row)
        for row in items
        if isinstance(row, dict) and (row.get("id") or row.get("item_id"))
    }


def _edge_key(edge: dict[str, Any]) -> str:
    return f"{edge.get('from')}->{edge.get('to')}:{';'.join(str(item) for item in edge.get('items') or [])}"


def _set_if_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value not in ("", None):
        target[key] = value


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_false(value: Any) -> bool:
    return str(value).strip().lower() in {"false", "0", "no", "non", "n"}


def _parse_json(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
