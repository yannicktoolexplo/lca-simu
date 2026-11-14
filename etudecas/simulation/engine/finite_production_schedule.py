"""Finite, dated placement of new lots on one explicitly known resource.

This is a planning calculation, not a physical execution or a netting pass.
Quantities and requested dates are immutable. The caller converts original
MRP margins into latest_start_day: no tau is added to physical work here.
Capacity and both availability calendars must be known at the decision date.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math
from numbers import Real
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ProductionLotRequest:
    proposal_id: str
    qty: float
    physical_due_day: int
    requested_available_day: int
    latest_start_day: int
    priority: int = 0


@dataclass(frozen=True)
class ScheduledProductionLot:
    request: ProductionLotRequest
    start_day: int | None
    physical_finish_day: int | None
    available_day: int | None
    allocations: tuple[tuple[int, float], ...]
    delay_days: int | None
    physical_delay_days: int | None
    start_margin_shortfall_days: int | None
    status: str
    earliest_start_day: int | None = None
    earliest_finish_day: int | None = None
    effective_physical_due_day: int | None = None
    effective_available_due_day: int | None = None
    effective_latest_start_day: int | None = None


@dataclass(frozen=True)
class FiniteProductionSchedule:
    lots: tuple[ScheduledProductionLot, ...]
    additional_load_by_day: tuple[tuple[int, float], ...]
    remaining_capacity_by_day: tuple[tuple[int, float], ...]
    blocked_same_day_capacity_by_day: tuple[tuple[int, float], ...]
    unscheduled_lot_ids: tuple[str, ...]
    first_work_day: int
    horizon_end_day: int
    capacity_known_day: int
    strategy: str = "earliest_EDF_bounds_then_latest_noninterleaved"


def _day(value, label, *, nonnegative=True):
    if type(value) is not int or (nonnegative and value < 0):
        raise ValueError(f"{label} must be an integer calendar day")
    return value


def _quantity(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be finite numeric work quantity")
    try:
        numeric = float(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be finite numeric work quantity") from error
    if not math.isfinite(numeric) or numeric < 0 or (positive and numeric == 0):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}")
    return Decimal(str(numeric))


def schedule_production_lots(
    requests: Iterable[ProductionLotRequest], *, decision_day: int,
    first_work_day: int, capacity_known_day: int,
    capacity_by_day: Mapping[int, float], reserved_by_day: Mapping[int, float],
    availability_by_start_day: Mapping[int, int],
    availability_by_finish_day: Mapping[int, int], allow_intraday: bool = False,
    allowed_start_days: Iterable[int] | None = None,
) -> FiniteProductionSchedule:
    """Place whole requests, without interleaving, inside a known finite horizon.

    First compute an earliest EDF witness. Relax a date constraint only as far
    as that witness requires, then place all requests backwards. Thus one
    unavoidable early delay does not advance every distant future request.

    Daily capacity is work in the same unit as quantities, not finished stock.
    Fractional work is supported; the caller enforces integer UN finished lots.
    Reservations are dated pre-existing work: a future reservation never blocks
    all earlier days. Sharing a reserved day requires intraday. The caller can
    postpone first_work_day if an active campaign bars new starts. A missing
    capacity/calendar day is invalid, never an observed zero.
    allowed_start_days restricts new starts only, never work already underway.

    Latest-start bounds denote the beginning of that day, or the earliest EDF
    position if it already shares that day. This conservative day convention
    avoids artificial infinitesimal work fragments merely to meet a margin.
    Availability is max(start-calendar[start], finish-calendar[finish]).
    No duration, tau, closure, capacity or quality rule is inferred here.
    """
    _day(decision_day, "Decision day")
    _day(first_work_day, "First work day")
    _day(capacity_known_day, "Capacity knowledge day", nonnegative=False)
    if first_work_day < decision_day or capacity_known_day > decision_day:
        raise ValueError("Work and capacity knowledge must be causal")
    if type(allow_intraday) is not bool:
        raise ValueError("Intraday permission must be explicit boolean")
    if not isinstance(capacity_by_day, Mapping) or not capacity_by_day:
        raise ValueError("Finite scheduling requires an explicit nonempty capacity horizon")
    for day in capacity_by_day:
        _day(day, "Capacity day")
    end = max(capacity_by_day)
    if (min(capacity_by_day) != first_work_day
            or len(capacity_by_day) != end - first_work_day + 1):
        raise ValueError("Capacity must cover every known day from first_work_day; missing is unknown")
    days = tuple(range(first_work_day, end + 1))
    capacity = {day: _quantity(capacity_by_day[day], "Capacity") for day in days}
    try:
        allowed_starts = set(days if allowed_start_days is None else allowed_start_days)
    except TypeError as error:
        raise ValueError("Allowed start days must be an explicit iterable of days") from error
    if any(type(day) is not int or day not in capacity for day in allowed_starts):
        raise ValueError("Allowed start days must belong to the known capacity horizon")
    calendars = []
    for name, calendar in (("Start availability", availability_by_start_day),
                           ("Finish availability", availability_by_finish_day)):
        if not isinstance(calendar, Mapping) or set(calendar) != set(days):
            raise ValueError(f"{name} requires every capacity-horizon day")
        previous = -1
        copied = {}
        for day in days:
            value = _day(calendar[day], name)
            if value < day or value < previous:
                raise ValueError(f"{name} must be causal and nondecreasing")
            copied[day] = value
            previous = value
        calendars.append(copied)
    start_available, finish_available = calendars
    if not isinstance(reserved_by_day, Mapping) or any(day not in capacity for day in reserved_by_day):
        raise ValueError("Reservations must belong to the known capacity horizon")
    for day in reserved_by_day:
        _day(day, "Reserved day")
    reserved = {day: _quantity(reserved_by_day.get(day, 0), "Reserved work") for day in days}
    if any(reserved[day] > capacity[day] for day in days):
        raise ValueError("Reserved work exceeds its available daily capacity")
    try:
        lots = tuple(requests)
    except TypeError as error:
        raise ValueError("New lots must be an iterable of explicit requests") from error
    identities = set()
    quantities = {}
    for request in lots:
        if not isinstance(request, ProductionLotRequest):
            raise ValueError("New lots must be explicit ProductionLotRequest objects")
        identity = request.proposal_id
        if not isinstance(identity, str) or not identity.strip() or identity in identities:
            raise ValueError("New lots require unique nonempty proposal identities")
        identities.add(identity)
        quantities[identity] = _quantity(request.qty, "Lot quantity", positive=True)
        for label in ("physical_due_day", "requested_available_day", "latest_start_day"):
            _day(getattr(request, label), label, nonnegative=False)
        if type(request.priority) is not int:
            raise ValueError("Lot priority must be an integer")
    ordered = tuple(sorted(lots, key=lambda row: (row.physical_due_day, row.priority, row.proposal_id)))
    free = {day: capacity[day] - reserved[day]
            if allow_intraday or reserved[day] == 0 else Decimal(0) for day in days}
    blocked = {day: capacity[day] - reserved[day] - free[day] for day in days}

    # A contiguous interval on this cumulative-work axis is a noninterleaved
    # lot; calendar closures contribute no capacity, but remain explicit days.
    segments, before, after = [], {}, {}
    total = Decimal(0)
    for day in days:
        before[day] = total
        if free[day] > 0:
            segments.append((day, total, total + free[day]))
        total += free[day]
        after[day] = total

    def profile(start, finish):
        return tuple((day, min(finish, right) - max(start, left))
                     for day, left, right in segments if min(finish, right) > max(start, left))

    earliest = {}
    cursor = Decimal(0)
    unscheduled = []
    for request in ordered:
        qty = quantities[request.proposal_id]
        permitted = next((max(cursor, left) for day, left, right in segments
                          if day in allowed_starts and right > cursor), None)
        if unscheduled or permitted is None or permitted + qty > total:
            unscheduled.append(request.proposal_id)
            continue
        cursor = permitted
        load = profile(cursor, cursor + qty)
        start_day, finish_day = load[0][0], load[-1][0]
        available = max(start_available[start_day], finish_available[finish_day])
        earliest[request.proposal_id] = (cursor, start_day, finish_day, available)
        cursor += qty
        if not allow_intraday:
            cursor = after[finish_day]

    placed, placed_load = {}, {}
    upper = total
    for request in reversed(ordered):
        identity = request.proposal_id
        if identity not in earliest:
            continue
        earliest_position, earliest_start, earliest_finish, earliest_available = earliest[identity]
        physical_bound = max(request.physical_due_day, earliest_finish)
        available_bound = max(request.requested_available_day, earliest_available)
        start_bound = max(request.latest_start_day, earliest_start)
        eligible_finish = [day for day in days if day <= physical_bound and finish_available[day] <= available_bound]
        eligible_start = [day for day in days if free[day] > 0 and day in allowed_starts
                          and day <= start_bound and start_available[day] <= available_bound]
        if not eligible_finish or not eligible_start:
            raise RuntimeError("Earliest feasibility witness lost its calendar bounds")
        finish_limit = min(upper, after[eligible_finish[-1]])
        position = finish_limit - quantities[identity]
        candidate_start = next((day for day, left, right in segments
                                if left <= position < right), None)
        if candidate_start not in eligible_start:
            # When the unconstrained latest start falls on a later calendar day,
            # move to the requested start day, retaining any shared-day position
            # of the EDF witness. No artificial infinitesimal start is invented.
            possible = [day for day in eligible_start
                        if candidate_start is not None and day <= candidate_start]
            if not possible:
                raise RuntimeError("Earliest feasibility witness lost its permitted start")
            position = min(position, max(earliest_position, before[possible[-1]]))
        if position < earliest_position:
            raise RuntimeError("Latest placement violated its earliest feasibility witness")
        load = profile(position, position + quantities[identity])
        start_day, finish_day = load[0][0], load[-1][0]
        available = max(start_available[start_day], finish_available[finish_day])
        if (start_day not in allowed_starts or start_day > start_bound
                or finish_day > physical_bound or available > available_bound
                or sum((qty for _, qty in load), Decimal(0)) != quantities[identity]):
            raise RuntimeError("Latest placement changed quantity or violated its relaxed bounds")
        delay = max(0, available - request.requested_available_day)
        physical_delay = max(0, finish_day - request.physical_due_day)
        margin_shortfall = max(0, start_day - request.latest_start_day)
        status = "late" if delay or physical_delay else "planning_margin_shortfall" if margin_shortfall else "on_time"
        placed[identity] = ScheduledProductionLot(request, start_day, finish_day, available,
            tuple((day, float(qty)) for day, qty in load), delay, physical_delay, margin_shortfall, status,
            earliest_start, earliest_finish, physical_bound, available_bound, start_bound)
        placed_load[identity] = load
        upper = position if allow_intraday else before[start_day]
    additional = {day: Decimal(0) for day in days}
    for load in placed_load.values():
        for day, qty in load:
            additional[day] += qty
    if any(additional[day] + reserved[day] > capacity[day] for day in days):
        raise RuntimeError("Finite schedule overbooks the resource")
    output = tuple(placed.get(request.proposal_id) or ScheduledProductionLot(
        request, None, None, None, (), None, None, None, "beyond_known_capacity_horizon") for request in ordered)
    return FiniteProductionSchedule(output,
        tuple((day, float(additional[day])) for day in days),
        tuple((day, float(capacity[day] - reserved[day] - additional[day])) for day in days),
        tuple((day, float(blocked[day])) for day in days), tuple(unscheduled),
        first_work_day, end, capacity_known_day)
