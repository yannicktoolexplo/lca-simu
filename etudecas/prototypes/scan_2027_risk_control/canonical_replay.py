from __future__ import annotations

"""Stage-1 reinjection of SCAN response playbooks into the canonical engine.

The canonical engine currently exposes scalar scenario and graph policies rather
than a day-by-day external controller port.  This module therefore implements a
transparent first integration step:

* each fixed playbook is translated into a documented canonical graph overlay;
* the adaptive sequence is converted into a duration-weighted overlay;
* all overlays are replayed in the full multi-item engine with paired seeds;
* the exact translation assumptions are exported for audit.

A true daily write-back interface remains a 2027 engine evolution.  The code is
kept separate from the canonical engine so the research mapping can be reviewed
before any production hook is added.
"""

import copy
import csv
import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import Action, clamp, safe_float
from .risk_mapping import build_canonical_risk_events


DEFAULT_CANONICAL_GRAPH_CANDIDATES: tuple[str, ...] = (
    "etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json",
    "etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json",
    "etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json",
)


def discover_canonical_graph(repo_root: Path, explicit: str = "auto") -> Path | None:
    if explicit != "auto":
        path = Path(explicit)
        if not path.is_absolute():
            path = repo_root / path
        return path.resolve() if path.exists() else None
    for relative in DEFAULT_CANONICAL_GRAPH_CANDIDATES:
        candidate = (repo_root / relative).resolve()
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def expand_action_schedule(
    decisions: pd.DataFrame,
    actions: Sequence[Action],
    days: int,
) -> pd.DataFrame:
    by_name = {action.name: action for action in actions}
    reference = by_name.get("mrp_reference") or actions[0]
    schedule = pd.DataFrame({"day": np.arange(days, dtype=int)})
    schedule["policy"] = reference.name
    if not decisions.empty and "day" in decisions and "selected_policy" in decisions:
        ordered = decisions.sort_values("day")
        for _, row in ordered.iterrows():
            start = int(row["day"])
            name = str(row["selected_policy"])
            if name in by_name:
                schedule.loc[schedule["day"] >= start, "policy"] = name
    for field in ("order_gain", "production_gain", "expedite", "smoothing", "safety_stock_gain", "supplier_relief"):
        schedule[field] = schedule["policy"].map({name: getattr(action, field) for name, action in by_name.items()}).astype(float)
    return schedule


def duration_weighted_action(schedule: pd.DataFrame, *, name: str = "adaptive_weighted_replay") -> Action:
    if schedule.empty:
        return Action(name, 0, 0, 0, 0.25, 0, 0, "Empty adaptive schedule; MRP-equivalent overlay.")
    means = {field: float(schedule[field].mean()) for field in (
        "order_gain", "production_gain", "expedite", "smoothing", "safety_stock_gain", "supplier_relief"
    )}
    return Action(
        name=name,
        description="Duration-weighted canonical replay of the adaptive reduced-order policy schedule.",
        **means,
    )


