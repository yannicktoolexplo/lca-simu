"""Independent memory-only acceptance cases for candidate material policies.

The source provides20 working days, not a proved ERP stock-floor algorithm.
These cases check the chosen non-consumable floor contract, not calibration.
No workbook, disk fixture, simulation, timestamp or permission operation occurs.
"""
from copy import deepcopy
import csv
import io
import json

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, StockProtection,
    plan_dated_requirements, plan_with_stock_protection,
    IndustrialComponentPlanningCalendar, IndustrialPlanningWindow, reconcile_industrial_requirements,
)
from etudecas.simulation.engine.run_first_simulation import supplier_receipt_available_day
from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.experiments.shared_components import revision_series


def protected(needs=(), *, stock=0, firms=(), points=(), lead=10, lots=None, day=0):
    return plan_with_stock_protection(
        decision_day=day, available_qty=stock, requirements=needs,
        firm_receipts=firms, lead_days=lead, lot_sizing=lots, protection=points,
    )


def arrivals(result):
    quantities = {}
    for row in result.plan.proposals:
        quantities[row.available_day] = quantities.get(row.available_day, 0) + row.qty
    return quantities


def test_protection_persists_after_consumption_without_becoming_consumption():
    # Need100 at10, then100 at25; maintain200 after each real withdrawal.
    result = protected([Requirement("first", 10, 100), Requirement("later", 25, 100)],
        points=[StockProtection("floor", 10, 200)])
    assert arrivals(result) == {10: 300, 25: 100}
    assert result.plan.proposed_qty == 400
    assert sum(r.qty for r in result.plan.allocations) == 200
    assert {r.requirement_id for r in result.plan.allocations} == {"first", "later"}
    assert sum(r.requirement_qty for r in result.plan.balances) == 200
    assert result.plan.closing_projected_qty == 200
    checked = {r.day: r for r in result.protection}
    for day in (10, 25):
        assert checked[day].target_qty == checked[day].projected_qty == 200
        assert checked[day].shortfall_qty == 0


def test_adding_a_later_need_never_reduces_the_same_earlier_floor():
    first = Requirement("first", 10, 100)
    floor = [StockProtection("floor", 10, 200)]
    before = protected([first], points=floor)
    after = protected([first, Requirement("new-later", 25, 100)], points=floor)
    assert arrivals(before) == {10: 300}
    assert arrivals(after)[10] == 300
    assert arrivals(after)[25] == 100
    assert before.plan.closing_projected_qty == after.plan.closing_projected_qty == 200


def test_repeated_protection_checkpoints_are_not_additive_daily_demand():
    result = protected(points=[StockProtection(f"floor-{d}", d, 200) for d in (10, 11, 12)])
    assert arrivals(result) == {10: 200}
    assert result.plan.allocations == ()
    assert sum(r.requirement_qty for r in result.plan.balances) == 0
    assert result.plan.closing_projected_qty == 200
    assert result.plan.late_qty == 0


def test_a_lower_future_floor_reuses_existing_stock_instead_of_buying_twice():
    result = protected([Requirement("real-use", 20, 100)],
        points=[StockProtection("raised", 10, 200), StockProtection("released", 20, 0)])
    assert arrivals(result) == {10: 200}
    assert result.plan.proposed_qty == 200 and result.plan.closing_projected_qty == 100
    at20 = next(r for r in result.protection if r.day == 20)
    assert at20.target_qty == 0 and at20.projected_qty == 100 and at20.shortfall_qty == 0


def test_available_stock_and_existing_commitments_each_cover_the_floor_once():
    result = protected([Requirement("real-use", 10, 100)], stock=100,
        firms=[FirmReceipt("committed", 10, 200)], points=[StockProtection("floor", 10, 200)])
    assert result.plan.proposals == ()
    assert result.plan.closing_projected_qty == 200
    assert sum(r.qty for r in result.plan.allocations) == 100
    assert all(r.shortfall_qty == 0 for r in result.protection)


def test_late_firm_is_not_rebought_and_unmet_protection_is_explicit():
    firms = [FirmReceipt("late-existing", 30, 400)]
    saved = deepcopy(firms)
    result = protected([Requirement("first", 10, 100), Requirement("later", 25, 100)],
        firms=firms, points=[StockProtection("floor", 10, 200)])
    assert result.plan.proposals == () and firms == saved
    assert result.plan.late_qty == 200 and result.plan.late_qty_days == 2500
    assert result.plan.closing_projected_qty == 200
    p = {r.day: r for r in result.protection}
    assert p[10].shortfall_qty > 0 and p[25].shortfall_qty > 0
    assert p[30].shortfall_qty == 0
    assert {r.available_day for r in result.plan.allocations} == {30}


def test_protection_before_feasible_arrival_reports_gap_without_fake_receipt():
    result = protected(points=[StockProtection("floor", 1, 100)], lead=10)
    assert arrivals(result) == {10: 100}
    assert result.plan.late_qty == 0  # No real material use has been delayed.
    p = {r.day: r for r in result.protection}
    assert p[1].projected_qty == 0 and p[1].shortfall_qty == 100
    assert p[10].projected_qty == 100 and p[10].shortfall_qty == 0


def test_absent_protection_preserves_the_complete_legacy_plan():
    kwargs = dict(decision_day=0, available_qty=20,
        requirements=[Requirement("first", 3, 50), Requirement("second", 7, 50)],
        firm_receipts=[FirmReceipt("firm", 5, 60)], lead_days=2,
        lot_sizing=LotSizing(multiple=10))
    legacy = plan_dated_requirements(**kwargs)
    result = plan_with_stock_protection(**kwargs)
    assert result.plan == legacy and result.protection == ()


def test_600kg_lot_surplus_is_kept_and_covers_later_need_without_another_order():
    result = protected([Requirement("first", 10, 100), Requirement("second", 20, 100)],
        points=[StockProtection("floor", 10, 200)], lots=LotSizing(multiple=600))
    assert arrivals(result) == {10: 600}
    assert result.plan.closing_projected_qty == 400
    assert all(r.shortfall_qty == 0 for r in result.protection)


@pytest.mark.parametrize("multiple,expected", [(600, 1200), (1000, 2000)])
def test_quantity_step_is_not_a_maximum_order_capacity(multiple, expected):
    result = protected([Requirement("large", 20, 1100)], lots=LotSizing(multiple=multiple))
    assert result.plan.proposed_qty == expected
    assert arrivals(result) == {20: expected}
    assert result.plan.closing_projected_qty == expected - 1100


def test_fractional_forecasts_do_not_create_a_ghost_physical_UN_purchase():
    result = protected([Requirement(f"forecast-{i}", 10, 0.1) for i in range(30)],
        stock=3, points=[StockProtection("floor", 10, 2)], lots=LotSizing(integer=True))
    assert result.plan.proposed_qty == 2
    assert all(r.qty == int(r.qty) for r in result.plan.proposals)
    assert result.plan.closing_projected_qty == 2


def test_planning_never_mutates_physical_inputs_or_relabels_requirements():
    needs = [Requirement("use", 20, 100)]
    firms = [FirmReceipt("held", 10, 100, "held")]
    points = [StockProtection("floor", 10, 200)]
    saved = deepcopy((needs, firms, points))
    protected(needs, firms=firms, points=points)
    assert (needs, firms, points) == saved


