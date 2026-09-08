from __future__ import annotations

"""Calibration of state-dependent regimes on canonical etudecas trajectories."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .core import (
    REGIME_CLASSIFICATION_RULES,
    REGIME_VARIABLES_USED,
    RunContext,
    clamp,
    classify_regime_signals,
    deep_merge,
    first_existing_column,
    optional_boolean,
    safe_float,
)


@dataclass(frozen=True)
class CalibrationArtifacts:
    frame: pd.DataFrame
    evidence: pd.DataFrame
    config: dict[str, Any]
    metadata: dict[str, Any]


VALIDATED_REGIMES: tuple[str, ...] = (
    "NOMINAL",
    "MATERIAL_TENSION",
    "CAPACITY_SATURATION",
    "SUPPLIER_STRESS",
    "OSCILLATORY",
    "CRISIS",
    "RECOVERY",
    "POST_CRISIS_OVERSTOCK",
)


@dataclass(frozen=True)
class RegimeAnnotationArtifacts:
    """Normalized row-level annotations and their daily portfolio vote."""

    rows: pd.DataFrame
    daily: pd.DataFrame
    metadata: dict[str, Any]


def _required_annotation_column(
    frame: pd.DataFrame,
    aliases: tuple[str, ...],
    label: str,
) -> str:
    column = first_existing_column(frame, aliases)
    if column is None:
        accepted = " or ".join(f"`{name}`" for name in aliases)
        raise ValueError(
            f"Regime annotation CSV is missing required {label} column ({accepted})."
        )
    return column


def _normalize_annotation_days(
    frame: pd.DataFrame,
    time_column: str,
    period_origin: str | pd.Timestamp | None = None,
) -> tuple[pd.Series, str]:
    """Normalize a numeric day/period or dated period to integer simulation days."""

    raw = frame[time_column]
    numeric = pd.to_numeric(raw, errors="coerce")
    if numeric.notna().all():
        fractional = (numeric - np.floor(numeric)).abs() > 1e-9
        if fractional.any():
            bad_rows = frame.index[fractional].tolist()
            raise ValueError(
                "Regime annotation day/period values must be integer simulation "
                f"days; invalid rows={bad_rows}."
            )
        if (numeric < 0).any():
            bad_rows = frame.index[numeric < 0].tolist()
            raise ValueError(
                f"Regime annotation day/period values must be non-negative; invalid rows={bad_rows}."
            )
        return numeric.astype(int), "integer_simulation_day"

    if time_column.lower() != "period":
        bad_rows = frame.index[numeric.isna()].tolist()
        raise ValueError(
            f"Regime annotation `day` values must be numeric; invalid rows={bad_rows}."
        )
    timestamps = pd.to_datetime(raw, errors="coerce")
    if timestamps.isna().any():
        bad_rows = frame.index[timestamps.isna()].tolist()
        raise ValueError(
            "Regime annotation `period` must contain integer simulation days or "
            f"parseable dates; invalid rows={bad_rows}."
        )
    if period_origin is None:
        raise ValueError(
            "Dated regime annotation `period` values require an explicit "
            "baseline calendar origin. Use integer simulation days or expose a "
            "coherent baseline calendar column; the minimum annotation date is "
            "never treated as simulation day zero."
        )
    origin = pd.to_datetime(period_origin, errors="coerce")
    if pd.isna(origin):
        raise ValueError(
            f"Baseline period origin is not parseable as a date: {period_origin!r}."
        )
    mapping = f"calendar_day_offset_from_baseline_origin:{origin.date().isoformat()}"
    day = (timestamps - origin).dt.days.astype(int)
    if (day < 0).any():
        bad_rows = frame.index[day < 0].tolist()
        raise ValueError(
            "Regime annotation periods precede the baseline period origin; "
            f"invalid rows={bad_rows}."
        )
    return day, mapping


def _aggregate_annotation_votes(rows: pd.DataFrame) -> pd.DataFrame:
    """Aggregate site-item expert rows to one transparent confidence-weighted daily vote."""

    output_rows: list[dict[str, Any]] = []
    for day, group in rows.groupby("day", sort=True):
        vote_weights = (
            group.groupby("validated_regime", sort=True)["expert_confidence"]
            .sum()
            .sort_index()
        )
        total_weight = float(vote_weights.sum())
        maximum_weight = float(vote_weights.max()) if not vote_weights.empty else 0.0
        winners = (
            vote_weights.index[
                np.isclose(vote_weights.to_numpy(dtype=float), maximum_weight)
            ].tolist()
            if maximum_weight > 0.0
            else []
        )
        tied = maximum_weight > 0.0 and len(winners) > 1
        winner = winners[0] if len(winners) == 1 else None
        winner_rows = (
            group.loc[group["validated_regime"] == winner]
            if winner is not None
            else group.iloc[0:0]
        )
        comments = [
            value
            for value in dict.fromkeys(
                str(value).strip() for value in group["comment"] if str(value).strip()
            )
        ]
        output_rows.append({
            "day": int(day),
            "business_validated_regime": winner,
            "business_annotation_count": int(len(group)),
            "business_distinct_regime_count": int(group["validated_regime"].nunique()),
            "business_vote_weight": maximum_weight,
            "business_total_vote_weight": total_weight,
            "business_vote_share": maximum_weight / total_weight if total_weight > 0.0 else 0.0,
            "business_vote_weights_by_regime": "|".join(
                f"{regime}:{float(weight):.12g}"
                for regime, weight in vote_weights.items()
            ),
            "business_expert_confidence_mean": (
                float(winner_rows["expert_confidence"].mean())
                if not winner_rows.empty
                else np.nan
            ),
            "business_annotation_conflict": int(group["validated_regime"].nunique() > 1),
            "business_vote_tie": int(tied),
            "business_zero_weight_vote": int(total_weight <= 0.0),
            "business_annotation_sites": "|".join(sorted(group["site"].unique())),
            "business_annotation_items": "|".join(sorted(group["item"].unique())),
            "business_annotation_comments": " | ".join(comments),
        })
    return pd.DataFrame(output_rows)


def load_regime_annotations(
    path: Path | None,
    *,
    period_origin: str | pd.Timestamp | None = None,
) -> RegimeAnnotationArtifacts:
    """Load and strictly validate optional expert regime annotations.

    Required fields are a numeric ``day`` or numeric/dated ``period``, ``site``,
    ``item`` or ``article``, ``validated_regime``, ``expert_confidence`` in
    ``[0, 1]``, and ``comment``. Regime values are normalized to uppercase and
    must match exactly one of the eight supported SCAN regimes.
    """

    empty_daily = pd.DataFrame(columns=[
        "day",
        "business_validated_regime",
        "business_annotation_count",
        "business_distinct_regime_count",
        "business_vote_weight",
        "business_total_vote_weight",
        "business_vote_share",
        "business_vote_weights_by_regime",
        "business_expert_confidence_mean",
        "business_annotation_conflict",
        "business_vote_tie",
        "business_zero_weight_vote",
        "business_annotation_sites",
        "business_annotation_items",
        "business_annotation_comments",
    ])
    if path is None:
        return RegimeAnnotationArtifacts(
            pd.DataFrame(),
            empty_daily,
            {
                "status": "not_provided",
                "schema_validation_status": "not_run",
                "source_path": None,
                "label_provenance": "pseudo_labels_only",
                "annotation_rows": 0,
                "annotated_days": 0,
                "conflict_day_count": 0,
                "tie_day_count": 0,
                "zero_weight_day_count": 0,
                "time_column": None,
                "time_mapping": None,
                "baseline_period_origin": (
                    str(period_origin) if period_origin is not None else None
                ),
            },
        )
    annotation_path = Path(path).resolve()
    if not annotation_path.exists() or not annotation_path.is_file():
        raise FileNotFoundError(
            f"Regime annotation CSV does not exist: {annotation_path}"
        )
    try:
        source = pd.read_csv(annotation_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"Unable to read regime annotation CSV `{annotation_path}`: {exc}"
        ) from exc

    time_column = first_existing_column(source, ["day", "period"])
    if time_column is None:
        raise ValueError(
            "Regime annotation CSV is missing required time column (`day` or `period`)."
        )
    site_column = _required_annotation_column(source, ("site", "site_id"), "site")
    item_column = _required_annotation_column(
        source, ("item", "article", "item_id", "article_id"), "item/article"
    )
    regime_column = _required_annotation_column(
        source, ("validated_regime",), "validated regime"
    )
    confidence_column = _required_annotation_column(
        source, ("expert_confidence",), "expert confidence"
    )
    comment_column = _required_annotation_column(source, ("comment",), "comment")

    if source.empty:
        metadata = {
            "status": "provided_empty",
            "schema_validation_status": "passed",
            "source_path": str(annotation_path),
            "label_provenance": "pseudo_labels_only",
            "annotation_rows": 0,
            "annotated_days": 0,
            "conflict_day_count": 0,
            "tie_day_count": 0,
            "zero_weight_day_count": 0,
            "time_column": time_column,
            "time_mapping": "not_applicable_empty_file",
            "baseline_period_origin": (
                str(period_origin) if period_origin is not None else None
            ),
        }
        return RegimeAnnotationArtifacts(pd.DataFrame(), empty_daily, metadata)

    day, time_mapping = _normalize_annotation_days(
        source, time_column, period_origin=period_origin
    )
    site = source[site_column].astype("string").fillna("").str.strip()
    item = source[item_column].astype("string").fillna("").str.strip()
    empty_identity = (site == "") | (item == "")
    if empty_identity.any():
        bad_rows = source.index[empty_identity].tolist()
        raise ValueError(
            f"Regime annotation site and item/article must be non-empty; invalid rows={bad_rows}."
        )

    regime = source[regime_column].astype("string").fillna("").str.strip().str.upper()
    invalid_regime = ~regime.isin(VALIDATED_REGIMES)
    if invalid_regime.any():
        invalid_values = sorted(regime.loc[invalid_regime].unique().tolist())
        bad_rows = source.index[invalid_regime].tolist()
        raise ValueError(
            "Regime annotation `validated_regime` must be one of "
            f"{list(VALIDATED_REGIMES)}; invalid values={invalid_values}, rows={bad_rows}."
        )

    confidence = pd.to_numeric(source[confidence_column], errors="coerce")
    invalid_confidence = confidence.isna() | (confidence < 0.0) | (confidence > 1.0)
    if invalid_confidence.any():
        bad_rows = source.index[invalid_confidence].tolist()
        raise ValueError(
            "Regime annotation `expert_confidence` must be numeric and within "
            f"[0, 1]; invalid rows={bad_rows}."
        )

    normalized = pd.DataFrame({
        "day": day,
        "site": site.astype(str),
        "item": item.astype(str),
        "validated_regime": regime.astype(str),
        "expert_confidence": confidence.astype(float),
        "comment": source[comment_column].astype("string").fillna("").astype(str),
    })
    daily = _aggregate_annotation_votes(normalized)
    metadata = {
        "status": "annotations_loaded",
        "schema_validation_status": "passed",
        "source_path": str(annotation_path),
        "label_provenance": "business_annotations_with_pseudo_fallback",
        "annotation_rows": int(len(normalized)),
        "annotated_days": int(normalized["day"].nunique()),
        "conflict_day_count": int(daily["business_annotation_conflict"].sum()),
        "tie_day_count": int(daily["business_vote_tie"].sum()),
        "zero_weight_day_count": int(daily["business_zero_weight_vote"].sum()),
        "time_column": time_column,
        "time_mapping": time_mapping,
        "baseline_period_origin": (
            str(period_origin) if period_origin is not None else None
        ),
        "site_column": site_column,
        "item_column": item_column,
        "regime_column": regime_column,
        "confidence_column": confidence_column,
        "comment_column": comment_column,
        "annotated_site_count": int(normalized["site"].nunique()),
        "annotated_item_count": int(normalized["item"].nunique()),
    }
    return RegimeAnnotationArtifacts(normalized, daily, metadata)


def apply_regime_annotations(
    frame: pd.DataFrame,
    annotations: RegimeAnnotationArtifacts,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Overlay resolved business votes while preserving every pseudo-label.

    A business label replaces the calibrated pseudo-label only when the daily
    confidence-weighted vote has one positive-weight winner. Tied or zero-weight
    votes remain visible in the annotation columns and deliberately fall back to
    the pseudo-label.
    """

    if "day" not in frame.columns or "calibrated_regime" not in frame.columns:
        raise ValueError(
            "Regime annotation overlay requires `day` and `calibrated_regime` columns."
        )

    result = frame.copy()
    result["pseudo_regime"] = result["calibrated_regime"].astype("string")
    daily = annotations.daily.copy()
    if daily.empty:
        for column in daily.columns:
            if column != "day":
                result[column] = np.nan
    else:
        result = result.merge(daily, on="day", how="left", validate="many_to_one")

    integer_columns = (
        "business_annotation_count",
        "business_distinct_regime_count",
        "business_annotation_conflict",
        "business_vote_tie",
        "business_zero_weight_vote",
    )
    for column in integer_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    for column in (
        "business_vote_weight",
        "business_total_vote_weight",
        "business_vote_share",
    ):
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result["business_expert_confidence_mean"] = pd.to_numeric(
        result["business_expert_confidence_mean"], errors="coerce"
    )
    for column in (
        "business_annotation_sites",
        "business_annotation_items",
        "business_annotation_comments",
        "business_vote_weights_by_regime",
    ):
        result[column] = result[column].astype("string").fillna("").astype(str)

    business_label = result["business_validated_regime"].isin(VALIDATED_REGIMES)
    result["regime_label_source"] = np.where(
        business_label, "business_annotation", "pseudo_label"
    )
    result["calibrated_regime"] = (
        result["business_validated_regime"]
        .where(business_label, result["pseudo_regime"])
        .astype("string")
    )

    frame_days = int(result["day"].nunique())
    source_days = set(pd.to_numeric(daily.get("day", pd.Series(dtype=int))).astype(int))
    frame_day_values = set(pd.to_numeric(result["day"], errors="coerce").dropna().astype(int))
    matched_day_values = source_days & frame_day_values
    matched_annotations = result["day"].isin(matched_day_values)
    matched_daily = result.loc[
        matched_annotations,
        [
            "day",
            "business_annotation_conflict",
            "business_vote_tie",
            "business_zero_weight_vote",
        ],
    ].drop_duplicates("day")
    business_label_days = int(result.loc[business_label, "day"].nunique())
    matched_annotation_days = int(len(matched_day_values))
    pseudo_label_days = max(0, frame_days - business_label_days)

    metadata = dict(annotations.metadata)
    metadata.update({
        "source_conflict_day_count": int(metadata.get("conflict_day_count", 0)),
        "source_tie_day_count": int(metadata.get("tie_day_count", 0)),
        "source_zero_weight_day_count": int(metadata.get("zero_weight_day_count", 0)),
        "frame_days": frame_days,
        "matched_annotation_days": matched_annotation_days,
        "unmatched_annotation_days": int(len(source_days - frame_day_values)),
        "business_label_days": business_label_days,
        "pseudo_label_days": pseudo_label_days,
        "annotation_coverage_fraction": (
            matched_annotation_days / frame_days if frame_days else 0.0
        ),
        "business_label_coverage_fraction": (
            business_label_days / frame_days if frame_days else 0.0
        ),
        "pseudo_label_coverage_fraction": (
            pseudo_label_days / frame_days if frame_days else 0.0
        ),
        "conflict_day_count": int(
            matched_daily["business_annotation_conflict"].sum()
        ),
        "tie_day_count": int(
            matched_daily["business_vote_tie"].sum()
        ),
        "zero_weight_day_count": int(
            matched_daily["business_zero_weight_vote"].sum()
        ),
    })
    if business_label_days:
        metadata["label_provenance"] = "business_annotations_with_pseudo_fallback"
    elif matched_annotation_days:
        metadata["label_provenance"] = "annotations_without_resolved_business_vote"
    else:
        metadata["label_provenance"] = "pseudo_labels_only"
    return result, metadata


