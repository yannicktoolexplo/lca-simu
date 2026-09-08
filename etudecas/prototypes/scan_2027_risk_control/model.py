from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import (
    EPS,
    Action,
    ScenarioPath,
    SimulationState,
    clamp,
    classify_regime_signals,
    logit,
    safe_float,
    safety_filter,
    sigmoid,
)


def simulate_step(state: SimulationState, action: Action, base_demand: float, base_risk: float,
                  scenario: ScenarioPath, step_index: int, config: Mapping[str, Any]) -> tuple[SimulationState, dict[str, float]]:
    nominal, risk_cfg, limits = config["nominal"], config["risk_dynamics"], config["limits"]
    action = safety_filter(action, config)
    demand = max(0.05, base_demand * float(scenario.demand_multiplier[step_index]))
    supplier_capacity = safe_float(nominal["supplier_capacity_ratio"], 1.12) * demand
    production_capacity = safe_float(nominal["production_capacity_ratio"], 1.10) * demand

    raw_target = (safe_float(nominal["raw_inventory_days"], 3.0) + action.safety_stock_gain) * demand
    finished_target = max(0.2, safe_float(nominal["finished_inventory_days"], 1.2) + 0.25 * action.safety_stock_gain) * demand
    order_target = (demand + 0.35 * state.backlog + 0.18 * max(0.0, raw_target - state.raw_inventory)) * max(0.0, 1 + action.order_gain)
    adjustment = 0.10 + 0.65 * (1.0 - action.smoothing)
    order = state.previous_order + adjustment * (order_target - state.previous_order)
    order = clamp(order, 0.0, safe_float(limits["max_order_ratio"], 1.55) * demand)
    nervousness = abs(order - state.previous_order) / max(demand, EPS)
    supplier_pressure = max(0.0, order - supplier_capacity) / max(supplier_capacity, EPS)

    stress = (
        safe_float(risk_cfg["stress_memory"], 0.86) * state.supplier_stress
        + safe_float(risk_cfg["nervousness_gain"], 0.44) * nervousness
        + safe_float(risk_cfg["pressure_gain"], 0.38) * supplier_pressure
        + safe_float(risk_cfg["expedite_gain"], 0.22) * action.expedite
        - safe_float(risk_cfg["relief_gain"], 0.32) * action.supplier_relief
    )
    stress = clamp(stress, 0.0, 2.0)
    realized_base_risk = (
        float(scenario.realized_risk_probability[step_index])
        if scenario.realized_risk_probability is not None
        else float(base_risk)
    )
    risk_value = float(sigmoid(
        logit(clamp(realized_base_risk, 0.01, 0.99))
        + safe_float(risk_cfg["stress_to_risk_gain"], 1.75) * stress
        + float(scenario.risk_noise[step_index])
    ))
    risk_value = clamp(risk_value, 0.01, 0.995)
    # The prediction interval is already translated into physical lead-time,
    # capacity and availability shocks by risk_mapping.py.  Only the incremental
    # risk created by our own response is fed back here; using total risk would
    # count the exogenous forecast twice.
    endogenous_risk_increment = max(0.0, risk_value - realized_base_risk)

    lead_time = safe_float(nominal["base_lead_time_days"], 5.0) * (
        1.0 + safe_float(risk_cfg["risk_to_lead_time"], 0.75) * endogenous_risk_increment
        + float(scenario.lead_time_shock[step_index]) - 0.22 * action.expedite
    )
    lead_time = clamp(lead_time, 1.0, 30.0)
    availability = 1.0 - safe_float(risk_cfg["risk_to_capacity_loss"], 0.42) * endogenous_risk_increment
    availability -= float(scenario.supply_shock[step_index])
    availability += 0.10 * action.expedite
    availability = clamp(availability, 0.05, 1.15)
    supply_capacity = supplier_capacity * availability
    gross_arrivals = min(state.pipeline / lead_time, supply_capacity)
    quality_yield = (
        float(scenario.quality_yield_multiplier[step_index])
        if scenario.quality_yield_multiplier is not None
        else 1.0
    )
    quality_yield = clamp(quality_yield, 0.25, 1.0)
    arrivals = gross_arrivals * quality_yield
    quality_loss = max(0.0, gross_arrivals - arrivals)
    pipeline = max(0.0, state.pipeline + order - gross_arrivals)
    raw_inventory = max(0.0, state.raw_inventory + arrivals)

    desired_production = demand + 0.42 * state.backlog + 0.15 * max(0.0, finished_target - state.finished_inventory)
    desired_production *= max(0.0, 1 + action.production_gain)
    capacity_factor = max(0.35, 1.0 - float(scenario.capacity_shock[step_index]))
    production_capacity_effective = min(
        safe_float(limits["max_production_ratio"], 1.35) * demand,
        production_capacity * max(0.0, 1 + action.production_gain) * capacity_factor,
    )
    production = min(desired_production, production_capacity_effective, raw_inventory)
    raw_inventory = max(0.0, raw_inventory - production)
    finished_inventory = max(0.0, state.finished_inventory + production)
    requirement = demand + state.backlog
    served_total = min(requirement, finished_inventory)
    finished_inventory = max(0.0, finished_inventory - served_total)
    backlog = max(0.0, requirement - served_total)
    service = min(demand, served_total) / max(demand, EPS)

    production_utilization = production / max(production_capacity_effective, EPS)
    supplier_utilization = arrivals / max(supply_capacity, EPS)
    purchase_cost_multiplier = (
        float(scenario.purchase_cost_multiplier[step_index])
        if scenario.purchase_cost_multiplier is not None
        else 1.0
    )
    transport_cost_multiplier = (
        float(scenario.transport_cost_multiplier[step_index])
        if scenario.transport_cost_multiplier is not None
        else 1.0
    )
    purchase_cost_proxy = gross_arrivals * max(1.0, purchase_cost_multiplier)
    transport_cost_proxy = gross_arrivals * max(1.0, transport_cost_multiplier) * (1.0 + action.expedite)
    next_state = SimulationState(raw_inventory, finished_inventory, backlog, pipeline, order, stress, risk_value, state.backlog)
    metrics = {
        "demand": demand,
        "served": min(demand, served_total),
        "service": service,
        "backlog": backlog,
        "backlog_recovery": max(0.0, state.backlog - backlog),
        "raw_inventory": raw_inventory,
        "finished_inventory": finished_inventory,
        "inventory_total": raw_inventory + finished_inventory,
        "pipeline": pipeline,
        "order": order,
        "arrivals": arrivals,
        "gross_arrivals": gross_arrivals,
        "quality_yield": quality_yield,
        "quality_loss": quality_loss,
        "production": production,
        "nervousness": nervousness,
        "supplier_pressure": supplier_pressure,
        "supplier_stress": stress,
        "supplier_risk": risk_value,
        "forecast_risk": float(base_risk),
        "realized_base_risk": realized_base_risk,
        "lead_time": lead_time,
        "production_utilization": production_utilization,
        "supplier_utilization": supplier_utilization,
        "expedite": action.expedite,
        "purchase_cost_multiplier": purchase_cost_multiplier,
        "transport_cost_multiplier": transport_cost_multiplier,
        "purchase_cost_proxy": purchase_cost_proxy,
        "transport_cost_proxy": transport_cost_proxy,
        "action_magnitude": abs(action.order_gain) + abs(action.production_gain) + action.expedite
        + abs(action.safety_stock_gain) * 0.25 + action.supplier_relief * 0.20,
    }
    return next_state, metrics


