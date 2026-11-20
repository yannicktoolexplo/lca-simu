"""Small independent work and genealogy examples, with no file fixtures."""

import math
import sys

import pytest

from etudecas.simulation.engine.engaged_lot_work import EngagedLotWork
from etudecas.simulation.engine.run_first_simulation import (
    engaged_production_available_day,
    incremental_component_issue,
    manufacturing_day_capacity,
    parse_args,
    production_completion_quantities,
)
from etudecas.simulation.lot_trace.campaigns import ProductionBatchWip


def test_integer_lot_resumes_without_releasing_partial_output():
    work = EngagedLotWork.parse("lot-1,4")
    batch = ProductionBatchWip("campaign", "batch", "factory", "PF", 2, 2, 11)
    closed = {3, 4, 5}  # Saturday, Sunday, declared Monday closure.
    issued = 0
    work_by_day, output_by_day, credit_by_day = [], [], {}
    for day in range(2, 10):
        daily_work = work.daily_work(target=batch.target_qty, executed=batch.executed_qty)
        cap = manufacturing_day_capacity(math.inf, day=day, closed_days=closed)
        done = min(daily_work, cap, 1 if day == 6 else math.inf)
        if done > 0:
            issue = incremental_component_issue(batch.executed_qty, done, 0.5, "UN", issued)
            issued += issue
            batch.add_execution(done, [{"lot_id": f"pack-{day}", "qty": issue}])
        output = production_completion_quantities(batch.target_qty if batch.is_complete else 0)
        work_by_day.append(done)
        output_by_day.append(output["released_qty"])
        if not batch.is_complete:
            credit_by_day[day] = engaged_production_available_day(decision_day=day,
                remaining_work_days=work.remaining_days(target=batch.target_qty, executed=batch.executed_qty),
                closed_days=closed)

    # Cumulative work boundaries of 2, 5, 8 and 11 units. The interrupted second
    # tranche resumes on the next open day and shifts completion by one day.
    assert work_by_day == [2, 0, 0, 0, 1, 2, 3, 3]
    assert output_by_day == [0, 0, 0, 0, 0, 0, 0, 11]
    assert credit_by_day == {2: 8, 3: 8, 4: 8, 5: 8, 6: 9, 7: 9, 8: 9}
    assert issued == 6  # Ceiling of 11 × 1/2, rounded once for the batch.
    assert [(row["lot_id"], row["qty"]) for row in batch.parent_allocations] == [
        ("pack-2", 1), ("pack-6", 1), ("pack-7", 1), ("pack-8", 1), ("pack-9", 2),
    ]


def test_only_due_overlap_on_the_selected_pair_is_refused():
    work = EngagedLotWork("lot-1", 10)
    first = dict(node_id="factory", item_id="PF", order_id="lot-1", state="active", planned_release_day=3)
    second = dict(first, order_id="lot-2", state="frozen", planned_release_day=8)
    third = dict(second, order_id="lot-3", item_id="another PF", planned_release_day=5)
    work.check_overlap(orders=[first, second, third], pair=("factory", "PF"), day=7, current_order_id="lot-1")
    work.check_overlap(orders=[second, third], pair=("factory", "PF"), day=8, current_order_id="lot-4")
    with pytest.raises(ValueError, match="lot-1 and lot-2"):
        work.check_overlap(orders=[first, second, third], pair=("factory", "PF"), day=8, current_order_id="lot-1")
    with pytest.raises(ValueError, match="lot-2 and lot-1"):
        work.check_overlap(orders=[dict(first, state="frozen")], pair=("factory", "PF"), day=8, current_order_id="lot-2")


def test_option_is_off_by_default_and_requires_a_whole_batch(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_first_simulation"])
    assert parse_args().engaged_lot_work_days == []
    for invalid in ("lot-1", ",10", "lot-1,0", "lot-1,2.5", "lot-1,366"):
        with pytest.raises(ValueError):
            EngagedLotWork.parse(invalid)
    work = EngagedLotWork.parse("lot-1,10")
    for target, executed in ((10.5, 0), (11, 2.5), (9, 0), (11, 11)):
        with pytest.raises(ValueError):
            work.daily_work(target=target, executed=executed)
    one_day = EngagedLotWork.parse("lot-1,1")
    assert one_day.daily_work(target=11, executed=0) == 11
