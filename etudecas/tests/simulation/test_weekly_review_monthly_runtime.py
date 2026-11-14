"""RollingMrpForecast integration oracles; memory only, no file fixtures."""
from copy import deepcopy
from datetime import date
import math

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.monthly_forecast import (
    MONTHLY_CONSUMPTION_POLICY,
    WEEKLY_REVIEW_MONTHLY_POLICY,
)


PAIR = ("C-review-memory", "item:finished")


def make_forecast(*, origin="2027-02-01", weekly_qty=250, rows=None,
                  customer=True, policy=WEEKLY_REVIEW_MONTHLY_POLICY):
    """Explicit source periods, same contracts as the existing monthly tests."""
    opening = date.fromisoformat(origin)
    first = ((7 - opening.weekday()) % 7 if customer
             else (6 - opening.weekday()) % 7)
    if first == 0:
        first = 7
    vintage = -opening.weekday() if customer else 0
    source_rows = rows if rows is not None else [
        dict(node_id=PAIR[0], item_id=PAIR[1], uom="UN", vintage_day=vintage,
             period_start_day=start, period_days=7, qty=weekly_qty,
             source_row=f"opening-{start}", source_file="memory-only")
        for start in range(first, first + 98, 7)
    ]
    payload = dict(schema_version=1, origin_date=origin,
        calendar="monday_start" if customer else "sunday_start",
        repeat_period_days=365, current_bucket_policy="excluded_unresolved_carry_over",
        rows=source_rows)
    return engine.RollingMrpForecast(payload, demand_pairs={PAIR}, origin_date=origin,
        missing_period_policy="last_known_period_v1", consumption_policy=policy,
        customer_demand_policy="source_customer_history_v1" if customer else None)


def observe(forecast, through, actuals):
    for day in range(forecast.consumption_revision, through + 1):
        forecast.observe_demand(day, {PAIR: actuals.get(day, 0)})


def daily(forecast, decision, target):
    # An intentionally huge finite fallback must not replace a known forecast.
    return forecast.window(PAIR, decision_day=decision, target_day=target,
                           fallback_daily_values=[999999.])


@pytest.mark.parametrize("customer", [True, False])
def test_runtime_weekly_monthly_reviews_700_over21_then450_over14(customer):
    forecast = make_forecast(customer=customer)
    observe(forecast, 6, {6: 300})  # Sunday February7 includes this day's demand.
    first = forecast.consumption_audit(PAIR, 6)
    assert first["policy"] == WEEKLY_REVIEW_MONTHLY_POLICY
    assert first["status"] == "known_calendar_month_consumed"
    assert first["monthly_forecast_qty"] == pytest.approx(1000)
    assert first["weekly_forecast_qty"] == ""
    assert first["period_start_day"] == 0 and first["period_end_day"] == 27
    assert first["review_demand_qty"] == 300
    assert first["review_observed_through_day"] == first["review_day"] == 6
    assert first["review_first_forecast_day"] == 7
    assert first["future_daily_qty"] == pytest.approx(700 / 21)
    assert math.fsum(daily(forecast, 6, day)[0] for day in range(7, 14)) == pytest.approx(700 / 3)
    observe(forecast, 13, {13: 250})
    second = forecast.consumption_audit(PAIR, 13)
    assert second["arrived_demand_qty"] == second["review_demand_qty"] == 550
    assert second["remaining_forecast_qty"] == pytest.approx(450)
    assert second["future_daily_qty"] == pytest.approx(450 / 14)
    assert second["review_first_forecast_day"] == 14
    assert math.fsum(daily(forecast, 13, day)[0] for day in range(14, 21)) == pytest.approx(225)


def test_runtime_weekly_monthly_monday_actual_keeps_rate_and_current_window_real():
    forecast = make_forecast()
    observe(forecast, 6, {6: 300})
    before = deepcopy(forecast.consumption_audit(PAIR, 6))
    observe(forecast, 7, {7: 100})
    monday = forecast.consumption_audit(PAIR, 7)
    assert monday["arrived_demand_qty"] == 400
    assert monday["monthly_remaining_after_actual_qty"] == 600
    assert monday["review_demand_qty"] == 300
    assert monday["unreviewed_actual_demand_qty"] == 100
    assert monday["review_day"] == 6
    assert monday["future_daily_qty"] == before["future_daily_qty"]
    assert monday["remaining_forecast_qty"] == pytest.approx(700 * 20 / 21)
    current, current_audit = daily(forecast, 7, 7)
    future, future_audit = daily(forecast, 7, 8)
    assert current == 100 and current_audit["actual_order_days"] == 1
    assert future == pytest.approx(700 / 21)
    assert future_audit["actual_order_days"] == 0
    average, audit = forecast.window(PAIR, decision_day=7, target_day=7,
                                    fallback_daily_values=[999999.] * 3)
    assert average * 3 == pytest.approx(100 + 2 * 700 / 21)
    assert audit["actual_order_days"] == 1


