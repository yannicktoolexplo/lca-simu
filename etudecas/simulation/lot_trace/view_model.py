from __future__ import annotations

from typing import Any, Iterable

from .indexes import (
    LotTraceIndexes,
    build_lot_trace_indexes,
    reachable_lot_ids,
)


def build_lot_trace_view_model(
    payload: dict[str, Any],
    lot_id: str,
    direction: str = "all",
    indexes: LotTraceIndexes | None = None,
) -> dict[str, Any]:
    indexes = indexes or build_lot_trace_indexes(payload)
    reach = reachable_lot_ids(indexes, lot_id, direction)
    visible_lot_ids = set(reach["lot_ids"])
    visible_links = [
        link
        for link in indexes.links
        if _as_str(link.get("parent_lot_id")) in visible_lot_ids
        and _as_str(link.get("child_lot_id")) in visible_lot_ids
    ]
    all_visible_events = [
        event
        for lot in reach["lot_ids"]
        for event in indexes.events_by_lot.get(lot, [])
    ]
    production_component_totals = _production_component_denominators(indexes)
    transport_child_totals = _transport_child_denominators(indexes)
    contribution_by_lot = _downstream_contribution_by_lot(
        indexes,
        reach["root_lot_id"],
        visible_lot_ids,
        production_component_totals,
        transport_child_totals,
    )
    causal_links = _selected_contribution_links(
        reach,
        visible_links,
        contribution_by_lot,
    )
    causal_occurrence_ids = {
        reach["root_lot_id"],
        *(
            _as_str(link.get("parent_lot_id"))
            for link in causal_links
        ),
        *(
            _as_str(link.get("child_lot_id"))
            for link in causal_links
        ),
    }
    causal_occurrence_ids.discard("")
    causal_reach = {
        **reach,
        "lot_ids": [
            occurrence_id
            for occurrence_id in reach["lot_ids"]
            if occurrence_id in causal_occurrence_ids
        ],
        "upstream_lot_ids": [
            occurrence_id
            for occurrence_id in reach["upstream_lot_ids"]
            if occurrence_id in causal_occurrence_ids
        ],
        "downstream_lot_ids": [
            occurrence_id
            for occurrence_id in reach["downstream_lot_ids"]
            if occurrence_id in causal_occurrence_ids
        ],
    }
    visible_events = _selected_contribution_events(
        indexes,
        causal_reach["root_lot_id"],
        causal_occurrence_ids,
        causal_links,
        contribution_by_lot,
    )
    event_count_by_lot = _event_count_by_lot(visible_events)
    business_lot_ids_by_occurrence = _business_lot_ids_by_occurrence(
        indexes,
        causal_occurrence_ids,
        causal_links,
    )
    contribution_qty_by_lot = {
        lot_id: _to_float(row.get("contribution_qty"))
        for lot_id, row in contribution_by_lot.items()
    }
    nodes = [
        _lot_node(
            occurrence_id,
            indexes,
            contribution_by_lot,
            business_lot_ids_by_occurrence,
            event_count_by_lot,
        )
        for occurrence_id in causal_reach["lot_ids"]
    ]
    links = [
        _compact_link(
            link,
            contribution_by_lot,
            indexes,
            production_component_totals,
        )
        for link in causal_links
    ]
    component_groups = _build_component_groups(
        causal_links,
        indexes,
        business_lot_ids_by_occurrence,
    )
    transport_groups = _build_transport_groups(
        causal_links,
        indexes,
        causal_occurrence_ids,
        business_lot_ids_by_occurrence,
    )
    business_lots = _build_business_lots(
        nodes,
        business_lot_ids_by_occurrence,
        causal_reach["root_lot_id"],
    )
    production_operations = _build_production_operations(
        causal_links,
        indexes,
        business_lot_ids_by_occurrence,
    )
    shipments = [
        group
        for group in transport_groups
        if group.get("group_type") == "shipment" and group.get("shipment_id")
    ]
    mixed_customer_lots = _build_mixed_customer_lots(
        indexes,
        causal_occurrence_ids,
        contribution_qty_by_lot,
    )
    snapshot = _build_snapshot(causal_reach, causal_links, visible_events, nodes)
    upstream_business_lot_ids = _business_ids_for_occurrences(
        causal_reach["upstream_lot_ids"],
        business_lot_ids_by_occurrence,
    )
    downstream_business_lot_ids = _business_ids_for_occurrences(
        causal_reach["downstream_lot_ids"],
        business_lot_ids_by_occurrence,
    )
    unidentified_occurrence_count = sum(
        1
        for occurrence_id in causal_reach["lot_ids"]
        if not business_lot_ids_by_occurrence.get(occurrence_id)
    )
    inferred_transport_count = sum(
        1 for group in transport_groups if group.get("group_type") != "shipment"
    )
    counter_label = _business_counter_label(
        len(business_lots),
        len(nodes),
        len(shipments),
        inferred_transport_count,
        len(production_operations),
    )

    return {
        "version": 1,
        "lot_id": causal_reach["root_lot_id"],
        "direction": causal_reach["direction"],
        "root_lot": indexes.lots.get(causal_reach["root_lot_id"], {}),
        "snapshot": snapshot,
        "business_lots": business_lots,
        "stock_occurrences": nodes,
        "shipments": shipments,
        "production_operations": production_operations,
        "events": visible_events,
        "nodes": nodes,
        "links": links,
        "component_groups": component_groups,
        "transport_groups": transport_groups,
        "mixed_customer_lots": mixed_customer_lots,
        "summary": {
            "lot_count": len(business_lots),
            "business_lot_count": len(business_lots),
            "upstream_lot_count": len(upstream_business_lot_ids),
            "downstream_lot_count": len(downstream_business_lot_ids),
            "upstream_business_lot_count": len(upstream_business_lot_ids),
            "downstream_business_lot_count": len(downstream_business_lot_ids),
            "stock_occurrence_count": len(nodes),
            "upstream_occurrence_count": len(causal_reach["upstream_lot_ids"]),
            "downstream_occurrence_count": len(causal_reach["downstream_lot_ids"]),
            "unidentified_occurrence_count": unidentified_occurrence_count,
            "shipment_count": len(shipments),
            "transport_movement_count": len(transport_groups),
            "inferred_transport_movement_count": inferred_transport_count,
            "production_operation_count": len(production_operations),
            "event_count": len(visible_events),
            "causal_event_count": len(visible_events),
            "excluded_non_causal_event_count": max(
                0,
                len(all_visible_events) - len(visible_events),
            ),
            "link_count": len(causal_links),
            "component_group_count": len(component_groups),
            "transport_group_count": len(transport_groups),
            "mixed_customer_lot_count": len(mixed_customer_lots),
            "business_counter_label": counter_label,
            "lot_count_basis": "unique_business_lot_id",
            "stock_occurrence_count_basis": "unique_stock_occurrence_id",
            "shipment_count_basis": "explicit_shipment_id_only",
            "production_operation_count_basis": (
                "production_campaign_id_or_inferred_operation"
            ),
            "selectable_lot_policy": "PF/PFI/MP lots only; transport receipt lots are context",
        },
    }


