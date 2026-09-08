#!/usr/bin/env python3
"""Audit business semantics of lot genealogy exported by a simulation run."""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

try:
    from etudecas.simulation.lot_trace.io import LOT_TRACE_CONTRACT_VERSION
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.simulation.lot_trace.io import LOT_TRACE_CONTRACT_VERSION

EPS = 1e-9
ROOT_CREATION_TYPES = {
    "external_procurement_receipt",
    "opening_production_order",
    "opening_stock",
    "production_output",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit lot identity, contribution and transport semantics.")
    parser.add_argument("--output-root", required=True, help="Simulation run containing data/ lot CSV files.")
    parser.add_argument("--report", default="", help="Markdown report path.")
    parser.add_argument("--max-examples", type=int, default=8)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int:
    try:
        return int(round(float(str(value).replace(",", "."))))
    except (TypeError, ValueError):
        return 0


def pct(numerator: int, denominator: int) -> str:
    return f"{100.0 * numerator / denominator:.1f}%" if denominator else "n/a"


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    data = [[str(value) for value in row] for row in rows]
    if not data:
        return "_Aucune ligne._"
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(row) + " |" for row in data],
        ]
    )


def walk(adjacency: dict[str, set[str]], root: str) -> set[str]:
    seen: set[str] = set()
    queue: deque[str] = deque([root])
    while queue:
        current = queue.popleft()
        for related in adjacency.get(current, set()):
            if related and related != root and related not in seen:
                seen.add(related)
                queue.append(related)
    return seen


def first_events(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for event in events:
        lot_id = event.get("lot_id", "")
        previous = result.get(lot_id)
        if lot_id and (previous is None or as_int(event.get("day")) < as_int(previous.get("day"))):
            result[lot_id] = event
    return result


def quantile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * ratio)]


def _issue(
    severity: str,
    kind: str,
    *,
    row: dict[str, str] | None = None,
    lot_id: str = "",
    details: str = "",
) -> dict[str, str]:
    source = row or {}
    return {
        "severity": severity,
        "kind": kind,
        "lot_id": lot_id or str(source.get("lot_id") or source.get("child_lot_id") or ""),
        "day": str(source.get("day") or ""),
        "node_id": str(source.get("node_id") or source.get("child_node_id") or ""),
        "item_id": str(source.get("item_id") or source.get("child_item_id") or ""),
        "details": details,
    }


def _has_column(rows: list[dict[str, str]], field: str) -> bool:
    return any(field in row for row in rows)


def _normalized_item(value: Any) -> str:
    return str(value or "").strip().removeprefix("item:")


def _normalized_uom(value: Any) -> str:
    uom = str(value or "").strip().upper()
    return {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITES": "UN",
        "UNITS": "UN",
        "ZUN": "UN",
    }.get(uom, uom)


def _canonical_node(value: Any) -> str:
    return str(value or "").strip().upper().replace("_", "-")


def _node_role(node_id: Any, node_types: dict[str, str]) -> str:
    node = _canonical_node(node_id)
    declared = str(node_types.get(node) or node_types.get(str(node_id or "")) or "").lower()
    if declared in {"factory", "distribution_center", "customer", "supplier_dc"}:
        return declared
    if node.startswith("DC-"):
        return "distribution_center"
    if node.startswith("C-"):
        return "customer"
    if node.startswith(("M-", "D-")):
        return "factory"
    if node.startswith("SDC-"):
        return "supplier_dc"
    return declared


