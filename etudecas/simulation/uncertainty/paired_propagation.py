"""Controlled paired experiments for input-to-KPI uncertainty propagation.

The ordinary Monte Carlo campaign varies many inputs at once.  This module
builds a small complementary design where one selected input is set to a low,
central and high value while every other sampled input and the random seed are
kept identical.  The resulting trajectories isolate the marginal effect much
more faithfully than a regression fitted on the mixed Monte Carlo cloud.
"""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any


SCHEMA_VERSION = "etudecas.paired_uncertainty_propagation.v1"
FACTOR_PREFIX_TO_SPEC = (
    ("factor::", "factors"),
    ("demand_item::", "demand_item_scale"),
    ("capacity_node::", "capacity_node_scale"),
    ("supplier_stock_node::", "supplier_node_scale"),
    ("supplier_capacity_node::", "supplier_capacity_node_scale"),
    ("supplier_lead_node::", "edge_src_lead_time_scale"),
    ("supplier_reliability_node::", "edge_src_reliability_scale"),
    ("supplier_stock_pair::", "supplier_stock_pair_scale"),
    ("supplier_capacity_pair::", "supplier_capacity_pair_scale"),
    ("supplier_lead_pair::", "edge_pair_lead_time_scale"),
    ("supplier_reliability_pair::", "edge_pair_reliability_scale"),
)
SUPPLIER_FACTOR_PREFIXES = (
    "supplier_stock_node::",
    "supplier_capacity_node::",
    "supplier_lead_node::",
    "supplier_reliability_node::",
    "supplier_stock_pair::",
    "supplier_capacity_pair::",
    "supplier_lead_pair::",
    "supplier_reliability_pair::",
    "factor::supplier_stock_scale",
    "factor::supplier_capacity_scale",
    "factor::lead_time_scale",
    "factor::external_procurement_daily_cap_days_scale",
    "factor::external_procurement_lead_days_scale",
)
ECONOMIC_FACTOR_KEYS = {
    "external_procurement_cost_multiplier_scale",
    "external_procurement_transport_cost_scale",
    "holding_cost_scale",
    "purchase_cost_floor_scale",
    "transport_cost_scale",
}
NON_ACTIONABLE_DEFAULT_FACTORS = {
    # A simultaneous reliability shock on every supplier is a systemic stress
    # scenario, not a supplier-level prediction input.
    "factor::supplier_reliability_scale",
}
PRIMARY_KPI_WEIGHTS = {
    "kpi::fill_rate": 1.40,
    "kpi::ending_backlog": 1.25,
    "kpi::total_produced": 1.10,
    "kpi::total_supplier_capacity_binding_qty": 1.00,
    "kpi::total_cost": 0.80,
}
ECONOMIC_KPI_WEIGHTS = {
    "kpi::total_cost": 1.50,
    "kpi::total_inventory_cost": 0.90,
    "kpi::total_external_procurement_cost": 0.90,
    "kpi::total_supplier_transport_cost": 0.80,
}


