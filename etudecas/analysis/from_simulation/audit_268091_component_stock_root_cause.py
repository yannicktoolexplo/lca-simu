"""Root-cause audit for the 268091 component stock gap.

The goal is deliberately narrow: explain why the simulated component stock
around PF 268091 differs from the observed Cos immobilized-stock KPI.
It does not recalibrate the model; it reconciles source stock, opening orders,
and simulation flows in one readable report.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
DEFAULT_RUN_DIR = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "result"
    / "_experiments"
    / "stock_target_268091_source_truth"
    / "5y"
    / "source_truth_wip_pipeline_v2"
)
PRODUCT_CODE = "268091"
PRODUCT_ITEM = "item:268091"
START_DATE = date(2025, 1, 1)


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def read_csv(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "cp1252", "utf-8"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle, delimiter=delimiter))
        except UnicodeDecodeError:
            continue
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one source file for {pattern}, found {matches}")
    return matches[0]


def euro(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def qty(value: float) -> str:
    return f"{value:,.1f}".replace(",", " ")


def real_pharma_kpi() -> dict[str, float]:
    rows = read_csv(source_file("Stock_Composants*Cos.csv"), delimiter=";")
    values = [parse_float(row.get("Sum_Valeur totale du stock")) for row in rows]
    return {
        "count": float(len(values)),
        "mean": sum(values) / len(values) if values else 0.0,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
        "first": values[0] if values else 0.0,
    }


def comparison_metrics(run_dir: Path) -> dict[str, str]:
    path = run_dir / "reports" / "source_truth_component_stock" / "component_immobilized_stock_comparison.csv"
    for row in read_csv(path):
        if (
            row.get("product_code") == PRODUCT_CODE
            and row.get("alignment") == "previous_day"
            and row.get("metric_id") == "stock_total_value_without_internal_rollup"
        ):
            return row
    raise RuntimeError(f"Missing comparison row in {path}")


def component_contributors(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "reports" / "source_truth_component_stock" / "component_immobilized_stock_component_contributors.csv"
    rows: list[dict[str, Any]] = []
    for row in read_csv(path):
        if row.get("product_code") != PRODUCT_CODE or row.get("alignment") != "previous_day":
            continue
        rows.append(
            {
                "item": str(row.get("component_item_id") or "").replace("item:", ""),
                "mean_stock_value_eur": parse_float(row.get("mean_stock_value_eur")),
                "mean_stock_qty": parse_float(row.get("mean_stock_qty")),
                "unit_value_eur": parse_float(row.get("unit_value_eur")),
                "share_pct": parse_float(row.get("share_of_simulated_stock_pct")),
            }
        )
    return sorted(rows, key=lambda row: row["mean_stock_value_eur"], reverse=True)


def component_flows(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / "reports" / "source_truth_component_stock" / "component_immobilized_stock_component_flows.csv"
    flows: dict[str, dict[str, Any]] = {}
    for row in read_csv(path):
        if row.get("product_code") != PRODUCT_CODE:
            continue
        item = str(row.get("component_item_id") or "").replace("item:", "")
        flows[item] = {
            "start_stock_qty": parse_float(row.get("start_stock_qty")),
            "end_stock_qty": parse_float(row.get("end_stock_qty")),
            "arrived_qty_total": parse_float(row.get("arrived_qty_total")),
            "approx_consumed_qty": parse_float(row.get("approx_consumed_qty")),
            "opening_order_qty": parse_float(row.get("opening_order_qty")),
            "generated_mrp_qty": parse_float(row.get("generated_mrp_qty")),
            "first_arrival_day": row.get("first_arrival_day") or "",
            "last_arrival_day": row.get("last_arrival_day") or "",
        }
    return flows


def day0_thresholds(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "data" / "component_immobilized_stock_daily.csv"
    rows: list[dict[str, Any]] = []
    for row in read_csv(path):
        if row.get("product_code") != PRODUCT_CODE or row.get("day") != "0":
            continue
        rows.append(
            {
                "mode": row.get("threshold_mode") or "",
                "stock": parse_float(row.get("stock_value_eur")),
                "useful": parse_float(row.get("useful_stock_value_eur")),
                "excess": parse_float(row.get("immobilized_stock_value_eur")),
            }
        )
    return rows


def opening_orders(run_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    path = run_dir / "reports" / "source_truth_alignment_268091" / "source_open_orders.csv"
    rows = read_csv(path)
    purchase = [row for row in rows if row.get("order_type") == "purchase_open_order"]
    production = [row for row in rows if row.get("order_type") == "production_open_order"]
    return purchase, production


def opening_production_consumption(run_dir: Path) -> dict[str, float]:
    path = run_dir / "data" / "opening_production_order_component_consumption.csv"
    rows = [row for row in read_csv(path) if row.get("output_item_id") == PRODUCT_ITEM]
    return {
        "rows": float(len(rows)),
        "consumed_from_stock": sum(parse_float(row.get("consumed_from_stock_qty")) for row in rows),
        "assumed_initial_wip": sum(parse_float(row.get("assumed_initial_wip_qty")) for row in rows),
        "shortage": sum(parse_float(row.get("shortage_assumed_wip_or_source_gap_qty")) for row in rows),
        "issue_days": float(len({row.get("issue_day") for row in rows})),
    }


def fia_suppliers_by_item() -> dict[str, set[str]]:
    path = SOURCE_DIR / "268091.xlsx"
    fia = pd.read_excel(path, sheet_name="FIA")

    def norm_item(value: Any) -> str:
        try:
            return str(int(float(value))).zfill(6)
        except (TypeError, ValueError):
            return str(value).strip()

    suppliers: dict[str, set[str]] = {}
    for _, row in fia.iterrows():
        item = norm_item(row.iloc[0])
        supplier = str(row.iloc[1]).strip()
        if item and supplier and supplier.lower() != "nan":
            suppliers.setdefault(item, set()).add(supplier)
    return suppliers


def write_report(run_dir: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    observed = real_pharma_kpi()
    comparison = comparison_metrics(run_dir)
    contributors = component_contributors(run_dir)
    flows = component_flows(run_dir)
    day0 = day0_thresholds(run_dir)
    purchase_orders, production_orders = opening_orders(run_dir)
    oproc = opening_production_consumption(run_dir)
    fia_suppliers = fia_suppliers_by_item()

    purchase_by_item: dict[str, dict[str, Any]] = {}
    for row in purchase_orders:
        item = str(row.get("item_id") or "").replace("item:", "")
        bucket = purchase_by_item.setdefault(
            item,
            {
                "rows": 0,
                "quantity": 0.0,
                "suppliers": set(),
                "first_day": None,
                "last_day": None,
            },
        )
        bucket["rows"] += 1
        bucket["quantity"] += parse_float(row.get("quantity"))
        if row.get("supplier"):
            bucket["suppliers"].add(str(row.get("supplier")))
        day = int(parse_float(row.get("entry_day"), -1))
        bucket["first_day"] = day if bucket["first_day"] is None else min(bucket["first_day"], day)
        bucket["last_day"] = day if bucket["last_day"] is None else max(bucket["last_day"], day)

    top_rows = contributors[:10]
    top3_value = sum(row["mean_stock_value_eur"] for row in contributors[:3])
    sim_mean = parse_float(comparison.get("simulated_snapshot_mean_eur"))
    observed_mean = observed["mean"]

    lines: list[str] = [
        "# Cause racine - stock composants 268091",
        "",
        "## Conclusion courte",
        "",
        (
            f"- Le KPI reel Cos vaut en moyenne {euro(observed_mean)} "
            f"sur {int(observed['count'])} photos 2025."
        ),
        (
            f"- La simulation comparee en stock composant physique vaut {euro(sim_mean)}, "
            f"soit un ecart de {euro(sim_mean - observed_mean)}."
        ),
        (
            f"- Les 3 composants `049371`, `002612`, `007923` portent deja "
            f"{euro(top3_value)} de stock simule moyen, donc plus que le KPI reel complet."
        ),
        "- Les O.Proc ne sont pas la cause principale: ils sont traites comme encours deja engages, pas comme une nouvelle consommation de stock libre.",
        "- La cause la plus probable est un ecart de perimetre: la simulation valorise le stock physique MRP des composants du BOM, alors que le CSV reel est un KPI agrege d'immobilise sans detail article/statut.",
        "",
        "## Verification O.Proc",
        "",
        f"- Lignes composant O.Proc tracees: {int(oproc['rows'])}.",
        f"- Consommation de stock libre a J0: {qty(oproc['consumed_from_stock'])}.",
        f"- Composants consideres deja engages en WIP initial: {qty(oproc['assumed_initial_wip'])}.",
        f"- Manque O.Proc: {qty(oproc['shortage'])}.",
        f"- Ordres de fabrication source: {len(production_orders)} lignes.",
        "",
        "## Stock J0 selon plusieurs lectures",
        "",
        "| Lecture simulation J0 | Stock physique | Stock utile | Excedent / immobilise calcule |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in sorted(day0, key=lambda r: r["mode"]):
        lines.append(
            f"| {row['mode']} | {euro(row['stock'])} | {euro(row['useful'])} | {euro(row['excess'])} |"
        )

    lines += [
        "",
        "## Top composants expliquant l'ecart",
        "",
        "| Item | Valeur moyenne simulee | Part | Stock debut | Commandes ouvertes | Consommation approx. | MRP genere | Lecture |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in top_rows:
        flow = flows.get(row["item"], {})
        unit = row["unit_value_eur"]
        open_value = parse_float(flow.get("opening_order_qty")) * unit
        start_value = parse_float(flow.get("start_stock_qty")) * unit
        consumed_value = parse_float(flow.get("approx_consumed_qty")) * unit
        generated_mrp = parse_float(flow.get("generated_mrp_qty"))
        read = "stock source + commandes ouvertes" if open_value > 0 and generated_mrp == 0 else "stock source + MRP"
        if open_value == 0 and generated_mrp == 0:
            read = "stock source seul"
        lines.append(
            "| {item} | {mean} | {share:.1f}% | {start} | {openv} | {consumed} | {mrp} | {read} |".format(
                item=row["item"],
                mean=euro(row["mean_stock_value_eur"]),
                share=row["share_pct"],
                start=euro(start_value),
                openv=euro(open_value),
                consumed=euro(consumed_value),
                mrp=qty(generated_mrp),
                read=read,
            )
        )

    lines += [
        "",
        "## Commandes ouvertes achat principales",
        "",
        "| Item | Lignes | Fournisseurs source | Quantite source | Jours reception |",
        "| --- | ---: | --- | ---: | --- |",
    ]
    for item, bucket in sorted(
        purchase_by_item.items(),
        key=lambda kv: flows.get(kv[0], {}).get("opening_order_qty", 0.0),
        reverse=True,
    )[:10]:
        lines.append(
            "| {item} | {rows} | {suppliers} | {quantity} | J{first} -> J{last} |".format(
                item=item,
                rows=bucket["rows"],
                suppliers=", ".join(sorted(bucket["suppliers"])) or "n/a",
                quantity=qty(bucket["quantity"]),
                first=bucket["first_day"],
                last=bucket["last_day"],
            )
        )

    production_orders_sorted = sorted(production_orders, key=lambda row: parse_float(row.get("entry_day")))
    lines += [
        "",
        "## Ordres de fabrication en cours source",
        "",
        "Ces lignes sont des PF `268091` deja lances au cut-over. Elles entrent comme PF aux dates source; leurs composants ne sont pas retires une deuxieme fois du stock libre.",
        "",
        "| Source row | Quantite PF | Date livraison | Date entree stock | Jour entree |",
        "| ---: | ---: | --- | --- | ---: |",
    ]
    for row in production_orders_sorted[:12]:
        lines.append(
            "| {source_row} | {quantity} | {delivery_date} | {entry_date} | J{entry_day} |".format(
                source_row=row.get("source_row") or "",
                quantity=qty(parse_float(row.get("quantity"))),
                delivery_date=(row.get("delivery_date") or "").split("T")[0],
                entry_date=(row.get("entry_date") or "").split("T")[0],
                entry_day=int(parse_float(row.get("entry_day"))),
            )
        )
    if len(production_orders_sorted) > 12:
        lines.append(f"| ... | {len(production_orders_sorted) - 12} autres lignes | ... | ... | ... |")

    lines += [
        "",
        "## Ecarts source / FIA visibles",
        "",
        "Ces points ne suffisent pas seuls a expliquer tout l'ecart, mais ils montrent que le carnet d'ordres et les voies fournisseur du BOM ne sont pas toujours le meme objet.",
        "",
        "| Item | Fournisseurs commandes ouvertes | Fournisseurs FIA 268091 | Lecture |",
        "| --- | --- | --- | --- |",
    ]
    for item in [row["item"] for row in contributors[:10]]:
        source_suppliers = purchase_by_item.get(item, {}).get("suppliers", set())
        fia_set = fia_suppliers.get(item, set())
        if not source_suppliers and not fia_set:
            continue
        missing = sorted(set(source_suppliers) - set(fia_set))
        if not missing and source_suppliers:
            read = "coherent"
        elif source_suppliers and not fia_set:
            read = "commande ouverte sans voie FIA dans le workbook"
        elif missing:
            read = "fournisseur du carnet absent de la FIA"
        else:
            read = "voie FIA sans commande ouverte source"
        lines.append(
            "| {item} | {source} | {fia} | {read} |".format(
                item=item,
                source=", ".join(sorted(source_suppliers)) or "aucun",
                fia=", ".join(sorted(fia_set)) or "aucun",
                read=read,
            )
        )

    lines += [
        "",
        "## Decision metier",
        "",
        "Pour coller au KPI reel, il ne faut pas calibrer brutalement le stock physique. Il faut d'abord choisir la meme definition que la source finance:",
        "",
        "1. stock physique composant site: tout ce qui est dans `Extract_Données_Complémentaires.xlsx`;",
        "2. stock attribuable au produit 268091: part du stock composant reservee ou statistiquement allouee a ce PF;",
        "3. stock immobilise finance: sous-ensemble du stock juge excedentaire/bloque/non utile selon une regle metier.",
        "",
        "Le fichier reel actuel ne contient que date + valeur. Sans detail article/statut, on ne peut pas verifier si `049371`, `002612` ou `007923` sont inclus dans le KPI reel.",
    ]

    report_path = output_dir / "audit_268091_component_stock_root_cause.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "etudecas" / "analysis" / "from_simulation" / "result" / "audit_268091_component_stock_root_cause",
    )
    args = parser.parse_args()
    report_path = write_report(args.run_dir, args.output_dir)
    print(f"[OK] report={report_path}")


if __name__ == "__main__":
    main()
