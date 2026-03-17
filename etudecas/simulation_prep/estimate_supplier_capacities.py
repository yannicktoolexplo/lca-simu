#!/usr/bin/env python3
"""
Persist estimated supplier daily capacities into a simulation-ready graph.

The estimates are read from a previously generated simulation summary
(`model_inputs.supplier_daily_capacity_pairs`) and injected into
`node.simulation_constraints.supplier_item_capacity_qty_per_day`.

Optionally, the script switches the scenario away from generic external
procurement toward an estimated-capacity source mode for unmodeled supplier
source pairs.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject estimated supplier capacities into a simulation-ready graph.")
    parser.add_argument(
        "--input-graph",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Simulation-ready input graph JSON.",
    )
    parser.add_argument(
        "--summary-json",
        default="etudecas/simulation/result/summaries/first_simulation_summary.json",
        help="Simulation summary JSON containing supplier_daily_capacity_pairs.",
    )
    parser.add_argument(
        "--output-graph",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready_estimated_supplier_capacity.json",
        help="Output graph JSON with explicit supplier capacities.",
    )
    parser.add_argument(
        "--report-json",
        default="etudecas/simulation_prep/result/estimated_supplier_capacity_report.json",
        help="Machine-readable report path.",
    )
    parser.add_argument(
        "--report-md",
        default="etudecas/simulation_prep/result/estimated_supplier_capacity_report.md",
        help="Markdown report path.",
    )
    parser.add_argument(
        "--scenario-id",
        default="scn:BASE",
        help="Scenario id to update.",
    )
    parser.add_argument(
        "--activate-estimated-source-mode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Set scenario.unmodeled_supplier_source_mode=estimated_capacity.",
    )
    parser.add_argument(
        "--disable-external-procurement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Disable generic external procurement in the scenario economic policy.",
    )
    return parser.parse_args()


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
    return scenarios[0] if scenarios else {"id": scenario_id}


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    args = parse_args()
    graph_path = Path(args.input_graph)
    summary_path = Path(args.summary_json)
    output_graph_path = Path(args.output_graph)
    report_json_path = Path(args.report_json)
    report_md_path = Path(args.report_md)

    graph = load_json(graph_path)
    summary = load_json(summary_path)
    capacity_rows = (
        (summary.get("production_tracking") or {}).get("supplier_daily_capacity_pairs")
        or (summary.get("model_inputs") or {}).get("supplier_daily_capacity_pairs")
        or []
    )
    if not capacity_rows:
        raise RuntimeError(f"No supplier_daily_capacity_pairs found in {summary_path}")

    nodes = graph.get("nodes", []) or []
    nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id") is not None}

    updated_pairs = 0
    nodes_touched: set[str] = set()
    explicit_bases: dict[str, str] = {}
    for row in capacity_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        node = nodes_by_id.get(node_id)
        if not isinstance(node, dict):
            continue
        sim_constraints = node.get("simulation_constraints")
        if not isinstance(sim_constraints, dict):
            sim_constraints = {}
        capacity_map = sim_constraints.get("supplier_item_capacity_qty_per_day")
        if not isinstance(capacity_map, dict):
            capacity_map = {}
        basis_map = sim_constraints.get("supplier_item_capacity_basis")
        if not isinstance(basis_map, dict):
            basis_map = {}
        effective_capacity = max(0.0, to_float(row.get("effective_capacity_qty_per_day"), 0.0))
        if effective_capacity <= 0:
            continue
        capacity_map[item_id] = round(effective_capacity, 6)
        basis = str(row.get("basis") or "derived")
        basis_map[item_id] = basis
        sim_constraints["supplier_item_capacity_qty_per_day"] = capacity_map
        sim_constraints["supplier_item_capacity_basis"] = basis_map
        node["simulation_constraints"] = sim_constraints
        nodes_touched.add(node_id)
        updated_pairs += 1
        explicit_bases[basis] = explicit_bases.get(basis, 0) + 1

    scenario = choose_scenario(graph, args.scenario_id)
    economic_policy = scenario.get("economic_policy")
    if not isinstance(economic_policy, dict):
        economic_policy = {}
    if args.activate_estimated_source_mode:
        scenario["unmodeled_supplier_source_mode"] = "estimated_replenishment"
    if args.disable_external_procurement:
        economic_policy["external_procurement_enabled"] = False
    scenario["economic_policy"] = economic_policy

    meta = graph.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["estimated_supplier_capacity_injection"] = {
        "applied_on_utc": datetime.now(timezone.utc).isoformat(),
        "input_graph": str(graph_path),
        "summary_json": str(summary_path),
        "scenario_id": args.scenario_id,
        "activate_estimated_source_mode": bool(args.activate_estimated_source_mode),
        "disable_external_procurement": bool(args.disable_external_procurement),
        "updated_supplier_item_pairs": updated_pairs,
        "updated_supplier_nodes": len(nodes_touched),
        "basis_counts": explicit_bases,
    }
    graph["meta"] = meta

    write_json(output_graph_path, graph)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_graph": str(graph_path),
        "summary_json": str(summary_path),
        "output_graph": str(output_graph_path),
        "scenario_id": args.scenario_id,
        "activate_estimated_source_mode": bool(args.activate_estimated_source_mode),
        "disable_external_procurement": bool(args.disable_external_procurement),
        "updated_supplier_item_pairs": updated_pairs,
        "updated_supplier_nodes": sorted(nodes_touched),
        "basis_counts": explicit_bases,
    }
    write_json(report_json_path, report)

    lines = [
        "# Estimated Supplier Capacity Injection",
        "",
        "## Summary",
        f"- Input graph: {graph_path}",
        f"- Summary source: {summary_path}",
        f"- Output graph: {output_graph_path}",
        f"- Scenario updated: {args.scenario_id}",
        f"- Estimated source mode activated: {args.activate_estimated_source_mode}",
        f"- External procurement disabled: {args.disable_external_procurement}",
        f"- Supplier-item capacities injected: {updated_pairs}",
        f"- Supplier nodes touched: {len(nodes_touched)}",
        f"- Basis counts: {explicit_bases}",
        "",
        "## Nodes touched",
    ]
    for node_id in sorted(nodes_touched):
        lines.append(f"- {node_id}")
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[OK] Output graph: {output_graph_path.resolve()}")
    print(f"[OK] Report JSON: {report_json_path.resolve()}")
    print(f"[OK] Report MD: {report_md_path.resolve()}")


if __name__ == "__main__":
    main()
