#!/usr/bin/env python3
"""
First-pass supply analysis for supply_graph_poc-style JSON.

Outputs:
- summary.json
- report.md
- node_degrees.csv
- single_source_risk.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a first-pass supply analysis.")
    parser.add_argument(
        "--input",
        default="etudecas/result_geocodage/supply_graph_poc_geocoded.json",
        help="Input JSON file (supply graph).",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/SC_first_analysis/results",
        help="Directory where analysis artifacts are written.",
    )
    return parser.parse_args()


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(item.get(key, "unknown")) for item in items)
    return dict(sorted(counter.items(), key=lambda x: (-x[1], x[0])))


def weakly_connected_components(node_ids: list[str], edges: list[dict[str, Any]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for e in edges:
        src = e.get("from")
        dst = e.get("to")
        if src in adjacency and dst in adjacency:
            adjacency[src].add(dst)
            adjacency[dst].add(src)

    seen: set[str] = set()
    components: list[list[str]] = []
    for nid in node_ids:
        if nid in seen:
            continue
        queue = deque([nid])
        seen.add(nid)
        comp: list[str] = []
        while queue:
            cur = queue.popleft()
            comp.append(cur)
            for nxt in adjacency[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        components.append(sorted(comp))
    return sorted(components, key=len, reverse=True)


def item_path_exists(
    item_id: str,
    target_node: str,
    per_item_adj: dict[str, dict[str, set[str]]],
    per_item_indeg: dict[str, dict[str, int]],
) -> bool:
    graph = per_item_adj.get(item_id, {})
    indeg = per_item_indeg.get(item_id, {})
    if target_node not in indeg and target_node not in graph:
        return False

    nodes = set(indeg.keys()) | set(graph.keys())
    sources = [n for n in nodes if indeg.get(n, 0) == 0 and graph.get(n)]
    if not sources:
        return False

    visited: set[str] = set()
    queue = deque(sources)
    visited.update(sources)
    while queue:
        cur = queue.popleft()
        if cur == target_node:
            return True
        for nxt in graph.get(cur, set()):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return False


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    items = data.get("items", []) or []
    nodes = data.get("nodes", []) or []
    edges = data.get("edges", []) or []
    scenarios = data.get("scenarios", []) or []

    node_ids = [str(n.get("id")) for n in nodes if n.get("id")]
    node_set = set(node_ids)
    item_ids = {str(i.get("id")) for i in items if i.get("id")}
    nodes_by_id = {str(n.get("id")): n for n in nodes if n.get("id")}

    indeg = {nid: 0 for nid in node_ids}
    outdeg = {nid: 0 for nid in node_ids}
    suppliers_by_to_item: dict[tuple[str, str], set[str]] = defaultdict(set)
    unique_suppliers_per_item: dict[str, set[str]] = defaultdict(set)
    per_item_adj: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    per_item_indeg: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    edge_item_missing_refs: list[dict[str, Any]] = []
    for e in edges:
        src = str(e.get("from"))
        dst = str(e.get("to"))
        if src in outdeg:
            outdeg[src] += 1
        if dst in indeg:
            indeg[dst] += 1

        e_items = e.get("items", [])
        if not isinstance(e_items, list):
            e_items = []
        for item_id in e_items:
            iid = str(item_id)
            if iid not in item_ids:
                edge_item_missing_refs.append({"edge_id": e.get("id"), "item_id": iid})
            suppliers_by_to_item[(dst, iid)].add(src)
            unique_suppliers_per_item[iid].add(src)
            per_item_adj[iid][src].add(dst)
            per_item_indeg[iid][dst] += 1
            per_item_indeg[iid].setdefault(src, per_item_indeg[iid].get(src, 0))

    isolated_nodes = sorted([nid for nid in node_ids if indeg[nid] == 0 and outdeg[nid] == 0])
    source_nodes = sorted([nid for nid in node_ids if indeg[nid] == 0 and outdeg[nid] > 0])
    sink_nodes = sorted([nid for nid in node_ids if outdeg[nid] == 0 and indeg[nid] > 0])
    components = weakly_connected_components(node_ids, edges)

    geo_total = len(nodes)
    geo_filled = 0
    geo_null = 0
    node_country_counts: Counter[str] = Counter()
    for n in nodes:
        geo = n.get("geo") or {}
        lat = safe_float(geo.get("lat"))
        lon = safe_float(geo.get("lon"))
        country = str(geo.get("country") or "unknown")
        node_country_counts[country] += 1
        if lat is not None and lon is not None:
            geo_filled += 1
        else:
            geo_null += 1

    single_source_rows: list[dict[str, Any]] = []
    for (to_node, item_id), suppliers in sorted(suppliers_by_to_item.items()):
        if len(suppliers) == 1:
            single_source_rows.append(
                {
                    "receiving_node": to_node,
                    "item_id": item_id,
                    "supplier_count": 1,
                    "suppliers": sorted(suppliers),
                }
            )

    low_supplier_items = []
    for iid in sorted(unique_suppliers_per_item):
        c = len(unique_suppliers_per_item[iid])
        if c <= 1:
            low_supplier_items.append({"item_id": iid, "supplier_count": c})

    demand_rows: list[dict[str, Any]] = []
    for scn in scenarios:
        sid = str(scn.get("id", ""))
        demand = scn.get("demand", []) or []
        for d in demand:
            node_id = str(d.get("node_id"))
            item_id = str(d.get("item_id"))
            profile = d.get("profile", []) or []
            values = [safe_float(p.get("value")) for p in profile if isinstance(p, dict)]
            values = [v for v in values if v is not None]
            reachable = item_path_exists(item_id, node_id, per_item_adj, per_item_indeg)
            demand_rows.append(
                {
                    "scenario_id": sid,
                    "node_id": node_id,
                    "item_id": item_id,
                    "profile_points": len(profile),
                    "demand_values": values,
                    "is_zero_demand": all(v == 0 for v in values) if values else True,
                    "reachable_from_upstream": reachable,
                }
            )

    edge_defaults = {
        "lead_time_is_default": sum(
            1 for e in edges if isinstance(e.get("lead_time"), dict) and e["lead_time"].get("is_default") is True
        ),
        "transport_cost_zero_default": sum(
            1
            for e in edges
            if isinstance(e.get("transport_cost"), dict)
            and e["transport_cost"].get("is_default") is True
            and safe_float(e["transport_cost"].get("value")) == 0
        ),
        "delay_limit_default": sum(
            1
            for e in edges
            if isinstance(e.get("delay_step_limit"), dict)
            and e["delay_step_limit"].get("is_default") is True
        ),
        "order_terms_price_null": sum(
            1
            for e in edges
            if isinstance(e.get("order_terms"), dict)
            and e["order_terms"].get("sell_price") is None
        ),
    }

    process_count = 0
    process_capacity_default = 0
    process_cost_default = 0
    inventory_states = 0
    inventory_initial_default = 0
    for n in nodes:
        inv = n.get("inventory", {}) or {}
        for state in inv.get("states", []) or []:
            inventory_states += 1
            if state.get("is_default_initial") is True:
                inventory_initial_default += 1
        for p in n.get("processes", []) or []:
            process_count += 1
            if isinstance(p.get("capacity"), dict) and p["capacity"].get("is_default") is True:
                process_capacity_default += 1
            if isinstance(p.get("cost"), dict) and p["cost"].get("is_default") is True:
                process_cost_default += 1

    top_in = sorted(indeg.items(), key=lambda x: (-x[1], x[0]))[:5]
    top_out = sorted(outdeg.items(), key=lambda x: (-x[1], x[0]))[:5]
    top_countries = sorted(node_country_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

    edge_country_known = 0
    edge_cross_border = 0
    edge_domestic = 0
    edge_missing_country = 0
    for e in edges:
        src = str(e.get("from"))
        dst = str(e.get("to"))
        src_country = str(((nodes_by_id.get(src, {}).get("geo") or {}).get("country")) or "").strip()
        dst_country = str(((nodes_by_id.get(dst, {}).get("geo") or {}).get("country")) or "").strip()
        if not src_country or not dst_country:
            edge_missing_country += 1
            continue
        edge_country_known += 1
        if src_country == dst_country:
            edge_domestic += 1
        else:
            edge_cross_border += 1

    return {
        "schema_version": data.get("schema_version"),
        "meta": data.get("meta", {}),
        "counts": {
            "items": len(items),
            "nodes": len(nodes),
            "edges": len(edges),
            "scenarios": len(scenarios),
        },
        "distribution": {
            "node_types": count_by(nodes, "type"),
            "edge_types": count_by(edges, "type"),
        },
        "connectivity": {
            "isolated_nodes": isolated_nodes,
            "source_nodes": source_nodes,
            "sink_nodes": sink_nodes,
            "weakly_connected_components": {
                "count": len(components),
                "sizes": [len(c) for c in components],
                "largest_component_size": len(components[0]) if components else 0,
            },
            "top_in_degree": top_in,
            "top_out_degree": top_out,
        },
        "data_quality": {
            "geo": {
                "total_nodes": geo_total,
                "filled_lat_lon": geo_filled,
                "missing_lat_lon": geo_null,
            },
            "edge_defaults": edge_defaults,
            "inventory_states": inventory_states,
            "inventory_initial_default_count": inventory_initial_default,
            "process_count": process_count,
            "process_capacity_default_count": process_capacity_default,
            "process_cost_default_count": process_cost_default,
            "edge_item_missing_refs": edge_item_missing_refs,
        },
        "geography": {
            "node_country_distribution": dict(sorted(node_country_counts.items(), key=lambda x: (-x[1], x[0]))),
            "top_countries": top_countries,
            "edge_country_known_count": edge_country_known,
            "edge_cross_border_count": edge_cross_border,
            "edge_domestic_count": edge_domestic,
            "edge_missing_country_count": edge_missing_country,
        },
        "supply_risk": {
            "single_source_receiving_pairs_count": len(single_source_rows),
            "single_source_receiving_pairs": single_source_rows,
            "items_with_one_or_zero_unique_suppliers": low_supplier_items,
        },
        "demand_checks": {
            "rows": demand_rows,
            "unreachable_demand_rows": [r for r in demand_rows if not r["reachable_from_upstream"]],
            "zero_demand_rows": [r for r in demand_rows if r["is_zero_demand"]],
        },
        "node_degrees": [{"node_id": nid, "in_degree": indeg[nid], "out_degree": outdeg[nid]} for nid in node_ids],
    }


def write_outputs(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with (output_dir / "node_degrees.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["node_id", "in_degree", "out_degree"])
        writer.writeheader()
        for row in summary["node_degrees"]:
            writer.writerow(row)

    with (output_dir / "single_source_risk.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["receiving_node", "item_id", "supplier_count", "suppliers"])
        writer.writeheader()
        for row in summary["supply_risk"]["single_source_receiving_pairs"]:
            writer.writerow(
                {
                    "receiving_node": row["receiving_node"],
                    "item_id": row["item_id"],
                    "supplier_count": row["supplier_count"],
                    "suppliers": ";".join(row["suppliers"]),
                }
            )

    counts = summary["counts"]
    connectivity = summary["connectivity"]
    quality = summary["data_quality"]
    geography = summary.get("geography", {})
    risk = summary["supply_risk"]
    demand_checks = summary["demand_checks"]
    top_countries = geography.get("top_countries", [])
    top_in = connectivity.get("top_in_degree", [])
    top_out = connectivity.get("top_out_degree", [])
    single_source = risk.get("single_source_receiving_pairs", [])

    def pct(n: int, d: int) -> str:
        if d <= 0:
            return "n/a"
        return f"{(100.0 * n / d):.1f}%"

    components_count = connectivity["weakly_connected_components"]["count"]
    isolated_count = len(connectivity["isolated_nodes"])
    geo_fill_pct = pct(quality["geo"]["filled_lat_lon"], quality["geo"]["total_nodes"])
    cross_border_pct = pct(
        geography.get("edge_cross_border_count", 0),
        geography.get("edge_country_known_count", 0),
    )
    single_source_ratio = pct(
        risk["single_source_receiving_pairs_count"],
        counts["edges"],
    )

    q1_status = "Oui" if components_count == 1 and isolated_count == 0 else "Partiel"
    q2_status = "Oui"
    q3_status = "Partiel" if len(demand_checks["zero_demand_rows"]) > 0 else "Oui"
    q4_status = "Partiel"
    q5_status = "Oui"
    q6_status = "Partiel"

    top_in_lines = "\n".join(
        f"| {node_id} | {score} |"
        for node_id, score in top_in
    ) or "| n/a | 0 |"
    top_out_lines = "\n".join(
        f"| {node_id} | {score} |"
        for node_id, score in top_out
    ) or "| n/a | 0 |"
    top_country_lines = "\n".join(
        f"| {country} | {count} |"
        for country, count in top_countries[:8]
    ) or "| n/a | 0 |"
    single_source_lines = "\n".join(
        f"| {row['receiving_node']} | {row['item_id']} | {';'.join(row['suppliers'])} |"
        for row in single_source[:10]
    ) or "| n/a | n/a | n/a |"

    priority_actions: list[str] = []
    if len(demand_checks["zero_demand_rows"]) > 0:
        priority_actions.append("Renseigner une demande non nulle pour pouvoir tester le service level et les ruptures.")
    if quality["edge_defaults"]["lead_time_is_default"] == counts["edges"]:
        priority_actions.append("Remplacer les lead times par défaut sur les arcs critiques.")
    if quality["edge_defaults"]["transport_cost_zero_default"] == counts["edges"]:
        priority_actions.append("Renseigner les coûts logistiques pour fiabiliser le coût total.")
    if risk["single_source_receiving_pairs_count"] > 0:
        priority_actions.append("Traiter les couples mono-source (dual sourcing ou stock de sécurité ciblé).")
    if isolated_count > 0:
        priority_actions.append("Décider du sort des nœuds isolés (supprimer, connecter ou documenter).")
    if not priority_actions:
        priority_actions.append("Aucune priorité bloquante détectée sur ce premier passage.")

    priority_lines = "\n".join(f"- {line}" for line in priority_actions)

    report = f"""# SC first analysis

