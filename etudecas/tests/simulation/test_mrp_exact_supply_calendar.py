"""Memory-only dated-calendar oracles; no files, simulation or time mutation."""
import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, StockProtection,
    plan_dated_requirements, plan_with_stock_protection,
)
from etudecas.simulation.engine.run_first_simulation import (
    dated_supply_release_calendar, dated_production_release,
    plan_component_network, calendarize_manufacturing_plan,
)


def test_future_receipt_weekday_is_computed_from_each_release_and_legacy_is_unchanged():
    # Origin Wednesday Jan1: Thu Jan2 arrival -> Fri Jan3 usable.
    # A Friday Jan3 dispatch arrives Saturday, usable Monday Jan6, too late
    # for Sunday's need. A frozen two-day lead incorrectly promises Sunday.
    calendar = dated_supply_release_calendar(decision_day=0, through_day=10,
        physical_lead_days=1, receipt_days=1)
    args = dict(decision_day=0, available_qty=0, requirements=[Requirement("need", 4, 10)],
                firm_receipts=[], lead_days=2, lot_sizing=LotSizing(integer=True))
    legacy = plan_dated_requirements(**args)
    exact = plan_dated_requirements(**args, availability_by_release=calendar)
    assert [(r.release_day, r.available_day, r.qty) for r in legacy.proposals] == [(2, 4, 10)]
    assert [(r.release_day, r.available_day, r.qty) for r in exact.proposals] == [(0, 2, 10)]
    assert plan_dated_requirements(**args, availability_by_release=None) == legacy


def test_weekly_dispatch_uses_previous_slot_and_exposes_late_next_slot():
    # Wednesday Jan8 +10calendar => Sat Jan18; six MF days => Mon Jan27.
    calendar = dated_supply_release_calendar(decision_day=4, through_day=35,
        physical_lead_days=10, receipt_days=6, review_days=7)
    assert calendar[:2] == ((7, 26), (14, 33))
    args = dict(decision_day=4, available_qty=0, firm_receipts=[], lead_days=18,
                lot_sizing=LotSizing(integer=True), availability_by_release=calendar)
    on_time = plan_dated_requirements(**args, requirements=[Requirement("future", 27, 10)])
    assert [(r.release_day, r.available_day) for r in on_time.proposals] == [(7, 26)]
    late = plan_dated_requirements(**args, requirements=[Requirement("near", 20, 10)])
    assert [(r.release_day, r.available_day) for r in late.proposals] == [(7, 26)]
    assert late.late_qty == 10 and late.late_qty_days == 60


def test_exact_calendar_nets_held_transit_and_reuses_lot_surplus_once():
    calendar = ((7, 16), (14, 23), (21, 30), (28, 37))
    plan = plan_dated_requirements(decision_day=4, available_qty=5,
        requirements=[Requirement("first", 17, 80), Requirement("second", 24, 10)],
        firm_receipts=[FirmReceipt("held", 16, 20, "held"), FirmReceipt("transit", 25, 10, "in_transit")],
        lead_days=9, lot_sizing=LotSizing(multiple=60, integer=True), availability_by_release=calendar)
    # 90 -5 -20 -10 =55, one60 lot, surplus5. Late real10 are retained.
    assert [(r.release_day, r.available_day, r.qty) for r in plan.proposals] == [(7, 16, 60)]
    assert plan.closing_projected_qty == 5 and plan.unallocated_firm_qty == 5
    assert sum(a.qty for a in plan.commitment_allocations if a.supply_id == "held") == 20
    assert sum(a.qty for a in plan.commitment_allocations if a.supply_id == "transit") == 10
    # Once the earlier lot is proposed, FIFO dates allocate only5 of the late
    # transit receipt; its other5 remain. Pre-net commitments still credit10.
    assert sum(a.qty for a in plan.allocations if a.supply_id == "transit") == 5
    assert plan.firm_late_qty == 5 and plan.late_qty_days == 5


def test_calendar_intersects_pair_and_lane_review_grids():
    # Pair review every4days AND lane review every6days, both anchored J0.
    # The first common slot after decisionJ1 is J12, not J6.
    calendar = dated_supply_release_calendar(decision_day=1, through_day=30,
        physical_lead_days=2, review_days=6, pair_review_days=4)
    assert calendar == ((12, 14), (24, 26), (36, 38))
    plan = plan_dated_requirements(decision_day=1, available_qty=0,
        requirements=[Requirement("need", 13, 10)], firm_receipts=[], lead_days=2,
        lot_sizing=LotSizing(integer=True), availability_by_release=calendar)
    assert [(r.release_day, r.available_day, r.qty) for r in plan.proposals] == [(12, 14, 10)]
    assert plan.late_qty == 10 and plan.late_qty_days == 10


