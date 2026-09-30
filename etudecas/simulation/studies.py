"""Unified entry point for sensitivity, targeted replay and propagation studies.

Each mode retains its scientific method and execution defaults. Sensitivity
materialization and targeted replay planning do not implicitly run simulations.
"""
from __future__ import annotations

import argparse
from importlib import import_module
import json
from pathlib import Path
from etudecas.simulation.experiments.sensitivity.designs import StudySpec, example_study_dict, build_scenario_designs, write_scenario_design_csv
from etudecas.simulation.experiments.sensitivity.materialize import materialize_cases
from etudecas.simulation.experiments.sensitivity.results import consolidate_case_csvs, discover_case_csvs, ingest_case_csvs, registry_rows, summarize_metrics, write_csv, write_json
from etudecas.simulation.experiments.targeted_replay.sources import discover_replay_catalog
from etudecas.simulation.experiments.targeted_replay.ranking import DEFAULT_KPI_SPECS, KpiSpec, rank_scenarios
from etudecas.simulation.experiments.targeted_replay.runner import TargetedReplayRunner
import concurrent.futures
import csv
import sys
from typing import Any
from etudecas.simulation.analysis_batch_common import load_json, write_json as write_paired_json
from etudecas.simulation.uncertainty.paired_propagation import (
    build_paired_propagation_payload,
    build_paired_run_specs,
    default_business_factor_ranges,
    is_economic_factor,
    select_background_rows,
    select_paired_factors,
    select_supplier_item_factors,
)
from etudecas.simulation.uncertainty.temporal_propagation import (
    build_temporal_propagation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def execute_run_spec(*args: Any, **kwargs: Any) -> Any:
    """Load the Monte Carlo executor only when a paired job actually starts."""
    from etudecas.simulation.montecarlo.run_montecarlo_analysis import execute_run_spec as execute
    return execute(*args, **kwargs)

def parse_sensitivity_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage generic etudecas sensitivity studies.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-example", help="Write an example study JSON.")
    init_parser.add_argument(
        "--output",
        default="etudecas/config/sensitivity/supplier_lead_capacity_example.json",
        help="Output study JSON path.",
    )

    design_parser = subparsers.add_parser("design", help="Generate scenario_design.csv from a study JSON.")
    design_parser.add_argument("--study", required=True, help="Study JSON path.")
    design_parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/experiments/result/sensitivity_study",
        help="Output directory.",
    )

    materialize_parser = subparsers.add_parser(
        "materialize",
        help="Write input_case.json files and a run_commands.ps1 queue without executing simulations.",
    )
    materialize_parser.add_argument("--study", required=True, help="Study JSON path.")
    materialize_parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/experiments/result/sensitivity_study",
        help="Output directory.",
    )

    ingest_parser = subparsers.add_parser("ingest", help="Normalize existing case-level CSV results.")
    ingest_parser.add_argument("--study", required=True, help="Study JSON path.")
    ingest_parser.add_argument(
        "--case-csv",
        action="append",
        required=True,
        help="Existing case-level CSV. Can be repeated.",
    )
    ingest_parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/experiments/result/sensitivity_study",
        help="Output directory.",
    )

    discover_parser = subparsers.add_parser(
        "discover",
        help="List historical case-level CSV files without scanning heavy case outputs.",
    )
    discover_parser.add_argument(
        "--root",
        default="etudecas/simulation/sensibility",
        help="Root directory to scan.",
    )

    consolidate_parser = subparsers.add_parser(
        "consolidate",
        help="Discover and normalize all historical case-level CSV files under a root.",
    )
    consolidate_parser.add_argument(
        "--root",
        default="etudecas/simulation/sensibility",
        help="Root directory to scan.",
    )
    consolidate_parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/experiments/result/sensitivity_consolidated",
        help="Output directory.",
    )
    return parser.parse_args(argv)