## Executive summary
- Items: {counts['items']}
- Nodes: {counts['nodes']}
- Edges: {counts['edges']}
- Scenarios: {counts['scenarios']}
- Geo completeness: {quality['geo']['filled_lat_lon']} / {quality['geo']['total_nodes']} ({geo_fill_pct})
- Single-source pairs: {risk['single_source_receiving_pairs_count']} ({single_source_ratio} des edges)
- Cross-border edges: {geography.get('edge_cross_border_count', 0)} / {geography.get('edge_country_known_count', 0)} ({cross_border_pct})

## Coverage des questions d'analyse
| Question | Statut | Evidence |
|---|---|---|
| 1. Structure réseau saine ? | {q1_status} | {components_count} composantes, {isolated_count} nœuds isolés |
| 2. Dépendances critiques ? | {q2_status} | {risk['single_source_receiving_pairs_count']} couples mono-source |
| 3. Demande servable ? | {q3_status} | {len(demand_checks['rows'])} lignes, {len(demand_checks['unreachable_demand_rows'])} non atteignables, {len(demand_checks['zero_demand_rows'])} à demande nulle |
| 4. Risque géographique ? | {q4_status} | {geography.get('edge_cross_border_count', 0)} flux cross-border, concentration pays mesurée |
| 5. Réel vs défaut ? | {q5_status} | lead_time par défaut: {quality['edge_defaults']['lead_time_is_default']}/{counts['edges']} |
| 6. Priorités d'enrichissement ? | {q6_status} | Voir section Priorités |

