"""Cross-validated variance decomposition for Etudecas Monte Carlo samples.

This module estimates predictive contributions, not Sobol indices.  The Monte
Carlo campaign is not a Saltelli design, so variance shares are obtained from
out-of-sample predictions and grouped permutation importance.  The residual
therefore includes interactions, nonlinear effects not represented by the
additive model, measurement noise, and any other unexplained variation.
"""

from __future__ import annotations

import csv
import math
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


FACTOR_PREFIXES = (
    "factor::",
    "demand_item::",
    "capacity_node::",
    "supplier_stock_node::",
    "supplier_capacity_node::",
    "supplier_lead_node::",
    "supplier_reliability_node::",
)

EXCLUDED_FACTORS = frozenset({"factor::supplier_reliability_scale"})

DEFAULT_KPIS = (
    "kpi::fill_rate",
    "kpi::ending_backlog",
    "kpi::total_cost",
    "kpi::total_produced",
    "kpi::total_supplier_capacity_binding_qty",
    "kpi::avg_inventory",
)

FAMILY_LABELS = {
    "demand": "Demand",
    "production_capacity": "Production capacity",
    "production_stock": "Production stock",
    "supplier_stock": "Supplier stock",
    "supplier_capacity": "Supplier capacity",
    "supplier_lead_time": "Supplier lead time",
    "supplier_reliability": "Supplier reliability by supplier",
    "external_supply_capacity": "External supply capacity",
    "external_supply_lead_time": "External supply lead time",
    "external_supply_cost": "External supply cost",
    "purchase_cost": "Purchase cost",
    "transport_cost": "Transport cost",
    "holding_cost": "Holding cost",
    "other_global_factors": "Other global factors",
}


def factor_family(factor: str) -> str | None:
    """Return the business family for a factor column.

    The global supplier reliability multiplier is intentionally excluded.  It
    represents a systemic stress, while supplier-specific reliability remains
    an operational uncertainty.
    """

    if factor in EXCLUDED_FACTORS:
        return None
    if factor.startswith("demand_item::") or factor == "factor::demand_scale":
        return "demand"
    if factor.startswith("capacity_node::") or factor == "factor::capacity_scale":
        return "production_capacity"
    if factor == "factor::production_stock_scale":
        return "production_stock"
    if factor.startswith("supplier_stock_node::") or factor == "factor::supplier_stock_scale":
        return "supplier_stock"
    if factor.startswith("supplier_capacity_node::") or factor == "factor::supplier_capacity_scale":
        return "supplier_capacity"
    if factor.startswith("supplier_lead_node::") or factor == "factor::lead_time_scale":
        return "supplier_lead_time"
    if factor.startswith("supplier_reliability_node::"):
        return "supplier_reliability"
    if factor == "factor::external_procurement_daily_cap_days_scale":
        return "external_supply_capacity"
    if factor == "factor::external_procurement_lead_days_scale":
        return "external_supply_lead_time"
    if factor in {
        "factor::external_procurement_cost_multiplier_scale",
        "factor::external_procurement_transport_cost_scale",
    }:
        return "external_supply_cost"
    if factor == "factor::purchase_cost_floor_scale":
        return "purchase_cost"
    if factor == "factor::transport_cost_scale":
        return "transport_cost"
    if factor == "factor::holding_cost_scale":
        return "holding_cost"
    if factor.startswith("factor::"):
        return "other_global_factors"
    return None


def _as_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return result if math.isfinite(result) else float("nan")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _load_rows(samples_csv: str | Path) -> tuple[Path, list[dict[str, str]]]:
    path = Path(samples_csv)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No Monte Carlo sample found in {path}")
    return path, rows


def _eligible_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[list[Mapping[str, Any]], int, int]:
    eligible: list[Mapping[str, Any]] = []
    baseline_count = 0
    failed_count = 0
    for row in rows:
        status = str(row.get("status") or "ok").strip().lower()
        if status not in {"", "ok", "success"}:
            failed_count += 1
            continue
        if _as_bool(row.get("is_baseline")):
            baseline_count += 1
            continue
        eligible.append(row)
    return eligible, baseline_count, failed_count


