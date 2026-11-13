"""Memory-only monthly forecasts; no workbook/file fixtures or physical rerun."""
from copy import deepcopy
import csv
from datetime import date, timedelta
import io
import math

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.monthly_forecast import (
    MONTHLY_CONSUMPTION_FIELDS, MONTHLY_CONSUMPTION_POLICY, calendar_month_bounds,
)


PAIR = ("C-memory", "item:finished")


def make_forecast(*, origin="2025-02-01", weekly_qty=250, rows=None, customer=False, annual=None):
    origin_date = date.fromisoformat(origin)
    first = (7 - origin_date.weekday()) % 7 if customer else (6 - origin_date.weekday()) % 7
    vintage = -origin_date.weekday() if customer else 0
    if first == 0:
        first = 7
    payload = dict(schema_version=1, origin_date=origin,
        calendar="monday_start" if customer else "sunday_start", repeat_period_days=365,
        current_bucket_policy="excluded_unresolved_carry_over", rows=rows or [
            dict(node_id=PAIR[0], item_id=PAIR[1], uom="UN", vintage_day=vintage,
                 period_start_day=start, period_days=7, qty=weekly_qty,
                 source_row=f"known-{start}", source_file="memory-only")
            for start in range(first, first + 98, 7)])
    return engine.RollingMrpForecast(payload, demand_pairs={PAIR}, origin_date=origin,
        missing_period_policy="last_known_period_v1", consumption_policy=MONTHLY_CONSUMPTION_POLICY,
        annual_projection_policy=annual,
        customer_demand_policy="source_customer_history_v1" if customer else None)


def observe(forecast, through, actuals):
    for day in range(forecast.consumption_revision, through + 1):
        forecast.observe_demand(day, {PAIR: actuals.get(day, 0)})


def future_total(forecast, decision, start, count):
    return math.fsum(forecast.window(PAIR, decision_day=decision, target_day=day,
        fallback_daily_values=[999])[0] for day in range(start, start + count))


def test_monthly_user_example_700_then450_on_two_weekly_reviews():
    forecast = make_forecast()
    observe(forecast, 6, {0: 300})
    row = forecast.consumption_audit(PAIR, 6)
    assert row["monthly_forecast_qty"] == pytest.approx(1000)
    assert row["weekly_forecast_qty"] == ""
    assert row["remaining_forecast_qty"] == pytest.approx(700)
    assert future_total(forecast, 6, 7, 7) == pytest.approx(700 / 3)
    observe(forecast, 13, {7: 250})
    assert forecast.consumption_audit(PAIR, 13)["remaining_forecast_qty"] == pytest.approx(450)
    assert future_total(forecast, 13, 14, 7) == pytest.approx(225)


@pytest.mark.parametrize("origin,expected_days", [
    ("2025-01-01", 31), ("2025-02-01", 28), ("2025-04-01", 30), ("2024-02-01", 29),
])
def test_monthly_real_calendar_not_four_week_month(origin, expected_days):
    forecast = make_forecast(origin=origin, weekly_qty=700)
    observe(forecast, 0, {0: 1})
    row = forecast.consumption_audit(PAIR, 0)
    assert (row["period_start_day"], row["period_end_day"]) == (0, expected_days - 1)
    assert row["monthly_forecast_qty"] == expected_days * 100
    assert row["arrived_demand_qty"] + row["remaining_forecast_qty"] == expected_days * 100


def test_monthly_reset_only_forecast_and_not_physical_obligations():
    forecast = make_forecast(weekly_qty=700)
    physical = dict(backlog=21, stock=30, WIP=70, firm=[dict(id="committed", qty=80)])
    before = deepcopy(physical)
    observe(forecast, 27, {0: 3000})
    assert forecast.consumption_audit(PAIR, 27)["expired_forecast_qty"] == 0
    observe(forecast, 28, {28: 6})
    row = forecast.consumption_audit(PAIR, 28)
    assert row["monthly_forecast_qty"] == 3100
    assert row["arrived_demand_qty"] == 6 and row["remaining_forecast_qty"] == 3094
    assert physical == before
    assert physical["backlog"] + row["today_arrived_qty"] == 27


def test_monthly_future_demand_does_not_rewrite_past_asof_and_overrun_remains_real():
    forecast = make_forecast()
    observe(forecast, 6, {0: 300})
    before = deepcopy(forecast.consumption_audit(PAIR, 6))
    observe(forecast, 13, {7: 1000})
    assert forecast.consumption_audit(PAIR, 6) == before
    now = forecast.consumption_audit(PAIR, 13)
    assert now["arrived_demand_qty"] == 1300
    assert now["remaining_forecast_qty"] == 0
    assert future_total(forecast, 13, 14, 14) == 0


