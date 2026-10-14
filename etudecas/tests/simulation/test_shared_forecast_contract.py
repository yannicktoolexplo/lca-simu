"""Known total-I candidate: independent arithmetic, entirely in memory.

These cases exercise the existing opt-in source-weekly policy, not industrial
calibration. No fixture, workbook, simulation, clock or filesystem mutation is
used. Forecast quantities may be fractional; purchases in UN remain integers.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, IndustrialComponentPlanningCalendar, IndustrialPlanningWindow,
    LotSizing, Requirement, plan_dated_requirements,
    reconcile_industrial_requirements,
)


PAIR = ("M-1430", "item:042342")
POLICY = "source_weekly_with_committed_floor_v1"


def _window(quantity, start=11, *, first=None, known=4):
    return IndustrialPlanningWindow(start, start if first is None else first,
        start + 7, quantity, known, "memory.xlsx", f"I{start}")


def _reconcile(needs, windows, *, decision=4, policy=POLICY):
    return reconcile_industrial_requirements(needs, windows, pair=PAIR,
        decision_day=decision, policy=policy)


def _total(rows):
    # Decimal representations are summed independently of production helpers.
    return sum((Fraction(str(row.qty)) for row in rows), Fraction(0))


def test_source_weekly_reproduces_042342_I420_gap_then_replaces_fixed_share_once():
    # H2 audit, first known window: no own BOM, I420=13,109,514;
    # fixed-share reconstruction=6,080,970, hence missing 7,028,544 UN.
    needs = [Requirement("external:fixed-share", 11, 6080970)]
    windows = [_window(13109514)]
    saved = deepcopy((needs, windows))
    nominal, nominal_audit = _reconcile(needs, windows, policy="separate_own_and_other_v1")
    candidate, audit = _reconcile(needs, windows)
    assert nominal == needs and nominal_audit[0]["planning_qty"] == 6080970
    assert _total(candidate) == 13109514
    assert _total(candidate) - _total(nominal) == 7028544
    assert audit[0]["source_qty"] == 13109514
    assert audit[0]["reconstructed_external_qty"] == 6080970
    assert audit[0]["committed_qty"] == 0
    # A second reconciliation replaces its generated forecasts, not adds I again.
    assert _reconcile(candidate, windows)[0] == candidate
    assert (needs, windows) == saved


def test_source_weekly_preserves_all_three_commitment_kinds_and_reserve_exactly():
    committed = [Requirement("campaign:c", 12, 20),
                 Requirement("opening-pack:p", 13, 5),
                 Requirement("opening_production:o", 14, 5)]
    reserve = Requirement("reserve:source", 11, 13)
    needs = [*committed, reserve, Requirement("derived:revocable-BOM", 15, 100),
             Requirement("external:old-estimate", 16, 40)]
    saved = deepcopy(needs)
    result, audit = _reconcile(needs, [_window(80)])
    # I80 contains the same modeled commitments30 once, leaving forecast50.
    assert _total(result) == 93
    assert all(any(row is original for row in result) for original in [*committed, reserve])
    assert not any(row.requirement_id in {"derived:revocable-BOM", "external:old-estimate"}
                   for row in result)
    assert _total(row for row in result if row.requirement_id.startswith("external:")) == 50
    assert audit[0]["own_qty"] == 130  # before replacement: committed30 + revocable100
    assert audit[0]["committed_qty"] == 30
    assert audit[0]["planning_qty"] == 80
    # This residual is not an observation of other formats: own revocable
    # forecasts were also superseded. Preserve this interpretation in reports.
    assert audit[0]["complement_qty"] == 50
    assert needs == saved


def test_source_weekly_explicit_zero_keeps_commitments_but_missing_keeps_every_need():
    committed = Requirement("campaign:c", 12, 20)
    reserve = Requirement("reserve:source", 13, 7)
    missing_own = Requirement("derived:unprovided", 20, 9)
    missing_other = Requirement("external:unprovided", 21, 8)
    backlog = Requirement("external:due-backlog", 4, 6)
    needs = [committed, reserve, Requirement("derived:revocable", 14, 40),
             Requirement("external:estimate", 15, 50), missing_own, missing_other, backlog]
    result, audit = _reconcile(needs, [_window(0)])
    assert result == [committed, reserve, missing_own, missing_other, backlog]
    assert audit[0]["committed_qty"] == audit[0]["planning_qty"] == 20
    assert audit[0]["complement_qty"] == 0
    assert _reconcile(needs, []) == (needs, [])


def test_source_weekly_avoids_max_BOM_double_count_only_on_explicit_covered_weeks():
    # Same hypothesized use forecast early by I and late by the revocable BOM.
    # Weekly max(I,BOM) would retain 100+100. I with an explicit later zero
    # supersedes that revocable forecast; an absent later week cannot do so.
    own = Requirement("derived:revocable-late", 20, 100)
    windows = [_window(100), _window(0, start=18)]
    legacy, _ = _reconcile([own], windows, policy=None)
    candidate, _ = _reconcile([own], windows)
    unknown, _ = _reconcile([own], windows[:1])
    assert float(_total(legacy)) == pytest.approx(200)
    assert _total(candidate) == 100
    assert _total(unknown) == 200 and own in unknown
    # A confirmed later need cannot be cancelled or matched across weeks.
    committed = replace(own, requirement_id="campaign:late")
    firm_candidate, _ = _reconcile([committed], windows)
    assert _total(firm_candidate) == 200 and committed in firm_candidate


def test_source_weekly_floor_preserves_dated_commitment_without_claiming_daily_I_envelope():
    committed = Requirement("opening_production:late-in-week", 17, 70)
    result, audit = _reconcile([committed], [_window(70)])
    assert result == [committed] and audit[0]["planning_qty"] == 70
    # Weekly matching does not prove coverage of the source's uniform daily
    # profile: I would represent 10/day before17 but the commitment stays17.
    assert _total(row for row in result if row.due_day < 17) == 0


def _calendar():
    def version(known, rows):
        return {"known_day": known, "rows": [dict(period_start_day=start,
            period_days=7, qty=qty, source_file="memory.xlsx", source_cells=f"v{known}!I{start}")
            for start, qty in rows]}
    payload = dict(schema_version=1, origin="2025-01-01", scenario_id="memory",
        semantics="industrial_total_gross_requirements_planning_only",
        versioned_series=[dict(node_id=PAIR[0], item_id=PAIR[1], uom="UN",
            repeat_period_days=0, period_days=7, period_anchor_day=4,
            current_bucket_policy="freeze_previous_exclude_current_vintage",
            missing_future_policy="unprovided_not_observed_zero",
            versions=[version(4, [(11, 70), (18, 140), (25, 210)]),
                      version(11, [(18, 0)]), version(18, [(25, 700)])])])
    return IndustrialComponentPlanningCalendar(payload, pair_uoms={PAIR: "UN"},
        origin_date="2025-01-01", missing_period_policy=None)


def test_source_weekly_calendar_is_causal_freezes_current_week_and_never_resurrects_omission():
    calendar = _calendar()
    assert calendar.windows(PAIR, decision_day=3, first_day=4, through_day=31) == ()
    initial = calendar.windows(PAIR, decision_day=4, first_day=5, through_day=31)
    assert [(w.period_start_day, w.qty, w.known_day) for w in initial] == [
        (11, 70, 4), (18, 140, 4), (25, 210, 4)]
    revised = calendar.windows(PAIR, decision_day=11, first_day=12, through_day=31)
    assert [(w.period_start_day, w.qty, w.known_day) for w in revised] == [
        (11, 60, 4), (18, 0, 11)]
    # At day14, three of the original seven current-week days remain: 70*3/7.
    clipped = calendar.windows(PAIR, decision_day=14, first_day=15, through_day=31)
    assert [(w.qty, w.known_day) for w in clipped] == [(30, 4), (0, 11)]
    later = calendar.windows(PAIR, decision_day=18, first_day=19, through_day=31)
    assert [(w.period_start_day, w.qty, w.known_day) for w in later] == [
        (18, 0, 11), (25, 700, 18)]


def test_source_weekly_fractional_forecasts_net_firm_receipt_once_and_order_integer_UN():
    forecasts, _ = _reconcile([], [_window(100)])
    receipt = FirmReceipt("held:existing", 25, 20, "held")
    plan = plan_dated_requirements(decision_day=4, available_qty=10,
        requirements=forecasts, firm_receipts=[receipt], lead_days=1,
        lot_sizing=LotSizing(integer=True))
    # 100 total need - 10 available - 20 already purchased = 70 new UN.
    # The20 arriving late are still firm, not repurchased to hide lateness.
    assert _total(forecasts) == 100
    assert plan.proposed_qty == 70
    assert all(row.qty == int(row.qty) for row in plan.proposals)
    allocations = [row for row in plan.allocations if row.supply_id == receipt.receipt_id]
    assert sum(row.qty for row in allocations) == pytest.approx(20)
    assert all(row.available_day == 25 and row.supply_kind == "held" for row in allocations)
    assert plan.firm_late_qty == pytest.approx(20)
    assert receipt == FirmReceipt("held:existing", 25, 20, "held")


@pytest.mark.parametrize("fault", ["future_vintage", "past_window", "overlap",
    "duplicate_identity", "negative_source", "negative_need", "missing_provenance"])
def test_source_weekly_rejects_noncausal_or_ambiguous_inputs(fault):
    needs, windows = [Requirement("derived:own", 12, 10)], [_window(70)]
    if fault == "future_vintage":
        windows[0] = replace(windows[0], known_day=5)
    elif fault == "past_window":
        windows[0] = _window(70, start=4)
    elif fault == "overlap":
        windows.append(_window(70, start=12))
    elif fault == "duplicate_identity":
        needs.append(needs[0])
    elif fault == "negative_source":
        windows[0] = _window(-1)
    elif fault == "negative_need":
        needs[0] = replace(needs[0], qty=-1)
    else:
        windows[0] = replace(windows[0], source_cells="")
    with pytest.raises(ValueError):
        _reconcile(needs, windows)


def test_source_weekly_runtime_override_is_scoped_to_042342_and_preserves_other_pairs():
    from etudecas.simulation.engine.run_first_simulation import plan_component_network
    other = ("M-1810", "item:001848")
    contexts = {pair: dict(window_days=14, fixed_floor_qty=0, target_days=0,
        safety_floor_qty=0, safety_days=0, legacy_rate=0) for pair in (PAIR, other)}
    args = dict(decision_day=4, requirements_by_pair={
        pair: [Requirement(f"external:estimate:{pair[1]}", 12, 40)] for pair in (PAIR, other)},
        available_by_pair={}, firm_receipts_by_pair={}, transport_sources_by_pair={},
        bom_by_pair={}, lead_days_by_pair={PAIR: 1, other: 1}, lot_sizing_by_pair={},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        industrial_windows_by_pair={pair: [_window(100)] for pair in (PAIR, other)},
        industrial_target_context_by_pair=contexts,
        industrial_requirement_reconciliation_policy="separate_own_and_other_v1")
    saved = deepcopy(args)
    baseline, original_needs, original_audit = plan_component_network(**args)
    candidate, needs, audit = plan_component_network(**args, industrial_purchase_source_pairs={PAIR})
    assert baseline[PAIR].proposed_qty == 40 and candidate[PAIR].proposed_qty == 100
    assert _total(needs[PAIR]) == 100
    assert audit[PAIR]["industrial_requirement_reconciliation_policy"] == POLICY
    assert candidate[other] == baseline[other]
    assert needs[other] == original_needs[other]
    assert audit[other] == original_audit[other]
    assert args == saved
