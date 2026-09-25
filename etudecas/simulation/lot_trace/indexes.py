"""Lot genealogy indexes and dated stock context."""

from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable
import math
from pathlib import Path
from .schema import read_csv_rows, to_float


# Indexes

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
    _production_totals: dict | None = None
    _transport_totals: dict | None = None


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


# Stock context

@dataclass(frozen=True)
class LotTraceStockContextSources:
    input_stocks_csv: Path | None = None
    output_products_csv: Path | None = None
    dc_stocks_csv: Path | None = None
    demand_service_csv: Path | None = None
    supplier_stocks_csv: Path | None = None


def build_lot_trace_stock_context(
    events: list[dict[str, Any]],
    genealogy: list[dict[str, Any]],
    sources: LotTraceStockContextSources,
) -> dict[str, dict[str, Any]]:
    relevant_keys = _relevant_stock_keys(events, genealogy)
    if not relevant_keys:
        return {}

    relevant_by_pair: dict[tuple[str, str], set[int]] = defaultdict(set)
    for node_id, item_id, day in relevant_keys:
        relevant_by_pair[(node_id, item_id)].add(day)

    out: dict[str, dict[str, Any]] = {}

    def set_context(
        *,
        node_id: str,
        item_id: str,
        day: int,
        label: str,
        before: float | None = None,
        after: float | None = None,
        delta: float | None = None,
        extra: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> None:
        if not node_id or not item_id:
            return
        if (node_id, item_id, day) not in relevant_keys:
            return
        ctx_key = _stock_context_key(node_id, item_id, day)
        if ctx_key in out and not overwrite:
            return
        payload: dict[str, Any] = {
            "node_id": node_id,
            "item_id": item_id,
            "day": day,
            "label": label,
        }
        if before is not None and not math.isnan(before):
            payload["before_qty"] = round(before, 6)
        if after is not None and not math.isnan(after):
            payload["after_qty"] = round(after, 6)
        if delta is not None and not math.isnan(delta):
            payload["delta_qty"] = round(delta, 6)
        elif before is not None and after is not None and not math.isnan(before) and not math.isnan(after):
            payload["delta_qty"] = round(after - before, 6)
        if extra:
            payload.update(extra)
        out[ctx_key] = payload

    if sources.input_stocks_csv is not None and sources.input_stocks_csv.exists():
        for row in read_csv_rows(sources.input_stocks_csv):
            node_id = str(row.get("node_id") or "")
            item_id = str(row.get("item_id") or "")
            day = int(to_float(row.get("day")) or 0)
            if (node_id, item_id, day) not in relevant_keys:
                continue
            before = to_float(row.get("stock_before_production"))
            after = to_float(row.get("stock_end_of_day"))
            set_context(
                node_id=node_id,
                item_id=item_id,
                day=day,
                label="stock intrant usine",
                before=before,
                after=after,
                overwrite=True,
            )

    _add_end_of_day_context(
        sources.output_products_csv,
        stock_field="stock_end_of_day",
        label="stock produit usine fin de jour",
        relevant_by_pair=relevant_by_pair,
        set_context=set_context,
    )
    _add_end_of_day_context(
        sources.dc_stocks_csv,
        stock_field="stock_end_of_day",
        label="stock DC fin de jour",
        relevant_by_pair=relevant_by_pair,
        set_context=set_context,
    )
    _add_end_of_day_context(
        sources.supplier_stocks_csv,
        stock_field="stock_end_of_day",
        label="stock fournisseur fin de jour",
        relevant_by_pair=relevant_by_pair,
        set_context=set_context,
    )

    if sources.demand_service_csv is not None and sources.demand_service_csv.exists():
        for row in read_csv_rows(sources.demand_service_csv):
            node_id = str(row.get("node_id") or "")
            item_id = str(row.get("item_id") or "")
            day = int(to_float(row.get("day")) or 0)
            if (node_id, item_id, day) not in relevant_keys:
                continue
            available = to_float(row.get("available_before_service_qty"))
            served = to_float(row.get("served_qty")) or 0.0
            backlog = to_float(row.get("backlog_end_qty"))
            after = (available - served) if available is not None and not math.isnan(available) else None
            set_context(
                node_id=node_id,
                item_id=item_id,
                day=day,
                label="stock client avant/apres service",
                before=available,
                after=after,
                extra={"served_qty": round(served, 6), "backlog_end_qty": round(backlog or 0.0, 6)},
                overwrite=True,
            )

    return out


def _relevant_stock_keys(
    events: list[dict[str, Any]],
    genealogy: list[dict[str, Any]],
) -> set[tuple[str, str, int]]:
    relevant_keys: set[tuple[str, str, int]] = set()
    for row in events:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if node_id and item_id:
            relevant_keys.add((node_id, item_id, _row_day(row)))
    for row in genealogy:
        day = _row_day(row)
        parent_node = str(row.get("parent_node_id") or "")
        parent_item = str(row.get("parent_item_id") or "")
        child_node = str(row.get("child_node_id") or "")
        child_item = str(row.get("child_item_id") or "")
        if parent_node and parent_item:
            relevant_keys.add((parent_node, parent_item, day))
        if child_node and child_item:
            relevant_keys.add((child_node, child_item, day))
    return relevant_keys


def _add_end_of_day_context(
    csv_path: Path | None,
    *,
    stock_field: str,
    label: str,
    relevant_by_pair: dict[tuple[str, str], set[int]],
    set_context: Any,
) -> None:
    if csv_path is None or not csv_path.exists():
        return
    rows = read_csv_rows(csv_path)
    by_pair: dict[tuple[str, str], dict[int, float]] = defaultdict(dict)
    for row in rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if (node_id, item_id) not in relevant_by_pair:
            continue
        day = int(to_float(row.get("day")) or 0)
        value = to_float(row.get(stock_field))
        if value is None or math.isnan(value):
            continue
        by_pair[(node_id, item_id)][day] = value
    for (node_id, item_id), wanted_days in relevant_by_pair.items():
        series = by_pair.get((node_id, item_id), {})
        if not series:
            continue
        for day in wanted_days:
            if day not in series:
                continue
            before = series.get(day - 1)
            if before is None and day == 0:
                before = 0.0
            after = series.get(day)
            set_context(
                node_id=node_id,
                item_id=item_id,
                day=day,
                label=label,
                before=before,
                after=after,
            )


def _stock_context_key(node_id: str, item_id: str, day: int) -> str:
    return f"{node_id}|{item_id}|{day}"


def _row_day(row: dict[str, Any]) -> int:
    numeric = to_float(row.get("day"))
    return int(round(numeric)) if numeric is not None and not math.isnan(numeric) else 0