def simulate_horizon(initial: SimulationState, action: Action, demand_path: np.ndarray, risk_path: np.ndarray,
                     scenario: ScenarioPath, config: Mapping[str, Any]) -> tuple[pd.DataFrame, SimulationState]:
    state = replace(initial)
    rows: list[dict[str, float | int | str]] = []
    for index in range(len(demand_path)):
        state, metrics = simulate_step(state, action, float(demand_path[index]), float(risk_path[index]), scenario, index, config)
        rows.append({"step": index, "policy": action.name, **metrics})
    return pd.DataFrame(rows), state


def classify_regime(state: SimulationState, metrics: Mapping[str, float], config: Mapping[str, Any]) -> str:
    """Classify the operational state with the shared calibration predicates.

    ``material_cover_days`` may be supplied explicitly by a richer physical
    engine.  The reduced model otherwise has an observed raw-inventory state,
    which is a valid material-cover measurement rather than an imputed zero.
    Post-crisis context is taken from explicit metrics when available; the
    one-step ``previous_backlog`` state supplies the conservative fallback.
    """

    thresholds = config["regime_thresholds"]
    demand = max(safe_float(metrics.get("demand"), 1.0), EPS)
    raw_days = state.raw_inventory / demand
    finished_days = state.finished_inventory / demand
    backlog_days = state.backlog / demand
    total_inventory_days = raw_days + finished_days
    nominal_inventory_days = max(
        safe_float(config.get("nominal", {}).get("raw_inventory_days"), 3.0)
        + safe_float(
            config.get("nominal", {}).get("finished_inventory_days"), 1.2
        ),
        EPS,
    )
    material_cover_supplied = "material_cover_days" in metrics
    material_cover = (
        metrics.get("material_cover_days") if material_cover_supplied else raw_days
    )
    material_cover_known = metrics.get(
        "material_cover_known",
        True if not material_cover_supplied else None,
    )
    recent_disruption = metrics.get(
        "recent_disruption_signal",
        float(state.previous_backlog > 0.0),
    )
    return classify_regime_signals(
        {
            "backlog_days": backlog_days,
            "previous_backlog_days": state.previous_backlog / demand,
            "service": metrics.get("service", 1.0),
            "supplier_risk": state.supplier_risk,
            "supplier_stress": state.supplier_stress,
            "nervousness": metrics.get("nervousness", 0.0),
            "production_utilization": metrics.get(
                "production_utilization", 0.0
            ),
            "supplier_utilization": metrics.get("supplier_utilization", 0.0),
            "material_cover_days": material_cover,
            "material_cover_known": material_cover_known,
            "inventory_cover_days": total_inventory_days,
            "inventory_excess_ratio": metrics.get(
                "inventory_excess_ratio",
                total_inventory_days / nominal_inventory_days,
            ),
            "recent_disruption_signal": recent_disruption,
            "post_crisis_overstock_candidate": metrics.get(
                "post_crisis_overstock_candidate", 1.0
            ),
        },
        thresholds,
    )


