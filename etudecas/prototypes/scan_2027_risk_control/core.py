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


def first_existing_column(frame: pd.DataFrame, names: Iterable[str]) -> str | None:
    lower_map = {str(column).lower(): str(column) for column in frame.columns}
    return next((lower_map[name.lower()] for name in names if name.lower() in lower_map), None)


def read_numeric(frame: pd.DataFrame, names: Sequence[str], default: float = 0.0) -> pd.Series:
    column = first_existing_column(frame, names)
    if column is None:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def aggregate_baseline(frame: pd.DataFrame, days: int) -> tuple[pd.DataFrame, float]:
    work = frame.copy()
    day_column = first_existing_column(work, ["day", "sim_day", "day_index", "date_index"])
    work["_day"] = pd.to_numeric(work[day_column], errors="coerce") if day_column else np.arange(len(work))
    work = work.dropna(subset=["_day"])
    work["_day"] = work["_day"].astype(int)

    daily = pd.DataFrame(index=sorted(work["_day"].unique()))
    daily["demand"] = read_numeric(work, ["demand", "demand_qty", "customer_demand"]).groupby(work["_day"]).sum()
    daily["served"] = read_numeric(work, ["served", "served_qty", "shipments", "delivered_qty"]).groupby(work["_day"]).sum()
    daily["backlog"] = read_numeric(work, ["backlog", "ending_backlog", "customer_backlog"]).groupby(work["_day"]).sum()
    daily["arrivals"] = read_numeric(work, ["arrivals", "receipts", "received_qty"]).groupby(work["_day"]).sum()
    daily["produced"] = read_numeric(work, ["produced", "production", "production_qty"]).groupby(work["_day"]).sum()
    daily["inventory"] = read_numeric(work, ["inventory", "total_inventory", "on_hand"]).groupby(work["_day"]).sum()
    daily["orders"] = read_numeric(work, ["orders", "order_qty", "supplier_orders"]).groupby(work["_day"]).sum()
    daily = daily.fillna(0.0).reset_index(names="day").sort_values("day").head(days)
    if daily.empty or daily["demand"].max() <= 0:
        raise ValueError("baseline CSV does not expose usable daily demand")
    scale = float(daily["demand"].replace(0.0, np.nan).median())
    scale = max(scale, 1.0)
    for column in ["demand", "served", "backlog", "arrivals", "produced", "inventory", "orders"]:
        daily[column] = daily[column] / scale
    daily["demand"] = daily["demand"].clip(lower=0.05)
    return daily, scale


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


def load_risk_series(path: Path | None, days: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    if path and path.exists() and path.stat().st_size > 0:
        frame = pd.read_csv(path)
        probability_column = first_existing_column(frame, [
            "predicted_incident_probability_30d", "predicted_probability", "predicted_risk_probability",
            "risk_probability", "predicted_risk", "probability", "p_risk"
        ])
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
            return series, np.full(days, clamp(width, 0.04, 0.30))

    rng = np.random.default_rng(seed + 31)
    day = np.arange(days)
    base = 0.10 + 0.02 * np.sin(2 * np.pi * day / 45)
    pulse1 = 0.72 * np.exp(-0.5 * ((day - int(days * 0.40)) / max(3, days * 0.045)) ** 2)
    pulse2 = 0.58 * np.exp(-0.5 * ((day - int(days * 0.72)) / max(3, days * 0.04)) ** 2)
    series = np.clip(base + pulse1 + pulse2 + rng.normal(0, 0.015, days), 0.02, 0.96)
    return series, np.clip(0.07 + 0.13 * series, 0.05, 0.22)


def build_input_context(
    repo_root: Path, baseline_csv: str, risk_csv: str, days: int, seed: int,
    force_synthetic: bool, mapping_config: Mapping[str, Any] | None = None,
) -> RunContext:
    baseline_path: Path | None = None
    risk_path: Path | None = None
    if not force_synthetic:
        baseline_path = (Path(baseline_csv) if baseline_csv != "auto" else discover_latest_file(repo_root, [
            "etudecas/simulation/result/**/data/first_simulation_daily.csv",
            "etudecas/simulation/result/**/first_simulation_daily.csv",
        ]))
        if baseline_path and not baseline_path.is_absolute():
            baseline_path = (repo_root / baseline_path).resolve()

    if baseline_path and baseline_path.exists():
        raw = pd.read_csv(baseline_path)
        columns = [str(c) for c in raw.columns]
        daily, _ = aggregate_baseline(raw, days)
        mode, observability = "etudecas_baseline", 0.78
    else:
        daily = generate_synthetic_baseline(days, seed)
        columns = [str(c) for c in daily.columns]
        mode, observability, baseline_path = "synthetic_fallback", 0.62, None

    if risk_csv != "auto":
        risk_path = Path(risk_csv)
        if not risk_path.is_absolute():
            risk_path = (repo_root / risk_path).resolve()
    elif not force_synthetic:
        risk_path = discover_latest_file(repo_root, [
            "etudecas/prototypes/prediction/**/predicted_supplier_item_risk.csv",
            "etudecas/**/predicted_supplier_risk.csv",
        ])
    risk, uncertainty = load_risk_series(risk_path, len(daily), seed)
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
        interval, physical, interval_meta.__dict__,
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
