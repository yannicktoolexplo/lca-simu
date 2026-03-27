#!/usr/bin/env python3
"""
Build an interactive HTML world map from a geocoded supply graph.

Includes two hover-panel modes:
- Simulation: current operational stock / production PNGs
- Sensitivity: low/base/high comparisons built from sensitivity case outputs
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

NODE_TYPE_STYLES = {
    "supplier_dc": {"name": "Supplier DC", "color": "#1f77b4", "symbol": "circle"},
    "factory": {"name": "Factory", "color": "#d62728", "symbol": "square"},
    "distribution_center": {"name": "Distribution Center", "color": "#ff7f0e", "symbol": "diamond"},
    "customer": {"name": "Customer", "color": "#2ca02c", "symbol": "star"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        "-i",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Input geocoded supply graph JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="etudecas/simulation/result/maps/supply_graph_poc_geocoded_map_with_factory_hover.html",
        help="Output HTML file.",
    )
    parser.add_argument(
        "--title",
        default="Supply Graph POC - Geocoded Map",
        help="HTML page title.",
    )
    parser.add_argument(
        "--sim-input-stocks-csv",
        default="etudecas/simulation/result/data/production_input_stocks_daily.csv",
        help="Simulation CSV for input material stocks.",
    )
    parser.add_argument(
        "--sim-output-products-csv",
        default="etudecas/simulation/result/data/production_output_products_daily.csv",
        help="Simulation CSV for output products production.",
    )
    parser.add_argument(
        "--sim-input-stocks-png-dir",
        default="etudecas/simulation/result/plots",
        help="Directory containing input/supplier/DC PNG files.",
    )
    parser.add_argument(
        "--sim-output-products-png-dir",
        default="etudecas/simulation/result/plots",
        help="Directory containing production_output_products_by_factory_<factory>.png files.",
    )
    parser.add_argument(
        "--sensitivity-cases-csv",
        default="etudecas/simulation/sensibility/result/sensitivity_cases.csv",
        help="Sensitivity cases summary CSV.",
    )
    parser.add_argument(
        "--supplier-shipments-csv",
        default="etudecas/simulation/result/data/production_supplier_shipments_daily.csv",
        help="Baseline supplier shipments CSV.",
    )
    parser.add_argument(
        "--supplier-stocks-csv",
        default="etudecas/simulation/result/data/production_supplier_stocks_daily.csv",
        help="Baseline supplier stocks CSV.",
    )
    parser.add_argument(
        "--supplier-capacity-csv",
        default="etudecas/simulation/result/data/production_supplier_capacity_daily.csv",
        help="Baseline supplier capacity utilization CSV.",
    )
    parser.add_argument(
        "--production-constraint-csv",
        default="etudecas/simulation/result/data/production_constraint_daily.csv",
        help="Production constraint CSV used to detect critical supplied items.",
    )
    parser.add_argument(
        "--structural-sensitivity-cases-csv",
        default="etudecas/simulation/sensibility/structural_result/sensitivity_cases.csv",
        help="Structural sensitivity cases summary CSV.",
    )
    parser.add_argument(
        "--supplier-local-criticality-csv",
        default="etudecas/simulation/result/data/supplier_local_criticality_ranking.csv",
        help="Output CSV ranking for supplier local criticality.",
    )
    parser.add_argument(
        "--supplier-local-criticality-json",
        default="etudecas/simulation/result/summaries/supplier_local_criticality_summary.json",
        help="Output JSON summary for supplier local criticality.",
    )
    parser.add_argument(
        "--realistic-sensitivity-summary-json",
        default="",
        help="Optional realistic annual sensitivity summary JSON.",
    )
    parser.add_argument(
        "--realistic-local-elasticities-csv",
        default="",
        help="Optional realistic annual local elasticities CSV.",
    )
    parser.add_argument(
        "--realistic-stress-impacts-csv",
        default="",
        help="Optional realistic annual stress impacts CSV.",
    )
    return parser.parse_args()


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def compact_graph_payload(raw: dict[str, Any]) -> dict[str, Any]:
    nodes_in = raw.get("nodes", [])
    edges_in = raw.get("edges", [])
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        raise ValueError("Expected JSON with list fields: nodes and edges.")

    nodes: list[dict[str, Any]] = []
    for node in nodes_in:
        if not isinstance(node, dict):
            continue
        geo = node.get("geo", {}) or {}
        lat = node.get("lat", geo.get("lat"))
        lon = node.get("lon", geo.get("lon"))
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            lat = None
            lon = None
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("type", "unknown"),
                "name": node.get("name", ""),
                "location_ID": node.get("location_ID"),
                "country": geo.get("country"),
                "lat": lat,
                "lon": lon,
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in edges_in:
        if not isinstance(edge, dict):
            continue
        items = edge.get("items", [])
        if not isinstance(items, list):
            items = []
        edges.append(
            {
                "id": edge.get("id"),
                "type": edge.get("type", "unknown"),
                "from": edge.get("from"),
                "to": edge.get("to"),
                "items": items,
            }
        )

    node_types = sorted({n.get("type", "unknown") for n in nodes})
    return {
        "schema_version": raw.get("schema_version"),
        "meta": raw.get("meta", {}),
        "nodes": nodes,
        "edges": edges,
        "node_types": node_types,
        "node_type_styles": NODE_TYPE_STYLES,
    }


def build_factory_hover_series(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    items = raw.get("items", []) or []

    factory_ids = {
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "factory"
    }
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}

    item_label: dict[str, str] = {}
    for it in items:
        iid = str(it.get("id"))
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        item_label[iid] = code if code else (name if name else iid)

    in_unit_by_node_item: dict[tuple[str, str], str] = {}
    out_unit_by_node_item: dict[tuple[str, str], str] = {}
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            item_id = str(st.get("item_id"))
            uom = str(st.get("uom") or "").strip()
            if item_id and uom:
                in_unit_by_node_item[(nid, item_id)] = uom
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                uom = str(inp.get("ratio_unit") or "").strip()
                if item_id and uom and (nid, item_id) not in in_unit_by_node_item:
                    in_unit_by_node_item[(nid, item_id)] = uom
            for out in (p.get("outputs") or []):
                item_id = str(out.get("item_id"))
                uom = str(out.get("uom") or "").strip()
                if item_id and uom:
                    out_unit_by_node_item[(nid, item_id)] = uom

    incoming_raw: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_input_stocks_csv.exists():
        with sim_input_stocks_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                val = to_float(row.get("stock_end_of_day"))
                if val is None:
                    val = to_float(row.get("stock_before_production")) or 0.0
                incoming_raw[node_id][item_id].append((day, val))

    outgoing_raw: dict[str, dict[str, list[tuple[int, float, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_output_products_csv.exists():
        with sim_output_products_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                prod = float(to_float(row.get("produced_qty")) or 0.0)
                cum = float(to_float(row.get("cum_produced_qty")) or 0.0)
                outgoing_raw[node_id][item_id].append((day, prod, cum))

    out: dict[str, Any] = {}
    for node_id in sorted(factory_ids):
        incoming = []
        for item_id, pts in sorted(incoming_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            incoming.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": in_unit_by_node_item.get((node_id, item_id), ""),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                }
            )

        outgoing = []
        for item_id, pts in sorted(outgoing_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            outgoing.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": out_unit_by_node_item.get((node_id, item_id), "unit/day"),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                    "cum_values": [p[2] for p in pts_sorted],
                }
            )

        if incoming or outgoing:
            out[node_id] = {
                "node_id": node_id,
                "node_name": node_name.get(node_id, node_id),
                "incoming": incoming,
                "outgoing": outgoing,
            }

    return out


def png_payload_from_bytes(png_bytes: bytes, filename: str) -> dict[str, Any]:
    return {
        "mime": "image/png",
        "data_b64": base64.b64encode(png_bytes).decode("ascii"),
        "filename": filename,
    }


def load_png_payload(png_path: Path) -> dict[str, Any] | None:
    if not png_path.exists():
        return None
    try:
        return png_payload_from_bytes(png_path.read_bytes(), png_path.name)
    except Exception:
        return None


def resolve_plot_payload(base_dir: Path, relative_path: Path, legacy_name: str) -> dict[str, Any] | None:
    candidates = [
        base_dir / relative_path,
        base_dir / legacy_name,
    ]
    for candidate in candidates:
        payload = load_png_payload(candidate)
        if payload is not None:
            return payload
    return None


def build_factory_hover_images(
    raw: dict[str, Any],
    input_png_dir: Path,
    output_png_dir: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    factory_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "factory"
    )
    out: dict[str, Any] = {}
    for factory_id in factory_ids:
        safe_factory = re.sub(r"[^A-Za-z0-9_-]+", "_", factory_id)
        incoming = resolve_plot_payload(
            input_png_dir,
            Path("factories") / "input_stocks" / f"production_input_stocks_by_material_{safe_factory}.png",
            f"production_input_stocks_by_material_{safe_factory}.png",
        )
        outgoing = resolve_plot_payload(
            output_png_dir,
            Path("factories") / "output_products" / f"production_output_products_by_factory_{safe_factory}.png",
            f"production_output_products_by_factory_{safe_factory}.png",
        )
        if outgoing is None:
            outgoing = resolve_plot_payload(
                output_png_dir,
                Path("factories") / "output_products" / "production_output_products.png",
                "production_output_products.png",
            )
        if not incoming and not outgoing:
            continue
        out[factory_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_hover_images(raw: dict[str, Any], png_dir: Path) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    supplier_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "supplier_dc"
    )
    out: dict[str, Any] = {}
    for supplier_id in supplier_ids:
        safe_supplier = re.sub(r"[^A-Za-z0-9_-]+", "_", supplier_id)
        incoming = resolve_plot_payload(
            png_dir,
            Path("suppliers") / "input_stocks" / f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
            f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
        )
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_stocks_by_material_{safe_supplier}.png")
        outgoing = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        if incoming or outgoing:
            out[supplier_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_hover_images(raw: dict[str, Any], png_dir: Path) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    dc_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "distribution_center"
    )
    out: dict[str, Any] = {}
    for dc_id in dc_ids:
        safe_dc = re.sub(r"[^A-Za-z0-9_-]+", "_", dc_id)
        incoming = resolve_plot_payload(
            png_dir,
            Path("distribution_centers") / "factory_outputs" / f"production_dc_factory_outputs_by_material_{safe_dc}.png",
            f"production_dc_factory_outputs_by_material_{safe_dc}.png",
        )
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_dc_shipments_by_material_{safe_dc}.png")
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_dc_stocks_by_material_{safe_dc}.png")
        if incoming:
            out[dc_id] = {"incoming": incoming, "outgoing": None}
    return out


def read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        nested_data_path = csv_path.parent / "data" / csv_path.name
        if nested_data_path.exists():
            csv_path = nested_data_path
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_edge_item_sets(raw: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incoming_items: dict[str, set[str]] = defaultdict(set)
    outgoing_items: dict[str, set[str]] = defaultdict(set)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        for item_id in edge.get("items") or []:
            item = str(item_id)
            if src:
                outgoing_items[src].add(item)
            if dst:
                incoming_items[dst].add(item)
    return incoming_items, outgoing_items


def aggregate_daily_series(
    rows: list[dict[str, str]],
    *,
    value_field: str,
    node_field: str | None = None,
    node_id: str | None = None,
    item_ids: set[str] | None = None,
) -> list[tuple[int, float]]:
    by_day: dict[int, float] = defaultdict(float)
    for row in rows:
        if node_field and node_id is not None and str(row.get(node_field) or "") != node_id:
            continue
        item_id = str(row.get("item_id") or "")
        if item_ids is not None and item_id not in item_ids:
            continue
        day = int(to_float(row.get("day")) or 0)
        value = float(to_float(row.get(value_field)) or 0.0)
        by_day[day] += value
    return sorted(by_day.items(), key=lambda it: it[0])


def build_line_chart_payload(
    series_map: dict[str, list[tuple[int, float]]],
    *,
    title: str,
    y_label: str,
    filename: str,
) -> dict[str, Any] | None:
    usable = {label: pts for label, pts in series_map.items() if pts}
    if not usable:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    colors = ["#0f766e", "#2563eb", "#dc2626", "#d97706", "#7c3aed", "#475569"]
    fig, ax = plt.subplots(figsize=(9.8, 4.8))
    for idx, (label, points) in enumerate(usable.items()):
        days = [p[0] for p in points]
        values = [p[1] for p in points]
        ax.plot(
            days,
            values,
            label=label,
            linewidth=2.1,
            color=colors[idx % len(colors)],
        )

    ax.set_title(title, fontsize=12, pad=10)
    ax.set_xlabel("Jour")
    ax.set_ylabel(y_label)
    ax.grid(True, which="major", color="#e2e8f0", linewidth=0.9)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    ax.legend(loc="best", fontsize=8.5, frameon=False)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def case_rows_by_id(case_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {
        str(row.get("case_id") or ""): row
        for row in case_rows
        if str(row.get("status") or "").lower() == "ok"
    }


def first_case_row(
    by_case_id: dict[str, dict[str, str]],
    *case_ids: str,
) -> dict[str, str] | None:
    for case_id in case_ids:
        row = by_case_id.get(case_id)
        if row is not None:
            return row
    return None


def baseline_sensitivity_row(by_case_id: dict[str, dict[str, str]]) -> dict[str, str] | None:
    return first_case_row(
        by_case_id,
        "baseline",
        "baseline_baseline_base",
    )


def case_multiplier_value(case_row: dict[str, str] | None) -> float | None:
    if not case_row:
        return None
    return to_float(case_row.get("value")) or to_float(case_row.get("factor_value"))


def case_output_dir(case_row: dict[str, str] | None) -> Path | None:
    if not case_row:
        return None
    raw = str(case_row.get("case_output_dir") or "").strip()
    return Path(raw) if raw else None


def safe_case_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def kpi_from_case(case_row: dict[str, str] | None, kpi_name: str) -> float | None:
    if not case_row:
        return None
    value = to_float(case_row.get(f"kpi::{kpi_name}"))
    if value is None or math.isnan(value):
        return None
    return value


def build_bar_chart_payload(
    value_map: dict[str, float | None],
    *,
    title: str,
    y_label: str,
    filename: str,
) -> dict[str, Any] | None:
    usable = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    if not usable:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    labels = [label for label, _ in usable]
    values = [float(value) for _, value in usable]
    colors = []
    for label in labels:
        if label == "Base":
            colors.append("#2563eb")
        elif "-" in label:
            colors.append("#d97706")
        else:
            colors.append("#0f766e")

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    bars = ax.bar(labels, values, color=colors, width=0.62)
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_ylabel(y_label)
    ax.grid(True, axis="y", color="#e2e8f0", linewidth=0.9)
    ax.set_axisbelow(True)
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")
    ax.tick_params(axis="x", labelrotation=18)

    ymax = max(values) if values else 0.0
    ymin = min(values) if values else 0.0
    span = max(abs(ymax - ymin), abs(ymax), 1.0)
    pad = span * 0.08
    ax.set_ylim(ymin - pad, ymax + pad)
    for bar, value in zip(bars, values):
        label = f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + (pad * 0.15 if value >= 0 else -pad * 0.4),
            label,
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=8.5,
            color="#0f172a",
        )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def multiplier_label(value: float | None, fallback: str) -> str:
    if value is None:
        return fallback
    if abs(value - 1.0) <= 1e-9:
        return "Base"
    return f"x{value:.2f}"


def align_series(
    baseline_points: list[tuple[int, float]],
    scenario_points: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    base_map = {day: value for day, value in baseline_points}
    scen_map = {day: value for day, value in scenario_points}
    days = sorted(set(base_map) | set(scen_map))
    return [(day, scen_map.get(day, 0.0) - base_map.get(day, 0.0)) for day in days]


def build_combo_bar_line_payload(
    value_map: dict[str, float | None],
    delta_series_map: dict[str, list[tuple[int, float]]],
    *,
    bar_title: str,
    bar_y_label: str,
    line_title: str,
    line_y_label: str,
    filename: str,
    note: str | None = None,
) -> dict[str, Any] | None:
    usable_bars = [(label, value) for label, value in value_map.items() if value is not None and not math.isnan(value)]
    usable_lines = {label: pts for label, pts in delta_series_map.items() if pts}
    if not usable_bars and not usable_lines:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(9.2, 7.2), gridspec_kw={"height_ratios": [1.0, 1.15]})
    fig.patch.set_facecolor("#ffffff")
    colors = ["#d97706", "#0f766e", "#dc2626", "#7c3aed", "#475569"]

    ax_bar = axes[0]
    if usable_bars:
        labels = [label for label, _ in usable_bars]
        values = [float(value) for _, value in usable_bars]
        bar_colors = []
        for label in labels:
            if label == "Base":
                bar_colors.append("#2563eb")
            elif any(token in label for token in ["x0.", "x0,", "-"]):
                bar_colors.append("#d97706")
            else:
                bar_colors.append("#0f766e")
        bars = ax_bar.bar(labels, values, color=bar_colors, width=0.62)
        ymax = max(values) if values else 0.0
        ymin = min(values) if values else 0.0
        span = max(abs(ymax - ymin), abs(ymax), 1.0)
        pad = span * 0.10
        ax_bar.set_ylim(ymin - pad, ymax + pad)
        for bar, value in zip(bars, values):
            label = f"{value:.3f}" if abs(value) < 10 else f"{value:.1f}"
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                value + (pad * 0.10 if value >= 0 else -pad * 0.35),
                label,
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=8.3,
                color="#0f172a",
            )
        ax_bar.set_ylabel(bar_y_label)
        ax_bar.tick_params(axis="x", labelrotation=18)
        ax_bar.grid(True, axis="y", color="#e2e8f0", linewidth=0.9)
        ax_bar.set_axisbelow(True)
    else:
        ax_bar.axis("off")
    ax_bar.set_title(bar_title, fontsize=12, pad=10)
    ax_bar.set_facecolor("#ffffff")

    ax_line = axes[1]
    if usable_lines:
        for idx, (label, points) in enumerate(usable_lines.items()):
            days = [p[0] for p in points]
            values = [p[1] for p in points]
            ax_line.plot(
                days,
                values,
                label=label,
                linewidth=2.1,
                color=colors[idx % len(colors)],
            )
        ax_line.axhline(0.0, color="#94a3b8", linewidth=1.0, linestyle="--")
        ax_line.set_xlabel("Jour")
        ax_line.set_ylabel(line_y_label)
        ax_line.grid(True, which="major", color="#e2e8f0", linewidth=0.9)
        ax_line.legend(loc="best", fontsize=8.2, frameon=False)
    else:
        ax_line.axis("off")
    ax_line.set_title(line_title, fontsize=11, pad=8)
    ax_line.set_facecolor("#ffffff")

    if note:
        fig.text(0.5, 0.012, note, ha="center", va="bottom", fontsize=9.5, color="#475569")

    fig.tight_layout(rect=(0, 0.03 if note else 0, 1, 1))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def build_note_payload(title: str, message: str, filename: str) -> dict[str, Any] | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")
    ax.axis("off")
    ax.text(0.5, 0.68, title, ha="center", va="center", fontsize=13, fontweight="bold", color="#0f172a")
    ax.text(0.5, 0.38, message, ha="center", va="center", fontsize=11, color="#475569")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return png_payload_from_bytes(buf.getvalue(), filename)


def local_signal_strength(
    baseline_row: dict[str, str] | None,
    low_row: dict[str, str] | None,
    high_row: dict[str, str] | None,
) -> tuple[float, float]:
    base_fill = kpi_from_case(baseline_row, "fill_rate") or 0.0
    base_backlog = kpi_from_case(baseline_row, "ending_backlog") or 0.0
    fill_impact = max(
        abs((kpi_from_case(low_row, "fill_rate") or base_fill) - base_fill),
        abs((kpi_from_case(high_row, "fill_rate") or base_fill) - base_fill),
    )
    backlog_impact = max(
        abs((kpi_from_case(low_row, "ending_backlog") or base_backlog) - base_backlog),
        abs((kpi_from_case(high_row, "ending_backlog") or base_backlog) - base_backlog),
    )
    return fill_impact, backlog_impact


def cumulative_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    total = 0.0
    out: list[tuple[int, float]] = []
    for day, value in points:
        total += value
        out.append((day, total))
    return out


def select_best_supplier_case_pair(
    by_case_id: dict[str, dict[str, str]],
    baseline_row: dict[str, str] | None,
    node_id: str,
) -> tuple[str, str, dict[str, str] | None, dict[str, str] | None, float, float]:
    safe_node = safe_case_token(node_id)
    candidates: list[tuple[str, str, dict[str, str] | None, dict[str, str] | None]] = [
        (
            "stock fournisseur local",
            "Stock four.",
            first_case_row(by_case_id, f"supplier_stock_node_{safe_node}_low", f"local_supplier_stock_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_stock_node_{safe_node}_high", f"local_supplier_stock_node_{safe_node}_high"),
        ),
        (
            "lead time sortant local",
            "Lead time",
            first_case_row(by_case_id, f"supplier_lead_time_node_{safe_node}_low", f"local_supplier_lead_time_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_lead_time_node_{safe_node}_high", f"local_supplier_lead_time_node_{safe_node}_high"),
        ),
        (
            "fiabilite locale",
            "OTIF",
            first_case_row(
                by_case_id,
                f"supplier_reliability_node_{safe_node}_low",
                f"local_supplier_reliability_node_{safe_node}_low",
                f"local_supplier_reliability_node_{safe_node}_adverse",
            ),
            first_case_row(by_case_id, f"supplier_reliability_node_{safe_node}_high", f"local_supplier_reliability_node_{safe_node}_high"),
        ),
        (
            "capacite fournisseur locale",
            "Cap. four.",
            first_case_row(by_case_id, f"supplier_capacity_node_{safe_node}_low", f"local_supplier_capacity_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_capacity_node_{safe_node}_high", f"local_supplier_capacity_node_{safe_node}_high"),
        ),
        (
            "capacite process locale",
            "Cap. proc.",
            first_case_row(by_case_id, f"capacity_{safe_node}_low", f"local_capacity_node_{safe_node}_low"),
            first_case_row(by_case_id, f"capacity_{safe_node}_high", f"local_capacity_node_{safe_node}_high"),
        ),
    ]
    best_label = ""
    best_short = ""
    best_low: dict[str, str] | None = None
    best_high: dict[str, str] | None = None
    best_score = -1.0
    best_fill_impact = 0.0
    best_backlog_impact = 0.0
    for label, short_label, low_row, high_row in candidates:
        if low_row is None and high_row is None:
            continue
        fill_impact, backlog_impact = local_signal_strength(baseline_row, low_row, high_row)
        score = fill_impact * 100.0 + backlog_impact / 25.0
        if score > best_score:
            best_label = label
            best_short = short_label
            best_low = low_row
            best_high = high_row
            best_score = score
            best_fill_impact = fill_impact
            best_backlog_impact = backlog_impact
    return best_label, best_short, best_low, best_high, best_fill_impact, best_backlog_impact


def build_factory_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory":
            continue

        safe_node = safe_case_token(node_id)
        low_row = first_case_row(by_case_id, f"capacity_{safe_node}_low", f"local_capacity_node_{safe_node}_low")
        high_row = first_case_row(by_case_id, f"capacity_{safe_node}_high", f"local_capacity_node_{safe_node}_high")
        if low_row is None and high_row is None:
            continue
        low_label = multiplier_label(case_multiplier_value(low_row), "Low")
        high_label = multiplier_label(case_multiplier_value(high_row), "High")
        low_dir = case_output_dir(low_row)
        high_dir = case_output_dir(high_row)

        base_input_csv = baseline_dir / "production_input_stocks_daily.csv"
        base_output_csv = baseline_dir / "production_output_products_daily.csv"
        if base_input_csv not in csv_cache:
            csv_cache[base_input_csv] = read_csv_rows(base_input_csv)
        if base_output_csv not in csv_cache:
            csv_cache[base_output_csv] = read_csv_rows(base_output_csv)
        base_input_series = aggregate_daily_series(
            csv_cache[base_input_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        base_output_series = aggregate_daily_series(
            csv_cache[base_output_csv],
            value_field="cum_produced_qty",
            node_field="node_id",
            node_id=node_id,
        )
        input_deltas: dict[str, list[tuple[int, float]]] = {}
        output_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            input_csv = root / "production_input_stocks_daily.csv"
            output_csv = root / "production_output_products_daily.csv"
            if input_csv not in csv_cache:
                csv_cache[input_csv] = read_csv_rows(input_csv)
            if output_csv not in csv_cache:
                csv_cache[output_csv] = read_csv_rows(output_csv)
            input_deltas[label] = align_series(
                base_input_series,
                aggregate_daily_series(
                    csv_cache[input_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
            output_deltas[label] = align_series(
                base_output_series,
                aggregate_daily_series(
                    csv_cache[output_csv],
                    value_field="cum_produced_qty",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(high_row, "fill_rate"),
            },
            input_deltas,
            bar_title=f"{node_id} - impact capacite sur fill rate systeme",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - ecart de stock intrants vs baseline",
            line_y_label="Delta stock total",
            filename=f"{node_id}_sensitivity_fill_rate.png",
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(high_row, "ending_backlog"),
            },
            output_deltas,
            bar_title=f"{node_id} - impact capacite sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de production cumulee vs baseline",
            line_y_label="Delta production cumulee",
            filename=f"{node_id}_sensitivity_backlog.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "supplier_dc":
            continue

        best_label, best_short, best_low, best_high, best_fill_impact, best_backlog_impact = (
            select_best_supplier_case_pair(by_case_id, baseline_row, node_id)
        )
        if best_low is None and best_high is None:
            continue
        low_label = multiplier_label(case_multiplier_value(best_low), "Low")
        high_label = multiplier_label(case_multiplier_value(best_high), "High")
        low_dir = case_output_dir(best_low)
        high_dir = case_output_dir(best_high)
        base_ship_csv = baseline_dir / "production_supplier_shipments_daily.csv"
        base_stock_csv = baseline_dir / "production_supplier_stocks_daily.csv"
        if base_ship_csv not in csv_cache:
            csv_cache[base_ship_csv] = read_csv_rows(base_ship_csv)
        if base_stock_csv not in csv_cache:
            csv_cache[base_stock_csv] = read_csv_rows(base_stock_csv)
        base_ship_series = aggregate_daily_series(
            csv_cache[base_ship_csv],
            value_field="shipped_qty",
            node_field="src_node_id",
            node_id=node_id,
        )
        base_stock_series = aggregate_daily_series(
            csv_cache[base_stock_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        ship_deltas: dict[str, list[tuple[int, float]]] = {}
        stock_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            ship_csv = root / "production_supplier_shipments_daily.csv"
            stock_csv = root / "production_supplier_stocks_daily.csv"
            if ship_csv not in csv_cache:
                csv_cache[ship_csv] = read_csv_rows(ship_csv)
            if stock_csv not in csv_cache:
                csv_cache[stock_csv] = read_csv_rows(stock_csv)
            ship_deltas[label] = align_series(
                base_ship_series,
                aggregate_daily_series(
                    csv_cache[ship_csv],
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=node_id,
                ),
            )
            stock_deltas[label] = align_series(
                base_stock_series,
                aggregate_daily_series(
                    csv_cache[stock_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
        note = None
        if best_fill_impact < 0.002 and best_backlog_impact < 5.0:
            note = "Impact faible: le nœud bouge peu sur le système malgré un choc local fort."

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(best_high, "fill_rate"),
            },
            ship_deltas,
            bar_title=f"{node_id} - impact {best_label} sur fill rate systeme",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - ecart d'expeditions vs baseline",
            line_y_label="Delta expeditions / jour",
            filename=f"{node_id}_sensitivity_fill_rate.png",
            note=note,
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(best_high, "ending_backlog"),
            },
            stock_deltas,
            bar_title=f"{node_id} - impact {best_label} sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de stock disponible vs baseline",
            line_y_label="Delta stock fin de journee",
            filename=f"{node_id}_sensitivity_backlog.png",
            note=note,
        )
        out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "distribution_center":
            continue

        dc_item_ids = set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
        base_demand_csv = baseline_dir / "production_demand_service_daily.csv"
        if base_demand_csv not in csv_cache:
            csv_cache[base_demand_csv] = read_csv_rows(base_demand_csv)
        fill_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "fill_rate")}
        backlog_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "ending_backlog")}
        backlog_deltas: dict[str, list[tuple[int, float]]] = {}
        served_deltas: dict[str, list[tuple[int, float]]] = {}
        for item_id in sorted(dc_item_ids):
            code = item_id.split(":", 1)[-1]
            base_backlog_series = aggregate_daily_series(
                csv_cache[base_demand_csv],
                value_field="backlog_end_qty",
                item_ids={item_id},
            )
            base_served_series = cumulative_series(
                aggregate_daily_series(
                    csv_cache[base_demand_csv],
                    value_field="served_qty",
                    item_ids={item_id},
                )
            )
            low_row = first_case_row(by_case_id, f"demand_item_{code}_low", f"local_demand_item_item_{code}_low")
            high_row = first_case_row(by_case_id, f"demand_item_{code}_high", f"local_demand_item_item_{code}_high")
            low_label = multiplier_label(case_multiplier_value(low_row), f"{code} low")
            high_label = multiplier_label(case_multiplier_value(high_row), f"{code} high")
            fill_values[f"{code} {low_label}"] = kpi_from_case(low_row, "fill_rate")
            fill_values[f"{code} {high_label}"] = kpi_from_case(high_row, "fill_rate")
            backlog_values[f"{code} {low_label}"] = kpi_from_case(low_row, "ending_backlog")
            backlog_values[f"{code} {high_label}"] = kpi_from_case(high_row, "ending_backlog")
            for label, row in ((f"{code} {low_label}", low_row), (f"{code} {high_label}", high_row)):
                root = case_output_dir(row)
                if root is None:
                    continue
                demand_csv = root / "production_demand_service_daily.csv"
                if demand_csv not in csv_cache:
                    csv_cache[demand_csv] = read_csv_rows(demand_csv)
                backlog_deltas[label] = align_series(
                    base_backlog_series,
                    aggregate_daily_series(
                        csv_cache[demand_csv],
                        value_field="backlog_end_qty",
                        item_ids={item_id},
                    ),
                )
                served_deltas[label] = align_series(
                    base_served_series,
                    cumulative_series(
                        aggregate_daily_series(
                            csv_cache[demand_csv],
                            value_field="served_qty",
                            item_ids={item_id},
                        )
                    ),
                )

        incoming = build_combo_bar_line_payload(
            fill_values,
            backlog_deltas,
            bar_title=f"{node_id} - impact demande sur fill rate systeme",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - ecart de backlog client vs baseline",
            line_y_label="Delta backlog",
            filename=f"{node_id}_sensitivity_fill_rate.png",
        )
        outgoing = build_combo_bar_line_payload(
            backlog_values,
            served_deltas,
            bar_title=f"{node_id} - impact demande sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de servi cumule vs baseline",
            line_y_label="Delta servi cumule",
            filename=f"{node_id}_sensitivity_backlog.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_sensitivity_hover_payloads(
    raw: dict[str, Any],
    sensitivity_cases_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case_rows = read_csv_rows(sensitivity_cases_csv)
    if not case_rows:
        return {}, {}, {}

    csv_cache: dict[Path, list[dict[str, str]]] = {}
    return (
        build_factory_sensitivity_hover_images(raw, case_rows, csv_cache),
        build_supplier_sensitivity_hover_images(raw, case_rows, csv_cache),
        build_distribution_center_sensitivity_hover_images(raw, case_rows, csv_cache),
    )


def build_factory_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(by_case_id.get("baseline"))
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory":
            continue
        safe_node = safe_case_token(node_id)
        low_dir = case_output_dir(by_case_id.get(f"capacity_{safe_node}_low"))
        high_dir = case_output_dir(by_case_id.get(f"capacity_{safe_node}_high"))
        low_row = by_case_id.get(f"capacity_{safe_node}_low")
        high_row = by_case_id.get(f"capacity_{safe_node}_high")
        if low_dir is None and high_dir is None:
            continue

        low_label = multiplier_label(to_float(low_row.get("value")) if low_row else None, "Low")
        high_label = multiplier_label(to_float(high_row.get("value")) if high_row else None, "High")
        base_input_csv = baseline_dir / "production_input_stocks_daily.csv"
        base_output_csv = baseline_dir / "production_output_products_daily.csv"
        if base_input_csv not in csv_cache:
            csv_cache[base_input_csv] = read_csv_rows(base_input_csv)
        if base_output_csv not in csv_cache:
            csv_cache[base_output_csv] = read_csv_rows(base_output_csv)
        base_input_series = aggregate_daily_series(
            csv_cache[base_input_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        base_output_series = aggregate_daily_series(
            csv_cache[base_output_csv],
            value_field="cum_produced_qty",
            node_field="node_id",
            node_id=node_id,
        )
        input_deltas: dict[str, list[tuple[int, float]]] = {}
        output_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            input_csv = root / "production_input_stocks_daily.csv"
            output_csv = root / "production_output_products_daily.csv"
            if input_csv not in csv_cache:
                csv_cache[input_csv] = read_csv_rows(input_csv)
            if output_csv not in csv_cache:
                csv_cache[output_csv] = read_csv_rows(output_csv)
            input_deltas[label] = align_series(
                base_input_series,
                aggregate_daily_series(
                    csv_cache[input_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
            output_deltas[label] = align_series(
                base_output_series,
                aggregate_daily_series(
                    csv_cache[output_csv],
                    value_field="cum_produced_qty",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(high_row, "fill_rate"),
            },
            input_deltas,
            bar_title=f"{node_id} - structurel: impact capacite sur fill rate",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - structurel: ecart de stock intrants vs baseline",
            line_y_label="Delta stock total",
            filename=f"{node_id}_structural_input.png",
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(high_row, "ending_backlog"),
            },
            output_deltas,
            bar_title=f"{node_id} - structurel: impact capacite sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de production cumulee vs baseline",
            line_y_label="Delta production cumulee",
            filename=f"{node_id}_structural_output.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(baseline_row)
    if baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "supplier_dc":
            continue

        best_label, best_short, best_low_row, best_high_row, best_fill_impact, best_backlog_impact = (
            select_best_supplier_case_pair(by_case_id, baseline_row, node_id)
        )
        if best_low_row is None and best_high_row is None:
            continue

        low_dir = case_output_dir(best_low_row)
        high_dir = case_output_dir(best_high_row)
        low_label = multiplier_label(to_float(best_low_row.get("value")) if best_low_row else None, "Low")
        high_label = multiplier_label(to_float(best_high_row.get("value")) if best_high_row else None, "High")
        base_ship_csv = baseline_dir / "production_supplier_shipments_daily.csv"
        base_stock_csv = baseline_dir / "production_supplier_stocks_daily.csv"
        if base_ship_csv not in csv_cache:
            csv_cache[base_ship_csv] = read_csv_rows(base_ship_csv)
        if base_stock_csv not in csv_cache:
            csv_cache[base_stock_csv] = read_csv_rows(base_stock_csv)
        base_ship_series = aggregate_daily_series(
            csv_cache[base_ship_csv],
            value_field="shipped_qty",
            node_field="src_node_id",
            node_id=node_id,
        )
        base_stock_series = aggregate_daily_series(
            csv_cache[base_stock_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        ship_deltas: dict[str, list[tuple[int, float]]] = {}
        stock_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            shipments_csv = root / "production_supplier_shipments_daily.csv"
            stocks_csv = root / "production_supplier_stocks_daily.csv"
            if shipments_csv not in csv_cache:
                csv_cache[shipments_csv] = read_csv_rows(shipments_csv)
            if stocks_csv not in csv_cache:
                csv_cache[stocks_csv] = read_csv_rows(stocks_csv)
            ship_deltas[label] = align_series(
                base_ship_series,
                aggregate_daily_series(
                    csv_cache[shipments_csv],
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=node_id,
                ),
            )
            stock_deltas[label] = align_series(
                base_stock_series,
                aggregate_daily_series(
                    csv_cache[stocks_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        note = None
        if best_fill_impact < 0.002 and best_backlog_impact < 5.0:
            note = "Impact faible mais courbes affichees pour comparaison structurelle."

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(best_high_row, "fill_rate"),
            },
            ship_deltas,
            bar_title=f"{node_id} - structurel: impact {best_label} sur fill rate",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - structurel: ecart d'expeditions vs baseline",
            line_y_label="Delta expeditions / jour",
            filename=f"{node_id}_structural_shipments.png",
            note=note,
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(best_high_row, "ending_backlog"),
            },
            stock_deltas,
            bar_title=f"{node_id} - structurel: impact {best_label} sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de stock disponible vs baseline",
            line_y_label="Delta stock fin de journee",
            filename=f"{node_id}_structural_stock.png",
            note=note,
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(by_case_id.get("baseline"))
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "distribution_center":
            continue

        dc_item_ids = set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
        base_demand_csv = baseline_dir / "production_demand_service_daily.csv"
        if base_demand_csv not in csv_cache:
            csv_cache[base_demand_csv] = read_csv_rows(base_demand_csv)
        fill_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "fill_rate")}
        backlog_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "ending_backlog")}
        backlog_deltas: dict[str, list[tuple[int, float]]] = {}
        served_deltas: dict[str, list[tuple[int, float]]] = {}
        for item_id in sorted(dc_item_ids):
            code = item_id.split(":", 1)[-1]
            base_backlog_series = aggregate_daily_series(
                csv_cache[base_demand_csv],
                value_field="backlog_end_qty",
                item_ids={item_id},
            )
            base_served_series = cumulative_series(
                aggregate_daily_series(
                    csv_cache[base_demand_csv],
                    value_field="served_qty",
                    item_ids={item_id},
                )
            )
            low_row = by_case_id.get(f"demand_item_{code}_low")
            high_row = by_case_id.get(f"demand_item_{code}_high")
            low_label = multiplier_label(to_float(low_row.get("value")) if low_row else None, f"{code} low")
            high_label = multiplier_label(to_float(high_row.get("value")) if high_row else None, f"{code} high")
            fill_values[f"{code} {low_label}"] = kpi_from_case(low_row, "fill_rate")
            fill_values[f"{code} {high_label}"] = kpi_from_case(high_row, "fill_rate")
            backlog_values[f"{code} {low_label}"] = kpi_from_case(low_row, "ending_backlog")
            backlog_values[f"{code} {high_label}"] = kpi_from_case(high_row, "ending_backlog")
            for label, row in ((f"{code} {low_label}", low_row), (f"{code} {high_label}", high_row)):
                root = case_output_dir(row)
                if root is None:
                    continue
                demand_csv = root / "production_demand_service_daily.csv"
                if demand_csv not in csv_cache:
                    csv_cache[demand_csv] = read_csv_rows(demand_csv)
                backlog_deltas[label] = align_series(
                    base_backlog_series,
                    aggregate_daily_series(
                        csv_cache[demand_csv],
                        value_field="backlog_end_qty",
                        item_ids={item_id},
                    ),
                )
                served_deltas[label] = align_series(
                    base_served_series,
                    cumulative_series(
                        aggregate_daily_series(
                            csv_cache[demand_csv],
                            value_field="served_qty",
                            item_ids={item_id},
                        )
                    ),
                )

        incoming = build_combo_bar_line_payload(
            fill_values,
            backlog_deltas,
            bar_title=f"{node_id} - structurel: impact demande sur fill rate",
            bar_y_label="Fill rate",
            line_title=f"{node_id} - structurel: ecart de backlog client vs baseline",
            line_y_label="Delta backlog",
            filename=f"{node_id}_structural_backlog.png",
        )
        outgoing = build_combo_bar_line_payload(
            backlog_values,
            served_deltas,
            bar_title=f"{node_id} - structurel: impact demande sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de servi cumule vs baseline",
            line_y_label="Delta servi cumule",
            filename=f"{node_id}_structural_served.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_structural_sensitivity_hover_payloads(
    raw: dict[str, Any],
    structural_cases_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case_rows = read_csv_rows(structural_cases_csv)
    if not case_rows:
        return {}, {}, {}

    csv_cache: dict[Path, list[dict[str, str]]] = {}
    return (
        build_factory_structural_hover_images(raw, case_rows, csv_cache),
        build_supplier_structural_hover_images(raw, case_rows, csv_cache),
        build_distribution_center_structural_hover_images(raw, case_rows, csv_cache),
    )


def metric_label_value(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def build_realistic_sensitivity_panel_metrics(
    raw: dict[str, Any],
    summary_json: Path,
    local_elasticities_csv: Path,
    stress_impacts_csv: Path,
) -> dict[str, Any]:
    local_rows = read_csv_rows(local_elasticities_csv)
    stress_rows = read_csv_rows(stress_impacts_csv)
    if not local_rows and not stress_rows and not summary_json.exists():
        return {"nodes": {}, "global": {}}

    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.exists() else {}
    except Exception:
        summary = {}

    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    node_item_ids: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        node_item_ids[node_id].update(incoming_items.get(node_id, set()))
        node_item_ids[node_id].update(outgoing_items.get(node_id, set()))
        inventory = node.get("inventory") or {}
        for state in (inventory.get("states") or []):
            item_id = str((state or {}).get("item_id") or "")
            if item_id:
                node_item_ids[node_id].add(item_id)
        for process in (node.get("processes") or []):
            for inp in (process.get("inputs") or []):
                item_id = str((inp or {}).get("item_id") or "")
                if item_id:
                    node_item_ids[node_id].add(item_id)
            for out in (process.get("outputs") or []):
                item_id = str((out or {}).get("item_id") or "")
                if item_id:
                    node_item_ids[node_id].add(item_id)

    def is_global_parameter(parameter_key: str) -> bool:
        return "::" not in parameter_key

    def row_scope(parameter_key: str, node_id: str) -> str | None:
        if parameter_key.endswith(f"::{node_id}"):
            return "direct"
        if parameter_key.startswith("demand_item::") and parameter_key.split("::", 1)[1] in node_item_ids.get(node_id, set()):
            return "item"
        return None

    def safe_abs(value: Any) -> float:
        num = to_float(value)
        if num is None or math.isnan(num):
            return 0.0
        return abs(num)

    def choose_local_global(kpi: str) -> dict[str, str] | None:
        candidates = [
            row
            for row in local_rows
            if str(row.get("kpi") or "") == kpi and is_global_parameter(str(row.get("parameter_key") or ""))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: safe_abs(row.get("abs_elasticity")))

    def choose_stress_global(kpi: str) -> dict[str, str] | None:
        delta_field = f"delta::{kpi}"
        candidates = [
            row
            for row in stress_rows
            if is_global_parameter(str(row.get("parameter_key") or ""))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: safe_abs(row.get(delta_field)))

    def choose_node_local(node_id: str, kpi: str) -> dict[str, str] | None:
        candidates = []
        for row in local_rows:
            if str(row.get("kpi") or "") != kpi:
                continue
            scope = row_scope(str(row.get("parameter_key") or ""), node_id)
            if not scope:
                continue
            candidates.append((0 if scope == "direct" else 1, safe_abs(row.get("abs_elasticity")), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], -item[1]))
        return candidates[0][2]

    def choose_node_stress(node_id: str, kpi: str) -> dict[str, str] | None:
        delta_field = f"delta::{kpi}"
        candidates = []
        for row in stress_rows:
            scope = row_scope(str(row.get("parameter_key") or ""), node_id)
            if not scope:
                continue
            candidates.append((0 if scope == "direct" else 1, safe_abs(row.get(delta_field)), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], -item[1]))
        return candidates[0][2]

    baseline = summary.get("baseline", {}) if isinstance(summary, dict) else {}
    baseline_fill = to_float((baseline or {}).get("fill_rate"))
    baseline_backlog = to_float((baseline or {}).get("ending_backlog"))
    baseline_cost = to_float((baseline or {}).get("total_cost"))

    def fmt_fill(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.1f}%"

    def fmt_backlog(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:,.0f}".replace(",", " ")

    def fmt_money(value: float | None) -> str:
        if value is None:
            return "n/a"
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f} k"
        return f"{value:.0f}"

    def describe_local(row: dict[str, str] | None, *, kpi: str) -> str:
        if not row:
            return "n/a"
        label = str(row.get("parameter_label") or row.get("parameter_key") or "").strip()
        elasticity = to_float(row.get("abs_elasticity"))
        if elasticity is None or math.isnan(elasticity):
            return label or "n/a"
        suffix = ""
        if str(row.get("parameter_key") or "").startswith("demand_item::"):
            suffix = " (via produit)"
        return f"{label}{suffix} | e={elasticity:.3f}"

    def describe_stress(row: dict[str, str] | None, *, kpi: str) -> str:
        if not row:
            return "n/a"
        label = str(row.get("parameter_label") or row.get("parameter_key") or "").strip()
        delta = to_float(row.get(f"delta::{kpi}"))
        if delta is None or math.isnan(delta):
            return label or "n/a"
        if kpi == "fill_rate":
            value = f"{delta * 100:+.1f} pts"
        elif kpi == "ending_backlog":
            value = f"{delta:+,.0f}".replace(",", " ")
        else:
            value = f"{fmt_money(delta)}"
            if not value.startswith("-") and not value.startswith("+"):
                value = f"+{value}"
        suffix = ""
        if str(row.get("parameter_key") or "").startswith("demand_item::"):
            suffix = " (via produit)"
        return f"{label}{suffix} | {value}"

    global_fill_local = choose_local_global("fill_rate")
    global_fill_stress = choose_stress_global("fill_rate")
    global_cost_local = choose_local_global("total_cost")
    global_cost_stress = choose_stress_global("total_cost")

    def classify_node(node_id: str) -> str:
        service_stress = safe_abs((choose_node_stress(node_id, "fill_rate") or {}).get("delta::fill_rate"))
        backlog_stress = safe_abs((choose_node_stress(node_id, "ending_backlog") or {}).get("delta::ending_backlog"))
        cost_stress = safe_abs((choose_node_stress(node_id, "total_cost") or {}).get("delta::total_cost"))
        service_elasticity = safe_abs((choose_node_local(node_id, "fill_rate") or {}).get("abs_elasticity"))
        cost_elasticity = safe_abs((choose_node_local(node_id, "total_cost") or {}).get("abs_elasticity"))
        if service_stress >= 0.05 or backlog_stress >= 1000 or service_elasticity >= 0.05:
            return "Critique service"
        if cost_stress >= 250_000 or cost_elasticity >= 0.20:
            return "Critique cout"
        if service_stress >= 0.01 or backlog_stress >= 250 or cost_stress >= 25_000:
            return "Surveiller"
        return "Impact local faible"

    nodes_payload: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        local_fill = choose_node_local(node_id, "fill_rate")
        stress_fill = choose_node_stress(node_id, "fill_rate")
        local_backlog = choose_node_local(node_id, "ending_backlog")
        stress_backlog = choose_node_stress(node_id, "ending_backlog")
        local_cost = choose_node_local(node_id, "total_cost")
        stress_cost = choose_node_stress(node_id, "total_cost")
        nodes_payload[node_id] = {
            "title": "Sensibilite realiste annuelle",
            "summary_lines": [
                metric_label_value(
                    "Baseline",
                    f"FR {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
                ),
                metric_label_value("Service global", describe_stress(global_fill_stress, kpi="fill_rate")),
                metric_label_value("Service lie", describe_stress(stress_fill, kpi="fill_rate")),
                metric_label_value("Elasticite service", describe_local(local_fill, kpi="fill_rate")),
                metric_label_value("Backlog lie", describe_stress(stress_backlog, kpi="ending_backlog")),
                metric_label_value("Cout global", describe_stress(global_cost_stress, kpi="total_cost")),
                metric_label_value("Cout lie", describe_stress(stress_cost, kpi="total_cost")),
                metric_label_value("Elasticite cout", describe_local(local_cost, kpi="total_cost")),
                metric_label_value("Statut", classify_node(node_id)),
            ],
        }

    global_payload = {
        "title": "Sensibilite realiste annuelle",
        "summary_lines": [
            metric_label_value(
                "Baseline",
                f"FR {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
            ),
            metric_label_value("Service global", describe_stress(global_fill_stress, kpi="fill_rate")),
            metric_label_value("Elasticite service", describe_local(global_fill_local, kpi="fill_rate")),
            metric_label_value("Cout global", describe_stress(global_cost_stress, kpi="total_cost")),
            metric_label_value("Elasticite cout", describe_local(global_cost_local, kpi="total_cost")),
        ],
    }
    selected_suppliers = summary.get("selected_suppliers", []) if isinstance(summary, dict) else []
    return {"nodes": nodes_payload, "global": global_payload, "selected_suppliers": selected_suppliers}


def build_supplier_local_criticality(
    raw: dict[str, Any],
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_capacity_csv: Path,
    production_constraint_csv: Path,
    sensitivity_cases_csv: Path,
    structural_sensitivity_cases_csv: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    nodes = raw.get("nodes", []) or []
    edges = raw.get("edges", []) or []
    supplier_ids = sorted(str(n.get("id")) for n in nodes if str(n.get("type") or "") == "supplier_dc")
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}
    supplier_has_explicit_capacity = {
        str(n.get("id")): any(
            to_float(((proc.get("capacity") or {}).get("max_rate"))) not in (None, 0.0)
            and (to_float(((proc.get("capacity") or {}).get("max_rate"))) or 0.0) > 0.0
            for proc in (n.get("processes") or [])
        )
        for n in nodes
        if str(n.get("type") or "") == "supplier_dc"
    }
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    edges_by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    suppliers_for_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    target_share_by_supplier_pair: dict[tuple[str, tuple[str, str]], float] = {}
    supplier_initial_total: dict[str, float] = {}
    for n in nodes:
        if str(n.get("type") or "") != "supplier_dc":
            continue
        supplier_initial_total[str(n.get("id"))] = sum(
            max(0.0, to_float((st or {}).get("initial")) or 0.0)
            for st in ((n.get("inventory") or {}).get("states") or [])
        )
    for e in edges:
        src = str(e.get("from") or "")
        dst = str(e.get("to") or "")
        if src:
            edges_by_src[src].append(e)
        for item_id in e.get("items") or []:
            suppliers_for_pair[(dst, str(item_id))].add(src)

    def edge_transport_cost(edge: dict[str, Any]) -> float:
        tc = edge.get("transport_cost") or {}
        val = to_float((tc or {}).get("value"))
        if val is not None and val > 0:
            return val
        distance = to_float(edge.get("distance_km"))
        return max(0.02, (distance or 0.0) * 0.00008)

    def edge_lead_days(edge: dict[str, Any]) -> float:
        return max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)

    def mrp_split_shares(count: int) -> list[float]:
        if count <= 0:
            return []
        if count == 1:
            return [1.0]
        if count == 2:
            return [0.7, 0.3]
        if count == 3:
            return [0.7, 0.2, 0.1]
        tail = 0.1 / float(count - 2)
        return [0.7, 0.2] + [tail] * (count - 2)

    edges_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        dst = str(edge.get("to") or "")
        src = str(edge.get("from") or "")
        if not dst or not src:
            continue
        for item_id in edge.get("items") or []:
            edges_by_pair[(dst, str(item_id))].append(edge)
    for pair, pair_edges in edges_by_pair.items():
        sorted_edges = sorted(
            pair_edges,
            key=lambda edge: (
                edge_transport_cost(edge),
                edge_lead_days(edge),
                str(edge.get("from") or ""),
            ),
        )
        shares = mrp_split_shares(len(sorted_edges))
        for edge, share in zip(sorted_edges, shares):
            target_share_by_supplier_pair[(str(edge.get("from") or ""), pair)] = share

    shipment_rows = read_csv_rows(supplier_shipments_csv)
    stock_rows = read_csv_rows(supplier_stocks_csv)
    capacity_rows = read_csv_rows(supplier_capacity_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    sensitivity_case_rows = read_csv_rows(sensitivity_cases_csv)
    structural_case_rows = read_csv_rows(structural_sensitivity_cases_csv)
    by_case_std = case_rows_by_id(sensitivity_case_rows)
    by_case_struct = case_rows_by_id(structural_case_rows)
    baseline_std = by_case_std.get("baseline")
    baseline_struct = by_case_struct.get("baseline")

    shipped_qty_by_supplier: dict[str, float] = defaultdict(float)
    shipped_qty_by_supplier_pair: dict[tuple[str, tuple[str, str]], float] = defaultdict(float)
    total_pair_flow_qty: dict[tuple[str, str], float] = defaultdict(float)
    active_days_by_supplier: dict[str, set[int]] = defaultdict(set)
    first_day_by_supplier: dict[str, int] = {}
    last_day_by_supplier: dict[str, int] = {}
    for row in shipment_rows:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        qty = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        day = int(to_float(row.get("day")) or 0)
        if not src:
            continue
        shipped_qty_by_supplier[src] += qty
        if dst and item_id:
            pair = (dst, item_id)
            shipped_qty_by_supplier_pair[(src, pair)] += qty
            total_pair_flow_qty[pair] += qty
        if qty > 0:
            active_days_by_supplier[src].add(day)
            first_day_by_supplier[src] = min(first_day_by_supplier.get(src, day), day)
            last_day_by_supplier[src] = max(last_day_by_supplier.get(src, day), day)

    avg_stock_by_supplier: dict[str, float] = defaultdict(float)
    min_stock_by_supplier: dict[str, float] = {}
    stock_count_by_supplier: dict[str, int] = defaultdict(int)
    for row in stock_rows:
        node_id = str(row.get("node_id") or "")
        val = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        avg_stock_by_supplier[node_id] += val
        stock_count_by_supplier[node_id] += 1
        min_stock_by_supplier[node_id] = min(min_stock_by_supplier.get(node_id, val), val)
    for supplier_id, total in list(avg_stock_by_supplier.items()):
        count = max(1, stock_count_by_supplier.get(supplier_id, 0))
        avg_stock_by_supplier[supplier_id] = total / count

    avg_capacity_utilization_by_supplier: dict[str, float] = defaultdict(float)
    max_capacity_utilization_by_supplier: dict[str, float] = defaultdict(float)
    capacity_count_by_supplier: dict[str, int] = defaultdict(int)
    for row in capacity_rows:
        node_id = str(row.get("node_id") or "")
        util = max(0.0, to_float(row.get("utilization")) or 0.0)
        avg_capacity_utilization_by_supplier[node_id] += util
        capacity_count_by_supplier[node_id] += 1
        max_capacity_utilization_by_supplier[node_id] = max(
            max_capacity_utilization_by_supplier.get(node_id, 0.0),
            util,
        )
    for supplier_id, total in list(avg_capacity_utilization_by_supplier.items()):
        count = max(1, capacity_count_by_supplier.get(supplier_id, 0))
        avg_capacity_utilization_by_supplier[supplier_id] = total / count

    shortage_qty_by_item: dict[str, float] = defaultdict(float)
    shortage_events_by_item: dict[str, int] = defaultdict(int)
    for row in constraint_rows:
        if str(row.get("binding_cause") or "") != "input_shortage":
            continue
        item_id = str(row.get("binding_input_item_id") or "")
        if not item_id:
            continue
        shortage_qty_by_item[item_id] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        shortage_events_by_item[item_id] += 1

    total_shipped_all = sum(shipped_qty_by_supplier.values())
    max_active_days = max((len(days) for days in active_days_by_supplier.values()), default=1)

    def normalize_map(values: dict[str, float], log_scale: bool = False) -> dict[str, float]:
        transformed: dict[str, float] = {}
        for key, value in values.items():
            transformed[key] = math.log1p(value) if log_scale else value
        max_value = max(transformed.values(), default=0.0)
        if max_value <= 0:
            return {key: 0.0 for key in values}
        return {key: transformed.get(key, 0.0) / max_value for key in values}

    raw_metrics: dict[str, dict[str, float]] = {}
    for supplier_id in supplier_ids:
        supplied_items = sorted(outgoing_items.get(supplier_id, set()))
        dest_nodes = sorted({str(e.get("to") or "") for e in edges_by_src.get(supplier_id, []) if e.get("to") is not None})
        sole_source_pairs = 0
        shared_source_pairs = 0
        for e in edges_by_src.get(supplier_id, []):
            dst = str(e.get("to") or "")
            for item_id in e.get("items") or []:
                pair_suppliers = suppliers_for_pair.get((dst, str(item_id)), set())
                if len(pair_suppliers) <= 1:
                    sole_source_pairs += 1
                else:
                    shared_source_pairs += 1
        shortage_supported_qty = sum(shortage_qty_by_item.get(item_id, 0.0) for item_id in supplied_items)
        shortage_supported_events = sum(shortage_events_by_item.get(item_id, 0) for item_id in supplied_items)
        std_label, std_short, std_low, std_high, std_fill_impact, std_backlog_impact = select_best_supplier_case_pair(
            by_case_std,
            baseline_std,
            supplier_id,
        )
        struct_label, struct_short, struct_low, struct_high, struct_fill_impact, struct_backlog_impact = (
            select_best_supplier_case_pair(by_case_struct, baseline_struct, supplier_id)
        )
        raw_metrics[supplier_id] = {
            "total_shipped_qty": shipped_qty_by_supplier.get(supplier_id, 0.0),
            "active_days": float(len(active_days_by_supplier.get(supplier_id, set()))),
            "sole_source_pairs": float(sole_source_pairs),
            "shared_source_pairs": float(shared_source_pairs),
            "shortage_supported_qty": shortage_supported_qty,
            "shortage_supported_events": float(shortage_supported_events),
            "standard_fill_impact": std_fill_impact,
            "structural_fill_impact": struct_fill_impact,
            "standard_backlog_impact": std_backlog_impact,
            "structural_backlog_impact": struct_backlog_impact,
        }

    volume_score = normalize_map({k: v["total_shipped_qty"] for k, v in raw_metrics.items()}, log_scale=True)
    shortage_score = normalize_map({k: v["shortage_supported_qty"] for k, v in raw_metrics.items()}, log_scale=True)
    sole_source_score = normalize_map({k: v["sole_source_pairs"] for k, v in raw_metrics.items()})
    standard_system_score = normalize_map(
        {k: v["standard_fill_impact"] * 100.0 + v["standard_backlog_impact"] / 100.0 for k, v in raw_metrics.items()}
    )
    structural_system_score = normalize_map(
        {k: v["structural_fill_impact"] * 100.0 + v["structural_backlog_impact"] / 100.0 for k, v in raw_metrics.items()}
    )

    metrics_by_supplier: dict[str, Any] = {}
    ranking_rows: list[dict[str, Any]] = []
    for supplier_id in supplier_ids:
        supplied_items = sorted(outgoing_items.get(supplier_id, set()))
        dest_nodes = sorted({str(e.get("to") or "") for e in edges_by_src.get(supplier_id, []) if e.get("to") is not None})
        item_labels = ", ".join(item.split(":", 1)[-1] for item in supplied_items[:5])
        if len(supplied_items) > 5:
            item_labels += ", ..."
        total_shipped_qty = shipped_qty_by_supplier.get(supplier_id, 0.0)
        active_days = len(active_days_by_supplier.get(supplier_id, set()))
        served_pairs = sorted(
            {
                pair
                for (src, pair), qty in shipped_qty_by_supplier_pair.items()
                if src == supplier_id and qty > 1e-9
            }
        )
        all_supported_pairs = sorted(
            {
                (str(e.get("to") or ""), str(item_id))
                for e in edges_by_src.get(supplier_id, [])
                for item_id in (e.get("items") or [])
                if e.get("to") is not None
            }
        )
        observed_share_den = sum(total_pair_flow_qty.get(pair, 0.0) for pair in all_supported_pairs)
        observed_share_num = sum(shipped_qty_by_supplier_pair.get((supplier_id, pair), 0.0) for pair in all_supported_pairs)
        observed_sourcing_share = (observed_share_num / observed_share_den) if observed_share_den > 1e-9 else 0.0
        target_share_weighted_num = sum(
            target_share_by_supplier_pair.get((supplier_id, pair), 0.0) * total_pair_flow_qty.get(pair, 0.0)
            for pair in all_supported_pairs
        )
        target_sourcing_share = (target_share_weighted_num / observed_share_den) if observed_share_den > 1e-9 else 0.0
        local_score = (
            0.35 * volume_score.get(supplier_id, 0.0)
            + 0.20 * (active_days / max_active_days if max_active_days > 0 else 0.0)
            + 0.25 * sole_source_score.get(supplier_id, 0.0)
            + 0.20 * shortage_score.get(supplier_id, 0.0)
        )
        system_score = 0.5 * standard_system_score.get(supplier_id, 0.0) + 0.5 * structural_system_score.get(supplier_id, 0.0)
        overall_score = 0.55 * local_score + 0.45 * system_score
        std_label, _std_short, _std_low, _std_high, std_fill_impact, std_backlog_impact = select_best_supplier_case_pair(
            by_case_std,
            baseline_std,
            supplier_id,
        )
        struct_label, _struct_short, _struct_low, _struct_high, struct_fill_impact, struct_backlog_impact = (
            select_best_supplier_case_pair(by_case_struct, baseline_struct, supplier_id)
        )
        row = {
            "supplier_id": supplier_id,
            "supplier_name": node_name.get(supplier_id, supplier_id),
            "items_supplied_count": len(supplied_items),
            "dest_nodes_count": len(dest_nodes),
            "sole_source_pairs": int(raw_metrics[supplier_id]["sole_source_pairs"]),
            "shared_source_pairs": int(raw_metrics[supplier_id]["shared_source_pairs"]),
            "total_shipped_qty": round(total_shipped_qty, 4),
            "active_days": active_days,
            "first_shipment_day": first_day_by_supplier.get(supplier_id, ""),
            "last_shipment_day": last_day_by_supplier.get(supplier_id, ""),
            "initial_stock_total": round(supplier_initial_total.get(supplier_id, 0.0), 4),
            "avg_stock_end_of_day": round(avg_stock_by_supplier.get(supplier_id, 0.0), 4),
            "min_stock_end_of_day": round(min_stock_by_supplier.get(supplier_id, 0.0), 4),
            "avg_capacity_utilization": round(avg_capacity_utilization_by_supplier.get(supplier_id, 0.0), 6),
            "max_capacity_utilization": round(max_capacity_utilization_by_supplier.get(supplier_id, 0.0), 6),
            "observed_sourcing_share": round(observed_sourcing_share, 6),
            "target_sourcing_share": round(target_sourcing_share, 6),
            "capacity_metric_mode": "explicit_capacity" if supplier_has_explicit_capacity.get(supplier_id, False) else "sourcing_share",
            "shortage_supported_qty": round(raw_metrics[supplier_id]["shortage_supported_qty"], 4),
            "shortage_supported_events": int(raw_metrics[supplier_id]["shortage_supported_events"]),
            "standard_best_driver": std_label,
            "standard_fill_impact": round(std_fill_impact, 6),
            "standard_backlog_impact": round(std_backlog_impact, 4),
            "structural_best_driver": struct_label,
            "structural_fill_impact": round(struct_fill_impact, 6),
            "structural_backlog_impact": round(struct_backlog_impact, 4),
            "local_criticality_score": round(local_score, 6),
            "system_criticality_score": round(system_score, 6),
            "overall_criticality_score": round(overall_score, 6),
            "top_items_preview": item_labels,
            "destinations_preview": ", ".join(dest_nodes[:4]) + (", ..." if len(dest_nodes) > 4 else ""),
        }
        ranking_rows.append(row)
        metrics_by_supplier[supplier_id] = {
            "summary_lines": [
                metric_label_value("Rang local/systeme", ""),
                metric_label_value("Flux expedie total", f"{row['total_shipped_qty']:.2f}"),
                metric_label_value("Jours actifs", str(row["active_days"])),
                metric_label_value("Paires mono-source", str(row["sole_source_pairs"])),
                metric_label_value("Exposition shortage", f"{row['shortage_supported_qty']:.2f}"),
                metric_label_value("Driver standard", std_label or "n/a"),
                metric_label_value("Driver structurel", struct_label or "n/a"),
                metric_label_value("Score criticite locale", f"{local_score:.3f}"),
                metric_label_value("Score criticite systeme", f"{system_score:.3f}"),
            ],
            "items": supplied_items,
            "destinations": dest_nodes,
            "scores": {
                "local": round(local_score, 6),
                "system": round(system_score, 6),
                "overall": round(overall_score, 6),
            },
        }
        if supplier_has_explicit_capacity.get(supplier_id, False):
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                4,
                metric_label_value("Utilisation cap. moy.", f"{row['avg_capacity_utilization']:.2%}"),
            )
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                5,
                metric_label_value("Utilisation cap. max", f"{row['max_capacity_utilization']:.2%}"),
            )
        else:
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                4,
                metric_label_value("Part sourcing observee", f"{row['observed_sourcing_share']:.1%}"),
            )
            metrics_by_supplier[supplier_id]["summary_lines"].insert(
                5,
                metric_label_value("Part cible MRP", f"{row['target_sourcing_share']:.1%}"),
            )

    ranking_rows.sort(key=lambda row: (-float(row["overall_criticality_score"]), -float(row["total_shipped_qty"]), row["supplier_id"]))
    for rank, row in enumerate(ranking_rows, start=1):
        row["rank"] = rank
        supplier_metrics = metrics_by_supplier.get(str(row["supplier_id"]), {})
        if supplier_metrics:
            supplier_metrics["rank"] = rank
            for entry in supplier_metrics.get("summary_lines", []):
                if entry.get("label") == "Rang local/systeme":
                    entry["value"] = f"{rank}"
                    break

    summary = {
        "supplier_count": len(ranking_rows),
        "top_local_criticality": ranking_rows[:10],
        "methodology": {
            "local_score_weights": {
                "volume": 0.35,
                "active_days": 0.20,
                "sole_source_pairs": 0.25,
                "shortage_exposure": 0.20,
            },
            "overall_score_weights": {
                "local": 0.55,
                "system": 0.45,
            },
        },
    }
    return metrics_by_supplier, ranking_rows, summary


def html_template(title: str, data_json: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .title {{
      font-weight: 700;
      font-size: 14px;
      margin-right: 8px;
    }}
    .meta {{
      font-size: 12px;
      color: #475569;
      margin-right: 14px;
    }}
    .box {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .modeTabs {{
      display: inline-flex;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      overflow: hidden;
      background: #f8fafc;
    }}
    .modeBtn {{
      border: 0;
      background: transparent;
      color: #334155;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 12px;
      cursor: pointer;
    }}
    .modeBtn.active {{
      background: #0f172a;
      color: #ffffff;
    }}
    #typeFilters label {{
      margin-right: 8px;
      font-size: 12px;
      white-space: nowrap;
    }}
    #chart {{
      width: 100%;
      height: calc(100vh - 64px);
    }}
    #factoryHoverPanel {{
      position: fixed;
      right: 16px;
      top: 88px;
      width: min(760px, calc(100vw - 32px));
      max-height: calc(100vh - 110px);
      background: rgba(255,255,255,0.98);
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
      z-index: 20;
      overflow: auto;
      display: none;
      padding: 10px;
    }}
    #factoryHoverPanel.visible {{
      display: block;
    }}
    .panelHeader {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }}
    #factoryHoverTitle {{
      font-size: 13px;
      font-weight: 700;
      margin: 0;
      color: #0f172a;
      min-width: 0;
    }}
    .panelHeaderRight {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }}
    .panelStatePill {{
      display: none;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      background: #e2e8f0;
      color: #0f172a;
    }}
    .panelStatePill.visible {{
      display: inline-flex;
    }}
    .panelClearBtn {{
      display: none;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #334155;
      font-size: 11px;
      font-weight: 600;
      padding: 5px 8px;
      border-radius: 8px;
      cursor: pointer;
    }}
    .panelClearBtn.visible {{
      display: inline-flex;
    }}
    .factoryHoverGrid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .panelMeta {{
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      background: #f8fafc;
      padding: 10px 12px;
    }}
    .panelMetaTitle {{
      font-size: 11px;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }}
    .panelMetaGrid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px 12px;
    }}
    .panelMetaRow {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      color: #334155;
    }}
    .panelMetaLabel {{
      color: #64748b;
    }}
    .panelMetaValue {{
      font-weight: 600;
      color: #0f172a;
      text-align: right;
    }}
    .factoryPlotBlock {{
      display: block;
    }}
    .factoryPlotLabel {{
      font-size: 11px;
      color: #334155;
      margin: 0 0 4px 2px;
      font-weight: 600;
    }}
    .factoryPlot {{
      width: 100%;
      height: clamp(300px, 42.5vh, 425px);
      object-fit: contain;
      object-position: center top;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      background: #fff;
    }}
    .factoryPlotOutgoing {{
      height: clamp(237.5px, 33.75vh, 337.5px);
    }}
    #factoryHoverNoImage {{
      font-size: 12px;
      color: #475569;
      padding: 8px 2px;
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div class="title">{html.escape(title)}</div>
    <div class="meta" id="stats"></div>
    <div class="box">
      <div class="modeTabs">
        <button id="modeOps" class="modeBtn active" type="button">Simulation</button>
        <button id="modeSensitivity" class="modeBtn" type="button">Sensibilite</button>
        <button id="modeStructural" class="modeBtn" type="button">Structurel</button>
      </div>
    </div>
    <div class="box">
      <label><input type="checkbox" id="showEdges" checked> Afficher flux</label>
    </div>
    <div class="box" id="typeFilters"></div>
  </div>
  <div id="chart"></div>

  <div id="factoryHoverPanel">
    <div class="panelHeader">
      <div id="factoryHoverTitle"></div>
      <div class="panelHeaderRight">
        <div id="factoryHoverState" class="panelStatePill"></div>
        <button id="factoryHoverClearSelection" class="panelClearBtn" type="button">Effacer</button>
      </div>
    </div>
    <div class="factoryHoverGrid">
      <div id="panelMeta" class="panelMeta" style="display:none;">
        <div id="panelMetaTitle" class="panelMetaTitle">Criticite locale</div>
        <div id="panelMetaGrid" class="panelMetaGrid"></div>
      </div>
      <div id="incomingBlock" class="factoryPlotBlock">
        <div id="incomingLabel" class="factoryPlotLabel">Stock matieres premieres (entree)</div>
        <img id="factoryIncomingImage" class="factoryPlot" alt="Node incoming chart"/>
      </div>
      <div id="outgoingBlock" class="factoryPlotBlock">
        <div id="outgoingLabel" class="factoryPlotLabel">Production produits finis (sortie)</div>
        <img id="factoryOutgoingImage" class="factoryPlot factoryPlotOutgoing" alt="Node outgoing chart"/>
      </div>
      <div id="factoryHoverNoImage" style="display:none;">Aucun PNG disponible pour ce noeud.</div>
    </div>
  </div>

  <script>
    const DATA = {data_json};
    const STYLES = DATA.node_type_styles || {{}};
    const FACTORY_HOVER_IMAGES = DATA.factory_hover_images || {{}};
    const SUPPLIER_HOVER_IMAGES = DATA.supplier_hover_images || {{}};
    const DC_HOVER_IMAGES = DATA.distribution_center_hover_images || {{}};
    const FACTORY_SENSITIVITY_HOVER_IMAGES = DATA.factory_sensitivity_hover_images || {{}};
    const SUPPLIER_SENSITIVITY_HOVER_IMAGES = DATA.supplier_sensitivity_hover_images || {{}};
    const DC_SENSITIVITY_HOVER_IMAGES = DATA.distribution_center_sensitivity_hover_images || {{}};
    const FACTORY_STRUCTURAL_HOVER_IMAGES = DATA.factory_structural_hover_images || {{}};
    const SUPPLIER_STRUCTURAL_HOVER_IMAGES = DATA.supplier_structural_hover_images || {{}};
    const DC_STRUCTURAL_HOVER_IMAGES = DATA.distribution_center_structural_hover_images || {{}};
    const SUPPLIER_LOCAL_METRICS = DATA.supplier_local_metrics || {{}};
    const REALISTIC_SENSITIVITY = DATA.realistic_sensitivity || {{ nodes: {{}}, global: {{}}, selected_suppliers: [] }};
    const nodeById = Object.fromEntries((DATA.nodes || []).map(n => [n.id, n]));
    const defaultPalette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"];
    let currentFactoryHoverId = null;
    let currentFactoryHoverType = null;
    let currentHoveredPanelId = null;
    let currentHoveredPanelType = null;
    let selectedPanelNodeId = null;
    let selectedPanelNodeType = null;
    let currentPanelMode = "ops";
    let hoverHandlersBound = false;

    function styleForType(nodeType, idx) {{
      const s = STYLES[nodeType] || {{}};
      return {{
        name: s.name || nodeType,
        color: s.color || defaultPalette[idx % defaultPalette.length],
        symbol: s.symbol || "circle",
      }};
    }}

    function initFilters() {{
      const container = document.getElementById("typeFilters");
      container.innerHTML = "<strong style='font-size:12px;'>Types:</strong>";
      (DATA.node_types || []).forEach((t, idx) => {{
        const style = styleForType(t, idx);
        const lbl = document.createElement("label");
        lbl.innerHTML = `<input class="typeChk" type="checkbox" value="${{t}}" checked> ${{style.name}}`;
        container.appendChild(lbl);
      }});
    }}

    function selectedTypes() {{
      return new Set(Array.from(document.querySelectorAll(".typeChk"))
        .filter(x => x.checked)
        .map(x => x.value));
    }}

    function nodeText(n) {{
      const loc = n.location_ID ? n.location_ID : "n/a";
      const country = n.country ? n.country : "n/a";
      return `${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}<br>Country: ${{country}}<br>Location: ${{loc}}`;
    }}

    function edgeText(e) {{
      const itemCount = Array.isArray(e.items) ? e.items.length : 0;
      const itemPreview = itemCount ? e.items.join(", ") : "n/a";
      return `Edge: ${{e.id}}<br>${{e.from}} -> ${{e.to}}<br>Items (${{itemCount}}): ${{itemPreview}}`;
    }}

    function clamp(value, min, max) {{
      return Math.min(Math.max(value, min), max);
    }}

    function computeGeoView(visibleNodes) {{
      if (!visibleNodes.length) {{
        return {{ scale: 1 }};
      }}
      const lats = visibleNodes.map(n => n.lat);
      const lons = visibleNodes.map(n => n.lon);

      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLon = Math.min(...lons);
      let maxLon = Math.max(...lons);

      const latSpan = Math.max(maxLat - minLat, 0.5);
      const lonSpan = Math.max(maxLon - minLon, 0.5);
      const padLat = Math.max(latSpan * 0.25, 2.0);
      const padLon = Math.max(lonSpan * 0.25, 2.0);

      minLat = clamp(minLat - padLat, -85, 85);
      maxLat = clamp(maxLat + padLat, -85, 85);
      minLon = clamp(minLon - padLon, -180, 180);
      maxLon = clamp(maxLon + padLon, -180, 180);

      const spanLat = Math.max(maxLat - minLat, 1);
      const spanLon = Math.max(maxLon - minLon, 1);
      const effectiveSpan = Math.max(spanLat, spanLon * 0.55);
      const scale = clamp(120 / effectiveSpan, 1.1, 25);

      return {{
        scale: scale,
        center: {{
          lat: (minLat + maxLat) / 2,
          lon: (minLon + maxLon) / 2,
        }}
      }};
    }}

    function buildTraces() {{
      const traces = [];
      const visibleTypes = selectedTypes();
      const showEdges = document.getElementById("showEdges").checked;

      const visibleNodes = (DATA.nodes || []).filter(n =>
        visibleTypes.has(n.type) &&
        Number.isFinite(n.lat) &&
        Number.isFinite(n.lon)
      );
      const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

      (DATA.node_types || []).forEach((nodeType, idx) => {{
        if (!visibleTypes.has(nodeType)) return;
        const style = styleForType(nodeType, idx);
        const subset = visibleNodes.filter(n => n.type === nodeType);
        if (!subset.length) return;
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: style.name,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          text: subset.map(nodeText),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 9,
            color: style.color,
            symbol: style.symbol,
            line: {{ width: 0.6, color: "#111827" }}
          }}
        }});
      }});

      let drawnEdges = 0;
      if (showEdges) {{
        for (const e of (DATA.edges || [])) {{
          const src = nodeById[e.from];
          const dst = nodeById[e.to];
          if (!src || !dst) continue;
          if (!visibleNodeIds.has(src.id) || !visibleNodeIds.has(dst.id)) continue;
          if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) continue;
          if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) continue;
          const itemCount = Array.isArray(e.items) ? e.items.length : 0;
          const width = 1 + Math.min(itemCount, 4);
          traces.push({{
            type: "scattergeo",
            mode: "lines",
            showlegend: false,
            lon: [src.lon, dst.lon],
            lat: [src.lat, dst.lat],
            line: {{ width, color: "#475569" }},
            opacity: 0.65,
            text: edgeText(e),
            hoverinfo: "skip",
          }});
          drawnEdges += 1;
        }}
      }}

      document.getElementById("stats").textContent =
        `${{visibleNodes.length}} nodes visibles / ${{(DATA.nodes || []).length}} | ` +
        `${{showEdges ? drawnEdges : 0}} flux affiches / ${{(DATA.edges || []).length}}`;
      return {{ traces, visibleNodes }};
    }}

    function hideFactoryPanel() {{
      const panel = document.getElementById("factoryHoverPanel");
      const incomingBlock = document.getElementById("incomingBlock");
      const outgoingBlock = document.getElementById("outgoingBlock");
      const metaBlock = document.getElementById("panelMeta");
      const metaGrid = document.getElementById("panelMetaGrid");
      const incomingLabel = document.getElementById("incomingLabel");
      const outgoingLabel = document.getElementById("outgoingLabel");
      const incomingImg = document.getElementById("factoryIncomingImage");
      const outgoingImg = document.getElementById("factoryOutgoingImage");
      const noImg = document.getElementById("factoryHoverNoImage");
      const statePill = document.getElementById("factoryHoverState");
      const clearBtn = document.getElementById("factoryHoverClearSelection");
      incomingBlock.style.display = "block";
      outgoingBlock.style.display = "block";
      incomingLabel.textContent = "Stock matieres premieres (entree)";
      outgoingLabel.textContent = "Production produits finis (sortie)";
      incomingImg.removeAttribute("src");
      incomingImg.style.display = "none";
      outgoingImg.removeAttribute("src");
      outgoingImg.style.display = "none";
      metaGrid.innerHTML = "";
      metaBlock.style.display = "none";
      noImg.style.display = "none";
      statePill.textContent = "";
      statePill.classList.remove("visible");
      clearBtn.classList.remove("visible");
      panel.classList.remove("visible");
      currentFactoryHoverId = null;
      currentFactoryHoverType = null;
    }}

    function isPanelSelectableType(nodeType) {{
      return nodeType === "factory" || nodeType === "supplier_dc" || nodeType === "distribution_center";
    }}

    function currentPanelTarget() {{
      if (selectedPanelNodeId && selectedPanelNodeType) {{
        return {{
          nodeId: selectedPanelNodeId,
          nodeType: selectedPanelNodeType,
          state: "Selection",
        }};
      }}
      if (currentHoveredPanelId && currentHoveredPanelType) {{
        return {{
          nodeId: currentHoveredPanelId,
          nodeType: currentHoveredPanelType,
          state: "Survol",
        }};
      }}
      return null;
    }}

    function selectablePointFromEvent(ev) {{
      const points = ev && Array.isArray(ev.points) ? ev.points : [];
      for (const point of points) {{
        if (!Array.isArray(point.customdata)) continue;
        const nodeType = point.customdata[1];
        if (!isPanelSelectableType(nodeType)) continue;
        return point;
      }}
      return null;
    }}

    function refreshFactoryPanel() {{
      const target = currentPanelTarget();
      if (!target) {{
        hideFactoryPanel();
        return;
      }}
      showFactoryPanel(target.nodeId, target.nodeType, target.state);
    }}

    function clearPanelSelection() {{
      selectedPanelNodeId = null;
      selectedPanelNodeType = null;
      refreshFactoryPanel();
    }}

    function syncPanelStateWithVisibleNodes(visibleNodes) {{
      const visibleNodeIds = new Set((visibleNodes || []).map(n => n.id));
      if (selectedPanelNodeId && !visibleNodeIds.has(selectedPanelNodeId)) {{
        selectedPanelNodeId = null;
        selectedPanelNodeType = null;
      }}
      if (currentHoveredPanelId && !visibleNodeIds.has(currentHoveredPanelId)) {{
        currentHoveredPanelId = null;
        currentHoveredPanelType = null;
      }}
    }}

    function renderPanelMeta(nodeId, nodeType) {{
      const metaBlock = document.getElementById("panelMeta");
      const metaTitle = document.getElementById("panelMetaTitle");
      const metaGrid = document.getElementById("panelMetaGrid");
      metaGrid.innerHTML = "";
      if (currentPanelMode === "sensitivity") {{
        const nodeMetrics = (REALISTIC_SENSITIVITY.nodes || {{}})[nodeId] || null;
        const metrics = nodeMetrics || REALISTIC_SENSITIVITY.global || null;
        if (!metrics || !Array.isArray(metrics.summary_lines) || !metrics.summary_lines.length) {{
          metaBlock.style.display = "none";
          return false;
        }}
        metaTitle.textContent = metrics.title || "Sensibilite realiste";
        metrics.summary_lines.forEach((entry) => {{
          const row = document.createElement("div");
          row.className = "panelMetaRow";
          const label = document.createElement("div");
          label.className = "panelMetaLabel";
          label.textContent = entry.label || "";
          const value = document.createElement("div");
          value.className = "panelMetaValue";
          value.textContent = entry.value || "";
          row.appendChild(label);
          row.appendChild(value);
          metaGrid.appendChild(row);
        }});
        metaBlock.style.display = "block";
        return true;
      }}
      if (nodeType !== "supplier_dc") {{
        metaBlock.style.display = "none";
        return false;
      }}
      const metrics = SUPPLIER_LOCAL_METRICS[nodeId] || null;
      if (!metrics || !Array.isArray(metrics.summary_lines) || !metrics.summary_lines.length) {{
        metaBlock.style.display = "none";
        return false;
      }}
      metaTitle.textContent = "Criticite locale fournisseur";
      metrics.summary_lines.forEach((entry) => {{
        const row = document.createElement("div");
        row.className = "panelMetaRow";
        const label = document.createElement("div");
        label.className = "panelMetaLabel";
        label.textContent = entry.label || "";
        const value = document.createElement("div");
        value.className = "panelMetaValue";
        value.textContent = entry.value || "";
        row.appendChild(label);
        row.appendChild(value);
        metaGrid.appendChild(row);
      }});
      metaBlock.style.display = "block";
      return true;
    }}

    function panelLabels(nodeType) {{
      if (currentPanelMode === "sensitivity") {{
        return {{
          incoming: "KPI systeme + courbe delta vs baseline",
          outgoing: "KPI systeme + courbe delta vs baseline"
        }};
      }}
      if (currentPanelMode === "structural") {{
        return {{
          incoming: "Structurel - KPI + courbe delta vs baseline",
          outgoing: "Structurel - KPI + courbe delta vs baseline"
        }};
      }}
      if (nodeType === "supplier_dc") {{
        return {{
          incoming: "Stocks d'entree usine lies au fournisseur",
          outgoing: "Expeditions du fournisseur"
        }};
      }}
      if (nodeType === "distribution_center") {{
        return {{
          incoming: "Productions usines liees au distribution center",
          outgoing: "Sorties distribution center"
        }};
      }}
      return {{
        incoming: "Stock matieres premieres (entree)",
        outgoing: "Production produits finis (sortie)"
      }};
    }}

    function panelImages(nodeId, nodeType) {{
      if (currentPanelMode === "sensitivity") {{
        if (nodeType === "factory") return FACTORY_SENSITIVITY_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "supplier_dc") return SUPPLIER_SENSITIVITY_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "distribution_center") return DC_SENSITIVITY_HOVER_IMAGES[nodeId] || null;
        return null;
      }}
      if (currentPanelMode === "structural") {{
        if (nodeType === "factory") return FACTORY_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "supplier_dc") return SUPPLIER_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        if (nodeType === "distribution_center") return DC_STRUCTURAL_HOVER_IMAGES[nodeId] || null;
        return null;
      }}
      if (nodeType === "factory") return FACTORY_HOVER_IMAGES[nodeId] || null;
      if (nodeType === "supplier_dc") return SUPPLIER_HOVER_IMAGES[nodeId] || null;
      if (nodeType === "distribution_center") return DC_HOVER_IMAGES[nodeId] || null;
      return null;
    }}

    function applyModeUi() {{
      document.getElementById("modeOps").classList.toggle("active", currentPanelMode === "ops");
      document.getElementById("modeSensitivity").classList.toggle("active", currentPanelMode === "sensitivity");
      document.getElementById("modeStructural").classList.toggle("active", currentPanelMode === "structural");
    }}

    function setPanelMode(mode) {{
      currentPanelMode = mode;
      applyModeUi();
      refreshFactoryPanel();
    }}

    function showFactoryPanel(nodeId, nodeType, panelState) {{
      const images = panelImages(nodeId, nodeType) || {{}};

      const panel = document.getElementById("factoryHoverPanel");
      const title = document.getElementById("factoryHoverTitle");
      const incomingBlock = document.getElementById("incomingBlock");
      const outgoingBlock = document.getElementById("outgoingBlock");
      const incomingLabel = document.getElementById("incomingLabel");
      const outgoingLabel = document.getElementById("outgoingLabel");
      const incomingImg = document.getElementById("factoryIncomingImage");
      const outgoingImg = document.getElementById("factoryOutgoingImage");
      const noImg = document.getElementById("factoryHoverNoImage");
      const statePill = document.getElementById("factoryHoverState");
      const clearBtn = document.getElementById("factoryHoverClearSelection");
      const nodeInfo = nodeById[nodeId] || {{}};
      const nodeName = nodeInfo.name || nodeId;
      const nodeTitle = nodeType === "factory" ? "Factory" :
        (nodeType === "supplier_dc" ? "Supplier" : "Distribution Center");
      const modeTitle = currentPanelMode === "sensitivity" ? "Sensibilite" :
        (currentPanelMode === "structural" ? "Structurel" : "Simulation");
      title.textContent = `${{nodeTitle}}: ${{nodeName}} (${{nodeId}}) | ${{modeTitle}}`;
      if (panelState) {{
        statePill.textContent = panelState;
        statePill.classList.add("visible");
      }} else {{
        statePill.textContent = "";
        statePill.classList.remove("visible");
      }}
      clearBtn.classList.toggle("visible", !!selectedPanelNodeId);

      const labels = panelLabels(nodeType);
      incomingLabel.textContent = labels.incoming;
      outgoingLabel.textContent = labels.outgoing;
      const hasMeta = renderPanelMeta(nodeId, nodeType);

      const incomingImageInfo = images.incoming || null;
      const outgoingImageInfo = images.outgoing || null;

      incomingBlock.style.display = incomingImageInfo ? "block" : "none";
      outgoingBlock.style.display = outgoingImageInfo ? "block" : "none";

      let visibleCount = 0;
      if (incomingImageInfo && incomingImageInfo.data_b64) {{
        incomingImg.src = `data:${{incomingImageInfo.mime || "image/png"}};base64,${{incomingImageInfo.data_b64}}`;
        incomingImg.style.display = "block";
        visibleCount += 1;
      }} else {{
        incomingImg.removeAttribute("src");
        incomingImg.style.display = "none";
      }}

      if (outgoingImageInfo && outgoingImageInfo.data_b64) {{
        outgoingImg.src = `data:${{outgoingImageInfo.mime || "image/png"}};base64,${{outgoingImageInfo.data_b64}}`;
        outgoingImg.style.display = "block";
        visibleCount += 1;
      }} else {{
        outgoingImg.removeAttribute("src");
        outgoingImg.style.display = "none";
      }}

      if (!visibleCount && !hasMeta) {{
        hideFactoryPanel();
        return;
      }}
      if (!visibleCount) {{
        if (
          currentPanelMode === "sensitivity" &&
          nodeType === "supplier_dc" &&
          Array.isArray(REALISTIC_SENSITIVITY.selected_suppliers) &&
          !REALISTIC_SENSITIVITY.selected_suppliers.includes(nodeId)
        ) {{
          noImg.textContent = "Pas de courbe locale: fournisseur hors perimetre top actifs de l'etude.";
        }} else {{
          noImg.textContent = "Aucun PNG disponible pour ce noeud.";
        }}
      }}
      noImg.style.display = visibleCount ? "none" : "block";
      currentFactoryHoverId = nodeId;
      currentFactoryHoverType = nodeType;
      panel.classList.add("visible");
    }}

    function bindHoverHandlers() {{
      if (hoverHandlersBound) return;
      const gd = document.getElementById("chart");
      gd.on("plotly_hover", (ev) => {{
        const p = selectablePointFromEvent(ev);
        if (!p) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (!isPanelSelectableType(nodeType)) {{
          currentHoveredPanelId = null;
          currentHoveredPanelType = null;
          refreshFactoryPanel();
          return;
        }}
        currentHoveredPanelId = nodeId;
        currentHoveredPanelType = nodeType;
        refreshFactoryPanel();
      }});
      gd.on("plotly_unhover", () => {{
        currentHoveredPanelId = null;
        currentHoveredPanelType = null;
        refreshFactoryPanel();
      }});
      gd.on("plotly_click", (ev) => {{
        const p = selectablePointFromEvent(ev);
        if (!p) {{
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (!isPanelSelectableType(nodeType)) {{
          return;
        }}
        if (selectedPanelNodeId === nodeId && selectedPanelNodeType === nodeType) {{
          selectedPanelNodeId = null;
          selectedPanelNodeType = null;
        }} else {{
          selectedPanelNodeId = nodeId;
          selectedPanelNodeType = nodeType;
        }}
        refreshFactoryPanel();
      }});
      hoverHandlersBound = true;
    }}

    function draw() {{
      const {{ traces, visibleNodes }} = buildTraces();
      syncPanelStateWithVisibleNodes(visibleNodes);
      const geoView = computeGeoView(visibleNodes);
      const geoLayout = {{
        scope: "world",
        projection: {{type: "natural earth", scale: geoView.scale || 1}},
        showland: true,
        landcolor: "#eef2f7",
        showcountries: true,
        countrycolor: "#cbd5e1",
        showocean: true,
        oceancolor: "#f8fbff"
      }};
      if (geoView.center) {{
        geoLayout.center = geoView.center;
      }}

      const layout = {{
        margin: {{l: 0, r: 0, t: 0, b: 0}},
        showlegend: true,
        legend: {{orientation: "h"}},
        geo: geoLayout
      }};

      Plotly.newPlot("chart", traces, layout, {{displayModeBar: true, responsive: true}});
      bindHoverHandlers();
      refreshFactoryPanel();
    }}

    function init() {{
      initFilters();
      applyModeUi();
      document.getElementById("showEdges").addEventListener("change", draw);
      document.getElementById("modeOps").addEventListener("click", () => setPanelMode("ops"));
      document.getElementById("modeSensitivity").addEventListener("click", () => setPanelMode("sensitivity"));
      document.getElementById("modeStructural").addEventListener("click", () => setPanelMode("structural"));
      document.getElementById("factoryHoverClearSelection").addEventListener("click", clearPanelSelection);
      for (const chk of document.querySelectorAll(".typeChk")) {{
        chk.addEventListener("change", draw);
      }}
      draw();
    }}

    window.addEventListener("load", init);
  </script>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    sim_input = Path(args.sim_input_stocks_csv)
    sim_output = Path(args.sim_output_products_csv)
    sim_input_png_dir = Path(args.sim_input_stocks_png_dir)
    sim_output_png_dir = Path(args.sim_output_products_png_dir)
    sensitivity_cases_csv = Path(args.sensitivity_cases_csv)
    supplier_shipments_csv = Path(args.supplier_shipments_csv)
    supplier_stocks_csv = Path(args.supplier_stocks_csv)
    supplier_capacity_csv = Path(args.supplier_capacity_csv)
    production_constraint_csv = Path(args.production_constraint_csv)
    structural_sensitivity_cases_csv = Path(args.structural_sensitivity_cases_csv)
    supplier_local_criticality_csv = Path(args.supplier_local_criticality_csv)
    supplier_local_criticality_json = Path(args.supplier_local_criticality_json)
    realistic_sensitivity_summary_json = (
        Path(args.realistic_sensitivity_summary_json)
        if args.realistic_sensitivity_summary_json
        else Path("__missing_realistic_sensitivity_summary__.json")
    )
    realistic_local_elasticities_csv = (
        Path(args.realistic_local_elasticities_csv)
        if args.realistic_local_elasticities_csv
        else Path("__missing_realistic_local_elasticities__.csv")
    )
    realistic_stress_impacts_csv = (
        Path(args.realistic_stress_impacts_csv)
        if args.realistic_stress_impacts_csv
        else Path("__missing_realistic_stress_impacts__.csv")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    supplier_local_criticality_csv.parent.mkdir(parents=True, exist_ok=True)
    supplier_local_criticality_json.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        payload = compact_graph_payload(raw)
        payload["factory_hover_series"] = build_factory_hover_series(raw, sim_input, sim_output)
        payload["factory_hover_images"] = build_factory_hover_images(raw, sim_input_png_dir, sim_output_png_dir)
        payload["supplier_hover_images"] = build_supplier_hover_images(raw, sim_input_png_dir)
        payload["distribution_center_hover_images"] = build_distribution_center_hover_images(raw, sim_input_png_dir)
        (
            payload["factory_sensitivity_hover_images"],
            payload["supplier_sensitivity_hover_images"],
            payload["distribution_center_sensitivity_hover_images"],
        ) = build_sensitivity_hover_payloads(raw, sensitivity_cases_csv)
        (
            payload["factory_structural_hover_images"],
            payload["supplier_structural_hover_images"],
            payload["distribution_center_structural_hover_images"],
        ) = build_structural_sensitivity_hover_payloads(raw, structural_sensitivity_cases_csv)
        (
            payload["supplier_local_metrics"],
            supplier_local_ranking_rows,
            supplier_local_summary,
        ) = build_supplier_local_criticality(
            raw,
            supplier_shipments_csv,
            supplier_stocks_csv,
            supplier_capacity_csv,
            production_constraint_csv,
            sensitivity_cases_csv,
            structural_sensitivity_cases_csv,
        )
        payload["realistic_sensitivity"] = build_realistic_sensitivity_panel_metrics(
            raw,
            realistic_sensitivity_summary_json,
            realistic_local_elasticities_csv,
            realistic_stress_impacts_csv,
        )
    except Exception as exc:
        print(f"[ERROR] Unable to read/parse input JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    csv_columns = sorted({key for row in supplier_local_ranking_rows for key in row.keys()})
    with supplier_local_criticality_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns)
        writer.writeheader()
        writer.writerows(supplier_local_ranking_rows)
    supplier_local_criticality_json.write_text(
        json.dumps(
            {
                "summary": supplier_local_summary,
                "ranking": supplier_local_ranking_rows,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    html_str = html_template(args.title, json.dumps(payload, ensure_ascii=False))
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
