"""Independent numeric oracles, memory only: no engine or file fixtures."""
from copy import deepcopy
import math

import pytest

from etudecas.simulation.engine.monthly_forecast import (
    MONTHLY_CONSUMPTION_FIELDS,
    MONTHLY_CONSUMPTION_POLICY,
    WEEKLY_REVIEW_MONTHLY_FIELDS,
    WEEKLY_REVIEW_MONTHLY_POLICY,
    remaining_month_budget,
    weekly_review_month_budget,
)


def february(actual, day, *, budget=1000):
    return weekly_review_month_budget(
        budget, actual, origin_date="2027-02-01", start_day=0,
        decision_day=day, end_day=27)


def test_weekly_review_user_example_700_over21_then450_over14():
    actual = [0.] * 28
    actual[6] = 300
    first = february(actual, 6)  # Sunday February7, including Sunday's demand.
    assert first["arrived_demand_qty"] == first["review_demand_qty"] == 300
    assert first["review_observed_through_day"] == first["review_day"] == 6
    assert first["review_first_forecast_day"] == 7
    assert first["review_future_days"] == first["future_days"] == 21
    assert first["review_remaining_month_qty"] == 700
    assert first["remaining_forecast_qty"] == pytest.approx(700)
    assert first["future_daily_qty"] == pytest.approx(700 / 21)
    actual[13] = 250
    second = february(actual, 13)
    assert second["arrived_demand_qty"] == second["review_demand_qty"] == 550
    assert second["remaining_forecast_qty"] == pytest.approx(450)
    assert second["review_first_forecast_day"] == 14
    assert second["review_future_days"] == 14
    assert second["future_daily_qty"] == pytest.approx(450 / 14)


def test_weekly_review_midweek_actual_changes_counter_not_frozen_rate():
    actual = [0.] * 28
    actual[6] = 300
    actual[9] = 250  # Wednesday February10, between Sunday reviews.
    row = february(actual, 9)
    assert row["arrived_demand_qty"] == 550
    assert row["review_demand_qty"] == 300
    assert row["unreviewed_actual_demand_qty"] == 250
    assert row["monthly_remaining_after_actual_qty"] == 450
    assert row["future_daily_qty"] == pytest.approx(700 / 21)
    assert row["remaining_forecast_qty"] == pytest.approx(700 * 18 / 21)
    assert row["review_day"] == row["review_observed_through_day"] == 6
    assert february(actual, 13)["future_daily_qty"] == pytest.approx(450 / 14)


def test_weekly_review_opening_and_partial_january_week():
    actual = [0.] * 31
    actual[0], actual[4] = 100, 200
    opening = weekly_review_month_budget(
        3100, actual, origin_date="2025-01-01", start_day=0, decision_day=0, end_day=30)
    assert opening["review_day"] == 0
    assert opening["review_observed_through_day"] == -1
    assert opening["review_first_forecast_day"] == 0
    assert opening["review_demand_qty"] == 0
    assert opening["review_future_days"] == 31
    assert opening["arrived_demand_qty"] == opening["unreviewed_actual_demand_qty"] == 100
    assert opening["future_daily_qty"] == 100
    assert opening["remaining_forecast_qty"] == 3000
    sunday = weekly_review_month_budget(
        3100, actual, origin_date="2025-01-01", start_day=0, decision_day=4, end_day=30)
    assert sunday["review_demand_qty"] == 300
    assert sunday["review_first_forecast_day"] == 5
    assert sunday["review_future_days"] == 26
    assert sunday["future_daily_qty"] == pytest.approx(2800 / 26)


def test_weekly_review_month_reset_excludes_previous_month_actuals():
    actual = [100.] * 31 + [0.] * 28
    actual[31] = 10  # Saturday February1.
    row = weekly_review_month_budget(
        560, actual, origin_date="2025-01-01", start_day=31, decision_day=31, end_day=58)
    assert row["arrived_demand_qty"] == 10
    assert row["review_demand_qty"] == 0
    assert row["review_observed_through_day"] == 30
    assert row["review_day"] == row["review_first_forecast_day"] == 31
    assert row["future_daily_qty"] == 20
    assert row["remaining_forecast_qty"] == 540
    assert row["monthly_remaining_after_actual_qty"] == 550
    # No claim about stocks or physical orders: the helper accepts neither.


def test_weekly_review_tail_is_causal_and_arguments_are_not_mutated():
    known = [0.] * 10
    known[6], known[9] = 300, 250
    actual = known + [999999.] * 18
    before = deepcopy(actual)
    expected = february(known, 9)
    assert february(actual, 9) == expected
    assert actual == before
    assert february(known + [float("nan"), -1, "not observed"], 9) == expected
    # Earlier-month history is equally outside this month's budget consumption.
    history = [float("nan")] * 31 + [10.]
    assert weekly_review_month_budget(560, history, origin_date="2025-01-01",
        start_day=31, decision_day=31, end_day=58)["arrived_demand_qty"] == 10


