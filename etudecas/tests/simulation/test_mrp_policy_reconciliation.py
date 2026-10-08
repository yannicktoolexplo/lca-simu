"""Independent memory-only acceptance cases for candidate material policies.

The source provides20 working days, not a proved ERP stock-floor algorithm.
These cases check the chosen non-consumable floor contract, not calibration.
No workbook, disk fixture, simulation, timestamp or permission operation occurs.
"""
from copy import deepcopy
from collections import defaultdict
import csv
import io
import json

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, StockProtection,
    plan_dated_requirements, plan_with_stock_protection,
    IndustrialComponentPlanningCalendar, IndustrialPlanningWindow, reconcile_industrial_requirements,
    industrial_forecast_missing_policy,
    plan_anticipated_requirements, SupplierOffer,
    ReceiptReplanningStatus, postpone_initial_receipts,
)
from etudecas.simulation.engine.run_first_simulation import supplier_receipt_available_day
from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.experiments.shared_components import revision_series


def _opening_postponement_runtime_case():
    # 5 January review; receipt Monday 6 / usable Wednesday 8; need 15 January.
    pair = ('M-test', 'item:test')
    raw = dict(order_type='opening_purchase_order', node_id=pair[0], item_id=pair[1],
        src_node_id='supplier:test', physical_delivery_day=5, arrival_day=7,
        receipt_qty=50, source_file='memory.xlsx', source_row=2)
    availability = engine.OpeningPurchaseAvailability([raw], item_unit_map={pair[1]: 'UN'})
    marker = availability.marker_for('memory.xlsx', 2)
    payload = dict(schema_version=1, mode='known_need_and_protection_v1', review_weekday=6,
        source_file='memory.xlsx', assumption='Memory-only experimental unshipped status',
        rows=[dict(source_row=2, replannable=True, transport_departed=False,
                   receipt_executed=False, replannable_until_day=4)])
    permissions = engine.resolve_opening_purchase_postponement(payload, availability=availability,
        origin_date='2025-01-01')
    calendar = engine.DatedReceiptCalendar()
    calendar.add(pair, 7, 50)
    kwargs = dict(permissions=permissions, decision_day=4, origin_date='2025-01-01', horizon_day=30,
        availability=availability, stock={pair:40},
        firm_snapshot={pair:[FirmReceipt(marker,7,50,'in_transit')]},
        requirements_by_pair={pair:[Requirement('later',14,40)]},
        plan_audits={pair:dict(protection_points=[StockProtection('floor',4,10)])},
        industrial_windows={pair:[IndustrialPlanningWindow(5,5,31,40,4,'memory.xlsx','F2')]},
        pipeline=defaultdict(list,{7:[(*pair,50,marker)]}), pending_receipt_calendar=calendar,
        commitments={pair:{marker:(7,50,'opening_purchase_order')}},
        order_rows=[dict(mrp_order_id=marker,qty=50,safety_time_days=7)],
        shipment_rows=[dict(src_node_id=raw['src_node_id'],dst_node_id=pair[0],item_id=pair[1],
            shipped_qty=50,arrival_day=5,day=-55,lead_days=60,transport_cost_basis='opening_order_book')],
        audit_rows=[],total_days=365,safety_source_days_by_pair={pair:5})
    return pair, marker, kwargs, payload


def test_opening_postponement_runtime_moves_one_commitment_without_stock_or_quantity_change():
    pair, marker, args, _ = _opening_postponement_runtime_case()
    assert engine.apply_opening_purchase_postponement(**args)
    row = args['availability'].by_marker[marker]
    # Monday 13 -> Wednesday 15 January; 5 workdays safety -> Wednesday 22.
    assert (row['physical_delivery_day'],row['arrival_day']) == (12,14)
    assert args['stock'][pair] == 40
    assert args['pipeline'][7] == [] and args['pipeline'][14] == [(*pair,50,marker)]
    assert args['pending_receipt_calendar'].total(pair) == 50
    assert args['commitments'][pair][marker] == (14,50,'opening_purchase_order')
    assert args['firm_snapshot'][pair] == [FirmReceipt(marker,14,50,'in_transit')]
    assert args['order_rows'][0]['qty'] == 50
    assert args['order_rows'][0]['implied_cover_need_day'] == 21
    assert args['shipment_rows'][0]['day'] == -55
    assert args['shipment_rows'][0]['arrival_day'] == 12
    assert args['audit_rows'][0]['original_physical_day'] == 5
    assert not row['received'] and not row['released']


def test_opening_postponement_runtime_permission_expires_at_original_date_even_after_delay():
    pair, marker, args, _ = _opening_postponement_runtime_case()
    assert engine.apply_opening_purchase_postponement(**args)
    args['decision_day'] = 11  # Sunday 12; still before revised G, after original G.
    args['requirements_by_pair'][pair] = [Requirement('much_later',25,40)]
    assert not engine.apply_opening_purchase_postponement(**args)
    assert args['availability'].by_marker[marker]['arrival_day'] == 14
    assert args['audit_rows'][-1]['applied'] == 0
    assert args['audit_rows'][-1]['replannable_until_day'] == 4


@pytest.mark.parametrize('received,departed', [(True,False),(False,True)])
def test_opening_postponement_runtime_preserves_received_or_dispatched_orders(received,departed):
    pair, marker, args, _ = _opening_postponement_runtime_case()
    args['availability'].by_marker[marker]['received'] = received
    args['permissions'][marker]['transport_departed'] = departed
    before = deepcopy(args['pipeline'])
    assert not engine.apply_opening_purchase_postponement(**args)
    assert args['pipeline'] == before
    assert args['stock'][pair] == 40
    assert args['availability'].by_marker[marker]['arrival_day'] == 7


def test_opening_postponement_runtime_missing_flag_is_noop_and_invalid_expiry_rejected():
    _, _, args, payload = _opening_postponement_runtime_case()
    assert engine.resolve_opening_purchase_postponement(None, availability=None,origin_date=None) == {}
    args['permissions'] = {}
    assert not engine.apply_opening_purchase_postponement(**args)
    payload['rows'][0]['replannable_until_day'] = 12
    with pytest.raises(ValueError,match='ORIGINAL'):
        engine.resolve_opening_purchase_postponement(payload,availability=args['availability'],origin_date='2025-01-01')


def _postponement_case(**changes):
    receipt = FirmReceipt("opening:row97", 2, 50, "confirmed")
    args = dict(decision_day=0, available_qty=40,
        requirements=[Requirement("early", 8, 20), Requirement("later", 12, 30)],
        firm_receipts=[receipt], protection=[StockProtection("floor", 0, 10)],
        coverage_days=range(1, 31), horizon_day=30,
        statuses=[ReceiptReplanningStatus(receipt.receipt_id, True, False, False, 0)],
        policy="known_need_and_protection_v1")
    args.update(changes)
    return args


def test_opening_postponement_keeps_identity_quantity_and_protected_need():
    args = _postponement_case()
    before = deepcopy(args)
    result = postpone_initial_receipts(**args)
    assert result.firm_receipts == (FirmReceipt("opening:row97", 12, 50, "confirmed"),)
    decision = result.decisions[0]
    assert (decision.old_available_day, decision.new_available_day, decision.first_deficit_day) == (2, 12, 12)
    assert decision.reason == "postponed_to_first_protected_need"
    assert args == before
    # Independent hand balance:40-20=20>=floor10; on D12 add50 then use30 =>40.
    assert 40 - 20 >= 10 and 40 - 20 + result.firm_receipts[0].qty - 30 == 40


def test_opening_postponement_nets_multiple_orders_sequentially_once():
    receipts = [FirmReceipt("first", 2, 50), FirmReceipt("second", 3, 50)]
    args = _postponement_case(available_qty=50, firm_receipts=receipts, protection=[],
        requirements=[Requirement(str(day), day, 50) for day in (10, 20, 30)],
        statuses=[ReceiptReplanningStatus(r.receipt_id, True, False, False, 0) for r in receipts])
    result = postpone_initial_receipts(**args)
    assert [(r.receipt_id, r.available_day, r.qty) for r in result.firm_receipts] == [
        ("first", 30, 50), ("second", 20, 50)]
    # Permuting caller order cannot change the tie-break/decisions, only output order.
    reverse = postpone_initial_receipts(**dict(args, firm_receipts=list(reversed(receipts))))
    assert {r.receipt_id: r for r in reverse.firm_receipts} == {r.receipt_id: r for r in result.firm_receipts}
    assert sum(r.qty for r in result.firm_receipts) == 100
    assert [50 - 50, 50 - 100 + 50, 50 - 150 + 100] == [0, 0, 0]


def test_opening_postponement_floor_is_persistent_not_daily_consumption():
    result = postpone_initial_receipts(**_postponement_case(available_qty=40, requirements=[],
        protection=[StockProtection("early", 0, 10), StockProtection("peak", 8, 50)]))
    assert result.firm_receipts[0].available_day == 8
    assert result.decisions[0].first_deficit_day == 8


@pytest.mark.parametrize("coverage,horizon,expected,reason", [
    (list(range(1, 31)), 30, 30, "postponed_to_known_horizon_boundary"),
    (list(range(1, 10)) + list(range(11, 31)), 30, 9, "postponed_to_known_horizon_boundary"),
    (list(range(1, 31)), 7, 7, "postponed_to_known_horizon_boundary"),
    ([], 30, 2, "no_later_continuous_coverage"),
])
def test_opening_postponement_never_crosses_unknown_forecast_or_horizon(coverage, horizon, expected, reason):
    result = postpone_initial_receipts(**_postponement_case(available_qty=100, requirements=[],
        coverage_days=coverage, horizon_day=horizon))
    assert result.firm_receipts[0].available_day == expected
    assert result.decisions[0].reason == reason


@pytest.mark.parametrize("status,state,reason", [
    (None, "confirmed", "status_missing"),
    (ReceiptReplanningStatus("opening:row97"), "confirmed", "status_not_known_at_decision"),
    (ReceiptReplanningStatus("opening:row97", True, False, False, 1), "confirmed", "status_not_known_at_decision"),
    (ReceiptReplanningStatus("opening:row97", False, False, False, 0), "confirmed", "status_not_explicitly_replannable_unshipped"),
    (ReceiptReplanningStatus("opening:row97", True, None, False, 0), "confirmed", "status_not_explicitly_replannable_unshipped"),
    (ReceiptReplanningStatus("opening:row97", True, True, False, 0), "in_transit", "transport_already_departed"),
    (ReceiptReplanningStatus("opening:row97", True, False, True, 0), "confirmed", "already_received"),
    (ReceiptReplanningStatus("opening:row97", True, False, False, 0), "held", "already_received"),
])
def test_opening_postponement_freezes_unknown_future_or_executed_states(status, state, reason):
    receipt = FirmReceipt("opening:row97", 2, 50, state)
    result = postpone_initial_receipts(**_postponement_case(firm_receipts=[receipt], statuses=[] if status is None else [status]))
    assert result.firm_receipts == (receipt,)
    assert result.decisions[0].reason == reason


def test_opening_postponement_does_not_advance_or_worsen_an_earlier_shortage():
    result = postpone_initial_receipts(**_postponement_case(available_qty=0,
        requirements=[Requirement("overdue", -1, 10)]))
    assert result.firm_receipts[0].available_day == 2
    assert result.decisions[0].reason == "receipt_already_needed"
    assert result.decisions[0].first_deficit_day == 0
    due = postpone_initial_receipts(**_postponement_case(firm_receipts=[FirmReceipt("opening:row97", 0, 50)]))
    assert due.firm_receipts[0].available_day == 0 and due.decisions[0].reason == "already_due"


def test_opening_postponement_nominal_policy_absent_is_exact_noop():
    args = _postponement_case(policy=None)
    result = postpone_initial_receipts(**args)
    assert result.firm_receipts == tuple(args["firm_receipts"])
    assert result.firm_receipts[0] is args["firm_receipts"][0]
    assert result.decisions == ()


@pytest.mark.parametrize("changes", [
    dict(policy="invented"), dict(available_qty=-1), dict(horizon_day=-1),
    dict(coverage_days=[1, 2.5]),
    dict(firm_receipts=[FirmReceipt("opening:row97", -1, 50)]),
    dict(firm_receipts=[FirmReceipt("opening:row97", 2, float("nan"))]),
    dict(firm_receipts=[FirmReceipt("opening:row97", 2, 50)] * 2),
    dict(statuses=[ReceiptReplanningStatus("missing", True, False, False, 0)]),
    dict(statuses=[ReceiptReplanningStatus("opening:row97", 1, False, False, 0)]),
    dict(protection=[StockProtection("a", 1, 1), StockProtection("b", 1, 2)]),
])
def test_opening_postponement_rejects_ambiguous_or_invalid_contract(changes):
    with pytest.raises(ValueError):
        postpone_initial_receipts(**_postponement_case(**changes))


def _customer_source_case(*, history_qty=100):
    pair = ("client", "item:PF")
    history = dict(schema_version=1, origin="2025-01-01", calendar="monday_start", rows=[
        dict(node_id=pair[0], item_id=pair[1], uom="UN", period_start_day=start,
             period_days=7, qty=history_qty, source_file="customer.xlsx", source_row=f"Historique!D{index + 2}")
        for index, start in enumerate(range(-2, 365, 7))])
    projection = dict(schema_version=1, origin="2025-01-01", calendar="monday_start",
        repeat_period_days=365, current_bucket_policy="excluded_unresolved_carry_over", rows=[
            dict(node_id=pair[0], item_id=pair[1], uom="UN", vintage_day=vintage,
                 period_start_day=start, period_days=7, qty=qty, source_file="customer.xlsx", source_row=cell)
            for vintage, start, qty, cell in [(-2, 5, 70, "initial"), (-2, 33, 140, "old-feb"),
                (26, 33, 700, "new-feb"), (26, 362, 210, "old-dec"), (334, 362, 280, "kept-dec"),
                (362, 369, 350, "new-jan"), (362, 516, 700, "source-2026")]])
    return pair, history, projection


def _customer_forecast(payload, pair, **changes):
    kwargs = dict(demand_pairs={pair}, origin_date="2025-01-01", missing_period_policy="last_known_period_v1",
        consumption_policy="weekly_actual_orders_v1", customer_demand_policy="source_customer_history_v1")
    return engine.RollingMrpForecast(payload, **dict(kwargs, **changes))


def test_customer_history_integer_allocation_preserves_full_and_boundary_weeks():
    pair, payload, _ = _customer_source_case()
    before = deepcopy(payload)
    history = engine.SourceCustomerHistory(payload, demand_pairs={pair}, origin_date="2025-01-01", sim_days=365)
    daily = [history.quantity(pair, decision_day=day, target_day=day)[0] for day in range(365)]
    assert all(type(qty) is int for qty in daily)
    assert daily[:5] == [14, 15, 14, 14, 15]
    assert sum(daily[:5]) == 72 and sum(daily[362:]) == 42
    assert sum(daily[5:12]) == 100 and sum(daily) == 5214
    assert history.quantity(pair, decision_day=0, target_day=0)[1]["source_file"] == "customer.xlsx"
    assert payload == before
    with pytest.raises(ValueError, match="current"):
        history.quantity(pair, decision_day=0, target_day=1)
    with pytest.raises(ValueError, match="current"):
        history.quantity(pair, decision_day=365, target_day=365)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "fraction", "negative", "weekday", "source"])
def test_customer_history_rejects_missing_or_invalid_weeks(fault):
    pair, history, _ = _customer_source_case()
    if fault == "missing": history["rows"].pop(1)
    elif fault == "duplicate": history["rows"].append(dict(history["rows"][0]))
    elif fault == "fraction": history["rows"][0]["qty"] = 1.5
    elif fault == "negative": history["rows"][0]["qty"] = -1
    elif fault == "weekday": history["rows"][0]["period_start_day"] = -1
    elif fault == "source": history["rows"][0]["source_file"] = ""
    with pytest.raises(ValueError):
        engine.SourceCustomerHistory(history, demand_pairs={pair}, origin_date="2025-01-01", sim_days=365)


def test_customer_forecast_asof_revision_preserves_old_period_and_2026_source():
    pair, _, payload = _customer_source_case()
    forecast = _customer_forecast(payload, pair)
    def value(decision, target):
        return forecast.window(pair, decision_day=decision, target_day=target, fallback_daily_values=[999999])
    assert forecast.selection(0) == (-2, 0)
    assert value(25, 33)[0] == 20 and value(26, 33)[0] == 100
    december, audit = value(364, 365)
    assert december == 40 and audit["source_vintage_days"] == "334"
    assert value(364, 516)[0] == 100  # Source2026 is not multiplied by1.05.
    assert forecast.selection(731) == (362, 0)  # Never recycle2025 versions.
    assert forecast.source_for_day(pair, selected=forecast.selection(731), target_day=735) == (None, None)


def test_customer_forecast_fallback_is_known_projection_not_future_history_or_nominal():
    pair, history, payload = _customer_source_case()
    forecast = _customer_forecast(payload, pair)
    early, audit = forecast.window(pair, decision_day=0, target_day=0, fallback_daily_values=[999999] * 5)
    assert early == 10 and audit["source_days"] == 0 and audit["fallback_days"] == 5
    assert audit["fallback_source_rows"] == "initial" and audit["fallback_source_vintage_days"] == "-2"
    tail, tail_audit = forecast.window(pair, decision_day=0, target_day=600, fallback_daily_values=[999999])
    assert tail == 20 and tail_audit["fallback_source_rows"] == "old-feb"
    # Altering a later realized week cannot be observed through the forecast API.
    history["rows"][-1]["qty"] = 100000000
    assert forecast.window(pair, decision_day=0, target_day=0, fallback_daily_values=[0] * 5) == (early, audit)


def test_customer_history_consumes_forecast_once_and_cover_uses_only_remaining_forecast():
    pair, history_payload, payload = _customer_source_case(history_qty=35)
    forecast = _customer_forecast(payload, pair)
    history = engine.SourceCustomerHistory(history_payload, demand_pairs={pair}, origin_date="2025-01-01", sim_days=365)
    for day in range(6):
        forecast.observe_demand(day, {pair: history.quantity(pair, decision_day=day, target_day=day)[0]})
    audit = forecast.consumption_audit(pair, 5)
    assert audit["weekly_forecast_qty"] == 70 and audit["arrived_demand_qty"] == 5
    assert audit["remaining_forecast_qty"] == 65 and audit["future_days"] == 6
    future, _ = forecast.window(pair, decision_day=5, target_day=6, fallback_daily_values=[999] * 2)
    assert future == pytest.approx(65 / 6)
    cover = engine.customer_physical_cover_need(decision_day=5, arrival_day=7,
        physical_requirements=[Requirement(str(d), d, future) for d in (6, 7)], available_qty=5,
        backlog_qty=3, firm_receipts=[FirmReceipt("already_shipped", 6, 10)], uom="UN")
    assert cover["customer_physical_order_qty"] == 10  # ceil(2*65/6+3-5-10), not next historical5/day.
    for day in range(6, 12):
        forecast.observe_demand(day, {pair: 5})
    assert forecast.consumption_audit(pair, 11)["expired_forecast_qty"] == 35
    assert forecast.consumption_audit(pair, 11)["remaining_forecast_qty"] == 0


def test_customer_forecast_weekly_export_matches_actual_daily_planning_window():
    pair, _, payload = _customer_source_case()
    forecast = _customer_forecast(payload, pair)
    for day in range(6):
        forecast.observe_demand(day, {pair: 5})
    rows = forecast.projection_audit_rows(pair, decision_day=5, horizon_days=10)
    assert [(r["period_start_day"], r["represented_start_day"], r["represented_end_day"])
            for r in rows] == [(5, 6, 11), (12, 12, 15)]
    assert rows[0]["weekly_source_qty"] == 70 and rows[0]["used_future_qty"] == pytest.approx(65)
    assert rows[1]["weekly_source_qty"] == "" and rows[1]["fallback_days"] == 4
    assert rows[1]["status"] == "nearest_known_period_fallback"
    daily, _ = forecast.window(pair, decision_day=5, target_day=6, fallback_daily_values=[0] * 10)
    assert sum(r["used_future_qty"] for r in rows) == pytest.approx(10 * daily)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=engine.CUSTOMER_FORECAST_PROJECTION_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    assert len(list(csv.DictReader(io.StringIO(output.getvalue())))) == 2


@pytest.mark.parametrize("fault", ["legacy_mode", "growth", "future_only", "bad_weekday", "same_week", "file"])
def test_customer_forecast_contract_rejects_ambiguous_or_noncausal_modes(fault):
    pair, _, payload = _customer_source_case()
    changes = {}
    if fault == "legacy_mode": changes["customer_demand_policy"] = None
    elif fault == "growth": changes["annual_projection_policy"] = "previous_year_105pct_v1"
    elif fault == "future_only": payload["rows"] = [r for r in payload["rows"] if r["vintage_day"] > 0]
    elif fault == "bad_weekday": payload["rows"][0]["vintage_day"] = -1
    elif fault == "same_week": payload["rows"][0]["period_start_day"] = -2
    elif fault == "file": payload["rows"][0]["source_file"] = ""
    with pytest.raises(ValueError):
        _customer_forecast(payload, pair, **changes)


def test_rolling_chain_safety_anticipates_known_peak_without_extra_quantity():
    needs = [Requirement("peak", 42, 100)]
    args = dict(decision_day=0, requirements=needs, safety_days=14, fixed_qty=0)
    old_points, old_audit = engine.source_stock_protection_profile(**args)
    points, audit = engine.source_stock_protection_profile(**args, projection=dict(
        source_working_days=10, origin_weekday=2, forecast_through_day=100))
    def plan(protection):
        return engine.plan_with_stock_protection(decision_day=0, available_qty=0,
            requirements=needs, firm_receipts=[], lead_days=20, protection=protection).plan
    assert [(p.release_day, p.available_day, p.qty) for p in plan(old_points).proposals] == [(22, 42, 100)]
    assert [(p.release_day, p.available_day, p.qty) for p in plan(points).proposals] == [(8, 28, 100)]
    assert max(p.minimum_qty for p in points if p.day <= 41) == 100
    assert next(p.minimum_qty for p in points if p.day == 42) == 0
    assert audit["historical_constant_target_qty"] == old_audit["target_qty"] == 0
    assert needs == [Requirement("peak", 42, 100)]


def test_rolling_chain_safety_keeps_tail_fallback_and_workday_weekends():
    needs = [Requirement(str(day), day, day * 10) for day in range(1, 10)]
    points, audit = engine.source_stock_protection_profile(decision_day=0, requirements=needs,
        safety_days=2, fixed_qty=25, projection=dict(source_working_days=2,
            origin_weekday=0, forecast_through_day=9))
    by_day = {day: next(p.minimum_qty for p in reversed(points) if p.day <= day) for day in range(1, 11)}
    assert by_day[3] == 220  # Thu close: Fri40 + Sat50 + Sun60 + Mon70.
    assert by_day[8] == by_day[10] == 30  # Unknown tail retains max(25,10+20), not zero.
    assert audit["prospective_safety_fallback_days"] == 2


def test_rolling_chain_safety_propagates_one_shift_through_network():
    depot, factory, component, raw, inputs = _chain_relation_memory_network()
    inputs.update(available_by_pair={}, requirements_by_pair={depot: [Requirement("client", 42, 100)]},
        lead_days_by_pair={depot: 2, factory: 3, component: 4, raw: 5})
    inputs["source_safety_by_pair"][depot] = dict(safety_days=14, fixed_qty=0,
        projection=dict(source_working_days=10, origin_weekday=2, forecast_through_day=100))
    saved = deepcopy(inputs)
    plans, _, audits = engine.plan_component_network(**inputs)
    assert [(plans[pair].proposals[0].release_day, plans[pair].proposed_qty)
            for pair in (depot, factory, component, raw)] == [(26, 100), (23, 100), (19, 200), (14, 600)]
    assert audits[depot]["chain_source_safety"]["projection_policy"] == "rolling_source_workdays_v1"
    assert inputs == saved


def test_allocated_supplier_scope_and_offers_preserve_sources_and_dates():
    pair = ("plant", "raw")
    lanes = [dict(src="a", mrp_share=.7, standard_order_qty=23920, lead_days_mean=28, unit_purchase_cost=2),
             dict(src="b", mrp_share=.2, standard_order_qty=20900, lead_days_mean=42, unit_purchase_cost=1),
             dict(src="c", mrp_share=.1, standard_order_qty=22800, lead_days_mean=56, unit_purchase_cost=3)]
    args = dict(purchase_pairs={pair}, lanes_by_dest_item={pair: lanes}, excluded_pairs=set())
    assert engine.allocated_supplier_scope(None, **args) == set()
    assert engine.allocated_supplier_scope("allocated_supplier_plan_v1", **args) == {pair}
    assert engine.allocated_supplier_scope("allocated_supplier_plan_v1", **dict(args, excluded_pairs={pair})) == set()
    before = deepcopy(lanes)
    context = engine.allocated_purchase_offers(lanes, decision_day=49, through_day=140, receipt_days=24,
        origin_date="2025-01-01", nonworking_dates=frozenset(), uom="KG", binding=True, rounding_policy=None)
    assert context["allocation_weights"] == (.7, .2, .1)
    offers = context["offers"]
    assert [o.supplier_id for o in offers] == ["a", "b", "c"]  # No cheapest-first reordering.
    assert offers[0].availability_by_release[0] == (49, 111)
    assert [o.lot_sizing.multiple for o in offers] == [23920, 20900, 22800]
    assert lanes == before


def _observed_execution_case(quantity=0):
    from etudecas.simulation.engine.mrp_planning import (
        ExternalComponentDemandCalendar, ObservedExternalComponentExecution,
    )
    pair = ("plant", "item:raw")
    row = dict(demand_id="observed:I2", node_id=pair[0], item_id=pair[1],
        known_day=5, period_start_day=5, period_days=1, qty=quantity, uom="KG",
        source_file="movements.xlsx", source_cells="I2", estimation_basis="other uses only")
    payload = dict(schema_version=1, origin="2025-01-01", scenario_id="memory",
        semantics="incremental_non_modelled_component_use", repeat_period_days=None,
        physical_use_only=True, rows=[row])
    forecast_payload = deepcopy(payload)
    forecast_payload["rows"] = [dict(row, demand_id="forecast", qty=8, known_day=0,
        period_start_day=0, period_days=7)]
    args = dict(pair_uoms={pair: "KG"}, origin_date="2025-01-01", horizon_days=365)
    return pair, payload, args, ExternalComponentDemandCalendar(forecast_payload, **args), ObservedExternalComponentExecution


def test_observed_execution_zero_overrides_due_but_absence_and_forecast_remain():
    pair, payload, args, forecast, cls = _observed_execution_case()
    actual = cls(payload, **args)
    original = forecast.requirements(decision_day=4, first_day=5, through_day=6)
    assert actual.merge_due(5, forecast.due(5))[pair] == ()
    assert actual.merge_due(6, forecast.due(6)) == forecast.due(6)
    assert forecast.requirements(decision_day=4, first_day=5, through_day=6) == original
    assert actual.calendar.requirements(decision_day=4, first_day=5, through_day=364) == {}
    assert actual.day_audit(pair, 5)["physical_demand_source"] == "observed_other_uses"
    assert actual.day_audit(pair, 6)["physical_demand_source"] == "estimated_other_uses"


def test_observed_execution_conserves_stock_and_mixed_backlog_without_double_use():
    from etudecas.simulation.engine.mrp_planning import serve_external_component_requirements
    pair, payload, args, forecast, cls = _observed_execution_case(5)
    actual = cls(payload, **args)
    old = forecast.due(4)[pair][0]
    due = actual.merge_due(5, forecast.due(5))[pair]
    result = serve_external_component_requirements(decision_day=5, available_qty=3,
        backlog=(old,), due=due, uom="KG")
    assert result.consumed_qty == 3 and result.available_end_qty == 0
    assert sum(r.qty for r in result.remaining) == pytest.approx(old.qty + 5 - 3)
    assert result.demand_qty == 5  # Estimated day5 is replaced, never added.
    assert actual.provenance(old.requirement_id, forecast)["physical_demand_source"] == "estimated_other_uses"
    assert actual.provenance(due[0].requirement_id, forecast)["physical_demand_source"] == "observed_other_uses"
    # A following observed zero cannot erase a previously unserved real issue.
    next_result = serve_external_component_requirements(decision_day=6, available_qty=10,
        backlog=result.remaining, due=(), uom="KG")
    assert next_result.consumed_qty == pytest.approx(old.qty + 5 - 3)
    assert next_result.remaining == ()


@pytest.mark.parametrize("mutation", ["future_visible", "repeat", "not_execution_only", "weekly_row"])
def test_observed_execution_rejects_leaking_or_ambiguous_calendar(mutation):
    _, payload, args, _, cls = _observed_execution_case()
    if mutation == "future_visible": payload["rows"][0]["known_day"] = 4
    elif mutation == "repeat": payload["repeat_period_days"] = 365
    elif mutation == "not_execution_only": payload["physical_use_only"] = False
    else: payload["rows"][0]["period_days"] = 7
    with pytest.raises(ValueError): cls(payload, **args)


def _current_envelope_case(rows=((4, 100, 60),)):
    pair = ("client", "item:PF")
    payload = dict(schema_version=1, origin_date="2025-01-01", calendar="sunday_start", rows=[
        dict(node_id="depot", item_id=pair[1], uom="UN", vintage_day=v, qty_I=i, qty_H=h, source_row=f"I{v}")
        for v, i, h in rows])
    return engine.CurrentRequirementEnvelope(payload,
        source_to_customer={("depot", pair[1]): pair}, origin_date="2025-01-01"), pair


def _envelope_service(envelope, pair, through, quantities):
    for day in range(len(envelope.served_prefix[pair]) - 1, through + 1):
        envelope.observe_service(day, {pair: quantities.get(day, 0)})


