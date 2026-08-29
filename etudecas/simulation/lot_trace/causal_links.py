from __future__ import annotations

import json
from typing import Any, Iterable

from .causality import join_ids, split_ids


LOT_CAUSAL_LINK_FIELDS = [
    "scenario_id",
    "causal_root_id",
    "causal_event_ids",
    "causal_status",
    "relation_type",
    "entity_type",
    "entity_id",
    "parent_entity_type",
    "parent_entity_id",
    "day",
    "node_id",
    "item_id",
    "qty",
    "uom",
    "basis",
    "notes",
]


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _entity_causal_rows(
    rows: Iterable[dict[str, Any]],
    *,
    entity_type: str,
    entity_id_field: str,
    relation_type: str,
    item_field: str = "item_id",
    qty_field: str = "qty",
    parent_entity_type: str = "",
    parent_entity_field: str = "",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        event_ids = join_ids(row.get("causal_event_ids"))
        root_ids = split_ids(row.get("causal_root_ids")) or split_ids(event_ids)
        entity_id = str(row.get(entity_id_field) or "").strip()
        if not root_ids or not entity_id:
            continue
        for root_id in root_ids:
            out.append(
                {
                    "scenario_id": str(row.get("scenario_id") or ""),
                    "causal_root_id": root_id,
                    "causal_event_ids": event_ids,
                    "causal_status": str(row.get("causal_status") or ""),
                    "relation_type": relation_type,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "parent_entity_type": parent_entity_type,
                    "parent_entity_id": (
                        str(row.get(parent_entity_field) or "")
                        if parent_entity_field
                        else ""
                    ),
                    "day": row.get("day", row.get("first_event_day", "")),
                    "node_id": str(row.get("node_id") or row.get("dst_node_id") or ""),
                    "item_id": str(row.get(item_field) or ""),
                    "qty": round(max(0.0, _to_float(row.get(qty_field))), 6),
                    "uom": str(row.get("uom") or ""),
                    "basis": "explicit_simulation_causal_context",
                    "notes": str(row.get("notes") or ""),
                }
            )
    return out


def _lot_event_entity_rows(
    rows: Iterable[dict[str, Any]],
    *,
    event_types: set[str],
    entity_type: str,
    entity_id_field: str,
    relation_type: str,
) -> list[dict[str, Any]]:
    selected_rows: list[dict[str, Any]] = []
    for row in rows:
        event_type = str(row.get("event_type") or "").strip()
        if event_type not in event_types:
            continue
        entity_id = str(row.get(entity_id_field) or "").strip()
        if not entity_id:
            continue
        parent_ids = split_ids(row.get("origin_production_order_ids")) or [""]
        for parent_id in parent_ids:
            selected_rows.append(
                {
                    **row,
                    "_causal_entity_id": entity_id,
                    "_causal_parent_id": parent_id,
                    "notes": (
                        f"lot_event={event_type}; event_id={row.get('event_id', '')}; "
                        f"trace_status={row.get('trace_status', '')}"
                    ),
                }
            )
    return _entity_causal_rows(
        selected_rows,
        entity_type=entity_type,
        entity_id_field="_causal_entity_id",
        relation_type=relation_type,
        item_field="item_id",
        qty_field="qty",
        parent_entity_type="production_order",
        parent_entity_field="_causal_parent_id",
    )


def _origin_contributions(row: dict[str, Any]) -> dict[str, float]:
    raw = str(row.get("origin_production_contributions_json") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            return {
                str(order_id): max(0.0, _to_float(qty))
                for order_id, qty in parsed.items()
                if str(order_id).strip() and max(0.0, _to_float(qty)) > 0.0
            }
    order_ids = split_ids(row.get("origin_production_order_ids"))
    qty = max(0.0, _to_float(row.get("qty")))
    if len(order_ids) == 1 and qty > 0.0:
        return {order_ids[0]: qty}
    return {}


def _structural_row(
    row: dict[str, Any],
    *,
    relation_type: str,
    entity_type: str,
    entity_id: str,
    parent_entity_type: str,
    parent_entity_id: str,
    qty: float | None = None,
    basis: str,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "scenario_id": str(row.get("scenario_id") or ""),
        "causal_root_id": "",
        "causal_event_ids": join_ids(row.get("causal_event_ids")),
        "causal_status": str(row.get("causal_status") or ""),
        "relation_type": relation_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "parent_entity_type": parent_entity_type,
        "parent_entity_id": parent_entity_id,
        "day": row.get("day", row.get("first_event_day", "")),
        "node_id": str(row.get("node_id") or row.get("dst_node_id") or ""),
        "item_id": str(row.get("item_id") or row.get("output_item_id") or ""),
        "qty": round(
            max(0.0, _to_float(row.get("qty") if qty is None else qty)),
            6,
        ),
        "uom": str(row.get("uom") or ""),
        "basis": basis,
        "notes": notes,
    }


def build_lot_causal_link_rows(
    *,
    lot_event_rows: Iterable[dict[str, Any]],
    genealogy_rows: Iterable[dict[str, Any]],
    production_plan_rows: Iterable[dict[str, Any]],
    production_campaign_rows: Iterable[dict[str, Any]],
    mrp_order_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a queryable causal index without replacing the physical genealogy.

    Causal roots are scenario events. Entity links remain separate from physical
    parent/child lot links so simultaneous risks are retained as co-causes rather
    than being assigned arbitrary shares.
    """

    lot_events = list(lot_event_rows)
    genealogy = list(genealogy_rows)
    plan_rows = list(production_plan_rows)
    campaign_rows = list(production_campaign_rows)
    orders = list(mrp_order_rows)
    out: list[dict[str, Any]] = []
    out.extend(
        _entity_causal_rows(
            orders,
            entity_type="mrp_order",
            entity_id_field="mrp_order_id",
            relation_type="risk_affects_mrp_order",
            item_field="item_id",
            qty_field="planned_receipt_qty",
        )
    )
    out.extend(
        _entity_causal_rows(
            plan_rows,
            entity_type="production_order",
            entity_id_field="planned_order_id",
            relation_type="risk_affects_production_plan",
            item_field="output_item_id",
            qty_field="planned_qty_after_lot_rule",
        )
    )
    out.extend(
        _entity_causal_rows(
            campaign_rows,
            entity_type="production_campaign",
            entity_id_field="campaign_id",
            relation_type="risk_affects_production_campaign",
            item_field="output_item_id",
            qty_field="actual_qty",
            parent_entity_type="production_order",
            parent_entity_field="planned_order_id",
        )
    )
    out.extend(
        _entity_causal_rows(
            lot_events,
            entity_type="lot_event",
            entity_id_field="event_id",
            relation_type="risk_affects_lot_event",
            item_field="item_id",
            qty_field="qty",
            parent_entity_type="lot_occurrence",
            parent_entity_field="lot_occurrence_id",
        )
    )
    out.extend(
        _lot_event_entity_rows(
            lot_events,
            event_types={"production_output"},
            entity_type="business_lot",
            entity_id_field="business_batch_id",
            relation_type="risk_affects_business_lot",
        )
    )
    out.extend(
        _lot_event_entity_rows(
            lot_events,
            event_types={"lane_ship", "lane_receipt"},
            entity_type="shipment",
            entity_id_field="shipment_id",
            relation_type="risk_affects_shipment",
        )
    )
    out.extend(
        _lot_event_entity_rows(
            lot_events,
            event_types={"demand_service"},
            entity_type="customer_stock_allocation",
            entity_id_field="event_id",
            relation_type="risk_affects_customer_stock_allocation",
        )
    )

    for row in campaign_rows:
        campaign_id = str(row.get("campaign_id") or "").strip()
        order_id = str(row.get("planned_order_id") or "").strip()
        if campaign_id and order_id:
            out.append(
                _structural_row(
                    row,
                    relation_type="production_order_has_campaign",
                    entity_type="production_campaign",
                    entity_id=campaign_id,
                    parent_entity_type="production_order",
                    parent_entity_id=order_id,
                    qty=_to_float(row.get("actual_qty")),
                    basis="explicit_planned_order_id",
                )
            )

    for row in lot_events:
        event_type = str(row.get("event_type") or "").strip()
        event_id = str(row.get("event_id") or "").strip()
        business_batch_id = str(row.get("business_batch_id") or "").strip()
        occurrence_id = str(row.get("lot_occurrence_id") or "").strip()
        shipment_id = str(row.get("shipment_id") or "").strip()
        campaign_id = str(row.get("production_campaign_id") or "").strip()
        order_id = str(row.get("planned_order_id") or "").strip()
        if event_type == "production_output" and business_batch_id:
            parent_type = "production_campaign" if campaign_id else "production_order"
            parent_id = campaign_id or order_id
            if parent_id:
                out.append(
                    _structural_row(
                        row,
                        relation_type="campaign_produces_business_lot",
                        entity_type="business_lot",
                        entity_id=business_batch_id,
                        parent_entity_type=parent_type,
                        parent_entity_id=parent_id,
                        basis="production_output_event",
                    )
                )
        if event_type in {"lane_ship", "shipment_reserve"} and shipment_id:
            parent_ids = [business_batch_id] if business_batch_id else split_ids(
                row.get("origin_production_order_ids")
            )
            parent_type = "business_lot" if business_batch_id else "production_order"
            for parent_id in parent_ids:
                out.append(
                    _structural_row(
                        row,
                        relation_type="lot_allocated_to_shipment",
                        entity_type="shipment",
                        entity_id=shipment_id,
                        parent_entity_type=parent_type,
                        parent_entity_id=parent_id,
                        basis=(
                            "simulated_route_date_consolidation"
                            if event_type == "lane_ship"
                            else "reserved_before_physical_departure"
                        ),
                    )
                )
        if event_type == "lane_receipt" and shipment_id and occurrence_id:
            out.append(
                _structural_row(
                    row,
                    relation_type="shipment_creates_stock_occurrence",
                    entity_type="lot_occurrence",
                    entity_id=occurrence_id,
                    parent_entity_type="shipment",
                    parent_entity_id=shipment_id,
                    basis="lane_receipt_event",
                )
            )
        if event_type == "demand_service" and event_id:
            contributions = _origin_contributions(row)
            for origin_order_id, contribution_qty in contributions.items():
                out.append(
                    _structural_row(
                        row,
                        relation_type="production_order_contributes_to_customer_allocation",
                        entity_type="customer_stock_allocation",
                        entity_id=event_id,
                        parent_entity_type="production_order",
                        parent_entity_id=origin_order_id,
                        qty=contribution_qty,
                        basis=str(
                            row.get("origin_allocation_basis")
                            or "quantitative_origin_contribution"
                        ),
                        notes="Stock allocation to demand; not carrier delivery proof.",
                    )
                )

    for row in genealogy:
        transition_id = str(row.get("replacement_transition_id") or "").strip()
        required_item = str(row.get("required_item_id") or "").strip()
        consumed_item = str(row.get("consumed_item_id") or "").strip()
        if not transition_id or not required_item or not consumed_item or required_item == consumed_item:
            continue
        out.append(
            {
                "scenario_id": str(row.get("scenario_id") or ""),
                "causal_root_id": "",
                "causal_event_ids": join_ids(row.get("causal_event_ids")),
                "causal_status": str(row.get("causal_status") or "approved_transition"),
                "relation_type": "approved_item_substitution",
                "entity_type": "reference_transition",
                "entity_id": transition_id,
                "parent_entity_type": "production_order",
                "parent_entity_id": str(row.get("planned_order_id") or ""),
                "day": row.get("day", ""),
                "node_id": str(row.get("child_node_id") or ""),
                "item_id": required_item,
                "qty": round(max(0.0, _to_float(row.get("replacement_qty"))), 6),
                "uom": "",
                "basis": f"required={required_item};consumed={consumed_item}",
                "notes": str(row.get("replacement_reason") or ""),
            }
        )

    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in out:
        key = (
            str(row.get("scenario_id") or ""),
            str(row.get("causal_root_id") or ""),
            str(row.get("relation_type") or ""),
            str(row.get("entity_type") or ""),
            str(row.get("entity_id") or ""),
            str(row.get("parent_entity_type") or ""),
            str(row.get("parent_entity_id") or ""),
            str(row.get("day") or ""),
            str(row.get("qty") or ""),
            str(row.get("basis") or ""),
        )
        unique[key] = row
    return sorted(
        unique.values(),
        key=lambda row: (
            str(row.get("causal_root_id") or ""),
            str(row.get("entity_type") or ""),
            str(row.get("entity_id") or ""),
            str(row.get("day") or ""),
        ),
    )


__all__ = ["LOT_CAUSAL_LINK_FIELDS", "build_lot_causal_link_rows"]