def local_observability_score(base_score: float, state: SimulationState, risk_uncertainty: float,
                              metrics: Mapping[str, float]) -> float:
    penalty = 0.55 * clamp(risk_uncertainty, 0.0, 0.50) + 0.08 * clamp(state.supplier_stress, 0.0, 2.0)
    penalty += 0.08 if safe_float(metrics.get("arrivals"), 0.0) <= EPS else 0.0
    return clamp(base_score - penalty, 0.0, 1.0)


def local_controllability_score(state: SimulationState, metrics: Mapping[str, float], config: Mapping[str, Any]) -> float:
    demand = max(safe_float(metrics.get("demand"), 1.0), EPS)
    raw_cover = clamp(state.raw_inventory / demand / 4.0, 0.0, 1.0)
    production_headroom = clamp(1.0 - safe_float(metrics.get("production_utilization"), 0.0), 0.0, 1.0)
    supplier_headroom = clamp(1.0 - safe_float(metrics.get("supplier_utilization"), 0.0), 0.0, 1.0)
    backlog_penalty = clamp(state.backlog / demand / safe_float(config["limits"]["max_backlog_days"], 4.0), 0.0, 1.0)
    return clamp(0.28 * raw_cover + 0.28 * production_headroom + 0.24 * supplier_headroom + 0.13 - 0.30 * backlog_penalty, 0.0, 1.0)


