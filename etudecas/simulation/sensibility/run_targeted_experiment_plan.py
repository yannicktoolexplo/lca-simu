#!/usr/bin/env python3
"""
Run a targeted 15-scenario experiment plan on top of the simulation engine.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import (  # noqa: E402
    apply_scales,
    choose_scenario,
    load_json,
    numeric_kpis,
    run_simulation,
    to_float,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run targeted experiment plan (15 scenarios).")
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
        default="etudecas/simulation/sensibility/targeted_plan_result",
        help="Experiment output directory.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Override simulation horizon in days (default: 30). Set 0 to keep scenario horizon.",
    )
    return parser.parse_args()


def infer_profile_base_value(profile: list[dict[str, Any]]) -> float:
    if not profile:
        return 0.0
    for p in profile:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "constant")).lower()
        if ptype == "constant":
            return to_float(p.get("value"), 0.0)
        if ptype == "step":
            return to_float(p.get("value"), 0.0)
        if ptype == "piecewise":
            points = sorted(
                [pt for pt in (p.get("points") or []) if isinstance(pt, dict)],
                key=lambda x: int(to_float(x.get("t"), 0.0)),
            )
            if points:
                return to_float(points[0].get("value"), 0.0)
    return 0.0


def scenario_horizon_days(data: dict[str, Any], scenario_id: str) -> int:
    scn = choose_scenario(data, scenario_id)
    days = int(round(to_float(scn.get("days"), 0.0)))
    if days > 0:
        return days
    return 365


def expand_profile_daily_values(profile: list[dict[str, Any]], horizon_days: int) -> list[float]:
    if horizon_days <= 0:
        return []
    if not profile:
        return [0.0] * horizon_days
    first = next((p for p in profile if isinstance(p, dict)), None)
    if not isinstance(first, dict):
        return [0.0] * horizon_days

    ptype = str(first.get("type", "constant")).lower()
    if ptype in {"constant", "step"}:
        value = round(max(0.0, to_float(first.get("value"), 0.0)), 6)
        return [value] * horizon_days

    if ptype == "piecewise":
        raw_points = sorted(
            [pt for pt in (first.get("points") or []) if isinstance(pt, dict)],
            key=lambda x: int(to_float(x.get("t"), 0.0)),
        )
        if not raw_points:
            return [0.0] * horizon_days
        values: list[float] = []
        current_idx = 0
        current_value = max(0.0, to_float(raw_points[0].get("value"), 0.0))
        for day in range(horizon_days):
            while current_idx + 1 < len(raw_points) and int(to_float(raw_points[current_idx + 1].get("t"), 0.0)) <= day:
                current_idx += 1
                current_value = max(0.0, to_float(raw_points[current_idx].get("value"), 0.0))
            values.append(round(current_value, 6))
        return values

    return [round(max(0.0, infer_profile_base_value(profile)), 6)] * horizon_days


def daily_piecewise_profile(values: list[float], *, source: str) -> list[dict[str, Any]]:
    points = [{"t": day, "value": round(max(0.0, value), 6)} for day, value in enumerate(values)]
    if not points:
        points = [{"t": 0, "value": 0.0}]
    return [
        {
            "type": "piecewise",
            "points": points,
            "uom": "unit/day",
            "source": source,
        }
    ]


def mutate_demand_spike(data: dict[str, Any], scenario_id: str) -> None:
    scn = choose_scenario(data, scenario_id)
    horizon_days = scenario_horizon_days(data, scenario_id)
    for d in (scn.get("demand") or []):
        base_values = expand_profile_daily_values(d.get("profile") or [], horizon_days)
        spiked_values = [
            round(value * (1.3 if 3 <= (day % 7) <= 5 else 1.0), 6)
            for day, value in enumerate(base_values)
        ]
        d["profile"] = daily_piecewise_profile(
            spiked_values,
            source="targeted_experiment_demand_spike_sync_weekly",
        )


def mutate_demand_volatility(data: dict[str, Any], scenario_id: str) -> None:
    scn = choose_scenario(data, scenario_id)
    horizon_days = scenario_horizon_days(data, scenario_id)
    factors = [0.8, 1.25, 0.9, 1.3, 0.85, 1.2]
    for d in (scn.get("demand") or []):
        base_values = expand_profile_daily_values(d.get("profile") or [], horizon_days)
        volatile_values = [
            round(value * factors[(day // 7) % len(factors)], 6)
            for day, value in enumerate(base_values)
        ]
        d["profile"] = daily_piecewise_profile(
            volatile_values,
            source="targeted_experiment_demand_volatility_weekly_cycle",
        )


Mutator = Callable[[dict[str, Any], str], None]


def build_experiment_definitions() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "baseline",
            "category": "reference",
            "description": "Reference run with current parameters.",
            "factors": {},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "safety_stock_low",
            "category": "inventory_policy",
            "description": "Lower safety stock policy (x0.5).",
            "factors": {"safety_stock_days_scale": 0.5},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "safety_stock_high",
            "category": "inventory_policy",
            "description": "Higher safety stock policy (x2.0).",
            "factors": {"safety_stock_days_scale": 2.0},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "review_period_2d",
            "category": "inventory_policy",
            "description": "Replenishment reviewed every 2 days.",
            "factors": {"review_period_scale": 2.0},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "review_period_7d",
            "category": "inventory_policy",
            "description": "Replenishment reviewed weekly (7 days).",
            "factors": {"review_period_scale": 7.0},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "supplier_reliability_95",
            "category": "supplier_risk",
            "description": "Supplier reliability reduced to ~95%.",
            "factors": {"supplier_reliability_scale": 0.95},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "supplier_reliability_85",
            "category": "supplier_risk",
            "description": "Supplier reliability reduced to ~85%.",
            "factors": {"supplier_reliability_scale": 0.85},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "lead_time_plus_20pct",
            "category": "supplier_risk",
            "description": "Lead time increased by +20%.",
            "factors": {"lead_time_scale": 1.2},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "lead_time_plus_40pct",
            "category": "supplier_risk",
            "description": "Lead time increased by +40%.",
            "factors": {"lead_time_scale": 1.4},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        },
        {
            "scenario_id": "capacity_m1430_minus_15pct",
            "category": "production_risk",
            "description": "Capacity degradation on M-1430 (-15%).",
            "factors": {},
            "demand_item_scale": {},
            "capacity_node_scale": {"M-1430": 0.85},
            "mutators": [],
        },
        {
            "scenario_id": "capacity_m1810_minus_15pct",
            "category": "production_risk",
            "description": "Capacity degradation on M-1810 (-15%).",
            "factors": {},
            "demand_item_scale": {},
            "capacity_node_scale": {"M-1810": 0.85},
            "mutators": [],
        },
        {
            "scenario_id": "demand_spike_sync",
            "category": "demand_risk",
            "description": "Synchronized demand spike (+30% between day 3 and 6).",
            "factors": {},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [mutate_demand_spike],
        },
        {
            "scenario_id": "demand_volatility_high",
            "category": "demand_risk",
            "description": "High demand volatility (piecewise swings).",
            "factors": {},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [mutate_demand_volatility],
        },
        {
            "scenario_id": "stress_combo",
            "category": "combined_stress",
            "description": "Combined stress: higher lead times, lower reliability, reduced capacities, higher demand.",
            "factors": {
                "lead_time_scale": 1.35,
                "supplier_reliability_scale": 0.85,
                "demand_scale": 1.2,
            },
            "demand_item_scale": {},
            "capacity_node_scale": {"M-1430": 0.9, "M-1810": 0.9},
            "mutators": [mutate_demand_spike],
        },
        {
            "scenario_id": "resilience_combo",
            "category": "combined_mitigation",
            "description": "Resilience policy: more safety stock, stronger capacity, better upstream buffers.",
            "factors": {
                "safety_stock_days_scale": 2.0,
                "review_period_scale": 1.0,
                "supplier_stock_scale": 1.2,
                "production_stock_scale": 1.1,
            },
            "demand_item_scale": {},
            "capacity_node_scale": {"M-1430": 1.1, "M-1810": 1.1},
            "mutators": [],
        },
    ]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    cases_dir = output_dir / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    definitions = build_experiment_definitions()

    rows: list[dict[str, Any]] = []
    for i, cfg in enumerate(definitions, start=1):
        scn_id = str(cfg["scenario_id"])
        case_dir = cases_dir / scn_id
        case_input = case_dir / "input_case.json"
        case_output = case_dir / "simulation_output"
        case_dir.mkdir(parents=True, exist_ok=True)

        factors = dict(cfg.get("factors") or {})
        demand_item_scale = dict(cfg.get("demand_item_scale") or {})
        capacity_node_scale = dict(cfg.get("capacity_node_scale") or {})

        data = apply_scales(
            base_data=base_data,
            scenario_id=args.scenario_id,
            factors=factors,
            demand_item_scale=demand_item_scale,
            capacity_node_scale=capacity_node_scale,
        )
        for fn in (cfg.get("mutators") or []):
            mut = fn
            if callable(mut):
                mut(data, args.scenario_id)

        write_json(case_input, data)

        row: dict[str, Any] = {
            "scenario_id": scn_id,
            "category": str(cfg.get("category", "")),
            "description": str(cfg.get("description", "")),
            "status": "ok",
            "error": "",
            "case_input": str(case_input),
            "case_output_dir": str(case_output),
            "factors_json": json.dumps(factors, ensure_ascii=False),
            "demand_item_scale_json": json.dumps(demand_item_scale, ensure_ascii=False),
            "capacity_node_scale_json": json.dumps(capacity_node_scale, ensure_ascii=False),
            "mutators_json": json.dumps(
                [getattr(m, "__name__", str(m)) for m in (cfg.get("mutators") or [])],
                ensure_ascii=False,
            ),
        }

        print(f"[RUN] {i:02d}/{len(definitions):02d} {scn_id}")
        try:
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
            row["policy::safety_stock_days"] = to_float((summary.get("policy") or {}).get("safety_stock_days"), math.nan)
            row["policy::review_period_days"] = to_float((summary.get("policy") or {}).get("review_period_days"), math.nan)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)

        rows.append(row)

    results_csv = output_dir / "scenario_results.csv"
    all_cols = sorted({k for r in rows for k in r.keys()})
    with results_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_cols)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    baseline = next((r for r in ok_rows if r.get("scenario_id") == "baseline"), None)
    if baseline is None:
        raise RuntimeError("Baseline scenario failed, cannot compute deltas.")

    kpi_cols = sorted([k for k in baseline.keys() if k.startswith("kpi::")])
    delta_rows: list[dict[str, Any]] = []
    for r in ok_rows:
        drow: dict[str, Any] = {
            "scenario_id": r["scenario_id"],
            "category": r["category"],
            "description": r["description"],
        }
        for k in kpi_cols:
            b = to_float(baseline.get(k), 0.0)
            v = to_float(r.get(k), 0.0)
            drow[k] = v
            drow[f"delta::{k}"] = v - b
            drow[f"delta_pct::{k}"] = ((v - b) / b * 100.0) if abs(b) > 1e-12 else float("nan")
        delta_rows.append(drow)

    delta_csv = output_dir / "scenario_delta_vs_baseline.csv"
    delta_cols = sorted({k for r in delta_rows for k in r.keys()})
    with delta_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=delta_cols)
        writer.writeheader()
        writer.writerows(delta_rows)

    def top_by(metric: str, reverse: bool, n: int = 5) -> list[dict[str, Any]]:
        cands = []
        for r in ok_rows:
            if r.get("scenario_id") == "baseline":
                continue
            val = to_float(r.get(metric), float("nan"))
            if math.isnan(val):
                continue
            cands.append(
                {
                    "scenario_id": r["scenario_id"],
                    "category": r["category"],
                    metric: val,
                    "kpi::fill_rate": to_float(r.get("kpi::fill_rate"), float("nan")),
                    "kpi::total_cost": to_float(r.get("kpi::total_cost"), float("nan")),
                    "kpi::ending_backlog": to_float(r.get("kpi::ending_backlog"), float("nan")),
                }
            )
        cands.sort(key=lambda x: to_float(x.get(metric), 0.0), reverse=reverse)
        return cands[:n]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days_override": args.days,
        "scenario_count": len(definitions),
        "successful_scenarios": len(ok_rows),
        "failed_scenarios": len(definitions) - len(ok_rows),
        "baseline_kpis": {k: to_float(baseline.get(k), float("nan")) for k in kpi_cols},
        "top_scenarios": {
            "best_fill_rate": top_by("kpi::fill_rate", reverse=True),
            "lowest_total_cost": top_by("kpi::total_cost", reverse=False),
            "lowest_ending_backlog": top_by("kpi::ending_backlog", reverse=False),
        },
    }
    summary_path = output_dir / "experiment_plan_summary.json"
    write_json(summary_path, summary)

    report_path = output_dir / "experiment_plan_report.md"
    failed = [r for r in rows if r.get("status") != "ok"]
    report = f"""# Targeted Experiment Plan Report

