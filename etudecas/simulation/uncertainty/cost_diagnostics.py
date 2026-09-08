"""Transparent diagnostics for Monte Carlo supply-cost results."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import median
from typing import Any


INCLUDED_COST_COMPONENTS = {
    "purchase": "kpi::total_purchase_cost",
    "transport": "kpi::total_transport_cost",
    "capital_holding": "kpi::total_holding_cost",
    "warehouse_operating": "kpi::total_warehouse_operating_cost",
    "inventory_risk": "kpi::total_inventory_risk_cost",
    "production": "kpi::total_production_cost",
}

SEPARATE_RISK_COSTS = {
    "exceptional_supply": "kpi::total_external_procurement_cost",
    "operational_risk": "kpi::operational_risk_cost",
}

EXCLUDED_FACTORS = {"factor::supplier_reliability_scale"}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = min(1.0, max(0.0, q)) * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _pearson(left: list[float], right: list[float]) -> float:
    count = min(len(left), len(right))
    if count < 3:
        return 0.0
    xs = left[:count]
    ys = right[:count]
    x_mean = sum(xs) / count
    y_mean = sum(ys) / count
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_norm = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    y_norm = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    return numerator / (x_norm * y_norm) if x_norm > 1e-12 and y_norm > 1e-12 else 0.0


def _stats(rows: list[dict[str, Any]], column: str) -> dict[str, float]:
    values = [_number(row.get(column)) for row in rows]
    clean = [value for value in values if value is not None]
    if not clean:
        return {}
    return {
        "min": min(clean),
        "p10": _percentile(clean, 0.10),
        "median": median(clean),
        "p90": _percentile(clean, 0.90),
        "max": max(clean),
        "p10_p90_width": _percentile(clean, 0.90) - _percentile(clean, 0.10),
    }


def _stats_values(values: list[float]) -> dict[str, float]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {}
    return {
        "min": min(clean),
        "p10": _percentile(clean, 0.10),
        "median": median(clean),
        "p90": _percentile(clean, 0.90),
        "max": max(clean),
        "p10_p90_width": _percentile(clean, 0.90) - _percentile(clean, 0.10),
    }


def build_cost_diagnostics(samples_csv: str | Path) -> dict[str, Any]:
    path = Path(samples_csv)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))
    successful = [
        row for row in all_rows
        if str(row.get("status") or "ok").lower() in {"", "ok", "success"}
    ]
    baseline = next(
        (row for row in successful if str(row.get("is_baseline") or "").lower() in {"1", "true", "yes"}),
        None,
    )
    stochastic = [row for row in successful if row is not baseline]
    if not stochastic:
        raise ValueError("No successful stochastic Monte Carlo sample is available for cost diagnostics.")

    total_key = (
        "kpi::total_supply_cost_accounting"
        if any(_number(row.get("kpi::total_supply_cost_accounting")) is not None for row in successful)
        else "kpi::total_cost"
    )
    exposure_key = (
        "kpi::total_economic_exposure"
        if any(_number(row.get("kpi::total_economic_exposure")) is not None for row in successful)
        else ""
    )
    components: dict[str, Any] = {}
    for label, column in {**INCLUDED_COST_COMPONENTS, **SEPARATE_RISK_COSTS}.items():
        component_stats = _stats(stochastic, column)
        if component_stats:
            component_stats["column"] = column
            component_stats["baseline"] = _number((baseline or {}).get(column))
            components[label] = component_stats

    identity_residuals: list[float] = []
    production_ratios: list[float] = []
    external_inclusion_residuals: list[float] = []
    non_production_costs: list[float] = []
    total_with_exceptional_supply: list[float] = []
    for row in stochastic:
        total = _number(row.get(total_key))
        included = [_number(row.get(column)) for column in INCLUDED_COST_COMPONENTS.values()]
        if total is None or any(value is None for value in included):
            continue
        included_total = sum(value for value in included if value is not None)
        identity_residuals.append(total - included_total)
        production = _number(row.get(INCLUDED_COST_COMPONENTS["production"])) or 0.0
        non_production = included_total - production
        non_production_costs.append(non_production)
        if non_production > 1e-12:
            production_ratios.append(production / (production + non_production))
        exceptional = _number(row.get(SEPARATE_RISK_COSTS["exceptional_supply"])) or 0.0
        reported_exposure = _number(row.get(exposure_key)) if exposure_key else None
        total_with_exceptional_supply.append(
            reported_exposure if reported_exposure is not None else total + exceptional
        )
        external_inclusion_residuals.append(total - included_total - exceptional)

    factor_columns = sorted(
        column for column in {key for row in stochastic for key in row}
        if column.startswith((
            "factor::",
            "demand_item::",
            "capacity_node::",
            "supplier_stock_node::",
            "supplier_capacity_node::",
            "supplier_lead_node::",
            "supplier_reliability_node::",
        )) and column not in EXCLUDED_FACTORS
    )
    correlations: list[dict[str, Any]] = []
    for factor in factor_columns:
        pairs = [
            (_number(row.get(factor)), _number(row.get(total_key)))
            for row in stochastic
        ]
        clean_pairs = [(left, right) for left, right in pairs if left is not None and right is not None]
        if len(clean_pairs) < 3:
            continue
        left = [pair[0] for pair in clean_pairs]
        right = [pair[1] for pair in clean_pairs]
        if max(left) - min(left) <= 1e-12:
            continue
        correlation = _pearson(left, right)
        correlations.append({"factor": factor, "correlation": correlation, "abs_correlation": abs(correlation)})
    correlations.sort(key=lambda row: row["abs_correlation"], reverse=True)

    total_stats = _stats(stochastic, total_key)
    total_stats["baseline"] = _number((baseline or {}).get(total_key))
    non_production_stats = _stats_values(non_production_costs)
    exposure_stats = _stats_values(total_with_exceptional_supply)
    if baseline:
        baseline_total = _number(baseline.get(total_key))
        baseline_production = _number(baseline.get(INCLUDED_COST_COMPONENTS["production"]))
        baseline_exceptional = _number(baseline.get(SEPARATE_RISK_COSTS["exceptional_supply"]))
        if baseline_total is not None and baseline_production is not None:
            non_production_stats["baseline"] = baseline_total - baseline_production
        baseline_exposure = _number(baseline.get(exposure_key)) if exposure_key else None
        if baseline_exposure is not None:
            exposure_stats["baseline"] = baseline_exposure
        elif baseline_total is not None and baseline_exceptional is not None:
            exposure_stats["baseline"] = baseline_total + baseline_exceptional
    identity_tolerance = max(1.0, abs(total_stats.get("median", 0.0)) * 1e-8)
    identity_max_error = max((abs(value) for value in identity_residuals), default=0.0)
    production_share = median(production_ratios) if production_ratios else None
    production_amplification = (
        1.0 / max(1e-12, 1.0 - production_share)
        if production_share is not None and production_share < 1.0
        else None
    )
    exceptional_separate = (
        identity_max_error <= identity_tolerance
        and max((abs(value) for value in external_inclusion_residuals), default=0.0) > identity_tolerance
    )
    return {
        "schema_version": "etudecas.montecarlo.cost-diagnostics.v2",
        "source": str(path),
        "sample_count": len(stochastic),
        "total_cost": total_stats,
        "cost_without_production": non_production_stats,
        "economic_exposure_including_exceptional_supply": exposure_stats,
        "components": components,
        "accounting_identity": {
            "included_components": list(INCLUDED_COST_COMPONENTS),
            "max_absolute_residual": identity_max_error,
            "valid_within_tolerance": identity_max_error <= identity_tolerance,
            "tolerance": identity_tolerance,
        },
        "production_cost_coupling": {
            "median_share_of_total": production_share,
            "mechanical_amplification_factor": production_amplification,
            "fixed_share_detected": production_share is not None
            and max((abs(value - production_share) for value in production_ratios), default=0.0) <= 1e-6,
            "reading": (
                "A fixed production share mechanically amplifies every other included cost. "
                "With fixed conversion unit rates, this test should be false and production cost "
                "changes only with produced quantities."
            ),
        },
        "exceptional_supply_cost": {
            "included_in_total_cost": not exceptional_separate,
            "tracked_separately": exceptional_separate,
            "combined_exposure_field": "economic_exposure_including_exceptional_supply",
        },
        "top_input_correlations_with_total_cost": correlations[:15],
        "reading": (
            "The accounting identity is deterministic. Input correlations are descriptive only; "
            "the controlled paired experiments and variance decomposition must be used for attribution."
        ),
    }


__all__ = ["build_cost_diagnostics"]
