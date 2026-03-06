#!/usr/bin/env python3
"""
Targeted review of model assumptions, policies and targeted disruptions.

This script tests how much results depend on the currently unsourced special
input of M-1810, using the detected item from the prepared graph.
"""

from __future__ import annotations

import copy
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from analysis_batch_common import load_json, numeric_kpis, run_simulation, write_json


ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = ROOT / "run_first_simulation.py"
BASE_INPUT = ROOT / "sensibility" / "shock_campaign_result" / "cases" / "baseline" / "input_case.json"
FULL_SAMPLES = ROOT / "result" / "full_system_exploration_samples.csv"
CRITICAL_MATERIALS = ROOT / "result" / "critical_input_materials_analysis.csv"
OUT_DIR = ROOT / "result" / "model_assumption_review"
DEFAULT_SPECIAL_SUPPLIER_ID = "SDC-1450"
DEFAULT_SPECIAL_SUPPLIER_NAME = "Supplier of Raw Materials - D1450"
DEFAULT_SPECIAL_SUPPLIER_LOCATION = "France - GAILLAC - 81600"
DEFAULT_SPECIAL_SUPPLIER_LAT = 43.901816
DEFAULT_SPECIAL_SUPPLIER_LON = 1.896506


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def choose_scenario(data: dict[str, Any]) -> dict[str, Any]:
    scenarios = data.get("scenarios") or []
    return scenarios[0] if scenarios else {}


