from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def write_json(path: Path, payload: Any) -> None:
    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value]
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def provenance_report_lines(summary: Mapping[str, Any]) -> list[str]:
    """Render the machine-readable evidence lineage without upgrading claims."""

    provenance = summary.get("provenance") or {}
    baseline = provenance.get("baseline") or {}
    forecast = provenance.get("forecast") or {}
    code = provenance.get("code_snapshot") or {}
    git = code.get("git") or {}
    if not provenance:
        return ["- Evidence provenance: not reported."]
    return [
        (
            "- Baseline evidence: "
            f"origin=`{baseline.get('origin', 'not_reported')}`; industrial "
            f"status=`{baseline.get('industrial_status', 'not_reported')}`; "
            f"SHA-256=`{baseline.get('source_sha256') or 'not_available'}`."
        ),
        (
            "- Forecast evidence: "
            f"origin=`{forecast.get('origin', 'not_reported')}`; industrial "
            f"status=`{forecast.get('industrial_status', 'not_reported')}`; "
            f"history=`{forecast.get('history_origin', 'not_reported')}`; "
            f"labels=`{forecast.get('label_origin', 'not_reported')}`; temporal "
            f"features=`{forecast.get('temporal_feature_origin', 'not_reported')}`; "
            f"use status=`{forecast.get('evaluation_status', 'not_reported')}`."
        ),
        (
            "- Forecast/calibration SHA-256: "
            f"`{forecast.get('source_sha256') or 'not_available'}` / "
            f"`{forecast.get('calibration_sha256') or 'not_available'}`."
        ),
        (
            "- Code snapshot: "
            f"SHA-256=`{code.get('sha256') or 'not_available'}` over "
            f"{int(code.get('file_count') or 0)} files; git HEAD="
            f"`{git.get('head') or 'not_available'}`; branch="
            f"`{git.get('branch') or 'detached_or_unavailable'}`; dirty="
            f"`{git.get('dirty') if git.get('dirty') is not None else 'not_available'}`."
        ),
    ]


