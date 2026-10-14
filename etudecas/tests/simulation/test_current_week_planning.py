"""Planning revisions only: arithmetic in memory, no files or simulations."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, IndustrialComponentPlanningCalendar, IndustrialPlanningHorizonCoverage,
    LotSizing, plan_dated_requirements, reconcile_industrial_requirements,
)

PAIR = ("M-1810", "item:693055")
CURRENT = "latest_known_remaining_current_v1"
LEGACY = "freeze_previous_exclude_current_vintage"


def payload(policy=CURRENT, quantity=270):
    def row(start, qty, cell):
        return dict(period_start_day=start, period_days=7, qty=qty,
                    source_file="memory.xlsx", source_cells=cell)
    return dict(schema_version=1, origin="2025-01-01", scenario_id="memory",
        semantics="industrial_total_gross_requirements_planning_only",
        versioned_series=[dict(node_id=PAIR[0], item_id=PAIR[1], uom="UN",
            repeat_period_days=0, period_days=7, period_anchor_day=4,
            current_bucket_policy=policy, missing_future_policy="unprovided_not_observed_zero",
            versions=[dict(known_day=186, rows=[row(193, 380, "I26845")]),
                      dict(known_day=193, rows=[row(193, quantity, "I27819"), row(200, 730, "I27820")]
                           if policy == CURRENT else [row(200, 730, "I27820")])])])


def calendar(raw=None, missing=None):
    return IndustrialComponentPlanningCalendar(raw or payload(), pair_uoms={PAIR: "UN"},
        origin_date="2025-01-01", missing_period_policy=missing)


def windows(cal, day=193, end=199):
    return cal.windows(PAIR, decision_day=day, first_day=day + 1, through_day=end)


def coverage(cal):
    raw = dict(schema_version=1, origin="2025-01-01", semantics="global_source_snapshot_week_bounds",
        rows=[dict(known_day=d, first_period_start_day=d, last_period_start_day=d + 364,
                   period_days=7, source_file="memory.xlsx", source_cells=f"A{d}:G{d}",
                   present_pairs=[dict(node_id=PAIR[0], item_id=PAIR[1])]) for d in (186, 193)])
    return IndustrialPlanningHorizonCoverage(raw, calendar=cal, eligible_pairs={PAIR}, origin_date="2025-01-01")


def test_current_week_revision_270_replaces_380_only_for_six_future_days():
    raw = payload(); original = deepcopy(raw)
    revised = windows(calendar(raw))[0]
    legacy = windows(calendar(payload(LEGACY)))[0]
    assert revised.qty == pytest.approx(270 * 6 / 7)
    assert legacy.qty == pytest.approx(380 * 6 / 7)
    assert legacy.qty - revised.qty == pytest.approx(110 * 6 / 7)
    assert (revised.first_day, revised.end_day_exclusive, revised.known_day, revised.source_cells) == (194, 200, 193, "I27819")
    assert (legacy.known_day, legacy.source_cells) == (186, "I26845")
    assert raw == original


def test_current_week_midweek_has_only_three_future_days_no_repeated_consumption():
    cal = calendar()
    before = windows(cal)[0]
    after = windows(cal, day=196)[0]
    assert after.qty == pytest.approx(270 * 3 / 7)
    assert (after.first_day, after.end_day_exclusive) == (197, 200)
    assert windows(cal)[0] == before  # querying later cannot rewrite an earlier decision
    with pytest.raises(ValueError):
        cal.windows(PAIR, decision_day=196, first_day=196, through_day=199)


def test_current_week_unknown_revision_is_not_visible_before_publication():
    result = windows(calendar(), day=192)[0]
    assert (result.qty, result.known_day, result.source_cells) == (380, 186, "I26845")


def test_current_week_revision_keeps_future_week_selection_and_provenance():
    result = windows(calendar(), end=206)
    assert [(w.period_start_day, w.known_day, w.source_cells) for w in result] == [
        (193, 193, "I27819"), (200, 193, "I27820")]
    assert result[1].qty == 730


def test_current_week_missing_is_unknown_but_explicit_zero_is_a_source_value():
    raw = payload()
    raw["versioned_series"][0]["versions"][1]["rows"].pop(0)
    assert windows(calendar(raw)) == ()
    result = windows(calendar(payload(quantity=0)))
    assert len(result) == 1 and result[0].qty == 0 and result[0].source_cells == "I27819"


def test_current_week_existing_optin_missing_fallback_keeps_last_supplied_period():
    raw = payload()
    raw["versioned_series"][0]["versions"][1]["rows"].pop(0)
    result = windows(calendar(raw, missing="last_known_period_v1"))[0]
    assert result.qty == pytest.approx(380 * 6 / 7)
    assert result.known_day == 186


def test_current_week_horizon_uses_same_latest_vintage_as_source_window():
    actual, absent = coverage(calendar()).select(PAIR, decision_day=193, first_day=194, through_day=206)
    assert len(actual) == 2 and absent == ()
    assert all(w.known_day == 193 for w in actual)
    assert actual[0].qty == pytest.approx(270 * 6 / 7)


def test_current_week_horizon_absence_is_separate_not_invented_zero():
    raw = payload(); raw["versioned_series"][0]["versions"][1]["rows"].pop(0)
    actual, absent = coverage(calendar(raw)).select(PAIR, decision_day=193, first_day=194, through_day=199)
    assert actual == () and len(absent) == 1
    assert absent[0].known_day == 193 and not hasattr(absent[0], "qty")


def test_current_week_legacy_horizon_and_stock_netting_stay_unchanged():
    actual, absent = coverage(calendar(payload(LEGACY))).select(PAIR, decision_day=193, first_day=194, through_day=206)
    assert absent == ()
    assert [w.known_day for w in actual] == [186, 193]
    assert actual[0].qty == pytest.approx(380 * 6 / 7)


def test_current_week_600_firm_receipt_is_netted_once_without_new_order():
    revised = windows(calendar())
    needs, _ = reconcile_industrial_requirements([], revised, pair=PAIR,
        decision_day=193, policy="source_weekly_with_committed_floor_v1")
    firm = FirmReceipt("existing:600", 198, 600, "confirmed")
    plan = plan_dated_requirements(decision_day=193, available_qty=0, requirements=needs,
        firm_receipts=[firm], lead_days=1, lot_sizing=LotSizing(integer=True))
    assert plan.proposed_qty == 0
    assert sum(a.qty for a in plan.allocations if a.supply_id == firm.receipt_id) == pytest.approx(270 * 6 / 7)
    assert firm == FirmReceipt("existing:600", 198, 600, "confirmed")


def test_current_week_fractional_forecast_creates_only_integer_physical_UN_orders():
    needs, _ = reconcile_industrial_requirements([], windows(calendar()), pair=PAIR,
        decision_day=193, policy="source_weekly_with_committed_floor_v1")
    plan = plan_dated_requirements(decision_day=193, available_qty=0, requirements=needs,
        firm_receipts=(), lead_days=1, lot_sizing=LotSizing(integer=True))
    assert plan.proposed_qty == 232
    assert all(p.qty == int(p.qty) for p in plan.proposals)


@pytest.mark.parametrize("fault", ["past_week", "legacy_current", "unknown_policy", "no_provenance"])
def test_current_week_rejects_invalid_temporal_or_source_contract(fault):
    raw = payload(); series = raw["versioned_series"][0]
    row = series["versions"][1]["rows"][0]
    if fault == "past_week": row["period_start_day"] = 186
    elif fault == "legacy_current": series["current_bucket_policy"] = LEGACY
    elif fault == "unknown_policy": series["current_bucket_policy"] = "invented"
    else: row["source_cells"] = ""
    with pytest.raises(ValueError): calendar(raw)