@pytest.mark.parametrize("invalid", [None, True, -1, float("nan"), float("inf")])
def test_missing_or_invalid_protection_cannot_silently_become_zero(invalid):
    with pytest.raises(ValueError):
        protected(points=[StockProtection("floor", 10, invalid)])


@pytest.mark.parametrize("invalid_day", [True, 10.5, None])
def test_protection_date_must_be_an_explicit_integer_day(invalid_day):
    with pytest.raises(ValueError):
        protected(points=[StockProtection("floor", invalid_day, 100)])


def test_duplicate_protection_identity_is_rejected():
    with pytest.raises(ValueError):
        protected(points=[StockProtection("same", 10, 100), StockProtection("same", 20, 200)])


@pytest.mark.parametrize("physical_day,available_day", [(2, 13), (5, 14), (8, 19)])
def test_seven_working_receipt_days_are_added_once_after_physical_arrival(physical_day, available_day):
    # Origin Wednesday1Jan2025; Friday3Jan +7 Mon-Fri days =Tuesday14Jan.
    # Jan6 ->Jan15; Jan9 ->Jan20. No holiday calendar is being invented.
    assert supplier_receipt_available_day(physical_day, 7, origin_date="2025-01-01") == available_day


def test_receipt_delay_zero_keeps_the_physical_date():
    assert supplier_receipt_available_day(2, 0, origin_date="2025-01-01") == 2


def test_default_revision_mass_unit_preserves_legacy_KG_and_year_end_prorata():
    records = [
        {"known_day": 354, "day": 354, "qty": 999, "unit": "KG", "row": 1},
        {"known_day": 354, "day": 361, "qty": 70, "unit": "KG", "row": 2},
        {"known_day": 354, "day": 368, "qty": 140, "unit": "KG", "row": 3},
    ]
    result = revision_series(records, [354], "001757/1810", 0.5)
    assert result == revision_series(records, [354], "001757/1810", 0.5, output_uom="KG")
    assert result["uom"] == "KG"
    rows = result["versions"][0]["rows"]
    assert [(r["period_start_day"], r["period_days"], r["qty"]) for r in rows] == [(361, 4, 20)]
    assert rows[0]["source_cells"] == "Feuille1!I2"
    assert json.loads(rows[0]["estimation_basis"])["fraction"] == 0.5


def test_G_revision_converts_canonical_KG_once_preserving_dates_and_provenance():
    records = [
        {"known_day": 4, "day": 4, "qty": 999, "unit": "KG", "row": 10},
        {"known_day": 4, "day": 11, "qty": 600, "unit": "KG", "row": 11},
        {"known_day": 4, "day": 368, "qty": 1200, "unit": "KG", "row": 12},
        {"known_day": 4, "day": 375, "qty": 1800, "unit": "KG", "row": 13},
    ]
    saved = deepcopy(records)
    kg = revision_series(records, [4], "693055/1810", 0.25, planning_horizon_days=364)
    grams = revision_series(records, [4], "693055/1810", 0.25,
        planning_horizon_days=364, output_uom="G")
    assert records == saved and grams["uom"] == "G"
    rows = grams["versions"][0]["rows"]
    assert [(r["period_start_day"], r["period_days"], r["qty"]) for r in rows] == [
        (11, 7, 150000), (368, 7, 300000)]
    equivalent = deepcopy(grams)
    equivalent["uom"] = "KG"
    for row in equivalent["versions"][0]["rows"]:
        row["qty"] /= 1000
    assert equivalent == kg
    for row in rows:
        assert json.loads(row["estimation_basis"])["fraction"] == 0.25
    assert [r["source_cells"] for r in rows] == ["Feuille1!I11", "Feuille1!I12"]


def test_UN_revision_keeps_fractional_forecast_but_rounds_each_week_once():
    from etudecas.simulation.engine.mrp_planning import ExternalComponentDemandCalendar

    records = [
        {"known_day": 4, "day": 4, "qty": 999, "unit": "UN", "row": 1},
        {"known_day": 4, "day": 11, "qty": 25, "unit": "UN", "row": 2},
        {"known_day": 4, "day": 18, "qty": 21, "unit": "UN", "row": 3},
        {"known_day": 11, "day": 18, "qty": 31, "unit": "UN", "row": 4},
    ]
    saved = deepcopy(records)
    series = revision_series(records, [4, 11], "042342/1430", 0.5,
                             planning_horizon_days=364, output_uom="UN")
    assert records == saved
    assert [r["qty"] for v in series["versions"] for r in v["rows"]] == [13, 11, 16]
    assert [json.loads(r["estimation_basis"])["unrounded_canonical_qty"]
            for v in series["versions"] for r in v["rows"]] == [12.5, 10.5, 15.5]
    pair = ("M-1430", "item:042342")
    calendar = ExternalComponentDemandCalendar({
        "schema_version": 3, "origin": "2025-01-01", "scenario_id": "memory-unit-revisions",
        "semantics": "incremental_non_modelled_component_use", "repeat_period_days": None,
        "rows": [], "versioned_series": [series],
    }, pair_uoms={pair: "UN"}, origin_date="2025-01-01", horizon_days=1825)
    # Half-up once per week: 12.5 -> 13, then cumulative allocation over 7 days.
    assert [sum(r.qty for r in calendar.due(day).get(pair, ()))
            for day in range(11, 18)] == [1, 2, 2, 2, 2, 2, 2]
    before = calendar.requirements(decision_day=10, first_day=18, through_day=24)[pair]
    after = calendar.requirements(decision_day=11, first_day=18, through_day=24)[pair]
    assert sum(r.qty for r in before) == 11
    assert sum(r.qty for r in after) == 16  # Replaced, never added to the old eleven.
    assert all(r.qty == int(r.qty) for r in before + after)


@pytest.mark.parametrize("source_unit,output_unit", [("UN", "KG"), ("UN", "G"), ("KG", "UN")])
def test_revision_rejects_mass_to_unit_conversion(source_unit, output_unit):
    with pytest.raises(ValueError):
        revision_series([{"known_day": 4, "day": 11, "qty": 100, "unit": source_unit, "row": 2}],
                        [4], "042342/1430", 0.5, planning_horizon_days=364, output_uom=output_unit)


PAIR = ("M-1810", "item:693055")
ORIGIN_PAIR = ("SDC-1450", PAIR[1])


def supplier_planning_candidate():
    pair = ("factory", "item:shared")
    payload = {"schema_version": 1, "rows": [{
        "policy_id": "explicit-selection", "node_id": pair[0], "item_id": pair[1],
        "uom": "KG", "selected_supplier_id": "fast", "status": "candidate_not_inferred_ERP",
        "source_refs": {"offer": "FIA!F16:H16", "safety": "source30workingdays"},
    }]}
    lanes = {pair: [dict(src=supplier, lead_days=days, lead_days_mean=float(days),
                        lead_time_source="case_data_fia", lead_time_is_default=False)
                    for supplier, days in [("fast", 21), ("slow", 42)]]}
    return pair, payload, lanes


