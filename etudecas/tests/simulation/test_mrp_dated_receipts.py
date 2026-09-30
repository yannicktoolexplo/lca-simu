"""Independent, in-memory examples for the opt-in dated-receipt policy.

These checks validate a bounded coverage rule, not an ERP algorithm or the
absence of shortages before the end of a coverage window. No file fixtures.
"""
from __future__ import annotations

import math
import json
from copy import deepcopy
from decimal import Decimal

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import (
    ExternalComponentDemandCalendar, FirmReceipt, LotSizing, Requirement,
    plan_dated_requirements, serve_external_component_requirements,
)


PAIR = ("M-1", "item:1")


def test_dated_receipts_late_order_does_not_cover_near_need():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 12, 30)
    calendar.add(PAIR, 40, 90)

    # End-of-day 10: 20 on hand, target 100, only 30 arrives by day 16.
    eligible = calendar.quantity(PAIR, decision_day=10, through_day=16)
    assert eligible == 30
    assert max(0, 100 - 20 - eligible) == 50
    assert max(0, 100 - 20 - calendar.total(PAIR)) == 0
    assert calendar.total(PAIR) == 120


def test_dated_receipts_both_window_limits_are_inclusive():
    calendar = engine.DatedReceiptCalendar()
    for day, quantity in [(9, 2), (10, 3), (16, 5), (17, 7)]:
        calendar.add(PAIR, day, quantity)
    assert calendar.quantity(PAIR, decision_day=10, through_day=16) == 8
    assert calendar.quantity(PAIR, decision_day=10, through_day=10) == 3
    assert calendar.quantity(PAIR, decision_day=10, through_day=9) == 0
    assert calendar.total(PAIR) == 17


def test_dated_receipts_received_today_is_only_counted_as_on_hand():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 10, 12)
    calendar.add(PAIR, 11, 8)
    # The simulator receives before planning: 5 + 12 physically on hand.
    calendar.remove(PAIR, 10, 12)
    on_hand = 17
    pending = calendar.quantity(PAIR, decision_day=10, through_day=11)
    assert pending == 8
    assert on_hand + pending == 25
    assert calendar.total(PAIR) == 8


def test_dated_receipts_exclusion_never_cancels_the_physical_receipt():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 40, 90)
    assert calendar.quantity(PAIR, decision_day=10, through_day=16) == 0
    assert calendar.quantity(PAIR, decision_day=33, through_day=40) == 90
    assert calendar.total(PAIR) == 90
    calendar.remove(PAIR, 40, 90)
    assert calendar.total(PAIR) == 0
    assert calendar.quantity(PAIR, decision_day=40, through_day=47) == 0


def test_dated_receipts_disjoint_origins_accumulate_once_without_unit_rounding():
    calendar = engine.DatedReceiptCalendar()
    # Three distinct scheduled receipts: lane, external purchase, estimation.
    # An index lookup may neither duplicate nor consume any origin.
    for quantity in (7.25, 11.5, 13.75):
        calendar.add(PAIR, 15, quantity)
    for _ in range(3):
        assert calendar.quantity(PAIR, decision_day=10, through_day=15) == 32.5
        assert calendar.total(PAIR) == 32.5
    calendar.remove(PAIR, 15, 11.5)
    assert calendar.quantity(PAIR, decision_day=10, through_day=15) == 21
    assert calendar.total(PAIR) == 21


def test_dated_receipts_queries_follow_new_orders_and_partial_receipts():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 12, 10)
    calendar.add(PAIR, 14, 20)
    assert calendar.quantity(PAIR, decision_day=10, through_day=14) == 30
    calendar.add(PAIR, 13, 7)
    assert calendar.quantity(PAIR, decision_day=10, through_day=14) == 37
    calendar.remove(PAIR, 12, 4)
    assert calendar.quantity(PAIR, decision_day=10, through_day=14) == 33
    calendar.remove(PAIR, 14, 20)
    assert calendar.quantity(PAIR, decision_day=13, through_day=14) == 7
    assert calendar.total(PAIR) == 13


def test_dated_receipts_does_not_mix_sites_or_articles():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 12, 10)
    calendar.add(("M-2", "item:1"), 12, 100)
    calendar.add(("M-1", "item:2"), 12, 1000)
    assert calendar.quantity(PAIR, decision_day=10, through_day=15) == 10
    assert calendar.quantity(("missing", "item:1"), decision_day=10, through_day=15) == 0
    assert calendar.total(("M-2", "item:1")) == 100


def test_dated_receipts_fully_received_day_can_be_reused():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 12, 10)
    calendar.remove(PAIR, 12, 10)
    assert calendar.total(PAIR) == 0
    calendar.add(PAIR, 12, 3)
    assert calendar.quantity(PAIR, decision_day=12, through_day=12) == 3
    assert calendar.total(PAIR) == 3


@pytest.mark.parametrize("value", [None, math.nan, math.inf, -1])
def test_dated_receipts_missing_or_invalid_quantity_is_not_imputed(value):
    calendar = engine.DatedReceiptCalendar()
    with pytest.raises((TypeError, ValueError)):
        calendar.add(PAIR, 12, value)
    assert calendar.total(PAIR) == 0


@pytest.mark.parametrize("day", [None, math.nan, math.inf, 12.5, True])
def test_dated_receipts_missing_or_fractional_date_is_not_imputed(day):
    calendar = engine.DatedReceiptCalendar()
    with pytest.raises((TypeError, ValueError)):
        calendar.add(PAIR, day, 10)
    assert calendar.total(PAIR) == 0


def test_dated_receipts_unknown_or_excess_receipt_is_rejected():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 12, 10)
    for day, quantity in [(11, 1), (12, 11)]:
        with pytest.raises((KeyError, ValueError)):
            calendar.remove(PAIR, day, quantity)
    assert calendar.total(PAIR) == 10


@pytest.mark.parametrize("days, expected", [(0, 10), (1, 10), (1.1, 11), (7, 16), (7.1, 17)])
def test_dated_receipt_cover_includes_current_day(days, expected):
    assert engine.mrp_receipt_cover_end_day(10, days) == expected


@pytest.mark.parametrize("days", [None, math.nan, math.inf, -1])
def test_dated_receipt_cover_requires_documented_finite_window(days):
    with pytest.raises((TypeError, ValueError)):
        engine.mrp_receipt_cover_end_day(10, days)


def test_dated_receipt_window_does_not_claim_to_solve_intermediate_shortage():
    calendar = engine.DatedReceiptCalendar()
    calendar.add(PAIR, 16, 100)
    # Need 100 on day 11, receipt only day 16: an aggregate window credits it.
    assert calendar.quantity(PAIR, decision_day=10, through_day=16) == 100
    assert calendar.quantity(PAIR, decision_day=10, through_day=11) == 0
    # Both are true. A time-phased demand balance is still needed to detect the
    # day-11 shortage; passing these tests must not be called ERP calibration.


def test_production_safety_target_keeps_the_largest_existing_floor():
    # The three targets have one common quantity unit; they are not additive.
    assert engine.production_mrp_safety_target(500, 10, 20, 100) == 500
    assert engine.production_mrp_safety_target(50, 10, 20, 100) == 200
    assert engine.production_mrp_safety_target(50, 10, 20, 300) == 300