## Setup
- Input: {input_path}
- Scenario: {args.scenario_id}
- Days override: {args.days}
- Scenarios total: {len(definitions)}
- Success: {len(ok_rows)}
- Failed: {len(failed)}

## Baseline KPIs
{json.dumps(summary['baseline_kpis'], indent=2, ensure_ascii=False)}

## Top scenarios
- Best fill rate: {json.dumps(summary['top_scenarios']['best_fill_rate'], ensure_ascii=False)}
- Lowest total cost: {json.dumps(summary['top_scenarios']['lowest_total_cost'], ensure_ascii=False)}
- Lowest ending backlog: {json.dumps(summary['top_scenarios']['lowest_ending_backlog'], ensure_ascii=False)}

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- experiment_plan_summary.json
- experiment_plan_report.md
- cases/*/simulation_output/first_simulation_summary.json
"""
    if failed:
        report += "\n## Failed Scenarios\n"
        for r in failed:
            report += f"- {r['scenario_id']}: {r.get('error', '')}\n"
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] Scenario results CSV: {results_csv.resolve()}")
    print(f"[OK] Scenario delta CSV: {delta_csv.resolve()}")
    print(f"[OK] Summary JSON: {summary_path.resolve()}")
    print(f"[OK] Report MD: {report_path.resolve()}")


if __name__ == "__main__":
    main()