def _choose_scenario(graph: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    scenarios = graph.get("scenarios") or []
    for scenario in scenarios:
        if str(scenario.get("id")) == scenario_id:
            return scenario
    if scenarios:
        return scenarios[0]
    scenario = {"id": scenario_id, "demand": []}
    graph["scenarios"] = [scenario]
    return scenario


def action_to_overlay_ledger(action: Action, graph: Mapping[str, Any], scenario_id: str) -> dict[str, Any]:
    scenario = next(
        (item for item in (graph.get("scenarios") or []) if str(item.get("id")) == scenario_id),
        (graph.get("scenarios") or [{}])[0] if (graph.get("scenarios") or []) else {},
    )
    base_safety = max(0.0, safe_float(scenario.get("safety_stock_days"), 7.0))
    base_fg = max(0.0, safe_float(scenario.get("fg_target_days"), 0.0))
    base_gap = max(0.01, safe_float(scenario.get("production_gap_gain"), 0.25))
    base_smoothing = clamp(safe_float(scenario.get("production_smoothing"), 0.20), 0.0, 0.95)
    econ = scenario.get("economic_policy") if isinstance(scenario.get("economic_policy"), dict) else {}
    base_external_cap = max(0.0, safe_float(econ.get("external_procurement_daily_cap_days"), 2.0))
    base_external_lead = max(0.0, safe_float(econ.get("external_procurement_lead_days"), 4.0))
    base_external_cost = max(0.1, safe_float(econ.get("external_procurement_cost_multiplier"), 2.0))

    target_smoothing = clamp(
        max(base_smoothing, 0.10 + 0.80 * action.smoothing + 0.10 * action.supplier_relief),
        0.0,
        0.95,
    )
    target_gap = clamp(
        base_gap * (1.0 + action.production_gain - 0.25 * action.supplier_relief),
        0.02,
        1.50,
    )
    return {
        "policy": action.name,
        "action": asdict(action),
        "scenario_patch": {
            "safety_stock_days": max(0.0, base_safety + 2.5 * action.safety_stock_gain + 1.5 * max(0.0, action.order_gain)),
            "fg_target_days": max(0.0, base_fg + 0.8 * max(0.0, action.safety_stock_gain)),
            "production_gap_gain": target_gap,
            "production_smoothing": target_smoothing,
            "external_procurement_daily_cap_days": max(0.0, base_external_cap * (1.0 + 1.8 * action.expedite + 0.7 * max(0.0, action.order_gain))),
            "external_procurement_lead_days": max(0.0, base_external_lead * (1.0 - 0.55 * action.expedite)),
            "external_procurement_cost_multiplier": base_external_cost * (1.0 + 0.35 * action.expedite),
        },
        "graph_scales": {
            "factory_capacity": max(0.50, 1.0 + action.production_gain),
            "opening_inventory": max(0.50, 1.0 + 0.18 * action.safety_stock_gain),
            "transport_lead_time": max(0.50, 1.0 - 0.35 * action.expedite),
        },
        "interpretation": {
            "order_gain": "Translated through safety-stock and external-procurement headroom; canonical MRP has no direct external order-gain port.",
            "supplier_relief": "Translated through stronger production smoothing and a lower production gap gain.",
            "adaptive_schedule": "A duration-weighted overlay is used in this stage-1 replay; daily controller write-back is not claimed.",
        },
    }


def apply_action_overlay_to_graph(
    graph: Mapping[str, Any],
    action: Action,
    *,
    scenario_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = copy.deepcopy(dict(graph))
    ledger = action_to_overlay_ledger(action, data, scenario_id)
    scenario = _choose_scenario(data, scenario_id)
    patch = ledger["scenario_patch"]
    scenario["safety_stock_days"] = round(patch["safety_stock_days"], 6)
    scenario["fg_target_days"] = round(patch["fg_target_days"], 6)
    scenario["production_gap_gain"] = round(patch["production_gap_gain"], 6)
    scenario["production_smoothing"] = round(patch["production_smoothing"], 6)
    econ = scenario.get("economic_policy")
    if not isinstance(econ, dict):
        econ = {}
    econ["external_procurement_daily_cap_days"] = round(patch["external_procurement_daily_cap_days"], 6)
    econ["external_procurement_lead_days"] = int(round(patch["external_procurement_lead_days"]))
    econ["external_procurement_cost_multiplier"] = round(patch["external_procurement_cost_multiplier"], 6)
    scenario["economic_policy"] = econ

    capacity_scale = safe_float(ledger["graph_scales"]["factory_capacity"], 1.0)
    inventory_scale = safe_float(ledger["graph_scales"]["opening_inventory"], 1.0)
    lead_scale = safe_float(ledger["graph_scales"]["transport_lead_time"], 1.0)
    process_count = 0
    inventory_state_count = 0
    edge_count = 0
    for node in data.get("nodes") or []:
        for process in node.get("processes") or []:
            capacity = process.get("capacity")
            if isinstance(capacity, dict) and "max_rate" in capacity:
                capacity["max_rate"] = round(max(0.0, safe_float(capacity.get("max_rate")) * capacity_scale), 6)
                capacity["scan_control_source"] = action.name
                process_count += 1
        inventory = node.get("inventory")
        if isinstance(inventory, dict):
            for state in inventory.get("states") or []:
                if "initial" in state:
                    state["initial"] = round(max(0.0, safe_float(state.get("initial")) * inventory_scale), 6)
                    inventory_state_count += 1
    for edge in data.get("edges") or []:
        lead = edge.get("lead_time")
        if not isinstance(lead, dict):
            continue
        changed = False
        for key in ("mean", "min", "max"):
            if key in lead:
                lead[key] = round(max(0.05, safe_float(lead.get(key)) * lead_scale), 6)
                changed = True
        if changed:
            lead["scan_control_source"] = action.name
            edge_count += 1

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["scan_control_overlay"] = {
        "schema_version": "scan.canonical_overlay.v1",
        "policy": action.name,
        "ledger": ledger,
        "applied_counts": {
            "process_capacities": process_count,
            "inventory_states": inventory_state_count,
            "edge_lead_times": edge_count,
        },
    }
    data["metadata"] = metadata
    ledger["applied_counts"] = metadata["scan_control_overlay"]["applied_counts"]
    return data, ledger


def _first_existing(paths: Sequence[Path]) -> Path | None:
    return next((path for path in paths if path.exists() and path.stat().st_size > 0), None)


def extract_canonical_kpis(result_dir: Path) -> dict[str, float]:
    daily_path = _first_existing([
        result_dir / "data" / "first_simulation_daily.csv",
        result_dir / "first_simulation_daily.csv",
    ])
    if daily_path is None:
        return {}
    daily = pd.read_csv(daily_path)
    demand = pd.to_numeric(daily.get("demand", daily.get("demand_qty", 0.0)), errors="coerce").fillna(0.0)
    served = pd.to_numeric(daily.get("served", daily.get("served_qty", 0.0)), errors="coerce").fillna(0.0)
    backlog = pd.to_numeric(daily.get("backlog_end", daily.get("backlog", 0.0)), errors="coerce").fillna(0.0)
    inventory = pd.to_numeric(daily.get("inventory_total", daily.get("inventory", 0.0)), errors="coerce").fillna(0.0)
    orders = pd.to_numeric(
        daily.get("estimated_source_ordered_qty", 0.0), errors="coerce"
    ).fillna(0.0) + pd.to_numeric(daily.get("external_procured_ordered_qty", 0.0), errors="coerce").fillna(0.0)
    total_cost = pd.to_numeric(
        daily.get("total_economic_exposure_day", daily.get("total_supply_cost_day", 0.0)), errors="coerce"
    ).fillna(0.0)
    scale = max(float(demand.replace(0.0, np.nan).median()), 1.0)
    service = served.sum() / max(demand.sum(), 1e-9)
    nervousness = float(orders.diff().abs().sum() / scale)
    return {
        "service": float(service),
        "service_loss": float(1.0 - service),
        "backlog_area_days": float(backlog.sum() / scale),
        "max_backlog_days": float(backlog.max() / scale),
        "mean_inventory_days": float(inventory.mean() / scale),
        "order_nervousness": nervousness,
        "total_economic_exposure": float(total_cost.sum()),
    }


def _paired_canonical_summary(runs: pd.DataFrame) -> pd.DataFrame:
    successful = runs.loc[runs["status"] == "ok"].copy()
    if successful.empty or "mrp_reference" not in set(successful["policy"]):
        return pd.DataFrame()
    metric_names = [
        "service", "service_loss", "backlog_area_days", "max_backlog_days",
        "mean_inventory_days", "order_nervousness", "total_economic_exposure",
    ]
    reference = successful.loc[successful["policy"] == "mrp_reference"].set_index("seed")
    rows: list[dict[str, Any]] = []
    for policy, group in successful.groupby("policy", sort=False):
        aligned = group.set_index("seed").join(reference[metric_names], rsuffix="_reference")
        row: dict[str, Any] = {"policy": policy, "paired_seed_count": int(len(aligned))}
        for metric in metric_names:
            delta = aligned[metric] - aligned[f"{metric}_reference"]
            row[f"mean_delta_{metric}"] = float(delta.mean())
            row[f"p90_delta_{metric}"] = float(delta.quantile(0.90))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("mean_delta_service_loss").reset_index(drop=True)


def prepare_canonical_overlay_package(
    *,
    graph_path: Path,
    decisions: pd.DataFrame,
    actions: Sequence[Action],
    output_root: Path,
    days: int,
    scenario_id: str = "scn:BASE",
    selected_policy_names: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write canonical input graphs without executing the heavy engine."""

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    schedule = expand_action_schedule(decisions, actions, days)
    adaptive_action = duration_weighted_action(schedule)
    by_name = {action.name: action for action in actions}
    names = list(selected_policy_names or [
        "mrp_reference", "balanced_robust", "supplier_relief",
        "service_protection", "reactive_buffer",
    ])
    policies = [by_name[name] for name in names if name in by_name]
    policies.append(adaptive_action)
    output_root.mkdir(parents=True, exist_ok=True)
    schedule.to_csv(output_root / "adaptive_control_schedule.csv", index=False)
    rows: list[dict[str, Any]] = []
    for action in policies:
        patched, ledger = apply_action_overlay_to_graph(graph, action, scenario_id=scenario_id)
        policy_root = output_root / action.name
        policy_root.mkdir(parents=True, exist_ok=True)
        (policy_root / "canonical_input_graph.json").write_text(
            json.dumps(patched, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (policy_root / "control_overlay_ledger.json").write_text(
            json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        rows.append({
            "policy": action.name,
            **{f"action_{key}": value for key, value in asdict(action).items() if key != "description"},
            **{f"scenario_{key}": value for key, value in ledger["scenario_patch"].items()},
            **{f"scale_{key}": value for key, value in ledger["graph_scales"].items()},
        })
    overlays = pd.DataFrame(rows)
    overlays.to_csv(output_root / "canonical_control_overlays.csv", index=False)
    return schedule, overlays


def run_canonical_replays(
    *,
    repo_root: Path,
    graph_path: Path,
    decisions: pd.DataFrame,
    actions: Sequence[Action],
    seeds: Sequence[int],
    output_root: Path,
    days: int,
    scenario_id: str = "scn:BASE",
    engine_script: Path | None = None,
    python_executable: str | None = None,
    selected_policy_names: Sequence[str] | None = None,
    prediction_path: Path | None = None,
    physical_risk_envelope: pd.DataFrame | None = None,
    risk_top_pairs: int = 3,
    prediction_horizon_days: int = 30,
    enable_state_dependent_risks: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    schedule = expand_action_schedule(decisions, actions, days)
    adaptive_action = duration_weighted_action(schedule)
    by_name = {action.name: action for action in actions}
    policies: list[Action] = []
    names = list(selected_policy_names or [
        "mrp_reference", "balanced_robust", "supplier_relief", "service_protection", "reactive_buffer"
    ])
    for name in names:
        if name in by_name and by_name[name] not in policies:
            policies.append(by_name[name])
    policies.append(adaptive_action)

    output_root.mkdir(parents=True, exist_ok=True)
    schedule.to_csv(output_root / "adaptive_control_schedule.csv", index=False)
    risk_events, risk_mapping_ledger = build_canonical_risk_events(
        prediction_path, physical_risk_envelope,
        days=days, top_pairs=risk_top_pairs,
        prediction_horizon_days=prediction_horizon_days, conservative=True,
    )
    risk_csv_path: Path | None = None
    if not risk_events.empty:
        risk_csv_path = output_root / "canonical_supplier_risk_events.csv"
        risk_events.to_csv(risk_csv_path, index=False)
        risk_mapping_ledger.to_csv(output_root / "canonical_risk_mapping_ledger.csv", index=False)
    engine = engine_script or (repo_root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py")
    interpreter = python_executable or sys.executable
    run_rows: list[dict[str, Any]] = []
    overlay_rows: list[dict[str, Any]] = []
    for action in policies:
        patched, ledger = apply_action_overlay_to_graph(graph, action, scenario_id=scenario_id)
        policy_root = output_root / action.name
        policy_root.mkdir(parents=True, exist_ok=True)
        input_path = policy_root / "canonical_input_graph.json"
        ledger_path = policy_root / "control_overlay_ledger.json"
        input_path.write_text(json.dumps(patched, indent=2, ensure_ascii=False), encoding="utf-8")
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
        overlay_rows.append({
            "policy": action.name,
            **{f"action_{key}": value for key, value in asdict(action).items() if key != "description"},
            **{f"scenario_{key}": value for key, value in ledger["scenario_patch"].items()},
            **{f"scale_{key}": value for key, value in ledger["graph_scales"].items()},
        })
        for seed in seeds:
            result_dir = policy_root / f"seed_{int(seed)}"
            cmd = [
                interpreter,
                str(engine),
                "--input", str(input_path),
                "--output-dir", str(result_dir),
                "--scenario-id", scenario_id,
                "--days", str(int(days)),
                "--seed", str(int(seed)),
                "--output-profile", "compact",
                "--skip-map",
                "--skip-plots",
                "--no-lot-trace",
                "--skip-lot-audit",
            ]
            if enable_state_dependent_risks:
                cmd.append("--supplier-state-dependent-risks")
            if risk_csv_path is not None:
                cmd.extend(["--supplier-risk-events-csv", str(risk_csv_path)])
            try:
                proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
                if proc.returncode != 0:
                    run_rows.append({
                        "policy": action.name,
                        "seed": int(seed),
                        "status": "failed",
                        "returncode": int(proc.returncode),
                        "error": (proc.stderr or proc.stdout)[-2000:],
                        "result_dir": str(result_dir),
                    })
                    continue
                kpis = extract_canonical_kpis(result_dir)
                run_rows.append({
                    "policy": action.name,
                    "seed": int(seed),
                    "status": "ok",
                    "returncode": 0,
                    "error": "",
                    "result_dir": str(result_dir),
                    **kpis,
                })
            except OSError as exc:
                run_rows.append({
                    "policy": action.name,
                    "seed": int(seed),
                    "status": "failed",
                    "returncode": -1,
                    "error": str(exc),
                    "result_dir": str(result_dir),
                })
    runs = pd.DataFrame(run_rows)
    overlays = pd.DataFrame(overlay_rows)
    summary = _paired_canonical_summary(runs)
    return runs, summary, overlays
