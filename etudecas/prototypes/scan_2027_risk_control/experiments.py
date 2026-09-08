from __future__ import annotations

"""Paired-policy and forecast-error experiments for the SCAN end-2026 PoC."""

import hashlib
from dataclasses import replace
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import (
    Action,
    RunContext,
    initial_state,
    sample_scenarios,
    slice_scenario,
)
from .decision import adaptive_summary, run_adaptive_controller
from .model import (
    classify_regime,
    local_controllability_score,
    local_observability_score,
    policy_objective,
    simulate_horizon,
    simulate_step,
)
from .risk_mapping import map_prediction_interval_to_physical


REDUCED_RECOVERY_STABLE_DAYS = 7
REDUCED_PAIRED_METRIC_NAMES = (
    "score",
    "service_loss",
    "min_service",
    "backlog_area",
    "max_backlog",
    "inventory_area",
    "nervousness",
    "risk_area",
    "risk_creation",
    "expedite",
    "quality_loss",
    "purchase_cost_proxy",
    "transport_cost_proxy",
    "constraint_violation",
    "constraint_violation_count",
    "constraint_violation_days",
    "mean_service",
    "mean_inventory",
    "mean_supplier_risk",
    "recovery_time_days",
    "recovery_time_lower_bound_days",
    "recovery_followup_days",
    "recovery_observed",
)


def _validated_unique_seeds(seeds: Sequence[int]) -> list[int]:
    values = [int(seed) for seed in seeds]
    if not values:
        raise ValueError("At least one paired seed is required.")
    if len(values) != len(set(values)):
        raise ValueError("Paired experiment seeds must be unique.")
    return values