def test_supplier_planning_absent_is_inert_and_explicit_selection_keeps_21_not_max42():
    pair, payload, lanes = supplier_planning_candidate()
    saved = deepcopy((payload, lanes))
    assert engine.resolve_supplier_planning_policies(None, execution_mode="historical",
        lanes_by_dest_item=lanes, item_unit_map={pair[1]: "KG"}) == {}
    policies = engine.resolve_supplier_planning_policies(payload, execution_mode="dated",
        lanes_by_dest_item=lanes, item_unit_map={pair[1]: "KG"})
    chosen = next(lane for lane in lanes[pair] if lane["src"] == policies[pair]["selected_supplier_id"])
    assert engine.supplier_delivery_lead_days(chosen, None, mode="source", stochastic=False) == 21
    # Jan22 + 13 Mon-Fri processing days = Feb10, versus Mar3 for the slow offer.
    assert supplier_receipt_available_day(21, 13, origin_date="2025-01-01") == 40
    assert supplier_receipt_available_day(42, 13, origin_date="2025-01-01") == 61
    assert (payload, lanes) == saved


@pytest.mark.parametrize("fault", ["unknown_supplier", "unit", "missing_source", "duplicate",
                                 "unknown_field", "mode", "invented_delivery", "protection"])
def test_supplier_planning_candidate_rejects_ambiguous_or_unsupported_parameters(fault):
    pair, payload, lanes = supplier_planning_candidate()
    row = payload["rows"][0]
    if fault == "unknown_supplier": row["selected_supplier_id"] = "absent"
    elif fault == "unit": row["uom"] = "UN"
    elif fault == "missing_source": row["source_refs"] = {}
    elif fault == "duplicate": payload["rows"].append(deepcopy(row))
    elif fault == "unknown_field": row["safety_override"] = 0
    elif fault == "invented_delivery": lanes[pair][0]["lead_time_source"] = "assumed"
    elif fault == "protection": row["protection_mode"] = "replace_stock"
    with pytest.raises(ValueError):
        engine.resolve_supplier_planning_policies(payload,
            execution_mode="historical" if fault == "mode" else "dated",
            lanes_by_dest_item=lanes, item_unit_map={pair[1]: "KG"})


def test_supplier_floor_differs_from_coverage_without_rebuying_initial_held_stock():
    pair = ("factory", "item:shared")
    kwargs = dict(decision_day=0, requirements_by_pair={pair: [Requirement("use", 50, 300)]},
        available_by_pair={pair: 300}, firm_receipts_by_pair={pair: [FirmReceipt("initial-held", 10, 300, "held")]},
        transport_sources_by_pair={}, bom_by_pair={}, lead_days_by_pair={pair: 40},
        lot_sizing_by_pair={pair: LotSizing(minimum=300, multiple=300)},
        reserve_targets_by_pair={pair: 300}, coverage_days_by_pair={pair: 120}, active_campaigns_by_pair={})
    saved = deepcopy(kwargs)
    legacy, _, _ = engine.plan_component_network(**kwargs)
    # 600 committed minus 300 use leaves300: no extra order for a300 floor.
    maintained, requirements, audits = engine.plan_component_network(**kwargs,
        protection_by_pair={pair: [StockProtection("source-safety", 1, 300)]})
    assert legacy[pair].proposals == maintained[pair].proposals == ()
    assert maintained[pair].closing_projected_qty == 300
    assert audits[pair]["reserve_requirement_qty"] == 0
    assert sum(row.qty for row in requirements[pair]) == 300
    # Same initial held300, but a400 floor needs one300 lot: physical use stays300.
    raised, requirements, _ = engine.plan_component_network(**kwargs,
        protection_by_pair={pair: [StockProtection("source-safety", 1, 400)]})
    assert raised[pair].proposed_qty == 300
    assert raised[pair].closing_projected_qty == 600
    assert sum(row.qty for row in requirements[pair]) == 300
    assert kwargs == saved


def coverage_floor_network(*, target=50, floor=15, stock=25, firms=(), lead=3, combined=True):
    pair = ("factory", "item:shared")
    return engine.plan_component_network(decision_day=0,
        requirements_by_pair={pair: [Requirement("early", 2, 10), Requirement("later", 5, 20)]},
        available_by_pair={pair: stock}, firm_receipts_by_pair={pair: firms},
        transport_sources_by_pair={}, bom_by_pair={}, lead_days_by_pair={pair: lead},
        lot_sizing_by_pair={pair: LotSizing()}, reserve_targets_by_pair={pair: target},
        coverage_days_by_pair={pair: 5}, active_campaigns_by_pair={},
        protection_by_pair={pair: [StockProtection("source-safety", 1, floor)]},
        coverage_protection_pairs={pair} if combined else None)


def test_coverage_floor_uses_maximum_at_original_dates_without_double_counting():
    pair = ("factory", "item:shared")
    plans, needs, audits = coverage_floor_network()
    assert plans[pair].proposed_qty == 25  # 30 real use + max(15,20) -25 stock.
    assert [(p.release_day, p.available_day, p.qty) for p in plans[pair].proposals] == [(0, 3, 5), (2, 5, 20)]
    assert [(p.day, p.minimum_qty) for p in audits[pair]["protection_points"]] == [(1, 15), (3, 20)]
    assert audits[pair]["dated_coverage_complement_qty"] == 20
    assert audits[pair]["reserve_requirement_qty"] == 0
    assert sum(n.qty for n in needs[pair]) == 30
    assert all(not n.requirement_id.startswith("reserve:") for n in needs[pair])
    # Adding C+S would wrongly buy40, including an extra15 units.
    assert plans[pair].proposed_qty != 30 + 20 + 15 - 25


def test_coverage_below_safety_preserves_previous_floor_plan():
    pair = ("factory", "item:shared")
    old, _, _ = coverage_floor_network(target=35, combined=False)
    new, _, _ = coverage_floor_network(target=35, combined=True)
    assert old[pair] == new[pair] and new[pair].proposed_qty == 20


def test_coverage_with_zero_safety_keeps_its_nominal_arrival_date():
    pair = ("factory", "item:shared")
    plans, _, audits = coverage_floor_network(floor=0)
    assert plans[pair].proposed_qty == 25
    assert [(p.day, p.minimum_qty) for p in audits[pair]["protection_points"]] == [(1, 0), (3, 20)]


@pytest.mark.parametrize("lead,expected", [(0, [(0, 20), (1, 20)]), (1, [(1, 20)])])
def test_coverage_floor_zero_or_one_day_lead_never_lowers_or_duplicates_protection(lead, expected):
    pair = ("factory", "item:shared")
    plans, _, audits = coverage_floor_network(lead=lead)
    assert [(p.day, p.minimum_qty) for p in audits[pair]["protection_points"]] == expected
    assert plans[pair].proposed_qty == 25


def test_coverage_floor_nets_initial_held_commitment_once():
    pair = ("factory", "item:shared")
    firms = [FirmReceipt("initial-held", 3, 25, "held")]
    saved = deepcopy(firms)
    plans, _, audits = coverage_floor_network(firms=firms)
    assert plans[pair].proposals == ()
    assert plans[pair].closing_projected_qty == 20
    assert firms == saved and audits[pair]["reserve_requirement_qty"] == 0


