from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


LOT_EXECUTION_EPS = 1e-6
LOT_EXECUTION_SEMANTICS_VERSION = "campaign-batch-wip-release-v1"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def physical_batch_target_qty(
    campaign_remaining_qty: float,
    lot_policy: dict[str, Any],
) -> float:
    """Return the quantity of the next indivisible released batch.

    A campaign may contain several fixed batches.  A min/max/multiple campaign
    is already bounded to one batch when it is launched, so its remaining
    quantity is the batch target.  This function deliberately says nothing
    about daily execution capacity: a batch may accumulate in work in progress
    over several days, but it is released only once the full target is reached.
    """

    remaining = max(0.0, _to_float(campaign_remaining_qty, 0.0))
    if remaining <= LOT_EXECUTION_EPS:
        return 0.0
    fixed_qty = max(0.0, _to_float(lot_policy.get("fixed_lot_qty"), 0.0))
    if fixed_qty > LOT_EXECUTION_EPS:
        return min(remaining, fixed_qty)
    return remaining


@dataclass
class ProductionBatchWip:
    """Physical batch state kept outside released finished-goods stock.

    ``executed_qty`` represents work completed on the batch.  It is not a
    finished lot and must not be shipped or consumed as finished goods.  Parent
    allocations are retained until release so genealogy covers every day of a
    multi-day batch, including work executed before day zero.  This state ends
    at execution completion.  A scenario's ``wip.tau_process`` remains a
    planning-cover parameter in the current engine; it is not silently added as
    a second maturation delay by this ledger version.
    """

    campaign_id: str
    batch_id: str
    node_id: str
    item_id: str
    campaign_started_day: int
    batch_started_day: int
    target_qty: float
    executed_qty: float = 0.0
    parent_allocations: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.target_qty = max(0.0, _to_float(self.target_qty, 0.0))
        self.executed_qty = min(
            self.target_qty,
            max(0.0, _to_float(self.executed_qty, 0.0)),
        )
        if self.target_qty <= LOT_EXECUTION_EPS:
            raise ValueError("A physical batch target must be strictly positive.")

    @property
    def remaining_qty(self) -> float:
        return max(0.0, self.target_qty - self.executed_qty)

    @property
    def is_complete(self) -> bool:
        return self.remaining_qty <= LOT_EXECUTION_EPS

    def add_execution(
        self,
        qty: float,
        parent_allocations: list[dict[str, Any]],
    ) -> float:
        """Add daily work and return the accepted quantity.

        The accepted quantity is capped at the batch remainder.  Allocations
        are copied because the simulation reuses its daily temporary lists.
        """

        accepted = min(
            self.remaining_qty,
            max(0.0, _to_float(qty, 0.0)),
        )
        if accepted <= LOT_EXECUTION_EPS:
            return 0.0
        self.executed_qty = min(self.target_qty, self.executed_qty + accepted)
        for allocation in parent_allocations:
            allocation_qty = max(0.0, _to_float(allocation.get("qty"), 0.0))
            if allocation_qty <= LOT_EXECUTION_EPS:
                continue
            self.parent_allocations.append(dict(allocation))
        return accepted


def make_batch_id(campaign_id: str, batch_sequence: int) -> str:
    sequence = max(1, int(batch_sequence))
    return f"{campaign_id}-B{sequence:03d}"


def production_week_index(reported_day: int) -> int:
    """Return a J0-aligned seven-day production bucket.

    Warm-up days are negative and therefore stay outside week zero.  This
    prevents the chosen warm-up length from moving the weekly lot-start limit.
    """

    return int(math.floor(int(reported_day) / 7))
