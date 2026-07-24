from __future__ import annotations

"""Calibration of state-dependent regimes on canonical etudecas trajectories."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .core import RunContext, clamp, deep_merge, first_existing_column, safe_float


@dataclass(frozen=True)
class CalibrationArtifacts:
    frame: pd.DataFrame
    evidence: pd.DataFrame
    config: dict[str, Any]
    metadata: dict[str, Any]


SIBLING_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "constraints": (
        "production_constraint_daily.csv",
        "data/production_constraint_daily.csv",
    ),
    "supplier_capacity": (
        "supplier_capacity_daily.csv",
        "data/supplier_capacity_daily.csv",
    ),
    "state_risk_events": (
        "supplier_state_risk_events.csv",
        "data/supplier_state_risk_events.csv",
    ),
    "factory_nervousness": (
        "factory_nervousness_daily.csv",
        "data/factory_nervousness_daily.csv",
    ),
    "supplier_risk_applied": (
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

    if stock_frame.empty or consumption_frame.empty:
        return pd.Series(dtype=float)
    stock_day = first_existing_column(stock_frame, ["day", "sim_day", "day_index"])
    consumption_day = first_existing_column(consumption_frame, ["day", "sim_day", "day_index"])
    node_stock = first_existing_column(stock_frame, ["node_id", "factory_id", "site_id"])
    item_stock = first_existing_column(stock_frame, ["item_id", "material_id", "component_id"])
    node_cons = first_existing_column(consumption_frame, ["node_id", "factory_id", "site_id"])
    item_cons = first_existing_column(consumption_frame, ["item_id", "material_id", "component_id"])
    stock_value = first_existing_column(stock_frame, [
        "stock_end_of_day", "stock_before_production", "stock_qty", "inventory_qty", "on_hand"
    ])
    consumption_value = first_existing_column(consumption_frame, [
        "consumed_qty", "consumption_qty", "required_qty", "input_consumption_qty"
    ])
    required = [stock_day, consumption_day, node_stock, item_stock, node_cons, item_cons, stock_value, consumption_value]
    if any(value is None for value in required):
        return pd.Series(dtype=float)

    stocks = pd.DataFrame({
        "day": pd.to_numeric(stock_frame[stock_day], errors="coerce"),
        "node_id": stock_frame[node_stock].astype(str),
        "item_id": stock_frame[item_stock].astype(str),
        "stock": pd.to_numeric(stock_frame[stock_value], errors="coerce"),
    }).dropna(subset=["day", "stock"])
    consumption = pd.DataFrame({
        "day": pd.to_numeric(consumption_frame[consumption_day], errors="coerce"),
        "node_id": consumption_frame[node_cons].astype(str),
        "item_id": consumption_frame[item_cons].astype(str),
        "consumption": pd.to_numeric(consumption_frame[consumption_value], errors="coerce"),
    }).dropna(subset=["day", "consumption"])
    if stocks.empty or consumption.empty:
        return pd.Series(dtype=float)
    stocks["day"] = stocks["day"].astype(int)
    consumption["day"] = consumption["day"].astype(int)
    stocks = stocks.groupby(["day", "node_id", "item_id"], as_index=False)["stock"].sum()
    consumption = consumption.groupby(["day", "node_id", "item_id"], as_index=False)["consumption"].sum()
    consumption = consumption.sort_values(["node_id", "item_id", "day"])
    consumption["reference_daily_consumption"] = consumption.groupby(["node_id", "item_id"])["consumption"].transform(
        lambda values: values.rolling(28, min_periods=3).median()
    )
    pair_median = consumption.groupby(["node_id", "item_id"])["consumption"].transform("median")
    consumption["reference_daily_consumption"] = consumption["reference_daily_consumption"].fillna(pair_median)
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

    detailed_cover = _detailed_material_cover_by_day(
        _read_optional(discovered.get("input_stocks")),
        _read_optional(discovered.get("input_consumption")),
    )
    if not detailed_cover.empty:
        frame = frame.merge(detailed_cover.rename("material_cover_days"), on="day", how="left")
        frame["material_cover_source"] = "pair_level_input_stock_and_consumption"
    else:
        # Fallback retained for self-contained and compact runs.  It is marked
        # explicitly because aggregate network inventory is a weaker proxy.
        frame["material_cover_days"] = frame["inventory_cover_days"].clip(0, 60)
        frame["material_cover_source"] = "aggregate_inventory_fallback"

    constraints = _read_optional(discovered.get("constraints"))
    if not constraints.empty:
        binding_columns = [column for column in constraints.columns if any(token in column.lower() for token in (
            "binding", "shortage", "constraint", "capacity_active", "limited"
        ))]
        if binding_columns:
            numeric = constraints[binding_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
            frame = frame.merge(
                _aggregate_by_day(constraints, (numeric.abs() > 1e-9).sum(axis=1), "sum").rename("constraint_activity"),
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

    frame = frame.fillna(0.0).sort_values("day").reset_index(drop=True)
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

    anchors = pd.DataFrame(index=frame.index)
    anchors["crisis"] = (frame["service"] <= min(0.92, service_q10)) | (
        frame["backlog_days"] >= _quantile(positive_backlog, 0.85, safe_float(defaults["crisis_backlog_days"]))
    )
    anchors["supplier_stress"] = (
        frame["state_risk_event_count"] > 0
    ) | (frame["calibration_risk_signal"] >= _quantile(
        frame["calibration_risk_signal"], 0.85, safe_float(defaults["supplier_risk"])
    ))
    anchors["capacity"] = (utilization >= _quantile(utilization, 0.88, safe_float(defaults["capacity_saturation"]))) | (
        frame["constraint_activity"] > 0
    )
    anchors["material"] = (
        frame["material_cover_days"] <= _quantile(frame.loc[frame["material_cover_days"] > 1e-9, "material_cover_days"], 0.12, safe_float(defaults["material_tension_days"]))
    ) & ((frame["backlog_delta"] > 0) | (frame["service"] < 0.99))
    anchors["oscillatory"] = (
        frame["nervousness"] >= _quantile(frame["nervousness"], 0.90, safe_float(defaults["oscillation_nervousness"]))
    ) & (frame["oscillation_index"] >= _quantile(frame["oscillation_index"], 0.75, 0.05))
    anchors["recovery"] = (frame["backlog_days"] > 0) & (frame["backlog_delta"] < 0) & (
        frame["service"].rolling(5, min_periods=1).mean() >= frame["service"].rolling(12, min_periods=1).mean()
    )
    anchors["overstock"] = (frame["inventory_cover_days"] >= _quantile(inventory_positive, 0.92, safe_float(defaults["overstock_days"]))) & (
        frame["backlog_days"] <= 0.02
    )

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

    calibrated = {
        "material_tension_days": _clip_threshold(
            "material_tension_days",
            _quantile(frame.loc[anchors["material"], "material_cover_days"], 0.75,
                      _quantile(frame.loc[frame["material_cover_days"] > 1e-9, "material_cover_days"], 0.12, safe_float(defaults["material_tension_days"]))),
        ),
        "capacity_saturation": _clip_threshold(
            "capacity_saturation",
            _quantile(utilization.loc[anchors["capacity"]], 0.30,
                      _quantile(utilization, 0.90, safe_float(defaults["capacity_saturation"]))),
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
            _quantile(frame.loc[anchors["oscillatory"], "nervousness"], 0.30,
                      _quantile(frame["nervousness"], 0.90, safe_float(defaults["oscillation_nervousness"]))),
        ),
        "crisis_backlog_days": _clip_threshold(
            "crisis_backlog_days",
            _quantile(frame.loc[anchors["crisis"], "backlog_days"], 0.30,
                      _quantile(positive_backlog, 0.85, safe_float(defaults["crisis_backlog_days"]))),
        ),
        "recovery_backlog_days": _clip_threshold(
            "recovery_backlog_days",
            _quantile(frame.loc[anchors["recovery"], "backlog_days"], 0.25,
                      safe_float(defaults["recovery_backlog_days"])),
        ),
        "overstock_days": _clip_threshold(
            "overstock_days",
            _quantile(frame.loc[anchors["overstock"], "inventory_cover_days"], 0.25,
                      _quantile(inventory_positive, 0.92, safe_float(defaults["overstock_days"]))),
        ),
    }

    feature_map = {
        "material_tension_days": ("material", "material_cover_days", "low"),
        "capacity_saturation": ("capacity", "max_utilization", "high"),
        "supplier_risk": ("supplier_stress", "base_risk", "high"),
        "supplier_stress": ("supplier_stress", "supplier_stress_proxy", "high"),
        "oscillation_nervousness": ("oscillatory", "nervousness", "high"),
        "crisis_backlog_days": ("crisis", "backlog_days", "high"),
        "recovery_backlog_days": ("recovery", "backlog_days", "contextual"),
        "overstock_days": ("overstock", "inventory_cover_days", "high"),
    }
    frame["max_utilization"] = utilization
    evidence_rows: list[dict[str, Any]] = []
    for threshold_name, (anchor_name, feature, direction) in feature_map.items():
        mask = anchors[anchor_name]
        positive = frame.loc[mask, feature]
        negative = frame.loc[~mask, feature]
        separation = _quantile(positive, 0.50, 0.0) - _quantile(negative, 0.50, 0.0)
        confidence = "high" if int(mask.sum()) >= 20 and abs(separation) > 0.05 else (
            "medium" if int(mask.sum()) >= 5 else "low"
        )
        if threshold_name == "supplier_risk" and not forecast_dynamic:
            confidence = "low"
        evidence_rows.append({
            "threshold": threshold_name,
            "calibrated_value": calibrated[threshold_name],
            "previous_value": safe_float(defaults[threshold_name]),
            "anchor": anchor_name,
            "feature": feature,
            "direction": direction,
            "anchor_days": int(mask.sum()),
            "non_anchor_days": int((~mask).sum()),
            "median_anchor": _quantile(positive, 0.50, 0.0),
            "median_non_anchor": _quantile(negative, 0.50, 0.0),
            "median_separation": float(separation),
            "confidence": confidence,
        })
    return calibrated, pd.DataFrame(evidence_rows)


def calibrate_nominal_parameters(frame: pd.DataFrame, base_config: Mapping[str, Any]) -> dict[str, float]:
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
    result = frame.copy()
    labels: list[str] = []
    previous_backlog = 0.0
    for _, row in result.iterrows():
        backlog = safe_float(row.get("backlog_days"))
        total_cover = safe_float(row.get("inventory_cover_days"))
        material_cover = safe_float(row.get("material_cover_days"), total_cover)
        utilization = max(safe_float(row.get("production_utilization")), safe_float(row.get("supplier_utilization")))
        if backlog >= safe_float(thresholds["crisis_backlog_days"]) and safe_float(row.get("service"), 1.0) < 0.95:
            label = "CRISIS"
        elif safe_float(row.get("base_risk")) >= safe_float(thresholds["supplier_risk"]) or safe_float(row.get("supplier_stress_proxy")) >= safe_float(thresholds["supplier_stress"]):
            label = "SUPPLIER_STRESS"
        elif safe_float(row.get("nervousness")) >= safe_float(thresholds["oscillation_nervousness"]) and backlog > 0.05:
            label = "OSCILLATORY"
        elif utilization >= safe_float(thresholds["capacity_saturation"]) and backlog > 0.02:
            label = "CAPACITY_SATURATION"
        elif material_cover <= safe_float(thresholds["material_tension_days"]):
            label = "MATERIAL_TENSION"
        elif previous_backlog > backlog and backlog >= safe_float(thresholds["recovery_backlog_days"]):
            label = "RECOVERY"
        elif total_cover >= safe_float(thresholds["overstock_days"]) and backlog <= 0.02:
            label = "POST_CRISIS_OVERSTOCK"
        else:
            label = "NOMINAL"
        labels.append(label)
        previous_backlog = backlog
    result["calibrated_regime"] = labels
    return result


def calibrate_from_context(context: RunContext, base_config: Mapping[str, Any]) -> CalibrationArtifacts:
    frame, files = build_calibration_frame(context)
    thresholds, evidence = calibrate_regime_thresholds(frame, base_config)
    nominal = calibrate_nominal_parameters(frame, base_config)
    calibrated_config = deep_merge(base_config, {
        "regime_thresholds": thresholds,
        "nominal": nominal,
        "calibration": {
            "source_mode": context.source_mode,
            "baseline_path": context.baseline_path,
            "files": files,
            "days": int(len(frame)),
            "method": "robust_quantile_anchors_v1",
        },
    })
    labeled = apply_calibrated_regime_labels(frame, thresholds)
    metadata = {
        "source_mode": context.source_mode,
        "baseline_path": context.baseline_path,
        "days": int(len(frame)),
        "files": files,
        "material_cover_source": str(labeled["material_cover_source"].mode().iloc[0]) if "material_cover_source" in labeled and not labeled.empty else "unknown",
        "calibration_risk_source": str(labeled["calibration_risk_source"].mode().iloc[0]) if "calibration_risk_source" in labeled and not labeled.empty else "unknown",
        "forecast_risk_is_dynamic": bool(int(labeled["forecast_risk_is_dynamic"].max())) if "forecast_risk_is_dynamic" in labeled and not labeled.empty else False,
        "regime_counts": {str(k): int(v) for k, v in labeled["calibrated_regime"].value_counts().items()},
        "high_confidence_thresholds": int((evidence["confidence"] == "high").sum()),
        "medium_confidence_thresholds": int((evidence["confidence"] == "medium").sum()),
        "low_confidence_thresholds": int((evidence["confidence"] == "low").sum()),
    }
    return CalibrationArtifacts(labeled, evidence, calibrated_config, metadata)