def _reachable_links(
    root: str,
    links_by_parent: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    queue: deque[str] = deque([root])
    seen = {root}
    result: list[dict[str, str]] = []
    while queue:
        parent = queue.popleft()
        for link in links_by_parent.get(parent, []):
            result.append(link)
            child = str(link.get("child_lot_id") or "")
            if child and child not in seen:
                seen.add(child)
                queue.append(child)
    return result


def _pf_has_factory_dc_customer_path(
    root: str,
    links_by_parent: dict[str, list[dict[str, str]]],
    demand_lots: set[str],
    node_types: dict[str, str],
) -> bool:
    queue: deque[tuple[str, int]] = deque([(root, 0)])
    seen = {(root, 0)}
    while queue:
        lot_id, stage = queue.popleft()
        if lot_id in demand_lots and stage == 2:
            return True
        for link in links_by_parent.get(lot_id, []):
            next_stage = stage
            if str(link.get("link_type") or "") == "transport":
                parent_role = _node_role(link.get("parent_node_id"), node_types)
                child_role = _node_role(link.get("child_node_id"), node_types)
                if stage == 0 and parent_role == "factory" and child_role == "distribution_center":
                    next_stage = 1
                elif stage == 1 and parent_role == "distribution_center" and child_role == "customer":
                    next_stage = 2
            child = str(link.get("child_lot_id") or "")
            state = (child, next_stage)
            if child and state not in seen:
                seen.add(state)
                queue.append(state)
    return False


def audit_acceptance_semantics(
    events: list[dict[str, str]],
    links: list[dict[str, str]],
    *,
    node_types: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    """Validate the post-migration lot trace contract.

    Missing columns identify a legacy run and are migration debt. Once a column
    exists, missing or incoherent values are acceptance errors.
    """

    issues: list[dict[str, str]] = []
    node_types = {_canonical_node(key): value for key, value in (node_types or {}).items()}
    creations = first_events(events)
    events_by_lot: dict[str, list[dict[str, str]]] = defaultdict(list)
    links_by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    links_by_child: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        events_by_lot[str(event.get("lot_id") or "")].append(event)
    for link in links:
        links_by_parent[str(link.get("parent_lot_id") or "")].append(link)
        links_by_child[str(link.get("child_lot_id") or "")].append(link)

    production_links = [row for row in links if str(row.get("link_type") or "") == "production"]
    transport_links = [row for row in links if str(row.get("link_type") or "") == "transport"]

    # Version the changed semantics explicitly so downstream consumers cannot
    # silently interpret allocation_share or shipment_id with the old contract.
    contract_field = "lot_trace_contract_version"
    if (events or links) and (
        not _has_column(events, contract_field) or (links and not _has_column(links, contract_field))
    ):
        issues.append(
            _issue(
                "migration",
                "migration_debt_lot_trace_contract_version",
                details=f"expected_contract_version={LOT_TRACE_CONTRACT_VERSION}",
            )
        )
    else:
        contract_versions = {
            str(row.get(contract_field) or "").strip()
            for row in [*events, *links]
            if row
        }
        if contract_versions != {LOT_TRACE_CONTRACT_VERSION}:
            issues.append(
                _issue(
                    "error",
                    "lot_trace_contract_version_mismatch",
                    details=(
                        f"expected={LOT_TRACE_CONTRACT_VERSION} "
                        f"observed={sorted(contract_versions)}"
                    ),
                )
            )

    # Production shares are defined independently for each BOM component.
    component_share_field = "component_allocation_share"
    if production_links and not _has_column(links, component_share_field):
        issues.append(
            _issue(
                "migration",
                "migration_debt_component_allocation_share",
                details=(
                    "Legacy genealogy has no component_allocation_share; production attribution "
                    "cannot be validated per BOM component."
                ),
            )
        )
    else:
        event_uoms: dict[str, set[str]] = defaultdict(set)
        for event in events:
            lot_id = str(event.get("lot_id") or "")
            uom = _normalized_uom(event.get("uom"))
            if lot_id and uom:
                event_uoms[lot_id].add(uom)
        by_child_component: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for link in production_links:
            by_child_component[
                (str(link.get("child_lot_id") or ""), str(link.get("parent_item_id") or ""))
            ].append(link)
        for (child_lot, component), rows in by_child_component.items():
            uoms = {
                uom
                for row in rows
                for uom in event_uoms.get(str(row.get("parent_lot_id") or ""), set())
            }
            if len(uoms) > 1:
                issues.append(
                    _issue(
                        "error",
                        "production_component_inter_uom_share",
                        row=rows[0],
                        lot_id=child_lot,
                        details=f"component={component} uoms={sorted(uoms)}",
                    )
                )
            shares = [as_float(row.get(component_share_field)) for row in rows]
            if any(str(row.get(component_share_field) or "").strip() == "" for row in rows):
                issues.append(
                    _issue(
                        "error",
                        "production_component_share_missing",
                        row=rows[0],
                        lot_id=child_lot,
                        details=f"component={component}",
                    )
                )
                continue
            if not math.isclose(sum(shares), 1.0, rel_tol=1e-6, abs_tol=1e-6):
                issues.append(
                    _issue(
                        "error",
                        "production_component_share_sum_mismatch",
                        row=rows[0],
                        lot_id=child_lot,
                        details=f"component={component} share_sum={sum(shares):.9f}",
                    )
                )
            component_qty = sum(max(0.0, as_float(row.get("parent_qty"))) for row in rows)
            if component_qty > EPS:
                for row, share in zip(rows, shares):
                    expected = max(0.0, as_float(row.get("parent_qty"))) / component_qty
                    if not math.isclose(share, expected, rel_tol=1e-6, abs_tol=1e-6):
                        issues.append(
                            _issue(
                                "error",
                                "production_component_share_qty_mismatch",
                                row=row,
                                lot_id=child_lot,
                                details=(
                                    f"component={component} share={share:.9f} "
                                    f"expected={expected:.9f}"
                                ),
                            )
                        )

    # A business batch and a stock occurrence are separate, stable identities.
    event_identity_fields = ("business_batch_id", "lot_occurrence_id")
    missing_event_identity_columns = [
        field for field in event_identity_fields if events and not _has_column(events, field)
    ]
    if missing_event_identity_columns:
        issues.append(
            _issue(
                "migration",
                "migration_debt_lot_identity",
                details=f"missing_columns={','.join(missing_event_identity_columns)}",
            )
        )
    else:
        occurrence_owner: dict[str, str] = {}
        for lot_id, rows in events_by_lot.items():
            batches = {str(row.get("business_batch_id") or "") for row in rows}
            occurrences = {str(row.get("lot_occurrence_id") or "") for row in rows}
            statuses = {str(row.get("trace_status") or "") for row in rows}
            provenance_batches = {
                batch
                for row in rows
                for batch in str(row.get("provenance_batch_id") or "").split("|")
                if batch
            }
            mixed_occurrence = (
                "mixed_batch_occurrence" in statuses
                and len(provenance_batches) > 1
            )
            untraced_occurrence = (
                any(status.startswith("untraced") for status in statuses)
                and all(str(row.get("trace_reason") or "").strip() for row in rows)
            )
            partially_traced_occurrence = (
                "partially_traced_mixed_occurrence" in statuses
                and bool(provenance_batches)
                and all(str(row.get("trace_reason") or "").strip() for row in rows)
            )
            if "" in occurrences or (
                "" in batches
                and not mixed_occurrence
                and not untraced_occurrence
                and not partially_traced_occurrence
            ):
                issues.append(
                    _issue(
                        "error",
                        "lot_identity_missing_value",
                        row=creations.get(lot_id),
                        lot_id=lot_id,
                        details=(
                            "lot_occurrence_id is mandatory; business_batch_id may be blank only "
                            "for an explicit mixed occurrence or an explicitly justified "
                            "untraced origin"
                        ),
                    )
                )
            if len(batches - {""}) > 1 or len(occurrences - {""}) > 1:
                issues.append(
                    _issue(
                        "error",
                        "lot_identity_changes_within_occurrence",
                        row=creations.get(lot_id),
                        lot_id=lot_id,
                        details=f"business_batches={sorted(batches)} occurrences={sorted(occurrences)}",
                    )
                )
            for occurrence in occurrences - {""}:
                previous = occurrence_owner.setdefault(occurrence, lot_id)
                if previous != lot_id:
                    issues.append(
                        _issue(
                            "error",
                            "lot_occurrence_id_reused",
                            row=creations.get(lot_id),
                            lot_id=lot_id,
                            details=f"occurrence={occurrence} first_lot={previous}",
                        )
                    )

    link_identity_fields = (
        "parent_business_batch_id",
        "parent_lot_occurrence_id",
        "child_business_batch_id",
        "child_lot_occurrence_id",
    )
    missing_link_identity_columns = [
        field for field in link_identity_fields if links and not _has_column(links, field)
    ]
    if missing_link_identity_columns:
        issues.append(
            _issue(
                "migration",
                "migration_debt_genealogy_identity",
                details=f"missing_columns={','.join(missing_link_identity_columns)}",
            )
        )
    elif not missing_event_identity_columns:
        event_identity = {
            lot_id: (
                str(row.get("business_batch_id") or ""),
                str(row.get("lot_occurrence_id") or ""),
            )
            for lot_id, row in creations.items()
        }
        for link in links:
            parent_expected = event_identity.get(str(link.get("parent_lot_id") or ""), ("", ""))
            child_expected = event_identity.get(str(link.get("child_lot_id") or ""), ("", ""))
            parent_actual = (
                str(link.get("parent_business_batch_id") or ""),
                str(link.get("parent_lot_occurrence_id") or ""),
            )
            child_actual = (
                str(link.get("child_business_batch_id") or ""),
                str(link.get("child_lot_occurrence_id") or ""),
            )
            if parent_actual != parent_expected or child_actual != child_expected:
                issues.append(
                    _issue(
                        "error",
                        "genealogy_identity_mismatch",
                        row=link,
                        details=(
                            f"parent_actual={parent_actual} parent_expected={parent_expected} "
                            f"child_actual={child_actual} child_expected={child_expected}"
                        ),
                    )
                )

    # A transport link represents a simulated movement only when its simulated
    # shipment identity and dates are explicit. It is not proof of a real truck
    # or handling unit. Legacy links remain readable as migration debt.
    transport_fields = ("shipment_id", "departure_day", "arrival_day")
    missing_transport_columns = [
        field for field in transport_fields if transport_links and not _has_column(transport_links, field)
    ]
    if missing_transport_columns:
        issues.append(
            _issue(
                "migration",
                "migration_debt_transport_identity",
                details=f"missing_columns={','.join(missing_transport_columns)}",
            )
        )
    else:
        shipment_context: dict[str, set[tuple[str, str, int, int]]] = defaultdict(set)
        for link in transport_links:
            shipment_id = str(link.get("shipment_id") or "")
            departure_raw = str(link.get("departure_day") or "").strip()
            arrival_raw = str(link.get("arrival_day") or "").strip()
            if not shipment_id or not departure_raw or not arrival_raw:
                issues.append(
                    _issue(
                        "error",
                        "transport_identity_or_dates_missing",
                        row=link,
                        details=(
                            f"shipment_id={shipment_id or 'missing'} "
                            f"departure_day={departure_raw or 'missing'} "
                            f"arrival_day={arrival_raw or 'missing'}"
                        ),
                    )
                )
                continue
            departure_day = as_int(departure_raw)
            arrival_day = as_int(arrival_raw)
            if departure_day > arrival_day:
                issues.append(
                    _issue(
                        "error",
                        "transport_departure_after_arrival",
                        row=link,
                        details=f"shipment_id={shipment_id} departure={departure_day} arrival={arrival_day}",
                    )
                )
            if arrival_day != as_int(link.get("day")):
                issues.append(
                    _issue(
                        "error",
                        "transport_arrival_differs_from_link_day",
                        row=link,
                        details=f"shipment_id={shipment_id} arrival={arrival_day} link_day={link.get('day')}",
                    )
                )
            shipment_context[shipment_id].add(
                (
                    _canonical_node(link.get("parent_node_id")),
                    _canonical_node(link.get("child_node_id")),
                    departure_day,
                    arrival_day,
                )
            )
        for shipment_id, contexts in shipment_context.items():
            if len(contexts) > 1:
                issues.append(
                    _issue(
                        "error",
                        "shipment_context_inconsistent",
                        details=f"shipment_id={shipment_id} contexts={sorted(contexts)}",
                    )
                )

        transport_events = [
            event
            for event in events
            if str(event.get("event_type") or "") in {"lane_ship", "lane_receipt"}
        ]
        missing_transport_event_columns = [
            field
            for field in transport_fields
            if transport_events and not _has_column(transport_events, field)
        ]
        if missing_transport_event_columns:
            issues.append(
                _issue(
                    "migration",
                    "migration_debt_transport_event_identity",
                    details=f"missing_columns={','.join(missing_transport_event_columns)}",
                )
            )
        else:
            event_context: dict[tuple[str, str, str], tuple[int, int]] = {}
            for event in transport_events:
                if str(event.get("trace_status") or "traced").startswith("untraced"):
                    continue
                shipment_id = str(event.get("shipment_id") or "")
                departure_raw = str(event.get("departure_day") or "").strip()
                arrival_raw = str(event.get("arrival_day") or "").strip()
                if not shipment_id or not departure_raw or not arrival_raw:
                    issues.append(
                        _issue(
                            "error",
                            "transport_event_identity_or_dates_missing",
                            row=event,
                            details=(
                                f"event_type={event.get('event_type')} "
                                f"shipment_id={shipment_id or 'missing'} "
                                f"departure_day={departure_raw or 'missing'} "
                                f"arrival_day={arrival_raw or 'missing'}"
                            ),
                        )
                    )
                    continue
                departure_day = as_int(departure_raw)
                arrival_day = as_int(arrival_raw)
                if departure_day > arrival_day:
                    issues.append(
                        _issue(
                            "error",
                            "transport_event_departure_after_arrival",
                            row=event,
                            details=(
                                f"shipment_id={shipment_id} departure={departure_day} "
                                f"arrival={arrival_day}"
                            ),
                        )
                    )
                key = (
                    shipment_id,
                    str(event.get("event_type") or ""),
                    str(event.get("lot_id") or ""),
                )
                previous = event_context.setdefault(key, (departure_day, arrival_day))
                if previous != (departure_day, arrival_day):
                    issues.append(
                        _issue(
                            "error",
                            "transport_event_context_inconsistent",
                            row=event,
                            details=(
                                f"shipment_id={shipment_id} first={previous} "
                                f"current={(departure_day, arrival_day)}"
                            ),
                        )
                    )

            for link in transport_links:
                shipment_id = str(link.get("shipment_id") or "")
                if not shipment_id:
                    continue
                parent_key = (
                    shipment_id,
                    "lane_ship",
                    str(link.get("parent_lot_id") or ""),
                )
                child_key = (
                    shipment_id,
                    "lane_receipt",
                    str(link.get("child_lot_id") or ""),
                )
                if parent_key in event_context and event_context[parent_key] != (
                    as_int(link.get("departure_day")),
                    as_int(link.get("arrival_day")),
                ):
                    issues.append(
                        _issue(
                            "error",
                            "transport_ship_event_link_dates_mismatch",
                            row=link,
                            details=f"shipment_id={shipment_id}",
                        )
                    )
                if child_key in event_context and event_context[child_key] != (
                    as_int(link.get("departure_day")),
                    as_int(link.get("arrival_day")),
                ):
                    issues.append(
                        _issue(
                            "error",
                            "transport_receipt_event_link_dates_mismatch",
                            row=link,
                            details=f"shipment_id={shipment_id}",
                        )
                    )

    # Aggregate/backorder receipts are valid only when their trace boundary is explicit.
    unparented_receipts = [
        event
        for lot_id, event in creations.items()
        if str(event.get("event_type") or "") == "lane_receipt"
        and not any(str(link.get("link_type") or "") == "transport" for link in links_by_child.get(lot_id, []))
    ]
    if unparented_receipts and (
        not _has_column(events, "trace_status") or not _has_column(events, "trace_reason")
    ):
        issues.append(
            _issue(
                "migration",
                "migration_debt_untraced_origin_status",
                details=f"unparented_receipts={len(unparented_receipts)}",
            )
        )
    else:
        for event in unparented_receipts:
            status = str(event.get("trace_status") or "")
            reason = str(event.get("trace_reason") or "")
            if not status.startswith("untraced") or not reason:
                issues.append(
                    _issue(
                        "error",
                        "untraced_origin_not_explicit",
                        row=event,
                        details=f"trace_status={status or 'missing'} trace_reason={reason or 'missing'}",
                    )
                )

    # Accepted PF paths include the physical factory -> DC -> customer sequence.
    demand_lots = {
        str(event.get("lot_id") or "")
        for event in events
        if str(event.get("event_type") or "") == "demand_service"
    }
    demand_ancestors = set(demand_lots)
    queue: deque[str] = deque(demand_lots)
    while queue:
        child = queue.popleft()
        for link in links_by_child.get(child, []):
            parent = str(link.get("parent_lot_id") or "")
            if parent and parent not in demand_ancestors:
                demand_ancestors.add(parent)
                queue.append(parent)
    for lot_id, creation in creations.items():
        if (
            str(creation.get("event_type") or "") == "production_output"
            and _normalized_item(creation.get("item_id")) in {"268091", "268967"}
            and lot_id in demand_ancestors
            and not _pf_has_factory_dc_customer_path(
                lot_id, links_by_parent, demand_lots, node_types
            )
        ):
            issues.append(
                _issue(
                    "error",
                    "finished_product_path_missing_supply_stage",
                    row=creation,
                    lot_id=lot_id,
                    details="consumed PF must follow factory -> distribution center -> customer",
                )
            )

    # PFI 773474 produced upstream must physically reach M-1430 before use there.
    for lot_id, creation in creations.items():
        if (
            str(creation.get("event_type") or "") != "production_output"
            or _normalized_item(creation.get("item_id")) != "773474"
            or _canonical_node(creation.get("node_id")) == "M-1430"
        ):
            continue
        reachable = _reachable_links(lot_id, links_by_parent)
        used_at_m1430 = any(
            str(link.get("link_type") or "") == "production"
            and _canonical_node(link.get("parent_node_id")) == "M-1430"
            and _normalized_item(link.get("parent_item_id")) == "773474"
            for link in reachable
        )
        reaches_m1430 = any(
            str(link.get("link_type") or "") == "transport"
            and _canonical_node(link.get("child_node_id")) == "M-1430"
            and _normalized_item(link.get("child_item_id")) == "773474"
            for link in reachable
        )
        if used_at_m1430 and not reaches_m1430:
            issues.append(
                _issue(
                    "error",
                    "semifinished_path_missing_m1430_transport",
                    row=creation,
                    lot_id=lot_id,
                    details="PFI 773474 used at M-1430 has no traced upstream-site -> M-1430 transport",
                )
            )

    return issues


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    data_dir = output_root / "data"
    events = read_csv(data_dir / "production_lot_events.csv")
    links = read_csv(data_dir / "production_lot_genealogy.csv")
    acceptance_issues = audit_acceptance_semantics(events, links)
    creations = first_events(events)
    events_by_lot: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        events_by_lot[event.get("lot_id", "")].append(event)

    children: dict[str, set[str]] = defaultdict(set)
    parents: dict[str, set[str]] = defaultdict(set)
    links_by_child: dict[str, list[dict[str, str]]] = defaultdict(list)
    for link in links:
        parent = link.get("parent_lot_id", "")
        child = link.get("child_lot_id", "")
        if parent and child:
            children[parent].add(child)
            parents[child].add(parent)
            links_by_child[child].append(link)

    event_types = Counter(row.get("event_type", "") for row in events)
    link_types = Counter(row.get("link_type", "") for row in links)

    # Lot identity should be stable after creation.
    node_changes = 0
    item_changes = 0
    uom_changes = 0
    for lot_id, creation in creations.items():
        lot_events = events_by_lot.get(lot_id, [])
        nodes = {row.get("node_id", "") for row in lot_events if row.get("node_id")}
        items = {row.get("item_id", "") for row in lot_events if row.get("item_id")}
        uoms = {row.get("uom", "") for row in lot_events if row.get("uom")}
        node_changes += len(nodes) > 1
        item_changes += len(items) > 1
        uom_changes += len(uoms) > 1

    # Production contribution: the relevant denominator is each BOM item,
    # never the sum of quantities expressed in heterogeneous units.
    production_links = [row for row in links if row.get("link_type") == "production"]
    production_by_child_item: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    production_uoms_by_child: dict[str, set[str]] = defaultdict(set)
    event_uom = {(row.get("lot_id", ""), row.get("item_id", "")): row.get("uom", "") for row in events}
    for link in production_links:
        child = link.get("child_lot_id", "")
        parent_item = link.get("parent_item_id", "")
        production_by_child_item[(child, parent_item)].append(link)
        parent_lot = link.get("parent_lot_id", "")
        uom = event_uom.get((parent_lot, parent_item), "")
        if uom:
            production_uoms_by_child[child].add(uom)

    split_groups = []
    attribution_factors: list[float] = []
    attribution_examples: list[tuple[float, dict[str, str], float, float]] = []
    for rows in production_by_child_item.values():
        unique_lots = {row.get("parent_lot_id", "") for row in rows}
        total = sum(as_float(row.get("parent_qty")) for row in rows)
        if len(unique_lots) <= 1 or total <= EPS:
            continue
        split_groups.append(rows)
        for row in rows:
            parent_qty = as_float(row.get("parent_qty"))
            child_qty = as_float(row.get("child_qty"))
            expected = child_qty * parent_qty / total if total > EPS else 0.0
            factor = child_qty / expected if expected > EPS else math.inf
            if math.isfinite(factor):
                attribution_factors.append(factor)
                attribution_examples.append((factor, row, total, expected))

    mixed_uom_productions = sum(len(uoms) > 1 for uoms in production_uoms_by_child.values())
    split_children = {row.get("child_lot_id", "") for rows in split_groups for row in rows}

    # Transport must use an explicit simulated shipment identity. The
    # route/day/item grouping is retained only to quantify legacy fallback.
    transport_links = [row for row in links if row.get("link_type") == "transport"]
    transport_groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in transport_links:
        key = (
            row.get("day", ""),
            row.get("parent_node_id", ""),
            row.get("child_node_id", ""),
            row.get("child_item_id", "") or row.get("parent_item_id", ""),
        )
        transport_groups[key].append(row)
    multi_parent_transport_groups = sum(
        len({row.get("parent_lot_id", "") for row in rows}) > 1 for rows in transport_groups.values()
    )
    multi_child_transport_groups = sum(
        len({row.get("child_lot_id", "") for row in rows}) > 1 for rows in transport_groups.values()
    )
    shipments: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in transport_links:
        shipment_id = str(row.get("shipment_id") or "").strip()
        if shipment_id:
            shipments[shipment_id].append(row)
    explicit_transport_links = sum(bool(str(row.get("shipment_id") or "").strip()) for row in transport_links)
    multi_item_shipments = sum(
        len(
            {
                str(row.get("child_item_id") or row.get("parent_item_id") or "")
                for row in rows
            }
        )
        > 1
        for rows in shipments.values()
    )
    known_handling_units = {
        str(row.get("handling_unit_id") or "").strip()
        for row in transport_links
        if str(row.get("handling_unit_id") or "").strip()
    }
    lane_receipt_lots = {
        lot_id for lot_id, event in creations.items() if event.get("event_type") == "lane_receipt"
    }
    unparented_receipts = [
        lot_id
        for lot_id in lane_receipt_lots
        if not any(row.get("link_type") == "transport" for row in links_by_child.get(lot_id, []))
    ]
    customer_receipts = [
        lot_id
        for lot_id in lane_receipt_lots
        if str(creations[lot_id].get("node_id", "")).startswith("C-")
    ]
    mixed_customer_receipts = [
        lot_id
        for lot_id in customer_receipts
        if len(
            {
                row.get("parent_lot_id", "")
                for row in links_by_child.get(lot_id, [])
                if row.get("link_type") == "transport"
            }
        )
        > 1
    ]
    explicitly_untraced_receipts = [
        lot_id
        for lot_id in unparented_receipts
        if str(creations[lot_id].get("trace_status") or "").startswith("untraced")
        and str(creations[lot_id].get("trace_reason") or "").strip()
    ]
    mixed_batch_occurrences = [
        lot_id
        for lot_id, event in creations.items()
        if str(event.get("trace_status") or "") == "mixed_batch_occurrence"
    ]
    partially_traced_occurrences = [
        lot_id
        for lot_id, event in creations.items()
        if str(event.get("trace_status") or "") == "partially_traced_mixed_occurrence"
    ]
    acceptance_errors = [row for row in acceptance_issues if row["severity"] == "error"]
    migration_debts = [row for row in acceptance_issues if row["severity"] == "migration"]
    contribution_errors = [
        row
        for row in acceptance_errors
        if row["kind"].startswith("production_component_")
    ]
    transport_errors = [
        row
        for row in acceptance_errors
        if row["kind"].startswith("transport_") or row["kind"].startswith("shipment_")
    ]
    identity_errors = [
        row
        for row in acceptance_errors
        if "identity" in row["kind"] or "occurrence" in row["kind"]
    ]

    # Exact end-to-end coverage.
    demand_lots = {
        row.get("lot_id", "") for row in events if row.get("event_type") == "demand_service"
    }
    demand_ancestors = set(demand_lots)
    queue = deque(demand_lots)
    while queue:
        child = queue.popleft()
        for parent in parents.get(child, set()):
            if parent not in demand_ancestors:
                demand_ancestors.add(parent)
                queue.append(parent)

    production_lots = [
        lot_id for lot_id, event in creations.items() if event.get("event_type") == "production_output"
    ]
    supplier_lots = [
        lot_id
        for lot_id, event in creations.items()
        if str(event.get("node_id", "")).startswith("SDC-")
        and event.get("event_type") in {"opening_stock", "external_procurement_receipt"}
    ]
    produced_by_item: dict[str, list[str]] = defaultdict(list)
    for lot_id in production_lots:
        produced_by_item[creations[lot_id].get("item_id", "")].append(lot_id)

    max_upstream = (0, "")
    max_downstream = (0, "")
    for lot_id in [*production_lots, *supplier_lots]:
        upstream_count = len(walk(parents, lot_id))
        downstream_count = len(walk(children, lot_id))
        max_upstream = max(max_upstream, (upstream_count, lot_id))
        max_downstream = max(max_downstream, (downstream_count, lot_id))

    per_item_rows = []
    for item_id, lot_ids in sorted(produced_by_item.items()):
        if len(lot_ids) < 10:
            continue
        reached = sum(lot_id in demand_ancestors for lot_id in lot_ids)
        per_item_rows.append([item_id, len(lot_ids), reached, pct(reached, len(lot_ids))])

    unreached_production_rows = []
    for lot_id in production_lots:
        if lot_id in demand_ancestors:
            continue
        creation = creations[lot_id]
        descendants = walk(children, lot_id)
        descendant_events = [
            event
            for descendant_id in descendants
            for event in events_by_lot.get(descendant_id, [])
        ]
        last_visible_day = max(
            [
                as_int(event.get("day"))
                for event in [*events_by_lot.get(lot_id, []), *descendant_events]
            ],
            default=as_int(creation.get("day")),
        )
        unreached_production_rows.append(
            [
                lot_id,
                creation.get("item_id", ""),
                creation.get("node_id", ""),
                as_int(creation.get("day")),
                f"{as_float(creation.get('qty')):.1f} {creation.get('uom', '')}".strip(),
                len(descendants),
                last_visible_day,
            ]
        )
    unreached_production_rows.sort(key=lambda row: (row[3], row[0]))

    attribution_examples.sort(key=lambda value: value[0], reverse=True)
    legacy_median = (
        f"x{statistics.median(attribution_factors):.2f}"
        if attribution_factors
        else "n/a"
    )
    legacy_p90 = (
        f"x{quantile(attribution_factors, 0.90):.2f}"
        if attribution_factors
        else "n/a"
    )
    example_rows = [
        [
            row.get("parent_lot_id", ""),
            row.get("parent_item_id", ""),
            row.get("child_lot_id", ""),
            f"{as_float(row.get('parent_qty')):.1f}",
            f"{total:.1f}",
            f"{expected:.1f}",
            f"x{factor:.1f} évité",
        ]
        for factor, row, total, expected in attribution_examples[: args.max_examples]
    ]

    report_path = Path(args.report) if args.report else output_root / "reports" / "lot_trace_semantic_diagnostic.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = f"""# Diagnostic semantique de la lotification

## Perimetre
- Run: `{output_root}`
- Lots: **{len(creations):,}**
- Evenements: **{len(events):,}**
- Liens genealogiques: **{len(links):,}**
- Types d'evenements: `{dict(event_types)}`
- Types de liens: `{dict(link_types)}`

## Verdict
{"La généalogie respecte le contrat quantitatif et logistique contrôlé sur ce run."
if not acceptance_errors else
"La généalogie contient encore des erreurs bloquantes listées ci-dessous."}
Les contributions MP/PFI -> PF sont calculées séparément par composant et unité.
Les mouvements logistiques disposent d'une identité d'expédition simulée et de dates de
départ/arrivée. Cette identité décrit un mouvement simulé ; elle ne prouve ni un camion
réel ni une palette réelle. Les réceptions issues de flux agrégés restent explicitement
signalées comme origine non tracée par lot.

## Acceptation du schema lotification
- Erreurs bloquantes: **{len(acceptance_errors)}**
- Dettes de migration anciens runs: **{len(migration_debts)}**

{markdown_table(
    ["Severite", "Controle", "Lot", "Details"],
    [
        [row["severity"], row["kind"], row["lot_id"], row["details"]]
        for row in acceptance_issues[: max(args.max_examples * 3, 12)]
    ],
)}

## Controle de chaque chemin
- Lots qui changent de noeud sans creation d'un lot enfant: **{node_changes}**
- Lots qui changent d'item: **{item_changes}**
- Lots qui changent d'unite: **{uom_changes}**
- Lots de production atteignant une consommation client: **{sum(lot in demand_ancestors for lot in production_lots)} / {len(production_lots)}** ({pct(sum(lot in demand_ancestors for lot in production_lots), len(production_lots))})
- Lots fournisseur atteignant une consommation client: **{sum(lot in demand_ancestors for lot in supplier_lots)} / {len(supplier_lots)}** ({pct(sum(lot in demand_ancestors for lot in supplier_lots), len(supplier_lots))})
- Plus grande ascendance exacte: **{max_upstream[0]} lots** pour `{max_upstream[1]}`
- Plus grande descendance exacte: **{max_downstream[0]} lots** pour `{max_downstream[1]}`
- Aucun chemin n'atteint la limite technique de 5 000 lots utilisee pour les statistiques.

{markdown_table(["Item produit", "Lots produits", "Atteignent le client", "Couverture"], per_item_rows)}

Lots produits sans consommation client observee avant la fin de l'horizon:

{markdown_table(
    ["Lot", "Item", "Site de production", "Jour de production", "Quantite", "Descendants", "Dernier jour visible"],
    unreached_production_rows[: max(args.max_examples * 2, 20)],
)}

## Production et contribution quantitative
- Liens de production: **{len(production_links):,}**
- Campagnes/enfants utilisant plusieurs lots pour un meme composant: **{len(split_children):,} / {len(production_lots):,}**
- Groupes enfant-composant repartis sur plusieurs lots: **{len(split_groups):,}**
- Erreurs actuelles de part par composant: **{len(contribution_errors):,}**
- Liens qui auraient été surestimés par l'ancien calcul global: **{len(attribution_factors):,}**
- Surestimation historique évitée, médiane: **{legacy_median}**
- Surestimation historique évitée, p90: **{legacy_p90}**
- Productions combinant plusieurs unites BOM: **{mixed_uom_productions:,}**. Une part globale calculee en additionnant G, KG, M et UN n'a pas de sens physique.

La contribution exportée utilise désormais:
`quantite du lot consommée / quantité totale du même composant et de la même unité`,
puis applique cette part à la quantité produite.

{markdown_table(["Lot parent", "Composant", "Lot produit", "Conso lot", "Conso composant", "PF attribuable", "Risque historique évité"], example_rows)}

## Transports
- Liens de transport: **{len(transport_links):,}**
- Liens rattachés à une expédition simulée explicite: **{explicit_transport_links:,} / {len(transport_links):,}**
- Expéditions simulées distinctes: **{len(shipments):,}**
- Expéditions simulées contenant plusieurs articles: **{multi_item_shipments:,}**
- Erreurs actuelles d'identité/date d'expédition: **{len(transport_errors):,}**
- Groupes hérités `jour + route + item` (diagnostic de compatibilité): **{len(transport_groups):,}**
- Groupes hérités fusionnant plusieurs lots parents: **{multi_parent_transport_groups:,}**
- Groupes hérités produisant plusieurs lots reçus: **{multi_child_transport_groups:,}**
- Lots de reception sans parent transport trace: **{len(unparented_receipts):,} / {len(lane_receipt_lots):,}**
- Origines non tracées explicitement justifiées: **{len(explicitly_untraced_receipts):,} / {len(unparented_receipts):,}**
- Lots clients melangeant plusieurs lots parents: **{len(mixed_customer_receipts):,} / {len(customer_receipts):,}**
- Occurrences de stock mélangeant plusieurs lots métier: **{len(mixed_batch_occurrences):,}**
- Occurrences mélangeant lots identifiés et origine inconnue: **{len(partially_traced_occurrences):,}**
- Unités logistiques réellement connues: **{len(known_handling_units):,}**

`shipment_id` représente une expédition simulée consolidée par route, départ et arrivée.
Il peut contenir plusieurs articles. `handling_unit_id` reste vide tant que les données
source ne décrivent pas les palettes, conteneurs ou numéros de transport réels.

## Identite et nommage
- Erreurs actuelles d'identité: **{len(identity_errors):,}**
- `business_batch_id`: identité métier stable à travers les mouvements simples.
- `lot_occurrence_id`: occurrence distincte sur un site ou dans un stock.
- `shipment_id`: mouvement logistique simulé, distinct du lot et de l'occurrence.
- Une réception consolidée de plusieurs lots métier conserve leurs identités dans
  `provenance_batch_id` et ne crée pas un faux lot métier unique.
- Les libellés métier sont traduits dans le payload d'affichage ; les codes techniques
  restent disponibles dans les données d'audit.

## Priorites
1. **P1 - Historique amont**: fournir le détail lot des {len(unparented_receipts)} réceptions agrégées si l'industriel le possède.
2. **P1 - Logistique réelle**: importer numéro de transport, palette/contenant et capacité réelle pour passer d'une expédition simulée à un voyage observé.
3. **P2 - Pré-horizon**: importer l'historique avant J0 pour relier les stocks initiaux à leur fournisseur réel.
"""
    report_path.write_text(report, encoding="utf-8")
    print(f"[OK] Semantic lot diagnostic: {report_path.resolve()}")


if __name__ == "__main__":
    main()