def test_exact_calendar_preserves_physical_UN_invariants():
    with pytest.raises(ValueError, match="Physical UN available"):
        plan_dated_requirements(decision_day=0, available_qty=0.5, requirements=[], firm_receipts=[],
            lead_days=1, lot_sizing=LotSizing(integer=True), availability_by_release=((0, 1),))


@pytest.mark.parametrize("calendar", [(), ((-1, 0),), ((0, 3), (0, 4)),
    ((0, 5), (1, 4)), ((0, -1),), ((0, 1), (1, 2))])
def test_exact_calendar_rejects_empty_noncausal_nonmonotone_or_truncated_tables(calendar):
    with pytest.raises(ValueError, match="calendar"):
        plan_dated_requirements(decision_day=0, available_qty=0, requirements=[Requirement("need", 3, 1)],
            firm_receipts=[], lead_days=1, availability_by_release=calendar)


def test_calendar_stock_floor_is_not_a_second_consumption_or_order():
    protected = plan_with_stock_protection(decision_day=4, available_qty=5,
        requirements=[Requirement("physical", 17, 10)], firm_receipts=[FirmReceipt("held", 16, 8, "held")],
        lead_days=9, lot_sizing=LotSizing(multiple=5, integer=True),
        protection=[StockProtection("source", 17, 20)],
        availability_by_release=((7, 16), (14, 23), (21, 30)))
    # Physical10 + persistentfloor20 - available5 - firm8 =17 =>20.
    assert protected.plan.proposed_qty == 20 and protected.plan.closing_projected_qty == 23
    assert sum(b.requirement_qty for b in protected.plan.balances) == 10
    assert all(b.shortfall_qty == 0 for b in protected.protection if b.day >= 17)


def test_calendar_closure_advances_start_or_reports_delay_and_keeps_quality_open():
    # Existing tau3 must fit outside closed days7..10; release3 completes6,
    # two MF receipt days from Tue Jan7 => Thu Jan9(day8), during closure.
    context = dict(physical_lead_days=3, receipt_days=2, closed_days=frozenset(range(7, 11)))
    calendar = dated_supply_release_calendar(decision_day=0, through_day=20, **context)
    requirements = [Requirement("need", 10, 10)]
    plan = plan_dated_requirements(decision_day=0, available_qty=0, requirements=requirements,
        firm_receipts=[], lead_days=5, availability_by_release=calendar)
    assert [(r.release_day, r.available_day) for r in plan.proposals] == [(3, 8)]
    assert calendarize_manufacturing_plan(plan, requirements=requirements, firm_receipts=[],
        closed_days=context["closed_days"], process_days=3, receipt_days=2) == plan
    late = plan_dated_requirements(decision_day=5, available_qty=0, requirements=requirements,
        firm_receipts=[], lead_days=5, availability_by_release=dated_supply_release_calendar(
            decision_day=5, through_day=20, **context))
    assert [(r.release_day, r.available_day) for r in late.proposals] == [(11, 16)]
    assert late.late_qty_days == 60


def test_calendar_network_propagates_aligned_transfer_before_BOM_once():
    customer, output, component = ("dest", "PF"), ("factory", "PF"), ("factory", "MP")
    plans, needs, audits = plan_component_network(decision_day=4,
        requirements_by_pair={customer: [Requirement("need", 17, 100)]},
        available_by_pair={}, firm_receipts_by_pair={},
        transport_sources_by_pair={customer: [(output, 1)]}, bom_by_pair={output: [(component, 2)]},
        lead_days_by_pair={customer: 9, output: 3, component: 1},
        lot_sizing_by_pair={customer: LotSizing(multiple=60), output: LotSizing(multiple=60)},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        availability_by_release_by_pair={customer: ((7, 16), (14, 23), (21, 30))})
    assert [(r.release_day, r.available_day, r.qty) for r in plans[customer].proposals] == [(7, 16, 120)]
    assert [(r.due_day, r.qty) for r in needs[output]] == [(7, 120)]
    assert [(r.due_day, r.qty) for r in needs[component]] == [(4, 240)]


def test_calendar_next_day_revalidation_does_not_relaunch_received_output():
    kwargs = dict(decision_day=4, snapshot_day=3, requirements=[Requirement("need", 8, 10)],
        lead_days=5, lot_sizing=LotSizing(integer=True),
        availability_by_release=dated_supply_release_calendar(decision_day=4, through_day=10,
            physical_lead_days=3, receipt_days=2))
    due, plan = dated_production_release(**kwargs, available_qty=10,
        firm_receipts=[FirmReceipt("arrived", 4, 10)])
    assert due == 0 and plan.proposals == ()
    due, plan = dated_production_release(**kwargs, available_qty=0, firm_receipts=[])
    assert due == 10 and plan.proposals[0].release_day == 4
