from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable


LOT_TRACE_DIRECTIONS = {"all", "upstream", "downstream"}


@dataclass(frozen=True)
class LotTraceIndexes:
    lots: dict[str, dict[str, Any]]
    events_by_lot: dict[str, list[dict[str, Any]]]
    links: list[dict[str, Any]]
    children_by_parent: dict[str, set[str]]
    parents_by_child: dict[str, set[str]]
    link_rows_by_parent: dict[str, list[dict[str, Any]]]
    link_rows_by_child: dict[str, list[dict[str, Any]]]


def build_lot_trace_indexes(payload: dict[str, Any]) -> LotTraceIndexes:
    lots = {
        _as_str(lot_id): lot
        for lot_id, lot in (payload.get("lots") or {}).items()
        if _as_str(lot_id)
    }
    events_by_lot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in payload.get("events") or []:
        lot_id = _as_str(event.get("lot_id"))
        if lot_id:
            events_by_lot[lot_id].append(event)

    links: list[dict[str, Any]] = []
    children_by_parent: dict[str, set[str]] = defaultdict(set)
    parents_by_child: dict[str, set[str]] = defaultdict(set)
    link_rows_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    link_rows_by_child: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for ordinal, row in enumerate(payload.get("genealogy") or []):
        parent_lot = _as_str(row.get("parent_lot_id"))
        child_lot = _as_str(row.get("child_lot_id"))
        if not parent_lot or not child_lot:
            continue
        link = dict(row)
        link["_link_id"] = _link_id(row, ordinal)
        links.append(link)
        children_by_parent[parent_lot].add(child_lot)
        parents_by_child[child_lot].add(parent_lot)
        link_rows_by_parent[parent_lot].append(link)
        link_rows_by_child[child_lot].append(link)

    return LotTraceIndexes(
        lots=lots,
        events_by_lot=dict(events_by_lot),
        links=links,
        children_by_parent=dict(children_by_parent),
        parents_by_child=dict(parents_by_child),
        link_rows_by_parent=dict(link_rows_by_parent),
        link_rows_by_child=dict(link_rows_by_child),
    )


def reachable_lot_ids(
    indexes: LotTraceIndexes,
    lot_id: str,
    direction: str = "all",
) -> dict[str, list[str]]:
    direction = _normalize_direction(direction)
    root = _as_str(lot_id)
    upstream = _walk(indexes.parents_by_child, root) if direction in {"all", "upstream"} else []
    downstream = _walk(indexes.children_by_parent, root) if direction in {"all", "downstream"} else []
    if direction == "upstream":
        visible = [root, *upstream]
    elif direction == "downstream":
        visible = [root, *downstream]
    else:
        visible = [root, *upstream, *downstream]
    return {
        "root_lot_id": root,
        "direction": direction,
        "upstream_lot_ids": _sort_lot_ids(upstream, indexes),
        "downstream_lot_ids": _sort_lot_ids(downstream, indexes),
        "lot_ids": _sort_lot_ids(_unique(visible), indexes),
    }


def _walk(adjacency: dict[str, set[str]], root: str) -> list[str]:
    if not root:
        return []
    seen: set[str] = set()
    queue: deque[str] = deque([root])
    while queue:
        current = queue.popleft()
        for nxt in sorted(adjacency.get(current, set())):
            if not nxt or nxt == root or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return list(seen)


def _sort_lot_ids(lot_ids: Iterable[str], indexes: LotTraceIndexes) -> list[str]:
    return sorted(_unique(lot_ids), key=lambda lot_id: (_day_sort(_lot_day(lot_id, indexes)), lot_id))


def _lot_day(lot_id: str, indexes: LotTraceIndexes) -> int | None:
    lot = indexes.lots.get(lot_id, {})
    day = _to_int(lot.get("created_day"))
    if day is not None:
        return day
    days = [_to_int(event.get("day")) for event in indexes.events_by_lot.get(lot_id, [])]
    days = [day for day in days if day is not None]
    return min(days) if days else None


def _normalize_direction(direction: str) -> str:
    direction = _as_str(direction).lower()
    aliases = {
        "all": "all",
        "complete": "all",
        "full": "all",
        "chaine_complete": "all",
        "upstream": "upstream",
        "amont": "upstream",
        "downstream": "downstream",
        "aval": "downstream",
    }
    normalized = aliases.get(direction, direction)
    if normalized not in LOT_TRACE_DIRECTIONS:
        raise ValueError(f"unknown lot trace direction: {direction}")
    return normalized


def _link_id(row: dict[str, Any], ordinal: int) -> str:
    return "|".join(
        [
            str(ordinal),
            _as_str(row.get("link_type")),
            _as_str(row.get("day")),
            _as_str(row.get("parent_lot_id")),
            _as_str(row.get("child_lot_id")),
            _as_str(row.get("source_id")),
        ]
    )


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


def _to_int(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _day_sort(value: Any) -> int:
    day = _to_int(value)
    return day if day is not None else 10**12