def prediction_coverage_report_lines(
    prediction: Mapping[str, Any],
) -> list[str]:
    """Render coverage evidence without turning score calibration into a p-CI."""

    status = str(prediction.get("coverage_guarantee_status") or "not_reported")
    calibration_status = str(
        prediction.get("conformal_calibration_status") or "not_reported"
    )
    target = str(prediction.get("coverage_target") or "not_reported")
    semantics = str(prediction.get("interval_semantics") or "not_reported")
    limitations = str(prediction.get("coverage_limitations") or "not_reported")
    definition = str(prediction.get("coverage_definition") or "not_reported")
    effective_level = prediction.get("effective_finite_sample_level")
    maximum_level = prediction.get("maximum_attainable_finite_sample_level")
    requested_level = prediction.get("requested_nominal_coverage")
    requested_rank = prediction.get("conformal_rank")
    rank_text = str(requested_rank) if requested_rank is not None else "not reported"
    finite_sample_score_available = (
        effective_level is not None
        and target == "future_binary_incident_outcome"
        and status.startswith("finite_sample_binary_outcome_score_level")
    )

    if finite_sample_score_available:
        requested_text = (
            f"{float(requested_level):.2%}"
            if requested_level is not None
            else "not reported"
        )
        evidence = [
            "- Binary-outcome score calibration: "
            f"target=`{target}`; requested level={requested_text}; "
            f"effective finite-sample level={float(effective_level):.2%}; "
            f"rank={rank_text}; definition=`{definition}`; calibration "
            f"status=`{calibration_status}`; interval status=`{status}`."
        ]
    elif status == "provided_interval_coverage_not_evaluated":
        evidence = [
            "- Coverage claim: not evaluated for the source-provided interval; "
            f"target=`{target}`; calibration status=`{calibration_status}`; "
            f"interval status=`{status}`."
        ]
    else:
        maximum_text = (
            f"; maximum attainable finite-sample level={float(maximum_level):.2%}"
            if maximum_level is not None
            else ""
        )
        evidence = [
            "- Coverage claim: none; "
            f"target=`{target}`; interval status=`{status}`; conformal "
            f"calibration status=`{calibration_status}`; requested "
            f"rank={rank_text}{maximum_text}."
        ]

    empirical = prediction.get("empirical_calibration_coverage")
    coverage_rows = int(prediction.get("calibration_coverage_rows") or 0)
    metric = str(
        prediction.get("empirical_calibration_metric") or "not_reported"
    )
    if empirical is not None and coverage_rows > 0:
        evidence.append(
            "- In-sample calibration-score inclusion rate: "
            f"{float(empirical):.2%} over {coverage_rows} scored rows; "
            f"metric=`{metric}`. This is not independent predictive coverage."
        )
    else:
        evidence.append(
            "- In-sample calibration-score inclusion rate: not available; "
            f"metric=`{metric}`."
        )
    evidence.extend([
        f"- Interval semantics: `{semantics}`.",
        f"- Coverage limitations: {limitations}",
    ])
    calibration_rows_before = int(
        prediction.get("calibration_rows_before") or 0
    )
    calibration_rows_after = int(
        prediction.get("calibration_rows_after") or 0
    )
    excluded_overlap_rows = int(
        prediction.get("excluded_overlap_rows") or 0
    )
    operational_target_rows = int(
        prediction.get("operational_target_rows") or 0
    )
    overlap_keys = list(prediction.get("overlap_key_columns") or [])
    overlap_status = str(prediction.get("overlap_status") or "not_reported")
    if calibration_rows_before or operational_target_rows:
        evidence.append(
            "- Operational-snapshot/scored-row overlap: "
            f"status=`{overlap_status}`; operational target rows="
            f"{operational_target_rows}; calibration rows before/after exact "
            f"overlap exclusion={calibration_rows_before}/{calibration_rows_after}; "
            f"excluded overlap rows={excluded_overlap_rows}; keys={overlap_keys}."
        )
    unique_probabilities = int(
        prediction.get("operational_probability_unique_count") or 0
    )
    if operational_target_rows:
        evidence.append(
            "- Operational snapshot probability diversity: unique probability "
            f"count={unique_probabilities} over {operational_target_rows} rows; "
            f"snapshot=`{prediction.get('operational_snapshot_date') or 'not_reported'}`; "
            f"week=`{prediction.get('operational_week_index') if prediction.get('operational_week_index') is not None else 'not_reported'}`."
        )
    evidence.append(
        "- Calibration-use status: "
        f"`{prediction.get('calibration_use_status', 'not_reported')}`; forecast "
        f"origin=`{prediction.get('forecast_origin', 'not_reported')}`. This is "
        "retrospective evidence for a non-deployment PoC, not a latent-probability claim."
    )
    return evidence