def _varying_numeric_columns(
    rows: Sequence[Mapping[str, Any]],
    columns: Iterable[str],
) -> list[str]:
    selected: list[str] = []
    for column in columns:
        values = np.asarray([_as_float(row.get(column)) for row in rows], dtype=float)
        finite = values[np.isfinite(values)]
        if finite.size < 3:
            continue
        scale = max(1.0, float(np.max(np.abs(finite))))
        if float(np.max(finite) - np.min(finite)) <= 1e-12 * scale:
            continue
        selected.append(column)
    return selected


def _folds(count: int, n_splits: int, seed: int) -> list[np.ndarray]:
    split_count = min(max(2, int(n_splits)), count)
    indices = np.arange(count, dtype=int)
    np.random.default_rng(seed).shuffle(indices)
    return [part for part in np.array_split(indices, split_count) if part.size]


def _fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float) -> dict[str, np.ndarray | float]:
    medians = np.zeros(x.shape[1], dtype=float)
    for index in range(x.shape[1]):
        finite = x[np.isfinite(x[:, index]), index]
        medians[index] = float(np.median(finite)) if finite.size else 0.0
    filled = np.where(np.isfinite(x), x, medians)
    means = np.mean(filled, axis=0)
    scales = np.std(filled, axis=0)
    scales = np.where(scales > 1e-12, scales, 1.0)
    z = (filled - means) / scales
    y_mean = float(np.mean(y))
    centered_y = y - y_mean

    # The dual system is cheaper and more stable when factors outnumber runs.
    if z.shape[1] > z.shape[0]:
        system = z @ z.T + float(alpha) * np.eye(z.shape[0])
        beta = z.T @ np.linalg.solve(system, centered_y)
    else:
        system = z.T @ z + float(alpha) * np.eye(z.shape[1])
        beta = np.linalg.solve(system, z.T @ centered_y)
    return {
        "medians": medians,
        "means": means,
        "scales": scales,
        "beta": beta,
        "y_mean": y_mean,
    }


def _transform(x: np.ndarray, model: Mapping[str, Any]) -> np.ndarray:
    medians = np.asarray(model["medians"], dtype=float)
    filled = np.where(np.isfinite(x), x, medians)
    return (filled - np.asarray(model["means"], dtype=float)) / np.asarray(model["scales"], dtype=float)


def _predict_transformed(z: np.ndarray, model: Mapping[str, Any]) -> np.ndarray:
    return float(model["y_mean"]) + z @ np.asarray(model["beta"], dtype=float)


def _predict(x: np.ndarray, model: Mapping[str, Any]) -> np.ndarray:
    return _predict_transformed(_transform(x, model), model)


