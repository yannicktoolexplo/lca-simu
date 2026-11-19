"""Place known MRP launches without inventing a machine throughput.

Each lot keeps its identity, quantity and requested date. Calendars and frozen
not-before dates may move its launch; other lots never occupy numeric capacity.
One day of work is the native daily-resolution convention, not a measured
physical duration. Materials remain a separate admission/execution check.
"""
from __future__ import annotations

from bisect import bisect_left
import math

from etudecas.simulation.engine.finite_production_schedule import (
    ProductionLotRequest, ScheduledProductionLot,
)


UNCONSTRAINED_PRODUCTION_POLICY = "unconstrained_lot_calendar_v1"


def schedule_uncapacitated_lots(requests, *, decision_day, first_work_day,
                               calendar_known_day, release_calendar,
                               new_order_not_before=None):
    """Return independent whole-lot placements on an already known calendar."""
    requests = tuple(requests)
    for name, value in (("decision_day", decision_day), ("first_work_day", first_work_day),
                        ("calendar_known_day", calendar_known_day)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer day")
    if calendar_known_day > decision_day:
        raise ValueError("A future calendar cannot schedule a currently known lot")
    if new_order_not_before is None:
        new_order_not_before = first_work_day
    if type(new_order_not_before) is not int or new_order_not_before < decision_day:
        raise ValueError("New-order not-before date must be causal")
    calendar = tuple(release_calendar)
    previous = -1
    for start, available in calendar:
        if (type(start) is not int or type(available) is not int
                or start < 0 or start <= previous or available < start):
            raise ValueError("Release calendar must have unique increasing starts and causal availability")
        previous = start
    starts = [row[0] for row in calendar]
    identities = set()
    result = []
    for row in requests:
        if (not isinstance(row, ProductionLotRequest) or not isinstance(row.proposal_id, str)
                or not row.proposal_id or row.proposal_id in identities):
            raise ValueError("Every lot must have a unique proposal identity")
        if (isinstance(row.qty, bool) or not math.isfinite(row.qty) or row.qty <= 0
                or row.qty != int(row.qty)):
            raise ValueError("Unconstrained PF scheduling requires whole physical units")
        if any(type(value) is not int for value in
               (row.latest_start_day, row.physical_due_day, row.requested_available_day)):
            raise ValueError("Lot dates must be integer calendar days")
        identities.add(row.proposal_id)
        earliest = max(decision_day, first_work_day, new_order_not_before, row.latest_start_day)
        index = bisect_left(starts, earliest)
        if index == len(calendar):
            raise ValueError("Known release calendar does not cover the requested launch")
        start, available = calendar[index]
        result.append(ScheduledProductionLot(
            request=row, start_day=start, physical_finish_day=start, available_day=available,
            allocations=((start, row.qty),),
            delay_days=max(0, available-row.requested_available_day),
            physical_delay_days=max(0, start-row.physical_due_day),
            start_margin_shortfall_days=max(0, start-row.latest_start_day),
            status="scheduled_without_machine_capacity"))
    return tuple(result)


def next_due_frozen_order(*, orders, pair, day, eligible_ids, attempted_ids):
    """Choose another already-due identity, never a new/future/repeated order.

    The initial finite identity set bounds same-day loop iterations without a
    numeric production cap. Callers must check previous physical completion
    and refresh usable stock before attempting the selected order.
    """
    due = [row for row in orders if (row["node_id"], row["item_id"]) == pair
           and row["state"] == "frozen" and row["planned_release_day"] <= day]
    due.sort(key=lambda row: (row["planned_release_day"], row["created_day"], row["order_id"]))
    if not due:
        return None
    identity = due[0]["order_id"]
    return identity if identity in eligible_ids and identity not in attempted_ids else None
