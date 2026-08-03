from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

EPS = 1e-9


@dataclass(frozen=True)
class Action:
    name: str
    order_gain: float
    production_gain: float
    expedite: float
    smoothing: float
    safety_stock_gain: float
    supplier_relief: float
    description: str


@dataclass
class SimulationState:
    raw_inventory: float
    finished_inventory: float
    backlog: float
    pipeline: float
    previous_order: float
    supplier_stress: float
    supplier_risk: float
    previous_backlog: float = 0.0


@dataclass(frozen=True)
class ScenarioPath:
    demand_multiplier: np.ndarray
    supply_shock: np.ndarray
    capacity_shock: np.ndarray
    lead_time_shock: np.ndarray
    risk_noise: np.ndarray
    realized_risk_probability: np.ndarray | None = None
    quality_yield_multiplier: np.ndarray | None = None
    purchase_cost_multiplier: np.ndarray | None = None
    transport_cost_multiplier: np.ndarray | None = None
    scenario_seed: int | None = None


@dataclass
class RunContext:
    input_series: pd.DataFrame
    source_mode: str
    baseline_path: str | None
    risk_path: str | None
    observability_base: float
    baseline_columns: list[str]
    prediction_interval: pd.DataFrame | None = None
    physical_risk_envelope: pd.DataFrame | None = None
    prediction_interval_metadata: dict[str, Any] | None = None
    baseline_ingestion_metadata: dict[str, Any] | None = None


DEFAULT_ACTIONS: tuple[Action, ...] = (
    Action("mrp_reference", 0.00, 0.00, 0.00, 0.25, 0.00, 0.00,
           "Current planning response used as the comparison reference."),
    Action("reactive_buffer", 0.22, 0.10, 0.32, 0.05, 0.55, 0.00,
           "Aggressive protection: more orders, buffer and expedited flows."),
    Action("service_protection", 0.10, 0.16, 0.22, 0.35, 0.25, 0.15,
           "Protect service while limiting abrupt order changes."),
    Action("supplier_relief", -0.06, 0.00, 0.00, 0.82, 0.20, 0.75,
           "Reduce supplier pressure and stabilize the order signal."),
    Action("balanced_robust", 0.05, 0.07, 0.10, 0.58, 0.35, 0.40,
           "Balanced response designed for uncertain supplier risk."),
    Action("recovery_damping", -0.12, -0.04, 0.00, 0.78, -0.10, 0.55,
           "Damp orders and production during recovery."),
)


DEFAULT_CONFIG: dict[str, Any] = {
    "review_period_days": 7,
    "controller_horizon_days": 28,
    "controller_scenarios": 48,
    "policy_comparison_scenarios": 100,
    "risk_aversion": 0.55,
    "cvar_quantile": 0.90,
    "nominal": {
        "raw_inventory_days": 3.0,
        "finished_inventory_days": 1.2,
        "pipeline_days": 4.0,
        "supplier_capacity_ratio": 1.12,
        "production_capacity_ratio": 1.10,
        "base_lead_time_days": 5.0,
    },
    "uncertainty": {
        "demand_sigma": 0.08,
        "supply_sigma": 0.10,
        "capacity_sigma": 0.06,
        "lead_time_sigma": 0.12,
        "risk_sigma": 0.12,
        "temporal_correlation": 0.70,
    },
    "risk_dynamics": {
        "stress_memory": 0.86,
        "nervousness_gain": 0.44,
        "pressure_gain": 0.38,
        "expedite_gain": 0.22,
        "relief_gain": 0.32,
        "stress_to_risk_gain": 1.75,
        "risk_to_capacity_loss": 0.42,
        "risk_to_lead_time": 0.75,
    },
    "controller_weights": {
        "service_loss": 10.0,
        "backlog_area": 5.0,
        "inventory_area": 0.12,
        "inventory_shortfall": 2.4,
        "terminal_inventory_shortfall": 8.0,
        "terminal_pipeline_shortfall": 2.0,
        "nervousness": 1.8,
        "supplier_risk": 2.0,
        "risk_creation": 6.0,
        "expedite": 0.9,
        "action_magnitude": 0.45,
    },
    "limits": {
        "min_service": 0.92,
        "max_backlog_days": 4.0,
        "max_order_ratio": 1.55,
        "max_production_ratio": 1.35,
        "max_expedite": 0.40,
        "min_order_gain": -0.18,
        "max_order_gain": 0.28,
        "min_production_gain": -0.10,
        "max_production_gain": 0.22,
    },
    "physical_risk_mapping": {
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
    },
    "regime_thresholds": {
        "material_tension_days": 0.85,
        "capacity_saturation": 0.94,
        "supplier_risk": 0.68,
        "supplier_stress": 0.72,
        "oscillation_nervousness": 0.38,
        "crisis_backlog_days": 1.60,
        "recovery_backlog_days": 0.15,
        "overstock_days": 7.0,
    },
}


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return json.loads(json.dumps(DEFAULT_CONFIG))
    return deep_merge(DEFAULT_CONFIG, json.loads(path.read_text(encoding="utf-8")))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def sigmoid(value: float | np.ndarray) -> float | np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0)))


def logit(probability: float) -> float:
    p = clamp(probability, 1e-6, 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def rolling_median(series: pd.Series, window: int = 14) -> pd.Series:
    return series.rolling(window, min_periods=1).median().replace(0.0, np.nan).bfill().ffill()


def discover_latest_file(repo_root: Path, patterns: Sequence[str]) -> Path | None:
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(repo_root.glob(pattern))
    candidates = [path for path in candidates if path.is_file() and path.stat().st_size > 0]
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, float, str]:
        name = str(path).lower()
        priority = sum(value for token, value in (
            ("physical_floor", 5), ("reference_baseline", 4), ("mrp_bom", 3), ("baseline", 2)
        ) if token in name)
        return priority, path.stat().st_mtime, str(path)

    return max(candidates, key=score)