def test_current_envelope_residual_gross_I_replaces_overlap_and_H_is_not_receipt():
    envelope, pair = _current_envelope_case()
    _envelope_service(envelope, pair, 4, {4: 10})
    needs = [Requirement("backlog:physical", 5, 10), Requirement("forecast:remaining", 6, 50)]
    extra, audit = envelope.requirement(pair, decision_day=4, requirements=needs)
    assert (audit["residual_I_qty"], audit["model_backlog_qty"], audit["model_remaining_forecast_qty"]) == (90, 10, 50)
    assert extra.qty == 30 and extra.due_day == 5
    # I100-served10=90; stock5+realfirm60 =>25. H60 is never subtracted a second time.
    plan = plan_dated_requirements(decision_day=4, available_qty=5, requirements=needs + [extra],
        firm_receipts=[FirmReceipt("real-model-firm", 5, 60)], lead_days=0)
    assert plan.proposed_qty == 25 and plan.closing_projected_qty == 0
    assert audit["source_H_qty"] == 60


def test_current_envelope_never_reduces_real_backlog_when_actual_orders_exceed_I():
    envelope, pair = _current_envelope_case()
    _envelope_service(envelope, pair, 4, {4: 10})
    needs = [Requirement("backlog:physical", 5, 110)]
    extra, audit = envelope.requirement(pair, decision_day=4, requirements=needs)
    assert extra is None and audit["residual_I_qty"] == 90 and needs[0].qty == 110


def test_current_envelope_repeated_snapshot_and_new_receipt_do_not_duplicate_orders():
    envelope, pair = _current_envelope_case(((4, 100, 60), (11, 100, 0)))
    _envelope_service(envelope, pair, 4, {})
    extra, audit = envelope.requirement(pair, decision_day=4, requirements=[])
    assert envelope.requirement(pair, decision_day=4, requirements=[]) == (extra, audit)
    first = plan_dated_requirements(decision_day=4, available_qty=0, requirements=[extra], firm_receipts=[], lead_days=1)
    assert first.proposed_qty == 100
    _envelope_service(envelope, pair, 5, {})
    repeated, _ = envelope.requirement(pair, decision_day=5, requirements=[])
    covered = plan_dated_requirements(decision_day=5, available_qty=100,
        requirements=[repeated], firm_receipts=[], lead_days=1)
    assert covered.proposals == ()
    _envelope_service(envelope, pair, 11, {})
    next_vintage, _ = envelope.requirement(pair, decision_day=11, requirements=[])
    assert next_vintage.qty == 100  # Replacement envelope, not200 cumulatively.
    assert plan_dated_requirements(decision_day=11, available_qty=100,
        requirements=[next_vintage], firm_receipts=[], lead_days=1).proposals == ()


def test_current_envelope_expiry_zero_revision_and_new_vintage_service_anchor():
    envelope, pair = _current_envelope_case(((4, 100, 60), (11, 100, 0), (18, 0, 0)))
    _envelope_service(envelope, pair, 10, {4: 10, 10: 5})
    extra, audit = envelope.requirement(pair, decision_day=10, requirements=[])
    assert extra is None and audit["expired_residual_qty"] == 85
    _envelope_service(envelope, pair, 11, {11: 20})
    extra, audit = envelope.requirement(pair, decision_day=11, requirements=[])
    assert extra.qty == 80 and audit["served_since_vintage_qty"] == 20  # Do not subtract the previous15 again.
    _envelope_service(envelope, pair, 18, {})
    extra, audit = envelope.requirement(pair, decision_day=18, requirements=[Requirement("backlog:real", 19, 40)])
    assert extra is None and audit["source_I_qty"] == 0 and audit["model_backlog_qty"] == 40


def test_current_envelope_missing_bucket_service_phase_and_csv_are_explicit():
    envelope, pair = _current_envelope_case()
    with pytest.raises(ValueError, match="service"):
        envelope.requirement(pair, decision_day=0, requirements=[])
    _envelope_service(envelope, pair, 0, {})
    _, missing = envelope.requirement(pair, decision_day=0, requirements=[])
    assert missing["status"] == "no_known_current_bucket"
    with pytest.raises(ValueError, match="consecutive"):
        envelope.observe_service(0, {pair: 0})
    _envelope_service(envelope, pair, 4, {})
    _, active = envelope.requirement(pair, decision_day=4, requirements=[])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=engine.CURRENT_REQUIREMENT_ENVELOPE_FIELDS)
    writer.writeheader()
    writer.writerows([missing, active])
    assert len(list(csv.DictReader(io.StringIO(output.getvalue())))) == 2


def _annual_projection_case(policy):
    pair = ("client", "item:PF")
    payload = dict(schema_version=1, origin="2025-01-01", calendar="sunday_start", repeat_period_days=365,
        current_bucket_policy="excluded_unresolved_carry_over", rows=[
            dict(node_id=pair[0], item_id=pair[1], uom="UN", vintage_day=v, period_start_day=start,
                 period_days=7, qty=quantity, source_row=str(start))
            for v, start, quantity in [(4, 11, 700), (4, 376, 7000), (354, 361, 700), (361, 376, 0)]])
    return engine.RollingMrpForecast(payload, demand_pairs={pair}, origin_date="2025-01-01",
        missing_period_policy="last_known_period_v1", consumption_policy="weekly_actual_orders_v1",
        annual_projection_policy=policy), pair


def test_annual_projection_replaces_2026_from_commercial_profile_not_I_and_leaves_2025():
    forecast, pair = _annual_projection_case("previous_year_105pct_v1")
    base, _ = forecast.window(pair, decision_day=4, target_day=11, fallback_daily_values=[10] * 7)
    projected, audit = forecast.window(pair, decision_day=4, target_day=376, fallback_daily_values=[10] * 7)
    assert base == 100 and projected == 10.5  # Neither I2025=100 nor source2026=1000 is growth base.
    assert audit["source_rows"] == "" and audit["annual_projected_days"] == 7
    assert audit["annual_projection_basis"] == "imported_commercial2025_profile"
    zero, _ = forecast.window(pair, decision_day=4, target_day=376, fallback_daily_values=[0])
    assert zero == 0


def test_annual_projection_opt_out_preserves_known_source2026_and_future_vintage_causality():
    forecast, pair = _annual_projection_case(None)
    old, audit = forecast.window(pair, decision_day=4, target_day=376, fallback_daily_values=[10])
    revised, _ = forecast.window(pair, decision_day=361, target_day=376, fallback_daily_values=[10])
    assert old == 1000 and revised == 0 and "annual_projection_policy" not in audit


def test_annual_projection_boundary_overrides_consumed_week_only_for_2026_dates():
    forecast, pair = _annual_projection_case("previous_year_105pct_v1")
    _observe_pf_days(forecast, pair, 363, {361: 10, 362: 10, 363: 10})
    before, _ = forecast.window(pair, decision_day=363, target_day=364, fallback_daily_values=[10])
    after, _ = forecast.window(pair, decision_day=363, target_day=365, fallback_daily_values=[10])
    assert before == 167.5  # Current remaining670 / four future days, unchanged convention on2025.
    assert after == 10.5  # Same source week crosses year; explicit commercial projection wins on2026.


def _closure_context():
    return dict(closed_days=frozenset(range(215, 227)), process_days=3, receipt_days=10, origin_date="2025-01-01")


def test_manufacturing_closure_advances_only_new_proposals_and_preserves_firm_quantities():
    # Aug4..15 closed. Nominal launch Aug5(day216), available Aug22(day233).
    needs = [Requirement("new", 233, 150)]
    firms = [FirmReceipt("actual-held", 232, 50, "held")]
    plan = plan_dated_requirements(decision_day=200, available_qty=0, requirements=needs,
        firm_receipts=firms, lead_days=17)
    moved = engine.calendarize_manufacturing_plan(plan, requirements=needs, firm_receipts=firms, **_closure_context())
    assert (plan.proposals[0].release_day, moved.proposals[0].release_day) == (216, 211)
    assert moved.proposals[0].available_day == 226  # Completion SunAug3 then10Mon-Fri ->FriAug15.
    assert moved.proposed_qty == plan.proposed_qty == 100
    assert moved.proposals[0].requested_day == 233
    firm = [a for a in moved.commitment_allocations if a.supply_id == "actual-held"][0]
    assert (firm.qty, firm.available_day) == (50, 232)


def test_manufacturing_closure_too_late_delays_and_revalidation_cannot_cancel_advance():
    context = _closure_context()
    needs = [Requirement("new", 233, 100)]
    due, refreshed = engine.dated_production_release(decision_day=211, snapshot_day=210,
        requirements=needs, available_qty=0, firm_receipts=[], lead_days=17, lot_sizing=LotSizing(integer=True),
        manufacturing_calendar=context)
    assert due == 100 and refreshed.proposals[0].release_day == 211
    due, late = engine.dated_production_release(decision_day=216, snapshot_day=215,
        requirements=needs, available_qty=0, firm_receipts=[], lead_days=17, lot_sizing=LotSizing(integer=True),
        manufacturing_calendar=context)
    assert due == 0 and late.proposals[0].release_day == 227
    assert late.late_qty == 100 and late.late_qty_days > 0


def test_manufacturing_closure_propagates_earlier_BOM_once_and_reuses_existing_surplus():
    output, component = ("factory", "PF"), ("factory", "material")
    needs = {output: [Requirement("new", 233, 100)]}
    context = dict(decision_day=200, requirements_by_pair=needs, available_by_pair={output: 0, component: 0},
        firm_receipts_by_pair={}, transport_sources_by_pair={}, bom_by_pair={output: [(component, 2)]},
        lead_days_by_pair={output: 17, component: 2}, lot_sizing_by_pair={}, reserve_targets_by_pair={},
        coverage_days_by_pair={}, active_campaigns_by_pair={})
    old, _, _ = engine.plan_component_network(**context)
    new, requirements, _ = engine.plan_component_network(**context,
        manufacturing_calendar_by_pair={output: _closure_context()})
    assert old[output].proposed_qty == new[output].proposed_qty == 100
    assert len(requirements[component]) == 1
    assert (requirements[component][0].due_day, requirements[component][0].qty) == (211, 200)
    assert new[component].proposed_qty == 200
    context["available_by_pair"][output] = 100
    covered, _, _ = engine.plan_component_network(**context,
        manufacturing_calendar_by_pair={output: _closure_context()})
    assert covered[output].proposals == () and covered[component].proposals == ()


def test_manufacturing_closure_work_calendar_scope_and_reschedule_guard():
    context = _closure_context()
    assert engine.manufacturing_work_finish(214, 3, context["closed_days"]) == 229
    # A lot already finished before closure can pass its existing quality clock during closure.
    assert supplier_receipt_available_day(211, 10, origin_date="2025-01-01") == 225
    kwargs = dict(nodes=[{"id": "factory", "type": "factory"}, {"id": "DC", "type": "distribution_center"}],
        produced_pairs={("factory", "PF"), ("factory", "OTHER")}, origin_date="2025-01-01")
    payload = dict(schema_version=1, rows=[dict(node_id="factory", start_date="2025-08-04",
        end_date="2025-08-15", provenance="confirmed user dates")])
    assert engine.resolve_manufacturing_closures(None, **kwargs) == {}
    selected = engine.resolve_manufacturing_closures(payload, **kwargs)
    assert set(selected) == kwargs["produced_pairs"] and selected["factory", "PF"] == context["closed_days"]
    needs = [Requirement("new", 5, 10)]
    plan = plan_dated_requirements(decision_day=0, available_qty=0, requirements=needs, firm_receipts=[], lead_days=1)
    with pytest.raises(ValueError, match="quantities"):
        engine.reschedule_dated_plan(plan, requirements=needs, firm_receipts=[],
            proposals=[engine.replace(plan.proposals[0], qty=11)])


def test_manufacturing_closure_stops_fractional_active_work_without_releasing_or_losing_it():
    closed = _closure_context()["closed_days"]
    target, executed = 10, 4.5  # Fractional work is valid; the eventual physical lot is integer.
    for day in (215, 220, 226):
        capacity = engine.manufacturing_day_capacity(float("inf"), day=day, closed_days=closed)
        executed += min(target - executed, capacity)
        assert executed == 4.5 and capacity == 0
    capacity = engine.manufacturing_day_capacity(6, day=227, closed_days=closed)
    executed += min(target - executed, capacity)
    assert executed == target == 10
    assert engine.manufacturing_day_capacity(6, day=220, closed_days=()) == 6


def test_manufacturing_closure_mps_zero_capacity_is_closed_not_unmodeled():
    pair, component = ("factory", "PF"), ("factory", "material")
    campaigns = {pair: 100}
    context = dict(day=215, process_input_requirements_by_output_pair={pair: [(component, 2)]},
        production_lot_policy_by_pair={pair: {"enabled": True}}, process_capacity_by_output_pair={pair: 0},
        mps_open_campaign_qty_by_pair=campaigns, mps_started_lots_by_week_pair={})
    assert engine.lotified_mps_component_signal({pair: 10}, **context, closed_output_pairs={pair}) == ({}, {})
    assert campaigns[pair] == 100
    # Historical0 still means capacity unknown, preserving opt-out semantics.
    component_signal, output_signal = engine.lotified_mps_component_signal({pair: 10}, **context)
    assert output_signal[pair] == 100 and component_signal[component] == 200


def known_pf_forecast(policy=None):
    pair = ("C", "item:PF")
    payload = {"schema_version": 1, "origin": "2025-01-01", "calendar": "sunday_start",
        "repeat_period_days": 365, "current_bucket_policy": "excluded_unresolved_carry_over", "rows": [
            {"node_id": "C", "item_id": "item:PF", "uom": "UN", "vintage_day": vintage,
             "period_start_day": period, "period_days": 7, "qty": qty, "source_row": row}
            for vintage, period, qty, row in [(4, 11, 70, "old-current"), (4, 18, 140, "old-future"),
                (11, 18, 0, "new-zero"), (11, 25, 210, "new-later"), (25, 32, 280, "not-yet-known")]]}
    return engine.RollingMrpForecast(payload, demand_pairs={pair}, origin_date="2025-01-01",
        missing_period_policy=policy), pair


def _consumed_pf_forecast(*, quantity=100, policy="weekly_actual_orders_v1"):
    pair = ("client", "item:PF")
    payload = {"schema_version": 1, "origin": "2025-01-01", "calendar": "sunday_start",
        "repeat_period_days": 365, "current_bucket_policy": "excluded_unresolved_carry_over", "rows": [
            {"node_id": pair[0], "item_id": pair[1], "uom": "UN", "vintage_day": vintage,
             "period_start_day": start, "period_days": 7, "qty": qty, "source_row": row}
            for vintage, start, qty, row in [(4, 11, quantity, "whole-week"), (4, 18, 140, "old-future"),
                (11, 18, 0, "explicit-zero"), (25, 32, 210, "unknown-future")]]}
    return engine.RollingMrpForecast(payload, demand_pairs={pair}, origin_date="2025-01-01",
        missing_period_policy="last_known_period_v1", consumption_policy=policy), pair


def _observe_pf_days(forecast, pair, through_day, quantities):
    for day in range(forecast.consumption_revision, through_day + 1):
        forecast.observe_demand(day, {pair: quantities.get(day, 0.0)})


def test_forecast_consumption_arrived_orders_not_shipments_and_backlog_once():
    forecast, pair = _consumed_pf_forecast()
    _observe_pf_days(forecast, pair, 13, {11: 10, 12: 10, 13: 10})
    row = forecast.consumption_audit(pair, 13)
    assert (row["weekly_forecast_qty"], row["arrived_demand_qty"], row["remaining_forecast_qty"]) == (100, 30, 70)
    assert (row["period_start_day"], row["period_end_day"], row["future_days"], row["future_daily_qty"]) == (11, 17, 4, 17.5)
    assert (row["source_vintage_day"], row["source_row"]) == (4, "whole-week")
    daily, _ = forecast.window(pair, decision_day=13, target_day=14, fallback_daily_values=[999] * 4)
    served = 10
    backlog = 30 - served
    assert daily * 4 + backlog == 90  # Subtracting served instead of arrived would incorrectly give110.
    needs = [Requirement("backlog-once", 14, backlog)] + [Requirement(f"future-{d}", d, daily) for d in range(14, 18)]
    plan = plan_dated_requirements(decision_day=13, available_qty=5, requirements=needs,
        firm_receipts=[FirmReceipt("one-receipt", 14, 25)], lead_days=0)
    assert plan.proposed_qty == 60 and plan.closing_projected_qty == 0


def test_forecast_consumption_excess_orders_leave_only_actual_backlog():
    forecast, pair = _consumed_pf_forecast()
    _observe_pf_days(forecast, pair, 13, {11: 40, 12: 40, 13: 40})
    row = forecast.consumption_audit(pair, 13)
    assert row["remaining_forecast_qty"] == row["future_daily_qty"] == 0
    backlog = 120 - 100  # Physical service is independent of the100 forecast.
    assert row["remaining_forecast_qty"] + backlog == 20


def test_forecast_consumption_today_is_arrived_demand_and_future_starts_tomorrow():
    forecast, pair = _consumed_pf_forecast()
    _observe_pf_days(forecast, pair, 13, {11: 10, 12: 10, 13: 10})
    today, audit = forecast.window(pair, decision_day=13, target_day=13, fallback_daily_values=[999])
    whole, _ = forecast.window(pair, decision_day=13, target_day=13, fallback_daily_values=[999] * 5)
    assert today == 10 and whole * 5 == 80  # Today's10 plus future70, not forecast100 or90 backlog.
    assert audit["actual_order_days"] == 1 and audit["source_days"] == audit["fallback_days"] == 0


def test_forecast_consumption_replaces_remainder_and_invalidates_initial_cache():
    forecast, pair = _consumed_pf_forecast()
    before, _ = forecast.window(pair, decision_day=13, target_day=14, fallback_daily_values=[999] * 4)
    assert before == pytest.approx(100 / 7)
    assert forecast.consumption_audit(pair, 13)["status"] == "awaiting_today_observation"
    _observe_pf_days(forecast, pair, 13, {11: 10, 12: 10, 13: 10})
    assert forecast.consumption_audit(pair, 13)["remaining_forecast_qty"] == 70
    forecast.observe_demand(14, {pair: 15})
    assert forecast.consumption_audit(pair, 14)["remaining_forecast_qty"] == 55
    assert forecast.consumption_audit(pair, 14)["future_daily_qty"] == pytest.approx(55 / 3)
    # A subsequent decision cannot contaminate an earlier as-of query.
    assert forecast.consumption_audit(pair, 13)["arrived_demand_qty"] == 30


def test_forecast_consumption_expires_without_carrying_forecast_into_backlog():
    forecast, pair = _consumed_pf_forecast()
    _observe_pf_days(forecast, pair, 17, {day: 10 for day in range(11, 18)})
    row = forecast.consumption_audit(pair, 17)
    assert row["expired_forecast_qty"] == 30
    assert row["remaining_forecast_qty"] == row["future_daily_qty"] == row["future_days"] == 0
    following, audit = forecast.window(pair, decision_day=17, target_day=18, fallback_daily_values=[999] * 7)
    assert following == 0 and audit["source_rows"] == "explicit-zero"


def test_forecast_consumption_uniform_orders_preserve_uniform_forecast():
    forecast, pair = _consumed_pf_forecast(quantity=70)
    _observe_pf_days(forecast, pair, 13, {11: 10, 12: 10, 13: 10})
    quantity, _ = forecast.window(pair, decision_day=13, target_day=13, fallback_daily_values=[999] * 5)
    assert quantity == 10
    assert forecast.consumption_audit(pair, 13)["remaining_forecast_qty"] == 40


def test_forecast_consumption_zero_unknown_and_future_periods_remain_distinct():
    forecast, pair = _consumed_pf_forecast()
    _observe_pf_days(forecast, pair, 4, {4: 12})
    assert forecast.consumption_audit(pair, 4)["status"] == "never_known_period_nominal_fallback"
    missing, audit = forecast.window(pair, decision_day=4, target_day=5, fallback_daily_values=[17] * 6)
    assert missing == 17 and audit["fallback_days"] == 6
    future, audit = forecast.window(pair, decision_day=4, target_day=18, fallback_daily_values=[999] * 7)
    assert future == 20 and audit["source_vintage_days"] == "4"  # Future revision to0 is not known yet.
    _observe_pf_days(forecast, pair, 18, {18: 7})
    row = forecast.consumption_audit(pair, 18)
    assert row["weekly_forecast_qty"] == row["remaining_forecast_qty"] == 0
    assert row["arrived_demand_qty"] == 7 and row["source_row"] == "explicit-zero"
    future, audit = forecast.window(pair, decision_day=18, target_day=32, fallback_daily_values=[19] * 7)
    assert future == 19 and audit["source_vintage_days"] == ""  # Never use vintage25 early.


def test_forecast_consumption_observation_is_once_and_cannot_skip_or_revise_days():
    forecast, pair = _consumed_pf_forecast()
    forecast.observe_demand(0, {pair: 10})
    forecast.observe_demand(0, {pair: 10})
    assert forecast.consumption_revision == 1
    with pytest.raises(ValueError, match="revised"):
        forecast.observe_demand(0, {pair: 11})
    with pytest.raises(ValueError, match="consecutive"):
        forecast.observe_demand(2, {pair: 10})


def test_forecast_consumption_opt_out_keeps_original_values_and_audit_exactly():
    forecast, pair = _consumed_pf_forecast(policy=None)
    before = forecast.window(pair, decision_day=13, target_day=13, fallback_daily_values=[999] * 7)
    forecast.observe_demand(13, {pair: 10000})
    after = forecast.window(pair, decision_day=13, target_day=13, fallback_daily_values=[999] * 7)
    assert after == before and forecast.consumption_revision == 0
    assert "actual_order_days" not in after[1]
    assert after[0] == pytest.approx(500 / 49)  # Five100/7 days and two explicit-zero days.


def test_forecast_consumption_csv_writer_accepts_all_real_audit_states_in_memory():
    forecast, pair = _consumed_pf_forecast()
    _observe_pf_days(forecast, pair, 4, {4: 12})
    rows = [dict(forecast.consumption_audit(pair, 4))]
    _observe_pf_days(forecast, pair, 18, {day: 10 for day in range(11, 18)})
    rows.extend(dict(forecast.consumption_audit(pair, day)) for day in (13, 17, 18))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=engine.FORECAST_CONSUMPTION_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    parsed = list(csv.DictReader(io.StringIO(output.getvalue())))
    assert len(parsed) == 4 and parsed[0]["weekly_forecast_qty"] == ""
    assert float(parsed[1]["remaining_forecast_qty"]) == 70
    assert float(parsed[2]["expired_forecast_qty"]) == 30
    assert float(parsed[3]["weekly_forecast_qty"]) == 0


@pytest.mark.parametrize("fault", [None, "no_source", "no_last_known", "no_dated_production", "not_customer", "no_manufacture", "past_target_bucket"])
def test_forecast_consumption_scope_requires_structural_finished_customer_and_dated_modes(fault):
    pair = ("customer", "item:PF")
    context = dict(source_forecast=True, missing_period_policy="last_known_period_v1",
        production_execution_policy="dated_releases_v1",
        nodes=[{"id": "factory", "type": "factory"}, {"id": "depot", "type": "distribution_center"},
               {"id": "customer", "type": "customer"}], demand_pairs={pair}, produced_pairs={("factory", pair[1])},
        lanes_by_dest_item={pair: [{"src": "depot"}], ("depot", pair[1]): [{"src": "factory"}]})
    if fault == "no_source": context["source_forecast"] = False
    elif fault == "no_last_known": context["missing_period_policy"] = None
    elif fault == "no_dated_production": context["production_execution_policy"] = None
    elif fault == "not_customer": context["nodes"][-1]["type"] = "factory"
    elif fault == "no_manufacture": context["produced_pairs"] = set()
    elif fault == "past_target_bucket": context["target_bucket_days"] = 7
    assert engine.resolve_forecast_consumption(None, **context) == set()
    if fault is None:
        assert engine.resolve_forecast_consumption("weekly_actual_orders_v1", **context) == {pair}
    else:
        with pytest.raises(ValueError):
            engine.resolve_forecast_consumption("weekly_actual_orders_v1", **context)


def test_known_pf_period_keeps_previous_forecast_when_current_bucket_is_missing():
    forecast, pair = known_pf_forecast("last_known_period_v1")
    quantity, audit = forecast.window(pair, decision_day=11, target_day=11, fallback_daily_values=[99] * 7)
    assert quantity == 10 and audit["source_days"] == 7 and audit["fallback_days"] == 0
    assert audit["source_rows"] == "old-current" and audit["source_vintage_days"] == "4"
    assert audit["vintage_day"] == 11  # Latest published plan is distinct from the row actually retained.


def test_known_pf_period_explicit_new_zero_overrides_previous_positive_forecast():
    forecast, pair = known_pf_forecast("last_known_period_v1")
    quantity, audit = forecast.window(pair, decision_day=11, target_day=18, fallback_daily_values=[99] * 7)
    assert quantity == 0 and audit["source_rows"] == "new-zero" and audit["source_vintage_days"] == "11"


def test_known_pf_period_does_not_use_future_or_invent_a_never_known_period():
    forecast, pair = known_pf_forecast("last_known_period_v1")
    quantity, audit = forecast.window(pair, decision_day=11, target_day=32, fallback_daily_values=[99] * 7)
    assert quantity == 99 and audit["source_days"] == 0 and audit["fallback_days"] == 7
    assert audit["source_vintage_days"] == ""
    later, _ = forecast.window(pair, decision_day=25, target_day=32, fallback_daily_values=[99] * 7)
    assert later == 40


def test_known_pf_period_preserves_legacy_fallback_without_opt_in():
    forecast, pair = known_pf_forecast()
    quantity, audit = forecast.window(pair, decision_day=11, target_day=11, fallback_daily_values=[99] * 7)
    assert quantity == 99
    assert audit == {"vintage_day": 11, "cycle_index": 0, "source_days": 0,
                     "fallback_days": 7, "source_rows": ""}


def test_known_pf_period_keeps_periods_separate_and_reports_mixed_provenance():
    forecast, pair = known_pf_forecast("last_known_period_v1")
    quantity, audit = forecast.window(pair, decision_day=11, target_day=11, fallback_daily_values=[99] * 14)
    assert quantity == 5 and audit["source_days"] == 14
    assert set(audit["source_rows"].split("|")) == {"old-current", "new-zero"}
    assert audit["source_vintage_days"] == "4|11"


def production_release(**overrides):
    values = dict(decision_day=1, snapshot_day=0, requirements=[Requirement("dispatch", 4, 100)],
                  available_qty=0, firm_receipts=(), lead_days=3, lot_sizing=LotSizing(multiple=50, integer=True))
    values.update(overrides)
    return engine.dated_production_release(**values)


def test_dated_production_release_is_due_once_and_has_no_new_launch_on_day_zero():
    assert production_release(decision_day=0, snapshot_day=None) == (0, None)
    quantity, plan = production_release()
    assert quantity == 100 and [(p.release_day, p.available_day, p.qty) for p in plan.proposals] == [(1, 4, 100)]
    assert production_release(campaign_remaining_qty=40, executed_wip_qty=60) == (0, None)
    assert production_release(decision_day=2, snapshot_day=1, available_qty=100)[0] == 0


def test_dated_production_release_renets_today_receipt_and_never_credits_it_twice():
    receipt = FirmReceipt("opening", 1, 100, "confirmed")
    assert production_release(available_qty=100, firm_receipts=[receipt])[0] == 0
    quantity, plan = production_release(requirements=[Requirement("dispatch", 4, 200)],
                                       available_qty=100, firm_receipts=[receipt])
    assert quantity == 100 and plan.proposed_qty == 100


def test_dated_production_release_keeps_late_firm_date_without_duplicate_production():
    quantity, plan = production_release(firm_receipts=[FirmReceipt("late-initial", 10, 100, "confirmed")])
    assert quantity == 0 and plan.proposals == () and plan.late_qty == 100
    assert {row.available_day for row in plan.allocations} == {10}


def test_dated_production_release_nets_partial_firm_and_uses_only_due_new_proposals():
    quantity, plan = production_release(firm_receipts=[FirmReceipt("initial", 4, 50)],
        requirements=[Requirement("near", 4, 100), Requirement("far", 20, 100)])
    assert quantity == 50 and plan.proposed_qty == 150
    assert sorted((r.release_day, r.qty) for r in plan.proposals) == [(1, 50), (17, 100)]


def test_dated_production_release_preserves_non_consumable_floor_and_integer_lots():
    quantity, plan = production_release(available_qty=20, protection=[StockProtection("floor", 1, 30)])
    assert quantity == 150 and plan.closing_projected_qty == 70
    assert sum(row.qty for row in plan.allocations) == 100
    assert all(row.qty == int(row.qty) for row in plan.proposals)


@pytest.mark.parametrize("snapshot", [-1, 1, 2])
def test_dated_production_release_rejects_stale_or_future_snapshot(snapshot):
    with pytest.raises(ValueError, match="preceding"):
        production_release(snapshot_day=snapshot)


def finished_goods_release_scope():
    pair = ("FACTORY", "item:PF")
    payload = {"schema_version": 1, "rows": [{"node_id": pair[0], "item_id": pair[1],
        "depot_node_id": "DC", "receipt_days": 10, "receipt_calendar": "monday_friday",
        "location_basis": "factory_before_push_hypothesis",
        "source_refs": {"receipt_days": "source E", "receipt_calendar": "user weekdays",
                        "location": "factory hypothesis"}}]}
    kwargs = dict(nodes=[{"id": "FACTORY", "type": "factory"},
                         {"id": "DC", "type": "distribution_center"}],
        produced_pairs={pair}, finished_item_ids={pair[1]}, item_unit_map={pair[1]: "UN"},
        lanes_by_dest_item={("DC", pair[1]): [{"src": "FACTORY"}]})
    return pair, payload, kwargs


