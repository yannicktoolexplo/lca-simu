from __future__ import annotations

from collections import defaultdict
from typing import Any


FACTORY_NERVOUSNESS_FIELDS = [
    "node_id",
    "output_item_id",
    "horizon_days",
    "constraint_rows",
    "desired_signal_days",
    "planned_signal_days",
    "actual_production_days",
    "actual_production_day_share",
    "desired_without_actual_days",
    "production_start_count",
    "production_stop_count",
    "requested_lot_starts",
    "actual_lot_starts",
    "campaign_rows",
    "completed_without_delay_campaigns",
    "completed_after_delay_campaigns",
    "blocked_campaigns",
    "delay_day_count",
    "desired_qty_total",
    "planned_signal_qty_total",
    "actual_qty_total",
    "avg_desired_qty_on_signal_days",
    "avg_actual_qty_on_production_days",
    "max_desired_qty",
    "max_planned_qty",
    "max_actual_qty",
    "lot_amplification_vs_avg_desired",
    "lot_amplification_vs_max_desired",
    "desired_churn_ratio",
    "planned_churn_ratio",
    "actual_churn_ratio",
    "nervousness_level",
    "nervousness_type",
    "business_reading",
]

EPS = 1e-9


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 6)


def _churn_ratio(values: list[float]) -> float:
    total = sum(abs(value) for value in values)
    if total <= EPS:
        return 0.0
    prev = 0.0
    churn = 0.0
    for value in values:
        churn += abs(value - prev)
        prev = value
    return churn / total


def _start_stop_counts(values: list[float]) -> tuple[int, int]:
    starts = 0
    stops = 0
    prev_active = False
    for value in values:
        active = value > EPS
        if active and not prev_active:
            starts += 1
        elif not active and prev_active:
            stops += 1
        prev_active = active
    return starts, stops


def _classify(
    *,
    horizon_days: int,
    actual_lot_starts: float,
    lot_amplification_vs_avg_desired: float,
    desired_without_actual_days: int,
    delayed_campaigns: int,
) -> tuple[str, str]:
    start_share = actual_lot_starts / horizon_days if horizon_days > 0 else 0.0
    high_frequency = start_share >= 0.40
    lumpy_batches = lot_amplification_vs_avg_desired >= 5.0
    delayed = delayed_campaigns > 0 or desired_without_actual_days >= 10
    if high_frequency and delayed:
        return "high", "cadence frequente avec reports"
    if high_frequency:
        return "high", "cadence tres frequente"
    if lumpy_batches and delayed:
        return "high", "gros lots avec reports intrants"
    if lumpy_batches:
        return "high", "gros lots par rapport au besoin"
    if delayed:
        return "medium", "reports ou jours non servis en production"
    if start_share >= 0.15 or lot_amplification_vs_avg_desired >= 2.0:
        return "medium", "cadence ou lots a surveiller"
    return "low", "stable"


