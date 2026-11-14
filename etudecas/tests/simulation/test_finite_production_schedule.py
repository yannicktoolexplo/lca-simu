"""Manual finite-resource oracles; all data and calendars stay in memory."""
from copy import deepcopy
import math

import pytest

from etudecas.simulation.engine.finite_production_schedule import (
    ProductionLotRequest, schedule_production_lots,
)


def lot(identity, due, *, qty=100, latest=None, available=None, priority=0):
    return ProductionLotRequest(identity, qty, due, due if available is None else available,
                                due if latest is None else latest, priority)


def schedule(requests, *, first=1, end=45, daily=25, reserved=None,
             closed=(), intraday=False, start_calendar=None, finish_calendar=None,
             allowed_starts=None):
    capacity = {day: 0 if day in closed else daily for day in range(first, end + 1)}
    calendar = {day: day for day in capacity}
    return schedule_production_lots(requests, decision_day=first - 1,
        first_work_day=first, capacity_known_day=first - 1,
        capacity_by_day=capacity, reserved_by_day=reserved or {},
        availability_by_start_day=start_calendar or calendar,
        availability_by_finish_day=finish_calendar or calendar,
        allow_intraday=intraday, allowed_start_days=allowed_starts)


def by_id(result):
    return {row.request.proposal_id: row for row in result.lots}


def test_finite_two_lots_due10_and12_do_not_create_avoidable_delay():
    result = schedule([lot("first", 10), lot("second", 12)])
    rows = by_id(result)
    assert (rows["first"].start_day, rows["first"].physical_finish_day) == (5, 8)
    assert (rows["second"].start_day, rows["second"].physical_finish_day) == (9, 12)
    assert all(row.status == "on_time" and row.delay_days == 0 for row in rows.values())
    assert all(math.fsum(qty for _, qty in row.allocations) == 100 for row in rows.values())
    assert max(dict(result.additional_load_by_day).values()) == 25


def test_finite_late_prefix_does_not_advance_distant_future_lot():
    result = schedule([lot("urgent", 2), lot("future", 40)])
    urgent, future = by_id(result)["urgent"], by_id(result)["future"]
    assert (urgent.start_day, urgent.physical_finish_day) == (1, 4)
    assert urgent.request.physical_due_day == urgent.request.requested_available_day == 2
    assert urgent.physical_delay_days == urgent.delay_days == 2
    assert (future.start_day, future.physical_finish_day) == (37, 40)
    assert future.status == "on_time"


def test_finite_equal_due_dates_honor_priority_and_never_interleave():
    first = lot("priority", 10, priority=-1)
    second = lot("ordinary", 10)
    rows = by_id(schedule([second, first]))
    assert (rows["priority"].start_day, rows["priority"].physical_finish_day) == (3, 6)
    assert (rows["ordinary"].start_day, rows["ordinary"].physical_finish_day) == (7, 10)
    assert rows["priority"].request is first and rows["ordinary"].request is second


def test_finite_engaged50_reserves_two_days_before_new_work():
    result = schedule([lot("new", 5)], reserved={1: 25, 2: 25})
    row = result.lots[0]
    assert (row.start_day, row.physical_finish_day) == (3, 6)
    assert row.physical_delay_days == row.delay_days == 1
    loads = dict(result.additional_load_by_day)
    assert loads[1] == loads[2] == 0


def test_finite_future_reservation_does_not_block_earlier_new_lot():
    result = schedule([lot("before_future_firm", 10)], reserved={30: 25})
    row = result.lots[0]
    assert (row.start_day, row.physical_finish_day) == (7, 10)
    assert row.status == "on_time"
    assert dict(result.additional_load_by_day)[30] == 0


def test_finite_closed_days_are_explicit_zero_not_workdays():
    result = schedule([lot("new", 7)], closed=(6, 7))
    row = result.lots[0]
    assert (row.start_day, row.physical_finish_day) == (2, 5)
    assert row.allocations == ((2, 25.), (3, 25.), (4, 25.), (5, 25.))
    assert dict(result.additional_load_by_day)[6] == dict(result.additional_load_by_day)[7] == 0


