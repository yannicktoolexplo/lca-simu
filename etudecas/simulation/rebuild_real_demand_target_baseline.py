#!/usr/bin/env python3
"""Rebuild the reference baseline against real demand and product service targets."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from analysis_batch_common import apply_scales, load_json, run_simulation, write_json
from result_paths import report_path, summary_path


TARGET_SERVICE_BY_ITEM = {
    "item:268967": 0.80,
    "item:268091": 0.93,
}

FACTORY_CAPACITY_NODE_SCALE = {
    "M-1430": 52.0,
    "M-1810": 119.0,
}

SUPPLIER_CAPACITY_SCALE = 320.0

SCENARIO_SETTINGS = {
    "warmup_days": 260,
    "reset_backlog_after_warmup": True,
    "initialization_policy": {
        "mode": "explicit_state",
        "state_scale": 0.02,
        "factory_input_on_hand_days": 0.0,
        "supplier_output_on_hand_days": 1.0,
        "distribution_center_on_hand_days": 3.0,
        "customer_on_hand_days": 0.0,
        "seed_in_transit": True,
        "in_transit_fill_ratio": 0.0,
        "seed_estimated_source_pipeline": False,
    },
    "economic_policy": {
        "transport_cost_realism_multiplier": 0.2,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild calibrated baseline for real demand targets.")
    parser.add_argument(
        "--source",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_current.json",
        help="Source simulation-ready graph JSON. Re-run prepare_simulation_graph first if this file is already calibrated.",
    )
    parser.add_argument(
        "--output-graph",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_current.json",
        help="Calibrated baseline graph JSON.",
    )
    parser.add_argument(
        "--named-output-graph",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated.json",
        help="Named copy of the calibrated baseline graph JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated",
        help="Simulation output directory for the rebuilt baseline.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id to rebuild.")
    parser.add_argument("--days", type=int, default=365, help="Measured horizon in days.")
    parser.add_argument(
        "--skip-simulation",
        action="store_true",
        help="Only rebuild the graph JSON without running the simulation.",
    )
    return parser.parse_args()


def compute_item_service(output_dir: Path) -> dict[str, dict[str, float]]:
    csv_path = output_dir / "data" / "production_demand_service_daily.csv"
    item_rows: dict[str, dict[str, float]] = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            item_id = str(row.get("item_id") or "")
            stats = item_rows.setdefault(
                item_id,
                {
                    "demand": 0.0,
                    "served": 0.0,
                    "ending_backlog": 0.0,
                },
            )
            stats["demand"] += float(row.get("demand_qty") or 0.0)
            stats["served"] += float(row.get("served_qty") or 0.0)
            stats["ending_backlog"] = float(row.get("backlog_end_qty") or 0.0)
    for item_id, stats in item_rows.items():
        demand = stats["demand"]
        stats["fill_rate"] = (stats["served"] / demand) if demand > 0 else 0.0
        stats["target_fill_rate"] = TARGET_SERVICE_BY_ITEM.get(item_id)
        if stats["target_fill_rate"] is None:
            stats["target_gap"] = None
        else:
            stats["target_gap"] = stats["fill_rate"] - stats["target_fill_rate"]
    return item_rows


def apply_scenario_settings(data: dict, scenario_id: str) -> dict:
    scenario = next((s for s in (data.get("scenarios") or []) if str(s.get("id")) == scenario_id), None)
    if scenario is None:
        raise ValueError(f"Scenario '{scenario_id}' not found in source graph.")
    for key, value in SCENARIO_SETTINGS.items():
        if isinstance(value, dict) and isinstance(scenario.get(key), dict):
            merged = dict(scenario.get(key) or {})
            merged.update(value)
            scenario[key] = merged
        else:
            scenario[key] = value
    return data


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    output_graph_path = Path(args.output_graph)
    named_output_graph_path = Path(args.named_output_graph)
    output_dir = Path(args.output_dir)
    run_script = Path("etudecas/simulation/run_first_simulation.py")

    base_data = load_json(source_path)
    if (base_data.get("meta") or {}).get("baseline_rebuild"):
        raise RuntimeError(
            "Source graph already contains baseline_rebuild metadata. "
            "Re-run prepare_simulation_graph to regenerate a clean real-demand graph before rebuilding."
        )
    calibrated = apply_scales(
        base_data,
        args.scenario_id,
        factors={"supplier_capacity_scale": SUPPLIER_CAPACITY_SCALE},
        capacity_node_scale=FACTORY_CAPACITY_NODE_SCALE,
    )
    calibrated = apply_scenario_settings(calibrated, args.scenario_id)

    meta = calibrated.get("meta") or {}
    meta["baseline_rebuild"] = {
        "type": "real_demand_target_service_rebuild",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_graph": str(source_path),
        "scenario_id": args.scenario_id,
        "days": int(args.days),
        "factory_capacity_node_scale": FACTORY_CAPACITY_NODE_SCALE,
        "supplier_capacity_scale": SUPPLIER_CAPACITY_SCALE,
        "scenario_settings": SCENARIO_SETTINGS,
        "target_service_by_item": TARGET_SERVICE_BY_ITEM,
    }
    calibrated["meta"] = meta

    write_json(output_graph_path, calibrated)
    if named_output_graph_path != output_graph_path:
        write_json(named_output_graph_path, calibrated)

    result_summary: dict[str, object] = {
        "graph_output": str(output_graph_path),
        "named_graph_output": str(named_output_graph_path),
        "scenario_id": args.scenario_id,
        "days": int(args.days),
        "factory_capacity_node_scale": FACTORY_CAPACITY_NODE_SCALE,
        "supplier_capacity_scale": SUPPLIER_CAPACITY_SCALE,
        "scenario_settings": SCENARIO_SETTINGS,
        "target_service_by_item": TARGET_SERVICE_BY_ITEM,
    }

    if not args.skip_simulation:
        summary, _stdout = run_simulation(
            run_script=run_script,
            input_json=output_graph_path,
            output_dir=output_dir,
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=False,
            skip_plots=False,
        )
        item_service = compute_item_service(output_dir)
        result_summary["simulation_summary_file"] = str(summary_path(output_dir, "first_simulation_summary.json"))
        result_summary["simulation_report_file"] = str(report_path(output_dir, "first_simulation_report.md"))
        result_summary["global_kpis"] = summary.get("kpis", {})
        result_summary["item_service"] = item_service

        lines = [
            "# Real-Demand Baseline Rebuild",
            "",
            f"- Source graph: `{source_path}`",
            f"- Scenario id: `{args.scenario_id}`",
            f"- Measured horizon: `{args.days}` days",
            f"- Factory scale M-1430: `{FACTORY_CAPACITY_NODE_SCALE['M-1430']}`",
            f"- Factory scale M-1810: `{FACTORY_CAPACITY_NODE_SCALE['M-1810']}`",
            f"- Supplier capacity scale: `{SUPPLIER_CAPACITY_SCALE}`",
            f"- Warm-up days: `{SCENARIO_SETTINGS['warmup_days']}`",
            f"- Reset backlog after warm-up: `{SCENARIO_SETTINGS['reset_backlog_after_warmup']}`",
            "",
            "## Product Service",
        ]
        for item_id, stats in sorted(item_service.items()):
            target = stats.get("target_fill_rate")
            target_str = "n/a" if target is None else f"{target:.2%}"
            gap = stats.get("target_gap")
            gap_str = "n/a" if gap is None else f"{gap:+.4f}"
            lines.append(
                f"- {item_id}: fill `{stats['fill_rate']:.4f}` vs target `{target_str}` "
                f"(gap `{gap_str}`), demand `{stats['demand']:.1f}`, served `{stats['served']:.1f}`, "
                f"ending backlog `{stats['ending_backlog']:.1f}`"
            )
        lines.extend(
            [
                "",
                "## Global KPI",
                f"- Fill rate global: `{summary['kpis'].get('fill_rate')}`",
                f"- Ending backlog global: `{summary['kpis'].get('ending_backlog')}`",
                f"- Warm-up backlog cleared: `{summary['kpis'].get('warmup_backlog_cleared_qty')}`",
                f"- Total cost: `{summary['kpis'].get('total_cost')}`",
            ]
        )
        report_path(output_dir, "baseline_rebuild_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        write_json(summary_path(output_dir, "baseline_rebuild_summary.json"), result_summary)

    print(json.dumps(result_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
