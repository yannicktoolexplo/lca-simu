#!/usr/bin/env python3
"""Rebuild the MRP-seeded lot-policy baseline with a finished-goods cycle-stock target."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import apply_scales, load_json, run_simulation, to_float, write_json
from etudecas.simulation.result_paths import report_path, summary_path


SCENARIO_PATCH = {
    "warmup_days": 0,
    "reset_backlog_after_warmup": False,
    "fg_target_days": 0.0,
    "demand_stock_target_days": 14.0,
    "initialization_policy": {
        "mode": "explicit_state",
        "state_scale": 0.02,
        "factory_input_on_hand_days": 0.0,
        "supplier_output_on_hand_days": 1.0,
        "distribution_center_on_hand_days": 3.0,
        "customer_on_hand_days": 0.0,
        "seed_in_transit": True,
        "in_transit_fill_ratio": 1.0,
        "seed_estimated_source_pipeline": True,
    },
    "estimated_source_requirement_cap_by_item": {
        "item:042342": 12.0,
        "item:333362": 8.0,
        "item:344135": 8.0,
        "item:338928": 10.0,
        "item:338929": 10.0,
    },
}

FACTORY_LOT_EXECUTION_POLICY = {
    "M-1430": {
        "item:268967": {
            "max_lots_per_week": 10,
            "source": "industrial_confirmation_2026-04-13",
        }
    },
    "M-1810": {
        "item:268091": {
            "max_lots_per_week": 10,
            "source": "industrial_confirmation_2026-04-13",
        }
    },
}

FACTORY_LOT_SIZING_OVERRIDES = {
    "M-1810": {
        "item:268091": {
            "lot_multiple_qty": 14400.0,
            "source": "industrial_confirmation_2026-04-13",
        }
    }
}

SUPPLIER_CAPACITY_OVERRIDES = {
    "SDC-VD0901566A": {
        "item:338928": {
            "capacity_qty_per_day": 64.935065,
            "basis": "peer_packaging_alignment",
        }
    }
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild MRP lot-policy baseline with calibrated FG cycle stock.")
    parser.add_argument(
        "--source",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json",
        help="Source graph JSON with MRP stocks and lot policies.",
    )
    parser.add_argument(
        "--output-graph",
        default="etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json",
        help="Output graph JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated",
        help="Simulation output directory.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id to rebuild.")
    parser.add_argument("--days", type=int, default=365, help="Measured horizon in days.")
    parser.add_argument(
        "--skip-simulation",
        action="store_true",
        help="Only write the patched graph without running the simulation.",
    )
    parser.add_argument(
        "--skip-map",
        action="store_true",
        help="Skip map regeneration when the final simulation is executed.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Skip plot regeneration when the final simulation is executed.",
    )
    return parser.parse_args()


def load_summary_file(path: Path) -> dict:
    if not path.exists():
        return {}
    return load_json(path)


def infer_nominal_lot_qty(proc: dict) -> float:
    lot_sizing = proc.get("lot_sizing") or {}
    fixed_lot_qty = max(0.0, to_float(lot_sizing.get("fixed_lot_qty"), 0.0))
    if fixed_lot_qty > 1e-9:
        return fixed_lot_qty
    max_lot_qty = max(0.0, to_float(lot_sizing.get("max_lot_qty"), 0.0))
    if max_lot_qty > 1e-9:
        return max_lot_qty
    min_lot_qty = max(0.0, to_float(lot_sizing.get("min_lot_qty"), 0.0))
    if min_lot_qty > 1e-9:
        return min_lot_qty
    return 0.0


def apply_factory_lot_execution_policy(
    data: dict,
    overrides: dict[str, dict[str, dict[str, float | str]]],
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    nodes_by_id = {
        str(node.get("id")): node
        for node in (data.get("nodes") or [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    for node_id, item_map in overrides.items():
        node = nodes_by_id.get(node_id)
        if not isinstance(node, dict):
            continue
        for proc in (node.get("processes") or []):
            outputs = proc.get("outputs") or []
            if not outputs:
                continue
            out_item = str((outputs[0] or {}).get("item_id") or "")
            payload = item_map.get(out_item)
            if not payload:
                continue
            max_lots_per_week = max(0.0, to_float(payload.get("max_lots_per_week"), 0.0))
            lot_execution = proc.get("lot_execution")
            if not isinstance(lot_execution, dict):
                lot_execution = {}
            lot_execution["max_lots_per_week"] = max_lots_per_week
            lot_execution["source"] = str(payload.get("source") or "override")
            proc["lot_execution"] = lot_execution

            capacity = proc.get("capacity")
            if not isinstance(capacity, dict):
                capacity = {}
            current_cap = max(0.0, to_float(capacity.get("max_rate"), 0.0))
            nominal_lot_qty = infer_nominal_lot_qty(proc)
            if nominal_lot_qty > 1e-9 and max_lots_per_week > 0:
                weekly_equivalent_daily_cap = (nominal_lot_qty * max_lots_per_week) / 7.0
                capacity["max_rate"] = round(max(current_cap, weekly_equivalent_daily_cap), 6)
                capacity["source"] = f"lot_week_equivalent_from_{lot_execution['source']}"
            proc["capacity"] = capacity
            rows.append(
                {
                    "node_id": node_id,
                    "item_id": out_item,
                    "max_lots_per_week": round(max_lots_per_week, 6),
                    "nominal_lot_qty": round(nominal_lot_qty, 6),
                    "capacity_qty_per_day": round(max(0.0, to_float(capacity.get("max_rate"), 0.0)), 6),
                    "source": str(lot_execution.get("source") or ""),
                }
            )
    return rows


def apply_factory_lot_sizing_overrides(
    data: dict,
    overrides: dict[str, dict[str, dict[str, float | str]]],
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    nodes_by_id = {
        str(node.get("id")): node
        for node in (data.get("nodes") or [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    for node_id, item_map in overrides.items():
        node = nodes_by_id.get(node_id)
        if not isinstance(node, dict):
            continue
        for proc in (node.get("processes") or []):
            outputs = proc.get("outputs") or []
            if not outputs:
                continue
            out_item = str((outputs[0] or {}).get("item_id") or "")
            payload = item_map.get(out_item)
            if not payload:
                continue
            lot_sizing = proc.get("lot_sizing")
            if not isinstance(lot_sizing, dict):
                lot_sizing = {}
            lot_sizing["lot_multiple_qty"] = round(max(0.0, to_float(payload.get("lot_multiple_qty"), 0.0)), 6)
            lot_sizing["source"] = str(payload.get("source") or lot_sizing.get("source") or "override")
            proc["lot_sizing"] = lot_sizing
            rows.append(
                {
                    "node_id": node_id,
                    "item_id": out_item,
                    "lot_multiple_qty": round(max(0.0, to_float(lot_sizing.get("lot_multiple_qty"), 0.0)), 6),
                    "source": str(lot_sizing.get("source") or ""),
                }
            )
    return rows


def apply_supplier_capacity_overrides(data: dict, overrides: dict[str, dict[str, dict[str, float | str]]]) -> None:
    if not overrides:
        return
    nodes_by_id = {
        str(node.get("id")): node
        for node in (data.get("nodes") or [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    for node_id, item_map in overrides.items():
        node = nodes_by_id.get(node_id)
        if not isinstance(node, dict):
            continue
        sim_constraints = node.get("simulation_constraints")
        if not isinstance(sim_constraints, dict):
            sim_constraints = {}
        qty_map = sim_constraints.get("supplier_item_capacity_qty_per_day")
        if not isinstance(qty_map, dict):
            qty_map = {}
        basis_map = sim_constraints.get("supplier_item_capacity_basis")
        if not isinstance(basis_map, dict):
            basis_map = {}
        for item_id, payload in item_map.items():
            qty_map[item_id] = round(float(payload.get("capacity_qty_per_day", 0.0)), 6)
            basis_map[item_id] = str(payload.get("basis") or "override")
        sim_constraints["supplier_item_capacity_qty_per_day"] = qty_map
        sim_constraints["supplier_item_capacity_basis"] = basis_map
        node["simulation_constraints"] = sim_constraints


def compute_availability_kpis(output_dir: Path, summary: dict) -> dict[str, dict[str, float]]:
    demand_csv_path = output_dir / "data" / "production_demand_service_daily.csv"
    if not demand_csv_path.exists():
        return {}
    objective_days = max(0.0, to_float((((summary or {}).get("policy") or {}).get("demand_stock_target_days")), 0.0))
    if objective_days <= 0.0:
        return {}

    demand_by_item_day: dict[str, dict[int, float]] = {}
    available_by_item_day: dict[str, dict[int, float]] = {}
    with demand_csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            item_id = str(row.get("item_id") or "")
            day = int(to_float(row.get("day"), 0.0))
            demand_by_item_day.setdefault(item_id, {})[day] = max(0.0, to_float(row.get("demand_qty"), 0.0))
            available_by_item_day.setdefault(item_id, {})[day] = max(0.0, to_float(row.get("available_before_service_qty"), 0.0))
    avg_daily_demand_by_item = {
        item_id: (sum(day_map.values()) / max(1, len(day_map)))
        for item_id, day_map in demand_by_item_day.items()
    }

    item_metrics: dict[str, dict[str, float]] = {}
    for item_id, day_stock in sorted(available_by_item_day.items()):
        demand_day_map = demand_by_item_day.get(item_id, {})
        if not demand_day_map:
            continue
        sorted_days = sorted(day_stock)
        coverage_values: list[float] = []
        days_meeting = 0
        for day in sorted_days:
            avg_daily_demand = max(0.0, avg_daily_demand_by_item.get(item_id, 0.0))
            coverage_days = (day_stock.get(day, 0.0) / avg_daily_demand) if avg_daily_demand > 1e-9 else math.inf
            coverage_values.append(coverage_days)
            if coverage_days + 1e-9 >= objective_days:
                days_meeting += 1
        if not coverage_values:
            continue
        item_metrics[item_id] = {
            "objective_days": round(objective_days, 4),
            "avg_coverage_days": round(sum(coverage_values) / len(coverage_values), 4),
            "min_coverage_days": round(min(coverage_values), 4),
            "ending_coverage_days": round(coverage_values[-1], 4),
            "days_meeting_objective_pct": round(100.0 * days_meeting / len(coverage_values), 2),
            "avg_daily_demand": round(avg_daily_demand_by_item.get(item_id, 0.0), 4),
        }
    return item_metrics


def compute_plan_adherence_kpis(output_dir: Path) -> dict[str, dict[str, float]]:
    csv_path = output_dir / "data" / "production_constraint_daily.csv"
    if not csv_path.exists():
        return {}
    factory_rows: dict[str, dict[str, float]] = {}
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            node_id = str(row.get("node_id") or "")
            stats = factory_rows.setdefault(
                node_id,
                {
                    "desired_qty": 0.0,
                    "planned_qty_after_lot_rule": 0.0,
                    "actual_qty": 0.0,
                    "shortfall_vs_desired_qty": 0.0,
                    "shortfall_vs_lot_plan_qty": 0.0,
                    "days": 0.0,
                    "capacity_days": 0.0,
                    "input_shortage_days": 0.0,
                    "weekly_lot_limit_days": 0.0,
                },
            )
            stats["desired_qty"] += max(0.0, to_float(row.get("desired_qty"), 0.0))
            stats["planned_qty_after_lot_rule"] += max(0.0, to_float(row.get("planned_qty_after_lot_rule"), 0.0))
            stats["actual_qty"] += max(0.0, to_float(row.get("actual_qty"), 0.0))
            stats["shortfall_vs_desired_qty"] += max(0.0, to_float(row.get("shortfall_vs_desired_qty"), 0.0))
            stats["shortfall_vs_lot_plan_qty"] += max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty"), 0.0))
            stats["days"] += 1
            binding_cause = str(row.get("binding_cause") or "")
            if binding_cause == "capacity":
                stats["capacity_days"] += 1
            if binding_cause == "input_shortage":
                stats["input_shortage_days"] += 1
            if binding_cause == "weekly_lot_limit":
                stats["weekly_lot_limit_days"] += 1
    for stats in factory_rows.values():
        planned = stats["planned_qty_after_lot_rule"]
        desired = stats["desired_qty"]
        actual = stats["actual_qty"]
        stats["adherence_to_executable_plan_pct"] = round((100.0 * actual / planned), 2) if planned > 1e-9 else 100.0
        stats["plan_uplift_vs_desired_pct"] = round((100.0 * max(0.0, planned - desired) / desired), 2) if desired > 1e-9 else 0.0
        stats["capacity_days_pct"] = round((100.0 * stats["capacity_days"] / stats["days"]), 2) if stats["days"] > 0 else 0.0
        stats["input_shortage_days_pct"] = round((100.0 * stats["input_shortage_days"] / stats["days"]), 2) if stats["days"] > 0 else 0.0
        stats["weekly_lot_limit_days_pct"] = round((100.0 * stats["weekly_lot_limit_days"] / stats["days"]), 2) if stats["days"] > 0 else 0.0
    return factory_rows


def compute_cost_kpis(summary: dict) -> dict[str, float]:
    kpis = (summary or {}).get("kpis") or {}
    inventory_cost = (
        max(0.0, to_float(kpis.get("total_holding_cost"), 0.0))
        + max(0.0, to_float(kpis.get("total_warehouse_operating_cost"), 0.0))
        + max(0.0, to_float(kpis.get("total_inventory_risk_cost"), 0.0))
    )
    return {
        "inventory_cost": round(inventory_cost, 4),
        "transport_cost": round(max(0.0, to_float(kpis.get("total_transport_cost"), 0.0)), 4),
        "purchase_cost": round(max(0.0, to_float(kpis.get("total_purchase_cost"), 0.0)), 4),
        "total_logistics_cost": round(max(0.0, to_float(kpis.get("total_logistics_cost"), 0.0)), 4),
        "total_cost": round(max(0.0, to_float(kpis.get("total_cost"), 0.0)), 4),
    }


def collect_run_metrics(output_dir: Path) -> dict[str, dict]:
    summary = load_summary_file(summary_path(output_dir, "first_simulation_summary.json"))
    if not summary:
        return {}
    return {
        "summary": summary,
        "availability": compute_availability_kpis(output_dir, summary),
        "plan": compute_plan_adherence_kpis(output_dir),
        "cost": compute_cost_kpis(summary),
    }


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    output_graph_path = Path(args.output_graph)
    output_dir = Path(args.output_dir)
    run_script = Path("etudecas/simulation/run_first_simulation.py")
    previous_metrics = collect_run_metrics(output_dir)

    data = load_json(source_path)
    data = apply_scales(
        data,
        args.scenario_id,
        factors={},
    )
    applied_factory_lot_rows = apply_factory_lot_execution_policy(data, FACTORY_LOT_EXECUTION_POLICY)
    applied_factory_lot_sizing_rows = apply_factory_lot_sizing_overrides(data, FACTORY_LOT_SIZING_OVERRIDES)
    apply_supplier_capacity_overrides(data, SUPPLIER_CAPACITY_OVERRIDES)
    scenario = next((s for s in (data.get("scenarios") or []) if str(s.get("id")) == args.scenario_id), None)
    if scenario is None:
        raise ValueError(f"Scenario '{args.scenario_id}' not found in source graph.")
    for key, value in SCENARIO_PATCH.items():
        scenario[key] = value

    meta = data.get("meta") or {}
    meta["mrp_lot_policy_rebuild"] = {
        "type": "mrp_lot_policy_lot_execution_rebuild",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_graph": str(source_path),
        "scenario_id": args.scenario_id,
        "days": int(args.days),
        "scenario_patch": SCENARIO_PATCH,
        "factory_lot_execution_policy": FACTORY_LOT_EXECUTION_POLICY,
        "applied_factory_lot_execution_rows": applied_factory_lot_rows,
        "factory_lot_sizing_overrides": FACTORY_LOT_SIZING_OVERRIDES,
        "applied_factory_lot_sizing_rows": applied_factory_lot_sizing_rows,
        "supplier_capacity_overrides": SUPPLIER_CAPACITY_OVERRIDES,
    }
    data["meta"] = meta
    write_json(output_graph_path, data)

    if args.skip_simulation:
        return

    summary, _stdout = run_simulation(
        run_script=run_script,
        input_json=output_graph_path,
        output_dir=output_dir,
        scenario_id=args.scenario_id,
        days=args.days,
        skip_map=args.skip_map,
        skip_plots=args.skip_plots,
    )
    current_metrics = collect_run_metrics(output_dir)
    summary = current_metrics.get("summary") or summary
    availability = current_metrics.get("availability") or {}
    plan = current_metrics.get("plan") or {}
    cost = current_metrics.get("cost") or {}

    lines = [
        "# MRP Lot-Policy Rebuild",
        "",
        f"- Source graph: `{source_path}`",
        f"- Output graph: `{output_graph_path}`",
        f"- Scenario id: `{args.scenario_id}`",
        f"- Measured horizon: `{args.days}` days",
        f"- Applied patch: `{SCENARIO_PATCH}`",
        f"- Applied factory lot-execution policy: `{FACTORY_LOT_EXECUTION_POLICY}`",
        f"- Applied factory lot-sizing overrides: `{FACTORY_LOT_SIZING_OVERRIDES}`",
        f"- Applied supplier capacity overrides: `{SUPPLIER_CAPACITY_OVERRIDES}`",
        "",
        "## Availability KPI",
    ]
    for item_id, stats in sorted(availability.items()):
        lines.append(
            f"- {item_id}: objective `{stats['objective_days']:.1f} j`, avg demand `{stats['avg_daily_demand']:.1f}/j`, "
            f"avg coverage `{stats['avg_coverage_days']:.1f} j`, ending coverage `{stats['ending_coverage_days']:.1f} j`, "
            f"days >= objective `{stats['days_meeting_objective_pct']:.1f}%`"
        )
    lines.extend(["", "## Factory Plan Adherence"])
    for node_id, stats in sorted(plan.items()):
        lines.append(
            f"- {node_id}: adherence executable plan `{stats['adherence_to_executable_plan_pct']:.1f}%`, "
            f"lot uplift vs desired `{stats['plan_uplift_vs_desired_pct']:.1f}%`, "
            f"plan gap `{stats['shortfall_vs_lot_plan_qty']:.1f}`, input-shortage days `{stats['input_shortage_days_pct']:.1f}%`, "
            f"weekly-lot-limit days `{stats['weekly_lot_limit_days_pct']:.1f}%`, capacity days `{stats['capacity_days_pct']:.1f}%`"
        )
    lines.extend(
        [
            "",
            "## Cost KPI",
            f"- Inventory cost: `{cost.get('inventory_cost')}`",
            f"- Transport cost: `{cost.get('transport_cost')}`",
            f"- Total logistics cost: `{cost.get('total_logistics_cost')}`",
            f"- Total cost: `{cost.get('total_cost')}`",
            f"- Simulation summary file: `{summary_path(output_dir, 'first_simulation_summary.json')}`",
            f"- Simulation report file: `{report_path(output_dir, 'first_simulation_report.md')}`",
        ]
    )
    if previous_metrics:
        prev_availability = previous_metrics.get("availability") or {}
        prev_plan = previous_metrics.get("plan") or {}
        prev_cost = previous_metrics.get("cost") or {}
        lines.extend(["", "## Delta Vs Previous Run"])
        for item_id, stats in sorted(availability.items()):
            prev = prev_availability.get(item_id)
            if not prev:
                continue
            lines.append(
                f"- {item_id}: days >= objective `{stats['days_meeting_objective_pct'] - prev.get('days_meeting_objective_pct', 0.0):+.1f} pts`, "
                f"ending coverage `{stats['ending_coverage_days'] - prev.get('ending_coverage_days', 0.0):+.1f} j`"
            )
        for node_id, stats in sorted(plan.items()):
            prev = prev_plan.get(node_id)
            if not prev:
                continue
            lines.append(
                f"- {node_id}: executable-plan adherence `{stats['adherence_to_executable_plan_pct'] - prev.get('adherence_to_executable_plan_pct', 0.0):+.1f} pts`, "
                f"lot uplift vs desired `{stats['plan_uplift_vs_desired_pct'] - prev.get('plan_uplift_vs_desired_pct', 0.0):+.1f} pts`, "
                f"input-shortage days `{stats['input_shortage_days_pct'] - prev.get('input_shortage_days_pct', 0.0):+.1f} pts`"
            )
        lines.append(
            f"- Costs: inventory `{cost.get('inventory_cost', 0.0) - prev_cost.get('inventory_cost', 0.0):+.1f}`, "
            f"transport `{cost.get('transport_cost', 0.0) - prev_cost.get('transport_cost', 0.0):+.1f}`, "
            f"total `{cost.get('total_cost', 0.0) - prev_cost.get('total_cost', 0.0):+.1f}`"
        )
    report_file = report_path(output_dir, "mrp_lot_policy_rebuild_report.md")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