SIBLING_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "constraints": (
        "production_constraint_daily.csv",
        "data/production_constraint_daily.csv",
    ),
    "supplier_capacity": (
        "production_supplier_capacity_daily.csv",
        "data/production_supplier_capacity_daily.csv",
        "supplier_capacity_daily.csv",
        "data/supplier_capacity_daily.csv",
    ),
    "state_risk_events": (
        "supplier_state_dependent_risk_events.csv",
        "data/supplier_state_dependent_risk_events.csv",
        "supplier_state_risk_events.csv",
        "data/supplier_state_risk_events.csv",
    ),
    "factory_nervousness": (
        "production_factory_nervousness.csv",
        "data/production_factory_nervousness.csv",
        "factory_nervousness_daily.csv",
        "data/factory_nervousness_daily.csv",
    ),
    "supplier_risk_applied": (
        "supplier_risk_events_applied_daily.csv",
        "data/supplier_risk_events_applied_daily.csv",
        "supplier_risk_applied_daily.csv",
        "data/supplier_risk_applied_daily.csv",
    ),
    "input_stocks": (
        "production_input_stocks_daily.csv",
        "data/production_input_stocks_daily.csv",
    ),
    "input_consumption": (
        "production_input_consumption_daily.csv",
        "data/production_input_consumption_daily.csv",
    ),
    "demand_service": (
        "production_demand_service_daily.csv",
        "data/production_demand_service_daily.csv",
    ),
}