BASELINE_SIGNAL_COLUMNS: dict[str, tuple[str, ...]] = {
    "demand": ("demand", "demand_qty", "customer_demand"),
    "served": ("served", "served_qty", "shipments", "delivered_qty"),
    "backlog": ("backlog", "backlog_end", "ending_backlog", "customer_backlog"),
    "arrivals": ("arrivals", "arrivals_qty", "receipts", "received_qty"),
    "produced": ("produced", "produced_qty", "production", "production_qty"),
    "inventory": ("inventory", "inventory_total", "total_inventory", "on_hand"),
}


# The ordering and predicates below are the single executable definition of a
# SCAN regime.  Calibration and the operational controller both delegate to
# ``classify_regime_signals`` so that a threshold boundary cannot silently mean
# two different things in the two paths.
REGIME_PRIORITY: tuple[str, ...] = (
    "CRISIS",
    "SUPPLIER_STRESS",
    "OSCILLATORY",
    "CAPACITY_SATURATION",
    "MATERIAL_TENSION",
    "RECOVERY",
    "POST_CRISIS_OVERSTOCK",
    "NOMINAL",
)

REGIME_CLASSIFICATION_RULES: dict[str, str] = {
    "CRISIS": (
        "backlog_days >= crisis_backlog_days and "
        "(service < 0.95 or supplier_risk >= crisis_supplier_risk_floor)"
    ),
    "SUPPLIER_STRESS": (
        "supplier_risk >= supplier_risk or "
        "supplier_stress >= supplier_stress"
    ),
    "OSCILLATORY": (
        "nervousness >= oscillation_nervousness and backlog_days > 0.05"
    ),
    "CAPACITY_SATURATION": (
        "max(production_utilization, supplier_utilization) >= "
        "capacity_saturation and backlog_days > 0.02"
    ),
    "MATERIAL_TENSION": (
        "material_cover_known and material_cover_days <= material_tension_days"
    ),
    "RECOVERY": (
        "previous_backlog_days > backlog_days and "
        "backlog_days >= recovery_backlog_days"
    ),
    "POST_CRISIS_OVERSTOCK": (
        "inventory_cover_days >= overstock_days and backlog_days <= 0.02 and "
        "inventory_excess_ratio >= 1.05 and recent_disruption_signal > 0 and "
        "post_crisis_overstock_candidate > 0"
    ),
    "NOMINAL": "fallthrough after all higher-priority predicates are false",
}

REGIME_VARIABLES_USED: dict[str, tuple[str, ...]] = {
    "CRISIS": ("backlog_days", "service", "supplier_risk"),
    "SUPPLIER_STRESS": ("supplier_risk", "supplier_stress"),
    "OSCILLATORY": ("nervousness", "backlog_days"),
    "CAPACITY_SATURATION": (
        "production_utilization",
        "supplier_utilization",
        "backlog_days",
    ),
    "MATERIAL_TENSION": ("material_cover_days", "material_cover_known"),
    "RECOVERY": ("previous_backlog_days", "backlog_days"),
    "POST_CRISIS_OVERSTOCK": (
        "inventory_cover_days",
        "backlog_days",
        "inventory_excess_ratio",
        "recent_disruption_signal",
        "post_crisis_overstock_candidate",
    ),
    "NOMINAL": tuple(),
}