def policy_objective(trajectory: pd.DataFrame, reference: pd.DataFrame, config: Mapping[str, Any]) -> dict[str, float]:
    w, limits, nominal = config["controller_weights"], config["limits"], config["nominal"]
    target = safe_float(nominal["raw_inventory_days"], 3.0) + safe_float(nominal["finished_inventory_days"], 1.2)
    minimum_buffer = max(0.8, 0.35 * target)
    result = {
        "service_loss": float((1 - trajectory["service"]).clip(lower=0).sum()),
        "backlog_area": float(trajectory["backlog"].sum()),
        "inventory_area": float((trajectory["inventory_total"] - target).clip(lower=0).sum()),
        "inventory_shortfall": float((minimum_buffer - trajectory["inventory_total"]).clip(lower=0).sum()),
        "terminal_inventory_shortfall": max(0.0, target - float(trajectory["inventory_total"].iloc[-1])),
        "terminal_pipeline_shortfall": max(0.0, safe_float(nominal["pipeline_days"], 4.0) - float(trajectory["pipeline"].iloc[-1])),
        "nervousness": float(trajectory["nervousness"].sum()),
        "risk_area": float(trajectory["supplier_risk"].sum()),
        "risk_creation": float((trajectory["supplier_risk"] - reference["supplier_risk"]).clip(lower=0).mean()),
        "expedite": float(trajectory["expedite"].sum()),
        "quality_loss": float(trajectory.get("quality_loss", pd.Series(0.0, index=trajectory.index)).sum()),
        "purchase_cost_proxy": float(trajectory.get("purchase_cost_proxy", pd.Series(0.0, index=trajectory.index)).sum()),
        "transport_cost_proxy": float(trajectory.get("transport_cost_proxy", pd.Series(0.0, index=trajectory.index)).sum()),
        "action_magnitude": float(trajectory["action_magnitude"].sum()),
        "min_service": float(trajectory["service"].min()),
        "max_backlog": float(trajectory["backlog"].max()),
        "final_risk": float(trajectory["supplier_risk"].iloc[-1]),
    }
    violation = float((trajectory["service"] < safe_float(limits["min_service"], 0.92)).sum()) * 4.0
    violation += float((trajectory["backlog"] - safe_float(limits["max_backlog_days"], 4.0)).clip(lower=0).sum()) * 20.0
    result["constraint_violation"] = violation
    result["score"] = (
        safe_float(w["service_loss"]) * result["service_loss"] + safe_float(w["backlog_area"]) * result["backlog_area"]
        + safe_float(w["inventory_area"]) * result["inventory_area"] + safe_float(w["inventory_shortfall"]) * result["inventory_shortfall"]
        + safe_float(w["terminal_inventory_shortfall"]) * result["terminal_inventory_shortfall"]
        + safe_float(w["terminal_pipeline_shortfall"]) * result["terminal_pipeline_shortfall"]
        + safe_float(w["nervousness"]) * result["nervousness"] + safe_float(w["supplier_risk"]) * result["risk_area"]
        + safe_float(w["risk_creation"]) * result["risk_creation"] * len(trajectory)
        + safe_float(w["expedite"]) * result["expedite"] + safe_float(w["action_magnitude"]) * result["action_magnitude"] + violation
    )
    return result


def cvar(values: Sequence[float], quantile: float) -> float:
    array = np.asarray(values, dtype=float)
    if len(array) == 0:
        return 0.0
    threshold = float(np.quantile(array, quantile))
    tail = array[array >= threshold]
    return float(tail.mean()) if len(tail) else threshold


def evaluate_actions(initial: SimulationState, actions: Sequence[Action], demand_path: np.ndarray, risk_path: np.ndarray,
                     scenarios: Sequence[ScenarioPath], config: Mapping[str, Any]) -> pd.DataFrame:
    from .core import DEFAULT_ACTIONS
    reference_action = next(a for a in DEFAULT_ACTIONS if a.name == "mrp_reference")
    references = [simulate_horizon(initial, reference_action, demand_path, risk_path, scenario, config)[0] for scenario in scenarios]
    rows: list[dict[str, float | str]] = []
    keys = ["service_loss", "backlog_area", "inventory_area", "inventory_shortfall",
            "terminal_inventory_shortfall", "terminal_pipeline_shortfall", "nervousness", "risk_area",
            "risk_creation", "expedite", "quality_loss", "purchase_cost_proxy", "transport_cost_proxy",
            "action_magnitude", "constraint_violation", "min_service", "max_backlog", "final_risk"]
    for action in actions:
        metrics = []
        for scenario, reference in zip(scenarios, references):
            trajectory, _ = simulate_horizon(initial, safety_filter(action, config), demand_path, risk_path, scenario, config)
            metrics.append(policy_objective(trajectory, reference, config))
        scores = [m["score"] for m in metrics]
        expected, tail = float(np.mean(scores)), cvar(scores, safe_float(config["cvar_quantile"], 0.90))
        row: dict[str, float | str] = {
            "policy": action.name, "expected_score": expected, "cvar_score": tail,
            "robust_score": expected + safe_float(config["risk_aversion"], 0.55) * tail,
            "description": action.description,
        }
        for key in keys:
            values = [m[key] for m in metrics]
            row[f"mean_{key}"] = float(np.mean(values))
            row[f"p90_{key}"] = float(np.quantile(values, 0.90))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("robust_score").reset_index(drop=True)


