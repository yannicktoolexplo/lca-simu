from __future__ import annotations

"""Paired-policy and forecast-error experiments for the SCAN end-2026 PoC."""

from dataclasses import replace
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import Action, RunContext, initial_state, sample_scenarios
from .decision import adaptive_summary, run_adaptive_controller
from .model import policy_objective, simulate_horizon
from .risk_mapping import map_prediction_interval_to_physical


def paired_policy_experiment(
    context: RunContext,
    config: Mapping[str, Any],
    actions: Sequence[Action],
    seeds: Sequence[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare policies with common random numbers and report paired deltas."""

    frame = context.input_series.reset_index(drop=True)
    demand_path = frame["demand"].to_numpy(dtype=float)
    risk_path = frame["base_risk"].to_numpy(dtype=float)
    reference_action = next(action for action in actions if action.name == "mrp_reference")
    initial = initial_state(config, float(demand_path[0]), float(risk_path[0]))
    run_rows: list[dict[str, Any]] = []
    for seed in seeds:
        scenario = sample_scenarios(
            1,
            len(frame),
            config,
            int(seed),
            physical_risk=context.physical_risk_envelope,
        )[0]
        reference, _ = simulate_horizon(initial, reference_action, demand_path, risk_path, scenario, config)
        for action in actions:
            trajectory, _ = simulate_horizon(initial, action, demand_path, risk_path, scenario, config)
            metrics = policy_objective(trajectory, reference, config)
            run_rows.append({
                "seed": int(seed),
                "policy": action.name,
                "scenario_seed": scenario.scenario_seed,
                **metrics,
                "mean_service": float(trajectory["service"].mean()),
                "mean_inventory": float(trajectory["inventory_total"].mean()),
                "mean_supplier_risk": float(trajectory["supplier_risk"].mean()),
            })
    runs = pd.DataFrame(run_rows)
    reference = runs.loc[runs["policy"] == "mrp_reference"].set_index("seed")
    delta_rows: list[dict[str, Any]] = []
    metric_names = [
        "score",
        "service_loss",
        "backlog_area",
        "nervousness",
        "risk_creation",
        "quality_loss",
        "mean_service",
        "mean_inventory",
        "mean_supplier_risk",
    ]
    for policy, group in runs.groupby("policy", sort=False):
        aligned = group.set_index("seed").join(reference[metric_names], rsuffix="_reference")
        row: dict[str, Any] = {"policy": policy, "paired_seed_count": int(len(aligned))}
        for metric in metric_names:
            delta = aligned[metric] - aligned[f"{metric}_reference"]
            mean = float(delta.mean())
            std = float(delta.std(ddof=1)) if len(delta) > 1 else 0.0
            half_width = 1.96 * std / max(np.sqrt(len(delta)), 1.0)
            row[f"mean_delta_{metric}"] = mean
            row[f"ci95_low_delta_{metric}"] = mean - half_width
            row[f"ci95_high_delta_{metric}"] = mean + half_width
            row[f"p90_delta_{metric}"] = float(delta.quantile(0.90))
        row["score_win_rate_vs_mrp"] = float((aligned["score"] < aligned["score_reference"]).mean())
        row["service_win_rate_vs_mrp"] = float((aligned["mean_service"] > aligned["mean_service_reference"]).mean())
        row["risk_creation_nonpositive_rate"] = float((aligned["risk_creation"] <= 0).mean())
        delta_rows.append(row)
    summary = pd.DataFrame(delta_rows).sort_values("mean_delta_score").reset_index(drop=True)
    return runs, summary


def _event_probability_series(days: int, start: int, duration: int, low: float, high: float, event: bool) -> np.ndarray:
    series = np.full(days, low, dtype=float)
    if event:
        stop = min(days, start + duration)
        series[max(0, start):stop] = high
    return series


def build_confusion_context(
    context: RunContext,
    *,
    predicted_event: bool,
    start_day: int,
    duration_days: int,
    low_probability: float,
    high_probability: float,
    mapping_config: Mapping[str, Any],
) -> RunContext:
    days = len(context.input_series)
    prediction = _event_probability_series(
        days, start_day, duration_days, low_probability, high_probability, predicted_event
    )
    width = np.where(prediction > low_probability + 1e-9, 0.12, 0.05)
    envelope = pd.DataFrame({
        "day": np.arange(days, dtype=int),
        "risk_lower": np.clip(prediction - width, 0, 1),
        "risk_center": prediction,
        "risk_upper": np.clip(prediction + width, 0, 1),
        "conditional_backlog_if_incident": np.where(prediction > 0.5, 24.0, 2.0),
        "conditional_fill_loss_if_incident": np.where(prediction > 0.5, 0.025, 0.002),
        "lead_mean_days": np.full(days, 8.0),
        "priority_score": prediction,
        "source_pairs": np.ones(days, dtype=int),
    })
    physical = map_prediction_interval_to_physical(envelope, mapping_config)
    input_series = context.input_series.copy()
    input_series["base_risk"] = prediction
    input_series["risk_uncertainty"] = width
    return replace(
        context,
        input_series=input_series,
        prediction_interval=envelope,
        physical_risk_envelope=physical,
        prediction_interval_metadata={
            "interval_method": "forecast_confusion_experiment",
            "predicted_event": bool(predicted_event),
        },
    )


def build_truth_physical_envelope(
    days: int,
    *,
    truth_event: bool,
    start_day: int,
    duration_days: int,
    low_probability: float,
    high_probability: float,
    mapping_config: Mapping[str, Any],
) -> pd.DataFrame:
    truth = _event_probability_series(days, start_day, duration_days, low_probability, high_probability, truth_event)
    envelope = pd.DataFrame({
        "day": np.arange(days, dtype=int),
        "risk_lower": truth,
        "risk_center": truth,
        "risk_upper": truth,
        "conditional_backlog_if_incident": np.where(truth > 0.5, 28.0, 1.0),
        "conditional_fill_loss_if_incident": np.where(truth > 0.5, 0.030, 0.001),
        "lead_mean_days": np.full(days, 8.0),
        "priority_score": truth,
        "source_pairs": np.ones(days, dtype=int),
    })
    return map_prediction_interval_to_physical(envelope, mapping_config)


def forecast_confusion_experiment(
    context: RunContext,
    config: Mapping[str, Any],
    actions: Sequence[Action],
    seeds: Sequence[int],
    *,
    start_day: int | None = None,
    duration_days: int = 42,
    low_probability: float = 0.08,
    high_probability: float = 0.82,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run TP/FP/FN/TN experiments with forecast and physical truth separated."""

    days = len(context.input_series)
    start = int(days * 0.35) if start_day is None else int(start_day)
    mapping = config.get("physical_risk_mapping", {})
    cases = {
        "TP": (True, True),
        "FP": (True, False),
        "FN": (False, True),
        "TN": (False, False),
    }
    rows: list[dict[str, Any]] = []
    for case, (predicted_event, truth_event) in cases.items():
        forecast_context = build_confusion_context(
            context,
            predicted_event=predicted_event,
            start_day=start,
            duration_days=duration_days,
            low_probability=low_probability,
            high_probability=high_probability,
            mapping_config=mapping,
        )
        truth_envelope = build_truth_physical_envelope(
            days,
            truth_event=truth_event,
            start_day=start,
            duration_days=duration_days,
            low_probability=low_probability,
            high_probability=high_probability,
            mapping_config=mapping,
        )
        for seed in seeds:
            realized = sample_scenarios(
                1, days, config, int(seed), physical_risk=truth_envelope
            )[0]
            trajectory, decisions, _ = run_adaptive_controller(
                forecast_context,
                config,
                actions,
                int(seed) + 100_000,
                realized_scenario=realized,
            )
            summary = adaptive_summary(trajectory)
            rows.append({
                "case": case,
                "predicted_event": int(predicted_event),
                "truth_event": int(truth_event),
                "seed": int(seed),
                "selected_policy_changes": int(max(0, decisions["selected_policy"].nunique() - 1)) if not decisions.empty else 0,
                "dominant_policy": str(decisions["selected_policy"].mode().iloc[0]) if not decisions.empty else "",
                "service_loss": float((1.0 - trajectory["service"]).clip(lower=0).sum()),
                "backlog_area": float(trajectory["backlog"].sum()),
                "nervousness_area": float(trajectory["nervousness"].sum()),
                "supplier_risk_area": float(trajectory["supplier_risk"].sum()),
                "risk_creation_area": float((trajectory["supplier_risk"] - trajectory["realized_base_risk"]).clip(lower=0).sum()),
                "expedite_area": float(trajectory["expedite"].sum()),
                **summary,
            })
    runs = pd.DataFrame(rows)
    aggregate_columns = [
        "service_loss", "backlog_area", "nervousness_area", "supplier_risk_area",
        "risk_creation_area", "expedite_area", "mean_service", "max_backlog",
        "mean_supplier_risk", "mean_observability", "mean_controllability",
    ]
    summary_rows: list[dict[str, Any]] = []
    for case, group in runs.groupby("case"):
        row: dict[str, Any] = {
            "case": case,
            "predicted_event": int(group["predicted_event"].iloc[0]),
            "truth_event": int(group["truth_event"].iloc[0]),
            "runs": int(len(group)),
            "dominant_policy": str(group["dominant_policy"].mode().iloc[0]),
        }
        for column in aggregate_columns:
            row[f"mean_{column}"] = float(group[column].mean())
            row[f"p90_{column}"] = float(group[column].quantile(0.90))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("case").reset_index(drop=True)

    oracle_for = {"TP": "TP", "FN": "TP", "TN": "TN", "FP": "TN"}
    by_case_seed = runs.set_index(["case", "seed"])
    regret_rows: list[dict[str, Any]] = []
    for _, row in runs.iterrows():
        oracle_case = oracle_for[str(row["case"])]
        oracle = by_case_seed.loc[(oracle_case, int(row["seed"]))]
        regret_rows.append({
            "case": row["case"],
            "oracle_case": oracle_case,
            "seed": int(row["seed"]),
            "service_loss_regret": float(row["service_loss"] - oracle["service_loss"]),
            "backlog_regret": float(row["backlog_area"] - oracle["backlog_area"]),
            "nervousness_regret": float(row["nervousness_area"] - oracle["nervousness_area"]),
            "risk_creation_regret": float(row["risk_creation_area"] - oracle["risk_creation_area"]),
            "expedite_regret": float(row["expedite_area"] - oracle["expedite_area"]),
        })
    regret = pd.DataFrame(regret_rows)
    return runs, summary, regret