def test_finite_latest_start_preserves_existing_margin_without_adding_duration():
    result = schedule([lot("margin", 10, latest=3)])
    row = result.lots[0]
    assert (row.start_day, row.physical_finish_day, row.available_day) == (3, 6, 6)
    assert row.start_margin_shortfall_days == 0
    assert len(row.allocations) == 4


def test_finite_availability_uses_max_of_two_calendars_and_reports_delay():
    start = {day: day + 3 for day in range(1, 11)}
    finish = {day: day + 2 for day in range(1, 11)}
    result = schedule([lot("quality", 4, available=4)], end=10,
                      start_calendar=start, finish_calendar=finish)
    row = result.lots[0]
    assert (row.start_day, row.physical_finish_day, row.available_day) == (1, 4, 6)
    assert row.physical_delay_days == 0 and row.delay_days == 2
    assert row.request.requested_available_day == 4


def test_finite_start_calendar_can_dominate_without_becoming_work_duration():
    start = {day: day + 10 for day in range(1, 21)}
    finish = {day: day + 2 for day in range(1, 21)}
    row = schedule([lot("existing_margin", 14, latest=2)], end=20,
        start_calendar=start, finish_calendar=finish).lots[0]
    assert (row.start_day, row.physical_finish_day, row.available_day) == (2, 5, 12)
    assert len(row.allocations) == 4


def test_finite_first_work_day_distinguishes_morning_and_previous_evening():
    capacity = {day: 25 for day in range(6)}
    calendar = {day: day for day in capacity}
    morning = schedule_production_lots([lot("today", 3)], decision_day=0,
        first_work_day=0, capacity_known_day=0, capacity_by_day=capacity,
        reserved_by_day={}, availability_by_start_day=calendar,
        availability_by_finish_day=calendar).lots[0]
    evening = schedule([lot("tomorrow", 3)], first=1, end=5).lots[0]
    assert (morning.start_day, morning.physical_finish_day) == (0, 3)
    assert (evening.start_day, evening.physical_finish_day) == (1, 4)


def test_finite_allowed_starts_do_not_erase_work_on_an_intervening_day():
    # With tau1 and closureJ2, new startsJ1 are forbidden, but workJ1 is valid
    # for a lot already launchedJ0. The scheduler must not close capacityJ1.
    capacity = {0: 25, 1: 25, 2: 0, 3: 25, 4: 25, 5: 25}
    calendar = {day: day for day in capacity}
    row = schedule_production_lots([lot("already_underway", 1, qty=50, latest=0)],
        decision_day=0, first_work_day=0, capacity_known_day=0,
        capacity_by_day=capacity, reserved_by_day={},
        availability_by_start_day=calendar, availability_by_finish_day=calendar,
        allowed_start_days={0, 3, 4, 5}).lots[0]
    assert row.allocations == ((0, 25.), (1, 25.))
    assert (row.start_day, row.physical_finish_day) == (0, 1)


def test_finite_forbidden_new_start_preserves_unused_known_capacity():
    result = schedule([lot("new", 1, qty=25)], end=6, closed=(2,),
                      allowed_starts={3, 4, 5, 6})
    row = result.lots[0]
    assert (row.start_day, row.physical_finish_day) == (3, 3)
    assert row.physical_delay_days == 2
    assert dict(result.remaining_capacity_by_day)[1] == 25


def test_finite_backward_placement_uses_latest_permitted_start():
    row = schedule([lot("new", 10)], end=12, allowed_starts={1, 5}).lots[0]
    assert (row.start_day, row.physical_finish_day) == (5, 8)


def test_finite_negative_requested_dates_are_preserved_as_overdue():
    request = lot("overdue", -1, available=0, latest=-3)
    row = schedule([request]).lots[0]
    assert row.request is request
    assert (row.start_day, row.physical_finish_day, row.available_day) == (1, 4, 4)
    assert row.physical_delay_days == 5 and row.delay_days == 4
    assert row.start_margin_shortfall_days == 4


def test_finite_no_permitted_start_is_explicitly_unplaced():
    result = schedule([lot("new", 10)], allowed_starts=set())
    assert result.unscheduled_lot_ids == ("new",)
    assert result.lots[0].start_day is None
    assert not any(qty for _, qty in result.additional_load_by_day)