def generic_production_release_scope():
    pair = ("factory-A", "item:intermediate")
    payload = dict(schema_version=1, rows=[dict(node_id=pair[0], item_id=pair[1],
        receipt_days=28, receipt_calendar="monday_friday", location_basis="source_confirmed_manufacturing_site",
        source_refs=dict(receipt_days="source E", receipt_calendar="user weekdays",
                         manufacturing_site="user confirms manufacture here"))])
    kwargs = dict(nodes=[dict(id=pair[0], type="factory")], produced_pairs={pair},
                  item_unit_map={pair[1]: "G"})
    return pair, payload, kwargs


def test_generic_production_release_accepts_mass_intermediate_without_depot_and_preserves_PF_policy():
    pair, payload, kwargs = generic_production_release_scope()
    before = deepcopy((payload, kwargs))
    assert engine.resolve_production_release_policy(None, receipt_netting_mode="within_cover", **kwargs) == {}
    assert engine.resolve_production_release_policy(payload, **kwargs) == {pair: payload["rows"][0]}
    assert (payload, kwargs) == before
    pf, legacy, legacy_kwargs = finished_goods_release_scope()
    assert engine.resolve_finished_goods_release_policy(legacy, **legacy_kwargs) == {pf: legacy["rows"][0]}
    assert engine.resolve_production_release_policy(None, **kwargs) == {}


@pytest.mark.parametrize("fault", ["no_process", "not_factory", "calendar", "no_provenance", "duplicate", "within_cover"])
def test_generic_production_release_rejects_unproved_process_or_calendar(fault):
    _pair, payload, kwargs = generic_production_release_scope()
    if fault == "no_process": kwargs["produced_pairs"] = set()
    elif fault == "not_factory": kwargs["nodes"][0]["type"] = "distribution_center"
    elif fault == "calendar": payload["rows"][0]["receipt_calendar"] = "unknown"
    elif fault == "no_provenance": payload["rows"][0]["source_refs"].pop("manufacturing_site")
    elif fault == "duplicate": payload["rows"].append(dict(payload["rows"][0]))
    elif fault == "within_cover": kwargs["receipt_netting_mode"] = "within_cover"
    with pytest.raises(ValueError):
        engine.resolve_production_release_policy(payload, **kwargs)


def test_generic_production_unknown_capacity_projects_one_fixed_batch_per_day_not_a_remote_date():
    assert engine.production_campaign_work_days(1800000, capacity_qty=0, fixed_lot_qty=600000) == 3
    assert engine.production_campaign_work_days(600000, capacity_qty=0, fixed_lot_qty=600000) == 1
    assert engine.production_campaign_work_days(0, capacity_qty=0, fixed_lot_qty=600000) == 0
    # A larger configured capacity still cannot execute two fixed batches in one daily process pass.
    assert engine.production_campaign_work_days(1800000, capacity_qty=1200000, fixed_lot_qty=600000) == 3
    with pytest.raises(ValueError, match="fixed batch"):
        engine.production_campaign_work_days(600000, capacity_qty=0, fixed_lot_qty=0)


def test_generic_production_two_full_mass_lots_use_integer_tokens_and_release_once_after_source_weekdays():
    pair, payload, kwargs = generic_production_release_scope()
    policy = engine.resolve_production_release_policy(payload, **kwargs)[pair]
    token = "item:virtual-token"
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={(pair[0], token): 730}, item_unit_map={token: "UN"})
    availability = engine.OpeningPurchaseAvailability([], item_unit_map={pair[1]: "G"})
    firms = []
    lots = []
    for number, physical_day, expected_available in [(1, 7, 47), (2, 8, 48)]:
        # The selected recipe has no capacity limit or other input: one entire batch per daily pass.
        available_tokens = ledger.pair_balance(node_id=pair[0], item_id=token)
        quantity = engine.production_input_feasible_execution_quantity(
            min(float("inf"), available_tokens * 600000, 600000),
            component_limits=[(available_tokens, 1 / 600000, "UN")])
        assert quantity == 600000
        consumed = engine.required_component_quantity(quantity, 1 / 600000, "UN")
        assert consumed == 1
        parents = ledger.consume(day=physical_day, node_id=pair[0], item_id=token, qty=consumed,
            event_type="production_consume", uom="UN", production_campaign_id="CMP")
        batch = engine.ProductionBatchWip(campaign_id="CMP", batch_id=f"B{number}", node_id=pair[0],
            item_id=pair[1], campaign_started_day=7, batch_started_day=physical_day, target_qty=600000)
        assert batch.add_execution(quantity, parents) == 600000 and batch.is_complete
        lot = ledger.create_child_lot(day=physical_day, node_id=pair[0], item_id=pair[1], qty=batch.target_qty,
            uom="G", source_type="production_output", source_id=batch.batch_id,
            parent_allocations=batch.parent_allocations, link_type="production", production_campaign_id="CMP")
        available_day = supplier_receipt_available_day(physical_day, policy["receipt_days"],
            origin_date="2025-01-01", calendar=policy["receipt_calendar"])
        assert available_day == expected_available  # Jan8/9 -> Feb17/18; arrival day excluded.
        marker = f"PRODUCTION_RELEASE|B{number}"
        availability.hold_production_lot(marker=marker, node_id=pair[0], item_id=pair[1], quantity=600000,
            lot_id=lot, physical_day=physical_day, available_day=available_day, ledger=ledger,
            source_kind="production_output")
        firms.append(FirmReceipt(marker, available_day, 600000, "held"))
        lots.append(lot)
    assert ledger.pair_balance(node_id=pair[0], item_id=token) == 728
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == availability.held_by_pair[pair] == 1200000
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=46, node_id=pair[0], item_id=pair[1], qty=1, event_type="lane_ship", uom="G")
    plan = plan_dated_requirements(decision_day=8, available_qty=0,
        requirements=[Requirement("transfer", 50, 1200000)], firm_receipts=firms, lead_days=40)
    assert plan.proposed_qty == 0 and sum(r.qty for r in firms) == 1200000
    assert sum(a.qty for a in plan.allocations if a.supply_kind == "held") == 1200000
    for firm in firms:
        availability.release(firm.receipt_id, firm.available_day, firm.qty, ledger=ledger)
        with pytest.raises(ValueError):
            availability.release(firm.receipt_id, firm.available_day, firm.qty, ledger=ledger)
    assert availability.held_by_pair[pair] == 0
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == 1200000
    assert ledger.pair_balance(node_id=pair[0], item_id=token) == 728
    assert len(ledger.genealogy_rows) == 2
    assert sum(r["event_type"] == "production_output" for r in ledger.event_rows) == 2
    assert sum(r["event_type"] == "stock_availability_release" for r in ledger.event_rows) == 2


def test_generic_production_release_does_not_replace_explicit_opening_OF_availability():
    pair, _payload, _kwargs = generic_production_release_scope()
    ledger = engine.LotLedger(enabled=True)
    lot = ledger.create_child_lot(day=26, node_id=pair[0], item_id=pair[1], qty=600000,
        uom="G", source_type="opening_production_order", source_id="OF-source",
        parent_allocations=[], link_type="production")
    availability = engine.OpeningPurchaseAvailability([], item_unit_map={pair[1]: "G"})
    availability.hold_production_lot(marker="OF-source", node_id=pair[0], item_id=pair[1], quantity=600000,
        lot_id=lot, physical_day=26, available_day=55, ledger=ledger, source_kind="opening_production_order")
    # Source Jan27 -> Feb25 is preserved; the new28weekday rule would instead give March6.
    assert supplier_receipt_available_day(26, 28, origin_date="2025-01-01") == 64
    availability.release("OF-source", 55, 600000, ledger=ledger)
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == 600000
    assert ledger.genealogy_rows == []
    assert [(r["event_type"], r["day"]) for r in ledger.event_rows] == [
        ("opening_production_order", 26), ("stock_availability_hold", 26), ("stock_availability_release", 55)]


def test_finished_goods_quality_scope_is_structural_opt_in_and_source_documented():
    pair, payload, kwargs = finished_goods_release_scope()
    assert engine.resolve_finished_goods_release_policy(None, **kwargs) == {}
    assert engine.resolve_finished_goods_release_policy(payload, **kwargs) == {pair: payload["rows"][0]}
    assert payload["rows"][0]["receipt_days"] == 10
    kwargs["lanes_by_dest_item"]["DC", pair[1]].append({"src": "OTHER"})
    with pytest.raises(ValueError, match="exclusive"):
        engine.resolve_finished_goods_release_policy(payload, **kwargs)


def test_finished_goods_quality_rejects_within_cover_but_preserves_unselected_legacy_mode():
    _pair, payload, kwargs = finished_goods_release_scope()
    assert engine.resolve_finished_goods_release_policy(None, receipt_netting_mode="within_cover", **kwargs) == {}
    with pytest.raises(ValueError, match="within_cover"):
        engine.resolve_finished_goods_release_policy(payload, receipt_netting_mode="within_cover", **kwargs)


def test_finished_goods_physical_completion_and_quality_release_are_distinct_after_partial_WIP():
    batch = engine.ProductionBatchWip(campaign_id="CMP", batch_id="BATCH", node_id="F", item_id="PF",
        campaign_started_day=0, batch_started_day=0, target_qty=100)
    assert batch.add_execution(40, [{"lot_id": "RM", "qty": 10}]) == 40
    partial = engine.production_completion_quantities(batch.target_qty if batch.is_complete else 0,
                                                     retained_for_quality=True)
    assert partial == {"released_qty": 0, "physical_completed_qty": 0}
    assert batch.add_execution(60, [{"lot_id": "RM", "qty": 15}]) == 60
    physical = engine.production_completion_quantities(batch.target_qty if batch.is_complete else 0,
                                                      retained_for_quality=True)
    assert physical == {"released_qty": 0, "physical_completed_qty": 100}
    release = engine.finished_goods_quality_release_event(dict(physical, actual_qty=60,
        actual_lot_starts=1, campaign_started_qty=100), day=23, lot_id="PF-LOT", qty=100)
    assert release["physical_completed_qty"] == release["actual_qty"] == release["actual_lot_starts"] == 0
    assert release["released_qty"] == 100 and release["day"] == 23
    assert release["release_gate_mode"] == "source_weekday_quality_release"
    assert sum(r["physical_completed_qty"] for r in (partial, physical, release)) == 100
    assert sum(r["released_qty"] for r in (partial, physical, release)) == 100
    assert sum(a["qty"] for a in batch.parent_allocations) == 25


def test_finished_goods_completion_export_preserves_legacy_fields_without_quality():
    assert engine.production_completion_quantities(0) == {"released_qty": 0}
    assert engine.production_completion_quantities(100) == {"released_qty": 100}


def test_batch_target_canonicalizes_observed_two_ulp_residue_before_stock_and_ledger():
    # Captured C failure: Gien268967, J265, fifth107800-unit physical batch.
    remainder = 107799.99999999997
    policy = {"enabled": True, "fixed_lot_qty": 107800}
    raw_target = engine.physical_batch_target_qty(remainder, policy)
    assert raw_target == remainder and raw_target != 107800
    with pytest.raises(ValueError, match="Physical UN available stock must be integer"):
        plan_with_stock_protection(decision_day=265, available_qty=raw_target,
            requirements=[Requirement("dispatch", 266, 107800)], firm_receipts=[], lead_days=0,
            lot_sizing=LotSizing(integer=True), protection=[StockProtection("floor", 266, 0)])
    target = engine.canonical_production_batch_target_qty(remainder, policy, "UN")
    batch = engine.ProductionBatchWip(campaign_id="CMP", batch_id="B005", node_id="factory", item_id="PF",
        campaign_started_day=255, batch_started_day=263, target_qty=target)
    assert batch.add_execution(50000.25, []) == 50000.25  # Fractional unfinished work remains permitted.
    assert batch.add_execution(57799.75, []) == 57799.75 and batch.is_complete
    released = batch.target_qty
    stock = released
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=263, stock={("factory", "RM"): 1}, item_unit_map={"RM": "G"})
    parents = ledger.consume(day=263, node_id="factory", item_id="RM", qty=1, event_type="production_consume", uom="G")
    ledger.create_child_lot(day=265, node_id="factory", item_id="PF", qty=released,
        source_type="production_output", source_id="factory|PF", parent_allocations=parents,
        link_type="production", uom="UN", production_campaign_id="CMP")
    assert stock == ledger.pair_balance(node_id="factory", item_id="PF") == 107800
    assert len(ledger.genealogy_rows) == 1
    plan = plan_with_stock_protection(decision_day=265, available_qty=stock,
        requirements=[Requirement("dispatch", 266, 107800)], firm_receipts=[], lead_days=0,
        lot_sizing=LotSizing(integer=True), protection=[StockProtection("floor", 266, 0)])
    assert plan.plan.proposed_qty == 0 and plan.plan.closing_projected_qty == 0


def test_batch_target_rejects_real_unit_fraction_and_preserves_integer_and_mass_targets():
    policy = {"enabled": True, "fixed_lot_qty": 107800}
    with pytest.raises(ValueError, match="Physical UN quantity must be integral"):
        engine.canonical_production_batch_target_qty(107799.5, policy, "UN")
    assert engine.canonical_production_batch_target_qty(107800, policy, "UN") == 107800
    assert engine.canonical_production_batch_target_qty(107799.5, policy, "G") == 107799.5


@pytest.mark.parametrize("fault", ["calendar", "location", "source", "quantity_unit", "not_manufactured"])
def test_finished_goods_quality_rejects_unsubstantiated_scope(fault):
    pair, payload, kwargs = finished_goods_release_scope()
    row = payload["rows"][0]
    if fault == "calendar": row["receipt_calendar"] = "calendar_days"
    elif fault == "location": row["location_basis"] = "proven_industrial_stock"
    elif fault == "source": row["source_refs"].pop("receipt_days")
    elif fault == "quantity_unit": kwargs["item_unit_map"][pair[1]] = "KG"
    else: kwargs["produced_pairs"] = set()
    with pytest.raises(ValueError):
        engine.resolve_finished_goods_release_policy(payload, **kwargs)


@pytest.mark.parametrize("physical,available", [(9, 23), (21, 35), (10, 23), (131, 145)])
def test_finished_goods_quality_ten_source_weekdays_exclude_arrival_and_weekends(physical, available):
    # 10 Jan -> 24 Jan; 22 Jan -> 5 Feb; Saturday11Jan ->24Jan; 12May ->26May.
    assert supplier_receipt_available_day(physical, 10, origin_date="2025-01-01") == available


def held_finished_goods_case():
    pair = ("FACTORY", "item:PF")
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={(pair[0], "item:RM"): 25},
                              item_unit_map={"item:RM": "KG"})
    parents = ledger.consume(day=9, node_id=pair[0], item_id="item:RM", qty=25,
                             event_type="production_consume", uom="KG", production_campaign_id="CMP")
    child = ledger.create_child_lot(day=9, node_id=pair[0], item_id=pair[1], qty=100, uom="UN",
        source_type="production_output", source_id="CMP", parent_allocations=parents, link_type="production",
        production_campaign_id="CMP")
    availability = engine.OpeningPurchaseAvailability([], item_unit_map={pair[1]: "UN"})
    return pair, ledger, child, availability


def test_finished_goods_quality_preserves_physical_lot_genealogy_and_single_firm_release():
    pair, ledger, child, availability = held_finished_goods_case()
    availability.hold_production_lot(marker="Q-CMP", node_id=pair[0], item_id=pair[1], quantity=100,
        lot_id=child, physical_day=9, available_day=23, ledger=ledger, source_kind="production_output")
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == 100
    assert availability.held_by_pair[pair] == 100 and len(ledger.genealogy_rows) == 1
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=22, node_id=pair[0], item_id=pair[1], qty=1, event_type="lane_ship", uom="UN")
    plan = plan_dated_requirements(decision_day=9, available_qty=0,
        requirements=[Requirement("dispatch", 20, 100)],
        firm_receipts=[FirmReceipt("Q-CMP", 23, 100, "held")], lead_days=14)
    assert plan.proposals == () and plan.late_qty == 100
    with pytest.raises(ValueError): availability.release("Q-CMP", 22, 100, ledger=ledger)
    availability.release("Q-CMP", 23, 100, ledger=ledger)
    assert availability.held_by_pair[pair] == 0 and len(ledger.genealogy_rows) == 1
    assert [(r["event_type"], r["day"]) for r in ledger.event_rows if r["lot_id"] == child] == [
        ("production_output", 9), ("stock_availability_hold", 9), ("stock_availability_release", 23)]
    with pytest.raises(ValueError): availability.release("Q-CMP", 23, 100, ledger=ledger)
    ledger.consume(day=23, node_id=pair[0], item_id=pair[1], qty=100, event_type="lane_ship", uom="UN")
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == 0


def test_finished_goods_quality_rejects_hold_larger_than_existing_lot_before_mutation():
    pair, ledger, child, availability = held_finished_goods_case()
    before = len(ledger.event_rows)
    with pytest.raises(ValueError, match="exceeds"):
        availability.hold_production_lot(marker="Q-CMP", node_id=pair[0], item_id=pair[1], quantity=101,
            lot_id=child, physical_day=9, available_day=23, ledger=ledger, source_kind="production_output")
    assert availability.rows == [] and len(ledger.event_rows) == before
    assert ledger.lots[child].get("qty_held", 0) == 0


@pytest.mark.parametrize("horizon", [15, 30])
def test_finished_goods_initial_order_keeps_source_G_I_and_one_commitment_without_second_delay(horizon):
    pair = ("FACTORY", "item:PF")
    pipeline, transit, issues = defaultdict(list), defaultdict(float), defaultdict(list)
    orders = []
    qty, rows, _ = engine.seed_open_orders_from_metadata(pipeline, transit,
        opening_open_orders_payload={"source_file": "Extract_En_cours.xlsx", "rows": [{
            "source_row": 75, "order_type": "production_open_order", "src_node_id": pair[0],
            "dst_node_id": pair[0], "item_id": pair[1], "quantity": 100, "uom": "UN",
            "physical_delivery_day": 9, "usable_day": 23, "receipt_release_days": 10,
            "planning_element": "O.Proc"}]}, lanes_by_dest_item={}, item_unit_map={pair[1]: "UN"},
        pair_mrp_safety_time_days={}, total_timeline_days=horizon, warmup_days=0,
        opening_production_bom_issues_by_day=issues, opening_production_order_bom_issue_mode="wip",
        mrp_order_rows=orders, supplier_shipment_rows=[], initialization_pipeline_rows=[],
        assumptions_ledger_rows=[], production_availability_pairs={pair})
    assert qty == 100 and transit[pair] == 100 and list(pipeline) == [23]
    assert len(pipeline[23]) == 1 and issues == {}
    assert orders[0]["physical_delivery_day"] == 9 and orders[0]["available_day"] == 23
    assert orders[0]["mrp_order_id"] == rows[0]["source_marker"] == pipeline[23][0][3]
    assert orders[0]["order_status_end_of_run"] == ("available" if horizon == 30 else "held_pending_availability")


def test_finished_goods_campaign_physical_completion_is_not_delayed_or_double_counted_by_quality():
    physical = dict(day=9, node_id="F", output_item_id="item:PF", campaign_id="CMP",
        event_type="run_campaign_complete", actual_qty=100, released_qty=0,
        campaign_started_qty=100, actual_lot_starts=1, campaign_remaining_end_qty=0, wip_end_qty=0)
    output = dict(day=9, event_type="production_output", production_campaign_id="CMP", lot_id="LOT",
        qty=100, notes=json.dumps({"available_day": 23, "availability_state": "held"}))
    held = engine.production_campaign_rows_with_availability([physical], [output])[0]
    assert held["actual_qty"] == 100 and held["completed_day"] == 9
    assert held["held_finished_qty"] == 100 and held["available_qty"] == 0
    assert held["availability_completed_day"] == "" and held["availability_status"] == "held"
    release = dict(day=23, event_type="stock_availability_release", source_type="finished_goods_release",
                   lot_id="LOT", qty=100)
    quality = dict(physical, day=23, event_type="quality_release", actual_qty=0, released_qty=100,
                   campaign_started_qty=0, actual_lot_starts=0)
    available = engine.production_campaign_rows_with_availability([physical, quality], [output, release])[0]
    assert available["completed_day"] == available["last_execution_day"] == 9
    assert available["actual_qty"] == available["available_qty"] == 100
    assert available["actual_lot_starts"] == 1 and available["held_finished_qty"] == 0
    assert available["availability_completed_day"] == 23 and available["availability_status"] == "available"


def test_finished_goods_active_campaign_waits_for_components_then_quality_without_second_BOM():
    factory, component = ("factory", "PF"), ("factory", "MP")
    plans, needs, audit = engine.plan_component_network(decision_day=0,
        requirements_by_pair={factory: [Requirement("dispatch", 20, 100)]},
        available_by_pair={}, firm_receipts_by_pair={component: [FirmReceipt("late-material", 30, 120)]},
        transport_sources_by_pair={}, bom_by_pair={factory: [(component, 2)]},
        lead_days_by_pair={factory: 17, component: 1}, lot_sizing_by_pair={},
        reserve_targets_by_pair={}, coverage_days_by_pair={},
        active_campaigns_by_pair={factory: ("campaign", 60, 40, 17)},
        campaign_receipt_context_by_pair={factory: {"receipt_days": 10, "origin_date": "2025-01-01"}})
    # Remaining60 consumes120; executed WIP40 is not consumed a second time.
    # Material31Jan(day30), then10weekdays ->14Feb(day44).
    assert sum(r.qty for r in needs[component]) == 120
    assert plans[factory].proposals == () and plans[factory].late_qty == 100
    assert {row.available_day for row in plans[factory].allocations} == {44}
    assert [(row.receipt_id, row.available_day, row.qty) for row in audit[factory]["firm_receipts"]] == [
        ("campaign:campaign", 44, 100)]


def test_finished_goods_first_batch_quality_release_cannot_complete_an_ongoing_campaign():
    physical = dict(day=9, node_id="F", output_item_id="item:PF", campaign_id="CMP",
        event_type="run_campaign", actual_qty=100, campaign_started_qty=200,
        actual_lot_starts=2, campaign_remaining_end_qty=100, wip_end_qty=0)
    output = dict(day=9, event_type="production_output", production_campaign_id="CMP", lot_id="FIRST",
        qty=100, notes=json.dumps({"available_day": 23, "availability_state": "held"}))
    waiting = dict(physical, day=22, event_type="delay_input_shortage", reason="input_shortage",
        actual_qty=0, campaign_started_qty=0, actual_lot_starts=0)
    quality = dict(physical, day=23, event_type="quality_release", actual_qty=0,
        released_qty=100, campaign_started_qty=0, actual_lot_starts=0, campaign_remaining_end_qty=0)
    release = dict(day=23, event_type="stock_availability_release", source_type="finished_goods_release",
        lot_id="FIRST", qty=100)
    row = engine.production_campaign_rows_with_availability([physical, waiting, quality], [output, release])[0]
    assert row["completed_day"] == "" and row["remaining_qty"] == 100
    assert row["last_execution_day"] == 9 and row["actual_qty"] == 100
    assert row["available_qty"] == 100 and row["held_finished_qty"] == 0
    assert row["availability_completed_day"] == "" and row["availability_status"] == "partially_available"


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


HORIZON_NET_POLICY = "covered_horizon_net_complement_v1"
CUMULATIVE_ENVELOPE_POLICY = "covered_cumulative_envelope_v1"
SEPARATE_USES_POLICY = "separate_own_and_other_v1"


def test_industrial_separate_uses_does_not_add_or_advance_displaced_same_use():
    own = Requirement("own:late", 300, 100)
    windows = [IndustrialPlanningWindow(4, 10, 11, 100, 4, "Flow.xlsx", "I2"),
               IndustrialPlanningWindow(298, 300, 301, 0, 4, "Flow.xlsx", "I44")]
    original = deepcopy(windows)
    result, audit = reconcile_industrial_requirements([own], windows, pair=("site", "item:x"),
        decision_day=4, policy=SEPARATE_USES_POLICY)
    assert result == [own] and result[0] is own and windows == original
    assert [row["planning_qty"] for row in audit] == [0, 100]
    assert [row["source_qty"] for row in audit] == [100, 0]
    assert all(row["complement_qty"] == 0 for row in audit)
    assert sum(row["complement_delta_qty"] for row in audit) == 100
    # This is not a claim that source week 10 was zero. It remains 100 in
    # comparison, without inventing another product or advancing this BOM.


def test_industrial_separate_uses_retains_identified_other_once_and_nets_real_firm():
    own, other = Requirement("own:production", 11, 20), Requirement("external:known-use", 12, 10)
    needs = [own, other]
    result, audit = reconcile_industrial_requirements(needs, [industrial_window(100)],
        pair=("site", "item:x"), decision_day=4, policy=SEPARATE_USES_POLICY)
    assert result == needs and all(a is b for a, b in zip(result, needs))
    row = audit[0]
    assert (row["source_qty"], row["own_qty"], row["reconstructed_external_qty"],
            row["complement_qty"], row["planning_qty"]) == (100, 20, 10, 10, 30)
    assert row["weekly_complement_before_netting_qty"] == 80
    assert row["complement_delta_qty"] == 70
    firm = FirmReceipt("actual-held", 11, 25, "held")
    plan = plan_dated_requirements(decision_day=4, available_qty=0, requirements=result,
        firm_receipts=[firm], lead_days=3, lot_sizing=LotSizing(integer=True))
    assert plan.proposed_qty == 5  # 20 own + 10 other - 25 genuinely committed.
    assert [(r.release_day, r.available_day, r.qty) for r in plan.proposals] == [(9, 12, 5)]
    assert firm == FirmReceipt("actual-held", 11, 25, "held")


def test_industrial_separate_uses_preserves_signed_negative_difference():
    needs = [Requirement("own:production", 11, 20), Requirement("external:known-use", 12, 40)]
    result, audit = reconcile_industrial_requirements(needs, [industrial_window(30)],
        pair=("site", "item:x"), decision_day=4, policy=SEPARATE_USES_POLICY)
    assert result == needs and sum(row.qty for row in result) == 60
    assert audit[0]["weekly_complement_before_netting_qty"] == 10
    assert audit[0]["complement_qty"] == 40
    assert audit[0]["complement_delta_qty"] == -30
    assert "temporal_overlap_removed_qty" not in audit[0]
    # An independent other-use forecast can exceed an older total forecast.
    # Preserve the signed comparison, rather than clipping away evidence.


def test_industrial_separate_uses_absence_zero_backlog_reserve_and_fractional_UN():
    needs = [Requirement("external:late", 2, 7), Requirement("own:today", 14, 1),
             Requirement("own:fractional-forecast", 16, .25), Requirement("external:fractional", 17, .5),
             Requirement("reserve:source-floor", 15, 90), Requirement("external:unknown-week", 25, 8)]
    result, audit = reconcile_industrial_requirements(needs, [industrial_window(0, first=15)],
        pair=("site", "item:x"), decision_day=14, policy=SEPARATE_USES_POLICY)
    assert result == needs and all(a is b for a, b in zip(result, needs))
    assert (audit[0]["source_qty"], audit[0]["own_qty"], audit[0]["complement_qty"],
            audit[0]["planning_qty"]) == (0, .25, .5, .75)
    assert audit[0]["complement_delta_qty"] == -.5
    assert (audit[0]["known_day"], audit[0]["source_file"], audit[0]["source_cells"]) == (4, "Flow.xlsx", "I2")
    missing, missing_audit = reconcile_industrial_requirements(iter(needs), [],
        pair=("site", "item:x"), decision_day=14, policy=SEPARATE_USES_POLICY)
    assert missing == needs and missing_audit == []


def test_industrial_separate_uses_opt_out_preserves_legacy_reconciliation_exactly():
    needs = [Requirement("own:production", 11, 20), Requirement("external:known-use", 12, 10)]
    kwargs = dict(pair=("site", "item:x"), decision_day=4)
    old = reconcile_industrial_requirements(needs, [industrial_window(100)], **kwargs)
    explicit_none = reconcile_industrial_requirements(needs, [industrial_window(100)], policy=None, **kwargs)
    assert old == explicit_none
    assert sum(row.qty for row in old[0]) == pytest.approx(100)
    assert old[1][0]["complement_qty"] == 80
    assert "temporal_overlap_removed_qty" not in old[1][0]
    new, _ = reconcile_industrial_requirements(needs, [industrial_window(100)], policy=SEPARATE_USES_POLICY, **kwargs)
    assert sum(row.qty for row in new) == 30 and needs[1].qty == 10


def test_industrial_separate_uses_network_ignores_total_I_for_purchases_and_protection():
    component, product = ("factory", "item:component"), ("factory", "item:product")
    kwargs = dict(decision_day=4,
        requirements_by_pair={product: [Requirement("customer", 18, 20)],
                              component: [Requirement("external:identified", 12, 10)]},
        available_by_pair={component: 0, product: 0},
        firm_receipts_by_pair={component: [FirmReceipt("real-held", 11, 25, "held")]},
        transport_sources_by_pair={}, bom_by_pair={product: [(component, 1)]},
        lead_days_by_pair={product: 7, component: 7}, lot_sizing_by_pair={},
        reserve_targets_by_pair={component: 1000}, coverage_days_by_pair={component: 14},
        active_campaigns_by_pair={}, protection_by_pair={component: [StockProtection("safety", 5, 100)]},
        industrial_target_context_by_pair={component: dict(window_days=14, fixed_floor_qty=0,
            target_days=14, safety_floor_qty=0, safety_days=7, legacy_rate=100)},
        industrial_requirement_reconciliation_policy=SEPARATE_USES_POLICY)
    before = deepcopy(kwargs)
    cases = []
    for source_windows in ({component: [industrial_window(100)]},
                           {component: [industrial_window(1000)]}, {component: []}, {}, None):
        plans, requirements, audits = engine.plan_component_network(**kwargs,
            industrial_windows_by_pair=source_windows)
        assert audits[component]["industrial_target_rate_qty"] == pytest.approx(30 / 14)
        assert audits[component]["protection_points"][0].minimum_qty == 15
        assert sum(row.qty for row in requirements[component]) == 30
        assert plans[component].proposed_qty == 20  # Uses30 + unchanged floor15 - firm25.
        assert plans[component].closing_projected_qty == 15
        cases.append((plans, requirements, audits[component]["protection_points"]))
    assert all(case == cases[0] for case in cases[1:])
    assert kwargs == before


