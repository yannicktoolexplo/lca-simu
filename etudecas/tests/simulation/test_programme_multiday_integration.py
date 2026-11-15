"""Memory-only counterfactuals, with manually calculated work and receipt dates."""
from copy import deepcopy
import json

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import LotSizing, OrderProposal, Requirement


def context(*, current=25, closed=(), quality=0):
    return dict(capacity_qty=25, known_day=4, first_work_day=5,
        current_capacity_qty=current, closed_days=closed, active_remaining_qty=0,
        opening_work=(), intraday=True,
        supply_calendar=dict(physical_lead_days=3, receipt_days=quality,
            origin_date="2025-01-01", closed_days=closed))


def proposals():
    return [OrderProposal("future", 20, 23, 23, 100)]


def test_multiday_physical_work_and_quality_are_separate_from_tau():
    inputs = context(quality=2); saved = deepcopy(inputs)
    placement = engine.programme_multiday_placements(proposals(), decision_day=5, context=inputs)["future"]
    assert placement["allocations"] == [(5,25),(6,25),(7,25),(8,25)]
    assert placement["physical_finish_day"] == 8  # Thursday 9 January.
    assert placement["available_day"] == 12  # Monday 13 January, two working control days.
    assert inputs == saved


def test_multiday_closed_day_and_partial_current_capacity():
    placement = engine.programme_multiday_placements(proposals(), decision_day=5,
        context=context(current=10, closed=(9,)))["future"]
    assert placement["allocations"] == [(5,10),(6,25),(7,25),(8,25),(10,15)]
    assert placement["physical_finish_day"] == 10


def test_multiday_preserves_existing_start_calendar_closure_guard():
    # Existing calendar forbids a new start if its tau planning interval crosses
    # a closure. This experiment does not change that separate convention.
    assert engine.programme_multiday_placements(proposals(), decision_day=5,
        context=context(closed=(6,))) == {}


@pytest.mark.parametrize("change", [dict(current_capacity_qty=0), dict(active_remaining_qty=1),
    dict(opening_work=(("initial",8,100),)), dict(closed_days=(5,))])
def test_multiday_does_not_promote_on_occupied_or_unavailable_machine(change):
    inputs = context(); inputs.update(change)
    assert engine.programme_multiday_placements(proposals(), decision_day=5, context=inputs) == {}


@pytest.mark.parametrize("change", [dict(known_day=6), dict(first_work_day=6),
    dict(capacity_qty=25.5), dict(intraday=False)])
def test_multiday_rejects_unknown_or_incompatible_capacity(change):
    inputs = context(); inputs.update(change)
    with pytest.raises(ValueError):
        engine.programme_multiday_placements(proposals(), decision_day=5, context=inputs)


def test_multiday_replacement_credits_once_and_reserves_full_remaining_work():
    capacity = context()
    inputs = dict(decision_day=5, snapshot_day=4, available_qty=0,
        requirements=[Requirement("first",12,100),Requirement("second",20,100)],
        firm_receipts=[], lead_days=3, lot_sizing=LotSizing(minimum=100,multiple=100,maximum=100,integer=True),
        manufacturing_capacity=capacity)
    _, original = engine.dated_production_release(**inputs)
    candidate = dict(programme_id="source-known", qty=100, available_day=8,
        work_allocations=[(5,25),(6,25),(7,25),(8,25)])
    saved = deepcopy(inputs)
    proof = engine.programme_replacement_check(candidate, original, **inputs)
    assert proof["status"] == "advanced_existing_lot"
    assert proof["before_proposed_qty"] == proof["after_with_programme_qty"] == 200
    assert sum(p["qty"] for p in proof["remaining_proposals"]) == 100
    audit = proof["counterfactual_capacity_plan"]
    assert len(audit) == 1
    assert json.loads(audit[0]["reserved_allocations_json"]) == {"5":25,"6":25,"7":25,"8":25}
    assert all(day >= 9 for day,qty in json.loads(audit[0]["allocations_json"]))
    assert inputs == saved
