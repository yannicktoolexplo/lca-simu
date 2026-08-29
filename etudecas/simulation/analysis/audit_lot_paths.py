#!/usr/bin/env python3
"""Audit all lot paths exported by the dynamic simulation."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

try:
    from etudecas.case_config import (
        UPSTREAM_INTERNAL_SITE_IDS,
        canonical_node_id,
    )
    from etudecas.simulation.analysis.audit_lot_trace_semantics import (
        audit_acceptance_semantics,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.case_config import (
        UPSTREAM_INTERNAL_SITE_IDS,
        canonical_node_id,
    )
    from etudecas.simulation.analysis.audit_lot_trace_semantics import (
        audit_acceptance_semantics,
    )


EPS = 1e-6
CREATION_PRIORITY = {
    "production_output": 0,
    "lane_receipt": 1,
    "external_procurement_receipt": 2,
    "estimated_source_receipt": 3,
    "estimated_capacity_receipt": 4,
    "opening_stock": 5,
    "stock_reconciliation": 6,
}
PRODUCTION_CONSUME_EVENTS = {
    "production_consume",
    "production_consume_reference_transition",
}
DEPLETION_EVENTS = {
    *PRODUCTION_CONSUME_EVENTS,
    "lane_ship",
    "demand_service",
    "writeoff",
    "supplier_writeoff",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit simulation lot genealogy and end-to-end paths.")
    parser.add_argument(
        "--output-root",
        default="etudecas/simulation/result/_codex_lot_trace_smoke",
        help="Simulation output root containing data/production_lot_events.csv.",
    )
    parser.add_argument(
        "--input",
        default="",
        help="Simulation-ready graph JSON. Defaults to input_file from summaries/first_simulation_summary.json.",
    )
    parser.add_argument("--report", default="", help="Markdown report path.")
    parser.add_argument("--issues-csv", default="", help="CSV path for detected issues and warnings.")
    parser.add_argument("--max-examples", type=int, default=8, help="Maximum examples per report section.")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(str(value).replace(",", "."))))
    except (TypeError, ValueError):
        return default


def read_input_path(output_root: Path, explicit: str) -> Path | None:
    if explicit:
        return Path(explicit)
    summary_path = output_root / "summaries" / "first_simulation_summary.json"
    if not summary_path.exists():
        return None
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    raw_path = str(data.get("input_file") or "")
    return Path(raw_path) if raw_path else None


def node_types(input_path: Path | None) -> dict[str, str]:
    if not input_path or not input_path.exists():
        return {}
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for node in raw.get("nodes", []):
        node_id = canonical_node_id(node.get("id"))
        out[node_id] = str(node.get("type") or node.get("node_type") or "")
    return out


def route_parts(source_id: str) -> tuple[str, str]:
    raw = str(source_id or "")
    if not raw.startswith("edge:"):
        return "", ""
    body = raw[5:]
    marker = "_TO_"
    marker_idx = body.index(marker) if marker in body else -1
    if marker_idx <= 0:
        return "", ""
    src = canonical_node_id(body[:marker_idx])
    rest = body[marker_idx + len(marker) :]
    item_sep = rest.rfind("_")
    dst = canonical_node_id(rest[:item_sep] if item_sep > 0 else rest)
    return src, dst


def transport_kind(src: str, dst: str, node_type: dict[str, str]) -> str:
    src = canonical_node_id(src)
    dst = canonical_node_id(dst)
    src_type = node_type.get(src, "")
    dst_type = node_type.get(dst, "")
    if src_type == "supplier_dc" and dst_type == "factory":
        return "supplier_to_semifinished_site" if dst in UPSTREAM_INTERNAL_SITE_IDS else "supplier_to_factory"
    if src_type == "factory" and dst_type == "factory":
        return (
            "semifinished_to_factory"
            if src in UPSTREAM_INTERNAL_SITE_IDS or dst in UPSTREAM_INTERNAL_SITE_IDS
            else "factory_to_factory"
        )
    if src_type == "factory" and dst_type == "distribution_center":
        return "factory_to_dc"
    if src_type == "distribution_center" and dst_type == "customer":
        return "dc_to_customer"
    if src_type == "supplier_dc":
        return "supplier_transport_other"
    return "transport_unclassified"


def creation_index(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_lot: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        if lot_id:
            by_lot[lot_id].append(row)
    out: dict[str, dict[str, str]] = {}
    for lot_id, rows in by_lot.items():
        out[lot_id] = sorted(
            rows,
            key=lambda row: (
                to_int(row.get("day")),
                CREATION_PRIORITY.get(str(row.get("event_type") or ""), 99),
                str(row.get("event_id") or ""),
            ),
        )[0]
    return out


def downstream_lots(root: str, children_by_parent: dict[str, list[dict[str, str]]], limit: int = 10000) -> set[str]:
    seen = {root}
    queue: deque[str] = deque([root])
    while queue and len(seen) < limit:
        lot_id = queue.popleft()
        for link in children_by_parent.get(lot_id, []):
            child = str(link.get("child_lot_id") or "")
            if child and child not in seen:
                seen.add(child)
                queue.append(child)
    return seen


def shortest_path_to_customer(
    root: str,
    children_by_parent: dict[str, list[dict[str, str]]],
    demand_service_lots: set[str],
) -> tuple[list[dict[str, str]], str]:
    queue: deque[tuple[str, list[dict[str, str]]]] = deque([(root, [])])
    seen = {root}
    while queue and len(seen) < 10000:
        lot_id, path = queue.popleft()
        if lot_id in demand_service_lots:
            return path, lot_id
        for link in children_by_parent.get(lot_id, []):
            child = str(link.get("child_lot_id") or "")
            if child and child not in seen:
                seen.add(child)
                queue.append((child, path + [link]))
    return [], ""


def format_path(root: str, path: list[dict[str, str]], end_lot: str, lots: dict[str, dict[str, str]]) -> str:
    if not end_lot:
        return ""
    parts = [root]
    for link in path:
        label = str(link.get("link_type") or "")
        src = canonical_node_id(link.get("parent_node_id"))
        dst = canonical_node_id(link.get("child_node_id"))
        item = str(link.get("parent_item_id") or link.get("child_item_id") or "")
        parts.append(f"{label} J{link.get('day')} {src}->{dst} {item}")
        parts.append(str(link.get("child_lot_id") or ""))
    end = lots.get(end_lot, {})
    parts.append(f"demand_service lot {end_lot} @ {canonical_node_id(end.get('node_id'))}/{end.get('item_id')}")
    return " -> ".join(parts)


def write_issues_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["severity", "kind", "lot_id", "day", "node_id", "item_id", "details"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def qty_mismatch(expected: float, actual: float) -> bool:
    return abs(expected - actual) > max(1e-4, abs(expected) * 1e-5, abs(actual) * 1e-5)


def pct(numerator: int | float, denominator: int | float) -> str:
    denom = float(denominator or 0)
    if denom <= 0:
        return "n/a"
    return f"{100.0 * float(numerator or 0) / denom:.1f}%"


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    data_dir = output_root / "data"
    report_path = Path(args.report) if args.report else output_root / "reports" / "lot_path_audit.md"
    issues_path = Path(args.issues_csv) if args.issues_csv else output_root / "data" / "lot_path_audit_issues.csv"
    input_path = read_input_path(output_root, args.input)
    node_type = node_types(input_path)

    events = read_csv(data_dir / "production_lot_events.csv")
    genealogy = read_csv(data_dir / "production_lot_genealogy.csv")
    plan_events_raw = read_csv(data_dir / "production_plan_events.csv")
    lots = creation_index(events)
    events_by_lot: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in events:
        events_by_lot[str(row.get("lot_id") or "")].append(row)

    children_by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    parents_by_child: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in genealogy:
        children_by_parent[str(row.get("parent_lot_id") or "")].append(row)
        parents_by_child[str(row.get("child_lot_id") or "")].append(row)

    issues: list[dict[str, Any]] = []
    missing_lot_refs = 0
    chronology_errors = 0
    route_mismatches = 0
    negative_qty_rows = 0

    for row in events:
        if to_float(row.get("qty")) < -EPS or to_float(row.get("qty_after")) < -EPS:
            negative_qty_rows += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "negative_event_qty",
                    "lot_id": row.get("lot_id", ""),
                    "day": row.get("day", ""),
                    "node_id": row.get("node_id", ""),
                    "item_id": row.get("item_id", ""),
                    "details": f"event_type={row.get('event_type')} qty={row.get('qty')} qty_after={row.get('qty_after')}",
                }
            )

    for row in genealogy:
        parent = str(row.get("parent_lot_id") or "")
        child = str(row.get("child_lot_id") or "")
        if parent not in lots or child not in lots:
            missing_lot_refs += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "missing_lot_reference",
                    "lot_id": parent if parent not in lots else child,
                    "day": row.get("day", ""),
                    "node_id": row.get("parent_node_id", ""),
                    "item_id": row.get("parent_item_id", ""),
                    "details": f"parent={parent in lots} child={child in lots}",
                }
            )
        link_day = to_int(row.get("day"))
        parent_day = to_int(lots.get(parent, {}).get("day"))
        child_day = to_int(lots.get(child, {}).get("day"))
        if parent in lots and parent_day > link_day:
            chronology_errors += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "parent_created_after_link",
                    "lot_id": parent,
                    "day": link_day,
                    "node_id": row.get("parent_node_id", ""),
                    "item_id": row.get("parent_item_id", ""),
                    "details": f"parent_created_day={parent_day}",
                }
            )
        if child in lots and child_day != link_day:
            chronology_errors += 1
            issues.append(
                {
                    "severity": "warning",
                    "kind": "child_creation_day_differs_from_link",
                    "lot_id": child,
                    "day": link_day,
                    "node_id": row.get("child_node_id", ""),
                    "item_id": row.get("child_item_id", ""),
                    "details": f"child_created_day={child_day}",
                }
            )
        if to_float(row.get("parent_qty")) < -EPS or to_float(row.get("child_qty")) < -EPS:
            negative_qty_rows += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "negative_link_qty",
                    "lot_id": parent,
                    "day": link_day,
                    "node_id": row.get("parent_node_id", ""),
                    "item_id": row.get("parent_item_id", ""),
                    "details": f"parent_qty={row.get('parent_qty')} child_qty={row.get('child_qty')}",
                }
            )
        if str(row.get("link_type") or "") == "transport":
            src, dst = route_parts(str(row.get("source_id") or ""))
            parent_node = canonical_node_id(row.get("parent_node_id"))
            child_node = canonical_node_id(row.get("child_node_id"))
            if src and dst and (src != parent_node or dst != child_node):
                route_mismatches += 1
                issues.append(
                    {
                        "severity": "warning",
                        "kind": "transport_source_route_mismatch",
                        "lot_id": parent,
                        "day": link_day,
                        "node_id": parent_node,
                        "item_id": row.get("parent_item_id", ""),
                        "details": f"source_id={row.get('source_id')} parsed={src}->{dst} link={parent_node}->{child_node}",
                    }
                )

    over_consumed = 0
    for lot_id, creation in lots.items():
        initial_qty = max(0.0, to_float(creation.get("qty")))
        depleted_qty = sum(
            max(0.0, to_float(row.get("qty")))
            for row in events_by_lot.get(lot_id, [])
            if str(row.get("event_type") or "") in DEPLETION_EVENTS
        )
        if depleted_qty > initial_qty + max(1e-5, initial_qty * 1e-5):
            over_consumed += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "lot_depletion_exceeds_initial_qty",
                    "lot_id": lot_id,
                    "day": creation.get("day", ""),
                    "node_id": creation.get("node_id", ""),
                    "item_id": creation.get("item_id", ""),
                    "details": f"initial={initial_qty:.6f} depleted={depleted_qty:.6f}",
                }
            )

    event_counts = Counter(str(row.get("event_type") or "") for row in events)
    link_counts = Counter(str(row.get("link_type") or "") for row in genealogy)
    transport_counts = Counter(
        transport_kind(row.get("parent_node_id", ""), row.get("child_node_id", ""), node_type)
        for row in genealogy
        if str(row.get("link_type") or "") == "transport"
    )

    demand_service_lots = {
        str(row.get("lot_id") or "")
        for row in events
        if str(row.get("event_type") or "") == "demand_service"
    }
    customer_reached_lots = set()
    for lot_id in lots:
        related = downstream_lots(lot_id, children_by_parent)
        if related & demand_service_lots:
            customer_reached_lots.add(lot_id)

    supplier_material_lots = [
        lot_id
        for lot_id, row in lots.items()
        if node_type.get(canonical_node_id(row.get("node_id")), "") == "supplier_dc"
        and str(row.get("event_type") or "") in {"opening_stock", "external_procurement_receipt", "estimated_source_receipt", "estimated_capacity_receipt"}
    ]
    factory_opening_lots = [
        lot_id
        for lot_id, row in lots.items()
        if node_type.get(canonical_node_id(row.get("node_id")), "") == "factory"
        and str(row.get("event_type") or "") == "opening_stock"
    ]
    production_lots = [lot_id for lot_id, row in lots.items() if str(row.get("event_type") or "") == "production_output"]

    supplier_mp_to_customer = [lot_id for lot_id in supplier_material_lots if lot_id in customer_reached_lots]
    factory_opening_to_customer = [lot_id for lot_id in factory_opening_lots if lot_id in customer_reached_lots]
    production_to_customer = [lot_id for lot_id in production_lots if lot_id in customer_reached_lots]

    lane_receipt_lots = [
        lot_id for lot_id, row in lots.items() if str(row.get("event_type") or "") == "lane_receipt"
    ]
    lane_receipts_without_parent = [
        lot_id
        for lot_id in lane_receipt_lots
        if not [row for row in parents_by_child.get(lot_id, []) if str(row.get("link_type") or "") == "transport"]
    ]
    lane_receipts_without_parent_by_flow: Counter[str] = Counter()
    lane_receipts_without_parent_examples: list[list[Any]] = []
    for lot_id in lane_receipts_without_parent:
        lot = lots.get(lot_id, {})
        src, dst = route_parts(str(lot.get("source_id") or ""))
        src = canonical_node_id(src)
        dst = canonical_node_id(dst or lot.get("node_id"))
        flow = transport_kind(src, dst, node_type) if src and dst else "unknown_or_aggregate"
        lane_receipts_without_parent_by_flow[flow] += 1
        if len(lane_receipts_without_parent_examples) < args.max_examples:
            lane_receipts_without_parent_examples.append(
                [
                    lot_id,
                    lot.get("day", ""),
                    f"{src or 'n/a'} -> {dst or 'n/a'}",
                    lot.get("item_id", ""),
                    f"{to_float(lot.get('qty')):.1f}",
                ]
            )

    customer_receipt_lots = [
        lot_id
        for lot_id, row in lots.items()
        if str(row.get("event_type") or "") == "lane_receipt"
        and node_type.get(canonical_node_id(row.get("node_id")), "") == "customer"
    ]
    mixed_customer_lots: list[tuple[int, float, str, str, list[str]]] = []
    for lot_id in customer_receipt_lots:
        transport_parents = [
            row
            for row in parents_by_child.get(lot_id, [])
            if str(row.get("link_type") or "") == "transport"
        ]
        parent_lots = sorted({str(row.get("parent_lot_id") or "") for row in transport_parents if row.get("parent_lot_id")})
        if len(parent_lots) <= 1:
            continue
        lot = lots.get(lot_id, {})
        mixed_customer_lots.append(
            (
                len(parent_lots),
                to_float(lot.get("qty")),
                lot_id,
                str(lot.get("item_id") or ""),
                parent_lots[:6],
            )
        )
    mixed_customer_lots.sort(reverse=True)
    mixed_customer_lot_examples = [
        [lot_id, item_id, parent_count, f"{qty:.1f}", ", ".join(parent_lots)]
        for parent_count, qty, lot_id, item_id, parent_lots in mixed_customer_lots[: args.max_examples]
    ]

    examples: list[tuple[str, str]] = []
    for lot_id in supplier_mp_to_customer[: args.max_examples]:
        path, end_lot = shortest_path_to_customer(lot_id, children_by_parent, demand_service_lots)
        examples.append((lot_id, format_path(lot_id, path, end_lot, lots)))
    if not examples:
        for lot_id in factory_opening_to_customer[: args.max_examples]:
            path, end_lot = shortest_path_to_customer(lot_id, children_by_parent, demand_service_lots)
            examples.append((lot_id, format_path(lot_id, path, end_lot, lots)))

    opening_stock_upstream_truncation = 0
    production_with_transport_upstream = 0
    for lot_id in production_lots:
        upstream_seen = {lot_id}
        queue: deque[str] = deque([lot_id])
        has_opening = False
        has_transport = False
        while queue and len(upstream_seen) < 10000:
            current = queue.popleft()
            for link in parents_by_child.get(current, []):
                if str(link.get("link_type") or "") == "transport":
                    has_transport = True
                parent = str(link.get("parent_lot_id") or "")
                if parent:
                    if str(lots.get(parent, {}).get("event_type") or "") == "opening_stock":
                        has_opening = True
                    if parent not in upstream_seen:
                        upstream_seen.add(parent)
                        queue.append(parent)
        if has_opening and not has_transport:
            opening_stock_upstream_truncation += 1
        if has_transport:
            production_with_transport_upstream += 1

    ship_qty_by_lot_source: dict[tuple[str, str], float] = defaultdict(float)
    transport_parent_qty_by_lot_source: dict[tuple[str, str], float] = defaultdict(float)
    for row in events:
        if str(row.get("event_type") or "") == "lane_ship":
            ship_qty_by_lot_source[(str(row.get("lot_id") or ""), str(row.get("source_id") or ""))] += max(
                0.0, to_float(row.get("qty"))
            )
    for row in genealogy:
        if str(row.get("link_type") or "") == "transport":
            transport_parent_qty_by_lot_source[(str(row.get("parent_lot_id") or ""), str(row.get("source_id") or ""))] += max(
                0.0, to_float(row.get("parent_qty"))
            )
    unresolved_shipments = []
    for key, shipped_qty in ship_qty_by_lot_source.items():
        linked_qty = transport_parent_qty_by_lot_source.get(key, 0.0)
        if shipped_qty > linked_qty + max(1e-5, shipped_qty * 1e-5):
            lot_id, source_id = key
            unresolved_shipments.append((shipped_qty - linked_qty, shipped_qty, linked_qty, lot_id, source_id))
    unresolved_shipments.sort(reverse=True)

    production_consume_qty: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    production_output_qty: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    lane_receipt_qty: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    for row in events:
        event_type = str(row.get("event_type") or "")
        if event_type in PRODUCTION_CONSUME_EVENTS:
            production_consume_qty[
                (
                    str(row.get("day") or ""),
                    str(row.get("lot_id") or ""),
                    canonical_node_id(row.get("node_id")),
                    str(row.get("item_id") or ""),
                    str(row.get("production_campaign_id") or ""),
                )
            ] += max(0.0, to_float(row.get("qty")))
        elif event_type == "production_output":
            production_output_qty[
                (
                    str(row.get("day") or ""),
                    str(row.get("lot_id") or ""),
                    canonical_node_id(row.get("node_id")),
                    str(row.get("item_id") or ""),
                    str(row.get("production_campaign_id") or ""),
                )
            ] += max(0.0, to_float(row.get("qty")))
        elif event_type == "lane_receipt":
            lane_receipt_qty[
                (
                    str(row.get("day") or ""),
                    str(row.get("lot_id") or ""),
                    canonical_node_id(row.get("node_id")),
                    str(row.get("item_id") or ""),
                    str(row.get("source_id") or ""),
                )
            ] += max(0.0, to_float(row.get("qty")))

    production_missing_consume = 0
    production_consume_qty_mismatches = 0
    production_missing_output = 0
    production_output_qty_mismatches = 0
    transport_missing_ship = 0
    transport_overlinked_ship = 0
    transport_missing_receipt = 0
    transport_receipt_qty_mismatches = 0
    transport_receipt_child_qty_conflicts = 0
    transport_receipt_share_mismatches = 0
    transport_receipt_parent_qty: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    transport_receipt_child_qty: dict[tuple[str, str, str, str, str], float] = {}
    transport_receipt_child_qty_conflict_keys: set[tuple[str, str, str, str, str]] = set()
    transport_receipt_share: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    transport_parent_qty_by_lot_source_all: dict[tuple[str, str], float] = defaultdict(float)

    for row in genealogy:
        link_type = str(row.get("link_type") or "")
        if link_type == "production":
            consume_key = (
                str(row.get("day") or ""),
                str(row.get("parent_lot_id") or ""),
                canonical_node_id(row.get("parent_node_id")),
                str(row.get("parent_item_id") or ""),
                str(row.get("production_campaign_id") or ""),
            )
            expected_parent_qty = max(0.0, to_float(row.get("parent_qty")))
            actual_parent_qty = production_consume_qty.get(consume_key, 0.0)
            if actual_parent_qty <= EPS:
                production_missing_consume += 1
                issues.append(
                    {
                        "severity": "error",
                        "kind": "production_link_missing_consume_event",
                        "lot_id": row.get("parent_lot_id", ""),
                        "day": row.get("day", ""),
                        "node_id": row.get("parent_node_id", ""),
                        "item_id": row.get("parent_item_id", ""),
                        "details": f"campaign={row.get('production_campaign_id')}",
                    }
                )
            elif qty_mismatch(expected_parent_qty, actual_parent_qty):
                production_consume_qty_mismatches += 1
                issues.append(
                    {
                        "severity": "error",
                        "kind": "production_link_consume_qty_mismatch",
                        "lot_id": row.get("parent_lot_id", ""),
                        "day": row.get("day", ""),
                        "node_id": row.get("parent_node_id", ""),
                        "item_id": row.get("parent_item_id", ""),
                        "details": f"link_parent_qty={expected_parent_qty:.6f} consume_event_qty={actual_parent_qty:.6f}",
                    }
                )

            output_key = (
                str(row.get("day") or ""),
                str(row.get("child_lot_id") or ""),
                canonical_node_id(row.get("child_node_id")),
                str(row.get("child_item_id") or ""),
                str(row.get("production_campaign_id") or ""),
            )
            expected_child_qty = max(0.0, to_float(row.get("child_qty")))
            actual_child_qty = production_output_qty.get(output_key, 0.0)
            if actual_child_qty <= EPS:
                production_missing_output += 1
                issues.append(
                    {
                        "severity": "error",
                        "kind": "production_link_missing_output_event",
                        "lot_id": row.get("child_lot_id", ""),
                        "day": row.get("day", ""),
                        "node_id": row.get("child_node_id", ""),
                        "item_id": row.get("child_item_id", ""),
                        "details": f"campaign={row.get('production_campaign_id')}",
                    }
                )
            elif qty_mismatch(expected_child_qty, actual_child_qty):
                production_output_qty_mismatches += 1
                issues.append(
                    {
                        "severity": "error",
                        "kind": "production_link_output_qty_mismatch",
                        "lot_id": row.get("child_lot_id", ""),
                        "day": row.get("day", ""),
                        "node_id": row.get("child_node_id", ""),
                        "item_id": row.get("child_item_id", ""),
                        "details": f"link_child_qty={expected_child_qty:.6f} output_event_qty={actual_child_qty:.6f}",
                    }
                )
        elif link_type == "transport":
            parent_key = (str(row.get("parent_lot_id") or ""), str(row.get("source_id") or ""))
            transport_parent_qty_by_lot_source_all[parent_key] += max(0.0, to_float(row.get("parent_qty")))
            receipt_key = (
                str(row.get("day") or ""),
                str(row.get("child_lot_id") or ""),
                canonical_node_id(row.get("child_node_id")),
                str(row.get("child_item_id") or ""),
                str(row.get("source_id") or ""),
            )
            transport_receipt_parent_qty[receipt_key] += max(0.0, to_float(row.get("parent_qty")))
            expected_child_qty = max(0.0, to_float(row.get("child_qty")))
            previous_child_qty = transport_receipt_child_qty.get(receipt_key)
            if previous_child_qty is None:
                transport_receipt_child_qty[receipt_key] = expected_child_qty
            elif qty_mismatch(previous_child_qty, expected_child_qty):
                transport_receipt_child_qty[receipt_key] = max(previous_child_qty, expected_child_qty)
                if receipt_key not in transport_receipt_child_qty_conflict_keys:
                    transport_receipt_child_qty_conflict_keys.add(receipt_key)
                    transport_receipt_child_qty_conflicts += 1
                    issues.append(
                        {
                            "severity": "warning",
                            "kind": "transport_receipt_child_qty_conflict",
                            "lot_id": row.get("child_lot_id", ""),
                            "day": row.get("day", ""),
                            "node_id": row.get("child_node_id", ""),
                            "item_id": row.get("child_item_id", ""),
                            "details": (
                                f"source_id={row.get('source_id')} "
                                f"first_child_qty={previous_child_qty:.6f} link_child_qty={expected_child_qty:.6f}"
                            ),
                        }
                    )
            transport_receipt_share[receipt_key] += max(0.0, to_float(row.get("allocation_share")))

    for (lot_id, source_id), linked_qty in transport_parent_qty_by_lot_source_all.items():
        if linked_qty <= EPS:
            continue
        shipped_qty = ship_qty_by_lot_source.get((lot_id, source_id), 0.0)
        if shipped_qty <= EPS:
            transport_missing_ship += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "transport_link_missing_ship_event",
                    "lot_id": lot_id,
                    "day": "",
                    "node_id": "",
                    "item_id": "",
                    "details": f"source_id={source_id} linked_parent_qty={linked_qty:.6f}",
                }
            )
        elif linked_qty > shipped_qty + max(1e-4, shipped_qty * 1e-5):
            transport_overlinked_ship += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "transport_link_qty_exceeds_ship_event",
                    "lot_id": lot_id,
                    "day": "",
                    "node_id": "",
                    "item_id": "",
                    "details": f"source_id={source_id} linked_parent_qty={linked_qty:.6f} shipped_qty={shipped_qty:.6f}",
                }
            )

    for receipt_key, parent_qty in transport_receipt_parent_qty.items():
        if parent_qty <= EPS:
            continue
        receipt_qty = lane_receipt_qty.get(receipt_key, 0.0)
        child_qty = transport_receipt_child_qty.get(receipt_key, 0.0)
        day, lot_id, node_id, item_id, source_id = receipt_key
        if receipt_qty <= EPS:
            transport_missing_receipt += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "transport_link_missing_receipt_event",
                    "lot_id": lot_id,
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "details": f"source_id={source_id} linked_parent_qty={parent_qty:.6f}",
                }
            )
        elif qty_mismatch(child_qty, receipt_qty):
            transport_receipt_qty_mismatches += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "transport_receipt_qty_mismatch",
                    "lot_id": lot_id,
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "details": (
                        f"source_id={source_id} linked_parent_qty={parent_qty:.6f} "
                        f"link_child_qty={child_qty:.6f} receipt_qty={receipt_qty:.6f}"
                    ),
                }
            )
        share_sum = transport_receipt_share.get(receipt_key, 0.0)
        if qty_mismatch(share_sum, 1.0):
            transport_receipt_share_mismatches += 1
            issues.append(
                {
                    "severity": "warning",
                    "kind": "transport_receipt_allocation_share_mismatch",
                    "lot_id": lot_id,
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "details": f"source_id={source_id} allocation_share_sum={share_sum:.9f}",
                }
            )

    output_qty_by_campaign: dict[str, float] = defaultdict(float)
    for (day, lot_id, node_id, item_id, campaign_id), qty in production_output_qty.items():
        if campaign_id:
            output_qty_by_campaign[campaign_id] += qty
    actual_qty_by_campaign: dict[str, float] = {}
    for row in plan_events_raw:
        if str(row.get("event_type") or "") != "start_campaign":
            continue
        campaign_id = str(row.get("campaign_id") or "")
        if campaign_id:
            actual_qty_by_campaign[campaign_id] = max(0.0, to_float(row.get("actual_qty")))
    production_plan_output_mismatches = 0
    for campaign_id, actual_qty in actual_qty_by_campaign.items():
        output_qty = output_qty_by_campaign.get(campaign_id, 0.0)
        if qty_mismatch(actual_qty, output_qty):
            production_plan_output_mismatches += 1
            issues.append(
                {
                    "severity": "error",
                    "kind": "production_plan_output_qty_mismatch",
                    "lot_id": "",
                    "day": "",
                    "node_id": "",
                    "item_id": "",
                    "details": f"campaign={campaign_id} plan_actual_qty={actual_qty:.6f} output_lot_qty={output_qty:.6f}",
                }
            )

    warning_rows = [
        {
            "severity": "info",
            "kind": "opening_stock_upstream_truncation",
            "lot_id": "",
            "day": "",
            "node_id": "",
            "item_id": "",
            "details": f"{opening_stock_upstream_truncation} production lots have opening-stock ancestors without transport history inside this run.",
        },
        {
            "severity": "info",
            "kind": "unresolved_shipments_possible_in_transit",
            "lot_id": "",
            "day": "",
            "node_id": "",
            "item_id": "",
            "details": f"{len(unresolved_shipments)} lot/source pairs have shipped quantity not linked to a received child lot in the genealogy.",
        },
        {
            "severity": "info",
            "kind": "lane_receipts_without_trace_parent",
            "lot_id": "",
            "day": "",
            "node_id": "",
            "item_id": "",
            "details": f"{len(lane_receipts_without_parent)} lane receipt lots have no transport parent link; usually initial pipeline, aggregate opening flow, or pre-horizon movement.",
        },
        {
            "severity": "info",
            "kind": "mixed_customer_receipt_lots",
            "lot_id": "",
            "day": "",
            "node_id": "",
            "item_id": "",
            "details": f"{len(mixed_customer_lots)} customer receipt lots mix more than one parent lot.",
        },
    ]
    acceptance_issues = audit_acceptance_semantics(events, genealogy, node_types=node_type)
    write_issues_csv(issues + acceptance_issues + warning_rows, issues_path)

    top_transport_rows = [
        [kind, count]
        for kind, count in transport_counts.most_common()
    ]
    top_unresolved_rows = [
        [lot_id, source_id, f"{gap:.1f}", f"{shipped:.1f}", f"{linked:.1f}"]
        for gap, shipped, linked, lot_id, source_id in unresolved_shipments[: args.max_examples]
    ]
    lane_receipts_without_parent_flow_rows = [
        [flow, count] for flow, count in lane_receipts_without_parent_by_flow.most_common()
    ]
    example_rows = [[lot_id, path] for lot_id, path in examples[: args.max_examples]]

    report = f"""# Lot Path Audit