def find_node(data: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in data.get("nodes") or []:
        if str(node.get("id")) == node_id:
            return node
    raise KeyError(f"Unknown node: {node_id}")


def find_edge(data: dict[str, Any], edge_id: str) -> dict[str, Any]:
    for edge in data.get("edges") or []:
        if str(edge.get("id")) == edge_id:
            return edge
    raise KeyError(f"Unknown edge: {edge_id}")


def scenario_policy(data: dict[str, Any]) -> dict[str, Any]:
    scn = choose_scenario(data)
    econ = scn.get("economic_policy")
    if not isinstance(econ, dict):
        econ = {}
        scn["economic_policy"] = econ
    return econ


def ensure_inventory_state(
    node: dict[str, Any],
    item_id: str,
    *,
    initial: float,
    uom: str,
    state_id: str | None = None,
    source: str = "model_assumption_review",
) -> dict[str, Any]:
    inv = node.setdefault("inventory", {})
    states = inv.setdefault("states", [])
    for state in states:
        if str(state.get("item_id")) == item_id:
            state["initial"] = round(max(0.0, initial), 6)
            if uom:
                state["uom"] = uom
            return state
    new_state = {
        "item_id": item_id,
        "state_id": state_id or f"I_{item_id.split(':')[-1]}_ASSUMED",
        "initial": round(max(0.0, initial), 6),
        "uom": uom,
        "holding_cost": {
            "value": 0.00004,
            "per": "unit*day",
            "is_default": False,
            "source": source,
        },
        "is_default_initial": False,
        "initial_source": source,
        "uom_source": source,
    }
    states.append(new_state)
    return new_state


def set_inventory_initial(data: dict[str, Any], node_id: str, item_id: str, initial: float) -> None:
    node = find_node(data, node_id)
    inv = node.setdefault("inventory", {})
    states = inv.setdefault("states", [])
    for state in states:
        if str(state.get("item_id")) == item_id:
            state["initial"] = round(max(0.0, initial), 6)
            return
    ensure_inventory_state(node, item_id, initial=initial, uom="G")


def scale_inventory_initial(data: dict[str, Any], node_id: str, item_id: str, factor: float) -> None:
    node = find_node(data, node_id)
    for state in (node.get("inventory") or {}).get("states", []) or []:
        if str(state.get("item_id")) == item_id:
            state["initial"] = round(max(0.0, safe_float(state.get("initial")) * factor), 6)
            return


def remove_edge(data: dict[str, Any], edge_id: str) -> None:
    data["edges"] = [edge for edge in (data.get("edges") or []) if str(edge.get("id")) != edge_id]


def remove_inventory_state(data: dict[str, Any], node_id: str, item_id: str) -> None:
    node = find_node(data, node_id)
    inv = node.setdefault("inventory", {})
    inv["states"] = [s for s in (inv.get("states") or []) if str(s.get("item_id")) != item_id]


def has_inbound_edge(data: dict[str, Any], dst_node_id: str, item_id: str) -> bool:
    return any(
        str(edge.get("to")) == dst_node_id and item_id in (edge.get("items") or [])
        for edge in (data.get("edges") or [])
    )


def detect_special_item_config(data: dict[str, Any]) -> dict[str, Any]:
    node = find_node(data, "M-1810")
    preferred = ["item:007923", "item:693710"]
    candidates: list[tuple[int, str, str]] = []
    for proc in node.get("processes") or []:
        for inp in proc.get("inputs") or []:
            item_id = str(inp.get("item_id"))
            if has_inbound_edge(data, "M-1810", item_id):
                continue
            unit = str(inp.get("ratio_unit") or "G")
            priority = preferred.index(item_id) if item_id in preferred else len(preferred)
            candidates.append((priority, item_id, unit))
    if not candidates:
        return {
            "special_item_id": "item:007923",
            "special_item_code": "007923",
            "special_item_unit": "G",
            "gaillac_edge_id": "edge:SDC-1450_TO_M-1810_007923_Q",
            "alt_edge_id": "edge:SDC-VD0519670A_TO_M-1810_007923_ASSUMED",
            "local_supplier_id": "SDC-ASSUMED-007923",
            "local_edge_id": "edge:SDC-ASSUMED-007923_TO_M-1810_007923",
        }
    _, item_id, unit = sorted(candidates)[0]
    code = item_id.split(":")[-1]
    return {
        "special_item_id": item_id,
        "special_item_code": code,
        "special_item_unit": unit,
        "gaillac_edge_id": f"edge:{DEFAULT_SPECIAL_SUPPLIER_ID}_TO_M-1810_{code}_Q",
        "alt_edge_id": f"edge:SDC-VD0519670A_TO_M-1810_{code}_ASSUMED",
        "local_supplier_id": f"SDC-ASSUMED-{code}",
        "local_edge_id": f"edge:SDC-ASSUMED-{code}_TO_M-1810_{code}",
    }


def special_case_ids(config: dict[str, Any]) -> dict[str, str]:
    code = str(config["special_item_code"])
    return {
        "no_supplier_mapping": f"hyp_{code}_no_supplier_mapping",
        "reroute_existing": f"hyp_{code}_vd0519670a",
        "dedicated_local": f"hyp_{code}_dedicated_local",
        "gaillac_outage": f"disrupt_{code}_gaillac_outage_5d",
    }


def ensure_default_special_mapping(data: dict[str, Any], config: dict[str, Any]) -> None:
    item_id = str(config["special_item_id"])
    edge_id = str(config["gaillac_edge_id"])
    if has_inbound_edge(data, "M-1810", item_id):
        return
    add_supplier_node_if_missing(
        data,
        node_id=DEFAULT_SPECIAL_SUPPLIER_ID,
        name=DEFAULT_SPECIAL_SUPPLIER_NAME,
        location_id=DEFAULT_SPECIAL_SUPPLIER_LOCATION,
        lat=DEFAULT_SPECIAL_SUPPLIER_LAT,
        lon=DEFAULT_SPECIAL_SUPPLIER_LON,
    )
    add_supplier_mapping(
        data,
        src_node_id=DEFAULT_SPECIAL_SUPPLIER_ID,
        dst_node_id="M-1810",
        item_id=item_id,
        initial_qty=3000.0,
        uom=str(config["special_item_unit"]),
        lead_days=8.0,
        transport_cost_per_unit=0.05,
        edge_id=edge_id,
        assumption_label=f"GAILLAC_{config['special_item_code']}",
    )


def remove_special_supplier_mapping(data: dict[str, Any], config: dict[str, Any]) -> None:
    remove_edge(data, str(config["gaillac_edge_id"]))
    remove_inventory_state(data, DEFAULT_SPECIAL_SUPPLIER_ID, str(config["special_item_id"]))


def add_supplier_node_if_missing(
    data: dict[str, Any],
    *,
    node_id: str,
    name: str,
    location_id: str,
    lat: float,
    lon: float,
    country: str = "France",
) -> dict[str, Any]:
    for node in data.get("nodes") or []:
        if str(node.get("id")) == node_id:
            return node
    node = {
        "id": node_id,
        "type": "supplier_dc",
        "name": name,
        "location_ID": location_id,
        "country": country,
        "lat": lat,
        "lon": lon,
        "inventory": {"states": [], "backlogs": [], "wip": []},
        "processes": [],
        "policies": {"ordering": [], "production": []},
        "accounting": {"defaults_used": True},
        "lca": {"defaults_used": True},
        "attrs": {"source_sheet": "model_assumption_review"},
    }
    data.setdefault("nodes", []).append(node)
    return node


def add_supplier_mapping(
    data: dict[str, Any],
    *,
    src_node_id: str,
    dst_node_id: str,
    item_id: str,
    initial_qty: float,
    uom: str,
    lead_days: float,
    transport_cost_per_unit: float,
    edge_id: str,
    assumption_label: str,
) -> None:
    src_node = find_node(data, src_node_id)
    ensure_inventory_state(
        src_node,
        item_id,
        initial=initial_qty,
        uom=uom,
        state_id=f"I_{item_id.split(':')[-1]}_{assumption_label}",
        source="model_assumption_review",
    )
    edge = {
        "id": edge_id,
        "type": "transport",
        "from": src_node_id,
        "to": dst_node_id,
        "items": [item_id],
        "mode": "truck",
        "distance_km": 0.0,
        "lead_time": {
            "type": "erlang_pipeline",
            "mean": lead_days,
            "stages": 4,
            "time_unit": "day",
            "is_default": False,
            "source": "model_assumption_review",
        },
        "order_terms": {
            "sell_price": 0.0,
            "price_base": 1.0,
            "quantity_unit": uom,
            "supply_order_frequency": {"value": 1, "time_unit": "day", "is_default": True},
        },
        "transport_cost": {
            "value": transport_cost_per_unit,
            "per": "unit",
            "is_default": False,
            "source": "model_assumption_review",
        },
        "delay_step_limit": {
            "value": 21,
            "is_default": False,
            "source": "model_assumption_review",
        },
        "service_level": {"otif": 1.0},
        "is_assumed": True,
        "assumption_label": assumption_label,
        "source": "model_assumption_review",
    }
    data.setdefault("edges", []).append(edge)


def set_lane_outage(data: dict[str, Any], edge_id: str, start_day: int, end_day: int, multiplier: float = 0.0) -> None:
    edge = find_edge(data, edge_id)
    edge["availability_profile"] = [
        {"start_day": int(start_day), "end_day": int(end_day), "multiplier": float(multiplier)}
    ]


def scale_edge_lead(data: dict[str, Any], edge_id: str, factor: float) -> None:
    edge = find_edge(data, edge_id)
    lead = edge.setdefault("lead_time", {})
    lead["mean"] = round(max(0.1, safe_float(lead.get("mean"), 1.0) * factor), 6)


def set_external_policy(data: dict[str, Any], **updates: Any) -> None:
    econ = scenario_policy(data)
    econ.update(updates)


def set_review_policy(
    data: dict[str, Any],
    *,
    review_days: int | None = None,
    safety_stock_days: float | None = None,
    fg_target_days: float | None = None,
    production_gap_gain: float | None = None,
    production_smoothing: float | None = None,
    bootstrap_scale: float | None = None,
) -> None:
    scn = choose_scenario(data)
    if review_days is not None:
        scn["review_period_days"] = int(review_days)
    if safety_stock_days is not None:
        scn["safety_stock_days"] = float(safety_stock_days)
    if fg_target_days is not None:
        scn["fg_target_days"] = float(fg_target_days)
    if production_gap_gain is not None:
        scn["production_gap_gain"] = float(production_gap_gain)
    if production_smoothing is not None:
        scn["production_smoothing"] = float(production_smoothing)
    if bootstrap_scale is not None:
        scn["opening_stock_bootstrap_scale"] = float(bootstrap_scale)


def scale_node_capacity(data: dict[str, Any], node_id: str, factor: float) -> None:
    node = find_node(data, node_id)
    for proc in node.get("processes") or []:
        cap = proc.setdefault("capacity", {})
        cap["max_rate"] = round(max(0.0, safe_float(cap.get("max_rate")) * factor), 6)


def parse_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def kpi_delta(result: dict[str, Any], baseline: dict[str, Any], key: str) -> float:
    return safe_float(result.get(key)) - safe_float(baseline.get(key))


def non_dominated_points(rows: list[dict[str, Any]], fill_key: str, cost_key: str) -> list[dict[str, Any]]:
    keep: list[dict[str, Any]] = []
    for row in rows:
        fill_i = safe_float(row.get(fill_key), math.nan)
        cost_i = safe_float(row.get(cost_key), math.nan)
        if math.isnan(fill_i) or math.isnan(cost_i):
            continue
        dominated = False
        for other in rows:
            if other is row:
                continue
            fill_j = safe_float(other.get(fill_key), math.nan)
            cost_j = safe_float(other.get(cost_key), math.nan)
            if math.isnan(fill_j) or math.isnan(cost_j):
                continue
            if fill_j >= fill_i and cost_j <= cost_i and (fill_j > fill_i or cost_j < cost_i):
                dominated = True
                break
        if not dominated:
            keep.append(row)
    keep.sort(key=lambda x: (-safe_float(x.get(fill_key)), safe_float(x.get(cost_key))))
    return keep


def build_case_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    item_id = str(config["special_item_id"])
    item_code = str(config["special_item_code"])
    unit = str(config["special_item_unit"])
    case_ids = special_case_ids(config)
    return [
        {
            "case_id": "baseline_gaillac",
            "category": "baseline",
            "description": f"Current baseline with assumed {item_code} -> {DEFAULT_SPECIAL_SUPPLIER_ID} / Gaillac.",
            "mutator": lambda d: ensure_default_special_mapping(d, config),
        },
        {
            "case_id": case_ids["no_supplier_mapping"],
            "category": "hypothesis",
            "description": f"Remove assumed supplier mapping for {item_code} but keep other baseline assumptions.",
            "mutator": lambda d: (
                ensure_default_special_mapping(d, config),
                remove_special_supplier_mapping(d, config),
                set_inventory_initial(d, "M-1810", item_id, 700.0),
            ),
        },
        {
            "case_id": case_ids["reroute_existing"],
            "category": "hypothesis",
            "description": f"Re-route {item_code} to existing supplier SDC-VD0519670A instead of Gaillac.",
            "mutator": lambda d: (
                ensure_default_special_mapping(d, config),
                remove_special_supplier_mapping(d, config),
                add_supplier_mapping(
                    d,
                    src_node_id="SDC-VD0519670A",
                    dst_node_id="M-1810",
                    item_id=item_id,
                    initial_qty=3000.0,
                    uom=unit,
                    lead_days=8.0,
                    transport_cost_per_unit=0.05,
                    edge_id=str(config["alt_edge_id"]),
                    assumption_label=f"ALT_VD0519670A_{item_code}",
                ),
            ),
        },
        {
            "case_id": case_ids["dedicated_local"],
            "category": "hypothesis",
            "description": f"Assign {item_code} to a dedicated local assumed supplier near Avene.",
            "mutator": lambda d: (
                ensure_default_special_mapping(d, config),
                remove_special_supplier_mapping(d, config),
                add_supplier_node_if_missing(
                    d,
                    node_id=str(config["local_supplier_id"]),
                    name=f"Assumed Supplier {item_code}",
                    location_id="France - AVENE - 34260",
                    lat=43.756966,
                    lon=3.09923,
                ),
                add_supplier_mapping(
                    d,
                    src_node_id=str(config["local_supplier_id"]),
                    dst_node_id="M-1810",
                    item_id=item_id,
                    initial_qty=3000.0,
                    uom=unit,
                    lead_days=2.0,
                    transport_cost_per_unit=0.03,
                    edge_id=str(config["local_edge_id"]),
                    assumption_label=f"LOCAL_{item_code}",
                ),
            ),
        },
        {
            "case_id": "hyp_730384_tight_flow",
            "category": "hypothesis",
            "description": "Treat 730384 (unit M) as a tighter flow: lower supplier and factory opening stocks.",
            "mutator": lambda d: (
                scale_inventory_initial(d, "SDC-VD0508918A", "item:730384", 0.2),
                scale_inventory_initial(d, "M-1430", "item:730384", 0.2),
            ),
        },
        {
            "case_id": "hyp_bootstrap_50pct",
            "category": "hypothesis",
            "description": "Reduce opening stock bootstrap by 50%.",
            "mutator": lambda d: set_review_policy(d, bootstrap_scale=0.5),
        },
        {
            "case_id": "hyp_bootstrap_150pct",
            "category": "hypothesis",
            "description": "Increase opening stock bootstrap by 50%.",
            "mutator": lambda d: set_review_policy(d, bootstrap_scale=1.5),
        },
        {
            "case_id": "hyp_external_off",
            "category": "hypothesis",
            "description": "Disable external procurement.",
            "mutator": lambda d: set_external_policy(d, external_procurement_enabled=False),
        },
        {
            "case_id": "hyp_external_limited",
            "category": "hypothesis",
            "description": "Keep external procurement but with tighter cap and slower lead.",
            "mutator": lambda d: set_external_policy(
                d,
                external_procurement_daily_cap_days=0.5,
                external_procurement_lead_days=7,
            ),
        },
        {
            "case_id": "hyp_external_expensive",
            "category": "hypothesis",
            "description": "Keep external procurement but make it much more expensive.",
            "mutator": lambda d: set_external_policy(
                d,
                external_procurement_cost_multiplier=4.0,
                external_procurement_transport_cost_per_unit=0.2,
            ),
        },
        {
            "case_id": "strict_raw_supported_only",
            "category": "strict_mode",
            "description": f"Strict mode: no external procurement, no assumed supplier for {item_code}, no bootstrap.",
            "mutator": lambda d: (
                ensure_default_special_mapping(d, config),
                remove_special_supplier_mapping(d, config),
                set_inventory_initial(d, "M-1810", item_id, 0.0),
                set_external_policy(d, external_procurement_enabled=False),
                set_review_policy(d, bootstrap_scale=0.0),
            ),
        },
        {
            "case_id": "policy_review_2d",
            "category": "policy",
            "description": "Periodic review every 2 days.",
            "mutator": lambda d: set_review_policy(d, review_days=2),
        },
        {
            "case_id": "policy_review_7d",
            "category": "policy",
            "description": "Periodic review every 7 days.",
            "mutator": lambda d: set_review_policy(d, review_days=7),
        },
        {
            "case_id": "policy_stock_buffered",
            "category": "policy",
            "description": "More buffered policy: higher safety stock and FG target.",
            "mutator": lambda d: set_review_policy(
                d,
                review_days=1,
                safety_stock_days=10.0,
                fg_target_days=6.0,
                production_gap_gain=0.2,
                production_smoothing=0.3,
            ),
        },
        {
            "case_id": "policy_reactive_mrp",
            "category": "policy",
            "description": "More reactive policy: daily review, higher gap gain, lower smoothing.",
            "mutator": lambda d: set_review_policy(
                d,
                review_days=1,
                safety_stock_days=6.0,
                fg_target_days=2.0,
                production_gap_gain=0.6,
                production_smoothing=0.05,
            ),
        },
        {
            "case_id": "disrupt_042342_outage_5d",
            "category": "targeted_disruption",
            "description": "Temporary 5-day outage of supplier lane for 042342.",
            "mutator": lambda d: set_lane_outage(d, "edge:SDC-VD0914690A_TO_M-1430_042342", 5, 9, 0.0),
        },
        {
            "case_id": "disrupt_042342_extreme_delay",
            "category": "targeted_disruption",
            "description": "Extreme delay on 042342 lane.",
            "mutator": lambda d: scale_edge_lead(d, "edge:SDC-VD0914690A_TO_M-1430_042342", 3.0),
        },
        {
            "case_id": "disrupt_773474_outage_5d",
            "category": "targeted_disruption",
            "description": "Temporary 5-day outage of 773474 lane from Gaillac.",
            "mutator": lambda d: set_lane_outage(d, "edge:SDC-1450_TO_M-1430_773474", 5, 9, 0.0),
        },
        {
            "case_id": case_ids["gaillac_outage"],
            "category": "targeted_disruption",
            "description": f"Temporary 5-day outage of assumed {item_code} lane from Gaillac.",
            "mutator": lambda d: (
                ensure_default_special_mapping(d, config),
                set_lane_outage(d, str(config["gaillac_edge_id"]), 5, 9, 0.0),
            ),
        },
        {
            "case_id": "disrupt_730384_outage_5d",
            "category": "targeted_disruption",
            "description": "Temporary 5-day outage of 730384 lane (unit M).",
            "mutator": lambda d: set_lane_outage(d, "edge:SDC-VD0508918A_TO_M-1430_730384", 5, 9, 0.0),
        },
        {
            "case_id": "disrupt_333362_outage_5d",
            "category": "targeted_disruption",
            "description": "Temporary 5-day outage of packaging item 333362.",
            "mutator": lambda d: set_lane_outage(d, "edge:SDC-VD0525412A_TO_M-1430_333362", 5, 9, 0.0),
        },
        {
            "case_id": "disrupt_M1810_capacity_down30",
            "category": "targeted_disruption",
            "description": "Targeted capacity reduction of 30% on M-1810.",
            "mutator": lambda d: scale_node_capacity(d, "M-1810", 0.7),
        },
    ]


def run_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_data = load_json(BASE_INPUT)
    config = detect_special_item_config(base_data)
    case_specs = build_case_specs(config)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runs_dir = OUT_DIR / "cases"
    runs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    baseline_summary: dict[str, Any] | None = None

    for spec in case_specs:
        case_id = spec["case_id"]
        case_dir = runs_dir / case_id
        input_path = case_dir / "input_case.json"
        output_dir = case_dir / "simulation_output"
        case_data = copy.deepcopy(base_data)
        spec["mutator"](case_data)
        write_json(input_path, case_data)
        summary, _ = run_simulation(RUN_SCRIPT, input_path, output_dir, "scn:BASE", days=30, skip_map=True, skip_plots=True)
        metrics = numeric_kpis(summary)
        row = {
            "case_id": case_id,
            "category": spec["category"],
            "description": spec["description"],
            **{k: round(v, 6) for k, v in metrics.items()},
            "review_period_days": safe_float((summary.get("policy") or {}).get("review_period_days"), math.nan),
            "safety_stock_days": safe_float((summary.get("policy") or {}).get("safety_stock_days"), math.nan),
            "production_gap_gain": safe_float((summary.get("policy") or {}).get("production_gap_gain"), math.nan),
            "production_smoothing": safe_float((summary.get("policy") or {}).get("production_smoothing"), math.nan),
            "opening_stock_bootstrap_scale": safe_float((summary.get("policy") or {}).get("opening_stock_bootstrap_scale"), math.nan),
            "assumed_supply_edges": ", ".join((summary.get("production_tracking") or {}).get("assumed_supply_edges") or []),
            "output_dir": str(output_dir),
        }
        results.append(row)
        if case_id == "baseline_gaillac":
            baseline_summary = summary

    if baseline_summary is None:
        raise RuntimeError("Missing baseline case.")
    return results, baseline_summary


def load_case_rows(results: list[dict[str, Any]], case_id: str, filename: str) -> list[dict[str, Any]]:
    case = next(r for r in results if r["case_id"] == case_id)
    path = Path(case["output_dir"]) / filename
    return parse_csv(path)


def summarize_backlog_causes(results: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    daily_rows = load_case_rows(results, case_id, "first_simulation_daily.csv")
    demand_rows = load_case_rows(results, case_id, "production_demand_service_daily.csv")
    constraint_rows = load_case_rows(results, case_id, "production_constraint_daily.csv")

    demand_by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
    constraint_by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in demand_rows:
        demand_by_day[int(row["day"])].append(row)
    for row in constraint_rows:
        constraint_by_day[int(row["day"])].append(row)

    shortfall_days: list[dict[str, Any]] = []
    cause_counter: Counter[str] = Counter()
    binding_counter: Counter[str] = Counter()
    for row in daily_rows:
        day = int(row["day"])
        demand = safe_float(row["demand"])
        served = safe_float(row["served"])
        if served + 1e-9 >= demand:
            continue
        impacted_items = [
            {
                "item_id": r["item_id"],
                "demand_qty": safe_float(r["demand_qty"]),
                "served_qty": safe_float(r["served_qty"]),
                "backlog_end_qty": safe_float(r["backlog_end_qty"]),
            }
            for r in demand_by_day.get(day, [])
            if safe_float(r["backlog_end_qty"]) > 1e-9 or safe_float(r["served_qty"]) + 1e-9 < safe_float(r["required_with_backlog_qty"])
        ]
        cands = [
            r
            for r in constraint_by_day.get(day, [])
            if safe_float(r["shortfall_vs_desired_qty"]) > 1e-9
        ]
        cands.sort(key=lambda r: safe_float(r["shortfall_vs_desired_qty"]), reverse=True)
        dominant = cands[0] if cands else None
        cause = dominant["binding_cause"] if dominant else "downstream_stockout_or_distribution"
        cause_counter[cause] += 1
        if dominant and dominant.get("binding_input_item_id"):
            binding_counter[dominant["binding_input_item_id"]] += 1
        shortfall_days.append(
            {
                "day": day,
                "demand": round(demand, 4),
                "served": round(served, 4),
                "ending_backlog": round(safe_float(row["backlog_end"]), 4),
                "impacted_items": impacted_items,
                "dominant_factory": dominant["node_id"] if dominant else "",
                "dominant_output_item": dominant["output_item_id"] if dominant else "",
                "dominant_cause": cause,
                "dominant_binding_input": dominant["binding_input_item_id"] if dominant else "",
                "dominant_shortfall_vs_desired_qty": round(safe_float(dominant["shortfall_vs_desired_qty"]) if dominant else 0.0, 4),
            }
        )
    return {
        "shortfall_days": shortfall_days,
        "cause_counts": dict(cause_counter),
        "binding_input_counts": dict(binding_counter.most_common()),
    }


def build_fragility_map(results: list[dict[str, Any]], baseline_row: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    with CRITICAL_MATERIALS.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    case_ids = special_case_ids(config)
    disruption_case_by_item = {
        "item:042342": "disrupt_042342_outage_5d",
        "item:773474": "disrupt_773474_outage_5d",
        str(config["special_item_id"]): case_ids["gaillac_outage"],
        "item:730384": "disrupt_730384_outage_5d",
        "item:333362": "disrupt_333362_outage_5d",
    }
    by_case = {r["case_id"]: r for r in results}
    out: list[dict[str, Any]] = []
    for row in rows:
        item_id = f"item:{row['item']}" if not str(row["item"]).startswith("item:") else str(row["item"])
        suppliers = int(float(row["suppliers"]))
        disruption_case = disruption_case_by_item.get(item_id)
        disruption_fill_delta = None
        disruption_backlog_delta = None
        if disruption_case and disruption_case in by_case:
            disruption_fill_delta = round(
                safe_float(by_case[disruption_case].get("fill_rate")) - safe_float(baseline_row.get("fill_rate")),
                6,
            )
            disruption_backlog_delta = round(
                safe_float(by_case[disruption_case].get("ending_backlog")) - safe_float(baseline_row.get("ending_backlog")),
                6,
            )
        dependency = "low"
        if item_id == str(config["special_item_id"]):
            dependency = "high_assumed_supplier"
        elif item_id == "item:730384":
            dependency = "medium_unit_M_ambiguous"
        structural_class = "mono_source" if suppliers == 1 else f"multi_source_{suppliers}"
        out.append(
            {
                "node": row["node"],
                "item_id": item_id,
                "supplier_count": suppliers,
                "criticality_score": round(safe_float(row["criticality_score"]), 6),
                "cover_days": round(safe_float(row["cover_days"]), 6),
                "total_consumed": round(safe_float(row["total_consumed"]), 6),
                "structural_class": structural_class,
                "model_dependency": dependency,
                "targeted_disruption_fill_delta": disruption_fill_delta,
                "targeted_disruption_backlog_delta": disruption_backlog_delta,
            }
        )
    out.sort(
        key=lambda r: (
            -safe_float(r["criticality_score"]),
            -abs(safe_float(r.get("targeted_disruption_backlog_delta"), 0.0)),
        )
    )
    return out


def build_confidence_table(results: list[dict[str, Any]], baseline_row: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    by_case = {r["case_id"]: r for r in results}
    item_code = str(config["special_item_code"])
    case_ids = special_case_ids(config)
    return [
        {
            "conclusion": "Mono-sourcing de item:042342 sur M-1430",
            "confidence": "high",
            "hypothesis_dependency": "low",
            "observed_vs_assumed": "Observed directly in Data_poc.xlsx relations and criticality table; no inferred supplier.",
            "evidence": "Supplier count = 1, highest criticality score.",
        },
        {
            "conclusion": f"Criticité élevée de item:{item_code} sur M-1810",
            "confidence": "medium",
            "hypothesis_dependency": "high",
            "observed_vs_assumed": f"Observed in BOM, but supplier mapping is assumed to {DEFAULT_SPECIAL_SUPPLIER_ID}/Gaillac.",
            "evidence": (
                f"No-supplier mapping fill {safe_float(by_case[case_ids['no_supplier_mapping']]['fill_rate']):.3f}; "
                f"5-day outage fill {safe_float(by_case[case_ids['gaillac_outage']]['fill_rate']):.3f}."
            ),
        },
        {
            "conclusion": "M-1810 agit comme goulot service/backlog",
            "confidence": "high",
            "hypothesis_dependency": "medium",
            "observed_vs_assumed": "Observed in sensitivity, policy tests and targeted capacity drop.",
            "evidence": f"M-1810 capacity-down case fill {safe_float(by_case['disrupt_M1810_capacity_down30']['fill_rate']):.3f}.",
        },
        {
            "conclusion": "M-1430 est le principal driver de coût",
            "confidence": "high",
            "hypothesis_dependency": "medium",
            "observed_vs_assumed": "Observed in OAT sensitivity on cost; absolute level still depends on cost assumptions.",
            "evidence": "capacity_node_scale::M-1430 remains top cost driver.",
        },
        {
            "conclusion": f"La baseline à {safe_float(baseline_row.get('fill_rate')) * 100.0:.1f}% repose fortement sur stock bootstrap + appro externe",
            "confidence": "high",
            "hypothesis_dependency": "high",
            "observed_vs_assumed": "Observed via strict mode and external-off cases; both are model assumptions, not source data.",
            "evidence": f"Strict mode fill {safe_float(by_case['strict_raw_supported_only']['fill_rate']):.3f}; external off fill {safe_float(by_case['hyp_external_off']['fill_rate']):.3f}.",
        },
        {
            "conclusion": "La fréquence de revue/pilotage est un levier majeur",
            "confidence": "high",
            "hypothesis_dependency": "medium",
            "observed_vs_assumed": "Observed across shocks, full exploration and policy cases.",
            "evidence": f"Review 7d fill {safe_float(by_case['policy_review_7d']['fill_rate']):.3f} vs baseline {baseline_row['fill_rate']:.3f}.",
        },
        {
            "conclusion": "Le niveau absolu de coût reste moins robuste que les tendances relatives",
            "confidence": "medium",
            "hypothesis_dependency": "high",
            "observed_vs_assumed": "Transport/purchase/holding were calibrated and external procurement is stylized.",
            "evidence": f"Baseline total cost {baseline_row['total_cost']:.1f}; external-expensive rises to {safe_float(by_case['hyp_external_expensive']['total_cost']):.1f}.",
        },
    ]


def load_full_exploration_rows() -> list[dict[str, Any]]:
    with FULL_SAMPLES.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("status") == "ok"]


def write_results_csv(results: list[dict[str, Any]], path: Path) -> None:
    if not results:
        return
    fieldnames = list(results[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        vals = []
        for col in columns:
            v = row.get(col, "")
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def build_report(
    results: list[dict[str, Any]],
    baseline_summary: dict[str, Any],
    backlog_summary: dict[str, Any],
    confidence_rows: list[dict[str, Any]],
    fragility_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    by_case = {r["case_id"]: r for r in results}
    baseline_row = by_case["baseline_gaillac"]
    full_rows = load_full_exploration_rows()

    case_frontier = non_dominated_points(results, "fill_rate", "total_cost")
    global_frontier = non_dominated_points(full_rows, "kpi::fill_rate", "kpi::total_cost")
    service_inventory_frontier = non_dominated_points(full_rows, "kpi::fill_rate", "kpi::avg_inventory")

    hypothesis_cases = [r for r in results if r["category"] == "hypothesis"]
    policy_cases = [r for r in results if r["category"] == "policy"]
    disruption_cases = [r for r in results if r["category"] == "targeted_disruption"]
    item_code = str(config["special_item_code"])

    hypothesis_cases.sort(key=lambda r: safe_float(r["fill_rate"]))
    policy_cases.sort(key=lambda r: safe_float(r["fill_rate"]))
    disruption_cases.sort(key=lambda r: safe_float(r["fill_rate"]))

    summary = {
        "baseline_case": baseline_row,
        "confidence_table": confidence_rows,
        "hypothesis_cases": hypothesis_cases,
        "policy_cases": policy_cases,
        "disruption_cases": disruption_cases,
        "backlog_decomposition": backlog_summary,
        "fragility_map_top10": fragility_rows[:10],
        "case_pareto_frontier": case_frontier[:12],
        "global_pareto_frontier_sample": global_frontier[:20],
        "service_inventory_frontier_sample": service_inventory_frontier[:20],
    }

    report = f"""# Revue approfondie des hypotheses et de la robustesse du modele supply

## Perimetre
- Base de travail: input prepare avec hypothese conservee `item:{item_code} -> {DEFAULT_SPECIAL_SUPPLIER_ID} / Gaillac`
- Objectif: distinguer ce qui est robuste, tester les hypotheses de completion, construire un mode strict, comparer des politiques de pilotage, decomposer les causes du backlog, cartographier la fragilite matiere, tracer des frontieres cout/service et tester des ruptures ciblees.

## 1) Baseline conservee
- Fill rate: **{baseline_row['fill_rate']:.6f}**
- Ending backlog: **{baseline_row['ending_backlog']:.4f}**
- Total cost: **{baseline_row['total_cost']:.4f}**
- External procured ordered qty: **{baseline_row['total_external_procured_ordered_qty']:.4f}**
- Opening stock bootstrap qty: **{baseline_row['total_opening_stock_bootstrap_qty']:.4f}**

## 2) Ce qui est robuste vs ce qui depend des hypotheses
{markdown_table(confidence_rows, ['conclusion', 'confidence', 'hypothesis_dependency', 'observed_vs_assumed', 'evidence'])}

## 3) Sensibilite des hypotheses de modelisation
{markdown_table(hypothesis_cases, ['case_id', 'description', 'fill_rate', 'ending_backlog', 'total_cost', 'total_external_procured_ordered_qty', 'total_opening_stock_bootstrap_qty'])}

Lecture:
- Les hypotheses qui changent le plus la lecture sont celles sur `{item_code}`, l'appro externe et le bootstrap de stock initial.
- `730384` en unite `M` reste un point de vigilance de semantique/metier, mais sous les buffers actuels ce n'est pas un driver majeur de degradation.

## 4) Mode strict "sans hypotheses fortes"
- Cas strict: `strict_raw_supported_only`
- Fill rate: **{safe_float(by_case['strict_raw_supported_only']['fill_rate']):.6f}**
- Ending backlog: **{safe_float(by_case['strict_raw_supported_only']['ending_backlog']):.4f}**
- Total cost: **{safe_float(by_case['strict_raw_supported_only']['total_cost']):.4f}**

Lecture:
- Cette vue montre ce que la donnee brute supporte reellement sans artifice fort.
- L'ecart avec la baseline mesure a quel point la performance actuelle depend des completions de preparation.

## 5) Comparaison des politiques de pilotage
{markdown_table(policy_cases, ['case_id', 'description', 'fill_rate', 'ending_backlog', 'total_cost', 'review_period_days', 'safety_stock_days', 'production_gap_gain', 'production_smoothing'])}

Lecture:
- La revue 7 jours degrade tres fortement le service.
- Une politique plus reactive de type MRP quotidien ameliorant le recalcul frequemment preserve mieux le service qu'une revue lente.
- Une politique plus bufferisee peut proteger le service, mais en poussant les couts et les stocks.

## 6) Decomposition fine des causes de backlog (baseline)
- Jours avec sous-service identifies: **{len(backlog_summary['shortfall_days'])}**
- Repartition dominante des causes: **{json.dumps(backlog_summary['cause_counts'], ensure_ascii=False)}**
- Inputs dominants en contrainte: **{json.dumps(dict(list(backlog_summary['binding_input_counts'].items())[:10]), ensure_ascii=False)}**

### Jours principaux de sous-service
{markdown_table(backlog_summary['shortfall_days'][:12], ['day', 'demand', 'served', 'ending_backlog', 'dominant_factory', 'dominant_output_item', 'dominant_cause', 'dominant_binding_input', 'dominant_shortfall_vs_desired_qty'])}

Lecture:
- Cette decomposition est maintenant basee sur un diagnostic journalier de contrainte de production, pas seulement sur l'evolution du backlog.
- Elle reste une inference de modele, mais elle est beaucoup plus defensable qu'une lecture purement qualitative.

## 7) Carte de fragilite par matiere
{markdown_table(fragility_rows[:15], ['node', 'item_id', 'supplier_count', 'criticality_score', 'cover_days', 'total_consumed', 'structural_class', 'model_dependency', 'targeted_disruption_fill_delta', 'targeted_disruption_backlog_delta'])}

Lecture:
- `item:042342` reste la fragilite structurelle majeure.
- `item:{item_code}` est un cas particulier: criticite operationnelle visible, mais dependance forte a l'hypothese Gaillac.
- `item:730384` et `item:333362` ressortent davantage comme points de vigilance de donnees / semantique que comme fragilites operationnelles dominantes dans la baseline.

## 8) Frontiere cout / service

### Frontiere Pareto sur les cas cibles de cette revue
{markdown_table(case_frontier[:12], ['case_id', 'category', 'fill_rate', 'ending_backlog', 'total_cost', 'total_external_procured_ordered_qty'])}

### Extrait de frontiere globale cout / service (full exploration)
{markdown_table(global_frontier[:12], ['run_id', 'kpi::fill_rate', 'kpi::ending_backlog', 'kpi::total_cost'])}

### Extrait de frontiere service / inventaire (full exploration)
{markdown_table(service_inventory_frontier[:12], ['run_id', 'kpi::fill_rate', 'kpi::avg_inventory', 'kpi::total_cost'])}

Lecture:
- La baseline est performante, mais elle est surtout protectrice.
- Certaines politiques ou hypotheses peuvent battre la baseline sur un axe, rarement sur service + cout simultanement.
- La frontiere montre bien que le service est souvent achete par du stock, pas seulement par une meilleure reactivite.

## 9) Ruptures ciblees plus realistes
{markdown_table(disruption_cases, ['case_id', 'description', 'fill_rate', 'ending_backlog', 'total_cost'])}

Lecture:
- Les ruptures les plus destructrices restent celles touchant les intrants critiques mono-source ou le pilotage.
- Les outages ponctuels sur `042342`, `773474` et `{item_code}` sont nettement plus instructifs que des chocs globaux abstraits.
- Les tests packaging `730384` / `333362` ne degradent pas fortement la baseline actuelle, ce qui suggere que leur enjeu est aujourd'hui plus data-quality que capacitaire.

## 10) Conclusion operative
1. La representation actuelle est utile pour raisonner, mais une partie non negligeable de la performance baseline repose sur des hypotheses de preparation.
2. Les conclusions les plus robustes sont: fragilite mono-source, sensibilite forte a la revue/pilotage, importance de `M-1810` pour le service et de `M-1430` pour le cout.
3. Les conclusions les moins robustes sont: criticite absolue de `{item_code}`, niveau absolu des couts et ampleur exacte de la resilience fournie par l'externe.
4. Le mode strict est la meilleure borne basse "supportee par la donnee brute".
5. Les ruptures ciblees et la carte de fragilite sont les sorties les plus utiles pour discuter concretement avec l'industriel sans surpromettre sur la precision du modele.
"""

    return summary, report


def build_onepager(summary: dict[str, Any], results: list[dict[str, Any]], config: dict[str, Any]) -> str:
    baseline = summary["baseline_case"]
    by_case = {row["case_id"]: row for row in results}
    case_ids = special_case_ids(config)
    item_code = str(config["special_item_code"])
    return f"""# Synthese 1 page - robustesse du modele supply

## A dire en ouverture
Le modele actuel est **utile pour raisonner** sur la supply, mais il ne faut pas le presenter comme une copie fidele de l'operationnel.
Il capte bien la structure reseau, les dependances matieres, les effets delai / revue / capacite / stock.
En revanche, une partie importante de la performance baseline depend encore d'**hypotheses de preparation**.

## Ce qui est solide
- `item:042342` sur `M-1430` est une **fragilite structurelle robuste**.
- `M-1810` ressort comme **goulot service / backlog**.
- `M-1430` ressort comme **driver principal de cout**.
- La **frequence de revue / pilotage** est un levier majeur:
  - baseline: fill rate `{safe_float(baseline['fill_rate']):.3f}`
  - revue `7 jours`: fill rate `{safe_float(by_case['policy_review_7d']['fill_rate']):.3f}`

## Ce qui depend fortement des hypotheses
- `item:{item_code}` est bien dans la BOM, mais **son fournisseur est suppose**:
  - hypothese conservee: `{item_code} -> {DEFAULT_SPECIAL_SUPPLIER_ID} / Gaillac`
- Le niveau de performance baseline depend fortement de:
  - l'**appro externe**
  - le **bootstrap de stock initial**
  - certaines hypotheses de completion du reseau
- Le **niveau absolu des couts** reste moins robuste que les tendances relatives.

## Chiffres cles a retenir
- Baseline actuelle:
  - fill rate `{safe_float(baseline['fill_rate']):.3f}`
  - backlog final `{safe_float(baseline['ending_backlog']):.1f}`
  - cout total `{safe_float(baseline['total_cost']) / 1000.0:.1f}k`
- Sans mapping fournisseur pour `{item_code}`:
  - fill rate `{safe_float(by_case[case_ids['no_supplier_mapping']]['fill_rate']):.3f}`
  - backlog `{safe_float(by_case[case_ids['no_supplier_mapping']]['ending_backlog']):.1f}`
- Sans appro externe:
  - fill rate `{safe_float(by_case['hyp_external_off']['fill_rate']):.3f}`
  - backlog `{safe_float(by_case['hyp_external_off']['ending_backlog']):.1f}`
- Mode strict "donnee brute seulement":
  - fill rate `{safe_float(by_case['strict_raw_supported_only']['fill_rate']):.3f}`
  - backlog `{safe_float(by_case['strict_raw_supported_only']['ending_backlog']):.1f}`

## Lecture simple
- La baseline est **bonne**, mais elle est aussi **protectrice**.
- Elle n'est pas uniquement portee par une supply "intrinsequement robuste":
  - elle est aussi soutenue par des stocks initiaux et des mecanismes de secours.
- Donc:
  - les **tendances** du modele sont utiles
  - les **niveaux absolus** doivent encore etre pris avec prudence

## Ce que montrent les tests cibles
- Rupture 5 jours sur `042342`:
  - fill rate `{safe_float(by_case['disrupt_042342_outage_5d']['fill_rate']):.3f}`
  - backlog `{safe_float(by_case['disrupt_042342_outage_5d']['ending_backlog']):.1f}`
- Rupture 5 jours sur `773474`:
  - fill rate `{safe_float(by_case['disrupt_773474_outage_5d']['fill_rate']):.3f}`
  - backlog `{safe_float(by_case['disrupt_773474_outage_5d']['ending_backlog']):.1f}`
- Rupture 5 jours sur `{item_code}` (hypothese Gaillac):
  - fill rate `{safe_float(by_case[case_ids['gaillac_outage']]['fill_rate']):.3f}`
  - backlog `{safe_float(by_case[case_ids['gaillac_outage']]['ending_backlog']):.1f}`
- Baisse de capacite `M-1810` de 30%:
  - fill rate `{safe_float(by_case['disrupt_M1810_capacity_down30']['fill_rate']):.3f}`
  - backlog `{safe_float(by_case['disrupt_M1810_capacity_down30']['ending_backlog']):.1f}`

Conclusion:
- les intrants critiques mono-source et `M-1810` sont les points les plus sensibles
- les tests packaging `730384` / `333362` sont aujourd'hui plus des sujets de **qualite de donnee** que de risque operationnel majeur

## Message prudent mais utile pour l'industriel
On peut dire:

> Le modele est deja utile pour identifier les dependances critiques, les matieres les plus sensibles, l'effet du pilotage MRP/revue et les zones de fragilite.
> En revanche, une partie importante de la performance actuelle depend encore d'hypotheses de preparation, notamment autour de `{item_code}`, de l'appro externe et des stocks initiaux.

## Les 5 messages les plus importants
1. `042342` est la fragilite la plus robuste du modele.
2. `M-1810` est le principal goulot service.
3. `{item_code}` est important, mais sa lecture depend de l'hypothese Gaillac.
4. La revue/pilotage change enormement le resultat.
5. La baseline est credible comme scenario de travail, pas encore comme verite operationnelle.
"""


def main() -> None:
    base_data = load_json(BASE_INPUT)
    config = detect_special_item_config(base_data)
    results, baseline_summary = run_cases()
    baseline_row = next(r for r in results if r["case_id"] == "baseline_gaillac")
    backlog_summary = summarize_backlog_causes(results, "baseline_gaillac")
    confidence_rows = build_confidence_table(results, baseline_row, config)
    fragility_rows = build_fragility_map(results, baseline_row, config)
    summary, report = build_report(results, baseline_summary, backlog_summary, confidence_rows, fragility_rows, config)
    onepager = build_onepager(summary, results, config)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_results_csv(results, OUT_DIR / "scenario_results.csv")
    write_json(OUT_DIR / "model_assumption_review_summary.json", summary)
    (OUT_DIR / "model_assumption_review_report.md").write_text(report, encoding="utf-8")
    (OUT_DIR / "model_assumption_review_onepager.md").write_text(onepager, encoding="utf-8")

    print(f"[OK] Scenario results: {(OUT_DIR / 'scenario_results.csv').resolve()}")
    print(f"[OK] Summary JSON: {(OUT_DIR / 'model_assumption_review_summary.json').resolve()}")
    print(f"[OK] Report: {(OUT_DIR / 'model_assumption_review_report.md').resolve()}")


if __name__ == "__main__":
    main()
