"""Exact in-memory oracles; no files, fixture mutation or simulator runs."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import (
    LotSizing, OrderProposal, Requirement, WeeklyProductionProgramme,
    plan_anticipated_requirements,
)


PAIR = ("F", "item:PF")
A = ("F", "item:A")
B = ("F", "item:B")
C = ("F", "item:C")
MULTIDAY = "current_week_existing_lot_multiday_v1"
LEGACY = "current_week_existing_lot_v1"


def programme_case(*, mode=MULTIDAY, ratio_a=2, budget_a=220, available_a=200, extra=False):
    payload = dict(schema_version=1, mode=mode, max_promotions_per_process=1,
        current_bucket_policy="latest_known_including_current", assumption="Synthetic known programme",
        series=[dict(node_id=PAIR[0], output_item_id=PAIR[1], versions=[dict(
            known_day=4, period_start_day=4, period_end_day_exclusive=11,
            component_budgets=[
                dict(item_id=A[1], qty=budget_a, uom="UN", source_file="synthetic", source_cells="A1"),
                dict(item_id=B[1], qty=22, uom="M", source_file="synthetic", source_cells="B1")])])])
    bom = {PAIR: [(A, ratio_a), (B, .2)] + ([(C, .02)] if extra else [])}
    units = {PAIR: "UN", A: "UN", B: "M", C: "UN"}
    placement = dict(start_day=5, physical_finish_day=8, available_day=8,
        allocations=[(5, 25), (6, 25), (7, 25), (8, 25)], capacity_known_day=4)
    args = dict(pair=PAIR, decision_day=5, proposals=[OrderProposal("future", 20, 23, 23, 100)],
        calendar=[(5, 8)], consumed={}, committed={}, available={A: available_a, B: 20, C: 4},
        capacity_qty=25, multiday_placements={"future": placement})
    return WeeklyProductionProgramme(payload, bom_by_pair=bom, pair_uoms=units), args, payload, bom, units


def anticipated_case(*, need=15, calendar=None, safety=0, decision=0):
    return dict(decision_day=decision, available_qty=0, requirements=[Requirement("physical", need, 100)],
        firm_receipts=(), source_working_days=safety, origin_weekday=2, fixed_floor_qty=0,
        lead_days=10, lot_sizing=LotSizing(integer=True),
        availability_by_release=tuple((d, d + 10) for d in range(11)) if calendar is None else calendar)


def test_anticipated_calendar_available_dates_cover_need_beyond_last_release():
    args = anticipated_case()
    before = deepcopy(args)
    physical, sourced, audit = plan_anticipated_requirements(**args)
    proposal, = physical.proposals
    assert (proposal.release_day, proposal.available_day, proposal.requested_day, proposal.qty) == (5, 15, 15, 100)
    assert physical.late_qty == 0 and sourced is None
    assert audit["anticipated_requirements"] == (Requirement("anticipated:15", 15, 100),)
    assert args == before


def test_anticipated_calendar_capture_shape_covers_day594_without_extrapolation():
    # Captured industrial failure: decision89, last physical need622,
    # source safety20 weekdays, last release453, last availability625.
    # Tuesday622 minus four Monday-Friday weeks = Tuesday594.
    calendar = tuple((day, day + 172) for day in range(89, 454))
    args = anticipated_case(need=622, calendar=calendar, safety=20, decision=89)
    physical, _, audit = plan_anticipated_requirements(**args)
    assert audit["anticipated_requirements"] == (Requirement("anticipated:594", 594, 100),)
    proposal, = physical.proposals
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (422, 594, 100)
    assert (proposal.release_day, proposal.available_day) in calendar
    assert [(b.day, b.requirement_qty) for b in physical.balances if b.requirement_qty] == [(622, 100)]
    assert physical.late_qty == 0


@pytest.mark.parametrize("need", [20, 21])
def test_anticipated_calendar_refuses_unproven_plateau_or_unknown_tail(need):
    # Last arrival20 equal to the need cannot exclude a later release also
    # arriving20. Last arrival20 below need21 does not cover the tail either.
    with pytest.raises(ValueError, match="cover the planning horizon"):
        plan_anticipated_requirements(**anticipated_case(need=need))


def test_anticipated_calendar_equal_availability_is_safe_if_releases_reach_need():
    calendar = tuple((day, 10) for day in range(11))
    plan, _, _ = plan_anticipated_requirements(**anticipated_case(need=10, calendar=calendar))
    assert (plan.proposals[0].release_day, plan.proposals[0].available_day) == (10, 10)


def test_anticipated_calendar_keeps_earliest_known_receipt_when_already_late():
    plan, _, audit = plan_anticipated_requirements(**anticipated_case(need=5))
    assert (plan.proposals[0].release_day, plan.proposals[0].available_day) == (0, 10)
    assert plan.late_qty == audit["anticipated_plan"].late_qty == 100
    assert plan.late_qty_days == 500


@pytest.mark.parametrize("calendar", [((0, 10), (2, 12)), ((0, 20), (1, 19)), ((1, 11), (2, 12))])
def test_anticipated_calendar_still_rejects_invalid_ordering_or_decision_origin(calendar):
    with pytest.raises(ValueError, match="consecutive and monotone"):
        plan_anticipated_requirements(**anticipated_case(calendar=calendar))


def test_multiday_programme_advances_original100_on_four25_days():
    book, args, _, _, _ = programme_case()
    before = deepcopy(args)
    row = book.select(**args)
    assert book.mode == MULTIDAY
    assert (row["qty"], row["release_day"], row["physical_finish_day"], row["available_day"]) == (100, 5, 8, 8)
    assert row["work_allocations"] == ((5, 25), (6, 25), (7, 25), (8, 25))
    assert row["original_proposal_id"] == "future" and row["original_release_day"] == 20
    assert row["original_available_day"] == 23 and row["capacity_known_day"] == 4
    assert [(r["allocated_qty"], r["residual_qty"]) for r in row["source_budgets"]] == [(200, 20), (20, 2)]
    assert row["physical_finish_delay_vs_source_week_days"] == 0
    assert args == before and book.rows == {} and book.events == []


def test_multiday_programme_keeps_physical_finish_distinct_from_quality_availability():
    book, args, _, _, _ = programme_case()
    args["multiday_placements"]["future"]["available_day"] = 12
    row = book.select(**args)
    # ThursdayJan9 finish8 + two weekdays => MondayJan13 available12.
    assert row["physical_finish_day"] == 8 and row["available_day"] == 12
    assert row["work_allocations"][-1] == (8, 25)


def test_multiday_programme_requires_all_material_not_just_first_day_share():
    book, args, _, _, _ = programme_case(available_a=199)
    assert book.select(**args) is None
    assert book.rows == {}


def test_multiday_programme_nets_known_budget_consumption_and_commitment_once():
    book, args, _, _, _ = programme_case()
    args.update(consumed={A: 10}, committed={A: 10})
    row = book.select(**args)
    budget = row["source_budgets"][0]
    assert (budget["consumed_qty"], budget["committed_qty"], budget["allocated_qty"], budget["residual_qty"]) == (10, 10, 200, 0)
    args["committed"][A] = 11
    assert book.select(**args) is None


def test_multiday_programme_partial_execution_and_one_promotion_survive_next_week():
    _, args, payload, bom, units = programme_case()
    next_version = deepcopy(payload["series"][0]["versions"][0])
    next_version.update(known_day=11, period_start_day=11, period_end_day_exclusive=18)
    payload["series"][0]["versions"].append(next_version)
    book = WeeklyProductionProgramme(payload, bom_by_pair=bom, pair_uoms=units)
    book.accept(book.select(**args))
    book.engage(PAIR, 5, "physical_campaign")
    for day in (5, 6, 7):
        book.execute(PAIR, day, "physical_campaign", 25)
        assert book.rows[PAIR]["state"] == "engaged"
    book.execute(PAIR, 8, "physical_campaign", 25)
    assert book.rows[PAIR]["state"] == "executed" and book.rows[PAIR]["executed_qty"] == 100
    assert sum(r.get("executed_today_qty", 0) for r in book.events) == 100
    args.update(decision_day=12, calendar=[(12, 15)])
    assert book.select(**args) is None  # not a fresh authorization each week


def test_multiday_programme_reports_cross_week_work_without_new_authorization():
    book, args, _, _, _ = programme_case()
    args["capacity_qty"] = 10
    args["multiday_placements"]["future"].update(physical_finish_day=14, available_day=14,
        allocations=[(day, 10) for day in range(5, 15)])
    row = book.select(**args)
    assert row["physical_finish_delay_vs_source_week_days"] == 4
    assert row["period_end_day_exclusive"] == 11 and row["qty"] == 100


def test_multiday_programme_preserves_partial_first_day_after_other_work():
    book, args, _, _, _ = programme_case()
    args["capacity_qty"] = 15
    args["multiday_placements"]["future"].update(physical_finish_day=9, available_day=9,
        allocations=[(5, 15), (6, 25), (7, 25), (8, 25), (9, 10)])
    row = book.select(**args)
    assert row["physical_finish_day"] == 9 and row["work_allocations"][0] == (5, 15)
    assert sum(qty for _, qty in row["work_allocations"]) == 100


@pytest.mark.parametrize("fault", ["zero_capacity", "future_source", "Sunday", "no_proposal", "missing_placement", "initial_Pack"])
def test_multiday_programme_abstains_when_a_launch_guard_is_missing(fault):
    book, args, _, _, _ = programme_case()
    if fault == "zero_capacity": args["capacity_qty"] = 0
    elif fault == "future_source": args["decision_day"] = 3
    elif fault == "Sunday": args.update(decision_day=4, calendar=[(4, 7)])
    elif fault == "no_proposal": args["proposals"] = []
    elif fault == "missing_placement": args["multiday_placements"] = {}
    else: args["opening_pack_pending_qty"] = 100
    assert book.select(**args) is None and book.rows == {}


@pytest.mark.parametrize("fault", ["missing_context", "future_capacity", "bad_finish", "early_availability", "partial_work", "unordered_work", "excess_first_day", "fractional_UN"])
def test_multiday_programme_rejects_noncausal_or_incomplete_placements(fault):
    book, args, _, _, _ = programme_case()
    placement = args["multiday_placements"]["future"]
    if fault == "missing_context": args["multiday_placements"] = None
    elif fault == "future_capacity": placement["capacity_known_day"] = 6
    elif fault == "bad_finish": placement["physical_finish_day"] = 7
    elif fault == "early_availability": placement["available_day"] = 7
    elif fault == "partial_work": placement["allocations"][-1] = (8, 24)
    elif fault == "unordered_work": placement["allocations"] = [(6, 25), (5, 25), (7, 25), (8, 25)]
    elif fault == "excess_first_day": placement["allocations"] = [(5, 26), (6, 24), (7, 25), (8, 25)]
    else: placement["allocations"] = [(5, 24.5), (6, 25.5), (7, 25), (8, 25)]
    with pytest.raises(ValueError, match="Multiday programme"):
        book.select(**args)
    assert book.rows == {} and book.events == []


@pytest.mark.parametrize("capacity", [-1, True, float("inf"), float("nan")])
def test_multiday_programme_rejects_invalid_capacity(capacity):
    book, args, _, _, _ = programme_case()
    args["capacity_qty"] = capacity
    with pytest.raises(ValueError, match="capacity"):
        book.select(**args)


def test_multiday_programme_integer_material_budget_matches_daily_consumption_ceils():
    book, args, _, _, _ = programme_case(ratio_a=.02, budget_a=4, available_a=4)
    row = book.select(**args)
    # Four days each consume ceil(25*.02)=1; ceil(100*.02)=2 is insufficient.
    assert row["source_budgets"][0]["allocated_qty"] == 4
    assert row["source_budgets"][0]["residual_qty"] == 0
    assert next(r for r in row["component_requirements"] if r["item_id"] == A[1])["qty"] == 4


@pytest.mark.parametrize("budget,available", [(2, 4), (4, 2)])
def test_multiday_programme_refuses_whole_lot_rounding_that_understates_daily_material(budget, available):
    book, args, _, _, _ = programme_case(ratio_a=.02, budget_a=budget, available_a=available)
    assert book.select(**args) is None


def test_multiday_programme_daily_integer_material_gate_covers_unbudgeted_BOM_components():
    book, args, _, _, _ = programme_case(extra=True)
    args["available"][C] = 2
    assert book.select(**args) is None
    args["available"][C] = 4
    row = book.select(**args)
    assert next(r for r in row["component_requirements"] if r["item_id"] == C[1])["qty"] == 4


def test_multiday_programme_does_not_change_legacy_capacity_or_integer_budget_rule():
    book, args, _, _, _ = programme_case(mode=LEGACY, ratio_a=.02, budget_a=2, available_a=2)
    assert book.select(**args) is None  # legacy requires full100 daily capacity
    args["capacity_qty"] = 100
    row = book.select(**args)
    assert row["qty"] == 100 and row["available_day"] == 8
    assert row["source_budgets"][0]["allocated_qty"] == 2
    assert "physical_finish_day" not in row and "work_allocations" not in row


def test_multiday_programme_keeps_one_promotion_schema_bound():
    _, _, payload, bom, units = programme_case()
    payload["max_promotions_per_process"] = 2
    with pytest.raises(ValueError, match="bounded policy"):
        WeeklyProductionProgramme(payload, bom_by_pair=bom, pair_uoms=units)