def derive_constraint_activity(trajectory: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    limits = config["limits"]
    frame = pd.DataFrame({"day": trajectory["day"]})
    frame["raw_inventory_floor_active"] = (trajectory["raw_inventory"] <= EPS).astype(int)
    frame["production_capacity_active"] = (trajectory["production_utilization"] >= 0.995).astype(int)
    frame["supplier_capacity_active"] = (trajectory["supplier_utilization"] >= 0.995).astype(int)
    frame["order_cap_active"] = (trajectory["order"] >= safe_float(limits["max_order_ratio"]) * trajectory["demand"] * 0.995).astype(int)
    frame["service_floor_active"] = (trajectory["service"] < safe_float(limits["min_service"])).astype(int)
    frame["backlog_limit_active"] = (trajectory["backlog"] > safe_float(limits["max_backlog_days"])).astype(int)
    frame["supplier_risk_limit_active"] = (trajectory["supplier_risk"] >= safe_float(config["regime_thresholds"]["supplier_risk"])).astype(int)
    active_columns = [c for c in frame.columns if c.endswith("_active")]
    frame["active_constraint_count"] = frame[active_columns].sum(axis=1)
    return frame


def derive_adaptive_state_space(trajectory: pd.DataFrame) -> pd.DataFrame:
    mapping = {"NOMINAL": 0, "RECOVERY": 1, "MATERIAL_TENSION": 1, "CAPACITY_SATURATION": 1,
               "SUPPLIER_STRESS": 2, "OSCILLATORY": 2, "POST_CRISIS_OVERSTOCK": 2, "CRISIS": 3}
    frame = trajectory[["day", "regime", "observability", "controllability", "supplier_risk", "backlog"]].copy()
    frame["model_detail_level"] = frame["regime"].map(mapping).fillna(1).astype(int)
    frame.loc[frame["observability"] < 0.45, "model_detail_level"] += 1
    frame["model_detail_level"] = frame["model_detail_level"].clip(0, 3)
    return frame


def estimate_supplier_impedance(trajectory: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    order_signal = trajectory["order"].diff().fillna(0).to_numpy(dtype=float)
    response = trajectory["supplier_risk"].diff().fillna(0).to_numpy(dtype=float)
    n = len(order_signal)
    if n < 8:
        return pd.DataFrame(columns=["frequency_cycle_per_day", "magnitude", "phase_rad"]), {
            "peak_frequency_cycle_per_day": 0.0, "peak_period_days": float("nan"), "peak_magnitude": 0.0}
    frequency = np.fft.rfftfreq(n, d=1.0)[1:]
    input_fft = np.fft.rfft(order_signal - order_signal.mean())[1:]
    output_fft = np.fft.rfft(response - response.mean())[1:]
    transfer = output_fft / np.where(np.abs(input_fft) < 1e-8, np.nan + 0j, input_fft)
    magnitude, phase = np.abs(transfer), np.angle(transfer)
    frame = pd.DataFrame({"frequency_cycle_per_day": frequency, "magnitude": magnitude, "phase_rad": phase}).replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        return frame, {"peak_frequency_cycle_per_day": 0.0, "peak_period_days": float("nan"), "peak_magnitude": 0.0}
    peak = frame.loc[frame["magnitude"].idxmax()]
    freq = float(peak["frequency_cycle_per_day"])
    return frame, {"peak_frequency_cycle_per_day": freq, "peak_period_days": 1.0 / freq if freq > 0 else float("nan"), "peak_magnitude": float(peak["magnitude"])}
