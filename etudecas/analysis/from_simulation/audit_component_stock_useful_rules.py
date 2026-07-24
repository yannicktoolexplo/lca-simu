"""Audit component immobilized-stock rules for the two source PF scopes.

The source KPI is an aggregate value named "Stock Composants Immobilise".
This script compares it against several simulation-derived readings, always
excluding internal roll-up/PFI valuation from the main component scope.
"""

from __future__ import annotations

import argparse
import math
import unicodedata
from datetime import date
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
    / "_reruns"
    / "_codex_mrp_open_orders_targets_5y"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "etudecas"
    / "analysis"
    / "from_simulation"
    / "result"
    / "component_stock_useful_rules"
)
START_DATE = date(2025, 1, 1)

PRODUCT_SOURCE = {
    "268091": "Stock_Composants*_Cos.csv",
    "268967": "Stock_Composants*_Pharma.csv",
}

PRODUCT_SITE = {
    "268091": "1810",
    "268967": "1430",
}

PRODUCT_EXCLUDED_COMPONENTS = {
    "268091": set(),
    "268967": {"773474"},
}

INTERNAL_VALUE_SOURCES = {"internal_bom_rollup", "internal_transfer_bom_rollup"}


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(" ", "").replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def euro(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def pct(value: float) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value:.1f}%"


def item_code(item_id: Any) -> str:
    text = str(item_id or "").strip()
    if text.startswith("item:"):
        text = text.split(":", 1)[1]
    try:
        return str(int(float(text))).zfill(6)
    except ValueError:
        pass
    return text.zfill(6) if text.isdigit() else text


def norm_text(value: Any) -> str:
    text = str(value or "").lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def find_column(df: pd.DataFrame, *tokens: str) -> str:
    normalized = {col: norm_text(col) for col in df.columns}
    for col, text in normalized.items():
        if all(token in text for token in tokens):
            return str(col)
    raise KeyError(f"Missing column containing {tokens}: {list(df.columns)}")


def norm_uom(value: Any) -> str:
    text = str(value or "").strip().upper().replace(".", "")
    if text in {"ZUN", "UN", "UNIT", "UNITE", "UNITES"}:
        return "UN"
    if text in {"G", "GR", "GRAMME", "GRAMMES"}:
        return "G"
    if text in {"KG", "KILO", "KILOGRAMME", "KILOGRAMMES"}:
        return "KG"
    if text in {"M", "METRE", "METRES"}:
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


def find_one(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one file for {pattern}, found {matches}")
    return matches[0]


def read_source_csv(pattern: str) -> pd.DataFrame:
    path = find_one(pattern)
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, sep=";", encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, sep=";")


def read_observed(product_code: str) -> pd.DataFrame:
    df = read_source_csv(PRODUCT_SOURCE[product_code]).copy()
    date_col = next(col for col in df.columns if "Date" in col)
    value_col = next(col for col in df.columns if "Valeur" in col or "stock" in col.lower())
    df["snapshot_dt"] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
    if df["snapshot_dt"].isna().all():
        raise ValueError(
            f"Aucune date source lisible pour {product_code} dans {PRODUCT_SOURCE[product_code]}"
        )
    df = df[df["snapshot_dt"].notna()].copy()
    df["source_day"] = (df["snapshot_dt"].dt.date - START_DATE).apply(lambda delta: delta.days)
    # Source snapshots are around 00:05. Compare with previous simulated closing day.
    df["sim_day"] = (df["source_day"] - 1).clip(lower=0)
    df["observed_value_eur"] = df[value_col].map(parse_float)
    if df.empty:
        raise ValueError(f"Aucune ligne source observee pour {product_code}")
    df["product_code"] = product_code
    return df[["product_code", "snapshot_dt", "source_day", "sim_day", "observed_value_eur"]].sort_values(
        "snapshot_dt"
    )


def relation_unit_prices() -> pd.DataFrame:
    relations = pd.read_excel(SOURCE_DIR / "demand_PF.xlsx", sheet_name="Relations_acteurs")
    relations["component_code"] = relations["product"].map(item_code)
    relations["unit_price_eur"] = relations["sell_price"].map(parse_float) / relations["price_base"].map(
        lambda value: parse_float(value, 1.0) or 1.0
    )
    relations["price_uom"] = relations["quantity_unit"].map(norm_uom)
    rows = []
    for component_code, group in relations.groupby("component_code"):
        positive = group[group["unit_price_eur"] > 0]
        selected = positive if not positive.empty else group
        rows.append(
            {
                "component_code": component_code,
                "unit_price_eur": float(selected["unit_price_eur"].median()),
                "price_uom": selected["price_uom"].mode().iloc[0] if not selected["price_uom"].mode().empty else "",
            }
        )
    return pd.DataFrame(rows)


