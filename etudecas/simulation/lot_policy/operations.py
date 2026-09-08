from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from .models import (
    ConsolidatedTransportPlan,
    Quantity,
    TransportConsolidationPolicy,
    TransportRequest,
)
from .uom import convert_quantity, round_up_to_multiple


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
