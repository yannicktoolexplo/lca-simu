#!/usr/bin/env python3
"""
Run reproducible Monte Carlo analysis on the supply simulation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import (
    apply_scales,
    detect_demand_items,
    detect_production_nodes,
    load_json,
    numeric_kpis,
    pearson_corr,
    percentile,
    run_simulation,
    safe_name,
    to_float,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Monte Carlo simulation analysis.")
    parser.add_argument(
        "--input",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--run-script",
        default="etudecas/simulation/run_first_simulation.py",
        help="Simulation runner script.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id.")
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/montecarlo/result",
        help="Monte Carlo result directory.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Override simulation horizon in days (default: 30). Set 0 to keep scenario horizon.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=120,
        help="Number of stochastic runs (excluding baseline run_0000).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--keep-run-artifacts",
        action="store_true",
        help="Keep per-run folders with full simulation outputs.",
    )
    return parser.parse_args()


def sample_factor(rng: random.Random, lo: float, mode: float, hi: float) -> float:
    return round(rng.triangular(lo, hi, mode), 6)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    if args.keep_run_artifacts:
        runs_dir.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    demand_items = detect_demand_items(base_data, args.scenario_id)
    production_nodes = detect_production_nodes(base_data)

    rng = random.Random(args.seed)

    # Triangular distributions (lo, mode, hi).
    global_factor_spec: dict[str, tuple[float, float, float]] = {
        "lead_time_scale": (0.8, 1.0, 1.3),
        "transport_cost_scale": (0.8, 1.0, 1.4),
        "supplier_stock_scale": (0.7, 1.0, 1.5),
        "production_stock_scale": (0.8, 1.0, 1.3),
    }
    demand_factor_spec: dict[str, tuple[float, float, float]] = {
        item: (0.7, 1.0, 1.3) for item in demand_items
    }
    capacity_factor_spec: dict[str, tuple[float, float, float]] = {
        node: (0.7, 1.0, 1.3) for node in production_nodes
    }

    total_runs = 1 + max(0, int(args.runs))  # baseline + stochastic
    rows: list[dict[str, Any]] = []

    for i in range(total_runs):
        run_id = f"run_{i:04d}"
        is_baseline = i == 0

        factors = {
            "demand_scale": 1.0,
            "lead_time_scale": 1.0,
            "transport_cost_scale": 1.0,
            "supplier_stock_scale": 1.0,
            "production_stock_scale": 1.0,
            "capacity_scale": 1.0,
        }
        demand_item_scale = {item: 1.0 for item in demand_items}
        capacity_node_scale = {node: 1.0 for node in production_nodes}

        if not is_baseline:
            for k, (lo, mode, hi) in global_factor_spec.items():
                factors[k] = sample_factor(rng, lo, mode, hi)
            for item, (lo, mode, hi) in demand_factor_spec.items():
                demand_item_scale[item] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in capacity_factor_spec.items():
                capacity_node_scale[node] = sample_factor(rng, lo, mode, hi)

        row: dict[str, Any] = {
            "run_id": run_id,
            "is_baseline": is_baseline,
            "status": "ok",
            "error": "",
        }
        row.update({f"factor::{k}": v for k, v in factors.items()})
        row.update({f"demand_item::{k}": v for k, v in demand_item_scale.items()})
        row.update({f"capacity_node::{k}": v for k, v in capacity_node_scale.items()})

        print(f"[RUN] {i+1:03d}/{total_runs:03d} {run_id}")

        try:
            mutated = apply_scales(
                base_data=base_data,
                scenario_id=args.scenario_id,
                factors=factors,
                demand_item_scale=demand_item_scale,
                capacity_node_scale=capacity_node_scale,
            )

            if args.keep_run_artifacts:
                case_dir = runs_dir / run_id
                case_dir.mkdir(parents=True, exist_ok=True)
                case_input = case_dir / "input_case.json"
                case_output = case_dir / "simulation_output"
                write_json(case_input, mutated)
                summary, _ = run_simulation(
                    run_script=run_script,
                    input_json=case_input,
                    output_dir=case_output,
                    scenario_id=args.scenario_id,
                    days=args.days,
                    skip_map=True,
                    skip_plots=True,
                )
                row["case_dir"] = str(case_dir)
            else:
                with tempfile.TemporaryDirectory(prefix=f"mc_{safe_name(run_id)}_") as tmp:
                    case_dir = Path(tmp)
                    case_input = case_dir / "input_case.json"
                    case_output = case_dir / "simulation_output"
                    write_json(case_input, mutated)
                    summary, _ = run_simulation(
                        run_script=run_script,
                        input_json=case_input,
                        output_dir=case_output,
                        scenario_id=args.scenario_id,
                        days=args.days,
                        skip_map=True,
                        skip_plots=True,
                    )
                row["case_dir"] = ""

            for k, v in numeric_kpis(summary).items():
                row[f"kpi::{k}"] = v
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)

        rows.append(row)

    samples_csv = output_dir / "montecarlo_samples.csv"
    all_columns = sorted({k for r in rows for k in r.keys()})
    with samples_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    failed_rows = [r for r in rows if r.get("status") != "ok"]
    baseline = next((r for r in ok_rows if bool(r.get("is_baseline"))), None)
    if baseline is None:
        raise RuntimeError("Baseline Monte Carlo run failed.")

    kpi_cols = sorted([k for k in baseline.keys() if k.startswith("kpi::")])
    factor_cols = sorted([k for k in baseline.keys() if k.startswith("factor::") or k.startswith("demand_item::") or k.startswith("capacity_node::")])

    metric_stats: dict[str, Any] = {}
    for k in kpi_cols:
        values = [to_float(r.get(k), float("nan")) for r in ok_rows]
        values = [v for v in values if not math.isnan(v)]
        if not values:
            continue
        sv = sorted(values)
        metric_stats[k] = {
            "n": len(values),
            "mean": mean(values),
            "std": pstdev(values) if len(values) > 1 else 0.0,
            "min": sv[0],
            "p05": percentile(sv, 0.05),
            "p50": percentile(sv, 0.50),
            "p95": percentile(sv, 0.95),
            "max": sv[-1],
            "baseline": to_float(baseline.get(k), float("nan")),
        }

    corr_targets = [k for k in ["kpi::fill_rate", "kpi::ending_backlog", "kpi::total_cost", "kpi::total_produced"] if k in kpi_cols]
    correlations: dict[str, dict[str, float]] = {}
    for fc in factor_cols:
        xs = [to_float(r.get(fc), float("nan")) for r in ok_rows]
        if any(math.isnan(x) for x in xs):
            continue
        correlations[fc] = {}
        for mk in corr_targets:
            ys = [to_float(r.get(mk), float("nan")) for r in ok_rows]
            if any(math.isnan(y) for y in ys):
                continue
            correlations[fc][mk] = pearson_corr(xs, ys)

    def top_runs(metric: str, reverse: bool, n: int = 10) -> list[dict[str, Any]]:
        candidates = []
        for r in ok_rows:
            val = to_float(r.get(metric), float("nan"))
            if math.isnan(val):
                continue
            candidates.append({"run_id": r["run_id"], metric: val})
        candidates.sort(key=lambda x: to_float(x.get(metric), 0.0), reverse=reverse)
        return candidates[:n]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days_override": args.days,
        "seed": args.seed,
        "runs_requested_excluding_baseline": args.runs,
        "runs_total_including_baseline": total_runs,
        "successful_runs": len(ok_rows),
        "failed_runs": len(failed_rows),
        "factor_distributions": {
            "global": global_factor_spec,
            "demand_item_scale": demand_factor_spec,
            "capacity_node_scale": capacity_factor_spec,
        },
        "metric_statistics": metric_stats,
        "factor_kpi_correlations_pearson": correlations,
        "top_runs": {
            "best_fill_rate": top_runs("kpi::fill_rate", reverse=True),
            "worst_fill_rate": top_runs("kpi::fill_rate", reverse=False),
            "lowest_total_cost": top_runs("kpi::total_cost", reverse=False),
            "highest_total_cost": top_runs("kpi::total_cost", reverse=True),
        },
    }
    summary_json = output_dir / "montecarlo_summary.json"
    write_json(summary_json, summary)

    failed_csv = output_dir / "montecarlo_failed_runs.csv"
    if failed_rows:
        with failed_csv.open("w", encoding="utf-8", newline="") as f:
            cols = sorted({k for r in failed_rows for k in r.keys()})
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(failed_rows)
    elif failed_csv.exists():
        failed_csv.unlink()

    report_md = output_dir / "montecarlo_report.md"
    report = f"""# Monte Carlo Analysis Report