def _finite_optional(value: Any) -> float | None:
    """Return a finite float without converting an unknown signal to zero."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def optional_boolean(value: Any) -> bool | None:
    """Parse common boolean encodings without treating ``"False"`` as true."""

    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0", "", "nan", "none"}:
            return False
        return False
    numeric = _finite_optional(value)
    if numeric is None:
        return None
    return bool(numeric)


def classify_regime_signals(
    signals: Mapping[str, Any],
    thresholds: Mapping[str, Any],
) -> str:
    """Classify normalized physical signals using the shared SCAN predicates.

    Missing scalar signals use neutral defaults except material cover.  Material
    cover is intentionally tri-state: an absent/non-finite value, or an explicit
    false ``material_cover_known`` flag, cannot trigger ``MATERIAL_TENSION``.
    A finite observed zero remains a valid physical stockout signal.
    """

    def value(name: str, default: float = 0.0) -> float:
        resolved = _finite_optional(signals.get(name))
        return default if resolved is None else resolved

    backlog_days = max(0.0, value("backlog_days"))
    service = clamp(value("service", 1.0), 0.0, 1.0)
    supplier_risk = clamp(value("supplier_risk"), 0.0, 2.0)
    supplier_stress = max(0.0, value("supplier_stress"))
    nervousness = max(0.0, value("nervousness"))
    utilization = max(
        value("production_utilization"),
        value("supplier_utilization"),
    )
    previous_backlog_days = max(0.0, value("previous_backlog_days"))
    inventory_cover_days = max(0.0, value("inventory_cover_days"))

    material_cover = _finite_optional(signals.get("material_cover_days"))
    explicit_known = signals.get("material_cover_known")
    parsed_known = optional_boolean(explicit_known)
    material_cover_known = material_cover is not None and (
        parsed_known is None or parsed_known
    )

    if (
        backlog_days >= safe_float(thresholds.get("crisis_backlog_days"), 1.60)
        and (
            service < 0.95
            or supplier_risk
            >= safe_float(thresholds.get("crisis_supplier_risk_floor"), 0.55)
        )
    ):
        return "CRISIS"
    if (
        supplier_risk >= safe_float(thresholds.get("supplier_risk"), 0.68)
        or supplier_stress
        >= safe_float(thresholds.get("supplier_stress"), 0.72)
    ):
        return "SUPPLIER_STRESS"
    if (
        nervousness
        >= safe_float(thresholds.get("oscillation_nervousness"), 0.38)
        and backlog_days > 0.05
    ):
        return "OSCILLATORY"
    if (
        utilization
        >= safe_float(thresholds.get("capacity_saturation"), 0.94)
        and backlog_days > 0.02
    ):
        return "CAPACITY_SATURATION"
    if (
        material_cover_known
        and float(material_cover)
        <= safe_float(thresholds.get("material_tension_days"), 0.85)
    ):
        return "MATERIAL_TENSION"
    if (
        previous_backlog_days > backlog_days
        and backlog_days
        >= safe_float(thresholds.get("recovery_backlog_days"), 0.15)
    ):
        return "RECOVERY"
    if (
        inventory_cover_days
        >= safe_float(thresholds.get("overstock_days"), 7.0)
        and backlog_days <= 0.02
        and value("inventory_excess_ratio", 1.0) >= 1.05
        and value("recent_disruption_signal") > 0.0
        and value("post_crisis_overstock_candidate", 1.0) > 0.0
    ):
        return "POST_CRISIS_OVERSTOCK"
    return "NOMINAL"

DIRECT_ORDER_COLUMNS: tuple[str, ...] = (
    "orders",
    "order_qty",
    "supplier_orders",
    "ordered_qty",
)

CANONICAL_ORDER_COMPONENT_COLUMNS: tuple[str, ...] = (
    "external_procured_ordered_qty",
    "estimated_source_ordered_qty",
)

RISK_PROBABILITY_COLUMNS: tuple[str, ...] = (
    "predicted_incident_probability_30d",
    "predicted_probability",
    "predicted_risk_probability",
    "risk_probability",
    "predicted_risk",
    "probability",
    "p_risk",
    # Aggregate supplier output is a last-resort reduced-order source.  The
    # supplier-item-site file remains preferred because canonical replay needs
    # its destination and item identifiers.
    "mean_predicted_incident_probability_30d",
    "max_predicted_incident_probability_30d",
)


def _csv_columns(path: Path) -> list[str]:
    try:
        return [str(column) for column in pd.read_csv(path, nrows=0).columns]
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return []


def _baseline_candidate_score(path: Path) -> tuple[int, int, float, str]:
    """Rank canonical baseline candidates without mistaking risk tests for one."""

    normalized = str(path).replace("\\", "/").lower()
    parts = tuple(part.lower() for part in path.parts)
    score = 0
    if "baseline" in parts:
        score += 1_000
    if any(part == "reference_baseline" for part in parts):
        score += 800
    if "/replays/baseline/" in normalized:
        score += 500
    if "scenario_runs" in parts:
        score -= 400
    if "worstcase" in parts:
        score -= 500
    if "state_dependent" in normalized:
        score -= 250
    if "non_state_risk" in normalized or "risk_test" in normalized:
        score -= 180
    elif "risk" in normalized:
        score -= 80
    if "physical_floor" in normalized:
        score += 40
    if "mrp_bom" in normalized:
        score += 30

    columns = {column.lower() for column in _csv_columns(path)}
    required_groups = (
        BASELINE_SIGNAL_COLUMNS["demand"],
        BASELINE_SIGNAL_COLUMNS["served"],
        BASELINE_SIGNAL_COLUMNS["backlog"],
        BASELINE_SIGNAL_COLUMNS["inventory"],
    )
    schema_score = sum(
        1 for aliases in required_groups if any(alias.lower() in columns for alias in aliases)
    )
    if not any(alias.lower() in columns for alias in BASELINE_SIGNAL_COLUMNS["demand"]):
        score -= 2_000
    if not any(alias.lower() in columns for alias in BASELINE_SIGNAL_COLUMNS["served"]):
        score -= 1_000
    return score, schema_score, path.stat().st_mtime, str(path)


def discover_baseline_file(repo_root: Path) -> Path | None:
    candidates: list[Path] = []
    for pattern in (
        "etudecas/simulation/result/**/data/first_simulation_daily.csv",
        "etudecas/simulation/result/**/first_simulation_daily.csv",
    ):
        candidates.extend(repo_root.glob(pattern))
    candidates = [path for path in candidates if path.is_file() and path.stat().st_size > 0]
    return max(candidates, key=_baseline_candidate_score) if candidates else None


def _prediction_candidate_score(path: Path) -> tuple[int, int, int, float, str]:
    columns = _csv_columns(path)
    lower_columns = {column.lower() for column in columns}
    name = path.name.lower()
    granular = all(
        any(alias in lower_columns for alias in aliases)
        for aliases in (
            ("supplier_id", "supplier", "src_node_id"),
            ("item_id", "material_id", "component_id"),
            ("factory_id", "dst_node_id", "destination_node_id", "site_id"),
        )
    )
    probability = next(
        (column for column in RISK_PROBABILITY_COLUMNS if column.lower() in lower_columns),
        None,
    )
    score = 0
    if name == "predicted_supplier_item_risk.csv":
        score += 1_000
    if granular:
        score += 500
    if name == "predicted_supplier_risk.csv":
        score += 50
    if probability is None:
        score -= 2_000
    return score, int(granular), int(probability is not None), path.stat().st_mtime, str(path)


def discover_prediction_file(repo_root: Path) -> Path | None:
    candidates: list[Path] = []
    for pattern in (
        "etudecas/prototypes/prediction/**/predicted_supplier_item_risk.csv",
        "etudecas/**/predicted_supplier_item_risk.csv",
        "etudecas/**/predicted_supplier_risk.csv",
    ):
        candidates.extend(repo_root.glob(pattern))
    unique_candidates = {
        path.resolve(): path
        for path in candidates
        if path.is_file() and path.stat().st_size > 0
    }
    return max(unique_candidates.values(), key=_prediction_candidate_score) if unique_candidates else None


def first_existing_column(frame: pd.DataFrame, names: Iterable[str]) -> str | None:
    lower_map = {str(column).lower(): str(column) for column in frame.columns}
    return next((lower_map[name.lower()] for name in names if name.lower() in lower_map), None)


def read_numeric(frame: pd.DataFrame, names: Sequence[str], default: float = 0.0) -> pd.Series:
    column = first_existing_column(frame, names)
    if column is None:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def aggregate_baseline_with_metadata(
    frame: pd.DataFrame,
    days: int,
) -> tuple[pd.DataFrame, float, dict[str, Any]]:
    work = frame.copy()
    day_column = first_existing_column(work, ["day", "sim_day", "day_index", "date_index"])
    work["_day"] = pd.to_numeric(work[day_column], errors="coerce") if day_column else np.arange(len(work))
    work = work.dropna(subset=["_day"])
    work["_day"] = work["_day"].astype(int)

    daily = pd.DataFrame(index=sorted(work["_day"].unique()))
    signal_columns: dict[str, list[str]] = {}
    signal_known_by_day: dict[str, pd.Series] = {}
    for signal, aliases in BASELINE_SIGNAL_COLUMNS.items():
        column = first_existing_column(work, aliases)
        signal_columns[signal] = [column] if column else []
        if column is None:
            raw_signal = pd.Series(np.nan, index=work.index, dtype=float)
        else:
            raw_signal = pd.to_numeric(work[column], errors="coerce")
        signal_known_by_day[signal] = raw_signal.notna().groupby(work["_day"]).any()
        daily[signal] = raw_signal.fillna(0.0).groupby(work["_day"]).sum()

    # Material calibration must be able to distinguish a measured physical zero
    # from a missing/NaN aggregate-inventory row after backward-compatible daily
    # aggregation has filled other signals with zero.
    daily["inventory_signal_known"] = signal_known_by_day["inventory"].reindex(
        daily.index, fill_value=False
    )

    direct_order_column = first_existing_column(work, DIRECT_ORDER_COLUMNS)
    if direct_order_column:
        signal_columns["orders"] = [direct_order_column]
        order_values = pd.to_numeric(work[direct_order_column], errors="coerce").fillna(0.0)
        orders_source = "baseline_direct_order_column"
    else:
        component_columns = [
            column
            for name in CANONICAL_ORDER_COMPONENT_COLUMNS
            if (column := first_existing_column(work, [name])) is not None
        ]
        signal_columns["orders"] = component_columns
        if component_columns:
            order_values = work[component_columns].apply(
                pd.to_numeric, errors="coerce"
            ).fillna(0.0).sum(axis=1)
            orders_source = "baseline_canonical_procurement_components"
        else:
            order_values = pd.Series(0.0, index=work.index, dtype=float)
            orders_source = "missing"
    daily["orders"] = order_values.groupby(work["_day"]).sum()
    daily = daily.fillna(0.0).reset_index(names="day").sort_values("day").head(days)
    if daily.empty or daily["demand"].max() <= 0:
        raise ValueError("baseline CSV does not expose usable daily demand")
    scale = float(daily["demand"].replace(0.0, np.nan).median())
    scale = max(scale, 1.0)
    for column in ["demand", "served", "backlog", "arrivals", "produced", "inventory", "orders"]:
        daily[column] = daily[column] / scale
    daily["demand"] = daily["demand"].clip(lower=0.05)
    nonzero_rows = {
        column: int((pd.to_numeric(daily[column], errors="coerce").fillna(0.0).abs() > EPS).sum())
        for column in ["demand", "served", "backlog", "arrivals", "produced", "inventory", "orders"]
    }
    unknown_signal_days = {
        signal: int(
            (~known.reindex(daily["day"].astype(int), fill_value=False)).sum()
        )
        for signal, known in signal_known_by_day.items()
    }
    calendar_column = first_existing_column(
        work,
        (
            "calendar_date",
            "simulation_date",
            "date",
            "period",
            "timestamp",
        ),
    )
    period_origin: str | None = None
    period_origin_source: str | None = None
    if calendar_column is not None:
        calendar_values = pd.to_datetime(work[calendar_column], errors="coerce")
        usable_calendar = calendar_values.notna() & work["_day"].notna()
        if usable_calendar.any():
            candidate_origins = (
                calendar_values.loc[usable_calendar].dt.normalize()
                - pd.to_timedelta(work.loc[usable_calendar, "_day"], unit="D")
            )
            if candidate_origins.nunique() == 1:
                period_origin = candidate_origins.iloc[0].date().isoformat()
                period_origin_source = (
                    f"baseline_calendar_column:{calendar_column};"
                    f"day_column:{day_column or 'row_index'}"
                )
    metadata: dict[str, Any] = {
        "day_column": day_column,
        "signal_columns": signal_columns,
        "orders_source": orders_source,
        "normalization_demand_median": scale,
        "row_count": int(len(daily)),
        "nonzero_rows": nonzero_rows,
        "unknown_signal_days": unknown_signal_days,
        "missing_signals": [
            signal for signal, columns in signal_columns.items() if not columns
        ],
        "all_zero_signals": [
            signal for signal, count in nonzero_rows.items() if count == 0
        ],
        "calendar_column": calendar_column,
        "period_origin": period_origin,
        "period_origin_source": period_origin_source,
    }
    return daily, scale, metadata


def aggregate_baseline(frame: pd.DataFrame, days: int) -> tuple[pd.DataFrame, float]:
    """Backward-compatible baseline aggregation without provenance details."""

    daily, scale, _ = aggregate_baseline_with_metadata(frame, days)
    return daily, scale


def _load_mrp_order_signal(
    baseline_path: Path,
    days: int,
) -> tuple[pd.Series, dict[str, Any]] | None:
    candidates = (
        baseline_path.parent / "mrp_orders_daily.csv",
        baseline_path.parent.parent / "data" / "mrp_orders_daily.csv",
        baseline_path.parent / "production_orders_daily.csv",
        baseline_path.parent.parent / "data" / "production_orders_daily.csv",
    )
    order_path = next(
        (path for path in candidates if path.exists() and path.stat().st_size > 0),
        None,
    )
    if order_path is None:
        return None
    try:
        frame = pd.read_csv(order_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return None
    day_column = first_existing_column(frame, ["release_day", "day", "order_date_imt", "day_index"])
    quantity_column = first_existing_column(
        frame,
        ["release_qty", "planned_release_qty", "order_qty", "planned_receipt_qty"],
    )
    if day_column is None or quantity_column is None:
        return None
    day = pd.to_numeric(frame[day_column], errors="coerce")
    quantity = pd.to_numeric(frame[quantity_column], errors="coerce").fillna(0.0).clip(lower=0.0)
    work = pd.DataFrame({"day": day, "orders": quantity}).dropna(subset=["day"])
    work["day"] = work["day"].astype(int)
    work = work.loc[(work["day"] >= 0) & (work["day"] < days)]
    if work.empty:
        return None
    signal = work.groupby("day")["orders"].sum().reindex(range(days), fill_value=0.0)
    return signal, {
        "path": str(order_path),
        "day_column": day_column,
        "quantity_column": quantity_column,
        "rows_used": int(len(work)),
    }


def generate_synthetic_baseline(days: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    day = np.arange(days)
    demand = np.clip(
        1.0 + 0.12 * np.sin(2 * np.pi * day / 28) + 0.05 * np.sin(2 * np.pi * day / 7)
        + 0.001 * day + rng.normal(0.0, 0.035, days), 0.55, None
    )
    pulse = 0.45 * np.exp(-0.5 * ((day - int(days * 0.40)) / max(4, days * 0.05)) ** 2)
    pulse += 0.35 * np.exp(-0.5 * ((day - int(days * 0.72)) / max(4, days * 0.04)) ** 2)
    availability = np.clip(1.05 - 0.70 * pulse + rng.normal(0, 0.03, days), 0.18, 1.20)

    raw, finished, backlog, pipeline, previous_order = 3.0, 1.2, 0.0, 4.0, 1.0
    rows: list[dict[str, float | int]] = []
    for index in range(days):
        target = demand[index] + 0.25 * backlog + 0.20 * max(0.0, 3.0 - raw)
        order = previous_order + 0.32 * (target - previous_order)
        arrivals = min(pipeline / 5.0, 1.12 * availability[index])
        pipeline = max(0.0, pipeline + order - arrivals)
        raw += arrivals
        produced = min(1.10, raw, demand[index] + 0.35 * backlog + 0.10)
        raw -= produced
        finished += produced
        requirement = demand[index] + backlog
        served = min(requirement, finished)
        finished -= served
        backlog = max(0.0, requirement - served)
        rows.append({"day": index, "demand": demand[index], "served": served, "backlog": backlog,
                     "arrivals": arrivals, "produced": produced, "inventory": raw + finished, "orders": order})
        previous_order = order
    return pd.DataFrame(rows)


def load_risk_series_with_metadata(
    path: Path | None,
    days: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if path and path.exists() and path.stat().st_size > 0:
        frame = pd.read_csv(path)
        probability_column = first_existing_column(frame, RISK_PROBABILITY_COLUMNS)
        if probability_column:
            probabilities = pd.to_numeric(frame[probability_column], errors="coerce").dropna().clip(0, 1)
            level = float(probabilities.quantile(0.90)) if not probabilities.empty else 0.12
            series = np.full(days, clamp(level, 0.02, 0.98))
            day_column = first_existing_column(frame, ["day", "day_index", "date_index"])
            if day_column and not probabilities.empty:
                temp = pd.DataFrame({"day": pd.to_numeric(frame[day_column], errors="coerce"),
                                     "risk": pd.to_numeric(frame[probability_column], errors="coerce")}).dropna()
                daily = temp.groupby("day")["risk"].quantile(0.90).sort_index()
                series = daily.reindex(range(days)).interpolate().bfill().ffill().clip(0.02, 0.98).to_numpy()
            lower = first_existing_column(frame, ["lower_probability", "risk_lower", "lower_bound"])
            upper = first_existing_column(frame, ["upper_probability", "risk_upper", "upper_bound"])
            width = 0.10
            if lower and upper:
                values = (pd.to_numeric(frame[upper], errors="coerce") - pd.to_numeric(frame[lower], errors="coerce")).abs().dropna()
                if not values.empty:
                    width = float(values.median() / 2)
            granular_columns = {
                "supplier": first_existing_column(frame, ["supplier_id", "supplier", "src_node_id"]),
                "item": first_existing_column(frame, ["item_id", "material_id", "component_id"]),
                "destination": first_existing_column(
                    frame, ["factory_id", "dst_node_id", "destination_node_id", "site_id"]
                ),
            }
            return series, np.full(days, clamp(width, 0.04, 0.30)), {
                "input_status": "prediction_rows_consumed",
                "fallback_used": False,
                "fallback_reason": None,
                "source_path": str(path),
                "probability_column": probability_column,
                "lower_column": lower,
                "upper_column": upper,
                "day_column": day_column,
                "rows_used": int(probabilities.size),
                "granularity": (
                    "supplier_item_destination"
                    if all(granular_columns.values())
                    else "supplier_aggregate"
                ),
                "identifier_columns": granular_columns,
            }
        fallback_reason = "probability_column_missing"
    elif path is None:
        fallback_reason = "prediction_file_not_found"
    else:
        fallback_reason = "prediction_file_missing_or_empty"

    rng = np.random.default_rng(seed + 31)
    day = np.arange(days)
    base = 0.10 + 0.02 * np.sin(2 * np.pi * day / 45)
    pulse1 = 0.72 * np.exp(-0.5 * ((day - int(days * 0.40)) / max(3, days * 0.045)) ** 2)
    pulse2 = 0.58 * np.exp(-0.5 * ((day - int(days * 0.72)) / max(3, days * 0.04)) ** 2)
    series = np.clip(base + pulse1 + pulse2 + rng.normal(0, 0.015, days), 0.02, 0.96)
    return series, np.clip(0.07 + 0.13 * series, 0.05, 0.22), {
        "input_status": "synthetic_risk_fallback",
        "fallback_used": True,
        "fallback_reason": fallback_reason,
        "source_path": str(path) if path is not None else None,
        "probability_column": None,
        "lower_column": None,
        "upper_column": None,
        "day_column": None,
        "rows_used": 0,
        "granularity": "synthetic_portfolio_series",
        "identifier_columns": {
            "supplier": None,
            "item": None,
            "destination": None,
        },
    }


def load_risk_series(path: Path | None, days: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Backward-compatible risk-series loader without provenance details."""

    risk, uncertainty, _ = load_risk_series_with_metadata(path, days, seed)
    return risk, uncertainty


