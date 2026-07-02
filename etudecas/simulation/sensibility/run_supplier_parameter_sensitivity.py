#!/usr/bin/env python3
"""
Run supplier-parameter sensitivity against the exact active baseline setup.

This runner is deliberately narrower than the generic threshold study:
- it keeps the simulator options from a baseline run_manifest when provided;
- it focuses on supplier stock, supplier capacity, supplier lead time and reliability;
- it evaluates guardrails against the baseline itself instead of dropping startup days.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SERVICE_KPI_TOLERANCE = 0.001
COUNT_KPI_TOLERANCE = 1.0
REQUIRED_DERIVED_KPI_COLUMNS = [
    "kpi::product_availability",
    "kpi::line_adherence",
    "kpi::line_nervousness",
    "kpi::production_replanning_count",
    "kpi::raw_material_stockout_days",
    "kpi::material_delay_days",
    "kpi::inventory_cost",
]

from etudecas.simulation.analysis_batch_common import (  # noqa: E402
    apply_scales,
    choose_scenario,
    detect_demand_items,
    load_json,
    numeric_kpis,
    safe_name,
    to_float,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run supplier-parameter sensitivity.")
    parser.add_argument(
        "--input",
        default="etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json",
        help="Simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--run-script",
        default="etudecas/simulation/engine/run_first_simulation.py",
        help="Simulation runner script.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id.")
    parser.add_argument("--days", type=int, default=1825, help="Simulation horizon.")
    parser.add_argument(
        "--baseline-manifest",
        default="etudecas/simulation/result/mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test/run_manifest.json",
        help="Optional baseline run_manifest.json. Extra simulator options are reused.",
    )
    parser.add_argument(
        "--baseline-result-dir",
        default="etudecas/simulation/result/mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test",
        help="Baseline result directory used to rank suppliers and compare guardrails.",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/sensibility/active_supplier_parameter_result",
        help="Output directory for the supplier sensitivity study.",
    )
    parser.add_argument(
        "--top-suppliers",
        type=int,
        default=0,
        help="Number of active suppliers to sweep. 0 means all active suppliers.",
    )
    parser.add_argument(
        "--groups",
        default="stock,capacity,lead_time,reliability,external,combined",
        help="Comma-separated groups: stock,capacity,lead_time,reliability,external,combined.",
    )
    parser.add_argument(
        "--stock-levels",
        default="0.25,0.5,0.75,1.0",
        help="Supplier opening stock scale levels.",
    )
    parser.add_argument(
        "--capacity-levels",
        default="0.5,0.6,0.75,0.9,1.0",
        help="Supplier capacity scale levels.",
    )
    parser.add_argument(
        "--lead-time-levels",
        default="1.0,1.25,1.5,2.0",
        help="Supplier planned lead-time scale levels.",
    )
    parser.add_argument(
        "--reliability-levels",
        default="0.95,0.97,0.99,1.0",
        help="Supplier reliability scale levels.",
    )
    parser.add_argument(
        "--external-capacity-levels",
        default="0.25,0.5,0.75,1.0",
        help="Supplier upstream supply daily-capacity scale levels.",
    )
    parser.add_argument(
        "--external-lead-levels",
        default="1.0,1.25,1.5,2.0",
        help="Supplier upstream supply lead-time scale levels.",
    )
    parser.add_argument(
        "--service-threshold",
        type=float,
        default=0.999999,
        help="Minimum fill rate accepted for a case.",
    )
    parser.add_argument(
        "--cost-increase-pct",
        type=float,
        default=0.10,
        help="Cost increase warning threshold vs baseline.",
    )
    parser.add_argument(
        "--artifact-mode",
        choices=["summary", "compact", "full"],
        default="summary",
        help=(
            "Retention mode for each case. summary keeps only reports/summaries and small diagnostic CSVs; "
            "compact keeps selected operational CSVs; full keeps the complete simulation_output."
        ),
    )
    parser.add_argument(
        "--keep-case-data",
        action="store_true",
        help="Legacy alias for --artifact-mode full.",
    )
    parser.add_argument(
        "--summarize-existing",
        action="store_true",
        help="Rebuild summary/report files from an existing supplier_parameter_sensitivity_cases.csv without rerunning cases.",
    )
    parser.add_argument(
        "--combined-capacity-level",
        type=float,
        default=0.75,
        help="Supplier capacity level for combined capacity+delay scenarios.",
    )
    parser.add_argument(
        "--combined-stock-level",
        type=float,
        default=0.50,
        help="Supplier stock level for combined stock+reliability scenarios.",
    )
    parser.add_argument(
        "--combined-lead-time-level",
        type=float,
        default=1.25,
        help="Supplier lead-time level for combined capacity+delay scenarios.",
    )
    parser.add_argument(
        "--combined-reliability-level",
        type=float,
        default=0.97,
        help="Supplier reliability level for combined stock+reliability scenarios.",
    )
    parser.add_argument(
        "--combined-upstream-capacity-level",
        type=float,
        default=0.75,
        help="Supplier upstream supply capacity level for combined upstream scenarios.",
    )
    parser.add_argument(
        "--combined-upstream-lead-level",
        type=float,
        default=1.25,
        help="Supplier upstream supply lead-time level for combined upstream scenarios.",
    )
    return parser.parse_args()


def parse_levels(text: str) -> list[float]:
    out: list[float] = []
    for part in str(text or "").split(","):
        part = part.strip()
        if not part:
            continue
        value = float(part)
        if value <= 0:
            raise ValueError(f"Levels must be > 0, got {value}")
        out.append(value)
    return sorted(set(out))


def selected_groups(text: str) -> set[str]:
    return {part.strip().lower() for part in str(text or "").split(",") if part.strip()}


def base_case() -> dict[str, Any]:
    return {
        "factors": {
            "lead_time_scale": 1.0,
            "supplier_stock_scale": 1.0,
            "supplier_capacity_scale": 1.0,
            "supplier_reliability_scale": 1.0,
            "external_procurement_daily_cap_days_scale": 1.0,
            "external_procurement_lead_days_scale": 1.0,
        },
        "demand_item_scale": {},
        "capacity_node_scale": {},
        "supplier_node_scale": {},
        "supplier_capacity_node_scale": {},
        "edge_src_lead_time_scale": {},
        "edge_src_reliability_scale": {},
        "scenario_flags": {},
    }


def clone_case_config(cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "factors": dict(cfg["factors"]),
        "demand_item_scale": dict(cfg["demand_item_scale"]),
        "capacity_node_scale": dict(cfg["capacity_node_scale"]),
        "supplier_node_scale": dict(cfg["supplier_node_scale"]),
        "supplier_capacity_node_scale": dict(cfg["supplier_capacity_node_scale"]),
        "edge_src_lead_time_scale": dict(cfg["edge_src_lead_time_scale"]),
        "edge_src_reliability_scale": dict(cfg["edge_src_reliability_scale"]),
        "scenario_flags": dict(cfg["scenario_flags"]),
    }


def detect_supplier_nodes(data: dict[str, Any]) -> list[str]:
    outgoing_sources = {
        str(edge.get("from"))
        for edge in (data.get("edges") or [])
        if edge.get("from") is not None
    }
    out = []
    for node in data.get("nodes", []) or []:
        node_id = str(node.get("id"))
        if str(node.get("type") or "") == "supplier_dc" and node_id in outgoing_sources:
            out.append(node_id)
    return sorted(set(out))


def rank_suppliers(baseline_result_dir: Path, allowed_suppliers: set[str]) -> list[str]:
    shipped_by_supplier: dict[str, float] = defaultdict(float)
    nominal_csv = baseline_result_dir / "data" / "supplier_nominal_parameters.csv"
    if nominal_csv.exists():
        with nominal_csv.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                supplier = str(row.get("supplier_id") or "")
                if supplier in allowed_suppliers:
                    shipped_by_supplier[supplier] += max(0.0, to_float(row.get("total_shipped_qty"), 0.0))
    shipments_csv = baseline_result_dir / "data" / "production_supplier_shipments_daily.csv"
    if not shipped_by_supplier and shipments_csv.exists():
        with shipments_csv.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                supplier = str(row.get("src_node_id") or "")
                if supplier in allowed_suppliers:
                    shipped_by_supplier[supplier] += max(0.0, to_float(row.get("shipped_qty"), 0.0))
    ranked = [supplier for supplier, _ in sorted(shipped_by_supplier.items(), key=lambda it: (-it[1], it[0]))]
    ranked.extend(supplier for supplier in sorted(allowed_suppliers) if supplier not in shipped_by_supplier)
    return ranked


def extract_manifest_extra_args(manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    cmd = manifest.get("simulator_command") or []
    if not isinstance(cmd, list) or not cmd:
        return []

    skip_value_for = {
        "--input",
        "--output-dir",
        "--scenario-id",
        "--days",
        "--output-profile",
        "--map-output",
        "--map-script",
    }
    skip_flags = {"--skip-map", "--skip-plots"}
    extra: list[str] = []
    i = 0
    while i < len(cmd):
        token = str(cmd[i])
        if i < 2:
            i += 1
            continue
        if token in skip_value_for:
            i += 2
            continue
        if token in skip_flags:
            i += 1
            continue
        extra.append(token)
        i += 1
    return extra


def split_supplier_floor_arg(extra_args: list[str]) -> tuple[list[str], Path | None]:
    cleaned: list[str] = []
    supplier_floors_csv: Path | None = None
    i = 0
    while i < len(extra_args):
        token = str(extra_args[i])
        if token == "--supplier-neutral-floors-csv":
            if i + 1 < len(extra_args):
                supplier_floors_csv = Path(str(extra_args[i + 1]))
            i += 2
            continue
        cleaned.append(token)
        i += 1
    return cleaned, supplier_floors_csv


def scale_csv_number(row: dict[str, str], field: str, scale: float) -> None:
    if field not in row:
        return
    raw = str(row.get(field) or "").strip()
    if not raw:
        return
    row[field] = f"{max(0.0, to_float(raw, 0.0) * scale):.6f}"


def write_case_supplier_floor_csv(
    *,
    baseline_csv: Path | None,
    output_csv: Path,
    config: dict[str, Any],
) -> Path | None:
    if baseline_csv is None or not baseline_csv.exists():
        return None
    with baseline_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows or not fieldnames:
        return None

    global_capacity_scale = to_float(config["factors"].get("supplier_capacity_scale"), 1.0)
    global_stock_scale = to_float(config["factors"].get("supplier_stock_scale"), 1.0)
    capacity_by_supplier = {
        str(supplier): to_float(scale, 1.0)
        for supplier, scale in config.get("supplier_capacity_node_scale", {}).items()
    }
    stock_by_supplier = {
        str(supplier): to_float(scale, 1.0)
        for supplier, scale in config.get("supplier_node_scale", {}).items()
    }

    for row in rows:
        supplier_id = str(row.get("supplier_id") or "")
        capacity_scale = global_capacity_scale * capacity_by_supplier.get(supplier_id, 1.0)
        stock_scale = global_stock_scale * stock_by_supplier.get(supplier_id, 1.0)
        for field in [
            "tested_capacity_floor_qty_per_day",
            "neutral_capacity_floor_qty_per_day",
            "industrial_nominal_capacity_qty_per_day",
            "effective_capacity_qty_per_day",
            "nominal_capacity_qty_per_day",
        ]:
            scale_csv_number(row, field, capacity_scale)
        for field in [
            "neutral_opening_stock_floor_qty",
            "simulated_opening_stock_qty",
            "input_initial_stock_qty",
            "base_stock_qty",
        ]:
            scale_csv_number(row, field, stock_scale)
        if "capacity_floor_basis" in row:
            row["capacity_floor_basis"] = "sensitivity_scaled_from_60_75_calibration"

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def apply_scenario_flags(mutated: dict[str, Any], scenario_id: str, flags: dict[str, bool]) -> None:
    if not flags:
        return
    scenario = choose_scenario(mutated, scenario_id)
    econ = scenario.get("economic_policy")
    if not isinstance(econ, dict):
        econ = {}
    for key, value in flags.items():
        econ[str(key)] = bool(value)
    scenario["economic_policy"] = econ


def run_simulation_case(
    *,
    run_script: Path,
    input_json: Path,
    output_dir: Path,
    scenario_id: str,
    days: int,
    extra_args: list[str],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(run_script),
        "--input",
        str(input_json),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        str(scenario_id),
        "--days",
        str(days),
        "--skip-map",
        "--skip-plots",
        "--output-profile",
        "compact",
        *extra_args,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        message = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
        raise RuntimeError(f"Simulation failed for {input_json}:\n{message}")

    summary_candidates = [
        output_dir / "summaries" / "first_simulation_summary.json",
        output_dir / "first_simulation_summary.json",
    ]
    for path in summary_candidates:
        if path.exists():
            return load_json(path)
    raise FileNotFoundError(f"Missing first_simulation_summary.json under {output_dir}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def operational_metrics(output_dir: Path) -> dict[str, float]:
    data_dir = output_dir / "data"
    demand_rows = read_csv_rows(data_dir / "production_demand_service_daily.csv")
    max_backlog = 0.0
    backlog_days: set[int] = set()
    min_daily_service = 1.0
    for row in demand_rows:
        day = int(to_float(row.get("day"), 0.0))
        required = max(0.0, to_float(row.get("required_with_backlog_qty"), 0.0))
        served = max(0.0, to_float(row.get("served_qty"), 0.0))
        backlog = max(0.0, to_float(row.get("backlog_end_qty"), 0.0))
        max_backlog = max(max_backlog, backlog)
        if backlog > 1e-6:
            backlog_days.add(day)
        if required > 1e-9:
            min_daily_service = min(min_daily_service, served / required)

    stock_by_key: dict[tuple[int, str, str], float] = {}
    for row in read_csv_rows(data_dir / "production_input_stocks_daily.csv"):
        key = (
            int(to_float(row.get("day"), 0.0)),
            str(row.get("node_id") or ""),
            str(row.get("item_id") or ""),
        )
        stock_by_key[key] = to_float(row.get("stock_end_of_day"), 0.0)

    floor_breach_days: set[int] = set()
    floor_breach_pairs: set[tuple[str, str]] = set()
    max_floor_gap = 0.0
    max_target_gap = 0.0
    for row in read_csv_rows(data_dir / "mrp_trace_daily.csv"):
        key = (
            int(to_float(row.get("day"), 0.0)),
            str(row.get("node_id") or ""),
            str(row.get("item_id") or ""),
        )
        if key not in stock_by_key:
            continue
        stock = stock_by_key[key]
        safety_floor = max(0.0, to_float(row.get("safety_floor_qty"), 0.0))
        target = max(0.0, to_float(row.get("target_stock_qty"), 0.0))
        if safety_floor > 0.0 and stock + 1e-6 < safety_floor:
            floor_breach_days.add(key[0])
            floor_breach_pairs.add((key[1], key[2]))
            max_floor_gap = max(max_floor_gap, safety_floor - stock)
        if target > 0.0 and stock + 1e-6 < target:
            max_target_gap = max(max_target_gap, target - stock)

    return {
        "max_daily_backlog_qty": round(max_backlog, 6),
        "backlog_days": float(len(backlog_days)),
        "min_daily_service_rate": round(min_daily_service, 9),
        "raw_material_safety_floor_breach_days": float(len(floor_breach_days)),
        "raw_material_safety_floor_breach_pairs": float(len(floor_breach_pairs)),
        "raw_material_max_safety_floor_gap_qty": round(max_floor_gap, 6),
        "raw_material_max_target_gap_qty": round(max_target_gap, 6),
    }


def inventory_holding_costs_by_node(data_dir: Path, case_input: Path | None) -> dict[str, float]:
    if case_input is None or not case_input.exists():
        return {}
    try:
        case_data = load_json(case_input)
    except Exception:
        return {}

    holding_by_key: dict[tuple[str, str], float] = {}
    for node in case_data.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        for state in ((node.get("inventory") or {}).get("states") or []):
            item_id = str(state.get("item_id") or "")
            holding = to_float((state.get("holding_cost") or {}).get("value"), math.nan)
            if node_id and item_id and not math.isnan(holding):
                holding_by_key[(node_id, item_id)] = max(0.0, holding)

    if not holding_by_key:
        return {}

    stock_files = [
        "production_input_stocks_daily.csv",
        "production_output_products_daily.csv",
        "production_supplier_stocks_daily.csv",
        "production_dc_stocks_daily.csv",
    ]
    cost_by_node: dict[str, float] = defaultdict(float)
    for file_name in stock_files:
        for row in read_csv_rows(data_dir / file_name):
            node_id = str(row.get("node_id") or "")
            item_id = str(row.get("item_id") or row.get("output_item_id") or "")
            stock = max(0.0, to_float(row.get("stock_end_of_day"), 0.0))
            holding = holding_by_key.get((node_id, item_id), 0.0)
            if node_id and holding > 0.0 and stock > 0.0:
                cost_by_node[node_id] += stock * holding
    return {node_id: round(value, 6) for node_id, value in cost_by_node.items()}


def derived_case_kpis(output_dir: Path, case_input: Path | None = None) -> dict[str, float]:
    data_dir = output_dir / "data"
    out: dict[str, float] = {}

    demand_rows = read_csv_rows(data_dir / "production_demand_service_daily.csv")
    demand_line_count = 0
    available_line_count = 0
    for row in demand_rows:
        required = max(0.0, to_float(row.get("required_with_backlog_qty"), 0.0))
        served = max(0.0, to_float(row.get("served_qty"), 0.0))
        if required <= 1e-9:
            continue
        demand_line_count += 1
        if served + 1e-6 >= required:
            available_line_count += 1
    out["product_availability"] = (
        round(available_line_count / demand_line_count, 9) if demand_line_count else 1.0
    )

    planned_qty_total = 0.0
    adhered_qty_total = 0.0
    line_changes = 0
    replanning_count = 0
    previous_plan_by_line: dict[tuple[str, str], float] = {}
    for row in read_csv_rows(data_dir / "production_constraint_daily.csv"):
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("output_item_id") or row.get("item_id") or "")
        planned = max(0.0, to_float(row.get("planned_qty_after_lot_rule"), 0.0))
        actual = max(0.0, to_float(row.get("actual_qty"), 0.0))
        planned_qty_total += planned
        adhered_qty_total += min(actual, planned)
        key = (node_id, item_id)
        previous_plan = previous_plan_by_line.get(key)
        if previous_plan is not None and abs(planned - previous_plan) > 1e-6:
            line_changes += 1
        previous_plan_by_line[key] = planned
        requested_lots = to_float(row.get("requested_lot_starts"), math.nan)
        actual_lots = to_float(row.get("actual_lot_starts"), math.nan)
        lot_shortfall = max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty"), 0.0))
        if (
            (not math.isnan(requested_lots) and not math.isnan(actual_lots) and actual_lots + 1e-9 < requested_lots)
            or lot_shortfall > 1e-6
        ):
            replanning_count += 1
    out["line_adherence"] = round(adhered_qty_total / planned_qty_total, 9) if planned_qty_total > 1e-9 else 1.0
    out["line_nervousness"] = float(line_changes)
    out["production_replanning_count"] = float(replanning_count)

    stock_by_key: dict[tuple[int, str, str], float] = {}
    for row in read_csv_rows(data_dir / "production_input_stocks_daily.csv"):
        key = (
            int(to_float(row.get("day"), 0.0)),
            str(row.get("node_id") or ""),
            str(row.get("item_id") or ""),
        )
        stock_by_key[key] = to_float(row.get("stock_end_of_day"), 0.0)
    stockout_days: set[int] = set()
    for row in read_csv_rows(data_dir / "mrp_trace_daily.csv"):
        key = (
            int(to_float(row.get("day"), 0.0)),
            str(row.get("node_id") or ""),
            str(row.get("item_id") or ""),
        )
        target_stock = max(0.0, to_float(row.get("target_stock_qty"), 0.0))
        if target_stock <= 0.0:
            continue
        stock = stock_by_key.get(key)
        if stock is not None and stock <= 1e-6:
            stockout_days.add(key[0])
    out["raw_material_stockout_days"] = float(len(stockout_days))

    max_delay = 0.0
    total_delay = 0.0
    delayed_orders = 0
    for row in read_csv_rows(data_dir / "mrp_orders_daily.csv"):
        planned_arrival = to_float(row.get("arrival_day"), math.nan)
        actual_arrival = to_float(row.get("actual_receipt_day"), math.nan)
        if math.isnan(planned_arrival) or math.isnan(actual_arrival):
            continue
        delay = max(0.0, actual_arrival - planned_arrival)
        max_delay = max(max_delay, delay)
        total_delay += delay
        if delay > 1e-9:
            delayed_orders += 1
    out["material_delay_days"] = round(max_delay, 6)
    out["material_delay_days_total"] = round(total_delay, 6)
    out["material_delayed_order_count"] = float(delayed_orders)

    node_costs = inventory_holding_costs_by_node(data_dir, case_input)
    if node_costs:
        out["inventory_holding_cost_node_max"] = round(max(node_costs.values()), 6)
        out["inventory_holding_cost_node_count"] = float(len(node_costs))
        out["inventory_holding_cost_proxy_total"] = round(sum(node_costs.values()), 6)
    return out


def prune_case_output(output_dir: Path, *, artifact_mode: str = "summary") -> None:
    if not output_dir.exists():
        return
    if artifact_mode == "full":
        return
    summary_keep = {
        output_dir / "summaries",
        output_dir / "reports",
        output_dir / "data" / "production_demand_service_daily.csv",
        output_dir / "data" / "production_constraint_daily.csv",
        output_dir / "data" / "production_output_products_daily.csv",
        output_dir / "data" / "production_factory_nervousness.csv",
        output_dir / "data" / "supplier_nominal_parameters.csv",
        output_dir / "data" / "supplier_risk_events_applied_daily.csv",
        output_dir / "data" / "supplier_state_dependent_risk_events.csv",
    }
    compact_keep = summary_keep | {
        output_dir / "data" / "production_input_stocks_daily.csv",
        output_dir / "data" / "production_supplier_stocks_daily.csv",
        output_dir / "data" / "production_dc_stocks_daily.csv",
        output_dir / "data" / "mrp_orders_daily.csv",
    }
    keep = compact_keep if artifact_mode == "compact" else summary_keep

    def try_unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return

    for child in output_dir.iterdir():
        if child in keep:
            continue
        if child.is_dir() and child.name == "data":
            for data_file in child.iterdir():
                if data_file not in keep:
                    try_unlink(data_file)
            continue
        if child.is_dir() and child.name in {"summaries", "reports"}:
            continue
        if child.is_file():
            try_unlink(child)


def build_specs(
    groups: set[str],
    suppliers: list[str],
    levels: dict[str, list[float]],
    combined_levels: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    combined_levels = combined_levels or {}
    if "stock" in groups:
        specs.append(
            {
                "parameter_key": "supplier_stock_scale",
                "parameter_group": "supplier_stock_global",
                "parameter_label": "Stock fournisseur global",
                "levels": levels["stock"],
                "config_kind": "factor",
                "target": "supplier_stock_scale",
                "safe_direction": "lower_is_riskier",
            }
        )
    if "capacity" in groups:
        specs.append(
            {
                "parameter_key": "supplier_capacity_scale",
                "parameter_group": "supplier_capacity_global",
                "parameter_label": "Capacite fournisseur globale",
                "levels": levels["capacity"],
                "config_kind": "factor",
                "target": "supplier_capacity_scale",
                "safe_direction": "lower_is_riskier",
            }
        )
    if "lead_time" in groups:
        specs.append(
            {
                "parameter_key": "supplier_lead_time_scale",
                "parameter_group": "supplier_lead_time_global",
                "parameter_label": "Delai fournisseur global",
                "levels": levels["lead_time"],
                "config_kind": "all_supplier_lead_time",
                "target": "",
                "safe_direction": "higher_is_riskier",
            }
        )
    if "reliability" in groups:
        specs.append(
            {
                "parameter_key": "supplier_reliability_scale",
                "parameter_group": "supplier_reliability_global",
                "parameter_label": "Fiabilite fournisseur globale",
                "levels": levels["reliability"],
                "config_kind": "all_supplier_reliability",
                "target": "",
                "safe_direction": "lower_is_riskier",
            }
        )
    if "external" in groups:
        specs.extend(
            [
                {
                    "parameter_key": "external_procurement_enabled",
                    "parameter_group": "supplier_upstream_supply",
                    "parameter_label": "Appro amont fournisseur active",
                    "levels": [0.01, 1.0],
                    "config_kind": "scenario_flag",
                    "target": "external_procurement_enabled",
                    "safe_direction": "lower_is_riskier",
                },
                {
                    "parameter_key": "external_procurement_daily_cap_days_scale",
                    "parameter_group": "supplier_upstream_supply",
                    "parameter_label": "Capacite appro amont fournisseur",
                    "levels": levels["external_capacity"],
                    "config_kind": "factor",
                    "target": "external_procurement_daily_cap_days_scale",
                    "safe_direction": "lower_is_riskier",
                },
                {
                    "parameter_key": "external_procurement_lead_days_scale",
                    "parameter_group": "supplier_upstream_supply",
                    "parameter_label": "Delai appro amont fournisseur",
                    "levels": levels["external_lead"],
                    "config_kind": "factor",
                    "target": "external_procurement_lead_days_scale",
                    "safe_direction": "higher_is_riskier",
                },
            ]
        )
    if "combined" in groups:
        combined_capacity = float(combined_levels.get("capacity", 0.75))
        combined_stock = float(combined_levels.get("stock", 0.50))
        combined_lead_time = float(combined_levels.get("lead_time", 1.25))
        combined_reliability = float(combined_levels.get("reliability", 0.97))
        combined_upstream_capacity = float(combined_levels.get("upstream_capacity", 0.75))
        combined_upstream_lead = float(combined_levels.get("upstream_lead", 1.25))
        specs.append(
            {
                "parameter_key": "combined_upstream_capacity_delay",
                "parameter_group": "supplier_combined_upstream_supply",
                "parameter_label": (
                    f"Appro amont combinee cap x{combined_upstream_capacity:g} "
                    f"+ delai x{combined_upstream_lead:g}"
                ),
                "levels": [1.0],
                "config_kind": "multi",
                "mutations": [
                    {
                        "config_kind": "factor",
                        "target": "external_procurement_daily_cap_days_scale",
                        "level": combined_upstream_capacity,
                    },
                    {
                        "config_kind": "factor",
                        "target": "external_procurement_lead_days_scale",
                        "level": combined_upstream_lead,
                    },
                ],
                "safe_direction": "scenario",
            }
        )

    for supplier in suppliers:
        if "stock" in groups:
            specs.append(
                {
                    "parameter_key": f"supplier_stock_node::{supplier}",
                    "parameter_group": "supplier_stock_node",
                    "parameter_label": f"Stock fournisseur {supplier}",
                    "levels": levels["stock"],
                    "config_kind": "supplier_node_scale",
                    "target": supplier,
                    "safe_direction": "lower_is_riskier",
                }
            )
        if "capacity" in groups:
            specs.append(
                {
                    "parameter_key": f"supplier_capacity_node::{supplier}",
                    "parameter_group": "supplier_capacity_node",
                    "parameter_label": f"Capacite fournisseur {supplier}",
                    "levels": levels["capacity"],
                    "config_kind": "supplier_capacity_node_scale",
                    "target": supplier,
                    "safe_direction": "lower_is_riskier",
                }
            )
        if "lead_time" in groups:
            specs.append(
                {
                    "parameter_key": f"supplier_lead_time_node::{supplier}",
                    "parameter_group": "supplier_lead_time_node",
                    "parameter_label": f"Delai fournisseur {supplier}",
                    "levels": levels["lead_time"],
                    "config_kind": "edge_src_lead_time_scale",
                    "target": supplier,
                    "safe_direction": "higher_is_riskier",
                }
            )
        if "reliability" in groups:
            specs.append(
                {
                    "parameter_key": f"supplier_reliability_node::{supplier}",
                    "parameter_group": "supplier_reliability_node",
                    "parameter_label": f"Fiabilite fournisseur {supplier}",
                    "levels": levels["reliability"],
                    "config_kind": "edge_src_reliability_scale",
                    "target": supplier,
                    "safe_direction": "lower_is_riskier",
                }
            )
        if "combined" in groups:
            specs.extend(
                [
                    {
                        "parameter_key": f"combined_capacity_delay::{supplier}",
                        "parameter_group": "supplier_combined_capacity_delay_node",
                        "parameter_label": (
                            f"Combine capacite x{combined_capacity:g} "
                            f"+ delai x{combined_lead_time:g} fournisseur {supplier}"
                        ),
                        "levels": [1.0],
                        "config_kind": "multi",
                        "mutations": [
                            {
                                "config_kind": "supplier_capacity_node_scale",
                                "target": supplier,
                                "level": combined_capacity,
                            },
                            {
                                "config_kind": "edge_src_lead_time_scale",
                                "target": supplier,
                                "level": combined_lead_time,
                            },
                        ],
                        "safe_direction": "scenario",
                    },
                    {
                        "parameter_key": f"combined_stock_reliability::{supplier}",
                        "parameter_group": "supplier_combined_stock_reliability_node",
                        "parameter_label": (
                            f"Combine stock x{combined_stock:g} "
                            f"+ fiabilite x{combined_reliability:g} fournisseur {supplier}"
                        ),
                        "levels": [1.0],
                        "config_kind": "multi",
                        "mutations": [
                            {
                                "config_kind": "supplier_node_scale",
                                "target": supplier,
                                "level": combined_stock,
                            },
                            {
                                "config_kind": "edge_src_reliability_scale",
                                "target": supplier,
                                "level": combined_reliability,
                            },
                        ],
                        "safe_direction": "scenario",
                    },
                ]
            )
    return specs


def apply_config_mutation(
    cfg: dict[str, Any],
    *,
    kind: str,
    target: str,
    level: float,
    suppliers: list[str],
) -> None:
    if kind == "factor":
        cfg["factors"][target] = level
    elif kind == "supplier_node_scale":
        cfg["supplier_node_scale"][target] = level
    elif kind == "supplier_capacity_node_scale":
        cfg["supplier_capacity_node_scale"][target] = level
    elif kind == "edge_src_lead_time_scale":
        cfg["edge_src_lead_time_scale"][target] = level
    elif kind == "edge_src_reliability_scale":
        cfg["edge_src_reliability_scale"][target] = level
    elif kind == "all_supplier_lead_time":
        cfg["edge_src_lead_time_scale"].update({supplier: level for supplier in suppliers})
    elif kind == "all_supplier_reliability":
        cfg["edge_src_reliability_scale"].update({supplier: level for supplier in suppliers})
    elif kind == "scenario_flag":
        cfg["scenario_flags"][target] = level >= 0.5
    else:
        raise ValueError(f"Unsupported config kind: {kind}")


def config_for_spec(spec: dict[str, Any], level: float, suppliers: list[str]) -> dict[str, Any]:
    cfg = clone_case_config(base_case())
    kind = str(spec["config_kind"])
    target = str(spec.get("target") or "")
    if kind == "multi":
        for mutation in spec.get("mutations", []) or []:
            apply_config_mutation(
                cfg,
                kind=str(mutation.get("config_kind") or ""),
                target=str(mutation.get("target") or ""),
                level=float(mutation.get("level", level)),
                suppliers=suppliers,
            )
    else:
        apply_config_mutation(cfg, kind=kind, target=target, level=level, suppliers=suppliers)
    return cfg


def case_id_for(parameter_key: str, level: float) -> str:
    return f"{safe_name(parameter_key)}_{str(level).replace('.', '_')}"


def run_case(
    *,
    case_id: str,
    spec: dict[str, Any],
    level: float,
    config: dict[str, Any],
    base_data: dict[str, Any],
    run_script: Path,
    scenario_id: str,
    days: int,
    cases_root: Path,
    extra_args: list[str],
    supplier_floor_csv: Path | None,
    artifact_mode: str,
) -> dict[str, Any]:
    case_dir = cases_root / case_id
    case_input = case_dir / "input_case.json"
    case_output = case_dir / "simulation_output"
    summary_candidates = [
        case_output / "summaries" / "first_simulation_summary.json",
        case_output / "first_simulation_summary.json",
    ]
    summary_file = next((path for path in summary_candidates if path.exists()), None)
    if summary_file is not None:
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
        apply_scenario_flags(mutated, scenario_id, config["scenario_flags"])
        case_dir.mkdir(parents=True, exist_ok=True)
        write_json(case_input, mutated)
        case_extra_args = list(extra_args)
        case_supplier_floor_csv = write_case_supplier_floor_csv(
            baseline_csv=supplier_floor_csv,
            output_csv=case_dir / "supplier_neutral_floors_case.csv",
            config=config,
        )
        if case_supplier_floor_csv is not None:
            case_extra_args.extend(["--supplier-neutral-floors-csv", str(case_supplier_floor_csv)])
        summary = run_simulation_case(
            run_script=run_script,
            input_json=case_input,
            output_dir=case_output,
            scenario_id=scenario_id,
            days=days,
            extra_args=case_extra_args,
        )
    op = operational_metrics(case_output)
    derived = derived_case_kpis(case_output, case_input)
    prune_case_output(case_output, artifact_mode=artifact_mode)

    row: dict[str, Any] = {
        "case_id": case_id,
        "parameter_key": spec["parameter_key"],
        "parameter_group": spec["parameter_group"],
        "parameter_label": spec["parameter_label"],
        "level": level,
        "safe_direction": spec["safe_direction"],
        "status": "ok",
        "case_input": str(case_input),
        "case_output_dir": str(case_output),
    }
    summary_kpis = numeric_kpis(summary)
    for key, value in summary_kpis.items():
        row[f"kpi::{key}"] = value
    if "total_holding_cost" in summary_kpis:
        row["kpi::inventory_cost"] = summary_kpis["total_holding_cost"]
    for key, value in derived.items():
        row[f"kpi::{key}"] = value
    for key, value in op.items():
        row[f"guard::{key}"] = value
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def reusable_case_row(row: dict[str, Any]) -> bool:
    if str(row.get("status") or "").lower() != "ok":
        return False
    case_output = Path(str(row.get("case_output_dir") or ""))
    if not (case_output / "summaries" / "first_simulation_summary.json").exists() and not (
        case_output / "first_simulation_summary.json"
    ).exists():
        return False
    return all(str(row.get(key) or "").strip() for key in REQUIRED_DERIVED_KPI_COLUMNS)


def is_case_acceptable(row: dict[str, Any], baseline: dict[str, Any], service_threshold: float) -> bool:
    fill = to_float(row.get("kpi::fill_rate"), math.nan)
    ending_backlog = to_float(row.get("kpi::ending_backlog"), math.nan)
    baseline_ending_backlog = to_float(baseline.get("kpi::ending_backlog"), 0.0)
    if math.isnan(fill) or fill + 1e-9 < service_threshold:
        return False
    if math.isnan(ending_backlog) or ending_backlog > baseline_ending_backlog + 1e-6:
        return False
    for key in [
        "guard::max_daily_backlog_qty",
        "guard::backlog_days",
        "guard::raw_material_safety_floor_breach_days",
        "guard::raw_material_safety_floor_breach_pairs",
        "guard::raw_material_max_safety_floor_gap_qty",
        "guard::raw_material_max_target_gap_qty",
    ]:
        value = to_float(row.get(key), math.nan)
        base = to_float(baseline.get(key), math.nan)
        if math.isnan(value) or math.isnan(base) or value > base + 1e-6:
            return False
    no_worse_higher_is_better = [
        "kpi::product_availability",
        "kpi::line_adherence",
    ]
    for key in no_worse_higher_is_better:
        base = to_float(baseline.get(key), math.nan)
        value = to_float(row.get(key), math.nan)
        if not math.isnan(base) and (math.isnan(value) or value + SERVICE_KPI_TOLERANCE < base):
            return False
    no_worse_lower_is_better_soft = [
        "kpi::line_nervousness",
        "kpi::production_replanning_count",
    ]
    for key in no_worse_lower_is_better_soft:
        base = to_float(baseline.get(key), math.nan)
        value = to_float(row.get(key), math.nan)
        if not math.isnan(base) and (math.isnan(value) or value > base + COUNT_KPI_TOLERANCE):
            return False
    no_worse_lower_is_better_hard = [
        "kpi::raw_material_stockout_days",
        "kpi::material_delay_days",
    ]
    for key in no_worse_lower_is_better_hard:
        base = to_float(baseline.get(key), math.nan)
        value = to_float(row.get(key), math.nan)
        if not math.isnan(base) and (math.isnan(value) or value > base + 1e-6):
            return False
    return True


def contiguous_acceptable_ranges(levels: list[float], acceptable_levels: list[float]) -> list[list[float]]:
    acceptable_set = {round(level, 12) for level in acceptable_levels if not math.isnan(level)}
    ranges: list[list[float]] = []
    current: list[float] = []
    for level in levels:
        if math.isnan(level):
            continue
        if round(level, 12) in acceptable_set:
            current.append(level)
            continue
        if current:
            ranges.append([current[0], current[-1]])
            current = []
    if current:
        ranges.append([current[0], current[-1]])
    return ranges


def baseline_safe_range(ranges: list[list[float]], baseline_level: float = 1.0) -> tuple[float | None, float | None]:
    for low, high in ranges:
        if low - 1e-9 <= baseline_level <= high + 1e-9:
            return low, high
    return None, None


def safe_range_label(row: dict[str, Any]) -> str:
    ranges = str(row.get("acceptable_ranges") or "[]")
    contiguous = str(row.get("acceptable_is_contiguous") or "").lower() == "true"
    low = row.get("baseline_contiguous_safe_low")
    high = row.get("baseline_contiguous_safe_high")
    if contiguous:
        return f"plage continue baseline [{low}, {high}]"
    return f"niveaux acceptables non contigus {row.get('acceptable_levels')}; plage continue baseline [{low}, {high}]"


def first_metric_crossing(
    rows: list[dict[str, Any]],
    metric_keys: list[str],
    *,
    baseline: float,
    direction: str,
    tolerance: float = 1e-9,
) -> float | None:
    if math.isnan(baseline):
        return None
    for row in rows:
        value = first_available_metric(row, metric_keys)
        if math.isnan(value):
            continue
        if direction == "lower_is_worse" and value + tolerance < baseline:
            return to_float(row.get("level"), math.nan)
        if direction == "higher_is_worse" and value > baseline + tolerance:
            return to_float(row.get("level"), math.nan)
    return None


def first_available_metric(row: dict[str, Any], metric_keys: list[str]) -> float:
    for key in metric_keys:
        value = to_float(row.get(key), math.nan)
        if not math.isnan(value):
            return value
    return math.nan


def clean_metric_values(rows: list[dict[str, Any]], metric_keys: list[str]) -> list[float]:
    return [value for row in rows if not math.isnan(value := first_available_metric(row, metric_keys))]


def summarize_parameter(
    spec: dict[str, Any],
    rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    *,
    service_threshold: float,
    cost_increase_pct: float,
) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: to_float(row.get("level"), 0.0))
    acceptable = [row for row in rows if is_case_acceptable(row, baseline, service_threshold)]
    levels = [to_float(row.get("level"), math.nan) for row in rows]
    safe_levels = [to_float(row.get("level"), math.nan) for row in acceptable]
    baseline_fill = to_float(baseline.get("kpi::fill_rate"), math.nan)
    baseline_cost = to_float(baseline.get("kpi::total_cost"), math.nan)
    baseline_external = to_float(baseline.get("kpi::total_external_procured_ordered_qty"), math.nan)
    baseline_availability = first_available_metric(baseline, ["kpi::product_availability", "kpi::fill_rate"])
    baseline_line_adherence = first_available_metric(baseline, ["kpi::line_adherence"])
    baseline_line_nervousness = first_available_metric(baseline, ["kpi::line_nervousness"])
    baseline_replanning = first_available_metric(baseline, ["kpi::production_replanning_count"])
    baseline_stockout_days = first_available_metric(baseline, ["kpi::raw_material_stockout_days"])
    baseline_material_delay = first_available_metric(baseline, ["kpi::material_delay_days"])
    baseline_inventory_cost = first_available_metric(
        baseline,
        ["kpi::inventory_cost", "kpi::total_holding_cost", "kpi::inventory_holding_cost_proxy_total"],
    )
    fill_values = [to_float(row.get("kpi::fill_rate"), math.nan) for row in rows]
    cost_values = [to_float(row.get("kpi::total_cost"), math.nan) for row in rows]
    external_values = [to_float(row.get("kpi::total_external_procured_ordered_qty"), math.nan) for row in rows]
    availability_values = clean_metric_values(rows, ["kpi::product_availability", "kpi::fill_rate"])
    line_adherence_values = clean_metric_values(rows, ["kpi::line_adherence"])
    line_nervousness_values = clean_metric_values(rows, ["kpi::line_nervousness"])
    replanning_values = clean_metric_values(rows, ["kpi::production_replanning_count"])
    stockout_day_values = clean_metric_values(rows, ["kpi::raw_material_stockout_days"])
    material_delay_values = clean_metric_values(rows, ["kpi::material_delay_days"])
    inventory_cost_values = clean_metric_values(
        rows,
        ["kpi::inventory_cost", "kpi::total_holding_cost", "kpi::inventory_holding_cost_proxy_total"],
    )

    safe_low = min(safe_levels) if safe_levels else None
    safe_high = max(safe_levels) if safe_levels else None
    acceptable_ranges = contiguous_acceptable_ranges(levels, safe_levels)
    baseline_safe_low, baseline_safe_high = baseline_safe_range(acceptable_ranges)
    acceptable_is_contiguous = len(acceptable_ranges) <= 1
    first_bad = None
    for row in rows:
        if not is_case_acceptable(row, baseline, service_threshold):
            first_bad = to_float(row.get("level"), math.nan)
            break
    fill_cross_level = None
    for row in rows:
        fill = to_float(row.get("kpi::fill_rate"), math.nan)
        if math.isnan(fill) or fill + 1e-9 < service_threshold:
            fill_cross_level = to_float(row.get("level"), math.nan)
            break

    max_fill_drop = max(
        (baseline_fill - value for value in fill_values if not math.isnan(value)),
        default=math.nan,
    )
    max_cost_increase = max(
        (value - baseline_cost for value in cost_values if not math.isnan(value)),
        default=math.nan,
    )
    max_external_delta = max(
        (value - baseline_external for value in external_values if not math.isnan(value)),
        default=math.nan,
    )
    target_gap_values = [to_float(row.get("guard::raw_material_max_target_gap_qty"), math.nan) for row in rows]
    safety_gap_values = [to_float(row.get("guard::raw_material_max_safety_floor_gap_qty"), math.nan) for row in rows]
    baseline_target_gap = to_float(baseline.get("guard::raw_material_max_target_gap_qty"), math.nan)
    baseline_safety_gap = to_float(baseline.get("guard::raw_material_max_safety_floor_gap_qty"), math.nan)
    max_target_gap_increase = max(
        (value - baseline_target_gap for value in target_gap_values if not math.isnan(value) and not math.isnan(baseline_target_gap)),
        default=math.nan,
    )
    max_safety_gap_increase = max(
        (value - baseline_safety_gap for value in safety_gap_values if not math.isnan(value) and not math.isnan(baseline_safety_gap)),
        default=math.nan,
    )

    cost_warn_level = None
    for row in rows:
        cost = to_float(row.get("kpi::total_cost"), math.nan)
        if not math.isnan(cost) and cost > baseline_cost * (1.0 + cost_increase_pct):
            cost_warn_level = to_float(row.get("level"), math.nan)
            break
    inventory_cost_warn_level = None
    for row in rows:
        inventory_cost = first_available_metric(
            row,
            ["kpi::inventory_cost", "kpi::total_holding_cost", "kpi::inventory_holding_cost_proxy_total"],
        )
        if (
            not math.isnan(inventory_cost)
            and not math.isnan(baseline_inventory_cost)
            and inventory_cost > baseline_inventory_cost * (1.0 + cost_increase_pct)
        ):
            inventory_cost_warn_level = to_float(row.get("level"), math.nan)
            break

    fill_mono = monotonicity(fill_values)
    backlog_values = [to_float(row.get("kpi::ending_backlog"), math.nan) for row in rows]
    backlog_cross_level = None
    baseline_backlog = to_float(baseline.get("kpi::ending_backlog"), 0.0)
    for row in rows:
        backlog = to_float(row.get("kpi::ending_backlog"), math.nan)
        if not math.isnan(backlog) and backlog > baseline_backlog + 1e-6:
            backlog_cross_level = to_float(row.get("level"), math.nan)
            break

    availability_cross_level = first_metric_crossing(
        rows,
        ["kpi::product_availability", "kpi::fill_rate"],
        baseline=baseline_availability,
        direction="lower_is_worse",
    )
    line_adherence_cross_level = first_metric_crossing(
        rows,
        ["kpi::line_adherence"],
        baseline=baseline_line_adherence,
        direction="lower_is_worse",
    )
    target_gap_cross_level = first_metric_crossing(
        rows,
        ["guard::raw_material_max_target_gap_qty"],
        baseline=baseline_target_gap,
        direction="higher_is_worse",
        tolerance=1e-6,
    )

    max_availability_drop = max(
        (baseline_availability - value for value in availability_values if not math.isnan(baseline_availability)),
        default=math.nan,
    )
    max_line_adherence_drop = max(
        (baseline_line_adherence - value for value in line_adherence_values if not math.isnan(baseline_line_adherence)),
        default=math.nan,
    )
    max_line_nervousness_increase = max(
        (value - baseline_line_nervousness for value in line_nervousness_values if not math.isnan(baseline_line_nervousness)),
        default=math.nan,
    )
    max_replanning_increase = max(
        (value - baseline_replanning for value in replanning_values if not math.isnan(baseline_replanning)),
        default=math.nan,
    )
    max_stockout_day_increase = max(
        (value - baseline_stockout_days for value in stockout_day_values if not math.isnan(baseline_stockout_days)),
        default=math.nan,
    )
    max_material_delay_increase = max(
        (value - baseline_material_delay for value in material_delay_values if not math.isnan(baseline_material_delay)),
        default=math.nan,
    )
    max_inventory_cost_increase = max(
        (value - baseline_inventory_cost for value in inventory_cost_values if not math.isnan(baseline_inventory_cost)),
        default=math.nan,
    )

    baseline_margin_pct = math.nan
    if spec["safe_direction"] == "lower_is_riskier" and baseline_safe_low is not None:
        baseline_margin_pct = max(0.0, (1.0 - float(baseline_safe_low)) * 100.0)
    elif spec["safe_direction"] == "higher_is_riskier" and baseline_safe_high is not None:
        baseline_margin_pct = max(0.0, (float(baseline_safe_high) - 1.0) * 100.0)
    parameter_group = str(spec["parameter_group"])
    parameter_key = str(spec["parameter_key"])

    return {
        "parameter_key": spec["parameter_key"],
        "parameter_group": spec["parameter_group"],
        "parameter_label": spec["parameter_label"],
        "safe_direction": spec["safe_direction"],
        "levels": json.dumps(levels),
        "acceptable_levels": json.dumps(safe_levels),
        "acceptable_ranges": json.dumps(acceptable_ranges),
        "acceptable_is_contiguous": acceptable_is_contiguous,
        "safe_band_low": safe_low,
        "safe_band_high": safe_high,
        "baseline_contiguous_safe_low": baseline_safe_low,
        "baseline_contiguous_safe_high": baseline_safe_high,
        "first_unacceptable_level": first_bad,
        "fill_rate_cross_service_threshold_at": fill_cross_level,
        "ending_backlog_cross_threshold_at": backlog_cross_level,
        "total_cost_cross_threshold_at": cost_warn_level,
        "inventory_cost_cross_threshold_at": inventory_cost_warn_level,
        "product_availability_cross_baseline_at": availability_cross_level,
        "line_adherence_cross_baseline_at": line_adherence_cross_level,
        "target_stock_gap_cross_baseline_at": target_gap_cross_level,
        "fill_rate_monotonicity": fill_mono,
        "ending_backlog_monotonicity": monotonicity(backlog_values),
        "total_cost_monotonicity": monotonicity(cost_values),
        "product_availability_monotonicity": monotonicity(availability_values),
        "line_adherence_monotonicity": monotonicity(line_adherence_values),
        "inventory_cost_monotonicity": monotonicity(inventory_cost_values),
        "fill_rate_min": min((v for v in fill_values if not math.isnan(v)), default=math.nan),
        "fill_rate_max": max((v for v in fill_values if not math.isnan(v)), default=math.nan),
        "product_availability_min": min(availability_values, default=math.nan),
        "line_adherence_min": min(line_adherence_values, default=math.nan),
        "line_nervousness_max": max(line_nervousness_values, default=math.nan),
        "production_replanning_count_max": max(replanning_values, default=math.nan),
        "raw_material_stockout_days_max": max(stockout_day_values, default=math.nan),
        "material_delay_days_max": max(material_delay_values, default=math.nan),
        "inventory_cost_max": max(inventory_cost_values, default=math.nan),
        "max_fill_rate_drop": max_fill_drop,
        "max_product_availability_drop": max_availability_drop,
        "max_line_adherence_drop": max_line_adherence_drop,
        "max_line_nervousness_increase": max_line_nervousness_increase,
        "max_production_replanning_count_increase": max_replanning_increase,
        "max_raw_material_stockout_days_increase": max_stockout_day_increase,
        "max_material_delay_days_increase": max_material_delay_increase,
        "max_inventory_cost_increase": max_inventory_cost_increase,
        "max_total_cost_increase": max_cost_increase,
        "max_external_procured_qty_delta": max_external_delta,
        "max_supplier_upstream_ordered_qty_delta": max_external_delta,
        "max_raw_material_target_gap_increase": max_target_gap_increase,
        "max_raw_material_safety_floor_gap_increase": max_safety_gap_increase,
        "baseline_margin_pct": baseline_margin_pct,
        "capacity_reduction_margin_pct": (
            baseline_margin_pct if "capacity" in parameter_group and "upstream" not in parameter_group else math.nan
        ),
        "stock_reduction_margin_pct": baseline_margin_pct if "stock" in parameter_group else math.nan,
        "delay_increase_margin_pct": (
            baseline_margin_pct if "lead" in parameter_group or "lead" in parameter_key else math.nan
        ),
        "reliability_reduction_margin_pct": baseline_margin_pct if "reliability" in parameter_group else math.nan,
        "upstream_capacity_reduction_margin_pct": (
            baseline_margin_pct if "upstream" in parameter_group and "cap" in parameter_key else math.nan
        ),
        "upstream_delay_increase_margin_pct": (
            baseline_margin_pct if "upstream" in parameter_group and "lead" in parameter_key else math.nan
        ),
        "cost_warning_level": cost_warn_level,
        "baseline_fill_rate": baseline_fill,
        "baseline_total_cost": baseline_cost,
        "baseline_product_availability": baseline_availability,
        "baseline_line_adherence": baseline_line_adherence,
        "baseline_inventory_cost": baseline_inventory_cost,
    }


def monotonicity(values: list[float]) -> str:
    clean = [value for value in values if not math.isnan(value)]
    if len(clean) < 2:
        return "flat"
    diffs = [b - a for a, b in zip(clean[:-1], clean[1:])]
    positives = [d for d in diffs if d > 1e-9]
    negatives = [d for d in diffs if d < -1e-9]
    if positives and not negatives:
        return "increasing"
    if negatives and not positives:
        return "decreasing"
    if not positives and not negatives:
        return "flat"
    return "non_monotonic"


def recommendation_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        key = str(row.get("parameter_key") or "")
        if key.startswith("supplier_stock_node::"):
            supplier_id = key.split("::", 1)[1]
            parameter = "stock_fournisseur"
        elif key.startswith("supplier_capacity_node::"):
            supplier_id = key.split("::", 1)[1]
            parameter = "capacite_fournisseur"
        elif key.startswith("supplier_lead_time_node::"):
            supplier_id = key.split("::", 1)[1]
            parameter = "delai_fournisseur"
        elif key.startswith("supplier_reliability_node::"):
            supplier_id = key.split("::", 1)[1]
            parameter = "fiabilite_fournisseur"
        elif key.startswith("combined_capacity_delay::"):
            supplier_id = key.split("::", 1)[1]
            parameter = "scenario_combine_capacite_delai"
        elif key.startswith("combined_stock_reliability::"):
            supplier_id = key.split("::", 1)[1]
            parameter = "scenario_combine_stock_fiabilite"
        elif key == "supplier_stock_scale":
            supplier_id = "GLOBAL"
            parameter = "stock_fournisseur_global"
        elif key == "supplier_capacity_scale":
            supplier_id = "GLOBAL"
            parameter = "capacite_fournisseur_globale"
        elif key == "supplier_lead_time_scale":
            supplier_id = "GLOBAL"
            parameter = "delai_fournisseur_global"
        elif key == "supplier_reliability_scale":
            supplier_id = "GLOBAL"
            parameter = "fiabilite_fournisseur_globale"
        elif key.startswith("external_procurement") or key.startswith("combined_upstream"):
            supplier_id = "GLOBAL"
            parameter = "appro_amont_fournisseur"
        else:
            continue
        out.append(
            {
                "supplier_id": supplier_id,
                "parameter": parameter,
                "tested_min_acceptable_scale": row.get("baseline_contiguous_safe_low"),
                "tested_max_acceptable_scale": row.get("baseline_contiguous_safe_high"),
                "first_unacceptable_level": row.get("first_unacceptable_level"),
                "tested_levels": row.get("levels"),
                "acceptable_levels": row.get("acceptable_levels"),
                "acceptable_ranges": row.get("acceptable_ranges"),
                "acceptable_is_contiguous": row.get("acceptable_is_contiguous"),
                "max_fill_rate_drop": row.get("max_fill_rate_drop"),
                "max_product_availability_drop": row.get("max_product_availability_drop"),
                "max_line_adherence_drop": row.get("max_line_adherence_drop"),
                "max_inventory_cost_increase": row.get("max_inventory_cost_increase"),
                "capacity_reduction_margin_pct": row.get("capacity_reduction_margin_pct"),
                "stock_reduction_margin_pct": row.get("stock_reduction_margin_pct"),
                "delay_increase_margin_pct": row.get("delay_increase_margin_pct"),
                "reliability_reduction_margin_pct": row.get("reliability_reduction_margin_pct"),
                "upstream_capacity_reduction_margin_pct": row.get("upstream_capacity_reduction_margin_pct"),
                "upstream_delay_increase_margin_pct": row.get("upstream_delay_increase_margin_pct"),
                "max_external_procured_qty_delta": row.get("max_external_procured_qty_delta"),
                "max_supplier_upstream_ordered_qty_delta": row.get("max_supplier_upstream_ordered_qty_delta"),
                "max_raw_material_target_gap_increase": row.get("max_raw_material_target_gap_increase"),
                "max_raw_material_safety_floor_gap_increase": row.get("max_raw_material_safety_floor_gap_increase"),
            }
        )
    out.sort(key=lambda r: (str(r["supplier_id"]), str(r["parameter"])))
    return out


def main() -> None:
    args = parse_args()
    artifact_mode = "full" if args.keep_case_data else str(args.artifact_mode or "summary")
    input_path = Path(args.input)
    run_script = Path(args.run_script)
    baseline_result_dir = Path(args.baseline_result_dir)
    output_dir = Path(args.output_dir)
    cases_root = output_dir / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    cases_root.mkdir(parents=True, exist_ok=True)

    groups = selected_groups(args.groups)
    levels = {
        "stock": parse_levels(args.stock_levels),
        "capacity": parse_levels(args.capacity_levels),
        "lead_time": parse_levels(args.lead_time_levels),
        "reliability": parse_levels(args.reliability_levels),
        "external_capacity": parse_levels(args.external_capacity_levels),
        "external_lead": parse_levels(args.external_lead_levels),
    }

    base_data = load_json(input_path)
    supplier_nodes_all = detect_supplier_nodes(base_data)
    ranked_suppliers = rank_suppliers(baseline_result_dir, set(supplier_nodes_all))
    selected_suppliers = ranked_suppliers if args.top_suppliers <= 0 else ranked_suppliers[: args.top_suppliers]
    extra_args, supplier_floor_csv = split_supplier_floor_arg(extract_manifest_extra_args(Path(args.baseline_manifest)))

    specs = build_specs(
        groups,
        selected_suppliers,
        levels,
        {
            "capacity": args.combined_capacity_level,
            "stock": args.combined_stock_level,
            "lead_time": args.combined_lead_time_level,
            "reliability": args.combined_reliability_level,
            "upstream_capacity": args.combined_upstream_capacity_level,
            "upstream_lead": args.combined_upstream_lead_level,
        },
    )
    cases_csv = output_dir / "supplier_parameter_sensitivity_cases.csv"
    if args.summarize_existing:
        if not cases_csv.exists():
            raise FileNotFoundError(f"Cannot summarize existing study: {cases_csv} does not exist")
        print(f"[SUMMARY] Reading existing cases: {cases_csv}", flush=True)
        all_rows = read_csv(cases_csv)
        baseline_matches = [row for row in all_rows if str(row.get("parameter_key") or "") == "baseline"]
        if not baseline_matches:
            raise ValueError(f"Cannot summarize existing study: no baseline row in {cases_csv}")
        baseline_row = baseline_matches[0]
    else:
        all_rows: list[dict[str, Any]] = []
        existing_by_case_id: dict[str, dict[str, Any]] = {}
        if cases_csv.exists():
            for row in read_csv(cases_csv):
                case_id = str(row.get("case_id") or "")
                if case_id and reusable_case_row(row):
                    existing_by_case_id[case_id] = row

        print("[RUN] baseline", flush=True)
        baseline_spec = {
            "parameter_key": "baseline",
            "parameter_group": "baseline",
            "parameter_label": "Baseline",
            "safe_direction": "baseline",
        }
        if "baseline" in existing_by_case_id:
            print("[REUSE] baseline", flush=True)
            baseline_row = existing_by_case_id["baseline"]
        else:
            baseline_row = run_case(
                case_id="baseline",
                spec=baseline_spec,
                level=1.0,
                config=base_case(),
                base_data=base_data,
                run_script=run_script,
                scenario_id=args.scenario_id,
                days=args.days,
                cases_root=cases_root,
                extra_args=extra_args,
                supplier_floor_csv=supplier_floor_csv,
                artifact_mode=artifact_mode,
            )
        all_rows.append(baseline_row)

        for spec_index, spec in enumerate(specs, start=1):
            for level_index, level in enumerate(spec["levels"], start=1):
                case_id = case_id_for(str(spec["parameter_key"]), float(level))
                print(
                    f"[RUN] {spec_index:03d}/{len(specs):03d} {spec['parameter_key']} "
                    f"{level_index:02d}/{len(spec['levels']):02d} level={level}",
                    flush=True,
                )
                if case_id in existing_by_case_id:
                    print(f"[REUSE] {case_id}", flush=True)
                    row = existing_by_case_id[case_id]
                else:
                    row = run_case(
                        case_id=case_id,
                        spec=spec,
                        level=float(level),
                        config=config_for_spec(spec, float(level), selected_suppliers),
                        base_data=base_data,
                        run_script=run_script,
                        scenario_id=args.scenario_id,
                        days=args.days,
                        cases_root=cases_root,
                        extra_args=extra_args,
                        supplier_floor_csv=supplier_floor_csv,
                        artifact_mode=artifact_mode,
                    )
                all_rows.append(row)

        write_csv(cases_csv, all_rows)

    by_parameter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        parameter_key = str(row.get("parameter_key") or "")
        if parameter_key == "baseline":
            continue
        by_parameter[parameter_key].append(row)

    summary_rows = [
        summarize_parameter(
            spec,
            by_parameter.get(str(spec["parameter_key"]), []),
            baseline_row,
            service_threshold=args.service_threshold,
            cost_increase_pct=args.cost_increase_pct,
        )
        for spec in specs
    ]
    summary_rows.sort(
        key=lambda row: (
            999.0 if row.get("first_unacceptable_level") in {None, ""} else abs(
                to_float(row.get("first_unacceptable_level"), 1.0) - 1.0
            ),
            -to_float(row.get("max_fill_rate_drop"), 0.0),
            -to_float(row.get("max_product_availability_drop"), 0.0),
            -to_float(row.get("max_line_adherence_drop"), 0.0),
            str(row.get("parameter_label") or ""),
        )
    )
    summary_csv = output_dir / "supplier_parameter_threshold_summary.csv"
    write_csv(summary_csv, summary_rows)
    recommendations_csv = output_dir / "supplier_parameter_recommendations.csv"
    recommendations = recommendation_rows(summary_rows)
    write_csv(recommendations_csv, recommendations)

    critical = [row for row in summary_rows if row.get("first_unacceptable_level") not in {None, ""}][:15]
    strongest_fill = sorted(summary_rows, key=lambda row: -to_float(row.get("max_fill_rate_drop"), 0.0))[:15]
    strongest_external = sorted(
        summary_rows,
        key=lambda row: -to_float(row.get("max_external_procured_qty_delta"), 0.0),
    )[:15]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "scenario_id": args.scenario_id,
        "days": args.days,
        "groups": sorted(groups),
        "selected_suppliers": selected_suppliers,
        "service_threshold": args.service_threshold,
        "cost_increase_pct": args.cost_increase_pct,
        "manifest_extra_args": extra_args,
        "supplier_floor_csv": "" if supplier_floor_csv is None else str(supplier_floor_csv),
        "baseline": baseline_row,
        "parameter_count": len(specs),
        "simulation_count": len(all_rows),
        "critical_parameters": critical,
        "strongest_fill_effects": strongest_fill,
        "strongest_supplier_upstream_supply_effects": strongest_external,
        "strongest_external_market_effects": strongest_external,
        "recommendations_csv": str(recommendations_csv),
    }
    summary_json = output_dir / "supplier_parameter_sensitivity_summary.json"
    write_json(summary_json, summary)

    report_lines = [
        "# Supplier Parameter Sensitivity",
        "",
        "## Method",
        f"- Horizon: {args.days} days",
        f"- Scenario: {args.scenario_id}",
        f"- Groups: {', '.join(sorted(groups))}",
        f"- Suppliers swept: {', '.join(selected_suppliers) if selected_suppliers else '(none)'}",
        f"- Supplier floor calibration CSV: {supplier_floor_csv if supplier_floor_csv else '(none)'}",
        "- Baseline guardrails are not warmup-adjusted: startup behavior remains included.",
        "- Accepted case: fill rate target met, ending backlog no worse than baseline, daily backlog no worse than baseline, raw-material safety-floor and target-stock gaps no worse than baseline.",
        "",
        "## Baseline",
        f"- Fill rate: {to_float(baseline_row.get('kpi::fill_rate'), math.nan):.6f}",
        f"- Product availability: {to_float(baseline_row.get('kpi::product_availability'), math.nan):.6f}",
        f"- Line adherence: {to_float(baseline_row.get('kpi::line_adherence'), math.nan):.6f}",
        f"- Line nervousness: {to_float(baseline_row.get('kpi::line_nervousness'), math.nan):.0f}",
        f"- Ending backlog: {to_float(baseline_row.get('kpi::ending_backlog'), math.nan):.4f}",
        f"- Max daily backlog: {to_float(baseline_row.get('guard::max_daily_backlog_qty'), math.nan):.4f}",
        f"- Backlog days: {to_float(baseline_row.get('guard::backlog_days'), math.nan):.0f}",
        f"- Raw material safety-floor breach days: {to_float(baseline_row.get('guard::raw_material_safety_floor_breach_days'), math.nan):.0f}",
        f"- Raw material max target gap qty: {to_float(baseline_row.get('guard::raw_material_max_target_gap_qty'), math.nan):.4f}",
        f"- Total cost: {to_float(baseline_row.get('kpi::total_cost'), math.nan):.4f}",
        f"- Inventory holding cost: {to_float(baseline_row.get('kpi::inventory_cost'), math.nan):.4f}",
        f"- Supplier upstream ordered qty: {to_float(baseline_row.get('kpi::total_external_procured_ordered_qty'), math.nan):.4f}",
        "",
        "## Critical Parameters",
    ]
    if critical:
        for row in critical[:10]:
            report_lines.append(
                f"- {row['parameter_label']}: first unacceptable level {row['first_unacceptable_level']}, "
                f"{safe_range_label(row)}, "
                f"max fill drop {to_float(row['max_fill_rate_drop'], 0.0):.6f}, "
                f"max availability drop {to_float(row.get('max_product_availability_drop'), 0.0):.6f}, "
                f"max adherence drop {to_float(row.get('max_line_adherence_drop'), 0.0):.6f}, "
                f"max target gap increase {to_float(row.get('max_raw_material_target_gap_increase'), 0.0):.4f}"
            )
    else:
        report_lines.append("- No unacceptable supplier parameter level in the tested grid.")

    report_lines.extend(["", "## Strongest Fill Effects"])
    for row in strongest_fill[:10]:
        report_lines.append(
            f"- {row['parameter_label']}: max fill drop {to_float(row['max_fill_rate_drop'], 0.0):.6f}, "
            f"acceptable {row['acceptable_levels']}"
        )

    report_lines.extend(["", "## Strongest Supplier Upstream Supply Effects"])
    for row in strongest_external[:10]:
        report_lines.append(
            f"- {row['parameter_label']}: max supplier upstream qty delta "
            f"{to_float(row['max_supplier_upstream_ordered_qty_delta'], 0.0):.4f}, "
            f"{safe_range_label(row)}"
        )

    report_lines.extend(["", "## Minimum Tested Supplier Settings"])
    critical_recommendations = [
        row
        for row in recommendations
        if str(row.get("first_unacceptable_level") or "").strip()
        or str(row.get("supplier_id") or "") == "GLOBAL"
    ]
    if critical_recommendations:
        for row in critical_recommendations[:20]:
            report_lines.append(
                f"- {row['supplier_id']} / {row['parameter']}: "
                f"minimum acceptable scale in the continuous baseline range {row['tested_min_acceptable_scale']} "
                f"(first unacceptable {row['first_unacceptable_level'] or 'none'})"
            )
    else:
        report_lines.append("- All supplier-level stock/capacity reductions were acceptable in the tested grid.")

    report_lines.extend(
        [
            "",
            "## Files",
            "- supplier_parameter_sensitivity_cases.csv",
            "- supplier_parameter_threshold_summary.csv",
            "- supplier_parameter_recommendations.csv",
            "- supplier_parameter_sensitivity_summary.json",
            "- cases/*/input_case.json",
        ]
    )
    report_path = output_dir / "supplier_parameter_sensitivity_report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"[OK] Cases CSV: {cases_csv.resolve()}", flush=True)
    print(f"[OK] Summary CSV: {summary_csv.resolve()}", flush=True)
    print(f"[OK] Recommendations CSV: {recommendations_csv.resolve()}", flush=True)
    print(f"[OK] Summary JSON: {summary_json.resolve()}", flush=True)
    print(f"[OK] Report MD: {report_path.resolve()}", flush=True)


if __name__ == "__main__":
    main()