def default_business_factor_ranges(factors: list[str]) -> dict[str, dict[str, float]]:
    """Return conservative operational ranges for controlled experiments.

    These ranges are working business hypotheses, not fitted probability
    distributions. They deliberately stay narrower than severe stress tests.
    """

    ranges: dict[str, dict[str, float]] = {}
    for factor in factors:
        values: tuple[float, float, float] | None = None
        if factor.startswith((
            "supplier_capacity_node::",
            "supplier_capacity_pair::",
            "factor::supplier_capacity_scale",
        )):
            values = (0.80, 1.00, 1.10)
        elif factor.startswith((
            "supplier_stock_node::",
            "supplier_stock_pair::",
            "factor::supplier_stock_scale",
        )):
            values = (0.75, 1.00, 1.10)
        elif factor.startswith((
            "supplier_lead_node::",
            "supplier_lead_pair::",
            "factor::lead_time_scale",
        )):
            values = (0.80, 1.00, 1.20)
        elif factor.startswith((
            "supplier_reliability_node::",
            "supplier_reliability_pair::",
        )):
            values = (0.90, 1.00, 1.05)
        elif factor == "factor::external_procurement_lead_days_scale":
            values = (0.80, 1.00, 1.20)
        elif factor == "factor::external_procurement_daily_cap_days_scale":
            values = (0.80, 1.00, 1.10)
        elif factor == "factor::holding_cost_scale":
            values = (0.80, 1.00, 1.20)
        elif factor == "factor::transport_cost_scale":
            values = (0.85, 1.00, 1.25)
        elif factor in {
            "factor::external_procurement_cost_multiplier_scale",
            "factor::external_procurement_transport_cost_scale",
        }:
            values = (0.75, 1.00, 1.25)
        elif factor == "factor::purchase_cost_floor_scale":
            values = (0.90, 1.00, 1.10)
        elif factor.startswith("demand_item::") or factor == "factor::demand_scale":
            values = (0.90, 1.00, 1.10)
        elif factor.startswith("capacity_node::") or factor == "factor::capacity_scale":
            values = (0.80, 1.00, 1.10)
        if values is not None:
            ranges[factor] = {"low": values[0], "center": values[1], "high": values[2]}
    return ranges


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def factor_family(factor: str) -> str:
    if is_economic_factor(factor):
        key = factor.removeprefix("factor::")
        if "holding" in key:
            return "holding_cost"
        if "transport" in key:
            return "transport_cost"
        if "purchase" in key:
            return "purchase_cost"
        return "external_procurement_cost"
    if factor.startswith((
        "supplier_lead_node::",
        "supplier_lead_pair::",
        "factor::lead_time_scale",
        "factor::external_procurement_lead",
    )):
        return "lead"
    if factor.startswith((
        "supplier_capacity_node::",
        "supplier_capacity_pair::",
        "factor::supplier_capacity",
        "factor::external_procurement_daily_cap",
    )):
        return "capacity"
    if factor.startswith((
        "supplier_stock_node::",
        "supplier_stock_pair::",
        "factor::supplier_stock",
    )):
        return "stock"
    if factor.startswith((
        "supplier_reliability_node::",
        "supplier_reliability_pair::",
        "factor::supplier_reliability",
    )):
        return "reliability"
    if factor.startswith("demand_item::"):
        return "demand"
    if factor.startswith("capacity_node::"):
        return "factory_capacity"
    return "global"


def factor_node_id(factor: str) -> str:
    pair_scope = factor_pair_scope(factor)
    if pair_scope:
        return pair_scope["supplier_id"]
    for prefix in (
        "supplier_stock_node::",
        "supplier_capacity_node::",
        "supplier_lead_node::",
        "supplier_reliability_node::",
        "capacity_node::",
    ):
        if factor.startswith(prefix):
            return factor.removeprefix(prefix)
    return ""


def factor_pair_scope(factor: str) -> dict[str, str]:
    for prefix in (
        "supplier_stock_pair::",
        "supplier_capacity_pair::",
        "supplier_lead_pair::",
        "supplier_reliability_pair::",
    ):
        if factor.startswith(prefix):
            parts = factor.removeprefix(prefix).split("|", 2)
            if len(parts) == 3:
                return {
                    "supplier_id": parts[0],
                    "destination_id": parts[1],
                    "item_id": parts[2],
                }
    return {}


def is_supplier_factor(factor: str) -> bool:
    return factor.startswith(SUPPLIER_FACTOR_PREFIXES)


def is_economic_factor(factor: str) -> bool:
    if not factor.startswith("factor::"):
        return False
    key = factor.removeprefix("factor::")
    return key in ECONOMIC_FACTOR_KEYS or (
        key.endswith(("_cost_scale", "_cost_multiplier_scale", "_price_scale"))
        and key != "supplier_reliability_scale"
    )