def _save_figure(
    fig: Any,
    path: Path,
    figure_provenance_label: str = "",
) -> None:
    if figure_provenance_label:
        fig.text(
            0.995,
            0.004,
            figure_provenance_label,
            ha="right",
            va="bottom",
            fontsize=7,
            color="dimgray",
        )
        fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
    else:
        fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def save_plots(output_dir: Path, adaptive: pd.DataFrame, decisions: pd.DataFrame,
               policy_comparison: pd.DataFrame, fixed_trajectories: pd.DataFrame,
               transitions: pd.DataFrame, constraints: pd.DataFrame,
               adaptive_state_space: pd.DataFrame, impedance: pd.DataFrame,
               figure_provenance_label: str = "") -> None:
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(adaptive["day"], adaptive["service"], label="service")
    axes[0].plot(adaptive["day"], adaptive["backlog"], label="backlog")
    axes[0].legend(); axes[0].set_title("Adaptive policy: service and backlog")
    axes[1].plot(adaptive["day"], adaptive["raw_inventory"], label="raw")
    axes[1].plot(adaptive["day"], adaptive["finished_inventory"], label="finished")
    axes[1].legend(); axes[1].set_title("Inventory states")
    axes[2].plot(adaptive["day"], adaptive["supplier_risk"], label="supplier risk")
    axes[2].plot(adaptive["day"], adaptive["base_risk"], linestyle="--", label="forecast risk")
    axes[2].legend(); axes[2].set_xlabel("day"); axes[2].set_title("Exogenous and endogenous risk")
    _save_figure(
        fig,
        plot_dir / "adaptive_state_trajectory.png",
        figure_provenance_label,
    )

    chain_series = [
        ("base_risk", "forecast risk", "incident probability"),
        ("action_magnitude", "applied response magnitude", "dimensionless index"),
        ("supplier_stress", "simulated supplier stress", "stress index"),
        ("supplier_risk", "resulting supplier risk", "incident probability"),
    ]
    if all(column in adaptive for column, _, _ in chain_series):
        fig, axes = plt.subplots(5, 1, figsize=(12, 11), sharex=True)
        for axis, (column, title, unit) in zip(axes[:4], chain_series):
            axis.plot(adaptive["day"], adaptive[column])
            axis.set_ylabel(unit)
            axis.set_title(title)
        axes[4].plot(
            adaptive["day"],
            (1.0 - adaptive["service"]).clip(lower=0.0),
        )
        axes[4].set_ylabel("service-loss ratio")
        axes[4].set_xlabel("day")
        axes[4].set_title("operational service consequence")
        fig.suptitle(
            "Simulated forecast → action → stress → risk → service chain "
            "(exploratory, not industrial causal identification)"
        )
        _save_figure(
            fig,
            plot_dir / "forecast_action_stress_risk_service_chain.png",
            figure_provenance_label,
        )

    regime_codes = {name: i for i, name in enumerate(sorted(adaptive["regime"].unique()))}
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.step(adaptive["day"], adaptive["regime"].map(regime_codes), where="post")
    ax.set_yticks(list(regime_codes.values()), list(regime_codes.keys()))
    ax.set_xlabel("day"); ax.set_title("State-dependent regime timeline")
    _save_figure(
        fig,
        plot_dir / "regime_timeline.png",
        figure_provenance_label,
    )

    if not decisions.empty:
        fig, ax = plt.subplots(figsize=(12, 4))
        policy_codes = {name: i for i, name in enumerate(sorted(decisions["selected_policy"].unique()))}
        ax.step(decisions["day"], decisions["selected_policy"].map(policy_codes), where="post")
        ax.set_yticks(list(policy_codes.values()), list(policy_codes.keys()))
        ax.set_xlabel("review day"); ax.set_title("Adaptive policy selection")
        _save_figure(
            fig,
            plot_dir / "adaptive_policy_selection.png",
            figure_provenance_label,
        )

    ordered = policy_comparison.sort_values("robust_score")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(ordered["policy"], ordered["robust_score"])
    ax.tick_params(axis="x", rotation=25); ax.set_ylabel("robust score (lower is better)")
    ax.set_title("Fixed-policy robust comparison")
    _save_figure(
        fig,
        plot_dir / "policy_frontier.png",
        figure_provenance_label,
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(ordered["policy"], ordered["mean_risk_creation"])
    ax.axhline(0.0, linewidth=0.8); ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("mean Risk Creation Index")
    ax.set_title("Risk created by the response relative to MRP")
    _save_figure(
        fig,
        plot_dir / "risk_creation_index_by_policy.png",
        figure_provenance_label,
    )

    sample = fixed_trajectories.groupby(["policy", "step"])["supplier_risk"].median().reset_index()
    fig, ax = plt.subplots(figsize=(12, 5))
    for policy, group in sample.groupby("policy"):
        ax.plot(group["step"], group["supplier_risk"], label=policy)
    ax.legend(ncol=2); ax.set_xlabel("day"); ax.set_ylabel("supplier risk")
    ax.set_title("Supplier-risk trajectories by policy")
    _save_figure(
        fig,
        plot_dir / "supplier_risk_endogenous.png",
        figure_provenance_label,
    )

    fig, ax = plt.subplots(figsize=(7, 6))
    scatter = ax.scatter(adaptive["observability"], adaptive["controllability"], c=adaptive["supplier_risk"])
    ax.set_xlabel("observability"); ax.set_ylabel("controllability")
    ax.set_title("State visibility and available recovery leverage")
    fig.colorbar(scatter, ax=ax, label="supplier risk")
    _save_figure(
        fig,
        plot_dir / "observability_controllability_map.png",
        figure_provenance_label,
    )

    active_cols = [c for c in constraints.columns if c.endswith("_active")]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(constraints["day"], *[constraints[c] for c in active_cols], labels=active_cols)
    ax.legend(loc="upper right", fontsize=7); ax.set_xlabel("day")
    ax.set_title("Active non-smooth constraints")
    _save_figure(
        fig,
        plot_dir / "active_constraints.png",
        figure_provenance_label,
    )

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.step(adaptive_state_space["day"], adaptive_state_space["model_detail_level"], where="post")
    ax.set_yticks([0, 1, 2, 3]); ax.set_xlabel("day"); ax.set_ylabel("detail level")
    ax.set_title("Adaptive state-space detail level")
    _save_figure(
        fig,
        plot_dir / "adaptive_state_space_level.png",
        figure_provenance_label,
    )

    if not impedance.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(impedance["frequency_cycle_per_day"], impedance["magnitude"])
        ax.set_xlabel("frequency (cycle/day)"); ax.set_ylabel("magnitude")
        ax.set_title("Exploratory supplier-impedance spectrum")
        _save_figure(
            fig,
            plot_dir / "supplier_impedance_spectrum.png",
            figure_provenance_label,
        )

    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(transitions, aspect="auto")
    ax.set_xticks(range(len(transitions.columns)), transitions.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(transitions.index)), transitions.index)
    ax.set_title("Regime-transition counts")
    fig.colorbar(image, ax=ax)
    _save_figure(
        fig,
        plot_dir / "regime_transition_matrix.png",
        figure_provenance_label,
    )


