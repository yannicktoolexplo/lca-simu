"""Pure memory oracles: net procurement precision, never physical mass edits.

No filesystem fixture, mocked files, timestamps or deletion operations.
"""
from dataclasses import replace
from fractions import Fraction

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, StockProtection, SupplierOffer,
    plan_anticipated_requirements, plan_dated_requirements,
    plan_sourced_requirements, plan_with_stock_protection, reschedule_dated_plan,
)
from etudecas.simulation.engine.run_first_simulation import mrp_mass_net_rounding_quantum


def _plan(quantities, *, scale=1, stock=0, minimum=0, multiple=0, maximum=None, grouping=None):
    return plan_dated_requirements(decision_day=0, available_qty=stock * scale,
        requirements=tuple(Requirement(str(day), day, qty * scale)
                           for day, qty in enumerate(quantities, 1)),
        firm_receipts=(), lead_days=0, grouping_days=grouping,
        lot_sizing=LotSizing(minimum=minimum * scale, multiple=multiple * scale,
            maximum=None if maximum is None else maximum * scale, net_rounding_quantum=scale))


@pytest.mark.parametrize("scale", [1, 1000])
@pytest.mark.parametrize("net,expected", [(.499, 0), (.5, 1), (1.49, 1), (1.5, 2),
    (600.4, 600), (600.5, 601)])
def test_half_up_net_and_precise_residual(scale, net, expected):
    plan = _plan([net], scale=scale)
    # Fraction is an independent rational oracle, not the production Decimal helper.
    q = Fraction(str(net))
    assert expected == (q.numerator * 2 + q.denominator) // (2 * q.denominator)
    assert plan.proposed_qty == expected * scale
    assert plan.closing_projected_qty == pytest.approx((expected - net) * scale)
    assert sum(r.qty for r in plan.uncovered_requirements) == pytest.approx(max(0, net - expected) * scale)


@pytest.mark.parametrize("scale", [1, 1000])
def test_round_once_before_standard_lots_and_keep_maximum(scale):
    assert _plan([600.4], scale=scale, minimum=600, multiple=600).proposed_qty == 600 * scale
    assert _plan([600.5], scale=scale, minimum=600, multiple=600).proposed_qty == 1200 * scale
    plan = _plan([1200.4], scale=scale, minimum=600, multiple=600, maximum=600)
    assert [p.qty for p in plan.proposals] == [600 * scale, 600 * scale]
    assert sum(r.qty for r in plan.uncovered_requirements) == pytest.approx(.4 * scale)


@pytest.mark.parametrize("scale", [1, 1000])
def test_round_net_not_stock_or_daily_consumption(scale):
    plan = _plan([100.7], scale=scale, stock=100.3)
    assert not plan.proposals
    assert plan.opening_available_qty == 100.3 * scale
    assert next(b for b in plan.balances if b.day == 1).requirement_qty == 100.7 * scale
    assert plan.closing_projected_qty == pytest.approx(-.4 * scale)


@pytest.mark.parametrize("scale", [1, 1000])
def test_sub_kg_residual_accumulates_with_real_lateness(scale):
    plan = _plan([.3, .3], scale=scale)
    assert [(p.requested_day, p.qty) for p in plan.proposals] == [(2, scale)]
    assert next(b for b in plan.balances if b.day == 1).after_proposals_qty == -.3 * scale
    assert plan.late_qty == .3 * scale and plan.late_qty_days == .3 * scale
    assert not plan.uncovered_requirements
    plan = _plan([1.49, .02], scale=scale)
    assert [(p.requested_day, p.qty) for p in plan.proposals] == [(1, scale), (2, scale)]


def test_many_small_needs_and_grouping_retain_total():
    plan = _plan([.2] * 10)
    assert [(p.requested_day, p.qty) for p in plan.proposals] == [(3, 1), (8, 1)]
    assert plan.closing_projected_qty == 0
    grouped = _plan([.3, .3], grouping=7)
    assert [(p.requested_day, p.qty) for p in grouped.proposals] == [(1, 1)]
    assert grouped.procurement_groups[0].net_requirement_qty == .6


@pytest.mark.parametrize("scale", [1, 1000])
def test_precision_dust_no_longer_triggers_a_standard_lot(scale):
    needs = (Requirement("first", 1, 5570.000000000001 * scale), Requirement("next", 2, 10 * scale))
    args = dict(decision_day=0, available_qty=5570 * scale, requirements=needs, firm_receipts=(), lead_days=0)
    old = plan_dated_requirements(**args, lot_sizing=LotSizing(minimum=600 * scale, multiple=600 * scale))
    new = plan_dated_requirements(**args, lot_sizing=LotSizing(minimum=600 * scale, multiple=600 * scale,
                                                             net_rounding_quantum=scale))
    assert old.proposals[0].requested_day == 1
    assert new.proposals[0].requested_day == 2
    assert new.proposed_qty == old.proposed_qty == 600 * scale