def cmd_init_example(args: argparse.Namespace) -> int:
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(example_study_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Example sensitivity study JSON: {path.resolve()}")
    return 0


def cmd_design(args: argparse.Namespace) -> int:
    study = StudySpec.from_path(args.study)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    study.write_manifest(output_dir / "study_manifest.json")
    designs = build_scenario_designs(study)
    write_scenario_design_csv(output_dir / "scenario_design.csv", designs)
    print(f"[OK] Study manifest: {(output_dir / 'study_manifest.json').resolve()}")
    print(f"[OK] Scenario design: {(output_dir / 'scenario_design.csv').resolve()} ({len(designs)} scenarios)")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    study = StudySpec.from_path(args.study)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = ingest_case_csvs([Path(path) for path in args.case_csv], study_id=study.study_id)
    summary = summarize_metrics(rows)
    study.write_manifest(output_dir / "study_manifest.json")
    write_csv(output_dir / "metrics.csv", rows)
    write_csv(output_dir / "registry.csv", registry_rows(rows))
    write_json(output_dir / "summary.json", summary)
    print(f"[OK] Metrics: {(output_dir / 'metrics.csv').resolve()} ({len(rows)} rows)")
    print(f"[OK] Registry: {(output_dir / 'registry.csv').resolve()}")
    print(f"[OK] Summary: {(output_dir / 'summary.json').resolve()}")
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    paths = discover_case_csvs(args.root)
    for path in paths:
        print(path)
    print(f"[OK] Discovered {len(paths)} case-level CSV files under {Path(args.root).resolve()}")
    return 0


def cmd_consolidate(args: argparse.Namespace) -> int:
    result = consolidate_case_csvs(args.root, args.output_dir)
    output_dir = Path(result["output_dir"])
    print(f"[OK] Source files: {(output_dir / 'source_files.csv').resolve()} ({len(result['paths'])} files)")
    print(f"[OK] Metrics: {(output_dir / 'metrics.csv').resolve()} ({len(result['metrics_rows'])} rows)")
    print(f"[OK] Registry: {(output_dir / 'registry.csv').resolve()}")
    print(f"[OK] Summary: {(output_dir / 'summary.json').resolve()}")
    return 0


def cmd_materialize(args: argparse.Namespace) -> int:
    study = StudySpec.from_path(args.study)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    study.write_manifest(output_dir / "study_manifest.json")
    designs = build_scenario_designs(study)
    write_scenario_design_csv(output_dir / "scenario_design.csv", designs)
    rows = materialize_cases(study, output_dir)
    print(f"[OK] Materialized cases: {(output_dir / 'materialized_cases.csv').resolve()} ({len(rows)} cases)")
    print(f"[OK] Run queue: {(output_dir / 'run_commands.ps1').resolve()}")
    return 0


def sensitivity_main(argv: list[str] | None = None) -> int:
    args = parse_sensitivity_args(argv)
    if args.command == "init-example":
        return cmd_init_example(args)
    if args.command == "design":
        return cmd_design(args)
    if args.command == "materialize":
        return cmd_materialize(args)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "discover":
        return cmd_discover(args)
    if args.command == "consolidate":
        return cmd_consolidate(args)
    raise ValueError(f"Unsupported command: {args.command}")


def parse_targeted_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rank companion scenarios by KPI influence, then replay the nominal and top-K "
            "scenarios with lot trace explicitly enabled."
        )
    )
    parser.add_argument(
        "--source-run",
        required=True,
        help="Pipeline output containing run_manifest.json and companion_runs.",
    )
    parser.add_argument("--output-dir", required=True, help="New targeted replay suite directory.")
    parser.add_argument("--top-k", type=int, default=3, help="Number of influential scenarios to replay.")
    parser.add_argument(
        "--kpi",
        action="append",
        default=[],
        metavar="NAME[:DIRECTION[:WEIGHT]]",
        help=(
            "Ranking KPI. DIRECTION is lower, higher, or absolute. Repeat for multiple KPIs. "
            "Defaults to availability, replanning rate, backlog, and total cost."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Optional horizon override. Zero preserves each recorded scenario horizon.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute simulations. Without this flag, only selection and comparison plans are written.",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help=(
            "Revalidate replay folders already present under OUTPUT_DIR and rebuild metrics, "
            "lot deltas, and the comparison manifest without rerunning simulations."
        ),
    )
    return parser.parse_args(argv)


