#!/usr/bin/env python3
"""Trace lot ancestors or descendants from simulation lot genealogy CSVs."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace production lot genealogy from simulation outputs.")
    parser.add_argument(
        "--output-root",
        default="etudecas/simulation/result",
        help="Simulation output root containing data/production_lot_*.csv.",
    )
    parser.add_argument(
        "--lot-id",
        default="",
        help="Lot id to trace. If omitted, the first production_output lot is used.",
    )
    parser.add_argument(
        "--direction",
        choices=["ancestors", "descendants", "both"],
        default="both",
        help="Trace upstream parents, downstream children, or both.",
    )
    parser.add_argument("--max-depth", type=int, default=6, help="Maximum traversal depth.")
    parser.add_argument(
        "--report",
        default="",
        help="Optional Markdown report path. Defaults to reports/lot_trace_<lot_id>.md.",
    )
    parser.add_argument(
        "--csv",
        default="",
        help="Optional CSV path. Defaults to data/lot_trace_<lot_id>.csv.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def pick_default_lot(events: list[dict[str, str]]) -> str:
    for row in events:
        if row.get("event_type") == "production_output" and row.get("lot_id"):
            return str(row["lot_id"])
    for row in events:
        if row.get("lot_id"):
            return str(row["lot_id"])
    return ""


def lot_index(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        if not lot_id:
            continue
        if lot_id not in out or row.get("event_type") in {
            "opening_stock",
            "lane_receipt",
            "external_procurement_receipt",
            "estimated_source_receipt",
            "estimated_capacity_receipt",
            "production_output",
        }:
            out[lot_id] = row
    return out


def traverse(
    *,
    root_lot_id: str,
    direction: str,
    max_depth: int,
    genealogy: list[dict[str, str]],
    lots: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    parent_rows_by_child: dict[str, list[dict[str, str]]] = defaultdict(list)
    child_rows_by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in genealogy:
        parent_rows_by_child[str(row.get("child_lot_id") or "")].append(row)
        child_rows_by_parent[str(row.get("parent_lot_id") or "")].append(row)

    queue: deque[tuple[str, int, str, dict[str, str] | None]] = deque()
    queue.append((root_lot_id, 0, "root", None))
    seen_lots: set[str] = set()
    rows: list[dict[str, Any]] = []
    while queue:
        lot_id, depth, relation_direction, via = queue.popleft()
        if lot_id in seen_lots:
            continue
        seen_lots.add(lot_id)
        lot = lots.get(lot_id, {})
        rows.append(
            {
                "direction": relation_direction,
                "depth": depth,
                "lot_id": lot_id,
                "node_id": lot.get("node_id", ""),
                "item_id": lot.get("item_id", ""),
                "event_type": lot.get("event_type", ""),
                "created_day": lot.get("day", ""),
                "initial_or_event_qty": lot.get("qty", ""),
                "qty_after_event": lot.get("qty_after", ""),
                "source_type": lot.get("source_type", ""),
                "source_id": lot.get("source_id", ""),
                "via_link_type": "" if via is None else via.get("link_type", ""),
                "via_parent_qty": "" if via is None else via.get("parent_qty", ""),
                "via_child_qty": "" if via is None else via.get("child_qty", ""),
                "related_lot_id": "" if via is None else (
                    via.get("parent_lot_id", "") if relation_direction == "ancestor" else via.get("child_lot_id", "")
                ),
            }
        )
        if depth >= max_depth:
            continue
        if direction in {"ancestors", "both"}:
            for edge in parent_rows_by_child.get(lot_id, []):
                parent = str(edge.get("parent_lot_id") or "")
                if parent:
                    queue.append((parent, depth + 1, "ancestor", edge))
        if direction in {"descendants", "both"}:
            for edge in child_rows_by_parent.get(lot_id, []):
                child = str(edge.get("child_lot_id") or "")
                if child:
                    queue.append((child, depth + 1, "descendant", edge))
    return rows


def write_rows_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]], limit: int = 40) -> str:
    cols = ["direction", "depth", "lot_id", "node_id", "item_id", "event_type", "initial_or_event_qty", "via_link_type"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in rows[:limit]:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in cols) + " |")
    if len(rows) > limit:
        lines.append(f"| ... | ... | {len(rows) - limit} more rows | | | | | |")
    return "\n".join(lines)


def write_report(rows: list[dict[str, Any]], path: Path, *, root_lot_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ancestor_count = sum(1 for row in rows if row["direction"] == "ancestor")
    descendant_count = sum(1 for row in rows if row["direction"] == "descendant")
    production_links = sum(1 for row in rows if row.get("via_link_type") == "production")
    transport_links = sum(1 for row in rows if row.get("via_link_type") == "transport")
    text = f"""# Lot trace {root_lot_id}

## Summary
- Rows: {len(rows)}
- Ancestors: {ancestor_count}
- Descendants: {descendant_count}
- Production links: {production_links}
- Transport links: {transport_links}

## Trace Preview
{markdown_table(rows)}
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    events = read_csv(output_root / "data" / "production_lot_events.csv")
    genealogy = read_csv(output_root / "data" / "production_lot_genealogy.csv")
    lots = lot_index(events)
    lot_id = str(args.lot_id or pick_default_lot(events))
    if not lot_id:
        raise SystemExit("No lot id found in production_lot_events.csv")
    rows = traverse(
        root_lot_id=lot_id,
        direction=args.direction,
        max_depth=max(0, int(args.max_depth)),
        genealogy=genealogy,
        lots=lots,
    )
    safe_lot_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in lot_id)
    csv_path = Path(args.csv) if args.csv else output_root / "data" / f"lot_trace_{safe_lot_id}.csv"
    report_path = Path(args.report) if args.report else output_root / "reports" / f"lot_trace_{safe_lot_id}.md"
    write_rows_csv(rows, csv_path)
    write_report(rows, report_path, root_lot_id=lot_id)
    print(f"[OK] Lot trace CSV: {csv_path.resolve()}")
    print(f"[OK] Lot trace report: {report_path.resolve()}")
    print(f"[OK] Traced lot: {lot_id} rows={len(rows)}")


if __name__ == "__main__":
    main()
