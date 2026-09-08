"""Command-line entrypoint for influential scenario lot-trace replay."""

from __future__ import annotations

import argparse
from pathlib import Path

from .discovery import discover_replay_catalog
from .ranking import rank_scenarios
from .runner import TargetedReplayRunner
from .schema import DEFAULT_KPI_SPECS, KpiSpec


def parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