def test_production_safety_target_uses_converted_days_without_second_conversion():
    # 20 working days have already become 28 calendar days upstream.
    assert engine.production_mrp_safety_target(0, 125, 28, 0) == 3500
    assert engine.production_mrp_safety_target(0, 0, 28, 175) == 175
    assert engine.production_mrp_safety_target(0, 1.25, 2, 0) == 2.5


@pytest.mark.parametrize("position", range(4))
@pytest.mark.parametrize("value", [None, math.nan, math.inf, -1])
def test_production_safety_target_does_not_impute_invalid_source_values(position, value):
    arguments = [100, 10, 20, 50]
    arguments[position] = value
    with pytest.raises((TypeError, ValueError)):
        engine.production_mrp_safety_target(*arguments)


def test_production_safety_target_rejects_overflow_instead_of_infinite_orders():
    with pytest.raises(ValueError):
        engine.production_mrp_safety_target(0, 1e308, 1e308, 0)


def test_dated_planner_keeps_late_firm_quantity_without_compensatory_purchase():
    requirements = [Requirement("A", 3, 50), Requirement("B", 7, 50)]
    receipts = [FirmReceipt("F", 5, 60)]
    original = deepcopy((requirements, receipts))
    plan = plan_dated_requirements(decision_day=0, available_qty=20,
        requirements=requirements, firm_receipts=receipts, lead_days=2,
        lot_sizing=LotSizing(integer=True))
    assert [(a.requirement_id, a.supply_id, a.qty, a.delay_days) for a in plan.commitment_allocations] == [
        ("A", "opening_stock", 20, 0), ("A", "F", 30, 2), ("B", "F", 30, 0)]
    assert [(p.release_day, p.available_day, p.requested_day, p.qty) for p in plan.proposals] == [(5, 7, 7, 20)]
    assert (plan.proposed_qty, plan.late_qty, plan.late_qty_days, plan.firm_late_qty) == (20, 30, 60, 30)
    assert {b.day: (b.before_proposals_qty, b.after_proposals_qty) for b in plan.balances} == {
        0: (20, 20), 3: (-30, -30), 5: (30, 30), 7: (-20, 0)}
    assert sum(a.qty for a in plan.allocations if a.supply_id == "F") == 60
    assert sum(a.qty for a in plan.allocations) == 100
    assert plan.unallocated_firm_qty == 0
    assert plan.closing_projected_qty == 0
    assert (requirements, receipts) == original


def test_dated_planner_receipt_on_due_day_is_on_time():
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("A", 3, 10)], firm_receipts=[FirmReceipt("F", 3, 10)], lead_days=2)
    assert plan.proposals == ()
    assert plan.late_qty == 0
    assert plan.closing_projected_qty == 0
    assert [(a.available_day, a.due_day, a.qty) for a in plan.allocations] == [(3, 3, 10)]


def test_dated_planner_very_late_firm_is_not_cancelled_or_bought_again():
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("A", 3, 50)], firm_receipts=[FirmReceipt("F", 20, 100)], lead_days=2)
    assert plan.proposals == ()
    assert (plan.late_qty, plan.late_qty_days, plan.unallocated_firm_qty) == (50, 850, 50)
    assert {b.day: b.after_proposals_qty for b in plan.balances} == {0: 0, 3: -50, 20: 50}


def test_dated_planner_new_proposal_respects_earliest_possible_arrival():
    plan = plan_dated_requirements(decision_day=4, available_qty=0,
        requirements=[Requirement("A", 5, 50)], firm_receipts=[], lead_days=3)
    assert [(p.release_day, p.available_day, p.requested_day, p.qty) for p in plan.proposals] == [(4, 7, 5, 50)]
    assert (plan.late_qty, plan.late_qty_days, plan.firm_late_qty) == (50, 100, 0)
    assert plan.balances[-1].after_proposals_qty == 0


def test_dated_planner_minimum_surplus_is_reused_by_later_need():
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("A", 3, 10), Requirement("B", 7, 5)], firm_receipts=[], lead_days=2,
        lot_sizing=LotSizing(minimum=20, integer=True))
    assert [(p.release_day, p.available_day, p.qty) for p in plan.proposals] == [(1, 3, 20)]
    assert plan.closing_projected_qty == 5
    assert plan.late_qty == 0
    assert [(a.requirement_id, a.qty, a.available_day) for a in plan.allocations] == [("A", 10, 3), ("B", 5, 3)]


def test_dated_planner_lot_maximum_limits_each_order_not_daily_capacity():
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("A", 7, 250)], firm_receipts=[], lead_days=2,
        lot_sizing=LotSizing(minimum=50, multiple=50, maximum=100, integer=True))
    assert [(p.release_day, p.available_day, p.qty) for p in plan.proposals] == [(5, 7, 100), (5, 7, 100), (5, 7, 50)]
    assert plan.proposed_qty == 250
    assert plan.closing_projected_qty == 0


def test_dated_planner_fractional_forecast_produces_whole_units_and_carries_surplus():
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("A", 3, 1.2), Requirement("B", 7, 1.2)], firm_receipts=[], lead_days=2,
        lot_sizing=LotSizing(integer=True))
    assert [(p.available_day, p.qty) for p in plan.proposals] == [(3, 2), (7, 1)]
    assert plan.proposed_qty == 3
    assert plan.closing_projected_qty == pytest.approx(0.6)
    assert sum(a.qty for a in plan.allocations) == pytest.approx(2.4)


def test_dated_planner_fractional_forecast_does_not_create_one_unit_from_roundoff():
    # Decimal arithmetic: 30 * 0.1 = 3, so the existing 3 UN cover every need.
    needs = [Requirement(f"N-{i:02d}", i + 1, 0.1) for i in range(30)]
    plan = plan_dated_requirements(decision_day=0, available_qty=3,
        requirements=needs, firm_receipts=[], lead_days=2, lot_sizing=LotSizing(integer=True))
    assert plan.proposals == ()
    assert plan.proposed_qty == 0
    assert plan.late_qty == 0
    assert sum(a.qty for a in plan.allocations) == pytest.approx(3)
    assert plan.closing_projected_qty == pytest.approx(0)


def test_dated_planner_known_zero_need_preserves_unallocated_firm_stock():
    plan = plan_dated_requirements(decision_day=0, available_qty=2,
        requirements=[Requirement("A", 3, 0)], firm_receipts=[FirmReceipt("F", 5, 10)], lead_days=2)
    assert plan.proposals == ()
    assert plan.allocations == ()
    assert (plan.unallocated_firm_qty, plan.closing_projected_qty) == (10, 12)


def test_dated_planner_distinct_receipt_states_contribute_once_each():
    receipts = [FirmReceipt("held", 2, 3, "held"), FirmReceipt("transit", 3, 4, "in_transit"),
                FirmReceipt("confirmed", 5, 5, "confirmed")]
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("A", 7, 12)], firm_receipts=receipts, lead_days=2)
    assert plan.proposals == ()
    assert [(a.supply_kind, a.qty) for a in plan.allocations] == [("held", 3), ("in_transit", 4), ("confirmed", 5)]
    assert plan.closing_projected_qty == 0


def test_dated_planner_input_permutation_keeps_same_quantities_dates_and_allocations():
    needs = [Requirement("B", 7, 50), Requirement("A", 3, 50)]
    receipts = [FirmReceipt("G", 8, 20), FirmReceipt("F", 5, 40)]
    args = {"decision_day": 0, "available_qty": 20, "lead_days": 2, "lot_sizing": LotSizing(integer=True)}
    first = plan_dated_requirements(requirements=needs, firm_receipts=receipts, **args)
    second = plan_dated_requirements(requirements=needs[::-1], firm_receipts=receipts[::-1], **args)
    assert first == second


