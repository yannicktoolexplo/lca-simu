"""Lot-level delta reports between a replayed baseline and one scenario."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from etudecas.simulation.lot_trace.causality import join_ids


LOT_DELTA_FIELDS = [
    "scenario_id",
    "baseline_reference_id",
    "planned_order_id",
    "node_id",
    "output_item_id",
    "comparison_status",
    "matching_basis",
    "matching_confidence",
    "baseline_status",
    "scenario_status",
    "baseline_first_event_day",
    "scenario_first_event_day",
    "baseline_completed_day",
    "scenario_completed_day",
    "production_shift_days",
    "baseline_delay_days",
    "scenario_delay_days",
    "baseline_produced_qty",
    "scenario_produced_qty",
    "scenario_completed_lot_ids",
    "scenario_shipment_ids",
    "scenario_first_arrival_day",
    "scenario_last_arrival_day",
    "scenario_customer_service_qty",
    "scenario_first_customer_service_day",
    "scenario_last_customer_service_day",
    "baseline_replacement_details_json",
    "scenario_replacement_details_json",
    "replacement_delta_details_json",
    "replacement_transitions",
    "causal_event_ids",
    "causal_root_ids",
    "causal_status",
    "delayed",
    "rescheduled",
    "substituted",
    "served_to_customer",
    "delivery_semantics",
]

SUPPLY_ORDER_DELTA_FIELDS = [
    "scenario_id",
    "baseline_reference_id",
    "baseline_mrp_order_id",
    "scenario_mrp_order_id",
    "mrp_order_id",
    "comparison_status",
    "matching_basis",
    "matching_confidence",
    "matched_qty",
    "order_shape_changed",
    "source_mode",
    "src_node_id",
    "dst_node_id",
    "item_id",
    "baseline_release_day",
    "scenario_release_day",
    "release_shift_days",
    "baseline_arrival_day",
    "scenario_arrival_day",
    "arrival_shift_days",
    "baseline_receipt_qty",
    "scenario_receipt_qty",
    "receipt_qty_delta",
    "scenario_shipment_id",
    "scenario_received_lot_ids",
    "causal_event_ids",
    "causal_root_ids",
    "delayed",
    "rescheduled",
    "quantity_changed",
    "physical_trace_semantics",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _day(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


def _reference(row: dict[str, Any]) -> str:
    origin_ids = [
        value
        for value in str(row.get("origin_production_order_ids") or "").split("|")
        if value
    ]
    if len(origin_ids) == 1:
        return origin_ids[0]
    return str(
        row.get("baseline_reference_id")
        or row.get("planned_order_id")
        or row.get("campaign_id")
        or ""
    ).strip()


def _origin_contributions(row: dict[str, Any]) -> dict[str, float]:
    raw = str(row.get("origin_production_contributions_json") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            return {
                str(order_id): max(0.0, _float(qty))
                for order_id, qty in parsed.items()
                if str(order_id).strip() and max(0.0, _float(qty)) > 0.0
            }
    reference = _reference(row)
    return {reference: max(0.0, _float(row.get("qty")))} if reference else {}


def _campaign_index(run_dir: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in _read_csv(run_dir / "data" / "production_campaigns.csv"):
        reference = _reference(row)
        if reference:
            out[reference] = row
    return out


def _mrp_orders_by_scope(
    run_dir: Path,
) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    out: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(run_dir / "data" / "mrp_orders_daily.csv"):
        scope = (
            str(row.get("order_type") or ""),
            str(row.get("src_node_id") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
        )
        out[scope].append(row)
    for rows in out.values():
        rows.sort(
            key=lambda row: (
                _day(row.get("release_day"))
                if _day(row.get("release_day")) is not None
                else 10**9,
                _day(row.get("arrival_day"))
                if _day(row.get("arrival_day")) is not None
                else 10**9,
                str(row.get("mrp_order_id") or ""),
            )
        )
    return out


def _received_lots_by_order(run_dir: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in _read_csv(run_dir / "data" / "production_lot_events.csv"):
        if str(row.get("event_type") or "") != "lane_receipt":
            continue
        order_id = str(
            row.get("baseline_reference_id")
            or row.get("planned_order_id")
            or ""
        ).strip()
        lot_id = str(row.get("business_batch_id") or row.get("lot_id") or "").strip()
        if order_id and lot_id:
            out[order_id].add(lot_id)
    return out


def _lot_evidence_by_reference(run_dir: Path) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "shipment_ids": set(),
            "arrival_days": [],
            "customer_service_qty": 0.0,
            "customer_service_days": [],
            "causal_event_ids": "",
            "causal_root_ids": "",
        }
    )
    for row in _read_csv(run_dir / "data" / "production_lot_events.csv"):
        contributions = _origin_contributions(row)
        if not contributions:
            continue
        for reference, contribution_qty in contributions.items():
            current = evidence[reference]
            shipment_id = str(row.get("shipment_id") or "").strip()
            if shipment_id:
                current["shipment_ids"].add(shipment_id)
            arrival_day = _day(row.get("arrival_day"))
            if arrival_day is not None and str(row.get("event_type") or "") == "lane_receipt":
                current["arrival_days"].append(arrival_day)
            if str(row.get("event_type") or "") == "demand_service":
                current["customer_service_qty"] += contribution_qty
                service_day = _day(row.get("day"))
                if service_day is not None:
                    current["customer_service_days"].append(service_day)
            current["causal_event_ids"] = join_ids(
                current["causal_event_ids"],
                row.get("causal_event_ids"),
            )
            current["causal_root_ids"] = join_ids(
                current["causal_root_ids"],
                row.get("causal_root_ids"),
            )
    return evidence


def _substitutions_by_reference(run_dir: Path) -> dict[str, dict[str, float]]:
    substitutions: dict[str, dict[str, Any]] = defaultdict(
        lambda: defaultdict(float)
    )
    for row in _read_csv(run_dir / "data" / "production_lot_genealogy.csv"):
        reference = _reference(row)
        transition = str(row.get("replacement_transition_id") or "").strip()
        if not reference or not transition:
            continue
        required_item = str(row.get("required_item_id") or "").strip()
        consumed_item = str(row.get("consumed_item_id") or "").strip()
        unit = str(row.get("parent_uom") or row.get("uom") or "").strip()
        detail_key = "|".join((transition, required_item, consumed_item, unit))
        substitutions[reference][detail_key] += max(0.0, _float(row.get("replacement_qty")))
    return {reference: dict(details) for reference, details in substitutions.items()}


def _substitution_deltas(
    baseline: dict[str, float],
    scenario: dict[str, float],
) -> dict[str, float]:
    return {
        key: round(scenario.get(key, 0.0) - baseline.get(key, 0.0), 6)
        for key in sorted(set(baseline) | set(scenario))
        if abs(scenario.get(key, 0.0) - baseline.get(key, 0.0)) > 1e-9
    }


def build_lot_delta_rows(
    *,
    baseline_run_dir: Path,
    scenario_run_dir: Path,
    scenario_id: str,
) -> list[dict[str, Any]]:
    """Compare stable production intents and their downstream lot outcomes."""

    baseline_campaigns = _campaign_index(baseline_run_dir)
    scenario_campaigns = _campaign_index(scenario_run_dir)
    scenario_evidence = _lot_evidence_by_reference(scenario_run_dir)
    baseline_substitutions = _substitutions_by_reference(baseline_run_dir)
    scenario_substitutions = _substitutions_by_reference(scenario_run_dir)
    rows: list[dict[str, Any]] = []

    for reference in sorted(set(baseline_campaigns) | set(scenario_campaigns)):
        baseline = baseline_campaigns.get(reference, {})
        scenario = scenario_campaigns.get(reference, {})
        evidence = scenario_evidence.get(reference, {})
        baseline_replacements = baseline_substitutions.get(reference, {})
        scenario_replacements = scenario_substitutions.get(reference, {})
        replacement_deltas = _substitution_deltas(
            baseline_replacements,
            scenario_replacements,
        )
        if baseline and scenario:
            comparison_status = "matched"
        elif scenario:
            comparison_status = "scenario_only"
        else:
            comparison_status = "baseline_only"

        baseline_completed = _day(baseline.get("completed_day"))
        scenario_completed = _day(scenario.get("completed_day"))
        production_shift = (
            scenario_completed - baseline_completed
            if baseline_completed is not None and scenario_completed is not None
            else ""
        )
        baseline_delay_days = int(round(_float(baseline.get("delay_day_count"))))
        scenario_delay_days = int(round(_float(scenario.get("delay_day_count"))))
        scenario_status = str(scenario.get("status") or "")
        event_ids = join_ids(
            scenario.get("causal_event_ids"),
            evidence.get("causal_event_ids"),
        )
        root_ids = join_ids(
            scenario.get("causal_root_ids"),
            evidence.get("causal_root_ids"),
        )
        arrival_days = list(evidence.get("arrival_days") or [])
        service_days = list(evidence.get("customer_service_days") or [])
        baseline_blocked = str(baseline.get("status") or "") in {
            "still_blocked",
            "not_started_blocked",
            "planned_without_output",
        }
        scenario_blocked = scenario_status in {
            "still_blocked",
            "not_started_blocked",
            "planned_without_output",
        }
        rows.append(
            {
                "scenario_id": scenario_id,
                "baseline_reference_id": reference,
                "planned_order_id": str(
                    scenario.get("planned_order_id")
                    or baseline.get("planned_order_id")
                    or reference
                ),
                "node_id": str(scenario.get("node_id") or baseline.get("node_id") or ""),
                "output_item_id": str(
                    scenario.get("output_item_id") or baseline.get("output_item_id") or ""
                ),
                "comparison_status": comparison_status,
                "matching_basis": "node_item_production_sequence_ordinal",
                "matching_confidence": (
                    "stable_sequence_match"
                    if comparison_status == "matched"
                    else "unmatched_intent"
                ),
                "baseline_status": str(baseline.get("status") or ""),
                "scenario_status": scenario_status,
                "baseline_first_event_day": baseline.get("first_event_day", ""),
                "scenario_first_event_day": scenario.get("first_event_day", ""),
                "baseline_completed_day": baseline.get("completed_day", ""),
                "scenario_completed_day": scenario.get("completed_day", ""),
                "production_shift_days": production_shift,
                "baseline_delay_days": baseline_delay_days,
                "scenario_delay_days": scenario_delay_days,
                "baseline_produced_qty": round(
                    max(0.0, _float(baseline.get("actual_qty"))),
                    6,
                ),
                "scenario_produced_qty": round(
                    max(0.0, _float(scenario.get("actual_qty"))),
                    6,
                ),
                "scenario_completed_lot_ids": str(scenario.get("completed_lot_ids") or ""),
                "scenario_shipment_ids": "|".join(sorted(evidence.get("shipment_ids") or set())),
                "scenario_first_arrival_day": min(arrival_days) if arrival_days else "",
                "scenario_last_arrival_day": max(arrival_days) if arrival_days else "",
                "scenario_customer_service_qty": round(
                    max(0.0, _float(evidence.get("customer_service_qty"))),
                    6,
                ),
                "scenario_first_customer_service_day": min(service_days) if service_days else "",
                "scenario_last_customer_service_day": max(service_days) if service_days else "",
                "baseline_replacement_details_json": json.dumps(
                    baseline_replacements,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "scenario_replacement_details_json": json.dumps(
                    scenario_replacements,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "replacement_delta_details_json": json.dumps(
                    replacement_deltas,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "replacement_transitions": "|".join(
                    sorted(
                        {
                            key.split("|", 1)[0]
                            for key in scenario_replacements
                            if key.split("|", 1)[0]
                        }
                    )
                ),
                "causal_event_ids": event_ids,
                "causal_root_ids": root_ids or event_ids,
                "causal_status": str(scenario.get("causal_status") or ""),
                "delayed": (
                    scenario_delay_days > baseline_delay_days
                    or (scenario_blocked and not baseline_blocked)
                ),
                "rescheduled": bool(
                    comparison_status == "matched"
                    and (
                        production_shift not in {"", 0}
                        or _day(scenario.get("first_event_day"))
                        != _day(baseline.get("first_event_day"))
                    )
                ),
                "substituted": bool(replacement_deltas),
                "served_to_customer": _float(evidence.get("customer_service_qty")) > 0.0,
                "delivery_semantics": "service_allocation_not_physical_delivery_proof",
            }
        )
    return rows


def build_supply_order_delta_rows(
    *,
    baseline_run_dir: Path,
    scenario_run_dir: Path,
    scenario_id: str,
) -> list[dict[str, Any]]:
    """Compare generated supply orders and their simulated physical receipts."""

    baseline_by_scope = _mrp_orders_by_scope(baseline_run_dir)
    scenario_by_scope = _mrp_orders_by_scope(scenario_run_dir)
    scenario_received_lots = _received_lots_by_order(scenario_run_dir)
    rows: list[dict[str, Any]] = []
    aligned_rows: list[tuple[dict[str, str], dict[str, str], float, str]] = []
    for scope in sorted(set(baseline_by_scope) | set(scenario_by_scope)):
        baseline_orders = baseline_by_scope.get(scope, [])
        scenario_orders = scenario_by_scope.get(scope, [])
        baseline_index = 0
        scenario_index = 0
        baseline_remaining = (
            max(0.0, _float(baseline_orders[0].get("planned_receipt_qty")))
            if baseline_orders
            else 0.0
        )
        scenario_remaining = (
            max(0.0, _float(scenario_orders[0].get("planned_receipt_qty")))
            if scenario_orders
            else 0.0
        )
        while baseline_index < len(baseline_orders) and scenario_index < len(scenario_orders):
            baseline = baseline_orders[baseline_index]
            scenario = scenario_orders[scenario_index]
            matched_qty = min(baseline_remaining, scenario_remaining)
            if matched_qty > 1e-9:
                aligned_rows.append((baseline, scenario, matched_qty, "matched"))
            baseline_remaining -= matched_qty
            scenario_remaining -= matched_qty
            if baseline_remaining <= 1e-9:
                baseline_index += 1
                if baseline_index < len(baseline_orders):
                    baseline_remaining = max(
                        0.0,
                        _float(
                            baseline_orders[baseline_index].get(
                                "planned_receipt_qty"
                            )
                        ),
                    )
            if scenario_remaining <= 1e-9:
                scenario_index += 1
                if scenario_index < len(scenario_orders):
                    scenario_remaining = max(
                        0.0,
                        _float(
                            scenario_orders[scenario_index].get(
                                "planned_receipt_qty"
                            )
                        ),
                    )
        if baseline_index < len(baseline_orders) and baseline_remaining > 1e-9:
            aligned_rows.append(
                (
                    baseline_orders[baseline_index],
                    {},
                    baseline_remaining,
                    "baseline_only",
                )
            )
            baseline_index += 1
        for baseline in baseline_orders[baseline_index:]:
            qty = max(0.0, _float(baseline.get("planned_receipt_qty")))
            if qty > 1e-9:
                aligned_rows.append((baseline, {}, qty, "baseline_only"))
        if scenario_index < len(scenario_orders) and scenario_remaining > 1e-9:
            aligned_rows.append(
                (
                    {},
                    scenario_orders[scenario_index],
                    scenario_remaining,
                    "scenario_only",
                )
            )
            scenario_index += 1
        for scenario in scenario_orders[scenario_index:]:
            qty = max(0.0, _float(scenario.get("planned_receipt_qty")))
            if qty > 1e-9:
                aligned_rows.append(({}, scenario, qty, "scenario_only"))

    for baseline, scenario, matched_qty, comparison_status in aligned_rows:
        baseline_order_id = str(baseline.get("mrp_order_id") or "").strip()
        scenario_order_id = str(scenario.get("mrp_order_id") or "").strip()
        reference = baseline_order_id or scenario_order_id
        baseline_release = _day(baseline.get("release_day"))
        scenario_release = _day(scenario.get("release_day"))
        baseline_arrival = _day(
            baseline.get("actual_receipt_day") or baseline.get("arrival_day")
        )
        scenario_arrival = _day(
            scenario.get("actual_receipt_day") or scenario.get("arrival_day")
        )
        release_shift = (
            scenario_release - baseline_release
            if baseline_release is not None and scenario_release is not None
            else ""
        )
        arrival_shift = (
            scenario_arrival - baseline_arrival
            if baseline_arrival is not None and scenario_arrival is not None
            else ""
        )
        baseline_qty = max(0.0, _float(baseline.get("planned_receipt_qty")))
        scenario_qty = max(0.0, _float(scenario.get("planned_receipt_qty")))
        rows.append(
            {
                "scenario_id": scenario_id,
                "baseline_reference_id": reference,
                "baseline_mrp_order_id": baseline_order_id,
                "scenario_mrp_order_id": scenario_order_id,
                "mrp_order_id": scenario_order_id or baseline_order_id,
                "comparison_status": comparison_status,
                "matching_basis": "route_item_fifo_cumulative_quantity_overlap",
                "matching_confidence": (
                    "stable_generated_order_id"
                    if (
                        comparison_status == "matched"
                        and baseline_order_id
                        and baseline_order_id == scenario_order_id
                    )
                    else (
                        "quantity_overlap_reconstruction"
                        if comparison_status == "matched"
                        else "unmatched_order"
                    )
                ),
                "matched_qty": round(max(0.0, matched_qty), 6),
                "order_shape_changed": bool(
                    comparison_status != "matched"
                    or abs(baseline_qty - scenario_qty) > 1e-6
                    or abs(matched_qty - baseline_qty) > 1e-6
                    or abs(matched_qty - scenario_qty) > 1e-6
                ),
                "source_mode": str(
                    scenario.get("order_type") or baseline.get("order_type") or ""
                ),
                "src_node_id": str(
                    scenario.get("src_node_id") or baseline.get("src_node_id") or ""
                ),
                "dst_node_id": str(
                    scenario.get("dst_node_id") or baseline.get("dst_node_id") or ""
                ),
                "item_id": str(
                    scenario.get("item_id") or baseline.get("item_id") or ""
                ),
                "baseline_release_day": baseline.get("release_day", ""),
                "scenario_release_day": scenario.get("release_day", ""),
                "release_shift_days": release_shift,
                "baseline_arrival_day": (
                    baseline.get("actual_receipt_day")
                    or baseline.get("arrival_day", "")
                ),
                "scenario_arrival_day": (
                    scenario.get("actual_receipt_day")
                    or scenario.get("arrival_day", "")
                ),
                "arrival_shift_days": arrival_shift,
                "baseline_receipt_qty": round(baseline_qty, 6),
                "scenario_receipt_qty": round(scenario_qty, 6),
                "receipt_qty_delta": round(scenario_qty - baseline_qty, 6),
                "scenario_shipment_id": str(scenario.get("shipment_id") or ""),
                "scenario_received_lot_ids": "|".join(
                    sorted(scenario_received_lots.get(scenario_order_id) or set())
                ),
                "causal_event_ids": join_ids(scenario.get("causal_event_ids")),
                "causal_root_ids": (
                    join_ids(scenario.get("causal_root_ids"))
                    or join_ids(scenario.get("causal_event_ids"))
                ),
                "delayed": bool(
                    comparison_status == "matched"
                    and isinstance(arrival_shift, int)
                    and arrival_shift > 0
                ),
                "rescheduled": bool(
                    comparison_status == "matched"
                    and isinstance(release_shift, int)
                    and release_shift != 0
                ),
                "quantity_changed": bool(
                    comparison_status == "matched"
                    and baseline_order_id
                    and baseline_order_id == scenario_order_id
                    and abs(scenario_qty - baseline_qty) > 1e-6
                ),
                "physical_trace_semantics": (
                    "simulated_supply_order_dispatch_group_and_stock_receipt"
                ),
            }
        )
    return rows


def write_lot_delta_report(
    *,
    baseline_run_dir: Path,
    scenario_run_dir: Path,
    scenario_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    rows = build_lot_delta_rows(
        baseline_run_dir=baseline_run_dir,
        scenario_run_dir=scenario_run_dir,
        scenario_id=scenario_id,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(char if char.isalnum() else "_" for char in scenario_id).strip("_")
    safe_id = safe_id or "scenario"
    csv_path = output_dir / f"lot_delta_{safe_id}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOT_DELTA_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    supply_order_rows = build_supply_order_delta_rows(
        baseline_run_dir=baseline_run_dir,
        scenario_run_dir=scenario_run_dir,
        scenario_id=scenario_id,
    )
    supply_order_csv_path = output_dir / f"supply_order_delta_{safe_id}.csv"
    with supply_order_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUPPLY_ORDER_DELTA_FIELDS)
        writer.writeheader()
        writer.writerows(supply_order_rows)
    delayed_supply_order_ids = {
        str(row["scenario_mrp_order_id"])
        for row in supply_order_rows
        if row["delayed"] and str(row["scenario_mrp_order_id"])
    }
    rescheduled_supply_order_ids = {
        str(row["scenario_mrp_order_id"])
        for row in supply_order_rows
        if row["rescheduled"] and str(row["scenario_mrp_order_id"])
    }
    changed_supply_order_ids = {
        str(row["scenario_mrp_order_id"])
        for row in supply_order_rows
        if row["quantity_changed"] and str(row["scenario_mrp_order_id"])
    }
    causally_attributed_supply_order_ids = {
        str(row["scenario_mrp_order_id"])
        for row in supply_order_rows
        if row["causal_root_ids"] and str(row["scenario_mrp_order_id"])
    }
    summary = {
        "scenario_id": scenario_id,
        "row_count": len(rows),
        "matched_orders": sum(row["comparison_status"] == "matched" for row in rows),
        "baseline_only_orders": sum(row["comparison_status"] == "baseline_only" for row in rows),
        "scenario_only_orders": sum(row["comparison_status"] == "scenario_only" for row in rows),
        "delayed_orders": sum(bool(row["delayed"]) for row in rows),
        "rescheduled_orders": sum(bool(row["rescheduled"]) for row in rows),
        "substituted_orders": sum(bool(row["substituted"]) for row in rows),
        "orders_served_to_customer": sum(bool(row["served_to_customer"]) for row in rows),
        "causally_attributed_orders": sum(bool(row["causal_root_ids"]) for row in rows),
        "supply_order_rows": len(supply_order_rows),
        "supply_order_comparison_segments": len(supply_order_rows),
        "matched_supply_order_segments": sum(
            row["comparison_status"] == "matched" for row in supply_order_rows
        ),
        "reconstructed_supply_order_segments": sum(
            row["matching_confidence"] == "quantity_overlap_reconstruction"
            for row in supply_order_rows
        ),
        "delayed_supply_orders": len(delayed_supply_order_ids),
        "delayed_supply_qty": round(
            sum(
                _float(row["matched_qty"])
                for row in supply_order_rows
                if row["delayed"]
            ),
            6,
        ),
        "rescheduled_supply_orders": len(rescheduled_supply_order_ids),
        "changed_supply_order_quantities": len(changed_supply_order_ids),
        "causally_attributed_supply_orders": len(
            causally_attributed_supply_order_ids
        ),
        "baseline_only_supply_qty": round(
            sum(
                _float(row["matched_qty"])
                for row in supply_order_rows
                if row["comparison_status"] == "baseline_only"
            ),
            6,
        ),
        "scenario_only_supply_qty": round(
            sum(
                _float(row["matched_qty"])
                for row in supply_order_rows
                if row["comparison_status"] == "scenario_only"
            ),
            6,
        ),
        "supply_order_matching_note": (
            "Stable generated order IDs are exact. Split or merged orders are "
            "reconstructed by route, item and FIFO cumulative quantity overlap."
        ),
        "csv": str(csv_path),
        "supply_order_csv": str(supply_order_csv_path),
        "delivery_semantics": "Customer service is a stock allocation to demand, not proof of carrier delivery.",
    }
    json_path = output_dir / f"lot_delta_{safe_id}.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary["json"] = str(json_path)
    return summary


__all__ = [
    "LOT_DELTA_FIELDS",
    "SUPPLY_ORDER_DELTA_FIELDS",
    "build_lot_delta_rows",
    "build_supply_order_delta_rows",
    "write_lot_delta_report",
]
