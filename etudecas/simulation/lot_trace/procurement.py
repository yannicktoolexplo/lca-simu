from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Any, Iterable


PROCUREMENT_TRACE_FIELDS = (
    "mrp_order_id",
    "order_day",
    "mrp_decision_day",
    "requested_release_day",
    "planned_release_day",
    "actual_release_day",
    "estimated_release_day",
    "planned_arrival_day",
    "actual_receipt_day",
    "procurement_lead_days",
    "procurement_lead_basis",
    "procurement_status",
    "supplier_node_id",
    "procurement_destination_node_id",
    "procurement_edge_id",
    "procurement_trace_status",
    "procurement_trace_reason",
)


def enrich_lot_trace_with_procurement(
    events: list[dict[str, Any]],
    genealogy: list[dict[str, Any]],
    mrp_order_rows: Iterable[dict[str, Any]],
    supply_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Join procurement orders to lot movements without inventing source facts.

    The engine keeps MRP orders and physical lot movements in separate tables.
    This function creates the presentation join used by the lot-trace payload:
    - lane shipments are matched on supplier, item, route and release day;
    - lane receipts are matched on destination, item and receipt day;
    - transport genealogy inherits the order attached to its child receipt.

    Opening stock is intentionally left as pre-horizon and untraced.
    """

    orders = normalize_procurement_orders(mrp_order_rows)
    lane_index = _build_lane_index(supply_graph)
    if not orders and not lane_index["by_edge"]:
        return {
            "orders": [],
            "summary": {
                "order_count": 0,
                "matched_lot_event_count": 0,
                "matched_transport_link_count": 0,
                "unmatched_lane_receipt_count": 0,
                "inferred_aggregate_receipt_count": 0,
                "opening_stock_policy": (
                    "Stock initial: approvisionnement anterieur a J0 non date "
                    "si aucun ordre source n'est disponible."
                ),
            },
        }
    matcher = _ProcurementMatcher(orders)
    receipt_procurement_by_lot: dict[str, dict[str, Any]] = {}
    matched_event_count = 0
    unmatched_receipt_count = 0
    inferred_aggregate_receipt_count = 0

    ordered_events = sorted(
        events,
        key=lambda row: (
            _to_int(row.get("day"), 0),
            str(row.get("event_id") or ""),
        ),
    )
    for event in ordered_events:
        event_type = str(event.get("event_type") or "")
        if event_type not in {"lane_ship", "lane_receipt"}:
            continue
        order = matcher.match(event, event_type=event_type)
        if order:
            _copy_procurement_fields(event, order)
            matched_event_count += 1
            if event_type == "lane_receipt":
                lot_id = str(event.get("lot_id") or "")
                if lot_id:
                    receipt_procurement_by_lot[lot_id] = event
            continue
        if event_type == "lane_receipt":
            lane = _match_lane(event, lane_index)
            if lane:
                _copy_aggregate_lane_fields(event, lane)
                lot_id = str(event.get("lot_id") or "")
                if lot_id:
                    receipt_procurement_by_lot[lot_id] = event
                inferred_aggregate_receipt_count += 1
                continue
        event["procurement_trace_status"] = (
            "receipt_without_matching_order"
            if event_type == "lane_receipt"
            else "shipment_without_matching_order"
        )
        event["procurement_trace_reason"] = (
            "no_mrp_order_matches_item_route_day_and_quantity"
        )
        if event_type == "lane_receipt":
            unmatched_receipt_count += 1

    matched_link_count = 0
    for link in genealogy:
        if str(link.get("link_type") or "") != "transport":
            continue
        child_lot_id = str(link.get("child_lot_id") or "")
        order = receipt_procurement_by_lot.get(child_lot_id)
        if order is None:
            order = matcher.match(
                link,
                event_type="lane_receipt",
                consume=False,
            )
        if order:
            _copy_procurement_fields(link, order)
            matched_link_count += 1
        else:
            link["procurement_trace_status"] = "transport_without_matching_order"
            link["procurement_trace_reason"] = (
                "no_mrp_order_matches_item_route_day_and_quantity"
            )

    return {
        "orders": orders,
        "summary": {
            "order_count": len(orders),
            "matched_lot_event_count": matched_event_count,
            "matched_transport_link_count": matched_link_count,
            "unmatched_lane_receipt_count": unmatched_receipt_count,
            "inferred_aggregate_receipt_count": inferred_aggregate_receipt_count,
            "opening_stock_policy": (
                "Stock initial: approvisionnement anterieur a J0 non date "
                "si aucun ordre source n'est disponible."
            ),
        },
    }


def _build_lane_index(
    supply_graph: dict[str, Any] | None,
) -> dict[str, Any]:
    by_edge: dict[str, dict[str, Any]] = {}
    by_destination_item: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in (supply_graph or {}).get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        edge_id = str(edge.get("id") or "").strip()
        source = str(edge.get("from") or edge.get("src") or "").strip()
        destination = str(edge.get("to") or edge.get("dst") or "").strip()
        lead_time = edge.get("lead_time") or {}
        if isinstance(lead_time, dict):
            lead_days = _optional_int(
                lead_time.get("mean")
                if lead_time.get("mean") not in {"", None}
                else lead_time.get("value")
            )
        else:
            lead_days = _optional_int(lead_time)
        items = edge.get("items") or []
        if not isinstance(items, list):
            items = [items]
        for item in items:
            item_id = str(item or "").strip()
            if not item_id:
                continue
            lane = {
                "edge_id": edge_id,
                "supplier_node_id": source,
                "destination_node_id": destination,
                "item_id": item_id,
                "lead_days": lead_days,
                "lead_time_basis": (
                    str(lead_time.get("source") or "supply_graph")
                    if isinstance(lead_time, dict)
                    else "supply_graph"
                ),
            }
            if edge_id:
                by_edge[edge_id] = lane
            by_destination_item[(destination, item_id)].append(lane)
    return {
        "by_edge": by_edge,
        "by_destination_item": by_destination_item,
    }


def _match_lane(
    event: dict[str, Any],
    lane_index: dict[str, Any],
) -> dict[str, Any] | None:
    source_id = str(event.get("source_id") or "")
    by_edge = lane_index.get("by_edge") or {}
    if source_id and source_id in by_edge:
        return by_edge[source_id]
    key = (
        str(event.get("node_id") or ""),
        str(event.get("item_id") or ""),
    )
    candidates = (lane_index.get("by_destination_item") or {}).get(key, [])
    return candidates[0] if len(candidates) == 1 else None


def _copy_aggregate_lane_fields(
    event: dict[str, Any],
    lane: dict[str, Any],
) -> None:
    receipt_day = _optional_int(event.get("day"))
    lead_days = _optional_int(lane.get("lead_days"))
    event.update(
        {
            "order_day": None,
            "mrp_decision_day": None,
            "requested_release_day": None,
            "planned_release_day": None,
            "actual_release_day": None,
            "estimated_release_day": (
                receipt_day - lead_days
                if receipt_day is not None and lead_days is not None
                else None
            ),
            "planned_arrival_day": None,
            "actual_receipt_day": receipt_day,
            "procurement_lead_days": lead_days,
            "procurement_lead_basis": str(
                lane.get("lead_time_basis") or "supply_graph"
            ),
            "procurement_status": "reapprovisionnement_agrege_recu",
            "supplier_node_id": str(lane.get("supplier_node_id") or ""),
            "procurement_destination_node_id": str(
                lane.get("destination_node_id") or event.get("node_id") or ""
            ),
            "procurement_edge_id": str(
                lane.get("edge_id") or event.get("source_id") or ""
            ),
            "procurement_trace_status": "aggregate_replenishment_inferred_timeline",
            "procurement_trace_reason": (
                "supplier_and_departure_inferred_from_lane_nominal_lead;"
                "individual_mrp_order_unavailable"
            ),
        }
    )


def normalize_procurement_orders(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    duplicate_count_by_signature: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("item_id") or "").strip()
        destination = str(
            row.get("dst_node_id") or row.get("node_id") or ""
        ).strip()
        if not item_id or not destination:
            continue
        source = str(row.get("src_node_id") or "").strip()
        edge_id = str(row.get("edge_id") or "").strip()
        decision_day = _optional_int(row.get("day"))
        requested_release_day = _optional_int(row.get("order_date_imt"))
        release_day = _optional_int(row.get("release_day"))
        planned_arrival_day = _optional_int(row.get("arrival_day"))
        actual_receipt_day = _optional_int(row.get("actual_receipt_day"))
        lead_days = _optional_int(row.get("lead_days"))
        release_qty = _to_float(row.get("release_qty"))
        receipt_qty = _to_float(row.get("planned_receipt_qty"))
        status = str(
            row.get("order_status_end_of_run")
            or row.get("receipt_status")
            or row.get("release_status")
            or ""
        ).strip()
        signature_payload = {
            "order_type": str(row.get("order_type") or ""),
            "source": source,
            "destination": destination,
            "item": item_id,
            "edge": edge_id,
            "decision_day": decision_day,
            "requested_release_day": requested_release_day,
            "release_day": release_day,
            "planned_arrival_day": planned_arrival_day,
            "actual_receipt_day": actual_receipt_day,
            "release_qty": round(release_qty, 6),
            "receipt_qty": round(receipt_qty, 6),
        }
        signature = json.dumps(
            signature_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        duplicate_count_by_signature[signature] += 1
        occurrence = duplicate_count_by_signature[signature]
        digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:12].upper()
        order_id = str(row.get("mrp_order_id") or "").strip()
        if not order_id:
            order_id = f"MRPORD-{digest}"
            if occurrence > 1:
                order_id = f"{order_id}-{occurrence}"
        normalized.append(
            {
                "mrp_order_id": order_id,
                "order_type": str(row.get("order_type") or ""),
                "order_day": decision_day,
                "mrp_decision_day": decision_day,
                "requested_release_day": requested_release_day,
                "planned_release_day": release_day,
                "actual_release_day": release_day,
                "estimated_release_day": None,
                "planned_arrival_day": planned_arrival_day,
                "actual_receipt_day": actual_receipt_day,
                "procurement_lead_days": lead_days,
                "procurement_lead_basis": "mrp_orders_daily",
                "procurement_status": status,
                "supplier_node_id": source,
                "procurement_destination_node_id": destination,
                "item_id": item_id,
                "procurement_edge_id": edge_id,
                "release_qty": round(release_qty, 6),
                "planned_receipt_qty": round(receipt_qty, 6),
                "uom": str(row.get("uom") or ""),
                "procurement_trace_status": "mrp_order_matched",
                "procurement_trace_reason": "joined_from_mrp_orders_daily",
            }
        )
    return normalized


class _ProcurementMatcher:
    def __init__(self, orders: list[dict[str, Any]]) -> None:
        self.orders = orders
        self.by_item: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.assigned_qty: dict[tuple[str, str], float] = defaultdict(float)
        self.assigned_zero_qty: set[tuple[str, str]] = set()
        for order in orders:
            self.by_item[str(order.get("item_id") or "")].append(order)

    def match(
        self,
        movement: dict[str, Any],
        *,
        event_type: str,
        consume: bool = True,
    ) -> dict[str, Any] | None:
        item_id = str(
            movement.get("item_id")
            or movement.get("child_item_id")
            or movement.get("parent_item_id")
            or ""
        )
        if not item_id:
            return None
        candidates = self.by_item.get(item_id, [])
        if not candidates:
            return None
        movement_day = _optional_int(
            movement.get("day")
            if event_type == "lane_receipt"
            else movement.get("departure_day", movement.get("day"))
        )
        movement_node = str(
            movement.get("node_id")
            or (
                movement.get("child_node_id")
                if event_type == "lane_receipt"
                else movement.get("parent_node_id")
            )
            or ""
        )
        movement_edge = str(
            movement.get("source_id")
            or movement.get("procurement_edge_id")
            or ""
        )
        movement_qty = _to_float(
            movement.get("qty")
            if movement.get("qty") not in {"", None}
            else (
                movement.get("child_qty")
                if event_type == "lane_receipt"
                else movement.get("parent_qty")
            )
        )

        scored: list[tuple[float, str, dict[str, Any]]] = []
        for order in candidates:
            expected_node = str(
                order.get("procurement_destination_node_id")
                if event_type == "lane_receipt"
                else order.get("supplier_node_id")
                or ""
            )
            if movement_node and expected_node and movement_node != expected_node:
                continue
            expected_day = (
                order.get("actual_receipt_day")
                if event_type == "lane_receipt"
                and order.get("actual_receipt_day") is not None
                else order.get("planned_arrival_day")
                if event_type == "lane_receipt"
                else order.get("planned_release_day")
            )
            day_distance = _distance(movement_day, expected_day, missing_penalty=5.0)
            if movement_day is not None and expected_day is not None and day_distance > 3:
                continue
            order_edge = str(order.get("procurement_edge_id") or "")
            if movement_edge and order_edge:
                if movement_edge != order_edge:
                    continue
            order_id = str(order.get("mrp_order_id") or "")
            assignment_key = (event_type, order_id)
            expected_qty = _to_float(
                order.get("planned_receipt_qty")
                if event_type == "lane_receipt"
                else order.get("release_qty")
            )
            qty_distance = 0.0
            if expected_qty > 0:
                residual_qty = max(
                    0.0,
                    expected_qty - self.assigned_qty[assignment_key],
                )
                qty_tolerance = max(1e-6, expected_qty * 1e-6)
                if consume and movement_qty > residual_qty + qty_tolerance:
                    continue
                qty_scale = max(abs(residual_qty), abs(movement_qty), 1.0)
                qty_distance = abs(residual_qty - movement_qty) / qty_scale
            elif consume and assignment_key in self.assigned_zero_qty:
                continue
            score = day_distance * 10.0 + qty_distance
            scored.append((score, str(order.get("mrp_order_id") or ""), order))
        if not scored:
            return None
        scored.sort(key=lambda entry: (entry[0], entry[1]))
        best_score, _, best_order = scored[0]
        if best_score >= 40.0:
            return None
        if consume:
            order_id = str(best_order.get("mrp_order_id") or "")
            assignment_key = (event_type, order_id)
            if movement_qty > 0:
                self.assigned_qty[assignment_key] += movement_qty
            else:
                self.assigned_zero_qty.add(assignment_key)
        return best_order


def _copy_procurement_fields(
    target: dict[str, Any],
    order: dict[str, Any],
) -> None:
    for field in PROCUREMENT_TRACE_FIELDS:
        target[field] = order.get(field)


def _distance(
    left: int | None,
    right: int | None,
    *,
    missing_penalty: float,
) -> float:
    if left is None or right is None:
        return missing_penalty
    return float(abs(left - right))


def _optional_int(value: Any) -> int | None:
    if value in {"", None}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return int(round(numeric))


def _to_int(value: Any, default: int = 0) -> int:
    parsed = _optional_int(value)
    return default if parsed is None else parsed


def _to_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(numeric) else numeric