def test_weekly_review_expiry_and_overrun_use_actual_month_total():
    actual = [0.] * 28
    actual[6] = 300
    row = february(actual, 27)  # Sunday at month end: no remaining forecast days.
    assert row["future_days"] == row["review_future_days"] == 0
    assert row["future_daily_qty"] == row["remaining_forecast_qty"] == 0
    assert row["expired_forecast_qty"] == 700
    actual[9] = 900
    midweek = february(actual, 9)
    assert midweek["arrived_demand_qty"] == 1200
    assert midweek["monthly_remaining_after_actual_qty"] == 0
    assert midweek["future_daily_qty"] == pytest.approx(700 / 21)
    assert february(actual, 13)["future_daily_qty"] == 0
    assert february(actual, 27)["expired_forecast_qty"] == 0


def test_weekly_review_non_sunday_month_end_expires_actual_not_stale_rate():
    actual = [0.] * 31
    actual[25], actual[30] = 300, 400  # Sunday January26 and Friday January31.
    row = weekly_review_month_budget(1000, actual, origin_date="2025-01-01",
        start_day=0, decision_day=30, end_day=30)
    assert row["review_observed_through_day"] == 25
    assert row["review_demand_qty"] == 300
    assert row["review_remaining_month_qty"] == 700
    assert row["unreviewed_actual_demand_qty"] == 400
    assert row["remaining_forecast_qty"] == row["future_daily_qty"] == 0
    assert row["expired_forecast_qty"] == 300


def test_weekly_review_policy_fields_and_legacy_daily_policy_remain_distinct():
    assert WEEKLY_REVIEW_MONTHLY_POLICY == "calendar_month_weekly_review_v1"
    assert MONTHLY_CONSUMPTION_POLICY == "calendar_month_actual_demand_v1"
    assert set(WEEKLY_REVIEW_MONTHLY_FIELDS).isdisjoint(MONTHLY_CONSUMPTION_FIELDS)
    row = february([100.], 0)
    assert set(WEEKLY_REVIEW_MONTHLY_FIELDS) <= row.keys()
    assert row["future_daily_qty"] == pytest.approx(1000 / 28)
    old = remaining_month_budget(1000, [100.], start_day=0, decision_day=0, end_day=27)
    assert old["remaining_forecast_qty"] == 900
    assert old["future_daily_qty"] == pytest.approx(900 / 27)
    assert not set(WEEKLY_REVIEW_MONTHLY_FIELDS) & old.keys()


def test_weekly_review_uses_calendar_weekday_and_leap_month_length():
    actual = [0.] * 29
    actual[3] = 290  # Sunday February4,2024; origin is Thursday February1.
    sunday = weekly_review_month_budget(2900, actual, origin_date="2024-02-01",
        start_day=0, decision_day=3, end_day=28)
    assert sunday["review_future_days"] == 25
    assert sunday["future_daily_qty"] == pytest.approx(2610 / 25)
    monday = weekly_review_month_budget(2900, actual, origin_date="2024-02-01",
        start_day=0, decision_day=3, end_day=28, review_weekday=0)
    assert monday["review_observed_through_day"] == -1
    assert monday["future_daily_qty"] == 100
    next_day = weekly_review_month_budget(2900, actual, origin_date="2024-02-01",
        start_day=0, decision_day=4, end_day=28, review_weekday=0)
    assert next_day["review_observed_through_day"] == 4
    assert next_day["future_daily_qty"] == pytest.approx(2610 / 24)


def test_weekly_review_zero_budget_keeps_actual_demand():
    row = february([17.], 0, budget=0)
    assert row["arrived_demand_qty"] == row["unreviewed_actual_demand_qty"] == 17
    assert row["future_daily_qty"] == row["remaining_forecast_qty"] == 0
    assert row["monthly_remaining_after_actual_qty"] == 0


@pytest.mark.parametrize("replacement", [
    {"budget": -1}, {"budget": math.inf}, {"budget": math.nan},
    {"budget": True}, {"budget": "1000"},
    {"start_day": -1}, {"start_day": 1}, {"decision_day": -1},
    {"decision_day": 28}, {"decision_day": True}, {"end_day": 28},
    {"end_day": 27.0}, {"review_weekday": -1}, {"review_weekday": 7},
    {"review_weekday": True}, {"origin_date": "2027-02-30"},
    {"origin_date": "20270201"}, {"origin_date": None},
    {"observed_demand": []}, {"observed_demand": [math.inf]},
    {"observed_demand": [math.nan]}, {"observed_demand": [-1]},
    {"observed_demand": [True]}, {"observed_demand": ["1"]},
    {"observed_demand": "0"},
])
def test_weekly_review_refuses_invalid_inputs(replacement):
    args = dict(budget=1000, observed_demand=[0.], origin_date="2027-02-01",
                start_day=0, decision_day=0, end_day=27, review_weekday=6)
    args.update(replacement)
    with pytest.raises(ValueError):
        weekly_review_month_budget(**args)


def test_weekly_review_refuses_overflowing_observed_total():
    with pytest.raises(ValueError, match="total"):
        february([1e308, 1e308], 1)
