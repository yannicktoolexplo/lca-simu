"""Audit opening order book data against FIA/BOM and simulation outputs.

This audit focuses on whether the order book imported from
``Extract_En_cours.xlsx`` is consistent with the modeled supplier lanes and with
the MRP order rows produced by the simulation.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl


REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT = REPO_ROOT / "etudecas"
SOURCE_DIR = ROOT / "data" / "source"
OUT_DIR = ROOT / "analysis" / "from_simulation" / "result" / "audit_order_book_vs_source"

SOURCE_GRAPH_PATH = SOURCE_DIR / "supply_graph_poc.json"
OPEN_ORDERS_XLSX = SOURCE_DIR / "Extract_En_cours.xlsx"
STOCKS_MRP_XLSX = SOURCE_DIR / "Extract_Données_Complémentaires.xlsx"
PRODUCT_WORKBOOKS = {
    "268091": SOURCE_DIR / "268091.xlsx",
    "268967": SOURCE_DIR / "268967.xlsx",
    "773474": SOURCE_DIR / "773474.xlsx",
}

RUNS_TO_COMPARE = {
    "5y_full": ROOT
    / "simulation"
    / "result"
    / "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_portfolio_test",
    "268091_365d_all_open_orders": ROOT
    / "simulation"
    / "result"
    / "_experiments"
    / "stock_target_268091_snapshotfix"
    / "365d"
    / "mc_refine_028_s2_soft025_cap050"
    / "run",
    "268091_365d_strict_fia_orders": ROOT
    / "simulation"
    / "result"
    / "_experiments"
    / "stock_target_268091_snapshotfix"
    / "365d"
    / "mc_refine_028_s2_soft025_cap050_strict_fia_orders"
    / "run",
}

DIVISION_TO_NODE = {
    "1430": "M-1430",
    "1450": "SDC-1450",
    "1810": "M-1810",
    "1920": "DC-1920",
}


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def norm_code(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() and len(text) < 6 else text


def to_item(value: Any) -> str:
    code = norm_code(value)
    return f"item:{code}" if code else ""


def item_code(item_id: str) -> str:
    return str(item_id or "").replace("item:", "")


def norm_uom(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"UN.", "ZUN"}:
        return "UN"
    return text


def supplier_node(value: Any) -> str:
    text = str(value or "").strip().upper()
    if not text:
        return ""
    return text if text.startswith("SDC-") else f"SDC-{text}"


def workbook_rows(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet = workbook[sheet_name]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    out: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows[1:], start=2):
        if not any(cell not in (None, "") for cell in row):
            continue
        record = {header[i]: row[i] if i < len(row) else None for i in range(len(header)) if header[i]}
        record["_row"] = row_index
        out.append(record)
    return out


def convert_qty(qty: float, from_uom: str, to_uom: str) -> float:
    from_uom = norm_uom(from_uom)
    to_uom = norm_uom(to_uom)
    if not from_uom or not to_uom or from_uom == to_uom:
        return qty
    if from_uom == "G" and to_uom == "KG":
        return qty / 1000.0
    if from_uom == "KG" and to_uom == "G":
        return qty * 1000.0
    return qty


def safe_ratio(qty: float, lot: float) -> float:
    if lot <= 1e-9:
        return 0.0
    return qty / lot


def is_near_integer(value: float, tol: float = 1e-6) -> bool:
    return abs(value - round(value)) <= tol


def read_graph(path: Path = SOURCE_GRAPH_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def graph_open_orders(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((graph.get("meta") or {}).get("opening_open_orders") or {}).get("rows") or [])


def item_units_from_graph(graph: dict[str, Any]) -> dict[str, str]:
    units: dict[str, str] = {}
    for item in graph.get("items") or []:
        item_id = str(item.get("id") or "")
        uom = norm_uom(item.get("uom") or item.get("unit"))
        if item_id and uom:
            units[item_id] = uom
    for node in graph.get("nodes") or []:
        for state in ((node.get("inventory") or {}).get("states") or []):
            item_id = str(state.get("item_id") or "")
            uom = norm_uom(state.get("uom") or state.get("unit"))
            if item_id and uom:
                units.setdefault(item_id, uom)
    for edge in graph.get("edges") or []:
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        uom = norm_uom(terms.get("quantity_unit") or attrs.get("standard_order_uom"))
        for item_id in edge.get("items") or []:
            if item_id and uom:
                units.setdefault(str(item_id), uom)
    return units


def lane_index(graph: dict[str, Any]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    exact: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_dest_item: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        lead = (edge.get("lead_time") or {}).get("mean") if isinstance(edge.get("lead_time"), dict) else None
        price = parse_float(terms.get("sell_price"), default=float("nan"))
        base = parse_float(terms.get("price_base"), default=1.0) or 1.0
        unit_price = None if not math.isfinite(price) else price / base
        for raw_item in edge.get("items") or []:
            item_id = str(raw_item)
            lane = {
                "edge_id": str(edge.get("id") or ""),
                "src_node_id": src,
                "dst_node_id": dst,
                "item_id": item_id,
                "lead_days": parse_float(lead),
                "standard_order_qty": parse_float(attrs.get("standard_order_qty")),
                "standard_order_uom": norm_uom(attrs.get("standard_order_uom") or terms.get("quantity_unit")),
                "unit_price": unit_price,
                "price_uom": norm_uom(terms.get("quantity_unit") or attrs.get("standard_order_uom")),
                "product_code": attrs.get("product_code"),
            }
            exact[(src, dst, item_id)] = lane
            by_dest_item[(dst, item_id)].append(lane)
    return exact, by_dest_item


def bom_index() -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    components_by_product: dict[str, set[str]] = defaultdict(set)
    products_by_item: dict[str, set[str]] = defaultdict(set)
    item_kind: dict[str, str] = {}
    for product, path in PRODUCT_WORKBOOKS.items():
        rows = workbook_rows(path, "BOM")
        for row in rows:
            if norm_code(row.get("Produit Fini")) != product:
                continue
            comp = to_item(row.get("N° composante"))
            if not comp:
                continue
            components_by_product[product].add(comp)
            products_by_item[comp].add(product)
            item_kind.setdefault(comp, str(row.get("Type") or "component"))
        item_kind[f"item:{product}"] = "PF" if product != "773474" else "PFI"
        products_by_item[f"item:{product}"].add(product)
    return components_by_product, products_by_item, item_kind


def read_lot_policies() -> dict[tuple[str, str], dict[str, float]]:
    policies: dict[tuple[str, str], dict[str, float]] = {}
    for row in workbook_rows(STOCKS_MRP_XLSX, "Taille de Lots"):
        node = DIVISION_TO_NODE.get(str(row.get("Division") or "").strip())
        item_id = to_item(row.get("Numéro d'article"))
        if not node or not item_id:
            continue
        policies[(node, item_id)] = {
            "fixed_lot": parse_float(row.get("Taille de lot fixe")),
            "max_lot": parse_float(row.get("Taille de lot maximale")),
            "min_lot": parse_float(row.get("Taille de lot minimale")),
        }
    return policies


def read_source_open_orders() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in workbook_rows(OPEN_ORDERS_XLSX, "Sheet1"):
        planning = str(row.get("Elément de planification") or "").strip()
        planning_key = planning.upper().replace(" ", "")
        if planning_key in {"AVICDE", "ECHCDE"}:
            order_type = "purchase_open_order"
        elif planning_key == "O.PROC":
            order_type = "production_open_order"
        else:
            order_type = "unsupported_open_order"
        division = str(row.get("Division") or "").strip()
        rows.append(
            {
                "source_row": row.get("_row"),
                "order_type": order_type,
                "planning_element": planning,
                "item_id": to_item(row.get("Numéro d'article")),
                "dst_node_id": DIVISION_TO_NODE.get(division, ""),
                "division": division,
                "src_node_id": supplier_node(row.get("Numéro de compte fournisseur")) if order_type == "purchase_open_order" else "",
                "quantity": parse_float(row.get("Quantité")),
                "uom": norm_uom(row.get("Unité de quantité de base")),
                "physical_delivery_date": row.get("Date de livraison").isoformat()
                if isinstance(row.get("Date de livraison"), datetime)
                else row.get("Date de livraison"),
                "usable_date": row.get("Date entrée").isoformat()
                if isinstance(row.get("Date entrée"), datetime)
                else row.get("Date entrée"),
                "receipt_release_days": int(round(parse_float(row.get("Temps de réception en jours")))),
            }
        )
    return rows


def order_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("order_type"),
        row.get("dst_node_id") or row.get("node_id"),
        row.get("item_id"),
        row.get("src_node_id"),
        round(parse_float(row.get("quantity", row.get("release_qty"))), 6),
        row.get("usable_day", row.get("arrival_day")),
    )


def value_order(
    row: dict[str, Any],
    lane: dict[str, Any] | None,
    fallback_lanes: list[dict[str, Any]],
) -> tuple[float | None, str]:
    selected = lane
    source = "exact_lane"
    if selected is None and fallback_lanes:
        selected = fallback_lanes[0]
        source = "fallback_dest_item"
    if not selected or selected.get("unit_price") is None:
        return None, "unpriced"
    qty = parse_float(row.get("quantity", row.get("release_qty")))
    price_qty = convert_qty(qty, str(row.get("uom") or ""), str(selected.get("price_uom") or ""))
    return price_qty * float(selected["unit_price"]), source


def annotate_source_orders(
    source_rows: list[dict[str, Any]],
    graph_rows: list[dict[str, Any]],
    exact_lanes: dict[tuple[str, str, str], dict[str, Any]],
    dest_lanes: dict[tuple[str, str], list[dict[str, Any]]],
    products_by_item: dict[str, set[str]],
    item_kind: dict[str, str],
    item_units: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    graph_by_source = {int(row.get("source_row", -1)): row for row in graph_rows if row.get("source_row") not in (None, "")}
    annotated: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    duplicate_counter = Counter(order_key(row) for row in source_rows)
    for row in source_rows:
        graph_row = graph_by_source.get(int(row.get("source_row") or -1))
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        lane = exact_lanes.get((src, dst, item_id)) if row.get("order_type") == "purchase_open_order" else None
        fallback_lanes = dest_lanes.get((dst, item_id), [])
        value, valuation_source = value_order(row, lane, fallback_lanes)
        item_uom = item_units.get(item_id, str(row.get("uom") or ""))
        qty_item_uom = convert_qty(parse_float(row.get("quantity")), str(row.get("uom") or ""), item_uom)
        standard_qty = parse_float((lane or (fallback_lanes[0] if fallback_lanes else {})).get("standard_order_qty"))
        standard_uom = str((lane or (fallback_lanes[0] if fallback_lanes else {})).get("standard_order_uom") or item_uom)
        qty_standard_uom = convert_qty(parse_float(row.get("quantity")), str(row.get("uom") or ""), standard_uom)
        ratio = safe_ratio(qty_standard_uom, standard_qty)
        flags: list[str] = []
        if row.get("order_type") == "purchase_open_order":
            if lane is None:
                flags.append("supplier_item_lane_absent")
            if not fallback_lanes:
                flags.append("no_dest_item_lane")
            if standard_qty > 1e-9 and qty_standard_uom + 1e-9 < standard_qty:
                flags.append("below_standard_order_qty")
            if standard_qty > 1e-9 and not is_near_integer(ratio):
                flags.append("not_multiple_of_standard_order_qty")
        if row.get("order_type") == "unsupported_open_order":
            flags.append("unsupported_planning_element")
        if not row.get("dst_node_id"):
            flags.append("unmapped_division")
        if graph_row is None:
            flags.append("not_in_graph_open_orders")
        if duplicate_counter[order_key(row)] > 1:
            flags.append("duplicate_same_key")

        record = {
            **row,
            "product_scope": ",".join(sorted(products_by_item.get(item_id, set()))),
            "item_kind": item_kind.get(item_id, ""),
            "graph_resolved": bool(graph_row),
            "graph_usable_day": graph_row.get("usable_day") if graph_row else "",
            "graph_physical_delivery_day": graph_row.get("physical_delivery_day") if graph_row else "",
            "valid_exact_lane": bool(lane),
            "fallback_lane_count": len(fallback_lanes),
            "selected_edge_id": (lane or (fallback_lanes[0] if fallback_lanes else {})).get("edge_id", ""),
            "selected_lane_src": (lane or (fallback_lanes[0] if fallback_lanes else {})).get("src_node_id", ""),
            "lead_days_fia": (lane or (fallback_lanes[0] if fallback_lanes else {})).get("lead_days", ""),
            "standard_order_qty": standard_qty,
            "standard_order_uom": standard_uom,
            "qty_item_uom": qty_item_uom,
            "qty_standard_uom": qty_standard_uom,
            "standard_order_ratio": ratio if standard_qty > 1e-9 else "",
            "estimated_value_eur": value,
            "valuation_source": valuation_source,
            "flags": "|".join(flags),
        }
        annotated.append(record)
        for flag in flags:
            anomalies.append(
                {
                    "source": "source_open_order",
                    "severity": "high" if flag in {"supplier_item_lane_absent", "not_in_graph_open_orders"} else "medium",
                    "flag": flag,
                    "source_row": row.get("source_row"),
                    "order_type": row.get("order_type"),
                    "item_id": item_id,
                    "dst_node_id": dst,
                    "src_node_id": src,
                    "quantity": row.get("quantity"),
                    "uom": row.get("uom"),
                    "estimated_value_eur": value,
                }
            )
    return annotated, anomalies


def read_run_orders(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "data" / "mrp_orders_daily.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def annotate_run_orders(
    run_name: str,
    rows: list[dict[str, Any]],
    exact_lanes: dict[tuple[str, str, str], dict[str, Any]],
    dest_lanes: dict[tuple[str, str], list[dict[str, Any]]],
    products_by_item: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    annotated: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    for row in rows:
        order_type = str(row.get("order_type") or "")
        if not (order_type.startswith("opening") or order_type in {"lane_release", "lane_release_min_annual_lot"}):
            continue
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        lane = exact_lanes.get((src, dst, item_id)) if src != dst else None
        fallback_lanes = dest_lanes.get((dst, item_id), [])
        flags: list[str] = []
        if order_type == "opening_purchase_order":
            if not row.get("edge_id"):
                flags.append("run_opening_purchase_empty_edge")
            if lane is None:
                flags.append("run_opening_purchase_supplier_lane_absent")
            if parse_float(row.get("lead_reference_days")) <= 1e-9:
                flags.append("run_opening_purchase_zero_reference_lead")
        if order_type == "lane_release":
            if not row.get("edge_id"):
                flags.append("run_mrp_release_empty_edge")
        std = parse_float(row.get("standard_order_qty"))
        qty = parse_float(row.get("release_qty"))
        if std > 1e-9 and qty > 1e-9 and not is_near_integer(safe_ratio(qty, std), tol=1e-4):
            flags.append("run_qty_not_multiple_of_standard_order")
        record = {
            "run": run_name,
            "day": row.get("day"),
            "order_type": order_type,
            "node_id": row.get("node_id"),
            "dst_node_id": dst,
            "src_node_id": src,
            "item_id": item_id,
            "product_scope": ",".join(sorted(products_by_item.get(item_id, set()))),
            "edge_id": row.get("edge_id"),
            "release_qty": qty,
            "planned_receipt_qty": parse_float(row.get("planned_receipt_qty")),
            "release_day": row.get("release_day"),
            "arrival_day": row.get("arrival_day"),
            "actual_receipt_day": row.get("actual_receipt_day"),
            "lead_days": row.get("lead_days"),
            "lead_reference_days": row.get("lead_reference_days"),
            "standard_order_qty": std,
            "valid_exact_lane": bool(lane),
            "fallback_lane_count": len(fallback_lanes),
            "flags": "|".join(flags),
        }
        annotated.append(record)
        for flag in flags:
            anomalies.append(
                {
                    "source": f"run:{run_name}",
                    "severity": "high" if "supplier_lane_absent" in flag or "empty_edge" in flag else "medium",
                    "flag": flag,
                    "item_id": item_id,
                    "dst_node_id": dst,
                    "src_node_id": src,
                    "quantity": qty,
                    "uom": "",
                    "estimated_value_eur": "",
                }
            )
    return annotated, anomalies


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_source(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("product_scope") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("src_node_id") or ""),
        )
        rec = agg.setdefault(
            key,
            {
                "product_scope": key[0],
                "dst_node_id": key[1],
                "item_id": key[2],
                "src_node_id": key[3],
                "rows": 0,
                "qty_item_uom": 0.0,
                "estimated_value_eur": 0.0,
                "supplier_lane_absent_rows": 0,
                "not_in_graph_rows": 0,
                "flags": Counter(),
            },
        )
        rec["rows"] += 1
        rec["qty_item_uom"] += parse_float(row.get("qty_item_uom"))
        rec["estimated_value_eur"] += parse_float(row.get("estimated_value_eur"))
        flags = [f for f in str(row.get("flags") or "").split("|") if f]
        for flag in flags:
            rec["flags"][flag] += 1
        if "supplier_item_lane_absent" in flags:
            rec["supplier_lane_absent_rows"] += 1
        if "not_in_graph_open_orders" in flags:
            rec["not_in_graph_rows"] += 1
    out = []
    for rec in agg.values():
        out.append({**rec, "flags": "; ".join(f"{k}:{v}" for k, v in rec["flags"].most_common())})
    return sorted(out, key=lambda r: (-float(r.get("estimated_value_eur") or 0.0), r["item_id"]))


def aggregate_runs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            str(row.get("run") or ""),
            str(row.get("order_type") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("src_node_id") or ""),
        )
        rec = agg.setdefault(
            key,
            {
                "run": key[0],
                "order_type": key[1],
                "dst_node_id": key[2],
                "item_id": key[3],
                "src_node_id": key[4],
                "rows": 0,
                "release_qty": 0.0,
                "empty_edge_rows": 0,
                "supplier_lane_absent_rows": 0,
                "flags": Counter(),
            },
        )
        rec["rows"] += 1
        rec["release_qty"] += parse_float(row.get("release_qty"))
        flags = [f for f in str(row.get("flags") or "").split("|") if f]
        for flag in flags:
            rec["flags"][flag] += 1
        if any("empty_edge" in f for f in flags):
            rec["empty_edge_rows"] += 1
        if any("supplier_lane_absent" in f for f in flags):
            rec["supplier_lane_absent_rows"] += 1
    out = []
    for rec in agg.values():
        out.append({**rec, "flags": "; ".join(f"{k}:{v}" for k, v in rec["flags"].most_common())})
    return sorted(out, key=lambda r: (r["run"], r["order_type"], -float(r.get("release_qty") or 0.0)))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = read_graph()
    exact_lanes, dest_lanes = lane_index(graph)
    item_units = item_units_from_graph(graph)
    _, products_by_item, item_kind = bom_index()
    lot_policies = read_lot_policies()
    source_rows = read_source_open_orders()
    graph_rows = graph_open_orders(graph)

    source_audit, source_anomalies = annotate_source_orders(
        source_rows,
        graph_rows,
        exact_lanes,
        dest_lanes,
        products_by_item,
        item_kind,
        item_units,
    )
    run_audit: list[dict[str, Any]] = []
    run_anomalies: list[dict[str, Any]] = []
    run_counts: dict[str, Any] = {}
    for run_name, run_dir in RUNS_TO_COMPARE.items():
        rows = read_run_orders(run_dir)
        annotated, anomalies = annotate_run_orders(run_name, rows, exact_lanes, dest_lanes, products_by_item)
        run_audit.extend(annotated)
        run_anomalies.extend(anomalies)
        order_counter = Counter(row.get("order_type") for row in rows)
        run_counts[run_name] = {
            "path": str(run_dir),
            "mrp_order_rows": len(rows),
            "order_types": dict(order_counter),
            "opening_purchase_rows": order_counter.get("opening_purchase_order", 0),
            "opening_production_rows": order_counter.get("opening_production_order", 0),
        }

    anomalies = source_anomalies + run_anomalies
    source_summary = aggregate_source(source_audit)
    run_summary = aggregate_runs(run_audit)

    open_order_values = [parse_float(row.get("estimated_value_eur")) for row in source_audit if row.get("estimated_value_eur") not in (None, "")]
    mismatch_value = sum(
        parse_float(row.get("estimated_value_eur"))
        for row in source_audit
        if "supplier_item_lane_absent" in str(row.get("flags") or "")
    )
    graph_missing_rows = [row for row in source_audit if "not_in_graph_open_orders" in str(row.get("flags") or "")]
    exact_missing_rows = [row for row in source_audit if "supplier_item_lane_absent" in str(row.get("flags") or "")]
    not_multiple_rows = [row for row in source_audit if "not_multiple_of_standard_order_qty" in str(row.get("flags") or "")]

    summary = {
        "source_open_orders_raw_rows": len(source_rows),
        "source_open_orders_graph_rows": len(graph_rows),
        "source_purchase_rows": sum(1 for row in source_rows if row.get("order_type") == "purchase_open_order"),
        "source_production_rows": sum(1 for row in source_rows if row.get("order_type") == "production_open_order"),
        "source_rows_not_in_graph": len(graph_missing_rows),
        "source_purchase_rows_missing_exact_lane": len(exact_missing_rows),
        "source_purchase_value_missing_exact_lane_eur": mismatch_value,
        "source_order_value_estimate_eur": sum(open_order_values),
        "source_order_value_mean_eur": statistics.mean(open_order_values) if open_order_values else 0.0,
        "source_not_multiple_standard_rows": len(not_multiple_rows),
        "run_counts": run_counts,
    }

    write_csv(OUT_DIR / "source_open_orders_audit.csv", source_audit)
    write_csv(OUT_DIR / "source_open_orders_summary.csv", source_summary)
    write_csv(OUT_DIR / "run_order_book_audit.csv", run_audit)
    write_csv(OUT_DIR / "run_order_book_summary.csv", run_summary)
    write_csv(OUT_DIR / "order_book_anomalies.csv", anomalies)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    top_mismatch = sorted(exact_missing_rows, key=lambda r: parse_float(r.get("estimated_value_eur")), reverse=True)[:12]
    top_orders = sorted(source_audit, key=lambda r: parse_float(r.get("estimated_value_eur")), reverse=True)[:12]
    top_run_anomalies = Counter(row.get("flag") for row in anomalies).most_common(12)

    md = [
        "# Audit carnet d'ordres vs sources",
        "",
        "## Synthese",
        "",
        f"- Lignes brutes `Extract_En_cours.xlsx`: {len(source_rows)}.",
        f"- Lignes resolues dans `supply_graph_poc.json`: {len(graph_rows)}.",
        f"- Ordres achat source: {summary['source_purchase_rows']} ; ordres production source: {summary['source_production_rows']}.",
        f"- Ordres achat sans voie fournisseur-item FIA exacte: {summary['source_purchase_rows_missing_exact_lane']} lignes, valeur estimee {mismatch_value:,.0f} EUR.",
        f"- Lignes source absentes du graphe ouvert: {summary['source_rows_not_in_graph']} lignes.",
        f"- Lignes achat non multiples de la quantite standard FIA: {summary['source_not_multiple_standard_rows']} lignes.",
        "",
        "## Lecture metier courte",
        "",
        "- Le carnet d'ordres reel est bien injecte dans le run 5 ans complet, mais certaines commandes fermes n'ont pas de voie fournisseur-item valide.",
        "- Quand une ligne achat n'a pas de voie FIA exacte, le moteur peut quand meme injecter la reception ferme; la ligne perd alors sa reference logistique/prix/lead fiable.",
        "- Les ordres de production ouverts (`O.Proc`) n'ont pas d'edge, ce qui est normal; ils representent une production interne deja planifiee.",
        "- Les ecarts critiques sont donc les achats ouverts sans voie FIA, pas les ordres de production sans edge.",
        "",
        "## Runs compares",
        "",
        "| Run | Ordres MRP | Opening achats | Opening production | Types |",
        "|---|---:|---:|---:|---|",
    ]
    for run_name, payload in run_counts.items():
        types = ", ".join(f"{k}:{v}" for k, v in sorted(payload["order_types"].items()))
        md.append(
            f"| {run_name} | {payload['mrp_order_rows']} | {payload['opening_purchase_rows']} | "
            f"{payload['opening_production_rows']} | {types} |"
        )
    md.extend(
        [
            "",
            "## Plus gros ordres ouverts source valorises",
            "",
            "| Row | Type | Produit scope | Item | Destination | Fournisseur | Quantite | UOM | Valeur EUR | Flags |",
            "|---:|---|---|---|---|---|---:|---|---:|---|",
        ]
    )
    for row in top_orders:
        md.append(
            f"| {row.get('source_row')} | {row.get('order_type')} | {row.get('product_scope')} | {row.get('item_id')} | "
            f"{row.get('dst_node_id')} | {row.get('src_node_id')} | {parse_float(row.get('quantity')):,.1f} | "
            f"{row.get('uom')} | {parse_float(row.get('estimated_value_eur')):,.0f} | {row.get('flags')} |"
        )
    md.extend(
        [
            "",
            "## Achats ouverts sans voie FIA exacte",
            "",
            "| Row | Produit scope | Item | Destination | Fournisseur carnet | Voie utilisee fallback | Quantite | UOM | Valeur EUR |",
            "|---:|---|---|---|---|---|---:|---|---:|",
        ]
    )
    for row in top_mismatch:
        md.append(
            f"| {row.get('source_row')} | {row.get('product_scope')} | {row.get('item_id')} | {row.get('dst_node_id')} | "
            f"{row.get('src_node_id')} | {row.get('selected_lane_src')} | {parse_float(row.get('quantity')):,.1f} | "
            f"{row.get('uom')} | {parse_float(row.get('estimated_value_eur')):,.0f} |"
        )
    md.extend(
        [
            "",
            "## Top anomalies",
            "",
            "| Anomalie | Occurrences |",
            "|---|---:|",
        ]
    )
    for flag, count in top_run_anomalies:
        md.append(f"| {flag} | {count} |")
    md.extend(
        [
            "",
            "## Fichiers generes",
            "",
            "- `source_open_orders_audit.csv` : chaque ligne source enrichie avec voie FIA, lot standard, valeur estimee et flags.",
            "- `source_open_orders_summary.csv` : aggregation source par produit/site/item/fournisseur.",
            "- `run_order_book_audit.csv` : ordres MRP simules et flags de coherence.",
            "- `run_order_book_summary.csv` : aggregation des ordres simules.",
            "- `order_book_anomalies.csv` : anomalies source et run.",
        ]
    )
    (OUT_DIR / "audit_order_book_vs_source_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[OK] report={OUT_DIR / 'audit_order_book_vs_source_report.md'}")


if __name__ == "__main__":
    main()
