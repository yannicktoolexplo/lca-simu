"""Memory-only calendar oracles; no files, fixtures, observed future or runs."""
from copy import deepcopy
from datetime import date, timedelta

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import FirmReceipt, LotSizing, Requirement, StockProtection


PAIR = ("factory", "component")


def network_case(*, exact=False, protection=False):
    calendar = tuple((day, day + 39) for day in range(89, 454))
    args = dict(decision_day=89, requirements_by_pair={PAIR: [Requirement("finite_shift", 608, 100)]},
        available_by_pair={}, firm_receipts_by_pair={}, transport_sources_by_pair={}, bom_by_pair={},
        lead_days_by_pair={PAIR: 39}, lot_sizing_by_pair={PAIR: LotSizing(integer=True)},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={})
    context = dict(physical_lead_days=39, receipt_days=0, origin_date="2025-01-01")
    if exact:
        args["availability_by_release_by_pair"] = {PAIR: calendar}
    else:
        context["calendar_kind"] = "supplier_receipt"
        args["anticipated_need_by_pair"] = {PAIR: dict(source_working_days=0, origin_weekday=2,
            fixed_floor_qty=0, availability_by_release=calendar)}
    if protection:
        args["requirements_by_pair"] = {PAIR: []}
        args["protection_by_pair"] = {PAIR: [StockProtection("source", 608, 100)]}
    return args, context


@pytest.mark.parametrize("exact", [False, True])
def test_network_calendar_extends_propagated_need608_preserving_quantity_and_prefix(exact):
    args, context = network_case(exact=exact)
    before = deepcopy(args)
    with pytest.raises(ValueError, match="cover|calendar"):
        engine.plan_component_network(**args)
    plans, needs, audit = engine.plan_component_network(**args,
        known_supply_calendar_context_by_pair={PAIR: context})
    proposal, = plans[PAIR].proposals
    # Independent arithmetic: known39 calendar days, demand608 => order569.
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (569, 608, 100)
    assert plans[PAIR].late_qty == 0
    assert needs[PAIR] == before["requirements_by_pair"][PAIR]
    assert args == before
    trace, = audit[PAIR]["calendar_extensions"]
    assert trace["old_last_release_day"] == 453 and trace["old_last_available_day"] == 492
    assert trace["new_last_release_day"] == 609 and trace["added_rows"] == 156
    assert trace["existing_prefix_preserved"] is True


def test_network_calendar_extends_source_stock_protection_without_physical_demand():
    args, context = network_case(exact=True, protection=True)
    plans, needs, audit = engine.plan_component_network(**args,
        known_supply_calendar_context_by_pair={PAIR: context})
    proposal, = plans[PAIR].proposals
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (569, 608, 100)
    assert needs[PAIR] == []
    assert audit[PAIR]["protection_points"][0].minimum_qty == 100


def test_network_calendar_captured_042342_rule_21calendar_plus14weekdays():
    # Independent source-rule oracle from the captured J89 failure: no affine
    # approximation; weekends create a variable release->available offset.
    origin = date(2025, 1, 1)
    def available(release):
        day, count = release + 21, 0
        while count < 14:
            day += 1
            count += (origin + timedelta(days=day)).weekday() < 5
        return day
    args, _ = network_case()
    args["anticipated_need_by_pair"][PAIR].update(source_working_days=5,
        availability_by_release=tuple((d, available(d)) for d in range(89, 454)))
    with pytest.raises(ValueError, match="cover"):
        engine.plan_component_network(**args)
    plans, _, audit = engine.plan_component_network(**args,
        known_supply_calendar_context_by_pair={PAIR: dict(calendar_kind="supplier_receipt",
            physical_lead_days=21, receipt_days=14, origin_date="2025-01-01")})
    proposal, = plans[PAIR].proposals
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (560, 601, 100)
    assert audit[PAIR]["anticipated_requirements"] == (Requirement("anticipated:601", 601, 100),)
    assert audit[PAIR]["calendar_extensions"][0]["new_last_available_day"] == 650