@pytest.mark.parametrize("value", [None, math.nan, math.inf, -1, True])
@pytest.mark.parametrize("field", ["available", "requirement", "firm"])
def test_dated_planner_missing_invalid_quantity_is_not_imputed(field, value):
    with pytest.raises(ValueError):
        plan_dated_requirements(decision_day=0, available_qty=value if field == "available" else 0,
            requirements=[Requirement("A", 3, value if field == "requirement" else 10)],
            firm_receipts=[FirmReceipt("F", 3, value if field == "firm" else 10)], lead_days=2)


@pytest.mark.parametrize("value", [None, math.nan, 1.5, True])
@pytest.mark.parametrize("field", ["decision", "due", "receipt", "lead"])
def test_dated_planner_missing_noninteger_day_is_not_imputed(field, value):
    with pytest.raises(ValueError):
        plan_dated_requirements(decision_day=value if field == "decision" else 0, available_qty=0,
            requirements=[Requirement("A", value if field == "due" else 3, 10)],
            firm_receipts=[FirmReceipt("F", value if field == "receipt" else 3, 10)],
            lead_days=value if field == "lead" else 2)


@pytest.mark.parametrize("kind", ["requirement", "firm"])
def test_dated_planner_duplicate_identity_is_rejected(kind):
    needs = [Requirement("A", 3, 10)] * (2 if kind == "requirement" else 1)
    receipts = [FirmReceipt("F", 3, 10)] * (2 if kind == "firm" else 1)
    with pytest.raises(ValueError):
        plan_dated_requirements(decision_day=0, available_qty=0,
            requirements=needs, firm_receipts=receipts, lead_days=2)


def test_dated_planner_past_firm_requires_reconciliation_with_available_stock():
    with pytest.raises(ValueError):
        plan_dated_requirements(decision_day=4, available_qty=10,
            requirements=[Requirement("A", 7, 10)], firm_receipts=[FirmReceipt("F", 3, 10)], lead_days=2)


@pytest.mark.parametrize("policy", [LotSizing(minimum=20, maximum=10), LotSizing(maximum=0),
    LotSizing(multiple=10, maximum=5), LotSizing(minimum=1.5, integer=True), LotSizing(multiple=-1)])
def test_dated_planner_inconsistent_lot_policy_is_rejected(policy):
    with pytest.raises(ValueError):
        plan_dated_requirements(decision_day=0, available_qty=0,
            requirements=[Requirement("A", 3, 10)], firm_receipts=[], lead_days=2, lot_sizing=policy)


def dated_network_inputs():
    return {"decision_day": 0, "requirements_by_pair": {}, "available_by_pair": {},
            "firm_receipts_by_pair": {}, "transport_sources_by_pair": {}, "bom_by_pair": {},
            "lead_days_by_pair": {}, "lot_sizing_by_pair": {}, "reserve_targets_by_pair": {},
            "coverage_days_by_pair": {}, "active_campaigns_by_pair": {}}


def test_dated_network_available_finished_stock_prevents_component_orders():
    depot, plant, component = ("DC", "PF"), ("M", "PF"), ("M", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={depot: [Requirement("customer", 10, 10)]},
                available_by_pair={depot: 10}, transport_sources_by_pair={depot: [(plant, 1)]},
                bom_by_pair={plant: [(component, 3)]})
    original = deepcopy(args)
    plans, requirements, _ = engine.plan_component_network(**args)
    assert all(plan.proposed_qty == 0 for plan in plans.values())
    assert sum(r.qty for r in requirements[component]) == 0
    assert args == original


def test_dated_network_nets_stock_before_two_same_site_processes_and_transport():
    depot, plant, semi, component = ("DC", "PF"), ("M", "PF"), ("M", "SEMI"), ("M", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={depot: [Requirement("customer", 20, 10)]},
                available_by_pair={plant: 5}, transport_sources_by_pair={depot: [(plant, 1)]},
                bom_by_pair={plant: [(semi, 2)], semi: [(component, 3)]},
                lead_days_by_pair={depot: 2, plant: 3, semi: 4, component: 5})
    plans, requirements, _ = engine.plan_component_network(**args)
    assert {pair: p.proposed_qty for pair, p in plans.items()} == {depot: 10, plant: 5, semi: 10, component: 30}
    assert [(r.due_day, r.qty) for r in requirements[plant]] == [(18, 10)]
    assert [(r.due_day, r.qty) for r in requirements[semi]] == [(15, 10)]
    assert [(r.due_day, r.qty) for r in requirements[component]] == [(11, 30)]
    assert [(p.release_day, p.available_day, p.qty) for p in plans[component].proposals] == [(6, 11, 30)]


def test_dated_network_inter_site_intermediate_transport_explodes_bom_once():
    final, semi_at_final, semi_at_origin, raw = ("M-A", "PF"), ("M-A", "SEMI"), ("M-B", "SEMI"), ("M-B", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={final: [Requirement("customer", 30, 10)]},
                bom_by_pair={final: [(semi_at_final, 2)], semi_at_origin: [(raw, 3)]},
                transport_sources_by_pair={semi_at_final: [(semi_at_origin, 1)]})
    plans, requirements, _ = engine.plan_component_network(**args)
    assert plans[final].proposed_qty == 10
    assert plans[semi_at_final].proposed_qty == 20
    assert plans[semi_at_origin].proposed_qty == 20
    assert plans[raw].proposed_qty == 60
    assert sum(r.qty for r in requirements[raw]) == 60


def test_dated_network_active_wip_credits_output_once_and_needs_only_remaining_components():
    product, component = ("M", "PF"), ("M", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("customer", 10, 100)]},
                bom_by_pair={product: [(component, 1)]},
                active_campaigns_by_pair={product: ("C", 20, 80, 5)})
    plans, requirements, audit = engine.plan_component_network(**args)
    assert plans[product].proposed_qty == 0
    assert [(a.supply_id, a.qty) for a in plans[product].allocations] == [("campaign:C", 100)]
    assert sum(r.qty for r in requirements[component]) == 20
    assert plans[component].proposed_qty == 20
    assert audit[component]["campaign_remaining_qty"] == 20


def test_dated_network_committed_campaign_needs_components_without_new_forecast():
    product, component = ("M", "PF"), ("M", "MP")
    args = dated_network_inputs()
    args.update(bom_by_pair={product: [(component, 2)]},
                active_campaigns_by_pair={product: ("C", 20, 80, 5)})
    plans, requirements, _ = engine.plan_component_network(**args)
    assert plans[product].proposed_qty == 0
    assert plans[product].unallocated_firm_qty == 100
    assert sum(r.qty for r in requirements[component]) == 40
    assert plans[component].proposed_qty == 40


def test_dated_network_campaign_also_supplied_as_firm_is_rejected():
    product = ("M", "PF")
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("customer", 10, 100)]},
                active_campaigns_by_pair={product: ("C", 20, 80, 5)},
                firm_receipts_by_pair={product: [FirmReceipt("campaign:C", 5, 100, "confirmed")]})
    with pytest.raises(ValueError):
        engine.plan_component_network(**args)


