#!/usr/bin/env python3
"""
Run deterministic one-factor-at-a-time sensitivity analysis on the supply simulation.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
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
    prune_simulation_output,
    run_simulation,
    safe_name,
    to_float,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one-factor-at-a-time sensitivity analysis.")
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
        default="etudecas/simulation/sensibility/result",
        help="Sensitivity result directory.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Override simulation horizon in days (default: 30). Set 0 to keep scenario horizon.",
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=0.2,
        help="Symmetric relative perturbation for OAT (e.g. 0.2 -> 0.8 and 1.2).",
    )
    parser.add_argument(
        "--opening-stock-bootstrap-scale",
        type=float,
        default=None,
        help="Override scenario opening_stock_bootstrap_scale before running the batch.",
    )
    parser.add_argument(
        "--external-procurement-enabled",
        type=str,
        default=None,
        help="Override scenario economic_policy.external_procurement_enabled with true/false.",
    )
    parser.add_argument(
        "--severity-profile",
        choices=["balanced", "aggressive"],
        default="balanced",
        help="Sensitivity amplitude profile. 'aggressive' uses stronger parameter swings.",
    )
    parser.add_argument(
        "--artifact-mode",
        choices=["compact", "full"],
        default="compact",
        help="Artifact retention mode. 'compact' prunes per-case detailed CSV/plot/map outputs.",
    )
    parser.add_argument(
        "--keep-detailed-case",
        action="append",
        default=["baseline", "baseline_repeat"],
        help="Case id to retain with full detailed outputs even in compact mode. Can be repeated.",
    )
    return parser.parse_args()


def base_case() -> dict[str, Any]:
    return {
        "factors": {
            "demand_scale": 1.0,
            "lead_time_scale": 1.0,
            "transport_cost_scale": 1.0,
            "supplier_stock_scale": 1.0,
            "production_stock_scale": 1.0,
            "capacity_scale": 1.0,
            "supplier_capacity_scale": 1.0,
            "safety_stock_days_scale": 1.0,
            "supplier_reliability_scale": 1.0,
        },
        "demand_item_scale": {},
        "capacity_node_scale": {},
        "supplier_node_scale": {},
        "supplier_capacity_node_scale": {},
        "edge_src_lead_time_scale": {},
        "edge_src_reliability_scale": {},
    }


def clone_case_config(case_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "factors": dict(case_cfg["factors"]),
        "demand_item_scale": dict(case_cfg["demand_item_scale"]),
        "capacity_node_scale": dict(case_cfg["capacity_node_scale"]),
        "supplier_node_scale": dict(case_cfg["supplier_node_scale"]),
        "supplier_capacity_node_scale": dict(case_cfg["supplier_capacity_node_scale"]),
        "edge_src_lead_time_scale": dict(case_cfg["edge_src_lead_time_scale"]),
        "edge_src_reliability_scale": dict(case_cfg["edge_src_reliability_scale"]),
    }


def detect_supplier_nodes(data: dict[str, Any]) -> list[str]:
    outgoing_sources = {
        str(edge.get("from"))
        for edge in (data.get("edges") or [])
        if edge.get("from") is not None
    }
    out: list[str] = []
    for node in data.get("nodes", []) or []:
        node_id = str(node.get("id"))
        if str(node.get("type") or "") == "supplier_dc" and node_id in outgoing_sources:
            out.append(node_id)
    return sorted(set(out))


def case_levels(parameter_kind: str, delta: float, severity_profile: str) -> tuple[float, float]:
    lo = 1.0 - delta
    hi = 1.0 + delta
    if severity_profile != "aggressive":
        if parameter_kind.endswith("reliability"):
            return max(0.2, lo), min(1.0, hi)
        return lo, hi

    aggressive_levels = {
        "lead_time": (0.5, 1.8),
        "transport_cost": (0.2, 2.0),
        "supplier_stock": (0.2, 1.8),
        "production_stock": (0.2, 1.8),
        "safety_stock_days": (0.2, 2.0),
        "supplier_reliability": (0.2, 1.0),
        "supplier_capacity": (0.2, 1.8),
        "demand_item": (0.2, 1.8),
        "capacity_node": (0.2, 1.8),
        "supplier_node": (0.2, 1.8),
        "edge_src_lead_time": (0.5, 1.8),
        "edge_src_reliability": (0.2, 1.0),
    }
    return aggressive_levels.get(parameter_kind, (lo, hi))


def build_design(
    data: dict[str, Any],
    scenario_id: str,
    delta: float,
    severity_profile: str,
) -> list[dict[str, Any]]:
    demand_items = detect_demand_items(data, scenario_id)
    production_nodes = detect_production_nodes(data)
    supplier_nodes = detect_supplier_nodes(data)
    lo = 1.0 - delta
    hi = 1.0 + delta
    if lo <= 0:
        raise ValueError(f"Invalid --delta={delta}. Must be < 1.0")

    design: list[dict[str, Any]] = []

    design.append(
        {
            "case_id": "baseline",
            "parameter": "baseline",
            "level": "base",
            "value": 1.0,
            "config": base_case(),
        }
    )
    design.append(
        {
            "case_id": "baseline_repeat",
            "parameter": "baseline",
            "level": "repeat",
            "value": 1.0,
            "config": base_case(),
        }
    )

    global_params = [
        "lead_time_scale",
        "transport_cost_scale",
        "supplier_stock_scale",
        "supplier_capacity_scale",
        "production_stock_scale",
        "safety_stock_days_scale",
        "supplier_reliability_scale",
    ]
    global_param_kinds = {
        "lead_time_scale": "lead_time",
        "transport_cost_scale": "transport_cost",
        "supplier_stock_scale": "supplier_stock",
        "supplier_capacity_scale": "supplier_capacity",
        "production_stock_scale": "production_stock",
        "safety_stock_days_scale": "safety_stock_days",
        "supplier_reliability_scale": "supplier_reliability",
    }
    for p in global_params:
        p_lo, p_hi = case_levels(global_param_kinds[p], delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["factors"][p] = val
            design.append(
                {
                    "case_id": f"{safe_name(p)}_{level}",
                    "parameter": p,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    for item in demand_items:
        pname = f"demand_item_scale::{item}"
        p_lo, p_hi = case_levels("demand_item", delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["demand_item_scale"][item] = val
            design.append(
                {
                    "case_id": f"demand_{safe_name(item)}_{level}",
                    "parameter": pname,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    for node in production_nodes:
        pname = f"capacity_node_scale::{node}"
        p_lo, p_hi = case_levels("capacity_node", delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["capacity_node_scale"][node] = val
            design.append(
                {
                    "case_id": f"capacity_{safe_name(node)}_{level}",
                    "parameter": pname,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    for node in supplier_nodes:
        pname = f"supplier_node_scale::{node}"
        p_lo, p_hi = case_levels("supplier_node", delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["supplier_node_scale"][node] = val
            design.append(
                {
                    "case_id": f"supplier_stock_node_{safe_name(node)}_{level}",
                    "parameter": pname,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    for node in supplier_nodes:
        pname = f"supplier_capacity_node_scale::{node}"
        p_lo, p_hi = case_levels("supplier_capacity", delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["supplier_capacity_node_scale"][node] = val
            design.append(
                {
                    "case_id": f"supplier_capacity_node_{safe_name(node)}_{level}",
                    "parameter": pname,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    for node in supplier_nodes:
        pname = f"edge_src_lead_time_scale::{node}"
        p_lo, p_hi = case_levels("edge_src_lead_time", delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["edge_src_lead_time_scale"][node] = val
            design.append(
                {
                    "case_id": f"supplier_lead_time_node_{safe_name(node)}_{level}",
                    "parameter": pname,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    for node in supplier_nodes:
        pname = f"edge_src_reliability_scale::{node}"
        p_lo, p_hi = case_levels("edge_src_reliability", delta, severity_profile)
        for level, val in [("low", p_lo), ("high", p_hi)]:
            cfg = clone_case_config(base_case())
            cfg["edge_src_reliability_scale"][node] = val
            design.append(
                {
                    "case_id": f"supplier_reliability_node_{safe_name(node)}_{level}",
                    "parameter": pname,
                    "level": level,
                    "value": val,
                    "config": cfg,
                }
            )

    return design


def parse_bool(text: str | None) -> bool | None:
    if text is None:
        return None
    normalized = str(text).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {text}")


def apply_batch_overrides(
    data: dict[str, Any],
    scenario_id: str,
    *,
    opening_stock_bootstrap_scale: float | None,
    external_procurement_enabled: bool | None,
) -> None:
    scenarios = data.get("scenarios", []) or []
    scn = next((s for s in scenarios if str(s.get("id")) == scenario_id), scenarios[0] if scenarios else None)
    if not isinstance(scn, dict):
        return
    if opening_stock_bootstrap_scale is not None:
        scn["opening_stock_bootstrap_scale"] = max(0.0, float(opening_stock_bootstrap_scale))
    if external_procurement_enabled is not None:
        econ = scn.get("economic_policy")
        if not isinstance(econ, dict):
            econ = {}
        econ["external_procurement_enabled"] = bool(external_procurement_enabled)
        scn["economic_policy"] = econ


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    cases_dir = output_dir / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    batch_external_procurement_enabled = parse_bool(args.external_procurement_enabled)
    apply_batch_overrides(
        base_data,
        args.scenario_id,
        opening_stock_bootstrap_scale=args.opening_stock_bootstrap_scale,
        external_procurement_enabled=batch_external_procurement_enabled,
    )
    design = build_design(base_data, args.scenario_id, args.delta, args.severity_profile)
    print(f"[INFO] Sensitivity design cases: {len(design)}")
    keep_detailed_cases = {str(case_id) for case_id in (args.keep_detailed_case or [])}

    rows: list[dict[str, Any]] = []
    for i, case in enumerate(design, start=1):
        case_id = str(case["case_id"])
        case_dir = cases_dir / case_id
        case_input = case_dir / "input_case.json"
        case_output = case_dir / "simulation_output"
        case_dir.mkdir(parents=True, exist_ok=True)

        cfg = case["config"]
        mutated = apply_scales(
            base_data=base_data,
            scenario_id=args.scenario_id,
            factors=cfg["factors"],
            demand_item_scale=cfg["demand_item_scale"],
            capacity_node_scale=cfg["capacity_node_scale"],
            supplier_node_scale=cfg["supplier_node_scale"],
            supplier_capacity_node_scale=cfg["supplier_capacity_node_scale"],
            edge_src_lead_time_scale=cfg["edge_src_lead_time_scale"],
            edge_src_reliability_scale=cfg["edge_src_reliability_scale"],
        )
        write_json(case_input, mutated)

        print(f"[RUN] {i:02d}/{len(design):02d} {case_id}")
        row: dict[str, Any] = {
            "case_id": case_id,
            "parameter": str(case["parameter"]),
            "level": str(case["level"]),
            "value": to_float(case["value"], 1.0),
            "status": "ok",
            "error": "",
            "case_input": str(case_input),
            "case_output_dir": str(case_output),
        }
        row.update({f"factor::{k}": v for k, v in cfg["factors"].items()})
        row.update({f"demand_item::{k}": v for k, v in cfg["demand_item_scale"].items()})
        row.update({f"capacity_node::{k}": v for k, v in cfg["capacity_node_scale"].items()})
        row.update({f"supplier_node::{k}": v for k, v in cfg["supplier_node_scale"].items()})
        row.update({f"supplier_capacity_node::{k}": v for k, v in cfg["supplier_capacity_node_scale"].items()})
        row.update({f"edge_src_lead_time::{k}": v for k, v in cfg["edge_src_lead_time_scale"].items()})
        row.update({f"edge_src_reliability::{k}": v for k, v in cfg["edge_src_reliability_scale"].items()})

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
            if args.artifact_mode == "compact" and case_id not in keep_detailed_cases:
                prune_simulation_output(case_output)
        except Exception as exc:
            row["status"] = "failed"
            row["error"] = str(exc)
        rows.append(row)

    cases_csv = output_dir / "sensitivity_cases.csv"
    all_columns = sorted({k for r in rows for k in r.keys()})
    with cases_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    baseline = next((r for r in ok_rows if r.get("case_id") == "baseline"), None)
    baseline_repeat = next((r for r in ok_rows if r.get("case_id") == "baseline_repeat"), None)
    if baseline is None:
        raise RuntimeError("Baseline case failed, cannot compare sensitivity.")

    kpi_cols = sorted([c for c in baseline.keys() if c.startswith("kpi::")])
    delta_rows: list[dict[str, Any]] = []
    for r in ok_rows:
        dr: dict[str, Any] = {
            "case_id": r["case_id"],
            "parameter": r["parameter"],
            "level": r["level"],
            "value": r["value"],
        }
        for k in kpi_cols:
            b = to_float(baseline.get(k), 0.0)
            v = to_float(r.get(k), 0.0)
            dr[k] = v
            dr[f"delta::{k}"] = v - b
            dr[f"delta_pct::{k}"] = ((v - b) / b * 100.0) if abs(b) > 1e-12 else float("nan")
        delta_rows.append(dr)

    delta_csv = output_dir / "sensitivity_delta_vs_baseline.csv"
    delta_cols = sorted({k for r in delta_rows for k in r.keys()})
    with delta_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=delta_cols)
        writer.writeheader()
        writer.writerows(delta_rows)

    parameter_summary_rows: list[dict[str, Any]] = []

    grouped: dict[str, dict[str, dict[str, float]]] = {}
    by_case_id = {str(r["case_id"]): r for r in ok_rows}
    for c in design:
        p = str(c["parameter"])
        if p == "baseline":
            continue
        grouped.setdefault(p, {})
    for param in sorted(grouped.keys()):
        low_case = next((c for c in design if c["parameter"] == param and c["level"] == "low"), None)
        high_case = next((c for c in design if c["parameter"] == param and c["level"] == "high"), None)
        if not low_case or not high_case:
            continue
        low_row = by_case_id.get(str(low_case["case_id"]))
        high_row = by_case_id.get(str(high_case["case_id"]))
        if not low_row or not high_row:
            continue
        metrics: dict[str, dict[str, float]] = {}
        x_low = to_float(low_case["value"], 1.0)
        x_high = to_float(high_case["value"], 1.0)
        dx = x_high - x_low
        for k in kpi_cols:
            y_low = to_float(low_row.get(k), 0.0)
            y_high = to_float(high_row.get(k), 0.0)
            y_base = to_float(baseline.get(k), 0.0)
            slope = (y_high - y_low) / dx if abs(dx) > 1e-12 else float("nan")
            normalized = float("nan")
            if abs(y_base) > 1e-12 and abs(dx) > 1e-12:
                normalized = ((y_high - y_low) / y_base) / dx
            metrics[k] = {
                "low": y_low,
                "high": y_high,
                "baseline": y_base,
                "slope_dy_dx": slope,
                "normalized_sensitivity": normalized,
            }
        grouped[param] = metrics
        summary_row: dict[str, Any] = {"parameter": param}
        for metric_key in ["kpi::fill_rate", "kpi::ending_backlog", "kpi::total_cost"]:
            metric = metrics.get(metric_key, {})
            metric_label = metric_key.replace("kpi::", "")
            summary_row[f"{metric_label}__baseline"] = metric.get("baseline")
            summary_row[f"{metric_label}__low"] = metric.get("low")
            summary_row[f"{metric_label}__high"] = metric.get("high")
            summary_row[f"{metric_label}__slope_dy_dx"] = metric.get("slope_dy_dx")
            summary_row[f"{metric_label}__normalized_sensitivity"] = metric.get("normalized_sensitivity")
        parameter_summary_rows.append(summary_row)

    parameter_summary_rows.sort(
        key=lambda row: abs(to_float(row.get("fill_rate__normalized_sensitivity"), 0.0)),
        reverse=True,
    )
    parameter_summary_csv = output_dir / "parameter_sensitivity_summary.csv"
    parameter_summary_cols = sorted({k for r in parameter_summary_rows for k in r.keys()}) if parameter_summary_rows else ["parameter"]
    with parameter_summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=parameter_summary_cols)
        writer.writeheader()
        writer.writerows(parameter_summary_rows)

    deterministic_check: dict[str, Any] = {"status": "unknown"}
    if baseline_repeat:
        diffs = {}
        max_abs = 0.0
        for k in kpi_cols:
            b = to_float(baseline.get(k), 0.0)
            r = to_float(baseline_repeat.get(k), 0.0)
            d = abs(r - b)
            diffs[k] = d
            max_abs = max(max_abs, d)
        deterministic_check = {
            "status": "pass" if max_abs <= 1e-9 else "warn",
            "max_abs_diff": max_abs,
            "abs_diff_by_kpi": diffs,
        }

    def top_drivers(metric_key: str, n: int = 5) -> list[dict[str, Any]]:
        rows_tmp: list[dict[str, Any]] = []
        for param, metrics in grouped.items():
            m = metrics.get(metric_key)
            if not m:
                continue
            sens = to_float(m.get("normalized_sensitivity"), float("nan"))
            if math.isnan(sens):
                continue
            rows_tmp.append(
                {
                    "parameter": param,
                    "normalized_sensitivity": sens,
                    "slope_dy_dx": to_float(m.get("slope_dy_dx"), float("nan")),
                }
            )
        rows_tmp.sort(key=lambda x: abs(to_float(x["normalized_sensitivity"], 0.0)), reverse=True)
        return rows_tmp[:n]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days_override": args.days,
        "delta": args.delta,
        "severity_profile": args.severity_profile,
        "parameter_levels": {
            "lead_time": list(case_levels("lead_time", args.delta, args.severity_profile)),
            "transport_cost": list(case_levels("transport_cost", args.delta, args.severity_profile)),
            "supplier_stock": list(case_levels("supplier_stock", args.delta, args.severity_profile)),
            "production_stock": list(case_levels("production_stock", args.delta, args.severity_profile)),
            "safety_stock_days": list(case_levels("safety_stock_days", args.delta, args.severity_profile)),
            "supplier_reliability": list(case_levels("supplier_reliability", args.delta, args.severity_profile)),
            "demand_item": list(case_levels("demand_item", args.delta, args.severity_profile)),
            "capacity_node": list(case_levels("capacity_node", args.delta, args.severity_profile)),
            "supplier_node": list(case_levels("supplier_node", args.delta, args.severity_profile)),
            "edge_src_lead_time": list(case_levels("edge_src_lead_time", args.delta, args.severity_profile)),
            "edge_src_reliability": list(case_levels("edge_src_reliability", args.delta, args.severity_profile)),
        },
        "batch_overrides": {
            "opening_stock_bootstrap_scale": args.opening_stock_bootstrap_scale,
            "external_procurement_enabled": batch_external_procurement_enabled,
        },
        "artifact_mode": args.artifact_mode,
        "kept_detailed_cases": sorted(keep_detailed_cases),
        "case_count": len(design),
        "successful_cases": len(ok_rows),
        "failed_cases": len(design) - len(ok_rows),
        "deterministic_check": deterministic_check,
        "kpis": kpi_cols,
        "normalized_sensitivity_by_parameter": grouped,
        "top_drivers": {
            "kpi::fill_rate": top_drivers("kpi::fill_rate"),
            "kpi::ending_backlog": top_drivers("kpi::ending_backlog"),
            "kpi::total_cost": top_drivers("kpi::total_cost"),
        },
    }
    summary_json = output_dir / "sensitivity_summary.json"
    write_json(summary_json, summary)

    report_md = output_dir / "sensitivity_report.md"
    failed = [r for r in rows if r.get("status") != "ok"]
    report = f"""# Sensitivity Analysis Report