## Scope
- Output root: `{output_root}`
- Graph input: `{input_path or 'n/a'}`
- Lots: `{len(lots)}`
- Lot events: `{len(events)}`
- Genealogy links: `{len(genealogy)}`

## Event And Link Counts
{markdown_table(['Type', 'Count'], [[k, v] for k, v in event_counts.most_common()])}

{markdown_table(['Link type', 'Count'], [[k, v] for k, v in link_counts.most_common()])}

## Logistic Flow Coverage
{markdown_table(['Flow class', 'Transport links'], top_transport_rows)}

## Integrity Checks
- Missing lot references in genealogy: `{missing_lot_refs}`
- Chronology warnings/errors: `{chronology_errors}`
- Transport source route mismatches after canonical aliases: `{route_mismatches}`
- Negative quantity rows: `{negative_qty_rows}`
- Lots depleted above initial quantity: `{over_consumed}`
- Lotification acceptance errors: `{sum(row['severity'] == 'error' for row in acceptance_issues)}`
- Legacy-run migration debts: `{sum(row['severity'] == 'migration' for row in acceptance_issues)}`
- Issue CSV: `{issues_path}`

## Simulation Cross-Checks
- Production links missing consume event: `{production_missing_consume}`
- Production link consume quantity mismatches: `{production_consume_qty_mismatches}`
- Production links missing output event: `{production_missing_output}`
- Production link output quantity mismatches: `{production_output_qty_mismatches}`
- Production plan actual quantity mismatches vs output lots: `{production_plan_output_mismatches}`
- Transport parent groups missing ship event: `{transport_missing_ship}`
- Transport parent groups linked above shipped quantity: `{transport_overlinked_ship}`
- Transport receipt groups missing receipt event: `{transport_missing_receipt}`
- Transport receipt child-quantity mismatches: `{transport_receipt_qty_mismatches}`
- Transport receipt child-quantity conflicts inside genealogy: `{transport_receipt_child_qty_conflicts}`
- Transport receipt allocation-share mismatches: `{transport_receipt_share_mismatches}`