def test_dated_network_late_commitment_does_not_explode_repurchase_into_bom():
    product, component = ("M", "PF"), ("M", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("A", 3, 50), Requirement("B", 7, 50)]},
                available_by_pair={product: 20}, firm_receipts_by_pair={product: [FirmReceipt("F", 5, 60)]},
                lead_days_by_pair={product: 2}, bom_by_pair={product: [(component, 3)]})
    plans, requirements, _ = engine.plan_component_network(**args)
    assert plans[product].proposed_qty == 20
    assert plans[product].firm_late_qty == 30
    assert sum(r.qty for r in requirements[component]) == 60
    assert [(r.due_day, r.qty) for r in requirements[component]] == [(5, 60)]


def test_dated_network_transport_shares_conserve_quantity():
    destination, left, right = ("M", "MP"), ("S-A", "MP"), ("S-B", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={destination: [Requirement("need", 10, 100)]},
                transport_sources_by_pair={destination: [(left, 0.25), (right, 0.75)]})
    plans, requirements, _ = engine.plan_component_network(**args)
    assert sum(r.qty for r in requirements[left]) == 25
    assert sum(r.qty for r in requirements[right]) == 75
    assert plans[left].proposed_qty + plans[right].proposed_qty == 100


def test_dated_network_reserve_is_complementary_to_gross_cover_not_added_twice():
    args = dated_network_inputs()
    args.update(requirements_by_pair={PAIR: [Requirement("need", 3, 80)]},
                reserve_targets_by_pair={PAIR: 100}, coverage_days_by_pair={PAIR: 7})
    plans, requirements, audit = engine.plan_component_network(**args)
    assert audit[PAIR]["reserve_requirement_qty"] == 20
    assert sum(r.qty for r in requirements[PAIR]) == 100
    assert plans[PAIR].proposed_qty == 100


@pytest.mark.parametrize("decision", [0, 1, 7, 31])
def test_dated_network_uncovered_reserve_is_replenished_at_earliest_planned_date(decision):
    args = dated_network_inputs()
    args.update(decision_day=decision, reserve_targets_by_pair={PAIR: 100},
                coverage_days_by_pair={PAIR: 30}, lead_days_by_pair={PAIR: 10})
    original = deepcopy(args)
    plans, requirements, audit = engine.plan_component_network(**args)
    # Candidate model convention: restore the already calculated protection
    # without moving its purchase twenty days ahead on every daily review.
    assert audit[PAIR]["reserve_requirement_qty"] == 100
    assert [(r.requirement_id, r.due_day, r.qty) for r in requirements[PAIR]] == [
        ("reserve:M-1|item:1", decision + 10, 100)]
    assert [(p.release_day, p.available_day, p.qty) for p in plans[PAIR].proposals] == [
        (decision, decision + 10, 100)]
    assert plans[PAIR].late_qty == 0
    assert args == original


def test_dated_network_reserve_order_is_netted_once_until_received_then_as_stock():
    # Ordinary state sequence in memory: one 100-unit order placed at day 0,
    # still pending at days 1/5/9, then the same quantity physically on hand.
    for decision in (0, 1, 5, 9, 10, 20, 40):
        args = dated_network_inputs()
        args.update(decision_day=decision, reserve_targets_by_pair={PAIR: 100},
                    coverage_days_by_pair={PAIR: 30}, lead_days_by_pair={PAIR: 10})
        if 0 < decision < 10:
            args["firm_receipts_by_pair"] = {PAIR: [FirmReceipt("one-purchase", 10, 100)]}
        elif decision >= 10:
            args["available_by_pair"] = {PAIR: 100}
        original = deepcopy(args)
        plans, _, _ = engine.plan_component_network(**args)
        assert plans[PAIR].proposed_qty == (100 if decision == 0 else 0)
        if decision != 0:
            assert plans[PAIR].proposals == ()
        # The tagged protection requirement is planning only; no physical
        # stock or received order is consumed or modified by this calculation.
        assert args == original


@pytest.mark.parametrize("target", [100, 60, 0])
def test_dated_network_reduced_reserve_does_not_cancel_or_duplicate_committed_order(target):
    args = dated_network_inputs()
    args.update(decision_day=1, reserve_targets_by_pair={PAIR: target},
                coverage_days_by_pair={PAIR: 30}, lead_days_by_pair={PAIR: 10},
                firm_receipts_by_pair={PAIR: [FirmReceipt("one-purchase", 10, 100)]})
    plans, _, audit = engine.plan_component_network(**args)
    assert audit[PAIR]["firm_receipts"] == [FirmReceipt("one-purchase", 10, 100)]
    assert plans[PAIR].proposals == ()
    assert plans[PAIR].unallocated_firm_qty == 100 - target


def test_dated_network_forecast_already_covering_target_adds_no_protection_purchase():
    args = dated_network_inputs()
    args.update(requirements_by_pair={PAIR: [Requirement("forecast", 20, 100)]},
                reserve_targets_by_pair={PAIR: 100}, coverage_days_by_pair={PAIR: 30},
                lead_days_by_pair={PAIR: 10})
    plans, requirements, audit = engine.plan_component_network(**args)
    assert audit[PAIR]["reserve_requirement_qty"] == 0
    assert requirements[PAIR] == [Requirement("forecast", 20, 100)]
    assert [(p.release_day, p.available_day, p.qty) for p in plans[PAIR].proposals] == [(10, 20, 100)]


def test_dated_network_late_firm_reserve_order_is_not_bought_again():
    args = dated_network_inputs()
    args.update(reserve_targets_by_pair={PAIR: 100}, coverage_days_by_pair={PAIR: 30},
                lead_days_by_pair={PAIR: 10},
                firm_receipts_by_pair={PAIR: [FirmReceipt("late-purchase", 40, 100)]})
    plans, requirements, audit = engine.plan_component_network(**args)
    assert [(r.due_day, r.qty) for r in requirements[PAIR]] == [(10, 100)]
    assert plans[PAIR].proposals == ()
    assert audit[PAIR]["firm_receipts"] == [FirmReceipt("late-purchase", 40, 100)]
    assert (plans[PAIR].late_qty, plans[PAIR].late_qty_days, plans[PAIR].firm_late_qty) == (100, 3000, 100)


def test_dated_network_cycle_rejected_before_any_physical_state_changes():
    first, second = ("M", "A"), ("M", "B")
    args = dated_network_inputs()
    args.update(requirements_by_pair={first: [Requirement("need", 10, 1)]},
                bom_by_pair={first: [(second, 1)], second: [(first, 1)]})
    original = deepcopy(args)
    with pytest.raises(ValueError, match="acyclic"):
        engine.plan_component_network(**args)
    assert args == original


@pytest.mark.parametrize("field,value", [
    ("lead_days_by_pair", 1.5), ("lead_days_by_pair", True), ("lead_days_by_pair", -1),
    ("coverage_days_by_pair", 1.5), ("coverage_days_by_pair", True), ("coverage_days_by_pair", -1),
    ("reserve_targets_by_pair", None), ("reserve_targets_by_pair", math.nan),
    ("reserve_targets_by_pair", math.inf), ("reserve_targets_by_pair", -1),
])
def test_dated_network_invalid_policy_is_not_rounded_or_imputed(field, value):
    args = dated_network_inputs()
    args["requirements_by_pair"] = {PAIR: [Requirement("need", 10, 1)]}
    args[field] = {PAIR: value}
    with pytest.raises(ValueError):
        engine.plan_component_network(**args)


