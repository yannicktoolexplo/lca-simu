"""Finite-capacity MRP integration, independent numbers and memory-only state."""
from copy import deepcopy
import json
import math

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, plan_dated_requirements,
)


PF = ("factory", "PF")
RM = ("factory", "RM")
LOTS = LotSizing(minimum=100, multiple=100, maximum=100, integer=True)


def context(*, decision=0, first=1, active=0, opening=(), quality=0, closed=()):
    return dict(capacity_qty=25, known_day=decision, first_work_day=first,
        closed_days=closed, active_remaining_qty=active, opening_work=opening,
        supply_calendar=dict(physical_lead_days=1, receipt_days=quality,
            origin_date="2025-01-01", closed_days=closed), intraday=True)


def base_plan(needs, *, decision=0, stock=0, firm=(), lead=1):
    return plan_dated_requirements(decision_day=decision, available_qty=stock,
        requirements=needs, firm_receipts=firm, lead_days=lead, lot_sizing=LOTS)


def network_args(*, needs, decision=0, campaigns=None, stock=0, firm=(), lead=1):
    return dict(decision_day=decision, requirements_by_pair={PF: needs},
        available_by_pair={PF: stock, RM: 1000}, firm_receipts_by_pair={PF: firm},
        transport_sources_by_pair={}, bom_by_pair={PF: [(RM, 2)]},
        lead_days_by_pair={PF: lead, RM: 1}, lot_sizing_by_pair={PF: LOTS},
        reserve_targets_by_pair={}, coverage_days_by_pair={},
        active_campaigns_by_pair=campaigns or {})


def identities(plan):
    return {row.proposal_id: (row.qty, row.requested_day) for row in plan.proposals}


def test_finite_integration_single_lot_start5_finish8_preserves_original_plan():
    needs = [Requirement("customer", 8, 100)]
    original = base_plan(needs)
    original_copy, needs_copy = deepcopy(original), deepcopy(needs)
    scheduled, audit = engine.finite_manufacturing_plan(original, requirements=needs,
        firm_receipts=(), context=context())
    assert identities(scheduled) == identities(original)
    assert scheduled.proposals[0].release_day == 5
    assert scheduled.proposals[0].available_day == 8
    assert audit[0]["planned_start_day"] == 5
    assert audit[0]["physical_finish_day"] == 8
    assert audit[0]["work_days"] == 4 and audit[0]["qty"] == 100
    assert json.loads(audit[0]["allocations_json"]) == [[5, 25], [6, 25], [7, 25], [8, 25]]
    assert original == original_copy and needs == needs_copy


def test_finite_integration_bridge_refuses_disabled_intraday_continuation():
    needs = [Requirement("customer", 8, 100)]
    original = base_plan(needs)
    capacity_context = context()
    capacity_context["intraday"] = False
    with pytest.raises(ValueError, match="intraday"):
        engine.finite_manufacturing_plan(original, requirements=needs,
            firm_receipts=(), context=capacity_context)


def test_finite_integration_two_lots_due10_and12_reserve_one_shared_resource():
    needs = [Requirement("earlier", 10, 100), Requirement("later", 12, 100)]
    original = base_plan(needs)
    scheduled, audit = engine.finite_manufacturing_plan(original, requirements=needs,
        firm_receipts=(), context=context())
    assert identities(scheduled) == identities(original)
    rows = sorted(audit, key=lambda row: row["requested_day"])
    assert [(r["planned_start_day"], r["physical_finish_day"]) for r in rows] == [(5, 8), (9, 12)]
    loads = {}
    for row in rows:
        for day, quantity in json.loads(row["allocations_json"]):
            loads[day] = loads.get(day, 0) + quantity
    assert max(loads.values()) == 25
    assert math.fsum(loads.values()) == 200
    assert scheduled.late_qty == 0


@pytest.mark.parametrize("source", ["stock", "firm"])
@pytest.mark.parametrize("required", [100, 200])
def test_finite_integration_existing100_netted_exactly_once(source, required):
    needs = [Requirement("customer", 8, required)]
    stock = 100 if source == "stock" else 0
    firm = () if source == "stock" else (FirmReceipt("already_committed", 8, 100, "confirmed"),)
    original = base_plan(needs, stock=stock, firm=firm)
    before = deepcopy(firm)
    scheduled, audit = engine.finite_manufacturing_plan(original, requirements=needs,
        firm_receipts=firm, context=context())
    assert identities(scheduled) == identities(original)
    assert scheduled.proposed_qty == required - 100
    assert math.fsum(a.qty for a in scheduled.commitment_allocations) == 100
    assert math.fsum(a.qty for a in scheduled.allocations) == required
    assert firm == before
    if required == 100:
        assert scheduled is original and audit == []
    else:
        assert len(scheduled.proposals) == 1 and audit[0]["qty"] == 100


