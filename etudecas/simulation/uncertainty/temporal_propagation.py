"""Temporal interpretation of controlled supplier uncertainty experiments."""

from __future__ import annotations

import csv
import math
from collections import deque
from pathlib import Path
from typing import Any

from etudecas.simulation.uncertainty.paired_propagation import factor_pair_scope


SCHEMA_VERSION = "etudecas.temporal-uncertainty-propagation.v1"

METRIC_STAGES = {
    "supplier_capacity_binding": "supplier",
    "production_delay_active_orders": "factory",
    "production_delay_active_qty": "factory",
    "production_delay_input_qty": "factory",
    "production_delay_capacity_qty": "factory",
    "production_reports": "factory",
    "produced_qty": "factory",
    "backlog": "customer",
    "service_rate": "customer",
    "total_supply_cost_cum": "economic",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _timing(days: list[int], row: dict[str, Any]) -> dict[str, Any]:
    center = [_number(value) for value in row.get("center") or []]
    low = [_number(value) for value in row.get("low") or []]
    high = [_number(value) for value in row.get("high") or []]
    length = min(len(days), len(center), len(low), len(high))
    if length <= 0:
        return {"observable": False}
    effects = [
        max(abs(low[index] - center[index]), abs(high[index] - center[index]))
        for index in range(length)
    ]
    peak = max(effects, default=0.0)
    if peak <= 1e-9:
        return {"observable": False, "peak_effect": 0.0}
    threshold = max(1e-9, peak * 0.02)
    active = [index for index, value in enumerate(effects) if value > threshold]
    if not active:
        return {"observable": False, "peak_effect": peak}
    peak_index = max(range(length), key=effects.__getitem__)
    recovery_day: int | None = None
    for index in range(peak_index + 1, max(peak_index + 1, length - 2)):
        if max(effects[index : index + 3], default=peak) <= threshold:
            recovery_day = int(days[index])
            break
    return {
        "observable": True,
        "first_effect_day": int(days[active[0]]),
        "peak_effect_day": int(days[peak_index]),
        "last_effect_day": int(days[active[-1]]),
        "recovery_day": recovery_day,
        "duration_days": int(days[active[-1]] - days[active[0]] + 1),
        "peak_effect": peak,
        "cumulative_absolute_effect": sum(effects),
        "detection_threshold": threshold,
    }


def _node_map(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(node.get("id") or ""): node
        for node in graph.get("nodes") or []
        if str(node.get("id") or "")
    }


def _network_path(
    graph: dict[str, Any],
    supplier_id: str,
    destination_id: str,
) -> dict[str, Any]:
    nodes = _node_map(graph)
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in graph.get("edges") or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if src and dst:
            adjacency.setdefault(src, []).append((dst, str(edge.get("id") or "")))
    start_path = [supplier_id]
    start_edges: list[str] = []
    if destination_id and destination_id != supplier_id:
        direct = next(
            (
                edge_id
                for dst, edge_id in adjacency.get(supplier_id, [])
                if dst == destination_id
            ),
            "",
        )
        if direct:
            start_path.append(destination_id)
            start_edges.append(direct)
    queue = deque([(start_path[-1], start_path, start_edges)])
    visited = {start_path[-1]}
    while queue:
        current, path, edge_ids = queue.popleft()
        if str((nodes.get(current) or {}).get("type") or "").lower() == "customer":
            return {"node_ids": path, "edge_ids": edge_ids, "complete_to_customer": True}
        for dst, edge_id in adjacency.get(current, []):
            if dst in visited:
                continue
            visited.add(dst)
            queue.append((dst, path + [dst], edge_ids + [edge_id]))
    return {
        "node_ids": start_path,
        "edge_ids": start_edges,
        "complete_to_customer": False,
    }


def _affected_output_items(
    graph: dict[str, Any],
    destination_id: str,
    input_item_id: str,
) -> list[str]:
    outputs: set[str] = set()
    nodes = _node_map(graph)
    destination = nodes.get(destination_id) or {}
    for process in destination.get("processes") or []:
        inputs = {str(row.get("item_id") or "") for row in process.get("inputs") or []}
        if input_item_id not in inputs:
            continue
        outputs.update(
            str(row.get("item_id") or "")
            for row in process.get("outputs") or []
            if str(row.get("item_id") or "")
        )
    return sorted(outputs)


def _read_nominal_lots(
    lot_events_csv: str | Path | None,
    *,
    destination_id: str,
    input_item_id: str,
    output_item_ids: list[str],
    first_day: int | None,
    last_day: int | None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    if not lot_events_csv or first_day is None or last_day is None:
        return []
    path = Path(lot_events_csv)
    if not path.exists():
        return []
    selected: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            day = int(round(_number(row.get("day"), -1.0)))
            if day < first_day or day > last_day:
                continue
            event_type = str(row.get("event_type") or "")
            item_id = str(row.get("item_id") or "")
            node_id = str(row.get("node_id") or "")
            input_match = (
                node_id == destination_id
                and item_id == input_item_id
                and event_type.startswith("production_consume")
            )
            output_match = (
                item_id in output_item_ids
                and event_type == "production_output"
            )
            if not input_match and not output_match:
                continue
            lot_id = str(row.get("lot_id") or "")
            if not lot_id:
                continue
            selected.setdefault(
                lot_id,
                {
                    "lot_id": lot_id,
                    "day": day,
                    "event_type": event_type,
                    "node_id": node_id,
                    "item_id": item_id,
                    "qty": _number(row.get("qty")),
                    "uom": str(row.get("uom") or ""),
                    "production_campaign_id": str(
                        row.get("production_campaign_id") or ""
                    ),
                },
            )
            if len(selected) >= limit:
                break
    return sorted(selected.values(), key=lambda row: (row["day"], row["lot_id"]))


def build_temporal_propagation(
    paired_payload: dict[str, Any],
    graph: dict[str, Any],
    *,
    lot_events_csv: str | Path | None = None,
) -> dict[str, Any]:
    days = [int(value) for value in paired_payload.get("days") or []]
    metrics = paired_payload.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    by_factor: dict[str, dict[str, Any]] = {}
    for metric, metric_payload in metrics.items():
        stage = METRIC_STAGES.get(str(metric))
        if not stage:
            continue
        for factor_row in (metric_payload or {}).get("factors") or []:
            factor = str(factor_row.get("factor") or "")
            if not factor:
                continue
            entry = by_factor.setdefault(
                factor,
                {
                    "factor": factor,
                    "family": str(factor_row.get("family") or ""),
                    "scope": dict(
                        factor_row.get("scope")
                        or factor_pair_scope(factor)
                    ),
                    "metric_timings": {},
                },
            )
            entry["metric_timings"][str(metric)] = {
                "stage": stage,
                **_timing(days, factor_row),
            }

    factors: list[dict[str, Any]] = []
    for factor in paired_payload.get("factors") or []:
        entry = by_factor.get(str(factor))
        if not entry:
            continue
        observable = {
            metric: timing
            for metric, timing in entry["metric_timings"].items()
            if timing.get("observable")
        }
        stage_first_days: dict[str, int] = {}
        for timing in observable.values():
            stage = str(timing.get("stage") or "")
            day = int(timing.get("first_effect_day") or 0)
            stage_first_days[stage] = min(stage_first_days.get(stage, day), day)
        scope = entry["scope"]
        supplier_id = str(scope.get("supplier_id") or "")
        destination_id = str(scope.get("destination_id") or "")
        item_id = str(scope.get("item_id") or "")
        first_day = min(stage_first_days.values()) if stage_first_days else None
        last_day = max(
            (
                int(timing.get("last_effect_day") or 0)
                for timing in observable.values()
            ),
            default=None,
        )
        output_items = _affected_output_items(
            graph,
            destination_id,
            item_id,
        )
        client_impacted = "customer" in stage_first_days
        factory_impacted = "factory" in stage_first_days
        supplier_impacted = "supplier" in stage_first_days
        if client_impacted:
            outcome = "client_impacted"
        elif supplier_impacted or factory_impacted:
            outcome = "absorbed_before_customer"
        else:
            outcome = "no_observable_effect"
        entry.update(
            {
                "stage_first_effect_days": stage_first_days,
                "supplier_to_factory_lag_days": (
                    stage_first_days["factory"] - stage_first_days["supplier"]
                    if "supplier" in stage_first_days and "factory" in stage_first_days
                    else None
                ),
                "factory_to_customer_lag_days": (
                    stage_first_days["customer"] - stage_first_days["factory"]
                    if "factory" in stage_first_days and "customer" in stage_first_days
                    else None
                ),
                "outcome": outcome,
                "affected_output_item_ids": output_items,
                "network_path": _network_path(
                    graph,
                    supplier_id,
                    destination_id,
                ) if supplier_id else {},
                "nominally_exposed_lots": _read_nominal_lots(
                    lot_events_csv,
                    destination_id=destination_id,
                    input_item_id=item_id,
                    output_item_ids=output_items,
                    first_day=first_day,
                    last_day=last_day,
                ),
                "lot_attribution_basis": (
                    "nominal_time_window_overlap_not_causal"
                    if lot_events_csv
                    else "not_available"
                ),
            }
        )
        factors.append(entry)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_schema_version": paired_payload.get("schema_version"),
        "scenario_id": paired_payload.get("scenario_id"),
        "horizon_days": max(days) + 1 if days else 0,
        "factor_count": len(factors),
        "factors": factors,
        "lotification_status": {
            "integrated": bool(lot_events_csv),
            "mode": "nominal_exposure_window",
            "causal_perturbed_lot_trace": False,
            "next_step": (
                "Rejouer avec lot trace uniquement les facteurs les plus "
                "impactants pour une attribution causale exacte."
            ),
        },
        "reading": (
            "Les dates sont derivees des ecarts entre runs controles bas/centre/haut. "
            "Les lots listes sont ceux du nominal qui chevauchent la fenetre d'impact; "
            "ils indiquent une exposition plausible, pas encore une causalite exacte."
        ),
    }


__all__ = ["build_temporal_propagation"]
