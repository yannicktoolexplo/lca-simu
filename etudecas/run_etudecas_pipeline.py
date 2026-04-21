#!/usr/bin/env python3
"""Unified entrypoint for the active etudecas pipeline.

The primary artifact is the supply-chain knowledge-graph JSON. The active flow is:

1. enrich the graph from case-study XLSX data
2. geocode nodes
3. prepare a simulation-ready reference graph
4. calibrate it to the real-demand reference
5. inject MRP snapshot + lot-policy data
6. run the reference simulation and regenerate the map

Secondary analysis and sensitivity scripts remain available, but this file is the
single operational entrypoint for rebuilding the reference graph and its simulations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

BASE_GRAPH_JSON = ROOT / "donnees" / "supply_graph_poc.json"
GEOCODED_GRAPH_JSON = ROOT / "result_geocodage" / "supply_graph_poc_geocoded.json"
PREP_GRAPH_JSON = ROOT / "simulation_prep" / "result" / "reference_baseline" / "supply_graph_reference_baseline_simulation_ready.json"
REAL_DEMAND_GRAPH_JSON = (
    ROOT / "simulation_prep" / "result" / "reference_baseline" / "supply_graph_reference_baseline_real_demand_target_calibrated.json"
)
MRP_LOT_GRAPH_JSON = (
    ROOT / "simulation_prep" / "result" / "reference_baseline" / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json"
)
FINAL_GRAPH_1Y_JSON = (
    ROOT
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json"
)
FINAL_GRAPH_5Y_JSON = (
    ROOT
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json"
)
FINAL_OUTPUT_1Y_DIR = ROOT / "simulation" / "result" / "reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated"
FINAL_OUTPUT_5Y_DIR = ROOT / "simulation" / "result" / "reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y"


def repo_rel(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
        root = REPO_ROOT.resolve(strict=False)
        return str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def run_python(script: Path, *args: str) -> None:
    cmd = [sys.executable, str(script), *args]
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def patch_repeated_horizon_graph(source_graph: Path, output_graph: Path, *, scenario_id: str, days: int) -> None:
    data = load_json(source_graph)
    scenarios = data.get("scenarios") or []
    scenario = next((row for row in scenarios if str(row.get("id")) == scenario_id), None)
    if not isinstance(scenario, dict):
        if not scenarios:
            raise ValueError(f"No scenario found in {source_graph}")
        scenario = scenarios[0]
    horizon = scenario.get("horizon")
    if not isinstance(horizon, dict):
        horizon = {}
    horizon["steps_to_run"] = int(days)
    horizon["repeat_period_days"] = 365
    scenario["horizon"] = horizon

    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["generated_by_pipeline"] = {
        "script": repo_rel(Path(__file__)),
        "source_graph": repo_rel(source_graph),
        "horizon_days": int(days),
        "repeat_period_days": 365,
    }
    data["meta"] = meta
    write_json(output_graph, data)


def forward_optional_flags(*, skip_map: bool, skip_plots: bool) -> list[str]:
    args: list[str] = []
    if skip_map:
        args.append("--skip-map")
    if skip_plots:
        args.append("--skip-plots")
    return args


def build_knowledge_graph() -> None:
    run_python(
        ROOT / "donnees" / "update_supply_graph_from_case_data.py",
        "--input-json",
        repo_rel(BASE_GRAPH_JSON),
        "--output-json",
        repo_rel(BASE_GRAPH_JSON),
    )
    run_python(
        ROOT / "scripts_geocodage" / "geocode_nodes_offline.py",
        "--input-json",
        repo_rel(BASE_GRAPH_JSON),
        "--output-dir",
        "etudecas/result_geocodage",
        "--output-name",
        GEOCODED_GRAPH_JSON.name,
    )


def prepare_reference_graph(*, simulation_days: int) -> None:
    run_python(
        ROOT / "simulation_prep" / "prepare_simulation_graph.py",
        "--input",
        repo_rel(GEOCODED_GRAPH_JSON),
        "--output-graph",
        repo_rel(PREP_GRAPH_JSON),
        "--output-report-json",
        "etudecas/simulation_prep/result/reference_baseline/simulation_prep_report.json",
        "--output-report-md",
        "etudecas/simulation_prep/result/reference_baseline/simulation_prep_report.md",
        "--simulation-days",
        str(simulation_days),
    )


def build_reference_baseline(*, scenario_id: str, days: int, skip_map: bool, skip_plots: bool) -> None:
    run_python(
        ROOT / "simulation" / "baselines" / "rebuild_real_demand_target_baseline.py",
        "--source",
        repo_rel(PREP_GRAPH_JSON),
        "--output-graph",
        repo_rel(REAL_DEMAND_GRAPH_JSON),
        "--named-output-graph",
        repo_rel(REAL_DEMAND_GRAPH_JSON),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        "--skip-simulation",
    )
    run_python(
        ROOT / "simulation_prep" / "inject_mrp_seed_data_v2.py",
        "--input-graph",
        repo_rel(REAL_DEMAND_GRAPH_JSON),
        "--output-graph",
        repo_rel(MRP_LOT_GRAPH_JSON),
        "--output-report-json",
        "etudecas/simulation_prep/result/reference_baseline/mrp_lot_policy_report.json",
        "--output-report-md",
        "etudecas/simulation_prep/result/reference_baseline/mrp_lot_policy_report.md",
        "--include-mrp-lot-policies",
    )
    run_python(
        ROOT / "simulation" / "baselines" / "rebuild_mrp_lot_policy_baseline.py",
        "--source",
        repo_rel(MRP_LOT_GRAPH_JSON),
        "--output-graph",
        repo_rel(FINAL_GRAPH_1Y_JSON),
        "--output-dir",
        repo_rel(FINAL_OUTPUT_1Y_DIR),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *forward_optional_flags(skip_map=skip_map, skip_plots=skip_plots),
    )


def run_5y_reference(*, scenario_id: str, days: int, skip_map: bool, skip_plots: bool) -> None:
    patch_repeated_horizon_graph(FINAL_GRAPH_1Y_JSON, FINAL_GRAPH_5Y_JSON, scenario_id=scenario_id, days=days)
    run_python(
        ROOT / "simulation" / "run_first_simulation.py",
        "--input",
        repo_rel(FINAL_GRAPH_5Y_JSON),
        "--output-dir",
        repo_rel(FINAL_OUTPUT_5Y_DIR),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *forward_optional_flags(skip_map=skip_map, skip_plots=skip_plots),
    )


def run_direct_simulation(*, input_graph: Path, output_dir: Path, scenario_id: str, days: int, skip_map: bool, skip_plots: bool) -> None:
    run_python(
        ROOT / "simulation" / "run_first_simulation.py",
        "--input",
        repo_rel(input_graph),
        "--output-dir",
        repo_rel(output_dir),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *forward_optional_flags(skip_map=skip_map, skip_plots=skip_plots),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified etudecas pipeline around the supply-chain JSON graph.")
    sub = parser.add_subparsers(dest="command", required=True)

    graph = sub.add_parser("graph", help="Rebuild the knowledge-graph JSON from XLSX and geocode it.")

    prepare = sub.add_parser("prepare", help="Prepare the simulation-ready reference graph from the geocoded graph.")
    prepare.add_argument("--simulation-days", type=int, default=365)

    reference = sub.add_parser("reference", help="Rebuild the active 1y reference baseline from the graph pipeline.")
    reference.add_argument("--simulation-days", type=int, default=365, help="Prep horizon written into the working graph.")
    reference.add_argument("--days", type=int, default=365, help="Final 1y measured horizon.")
    reference.add_argument("--scenario-id", default="scn:BASE")
    reference.add_argument("--skip-map", action="store_true")
    reference.add_argument("--skip-plots", action="store_true")

    all_cmd = sub.add_parser("all", help="Run the full active pipeline and optionally the 5y simulation.")
    all_cmd.add_argument("--simulation-days", type=int, default=365, help="Prep horizon written into the working graph.")
    all_cmd.add_argument("--days", type=int, default=365, help="Final 1y measured horizon.")
    all_cmd.add_argument("--scenario-id", default="scn:BASE")
    all_cmd.add_argument("--with-5y", action="store_true", help="Also rebuild and run the repeated 5y variant.")
    all_cmd.add_argument("--days-5y", type=int, default=1825)
    all_cmd.add_argument("--skip-map", action="store_true")
    all_cmd.add_argument("--skip-plots", action="store_true")

    sim = sub.add_parser("simulate", help="Run the simulator directly from a graph JSON.")
    sim.add_argument("--input-graph", required=True)
    sim.add_argument("--output-dir", required=True)
    sim.add_argument("--scenario-id", default="scn:BASE")
    sim.add_argument("--days", type=int, default=365)
    sim.add_argument("--skip-map", action="store_true")
    sim.add_argument("--skip-plots", action="store_true")

    sim5 = sub.add_parser("simulate-5y", help="Patch the active 1y graph to a repeated 5y horizon and run it.")
    sim5.add_argument("--scenario-id", default="scn:BASE")
    sim5.add_argument("--days", type=int, default=1825)
    sim5.add_argument("--skip-map", action="store_true")
    sim5.add_argument("--skip-plots", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "graph":
        build_knowledge_graph()
        return
    if args.command == "prepare":
        prepare_reference_graph(simulation_days=args.simulation_days)
        return
    if args.command == "reference":
        build_knowledge_graph()
        prepare_reference_graph(simulation_days=args.simulation_days)
        build_reference_baseline(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        return
    if args.command == "all":
        build_knowledge_graph()
        prepare_reference_graph(simulation_days=args.simulation_days)
        build_reference_baseline(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        if args.with_5y:
            run_5y_reference(
                scenario_id=args.scenario_id,
                days=args.days_5y,
                skip_map=args.skip_map,
                skip_plots=args.skip_plots,
            )
        return
    if args.command == "simulate":
        run_direct_simulation(
            input_graph=Path(args.input_graph),
            output_dir=Path(args.output_dir),
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        return
    if args.command == "simulate-5y":
        run_5y_reference(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        return
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