def test_runtime_weekly_monthly_later_actuals_do_not_rewrite_past_asof():
    forecast = make_forecast()
    observe(forecast, 7, {6: 300, 7: 100})
    earlier_row = deepcopy(forecast.consumption_audit(PAIR, 7))
    earlier_future = deepcopy(daily(forecast, 7, 10))
    observe(forecast, 20, {8: 10000, 13: 9000, 20: 8000})
    assert forecast.consumption_audit(PAIR, 7) == earlier_row
    assert daily(forecast, 7, 10) == earlier_future
    current = forecast.consumption_audit(PAIR, 20)
    assert current["arrived_demand_qty"] == 27400
    assert current["future_daily_qty"] == 0
    assert current["monthly_remaining_after_actual_qty"] == 0
    assert current["review_observed_through_day"] == 20


def test_runtime_weekly_monthly_budget_versions_frozen_at_each_month_opening():
    rows = []
    # Jan1,2025 is Wednesday. Versions are Mondays Dec30,Jan20,Feb10.
    for vintage, first, weekly in [(-2, 5, 70), (19, 26, 140), (40, 47, 700)]:
        rows.extend(dict(node_id=PAIR[0], item_id=PAIR[1], uom="UN",
            vintage_day=vintage, period_start_day=start, period_days=7, qty=weekly,
            source_row=f"version-{vintage}-period-{start}", source_file="memory-only")
            for start in range(first, first + 98, 7))
    forecast = make_forecast(origin="2025-01-01", rows=rows)
    observe(forecast, 0, {0: 13})
    january_opening = deepcopy(forecast.consumption_audit(PAIR, 0))
    assert january_opening["monthly_forecast_qty"] == 310
    assert january_opening["source_vintage_day"] == -2
    observe(forecast, 20, {})
    january_later = forecast.consumption_audit(PAIR, 20)
    assert january_later["monthly_forecast_qty"] == 310
    assert january_later["budget_source_vintage_days"] == "-2"
    assert forecast.consumption_audit(PAIR, 0) == january_opening
    # Looking into February in January must not freeze February's budget.
    assert daily(forecast, 20, 31)[0] == 20
    assert (PAIR, 31) not in forecast._monthly_budgets
    observe(forecast, 31, {31: 6})
    february_opening = deepcopy(forecast.consumption_audit(PAIR, 31))
    assert february_opening["monthly_forecast_qty"] == 560
    assert february_opening["budget_source_vintage_days"] == "19"
    assert february_opening["arrived_demand_qty"] == 6
    assert february_opening["review_demand_qty"] == 0
    assert february_opening["review_observed_through_day"] == 30
    assert february_opening["future_daily_qty"] == 20
    assert february_opening["remaining_forecast_qty"] == 540
    observe(forecast, 46, {})  # New Feb10 version is known but budget stays fixed.
    assert forecast.consumption_audit(PAIR, 46)["monthly_forecast_qty"] == 560
    assert forecast.consumption_audit(PAIR, 46)["budget_source_vintage_days"] == "19"
    assert forecast.consumption_audit(PAIR, 31) == february_opening


def test_runtime_weekly_monthly_opt_in_keeps_legacy_daily_recalculation():
    weekly = make_forecast()
    legacy = make_forecast(policy=MONTHLY_CONSUMPTION_POLICY)
    for forecast in (weekly, legacy):
        observe(forecast, 7, {6: 300, 7: 100})
    weekly_row = weekly.consumption_audit(PAIR, 7)
    old_row = legacy.consumption_audit(PAIR, 7)
    assert old_row["policy"] == MONTHLY_CONSUMPTION_POLICY
    assert old_row["arrived_demand_qty"] == weekly_row["arrived_demand_qty"] == 400
    assert old_row["remaining_forecast_qty"] == 600
    assert old_row["future_daily_qty"] == 30
    assert "review_day" not in old_row
    assert weekly_row["future_daily_qty"] == pytest.approx(700 / 21)
    assert daily(legacy, 7, 8)[0] == 30
    assert daily(weekly, 7, 8)[0] == pytest.approx(700 / 21)


@pytest.mark.parametrize("sunday_actual,expected_dispatch_week,expected_capped_days", [
    (0, 250, 0),             # Source profile is lower than unconsumed-budget rate.
    (300, 700 / 3, 7),       # Frozen review rate caps the original source profile.
])
def test_runtime_weekly_monthly_dispatch_preserves_source_profile_bound(
    sunday_actual, expected_dispatch_week, expected_capped_days,
):
    forecast = make_forecast()
    observe(forecast, 6, {6: sunday_actual})
    values, audit = forecast.customer_dispatch_window(
        PAIR, decision_day=6, target_day=7, window_days=7)
    assert math.fsum(values) == pytest.approx(expected_dispatch_week)
    assert all(value <= 250 / 7 for value in values)
    assert audit["customer_dispatch_forecast_capped_days"] == expected_capped_days
    assert "capped_by_month_remaining" in audit["customer_dispatch_forecast_basis"]
    planning = math.fsum(daily(forecast, 6, day)[0] for day in range(7, 14))
    assert planning == pytest.approx((1000 - sunday_actual) / 3)
    # Later physical demand cannot leak into a past dispatch forecast.
    observe(forecast, 9, {7: 5000, 9: 6000})
    after, after_audit = forecast.customer_dispatch_window(
        PAIR, decision_day=6, target_day=7, window_days=7)
    assert after == values and after_audit == audit
