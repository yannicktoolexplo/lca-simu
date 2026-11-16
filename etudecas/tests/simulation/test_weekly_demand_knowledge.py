"""Weekly publication oracles: memory only, no filesystem fixtures or runs."""
from copy import deepcopy
from datetime import date
import math

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.monthly_forecast import (
    DAILY_DEMAND_KNOWLEDGE_POLICY, WEEKLY_DEMAND_KNOWLEDGE_POLICY,
    WEEKLY_REVIEW_MONTHLY_POLICY,
)


PAIR = ('client', 'item:268967')


def setup_case(*, origin='2025-01-01', days=45, pair=PAIR, totals=None, forecast_week=250,
               mode=WEEKLY_DEMAND_KNOWLEDGE_POLICY):
    first = -date.fromisoformat(origin).weekday()
    totals = totals or {}
    history = dict(schema_version=1, origin=origin, calendar='monday_start', rows=[
        dict(node_id=pair[0], item_id=pair[1], uom='UN', period_start_day=start,
            period_days=7, qty=totals.get(start, 0), source_file='memory-history',
            source_row=f'History!R{index+1}') for index, start in enumerate(range(first, days, 7))])
    forecast = dict(schema_version=1, origin=origin, calendar='monday_start', repeat_period_days=365,
        current_bucket_policy='excluded_unresolved_carry_over', rows=[
            dict(node_id=pair[0], item_id=pair[1], uom='UN', vintage_day=first,
                period_start_day=start, period_days=7, qty=forecast_week,
                source_file='memory-forecast', source_row=f'Forecast!R{index+1}')
            for index, start in enumerate(range(first+7, first+105, 7))])
    physical = engine.SourceCustomerHistory(history, demand_pairs={pair}, origin_date=origin,
        sim_days=days, knowledge_policy=mode)
    planning = engine.RollingMrpForecast(forecast, demand_pairs={pair}, origin_date=origin,
        missing_period_policy='last_known_period_v1', consumption_policy=WEEKLY_REVIEW_MONTHLY_POLICY,
        customer_demand_policy='source_customer_history_v1', customer_demand_knowledge_policy=mode)
    return physical, planning


def advance(physical, planning, through, pair=PAIR):
    result = []
    for day in range(planning.consumption_revision, through+1):
        quantity, audit = physical.quantity(pair, decision_day=day, target_day=day)
        if planning.customer_demand_knowledge_policy == WEEKLY_DEMAND_KNOWLEDGE_POLICY:
            publication = physical.publication(pair, day)
            planning.observe_demand(day, {pair: quantity},
                publications=[] if publication is None else [publication])
        else:
            planning.observe_demand(day, {pair: quantity})
        result.append((day, quantity, audit))
    return result


def planned(planning, decision, target=None, pair=PAIR):
    return planning.window(pair, decision_day=decision, target_day=decision if target is None else target,
        fallback_daily_values=[999999])[0]


@pytest.mark.parametrize('item', ['item:268091', 'item:268967'])
def test_unpublished_week_cannot_change_forecast_arrival_or_customer_dispatch(item):
    pair = ('client', item)
    cases = [setup_case(pair=pair, totals={-2: 0, 5: total}) for total in (0, 100003)]
    states = []
    for physical, planning in cases:
        observed = advance(physical, planning, 11, pair)
        assert all(quantity == 0 for _, quantity, _ in observed)
        # Unknown is not labelled as a measured zero and no total/source cell leaks.
        for day, _, audit in observed:
            if day != 5:  # Day5 publishes the explicit zero opening fragment.
                assert audit['status'] == 'no_publication_due_not_observed_zero'
                assert audit['weekly_source_qty'] == audit['source_row'] == ''
            else:
                assert audit['status'] == 'published_source_zero'
                assert audit['weekly_source_qty'] == 0 and audit['known_day'] == 5
        dispatch = engine.customer_known_demand_need(decision_day=11, arrival_day=12,
            available_qty=0, backlog_qty=0, firm_receipts=[], uom='UN')
        assert dispatch['customer_physical_order_qty'] == 0
        states.append((planning.consumption_audit(pair, 11), planned(planning, 11, pair=pair), dispatch))
    assert states[0] == states[1]
    assert advance(*cases[0], 12, pair)[0][1] == 0
    assert advance(*cases[1], 12, pair)[0][1] == 100003


def test_four_week_month_publishes300_then_plans700_over_three_weeks():
    physical, planning = setup_case(origin='2027-02-01', days=28, totals={0: 300})
    assert all(qty == 0 for _, qty, _ in advance(physical, planning, 6))
    assert advance(physical, planning, 7)[0][1] == 300
    audit = planning.consumption_audit(PAIR, 7)
    assert audit['monthly_forecast_qty'] == pytest.approx(1000)
    assert audit['review_remaining_month_qty'] == 700
    assert audit['review_future_days'] == 21
    assert audit['future_daily_qty'] == pytest.approx(700/21)
    assert math.fsum(planned(planning, 7, d) for d in range(7, 14)) == pytest.approx(700/3)
    # Monday's300 describe the previous week and are never today's MRP forecast.
    assert planned(planning, 7) == pytest.approx(700/21)
    advance(physical, planning, 10)
    assert planned(planning, 10) == planned(planning, 7)