def _find_sibling(baseline_path: Path | None, candidates: tuple[str, ...]) -> Path | None:
    if baseline_path is None:
        return None
    roots = [baseline_path.parent, baseline_path.parent.parent]
    for root in roots:
        for relative in candidates:
            candidate = root / relative
            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate
    return None


def discover_calibration_files(context: RunContext) -> dict[str, Path]:
    baseline = Path(context.baseline_path) if context.baseline_path else None
    result: dict[str, Path] = {}
    for key, candidates in SIBLING_ARTIFACTS.items():
        path = _find_sibling(baseline, candidates)
        if path is not None:
            result[key] = path
    return result


def _read_optional(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def _numeric(frame: pd.DataFrame, names: list[str], default: float = 0.0) -> pd.Series:
    column = first_existing_column(frame, names)
    if column is None:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _aggregate_by_day(frame: pd.DataFrame, value: pd.Series, how: str = "max") -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    day_column = first_existing_column(frame, ["day", "sim_day", "day_index"])
    if day_column is None:
        return pd.Series(dtype=float)
    day = pd.to_numeric(frame[day_column], errors="coerce")
    work = pd.DataFrame({"day": day, "value": value}).dropna(subset=["day"])
    if work.empty:
        return pd.Series(dtype=float)
    work["day"] = work["day"].astype(int)
    grouped = work.groupby("day")["value"]
    if how == "sum":
        return grouped.sum()
    if how == "mean":
        return grouped.mean()
    return grouped.max()


def _detailed_material_cover_by_day(
    stock_frame: pd.DataFrame,
    consumption_frame: pd.DataFrame,
) -> pd.Series:
    """Return a robust low-tail material cover from pair-level physical files.

    Total network inventory divided by customer demand is not a meaningful raw-
    material cover.  When detailed files are available, cover is calculated for
    each active factory-item pair and the daily 10th percentile is retained.
    This captures the first materially constrained lanes without letting a single
    inactive or zero-flow item dominate the regime calibration.
    """

    if stock_frame.empty:
        return pd.Series(dtype=float)
    stock_day = first_existing_column(stock_frame, ["day", "sim_day", "day_index"])
    node_stock = first_existing_column(stock_frame, ["node_id", "factory_id", "site_id"])
    item_stock = first_existing_column(stock_frame, ["item_id", "material_id", "component_id"])
    stock_value = first_existing_column(stock_frame, [
        "stock_end_of_day", "stock_before_production", "stock_qty", "inventory_qty", "on_hand"
    ])
    if any(value is None for value in [stock_day, node_stock, item_stock, stock_value]):
        return pd.Series(dtype=float)

    stocks = pd.DataFrame({
        "day": pd.to_numeric(stock_frame[stock_day], errors="coerce"),
        "node_id": stock_frame[node_stock].astype(str),
        "item_id": stock_frame[item_stock].astype(str),
        "stock": pd.to_numeric(stock_frame[stock_value], errors="coerce"),
    }).dropna(subset=["day", "stock"])
    consumption = pd.DataFrame()
    if not consumption_frame.empty:
        consumption_day = first_existing_column(
            consumption_frame, ["day", "sim_day", "day_index"]
        )
        node_cons = first_existing_column(
            consumption_frame, ["node_id", "factory_id", "site_id"]
        )
        item_cons = first_existing_column(
            consumption_frame, ["item_id", "material_id", "component_id"]
        )
        consumption_value = first_existing_column(consumption_frame, [
            "consumed_qty", "consumption_qty", "required_qty", "input_consumption_qty"
        ])
        if all(
            value is not None
            for value in [consumption_day, node_cons, item_cons, consumption_value]
        ):
            consumption = pd.DataFrame({
                "day": pd.to_numeric(
                    consumption_frame[str(consumption_day)], errors="coerce"
                ),
                "node_id": consumption_frame[str(node_cons)].astype(str),
                "item_id": consumption_frame[str(item_cons)].astype(str),
                "consumption": pd.to_numeric(
                    consumption_frame[str(consumption_value)], errors="coerce"
                ),
            }).dropna(subset=["day", "consumption"])

    # The canonical engine always exports stock immediately before production
    # and at end of day, but older runs do not have a separate consumption CSV.
    # Their non-negative difference is the actual material consumed that day.
    if consumption.empty:
        stock_before = first_existing_column(
            stock_frame, ["stock_before_production"]
        )
        stock_end = first_existing_column(stock_frame, ["stock_end_of_day"])
        if stock_before is None or stock_end is None:
            return pd.Series(dtype=float)
        consumption = pd.DataFrame({
            "day": pd.to_numeric(stock_frame[stock_day], errors="coerce"),
            "node_id": stock_frame[node_stock].astype(str),
            "item_id": stock_frame[item_stock].astype(str),
            "consumption": (
                pd.to_numeric(stock_frame[stock_before], errors="coerce")
                - pd.to_numeric(stock_frame[stock_end], errors="coerce")
            ).clip(lower=0.0),
        }).dropna(subset=["day", "consumption"])
    if stocks.empty or consumption.empty:
        return pd.Series(dtype=float)
    stocks["day"] = stocks["day"].astype(int)
    consumption["day"] = consumption["day"].astype(int)
    stocks = stocks.groupby(["day", "node_id", "item_id"], as_index=False)["stock"].sum()
    consumption = consumption.groupby(["day", "node_id", "item_id"], as_index=False)["consumption"].sum()
    consumption = consumption.sort_values(["node_id", "item_id", "day"])
    # Production consumes in lots, so daily usage is sparse and its median is
    # often exactly zero.  A rolling mean estimates the equivalent daily rate
    # without turning every non-production day into infinite material cover.
    consumption["reference_daily_consumption"] = consumption.groupby(
        ["node_id", "item_id"]
    )["consumption"].transform(
        lambda values: values.rolling(28, min_periods=3).mean()
    )
    pair_mean = consumption.groupby(
        ["node_id", "item_id"]
    )["consumption"].transform("mean")
    consumption["reference_daily_consumption"] = (
        consumption["reference_daily_consumption"].fillna(pair_mean)
    )
    merged = stocks.merge(
        consumption[["day", "node_id", "item_id", "reference_daily_consumption"]],
        on=["day", "node_id", "item_id"], how="left",
    )
    active = merged["reference_daily_consumption"] > 1e-9
    merged = merged.loc[active].copy()
    if merged.empty:
        return pd.Series(dtype=float)
    merged["cover_days"] = (merged["stock"].clip(lower=0) / merged["reference_daily_consumption"]).clip(0, 365)
    return merged.groupby("day")["cover_days"].quantile(0.10)


def build_calibration_frame(context: RunContext) -> tuple[pd.DataFrame, dict[str, str]]:
    base = context.input_series.copy().reset_index(drop=True)
    day_values = pd.to_numeric(base["day"], errors="coerce")
    fallback_days = pd.Series(np.arange(len(base)), index=base.index, dtype=float)
    base["day"] = day_values.where(day_values.notna(), fallback_days).astype(int)
    demand_reference = base["demand"].rolling(28, min_periods=7).median().replace(0.0, np.nan).bfill().ffill()
    demand_reference = demand_reference.clip(lower=1e-6)
    frame = pd.DataFrame({
        "day": base["day"],
        "demand": base["demand"],
        "served": base["served"],
        "service": base.get("historical_service", base["served"] / base["demand"].replace(0, np.nan)).fillna(1.0).clip(0, 1),
        "backlog": base["backlog"].clip(lower=0),
        "inventory": base["inventory"].clip(lower=0),
        "orders": base["orders"].clip(lower=0),
        "arrivals": base["arrivals"].clip(lower=0),
        "produced": base["produced"].clip(lower=0),
        "base_risk": base["base_risk"].clip(0, 1),
        "risk_uncertainty": base["risk_uncertainty"].clip(lower=0),
        "nervousness": base.get("historical_nervousness", base["orders"].diff().abs() / demand_reference).fillna(0).clip(lower=0),
        "production_utilization": base.get("historical_production_utilization", 0.0),
    })
    frame["inventory_cover_days"] = frame["inventory"] / demand_reference
    frame["backlog_days"] = frame["backlog"] / demand_reference
    frame["backlog_delta"] = frame["backlog_days"].diff().fillna(0.0)
    frame["service_loss"] = 1.0 - frame["service"]
    frame["order_delta"] = frame["orders"].diff().fillna(0.0)
    frame["order_acceleration"] = frame["order_delta"].diff().fillna(0.0)
    frame["oscillation_index"] = (
        frame["order_delta"].rolling(14, min_periods=4).std().fillna(0.0)
        / demand_reference
    ).clip(lower=0)

    discovered = discover_calibration_files(context)
    file_map = {key: str(value) for key, value in discovered.items()}

    input_stocks = _read_optional(discovered.get("input_stocks"))
    input_consumption = _read_optional(discovered.get("input_consumption"))
    detailed_cover = _detailed_material_cover_by_day(
        input_stocks,
        input_consumption,
    )
    if not detailed_cover.empty:
        frame = frame.merge(detailed_cover.rename("material_cover_days"), on="day", how="left")
        frame["material_cover_source"] = (
            "pair_level_input_stock_and_consumption"
            if not input_consumption.empty
            else "pair_level_input_stock_implied_consumption"
        )
        frame["material_cover_known"] = pd.to_numeric(
            frame["material_cover_days"], errors="coerce"
        ).notna()
        frame["material_cover_status"] = np.where(
            frame["material_cover_known"],
            "observed_pair_level",
            "unknown_pair_level_gap",
        )
    else:
        baseline_metadata = dict(context.baseline_ingestion_metadata or {})
        missing_baseline_signals = set(baseline_metadata.get("missing_signals") or ())
        aggregate_inventory_known = (
            not baseline_metadata or "inventory" not in missing_baseline_signals
        )
        if aggregate_inventory_known:
            # Fallback retained for self-contained and compact runs.  It is
            # marked explicitly because aggregate network inventory is a weaker
            # proxy than factory-item material stock and consumption.
            if "inventory_signal_known" in base:
                inventory_row_known = base["inventory_signal_known"].map(
                    lambda value: optional_boolean(value) is True
                )
            else:
                inventory_row_known = pd.to_numeric(
                    base.get("inventory", pd.Series(np.nan, index=base.index)),
                    errors="coerce",
                ).notna()
            inventory_row_known = inventory_row_known.to_numpy(dtype=bool)
            frame["material_cover_days"] = frame[
                "inventory_cover_days"
            ].clip(0, 60).where(inventory_row_known, np.nan)
            frame["material_cover_known"] = (
                inventory_row_known
                & pd.to_numeric(
                    frame["material_cover_days"], errors="coerce"
                ).notna().to_numpy(dtype=bool)
            )
            frame["material_cover_source"] = np.where(
                frame["material_cover_known"],
                "aggregate_inventory_fallback",
                "unavailable_aggregate_inventory_gap",
            )
            frame["material_cover_status"] = np.where(
                frame["material_cover_known"],
                "aggregate_inventory_fallback",
                "unknown_aggregate_inventory_gap",
            )
        else:
            # The baseline aggregation represents missing columns as zero for
            # other backward-compatible signals.  Material cover must not reuse
            # that placeholder: an unknown stock signal is not a stockout.
            frame["material_cover_days"] = np.nan
            frame["material_cover_source"] = "unavailable_no_material_or_inventory_signal"
            frame["material_cover_known"] = False
            frame["material_cover_status"] = "unknown_no_physical_cover_signal"

    constraints = _read_optional(discovered.get("constraints"))
    if not constraints.empty:
        numeric_binding_columns = [
            column
            for column in constraints.columns
            if any(
                token in column.lower()
                for token in (
                    "shortfall",
                    "shortage_qty",
                    "constraint_qty",
                    "capacity_active",
                    "limited_qty",
                    "binding_qty",
                )
            )
        ]
        row_activity = pd.Series(0.0, index=constraints.index, dtype=float)
        if numeric_binding_columns:
            numeric = constraints[numeric_binding_columns].apply(
                pd.to_numeric, errors="coerce"
            ).fillna(0.0)
            row_activity += (numeric.abs() > 1e-9).sum(axis=1)
        cause_column = first_existing_column(
            constraints,
            ["binding_cause", "constraint_cause", "binding_reason", "shortfall_cause"],
        )
        if cause_column:
            neutral_causes = {
                "",
                "none",
                "no_binding",
                "not_binding",
                "unconstrained",
                "not_applicable",
                "na",
                "nan",
            }
            causes = (
                constraints[cause_column]
                .astype("string")
                .fillna("")
                .str.strip()
                .str.lower()
            )
            row_activity += (~causes.isin(neutral_causes)).astype(float)
        if (row_activity > 0).any():
            frame = frame.merge(
                _aggregate_by_day(
                    constraints, row_activity, "sum"
                ).rename("constraint_activity"),
                on="day", how="left",
            )
    if "constraint_activity" not in frame:
        frame["constraint_activity"] = 0.0

    supplier_capacity = _read_optional(discovered.get("supplier_capacity"))
    if not supplier_capacity.empty:
        utilization = _numeric(supplier_capacity, ["utilization", "capacity_utilization", "used_ratio"], 0.0)
        frame = frame.merge(
            _aggregate_by_day(supplier_capacity, utilization, "max").rename("supplier_utilization"),
            on="day", how="left",
        )
    if "supplier_utilization" not in frame:
        frame["supplier_utilization"] = np.clip(frame["arrivals"] / demand_reference, 0, 2)

    state_events = _read_optional(discovered.get("state_risk_events"))
    frame["state_risk_event_count"] = 0.0
    frame["state_risk_event_severity"] = 0.0
    if not state_events.empty:
        active_count = pd.Series(0.0, index=frame.index)
        active_severity = pd.Series(0.0, index=frame.index)
        day_to_index = {int(day): index for index, day in enumerate(frame["day"].astype(int))}
        for _, event_row in state_events.iterrows():
            start = int(safe_float(event_row.get("start_day", event_row.get("trigger_day", event_row.get("day", 0))), 0.0))
            end = int(safe_float(event_row.get("end_day", start), start))
            if end < start:
                start, end = end, start
            risk_type = str(event_row.get("risk_type") or event_row.get("effect") or "").lower()
            multiplier = safe_float(event_row.get("multiplier"), 1.0)
            if any(token in risk_type for token in ("capacity", "availability", "quality", "yield", "reliability")):
                severity = max(0.0, 1.0 - multiplier)
            elif "lead" in risk_type or "delay" in risk_type:
                severity = clamp(multiplier / 90.0 if multiplier > 1.0 else 1.0 - multiplier, 0.0, 1.0)
            elif "writeoff" in risk_type or "stock" in risk_type:
                severity = clamp(multiplier, 0.0, 1.0)
            elif "cost" in risk_type:
                severity = clamp((multiplier - 1.0) / 1.5, 0.0, 1.0)
            else:
                severity = clamp(abs(1.0 - multiplier), 0.0, 1.0)
            for day in range(start, end + 1):
                index = day_to_index.get(day)
                if index is None:
                    continue
                active_count.iloc[index] += 1.0
                active_severity.iloc[index] = max(active_severity.iloc[index], severity)
        frame["state_risk_event_count"] = active_count.to_numpy(dtype=float)
        frame["state_risk_event_severity"] = active_severity.to_numpy(dtype=float)

    applied_risk = _read_optional(discovered.get("supplier_risk_applied"))
    frame["applied_risk_severity"] = 0.0
    if not applied_risk.empty:
        severity_parts: list[pd.Series] = []
        for names in (["capacity_multiplier"], ["availability_multiplier"], ["reliability_multiplier"], ["quality_yield_multiplier"]):
            column = first_existing_column(applied_risk, names)
            if column:
                severity_parts.append((1.0 - pd.to_numeric(applied_risk[column], errors="coerce").fillna(1.0)).clip(0, 1))
        lead_column = first_existing_column(applied_risk, ["lead_time_extra_days", "external_lead_time_extra_days", "quality_delay_days"])
        if lead_column:
            severity_parts.append((pd.to_numeric(applied_risk[lead_column], errors="coerce").fillna(0.0) / 90.0).clip(0, 1))
        writeoff_column = first_existing_column(applied_risk, ["stock_writeoff_fraction"])
        if writeoff_column:
            severity_parts.append(pd.to_numeric(applied_risk[writeoff_column], errors="coerce").fillna(0.0).clip(0, 1))
        if severity_parts:
            row_severity = pd.concat(severity_parts, axis=1).max(axis=1)
            aggregated = _aggregate_by_day(applied_risk, row_severity, "max")
            if not aggregated.empty:
                frame = frame.drop(columns=["applied_risk_severity"]).merge(
                    aggregated.rename("applied_risk_severity"), on="day", how="left"
                )
                frame["applied_risk_severity"] = frame["applied_risk_severity"].fillna(0.0)

    forecast_dynamic = float(frame["base_risk"].std(ddof=0)) > 0.02 and int(frame["base_risk"].nunique()) > 5
    event_signal = frame[["state_risk_event_severity", "applied_risk_severity"]].max(axis=1)
    if event_signal.max() > 1e-9:
        frame["calibration_risk_signal"] = np.maximum(
            event_signal, frame["base_risk"] if forecast_dynamic else 0.0
        )
        frame["calibration_risk_source"] = "events_and_dynamic_forecast" if forecast_dynamic else "canonical_event_trajectory"
    else:
        frame["calibration_risk_signal"] = frame["base_risk"]
        frame["calibration_risk_source"] = "forecast_fallback"
    frame["forecast_risk_is_dynamic"] = int(forecast_dynamic)

    nervousness_file = _read_optional(discovered.get("factory_nervousness"))
    if not nervousness_file.empty:
        nervousness_value = _numeric(nervousness_file, [
            "nervousness", "factory_nervousness", "normalized_nervousness", "plan_change_ratio"
        ], 0.0)
        aggregated = _aggregate_by_day(nervousness_file, nervousness_value, "max")
        if not aggregated.empty:
            frame = frame.merge(aggregated.rename("factory_nervousness_observed"), on="day", how="left")
            frame["nervousness"] = frame[["nervousness", "factory_nervousness_observed"]].max(axis=1)

    inventory_reference = (
        frame["inventory_cover_days"]
        .rolling(60, min_periods=min(14, max(1, len(frame))))
        .median()
        .shift(1)
    )
    inventory_fallback = _quantile(
        frame.loc[frame["inventory_cover_days"] > 0, "inventory_cover_days"],
        0.50,
        1.0,
    )
    frame["inventory_reference_cover_days"] = inventory_reference.fillna(
        inventory_fallback
    ).clip(lower=1e-6)
    frame["inventory_excess_ratio"] = (
        frame["inventory_cover_days"] / frame["inventory_reference_cover_days"]
    ).clip(0.0, 20.0)
    disruption = (
        (frame["backlog_days"] > 0.02)
        | (frame["service"] < 0.98)
        | (frame["state_risk_event_count"] > 0)
        | (frame["applied_risk_severity"] > 0)
        | (frame["constraint_activity"] > 0)
    ).astype(float)
    frame["recent_disruption_signal"] = (
        disruption.rolling(60, min_periods=1).max().shift(1).fillna(0.0)
    )

    # Preserve unknown material-cover values.  A blanket ``fillna(0)`` would
    # turn a missing/gapped measurement into a false physical stockout and
    # could trigger MATERIAL_TENSION by itself.
    for column in frame.select_dtypes(include=[np.number, "bool"]).columns:
        if column != "material_cover_days":
            frame[column] = frame[column].fillna(0.0)
    frame = frame.sort_values("day").reset_index(drop=True)
    return frame, file_map


def _quantile(values: pd.Series, q: float, fallback: float) -> float:
    clean = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(clean.quantile(q)) if not clean.empty else float(fallback)


def _clip_threshold(name: str, value: float) -> float:
    bounds = {
        "material_tension_days": (0.15, 5.0),
        "capacity_saturation": (0.60, 0.995),
        "supplier_risk": (0.25, 0.95),
        "supplier_stress": (0.25, 1.50),
        "oscillation_nervousness": (0.05, 1.50),
        "crisis_backlog_days": (0.15, 10.0),
        "recovery_backlog_days": (0.02, 3.0),
        "overstock_days": (2.0, 30.0),
    }
    low, high = bounds[name]
    return clamp(value, low, high)


def calibrate_regime_thresholds(frame: pd.DataFrame, base_config: Mapping[str, Any]) -> tuple[dict[str, float], pd.DataFrame]:
    defaults = base_config["regime_thresholds"]
    forecast_dynamic = bool(int(frame.get("forecast_risk_is_dynamic", pd.Series([0])).max()))
    service_q10 = _quantile(frame["service"], 0.10, 0.95)
    positive_backlog = frame.loc[frame["backlog_days"] > 1e-9, "backlog_days"]
    inventory_positive = frame.loc[frame["inventory_cover_days"] > 1e-9, "inventory_cover_days"]
    utilization = frame[["production_utilization", "supplier_utilization"]].max(axis=1)
    positive_utilization = utilization.loc[utilization > 1e-9]
    material_cover_values = pd.to_numeric(
        frame.get("material_cover_days", pd.Series(np.nan, index=frame.index)),
        errors="coerce",
    )
    if "material_cover_known" in frame:
        material_cover_known = (
            frame["material_cover_known"].map(
                lambda value: optional_boolean(value) is True
            )
            & material_cover_values.notna()
        )
    else:
        material_cover_known = material_cover_values.notna()
    positive_material_cover = material_cover_values.loc[
        material_cover_known & (material_cover_values > 1e-9)
    ]
    positive_nervousness = frame.loc[frame["nervousness"] > 1e-9, "nervousness"]
    capacity_cut = _quantile(
        positive_utilization, 0.88, safe_float(defaults["capacity_saturation"])
    )
    material_cut = _quantile(
        positive_material_cover, 0.12, safe_float(defaults["material_tension_days"])
    )
    nervousness_cut = _quantile(
        positive_nervousness, 0.90, safe_float(defaults["oscillation_nervousness"])
    )

    anchors = pd.DataFrame(index=frame.index)
    anchors["crisis"] = (frame["service"] <= min(0.92, service_q10)) | (
        frame["backlog_days"] >= _quantile(positive_backlog, 0.85, safe_float(defaults["crisis_backlog_days"]))
    )
    anchors["supplier_stress"] = (
        frame["state_risk_event_count"] > 0
    ) | (frame["calibration_risk_signal"] >= _quantile(
        frame["calibration_risk_signal"], 0.85, safe_float(defaults["supplier_risk"])
    ))
    anchors["capacity"] = (
        ((utilization > 1e-9) & (utilization >= capacity_cut))
        | (frame["constraint_activity"] > 0)
    )
    anchors["material"] = (
        material_cover_known
        & (material_cover_values > 1e-9)
        & (material_cover_values <= material_cut)
    ) & ((frame["backlog_delta"] > 0) | (frame["service"] < 0.99))
    anchors["oscillatory"] = (
        (frame["nervousness"] > 1e-9)
        & (frame["nervousness"] >= nervousness_cut)
        & (frame["oscillation_index"] > 1e-9)
    ) & (
        frame["oscillation_index"]
        >= _quantile(
            frame.loc[frame["oscillation_index"] > 1e-9, "oscillation_index"],
            0.75,
            0.05,
        )
    )
    anchors["recovery"] = (frame["backlog_days"] > 0) & (frame["backlog_delta"] < 0) & (
        frame["service"].rolling(5, min_periods=1).mean() >= frame["service"].rolling(12, min_periods=1).mean()
    )
    inventory_excess = frame.get(
        "inventory_excess_ratio", pd.Series(1.0, index=frame.index)
    )
    recent_disruption = frame.get(
        "recent_disruption_signal", pd.Series(0.0, index=frame.index)
    )
    anchors["overstock"] = (
        frame["inventory_cover_days"]
        >= _quantile(
            inventory_positive, 0.92, safe_float(defaults["overstock_days"])
        )
    ) & (
        inventory_excess
        >= max(
            1.05,
            _quantile(
                inventory_excess.loc[inventory_excess > 1.0],
                0.75,
                1.05,
            ),
        )
    ) & (
        frame["backlog_days"] <= 0.02
    ) & (
        recent_disruption > 0
    )
    frame["post_crisis_overstock_candidate"] = anchors["overstock"].astype(int)

    supplier_stress_proxy = np.clip(
        0.45 * frame["calibration_risk_signal"]
        + 0.10 * frame["base_risk"]
        + 0.25 * np.tanh(frame["nervousness"])
        + 0.10 * np.tanh(frame["state_risk_event_count"])
        + 0.10 * np.tanh(frame["constraint_activity"]),
        0.0,
        2.0,
    )
    frame["supplier_stress_proxy"] = supplier_stress_proxy

    capacity_anchor_utilization = utilization.loc[anchors["capacity"] & (utilization > 1e-9)]
    crisis_anchor_backlog = frame.loc[
        anchors["crisis"] & (frame["backlog_days"] > 1e-9), "backlog_days"
    ]
    recovery_anchor_backlog = frame.loc[
        anchors["recovery"] & (frame["backlog_days"] > 1e-9), "backlog_days"
    ]
    material_anchor_cover = material_cover_values.loc[anchors["material"]]
    oscillatory_anchor_nervousness = frame.loc[anchors["oscillatory"], "nervousness"]
    overstock_anchor_inventory = frame.loc[anchors["overstock"], "inventory_cover_days"]

    calibrated = {
        "material_tension_days": _clip_threshold(
            "material_tension_days",
            _quantile(material_anchor_cover, 0.75, material_cut)
            if not material_anchor_cover.empty
            else safe_float(defaults["material_tension_days"]),
        ),
        "capacity_saturation": _clip_threshold(
            "capacity_saturation",
            _quantile(capacity_anchor_utilization, 0.30, capacity_cut)
            if not capacity_anchor_utilization.empty
            else safe_float(defaults["capacity_saturation"]),
        ),
        "supplier_risk": _clip_threshold(
            "supplier_risk",
            _quantile(frame.loc[anchors["supplier_stress"], "base_risk"], 0.30,
                      _quantile(frame["base_risk"], 0.85, safe_float(defaults["supplier_risk"])))
            if forecast_dynamic else safe_float(defaults["supplier_risk"]),
        ),
        "supplier_stress": _clip_threshold(
            "supplier_stress",
            _quantile(frame.loc[anchors["supplier_stress"], "supplier_stress_proxy"], 0.30,
                      safe_float(defaults["supplier_stress"])),
        ),
        "oscillation_nervousness": _clip_threshold(
            "oscillation_nervousness",
            _quantile(oscillatory_anchor_nervousness, 0.30, nervousness_cut)
            if not oscillatory_anchor_nervousness.empty
            else safe_float(defaults["oscillation_nervousness"]),
        ),
        "crisis_backlog_days": _clip_threshold(
            "crisis_backlog_days",
            _quantile(
                crisis_anchor_backlog,
                0.30,
                _quantile(positive_backlog, 0.85, safe_float(defaults["crisis_backlog_days"])),
            )
            if not crisis_anchor_backlog.empty
            else safe_float(defaults["crisis_backlog_days"]),
        ),
        "recovery_backlog_days": _clip_threshold(
            "recovery_backlog_days",
            _quantile(
                recovery_anchor_backlog,
                0.25,
                safe_float(defaults["recovery_backlog_days"]),
            )
            if not recovery_anchor_backlog.empty
            else safe_float(defaults["recovery_backlog_days"]),
        ),
        "overstock_days": _clip_threshold(
            "overstock_days",
            _quantile(
                overstock_anchor_inventory,
                0.25,
                _quantile(inventory_positive, 0.92, safe_float(defaults["overstock_days"])),
            )
            if not overstock_anchor_inventory.empty
            else safe_float(defaults["overstock_days"]),
        ),
    }

    signal_available = {
        "material_tension_days": not positive_material_cover.empty,
        "capacity_saturation": not positive_utilization.empty,
        "supplier_risk": forecast_dynamic,
        "supplier_stress": bool((frame["calibration_risk_signal"] > 1e-9).any()),
        "oscillation_nervousness": not positive_nervousness.empty
        and bool((frame["oscillation_index"] > 1e-9).any()),
        "crisis_backlog_days": not positive_backlog.empty,
        "recovery_backlog_days": not positive_backlog.empty,
        "overstock_days": bool(anchors["overstock"].any()),
    }
    frame["max_utilization"] = utilization

    # Keep exactly one auditable evidence row per executable regime.  Supplier
    # stress owns two thresholds, while NOMINAL is an ordered fallthrough; the
    # legacy scalar columns remain for report compatibility and use the
    # supplier-stress exclusion boundary on the NOMINAL row.
    classified = apply_calibrated_regime_labels(frame, calibrated)[
        "calibrated_regime"
    ]
    evidence_spec: dict[str, dict[str, Any]] = {
        "NOMINAL": {
            "threshold": "supplier_stress",
            "thresholds": (),
            "feature": "supplier_stress_proxy",
            "direction": "fallthrough",
            "available": True,
            "method": "ordered_rule_fallthrough",
        },
        "MATERIAL_TENSION": {
            "threshold": "material_tension_days",
            "thresholds": ("material_tension_days",),
            "feature": "material_cover_days",
            "direction": "low",
            "available": signal_available["material_tension_days"],
            "method": "robust_quantile_anchor",
        },
        "CAPACITY_SATURATION": {
            "threshold": "capacity_saturation",
            "thresholds": ("capacity_saturation",),
            "feature": "max_utilization",
            "direction": "high",
            "available": signal_available["capacity_saturation"],
            "method": "robust_quantile_anchor",
        },
        "SUPPLIER_STRESS": {
            "threshold": "supplier_risk",
            "thresholds": ("supplier_risk", "supplier_stress"),
            "feature": "supplier_stress_proxy",
            "direction": "high",
            "available": (
                signal_available["supplier_risk"]
                or signal_available["supplier_stress"]
            ),
            "method": "robust_quantile_anchor",
        },
        "OSCILLATORY": {
            "threshold": "oscillation_nervousness",
            "thresholds": ("oscillation_nervousness",),
            "feature": "nervousness",
            "direction": "high",
            "available": signal_available["oscillation_nervousness"],
            "method": "robust_quantile_anchor",
        },
        "CRISIS": {
            "threshold": "crisis_backlog_days",
            "thresholds": ("crisis_backlog_days",),
            "feature": "backlog_days",
            "direction": "high",
            "available": signal_available["crisis_backlog_days"],
            "method": "robust_quantile_anchor",
        },
        "RECOVERY": {
            "threshold": "recovery_backlog_days",
            "thresholds": ("recovery_backlog_days",),
            "feature": "backlog_days",
            "direction": "contextual",
            "available": signal_available["recovery_backlog_days"],
            "method": "robust_quantile_anchor",
        },
        "POST_CRISIS_OVERSTOCK": {
            "threshold": "overstock_days",
            "thresholds": ("overstock_days",),
            "feature": "inventory_cover_days",
            "direction": "high_after_disruption",
            "available": signal_available["overstock_days"],
            "method": "robust_quantile_anchor",
        },
    }

    unknown_material_days = int((~material_cover_known).sum())
    material_sources = sorted(
        str(value)
        for value in frame.get(
            "material_cover_source", pd.Series("unknown", index=frame.index)
        ).dropna().unique()
    )
    material_limitations: list[str] = []
    if unknown_material_days:
        material_limitations.append(
            f"{unknown_material_days} day(s) have unknown material cover and are "
            "excluded from MATERIAL_TENSION triggering and threshold fitting"
        )
    if "aggregate_inventory_fallback" in material_sources:
        material_limitations.append(
            "aggregate inventory is an explicitly qualified weak material-cover fallback"
        )
    if not material_sources or all(source.startswith("unavailable_") for source in material_sources):
        material_limitations.append("no usable physical material-cover signal")

    evidence_rows: list[dict[str, Any]] = []
    for regime in VALIDATED_REGIMES:
        spec = evidence_spec[regime]
        threshold_name = str(spec["threshold"])
        feature = str(spec["feature"])
        direction = str(spec["direction"])
        mask = classified == regime
        positive = frame.loc[mask, feature]
        negative = frame.loc[~mask, feature]
        separation = _quantile(positive, 0.50, 0.0) - _quantile(negative, 0.50, 0.0)
        confidence = "high" if int(mask.sum()) >= 20 and abs(separation) > 0.05 else (
            "medium" if int(mask.sum()) >= 5 else "low"
        )
        if not bool(spec["available"]):
            confidence = "low"
        threshold_names = tuple(spec["thresholds"])
        initial_thresholds = {
            name: safe_float(defaults[name]) for name in threshold_names
        }
        calibrated_thresholds = {
            name: calibrated[name] for name in threshold_names
        }
        limitations = [
            "pseudo-label evidence; representative business labels remain required",
            "ordered predicates assign a day only to the first matching regime",
        ]
        if regime == "NOMINAL":
            limitations.append(
                "the legacy supplier_stress scalar is an exclusion-boundary "
                "diagnostic, not a positive NOMINAL predicate"
            )
        if regime == "MATERIAL_TENSION":
            limitations.extend(material_limitations)
        evidence_rows.append({
            "regime": regime,
            "classification_rule": REGIME_CLASSIFICATION_RULES[regime],
            "variables_used": "|".join(REGIME_VARIABLES_USED[regime]) or (
                "all_higher_priority_rule_variables"
            ),
            "initial_thresholds": json.dumps(
                initial_thresholds, sort_keys=True, separators=(",", ":")
            ),
            "calibrated_thresholds": json.dumps(
                calibrated_thresholds, sort_keys=True, separators=(",", ":")
            ),
            "method": spec["method"],
            "anchor_count": int(mask.sum()),
            "separation": float(separation),
            "limitations": "; ".join(limitations),
            "threshold": threshold_name,
            "calibrated_value": calibrated[threshold_name],
            "previous_value": safe_float(defaults[threshold_name]),
            "anchor": regime.lower(),
            "feature": feature,
            "direction": direction,
            "anchor_days": int(mask.sum()),
            "non_anchor_days": int((~mask).sum()),
            "median_anchor": _quantile(positive, 0.50, 0.0),
            "median_non_anchor": _quantile(negative, 0.50, 0.0),
            "median_separation": float(separation),
            "confidence": confidence,
            "signal_status": (
                "observed" if bool(spec["available"]) else "insufficient_signal"
            ),
        })
    evidence = pd.DataFrame(evidence_rows)
    if list(evidence["regime"]) != list(VALIDATED_REGIMES) or evidence["regime"].duplicated().any():
        raise AssertionError("Calibration evidence must contain each SCAN regime exactly once.")
    return calibrated, evidence


def _declared_nominal_parameters(
    base_config: Mapping[str, Any],
) -> dict[str, float]:
    """Return the reduced-model parameters declared by the experiment config."""

    nominal = base_config["nominal"]
    return {
        "raw_inventory_days": safe_float(nominal["raw_inventory_days"]),
        "finished_inventory_days": safe_float(
            nominal["finished_inventory_days"]
        ),
        "supplier_capacity_ratio": safe_float(
            nominal["supplier_capacity_ratio"]
        ),
        "production_capacity_ratio": safe_float(
            nominal["production_capacity_ratio"]
        ),
        "pipeline_days": safe_float(nominal["pipeline_days"]),
        "base_lead_time_days": safe_float(
            nominal["base_lead_time_days"]
        ),
    }


def calibrate_nominal_parameters(
    frame: pd.DataFrame,
    base_config: Mapping[str, Any],
    *,
    allow_aggregate_refit: bool = False,
) -> dict[str, float]:
    """Estimate reduced-model nominal parameters only with comparable units.

    Canonical etudecas daily totals mix finished-product demand with inventory,
    production and arrivals aggregated across items and bill-of-material levels.
    Ratios between those totals are therefore not automatically meaningful.
    The safe default retains the declared reduced-model hypotheses.  The
    quantile refit is available only when the caller has established a common
    normalized unit, as for the self-contained synthetic reduced model.
    """

    declared = _declared_nominal_parameters(base_config)
    if not allow_aggregate_refit:
        return declared

    nominal = base_config["nominal"]
    demand = frame["demand"].replace(0.0, np.nan)
    no_backlog = frame["backlog_days"] <= 0.02
    stable = no_backlog & (frame["service"] >= 0.98) & (frame["nervousness"] <= frame["nervousness"].quantile(0.75))
    stable_frame = frame.loc[stable] if stable.any() else frame
    total_cover = stable_frame["inventory_cover_days"].clip(lower=0)
    total_target = _quantile(total_cover, 0.50, safe_float(nominal["raw_inventory_days"]) + safe_float(nominal["finished_inventory_days"]))
    raw_share = clamp(safe_float(nominal["raw_inventory_days"]) / max(
        safe_float(nominal["raw_inventory_days"]) + safe_float(nominal["finished_inventory_days"]), 1e-6
    ), 0.50, 0.90)
    production_ratio = (frame["produced"] / demand).replace([np.inf, -np.inf], np.nan)
    arrival_ratio = (frame["arrivals"] / demand).replace([np.inf, -np.inf], np.nan)
    return {
        "raw_inventory_days": clamp(total_target * raw_share, 0.25, 20.0),
        "finished_inventory_days": clamp(total_target * (1.0 - raw_share), 0.10, 10.0),
        "supplier_capacity_ratio": clamp(_quantile(arrival_ratio, 0.95, safe_float(nominal["supplier_capacity_ratio"])), 0.70, 3.0),
        "production_capacity_ratio": clamp(_quantile(production_ratio, 0.95, safe_float(nominal["production_capacity_ratio"])), 0.70, 3.0),
        "pipeline_days": safe_float(nominal["pipeline_days"]),
        "base_lead_time_days": safe_float(nominal["base_lead_time_days"]),
    }


def apply_calibrated_regime_labels(frame: pd.DataFrame, thresholds: Mapping[str, float]) -> pd.DataFrame:
    """Apply the same ordered predicates used by operational classification."""

    result = frame.copy()
    labels: list[str] = []
    previous_backlog = 0.0
    for _, row in result.iterrows():
        backlog = safe_float(row.get("backlog_days"))
        explicit_previous = row.get("previous_backlog_days")
        previous_for_row = (
            previous_backlog
            if explicit_previous is None or pd.isna(explicit_previous)
            else safe_float(explicit_previous)
        )
        material_cover = pd.to_numeric(
            pd.Series([row.get("material_cover_days")]), errors="coerce"
        ).iloc[0]
        material_known_value = row.get("material_cover_known")
        material_known = (
            material_known_value
            if material_known_value is not None and not pd.isna(material_known_value)
            else bool(pd.notna(material_cover))
        )
        label = classify_regime_signals(
            {
                "backlog_days": backlog,
                "previous_backlog_days": previous_for_row,
                "service": row.get("service", 1.0),
                "supplier_risk": row.get("base_risk", row.get("supplier_risk", 0.0)),
                "supplier_stress": row.get(
                    "supplier_stress_proxy", row.get("supplier_stress", 0.0)
                ),
                "nervousness": row.get("nervousness", 0.0),
                "production_utilization": row.get("production_utilization", 0.0),
                "supplier_utilization": row.get("supplier_utilization", 0.0),
                "material_cover_days": material_cover,
                "material_cover_known": material_known,
                "inventory_cover_days": row.get("inventory_cover_days", 0.0),
                "inventory_excess_ratio": row.get("inventory_excess_ratio", 1.0),
                "recent_disruption_signal": row.get(
                    "recent_disruption_signal", 0.0
                ),
                "post_crisis_overstock_candidate": row.get(
                    "post_crisis_overstock_candidate", 1.0
                ),
            },
            thresholds,
        )
        labels.append(label)
        previous_backlog = backlog
    result["calibrated_regime"] = labels
    return result


def _context_period_origin(context: RunContext) -> str | None:
    """Return a declared baseline calendar origin when ingestion exposes one."""

    metadata = dict(context.baseline_ingestion_metadata or {})
    for key in (
        "period_origin",
        "simulation_start_date",
        "start_date",
        "calendar_origin",
        "date_origin",
    ):
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def calibrate_from_context(
    context: RunContext,
    base_config: Mapping[str, Any],
    regime_annotations_path: Path | None = None,
) -> CalibrationArtifacts:
    """Calibrate pseudo-regimes and optionally overlay expert business labels."""

    frame, files = build_calibration_frame(context)
    thresholds, evidence = calibrate_regime_thresholds(frame, base_config)
    declared_nominal = _declared_nominal_parameters(base_config)
    aggregate_refit_allowed = context.source_mode == "synthetic_fallback"
    aggregate_refit_candidate = calibrate_nominal_parameters(
        frame,
        base_config,
        allow_aggregate_refit=True,
    )
    nominal = (
        aggregate_refit_candidate
        if aggregate_refit_allowed
        else declared_nominal
    )
    nominal_calibration = {
        "status": (
            "refit_on_normalized_synthetic_reduced_model"
            if aggregate_refit_allowed
            else "retained_declared_reduced_model_parameters"
        ),
        "refit_applied": bool(aggregate_refit_allowed),
        "unit_comparability": (
            "normalized_synthetic_reduced_model_unit"
            if aggregate_refit_allowed
            else "not_established_across_items_and_bom_levels"
        ),
        "declared_values": declared_nominal,
        "aggregate_refit_candidate": aggregate_refit_candidate,
        "effective_values": nominal,
        "candidate_status": (
            "applied"
            if aggregate_refit_allowed
            else "diagnostic_only_not_applied"
        ),
        "interpretation": (
            "Synthetic normalized series support an internal reduced-model "
            "quantile refit; this is not an empirical industrial estimate."
            if aggregate_refit_allowed
            else "Aggregate inventory, arrivals and production are not divided "
            "by finished-product demand because cross-item and bill-of-material "
            "unit comparability is not established. Declared reduced-model "
            "parameters remain research hypotheses."
        ),
    }
    pseudo_labeled = apply_calibrated_regime_labels(frame, thresholds)
    period_origin = _context_period_origin(context)
    annotations = load_regime_annotations(
        regime_annotations_path,
        period_origin=period_origin,
    )
    labeled, annotation_metadata = apply_regime_annotations(
        pseudo_labeled, annotations
    )

    evidence_metadata = {
        "label_provenance": annotation_metadata["label_provenance"],
        "annotation_status": annotation_metadata["status"],
        "annotation_schema_validation_status": annotation_metadata[
            "schema_validation_status"
        ],
        "annotation_source_path": annotation_metadata["source_path"],
        "annotation_rows": annotation_metadata["annotation_rows"],
        "annotated_days": annotation_metadata["annotated_days"],
        "matched_annotation_days": annotation_metadata["matched_annotation_days"],
        "business_label_days": annotation_metadata["business_label_days"],
        "pseudo_label_days": annotation_metadata["pseudo_label_days"],
        "annotation_coverage_fraction": annotation_metadata[
            "annotation_coverage_fraction"
        ],
        "business_label_coverage_fraction": annotation_metadata[
            "business_label_coverage_fraction"
        ],
        "annotation_conflict_day_count": annotation_metadata["conflict_day_count"],
        "annotation_source_conflict_day_count": annotation_metadata[
            "source_conflict_day_count"
        ],
        "annotation_tie_day_count": annotation_metadata["tie_day_count"],
        "annotation_zero_weight_day_count": annotation_metadata[
            "zero_weight_day_count"
        ],
    }
    for column, value in evidence_metadata.items():
        evidence[column] = value

    material_known_series = labeled.get(
        "material_cover_known", pd.Series(False, index=labeled.index)
    ).map(lambda value: optional_boolean(value) is True)
    material_cover_unknown_days = int((~material_known_series).sum())

    calibrated_config = deep_merge(base_config, {
        "regime_thresholds": thresholds,
        "nominal": nominal,
        "calibration": {
            "source_mode": context.source_mode,
            "baseline_path": context.baseline_path,
            "files": files,
            "days": int(len(frame)),
            "method": "robust_quantile_anchors_v1",
            "regime_rule_source": "core.classify_regime_signals",
            "material_cover_unknown_days": material_cover_unknown_days,
            "regime_annotations": annotation_metadata,
            "nominal_parameter_calibration": nominal_calibration,
        },
    })
    metadata = {
        "source_mode": context.source_mode,
        "baseline_path": context.baseline_path,
        "days": int(len(frame)),
        "files": files,
        "material_cover_source": str(labeled["material_cover_source"].mode().iloc[0]) if "material_cover_source" in labeled and not labeled.empty else "unknown",
        "material_cover_unknown_days": material_cover_unknown_days,
        "material_cover_status_counts": {
            str(key): int(value)
            for key, value in labeled.get(
                "material_cover_status",
                pd.Series("unknown", index=labeled.index),
            ).value_counts().items()
        },
        "regime_rule_source": "core.classify_regime_signals",
        "nominal_parameter_calibration": nominal_calibration,
        "calibration_risk_source": str(labeled["calibration_risk_source"].mode().iloc[0]) if "calibration_risk_source" in labeled and not labeled.empty else "unknown",
        "forecast_risk_is_dynamic": bool(int(labeled["forecast_risk_is_dynamic"].max())) if "forecast_risk_is_dynamic" in labeled and not labeled.empty else False,
        "regime_counts": {str(k): int(v) for k, v in labeled["calibrated_regime"].value_counts().items()},
        "pseudo_regime_counts": {
            str(k): int(v) for k, v in labeled["pseudo_regime"].value_counts().items()
        },
        "business_regime_counts": {
            str(k): int(v)
            for k, v in labeled["business_validated_regime"].dropna().value_counts().items()
        },
        "label_provenance": annotation_metadata["label_provenance"],
        "annotation_coverage_fraction": annotation_metadata[
            "annotation_coverage_fraction"
        ],
        "business_label_coverage_fraction": annotation_metadata[
            "business_label_coverage_fraction"
        ],
        "annotation_conflict_day_count": annotation_metadata["conflict_day_count"],
        "regime_annotations": annotation_metadata,
        "high_confidence_thresholds": int((evidence["confidence"] == "high").sum()),
        "medium_confidence_thresholds": int((evidence["confidence"] == "medium").sum()),
        "low_confidence_thresholds": int((evidence["confidence"] == "low").sum()),
    }
    return CalibrationArtifacts(labeled, evidence, calibrated_config, metadata)