@pytest.mark.parametrize("shares", [(0.4, 0.4), (0.7, 0.7), (True, 0.5)])
def test_dated_network_invalid_transport_split_cannot_create_or_lose_requirements(shares):
    args = dated_network_inputs()
    args.update(requirements_by_pair={PAIR: [Requirement("need", 10, 100)]},
                transport_sources_by_pair={PAIR: [(("S-A", PAIR[1]), shares[0]), (("S-B", PAIR[1]), shares[1])]})
    with pytest.raises(ValueError):
        engine.plan_component_network(**args)


def test_dated_planner_decimal_residual_never_becomes_an_undercovered_float_proposal():
    # 2 - 0.9999999999999999 = 1.0000000000000001. Converting that
    # missing quantity too early to float gives 1.0 and undercovers the need.
    plan = plan_dated_requirements(decision_day=0, available_qty=0.9999999999999999,
        requirements=[Requirement("need", 5, 2)], firm_receipts=[], lead_days=2)
    assert len(plan.proposals) == 1
    proposal = plan.proposals[0]
    exact_missing = Decimal('1.0000000000000001')
    public_quantity = Decimal(str(proposal.qty))
    assert exact_missing <= public_quantity <= exact_missing + Decimal(str(math.ulp(proposal.qty)))
    assert (proposal.release_day, proposal.available_day) == (3, 5)
    assert plan.late_qty == 0
    assert 0 <= plan.closing_projected_qty <= math.ulp(proposal.qty)
    assert sum(a.qty for a in plan.allocations) == pytest.approx(2, abs=1e-15)


def test_dated_planner_real_001893_day_two_fractional_requirements_are_fully_covered():
    # Exact failing inputs captured from the ordinary five-year simulation;
    # copied as numbers, with no filesystem fixture or application oracle.
    due_days = [252, 255, 258, 260, 262, 265, 268, 271, 275, 278, 281, 284,
                286, 289, 291, 294, 298, 302, 304, 307, 312, 315, 317, 319,
                321, 323, 325, 326, 328, 331, 334, 337, 339, 342, 344, 345,
                347, 348, 349, 351, 353, 355, 356]
    requirements = [Requirement(f"derived:{index}", day, 222.16320000000002)
                    for index, day in enumerate(due_days, 1)]
    requirements.append(Requirement("reserve", 127, 9037.541672003308))
    plan = plan_dated_requirements(decision_day=2, available_qty=9561.3368,
        requirements=requirements, firm_receipts=[], lead_days=90)
    exact_missing = Decimal('222.16320000000002') * 43 + Decimal('9037.541672003308') - Decimal('9561.3368')
    proposed = sum((Decimal(str(p.qty)) for p in plan.proposals), Decimal(0))
    representation_budget = sum((Decimal(str(math.ulp(p.qty))) for p in plan.proposals), Decimal(0))
    assert exact_missing <= proposed <= exact_missing + representation_budget
    assert len(plan.proposals) == 41
    assert (plan.proposals[0].release_day, plan.proposals[0].available_day) == (168, 258)
    assert all(p.available_day - p.release_day == 90 for p in plan.proposals)
    assert 0 <= plan.closing_projected_qty <= float(representation_budget)
    assert plan.late_qty == 0
    for requirement in requirements:
        allocated = sum(a.qty for a in plan.allocations if a.requirement_id == requirement.requirement_id)
        assert allocated == pytest.approx(requirement.qty, abs=1e-12)


def test_dated_planner_fractional_multiple_and_maximum_keep_the_actual_excess_need():
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement("need", 5, 0.30000000000000004)], firm_receipts=[], lead_days=2,
        lot_sizing=LotSizing(minimum=0.1, multiple=0.1, maximum=0.3))
    assert [p.qty for p in plan.proposals] == [0.3, 0.1]
    assert plan.closing_projected_qty == pytest.approx(0.09999999999999996)
    assert plan.late_qty == 0


def test_dated_network_real_campaign_cannot_finish_before_remaining_packaging():
    product, packaging = ("M-1430", "item:268967"), ("M-1430", "item:344135")
    args = dated_network_inputs()
    args.update(decision_day=905,
        requirements_by_pair={product: [Requirement("customer", 908, 107800)]},
        firm_receipts_by_pair={packaging: [FirmReceipt("purchase", 971, 240000)]},
        active_campaigns_by_pair={product: ("real-campaign", 18405, 89395, 908)},
        bom_by_pair={product: [(packaging, 1)]})
    original = deepcopy(args)
    plans, requirements, audit = engine.plan_component_network(**args)
    # 89 395 are already executed WIP; only the remaining 18 405 need packaging.
    assert [(r.due_day, r.qty) for r in requirements[packaging]] == [(906, 18405)]
    assert all(plan.proposals == () for plan in plans.values())
    assert audit[product]["firm_receipts"] == [FirmReceipt("campaign:real-campaign", 971, 107800, "confirmed")]
    assert [(a.supply_id, a.available_day, a.qty) for a in plans[product].allocations] == [
        ("campaign:real-campaign", 971, 107800)]
    assert (plans[product].late_qty, plans[product].late_qty_days) == (107800, 107800 * 63)
    assert {b.day: b.after_proposals_qty for b in plans[product].balances} == {905: 0, 908: -107800, 971: 0}
    assert plans[packaging].unallocated_firm_qty == 240000 - 18405
    assert args == original


@pytest.mark.parametrize("reverse_insertion", [False, True])
def test_dated_network_material_date_propagates_through_two_existing_campaigns(reverse_insertion):
    product, semi, raw = ("M", "PF"), ("M", "SEMI"), ("M", "MP")
    campaigns = [(product, ("PF-C", 100, 0, 6)), (semi, ("SEMI-C", 50, 50, 3))]
    links = [(product, [(semi, 1)]), (semi, [(raw, 0.4)])]
    if reverse_insertion:
        campaigns.reverse()
        links.reverse()
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("customer", 10, 100)]},
        active_campaigns_by_pair=dict(campaigns), bom_by_pair=dict(links),
        firm_receipts_by_pair={raw: [FirmReceipt("raw-purchase", 20, 20)]})
    plans, requirements, audit = engine.plan_component_network(**args)
    assert sum(r.qty for r in requirements[semi]) == 100
    assert sum(r.qty for r in requirements[raw]) == 20
    assert all(plan.proposals == () for plan in plans.values())
    for pair, identity in ((semi, "SEMI-C"), (product, "PF-C")):
        assert audit[pair]["firm_receipts"] == [FirmReceipt("campaign:" + identity, 20, 100, "confirmed")]
        assert {a.available_day for a in plans[pair].allocations} == {20}
    assert (plans[product].late_qty, plans[product].late_qty_days) == (100, 1000)


@pytest.mark.parametrize("remaining,wip,component_stock", [(18405, 89395, 18405), (0, 107800, 0)])
def test_dated_network_ready_material_or_completed_wip_keeps_estimated_finish(remaining, wip, component_stock):
    product, component = ("M", "PF"), ("M", "MP")
    args = dated_network_inputs()
    args.update(decision_day=905,
        requirements_by_pair={product: [Requirement("customer", 908, 107800)]},
        available_by_pair={component: component_stock},
        firm_receipts_by_pair={component: [FirmReceipt("unneeded-future", 971, 240000)]},
        active_campaigns_by_pair={product: ("C", remaining, wip, 908)},
        bom_by_pair={product: [(component, 1)]})
    plans, _, audit = engine.plan_component_network(**args)
    assert audit[product]["firm_receipts"] == [FirmReceipt("campaign:C", 908, 107800, "confirmed")]
    assert plans[product].late_qty == 0
    assert all(plan.proposals == () for plan in plans.values())