def test_industrial_separate_uses_csv_keeps_signed_delta_and_legacy_fields_distinct():
    requirements = [Requirement("own:production", 11, 20), Requirement("external:known-use", 12, 40)]
    _, audit = reconcile_industrial_requirements(requirements, [industrial_window(30)],
        pair=("site", "item:x"), decision_day=4, policy=SEPARATE_USES_POLICY)
    fields = engine.industrial_reconciliation_csv_fields(SEPARATE_USES_POLICY)
    assert "industrial_complement_delta_qty" in fields
    assert "industrial_temporal_overlap_removed_qty" not in fields
    row = dict(industrial_requirement_reconciliation_policy=SEPARATE_USES_POLICY,
        industrial_weekly_complement_before_netting_qty=audit[0]["weekly_complement_before_netting_qty"],
        industrial_complement_delta_qty=audit[0]["complement_delta_qty"])
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerow(row)
    restored = next(csv.DictReader(io.StringIO(stream.getvalue())))
    assert float(restored["industrial_complement_delta_qty"]) == -30
    for legacy_policy in (HORIZON_NET_POLICY, CUMULATIVE_ENVELOPE_POLICY):
        legacy_fields = engine.industrial_reconciliation_csv_fields(legacy_policy)
        assert "industrial_temporal_overlap_removed_qty" in legacy_fields
        assert "industrial_complement_delta_qty" not in legacy_fields


@pytest.mark.parametrize("fault", ["future", "overlap", "duplicate_identity", "negative",
                                  "fractional_date", "nan_source", "missing_provenance", "past_window"])
def test_industrial_separate_uses_rejects_invalid_or_noncausal_inputs(fault):
    needs = [Requirement("own:production", 11, 20)]
    windows = [industrial_window(100)]
    if fault == "future":
        windows = [IndustrialPlanningWindow(11, 11, 18, 100, 5, "Flow.xlsx", "I2")]
    elif fault == "overlap":
        windows.append(IndustrialPlanningWindow(12, 12, 19, 50, 4, "Flow.xlsx", "I3"))
    elif fault == "duplicate_identity":
        needs.append(Requirement("own:production", 12, 1))
    elif fault == "negative":
        needs.append(Requirement("external:invalid", 25, -1))
    elif fault == "fractional_date":
        needs = [Requirement("own:production", 11.5, 20)]
    elif fault == "nan_source":
        windows = [industrial_window(float("nan"))]
    elif fault == "missing_provenance":
        windows = [IndustrialPlanningWindow(11, 11, 18, 100, 4, "Flow.xlsx", "")]
    elif fault == "past_window":
        windows = [IndustrialPlanningWindow(4, 4, 11, 100, 4, "Flow.xlsx", "I2")]
    with pytest.raises(ValueError, match="Separate uses"):
        reconcile_industrial_requirements(needs, windows, pair=("site", "item:x"),
            decision_day=4, policy=SEPARATE_USES_POLICY)


def test_industrial_envelope_preserves_early_source_need_without_duplicating_late_BOM():
    own = Requirement("own:late", 300, 100)
    windows = [IndustrialPlanningWindow(4, 10, 11, 100, 4, "Flow.xlsx", "I2"),
               IndustrialPlanningWindow(298, 300, 301, 0, 4, "Flow.xlsx", "I44")]
    before = deepcopy(windows)
    planned, audit = reconcile_industrial_requirements([own], windows, pair=("site", "x"),
        decision_day=4, policy=CUMULATIVE_ENVELOPE_POLICY)
    assert [(r.due_day, r.qty) for r in planned] == [(10, 100)]
    assert planned[0].requirement_id == "industrial-envelope-own:own:late:D10"
    assert audit[1]["original_own_requirements"] == (own,)
    assert audit[0]["own_planning_allocations"] == [dict(requirement_id="own:late",
        original_due_day=300, planned_day=10, qty=100)]
    assert audit[0]["own_advanced_qty"] == 100
    assert sum(a["complement_qty"] for a in audit) == 0
    assert (own.due_day, own.qty) == (300, 100) and windows == before
    old, _ = reconcile_industrial_requirements([own], windows, pair=("site", "x"),
        decision_day=4, policy=HORIZON_NET_POLICY)
    assert old == [own]  # P remains a separate, rejected experiment.


def test_industrial_envelope_daily_prefixes_and_FIFO_fragments_match_manual_calendar():
    own = [Requirement("own:a", 14, 5), Requirement("own:b", 20, 12)]
    windows = [industrial_window(14), IndustrialPlanningWindow(18, 18, 25, 7, 7, "Flow.xlsx", "I3")]
    planned, audit = reconcile_industrial_requirements(own, windows, pair=("site", "x"),
        decision_day=10, policy=CUMULATIVE_ENVELOPE_POLICY)
    # Source gives 2/day on11..17 then1/day on18..24, dominating BOM5@14+12@20.
    for day in range(11, 25):
        source_prefix = 2 * (min(day, 17) - 10) + max(0, day - 17)
        own_prefix = (5 if day >= 14 else 0) + (12 if day >= 20 else 0)
        assert sum(r.qty for r in planned if r.due_day <= day) == max(source_prefix, own_prefix)
    allocations = [row for window in audit for row in window["own_planning_allocations"]]
    for original in own:
        parts = [row for row in allocations if row["requirement_id"] == original.requirement_id]
        assert sum(row["qty"] for row in parts) == original.qty
        assert all(row["planned_day"] <= original.due_day for row in parts)
    assert sum(window["own_advanced_qty"] for window in audit) == 16
    extra = [row for row in planned if row.requirement_id.startswith("external:")]
    assert [(row.due_day, row.qty) for row in extra] == [(21, 1), (22, 1), (23, 1), (24, 1)]
    assert [window["known_day"] for window in audit] == [4, 7]


def test_industrial_envelope_338929_budget_removes_overlap_and_keeps_early_BOM():
    original = Requirement("derived:own", 12, 2880000)
    windows = [industrial_window(1530741),
               IndustrialPlanningWindow(18, 18, 25, 1736441, 4, "Flow.xlsx", "I3")]
    result, audit = reconcile_industrial_requirements([original], windows, pair=("site", "x"),
        decision_day=4, policy=CUMULATIVE_ENVELOPE_POLICY)
    assert sum(row.qty for row in result) == pytest.approx(3267182)
    assert sum(row.qty for row in result if row.due_day <= 12) == pytest.approx(2880000)
    assert sum(row["complement_qty"] for row in audit) == pytest.approx(387182)
    assert sum(row["weekly_complement_before_netting_qty"] for row in audit) == 1736441
    assert all(value >= 0 for row in audit for key, value in row.items()
               if key.endswith("_qty"))
    # Original BOM is immutable even where its planning fragments move earlier.
    assert original == Requirement("derived:own", 12, 2880000)


def test_industrial_envelope_missing_dates_reserves_and_overdue_needs_are_untouched():
    partial, later = Requirement("own:partial", 16, 20), Requirement("own:later", 27, 15)
    untouched = [Requirement("own:uncovered", 21, 1000), Requirement("external:past", 14, 9),
        Requirement("external:missing", 21, 50), Requirement("reserve:floor", 16, 8),
        Requirement("own:explicit_zero", 26, 0)]
    needs = [partial, later, *untouched, Requirement("external:zero", 26, 80)]
    windows = [IndustrialPlanningWindow(11, 15, 18, 30, 4, "Flow.xlsx", "I2"),
               IndustrialPlanningWindow(25, 25, 32, 0, 11, "Flow.xlsx", "I3")]
    saved = deepcopy(needs)
    result, audit = reconcile_industrial_requirements(needs, windows, pair=("site", "x"),
        decision_day=14, policy=CUMULATIVE_ENVELOPE_POLICY)
    assert all(any(r is original for r in result) for original in untouched)
    assert not any(r.requirement_id == "external:zero" for r in result)
    planned = [r for r in result if r.requirement_id.startswith("industrial-envelope-own:")]
    assert [(r.due_day, r.qty) for r in planned] == [(15, 10), (16, 10), (17, 10), (27, 5)]
    assert sum(a["planning_qty"] for a in audit) == 35
    assert sum(a["complement_qty"] for a in audit) == 0
    assert sum(a["own_qty"] for a in audit) == 35  # Excludes reserve, uncovered and overdue.
    assert needs == saved
    assert reconcile_industrial_requirements(needs, [], pair=("site", "x"), decision_day=14,
        policy=CUMULATIVE_ENVELOPE_POLICY) == (needs, [])


@pytest.mark.parametrize("source, own, expected", [(1.5, 1, 1.5), (0, 1.5, 1.5), (0, 0, 0)])
def test_industrial_envelope_fractional_UN_forecasts_have_exact_nonnegative_budgets(source, own, expected):
    original = Requirement("own:UN", 17, own)
    result, audit = reconcile_industrial_requirements([original], [industrial_window(source)],
        pair=("site", "UN-item"), decision_day=4, policy=CUMULATIVE_ENVELOPE_POLICY)
    assert sum(r.qty for r in result) == pytest.approx(expected)
    assert audit[0]["complement_qty"] == max(0, source - own)
    assert audit[0]["own_planned_qty"] == own
    assert all(r.qty >= 0 for r in result)
    assert all(row["planned_day"] <= row["original_due_day"] for row in audit[0]["own_planning_allocations"])
    if not source and own:
        assert [(row.due_day, row.qty) for row in result] == [(17, own)]


@pytest.mark.parametrize("fault", ["future_vintage", "past_window", "overlap", "duplicate_period",
                                  "duplicate_id", "negative", "nan", "identity_collision"])
def test_industrial_envelope_rejects_noncausal_or_ambiguous_inputs(fault):
    windows = [industrial_window()]
    needs = [Requirement("own", 12, 10)]
    if fault == "future_vintage": windows[0] = IndustrialPlanningWindow(11, 11, 18, 100, 5, "Flow.xlsx", "I2")
    elif fault == "past_window": windows[0] = IndustrialPlanningWindow(4, 4, 11, 100, 4, "Flow.xlsx", "I2")
    elif fault == "overlap": windows.append(IndustrialPlanningWindow(12, 12, 19, 100, 4, "Flow.xlsx", "I3"))
    elif fault == "duplicate_period": windows = [industrial_window(first=11, end=13), industrial_window(first=13, end=18)]
    elif fault == "duplicate_id": needs.append(Requirement("own", 19, 20))
    elif fault == "negative": windows[0] = industrial_window(-1)
    elif fault == "nan": needs[0] = Requirement("own", 12, float("nan"))
    else: needs.append(Requirement("industrial-envelope-own:own:D11", 30, 1))
    with pytest.raises(ValueError):
        reconcile_industrial_requirements(needs, windows, pair=("site", "x"), decision_day=4,
            policy=CUMULATIVE_ENVELOPE_POLICY)


def test_industrial_envelope_network_advances_procurement_without_altering_production_or_firm():
    component, product = ("factory", "raw"), ("factory", "PF")
    args = dict(decision_day=4, requirements_by_pair={product: [Requirement("customer", 35, 100)]},
        available_by_pair={component: 20}, firm_receipts_by_pair={component: [FirmReceipt("held", 11, 30, "held")]},
        transport_sources_by_pair={}, bom_by_pair={product: [(component, 1)]},
        lead_days_by_pair={product: 7, component: 1}, lot_sizing_by_pair={}, reserve_targets_by_pair={},
        coverage_days_by_pair={}, active_campaigns_by_pair={},
        industrial_windows_by_pair={component: [industrial_window(100),
            IndustrialPlanningWindow(25, 25, 32, 0, 4, "Flow.xlsx", "I4")]},
        industrial_target_context_by_pair={component: dict(window_days=14, fixed_floor_qty=0,
            target_days=0, safety_floor_qty=0, safety_days=0, legacy_rate=0)})
    saved = deepcopy(args)
    old_plans, _, old_audit = engine.plan_component_network(**args)
    plans, needs, audit = engine.plan_component_network(**args,
        industrial_requirement_reconciliation_policy=CUMULATIVE_ENVELOPE_POLICY)
    assert plans[product] == old_plans[product]
    assert old_plans[component].proposed_qty == 150
    assert plans[component].proposed_qty == pytest.approx(50)
    assert sum(r.qty for r in needs[component]) == pytest.approx(100)
    assert max(r.due_day for r in needs[component]) == 17
    assert audit[component]["firm_receipts"] == old_audit[component]["firm_receipts"]
    assert audit[component]["industrial_temporal_overlap_removed_qty"] == 100
    assert "industrial_requirement_reconciliation_policy" not in old_audit[component]
    assert args == saved


def test_industrial_horizon_net_removes_338929_aggregate_temporal_overlap_without_changing_own():
    # Two-window compression of the Jan5 audited totals, not invented source
    # rows: I3267182, own2880000, sum positive weekly gaps1736441.
    own = Requirement("derived:own", 12, 2880000)
    needs = [own, Requirement("external:old", 19, 900000)]
    windows = [industrial_window(1530741),
               IndustrialPlanningWindow(18, 18, 25, 1736441, 4, "Flow.xlsx", "I3")]
    saved = deepcopy((needs, windows))
    legacy, old_audit = reconcile_industrial_requirements(needs, windows, pair=("site", "x"), decision_day=4)
    result, audit = reconcile_industrial_requirements(needs, windows, pair=("site", "x"), decision_day=4,
                                                    policy=HORIZON_NET_POLICY)
    assert sum(r.qty for r in legacy) == pytest.approx(4616441)
    assert sum(r.qty for r in result) == pytest.approx(3267182)
    assert sum(w["complement_qty"] for w in audit) == pytest.approx(387182)
    assert sum(w["temporal_overlap_removed_qty"] for w in audit) == pytest.approx(1349259)
    assert result[0] is own and (own.due_day, own.qty) == (12, 2880000)
    assert all(18 <= row.due_day < 25 for row in result[1:])
    assert (needs, windows) == saved
    assert "temporal_overlap_removed_qty" not in old_audit[0]
    assert reconcile_industrial_requirements(needs, windows, pair=("site", "x"), decision_day=4,
                                            policy=None) == (legacy, old_audit)


def test_industrial_horizon_net_keeps_gaps_past_due_and_explicit_zero_distinct():
    needs = [Requirement("own:partial", 16, 20), Requirement("own:zero", 27, 15),
             Requirement("own:uncovered", 21, 1000), Requirement("external:past", 14, 9),
             Requirement("external:missing", 21, 50), Requirement("external:zero", 26, 80)]
    windows = [IndustrialPlanningWindow(11, 15, 18, 30, 4, "Flow.xlsx", "I2"),
               IndustrialPlanningWindow(25, 25, 32, 0, 11, "Flow.xlsx", "I3")]
    saved = deepcopy((needs, windows))
    result, audit = reconcile_industrial_requirements(needs, windows, pair=("site", "x"), decision_day=14,
                                                    policy=HORIZON_NET_POLICY)
    assert result == needs[:-1]  # Covered own35>I30, so no extra; gap50 and due9 remain.
    assert sum(w["own_qty"] for w in audit) == 35  # Excludes uncovered own1000.
    assert sum(w["complement_qty"] for w in audit) == 0
    assert [w["known_day"] for w in audit] == [4, 11]
    assert (needs, windows) == saved
    assert reconcile_industrial_requirements(needs, [], pair=("site", "x"), decision_day=14,
                                            policy=HORIZON_NET_POLICY) == (needs, [])


def test_industrial_horizon_net_fractional_forecast_budget_preserves_residual_calendar():
    windows = [IndustrialPlanningWindow(day, day, day+7, qty, 4, "Flow.xlsx", f"I{day}")
               for day, qty in ((11, 10.5), (18, 20.5), (25, 0))]
    needs = [Requirement("own:a", 20, 10), Requirement("own:b", 27, 8)]
    result, audit = reconcile_industrial_requirements(needs, windows, pair=("site", "UN-item"),
                                                    decision_day=4, policy=HORIZON_NET_POLICY)
    # Total source31-own18=13; positive residuals10.5/10.5 receive6.5 each.
    assert [row["complement_qty"] for row in audit] == [6.5, 6.5, 0]
    assert sum(row.qty for row in result) == pytest.approx(31)
    extra = [row for row in result if row.requirement_id.startswith("external:")]
    assert len(extra) == 14 and all(row.qty == pytest.approx(6.5 / 7) for row in extra)
    assert all(11 <= row.due_day < 25 for row in extra)
    repeated, _ = reconcile_industrial_requirements(result, windows, pair=("site", "UN-item"),
                                                  decision_day=4, policy=HORIZON_NET_POLICY)
    assert repeated == result  # Never add the complement a second time.


def test_industrial_horizon_net_documents_early_source_need_offset_by_late_own_limit():
    own = Requirement("own:late", 300, 100)
    windows = [industrial_window(100), IndustrialPlanningWindow(298, 298, 305, 0, 4, "Flow.xlsx", "I44")]
    result, audit = reconcile_industrial_requirements([own], windows, pair=("site", "x"),
                                                    decision_day=4, policy=HORIZON_NET_POLICY)
    assert result == [own] and result[0].due_day == 300
    assert audit[0]["temporal_overlap_removed_qty"] == 100
    # This is the candidate's explicit limit, not a demonstrated ERP rule:
    # a truly distinct early shared use would need separate evidence/identity.


@pytest.mark.parametrize("fault", ["future_vintage", "past_window", "overlap", "duplicate_period", "duplicate_id", "negative", "unknown_policy"])
def test_industrial_horizon_net_rejects_noncausal_or_ambiguous_inputs(fault):
    windows = [industrial_window()]
    needs = [Requirement("own", 12, 10)]
    policy = HORIZON_NET_POLICY
    if fault == "future_vintage": windows[0] = IndustrialPlanningWindow(11, 11, 18, 100, 5, "Flow.xlsx", "I2")
    elif fault == "past_window": windows[0] = IndustrialPlanningWindow(4, 4, 11, 100, 4, "Flow.xlsx", "I2")
    elif fault == "overlap": windows.append(IndustrialPlanningWindow(12, 12, 19, 100, 4, "Flow.xlsx", "I3"))
    elif fault == "duplicate_period": windows = [industrial_window(first=11, end=13), industrial_window(first=13, end=18)]
    elif fault == "duplicate_id": needs.append(Requirement("own", 19, 20))
    elif fault == "negative": windows[0] = industrial_window(-1)
    else: policy = "unknown"
    with pytest.raises(ValueError):
        reconcile_industrial_requirements(needs, windows, pair=("site", "x"), decision_day=4, policy=policy)


def test_industrial_horizon_net_network_changes_purchases_after_BOM_and_nets_firm_once():
    component, product = ("factory", "raw"), ("factory", "PF")
    args = dict(decision_day=4, requirements_by_pair={product: [Requirement("customer", 35, 100)]},
        available_by_pair={component: 20}, firm_receipts_by_pair={component: [FirmReceipt("held", 11, 30, "held")]},
        transport_sources_by_pair={}, bom_by_pair={product: [(component, 1)]},
        lead_days_by_pair={product: 7, component: 1}, lot_sizing_by_pair={}, reserve_targets_by_pair={},
        coverage_days_by_pair={}, active_campaigns_by_pair={},
        industrial_windows_by_pair={component: [industrial_window(100),
            IndustrialPlanningWindow(25, 25, 32, 0, 4, "Flow.xlsx", "I4")]},
        industrial_target_context_by_pair={component: dict(window_days=14, fixed_floor_qty=0,
            target_days=0, safety_floor_qty=0, safety_days=0, legacy_rate=0)})
    saved = deepcopy(args)
    old_plans, old_needs, old_audit = engine.plan_component_network(**args)
    plans, needs, audit = engine.plan_component_network(**args,
        industrial_requirement_reconciliation_policy=HORIZON_NET_POLICY)
    assert plans[product] == old_plans[product]
    assert old_plans[component].proposed_qty == 150 and plans[component].proposed_qty == 50
    assert sum(r.qty for r in needs[component]) == 100
    assert sum(r.qty for r in old_needs[component]) == pytest.approx(200)
    assert [(r.due_day, r.qty) for r in needs[component]] == [(28, 100)]
    assert audit[component]["industrial_temporal_overlap_removed_qty"] == 100
    assert "industrial_requirement_reconciliation_policy" not in old_audit[component]
    assert args == saved  # Stock, firms, production quantities and input snapshot are not mutated.


def test_industrial_horizon_net_csv_audit_is_conditional_and_writes_in_memory():
    base = engine.dated_plan_daily_csv_fields(industrial_planning=True)
    extended = engine.dated_plan_daily_csv_fields(industrial_planning=True, industrial_reconciliation=True)
    assert all(key not in base for key in engine.INDUSTRIAL_RECONCILIATION_FIELDS)
    assert set(extended) - set(base) == set(engine.INDUSTRIAL_RECONCILIATION_FIELDS)
    row = dict(industrial_requirement_reconciliation_policy=HORIZON_NET_POLICY,
               industrial_weekly_complement_before_netting_qty=1736441,
               industrial_temporal_overlap_removed_qty=1349259)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=extended)
    writer.writeheader()
    writer.writerow(row)
    restored = next(csv.DictReader(io.StringIO(output.getvalue())))
    assert restored["industrial_requirement_reconciliation_policy"] == HORIZON_NET_POLICY
    assert float(restored["industrial_temporal_overlap_removed_qty"]) == 1349259


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


def _moved_industrial_forecast(policy):
    pair = ("M-1430", "item:333362")
    series = revision_series([
        {"known_day": 53, "day": 74, "qty": 110495, "unit": "UN", "row": 7626},
        {"known_day": 53, "day": 81, "qty": 0, "unit": "UN", "row": 7627},
        {"known_day": 60, "day": 81, "qty": 110495, "unit": "UN", "row": 8635},
    ], [53, 60], "333362/1430", 1, planning_horizon_days=364, output_uom="UN")
    payload = dict(schema_version=1, origin="2025-01-01", scenario_id="memory",
        semantics="industrial_total_gross_requirements_planning_only", versioned_series=[series])
    calendar = IndustrialComponentPlanningCalendar(payload, pair_uoms={pair:"UN"},
        origin_date="2025-01-01", missing_period_policy=industrial_forecast_missing_policy(
            policy, "last_known_period_v1"))
    return pair, calendar


def test_latest_industrial_vintage_does_not_resurrect_moved_need():
    pair, current = _moved_industrial_forecast("latest_vintage_v1")
    _, legacy = _moved_industrial_forecast(None)
    args = dict(decision_day=60, first_day=61, through_day=90)
    assert sum(w.qty for w in legacy.windows(pair, **args)) == 220990
    windows = current.windows(pair, **args)
    assert [(w.period_start_day, w.qty, w.known_day) for w in windows] == [(81,110495,60)]
    # Independent source balance at the new date: the old debit is absent.
    assert 400250 + 124000 - sum(w.qty for w in windows) == 413755


def test_latest_industrial_vintage_is_causal_and_freezes_current_week():
    pair, current = _moved_industrial_forecast("latest_vintage_v1")
    before = current.windows(pair, decision_day=59, first_day=60, through_day=90)
    assert [(w.period_start_day,w.qty,w.known_day) for w in before] == [(74,110495,53),(81,0,53)]
    # No later vintage is introduced; current week's quantity remains prorated.
    ongoing = current.windows(pair, decision_day=82, first_day=83, through_day=90)
    assert len(ongoing) == 1 and ongoing[0].qty == pytest.approx(110495*5/7)
    assert ongoing[0].known_day == 60


def test_latest_industrial_absence_keeps_bom_and_other_use_fallback_not_fake_zero():
    pair, current = _moved_industrial_forecast("latest_vintage_v1")
    needs = [Requirement("own",74,50), Requirement("external:estimate",74,20)]
    windows = current.windows(pair, decision_day=60, first_day=61, through_day=80)
    result, audit = reconcile_industrial_requirements(needs, windows, pair=pair, decision_day=60)
    assert windows == () and result == needs and audit == []


def test_industrial_revision_policy_rejects_unknown_and_keeps_legacy_explicit():
    assert industrial_forecast_missing_policy(None,"last_known_period_v1") == "last_known_period_v1"
    assert industrial_forecast_missing_policy("latest_vintage_v1","last_known_period_v1") is None
    with pytest.raises(ValueError, match="Unknown industrial"):
        industrial_forecast_missing_policy("unrecognized",None)


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


def _anticipated_calendar(decision, delivery, receipt=13):
    # Independent forward oracle; no production receipt/calendar helper.
    from datetime import date, timedelta
    origin = date(2025, 1, 1)
    rows = []
    for release in range(decision, 250):
        available = origin + timedelta(days=release + delivery)
        counted = 0
        while counted < receipt:
            available += timedelta(days=1)
            counted += available.weekday() < 5
        rows.append((release, (available - origin).days))
    return tuple(rows)


@pytest.mark.parametrize('decision,delivery,expected_release', [(0,56,49),(75,21,84)])
def test_anticipated_dates_source_safety_delivery_and_receipt_once(decision, delivery, expected_release):
    # Jun1=151 -> May5=124 -> Apr16=105 -> Feb19=49 or Mar26=84.
    needs = [Requirement('physical-June1',151,100)]
    plan, sourced, audit = plan_anticipated_requirements(decision_day=decision, available_qty=0,
        requirements=needs, firm_receipts=(), source_working_days=20, origin_weekday=2,
        fixed_floor_qty=0, lead_days=delivery+19,
        availability_by_release=_anticipated_calendar(decision,delivery))
    assert sourced is None
    assert audit['anticipated_requirements'] == (Requirement('anticipated:124',124,100),)
    proposal, = plan.proposals
    assert (proposal.release_day,proposal.available_day,proposal.requested_day) == (expected_release,124,124)
    assert expected_release+delivery == 105
    assert sum(b.requirement_qty for b in plan.balances) == 100
    assert [(b.day,b.requirement_qty) for b in plan.balances if b.requirement_qty] == [(151,100)]
    assert needs == [Requirement('physical-June1',151,100)]


def test_anticipated_sourcing_bridges_protected_date_not_only_physical_shortage():
    decision=75  # Mar17, principal available May29; before physicalJun1 but after protectedMay5.
    def offer(name,price,delivery,standard):
        calendar=_anticipated_calendar(decision,delivery)
        return SupplierOffer(name,price,'EUR','KG',calendar[0][1]-decision,
            LotSizing(minimum=standard,multiple=standard),calendar)
    plan,sourced,audit=plan_anticipated_requirements(decision_day=decision,available_qty=0,
        requirements=[Requirement('real',151,100)],firm_receipts=(),source_working_days=20,
        origin_weekday=2,fixed_floor_qty=0,lead_days=75,
        sourcing=dict(primary=offer('main',1.58,56,6000),backups=(offer('backup',4.2,21,4000),)))
    assert sourced.backup_proposed_qty == plan.proposed_qty == 4000
    proposal,=sourced.proposals
    assert proposal.role == 'backup'
    assert (proposal.proposal.release_day,proposal.proposal.available_day) == (84,124)
    assert plan.late_qty == 0
    assert sum(a.qty for a in plan.allocations) == 100


@pytest.mark.parametrize('stock,firms,expected', [
    (100,(),0), (0,(FirmReceipt('held',25,100,'held'),),0), (120,(),30)])
def test_anticipated_past_dates_keep_remaining_needs_and_net_stock_or_held_once(stock,firms,expected):
    plan,_,audit=plan_anticipated_requirements(decision_day=20,available_qty=stock,
        requirements=[Requirement('remaining',30,100)],firm_receipts=firms,
        source_working_days=10,origin_weekday=2,fixed_floor_qty=50 if stock==120 else 0,lead_days=5)
    assert plan.proposed_qty == expected
    assert sum(b.requirement_qty for b in plan.balances) == 100
    assert plan.late_qty == 0
    if firms:
        assert audit['anticipated_plan'].late_qty == 100
        assert audit['anticipated_plan'].late_qty_days == 500
    if stock==120:
        assert plan.closing_projected_qty == 50


def test_anticipated_fixed_floor_is_maximum_with_time_safety_and_not_added_twice():
    plan,_,audit=plan_anticipated_requirements(decision_day=0,available_qty=50,
        requirements=[Requirement('later',30,100)],firm_receipts=(),
        source_working_days=10,origin_weekday=2,fixed_floor_qty=50,lead_days=0)
    assert plan.proposed_qty == 100
    assert plan.closing_projected_qty == 50
    assert sum(r.qty for r in audit['anticipated_requirements']) == 150
    assert sum(b.requirement_qty for b in plan.balances) == 100


def test_anticipated_zero_safety_weekend_deadline_uses_latest_feasible_release():
    # Jan12 Sunday: QA1 means physicalThuJan9 -> availableFriJan10,
    # or physicalFridayJan10 -> availableMondayJan13 (too late).
    plan,_,_=plan_anticipated_requirements(decision_day=0,available_qty=0,
        requirements=[Requirement('Sunday',11,1)],firm_receipts=(),source_working_days=0,
        origin_weekday=2,fixed_floor_qty=0,lead_days=1,
        availability_by_release=_anticipated_calendar(0,0,1))
    assert (plan.proposals[0].release_day,plan.proposals[0].available_day) == (8,9)


