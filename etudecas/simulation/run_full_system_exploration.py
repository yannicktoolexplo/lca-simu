#!/usr/bin/env python3
"""
Run a broad system exploration (corner scenarios + random sampling)
to stress most tunable parameters of the supply simulation.
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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import (  # noqa: E402
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
from etudecas.simulation.result_paths import data_path, ensure_standard_dirs, report_path, summary_path  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run broad full-system exploration.")
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
        default="etudecas/simulation/result",
        help="Output directory.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Override simulation horizon in days (default: 30).",
    )
    parser.add_argument(
        "--random-runs",
        type=int,
        default=180,
        help="Number of random runs after baseline and corner scenarios.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    return parser.parse_args()


def sample_tri(rng: random.Random, lo: float, mode: float, hi: float) -> float:
    return round(rng.triangular(lo, hi, mode), 6)


def top_runs(rows: list[dict[str, Any]], metric: str, reverse: bool, n: int = 10) -> list[dict[str, Any]]:
    vals = []
    for r in rows:
        v = to_float(r.get(metric), float("nan"))
        if math.isnan(v):
            continue
        vals.append({"run_id": r["run_id"], metric: v})
    vals.sort(key=lambda x: to_float(x.get(metric), 0.0), reverse=reverse)
    return vals[:n]


def extract_run_parameters(row: dict[str, Any]) -> dict[str, dict[str, float]]:
    factors: dict[str, float] = {}
    demand_item_scale: dict[str, float] = {}
    capacity_node_scale: dict[str, float] = {}
    for k, v in row.items():
        if k.startswith("factor::"):
            factors[k.replace("factor::", "", 1)] = to_float(v, float("nan"))
        elif k.startswith("demand_item::"):
            demand_item_scale[k.replace("demand_item::", "", 1)] = to_float(v, float("nan"))
        elif k.startswith("capacity_node::"):
            capacity_node_scale[k.replace("capacity_node::", "", 1)] = to_float(v, float("nan"))
    return {
        "factors": dict(sorted(factors.items())),
        "demand_item_scale": dict(sorted(demand_item_scale.items())),
        "capacity_node_scale": dict(sorted(capacity_node_scale.items())),
    }


def pick_extreme_case(rows: list[dict[str, Any]], metric: str, reverse: bool) -> dict[str, Any]:
    candidates = []
    for r in rows:
        v = to_float(r.get(metric), float("nan"))
        if math.isnan(v):
            continue
        candidates.append((v, r))
    if not candidates:
        return {}
    candidates.sort(key=lambda x: x[0], reverse=reverse)
    best_row = candidates[0][1]
    metrics = {
        k.replace("kpi::", "", 1): to_float(v, float("nan"))
        for k, v in best_row.items()
        if k.startswith("kpi::")
    }
    return {
        "run_id": best_row.get("run_id"),
        "target_metric": metric.replace("kpi::", "", 1),
        "target_metric_value": to_float(best_row.get(metric), float("nan")),
        "metrics": dict(sorted(metrics.items())),
        "parameters": extract_run_parameters(best_row),
    }


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_standard_dirs(output_dir)

    samples_csv = data_path(output_dir, "full_system_exploration_samples.csv")
    summary_json = summary_path(output_dir, "full_system_exploration_summary.json")
    report_md = report_path(output_dir, "full_system_exploration_report.md")

    base_data = load_json(input_path)
    demand_items = detect_demand_items(base_data, args.scenario_id)
    production_nodes = detect_production_nodes(base_data)

    rng = random.Random(args.seed)

    # Broader ranges than the existing Monte Carlo.
    global_spec: dict[str, tuple[float, float, float]] = {
        "demand_scale": (0.70, 1.00, 1.40),
        "lead_time_scale": (0.60, 1.00, 1.60),
        "transport_cost_scale": (0.70, 1.00, 1.60),
        "supplier_stock_scale": (0.50, 1.00, 1.80),
        "production_stock_scale": (0.50, 1.00, 1.50),
        "capacity_scale": (0.70, 1.00, 1.30),
        "safety_stock_days_scale": (0.40, 1.00, 2.50),
        "review_period_scale": (1.00, 2.00, 7.00),
        "supplier_reliability_scale": (0.75, 0.98, 1.00),
        "fg_target_days_scale": (0.40, 1.00, 2.50),
        "production_gap_gain_scale": (0.50, 1.00, 1.80),
        "production_smoothing_scale": (0.50, 1.00, 1.80),
        "holding_cost_scale": (0.70, 1.00, 1.60),
        "purchase_cost_floor_scale": (0.70, 1.00, 1.80),
        "external_procurement_daily_cap_days_scale": (0.20, 1.00, 2.00),
        "external_procurement_lead_days_scale": (0.50, 1.00, 2.50),
        "external_procurement_cost_multiplier_scale": (0.70, 1.00, 2.00),
        "external_procurement_transport_cost_scale": (0.70, 1.00, 2.00),
    }
    demand_item_spec = {item: (0.60, 1.00, 1.50) for item in demand_items}
    capacity_node_spec = {node: (0.70, 1.00, 1.30) for node in production_nodes}

    # Corner scenarios focus on key interaction axes.
    corner_axes: dict[str, tuple[float, float]] = {
        "demand_scale": (0.85, 1.20),
        "lead_time_scale": (0.80, 1.40),
        "supplier_reliability_scale": (0.85, 1.00),
        "capacity_scale": (0.85, 1.20),
        "supplier_stock_scale": (0.80, 1.30),
        "review_period_scale": (1.0, 4.0),
        "external_procurement_daily_cap_days_scale": (0.5, 1.5),
        "external_procurement_lead_days_scale": (0.7, 1.8),
    }

    corner_cases: list[dict[str, float]] = []
    keys = sorted(corner_axes.keys())
    n_corners = 1 << len(keys)
    for mask in range(n_corners):
        cfg = {k: 1.0 for k in global_spec.keys()}
        for i, k in enumerate(keys):
            lo, hi = corner_axes[k]
            cfg[k] = hi if (mask & (1 << i)) else lo
        corner_cases.append(cfg)

    total_runs = 1 + len(corner_cases) + max(0, int(args.random_runs))
    rows: list[dict[str, Any]] = []

    for i in range(total_runs):
        run_id = f"full_run_{i:04d}"
        is_baseline = i == 0
        is_corner = (0 < i <= len(corner_cases))

        factors = {k: 1.0 for k in global_spec.keys()}
        demand_item_scale = {item: 1.0 for item in demand_items}
        capacity_node_scale = {node: 1.0 for node in production_nodes}

        if is_corner:
            factors.update(corner_cases[i - 1])
        elif not is_baseline:
            for k, (lo, mode, hi) in global_spec.items():
                factors[k] = sample_tri(rng, lo, mode, hi)
            # Keep review period integer-like.
            factors["review_period_scale"] = float(max(1, int(round(factors["review_period_scale"]))))
            for item, (lo, mode, hi) in demand_item_spec.items():
                demand_item_scale[item] = sample_tri(rng, lo, mode, hi)
            for node, (lo, mode, hi) in capacity_node_spec.items():
                capacity_node_scale[node] = sample_tri(rng, lo, mode, hi)

        row: dict[str, Any] = {
            "run_id": run_id,
            "is_baseline": is_baseline,
            "is_corner_case": is_corner,
            "status": "ok",
            "error": "",
        }
        row.update({f"factor::{k}": v for k, v in factors.items()})
        row.update({f"demand_item::{k}": v for k, v in demand_item_scale.items()})
        row.update({f"capacity_node::{k}": v for k, v in capacity_node_scale.items()})

        print(f"[RUN] {i + 1:03d}/{total_runs:03d} {run_id}")
        try:
            mutated = apply_scales(
                base_data=base_data,
                scenario_id=args.scenario_id,
                factors=factors,
                demand_item_scale=demand_item_scale,
                capacity_node_scale=capacity_node_scale,
            )
            with tempfile.TemporaryDirectory(prefix=f"full_{safe_name(run_id)}_") as tmp:
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
            for k, v in numeric_kpis(summary).items():
                row[f"kpi::{k}"] = v
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)
        rows.append(row)

    all_columns = sorted({k for r in rows for k in r.keys()})
    with samples_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    failed_rows = [r for r in rows if r.get("status") != "ok"]
    baseline = next((r for r in ok_rows if bool(r.get("is_baseline"))), None)
    if baseline is None:
        raise RuntimeError("Baseline run failed in full exploration.")

    kpi_cols = sorted([k for k in baseline.keys() if k.startswith("kpi::")])
    factor_cols = sorted(
        [
            k
            for k in baseline.keys()
            if k.startswith("factor::")
            or k.startswith("demand_item::")
            or k.startswith("capacity_node::")
        ]
    )

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

    corr_targets = [k for k in ["kpi::fill_rate", "kpi::ending_backlog", "kpi::total_cost"] if k in kpi_cols]
    correlations: dict[str, dict[str, float]] = {}
    for fc in factor_cols:
        xs = [to_float(r.get(fc), float("nan")) for r in ok_rows]
        if any(math.isnan(x) for x in xs):
            continue
        if max(xs) - min(xs) <= 1e-12:
            continue
        correlations[fc] = {}
        for mk in corr_targets:
            ys = [to_float(r.get(mk), float("nan")) for r in ok_rows]
            if any(math.isnan(y) for y in ys):
                continue
            correlations[fc][mk] = pearson_corr(xs, ys)

    fill_vals = [to_float(r.get("kpi::fill_rate"), float("nan")) for r in ok_rows]
    fill_vals = [v for v in fill_vals if not math.isnan(v)]
    backlog_vals = [to_float(r.get("kpi::ending_backlog"), float("nan")) for r in ok_rows]
    backlog_vals = [v for v in backlog_vals if not math.isnan(v)]
    cost_vals = [to_float(r.get("kpi::total_cost"), float("nan")) for r in ok_rows]
    cost_vals = [v for v in cost_vals if not math.isnan(v)]

    b_fill = to_float(baseline.get("kpi::fill_rate"), float("nan"))
    b_backlog = to_float(baseline.get("kpi::ending_backlog"), float("nan"))
    b_cost = to_float(baseline.get("kpi::total_cost"), float("nan"))

    risk_probabilities = {
        "p_fill_lt_0_90": sum(1 for v in fill_vals if v < 0.90) / len(fill_vals) if fill_vals else float("nan"),
        "p_fill_lt_0_85": sum(1 for v in fill_vals if v < 0.85) / len(fill_vals) if fill_vals else float("nan"),
        "p_backlog_gt_100": sum(1 for v in backlog_vals if v > 100.0) / len(backlog_vals) if backlog_vals else float("nan"),
        "p_backlog_gt_200": sum(1 for v in backlog_vals if v > 200.0) / len(backlog_vals) if backlog_vals else float("nan"),
        "p_cost_gt_24000": sum(1 for v in cost_vals if v > 24000.0) / len(cost_vals) if cost_vals else float("nan"),
        "p_cost_gt_28000": sum(1 for v in cost_vals if v > 28000.0) / len(cost_vals) if cost_vals else float("nan"),
        "p_fill_ge_baseline": (
            sum(1 for r in ok_rows if to_float(r.get("kpi::fill_rate"), -1e9) >= b_fill) / len(ok_rows)
            if ok_rows and not math.isnan(b_fill)
            else float("nan")
        ),
        "p_backlog_le_baseline": (
            sum(1 for r in ok_rows if to_float(r.get("kpi::ending_backlog"), 1e18) <= b_backlog) / len(ok_rows)
            if ok_rows and not math.isnan(b_backlog)
            else float("nan")
        ),
        "p_cost_le_baseline": (
            sum(1 for r in ok_rows if to_float(r.get("kpi::total_cost"), 1e18) <= b_cost) / len(ok_rows)
            if ok_rows and not math.isnan(b_cost)
            else float("nan")
        ),
    }

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days_override": args.days,
        "seed": args.seed,
        "runs": {
            "total_requested": total_runs,
            "baseline": 1,
            "corner_cases": len(corner_cases),
            "random_runs": max(0, int(args.random_runs)),
            "successful_runs": len(ok_rows),
            "failed_runs": len(failed_rows),
        },
        "sampling_space": {
            "global_factors_triangular": global_spec,
            "demand_item_triangular": demand_item_spec,
            "capacity_node_triangular": capacity_node_spec,
            "corner_axes_binary": corner_axes,
        },
        "metric_statistics": metric_stats,
        "factor_kpi_correlations_pearson": correlations,
        "risk_probabilities": risk_probabilities,
        "top_runs": {
            "best_fill_rate": top_runs(ok_rows, "kpi::fill_rate", reverse=True),
            "worst_fill_rate": top_runs(ok_rows, "kpi::fill_rate", reverse=False),
            "lowest_total_cost": top_runs(ok_rows, "kpi::total_cost", reverse=False),
            "highest_total_cost": top_runs(ok_rows, "kpi::total_cost", reverse=True),
        },
        "extreme_cases_with_parameters": {
            "worst_fill_rate": pick_extreme_case(ok_rows, "kpi::fill_rate", reverse=False),
            "best_fill_rate": pick_extreme_case(ok_rows, "kpi::fill_rate", reverse=True),
            "highest_total_cost": pick_extreme_case(ok_rows, "kpi::total_cost", reverse=True),
            "lowest_total_cost": pick_extreme_case(ok_rows, "kpi::total_cost", reverse=False),
            "highest_ending_backlog": pick_extreme_case(ok_rows, "kpi::ending_backlog", reverse=True),
            "lowest_ending_backlog": pick_extreme_case(ok_rows, "kpi::ending_backlog", reverse=False),
        },
    }
    write_json(summary_json, summary)

    report = f"""# Full System Exploration Report