def test_dated_network_campaign_uses_latest_allocated_component_without_adding_process_time():
    product, early, late, on_hand = ("M", "PF"), ("M", "A"), ("M", "B"), ("M", "C")
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("customer", 10, 10)]},
        available_by_pair={on_hand: 40},
        firm_receipts_by_pair={early: [FirmReceipt("early", 12, 20)], late: [FirmReceipt("late", 20, 30)]},
        active_campaigns_by_pair={product: ("C", 10, 0, 5)},
        bom_by_pair={product: [(early, 2), (late, 3), (on_hand, 4)]},
        lead_days_by_pair={product: 3})
    plans, _, audit = engine.plan_component_network(**args)
    assert audit[product]["firm_receipts"] == [FirmReceipt("campaign:C", 20, 10, "confirmed")]
    assert plans[product].late_qty_days == 100
    assert all(plan.proposals == () for plan in plans.values())


def test_dated_network_delayed_campaign_keeps_existing_quantified_proposal_and_its_dates():
    product, component = ("M", "PF"), ("M", "MP")
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("first", 3, 10), Requirement("later", 7, 5)]},
        active_campaigns_by_pair={product: ("C", 10, 0, 3)},
        firm_receipts_by_pair={component: [FirmReceipt("material", 20, 30)]},
        bom_by_pair={product: [(component, 1)]},
        lead_days_by_pair={product: 2}, lot_sizing_by_pair={product: LotSizing(minimum=20)})
    plans, requirements, audit = engine.plan_component_network(**args)
    # The one 20-unit new proposal covers the 5-unit shortage at minimum lot size.
    # Moving the existing campaign changes allocation, not the new order or BOM.
    assert [(p.release_day, p.available_day, p.requested_day, p.qty) for p in plans[product].proposals] == [(5, 7, 7, 20)]
    assert sum(r.qty for r in requirements[component]) == 30
    assert plans[component].proposals == ()
    assert audit[product]["firm_receipts"] == [FirmReceipt("campaign:C", 20, 10, "confirmed")]
    assert (plans[product].late_qty, plans[product].late_qty_days) == (10, 40)
    # This guard covers existing campaigns only, not feasibility of every new proposal.


def external_component_payload(**row_changes):
    row = {"demand_id": "source-I42", "node_id": PAIR[0], "item_id": PAIR[1],
           "known_day": 4, "period_start_day": 11, "period_days": 7,
           "qty": 10, "uom": "UN", "source_file": "source.xlsx",
           "source_cells": "Plan!I42", "estimation_basis": "declared_incremental_hypothesis"}
    row.update(row_changes)
    return {"schema_version": 1, "origin": "2025-01-01", "scenario_id": "estimated",
            "semantics": "incremental_non_modelled_component_use", "repeat_period_days": None,
            "rows": [row]}


def external_component_calendar(payload=None, *, unit="UN", horizon=730):
    return ExternalComponentDemandCalendar(payload or external_component_payload(),
        pair_uoms={PAIR: unit}, origin_date="2025-01-01", horizon_days=horizon)


def test_external_components_weekly_integer_split_conserves_quantity_and_knowledge():
    payload = external_component_payload()
    saved = deepcopy(payload)
    calendar = external_component_calendar(payload)
    assert calendar.requirements(decision_day=3, first_day=0, through_day=40) == {}
    rows = calendar.requirements(decision_day=4, first_day=11, through_day=17)[PAIR]
    assert [r.qty for r in rows] == [1, 1, 2, 1, 2, 1, 2]
    assert [r.due_day for r in rows] == list(range(11, 18))
    assert sum(r.qty for r in rows) == 10
    assert calendar.due(10) == {}
    assert calendar.due(17)[PAIR] == (rows[-1],)
    assert calendar.due(18) == {}
    assert payload == saved


def test_external_components_repeated_year_is_synthetic_and_known_only_in_its_cycle():
    payload = external_component_payload()
    payload["repeat_period_days"] = 365
    calendar = external_component_calendar(payload)
    assert calendar.requirements(decision_day=368, first_day=376, through_day=382) == {}
    rows = calendar.requirements(decision_day=369, first_day=376, through_day=382)[PAIR]
    assert sum(r.qty for r in rows) == 10
    assert len({r.requirement_id for r in rows}) == 7
    assert all(":C1:" in r.requirement_id for r in rows)
    assert {calendar.provenance(r.requirement_id)["known_day"] for r in rows} == {369}
    assert calendar.due(730) == {}


def test_external_components_mass_split_keeps_fraction_and_truncated_horizon():
    payload = external_component_payload(uom="KG", qty=1, period_days=3)
    calendar = external_component_calendar(payload, unit="KG", horizon=13)
    rows = calendar.requirements(decision_day=4, first_day=11, through_day=99)[PAIR]
    assert [r.due_day for r in rows] == [11, 12]
    assert sum(r.qty for r in rows) == pytest.approx(2/3)
    # The third day is outside this run; it is not redistributed into day 12.


def test_external_components_explicit_zero_creates_no_physical_requirement():
    calendar = external_component_calendar(external_component_payload(qty=0))
    assert calendar.pairs == (PAIR,)
    assert calendar.requirements(decision_day=4, first_day=0, through_day=729) == {}


@pytest.mark.parametrize("changes", [
    {"qty": None}, {"qty": float("nan")}, {"qty": float("inf")}, {"qty": -1},
    {"qty": True}, {"qty": 1.5}, {"known_day": 12}, {"known_day": True},
    {"period_days": 0}, {"period_days": 8}, {"period_days": 2.5},
    {"period_start_day": 363}, {"node_id": "unknown"}, {"uom": "KG"},
    {"source_file": ""}, {"source_cells": ""}, {"estimation_basis": ""},
])
def test_external_components_invalid_source_is_not_imputed(changes):
    with pytest.raises(ValueError):
        external_component_calendar(external_component_payload(**changes))


@pytest.mark.parametrize("duplicate_id,start", [(True, 30), (False, 15)])
def test_external_components_duplicate_identity_or_overlapping_vintages_are_rejected(duplicate_id, start):
    payload = external_component_payload()
    other = {**payload["rows"][0], "period_start_day": start}
    if not duplicate_id:
        other["demand_id"] = "other-vintage"
    payload["rows"].append(other)
    with pytest.raises(ValueError):
        external_component_calendar(payload)


def test_external_components_fifo_backlog_is_carried_once_and_separate_from_new_demand():
    old = Requirement("old", 1, 4)
    new = Requirement("new", 2, 6)
    first = serve_external_component_requirements(decision_day=2, available_qty=7,
        backlog=[old], due=[new], uom="UN")
    assert first.allocations == (old, Requirement("new", 2, 3))
    assert first.remaining == (Requirement("new", 2, 3),)
    assert (first.demand_qty, first.backlog_start_qty, first.consumed_qty, first.available_end_qty) == (6, 4, 7, 0)
    second = serve_external_component_requirements(decision_day=3, available_qty=5,
        backlog=first.remaining, due=[Requirement("tomorrow", 3, 2)], uom="UN")
    assert second.consumed_qty == 5
    assert second.remaining == ()
    assert second.demand_qty == 2
    assert first.consumed_qty + second.consumed_qty == 12