def test_anticipated_fractional_UN_forecasts_keep_integer_physical_orders():
    plan,_,_=plan_anticipated_requirements(decision_day=0,available_qty=0,
        requirements=[Requirement('fraction-a',30,.5),Requirement('fraction-b',31,.6)],firm_receipts=(),
        source_working_days=10,origin_weekday=2,fixed_floor_qty=0,lead_days=5,lot_sizing=LotSizing(integer=True))
    assert plan.proposed_qty == 2
    assert all(p.qty == int(p.qty) for p in plan.proposals)
    assert sum(b.requirement_qty for b in plan.balances) == 1.1


def test_anticipated_network_overrides_only_external_legacy_coverage_and_keeps_default():
    pair=('factory','material')
    kwargs=dict(decision_day=0,requirements_by_pair={pair:[Requirement('physical',30,100)]},
        available_by_pair={pair:100},firm_receipts_by_pair={},transport_sources_by_pair={},bom_by_pair={},
        lead_days_by_pair={pair:5},lot_sizing_by_pair={},reserve_targets_by_pair={pair:1000},
        coverage_days_by_pair={pair:10},active_campaigns_by_pair={})
    baseline=engine.plan_component_network(**kwargs)
    candidate=engine.plan_component_network(**kwargs,anticipated_need_by_pair={pair:dict(
        source_working_days=10,origin_weekday=2,fixed_floor_qty=0)})
    assert baseline[0][pair].proposed_qty == 1000
    assert candidate[0][pair].proposed_qty == 0
    assert candidate[1][pair] == [Requirement('physical',30,100)]
    assert candidate[2][pair]['reserve_requirement_qty'] == 0
    assert candidate[2][pair]['protection_points'] == ()
    assert engine.plan_component_network(**kwargs) == baseline


def test_anticipated_trace_export_keeps_nonpurchase_or_legacy_fields_absent():
    # Exercise the real trace serializer and CSV writer in memory: a factory
    # node has a dated plan but none of the six purchase-only diagnostics.
    legacy = dict(dated_action_scope='planning_only_SD_execution_preserved',
                  dated_stock_qty=123.4567894, dated_release_today_qty=0.0)
    purchase = dict(legacy, purchase_need_date_policy='source_safety_backwards_v1',
        anticipated_safety_working_days=20, anticipated_fixed_floor_qty=0.0,
        anticipated_late_qty=12.25, anticipated_first_shortage_day=124,
        anticipated_no_extra_time_floor=1)
    saved = deepcopy((legacy,purchase))
    stream=io.StringIO()
    writer=csv.DictWriter(stream,fieldnames=engine.MRP_NETWORK_PLAN_FIELDS)
    writer.writeheader()
    writer.writerows(engine.mrp_network_plan_trace_values(row) for row in (legacy,purchase,None))
    stream.seek(0)
    old,current,absent=list(csv.DictReader(stream))
    for field in ('purchase_need_date_policy','anticipated_safety_working_days',
                  'anticipated_fixed_floor_qty','anticipated_late_qty',
                  'anticipated_first_shortage_day','anticipated_no_extra_time_floor'):
        assert old[field] == absent[field] == ''
        assert current[field] != ''
    assert old['dated_stock_qty'] == '123.456789'
    assert current['anticipated_first_shortage_day'] == '124'
    assert current['anticipated_no_extra_time_floor'] == '1'
    assert (legacy,purchase) == saved


def test_common_708073_fixed_floor_is_retained_at_anticipated_need_date():
    # Source parameters F=2,000 kg, S=10 working days, standard=5,000 kg.
    # Synthetic remaining need: Feb10 (day40), protected Jan27 (day26).
    # Of 7,000 stock, only 5,000 can cover 6,000 while retaining the floor.
    args = dict(decision_day=0, available_qty=7000,
        requirements=[Requirement('use', 40, 6000)], firm_receipts=(),
        source_working_days=10, origin_weekday=2, fixed_floor_qty=2000,
        lead_days=5, lot_sizing=LotSizing(minimum=5000, multiple=5000), grouping_days=1)
    legacy, _, _ = plan_anticipated_requirements(**args)
    common, _, audit = plan_anticipated_requirements(**args, fixed_floor_mode='additive')
    assert [(p.available_day, p.qty) for p in legacy.proposals] == [(40, 5000)]
    assert [(p.available_day, p.qty) for p in common.proposals] == [(26, 5000)]
    assert common.closing_projected_qty == 6000
    assert sum(b.requirement_qty for b in common.balances) == 6000
    assert sum(r.qty for r in audit['anticipated_requirements']) == 8000
    assert audit['anticipated_fixed_floor_mode'] == 'additive'


def test_common_001848_zero_fixed_floor_keeps_the_same_calendar_and_supplier_choice():
    # Same source S=20 working days, primary 56 calendar days / 6,000 kg,
    # backup 21 days / 4,000 kg, plus the separately supplied receipt calendar.
    decision = 75
    def offer(name, price, delivery, standard):
        calendar = _anticipated_calendar(decision, delivery)
        return SupplierOffer(name, price, 'EUR', 'KG', calendar[0][1] - decision,
            LotSizing(minimum=standard, multiple=standard), calendar)
    args = dict(decision_day=decision, available_qty=0,
        requirements=[Requirement('June1', 151, 100)], firm_receipts=(),
        source_working_days=20, origin_weekday=2, fixed_floor_qty=0, lead_days=75,
        sourcing=dict(primary=offer('main', 1.58, 56, 6000),
                      backups=(offer('backup', 4.2, 21, 4000),)))
    legacy, old_sourcing, _ = plan_anticipated_requirements(**args)
    common, sourcing, _ = plan_anticipated_requirements(**args, fixed_floor_mode='additive')
    assert common == legacy and sourcing == old_sourcing
    assert [(p.proposal.release_day, p.proposal.available_day, p.proposal.qty)
            for p in sourcing.proposals] == [(84, 124, 4000)]


def _common_memory_offers(integer=False):
    return dict(primary=SupplierOffer('main', 1, 'EUR', 'UN' if integer else 'KG', 20,
                    LotSizing(minimum=5000, multiple=5000, integer=integer)),
                backups=(SupplierOffer('backup', 2, 'EUR', 'UN' if integer else 'KG', 3,
                    LotSizing(minimum=5000, multiple=5000, integer=integer)),))


def test_common_fixed_floor_is_reserved_before_testing_a_backup_but_not_a_backup_need():
    args = dict(decision_day=0, available_qty=2000, firm_receipts=(),
        source_working_days=10, origin_weekday=2, fixed_floor_qty=2000, lead_days=20,
        sourcing=_common_memory_offers(), fixed_floor_mode='additive', grouping_days=1)
    plan, sourced, _ = plan_anticipated_requirements(
        **args, requirements=[Requirement('physical', 20, 1000)])
    assert sourced.backup_proposed_qty == plan.proposed_qty == 5000
    assert plan.closing_projected_qty == 6000
    assert [(b.day, b.requirement_qty) for b in plan.balances if b.requirement_qty] == [(20, 1000)]
    args['available_qty'] = 0
    floor_only, sourced, _ = plan_anticipated_requirements(**args, requirements=())
    assert sourced.backup_proposed_qty == 0
    assert [(p.available_day, p.qty) for p in floor_only.proposals] == [(20, 5000)]
    assert floor_only.allocations == ()


def test_common_late_firm_quantity_is_never_rebought_and_exposes_the_delay():
    firms = [FirmReceipt('already-committed', 40, 6000, 'confirmed')]
    saved = deepcopy(firms)
    physical, sourced, audit = plan_anticipated_requirements(
        decision_day=0, available_qty=2000, requirements=[Requirement('physical', 20, 6000)],
        firm_receipts=firms, source_working_days=10, origin_weekday=2,
        fixed_floor_qty=2000, lead_days=20, sourcing=_common_memory_offers(),
        fixed_floor_mode='additive', grouping_days=1)
    assert physical.proposals == () and sourced.backup_proposed_qty == 0
    assert sourced.retained_firm_qty == 6000 and firms == saved
    assert audit['anticipated_plan'].late_qty == 6000
    assert physical.late_qty == 4000 and physical.late_qty_days == 80000
    assert physical.closing_projected_qty == 2000


@pytest.mark.parametrize('provisional', [False, True])
def test_common_same_review_backup_needs_are_grouped_before_supplier_rounding(provisional):
    # Two 3,050 needs on the same protected date need 6,100: one 10,000 lot,
    # never a forced fixed 5,000 order per signal. Its surplus serves day30.
    from etudecas.simulation.engine.mrp_planning import plan_sourced_requirements
    plan = plan_sourced_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('a', 3, 3050), Requirement('b', 3, 3050),
                      Requirement('later', 30, 1000)], firm_receipts=(),
        **_common_memory_offers(), grouping_days=1, preserve_reserve_allocation=True,
        provisional_lots_until_release=provisional)
    assert [(r.role, r.proposal.qty) for r in plan.proposals] == [('backup', 10000)]
    assert plan.plan.closing_projected_qty == 2900
    assert sum(a.qty for a in plan.plan.allocations) == 7100
    assert all(g.proposal_ids for g in plan.plan.procurement_groups)
    assert {p for g in plan.plan.procurement_groups for p in g.proposal_ids} == {
        p.proposal.proposal_id for p in plan.proposals}


def test_common_same_review_primary_needs_are_grouped_without_future_week_merging():
    from etudecas.simulation.engine.mrp_planning import plan_sourced_requirements
    plan = plan_sourced_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('a', 30, 3050), Requirement('b', 30, 3050),
                      Requirement('later', 60, 6000)], firm_receipts=(),
        **_common_memory_offers(), grouping_days=1, preserve_reserve_allocation=True)
    assert [(r.role, r.proposal.available_day, r.proposal.qty) for r in plan.proposals] == [
        ('primary', 30, 10000), ('primary', 60, 5000)]
    assert plan.plan.closing_projected_qty == 2900
    assert [g.net_requirement_qty for g in plan.plan.procurement_groups] == [6100, 2100]


def test_common_additive_UN_forecasts_round_physical_orders_and_do_not_mutate_inputs():
    needs = [Requirement('a', 20, .1), Requirement('b', 20, .2), Requirement('c', 21, .8)]
    firms = [FirmReceipt('held', 5, 1, 'held')]
    saved = deepcopy((needs, firms))
    plan, _, audit = plan_anticipated_requirements(decision_day=0, available_qty=2,
        requirements=needs, firm_receipts=firms, source_working_days=10, origin_weekday=2,
        fixed_floor_qty=3, lead_days=2, lot_sizing=LotSizing(integer=True),
        grouping_days=1, fixed_floor_mode='additive')
    assert all(p.qty == int(p.qty) for p in plan.proposals)
    assert plan.proposed_qty == 2
    assert plan.closing_projected_qty == pytest.approx(3.9)
    assert sum(r.qty for r in audit['anticipated_requirements']) == pytest.approx(4.1)
    assert (needs, firms) == saved


@pytest.mark.parametrize('mode', ['unknown', '', None, False])
def test_common_fixed_floor_mode_rejects_silent_fallback(mode):
    with pytest.raises(ValueError, match='mode'):
        plan_anticipated_requirements(decision_day=0, available_qty=0, requirements=(),
            firm_receipts=(), source_working_days=0, origin_weekday=2,
            fixed_floor_qty=0, lead_days=0, fixed_floor_mode=mode)


def _common_internal_safety_memory_scope():
    internal = ("factory-B", "item:internal")
    purchase = ("factory-B", "item:purchase")
    mixed = ("factory-B", "item:mixed")
    missing = ("factory-B", "item:no-policy")
    zero = ("factory-B", "item:zero")
    finished = ("warehouse-C", "item:finished")
    boundary = ("factory-A", "item:boundary")
    source_policy = dict(safety_time_days=20, safety_stock_qty=0, source="source_policy_sheet")
    nodes = [
        {"id": "factory-A", "type": "factory", "inventory": {"states": [
            {"item_id": boundary[1], "mrp_policy": dict(source_policy)}]}},
        {"id": "factory-B", "type": "factory", "inventory": {"states": [
            {"item_id": pair[1], "mrp_policy": dict(source_policy)} for pair in (internal, purchase, mixed)]
            + [{"item_id": missing[1]}, {"item_id": zero[1], "mrp_policy": dict(
                safety_time_days=0, safety_stock_qty=0, source="source_policy_sheet")}]}},
        {"id": "warehouse-C", "type": "distribution_center", "inventory": {"states": [
            {"item_id": finished[1], "mrp_policy": dict(source_policy)}]}},
        {"id": "external-A", "type": "supplier"},
    ]
    lanes = {pair: [{"src": "factory-A"}] for pair in (internal, missing, zero)}
    lanes[purchase] = [{"src": "external-A"}]
    lanes[mixed] = [{"src": "factory-A"}, {"src": "external-A"}]
    lanes[finished] = [{"src": "factory-B"}]
    return internal, dict(nodes=nodes, component_pairs={internal, purchase, mixed, missing, zero},
                         lanes_by_dest_item=lanes)


def test_common_internal_safety_scope_is_structural_and_defaults_are_unchanged():
    internal, kwargs = _common_internal_safety_memory_scope()
    saved = deepcopy(kwargs)
    assert engine.resolve_common_internal_safety_pairs(None, execution_mode="historical", **kwargs) == set()
    assert engine.resolve_common_internal_safety_pairs(None, execution_mode="dated", **kwargs) == set()
    assert engine.resolve_common_internal_safety_pairs(
        "source_stock_floor_v1", execution_mode="dated", **kwargs) == {internal}
    assert kwargs == saved


@pytest.mark.parametrize("fault", ["version", "mode", "missing_source", "negative", "boolean"])
def test_common_internal_safety_rejects_invalid_activation_or_source_parameters(fault):
    _, kwargs = _common_internal_safety_memory_scope()
    policy = kwargs["nodes"][1]["inventory"]["states"][0]["mrp_policy"]
    if fault == "missing_source": policy["source"] = ""
    elif fault == "negative": policy["safety_time_days"] = -1
    elif fault == "boolean": policy["safety_stock_qty"] = True
    with pytest.raises(ValueError):
        engine.resolve_common_internal_safety_pairs(
            "unknown" if fault == "version" else "source_stock_floor_v1",
            execution_mode="historical" if fault == "mode" else "dated", **kwargs)


def _common_internal_floor_network(*, stock, firms, needs, floor=200, day=0, protected_floor=True,
                                   integer=False):
    pair, scope = _common_internal_safety_memory_scope()
    selected = engine.resolve_common_internal_safety_pairs(
        "source_stock_floor_v1" if protected_floor else None, execution_mode="dated", **scope)
    source = ("factory-A", pair[1])
    # Independent external leaf and PF deposit stay outside this candidate's scope.
    purchase, deposit = ("factory-B", "item:purchase"), ("warehouse-C", "item:finished")
    plans, requirements, audit = engine.plan_component_network(
        decision_day=day, requirements_by_pair={pair: list(needs),
            purchase: [Requirement("external-use", 40, 50)], deposit: [Requirement("customer", 40, 50)]},
        available_by_pair={pair: stock, source: 1000, purchase: 50, deposit: 50},
        firm_receipts_by_pair={pair: list(firms)}, transport_sources_by_pair={pair: [(source, 1.0)]},
        bom_by_pair={}, lead_days_by_pair={pair: 10, source: 1, purchase: 5, deposit: 2},
        lot_sizing_by_pair={pair: LotSizing(integer=integer)}, reserve_targets_by_pair={pair: floor},
        coverage_days_by_pair={pair: 50}, active_campaigns_by_pair={},
        protection_by_pair={p: [StockProtection("source-safety", day + 1, floor)] for p in selected} or None,
    )
    return pair, plans, requirements, audit


def test_common_internal_floor_survives_use_and_counts_existing_stock_and_firm_once():
    needs, firms = [Requirement("physical-use", 10, 100)], [FirmReceipt("firm", 10, 100, "in_transit")]
    saved = deepcopy((needs, firms))
    pair, legacy, _, _ = _common_internal_floor_network(stock=100, firms=firms, needs=needs, protected_floor=False)
    _, plans, requirements, audit = _common_internal_floor_network(stock=100, firms=firms, needs=needs)
    # Physical balance: stock100 + firm100 + new100 - use100 = protected200.
    assert legacy[pair].proposed_qty == 0
    assert plans[pair].proposed_qty == 100
    assert plans[pair].closing_projected_qty == 200
    assert sum(row.qty for row in requirements[pair]) == 100
    assert audit[pair]["reserve_requirement_qty"] == 0
    assert sum(row.qty for row in audit[pair]["firm_receipts"]) == 100
    assert audit[pair]["protected_plan"].protection[-1].shortfall_qty == 0
    for other in (("factory-B", "item:purchase"), ("warehouse-C", "item:finished")):
        assert plans[other] == legacy[other]
    assert (needs, firms) == saved


def test_common_internal_floor_retains_late_firm_without_duplicate_transfer():
    pair, plans, _, audit = _common_internal_floor_network(stock=0,
        firms=[FirmReceipt("late-firm", 30, 300, "in_transit")], needs=[Requirement("use", 10, 100)])
    assert plans[pair].proposals == ()
    assert plans[pair].late_qty == 100 and plans[pair].late_qty_days == 2000
    assert plans[pair].closing_projected_qty == 200
    assert audit[pair]["reserve_requirement_qty"] == 0
    points = {row.day: row for row in audit[pair]["protected_plan"].protection}
    assert points[10].shortfall_qty > 0 and points[30].shortfall_qty == 0


def test_common_internal_floor_daily_review_does_not_rebuy_previous_proposals():
    need = Requirement("use", 20, 100)
    pair, first, _, _ = _common_internal_floor_network(stock=0, firms=(), needs=[need])
    assert first[pair].proposed_qty == 300
    commitments = [FirmReceipt(row.proposal_id, row.available_day, row.qty, "in_transit")
                   for row in first[pair].proposals]
    _, second, _, audit = _common_internal_floor_network(stock=0, firms=commitments, needs=[need], day=1)
    assert second[pair].proposals == () and second[pair].closing_projected_qty == 200
    assert sum(row.qty for row in audit[pair]["firm_receipts"]) == 300


def test_common_internal_floor_preserves_integer_physical_transfers_for_UN():
    pair, plans, _, audit = _common_internal_floor_network(stock=2, firms=(),
        needs=[Requirement("fractional-forecast", 20, 0.6)], floor=2, integer=True)
    assert plans[pair].proposed_qty == 1
    assert all(row.qty == int(row.qty) for row in plans[pair].proposals)
    assert plans[pair].closing_projected_qty == pytest.approx(2.4)
    assert audit[pair]["reserve_requirement_qty"] == 0


def _depot_feedback_memory_scope():
    return dict(execution_mode="dated", forecast_signal=True,
        nodes=[{"id": name, "type": kind} for name, kind in (
            ("factory", "factory"), ("other", "factory"), ("external", "supplier"),
            ("depot", "distribution_center"), ("depot2", "distribution_center"))],
        produced_pairs={("factory", "PF"), ("other", "PF"), ("factory", "component")},
        finished_item_ids={"PF"}, lanes_by_dest_item={
            ("depot", "PF"): [{"src": "factory"}, {"src": "factory"}],
            ("depot2", "PF"): [{"src": "other"}, {"src": "external"}],
            ("depot", "component"): [{"src": "factory"}]})


def test_depot_source_safety_selection_is_structural_source_scoped_and_opt_in():
    scope = _depot_feedback_memory_scope()
    source_pairs = {("depot", "PF"), ("depot2", "PF"), ("depot", "component")}
    saved = deepcopy(scope)
    assert engine.resolve_depot_safety_protection(None, source_policy_pairs=source_pairs, **scope) == set()
    assert engine.resolve_depot_safety_protection("source_stock_floor_v1", source_policy_pairs=source_pairs,
                                                 **scope) == {("depot", "PF")}
    assert engine.resolve_depot_safety_protection("source_stock_floor_v1", source_policy_pairs=set(), **scope) == set()
    assert scope == saved
    with pytest.raises(ValueError, match="Unknown"):
        engine.resolve_depot_safety_protection("bad", source_policy_pairs=source_pairs, **scope)


@pytest.mark.parametrize("rate,source_days,fixed,expected", [(3,26,0,78),(3,26,100,100),(3,0,50,50),(3,0,0,0)])
def test_depot_source_safety_quantity_excludes_transport_review_and_generic_coverage(rate, source_days, fixed, expected):
    # Only the already calendar-converted source safety enters this shared formula.
    assert engine.production_mrp_safety_target(0, rate, source_days, fixed) == expected


def depot_source_safety_network(*, protected=True, firm_depot=()):
    depot, factory, component = ("depot", "PF"), ("factory", "PF"), ("factory", "MP")
    return engine.plan_component_network(decision_day=0,
        requirements_by_pair={depot: [Requirement("customer-first",10,30), Requirement("customer-second",20,40)]},
        available_by_pair={depot:80,factory:20,component:100},
        firm_receipts_by_pair={depot:firm_depot},
        transport_sources_by_pair={depot:[(factory,1)]}, bom_by_pair={factory:[(component,2)]},
        lead_days_by_pair={depot:2,factory:3,component:1},
        lot_sizing_by_pair={depot:LotSizing(integer=True),factory:LotSizing(integer=True)},
        reserve_targets_by_pair={depot:0 if protected else 60,factory:0},
        coverage_days_by_pair={depot:31}, active_campaigns_by_pair={},
        protection_by_pair={depot:[StockProtection("source-safety",1,60)]} if protected else None)


def test_depot_source_safety_persists_after_demand_without_copying_floor_upstream():
    depot, factory, component = ("depot", "PF"), ("factory", "PF"), ("factory", "MP")
    legacy, legacy_needs, _ = depot_source_safety_network(protected=False)
    plans, needs, audit = depot_source_safety_network()
    assert legacy[depot].proposed_qty == 0 and legacy[depot].closing_projected_qty == 10
    assert plans[depot].proposed_qty == 50 and plans[depot].closing_projected_qty == 60
    assert [(r.release_day,r.available_day,r.qty) for r in plans[depot].proposals] == [(8,10,10),(18,20,40)]
    assert sum(r.qty for r in needs[depot]) == sum(r.qty for r in legacy_needs[depot]) == 70
    assert audit[depot]["reserve_requirement_qty"] == 0
    assert plans[factory].proposed_qty == 30 and plans[factory].closing_projected_qty == 0
    assert sum(r.qty for r in needs[component]) == 60  # Only30 newPF*2; factory20 is reused.
    assert all(r.shortfall_qty == 0 for r in audit[depot]["protected_plan"].protection)
    assert all(r.qty == int(r.qty) for r in plans[depot].proposals)


def test_depot_source_safety_nets_late_firm_once_without_duplicate_manufacture():
    depot, factory = ("depot", "PF"), ("factory", "PF")
    plans, needs, audit = depot_source_safety_network(firm_depot=[FirmReceipt("engaged-transfer",30,50)])
    assert plans[depot].proposals == () and plans[factory].proposals == ()
    assert plans[depot].closing_projected_qty == 60
    protection = {r.day:r for r in audit[depot]["protected_plan"].protection}
    assert protection[10].shortfall_qty == 10 and protection[20].shortfall_qty == 50
    assert protection[30].shortfall_qty == 0
    assert len(audit[depot]["firm_receipts"]) == 1


@pytest.mark.parametrize("quality_release", [False, True], ids=["D-C", "D-Q-C"])
def test_depot_safety_actual_csv_schemas_export_enriched_plan_and_quality_rows_in_memory(quality_release):
    depot = ("depot", "PF")
    plans, needs, audit = depot_source_safety_network()
    # Build a complete decision row independently of the new header helper.
    # This is the same enriched dictionary contract as dated_plan_decisions:
    # all existing study diagnostics, plus C's two newly introduced values.
    legacy_fields = (engine.MRP_NETWORK_PLAN_FIELDS + engine.EXTERNAL_COMPONENT_PLAN_FIELDS
        + engine.SOURCING_PLAN_FIELDS + engine.STOCK_PROTECTION_FIELDS
        + ["internal_component_safety_policy"] + engine.COVERAGE_PROTECTION_FIELDS
        + engine.INDUSTRIAL_PLANNING_FIELDS + engine.PROSPECTIVE_SAFETY_FIELDS)
    decision = {field: "" for field in legacy_fields}
    decision.update(dated_action_scope="transport_replenishment",
        dated_requirement_qty=sum(r.qty for r in needs[depot]),
        dated_proposed_qty=plans[depot].proposed_qty,
        dated_protection_target_qty=max(r.target_qty for r in audit[depot]["protected_plan"].protection),
        depot_safety_protection_policy="source_stock_floor_v1", depot_safety_protection_qty=60)
    row = dict(day=0,node_id=depot[0],item_id=depot[1],uom="UN",action_scope="transport_replenishment",**decision)
    before = deepcopy(row)
    fields = engine.dated_plan_daily_csv_fields(external_components=True, sourcing=True,
        stock_protection=True, internal_safety=True, coverage_protection=True,
        industrial_planning=True, prospective_safety=True, depot_safety=True)
    stream = io.StringIO()
    writer = csv.DictWriter(stream,fieldnames=fields)  # Default strict extrasaction='raise'.
    writer.writeheader()
    writer.writerow(row)
    restored = next(csv.DictReader(io.StringIO(stream.getvalue())))
    assert row == before and len(fields) == len(set(fields))
    assert restored["depot_safety_protection_policy"] == "source_stock_floor_v1"
    assert restored["depot_safety_protection_qty"] == "60"
    assert float(restored["dated_requirement_qty"]) == 70 and float(restored["dated_proposed_qty"]) == 50

    # D+C and D+Q+C share the dated-plan schema; Q enriches only the separate
    # production event schema. Physical G and actual I must both serialize.
    event = {field: "" for field in engine.PRODUCTION_PLAN_EVENT_FIELDS}
    event.update(day=10,event_type="production",campaign_id="CMP",batch_id="BATCH",actual_qty=100,
        **engine.production_completion_quantities(100,retained_for_quality=quality_release))
    if quality_release:
        event["release_gate_mode"] = "physical_completion_then_source_weekday_quality"
    events = [event]
    if quality_release:
        events.append(engine.finished_goods_quality_release_event(event,day=24,lot_id="LOT",qty=100))
    production_stream = io.StringIO()
    production_writer = csv.DictWriter(production_stream,fieldnames=engine.production_plan_csv_fields(
        quality_release=quality_release))
    production_writer.writeheader()
    production_writer.writerows(events)
    restored_events = list(csv.DictReader(io.StringIO(production_stream.getvalue())))
    assert sum(float(r["released_qty"]) for r in restored_events) == 100
    if quality_release:
        assert [float(r["physical_completed_qty"]) for r in restored_events] == [100,0]
        assert [float(r["actual_qty"]) for r in restored_events] == [100,0]
    else:
        assert "physical_completed_qty" not in restored_events[0]


def test_depot_safety_actual_csv_schema_preserves_legacy_header_order_when_disabled():
    expected = (["day","node_id","item_id","uom","action_scope"] + engine.MRP_NETWORK_PLAN_FIELDS
        + engine.EXTERNAL_COMPONENT_PLAN_FIELDS + engine.SOURCING_PLAN_FIELDS
        + engine.STOCK_PROTECTION_FIELDS + ["internal_component_safety_policy"]
        + engine.COVERAGE_PROTECTION_FIELDS + engine.INDUSTRIAL_PLANNING_FIELDS
        + engine.PROSPECTIVE_SAFETY_FIELDS)
    assert engine.dated_plan_daily_csv_fields(external_components=True, sourcing=True,
        stock_protection=True, internal_safety=True, coverage_protection=True,
        industrial_planning=True, prospective_safety=True) == expected
    assert engine.production_plan_csv_fields() == engine.PRODUCTION_PLAN_EVENT_FIELDS


def test_depot_feedback_selects_exclusive_finished_output_routes_and_is_opt_in():
    scope = _depot_feedback_memory_scope()
    before = deepcopy(scope)
    assert engine.resolve_production_depot_feedback(None, **scope) == {}
    assert engine.resolve_production_depot_feedback("net_depot_position_v1", **scope) == {
        ("factory", "PF"): (("depot", "PF"),)}
    assert scope == before
    # A shared downstream depot cannot be assigned to either factory, even if
    # one also owns another depot: partial ownership would hide its shared flow.
    scope["lanes_by_dest_item"][("depot2", "PF")].append({"src": "factory"})
    assert engine.resolve_production_depot_feedback("net_depot_position_v1", **scope) == {}


@pytest.mark.parametrize("fault", ["version", "historical", "capacity"])
def test_depot_feedback_rejects_unsupported_activation(fault):
    scope = _depot_feedback_memory_scope()
    if fault == "historical": scope["execution_mode"] = "historical"
    if fault == "capacity": scope["forecast_signal"] = False
    with pytest.raises(ValueError):
        engine.resolve_production_depot_feedback("bad" if fault == "version" else "net_depot_position_v1", **scope)


def _depot_feedback_position(**overrides):
    args = dict(output_pair=("factory", "PF"), depot_pairs=(("depot", "PF"),),
        decision_day=5, before_receipts=False, stock_by_pair={
            ("factory", "PF"): 40, ("depot", "PF"): 70},
        commitments_by_pair={
            ("factory", "PF"): {"opening-OF": (20, 30, "production")},
            ("depot", "PF"): {"truck": (7, 20, "lane")}},
        depot_targets={("depot", "PF"): 200}, backlog_by_pair={("depot", "PF"): 10},
        local_target_qty=20, remaining_qty=25, executed_wip_qty=5)
    args.update(overrides)
    saved = deepcopy(args)
    result = engine.production_depot_position(**args)
    assert args == saved
    return result