def source_opening_minus_week_consumption(observed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute useful stock from source opening stock and week-1 consumption.

    useful implied here means:
    source stock value on Jan 1 - one source demand week of BOM consumption
    - first observed immobilized-stock snapshot.
    """

    extract_path = find_one("Extract_Donn*Compl*.xlsx")
    stocks = pd.read_excel(extract_path, sheet_name="Stocks")
    stocks["component_code"] = stocks[find_column(stocks, "article")].map(item_code)
    stocks["site"] = stocks[find_column(stocks, "division")].astype(str).str.strip()
    stocks["stock_qty"] = stocks[find_column(stocks, "stock")].map(parse_float)
    stocks["stock_uom"] = stocks[find_column(stocks, "unite")].map(norm_uom)

    bom = pd.read_excel(SOURCE_DIR / "demand_PF.xlsx", sheet_name="BOM")
    bom = bom[pd.to_numeric(bom["output_product"], errors="coerce").notna()].copy()
    bom["product_code"] = bom["output_product"].map(item_code)
    bom["component_code"] = bom["input_product"].map(item_code)
    bom["qty_per_batch"] = bom["quantity"].map(parse_float)
    bom["batch_size"] = bom["batch_size"].map(parse_float)
    bom["bom_uom"] = bom["quantity_unit"].map(norm_uom)

    demand = pd.read_excel(SOURCE_DIR / "demand_PF.xlsx", sheet_name="Demande")
    demand["product_code"] = demand["product"].map(item_code)
    demand["step_num"] = pd.to_numeric(demand["step"], errors="coerce")
    demand["real_demand"] = demand["real demand"].map(parse_float)

    prices = relation_unit_prices()
    detail_rows = []
    summary_rows = []
    for product_code in sorted(PRODUCT_SOURCE):
        product_bom = bom[
            (bom["product_code"] == product_code)
            & (~bom["component_code"].isin(PRODUCT_EXCLUDED_COMPONENTS.get(product_code, set())))
        ].copy()
        week_demand = float(
            demand[(demand["product_code"] == product_code) & (demand["step_num"] == 1)]["real_demand"].sum()
        )
        site = PRODUCT_SITE[product_code]
        opening_value = 0.0
        week_consumption_value = 0.0
        for _, component in product_bom.iterrows():
            component_code = str(component["component_code"])
            stock = stocks[(stocks["site"] == site) & (stocks["component_code"] == component_code)]
            price = prices[prices["component_code"] == component_code]
            unit_price = float(price["unit_price_eur"].iloc[0]) if not price.empty else 0.0
            price_uom = str(price["price_uom"].iloc[0]) if not price.empty else str(component["bom_uom"])
            stock_qty = float(stock["stock_qty"].sum()) if not stock.empty else 0.0
            stock_uom = str(stock["stock_uom"].iloc[0]) if not stock.empty else str(component["bom_uom"])
            stock_qty_price_uom = convert_qty(stock_qty, stock_uom, price_uom)
            stock_value = (stock_qty_price_uom or 0.0) * unit_price
            consumption_qty = (
                float(component["qty_per_batch"]) * week_demand / float(component["batch_size"])
                if float(component["batch_size"]) > 0
                else 0.0
            )
            consumption_qty_price_uom = convert_qty(consumption_qty, component["bom_uom"], price_uom)
            component_consumption_value = (consumption_qty_price_uom or 0.0) * unit_price
            opening_value += stock_value
            week_consumption_value += component_consumption_value
            detail_rows.append(
                {
                    "product_code": product_code,
                    "component_code": component_code,
                    "site": site,
                    "stock_qty_source": stock_qty,
                    "stock_uom": stock_uom,
                    "unit_price_eur": unit_price,
                    "price_uom": price_uom,
                    "opening_value_eur": stock_value,
                    "week1_demand_pf": week_demand,
                    "week1_consumption_qty_bom_uom": consumption_qty,
                    "bom_uom": component["bom_uom"],
                    "week1_consumption_value_eur": component_consumption_value,
                }
            )
        observed_product = observed[observed["product_code"] == product_code].sort_values("snapshot_dt")
        first_observed = observed_product.iloc[0]
        after_week = opening_value - week_consumption_value
        summary_rows.append(
            {
                "product_code": product_code,
                "opening_source_component_value_eur": opening_value,
                "week1_consumption_value_eur": week_consumption_value,
                "after_week1_consumption_eur": after_week,
                "first_real_immobilized_eur": float(first_observed["observed_value_eur"]),
                "first_real_snapshot": str(first_observed["snapshot_dt"]),
                "useful_implied_from_first_snapshot_eur": after_week - float(first_observed["observed_value_eur"]),
                "mean_real_immobilized_eur": float(observed_product["observed_value_eur"].mean()),
                "useful_implied_using_mean_real_eur": after_week
                - float(observed_product["observed_value_eur"].mean()),
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(detail_rows)


def read_component_details(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "data" / "component_immobilized_stock_components_daily.csv"
    df = pd.read_csv(path)
    df["product_code"] = df["product_code"].astype(str)
    df = df[~df["value_source"].astype(str).isin(INTERNAL_VALUE_SOURCES)].copy()
    for col in [
        "day",
        "stock_qty",
        "useful_qty",
        "immobilized_qty",
        "unit_value_eur",
        "stock_value_eur",
        "useful_value_eur",
        "immobilized_value_eur",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["day"] = df["day"].astype(int)
    df["component_code"] = df["component_item_id"].map(item_code)
    return df


def read_lot_consumption(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "data" / "production_lot_events.csv"
    df = pd.read_csv(path, usecols=["day", "event_type", "node_id", "item_id", "qty"])
    df = df[df["event_type"].eq("production_consume")].copy()
    df["day"] = pd.to_numeric(df["day"], errors="coerce").fillna(0).astype(int)
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.0)
    return df.groupby(["day", "node_id", "item_id"], as_index=False)["qty"].sum()


def simulated_opening_minus_consumption(run_dir: Path, details: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the same opening-minus-consumption reading to simulated stocks."""

    scope = (
        details[details["threshold_mode"].eq("target_stock")]
        [["product_code", "node_id", "component_item_id", "component_code", "unit_value_eur", "value_source"]]
        .drop_duplicates()
        .copy()
    )
    stocks = pd.read_csv(run_dir / "data" / "production_input_stocks_daily.csv")
    for col in ["day", "stock_before_production", "stock_end_of_day"]:
        stocks[col] = pd.to_numeric(stocks[col], errors="coerce").fillna(0.0)
    stocks["day"] = stocks["day"].astype(int)

    lot_events = pd.read_csv(
        run_dir / "data" / "production_lot_events.csv",
        usecols=["day", "event_type", "node_id", "item_id", "qty"],
    )
    lot_events = lot_events[lot_events["event_type"].eq("production_consume")].copy()
    lot_events["day"] = pd.to_numeric(lot_events["day"], errors="coerce").fillna(0).astype(int)
    lot_events["qty"] = pd.to_numeric(lot_events["qty"], errors="coerce").fillna(0.0)

    opening_rows = []
    consumption_rows = []
    for _, row in scope.iterrows():
        product_code = str(row["product_code"])
        node_id = str(row["node_id"])
        item_id = str(row["component_item_id"])
        unit_value = float(row["unit_value_eur"])
        stock = stocks[(stocks["day"].eq(0)) & (stocks["node_id"].eq(node_id)) & (stocks["item_id"].eq(item_id))]
        opening_qty = float(stock["stock_before_production"].sum()) if not stock.empty else 0.0
        day0_end_qty = float(stock["stock_end_of_day"].sum()) if not stock.empty else 0.0
        opening_rows.append(
            {
                "product_code": product_code,
                "node_id": node_id,
                "component_item_id": item_id,
                "component_code": row["component_code"],
                "unit_value_eur": unit_value,
                "value_source": row["value_source"],
                "opening_qty_before_j0": opening_qty,
                "opening_value_before_j0_eur": opening_qty * unit_value,
                "day0_end_qty": day0_end_qty,
                "day0_end_value_eur": day0_end_qty * unit_value,
            }
        )
        events = lot_events[(lot_events["node_id"].eq(node_id)) & (lot_events["item_id"].eq(item_id))]
        for end_day in (4, 5, 6):
            consumed_qty = float(events[events["day"].between(0, end_day)]["qty"].sum())
            consumption_rows.append(
                {
                    "product_code": product_code,
                    "node_id": node_id,
                    "component_item_id": item_id,
                    "component_code": row["component_code"],
                    "period": f"J0-J{end_day}",
                    "consumed_qty": consumed_qty,
                    "consumed_value_eur": consumed_qty * unit_value,
                }
            )

    opening = pd.DataFrame(opening_rows)
    consumption = pd.DataFrame(consumption_rows)
    by_day = (
        details[details["threshold_mode"].eq("target_stock")]
        .groupby(["product_code", "day"], as_index=False)
        .agg(
            sim_stock_value_end_period_eur=("stock_value_eur", "sum"),
            sim_useful_mrp_end_period_eur=("useful_value_eur", "sum"),
            sim_immobilized_target_end_period_eur=("immobilized_value_eur", "sum"),
        )
    )
    summary_rows = []
    for product_code in sorted(PRODUCT_SOURCE):
        opening_value = float(opening[opening["product_code"].astype(str).eq(product_code)]["opening_value_before_j0_eur"].sum())
        day0_end_value = float(opening[opening["product_code"].astype(str).eq(product_code)]["day0_end_value_eur"].sum())
        for end_day in (4, 5, 6):
            period = f"J0-J{end_day}"
            consumed_value = float(
                consumption[
                    (consumption["product_code"].astype(str).eq(product_code)) & (consumption["period"].eq(period))
                ]["consumed_value_eur"].sum()
            )
            stock_after_consumption = opening_value - consumed_value
            row = by_day[(by_day["product_code"].astype(str).eq(product_code)) & (by_day["day"].eq(end_day))]
            stock_end = float(row["sim_stock_value_end_period_eur"].iloc[0]) if not row.empty else 0.0
            useful_mrp = float(row["sim_useful_mrp_end_period_eur"].iloc[0]) if not row.empty else 0.0
            immobilized = float(row["sim_immobilized_target_end_period_eur"].iloc[0]) if not row.empty else 0.0
            summary_rows.append(
                {
                    "product_code": product_code,
                    "period": period,
                    "opening_sim_component_value_before_j0_eur": opening_value,
                    "day0_end_component_value_eur": day0_end_value,
                    "sim_consumption_value_eur": consumed_value,
                    "opening_minus_consumption_eur": stock_after_consumption,
                    "sim_stock_value_end_period_eur": stock_end,
                    "sim_immobilized_target_end_period_eur": immobilized,
                    "sim_useful_mrp_end_period_eur": useful_mrp,
                    "useful_implied_opening_minus_consumption_minus_sim_immob_eur": stock_after_consumption
                    - immobilized,
                }
            )
    return pd.DataFrame(summary_rows), pd.DataFrame(opening_rows + consumption_rows)


def future_need(consumption: pd.DataFrame, keys: pd.DataFrame, horizon: int, max_day: int) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    day_index = pd.RangeIndex(0, max_day + horizon + 2, name="day")
    for _, key in keys.drop_duplicates(["node_id", "component_item_id"]).iterrows():
        node_id = str(key["node_id"])
        item_id = str(key["component_item_id"])
        series = (
            consumption[(consumption["node_id"].eq(node_id)) & (consumption["item_id"].eq(item_id))]
            .set_index("day")["qty"]
            .reindex(day_index, fill_value=0.0)
            .astype(float)
        )
        csum = series.cumsum()
        end_idx = (pd.Series(day_index, index=day_index) + horizon).clip(upper=day_index[-1]).astype(int)
        qty = csum.loc[end_idx.to_numpy()].to_numpy() - csum.to_numpy()
        rows.append(
            pd.DataFrame(
                {
                    "day": day_index.to_numpy(),
                    "node_id": node_id,
                    "component_item_id": item_id,
                    f"future_need_{horizon}d_qty": qty,
                }
            )
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def metric(real: pd.Series, sim: pd.Series) -> dict[str, float]:
    diff = sim - real
    corr = real.corr(sim) if len(real) > 1 and float(sim.std()) > 0 else float("nan")
    return {
        "observed_mean_eur": float(real.mean()),
        "simulated_mean_eur": float(sim.mean()),
        "bias_eur": float(diff.mean()),
        "bias_pct": float(100.0 * diff.mean() / real.mean()) if real.mean() else float("nan"),
        "mae_eur": float(diff.abs().mean()),
        "mae_pct": float(100.0 * diff.abs().mean() / real.mean()) if real.mean() else float("nan"),
        "corr": float(corr),
    }


def aggregate_existing_modes(details: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        details.groupby(["product_code", "day", "threshold_mode"], as_index=False)
        .agg(
            stock_value_eur=("stock_value_eur", "sum"),
            useful_value_eur=("useful_value_eur", "sum"),
            immobilized_value_eur=("immobilized_value_eur", "sum"),
            component_count=("component_item_id", "nunique"),
        )
        .copy()
    )
    rows = []
    for _, row in grouped.iterrows():
        rows.append(
            {
                "product_code": row["product_code"],
                "day": int(row["day"]),
                "rule": f"excess_vs_{row['threshold_mode']}",
                "stock_value_eur": float(row["stock_value_eur"]),
                "useful_value_eur": float(row["useful_value_eur"]),
                "immobilized_value_eur": float(row["immobilized_value_eur"]),
                "component_count": int(row["component_count"]),
            }
        )
    physical = (
        details[details["threshold_mode"].eq("target_stock")]
        .groupby(["product_code", "day"], as_index=False)
        .agg(stock_value_eur=("stock_value_eur", "sum"), component_count=("component_item_id", "nunique"))
    )
    for _, row in physical.iterrows():
        rows.append(
            {
                "product_code": row["product_code"],
                "day": int(row["day"]),
                "rule": "physical_stock_value",
                "stock_value_eur": float(row["stock_value_eur"]),
                "useful_value_eur": 0.0,
                "immobilized_value_eur": float(row["stock_value_eur"]),
                "component_count": int(row["component_count"]),
            }
        )
    return pd.DataFrame(rows)


def aggregate_future_need_modes(details: pd.DataFrame, consumption: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    base = details[details["threshold_mode"].eq("target_stock")].copy()
    max_day = int(max(base["day"].max(), 1824))
    rows = []
    keys = base[["node_id", "component_item_id"]].drop_duplicates()
    for horizon in horizons:
        needs = future_need(consumption, keys, horizon, max_day)
        if needs.empty:
            continue
        merged = base.merge(needs, on=["day", "node_id", "component_item_id"], how="left")
        need_col = f"future_need_{horizon}d_qty"
        merged[need_col] = pd.to_numeric(merged[need_col], errors="coerce").fillna(0.0)
        merged["future_useful_value_eur"] = (
            merged[["stock_qty", need_col]].min(axis=1).clip(lower=0.0) * merged["unit_value_eur"]
        )
        merged["future_immobilized_value_eur"] = (
            (merged["stock_qty"] - merged[need_col]).clip(lower=0.0) * merged["unit_value_eur"]
        )
        grouped = (
            merged.groupby(["product_code", "day"], as_index=False)
            .agg(
                stock_value_eur=("stock_value_eur", "sum"),
                useful_value_eur=("future_useful_value_eur", "sum"),
                immobilized_value_eur=("future_immobilized_value_eur", "sum"),
                component_count=("component_item_id", "nunique"),
            )
            .copy()
        )
        grouped["rule"] = f"excess_vs_future_need_{horizon}d"
        rows.append(grouped)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)[
        ["product_code", "day", "rule", "stock_value_eur", "useful_value_eur", "immobilized_value_eur", "component_count"]
    ]


def compare_rules(observed: pd.DataFrame, rules: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if observed.empty:
        raise ValueError("Comparaison impossible: aucune ligne source observee.")
    if rules.empty:
        raise ValueError("Comparaison impossible: aucune serie simulation candidate.")
    pairs = observed.merge(rules, left_on=["product_code", "sim_day"], right_on=["product_code", "day"], how="left")
    matched = pairs.dropna(subset=["immobilized_value_eur"])
    if matched.empty:
        products = ", ".join(sorted(set(map(str, observed["product_code"]))))
        days = ", ".join(map(str, sorted(set(map(int, observed["sim_day"])))))
        raise ValueError(
            "Comparaison source/simulation impossible: aucune photo source n'est appariee "
            f"avec une journee simulee. PF={products}; jours attendus={days}"
        )
    pairs["implied_useful_value_eur"] = (pairs["stock_value_eur"] - pairs["observed_value_eur"]).clip(lower=0.0)
    pairs["useful_gap_vs_implied_eur"] = pairs["useful_value_eur"] - pairs["implied_useful_value_eur"]
    rows = []
    for (product_code, rule), grp in matched.groupby(["product_code", "rule"]):
        m = metric(grp["observed_value_eur"], grp["immobilized_value_eur"])
        useful = metric(grp["implied_useful_value_eur"], grp["useful_value_eur"])
        rows.append(
            {
                "product_code": product_code,
                "rule": rule,
                **m,
                "stock_mean_eur": float(grp["stock_value_eur"].mean()),
                "candidate_useful_mean_eur": float(grp["useful_value_eur"].mean()),
                "implied_useful_mean_eur": float(grp["implied_useful_value_eur"].mean()),
                "useful_bias_eur": float(grp["useful_gap_vs_implied_eur"].mean()),
                "useful_mae_eur": useful["mae_eur"],
                "component_count_mean": float(grp["component_count"].mean()),
            }
        )
    metrics = pd.DataFrame(rows).sort_values(["product_code", "mae_eur", "rule"])
    return metrics, pairs


def source_price_rows() -> pd.DataFrame:
    rows = []
    for product_code in PRODUCT_SOURCE:
        path = find_one(f"{product_code}.xlsx")
        fia = pd.read_excel(path, sheet_name="FIA")
        bom = pd.read_excel(path, sheet_name="BOM")
        component_col = next(col for col in bom.columns if "composante" in col.lower())
        bom_components = {str(int(float(v))).zfill(6) for v in bom[component_col].dropna()}
        price_col = next((col for col in fia.columns if "Montant" in col), "")
        base_col = next((col for col in fia.columns if "Base" in col), "")
        supplier_col = next((col for col in fia.columns if "fournisseur" in col.lower()), "")
        item_col = next((col for col in fia.columns if "article" in col.lower()), "")
        for _, row in fia.iterrows():
            code = str(int(float(row[item_col]))).zfill(6)
            if code not in bom_components:
                continue
            price = parse_float(row.get(price_col))
            base = parse_float(row.get(base_col), 1.0) or 1.0
            rows.append(
                {
                    "product_code": product_code,
                    "component_code": code,
                    "supplier": row.get(supplier_col, ""),
                    "source_unit_price_eur": price / base if base else 0.0,
                    "raw_price": price,
                    "price_base": base,
                }
            )
    return pd.DataFrame(rows)


def contributor_summary(details: pd.DataFrame, observed: pd.DataFrame) -> pd.DataFrame:
    wanted_days = set(observed["sim_day"].astype(int).tolist())
    wanted_products = set(observed["product_code"].astype(str).tolist())
    target = details[
        (details["threshold_mode"].eq("target_stock"))
        & (details["day"].isin(wanted_days))
        & (details["product_code"].astype(str).isin(wanted_products))
    ].copy()
    return (
        target.groupby(["product_code", "node_id", "component_code", "value_source"], as_index=False)
        .agg(
            stock_value_mean_eur=("stock_value_eur", "mean"),
            useful_value_mean_eur=("useful_value_eur", "mean"),
            immobilized_value_mean_eur=("immobilized_value_eur", "mean"),
            stock_qty_mean=("stock_qty", "mean"),
            unit_value_eur=("unit_value_eur", "median"),
            snapshots=("day", "nunique"),
        )
        .sort_values(["product_code", "stock_value_mean_eur"], ascending=[True, False])
    )


def write_report(
    output_dir: Path,
    metrics: pd.DataFrame,
    pairs: pd.DataFrame,
    contributors: pd.DataFrame,
    prices: pd.DataFrame,
    source_opening: pd.DataFrame,
    source_opening_details: pd.DataFrame,
    simulated_opening: pd.DataFrame,
    simulated_opening_details: pd.DataFrame,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_dir / "component_stock_rule_metrics.csv", index=False)
    pairs.to_csv(output_dir / "component_stock_rule_snapshot_pairs.csv", index=False)
    contributors.to_csv(output_dir / "component_stock_rule_contributors.csv", index=False)
    prices.to_csv(output_dir / "component_stock_source_prices.csv", index=False)
    source_opening.to_csv(output_dir / "source_opening_minus_week_consumption_summary.csv", index=False)
    source_opening_details.to_csv(output_dir / "source_opening_minus_week_consumption_components.csv", index=False)
    simulated_opening.to_csv(output_dir / "sim_opening_minus_consumption_summary.csv", index=False)
    simulated_opening_details.to_csv(output_dir / "sim_opening_minus_consumption_components.csv", index=False)

    lines = [
        "# Audit stock composant immobilise - regles de stock utile",
        "",
        "Perimetre: composants des PF 268091 et 268967, PFI/roll-up internes exclus de la lecture principale.",
        "Comparaison: photos source hebdomadaires vers cloture simulation de la veille.",
        "",
        "## Stock utile implicite depuis les donnees source",
        "",
        "Formule demandee: stock composants source au 01/01 - consommation BOM semaine 1 - premier stock immobilise reel.",
        "",
        "| PF | Stock composants source 01/01 | Conso semaine 1 | Stock apres conso | Premier immobilise reel | Stock utile implicite | Date photo reelle |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for _, row in source_opening.sort_values("product_code").iterrows():
        lines.append(
            f"| {row['product_code']} | {euro(row['opening_source_component_value_eur'])} | "
            f"{euro(row['week1_consumption_value_eur'])} | {euro(row['after_week1_consumption_eur'])} | "
            f"{euro(row['first_real_immobilized_eur'])} | "
            f"{euro(row['useful_implied_from_first_snapshot_eur'])} | {row['first_real_snapshot']} |"
        )

    lines += [
        "",
        "## Meme lecture cote simulation",
        "",
        "Formule: stock composants simule debut J0 - consommation simulee de la periode - immobilise simule en fin de periode.",
        "",
        "| PF | Periode | Stock sim debut J0 | Conso sim | Apres conso | Immobilise sim | Utile implicite sim | Utile MRP sim |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in simulated_opening.sort_values(["product_code", "period"]).iterrows():
        lines.append(
            f"| {row['product_code']} | {row['period']} | "
            f"{euro(row['opening_sim_component_value_before_j0_eur'])} | "
            f"{euro(row['sim_consumption_value_eur'])} | "
            f"{euro(row['opening_minus_consumption_eur'])} | "
            f"{euro(row['sim_immobilized_target_end_period_eur'])} | "
            f"{euro(row['useful_implied_opening_minus_consumption_minus_sim_immob_eur'])} | "
            f"{euro(row['sim_useful_mrp_end_period_eur'])} |"
        )

    lines += [
        "",
        "## Diagnostic des regles sur stock simule",
        "",
        "Cette section reste un diagnostic modele: elle part du stock physique simule moyen, pas de la photo source du 01/01.",
        "",
        "| PF | Regle | Reel moyen | Simulation | Ecart | MAE | Stock physique sim | Stock utile candidat | Utile implicite depuis stock simule |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for product_code, grp in metrics.groupby("product_code"):
        best = grp.sort_values(["mae_eur", "rule"]).iloc[0]
        lines.append(
            f"| {product_code} | `{best['rule']}` | {euro(best['observed_mean_eur'])} | "
            f"{euro(best['simulated_mean_eur'])} | {euro(best['bias_eur'])} ({pct(best['bias_pct'])}) | "
            f"{euro(best['mae_eur'])} | {euro(best['stock_mean_eur'])} | "
            f"{euro(best['candidate_useful_mean_eur'])} | {euro(best['implied_useful_mean_eur'])} |"
        )

    lines += [
        "",
        "## Regles candidates principales",
        "",
        "| PF | Regle | Reel moyen | Simulation | Bias | MAE | Corr | Utile candidat | Utile implique | Biais utile |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    preferred = {
        "physical_stock_value",
        "excess_vs_target_stock",
        "excess_vs_coverage",
        "excess_vs_safety_plus_coverage",
        "excess_vs_max_safety_coverage",
        "excess_vs_demand_90d",
        "excess_vs_future_need_30d",
        "excess_vs_future_need_60d",
        "excess_vs_future_need_90d",
        "excess_vs_future_need_180d",
    }
    for _, row in metrics[metrics["rule"].isin(preferred)].sort_values(["product_code", "mae_eur"]).iterrows():
        lines.append(
            f"| {row['product_code']} | `{row['rule']}` | {euro(row['observed_mean_eur'])} | "
            f"{euro(row['simulated_mean_eur'])} | {euro(row['bias_eur'])} ({pct(row['bias_pct'])}) | "
            f"{euro(row['mae_eur'])} | {row['corr']:.2f} | {euro(row['candidate_useful_mean_eur'])} | "
            f"{euro(row['implied_useful_mean_eur'])} | {euro(row['useful_bias_eur'])} |"
        )

    lines += [
        "",
        "## Regles communes aux deux PF",
        "",
        "| Regle | MAE moyen pondere | Bias moyen pondere | MAE moyenne relative |",
        "| --- | ---: | ---: | ---: |",
    ]
    common = (
        metrics.groupby("rule", as_index=False)
        .agg(
            mae_eur=("mae_eur", "sum"),
            observed_mean_eur=("observed_mean_eur", "sum"),
            bias_eur=("bias_eur", "sum"),
            product_count=("product_code", "nunique"),
        )
        .copy()
    )
    common = common[common["product_count"] == len(PRODUCT_SOURCE)].copy()
    common["weighted_mae_pct"] = common["mae_eur"] / common["observed_mean_eur"].replace(0.0, pd.NA) * 100.0
    common["weighted_bias_pct"] = common["bias_eur"] / common["observed_mean_eur"].replace(0.0, pd.NA) * 100.0
    for _, row in common.sort_values(["weighted_mae_pct", "rule"]).head(10).iterrows():
        lines.append(
            f"| `{row['rule']}` | {euro(row['mae_eur'])} | "
            f"{euro(row['bias_eur'])} ({pct(row['weighted_bias_pct'])}) | {pct(row['weighted_mae_pct'])} |"
        )

    lines += [
        "",
        "## Lecture des causes",
        "",
        "- Cause 1 / cible MRP: si `excess_vs_target_stock` est trop bas, la cible utile MRP est trop haute; s'il est trop haut, la cible utile MRP est trop basse.",
        "- Cause 3 / prix-perimetre: les composants a prix source nul ou manquant ne peuvent pas expliquer une surevaluation; ils sous-valorisent plutot la simulation.",
        "- Definition du stock utile: la colonne `Utile implique` vaut stock physique simule moins stock immobilise reel. Une bonne regle doit s'en rapprocher sur les deux PF.",
        "",
        "## Prix source nuls sur composants BOM",
        "",
        "| PF | Composant | Fournisseur | Prix unitaire source | Prix brut / base |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    zero_prices = prices[prices["source_unit_price_eur"].fillna(0.0).le(0.0)].copy()
    for _, row in zero_prices.iterrows():
        lines.append(
            f"| {row['product_code']} | {row['component_code']} | {row['supplier']} | "
            f"{row['source_unit_price_eur']:.6g} | {row['raw_price']:g} / {row['price_base']:g} |"
        )

    lines += [
        "",
        "## Top contributeurs valorises par PF",
        "",
        "| PF | Composant | Valeur stock | Valeur utile MRP | Immobilise MRP | Prix unitaire | Source valeur |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for product_code, grp in contributors.groupby("product_code"):
        for _, row in grp.head(8).iterrows():
            lines.append(
                f"| {product_code} | {row['component_code']} | {euro(row['stock_value_mean_eur'])} | "
                f"{euro(row['useful_value_mean_eur'])} | {euro(row['immobilized_value_mean_eur'])} | "
                f"{row['unit_value_eur']:.6g} | {row['value_source']} |"
            )

    path = output_dir / "component_stock_useful_rules_audit.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(run_dir: Path, output_dir: Path) -> Path:
    observed = pd.concat([read_observed(product_code) for product_code in PRODUCT_SOURCE], ignore_index=True)
    details = read_component_details(run_dir)
    consumption = read_lot_consumption(run_dir)
    existing = aggregate_existing_modes(details)
    future = aggregate_future_need_modes(details, consumption, [7, 14, 21, 30, 45, 60, 90, 120, 180, 270, 365])
    rules = pd.concat([existing, future], ignore_index=True)
    metrics, pairs = compare_rules(observed, rules)
    contributors = contributor_summary(details, observed)
    prices = source_price_rows()
    source_opening, source_opening_details = source_opening_minus_week_consumption(observed)
    sim_opening, sim_opening_details = simulated_opening_minus_consumption(run_dir, details)
    return write_report(
        output_dir,
        metrics,
        pairs,
        contributors,
        prices,
        source_opening,
        source_opening_details,
        sim_opening,
        sim_opening_details,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = run(args.run_dir, args.output_dir)
    print(report)


if __name__ == "__main__":
    main()
