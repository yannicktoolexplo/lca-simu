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


@dataclass
class RunContext:
    input_series: pd.DataFrame
    source_mode: str
    baseline_path: str | None
    risk_path: str | None
    observability_base: float
    baseline_columns: list[str]


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
    scale = max(float(daily["demand"].replace(0.0, np.nan).median()), 1.0)
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
            "predicted_probability", "predicted_risk_probability", "risk_probability", "predicted_risk", "probability", "p_risk"
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


def build_input_context(repo_root: Path, baseline_csv: str, risk_csv: str, days: int, seed: int,
                        force_synthetic: bool) -> RunContext:
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
    daily = daily.copy()
    daily["base_risk"] = risk
    daily["risk_uncertainty"] = uncertainty
    reference = rolling_median(daily["demand"])
    daily["demand_ratio"] = (daily["demand"] / reference).clip(0.4, 2.5)
    daily["historical_service"] = (daily["served"] / daily["demand"].replace(0, np.nan)).clip(0, 1).fillna(1)
    daily["historical_nervousness"] = (daily["orders"].diff().abs() / reference).fillna(0).clip(0, 3)
    daily["historical_production_utilization"] = (
        daily["produced"] / daily["produced"].rolling(28, min_periods=7).quantile(0.95).replace(0, np.nan)
    ).fillna(0).clip(0, 2)
    return RunContext(daily, mode, str(baseline_path) if baseline_path else None,
                      str(risk_path) if risk_path and risk_path.exists() else None, observability, columns)


def correlated_noise(rng: np.random.Generator, length: int, sigma: float, correlation: float) -> np.ndarray:
    result = np.zeros(length)
    innovations = rng.normal(0.0, sigma, length)
    for i in range(1, length):
        result[i] = correlation * result[i - 1] + math.sqrt(max(0.0, 1 - correlation**2)) * innovations[i]
    return result


def sample_scenarios(count: int, length: int, config: Mapping[str, Any], seed: int) -> list[ScenarioPath]:
    cfg = config["uncertainty"]
    rng = np.random.default_rng(seed)
    scenarios: list[ScenarioPath] = []
    for _ in range(count):
        corr = safe_float(cfg["temporal_correlation"], 0.7)
        scenarios.append(ScenarioPath(
            demand_multiplier=np.clip(1 + correlated_noise(rng, length, safe_float(cfg["demand_sigma"]), corr), 0.65, 1.45),
            supply_shock=np.clip(correlated_noise(rng, length, safe_float(cfg["supply_sigma"]), corr), 0, 0.65),
            capacity_shock=np.clip(correlated_noise(rng, length, safe_float(cfg["capacity_sigma"]), corr), 0, 0.45),
            lead_time_shock=np.clip(correlated_noise(rng, length, safe_float(cfg["lead_time_sigma"]), corr), -0.15, 0.80),
            risk_noise=correlated_noise(rng, length, safe_float(cfg["risk_sigma"]), corr),
        ))
    return scenarios


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