def targeted_main(argv: list[str] | None = None) -> int:
    args = parse_targeted_args(argv)
    specs = [KpiSpec.parse(value) for value in args.kpi] if args.kpi else list(DEFAULT_KPI_SPECS)
    catalog = discover_replay_catalog(args.source_run)
    ranking = rank_scenarios(catalog.baseline, catalog.candidates, specs)
    runner = TargetedReplayRunner(
        catalog=catalog,
        ranking=ranking,
        specs=specs,
        output_dir=Path(args.output_dir),
        top_k=args.top_k,
        days=args.days or None,
    )
    if args.execute and args.reuse_existing:
        raise SystemExit("--execute and --reuse-existing are mutually exclusive")
    result = runner.run(
        execute=bool(args.execute),
        reuse_existing=bool(args.reuse_existing),
    )
    print(f"[OK] Selection manifest: {(Path(args.output_dir) / 'selection_manifest.json').resolve()}")
    print(f"[OK] Comparison manifest: {(Path(args.output_dir) / 'comparison_manifest.json').resolve()}")
    print(f"[OK] Execution status: {result['execution_status']}")
    return 0 if result["execution_status"] in {"planned", "completed"} else 1


def parse_paired_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired +/- uncertainty experiments from an existing Monte Carlo result.")
    parser.add_argument("--summary-json", required=True, help="Existing montecarlo_summary.json.")
    parser.add_argument("--factor-count", type=int, default=8)
    parser.add_argument("--background-count", type=int, default=20)
    parser.add_argument("--input-uncertainty", type=float, default=0.20)
    parser.add_argument("--workers", type=int, default=0, help="0 reuses the worker count recorded in the MC summary.")
    parser.add_argument("--trajectory-max-points", type=int, default=730)
    parser.add_argument(
        "--lot-events-csv",
        help="Optional nominal production_lot_events.csv used to identify lots exposed in time.",
    )
    return parser.parse_args(argv)