def _build_snapshot(
    reach: dict[str, Any],
    links: list[dict[str, Any]],
    events: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    days = [_to_int(event.get("day")) for event in events]
    days.extend(_to_int(link.get("day")) for link in links)
    days = [day for day in days if day is not None]
    node_ids = _unique(
        [node.get("node_id") for node in nodes]
        + [link.get("parent_node_id") for link in links]
        + [link.get("child_node_id") for link in links]
    )
    item_ids = _unique(
        [node.get("item_id") for node in nodes]
        + [link.get("parent_item_id") for link in links]
        + [link.get("child_item_id") for link in links]
    )
    campaign_ids = _unique(
        [event.get("production_campaign_id") for event in events]
        + [link.get("production_campaign_id") for link in links]
    )
    return {
        "root_lot_id": reach["root_lot_id"],
        "direction": reach["direction"],
        "lot_ids": reach["lot_ids"],
        "upstream_lot_ids": reach["upstream_lot_ids"],
        "downstream_lot_ids": reach["downstream_lot_ids"],
        "event_ids": _unique(event.get("event_id") for event in events),
        "link_ids": [link["_link_id"] for link in links],
        "node_ids": node_ids,
        "item_ids": item_ids,
        "campaign_ids": campaign_ids,
        "days": sorted(set(days)),
        "first_day": min(days) if days else None,
        "last_day": max(days) if days else None,
    }


def _selected_contribution_links(
    reach: dict[str, Any],
    visible_links: list[dict[str, Any]],
    contribution_by_lot: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    root_lot_id = _as_str(reach.get("root_lot_id"))
    upstream_occurrence_ids = set(reach.get("upstream_lot_ids") or [])
    selected_link_ids: set[str] = set()
    for contribution in contribution_by_lot.values():
        for link_id, qty in (contribution.get("_path_contributions") or {}).items():
            if _to_float(qty) > 0:
                selected_link_ids.add(_as_str(link_id))

    selected: list[dict[str, Any]] = []
    for link in visible_links:
        parent_lot_id = _as_str(link.get("parent_lot_id"))
        child_lot_id = _as_str(link.get("child_lot_id"))
        is_upstream_path = (
            parent_lot_id in upstream_occurrence_ids
            and (
                child_lot_id in upstream_occurrence_ids
                or child_lot_id == root_lot_id
            )
        )
        is_downstream_contribution = _as_str(link.get("_link_id")) in selected_link_ids
        if is_upstream_path or is_downstream_contribution:
            selected.append(link)
    return selected


def _selected_contribution_events(
    indexes: LotTraceIndexes,
    root_lot_id: str,
    causal_occurrence_ids: set[str],
    causal_links: list[dict[str, Any]],
    contribution_by_lot: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    links_by_parent: dict[str, list[dict[str, Any]]] = {}
    links_by_child: dict[str, list[dict[str, Any]]] = {}
    explicit_event_ids: set[str] = set()
    for link in causal_links:
        parent_lot_id = _as_str(link.get("parent_lot_id"))
        child_lot_id = _as_str(link.get("child_lot_id"))
        links_by_parent.setdefault(parent_lot_id, []).append(link)
        links_by_child.setdefault(child_lot_id, []).append(link)
        explicit_event_ids.update(_identifier_values(link.get("causal_event_ids")))

    selected: list[dict[str, Any]] = []
    for occurrence_id in sorted(causal_occurrence_ids):
        outgoing_links = links_by_parent.get(occurrence_id, [])
        incoming_links = links_by_child.get(occurrence_id, [])
        outgoing_days = [
            _to_int(link.get("day"))
            for link in outgoing_links
            if _to_int(link.get("day")) is not None
        ]
        latest_outgoing_day = max(outgoing_days) if outgoing_days else None
        for event in indexes.events_by_lot.get(occurrence_id, []):
            event_type = _as_str(event.get("event_type")).lower()
            event_id = _as_str(event.get("event_id"))
            event_day = _to_int(event.get("day"))
            is_explicit = (
                event_id in explicit_event_ids
                or root_lot_id in _identifier_values(event.get("causal_root_ids"))
                or root_lot_id in _identifier_values(event.get("related_lot_id"))
            )
            is_creation = _is_lot_creation_event(event_type)
            is_link_event = any(
                _event_matches_link(event, link, role="parent")
                for link in outgoing_links
            ) or any(
                _event_matches_link(event, link, role="child")
                for link in incoming_links
            )
            has_selected_contribution = _to_float(
                (contribution_by_lot.get(occurrence_id) or {}).get(
                    "contribution_qty"
                )
            ) > 0
            is_customer_service = (
                event_type == "demand_service" and has_selected_contribution
            )
            is_quantity_effect = (
                event_type in {"writeoff", "stock_writeoff"}
                and latest_outgoing_day is not None
                and event_day is not None
                and event_day <= latest_outgoing_day
            )
            if (
                is_explicit
                or is_link_event
                or is_customer_service
                or is_quantity_effect
                or (
                    is_creation
                    and (
                        occurrence_id == root_lot_id
                        or incoming_links
                        or outgoing_links
                    )
                )
            ):
                selected.append(event)
    return sorted(
        selected,
        key=lambda event: (
            _day_sort(event.get("day")),
            _as_str(event.get("event_id")),
        ),
    )


def _is_lot_creation_event(event_type: str) -> bool:
    return event_type in {
        "creation",
        "opening_stock",
        "production_output",
        "lane_receipt",
        "external_procurement_receipt",
        "estimated_source_receipt",
        "estimated_capacity_receipt",
    }


def _event_matches_link(
    event: dict[str, Any],
    link: dict[str, Any],
    role: str,
) -> bool:
    event_type = _as_str(event.get("event_type")).lower()
    link_type = _as_str(link.get("link_type")).lower()
    related_lot_id = _as_str(event.get("related_lot_id"))
    expected_related_lot_id = _as_str(
        link.get("child_lot_id") if role == "parent" else link.get("parent_lot_id")
    )
    if related_lot_id and related_lot_id != expected_related_lot_id:
        return False

    if link_type == "production":
        if role == "parent":
            if "production_consume" not in event_type:
                return False
        elif event_type not in {"production_output", "creation"}:
            return False
        event_campaign_id = _as_str(event.get("production_campaign_id"))
        link_campaign_id = _as_str(link.get("production_campaign_id"))
        if event_campaign_id and link_campaign_id:
            return event_campaign_id == link_campaign_id
        return _to_int(event.get("day")) == _to_int(link.get("day"))

    if link_type == "transport":
        expected_types = (
            {"lane_ship"}
            if role == "parent"
            else {
                "lane_receipt",
                "external_procurement_receipt",
                "estimated_source_receipt",
                "estimated_capacity_receipt",
                "creation",
            }
        )
        if event_type not in expected_types:
            return False
        event_shipment_id = _as_str(
            event.get("shipment_id") or event.get("consignment_id")
        )
        link_shipment_id = _as_str(
            link.get("shipment_id") or link.get("consignment_id")
        )
        if event_shipment_id and link_shipment_id:
            return event_shipment_id == link_shipment_id
        event_source_id = _as_str(event.get("source_id"))
        link_source_id = _as_str(link.get("source_id"))
        if event_source_id and link_source_id and event_source_id != link_source_id:
            return False
        if role == "child":
            return _to_int(event.get("day")) == _transport_arrival_day(link)
        departure_day = _to_int(link.get("departure_day"))
        return departure_day is None or _to_int(event.get("day")) == departure_day
    return False


def _identifier_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {
            _as_str(item).strip()
            for item in value
            if _as_str(item).strip()
        }
    text = _as_str(value).strip()
    if not text:
        return set()
    for separator in (";", "|"):
        text = text.replace(separator, ",")
    return {part.strip() for part in text.split(",") if part.strip()}


def _event_count_by_lot(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        occurrence_id = _as_str(event.get("lot_id"))
        if occurrence_id:
            counts[occurrence_id] = counts.get(occurrence_id, 0) + 1
    return counts


def _business_lot_ids_by_occurrence(
    indexes: LotTraceIndexes,
    occurrence_ids: set[str],
    causal_links: list[dict[str, Any]],
) -> dict[str, list[str]]:
    incoming_transport: dict[str, list[str]] = {}
    for link in causal_links:
        if _as_str(link.get("link_type")) != "transport":
            continue
        child_lot_id = _as_str(link.get("child_lot_id"))
        parent_lot_id = _as_str(link.get("parent_lot_id"))
        if child_lot_id and parent_lot_id:
            incoming_transport.setdefault(child_lot_id, []).append(parent_lot_id)

    memo: dict[str, list[str]] = {}

    def resolve(occurrence_id: str, resolving: set[str]) -> list[str]:
        if occurrence_id in memo:
            return memo[occurrence_id]
        if occurrence_id in resolving:
            return []
        next_resolving = {*resolving, occurrence_id}
        parent_occurrence_ids = incoming_transport.get(occurrence_id, [])
        if parent_occurrence_ids:
            inherited = sorted(
                {
                    business_lot_id
                    for parent_occurrence_id in parent_occurrence_ids
                    for business_lot_id in resolve(
                        parent_occurrence_id,
                        next_resolving,
                    )
                }
            )
            if inherited:
                memo[occurrence_id] = inherited
                return inherited

        explicit = _explicit_business_lot_ids(
            indexes.lots.get(occurrence_id, {})
        )
        if explicit:
            memo[occurrence_id] = explicit
            return explicit
        if _is_unidentified_receipt_occurrence(occurrence_id, indexes):
            memo[occurrence_id] = []
            return []
        memo[occurrence_id] = [occurrence_id]
        return memo[occurrence_id]

    for occurrence_id in sorted(occurrence_ids):
        resolve(occurrence_id, set())
    return {
        occurrence_id: memo.get(occurrence_id, [])
        for occurrence_id in sorted(occurrence_ids)
    }


def _explicit_business_lot_ids(lot: dict[str, Any]) -> list[str]:
    identity = lot.get("identity") if isinstance(lot.get("identity"), dict) else {}
    return sorted(
        {
            *_identifier_values(lot.get("business_lot_id")),
            *_identifier_values(lot.get("business_lot_ids")),
            *_identifier_values(lot.get("business_batch_id")),
            *_identifier_values(identity.get("business_lot_id")),
            *_identifier_values(identity.get("business_lot_ids")),
        }
    )


def _is_unidentified_receipt_occurrence(
    occurrence_id: str,
    indexes: LotTraceIndexes,
) -> bool:
    lot = indexes.lots.get(occurrence_id, {})
    trace_scope = _as_str(lot.get("trace_scope")).lower()
    if "receipt" in trace_scope:
        return True
    return any(
        _as_str(event.get("event_type")).lower() == "lane_receipt"
        for event in indexes.events_by_lot.get(occurrence_id, [])
    )


def _business_ids_for_occurrences(
    occurrence_ids: Iterable[Any],
    business_lot_ids_by_occurrence: dict[str, list[str]],
) -> list[str]:
    return sorted(
        {
            business_lot_id
            for occurrence_id in occurrence_ids
            for business_lot_id in business_lot_ids_by_occurrence.get(
                _as_str(occurrence_id),
                [],
            )
        }
    )


def _build_business_lots(
    nodes: list[dict[str, Any]],
    business_lot_ids_by_occurrence: dict[str, list[str]],
    root_occurrence_id: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    root_business_lot_ids = set(
        business_lot_ids_by_occurrence.get(root_occurrence_id, [])
    )
    for node in nodes:
        occurrence_id = _as_str(node.get("stock_occurrence_id")) or _as_str(
            node.get("lot_id")
        )
        for business_lot_id in business_lot_ids_by_occurrence.get(
            _as_str(node.get("lot_id")),
            [],
        ):
            group = grouped.setdefault(
                business_lot_id,
                {
                    "business_lot_id": business_lot_id,
                    "occurrence_ids": set(),
                    "node_ids": set(),
                    "item_ids": set(),
                    "first_day": None,
                    "last_day": None,
                    "is_selected_business_lot": (
                        business_lot_id in root_business_lot_ids
                    ),
                },
            )
            group["occurrence_ids"].add(occurrence_id)
            if node.get("node_id"):
                group["node_ids"].add(node["node_id"])
            if node.get("item_id"):
                group["item_ids"].add(node["item_id"])
            first_day = _to_int(node.get("first_day"))
            last_day = _to_int(node.get("last_day"))
            if first_day is not None:
                group["first_day"] = (
                    first_day
                    if group["first_day"] is None
                    else min(group["first_day"], first_day)
                )
            if last_day is not None:
                group["last_day"] = (
                    last_day
                    if group["last_day"] is None
                    else max(group["last_day"], last_day)
                )
    return [
        {
            **group,
            "occurrence_ids": sorted(group["occurrence_ids"]),
            "occurrence_count": len(group["occurrence_ids"]),
            "node_ids": sorted(group["node_ids"]),
            "item_ids": sorted(group["item_ids"]),
        }
        for group in sorted(
            grouped.values(),
            key=lambda row: (
                not row["is_selected_business_lot"],
                row["business_lot_id"],
            ),
        )
    ]


def _build_production_operations(
    links: list[dict[str, Any]],
    indexes: LotTraceIndexes,
    business_lot_ids_by_occurrence: dict[str, list[str]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for link in links:
        if _as_str(link.get("link_type")) != "production":
            continue
        child_occurrence_id = _as_str(link.get("child_lot_id"))
        campaign_id = _as_str(link.get("production_campaign_id"))
        day = _to_int(link.get("day"))
        node_id = _as_str(link.get("child_node_id"))
        key = (
            "campaign",
            campaign_id,
        ) if campaign_id else (
            "inferred",
            day,
            node_id,
            child_occurrence_id,
        )
        operation_id = (
            campaign_id
            if campaign_id
            else f"PRODUCTION:{day}:{node_id}:{child_occurrence_id}"
        )
        group = grouped.setdefault(
            key,
            {
                "production_operation_id": operation_id,
                "production_campaign_id": campaign_id,
                "identity_status": "identified" if campaign_id else "inferred",
                "day": day,
                "node_ids": set(),
                "input_occurrence_ids": set(),
                "output_occurrence_ids": set(),
                "input_business_lot_ids": set(),
                "output_business_lot_ids": set(),
                "input_item_ids": set(),
                "output_item_ids": set(),
                "output_qty_by_occurrence": {},
            },
        )
        parent_occurrence_id = _as_str(link.get("parent_lot_id"))
        if node_id:
            group["node_ids"].add(node_id)
        group["input_occurrence_ids"].add(parent_occurrence_id)
        group["output_occurrence_ids"].add(child_occurrence_id)
        group["input_business_lot_ids"].update(
            business_lot_ids_by_occurrence.get(parent_occurrence_id, [])
        )
        group["output_business_lot_ids"].update(
            business_lot_ids_by_occurrence.get(child_occurrence_id, [])
        )
        if link.get("parent_item_id"):
            group["input_item_ids"].add(_as_str(link.get("parent_item_id")))
        if link.get("child_item_id"):
            group["output_item_ids"].add(_as_str(link.get("child_item_id")))
        group["output_qty_by_occurrence"][child_occurrence_id] = max(
            _to_float(
                group["output_qty_by_occurrence"].get(child_occurrence_id)
            ),
            _to_float(link.get("child_qty")),
        )

    return [
        {
            **group,
            "node_ids": sorted(group["node_ids"]),
            "input_occurrence_ids": sorted(group["input_occurrence_ids"]),
            "output_occurrence_ids": sorted(group["output_occurrence_ids"]),
            "input_business_lot_ids": sorted(group["input_business_lot_ids"]),
            "output_business_lot_ids": sorted(group["output_business_lot_ids"]),
            "input_item_ids": sorted(group["input_item_ids"]),
            "output_item_ids": sorted(group["output_item_ids"]),
            "input_occurrence_count": len(group["input_occurrence_ids"]),
            "output_occurrence_count": len(group["output_occurrence_ids"]),
            "output_qty": _round_qty(
                sum(group["output_qty_by_occurrence"].values())
            ),
        }
        for group in sorted(
            grouped.values(),
            key=lambda row: (
                _day_sort(row["day"]),
                row["production_operation_id"],
            ),
        )
    ]


def _business_counter_label(
    business_lot_count: int,
    occurrence_count: int,
    shipment_count: int,
    inferred_transport_count: int,
    production_count: int,
) -> str:
    shipment_text = f"{shipment_count} expedition(s) identifiee(s)"
    if inferred_transport_count:
        shipment_text += (
            f" + {inferred_transport_count} mouvement(s) sans ID expedition"
        )
    return (
        f"{business_lot_count} lot(s) metier | "
        f"{occurrence_count} occurrence(s) de stock | "
        f"{shipment_text} | "
        f"{production_count} operation(s) de production"
    )


def _build_component_groups(
    links: list[dict[str, Any]],
    indexes: LotTraceIndexes,
    business_lot_ids_by_occurrence: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for link in links:
        if _as_str(link.get("link_type")) != "production":
            continue
        parent_lot_id = _as_str(link.get("parent_lot_id"))
        uom = _lot_uom(parent_lot_id, indexes)
        key = (
            _to_int(link.get("day")),
            _as_str(link.get("child_lot_id")),
            _as_str(link.get("parent_node_id")),
            _as_str(link.get("parent_item_id")),
            uom,
            _as_str(link.get("production_campaign_id")),
        )
        group = grouped.setdefault(
            key,
            {
                "day": key[0],
                "child_lot_id": key[1],
                "node_id": key[2],
                "item_id": key[3],
                "uom": key[4],
                "production_campaign_id": key[5],
                "parent_lot_ids": set(),
                "business_lot_ids": set(),
                "qty": 0.0,
                "child_qty": 0.0,
            },
        )
        parent_lot_id = _as_str(link.get("parent_lot_id"))
        group["parent_lot_ids"].add(parent_lot_id)
        group["business_lot_ids"].update(
            (business_lot_ids_by_occurrence or {}).get(parent_lot_id, [])
        )
        group["qty"] += _to_float(link.get("parent_qty"))
        group["child_qty"] = max(group["child_qty"], _to_float(link.get("child_qty")))

    return [
        {
            **group,
            "parent_lot_ids": sorted(group["parent_lot_ids"]),
            "parent_occurrence_ids": sorted(group["parent_lot_ids"]),
            "occurrence_count": len(group["parent_lot_ids"]),
            "business_lot_ids": sorted(group["business_lot_ids"]),
            "business_lot_count": len(group["business_lot_ids"]),
            "lot_count": len(group["business_lot_ids"]),
            "qty": _round_qty(group["qty"]),
            "child_qty": _round_qty(group["child_qty"]),
        }
        for group in sorted(
            grouped.values(),
            key=lambda row: (_day_sort(row["day"]), row["item_id"], row["uom"]),
        )
    ]


def _build_transport_groups(
    links: list[dict[str, Any]],
    indexes: LotTraceIndexes,
    visible_lot_ids: set[str],
    business_lot_ids_by_occurrence: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for link in links:
        if _as_str(link.get("link_type")) != "transport":
            continue
        arrival_day = _transport_arrival_day(link)
        departure_day = _transport_departure_day(link, indexes)
        shipment_id = _transport_value(link, indexes, ("shipment_id", "consignment_id"))
        handling_unit = _transport_value(
            link,
            indexes,
            ("handling_unit", "handling_unit_id", "transport_unit_id", "container_id"),
        )
        item_id = _as_str(link.get("child_item_id")) or _as_str(link.get("parent_item_id"))
        uom = _transport_uom(link, indexes)
        from_node_id = _as_str(link.get("parent_node_id"))
        to_node_id = _as_str(link.get("child_node_id"))
        source_id = _as_str(link.get("source_id"))
        source_trace_status = _as_str(link.get("trace_status"))
        source_trace_reason = _as_str(link.get("trace_reason"))
        if shipment_id:
            key = ("shipment", shipment_id)
            group_type = "shipment"
            trace_status = source_trace_status or "simulation_movement_identified"
            trace_reason = source_trace_reason or "shipment_id_present"
        else:
            key = (
                "inferred_group",
                arrival_day,
                from_node_id,
                to_node_id,
                item_id,
                uom,
                source_id,
            )
            group_type = "inferred_group"
            trace_status = "inferred"
            trace_reason = "shipment_id_missing_grouped_by_arrival_route_item"
        group = grouped.setdefault(
            key,
            {
                "group_id": shipment_id or _inferred_transport_group_id(
                    arrival_day,
                    from_node_id,
                    to_node_id,
                    item_id,
                    uom,
                    source_id,
                ),
                "group_type": group_type,
                "shipment_id": shipment_id,
                "departure_days": set(),
                "arrival_days": set(),
                "from_node_ids": set(),
                "to_node_ids": set(),
                "item_ids": set(),
                "uoms": set(),
                "handling_units": set(),
                "mrp_order_ids": set(),
                "order_days": set(),
                "mrp_decision_days": set(),
                "requested_release_days": set(),
                "planned_release_days": set(),
                "actual_release_days": set(),
                "estimated_release_days": set(),
                "planned_arrival_days": set(),
                "actual_receipt_days": set(),
                "procurement_lead_days": set(),
                "procurement_lead_bases": set(),
                "procurement_statuses": set(),
                "procurement_trace_statuses": set(),
                "procurement_trace_reasons": set(),
                "parent_lot_ids": set(),
                "child_lot_ids": set(),
                "source_ids": set(),
                "lines": {},
                "trace_status": trace_status,
                "trace_reason": trace_reason,
                "trace_statuses": set(),
                "trace_reasons": set(),
            },
        )
        if trace_status:
            group["trace_statuses"].add(trace_status)
        if trace_reason:
            group["trace_reasons"].add(trace_reason)
        if departure_day is not None:
            group["departure_days"].add(departure_day)
        if arrival_day is not None:
            group["arrival_days"].add(arrival_day)
        if from_node_id:
            group["from_node_ids"].add(from_node_id)
        if to_node_id:
            group["to_node_ids"].add(to_node_id)
        if item_id:
            group["item_ids"].add(item_id)
        if uom:
            group["uoms"].add(uom)
        if handling_unit:
            group["handling_units"].add(handling_unit)
        _remember_procurement_metadata(group, link)
        parent_lot = _as_str(link.get("parent_lot_id"))
        child_lot = _as_str(link.get("child_lot_id"))
        if parent_lot:
            group["parent_lot_ids"].add(parent_lot)
        if child_lot:
            group["child_lot_ids"].add(child_lot)
        if source_id:
            group["source_ids"].add(source_id)
        line_key = (item_id, uom)
        line = group["lines"].setdefault(
            line_key,
            {
                "item_id": item_id,
                "uom": uom,
                "shipped_qty": 0.0,
                "received_qty_by_child": {},
            },
        )
        line["shipped_qty"] += _to_float(link.get("parent_qty"))
        child_qty = _to_float(link.get("child_qty"))
        line["received_qty_by_child"][child_lot] = max(
            line["received_qty_by_child"].get(child_lot, 0.0),
            child_qty,
        )

    linked_child_lots = {
        _as_str(link.get("child_lot_id"))
        for link in links
        if _as_str(link.get("link_type")) == "transport"
    }
    for child_lot in sorted(visible_lot_ids - linked_child_lots):
        for event in indexes.events_by_lot.get(child_lot, []):
            if _as_str(event.get("event_type")) != "lane_receipt":
                continue
            arrival_day = _to_int(event.get("day"))
            item_id = _as_str(event.get("item_id"))
            uom = _normalize_uom(event.get("uom"))
            to_node_id = _as_str(event.get("node_id"))
            source_id = _as_str(event.get("source_id"))
            trace_status = _as_str(event.get("trace_status")) or "untraced_origin"
            trace_reason = _as_str(event.get("trace_reason")) or "no_transport_parent_link"
            shipment_id = _as_str(event.get("shipment_id"))
            departure_day = _to_int(event.get("departure_day"))
            handling_unit = _as_str(event.get("handling_unit_id"))
            group_id = f"untraced_receipt:{child_lot}:{arrival_day}"
            grouped[("untraced_receipt", child_lot, arrival_day)] = {
                "group_id": group_id,
                "group_type": "untraced_receipt",
                "shipment_id": shipment_id,
                "departure_days": {departure_day} if departure_day is not None else set(),
                "arrival_days": {arrival_day} if arrival_day is not None else set(),
                "from_node_ids": {
                    _as_str(event.get("supplier_node_id"))
                }
                if _as_str(event.get("supplier_node_id"))
                else set(),
                "to_node_ids": {to_node_id} if to_node_id else set(),
                "item_ids": {item_id} if item_id else set(),
                "uoms": {uom} if uom else set(),
                "handling_units": {handling_unit} if handling_unit else set(),
                "mrp_order_ids": {
                    _as_str(event.get("mrp_order_id"))
                }
                if _as_str(event.get("mrp_order_id"))
                else set(),
                "order_days": _optional_int_set(event.get("order_day")),
                "mrp_decision_days": _optional_int_set(
                    event.get("mrp_decision_day")
                ),
                "requested_release_days": _optional_int_set(
                    event.get("requested_release_day")
                ),
                "planned_release_days": _optional_int_set(
                    event.get("planned_release_day")
                ),
                "actual_release_days": _optional_int_set(
                    event.get("actual_release_day")
                ),
                "estimated_release_days": _optional_int_set(
                    event.get("estimated_release_day")
                ),
                "planned_arrival_days": _optional_int_set(
                    event.get("planned_arrival_day")
                ),
                "actual_receipt_days": _optional_int_set(
                    event.get("actual_receipt_day")
                ),
                "procurement_lead_days": _optional_int_set(
                    event.get("procurement_lead_days")
                ),
                "procurement_lead_bases": {
                    _as_str(event.get("procurement_lead_basis"))
                }
                if _as_str(event.get("procurement_lead_basis"))
                else set(),
                "procurement_statuses": {
                    _as_str(event.get("procurement_status"))
                }
                if _as_str(event.get("procurement_status"))
                else set(),
                "procurement_trace_statuses": {
                    _as_str(event.get("procurement_trace_status"))
                }
                if _as_str(event.get("procurement_trace_status"))
                else set(),
                "procurement_trace_reasons": {
                    _as_str(event.get("procurement_trace_reason"))
                }
                if _as_str(event.get("procurement_trace_reason"))
                else set(),
                "parent_lot_ids": set(),
                "child_lot_ids": {child_lot},
                "source_ids": {source_id} if source_id else set(),
                "lines": {
                    (item_id, uom): {
                        "item_id": item_id,
                        "uom": uom,
                        "shipped_qty": 0.0,
                        "received_qty_by_child": {child_lot: _to_float(event.get("qty"))},
                    }
                },
                "trace_status": trace_status,
                "trace_reason": trace_reason,
                "trace_statuses": {trace_status},
                "trace_reasons": {trace_reason},
            }

    out = []
    for group in sorted(
        grouped.values(),
        key=lambda row: (
            _day_sort(min(row["arrival_days"]) if row["arrival_days"] else None),
            sorted(row["from_node_ids"])[0] if row["from_node_ids"] else "",
            sorted(row["to_node_ids"])[0] if row["to_node_ids"] else "",
            row["group_id"],
        ),
    ):
        lines = []
        for line in sorted(group["lines"].values(), key=lambda row: (row["item_id"], row["uom"])):
            received_qty = sum(line["received_qty_by_child"].values())
            lines.append(
                {
                    "item_id": line["item_id"],
                    "uom": line["uom"],
                    "shipped_qty": _round_qty(line["shipped_qty"]),
                    "received_qty": _round_qty(received_qty),
                }
            )
        item_ids = sorted(group["item_ids"])
        uoms = sorted(group["uoms"])
        from_node_ids = sorted(group["from_node_ids"])
        to_node_ids = sorted(group["to_node_ids"])
        departure_days = sorted(group["departure_days"])
        arrival_days = sorted(group["arrival_days"])
        handling_units = sorted(group["handling_units"])
        mrp_order_ids = sorted(group.get("mrp_order_ids") or [])
        order_days = sorted(group.get("order_days") or [])
        mrp_decision_days = sorted(group.get("mrp_decision_days") or [])
        requested_release_days = sorted(
            group.get("requested_release_days") or []
        )
        planned_release_days = sorted(group.get("planned_release_days") or [])
        actual_release_days = sorted(group.get("actual_release_days") or [])
        estimated_release_days = sorted(
            group.get("estimated_release_days") or []
        )
        planned_arrival_days = sorted(group.get("planned_arrival_days") or [])
        actual_receipt_days = sorted(group.get("actual_receipt_days") or [])
        procurement_lead_days = sorted(group.get("procurement_lead_days") or [])
        procurement_lead_bases = sorted(
            group.get("procurement_lead_bases") or []
        )
        procurement_statuses = sorted(group.get("procurement_statuses") or [])
        procurement_trace_statuses = sorted(
            group.get("procurement_trace_statuses") or []
        )
        procurement_trace_reasons = sorted(
            group.get("procurement_trace_reasons") or []
        )
        trace_statuses = sorted(group.get("trace_statuses") or {group["trace_status"]})
        trace_reasons = sorted(group.get("trace_reasons") or {group["trace_reason"]})
        if any(status.startswith("untraced") for status in trace_statuses):
            trace_status = next(
                status for status in trace_statuses if status.startswith("untraced")
            )
        elif "partially_traced_mixed_occurrence" in trace_statuses:
            trace_status = "partially_traced_mixed_occurrence"
        elif "mixed_batch_occurrence" in trace_statuses:
            trace_status = "mixed_batch_occurrence"
        elif len(trace_statuses) == 1:
            trace_status = trace_statuses[0]
        else:
            trace_status = "mixed_trace_status"
        trace_reason = " ; ".join(reason for reason in trace_reasons if reason)
        quantities_comparable = len(lines) == 1
        parent_business_lot_ids = _business_ids_for_occurrences(
            group["parent_lot_ids"],
            business_lot_ids_by_occurrence or {},
        )
        child_business_lot_ids = _business_ids_for_occurrences(
            group["child_lot_ids"],
            business_lot_ids_by_occurrence or {},
        )
        movement_business_lot_ids = sorted(
            {*parent_business_lot_ids, *child_business_lot_ids}
        )
        out.append(
            {
                "group_id": group["group_id"],
                "group_type": group["group_type"],
                "shipment_id": group["shipment_id"],
                "day": arrival_days[0] if len(arrival_days) == 1 else None,
                "departure_day": departure_days[0] if len(departure_days) == 1 else None,
                "arrival_day": arrival_days[0] if len(arrival_days) == 1 else None,
                "departure_days": departure_days,
                "arrival_days": arrival_days,
                "from_node_id": from_node_ids[0] if len(from_node_ids) == 1 else "",
                "to_node_id": to_node_ids[0] if len(to_node_ids) == 1 else "",
                "from_node_ids": from_node_ids,
                "to_node_ids": to_node_ids,
                "item_id": item_ids[0] if len(item_ids) == 1 else "",
                "item_ids": item_ids,
                "uom": uoms[0] if len(uoms) == 1 else "",
                "uoms": uoms,
                "handling_unit": handling_units[0] if len(handling_units) == 1 else "",
                "handling_units": handling_units,
                "mrp_order_id": mrp_order_ids[0] if len(mrp_order_ids) == 1 else "",
                "mrp_order_ids": mrp_order_ids,
                "order_day": order_days[0] if len(order_days) == 1 else None,
                "order_days": order_days,
                "mrp_decision_day": (
                    mrp_decision_days[0]
                    if len(mrp_decision_days) == 1
                    else None
                ),
                "mrp_decision_days": mrp_decision_days,
                "requested_release_day": (
                    requested_release_days[0]
                    if len(requested_release_days) == 1
                    else None
                ),
                "requested_release_days": requested_release_days,
                "planned_release_day": (
                    planned_release_days[0]
                    if len(planned_release_days) == 1
                    else None
                ),
                "planned_release_days": planned_release_days,
                "actual_release_day": (
                    actual_release_days[0]
                    if len(actual_release_days) == 1
                    else None
                ),
                "actual_release_days": actual_release_days,
                "estimated_release_day": (
                    estimated_release_days[0]
                    if len(estimated_release_days) == 1
                    else None
                ),
                "estimated_release_days": estimated_release_days,
                "planned_arrival_day": (
                    planned_arrival_days[0]
                    if len(planned_arrival_days) == 1
                    else None
                ),
                "planned_arrival_days": planned_arrival_days,
                "actual_receipt_day": (
                    actual_receipt_days[0]
                    if len(actual_receipt_days) == 1
                    else None
                ),
                "actual_receipt_days": actual_receipt_days,
                "procurement_lead_days": procurement_lead_days,
                "procurement_lead_bases": procurement_lead_bases,
                "procurement_statuses": procurement_statuses,
                "procurement_trace_statuses": procurement_trace_statuses,
                "procurement_trace_reasons": procurement_trace_reasons,
                "parent_lot_ids": sorted(group["parent_lot_ids"]),
                "child_lot_ids": sorted(group["child_lot_ids"]),
                "parent_occurrence_ids": sorted(group["parent_lot_ids"]),
                "child_occurrence_ids": sorted(group["child_lot_ids"]),
                "source_ids": sorted(group["source_ids"]),
                "parent_lot_count": len(parent_business_lot_ids),
                "child_lot_count": len(child_business_lot_ids),
                "parent_occurrence_count": len(group["parent_lot_ids"]),
                "child_occurrence_count": len(group["child_lot_ids"]),
                "parent_business_lot_ids": parent_business_lot_ids,
                "child_business_lot_ids": child_business_lot_ids,
                "business_lot_ids": movement_business_lot_ids,
                "business_lot_count": len(movement_business_lot_ids),
                "shipped_qty": lines[0]["shipped_qty"] if quantities_comparable else None,
                "received_qty": lines[0]["received_qty"] if quantities_comparable else None,
                "lines": lines,
                "quantities_comparable": quantities_comparable,
                "trace_status": trace_status,
                "trace_reason": trace_reason,
                "reason": trace_reason,
                "is_simulated_shipment": bool(group["shipment_id"]),
                "is_physical_shipment": False,
                "is_consolidated": len(group["parent_lot_ids"]) > 1 or len(group["child_lot_ids"]) > 1,
            }
        )
    return out


def _downstream_contribution_by_lot(
    indexes: LotTraceIndexes,
    root_lot_id: str,
    visible_lot_ids: set[str],
    production_denominators: dict[tuple[str, str, str], float] | None = None,
    transport_denominators: dict[tuple[str, str, str], float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Propagate the selected lot contribution through production and transport.

    The quantity has two distinct meanings depending on the link type:
    - transport: same business item is moved, so the traced quantity stays in
      the transported unit;
    - production: a consumed MP/PFI lot contributes to the produced PF/PFI lot.
      The child contribution is expressed in output units and is based on the
      consumed component share for that production genealogy link.
    """

    root = _as_str(root_lot_id)
    if not root:
        return {}
    root_qty = _lot_total_qty(root, indexes)
    contributions: dict[str, dict[str, Any]] = (
        {
            root: {
                "contribution_qty": root_qty,
                "contribution_basis": "selected_lot_total_qty",
                "contribution_source_lot_id": root,
                "contribution_path_link_type": "root",
            }
        }
        if root_qty > 0
        else {}
    )
    production_denominators = production_denominators or _production_component_denominators(indexes)
    transport_denominators = transport_denominators or _transport_child_denominators(indexes)
    queue: list[tuple[str, float]] = [(root, root_qty)]
    guard = 0
    while queue and guard < 10000:
        guard += 1
        parent, contribution_delta = queue.pop(0)
        if contribution_delta <= 0:
            continue
        parent_total = _lot_total_qty(parent, indexes)
        parent_share = min(1.0, max(0.0, contribution_delta / parent_total)) if parent_total > 0 else 1.0
        for link in indexes.link_rows_by_parent.get(parent, []):
            link_type = _as_str(link.get("link_type"))
            if link_type not in {"transport", "production"}:
                continue
            child = _as_str(link.get("child_lot_id"))
            if not child or child not in visible_lot_ids:
                continue
            parent_link_qty = _to_float(link.get("parent_qty"))
            child_link_qty = _to_float(link.get("child_qty"))
            if link_type == "production":
                if parent_link_qty <= 0 or child_link_qty <= 0:
                    continue
                denominator_key = _production_component_key(link, indexes)
                component_total = production_denominators.get(denominator_key, 0.0)
                if component_total <= 0:
                    continue
                component_lot_share = min(1.0, max(0.0, parent_link_qty / component_total))
                traced_qty = child_link_qty * component_lot_share * parent_share
                basis = "production_same_component_consumption_share"
            else:
                denominator_key = _transport_child_key(link, indexes)
                transported_parent_total = transport_denominators.get(denominator_key, 0.0)
                if transported_parent_total <= 0 or child_link_qty <= 0:
                    continue
                transported_lot_share = min(
                    1.0,
                    max(0.0, parent_link_qty / transported_parent_total),
                )
                traced_qty = child_link_qty * transported_lot_share * parent_share
                basis = "transport_received_quantity_share"
            if traced_qty <= 0:
                continue
            old = _to_float((contributions.get(child) or {}).get("contribution_qty"))
            child_total = _lot_total_qty(child, indexes)
            new_value = min(child_total, old + traced_qty) if child_total > 0 else old + traced_qty
            accepted_delta = new_value - old
            if accepted_delta <= 1e-9:
                continue
            existing = contributions.get(child) or {}
            link_id = _as_str(link.get("_link_id"))
            path_contributions = dict(existing.get("_path_contributions") or {})
            path_contributions[link_id] = _to_float(path_contributions.get(link_id)) + accepted_delta
            parent_lot_ids = set(existing.get("_contribution_parent_lot_ids") or [])
            parent_lot_ids.add(parent)
            contributions[child] = {
                "contribution_qty": new_value,
                "contribution_basis": (
                    basis
                    if not existing or _as_str(existing.get("contribution_basis")) == basis
                    else "multiple_path_types"
                ),
                "contribution_source_lot_id": root,
                "contribution_parent_lot_id": parent if len(parent_lot_ids) == 1 else "",
                "contribution_path_link_type": link_type,
                "contribution_parent_share": _round_ratio(parent_share),
                "_path_contributions": path_contributions,
                "_contribution_parent_lot_ids": sorted(parent_lot_ids),
            }
            queue.append((child, accepted_delta))
    return contributions


def _production_component_denominators(indexes: LotTraceIndexes) -> dict[tuple[str, str, str], float]:
    totals: dict[tuple[str, str, str], float] = {}
    for link in indexes.links:
        if _as_str(link.get("link_type")) != "production":
            continue
        key = _production_component_key(link, indexes)
        totals[key] = totals.get(key, 0.0) + _to_float(link.get("parent_qty"))
    return totals


def _transport_child_denominators(indexes: LotTraceIndexes) -> dict[tuple[str, str, str], float]:
    totals: dict[tuple[str, str, str], float] = {}
    for link in indexes.links:
        if _as_str(link.get("link_type")) != "transport":
            continue
        key = _transport_child_key(link, indexes)
        totals[key] = totals.get(key, 0.0) + _to_float(link.get("parent_qty"))
    return totals


def _transport_child_key(
    link: dict[str, Any],
    indexes: LotTraceIndexes,
) -> tuple[str, str, str]:
    parent_lot_id = _as_str(link.get("parent_lot_id"))
    return (
        _as_str(link.get("child_lot_id")),
        _as_str(link.get("parent_item_id")) or _as_str(link.get("child_item_id")),
        _lot_uom(parent_lot_id, indexes),
    )


def _production_component_key(
    link: dict[str, Any],
    indexes: LotTraceIndexes,
) -> tuple[str, str, str]:
    parent_lot_id = _as_str(link.get("parent_lot_id"))
    return (
        _as_str(link.get("child_lot_id")),
        _as_str(link.get("parent_item_id")),
        _lot_uom(parent_lot_id, indexes),
    )


def _lot_total_qty(lot_id: str, indexes: LotTraceIndexes) -> float:
    qty = _to_float(indexes.lots.get(lot_id, {}).get("qty"))
    if qty > 0:
        return qty
    events = indexes.events_by_lot.get(lot_id, [])
    for event in events:
        if _as_str(event.get("event_type")) in {
            "production_output",
            "lane_receipt",
            "external_procurement_receipt",
            "estimated_source_receipt",
            "estimated_capacity_receipt",
            "opening_stock",
        }:
            event_qty = _to_float(event.get("qty"))
            if event_qty > 0:
                return event_qty
    return _to_float(events[0].get("qty")) if events else 0.0


def _build_mixed_customer_lots(
    indexes: LotTraceIndexes,
    visible_lot_ids: set[str],
    contribution_qty_by_lot: dict[str, float],
) -> list[dict[str, Any]]:
    mixed: list[dict[str, Any]] = []
    for lot_id in sorted(visible_lot_ids):
        if not _is_customer_lot(lot_id, indexes):
            continue
        incoming = [
            link
            for link in indexes.link_rows_by_child.get(lot_id, [])
            if _as_str(link.get("link_type")) == "transport"
        ]
        parent_lots = _unique(link.get("parent_lot_id") for link in incoming)
        if len(parent_lots) <= 1:
            continue
        visible_parent_lots = [lot for lot in parent_lots if contribution_qty_by_lot.get(lot, 0.0) > 0]
        other_parent_lots = [lot for lot in parent_lots if lot not in visible_parent_lots]
        total_qty = max(
            [_to_float(link.get("child_qty")) for link in incoming]
            + [_lot_total_qty(lot_id, indexes)]
        )
        visible_qty = min(total_qty, max(0.0, contribution_qty_by_lot.get(lot_id, 0.0))) if total_qty > 0 else 0.0
        other_qty = max(0.0, total_qty - visible_qty)
        mixed.append(
            {
                "lot_id": lot_id,
                "node_id": _lot_or_event_node(lot_id, indexes),
                "item_id": _lot_or_event_item(lot_id, indexes),
                "parent_lot_ids": parent_lots,
                "visible_parent_lot_ids": visible_parent_lots,
                "other_parent_lot_ids": other_parent_lots,
                "visible_contribution_qty": _round_qty(visible_qty),
                "other_contribution_qty": _round_qty(other_qty),
                "total_qty": _round_qty(total_qty),
                "visible_share": _round_ratio(visible_qty / total_qty) if total_qty > 0 else None,
                "is_mixed_with_other_origin": bool(other_parent_lots),
            }
        )
    return mixed


def _lot_node(
    lot_id: str,
    indexes: LotTraceIndexes,
    contribution_by_lot: dict[str, dict[str, Any]] | None = None,
    business_lot_ids_by_occurrence: dict[str, list[str]] | None = None,
    causal_event_count_by_lot: dict[str, int] | None = None,
) -> dict[str, Any]:
    lot = indexes.lots.get(lot_id, {})
    events = indexes.events_by_lot.get(lot_id, [])
    days = [_to_int(event.get("day")) for event in events]
    days = [day for day in days if day is not None]
    contribution = (contribution_by_lot or {}).get(lot_id) or {}
    identity = lot.get("identity") if isinstance(lot.get("identity"), dict) else {}
    business_lot_ids = list(
        (business_lot_ids_by_occurrence or {}).get(lot_id)
        or _explicit_business_lot_ids(lot)
    )
    stock_occurrence_id = (
        _as_str(lot.get("stock_occurrence_id"))
        or _as_str(identity.get("stock_occurrence_id"))
        or _as_str(lot.get("lot_occurrence_id"))
        or lot_id
    )
    causal_event_count = int((causal_event_count_by_lot or {}).get(lot_id, 0))
    return {
        "lot_id": lot_id,
        "entity_type": "stock_occurrence",
        "label": _as_str(lot.get("label")) or lot_id,
        "trace_scope": _as_str(lot.get("trace_scope")),
        "trace_scope_label": _as_str(lot.get("trace_scope_label")),
        "node_id": _as_str(lot.get("node_id")) or _lot_or_event_node(lot_id, indexes),
        "item_id": _as_str(lot.get("item_id")) or _lot_or_event_item(lot_id, indexes),
        "created_day": _to_int(lot.get("created_day")),
        "first_day": _to_int(lot.get("first_day")) if lot.get("first_day") != "" else (min(days) if days else None),
        "last_day": _to_int(lot.get("last_day")) if lot.get("last_day") != "" else (max(days) if days else None),
        "qty": _round_qty(_to_float(lot.get("qty"))),
        "uom": _as_str(lot.get("uom")),
        "source_type": _as_str(lot.get("source_type")),
        "source_id": _as_str(lot.get("source_id")),
        "production_campaign_id": _as_str(lot.get("production_campaign_id")),
        "scenario_id": _as_str(lot.get("scenario_id")),
        "planned_order_id": _as_str(lot.get("planned_order_id")),
        "baseline_reference_id": _as_str(lot.get("baseline_reference_id")),
        "causal_event_ids": _as_str(lot.get("causal_event_ids")),
        "causal_root_ids": _as_str(lot.get("causal_root_ids")),
        "causal_status": _as_str(lot.get("causal_status")),
        "origin_production_order_ids": _as_str(
            lot.get("origin_production_order_ids")
        ),
        "origin_production_contributions_json": _as_str(
            lot.get("origin_production_contributions_json")
        ),
        "origin_allocation_basis": _as_str(lot.get("origin_allocation_basis")),
        "business_lot_id": business_lot_ids[0] if len(business_lot_ids) == 1 else "",
        "business_lot_ids": business_lot_ids,
        "business_identity_status": _as_str(lot.get("business_identity_status"))
        or _as_str(identity.get("business_identity_status")),
        "business_identity_origin": _as_str(lot.get("business_identity_origin"))
        or _as_str(identity.get("business_identity_origin")),
        "business_identity_label": _as_str(lot.get("business_identity_label"))
        or _as_str(identity.get("business_identity_label")),
        "stock_occurrence_id": stock_occurrence_id,
        "shipment_id": _as_str(lot.get("shipment_id"))
        or _as_str(identity.get("shipment_id")),
        "shipment_identity_status": _as_str(lot.get("shipment_identity_status"))
        or _as_str(identity.get("shipment_identity_status")),
        "shipment_identity_origin": _as_str(lot.get("shipment_identity_origin"))
        or _as_str(identity.get("shipment_identity_origin")),
        "shipment_identity_label": _as_str(lot.get("shipment_identity_label"))
        or _as_str(identity.get("shipment_identity_label")),
        "logistics_lane_id": _as_str(lot.get("logistics_lane_id"))
        or _as_str(identity.get("logistics_lane_id")),
        "origin_trace_status": _as_str(lot.get("origin_trace_status")),
        "origin_trace_label": _as_str(lot.get("origin_trace_label")),
        "trace_status": _as_str(lot.get("trace_status")),
        "trace_reason": _as_str(lot.get("trace_reason")),
        "event_count": causal_event_count,
        "causal_event_count": causal_event_count,
        "available_event_count": int(lot.get("event_count") or len(events)),
        "pf_availability_status": _as_str(lot.get("pf_availability_status")),
        "pf_availability_status_label": _as_str(lot.get("pf_availability_status_label")),
        "contribution_qty": _round_qty(_to_float(contribution.get("contribution_qty"))),
        "contribution_basis": _as_str(contribution.get("contribution_basis")),
        "contribution_source_lot_id": _as_str(contribution.get("contribution_source_lot_id")),
        "contribution_parent_lot_id": _as_str(contribution.get("contribution_parent_lot_id")),
        "contribution_path_link_type": _as_str(contribution.get("contribution_path_link_type")),
    }


def _compact_link(
    link: dict[str, Any],
    contribution_by_lot: dict[str, dict[str, Any]] | None = None,
    indexes: LotTraceIndexes | None = None,
    production_denominators: dict[tuple[str, str, str], float] | None = None,
) -> dict[str, Any]:
    child_lot = _as_str(link.get("child_lot_id"))
    child_contribution = (contribution_by_lot or {}).get(child_lot) or {}
    path_contributions = child_contribution.get("_path_contributions") or {}
    link_contribution_qty = _to_float(path_contributions.get(_as_str(link.get("_link_id"))))
    child_total = _to_float(link.get("child_qty"))
    link_type = _as_str(link.get("link_type"))
    allocation_share = _to_float(link.get("allocation_share"))
    allocation_basis = "source_allocation_share"
    if link_type == "production" and indexes is not None:
        denominator = (production_denominators or {}).get(
            _production_component_key(link, indexes),
            0.0,
        )
        allocation_share = (
            _to_float(link.get("parent_qty")) / denominator
            if denominator > 0
            else 0.0
        )
        allocation_basis = "same_child_same_component_same_uom"
    shipment_id = ""
    departure_day = None
    arrival_day = None
    handling_unit_id = ""
    trace_status = _as_str(link.get("trace_status"))
    trace_reason = _as_str(link.get("trace_reason"))
    if indexes is not None:
        shipment_id = _transport_value(link, indexes, ("shipment_id", "consignment_id"))
        departure_day = _transport_departure_day(link, indexes)
        arrival_day = _transport_arrival_day(link)
        handling_unit_id = _transport_value(
            link,
            indexes,
            ("handling_unit_id", "handling_unit", "transport_unit_id", "container_id"),
        )
    return {
        "link_id": link["_link_id"],
        "day": _to_int(link.get("day")),
        "link_type": link_type,
        "parent_lot_id": _as_str(link.get("parent_lot_id")),
        "parent_node_id": _as_str(link.get("parent_node_id")),
        "parent_item_id": _as_str(link.get("parent_item_id")),
        "child_lot_id": _as_str(link.get("child_lot_id")),
        "child_node_id": _as_str(link.get("child_node_id")),
        "child_item_id": _as_str(link.get("child_item_id")),
        "parent_qty": _round_qty(_to_float(link.get("parent_qty"))),
        "child_qty": _round_qty(_to_float(link.get("child_qty"))),
        "allocation_share": _round_ratio(allocation_share),
        "component_allocation_share": (
            _round_ratio(allocation_share) if link_type == "production" else None
        ),
        "allocation_basis": allocation_basis,
        "source_id": _as_str(link.get("source_id")),
        "production_campaign_id": _as_str(link.get("production_campaign_id")),
        "scenario_id": _as_str(link.get("scenario_id")),
        "planned_order_id": _as_str(link.get("planned_order_id")),
        "baseline_reference_id": _as_str(link.get("baseline_reference_id")),
        "causal_event_ids": _as_str(link.get("causal_event_ids")),
        "causal_root_ids": _as_str(link.get("causal_root_ids")),
        "causal_status": _as_str(link.get("causal_status")),
        "origin_production_order_ids": _as_str(
            link.get("origin_production_order_ids")
        ),
        "origin_production_contributions_json": _as_str(
            link.get("origin_production_contributions_json")
        ),
        "origin_allocation_basis": _as_str(
            link.get("origin_allocation_basis")
        ),
        "required_item_id": _as_str(link.get("required_item_id")),
        "consumed_item_id": _as_str(link.get("consumed_item_id")),
        "replacement_qty": _round_qty(_to_float(link.get("replacement_qty"))),
        "replacement_reason": _as_str(link.get("replacement_reason")),
        "replacement_transition_id": _as_str(
            link.get("replacement_transition_id")
        ),
        "business_lot_id": _as_str(link.get("business_lot_id"))
        or _as_str(link.get("business_batch_id")),
        "parent_business_lot_id": _as_str(link.get("parent_business_lot_id"))
        or _as_str(link.get("parent_business_batch_id")),
        "parent_stock_occurrence_id": _as_str(link.get("parent_stock_occurrence_id"))
        or _as_str(link.get("parent_lot_occurrence_id"))
        or _as_str(link.get("parent_stock_lot_id")),
        "child_business_lot_id": _as_str(link.get("child_business_lot_id"))
        or _as_str(link.get("child_business_batch_id")),
        "child_stock_occurrence_id": _as_str(link.get("child_stock_occurrence_id"))
        or _as_str(link.get("child_lot_occurrence_id"))
        or _as_str(link.get("child_stock_lot_id")),
        "provenance_batch_id": _as_str(link.get("provenance_batch_id")),
        "shipment_id": shipment_id,
        "departure_day": departure_day,
        "arrival_day": arrival_day,
        "handling_unit_id": handling_unit_id,
        "mrp_order_id": _as_str(link.get("mrp_order_id")),
        "order_day": _to_int(link.get("order_day")),
        "mrp_decision_day": _to_int(link.get("mrp_decision_day")),
        "requested_release_day": _to_int(link.get("requested_release_day")),
        "planned_release_day": _to_int(link.get("planned_release_day")),
        "actual_release_day": _to_int(link.get("actual_release_day")),
        "estimated_release_day": _to_int(link.get("estimated_release_day")),
        "planned_arrival_day": _to_int(link.get("planned_arrival_day")),
        "actual_receipt_day": _to_int(link.get("actual_receipt_day")),
        "procurement_lead_days": _to_int(
            link.get("procurement_lead_days")
        ),
        "procurement_lead_basis": _as_str(
            link.get("procurement_lead_basis")
        ),
        "procurement_status": _as_str(link.get("procurement_status")),
        "supplier_node_id": _as_str(link.get("supplier_node_id")),
        "procurement_destination_node_id": _as_str(
            link.get("procurement_destination_node_id")
        ),
        "procurement_edge_id": _as_str(link.get("procurement_edge_id")),
        "procurement_trace_status": _as_str(
            link.get("procurement_trace_status")
        ),
        "procurement_trace_reason": _as_str(
            link.get("procurement_trace_reason")
        ),
        "trace_status": trace_status,
        "trace_reason": trace_reason,
        "contribution_qty": _round_qty(link_contribution_qty),
        "contribution_share_of_child": (
            _round_ratio(link_contribution_qty / child_total)
            if child_total > 0
            else None
        ),
        "contribution_basis": _as_str(child_contribution.get("contribution_basis")),
    }


def _transport_arrival_day(link: dict[str, Any]) -> int | None:
    for field in ("arrival_day", "receipt_day", "day"):
        day = _to_int(link.get(field))
        if day is not None:
            return day
    return None


def _transport_departure_day(
    link: dict[str, Any],
    indexes: LotTraceIndexes,
) -> int | None:
    for field in ("departure_day", "ship_day", "dispatch_day"):
        day = _to_int(link.get(field))
        if day is not None:
            return day
    parent_lot_id = _as_str(link.get("parent_lot_id"))
    source_id = _as_str(link.get("source_id"))
    arrival_day = _transport_arrival_day(link)
    candidates = []
    for event in indexes.events_by_lot.get(parent_lot_id, []):
        if _as_str(event.get("event_type")) != "lane_ship":
            continue
        if source_id and _as_str(event.get("source_id")) not in {"", source_id}:
            continue
        day = _to_int(event.get("day"))
        if day is not None and (arrival_day is None or day <= arrival_day):
            candidates.append(day)
    return max(candidates) if candidates else None


def _transport_value(
    link: dict[str, Any],
    indexes: LotTraceIndexes,
    fields: tuple[str, ...],
) -> str:
    for field in fields:
        value = _as_str(link.get(field))
        if value:
            return value
    expected_shipment_id = _as_str(
        link.get("shipment_id") or link.get("consignment_id")
    )
    expected_source_id = _as_str(link.get("source_id"))
    expected_arrival_day = _transport_arrival_day(link)
    lot_ids = (
        _as_str(link.get("parent_lot_id")),
        _as_str(link.get("child_lot_id")),
    )
    for lot_id in lot_ids:
        for event in indexes.events_by_lot.get(lot_id, []):
            event_shipment_id = _as_str(
                event.get("shipment_id") or event.get("consignment_id")
            )
            if expected_shipment_id:
                if event_shipment_id != expected_shipment_id:
                    continue
            else:
                event_source_id = _as_str(event.get("source_id"))
                if (
                    expected_source_id
                    and event_source_id
                    and event_source_id != expected_source_id
                ):
                    continue
                event_day = _to_int(event.get("day"))
                if (
                    expected_arrival_day is not None
                    and event_day is not None
                    and event_day > expected_arrival_day
                ):
                    continue
            for field in fields:
                value = _as_str(event.get(field))
                if value:
                    return value
    return ""


def _remember_procurement_metadata(
    group: dict[str, Any],
    source: dict[str, Any],
) -> None:
    text_fields = {
        "mrp_order_ids": "mrp_order_id",
        "procurement_statuses": "procurement_status",
        "procurement_lead_bases": "procurement_lead_basis",
        "procurement_trace_statuses": "procurement_trace_status",
        "procurement_trace_reasons": "procurement_trace_reason",
    }
    for target_field, source_field in text_fields.items():
        value = _as_str(source.get(source_field))
        if value:
            group[target_field].add(value)
    day_fields = {
        "order_days": "order_day",
        "mrp_decision_days": "mrp_decision_day",
        "requested_release_days": "requested_release_day",
        "planned_release_days": "planned_release_day",
        "actual_release_days": "actual_release_day",
        "estimated_release_days": "estimated_release_day",
        "planned_arrival_days": "planned_arrival_day",
        "actual_receipt_days": "actual_receipt_day",
        "procurement_lead_days": "procurement_lead_days",
    }
    for target_field, source_field in day_fields.items():
        value = _to_int(source.get(source_field))
        if value is not None:
            group[target_field].add(value)
    supplier_node_id = _as_str(source.get("supplier_node_id"))
    destination_node_id = _as_str(
        source.get("procurement_destination_node_id")
    )
    if supplier_node_id:
        group["from_node_ids"].add(supplier_node_id)
    if destination_node_id:
        group["to_node_ids"].add(destination_node_id)


def _optional_int_set(value: Any) -> set[int]:
    parsed = _to_int(value)
    return {parsed} if parsed is not None else set()


def _transport_uom(link: dict[str, Any], indexes: LotTraceIndexes) -> str:
    for field in ("uom", "parent_uom", "child_uom"):
        uom = _normalize_uom(link.get(field))
        if uom:
            return uom
    parent_uom = _lot_uom(_as_str(link.get("parent_lot_id")), indexes)
    child_uom = _lot_uom(_as_str(link.get("child_lot_id")), indexes)
    return parent_uom or child_uom


def _lot_uom(lot_id: str, indexes: LotTraceIndexes) -> str:
    uom = _normalize_uom(indexes.lots.get(lot_id, {}).get("uom"))
    if uom:
        return uom
    for event in indexes.events_by_lot.get(lot_id, []):
        uom = _normalize_uom(event.get("uom"))
        if uom:
            return uom
    return ""


def _normalize_uom(value: Any) -> str:
    unit = _as_str(value).strip().upper()
    return {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITES": "UN",
        "UNITS": "UN",
        "ZUN": "UN",
    }.get(unit, unit)


def _inferred_transport_group_id(
    arrival_day: int | None,
    from_node_id: str,
    to_node_id: str,
    item_id: str,
    uom: str,
    source_id: str,
) -> str:
    return ":".join(
        [
            "inferred_group",
            str(arrival_day) if arrival_day is not None else "unknown_day",
            from_node_id or "unknown_origin",
            to_node_id or "unknown_destination",
            item_id or "unknown_item",
            uom or "unknown_uom",
            source_id or "unknown_source",
        ]
    )


def _is_customer_lot(lot_id: str, indexes: LotTraceIndexes) -> bool:
    node_id = _lot_or_event_node(lot_id, indexes)
    if node_id.startswith("C-"):
        return True
    return any(_as_str(link.get("child_node_id")).startswith("C-") for link in indexes.link_rows_by_child.get(lot_id, []))


def _lot_or_event_node(lot_id: str, indexes: LotTraceIndexes) -> str:
    lot_node = _as_str(indexes.lots.get(lot_id, {}).get("node_id"))
    if lot_node:
        return lot_node
    for event in indexes.events_by_lot.get(lot_id, []):
        node = _as_str(event.get("node_id"))
        if node:
            return node
    for link in indexes.link_rows_by_child.get(lot_id, []):
        node = _as_str(link.get("child_node_id"))
        if node:
            return node
    for link in indexes.link_rows_by_parent.get(lot_id, []):
        node = _as_str(link.get("parent_node_id"))
        if node:
            return node
    return ""


def _lot_or_event_item(lot_id: str, indexes: LotTraceIndexes) -> str:
    lot_item = _as_str(indexes.lots.get(lot_id, {}).get("item_id"))
    if lot_item:
        return lot_item
    for event in indexes.events_by_lot.get(lot_id, []):
        item = _as_str(event.get("item_id"))
        if item:
            return item
    for link in indexes.link_rows_by_child.get(lot_id, []):
        item = _as_str(link.get("child_item_id"))
        if item:
            return item
    for link in indexes.link_rows_by_parent.get(lot_id, []):
        item = _as_str(link.get("parent_item_id"))
        if item:
            return item
    return ""


def _unique(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _as_str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _to_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number


def _to_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _round_qty(value: float) -> float:
    return round(float(value), 6)


def _round_ratio(value: float) -> float:
    return round(float(value), 6)


def _day_sort(value: Any) -> int:
    day = _to_int(value)
    return day if day is not None else 10**12