def test_coverage_floor_recovers_observed_708073_day93_release_pressure():
    # Minimal reconstruction of the observed release arithmetic, not a replay
    # of all future weeks: stock4416.778811, C4406.584316, due128, safety2000.
    pair = ("factory", "item:shared")
    stock, complement, by_arrival = 4416.778811, 4406.584316, 716.981738
    kwargs = dict(decision_day=93, requirements_by_pair={pair: [Requirement("covered-use", 128, by_arrival)]},
        available_by_pair={pair: stock}, firm_receipts_by_pair={}, transport_sources_by_pair={}, bom_by_pair={},
        lead_days_by_pair={pair: 35}, lot_sizing_by_pair={pair: LotSizing()},
        reserve_targets_by_pair={pair: complement + by_arrival}, coverage_days_by_pair={pair: 120},
        active_campaigns_by_pair={}, protection_by_pair={pair: [StockProtection("source-safety", 94, 2000)]})
    old, _, _ = engine.plan_component_network(**kwargs)
    new, _, audits = engine.plan_component_network(**kwargs, coverage_protection_pairs={pair})
    assert old[pair].proposals == ()
    assert len(new[pair].proposals) == 1
    proposal = new[pair].proposals[0]
    assert (proposal.release_day, proposal.available_day) == (93, 128)
    assert proposal.qty == pytest.approx(706.787243)
    assert audits[pair]["dated_coverage_complement_qty"] == pytest.approx(complement)
    assert engine.mrp_purchase_order_quantity(proposal.qty, 5000, 5000, binding=True, uom="KG") == 5000


def industrial_window(quantity=100, first=11, end=18):
    return IndustrialPlanningWindow(11, first, end, quantity, 4, "Flow.xlsx", "I2")


def test_industrial_total_replaces_future_estimate_after_weekly_own_not_daily_maximum():
    own = Requirement("derived:core", 11, 100)
    estimated = Requirement("external:old", 12, 80)
    saved = [own, estimated]
    result, audit = reconcile_industrial_requirements(saved, [industrial_window()], pair=("site", "item:x"), decision_day=4)
    assert result == [own] and saved == [own, estimated]
    assert audit[0]["source_qty"] == audit[0]["own_qty"] == audit[0]["planning_qty"] == 100
    assert audit[0]["reconstructed_external_qty"] == 80 and audit[0]["complement_qty"] == 0
    # A daily maximum would incorrectly plan100+6*(100/7)=185.714.
    assert sum(row.qty for row in result) == 100


def test_industrial_partial_week_keeps_prior_consumption_out_of_future_complement():
    # Source100/7, three future days remain; only20 own units are still due.
    window = industrial_window(100 * 3 / 7, first=15, end=18)
    needs = [Requirement("derived:own", 16, 20), Requirement("external:old", 17, 50),
             Requirement("external:already-due", 12, 9)]
    result, audit = reconcile_industrial_requirements(needs, [window], pair=("site", "item:x"), decision_day=14)
    assert audit[0]["complement_qty"] == pytest.approx(100 * 3 / 7 - 20)
    assert sum(row.qty for row in result if row.due_day > 14) == pytest.approx(100 * 3 / 7)
    assert next(row for row in result if row.requirement_id == "external:already-due").qty == 9


def test_industrial_explicit_zero_preserves_own_excess_and_backlog_missing_preserves_estimate():
    needs = [Requirement("campaign:committed", 11, 20), Requirement("external:estimated", 12, 80),
             Requirement("external:backlog", 4, 7)]
    zero, audit = reconcile_industrial_requirements(needs, [industrial_window(0)], pair=("site", "item:x"), decision_day=4)
    assert zero == [needs[0], needs[2]]
    assert audit[0]["source_qty"] == 0 and audit[0]["source_excess_own_qty"] == 20
    missing, missing_audit = reconcile_industrial_requirements(needs, [], pair=("site", "item:x"), decision_day=4)
    assert missing == needs and missing_audit == []


def test_industrial_calendar_is_causal_retains_zero_and_fractional_UN_forecasts():
    series = revision_series([
        {"known_day": 4, "day": 11, "qty": 12.5, "unit": "KG", "row": 2},
        {"known_day": 4, "day": 18, "qty": 0, "unit": "KG", "row": 3},
        {"known_day": 11, "day": 18, "qty": 21, "unit": "KG", "row": 4},
    ], [4, 11], "055703/1810", 1, planning_horizon_days=364)
    series["uom"] = "UN"  # Deliberately fractional forecast; no physical calendar.
    pair = ("M-1810", "item:055703")
    payload = dict(schema_version=1, origin="2025-01-01", scenario_id="memory",
        semantics="industrial_total_gross_requirements_planning_only", versioned_series=[series])
    saved = deepcopy(payload)
    calendar = IndustrialComponentPlanningCalendar(payload, pair_uoms={pair: "UN"}, origin_date="2025-01-01")
    assert calendar.windows(pair, decision_day=3, first_day=4, through_day=24) == ()
    known = calendar.windows(pair, decision_day=4, first_day=5, through_day=24)
    assert [(w.qty, w.known_day) for w in known] == [(12.5, 4), (0, 4)]
    revised = calendar.windows(pair, decision_day=12, first_day=13, through_day=24)
    assert [(w.qty, w.known_day) for w in revised] == [(pytest.approx(12.5 * 5 / 7), 4), (21, 11)]
    assert payload == saved


def test_industrial_network_reconciles_after_BOM_and_recomputes_targets_without_double_order():
    component, product = ("factory", "item:component"), ("factory", "item:product")
    window = IndustrialPlanningWindow(11, 11, 18, 100, 4, "Flow.xlsx", "I2")
    kwargs = dict(decision_day=4,
        requirements_by_pair={product: [Requirement("customer", 18, 100)],
                              component: [Requirement("external:old", 12, 80)]},
        available_by_pair={component: 0, product: 0},
        firm_receipts_by_pair={component: [FirmReceipt("initial-held", 11, 100, "held")]},
        transport_sources_by_pair={}, bom_by_pair={product: [(component, 1)]},
        lead_days_by_pair={product: 7, component: 7}, lot_sizing_by_pair={},
        reserve_targets_by_pair={component: 1000}, coverage_days_by_pair={component: 14}, active_campaigns_by_pair={},
        protection_by_pair={component: [StockProtection("safety", 5, 100)]},
        industrial_windows_by_pair={component: [window]}, industrial_target_context_by_pair={component: {
            "window_days": 14, "fixed_floor_qty": 0, "target_days": 14,
            "safety_floor_qty": 0, "safety_days": 7, "legacy_rate": 100}})
    saved = deepcopy(kwargs)
    plans, requirements, audits = engine.plan_component_network(**kwargs)
    audit = audits[component]
    assert audit["industrial_source_requirement_qty"] == audit["industrial_own_requirement_qty"] == 100
    assert audit["industrial_planning_complement_qty"] == 0
    assert audit["industrial_target_rate_qty"] == pytest.approx(100 / 14)
    assert audit["protection_points"][0].minimum_qty == 50
    assert sum(row.qty for row in requirements[component]) == 100
    assert plans[component].proposed_qty == 50  # Firm100 covers use100, only floor50 missing.
    assert plans[component].closing_projected_qty == 50
    assert kwargs == saved


def test_industrial_source_beyond_target_window_keeps_legacy_target_and_protection():
    pair = ("factory", "item:component")
    kwargs = dict(decision_day=4, requirements_by_pair={pair: [Requirement("derived:own", 11, 15)]},
        available_by_pair={}, firm_receipts_by_pair={}, transport_sources_by_pair={}, bom_by_pair={},
        lead_days_by_pair={pair: 7}, lot_sizing_by_pair={}, reserve_targets_by_pair={pair: 1000},
        coverage_days_by_pair={pair: 14}, active_campaigns_by_pair={},
        protection_by_pair={pair: [StockProtection("safety", 5, 100)]}, coverage_protection_pairs={pair})
    _, _, old_audit = engine.plan_component_network(**kwargs)
    _, _, new_audit = engine.plan_component_network(**kwargs,
        industrial_windows_by_pair={pair: [IndustrialPlanningWindow(200, 200, 207, 100, 4, "Flow.xlsx", "I9")]},
        industrial_target_context_by_pair={pair: {"window_days": 14, "fixed_floor_qty": 0, "target_days": 14,
            "safety_floor_qty": 0, "safety_days": 7, "legacy_rate": 100}})
    assert new_audit[pair]["industrial_target_rate_qty"] == 100
    assert new_audit[pair]["industrial_core_rate"] is None
    assert new_audit[pair]["protection_points"] == old_audit[pair]["protection_points"]
    assert new_audit[pair]["dated_coverage_complement_qty"] == 985


