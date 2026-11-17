"""Calendar oracles using only in-memory inputs and calculations."""
import pytest

from etudecas.simulation.engine.manufacturing_work_calendar import resolve_manufacturing_work_calendar
from etudecas.simulation.engine.run_first_simulation import (
    dated_supply_release_calendar, calendarize_manufacturing_plan,
    finite_manufacturing_plan, manufacturing_day_capacity, manufacturing_work_finish,
    extend_known_supply_calendar,
)
from etudecas.simulation.engine.mrp_planning import Requirement, LotSizing, plan_dated_requirements


def workdays():
    return {"schema_version": 1, "rows": [{"node_id": "M", "working_weekdays": [0, 1, 2, 3, 4],
            "known_day": 0, "provenance": "Declared test hypothesis"}]}


def closed_days(payload=None, through=50):
    return resolve_manufacturing_work_calendar(workdays() if payload is None else payload,
        nodes=[{"id": "M", "type": "factory"}], produced_pairs={("M", "PF")},
        origin_date="2025-01-01", through_day=through)[("M", "PF")]


def test_weekday_calendar_covers_future_projection_and_does_not_guess_missing_sites():
    days = closed_days(through=4000)
    assert {3, 4, 10, 11, 367, 368}.issubset(days)
    assert 2 not in days and 5 not in days and 369 not in days
    assert 4000 in days  # Saturday 4000 days after Wednesday.
    assert resolve_manufacturing_work_calendar(None, nodes=[], produced_pairs=set(),
        origin_date="2025-01-01", through_day=4000) == {}


def test_work_calendar_refuses_unknown_capacity_calendar_and_empty_workweek():
    for change in ({"known_day": 1}, {"working_weekdays": []}, {"working_weekdays": [True]},
                   {"working_weekdays": [0, 0]}, {"provenance": ""}, {"node_id": "absent"}):
        payload = workdays()
        payload["rows"][0].update(change)
        with pytest.raises(ValueError):
            closed_days(payload)


def test_friday_launch_spans_weekend_without_work_or_extra_tau_duration():
    closed = closed_days(through=800)
    calendar = dict(physical_lead_days=3, receipt_days=0, origin_date="2025-01-01",
                    closed_days=closed, planning_interval_closed_days=frozenset())
    starts = dict(dated_supply_release_calendar(decision_day=2, through_day=9, **calendar))
    assert starts[2] == 5 and 3 not in starts and 4 not in starts
    requirements = (Requirement("need", 7, 100),)
    plan = plan_dated_requirements(decision_day=0, available_qty=0, requirements=requirements,
        firm_receipts=(), lead_days=3, lot_sizing=LotSizing(integer=True))
    plan = calendarize_manufacturing_plan(plan, requirements=requirements, firm_receipts=(),
        closed_days=closed, planning_interval_closed_days=frozenset(), process_days=3)
    placed, audit = finite_manufacturing_plan(plan, requirements=requirements, firm_receipts=(),
        context=dict(capacity_qty=25, known_day=0, first_work_day=2, closed_days=closed,
                     supply_calendar=calendar, intraday=True))
    row = placed.proposals[0]
    assert (row.release_day, row.available_day, row.qty) == (2, 7, 100)
    assert audit[0]["physical_finish_day"] == 7
    assert manufacturing_work_finish(1, 4, closed) == 7
    assert [manufacturing_day_capacity(25, day=d, closed_days=closed) for d in range(2, 8)] == [25, 0, 0, 25, 25, 25]


def test_historical_shutdown_interval_keeps_its_original_rule_with_weekly_workdays():
    weekly = closed_days(through=60)
    shutdown = frozenset({5})
    combined = weekly | shutdown
    starts = dict(dated_supply_release_calendar(decision_day=2, through_day=10,
        physical_lead_days=3, closed_days=combined, planning_interval_closed_days=shutdown))
    assert 2 not in starts  # Its unchanged planning allowance crosses the shutdown J5.
    assert starts[6] == 9


def test_weekday_calendar_extension_keeps_long_tau_without_requiring_contiguous_workdays():
    context = dict(physical_lead_days=7, closed_days=closed_days(through=4000),
                   planning_interval_closed_days=frozenset(), origin_date="2025-01-01")
    prefix = dated_supply_release_calendar(decision_day=0, through_day=9, **context)
    extended, trace = extend_known_supply_calendar(prefix, decision_day=0, through_day=367,
                                                    context=context)
    assert extended[:len(prefix)] == prefix
    assert extended[-1] == (369, 376)  # First Monday after the requested Saturday.
    assert trace["existing_prefix_preserved"]
