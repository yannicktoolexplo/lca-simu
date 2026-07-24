from __future__ import annotations

"""Prediction-interval to physical-risk mapping for the SCAN end-2026 PoC.

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
    nominal_coverage: float
    residual_quantile: float
    rows_used: int
    pairs_used: int


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
}


PROBABILITY_COLUMNS: tuple[str, ...] = (
    "predicted_incident_probability_30d",
    "predicted_probability",
    "predicted_risk_probability",
    "risk_probability",
    "predicted_risk",
    "probability",
    "p_risk",
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


def _conformal_residual_quantile(calibration_path: Path | None, alpha: float) -> tuple[float, int]:
    if calibration_path is None:
        return float("nan"), 0
    try:
        frame = pd.read_csv(calibration_path)
    except (OSError, pd.errors.ParserError):
        return float("nan"), 0
    probability_column = first_existing_column(frame, PROBABILITY_COLUMNS)
    truth_column = first_existing_column(frame, [
        "incident_next_30d", "true_incident", "incident", "label", "target", "y_true"
    ])
    if probability_column is None or truth_column is None:
        return float("nan"), 0
    probability = pd.to_numeric(frame[probability_column], errors="coerce")
    truth = pd.to_numeric(frame[truth_column], errors="coerce")
    valid = probability.notna() & truth.notna()
    if not valid.any():
        return float("nan"), 0
    residuals = (truth[valid].clip(0, 1) - probability[valid].clip(0, 1)).abs().to_numpy(dtype=float)
    # Finite-sample split-conformal quantile.  A shrinkage cap is intentionally
    # applied because binary residuals alone can otherwise produce the trivial
    # [0, 1] interval on small calibration sets.  The cap is reported explicitly.
    rank = int(np.ceil((len(residuals) + 1) * (1.0 - alpha))) - 1
    rank = min(max(rank, 0), len(residuals) - 1)
    quantile = float(np.sort(residuals)[rank])
    return quantile, int(len(residuals))


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


def build_prediction_interval_envelope(
    prediction_path: Path | None,
    days: int,
    *,
    fallback_center: np.ndarray | Sequence[float] | None = None,
    fallback_uncertainty: np.ndarray | Sequence[float] | None = None,
    mapping_config: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, PredictionIntervalMetadata]:
    """Create one daily portfolio-level prediction interval.

    The current prediction POC is supplier-item-site based and usually contains
    weekly snapshots rather than a daily interval.  For the reduced-order risk
    control bench we aggregate the most recent snapshot with a priority-weighted
    upper-tail rule, then repeat it over the requested horizon.  If dated daily or
    weekly observations are provided, the function interpolates them instead.
    """

    cfg = {**DEFAULT_PHYSICAL_MAPPING, **dict(mapping_config or {})}
    alpha = clamp(safe_float(cfg.get("conformal_alpha"), 0.10), 0.01, 0.49)
    nominal_coverage = 1.0 - alpha
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

    calibration_path = _discover_prediction_calibration(prediction_path)
    residual_q, residual_rows = _conformal_residual_quantile(calibration_path, alpha)
    residual_half_width = clamp(
        0.50 * residual_q if np.isfinite(residual_q) else float(np.nanmedian(fallback_width_array)),
        minimum_width,
        maximum_width,
    )

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
            None,
            str(calibration_path) if calibration_path else None,
            "fallback_from_existing_risk_series",
            nominal_coverage,
            residual_half_width,
            residual_rows,
            0,
        )

    frame = pd.read_csv(prediction_path)
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
            "fallback_probability_column_missing",
            nominal_coverage,
            residual_half_width,
            residual_rows,
            0,
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
    else:
        row_penalty = _numeric(work, ["uncertainty_penalty"], 0.0).clip(0, 1)
        row_width = np.clip(residual_half_width + 0.12 * row_penalty, minimum_width, maximum_width)
        work["_lower"] = (work["_probability"] - row_width).clip(0, 1)
        work["_upper"] = (work["_probability"] + row_width).clip(0, 1)
        interval_method = "residual_and_uncertainty_penalty_interval"

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
    # A latest 30-day supplier forecast must not be extrapolated as certain over
    # a six-month or multi-year simulation.  When only one prediction instant is
    # available, transition after the validity horizon toward a broad long-term
    # prior.  This represents missing future information rather than assuming
    # either permanent crisis or permanent safety.
    if int(daily["day"].nunique()) <= 1 and days > 1:
        validity = max(1.0, safe_float(cfg.get("forecast_validity_days"), 30.0))
        decay = max(1.0, safe_float(cfg.get("forecast_decay_days"), 30.0))
        prior_center = clamp(safe_float(cfg.get("long_horizon_prior_center"), 0.12), 0.01, 0.99)
        prior_width = clamp(
            safe_float(cfg.get("long_horizon_prior_half_width"), 0.25),
            minimum_width, maximum_width,
        )
        blend = np.clip((envelope["day"].to_numpy(dtype=float) - validity) / decay, 0.0, 1.0)
        current_center = envelope["risk_center"].to_numpy(dtype=float)
        current_lower = envelope["risk_lower"].to_numpy(dtype=float)
        current_upper = envelope["risk_upper"].to_numpy(dtype=float)
        envelope["risk_center"] = (1.0 - blend) * current_center + blend * prior_center
        envelope["risk_lower"] = (1.0 - blend) * current_lower + blend * max(0.0, prior_center - prior_width)
        envelope["risk_upper"] = (1.0 - blend) * current_upper + blend * min(1.0, prior_center + prior_width)
        envelope["priority_score"] = (1.0 - blend) * envelope["priority_score"].to_numpy(dtype=float) + blend * prior_center
        interval_method = f"{interval_method}_with_forecast_horizon_decay"
    envelope["source_pairs"] = envelope["source_pairs"].round().fillna(0).astype(int)
    envelope["risk_lower"] = envelope["risk_lower"].clip(0, 1)
    envelope["risk_center"] = envelope["risk_center"].clip(0.01, 0.99)
    envelope["risk_upper"] = envelope["risk_upper"].clip(0, 1)
    envelope["risk_lower"] = np.minimum(envelope["risk_lower"], envelope["risk_center"])
    envelope["risk_upper"] = np.maximum(envelope["risk_upper"], envelope["risk_center"])
    return envelope, PredictionIntervalMetadata(
        str(prediction_path),
        str(calibration_path) if calibration_path else None,
        interval_method,
        nominal_coverage,
        residual_half_width,
        residual_rows,
        int(work[[c for c in ["supplier_id", "item_id", "factory_id"] if c in work]].drop_duplicates().shape[0])
        if any(c in work for c in ["supplier_id", "item_id", "factory_id"]) else int(len(work)),
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


def select_top_prediction_pairs(
    prediction_path: Path | None,
    *,
    top_pairs: int = 3,
) -> pd.DataFrame:
    """Select auditable supplier-item-destination lanes for canonical replay.

    The prediction PoC is scored at supplier-item-factory level.  The canonical
    engine needs exactly those identifiers in its risk-event CSV, so the replay
    retains the highest-priority distinct pairs from the latest available
    snapshot rather than applying one portfolio score to every supplier.
    """

    columns = ["supplier_id", "item_id", "dst_node_id", "probability", "priority_score"]
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
    work = work.sort_values(["priority_score", "probability"], ascending=False)
    work = work.drop_duplicates(["supplier_id", "item_id", "dst_node_id"])
    return work[columns].head(max(0, int(top_pairs))).reset_index(drop=True)


def build_canonical_risk_events(
    prediction_path: Path | None,
    physical_envelope: pd.DataFrame | None,
    *,
    days: int,
    top_pairs: int = 3,
    prediction_horizon_days: int = 30,
    conservative: bool = True,
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
    pairs = select_top_prediction_pairs(prediction_path, top_pairs=top_pairs)
    if pairs.empty or physical_envelope is None or physical_envelope.empty or days <= 0:
        return pd.DataFrame(columns=event_columns), pd.DataFrame()
    horizon = min(int(days), max(1, int(prediction_horizon_days)), len(physical_envelope))
    window = physical_envelope.iloc[:horizon]
    suffix = "upper" if conservative else "center"
    probability_column = f"risk_{suffix}"
    probability = float(pd.to_numeric(window[probability_column], errors="coerce").mean())
    values = {
        "availability": float(pd.to_numeric(window[f"availability_multiplier_{suffix}"], errors="coerce").min()),
        "capacity": float(pd.to_numeric(window[f"capacity_multiplier_{suffix}"], errors="coerce").min()),
        "lead_time_extra_days": float(pd.to_numeric(window[f"lead_time_extra_days_{suffix}"], errors="coerce").max()),
        "quality_yield": float(pd.to_numeric(window[f"quality_yield_multiplier_{suffix}"], errors="coerce").min()),
    }
    events: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    for pair_index, pair in pairs.iterrows():
        pair_scale = clamp(0.65 + 0.35 * safe_float(pair["probability"], probability), 0.50, 1.0)
        for risk_type, raw_value in values.items():
            if risk_type in {"availability", "capacity", "quality_yield"}:
                multiplier = 1.0 - pair_scale * (1.0 - raw_value)
                if multiplier >= 0.995:
                    continue
            else:
                multiplier = pair_scale * raw_value
                if multiplier <= 0.05:
                    continue
            event_id = f"SCAN_PRED_{pair_index + 1:02d}_{risk_type.upper()}"
            note = (
                f"SCAN prediction interval -> physical {risk_type}; "
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
                "edge_id": "",
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
                "prediction_probability": safe_float(pair["probability"]),
                "pair_priority_score": safe_float(pair["priority_score"]),
                "portfolio_probability": probability,
                "interval_side": suffix,
                "risk_type": risk_type,
                "raw_physical_value": raw_value,
                "applied_multiplier": multiplier,
                "start_day": 0,
                "end_day": horizon - 1,
                "mapping_status": "research_mapping_requires_industrial_calibration",
            })
    return pd.DataFrame(events, columns=event_columns), pd.DataFrame(ledger_rows)
