#!/usr/bin/env python3
"""
Run a more realistic annual sensitivity study:
- local calibrated sensitivity around the baseline
- adverse stress tests kept separate from local elasticities
"""

from __future__ import annotations

import argparse
import csv
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
from etudecas.simulation.sensibility.case_naming import realistic_case_id  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a realistic annual sensitivity study.")
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
        default="etudecas/simulation/sensibility/annual_realistic_result",
        help="Output directory for the realistic sensitivity study.",
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
        default=8,
        help="Number of active suppliers kept for node-level sensitivity.",
    )
    parser.add_argument(
        "--artifact-mode",
        choices=["compact", "full"],
        default="compact",
        help="Artifact retention mode. 'compact' prunes per-case simulation data/maps/plots after KPI extraction.",
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
    ordered = sorted(
        shipped_qty_by_supplier.items(),
        key=lambda it: (-it[1], it[0]),
    )
    selected = [supplier for supplier, qty in ordered if qty > 1e-9][:top_n]
    if not selected:
        selected = sorted(allowed_suppliers)[:top_n]
    return selected


def make_case(
    *,
    study: str,
    parameter_key: str,
    parameter_group: str,
    parameter_label: str,
    direction: str,
    factor_value: float,
    config: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    case_id = realistic_case_id(study=study, parameter_key=parameter_key, direction=direction)
    return {
        "study": study,
        "case_id": case_id,
        "parameter_key": parameter_key,
        "parameter_group": parameter_group,
        "parameter_label": parameter_label,
        "direction": direction,
        "factor_value": factor_value,
        "config": config,
        "notes": notes,
    }


def build_local_cases(
    demand_items: list[str],
    production_nodes: list[str],
    supplier_nodes: list[str],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    local_global_levels = {
        "lead_time_scale": (0.9, 1.1, "lead_time", "Lead time global"),
        "transport_cost_scale": (0.9, 1.1, "transport_cost", "Cout transport global"),
        "supplier_stock_scale": (0.9, 1.1, "supplier_stock", "Stock fournisseur global"),
        "production_stock_scale": (0.9, 1.1, "production_stock", "Stock production global"),
        "capacity_scale": (0.95, 1.05, "capacity_global", "Capacite globale"),
        "supplier_capacity_scale": (0.95, 1.05, "supplier_capacity_global", "Debit fournisseur global"),
        "safety_stock_days_scale": (0.9, 1.1, "safety_stock", "Safety stock global"),
    }
    for factor_name, (low, high, group, label) in local_global_levels.items():
        for direction, value in (("low", low), ("high", high)):
            cfg = clone_case_config(base_case())
            cfg["factors"][factor_name] = value
            cases.append(
                make_case(
                    study="local",
                    parameter_key=factor_name,
                    parameter_group=group,
                    parameter_label=label,
                    direction=direction,
                    factor_value=value,
                    config=cfg,
                )
            )

    # Reliability is bounded by 1.0, so use an adverse local semi-elasticity only.
    for factor_name, value, group, label in [
        ("supplier_reliability_scale", 0.95, "supplier_reliability_global", "Fiabilite fournisseur globale"),
    ]:
        cfg = clone_case_config(base_case())
        cfg["factors"][factor_name] = value
        cases.append(
            make_case(
                study="local",
                parameter_key=factor_name,
                parameter_group=group,
                parameter_label=label,
                direction="adverse",
                factor_value=value,
                config=cfg,
                notes="One-sided local sensitivity because reliability is upper bounded.",
            )
        )

    for item_id in demand_items:
        for direction, value in (("low", 0.9), ("high", 1.1)):
            cfg = clone_case_config(base_case())
            cfg["demand_item_scale"][item_id] = value
            cases.append(
                make_case(
                    study="local",
                    parameter_key=f"demand_item::{item_id}",
                    parameter_group="demand_item",
                    parameter_label=f"Demande {item_id.split(':', 1)[-1]}",
                    direction=direction,
                    factor_value=value,
                    config=cfg,
                )
            )

    for node_id in production_nodes:
        for direction, value in (("low", 0.95), ("high", 1.05)):
            cfg = clone_case_config(base_case())
            cfg["capacity_node_scale"][node_id] = value
            cases.append(
                make_case(
                    study="local",
                    parameter_key=f"capacity_node::{node_id}",
                    parameter_group="capacity_node",
                    parameter_label=f"Capacite {node_id}",
                    direction=direction,
                    factor_value=value,
                    config=cfg,
                )
            )

    for node_id in supplier_nodes:
        supplier_specs = [
            ("supplier_node_scale", 0.9, 1.1, "supplier_stock_node", "Stock fournisseur"),
            ("supplier_capacity_node_scale", 0.9, 1.1, "supplier_capacity_node", "Debit fournisseur"),
            ("edge_src_lead_time_scale", 0.9, 1.1, "supplier_lead_time_node", "Lead time fournisseur"),
        ]
        for dict_name, low, high, group, label in supplier_specs:
            for direction, value in (("low", low), ("high", high)):
                cfg = clone_case_config(base_case())
                cfg[dict_name][node_id] = value
                cases.append(
                    make_case(
                        study="local",
                        parameter_key=f"{group}::{node_id}",
                        parameter_group=group,
                        parameter_label=f"{label} {node_id}",
                        direction=direction,
                        factor_value=value,
                        config=cfg,
                    )
                )

        cfg = clone_case_config(base_case())
        cfg["edge_src_reliability_scale"][node_id] = 0.95
        cases.append(
            make_case(
                study="local",
                parameter_key=f"supplier_reliability_node::{node_id}",
                parameter_group="supplier_reliability_node",
                parameter_label=f"Fiabilite fournisseur {node_id}",
                direction="adverse",
                factor_value=0.95,
                config=cfg,
                notes="One-sided local sensitivity because reliability is upper bounded.",
            )
        )
    return cases


def build_stress_cases(
    demand_items: list[str],
    production_nodes: list[str],
    supplier_nodes: list[str],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    stress_global_specs = [
        ("lead_time_scale", 1.25, "lead_time", "Lead time global"),
        ("transport_cost_scale", 1.25, "transport_cost", "Cout transport global"),
        ("supplier_stock_scale", 0.8, "supplier_stock", "Stock fournisseur global"),
        ("production_stock_scale", 0.8, "production_stock", "Stock production global"),
        ("supplier_capacity_scale", 0.8, "supplier_capacity_global", "Debit fournisseur global"),
        ("supplier_reliability_scale", 0.9, "supplier_reliability_global", "Fiabilite fournisseur globale"),
        ("safety_stock_days_scale", 0.8, "safety_stock", "Safety stock global"),
    ]
    for factor_name, value, group, label in stress_global_specs:
        cfg = clone_case_config(base_case())
        cfg["factors"][factor_name] = value
        cases.append(
            make_case(
                study="stress",
                parameter_key=factor_name,
                parameter_group=group,
                parameter_label=label,
                direction="stress",
                factor_value=value,
                config=cfg,
            )
        )

    for item_id in demand_items:
        cfg = clone_case_config(base_case())
        cfg["demand_item_scale"][item_id] = 1.2
        cases.append(
            make_case(
                study="stress",
                parameter_key=f"demand_item::{item_id}",
                parameter_group="demand_item",
                parameter_label=f"Demande {item_id.split(':', 1)[-1]}",
                direction="stress",
                factor_value=1.2,
                config=cfg,
            )
        )

    for node_id in production_nodes:
        cfg = clone_case_config(base_case())
        cfg["capacity_node_scale"][node_id] = 0.85
        cases.append(
            make_case(
                study="stress",
                parameter_key=f"capacity_node::{node_id}",
                parameter_group="capacity_node",
                parameter_label=f"Capacite {node_id}",
                direction="stress",
                factor_value=0.85,
                config=cfg,
            )
        )

    for node_id in supplier_nodes:
        supplier_stress_specs = [
            ("supplier_node_scale", 0.75, "supplier_stock_node", "Stock fournisseur"),
            ("supplier_capacity_node_scale", 0.75, "supplier_capacity_node", "Debit fournisseur"),
            ("edge_src_lead_time_scale", 1.5, "supplier_lead_time_node", "Lead time fournisseur"),
            ("edge_src_reliability_scale", 0.85, "supplier_reliability_node", "Fiabilite fournisseur"),
        ]
        for dict_name, value, group, label in supplier_stress_specs:
            cfg = clone_case_config(base_case())
            cfg[dict_name][node_id] = value
            cases.append(
                make_case(
                    study="stress",
                    parameter_key=f"{group}::{node_id}",
                    parameter_group=group,
                    parameter_label=f"{label} {node_id}",
                    direction="stress",
                    factor_value=value,
                    config=cfg,
                )
            )
    return cases


def run_case(
    *,
    case: dict[str, Any],
    base_data: dict[str, Any],
    input_root: Path,
    output_root: Path,
    run_script: Path,
    scenario_id: str,
    days: int,
) -> dict[str, Any]:
    case_dir = output_root / case["study"] / case["case_id"]
    case_input = case_dir / "input_case.json"
    case_output = case_dir / "simulation_output"
    case_dir.mkdir(parents=True, exist_ok=True)
    mutated = apply_scales(
        base_data=base_data,
        scenario_id=scenario_id,
        factors=case["config"]["factors"],
        demand_item_scale=case["config"]["demand_item_scale"],
        capacity_node_scale=case["config"]["capacity_node_scale"],
        supplier_node_scale=case["config"]["supplier_node_scale"],
        supplier_capacity_node_scale=case["config"]["supplier_capacity_node_scale"],
        edge_src_lead_time_scale=case["config"]["edge_src_lead_time_scale"],
        edge_src_reliability_scale=case["config"]["edge_src_reliability_scale"],
    )
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
        "study": case["study"],
        "case_id": case["case_id"],
        "parameter_key": case["parameter_key"],
        "parameter_group": case["parameter_group"],
        "parameter_label": case["parameter_label"],
        "direction": case["direction"],
        "factor_value": case["factor_value"],
        "notes": case.get("notes", ""),
        "case_input": str(case_input),
        "case_output_dir": str(case_output),
        "status": "ok",
    }
    for key, value in numeric_kpis(summary).items():
        row[f"kpi::{key}"] = value
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compute_local_elasticities(
    baseline: dict[str, Any],
    local_rows: list[dict[str, Any]],
    kpi_keys: list[str],
) -> list[dict[str, Any]]:
    by_parameter: dict[str, list[dict[str, Any]]] = {}
    for row in local_rows:
        by_parameter.setdefault(str(row["parameter_key"]), []).append(row)

    elasticity_rows: list[dict[str, Any]] = []
    for parameter_key, rows in sorted(by_parameter.items()):
        meta = rows[0]
        low_row = next((row for row in rows if row.get("direction") == "low"), None)
        high_row = next((row for row in rows if row.get("direction") == "high"), None)
        adverse_row = next((row for row in rows if row.get("direction") == "adverse"), None)
        for kpi_key in kpi_keys:
            baseline_value = to_float(baseline.get(f"kpi::{kpi_key}"), math.nan)
            if math.isnan(baseline_value):
                continue

            method = ""
            elasticity = math.nan
            low_value = to_float(low_row.get(f"kpi::{kpi_key}"), math.nan) if low_row else math.nan
            high_value = to_float(high_row.get(f"kpi::{kpi_key}"), math.nan) if high_row else math.nan
            adverse_value = to_float(adverse_row.get(f"kpi::{kpi_key}"), math.nan) if adverse_row else math.nan
            if low_row and high_row:
                x_low = to_float(low_row.get("factor_value"), 1.0)
                x_high = to_float(high_row.get("factor_value"), 1.0)
                dx_rel = x_high - x_low
                dy_rel = ((high_value - low_value) / baseline_value) if abs(baseline_value) > 1e-12 else math.nan
                if abs(dx_rel) > 1e-12 and not math.isnan(dy_rel):
                    elasticity = dy_rel / dx_rel
                    method = "central"
            elif adverse_row:
                x = to_float(adverse_row.get("factor_value"), 1.0)
                dx_rel = x - 1.0
                dy_rel = ((adverse_value - baseline_value) / baseline_value) if abs(baseline_value) > 1e-12 else math.nan
                if abs(dx_rel) > 1e-12 and not math.isnan(dy_rel):
                    elasticity = dy_rel / dx_rel
                    method = "one_sided_adverse"

            row = {
                "parameter_key": parameter_key,
                "parameter_group": meta["parameter_group"],
                "parameter_label": meta["parameter_label"],
                "kpi": kpi_key,
                "method": method,
                "baseline_kpi": baseline_value,
                "low_kpi": low_value,
                "high_kpi": high_value,
                "adverse_kpi": adverse_value,
                "elasticity": elasticity,
                "abs_elasticity": abs(elasticity) if not math.isnan(elasticity) else math.nan,
            }
            elasticity_rows.append(row)
    return elasticity_rows


def compute_stress_impacts(
    baseline: dict[str, Any],
    stress_rows: list[dict[str, Any]],
    kpi_keys: list[str],
) -> list[dict[str, Any]]:
    impact_rows: list[dict[str, Any]] = []
    for row in stress_rows:
        impact_row = dict(row)
        for kpi_key in kpi_keys:
            base = to_float(baseline.get(f"kpi::{kpi_key}"), math.nan)
            value = to_float(row.get(f"kpi::{kpi_key}"), math.nan)
            impact_row[f"baseline::{kpi_key}"] = base
            impact_row[f"delta::{kpi_key}"] = value - base if not (math.isnan(base) or math.isnan(value)) else math.nan
            if not math.isnan(base) and abs(base) > 1e-12 and not math.isnan(value):
                impact_row[f"delta_pct::{kpi_key}"] = ((value - base) / base) * 100.0
            else:
                impact_row[f"delta_pct::{kpi_key}"] = math.nan
        impact_rows.append(impact_row)
    return impact_rows


def top_local(elasticity_rows: list[dict[str, Any]], kpi: str, n: int = 10) -> list[dict[str, Any]]:
    rows = [row for row in elasticity_rows if row["kpi"] == kpi and not math.isnan(to_float(row["abs_elasticity"], math.nan))]
    rows.sort(key=lambda row: (-to_float(row["abs_elasticity"], 0.0), str(row["parameter_label"])))
    return rows[:n]


def top_stress(impact_rows: list[dict[str, Any]], kpi: str, adverse: str, n: int = 10) -> list[dict[str, Any]]:
    key = f"delta::{kpi}"
    rows = [row for row in impact_rows if not math.isnan(to_float(row.get(key), math.nan))]
    if adverse == "min":
        rows.sort(key=lambda row: (to_float(row.get(key), 0.0), str(row["parameter_label"])))
    else:
        rows.sort(key=lambda row: (-to_float(row.get(key), 0.0), str(row["parameter_label"])))
    return rows[:n]


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    output_dir = Path(args.output_dir)
    cases_root = output_dir / "cases"
    keep_detailed_cases = set(args.keep_detailed_case or [])
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_root.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    demand_items = detect_demand_items(base_data, args.scenario_id)
    production_nodes = detect_production_nodes(base_data)
    supplier_nodes = detect_supplier_nodes(base_data)

    baseline_case = make_case(
        study="baseline",
        parameter_key="baseline",
        parameter_group="baseline",
        parameter_label="Baseline annuelle",
        direction="base",
        factor_value=1.0,
        config=base_case(),
    )
    baseline_repeat_case = make_case(
        study="baseline",
        parameter_key="baseline",
        parameter_group="baseline",
        parameter_label="Baseline annuelle repeat",
        direction="repeat",
        factor_value=1.0,
        config=base_case(),
    )

    print("[RUN] baseline annual")
    baseline_row = run_case(
        case=baseline_case,
        base_data=base_data,
        input_root=output_dir,
        output_root=cases_root,
        run_script=run_script,
        scenario_id=args.scenario_id,
        days=args.days,
    )
    print("[RUN] baseline annual repeat")
    baseline_repeat_row = run_case(
        case=baseline_repeat_case,
        base_data=base_data,
        input_root=output_dir,
        output_root=cases_root,
        run_script=run_script,
        scenario_id=args.scenario_id,
        days=args.days,
    )

    baseline_shipments_csv = cases_root / "baseline" / baseline_case["case_id"] / "simulation_output" / "data" / "production_supplier_shipments_daily.csv"
    selected_suppliers = select_active_suppliers(
        baseline_shipments_csv,
        allowed_suppliers=set(supplier_nodes),
        top_n=args.top_suppliers,
    )
    local_cases = build_local_cases(demand_items, production_nodes, selected_suppliers)
    stress_cases = build_stress_cases(demand_items, production_nodes, selected_suppliers)

    local_rows: list[dict[str, Any]] = []
    for idx, case in enumerate(local_cases, start=1):
        print(f"[RUN] local {idx:02d}/{len(local_cases):02d} {case['case_id']}")
        row = run_case(
            case=case,
            base_data=base_data,
            input_root=output_dir,
            output_root=cases_root,
            run_script=run_script,
            scenario_id=args.scenario_id,
            days=args.days,
        )
        local_rows.append(row)
        if args.artifact_mode == "compact" and case["case_id"] not in keep_detailed_cases:
            prune_simulation_output(cases_root / case["study"] / case["case_id"] / "simulation_output")

    stress_rows: list[dict[str, Any]] = []
    for idx, case in enumerate(stress_cases, start=1):
        print(f"[RUN] stress {idx:02d}/{len(stress_cases):02d} {case['case_id']}")
        row = run_case(
            case=case,
            base_data=base_data,
            input_root=output_dir,
            output_root=cases_root,
            run_script=run_script,
            scenario_id=args.scenario_id,
            days=args.days,
        )
        stress_rows.append(row)
        if args.artifact_mode == "compact" and case["case_id"] not in keep_detailed_cases:
            prune_simulation_output(cases_root / case["study"] / case["case_id"] / "simulation_output")

    kpi_keys = [
        "fill_rate",
        "ending_backlog",
        "total_cost",
        "total_external_procured_ordered_qty",
        "avg_inventory",
    ]
    elasticity_rows = compute_local_elasticities(baseline_row, local_rows, kpi_keys)
    stress_impact_rows = compute_stress_impacts(baseline_row, stress_rows, kpi_keys)

    deterministic_diffs: dict[str, float] = {}
    max_abs_diff = 0.0
    for key in kpi_keys:
        base_value = to_float(baseline_row.get(f"kpi::{key}"), 0.0)
        repeat_value = to_float(baseline_repeat_row.get(f"kpi::{key}"), 0.0)
        diff = abs(repeat_value - base_value)
        deterministic_diffs[key] = diff
        max_abs_diff = max(max_abs_diff, diff)

    local_cases_csv = output_dir / "local_cases.csv"
    stress_cases_csv = output_dir / "stress_cases.csv"
    elasticity_csv = output_dir / "local_elasticities.csv"
    stress_impact_csv = output_dir / "stress_impacts.csv"
    write_csv(local_cases_csv, [baseline_row, baseline_repeat_row] + local_rows)
    write_csv(stress_cases_csv, [baseline_row] + stress_rows)
    write_csv(elasticity_csv, elasticity_rows)
    write_csv(stress_impact_csv, stress_impact_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days": args.days,
        "artifact_mode": args.artifact_mode,
        "selected_suppliers": selected_suppliers,
        "baseline": {key: to_float(baseline_row.get(f"kpi::{key}"), math.nan) for key in kpi_keys},
        "deterministic_check": {
            "status": "pass" if max_abs_diff <= 1e-9 else "warn",
            "max_abs_diff": max_abs_diff,
            "abs_diff_by_kpi": deterministic_diffs,
        },
        "methodology": {
            "local": "small calibrated perturbations around baseline; central elasticities where possible, one-sided adverse semi-elasticity for bounded reliability",
            "stress": "plausible adverse changes kept separate from local elasticities",
            "supplier_scope": "top active suppliers in annual baseline",
        },
        "top_local_fill_rate": top_local(elasticity_rows, "fill_rate"),
        "top_local_ending_backlog": top_local(elasticity_rows, "ending_backlog"),
        "top_local_total_cost": top_local(elasticity_rows, "total_cost"),
        "top_stress_fill_rate_drop": top_stress(stress_impact_rows, "fill_rate", "min"),
        "top_stress_backlog_increase": top_stress(stress_impact_rows, "ending_backlog", "max"),
        "top_stress_cost_increase": top_stress(stress_impact_rows, "total_cost", "max"),
    }
    summary_path = output_dir / "realistic_sensitivity_summary.json"
    write_json(summary_path, summary)

    report = f"""# Realistic Annual Sensitivity Study

## Method
- Horizon: {args.days} days
- Baseline: annual simulation current setup
- Local sensitivity: calibrated perturbations around baseline
- Stress tests: adverse scenarios separated from local elasticities
- Supplier scope: {len(selected_suppliers)} active suppliers -> {", ".join(selected_suppliers) if selected_suppliers else "none"}
- Artifact mode: {args.artifact_mode}

## Baseline
- Fill rate: {summary['baseline']['fill_rate']}
- Ending backlog: {summary['baseline']['ending_backlog']}
- Total cost: {summary['baseline']['total_cost']}
- External procured qty: {summary['baseline']['total_external_procured_ordered_qty']}
- Avg inventory: {summary['baseline']['avg_inventory']}

## Deterministic Check
- Status: {summary['deterministic_check']['status']}
- Max absolute KPI diff baseline vs repeat: {summary['deterministic_check']['max_abs_diff']}

## Top Local Elasticities

### Fill rate
{chr(10).join(f"- {row['parameter_label']}: elasticity={row['elasticity']}" for row in summary['top_local_fill_rate'])}

### Ending backlog
{chr(10).join(f"- {row['parameter_label']}: elasticity={row['elasticity']}" for row in summary['top_local_ending_backlog'])}

### Total cost
{chr(10).join(f"- {row['parameter_label']}: elasticity={row['elasticity']}" for row in summary['top_local_total_cost'])}

## Top Stress Impacts

### Fill rate drops
{chr(10).join(f"- {row['parameter_label']}: delta_fill_rate={row['delta::fill_rate']}" for row in summary['top_stress_fill_rate_drop'])}

### Backlog increases
{chr(10).join(f"- {row['parameter_label']}: delta_backlog={row['delta::ending_backlog']}" for row in summary['top_stress_backlog_increase'])}

### Cost increases
{chr(10).join(f"- {row['parameter_label']}: delta_cost={row['delta::total_cost']}" for row in summary['top_stress_cost_increase'])}

## Files
- local_cases.csv
- stress_cases.csv
- local_elasticities.csv
- stress_impacts.csv
- realistic_sensitivity_summary.json
"""
    report_path = output_dir / "realistic_sensitivity_report.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] Local cases CSV: {local_cases_csv}")
    print(f"[OK] Stress cases CSV: {stress_cases_csv}")
    print(f"[OK] Local elasticities CSV: {elasticity_csv}")
    print(f"[OK] Stress impacts CSV: {stress_impact_csv}")
    print(f"[OK] Summary JSON: {summary_path}")
    print(f"[OK] Report MD: {report_path}")


if __name__ == "__main__":
    main()
