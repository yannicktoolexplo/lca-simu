from __future__ import annotations

from typing import Any


GRAPH_SCHEMA_VERSION = "etudecas.supply_graph.v1"
NODE_TYPES = {"supplier_dc", "factory", "distribution_center", "customer"}
EDGE_TYPES = {"transport", "supply", "distribution"}


def normalize_item_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("item:") else f"item:{text}"


def ensure_graph_shape(graph: dict[str, Any]) -> dict[str, Any]:
    graph.setdefault("schema_version", GRAPH_SCHEMA_VERSION)
    graph.setdefault("meta", {})
    graph.setdefault("items", [])
    graph.setdefault("nodes", [])
    graph.setdefault("edges", [])
    graph.setdefault("scenarios", [])
    return graph


def validate_graph_contract(graph: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(graph, dict):
        return [{"level": "error", "field": "root", "message": "graph must be a JSON object"}]

    for key in ["items", "nodes", "edges", "scenarios"]:
        if not isinstance(graph.get(key), list):
            issues.append({"level": "error", "field": key, "message": f"{key} must be a list"})

    item_ids: set[str] = set()
    for idx, item in enumerate(graph.get("items") or []):
        item_id = str((item or {}).get("id") or (item or {}).get("item_id") or "").strip()
        if not item_id:
            issues.append({"level": "error", "field": f"items[{idx}].id", "message": "missing item id"})
            continue
        if item_id in item_ids:
            issues.append({"level": "error", "field": f"items[{idx}].id", "message": f"duplicate item id {item_id}"})
        item_ids.add(item_id)

    node_ids: set[str] = set()
    for idx, node in enumerate(graph.get("nodes") or []):
        node_id = str((node or {}).get("id") or "").strip()
        if not node_id:
            issues.append({"level": "error", "field": f"nodes[{idx}].id", "message": "missing node id"})
            continue
        if node_id in node_ids:
            issues.append({"level": "error", "field": f"nodes[{idx}].id", "message": f"duplicate node id {node_id}"})
        node_ids.add(node_id)
        node_type = str((node or {}).get("type") or "").strip()
        if node_type and node_type not in NODE_TYPES:
            issues.append({"level": "warning", "field": f"nodes[{idx}].type", "message": f"unusual node type {node_type}"})
        inventory = (node or {}).get("inventory") or {}
        if inventory and not isinstance(inventory, dict):
            issues.append({"level": "error", "field": f"nodes[{idx}].inventory", "message": "inventory must be a mapping"})
        elif isinstance(inventory, dict):
            for stock_type, rows in inventory.items():
                if not isinstance(rows, list):
                    issues.append({"level": "error", "field": f"nodes[{idx}].inventory.{stock_type}", "message": "inventory bucket must be a list"})
                    continue
                for sidx, row in enumerate(rows):
                    item_id = normalize_item_id((row or {}).get("item_id"))
                    if not item_id:
                        issues.append({"level": "error", "field": f"nodes[{idx}].inventory.{stock_type}[{sidx}].item_id", "message": "missing inventory item id"})
                    if "initial" in (row or {}) and not _is_number((row or {}).get("initial")):
                        issues.append({"level": "error", "field": f"nodes[{idx}].inventory.{stock_type}[{sidx}].initial", "message": "initial inventory must be numeric"})
        processes = (node or {}).get("processes") or []
        if processes and not isinstance(processes, list):
            issues.append({"level": "error", "field": f"nodes[{idx}].processes", "message": "processes must be a list"})
        elif isinstance(processes, list):
            for pidx, process in enumerate(processes):
                outputs = (process or {}).get("outputs") or []
                inputs = (process or {}).get("inputs") or []
                if not isinstance(outputs, list):
                    issues.append({"level": "error", "field": f"nodes[{idx}].processes[{pidx}].outputs", "message": "outputs must be a list"})
                elif not any(normalize_item_id((row or {}).get("item_id")) for row in outputs):
                    issues.append({"level": "error", "field": f"nodes[{idx}].processes[{pidx}].outputs", "message": "process must expose at least one output item"})
                if not isinstance(inputs, list):
                    issues.append({"level": "error", "field": f"nodes[{idx}].processes[{pidx}].inputs", "message": "inputs must be a list"})
                for iidx, row in enumerate(inputs if isinstance(inputs, list) else []):
                    if not normalize_item_id((row or {}).get("item_id")):
                        issues.append({"level": "error", "field": f"nodes[{idx}].processes[{pidx}].inputs[{iidx}].item_id", "message": "missing process input item id"})
                    if "ratio_per_batch" in (row or {}) and not _is_number((row or {}).get("ratio_per_batch")):
                        issues.append({"level": "error", "field": f"nodes[{idx}].processes[{pidx}].inputs[{iidx}].ratio_per_batch", "message": "ratio_per_batch must be numeric"})

    edge_ids: set[str] = set()
    for idx, edge in enumerate(graph.get("edges") or []):
        edge_id = str((edge or {}).get("id") or "").strip()
        if edge_id:
            if edge_id in edge_ids:
                issues.append({"level": "error", "field": f"edges[{idx}].id", "message": f"duplicate edge id {edge_id}"})
            edge_ids.add(edge_id)
        src = str((edge or {}).get("from") or "").strip()
        dst = str((edge or {}).get("to") or "").strip()
        if src and src not in node_ids:
            issues.append({"level": "error", "field": f"edges[{idx}].from", "message": f"unknown source node {src}"})
        if dst and dst not in node_ids:
            issues.append({"level": "error", "field": f"edges[{idx}].to", "message": f"unknown destination node {dst}"})
        edge_type = str((edge or {}).get("type") or "").strip()
        if edge_type and edge_type not in EDGE_TYPES:
            issues.append({"level": "warning", "field": f"edges[{idx}].type", "message": f"unusual edge type {edge_type}"})
        items = (edge or {}).get("items") or []
        if not isinstance(items, list):
            issues.append({"level": "error", "field": f"edges[{idx}].items", "message": "edge items must be a list"})
        elif not items:
            issues.append({"level": "warning", "field": f"edges[{idx}].items", "message": "edge has no item scope"})

    for idx, scenario in enumerate(graph.get("scenarios") or []):
        if not str((scenario or {}).get("id") or "").strip():
            issues.append({"level": "error", "field": f"scenarios[{idx}].id", "message": "missing scenario id"})
        demand = (scenario or {}).get("demand")
        if demand is None:
            continue
        if isinstance(demand, dict):
            daily = demand.get("daily")
            if daily is None:
                continue
            if not isinstance(daily, list):
                issues.append({"level": "error", "field": f"scenarios[{idx}].demand.daily", "message": "daily demand must be a list"})
                continue
            for didx, row in enumerate(daily):
                if not str((row or {}).get("customer_id") or (row or {}).get("node_id") or "").strip():
                    issues.append({"level": "error", "field": f"scenarios[{idx}].demand.daily[{didx}].customer_id", "message": "missing demand customer id"})
                if not normalize_item_id((row or {}).get("item_id")):
                    issues.append({"level": "error", "field": f"scenarios[{idx}].demand.daily[{didx}].item_id", "message": "missing demand item id"})
                if not _is_number((row or {}).get("day")):
                    issues.append({"level": "error", "field": f"scenarios[{idx}].demand.daily[{didx}].day", "message": "demand day must be numeric"})
                if not _is_number((row or {}).get("quantity")):
                    issues.append({"level": "error", "field": f"scenarios[{idx}].demand.daily[{didx}].quantity", "message": "demand quantity must be numeric"})
        elif not isinstance(demand, list):
            issues.append({"level": "error", "field": f"scenarios[{idx}].demand", "message": "demand must be a list or a mapping"})

    return issues


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
