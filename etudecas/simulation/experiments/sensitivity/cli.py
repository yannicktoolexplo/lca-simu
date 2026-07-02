"""CLI for generic sensitivity study preparation and result ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .designs import build_scenario_designs, write_scenario_design_csv
from .discovery import consolidate_case_csvs, discover_case_csvs
from .materialize import materialize_cases
from .results import ingest_case_csvs, registry_rows, summarize_metrics, write_csv, write_json
from .schema import StudySpec, example_study_dict


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


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


def main() -> int:
    args = parse_args()
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


if __name__ == "__main__":
    raise SystemExit(main())