def build_input_context(
    repo_root: Path, baseline_csv: str, risk_csv: str, days: int, seed: int,
    force_synthetic: bool, mapping_config: Mapping[str, Any] | None = None,
) -> RunContext:
    baseline_path: Path | None = None
    risk_path: Path | None = None
    if not force_synthetic:
        baseline_path = (
            Path(baseline_csv)
            if baseline_csv != "auto"
            else discover_baseline_file(repo_root)
        )
        if baseline_path and not baseline_path.is_absolute():
            baseline_path = (repo_root / baseline_path).resolve()

    if baseline_path and baseline_path.exists():
        raw = pd.read_csv(baseline_path)
        columns = [str(c) for c in raw.columns]
        daily, scale, baseline_metadata = aggregate_baseline_with_metadata(raw, days)
        baseline_metadata.update({
            "input_status": "etudecas_baseline_consumed",
            "source_path": str(baseline_path),
            "selection_method": "explicit_path" if baseline_csv != "auto" else "scored_canonical_baseline_discovery",
        })
        if baseline_metadata["nonzero_rows"].get("orders", 0) == 0:
            sibling_orders = _load_mrp_order_signal(baseline_path, len(daily))
            if sibling_orders is not None:
                raw_orders, order_metadata = sibling_orders
                daily["orders"] = (
                    raw_orders.reindex(daily["day"].astype(int), fill_value=0.0).to_numpy(dtype=float)
                    / scale
                )
                nonzero_order_rows = int((daily["orders"].abs() > EPS).sum())
                if nonzero_order_rows > 0:
                    baseline_metadata["orders_source"] = "mrp_orders_daily_sibling"
                    baseline_metadata["signal_columns"]["orders"] = [
                        order_metadata["quantity_column"]
                    ]
                    baseline_metadata["orders_artifact"] = order_metadata
                    baseline_metadata["nonzero_rows"]["orders"] = nonzero_order_rows
                    baseline_metadata["missing_signals"] = [
                        signal for signal in baseline_metadata["missing_signals"] if signal != "orders"
                    ]
                    baseline_metadata["all_zero_signals"] = [
                        signal for signal in baseline_metadata["all_zero_signals"] if signal != "orders"
                    ]
        mode, observability = "etudecas_baseline", 0.78
    else:
        daily = generate_synthetic_baseline(days, seed)
        daily["inventory_signal_known"] = True
        columns = [str(c) for c in daily.columns]
        mode, observability, baseline_path = "synthetic_fallback", 0.62, None
        baseline_metadata = {
            "input_status": "synthetic_baseline_fallback",
            "source_path": None,
            "selection_method": "forced_synthetic" if force_synthetic else "baseline_not_found",
            "day_column": "day",
            "signal_columns": {column: [column] for column in daily.columns if column != "day"},
            "orders_source": "synthetic_generator",
            "row_count": int(len(daily)),
            "nonzero_rows": {
                column: int((daily[column].abs() > EPS).sum())
                for column in daily.columns if column != "day"
            },
            "missing_signals": [],
            "all_zero_signals": [
                column for column in daily.columns
                if column != "day" and not (daily[column].abs() > EPS).any()
            ],
        }

    if risk_csv != "auto":
        risk_path = Path(risk_csv)
        if not risk_path.is_absolute():
            risk_path = (repo_root / risk_path).resolve()
    elif not force_synthetic:
        risk_path = discover_prediction_file(repo_root)
    risk, uncertainty, risk_series_metadata = load_risk_series_with_metadata(
        risk_path, len(daily), seed
    )
    from .risk_mapping import build_prediction_interval_envelope, map_prediction_interval_to_physical

    interval, interval_meta = build_prediction_interval_envelope(
        risk_path,
        len(daily),
        fallback_center=risk,
        fallback_uncertainty=uncertainty,
        mapping_config=mapping_config or DEFAULT_CONFIG.get("physical_risk_mapping", {}),
    )
    physical = map_prediction_interval_to_physical(
        interval, mapping_config or DEFAULT_CONFIG.get("physical_risk_mapping", {})
    )
    interval_metadata = dict(interval_meta.__dict__)
    interval_metadata["risk_series_ingestion"] = risk_series_metadata
    interval_metadata["input_status"] = (
        "prediction_rows_consumed"
        if not bool(interval_metadata.get("fallback_used"))
        else "fallback_consumed"
    )
    daily = daily.copy()
    daily["base_risk"] = interval["risk_center"].to_numpy(dtype=float)
    daily["risk_uncertainty"] = (
        interval["risk_upper"].to_numpy(dtype=float) - interval["risk_lower"].to_numpy(dtype=float)
    ) / 2.0
    reference = rolling_median(daily["demand"])
    daily["demand_ratio"] = (daily["demand"] / reference).clip(0.4, 2.5)
    daily["historical_service"] = (daily["served"] / daily["demand"].replace(0, np.nan)).clip(0, 1).fillna(1)
    daily["historical_nervousness"] = (daily["orders"].diff().abs() / reference).fillna(0).clip(0, 3)
    daily["historical_production_utilization"] = (
        daily["produced"] / daily["produced"].rolling(28, min_periods=7).quantile(0.95).replace(0, np.nan)
    ).fillna(0).clip(0, 2)
    return RunContext(
        daily, mode, str(baseline_path) if baseline_path else None,
        str(risk_path) if risk_path and risk_path.exists() else None, observability, columns,
        interval, physical, interval_metadata, baseline_metadata,
    )


