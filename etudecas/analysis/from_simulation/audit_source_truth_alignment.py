"""Audit source-truth alignment for one finished product simulation scope.

This report keeps four notions separate:

* physical component stock from ``Extract_Données_Complémentaires.xlsx``;
* source open manufacturing and purchase orders from ``Extract_En_cours.xlsx``;
* simulated stock/order consumption produced by a run;
* observed business KPI for immobilized component stock.

It is intentionally a post-run audit. It does not tune the simulation.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import openpyxl

from etudecas.simulation.analysis.component_immobilized_stock import (
    ProductScope,
    build_unit_values,
    discover_product_scopes,
    parse_float,
    read_json,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
SIM_START_DATE = date(2025, 1, 1)

PRODUCT_WORKBOOKS = {
    "268091": SOURCE_DIR / "268091.xlsx",
    "268967": SOURCE_DIR / "268967.xlsx",
    "773474": SOURCE_DIR / "773474.xlsx",
}

PRODUCT_OBSERVED_COMPONENT_STOCK = {
    "268091": "Stock_Composants*_Cos.csv",
    "268967": "Stock_Composants*_Pharma.csv",
}


def norm_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() and len(text) < 6 else text


def to_item(value: Any) -> str:
    code = norm_code(value)
    return f"item:{code}" if code else ""


def norm_uom(value: Any) -> str:
    text = str(value or "").strip().upper().replace(".", "")
    if text in {"ZUN", "UN", "UNIT", "UNITE", "UNITES"}:
        return "UN"
    if text in {"G", "GR", "GRAMME", "GRAMMES"}:
        return "G"
    if text in {"KG", "KILO", "KILOGRAMME", "KILOGRAMMES"}:
        return "KG"
    if text in {"M", "ML", "METRE", "METRES", "METER", "METERS"}:
        return "M"
    return text


def convert_qty(qty: float, from_uom: Any, to_uom: Any) -> float | None:
    src = norm_uom(from_uom)
    dst = norm_uom(to_uom)
    if not src or not dst or src == dst:
        return qty
    mass_to_g = {"G": 1.0, "KG": 1000.0}
    if src in mass_to_g and dst in mass_to_g:
        return qty * mass_to_g[src] / mass_to_g[dst]
    return None


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


def row_get(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    lowered = {key.lower(): key for key in row}
    for name in names:
        key = lowered.get(name.lower())
        if key:
            return row.get(key)
    return None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
        return list(csv.DictReader(handle, dialect=dialect))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], *, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": float(len(values)),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def choose_scope(graph: dict[str, Any], product_code: str) -> ProductScope:
    product_item = f"item:{norm_code(product_code)}"
    scopes = [scope for scope in discover_product_scopes(graph) if scope.product_item == product_item]
    if not scopes:
        raise ValueError(f"No product scope found for {product_item}")
    return scopes[0]


def read_observed_component_stock(product_code: str) -> list[dict[str, Any]]:
    pattern = PRODUCT_OBSERVED_COMPONENT_STOCK.get(norm_code(product_code))
    if not pattern:
        return []
    matches = sorted(SOURCE_DIR.glob(pattern))
    if not matches:
        return []
    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(matches[0]):
        value_key = next((key for key in row if "valeur" in key.lower() or "stock" in key.lower()), "")
        date_key = next((key for key in row if "date" in key.lower()), "")
        if not value_key:
            continue
        snapshot_date: date | None = None
        if date_key and row.get(date_key):
            try:
                snapshot_date = datetime.fromisoformat(str(row[date_key])).date()
            except ValueError:
                snapshot_date = None
        rows.append(
            {
                "date": snapshot_date.isoformat() if snapshot_date else "",
                "day": (snapshot_date - SIM_START_DATE).days if snapshot_date else "",
                "observed_value_eur": parse_float(row.get(value_key)),
            }
        )
    return rows


def source_component_stock(
    *,
    scope: ProductScope,
    unit_values: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = workbook_rows(SOURCE_DIR / "Extract_Données_Complémentaires.xlsx", "Stocks")
    out: list[dict[str, Any]] = []
    division = scope.factory.replace("M-", "").replace("SDC-", "").replace("DC-", "")
    for row in rows:
        if str(row_get(row, "Division") or "").strip() != division:
            continue
        item_id = to_item(row_get(row, "NumÃ©ro d'article", "Numéro d'article"))
        if item_id not in scope.component_items:
            continue
        qty = parse_float(row_get(row, "Stock Total"))
        uom = norm_uom(row_get(row, "UnitÃ© de quantitÃ© de base", "Unité de quantité de base"))
        unit_info = unit_values.get((scope.factory, item_id), {})
        price_uom = norm_uom(unit_info.get("uom") or uom)
        priced_qty = convert_qty(qty, uom, price_uom)
        unit_value = unit_info.get("unit_value_eur")
        value = priced_qty * float(unit_value) if priced_qty is not None and unit_value is not None else None
        out.append(
            {
                "node_id": scope.factory,
                "item_id": item_id,
                "source_stock_qty": qty,
                "source_uom": uom,
                "priced_qty": priced_qty,
                "price_uom": price_uom,
                "unit_value_eur": unit_value,
                "source_stock_value_eur": value,
                "value_source": unit_info.get("source", ""),
            }
        )
    return sorted(out, key=lambda row: row["item_id"])


def source_open_orders(scope: ProductScope) -> list[dict[str, Any]]:
    rows = workbook_rows(SOURCE_DIR / "Extract_En_cours.xlsx", "Sheet1")
    division = scope.factory.replace("M-", "").replace("SDC-", "").replace("DC-", "")
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row_get(row, "Division") or "").strip() != division:
            continue
        item_id = to_item(row_get(row, "NumÃ©ro d'article", "Numéro d'article"))
        planning = str(row_get(row, "ElÃ©ment de planification", "Elément de planification") or "").strip()
        planning_key = planning.upper().replace(" ", "")
        if item_id == scope.product_item and planning_key == "O.PROC":
            order_type = "production_open_order"
        elif item_id in scope.component_items and planning_key in {"AVICDE", "ECHCDE"}:
            order_type = "purchase_open_order"
        else:
            continue
        delivery_date = row_get(row, "Date de livraison")
        entry_date = row_get(row, "Date entrÃ©e", "Date entrée")
        delivery_day = (delivery_date.date() - SIM_START_DATE).days if isinstance(delivery_date, datetime) else ""
        entry_day = (entry_date.date() - SIM_START_DATE).days if isinstance(entry_date, datetime) else ""
        out.append(
            {
                "source_row": row.get("_row"),
                "order_type": order_type,
                "planning_element": planning,
                "node_id": scope.factory,
                "item_id": item_id,
                "supplier": row_get(row, "NumÃ©ro de compte fournisseur", "Numéro de compte fournisseur") or "",
                "quantity": parse_float(row_get(row, "QuantitÃ©", "Quantité")),
                "uom": norm_uom(row_get(row, "UnitÃ© de quantitÃ© de base", "Unité de quantité de base")),
                "delivery_day": delivery_day,
                "entry_day": entry_day,
                "delivery_date": delivery_date.isoformat() if isinstance(delivery_date, datetime) else delivery_date,
                "entry_date": entry_date.isoformat() if isinstance(entry_date, datetime) else entry_date,
            }
        )
    return sorted(out, key=lambda row: (row["order_type"], row["item_id"], row["delivery_day"], row["source_row"]))


def simulated_opening_component_stock(
    *,
    run_dir: Path,
    scope: ProductScope,
    unit_values: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    path = run_dir / "data" / "initialization_observed_stock.csv"
    rows = read_csv_rows(path) if path.exists() else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("node_id") != scope.factory or row.get("item_id") not in scope.component_items:
            continue
        item_id = str(row.get("item_id"))
        qty = parse_float(row.get("opening_stock_qty"))
        unit_info = unit_values.get((scope.factory, item_id), {})
        unit_value = unit_info.get("unit_value_eur")
        value = qty * float(unit_value) if unit_value is not None else None
        out.append(
            {
                "node_id": scope.factory,
                "item_id": item_id,
                "sim_opening_stock_qty": qty,
                "unit_value_eur": unit_value,
                "sim_opening_stock_value_eur": value,
                "value_source": unit_info.get("source", ""),
            }
        )
    return sorted(out, key=lambda row: row["item_id"])


def simulated_day0_end_component_stock(
    *,
    run_dir: Path,
    scope: ProductScope,
    unit_values: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    path = run_dir / "data" / "production_input_stocks_daily.csv"
    rows = read_csv_rows(path) if path.exists() else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if int(parse_float(row.get("day"))) != 0:
            continue
        if row.get("node_id") != scope.factory or row.get("item_id") not in scope.component_items:
            continue
        item_id = str(row.get("item_id"))
        qty = parse_float(row.get("stock_end_of_day"))
        unit_info = unit_values.get((scope.factory, item_id), {})
        unit_value = unit_info.get("unit_value_eur")
        out[item_id] = {
            "sim_day0_end_stock_qty": qty,
            "sim_day0_end_stock_value_eur": qty * float(unit_value) if unit_value is not None else None,
        }
    return out


def simulated_opening_production_consumption(run_dir: Path, scope: ProductScope) -> list[dict[str, Any]]:
    path = run_dir / "data" / "opening_production_order_component_consumption.csv"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(path):
        if row.get("node_id") == scope.factory and row.get("output_item_id") == scope.product_item:
            rows.append(
                {
                    "issue_day": int(parse_float(row.get("issue_day") or row.get("day"))),
                    "receipt_day": row.get("receipt_day", ""),
                    "component_item_id": row.get("component_item_id", ""),
                    "bom_issue_mode": row.get("bom_issue_mode", ""),
                    "opening_production_qty": parse_float(row.get("opening_production_qty")),
                    "required_component_qty": parse_float(row.get("required_component_qty")),
                    "consumed_from_stock_qty": parse_float(row.get("consumed_from_stock_qty")),
                    "assumed_initial_wip_qty": parse_float(row.get("assumed_initial_wip_qty")),
                    "shortage_assumed_wip_or_source_gap_qty": parse_float(
                        row.get("shortage_assumed_wip_or_source_gap_qty")
                    ),
                    "source_id": row.get("source_id", ""),
                }
            )
    return rows


def simulated_open_orders(run_dir: Path, scope: ProductScope) -> list[dict[str, Any]]:
    path = run_dir / "data" / "mrp_orders_daily.csv"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for row in read_csv_rows(path):
        item_id = row.get("item_id", "")
        order_type = row.get("order_type", "")
        if row.get("node_id") != scope.factory:
            continue
        if not (
            item_id == scope.product_item and order_type == "opening_production_order"
            or item_id in scope.component_items and order_type == "opening_purchase_order"
        ):
            continue
        rows.append(
            {
                "order_type": order_type,
                "item_id": item_id,
                "release_qty": parse_float(row.get("release_qty")),
                "release_day": int(parse_float(row.get("release_day"))),
                "arrival_day": int(parse_float(row.get("arrival_day"))),
                "actual_receipt_day": row.get("actual_receipt_day", ""),
                "src_node_id": row.get("src_node_id", ""),
                "edge_id": row.get("edge_id", ""),
            }
        )
    return rows


def latest_policy(run_dir: Path) -> dict[str, Any]:
    candidates = [
        run_dir / "summaries" / "first_simulation_summary.json",
        run_dir / "summary" / "first_simulation_summary.json",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return ((data.get("policy") or {}).get("initialization_policy") or {})


def money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.0f} EUR".replace(",", " ")


def build_report(run_dir: Path, graph_path: Path, product_code: str, output_dir: Path) -> dict[str, Any]:
    graph = read_json(graph_path)
    scope = choose_scope(graph, product_code)
    unit_values = build_unit_values(graph)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_stock = source_component_stock(scope=scope, unit_values=unit_values)
    sim_stock = simulated_opening_component_stock(run_dir=run_dir, scope=scope, unit_values=unit_values)
    sim_day0_end_by_item = simulated_day0_end_component_stock(run_dir=run_dir, scope=scope, unit_values=unit_values)
    source_orders = source_open_orders(scope)
    sim_orders = simulated_open_orders(run_dir, scope)
    consumption_rows = simulated_opening_production_consumption(run_dir, scope)
    observed_rows = read_observed_component_stock(product_code)

    sim_by_item = {row["item_id"]: row for row in sim_stock}
    alignment_rows: list[dict[str, Any]] = []
    for row in source_stock:
        sim_row = sim_by_item.get(row["item_id"], {})
        source_value = row.get("source_stock_value_eur")
        sim_value = sim_row.get("sim_opening_stock_value_eur")
        sim_day0_end = sim_day0_end_by_item.get(row["item_id"], {})
        alignment_rows.append(
            {
                **row,
                "sim_opening_stock_qty": sim_row.get("sim_opening_stock_qty", ""),
                "sim_opening_stock_value_eur": sim_value,
                "sim_day0_end_stock_qty": sim_day0_end.get("sim_day0_end_stock_qty", ""),
                "sim_day0_end_stock_value_eur": sim_day0_end.get("sim_day0_end_stock_value_eur", ""),
                "value_delta_eur": (sim_value - source_value)
                if isinstance(source_value, (int, float)) and isinstance(sim_value, (int, float))
                else "",
            }
        )

    source_stock_value = sum(float(row["source_stock_value_eur"]) for row in source_stock if row.get("source_stock_value_eur") is not None)
    sim_stock_value = sum(float(row["sim_opening_stock_value_eur"]) for row in sim_stock if row.get("sim_opening_stock_value_eur") is not None)
    sim_day0_end_stock_value = sum(
        float(row["sim_day0_end_stock_value_eur"])
        for row in sim_day0_end_by_item.values()
        if row.get("sim_day0_end_stock_value_eur") is not None
    )
    source_oproc_qty = sum(row["quantity"] for row in source_orders if row["order_type"] == "production_open_order")
    sim_oproc_qty = sum(row["release_qty"] for row in sim_orders if row["order_type"] == "opening_production_order")
    source_purchase_qty_count = len([row for row in source_orders if row["order_type"] == "purchase_open_order"])
    sim_purchase_qty_count = len([row for row in sim_orders if row["order_type"] == "opening_purchase_order"])
    shortage_by_item: dict[str, float] = defaultdict(float)
    consumed_by_item: dict[str, float] = defaultdict(float)
    assumed_wip_by_item: dict[str, float] = defaultdict(float)
    for row in consumption_rows:
        item_id = row["component_item_id"]
        shortage_by_item[item_id] += row["shortage_assumed_wip_or_source_gap_qty"]
        consumed_by_item[item_id] += row["consumed_from_stock_qty"]
        assumed_wip_by_item[item_id] += row["assumed_initial_wip_qty"]

    observed_values = [float(row["observed_value_eur"]) for row in observed_rows]
    observed_stats = stats(observed_values)
    policy = latest_policy(run_dir)

    write_csv(
        output_dir / "component_stock_alignment.csv",
        alignment_rows,
        columns=[
            "node_id",
            "item_id",
            "source_stock_qty",
            "source_uom",
            "priced_qty",
            "price_uom",
            "unit_value_eur",
            "source_stock_value_eur",
            "sim_opening_stock_qty",
            "sim_opening_stock_value_eur",
            "sim_day0_end_stock_qty",
            "sim_day0_end_stock_value_eur",
            "value_delta_eur",
            "value_source",
        ],
    )
    write_csv(
        output_dir / "source_open_orders.csv",
        source_orders,
        columns=[
            "source_row",
            "order_type",
            "planning_element",
            "node_id",
            "item_id",
            "supplier",
            "quantity",
            "uom",
            "delivery_day",
            "entry_day",
            "delivery_date",
            "entry_date",
        ],
    )
    write_csv(
        output_dir / "opening_production_consumption_summary.csv",
        [
            {
                "component_item_id": item_id,
                "consumed_from_stock_qty": consumed_by_item.get(item_id, 0.0),
                "assumed_initial_wip_qty": assumed_wip_by_item.get(item_id, 0.0),
                "shortage_assumed_wip_or_source_gap_qty": shortage_by_item.get(item_id, 0.0),
            }
            for item_id in sorted(set(consumed_by_item) | set(assumed_wip_by_item) | set(shortage_by_item))
        ],
        columns=[
            "component_item_id",
            "consumed_from_stock_qty",
            "assumed_initial_wip_qty",
            "shortage_assumed_wip_or_source_gap_qty",
        ],
    )

    top_shortages = sorted(shortage_by_item.items(), key=lambda item: item[1], reverse=True)[:8]
    summary = {
        "run_dir": str(run_dir),
        "graph_path": str(graph_path),
        "product_code": norm_code(product_code),
        "factory": scope.factory,
        "component_count": len(scope.component_items),
        "opening_production_order_bom_issue_mode": policy.get("opening_production_order_bom_issue_mode", ""),
        "source_component_stock_value_eur": source_stock_value,
        "sim_opening_component_stock_value_eur": sim_stock_value,
        "sim_day0_end_component_stock_value_eur": sim_day0_end_stock_value,
        "component_stock_value_delta_eur": sim_stock_value - source_stock_value,
        "source_open_production_qty": source_oproc_qty,
        "sim_opening_production_qty": sim_oproc_qty,
        "source_purchase_order_component_line_count": source_purchase_qty_count,
        "sim_purchase_order_component_line_count": sim_purchase_qty_count,
        "observed_immobilized_component_stock": observed_stats,
        "top_opening_production_shortages": [
            {"component_item_id": item_id, "shortage_qty": qty} for item_id, qty in top_shortages if qty > 1e-9
        ],
    }
    (output_dir / "source_truth_alignment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = [
        f"# Source-truth alignment - {norm_code(product_code)}",
        "",
        f"- Run: `{run_dir}`",
        f"- Graphe: `{graph_path}`",
        f"- Site produit: `{scope.factory}`",
        f"- Composants BOM: {len(scope.component_items)}",
        f"- Mode issue O.Proc: `{summary['opening_production_order_bom_issue_mode'] or 'n/a'}`",
        "",
        "## Stock composants",
        "",
        f"- Stock physique source `Stocks_MRP` valorise: {money(source_stock_value)}",
        f"- Stock composant simule en entree J0 valorise: {money(sim_stock_value)}",
        f"- Stock composant simule fin J0 valorise: {money(sim_day0_end_stock_value)}",
        f"- Ecart sim - source: {money(sim_stock_value - source_stock_value)}",
        "",
        "Lecture: ce stock est le stock physique composant. Ce n'est pas encore le stock immobilise metier, qui est un KPI agregé et potentiellement net d'une couverture utile.",
        "",
        "## Encours source",
        "",
        f"- O.Proc source produit fini: {len([r for r in source_orders if r['order_type'] == 'production_open_order'])} lignes / {source_oproc_qty:,.1f} unites".replace(",", " "),
        f"- O.Proc simulees: {len([r for r in sim_orders if r['order_type'] == 'opening_production_order'])} lignes / {sim_oproc_qty:,.1f} unites".replace(",", " "),
        f"- Commandes achats composants source: {source_purchase_qty_count} lignes",
        f"- Commandes achats composants simulees: {sim_purchase_qty_count} lignes",
        "",
        "## Consommation composants des O.Proc",
        "",
    ]
    if top_shortages:
        md.append("Top composants avec manque simule apres consommation O.Proc:")
        for item_id, qty in top_shortages:
            if qty > 1e-9:
                md.append(f"- `{item_id}`: {qty:,.1f}".replace(",", " "))
    else:
        md.append("Aucun manque composant O.Proc mesure.")
    md.extend(
        [
            "",
            "## KPI reel stock immobilise",
            "",
            f"- Observations: {int(observed_stats['count'])}",
            f"- Moyenne: {money(observed_stats['mean'])}",
            f"- Mediane: {money(observed_stats['median'])}",
            f"- Min / max: {money(observed_stats['min'])} / {money(observed_stats['max'])}",
            "",
            "Fichiers generes:",
            "",
            "- `component_stock_alignment.csv`",
            "- `source_open_orders.csv`",
            "- `opening_production_consumption_summary.csv`",
            "- `source_truth_alignment_summary.json`",
        ]
    )
    (output_dir / "source_truth_alignment_report.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--product-code", default="268091")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    output_dir = args.output_dir or args.run_dir / "reports" / f"source_truth_alignment_{norm_code(args.product_code)}"
    summary = build_report(args.run_dir, args.graph, args.product_code, output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
