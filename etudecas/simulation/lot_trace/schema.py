from __future__ import annotations

import math
from typing import Any


LOT_TRACE_NUMERIC_FIELDS = {
    "qty",
    "qty_after",
    "parent_qty",
    "child_qty",
    "allocation_share",
    "component_allocation_share",
    "desired_qty",
    "planned_qty_after_lot_rule",
    "actual_qty",
    "shortfall_vs_desired_qty",
    "shortfall_vs_lot_plan_qty",
    "planned_qty_before",
    "planned_qty_after",
    "lot_fixed_qty",
    "lot_min_qty",
    "lot_max_qty",
    "lot_multiple_qty",
    "campaign_requested_qty",
    "campaign_started_qty",
    "campaign_remaining_start_qty",
    "campaign_remaining_end_qty",
    "planned_qty",
    "requested_qty",
    "started_qty",
    "actual_qty",
    "completed_lot_qty",
    "blocked_lot_qty",
    "max_daily_shortfall_qty",
    "repeated_daily_shortfall_qty",
    "replacement_qty",
}
LOT_TRACE_INTEGER_FIELDS = {
    "day",
    "departure_day",
    "arrival_day",
    "next_expected_receipt_day",
    "first_event_day",
    "first_delay_day",
    "last_delay_day",
    "completed_day",
    "delay_event_count",
    "delay_day_count",
    "delay_span_days",
    "event_count",
    "max_lots_per_week",
    "started_lots_this_week",
    "requested_lot_starts",
    "actual_lot_starts",
}


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compact_lot_trace_row(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        value = row.get(field, "")
        if value == "":
            out[field] = ""
            continue
        if field in LOT_TRACE_INTEGER_FIELDS:
            numeric = to_float(value)
            out[field] = int(round(numeric)) if numeric is not None and not math.isnan(numeric) else value
        elif field in LOT_TRACE_NUMERIC_FIELDS:
            numeric = to_float(value)
            out[field] = round(numeric, 6) if numeric is not None and not math.isnan(numeric) else value
        else:
            out[field] = value
    return out
