#!/usr/bin/env python3
"""
Run a broad perturbation/shock campaign across many supply parameters.
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
    detect_demand_items,
    detect_production_nodes,
    load_json,
    numeric_kpis,
    run_simulation,
    safe_name,
    to_float,
    write_json,
)


Mutator = Callable[[dict[str, Any], str], None]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run perturbation/shock scenario campaign.")
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
        default="etudecas/simulation/sensibility/shock_campaign_result",
        help="Shock campaign output directory.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Override simulation horizon in days (default: 30).",
    )
    return parser.parse_args()


def infer_profile_base_value(profile: list[dict[str, Any]]) -> float:
    if not profile:
        return 0.0
    for p in profile:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "constant")).lower()
        if ptype in {"constant", "step"}:
            return to_float(p.get("value"), 0.0)
        if ptype == "piecewise":
            points = sorted(
                [pt for pt in (p.get("points") or []) if isinstance(pt, dict)],
                key=lambda x: int(to_float(x.get("t"), 0.0)),
            )
            if points:
                return to_float(points[0].get("value"), 0.0)
    return 0.0


def make_sync_spike_mutator(multiplier: float, start: int = 3, end: int = 10) -> Mutator:
    def _mut(data: dict[str, Any], scenario_id: str) -> None:
        scn = choose_scenario(data, scenario_id)
        for d in (scn.get("demand") or []):
            base = infer_profile_base_value(d.get("profile") or [])
            d["profile"] = [
                {
                    "type": "piecewise",
                    "points": [
                        {"t": 0, "value": round(base, 6)},
                        {"t": start, "value": round(base * multiplier, 6)},
                        {"t": end, "value": round(base, 6)},
                    ],
                    "uom": "unit/day",
                    "source": f"shock_sync_spike_x{multiplier}",
                }
            ]

    _mut.__name__ = f"sync_spike_x{str(multiplier).replace('.', '_')}"
    return _mut


def make_wave_mutator(factors: list[float], step: int = 2) -> Mutator:
    def _mut(data: dict[str, Any], scenario_id: str) -> None:
        scn = choose_scenario(data, scenario_id)
        for d in (scn.get("demand") or []):
            base = infer_profile_base_value(d.get("profile") or [])
            points = []
            t = 0
            for f in factors:
                points.append({"t": t, "value": round(base * f, 6)})
                t += step
            d["profile"] = [
                {
                    "type": "piecewise",
                    "points": points,
                    "uom": "unit/day",
                    "source": "shock_wave_profile",
                }
            ]

    _mut.__name__ = "wave_profile"
    return _mut


def make_drop_recovery_mutator(drop_factor: float, recover_day: int = 12) -> Mutator:
    def _mut(data: dict[str, Any], scenario_id: str) -> None:
        scn = choose_scenario(data, scenario_id)
        for d in (scn.get("demand") or []):
            base = infer_profile_base_value(d.get("profile") or [])
            d["profile"] = [
                {
                    "type": "piecewise",
                    "points": [
                        {"t": 0, "value": round(base, 6)},
                        {"t": 2, "value": round(base * drop_factor, 6)},
                        {"t": recover_day, "value": round(base, 6)},
                    ],
                    "uom": "unit/day",
                    "source": f"shock_drop_x{drop_factor}",
                }
            ]

    _mut.__name__ = f"drop_recovery_x{str(drop_factor).replace('.', '_')}"
    return _mut


def clone_case(case_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": str(case_cfg["scenario_id"]),
        "category": str(case_cfg["category"]),
        "description": str(case_cfg["description"]),
        "factors": dict(case_cfg.get("factors") or {}),
        "demand_item_scale": dict(case_cfg.get("demand_item_scale") or {}),
        "capacity_node_scale": dict(case_cfg.get("capacity_node_scale") or {}),
        "mutators": list(case_cfg.get("mutators") or []),
    }


def build_shock_definitions(data: dict[str, Any], scenario_id: str) -> list[dict[str, Any]]:
    demand_items = detect_demand_items(data, scenario_id)
    production_nodes = detect_production_nodes(data)
    if not demand_items:
        raise RuntimeError("No demand items found for scenario.")
    if not production_nodes:
        raise RuntimeError("No production nodes found.")

    defs: list[dict[str, Any]] = [
        {
            "scenario_id": "baseline",
            "category": "reference",
            "description": "Reference run.",
            "factors": {},
            "demand_item_scale": {},
            "capacity_node_scale": {},
            "mutators": [],
        }
    ]

    # Global single-factor shocks (mild/severe).
    global_shocks: dict[str, list[tuple[str, float]]] = {
        "demand_scale": [("down", 0.8), ("up", 1.2), ("up_severe", 1.4)],
        "lead_time_scale": [("down", 0.8), ("up", 1.3), ("up_severe", 1.6)],
        "transport_cost_scale": [("down", 0.8), ("up", 1.3), ("up_severe", 1.6)],
        "supplier_stock_scale": [("down", 0.7), ("up", 1.2), ("up_severe", 1.6)],
        "production_stock_scale": [("down", 0.7), ("up", 1.2), ("up_severe", 1.4)],
        "capacity_scale": [("down", 0.8), ("down_severe", 0.7), ("up", 1.2)],
        "safety_stock_days_scale": [("low", 0.5), ("high", 1.8), ("high_severe", 2.5)],
        "review_period_scale": [("2d", 2.0), ("4d", 4.0), ("7d", 7.0)],
        "supplier_reliability_scale": [("95pct", 0.95), ("85pct", 0.85), ("75pct", 0.75)],
    }
    for param, levels in global_shocks.items():
        for label, value in levels:
            defs.append(
                {
                    "scenario_id": f"{safe_name(param)}_{label}",
                    "category": "single_factor_global",
                    "description": f"{param} -> {value}",
                    "factors": {param: value},
                    "demand_item_scale": {},
                    "capacity_node_scale": {},
                    "mutators": [],
                }
            )

    # Demand item specific shocks.
    for item in demand_items:
        for label, value in [("down", 0.7), ("up", 1.3), ("up_severe", 1.5)]:
            defs.append(
                {
                    "scenario_id": f"demand_{safe_name(item)}_{label}",
                    "category": "single_factor_item_demand",
                    "description": f"Demand scale on {item} -> {value}",
                    "factors": {},
                    "demand_item_scale": {item: value},
                    "capacity_node_scale": {},
                    "mutators": [],
                }
            )

    # Production node specific shocks.
    for node in production_nodes:
        for label, value in [("down10", 0.9), ("down20", 0.8), ("down30", 0.7), ("up20", 1.2)]:
            defs.append(
                {
                    "scenario_id": f"capacity_{safe_name(node)}_{label}",
                    "category": "single_factor_node_capacity",
                    "description": f"Capacity scale on {node} -> {value}",
                    "factors": {},
                    "demand_item_scale": {},
                    "capacity_node_scale": {node: value},
                    "mutators": [],
                }
            )

    # Demand profile shocks.
    defs.extend(
        [
            {
                "scenario_id": "demand_sync_spike_150",
                "category": "profile_shock",
                "description": "Synchronized demand spike +50%.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [make_sync_spike_mutator(1.5, start=3, end=10)],
            },
            {
                "scenario_id": "demand_sync_spike_200",
                "category": "profile_shock",
                "description": "Synchronized demand spike +100%.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [make_sync_spike_mutator(2.0, start=3, end=11)],
            },
            {
                "scenario_id": "demand_wave_high_vol",
                "category": "profile_shock",
                "description": "High volatility demand wave.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [make_wave_mutator([0.7, 1.4, 0.8, 1.5, 0.75, 1.35], step=2)],
            },
            {
                "scenario_id": "demand_wave_extreme",
                "category": "profile_shock",
                "description": "Extreme oscillating demand wave.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [make_wave_mutator([0.6, 1.6, 0.7, 1.7, 0.65, 1.5], step=2)],
            },
            {
                "scenario_id": "demand_drop_recovery_50",
                "category": "profile_shock",
                "description": "Demand drops to 50% then recovers.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [make_drop_recovery_mutator(0.5, recover_day=12)],
            },
            {
                "scenario_id": "demand_drop_recovery_30",
                "category": "profile_shock",
                "description": "Demand drops to 30% then recovers.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [make_drop_recovery_mutator(0.3, recover_day=14)],
            },
        ]
    )

    # Combined stress scenarios.
    # Pick first two production nodes if available.
    node_a = production_nodes[0]
    node_b = production_nodes[1] if len(production_nodes) > 1 else production_nodes[0]
    item_a = demand_items[0]
    item_b = demand_items[1] if len(demand_items) > 1 else demand_items[0]

    defs.extend(
        [
            {
                "scenario_id": "combo_supplier_crunch",
                "category": "combined_stress",
                "description": "Longer lead times + lower reliability + lower supplier stock.",
                "factors": {
                    "lead_time_scale": 1.5,
                    "supplier_reliability_scale": 0.8,
                    "supplier_stock_scale": 0.7,
                    "review_period_scale": 4.0,
                },
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [],
            },
            {
                "scenario_id": "combo_demand_boom",
                "category": "combined_stress",
                "description": "High global demand + item spikes + profile spike.",
                "factors": {"demand_scale": 1.25},
                "demand_item_scale": {item_a: 1.4, item_b: 1.4},
                "capacity_node_scale": {},
                "mutators": [make_sync_spike_mutator(1.6, start=3, end=10)],
            },
            {
                "scenario_id": "combo_dual_plant_outage",
                "category": "combined_stress",
                "description": "Simultaneous production outages on both plants.",
                "factors": {},
                "demand_item_scale": {},
                "capacity_node_scale": {node_a: 0.65, node_b: 0.65},
                "mutators": [],
            },
            {
                "scenario_id": "combo_logistics_strike",
                "category": "combined_stress",
                "description": "Lead/transport shock with slower review period.",
                "factors": {
                    "lead_time_scale": 1.6,
                    "transport_cost_scale": 1.6,
                    "review_period_scale": 7.0,
                },
                "demand_item_scale": {},
                "capacity_node_scale": {},
                "mutators": [],
            },
            {
                "scenario_id": "combo_systemic_stress",
                "category": "combined_stress",
                "description": "Full systemic stress: demand up, delays up, reliability down, capacities down.",
                "factors": {
                    "demand_scale": 1.3,
                    "lead_time_scale": 1.5,
                    "supplier_reliability_scale": 0.78,
                    "supplier_stock_scale": 0.75,
                    "review_period_scale": 4.0,
                },
                "demand_item_scale": {item_a: 1.3, item_b: 1.3},
                "capacity_node_scale": {node_a: 0.8, node_b: 0.8},
                "mutators": [make_wave_mutator([1.0, 1.5, 1.1, 1.6, 1.0, 1.4], step=2)],
            },
            {
                "scenario_id": "combo_extreme_black_swan",
                "category": "combined_stress",
                "description": "Extreme black-swan stress combining severe shocks.",
                "factors": {
                    "demand_scale": 1.4,
                    "lead_time_scale": 1.6,
                    "supplier_reliability_scale": 0.75,
                    "supplier_stock_scale": 0.6,
                    "production_stock_scale": 0.7,
                    "capacity_scale": 0.75,
                    "review_period_scale": 7.0,
                },
                "demand_item_scale": {item_a: 1.5, item_b: 1.5},
                "capacity_node_scale": {node_a: 0.7, node_b: 0.7},
                "mutators": [make_sync_spike_mutator(2.0, start=2, end=12)],
            },
            {
                "scenario_id": "combo_resilience_max",
                "category": "combined_mitigation",
                "description": "Aggressive resilience policy for stress resistance.",
                "factors": {
                    "safety_stock_days_scale": 2.5,
                    "supplier_stock_scale": 1.5,
                    "production_stock_scale": 1.3,
                    "capacity_scale": 1.2,
                    "review_period_scale": 1.0,
                    "supplier_reliability_scale": 1.0,
                },
                "demand_item_scale": {},
                "capacity_node_scale": {node_a: 1.2, node_b: 1.2},
                "mutators": [],
            },
        ]
    )

    # Ensure unique ids and deterministic order.
    seen = set()
    out = []
    for d in defs:
        sid = str(d["scenario_id"])
        if sid in seen:
            continue
        seen.add(sid)
        out.append(clone_case(d))
    return out


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    cases_dir = output_dir / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    definitions = build_shock_definitions(base_data, args.scenario_id)
    print(f"[INFO] Shock scenarios: {len(definitions)}")

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
            if callable(fn):
                fn(data, args.scenario_id)

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

        print(f"[RUN] {i:03d}/{len(definitions):03d} {scn_id}")
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
        raise RuntimeError("Baseline scenario failed in shock campaign.")

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

    def top_by(metric: str, reverse: bool, n: int = 8) -> list[dict[str, Any]]:
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
            "worst_fill_rate": top_by("kpi::fill_rate", reverse=False),
            "highest_ending_backlog": top_by("kpi::ending_backlog", reverse=True),
        },
    }
    summary_path = output_dir / "shock_campaign_summary.json"
    write_json(summary_path, summary)

    failed_rows = [r for r in rows if r.get("status") != "ok"]
    report_path = output_dir / "shock_campaign_report.md"
    report = f"""# Shock Campaign Report