def internal_policy():
    return {"schema_version": 1, "rows": [{
        "policy_id": "candidate", "node_id": PAIR[0], "item_id": PAIR[1],
        "source_node_id": ORIGIN_PAIR[0], "uom": "G", "transfer_multiple_qty": 600000,
        "receipt_days": 7, "receipt_calendar": "monday_friday", "protection_mode": "dated_stock_floor",
        "source_refs": {"safety": "20working days, candidate floor interpretation"},
        "status": "candidate_not_inferred_ERP"}]}


def resolve_policy(payload, *, mode="dated"):
    return engine.resolve_internal_component_policies(payload, execution_mode=mode,
        lanes_by_dest_item={PAIR: [{"src": ORIGIN_PAIR[0], "lead_days": 70}]},
        item_unit_map={PAIR[1]: "G"})


def test_internal_policy_absent_preserves_legacy_and_present_is_narrowly_scoped():
    assert resolve_policy(None, mode="historical") == {}
    data = internal_policy()
    saved = deepcopy(data)
    result = resolve_policy(data)
    assert set(result) == {PAIR}
    assert result[PAIR]["transfer_multiple_qty"] == 600000
    assert data == saved


@pytest.mark.parametrize("fault", ["other_item", "other_source", "KG_unit", "lot50000", "receipt_calendar", "historical", "duplicate"])
def test_internal_policy_cannot_generalize_or_silently_change_source_conventions(fault):
    data = internal_policy()
    if fault == "other_item": data["rows"][0]["item_id"] = "item:001757"
    elif fault == "other_source": data["rows"][0]["source_node_id"] = "M-1430"
    elif fault == "KG_unit": data["rows"][0]["uom"] = "KG"
    elif fault == "lot50000": data["rows"][0]["transfer_multiple_qty"] = 50000
    elif fault == "receipt_calendar": data["rows"][0]["receipt_calendar"] = "calendar_days"
    elif fault == "duplicate": data["rows"].append(deepcopy(data["rows"][0]))
    with pytest.raises(ValueError):
        resolve_policy(data, mode="historical" if fault == "historical" else "dated")


def transferred_material(*, parent_quantities=(700000,), transfer_qty=600000):
    ledger = engine.LotLedger(enabled=True)
    for quantity in parent_quantities:
        ledger.seed_opening_stock(day=0, stock={ORIGIN_PAIR: quantity}, item_unit_map={PAIR[1]: "G"})
    parent = next(iter(ledger.lots))
    allocations = ledger.consume(day=0, node_id=ORIGIN_PAIR[0], item_id=PAIR[1], qty=transfer_qty,
        event_type="lane_ship", uom="G", shipment_id="SHIP1", source_id="lane1",
        planned_order_id="ORDER1", departure_day=0, arrival_day=2)
    raw = {"order_type": "internal_transfer_delivery", "mrp_order_id": "ORDER1",
        "node_id": PAIR[0], "item_id": PAIR[1], "src_node_id": ORIGIN_PAIR[0],
        "edge_id": "lane1", "shipment_id": "SHIP1", "departure_day": 0,
        "receipt_qty": transfer_qty, "physical_delivery_day": 2, "arrival_day": 13,
        "parent_allocations": allocations, "source_file": "graph.meta.internal_component_policy",
        "source_row": "candidate"}
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={PAIR[1]: "G"})
    calendar.add_order(raw)
    return ledger, calendar, raw, parent


def test_internal_delivery_keeps_parent_genealogy_and_one_physical_receipt_G_then_I():
    ledger, calendar, raw, parent = transferred_material()
    original = deepcopy(raw)
    assert calendar.receive_physical(1, ledger=ledger) == {}
    assert ledger.pair_balance(node_id=ORIGIN_PAIR[0], item_id=PAIR[1]) == 100000
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 0
    assert calendar.receive_physical(2, ledger=ledger) == {PAIR: 600000}
    child = calendar.by_marker["ORDER1"]["lot_id"]
    assert child != parent and calendar.held_by_pair[PAIR] == 600000
    assert len(ledger.genealogy_rows) == 1
    link = ledger.genealogy_rows[0]
    assert (link["parent_lot_id"], link["child_lot_id"], link["parent_qty"], link["child_qty"]) == (
        parent, child, 600000, 600000)
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=3, node_id=PAIR[0], item_id=PAIR[1], qty=1,
            event_type="production_consume", uom="G")
    calendar.release("ORDER1", 13, 600000, ledger=ledger)
    assert calendar.held_by_pair[PAIR] == 0 and len(ledger.lots) == 2
    assert [(r["event_type"], r["day"], r["qty"]) for r in ledger.event_rows if r["lot_id"] == child] == [
        ("lane_receipt", 2, 600000), ("stock_availability_hold", 2, 600000),
        ("stock_availability_release", 13, 600000)]
    ledger.consume(day=13, node_id=PAIR[0], item_id=PAIR[1], qty=100000,
        event_type="production_consume", uom="G")
    assert ledger.pair_balance(node_id=PAIR[0], item_id=PAIR[1]) == 500000
    assert raw == original


@pytest.mark.parametrize("fault", ["duplicate_order", "duplicate_G", "early_I", "wrong_I_quantity"])
def test_internal_delivery_rejects_duplicate_or_invalid_transition_without_mutation(fault):
    ledger, calendar, raw, _ = transferred_material()
    calendar.receive_physical(2, ledger=ledger)
    before = deepcopy((ledger.event_rows, ledger.genealogy_rows, ledger.lots, calendar.held_by_pair))
    with pytest.raises(ValueError):
        if fault == "duplicate_order": calendar.add_order(raw)
        elif fault == "duplicate_G": calendar.receive_physical(2, ledger=ledger)
        elif fault == "early_I": calendar.release("ORDER1", 12, 600000, ledger=ledger)
        else: calendar.release("ORDER1", 13, 600001, ledger=ledger)
    assert (ledger.event_rows, ledger.genealogy_rows, ledger.lots, calendar.held_by_pair) == before


def native_internal_evidence(*, horizon=20):
    ledger, calendar, raw, _ = transferred_material()
    calendar.receive_physical(2, ledger=ledger)
    if horizon > 13:
        calendar.release("ORDER1", 13, 600000, ledger=ledger)
    order = {**raw, "order_type": "lane_release", "planned_receipt_qty": "600000",
        "available_day": "13", "actual_physical_receipt_day": "2",
        "actual_available_day": "13" if horizon > 13 else ""}
    return order, ledger


@pytest.mark.parametrize("horizon", [10, 20])
def test_native_internal_audit_accepts_actual_child_lot_and_future_availability(horizon):
    from etudecas.testing.independent_review import Evidence, audit_internal_transfer_availability
    order, ledger = native_internal_evidence(horizon=horizon)
    evidence = Evidence()
    assert audit_internal_transfer_availability([order], ledger.event_rows, ledger.genealogy_rows,
        horizon, {PAIR}, evidence) == 1
    assert all(r["failed"] == 0 for r in evidence.checks.values())