## Connectivity
- Weakly connected components: {connectivity['weakly_connected_components']['count']}
- Largest component size: {connectivity['weakly_connected_components']['largest_component_size']}
- Isolated nodes: {len(connectivity['isolated_nodes'])}
- Source nodes: {len(connectivity['source_nodes'])}
- Sink nodes: {len(connectivity['sink_nodes'])}

### Top nœuds entrants (in-degree)
| Node | In-degree |
|---|---|
{top_in_lines}

### Top nœuds sortants (out-degree)
| Node | Out-degree |
|---|---|
{top_out_lines}

## Data quality
- Geo filled (lat/lon): {quality['geo']['filled_lat_lon']} / {quality['geo']['total_nodes']}
- Edge lead_time default count: {quality['edge_defaults']['lead_time_is_default']} / {counts['edges']}
- Edge transport_cost zero default count: {quality['edge_defaults']['transport_cost_zero_default']} / {counts['edges']}
- Inventory states with default initial: {quality['inventory_initial_default_count']} / {quality['inventory_states']}
- Process capacity default count: {quality['process_capacity_default_count']} / {quality['process_count']}
- Process cost default count: {quality['process_cost_default_count']} / {quality['process_count']}

## Geography
- Countries represented: {len(geography.get('node_country_distribution', {}))}
- Edge with known countries: {geography.get('edge_country_known_count', 0)} / {counts['edges']}
- Cross-border edges: {geography.get('edge_cross_border_count', 0)}
- Domestic edges: {geography.get('edge_domestic_count', 0)}

### Top countries (nodes)
| Country | Node count |
|---|---|
{top_country_lines}

## Supply risk
- Single-source receiving pairs: {risk['single_source_receiving_pairs_count']}
- Items with <=1 unique supplier: {len(risk['items_with_one_or_zero_unique_suppliers'])}

### Sample mono-source pairs (top 10)
| Receiving node | Item | Supplier |
|---|---|---|
{single_source_lines}

## Demand checks
- Demand rows: {len(demand_checks['rows'])}
- Unreachable demand rows: {len(demand_checks['unreachable_demand_rows'])}
- Zero-demand rows: {len(demand_checks['zero_demand_rows'])}

## Priorités d'action
{priority_lines}

## Files generated
- summary.json
- node_degrees.csv
- single_source_risk.csv
"""
    (output_dir / "report.md").write_text(report, encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    summary = analyze(data)
    write_outputs(summary, output_dir)
    print(f"[OK] Analysis written to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
