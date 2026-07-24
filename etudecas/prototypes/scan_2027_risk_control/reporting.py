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


def save_plots(output_dir: Path, adaptive: pd.DataFrame, decisions: pd.DataFrame,
               policy_comparison: pd.DataFrame, fixed_trajectories: pd.DataFrame,
               transitions: pd.DataFrame, constraints: pd.DataFrame,
               adaptive_state_space: pd.DataFrame, impedance: pd.DataFrame) -> None:
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
    fig.tight_layout(); fig.savefig(plot_dir / "adaptive_state_trajectory.png", dpi=160); plt.close(fig)

    regime_codes = {name: i for i, name in enumerate(sorted(adaptive["regime"].unique()))}
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.step(adaptive["day"], adaptive["regime"].map(regime_codes), where="post")
    ax.set_yticks(list(regime_codes.values()), list(regime_codes.keys()))
    ax.set_xlabel("day"); ax.set_title("State-dependent regime timeline")
    fig.tight_layout(); fig.savefig(plot_dir / "regime_timeline.png", dpi=160); plt.close(fig)

    if not decisions.empty:
        fig, ax = plt.subplots(figsize=(12, 4))
        policy_codes = {name: i for i, name in enumerate(sorted(decisions["selected_policy"].unique()))}
        ax.step(decisions["day"], decisions["selected_policy"].map(policy_codes), where="post")
        ax.set_yticks(list(policy_codes.values()), list(policy_codes.keys()))
        ax.set_xlabel("review day"); ax.set_title("Adaptive policy selection")
        fig.tight_layout(); fig.savefig(plot_dir / "adaptive_policy_selection.png", dpi=160); plt.close(fig)

    ordered = policy_comparison.sort_values("robust_score")
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(ordered["policy"], ordered["robust_score"])
    ax.tick_params(axis="x", rotation=25); ax.set_ylabel("robust score (lower is better)")
    ax.set_title("Fixed-policy robust comparison")
    fig.tight_layout(); fig.savefig(plot_dir / "policy_frontier.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(ordered["policy"], ordered["mean_risk_creation"])
    ax.axhline(0.0, linewidth=0.8); ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("mean Risk Creation Index")
    ax.set_title("Risk created by the response relative to MRP")
    fig.tight_layout(); fig.savefig(plot_dir / "risk_creation_index_by_policy.png", dpi=160); plt.close(fig)

    sample = fixed_trajectories.groupby(["policy", "step"])["supplier_risk"].median().reset_index()
    fig, ax = plt.subplots(figsize=(12, 5))
    for policy, group in sample.groupby("policy"):
        ax.plot(group["step"], group["supplier_risk"], label=policy)
    ax.legend(ncol=2); ax.set_xlabel("day"); ax.set_ylabel("supplier risk")
    ax.set_title("Supplier-risk trajectories by policy")
    fig.tight_layout(); fig.savefig(plot_dir / "supplier_risk_endogenous.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    scatter = ax.scatter(adaptive["observability"], adaptive["controllability"], c=adaptive["supplier_risk"])
    ax.set_xlabel("observability"); ax.set_ylabel("controllability")
    ax.set_title("State visibility and available recovery leverage")
    fig.colorbar(scatter, ax=ax, label="supplier risk")
    fig.tight_layout(); fig.savefig(plot_dir / "observability_controllability_map.png", dpi=160); plt.close(fig)

    active_cols = [c for c in constraints.columns if c.endswith("_active")]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(constraints["day"], *[constraints[c] for c in active_cols], labels=active_cols)
    ax.legend(loc="upper right", fontsize=7); ax.set_xlabel("day")
    ax.set_title("Active non-smooth constraints")
    fig.tight_layout(); fig.savefig(plot_dir / "active_constraints.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.step(adaptive_state_space["day"], adaptive_state_space["model_detail_level"], where="post")
    ax.set_yticks([0, 1, 2, 3]); ax.set_xlabel("day"); ax.set_ylabel("detail level")
    ax.set_title("Adaptive state-space detail level")
    fig.tight_layout(); fig.savefig(plot_dir / "adaptive_state_space_level.png", dpi=160); plt.close(fig)

    if not impedance.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(impedance["frequency_cycle_per_day"], impedance["magnitude"])
        ax.set_xlabel("frequency (cycle/day)"); ax.set_ylabel("magnitude")
        ax.set_title("Exploratory supplier-impedance spectrum")
        fig.tight_layout(); fig.savefig(plot_dir / "supplier_impedance_spectrum.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(transitions, aspect="auto")
    ax.set_xticks(range(len(transitions.columns)), transitions.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(transitions.index)), transitions.index)
    ax.set_title("Regime-transition counts")
    fig.colorbar(image, ax=ax)
    fig.tight_layout(); fig.savefig(plot_dir / "regime_transition_matrix.png", dpi=160); plt.close(fig)


def write_report(output_dir: Path, context: Any, adaptive: pd.DataFrame, decisions: pd.DataFrame,
                 policy_comparison: pd.DataFrame, constraints: pd.DataFrame,
                 impedance_summary: Mapping[str, float], summary: Mapping[str, Any]) -> None:
    best = policy_comparison.iloc[0]
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
        "- Stress and risk coefficients are research hypotheses requiring industrial calibration.",
        "- Finite action library; this is not yet a constrained MPC solver.",
        "- Read-only adapter to current etudecas outputs; selected actions are not yet written back into the canonical engine.",
        "",
        "## Next integration step",
        "",
        "Apply the selected action to a canonical etudecas scenario, rerun the full physical MRP engine with paired random seeds, and compare closed-loop service, backlog, inventory, nervousness and supplier-risk trajectories.",
    ]
    (output_dir / "poc_report.md").write_text("\n".join(lines), encoding="utf-8")