## Expected Model Limits Detected
- Production lots with only pre-J0 opening-stock upstream and no in-run transport history: `{opening_stock_upstream_truncation}` / `{len(production_lots)}`
- Production lots with at least one upstream transport in-run: `{production_with_transport_upstream}` / `{len(production_lots)}`
- Lot/source shipment pairs not fully linked to received child lots: `{len(unresolved_shipments)}`. These are usually shipments still in transit, outside the visible horizon, or released through aggregate order-book mechanics.
- Lane receipt lots without a transport parent link: `{len(lane_receipts_without_parent)}` / `{len(lane_receipt_lots)}`. These should be displayed as explicit non-traced origins, not as broken genealogy.
- Customer receipt lots mixing multiple parent lots: `{len(mixed_customer_lots)}` / `{len(customer_receipt_lots)}`. These need split/contribution labels in lot-trace diagrams.

{markdown_table(['Lot', 'Source edge', 'Unlinked qty', 'Shipped qty', 'Linked transport parent qty'], top_unresolved_rows) if top_unresolved_rows else 'No unresolved shipment examples.'}

### Lane Receipts Without Parent Link
{markdown_table(['Flow class', 'Lots'], lane_receipts_without_parent_flow_rows) if lane_receipts_without_parent_flow_rows else 'No lane receipt without parent link.'}

