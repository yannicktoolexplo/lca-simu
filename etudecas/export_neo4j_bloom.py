"""Export supply knowledge graph + diagnostics to Neo4j/Bloom friendly CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from supply_issue_graph import (
    _actor_sheet_keys,
    _build_actor_info,
    _build_supply_edges,
    _extract_code,
    _haversine_km,
    _load_data_poc,
    _normalize_product_code,
    _sd_reception_score,
    _zone_scores_from_report,
)


def _num(value: object) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return ""
    if math.isnan(x) or math.isinf(x):
        return ""
    return f"{x:.12g}"


def _text(value: object) -> str:
    if value is None:
        return ""
    s = str(value)
    if s.lower() == "nan":
        return ""
    return s


def _normalize_product_node_id(raw: object) -> str:
    code = _normalize_product_code(raw)
    if code == "unknown":
        return ""
    return f"P:{code}"


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            out = {}
            for key in headers:
                value = row.get(key, "")
                if isinstance(value, float):
                    out[key] = _num(value)
                elif isinstance(value, bool):
                    out[key] = "true" if value else "false"
                else:
                    out[key] = _text(value)
            writer.writerow(out)


def _relation_lookup(data_poc, source_actor_id: str, target_actor_id: str, product_code: str, actor_role_map: dict[str, str]) -> dict | None:
    if data_poc is None:
        return None
    source_keys = _actor_sheet_keys(source_actor_id, actor_role_map[source_actor_id])
    target_keys = _actor_sheet_keys(target_actor_id, actor_role_map[target_actor_id])
    for sk in source_keys:
        for tk in target_keys:
            rel = data_poc.relation_by_triplet.get((sk, tk, product_code))
            if rel is not None:
                return rel
    return None


def export_neo4j(
    graph_path: Path,
    coords_path: Path,
    report_path: Path,
    output_dir: Path,
    data_poc_path: Path | None,
) -> dict[str, int]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    coords = json.loads(coords_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))

    data_poc = _load_data_poc(data_poc_path) if data_poc_path is not None else None
    actor_info = _build_actor_info(graph, coords)
    zone_scores = _zone_scores_from_report(report)
    sd_reception = _sd_reception_score(report)
    supply_edges = _build_supply_edges(graph, actor_info, zone_scores, data_poc=data_poc)

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_by_id = {node["id"]: node for node in nodes}
    actor_role_map = {actor_id: actor.role for actor_id, actor in actor_info.items()}

    supply_props_by_key: dict[tuple[str, str, str], dict] = {}
    for edge in edges:
        if edge.get("relation") != "SUPPLIES":
            continue
        product_id = _normalize_product_node_id(edge.get("product", ""))
        if not product_id:
            continue
        product_code = product_id.replace("P:", "")
        key = (edge.get("source", ""), edge.get("target", ""), product_code)
        supply_props_by_key[key] = edge

    actor_rows = []
    for actor_id, info in sorted(actor_info.items(), key=lambda x: x[0]):
        raw = node_by_id.get(actor_id, {})
        actor_rows.append(
            {
                "actor_id": actor_id,
                "actor_code": _extract_code(actor_id) or actor_id,
                "name": _text(raw.get("id", actor_id)),
                "role": info.role,
                "description": _text(raw.get("description", raw.get("label", ""))),
                "layer": _text(raw.get("layer", "")),
                "location_id": _text(raw.get("location_ID", "")),
                "lat": info.lat,
                "lon": info.lon,
                "degree_centrality": raw.get("degree_centrality", ""),
                "is_placeholder": raw.get("layer", "") == "actor_placeholder",
            }
        )

    product_id_set = set()
    for node in nodes:
        if node.get("layer") == "product":
            normalized = _normalize_product_node_id(node.get("id", ""))
            if normalized:
                product_id_set.add(normalized)
    for edge in edges:
        for endpoint in ("source", "target"):
            node_id = _normalize_product_node_id(edge.get(endpoint, ""))
            if node_id:
                product_id_set.add(node_id)
        node_id = _normalize_product_node_id(edge.get("product", ""))
        if node_id:
            product_id_set.add(node_id)
    for edge in supply_edges:
        product_id_set.add(f"P:{edge.product}")

    bom_criticality = {} if data_poc is None else data_poc.product_bom_criticality
    product_rows = []
    for product_id in sorted(product_id_set):
        raw = node_by_id.get(product_id, {})
        product_code = product_id.replace("P:", "")
        product_rows.append(
            {
                "product_id": product_id,
                "product_code": product_code,
                "name": _text(raw.get("id", product_id)),
                "degree_centrality": raw.get("degree_centrality", ""),
                "bom_criticality": bom_criticality.get(product_code, ""),
            }
        )

    org_rows = []
    for node in nodes:
        if node.get("layer") == "org":
            org_rows.append(
                {
                    "org_id": _text(node.get("id", "")),
                    "name": _text(node.get("id", "")),
                    "layer": _text(node.get("layer", "")),
                }
            )

    issue_rows = []
    issues = report.get("issues", [])
    for idx, issue in enumerate(issues, start=1):
        issue_rows.append(
            {
                "issue_id": f"ISSUE_{idx:03d}",
                "severity": _text(issue.get("severity", "")),
                "area": _text(issue.get("area", "")),
                "description": _text(issue.get("issue", "")),
            }
        )

    zone_rows = []
    for zone, score in sorted(zone_scores.items()):
        zone_rows.append(
            {
                "zone_id": zone.upper(),
                "zone": zone,
                "zone_score": score,
            }
        )

    summary_rows = [
        {
            "summary_id": "SD_RECEPTION",
            "metric": "sd_reception_score",
            "value": sd_reception.get("score", 0.0),
            "details": (
                f"peak_gain_db={sd_reception.get('stock_peak_gain_db', 0.0):.3f},"
                f"distortion={sd_reception.get('stock_distortion_ratio', 0.0):.3f}"
            ),
        }
    ]

    link_rows = []
    rel_actor_to_link = []
    rel_link_to_actor = []
    rel_link_to_product = []
    rel_link_to_zone = []

    distance_values = []
    for idx, edge in enumerate(supply_edges, start=1):
        src = actor_info[edge.source]
        dst = actor_info[edge.target]
        distance_km = _haversine_km(src.lat, src.lon, dst.lat, dst.lon)
        distance_values.append(distance_km)

        product_id = f"P:{edge.product}"
        base_props = supply_props_by_key.get((edge.source, edge.target, edge.product), {})
        rel_data = _relation_lookup(data_poc, edge.source, edge.target, edge.product, actor_role_map)

        if rel_data is not None:
            sell_price = rel_data.get("sell_price", "")
            price_base = rel_data.get("price_base", "")
            quantity_unit = rel_data.get("quantity_unit", "")
            source_dataset = "data_poc"
        else:
            sell_price = base_props.get("sell_price", "")
            price_base = base_props.get("price_base", "")
            quantity_unit = base_props.get("quantity_unit", "")
            source_dataset = "knowledge_graph"

        unit_price = ""
        try:
            if sell_price not in ("", None) and price_base not in ("", None):
                sell_val = float(sell_price)
                base_val = float(price_base)
                if not math.isnan(sell_val) and not math.isnan(base_val) and abs(base_val) > 1e-12:
                    unit_price = sell_val / base_val
        except Exception:
            unit_price = ""

        link_id = f"L{idx:04d}"
        link_rows.append(
            {
                "link_id": link_id,
                "source_actor_id": edge.source,
                "target_actor_id": edge.target,
                "product_id": product_id,
                "zone": edge.zone,
                "material_family": edge.material_family,
                "risk_score": edge.risk_score,
                "risk_display": edge.risk_display,
                "distance_km": distance_km,
                "sell_price": sell_price,
                "price_base": price_base,
                "unit_price": unit_price,
                "quantity_unit": quantity_unit,
                "source_dataset": source_dataset,
            }
        )
        rel_actor_to_link.append({"actor_id": edge.source, "link_id": link_id})
        rel_link_to_actor.append({"link_id": link_id, "actor_id": edge.target})
        rel_link_to_product.append({"link_id": link_id, "product_id": product_id})
        rel_link_to_zone.append({"link_id": link_id, "zone_id": edge.zone.upper()})

    dist_min = min(distance_values) if distance_values else 0.0
    dist_max = max(distance_values) if distance_values else 1.0

    def _distance_norm(distance_km: float) -> float:
        if dist_max - dist_min <= 1e-12:
            return 0.0
        return (distance_km - dist_min) / (dist_max - dist_min)

    issue_to_link_rows = []
    issue_to_actor_rows = []
    issue_to_product_rows = []
    summary_to_actor_rows = []

    actor_reception_candidates = [actor_id for actor_id, info in actor_info.items() if info.role == "Customer"]
    for actor_id in actor_reception_candidates:
        summary_to_actor_rows.append(
            {
                "summary_id": "SD_RECEPTION",
                "actor_id": actor_id,
                "score": sd_reception.get("score", 0.0),
            }
        )

    for idx, issue in enumerate(issue_rows, start=1):
        issue_id = issue["issue_id"]
        area = issue["area"].lower()

        link_scores = []
        for link in link_rows:
            score = float(link["risk_score"])
            zone = _text(link["zone"])
            if "sd" in area:
                score = 0.75 * score + 0.25 * (1.0 if zone in ("distribution_to_customer", "manufacturer_to_distribution") else 0.0)
            elif "transport" in area:
                score = 0.6 * score + 0.4 * _distance_norm(float(link["distance_km"]))
            elif "tail risk" in area or "variability" in area or "service" in area:
                score = 0.85 * score + 0.15 * float(link["risk_display"])
            link_scores.append((link, score))

        link_scores.sort(key=lambda x: x[1], reverse=True)
        selected_links = link_scores[: min(10, len(link_scores))]
        for rank, (link, score) in enumerate(selected_links, start=1):
            issue_to_link_rows.append(
                {
                    "issue_id": issue_id,
                    "link_id": link["link_id"],
                    "impact_score": score,
                    "rank": rank,
                    "zone_hint": link["zone"],
                }
            )

        actor_scores: dict[str, float] = {}
        product_scores: dict[str, float] = {}
        for link, score in selected_links:
            s_actor = _text(link["source_actor_id"])
            t_actor = _text(link["target_actor_id"])
            prod = _text(link["product_id"])
            actor_scores[s_actor] = max(actor_scores.get(s_actor, 0.0), score)
            actor_scores[t_actor] = max(actor_scores.get(t_actor, 0.0), score)
            product_scores[prod] = max(product_scores.get(prod, 0.0), score)

        for rank, (actor_id, score) in enumerate(sorted(actor_scores.items(), key=lambda x: x[1], reverse=True)[:8], start=1):
            issue_to_actor_rows.append(
                {
                    "issue_id": issue_id,
                    "actor_id": actor_id,
                    "impact_score": score,
                    "rank": rank,
                }
            )
        for rank, (product_id, score) in enumerate(
            sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:12],
            start=1,
        ):
            issue_to_product_rows.append(
                {
                    "issue_id": issue_id,
                    "product_id": product_id,
                    "impact_score": score,
                    "rank": rank,
                }
            )

    rel_supplies_product_rows = []
    rel_used_by_rows = []
    rel_bom_rows = []
    rel_org_actor_rows = []
    for edge in edges:
        relation = _text(edge.get("relation", ""))
        source = _text(edge.get("source", ""))
        target = _text(edge.get("target", ""))

        if relation == "SUPPLIES_PRODUCT":
            product_id = _normalize_product_node_id(target)
            if source in actor_info and product_id:
                rel_supplies_product_rows.append({"actor_id": source, "product_id": product_id})
        elif relation == "USED_BY":
            product_id = _normalize_product_node_id(source)
            if target in actor_info and product_id:
                rel_used_by_rows.append({"product_id": product_id, "actor_id": target})
        elif relation == "BOM_COMPONENT_OF":
            source_product = _normalize_product_node_id(source)
            target_product = _normalize_product_node_id(target)
            if source_product and target_product:
                rel_bom_rows.append(
                    {
                        "input_product_id": source_product,
                        "output_product_id": target_product,
                        "quantity": edge.get("quantity", ""),
                        "quantity_unit": edge.get("quantity_unit", ""),
                    }
                )
        elif relation == "OWNS_OR_OPERATES":
            if source and target in actor_info:
                rel_org_actor_rows.append({"org_id": source, "actor_id": target})

    neo_dir = output_dir
    _write_csv(
        neo_dir / "nodes_actor.csv",
        [
            "actor_id",
            "actor_code",
            "name",
            "role",
            "description",
            "layer",
            "location_id",
            "lat",
            "lon",
            "degree_centrality",
            "is_placeholder",
        ],
        actor_rows,
    )
    _write_csv(
        neo_dir / "nodes_product.csv",
        ["product_id", "product_code", "name", "degree_centrality", "bom_criticality"],
        product_rows,
    )
    _write_csv(neo_dir / "nodes_org.csv", ["org_id", "name", "layer"], org_rows)
    _write_csv(neo_dir / "nodes_issue.csv", ["issue_id", "severity", "area", "description"], issue_rows)
    _write_csv(neo_dir / "nodes_zone.csv", ["zone_id", "zone", "zone_score"], zone_rows)
    _write_csv(neo_dir / "nodes_summary.csv", ["summary_id", "metric", "value", "details"], summary_rows)
    _write_csv(
        neo_dir / "nodes_supply_link.csv",
        [
            "link_id",
            "source_actor_id",
            "target_actor_id",
            "product_id",
            "zone",
            "material_family",
            "risk_score",
            "risk_display",
            "distance_km",
            "sell_price",
            "price_base",
            "unit_price",
            "quantity_unit",
            "source_dataset",
        ],
        link_rows,
    )

    _write_csv(neo_dir / "rel_actor_supplies_link.csv", ["actor_id", "link_id"], rel_actor_to_link)
    _write_csv(neo_dir / "rel_link_delivers_to_actor.csv", ["link_id", "actor_id"], rel_link_to_actor)
    _write_csv(neo_dir / "rel_link_for_product.csv", ["link_id", "product_id"], rel_link_to_product)
    _write_csv(neo_dir / "rel_link_in_zone.csv", ["link_id", "zone_id"], rel_link_to_zone)
    _write_csv(neo_dir / "rel_actor_supplies_product.csv", ["actor_id", "product_id"], rel_supplies_product_rows)
    _write_csv(neo_dir / "rel_product_used_by_actor.csv", ["product_id", "actor_id"], rel_used_by_rows)
    _write_csv(
        neo_dir / "rel_bom_component_of.csv",
        ["input_product_id", "output_product_id", "quantity", "quantity_unit"],
        rel_bom_rows,
    )
    _write_csv(neo_dir / "rel_org_operates_actor.csv", ["org_id", "actor_id"], rel_org_actor_rows)
    _write_csv(
        neo_dir / "rel_issue_impacts_link.csv",
        ["issue_id", "link_id", "impact_score", "rank", "zone_hint"],
        issue_to_link_rows,
    )
    _write_csv(
        neo_dir / "rel_issue_impacts_actor.csv",
        ["issue_id", "actor_id", "impact_score", "rank"],
        issue_to_actor_rows,
    )
    _write_csv(
        neo_dir / "rel_issue_impacts_product.csv",
        ["issue_id", "product_id", "impact_score", "rank"],
        issue_to_product_rows,
    )
    _write_csv(
        neo_dir / "rel_summary_highlights_actor.csv",
        ["summary_id", "actor_id", "score"],
        summary_to_actor_rows,
    )

    stats = {
        "actors": len(actor_rows),
        "products": len(product_rows),
        "orgs": len(org_rows),
        "issues": len(issue_rows),
        "zones": len(zone_rows),
        "supply_links": len(link_rows),
        "issue_link_edges": len(issue_to_link_rows),
        "issue_actor_edges": len(issue_to_actor_rows),
        "issue_product_edges": len(issue_to_product_rows),
        "data_poc_used": 1 if data_poc is not None else 0,
        "data_poc_relation_rows": 0 if data_poc is None else len(data_poc.relation_by_triplet),
        "data_poc_relation_rows_matched": 0 if data_poc is None else data_poc.matched_relations,
    }
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Neo4j/Bloom CSV pack for supply risk graph")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json")
    parser.add_argument("--coords", type=str, default="actor_coords.json")
    parser.add_argument("--report", type=str, default="advanced_complex_full_report.json")
    parser.add_argument("--data-poc", type=str, default="Data_poc.xlsx")
    parser.add_argument("--out-dir", type=str, default="neo4j_export")
    args = parser.parse_args()

    data_poc_path = Path(args.data_poc) if args.data_poc else None
    stats = export_neo4j(
        graph_path=Path(args.graph),
        coords_path=Path(args.coords),
        report_path=Path(args.report),
        output_dir=Path(args.out_dir),
        data_poc_path=data_poc_path,
    )

    print("Neo4j export generated in:", args.out_dir)
    for key, value in stats.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()

