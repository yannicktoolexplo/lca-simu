"""Calendar-month forecast arithmetic, independent of physical stock and orders.

Source daily forecasts are frozen as-of month opening by the caller. Only
already observed real demand consumes that budget. This module never changes
physical demand, backlog, inventory, manufacturing orders or lot quantities.
"""
from __future__ import annotations

from datetime import date, timedelta
import math


MONTHLY_CONSUMPTION_POLICY = "calendar_month_actual_demand_v1"
MONTHLY_CONSUMPTION_FIELDS = [
    "period_kind", "monthly_forecast_qty", "month_opening_day",
    "budget_source_vintage_days", "budget_source_rows", "budget_fallback_days",
    "budget_source_qty", "budget_fallback_qty", "redistribution_review", "budget_basis",
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