@pytest.mark.parametrize("fault,failed_check", [
    ("second_receipt", "internal_transfer_single_physical"),
    ("wrong_I", "internal_transfer_availability_date"),
    ("new_lot_at_I", "internal_transfer_same_lot_G_I"),
    ("unlinked_parent", "internal_transfer_transported_parents"),
    ("orphan_hold", "internal_transfer_no_orphan_availability"),
])
def test_native_internal_audit_rejects_broken_date_or_material_identity_in_memory(fault, failed_check):
    from etudecas.testing.independent_review import Evidence, audit_internal_transfer_availability
    order, ledger = native_internal_evidence()
    events, links = deepcopy(ledger.event_rows), deepcopy(ledger.genealogy_rows)
    receipt = next(r for r in events if r["event_type"] == "lane_receipt")
    release = next(r for r in events if r["event_type"] == "stock_availability_release")
    if fault == "second_receipt": events.append(deepcopy(receipt))
    elif fault == "wrong_I": release["day"] = 12
    elif fault == "new_lot_at_I": release["lot_id"] = "NONEXISTENT"
    elif fault == "unlinked_parent": links[0]["parent_lot_id"] = "OTHER"
    else:
        orphan = deepcopy(next(r for r in events if r["event_type"] == "stock_availability_hold"))
        orphan["source_id"] = "NO_ORDER"
        events.append(orphan)
    evidence = Evidence()
    audit_internal_transfer_availability([order], events, links, 20, {PAIR}, evidence)
    assert evidence.checks[failed_check]["failed"] > 0


def test_internal_held_lot_events_export_in_memory_with_the_real_writer_columns():
    _, ledger = native_internal_evidence()
    fields = engine.lot_trace_csv_fields(dated_availability=True)
    for kind, rows in (("events", ledger.event_rows), ("genealogy", ledger.genealogy_rows)):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=fields[kind])
        writer.writeheader()
        writer.writerows(rows)
        exported = list(csv.DictReader(io.StringIO(stream.getvalue())))
        assert len(exported) == len(rows)
        assert all(r.get("shipment_id", "") == str(original.get("shipment_id", ""))
                   for r, original in zip(exported, rows))


@pytest.mark.parametrize("parents", [(600000, 600000), (400000, 400000, 400000)])
def test_native_internal_audit_understands_total_child_quantity_on_each_parent_link(parents):
    from etudecas.testing.independent_review import Evidence, audit_internal_transfer_availability
    ledger, calendar, raw, _ = transferred_material(parent_quantities=parents, transfer_qty=1200000)
    calendar.receive_physical(2, ledger=ledger)
    calendar.release("ORDER1", 13, 1200000, ledger=ledger)
    order = {**raw, "order_type": "lane_release", "planned_receipt_qty": "1200000",
             "available_day": "13", "actual_physical_receipt_day": "2", "actual_available_day": "13"}
    assert len(ledger.genealogy_rows) == len(parents)
    assert [r["parent_qty"] for r in ledger.genealogy_rows] == list(parents)
    assert all(r["child_qty"] == 1200000 for r in ledger.genealogy_rows)
    evidence = Evidence()
    audit_internal_transfer_availability([order], ledger.event_rows, ledger.genealogy_rows, 20, {PAIR}, evidence)
    assert all(r["failed"] == 0 for r in evidence.checks.values())
    # A real missing parent quantity must still fail; only the interpretation
    # of the repeated child total changed. No disk files are altered.
    damaged_links = deepcopy(ledger.genealogy_rows)
    damaged_links[0]["parent_qty"] -= 1
    invalid = Evidence()
    audit_internal_transfer_availability([order], ledger.event_rows, damaged_links, 20, {PAIR}, invalid)
    assert invalid.checks["internal_transfer_genealogy_parent_quantity"]["failed"] == 1


class NoSupplierLeadDraw:
    """Any accidental random operation would fail this memory-only oracle."""
    def random(self):
        raise AssertionError("A source delivery must not draw a random value")

    gammavariate = gauss = triangular = lambda self, *args: self.random()


def fia_delivery_lane(days=35):
    return {"lead_days": days, "lead_days_mean": float(days), "lead_stages": 4,
            "lead_time_type": "erlang", "lead_time_source": "case_data_fia",
            "lead_time_is_default": False, "delay_step_limit": 999}


def test_source_delivery_keeps_35_FIA_days_and_applies_receipt_9_days_only_after_G():
    lane = fia_delivery_lane()
    saved = deepcopy(lane)
    delivery = engine.supplier_delivery_lead_days(lane, NoSupplierLeadDraw(),
        mode="source", stochastic=True)
    assert delivery == 35 and lane == saved
    # 1 January +35 calendar days =5 February; +9 Monday-Friday days =18 February.
    assert supplier_receipt_available_day(delivery, 9, origin_date="2025-01-01") == 48
    # The comparison option must not also remove the existing prudence buffer:
    # ceil(35 +1.65 *35/sqrt(4)) =64, versus35 under the older global flag.
    assert engine.lead_time_cover_days(lane, True, "erlang") == 64
    assert engine.lead_time_cover_days(lane, False, "erlang") == 35


@pytest.mark.parametrize("days", [14, 21, 28, 35, 42, 56, 84, 120, 154])
def test_source_delivery_is_common_to_all_explicit_FIA_references_without_RNG(days):
    for distribution in ("erlang", "industrial"):
        for stochastic in (False, True):
            assert engine.supplier_delivery_lead_days(fia_delivery_lane(days), NoSupplierLeadDraw(),
                mode="source", stochastic=stochastic, distribution_mode=distribution) == days


@pytest.mark.parametrize("field,value", [
    ("lead_time_source", "default"), ("lead_time_source", None), ("lead_time_is_default", True),
    ("lead_days_mean", None), ("lead_days_mean", True), ("lead_days_mean", 0),
    ("lead_days_mean", -1), ("lead_days_mean", 35.5), ("lead_days_mean", float("nan")),
    ("lead_days_mean", float("inf")),
])
def test_source_delivery_refuses_unproven_or_invalid_reference_instead_of_defaulting(field, value):
    lane = fia_delivery_lane()
    lane[field] = value
    with pytest.raises(ValueError, match="explicit positive whole-day FIA"):
        engine.supplier_delivery_lead_days(lane, NoSupplierLeadDraw(), mode="source", stochastic=True)


def test_sampled_supplier_delivery_preserves_the_real_legacy_draw_and_rounding():
    class FixedGamma:
        calls = []

        def gammavariate(self, shape, scale):
            self.calls.append((shape, scale))
            return 81.2

    rng = FixedGamma()
    assert engine.supplier_delivery_lead_days(fia_delivery_lane(), rng,
        mode="sampled", stochastic=True, distribution_mode="erlang") == 82
    assert rng.calls == [(4, 8.75)]
    assert engine.supplier_delivery_lead_days(fia_delivery_lane(), NoSupplierLeadDraw(),
        mode="sampled", stochastic=False) == 35


def test_unknown_supplier_delivery_mode_is_rejected():
    with pytest.raises(ValueError, match="sampled or source"):
        engine.supplier_delivery_lead_days(fia_delivery_lane(), NoSupplierLeadDraw(),
            mode="unrecognized", stochastic=True)