def _factor_columns(rows: list[dict[str, Any]]) -> set[str]:
    return {
        key
        for row in rows
        for key in row
        if any(key.startswith(prefix) for prefix, _target in FACTOR_PREFIX_TO_SPEC)
    }


def select_paired_factors(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    limit: int = 4,
) -> list[str]:
    """Select a balanced set of operational supplier and economic inputs."""

    factor_columns = _factor_columns(rows)
    stochastic = [
        row
        for row in rows
        if str(row.get("status") or "ok").lower() in {"", "ok", "success"}
        and str(row.get("is_baseline") or "").lower() not in {"1", "true", "yes"}
    ]
    correlations = summary.get("factor_kpi_correlations_pearson")
    correlations = correlations if isinstance(correlations, dict) else {}
    scored: list[tuple[float, int, str, str]] = []
    for factor in factor_columns:
        if factor in NON_ACTIONABLE_DEFAULT_FACTORS:
            continue
        factor_group = "economic" if is_economic_factor(factor) else "operational"
        if factor_group == "operational" and not is_supplier_factor(factor):
            continue
        values = [_to_float(row.get(factor), float("nan")) for row in stochastic]
        values = [value for value in values if math.isfinite(value)]
        if len(values) < 3 or max(values) - min(values) <= 1e-9:
            continue
        target_corrs = correlations.get(factor) if isinstance(correlations.get(factor), dict) else {}
        weights = ECONOMIC_KPI_WEIGHTS if factor_group == "economic" else PRIMARY_KPI_WEIGHTS
        score = max(
            (
                abs(_to_float(target_corrs.get(kpi), 0.0)) * weight
                for kpi, weight in weights.items()
            ),
            default=0.0,
        )
        node_preference = 1 if factor_node_id(factor) else 0
        scored.append((score, node_preference, factor, factor_group))
    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    selected: list[str] = []
    target = max(0, int(limit))

    # When both kinds are available, reserve one slot for each. This avoids a
    # cost-only ranking hiding physical supplier levers, or the reverse.
    if target >= 2:
        for required_group in ("operational", "economic"):
            candidate = next((item for item in scored if item[3] == required_group), None)
            if candidate is not None and candidate[2] not in selected:
                selected.append(candidate[2])

    used_families: set[str] = set()
    used_families.update(factor_family(factor) for factor in selected)
    for _score, _node_preference, factor, _group in scored:
        if factor in selected:
            continue
        family = factor_family(factor)
        if family in used_families:
            continue
        selected.append(factor)
        used_families.add(family)
        if len(selected) >= target:
            return selected[:target]
    for _score, _node_preference, factor, _group in scored:
        if factor not in selected:
            selected.append(factor)
        if len(selected) >= target:
            break
    return selected[:target]


def select_supplier_item_factors(
    base_data: dict[str, Any],
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    limit: int = 6,
) -> list[str]:
    """Select distinct supplier-item-destination levers for paired tests."""

    correlations = summary.get("factor_kpi_correlations_pearson")
    correlations = correlations if isinstance(correlations, dict) else {}
    factor_columns = _factor_columns(rows)
    family_prefixes = {
        "stock": ("supplier_stock_node::", "supplier_stock_pair::"),
        "capacity": ("supplier_capacity_node::", "supplier_capacity_pair::"),
        "lead": ("supplier_lead_node::", "supplier_lead_pair::"),
        "reliability": (
            "supplier_reliability_node::",
            "supplier_reliability_pair::",
        ),
    }
    family_prior = {
        "lead": 0.04,
        "capacity": 0.03,
        "stock": 0.02,
        "reliability": 0.01,
    }
    scored: list[tuple[float, str]] = []
    seen_scopes: set[tuple[str, str, str]] = set()
    for edge in base_data.get("edges") or []:
        if str(edge.get("type") or "").lower() != "transport":
            continue
        supplier_id = str(edge.get("from") or "")
        destination_id = str(edge.get("to") or "")
        if not supplier_id.startswith("SDC-") or not destination_id.startswith(("M-", "SDC-")):
            continue
        for item_id in [str(value) for value in (edge.get("items") or []) if str(value)]:
            scope = (supplier_id, destination_id, item_id)
            if scope in seen_scopes:
                continue
            seen_scopes.add(scope)
            best: tuple[float, str] | None = None
            for family, (node_prefix, pair_prefix) in family_prefixes.items():
                node_factor = f"{node_prefix}{supplier_id}"
                if node_factor not in factor_columns:
                    continue
                target_corrs = (
                    correlations.get(node_factor)
                    if isinstance(correlations.get(node_factor), dict)
                    else {}
                )
                score = max(
                    (
                        abs(_to_float(target_corrs.get(kpi), 0.0)) * weight
                        for kpi, weight in PRIMARY_KPI_WEIGHTS.items()
                    ),
                    default=0.0,
                ) + family_prior[family]
                pair_factor = (
                    f"{pair_prefix}{supplier_id}|{destination_id}|{item_id}"
                )
                candidate = (score, pair_factor)
                if best is None or candidate > best:
                    best = candidate
            if best is not None:
                scored.append(best)
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [factor for _score, factor in scored[: max(0, int(limit))]]