def correlated_noise(rng: np.random.Generator, length: int, sigma: float, correlation: float) -> np.ndarray:
    result = np.zeros(length)
    innovations = rng.normal(0.0, sigma, length)
    for i in range(1, length):
        result[i] = correlation * result[i - 1] + math.sqrt(max(0.0, 1 - correlation**2)) * innovations[i]
    return result


def _slice_or_pad(values: pd.Series | np.ndarray, start_day: int, length: int, default: float) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if len(array) == 0:
        return np.full(length, default, dtype=float)
    start = max(0, int(start_day))
    stop = min(len(array), start + length)
    sliced = array[start:stop]
    if len(sliced) < length:
        fill = float(sliced[-1]) if len(sliced) else float(array[-1])
        sliced = np.pad(sliced, (0, length - len(sliced)), constant_values=fill)
    return sliced.astype(float)


def sample_scenarios(
    count: int,
    length: int,
    config: Mapping[str, Any],
    seed: int,
    *,
    physical_risk: pd.DataFrame | None = None,
    start_day: int = 0,
) -> list[ScenarioPath]:
    """Sample common-random-number scenarios, optionally from prediction intervals."""

    cfg = config["uncertainty"]
    rng = np.random.default_rng(seed)
    scenarios: list[ScenarioPath] = []
    use_physical = physical_risk is not None and not physical_risk.empty
    if use_physical:
        from .risk_mapping import interpolate_interval

        columns: dict[str, np.ndarray] = {}
        for name, default in (
            ("risk_lower", 0.05), ("risk_center", 0.12), ("risk_upper", 0.25),
            ("availability_multiplier_lower", 1.0), ("availability_multiplier_center", 1.0), ("availability_multiplier_upper", 1.0),
            ("capacity_multiplier_lower", 1.0), ("capacity_multiplier_center", 1.0), ("capacity_multiplier_upper", 1.0),
            ("lead_time_extra_days_lower", 0.0), ("lead_time_extra_days_center", 0.0), ("lead_time_extra_days_upper", 0.0),
            ("quality_yield_multiplier_lower", 1.0), ("quality_yield_multiplier_center", 1.0), ("quality_yield_multiplier_upper", 1.0),
            ("purchase_cost_multiplier_lower", 1.0), ("purchase_cost_multiplier_center", 1.0), ("purchase_cost_multiplier_upper", 1.0),
            ("transport_cost_multiplier_lower", 1.0), ("transport_cost_multiplier_center", 1.0), ("transport_cost_multiplier_upper", 1.0),
        ):
            if name in physical_risk:
                columns[name] = _slice_or_pad(physical_risk[name], start_day, length, default)
            else:
                columns[name] = np.full(length, default, dtype=float)

    for scenario_index in range(count):
        corr = safe_float(cfg["temporal_correlation"], 0.7)
        demand_multiplier = np.clip(
            1 + correlated_noise(rng, length, safe_float(cfg["demand_sigma"]), corr), 0.65, 1.45
        )
        base_supply = np.clip(correlated_noise(rng, length, safe_float(cfg["supply_sigma"]), corr), 0, 0.65)
        base_capacity = np.clip(correlated_noise(rng, length, safe_float(cfg["capacity_sigma"]), corr), 0, 0.45)
        base_lead = np.clip(correlated_noise(rng, length, safe_float(cfg["lead_time_sigma"]), corr), -0.15, 0.80)
        risk_noise = correlated_noise(rng, length, safe_float(cfg["risk_sigma"]), corr)
        if use_physical:
            latent = correlated_noise(rng, length, 1.0, corr)
            realized_risk = np.clip(interpolate_interval(
                columns["risk_lower"], columns["risk_center"], columns["risk_upper"], latent
            ), 0.01, 0.995)
            # Use the same latent quantile for probability and physical effects.
            # The multiplier curves are decreasing with risk, which the linear
            # interpolation handles naturally; reversing the endpoints would
            # incorrectly associate high risk with high availability.
            availability = interpolate_interval(
                columns["availability_multiplier_lower"],
                columns["availability_multiplier_center"],
                columns["availability_multiplier_upper"],
                latent,
            )
            capacity = interpolate_interval(
                columns["capacity_multiplier_lower"],
                columns["capacity_multiplier_center"],
                columns["capacity_multiplier_upper"],
                latent,
            )
            lead_extra = interpolate_interval(
                columns["lead_time_extra_days_lower"],
                columns["lead_time_extra_days_center"],
                columns["lead_time_extra_days_upper"],
                latent,
            )
            quality = interpolate_interval(
                columns["quality_yield_multiplier_lower"],
                columns["quality_yield_multiplier_center"],
                columns["quality_yield_multiplier_upper"],
                latent,
            )
            purchase_cost = interpolate_interval(
                columns["purchase_cost_multiplier_lower"],
                columns["purchase_cost_multiplier_center"],
                columns["purchase_cost_multiplier_upper"],
                latent,
            )
            transport_cost = interpolate_interval(
                columns["transport_cost_multiplier_lower"],
                columns["transport_cost_multiplier_center"],
                columns["transport_cost_multiplier_upper"],
                latent,
            )
            nominal_lead = max(1.0, safe_float(config["nominal"]["base_lead_time_days"], 5.0))
            supply_shock = np.clip((1.0 - availability) + 0.35 * base_supply, 0.0, 0.85)
            capacity_shock = np.clip((1.0 - capacity) + 0.35 * base_capacity, 0.0, 0.75)
            lead_time_shock = np.clip(lead_extra / nominal_lead + 0.35 * base_lead, -0.15, 2.0)
        else:
            realized_risk = None
            quality = None
            purchase_cost = None
            transport_cost = None
            supply_shock = base_supply
            capacity_shock = base_capacity
            lead_time_shock = base_lead
        scenarios.append(ScenarioPath(
            demand_multiplier=demand_multiplier,
            supply_shock=supply_shock,
            capacity_shock=capacity_shock,
            lead_time_shock=lead_time_shock,
            risk_noise=risk_noise,
            realized_risk_probability=realized_risk,
            quality_yield_multiplier=quality,
            purchase_cost_multiplier=purchase_cost,
            transport_cost_multiplier=transport_cost,
            scenario_seed=int(seed + scenario_index),
        ))
    return scenarios


