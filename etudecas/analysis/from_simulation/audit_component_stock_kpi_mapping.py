"""Audit product/family mapping for component immobilized-stock KPI files.

This script is diagnostic only. It checks whether the aggregate real files
``Stock_Composants_Immobilise_*.csv`` are being compared to the right finished
product/component perimeter before trying to infer an immobilized-stock rule.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = REPO_ROOT / "etudecas" / "data" / "source"
RUN_DIR = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "result"
    / "_experiments"
    / "stock_target_268091_source_truth"
    / "5y"
    / "source_truth_wip_pipeline_v2"
)
OUTPUT_DIR = (
    REPO_ROOT
    / "etudecas"
    / "analysis"
    / "from_simulation"
    / "result"
    / "component_stock_kpi_mapping_audit"
)


PRODUCTS = {
    "268091": {"division": 1810, "workbook": "268091.xlsx"},
    "268967": {"division": 1430, "workbook": "268967.xlsx"},
}


def norm(value: Any) -> str:
    text = str(value)
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    ).lower()


def find_col(df: pd.DataFrame, *needles: str) -> str:
    targets = [norm(needle) for needle in needles]
    matches = []
    for column in df.columns:
        normalized = norm(column)
        if all(target in normalized for target in targets):
            matches.append(column)
    if not matches:
        raise KeyError((needles, list(df.columns)))
    return sorted(matches, key=lambda item: len(str(item)), reverse=True)[0]


def uom_factor(from_uom: Any, to_uom: Any) -> float | None:
    source = norm(from_uom).upper().replace(".", "").strip()
    target = norm(to_uom).upper().replace(".", "").strip()
    aliases = {"UNIT": "UN", "UNITE": "UN", "UNITES": "UN", "ZUN": "UN"}
    source = aliases.get(source, source)
    target = aliases.get(target, target)
    if source == target:
        return 1.0
    if source == "G" and target == "KG":
        return 0.001
    if source == "KG" and target == "G":
        return 1000.0
    return None


def euro(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def product_components(product_code: str) -> set[str]:
    workbook = SOURCE_DIR / PRODUCTS[product_code]["workbook"]
    bom = pd.read_excel(workbook, sheet_name="BOM")
    component_col = find_col(bom, "composante")
    return {str(int(value)).zfill(6) for value in bom[component_col].dropna()}


def source_stock_values(product_code: str) -> pd.DataFrame:
    """Value opening component stock with min/mean/max source purchase prices."""
    product = PRODUCTS[product_code]
    workbook = SOURCE_DIR / product["workbook"]
    components = product_components(product_code)

    stocks = pd.read_excel(SOURCE_DIR / "Extract_Données_Complémentaires.xlsx", sheet_name="Stocks")
    # The source workbook has a stable layout; using positions avoids terminal
    # encoding issues around accented column names.
    stock_item_col = stocks.columns[0]
    stock_division_col = stocks.columns[2]
    stock_qty_col = stocks.columns[4]
    stock_uom_col = stocks.columns[5]
    stocks["item_code"] = stocks[stock_item_col].dropna().astype(int).astype(str).str.zfill(6)
    stocks = stocks[
        (stocks["item_code"].isin(components))
        & (stocks[stock_division_col].astype(int) == int(product["division"]))
    ].copy()

    fia = pd.read_excel(workbook, sheet_name="FIA")
    fia_item_col = fia.columns[0]
    supplier_col = fia.columns[1]
    price_col = fia.columns[2]
    price_base_col = fia.columns[3]
    price_uom_col = fia.columns[-1]
    fia["item_code"] = fia[fia_item_col].dropna().astype(int).astype(str).str.zfill(6)

    rows = []
    for _, stock_row in stocks.iterrows():
        item_code = stock_row["item_code"]
        candidates = []
        for _, price_row in fia[fia["item_code"] == item_code].iterrows():
            factor = uom_factor(stock_row[stock_uom_col], price_row[price_uom_col])
            if factor is None:
                continue
            unit_value = float(price_row[price_col]) / float(price_row[price_base_col]) * factor
            candidates.append((unit_value, str(price_row[supplier_col])))
        if not candidates:
            stats = {"min": 0.0, "mean": 0.0, "max": 0.0}
            suppliers = ""
        else:
            values = [value for value, _supplier in candidates]
            stats = {"min": min(values), "mean": sum(values) / len(values), "max": max(values)}
            suppliers = ",".join(sorted({supplier for _value, supplier in candidates}))
        stock_qty = float(stock_row[stock_qty_col])
        rows.append(
            {
                "product_code": product_code,
                "division": product["division"],
                "item_code": item_code,
                "stock_qty": stock_qty,
                "stock_uom": stock_row[stock_uom_col],
                "suppliers": suppliers,
                **{f"{mode}_value_eur": stock_qty * unit for mode, unit in stats.items()},
            }
        )
    return pd.DataFrame(rows)


def real_snapshots(label: str) -> pd.DataFrame:
    path = next(SOURCE_DIR.glob(f"Stock_Composants*{label}.csv"))
    df = pd.read_csv(path, sep=";")
    return pd.DataFrame(
        {
            "label": label,
            "snapshot_dt": pd.to_datetime(df.iloc[:, 0]),
            "real_value_eur": df.iloc[:, 1].astype(float),
        }
    )


def actor_mapping() -> pd.DataFrame:
    actors = pd.read_excel(SOURCE_DIR / "demand_PF.xlsx", sheet_name="Acteurs")
    rows = []
    for _, row in actors[actors["role"] == "Manufacturer"].iterrows():
        products = str(row["manufactured_products"])
        for product_code in [part.strip() for part in products.split(",") if part.strip().isdigit()]:
            rows.append(
                {
                    "product_code": product_code,
                    "description": row["description"],
                    "location_ID": row["location_ID"],
                }
            )
    return pd.DataFrame(rows)


def simulation_stock_summary() -> pd.DataFrame:
    path = RUN_DIR / "data" / "component_immobilized_stock_daily.csv"
    if not path.exists():
        return pd.DataFrame()
    daily = pd.read_csv(path)
    rows = []
    for product_code in PRODUCTS:
        subset = daily[daily["product_code"].astype(str) == product_code].drop_duplicates("day")
        if subset.empty:
            continue
        rows.append(
            {
                "product_code": product_code,
                "sim_day0_stock_value_eur": float(subset[subset["day"] == 0]["stock_value_eur"].iloc[0]),
                "sim_mean_stock_value_eur": float(subset["stock_value_eur"].mean()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    source_rows = []
    component_rows = []
    for product_code in PRODUCTS:
        components = source_stock_values(product_code)
        component_rows.append(components)
        source_rows.append(
            {
                "product_code": product_code,
                "division": PRODUCTS[product_code]["division"],
                "source_min_price_value_eur": float(components["min_value_eur"].sum()),
                "source_mean_price_value_eur": float(components["mean_value_eur"].sum()),
                "source_max_price_value_eur": float(components["max_value_eur"].sum()),
                "priced_component_count": int((components["max_value_eur"] > 0).sum()),
                "component_count": int(len(components)),
            }
        )
    source_summary = pd.DataFrame(source_rows)

    # Prefer the run alignment for 268091 when present because it uses the
    # simulation's consolidated valuation basis, including prices outside the
    # single workbook when available.
    alignment = RUN_DIR / "reports" / "source_truth_alignment_268091" / "component_stock_alignment.csv"
    if alignment.exists():
        alignment_df = pd.read_csv(alignment)
        source_summary.loc[
            source_summary["product_code"] == "268091", "source_run_alignment_value_eur"
        ] = float(alignment_df["source_stock_value_eur"].sum())

    real_summary = []
    for label in ("Cos", "Pharma"):
        snapshots = real_snapshots(label)
        real_summary.append(
            {
                "real_label": label,
                "real_first_value_eur": float(snapshots["real_value_eur"].iloc[0]),
                "real_mean_value_eur": float(snapshots["real_value_eur"].mean()),
                "real_min_value_eur": float(snapshots["real_value_eur"].min()),
                "real_max_value_eur": float(snapshots["real_value_eur"].max()),
            }
        )
    real_summary = pd.DataFrame(real_summary)

    comparisons = []
    for _, product in source_summary.iterrows():
        reference = product.get("source_run_alignment_value_eur")
        if pd.isna(reference):
            reference = product["source_max_price_value_eur"]
        for _, real in real_summary.iterrows():
            comparisons.append(
                {
                    "product_code": product["product_code"],
                    "reference_source_value_eur": float(reference),
                    "real_label": real["real_label"],
                    "real_first_value_eur": real["real_first_value_eur"],
                    "first_gap_eur": float(reference - real["real_first_value_eur"]),
                    "first_gap_abs_eur": abs(float(reference - real["real_first_value_eur"])),
                }
            )
    comparisons = pd.DataFrame(comparisons).sort_values(["product_code", "first_gap_abs_eur"])

    actors = actor_mapping()
    sim_summary = simulation_stock_summary()
    source_summary = source_summary.merge(actors, on="product_code", how="left").merge(
        sim_summary, on="product_code", how="left"
    )

    source_summary.to_csv(OUTPUT_DIR / "source_component_stock_by_product.csv", index=False)
    real_summary.to_csv(OUTPUT_DIR / "real_component_stock_kpi_files.csv", index=False)
    comparisons.to_csv(OUTPUT_DIR / "product_to_real_kpi_comparison.csv", index=False)
    pd.concat(component_rows, ignore_index=True).to_csv(
        OUTPUT_DIR / "source_component_stock_by_item.csv", index=False
    )

    best_268091 = comparisons[comparisons["product_code"] == "268091"].iloc[0]
    lines = [
        "# Audit mapping KPI stock composants",
        "",
        "## Conclusion",
        "",
        (
            "Le facteur `28%` n'est pas une regle metier robuste. Le premier ecart vient d'un "
            "probleme de perimetre: le produit `268091` doit etre compare au KPI reel dont le "
            "niveau correspond a son stock composant source, pas forcement au fichier libelle "
            "`Pharma`."
        ),
        "",
        (
            f"Pour `268091`, la valeur source consolidee du run vaut "
            f"{euro(float(source_summary[source_summary['product_code'] == '268091']['source_run_alignment_value_eur'].iloc[0]))}. "
            f"La premiere photo `Cos` vaut {euro(float(real_summary[real_summary['real_label'] == 'Cos']['real_first_value_eur'].iloc[0]))}, "
            f"alors que la premiere photo `Pharma` vaut {euro(float(real_summary[real_summary['real_label'] == 'Pharma']['real_first_value_eur'].iloc[0]))}."
        ),
        "",
        (
            f"Le meilleur rapprochement premier point pour `268091` est donc `{best_268091['real_label']}` "
            f"avec un ecart absolu de {euro(float(best_268091['first_gap_abs_eur']))}."
        ),
        "",
        "## Mapping source produit",
        "",
        "| Produit | Division | Description source | Stock source min | Stock source moyen | Stock source max | Stock source run | Stock simulation J0 | Stock simulation moyen |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in source_summary.iterrows():
        run_value = row.get("source_run_alignment_value_eur")
        run_text = euro(float(run_value)) if pd.notna(run_value) else "n/a"
        sim_j0 = row.get("sim_day0_stock_value_eur")
        sim_mean = row.get("sim_mean_stock_value_eur")
        lines.append(
            "| "
            f"{row['product_code']} | {int(row['division'])} | {row.get('description', '')} | "
            f"{euro(row['source_min_price_value_eur'])} | "
            f"{euro(row['source_mean_price_value_eur'])} | "
            f"{euro(row['source_max_price_value_eur'])} | "
            f"{run_text} | "
            f"{euro(float(sim_j0)) if pd.notna(sim_j0) else 'n/a'} | "
            f"{euro(float(sim_mean)) if pd.notna(sim_mean) else 'n/a'} |"
        )

    lines += [
        "",
        "## Fichiers KPI reels agreges",
        "",
        "| Fichier reel | Premiere photo | Moyenne 2025 | Min | Max |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, row in real_summary.iterrows():
        lines.append(
            f"| {row['real_label']} | {euro(row['real_first_value_eur'])} | "
            f"{euro(row['real_mean_value_eur'])} | {euro(row['real_min_value_eur'])} | "
            f"{euro(row['real_max_value_eur'])} |"
        )

    lines += [
        "",
        "## Comparaison premier point",
        "",
        "| Produit | Reference stock source | KPI reel teste | Premiere photo reelle | Ecart |",
        "| --- | ---: | --- | ---: | ---: |",
    ]
    for _, row in comparisons.iterrows():
        lines.append(
            f"| {row['product_code']} | {euro(row['reference_source_value_eur'])} | "
            f"{row['real_label']} | {euro(row['real_first_value_eur'])} | {euro(row['first_gap_eur'])} |"
        )

    lines += [
        "",
        "## Lecture metier",
        "",
        (
            "- On ne peut pas expliquer proprement `~220 kEUR` a partir d'un stock initial `~700-900 kEUR` "
            "si ces deux chiffres ne portent pas sur le meme couple produit/perimetre."
        ),
        (
            "- Pour `268091`, le niveau `~657 kEUR` du fichier `Cos` colle au stock composant source; "
            "l'ecart restant releve ensuite des mouvements de stock et de la convention de valorisation."
        ),
        (
            "- Le fichier `Pharma` a `~221 kEUR` est un autre perimetre. Pour l'expliquer, il faut auditer "
            "`268967` en excluant les PFI internes et probablement certaines familles de composants/packaging, "
            "mais ce n'est pas la regle de `268091`."
        ),
        (
            "- La prochaine correction propre est de parametrer explicitement le mapping "
            "`produit -> KPI reel stock composants` au lieu d'utiliser `Stock_Composants*Pharma.csv` en dur."
        ),
    ]

    report_path = OUTPUT_DIR / "component_stock_kpi_mapping_audit.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