def build_factory_nervousness_rows(
    production_constraint_rows: list[dict[str, Any]],
    production_campaign_rows: list[dict[str, Any]],
    *,
    horizon_days: int,
) -> list[dict[str, Any]]:
    """Build a business-level factory nervousness diagnostic.

    This is intentionally separate from shortage reporting. A line can have few
    blocked campaigns but still be nervous because it launches too frequently or
    because fixed lots are much larger than the smoothed production need.
    """

    horizon = max(0, int(horizon_days))
    pairs: set[tuple[str, str]] = set()
    constraint_rows_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in production_constraint_rows:
        pair = (str(row.get("node_id") or ""), str(row.get("output_item_id") or ""))
        if not pair[0] or not pair[1]:
            continue
        pairs.add(pair)
        constraint_rows_by_pair[pair].append(row)

    campaign_rows_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in production_campaign_rows:
        pair = (str(row.get("node_id") or ""), str(row.get("output_item_id") or ""))
        if not pair[0] or not pair[1]:
            continue
        pairs.add(pair)
        campaign_rows_by_pair[pair].append(row)

    out: list[dict[str, Any]] = []
    for pair in sorted(pairs):
        desired = [0.0] * horizon
        planned = [0.0] * horizon
        actual = [0.0] * horizon
        requested_lot_starts = 0.0
        actual_lot_starts = 0.0

        for row in constraint_rows_by_pair.get(pair, []):
            day = _to_int(row.get("day"), -1)
            if 0 <= day < horizon:
                desired[day] += max(0.0, _to_float(row.get("desired_qty")))
                planned[day] += max(0.0, _to_float(row.get("planned_qty_after_lot_rule")))
                actual[day] += max(0.0, _to_float(row.get("actual_qty")))
            requested_lot_starts += max(0.0, _to_float(row.get("requested_lot_starts")))
            actual_lot_starts += max(0.0, _to_float(row.get("actual_lot_starts")))

        campaign_rows = campaign_rows_by_pair.get(pair, [])
        completed_without_delay = sum(1 for row in campaign_rows if str(row.get("status") or "") == "completed_without_delay")
        completed_after_delay = sum(1 for row in campaign_rows if str(row.get("status") or "") == "completed_after_delay")
        blocked_campaigns = sum(
            1
            for row in campaign_rows
            if str(row.get("status") or "") in {"still_blocked", "not_started_blocked"}
        )
        delayed_campaigns = completed_after_delay + blocked_campaigns
        delay_day_count = sum(_to_int(row.get("delay_day_count"), 0) for row in campaign_rows)

        desired_total = sum(desired)
        planned_total = sum(planned)
        actual_total = sum(actual)
        desired_signal_days = sum(1 for value in desired if value > EPS)
        planned_signal_days = sum(1 for value in planned if value > EPS)
        actual_production_days = sum(1 for value in actual if value > EPS)
        desired_without_actual_days = sum(1 for desired_qty, actual_qty in zip(desired, actual) if desired_qty > EPS and actual_qty <= EPS)
        production_starts, production_stops = _start_stop_counts(actual)
        avg_desired = desired_total / desired_signal_days if desired_signal_days else 0.0
        avg_actual = actual_total / actual_production_days if actual_production_days else 0.0
        max_desired = max(desired, default=0.0)
        max_planned = max(planned, default=0.0)
        max_actual = max(actual, default=0.0)
        amp_avg = avg_actual / avg_desired if avg_desired > EPS else 0.0
        amp_max = max_actual / max_desired if max_desired > EPS else 0.0
        level, kind = _classify(
            horizon_days=horizon,
            actual_lot_starts=actual_lot_starts,
            lot_amplification_vs_avg_desired=amp_avg,
            desired_without_actual_days=desired_without_actual_days,
            delayed_campaigns=delayed_campaigns,
        )
        if "cadence" in kind and "reports" not in kind:
            reading = "Nervosite haute: lancements tres frequents meme sans report; verifier regroupement et taille de lot."
        elif "gros lots" in kind and "reports" not in kind:
            reading = "Nervosite haute: lots tres grands par rapport au besoin lisse; verifier stock cible et cadence."
        elif level == "high":
            reading = "Nervosite haute: verifier taille de lot, frequence de lancement et causes de report."
        elif level == "medium":
            reading = "Nervosite moderee: ligne stable globalement mais signaux a surveiller."
        else:
            reading = "Nervosite faible: peu de reports et cadence compatible avec le besoin simule."

        out.append(
            {
                "node_id": pair[0],
                "output_item_id": pair[1],
                "horizon_days": horizon,
                "constraint_rows": len(constraint_rows_by_pair.get(pair, [])),
                "desired_signal_days": desired_signal_days,
                "planned_signal_days": planned_signal_days,
                "actual_production_days": actual_production_days,
                "actual_production_day_share": _round(actual_production_days / horizon if horizon > 0 else 0.0),
                "desired_without_actual_days": desired_without_actual_days,
                "production_start_count": production_starts,
                "production_stop_count": production_stops,
                "requested_lot_starts": _round(requested_lot_starts),
                "actual_lot_starts": _round(actual_lot_starts),
                "campaign_rows": len(campaign_rows),
                "completed_without_delay_campaigns": completed_without_delay,
                "completed_after_delay_campaigns": completed_after_delay,
                "blocked_campaigns": blocked_campaigns,
                "delay_day_count": delay_day_count,
                "desired_qty_total": _round(desired_total),
                "planned_signal_qty_total": _round(planned_total),
                "actual_qty_total": _round(actual_total),
                "avg_desired_qty_on_signal_days": _round(avg_desired),
                "avg_actual_qty_on_production_days": _round(avg_actual),
                "max_desired_qty": _round(max_desired),
                "max_planned_qty": _round(max_planned),
                "max_actual_qty": _round(max_actual),
                "lot_amplification_vs_avg_desired": _round(amp_avg),
                "lot_amplification_vs_max_desired": _round(amp_max),
                "desired_churn_ratio": _round(_churn_ratio(desired)),
                "planned_churn_ratio": _round(_churn_ratio(planned)),
                "actual_churn_ratio": _round(_churn_ratio(actual)),
                "nervousness_level": level,
                "nervousness_type": kind,
                "business_reading": reading,
            }
        )
    return out
