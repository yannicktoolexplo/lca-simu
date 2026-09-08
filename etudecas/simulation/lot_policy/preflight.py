from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable

from .models import LotPolicyRegistry, PolicyScope, PolicySource
from .uom import (
    IncompatibleUomError,
    as_decimal,
    convert_quantity,
    normalize_uom,
    quantity_multiple,
)


class PreflightSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class CandidateLotQuantity:
    item_id: str
    scope: PolicyScope
    quantity: Decimal
    uom: str
    source_ref: str
    field_name: str
    site_id: str = ""
    supplier_id: str = ""
    origin_id: str = ""
    destination_id: str = ""

    def __init__(
        self,
        *,
        item_id: str,
        scope: PolicyScope,
        quantity: Decimal | float | int | str,
        uom: str,
        source_ref: str,
        field_name: str,
        site_id: str = "",
        supplier_id: str = "",
        origin_id: str = "",
        destination_id: str = "",
    ) -> None:
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "quantity", as_decimal(quantity))
        object.__setattr__(self, "uom", normalize_uom(uom))
        object.__setattr__(self, "source_ref", source_ref)
        object.__setattr__(self, "field_name", field_name)
        object.__setattr__(self, "site_id", site_id)
        object.__setattr__(self, "supplier_id", supplier_id)
        object.__setattr__(self, "origin_id", origin_id)
        object.__setattr__(self, "destination_id", destination_id)


@dataclass(frozen=True)
class PreflightIssue:
    severity: PreflightSeverity
    code: str
    message: str
    item_id: str
    source_ref: str
    canonical_source: PolicySource | None = None


def _issue(
    candidate: CandidateLotQuantity,
    *,
    code: str,
    message: str,
    source: PolicySource | None,
    severity: PreflightSeverity = PreflightSeverity.ERROR,
) -> PreflightIssue:
    return PreflightIssue(
        severity=severity,
        code=code,
        message=message,
        item_id=candidate.item_id,
        source_ref=candidate.source_ref,
        canonical_source=source,
    )


def _ratio_issue(
    candidate: CandidateLotQuantity,
    candidate_in_policy_uom: Decimal,
    canonical_qty: Decimal,
    canonical_uom: str,
    source: PolicySource,
) -> PreflightIssue | None:
    if canonical_qty <= 0:
        return None
    ratio = candidate_in_policy_uom / canonical_qty
    if ratio in {Decimal("1000"), Decimal("0.001")}:
        return _issue(
            candidate,
            code="likely_mass_conversion_applied_without_uom_change",
            message=(
                f"{candidate.quantity} {candidate.uom} differs from the canonical "
                f"{canonical_qty} {canonical_uom} by exactly x{ratio}; check a G/KG "
                "conversion applied to the value without changing the UOM."
            ),
            source=source,
        )
    return None


