from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable


LOT_TRACE_DIRECTIONS = {"all", "upstream", "downstream"}
LOT_TRACE_WALK_LIMIT = 5000


@dataclass
class LotTraceIndexes:
    lots: dict[str, dict[str, Any]]
    events_by_lot: dict[str, list[dict[str, Any]]]
    links: list[dict[str, Any]]
    children_by_parent: dict[str, set[str]]
    parents_by_child: dict[str, set[str]]
    link_rows_by_parent: dict[str, list[dict[str, Any]]]
    link_rows_by_child: dict[str, list[dict[str, Any]]]
    _walk_cache: dict[tuple[str, str], list[str]] | None = None
    _downstream_stats_cache: dict[str, dict[str, Any]] | None = None
    _upstream_stats_cache: dict[str, dict[str, Any]] | None = None
    _upstream_roots_cache: dict[str, set[str]] | None = None


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


def lot_trace_downstream_stats(indexes: LotTraceIndexes, lot_id: str) -> dict[str, Any]:
    root = _as_str(lot_id)
    if indexes._downstream_stats_cache is None:
        indexes._downstream_stats_cache = {}
    if root in indexes._downstream_stats_cache:
        return dict(indexes._downstream_stats_cache[root])
    downstream_lot_ids = _cached_bounded_walk(indexes, "downstream", root)
    link_types: set[str] = set()
    nodes: set[str] = set()
    finished_product_lots = 0
    for child in downstream_lot_ids:
        for row in indexes.events_by_lot.get(child, []):
            node_id = _as_str(row.get("node_id"))
            if node_id:
                nodes.add(node_id)
            if _as_str(row.get("event_type")) == "production_output":
                finished_product_lots += 1
        _collect_link_types(indexes.link_rows_by_parent.get(child, []), link_types)
    _collect_link_types(indexes.link_rows_by_parent.get(root, []), link_types)
    stats = {
        "downstream_lot_count": len(downstream_lot_ids),
        "downstream_node_count": len(nodes),
        "downstream_finished_product_lot_count": finished_product_lots,
        "downstream_link_types": sorted(link_types),
    }
    indexes._downstream_stats_cache[root] = stats
    return dict(stats)


def lot_trace_upstream_stats(indexes: LotTraceIndexes, lot_id: str) -> dict[str, Any]:
    root = _as_str(lot_id)
    if indexes._upstream_stats_cache is None:
        indexes._upstream_stats_cache = {}
    if root in indexes._upstream_stats_cache:
        return dict(indexes._upstream_stats_cache[root])
    upstream_lot_ids = _cached_bounded_walk(indexes, "upstream", root)
    link_types: set[str] = set()
    nodes: set[str] = set()
    supplier_material_lots = 0
    for parent in upstream_lot_ids:
        for row in indexes.events_by_lot.get(parent, []):
            node_id = _as_str(row.get("node_id"))
            if node_id:
                nodes.add(node_id)
            if _as_str(row.get("event_type")) in {
                "external_procurement_receipt",
                "estimated_source_receipt",
                "estimated_capacity_receipt",
                "opening_stock",
            }:
                supplier_material_lots += 1
        _collect_link_types(indexes.link_rows_by_child.get(parent, []), link_types)
    _collect_link_types(indexes.link_rows_by_child.get(root, []), link_types)
    stats = {
        "upstream_lot_count": len(upstream_lot_ids),
        "upstream_node_count": len(nodes),
        "upstream_material_lot_count": supplier_material_lots,
        "upstream_link_types": sorted(link_types),
    }
    indexes._upstream_stats_cache[root] = stats
    return dict(stats)


def lot_trace_upstream_roots(indexes: LotTraceIndexes, lot_id: str) -> set[str]:
    root = _as_str(lot_id)
    if not root:
        return set()
    if indexes._upstream_roots_cache is None:
        indexes._upstream_roots_cache = {}
    if root in indexes._upstream_roots_cache:
        return set(indexes._upstream_roots_cache[root])
    roots: set[str] = set()
    visited: set[str] = {root}
    queue: deque[str] = deque(sorted(indexes.parents_by_child.get(root, set())))
    while queue and len(visited) - 1 < LOT_TRACE_WALK_LIMIT:
        parent = _as_str(queue.popleft())
        if not parent or parent in visited:
            continue
        visited.add(parent)
        grandparents = indexes.parents_by_child.get(parent, set())
        if grandparents:
            queue.extend(sorted(grandparents))
        else:
            roots.add(parent)
    indexes._upstream_roots_cache[root] = roots
    return roots


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


def _bounded_walk(adjacency: dict[str, set[str]], root: str) -> list[str]:
    if not root:
        return []
    seen: set[str] = {root}
    out: list[str] = []
    queue: deque[str] = deque(sorted(adjacency.get(root, set())))
    while queue and len(out) < LOT_TRACE_WALK_LIMIT:
        current = _as_str(queue.popleft())
        if not current or current in seen:
            continue
        seen.add(current)
        out.append(current)
        queue.extend(sorted(adjacency.get(current, set())))
    return out


def _cached_bounded_walk(indexes: LotTraceIndexes, direction: str, root: str) -> list[str]:
    if indexes._walk_cache is None:
        indexes._walk_cache = {}
    cache_key = (direction, root)
    cached = indexes._walk_cache.get(cache_key)
    if cached is not None:
        return list(cached)
    adjacency = indexes.parents_by_child if direction == "upstream" else indexes.children_by_parent
    walked = _bounded_walk(adjacency, root)
    indexes._walk_cache[cache_key] = walked
    return list(walked)


def _collect_link_types(rows: Iterable[dict[str, Any]], link_types: set[str]) -> None:
    for row in rows:
        link_type = _as_str(row.get("link_type"))
        if link_type:
            link_types.add(link_type)


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
