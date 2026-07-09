"""Compact trajectory extraction for Monte Carlo simulation runs."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from etudecas.simulation.result_paths import data_path, resolve_existing_path


TRAJECTORY_METRICS: dict[str, dict[str, Any]] = {
    "service_rate": {
        "label": "Service client cumule",
        "y_label": "Servi / demande cumulee (%)",
        "reference_value": 100.0,
        "reference_label": "service 100%",
        "digits": 4,
    },
    "backlog": {
        "label": "Backlog client",
        "y_label": "Backlog fin jour",
        "reference_value": 0.0,
        "reference_label": "objectif backlog 0",
        "digits": 3,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
    "produced_qty": {
        "label": "Production realisee",
        "y_label": "Quantite produite / jour",
        "digits": 3,
        "zero_floor": True,
    },
    "production_reports": {
        "label": "Lots production reportes",
        "y_label": "Volume de lots entrant en report / jour",
        "reference_value": 0.0,
        "reference_label": "objectif report 0",
        "digits": 3,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
    "production_delay_active_orders": {
        "label": "Ordres production en attente",
        "y_label": "Campagnes bloquees en fin de jour",
        "reference_value": 0.0,
        "reference_label": "objectif attente 0",
        "digits": 0,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
    "production_delay_active_qty": {
        "label": "Volume production en attente",
        "y_label": "Volume de lots encore bloque",
        "reference_value": 0.0,
        "reference_label": "objectif attente 0",
        "digits": 3,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
    "production_delay_input_qty": {
        "label": "Reports par intrants",
        "y_label": "Volume de lots retarde par MP/PFI",
        "reference_value": 0.0,
        "reference_label": "objectif report 0",
        "digits": 3,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
    "production_delay_capacity_qty": {
        "label": "Reports par capacite",
        "y_label": "Volume de lots retarde par capacite",
        "reference_value": 0.0,
        "reference_label": "objectif report 0",
        "digits": 3,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
    "total_supply_cost_cum": {
        "label": "Cout supply cumule",
        "y_label": "Cout cumule",
        "digits": 2,
        "zero_floor": True,
    },
    "supplier_capacity_binding": {
        "label": "Contrainte capacite fournisseur",
        "y_label": "Quantite contrainte / jour",
        "digits": 3,
        "zero_floor": True,
        "upper_percentile": 1.0,
    },
}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _to_day(value: Any) -> int | None:
    try:
        day = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return day if day >= 0 else None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _simulation_data_file(output_dir: Path, filename: str) -> Path:
    return resolve_existing_path(data_path(output_dir, filename), output_dir / filename)


def _round_metric_value(metric_key: str, value: float) -> float:
    digits = int(TRAJECTORY_METRICS.get(metric_key, {}).get("digits", 3))
    return round(float(value), digits)


def _select_indices(length: int, max_points: int) -> list[int]:
    if max_points <= 0 or length <= max_points:
        return list(range(length))
    if max_points <= 1:
        return [0]
    return sorted({round(i * (length - 1) / (max_points - 1)) for i in range(max_points)})


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    q = max(0.0, min(1.0, q))
    pos = q * (len(sorted_values) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    weight = pos - lo
    return sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight


def _select_display_runs(runs: list[dict[str, Any]], max_display_runs: int) -> list[dict[str, Any]]:
    if max_display_runs <= 0 or len(runs) <= max_display_runs:
        return runs
    baseline = [run for run in runs if bool(run.get("is_baseline"))]
    stochastic = [run for run in runs if not bool(run.get("is_baseline"))]
    slots = max(0, max_display_runs - len(baseline))
    if slots <= 0:
        return baseline[:max_display_runs]
    indices = _select_indices(len(stochastic), slots)
    return baseline + [stochastic[idx] for idx in indices if idx < len(stochastic)]


def _metric_values_for_days(
    run: dict[str, Any],
    metric_key: str,
    days: list[int],
) -> list[float] | None:
    points = {int(day): float(value) for day, value in (run.get("series") or {}).get(metric_key, [])}
    if not points:
        return None
    fallback = 0.0
    values: list[float] = []
    for day in days:
        fallback = points.get(day, fallback)
        values.append(_round_metric_value(metric_key, fallback))
    return values


def extract_run_trajectories(output_dir: Path, *, max_points: int = 0) -> dict[str, list[tuple[int, float]]]:
    """Extract compact business trajectories from one simulation output folder.

    The function reads only standard CSV outputs and returns a small set of
    generic KPI trajectories. It does not keep the run artifacts.
    """

    daily_rows = _read_csv_rows(_simulation_data_file(output_dir, "first_simulation_daily.csv"))
    if not daily_rows:
        return {}

    days: list[int] = []
    raw: dict[str, list[tuple[int, float]]] = {key: [] for key in TRAJECTORY_METRICS}
    cumulative_demand = 0.0
    cumulative_served = 0.0
    cumulative_cost = 0.0
    for row in daily_rows:
        day = _to_day(row.get("day"))
        if day is None:
            continue
        days.append(day)
        demand = max(0.0, _to_float(row.get("demand")))
        served = max(0.0, _to_float(row.get("served")))
        cumulative_demand += demand
        cumulative_served += served
        cumulative_cost += _to_float(row.get("total_supply_cost_day"))
        service_rate = (100.0 * cumulative_served / cumulative_demand) if cumulative_demand > 0 else 100.0
        raw["service_rate"].append((day, service_rate))
        raw["backlog"].append((day, max(0.0, _to_float(row.get("backlog_end")))))
        raw["produced_qty"].append((day, max(0.0, _to_float(row.get("produced_qty")))))
        raw["total_supply_cost_cum"].append((day, max(0.0, cumulative_cost)))
        raw["supplier_capacity_binding"].append((day, max(0.0, _to_float(row.get("supplier_capacity_binding_qty")))))

    report_by_day: dict[int, float] = defaultdict(float)
    input_report_by_day: dict[int, float] = defaultdict(float)
    capacity_report_by_day: dict[int, float] = defaultdict(float)
    active_order_delta: dict[int, float] = defaultdict(float)
    active_qty_delta: dict[int, float] = defaultdict(float)
    campaign_rows = _read_csv_rows(_simulation_data_file(output_dir, "production_campaigns.csv"))
    if campaign_rows:
        horizon_end = max(days) + 1 if days else 0
        for row in campaign_rows:
            status = str(row.get("status") or "")
            if status not in {"completed_after_delay", "still_blocked", "not_started_blocked"}:
                continue
            first_delay = _to_day(row.get("first_delay_day"))
            if first_delay is None:
                continue
            qty = max(
                0.0,
                _to_float(row.get("blocked_lot_qty"))
                or _to_float(row.get("planned_qty"))
                or _to_float(row.get("requested_qty")),
            )
            if qty <= 0.0:
                continue
            report_by_day[first_delay] += qty
            reasons = {
                str(reason).strip()
                for reason in str(row.get("delay_reasons") or "").split("|")
                if str(reason).strip()
            }
            if "input_shortage" in reasons:
                input_report_by_day[first_delay] += qty
            if "capacity" in reasons:
                capacity_report_by_day[first_delay] += qty
            completed_day = _to_day(row.get("completed_day"))
            end_day = completed_day if completed_day is not None else horizon_end
            if end_day <= first_delay:
                end_day = first_delay + 1
            active_order_delta[first_delay] += 1.0
            active_order_delta[end_day] -= 1.0
            active_qty_delta[first_delay] += qty
            active_qty_delta[end_day] -= qty
    else:
        # Legacy fallback: daily constraints do not identify campaigns, so this
        # is a repeated planning signal rather than a unique delayed lot volume.
        for row in _read_csv_rows(_simulation_data_file(output_dir, "production_constraint_daily.csv")):
            day = _to_day(row.get("day"))
            if day is None:
                continue
            shortfall = max(0.0, _to_float(row.get("shortfall_vs_lot_plan_qty")))
            if shortfall > 0:
                report_by_day[day] += shortfall
                if str(row.get("binding_cause") or "") == "input_shortage":
                    input_report_by_day[day] += shortfall
                if str(row.get("binding_cause") or "") == "capacity":
                    capacity_report_by_day[day] += shortfall
    active_orders = 0.0
    active_qty = 0.0
    active_orders_by_day: dict[int, float] = {}
    active_qty_by_day: dict[int, float] = {}
    for day in sorted(set(days)):
        active_orders += active_order_delta.get(day, 0.0)
        active_qty += active_qty_delta.get(day, 0.0)
        active_orders_by_day[day] = max(0.0, active_orders)
        active_qty_by_day[day] = max(0.0, active_qty)
    raw["production_reports"] = [(day, report_by_day.get(day, 0.0)) for day in sorted(set(days))]
    raw["production_delay_active_orders"] = [(day, active_orders_by_day.get(day, 0.0)) for day in sorted(set(days))]
    raw["production_delay_active_qty"] = [(day, active_qty_by_day.get(day, 0.0)) for day in sorted(set(days))]
    raw["production_delay_input_qty"] = [(day, input_report_by_day.get(day, 0.0)) for day in sorted(set(days))]
    raw["production_delay_capacity_qty"] = [(day, capacity_report_by_day.get(day, 0.0)) for day in sorted(set(days))]

    out: dict[str, list[tuple[int, float]]] = {}
    for metric_key, points in raw.items():
        ordered = sorted(points, key=lambda item: item[0])
        indices = _select_indices(len(ordered), max_points)
        out[metric_key] = [
            (int(ordered[idx][0]), _round_metric_value(metric_key, ordered[idx][1]))
            for idx in indices
        ]
    return out


def build_montecarlo_trajectories_payload(
    runs: list[dict[str, Any]],
    *,
    scenario_id: str,
    seed: int,
    profile: str,
    max_points: int = 0,
    max_display_runs: int = 60,
) -> dict[str, Any]:
    """Build a compact JSON payload from per-run trajectory extracts."""

    usable_runs = [run for run in runs if isinstance(run.get("series"), dict) and run.get("series")]
    day_set = {
        int(day)
        for run in usable_runs
        for points in (run.get("series") or {}).values()
        for day, _value in points
    }
    days = sorted(day_set)
    indices = _select_indices(len(days), max_points)
    days = [days[idx] for idx in indices]

    metrics: dict[str, Any] = {}
    for metric_key, meta in TRAJECTORY_METRICS.items():
        all_run_values = [
            values
            for run in usable_runs
            if (values := _metric_values_for_days(run, metric_key, days)) is not None
        ]
        if not all_run_values:
            continue
        percentile_payload: dict[str, list[float]] = {}
        for label, q in [
            ("min", 0.00),
            ("p05", 0.05),
            ("p10", 0.10),
            ("p25", 0.25),
            ("p50", 0.50),
            ("p75", 0.75),
            ("p90", 0.90),
            ("p95", 0.95),
            ("max", 1.00),
        ]:
            percentile_payload[label] = [
                _round_metric_value(metric_key, _percentile(sorted(values[pos] for values in all_run_values), q))
                for pos in range(len(days))
            ]

        series_payload: list[dict[str, Any]] = []
        display_runs = _select_display_runs(usable_runs, max_display_runs)
        for run in display_runs:
            values = _metric_values_for_days(run, metric_key, days)
            if values is None:
                continue
            is_baseline = bool(run.get("is_baseline"))
            series_payload.append(
                {
                    "run_id": str(run.get("run_id") or ""),
                    "label": "Nominal" if is_baseline else str(run.get("run_id") or "scenario"),
                    "is_baseline": is_baseline,
                    "values": values,
                }
            )
        if series_payload:
            metrics[metric_key] = {
                "label": meta.get("label", metric_key),
                "y_label": meta.get("y_label", ""),
                "reference_value": meta.get("reference_value"),
                "reference_label": meta.get("reference_label", ""),
                "zero_floor": bool(meta.get("zero_floor")),
                "upper_percentile": float(meta.get("upper_percentile", 0.90)),
                "bands": percentile_payload,
                "series": series_payload,
                "series_total_count": len(all_run_values),
                "series_display_count": len(series_payload),
            }

    return {
        "schema_version": "etudecas.montecarlo_trajectories.v1",
        "scenario_id": scenario_id,
        "seed": int(seed),
        "uncertainty_profile": profile,
        "days": days,
        "run_count": len(usable_runs),
        "stochastic_run_count": sum(1 for run in usable_runs if not bool(run.get("is_baseline"))),
        "max_points": int(max_points),
        "max_display_runs": int(max_display_runs),
        "metrics": metrics,
    }