def empirical_policy_memory():
    return {"schema_version": 1, "origin_date": "2025-01-01", "min_samples": 5,
            "observations": [{"id": str(i), "known_day": 10+i, "delta_days": i-2,
                              "lower_days": i-5, "upper_days": i+1, "observed_end_day": 10+i}
                             for i in range(6)]}


def test_empirical_delivery_has_no_future_leak_and_no_erlang_fallback():
    policy = engine.resolve_empirical_supplier_delivery_policy(empirical_policy_memory(), origin_date="2025-01-01")
    class NoDraw:
        def randrange(self, *args):
            raise AssertionError("Insufficient history must not sample")
    days, evidence = engine.empirical_supplier_delivery_draw(fia_delivery_lane(), NoDraw(),
        policy=policy, decision_day=13, stochastic=True)
    assert days == 35 and evidence["empirical_pool_size"] == 4
    assert evidence["empirical_status"] == "fallback_insufficient_history"
    days, evidence = engine.empirical_supplier_delivery_draw(fia_delivery_lane(), NoDraw(),
        policy=policy, decision_day=100, stochastic=False)
    assert days == 35 and evidence["empirical_status"] == "deterministic"


def test_empirical_delivery_sample_records_source_identity_and_separate_receipt():
    class LastKnown:
        def randrange(self, n):
            assert n == 5  # sixth observation is only known tomorrow
            return n-1
    policy = empirical_policy_memory()
    days, evidence = engine.empirical_supplier_delivery_draw(fia_delivery_lane(), LastKnown(),
        policy=policy, decision_day=14, stochastic=True)
    assert days == 37 and evidence["empirical_sample_id"] == "4"
    assert evidence["empirical_known_day"] == 14 and evidence["empirical_delta_days"] == 2
    # Arrival day 51 = Friday21February; 1 processing workday -> Monday24February J54.
    assert supplier_receipt_available_day(14+days, 1, origin_date="2025-01-01") == 54


def test_empirical_delivery_clips_only_negative_duration_and_reports_it():
    class First:
        def randrange(self, n):
            return 0
    policy = empirical_policy_memory()
    policy["observations"][0].update(delta_days=-50, lower_days=-56, upper_days=-44)
    days, evidence = engine.empirical_supplier_delivery_draw(fia_delivery_lane(), First(),
        policy=policy, decision_day=100, stochastic=True)
    assert days == 1 and evidence["empirical_unclipped_lead_days"] == -15
    assert evidence["empirical_status"] == "sampled_clipped_at_one_day"


@pytest.mark.parametrize("mutation", ["duplicate", "future_photo", "float_days", "bad_interval", "small_pool", "wrong_origin"])
def test_empirical_policy_rejects_invalid_or_unavailable_evidence(mutation):
    policy = empirical_policy_memory()
    if mutation == "duplicate": policy["observations"][1]["id"] = "0"
    elif mutation == "future_photo": policy["observations"][0]["observed_end_day"] = 20
    elif mutation == "float_days": policy["observations"][0]["delta_days"] = float("nan")
    elif mutation == "bad_interval": policy["observations"][0]["lower_days"] = 50
    elif mutation == "small_pool": policy["min_samples"] = 1
    elif mutation == "wrong_origin": policy["origin_date"] = "2026-01-01"
    with pytest.raises(ValueError):
        engine.resolve_empirical_supplier_delivery_policy(policy, origin_date="2025-01-01")


def test_explicit_sourcing_audit_never_claims_legacy_30_70_quotas_or_mutates_inputs():
    legacy = {"item_id": "item:001848", "mrp_share": 0.3, "mrp_rank": 2,
              "mrp_share_basis": "legacy_fixed_split", "release_qty": 6000}
    saved = deepcopy(legacy)
    assert engine.sourcing_allocation_audit_fields(legacy, explicit_policy=False) == {}
    fields = engine.sourcing_allocation_audit_fields(legacy, explicit_policy=True)
    assert fields == {"mrp_share": "", "mrp_rank": "",
                      "mrp_share_basis": "explicit_primary_backup_no_fixed_quota"}
    assert legacy == saved
    exported = {**legacy, **fields}
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(exported))
    writer.writeheader()
    writer.writerow(exported)
    row = next(csv.DictReader(io.StringIO(stream.getvalue())))
    assert row["mrp_share"] == row["mrp_rank"] == ""
    assert row["release_qty"] == "6000"


def test_opening_source_order_is_not_relabelled_as_a_new_sourcing_decision():
    opening = {"order_type": "opening_purchase_order", "mrp_share": 0.7,
               "release_qty": 4000, "source_row": 9, "arrival_day": 48}
    fields = engine.sourcing_allocation_audit_fields(opening, explicit_policy=True)
    assert fields == {"mrp_share": "", "mrp_share_basis": "opening_source_order_no_model_quota"}
    assert opening["source_row"] == 9 and opening["arrival_day"] == 48


def test_gaillac_site_functions_preserve_physical_state_and_legacy_role():
    from etudecas.knowledge_graph.update_supply_graph_from_case_data import annotate_upstream_site

    node = {"id": "SDC-1450", "type": "factory", "attrs": {"source_sheet": "Acteurs"},
            "inventory": {"states": [{"item_id": "item:021081", "initial": 1142100, "uom": "KG"}]},
            "processes": [{"id": "proc:MAKE_773474", "inputs": [{"item_id": "item:021081"}]}]}
    stock, processes = deepcopy(node["inventory"]), deepcopy(node["processes"])
    annotate_upstream_site(node)
    assert node["type"] == "factory" and node["id"] == "SDC-1450"
    assert node["attrs"]["site_functions"] == ["receiving", "storage", "manufacturing", "shipping"]
    assert node["attrs"]["physical_site_code"] == "1450"
    assert node["attrs"]["site_role"] == "internal_upstream_semi_finished"
    assert node["attrs"]["source_sheet"] == "Acteurs"
    assert node["inventory"] == stock and node["processes"] == processes
    once = deepcopy(node)
    annotate_upstream_site(node)
    assert node == once


def test_gaillac_annotation_does_not_relabel_other_sites_or_create_flows():
    from etudecas.knowledge_graph.update_supply_graph_from_case_data import annotate_upstream_site, make_supplier_node

    for identifier in ["DC-1450", "M-1810", "SDC-VD0951020A"]:
        node = {"id": identifier, "type": "distribution_center", "inventory": {"states": []}}
        saved = deepcopy(node)
        annotate_upstream_site(node)
        assert node == saved
    created = make_supplier_node("D1450", "SDC-1450", None)
    assert created["attrs"]["physical_site_code"] == "1450"
    assert created["inventory"]["states"] == [] and created["processes"] == []


def prospective_memory(*, needs=(), decision=0, days=1, through=20, known=None,
                       fixed=0, legacy=20, activation=3, complement=0):
    from etudecas.simulation.engine.mrp_planning import prospective_stock_protection
    return prospective_stock_protection(decision_day=decision, requirements=needs,
        source_working_days=days, origin_weekday=2, forecast_through_day=through,
        covered_days=range(decision + 1, through + 1) if known is None else known,
        fixed_floor_qty=fixed, legacy_floor_qty=legacy,
        coverage_activation_day=activation, coverage_complement_qty=complement)


