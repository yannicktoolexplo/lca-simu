from __future__ import annotations

"""Prediction-output to physical-risk mapping for the SCAN end-2026 PoC.

The supplier prediction model emits probabilities and conditional impact proxies.
This module converts those statistical outputs into auditable physical uncertainty
on availability, capacity, lead time, quality yield and cost.  It deliberately
keeps the mapping configurable because the coefficients are research hypotheses
until they are calibrated with industrial observations.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import clamp, first_existing_column, safe_float, sigmoid


@dataclass(frozen=True)
class PredictionIntervalMetadata:
    source_path: str | None
    calibration_path: str | None
    interval_method: str
    nominal_coverage: float | None
    residual_quantile: float | None
    rows_used: int
    pairs_used: int
    prediction_rows_used: int
    input_status: str
    fallback_used: bool
    fallback_reason: str | None
    probability_column: str | None
    lower_column: str | None
    upper_column: str | None
    uncertainty_column: str | None
    calibration_probability_column: str | None
    calibration_truth_column: str | None
    prediction_granularity: str
    empirical_calibration_coverage: float | None = None
    calibration_coverage_rows: int = 0
    coverage_definition: str = "not_applicable"
    effective_interval_half_width: float | None = None
    coverage_guarantee_status: str = "not_available"
    forecast_validity_days: float | None = None
    long_horizon_prior_center: float | None = None
    uncertainty_policy: str = "not_applicable"
    requested_nominal_coverage: float | None = None
    effective_finite_sample_level: float | None = None
    maximum_attainable_finite_sample_level: float | None = None
    conformal_rank: int | None = None
    conformal_calibration_status: str = "not_estimable_not_evaluated"
    coverage_target: str = "none"
    interval_semantics: str = "not_reported"
    empirical_calibration_metric: str = "not_applicable"
    coverage_limitations: str = "not_reported"
    calibration_rows_before: int = 0
    calibration_rows_after: int = 0
    excluded_overlap_rows: int = 0
    overlap_key_columns: tuple[str, ...] = ()
    operational_target_rows: int = 0
    operational_probability_unique_count: int = 0
    operational_snapshot_date: str | None = None
    operational_week_index: float | None = None
    calibration_use_status: str = "retrospective_non_deployment"


@dataclass(frozen=True)
class _ResidualCalibration:
    """Auditable split-conformal score calibration for a binary outcome.

    The score ``abs(Y - p_hat)`` can calibrate membership of a future binary
    outcome in a predictive envelope.  It is not an estimator or confidence
    interval for the latent conditional probability ``P(Y=1 | X)``.
    """

    quantile: float | None
    rows: int
    probability_column: str | None
    truth_column: str | None
    empirical_score_inclusion_rate: float | None
    requested_rank: int | None
    effective_finite_sample_level: float | None
    maximum_attainable_finite_sample_level: float | None
    status: str
    calibration_rows_before: int = 0
    calibration_rows_after: int = 0
    excluded_overlap_rows: int = 0
    overlap_key_columns: tuple[str, ...] = ()


DEFAULT_PHYSICAL_MAPPING: dict[str, float] = {
    "availability_loss_at_unit_risk": 0.55,
    "capacity_loss_at_unit_risk": 0.42,
    "lead_extra_fraction_of_nominal_at_unit_risk": 1.10,
    "quality_yield_loss_at_unit_risk": 0.24,
    "purchase_cost_increase_at_unit_risk": 0.35,
    "transport_cost_increase_at_unit_risk": 0.22,
    "severity_backlog_scale": 25.0,
    "severity_fill_loss_scale": 0.025,
    "minimum_interval_half_width": 0.04,
    "maximum_interval_half_width": 0.35,
    "conformal_alpha": 0.10,
    "forecast_validity_days": 30.0,
    "forecast_decay_days": 30.0,
    "long_horizon_prior_center": 0.12,
    "long_horizon_prior_half_width": 0.25,
    "long_horizon_uncertainty_growth": 0.10,
}


PROBABILITY_COLUMNS: tuple[str, ...] = (
    "predicted_incident_probability_30d",
    "predicted_probability",
    "predicted_risk_probability",
    "risk_probability",
    "predicted_risk",
    "probability",
    "p_risk",
    "mean_predicted_incident_probability_30d",
    "max_predicted_incident_probability_30d",
)
LOWER_COLUMNS: tuple[str, ...] = (
    "predicted_probability_lower",
    "lower_probability",
    "risk_lower",
    "lower_bound",
    "prediction_lower",
)
UPPER_COLUMNS: tuple[str, ...] = (
    "predicted_probability_upper",
    "upper_probability",
    "risk_upper",
    "upper_bound",
    "prediction_upper",
)


def _numeric(frame: pd.DataFrame, names: Sequence[str], default: float = 0.0) -> pd.Series:
    column = first_existing_column(frame, names)
    if column is None:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _discover_prediction_calibration(prediction_path: Path | None) -> Path | None:
    if prediction_path is None:
        return None
    candidates = [
        prediction_path.parent / "prediction_test_scored_rows.csv",
        prediction_path.parent.parent / "result" / "prediction_test_scored_rows.csv",
        prediction_path.parent / "calibration_rows.csv",
    ]
    return next((candidate for candidate in candidates if candidate.exists() and candidate.stat().st_size > 0), None)


_OVERLAP_COLUMN_CANDIDATES: dict[str, tuple[str, ...]] = {
    "snapshot_date": ("snapshot_date", "forecast_snapshot_date"),
    "week_index": ("week_index", "week", "period_index"),
    "pair_key": ("pair_key", "supplier_item_factory_key"),
    "supplier_id": ("supplier_id", "supplier", "src_node_id"),
    "item_id": ("item_id", "material_id", "component_id"),
    "dst_node_id": (
        "factory_id",
        "dst_node_id",
        "destination_node_id",
        "site_id",
    ),
}


def _normalise_overlap_column(series: pd.Series, axis: str) -> pd.Series:
    """Return stable comparable values without treating missing keys as equal."""

    if axis == "snapshot_date":
        values = pd.to_datetime(series, errors="coerce")
        return values.dt.strftime("%Y-%m-%dT%H:%M:%S.%f")
    if axis == "week_index":
        values = pd.to_numeric(series, errors="coerce")
        return values.map(lambda value: format(float(value), ".17g") if pd.notna(value) else pd.NA)
    values = series.astype("string").str.strip()
    return values.mask(values.eq(""), pd.NA)


def _exact_operational_overlap_mask(
    calibration_frame: pd.DataFrame,
    operational_target: pd.DataFrame | None,
) -> tuple[pd.Series, tuple[str, ...]]:
    """Identify exact snapshot/lane rows reused as the operational target.

    Exclusion is deliberately conservative: at least one shared temporal key is
    required, plus either a shared pair key or the complete supplier/item/site
    identity.  A calibration set is therefore never shortened using a weak
    supplier-only or item-only match.
    """

    empty = pd.Series(False, index=calibration_frame.index, dtype=bool)
    if operational_target is None or calibration_frame.empty or operational_target.empty:
        return empty, ()

    columns: dict[str, tuple[str, str]] = {}
    for axis, candidates in _OVERLAP_COLUMN_CANDIDATES.items():
        calibration_column = first_existing_column(calibration_frame, candidates)
        operational_column = first_existing_column(operational_target, candidates)
        if calibration_column is not None and operational_column is not None:
            columns[axis] = (calibration_column, operational_column)

    temporal_axes = [
        axis for axis in ("snapshot_date", "week_index") if axis in columns
    ]
    if not temporal_axes:
        return empty, ()
    if "pair_key" in columns:
        identity_axes = ["pair_key"]
    elif all(axis in columns for axis in ("supplier_id", "item_id", "dst_node_id")):
        identity_axes = ["supplier_id", "item_id", "dst_node_id"]
    else:
        return empty, ()
    axes = tuple([*temporal_axes, *identity_axes])

    calibration_keys = pd.DataFrame(index=calibration_frame.index)
    operational_keys = pd.DataFrame(index=operational_target.index)
    for axis in axes:
        calibration_column, operational_column = columns[axis]
        calibration_keys[axis] = _normalise_overlap_column(
            calibration_frame[calibration_column], axis
        )
        operational_keys[axis] = _normalise_overlap_column(
            operational_target[operational_column], axis
        )
    valid_calibration = calibration_keys.notna().all(axis=1)
    valid_operational = operational_keys.notna().all(axis=1)
    if not valid_operational.any():
        return empty, ()
    target_keys = {
        tuple(row)
        for row in operational_keys.loc[valid_operational, list(axes)].itertuples(
            index=False, name=None
        )
    }
    matched = calibration_keys.loc[:, list(axes)].apply(
        lambda row: tuple(row) in target_keys,
        axis=1,
    )
    return (valid_calibration & matched).astype(bool), axes


def _calibrate_binary_outcome_residuals(
    calibration_path: Path | None,
    alpha: float,
    *,
    operational_target: pd.DataFrame | None = None,
) -> _ResidualCalibration:
    """Calibrate ``abs(Y - p_hat)`` without reinterpreting it as a CI for p.

    With ``n`` exchangeable calibration scores, a finite threshold at requested
    level ``1 - alpha`` exists only if
    ``ceil((n + 1) * (1 - alpha)) <= n``.  When that condition fails we return
    an explicit non-estimable status; using the largest observed score would
    advertise a finite-sample level that the calibration sample cannot attain.
    """

    if not 0.0 < float(alpha) < 1.0:
        return _ResidualCalibration(
            None, 0, None, None, None, None, None, None,
            "not_estimable_invalid_alpha",
        )
    if calibration_path is None:
        return _ResidualCalibration(
            None, 0, None, None, None, None, None, None,
            "not_estimable_calibration_path_missing",
        )
    try:
        frame = pd.read_csv(calibration_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return _ResidualCalibration(
            None, 0, None, None, None, None, None, None,
            "not_estimable_calibration_unreadable",
        )
    calibration_rows_before = int(len(frame))
    overlap_mask, overlap_key_columns = _exact_operational_overlap_mask(
        frame, operational_target
    )
    excluded_overlap_rows = int(overlap_mask.sum())
    if excluded_overlap_rows:
        frame = frame.loc[~overlap_mask].copy()
    calibration_rows_after = int(len(frame))
    probability_column = first_existing_column(frame, PROBABILITY_COLUMNS)
    truth_column = first_existing_column(frame, [
        "incident_next_30d", "true_incident", "incident", "label", "target", "y_true"
    ])
    if probability_column is None or truth_column is None:
        return _ResidualCalibration(
            None, 0, probability_column, truth_column, None, None, None, None,
            "not_estimable_probability_or_binary_truth_column_missing",
            calibration_rows_before,
            calibration_rows_after,
            excluded_overlap_rows,
            overlap_key_columns,
        )
    probability = pd.to_numeric(frame[probability_column], errors="coerce")
    truth = pd.to_numeric(frame[truth_column], errors="coerce")
    valid = (
        probability.notna()
        & probability.between(0.0, 1.0, inclusive="both")
        & truth.isin([0.0, 1.0])
    )
    if not valid.any():
        return _ResidualCalibration(
            None, 0, probability_column, truth_column, None, None, None, None,
            "not_estimable_no_valid_binary_outcome_rows",
            calibration_rows_before,
            calibration_rows_after,
            excluded_overlap_rows,
            overlap_key_columns,
        )
    residuals = (
        truth[valid] - probability[valid]
    ).abs().to_numpy(dtype=float)
    rows = int(len(residuals))
    requested_rank = int(np.ceil((rows + 1) * (1.0 - alpha)))
    maximum_level = float(rows / (rows + 1))
    if requested_rank > rows:
        return _ResidualCalibration(
            None,
            rows,
            probability_column,
            truth_column,
            None,
            requested_rank,
            None,
            maximum_level,
            "not_estimable_requested_rank_exceeds_calibration_size",
            calibration_rows_before,
            calibration_rows_after,
            excluded_overlap_rows,
            overlap_key_columns,
        )
    quantile = float(np.sort(residuals)[requested_rank - 1])
    empirical_score_inclusion_rate = float(
        np.mean(residuals <= quantile + 1e-12)
    )
    return _ResidualCalibration(
        quantile,
        rows,
        probability_column,
        truth_column,
        empirical_score_inclusion_rate,
        requested_rank,
        float(requested_rank / (rows + 1)),
        maximum_level,
        "estimable_binary_outcome_predictive_score",
        calibration_rows_before,
        calibration_rows_after,
        excluded_overlap_rows,
        overlap_key_columns,
    )


def _conformal_residual_quantile(
    calibration_path: Path | None,
    alpha: float,
    *,
    operational_target: pd.DataFrame | None = None,
) -> tuple[float, int, str | None, str | None, float | None]:
    """Compatibility wrapper for the former private five-value helper."""

    result = _calibrate_binary_outcome_residuals(
        calibration_path,
        alpha,
        operational_target=operational_target,
    )
    return (
        float(result.quantile) if result.quantile is not None else float("nan"),
        result.rows,
        result.probability_column,
        result.truth_column,
        result.empirical_score_inclusion_rate,
    )


_BINARY_OUTCOME_COVERAGE_DEFINITION = (
    "future_binary_outcome_membership_abs_y_minus_p_hat_leq_q"
)
_BINARY_OUTCOME_COVERAGE_TARGET = "future_binary_incident_outcome"
_BINARY_OUTCOME_INTERVAL_SEMANTICS = (
    "residual_calibrated_binary_outcome_operational_envelope_"
    "not_latent_probability_confidence_interval"
)
_ASSUMPTION_ENVELOPE_SEMANTICS = (
    "nonconformal_assumption_envelope_not_calibrated_probability_interval"
)
_BINARY_OUTCOME_COVERAGE_LIMITATIONS = (
    "Finite-sample level concerns marginal membership of one future binary "
    "outcome under exchangeability and a predictor fixed independently of the "
    "calibration rows. It does not cover the latent incident probability, "
    "portfolio aggregation or selection, forecast-horizon transforms, or any "
    "mapped physical quantity. The calibration inclusion rate is in-sample."
)
_NONCONFORMAL_LIMITATIONS = (
    "Assumption envelope only: no conformal or frequentist coverage claim for "
    "a future outcome, a latent incident probability, or mapped physics."
)


def _aggregate_latest_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    snapshot_column = first_existing_column(work, ["snapshot_date", "date", "timestamp"])
    week_column = first_existing_column(work, ["week_index", "week", "period_index"])
    if snapshot_column is not None:
        snapshot = pd.to_datetime(work[snapshot_column], errors="coerce")
        if snapshot.notna().any():
            work = work.loc[snapshot == snapshot.max()].copy()
    elif week_column is not None:
        week = pd.to_numeric(work[week_column], errors="coerce")
        if week.notna().any():
            work = work.loc[week == week.max()].copy()
    return work


def _operational_target_summary(
    frame: pd.DataFrame | None,
) -> dict[str, Any]:
    """Summarise the exact operational snapshot used by the envelope."""

    if frame is None or frame.empty:
        return {
            "rows": 0,
            "probability_unique_count": 0,
            "snapshot_date": None,
            "week_index": None,
        }
    probability_column = first_existing_column(frame, PROBABILITY_COLUMNS)
    probability_unique_count = 0
    if probability_column is not None:
        probability = pd.to_numeric(frame[probability_column], errors="coerce")
        probability_unique_count = int(probability.dropna().nunique())
    snapshot_column = first_existing_column(
        frame, ["snapshot_date", "forecast_snapshot_date", "date"]
    )
    snapshot_date: str | None = None
    if snapshot_column is not None:
        timestamps = pd.to_datetime(frame[snapshot_column], errors="coerce")
        if timestamps.notna().any():
            snapshot_date = timestamps.max().isoformat()
    week_column = first_existing_column(frame, ["week_index", "week", "period_index"])
    week_index: float | None = None
    if week_column is not None:
        weeks = pd.to_numeric(frame[week_column], errors="coerce")
        if weeks.notna().any():
            week_index = float(weeks.max())
    return {
        "rows": int(len(frame)),
        "probability_unique_count": probability_unique_count,
        "snapshot_date": snapshot_date,
        "week_index": week_index,
    }


def _apply_forecast_horizon_decay(
    frame: pd.DataFrame,
    cfg: Mapping[str, Any],
    *,
    forecast_origin_day: float = 0.0,
) -> pd.DataFrame:
    """Decay the center to a prior while widening, never shrinking, uncertainty.

    ``risk_upper - risk_lower`` is the operational uncertainty consumed by the
    reduced controller.  It is held constant inside the predictor validity
    horizon, then grows monotonically toward a broad prior interval.  When the
    operational bounds already span ``[0, 1]`` the envelope is saturated and
    therefore remains constant.
    """

    result = frame.copy()
    if result.empty or int(result["day"].nunique()) <= 1:
        return result
    validity = max(1.0, safe_float(cfg.get("forecast_validity_days"), 30.0))
    decay = max(1.0, safe_float(cfg.get("forecast_decay_days"), 30.0))
    prior_center = clamp(
        safe_float(cfg.get("long_horizon_prior_center"), 0.12), 0.01, 0.99
    )
    configured_prior_width = clamp(
        safe_float(cfg.get("long_horizon_prior_half_width"), 0.25), 0.0, 0.50
    )
    growth = clamp(
        safe_float(cfg.get("long_horizon_uncertainty_growth"), 0.10), 0.0, 1.0
    )
    day = pd.to_numeric(result["day"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    blend = np.clip(
        (day - float(forecast_origin_day) - validity) / decay, 0.0, 1.0
    )
    center_start = pd.to_numeric(
        result["risk_center"], errors="coerce"
    ).fillna(prior_center).to_numpy(dtype=float)
    lower_start = pd.to_numeric(
        result["risk_lower"], errors="coerce"
    ).to_numpy(dtype=float)
    upper_start = pd.to_numeric(
        result["risk_upper"], errors="coerce"
    ).to_numpy(dtype=float)
    lower_start = np.where(np.isfinite(lower_start), lower_start, center_start)
    upper_start = np.where(np.isfinite(upper_start), upper_start, center_start)
    span_start = np.clip(upper_start - lower_start, 0.0, 1.0)
    target_span = np.minimum(
        1.0,
        np.maximum(2.0 * configured_prior_width, span_start + growth),
    )
    span = span_start + blend * (target_span - span_start)
    center = (1.0 - blend) * center_start + blend * prior_center

    # Shift bounded intervals rather than shortening them at probability
    # boundaries.  This preserves the requested span and keeps the center inside.
    lower = np.clip(center - 0.5 * span, 0.0, 1.0 - span)
    upper = lower + span
    result["risk_center"] = np.clip(center, 0.01, 0.99)
    result["risk_lower"] = np.minimum(lower, result["risk_center"])
    result["risk_upper"] = np.maximum(upper, result["risk_center"])
    result["risk_interval_span"] = result["risk_upper"] - result["risk_lower"]
    result["risk_uncertainty_half_width"] = 0.5 * result["risk_interval_span"]
    result["forecast_validity_status"] = np.where(
        day <= float(forecast_origin_day) + validity,
        "within_validity",
        "decayed_to_broad_prior",
    )
    return result


def _prediction_identifier_columns(frame: pd.DataFrame) -> dict[str, str | None]:
    return {
        "supplier_id": first_existing_column(
            frame, ["supplier_id", "supplier", "src_node_id"]
        ),
        "item_id": first_existing_column(
            frame, ["item_id", "material_id", "component_id"]
        ),
        "dst_node_id": first_existing_column(
            frame, ["factory_id", "dst_node_id", "destination_node_id", "site_id"]
        ),
    }


def build_granular_prediction_interval_envelope(
    prediction_path: Path | None,
    days: int,
    *,
    fallback_uncertainty: np.ndarray | Sequence[float] | None = None,
    mapping_config: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Preserve supplier-item-destination operational envelopes by forecast day.

    Only the latest predictor snapshot is treated as information available at
    simulation day zero.  Each distinct lane is expanded over the requested
    horizon, with its center decaying and interval widening after forecast
    validity.  The returned rows are suitable both for audit exports and
    pair-specific canonical risk-event mapping.
    """

    columns = [
        "scope",
        "day",
        "period",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "source_snapshot_date",
        "source_week_index",
        "risk_lower",
        "risk_center",
        "risk_upper",
        "risk_interval_span",
        "risk_uncertainty_half_width",
        "conditional_backlog_if_incident",
        "conditional_fill_loss_if_incident",
        "lead_mean_days",
        "priority_score",
        "source_pairs",
        "forecast_validity_status",
    ]
    if (
        prediction_path is None
        or days <= 0
        or not prediction_path.exists()
        or prediction_path.stat().st_size <= 0
    ):
        return pd.DataFrame(columns=columns)
    try:
        source = pd.read_csv(prediction_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame(columns=columns)
    probability_column = first_existing_column(source, PROBABILITY_COLUMNS)
    identifiers = _prediction_identifier_columns(source)
    if probability_column is None or not all(identifiers.values()):
        return pd.DataFrame(columns=columns)

    cfg = {**DEFAULT_PHYSICAL_MAPPING, **dict(mapping_config or {})}
    alpha = clamp(safe_float(cfg.get("conformal_alpha"), 0.10), 0.01, 0.49)
    minimum_width = safe_float(cfg.get("minimum_interval_half_width"), 0.04)
    maximum_width = safe_float(cfg.get("maximum_interval_half_width"), 0.35)
    fallback_width = float(
        np.nanmedian(
            np.asarray(
                fallback_uncertainty
                if fallback_uncertainty is not None
                else [0.10],
                dtype=float,
            )
        )
    )
    calibration_path = _discover_prediction_calibration(prediction_path)
    operational_target = _aggregate_latest_snapshot(source)
    residual_q, _, _, _, _ = _conformal_residual_quantile(
        calibration_path,
        alpha,
        operational_target=operational_target,
    )

    work = operational_target.copy()
    work["_probability"] = pd.to_numeric(
        work[probability_column], errors="coerce"
    ).clip(0, 1)
    work = work.dropna(subset=["_probability"])
    if work.empty:
        return pd.DataFrame(columns=columns)
    lower_column = first_existing_column(work, LOWER_COLUMNS)
    upper_column = first_existing_column(work, UPPER_COLUMNS)
    if lower_column and upper_column:
        work["_lower"] = pd.to_numeric(
            work[lower_column], errors="coerce"
        ).fillna(work["_probability"])
        work["_upper"] = pd.to_numeric(
            work[upper_column], errors="coerce"
        ).fillna(work["_probability"])
    else:
        penalty = _numeric(work, ["uncertainty_penalty"], 0.0).clip(0, 1)
        if np.isfinite(residual_q):
            # Reuse the binary-outcome score quantile as an operational
            # half-width. These endpoints are not confidence bounds for the
            # latent incident probability.
            width = np.minimum(1.0, max(minimum_width, residual_q) + 0.12 * penalty)
        else:
            width = np.clip(
                fallback_width + 0.12 * penalty, minimum_width, maximum_width
            )
        work["_lower"] = (work["_probability"] - width).clip(0, 1)
        work["_upper"] = (work["_probability"] + width).clip(0, 1)

    for canonical, source_column in identifiers.items():
        work[canonical] = work[str(source_column)].astype("string").fillna("").astype(str)
    work = work.loc[
        (work["supplier_id"].str.len() > 0)
        & (work["item_id"].str.len() > 0)
        & (work["dst_node_id"].str.len() > 0)
    ].copy()
    work["_backlog"] = _numeric(
        work,
        [
            "conditional_expected_backlog_if_incident",
            "expected_backlog_if_incident",
            "conditional_backlog",
        ],
        0.0,
    ).clip(lower=0)
    work["_fill_loss"] = _numeric(
        work,
        [
            "conditional_expected_fill_loss_if_incident",
            "expected_fill_loss_if_incident",
            "conditional_fill_loss",
        ],
        0.0,
    ).clip(lower=0)
    work["_lead_mean"] = _numeric(
        work, ["lead_mean_days", "lead_time_days", "planned_lead_time_days"], 5.0
    ).clip(lower=0.5)
    work["_priority"] = _numeric(
        work,
        [
            "predicted_priority_score",
            "combined_proxy_risk_score",
            "impact_proxy_score",
        ],
        1.0,
    ).clip(lower=0)
    work = work.sort_values(
        ["supplier_id", "item_id", "dst_node_id", "_priority"],
        ascending=[True, True, True, False],
    ).drop_duplicates(["supplier_id", "item_id", "dst_node_id"])

    snapshot_column = first_existing_column(work, ["snapshot_date", "date"])
    week_column = first_existing_column(work, ["week_index", "week", "period_index"])
    lane_rows = pd.DataFrame({
        "supplier_id": work["supplier_id"],
        "item_id": work["item_id"],
        "dst_node_id": work["dst_node_id"],
        "source_snapshot_date": (
            work[snapshot_column].astype("string").fillna("").astype(str)
            if snapshot_column
            else ""
        ),
        "source_week_index": (
            pd.to_numeric(work[week_column], errors="coerce")
            if week_column
            else np.nan
        ),
        "risk_lower": work["_lower"].clip(0, 1),
        "risk_center": work["_probability"].clip(0.01, 0.99),
        "risk_upper": work["_upper"].clip(0, 1),
        "conditional_backlog_if_incident": work["_backlog"],
        "conditional_fill_loss_if_incident": work["_fill_loss"],
        "lead_mean_days": work["_lead_mean"],
        "priority_score": work["_priority"],
    }).reset_index(drop=True)
    lane_rows["risk_lower"] = np.minimum(
        lane_rows["risk_lower"], lane_rows["risk_center"]
    )
    lane_rows["risk_upper"] = np.maximum(
        lane_rows["risk_upper"], lane_rows["risk_center"]
    )
    lane_rows["_join_key"] = 1
    day_grid = pd.DataFrame({"day": np.arange(days, dtype=int), "_join_key": 1})
    granular = lane_rows.merge(day_grid, on="_join_key", how="inner").drop(
        columns=["_join_key"]
    )
    granular["scope"] = "supplier_item_destination"
    granular["period"] = granular["day"]
    granular["source_pairs"] = 1
    granular = pd.concat(
        [
            _apply_forecast_horizon_decay(group, cfg)
            for _, group in granular.groupby(
                ["supplier_id", "item_id", "dst_node_id"], sort=False
            )
        ],
        ignore_index=True,
    )
    granular["scope"] = "supplier_item_destination"
    granular["supplier_id"] = granular["supplier_id"].astype(str)
    granular["item_id"] = granular["item_id"].astype(str)
    granular["dst_node_id"] = granular["dst_node_id"].astype(str)
    return granular.reindex(columns=columns)


def build_prediction_interval_envelope(
    prediction_path: Path | None,
    days: int,
    *,
    fallback_center: np.ndarray | Sequence[float] | None = None,
    fallback_uncertainty: np.ndarray | Sequence[float] | None = None,
    mapping_config: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, PredictionIntervalMetadata]:
    """Create one daily portfolio-level operational prediction envelope.

    The current prediction POC is supplier-item-site based and usually contains
    weekly snapshots rather than a daily interval.  For the reduced-order risk
    control bench we aggregate the most recent snapshot with a priority-weighted
    upper-tail rule, then repeat it over the requested horizon.  If dated daily or
    weekly observations are provided, the function interpolates them instead.
    """

    cfg = {**DEFAULT_PHYSICAL_MAPPING, **dict(mapping_config or {})}
    alpha = clamp(safe_float(cfg.get("conformal_alpha"), 0.10), 0.01, 0.49)
    requested_nominal_coverage = 1.0 - alpha
    minimum_width = safe_float(cfg.get("minimum_interval_half_width"), 0.04)
    maximum_width = safe_float(cfg.get("maximum_interval_half_width"), 0.35)
    fallback_center_array = np.asarray(
        fallback_center if fallback_center is not None else np.full(days, 0.12), dtype=float
    )
    if len(fallback_center_array) < days:
        fallback_center_array = np.pad(fallback_center_array, (0, days - len(fallback_center_array)), mode="edge")
    fallback_width_array = np.asarray(
        fallback_uncertainty if fallback_uncertainty is not None else np.full(days, 0.10), dtype=float
    )
    if len(fallback_width_array) < days:
        fallback_width_array = np.pad(fallback_width_array, (0, days - len(fallback_width_array)), mode="edge")

    prediction_source: pd.DataFrame | None = None
    if (
        prediction_path is not None
        and prediction_path.exists()
        and prediction_path.stat().st_size > 0
    ):
        try:
            prediction_source = pd.read_csv(prediction_path)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError):
            prediction_source = None
    operational_target = (
        _aggregate_latest_snapshot(prediction_source)
        if prediction_source is not None
        else None
    )
    operational_summary = _operational_target_summary(operational_target)
    calibration_path = _discover_prediction_calibration(prediction_path)
    calibration = _calibrate_binary_outcome_residuals(
        calibration_path,
        alpha,
        operational_target=operational_target,
    )
    residual_q = (
        float(calibration.quantile)
        if calibration.quantile is not None
        else float("nan")
    )
    residual_rows = calibration.rows
    calibration_probability_column = calibration.probability_column
    calibration_truth_column = calibration.truth_column
    empirical_calibration_coverage = calibration.empirical_score_inclusion_rate
    if calibration.quantile is not None:
        # q calibrates a binary-outcome score, not uncertainty about the latent
        # probability.  Widening this operational envelope does not weaken the
        # score-membership construction, but downstream transforms have no such
        # guarantee (see the exported limitations).
        residual_half_width = clamp(calibration.quantile, minimum_width, 1.0)
        coverage_guarantee_status = (
            "finite_sample_binary_outcome_score_level_under_exchangeability"
        )
    else:
        residual_half_width = clamp(
            float(np.nanmedian(fallback_width_array)),
            minimum_width,
            maximum_width,
        )
        coverage_guarantee_status = "nonconformal_assumption_envelope"

    if prediction_path is None or not prediction_path.exists() or prediction_path.stat().st_size <= 0:
        center = np.clip(fallback_center_array[:days], 0.01, 0.99)
        width = np.clip(fallback_width_array[:days], minimum_width, maximum_width)
        envelope = pd.DataFrame({
            "day": np.arange(days, dtype=int),
            "risk_lower": np.clip(center - width, 0.0, 1.0),
            "risk_center": center,
            "risk_upper": np.clip(center + width, 0.0, 1.0),
            "conditional_backlog_if_incident": np.zeros(days),
            "conditional_fill_loss_if_incident": np.zeros(days),
            "lead_mean_days": np.full(days, 5.0),
            "priority_score": center,
            "source_pairs": np.ones(days, dtype=int),
        })
        return envelope, PredictionIntervalMetadata(
            str(prediction_path) if prediction_path is not None else None,
            str(calibration_path) if calibration_path else None,
            "assumption_envelope_from_existing_risk_series",
            None,
            float(residual_q) if np.isfinite(residual_q) else None,
            residual_rows,
            0,
            0,
            "fallback_consumed",
            True,
            (
                "prediction_file_not_found"
                if prediction_path is None
                else "prediction_file_missing_or_empty"
            ),
            None,
            None,
            None,
            None,
            calibration_probability_column,
            calibration_truth_column,
            "fallback_portfolio_series",
            empirical_calibration_coverage,
            residual_rows,
            "not_applicable_nonconformal_assumption_envelope",
            float(np.nanmedian(width)) if len(width) else None,
            "nonconformal_assumption_envelope",
            safe_float(cfg.get("forecast_validity_days"), 30.0),
            safe_float(cfg.get("long_horizon_prior_center"), 0.12),
            "fallback_series_width_not_forced_to_grow",
            requested_nominal_coverage=requested_nominal_coverage,
            effective_finite_sample_level=(
                calibration.effective_finite_sample_level
            ),
            maximum_attainable_finite_sample_level=(
                calibration.maximum_attainable_finite_sample_level
            ),
            conformal_rank=calibration.requested_rank,
            conformal_calibration_status=calibration.status,
            coverage_target="none",
            interval_semantics=_ASSUMPTION_ENVELOPE_SEMANTICS,
            empirical_calibration_metric=(
                "in_sample_calibration_score_inclusion_rate_not_predictive_coverage"
                if empirical_calibration_coverage is not None
                else "not_available"
            ),
            coverage_limitations=_NONCONFORMAL_LIMITATIONS,
            calibration_rows_before=calibration.calibration_rows_before,
            calibration_rows_after=calibration.calibration_rows_after,
            excluded_overlap_rows=calibration.excluded_overlap_rows,
            overlap_key_columns=calibration.overlap_key_columns,
            operational_target_rows=int(operational_summary["rows"]),
            operational_probability_unique_count=int(
                operational_summary["probability_unique_count"]
            ),
            operational_snapshot_date=operational_summary["snapshot_date"],
            operational_week_index=operational_summary["week_index"],
        )

    frame = (
        prediction_source.copy()
        if prediction_source is not None
        else pd.read_csv(prediction_path)
    )
    probability_column = first_existing_column(frame, PROBABILITY_COLUMNS)
    if probability_column is None:
        center = np.clip(fallback_center_array[:days], 0.01, 0.99)
        width = np.clip(fallback_width_array[:days], minimum_width, maximum_width)
        envelope = pd.DataFrame({
            "day": np.arange(days, dtype=int),
            "risk_lower": np.clip(center - width, 0.0, 1.0),
            "risk_center": center,
            "risk_upper": np.clip(center + width, 0.0, 1.0),
            "conditional_backlog_if_incident": np.zeros(days),
            "conditional_fill_loss_if_incident": np.zeros(days),
            "lead_mean_days": np.full(days, 5.0),
            "priority_score": center,
            "source_pairs": np.ones(days, dtype=int),
        })
        return envelope, PredictionIntervalMetadata(
            str(prediction_path),
            str(calibration_path) if calibration_path else None,
            "assumption_envelope_probability_column_missing",
            None,
            float(residual_q) if np.isfinite(residual_q) else None,
            residual_rows,
            0,
            0,
            "fallback_consumed",
            True,
            "probability_column_missing",
            None,
            None,
            None,
            None,
            calibration_probability_column,
            calibration_truth_column,
            "fallback_portfolio_series",
            empirical_calibration_coverage,
            residual_rows,
            "not_applicable_nonconformal_assumption_envelope",
            float(np.nanmedian(width)) if len(width) else None,
            "nonconformal_assumption_envelope",
            safe_float(cfg.get("forecast_validity_days"), 30.0),
            safe_float(cfg.get("long_horizon_prior_center"), 0.12),
            "fallback_series_width_not_forced_to_grow",
            requested_nominal_coverage=requested_nominal_coverage,
            effective_finite_sample_level=(
                calibration.effective_finite_sample_level
            ),
            maximum_attainable_finite_sample_level=(
                calibration.maximum_attainable_finite_sample_level
            ),
            conformal_rank=calibration.requested_rank,
            conformal_calibration_status=calibration.status,
            coverage_target="none",
            interval_semantics=_ASSUMPTION_ENVELOPE_SEMANTICS,
            empirical_calibration_metric=(
                "in_sample_calibration_score_inclusion_rate_not_predictive_coverage"
                if empirical_calibration_coverage is not None
                else "not_available"
            ),
            coverage_limitations=_NONCONFORMAL_LIMITATIONS,
            calibration_rows_before=calibration.calibration_rows_before,
            calibration_rows_after=calibration.calibration_rows_after,
            excluded_overlap_rows=calibration.excluded_overlap_rows,
            overlap_key_columns=calibration.overlap_key_columns,
            operational_target_rows=int(operational_summary["rows"]),
            operational_probability_unique_count=int(
                operational_summary["probability_unique_count"]
            ),
            operational_snapshot_date=operational_summary["snapshot_date"],
            operational_week_index=operational_summary["week_index"],
        )

    work = frame.copy()
    work["_probability"] = pd.to_numeric(work[probability_column], errors="coerce").clip(0, 1)
    work = work.dropna(subset=["_probability"])
    if work.empty:
        return build_prediction_interval_envelope(
            None,
            days,
            fallback_center=fallback_center_array,
            fallback_uncertainty=fallback_width_array,
            mapping_config=cfg,
        )

    lower_column = first_existing_column(work, LOWER_COLUMNS)
    upper_column = first_existing_column(work, UPPER_COLUMNS)
    if lower_column and upper_column:
        work["_lower"] = pd.to_numeric(work[lower_column], errors="coerce").fillna(work["_probability"])
        work["_upper"] = pd.to_numeric(work[upper_column], errors="coerce").fillna(work["_probability"])
        interval_method = "provided_probability_interval"
        uncertainty_column = None
    else:
        uncertainty_column = first_existing_column(work, ["uncertainty_penalty"])
        row_penalty = _numeric(work, ["uncertainty_penalty"], 0.0).clip(0, 1)
        if np.isfinite(residual_q):
            row_width = np.minimum(
                1.0, residual_half_width + 0.12 * row_penalty
            )
        else:
            row_width = np.clip(
                residual_half_width + 0.12 * row_penalty,
                minimum_width,
                maximum_width,
            )
        work["_lower"] = (work["_probability"] - row_width).clip(0, 1)
        work["_upper"] = (work["_probability"] + row_width).clip(0, 1)
        interval_method = (
            "binary_outcome_residual_calibrated_operational_envelope"
            if calibration.quantile is not None
            else "assumption_envelope_with_uncertainty_penalty"
        )

    work["_backlog"] = _numeric(work, [
        "conditional_expected_backlog_if_incident", "expected_backlog_if_incident", "conditional_backlog"
    ], 0.0).clip(lower=0)
    work["_fill_loss"] = _numeric(work, [
        "conditional_expected_fill_loss_if_incident", "expected_fill_loss_if_incident", "conditional_fill_loss"
    ], 0.0).clip(lower=0)
    work["_lead_mean"] = _numeric(work, ["lead_mean_days", "lead_time_days", "planned_lead_time_days"], 5.0).clip(lower=0.5)
    work["_priority"] = _numeric(work, [
        "predicted_priority_score", "combined_proxy_risk_score", "impact_proxy_score"
    ], 1.0).clip(lower=0)

    day_column = first_existing_column(work, ["day", "day_index", "date_index"])
    week_column = first_existing_column(work, ["week_index", "week", "period_index"])
    snapshot_column = first_existing_column(work, ["snapshot_date", "date"])

    if day_column is not None:
        work["_day"] = pd.to_numeric(work[day_column], errors="coerce")
    elif snapshot_column is not None:
        timestamps = pd.to_datetime(work[snapshot_column], errors="coerce")
        if timestamps.notna().any():
            origin = timestamps.min()
            work["_day"] = (timestamps - origin).dt.days
        else:
            work["_day"] = np.nan
    elif week_column is not None:
        weeks = pd.to_numeric(work[week_column], errors="coerce")
        work["_day"] = (weeks - weeks.min()) * 7
    else:
        work = _aggregate_latest_snapshot(work)
        work["_day"] = 0

    work = work.dropna(subset=["_day"])
    work["_day"] = work["_day"].astype(int)
    # Priority-weighted upper-tail aggregation retains critical supplier-item-site
    # pairs without letting a single tiny pair fully dominate the portfolio.
    def aggregate_group(group: pd.DataFrame) -> pd.Series:
        weight = np.maximum(group["_priority"].to_numpy(dtype=float), 0.05)
        weight = weight / weight.sum()
        order = np.argsort(group["_probability"].to_numpy(dtype=float))
        cumulative = np.cumsum(weight[order])
        quantile_idx = order[min(int(np.searchsorted(cumulative, 0.85)), len(order) - 1)]
        anchor = group.iloc[int(quantile_idx)]
        return pd.Series({
            "risk_lower": float(anchor["_lower"]),
            "risk_center": float(anchor["_probability"]),
            "risk_upper": float(anchor["_upper"]),
            "conditional_backlog_if_incident": float(np.average(group["_backlog"], weights=weight)),
            "conditional_fill_loss_if_incident": float(np.average(group["_fill_loss"], weights=weight)),
            "lead_mean_days": float(np.average(group["_lead_mean"], weights=weight)),
            "priority_score": float(group["_priority"].max()),
            "source_pairs": int(len(group)),
        })

    daily = work.groupby("_day", sort=True, group_keys=False).apply(aggregate_group, include_groups=False)
    daily.index.name = "day"
    daily = daily.reset_index().sort_values("day")
    grid = pd.DataFrame({"day": np.arange(days, dtype=int)})
    envelope = grid.merge(daily, on="day", how="left")
    numeric_columns = [column for column in envelope.columns if column != "day"]
    envelope[numeric_columns] = envelope[numeric_columns].interpolate(limit_direction="both")
    # A supplier forecast must not be extrapolated as certain past the validity
    # of its last observed prediction period.
    last_prediction_day = float(
        pd.to_numeric(daily["day"], errors="coerce").max()
    )
    if days > 1 and np.isfinite(last_prediction_day):
        envelope = _apply_forecast_horizon_decay(
            envelope,
            cfg,
            forecast_origin_day=last_prediction_day,
        )
        validity = max(1.0, safe_float(cfg.get("forecast_validity_days"), 30.0))
        decay = max(1.0, safe_float(cfg.get("forecast_decay_days"), 30.0))
        prior_center = clamp(
            safe_float(cfg.get("long_horizon_prior_center"), 0.12), 0.01, 0.99
        )
        blend = np.clip(
            (
                envelope["day"].to_numpy(dtype=float)
                - last_prediction_day
                - validity
            )
            / decay,
            0.0,
            1.0,
        )
        envelope["priority_score"] = (1.0 - blend) * envelope["priority_score"].to_numpy(dtype=float) + blend * prior_center
        if bool((blend > 0.0).any()):
            interval_method = f"{interval_method}_with_forecast_horizon_decay"
    else:
        envelope["risk_interval_span"] = envelope["risk_upper"] - envelope["risk_lower"]
        envelope["risk_uncertainty_half_width"] = (
            0.5 * envelope["risk_interval_span"]
        )
        envelope["forecast_validity_status"] = "within_observed_prediction_periods"
    envelope["source_pairs"] = envelope["source_pairs"].round().fillna(0).astype(int)
    envelope["risk_lower"] = envelope["risk_lower"].clip(0, 1)
    envelope["risk_center"] = envelope["risk_center"].clip(0.01, 0.99)
    envelope["risk_upper"] = envelope["risk_upper"].clip(0, 1)
    envelope["risk_lower"] = np.minimum(envelope["risk_lower"], envelope["risk_center"])
    envelope["risk_upper"] = np.maximum(envelope["risk_upper"], envelope["risk_center"])
    envelope["risk_interval_span"] = envelope["risk_upper"] - envelope["risk_lower"]
    envelope["risk_uncertainty_half_width"] = 0.5 * envelope["risk_interval_span"]
    envelope["scope"] = "portfolio"
    envelope["period"] = envelope["day"]
    envelope["supplier_id"] = ""
    envelope["item_id"] = ""
    envelope["dst_node_id"] = ""
    identifier_columns = {
        "supplier": first_existing_column(work, ["supplier_id", "supplier", "src_node_id"]),
        "item": first_existing_column(work, ["item_id", "material_id", "component_id"]),
        "destination": first_existing_column(
            work, ["factory_id", "dst_node_id", "destination_node_id", "site_id"]
        ),
    }
    prediction_granularity = (
        "supplier_item_destination"
        if all(identifier_columns.values())
        else "supplier_aggregate"
    )
    if lower_column and upper_column:
        reported_nominal_coverage = None
        reported_coverage_status = "provided_interval_coverage_not_evaluated"
        reported_coverage_definition = "not_evaluated_provided_interval"
        reported_coverage_target = "unspecified_provided_interval_target"
        reported_interval_semantics = (
            "provided_probability_interval_semantics_and_coverage_not_evaluated"
        )
        reported_limitations = (
            "Source-provided endpoints are passed through, but their construction, "
            "coverage target and empirical coverage were not established here."
        )
        effective_interval_half_width = float(
            np.nanmedian(
                0.5
                * (
                    pd.to_numeric(work["_upper"], errors="coerce")
                    - pd.to_numeric(work["_lower"], errors="coerce")
                ).clip(lower=0.0)
            )
        )
    elif calibration.quantile is not None:
        reported_nominal_coverage = requested_nominal_coverage
        reported_coverage_status = coverage_guarantee_status
        reported_coverage_definition = _BINARY_OUTCOME_COVERAGE_DEFINITION
        reported_coverage_target = _BINARY_OUTCOME_COVERAGE_TARGET
        reported_interval_semantics = _BINARY_OUTCOME_INTERVAL_SEMANTICS
        reported_limitations = _BINARY_OUTCOME_COVERAGE_LIMITATIONS
        effective_interval_half_width = residual_half_width
    else:
        reported_nominal_coverage = None
        reported_coverage_status = "nonconformal_assumption_envelope"
        reported_coverage_definition = (
            "not_applicable_nonconformal_assumption_envelope"
        )
        reported_coverage_target = "none"
        reported_interval_semantics = _ASSUMPTION_ENVELOPE_SEMANTICS
        reported_limitations = _NONCONFORMAL_LIMITATIONS
        effective_interval_half_width = residual_half_width
    return envelope, PredictionIntervalMetadata(
        str(prediction_path),
        str(calibration_path) if calibration_path else None,
        interval_method,
        reported_nominal_coverage,
        float(residual_q) if np.isfinite(residual_q) else None,
        residual_rows,
        int(work[[c for c in ["supplier_id", "item_id", "factory_id"] if c in work]].drop_duplicates().shape[0])
        if any(c in work for c in ["supplier_id", "item_id", "factory_id"]) else int(len(work)),
        int(len(work)),
        "prediction_rows_consumed",
        False,
        None,
        probability_column,
        lower_column,
        upper_column,
        uncertainty_column,
        calibration_probability_column,
        calibration_truth_column,
        prediction_granularity,
        empirical_calibration_coverage,
        residual_rows,
        reported_coverage_definition,
        effective_interval_half_width,
        reported_coverage_status,
        safe_float(cfg.get("forecast_validity_days"), 30.0),
        safe_float(cfg.get("long_horizon_prior_center"), 0.12),
        "nondecreasing_interval_span_after_validity",
        requested_nominal_coverage=requested_nominal_coverage,
        effective_finite_sample_level=calibration.effective_finite_sample_level,
        maximum_attainable_finite_sample_level=(
            calibration.maximum_attainable_finite_sample_level
        ),
        conformal_rank=calibration.requested_rank,
        conformal_calibration_status=calibration.status,
        coverage_target=reported_coverage_target,
        interval_semantics=reported_interval_semantics,
        empirical_calibration_metric=(
            "in_sample_calibration_score_inclusion_rate_not_predictive_coverage"
            if empirical_calibration_coverage is not None
            else "not_available"
        ),
        coverage_limitations=reported_limitations,
        calibration_rows_before=calibration.calibration_rows_before,
        calibration_rows_after=calibration.calibration_rows_after,
        excluded_overlap_rows=calibration.excluded_overlap_rows,
        overlap_key_columns=calibration.overlap_key_columns,
        operational_target_rows=int(operational_summary["rows"]),
        operational_probability_unique_count=int(
            operational_summary["probability_unique_count"]
        ),
        operational_snapshot_date=operational_summary["snapshot_date"],
        operational_week_index=operational_summary["week_index"],
    )


