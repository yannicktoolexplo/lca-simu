#!/usr/bin/env python3
"""
Prepare a simulation-ready copy of a geocoded supply graph.

Outputs:
- simulation-ready graph JSON
- preparation report JSON
- preparation report Markdown
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare simulation-ready supply graph.")
    parser.add_argument(
        "--input",
        default="etudecas/result_geocodage/supply_graph_poc_geocoded.json",
        help="Input geocoded graph JSON.",
    )
    parser.add_argument(
        "--output-graph",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Output simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--output-report-json",
        default="etudecas/simulation_prep/result/simulation_prep_report.json",
        help="Output prep report JSON.",
    )
    parser.add_argument(
        "--output-report-md",
        default="etudecas/simulation_prep/result/simulation_prep_report.md",
        help="Output prep report Markdown.",
    )
    return parser.parse_args()


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def normalize_unit(unit: Any) -> str:
    s = str(unit or "").strip().upper()
    aliases = {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITS": "UN",
    }
    return aliases.get(s, s)


def infer_item_unit_map(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, str]:
    votes: dict[str, Counter[str]] = defaultdict(Counter)

    for e in edges:
        u = normalize_unit(((e.get("order_terms") or {}).get("quantity_unit")))
        if not u:
            continue
        for item_id in (e.get("items") or []):
            votes[str(item_id)][u] += 3

    for n in nodes:
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                u = normalize_unit(inp.get("ratio_unit"))
                if item_id and u:
                    votes[item_id][u] += 1

    priority = {"KG": 4, "G": 3, "UN": 2, "M": 1}
    out: dict[str, str] = {}
    for item_id, cnt in votes.items():
        best = sorted(cnt.items(), key=lambda x: (-x[1], -priority.get(x[0], 0), x[0]))[0][0]
        out[item_id] = best
    return out


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_node_maps(nodes: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[float, float]]]:
    by_id: dict[str, dict[str, Any]] = {}
    coords: dict[str, tuple[float, float]] = {}
    for n in nodes:
        nid = str(n.get("id"))
        by_id[nid] = n
        geo = n.get("geo") or {}
        lat = to_float(geo.get("lat"))
        lon = to_float(geo.get("lon"))
        if lat is not None and lon is not None:
            coords[nid] = (lat, lon)
    return by_id, coords


def estimate_lead_time_days(distance_km: float, src_type: str, dst_type: str) -> float:
    base_days = max(1.0, distance_km / 650.0)
    lane_buffer = 1.0
    if src_type == "supplier_dc" and dst_type == "factory":
        lane_buffer = 2.0
    elif src_type == "factory" and dst_type == "distribution_center":
        lane_buffer = 1.5
    elif src_type == "distribution_center" and dst_type == "customer":
        lane_buffer = 1.0
    return round(base_days + lane_buffer, 2)


def estimate_transport_cost_per_unit(distance_km: float) -> float:
    # Simple placeholder estimate for early simulation setup.
    return round(max(0.05, 0.03 + 0.0011 * distance_km), 4)


def ensure_sim_meta(graph: dict[str, Any]) -> None:
    meta = graph.setdefault("meta", {})
    prep = {
        "prepared_for_simulation": True,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "assumption_version": "v1",
        "notes": [
            "Missing/default values were replaced with explicit assumptions for first-pass simulation.",
            "Review simulation_prep_report before running production scenarios.",
        ],
    }
    meta["simulation_prep"] = prep


def prepare_graph(graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    g = deepcopy(graph)
    ensure_sim_meta(g)

    nodes = g.get("nodes", []) or []
    edges = g.get("edges", []) or []
    scenarios = g.get("scenarios", []) or []
    node_by_id, coords = build_node_maps(nodes)
    item_unit_map = infer_item_unit_map(nodes, edges)

    in_degree: dict[str, int] = defaultdict(int)
    for e in edges:
        dst = str(e.get("to"))
        in_degree[dst] += 1

    customer_ids = {
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "customer"
    }
    customer_item_pairs: set[tuple[str, str]] = set()
    for e in edges:
        dst = str(e.get("to"))
        if dst not in customer_ids:
            continue
        for item_id in (e.get("items") or []):
            customer_item_pairs.add((dst, str(item_id)))

    change_counts = defaultdict(int)
    changed_edge_ids: list[str] = []
    changed_node_ids: list[str] = []
    changed_demand_rows: list[dict[str, str]] = []

    # Edge-level enrichment
    for e in edges:
        eid = str(e.get("id"))
        src = str(e.get("from"))
        dst = str(e.get("to"))
        src_type = str((node_by_id.get(src) or {}).get("type") or "")
        dst_type = str((node_by_id.get(dst) or {}).get("type") or "")

        src_c = coords.get(src)
        dst_c = coords.get(dst)
        computed_dist = None
        if src_c and dst_c:
            computed_dist = round(haversine_km(src_c[0], src_c[1], dst_c[0], dst_c[1]), 1)

        if e.get("distance_km") is None and computed_dist is not None:
            e["distance_km"] = computed_dist
            change_counts["edge_distance_filled"] += 1
            changed_edge_ids.append(eid)

        effective_dist = to_float(e.get("distance_km")) or computed_dist or 500.0

        lead = e.get("lead_time") or {}
        if not isinstance(lead, dict):
            lead = {}
        if lead.get("is_default") is True or to_float(lead.get("mean")) is None:
            lead["type"] = "erlang_pipeline"
            lead["mean"] = estimate_lead_time_days(effective_dist, src_type, dst_type)
            lead["stages"] = int(lead.get("stages") or 4)
            lead["time_unit"] = "day"
            lead["is_default"] = False
            lead["source"] = "simulation_prep_assumption"
            e["lead_time"] = lead
            change_counts["edge_lead_time_updated"] += 1
            if eid not in changed_edge_ids:
                changed_edge_ids.append(eid)

        tc = e.get("transport_cost") or {}
        if not isinstance(tc, dict):
            tc = {}
        tc_value = to_float(tc.get("value"))
        if tc.get("is_default") is True or tc_value is None or tc_value == 0:
            tc["value"] = estimate_transport_cost_per_unit(effective_dist)
            tc["per"] = "unit"
            tc["is_default"] = False
            tc["source"] = "simulation_prep_assumption"
            e["transport_cost"] = tc
            change_counts["edge_transport_cost_updated"] += 1
            if eid not in changed_edge_ids:
                changed_edge_ids.append(eid)

        dsl = e.get("delay_step_limit") or {}
        if not isinstance(dsl, dict):
            dsl = {}
        if dsl.get("is_default") is True or dsl.get("value") in (None, 999):
            dsl["value"] = 21
            dsl["is_default"] = False
            dsl["source"] = "simulation_prep_assumption"
            e["delay_step_limit"] = dsl
            change_counts["edge_delay_limit_updated"] += 1
            if eid not in changed_edge_ids:
                changed_edge_ids.append(eid)

    # Node-level enrichment
    node_base_stock = {
        "supplier_dc": 1500.0,
        "factory": 800.0,
        "distribution_center": 1200.0,
        "customer": 0.0,
    }
    for n in nodes:
        nid = str(n.get("id"))
        ntype = str(n.get("type") or "unknown")
        inv = n.get("inventory") or {}
        states = inv.get("states") or []
        node_changed = False

        for st in states:
            item_id = str(st.get("item_id"))
            target_uom = item_unit_map.get(item_id, "")
            current_uom = normalize_unit(st.get("uom"))
            if target_uom and current_uom and target_uom != current_uom:
                st["uom"] = target_uom
                st["uom_source"] = "simulation_prep_inferred_from_relations_bom"
                change_counts["inventory_uom_harmonized"] += 1
                node_changed = True

            initial = to_float(st.get("initial"))
            if initial is None or initial <= 0:
                base = node_base_stock.get(ntype, 500.0)
                uplift = float(in_degree.get(nid, 0) * 50)
                new_initial = round(base + uplift, 2)
                if ntype == "customer":
                    new_initial = 0.0
                st["initial"] = new_initial
                st["is_default_initial"] = False
                st["initial_source"] = "simulation_prep_assumption"
                change_counts["inventory_initial_updated"] += 1
                node_changed = True

            hc = st.get("holding_cost") or {}
            if isinstance(hc, dict):
                hc_val = to_float(hc.get("value"))
                if hc.get("is_default") is True or hc_val is None or hc_val == 0:
                    hc["value"] = 0.04
                    hc["per"] = "unit*day"
                    hc["is_default"] = False
                    hc["source"] = "simulation_prep_assumption"
                    st["holding_cost"] = hc
                    change_counts["inventory_holding_cost_updated"] += 1
                    node_changed = True

        policies = n.get("policies")
        if not isinstance(policies, dict):
            policies = {}
        sim_policy = policies.get("simulation_policy")
        if not isinstance(sim_policy, dict):
            sim_policy = {}
        if not sim_policy:
            sim_policy.update(
                {
                    "service_level_target": 0.95,
                    "review_period_days": 7,
                    "reorder_mode": "base_stock",
                    "source": "simulation_prep_assumption",
                }
            )
            policies["simulation_policy"] = sim_policy
            n["policies"] = policies
            change_counts["node_policy_added"] += 1
            node_changed = True

        processes = n.get("processes") or []
        for p in processes:
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                target_uom = item_unit_map.get(item_id, "")
                current_uom = normalize_unit(inp.get("ratio_unit"))
                if target_uom and not current_uom:
                    inp["ratio_unit"] = target_uom
                    change_counts["process_input_uom_filled"] += 1
                    node_changed = True

            cap = p.get("capacity") or {}
            if isinstance(cap, dict):
                max_rate = to_float(cap.get("max_rate")) or 0.0
                if cap.get("is_default") is True:
                    batch_size = to_float(p.get("batch_size")) or 1000.0
                    cap["max_rate"] = round(max(max_rate, batch_size / 40.0), 2)
                    cap["uom"] = cap.get("uom") or "unit/day"
                    cap["is_default"] = False
                    cap["source"] = "simulation_prep_assumption"
                    p["capacity"] = cap
                    change_counts["process_capacity_updated"] += 1
                    node_changed = True

            cost = p.get("cost") or {}
            if isinstance(cost, dict):
                cval = to_float(cost.get("value"))
                if cost.get("is_default") is True or cval is None or cval == 0:
                    cost["value"] = 0.35
                    cost["per"] = "unit"
                    cost["is_default"] = False
                    cost["source"] = "simulation_prep_assumption"
                    p["cost"] = cost
                    change_counts["process_cost_updated"] += 1
                    node_changed = True

        if node_changed:
            changed_node_ids.append(nid)

    # Demand enrichment
    for scn in scenarios:
        sid = str(scn.get("id") or "unknown_scn")
        demands = scn.get("demand") or []
        if not isinstance(demands, list):
            demands = []
        existing_pairs = {
            (str(d.get("node_id")), str(d.get("item_id")))
            for d in demands
            if isinstance(d, dict)
        }

        for pair in sorted(customer_item_pairs):
            if pair in existing_pairs:
                continue
            node_id, item_id = pair
            demands.append(
                {
                    "node_id": node_id,
                    "item_id": item_id,
                    "profile": [
                        {
                            "type": "constant",
                            "value": 0.0,
                            "uom": "unit/day",
                            "is_default": True,
                        }
                    ],
                    "defaults": {"demand": True},
                }
            )
            change_counts["demand_rows_added"] += 1
            changed_demand_rows.append(
                {
                    "scenario_id": sid,
                    "node_id": node_id,
                    "item_id": item_id,
                    "action": "added_missing_customer_demand",
                }
            )
        scn["demand"] = demands

        for d in demands:
            if not isinstance(d, dict):
                continue
            node_id = str(d.get("node_id") or "")
            profile = d.get("profile") or []
            if not isinstance(profile, list) or not profile:
                profile = [{"type": "constant", "value": 0.0, "uom": "unit/day", "is_default": True}]
                d["profile"] = profile

            is_all_zero = True
            for p in profile:
                val = to_float((p or {}).get("value"))
                if val is not None and abs(val) > 1e-9:
                    is_all_zero = False
                    break

            if is_all_zero:
                base = 120.0 if str((node_by_id.get(node_id) or {}).get("type")) == "customer" else 80.0
                for p in profile:
                    if isinstance(p, dict):
                        p["type"] = p.get("type") or "constant"
                        p["value"] = base
                        p["uom"] = p.get("uom") or "unit/day"
                        p["is_default"] = False
                        p["source"] = "simulation_prep_assumption"
                change_counts["demand_profile_updated"] += 1
                changed_demand_rows.append(
                    {
                        "scenario_id": sid,
                        "node_id": node_id,
                        "item_id": str(d.get("item_id")),
                        "action": "filled_zero_or_missing_profile",
                    }
                )

    # Validation snapshot after enrichment
    missing_geo_nodes = []
    for n in nodes:
        geo = n.get("geo") or {}
        if to_float(geo.get("lat")) is None or to_float(geo.get("lon")) is None:
            missing_geo_nodes.append(str(n.get("id")))

    edges_missing_distance = [str(e.get("id")) for e in edges if to_float(e.get("distance_km")) is None]
    edges_zero_transport_cost = []
    for e in edges:
        tc = e.get("transport_cost") or {}
        if to_float((tc or {}).get("value")) in (None, 0.0):
            edges_zero_transport_cost.append(str(e.get("id")))
    zero_demand_rows = []
    for scn in scenarios:
        sid = str(scn.get("id") or "")
        for d in (scn.get("demand") or []):
            vals = []
            for p in (d.get("profile") or []):
                if isinstance(p, dict):
                    v = to_float(p.get("value"))
                    if v is not None:
                        vals.append(v)
            if not vals or all(v == 0 for v in vals):
                zero_demand_rows.append({"scenario_id": sid, "node_id": str(d.get("node_id")), "item_id": str(d.get("item_id"))})

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "changes": dict(sorted(change_counts.items())),
        "item_unit_map_sample": dict(sorted(item_unit_map.items())[:20]),
        "changed_entities": {
            "edge_count": len(set(changed_edge_ids)),
            "node_count": len(set(changed_node_ids)),
            "demand_rows_count": len(changed_demand_rows),
            "demand_rows": changed_demand_rows,
        },
        "validation_after_prep": {
            "missing_geo_nodes_count": len(missing_geo_nodes),
            "missing_geo_nodes": sorted(missing_geo_nodes),
            "edges_missing_distance_count": len(edges_missing_distance),
            "edges_zero_transport_cost_count": len(edges_zero_transport_cost),
            "zero_demand_rows_count": len(zero_demand_rows),
            "zero_demand_rows": zero_demand_rows,
        },
        "assumptions": {
            "inventory_base_stock_by_node_type": node_base_stock,
            "delay_step_limit_assumed": 21,
            "holding_cost_per_unit_day_assumed": 0.04,
            "process_cost_per_unit_assumed": 0.35,
            "demand_constant_assumed_customer": 120.0,
            "demand_constant_assumed_other": 80.0,
        },
    }
    return g, report


def report_markdown(report: dict[str, Any], input_path: str, output_graph_path: str) -> str:
    c = report["changes"]
    v = report["validation_after_prep"]
    ch = report["changed_entities"]
    return f"""# Simulation prep report

