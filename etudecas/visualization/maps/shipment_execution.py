"""Physical transport observations, distinct from reservations and forecasts."""
from __future__ import annotations

import math
from typing import Any


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def executed_shipment_day(row: dict, *, arrival: bool = False, horizon_days: int | None = None) -> int | None:
    """Use explicit execution flags when present; bound legacy dates by observation."""
    prefix = "arrival" if arrival else "departure"
    flag = str(row.get(prefix + "_executed", "")).strip().lower()
    if flag and flag not in {"1", "1.0", "true", "yes"}:
        return None
    status = str(row.get("execution_status") or "")
    if status in {"reserved_pending_departure", "planned_pending_departure"}:
        return None
    if arrival and status == "in_transit":
        return None
    day = number(row.get("realized_" + prefix + "_day"))
    if day is None:
        # An explicit execution contract must carry its actual date. Historical
        # exports without that contract use their event date, with horizon checks.
        if flag and "realized_" + prefix + "_day" in row:
            return None
        day = number(row.get("arrival_day" if arrival else "day"))
    if day is None or day < 0:
        return None
    observation = number(row.get("observation_day"))
    if observation is not None and day > observation:
        return None
    if horizon_days is not None and horizon_days > 0 and day >= horizon_days:
        return None
    return int(day)


def observed_transport_lead(row: dict, *, horizon_days: int | None = None) -> float | None:
    receipt = executed_shipment_day(row, arrival=True, horizon_days=horizon_days)
    departure = executed_shipment_day(row, horizon_days=horizon_days)
    if receipt is None or departure is None or receipt < departure:
        return None
    return float(receipt - departure)
