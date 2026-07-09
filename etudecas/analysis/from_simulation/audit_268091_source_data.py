"""Audit likely source-data issues around PF 268091 component stock.

The goal is not to validate the simulation engine. It checks whether source
files can explain the gap between the real Cos component immobilized stock
and the simulated component stock for the 268091 BOM.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl


REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT = REPO_ROOT / "etudecas"
SOURCE_DIR = ROOT / "data" / "source"
OUT_DIR = ROOT / "analysis" / "from_simulation" / "result" / "audit_268091_source_data"

PRODUCT_CODE = "268091"
PRODUCT_ITEM = "item:268091"
FACTORY_DIVISION = "1810"
FACTORY_NODE = "M-1810"


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


def norm_uom(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"UN.", "ZUN"}:
        return "UN"
    return text


def to_item(code: Any) -> str:
    return f"item:{norm_code(code)}"


def workbook_rows(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet = workbook[sheet_name]
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    out: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows[1:], start=2):
        record = {header[i]: row[i] if i < len(row) else None for i in range(len(header))}
        record["_row"] = row_index
        out.append(record)
    return out


def source_graph() -> dict[str, Any]:
    return json.loads((SOURCE_DIR / "supply_graph_poc.json").read_text(encoding="utf-8"))


def read_real_component_stock() -> list[float]:
    path = next(SOURCE_DIR.glob("Stock_Composants*Cos.csv"))
    values: list[float] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            values.append(parse_float(row.get("Sum_Valeur totale du stock")))
    return values


def read_ca() -> dict[str, float]:
    matches = sorted(SOURCE_DIR.glob("CA_Perdu*.csv"))
    if not matches:
        return {}
    total_livre = 0.0
    total_perdu = 0.0
    with matches[0].open(encoding="cp1252", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        next(reader, None)
        for row in reader:
            if len(row) < 5 or str(row[0]).strip() != PRODUCT_CODE:
                continue
            total_livre += parse_float(row[2])
            total_perdu += parse_float(row[3])
    return {
        "ca_livre": total_livre,
        "ca_perdu": total_perdu,
        "ca_potentiel": total_livre + total_perdu,
        "service_ca": total_livre / (total_livre + total_perdu) if total_livre + total_perdu else 0.0,
    }


def component_prices(graph: dict[str, Any], component_items: set[str]) -> dict[str, dict[str, Any]]:
    product_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fallback_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.get("edges", []):
        item_id = (edge.get("items") or [None])[0]
        if item_id not in component_items:
            continue
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        sell_price = parse_float(terms.get("sell_price"), default=float("nan"))
        price_base = parse_float(terms.get("price_base"), default=1.0) or 1.0
        unit_price = None if sell_price != sell_price else sell_price / price_base
        row = {
            "supplier": edge.get("from"),
            "unit_price": unit_price,
            "price_uom": norm_uom(terms.get("quantity_unit") or attrs.get("standard_order_uom")),
            "standard_order_qty": parse_float(attrs.get("standard_order_qty")),
            "source_workbook": attrs.get("source_workbook"),
            "product_code": attrs.get("product_code"),
        }
        if attrs.get("product_code") == PRODUCT_CODE:
            product_rows[item_id].append(row)
        else:
            fallback_rows[item_id].append(row)

    out: dict[str, dict[str, Any]] = {}
    for item_id in sorted(component_items):
        rows = product_rows.get(item_id) or fallback_rows.get(item_id) or []
        positive = [float(row["unit_price"]) for row in rows if row.get("unit_price") and float(row["unit_price"]) > 0]
        out[item_id] = {
            "unit_price": statistics.median(positive) if positive else None,
            "sources": rows,
            "source_count": len(rows),
            "price_scope": "product_code" if product_rows.get(item_id) else ("fallback" if rows else "missing"),
        }
    return out


def qty_to_price_uom(qty: float, qty_uom: str, price_uom: str) -> float:
    qty_uom = norm_uom(qty_uom)
    price_uom = norm_uom(price_uom)
    if qty_uom == price_uom:
        return qty
    if qty_uom == "G" and price_uom == "KG":
        return qty / 1000.0
    if qty_uom == "KG" and price_uom == "G":
        return qty * 1000.0
    return qty


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    graph = source_graph()
    bom_rows = workbook_rows(SOURCE_DIR / "268091.xlsx", "BOM")
    fia_rows = workbook_rows(SOURCE_DIR / "268091.xlsx", "FIA")
    open_rows = workbook_rows(SOURCE_DIR / "Extract_En_cours.xlsx", "Sheet1")
    stock_rows = workbook_rows(SOURCE_DIR / "Extract_Données_Complémentaires.xlsx", "Stocks")

    bom_components = []
    for row in bom_rows:
        if norm_code(row.get("Produit Fini")) != PRODUCT_CODE:
            continue
        bom_components.append(
            {
                "item_id": to_item(row.get("N° composante")),
                "component_code": norm_code(row.get("N° composante")),
                "type": row.get("Type"),
                "qty_per_1000": parse_float(row.get("Qté composants (UQB)")),
                "uom": norm_uom(row.get("Unité de quantité")),
                "row": row.get("_row"),
            }
        )
    component_items = {row["item_id"] for row in bom_components}
    prices = component_prices(graph, component_items)

    fia_suppliers_by_item: dict[str, set[str]] = defaultdict(set)
    for row in fia_rows:
        item_id = to_item(row.get("Numéro d'article"))
        if item_id in component_items:
            fia_suppliers_by_item[item_id].add(f"SDC-{row.get('Numéro de compte fournisseur')}")

    open_order_rows = []
    supplier_mismatch_rows = []
    total_open_order_value = 0.0
    for row in open_rows:
        if str(row.get("Division")).strip() != FACTORY_DIVISION:
            continue
        item_id = to_item(row.get("Numéro d'article"))
        if item_id not in component_items:
            continue
        supplier = f"SDC-{row.get('Numéro de compte fournisseur')}"
        qty = parse_float(row.get("Quantité"))
        uom = norm_uom(row.get("Unité de quantité de base"))
        price = prices.get(item_id, {}).get("unit_price")
        price_uom = ""
        price_sources = prices.get(item_id, {}).get("sources") or []
        if price_sources:
            price_uom = price_sources[0].get("price_uom") or ""
        value = None
        if price is not None:
            value = qty_to_price_uom(qty, uom, price_uom) * float(price)
            total_open_order_value += value
        record = {
            "source_row": row.get("_row"),
            "item_id": item_id,
            "supplier": supplier,
            "qty": qty,
            "uom": uom,
            "date_livraison": row.get("Date de livraison").isoformat() if isinstance(row.get("Date de livraison"), datetime) else row.get("Date de livraison"),
            "date_entree": row.get("Date entrée").isoformat() if isinstance(row.get("Date entrée"), datetime) else row.get("Date entrée"),
            "value_eur": value,
            "fia_suppliers": ",".join(sorted(fia_suppliers_by_item.get(item_id, set()))),
        }
        open_order_rows.append(record)
        if supplier not in fia_suppliers_by_item.get(item_id, set()):
            supplier_mismatch_rows.append(record)

    stock_report = []
    for row in stock_rows:
        if str(row.get("Division")).strip() != FACTORY_DIVISION:
            continue
        item_id = to_item(row.get("Numéro d'article"))
        if item_id not in component_items:
            continue
        qty = parse_float(row.get("Stock Total"))
        uom = norm_uom(row.get("Unité de quantité de base"))
        price = prices.get(item_id, {}).get("unit_price")
        price_uom = ""
        price_sources = prices.get(item_id, {}).get("sources") or []
        if price_sources:
            price_uom = price_sources[0].get("price_uom") or ""
        value = qty_to_price_uom(qty, uom, price_uom) * float(price) if price is not None else None
        stock_report.append(
            {
                "item_id": item_id,
                "stock_qty": qty,
                "stock_uom": uom,
                "unit_price": price,
                "price_uom": price_uom,
                "value_eur": value,
                "source_row": row.get("_row"),
            }
        )

    bom_cost_rows = []
    total_bom_cost_per_1000 = 0.0
    for row in bom_components:
        price = prices.get(row["item_id"], {}).get("unit_price")
        price_sources = prices.get(row["item_id"], {}).get("sources") or []
        price_uom = price_sources[0].get("price_uom") if price_sources else ""
        cost = None
        if price is not None:
            cost = qty_to_price_uom(row["qty_per_1000"], row["uom"], price_uom or row["uom"]) * float(price)
            total_bom_cost_per_1000 += cost
        bom_cost_rows.append({**row, "unit_price": price, "price_uom": price_uom, "cost_per_1000": cost})

    observed_stock_values = read_real_component_stock()
    ca = read_ca()
    summary = {
        "real_component_immobilized_stock_mean_eur": statistics.mean(observed_stock_values),
        "real_component_immobilized_stock_min_eur": min(observed_stock_values),
        "real_component_immobilized_stock_max_eur": max(observed_stock_values),
        "bom_component_count": len(bom_components),
        "bom_cost_per_1000_eur": total_bom_cost_per_1000,
        "bom_cost_per_unit_eur": total_bom_cost_per_1000 / 1000.0,
        "opening_open_order_value_eur": total_open_order_value,
        "supplier_mismatch_count": len(supplier_mismatch_rows),
        "supplier_mismatch_value_eur": sum(float(row.get("value_eur") or 0.0) for row in supplier_mismatch_rows),
        **ca,
    }

    def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        fields = sorted({key for row in rows for key in row})
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(OUT_DIR / "bom_cost_audit.csv", bom_cost_rows)
    write_csv(OUT_DIR / "opening_orders_audit.csv", open_order_rows)
    write_csv(OUT_DIR / "supplier_mismatches.csv", supplier_mismatch_rows)
    write_csv(OUT_DIR / "stock_snapshot_audit.csv", stock_report)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    top_mismatch = sorted(supplier_mismatch_rows, key=lambda row: float(row.get("value_eur") or 0.0), reverse=True)[:8]
    top_orders = sorted(open_order_rows, key=lambda row: float(row.get("value_eur") or 0.0), reverse=True)[:8]
    md = [
        "# Audit donnees source 268091",
        "",
        f"- Stock composant immobilise reel moyen: {summary['real_component_immobilized_stock_mean_eur']:,.0f} EUR.",
        f"- Cout BOM valorise: {summary['bom_cost_per_unit_eur']:,.3f} EUR/unite PF.",
        f"- Valeur des ordres ouverts initiaux composants 268091: {summary['opening_open_order_value_eur']:,.0f} EUR.",
        f"- Valeur avec fournisseur en-cours absent de la FIA: {summary['supplier_mismatch_value_eur']:,.0f} EUR ({summary['supplier_mismatch_count']} lignes).",
        f"- CA potentiel reel 268091: {summary.get('ca_potentiel', 0.0):,.0f} EUR ; service CA: {summary.get('service_ca', 0.0):.1%}.",
        "",
        "## Principaux ordres ouverts",
        "",
        "| Source row | Item | Fournisseur | Quantite | UOM | Valeur EUR | Fournisseurs FIA |",
        "|---:|---|---|---:|---|---:|---|",
    ]
    for row in top_orders:
        md.append(
            f"| {row['source_row']} | {row['item_id']} | {row['supplier']} | {row['qty']:,.1f} | "
            f"{row['uom']} | {float(row.get('value_eur') or 0.0):,.0f} | {row['fia_suppliers']} |"
        )
    md.extend(
        [
            "",
            "## Fournisseurs en-cours absents de la FIA",
            "",
            "| Source row | Item | Fournisseur en-cours | Quantite | UOM | Valeur EUR | Fournisseurs FIA |",
            "|---:|---|---|---:|---|---:|---|",
        ]
    )
    for row in top_mismatch:
        md.append(
            f"| {row['source_row']} | {row['item_id']} | {row['supplier']} | {row['qty']:,.1f} | "
            f"{row['uom']} | {float(row.get('value_eur') or 0.0):,.0f} | {row['fia_suppliers']} |"
        )
    md.extend(
        [
            "",
            "## Lecture",
            "",
            "- Le probleme le plus probable est un ecart entre la FIA et le carnet d'ordres initial, surtout sur `item:049371`.",
            "- Si les ordres ouverts `049371` appartiennent bien a `VD0518550B`, il manque une voie FIA pour ce fournisseur; si ce fournisseur est obsolete, ces ordres ne doivent peut-etre pas etre injectes tels quels.",
            "- Le KPI reel est agrege: il ne permet pas de verifier composant par composant quelle partie du stock est incluse dans `stock immobilise Cos`.",
        ]
    )
    (OUT_DIR / "audit_268091_source_data_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[OK] report={OUT_DIR / 'audit_268091_source_data_report.md'}")


if __name__ == "__main__":
    main()