def test_monthly_month_opening_cutoff_survives_future_query_and_later_vintage():
    rows = []
    for vintage, first, weekly in [(0, 1, 70), (24, 31, 140), (40, 45, 700)]:
        rows += [dict(node_id=PAIR[0], item_id=PAIR[1], uom="UN", vintage_day=vintage,
                      period_start_day=start, period_days=7, qty=weekly,
                      source_row=f"v{vintage}p{start}") for start in range(first, 100, 7)]
    forecast = make_forecast(origin="2025-01-01", rows=rows)
    observe(forecast, 19, {})
    future_total(forecast, 19, 31, 7)  # Planning February in January must not freeze its opening.
    assert (PAIR, 31) not in forecast._monthly_budgets
    observe(forecast, 31, {})
    february = deepcopy(forecast.consumption_audit(PAIR, 31))
    assert february["monthly_forecast_qty"] == 560  #28days*20 from known Jan25 version.
    assert february["budget_source_vintage_days"] == "24"
    observe(forecast, 46, {})
    assert forecast.consumption_audit(PAIR, 46)["monthly_forecast_qty"] == 560
    assert forecast.consumption_audit(PAIR, 31) == february


def test_monthly_customer_projection_opening_fallback_is_counted_not_hidden():
    forecast = make_forecast(origin="2025-01-01", weekly_qty=700, customer=True)
    observe(forecast, 0, {0: 13})
    row = forecast.consumption_audit(PAIR, 0)
    assert row["monthly_forecast_qty"] == 3100
    assert row["budget_fallback_days"] == 5
    assert row["budget_fallback_qty"] == 500 and row["budget_source_qty"] == 2600
    assert row["source_vintage_day"] == -2
    current, audit = forecast.window(PAIR, decision_day=0, target_day=0, fallback_daily_values=[999])
    assert current == 13 and audit["actual_order_days"] == 1


def test_monthly_expiry_and_audit_csv_are_distinct_from_weekly():
    forecast = make_forecast(weekly_qty=700)
    observe(forecast, 27, {0: 300})
    row = forecast.consumption_audit(PAIR, 27)
    assert row["expired_forecast_qty"] == 2500
    assert row["future_days"] == row["remaining_forecast_qty"] == 0
    assert row["period_kind"] == "calendar_month" and row["weekly_forecast_qty"] == ""
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=engine.FORECAST_CONSUMPTION_FIELDS + MONTHLY_CONSUMPTION_FIELDS)
    writer.writeheader(); writer.writerow(row)
    assert "monthly_forecast_qty" in stream.getvalue()


def test_monthly_refuses_partial_origin_and_unsupported_annual_projection():
    with pytest.raises(ValueError, match="month-opening"):
        make_forecast(origin="2025-02-02")
    with pytest.raises(ValueError, match="no annual"):
        make_forecast(origin="2025-01-01", annual="previous_year_105pct_v1")
    assert calendar_month_bounds("2025-01-01", 31) == (31, 58)
    with pytest.raises(ValueError, match="nonnegative"):
        calendar_month_bounds("2025-01-01", -1)


def test_monthly_scope_retains_customer_source_and_daily_bucket_guards():
    args = dict(source_forecast=True, missing_period_policy="last_known_period_v1",
        production_execution_policy="dated_releases_v1",
        nodes=[dict(id="C", type="customer"), dict(id="D", type="distribution_center"),
               dict(id="F", type="factory")], demand_pairs={("C", "PF")},
        produced_pairs={("F", "PF")}, lanes_by_dest_item={
            ("C", "PF"): [dict(src="D")], ("D", "PF"): [dict(src="F")]})
    assert engine.resolve_forecast_consumption(MONTHLY_CONSUMPTION_POLICY, **args) == {("C", "PF")}
    with pytest.raises(ValueError, match="Monthly forecast"):
        engine.resolve_forecast_consumption(MONTHLY_CONSUMPTION_POLICY, **args, target_bucket_days=7)


def test_monthly_dispatch_keeps_source_profile_capped_not_future_physical_orders():
    forecast = make_forecast(origin="2025-02-01", weekly_qty=250, customer=True)
    observe(forecast, 6, {0: 900})
    values, audit = forecast.customer_dispatch_window(PAIR, decision_day=6, target_day=7, window_days=7)
    assert sum(values) == pytest.approx(100 / 3)
    assert "capped_by_month_remaining" in audit["customer_dispatch_forecast_basis"]
