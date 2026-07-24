from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import (
    DEFAULT_ACTIONS,
    Action,
    RunContext,
    central_scenario_from_physical,
    initial_state,
    sample_scenarios,
    slice_scenario,
)
from .model import (
    classify_regime,
    evaluate_actions,
    local_controllability_score,
    local_observability_score,
    simulate_horizon,
    simulate_step,
)


def allowed_actions_for_regime(regime: str, actions: Sequence[Action]) -> list[Action]:
    by_name = {action.name: action for action in actions}
    mapping = {
        "NOMINAL": ["mrp_reference", "balanced_robust", "supplier_relief"],
        "MATERIAL_TENSION": ["mrp_reference", "service_protection", "balanced_robust", "reactive_buffer"],
        "CAPACITY_SATURATION": ["mrp_reference", "balanced_robust", "supplier_relief", "recovery_damping"],
        "SUPPLIER_STRESS": ["mrp_reference", "supplier_relief", "balanced_robust", "service_protection"],
        "OSCILLATORY": ["mrp_reference", "supplier_relief", "balanced_robust", "recovery_damping"],
        "CRISIS": ["mrp_reference", "service_protection", "balanced_robust", "reactive_buffer", "supplier_relief"],
        "RECOVERY": ["mrp_reference", "balanced_robust", "recovery_damping", "supplier_relief"],
        "POST_CRISIS_OVERSTOCK": ["mrp_reference", "recovery_damping", "supplier_relief"],
    }
    return [by_name[name] for name in mapping.get(regime, list(by_name)) if name in by_name]


def run_adaptive_controller(
    context: RunContext,
    config: Mapping[str, Any],
    actions: Sequence[Action],
    seed: int,
    *,
    realized_scenario: Any | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = context.input_series.reset_index(drop=True)
    state = initial_state(config, float(frame["demand"].iloc[0]), float(frame["base_risk"].iloc[0]))
    current_action = next(action for action in actions if action.name == "mrp_reference")
    actual_scenario = realized_scenario or central_scenario_from_physical(
        context.physical_risk_envelope, len(frame), config
    )
    review_period = int(config["review_period_days"])
    rows: list[dict[str, float | int | str]] = []
    decision_rows: list[dict[str, float | int | str]] = []
    candidate_rows: list[dict[str, float | int | str]] = []

    for day, input_row in frame.iterrows():
        one_step = slice_scenario(actual_scenario, day, 1)
        state, metrics = simulate_step(
            state, current_action, float(input_row["demand"]),
            float(input_row["base_risk"]), one_step, 0, config
        )
        regime = classify_regime(state, metrics, config)
        observability = local_observability_score(context.observability_base, state, float(input_row["risk_uncertainty"]), metrics)
        controllability = local_controllability_score(state, metrics, config)

        if day % review_period == 0:
            horizon = min(int(config["controller_horizon_days"]), len(frame) - day)
            demand_path = frame.loc[day:day + horizon - 1, "demand"].to_numpy(dtype=float)
            risk_path = frame.loc[day:day + horizon - 1, "base_risk"].to_numpy(dtype=float)
            scenarios = sample_scenarios(
                int(config["controller_scenarios"]), horizon, config, seed + day,
                physical_risk=context.physical_risk_envelope, start_day=day,
            )
            candidates = allowed_actions_for_regime(regime, actions)
            evaluations = evaluate_actions(state, candidates, demand_path, risk_path, scenarios, config)
            for _, candidate in evaluations.iterrows():
                candidate_rows.append({"day": day, "regime": regime, **candidate.to_dict()})
            selected_name = str(evaluations.iloc[0]["policy"])
            current_action = next(action for action in actions if action.name == selected_name)
            decision_rows.append({
                "day": day,
                "regime": regime,
                "selected_policy": selected_name,
                "robust_score": float(evaluations.iloc[0]["robust_score"]),
                "observability": observability,
                "controllability": controllability,
            })

        rows.append({
            "day": int(input_row["day"]),
            "regime": regime,
            "selected_policy": current_action.name,
            "base_risk": float(input_row["base_risk"]),
            "risk_uncertainty": float(input_row["risk_uncertainty"]),
            "observability": observability,
            "controllability": controllability,
            **metrics,
        })

    return pd.DataFrame(rows), pd.DataFrame(decision_rows), pd.DataFrame(candidate_rows)


def simulate_fixed_policy_scenarios(context: RunContext, config: Mapping[str, Any], actions: Sequence[Action], seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = context.input_series.reset_index(drop=True)
    demand_path = frame["demand"].to_numpy(dtype=float)
    risk_path = frame["base_risk"].to_numpy(dtype=float)
    scenarios = sample_scenarios(
        int(config["policy_comparison_scenarios"]), len(frame), config, seed + 9000,
        physical_risk=context.physical_risk_envelope, start_day=0,
    )
    initial = initial_state(config, demand_path[0], risk_path[0])
    comparison = evaluate_actions(initial, actions, demand_path, risk_path, scenarios, config)
    sample_scenarios_subset = scenarios[: min(12, len(scenarios))]
    rows: list[pd.DataFrame] = []
    for action in actions:
        for scenario_id, scenario in enumerate(sample_scenarios_subset):
            trajectory, _ = simulate_horizon(initial, action, demand_path, risk_path, scenario, config)
            trajectory["scenario_id"] = scenario_id
            rows.append(trajectory)
    return comparison, pd.concat(rows, ignore_index=True)


def adaptive_summary(trajectory: pd.DataFrame) -> dict[str, float]:
    return {
        "mean_service": float(trajectory["service"].mean()),
        "min_service": float(trajectory["service"].min()),
        "backlog_area": float(trajectory["backlog"].sum()),
        "max_backlog": float(trajectory["backlog"].max()),
        "mean_inventory": float(trajectory["inventory_total"].mean()),
        "nervousness_area": float(trajectory["nervousness"].sum()),
        "mean_supplier_risk": float(trajectory["supplier_risk"].mean()),
        "max_supplier_risk": float(trajectory["supplier_risk"].max()),
        "mean_risk_creation_vs_forecast": float((trajectory["supplier_risk"] - trajectory.get("forecast_risk", trajectory["base_risk"])).clip(lower=0).mean()),
        "quality_loss_area": float(trajectory.get("quality_loss", pd.Series(0.0, index=trajectory.index)).sum()),
        "mean_observability": float(trajectory["observability"].mean()),
        "mean_controllability": float(trajectory["controllability"].mean()),
    }


def regime_transition_matrix(trajectory: pd.DataFrame) -> pd.DataFrame:
    regimes = list(dict.fromkeys(list(trajectory["regime"].astype(str))))
    matrix = pd.DataFrame(0, index=regimes, columns=regimes, dtype=int)
    values = trajectory["regime"].astype(str).tolist()
    for previous, current in zip(values[:-1], values[1:]):
        matrix.loc[previous, current] += 1
    return matrix