def select_background_rows(rows: list[dict[str, Any]], *, count: int = 5) -> list[dict[str, Any]]:
    """Pick deterministic, family-diverse Monte Carlo backgrounds."""

    candidates = [
        row
        for row in rows
        if str(row.get("status") or "ok").lower() in {"", "ok", "success"}
        and str(row.get("is_baseline") or "").lower() not in {"1", "true", "yes"}
    ]
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_family[str(row.get("scenario_family") or "global")].append(row)
    for family_rows in by_family.values():
        family_rows.sort(key=lambda row: str(row.get("run_id") or ""))

    selected: list[dict[str, Any]] = []
    families = sorted(by_family)
    round_index = 0
    target = max(0, int(count))
    while len(selected) < target and families:
        next_families: list[str] = []
        for family in families:
            family_rows = by_family[family]
            if round_index < len(family_rows):
                selected.append(family_rows[round_index])
                if len(selected) >= target:
                    break
            if round_index + 1 < len(family_rows):
                next_families.append(family)
        if len(selected) >= target:
            break
        families = next_families
        round_index += 1
    return selected


def _sample_row_to_spec(row: dict[str, Any]) -> dict[str, Any]:
    spec_parts: dict[str, dict[str, float]] = {
        target: {} for _prefix, target in FACTOR_PREFIX_TO_SPEC
    }
    for key, raw_value in row.items():
        for prefix, target in FACTOR_PREFIX_TO_SPEC:
            if key.startswith(prefix):
                spec_parts[target][key.removeprefix(prefix)] = _to_float(raw_value, 1.0)
                break
    return spec_parts


def _set_spec_factor(spec: dict[str, Any], factor: str, value: float) -> None:
    for prefix, target in FACTOR_PREFIX_TO_SPEC:
        if factor.startswith(prefix):
            spec[target][factor.removeprefix(prefix)] = float(value)
            return
    raise ValueError(f"Unsupported paired factor: {factor}")


def _configured_factor_range(raw_range: Any) -> tuple[float, float, float] | None:
    if isinstance(raw_range, dict):
        values = (raw_range.get("low"), raw_range.get("center"), raw_range.get("high"))
    elif isinstance(raw_range, (list, tuple)) and len(raw_range) == 3:
        values = tuple(raw_range)
    else:
        return None
    parsed = tuple(_to_float(value, float("nan")) for value in values)
    if not all(math.isfinite(value) for value in parsed):
        raise ValueError("A paired factor range must contain finite low/center/high values.")
    low, center, high = parsed
    if low < 0.0 or not low <= center <= high or high - low <= 1e-12:
        raise ValueError("A paired factor range must satisfy 0 <= low <= center <= high and low < high.")
    return low, center, high