def test_prospective_window_excludes_current_day_includes_weekend_and_last_day():
    # At Friday31January close (J30), one working day ends Monday3February J33.
    needs = [Requirement(str(d), d, q) for d,q in [(30,99),(31,5),(32,7),(33,11),(34,100)]]
    saved = deepcopy(needs)
    points, audit = prospective_memory(needs=needs, decision=29, days=1, through=40, activation=35)
    first = audit['prospective_checkpoints'][30]
    assert first == dict(safety_window_end_day=33, safety_window_need_qty=23,
                         safety_window_covered=1, safety_source_floor_qty=23)
    assert points[0].day == 30 and audit['prospective_safety_tomorrow_qty'] == 23
    assert needs == saved


@pytest.mark.parametrize('days', [0,1,7,10,30])
def test_prospective_calendar_matches_independent_date_iteration_across_month(days):
    from datetime import date, timedelta
    needs = [Requirement(str(d), d, d + 0.25) for d in range(1,100)]
    points, audit = prospective_memory(needs=needs, days=days, through=99, activation=3)
    origin = date(2025,1,1)
    for when, row in audit['prospective_checkpoints'].items():
        end_date = origin + timedelta(days=when)
        count = 0
        while count < days:
            end_date += timedelta(days=1)
            if end_date.weekday() < 5:
                count += 1
        end = (end_date - origin).days
        assert row['safety_window_end_day'] == end
        complete = end <= 99
        assert row['safety_window_covered'] == int(complete)
        if complete:
            expected = sum(r.qty for r in needs if when < r.due_day <= end)
            assert row['safety_window_need_qty'] == expected
        else:
            assert row['safety_window_need_qty'] == ''
            assert row['safety_source_floor_qty'] == 20


def test_prospective_explicit_zero_is_known_missing_day_and_tail_use_legacy():
    points, known = prospective_memory(needs=(), fixed=5, legacy=20, known=range(1,21))
    assert known['prospective_safety_basis'] == 'dated_known_window'
    assert known['prospective_safety_tomorrow_qty'] == 5
    _, missing = prospective_memory(needs=(), fixed=5, legacy=20, known=range(3,21))
    assert missing['prospective_safety_basis'] == 'fallback_incomplete_forecast'
    assert missing['prospective_safety_tomorrow_qty'] == 20
    assert points[-1].minimum_qty == 20
    assert known['prospective_safety_dated_days'] + known['prospective_safety_fallback_days'] == 20
    _, empty = prospective_memory(needs=(), days=0, fixed=5, legacy=20, known=[])
    assert empty['prospective_safety_tomorrow_qty'] == 5  # Empty window requires no source dates.


def test_prospective_floor_coverage_maximum_and_held_commitment_counted_once():
    needs = [Requirement('use',4,80)]
    points, audit = prospective_memory(needs=needs, days=1, through=10,
        fixed=10, legacy=20, activation=2, complement=15)
    result = protected(needs, stock=0, firms=[FirmReceipt('held',2,100,'held')], points=points, lead=2)
    assert result.plan.proposals == ()
    assert result.plan.closing_projected_qty == 20
    assert sum(r.qty for r in result.plan.allocations) == 80
    assert max(p.minimum_qty for p in points) == 80  # Not80+15.
    assert points[0].day == 1


def test_prospective_default_network_unchanged_and_empty_coverage_is_legacy():
    pair = ('factory','item:shared')
    kwargs = dict(decision_day=0, requirements_by_pair={pair:[Requirement('use',5,30)]},
        available_by_pair={pair:25}, firm_receipts_by_pair={}, transport_sources_by_pair={}, bom_by_pair={},
        lead_days_by_pair={pair:3}, lot_sizing_by_pair={}, reserve_targets_by_pair={pair:50},
        coverage_days_by_pair={pair:5}, active_campaigns_by_pair={},
        protection_by_pair={pair:[StockProtection('source',1,15)]}, coverage_protection_pairs={pair})
    saved = deepcopy(kwargs)
    old = engine.plan_component_network(**kwargs)
    explicit_none = engine.plan_component_network(**kwargs, prospective_safety_by_pair=None)
    assert old == explicit_none and kwargs == saved
    new = engine.plan_component_network(**kwargs, prospective_safety_by_pair={pair:dict(
        source_working_days=1, origin_weekday=2, forecast_through_day=10,
        covered_days=[], fixed_floor_qty=0)})
    assert new[0] == old[0] and new[1] == old[1]
    assert new[2][pair]['prospective_safety_tomorrow_qty'] == 15
    assert new[2][pair]['prospective_safety_dated_days'] == 0


def test_prospective_after_BOM_and_total_source_reconciliation_keeps_requirements_once():
    component, product = ('factory','item:component'), ('factory','item:product')
    kwargs = dict(decision_day=4, requirements_by_pair={product:[Requirement('customer',18,100)],
        component:[Requirement('external:old',12,80)]}, available_by_pair={}, firm_receipts_by_pair={},
        transport_sources_by_pair={}, bom_by_pair={product:[(component,1)]},
        lead_days_by_pair={product:7,component:7}, lot_sizing_by_pair={},
        reserve_targets_by_pair={component:0}, coverage_days_by_pair={component:14}, active_campaigns_by_pair={},
        protection_by_pair={component:[StockProtection('source',5,50)]}, coverage_protection_pairs={component},
        industrial_windows_by_pair={component:[IndustrialPlanningWindow(11,11,18,100,4,'Flow.xlsx','I2')]},
        industrial_target_context_by_pair={component:dict(window_days=14,fixed_floor_qty=0,target_days=0,
            safety_floor_qty=0,safety_days=7,legacy_rate=50)},
        prospective_safety_by_pair={component:dict(source_working_days=5,origin_weekday=2,
            forecast_through_day=25,covered_days=range(5,26),fixed_floor_qty=0)})
    plans, requirements, audits = engine.plan_component_network(**kwargs)
    assert sum(r.qty for r in requirements[component]) == 100
    assert audits[component]['prospective_safety_tomorrow_qty'] == 100  # Monday6Jan throughMonday13Jan.
    assert audits[component]['industrial_planning_complement_qty'] == 0


@pytest.mark.parametrize('shortage,expected', [(299,300),(300,300),(305,600),(600,600),(601,900)])
def test_prospective_keeps_existing_physical_purchase_rounding(shortage,expected):
    assert engine.mrp_purchase_order_quantity(shortage,10000,300,binding=True,uom='KG') == expected


def test_prospective_external_coverage_retains_explicit_zero_and_causal_vintage():
    from etudecas.simulation.engine.mrp_planning import ExternalComponentDemandCalendar
    series = revision_series([dict(known_day=4,day=11,qty=0,unit='KG',row=2),
        dict(known_day=11,day=18,qty=70,unit='KG',row=3)], [4,11], '055703/1810',1,planning_horizon_days=364)
    pair = ('M-1810','item:055703')
    payload = dict(schema_version=3,origin='2025-01-01',scenario_id='memory',
        semantics='incremental_non_modelled_component_use',rows=[],versioned_series=[series])
    cal = ExternalComponentDemandCalendar(payload,pair_uoms={pair:'KG'},origin_date='2025-01-01',horizon_days=800)
    assert cal.covered_days(pair,decision_day=3,first_day=4,through_day=24) == frozenset()
    assert cal.covered_days(pair,decision_day=4,first_day=5,through_day=24) == frozenset(range(11,18))
    assert cal.requirements(decision_day=4,first_day=5,through_day=24) == {}
    assert cal.covered_days(pair,decision_day=12,first_day=13,through_day=24) == frozenset(range(13,25))
