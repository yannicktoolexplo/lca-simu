from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import read_csv_rows
from .schema import to_float


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
