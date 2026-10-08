"""Memory-only oracles for the opt-in physical customer dispatch profile.

No workbook, simulation, filesystem fixture or source mutation is used.
Planning consumption remains a separate, unchanged forecast calculation.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine import run_first_simulation as engine


PAIR = ("C-TEST", "item:268091")
OTHER = ("C-TEST", "item:268967")


def _forecast(periods=None, *, pairs=(PAIR,)):
    periods = periods if periods is not None else [
        (-2, 5, 329532, "Previsions!F3"), (-2, 12, 75740, "Previsions!G3")]
    payload = dict(schema_version=1, origin="2025-01-01", calendar="monday_start",
        repeat_period_days=365, current_bucket_policy="excluded_unresolved_carry_over", rows=[
            dict(node_id=pair[0], item_id=pair[1], uom="UN", vintage_day=vintage,
                 period_start_day=start, period_days=7, qty=qty,
                 source_file="memory.xlsx", source_row=cell)
            for pair in pairs for vintage, start, qty, cell in periods])
    return engine.RollingMrpForecast(payload, demand_pairs=set(pairs), origin_date="2025-01-01",
        missing_period_policy="last_known_period_v1", consumption_policy="weekly_actual_orders_v1",
        customer_demand_policy="source_customer_history_v1")


def _observe(forecast, quantities):
    for day, quantity in enumerate(quantities):
        forecast.observe_demand(day, {pair: quantity for pair in forecast.demand_pairs})


def _profile(forecast, *, decision=0, target=1, days=2, pair=PAIR, selected=frozenset({PAIR})):
    return engine.customer_dispatch_profile(forecast, pair, policy_pairs=selected,
        decision_day=decision, target_day=target, window_days=days)


def _contract():
    history = dict(schema_version=1, origin="2025-01-01", calendar="monday_start", rows=[
        dict(node_id=pair[0], item_id=pair[1], uom="UN", period_start_day=-2,
             period_days=7, qty=13300, source_file="memory.xlsx", source_row=f"History!D{index + 2}")
        for index, pair in enumerate((PAIR, OTHER))])
    policy = dict(schema_version=1, mode="dated_source_profile_v1", pairs=[list(PAIR)],
                  opening_missing_period="observed_to_date_mean_v1")
    context = dict(customer_cover_pairs={PAIR, OTHER}, customer_demand_policy="source_customer_history_v1",
        forecast=_forecast(pairs=(PAIR, OTHER)), demand_calendar=engine.SourceCustomerHistory(
            history, demand_pairs={PAIR, OTHER}, origin_date="2025-01-01", sim_days=1))
    return policy, context


def test_opening_observed_mean_has_manual_3800_future_cover_and_5700_order():
    forecast = _forecast()
    _observe(forecast, [1900])
    values, audit = _profile(forecast)
    # Jan 1 is Wednesday: only today's 1900 is observed, Jan 2-3 are future.
    assert values == [1900, 1900]
    assert audit["customer_dispatch_forecast_future_qty"] == 3800
    assert audit["customer_dispatch_forecast_opening_observed_days"] == 1
    assert audit["customer_dispatch_forecast_opening_days"] == 2
    assert audit["customer_dispatch_forecast_basis"] == "opening_observed_to_date_mean_assumption"
    decision = engine.customer_physical_cover_need(decision_day=0, arrival_day=2,
        physical_requirements=[engine.Requirement(f"future:{day}", day, qty)
                               for day, qty in enumerate(values, 1)],
        available_qty=0, backlog_qty=1900, firm_receipts=[], uom="UN")
    assert decision["customer_physical_future_demand_qty"] == 3800
    assert decision["customer_physical_order_qty"] == 5700
    assert decision["customer_physical_order_qty"] % 1 == 0


def test_opening_mean_ignores_later_observations_and_stops_at_week_boundary():
    first, changed_future = _forecast(), _forecast()
    _observe(first, [1900, 2100, 2300, 2500, 2700])
    _observe(changed_future, [1900, 999999, 888888, 777777, 666666])
    assert _profile(first, decision=0) == _profile(changed_future, decision=0)
    values, audit = _profile(first, decision=3, target=4, days=2)
    # Mean of Wed-Sat = 2200; Monday belongs to the known source week.
    assert values == [2200, 47076]
    assert audit["customer_dispatch_forecast_opening_observed_days"] == 4
    assert audit["customer_dispatch_forecast_opening_days"] == 1
    assert audit["customer_dispatch_forecast_source_days"] == 1


def test_january11_uses_47076_then_10820_without_endweek_compression():
    forecast = _forecast()
    _observe(forecast, [1900] * 5 + [5000] * 5 + [5616])
    values, audit = _profile(forecast, decision=10, target=11, days=2)
    # Six arrived days in Jan 6-12 total 30616. Legacy redistributes 298916
    # onto Sunday; physical dispatch retains 329532 / 7 = 47076 that day.
    assert values == [47076, 10820]
    assert audit["customer_dispatch_forecast_future_qty"] == 57896
    assert audit["customer_dispatch_forecast_source_rows"] == "Previsions!F3|Previsions!G3"
    assert audit["customer_dispatch_forecast_source_vintage_days"] == "-2"
    assert audit["customer_dispatch_forecast_capped_days"] == 0


@pytest.mark.parametrize("arrived,expected", [(0, 10), (66, 4), (71, 0)],
                         ids=["daily_ceiling", "remaining_cap", "above_forecast"])
def test_current_week_is_capped_by_source_daily_and_remaining(arrived, expected):
    forecast = _forecast([(-2, 5, 70, "F3")])
    _observe(forecast, [0] * 10 + [arrived])
    values, audit = _profile(forecast, decision=10, target=11, days=1)
    assert values == [expected]
    assert audit["customer_dispatch_forecast_capped_days"] == int(expected < 10)


def test_explicit_zero_is_source_and_missing_week_is_traced_fallback():
    forecast = _forecast([(-2, 5, 70, "F3"), (-2, 12, 0, "G3"), (-2, 26, 700, "I3")])
    _observe(forecast, [1900])
    zero, zero_audit = _profile(forecast, target=12, days=1)
    missing, missing_audit = _profile(forecast, target=25, days=1)
    assert zero == [0] and zero_audit["customer_dispatch_forecast_source_days"] == 1
    assert zero_audit["customer_dispatch_forecast_fallback_days"] == 0
    assert missing == [100] and missing_audit["customer_dispatch_forecast_source_days"] == 0
    assert missing_audit["customer_dispatch_forecast_fallback_days"] == 1
    assert missing_audit["customer_dispatch_forecast_fallback_source_rows"] == "I3"
    assert missing_audit["customer_dispatch_forecast_fallback_vintage_days"] == "-2"
    assert missing_audit["customer_dispatch_forecast_opening_days"] == 0


def test_future_vintage_is_ignored_and_older_known_target_period_is_retained():
    known = [(-2, 5, 70, "initial"), (-2, 19, 140, "old-target"), (5, 12, 210, "latest-other")]
    forecast = _forecast(known + [(12, 19, 700, "future-target")])
    changed_future = _forecast(known + [(12, 19, 999999, "future-target-changed")])
    actual = _profile(forecast, decision=10, target=19, days=1)
    assert actual == _profile(changed_future, decision=10, target=19, days=1)
    values, audit = actual
    assert values == [20]
    assert audit["customer_dispatch_forecast_source_rows"] == "old-target"
    assert audit["customer_dispatch_forecast_source_vintage_days"] == "-2"
    assert audit["customer_dispatch_forecast_fallback_days"] == 0
    assert _profile(forecast, decision=12, target=19, days=1)[0] == [100]


def test_physical_profile_does_not_change_legacy_window_or_consumption():
    forecast = _forecast()
    _observe(forecast, [1900] * 5 + [5000] * 5 + [5616])
    kwargs = dict(decision_day=10, target_day=11, fallback_daily_values=[0, 0])
    legacy_before = deepcopy(forecast.window(PAIR, **kwargs))
    consumption_before = deepcopy(forecast.consumption_audit(PAIR, 10))
    assert legacy_before[0] == (298916 + 10820) / 2
    assert consumption_before["remaining_forecast_qty"] == 298916
    _profile(forecast, decision=10, target=11, days=2)
    assert forecast.window(PAIR, **kwargs) == legacy_before
    assert forecast.consumption_audit(PAIR, 10) == consumption_before


def test_only_selected_pair_gets_profile_and_absent_policy_keeps_legacy_sentinel():
    policy, context = _contract()
    before = deepcopy(policy)
    selected = engine.resolve_customer_dispatch_forecast_policy(policy, **context)
    assert selected == frozenset({PAIR}) and policy == before
    _observe(context["forecast"], [1900])
    assert _profile(context["forecast"], selected=selected)[0] == [1900, 1900]
    assert _profile(None, pair=OTHER, selected=selected) == (None, {})
    assert engine.resolve_customer_dispatch_forecast_policy(None, **context) == frozenset()
    assert _profile(None, selected=frozenset()) == (None, {})


def test_profile_audit_exports_through_customer_cover_trace_without_legacy_values():
    forecast = _forecast()
    _observe(forecast, [1900])
    _, audit = _profile(forecast)
    trace = engine.customer_physical_cover_trace({PAIR: audit}, PAIR, enabled=True)
    assert set(audit) <= set(engine.CUSTOMER_PHYSICAL_COVER_FIELDS)
    assert all(trace[key] == value for key, value in audit.items())
    legacy_trace = engine.customer_physical_cover_trace({}, PAIR, enabled=True)
    assert all(legacy_trace[key] == "" for key in audit)


@pytest.mark.parametrize("fault", ["not_object", "missing_field", "unknown_field", "schema_bool",
    "schema_version", "mode", "opening_mode", "empty_pairs", "tuple_pair", "invalid_pair",
    "blank_pair", "duplicate", "unknown_pair", "no_cover", "wrong_demand_mode",
    "no_forecast", "no_history"], ids=str)
def test_policy_rejects_malformed_or_unavailable_contract(fault):
    policy, context = _contract()
    if fault == "not_object": policy = "dated_source_profile_v1"
    elif fault == "missing_field": policy.pop("opening_missing_period")
    elif fault == "unknown_field": policy["extra"] = True
    elif fault == "schema_bool": policy["schema_version"] = True
    elif fault == "schema_version": policy["schema_version"] = 2
    elif fault == "mode": policy["mode"] = "other"
    elif fault == "opening_mode": policy["opening_missing_period"] = "future_mean"
    elif fault == "empty_pairs": policy["pairs"] = []
    elif fault == "tuple_pair": policy["pairs"] = [PAIR]
    elif fault == "invalid_pair": policy["pairs"] = [[PAIR[0], 268091]]
    elif fault == "blank_pair": policy["pairs"] = [["", PAIR[1]]]
    elif fault == "duplicate": policy["pairs"] *= 2
    elif fault == "unknown_pair": policy["pairs"] = [["unknown", PAIR[1]]]
    elif fault == "no_cover": context["customer_cover_pairs"] = set()
    elif fault == "wrong_demand_mode": context["customer_demand_policy"] = "source_prior_week_need_v1"
    elif fault == "no_forecast": context["forecast"] = None
    elif fault == "no_history": context["demand_calendar"] = None
    with pytest.raises(ValueError, match="[Cc]ustomer dispatch"):
        engine.resolve_customer_dispatch_forecast_policy(policy, **context)


def _known_decision(*, day=0, arrival=2, backlog=1900, available=0, receipts=()):
    return engine.customer_known_demand_need(decision_day=day,arrival_day=arrival,
        backlog_qty=backlog,available_qty=available,firm_receipts=receipts,uom="UN")


def test_known_orders_policy_covers_both_products_without_forecast_dependency():
    _,context=_contract()
    context['forecast']=None
    policy=dict(schema_version=1,mode='known_demand_only_v1',pairs=[list(PAIR),list(OTHER)])
    before=deepcopy(policy)
    assert engine.resolve_customer_dispatch_forecast_policy(policy,**context)==frozenset({PAIR,OTHER})
    assert policy==before
    assert engine.resolve_customer_dispatch_forecast_policy(None,**context)==frozenset()


def test_known_orders_january1_dispatches_1900_not_forecast_cover_and_preserves_MRP():
    low,high=_forecast([(-2,5,70,'F3')]),_forecast([(-2,5,9999999,'F3')])
    proofs=[]
    for forecast in (low,high):
        _observe(forecast,[1900])
        kwargs=dict(decision_day=0,target_day=1,fallback_daily_values=[0,0])
        before=deepcopy(forecast.window(PAIR,**kwargs))
        consumption=deepcopy(forecast.consumption_audit(PAIR,0))
        proofs.append(_known_decision())
        assert forecast.window(PAIR,**kwargs)==before
        assert forecast.consumption_audit(PAIR,0)==consumption
    assert proofs[0]==proofs[1]
    decision=proofs[0]
    assert decision['customer_physical_order_qty']==1900
    assert decision['customer_physical_future_demand_qty']==0
    assert decision['customer_physical_target_qty']==1900
    assert decision['customer_dispatch_forecast_policy']=='known_demand_only_v1'


@pytest.mark.parametrize('backlog,available,pending,expected',[
    (0,0,0,0),(1900,0,0,1900),(1900,500,0,1400),(1900,0,700,1200),
    (1900,500,700,700),(1900,2500,0,0),(1900,0,2500,0)])
def test_known_orders_net_only_unserved_demand_available_and_all_open_promises(backlog,available,pending,expected):
    # Promise can arrive after the next new shipment: still no duplicate order.
    receipts=[engine.FirmReceipt('already_committed',20,pending)] if pending else []
    decision=_known_decision(backlog=backlog,available=available,receipts=receipts)
    assert decision['customer_physical_order_qty']==expected
    assert decision['customer_physical_order_qty']%1==0
    assert decision['customer_physical_firm_cover_qty']==pending


def test_known_orders_two_day_transport_leaves_visible_backlog_without_duplicate_dispatch():
    first=_known_decision()
    assert first['customer_physical_order_qty']==1900
    # Jan2: yesterday's 1900 is still in transit; another1900 has arrived as demand.
    second=_known_decision(day=1,arrival=3,backlog=3800,
        receipts=[engine.FirmReceipt('dispatch_J0',2,1900,'in_transit')])
    assert second['customer_physical_backlog_qty']==3800
    assert second['customer_physical_order_qty']==1900
    # Jan3: receive1900, serve it, know another1900. Only J1 shipment remains.
    third=_known_decision(day=2,arrival=4,backlog=3800,
        receipts=[engine.FirmReceipt('dispatch_J1',3,1900,'in_transit')])
    assert third['customer_physical_order_qty']==1900
    assert sum(d['customer_physical_order_qty'] for d in (first,second,third))==5700
    # Jan4 without new demand: receive/service J1; J2 covers the last1900.
    assert _known_decision(day=3,arrival=5,backlog=1900,receipts=[
        engine.FirmReceipt('dispatch_J2',4,1900)
    ])['customer_physical_order_qty']==0


def test_known_orders_pending_reserved_departure_netted_once_and_fractional_UN_rejected():
    receipts=[engine.FirmReceipt('transit',1,600,'in_transit'),
              engine.FirmReceipt('reserved_dispatch',8,800,'confirmed')]
    assert _known_decision(receipts=receipts)['customer_physical_order_qty']==500
    with pytest.raises(ValueError,match='unique'):
        _known_decision(receipts=receipts+[receipts[0]])
    for kwargs in ({'backlog':.5},{'available':.5},{'receipts':[engine.FirmReceipt('fraction',1,.5)]}):
        with pytest.raises(ValueError,match='integral'):_known_decision(**kwargs)
    with pytest.raises(ValueError):_known_decision(day=0,arrival=0)


def test_known_orders_trace_distinguishes_zero_future_from_legacy_profile():
    decision=_known_decision()
    trace=engine.customer_physical_cover_trace({PAIR:decision},PAIR,enabled=True)
    assert set(decision)<=set(engine.CUSTOMER_PHYSICAL_COVER_FIELDS)
    assert trace['customer_dispatch_forecast_basis']=='known_backlog_after_service_no_future_forecast'
    assert trace['customer_dispatch_forecast_future_qty']==0
    assert trace['customer_dispatch_forecast_source_rows']==''


def test_known_orders_policy_rejects_opening_forecast_option_and_unobserved_history():
    _,context=_contract()
    policy=dict(schema_version=1,mode='known_demand_only_v1',pairs=[list(PAIR)])
    with pytest.raises(ValueError):engine.resolve_customer_dispatch_forecast_policy(
        dict(policy,opening_missing_period='observed_to_date_mean_v1'),**context)
    context['demand_calendar']=None
    with pytest.raises(ValueError):engine.resolve_customer_dispatch_forecast_policy(policy,**context)


def test_known_orders_preserves_explicit_single_route_limit():
    route=dict(src='D-X',dst=PAIR[0],item_id=PAIR[1],order_frequency_days=1,standard_order_qty=0)
    with pytest.raises(ValueError,match='one daily'):
        engine.resolve_customer_physical_cover('physical_demand_cover_v1',
            nodes=[dict(id='D-X',type='distribution_center'),dict(id=PAIR[0],type='customer')],
            demand_pairs={PAIR},lanes_by_dest_item={PAIR:[route,dict(route)]},dated_planning=True)


@pytest.mark.parametrize('requested,multiple,expected',[
    (3800,0,1900),(96052,0,1900),(3800,1000,1000),(3800,2000,0),(570.5,0,570)])
def test_known_orders_physical_cap_blocks_controls_and_upward_lot_rounding(requested,multiple,expected):
    assert engine.cap_known_customer_dispatch(requested,known_need=1900,
        uom='UN',multiple_qty=multiple)==expected


def test_known_orders_second_dispatch_attempt_sees_first_reserved_departure():
    first=engine.cap_known_customer_dispatch(5000,known_need=1900,uom='UN',multiple_qty=1000)
    assert first==1000
    remaining=_known_decision(receipts=[engine.FirmReceipt('first_reserved',2,first)])
    second=engine.cap_known_customer_dispatch(5000,known_need=remaining['customer_physical_order_qty'],uom='UN')
    assert first+second==1900
