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
        "--manifest-json",
        default="",
        help=(
            "Optional run_manifest.json. When provided, the Monte Carlo runner reuses the "
            "same simulation input, scenario and calibration options as the active baseline."
        ),
    )
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
        "--uncertainty-profile",
        choices=["workshop", "risk_probe", "legacy"],
        default="workshop",
        help=(
            "Sampling profile. workshop keeps perturbations close to operational uncertainty; "
            "risk_probe widens supplier-side uncertainty to reveal fragility; "
            "legacy keeps the older wider stress-style ranges."
        ),
    )
    parser.add_argument(
        "--simulator-extra-arg",
        action="append",
        default=[],
        help="Additional argument passed to run_first_simulation.py. Repeat once per token.",
    )
    parser.add_argument(
        "--keep-run-artifacts",
        action="store_true",
        help="Keep per-run folders with full simulation outputs.",
    )
    return parser.parse_args()


def sample_factor(rng: random.Random, lo: float, mode: float, hi: float) -> float:
    return round(rng.triangular(lo, hi, mode), 6)


def detect_supplier_nodes(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for n in data.get("nodes", []) or []:
        if str(n.get("type") or "").lower() == "supplier_dc":
            node_id = str(n.get("id") or "")
            if node_id:
                out.append(node_id)
    return sorted(set(out))


def detect_supplier_edge_sources(data: dict[str, Any]) -> list[str]:
    suppliers = set(detect_supplier_nodes(data))
    out: list[str] = []
    for e in data.get("edges", []) or []:
        src = str(e.get("from") or "")
        if src in suppliers:
            out.append(src)
    return sorted(set(out))


def extract_manifest_command(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = load_json(manifest_path)
    command = [str(x) for x in (manifest.get("simulator_command") or [])]
    if not command:
        raise ValueError(f"No simulator_command found in manifest: {manifest_path}")

    script_idx = next((i for i, tok in enumerate(command) if tok.endswith("run_first_simulation.py")), None)
    if script_idx is None:
        script_idx = 1 if len(command) > 1 else 0
    run_script = Path(command[script_idx])

    input_path = Path(str(manifest.get("input_graph") or ""))
    scenario_id = str(manifest.get("scenario_id") or "scn:BASE")
    manifest_days = int(to_float(manifest.get("days"), 0.0))
    extra_args: list[str] = []

    base_value_flags = {
        "--input",
        "--output-dir",
        "--scenario-id",
        "--days",
        "--map-script",
        "--map-output",
        "--output-profile",
    }
    base_bool_flags = {"--skip-map", "--skip-plots"}
    i = script_idx + 1
    while i < len(command):
        tok = command[i]
        if tok in base_value_flags:
            val = command[i + 1] if i + 1 < len(command) else ""
            if tok == "--input" and val:
                input_path = Path(val)
            elif tok == "--scenario-id" and val:
                scenario_id = val
            elif tok == "--days" and val:
                manifest_days = int(to_float(val, manifest_days))
            i += 2
            continue
        if tok in base_bool_flags:
            i += 1
            continue
        extra_args.append(tok)
        if tok.startswith("--") and i + 1 < len(command) and not command[i + 1].startswith("--"):
            extra_args.append(command[i + 1])
            i += 2
        else:
            i += 1

    return {
        "manifest_path": str(manifest_path),
        "input_path": str(input_path),
        "run_script": str(run_script),
        "scenario_id": scenario_id,
        "manifest_days": manifest_days,
        "simulator_extra_args": extra_args,
    }


def factor_specs(profile: str) -> tuple[dict[str, tuple[float, float, float]], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    if profile == "legacy":
        return (
            {
                "lead_time_scale": (0.8, 1.0, 1.3),
                "transport_cost_scale": (0.8, 1.0, 1.4),
                "supplier_stock_scale": (0.7, 1.0, 1.5),
                "production_stock_scale": (0.8, 1.0, 1.3),
            },
            (0.7, 1.0, 1.3),
            (0.7, 1.0, 1.3),
            (0.75, 1.0, 1.15),
            (0.75, 1.0, 1.15),
            (0.85, 1.0, 1.25),
            (0.95, 1.0, 1.0),
        )
    if profile == "risk_probe":
        return (
            {
                "demand_scale": (0.90, 1.0, 1.15),
                "lead_time_scale": (0.90, 1.0, 1.50),
                "transport_cost_scale": (0.90, 1.0, 1.20),
                "supplier_stock_scale": (0.60, 1.0, 1.10),
                "production_stock_scale": (0.85, 1.0, 1.05),
                "supplier_capacity_scale": (0.60, 1.0, 1.05),
                "supplier_reliability_scale": (0.90, 1.0, 1.0),
                "external_procurement_daily_cap_days_scale": (0.60, 1.0, 1.05),
                "external_procurement_lead_days_scale": (0.90, 1.0, 1.60),
                "holding_cost_scale": (0.90, 1.0, 1.12),
            },
            (0.85, 1.0, 1.20),
            (0.85, 1.0, 1.05),
            (0.50, 1.0, 1.10),
            (0.60, 1.0, 1.05),
            (0.90, 1.0, 1.80),
            (0.90, 1.0, 1.0),
        )
    return (
        {
            "demand_scale": (0.96, 1.0, 1.06),
            "lead_time_scale": (0.95, 1.0, 1.15),
            "transport_cost_scale": (0.95, 1.0, 1.10),
            "supplier_stock_scale": (0.85, 1.0, 1.05),
            "production_stock_scale": (0.90, 1.0, 1.05),
            "supplier_capacity_scale": (0.85, 1.0, 1.05),
            "external_procurement_daily_cap_days_scale": (0.85, 1.0, 1.05),
            "external_procurement_lead_days_scale": (0.95, 1.0, 1.20),
            "holding_cost_scale": (0.95, 1.0, 1.08),
        },
        (0.95, 1.0, 1.08),
        (0.90, 1.0, 1.05),
        (0.85, 1.0, 1.05),
        (0.85, 1.0, 1.05),
        (0.95, 1.0, 1.20),
        (0.97, 1.0, 1.0),
    )


def metric_probability(rows: list[dict[str, Any]], metric: str, predicate) -> float | None:
    values = [to_float(r.get(metric), float("nan")) for r in rows if r.get("status") == "ok"]
    values = [v for v in values if not math.isnan(v)]
    if not values:
        return None
    return sum(1 for v in values if predicate(v)) / float(len(values))


def arg_value(args: list[str], flag: str) -> str:
    for i, token in enumerate(args):
        if token == flag and i + 1 < len(args):
            return args[i + 1]
    return ""


def replace_arg_value(args: list[str], flag: str, value: str) -> list[str]:
    out = list(args)
    for i, token in enumerate(out):
        if token == flag and i + 1 < len(out):
            out[i + 1] = value
            return out
    out.extend([flag, value])
    return out


def scaled_value(raw: Any, factor: float, *, minimum: float = 0.0) -> str:
    value = to_float(raw, float("nan"))
    if math.isnan(value):
        return str(raw if raw is not None else "")
    return str(round(max(minimum, value * factor), 6))


def write_scaled_supplier_neutral_floors(
    source_csv: Path,
    target_csv: Path,
    *,
    factors: dict[str, float],
    supplier_node_scale: dict[str, float],
    supplier_capacity_node_scale: dict[str, float],
    edge_src_lead_time_scale: dict[str, float],
    edge_src_reliability_scale: dict[str, float],
) -> bool:
    if not source_csv.exists():
        return False
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    stock_cols = {
        "neutral_opening_stock_floor_qty",
        "simulated_opening_stock_qty",
        "base_stock_qty",
    }
    capacity_cols = {
        "neutral_capacity_floor_qty_per_day",
        "effective_capacity_qty_per_day",
        "tested_capacity_floor_qty_per_day",
        "external_procurement_nominal_capacity_qty_per_day",
    }
    lead_cols = {
        "planned_lead_time_days",
        "lead_reference_days",
        "lead_cover_days",
        "delay_step_limit",
        "external_procurement_lead_days",
    }
    pipeline_cols = {
        "external_procurement_pipeline_target_qty",
        "external_procurement_initial_pipeline_seed_qty",
    }
    reliability_cols = {"nominal_reliability_otif"}

    with source_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for row in rows:
        supplier_id = str(row.get("supplier_id") or "")
        stock_factor = to_float(factors.get("supplier_stock_scale"), 1.0) * to_float(
            supplier_node_scale.get(supplier_id), 1.0
        )
        capacity_factor = to_float(factors.get("supplier_capacity_scale"), 1.0) * to_float(
            supplier_capacity_node_scale.get(supplier_id), 1.0
        )
        lead_factor = to_float(factors.get("lead_time_scale"), 1.0) * to_float(
            edge_src_lead_time_scale.get(supplier_id), 1.0
        )
        reliability_factor = to_float(factors.get("supplier_reliability_scale"), 1.0) * to_float(
            edge_src_reliability_scale.get(supplier_id), 1.0
        )
        for col in stock_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), stock_factor)
        for col in capacity_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), capacity_factor)
        for col in lead_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), lead_factor, minimum=1.0)
        for col in pipeline_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), lead_factor)
        for col in reliability_cols:
            if col in row:
                value = to_float(row.get(col), float("nan"))
                if not math.isnan(value):
                    row[col] = str(round(min(1.0, max(0.01, value * reliability_factor)), 6))

    with target_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def main() -> None:
    args = parse_args()
    manifest_config: dict[str, Any] = {}
    if args.manifest_json:
        manifest_config = extract_manifest_command(Path(args.manifest_json))

    input_path = Path(manifest_config.get("input_path") or args.input)
    run_script = Path(manifest_config.get("run_script") or args.run_script)
    scenario_id = str(manifest_config.get("scenario_id") or args.scenario_id)
    simulator_extra_args = list(manifest_config.get("simulator_extra_args") or [])
    simulator_extra_args.extend(str(arg) for arg in (args.simulator_extra_arg or []))
    supplier_neutral_floors_csv = arg_value(simulator_extra_args, "--supplier-neutral-floors-csv")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    if args.keep_run_artifacts:
        runs_dir.mkdir(parents=True, exist_ok=True)

    base_data = load_json(input_path)
    demand_items = detect_demand_items(base_data, scenario_id)
    production_nodes = detect_production_nodes(base_data)
    supplier_nodes = detect_supplier_nodes(base_data)
    supplier_edge_sources = detect_supplier_edge_sources(base_data)

    rng = random.Random(args.seed)

    # Triangular distributions (lo, mode, hi).
    (
        global_factor_spec,
        demand_spec_default,
        production_capacity_spec_default,
        supplier_stock_spec_default,
        supplier_capacity_spec_default,
        supplier_lead_spec_default,
        supplier_reliability_spec_default,
    ) = factor_specs(args.uncertainty_profile)
    demand_factor_spec: dict[str, tuple[float, float, float]] = {
        item: demand_spec_default for item in demand_items
    }
    capacity_factor_spec: dict[str, tuple[float, float, float]] = {
        node: production_capacity_spec_default for node in production_nodes
    }
    supplier_stock_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_stock_spec_default for node in supplier_nodes
    }
    supplier_capacity_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_capacity_spec_default for node in supplier_nodes
    }
    supplier_lead_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_lead_spec_default for node in supplier_edge_sources
    }
    supplier_reliability_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_reliability_spec_default for node in supplier_edge_sources
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
            "supplier_capacity_scale": 1.0,
            "supplier_reliability_scale": 1.0,
            "external_procurement_daily_cap_days_scale": 1.0,
            "external_procurement_lead_days_scale": 1.0,
            "holding_cost_scale": 1.0,
        }
        demand_item_scale = {item: 1.0 for item in demand_items}
        capacity_node_scale = {node: 1.0 for node in production_nodes}
        supplier_node_scale = {node: 1.0 for node in supplier_nodes}
        supplier_capacity_node_scale = {node: 1.0 for node in supplier_nodes}
        edge_src_lead_time_scale = {node: 1.0 for node in supplier_edge_sources}
        edge_src_reliability_scale = {node: 1.0 for node in supplier_edge_sources}

        if not is_baseline:
            for k, (lo, mode, hi) in global_factor_spec.items():
                factors[k] = sample_factor(rng, lo, mode, hi)
            for item, (lo, mode, hi) in demand_factor_spec.items():
                demand_item_scale[item] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in capacity_factor_spec.items():
                capacity_node_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in supplier_stock_factor_spec.items():
                supplier_node_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in supplier_capacity_factor_spec.items():
                supplier_capacity_node_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in supplier_lead_factor_spec.items():
                edge_src_lead_time_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in supplier_reliability_factor_spec.items():
                edge_src_reliability_scale[node] = sample_factor(rng, lo, mode, hi)

        row: dict[str, Any] = {
            "run_id": run_id,
            "is_baseline": is_baseline,
            "status": "ok",
            "error": "",
        }
        row.update({f"factor::{k}": v for k, v in factors.items()})
        row.update({f"demand_item::{k}": v for k, v in demand_item_scale.items()})
        row.update({f"capacity_node::{k}": v for k, v in capacity_node_scale.items()})
        row.update({f"supplier_stock_node::{k}": v for k, v in supplier_node_scale.items()})
        row.update({f"supplier_capacity_node::{k}": v for k, v in supplier_capacity_node_scale.items()})
        row.update({f"supplier_lead_node::{k}": v for k, v in edge_src_lead_time_scale.items()})
        row.update({f"supplier_reliability_node::{k}": v for k, v in edge_src_reliability_scale.items()})

        print(f"[RUN] {i+1:03d}/{total_runs:03d} {run_id}")

        try:
            mutated = apply_scales(
                base_data=base_data,
                scenario_id=scenario_id,
                factors=factors,
                demand_item_scale=demand_item_scale,
                capacity_node_scale=capacity_node_scale,
                supplier_node_scale=supplier_node_scale,
                supplier_capacity_node_scale=supplier_capacity_node_scale,
                edge_src_lead_time_scale=edge_src_lead_time_scale,
                edge_src_reliability_scale=edge_src_reliability_scale,
            )

            if args.keep_run_artifacts:
                case_dir = runs_dir / run_id
                case_dir.mkdir(parents=True, exist_ok=True)
                case_input = case_dir / "input_case.json"
                case_output = case_dir / "simulation_output"
                run_extra_args = list(simulator_extra_args)
                neutral_floors_csv = arg_value(run_extra_args, "--supplier-neutral-floors-csv")
                if neutral_floors_csv:
                    case_neutral_floors = case_dir / "supplier_neutral_floors_case.csv"
                    wrote_neutral_floors = write_scaled_supplier_neutral_floors(
                        Path(neutral_floors_csv),
                        case_neutral_floors,
                        factors=factors,
                        supplier_node_scale=supplier_node_scale,
                        supplier_capacity_node_scale=supplier_capacity_node_scale,
                        edge_src_lead_time_scale=edge_src_lead_time_scale,
                        edge_src_reliability_scale=edge_src_reliability_scale,
                    )
                    if wrote_neutral_floors:
                        run_extra_args = replace_arg_value(
                            run_extra_args,
                            "--supplier-neutral-floors-csv",
                            str(case_neutral_floors),
                        )
                write_json(case_input, mutated)
                summary, _ = run_simulation(
                    run_script=run_script,
                    input_json=case_input,
                    output_dir=case_output,
                    scenario_id=scenario_id,
                    days=args.days,
                    skip_map=True,
                    skip_plots=True,
                    extra_args=run_extra_args,
                )
                row["case_dir"] = str(case_dir)
            else:
                with tempfile.TemporaryDirectory(prefix=f"mc_{safe_name(run_id)}_") as tmp:
                    case_dir = Path(tmp)
                    case_input = case_dir / "input_case.json"
                    case_output = case_dir / "simulation_output"
                    run_extra_args = list(simulator_extra_args)
                    neutral_floors_csv = arg_value(run_extra_args, "--supplier-neutral-floors-csv")
                    if neutral_floors_csv:
                        case_neutral_floors = case_dir / "supplier_neutral_floors_case.csv"
                        wrote_neutral_floors = write_scaled_supplier_neutral_floors(
                            Path(neutral_floors_csv),
                            case_neutral_floors,
                            factors=factors,
                            supplier_node_scale=supplier_node_scale,
                            supplier_capacity_node_scale=supplier_capacity_node_scale,
                            edge_src_lead_time_scale=edge_src_lead_time_scale,
                            edge_src_reliability_scale=edge_src_reliability_scale,
                        )
                        if wrote_neutral_floors:
                            run_extra_args = replace_arg_value(
                                run_extra_args,
                                "--supplier-neutral-floors-csv",
                                str(case_neutral_floors),
                            )
                    write_json(case_input, mutated)
                    summary, _ = run_simulation(
                        run_script=run_script,
                        input_json=case_input,
                        output_dir=case_output,
                        scenario_id=scenario_id,
                        days=args.days,
                        skip_map=True,
                        skip_plots=True,
                        extra_args=run_extra_args,
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
    stochastic_ok_rows = [r for r in ok_rows if not bool(r.get("is_baseline"))]
    distribution_rows = stochastic_ok_rows or ok_rows
    failed_rows = [r for r in rows if r.get("status") != "ok"]
    baseline = next((r for r in ok_rows if bool(r.get("is_baseline"))), None)
    if baseline is None:
        raise RuntimeError("Baseline Monte Carlo run failed.")

    kpi_cols = sorted([k for k in baseline.keys() if k.startswith("kpi::")])
    factor_prefixes = (
        "factor::",
        "demand_item::",
        "capacity_node::",
        "supplier_stock_node::",
        "supplier_capacity_node::",
        "supplier_lead_node::",
        "supplier_reliability_node::",
    )
    factor_cols = sorted([k for k in baseline.keys() if k.startswith(factor_prefixes)])

    metric_stats: dict[str, Any] = {}
    for k in kpi_cols:
        values = [to_float(r.get(k), float("nan")) for r in distribution_rows]
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
        xs = [to_float(r.get(fc), float("nan")) for r in distribution_rows]
        if any(math.isnan(x) for x in xs):
            continue
        correlations[fc] = {}
        for mk in corr_targets:
            ys = [to_float(r.get(mk), float("nan")) for r in distribution_rows]
            if any(math.isnan(y) for y in ys):
                continue
            correlations[fc][mk] = pearson_corr(xs, ys)

    def top_runs(metric: str, reverse: bool, n: int = 10) -> list[dict[str, Any]]:
        candidates = []
        for r in distribution_rows:
            val = to_float(r.get(metric), float("nan"))
            if math.isnan(val):
                continue
            candidates.append({"run_id": r["run_id"], metric: val})
        candidates.sort(key=lambda x: to_float(x.get(metric), 0.0), reverse=reverse)
        return candidates[:n]

    driver_rankings: dict[str, list[dict[str, Any]]] = {}
    for target in corr_targets:
        ranked: list[dict[str, Any]] = []
        for factor, target_corrs in correlations.items():
            corr = to_float(target_corrs.get(target), float("nan"))
            if math.isnan(corr):
                continue
            ranked.append({"factor": factor, "correlation": corr, "absolute_correlation": abs(corr)})
        ranked.sort(key=lambda x: x["absolute_correlation"], reverse=True)
        driver_rankings[target] = ranked[:12]

    decision_metrics = {
        "fill_rate_below_100pct": metric_probability(distribution_rows, "kpi::fill_rate", lambda v: v < 0.999999),
        "fill_rate_below_99pct": metric_probability(distribution_rows, "kpi::fill_rate", lambda v: v < 0.99),
        "backlog_positive": metric_probability(distribution_rows, "kpi::ending_backlog", lambda v: v > 1e-9),
        "total_cost_above_baseline": metric_probability(
            distribution_rows,
            "kpi::total_cost",
            lambda v: v > to_float(baseline.get("kpi::total_cost"), float("inf")),
        ),
        "inventory_cost_above_baseline": metric_probability(
            distribution_rows,
            "kpi::total_inventory_cost_legacy_raw_holding",
            lambda v: v > to_float(baseline.get("kpi::total_inventory_cost_legacy_raw_holding"), float("inf")),
        ),
        "supplier_capacity_binding_above_baseline": metric_probability(
            distribution_rows,
            "kpi::total_supplier_capacity_binding_qty",
            lambda v: v > to_float(baseline.get("kpi::total_supplier_capacity_binding_qty"), float("inf")),
        ),
    }

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "manifest": manifest_config,
        "scenario_id": scenario_id,
        "days_override": args.days,
        "seed": args.seed,
        "uncertainty_profile": args.uncertainty_profile,
        "simulator_extra_args": simulator_extra_args,
        "supplier_neutral_floors_adjusted_per_run": bool(supplier_neutral_floors_csv),
        "supplier_neutral_floors_source_csv": supplier_neutral_floors_csv,
        "runs_requested_excluding_baseline": args.runs,
        "runs_total_including_baseline": total_runs,
        "successful_runs": len(ok_rows),
        "successful_stochastic_runs": len(stochastic_ok_rows),
        "failed_runs": len(failed_rows),
        "factor_distributions": {
            "global": global_factor_spec,
            "demand_item_scale": demand_factor_spec,
            "capacity_node_scale": capacity_factor_spec,
            "supplier_stock_node_scale": supplier_stock_factor_spec,
            "supplier_capacity_node_scale": supplier_capacity_factor_spec,
            "supplier_lead_node_scale": supplier_lead_factor_spec,
            "supplier_reliability_node_scale": supplier_reliability_factor_spec,
        },
        "metric_statistics": metric_stats,
        "decision_metrics": decision_metrics,
        "factor_kpi_correlations_pearson": correlations,
        "driver_rankings": driver_rankings,
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
- Scenario: {scenario_id}
- Days override: {args.days}
- Seed: {args.seed}
- Uncertainty profile: {args.uncertainty_profile}
- Runs requested (excluding baseline): {args.runs}
- Runs total (including baseline): {total_runs}
- Runs success: {len(ok_rows)}
- Stochastic runs success: {len(stochastic_ok_rows)}
- Runs failed: {len(failed_rows)}
- Keep run artifacts: {args.keep_run_artifacts}

## Decision Metrics
{json.dumps(decision_metrics, indent=2, ensure_ascii=False)}

## KPI Statistics (distribution over successful runs)
{json.dumps(metric_stats, indent=2, ensure_ascii=False)}

## Top Drivers
{json.dumps(driver_rankings, indent=2, ensure_ascii=False)}

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