@pytest.mark.parametrize("bad", [None, True, -1, float("nan"), float("inf"), .5])
def test_external_components_physical_units_reject_invalid_stock_and_need(bad):
    with pytest.raises(ValueError):
        serve_external_component_requirements(decision_day=1, available_qty=bad,
            backlog=(), due=[Requirement("use", 1, 1)], uom="UN")
    with pytest.raises(ValueError):
        serve_external_component_requirements(decision_day=1, available_qty=10,
            backlog=(), due=[Requirement("use", 1, bad)], uom="UN")


def test_external_components_future_or_repeated_physical_requirement_is_rejected():
    row = Requirement("use", 2, 3)
    with pytest.raises(ValueError):
        serve_external_component_requirements(decision_day=1, available_qty=10,
            backlog=(), due=[row], uom="UN")
    with pytest.raises(ValueError):
        serve_external_component_requirements(decision_day=2, available_qty=10,
            backlog=[row], due=[row], uom="UN")


def test_external_components_consume_available_lots_only_without_creating_finished_goods():
    stock = {PAIR: 10.0}
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock=stock, item_unit_map={PAIR[1]: "UN"})
    held_lot = next(iter(ledger.lots))
    availability = engine.InitialStockAvailability({"schema_version": 1,
        "knowledge_date": "2025-01-01", "rows": [{"node_id": PAIR[0], "item_id": PAIR[1],
        "quantity": 10, "uom": "UN", "release_day": 3, "source_row": "MRP!J1"}]},
        stock=stock, item_unit_map={PAIR[1]: "UN"}, origin_date="2025-01-01")
    availability.initialize(stock=stock, ledger=ledger)
    available_lot = ledger.create_lot(day=1, node_id=PAIR[0], item_id=PAIR[1], qty=3,
        source_type="lane_receipt", event_type="lane_receipt", uom="UN")
    service = serve_external_component_requirements(decision_day=1, available_qty=3,
        backlog=(), due=[Requirement("external-use", 1, 7)], uom="UN")
    allocations = ledger.consume(day=1, node_id=PAIR[0], item_id=PAIR[1],
        qty=service.consumed_qty, event_type="external_component_consume", uom="UN")
    assert [(r["lot_id"], r["qty"]) for r in allocations] == [(available_lot, 3)]
    assert ledger.lots[held_lot]["qty_remaining"] == 10
    assert service.remaining == (Requirement("external-use", 1, 4),)
    assert ledger.genealogy_rows == []
    assert not any(r["event_type"] == "production_output" for r in ledger.event_rows)


def test_external_components_add_incremental_need_once_before_multilevel_netting():
    product, semi, raw = ("M", "PF"), ("M", "SEMI"), ("M", "RAW")
    args = dated_network_inputs()
    args.update(requirements_by_pair={product: [Requirement("PF", 10, 10)],
        semi: [Requirement("external-use", 10, 5)]},
        bom_by_pair={product: [(semi, 2)], semi: [(raw, 3)]})
    plans, requirements, _ = engine.plan_component_network(**args)
    assert plans[product].proposed_qty == 10
    assert plans[semi].proposed_qty == 25
    assert plans[raw].proposed_qty == 75
    assert sum(r.qty for r in requirements[semi]) == 25
    assert sum(r.qty for r in requirements[raw]) == 75


def external_service_audit_example():
    policy = external_component_payload(known_day=0, period_start_day=0, period_days=1, qty=5)
    source = policy["rows"][0]
    row = {"day": 0, "node_id": PAIR[0], "item_id": PAIR[1], "uom": "UN",
           "demand_qty": 5, "backlog_start_qty": 0, "required_qty": 5,
           "consumed_qty": 3, "backlog_end_qty": 2, "available_before_qty": 3,
           "available_after_qty": 0, "core_consumed_qty": 4, "total_component_consumed_qty": 7}
    event = {"day": 0, "node_id": PAIR[0], "item_id": PAIR[1], "uom": "UN",
             "event_type": "external_component_consume", "source_id": "external:estimated:source-I42:C0:D0",
             "qty": 3, "notes": json.dumps({"scope": "estimated_non_modelled_component_use", "due_day": 0,
                 "known_day": 0, "cycle_index": 0, "scenario_id": "estimated", "demand_id": source["demand_id"],
                 "source_file": source["source_file"], "source_cells": source["source_cells"],
                 "estimation_basis": source["estimation_basis"]})}
    core = {"day": 0, "node_id": PAIR[0], "item_id": PAIR[1], "consumed_qty": 4}
    return policy, row, event, core


def test_external_independent_audit_accepts_conserved_stock_and_separate_backlog():
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    policy, row, event, core = external_service_audit_example()
    evidence = Evidence()
    assert audit_external_component_service([row], [event], [core], policy, 1, evidence) == 1
    assert all(check["failed"] == 0 for check in evidence.checks.values())


@pytest.mark.parametrize("fault", ["debit_missing", "quantity_duplicated", "unknown_source",
                                  "core_double_counted", "backlog_lost", "unproven_provenance"])
def test_external_independent_audit_rejects_accounting_or_identity_errors_in_memory(fault):
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    policy, row, event, core = external_service_audit_example()
    events = [event]
    if fault == "debit_missing": events = []
    elif fault == "quantity_duplicated": events = [event, dict(event)]
    elif fault == "unknown_source": event["source_id"] = "not-a-source-requirement"
    elif fault == "core_double_counted": row["core_consumed_qty"] = 7
    elif fault == "backlog_lost": row["backlog_end_qty"] = 0
    elif fault == "unproven_provenance": event["notes"] = "{}"
    evidence = Evidence()
    audit_external_component_service([row], events, [core], policy, 1, evidence)
    assert any(check["failed"] for check in evidence.checks.values())


def test_external_intermediate_signal_reaches_upstream_factory_without_inventing_finished_goods():
    semi_use, semi_make, raw = ("F", "item:SEMI"), ("S", "item:SEMI"), ("S", "item:RAW")
    bom = {("F", "item:PF"): [(semi_use, 2)], semi_make: [(raw, 3)]}
    lanes = [{"src": "S", "dst": "F", "item_id": "item:SEMI"}]
    signal = engine.upstream_external_production_signals({semi_use: 20}, lanes=lanes,
        process_input_requirements_by_output_pair=bom, finished_good_item_ids={"item:PF"})
    assert signal == {semi_make: 20}
    args = dated_network_inputs()
    args.update(requirements_by_pair={semi_use: [Requirement("external", 10, 20)]},
        transport_sources_by_pair={semi_use: [(semi_make, 1)]}, bom_by_pair=bom)
    plans, requirements, _ = engine.plan_component_network(**args)
    assert plans[semi_make].proposed_qty == 20
    assert sum(r.qty for r in requirements[raw]) == 60
    # The physical output signal is not a second seed added to these requirements.


def test_external_raw_use_never_becomes_extra_intermediate_or_finished_output():
    semi, raw = ("S", "item:SEMI"), ("S", "item:RAW")
    signal = engine.upstream_external_production_signals({raw: 100}, lanes=[],
        process_input_requirements_by_output_pair={semi: [(raw, 3)]},
        finished_good_item_ids={"item:PF"})
    assert signal == {}


