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
    component_groups = _build_component_groups(visible_links)
    transport_groups = _build_transport_groups(visible_links)
    contribution_by_lot = _downstream_contribution_by_lot(
        indexes,
        reach["root_lot_id"],
        visible_lot_ids,
    )
    contribution_qty_by_lot = {
        lot_id: _to_float(row.get("contribution_qty"))
        for lot_id, row in contribution_by_lot.items()
    }
    nodes = [_lot_node(lot, indexes, contribution_by_lot) for lot in reach["lot_ids"]]
    links = [_compact_link(link, contribution_by_lot) for link in visible_links]
    mixed_customer_lots = _build_mixed_customer_lots(indexes, visible_lot_ids, contribution_qty_by_lot)
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


def _downstream_contribution_by_lot(
    indexes: LotTraceIndexes,
    root_lot_id: str,
    visible_lot_ids: set[str],
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
    queue = [root]
    guard = 0
    while queue and guard < 10000:
        guard += 1
        parent = queue.pop(0)
        parent_contribution = _to_float((contributions.get(parent) or {}).get("contribution_qty"))
        if parent_contribution <= 0:
            continue
        parent_total = _lot_total_qty(parent, indexes)
        parent_share = min(1.0, max(0.0, parent_contribution / parent_total)) if parent_total > 0 else 1.0
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
                traced_parent_qty = min(parent_link_qty, parent_link_qty * parent_share)
                traced_qty = child_link_qty * min(1.0, traced_parent_qty / parent_link_qty)
                basis = "production_bom_consumption_share"
            else:
                link_qty = parent_link_qty or child_link_qty
                if link_qty <= 0:
                    continue
                traced_qty = link_qty * parent_share
                basis = "transport_quantity_share"
            if traced_qty <= 0:
                continue
            old = _to_float((contributions.get(child) or {}).get("contribution_qty"))
            child_total = _lot_total_qty(child, indexes)
            new_value = min(child_total, old + traced_qty) if child_total > 0 else old + traced_qty
            if new_value > old + 1e-9:
                contributions[child] = {
                    "contribution_qty": new_value,
                    "contribution_basis": basis,
                    "contribution_source_lot_id": root,
                    "contribution_parent_lot_id": parent,
                    "contribution_path_link_type": link_type,
                    "contribution_parent_share": _round_ratio(parent_share),
                }
                queue.append(child)
    return contributions


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
) -> dict[str, Any]:
    lot = indexes.lots.get(lot_id, {})
    events = indexes.events_by_lot.get(lot_id, [])
    days = [_to_int(event.get("day")) for event in events]
    days = [day for day in days if day is not None]
    contribution = (contribution_by_lot or {}).get(lot_id) or {}
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
        "contribution_qty": _round_qty(_to_float(contribution.get("contribution_qty"))),
        "contribution_basis": _as_str(contribution.get("contribution_basis")),
        "contribution_source_lot_id": _as_str(contribution.get("contribution_source_lot_id")),
        "contribution_parent_lot_id": _as_str(contribution.get("contribution_parent_lot_id")),
        "contribution_path_link_type": _as_str(contribution.get("contribution_path_link_type")),
    }


def _compact_link(
    link: dict[str, Any],
    contribution_by_lot: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    child_lot = _as_str(link.get("child_lot_id"))
    child_contribution = (contribution_by_lot or {}).get(child_lot) or {}
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
        "contribution_qty": _round_qty(_to_float(child_contribution.get("contribution_qty"))),
        "contribution_basis": _as_str(child_contribution.get("contribution_basis")),
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
