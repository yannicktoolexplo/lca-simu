"""Apply lot policies to engine quantities and transport requests."""

from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Iterable
from .catalog import canonical_lot_policy_registry
from .models import (
    PolicySource,
    convert_quantity,
    normalize_uom,
    ConsolidatedTransportPlan,
    Quantity,
    TransportConsolidationPolicy,
    TransportRequest,
    round_up_to_multiple,
)
from collections import defaultdict


# Engine adapter

def normalize_item_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("item:") else f"item:{text}"


@dataclass(frozen=True)
class LaneLotDecision:
    quantity: float
    uom: str
    scope: str
    source: str
    confidence: str
    note: str
    order_frequency_days: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "uom": self.uom,
            "scope": self.scope,
            "source": self.source,
            "confidence": self.confidence,
            "note": self.note,
            "order_frequency_days": self.order_frequency_days,
        }


def _source_fields(source: PolicySource) -> tuple[str, str, str]:
    return source.reference, source.confidence.value, source.note


def _converted(value: Decimal, source_uom: str, target_uom: str) -> float:
    return float(convert_quantity(value, source_uom, target_uom))


def resolve_canonical_lane_lot(
    *,
    origin_id: Any,
    destination_id: Any,
    item_id: Any,
    lane_uom: Any,
) -> LaneLotDecision | None:
    """Resolve an explicitly sourced order/dispatch quantum for one lane.

    Production lot sizing is intentionally excluded. A production batch and an
    MRP replenishment order are different business objects: reusing the former
    as ``standard_order_qty`` changes the MRP control law and can suppress
    otherwise valid replenishment demand. Internal truck consolidation is
    derived later from the physical shipment and its source business batch.
    """

    origin = str(origin_id or "").strip()
    destination = str(destination_id or "").strip()
    item = normalize_item_id(item_id)
    target_uom = normalize_uom(lane_uom)
    policy = canonical_lot_policy_registry().get(item)
    if policy is None:
        return None

    for rule in policy.transport:
        if rule.origin_id != origin or rule.destination_id != destination:
            continue
        quantity = rule.dispatch_multiple or rule.minimum_dispatch_qty
        if quantity is None:
            continue
        source, confidence, note = _source_fields(rule.source)
        return LaneLotDecision(
            quantity=_converted(quantity, rule.uom, target_uom),
            uom=target_uom,
            scope="transport",
            source=source,
            confidence=confidence,
            note=note,
            order_frequency_days=rule.window_days,
        )

    for rule in policy.procurement:
        if rule.supplier_id != origin or rule.destination_id != destination:
            continue
        quantity = rule.order_multiple or rule.moq
        source, confidence, note = _source_fields(rule.source)
        return LaneLotDecision(
            quantity=_converted(quantity, rule.uom, target_uom),
            uom=target_uom,
            scope="procurement",
            source=source,
            confidence=confidence,
            note=note,
        )

    return None


def resolve_internal_dispatch_multiple(
    *,
    origin_id: Any,
    destination_id: Any,
    item_id: Any,
    lane_uom: Any,
) -> LaneLotDecision | None:
    """Return the production-batch multiple used to consolidate an internal load.

    This value is a physical dispatch rule only. It must never be used as an
    MRP order quantum or as an input to the inventory-position target.
    """

    origin = str(origin_id or "").strip()
    destination = str(destination_id or "").strip()
    if not (
        (origin.startswith("M-") or origin.startswith("SDC-"))
        and (destination.startswith("M-") or destination.startswith("DC-"))
    ):
        return None
    item = normalize_item_id(item_id)
    target_uom = normalize_uom(lane_uom)
    policy = canonical_lot_policy_registry().get(item)
    if policy is None:
        return None
    for rule in policy.production:
        if rule.site_id != origin:
            continue
        quantity = rule.fixed_qty or rule.multiple_qty or rule.minimum_qty
        if quantity is None:
            continue
        source, confidence, note = _source_fields(rule.source)
        return LaneLotDecision(
            quantity=_converted(quantity, rule.uom, target_uom),
            uom=target_uom,
            scope="internal_physical_dispatch",
            source=source,
            confidence=confidence,
            note=(
                note
                or "Internal road dispatch is consolidated on the production-batch multiple."
            ),
        )
    return None


