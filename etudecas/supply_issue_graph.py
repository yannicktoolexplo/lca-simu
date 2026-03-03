"""Plot full supply knowledge graph and annotate issue hotspots."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

from supply_graph_tools import _canonical_coord_keys, _extract_code, _infer_role


@dataclass
class ActorInfo:
    actor_id: str
    role: str
    description: str
    lat: float
    lon: float


@dataclass
class SupplyEdgeInfo:
    source: str
    target: str
    product: str
    relation: str
    zone: str
    risk_score: float
    risk_display: float
    material_family: str


@dataclass
class DataPocInfo:
    relation_by_triplet: dict[tuple[str, str, str], dict[str, float | str]]
    product_bom_criticality: dict[str, float]
    matched_relations: int = 0
    unmatched_relations: int = 0


def _safe_float(value: object, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius_km * math.asin(math.sqrt(a))


def _material_family(description: str) -> str:
    d = (description or "").lower()
    if "raw material" in d:
        return "raw_material"
    if "packaging" in d:
        return "packaging"
    if "manufacturer" in d or "drugs" in d or "cosmetics" in d:
        return "finished_or_intermediate"
    return "other"


def _normalize_product(product: str) -> str:
    value = (product or "").replace("P:", "").strip()
    return value if value else "unknown"


def _normalize_product_code(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    text = text.replace("P:", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _actor_sheet_keys(actor_id: str, role: str) -> list[str]:
    code = _extract_code(actor_id)
    if not code:
        return []
    prefix = {
        "Supplier Distribution Center": "SDC",
        "Manufacturer": "M",
        "Distribution Center": "DC",
        "Customer": "C",
    }.get(role, "")
    keys = []
    if prefix:
        keys.append(f"{prefix} - {code}")
        if prefix in ("DC", "M", "C") and code.startswith("D"):
            keys.append(f"{prefix} - {code[1:]}")
        if prefix == "DC" and code.isdigit():
            keys.append(f"{prefix} - D{code}")
    return list(dict.fromkeys(keys))


def _load_data_poc(data_poc_path: str | Path | None) -> DataPocInfo | None:
    if data_poc_path is None:
        return None
    path = Path(data_poc_path)
    if not path.exists():
        return None

    relation_by_triplet: dict[tuple[str, str, str], dict[str, float | str]] = {}
    product_bom_criticality: dict[str, float] = {}

    try:
        relations = pd.read_excel(path, sheet_name="Relations_acteurs")
        bom = pd.read_excel(path, sheet_name="BOM")
    except Exception:
        return None

    for _, row in relations.iterrows():
        supplier = str(row.get("supplier", "")).strip()
        customer = str(row.get("customer", "")).strip()
        product = _normalize_product_code(row.get("product", ""))
        if not supplier or not customer or product == "unknown":
            continue
        relation_by_triplet[(supplier, customer, product)] = {
            "sell_price": _safe_float(row.get("sell_price"), default=float("nan")),
            "price_base": _safe_float(row.get("price_base"), default=float("nan")),
            "quantity_unit": str(row.get("quantity_unit", "")).strip(),
            "supply_order_frequency": _safe_float(row.get("supply_order_frequency"), default=float("nan")),
            "customer_priority_rank": _safe_float(row.get("customer_priority_rank"), default=float("nan")),
            "supplier_priority_rank": _safe_float(row.get("supplier_priority_rank"), default=float("nan")),
            "delay_step_limit": _safe_float(row.get("delay_step_limit"), default=float("nan")),
            "transport_cost": _safe_float(row.get("transport_cost"), default=float("nan")),
        }

    bom_valid = bom[(bom.get("output_product").notna()) & (bom.get("input_product").notna())].copy()
    if not bom_valid.empty:
        bom_valid["output_product_norm"] = bom_valid["output_product"].apply(_normalize_product_code)
        bom_valid["input_product_norm"] = bom_valid["input_product"].apply(_normalize_product_code)
        bom_valid["quantity_num"] = bom_valid["quantity"].apply(lambda x: max(0.0, _safe_float(x, default=0.0)))
        totals_by_output = bom_valid.groupby("output_product_norm")["quantity_num"].sum().to_dict()
        raw_score: dict[str, float] = defaultdict(float)
        for _, row in bom_valid.iterrows():
            output_product = row["output_product_norm"]
            input_product = row["input_product_norm"]
            total = totals_by_output.get(output_product, 0.0)
            if total <= 1e-12:
                continue
            raw_score[input_product] += float(row["quantity_num"]) / total
        if raw_score:
            max_score = max(raw_score.values())
            if max_score > 1e-12:
                product_bom_criticality = {k: float(v / max_score) for k, v in raw_score.items()}

    return DataPocInfo(
        relation_by_triplet=relation_by_triplet,
        product_bom_criticality=product_bom_criticality,
        matched_relations=0,
        unmatched_relations=len(relation_by_triplet),
    )


def _stage_zone_from_backlog_key(backlog_key: str) -> str:
    key = backlog_key.replace("backlog_", "")
    if "distribution_to_stock_arrivee_ligne_production" in key:
        return "distribution_to_customer"
    if "stock_distribution_to_distribution" in key:
        return "manufacturer_to_distribution"
    if "stock_amont_to_stock_apres_transport_amont" in key:
        return "supplier_to_manufacturer"
    if "stock_apres_transport_amont_to_transformation_1" in key:
        return "supplier_to_manufacturer"
    if "transformation_1" in key or "transformation_2" in key or "stock_apres_transport_t1_to_transformation_2" in key:
        return "manufacturing_internal"
    return "other"


def _role_flow_zone(source_role: str, target_role: str) -> str:
    if source_role == "Supplier Distribution Center" and target_role == "Manufacturer":
        return "supplier_to_manufacturer"
    if source_role == "Manufacturer" and target_role == "Distribution Center":
        return "manufacturer_to_distribution"
    if source_role == "Distribution Center" and target_role == "Customer":
        return "distribution_to_customer"
    return "other"


def _fallback_positions(actor_ids: list[str], actor_roles: dict[str, str]) -> dict[str, tuple[float, float]]:
    by_role: dict[str, list[str]] = {}
    for actor_id in actor_ids:
        by_role.setdefault(actor_roles[actor_id], []).append(actor_id)

    role_order = [
        "Supplier Distribution Center",
        "Manufacturer",
        "Distribution Center",
        "Customer",
        "Unknown",
    ]
    role_x = {role: float(i) for i, role in enumerate(role_order)}

    output: dict[str, tuple[float, float]] = {}
    for role, ids in by_role.items():
        ids_sorted = sorted(ids)
        x = role_x.get(role, float(len(role_order)))
        for idx, actor_id in enumerate(ids_sorted):
            y = float(idx) - 0.5 * max(0, len(ids_sorted) - 1)
            output[actor_id] = (x, y)
    return output


def _build_actor_info(graph: dict, coords: dict[str, list[float]]) -> dict[str, ActorInfo]:
    actor_nodes = [n for n in graph.get("nodes", []) if n.get("layer") in ("actor", "actor_placeholder")]
    actor_ids = [n["id"] for n in actor_nodes]
    actor_roles = {n["id"]: _infer_role(n["id"], n.get("role")) for n in actor_nodes}

    fallback = _fallback_positions(actor_ids, actor_roles)
    actor_info: dict[str, ActorInfo] = {}

    for node in actor_nodes:
        actor_id = node["id"]
        role = actor_roles[actor_id]
        description = str(node.get("description") or node.get("label") or actor_id)

        lat = None
        lon = None
        for key in _canonical_coord_keys(actor_id, role):
            if key in coords:
                coord = coords[key]
                if isinstance(coord, list) and len(coord) >= 2:
                    lat = _safe_float(coord[0], default=float("nan"))
                    lon = _safe_float(coord[1], default=float("nan"))
                    break

        if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
            fx, fy = fallback[actor_id]
            lon = fx
            lat = fy

        actor_info[actor_id] = ActorInfo(
            actor_id=actor_id,
            role=role,
            description=description,
            lat=float(lat),
            lon=float(lon),
        )
    return actor_info


def _zone_scores_from_report(report: dict) -> dict[str, float]:
    bottlenecks = report.get("des_distribution", {}).get("top_bottlenecks", [])
    raw_scores: dict[str, float] = {
        "supplier_to_manufacturer": 0.0,
        "manufacturing_internal": 0.0,
        "manufacturer_to_distribution": 0.0,
        "distribution_to_customer": 0.0,
        "other": 0.0,
    }

    for item in bottlenecks:
        key = str(item.get("link_backlog_key", ""))
        p95 = float(item.get("p95_max_backlog", 0.0))
        zone = _stage_zone_from_backlog_key(key)
        raw_scores[zone] = max(raw_scores.get(zone, 0.0), p95)

    max_score = max(raw_scores.values()) if raw_scores else 0.0
    if max_score <= 1e-12:
        return {k: 0.0 for k in raw_scores}
    return {k: v / max_score for k, v in raw_scores.items()}


def _sd_reception_score(report: dict) -> dict[str, float]:
    summary = report.get("sd_frequency", {}).get("summary", {})
    stock_summary = summary.get("stock_arrivee", {})
    backlog_summary = summary.get("backlog_client", {})
    gain_db = float(stock_summary.get("peak_gain_db", 0.0))
    distortion = float(stock_summary.get("max_distortion_ratio", 0.0))
    backlog_gain = float(backlog_summary.get("peak_gain_db", -300.0))

    gain_score = min(1.0, max(0.0, gain_db / 24.0))
    distortion_score = min(1.0, max(0.0, distortion / 0.35))
    backlog_score = min(1.0, max(0.0, (backlog_gain + 12.0) / 12.0))
    score = max(gain_score, 0.65 * distortion_score, 0.45 * backlog_score)

    return {
        "score": score,
        "stock_peak_gain_db": gain_db,
        "stock_distortion_ratio": distortion,
        "backlog_peak_gain_db": backlog_gain,
    }


def _build_supply_edges(
    graph: dict,
    actor_info: dict[str, ActorInfo],
    zone_scores: dict[str, float],
    data_poc: DataPocInfo | None = None,
) -> list[SupplyEdgeInfo]:
    raw_edges: list[dict] = []
    product_suppliers: dict[str, set[str]] = defaultdict(set)
    target_in_degree: Counter[str] = Counter()
    distances_km: list[float] = []
    unit_costs: list[float] = []

    for edge in graph.get("edges", []):
        if edge.get("relation") != "SUPPLIES":
            continue
        source = edge.get("source")
        target = edge.get("target")
        if source not in actor_info or target not in actor_info:
            continue
        raw_edges.append(edge)
        product = _normalize_product(str(edge.get("product") or ""))
        product_suppliers[product].add(source)
        target_in_degree[target] += 1

        src = actor_info[source]
        dst = actor_info[target]
        distances_km.append(_haversine_km(src.lat, src.lon, dst.lat, dst.lon))

        if data_poc is not None:
            source_keys = _actor_sheet_keys(source, actor_info[source].role)
            target_keys = _actor_sheet_keys(target, actor_info[target].role)
            relation_data = None
            for sk in source_keys:
                for tk in target_keys:
                    candidate = data_poc.relation_by_triplet.get((sk, tk, product))
                    if candidate is not None:
                        relation_data = candidate
                        break
                if relation_data is not None:
                    break
            if relation_data is not None:
                sell_price = relation_data.get("sell_price")
                price_base = relation_data.get("price_base")
            else:
                sell_price = edge.get("sell_price")
                price_base = edge.get("price_base")
        else:
            sell_price = edge.get("sell_price")
            price_base = edge.get("price_base")

        if isinstance(sell_price, (int, float)) and isinstance(price_base, (int, float)) and price_base not in (0, 0.0):
            if not (math.isnan(float(sell_price)) or math.isnan(float(price_base))):
                unit_costs.append(max(0.0, float(sell_price) / float(price_base)))

    if not raw_edges:
        return []

    scarcity_values = [1.0 / max(1, len(product_suppliers[_normalize_product(str(e.get("product") or ""))])) for e in raw_edges]
    max_in_degree = max(target_in_degree.values()) if target_in_degree else 1
    min_dist = min(distances_km) if distances_km else 0.0
    max_dist = max(distances_km) if distances_km else 1.0
    min_scarcity = min(scarcity_values) if scarcity_values else 0.0
    max_scarcity = max(scarcity_values) if scarcity_values else 1.0
    min_cost = min(unit_costs) if unit_costs else 0.0
    max_cost = max(unit_costs) if unit_costs else 1.0

    def _norm(value: float, vmin: float, vmax: float) -> float:
        if vmax - vmin <= 1e-12:
            return 0.5
        return min(1.0, max(0.0, (value - vmin) / (vmax - vmin)))

    out: list[SupplyEdgeInfo] = []
    raw_scores: list[float] = []
    for edge in raw_edges:
        source = edge["source"]
        target = edge["target"]

        source_role = actor_info[source].role
        target_role = actor_info[target].role
        zone = _role_flow_zone(source_role, target_role)
        zone_risk = zone_scores.get(zone, 0.0)
        if zone == "other":
            zone_risk = max(zone_risk, zone_scores.get("manufacturing_internal", 0.0) * 0.7)

        product = _normalize_product(str(edge.get("product") or ""))
        supplier_count = max(1, len(product_suppliers[product]))
        scarcity = _norm(1.0 / supplier_count, min_scarcity, max_scarcity)
        concentration = min(1.0, max(0.0, target_in_degree[target] / max_in_degree))

        src = actor_info[source]
        dst = actor_info[target]
        distance = _haversine_km(src.lat, src.lon, dst.lat, dst.lon)
        distance_norm = _norm(distance, min_dist, max_dist)

        relation_data = None
        if data_poc is not None:
            source_keys = _actor_sheet_keys(source, actor_info[source].role)
            target_keys = _actor_sheet_keys(target, actor_info[target].role)
            for sk in source_keys:
                for tk in target_keys:
                    candidate = data_poc.relation_by_triplet.get((sk, tk, product))
                    if candidate is not None:
                        relation_data = candidate
                        break
                if relation_data is not None:
                    break

        if relation_data is not None:
            sell_price = relation_data.get("sell_price")
            price_base = relation_data.get("price_base")
        else:
            sell_price = edge.get("sell_price")
            price_base = edge.get("price_base")

        if isinstance(sell_price, (int, float)) and isinstance(price_base, (int, float)) and price_base not in (0, 0.0):
            if not (math.isnan(float(sell_price)) or math.isnan(float(price_base))):
                unit_cost = max(0.0, float(sell_price) / float(price_base))
                cost_norm = _norm(unit_cost, min_cost, max_cost)
            else:
                cost_norm = 0.5
        else:
            cost_norm = 0.5

        bom_criticality = 0.5
        if data_poc is not None and data_poc.product_bom_criticality:
            if product in data_poc.product_bom_criticality:
                bom_criticality = data_poc.product_bom_criticality[product]
            elif zone in ("manufacturer_to_distribution", "distribution_to_customer"):
                bom_criticality = 0.85
            else:
                bom_criticality = 0.2

        risk = (
            0.34 * zone_risk
            + 0.22 * scarcity
            + 0.16 * concentration
            + 0.10 * distance_norm
            + 0.08 * cost_norm
            + 0.10 * bom_criticality
        )
        raw_scores.append(risk)

        out.append(
            SupplyEdgeInfo(
                source=source,
                target=target,
                product=product,
                relation=str(edge.get("relation", "")),
                zone=zone,
                risk_score=float(risk),
                risk_display=0.0,
                material_family=_material_family(actor_info[source].description),
            )
        )
        if data_poc is not None:
            if relation_data is not None:
                data_poc.matched_relations += 1

    if len(out) == 1:
        out[0].risk_display = 1.0
    else:
        ranked = sorted(enumerate(raw_scores), key=lambda x: x[1])
        for rank, (idx, _) in enumerate(ranked):
            out[idx].risk_display = rank / float(len(out) - 1)
    return out


def _short_actor_label(actor_id: str) -> str:
    code = _extract_code(actor_id)
    if code:
        return code
    return actor_id.replace("Actor:", "")


def _role_color(role: str) -> str:
    return {
        "Supplier Distribution Center": "#4C78A8",
        "Manufacturer": "#F58518",
        "Distribution Center": "#54A24B",
        "Customer": "#E45756",
    }.get(role, "#9D9DA3")


def _zone_color(zone: str) -> str:
    return {
        "supplier_to_manufacturer": "#1F77B4",
        "manufacturing_internal": "#D62728",
        "manufacturer_to_distribution": "#FF7F0E",
        "distribution_to_customer": "#2CA02C",
        "other": "#7F7F7F",
    }.get(zone, "#7F7F7F")


def _top_edge_rows(edges: list[SupplyEdgeInfo], limit: int = 14) -> list[str]:
    ordered = sorted(
        edges,
        key=lambda e: (e.risk_score, e.zone, e.material_family, e.product, e.source, e.target),
        reverse=True,
    )
    rows: list[str] = []
    for edge in ordered[:limit]:
        s = _short_actor_label(edge.source)
        t = _short_actor_label(edge.target)
        rows.append(
            f"{s} -> {t} | product={edge.product} | type={edge.material_family} | zone={edge.zone} | risk={edge.risk_score:.2f} | display={edge.risk_display:.2f}"
        )
    return rows


def _detailed_text_report(
    report: dict,
    edges: list[SupplyEdgeInfo],
    zone_scores: dict[str, float],
    sd_reception: dict[str, float],
    data_poc: DataPocInfo | None = None,
) -> str:
    lines = []
    lines.append("Supply issue localization report")
    lines.append("")
    lines.append("DES zone risk scores (normalized):")
    lines.append(f"- supplier_to_manufacturer: {zone_scores.get('supplier_to_manufacturer', 0.0):.3f}")
    lines.append(f"- manufacturing_internal: {zone_scores.get('manufacturing_internal', 0.0):.3f}")
    lines.append(f"- manufacturer_to_distribution: {zone_scores.get('manufacturer_to_distribution', 0.0):.3f}")
    lines.append(f"- distribution_to_customer: {zone_scores.get('distribution_to_customer', 0.0):.3f}")
    lines.append("")
    lines.append("SD reception-node indicators:")
    lines.append(f"- reception_score_0_1: {sd_reception.get('score', 0.0):.3f}")
    lines.append(f"- stock_peak_gain_db: {sd_reception.get('stock_peak_gain_db', 0.0):.3f}")
    lines.append(f"- stock_distortion_ratio: {sd_reception.get('stock_distortion_ratio', 0.0):.3f}")
    lines.append(f"- backlog_peak_gain_db: {sd_reception.get('backlog_peak_gain_db', 0.0):.3f}")
    if data_poc is not None:
        lines.append("")
        lines.append("Data_poc enrichment:")
        lines.append(f"- relation_rows_loaded: {len(data_poc.relation_by_triplet)}")
        lines.append(f"- relation_rows_matched_to_graph_edges: {data_poc.matched_relations}")
        lines.append(f"- bom_products_with_criticality: {len(data_poc.product_bom_criticality)}")
    lines.append("")
    lines.append("Top localized risky links:")
    lines.extend([f"- {row}" for row in _top_edge_rows(edges)])

    issues = report.get("issues", [])
    if issues:
        lines.append("")
        lines.append("Detected issues:")
        for issue in issues:
            sev = issue.get("severity", "n/a")
            area = issue.get("area", "n/a")
            text = issue.get("issue", "")
            lines.append(f"- [{sev}] {area}: {text}")

    return "\n".join(lines)


def plot_annotated_supply_graph(
    graph_path: str | Path,
    coords_path: str | Path,
    report_path: str | Path,
    output_path: str | Path,
    output_json: str | Path | None = None,
    output_text: str | Path | None = None,
    data_poc_path: str | Path | None = "Data_poc.xlsx",
) -> dict[str, object]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    coords = json.loads(Path(coords_path).read_text(encoding="utf-8"))
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    data_poc = _load_data_poc(data_poc_path)

    actor_info = _build_actor_info(graph, coords)
    zone_scores = _zone_scores_from_report(report)
    sd_reception = _sd_reception_score(report)
    edges = _build_supply_edges(graph, actor_info, zone_scores, data_poc=data_poc)

    fig, ax_graph = plt.subplots(1, 1, figsize=(14, 9))

    edge_cmap = plt.colormaps["turbo"]
    for edge in edges:
        src = actor_info[edge.source]
        dst = actor_info[edge.target]
        display_score = min(1.0, max(0.0, edge.risk_display))
        color = edge_cmap(display_score)
        width = 0.6 + 4.2 * display_score
        alpha = 0.10 + 0.80 * display_score
        ax_graph.plot([src.lon, dst.lon], [src.lat, dst.lat], color=color, linewidth=width, alpha=alpha, zorder=1)

    roles = sorted({a.role for a in actor_info.values()})
    for role in roles:
        role_nodes = [a for a in actor_info.values() if a.role == role]
        xs = [a.lon for a in role_nodes]
        ys = [a.lat for a in role_nodes]
        ax_graph.scatter(
            xs,
            ys,
            s=70,
            color=_role_color(role),
            edgecolor="black",
            linewidth=0.5,
            alpha=0.9,
            label=role,
            zorder=2,
        )

    reception_nodes = [a for a in actor_info.values() if a.role == "Customer"]
    if reception_nodes:
        rx = [a.lon for a in reception_nodes]
        ry = [a.lat for a in reception_nodes]
        r_score = min(1.0, max(0.0, sd_reception.get("score", 0.0)))
        halo_color = plt.cm.Blues(0.35 + 0.65 * r_score)
        ax_graph.scatter(
            rx,
            ry,
            s=550,
            facecolors="none",
            edgecolors=halo_color,
            linewidths=2.8 + 2.2 * r_score,
            alpha=0.95,
            zorder=3,
        )

    for actor in actor_info.values():
        ax_graph.text(
            actor.lon,
            actor.lat,
            _short_actor_label(actor.actor_id),
            fontsize=8,
            ha="left",
            va="bottom",
            color="#202020",
            zorder=3,
        )

    sm = plt.cm.ScalarMappable(cmap=edge_cmap, norm=plt.Normalize(vmin=0.0, vmax=1.0))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax_graph, fraction=0.03, pad=0.02)
    cbar.set_label("DES link risk percentile rank (0-1)")

    sd_label = (
        "SD reception stress: "
        f"{sd_reception.get('score', 0.0):.2f} "
        f"(gain={sd_reception.get('stock_peak_gain_db', 0.0):.1f} dB)"
    )
    proxy = Line2D([0], [0], marker="o", markersize=10, color="none", markerfacecolor="none", markeredgecolor="#1f4e79", lw=0)
    handles, labels = ax_graph.get_legend_handles_labels()
    handles.append(proxy)
    labels.append(sd_label)

    ax_graph.set_title("Supply knowledge graph - risk links and SD reception marker")
    ax_graph.set_xlabel("Longitude / fallback x")
    ax_graph.set_ylabel("Latitude / fallback y")
    ax_graph.grid(alpha=0.2)
    ax_graph.legend(handles=handles, labels=labels, loc="upper left", fontsize=8, framealpha=0.9)

    fig.suptitle("Supply chain graph annotations (visual only)", y=0.99)
    plt.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)

    detailed_text = _detailed_text_report(report, edges, zone_scores, sd_reception, data_poc=data_poc)

    payload = {
        "graph_path": str(graph_path),
        "coords_path": str(coords_path),
        "report_path": str(report_path),
        "output_png": str(output_path),
        "zone_scores": zone_scores,
        "sd_reception": sd_reception,
        "data_poc_used": data_poc is not None,
        "data_poc_relation_rows": 0 if data_poc is None else len(data_poc.relation_by_triplet),
        "data_poc_relation_rows_matched": 0 if data_poc is None else data_poc.matched_relations,
        "data_poc_bom_criticality_products": 0 if data_poc is None else len(data_poc.product_bom_criticality),
        "top_localized_links": _top_edge_rows(edges),
        "detailed_report": detailed_text,
    }

    if output_json is not None:
        Path(output_json).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    if output_text is not None:
        Path(output_text).write_text(detailed_text, encoding="utf-8")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot knowledge graph and annotate localized supply issues")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json", help="Path to knowledge_graph.json")
    parser.add_argument("--coords", type=str, default="actor_coords.json", help="Path to actor_coords.json")
    parser.add_argument(
        "--report",
        type=str,
        default="advanced_complex_full_report.json",
        help="Path to advanced diagnostics report JSON",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="supply_issue_annotated.png",
        help="Output PNG path",
    )
    parser.add_argument(
        "--out-json",
        type=str,
        default="supply_issue_annotated.json",
        help="Output JSON metadata",
    )
    parser.add_argument(
        "--out-text",
        type=str,
        default="supply_issue_annotated_report.txt",
        help="Output full text report",
    )
    parser.add_argument(
        "--data-poc",
        type=str,
        default="Data_poc.xlsx",
        help="Optional Data_poc.xlsx path for enrichment",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = plot_annotated_supply_graph(
        graph_path=args.graph,
        coords_path=args.coords,
        report_path=args.report,
        output_path=args.out,
        output_json=args.out_json,
        output_text=args.out_text,
        data_poc_path=args.data_poc,
    )
    print(f"Annotated graph PNG: {payload['output_png']}")
    print(f"Zone scores: {payload['zone_scores']}")
    print(f"SD reception score: {payload['sd_reception']['score']:.3f}")
    print(f"Top links listed: {len(payload['top_localized_links'])}")


if __name__ == "__main__":
    main()