## Inputs / outputs
- Input graph: {input_path}
- Output graph: {output_graph_path}
- Generated at (UTC): {report['generated_at_utc']}

## What was enriched
- Edge distances filled: {c.get('edge_distance_filled', 0)}
- Edge lead times updated: {c.get('edge_lead_time_updated', 0)}
- Edge transport costs updated: {c.get('edge_transport_cost_updated', 0)}
- Edge delay limits updated: {c.get('edge_delay_limit_updated', 0)}
- Inventory initials updated: {c.get('inventory_initial_updated', 0)}
- Inventory holding costs updated: {c.get('inventory_holding_cost_updated', 0)}
- Inventory UOM harmonized: {c.get('inventory_uom_harmonized', 0)}
- Node policies added: {c.get('node_policy_added', 0)}
- Process capacities updated: {c.get('process_capacity_updated', 0)}
- Process costs updated: {c.get('process_cost_updated', 0)}
- Demand rows added: {c.get('demand_rows_added', 0)}
- Demand rows updated: {c.get('demand_profile_updated', 0)}

## Changed entities
- Changed edges: {ch.get('edge_count', 0)}
- Changed nodes: {ch.get('node_count', 0)}
- Changed demand rows: {ch.get('demand_rows_count', 0)}

## Validation after prep
- Missing geo nodes: {v.get('missing_geo_nodes_count', 0)}
- Edges still missing distance: {v.get('edges_missing_distance_count', 0)}
- Edges still zero transport cost: {v.get('edges_zero_transport_cost_count', 0)}
- Zero-demand rows remaining: {v.get('zero_demand_rows_count', 0)}

## Review reminder
This graph is assumption-based and intended for pre-simulation validation.
Review the assumptions in simulation_prep_report.json before scenario studies.
"""


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    out_graph = Path(args.output_graph)
    out_report_json = Path(args.output_report_json)
    out_report_md = Path(args.output_report_md)

    out_graph.parent.mkdir(parents=True, exist_ok=True)

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    prepared, report = prepare_graph(raw)

    out_graph.write_text(json.dumps(prepared, indent=2, ensure_ascii=False), encoding="utf-8")
    out_report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    out_report_md.write_text(
        report_markdown(report, str(input_path), str(out_graph)),
        encoding="utf-8",
    )
    print(f"[OK] Simulation-ready graph written: {out_graph.resolve()}")
    print(f"[OK] Prep report written: {out_report_json.resolve()}")
    print(f"[OK] Prep report (md) written: {out_report_md.resolve()}")


if __name__ == "__main__":
    main()