def _constraint_violation_counts(
    trajectory: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[int, int]:
    limits = config["limits"]
    service = trajectory["service"] < float(limits["min_service"])
    backlog = trajectory["backlog"] > float(limits["max_backlog_days"])
    return int(service.sum() + backlog.sum()), int((service | backlog).sum())


def _reduced_recovery_contract(
    trajectory: pd.DataFrame,
    *,
    stable_days: int = REDUCED_RECOVERY_STABLE_DAYS,
) -> dict[str, Any]:
    """Return an auditable, censoring-aware recovery outcome.

    Recovery is applicable only after an observed disruption (positive backlog
    or service below 99%).  Its origin is the maximum-backlog day, or the
    minimum-service day for a service-only incident.  Recovery is observed only
    when backlog then remains zero and daily service remains at least 99% for a
    complete seven-day window.  A trajectory that ends first is right-censored:
    its duration is unknown, while follow-up is retained as a lower bound.
    """

    if stable_days < 1:
        raise ValueError("stable_days must be at least one")
    required = {"backlog", "service"}
    missing = sorted(required.difference(trajectory.columns))
    if missing:
        raise ValueError(
            "Reduced recovery requires trajectory columns: "
            + ", ".join(missing)
        )
    if trajectory.empty:
        return {
            "recovery_time_days": float("nan"),
            "recovery_time_lower_bound_days": float("nan"),
            "recovery_followup_days": float("nan"),
            "recovery_observed": float("nan"),
            "recovery_status": "not_estimable_empty_trajectory",
            "recovery_episode_detected": float("nan"),
            "recovery_episode_basis": "unavailable",
        }

    backlog = pd.to_numeric(trajectory["backlog"], errors="coerce")
    service = pd.to_numeric(trajectory["service"], errors="coerce")
    if not (
        np.isfinite(backlog.to_numpy(dtype=float)).all()
        and np.isfinite(service.to_numpy(dtype=float)).all()
    ):
        raise ValueError("Reduced recovery requires finite backlog and service values")

    backlog_disruption = backlog > 1e-9
    service_disruption = service < 0.99
    if not bool((backlog_disruption | service_disruption).any()):
        return {
            "recovery_time_days": float("nan"),
            "recovery_time_lower_bound_days": float("nan"),
            "recovery_followup_days": float("nan"),
            "recovery_observed": float("nan"),
            "recovery_status": "not_applicable_no_disruption",
            "recovery_episode_detected": 0.0,
            "recovery_episode_basis": "no_backlog_or_service_disruption",
        }

    if bool(backlog_disruption.any()):
        peak_index = int(backlog.to_numpy(dtype=float).argmax())
        episode_basis = "backlog_peak"
    else:
        # Service-only incidents have no meaningful backlog peak.  Anchor the
        # follow-up on the worst observed service day instead of day zero.
        peak_index = int(service.to_numpy(dtype=float).argmin())
        episode_basis = "service_minimum"
    followup_days = float(max(0, len(trajectory) - peak_index - 1))
    recovery_time = float("nan")
    lower_bound = followup_days
    observed = 0.0
    status = "right_censored"
    final_window_start = len(trajectory) - stable_days
    for index in range(peak_index, final_window_start + 1):
        stop = index + stable_days
        if (
            (backlog.iloc[index:stop] <= 1e-9).all()
            and (service.iloc[index:stop] >= 0.99).all()
        ):
            recovery_time = float(index - peak_index)
            lower_bound = recovery_time
            observed = 1.0
            status = "observed"
            break
    return {
        "recovery_time_days": recovery_time,
        "recovery_time_lower_bound_days": lower_bound,
        "recovery_followup_days": followup_days,
        "recovery_observed": observed,
        "recovery_status": status,
        "recovery_episode_detected": 1.0,
        "recovery_episode_basis": episode_basis,
    }


def _policy_run_record(
    *,
    seed: int,
    scenario_seed: int | None,
    policy: str,
    run_type: str,
    trajectory: pd.DataFrame,
    reference: pd.DataFrame,
    config: Mapping[str, Any],
    oracle_fixed_policy: str = "",
    controller_seed: int | None = None,
) -> dict[str, Any]:
    metrics = policy_objective(trajectory, reference, config)
    violation_count, violation_days = _constraint_violation_counts(trajectory, config)
    recovery = _reduced_recovery_contract(trajectory)
    return {
        "seed": int(seed),
        "policy": policy,
        "run_type": run_type,
        "scenario_seed": scenario_seed,
        "controller_seed": controller_seed,
        "oracle_fixed_policy": oracle_fixed_policy,
        **metrics,
        "constraint_violation_count": violation_count,
        "constraint_violation_days": violation_days,
        "mean_service": float(trajectory["service"].mean()),
        "mean_inventory": float(trajectory["inventory_total"].mean()),
        "mean_supplier_risk": float(trajectory["supplier_risk"].mean()),
        **recovery,
    }


def _paired_cohens_dz(
    delta: pd.Series,
    *,
    exact_reference: bool = False,
) -> tuple[float, str]:
    """Return conventional Cohen's dz for paired observations.

    Cohen's dz is the mean paired difference divided by the sample standard
    deviation of those differences.  A constant non-zero difference therefore
    has no finite, estimable dz; returning ``NaN`` with a machine-readable status
    is more defensible than silently substituting a different effect definition.
    The MRP self-comparison is an identity by construction and remains exactly
    zero to preserve the reference invariant.
    """

    values = pd.to_numeric(delta, errors="coerce").dropna().to_numpy(dtype=float)
    if exact_reference:
        return 0.0, "exact_reference_zero"
    if len(values) == 0:
        return float("nan"), "not_estimable_no_pairs"
    if len(values) < 2:
        return float("nan"), "not_estimable_single_pair"
    mean = float(np.mean(values))
    if abs(mean) <= 1e-12:
        return 0.0, "exact_zero_mean"
    paired_std = float(np.std(values, ddof=1))
    if not np.isfinite(paired_std) or paired_std <= 1e-12:
        return float("nan"), "not_estimable_zero_paired_variance"
    return mean / paired_std, "paired_cohens_dz"


def _attach_reduced_mrp_reference_deltas(runs: pd.DataFrame) -> pd.DataFrame:
    """Attach per-seed reduced-model MRP values and auditable differences."""

    result = runs.copy()
    if result.empty:
        return result
    reference = (
        result.loc[result["policy"].eq("mrp_reference")]
        .drop_duplicates("seed", keep="last")
        .set_index("seed")
    )
    metric_names = [
        metric for metric in REDUCED_PAIRED_METRIC_NAMES
        if metric in result.columns
    ]
    for metric in metric_names:
        reference_column = f"mrp_reference_{metric}"
        delta_column = f"delta_vs_mrp_{metric}"
        reference_values = pd.to_numeric(
            reference.get(metric, pd.Series(dtype=float)),
            errors="coerce",
        )
        result[reference_column] = result["seed"].map(reference_values)
        result[delta_column] = (
            pd.to_numeric(result[metric], errors="coerce")
            - pd.to_numeric(result[reference_column], errors="coerce")
        )
        # The reference identity is exact by construction, including when a
        # duration is censored or non-applicable and has no point estimate.
        result.loc[
            result["policy"].eq("mrp_reference"),
            delta_column,
        ] = 0.0

    if "recovery_status" not in result:
        return result
    result["mrp_reference_recovery_status"] = result["seed"].map(
        reference.get("recovery_status", pd.Series(dtype=str))
    )
    reference_self = result["policy"].eq("mrp_reference")
    observed_pair = (
        result["recovery_status"].astype(str).eq("observed")
        & result["mrp_reference_recovery_status"].astype(str).eq("observed")
    )
    policy_not_applicable = result["recovery_status"].astype(str).eq(
        "not_applicable_no_disruption"
    )
    reference_not_applicable = (
        result["mrp_reference_recovery_status"]
        .astype(str)
        .eq("not_applicable_no_disruption")
    )
    for metric in (
        "recovery_time_days",
        "recovery_time_lower_bound_days",
        "recovery_followup_days",
        "recovery_observed",
    ):
        delta_column = f"delta_vs_mrp_{metric}"
        if delta_column in result:
            result.loc[~(reference_self | observed_pair), delta_column] = float("nan")
    result["delta_vs_mrp_recovery_time_status"] = np.select(
        [
            reference_self,
            observed_pair,
            result["mrp_reference_recovery_status"].isna(),
            policy_not_applicable & reference_not_applicable,
            policy_not_applicable | reference_not_applicable,
        ],
        [
            "reference_self_exact_zero",
            "observed_pair",
            "missing_mrp_reference",
            "not_comparable_no_disruption",
            "not_comparable_non_applicable",
        ],
        default="not_comparable_censored",
    )
    return result


def _paired_reduced_summary(runs: pd.DataFrame) -> pd.DataFrame:
    """Summarize reduced-model paired effects without fabricating uncertainty."""

    if runs.empty or "mrp_reference" not in set(runs["policy"]):
        return pd.DataFrame()
    metric_names = [
        metric for metric in REDUCED_PAIRED_METRIC_NAMES
        if metric in runs.columns
    ]
    reference_columns = list(metric_names)
    if "recovery_status" in runs:
        reference_columns.append("recovery_status")
    reference = (
        runs.loc[runs["policy"].eq("mrp_reference")]
        .drop_duplicates("seed", keep="last")
        .set_index("seed")
    )
    rows: list[dict[str, Any]] = []
    higher_is_better = {"min_service", "mean_service"}
    for policy, group in runs.groupby("policy", sort=False):
        aligned = group.set_index("seed").join(
            reference[reference_columns],
            rsuffix="_reference",
            how="inner",
        )
        if aligned.empty:
            continue
        row: dict[str, Any] = {
            "policy": policy,
            "paired_seed_count": int(len(aligned)),
        }
        for metric in metric_names:
            current = pd.to_numeric(aligned[metric], errors="coerce")
            baseline = pd.to_numeric(
                aligned[f"{metric}_reference"],
                errors="coerce",
            )
            valid_pair = (
                current.notna()
                & baseline.notna()
                & np.isfinite(current)
                & np.isfinite(baseline)
            )
            if metric in {
                "recovery_time_days",
                "recovery_time_lower_bound_days",
                "recovery_followup_days",
                "recovery_observed",
            }:
                valid_pair &= (
                    aligned.get(
                        "recovery_status",
                        pd.Series("", index=aligned.index),
                    ).astype(str).eq("observed")
                    & aligned.get(
                        "recovery_status_reference",
                        pd.Series("", index=aligned.index),
                    ).astype(str).eq("observed")
                )
            delta = (current - baseline).loc[valid_pair]
            observed_count = int(len(delta))
            exact_reference = policy == "mrp_reference"
            if exact_reference:
                delta = pd.Series(0.0, index=delta.index, dtype=float)

            mean = (
                0.0
                if exact_reference
                else float(delta.mean()) if observed_count else float("nan")
            )
            row[f"mean_delta_{metric}"] = mean
            row[f"paired_observed_count_{metric}"] = observed_count
            row[f"median_delta_{metric}"] = (
                0.0
                if exact_reference
                else float(delta.median()) if observed_count else float("nan")
            )
            row[f"p90_delta_{metric}"] = (
                0.0
                if exact_reference
                else float(delta.quantile(0.90)) if observed_count else float("nan")
            )
            if exact_reference:
                ci95_low = 0.0
                ci95_high = 0.0
                ci95_status = "exact_reference_zero"
            elif observed_count == 0:
                ci95_low = float("nan")
                ci95_high = float("nan")
                ci95_status = "not_estimable_no_observed_pairs"
            elif observed_count == 1:
                ci95_low = float("nan")
                ci95_high = float("nan")
                ci95_status = "not_estimable_single_pair"
            else:
                std = float(delta.std(ddof=1))
                half_width = 1.96 * std / np.sqrt(observed_count)
                ci95_low = mean - half_width
                ci95_high = mean + half_width
                ci95_status = "normal_approximation_95"
            row[f"ci95_low_delta_{metric}"] = ci95_low
            row[f"ci95_high_delta_{metric}"] = ci95_high
            row[f"ci95_status_delta_{metric}"] = ci95_status

            effect, effect_status = _paired_cohens_dz(
                delta,
                exact_reference=exact_reference,
            )
            # Keep historical names while exposing the precise method/status.
            row[f"standardized_effect_delta_{metric}"] = effect
            row[f"standardized_effect_status_delta_{metric}"] = effect_status
            row[f"cohen_dz_delta_{metric}"] = effect
            row[f"cohen_dz_status_delta_{metric}"] = effect_status
            row[f"win_rate_vs_mrp_{metric}"] = (
                float(
                    (delta > 0).mean()
                    if metric in higher_is_better
                    else (delta < 0).mean()
                )
                if observed_count else float("nan")
            )
            if metric == "recovery_time_days":
                if exact_reference:
                    pairing_status = "reference_self_identity"
                elif observed_count == 0:
                    current_status = aligned.get(
                        "recovery_status",
                        pd.Series("", index=aligned.index),
                    ).astype(str)
                    reference_status = aligned.get(
                        "recovery_status_reference",
                        pd.Series("", index=aligned.index),
                    ).astype(str)
                    if bool(
                        (
                            current_status.eq("not_applicable_no_disruption")
                            & reference_status.eq(
                                "not_applicable_no_disruption"
                            )
                        ).all()
                    ):
                        pairing_status = "not_applicable_no_disruption_pairs"
                    else:
                        pairing_status = "not_comparable_no_observed_pairs"
                elif observed_count < len(aligned):
                    pairing_status = "partial_observed_pairs_excludes_censored"
                else:
                    pairing_status = "all_pairs_observed"
                row["pairing_status_delta_recovery_time_days"] = pairing_status

        row["score_win_rate_vs_mrp"] = row.get(
            "win_rate_vs_mrp_score",
            float("nan"),
        )
        row["service_win_rate_vs_mrp"] = row.get(
            "win_rate_vs_mrp_mean_service",
            float("nan"),
        )
        if "risk_creation" in aligned:
            row["risk_creation_nonpositive_rate"] = float(
                (pd.to_numeric(aligned["risk_creation"], errors="coerce") <= 0).mean()
            )
        rows.append(row)
    summary = pd.DataFrame(rows)
    if "mean_delta_score" in summary:
        summary = summary.sort_values("mean_delta_score")
    return summary.reset_index(drop=True)


def paired_policy_experiment(
    context: RunContext,
    config: Mapping[str, Any],
    actions: Sequence[Action],
    seeds: Sequence[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare policies with common random numbers and report paired deltas."""

    paired_seeds = _validated_unique_seeds(seeds)
    frame = context.input_series.reset_index(drop=True)
    demand_path = frame["demand"].to_numpy(dtype=float)
    risk_path = frame["base_risk"].to_numpy(dtype=float)
    reference_action = next(action for action in actions if action.name == "mrp_reference")
    initial = initial_state(config, float(demand_path[0]), float(risk_path[0]))
    run_rows: list[dict[str, Any]] = []
    for seed in paired_seeds:
        scenario = sample_scenarios(
            1,
            len(frame),
            config,
            int(seed),
            physical_risk=context.physical_risk_envelope,
        )[0]
        reference, _ = simulate_horizon(initial, reference_action, demand_path, risk_path, scenario, config)
        fixed_records: list[dict[str, Any]] = []
        for action in actions:
            trajectory, _ = simulate_horizon(initial, action, demand_path, risk_path, scenario, config)
            record = _policy_run_record(
                seed=int(seed),
                scenario_seed=scenario.scenario_seed,
                policy=action.name,
                run_type="fixed",
                trajectory=trajectory,
                reference=reference,
                config=config,
            )
            fixed_records.append(record)
            run_rows.append(record)

        controller_seed = int(seed) + 1_000_000
        adaptive, decisions, _ = run_adaptive_controller(
            context,
            config,
            actions,
            controller_seed,
            realized_scenario=scenario,
        )
        adaptive_record = _policy_run_record(
            seed=int(seed),
            scenario_seed=scenario.scenario_seed,
            policy="adaptive",
            run_type="adaptive",
            trajectory=adaptive,
            reference=reference,
            config=config,
            controller_seed=controller_seed,
        )
        adaptive_record["selected_policy_changes"] = (
            int(max(0, decisions["selected_policy"].nunique() - 1))
            if not decisions.empty else 0
        )
        adaptive_record["dominant_policy"] = (
            str(decisions["selected_policy"].mode().iloc[0])
            if not decisions.empty else reference_action.name
        )
        run_rows.append(adaptive_record)

        # The oracle is deliberately realizable and auditable: it is the fixed
        # playbook with the lowest ex-post score on this exact physical path.
        best_fixed = min(fixed_records, key=lambda record: float(record["score"]))
        oracle_record = dict(best_fixed)
        oracle_record.update({
            "policy": "oracle",
            "run_type": "oracle_best_fixed_ex_post",
            "oracle_fixed_policy": str(best_fixed["policy"]),
        })
        run_rows.append(oracle_record)

    runs = _attach_reduced_mrp_reference_deltas(pd.DataFrame(run_rows))
    summary = _paired_reduced_summary(runs)
    return runs, summary


def _event_probability_series(days: int, start: int, duration: int, low: float, high: float, event: bool) -> np.ndarray:
    series = np.full(days, low, dtype=float)
    if event:
        stop = min(days, start + duration)
        series[max(0, start):stop] = high
    return series


def _scenario_fingerprint(scenario: Any) -> str:
    """Hash the complete realized physical path for pairing audits."""

    digest = hashlib.sha256()
    for field in (
        "demand_multiplier",
        "supply_shock",
        "capacity_shock",
        "lead_time_shock",
        "risk_noise",
        "realized_risk_probability",
        "quality_yield_multiplier",
        "purchase_cost_multiplier",
        "transport_cost_multiplier",
    ):
        value = getattr(scenario, field, None)
        digest.update(field.encode("utf-8"))
        if value is None:
            digest.update(b"<none>")
            continue
        array = np.ascontiguousarray(np.asarray(value, dtype=np.float64))
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes())
    digest.update(str(getattr(scenario, "scenario_seed", None)).encode("ascii"))
    return digest.hexdigest()


def build_confusion_context(
    context: RunContext,
    *,
    predicted_event: bool,
    start_day: int,
    duration_days: int,
    low_probability: float,
    high_probability: float,
    interval_half_width: float | None = None,
    mapping_config: Mapping[str, Any],
) -> RunContext:
    days = len(context.input_series)
    prediction = _event_probability_series(
        days, start_day, duration_days, low_probability, high_probability, predicted_event
    )
    width = (
        np.full(days, float(interval_half_width), dtype=float)
        if interval_half_width is not None
        else np.where(prediction > low_probability + 1e-9, 0.12, 0.05)
    )
    width = np.clip(width, 0.0, 0.49)
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


def _confusion_trajectory_metrics(
    trajectory: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    event_start_day: int,
    event_duration_days: int,
) -> dict[str, float]:
    """Return operational metrics used by both adaptive and MRP confusion runs."""

    nominal = config["nominal"]
    target_inventory = (
        float(nominal["raw_inventory_days"])
        + float(nominal["finished_inventory_days"])
    )
    demand = pd.to_numeric(trajectory["demand"], errors="coerce").fillna(0.0)
    order = pd.to_numeric(trajectory["order"], errors="coerce").fillna(0.0)
    production = pd.to_numeric(
        trajectory.get("production", pd.Series(0.0, index=trajectory.index)),
        errors="coerce",
    ).fillna(0.0)
    inventory = pd.to_numeric(
        trajectory["inventory_total"], errors="coerce"
    ).fillna(0.0)
    supplier_risk = pd.to_numeric(
        trajectory["supplier_risk"], errors="coerce"
    ).fillna(0.0)
    realized_risk = pd.to_numeric(
        trajectory.get(
            "realized_base_risk",
            trajectory.get("base_risk", pd.Series(0.0, index=trajectory.index)),
        ),
        errors="coerce",
    ).fillna(0.0)
    purchase_cost = pd.to_numeric(
        trajectory.get(
            "purchase_cost_proxy", pd.Series(0.0, index=trajectory.index)
        ),
        errors="coerce",
    ).fillna(0.0)
    transport_cost = pd.to_numeric(
        trajectory.get(
            "transport_cost_proxy", pd.Series(0.0, index=trajectory.index)
        ),
        errors="coerce",
    ).fillna(0.0)
    demand_scale = max(float(demand.replace(0.0, np.nan).median()), 1e-9)
    event_stop = min(
        len(trajectory),
        max(0, int(event_start_day)) + max(1, int(event_duration_days)),
    )
    post_event_inventory = inventory.iloc[event_stop:]
    return {
        "service_loss": float(
            (1.0 - trajectory["service"]).clip(lower=0.0).sum()
        ),
        "backlog_area": float(trajectory["backlog"].sum()),
        "max_backlog": float(trajectory["backlog"].max()),
        "mean_service": float(trajectory["service"].mean()),
        "mean_inventory": float(inventory.mean()),
        "unused_stock_area": float(
            (inventory - target_inventory).clip(lower=0.0).sum()
        ),
        "post_event_overstock_area": float(
            (post_event_inventory - target_inventory).clip(lower=0.0).sum()
        ),
        "order_area": float(order.sum()),
        "over_ordering_area": float((order - demand).clip(lower=0.0).sum()),
        "nervousness_area": float(trajectory["nervousness"].sum()),
        "production_nervousness_area": float(
            production.diff().abs().fillna(0.0).sum() / demand_scale
        ),
        "expedite_area": float(trajectory["expedite"].sum()),
        "purchase_cost_proxy": float(purchase_cost.sum()),
        "transport_cost_proxy": float(transport_cost.sum()),
        "total_cost_proxy": float((purchase_cost + transport_cost).sum()),
        "supplier_stress_area": float(trajectory["supplier_stress"].sum()),
        "supplier_risk_area": float(supplier_risk.sum()),
        "risk_creation_area": float(
            (supplier_risk - realized_risk).clip(lower=0.0).sum()
        ),
        "quality_loss_area": float(
            trajectory.get(
                "quality_loss", pd.Series(0.0, index=trajectory.index)
            ).sum()
        ),
    }


def _simulate_forecast_gated_response(
    context: RunContext,
    config: Mapping[str, Any],
    *,
    reference_action: Action,
    response_action: Action,
    response_intensity: float,
    predicted_event: bool,
    start_day: int,
    duration_days: int,
    realized_scenario: Any,
) -> pd.DataFrame:
    """Apply a declared bounded response only inside the forecast alert window.

    This protocol makes the action channel explicit in TP/FP/FN/TN analysis.
    The physical realization remains the same for cases sharing the same truth
    and seed; only the forecast-gated response changes.
    """

    frame = context.input_series.reset_index(drop=True)
    bounded_intensity = float(np.clip(response_intensity, 0.0, 1.0))
    graded_response = Action(
        name=response_action.name,
        order_gain=(
            reference_action.order_gain
            + bounded_intensity
            * (response_action.order_gain - reference_action.order_gain)
        ),
        production_gain=(
            reference_action.production_gain
            + bounded_intensity
            * (
                response_action.production_gain
                - reference_action.production_gain
            )
        ),
        expedite=(
            reference_action.expedite
            + bounded_intensity
            * (response_action.expedite - reference_action.expedite)
        ),
        smoothing=(
            reference_action.smoothing
            + bounded_intensity
            * (response_action.smoothing - reference_action.smoothing)
        ),
        safety_stock_gain=(
            reference_action.safety_stock_gain
            + bounded_intensity
            * (
                response_action.safety_stock_gain
                - reference_action.safety_stock_gain
            )
        ),
        supplier_relief=(
            reference_action.supplier_relief
            + bounded_intensity
            * (
                response_action.supplier_relief
                - reference_action.supplier_relief
            )
        ),
        description=(
            "Graded forecast-gated interpolation between the MRP reference "
            f"and {response_action.name}."
        ),
    )
    state = initial_state(
        config,
        float(frame["demand"].iloc[0]),
        float(frame["base_risk"].iloc[0]),
    )
    stop_day = min(len(frame), int(start_day) + int(duration_days))
    rows: list[dict[str, Any]] = []
    for day, input_row in frame.iterrows():
        response_active = bool(
            predicted_event and int(start_day) <= day < stop_day
        )
        action = graded_response if response_active else reference_action
        one_step = slice_scenario(realized_scenario, day, 1)
        state, metrics = simulate_step(
            state,
            action,
            float(input_row["demand"]),
            float(input_row["base_risk"]),
            one_step,
            0,
            config,
        )
        regime = classify_regime(state, metrics, config)
        observability = local_observability_score(
            context.observability_base,
            state,
            float(input_row["risk_uncertainty"]),
            metrics,
        )
        controllability = local_controllability_score(
            state,
            metrics,
            config,
        )
        rows.append({
            "day": int(input_row["day"]),
            "regime": regime,
            "selected_policy": action.name,
            "response_active": int(response_active),
            "response_intensity": (
                bounded_intensity if response_active else 0.0
            ),
            "base_risk": float(input_row["base_risk"]),
            "risk_uncertainty": float(input_row["risk_uncertainty"]),
            "observability": observability,
            "controllability": controllability,
            **metrics,
        })
    return pd.DataFrame(rows)


def forecast_confusion_experiment(
    context: RunContext,
    config: Mapping[str, Any],
    actions: Sequence[Action],
    seeds: Sequence[int],
    *,
    start_day: int | None = None,
    duration_days: int = 42,
    incident_duration_days: int | None = None,
    forecast_signal_duration_days: int | None = None,
    low_probability: float | None = None,
    high_probability: float | None = None,
    forecast_low_probability: float | None = None,
    forecast_high_probability: float | None = None,
    truth_nominal_probability: float | None = None,
    truth_incident_probability: float | None = None,
    alert_threshold: float | None = None,
    interval_half_width: float | None = None,
    alert_response_policy: str = "balanced_robust",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run TP/FP/FN/TN with forecast, truth, action and consequence separated."""

    days = len(context.input_series)
    start = int(days * 0.35) if start_day is None else int(start_day)
    paired_seeds = _validated_unique_seeds(seeds)
    if days < 2:
        raise ValueError("TP/FP/FN/TN experiments require at least two days.")
    if not 1 <= start < days:
        raise ValueError(
            "start_day must leave at least one common pre-event baseline day."
        )
    response_duration = int(duration_days)
    incident_duration = int(
        incident_duration_days
        if incident_duration_days is not None
        else response_duration
    )
    forecast_duration = int(
        forecast_signal_duration_days
        if forecast_signal_duration_days is not None
        else response_duration
    )
    if min(response_duration, incident_duration, forecast_duration) < 1:
        raise ValueError(
            "Response, incident and forecast-signal durations must be positive."
        )
    legacy_probability_alias_used = (
        low_probability is not None or high_probability is not None
    )
    explicit_probability_arguments_used = any(
        value is not None
        for value in (
            forecast_low_probability,
            forecast_high_probability,
            truth_nominal_probability,
            truth_incident_probability,
        )
    )
    if legacy_probability_alias_used:
        if low_probability is None or high_probability is None:
            raise ValueError(
                "Legacy low_probability/high_probability aliases must be "
                "provided together."
            )
        if explicit_probability_arguments_used:
            raise ValueError(
                "Do not combine legacy low_probability/high_probability "
                "aliases with explicit forecast/truth probabilities."
            )
        # Exact backward-compatible protocol: the two historical values drove
        # both the forecast signal and the physical truth envelope.
        forecast_low_probability = float(low_probability)
        forecast_high_probability = float(high_probability)
        truth_nominal_probability = float(low_probability)
        truth_incident_probability = float(high_probability)
    else:
        forecast_low_probability = float(
            0.08
            if forecast_low_probability is None
            else forecast_low_probability
        )
        forecast_high_probability = float(
            0.82
            if forecast_high_probability is None
            else forecast_high_probability
        )
        truth_nominal_probability = float(
            0.08
            if truth_nominal_probability is None
            else truth_nominal_probability
        )
        truth_incident_probability = float(
            0.82
            if truth_incident_probability is None
            else truth_incident_probability
        )
    if not (
        np.isfinite(forecast_low_probability)
        and np.isfinite(forecast_high_probability)
        and 0.0
        <= float(forecast_low_probability)
        < float(forecast_high_probability)
        <= 1.0
    ):
        raise ValueError(
            "Expected 0 <= forecast_low_probability < "
            "forecast_high_probability <= 1."
        )
    if not (
        np.isfinite(truth_nominal_probability)
        and np.isfinite(truth_incident_probability)
        and 0.0
        <= float(truth_nominal_probability)
        < float(truth_incident_probability)
        <= 1.0
    ):
        raise ValueError(
            "Expected 0 <= truth_nominal_probability < "
            "truth_incident_probability <= 1."
        )
    threshold = (
        float(alert_threshold)
        if alert_threshold is not None
        else 0.5
        * (
            float(forecast_low_probability)
            + float(forecast_high_probability)
        )
    )
    if not (
        np.isfinite(threshold)
        and float(forecast_low_probability)
        < threshold
        <= float(forecast_high_probability)
    ):
        raise ValueError(
            "alert_threshold must separate no-alert and alert probabilities."
        )
    mapping = config.get("physical_risk_mapping", {})
    cases = {
        "TP": (True, True),
        "FP": (True, False),
        "FN": (False, True),
        "TN": (False, False),
    }
    reference_action = next(action for action in actions if action.name == "mrp_reference")
    response_candidates = [
        action for action in actions if action.name == alert_response_policy
    ]
    if not response_candidates:
        raise ValueError(
            f"Unknown alert_response_policy: {alert_response_policy}"
        )
    response_action = response_candidates[0]
    if response_action.name == reference_action.name:
        raise ValueError(
            "alert_response_policy must differ from mrp_reference so the "
            "forecast-action channel is identifiable."
        )
    rows: list[dict[str, Any]] = []
    for case, (predicted_event, truth_event) in cases.items():
        forecast_context = build_confusion_context(
            context,
            predicted_event=predicted_event,
            start_day=start,
            duration_days=forecast_duration,
            low_probability=forecast_low_probability,
            high_probability=forecast_high_probability,
            interval_half_width=interval_half_width,
            mapping_config=mapping,
        )
        truth_envelope = build_truth_physical_envelope(
            days,
            truth_event=truth_event,
            start_day=start,
            duration_days=incident_duration,
            low_probability=truth_nominal_probability,
            high_probability=truth_incident_probability,
            mapping_config=mapping,
        )
        effective_width = (
            float(interval_half_width)
            if interval_half_width is not None
            else float(0.12 if predicted_event else 0.05)
        )
        # The alert cell remains defined by the forecast centre relative to the
        # threshold, while the bounded response magnitude uses the conservative
        # upper probability. This keeps physical truth fixed and makes interval
        # width an explicit operational design variable instead of a display-only
        # observability input.
        forecast_center = (
            float(forecast_high_probability)
            if predicted_event
            else float(forecast_low_probability)
        )
        conservative_alert_probability = float(
            np.clip(forecast_center + effective_width, 0.0, 1.0)
        )
        response_intensity = (
            float(
                np.clip(
                    (
                        conservative_alert_probability - threshold
                    )
                    / max(1.0 - threshold, 1e-9),
                    0.05,
                    1.0,
                )
            )
            if predicted_event
            else 0.0
        )
        for seed in paired_seeds:
            realized = sample_scenarios(
                1, days, config, int(seed), physical_risk=truth_envelope
            )[0]
            physical_scenario_fingerprint = _scenario_fingerprint(realized)
            demand_path = forecast_context.input_series["demand"].to_numpy(dtype=float)
            risk_path = forecast_context.input_series["base_risk"].to_numpy(dtype=float)
            initial = initial_state(config, float(demand_path[0]), float(risk_path[0]))
            mrp_trajectory, _ = simulate_horizon(
                initial,
                reference_action,
                demand_path,
                risk_path,
                realized,
                config,
            )
            mrp_metrics = _confusion_trajectory_metrics(
                mrp_trajectory,
                config,
                event_start_day=start,
                event_duration_days=incident_duration,
            )
            trajectory = _simulate_forecast_gated_response(
                forecast_context,
                config,
                reference_action=reference_action,
                response_action=response_action,
                response_intensity=response_intensity,
                predicted_event=predicted_event,
                start_day=start,
                duration_days=response_duration,
                realized_scenario=realized,
            )
            summary = adaptive_summary(trajectory)
            adaptive_metrics = _confusion_trajectory_metrics(
                trajectory,
                config,
                event_start_day=start,
                event_duration_days=incident_duration,
            )
            rows.append({
                "case": case,
                "predicted_event": int(predicted_event),
                "truth_event": int(truth_event),
                "alert_triggered": int(
                    float(forecast_context.input_series["base_risk"].max())
                    >= threshold
                ),
                "incident_occurred": int(truth_event),
                "seed": int(seed),
                "alert_threshold": threshold,
                "interval_half_width": effective_width,
                "conservative_alert_probability": (
                    conservative_alert_probability
                ),
                "response_intensity": response_intensity,
                "response_intensity_method": (
                    "bounded_upper_probability_exceedance"
                ),
                "alert_duration_days": response_duration,
                "alert_response_duration_days": response_duration,
                "forecast_signal_duration_days": forecast_duration,
                "incident_duration_days": incident_duration,
                "physical_scenario_fingerprint": (
                    physical_scenario_fingerprint
                ),
                # Legacy aliases retained for downstream readers; both refer
                # only to the forecast signal, never to physical truth.
                "low_probability": float(forecast_low_probability),
                "high_probability": float(forecast_high_probability),
                "forecast_low_probability": float(
                    forecast_low_probability
                ),
                "forecast_high_probability": float(
                    forecast_high_probability
                ),
                "truth_nominal_probability": float(
                    truth_nominal_probability
                ),
                "truth_incident_probability": float(
                    truth_incident_probability
                ),
                "response_protocol": (
                    "forecast_gated_graded_bounded_policy"
                ),
                "alert_response_policy": response_action.name,
                "action_taken": int(
                    trajectory["response_active"].astype(int).any()
                ),
                "response_action_days": int(
                    trajectory["response_active"].astype(int).sum()
                ),
                "selected_policy_changes": int(
                    trajectory["selected_policy"]
                    .astype(str)
                    .ne(
                        trajectory["selected_policy"]
                        .astype(str)
                        .shift(1)
                    )
                    .iloc[1:]
                    .sum()
                ),
                "dominant_policy": str(
                    trajectory["selected_policy"].mode().iloc[0]
                ),
                **adaptive_metrics,
                **{f"mrp_{name}": value for name, value in mrp_metrics.items()},
                **summary,
            })
    runs = pd.DataFrame(rows)
    aggregate_columns = [
        "service_loss", "backlog_area", "max_backlog", "mean_service",
        "mean_inventory", "unused_stock_area", "post_event_overstock_area",
        "order_area", "over_ordering_area", "nervousness_area",
        "production_nervousness_area", "expedite_area",
        "purchase_cost_proxy", "transport_cost_proxy", "total_cost_proxy",
        "supplier_stress_area", "supplier_risk_area", "risk_creation_area",
        "quality_loss_area", "mean_supplier_risk", "mean_observability",
        "mean_controllability",
    ]
    summary_rows: list[dict[str, Any]] = []
    for case, group in runs.groupby("case"):
        row: dict[str, Any] = {
            "case": case,
            "predicted_event": int(group["predicted_event"].iloc[0]),
            "truth_event": int(group["truth_event"].iloc[0]),
            "alert_triggered": int(group["alert_triggered"].iloc[0]),
            "incident_occurred": int(group["incident_occurred"].iloc[0]),
            "action_taken": int(group["action_taken"].iloc[0]),
            "response_action_days": int(
                group["response_action_days"].iloc[0]
            ),
            "response_intensity": float(
                group["response_intensity"].iloc[0]
            ),
            "conservative_alert_probability": float(
                group["conservative_alert_probability"].iloc[0]
            ),
            "response_intensity_method": str(
                group["response_intensity_method"].iloc[0]
            ),
            "response_protocol": str(
                group["response_protocol"].iloc[0]
            ),
            "alert_response_policy": str(
                group["alert_response_policy"].iloc[0]
            ),
            "runs": int(len(group)),
            "dominant_policy": str(group["dominant_policy"].mode().iloc[0]),
            "alert_threshold": float(group["alert_threshold"].iloc[0]),
            "interval_half_width": float(group["interval_half_width"].iloc[0]),
            "alert_duration_days": int(group["alert_duration_days"].iloc[0]),
            "alert_response_duration_days": int(
                group["alert_response_duration_days"].iloc[0]
            ),
            "forecast_signal_duration_days": int(
                group["forecast_signal_duration_days"].iloc[0]
            ),
            "incident_duration_days": int(
                group["incident_duration_days"].iloc[0]
            ),
            "low_probability": float(group["low_probability"].iloc[0]),
            "high_probability": float(group["high_probability"].iloc[0]),
            "forecast_low_probability": float(
                group["forecast_low_probability"].iloc[0]
            ),
            "forecast_high_probability": float(
                group["forecast_high_probability"].iloc[0]
            ),
            "truth_nominal_probability": float(
                group["truth_nominal_probability"].iloc[0]
            ),
            "truth_incident_probability": float(
                group["truth_incident_probability"].iloc[0]
            ),
        }
        scenario_fingerprints = sorted(
            group["physical_scenario_fingerprint"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        row["physical_scenario_fingerprint_count"] = len(
            scenario_fingerprints
        )
        row["physical_scenario_set_fingerprint"] = hashlib.sha256(
            "|".join(scenario_fingerprints).encode("ascii")
        ).hexdigest()
        for column in aggregate_columns:
            row[f"mean_{column}"] = float(group[column].mean())
            row[f"p90_{column}"] = float(group[column].quantile(0.90))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("case").reset_index(drop=True)

    oracle_for = {"TP": "TP", "FN": "TP", "TN": "TN", "FP": "TN"}
    by_case_seed = runs.set_index(["case", "seed"])
    regret_rows: list[dict[str, Any]] = []
    regret_metrics = {
        "service_loss": "service_loss",
        "backlog_area": "backlog",
        "unused_stock_area": "unused_stock",
        "post_event_overstock_area": "post_event_overstock",
        "over_ordering_area": "over_ordering",
        "nervousness_area": "nervousness",
        "production_nervousness_area": "production_nervousness",
        "expedite_area": "expedite",
        "total_cost_proxy": "total_cost",
        "supplier_stress_area": "supplier_stress",
        "supplier_risk_area": "supplier_risk",
        "risk_creation_area": "risk_creation",
        "quality_loss_area": "quality_loss",
    }
    for _, row in runs.iterrows():
        oracle_case = oracle_for[str(row["case"])]
        oracle = by_case_seed.loc[(oracle_case, int(row["seed"]))]
        regret_row: dict[str, Any] = {
            "case": row["case"],
            "oracle_case": oracle_case,
            "benchmark_case": oracle_case,
            "benchmark_definition": (
                "matched_truth_correct_forecast_gated_response"
            ),
            "regret_sign_convention": (
                "candidate_minus_benchmark; positive_is_worse"
            ),
            "seed": int(row["seed"]),
            "alert_threshold": float(row["alert_threshold"]),
            "interval_half_width": float(row["interval_half_width"]),
            "alert_duration_days": int(row["alert_duration_days"]),
            "alert_response_duration_days": int(
                row["alert_response_duration_days"]
            ),
            "forecast_signal_duration_days": int(
                row["forecast_signal_duration_days"]
            ),
            "incident_duration_days": int(row["incident_duration_days"]),
            "physical_scenario_fingerprint": str(
                row["physical_scenario_fingerprint"]
            ),
        }
        for metric, label in regret_metrics.items():
            regret_row[f"{label}_regret"] = float(row[metric] - oracle[metric])
            regret_row[f"{label}_regret_vs_mrp"] = float(
                row[metric] - row[f"mrp_{metric}"]
            )
        regret_rows.append(regret_row)
    regret = pd.DataFrame(regret_rows)
    return runs, summary, regret


def forecast_confusion_sensitivity_experiment(
    context: RunContext,
    config: Mapping[str, Any],
    actions: Sequence[Action],
    seeds: Sequence[int],
    *,
    alert_thresholds: Sequence[float] = (0.40, 0.70),
    interval_half_widths: Sequence[float] = (0.05, 0.18),
    alert_durations_days: Sequence[int] = (14, 42),
    start_day: int | None = None,
    forecast_low_probability: float = 0.08,
    forecast_high_probability: float = 0.82,
    truth_nominal_probability: float = 0.08,
    truth_incident_probability: float = 0.82,
    incident_duration_days: int = 42,
    forecast_signal_duration_days: int = 42,
    alert_response_policy: str = "balanced_robust",
) -> pd.DataFrame:
    """Evaluate a compact full-factorial alert-threshold/width/duration grid.

    TP/FP/FN/TN identities and physical truth remain fixed at every grid point.
    Forecast probabilities are explicit fixed inputs independent of the tested
    threshold set. The threshold changes the decision margin, while interval
    width changes the graded bounded response through the conservative upper
    probability. Physical-incident and forecast-signal durations are fixed;
    only the bounded response window uses ``alert_durations_days``. The returned
    table contains case-level KPIs and mean regret versus both the
    correct-forecast oracle and MRP.
    """

    threshold_values = [
        float(np.clip(threshold, 0.02, 0.98))
        for threshold in alert_thresholds
    ]
    if not threshold_values:
        return pd.DataFrame()
    forecast_low_probability = float(forecast_low_probability)
    forecast_high_probability = float(forecast_high_probability)
    if not (
        np.isfinite(forecast_low_probability)
        and np.isfinite(forecast_high_probability)
        and 0.0
        <= forecast_low_probability
        < min(threshold_values)
        and max(threshold_values)
        <= forecast_high_probability
        <= 1.0
    ):
        raise ValueError(
            "Fixed forecast probabilities must satisfy 0 <= low < every "
            "threshold <= high <= 1."
        )
    if not (
        np.isfinite(truth_nominal_probability)
        and np.isfinite(truth_incident_probability)
        and 0.0
        <= float(truth_nominal_probability)
        < float(truth_incident_probability)
        <= 1.0
    ):
        raise ValueError(
            "Fixed physical-truth probabilities must satisfy "
            "0 <= nominal < incident <= 1."
        )
    if int(incident_duration_days) < 1 or int(
        forecast_signal_duration_days
    ) < 1:
        raise ValueError(
            "Fixed incident and forecast-signal durations must be positive."
        )

    output: list[pd.DataFrame] = []
    for threshold_value in threshold_values:
        for width in interval_half_widths:
            width_value = float(np.clip(width, 0.0, 0.49))
            for duration in alert_durations_days:
                duration_value = max(1, int(duration))
                _, case_summary, regret = forecast_confusion_experiment(
                    context,
                    config,
                    actions,
                    seeds,
                    start_day=start_day,
                    duration_days=duration_value,
                    incident_duration_days=int(incident_duration_days),
                    forecast_signal_duration_days=int(
                        forecast_signal_duration_days
                    ),
                    forecast_low_probability=forecast_low_probability,
                    forecast_high_probability=forecast_high_probability,
                    truth_nominal_probability=truth_nominal_probability,
                    truth_incident_probability=truth_incident_probability,
                    alert_threshold=threshold_value,
                    interval_half_width=width_value,
                    alert_response_policy=alert_response_policy,
                )
                regret_summary = (
                    regret.groupby("case", as_index=False)
                    .mean(numeric_only=True)
                    .drop(
                        columns=[
                            "seed",
                            "alert_threshold",
                            "interval_half_width",
                            "alert_duration_days",
                            "alert_response_duration_days",
                            "forecast_signal_duration_days",
                            "incident_duration_days",
                        ],
                        errors="ignore",
                    )
                )
                combined = case_summary.merge(
                    regret_summary, on="case", how="left", validate="one_to_one"
                )
                combined["sensitivity_design"] = (
                    "fixed_truth_full_factorial_threshold_x_interval_width_x_duration"
                )
                combined["probability_design"] = (
                    "fixed_across_threshold_grid"
                )
                output.append(combined)
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame()
