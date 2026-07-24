#!/usr/bin/env python3
"""Run the six RESILIENCE-SCAN validation work packages targeted for end 2026."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.calibration import calibrate_from_context
from etudecas.prototypes.scan_2027_risk_control.canonical_replay import (
    discover_canonical_graph,
    prepare_canonical_overlay_package,
    run_canonical_replays,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    DEFAULT_ACTIONS,
    build_input_context,
    load_config,
    safety_filter,
)
from etudecas.prototypes.scan_2027_risk_control.decision import (
    adaptive_summary,
    regime_transition_matrix,
    run_adaptive_controller,
    simulate_fixed_policy_scenarios,
)
from etudecas.prototypes.scan_2027_risk_control.end_2026_reporting import (
    save_end_2026_plots,
    write_end_2026_report,
)
from etudecas.prototypes.scan_2027_risk_control.experiments import (
    forecast_confusion_experiment,
    paired_policy_experiment,
)
from etudecas.prototypes.scan_2027_risk_control.model import (
    derive_adaptive_state_space,
    derive_constraint_activity,
    estimate_supplier_impedance,
)
from etudecas.prototypes.scan_2027_risk_control.rci_validation import (
    build_rci_business_validation_pack,
    summarize_completed_business_review,
    write_business_validation_guide,
)
from etudecas.prototypes.scan_2027_risk_control.reporting import save_plots, write_json, write_report
from etudecas.prototypes.scan_2027_risk_control.risk_mapping import (
    build_canonical_risk_events,
    build_prediction_interval_envelope,
    map_prediction_interval_to_physical,
)


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Run regime calibration, prediction-to-physics mapping, paired comparisons, forecast-error tests and RCI review pack."
    )
    parser.add_argument("--repo-root", default=str(here.parents[3]))
    parser.add_argument("--baseline-csv", default="auto")
    parser.add_argument("--risk-csv", default="auto")
    parser.add_argument("--config", default=str(here / "config" / "default_config.json"))
    parser.add_argument("--output-dir", default=str(here / "outputs" / "end_2026_validation"))
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--seed", type=int, default=20260)
    parser.add_argument("--paired-seed-count", type=int, default=12)
    parser.add_argument("--confusion-seed-count", type=int, default=6)
    parser.add_argument("--confusion-duration-days", type=int, default=42)
    parser.add_argument("--controller-scenarios", type=int, default=12)
    parser.add_argument("--policy-comparison-scenarios", type=int, default=24)
    parser.add_argument("--controller-horizon-days", type=int, default=21)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--canonical-replay", choices=["off", "overlay", "run"], default="overlay")
    parser.add_argument("--canonical-graph", default="auto")
    parser.add_argument("--canonical-days", type=int, default=365)
    parser.add_argument("--canonical-seed-count", type=int, default=3)
    parser.add_argument("--canonical-top-risk-pairs", type=int, default=3)
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--business-review-csv", default="")
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args()


def _jsonable_record(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records")) if not frame.empty else []


def _refresh_prediction_mapping(context: Any, config: dict[str, Any], days: int) -> Any:
    prediction_path = Path(context.risk_path) if context.risk_path else None
    interval, metadata = build_prediction_interval_envelope(
        prediction_path,
        days,
        fallback_center=context.input_series["base_risk"].to_numpy(dtype=float),
        fallback_uncertainty=context.input_series["risk_uncertainty"].to_numpy(dtype=float),
        mapping_config=config.get("physical_risk_mapping", {}),
    )
    physical = map_prediction_interval_to_physical(interval, config.get("physical_risk_mapping", {}))
    input_series = context.input_series.head(days).copy().reset_index(drop=True)
    input_series["base_risk"] = interval["risk_center"].to_numpy(dtype=float)
    input_series["risk_uncertainty"] = (
        interval["risk_upper"].to_numpy(dtype=float) - interval["risk_lower"].to_numpy(dtype=float)
    ) / 2.0
    return replace(
        context,
        input_series=input_series,
        prediction_interval=interval,
        physical_risk_envelope=physical,
        prediction_interval_metadata=metadata.__dict__,
    )


def _write_frames(data_dir: Path, frames: dict[str, pd.DataFrame]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(data_dir / name, index=False)


def main() -> None:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    config_dir = output_dir / "config"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(args.config).resolve()
    base_config = load_config(config_path if config_path.exists() else None)
    # The end-2026 runner uses a tractable validation profile by default; the
    # original higher-fidelity counts remain available through CLI overrides.
    base_config["controller_scenarios"] = max(2, int(args.controller_scenarios))
    base_config["policy_comparison_scenarios"] = max(4, int(args.policy_comparison_scenarios))
    base_config["controller_horizon_days"] = max(7, int(args.controller_horizon_days))
    context = build_input_context(
        repo_root,
        args.baseline_csv,
        args.risk_csv,
        max(56, int(args.days)),
        int(args.seed),
        bool(args.synthetic),
        mapping_config=base_config.get("physical_risk_mapping", {}),
    )
    context = _refresh_prediction_mapping(context, base_config, len(context.input_series))

    # 1. Calibrate state-dependent regimes and nominal reduced-order scales.
    calibration = calibrate_from_context(context, base_config)
    config = calibration.config
    actions = tuple(safety_filter(action, config) for action in DEFAULT_ACTIONS)
    write_json(config_dir / "calibrated_config.json", config)

    # 2. Run the calibrated adaptive layer and standard policy comparison.
    adaptive, decisions, candidates = run_adaptive_controller(context, config, actions, int(args.seed))
    policy_comparison, fixed_trajectories = simulate_fixed_policy_scenarios(
        context, config, actions, int(args.seed)
    )
    transitions = regime_transition_matrix(adaptive)
    constraints = derive_constraint_activity(adaptive, config)
    adaptive_space = derive_adaptive_state_space(adaptive)
    impedance, impedance_summary = estimate_supplier_impedance(adaptive)

    # 3. Paired policy experiment with common random numbers.
    paired_seeds = list(range(int(args.seed), int(args.seed) + max(1, int(args.paired_seed_count))))
    paired_runs, paired_summary = paired_policy_experiment(context, config, actions, paired_seeds)

    # 4. Explicit false-positive / false-negative experiments.
    confusion_seeds = list(range(
        int(args.seed) + 50_000,
        int(args.seed) + 50_000 + max(1, int(args.confusion_seed_count)),
    ))
    confusion_runs, confusion_summary, confusion_regret = forecast_confusion_experiment(
        context,
        config,
        actions,
        confusion_seeds,
        duration_days=min(int(args.confusion_duration_days), max(7, len(context.input_series) // 2)),
    )

    # 5. RCI business review pack. Human validation is explicitly pending unless
    # a completed review file is provided.
    rci_review = build_rci_business_validation_pack(adaptive, decisions, candidates, config)
    rci_review.to_csv(data_dir / "rci_business_review_template.csv", index=False)
    blind_columns = [column for column in rci_review.columns if not column.startswith("model_rci")]
    rci_review[blind_columns].to_csv(data_dir / "rci_business_review_blind.csv", index=False)
    write_business_validation_guide(output_dir / "rci_business_validation_guide.md")
    if args.business_review_csv:
        completed_path = Path(args.business_review_csv).resolve()
        completed_review = pd.read_csv(completed_path) if completed_path.exists() else pd.DataFrame()
    else:
        completed_review = pd.DataFrame()
    rci_status = summarize_completed_business_review(completed_review)
    write_json(output_dir / "rci_business_validation_status.json", rci_status)

    # 6. Canonical engine stage-1 reinjection.
    canonical_runs = pd.DataFrame()
    canonical_summary = pd.DataFrame()
    canonical_overlays = pd.DataFrame()
    graph_path = discover_canonical_graph(repo_root, args.canonical_graph)
    canonical_metadata: dict[str, Any] = {
        "mode": args.canonical_replay,
        "graph_path": str(graph_path) if graph_path else None,
        "status": "disabled" if args.canonical_replay == "off" else "graph_not_found",
    }
    canonical_root = output_dir / "canonical_replay"
    if args.canonical_replay != "off" and graph_path is not None:
        _, canonical_overlays = prepare_canonical_overlay_package(
            graph_path=graph_path,
            decisions=decisions,
            actions=actions,
            output_root=canonical_root,
            days=min(int(args.canonical_days), len(context.input_series)),
            scenario_id=args.scenario_id,
        )
        canonical_risk_events, canonical_risk_ledger = build_canonical_risk_events(
            Path(context.risk_path) if context.risk_path else None,
            context.physical_risk_envelope,
            days=min(int(args.canonical_days), len(context.input_series)),
            top_pairs=int(args.canonical_top_risk_pairs),
            prediction_horizon_days=30,
            conservative=True,
        )
        canonical_risk_events.to_csv(canonical_root / "canonical_supplier_risk_events.csv", index=False)
        canonical_risk_ledger.to_csv(canonical_root / "canonical_risk_mapping_ledger.csv", index=False)
        canonical_metadata.update({
            "status": "overlays_prepared",
            "risk_event_count": int(len(canonical_risk_events)),
            "risk_pairs": int(canonical_risk_ledger[["supplier_id", "item_id", "dst_node_id"]].drop_duplicates().shape[0])
            if not canonical_risk_ledger.empty else 0,
        })
        if args.canonical_replay == "run":
            canonical_seeds = list(range(
                int(args.seed) + 90_000,
                int(args.seed) + 90_000 + max(1, int(args.canonical_seed_count)),
            ))
            canonical_runs, canonical_summary, canonical_overlays = run_canonical_replays(
                repo_root=repo_root,
                graph_path=graph_path,
                decisions=decisions,
                actions=actions,
                seeds=canonical_seeds,
                output_root=canonical_root,
                days=min(int(args.canonical_days), len(context.input_series)),
                scenario_id=args.scenario_id,
                prediction_path=Path(context.risk_path) if context.risk_path else None,
                physical_risk_envelope=context.physical_risk_envelope,
                risk_top_pairs=int(args.canonical_top_risk_pairs),
                prediction_horizon_days=30,
                enable_state_dependent_risks=True,
            )
            canonical_metadata.update({
                "status": "executed" if not canonical_runs.empty and (canonical_runs["status"] == "ok").any() else "execution_failed",
                "paired_seed_count": int(args.canonical_seed_count),
                "successful_runs": int((canonical_runs["status"] == "ok").sum()) if not canonical_runs.empty else 0,
                "failed_runs": int((canonical_runs["status"] != "ok").sum()) if not canonical_runs.empty else 0,
            })

    _write_frames(data_dir, {
        "input_series.csv": context.input_series,
        "prediction_interval_envelope.csv": context.prediction_interval if context.prediction_interval is not None else pd.DataFrame(),
        "physical_risk_envelope.csv": context.physical_risk_envelope if context.physical_risk_envelope is not None else pd.DataFrame(),
        "regime_calibration_frame.csv": calibration.frame,
        "regime_calibration_evidence.csv": calibration.evidence,
        "adaptive_state_trajectory.csv": adaptive,
        "policy_decisions.csv": decisions,
        "candidate_policy_evaluations.csv": candidates,
        "fixed_policy_comparison.csv": policy_comparison,
        "fixed_policy_trajectories.csv": fixed_trajectories,
        "regime_transition_matrix.csv": transitions.reset_index(names="from_regime"),
        "active_constraints.csv": constraints,
        "adaptive_state_space.csv": adaptive_space,
        "supplier_impedance_spectrum.csv": impedance,
        "paired_policy_runs.csv": paired_runs,
        "paired_policy_summary.csv": paired_summary,
        "forecast_confusion_runs.csv": confusion_runs,
        "forecast_confusion_summary.csv": confusion_summary,
        "forecast_confusion_regret.csv": confusion_regret,
        "canonical_runs.csv": canonical_runs,
        "canonical_paired_summary.csv": canonical_summary,
        "canonical_control_overlays.csv": canonical_overlays,
    })

    prediction_meta = dict(context.prediction_interval_metadata or {})
    manifest: dict[str, Any] = {
        "schema_version": "scan.end_2026.validation.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "mode": context.source_mode,
            "baseline_path": context.baseline_path,
            "risk_path": context.risk_path,
            "days": int(len(context.input_series)),
        },
        "regime_calibration": calibration.metadata,
        "prediction_to_physics": {
            "prediction_path": context.risk_path,
            **prediction_meta,
            "physical_fields": [
                "availability", "capacity", "lead_time", "quality_yield",
                "purchase_cost", "transport_cost",
            ],
        },
        "adaptive": adaptive_summary(adaptive),
        "regime_counts": {str(key): int(value) for key, value in adaptive["regime"].value_counts().items()},
        "policy_selection_counts": {str(key): int(value) for key, value in decisions["selected_policy"].value_counts().items()}
        if not decisions.empty else {},
        "paired_policy_summary": _jsonable_record(paired_summary),
        "forecast_confusion_summary": _jsonable_record(confusion_summary),
        "canonical_replay": canonical_metadata,
        "rci_business_validation": rci_status,
        "supplier_impedance": impedance_summary,
        "work_package_status": {
            "regime_calibration": "implemented_with_trajectory_pseudo_anchors",
            "prediction_intervals_to_physical_disruptions": "implemented_research_mapping",
            "canonical_action_reinjection": canonical_metadata["status"],
            "paired_seed_policy_comparison": "implemented",
            "false_positive_false_negative_study": "implemented",
            "rci_procurement_planning_validation": rci_status.get("status", "pending_business_review"),
        },
        "limitations": [
            "Industrial labels are still required to confirm calibrated regimes.",
            "Prediction-to-physics coefficients are explicit research hypotheses.",
            "Adaptive canonical replay is duration-weighted until a daily control port is added.",
            "RCI business validation remains pending until procurement and planning complete the review CSV.",
        ],
    }
    write_json(output_dir / "run_manifest.json", manifest)
    write_report(
        output_dir, context, adaptive, decisions, policy_comparison,
        constraints, impedance_summary, manifest,
    )
    write_end_2026_report(
        output_dir,
        manifest,
        calibration.evidence,
        paired_summary,
        confusion_summary,
        rci_status,
        canonical_summary,
    )
    if not args.no_plots:
        save_plots(
            output_dir, adaptive, decisions, policy_comparison, fixed_trajectories,
            transitions, constraints, adaptive_space, impedance,
        )
        save_end_2026_plots(
            output_dir,
            calibration.frame,
            calibration.evidence,
            context.prediction_interval if context.prediction_interval is not None else pd.DataFrame(),
            context.physical_risk_envelope if context.physical_risk_envelope is not None else pd.DataFrame(),
            paired_summary,
            confusion_summary,
            confusion_regret,
            rci_review,
            canonical_summary,
        )

    print(f"SCAN end-2026 validation package completed: {output_dir}")
    print(f"Source mode: {context.source_mode}")
    print(f"Calibrated regimes: {calibration.metadata['regime_counts']}")
    print(f"Canonical replay: {canonical_metadata['status']}")
    print(f"RCI business validation: {rci_status.get('status')}")


if __name__ == "__main__":
    main()