def resolve_repo_path(value: Any) -> Path:
    candidate = Path(str(value or ""))
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def paired_main(argv: list[str] | None = None) -> None:
    args = parse_paired_args(argv)
    summary_path = resolve_repo_path(args.summary_json)
    summary = load_json(summary_path)
    samples_path = summary_path.with_name("montecarlo_samples.csv")
    if not samples_path.exists():
        raise FileNotFoundError(f"Monte Carlo samples not found: {samples_path}")
    rows = read_rows(samples_path)
    base_data = load_json(resolve_repo_path(summary.get("input")))
    factor_count = max(0, int(args.factor_count))
    pair_target = max(0, factor_count - min(2, factor_count // 4))
    factors = select_supplier_item_factors(
        base_data,
        summary,
        rows,
        limit=pair_target,
    )
    ranked_fallback = select_paired_factors(
        summary,
        rows,
        limit=max(factor_count * 2, factor_count),
    )
    for factor in [
        *[value for value in ranked_fallback if is_economic_factor(value)],
        *ranked_fallback,
    ]:
        if len(factors) >= factor_count:
            break
        if factor not in factors:
            factors.append(factor)
    backgrounds = select_background_rows(rows, count=max(0, int(args.background_count)))
    specs = build_paired_run_specs(
        factors=factors,
        backgrounds=backgrounds,
        uncertainty=max(0.0, float(args.input_uncertainty)),
        factor_ranges=default_business_factor_ranges(factors),
        range_rows=rows,
        reuse_background_centers=True,
    )
    if not specs:
        raise RuntimeError("No paired run specification could be built from the selected Monte Carlo campaign.")

    run_script = resolve_repo_path(summary.get("run_script") or "etudecas/simulation/engine/run_first_simulation.py")
    scenario_id = str(summary.get("scenario_id") or "scn:BASE")
    days = int(summary.get("days_override") or 0)
    simulator_extra_args = [str(token) for token in (summary.get("simulator_extra_args") or [])]
    worker_count = max(1, min(int(args.workers or summary.get("workers") or 1), len(specs)))
    print(
        f"[PAIRED] factors={len(factors)} backgrounds={len(backgrounds)} "
        f"runs={len(specs)} workers={worker_count}",
        flush=True,
    )

    results: dict[int, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_spec = {
            executor.submit(
                execute_run_spec,
                spec,
                base_data=base_data,
                scenario_id=scenario_id,
                run_script=run_script,
                days=days,
                simulator_extra_args=simulator_extra_args,
                keep_run_artifacts=False,
                runs_dir=summary_path.parent / "paired_runs",
                save_trajectories=True,
                trajectory_max_points=max(0, int(args.trajectory_max_points)),
            ): spec
            for spec in specs
        }
        for completed, future in enumerate(concurrent.futures.as_completed(future_to_spec), start=1):
            spec = future_to_spec[future]
            try:
                result = future.result()
            except Exception as exc:
                failed_row = dict(spec["row"])
                failed_row["status"] = "failed"
                failed_row["error"] = str(exc)
                result = {"index": int(spec["index"]), "row": failed_row, "trajectory_run": None}
            results[int(spec["index"])] = result
            print(
                f"[PAIRED DONE] {completed:03d}/{len(specs):03d} "
                f"{spec['run_id']} status={result['row'].get('status', 'unknown')}",
                flush=True,
            )

    trajectories: list[dict[str, Any]] = []
    failed = 0
    for spec in specs:
        result = results.get(int(spec["index"]))
        if not result or result["row"].get("status") != "ok" or not result.get("trajectory_run"):
            failed += 1
            continue
        trajectory = result["trajectory_run"]
        trajectory["paired_metadata"] = dict(spec.get("paired_metadata") or {})
        trajectories.append(trajectory)

    payload = build_paired_propagation_payload(
        factors=factors,
        backgrounds=backgrounds,
        trajectory_runs=trajectories,
        scenario_id=scenario_id,
        uncertainty=max(0.0, float(args.input_uncertainty)),
    )
    payload["failed_runs"] = failed
    output_path = summary_path.with_name("montecarlo_paired_propagation.json")
    write_paired_json(output_path, payload)
    lot_events_path = (
        resolve_repo_path(args.lot_events_csv)
        if args.lot_events_csv
        else summary_path.parent.parent.parent / "data" / "production_lot_events.csv"
    )
    temporal_payload = build_temporal_propagation(
        payload,
        base_data,
        lot_events_csv=lot_events_path if lot_events_path.exists() else None,
    )
    temporal_path = summary_path.with_name(
        "montecarlo_temporal_propagation.json"
    )
    write_paired_json(temporal_path, temporal_payload)
    summary["paired_propagation"] = {
        "enabled": True,
        "path": str(output_path),
        "schema_version": payload.get("schema_version"),
        "method": payload.get("method"),
        "input_relative_uncertainty": payload.get("input_relative_uncertainty"),
        "factor_count": payload.get("factor_count"),
        "background_count": payload.get("background_count"),
        "runs_expected": len(specs),
        "runs_successful": payload.get("run_count"),
        "runs_failed": failed,
        "factors": factors,
        "temporal_propagation_path": str(temporal_path),
        "lot_events_path": str(lot_events_path) if lot_events_path.exists() else "",
    }
    write_paired_json(summary_path, summary)
    print(f"[OK] Paired propagation: {output_path.resolve()}", flush=True)


def parse_temporal_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paired-json", required=True)
    parser.add_argument("--graph-json", required=True)
    parser.add_argument("--lot-events-csv")
    parser.add_argument("--output-json", required=True)
    return parser.parse_args(argv)


def temporal_main(argv: list[str] | None = None) -> None:
    args = parse_temporal_args(argv)
    paired = json.loads(Path(args.paired_json).read_text(encoding="utf-8"))
    graph = json.loads(Path(args.graph_json).read_text(encoding="utf-8"))
    payload = build_temporal_propagation(
        paired,
        graph,
        lot_events_csv=args.lot_events_csv,
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] Temporal propagation: {output.resolve()}")



def main(argv: list[str] | None = None) -> int | None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == 'shared-components':
        from etudecas.simulation.experiments.shared_components import main as shared_main
        return shared_main(arguments[1:])
    modes = {
        "sensitivity": sensitivity_main,
        "targeted": targeted_main,
        "paired": paired_main,
        "temporal": temporal_main,
    }
    # One current entry per research capability. Imports are deferred so an
    # ordinary sensitivity plan does not load the supplier campaign machinery.
    research_modes = {
        "cascade": "canonical_cascade_campaign",
        "supplier-configurations": "supplier_service_landscape_campaign",
        "supplier-calibration": "supplier_service_regime_calibration_runner",
        "supplier-campaign": "supplier_operating_point_full_campaign_v8",
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=(*modes, *research_modes, 'shared-components'))
    # Each existing parser owns its arguments, defaults and refusal behavior.
    if not arguments or arguments[0] not in (*modes, *research_modes):
        parser.parse_args(arguments)
    if arguments[0] in research_modes:
        module = import_module(
            "etudecas.prototypes.scan_2027_risk_control." + research_modes[arguments[0]]
        )
        return module.main(arguments[1:])
    return modes[arguments[0]](arguments[1:])


if __name__ == "__main__":
    raise SystemExit(main())