def normalize_physical_quantity(
    value: Any,
    uom: Any,
    *,
    rounding: str = "nearest",
) -> float:
    """Keep countable physical quantities integral without changing mass/length."""

    quantity = Decimal(str(max(0.0, float(value or 0.0))))
    if normalize_uom(uom) != "UN":
        return float(quantity)
    modes = {
        "nearest": ROUND_HALF_UP,
        "up": ROUND_CEILING,
        "down": ROUND_FLOOR,
    }
    if rounding not in modes:
        raise ValueError(f"Unsupported physical rounding mode: {rounding}")
    return float(quantity.quantize(Decimal("1"), rounding=modes[rounding]))


def required_component_quantity(
    output_quantity: Any,
    requirement_per_output: Any,
    component_uom: Any,
) -> float:
    """Return the physical BOM issue quantity for one production operation."""

    raw_required = max(
        0.0,
        float(output_quantity or 0.0) * float(requirement_per_output or 0.0),
    )
    return normalize_physical_quantity(raw_required, component_uom, rounding="up")


def available_component_quantity(value: Any, component_uom: Any) -> float:
    """Return stock that can physically be issued to a BOM operation."""

    return normalize_physical_quantity(value, component_uom, rounding="down")


# Operations

def consolidate_transport_requests(
    requests: Iterable[TransportRequest],
    policy: TransportConsolidationPolicy,
) -> list[ConsolidatedTransportPlan]:
    """Consolidate demand without confusing demand quantity and dispatch quantity."""

    grouped: dict[int, list[tuple[TransportRequest, Decimal]]] = defaultdict(list)
    for request in requests:
        if request.item_id != policy.item_id:
            raise ValueError(f"Request {request.request_id} has the wrong item")
        if request.origin_id != policy.origin_id or request.destination_id != policy.destination_id:
            raise ValueError(f"Request {request.request_id} has the wrong transport route")
        quantity = convert_quantity(
            request.quantity.value,
            request.quantity.uom,
            policy.uom,
        )
        bucket_start = (request.day // policy.window_days) * policy.window_days
        grouped[bucket_start].append((request, quantity))

    plans: list[ConsolidatedTransportPlan] = []
    for bucket_start in sorted(grouped):
        rows = grouped[bucket_start]
        demand_qty = sum((quantity for _, quantity in rows), Decimal("0"))
        dispatch_qty = demand_qty
        if policy.minimum_dispatch_qty is not None:
            dispatch_qty = max(dispatch_qty, policy.minimum_dispatch_qty)
        if policy.dispatch_multiple is not None:
            dispatch_qty = round_up_to_multiple(dispatch_qty, policy.dispatch_multiple)
        if (
            policy.maximum_dispatch_qty is not None
            and dispatch_qty > policy.maximum_dispatch_qty
        ):
            raise ValueError(
                f"Consolidated dispatch {dispatch_qty} {policy.uom} exceeds "
                f"maximum {policy.maximum_dispatch_qty} {policy.uom}"
            )
        overage = dispatch_qty - demand_qty
        plans.append(
            ConsolidatedTransportPlan(
                item_id=policy.item_id,
                origin_id=policy.origin_id,
                destination_id=policy.destination_id,
                bucket_start_day=bucket_start,
                bucket_end_day=bucket_start + policy.window_days - 1,
                demand_qty=Quantity(demand_qty, policy.uom),
                dispatch_qty=Quantity(dispatch_qty, policy.uom),
                planned_overage_qty=Quantity(overage, policy.uom) if overage > 0 else None,
                request_ids=tuple(request.request_id for request, _ in rows),
            )
        )
    return plans