def write_report(output_dir: Path, context: Any, adaptive: pd.DataFrame, decisions: pd.DataFrame,
                 policy_comparison: pd.DataFrame, constraints: pd.DataFrame,
                 impedance_summary: Mapping[str, float], summary: Mapping[str, Any]) -> None:
    best = policy_comparison.iloc[0]
    canonical = summary.get("canonical_replay") or {}
    prediction = summary.get("prediction_to_physics") or {}
    rci = summary.get("rci_business_validation") or {}
    calibration = summary.get("regime_calibration") or {}
    nominal_calibration = (
        calibration.get("nominal_parameter_calibration") or {}
    )
    nominal_declared = json.dumps(
        nominal_calibration.get("declared_values") or {},
        sort_keys=True,
    )
    nominal_candidate = json.dumps(
        nominal_calibration.get("aggregate_refit_candidate") or {},
        sort_keys=True,
    )
    nominal_effective = json.dumps(
        nominal_calibration.get("effective_values") or {},
        sort_keys=True,
    )
    canonical_status = str(canonical.get("status") or "not_requested")
    if canonical_status == "executed":
        canonical_limit = (
            "- Canonical actions were applied through a precomputed daily "
            "open-loop schedule; online state-feedback recomputation is not claimed."
        )
        next_step = (
            "Increase the paired canonical seed count, validate prediction-to-physics "
            "coefficients on incidents, and only then evaluate an online constrained controller."
        )
    elif canonical_status == "overlays_prepared":
        canonical_limit = (
            "- Canonical schedules and compatibility overlays were prepared but "
            "the full physical engine was not executed in this run."
        )
        next_step = (
            "Execute `--canonical-replay run` with paired seeds and inspect the "
            "per-run action ledger and replay error status."
        )
    else:
        canonical_limit = (
            f"- Canonical replay status is `{canonical_status}`; no successful "
            "full-engine evidence is claimed for this run."
        )
        next_step = (
            "Resolve the canonical replay status, then execute paired full-engine "
            "runs before drawing operational conclusions."
        )
    prediction_evidence = prediction_coverage_report_lines(prediction)
    provenance_evidence = provenance_report_lines(summary)
    rci_status = str(rci.get("status") or "not_reported")
    if rci_status == "pending_business_review":
        rci_limit = (
            "- RCI business review is pending; simulation metrics are not an "
            "industrially validated operational KPI."
        )
    elif rci_status == "review_available":
        rci_limit = (
            "- Complete RCI ratings are available for exploratory analysis, but "
            "explicit business governance sign-off is still required."
        )
    else:
        rci_limit = (
            f"- RCI business status is `{rci_status}`; no industrial-validation "
            "claim is made."
        )
    oracle_note = (
        "- Canonical oracle rows are retrospective, ex-post selections from "
        "already executed fixed-policy rows; they are not additional engine runs "
        "or an online policy."
        if int(canonical.get("derived_oracle_rows") or 0) > 0
        else "- No online canonical oracle policy is claimed."
    )
    lines = [
        "# SCAN 2027 state-dependent risk-control PoC",
        "",
        "## Purpose",
        "",
        "Transform an uncertain supplier-risk signal into a bounded operational response, while explicitly measuring service, backlog, order nervousness and supplier risk created by the response.",
        "",
        "## Input",
        "",
        f"- Source mode: `{context.source_mode}`",
        f"- Baseline: `{context.baseline_path}`",
        f"- Risk forecast: `{context.risk_path}`",
        f"- Simulated days: {len(adaptive)}",
        f"- Prediction export scopes: {prediction.get('export_scopes', 'not_reported')}; granular pairs: {prediction.get('granular_pairs', 0)}",
        *prediction_evidence,
        "",
        "### Evidence provenance",
        "",
        *provenance_evidence,
        "",
        "### Reduced-model nominal parameter scope",
        "",
        (
            "- Regime-calibration risk signal: "
            f"`{calibration.get('calibration_risk_source', 'not_reported')}`; "
            "this provenance distinguishes canonical event evidence from a "
            "forecast proxy fallback."
        ),
        (
            "- Status: "
            f"`{nominal_calibration.get('status', 'not_reported')}`; "
            f"aggregate refit applied: `{bool(nominal_calibration.get('refit_applied', False))}`; "
            "unit comparability: "
            f"`{nominal_calibration.get('unit_comparability', 'not_reported')}`."
        ),
        f"- Declared parameters: `{nominal_declared}`.",
        f"- Aggregate diagnostic candidate: `{nominal_candidate}`.",
        f"- Effective parameters: `{nominal_effective}`.",
        (
            "- Interpretation: "
            f"{nominal_calibration.get('interpretation', 'not reported')}"
        ),
        "",
        "## Main result",
        "",
        f"- Best fixed policy: **{best['policy']}**",
        f"- Robust score: {float(best['robust_score']):.3f}",
        f"- Adaptive mean service: {float(adaptive['service'].mean()):.3f}",
        f"- Maximum backlog: {float(adaptive['backlog'].max()):.3f} demand-days",
        f"- Mean supplier risk: {float(adaptive['supplier_risk'].mean()):.3f}",
        f"- Mean observability: {float(adaptive['observability'].mean()):.3f}",
        f"- Mean controllability: {float(adaptive['controllability'].mean()):.3f}",
        "",
        "## Interpretation",
        "",
        "The selector compares bounded playbooks on identical uncertainty scenarios. Supplier stress responds to order nervousness and capacity pressure, so an aggressive action can protect inventory while increasing future supplier risk. The adaptive layer reselects the policy at each review period according to the diagnosed regime.",
        "",
        "## Forward-looking outputs",
        "",
        f"- Days with at least one active non-smooth constraint: {int((constraints['active_constraint_count'] > 0).sum())}",
        f"- Peak supplier-response frequency: {impedance_summary.get('peak_frequency_cycle_per_day', 0.0):.4f} cycle/day",
        f"- Equivalent peak period: {impedance_summary.get('peak_period_days', float('nan')):.2f} days",
        "",
        "## Limitations",
        "",
        "- Reduced-order model expressed in equivalent demand-days.",
        "- Its demand and risk paths can come from the simulated etudecas case, but its initial stocks, pipeline and subsequent dynamics are reconstructed hypotheses; reduced paired/confusion runs are not article/BOM state replays.",
        "- Its nominal parameters are hypotheses, not estimates from industrial observations; aggregate cross-item/BOM ratios are not applied unless unit comparability is established.",
        "- Stress and risk coefficients are research hypotheses requiring industrial calibration.",
        "- Finite action library; this is not yet a constrained MPC solver.",
        canonical_limit,
        oracle_note,
        rci_limit,
        "",
        "## Next integration step",
        "",
        next_step,
    ]
    (output_dir / "poc_report.md").write_text("\n".join(lines), encoding="utf-8")
