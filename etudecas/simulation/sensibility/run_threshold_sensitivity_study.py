#!/usr/bin/env python3
"""
Run a multi-level one-factor-at-a-time sensitivity study with breakpoint detection.

Goal:
- quantify what each parameter moves in the outputs
- identify when a KPI crosses an operational threshold
- support baseline realism reviews by exposing "safe bands" around the current setup
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run threshold-oriented sensitivity study.")
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
        default="etudecas/simulation/sensibility/threshold_result",
        help="Output directory for the study.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Simulation horizon in days for the study.",
    )
    parser.add_argument(
        "--top-suppliers",
        type=int,
        default=4,
        help="Number of active suppliers kept for node-level sweeps.",
    )
    parser.add_argument(
        "--service-threshold",
        type=float,
        default=0.90,
        help="Operational service threshold used for breakpoint detection.",
    )
    parser.add_argument(
        "--service-soft-threshold",
        type=float,
        default=0.85,
        help="Soft service threshold used for broader realism screening.",
    )
    parser.add_argument(
        "--backlog-increase-pct",
        type=float,
        default=0.25,
        help="Relative backlog increase threshold vs baseline (0.25 -> +25%%).",
    )
    parser.add_argument(
        "--cost-increase-pct",
        type=float,
        default=0.10,
        help="Relative cost increase threshold vs baseline (0.10 -> +10%%).",
    )
    return parser.parse_args()


def base_case() -> dict[str, Any]:
    return {
        "factors": {
            "lead_time_scale": 1.0,
            "supplier_stock_scale": 1.0,
            "production_stock_scale": 1.0,
            "safety_stock_days_scale": 1.0,
            "review_period_scale": 1.0,
            "supplier_reliability_scale": 1.0,
            "holding_cost_scale": 1.0,
            "external_procurement_daily_cap_days_scale": 1.0,
            "external_procurement_lead_days_scale": 1.0,
            "external_procurement_cost_multiplier_scale": 1.0,
        },
        "demand_item_scale": {},
        "capacity_node_scale": {},
        "supplier_node_scale": {},
        "supplier_capacity_node_scale": {},
        "edge_src_lead_time_scale": {},
        "edge_src_reliability_scale": {},
        "scenario_scalars": {},
        "scenario_flags": {},
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
        "scenario_scalars": dict(case_cfg["scenario_scalars"]),
        "scenario_flags": dict(case_cfg["scenario_flags"]),
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


def select_active_suppliers(
    shipment_csv: Path,
    allowed_suppliers: set[str],
    top_n: int,
) -> list[str]:
    shipped_qty_by_supplier: dict[str, float] = {}
    if shipment_csv.exists():
        with shipment_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = str(row.get("src_node_id") or "")
                if src not in allowed_suppliers:
                    continue
                shipped_qty_by_supplier[src] = shipped_qty_by_supplier.get(src, 0.0) + max(
                    0.0,
                    to_float(row.get("shipped_qty"), 0.0),
                )
    ordered = sorted(shipped_qty_by_supplier.items(), key=lambda it: (-it[1], it[0]))
    selected = [supplier for supplier, qty in ordered if qty > 1e-9][:top_n]
    if not selected:
        selected = sorted(allowed_suppliers)[:top_n]
    return selected


def parameter_specs(
    demand_items: list[str],
    production_nodes: list[str],
    supplier_nodes: list[str],
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "parameter_key": "lead_time_scale",
            "parameter_group": "global",
            "parameter_label": "Lead time global",
            "kind": "factor",
            "target": "lead_time_scale",
            "levels": [0.75, 0.9, 1.0, 1.1, 1.25, 1.5],
            "realism_focus": "exogenous_network",
        },
        {
            "parameter_key": "supplier_reliability_scale",
            "parameter_group": "global",
            "parameter_label": "Fiabilite fournisseur globale",
            "kind": "factor",
            "target": "supplier_reliability_scale",
            "levels": [0.85, 0.9, 0.95, 1.0],
            "realism_focus": "exogenous_network",
        },
        {
            "parameter_key": "supplier_stock_scale",
            "parameter_group": "global",
            "parameter_label": "Stock fournisseur global",
            "kind": "factor",
            "target": "supplier_stock_scale",
            "levels": [0.5, 0.75, 1.0, 1.25, 1.5],
            "realism_focus": "buffer_policy",
        },
        {
            "parameter_key": "production_stock_scale",
            "parameter_group": "global",
            "parameter_label": "Stock production global",
            "kind": "factor",
            "target": "production_stock_scale",
            "levels": [0.5, 0.75, 1.0, 1.25, 1.5],
            "realism_focus": "buffer_policy",
        },
        {
            "parameter_key": "safety_stock_days_scale",
            "parameter_group": "global",
            "parameter_label": "Safety stock global",
            "kind": "factor",
            "target": "safety_stock_days_scale",
            "levels": [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
            "realism_focus": "buffer_policy",
        },
        {
            "parameter_key": "review_period_scale",
            "parameter_group": "global",
            "parameter_label": "Periode de revue",
            "kind": "factor",
            "target": "review_period_scale",
            "levels": [1.0, 2.0, 3.0, 5.0, 7.0],
            "realism_focus": "planning_policy",
        },
        {
            "parameter_key": "opening_stock_bootstrap_scale",
            "parameter_group": "global",
            "parameter_label": "Bootstrap stock initial",
            "kind": "scenario_scalar",
            "target": "opening_stock_bootstrap_scale",
            "levels": [0.25, 0.5, 0.75, 1.0, 1.25],
            "realism_focus": "model_protection",
        },
        {
            "parameter_key": "external_procurement_enabled",
            "parameter_group": "global",
            "parameter_label": "Appro externe activee",
            "kind": "scenario_flag",
            "target": "external_procurement_enabled",
            "levels": [0.0, 1.0],
            "realism_focus": "model_protection",
        },
        {
            "parameter_key": "external_procurement_daily_cap_days_scale",
            "parameter_group": "global",
            "parameter_label": "Capacite appro externe",
            "kind": "factor",
            "target": "external_procurement_daily_cap_days_scale",
            "levels": [0.4, 0.7, 1.0, 1.3, 1.6],
            "realism_focus": "model_protection",
        },
        {
            "parameter_key": "external_procurement_lead_days_scale",
            "parameter_group": "global",
            "parameter_label": "Delai appro externe",
            "kind": "factor",
            "target": "external_procurement_lead_days_scale",
            "levels": [0.6, 0.8, 1.0, 1.2, 1.5],
            "realism_focus": "model_protection",
        },
        {
            "parameter_key": "external_procurement_cost_multiplier_scale",
            "parameter_group": "global",
            "parameter_label": "Surcout appro externe",
            "kind": "factor",
            "target": "external_procurement_cost_multiplier_scale",
            "levels": [0.7, 1.0, 1.5, 2.0, 3.0],
            "realism_focus": "economic_penalty",
        },
        {
            "parameter_key": "holding_cost_scale",
            "parameter_group": "global",
            "parameter_label": "Cout de stock",
            "kind": "factor",
            "target": "holding_cost_scale",
            "levels": [0.5, 0.75, 1.0, 1.25, 1.5],
            "realism_focus": "economic_penalty",
        },
    ]

    for item_id in demand_items:
        specs.append(
            {
                "parameter_key": f"demand_item::{item_id}",
                "parameter_group": "demand_item",
                "parameter_label": f"Demande {item_id.split(':', 1)[-1]}",
                "kind": "demand_item_scale",
                "target": item_id,
                "levels": [0.8, 0.9, 1.0, 1.1, 1.2],
                "realism_focus": "market_demand",
            }
        )

    for node_id in production_nodes:
        specs.append(
            {
                "parameter_key": f"capacity_node::{node_id}",
                "parameter_group": "capacity_node",
                "parameter_label": f"Capacite {node_id}",
                "kind": "capacity_node_scale",
                "target": node_id,
                "levels": [0.7, 0.85, 1.0, 1.15, 1.3],
                "realism_focus": "operations_capacity",
            }
        )

    for node_id in supplier_nodes:
        specs.extend(
            [
                {
                    "parameter_key": f"supplier_stock_node::{node_id}",
                    "parameter_group": "supplier_stock_node",
                    "parameter_label": f"Stock fournisseur {node_id}",
                    "kind": "supplier_node_scale",
                    "target": node_id,
                    "levels": [0.6, 0.8, 1.0, 1.2, 1.4],
                    "realism_focus": "supplier_buffer",
                },
                {
                    "parameter_key": f"supplier_capacity_node::{node_id}",
                    "parameter_group": "supplier_capacity_node",
                    "parameter_label": f"Debit fournisseur {node_id}",
                    "kind": "supplier_capacity_node_scale",
                    "target": node_id,
                    "levels": [0.6, 0.8, 1.0, 1.2, 1.4],
                    "realism_focus": "supplier_capacity",
                },
                {
                    "parameter_key": f"supplier_lead_time_node::{node_id}",
                    "parameter_group": "supplier_lead_time_node",
                    "parameter_label": f"Lead time fournisseur {node_id}",
                    "kind": "edge_src_lead_time_scale",
                    "target": node_id,
                    "levels": [0.7, 0.85, 1.0, 1.2, 1.5],
                    "realism_focus": "supplier_lead_time",
                },
                {
                    "parameter_key": f"supplier_reliability_node::{node_id}",
                    "parameter_group": "supplier_reliability_node",
                    "parameter_label": f"Fiabilite fournisseur {node_id}",
                    "kind": "edge_src_reliability_scale",
                    "target": node_id,
                    "levels": [0.85, 0.9, 0.95, 1.0],
                    "realism_focus": "supplier_reliability",
                },
            ]
        )
    return specs


def make_case_config(spec: dict[str, Any], level: float) -> dict[str, Any]:
    cfg = clone_case_config(base_case())
    kind = str(spec["kind"])
    target = str(spec["target"])
    if kind == "factor":
        cfg["factors"][target] = level
    elif kind == "demand_item_scale":
        cfg["demand_item_scale"][target] = level
    elif kind == "capacity_node_scale":
        cfg["capacity_node_scale"][target] = level
    elif kind == "supplier_node_scale":
        cfg["supplier_node_scale"][target] = level
    elif kind == "supplier_capacity_node_scale":
        cfg["supplier_capacity_node_scale"][target] = level
    elif kind == "edge_src_lead_time_scale":
        cfg["edge_src_lead_time_scale"][target] = level
    elif kind == "edge_src_reliability_scale":
        cfg["edge_src_reliability_scale"][target] = level
    elif kind == "scenario_scalar":
        cfg["scenario_scalars"][target] = level
    elif kind == "scenario_flag":
        cfg["scenario_flags"][target] = level >= 0.5
    else:
        raise ValueError(f"Unsupported parameter kind: {kind}")
    return cfg


def run_case(
    *,
    case_id: str,
    parameter_key: str,
    parameter_group: str,
    parameter_label: str,
    realism_focus: str,
    level: float,
    config: dict[str, Any],
    base_data: dict[str, Any],
    run_script: Path,
    scenario_id: str,
    days: int,
    cases_root: Path,
) -> dict[str, Any]:
    case_dir = cases_root / case_id
    case_input = case_dir / "input_case.json"
    case_output = case_dir / "simulation_output"
    case_dir.mkdir(parents=True, exist_ok=True)
    summary_path_candidates = [
        case_output / "summaries" / "first_simulation_summary.json",
        case_output / "first_simulation_summary.json",
    ]
    summary_file = next((path for path in summary_path_candidates if path.exists()), None)
    if summary_file is not None and case_input.exists():
        summary = load_json(summary_file)
    else:
        mutated = apply_scales(
            base_data=base_data,
            scenario_id=scenario_id,
            factors=config["factors"],
            demand_item_scale=config["demand_item_scale"],
            capacity_node_scale=config["capacity_node_scale"],
            supplier_node_scale=config["supplier_node_scale"],
            supplier_capacity_node_scale=config["supplier_capacity_node_scale"],
            edge_src_lead_time_scale=config["edge_src_lead_time_scale"],
            edge_src_reliability_scale=config["edge_src_reliability_scale"],
        )
        scn = choose_scenario(mutated, scenario_id)
        for key, value in config["scenario_scalars"].items():
            scn[str(key)] = round(max(0.0, to_float(value, 0.0)), 6)
        if config["scenario_flags"]:
            econ = scn.get("economic_policy")
            if not isinstance(econ, dict):
                econ = {}
            for key, value in config["scenario_flags"].items():
                econ[str(key)] = bool(value)
            scn["economic_policy"] = econ
        write_json(case_input, mutated)
        summary, _ = run_simulation(
            run_script=run_script,
            input_json=case_input,
            output_dir=case_output,
            scenario_id=scenario_id,
            days=days,
            skip_map=True,
            skip_plots=True,
        )
    row: dict[str, Any] = {
        "case_id": case_id,
        "parameter_key": parameter_key,
        "parameter_group": parameter_group,
        "parameter_label": parameter_label,
        "realism_focus": realism_focus,
        "level": level,
        "status": "ok",
        "case_input": str(case_input),
        "case_output_dir": str(case_output),
    }
    for key, value in numeric_kpis(summary).items():
        row[f"kpi::{key}"] = value
    return row


def sign_with_tol(value: float, tol: float = 1e-9) -> int:
    if value > tol:
        return 1
    if value < -tol:
        return -1
    return 0


def monotonicity(values: list[float]) -> str:
    if len(values) < 2:
        return "flat"
    signs = [sign_with_tol(b - a) for a, b in zip(values[:-1], values[1:])]
    non_zero = [s for s in signs if s != 0]
    if not non_zero:
        return "flat"
    if all(s >= 0 for s in non_zero):
        return "increasing"
    if all(s <= 0 for s in non_zero):
        return "decreasing"
    return "non_monotonic"


def first_crossing(
    rows: list[dict[str, Any]],
    metric_key: str,
    predicate,
) -> float | None:
    for row in rows:
        value = to_float(row.get(metric_key), math.nan)
        if math.isnan(value):
            continue
        if predicate(value):
            return to_float(row.get("level"), math.nan)
    return None


def safe_band(
    rows: list[dict[str, Any]],
    *,
    fill_key: str,
    cost_key: str,
    backlog_key: str,
    min_fill: float,
    max_cost: float,
    max_backlog: float,
) -> tuple[float | None, float | None]:
    safe_levels = []
    for row in rows:
        fill = to_float(row.get(fill_key), math.nan)
        cost = to_float(row.get(cost_key), math.nan)
        backlog = to_float(row.get(backlog_key), math.nan)
        if math.isnan(fill) or math.isnan(cost) or math.isnan(backlog):
            continue
        if fill >= min_fill and cost <= max_cost and backlog <= max_backlog:
            safe_levels.append(to_float(row.get("level"), math.nan))
    if not safe_levels:
        return None, None
    return min(safe_levels), max(safe_levels)


def summarize_parameter(
    spec: dict[str, Any],
    rows: list[dict[str, Any]],
    baseline_row: dict[str, Any],
    *,
    service_threshold: float,
    service_soft_threshold: float,
    backlog_increase_pct: float,
    cost_increase_pct: float,
) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: to_float(row.get("level"), 0.0))
    fill_key = "kpi::fill_rate"
    backlog_key = "kpi::ending_backlog"
    cost_key = "kpi::total_cost"
    ext_key = "kpi::total_external_procured_ordered_qty"
    inv_key = "kpi::avg_inventory"

    baseline_fill = to_float(baseline_row.get(fill_key), math.nan)
    baseline_backlog = to_float(baseline_row.get(backlog_key), math.nan)
    baseline_cost = to_float(baseline_row.get(cost_key), math.nan)

    fill_values = [to_float(row.get(fill_key), math.nan) for row in rows]
    backlog_values = [to_float(row.get(backlog_key), math.nan) for row in rows]
    cost_values = [to_float(row.get(cost_key), math.nan) for row in rows]
    fill_valid = [value for value in fill_values if not math.isnan(value)]
    backlog_valid = [value for value in backlog_values if not math.isnan(value)]
    cost_valid = [value for value in cost_values if not math.isnan(value)]
    external_valid = [
        value
        for value in (to_float(row.get(ext_key), math.nan) for row in rows)
        if not math.isnan(value)
    ]
    inventory_valid = [
        value
        for value in (to_float(row.get(inv_key), math.nan) for row in rows)
        if not math.isnan(value)
    ]

    fill_mono = monotonicity(fill_values)
    backlog_mono = monotonicity(backlog_values)
    cost_mono = monotonicity(cost_values)

    max_fill_drop = max(
        ((baseline_fill - value) for value in fill_valid),
        default=math.nan,
    )
    max_backlog_increase = max(
        ((value - baseline_backlog) for value in backlog_valid),
        default=math.nan,
    )
    max_cost_increase = max(
        ((value - baseline_cost) for value in cost_valid),
        default=math.nan,
    )

    fill_cross_90 = first_crossing(rows, fill_key, lambda value: value < service_threshold)
    fill_cross_soft = first_crossing(rows, fill_key, lambda value: value < service_soft_threshold)
    backlog_cross = first_crossing(
        rows,
        backlog_key,
        lambda value: value > baseline_backlog * (1.0 + backlog_increase_pct),
    )
    cost_cross = first_crossing(
        rows,
        cost_key,
        lambda value: value > baseline_cost * (1.0 + cost_increase_pct),
    )
    safe_low, safe_high = safe_band(
        rows,
        fill_key=fill_key,
        cost_key=cost_key,
        backlog_key=backlog_key,
        min_fill=service_threshold,
        max_cost=baseline_cost * (1.0 + cost_increase_pct),
        max_backlog=baseline_backlog * (1.0 + backlog_increase_pct),
    )

    steepest_fill_segment = None
    steepest_fill_slope = -1.0
    for prev_row, next_row in zip(rows[:-1], rows[1:]):
        x0 = to_float(prev_row.get("level"), math.nan)
        x1 = to_float(next_row.get("level"), math.nan)
        y0 = to_float(prev_row.get(fill_key), math.nan)
        y1 = to_float(next_row.get(fill_key), math.nan)
        if math.isnan(x0) or math.isnan(x1) or math.isnan(y0) or math.isnan(y1) or abs(x1 - x0) <= 1e-12:
            continue
        slope = abs((y1 - y0) / (x1 - x0))
        if slope > steepest_fill_slope:
            steepest_fill_slope = slope
            steepest_fill_segment = [x0, x1]

    baseline_external = to_float(baseline_row.get(ext_key), math.nan)
    baseline_inventory = to_float(baseline_row.get(inv_key), math.nan)
    min_fill = min(fill_valid, default=math.nan)
    max_fill = max(fill_valid, default=math.nan)
    min_cost = min(cost_valid, default=math.nan)
    max_cost = max(cost_valid, default=math.nan)
    min_backlog = min(backlog_valid, default=math.nan)
    max_backlog = max(backlog_valid, default=math.nan)
    max_external = max(external_valid, default=math.nan)
    min_external = min(external_valid, default=math.nan)
    max_inventory = max(inventory_valid, default=math.nan)
    min_inventory = min(inventory_valid, default=math.nan)

    return {
        "parameter_key": spec["parameter_key"],
        "parameter_group": spec["parameter_group"],
        "parameter_label": spec["parameter_label"],
        "realism_focus": spec["realism_focus"],
        "levels": spec["levels"],
        "baseline_fill_rate": baseline_fill,
        "baseline_backlog": baseline_backlog,
        "baseline_total_cost": baseline_cost,
        "baseline_external_procured_qty": baseline_external,
        "baseline_avg_inventory": baseline_inventory,
        "fill_rate_monotonicity": fill_mono,
        "ending_backlog_monotonicity": backlog_mono,
        "total_cost_monotonicity": cost_mono,
        "max_fill_rate_drop": max_fill_drop,
        "max_backlog_increase": max_backlog_increase,
        "max_total_cost_increase": max_cost_increase,
        "fill_rate_cross_service_threshold_at": fill_cross_90,
        "fill_rate_cross_soft_threshold_at": fill_cross_soft,
        "ending_backlog_cross_threshold_at": backlog_cross,
        "total_cost_cross_threshold_at": cost_cross,
        "safe_band_low": safe_low,
        "safe_band_high": safe_high,
        "steepest_fill_segment": steepest_fill_segment,
        "fill_rate_min": min_fill,
        "fill_rate_max": max_fill,
        "ending_backlog_min": min_backlog,
        "ending_backlog_max": max_backlog,
        "total_cost_min": min_cost,
        "total_cost_max": max_cost,
        "external_procured_qty_min": min_external,
        "external_procured_qty_max": max_external,
        "avg_inventory_min": min_inventory,
        "avg_inventory_max": max_inventory,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    cases_root = output_dir / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_root.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    demand_items = detect_demand_items(base_data, args.scenario_id)
    production_nodes = [
        node_id
        for node_id in detect_production_nodes(base_data)
        if node_id.startswith("M-")
    ]
    supplier_nodes_all = detect_supplier_nodes(base_data)

    print("[RUN] baseline threshold study", flush=True)
    baseline_row = run_case(
        case_id="baseline",
        parameter_key="baseline",
        parameter_group="baseline",
        parameter_label="Baseline",
        realism_focus="baseline",
        level=1.0,
        config=base_case(),
        base_data=base_data,
        run_script=run_script,
        scenario_id=args.scenario_id,
        days=args.days,
        cases_root=cases_root,
    )
    print("[RUN] baseline repeat", flush=True)
    baseline_repeat_row = run_case(
        case_id="baseline_repeat",
        parameter_key="baseline",
        parameter_group="baseline",
        parameter_label="Baseline repeat",
        realism_focus="baseline",
        level=1.0,
        config=base_case(),
        base_data=base_data,
        run_script=run_script,
        scenario_id=args.scenario_id,
        days=args.days,
        cases_root=cases_root,
    )

    baseline_shipments_csv = (
        cases_root / "baseline" / "simulation_output" / "data" / "production_supplier_shipments_daily.csv"
    )
    selected_suppliers = select_active_suppliers(
        baseline_shipments_csv,
        allowed_suppliers=set(supplier_nodes_all),
        top_n=args.top_suppliers,
    )
    specs = parameter_specs(demand_items, production_nodes, selected_suppliers)

    all_rows: list[dict[str, Any]] = [baseline_row, baseline_repeat_row]
    for spec_index, spec in enumerate(specs, start=1):
        levels = list(spec["levels"])
        total_levels = len(levels)
        for level_index, level in enumerate(levels, start=1):
            case_id = f"{safe_name(spec['parameter_key'])}_{safe_name(level)}"
            print(
                f"[RUN] {spec_index:02d}/{len(specs):02d} {spec['parameter_key']} "
                f"{level_index:02d}/{total_levels:02d} level={level}",
                flush=True,
            )
            cfg = make_case_config(spec, float(level))
            row = run_case(
                case_id=case_id,
                parameter_key=str(spec["parameter_key"]),
                parameter_group=str(spec["parameter_group"]),
                parameter_label=str(spec["parameter_label"]),
                realism_focus=str(spec["realism_focus"]),
                level=float(level),
                config=cfg,
                base_data=base_data,
                run_script=run_script,
                scenario_id=args.scenario_id,
                days=args.days,
                cases_root=cases_root,
            )
            all_rows.append(row)

    deterministic_diffs: dict[str, float] = {}
    kpi_keys = [
        "fill_rate",
        "ending_backlog",
        "total_cost",
        "total_external_procured_ordered_qty",
        "avg_inventory",
    ]
    max_abs_diff = 0.0
    for key in kpi_keys:
        base_value = to_float(baseline_row.get(f"kpi::{key}"), 0.0)
        repeat_value = to_float(baseline_repeat_row.get(f"kpi::{key}"), 0.0)
        diff = abs(repeat_value - base_value)
        deterministic_diffs[key] = diff
        max_abs_diff = max(max_abs_diff, diff)

    cases_csv = output_dir / "threshold_sweep_cases.csv"
    write_csv(cases_csv, all_rows)

    summary_rows = []
    by_parameter: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        parameter_key = str(row.get("parameter_key") or "")
        if parameter_key in {"", "baseline"}:
            continue
        by_parameter.setdefault(parameter_key, []).append(row)

    for spec in specs:
        rows = by_parameter.get(str(spec["parameter_key"]), [])
        if not rows:
            continue
        summary_rows.append(
            summarize_parameter(
                spec,
                rows,
                baseline_row,
                service_threshold=args.service_threshold,
                service_soft_threshold=args.service_soft_threshold,
                backlog_increase_pct=args.backlog_increase_pct,
                cost_increase_pct=args.cost_increase_pct,
            )
        )

    summary_rows.sort(
        key=lambda row: (
            to_float(row.get("fill_rate_cross_service_threshold_at"), 999.0),
            -to_float(row.get("max_fill_rate_drop"), 0.0),
            str(row.get("parameter_label")),
        )
    )

    summary_csv = output_dir / "parameter_threshold_summary.csv"
    write_csv(summary_csv, summary_rows)

    critical_by_service = [
        {
            "parameter_label": row["parameter_label"],
            "parameter_key": row["parameter_key"],
            "cross_at": row["fill_rate_cross_service_threshold_at"],
            "safe_band_low": row["safe_band_low"],
            "safe_band_high": row["safe_band_high"],
            "max_fill_rate_drop": row["max_fill_rate_drop"],
        }
        for row in summary_rows
        if row.get("fill_rate_cross_service_threshold_at") is not None
    ][:10]
    strongest_fill_effects = sorted(
        summary_rows,
        key=lambda row: -to_float(row.get("max_fill_rate_drop"), 0.0),
    )[:10]
    strongest_cost_effects = sorted(
        summary_rows,
        key=lambda row: -to_float(row.get("max_total_cost_increase"), 0.0),
    )[:10]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days": args.days,
        "service_threshold": args.service_threshold,
        "service_soft_threshold": args.service_soft_threshold,
        "backlog_increase_pct": args.backlog_increase_pct,
        "cost_increase_pct": args.cost_increase_pct,
        "selected_suppliers": selected_suppliers,
        "baseline": baseline_row,
        "deterministic_check": {
            "status": "pass" if max_abs_diff <= 1e-9 else "warn",
            "max_abs_diff": max_abs_diff,
            "abs_diff_by_kpi": deterministic_diffs,
        },
        "parameter_count": len(specs),
        "simulation_count": len(all_rows),
        "critical_by_service_threshold": critical_by_service,
        "strongest_fill_effects": strongest_fill_effects,
        "strongest_cost_effects": strongest_cost_effects,
    }
    summary_json = output_dir / "threshold_sensitivity_summary.json"
    write_json(summary_json, summary)

    report_lines = [
        "# Threshold-Oriented Sensitivity Study",
        "",
        "## Method",
        f"- Horizon: {args.days} days",
        f"- Scenario: {args.scenario_id}",
        "- Design: deterministic one-factor-at-a-time, multi-level sweeps",
        f"- Service threshold: {args.service_threshold:.3f}",
        f"- Soft service threshold: {args.service_soft_threshold:.3f}",
        f"- Backlog alert threshold: +{args.backlog_increase_pct * 100:.1f}% vs baseline",
        f"- Cost alert threshold: +{args.cost_increase_pct * 100:.1f}% vs baseline",
        f"- Active suppliers screened individually: {', '.join(selected_suppliers) if selected_suppliers else '(none)'}",
        "",
        "## Baseline",
        f"- Fill rate: {to_float(baseline_row.get('kpi::fill_rate'), math.nan):.6f}",
        f"- Ending backlog: {to_float(baseline_row.get('kpi::ending_backlog'), math.nan):.4f}",
        f"- Total cost: {to_float(baseline_row.get('kpi::total_cost'), math.nan):.4f}",
        f"- External procured qty: {to_float(baseline_row.get('kpi::total_external_procured_ordered_qty'), math.nan):.4f}",
        f"- Avg inventory: {to_float(baseline_row.get('kpi::avg_inventory'), math.nan):.4f}",
        "",
        "## Most Critical For Service Threshold",
    ]
    if critical_by_service:
        for row in critical_by_service:
            report_lines.append(
                f"- {row['parameter_label']}: cross<{args.service_threshold:.2f} at level "
                f"{row['cross_at']}, safe band [{row['safe_band_low']}, {row['safe_band_high']}], "
                f"max fill drop {to_float(row['max_fill_rate_drop'], 0.0):.4f}"
            )
    else:
        report_lines.append(f"- No parameter crossed the service threshold {args.service_threshold:.2f}.")

    report_lines.extend(["", "## Strongest Fill-Rate Effects"])
    for row in strongest_fill_effects:
        report_lines.append(
            f"- {row['parameter_label']}: max fill drop {to_float(row['max_fill_rate_drop'], 0.0):.4f}, "
            f"monotonicity={row['fill_rate_monotonicity']}, steepest segment={row['steepest_fill_segment']}"
        )

    report_lines.extend(["", "## Strongest Cost Effects"])
    for row in strongest_cost_effects:
        report_lines.append(
            f"- {row['parameter_label']}: max total-cost increase "
            f"{to_float(row['max_total_cost_increase'], 0.0):.2f}, monotonicity={row['total_cost_monotonicity']}"
        )

    report_lines.extend(
        [
            "",
            "## Files",
            "- threshold_sweep_cases.csv",
            "- parameter_threshold_summary.csv",
            "- threshold_sensitivity_summary.json",
        ]
    )
    report_md = output_dir / "threshold_sensitivity_report.md"
    report_md.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"[OK] Cases CSV: {cases_csv.resolve()}", flush=True)
    print(f"[OK] Summary CSV: {summary_csv.resolve()}", flush=True)
    print(f"[OK] Summary JSON: {summary_json.resolve()}", flush=True)
    print(f"[OK] Report MD: {report_md.resolve()}", flush=True)


if __name__ == "__main__":
    main()