def _severity_index(envelope: pd.DataFrame, cfg: Mapping[str, Any]) -> np.ndarray:
    backlog_scale = max(1e-6, safe_float(cfg.get("severity_backlog_scale"), 25.0))
    fill_scale = max(1e-6, safe_float(cfg.get("severity_fill_loss_scale"), 0.025))
    backlog = pd.to_numeric(envelope.get("conditional_backlog_if_incident", 0.0), errors="coerce").fillna(0).to_numpy(dtype=float)
    fill = pd.to_numeric(envelope.get("conditional_fill_loss_if_incident", 0.0), errors="coerce").fillna(0).to_numpy(dtype=float)
    severity = 0.55 * np.tanh(backlog / backlog_scale) + 0.45 * np.tanh(fill / fill_scale)
    # Never collapse to zero: a probability without an impact proxy still has a
    # physical interpretation, just with lower confidence.
    return np.clip(0.35 + 0.65 * severity, 0.20, 1.0)


def map_prediction_interval_to_physical(
    envelope: pd.DataFrame,
    mapping_config: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    cfg = {**DEFAULT_PHYSICAL_MAPPING, **dict(mapping_config or {})}
    result = envelope.copy()
    severity = _severity_index(result, cfg)
    result["severity_index"] = severity
    nominal_lead = pd.to_numeric(result.get("lead_mean_days", 5.0), errors="coerce").fillna(5.0).clip(lower=0.5).to_numpy(dtype=float)

    for suffix in ("lower", "center", "upper"):
        probability = pd.to_numeric(result[f"risk_{suffix}"], errors="coerce").fillna(0.0).clip(0, 1).to_numpy(dtype=float)
        weighted = probability * severity
        result[f"availability_multiplier_{suffix}"] = np.clip(
            1.0 - safe_float(cfg["availability_loss_at_unit_risk"]) * weighted, 0.20, 1.05
        )
        result[f"capacity_multiplier_{suffix}"] = np.clip(
            1.0 - safe_float(cfg["capacity_loss_at_unit_risk"]) * weighted, 0.25, 1.05
        )
        result[f"lead_time_extra_days_{suffix}"] = np.clip(
            safe_float(cfg["lead_extra_fraction_of_nominal_at_unit_risk"]) * nominal_lead * weighted,
            0.0,
            90.0,
        )
        result[f"quality_yield_multiplier_{suffix}"] = np.clip(
            1.0 - safe_float(cfg["quality_yield_loss_at_unit_risk"]) * weighted, 0.50, 1.0
        )
        result[f"purchase_cost_multiplier_{suffix}"] = np.clip(
            1.0 + safe_float(cfg["purchase_cost_increase_at_unit_risk"]) * weighted, 1.0, 2.5
        )
        result[f"transport_cost_multiplier_{suffix}"] = np.clip(
            1.0 + safe_float(cfg["transport_cost_increase_at_unit_risk"]) * weighted, 1.0, 2.0
        )
    return result


SENSITIVITY_COEFFICIENT_TARGETS: dict[str, str] = {
    "availability_loss_at_unit_risk": "availability_multiplier",
    "capacity_loss_at_unit_risk": "capacity_multiplier",
    "lead_extra_fraction_of_nominal_at_unit_risk": "lead_time_extra_days",
    "quality_yield_loss_at_unit_risk": "quality_yield_multiplier",
    "purchase_cost_increase_at_unit_risk": "purchase_cost_multiplier",
    "transport_cost_increase_at_unit_risk": "transport_cost_multiplier",
}


def physical_mapping_coefficient_sensitivity(
    envelope: pd.DataFrame,
    mapping_config: Mapping[str, Any] | None = None,
    *,
    factors: Sequence[float] = (0.8, 1.0, 1.2),
    coefficients: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Evaluate explicit one-at-a-time physical-mapping coefficient changes."""

    output_columns = [
        "coefficient",
        "factor",
        "baseline_coefficient_value",
        "perturbed_coefficient_value",
        "physical_field",
        "interval_side",
        "baseline_mean_physical_value",
        "perturbed_mean_physical_value",
        "absolute_delta",
        "relative_delta",
        "rows_evaluated",
    ]
    if envelope.empty:
        return pd.DataFrame(columns=output_columns)
    factor_values = [safe_float(value, float("nan")) for value in factors]
    if not factor_values or any(
        not np.isfinite(value) or value <= 0.0 for value in factor_values
    ):
        raise ValueError("Sensitivity factors must be finite and strictly positive.")
    cfg = {**DEFAULT_PHYSICAL_MAPPING, **dict(mapping_config or {})}
    selected = list(coefficients or SENSITIVITY_COEFFICIENT_TARGETS)
    unknown = sorted(set(selected) - set(SENSITIVITY_COEFFICIENT_TARGETS))
    if unknown:
        raise ValueError(f"Unknown physical mapping sensitivity coefficients: {unknown}")
    baseline = map_prediction_interval_to_physical(envelope, cfg)
    rows: list[dict[str, Any]] = []
    for coefficient in selected:
        baseline_coefficient = safe_float(cfg[coefficient])
        physical_field = SENSITIVITY_COEFFICIENT_TARGETS[coefficient]
        for factor in factor_values:
            perturbed_cfg = dict(cfg)
            perturbed_cfg[coefficient] = baseline_coefficient * factor
            perturbed = map_prediction_interval_to_physical(envelope, perturbed_cfg)
            for side in ("lower", "center", "upper"):
                column = f"{physical_field}_{side}"
                baseline_mean = float(
                    pd.to_numeric(baseline[column], errors="coerce").mean()
                )
                perturbed_mean = float(
                    pd.to_numeric(perturbed[column], errors="coerce").mean()
                )
                delta = perturbed_mean - baseline_mean
                rows.append({
                    "coefficient": coefficient,
                    "factor": factor,
                    "baseline_coefficient_value": baseline_coefficient,
                    "perturbed_coefficient_value": baseline_coefficient * factor,
                    "physical_field": physical_field,
                    "interval_side": side,
                    "baseline_mean_physical_value": baseline_mean,
                    "perturbed_mean_physical_value": perturbed_mean,
                    "absolute_delta": delta,
                    "relative_delta": (
                        delta / abs(baseline_mean)
                        if abs(baseline_mean) > 1e-12
                        else 0.0
                    ),
                    "rows_evaluated": int(len(envelope)),
                })
    return pd.DataFrame(rows, columns=output_columns)


def combine_portfolio_and_granular_envelopes(
    portfolio: pd.DataFrame,
    granular: pd.DataFrame,
) -> pd.DataFrame:
    """Combine controller and lane-level rows into one auditable export."""

    portfolio_rows = portfolio.copy()
    if not portfolio_rows.empty:
        portfolio_rows["scope"] = "portfolio"
        portfolio_rows["period"] = portfolio_rows.get("period", portfolio_rows["day"])
        for column in ("supplier_id", "item_id", "dst_node_id"):
            portfolio_rows[column] = ""
    granular_rows = granular.copy()
    if not granular_rows.empty:
        granular_rows["scope"] = "supplier_item_destination"
    return pd.concat([portfolio_rows, granular_rows], ignore_index=True, sort=False)


def interpolate_interval(lower: np.ndarray, center: np.ndarray, upper: np.ndarray, latent: np.ndarray) -> np.ndarray:
    """Interpolate a three-point interval with a correlated latent variable.

    ``latent`` is converted to a smooth pseudo-quantile.  Negative values sample
    the lower half of the interval; positive values sample the upper half.
    """

    quantile = np.asarray(sigmoid(latent), dtype=float)
    return np.where(
        quantile <= 0.5,
        lower + (center - lower) * (2.0 * quantile),
        center + (upper - center) * (2.0 * quantile - 1.0),
    )


CANONICAL_ACTIVITY_FILENAMES: tuple[str, ...] = (
    "production_supplier_shipments_daily.csv",
    "mrp_orders_daily.csv",
)


def discover_canonical_activity_files(
    baseline_path: Path | None,
) -> tuple[Path, ...]:
    """Find deterministic flow-evidence siblings for a canonical baseline."""

    if baseline_path is None:
        return ()
    baseline = Path(baseline_path)
    roots = (
        baseline.parent,
        baseline.parent / "data",
        baseline.parent.parent,
        baseline.parent.parent / "data",
    )
    discovered: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for filename in CANONICAL_ACTIVITY_FILENAMES:
            candidate = root / filename
            try:
                resolved = candidate.resolve()
            except (OSError, RuntimeError):
                resolved = candidate
            key = str(resolved)
            if (
                key not in seen
                and candidate.exists()
                and candidate.is_file()
                and candidate.stat().st_size > 0
            ):
                discovered.append(resolved)
                seen.add(key)
    return tuple(discovered)


def load_canonical_lane_activity(
    baseline_path: Path | None,
    *,
    horizon_days: int,
) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Load non-zero canonical shipment/order flow as standardized lane rows.

    The day and quantity semantics intentionally mirror the strict canonical
    replay contract: the source ``day`` column is bounded to ``J0..J{H-1}``,
    shipment activity uses pulled/shipped quantities, and MRP opening orders
    are excluded before testing released/planned quantities.

    ``None`` means that no usable activity evidence was supplied.  An empty
    DataFrame means that usable evidence was supplied but contains no non-zero
    flow in the requested horizon; callers must not conflate those cases.
    """

    columns = [
        "supplier_id",
        "item_id",
        "dst_node_id",
        "day",
        "qty",
        "activity_source",
        "activity_path",
        "quantity_columns",
    ]
    horizon = max(0, int(horizon_days))
    paths = discover_canonical_activity_files(baseline_path)
    metadata: dict[str, Any] = {
        "evidence_status": "not_provided",
        "baseline_path": str(baseline_path) if baseline_path else "",
        "paths_discovered": [str(path) for path in paths],
        "paths_used": [],
        "horizon_start_day": 0,
        "horizon_end_day": horizon - 1 if horizon > 0 else -1,
        "row_count": 0,
        "lane_count": 0,
        "total_evidence_qty": 0.0,
        "quantity_definition": (
            "sum_of_rowwise_max_absolute_supported_quantity; "
            "shipment_and_order_evidence_are_not_netted; "
            "opening_order_book_flows_are_excluded_as_not_risk_addressable"
        ),
        "risk_addressability_definition": (
            "nonzero_supplier_lane_release_or_nonopening_shipment_within_"
            "the_canonical_replay_horizon"
        ),
        "excluded_opening_flow_row_count": 0,
        "excluded_opening_flow_lane_count": 0,
        "excluded_opening_flow_qty": 0.0,
        "excluded_opening_flow_lanes": [],
        "errors": [],
    }
    standardized: list[pd.DataFrame] = []
    excluded_opening_rows: list[pd.DataFrame] = []
    usable_file_count = 0
    for path in paths:
        source_kind = (
            "shipment"
            if path.name == "production_supplier_shipments_daily.csv"
            else "mrp_order"
        )
        try:
            source = pd.read_csv(path)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
            metadata["errors"].append(
                {"path": str(path), "error": f"read_failed: {exc}"}
            )
            continue
        supplier_column = first_existing_column(
            source,
            [
                "src_node_id",
                "src",
                "supplier_id",
                "supplier",
                "source_node_id",
            ],
        )
        item_column = first_existing_column(
            source,
            ["item_id", "item", "material_id", "component_id"],
        )
        destination_column = first_existing_column(
            source,
            [
                "dst_node_id",
                "dst",
                "factory_id",
                "destination_node_id",
                "site_id",
            ],
        )
        day_column = first_existing_column(
            source,
            ["day", "simulation_day", "shipment_day", "order_day"],
        )
        quantity_candidates = (
            (
                "pulled_qty",
                "shipped_qty",
                "shipment_qty",
                "qty",
                "quantity",
            )
            if source_kind == "shipment"
            else (
                "release_qty",
                "planned_receipt_qty",
                "ordered_qty",
                "order_qty",
                "qty",
                "quantity",
            )
        )
        quantity_columns = [
            column for column in quantity_candidates if column in source
        ]
        missing = [
            name
            for name, column in (
                ("supplier", supplier_column),
                ("item", item_column),
                ("destination", destination_column),
                ("day", day_column),
            )
            if column is None
        ]
        if not quantity_columns:
            missing.append("quantity")
        if missing:
            metadata["errors"].append(
                {
                    "path": str(path),
                    "error": "missing_columns: " + ", ".join(missing),
                }
            )
            continue
        usable_file_count += 1
        metadata["paths_used"].append(str(path))
        work = pd.DataFrame(
            {
                "supplier_id": (
                    source[str(supplier_column)]
                    .astype("string")
                    .fillna("")
                    .str.strip()
                    .astype(str)
                ),
                "item_id": (
                    source[str(item_column)]
                    .astype("string")
                    .fillna("")
                    .str.strip()
                    .astype(str)
                ),
                "dst_node_id": (
                    source[str(destination_column)]
                    .astype("string")
                    .fillna("")
                    .str.strip()
                    .astype(str)
                ),
                "day": pd.to_numeric(
                    source[str(day_column)], errors="coerce"
                ),
            }
        )
        quantities = pd.concat(
            [
                pd.to_numeric(source[column], errors="coerce").abs()
                for column in quantity_columns
            ],
            axis=1,
        ).fillna(0.0)
        work["qty"] = quantities.max(axis=1)
        work["activity_source"] = source_kind
        work["activity_path"] = str(path)
        work["quantity_columns"] = "|".join(quantity_columns)
        valid = (
            work["supplier_id"].str.len().gt(0)
            & work["item_id"].str.len().gt(0)
            & work["dst_node_id"].str.len().gt(0)
            & work["day"].ge(0)
            & work["day"].lt(horizon)
            & work["qty"].gt(1e-9)
        )
        opening_flow = pd.Series(False, index=source.index, dtype=bool)
        if source_kind == "mrp_order" and "order_type" in source:
            opening_flow |= (
                source["order_type"]
                .astype("string")
                .fillna("")
                .str.lower()
                .str.startswith("opening_")
            )
        if source_kind == "shipment" and "transport_cost_basis" in source:
            # Opening purchase orders are seeded directly into the initial
            # pipeline and mirrored in the shipment artifact.  They bypass the
            # supplier lane execution loop where risk events are resolved, so
            # their quantity is not evidence that a SCAN event can be applied.
            opening_flow |= (
                source["transport_cost_basis"]
                .astype("string")
                .fillna("")
                .str.strip()
                .str.lower()
                .eq("opening_order_book")
            )
        excluded = valid & opening_flow
        if excluded.any():
            excluded_opening_rows.append(
                work.loc[
                    excluded,
                    [
                        "supplier_id",
                        "item_id",
                        "dst_node_id",
                        "day",
                        "qty",
                        "activity_source",
                        "activity_path",
                    ],
                ].copy()
            )
        valid &= ~opening_flow
        standardized.append(work.loc[valid, columns].copy())

    if usable_file_count <= 0:
        metadata["evidence_status"] = (
            "not_provided" if not paths else "unavailable_invalid_schema"
        )
        return None, metadata
    activity = (
        pd.concat(standardized, ignore_index=True)
        if standardized
        else pd.DataFrame(columns=columns)
    )
    excluded_opening = (
        pd.concat(excluded_opening_rows, ignore_index=True)
        if excluded_opening_rows
        else pd.DataFrame(
            columns=[
                "supplier_id",
                "item_id",
                "dst_node_id",
                "day",
                "qty",
                "activity_source",
                "activity_path",
            ]
        )
    )
    if excluded_opening.empty:
        excluded_opening_lanes: list[dict[str, Any]] = []
    else:
        excluded_opening_lanes = (
            excluded_opening.groupby(
                ["supplier_id", "item_id", "dst_node_id"],
                as_index=False,
                sort=False,
            )
            .agg(
                excluded_opening_flow_qty=("qty", "sum"),
                excluded_opening_flow_row_count=("qty", "size"),
                excluded_opening_flow_first_day=("day", "min"),
                excluded_opening_flow_last_day=("day", "max"),
            )
            .to_dict(orient="records")
        )
    metadata.update(
        {
            "evidence_status": "provided",
            "row_count": int(len(activity)),
            "lane_count": int(
                activity[
                    ["supplier_id", "item_id", "dst_node_id"]
                ].drop_duplicates().shape[0]
            )
            if not activity.empty
            else 0,
            "total_evidence_qty": float(
                pd.to_numeric(activity["qty"], errors="coerce").sum()
            )
            if not activity.empty
            else 0.0,
            "excluded_opening_flow_row_count": int(len(excluded_opening)),
            "excluded_opening_flow_lane_count": int(
                len(excluded_opening_lanes)
            ),
            "excluded_opening_flow_qty": float(
                pd.to_numeric(
                    excluded_opening["qty"], errors="coerce"
                ).sum()
            )
            if not excluded_opening.empty
            else 0.0,
            "excluded_opening_flow_lanes": excluded_opening_lanes,
        }
    )
    return activity, metadata


def _aggregate_canonical_lane_activity(
    canonical_activity: pd.DataFrame,
    *,
    horizon_days: int,
) -> pd.DataFrame:
    required = {
        "supplier_id",
        "item_id",
        "dst_node_id",
        "day",
        "qty",
    }
    if not required.issubset(canonical_activity.columns):
        return pd.DataFrame(
            columns=[
                "supplier_id",
                "item_id",
                "dst_node_id",
                "canonical_activity_qty",
                "canonical_activity_row_count",
                "canonical_activity_first_day",
                "canonical_activity_last_day",
                "canonical_activity_source",
                "canonical_activity_path",
            ]
        )
    work = canonical_activity.copy()
    for column in ("supplier_id", "item_id", "dst_node_id"):
        work[column] = (
            work[column]
            .astype("string")
            .fillna("")
            .str.strip()
            .astype(str)
        )
    work["day"] = pd.to_numeric(work["day"], errors="coerce")
    work["qty"] = pd.to_numeric(work["qty"], errors="coerce").fillna(0.0).abs()
    work = work.loc[
        work["day"].ge(0)
        & work["day"].lt(max(0, int(horizon_days)))
        & work["qty"].gt(1e-9)
        & work["supplier_id"].str.len().gt(0)
        & work["item_id"].str.len().gt(0)
        & work["dst_node_id"].str.len().gt(0)
    ].copy()
    if work.empty:
        return pd.DataFrame(
            columns=[
                "supplier_id",
                "item_id",
                "dst_node_id",
                "canonical_activity_qty",
                "canonical_activity_row_count",
                "canonical_activity_first_day",
                "canonical_activity_last_day",
                "canonical_activity_source",
                "canonical_activity_path",
            ]
        )
    if "activity_source" not in work:
        work["activity_source"] = "provided_activity"
    if "activity_path" not in work:
        work["activity_path"] = ""

    def joined(values: pd.Series) -> str:
        return "|".join(
            sorted(
                {
                    str(value)
                    for value in values
                    if str(value).strip()
                }
            )
        )

    return (
        work.groupby(
            ["supplier_id", "item_id", "dst_node_id"],
            as_index=False,
            sort=False,
        )
        .agg(
            canonical_activity_qty=("qty", "sum"),
            canonical_activity_row_count=("qty", "size"),
            canonical_activity_first_day=("day", "min"),
            canonical_activity_last_day=("day", "max"),
            canonical_activity_source=("activity_source", joined),
            canonical_activity_path=("activity_path", joined),
        )
    )


def select_top_prediction_pairs(
    prediction_path: Path | None,
    *,
    top_pairs: int = 3,
    canonical_graph: Mapping[str, Any] | None = None,
    canonical_activity: pd.DataFrame | None = None,
    canonical_activity_metadata: Mapping[str, Any] | None = None,
    canonical_horizon_days: int = 30,
) -> pd.DataFrame:
    """Select auditable supplier-item-destination lanes for canonical replay.

    The prediction PoC is scored at supplier-item-factory level.  The canonical
    engine needs exactly those identifiers in its risk-event CSV, so the replay
    retains the highest-priority distinct pairs from the latest available
    snapshot rather than applying one portfolio score to every supplier.  When
    a canonical graph is supplied, incompatible prediction rows are skipped and
    the selection is refilled with the next highest-priority graph lane.  When
    standardized canonical activity is supplied, graph-compatible lanes without
    non-zero risk-addressable shipment/order flow in the replay horizon are
    likewise rejected and deterministically refilled.  Initial order-book flows
    are reported separately because the canonical engine seeds them outside the
    supplier-risk resolution loop.  Absence of activity evidence preserves the
    graph-only fallback but is explicitly labelled as unverified.
    """

    columns = [
        "supplier_id",
        "item_id",
        "dst_node_id",
        "probability",
        "priority_score",
        "prediction_rank",
        "canonical_edge_id",
        "graph_match_status",
        "canonical_activity_evidence_status",
        "canonical_activity_qty",
        "canonical_activity_row_count",
        "canonical_activity_first_day",
        "canonical_activity_last_day",
        "canonical_activity_source",
        "canonical_activity_path",
        "canonical_activity_horizon_start_day",
        "canonical_activity_horizon_end_day",
        "selection_status",
    ]
    if prediction_path is None or not prediction_path.exists() or prediction_path.stat().st_size <= 0:
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(prediction_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame(columns=columns)
    probability_column = first_existing_column(frame, PROBABILITY_COLUMNS)
    supplier_column = first_existing_column(frame, ["supplier_id", "supplier", "src_node_id"])
    item_column = first_existing_column(frame, ["item_id", "material_id", "component_id"])
    destination_column = first_existing_column(frame, ["factory_id", "dst_node_id", "destination_node_id", "site_id"])
    if not all([probability_column, supplier_column, item_column, destination_column]):
        return pd.DataFrame(columns=columns)
    work = _aggregate_latest_snapshot(frame).copy()
    work["probability"] = pd.to_numeric(work[probability_column], errors="coerce").clip(0, 1)
    priority_column = first_existing_column(work, [
        "predicted_priority_score", "combined_proxy_risk_score", "impact_proxy_score"
    ])
    if priority_column:
        priority = pd.to_numeric(work[priority_column], errors="coerce").fillna(0.0).clip(lower=0)
    else:
        priority = work["probability"].fillna(0.0)
    # A probability floor prevents a very high structural score with negligible
    # current incident probability from dominating the immediate replay.
    work["priority_score"] = priority * (0.25 + 0.75 * work["probability"].fillna(0.0))
    work["supplier_id"] = work[supplier_column].astype(str)
    work["item_id"] = work[item_column].astype(str)
    work["dst_node_id"] = work[destination_column].astype(str)
    work = work.dropna(subset=["probability"])
    work = work.loc[
        (work["supplier_id"].str.len() > 0)
        & (work["item_id"].str.len() > 0)
        & (work["dst_node_id"].str.len() > 0)
    ]
    work = work.sort_values(
        [
            "priority_score",
            "probability",
            "supplier_id",
            "item_id",
            "dst_node_id",
        ],
        ascending=[False, False, True, True, True],
        kind="mergesort",
    )
    work = work.drop_duplicates(["supplier_id", "item_id", "dst_node_id"])
    work["prediction_rank"] = np.arange(1, len(work) + 1, dtype=int)
    requested = max(0, int(top_pairs))
    graph_filter_applied = canonical_graph is not None
    if canonical_graph is not None:
        lane_index: dict[tuple[str, str, str], str] = {}
        for edge in canonical_graph.get("edges") or []:
            if not isinstance(edge, Mapping):
                continue
            supplier_id = str(edge.get("from") or edge.get("src") or "")
            dst_node_id = str(edge.get("to") or edge.get("dst") or "")
            edge_id = str(edge.get("id") or edge.get("edge_id") or "")
            raw_items = edge.get("items")
            if isinstance(raw_items, str):
                item_ids = [raw_items]
            elif isinstance(raw_items, Sequence):
                item_ids = [str(item) for item in raw_items if str(item)]
            else:
                item_id = str(edge.get("item_id") or "")
                item_ids = [item_id] if item_id else []
            for item_id in item_ids:
                key = (supplier_id, str(item_id), dst_node_id)
                if all(key) and key not in lane_index:
                    lane_index[key] = edge_id

        keys = list(
            zip(
                work["supplier_id"].astype(str),
                work["item_id"].astype(str),
                work["dst_node_id"].astype(str),
            )
        )
        work["canonical_edge_id"] = [
            lane_index.get(key, "") for key in keys
        ]
        work["graph_match_status"] = np.where(
            [key in lane_index for key in keys],
            "matched",
            "unmatched",
        )
    else:
        work["canonical_edge_id"] = ""
        work["graph_match_status"] = "not_checked"

    activity_filter_applied = canonical_activity is not None
    activity_metadata = dict(canonical_activity_metadata or {})
    activity_evidence_status = str(
        activity_metadata.get("evidence_status")
        or ("provided" if activity_filter_applied else "not_provided")
    )
    horizon = max(0, int(canonical_horizon_days))
    excluded_opening_lane_keys = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        )
        for row in activity_metadata.get("excluded_opening_flow_lanes", [])
        if isinstance(row, Mapping)
    }
    if activity_filter_applied:
        lane_activity = _aggregate_canonical_lane_activity(
            canonical_activity,
            horizon_days=horizon,
        )
        work = work.merge(
            lane_activity,
            on=["supplier_id", "item_id", "dst_node_id"],
            how="left",
        )
        active_mask = pd.to_numeric(
            work["canonical_activity_qty"], errors="coerce"
        ).fillna(0.0).gt(1e-9)
        work_keys = list(
            zip(
                work["supplier_id"].astype(str),
                work["item_id"].astype(str),
                work["dst_node_id"].astype(str),
            )
        )
        opening_only_mask = pd.Series(
            [key in excluded_opening_lane_keys for key in work_keys],
            index=work.index,
            dtype=bool,
        ) & ~active_mask
        work["canonical_activity_evidence_status"] = np.select(
            [active_mask, opening_only_mask],
            [
                "active_nonzero_canonical_flow",
                "opening_only_flow_not_risk_addressable",
            ],
            default="no_nonzero_canonical_flow",
        )
    else:
        work["canonical_activity_evidence_status"] = (
            f"activity_unverified_{activity_evidence_status}"
        )
        for column, default in (
            ("canonical_activity_qty", np.nan),
            ("canonical_activity_row_count", 0),
            ("canonical_activity_first_day", np.nan),
            ("canonical_activity_last_day", np.nan),
            ("canonical_activity_source", ""),
            ("canonical_activity_path", ""),
        ):
            work[column] = default
    work["canonical_activity_qty"] = pd.to_numeric(
        work["canonical_activity_qty"], errors="coerce"
    )
    work["canonical_activity_row_count"] = pd.to_numeric(
        work["canonical_activity_row_count"], errors="coerce"
    ).fillna(0).astype(int)
    for column in ("canonical_activity_source", "canonical_activity_path"):
        work[column] = work[column].astype("string").fillna("").astype(str)
    work["canonical_activity_horizon_start_day"] = 0
    work["canonical_activity_horizon_end_day"] = horizon - 1

    selected_records: list[dict[str, Any]] = []
    selection_audit: list[dict[str, Any]] = []
    for row in work.to_dict(orient="records"):
        if len(selected_records) >= requested:
            break
        if graph_filter_applied and row["graph_match_status"] != "matched":
            row["selection_status"] = "rejected_graph_unmatched"
            selection_audit.append(row)
            continue
        if (
            activity_filter_applied
            and row["canonical_activity_evidence_status"]
            != "active_nonzero_canonical_flow"
        ):
            row["selection_status"] = (
                "rejected_opening_only_flow"
                if row["canonical_activity_evidence_status"]
                == "opening_only_flow_not_risk_addressable"
                else "rejected_no_nonzero_canonical_flow"
            )
            selection_audit.append(row)
            continue
        if activity_filter_applied:
            row["selection_status"] = (
                "selected_graph_compatible_active_flow"
                if graph_filter_applied
                else "selected_active_flow"
            )
        else:
            row["selection_status"] = (
                "selected_graph_compatible"
                if graph_filter_applied
                else "selected_unfiltered"
            )
        selected_records.append(row)

    selected = pd.DataFrame(selected_records)
    if selected.empty:
        result = pd.DataFrame(columns=columns)
    else:
        result = selected.reindex(columns=columns).reset_index(drop=True)

    result.attrs["selection_audit"] = [
        {column: row.get(column) for column in columns}
        for row in selection_audit
    ]
    result.attrs["graph_filter_applied"] = graph_filter_applied
    result.attrs["activity_filter_applied"] = activity_filter_applied
    result.attrs["canonical_activity_metadata"] = activity_metadata
    result.attrs["canonical_activity_evidence_status"] = (
        activity_evidence_status
    )
    result.attrs["canonical_activity_horizon_days"] = horizon
    result.attrs["graph_compatible_candidate_count"] = int(
        work["graph_match_status"].eq("matched").sum()
        if graph_filter_applied
        else len(work)
    )
    result.attrs["graph_incompatible_candidate_count"] = int(
        work["graph_match_status"].eq("unmatched").sum()
        if graph_filter_applied
        else 0
    )
    result.attrs["active_candidate_count"] = int(
        work["canonical_activity_evidence_status"]
        .eq("active_nonzero_canonical_flow")
        .sum()
        if activity_filter_applied
        else 0
    )
    result.attrs["inactive_candidate_count"] = int(
        (~work["canonical_activity_evidence_status"]
        .eq("active_nonzero_canonical_flow"))
        .sum()
        if activity_filter_applied
        else 0
    )
    result.attrs["opening_only_candidate_count"] = int(
        work["canonical_activity_evidence_status"]
        .eq("opening_only_flow_not_risk_addressable")
        .sum()
        if activity_filter_applied
        else 0
    )
    return result


def build_canonical_risk_events(
    prediction_path: Path | None,
    physical_envelope: pd.DataFrame | None,
    *,
    days: int,
    top_pairs: int = 3,
    prediction_horizon_days: int = 30,
    conservative: bool = True,
    canonical_graph: Mapping[str, Any] | None = None,
    canonical_activity: pd.DataFrame | None = None,
    canonical_activity_metadata: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Translate prediction intervals into canonical physical risk events.

    The current predictor estimates a 30-day incident probability.  Therefore
    the canonical replay applies the physical envelope only over a configurable
    validity horizon instead of extrapolating a latest snapshot over the full
    multi-year simulation.  Multipliers use the conservative interval side by
    default; the mapping ledger retains the underlying probability and selected
    lane so the assumption remains reviewable.
    """

    event_columns = [
        "event_id", "risk_type", "supplier_id", "item_id", "dst_node_id",
        "edge_id", "start_day", "end_day", "multiplier", "notes",
    ]
    pairs = select_top_prediction_pairs(
        prediction_path,
        top_pairs=top_pairs,
        canonical_graph=canonical_graph,
        canonical_activity=canonical_activity,
        canonical_activity_metadata=canonical_activity_metadata,
        canonical_horizon_days=min(
            max(0, int(days)),
            max(1, int(prediction_horizon_days)),
        ),
    )
    selection_audit = list(pairs.attrs.get("selection_audit", []))
    graph_filter_applied = bool(
        pairs.attrs.get("graph_filter_applied", False)
    )
    compatible_candidate_count = int(
        pairs.attrs.get("graph_compatible_candidate_count", len(pairs))
    )
    incompatible_candidate_count = int(
        pairs.attrs.get("graph_incompatible_candidate_count", 0)
    )
    activity_filter_applied = bool(
        pairs.attrs.get("activity_filter_applied", False)
    )
    active_candidate_count = int(
        pairs.attrs.get("active_candidate_count", 0)
    )
    inactive_candidate_count = int(
        pairs.attrs.get("inactive_candidate_count", 0)
    )
    audit_ledger_rows = [
        {
            "event_id": "",
            "supplier_id": str(row.get("supplier_id") or ""),
            "item_id": str(row.get("item_id") or ""),
            "dst_node_id": str(row.get("dst_node_id") or ""),
            "canonical_edge_id": str(
                row.get("canonical_edge_id") or ""
            ),
            "prediction_probability": safe_float(row.get("probability")),
            "pair_priority_score": safe_float(row.get("priority_score")),
            "prediction_rank": int(safe_float(row.get("prediction_rank"), 0)),
            "graph_match_status": str(
                row.get("graph_match_status") or "not_checked"
            ),
            "selection_status": str(
                row.get("selection_status") or "rejected_unselected"
            ),
            "graph_filter_applied": graph_filter_applied,
            "graph_compatible_candidate_count": compatible_candidate_count,
            "graph_incompatible_candidate_count": incompatible_candidate_count,
            "activity_filter_applied": activity_filter_applied,
            "active_candidate_count": active_candidate_count,
            "inactive_candidate_count": inactive_candidate_count,
            "canonical_activity_evidence_status": str(
                row.get("canonical_activity_evidence_status")
                or "activity_unverified_not_provided"
            ),
            "canonical_activity_qty": safe_float(
                row.get("canonical_activity_qty"), np.nan
            ),
            "canonical_activity_row_count": int(
                safe_float(row.get("canonical_activity_row_count"), 0)
            ),
            "canonical_activity_first_day": safe_float(
                row.get("canonical_activity_first_day"), np.nan
            ),
            "canonical_activity_last_day": safe_float(
                row.get("canonical_activity_last_day"), np.nan
            ),
            "canonical_activity_source": str(
                row.get("canonical_activity_source") or ""
            ),
            "canonical_activity_path": str(
                row.get("canonical_activity_path") or ""
            ),
            "canonical_activity_horizon_start_day": int(
                safe_float(
                    row.get("canonical_activity_horizon_start_day"), 0
                )
            ),
            "canonical_activity_horizon_end_day": int(
                safe_float(
                    row.get("canonical_activity_horizon_end_day"), -1
                )
            ),
            "portfolio_probability": np.nan,
            "interval_side": "",
            "risk_type": "",
            "raw_physical_value": np.nan,
            "applied_multiplier": np.nan,
            "start_day": np.nan,
            "end_day": np.nan,
            "mapping_status": (
                "not_applied_no_nonzero_canonical_flow"
                if str(row.get("selection_status"))
                == "rejected_no_nonzero_canonical_flow"
                else "not_applied_opening_only_flow_not_risk_addressable"
                if str(row.get("selection_status"))
                == "rejected_opening_only_flow"
                else "not_applied_graph_lane_unmatched"
                if str(row.get("selection_status"))
                == "rejected_graph_unmatched"
                else "not_applied_unselected_prediction_lane"
            ),
            "physical_envelope_scope": "not_mapped",
        }
        for row in selection_audit
    ]
    if (
        pairs.empty
        or physical_envelope is None
        or physical_envelope.empty
        or days <= 0
    ):
        return (
            pd.DataFrame(columns=event_columns),
            pd.DataFrame(audit_ledger_rows),
        )
    horizon = min(int(days), max(1, int(prediction_horizon_days)), len(physical_envelope))
    suffix = "upper" if conservative else "center"
    probability_column = f"risk_{suffix}"
    portfolio_window = physical_envelope.copy()
    if "scope" in portfolio_window:
        selected_portfolio = portfolio_window.loc[
            portfolio_window["scope"].astype(str) == "portfolio"
        ]
        if not selected_portfolio.empty:
            portfolio_window = selected_portfolio
    if "day" in portfolio_window:
        portfolio_window = portfolio_window.loc[
            pd.to_numeric(portfolio_window["day"], errors="coerce").between(
                0, horizon - 1
            )
        ]
    portfolio_window = portfolio_window.iloc[:horizon]
    events: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    for pair_index, pair in pairs.iterrows():
        window = pd.DataFrame()
        required_pair_columns = {"supplier_id", "item_id", "dst_node_id"}
        if required_pair_columns.issubset(physical_envelope.columns):
            pair_mask = (
                (physical_envelope["supplier_id"].astype(str) == str(pair["supplier_id"]))
                & (physical_envelope["item_id"].astype(str) == str(pair["item_id"]))
                & (physical_envelope["dst_node_id"].astype(str) == str(pair["dst_node_id"]))
            )
            if "scope" in physical_envelope:
                pair_mask &= (
                    physical_envelope["scope"].astype(str)
                    == "supplier_item_destination"
                )
            window = physical_envelope.loc[pair_mask].copy()
            if "day" in window:
                window = window.loc[
                    pd.to_numeric(window["day"], errors="coerce").between(
                        0, horizon - 1
                    )
                ]
        pair_specific = not window.empty
        if not pair_specific:
            window = portfolio_window
        if window.empty:
            continue
        probability = float(
            pd.to_numeric(window[probability_column], errors="coerce").mean()
        )
        values = {
            "availability": float(
                pd.to_numeric(
                    window[f"availability_multiplier_{suffix}"], errors="coerce"
                ).min()
            ),
            "capacity": float(
                pd.to_numeric(
                    window[f"capacity_multiplier_{suffix}"], errors="coerce"
                ).min()
            ),
            "lead_time_extra_days": float(
                pd.to_numeric(
                    window[f"lead_time_extra_days_{suffix}"], errors="coerce"
                ).max()
            ),
            "quality_yield": float(
                pd.to_numeric(
                    window[f"quality_yield_multiplier_{suffix}"], errors="coerce"
                ).min()
            ),
            "purchase_cost": float(
                pd.to_numeric(
                    window[f"purchase_cost_multiplier_{suffix}"],
                    errors="coerce",
                ).max()
            ),
            "transport_cost": float(
                pd.to_numeric(
                    window[f"transport_cost_multiplier_{suffix}"],
                    errors="coerce",
                ).max()
            ),
        }
        pair_scale = (
            1.0
            if pair_specific
            else clamp(
                0.65 + 0.35 * safe_float(pair["probability"], probability),
                0.50,
                1.0,
            )
        )
        for risk_type, raw_value in values.items():
            if risk_type in {"availability", "capacity", "quality_yield"}:
                multiplier = 1.0 - pair_scale * (1.0 - raw_value)
                if multiplier >= 0.995:
                    continue
            elif risk_type in {"purchase_cost", "transport_cost"}:
                # Cost fields are multiplicative factors centred on one.
                # Scale only their increase, never the full raw multiplier.
                multiplier = 1.0 + pair_scale * (raw_value - 1.0)
                if multiplier <= 1.005:
                    continue
            else:
                multiplier = pair_scale * raw_value
                if multiplier <= 0.05:
                    continue
            event_id = f"SCAN_PRED_{pair_index + 1:02d}_{risk_type.upper()}"
            note = (
                f"SCAN operational prediction envelope -> physical {risk_type}; "
                f"portfolio_{suffix}_probability={probability:.4f}; "
                f"pair_probability={safe_float(pair['probability']):.4f}; "
                f"validity_horizon={horizon}d"
            )
            events.append({
                "event_id": event_id,
                "risk_type": risk_type,
                "supplier_id": str(pair["supplier_id"]),
                "item_id": str(pair["item_id"]),
                "dst_node_id": str(pair["dst_node_id"]),
                "edge_id": str(pair.get("canonical_edge_id") or ""),
                "start_day": 0,
                "end_day": horizon - 1,
                "multiplier": round(float(multiplier), 6),
                "notes": note,
            })
            ledger_rows.append({
                "event_id": event_id,
                "supplier_id": str(pair["supplier_id"]),
                "item_id": str(pair["item_id"]),
                "dst_node_id": str(pair["dst_node_id"]),
                "canonical_edge_id": str(
                    pair.get("canonical_edge_id") or ""
                ),
                "prediction_probability": safe_float(pair["probability"]),
                "pair_priority_score": safe_float(pair["priority_score"]),
                "prediction_rank": int(
                    safe_float(pair.get("prediction_rank"), pair_index + 1)
                ),
                "graph_match_status": str(
                    pair.get("graph_match_status") or "not_checked"
                ),
                "selection_status": str(
                    pair.get("selection_status") or "selected_unfiltered"
                ),
                "graph_filter_applied": graph_filter_applied,
                "graph_compatible_candidate_count": compatible_candidate_count,
                "graph_incompatible_candidate_count": incompatible_candidate_count,
                "activity_filter_applied": activity_filter_applied,
                "active_candidate_count": active_candidate_count,
                "inactive_candidate_count": inactive_candidate_count,
                "canonical_activity_evidence_status": str(
                    pair.get("canonical_activity_evidence_status")
                    or "activity_unverified_not_provided"
                ),
                "canonical_activity_qty": safe_float(
                    pair.get("canonical_activity_qty"), np.nan
                ),
                "canonical_activity_row_count": int(
                    safe_float(
                        pair.get("canonical_activity_row_count"), 0
                    )
                ),
                "canonical_activity_first_day": safe_float(
                    pair.get("canonical_activity_first_day"), np.nan
                ),
                "canonical_activity_last_day": safe_float(
                    pair.get("canonical_activity_last_day"), np.nan
                ),
                "canonical_activity_source": str(
                    pair.get("canonical_activity_source") or ""
                ),
                "canonical_activity_path": str(
                    pair.get("canonical_activity_path") or ""
                ),
                "canonical_activity_horizon_start_day": int(
                    safe_float(
                        pair.get(
                            "canonical_activity_horizon_start_day"
                        ),
                        0,
                    )
                ),
                "canonical_activity_horizon_end_day": int(
                    safe_float(
                        pair.get("canonical_activity_horizon_end_day"),
                        -1,
                    )
                ),
                "portfolio_probability": probability,
                "interval_side": suffix,
                "risk_type": risk_type,
                "raw_physical_value": raw_value,
                "applied_multiplier": multiplier,
                "start_day": 0,
                "end_day": horizon - 1,
                "mapping_status": "research_mapping_requires_industrial_calibration",
                "physical_envelope_scope": (
                    "supplier_item_destination" if pair_specific else "portfolio_proxy"
                ),
            })
    return (
        pd.DataFrame(events, columns=event_columns),
        pd.DataFrame([*audit_ledger_rows, *ledger_rows]),
    )