def test_protection_and_anticipated_wrappers_preserve_precise_needs():
    args = dict(decision_day=0, available_qty=10, requirements=(Requirement("use", 1, .3),),
                firm_receipts=(), lead_days=0, lot_sizing=LotSizing(net_rounding_quantum=1))
    protected = plan_with_stock_protection(**args, protection=(StockProtection("floor", 1, 10),))
    assert not protected.plan.proposals
    assert protected.plan.closing_projected_qty == 9.7
    assert protected.protection[-1].shortfall_qty == pytest.approx(.3)
    plan, _, audit = plan_anticipated_requirements(**args, source_working_days=1,
        origin_weekday=2, fixed_floor_qty=10, fixed_floor_mode="additive")
    assert not plan.proposals and plan.closing_projected_qty == 9.7
    assert sum(r.qty for r in audit["anticipated_plan"].uncovered_requirements) == pytest.approx(.3)


def test_reschedule_preserves_uncovered_mass_without_fictitious_supply():
    needs = (Requirement("use", 1, 1.4),)
    args = dict(decision_day=0, available_qty=0, requirements=needs,
                firm_receipts=(), lead_days=0, lot_sizing=LotSizing(net_rounding_quantum=1))
    original = plan_dated_requirements(**args)
    plan = reschedule_dated_plan(original, requirements=needs, firm_receipts=(),
        proposals=tuple(replace(p, available_day=3) for p in original.proposals))
    assert plan.proposed_qty == 1 and plan.closing_projected_qty == -.4
    assert plan.late_qty_days == 2
    assert plan.uncovered_requirements == (Requirement("use", 1, .4),)


@pytest.mark.parametrize("provisional", [False, True])
@pytest.mark.parametrize("scale", [1, 1000])
def test_sourcing_propagates_precision_and_firm_receipts(provisional, scale):
    lot = LotSizing(minimum=600 * scale, multiple=600 * scale, net_rounding_quantum=scale)
    primary = SupplierOffer("primary", 1, "EUR", "KG" if scale == 1 else "G", 0, lot)
    plan = plan_sourced_requirements(decision_day=0, available_qty=0,
        requirements=(Requirement("use", 0, 1200.4 * scale),),
        firm_receipts=(FirmReceipt("committed", 0, 600 * scale, "confirmed"),),
        primary=primary, backups=(), provisional_lots_until_release=provisional).plan
    assert plan.proposed_qty == 600 * scale
    assert sum(r.qty for r in plan.uncovered_requirements) == pytest.approx(.4 * scale)


def test_policy_is_explicit_and_un_integer_unchanged():
    assert mrp_mass_net_rounding_quantum(None, "KG") == 0
    assert mrp_mass_net_rounding_quantum("nearest_kg_half_up_v1", "KG") == 1
    assert mrp_mass_net_rounding_quantum("nearest_kg_half_up_v1", "G") == 1000
    assert mrp_mass_net_rounding_quantum("nearest_kg_half_up_v1", "UN") == 0
    with pytest.raises(ValueError, match="Unknown"):
        mrp_mass_net_rounding_quantum("guess", "KG")
    args = dict(decision_day=0, available_qty=0, requirements=(Requirement("fractional_forecast", 1, .1),),
                firm_receipts=(), lead_days=0)
    assert plan_dated_requirements(**args, lot_sizing=LotSizing(integer=True)).proposed_qty == 1
    with pytest.raises(ValueError, match="UN"):
        plan_dated_requirements(**args, lot_sizing=LotSizing(integer=True, net_rounding_quantum=1))
    with pytest.raises(ValueError, match="quantum"):
        plan_dated_requirements(**args, lot_sizing=LotSizing(net_rounding_quantum=-1))


@pytest.mark.parametrize("scale", [1, 1000])
def test_backup_sub_kg_shortages_accumulate_instead_of_disappearing(scale):
    lot = LotSizing(net_rounding_quantum=scale)
    primary = SupplierOffer("primary", 1, "EUR", "KG" if scale == 1 else "G", 10, lot)
    backup = replace(primary, supplier_id="backup", purchase_unit_cost=2, lead_days=0)
    sourced = plan_sourced_requirements(decision_day=0, available_qty=0,
        requirements=(Requirement("first", 1, .3 * scale), Requirement("second", 2, .3 * scale)),
        firm_receipts=(), primary=primary, backups=(backup,))
    assert [(p.role, p.proposal.requested_day, p.proposal.qty) for p in sourced.proposals] == [("backup", 2, scale)]
    assert sourced.plan.late_qty_days == .3 * scale