def test_network_calendar_preserves_a_late_firm_receipt_without_repurchase():
    args, context = network_case()
    args["firm_receipts_by_pair"] = {PAIR: [FirmReceipt("committed", 700, 100, "confirmed")]}
    plans, _, audit = engine.plan_component_network(**args,
        known_supply_calendar_context_by_pair={PAIR: context})
    assert plans[PAIR].proposals == ()
    assert audit[PAIR]["firm_receipts"] == args["firm_receipts_by_pair"][PAIR]
    assert plans[PAIR].late_qty == 100 and plans[PAIR].late_qty_days == 9200


def test_calendar_extension_covers_weekend_quality_plateau_with_latest_release():
    # Jan1 Wednesday: two quality weekdays give J0->J2, J1->J5,
    # J2/J3/J4->J6. A calendar endingJ2 misses feasible latest releaseJ4.
    old = ((0, 2), (1, 5), (2, 6))
    context = dict(calendar_kind="supplier_receipt", physical_lead_days=0,
        receipt_days=2, origin_date="2025-01-01")
    extended, _ = engine.extend_known_supply_calendar(old, decision_day=0, through_day=7, context=context)
    assert extended[:3] == old
    assert [r for r, a in extended if a <= 6][-1] == 4
    assert dict(extended)[3] == dict(extended)[4] == 6


def test_calendar_extension_preserves_exact_start_closures():
    extended, _ = engine.extend_known_supply_calendar(((0, 1),), decision_day=0, through_day=5,
        context=dict(physical_lead_days=1, closed_days=(2,), receipt_days=0))
    assert extended == ((0, 1), (3, 4), (4, 5), (5, 6))


def test_calendar_extension_refuses_mismatching_declared_prefix():
    with pytest.raises(ValueError, match="prefix"):
        engine.extend_known_supply_calendar(((0, 2), (1, 3)), decision_day=0, through_day=10,
            context=dict(physical_lead_days=3))


def test_calendar_extension_never_infers_unknown_tail():
    original = ((0, 10), (1, 11))
    assert engine.extend_known_supply_calendar(original, decision_day=0, through_day=20,
        context=None) == (original, None)


def test_calendar_extension_refuses_horizon_above3660():
    with pytest.raises(ValueError, match="3660"):
        engine.extend_known_supply_calendar(((0, 1),), decision_day=0, through_day=3661,
            context=dict(physical_lead_days=1))


def test_calendar_extension_keeps_already_sufficient_calendar_identical():
    original = ((0, 2), (1, 3), (2, 4))
    assert engine.extend_known_supply_calendar(original, decision_day=0, through_day=2,
        context=dict(physical_lead_days=2)) == (original, None)


@pytest.mark.parametrize("decision,remaining", [(75, 3), (76, 2), (77, 1)])
def test_engaged_finite_campaign_completion_does_not_slide_after_daily_work(decision, remaining):
    # 100UN at25/day: after first workJ75, 75UN=3days remain, finishJ78.
    assert engine.engaged_production_available_day(decision_day=decision,
        remaining_work_days=remaining) == 78


@pytest.mark.parametrize("decision,remaining", [(75, 3), (76, 2), (77, 1)])
def test_engaged_finite_campaign_quality_two_weekdays_once(decision, remaining):
    # J78 ThursdayMarch20 -> quality FridayJ79, MondayJ82.
    assert engine.engaged_production_available_day(decision_day=decision,
        remaining_work_days=remaining, receipt_days=2) == 82


def test_engaged_finite_campaign_respects_known_work_and_quality_closures():
    # WorkJ76,J77, J78 closed, last workJ79Friday; qualityJ82,J83.
    assert engine.engaged_production_available_day(decision_day=75,
        remaining_work_days=3, closed_days=(78,), receipt_days=2) == 83


@pytest.mark.parametrize("remaining", [-1, 2.5, True])
def test_engaged_finite_campaign_rejects_invalid_remaining_work_days(remaining):
    with pytest.raises(ValueError, match="integer days"):
        engine.engaged_production_available_day(decision_day=75, remaining_work_days=remaining)