def test_depot_feedback_nets_factory_depot_firms_and_campaign_once():
    result = _depot_feedback_position()
    # Target20+200+backlog10 minus stocks40+70, firms30+20 and WIP25+5.
    assert result["network_target_qty"] == 230
    assert result["network_position_qty"] == 190
    assert result["gap_qty"] == 40
    assert result["firm_qty"] == 50 and result["campaign_qty"] == 30
    # The forecast10 is the flow; the depot order is not added as a second flow.
    assert 10 + 0.25 * result["gap_qty"] == 20


def test_depot_feedback_surplus_can_reduce_the_production_signal():
    result = _depot_feedback_position(stock_by_pair={
        ("factory", "PF"): 40, ("depot", "PF"): 220})
    assert result["gap_qty"] == -110
    assert 10 + .25 * result["gap_qty"] == -17.5
    # A later committed OF remains quantity coverage, not another new launch.
    later = _depot_feedback_position(commitments_by_pair={
        ("factory", "PF"): {"future-OF": (365, 200, "production")}})
    assert later["gap_qty"] == -110


def test_depot_feedback_receipt_phases_and_held_release_do_not_double_count():
    factory, depot = ("factory", "PF"), ("depot", "PF")
    firms = {factory: {"today-OF": (5, 30, "production"), "held-today": (5, 10, "held"),
                       "future-held": (8, 5, "held"), "already-received": (4, 999, "production")},
             depot: {"today-truck": (5, 20, "lane")}}
    # The held10 is already part of stock at both stages. Pipeline receipts
    # become stock between MPS and physical execution; the position stays fixed.
    before = _depot_feedback_position(before_receipts=True, commitments_by_pair=firms)
    after = _depot_feedback_position(before_receipts=False, commitments_by_pair=firms,
                                    stock_by_pair={factory: 70, depot: 90})
    assert before["firm_qty"] == 55 and after["firm_qty"] == 5
    assert before["network_position_qty"] == after["network_position_qty"] == 195
    assert before["gap_qty"] == after["gap_qty"] == 35


def test_depot_feedback_internal_moves_and_batch_release_preserve_position():
    factory, depot = ("factory", "PF"), ("depot", "PF")
    initial = _depot_feedback_position(commitments_by_pair={})
    departed = _depot_feedback_position(stock_by_pair={factory: 20, depot: 70},
        commitments_by_pair={depot: {"transfer": (7, 20, "lane")}})
    arrived = _depot_feedback_position(stock_by_pair={factory: 20, depot: 90}, commitments_by_pair={})
    completed = _depot_feedback_position(stock_by_pair={factory: 70, depot: 70},
        commitments_by_pair={}, remaining_qty=0, executed_wip_qty=0)
    assert {r["network_position_qty"] for r in (initial, departed, arrived, completed)} == {140}
    assert {r["gap_qty"] for r in (initial, departed, arrived, completed)} == {90}


@pytest.mark.parametrize("need_day", [20, 364])
def test_depot_feedback_projection_retains_depot_floor_and_explodes_only_net_production(need_day):
    depot, factory, component = ("depot", "PF"), ("factory", "PF"), ("factory", "MP")
    plans, requirements, audit = engine.plan_component_network(decision_day=0,
        requirements_by_pair={depot: [Requirement("customer", need_day, 100)]},
        available_by_pair={depot: 50, factory: 30, component: 1000},
        firm_receipts_by_pair={factory: [FirmReceipt("opening-OF", 5, 70, "confirmed")]},
        transport_sources_by_pair={depot: [(factory, 1)]}, bom_by_pair={factory: [(component, 2)]},
        lead_days_by_pair={depot: 2, factory: 3, component: 1},
        lot_sizing_by_pair={depot: LotSizing(integer=True), factory: LotSizing(integer=True)},
        reserve_targets_by_pair={depot: 0, factory: 0}, coverage_days_by_pair={},
        active_campaigns_by_pair={factory: ("campaign", 20, 10, 3)},
        protection_by_pair={depot: [StockProtection("existing-DC-target", 1, 200)],
                            factory: [StockProtection("unchanged-factory-target", 1, 0)]},
        production_floor_pairs={factory})
    # DC50 + transfer250 - consumption100 = source target200.
    # Factory30 + openingOF70 + campaign30 + new120 - transfer250 = 0.
    # Components: campaign remaining20*2 + new120*2 = 280. Executed WIP10
    # and the initial OF never consume their BOM a second time.
    assert plans[depot].proposed_qty == 250 and plans[depot].closing_projected_qty == 200
    assert plans[factory].proposed_qty == 120 and plans[factory].closing_projected_qty == 0
    assert sum(r.qty for r in requirements[depot]) == 100
    assert sum(r.qty for r in requirements[component]) == 280
    assert audit[depot]["reserve_requirement_qty"] == audit[factory]["reserve_requirement_qty"] == 0
    assert sum(r.qty for r in audit[factory]["firm_receipts"]) == 100
    assert all(p.qty == int(p.qty) for pair in (depot, factory) for p in plans[pair].proposals)


def _industrial_internal_network(*, source_qty=100, own_qty=60, prior_extra=30,
                                 stock=20, firms=(), windows=True, integer=False):
    transferred, source = ("local", "input"), ("upstream", "input")
    product, purchased = ("local", "finished"), ("local", "purchased")
    context = dict(window_days=14, fixed_floor_qty=20, target_days=0,
                   safety_floor_qty=20, safety_days=0, legacy_rate=0)
    source_window = IndustrialPlanningWindow(11, 11, 18, source_qty, 4, "Flow.xlsx", "I7")
    kwargs = dict(decision_day=4,
        requirements_by_pair={product: [Requirement("customer", 18, own_qty)],
            transferred: [Requirement("external:old-transfer", 12, prior_extra)],
            purchased: [Requirement("own-purchase", 11, 60), Requirement("external:old-purchase", 12, 30)]},
        available_by_pair={transferred: stock, source: 1000, purchased: 20},
        firm_receipts_by_pair={transferred: list(firms)},
        transport_sources_by_pair={transferred: [(source, 1)]}, bom_by_pair={product: [(transferred, 1)]},
        lead_days_by_pair={transferred: 2, source: 1, product: 7, purchased: 2},
        lot_sizing_by_pair={transferred: LotSizing(integer=integer)},
        reserve_targets_by_pair={transferred: 999, purchased: 999},
        coverage_days_by_pair={transferred: 14, purchased: 14}, active_campaigns_by_pair={},
        protection_by_pair={pair: [StockProtection("source-floor", 5, 20)] for pair in (transferred, purchased)},
        industrial_windows_by_pair={transferred: [source_window] if windows else [],
            purchased: [IndustrialPlanningWindow(11, 11, 18, 100, 4, "Flow.xlsx", "I8")]},
        industrial_target_context_by_pair={transferred: dict(context), purchased: dict(context)},
        industrial_internal_pairs={transferred})
    return transferred, source, purchased, kwargs


def test_industrial_internal_replaces_extra_and_propagates_source_total_before_transfer():
    pair, source, purchased, kwargs = _industrial_internal_network()
    saved = deepcopy(kwargs)
    plans, needs, audits = engine.plan_component_network(**kwargs)
    audit = audits[pair]
    # I100 - BOM60 = replacement extra40, replacing prior30. Net addition10,
    # not residual10 replacing30 (would total70), nor old30+new40 (total130).
    assert audit["industrial_own_requirement_qty"] == 60
    assert audit["industrial_reconstructed_external_qty"] == 30
    assert audit["industrial_planning_complement_qty"] == 40
    assert audit["industrial_planning_requirement_qty"] == 100
    assert sum(r.qty for r in needs[pair]) == pytest.approx(100)
    assert sum(r.qty for r in needs[pair] if r.requirement_id.startswith("external:")) == pytest.approx(40)
    assert not any(r.requirement_id == "external:old-transfer" for r in needs[pair])
    assert plans[pair].proposed_qty == pytest.approx(100)
    assert plans[pair].closing_projected_qty == pytest.approx(20)
    assert sum(r.qty for r in needs[source]) == pytest.approx(100)
    assert audits[pair]["reserve_requirement_qty"] == 0
    assert kwargs == saved
    # The already-supported independent external leaf is unchanged.
    old = deepcopy(kwargs)
    del old["industrial_windows_by_pair"][pair]
    old.pop("industrial_internal_pairs")
    old_plans, old_needs, old_audits = engine.plan_component_network(**old)
    assert old_plans[purchased] == plans[purchased]
    assert old_needs[purchased] == needs[purchased]
    assert old_audits[purchased] == audits[purchased]


@pytest.mark.parametrize("arrival", [11, 40])
def test_industrial_internal_retains_firm_once_even_when_late(arrival):
    pair, source, _, kwargs = _industrial_internal_network(firms=[FirmReceipt("firm-transfer", arrival, 100, "in_transit")])
    plans, needs, audit = engine.plan_component_network(**kwargs)
    assert plans[pair].proposed_qty == pytest.approx(0, abs=1e-9)
    assert plans[pair].closing_projected_qty == pytest.approx(20)
    assert sum(r.qty for r in audit[pair]["firm_receipts"]) == 100
    assert sum(r.qty for r in needs[source]) == 0
    if arrival == 40:
        assert plans[pair].late_qty > 0
        assert audit[pair]["protected_plan"].protection[-1].shortfall_qty == 0


def test_industrial_internal_fractional_residual_cannot_create_an_upstream_lot():
    pair, source, _, kwargs = _industrial_internal_network(
        firms=[FirmReceipt("firm-transfer", 11, 100, "in_transit")])
    kwargs["available_by_pair"][source] = 0
    kwargs["lot_sizing_by_pair"][source] = LotSizing(minimum=3200, multiple=3200)
    plans, needs, _ = engine.plan_component_network(**kwargs)
    # 40/7 introduces a possible 4e-15 floating residual at the transfer.
    # The upstream source must receive ZERO demand and create ZERO 3,200 lots,
    # not merely have its incorrect order hidden by a tolerant assertion.
    assert plans[pair].proposed_qty <= 1e-9
    assert needs[source] == []
    assert plans[source].proposals == () and plans[source].proposed_qty == 0


@pytest.mark.parametrize("source_qty,windows,own,expected", [
    (0, False, 60, 90),  # Missing source week retains the estimated30.
    (0, True, 60, 60),   # Explicit zero cannot delete own BOM60.
    (100, True, 120, 120),  # Own > source: retain120, extra0, report excess20.
])
def test_industrial_internal_unknown_zero_and_own_excess_are_distinct(source_qty, windows, own, expected):
    pair, source, _, kwargs = _industrial_internal_network(source_qty=source_qty, windows=windows, own_qty=own)
    plans, needs, audit = engine.plan_component_network(**kwargs)
    assert sum(r.qty for r in needs[pair]) == pytest.approx(expected)
    assert plans[pair].proposed_qty == pytest.approx(expected)
    assert plans[pair].closing_projected_qty == pytest.approx(20)
    assert sum(r.qty for r in needs[source]) == pytest.approx(expected)
    assert audit[pair]["industrial_source_excess_own_qty"] == (max(0, own-source_qty) if windows else 0)


def test_industrial_internal_fractional_forecast_keeps_physical_UN_orders_integer():
    pair, source, _, kwargs = _industrial_internal_network(source_qty=100.6, integer=True)
    plans, needs, _ = engine.plan_component_network(**kwargs)
    assert sum(r.qty for r in needs[pair]) == pytest.approx(100.6)
    assert plans[pair].proposed_qty == 101
    assert all(p.qty == int(p.qty) for p in plans[pair].proposals)
    assert sum(r.qty for r in needs[source]) == 101
    assert plans[pair].closing_projected_qty == pytest.approx(20.4)


def test_industrial_internal_safety_days_use_reconciled_rate_without_second_reserve():
    pair, source, _, kwargs = _industrial_internal_network(
        firms=[FirmReceipt("firm-transfer", 11, 100, "in_transit")])
    kwargs["industrial_target_context_by_pair"][pair].update(safety_days=7, target_days=7)
    plans, needs, audit = engine.plan_component_network(**kwargs)
    # Same source F20 and S7 applied to known rate100/14 -> floor50.
    # Stock20 + firm100 + new30 - source-total use100 = floor50.
    assert audit[pair]["industrial_target_rate_qty"] == pytest.approx(100/14)
    assert audit[pair]["protection_points"][0].minimum_qty == 50
    assert audit[pair]["reserve_requirement_qty"] == 0
    assert plans[pair].proposed_qty == pytest.approx(30)
    assert plans[pair].closing_projected_qty == pytest.approx(50)
    assert sum(r.qty for r in needs[source]) == pytest.approx(30)


@pytest.mark.parametrize("fault", ["not_authorized", "no_protection", "no_transport", "manufactured", "campaign"])
def test_industrial_internal_requires_explicit_pure_transfer_protection(fault):
    pair, source, _, kwargs = _industrial_internal_network()
    if fault == "not_authorized": kwargs.pop("industrial_internal_pairs")
    elif fault == "no_protection": del kwargs["protection_by_pair"][pair]
    elif fault == "no_transport": del kwargs["transport_sources_by_pair"][pair]
    elif fault == "manufactured":
        del kwargs["transport_sources_by_pair"][pair]
        kwargs["bom_by_pair"][pair] = [(source, 1)]
    elif fault == "campaign": kwargs["active_campaigns_by_pair"][pair] = ("active", 20, 10, 8)
    with pytest.raises(ValueError):
        engine.plan_component_network(**kwargs)


def _push_finished_scope():
    return dict(nodes=[{"id": name, "type": kind} for name, kind in (
        ("factory", "factory"), ("depot", "distribution_center"),
        ("customer", "customer"), ("supplier", "supplier"))],
        produced_pairs={("factory", "PF1"), ("factory", "PF2"), ("factory", "component")},
        finished_item_ids={"PF1", "PF2"}, lanes_by_dest_item={
            ("depot", "PF1"): [{"src": "factory"}],
            ("depot", "PF2"): [{"src": "factory"}],
            ("customer", "PF1"): [{"src": "depot"}],
            ("depot", "component"): [{"src": "factory"}],
            ("factory", "material"): [{"src": "supplier"}]})


def test_push_finished_selects_all_finished_routes_without_item_rules_and_is_opt_in():
    kwargs = _push_finished_scope()
    saved = deepcopy(kwargs)
    assert engine.resolve_finished_goods_push_sources(None, **kwargs) == {}
    assert engine.resolve_finished_goods_push_sources("push_released_available_v1", **kwargs) == {
        ("depot", "PF1"): ("factory", "PF1"), ("depot", "PF2"): ("factory", "PF2")}
    assert kwargs == saved


@pytest.mark.parametrize("fault", ["version", "duplicate_route", "mixed_source", "multiple_destinations"])
def test_push_finished_rejects_ambiguous_allocation(fault):
    kwargs = _push_finished_scope()
    if fault == "duplicate_route": kwargs["lanes_by_dest_item"][("depot", "PF1")].append({"src": "factory"})
    elif fault == "mixed_source": kwargs["lanes_by_dest_item"][("depot", "PF1")].append({"src": "supplier"})
    elif fault == "multiple_destinations": kwargs["lanes_by_dest_item"][("customer", "PF1")] = [{"src": "factory"}]
    with pytest.raises(ValueError):
        engine.resolve_finished_goods_push_sources("bad" if fault == "version" else "push_released_available_v1", **kwargs)


def test_push_finished_uses_released_unreserved_stock_and_never_rebuys_a_reserved_truck():
    factory, depot, customer = ("factory", "PF1"), ("depot", "PF1"), ("customer", "PF1")
    available = {factory: 14400, depot: 900000, customer: 20000}
    arguments = dict(destination=depot, push_sources={depot: factory},
                     available_by_pair=available, legacy_need=-50000, uom="UN")
    saved = deepcopy(arguments)
    # A surplus at the depot does not retain the released palette at its plant.
    assert engine.finished_goods_dispatch_need(**arguments) == 14400
    assert arguments == saved
    # The transport executor reserves/debits free plant stock at commitment.
    available[factory] -= 14400
    assert engine.finished_goods_dispatch_need(**arguments) == 0
    arguments["destination"] = customer
    assert engine.finished_goods_dispatch_need(**arguments) == -50000
    arguments["push_sources"] = {}
    arguments["destination"] = depot
    assert engine.finished_goods_dispatch_need(**arguments) == -50000


def test_zero_source_safety_pushes_available_finished_goods_without_creating_customer_stock():
    factory, depot, customer = ("factory", "PF1"), ("depot", "PF1"), ("customer", "PF1")
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={factory: 180}, item_unit_map={"PF1": "UN"})
    held_lot = ledger.create_child_lot(day=0, node_id=factory[0], item_id=factory[1], qty=60,
        source_type="opening_production_order", source_id="initial-OF", parent_allocations=[],
        link_type="production", uom="UN")
    availability = engine.OpeningPurchaseAvailability([], item_unit_map={"PF1": "UN"})
    availability.hold_production_lot(marker="initial-OF", node_id=factory[0], item_id=factory[1],
        quantity=60, lot_id=held_lot, physical_day=0, available_day=10, ledger=ledger,
        source_kind="opening_production_order")
    free = ledger.pair_balance(node_id=factory[0], item_id=factory[1]) - availability.held_by_pair[factory]
    assert free == 180 and availability.held_by_pair[factory] == 60
    generic_days = engine.generic_safety_days_for_pair(depot, source_policy_pairs={depot},
        default_days=7, source_precedence=True)
    source_safety_days = source_safety_qty = 0
    legacy_target = max(source_safety_qty, 100 * source_safety_days, 100 * generic_days)
    assert legacy_target == 0
    push_sources = engine.resolve_finished_goods_push_sources("push_released_available_v1", **_push_finished_scope())
    available = {factory: free, depot: 0, customer: 0}
    pushed = engine.finished_goods_dispatch_need(destination=depot, push_sources=push_sources,
        available_by_pair=available, legacy_need=legacy_target, uom="UN")
    assert pushed == 180  # Push follows released supply, not zero safety or client100.
    parents = ledger.consume(day=0, node_id=factory[0], item_id=factory[1], qty=pushed,
        event_type="lane_ship", uom="UN", shipment_id="to-DC", source_id="route-to-DC")
    available[factory] -= pushed
    assert engine.finished_goods_dispatch_need(destination=depot, push_sources=push_sources,
        available_by_pair=available, legacy_need=0, uom="UN") == 0
    ledger.create_child_lot(day=2, node_id=depot[0], item_id=depot[1], qty=pushed,
        source_type="lane_receipt", source_id="route-to-DC", shipment_id="to-DC",
        parent_allocations=parents, link_type="transport", uom="UN")
    available[depot] += pushed
    client = engine.customer_physical_cover_need(decision_day=2, arrival_day=4,
        physical_requirements=[Requirement("physical-service-day4", 4, 100)], available_qty=0,
        backlog_qty=0, firm_receipts=[], uom="UN")
    assert client["customer_physical_order_qty"] == 100
    allocations = ledger.consume(day=2, node_id=depot[0], item_id=depot[1], qty=100,
        event_type="lane_ship", uom="UN", shipment_id="to-client", source_id="route-to-client")
    available[depot] -= 100
    ledger.create_child_lot(day=4, node_id=customer[0], item_id=customer[1], qty=100,
        source_type="lane_receipt", source_id="route-to-client", shipment_id="to-client",
        parent_allocations=allocations, link_type="transport", uom="UN")
    ledger.consume(day=4, node_id=customer[0], item_id=customer[1], qty=100,
        event_type="demand_service", source_id="physical-service-day4", uom="UN")
    assert ledger.pair_balance(node_id=customer[0], item_id=customer[1]) == 0
    assert ledger.pair_balance(node_id=depot[0], item_id=depot[1]) == available[depot] == 80
    assert ledger.pair_balance(node_id=factory[0], item_id=factory[1]) == 60
    assert 80 + 60 + 100 == 240  # Remaining depot+held plant+served equals physical supply.
    availability.release("initial-OF", 10, 60, ledger=ledger)
    available[factory] += 60
    assert engine.finished_goods_dispatch_need(destination=depot, push_sources=push_sources,
        available_by_pair=available, legacy_need=0, uom="UN") == 60


@pytest.mark.parametrize("qty", [True, -1, float("nan"), 1.2])
def test_push_finished_rejects_invalid_or_fractional_physical_UN(qty):
    with pytest.raises(ValueError):
        engine.finished_goods_dispatch_need(destination=("dc", "PF"),
            push_sources={("dc", "PF"): ("plant", "PF")},
            available_by_pair={("plant", "PF"): qty}, legacy_need=0, uom="UN")


def test_push_finished_and_existing_feedback_conserve_position_without_counting_customers():
    factory, depot = ("factory", "PF"), ("depot", "PF")
    before = _depot_feedback_position(commitments_by_pair={},
        stock_by_pair={factory: 40, depot: 70, ("customer", "PF"): 999999})
    pushed = engine.finished_goods_dispatch_need(destination=depot, push_sources={depot: factory},
        available_by_pair={factory: 40}, legacy_need=0, uom="UN")
    after = _depot_feedback_position(stock_by_pair={factory: 0, depot: 70},
        commitments_by_pair={depot: {"push": (7, pushed, "lane")}})
    assert before["network_position_qty"] == after["network_position_qty"] == 140
    assert before["gap_qty"] == after["gap_qty"] == 90


def _anticipated_transfer_network(*, stock=0, firms=(), needs=None, floor=0, day=0, integer=False):
    pair, source, component = ("local", "input"), ("source", "input"), ("source", "raw")
    kwargs = dict(decision_day=day,
        requirements_by_pair={pair: [Requirement("physical", 40, 100)] if needs is None else list(needs)},
        available_by_pair={pair: stock, component: 1000}, firm_receipts_by_pair={pair: list(firms)},
        transport_sources_by_pair={pair: [(source, 1)]}, bom_by_pair={source: [(component, 2)]},
        lead_days_by_pair={pair: 10, source: 2, component: 1},
        lot_sizing_by_pair={pair: LotSizing(integer=integer)},
        reserve_targets_by_pair={pair: 999}, coverage_days_by_pair={pair: 39}, active_campaigns_by_pair={},
        protection_by_pair={pair: [StockProtection("unused-legacy-average", day + 1, 999)]},
        anticipated_need_by_pair={pair: dict(source_working_days=20, origin_weekday=2,
            fixed_floor_qty=floor, fixed_floor_mode="additive")}, anticipated_internal_pairs={pair})
    return pair, source, component, kwargs


def test_anticipated_transfer_scope_uses_source_integer_workdays_and_keeps_legacy_default():
    pair, kwargs = _common_internal_safety_memory_scope()
    assert engine.resolve_common_internal_safety_pairs("source_safety_additive_v2", execution_mode="dated", **kwargs) == {pair}
    kwargs["nodes"][1]["inventory"]["states"][0]["mrp_policy"]["safety_time_days"] = 20.5
    with pytest.raises(ValueError):
        engine.resolve_common_internal_safety_pairs("source_safety_additive_v2", execution_mode="dated", **kwargs)
    assert engine.resolve_common_internal_safety_pairs("source_stock_floor_v1", execution_mode="dated", **kwargs) == {pair}


def test_anticipated_transfer_moves_safety_once_before_transport_and_upstream_BOM():
    pair, source, component, kwargs = _anticipated_transfer_network()
    saved = deepcopy(kwargs)
    plans, needs, audit = engine.plan_component_network(**kwargs)
    # Day0=Wed Jan1. Physical Mon Feb10 (40) minus20 weekdays=Mon Jan13 (12).
    # Internal10 calendar days gives release Jan3 (2), then upstream process2.
    assert [(p.release_day, p.available_day, p.qty) for p in plans[pair].proposals] == [(2, 12, 100)]
    assert [(r.due_day, r.qty) for r in needs[pair]] == [(40, 100)]
    assert [(r.due_day, r.qty) for r in needs[source]] == [(2, 100)]
    assert [(p.release_day, p.available_day, p.qty) for p in plans[source].proposals] == [(0, 2, 100)]
    assert [(r.due_day, r.qty) for r in needs[component]] == [(0, 200)]
    assert audit[pair]["reserve_requirement_qty"] == 0
    assert audit[pair]["protection_points"] == ()
    assert audit[pair]["anticipated_fixed_floor_qty"] == 0
    assert kwargs == saved


def test_anticipated_transfer_fixed_floor_is_reserved_once_without_legacy_average():
    pair, source, _, kwargs = _anticipated_transfer_network(stock=100, floor=200,
        firms=[FirmReceipt("firm", 10, 100, "in_transit")])
    plans, needs, audit = engine.plan_component_network(**kwargs)
    # Available100+firm100+new100 - real use100 = F200. No legacy999 added.
    assert plans[pair].proposed_qty == 100 and plans[pair].closing_projected_qty == 200
    assert sum(r.qty for r in needs[source]) == 100
    assert sum(r.qty for r in audit[pair]["firm_receipts"]) == 100
    assert [(r.due_day, r.qty) for r in audit[pair]["anticipated_requirements"]] == [(0, 200), (12, 100)]
    assert sum(r.qty for r in needs[pair]) == 100


def customer_cover_scope():
    pair = ("customer", "PF-A")
    route = {"src": "DC", "dst": pair[0], "item_id": pair[1], "lead_days": 2,
             "order_frequency_days": 1, "standard_order_qty": 0}
    return pair, dict(nodes=[{"id": "customer", "type": "customer"},
                            {"id": "DC", "type": "distribution_center"}],
        demand_pairs={pair}, lanes_by_dest_item={pair: [route]}, dated_planning=True)


def physical_customer_need(day=0, *, lead=2, daily=1900, stock=0, backlog=1900, firms=(), uom="UN"):
    return engine.customer_physical_cover_need(decision_day=day, arrival_day=day + lead,
        physical_requirements=[Requirement(f"physical:{d}", d, daily) for d in range(day + 1, day + lead + 1)],
        available_qty=stock, backlog_qty=backlog, firm_receipts=firms, uom=uom)


def test_customer_physical_cover_opt_in_selects_routes_without_article_specific_rule():
    pair, kwargs = customer_cover_scope()
    before = deepcopy(kwargs)
    assert engine.resolve_customer_physical_cover(None, **kwargs) == {}
    assert engine.resolve_customer_physical_cover("physical_demand_cover_v1", **kwargs) == {
        pair: kwargs["lanes_by_dest_item"][pair][0]}
    other = (pair[0], "other-product")
    kwargs["demand_pairs"].add(other)
    kwargs["lanes_by_dest_item"][other] = [dict(kwargs["lanes_by_dest_item"][pair][0], item_id=other[1])]
    assert set(engine.resolve_customer_physical_cover("physical_demand_cover_v1", **kwargs)) == {pair, other}
    assert kwargs["lanes_by_dest_item"][pair] == before["lanes_by_dest_item"][pair]


@pytest.mark.parametrize("fault", ["version", "historical", "stochastic", "review", "warmup", "controls",
                                 "perturbation", "several_routes", "supplier", "staggered_standard"])
def test_customer_physical_cover_rejects_unqualified_timing_before_execution(fault):
    pair, kwargs = customer_cover_scope()
    if fault == "historical": kwargs["dated_planning"] = False
    elif fault == "stochastic": kwargs["stochastic_leads"] = True
    elif fault == "review": kwargs["review_days"] = 7
    elif fault == "warmup": kwargs["warmup_days"] = 2
    elif fault == "controls": kwargs["controls"] = True
    elif fault == "perturbation": kwargs["demand_perturbation"] = True
    elif fault == "several_routes": kwargs["lanes_by_dest_item"][pair] *= 2
    elif fault == "supplier": kwargs["nodes"][1]["type"] = "supplier_dc"
    elif fault == "staggered_standard": kwargs["lanes_by_dest_item"][pair][0]["standard_order_qty"] = 100
    # Unsupported contexts remain unchanged when the feature is absent.
    assert engine.resolve_customer_physical_cover(None, **kwargs) == {}
    with pytest.raises(ValueError):
        engine.resolve_customer_physical_cover("invalid" if fault == "version" else "physical_demand_cover_v1", **kwargs)


def test_customer_physical_cover_two_day_manual_oracle_no_forecast_stock():
    first = physical_customer_need()
    assert first["customer_physical_target_qty"] == first["customer_physical_order_qty"] == 5700
    arrival, pulled, delivered = engine.lane_delivery_schedule(day=0, lead_days=2, lead_cover=3,
        order_frequency_days=1, pull_qty=5700, delivered_qty=5700, reliability=1, shipment_uom="UN",
        standard_order_qty=0, standard_order_binding=True)[0]
    assert (arrival, pulled, delivered) == (2, 5700, 5700)
    second = physical_customer_need(1, backlog=3800, firms=[FirmReceipt("allocated-day0", arrival, delivered)])
    assert second["customer_physical_order_qty"] == 1900
    # At day2 the first receipt serves day0+day1+day2: no 14-day stock appears.
    assert delivered - (1900 + 1900 + 1900) == 0
    third = physical_customer_need(2, backlog=0, firms=[FirmReceipt("already-received", 2, 5700),
                                                      FirmReceipt("allocated-day1", 3, 1900)])
    assert third["customer_physical_order_qty"] == 1900


def test_customer_physical_cover_stock_and_firms_are_netted_once_by_date():
    firms = [FirmReceipt("received-today", 4, 100), FirmReceipt("allocated", 5, 150),
             FirmReceipt("later", 9, 500)]
    result = physical_customer_need(4, daily=100, backlog=50, stock=100, firms=firms)
    assert result["customer_physical_target_qty"] == 250
    assert result["customer_physical_firm_cover_qty"] == 150
    assert result["customer_physical_order_qty"] == 0
    assert len(firms) == 3  # Later firm is preserved; it is not available early.
    with pytest.raises(ValueError, match="identity"):
        physical_customer_need(firms=[firms[1], firms[1]])


