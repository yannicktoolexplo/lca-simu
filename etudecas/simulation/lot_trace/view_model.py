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
    visible_events = [
        event
        for lot in reach["lot_ids"]
        for event in indexes.events_by_lot.get(lot, [])
    ]
    nodes = [_lot_node(lot, indexes) for lot in reach["lot_ids"]]
    links = [_compact_link(link) for link in visible_links]
    component_groups = _build_component_groups(visible_links)
    transport_groups = _build_transport_groups(visible_links)
    mixed_customer_lots = _build_mixed_customer_lots(indexes, visible_lot_ids)
    snapshot = _build_snapshot(reach, visible_links, visible_events, nodes)

    return {
        "version": 1,
        "lot_id": reach["root_lot_id"],
        "direction": reach["direction"],
        "root_lot": indexes.lots.get(reach["root_lot_id"], {}),
        "snapshot": snapshot,
        "nodes": nodes,
        "links": links,
        "component_groups": component_groups,
        "transport_groups": transport_groups,
        "mixed_customer_lots": mixed_customer_lots,
        "summary": {
            "lot_count": len(reach["lot_ids"]),
            "upstream_lot_count": len(reach["upstream_lot_ids"]),
            "downstream_lot_count": len(reach["downstream_lot_ids"]),
            "event_count": len(visible_events),
            "link_count": len(visible_links),
            "component_group_count": len(component_groups),
            "transport_group_count": len(transport_groups),
            "mixed_customer_lot_count": len(mixed_customer_lots),
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


def _build_component_groups(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for link in links:
        if _as_str(link.get("link_type")) != "production":
            continue
        key = (
            _to_int(link.get("day")),
            _as_str(link.get("child_lot_id")),
            _as_str(link.get("parent_node_id")),
            _as_str(link.get("parent_item_id")),
            _as_str(link.get("production_campaign_id")),
        )
        group = grouped.setdefault(
            key,
            {
                "day": key[0],
                "child_lot_id": key[1],
                "node_id": key[2],
                "item_id": key[3],
                "production_campaign_id": key[4],
                "parent_lot_ids": set(),
                "lot_count": 0,
                "qty": 0.0,
                "child_qty": 0.0,
            },
        )
        group["parent_lot_ids"].add(_as_str(link.get("parent_lot_id")))
        group["qty"] += _to_float(link.get("parent_qty"))
        group["child_qty"] = max(group["child_qty"], _to_float(link.get("child_qty")))

    return [
        {
            **group,
            "parent_lot_ids": sorted(group["parent_lot_ids"]),
            "lot_count": len(group["parent_lot_ids"]),
            "qty": _round_qty(group["qty"]),
            "child_qty": _round_qty(group["child_qty"]),
        }
        for group in sorted(grouped.values(), key=lambda row: (_day_sort(row["day"]), row["item_id"]))
    ]


def _build_transport_groups(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for link in links:
        if _as_str(link.get("link_type")) != "transport":
            continue
        day = _to_int(link.get("day"))
        item_id = _as_str(link.get("child_item_id")) or _as_str(link.get("parent_item_id"))
        key = (
            day,
            _as_str(link.get("parent_node_id")),
            _as_str(link.get("child_node_id")),
            item_id,
        )
        group = grouped.setdefault(
            key,
            {
                "day": day,
                "from_node_id": key[1],
                "to_node_id": key[2],
                "item_id": item_id,
                "parent_lot_ids": set(),
                "child_lot_ids": set(),
                "source_ids": set(),
                "shipped_qty": 0.0,
                "received_qty_by_child": {},
            },
        )
        parent_lot = _as_str(link.get("parent_lot_id"))
        child_lot = _as_str(link.get("child_lot_id"))
        if parent_lot:
            group["parent_lot_ids"].add(parent_lot)
        if child_lot:
            group["child_lot_ids"].add(child_lot)
        source_id = _as_str(link.get("source_id"))
        if source_id:
            group["source_ids"].add(source_id)
        group["shipped_qty"] += _to_float(link.get("parent_qty"))
        child_qty = _to_float(link.get("child_qty"))
        group["received_qty_by_child"][child_lot] = max(
            group["received_qty_by_child"].get(child_lot, 0.0),
            child_qty,
        )

    out = []
    for group in sorted(
        grouped.values(),
        key=lambda row: (_day_sort(row["day"]), row["from_node_id"], row["to_node_id"], row["item_id"]),
    ):
        received_qty = sum(group["received_qty_by_child"].values())
        out.append(
            {
                "day": group["day"],
                "from_node_id": group["from_node_id"],
                "to_node_id": group["to_node_id"],
                "item_id": group["item_id"],
                "parent_lot_ids": sorted(group["parent_lot_ids"]),
                "child_lot_ids": sorted(group["child_lot_ids"]),
                "source_ids": sorted(group["source_ids"]),
                "parent_lot_count": len(group["parent_lot_ids"]),
                "child_lot_count": len(group["child_lot_ids"]),
                "shipped_qty": _round_qty(group["shipped_qty"]),
                "received_qty": _round_qty(received_qty),
                "is_consolidated": len(group["parent_lot_ids"]) > 1 or len(group["child_lot_ids"]) > 1,
            }
        )
    return out


def _build_mixed_customer_lots(
    indexes: LotTraceIndexes,
    visible_lot_ids: set[str],
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
        visible_parent_lots = [lot for lot in parent_lots if lot in visible_lot_ids]
        other_parent_lots = [lot for lot in parent_lots if lot not in visible_lot_ids]
        total_qty = max(
            [_to_float(link.get("child_qty")) for link in incoming]
            + [_to_float(indexes.lots.get(lot_id, {}).get("qty"))]
        )
        visible_qty = sum(
            _to_float(link.get("parent_qty"))
            for link in incoming
            if _as_str(link.get("parent_lot_id")) in visible_lot_ids
        )
        other_qty = sum(
            _to_float(link.get("parent_qty"))
            for link in incoming
            if _as_str(link.get("parent_lot_id")) not in visible_lot_ids
        )
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


def _lot_node(lot_id: str, indexes: LotTraceIndexes) -> dict[str, Any]:
    lot = indexes.lots.get(lot_id, {})
    events = indexes.events_by_lot.get(lot_id, [])
    days = [_to_int(event.get("day")) for event in events]
    days = [day for day in days if day is not None]
    return {
        "lot_id": lot_id,
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
        "event_count": int(lot.get("event_count") or len(events)),
        "pf_availability_status": _as_str(lot.get("pf_availability_status")),
        "pf_availability_status_label": _as_str(lot.get("pf_availability_status_label")),
    }


def _compact_link(link: dict[str, Any]) -> dict[str, Any]:
    return {
        "link_id": link["_link_id"],
        "day": _to_int(link.get("day")),
        "link_type": _as_str(link.get("link_type")),
        "parent_lot_id": _as_str(link.get("parent_lot_id")),
        "parent_node_id": _as_str(link.get("parent_node_id")),
        "parent_item_id": _as_str(link.get("parent_item_id")),
        "child_lot_id": _as_str(link.get("child_lot_id")),
        "child_node_id": _as_str(link.get("child_node_id")),
        "child_item_id": _as_str(link.get("child_item_id")),
        "parent_qty": _round_qty(_to_float(link.get("parent_qty"))),
        "child_qty": _round_qty(_to_float(link.get("child_qty"))),
        "allocation_share": _round_ratio(_to_float(link.get("allocation_share"))),
        "source_id": _as_str(link.get("source_id")),
        "production_campaign_id": _as_str(link.get("production_campaign_id")),
    }


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
