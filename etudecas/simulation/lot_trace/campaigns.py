from __future__ import annotations

from collections import defaultdict
from typing import Any


PRODUCTION_CAMPAIGN_FIELDS = [
    "campaign_id",
    "record_type",
    "semantics_version",
    "node_id",
    "output_item_id",
    "process_tau_days",
    "release_gate_mode",
    "status",
    "status_label",
    "campaign_started_day",
    "first_event_day",
    "first_execution_day",
    "last_execution_day",
    "first_delay_day",
    "last_delay_day",
    "last_release_day",
    "completed_day",
    "completion_basis",
    "delay_event_count",
    "delay_day_count",
    "delay_span_days",
    "event_count",
    "planned_qty",
    "requested_qty",
    "started_qty",
    "actual_qty",
    "remaining_qty",
    "wip_qty",
    "requested_lot_starts",
    "actual_lot_starts",
    "lot_policy_modes",
    "completed_lot_ids",
    "completed_lot_qty",
    "released_batch_count",
    "blocked_lot_qty",
    "max_daily_shortfall_qty",
    "repeated_daily_shortfall_qty",
    "delay_reasons",
    "binding_input_item_ids",
    "next_expected_receipt_days",
    "first_event_type",
    "last_event_type",
    "notes",
]

CAMPAIGN_DELAY_EVENT_TYPES = {
    "delay_input_shortage",
    "delay_capacity",
    "delay_weekly_lot_limit",
    "delay_lot_campaign_blocked",
    "partial_run_input_shortage",
    "partial_run_capacity",
}

LOT_TRACE_EPS = 1e-6


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_day(row: dict[str, Any]) -> int:
    return int(round(_to_float(row.get("day"), 0.0)))


def _qty(row: dict[str, Any], field: str) -> float:
    return max(0.0, _to_float(row.get(field), 0.0))


def _synthetic_order_id(row: dict[str, Any]) -> str:
    node_id = str(row.get("node_id") or "node")
    output_item_id = str(row.get("output_item_id") or "item").replace(":", "-")
    event_type = str(row.get("event_type") or "plan")
    return f"ORDER-{node_id}-{output_item_id}-D{_as_day(row)}-{event_type}"


def _compact_plan_release_rows(
    rows: list[dict[str, Any]],
    *,
    campaign_id: str,
) -> list[dict[str, Any]]:
    """Return exact physical batch releases recorded by compact plan events.

    Compact runs intentionally omit the lot ledger.  Their plan-event schema
    nevertheless records a physical ``released_qty`` and a stable ``batch_id``
    once execution of a batch is complete.  We use that evidence only when the
    whole lot-event input is absent.  A repeated or anonymous release cannot be
    counted exactly, so it is rejected instead of being turned into a synthetic
    lot or an inferred batch.
    """

    release_rows: list[dict[str, Any]] = []
    released_batch_ids: set[str] = set()
    for row in rows:
        if _qty(row, "released_qty") <= LOT_TRACE_EPS:
            continue
        batch_id = str(row.get("batch_id") or "").strip()
        if not batch_id:
            raise ValueError(
                "Compact production release lacks batch_id; "
                f"campaign {campaign_id!r} cannot be summarized exactly"
            )
        if batch_id in released_batch_ids:
            raise ValueError(
                "Compact production release repeats batch_id; "
                f"campaign {campaign_id!r}, batch {batch_id!r} cannot be "
                "summarized without double counting"
            )
        released_batch_ids.add(batch_id)
        release_rows.append(row)
    return release_rows