def test_january_2025_review_uses700_over19_real_calendar_days():
    physical, planning = setup_case(totals={5: 300}, forecast_week=1000*7/31)
    advance(physical, planning, 12)
    audit = planning.consumption_audit(PAIR, 12)
    assert audit['monthly_forecast_qty'] == pytest.approx(1000)
    assert audit['review_remaining_month_qty'] == pytest.approx(700)
    assert audit['review_future_days'] == 19
    assert planned(planning, 12) == pytest.approx(700/19)


def test_cross_month_week301_is215_january86_february_known_on_february3():
    physical, planning = setup_case(totals={26: 301})
    advance(physical, planning, 32)
    before = deepcopy(planning.consumption_audit(PAIR, 30))
    assert planning.consumption_audit(PAIR, 32)['effective_month_published_qty'] == 0
    assert advance(physical, planning, 33)[0][1] == 301
    publication = physical.publication(PAIR, 33)
    assert sum(row['qty'] for row in publication['effective_daily_quantities'] if row['day'] < 31) == 215
    assert sum(row['qty'] for row in publication['effective_daily_quantities'] if row['day'] >= 31) == 86
    audit = planning.consumption_audit(PAIR, 33)
    assert audit['monthly_forecast_qty'] == pytest.approx(1000)
    assert audit['published_today_qty'] == 301
    assert audit['effective_month_published_qty'] == 86
    assert planned(planning, 33) == pytest.approx(914/26)
    assert planning.consumption_audit(PAIR, 30) == before  # No retroactive January knowledge.


@pytest.mark.parametrize('days,pending', [(10, 50), (12, 70)])
def test_initial_fragment10_contributes8_and_last_unpublished_fragment_stays_pending(days, pending):
    physical, planning = setup_case(days=days, totals={-2: 10, 5: 70})
    arrivals = advance(physical, planning, days-1)
    assert sum(qty for _, qty, _ in arrivals) == 8
    assert arrivals[5][1] == 8
    published, final = physical.publication_audit_rows()
    assert published['published_qty'] == 8 and published['known_day'] == 5
    assert final['published_qty'] == 0 and final['pending_qty'] == pending
    assert final['known_day'] == 12 and final['status'] == 'pending_not_disclosed'
    assert published['effective_qty_in_horizon'] + final['effective_qty_in_horizon'] == 8+pending


def test_repeated_publication_is_idempotent_and_not_a_second_physical_requirement():
    physical, planning = setup_case(totals={-2: 10})
    advance(physical, planning, 5)
    record = physical.publication(PAIR, 5)
    before = deepcopy(planning.consumption_audit(PAIR, 5))
    planning.observe_demand(5, {PAIR: 8}, publications=[record])
    assert len(planning._published_weeks) == 1
    assert sum(planning._observed_demands[PAIR]) == 8
    assert planning.consumption_audit(PAIR, 5) == before
    # Caller changes after registration cannot rewrite the owned observation.
    record['effective_daily_quantities'][0]['qty'] = 999
    assert planning.consumption_audit(PAIR, 5) == before
    revised = physical.publication(PAIR, 5)
    revised['source_row'] = 'different-source'
    with pytest.raises(ValueError, match='cannot be revised'):
        planning.observe_demand(5, {PAIR: 8}, publications=[revised])


@pytest.mark.parametrize('fault', ['future', 'duplicate', 'fraction', 'physical_mismatch', 'missing', 'wrong_period'])
def test_invalid_publication_is_refused_before_observation_state_changes(fault):
    physical, planning = setup_case(totals={-2: 10})
    advance(physical, planning, 4)
    publication = physical.publication(PAIR, 5)
    rows, quantity = [publication], 8
    if fault == 'future': publication['known_day'] = 12
    elif fault == 'duplicate': rows.append(deepcopy(publication))
    elif fault == 'fraction': publication['effective_daily_quantities'][0]['qty'] = 1.5
    elif fault == 'physical_mismatch': quantity = 7
    elif fault == 'missing': rows = []
    else: publication['period_end_day'] = 5
    with pytest.raises(ValueError):
        planning.observe_demand(5, {PAIR: quantity}, publications=rows)
    assert planning.consumption_revision == 5
    assert planning._published_weeks == {}
    assert sum(planning._observed_demands[PAIR]) == 0


def test_default_history_and_forecast_keep_legacy_daily_arrival_behavior():
    physical, planning = setup_case(totals={-2: 100}, mode=DAILY_DEMAND_KNOWLEDGE_POLICY)
    arrivals = advance(physical, planning, 4)
    assert [qty for _, qty, _ in arrivals] == [14, 15, 14, 14, 15]
    assert planned(planning, 4) == 15
    assert all('known_day' not in audit for _, _, audit in arrivals)
    assert planning._published_weeks == {}


def test_policy_rejects_unsupported_mode_and_horizon():
    with pytest.raises(ValueError, match='Unknown customer demand knowledge'):
        setup_case(mode='guess_daily')
    with pytest.raises(ValueError, match='annual horizon'):
        setup_case(days=366)


@pytest.mark.parametrize('history_mode,consumption', [
    ('source_customer_history_v1', 'weekly_actual_orders_v1'),
    (None, WEEKLY_REVIEW_MONTHLY_POLICY),
])
def test_forecast_refuses_weekly_publication_without_matching_source_contract(history_mode, consumption):
    with pytest.raises(ValueError, match='requires customer history and weekly monthly review'):
        engine.RollingMrpForecast({}, demand_pairs={PAIR}, origin_date='2025-01-01',
            missing_period_policy='last_known_period_v1', consumption_policy=consumption,
            customer_demand_policy=history_mode,
            customer_demand_knowledge_policy=WEEKLY_DEMAND_KNOWLEDGE_POLICY)
