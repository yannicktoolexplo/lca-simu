from __future__ import annotations

import csv
from pathlib import Path

from .campaigns import PRODUCTION_CAMPAIGN_FIELDS


LOT_TRACE_EVENT_FIELDS = [
    "event_id",
    "day",
    "event_type",
    "lot_id",
    "node_id",
    "item_id",
    "qty",
    "qty_after",
    "uom",
    "source_type",
    "source_id",
    "shipment_id",
    "risk_decision_day",
    "risk_event_ids",
    "related_lot_id",
    "production_campaign_id",
    "notes",
]
LOT_TRACE_GENEALOGY_FIELDS = [
    "day",
    "link_type",
    "parent_lot_id",
    "parent_node_id",
    "parent_item_id",
    "child_lot_id",
    "child_node_id",
    "child_item_id",
    "parent_qty",
    "child_qty",
    "allocation_share",
    "source_id",
    "shipment_id",
    "risk_decision_day",
    "risk_event_ids",
    "production_campaign_id",
    "notes",
]
LOT_TRACE_PLAN_EVENT_FIELDS = [
    "day",
    "campaign_id",
    "semantics_version",
    "campaign_started_day",
    "node_id",
    "output_item_id",
    "batch_id",
    "batch_started_day",
    "batch_target_qty",
    "batch_executed_start_qty",
    "batch_executed_today_qty",
    "batch_executed_end_qty",
    "process_tau_days",
    "release_gate_mode",
    "wip_start_qty",
    "wip_end_qty",
    "released_qty",
    "released_lot_id",
    "is_day_zero_carry_in",
    "event_type",
    "reason",
    "desired_qty",
    "planned_qty_after_lot_rule",
    "actual_qty",
    "shortfall_vs_desired_qty",
    "shortfall_vs_lot_plan_qty",
    "binding_input_item_id",
    "planned_qty_before",
    "planned_qty_after",
    "lot_policy_mode",
    "lot_fixed_qty",
    "lot_min_qty",
    "lot_max_qty",
    "lot_multiple_qty",
    "max_lots_per_week",
    "started_lots_this_week",
    "requested_lot_starts",
    "actual_lot_starts",
    "campaign_requested_qty",
    "campaign_started_qty",
    "campaign_remaining_start_qty",
    "campaign_remaining_end_qty",
    "next_expected_receipt_day",
    "notes",
]
LOT_TRACE_CAMPAIGN_FIELDS = PRODUCTION_CAMPAIGN_FIELDS


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