def build_production_campaign_rows(
    production_plan_event_rows: list[dict[str, Any]],
    lot_event_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize daily planning rows into business-level production campaigns.

    A physical lot only exists once production succeeds. This ledger keeps the
    planned/reported order visible before that point, without pretending it is a
    lot.
    """

    rows_by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    record_type_by_campaign: dict[str, str] = {}
    for row in production_plan_event_rows:
        campaign_id = str(row.get("campaign_id") or "").strip()
        record_type = "campaign"
        if not campaign_id:
            event_type = str(row.get("event_type") or "")
            reason = str(row.get("reason") or "")
            if not event_type and not reason:
                continue
            campaign_id = _synthetic_order_id(row)
            record_type = "order_request"
        row_copy = dict(row)
        row_copy["campaign_id"] = campaign_id
        rows_by_campaign[campaign_id].append(row_copy)
        record_type_by_campaign[campaign_id] = record_type

    lot_trace_available = bool(lot_event_rows)
    output_lots_by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lot_event_rows:
        if str(row.get("event_type") or "") != "production_output":
            continue
        campaign_id = str(row.get("production_campaign_id") or "").strip()
        if not campaign_id:
            continue
        output_lots_by_campaign[campaign_id].append(row)

    out: list[dict[str, Any]] = []
    for campaign_id, rows in rows_by_campaign.items():
        ordered_rows = sorted(rows, key=lambda row: (_as_day(row), str(row.get("event_type") or "")))
        if not ordered_rows:
            continue
        first_row = ordered_rows[0]
        delay_rows = [
            row
            for row in ordered_rows
            if str(row.get("event_type") or "") in CAMPAIGN_DELAY_EVENT_TYPES
            or (
                str(row.get("reason") or "")
                in {"input_shortage", "capacity", "weekly_lot_limit", "lot_campaign_blocked"}
                and _qty(row, "actual_qty") <= LOT_TRACE_EPS
            )
        ]
        run_rows = [row for row in ordered_rows if _qty(row, "actual_qty") > LOT_TRACE_EPS]
        output_lot_rows = sorted(output_lots_by_campaign.get(campaign_id, []), key=lambda row: _as_day(row))
        output_lot_ids = [str(row.get("lot_id") or "") for row in output_lot_rows if str(row.get("lot_id") or "")]
        output_lot_qty = sum(_qty(row, "qty") for row in output_lot_rows)
        compact_release_rows = (
            []
            if lot_trace_available
            else _compact_plan_release_rows(
                ordered_rows,
                campaign_id=campaign_id,
            )
        )
        release_evidence_rows = (
            output_lot_rows if lot_trace_available else compact_release_rows
        )
        release_evidence_qty = (
            output_lot_qty
            if lot_trace_available
            else sum(_qty(row, "released_qty") for row in compact_release_rows)
        )
        released_batch_count = (
            len(output_lot_ids)
            if lot_trace_available
            else len(compact_release_rows)
        )
        first_event_day = _as_day(first_row)
        campaign_started_day = min(
            (
                int(round(_to_float(row.get("campaign_started_day"), _as_day(row))))
                for row in ordered_rows
                if str(row.get("campaign_started_day") or "").strip()
            ),
            default=first_event_day,
        )
        first_execution_day = min((_as_day(row) for row in run_rows), default="")
        last_execution_day = max((_as_day(row) for row in run_rows), default="")
        first_delay_day = min((_as_day(row) for row in delay_rows), default="")
        last_delay_day = max((_as_day(row) for row in delay_rows), default="")
        last_release_day = max(
            (_as_day(row) for row in release_evidence_rows),
            default="",
        )
        final_row = ordered_rows[-1]
        remaining_qty = _qty(final_row, "campaign_remaining_end_qty")
        wip_qty = _qty(final_row, "wip_end_qty")
        remaining_raw = final_row.get("campaign_remaining_end_qty")
        has_explicit_remaining = remaining_raw is not None and str(remaining_raw).strip() != ""
        campaign_complete = bool(release_evidence_rows) and (
            (has_explicit_remaining and remaining_qty <= LOT_TRACE_EPS)
            or str(final_row.get("event_type") or "") == "run_campaign_complete"
        )
        completed_day = last_release_day if campaign_complete else ""
        completion_basis = (
            (
                "last_released_physical_lot"
                if lot_trace_available
                else "last_released_physical_batch_from_plan_event"
            )
            if campaign_complete
            else ""
        )
        planned_qty = max(
            [_qty(row, "planned_qty_after_lot_rule") for row in ordered_rows]
            + [_qty(row, "planned_qty_before") for row in ordered_rows]
            + [_qty(row, "campaign_remaining_start_qty") for row in ordered_rows],
            default=0.0,
        )
        requested_qty = max(
            [_qty(row, "campaign_requested_qty") for row in ordered_rows]
            + [_qty(row, "planned_qty_after_lot_rule") for row in ordered_rows]
            + [_qty(row, "planned_qty_before") for row in ordered_rows]
            + [_qty(row, "campaign_remaining_start_qty") for row in ordered_rows],
            default=0.0,
        )
        started_qty = max((_qty(row, "campaign_started_qty") for row in ordered_rows), default=0.0)
        if requested_qty > planned_qty:
            planned_qty = requested_qty
        requested_lot_starts = max((_qty(row, "requested_lot_starts") for row in ordered_rows), default=0.0)
        actual_lot_starts = sum(_qty(row, "actual_lot_starts") for row in ordered_rows)
        actual_qty = (
            release_evidence_qty
            if release_evidence_qty > LOT_TRACE_EPS
            else sum(_qty(row, "actual_qty") for row in run_rows)
        )
        max_shortfall = max((_qty(row, "shortfall_vs_lot_plan_qty") for row in delay_rows), default=0.0)
        repeated_shortfall = sum(_qty(row, "shortfall_vs_lot_plan_qty") for row in delay_rows)
        delay_days = sorted({_as_day(row) for row in delay_rows})
        if campaign_complete and delay_rows:
            status = "completed_after_delay"
            status_label = "Produit apres report"
        elif campaign_complete:
            status = "completed_without_delay"
            status_label = "Produit sans report"
        elif release_evidence_rows and delay_rows:
            status = "partially_released_blocked"
            status_label = "Partiellement libere, campagne encore contrainte"
        elif release_evidence_rows:
            status = "partially_released_in_progress"
            status_label = "Partiellement libere, campagne en cours"
        elif run_rows and delay_rows:
            status = "in_progress_delayed"
            status_label = "Encours de fabrication contraint"
        elif run_rows:
            status = "in_progress_wip"
            status_label = "Encours de fabrication"
        elif delay_rows:
            status = "still_blocked" if record_type_by_campaign.get(campaign_id) == "campaign" else "not_started_blocked"
            status_label = "Toujours bloque" if status == "still_blocked" else "Ordre non lance"
        else:
            status = "planned_without_output"
            status_label = "Plan sans lot produit"
        delay_reasons = sorted({str(row.get("reason") or "") for row in delay_rows if str(row.get("reason") or "")})
        lot_policy_modes = sorted({str(row.get("lot_policy_mode") or "") for row in ordered_rows if str(row.get("lot_policy_mode") or "")})
        binding_inputs = sorted(
            {str(row.get("binding_input_item_id") or "") for row in delay_rows if str(row.get("binding_input_item_id") or "")}
        )
        next_receipts = sorted(
            {
                str(int(round(_to_float(row.get("next_expected_receipt_day"), 0.0))))
                for row in delay_rows
                if str(row.get("next_expected_receipt_day") or "").strip()
            },
            key=lambda value: int(value),
        )
        delay_span_days = (
            int(last_delay_day) - int(first_delay_day) + 1
            if first_delay_day != "" and last_delay_day != ""
            else 0
        )
        semantics_versions = sorted(
            {
                str(row.get("semantics_version") or "")
                for row in ordered_rows
                if str(row.get("semantics_version") or "")
            }
        )
        semantics_version = "|".join(semantics_versions) or "legacy-daily-output"
        process_tau_days = max((_qty(row, "process_tau_days") for row in ordered_rows), default=0.0)
        release_gate_modes = sorted(
            {
                str(row.get("release_gate_mode") or "")
                for row in ordered_rows
                if str(row.get("release_gate_mode") or "")
            }
        )
        release_gate_mode = "|".join(release_gate_modes) or "legacy_daily_output"
        notes = (
            "daily actual_qty is executed work; completed lots are released physical stock; "
            "shortfall fields are daily planning signals; blocked_lot_qty counts the delayed batch once"
        )
        if lot_trace_available:
            notes += "; release_evidence=lot_trace_production_output"
        else:
            notes += (
                "; release_evidence=production_plan_released_batch; "
                "compact evidence has no physical lot identifier or genealogy"
            )
        if record_type_by_campaign.get(campaign_id) == "order_request":
            notes = "order request blocked before campaign creation; " + notes
        blocked_lot_qty = max_shortfall
        if status in {"still_blocked", "not_started_blocked"}:
            blocked_lot_qty = max(blocked_lot_qty, requested_qty, planned_qty)
        out.append(
            {
                "campaign_id": campaign_id,
                "record_type": record_type_by_campaign.get(campaign_id, "campaign"),
                "semantics_version": semantics_version,
                "node_id": str(first_row.get("node_id") or ""),
                "output_item_id": str(first_row.get("output_item_id") or ""),
                "process_tau_days": round(process_tau_days, 6),
                "release_gate_mode": release_gate_mode,
                "status": status,
                "status_label": status_label,
                "campaign_started_day": campaign_started_day,
                "first_event_day": first_event_day,
                "first_execution_day": first_execution_day,
                "last_execution_day": last_execution_day,
                "first_delay_day": first_delay_day,
                "last_delay_day": last_delay_day,
                "last_release_day": last_release_day,
                "completed_day": completed_day,
                "completion_basis": completion_basis,
                "delay_event_count": len(delay_rows),
                "delay_day_count": len(delay_days),
                "delay_span_days": delay_span_days,
                "event_count": len(ordered_rows),
                "planned_qty": round(planned_qty, 6),
                "requested_qty": round(requested_qty, 6),
                "started_qty": round(started_qty, 6),
                "actual_qty": round(actual_qty, 6),
                "remaining_qty": round(remaining_qty, 6),
                "wip_qty": round(wip_qty, 6),
                "requested_lot_starts": round(requested_lot_starts, 6),
                "actual_lot_starts": round(actual_lot_starts, 6),
                "lot_policy_modes": "|".join(lot_policy_modes),
                "completed_lot_ids": "|".join(output_lot_ids),
                "completed_lot_qty": round(release_evidence_qty, 6),
                "released_batch_count": released_batch_count,
                "blocked_lot_qty": round(blocked_lot_qty, 6),
                "max_daily_shortfall_qty": round(max_shortfall, 6),
                "repeated_daily_shortfall_qty": round(repeated_shortfall, 6),
                "delay_reasons": "|".join(delay_reasons),
                "binding_input_item_ids": "|".join(binding_inputs),
                "next_expected_receipt_days": "|".join(next_receipts),
                "first_event_type": str(first_row.get("event_type") or ""),
                "last_event_type": str(ordered_rows[-1].get("event_type") or ""),
                "notes": notes,
            }
        )
    return sorted(
        out,
        key=lambda row: (
            int(row["first_delay_day"]) if row["first_delay_day"] != "" else int(row["first_event_day"] or 0),
            str(row["campaign_id"]),
        ),
    )


def deferred_orders_from_campaign_rows(
    campaign_rows: list[dict[str, Any]],
    *,
    visible_finished_product_items: set[str] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    visible_items = visible_finished_product_items or set()
    for row in campaign_rows:
        status = str(row.get("status") or "")
        if status not in {
            "completed_after_delay",
            "still_blocked",
            "not_started_blocked",
            "partially_released_blocked",
            "in_progress_delayed",
        }:
            continue
        output_item = str(row.get("output_item_id") or "")
        if visible_items and output_item not in visible_items:
            continue
        campaign_id = str(row.get("campaign_id") or "")
        if not campaign_id:
            continue
        completed_lots = [
            lot_id
            for lot_id in str(row.get("completed_lot_ids") or "").split("|")
            if lot_id
        ]
        blocking_inputs = [
            item_id
            for item_id in str(row.get("binding_input_item_ids") or "").split("|")
            if item_id
        ]
        receipt_days = [
            int(round(_to_float(day, 0.0)))
            for day in str(row.get("next_expected_receipt_days") or "").split("|")
            if str(day).strip()
        ]
        first_delay = row.get("first_delay_day")
        last_delay = row.get("last_delay_day")
        completed_day = row.get("completed_day")
        label = (
            f"[ORDRE REPORTE] {campaign_id} | J{first_delay}->{completed_day if completed_day != '' else last_delay} "
            f"| {row.get('node_id') or ''} {output_item} | {_to_float(row.get('planned_qty'), 0.0):.1f}"
        )
        out.append(
            {
                "entity_type": "deferred_production_order",
                "selection_id": f"order:{campaign_id}",
                "campaign_id": campaign_id,
                "record_type": str(row.get("record_type") or "campaign"),
                "label": label,
                "status": status,
                "status_label": str(row.get("status_label") or ""),
                "node_id": str(row.get("node_id") or ""),
                "output_item_id": output_item,
                "first_delay_day": first_delay,
                "last_delay_day": last_delay,
                "delay_days": int(_to_float(row.get("delay_day_count"), 0.0)),
                "delay_span_days": int(_to_float(row.get("delay_span_days"), 0.0)),
                "planned_qty": round(_to_float(row.get("planned_qty"), 0.0), 6),
                "actual_completion_qty": round(_to_float(row.get("actual_qty"), 0.0), 6),
                "blocked_lot_qty": round(_to_float(row.get("blocked_lot_qty"), 0.0), 6),
                "repeated_daily_shortfall_qty": round(_to_float(row.get("repeated_daily_shortfall_qty"), 0.0), 6),
                "blocking_input_item_ids": blocking_inputs,
                "next_expected_receipt_days": receipt_days,
                "completed_day": completed_day,
                "completed_lot_id": completed_lots[0] if completed_lots else "",
                "completed_lot_ids": completed_lots,
                "completed_lot_qty": round(_to_float(row.get("completed_lot_qty"), 0.0), 6),
                "event_count": int(_to_float(row.get("event_count"), 0.0)),
                "delay_event_count": int(_to_float(row.get("delay_event_count"), 0.0)),
            }
        )
    return sorted(
        out,
        key=lambda row: (
            int(_to_float(row.get("first_delay_day"), 0.0)),
            str(row.get("campaign_id") or ""),
        ),
    )