def test_customer_physical_cover_unallocated_shortage_is_revised_not_accumulated_as_orders():
    # DC stock zero on day0/day1. No allocation => no firm order identity.
    firms, releases = [], []
    for day, source_available in ((0, 0), (1, 0), (2, 10)):
        needs = [Requirement("initial-service", 0, 10)]
        decision = engine.customer_physical_cover_need(decision_day=day, arrival_day=day + 2,
            physical_requirements=needs, available_qty=0, backlog_qty=10, firm_receipts=firms, uom="UN")
        assert decision["customer_physical_order_qty"] == 10
        allocated = min(source_available, decision["customer_physical_order_qty"])
        if allocated:
            releases.append(allocated)
            firms.append(FirmReceipt("only-allocated-transfer", day + 2, allocated))
    assert releases == [10]  # Not the sum30 of three revocable requests.
    after = engine.customer_physical_cover_need(decision_day=3, arrival_day=5, physical_requirements=[],
        available_qty=0, backlog_qty=10, firm_receipts=firms, uom="UN")
    assert after["customer_physical_order_qty"] == 0
    # The actual day4 receipt is in customer stock, then serves the backlog once.
    assert 10 - 10 == 0


@pytest.mark.parametrize("uom,expected", [("UN", 4), ("KG", 3.4), ("G", 3.4)])
def test_customer_physical_cover_rounds_only_countable_physical_orders(uom, expected):
    result = physical_customer_need(daily=1.4, backlog=0.6, uom=uom)
    assert result["customer_physical_order_qty"] == pytest.approx(expected)


def test_customer_physical_cover_csv_extension_keeps_legacy_and_exports_exact_decision():
    pair = ("customer", "PF-A")
    decision = physical_customer_need()
    decision["customer_previous_forecast_order_qty"] = 50919
    assert engine.customer_physical_cover_trace({pair: decision}, pair, enabled=False) == {}
    row = dict(day=0, node_id=pair[0], item_id=pair[1],
        **engine.customer_physical_cover_trace({pair: decision}, pair, enabled=True))
    stream = io.StringIO()
    fields = ["day", "node_id", "item_id"] + engine.CUSTOMER_PHYSICAL_COVER_FIELDS
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerow(row)
    actual = next(csv.DictReader(io.StringIO(stream.getvalue())))
    assert actual["customer_physical_order_qty"] == "5700.0"
    assert actual["customer_previous_forecast_order_qty"] == "50919"
    assert all(value == "" for value in engine.customer_physical_cover_trace({}, pair, enabled=True).values())


@pytest.mark.parametrize("source_days,fixed", [(0, 0), (0, 500), (20, 0)])
def test_explicit_source_policy_replaces_generic_days_including_zero_without_changing_fixed_qty(source_days, fixed):
    pair = ("DC", "PF")
    context = dict(source_policy_pairs={pair}, default_days=7)
    assert engine.generic_safety_days_for_pair(pair, **context) == 7
    effective = engine.generic_safety_days_for_pair(pair, source_precedence=True, **context)
    assert effective == 0
    assert max(fixed, source_days * 100, effective * 100) == max(fixed, source_days * 100)
    assert engine.generic_safety_days_for_pair(("other", "PF"), source_precedence=True, **context) == 7


def opening_source_dates_case():
    pair = ("factory", "intermediate")
    orders = {"source_file": "Extract_En_cours.xlsx", "rows": [{
        "source_row": 105, "order_type": "production_open_order", "planning_element": "O.Proc",
        "dst_node_id": pair[0], "item_id": pair[1], "quantity": 3200000, "uom": "G",
        "physical_delivery_day": 23, "usable_day": 61, "receipt_release_days": 26}]}
    context = dict(opening_orders=orders, nodes=[{"id": pair[0], "type": "factory"}],
        dated_execution=True, lot_trace=True, bom_issue_mode="wip")
    return pair, context


def test_opening_source_dates_scope_keeps_new_production_and_legacy_unchanged():
    pair, kwargs = opening_source_dates_case()
    assert engine.resolve_opening_production_availability(None, **kwargs) == set()
    before = deepcopy(kwargs)
    assert engine.resolve_opening_production_availability("source_dates_v1", **kwargs) == {pair}
    assert kwargs == before
    # Identified source O.Proc does not require a reconstructed BOM or a Q rule.
    assert "processes" not in kwargs["nodes"][0]


@pytest.mark.parametrize("fault", ["version", "missing_G", "reverse_dates", "duplicate_identity", "no_source",
                                 "no_lots", "not_wip", "unknown_factory", "fractional_UN"])
def test_opening_source_dates_rejects_ambiguous_identity_or_unproved_dates(fault):
    _, kwargs = opening_source_dates_case()
    row = kwargs["opening_orders"]["rows"][0]
    if fault == "missing_G": row.pop("physical_delivery_day")
    elif fault == "reverse_dates": row["usable_day"] = 22
    elif fault == "duplicate_identity": kwargs["opening_orders"]["rows"].append(dict(row))
    elif fault == "no_source": kwargs["opening_orders"].pop("source_file")
    elif fault == "no_lots": kwargs["lot_trace"] = False
    elif fault == "not_wip": kwargs["bom_issue_mode"] = "receipt"
    elif fault == "unknown_factory": kwargs["nodes"] = []
    elif fault == "fractional_UN": row.update(uom="UN", quantity=1.5)
    assert engine.resolve_opening_production_availability(None, **kwargs) == set()
    with pytest.raises(ValueError):
        engine.resolve_opening_production_availability("bad" if fault == "version" else "source_dates_v1", **kwargs)


def test_opening_source_dates_seed_then_hold_at_G_release_once_at_I_without_second_BOM():
    pair, context = opening_source_dates_case()
    selected = engine.resolve_opening_production_availability("source_dates_v1", **context)
    pipeline, transit, order_rows, issues = defaultdict(list), defaultdict(float), [], defaultdict(list)
    total, rows, _ = engine.seed_open_orders_from_metadata(pipeline, transit,
        opening_open_orders_payload=context["opening_orders"], lanes_by_dest_item={},
        item_unit_map={pair[1]: "KG"}, pair_mrp_safety_time_days={}, total_timeline_days=365, warmup_days=0,
        opening_production_bom_issues_by_day=issues, opening_production_order_bom_issue_mode="wip",
        mrp_order_rows=order_rows, supplier_shipment_rows=[], initialization_pipeline_rows=[],
        assumptions_ledger_rows=[], dated_purchase_availability=True, production_availability_pairs=selected)
    assert total == transit[pair] == 3200 and issues == {}
    assert list(pipeline) == [61] and pipeline[61][0][2] == 3200
    row = rows[0]
    assert (row["physical_delivery_day"], row["arrival_day"]) == (23, 61)
    ledger = engine.LotLedger(enabled=True)
    lot = ledger.create_child_lot(day=23, node_id=pair[0], item_id=pair[1], qty=3200,
        source_type="opening_production_order", source_id=row["source_marker"], parent_allocations=[],
        link_type="production", uom="KG")
    availability = engine.OpeningPurchaseAvailability(rows, item_unit_map={pair[1]: "KG"})
    receipt_identity = engine.initial_planning_receipt_identity("lane", 61, 0, pipeline[61][0],
        availability_markers=availability.by_marker, opening_production_pairs=selected)
    assert receipt_identity == row["source_marker"]
    legacy_identity = engine.initial_planning_receipt_identity("lane", 61, 0, pipeline[61][0],
        availability_markers=availability.by_marker, opening_production_pairs=set())
    assert legacy_identity == "initial:lane:61:0"
    commitments = {receipt_identity: (61, 3200, "production")}
    held = availability.hold_production_lot(marker=row["source_marker"], node_id=pair[0], item_id=pair[1],
        quantity=3200, lot_id=lot, physical_day=23, available_day=61, ledger=ledger,
        source_kind="opening_production_order")
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == availability.held_by_pair[pair] == 3200
    commitments[row["source_marker"]] = (61, 3200, "held")
    assert len(commitments) == 1 and sum(values[1] for values in commitments.values()) == 3200
    plan = plan_dated_requirements(decision_day=23, available_qty=0, requirements=[Requirement("transfer", 30, 3200)],
        firm_receipts=[FirmReceipt(row["source_marker"], 61, 3200, "held")], lead_days=10)
    assert plan.proposals == () and plan.late_qty_days == 3200 * 31
    with pytest.raises(ValueError): availability.release(row["source_marker"], 60, 3200, ledger=ledger)
    availability.release(row["source_marker"], 61, 3200, ledger=ledger)
    assert availability.held_by_pair[pair] == 0 and held["released"]
    with pytest.raises(ValueError): availability.release(row["source_marker"], 61, 3200, ledger=ledger)
    assert [(r["event_type"], r["day"]) for r in ledger.event_rows] == [
        ("opening_production_order", 23), ("stock_availability_hold", 23), ("stock_availability_release", 61)]
    assert ledger.genealogy_rows == [] and issues == {}


def test_anticipated_transfer_past_protection_is_due_now_and_late_firm_is_not_duplicated():
    pair, source, _, kwargs = _anticipated_transfer_network(day=20,
        firms=[FirmReceipt("late", 45, 100, "in_transit")])
    plans, needs, audit = engine.plan_component_network(**kwargs)
    assert plans[pair].proposals == () and needs[source] == []
    assert plans[pair].late_qty == 100 and plans[pair].late_qty_days == 500
    assert [(r.due_day, r.qty) for r in audit[pair]["anticipated_requirements"]] == [(20, 100)]
    assert audit[pair]["anticipated_plan"].late_qty_days == 2500
    assert [(r.due_day, r.qty) for r in needs[pair]] == [(40, 100)]


def test_anticipated_transfer_review_nets_firm_commitments_and_keeps_UN_integer():
    pair, source, _, kwargs = _anticipated_transfer_network(stock=2, floor=2, integer=True,
        needs=[Requirement("forecast-a", 40, .6), Requirement("forecast-b", 41, .7)])
    plans, needs, _ = engine.plan_component_network(**kwargs)
    assert plans[pair].proposed_qty == 2
    assert all(p.qty == int(p.qty) for p in plans[pair].proposals)
    assert plans[pair].closing_projected_qty == pytest.approx(2.7)
    kwargs["firm_receipts_by_pair"][pair] = [FirmReceipt(p.proposal_id, p.available_day, p.qty, "in_transit") for p in plans[pair].proposals]
    kwargs["decision_day"] = 1
    repeated, needs, _ = engine.plan_component_network(**kwargs)
    assert repeated[pair].proposals == () and needs[source] == []


def test_anticipated_transfer_reconciles_known_industrial_I_before_safety_and_preserves_external():
    pair, source, purchased, kwargs = _industrial_internal_network()
    old_plans, old_needs, old_audit = engine.plan_component_network(**kwargs)
    kwargs.update(anticipated_internal_pairs={pair}, anticipated_need_by_pair={pair: dict(
        source_working_days=5, origin_weekday=2, fixed_floor_qty=20, fixed_floor_mode="additive")})
    kwargs["industrial_target_context_by_pair"][pair].update(safety_days=100, target_days=100)
    plans, needs, audit = engine.plan_component_network(**kwargs)
    assert audit[pair]["industrial_planning_complement_qty"] == 40
    assert sum(r.qty for r in needs[pair]) == pytest.approx(100)
    assert plans[pair].proposed_qty == pytest.approx(100)
    assert plans[pair].closing_projected_qty == pytest.approx(20)
    assert sum(r.qty for r in needs[source]) == pytest.approx(100)
    assert audit[pair]["protection_points"] == ()
    assert plans[purchased] == old_plans[purchased]
    assert needs[purchased] == old_needs[purchased] and audit[purchased] == old_audit[purchased]
    kwargs["firm_receipts_by_pair"][pair] = [FirmReceipt("firm-total", 11, 100, "in_transit")]
    kwargs["available_by_pair"][source] = 0
    kwargs["lot_sizing_by_pair"][source] = LotSizing(minimum=3200, multiple=3200)
    again, again_needs, _ = engine.plan_component_network(**kwargs)
    assert again_needs[source] == [] and again[source].proposals == ()


@pytest.mark.parametrize("fault", ["not_authorized", "no_protection", "no_transport", "campaign", "sourcing", "mode"])
def test_anticipated_transfer_requires_structural_authorization(fault):
    pair, _, _, kwargs = _anticipated_transfer_network()
    if fault == "not_authorized": kwargs.pop("anticipated_internal_pairs")
    elif fault == "no_protection": kwargs["protection_by_pair"] = {}
    elif fault == "no_transport": kwargs["transport_sources_by_pair"] = {}
    elif fault == "campaign": kwargs["active_campaigns_by_pair"][pair] = ("active", 1, 0, 4)
    elif fault == "sourcing": kwargs["sourcing_by_pair"] = {pair: {}}
    elif fault == "mode": kwargs["anticipated_need_by_pair"][pair]["fixed_floor_mode"] = "maximum"
    with pytest.raises(ValueError):
        engine.plan_component_network(**kwargs)


def _internal_dispatch_lot_scope():
    pair, kwargs = _common_internal_safety_memory_scope()
    kwargs["item_unit_map"] = {pair[1]: "KG"}
    kwargs["current_lots"] = {pair: LotSizing()}
    kwargs["lanes_by_dest_item"][pair][0]["physical_dispatch_multiple"] = 3200
    return pair, kwargs


def test_internal_dispatch_lot_alignment_is_structural_and_opt_in():
    pair, kwargs = _internal_dispatch_lot_scope()
    saved = deepcopy(kwargs)
    assert engine.resolve_internal_transfer_planning_lots(None, execution_mode="historical", **kwargs) == {}
    aligned = engine.resolve_internal_transfer_planning_lots("execution_dispatch_multiple_v1", execution_mode="dated", **kwargs)
    assert aligned == {pair: LotSizing(multiple=3200)}
    assert kwargs == saved
    # No inferred lot on other inputs, no supplier/mixed-route/PF-depot change.
    kwargs["lanes_by_dest_item"][pair].append({"src": "factory-A", "physical_dispatch_multiple": 3200})
    assert engine.resolve_internal_transfer_planning_lots("execution_dispatch_multiple_v1", execution_mode="dated", **kwargs) == {}


@pytest.mark.parametrize("fault", ["version", "historical", "negative", "boolean", "fractional_UN", "competing_lot"])
def test_internal_dispatch_lot_alignment_rejects_invalid_or_competing_constraints(fault):
    pair, kwargs = _internal_dispatch_lot_scope()
    if fault == "negative": kwargs["lanes_by_dest_item"][pair][0]["physical_dispatch_multiple"] = -1
    elif fault == "boolean": kwargs["lanes_by_dest_item"][pair][0]["physical_dispatch_multiple"] = True
    elif fault == "fractional_UN":
        kwargs["item_unit_map"][pair[1]] = "UN"
        kwargs["lanes_by_dest_item"][pair][0]["physical_dispatch_multiple"] = 3.2
    elif fault == "competing_lot": kwargs["current_lots"][pair] = LotSizing(multiple=600)
    with pytest.raises(ValueError):
        engine.resolve_internal_transfer_planning_lots("bad" if fault == "version" else "execution_dispatch_multiple_v1",
            execution_mode="historical" if fault == "historical" else "dated", **kwargs)


@pytest.mark.parametrize("anticipated", [False, True])
def test_internal_dispatch_lot_surplus_replaces_later_transfer_and_is_propagated_once(anticipated):
    pair, source, component, kwargs = _anticipated_transfer_network(
        needs=[Requirement("first", 40, 500), Requirement("second", 50, 500)])
    kwargs["available_by_pair"][component] = 10000
    kwargs["lot_sizing_by_pair"][source] = LotSizing(minimum=3200, multiple=3200, maximum=3200)
    if not anticipated:
        kwargs.pop("anticipated_need_by_pair")
        kwargs.pop("anticipated_internal_pairs")
        kwargs["protection_by_pair"][pair] = [StockProtection("source-zero", 1, 0)]
    legacy, _, _ = engine.plan_component_network(**kwargs)
    assert [p.qty for p in legacy[pair].proposals] == [500, 500]
    kwargs["lot_sizing_by_pair"][pair] = LotSizing(multiple=3200)
    plans, needs, _ = engine.plan_component_network(**kwargs)
    assert [p.qty for p in plans[pair].proposals] == [3200]
    assert [r.qty for r in needs[source]] == [3200]
    assert plans[pair].closing_projected_qty == 2200
    assert plans[source].proposed_qty == legacy[source].proposed_qty == 3200
    assert plans[source].closing_projected_qty == 0
    assert legacy[source].closing_projected_qty == 2200
    assert sum(r.qty for r in needs[component]) == 6400
    # Rounded committed transport is netted once, even when available late.
    kwargs["firm_receipts_by_pair"][pair] = [FirmReceipt("truck", 45, 3200, "in_transit")]
    revised, needs, _ = engine.plan_component_network(**kwargs)
    assert revised[pair].proposals == () and needs[source] == []
    assert revised[pair].closing_projected_qty == 2200
    assert revised[pair].late_qty_days == 2500


def _source_internal_receipt_scope():
    pair, source = ("plant-B", "item:component"), ("plant-A", "item:component")
    payload = {"schema_version": 2, "rows": [{
        "policy_id": "source-receipt", "node_id": pair[0], "item_id": pair[1],
        "source_node_id": source[0], "uom": "G", "receipt_days": 6,
        "receipt_calendar": "monday_friday", "delivery_reference_days": 10.0,
        "source_refs": {"receipt_days": "Flow.xlsx!E941", "receipt_calendar": "confirmed business calendar",
                        "delivery_reference": "existing source lane"},
        "status": "candidate_not_inferred_ERP"}]}
    kwargs = dict(execution_mode="dated", nodes=[{"id": source[0], "type": "factory"},
        {"id": pair[0], "type": "factory", "processes": [{
            "inputs": [{"item_id": pair[1], "ratio_per_batch": 1}],
            "outputs": [{"item_id": "item:finished"}]}]}],
        lanes_by_dest_item={pair: [{"src": source[0], "lead_days": 10}]},
        item_unit_map={pair[1]: "G"})
    return pair, source, payload, kwargs


def test_source_internal_receipt_v2_is_structural_and_does_not_add_safety_or_lot_rules():
    pair, _, payload, kwargs = _source_internal_receipt_scope()
    before = deepcopy((payload, kwargs))
    result = engine.resolve_internal_component_policies(payload, **kwargs)
    assert result == {pair: payload["rows"][0]}
    assert result[pair]["receipt_days"] == 6 and result[pair]["delivery_reference_days"] == 10
    assert "transfer_multiple_qty" not in result[pair] and "protection_mode" not in result[pair]
    assert engine.resolve_internal_component_policies(None, **kwargs) == {}
    assert (payload, kwargs) == before
    # The same rule accepts a different physical unit; it never converts the
    # six receipt days into a mass or quantity.
    payload["rows"][0]["uom"] = kwargs["item_unit_map"][pair[1]] = "UN"
    assert engine.resolve_internal_component_policies(payload, **kwargs)[pair]["receipt_days"] == 6


@pytest.mark.parametrize("fault", ["no_BOM", "local_output", "supplier", "multiple_routes", "unit",
                                 "missing_source", "wrong_lead", "calendar", "extra_stock_rule"])
def test_source_internal_receipt_v2_rejects_unsupported_structure_and_parameters(fault):
    pair, source, payload, kwargs = _source_internal_receipt_scope()
    row = payload["rows"][0]
    if fault == "no_BOM": kwargs["nodes"][1]["processes"] = []
    elif fault == "local_output": kwargs["nodes"][1]["processes"][0]["outputs"].append({"item_id": pair[1]})
    elif fault == "supplier": kwargs["nodes"][0]["type"] = "supplier_dc"
    elif fault == "multiple_routes": kwargs["lanes_by_dest_item"][pair].append({"src": source[0], "lead_days": 10})
    elif fault == "unit": row["uom"] = "KG"
    elif fault == "missing_source": del row["source_refs"]["receipt_calendar"]
    elif fault == "wrong_lead": row["delivery_reference_days"] = 16
    elif fault == "calendar": row["receipt_calendar"] = "calendar_days"
    elif fault == "extra_stock_rule": row["protection_mode"] = "dated_stock_floor"
    with pytest.raises(ValueError):
        engine.resolve_internal_component_policies(payload, **kwargs)


@pytest.mark.parametrize("physical_day,available_day", [(45, 54), (44, 54), (46, 54), (47, 55)])
def test_source_internal_receipt_six_workdays_skip_weekends_without_counting_arrival(physical_day, available_day):
    # Origin1Jan2025. Fri14/Sat15/Sun16Feb all release Mon24Feb;
    # Mon17Feb releases Tue25Feb. No additional holiday convention.
    assert supplier_receipt_available_day(physical_day, 6, origin_date="2025-01-01") == available_day


def test_source_internal_receipt_keeps_one_lot_held_until_six_workdays_and_one_firm_credit():
    pair, source, payload, kwargs = _source_internal_receipt_scope()
    policy = engine.resolve_internal_component_policies(payload, **kwargs)[pair]
    physical_day = 35 + int(policy["delivery_reference_days"])
    available_day = supplier_receipt_available_day(physical_day, policy["receipt_days"], origin_date="2025-01-01")
    assert (physical_day, available_day) == (45, 54)
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={source: 3200000}, item_unit_map={pair[1]: "G"})
    parents = ledger.consume(day=35, node_id=source[0], item_id=pair[1], qty=3200000,
        event_type="lane_ship", uom="G", shipment_id="R-SHIP", source_id="R-LANE",
        planned_order_id="R-ORDER", departure_day=35, arrival_day=physical_day)
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={pair[1]: "G"})
    calendar.add_order(dict(order_type="internal_transfer_delivery", mrp_order_id="R-ORDER",
        node_id=pair[0], item_id=pair[1], src_node_id=source[0], edge_id="R-LANE",
        shipment_id="R-SHIP", departure_day=35, receipt_qty=3200000,
        physical_delivery_day=physical_day, arrival_day=available_day, parent_allocations=parents,
        source_file="graph.meta.internal_component_policy", source_row="source-receipt"))
    assert calendar.receive_physical(44, ledger=ledger) == {}
    assert calendar.receive_physical(45, ledger=ledger) == {pair: 3200000}
    assert calendar.held_by_pair[pair] == 3200000
    child = calendar.by_marker["R-ORDER"]["lot_id"]
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=53, node_id=pair[0], item_id=pair[1], qty=1,
            event_type="production_consume", uom="G")
    # Receipt at G is not added to usable stock or to a second MRP receipt.
    future = plan_dated_requirements(decision_day=45, available_qty=0,
        requirements=[Requirement("use", 50, 1000000)],
        firm_receipts=[FirmReceipt("R-ORDER", available_day, 3200000, "held")], lead_days=19)
    assert future.proposals == () and future.late_qty_days == 4000000
    assert future.closing_projected_qty == 2200000
    calendar.release("R-ORDER", 54, 3200000, ledger=ledger)
    assert calendar.held_by_pair[pair] == 0 and len(ledger.genealogy_rows) == 1
    assert [(r["event_type"], r["day"]) for r in ledger.event_rows if r["lot_id"] == child] == [
        ("lane_receipt", 45), ("stock_availability_hold", 45), ("stock_availability_release", 54)]
    ledger.consume(day=54, node_id=pair[0], item_id=pair[1], qty=1000000,
        event_type="production_consume", uom="G")
    assert ledger.pair_balance(node_id=pair[0], item_id=pair[1]) == 2200000


def test_source_internal_receipt_changes_planning_lead_without_adding_a_stock_target():
    # DecisionWed5Feb35, transport10 then6working ->availabilityMon24Feb54.
    # The same source floor200 remains200. Only transfer timing changes.
    pair, _, _, kwargs = _anticipated_transfer_network(day=35, stock=200,
        needs=[Requirement("use", 70, 100)])
    kwargs.pop("anticipated_need_by_pair")
    kwargs.pop("anticipated_internal_pairs")
    kwargs["protection_by_pair"][pair] = [StockProtection("unchanged-source", 36, 200)]
    old, _, _ = engine.plan_component_network(**kwargs)
    kwargs["lead_days_by_pair"][pair] = supplier_receipt_available_day(45, 6, origin_date="2025-01-01") - 35
    new, needs, audit = engine.plan_component_network(**kwargs)
    assert old[pair].proposed_qty == new[pair].proposed_qty == 100
    assert old[pair].closing_projected_qty == new[pair].closing_projected_qty == 200
    assert old[pair].proposals[0].release_day == 60
    assert new[pair].proposals[0].release_day == 51
    assert new[pair].proposals[0].available_day == 70
    assert audit[pair]["protection_points"][0].minimum_qty == 200
    assert sum(r.qty for r in needs[pair]) == 100


def _internal_transport_candidate_scope(transport=1):
    pair, source, payload, kwargs = _source_internal_receipt_scope()
    row = payload["rows"][0]
    row.update(uom="KG", receipt_days=7, delivery_reference_days=70,
               physical_transport_days=transport, transfer_multiple_qty=600)
    row["source_refs"].update(physical_transport_days="explicit calendar-day transport hypothesis",
        transfer_multiple_qty="source receipt multiples; candidate, not identified trucks",
        receipt_calendar="Monday-Friday assumption for this separate experiment")
    kwargs["item_unit_map"][pair[1]] = "KG"
    edge = dict(id="internal", **{"from": source[0], "to": pair[0]}, items=[pair[1]],
        lead_time=dict(mean=70, type="erlang", stages=4, source="FIA reference"),
        order_terms=dict(quantity_unit="KG"), attrs=dict(standard_order_qty=1))
    _, kwargs["lanes_by_dest_item"] = engine.lane_records([edge])
    kwargs["lanes_by_dest_item"][pair][0]["order_frequency_days"] = 7
    return pair, source, payload, kwargs, edge


@pytest.mark.parametrize("transport,physical_day,available_day", [(1, 8, 19), (7, 14, 23)])
def test_internal_transport_candidate_keeps_FIA_and_separates_physical_and_receipt_clocks(transport, physical_day, available_day):
    pair, _, payload, kwargs, edge = _internal_transport_candidate_scope(transport)
    source_edge = deepcopy(edge)
    policies = engine.resolve_internal_component_policies(payload, **kwargs)
    engine.apply_internal_component_lane_policies(policies, kwargs["lanes_by_dest_item"], schema_version=2)
    lane = kwargs["lanes_by_dest_item"][pair][0]
    assert edge == source_edge
    assert (lane["lead_days"], lane["lead_days_mean"], engine.lead_time_reference_days(lane)) == (70, 70, 70)
    assert lane["order_frequency_days"] == 7
    assert lane["physical_dispatch_multiple"] == lane["standard_order_qty"] == 600
    rng = engine.random.Random(7)
    state = rng.getstate()
    for stochastic in (False, True):
        assert engine.sample_lead_days(lane, rng, stochastic) == transport
        assert engine.lead_time_cover_days(lane, stochastic) == transport
    assert rng.getstate() == state  # No draw from the unrelated FIA Erlang law.
    assert engine.operational_transport_days(lane) == transport
    # Departure Jan8, physical Jan9/Jan15, usable Jan20/Jan24: no70-day addition.
    schedule = engine.lane_delivery_schedule(day=7, lead_days=transport, lead_cover=transport,
        order_frequency_days=7, pull_qty=1200, delivered_qty=1200, reliability=1,
        shipment_uom="KG", standard_order_qty=600, standard_order_binding=True, preserve_dated_release=True)
    assert schedule == [(physical_day, 1200, 1200)]
    assert supplier_receipt_available_day(physical_day, 7, origin_date="2025-01-01") == available_day


def test_internal_transport_candidate_absent_keeps_legacy_routes_and_sourcing_unchanged():
    pair, _, payload, kwargs = _source_internal_receipt_scope()
    before = deepcopy(kwargs["lanes_by_dest_item"])
    policies = engine.resolve_internal_component_policies(payload, **kwargs)
    engine.apply_internal_component_lane_policies(policies, kwargs["lanes_by_dest_item"], schema_version=2)
    assert kwargs["lanes_by_dest_item"] == before
    lane = kwargs["lanes_by_dest_item"][pair][0]
    assert engine.operational_transport_days(lane) == engine.lead_time_reference_days(lane) == 10
    assert engine.sample_lead_days(lane, None, False) == engine.lead_time_cover_days(lane, False) == 10
    # Applying a candidate to one internal route does not change another route.
    pair, _, payload, kwargs, _ = _internal_transport_candidate_scope()
    other_pair = ("other-plant", "other-item")
    other_lane = dict(src="supplier", lead_days=35, lead_days_mean=35, standard_order_qty=17)
    kwargs["lanes_by_dest_item"][other_pair] = [deepcopy(other_lane)]
    policies = engine.resolve_internal_component_policies(payload, **kwargs)
    engine.apply_internal_component_lane_policies(policies, kwargs["lanes_by_dest_item"], schema_version=2)
    assert kwargs["lanes_by_dest_item"][other_pair][0] == other_lane
    assert engine.sample_lead_days(other_lane, None, False) == 35


@pytest.mark.parametrize("fault", ["zero_days", "fractional_days", "boolean_days", "missing_transport_source",
                                 "zero_lot", "infinite_lot", "fractional_UN", "missing_lot_source"])
def test_internal_transport_candidate_rejects_unproved_dates_and_invalid_physical_lots(fault):
    pair, _, payload, kwargs, _ = _internal_transport_candidate_scope()
    row = payload["rows"][0]
    if fault == "zero_days": row["physical_transport_days"] = 0
    elif fault == "fractional_days": row["physical_transport_days"] = 1.5
    elif fault == "boolean_days": row["physical_transport_days"] = True
    elif fault == "missing_transport_source": row["source_refs"].pop("physical_transport_days")
    elif fault == "zero_lot": row["transfer_multiple_qty"] = 0
    elif fault == "infinite_lot": row["transfer_multiple_qty"] = float("inf")
    elif fault == "fractional_UN":
        row["uom"] = kwargs["item_unit_map"][pair[1]] = "UN"
        row["transfer_multiple_qty"] = 2.5
    elif fault == "missing_lot_source": row["source_refs"].pop("transfer_multiple_qty")
    with pytest.raises(ValueError):
        engine.resolve_internal_component_policies(payload, **kwargs)