def central_scenario_from_physical(
    physical_risk: pd.DataFrame | None,
    length: int,
    config: Mapping[str, Any],
    *,
    start_day: int = 0,
) -> ScenarioPath:
    if physical_risk is None or physical_risk.empty:
        return no_uncertainty_scenario(length)
    nominal_lead = max(1.0, safe_float(config["nominal"]["base_lead_time_days"], 5.0))
    center = lambda name, default: _slice_or_pad(physical_risk[name], start_day, length, default) if name in physical_risk else np.full(length, default)
    availability = center("availability_multiplier_center", 1.0)
    capacity = center("capacity_multiplier_center", 1.0)
    lead_extra = center("lead_time_extra_days_center", 0.0)
    return ScenarioPath(
        demand_multiplier=np.ones(length),
        supply_shock=np.clip(1.0 - availability, 0.0, 0.85),
        capacity_shock=np.clip(1.0 - capacity, 0.0, 0.75),
        lead_time_shock=np.clip(lead_extra / nominal_lead, -0.15, 2.0),
        risk_noise=np.zeros(length),
        realized_risk_probability=np.clip(center("risk_center", 0.12), 0.01, 0.995),
        quality_yield_multiplier=np.clip(center("quality_yield_multiplier_center", 1.0), 0.25, 1.0),
        purchase_cost_multiplier=np.clip(center("purchase_cost_multiplier_center", 1.0), 1.0, 3.0),
        transport_cost_multiplier=np.clip(center("transport_cost_multiplier_center", 1.0), 1.0, 3.0),
    )


