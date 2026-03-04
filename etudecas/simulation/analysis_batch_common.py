#!/usr/bin/env python3
"""
Common helpers for sensitivity and Monte Carlo simulation batches.
"""

from __future__ import annotations

import copy
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def choose_scenario(data: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    scenarios = data.get("scenarios", []) or []
    for scn in scenarios:
        if str(scn.get("id")) == scenario_id:
            return scn
    return scenarios[0] if scenarios else {"id": scenario_id, "demand": []}


def detect_production_nodes(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for n in data.get("nodes", []) or []:
        if n.get("processes"):
            out.append(str(n.get("id")))
    return sorted(set(out))


def detect_demand_items(data: dict[str, Any], scenario_id: str) -> list[str]:
    scn = choose_scenario(data, scenario_id)
    items = [str(d.get("item_id")) for d in (scn.get("demand", []) or []) if d.get("item_id") is not None]
    return sorted(set(items))


def scale_profile_values(profile: list[dict[str, Any]], factor: float) -> None:
    if factor <= 0:
        raise ValueError(f"Invalid non-positive scale factor: {factor}")
    for p in profile:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "constant")).lower()
        if ptype in {"constant", "step"} and "value" in p:
            p["value"] = round(max(0.0, to_float(p.get("value"), 0.0) * factor), 6)
        elif ptype == "piecewise":
            points = p.get("points") or []
            for pt in points:
                if isinstance(pt, dict) and "value" in pt:
                    pt["value"] = round(max(0.0, to_float(pt.get("value"), 0.0) * factor), 6)


def apply_scales(
    base_data: dict[str, Any],
    scenario_id: str,
    factors: dict[str, float],
    demand_item_scale: dict[str, float] | None = None,
    capacity_node_scale: dict[str, float] | None = None,
) -> dict[str, Any]:
    data = copy.deepcopy(base_data)
    demand_item_scale = demand_item_scale or {}
    capacity_node_scale = capacity_node_scale or {}
    production_nodes = set(detect_production_nodes(data))

    demand_global_scale = to_float(factors.get("demand_scale", 1.0), 1.0)
    lead_time_scale = to_float(factors.get("lead_time_scale", 1.0), 1.0)
    transport_cost_scale = to_float(factors.get("transport_cost_scale", 1.0), 1.0)
    supplier_stock_scale = to_float(factors.get("supplier_stock_scale", 1.0), 1.0)
    production_stock_scale = to_float(factors.get("production_stock_scale", 1.0), 1.0)
    capacity_global_scale = to_float(factors.get("capacity_scale", 1.0), 1.0)
    safety_stock_days_scale = to_float(factors.get("safety_stock_days_scale", 1.0), 1.0)
    review_period_scale = to_float(factors.get("review_period_scale", 1.0), 1.0)
    supplier_reliability_scale = to_float(factors.get("supplier_reliability_scale", 1.0), 1.0)

    if any(
        v <= 0
        for v in [
            demand_global_scale,
            lead_time_scale,
            transport_cost_scale,
            supplier_stock_scale,
            production_stock_scale,
            capacity_global_scale,
            safety_stock_days_scale,
            review_period_scale,
            supplier_reliability_scale,
        ]
    ):
        raise ValueError("All factors must be strictly positive.")

    scn = choose_scenario(data, scenario_id)
    for d in (scn.get("demand", []) or []):
        item_id = str(d.get("item_id"))
        scale = demand_global_scale * to_float(demand_item_scale.get(item_id, 1.0), 1.0)
        scale_profile_values(d.get("profile") or [], scale)
    base_safety_days = to_float(scn.get("safety_stock_days", 7.0), 7.0)
    base_review_days = to_float(scn.get("review_period_days", 1.0), 1.0)
    scn["safety_stock_days"] = round(max(0.0, base_safety_days * safety_stock_days_scale), 6)
    scn["review_period_days"] = max(1, int(round(max(1.0, base_review_days * review_period_scale))))

    for n in data.get("nodes", []) or []:
        node_id = str(n.get("id"))
        node_cap_scale = to_float(capacity_node_scale.get(node_id, 1.0), 1.0) * capacity_global_scale
        if node_cap_scale <= 0:
            raise ValueError(f"Invalid capacity scale for node {node_id}: {node_cap_scale}")
        for p in (n.get("processes") or []):
            cap = p.get("capacity") or {}
            if "max_rate" in cap:
                cap["max_rate"] = round(max(0.0, to_float(cap.get("max_rate"), 0.0) * node_cap_scale), 6)
            p["capacity"] = cap

        inv = n.get("inventory") or {}
        states = inv.get("states") or []
        inv_factor = production_stock_scale if node_id in production_nodes else supplier_stock_scale
        for st in states:
            if "initial" in st:
                st["initial"] = round(max(0.0, to_float(st.get("initial"), 0.0) * inv_factor), 6)
        inv["states"] = states
        n["inventory"] = inv

    for e in data.get("edges", []) or []:
        lead = e.get("lead_time") or {}
        for k in ["mean", "min", "max"]:
            if k in lead:
                lead[k] = round(max(0.05, to_float(lead.get(k), 0.0) * lead_time_scale), 6)
        e["lead_time"] = lead

        tc = e.get("transport_cost") or {}
        if "value" in tc:
            tc["value"] = round(max(0.0, to_float(tc.get("value"), 0.0) * transport_cost_scale), 6)
        e["transport_cost"] = tc

        service_level = e.get("service_level") or {}
        base_rel = to_float(service_level.get("otif", e.get("otif", 1.0)), 1.0)
        service_level["otif"] = round(min(1.0, max(0.01, base_rel * supplier_reliability_scale)), 6)
        e["service_level"] = service_level

    return data


def run_simulation(
    run_script: Path,
    input_json: Path,
    output_dir: Path,
    scenario_id: str,
    days: int = 0,
    skip_map: bool = True,
    skip_plots: bool = True,
) -> tuple[dict[str, Any], str]:
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
    ]
    if days > 0:
        cmd.extend(["--days", str(days)])
    if skip_map:
        cmd.append("--skip-map")
    if skip_plots:
        cmd.append("--skip-plots")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        message = "\n".join([part for part in [stdout, stderr] if part]).strip()
        raise RuntimeError(f"Simulation failed for {input_json}:\n{message}")

    summary_path = output_dir / "first_simulation_summary.json"
    summary = load_json(summary_path)
    return summary, proc.stdout


def numeric_kpis(summary: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in (summary.get("kpis") or {}).items():
        fv = to_float(v, math.nan)
        if math.isnan(fv):
            continue
        out[str(k)] = fv
    return out


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    q = min(1.0, max(0.0, q))
    pos = q * (len(sorted_values) - 1)
    i = int(math.floor(pos))
    j = int(math.ceil(pos))
    if i == j:
        return sorted_values[i]
    w = pos - i
    return sorted_values[i] * (1.0 - w) + sorted_values[j] * w


def pearson_corr(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 2:
        return float("nan")
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs[:n], ys[:n]))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs[:n]))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys[:n]))
    if denx <= 0 or deny <= 0:
        return float("nan")
    return num / (denx * deny)
