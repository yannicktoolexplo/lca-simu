"""Independent calendar-coverage oracles for all three purchasing routes."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, SupplierOffer, plan_allocated_purchase_requirements,
    plan_dated_requirements, plan_sourced_requirements,
)


ROUTES = ("dated", "allocated", "sourced")


def route_plan(route, calendar, *, due=15, qty=100, firms=()):
    args = dict(decision_day=0, available_qty=0, requirements=(Requirement("need", due, qty),),
        firm_receipts=firms)
    lot = LotSizing(minimum=20, multiple=20, integer=True)
    offer = SupplierOffer("supplier", 1, "EUR", "UN", 10, lot, calendar)
    if route == "dated":
        return plan_dated_requirements(**args, lead_days=10, lot_sizing=lot,
            availability_by_release=calendar)
    if route == "allocated":
        return plan_allocated_purchase_requirements(**args, offers=(offer,), allocation_weights=(1,)).plan
    return plan_sourced_requirements(**args, primary=offer, backups=()).plan


@pytest.mark.parametrize("route", ROUTES)
def test_calendar_routes_accept_available_coverage_beyond_last_release(route):
    short = tuple((day, day+10) for day in range(11))
    full = tuple((day, day+10) for day in range(26))
    before = deepcopy(short)
    result = route_plan(route, short, qty=31)
    assert result == route_plan(route, full, qty=31)
    proposal, = result.proposals
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (5, 15, 40)
    assert result.closing_projected_qty == 9 and result.late_qty == 0
    assert short == before


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("due", [20, 21])
def test_calendar_routes_refuse_truncated_plateau_or_insufficient_arrivals(route, due):
    # Lastarrival20==need20 might omit release11 also arriving20.
    # Lastarrival20<need21 plainly does not cover the requirement.
    short = tuple((day, day+10) for day in range(11))
    with pytest.raises(ValueError, match="cover"):
        route_plan(route, short, due=due)


@pytest.mark.parametrize("route", ROUTES)
def test_calendar_routes_equal_arrival_safe_when_releases_reach_need(route):
    calendar = tuple((day, 20) for day in range(21))
    result = route_plan(route, calendar, due=20)
    proposal, = result.proposals
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (20, 20, 100)


@pytest.mark.parametrize("route", ROUTES)
def test_calendar_routes_keep_earliest_arrival_and_explicit_lateness(route):
    calendar = tuple((day, day+10) for day in range(11))
    result = route_plan(route, calendar, due=5)
    proposal, = result.proposals
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (0, 10, 100)
    assert result.late_qty == 100 and result.late_qty_days == 500


@pytest.mark.parametrize("route", ROUTES)
def test_calendar_routes_retain_late_firm_without_duplicate_purchase(route):
    calendar = tuple((day, day+10) for day in range(11))
    result = route_plan(route, calendar, firms=(FirmReceipt("firm", 25, 100, "confirmed"),))
    assert result.proposals == ()
    assert result.late_qty == 100 and result.late_qty_days == 1000


def test_allocated_four_supplier_lots_and_weights_unchanged_with_shorter_covered_calendar():
    # Source-shaped timing: decision89, known releases89..453, arrivals314..678.
    # Need540 remains covered; latest permitted release315 -> availability540.
    short = tuple((day, day+225) for day in range(89, 454))
    full = tuple((day, day+225) for day in range(89, 542))
    lot = LotSizing(minimum=20000, multiple=20000, net_rounding_quantum=1)
    def solve(calendar):
        offers = tuple(SupplierOffer(f"S{i}", price, "EUR", "KG", 225, lot, calendar,
            standard_order_qty=20000) for i, price in enumerate((12.1, 12.1, 12.15, 15)))
        return plan_allocated_purchase_requirements(decision_day=89, available_qty=0,
            requirements=(Requirement("future", 540, 1000000),), firm_receipts=(),
            offers=offers, allocation_weights=(.7, .2, .05, .05), grouping_days=1)
    result = solve(short)
    assert result == solve(full)
    #700k,200k,50k->60k; final share capped to40k remaining: no extra purchase.
    assert [(row.supplier_id, row.proposal.qty) for row in result.proposals] == [
        ("S0", 700000), ("S1", 200000), ("S2", 60000), ("S3", 40000)]
    assert all((row.proposal.release_day, row.proposal.available_day) == (315, 540)
               for row in result.proposals)
    assert result.plan.proposed_qty == 1000000 and result.plan.closing_projected_qty == 0


@pytest.mark.parametrize("route", ROUTES)
def test_calendar_routes_keep_ordered_monotone_input_guard(route):
    with pytest.raises(ValueError, match="monotone|ordered"):
        route_plan(route, ((0, 20), (1, 19)), due=15)