## Setup
- Input: {input_path}
- Scenario: {args.scenario_id}
- Days override: {args.days}
- Seed: {args.seed}
- Runs requested (excluding baseline): {args.runs}
- Runs total (including baseline): {total_runs}
- Runs success: {len(ok_rows)}
- Runs failed: {len(failed_rows)}
- Keep run artifacts: {args.keep_run_artifacts}

## KPI Statistics (distribution over successful runs)
{json.dumps(metric_stats, indent=2, ensure_ascii=False)}

## Top Runs
- Best fill rate: {json.dumps(summary['top_runs']['best_fill_rate'], ensure_ascii=False)}
- Worst fill rate: {json.dumps(summary['top_runs']['worst_fill_rate'], ensure_ascii=False)}
- Lowest total cost: {json.dumps(summary['top_runs']['lowest_total_cost'], ensure_ascii=False)}
- Highest total cost: {json.dumps(summary['top_runs']['highest_total_cost'], ensure_ascii=False)}

## Files
- montecarlo_samples.csv
- montecarlo_summary.json
- montecarlo_report.md
"""
    if failed_rows:
        report += "- montecarlo_failed_runs.csv\n"
    report_md.write_text(report, encoding="utf-8")

    print(f"[OK] Samples CSV: {samples_csv.resolve()}")
    print(f"[OK] Summary JSON: {summary_json.resolve()}")
    print(f"[OK] Report MD: {report_md.resolve()}")
    if failed_rows:
        print(f"[WARN] Failed runs CSV: {failed_csv.resolve()}")


if __name__ == "__main__":
    main()