def test_finite_integration_campaign_reserves_remaining50_not_executed_WIP50():
    needs = [Requirement("customer", 6, 200)]
    args = network_args(needs=needs, campaigns={PF: ("active", 50, 50, 2)})
    before = deepcopy(args)
    plans, requirements, audit = engine.plan_component_network(**args,
        manufacturing_capacity_by_pair={PF: context(active=50)})
    assert args == before
    assert plans[PF].proposed_qty == 100
    firm = audit[PF]["firm_receipts"]
    assert [(r.receipt_id, r.qty, r.available_day) for r in firm] == [("campaign:active", 100, 2)]
    capacity = audit[PF]["finite_capacity_plan"][0]
    assert capacity["reserved_work_qty"] == 50
    assert capacity["first_work_day"] == capacity["planned_start_day"] == 3
    assert capacity["physical_finish_day"] == 6
    assert math.fsum(r.qty for r in requirements[RM] if r.requirement_id.startswith("campaign:")) == 100
    assert math.fsum(r.qty for r in requirements[RM] if r.requirement_id.startswith("derived:")) == 200
    assert math.fsum(r.qty for r in requirements[RM]) == 300


def test_finite_integration_future_opening_order_does_not_block_due10():
    needs = [Requirement("customer", 10, 100)]
    original = base_plan(needs)
    scheduled, audit = engine.finite_manufacturing_plan(original, requirements=needs,
        firm_receipts=(), context=context(opening=(("OF", 30, 50),)))
    assert scheduled.proposals[0].release_day == 7
    assert audit[0]["physical_finish_day"] == 10
    assert audit[0]["reserved_work_qty"] == 50
    assert audit[0]["first_work_day"] == 1
    assert scheduled.late_qty == 0


def test_finite_integration_quality_two_weekdays_is_applied_once():
    # Jan1,2025 is Wednesday: J8=Thursday Jan9, J9=Friday, J12=Monday.
    # Four workdays J5..J8 finish the lot; two quality weekdays are J9 and J12.
    needs = [Requirement("customer", 12, 100)]
    original = base_plan(needs)
    scheduled, audit = engine.finite_manufacturing_plan(original, requirements=needs,
        firm_receipts=(), context=context(quality=2))
    row = audit[0]
    assert (row["planned_start_day"], row["physical_finish_day"], row["available_day"]) == (5, 8, 12)
    assert row["work_days"] == 4
    assert scheduled.proposals[0].available_day == 12
    assert scheduled.late_qty == 0


def test_finite_integration_evening_plan_and_morning_release_agree():
    needs = (Requirement("customer", 8, 100),)
    evening = base_plan(needs, decision=4)
    evening, evening_audit = engine.finite_manufacturing_plan(evening, requirements=needs,
        firm_receipts=(), context=context(decision=4, first=5))
    assert evening.proposals[0].release_day == 5
    assert evening_audit[0]["physical_finish_day"] == 8
    rows = []
    wanted, morning = engine.dated_production_release(decision_day=5, snapshot_day=4,
        requirements=needs, available_qty=0, firm_receipts=(), lead_days=1,
        lot_sizing=LOTS, manufacturing_capacity=context(decision=5, first=5), capacity_audit=rows)
    assert wanted == 100
    assert morning.proposals[0].release_day == 5
    assert rows[0]["physical_finish_day"] == 8
    earlier_wanted, earlier = engine.dated_production_release(decision_day=4, snapshot_day=3,
        requirements=needs, available_qty=0, firm_receipts=(), lead_days=1,
        lot_sizing=LOTS, manufacturing_capacity=context(decision=4, first=4))
    assert earlier_wanted == 0
    assert earlier.proposals[0].release_day == 5


def test_finite_integration_network_explodes_BOM200_at_advanced_release5():
    args = network_args(needs=[Requirement("customer", 8, 100)])
    before = deepcopy(args)
    legacy, legacy_needs, _ = engine.plan_component_network(**args)
    plans, requirements, audit = engine.plan_component_network(**args,
        manufacturing_capacity_by_pair={PF: context()})
    assert args == before
    assert identities(plans[PF]) == identities(legacy[PF])
    assert [(r.qty, r.due_day) for r in legacy_needs[RM]] == [(200, 7)]
    assert [(r.qty, r.due_day) for r in requirements[RM]] == [(200, 5)]
    assert plans[PF].proposals[0].release_day == 5
    assert plans[RM].proposed_qty == 0  # Initial1000RM covers200; no duplicate buy.
    assert audit[PF]["finite_capacity_plan"][0]["qty"] == 100


def test_finite_integration_default_none_preserves_legacy_42day_prototype():
    needs = [Requirement("prototype42", 43, 100)]
    args = dict(decision_day=1, snapshot_day=0, requirements=needs, available_qty=0,
                firm_receipts=(), lead_days=42, lot_sizing=LOTS)
    legacy = engine.dated_production_release(**args)
    explicit = engine.dated_production_release(**args, manufacturing_capacity=None)
    assert explicit == legacy
    assert legacy[0] == 100
    assert (legacy[1].proposals[0].release_day, legacy[1].proposals[0].available_day) == (1, 43)
    args = network_args(needs=needs, decision=1, lead=42)
    network = engine.plan_component_network(**args)
    assert engine.plan_component_network(**args, manufacturing_capacity_by_pair=None) == network
    assert (network[0][PF].proposals[0].release_day, network[0][PF].proposals[0].available_day) == (1, 43)