@pytest.mark.parametrize("intraday,expected", [
    (False, [(1, 1), (2, 2)]),
    (True, [(2, 2), (2, 2)]),
])
def test_finite_same_day_sharing_requires_intraday(intraday, expected):
    result = schedule([lot("a", 2, qty=50), lot("b", 2, qty=50)],
                      first=1, end=3, daily=100, intraday=intraday)
    assert [(row.start_day, row.physical_finish_day) for row in result.lots] == expected
    assert max(dict(result.additional_load_by_day).values()) <= 100


def test_finite_engaged_partial_day_shared_only_when_intraday():
    args = dict(first=1, end=3, daily=100, reserved={1: 50})
    no_share = schedule([lot("new", 1, qty=50)], **args).lots[0]
    share = schedule([lot("new", 1, qty=50)], intraday=True, **args).lots[0]
    assert no_share.start_day == no_share.physical_finish_day == 2
    assert share.start_day == share.physical_finish_day == 1


def test_finite_shared_day_latest_start_keeps_earliest_feasibility_witness():
    requests = [lot("a", 2, qty=50, latest=1), lot("b", 2, qty=100, latest=1)]
    result = schedule(requests, first=1, end=3, daily=100, intraday=True)
    first, second = result.lots
    assert first.allocations == ((1, 50.),)
    assert second.allocations == ((1, 50.), (2, 50.))
    assert second.start_margin_shortfall_days == 0


def test_finite_short_horizon_preserves_unplaced_lot_without_invented_zero_future():
    requests = [lot("a", 10), lot("b", 12)]
    result = schedule(requests, end=5)
    assert result.unscheduled_lot_ids == ("b",)
    unplaced = result.lots[1]
    assert unplaced.request is requests[1]
    assert unplaced.status == "beyond_known_capacity_horizon"
    assert unplaced.allocations == ()
    assert unplaced.start_day is unplaced.physical_finish_day is unplaced.available_day is None
    assert unplaced.delay_days is None
    assert math.fsum(dict(result.additional_load_by_day).values()) == 100


def test_finite_fractional_work_units_and_input_purity():
    requests = [lot("grams", 3, qty=1.5)]
    capacity = {1: .5, 2: .5, 3: .5}
    reserved = {}
    calendar = {1: 1, 2: 2, 3: 3}
    before = deepcopy((requests, capacity, reserved, calendar))
    result = schedule_production_lots(requests, decision_day=0, first_work_day=1,
        capacity_known_day=0, capacity_by_day=capacity, reserved_by_day=reserved,
        availability_by_start_day=calendar, availability_by_finish_day=calendar)
    assert result.lots[0].allocations == ((1, .5), (2, .5), (3, .5))
    assert (requests, capacity, reserved, calendar) == before


@pytest.mark.parametrize("field,value", [
    ("capacity_known_day", 1), ("first_work_day", 0),
    ("capacity_by_day", {1: 25, 3: 25}),
    ("capacity_by_day", {1: 25, 2: math.inf, 3: 25}),
    ("capacity_by_day", {1: 25, 2: -1, 3: 25}),
    ("reserved_by_day", {1: 26}), ("reserved_by_day", {4: 1}),
    ("availability_by_finish_day", {1: 1, 3: 3}),
    ("availability_by_start_day", {1: 2, 2: 2, 3: 1}),
    ("allow_intraday", 1),
    ("allowed_start_days", {0}), ("allowed_start_days", {True}),
])
def test_finite_refuses_unknown_or_noncausal_calendars(field, value):
    args = dict(decision_day=0, first_work_day=1, capacity_known_day=0,
        capacity_by_day={1: 25, 2: 25, 3: 25}, reserved_by_day={},
        availability_by_start_day={1: 1, 2: 2, 3: 3},
        availability_by_finish_day={1: 1, 2: 2, 3: 3}, allow_intraday=False)
    args[field] = value
    with pytest.raises(ValueError):
        schedule_production_lots([lot("new", 3)], **args)


@pytest.mark.parametrize("requests", [
    [lot("same", 3), lot("same", 4)], [lot("bad", 3, qty=0)],
    [lot("bad", 3, qty=-1)], [lot("bad", 3, qty=math.nan)],
    [lot("bad", 3, qty=True)], [lot("bad", 3, priority=True)],
])
def test_finite_refuses_invalid_lot_contract(requests):
    with pytest.raises(ValueError):
        schedule(requests)
