"""Supplier local criticality, independent of map construction.

Extracted without changing the historical formulas, rows or display descriptors.
The CSV and sensitivity decoding primitives below deliberately retain their
previous missing-file, decimal-comma and fallback semantics. This module does
not import visualization; map callers retain compatibility re-exports.
"""
from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from etudecas.risk.supplier_audit import (
    blend_criticality_with_audit,
    estimate_supplier_audit_profiles,
    supplier_audit_score,
    supplier_estimated_score,
)

__all__ = ["build_supplier_local_criticality"]



def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def metric_label_value(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def _case_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


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


def safe_case_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def kpi_from_case(case_row: dict[str, str] | None, kpi_name: str) -> float | None:
    if not case_row:
        return None
    value = _case_to_float(case_row.get(f"kpi::{kpi_name}"))
    if value is None or math.isnan(value):
        return None
    return value


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


def build_supplier_local_criticality(
    raw: dict[str, Any],
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_capacity_csv: Path,
    production_constraint_csv: Path,
    sensitivity_cases_csv: Path,
    structural_sensitivity_cases_csv: Path,
    supplier_audits: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    supplier_audits = supplier_audits or {}
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
        structural_criticality_score = 0.55 * local_score + 0.45 * system_score
        audit = supplier_audits.get(supplier_id)
        audit_criticality_score = supplier_audit_score(audit)
        # Keep the operational ranking comparable across the whole supplier
        # population. Audit and proxy values are displayed alongside it and do
        # not silently change the rank when coverage differs by supplier.
        overall_score = structural_criticality_score
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
            "structural_criticality_score": round(structural_criticality_score, 6),
            "audit_criticality_score": round(audit_criticality_score, 6) if audit_criticality_score is not None else "",
            "audit_criterion_count": int((audit or {}).get("criterion_count") or 0),
            "audit_answered_criterion_count": int((audit or {}).get("answered_criterion_count") or 0),
            "audit_status": str((audit or {}).get("audit_status") or "not_available"),
            "overall_criticality_score": round(overall_score, 6),
            "indicative_adjusted_score": round(
                blend_criticality_with_audit(structural_criticality_score, audit), 6
            ),
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
                summary_lines.append(metric_label_value("Part cible MRP", f"{row['target_sourcing_share']:.1%}"))
        else:
            summary_lines.append(metric_label_value("Part du flux observee", "n/a"))
        nominal_capacity = supplier_nominal_capacity_by_supplier.get(supplier_id, 0.0)
        if nominal_capacity > 0:
            summary_lines.append(metric_label_value("Capacite nominale", f"{nominal_capacity:,.2f}/j".replace(",", " ")))
        basis_label = supplier_capacity_basis_by_supplier.get(supplier_id, "")
        if basis_label:
            scale = supplier_capacity_scale_by_supplier.get(supplier_id, 0.0)
            suffix = f" x{scale:.0f}" if scale > 0 else ""
            summary_lines.append(metric_label_value("Reference capacite", f"{basis_label}{suffix}"))
        summary_lines.append(metric_label_value("Paires mono-source", str(row["sole_source_pairs"])))
        if row["shortage_supported_qty"] > 0 or row["shortage_supported_events"] > 0:
            summary_lines.append(
                metric_label_value(
                    "Rupture couverte",
                    f"{row['shortage_supported_qty']:.2f} sur {row['shortage_supported_events']} evenements",
                )
            )
        else:
            summary_lines.append(metric_label_value("Rupture couverte", "aucune detectee"))
        summary_lines.append(metric_label_value("Criticite locale", f"{local_score:.3f}"))
        if audit_criticality_score is not None:
            summary_lines.extend(
                [
                    metric_label_value("Criticite structurelle", f"{structural_criticality_score:.3f}"),
                    metric_label_value("Indice audit fournisseur", f"{audit_criticality_score:.1%}"),
                    metric_label_value(
                        "Indice croise indicatif",
                        f"{blend_criticality_with_audit(structural_criticality_score, audit):.3f}",
                    ),
                    metric_label_value("Criteres audit integres", str(audit.get("criterion_count") or 0)),
                ]
            )
        if std_label or struct_label or system_score > 1e-9:
            if std_label:
                summary_lines.append(metric_label_value("Point faible sensibilite", std_label))
            if struct_label:
                summary_lines.append(metric_label_value("Point faible reseau", struct_label))
            summary_lines.append(metric_label_value("Criticite reseau", f"{system_score:.3f}"))
        metrics_by_supplier[supplier_id] = {
            "summary_lines": summary_lines,
            "items": supplied_items,
            "destinations": dest_nodes,
            "scores": {
                "local": round(local_score, 6),
                "system": round(system_score, 6),
                "structural": round(structural_criticality_score, 6),
                "audit": round(audit_criticality_score, 6) if audit_criticality_score is not None else None,
                "overall": round(overall_score, 6),
            },
            "supplier_audit": audit,
        }

    estimate_supplier_audit_profiles(supplier_audits, ranking_rows)
    for row in ranking_rows:
        supplier_id = str(row["supplier_id"])
        audit = supplier_audits.get(supplier_id) or {}
        estimated_score = supplier_estimated_score(audit)
        audited_score = supplier_audit_score(audit)
        row["supplier_name"] = supplier_id
        row["audit_status"] = str(audit.get("audit_status") or "not_available")
        row["audit_criterion_count"] = int(audit.get("criterion_count") or 0)
        row["audit_answered_criterion_count"] = int(audit.get("answered_criterion_count") or 0)
        row["audit_estimated_criterion_count"] = int(audit.get("estimated_criterion_count") or 0)
        row["audit_criticality_score"] = round(audited_score, 6) if audited_score is not None else ""
        row["estimated_audit_risk_index"] = (
            round(estimated_score, 6) if estimated_score is not None else ""
        )
        proxy_score = audited_score if audited_score is not None else estimated_score
        row["indicative_adjusted_score"] = (
            round(0.70 * float(row["structural_criticality_score"]) + 0.30 * proxy_score, 6)
            if proxy_score is not None
            else row["structural_criticality_score"]
        )
        supplier_metrics = metrics_by_supplier.get(supplier_id, {})
        supplier_metrics["supplier_audit"] = audit
        supplier_metrics.setdefault("scores", {})["audit_estimate"] = (
            round(estimated_score, 6) if estimated_score is not None else None
        )
        supplier_metrics["scores"]["indicative_adjusted"] = row["indicative_adjusted_score"]

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
            "supplier_audit_blend": {
                "structural_score": 0.70,
                "supplier_audit_score": 0.30,
                "ranking_effect": "none",
                "purpose": "indicative_adjusted_score_only",
            },
        },
        "supplier_audit_profile_count": len(supplier_audits),
        "supplier_audit_scored_count": sum(
            1 for audit in supplier_audits.values() if supplier_audit_score(audit) is not None
        ),
        "supplier_audit_estimated_count": sum(
            1 for audit in supplier_audits.values() if supplier_estimated_score(audit) is not None
        ),
    }
    return metrics_by_supplier, ranking_rows, summary