## Setup
- Input: {input_path}
- Scenario: {args.scenario_id}
- Days override: {args.days}
- OAT delta: +/-{args.delta * 100:.1f}%
- Severity profile: {args.severity_profile}
- Artifact mode: {args.artifact_mode}
- Kept detailed cases: {', '.join(sorted(keep_detailed_cases)) if keep_detailed_cases else '(none)'}
- Parameter levels: {json.dumps(summary['parameter_levels'], ensure_ascii=False)}
- Cases total: {len(design)}
- Cases success: {len(ok_rows)}
- Cases failed: {len(failed)}
- Determinism check (baseline vs repeat): {deterministic_check.get('status')} (max abs KPI diff={to_float(deterministic_check.get('max_abs_diff'), 0.0):.6g})

## Top Drivers (normalized sensitivity)
- Fill rate: {json.dumps(summary['top_drivers']['kpi::fill_rate'], ensure_ascii=False)}
- Ending backlog: {json.dumps(summary['top_drivers']['kpi::ending_backlog'], ensure_ascii=False)}
- Total cost: {json.dumps(summary['top_drivers']['kpi::total_cost'], ensure_ascii=False)}

## Files
- sensitivity_cases.csv
- sensitivity_delta_vs_baseline.csv
- parameter_sensitivity_summary.csv
- sensitivity_summary.json
- cases/*/input_case.json
- cases/*/simulation_output/(summaries,reports) in compact mode
"""
    if failed:
        report += "\n## Failed Cases\n"
        for f in failed:
            report += f"- {f['case_id']}: {f.get('error', '')}\n"
    report_md.write_text(report, encoding="utf-8")

    print(f"[OK] Cases CSV: {cases_csv.resolve()}")
    print(f"[OK] Delta CSV: {delta_csv.resolve()}")
    print(f"[OK] Parameter summary CSV: {parameter_summary_csv.resolve()}")
    print(f"[OK] Summary JSON: {summary_json.resolve()}")
    print(f"[OK] Report MD: {report_md.resolve()}")


if __name__ == "__main__":
    main()
