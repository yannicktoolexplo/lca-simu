"""Global KPI tree payload builder for supply-chain world maps."""

from __future__ import annotations

import math
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from etudecas.case_config import ITEM_DISPLAY_REFERENCE_NOTES
from etudecas.simulation.kpi_engine import (
    DEFAULT_PHYSICS_KPI_DEFINITIONS,
    KpiDefinition,
    compute_kpi_rows,
    write_kpi_rows_csv,
)
from etudecas.visualization.maps.map_data_loader import read_csv_rows
from etudecas.visualization.maps.map_payload_builder import (
    display_node_label,
    display_standard_order_qty,
    is_simulation_hidden_item,
)
from etudecas.visualization.maps.map_render import fmt_pct, fmt_qty


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


DAILY_COST_FIELDS = [
    "holding_cost_day",
    "warehouse_operating_cost_day",
    "inventory_risk_cost_day",
    "transport_cost_day",
    "operational_transport_cost_day",
    "purchase_cost_day",
    "operational_purchase_cost_day",
    "production_cost_day",
    "total_supply_cost_day",
]


def positive_sum(rows: list[dict[str, str]], field: str) -> float:
    total = 0.0
    for row in rows:
        value = to_float(row.get(field))
        if value is not None and not math.isnan(value):
            total += max(0.0, value)
    return total


def has_positive_daily_costs(rows: list[dict[str, str]]) -> bool:
    return any(positive_sum(rows, field) > 1e-9 for field in DAILY_COST_FIELDS)


def read_daily_kpi_rows_with_cost_fallback(daily_kpi_csv: Path) -> tuple[list[dict[str, str]], Path, str]:
    rows = read_csv_rows(daily_kpi_csv)
    if has_positive_daily_costs(rows):
        return rows, daily_kpi_csv, "daily_cost_csv"

    sibling_first_daily = daily_kpi_csv.parent / "first_simulation_daily.csv"
    if sibling_first_daily != daily_kpi_csv and sibling_first_daily.exists():
        sibling_rows = read_csv_rows(sibling_first_daily)
        if has_positive_daily_costs(sibling_rows):
            return sibling_rows, sibling_first_daily, "first_simulation_daily_fallback"

    return rows, daily_kpi_csv, "summary_reconstructed_fallback"


