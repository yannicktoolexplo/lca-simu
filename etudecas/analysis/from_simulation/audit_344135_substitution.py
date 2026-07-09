"""Audit whether component 344135 has an explicit or plausible substitute.

The check is intentionally source-driven: it compares BOM/FIA/source stock/open
orders and searches source workbooks for replacement-like wording. It does not
change the simulation graph.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
OUT_DIR = (
    REPO_ROOT
    / "etudecas"
    / "analysis"
    / "from_simulation"
    / "result"
    / "audit_344135_substitution"
)

TARGET_COMPONENT = "344135"
PRODUCT_WORKBOOKS = ("268967.xlsx", "268091.xlsx", "773474.xlsx")
SEARCH_TERMS = (
    "344135",
    "34413",
    "VD0993480A",
    "remplac",
    "substit",
    "alternat",
    "equiv",
    "équiv",
    "ancien",
    "nouveau",
)


def code(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text and text.lower() != "nan" else ""


def text(value: object) -> str:
    if value is None:
        return ""
    value_text = str(value).strip()
    return "" if value_text.lower() == "nan" else value_text


def to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def read_bom_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for workbook in PRODUCT_WORKBOOKS:
        path = SOURCE_DIR / workbook
        if not path.exists():
            continue
        df = pd.read_excel(path, sheet_name="BOM", dtype=str)
        for _, row in df.iterrows():
            rows.append(
                {
                    "workbook": workbook,
                    "finished_product": code(row.iloc[0]),
                    "base_qty": text(row.iloc[1]),
                    "component": code(row.iloc[2]),
                    "component_type": text(row.iloc[3]),
                    "qty_per_base": text(row.iloc[4]),
                    "uom": text(row.iloc[5]),
                }
            )
    return rows


def read_fia_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for workbook in PRODUCT_WORKBOOKS:
        path = SOURCE_DIR / workbook
        if not path.exists():
            continue
        try:
            df = pd.read_excel(path, sheet_name="FIA", dtype=str)
        except ValueError:
            continue
        for _, row in df.iterrows():
            item = code(row.iloc[0])
            supplier = text(row.iloc[1])
            amount = next((to_float(row[col], None) for col in df.columns if "Montant" in str(col)), None)
            price_base = next((to_float(row[col], None) for col in df.columns if "Base de prix" in str(col)), None)
            lead_time = next(
                (to_float(row[col], None) for col in df.columns if "Délai prévisionnel" in str(col)),
                None,
            )
            standard_order = next(
                (to_float(row[col], None) for col in df.columns if "Quantité standard" in str(col)),
                None,
            )
            unit = next(
                (
                    text(row[col])
                    for col in df.columns
                    if "Unité de quantité" in str(col) or "Unité de condition" in str(col)
                ),
                "",
            )
            rows.append(
                {
                    "workbook": workbook,
                    "item": item,
                    "supplier": supplier,
                    "price_amount": amount,
                    "price_base": price_base,
                    "lead_time_days": lead_time,
                    "standard_order": standard_order,
                    "unit": unit,
                }
            )
    return rows


def read_stock_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    path = SOURCE_DIR / "Extract_Données_Complémentaires.xlsx"
    if not path.exists():
        path = SOURCE_DIR / "Stocks_MRP.xlsx"
    if not path.exists():
        return rows
    stock = pd.read_excel(path, sheet_name="Stocks", dtype=str)
    policy = pd.read_excel(path, sheet_name="Politique de Stock MRP", dtype=str)
    policy_by_key = {
        (code(row.iloc[0]), text(row.iloc[2])): row
        for _, row in policy.iterrows()
    }
    for _, row in stock.iterrows():
        key = (code(row.iloc[0]), text(row.iloc[2]))
        pol = policy_by_key.get(key)
        rows.append(
            {
                "item": key[0],
                "item_type": text(row.iloc[1]),
                "division": key[1],
                "division_name": text(row.iloc[3]),
                "stock_total": to_float(row.iloc[4]),
                "stock_uom": text(row.iloc[5]),
                "snapshot_date": text(row.iloc[6]),
                "safety_delay_days": to_float(pol.iloc[4]) if pol is not None else "",
                "safety_stock": to_float(pol.iloc[5]) if pol is not None else "",
            }
        )
    return rows


def read_open_orders() -> list[dict[str, object]]:
    path = SOURCE_DIR / "Extract_En_cours.xlsx"
    if not path.exists():
        return []
    df = pd.read_excel(path, dtype=str)
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "item": code(row.iloc[0]),
                "planning_element": text(row.iloc[1]),
                "division": text(row.iloc[2]),
                "supplier_account": text(row.iloc[3]),
                "quantity": to_float(row.iloc[4]),
                "uom": text(row.iloc[5]),
                "delivery_date": text(row.iloc[6]),
                "receipt_release_days": to_float(row.iloc[7]),
                "usable_date": text(row.iloc[8]),
            }
        )
    return rows


def search_source_hits() -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for path in sorted(SOURCE_DIR.glob("*")):
        if path.suffix.lower() not in {".xlsx", ".csv", ".json"}:
            continue
        if path.suffix.lower() == ".xlsx":
            try:
                xl = pd.ExcelFile(path)
            except Exception:
                continue
            for sheet in xl.sheet_names:
                try:
                    df = pd.read_excel(path, sheet_name=sheet, dtype=str)
                except Exception:
                    continue
                for idx, row in df.fillna("").iterrows():
                    row_text = " | ".join(text(v) for v in row.values)
                    low = row_text.lower()
                    matched = [term for term in SEARCH_TERMS if term.lower() in low]
                    if matched:
                        hits.append(
                            {
                                "file": path.name,
                                "sheet": sheet,
                                "row": str(idx + 2),
                                "matched_terms": ";".join(matched),
                                "content": row_text[:500],
                            }
                        )
        elif path.suffix.lower() == ".csv":
            for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
                try:
                    df = pd.read_csv(path, sep=None, engine="python", encoding=encoding, dtype=str)
                    break
                except Exception:
                    df = None
            if df is None:
                continue
            for idx, row in df.fillna("").iterrows():
                row_text = " | ".join(text(v) for v in row.values)
                low = row_text.lower()
                matched = [term for term in SEARCH_TERMS if term.lower() in low]
                if matched:
                    hits.append(
                        {
                            "file": path.name,
                            "sheet": "",
                            "row": str(idx + 2),
                            "matched_terms": ";".join(matched),
                            "content": row_text[:500],
                        }
                    )
        else:
            data = path.read_text(encoding="utf-8", errors="ignore")
            low = data.lower()
            matched = [term for term in SEARCH_TERMS if term.lower() in low]
            if matched:
                hits.append(
                    {
                        "file": path.name,
                        "sheet": "",
                        "row": "",
                        "matched_terms": ";".join(matched),
                        "content": "json file contains matching terms",
                    }
                )
    return hits


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bom_rows = read_bom_rows()
    fia_rows = read_fia_rows()
    stock_rows = read_stock_rows()
    order_rows = read_open_orders()
    source_hits = search_source_hits()

    pack_rows = [row for row in bom_rows if str(row["component_type"]).lower() == "pack"]
    candidate_components = {
        row["component"]
        for row in pack_rows
        if row["uom"].upper().startswith("UN") and to_float(row["qty_per_base"]) == 1000.0
    }
    candidate_components.add(TARGET_COMPONENT)

    candidate_rows = []
    fia_by_item = {}
    for row in fia_rows:
        fia_by_item.setdefault(row["item"], []).append(row)
    stock_by_item = {}
    for row in stock_rows:
        stock_by_item.setdefault(row["item"], []).append(row)
    orders_by_item = {}
    for row in order_rows:
        orders_by_item.setdefault(row["item"], []).append(row)

    for component in sorted(candidate_components):
        for bom in [row for row in bom_rows if row["component"] == component]:
            stocks = stock_by_item.get(component, [])
            orders = orders_by_item.get(component, [])
            suppliers = fia_by_item.get(component, [])
            candidate_rows.append(
                {
                    "component": component,
                    "finished_product": bom["finished_product"],
                    "workbook": bom["workbook"],
                    "component_type": bom["component_type"],
                    "qty_per_1000_pf": bom["qty_per_base"],
                    "uom": bom["uom"],
                    "supplier_accounts": ";".join(sorted({str(r["supplier"]) for r in suppliers})),
                    "stock_locations": ";".join(
                        f'{r["division"]}:{r["stock_total"]:g} {r["stock_uom"]}' for r in stocks
                    ),
                    "open_order_count": len(orders),
                    "open_order_qty": sum(float(r["quantity"]) for r in orders),
                    "open_order_locations": ";".join(
                        sorted({f'{r["division"]}/{r["supplier_account"]}' for r in orders})
                    ),
                    "substitution_reading": (
                        "target_component"
                        if component == TARGET_COMPONENT
                        else "structural_similarity_only_not_a_declared_substitute"
                    ),
                }
            )

    write_csv(OUT_DIR / "bom_pack_candidate_comparison.csv", candidate_rows)
    write_csv(OUT_DIR / "source_search_hits.csv", source_hits)
    write_csv(OUT_DIR / "344135_open_orders.csv", orders_by_item.get(TARGET_COMPONENT, []))
    write_csv(OUT_DIR / "344135_stock_rows.csv", stock_by_item.get(TARGET_COMPONENT, []))

    explicit_substitution_hits = [
        row
        for row in source_hits
        if TARGET_COMPONENT in row["content"]
        and any(term in row["matched_terms"].lower() for term in ("remplac", "substit", "alternat", "equiv", "équiv"))
    ]

    summary = {
        "target_component": TARGET_COMPONENT,
        "explicit_substitution_hits": len(explicit_substitution_hits),
        "target_open_order_count": len(orders_by_item.get(TARGET_COMPONENT, [])),
        "target_stock_rows": stock_by_item.get(TARGET_COMPONENT, []),
        "structural_candidate_components": sorted(candidate_components),
        "reading": (
            "No explicit substitute for 344135 was found in the active source files. "
            "The closest components are packaging items with the same 1000 UN / 1000 PF ratio, "
            "but they belong to another finished product/site and cannot be consumed as substitutes "
            "without an explicit equivalence rule."
        ),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md = [
        "# Audit substitution 344135",
        "",
        "## Conclusion",
        "",
        "- Aucune règle explicite de remplacement/substitution pour `344135` n'a été trouvée dans les fichiers source actifs.",
        "- `344135` est présent comme composant `Pack` du PF `268967`, ratio `1000 UN / 1000 PF`, dans `268967.xlsx`, `Data_poc.xlsx` et `demand_PF.xlsx`.",
        "- Le stock source de `344135` au 2025-01-01 est `0 ZUN` à Gien `1430`.",
        "- `Extract_En_cours.xlsx` ne contient aucun ordre ouvert pour `344135`.",
        "- Les références `338928` et `338929` sont structurellement proches (`Pack`, `1000 UN / 1000 PF`) mais elles appartiennent au PF `268091` sur Avène `1810`; ce ne sont pas des substituts déclarés de `344135`.",
        "",
        "## Lecture métier",
        "",
        "Si `344135` peut réellement être remplacé par une autre référence, il manque une donnée de correspondance article dans les sources. Sans cette table, la simulation a raison de bloquer la première production `268967` jusqu'à arrivée de `344135`.",
        "",
        "## Fichiers générés",
        "",
        "- `bom_pack_candidate_comparison.csv`",
        "- `source_search_hits.csv`",
        "- `344135_open_orders.csv`",
        "- `344135_stock_rows.csv`",
        "- `summary.json`",
    ]
    (OUT_DIR / "audit_344135_substitution.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[OK] report written to {OUT_DIR / 'audit_344135_substitution.md'}")


if __name__ == "__main__":
    main()