## Setup
- Input: {input_path}
- Scenario: {args.scenario_id}
- Days override: {args.days}
- Scenarios total: {len(definitions)}
- Success: {len(ok_rows)}
- Failed: {len(failed_rows)}

## Baseline KPIs
{json.dumps(summary['baseline_kpis'], indent=2, ensure_ascii=False)}

## Top scenarios
- Best fill rate: {json.dumps(summary['top_scenarios']['best_fill_rate'], ensure_ascii=False)}
- Lowest total cost: {json.dumps(summary['top_scenarios']['lowest_total_cost'], ensure_ascii=False)}
- Lowest ending backlog: {json.dumps(summary['top_scenarios']['lowest_ending_backlog'], ensure_ascii=False)}
- Worst fill rate: {json.dumps(summary['top_scenarios']['worst_fill_rate'], ensure_ascii=False)}
- Highest ending backlog: {json.dumps(summary['top_scenarios']['highest_ending_backlog'], ensure_ascii=False)}

## Files
- scenario_results.csv
- scenario_delta_vs_baseline.csv
- shock_campaign_summary.json
- shock_campaign_report.md
- cases/*/simulation_output/first_simulation_summary.json
"""
    if failed_rows:
        report += "\n## Failed Scenarios\n"
        for r in failed_rows:
            report += f"- {r['scenario_id']}: {r.get('error', '')}\n"
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] Scenario results CSV: {results_csv.resolve()}")
    print(f"[OK] Scenario delta CSV: {delta_csv.resolve()}")
    print(f"[OK] Summary JSON: {summary_path.resolve()}")
    print(f"[OK] Report MD: {report_path.resolve()}")


if __name__ == "__main__":
    main()