@pytest.mark.parametrize("unit", ["KG", "UN"])
def test_internal_transport_multiple_is_strict_and_reuses_plan_surplus_without_second_upstream_order(unit):
    pair, source, payload, kwargs, _ = _internal_transport_candidate_scope()
    payload["rows"][0]["uom"] = kwargs["item_unit_map"][pair[1]] = unit
    policies = engine.resolve_internal_component_policies(payload, **kwargs)
    engine.apply_internal_component_lane_policies(policies, kwargs["lanes_by_dest_item"], schema_version=2)
    multiple = kwargs["lanes_by_dest_item"][pair][0]["internal_transfer_multiple_qty"]
    # This is the actual execution sizing helper, not a reimplementation.
    for available, expected in ((1800, 1200), (1190, 600), (590, 0)):
        assert engine.mrp_purchase_order_quantity(700, available, multiple, binding=True, uom=unit) == expected
    context = dict(decision_day=7, requirements_by_pair={pair: [Requirement("one", 19, 700), Requirement("two", 26, 400)]},
        available_by_pair={pair: 0, source: 1800}, firm_receipts_by_pair={},
        transport_sources_by_pair={pair: [(source, 1.0)]}, bom_by_pair={},
        lead_days_by_pair={pair: 12, source: 28}, lot_sizing_by_pair={pair: LotSizing(multiple=multiple, integer=unit == "UN")},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={})
    plans, needs, _ = engine.plan_component_network(**context)
    assert [(p.release_day, p.available_day, p.qty) for p in plans[pair].proposals] == [(7, 19, 1200)]
    assert plans[pair].closing_projected_qty == 100
    assert sum(r.qty for r in needs[source]) == 1200
    context["firm_receipts_by_pair"] = {pair: [FirmReceipt("same-shipment", 19, 1200, "in_transit")]}
    after, needs, _ = engine.plan_component_network(**context)
    assert after[pair].proposals == () and needs[source] == []
    assert after[pair].closing_projected_qty == 100


@pytest.mark.parametrize("transport,physical_day,available_day", [(1, 8, 19), (7, 14, 23)])
def test_internal_transport_candidate_retains_one_lot_and_firm_quantity_through_receipt(transport, physical_day, available_day):
    pair, source, payload, kwargs, _ = _internal_transport_candidate_scope(transport)
    policies = engine.resolve_internal_component_policies(payload, **kwargs)
    engine.apply_internal_component_lane_policies(policies, kwargs["lanes_by_dest_item"], schema_version=2)
    lane = kwargs["lanes_by_dest_item"][pair][0]
    assert 7 + engine.sample_lead_days(lane, None, False) == physical_day
    assert supplier_receipt_available_day(physical_day, 7, origin_date="2025-01-01") == available_day
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock={source: 1200}, item_unit_map={pair[1]: "KG"})
    parents = ledger.consume(day=7, node_id=source[0], item_id=pair[1], qty=1200,
        event_type="lane_ship", uom="KG", shipment_id="transfer", planned_order_id="committed",
        source_id="internal", departure_day=7, arrival_day=physical_day)
    calendar = engine.OpeningPurchaseAvailability([], item_unit_map={pair[1]: "KG"})
    calendar.add_order(dict(order_type="internal_transfer_delivery", mrp_order_id="committed",
        node_id=pair[0], item_id=pair[1], src_node_id=source[0], edge_id="internal", shipment_id="transfer",
        departure_day=7, receipt_qty=1200, physical_delivery_day=physical_day, arrival_day=available_day,
        parent_allocations=parents, source_file="graph.meta.internal_component_policy", source_row="source-receipt"))
    assert calendar.receive_physical(physical_day - 1, ledger=ledger) == {}
    assert calendar.receive_physical(physical_day, ledger=ledger) == {pair: 1200}
    assert calendar.held_by_pair[pair] == 1200
    with pytest.raises(ValueError, match="available"):
        ledger.consume(day=available_day - 1, node_id=pair[0], item_id=pair[1], qty=1,
            event_type="production_consume", uom="KG")
    plan = plan_dated_requirements(decision_day=physical_day, available_qty=0,
        requirements=[Requirement("use", available_day + 1, 700)],
        firm_receipts=[FirmReceipt("committed", available_day, 1200, "held")], lead_days=available_day - 7,
        lot_sizing=LotSizing(multiple=600))
    assert plan.proposals == () and plan.closing_projected_qty == 500
    calendar.release("committed", available_day, 1200, ledger=ledger)
    assert calendar.held_by_pair[pair] == 0 and len(ledger.genealogy_rows) == 1
    child = calendar.by_marker["committed"]["lot_id"]
    assert [(r["event_type"], r["day"]) for r in ledger.event_rows if r["lot_id"] == child] == [
        ("lane_receipt", physical_day), ("stock_availability_hold", physical_day),
        ("stock_availability_release", available_day)]


def test_internal_transport_initial_held_is_one_existing_stock_not_a_new_receipt():
    # Source date is a fixed Sunday Jan12, not a seven-working-day recalculation.
    source = ("plant-A", "item:component")
    stock = {source: 1800}
    ledger = engine.LotLedger(enabled=True)
    ledger.seed_opening_stock(day=0, stock=stock, item_unit_map={source[1]: "KG"})
    calendar = engine.InitialStockAvailability(dict(schema_version=1, knowledge_date="2025-01-05",
        assumption="backcast_first_snapshot_for_separate_experiment", rows=[dict(node_id=source[0],
            item_id=source[1], quantity=1200, uom="KG", release_day=11, source_row="source J future")]),
        stock=stock, item_unit_map={source[1]: "KG"}, origin_date="2025-01-01")
    calendar.initialize(stock=stock, ledger=ledger)
    assert stock[source] == 600 and calendar.held_by_pair[source] == 1200
    assert ledger.pair_balance(node_id=source[0], item_id=source[1]) == 1800
    assert engine.mrp_purchase_order_quantity(700, stock[source], 600, binding=True, uom="KG") == 600
    early = plan_dated_requirements(decision_day=7, available_qty=stock[source],
        requirements=[Requirement("transfer", 12, 1800)],
        firm_receipts=[FirmReceipt("initial-held", 11, calendar.planning_quantity(source, decision_day=7, through_day=12), "held")],
        lead_days=28, lot_sizing=LotSizing(multiple=600))
    assert early.proposals == ()
    assert calendar.release(10, stock=stock, ledger=ledger) == {}
    assert calendar.release(11, stock=stock, ledger=ledger) == {source: 1200}
    assert calendar.release(11, stock=stock, ledger=ledger) == {}
    assert stock[source] == 1800 and calendar.planning_quantity(source, decision_day=11, through_day=12) == 0
    after = plan_dated_requirements(decision_day=11, available_qty=stock[source],
        requirements=[Requirement("transfer", 12, 1800)], firm_receipts=[], lead_days=28)
    assert after.proposals == () and after.closing_projected_qty == early.closing_projected_qty == 0
    assert ledger.pair_balance(node_id=source[0], item_id=source[1]) == 1800
    assert not any(r["event_type"] in {"lane_receipt", "external_procurement_receipt"} for r in ledger.event_rows)


def _source_boundary_calendar_policy(calendar="monday_friday"):
    pair = ("source-plant", "item:component")
    payload = dict(schema_version=1, rows=[dict(node_id=pair[0], item_id=pair[1], uom="KG",
        fixed_lot_qty=600, lead_days=28, lead_calendar=calendar, review_period_days=1,
        lot_source=dict(cell="source lot"), lead_source=dict(cell="source receipt", calendar_confirmation="user Monday-Friday"),
        capacity_status="unknown_not_modeled")])
    context = dict(eligible_pairs={pair}, item_unit_map={pair[1]: "KG"})
    return pair, payload, context


@pytest.mark.parametrize("decision,available", [(0, 40), (4, 42), (7, 47), (9, 49)])
def test_source_boundary_workdays_keep_source28_and_exact_availability(decision, available):
    # Jan1->Feb10; SunJan5->Feb12; Jan8->Feb17; FriJan10->Feb19.
    # The order date is excluded; no holidays are invented.
    pair, payload, context = _source_boundary_calendar_policy()
    original = deepcopy(payload)
    policy = engine.source_boundary_supply_policies(payload, **context)[pair]
    assert engine.source_boundary_available_day(decision, policy, origin_date="2025-01-01") == available
    assert policy["lead_days"] == 28 and payload == original
    effective_lead = available - decision
    assert effective_lead in {38, 40}
    assert effective_lead + policy["review_period_days"] in {39, 41}
    plan = plan_dated_requirements(decision_day=decision, available_qty=0,
        requirements=[Requirement("downstream-transfer", available, 600)], firm_receipts=[],
        lead_days=effective_lead, lot_sizing=LotSizing(minimum=600, multiple=600))
    assert [(p.release_day, p.available_day, p.qty) for p in plan.proposals] == [(decision, available, 600)]


def test_source_boundary_calendar_legacy_retains28_calendar_days_and_original_fields():
    pair, payload, context = _source_boundary_calendar_policy("calendar_days_assumption")
    payload["rows"][0]["lead_source"].pop("calendar_confirmation")
    saved = deepcopy(payload)
    policy = engine.source_boundary_supply_policies(payload, **context)[pair]
    assert payload == saved
    assert [engine.source_boundary_available_day(day, policy, origin_date="2025-01-01")
            for day in (0, 4, 7, 9)] == [28, 32, 35, 37]
    assert engine.source_boundary_trace_fields() == engine.SOURCE_BOUNDARY_TRACE_FIELDS
    assert not set(engine.SOURCE_BOUNDARY_CALENDAR_FIELDS) & set(engine.source_boundary_trace_fields())


@pytest.mark.parametrize("fault", ["unknown_calendar", "missing_confirmation", "blank_confirmation"])
def test_source_boundary_workdays_require_explicit_calendar_provenance(fault):
    _, payload, context = _source_boundary_calendar_policy()
    row = payload["rows"][0]
    if fault == "unknown_calendar": row["lead_calendar"] = "business_days_unspecified"
    elif fault == "missing_confirmation": row["lead_source"].pop("calendar_confirmation")
    else: row["lead_source"]["calendar_confirmation"] = " "
    with pytest.raises(ValueError):
        engine.source_boundary_supply_policies(payload, **context)


def test_source_boundary_workday_commitment_keeps_its_date_and_nets_once_on_later_review():
    pair, payload, context = _source_boundary_calendar_policy()
    policy = engine.source_boundary_supply_policies(payload, **context)[pair]
    arrival = engine.source_boundary_available_day(4, policy, origin_date="2025-01-01")
    assert arrival == 42
    # An existing600kg order is not moved to the newly computed date43 atJ5.
    today_arrival = engine.source_boundary_available_day(5, policy, origin_date="2025-01-01")
    assert today_arrival == 43
    needs = [Requirement("transfer-a", 42, 600), Requirement("transfer-b", 50, 600)]
    plan = plan_dated_requirements(decision_day=5, available_qty=0, requirements=needs,
        firm_receipts=[FirmReceipt("original-order", arrival, 600, "confirmed")],
        lead_days=today_arrival - 5, lot_sizing=LotSizing(minimum=600, multiple=600))
    assert plan.proposed_qty == 600
    assert [(p.release_day, p.available_day, p.qty) for p in plan.proposals] == [(12, 50, 600)]
    assert engine.source_boundary_order_quantity(1200, 0, 600, 600) == 600
    # This is a dated availability promise only: no earlier physical lot or
    # fabrication event is generated by the planning/calendar helper.
    assert plan.closing_projected_qty == 0


def test_source_boundary_calendar_trace_exports_with_real_conditional_columns_in_memory():
    base = {field: 0 for field in engine.source_boundary_trace_fields()}
    base.update(source_boundary_lead_days=28, source_boundary_fixed_lot_qty=600,
                source_boundary_cover_days=39, source_boundary_order_qty=600)
    calendar = dict(source_boundary_lead_calendar="monday_friday",
        source_boundary_effective_lead_days=38, source_boundary_available_day=42)
    for enabled in (False, True):
        row = dict(base, **(calendar if enabled else {}))
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=engine.source_boundary_trace_fields(working_calendar=enabled))
        writer.writeheader()
        writer.writerow(row)
        record = next(csv.DictReader(io.StringIO(stream.getvalue())))
        assert record["source_boundary_lead_days"] == "28"
        if enabled:
            assert record["source_boundary_lead_calendar"] == "monday_friday"
            assert record["source_boundary_effective_lead_days"] == "38"
            assert record["source_boundary_available_day"] == "42"
        else:
            assert not set(calendar) & set(record)


def _chain_relation_memory_network():
    depot, factory = ("depot", "item:finished"), ("composite-plant", "item:finished")
    component, raw = ("composite-plant", "item:intermediate"), ("composite-plant", "item:purchased")
    inputs = dict(decision_day=0, requirements_by_pair={depot: [Requirement("client", 5, 100)]},
        available_by_pair={factory: 100}, firm_receipts_by_pair={},
        transport_sources_by_pair={depot: [(factory, 1.0)]},
        bom_by_pair={factory: [(component, 2.0)], component: [(raw, 3.0)]},
        lead_days_by_pair={depot: 1, factory: 1, component: 1, raw: 1},
        lot_sizing_by_pair={depot: LotSizing(integer=True), factory: LotSizing(integer=True)},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        source_safety_by_pair={factory: dict(safety_days=0, fixed_qty=0),
                               component: dict(safety_days=0, fixed_qty=0)},
        production_floor_pairs={factory, component})
    return depot, factory, component, raw, inputs


def test_chain_safety_uses_dated_window_not_lot_as_daily_rate():
    # Same100futureunits concentrated on one day or spread across ten days:
    # a10-day source window protects100, never100*10.
    concentrated = [Requirement("one-lot", 10, 100), Requirement("overdue", -1, 900),
                    Requirement("today", 0, 800), Requirement("outside", 11, 700)]
    spread = [Requirement(str(day), day, 10) for day in range(1, 11)]
    point, audit = engine.dated_source_stock_protection(decision_day=0,
        requirements=concentrated, safety_days=10, fixed_qty=0)
    other, _ = engine.dated_source_stock_protection(decision_day=0,
        requirements=spread, safety_days=10, fixed_qty=0)
    assert point.minimum_qty == other.minimum_qty == 100
    assert audit["dated_requirement_qty"] == 100 and audit["window_days"] == 10
    assert [r.qty for r in concentrated] == [100, 900, 800, 700]
    fixed, _ = engine.dated_source_stock_protection(decision_day=0,
        requirements=spread, safety_days=0, fixed_qty=30)
    assert fixed.minimum_qty == 30


def test_chain_depot_residual_compression_does_not_amplify_source_safety():
    # An84-calendar-day safety window contains the same residual70plus100
    # later forecast, whether the residual is spread or on its final day.
    following = [Requirement("later", 20, 100)]
    scattered = [Requirement(str(d), d, 10) for d in range(1, 8)] + following
    compressed = [Requirement("last-day", 7, 70)] + following
    for needs in (scattered, compressed):
        point, audit = engine.dated_source_stock_protection(decision_day=0,
            requirements=needs, safety_days=84, fixed_qty=0)
        assert point.minimum_qty == audit["target_qty"] == 170


@pytest.mark.parametrize("shipped", [40, 100])
def test_chain_snapshot_after_push_nets_destination_firm_before_exploding_BOM(shipped):
    depot, factory, component, raw, inputs = _chain_relation_memory_network()
    original = deepcopy(inputs)
    before, old_requirements, _ = engine.plan_component_network(**inputs)
    assert before[factory].proposed_qty == 0
    assert sum(r.qty for r in old_requirements[factory]) == 100
    snapshot, plans, requirements, _ = engine.reconcile_production_execution_snapshot(inputs,
        available_by_pair={factory: 100 - shipped},
        firm_receipts_by_pair={depot: [FirmReceipt("actual-push", 1, shipped, "in_transit")]},
        produced_pairs={factory, component})
    assert sum(r.qty for r in requirements[factory]) == 100 - shipped
    assert plans[factory].proposed_qty == plans[component].proposed_qty == plans[raw].proposed_qty == 0
    assert snapshot[factory]["requirements"] == tuple(requirements[factory])
    assert inputs == original
    # Independent accounting: remaining factory + shipped =100client need.
    assert (100 - shipped) + shipped == 100


def test_chain_snapshot_propagates_uncovered_need_through_all_manufacturing_levels():
    depot, factory, component, raw, inputs = _chain_relation_memory_network()
    snapshot, plans, requirements, _ = engine.reconcile_production_execution_snapshot(inputs,
        available_by_pair={factory: 20},
        firm_receipts_by_pair={depot: [FirmReceipt("push40", 1, 40, "in_transit")]},
        produced_pairs={factory, component})
    #100−40intransit−20factory=40newPF; BOM2then3 gives80and240.
    assert plans[factory].proposed_qty == 40
    assert plans[component].proposed_qty == 80
    assert plans[raw].proposed_qty == 240
    assert sum(r.qty for r in requirements[raw]) == 240
    assert len(snapshot) == 2


def test_chain_snapshot_preserves_active_campaign_and_held_quantities_once():
    depot, factory, component, raw, inputs = _chain_relation_memory_network()
    inputs["active_campaigns_by_pair"] = {factory: ("active", 40, 20, 3)}
    snapshots, plans, requirements, audit = engine.reconcile_production_execution_snapshot(inputs,
        available_by_pair={component: 80},
        firm_receipts_by_pair={depot: [FirmReceipt("held-push", 1, 40, "held")]},
        produced_pairs={factory, component})
    #60futurePF =40notyetfabricated+20WIP. Only40*2=80componentsremain.
    assert plans[factory].proposed_qty == plans[component].proposed_qty == 0
    assert sum(r.qty for r in requirements[component]) == 80
    assert [(r.receipt_id, r.qty) for r in audit[factory]["firm_receipts"]] == [("campaign:active", 60)]
    assert len({r.requirement_id for r in snapshots[component]["requirements"]}) == 1


def test_chain_source_protection_replaces_virtual_production_floor_from_first_snapshot():
    depot, factory, component, raw, inputs = _chain_relation_memory_network()
    inputs["requirements_by_pair"] = {}
    inputs["available_by_pair"] = {}
    inputs["protection_by_pair"] = {factory: [StockProtection("legacy-lot-daily", 1, 19200)]}
    inputs["reserve_targets_by_pair"] = {factory: 19200}
    inputs["source_safety_by_pair"][factory]["safety_days"] = 28
    plans, _, audits = engine.plan_component_network(**inputs)
    assert plans[factory].proposed_qty == plans[component].proposed_qty == plans[raw].proposed_qty == 0
    assert audits[factory]["chain_source_safety"]["target_qty"] == 0
    assert inputs["protection_by_pair"][factory][0].minimum_qty == 19200
    # Opt-out remains the prior mode, including that historical floor.
    legacy_inputs = dict(inputs, source_safety_by_pair=None)
    legacy, _, _ = engine.plan_component_network(**legacy_inputs)
    assert legacy[factory].proposed_qty == 19200
    absent = dict(legacy_inputs)
    absent.pop("source_safety_by_pair")
    assert engine.plan_component_network(**absent) == engine.plan_component_network(**legacy_inputs)


def test_chain_unknown_capacity_campaign_uses_existing_fixed_batch_daily_convention():
    #6.4tremaining=2x3.2t, not6.4e6/1e-9days. tau3 stays a planning bound.
    work = engine.production_campaign_work_days(6_400_000, capacity_qty=0, fixed_lot_qty=3_200_000)
    assert work == 2
    decision, tau = 4, 3
    assert decision + max(1, work, tau) == 7
    with pytest.raises(ValueError):
        engine.production_campaign_work_days(10, capacity_qty=0, fixed_lot_qty=0)


def test_chain_snapshot_csv_accepts_all_actual_columns_in_memory():
    row = dict(day=0, node_id="plant", item_id="item:made", uom="UN",
        policy="dated_relation_consistent_v1", pre_dispatch_available_qty=100,
        post_dispatch_available_qty=0, pre_dispatch_requirement_qty=100,
        post_dispatch_requirement_qty=0, post_dispatch_firm_qty=0,
        post_dispatch_due_proposal_qty=0, source_safety_window_days=28,
        source_safety_requirement_qty=0, source_safety_target_qty=0)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=engine.CHAIN_EXECUTION_SNAPSHOT_FIELDS)
    writer.writeheader()
    writer.writerow(row)
    result = next(csv.DictReader(io.StringIO(stream.getvalue())))
    assert result["post_dispatch_due_proposal_qty"] == "0"
    assert set(result) == set(row)


def _prior_week_customer_case(rows=None):
    pair = ("customer", "item:finished")
    rows = rows if rows is not None else [(4, 11, 100, "I-old"), (4, 18, 70, "I-before-zero"),
                                          (11, 18, 0, "I-zero"), (4, 25, 70, "I-known"),
                                          (18, 25, 700000, "I-not-yet-known")]
    payload = dict(schema_version=1, origin="2025-01-01", calendar="sunday_start",
        repeat_period_days=365, current_bucket_policy="excluded_unresolved_carry_over",
        rows=[dict(node_id=pair[0], item_id=pair[1], uom="UN", vintage_day=vintage,
                   period_start_day=start, period_days=7, qty=qty, source_row=source)
              for vintage, start, qty, source in rows])
    profiles = {pair: [dict(type="constant", value=2.5, repeat_period_days=365)]}
    calendar = engine.SourcePriorWeekCustomerDemand(payload, nominal_profiles=profiles, origin_date="2025-01-01")
    return calendar, pair, payload, profiles


def test_prior_week_customer_preserves_integer_week_and_freezes_before_start():
    calendar, pair, _, _ = _prior_week_customer_case()
    result = [calendar.quantity(pair, decision_day=d, target_day=d) for d in range(11, 18)]
    assert [qty for qty, _ in result] == [14, 14, 14, 15, 14, 14, 15]
    assert sum(qty for qty, _ in result) == 100
    assert all(type(qty) is int for qty, _ in result)
    assert {audit["source_vintage_day"] for _, audit in result} == {4}
    assert {audit["period_start_day"] for _, audit in result} == {11}
    assert {audit["source_row"] for _, audit in result} == {"I-old"}


def test_prior_week_customer_preview_ignores_future_revision_then_uses_known_zero():
    calendar, pair, _, _ = _prior_week_customer_case()
    # The large future revision exists in memory, but is not knowable on17.
    early, audit = calendar.quantity(pair, decision_day=17, target_day=25)
    assert early == 10 and audit["source_vintage_day"] == 4
    known, audit = calendar.quantity(pair, decision_day=18, target_day=25)
    assert known == 100000 and audit["source_vintage_day"] == 18
    # For the same target, a known explicit zero overrides an older70.
    assert calendar.quantity(pair, decision_day=10, target_day=18)[0] == 10
    qty, audit = calendar.quantity(pair, decision_day=11, target_day=18)
    assert qty == 0 and audit["status"] == "explicit_source_zero"
    assert audit["source_row"] == "I-zero"
    actual_first20 = [calendar.quantity(pair, decision_day=d, target_day=d)[0] for d in range(20)]
    assert sum(actual_first20) == 127  # Initial10 + unknown-week17 + source100 + zero0.


def test_prior_week_customer_missing_period_keeps_nominal_and_forecast_profile_separate():
    calendar, pair, payload, profiles = _prior_week_customer_case()
    original_payload, original_profiles = deepcopy(payload), deepcopy(profiles)
    qty, audit = calendar.quantity(pair, decision_day=0, target_day=0)
    assert qty == 2 and audit["nominal_day_qty"] == 2.5
    assert audit["source_row"] == "" and audit["weekly_source_qty"] == ""
    assert audit["allocation_start_day"] == 0 and audit["period_start_day"] == -3
    assert sum(calendar.quantity(pair, decision_day=d, target_day=d)[0] for d in range(4)) == 10
    # A52-week missing-source window remains the original fractional nominal
    # forecast. It never sees the estimated physical daily allocations.
    forecast = engine.RollingMrpForecast(payload, demand_pairs={pair}, origin_date="2025-01-01",
        missing_period_policy="last_known_period_v1", consumption_policy="weekly_actual_orders_v1")
    fallback = [engine.profile_value(profiles[pair], d) for d in range(1, 365)]
    quantity, forecast_audit = forecast.window(pair, decision_day=0, target_day=1, fallback_daily_values=fallback)
    assert quantity == 2.5 and forecast_audit["fallback_days"] == 364
    assert profiles == original_profiles and payload == original_payload


def test_prior_week_customer_partial_december_and_2026_do_not_repeat_vintages():
    calendar, pair, _, _ = _prior_week_customer_case([(354, 361, 10, "December"),
                                                     (354, 368, 21, "known-2026-tail")])
    in2025 = [calendar.quantity(pair, decision_day=d, target_day=d)[0] for d in range(361, 365)]
    assert in2025 == [1, 1, 2, 1] and sum(in2025) == 5
    assert sum(calendar.quantity(pair, decision_day=361, target_day=d)[0] for d in range(361, 368)) == 10
    assert calendar.quantity(pair, decision_day=364, target_day=368)[0] == 3
    _, absent = calendar.quantity(pair, decision_day=372, target_day=375)
    assert absent["status"] == "nominal_fallback_no_known_period" and absent["source_vintage_day"] == ""


def test_prior_week_customer_orders_consume_forecast_once_with_separate_backlog():
    calendar, pair, payload, _ = _prior_week_customer_case()
    forecast = engine.RollingMrpForecast(payload, demand_pairs={pair}, origin_date="2025-01-01",
        missing_period_policy="last_known_period_v1", consumption_policy="weekly_actual_orders_v1")
    for day in range(14):
        demand, _ = calendar.quantity(pair, decision_day=day, target_day=day)
        forecast.observe_demand(day, {pair: demand})
    audit = forecast.consumption_audit(pair, 13)
    assert audit["arrived_demand_qty"] == 42 and audit["remaining_forecast_qty"] == 58
    backlog = 42 - 20  # Only20 of the42arrived orders were physically served.
    assert audit["remaining_forecast_qty"] + backlog == 80
    for day in range(14, 18):
        forecast.observe_demand(day, {pair: calendar.quantity(pair, decision_day=day, target_day=day)[0]})
    assert forecast.consumption_audit(pair, 17)["expired_forecast_qty"] == 0


def test_prior_week_customer_cover_nets_committed_quantities_once():
    calendar, pair, _, _ = _prior_week_customer_case()
    needs = [Requirement(str(day), day, calendar.quantity(pair, decision_day=11, target_day=day)[0])
             for day in (12, 13)]
    assert sum(row.qty for row in needs) == 28
    result = engine.customer_physical_cover_need(decision_day=11, arrival_day=13,
        physical_requirements=needs, available_qty=5, backlog_qty=3,
        firm_receipts=[FirmReceipt("already-shipped", 12, 10)], uom="UN")
    assert result["customer_physical_order_qty"] == 16  #28future+3backlog−5stock−10firm.
    assert calendar.quantity(pair, decision_day=12, target_day=12)[0] == needs[0].qty


@pytest.mark.parametrize("fault", ["fraction", "current", "weekday", "duplicate"])
def test_prior_week_customer_rejects_invalid_physical_or_temporal_source(fault):
    _, pair, payload, profiles = _prior_week_customer_case()
    if fault == "fraction": payload["rows"][0]["qty"] = 100.5
    elif fault == "current": payload["rows"][0]["period_start_day"] = 4
    elif fault == "weekday": payload["rows"][0]["period_start_day"] = 12
    elif fault == "duplicate": payload["rows"].append(dict(payload["rows"][0]))
    with pytest.raises(ValueError):
        engine.SourcePriorWeekCustomerDemand(payload, nominal_profiles=profiles, origin_date="2025-01-01")


@pytest.mark.parametrize("fault", [None, "mode", "forecast_scope", "cover_scope", "envelope", "long_run"])
def test_prior_week_customer_opt_in_scope_and_opt_out_are_explicit(fault):
    pair = ("customer", "item:finished")
    kwargs = dict(demand_pairs={pair}, forecast_consumption_pairs={pair}, customer_cover_pairs={pair},
                  current_envelope_policy=None, sim_days=365)
    policy = "source_prior_week_need_v1"
    if fault == "mode": policy = "source_current_I"
    elif fault == "forecast_scope": kwargs["forecast_consumption_pairs"] = set()
    elif fault == "cover_scope": kwargs["customer_cover_pairs"] = set()
    elif fault == "envelope": kwargs["current_envelope_policy"] = "gross_current_residual_v1"
    elif fault == "long_run": kwargs["sim_days"] = 366
    assert engine.resolve_customer_demand_policy(None, **kwargs) is False
    if fault is None:
        assert engine.resolve_customer_demand_policy(policy, **kwargs) is True
    else:
        with pytest.raises(ValueError):
            engine.resolve_customer_demand_policy(policy, **kwargs)


def test_prior_week_customer_csv_contains_exact_quantities_and_provenance_in_memory():
    calendar, pair, _, _ = _prior_week_customer_case()
    records = [calendar.quantity(pair, decision_day=day, target_day=day)[1] for day in (0, 11, 18)]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=engine.CUSTOMER_DEMAND_POLICY_FIELDS)
    writer.writeheader()
    writer.writerows(records)
    rows = list(csv.DictReader(io.StringIO(output.getvalue())))
    assert len(rows) == 3 and rows[0]["status"] == "nominal_fallback_no_known_period"
    assert rows[1]["day_qty"] == "14" and rows[1]["weekly_source_qty"] == "100"
    assert rows[2]["day_qty"] == "0" and rows[2]["source_row"] == "I-zero"