def read_summary_kpis(data_dir: Path) -> dict[str, float]:
    summary_path = data_dir.parent / "summaries" / "first_simulation_summary.json"
    if not summary_path.exists():
        return {}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    kpis = payload.get("kpis") if isinstance(payload, dict) else None
    if not isinstance(kpis, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in kpis.items():
        numeric = to_float(value)
        if numeric is not None and not math.isnan(numeric):
            out[str(key)] = float(numeric)
    return out


def add_weighted_total(target: dict[int, float], day: int, value: float) -> None:
    target[day] = target.get(day, 0.0) + max(0.0, value)


def stock_weight_from_rows(rows: list[dict[str, str]], day_field: str = "day") -> dict[int, float]:
    weights: dict[int, float] = defaultdict(float)
    for row in rows:
        day_value = to_float(row.get(day_field))
        if day_value is None or math.isnan(day_value):
            continue
        stock_value = None
        for field in ["stock_end_of_day", "stock_qty", "ending_stock_qty", "available_stock_qty"]:
            stock_value = to_float(row.get(field))
            if stock_value is not None and not math.isnan(stock_value):
                break
        if stock_value is None or math.isnan(stock_value):
            continue
        weights[int(day_value)] += max(0.0, stock_value)
    return dict(weights)


def scale_daily_weights(days: list[int], weights: dict[int, float], total: float) -> dict[int, float]:
    total = max(0.0, total)
    if total <= 1e-9:
        return {day: 0.0 for day in days}
    weight_sum = sum(max(0.0, weights.get(day, 0.0)) for day in days)
    if weight_sum <= 1e-9:
        flat = total / len(days) if days else 0.0
        return {day: flat for day in days}
    return {day: total * max(0.0, weights.get(day, 0.0)) / weight_sum for day in days}


def reconstructed_cost_series_from_run(
    data_dir: Path,
    days: list[int],
) -> tuple[dict[str, dict[int, float]], str]:
    """Recover daily cost curves when first_simulation_daily.csv is unavailable.

    The engine summary remains the source of truth for totals. Daily shape is allocated
    with operational drivers available in the run: stocks for inventory costs, shipped
    transport cost for transport, MRP release volume for purchase, and production volume
    for conversion cost.
    """
    if not days:
        return {}, "no_days"

    kpis = read_summary_kpis(data_dir)
    if not kpis:
        return {}, "missing_summary"

    stock_weights: dict[int, float] = defaultdict(float)
    for filename in [
        "production_input_stocks_daily.csv",
        "production_output_products_daily.csv",
        "production_dc_stocks_daily.csv",
        "production_supplier_stocks_daily.csv",
    ]:
        for day, value in stock_weight_from_rows(read_csv_rows(data_dir / filename)).items():
            stock_weights[day] += value

    production_weights: dict[int, float] = defaultdict(float)
    for row in read_csv_rows(data_dir / "production_output_products_daily.csv"):
        day = to_float(row.get("day"))
        qty = to_float(row.get("produced_qty"))
        if day is not None and not math.isnan(day) and qty is not None and not math.isnan(qty):
            production_weights[int(day)] += max(0.0, qty)

    purchase_weights: dict[int, float] = defaultdict(float)
    for row in read_csv_rows(data_dir / "mrp_orders_daily.csv"):
        day_value = to_float(row.get("release_day"))
        if day_value is None or math.isnan(day_value):
            day_value = to_float(row.get("day"))
        qty = to_float(row.get("release_qty"))
        if day_value is not None and not math.isnan(day_value) and qty is not None and not math.isnan(qty):
            purchase_weights[int(day_value)] += max(0.0, qty)

    transport_cost_weights: dict[int, float] = defaultdict(float)
    transport_qty_weights: dict[int, float] = defaultdict(float)
    transport_cost_observed = 0.0
    for row in read_csv_rows(data_dir / "production_supplier_shipments_daily.csv"):
        day = to_float(row.get("day"))
        if day is None or math.isnan(day):
            continue
        cost = to_float(row.get("transport_cost"))
        if cost is not None and not math.isnan(cost) and cost > 0:
            add_weighted_total(transport_cost_weights, int(day), cost)
            transport_cost_observed += cost
        qty = to_float(row.get("shipped_qty"))
        if qty is not None and not math.isnan(qty):
            add_weighted_total(transport_qty_weights, int(day), qty)

    holding = scale_daily_weights(days, dict(stock_weights), kpis.get("total_holding_cost", 0.0))
    warehouse = scale_daily_weights(days, dict(stock_weights), kpis.get("total_warehouse_operating_cost", 0.0))
    risk = scale_daily_weights(days, dict(stock_weights), kpis.get("total_inventory_risk_cost", 0.0))
    production = scale_daily_weights(days, dict(production_weights), kpis.get("total_production_cost", 0.0))
    purchase = scale_daily_weights(days, dict(purchase_weights), kpis.get("total_purchase_cost", 0.0))
    transport_total = kpis.get("total_transport_cost", 0.0)
    transport_weights = transport_cost_weights if transport_cost_observed > 1e-9 else transport_qty_weights
    transport = scale_daily_weights(days, dict(transport_weights), transport_total)

    total = {
        day: holding[day] + warehouse[day] + risk[day] + production[day] + purchase[day] + transport[day]
        for day in days
    }
    note = (
        "reconstruit depuis first_simulation_summary.json; "
        "forme journaliere allouee par stock, production, commandes MRP et transports"
    )
    if transport_cost_observed > 1e-9:
        note += "; transport journalier observe puis remis a l'echelle du total moteur"
    return {
        "holding_cost_day": holding,
        "warehouse_operating_cost_day": warehouse,
        "inventory_risk_cost_day": risk,
        "operational_transport_cost_day": transport,
        "transport_cost_day": transport,
        "operational_purchase_cost_day": purchase,
        "purchase_cost_day": purchase,
        "production_cost_day": production,
        "total_supply_cost_day": total,
    }, note


def compact_item_label(item_id: str) -> str:
    raw = str(item_id or "").strip()
    if raw.startswith("item:"):
        return raw.split(":", 1)[1]
    return raw or "n/a"


def item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code if code else (name if name else item_id)
        lookup[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return lookup


def order_placed_day(row: dict[str, str]) -> float | None:
    value = to_float(row.get("order_date_imt"))
    if value is None or math.isnan(value):
        value = to_float(row.get("day"))
    if value is None or math.isnan(value):
        return None
    return float(value)


def is_opening_order_row(row: dict[str, str]) -> bool:
    return str(row.get("order_type") or "").startswith("opening_")


def source_planned_material_lead_days(row: dict[str, str]) -> float | None:
    value = to_float(row.get("lead_reference_days"))
    if value is not None and not math.isnan(value) and value > 0:
        return float(value)
    if is_opening_order_row(row):
        value = to_float(row.get("lead_days"))
        if value is not None and not math.isnan(value) and value >= 0:
            return float(value)
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


def build_global_kpi_tree_payload(
    daily_kpi_csv: Path,
    demand_service_csv: Path,
    production_constraint_csv: Path,
    mrp_orders_csv: Path | None = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    daily_rows, effective_daily_kpi_csv, cost_source = read_daily_kpi_rows_with_cost_fallback(daily_kpi_csv)
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
        lot_plan_shortfall = max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0)
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
            production_by_day[day]["input_shortage_shortfall_desired_qty"] += shortfall
            production_by_day[day]["input_shortage_shortfall_lot_plan_qty"] += lot_plan_shortfall
            production_by_day[day]["input_shortage_plan_gap_qty"] += abs(actual - planned)
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

    cost_source_note = "cout journalier moteur"
    if cost_source == "first_simulation_daily_fallback":
        cost_source_note = "cout journalier moteur via first_simulation_daily.csv"
    elif cost_source == "summary_reconstructed_fallback":
        reconstructed_costs, reconstructed_note = reconstructed_cost_series_from_run(production_constraint_csv.parent, days)
        if reconstructed_costs:
            for field, series in reconstructed_costs.items():
                for day, value in series.items():
                    daily_by_day[day][field] = max(0.0, value)
            cost_source_note = reconstructed_note
        else:
            cost_source_note = f"cout non disponible ({reconstructed_note})"

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
    input_shortage_shortfall_desired_qty = {
        day: production_by_day[day].get("input_shortage_shortfall_desired_qty", 0.0)
        for day in days
    }
    input_shortage_shortfall_lot_plan_qty = {
        day: production_by_day[day].get("input_shortage_shortfall_lot_plan_qty", 0.0)
        for day in days
    }
    input_shortage_plan_gap_qty = {
        day: production_by_day[day].get("input_shortage_plan_gap_qty", 0.0)
        for day in days
    }
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
    input_shortage_lot_plan_loss_share = {
        day: (
            100.0 * input_shortage_shortfall_lot_plan_qty[day] / planned_qty[day]
            if planned_qty[day] > 0
            else 0.0
        )
        for day in days
    }
    input_shortage_desired_loss_share = {
        day: (
            100.0 * input_shortage_shortfall_desired_qty[day] / desired_qty[day]
            if desired_qty[day] > 0
            else 0.0
        )
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
    startup_cost = {
        day: total_supply_cost[day] if day < startup_cutoff_days else 0.0
        for day in days
    }
    established_cost = {
        day: total_supply_cost[day] if day >= startup_cutoff_days else 0.0
        for day in days
    }
    positive_costs = [value for value in total_supply_cost.values() if value > 0]
    established_positive_costs = [
        total_supply_cost[day]
        for day in days
        if day >= startup_cutoff_days and total_supply_cost[day] > 0
    ]
    avg_established_cost = (
        sum(established_positive_costs) / len(established_positive_costs)
        if established_positive_costs
        else 0.0
    )
    cost_index_base_costs = established_positive_costs if established_positive_costs else positive_costs
    avg_total_supply_cost = sum(cost_index_base_costs) / len(cost_index_base_costs) if cost_index_base_costs else 1.0
    established_average_cost = {
        day: avg_established_cost if day >= startup_cutoff_days and avg_established_cost > 1e-9 else 0.0
        for day in days
    }
    opening_cost = {day: opening_transport_cost[day] + opening_purchase_cost[day] for day in days}
    cost_index_base_label = "regime etabli J30+" if established_positive_costs else "scenario complet"
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
    physics_kpi_csv = effective_daily_kpi_csv.parent / "physics_of_decision_kpi_daily.csv"
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
    total_input_shortage_shortfall_lot_plan = sum(input_shortage_shortfall_lot_plan_qty.values())
    total_input_shortage_shortfall_desired = sum(input_shortage_shortfall_desired_qty.values())
    max_input_shortage_line_share = max(input_shortage_line_share.values(), default=0.0)
    avg_input_shortage_line_share = (
        sum(input_shortage_line_share.values()) / len(input_shortage_line_share)
        if input_shortage_line_share
        else 0.0
    )
    capacity_days = sum(1 for day in days if production_by_day[day].get("capacity_day", 0.0) > 0)
    weekly_lot_limit_days = sum(1 for day in days if production_by_day[day].get("weekly_lot_limit_day", 0.0) > 0)
    total_requested_lot_starts = sum(requested_lot_starts.values())
    total_actual_lot_starts = sum(actual_lot_starts.values())
    total_logistics_cost = sum(logistics_cost.values())
    total_supply_cost_value = sum(total_supply_cost.values())
    total_startup_cost = sum(startup_cost.values())
    total_established_cost = sum(established_cost.values())
    total_inventory_cost = sum(inventory_cost.values())
    total_transport_cost = sum(transport_cost.values())
    total_opening_transport_cost = sum(opening_transport_cost.values())
    total_purchase_cost = sum(purchase_cost.values())
    total_production_cost = sum(production_cost.values())
    total_opening_purchase_cost = sum(opening_purchase_cost.values())
    total_opening_cost = sum(opening_cost.values())
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
            "name": "Part lignes contraintes matiere",
            "formula": "100 x lignes dont binding_cause = input_shortage / lignes actives",
            "terms": "Contrainte matiere signifie que la production demandee n'a pas pu etre executee faute de composant disponible.",
            "interpretation": "Part de production limitee par manque de composant.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Manque matiere vs plan lotifie",
            "formula": "100 x somme(shortfall_vs_lot_plan_qty si binding_cause=input_shortage) / somme(planned_qty_after_lot_rule)",
            "terms": "Mesure la partie du plan lotifie non executee a cause d'une matiere/composant disponible insuffisant.",
            "interpretation": "C'est le meilleur indicateur pour relier tension MP et instabilite planning: le client peut rester servi, mais l'usine doit modifier son plan.",
        },
        {
            "family": "Production",
            "level": "KPI secondaire",
            "name": "Manque matiere vs besoin usine",
            "formula": "100 x somme(shortfall_vs_desired_qty si binding_cause=input_shortage) / somme(desired_qty)",
            "terms": "Mesure le manque strict par rapport au besoin industriel du jour, hors surproduction/lotification future.",
            "interpretation": "Permet de distinguer un ecart au plan lotifie d'un vrai manque par rapport au besoin du jour.",
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
            "formula": "100 x (Cout_stock(t) + Cout_transport(t) + Cout_achat(t) + Cout_production(t)) / base_cout",
            "terms": "base_cout=moyenne des jours J30+ avec cout operationnel positif si disponible, sinon moyenne des jours du scenario avec cout positif. Cout_transport et Cout_achat excluent le carnet initial deja engage.",
            "interpretation": "Indice base 100. Au-dessus de 100, la journee coute plus cher que le regime etabli quand celui-ci est observable.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Cout d'amorcage J0-J29",
            "formula": "Cout_operationnel_total(t) si t < 30, sinon 0",
            "terms": "Isole la phase d'amorcage afin que les couts initiaux ne soient pas confondus avec le regime etabli.",
            "interpretation": "Les pics J0-J29 peuvent venir de la mise en route du scenario et doivent etre lus a part.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Regime etabli J30+",
            "formula": "Cout_operationnel_total(t) si t >= 30, sinon 0",
            "terms": "Fenetre retenue pour la base d'indice lorsque des couts positifs existent apres J29.",
            "interpretation": "Montre la trajectoire cout une fois l'amorcage sorti de la lecture principale.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Moyenne regime etabli",
            "formula": "moyenne(Cout_operationnel_total(t) pour t >= 30 et cout > 0)",
            "terms": "Ligne horizontale tracee sur J30+ uniquement; absente si aucun regime etabli positif n'est disponible.",
            "interpretation": "Reference visuelle de la base 100 utilisee par l'indice cout.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Carnet initial deja engage",
            "formula": "opening_open_order_purchase_cost_day + opening_open_order_transport_cost_day",
            "terms": "Couts d'achat et de transport des open orders presents au demarrage, deja engages avant les decisions simulees.",
            "interpretation": "Ce montant est affiche separement du cout operationnel pilotable pour eviter de l'attribuer a la politique courante.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution cout d'achat matiere - indice",
            "formula": "100 x Cout_achat(t) / base_cout",
            "terms": "Cout_achat=operational_purchase_cost_day, c.-a-d. cout d'achat des matieres/fournisseurs sur les flux commandes par la politique simulee, hors carnet initial deja engage.",
            "interpretation": "Part de la pression cout due au cout d'achat des matieres/fournisseurs.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution cout de production - indice",
            "formula": "100 x Cout_production(t) / base_cout",
            "terms": "Cout_production=production_cost_day, estimation de cout de conversion pharma: fabrication, main-d'oeuvre, utilites, qualite, nettoyage, maintenance et depreciation.",
            "interpretation": "Part de la pression cout due aux operations de fabrication, separee des achats matieres.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution stock - indice",
            "formula": "100 x Cout_stock(t) / base_cout",
            "terms": "Cout_stock=holding_cost_day + warehouse_operating_cost_day + inventory_risk_cost_day.",
            "interpretation": "Part de la pression cout due au stock: immobilisation, stockage, risque inventaire.",
        },
        {
            "family": "Couts stock / transport",
            "level": "KPI secondaire",
            "name": "Contribution transport pilotable - indice",
            "formula": "100 x Cout_transport_pilotable(t) / base_cout",
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
                "formula": "Indice base 100 du cout operationnel journalier total, base J30+ si disponible",
                "terms": "Cout operationnel = cout d'achat matiere + cout de production + cout stock + cout de transport. J0-J29, J30+, moyenne J30+ et carnet initial sont affiches dans les KPI secondaires.",
                "interpretation": "Permet de voir les jours plus chers que le regime etabli, sans laisser l'amorcage J0-J29 deformer la base de comparaison.",
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
        "Cout d'amorcage J0-J29",
        "Regime etabli J30+",
        "Moyenne regime etabli",
        "Carnet initial deja engage",
        "Pilotable",
    }

    physics_kpi_display = [
        ("product_availability", "Disponibilite produit", "#0f766e", "served_qty / required_with_backlog_qty"),
        ("line_adherence", "Adherence plan lotifie", "#2563eb", "actual_qty vs planned_qty_after_lot_rule, moyenne glissante 30j"),
        ("line_nervousness", "Nervosite planning (%)", "#d97706", "Amplitude moyenne journaliere des changements de plan par ligne"),
        ("production_replanning_count", "Lignes replanifiees", "#7c3aed", "Nombre de lignes dont le plan change vs jour precedent"),
        ("raw_material_stockout_days", "Signal MP usine zero 30j", "#dc2626", "Diagnostic technique: nombre de jours calendaires, dans la fenetre glissante 30j, ou au moins une MP suivie finit la journee a stock usine nul."),
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
        "startup_cutoff_day": startup_cutoff_days,
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
                "objective": "Reduire l'instabilite planning due aux ruptures composants.",
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
                    summary("Jours contrainte matiere", str(input_shortage_days)),
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
                "id": "material_factory_nervousness",
                "label": "Nervosite matiere usine",
                "objective": "Mesurer comment les tensions matieres perturbent l'execution usine, meme si le service client reste protege.",
                "summary": [
                    summary("Jours avec contrainte matiere", str(input_shortage_days)),
                    summary("Lignes contraintes matiere max", fmt_pct(max_input_shortage_line_share)),
                    summary("Lignes contraintes matiere moy.", fmt_pct(avg_input_shortage_line_share)),
                    summary("Manque vs plan lotifie", fmt_qty(total_input_shortage_shortfall_lot_plan)),
                    summary("Manque vs besoin usine", fmt_qty(total_input_shortage_shortfall_desired)),
                    summary("Lecture service client", "absorbe si fill rate reste a 100% et backlog a 0"),
                ],
                "secondary": [
                    {"label": "Lignes contraintes matiere (%)", **series_from_map(input_shortage_line_share), "color": "#be123c"},
                    {"label": "Manque matiere vs plan lotifie (%)", **series_from_map(input_shortage_lot_plan_loss_share), "color": "#dc2626", "dash": "dash"},
                    {"label": "Manque matiere vs besoin usine (%)", **series_from_map(input_shortage_desired_loss_share), "color": "#f97316"},
                    {"label": "Nervosite planning (%)", **series_from_map(line_nervousness), "color": "#7c3aed"},
                    {"label": "Lignes replanifiees", **series_from_map(production_replanning_count), "color": "#475569", "dash": "dot"},
                    {"label": "Signal MP usine zero 30j", **series_from_map(raw_material_stockout_days_30d), "color": "#64748b", "dash": "dot"},
                ],
                "secondary_y_label": "% / lignes",
            },
            {
                "id": "cost",
                "label": "Couts supply",
                "objective": "Comprendre le cout operationnel: achat matiere, production, stock et transport.",
                "summary": [
                    summary("Cout operationnel total", fmt_qty(total_supply_cost_value)),
                    summary("Cout d'amorcage J0-J29", fmt_qty(total_startup_cost)),
                    summary("Regime etabli J30+", fmt_qty(total_established_cost)),
                    summary(
                        "Moyenne regime etabli",
                        fmt_qty(avg_established_cost) if avg_established_cost > 1e-9 else "n/a",
                    ),
                    summary("Base indice cout", cost_index_base_label),
                    summary("Cout d'achat matiere", f"{fmt_qty(total_purchase_cost)} ({cost_share(total_purchase_cost)})"),
                    summary("Cout de production", f"{fmt_qty(total_production_cost)} ({cost_share(total_production_cost)})"),
                    summary("Cout stock", f"{fmt_qty(total_inventory_cost)} ({cost_share(total_inventory_cost)})"),
                    summary("Cout de transport pilotable", f"{fmt_qty(total_transport_cost)} ({cost_share(total_transport_cost)})"),
                    summary(
                        "Carnet initial deja engage",
                        f"{fmt_qty(total_opening_cost)} (achat {fmt_qty(total_opening_purchase_cost)}, transport {fmt_qty(total_opening_transport_cost)})",
                    ),
                    summary("Cout total scenario", fmt_qty(total_scenario_cost_excluding_external)),
                    summary("Principal pic transport", transport_spike_driver),
                    summary("Source cout", cost_source_note),
                ],
                "secondary": [
                    {"label": "Cout operationnel total", **series_from_map(total_supply_cost), "color": "#d97706"},
                    {"label": "Cout d'amorcage (J0-J29)", **series_from_map(startup_cost), "color": "#f59e0b", "dash": "dot"},
                    {"label": "Regime etabli (J30+)", **series_from_map(established_cost), "color": "#0891b2"},
                    {"label": "Moyenne regime etabli", **series_from_map(established_average_cost), "color": "#111827", "dash": "dash"},
                    {"label": "Carnet initial deja engage", **series_from_map(opening_cost), "color": "#64748b", "dash": "dashdot"},
                    {"label": "Cout d'achat matiere", **series_from_map(purchase_cost), "color": "#0f766e"},
                    {"label": "Cout de production", **series_from_map(production_cost), "color": "#be123c"},
                    {"label": "Cout stock", **series_from_map(inventory_cost), "color": "#7c3aed"},
                    {"label": "Cout de transport pilotable", **series_from_map(transport_cost), "color": "#f97316"},
                ],
                "secondary_y_label": "Cout / jour",
            },
        ],
    }

