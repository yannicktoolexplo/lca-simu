from __future__ import annotations

"""Reporting for the SCAN end-2026 validation work package."""

from pathlib import Path
from typing import Any, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _save(fig: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def save_end_2026_plots(
    output_dir: Path,
    calibration_frame: pd.DataFrame,
    calibration_evidence: pd.DataFrame,
    prediction_interval: pd.DataFrame,
    physical_envelope: pd.DataFrame,
    paired_summary: pd.DataFrame,
    confusion_summary: pd.DataFrame,
    confusion_regret: pd.DataFrame,
    rci_review: pd.DataFrame,
    canonical_summary: pd.DataFrame | None = None,
) -> None:
    plot_dir = output_dir / "plots" / "end_2026"
    plot_dir.mkdir(parents=True, exist_ok=True)

    if not calibration_frame.empty:
        regime_order = list(dict.fromkeys(calibration_frame["calibrated_regime"].astype(str)))
        codes = {name: index for index, name in enumerate(regime_order)}
        fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
        axes[0].plot(calibration_frame["day"], calibration_frame["service"], label="service")
        axes[0].plot(calibration_frame["day"], calibration_frame["backlog_days"], label="backlog (demand-days)")
        axes[0].set_title("Canonical trajectory used for regime calibration")
        axes[0].legend()
        axes[1].plot(calibration_frame["day"], calibration_frame["material_cover_days"], label="critical material cover")
        axes[1].plot(calibration_frame["day"], calibration_frame["max_utilization"], label="max utilization")
        axes[1].legend()
        axes[2].step(
            calibration_frame["day"], calibration_frame["calibrated_regime"].map(codes), where="post"
        )
        axes[2].set_yticks(list(codes.values()), list(codes.keys()))
        axes[2].set_xlabel("day")
        axes[2].set_title("Calibrated state-dependent regimes")
        _save(fig, plot_dir / "regime_calibration_trajectory.png")

    if not calibration_evidence.empty:
        ordered = calibration_evidence.reset_index(drop=True)
        x = np.arange(len(ordered))
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.bar(x - 0.18, ordered["previous_value"], width=0.36, label="initial threshold")
        ax.bar(x + 0.18, ordered["calibrated_value"], width=0.36, label="calibrated threshold")
        ax.set_xticks(x, ordered["threshold"], rotation=30, ha="right")
        ax.set_title("Regime thresholds: initial hypotheses vs trajectory calibration")
        ax.legend()
        _save(fig, plot_dir / "regime_threshold_comparison.png")

    if not prediction_interval.empty:
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.fill_between(
            prediction_interval["day"], prediction_interval["risk_lower"], prediction_interval["risk_upper"],
            alpha=0.25, label="prediction interval",
        )
        ax.plot(prediction_interval["day"], prediction_interval["risk_center"], label="forecast center")
        ax.set_ylim(0, 1)
        ax.set_xlabel("day")
        ax.set_ylabel("supplier incident probability")
        ax.set_title("Supplier-risk forecast with explicit uncertainty")
        ax.legend()
        _save(fig, plot_dir / "prediction_interval.png")

    if not physical_envelope.empty:
        fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
        for suffix, style in [("lower", ":"), ("center", "-"), ("upper", "--")]:
            axes[0, 0].plot(physical_envelope["day"], physical_envelope[f"availability_multiplier_{suffix}"], linestyle=style, label=suffix)
            axes[0, 1].plot(physical_envelope["day"], physical_envelope[f"capacity_multiplier_{suffix}"], linestyle=style)
            axes[1, 0].plot(physical_envelope["day"], physical_envelope[f"lead_time_extra_days_{suffix}"], linestyle=style)
            axes[1, 1].plot(physical_envelope["day"], physical_envelope[f"quality_yield_multiplier_{suffix}"], linestyle=style)
        axes[0, 0].set_title("Availability multiplier")
        axes[0, 1].set_title("Capacity multiplier")
        axes[1, 0].set_title("Additional lead time (days)")
        axes[1, 1].set_title("Quality-yield multiplier")
        axes[0, 0].legend(title="interval side")
        axes[1, 0].set_xlabel("day")
        axes[1, 1].set_xlabel("day")
        fig.suptitle("Physical perturbation envelope derived from supplier prediction")
        _save(fig, plot_dir / "prediction_to_physical_perturbations.png")

    if not paired_summary.empty:
        ordered = paired_summary.sort_values("mean_delta_score")
        x = np.arange(len(ordered))
        lower = ordered["mean_delta_score"] - ordered["ci95_low_delta_score"]
        upper = ordered["ci95_high_delta_score"] - ordered["mean_delta_score"]
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(x, ordered["mean_delta_score"], yerr=np.vstack([lower.clip(lower=0), upper.clip(lower=0)]), capsize=4)
        ax.axhline(0, linewidth=0.8)
        ax.set_xticks(x, ordered["policy"], rotation=25, ha="right")
        ax.set_ylabel("paired score delta vs MRP (lower is better)")
        ax.set_title("Policy comparison with common random numbers")
        _save(fig, plot_dir / "paired_policy_comparison.png")

    if not confusion_summary.empty:
        order = [case for case in ["TP", "FP", "FN", "TN"] if case in set(confusion_summary["case"])]
        ordered = confusion_summary.set_index("case").loc[order].reset_index()
        x = np.arange(len(ordered))
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
        axes[0].bar(x, ordered["mean_service_loss"])
        axes[0].set_title("Service loss")
        axes[1].bar(x, ordered["mean_nervousness_area"])
        axes[1].set_title("Plan/order nervousness")
        axes[2].bar(x, ordered["mean_risk_creation_area"])
        axes[2].set_title("Risk created by response")
        for ax in axes:
            ax.set_xticks(x, ordered["case"])
        fig.suptitle("Explicit true-positive / false-positive / false-negative / true-negative experiments")
        _save(fig, plot_dir / "forecast_confusion_cases.png")

    if not confusion_regret.empty:
        regret = confusion_regret.groupby("case", as_index=False)[[
            "service_loss_regret", "backlog_regret", "nervousness_regret", "risk_creation_regret"
        ]].mean()
        order = [case for case in ["FP", "FN"] if case in set(regret["case"])]
        if order:
            regret = regret.set_index("case").loc[order]
            fig, ax = plt.subplots(figsize=(10, 5))
            regret.plot(kind="bar", ax=ax)
            ax.axhline(0, linewidth=0.8)
            ax.set_ylabel("regret relative to oracle forecast")
            ax.set_title("Operational cost of forecast errors")
            _save(fig, plot_dir / "forecast_error_regret.png")

    if not rci_review.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        scatter = ax.scatter(
            rci_review["forecast_nervousness"], rci_review["model_rci"],
            s=40 + 80 * rci_review["model_rci_severity_proxy"].clip(lower=0),
            c=rci_review["forecast_service_loss"], alpha=0.8,
        )
        ax.set_xlabel("order/plan nervousness over review window")
        ax.set_ylabel("model Risk Creation Index")
        ax.set_title("Episodes prepared for procurement and planning review")
        fig.colorbar(scatter, ax=ax, label="service-loss area")
        _save(fig, plot_dir / "rci_business_review_episodes.png")

    if canonical_summary is not None and not canonical_summary.empty:
        ordered = canonical_summary.sort_values("mean_delta_service_loss")
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(ordered["policy"], ordered["mean_delta_service_loss"])
        ax.axhline(0, linewidth=0.8)
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("paired canonical service-loss delta vs MRP")
        ax.set_title("Full-engine canonical replay with paired seeds")
        _save(fig, plot_dir / "canonical_paired_replay.png")


def write_end_2026_report(
    output_dir: Path,
    manifest: Mapping[str, Any],
    calibration_evidence: pd.DataFrame,
    paired_summary: pd.DataFrame,
    confusion_summary: pd.DataFrame,
    rci_status: Mapping[str, Any],
    canonical_summary: pd.DataFrame | None,
) -> None:
    calibration = manifest.get("regime_calibration", {})
    prediction = manifest.get("prediction_to_physics", {})
    canonical = manifest.get("canonical_replay", {})
    lines = [
        "# RESILIENCE-SCAN — validation package for end 2026",
        "",
        "## Purpose",
        "",
        "Close the six end-2026 gaps between the existing etudecas prototype and the 2027 robust-control programme: regime calibration, probabilistic-to-physical risk mapping, canonical action replay, paired policy comparison, explicit forecast-error experiments, and business validation of the Risk Creation Index.",
        "",
        "## 1. Regime calibration on etudecas trajectories",
        "",
        f"- Source mode: `{calibration.get('source_mode')}`",
        f"- Baseline: `{calibration.get('baseline_path')}`",
        f"- Days used: {calibration.get('days', 0)}",
        f"- Material-cover source: `{calibration.get('material_cover_source', 'unknown')}`",
        f"- High / medium / low confidence thresholds: {calibration.get('high_confidence_thresholds', 0)} / {calibration.get('medium_confidence_thresholds', 0)} / {calibration.get('low_confidence_thresholds', 0)}",
        "",
    ]
    if not calibration_evidence.empty:
        lines.extend([
            "| Threshold | Previous | Calibrated | Anchor days | Confidence |",
            "|---|---:|---:|---:|---|",
            *[
                f"| {row.threshold} | {row.previous_value:.4g} | {row.calibrated_value:.4g} | {int(row.anchor_days)} | {row.confidence} |"
                for row in calibration_evidence.itertuples()
            ],
            "",
        ])
    lines.extend([
        "## 2. Supplier-prediction uncertainty mapped to physical disruptions",
        "",
        f"- Prediction file: `{prediction.get('prediction_path')}`",
        f"- Interval method: `{prediction.get('interval_method')}`",
        f"- Nominal coverage: {prediction.get('nominal_coverage')}",
        "- Physical outputs: availability, capacity, lead-time, quality-yield and cost envelopes.",
        "- These coefficients remain calibration hypotheses; the ledger exposes every mapping assumption.",
        "",
        "## 3. Policy comparison with paired seeds",
        "",
        "Every policy is evaluated on the same stochastic paths. This common-random-number design isolates the policy effect from Monte Carlo noise.",
        "",
    ])
    if not paired_summary.empty:
        lines.extend([
            "| Policy | Paired runs | Mean score delta | Service win rate | Non-positive RCI rate |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {row.policy} | {int(row.paired_seed_count)} | {row.mean_delta_score:.4g} | {row.service_win_rate_vs_mrp:.1%} | {row.risk_creation_nonpositive_rate:.1%} |"
                for row in paired_summary.itertuples()
            ],
            "",
        ])
    lines.extend([
        "## 4. False positives and false negatives",
        "",
        "The forecast and the physical truth are separated. TP/FP/FN/TN cases therefore measure the operational consequences of acting on a wrong alert or missing a real event.",
        "",
    ])
    if not confusion_summary.empty:
        lines.extend([
            "| Case | Predicted event | Real event | Mean service loss | Mean nervousness | Mean RCI area |",
            "|---|---:|---:|---:|---:|---:|",
            *[
                f"| {row.case} | {int(row.predicted_event)} | {int(row.truth_event)} | {row.mean_service_loss:.4g} | {row.mean_nervousness_area:.4g} | {row.mean_risk_creation_area:.4g} |"
                for row in confusion_summary.itertuples()
            ],
            "",
        ])
    lines.extend([
        "## 5. Canonical engine reinjection",
        "",
        f"- Mode: `{canonical.get('mode')}`",
        f"- Graph: `{canonical.get('graph_path')}`",
        f"- Status: `{canonical.get('status')}`",
        "- The stage-1 integration translates bounded playbooks into explicit scenario/graph overlays and can replay them in the full multi-item MRP engine with paired seeds.",
        "- A duration-weighted overlay is used for the adaptive schedule because the current canonical engine does not yet expose a daily external-control port.",
        "",
    ])
    if canonical_summary is not None and not canonical_summary.empty:
        lines.extend([
            "| Policy | Paired seeds | Service-loss delta | Backlog-area delta | Nervousness delta |",
            "|---|---:|---:|---:|---:|",
            *[
                f"| {row.policy} | {int(row.paired_seed_count)} | {row.mean_delta_service_loss:.4g} | {row.mean_delta_backlog_area_days:.4g} | {row.mean_delta_order_nervousness:.4g} |"
                for row in canonical_summary.itertuples()
            ],
            "",
        ])
    lines.extend([
        "## 6. Risk Creation Index business validation",
        "",
        f"- Status: `{rci_status.get('status')}`",
        f"- Completed review rows: {rci_status.get('completed_rows', 0)}",
        "- The generated CSV is a structured review pack for procurement and planning. Until those fields are completed, the RCI is a simulation-supported research hypothesis, not a certified operational KPI.",
        "",
        "## Main limitations",
        "",
        "- Regime labels are calibrated with pseudo-anchors derived from operational trajectories; industrial labels remain necessary.",
        "- Prediction-to-physics coefficients are explicit but not yet estimated from incident histories.",
        "- The reduced-order controller is a playbook selector, not yet a constrained MPC.",
        "- Canonical adaptive replay is a stage-1 overlay, not a day-by-day closed-loop write-back.",
        "- Business validation of RCI must be completed by procurement and planning experts.",
    ])
    (output_dir / "end_2026_validation_report.md").write_text("\n".join(lines), encoding="utf-8")
