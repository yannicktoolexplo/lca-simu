#!/usr/bin/env python3
"""Run a dedicated annual scenario with doubled factory capacities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis_batch_common import apply_scales, load_json, run_simulation, write_json
from result_paths import ensure_standard_dirs, map_path, report_path, summary_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a scenario with doubled factory capacities.")
    parser.add_argument(
        "--input",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/result/capacity_x2_annual",
        help="Directory where scenario outputs are written.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id to simulate.")
    parser.add_argument("--days", type=int, default=365, help="Simulation horizon in days.")
    parser.add_argument(
        "--factor",
        type=float,
        default=2.0,
        help="Capacity multiplier applied to the selected factories.",
    )
    parser.add_argument(
        "--nodes",
        nargs="+",
        default=["M-1430", "M-1810"],
        help="Production nodes whose capacities must be scaled.",
    )
    parser.add_argument("--skip-map", action="store_true", help="Skip map regeneration.")
    parser.add_argument("--skip-plots", action="store_true", help="Skip plot regeneration.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    ensure_standard_dirs(output_dir)

    base_data = load_json(input_path)
    capacity_node_scale = {str(node): float(args.factor) for node in args.nodes}
    scenario_data = apply_scales(
        base_data,
        args.scenario_id,
        factors={},
        capacity_node_scale=capacity_node_scale,
    )

    scenario_input_path = output_dir / "input_capacity_x2.json"
    write_json(scenario_input_path, scenario_data)

    sim_cmd = [
        "python",
        "etudecas/simulation/run_first_simulation.py",
        "--input",
        str(scenario_input_path),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        str(args.scenario_id),
        "--days",
        str(args.days),
        "--map-output",
        str(map_path(output_dir, "supply_graph_poc_geocoded_map_with_factory_hover.html")),
    ]
    if args.skip_map:
        sim_cmd.append("--skip-map")
    if args.skip_plots:
        sim_cmd.append("--skip-plots")

    import subprocess

    proc = subprocess.run(sim_cmd, check=True, capture_output=True, text=True)
    summary = load_json(summary_path(output_dir, "first_simulation_summary.json"))

    scenario_report = {
        "scenario": "capacity_x2_factories",
        "input": str(input_path),
        "scenario_input": str(scenario_input_path),
        "scenario_id": args.scenario_id,
        "days": args.days,
        "capacity_factor": args.factor,
        "target_nodes": list(args.nodes),
        "kpis": summary.get("kpis", {}),
        "summary_file": str(summary_path(output_dir, "first_simulation_summary.json")),
        "map_file": str(map_path(output_dir, "supply_graph_poc_geocoded_map_with_factory_hover.html")),
    }
    write_json(summary_path(output_dir, "capacity_x2_scenario_summary.json"), scenario_report)

    report_lines = [
        "# Capacity x2 Scenario",
        "",
        f"- Input: `{input_path}`",
        f"- Scenario id: `{args.scenario_id}`",
        f"- Horizon: `{args.days}` days",
        f"- Capacity factor: `{args.factor}`",
        f"- Target nodes: `{', '.join(args.nodes)}`",
        "",
        "## KPI",
        f"- Fill rate: `{summary['kpis'].get('fill_rate')}`",
        f"- Ending backlog: `{summary['kpis'].get('ending_backlog')}`",
        f"- Total cost: `{summary['kpis'].get('total_cost')}`",
        f"- Total served: `{summary['kpis'].get('total_served')}`",
        f"- Total demand: `{summary['kpis'].get('total_demand')}`",
        "",
        "## Files",
        f"- Scenario input: `{scenario_input_path}`",
        f"- Simulation summary: `{summary_path(output_dir, 'first_simulation_summary.json')}`",
    ]
    if not args.skip_map:
        report_lines.append(
            f"- Map: `{map_path(output_dir, 'supply_graph_poc_geocoded_map_with_factory_hover.html')}`"
        )
    report_path(output_dir, "capacity_x2_scenario_report.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(scenario_report, indent=2, ensure_ascii=False))
    if proc.stdout.strip():
        print(proc.stdout.strip())


if __name__ == "__main__":
    main()