def _choose_alpha(
    x: np.ndarray,
    y: np.ndarray,
    candidates: Sequence[float],
    seed: int,
) -> float:
    if len(candidates) == 1 or y.size < 10:
        return float(candidates[0])
    folds = _folds(y.size, min(3, y.size // 3), seed)
    best_alpha = float(candidates[0])
    best_mse = float("inf")
    all_indices = np.arange(y.size, dtype=int)
    for alpha in candidates:
        squared_error = 0.0
        observations = 0
        for test_indices in folds:
            train_indices = np.setdiff1d(all_indices, test_indices, assume_unique=False)
            if train_indices.size < 2:
                continue
            model = _fit_ridge(x[train_indices], y[train_indices], float(alpha))
            error = y[test_indices] - _predict(x[test_indices], model)
            squared_error += float(error @ error)
            observations += int(test_indices.size)
        mse = squared_error / observations if observations else float("inf")
        if mse < best_mse:
            best_mse = mse
            best_alpha = float(alpha)
    return best_alpha


def _safe_r2(y: np.ndarray, predictions: np.ndarray) -> float:
    denominator = float(np.sum((y - np.mean(y)) ** 2))
    if denominator <= 1e-24:
        return 0.0
    return 1.0 - float(np.sum((y - predictions) ** 2)) / denominator


def _json_float(value: float) -> float:
    return float(value) if math.isfinite(float(value)) else 0.0


def _decompose_kpi(
    rows: Sequence[Mapping[str, Any]],
    kpi: str,
    factor_columns: Sequence[str],
    family_columns: Mapping[str, Sequence[str]],
    *,
    n_splits: int,
    permutation_repeats: int,
    random_seed: int,
    alpha_candidates: Sequence[float],
) -> dict[str, Any]:
    finite_rows = [row for row in rows if math.isfinite(_as_float(row.get(kpi)))]
    if len(finite_rows) < max(8, n_splits * 2):
        return {
            "status": "insufficient_data",
            "sample_count": len(finite_rows),
            "reason": "At least two observations per validation fold are required.",
        }

    y = np.asarray([_as_float(row.get(kpi)) for row in finite_rows], dtype=float)
    variance = float(np.var(y))
    if variance <= 1e-24:
        return {
            "status": "constant_kpi",
            "sample_count": len(finite_rows),
            "variance": 0.0,
            "explained_share": 0.0,
            "residual_interactions_unexplained_share": 1.0,
            "families": [],
        }

    active_factors = _varying_numeric_columns(finite_rows, factor_columns)
    if not active_factors:
        return {
            "status": "no_varying_factor",
            "sample_count": len(finite_rows),
            "variance": _json_float(variance),
            "explained_share": 0.0,
            "residual_interactions_unexplained_share": 1.0,
            "families": [],
        }

    column_index = {column: index for index, column in enumerate(active_factors)}
    active_families = {
        family: [column_index[column] for column in columns if column in column_index]
        for family, columns in family_columns.items()
    }
    active_families = {family: indices for family, indices in active_families.items() if indices}
    x = np.asarray(
        [[_as_float(row.get(column)) for column in active_factors] for row in finite_rows],
        dtype=float,
    )

    seed = int(random_seed) + zlib.crc32(kpi.encode("utf-8"))
    outer_folds = _folds(y.size, n_splits, seed)
    all_indices = np.arange(y.size, dtype=int)
    predictions = np.full(y.shape, np.nan, dtype=float)
    selected_alphas: list[float] = []
    fold_r2: list[float] = []
    signed_importance = {family: 0.0 for family in active_families}
    importance_weight = {family: 0 for family in active_families}

    for fold_number, test_indices in enumerate(outer_folds):
        train_indices = np.setdiff1d(all_indices, test_indices, assume_unique=False)
        alpha = _choose_alpha(
            x[train_indices],
            y[train_indices],
            alpha_candidates,
            seed + 1009 * (fold_number + 1),
        )
        selected_alphas.append(alpha)
        model = _fit_ridge(x[train_indices], y[train_indices], alpha)
        transformed_test = _transform(x[test_indices], model)
        baseline_predictions = _predict_transformed(transformed_test, model)
        predictions[test_indices] = baseline_predictions
        fold_r2.append(_safe_r2(y[test_indices], baseline_predictions))
        baseline_mse = float(np.mean((y[test_indices] - baseline_predictions) ** 2))

        for family_number, (family, feature_indices) in enumerate(active_families.items()):
            increases: list[float] = []
            family_seed = seed + 100_003 * (fold_number + 1) + 997 * (family_number + 1)
            rng = np.random.default_rng(family_seed)
            for _ in range(max(1, int(permutation_repeats))):
                permutation = rng.permutation(test_indices.size)
                permuted = transformed_test.copy()
                # A shared row permutation preserves dependencies inside the family.
                permuted[:, feature_indices] = transformed_test[permutation][:, feature_indices]
                permuted_predictions = _predict_transformed(permuted, model)
                permuted_mse = float(np.mean((y[test_indices] - permuted_predictions) ** 2))
                increases.append(permuted_mse - baseline_mse)
            signed_importance[family] += float(np.mean(increases)) * int(test_indices.size)
            importance_weight[family] += int(test_indices.size)

    oos_r2 = _safe_r2(y, predictions)
    explained_share = min(1.0, max(0.0, oos_r2))
    mean_importance = {
        family: signed_importance[family] / max(1, importance_weight[family])
        for family in active_families
    }
    positive_total = sum(max(0.0, value) for value in mean_importance.values())

    family_payload: list[dict[str, Any]] = []
    for family, feature_indices in active_families.items():
        positive_importance = max(0.0, mean_importance[family])
        relative_importance = positive_importance / positive_total if positive_total > 0.0 else 0.0
        contribution = explained_share * relative_importance
        factors = [active_factors[index] for index in feature_indices]
        family_payload.append(
            {
                "family": family,
                "label": FAMILY_LABELS.get(family, family.replace("_", " ").title()),
                "factor_count": len(factors),
                "factors": factors,
                "grouped_permutation_mse_increase": _json_float(mean_importance[family]),
                "importance_within_explained_share": _json_float(relative_importance),
                "explained_variance_share": _json_float(contribution),
                "explained_variance_percent": _json_float(100.0 * contribution),
            }
        )
    family_payload.sort(key=lambda row: row["explained_variance_share"], reverse=True)

    return {
        "status": "ok",
        "sample_count": int(y.size),
        "factor_count": len(active_factors),
        "family_count": len(active_families),
        "variance": _json_float(variance),
        "oos_r2": _json_float(oos_r2),
        "explained_share": _json_float(explained_share),
        "explained_percent": _json_float(100.0 * explained_share),
        "residual_interactions_unexplained_share": _json_float(1.0 - explained_share),
        "residual_interactions_unexplained_percent": _json_float(100.0 * (1.0 - explained_share)),
        "families": family_payload,
        "validation": {
            "fold_count": len(outer_folds),
            "fold_r2": [_json_float(value) for value in fold_r2],
            "selected_ridge_alpha": selected_alphas,
            "permutation_repeats_per_fold": max(1, int(permutation_repeats)),
        },
    }


def build_variance_decomposition(
    samples_csv: str | Path,
    *,
    kpis: Sequence[str] | None = None,
    n_splits: int = 5,
    permutation_repeats: int = 20,
    random_seed: int = 42,
    alpha_candidates: Sequence[float] = (0.1, 1.0, 10.0, 100.0),
) -> dict[str, Any]:
    """Build a JSON-serializable predictive variance decomposition.

    Shares are based on a cross-validated additive Ridge model.  Grouped
    permutation allocates the model's explained share across factor families;
    the remaining share is deliberately labelled interactions/nonlinearities/
    unexplained.  This is not a causal decomposition and not a Sobol analysis.
    """

    path, all_rows = _load_rows(samples_csv)
    rows, baseline_count, failed_count = _eligible_rows(all_rows)
    if not rows:
        raise ValueError("No successful stochastic Monte Carlo sample is available.")

    all_columns = sorted({column for row in rows for column in row})
    candidate_factors = [
        column
        for column in all_columns
        if column.startswith(FACTOR_PREFIXES) and column not in EXCLUDED_FACTORS
    ]
    factor_columns = _varying_numeric_columns(rows, candidate_factors)
    family_columns: dict[str, list[str]] = {}
    for column in factor_columns:
        family = factor_family(column)
        if family is not None:
            family_columns.setdefault(family, []).append(column)

    if kpis is None:
        selected_kpis = [column for column in DEFAULT_KPIS if column in all_columns]
        if not selected_kpis:
            selected_kpis = [column for column in all_columns if column.startswith("kpi::")]
    else:
        selected_kpis = list(dict.fromkeys(kpis))

    decomposition = {
        kpi: _decompose_kpi(
            rows,
            kpi,
            factor_columns,
            family_columns,
            n_splits=n_splits,
            permutation_repeats=permutation_repeats,
            random_seed=random_seed,
            alpha_candidates=alpha_candidates,
        )
        for kpi in selected_kpis
        if kpi in all_columns
    }

    return {
        "schema_version": "1.0",
        "method": {
            "name": "cross_validated_grouped_permutation_ridge",
            "is_sobol": False,
            "model_scope": "additive predictive approximation",
            "validation": "nested Ridge selection and out-of-sample K-fold predictions",
            "allocation": "grouped permutation on held-out folds",
            "residual_definition": (
                "Interactions, nonlinear effects not captured by the additive model, "
                "noise, and other unexplained variation."
            ),
            "limitations": [
                "The Monte Carlo campaign is not a Saltelli design; these are not Sobol indices.",
                "Permutation shares are predictive, not causal.",
                "Strong dependence between factor families can redistribute permutation importance.",
                "Negative out-of-sample R2 is reported but contributes zero explained share.",
            ],
        },
        "source": {
            "samples_csv": str(path),
            "row_count": len(all_rows),
            "stochastic_success_count": len(rows),
            "baseline_excluded_count": baseline_count,
            "failed_excluded_count": failed_count,
        },
        "excluded_factors": sorted(EXCLUDED_FACTORS),
        "factor_families": {
            family: {
                "label": FAMILY_LABELS.get(family, family.replace("_", " ").title()),
                "factor_count": len(columns),
                "factors": columns,
            }
            for family, columns in sorted(family_columns.items())
        },
        "kpis": decomposition,
    }


__all__ = [
    "DEFAULT_KPIS",
    "EXCLUDED_FACTORS",
    "build_variance_decomposition",
    "factor_family",
]