{markdown_table(['Lot', 'Day', 'Route', 'Item', 'Qty'], lane_receipts_without_parent_examples) if lane_receipts_without_parent_examples else ''}

### Mixed Customer Receipt Lots
{markdown_table(['Customer lot', 'Item', 'Parent lot count', 'Qty', 'Example parent lots'], mixed_customer_lot_examples) if mixed_customer_lot_examples else 'No mixed customer receipt lot detected.'}

## Raw Material To Customer Traceability
- Supplier-material lots considered: `{len(supplier_material_lots)}`
- Supplier-material lots reaching a customer service event: `{len(supplier_mp_to_customer)}` (`{pct(len(supplier_mp_to_customer), len(supplier_material_lots))}`)
- Factory opening-stock lots reaching a customer service event: `{len(factory_opening_to_customer)}` (`{pct(len(factory_opening_to_customer), len(factory_opening_lots))}`)
- Produced lots reaching a customer service event: `{len(production_to_customer)}` (`{pct(len(production_to_customer), len(production_lots))}`)

{markdown_table(['Root lot', 'Shortest path to customer service'], example_rows) if example_rows else 'No supplier-material-to-customer path reached customer service in this horizon.'}

## Interpretation
- Yes, a raw material can be followed to the client when the full chain occurs inside the simulated horizon: supplier/source lot -> transport -> factory stock -> production -> factory/DC transport -> customer stock -> demand_service.
- If the material starts as opening stock at a factory on J0, its supplier-side history is pre-J0 and cannot be reconstructed without historical lot data or a warm-up/pre-horizon lot run.
- A lot is considered to have reached the client when one of its descendants is consumed by a `demand_service` event at the customer node.
"""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"[OK] Lot path audit report: {report_path.resolve()}")
    print(f"[OK] Lot path issues CSV: {issues_path.resolve()}")
    all_issues = issues + acceptance_issues
    print(
        "[OK] "
        f"errors={sum(1 for row in all_issues if row['severity'] == 'error')} "
        f"warnings={sum(1 for row in all_issues if row['severity'] == 'warning')} "
        f"migration_debts={sum(1 for row in all_issues if row['severity'] == 'migration')}"
    )


if __name__ == "__main__":
    main()
