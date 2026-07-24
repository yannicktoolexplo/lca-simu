#!/usr/bin/env python3
"""SCAN 2027 research PoC: state-dependent supplier-risk control.

This prototype consumes current etudecas outputs when available, propagates
supplier-risk uncertainty, diagnoses operating regimes, models endogenous risk
created by order nervousness, and compares bounded response playbooks with a
scenario-based robust selector.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control.core import DEFAULT_ACTIONS, build_input_context, load_config, safety_filter
from etudecas.prototypes.scan_2027_risk_control.decision import (
    adaptive_summary,
    regime_transition_matrix,
    run_adaptive_controller,
    simulate_fixed_policy_scenarios,
)
from etudecas.prototypes.scan_2027_risk_control.model import derive_adaptive_state_space, derive_constraint_activity, estimate_supplier_impedance
from etudecas.prototypes.scan_2027_risk_control.reporting import save_plots, write_json, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SCAN 2027 state-dependent risk-control PoC.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[3]),
                        help="Repository root used to discover etudecas outputs.")
    parser.add_argument("--baseline-csv", default="auto",
                        help="Path to first_simulation_daily.csv, relative to repo root, or 'auto'.")
    parser.add_argument("--risk-csv", default="auto",
                        help="Path to predicted supplier-risk CSV, relative to repo root, or 'auto'.")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "config" / "default_config.json"))
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "outputs" / "latest"))
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--synthetic", action="store_true", help="Force the self-contained synthetic fallback.")
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    config_path = Path(args.config).resolve()
    config = load_config(config_path if config_path.exists() else None)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    context = build_input_context(repo_root, args.baseline_csv, args.risk_csv,
                                  max(28, int(args.days)), int(args.seed), bool(args.synthetic))
    actions = tuple(safety_filter(action, config) for action in DEFAULT_ACTIONS)
    adaptive, decisions, candidates = run_adaptive_controller(context, config, actions, int(args.seed))
    comparison, fixed = simulate_fixed_policy_scenarios(context, config, actions, int(args.seed))
    transitions = regime_transition_matrix(adaptive)
    constraints = derive_constraint_activity(adaptive, config)
    adaptive_space = derive_adaptive_state_space(adaptive)
    impedance, impedance_summary = estimate_supplier_impedance(adaptive)

    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "input_series.csv": context.input_series,
        "adaptive_state_trajectory.csv": adaptive,
        "policy_decisions.csv": decisions,
        "candidate_policy_evaluations.csv": candidates,
        "policy_comparison.csv": comparison,
        "fixed_policy_trajectories.csv": fixed,
        "active_constraints.csv": constraints,
        "adaptive_state_space.csv": adaptive_space,
        "supplier_impedance_spectrum.csv": impedance,
    }.items():
        frame.to_csv(data_dir / name, index=False)
    transitions.to_csv(data_dir / "regime_transition_matrix.csv")

    summary: dict[str, Any] = {
        "schema_version": "scan.2027.state_dependent_risk_control_poc.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "mode": context.source_mode,
            "baseline_path": context.baseline_path,
            "risk_path": context.risk_path,
            "baseline_columns": context.baseline_columns,
        },
        "parameters": {
            "days": len(context.input_series),
            "seed": int(args.seed),
            "review_period_days": int(config["review_period_days"]),
            "controller_horizon_days": int(config["controller_horizon_days"]),
            "controller_scenarios": int(config["controller_scenarios"]),
            "policy_comparison_scenarios": int(config["policy_comparison_scenarios"]),
        },
        "adaptive": adaptive_summary(adaptive),
        "regime_counts": {str(k): int(v) for k, v in adaptive["regime"].value_counts().items()},
        "policy_selection_counts": {str(k): int(v) for k, v in decisions["selected_policy"].value_counts().items()} if not decisions.empty else {},
        "best_fixed_policy": comparison.iloc[0].to_dict(),
        "non_smooth_constraints": {
            "days_with_active_constraint": int((constraints["active_constraint_count"] > 0).sum()),
            "total_activations": {c: int(constraints[c].sum()) for c in constraints if c.endswith("_active")},
        },
        "supplier_impedance": impedance_summary,
        "adaptive_state_space_levels": {str(k): int(v) for k, v in adaptive_space["model_detail_level"].value_counts().sort_index().items()},
        "research_hypotheses": [
            "H1: state-dependent action selection reduces service loss under uncertainty.",
            "H2: aggressive over-ordering can create endogenous supplier risk.",
            "H3: observability and controllability deteriorate in critical regimes.",
            "H4: scenario-based selection can outperform a single static response.",
        ],
        "limitations": [
            "Reduced-order model in equivalent demand-days.",
            "PoC coefficients require industrial calibration.",
            "Finite action library; no constrained MPC yet.",
            "Read-only adapter; no closed-loop write-back to the full engine yet.",
        ],
    }
    write_json(output_dir / "run_manifest.json", summary)
    write_report(output_dir, context, adaptive, decisions, comparison, constraints, impedance_summary, summary)
    if not args.no_plots:
        save_plots(output_dir, adaptive, decisions, comparison, fixed, transitions, constraints, adaptive_space, impedance)

    print(f"SCAN 2027 PoC completed: {output_dir}")
    print(f"Source mode: {context.source_mode}")
    print(f"Adaptive mean service: {summary['adaptive']['mean_service']:.3f}")
    print(f"Adaptive max backlog: {summary['adaptive']['max_backlog']:.3f}")
    print(f"Best fixed policy: {summary['best_fixed_policy']['policy']}")


if __name__ == "__main__":
    main()
