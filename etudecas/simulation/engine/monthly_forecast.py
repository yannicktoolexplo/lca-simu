"""Calendar-month forecast arithmetic, independent of physical stock and orders.

Source daily forecasts are frozen as-of month opening by the caller. Only
already observed real demand consumes that budget. This module never changes
physical demand, backlog, inventory, manufacturing orders or lot quantities.
"""
from __future__ import annotations

from datetime import date, timedelta
from collections.abc import Sequence
import math
from numbers import Real


MONTHLY_CONSUMPTION_POLICY = "calendar_month_actual_demand_v1"
MONTHLY_CONSUMPTION_FIELDS = [
    "period_kind", "monthly_forecast_qty", "month_opening_day",
    "budget_source_vintage_days", "budget_source_rows", "budget_fallback_days",
    "budget_source_qty", "budget_fallback_qty", "redistribution_review", "budget_basis",
]

WEEKLY_REVIEW_MONTHLY_POLICY = "calendar_month_weekly_review_v1"
WEEKLY_REVIEW_MONTHLY_FIELDS = [
    "review_day", "review_observed_through_day", "review_first_forecast_day",
    "review_demand_qty", "review_remaining_month_qty", "review_future_days",
    "unreviewed_actual_demand_qty", "monthly_remaining_after_actual_qty",
    "review_weekday",
]


def calendar_month_bounds(origin_date: str, day: int) -> tuple[int, int]:
    """Return inclusive day offsets for the actual month containing ``day``."""
    if type(day) is not int or day < 0:
        raise ValueError("Monthly consumption requires a nonnegative integer decision day")
    origin = date.fromisoformat(origin_date)
    today = origin + timedelta(days=day)
    start = today.replace(day=1)
    following = (date(today.year + 1, 1, 1) if today.month == 12
                 else date(today.year, today.month + 1, 1))
    return (start - origin).days, (following - origin).days - 1


def remaining_month_budget(budget: float, observed_demand: list[float], *,
                           start_day: int, decision_day: int, end_day: int) -> dict:
    """Consume known demand and spread only the remainder over future days.

    Daily as-of recalculation preserves causality; three equally long future
    weeks consequently each receive one third of the remaining budget. It is
    not a freeze of the manufacturing programme or a manufactured quantity.
    """
    if (not math.isfinite(budget) or budget < 0 or start_day < 0
            or not start_day <= decision_day <= end_day
            or len(observed_demand) <= decision_day):
        raise ValueError("Monthly consumption requires a known budget and observed current month")
    known = observed_demand[start_day:decision_day + 1]
    if any(not math.isfinite(value) or value < 0 for value in known):
        raise ValueError("Observed real demand must be finite and nonnegative")
    demand = math.fsum(known)
    remainder = max(0.0, budget - demand)
    future_days = end_day - decision_day
    return dict(arrived_demand_qty=demand,
        remaining_forecast_qty=remainder if future_days else 0.0,
        future_days=future_days,
        future_daily_qty=remainder / future_days if future_days else 0.0,
        expired_forecast_qty=remainder if not future_days else 0.0)


def _validate_weekly_review_month_inputs(
    budget: float, observed_demand: Sequence[float], *, origin_date: str,
    start_day: int, decision_day: int, end_day: int, review_weekday: int,
) -> tuple[date, list[float], float]:
    """Validate only the observed month prefix; never inspect a future tail."""
    if any(type(value) is not int for value in (start_day, decision_day, end_day)):
        raise ValueError("Monthly review day offsets must be integers")
    if start_day < 0 or not start_day <= decision_day <= end_day:
        raise ValueError("Monthly review requires ordered nonnegative day offsets")
    if type(review_weekday) is not int or not 0 <= review_weekday <= 6:
        raise ValueError("Review weekday must be an integer from 0(Monday) to 6(Sunday)")
    if not isinstance(origin_date, str):
        raise ValueError("Monthly review origin_date must be an ISO calendar date")
    try:
        origin = date.fromisoformat(origin_date)
        today = origin + timedelta(days=decision_day)
        month_start, month_end = calendar_month_bounds(origin_date, decision_day)
    except (ValueError, OverflowError) as error:
        raise ValueError("Monthly review requires valid calendar dates") from error
    if origin.isoformat() != origin_date:
        raise ValueError("Monthly review origin_date must use YYYY-MM-DD")
    if start_day != max(0, month_start) or end_day != month_end:
        raise ValueError("Monthly review bounds must match the current calendar month")

    def finite_nonnegative(value: float, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{label} must be finite nonnegative numbers")
        try:
            numeric = float(value)
        except (ValueError, OverflowError) as error:
            raise ValueError(f"{label} must be finite nonnegative numbers") from error
        if not math.isfinite(numeric) or numeric < 0:
            raise ValueError(f"{label} must be finite nonnegative numbers")
        return numeric

    numeric_budget = finite_nonnegative(budget, "Monthly budget")
    if (not isinstance(observed_demand, Sequence)
            or isinstance(observed_demand, (str, bytes))
            or len(observed_demand) <= decision_day):
        raise ValueError("Monthly review requires observed demand through decision day")
    known = [finite_nonnegative(value, "Observed real demand")
             for value in observed_demand[start_day:decision_day + 1]]
    try:
        total = math.fsum(known)
    except OverflowError as error:
        raise ValueError("Observed real demand total must remain finite") from error
    if not math.isfinite(total):
        raise ValueError("Observed real demand total must remain finite")
    return today, known, numeric_budget


def weekly_review_month_budget(
    budget: float, observed_demand: list[float], *, origin_date: str,
    start_day: int, decision_day: int, end_day: int, review_weekday: int = 6,
) -> dict:
    """Keep a monthly forecast rate fixed between end-of-week reviews.

    A Sunday review includes Sunday's observed real demand and applies to
    Monday onwards. Before the first review, the opening month's budget is
    spread over its days without consuming opening-day demand in advance.
    Actual demand keeps accumulating between reviews, but changes the rate
    only at the next review. At month end only the unconsumed forecast budget
    expires; this pure arithmetic helper never touches physical obligations.
    """
    today, known, numeric_budget = _validate_weekly_review_month_inputs(
        budget, observed_demand, origin_date=origin_date, start_day=start_day,
        decision_day=decision_day, end_day=end_day, review_weekday=review_weekday)
    last_review = decision_day - (today.weekday() - review_weekday) % 7
    cutoff = last_review if last_review >= start_day else start_day - 1
    reviewed_days = cutoff - start_day + 1
    reviewed_demand = math.fsum(known[:reviewed_days])
    arrived_demand = math.fsum(known)
    review_remaining = max(0.0, numeric_budget - reviewed_demand)
    review_future_days = end_day - cutoff
    rate = review_remaining / review_future_days if review_future_days else 0.0
    future_days = end_day - decision_day
    monthly_remaining = max(0.0, numeric_budget - arrived_demand)
    return dict(
        arrived_demand_qty=arrived_demand,
        remaining_forecast_qty=rate * future_days,
        future_days=future_days,
        future_daily_qty=rate if future_days else 0.0,
        expired_forecast_qty=monthly_remaining if not future_days else 0.0,
        review_day=cutoff if cutoff >= start_day else start_day,
        review_observed_through_day=cutoff,
        review_first_forecast_day=cutoff + 1,
        review_demand_qty=reviewed_demand,
        review_remaining_month_qty=review_remaining,
        review_future_days=review_future_days,
        unreviewed_actual_demand_qty=math.fsum(known[reviewed_days:]),
        monthly_remaining_after_actual_qty=monthly_remaining,
        review_weekday=review_weekday,
    )