def slice_scenario(scenario: ScenarioPath, start: int, length: int) -> ScenarioPath:
    def sliced(value: np.ndarray | None, default: float) -> np.ndarray | None:
        return None if value is None else _slice_or_pad(value, start, length, default)
    return ScenarioPath(
        demand_multiplier=_slice_or_pad(scenario.demand_multiplier, start, length, 1.0),
        supply_shock=_slice_or_pad(scenario.supply_shock, start, length, 0.0),
        capacity_shock=_slice_or_pad(scenario.capacity_shock, start, length, 0.0),
        lead_time_shock=_slice_or_pad(scenario.lead_time_shock, start, length, 0.0),
        risk_noise=_slice_or_pad(scenario.risk_noise, start, length, 0.0),
        realized_risk_probability=sliced(scenario.realized_risk_probability, 0.12),
        quality_yield_multiplier=sliced(scenario.quality_yield_multiplier, 1.0),
        purchase_cost_multiplier=sliced(scenario.purchase_cost_multiplier, 1.0),
        transport_cost_multiplier=sliced(scenario.transport_cost_multiplier, 1.0),
        scenario_seed=scenario.scenario_seed,
    )


def no_uncertainty_scenario(length: int) -> ScenarioPath:
    return ScenarioPath(np.ones(length), np.zeros(length), np.zeros(length), np.zeros(length), np.zeros(length))


def initial_state(config: Mapping[str, Any], first_demand: float, first_risk: float) -> SimulationState:
    nominal = config["nominal"]
    return SimulationState(
        safe_float(nominal["raw_inventory_days"], 3) * first_demand,
        safe_float(nominal["finished_inventory_days"], 1.2) * first_demand,
        0.0,
        safe_float(nominal["pipeline_days"], 4) * first_demand,
        first_demand,
        0.05,
        first_risk,
        0.0,
    )


def safety_filter(action: Action, config: Mapping[str, Any]) -> Action:
    limits = config["limits"]
    return replace(
        action,
        order_gain=clamp(action.order_gain, safe_float(limits["min_order_gain"]), safe_float(limits["max_order_gain"])),
        production_gain=clamp(action.production_gain, safe_float(limits["min_production_gain"]), safe_float(limits["max_production_gain"])),
        expedite=clamp(action.expedite, 0.0, safe_float(limits["max_expedite"])),
        smoothing=clamp(action.smoothing, 0.0, 1.0),
    )