## Setup
- Input: {input_path}
- Scenario: {args.scenario_id}
- Days override: {args.days}
- Seed: {args.seed}
- Total runs: {total_runs}
  - Baseline: 1
  - Corner scenarios: {len(corner_cases)}
  - Random runs: {max(0, int(args.random_runs))}
- Successful runs: {len(ok_rows)}
- Failed runs: {len(failed_rows)}

## KPI Statistics
{json.dumps(metric_stats, indent=2, ensure_ascii=False)}

## Risk Probabilities
{json.dumps(risk_probabilities, indent=2, ensure_ascii=False)}

## Top Runs
- Best fill rate: {json.dumps(summary['top_runs']['best_fill_rate'], ensure_ascii=False)}
- Worst fill rate: {json.dumps(summary['top_runs']['worst_fill_rate'], ensure_ascii=False)}
- Lowest total cost: {json.dumps(summary['top_runs']['lowest_total_cost'], ensure_ascii=False)}
- Highest total cost: {json.dumps(summary['top_runs']['highest_total_cost'], ensure_ascii=False)}

## Extreme Cases With Parameters
{json.dumps(summary['extreme_cases_with_parameters'], indent=2, ensure_ascii=False)}
"""
    report_md.write_text(report, encoding="utf-8")

    failed_csv = output_dir / "full_system_exploration_failed_runs.csv"
    if failed_rows:
        with failed_csv.open("w", encoding="utf-8", newline="") as f:
            cols = sorted({k for r in failed_rows for k in r.keys()})
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(failed_rows)
    elif failed_csv.exists():
        failed_csv.unlink()

    print(f"[OK] Samples CSV: {samples_csv.resolve()}")
    print(f"[OK] Summary JSON: {summary_json.resolve()}")
    print(f"[OK] Report MD: {report_md.resolve()}")
    if failed_rows:
        print(f"[WARN] Failed runs CSV: {failed_csv.resolve()}")


if __name__ == "__main__":
    main()