def test_external_multisource_intermediate_signal_is_shared_instead_of_duplicated():
    used = ("F", "item:SEMI")
    first, second = ("S1", "item:SEMI"), ("S2", "item:SEMI")
    signal = engine.upstream_external_production_signals({used: 20}, lanes=[
        {"src": "S1", "dst": "F", "item_id": "item:SEMI", "mrp_share": 1},
        {"src": "S2", "dst": "F", "item_id": "item:SEMI", "mrp_share": 3}],
        process_input_requirements_by_output_pair={first: [(("S1", "item:RAW"), 3)],
            second: [(("S2", "item:RAW"), 3)]}, finished_good_item_ids={"item:PF"})
    assert signal == {first: 5, second: 15}


def lane_schedule_example(**changes):
    args = {"day": 7, "lead_days": 55, "lead_cover": 128, "order_frequency_days": 7,
            "pull_qty": 1800.0, "delivered_qty": 1800.0, "reliability": 1.0,
            "shipment_uom": "KG", "standard_order_qty": 50.0,
            "standard_order_binding": True}
    args.update(changes)
    return engine.lane_delivery_schedule(**args)


def test_external_dated_lane_keeps_due_transfer_together_without_second_time_spread():
    # Conditional oracle: 1800 KG have already passed stock/capacity constraints.
    # It does not assert that the real source stock held 1800 KG on day 7.
    assert lane_schedule_example(preserve_dated_release=True) == [(62, 1800, 1800)]
    # Lead55 and review cadence7 are unchanged; neither is divided by lot count.
    assert lane_schedule_example(day=14, preserve_dated_release=True) == [(69, 1800, 1800)]


def test_external_lane_legacy_spread_preserves_exact_dates_quantities_and_default():
    expected_days = [62, 69, 76, 83, 90, 97, 104, 111, 118, 126,
                     133, 140, 147, 154, 161, 168, 175, 182, 189]
    expected = [(day, 100 if index < 17 else 50, 100 if index < 17 else 50)
                for index, day in enumerate(expected_days)]
    assert lane_schedule_example() == expected
    assert lane_schedule_example(preserve_dated_release=False) == expected
    assert sum(row[1] for row in expected) == 1800
    assert lane_schedule_example(standard_order_binding=False) == [(62, 1800, 1800)]


@pytest.mark.parametrize("stock,capacity,expected,remaining", [(1300, 5000, 1300, 500), (1300, 400, 400, 1400)])
def test_external_lane_preserves_upstream_stock_and_capacity_limits(stock, capacity, expected, remaining):
    constrained = engine.mrp_purchase_order_quantity(1800, min(stock, capacity), 50,
        binding=True, uom="KG")
    assert constrained == expected
    schedule = lane_schedule_example(pull_qty=constrained, delivered_qty=constrained,
        preserve_dated_release=True)
    assert schedule == [(62, expected, expected)]
    assert stock - sum(r[1] for r in schedule) >= 0
    assert capacity - sum(r[1] for r in schedule) >= 0
    assert 1800 - sum(r[1] for r in schedule) == remaining


def test_external_lane_does_not_apply_quality_twice_or_change_integer_execution():
    assert lane_schedule_example(pull_qty=1800, delivered_qty=900, reliability=.5,
        preserve_dated_release=True) == [(62, 1800, 900)]
    assert lane_schedule_example(pull_qty=10, delivered_qty=8, reliability=.8,
        shipment_uom="UN", standard_order_qty=1, preserve_dated_release=True) == [(62, 10, 8)]


@pytest.mark.parametrize("available", [13, 26, 52, 63, 91])
def test_production_input_boundary_never_issues_one_extra_physical_unit(available):
    ratio = 11 / 1000
    candidate = available / ratio
    # Independent reproduction: the uncorrected binary product crosses the
    # integer boundary; ceil is the physical issue rule, not a tolerance.
    assert math.ceil(candidate * ratio) == available + 1
    quantity = engine.production_input_feasible_execution_quantity(candidate,
        component_limits=[(available, ratio, "UN")])
    assert 0 < candidate - quantity <= math.ulp(candidate)
    assert math.ceil(quantity * ratio) == available
    assert engine.required_component_quantity(quantity, ratio, "UN") == available
    assert not quantity.is_integer()  # Internal work is allowed to be fractional.


@pytest.mark.parametrize("reverse", [False, True])
def test_production_input_feasibility_respects_all_components_together(reverse):
    limits = [(13, .011, "UN"), (500, .5, "UN"), (3000, 1, "ZUN"), (10000, 2, "KG")]
    quantity = engine.production_input_feasible_execution_quantity(13 / .011,
        component_limits=list(reversed(limits)) if reverse else limits)
    assert quantity == 1000  # The second component, not 426331, limits this case.
    assert [math.ceil(quantity * ratio) for _, ratio, unit in limits if unit != "KG"] == [11, 500, 1000]
    assert all(engine.required_component_quantity(quantity, ratio, unit) <= available
        for available, ratio, unit in limits)
    assert quantity * 2 == 2000  # Mass remains fractional-capable and conserved.


@pytest.mark.parametrize("candidate", [0.0, 400.0, 1000.125])
def test_production_input_feasibility_preserves_already_safe_capacity_or_plan(candidate):
    quantity = engine.production_input_feasible_execution_quantity(candidate,
        component_limits=[(13, .011, "UN"), (3000, 2, "KG")])
    assert quantity.hex() == candidate.hex()
    assert math.ceil(quantity * .011) <= 13


def test_production_input_zero_stock_and_wip_residue_consume_nothing():
    quantity = engine.production_input_feasible_execution_quantity(2,
        component_limits=[(0, .011, "UN")])
    assert quantity == 0
    residue = engine.production_input_feasible_execution_quantity(1e-12,
        component_limits=[(1, .011, "UN")])
    # The execution guard still precedes every material issue in the engine.
    executed = engine.production_wip_execution_quantity(residue)
    assert executed == 0
    assert engine.required_component_quantity(executed, .011, "UN") == 0


@pytest.mark.parametrize("candidate,limits", [
    (None, []), (True, []), (-1, []), (float("nan"), []), (float("inf"), []),
    (1, [(None, .011, "UN")]), (1, [(True, .011, "UN")]),
    (1, [(1.5, .011, "UN")]), (1, [(float("inf"), .011, "UN")]),
    (1, [(13, 0, "UN")]), (1, [(13, -1, "UN")]),
    (1, [(13, float("nan"), "UN")]), (1, [(13, .011, "")]),
])
def test_production_input_feasibility_rejects_missing_or_nonphysical_limits(candidate, limits):
    with pytest.raises(ValueError):
        engine.production_input_feasible_execution_quantity(candidate, component_limits=limits)


def test_production_input_fractional_work_completes_an_integer_finished_batch():
    batch = engine.ProductionBatchWip(campaign_id="C", batch_id="B", node_id="M",
        item_id="item:PF", campaign_started_day=0, batch_started_day=0, target_qty=2400)
    first = engine.production_input_feasible_execution_quantity(13 / .011,
        component_limits=[(13, .011, "UN")])
    assert batch.add_execution(first, [{"lot_id": "first", "qty": 13}]) == first
    assert not batch.is_complete
    assert not batch.executed_qty.is_integer()
    second = engine.production_input_feasible_execution_quantity(batch.remaining_qty,
        component_limits=[(14, .011, "UN")])
    assert math.ceil(second * .011) == 14
    batch.add_execution(second, [{"lot_id": "second", "qty": 14}])
    assert batch.is_complete
    assert batch.executed_qty == batch.target_qty == 2400
    assert sum(row["qty"] for row in batch.parent_allocations) == 27
    # Actual released PF integrality is also checked against the full-run CSV;
    # this memory case only proves that fractional work does not change the lot.