def preflight_candidate(
    candidate: CandidateLotQuantity,
    registry: LotPolicyRegistry,
) -> list[PreflightIssue]:
    policy = registry.get(candidate.item_id)
    if policy is None:
        return [
            _issue(
                candidate,
                code="no_canonical_policy",
                message=f"No canonical lot policy is registered for {candidate.item_id}.",
                source=None,
                severity=PreflightSeverity.WARNING,
            )
        ]
    if candidate.quantity <= 0:
        return [
            _issue(
                candidate,
                code="non_positive_quantity",
                message="Lot-policy quantities must be positive.",
                source=None,
            )
        ]
    if candidate.uom not in policy.uom.allowed_uoms:
        return [
            _issue(
                candidate,
                code="uom_not_allowed",
                message=(
                    f"{candidate.uom} is not allowed for {candidate.item_id}; "
                    f"expected one of {policy.uom.allowed_uoms}."
                ),
                source=None,
            )
        ]

    issues: list[PreflightIssue] = []
    if candidate.scope == PolicyScope.PROCUREMENT:
        matching = [
            rule
            for rule in policy.procurement
            if (not candidate.supplier_id or rule.supplier_id == candidate.supplier_id)
            and (not candidate.destination_id or rule.destination_id == candidate.destination_id)
        ]
        if policy.procurement and not matching:
            return [
                _issue(
                    candidate,
                    code="no_matching_procurement_route",
                    message=(
                        f"No procurement rule matches supplier {candidate.supplier_id or '*'} "
                        f"and destination {candidate.destination_id or '*'}."
                    ),
                    source=None,
                    severity=PreflightSeverity.WARNING,
                )
            ]
        for rule in matching:
            try:
                amount = convert_quantity(candidate.quantity, candidate.uom, rule.uom)
            except IncompatibleUomError as exc:
                issues.append(
                    _issue(
                        candidate,
                        code="incompatible_procurement_uom",
                        message=str(exc),
                        source=rule.source,
                    )
                )
                continue
            ratio_issue = _ratio_issue(candidate, amount, rule.moq, rule.uom, rule.source)
            if ratio_issue:
                issues.append(ratio_issue)
            if amount < rule.moq:
                issues.append(
                    _issue(
                        candidate,
                        code="below_procurement_moq",
                        message=f"{amount} {rule.uom} is below MOQ {rule.moq} {rule.uom}.",
                        source=rule.source,
                    )
                )
            if rule.order_multiple is not None and not quantity_multiple(amount, rule.order_multiple):
                issues.append(
                    _issue(
                        candidate,
                        code="not_procurement_order_multiple",
                        message=(
                            f"{amount} {rule.uom} is not a multiple of "
                            f"{rule.order_multiple} {rule.uom}."
                        ),
                        source=rule.source,
                    )
                )
    elif candidate.scope == PolicyScope.PRODUCTION:
        matching = [
            rule
            for rule in policy.production
            if not candidate.site_id or rule.site_id == candidate.site_id
        ]
        if policy.production and not matching:
            return [
                _issue(
                    candidate,
                    code="no_matching_production_site",
                    message=f"No production rule matches site {candidate.site_id or '*'}.",
                    source=None,
                    severity=PreflightSeverity.WARNING,
                )
            ]
        for rule in matching:
            try:
                amount = convert_quantity(candidate.quantity, candidate.uom, rule.uom)
            except IncompatibleUomError as exc:
                issues.append(
                    _issue(
                        candidate,
                        code="incompatible_production_uom",
                        message=str(exc),
                        source=rule.source,
                    )
                )
                continue
            if rule.fixed_qty is not None and amount != rule.fixed_qty:
                issues.append(
                    _issue(
                        candidate,
                        code="production_fixed_lot_mismatch",
                        message=(
                            f"{amount} {rule.uom} differs from fixed production lot "
                            f"{rule.fixed_qty} {rule.uom}."
                        ),
                        source=rule.source,
                    )
                )
            if rule.minimum_qty is not None and amount < rule.minimum_qty:
                issues.append(
                    _issue(
                        candidate,
                        code="below_production_minimum",
                        message=f"{amount} {rule.uom} is below {rule.minimum_qty} {rule.uom}.",
                        source=rule.source,
                    )
                )
            if rule.maximum_qty is not None and amount > rule.maximum_qty:
                issues.append(
                    _issue(
                        candidate,
                        code="above_production_maximum",
                        message=f"{amount} {rule.uom} exceeds {rule.maximum_qty} {rule.uom}.",
                        source=rule.source,
                    )
                )
            if rule.multiple_qty is not None and not quantity_multiple(amount, rule.multiple_qty):
                issues.append(
                    _issue(
                        candidate,
                        code="not_production_multiple",
                        message=f"{amount} {rule.uom} is not a multiple of {rule.multiple_qty} {rule.uom}.",
                        source=rule.source,
                    )
                )
    elif candidate.scope == PolicyScope.TRANSPORT:
        matching = [
            rule
            for rule in policy.transport
            if (not candidate.origin_id or rule.origin_id == candidate.origin_id)
            and (not candidate.destination_id or rule.destination_id == candidate.destination_id)
        ]
        if policy.transport and not matching:
            return [
                _issue(
                    candidate,
                    code="no_matching_transport_route",
                    message=(
                        f"No transport rule matches route {candidate.origin_id or '*'} -> "
                        f"{candidate.destination_id or '*'}."
                    ),
                    source=None,
                    severity=PreflightSeverity.WARNING,
                )
            ]
        for rule in matching:
            try:
                amount = convert_quantity(candidate.quantity, candidate.uom, rule.uom)
            except IncompatibleUomError as exc:
                issues.append(
                    _issue(
                        candidate,
                        code="incompatible_transport_uom",
                        message=str(exc),
                        source=rule.source,
                    )
                )
                continue
            if rule.minimum_dispatch_qty is not None and amount < rule.minimum_dispatch_qty:
                issues.append(
                    _issue(
                        candidate,
                        code="below_transport_dispatch_minimum",
                        message=(
                            f"{amount} {rule.uom} is below the physical dispatch minimum "
                            f"{rule.minimum_dispatch_qty} {rule.uom}."
                        ),
                        source=rule.source,
                    )
                )
            if rule.dispatch_multiple is not None and not quantity_multiple(amount, rule.dispatch_multiple):
                issues.append(
                    _issue(
                        candidate,
                        code="not_transport_dispatch_multiple",
                        message=(
                            f"{amount} {rule.uom} is not a dispatch multiple of "
                            f"{rule.dispatch_multiple} {rule.uom}."
                        ),
                        source=rule.source,
                    )
                )
    return issues


def _edge_item_ids(edge: dict[str, Any]) -> Iterable[str]:
    for value in edge.get("items") or []:
        if value:
            yield str(value)


def preflight_graph(
    graph: dict[str, Any],
    registry: LotPolicyRegistry,
) -> list[PreflightIssue]:
    """Audit graph lot quantities without modifying source data."""

    issues: list[PreflightIssue] = []
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        raw_qty = attrs.get("standard_order_qty")
        raw_uom = attrs.get("standard_order_uom")
        if raw_qty in {None, ""} or raw_uom in {None, ""}:
            continue
        origin = str(edge.get("from") or "")
        destination = str(edge.get("to") or "")
        for item_id in _edge_item_ids(edge):
            policy = registry.get(item_id)
            if policy is None:
                continue
            is_internal_transport = any(
                rule.origin_id == origin and rule.destination_id == destination
                for rule in policy.transport
            )
            scope = PolicyScope.TRANSPORT if is_internal_transport else PolicyScope.PROCUREMENT
            issues.extend(
                preflight_candidate(
                    CandidateLotQuantity(
                        item_id=item_id,
                        scope=scope,
                        quantity=raw_qty,
                        uom=str(raw_uom),
                        source_ref=str(edge.get("id") or "graph_edge"),
                        field_name="attrs.standard_order_qty",
                        supplier_id=origin,
                        origin_id=origin,
                        destination_id=destination,
                    ),
                    registry,
                )
            )
    return issues