def resolve_factor_range(
    factor: str,
    rows: list[dict[str, Any]],
    *,
    uncertainty: float = 0.20,
    factor_ranges: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve low/center/high from business config, observations or fallback.

    ``factor_ranges`` accepts either ``(low, center, high)`` or a mapping with
    these three keys. Observed ranges use robust p05/p50/p95 quantiles so one
    extreme Monte Carlo draw cannot define the controlled experiment alone.
    """

    configured = _configured_factor_range((factor_ranges or {}).get(factor))
    if configured is not None:
        low, center, high = configured
        source = "business_config"
    else:
        observed = [
            _to_float(row.get(factor), float("nan"))
            for row in rows
            if str(row.get("status") or "ok").lower() in {"", "ok", "success"}
        ]
        observed = [value for value in observed if math.isfinite(value) and value >= 0.0]
        if len(observed) >= 3 and max(observed) - min(observed) > 1e-12:
            low = _percentile(observed, 0.05)
            center = _percentile(observed, 0.50)
            high = _percentile(observed, 0.95)
            source = "observed_p05_p50_p95"
        else:
            uncertainty = max(0.0, float(uncertainty))
            baseline_row = next(
                (
                    row for row in rows
                    if str(row.get("is_baseline") or "").lower() in {"1", "true", "yes"}
                ),
                None,
            )
            center = _to_float((baseline_row or {}).get(factor), 1.0)
            if abs(center) <= 1e-12:
                center = 1.0
            low = max(0.0, center * (1.0 - uncertainty))
            high = center * (1.0 + uncertainty)
            source = "uniform_relative_fallback"
    return {
        "low": float(low),
        "center": float(center),
        "high": float(high),
        "source": source,
    }


def build_paired_run_specs(
    *,
    factors: list[str],
    backgrounds: list[dict[str, Any]],
    uncertainty: float = 0.20,
    factor_ranges: dict[str, Any] | None = None,
    range_rows: list[dict[str, Any]] | None = None,
    reuse_background_centers: bool = False,
) -> list[dict[str, Any]]:
    """Create factor-specific low/centre/high paired simulations.

    ``uncertainty`` remains the backward-compatible fallback when neither a
    configured nor an observed range can be resolved.
    """

    uncertainty = max(0.0, float(uncertainty))
    range_source_rows = range_rows if range_rows is not None else backgrounds
    resolved_ranges = {
        factor: resolve_factor_range(
            factor,
            range_source_rows,
            uncertainty=uncertainty,
            factor_ranges=factor_ranges,
        )
        for factor in factors
    }
    specs: list[dict[str, Any]] = []
    index = 0
    centered_backgrounds: list[tuple[dict[str, Any], dict[str, dict[str, Any]]]] = []
    for background_index, background in enumerate(backgrounds):
        base_parts = _sample_row_to_spec(background)
        if reuse_background_centers:
            for factor, factor_range in resolved_ranges.items():
                _set_spec_factor(base_parts, factor, factor_range["center"])
        centered_backgrounds.append((background, base_parts))

        if reuse_background_centers:
            background_id = str(background.get("run_id") or f"background_{background_index + 1}")
            run_id = f"paired_b{background_index + 1:02d}_center"
            output_row = {
                "run_id": run_id,
                "is_baseline": False,
                "scenario_family": "paired_propagation",
                "scenario_family_label": "Propagation controlee",
                "status": "ok",
                "error": "",
                "paired_factor": "__shared_center__",
                "paired_background_id": background_id,
                "paired_variant": "center",
            }
            for prefix, target in FACTOR_PREFIX_TO_SPEC:
                output_row.update({f"{prefix}{key}": val for key, val in base_parts[target].items()})
            specs.append(
                {
                    "index": index,
                    "run_id": run_id,
                    "is_baseline": False,
                    "scenario_family": "paired_propagation",
                    "row": output_row,
                    "paired_metadata": {
                        "factor": "__shared_center__",
                        "factor_family": "shared_center",
                        "factor_node_id": "",
                        "background_id": background_id,
                        "background_family": str(background.get("scenario_family") or "global"),
                        "variant": "center",
                        "shared_center": True,
                    },
                    **{name: dict(values) for name, values in base_parts.items()},
                }
            )
            index += 1

    for factor_index, factor in enumerate(factors):
        factor_range = resolved_ranges[factor]
        variants = [("low", factor_range["low"]), ("high", factor_range["high"])]
        if not reuse_background_centers:
            variants.insert(1, ("center", factor_range["center"]))
        for background_index, (background, centered_parts) in enumerate(centered_backgrounds):
            for variant, value in variants:
                parts = {name: dict(values) for name, values in centered_parts.items()}
                _set_spec_factor(parts, factor, value)
                run_id = f"paired_f{factor_index + 1:02d}_b{background_index + 1:02d}_{variant}"
                paired_meta = {
                    "factor": factor,
                    "factor_family": factor_family(factor),
                    "factor_node_id": factor_node_id(factor),
                    "factor_scope": factor_pair_scope(factor),
                    "background_id": str(background.get("run_id") or f"background_{background_index + 1}"),
                    "background_family": str(background.get("scenario_family") or "global"),
                    "variant": variant,
                    "input_value": value,
                    "input_reference": factor_range["center"],
                    "input_low": factor_range["low"],
                    "input_high": factor_range["high"],
                    "input_range_source": factor_range["source"],
                    "input_relative_uncertainty": max(
                        abs(factor_range["low"] - factor_range["center"]),
                        abs(factor_range["high"] - factor_range["center"]),
                    ) / max(abs(factor_range["center"]), 1e-12),
                }
                output_row = {
                    "run_id": run_id,
                    "is_baseline": False,
                    "scenario_family": "paired_propagation",
                    "scenario_family_label": "Propagation controlee",
                    "status": "ok",
                    "error": "",
                    "paired_factor": factor,
                    "paired_background_id": paired_meta["background_id"],
                    "paired_variant": variant,
                    "paired_input_value": value,
                    "paired_input_range_source": factor_range["source"],
                }
                for prefix, target in FACTOR_PREFIX_TO_SPEC:
                    output_row.update({f"{prefix}{key}": val for key, val in parts[target].items()})
                specs.append(
                    {
                        "index": index,
                        "run_id": run_id,
                        "is_baseline": False,
                        "scenario_family": "paired_propagation",
                        "row": output_row,
                        "paired_metadata": paired_meta,
                        **parts,
                    }
                )
                index += 1
    return specs


def _trajectory_values(run: dict[str, Any], metric: str, days: list[int]) -> list[float] | None:
    points = {
        int(day): _to_float(value)
        for day, value in ((run.get("series") or {}).get(metric) or [])
    }
    if not points:
        return None
    values: list[float] = []
    previous = 0.0
    for day in days:
        previous = points.get(day, previous)
        values.append(previous)
    return values


def build_paired_propagation_payload(
    *,
    factors: list[str],
    backgrounds: list[dict[str, Any]],
    trajectory_runs: list[dict[str, Any]],
    scenario_id: str,
    uncertainty: float,
) -> dict[str, Any]:
    """Aggregate paired deltas into one readable envelope per input and KPI."""

    usable = [run for run in trajectory_runs if isinstance(run.get("series"), dict) and run.get("series")]
    days = sorted(
        {
            int(day)
            for run in usable
            for points in (run.get("series") or {}).values()
            for day, _value in points
        }
    )
    metric_names = sorted(
        {
            metric
            for run in usable
            for metric in (run.get("series") or {})
        }
    )
    by_triplet: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    shared_centers: dict[str, dict[str, Any]] = {}
    input_ranges: dict[str, dict[str, Any]] = {}
    for run in usable:
        meta = run.get("paired_metadata") if isinstance(run.get("paired_metadata"), dict) else {}
        factor = str(meta.get("factor") or "")
        background_id = str(meta.get("background_id") or "")
        variant = str(meta.get("variant") or "")
        if meta.get("shared_center") and background_id and variant == "center":
            shared_centers[background_id] = run
        elif factor and background_id and variant:
            by_triplet[(factor, background_id)][variant] = run
            if factor not in input_ranges:
                input_ranges[factor] = {
                    "low": _to_float(meta.get("input_low"), max(0.0, 1.0 - float(uncertainty))),
                    "center": _to_float(meta.get("input_reference"), 1.0),
                    "high": _to_float(meta.get("input_high"), 1.0 + float(uncertainty)),
                    "source": str(meta.get("input_range_source") or "uniform_relative_fallback"),
                }

    metrics: dict[str, Any] = {}
    for metric in metric_names:
        factor_payloads: list[dict[str, Any]] = []
        for factor in factors:
            complete: list[tuple[list[float], list[float], list[float]]] = []
            for background in backgrounds:
                background_id = str(background.get("run_id") or "")
                variants = by_triplet.get((factor, background_id), {})
                low = _trajectory_values(variants.get("low", {}), metric, days)
                center_run = variants.get("center") or shared_centers.get(background_id, {})
                center = _trajectory_values(center_run, metric, days)
                high = _trajectory_values(variants.get("high", {}), metric, days)
                if low is not None and center is not None and high is not None:
                    complete.append((low, center, high))
            if not complete:
                continue
            center_curve: list[float] = []
            lower_curve: list[float] = []
            upper_curve: list[float] = []
            for position in range(len(days)):
                centers = [triplet[1][position] for triplet in complete]
                lower_effects = [
                    min(triplet[0][position] - triplet[1][position], triplet[2][position] - triplet[1][position], 0.0)
                    for triplet in complete
                ]
                upper_effects = [
                    max(triplet[0][position] - triplet[1][position], triplet[2][position] - triplet[1][position], 0.0)
                    for triplet in complete
                ]
                center_value = float(median(centers))
                center_curve.append(center_value)
                lower_curve.append(center_value + _percentile(lower_effects, 0.10))
                upper_curve.append(center_value + _percentile(upper_effects, 0.90))
            max_width = max((high - low for low, high in zip(lower_curve, upper_curve)), default=0.0)
            input_range = input_ranges.get(
                factor,
                {
                    "low": max(0.0, 1.0 - float(uncertainty)),
                    "center": 1.0,
                    "high": 1.0 + float(uncertainty),
                    "source": "uniform_relative_fallback",
                },
            )
            factor_payloads.append(
                {
                    "factor": factor,
                    "family": factor_family(factor),
                    "node_id": factor_node_id(factor),
                    "scope": factor_pair_scope(factor),
                    "background_count": len(complete),
                    "input_reference": input_range["center"],
                    "input_low": input_range["low"],
                    "input_high": input_range["high"],
                    "input_range_source": input_range["source"],
                    "center": center_curve,
                    "low": lower_curve,
                    "high": upper_curve,
                    "max_width": max_width,
                    "aggregation": "paired_effect_p10_p90",
                }
            )
        if factor_payloads:
            metrics[metric] = {"factors": factor_payloads}

    return {
        "schema_version": SCHEMA_VERSION,
        "method": "paired_controlled_runs",
        "scenario_id": scenario_id,
        "input_relative_uncertainty": float(uncertainty),
        "input_range_mode": "factor_specific_with_relative_fallback",
        "factor_count": len(factors),
        "background_count": len(backgrounds),
        "run_count": len(usable),
        "days": days,
        "factors": factors,
        "background_run_ids": [str(row.get("run_id") or "") for row in backgrounds],
        "metrics": metrics,
        "reading": (
            "Chaque enveloppe provient de runs apparies: un seul input prend une valeur basse, centrale et haute "
            "issue de la configuration metier ou des quantiles observes; "
            "tous les autres inputs restent identiques dans un meme triplet. La bande agrege les effets apparies "
            "P10-P90 sur plusieurs contextes Monte Carlo. Le pourcentage uniforme est uniquement un repli."
        ),
    }
