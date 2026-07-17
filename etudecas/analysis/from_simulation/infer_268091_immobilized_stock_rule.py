"""Infer plausible immobilized-stock rules for PF 268091.

This audit compares the observed weekly Cos/PF immobilized-stock snapshots
with several simulation-derived interpretations:

- physical stock value;
- stock above a future-consumption horizon;
- stock above supplier lead time and/or MRP safety-time coverage;
- PF value inferred from simulated PF quantities.

It is intentionally diagnostic. It does not change the simulation.
"""

from __future__ import annotations

import math
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
    / "infer_268091_immobilized_stock_rule"
)

START_DATE = date(2025, 1, 1)
PRODUCT_CODE = "268091"
PRODUCT_ITEM = f"item:{PRODUCT_CODE}"
FACTORY = "M-1810"
DC = "DC-1920"


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one source file for {pattern}, found {matches}")
    return matches[0]


def read_source_csv(pattern: str) -> pd.DataFrame:
    path = source_file(pattern)
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, sep=";", encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.read_csv(path, sep=";")


def item_code(value: Any) -> str:
    try:
        return str(int(float(value))).zfill(6)
    except (TypeError, ValueError):
        text = str(value).strip().replace("item:", "")
        return text.zfill(6) if text.isdigit() else text


def item_id(value: Any) -> str:
    return f"item:{item_code(value)}"


def euro(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def pct(value: float) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{100.0 * value:.1f}%"


def real_component_snapshots() -> pd.DataFrame:
    df = read_source_csv("Stock_Composants*Cos.csv").copy()
    df["snapshot_dt"] = pd.to_datetime(df["Date de photo DMP"])
    df["day"] = (df["snapshot_dt"].dt.date - START_DATE).apply(lambda delta: delta.days)
    df["sim_day"] = (df["day"] - 1).clip(lower=0)
    df["real_value_eur"] = df["Sum_Valeur totale du stock"].map(parse_float)
    return df[["snapshot_dt", "day", "sim_day", "real_value_eur"]].sort_values("snapshot_dt")


def real_pf_snapshots() -> pd.DataFrame:
    df = read_source_csv("Stock_PF*.csv").copy()
    df = df[df["Numéro article"].astype(str).str.strip() == PRODUCT_CODE].copy()
    df["snapshot_dt"] = pd.to_datetime(df["Date de photo DMP"])
    df["day"] = (df["snapshot_dt"].dt.date - START_DATE).apply(lambda delta: delta.days)
    df["sim_day"] = (df["day"] - 1).clip(lower=0)
    df["real_value_eur"] = df["Sum_Valeur totale du stock"].map(parse_float)
    return df[["snapshot_dt", "day", "sim_day", "real_value_eur"]].sort_values("snapshot_dt")


def bom_components() -> list[str]:
    bom = pd.read_excel(source_file("268091.xlsx"), sheet_name="BOM")
    bom = bom[bom["Produit Fini"].astype(str).str.strip() == PRODUCT_CODE]
    return sorted({item_id(value) for value in bom["N° composante"].tolist()})


def source_policy() -> pd.DataFrame:
    policy = pd.read_excel(source_file("Extract_Données_Complémentaires.xlsx"), sheet_name="Politique de Stock MRP")
    policy = policy[policy["Division"].astype(str).str.strip() == "1810"].copy()
    policy["item_id"] = policy["Numéro d'article"].map(item_id)
    policy["safety_time_days"] = policy["Délai de sécurité (en jours ouvrés)"].map(parse_float)
    policy["explicit_safety_stock_qty"] = policy["Stock de sécurité"].map(parse_float)
    return policy[["item_id", "safety_time_days", "explicit_safety_stock_qty", "Unité de quantité de base"]]


def fia_leads() -> pd.DataFrame:
    fia = pd.read_excel(source_file("268091.xlsx"), sheet_name="FIA")
    fia["item_id"] = fia["Numéro d'article"].map(item_id)
    fia["lead_days"] = fia["Délai prévisionnel de livraison en jours"].map(parse_float)
    return (
        fia.groupby("item_id", as_index=False)
        .agg(
            supplier_count=("Numéro de compte fournisseur", "nunique"),
            lead_days=("lead_days", "median"),
            min_lead_days=("lead_days", "min"),
            max_lead_days=("lead_days", "max"),
        )
        .sort_values("item_id")
    )


def bom_value_for_pf_qty(pf_qty: float) -> float:
    bom = pd.read_excel(source_file("268091.xlsx"), sheet_name="BOM")
    bom = bom[bom["Produit Fini"].astype(str).str.strip() == PRODUCT_CODE].copy()
    fia = pd.read_excel(source_file("268091.xlsx"), sheet_name="FIA")
    fia["item_id"] = fia["Numéro d'article"].map(item_id)
    fia["unit_price"] = fia["Montant"].map(parse_float) / fia["Base de prix"].map(parse_float).replace(0.0, pd.NA)
    fia["price_uom"] = fia["Unité de quantité"].astype(str).str.upper().str.replace(".", "", regex=False)
    prices = fia.groupby("item_id", as_index=False).agg(unit_price=("unit_price", "median"), price_uom=("price_uom", "first"))
    bom["component_item_id"] = bom["N° composante"].map(item_id)
    bom["qty_bom_uom"] = bom["Qté composants (UQB)"].map(parse_float) * (pf_qty / 1000.0)
    bom["bom_uom"] = bom["Unité de quantité"].astype(str).str.upper().str.replace(".", "", regex=False)
    bom = bom.merge(prices, left_on="component_item_id", right_on="item_id", how="left")
    bom["qty_price_uom"] = bom["qty_bom_uom"]
    mask_g_to_kg = (bom["bom_uom"] == "G") & (bom["price_uom"] == "KG")
    bom.loc[mask_g_to_kg, "qty_price_uom"] = bom.loc[mask_g_to_kg, "qty_bom_uom"] / 1000.0
    bom["value_eur"] = bom["qty_price_uom"] * bom["unit_price"].fillna(0.0)
    return float(bom["value_eur"].sum())


def first_week_check(run_dir: Path) -> dict[str, float]:
    alignment = pd.read_csv(run_dir / "reports" / "source_truth_alignment_268091" / "component_stock_alignment.csv")
    source_opening_value = float(alignment["source_stock_value_eur"].sum())
    sim_day0_end_value = float(alignment["sim_day0_end_stock_value_eur"].sum())

    snapshots = real_component_snapshots()
    first_real_value = float(snapshots.iloc[0]["real_value_eur"])

    stock = component_stock(run_dir, set(bom_components()))
    day5_value = float(stock[stock["day"] == 5]["stock_value_eur"].sum())

    lot_events = pd.read_csv(run_dir / "data" / "production_lot_events.csv")
    first_week_outputs = lot_events[
        (lot_events["day"] <= 5)
        & (lot_events["event_type"] == "production_output")
        & (lot_events["node_id"] == FACTORY)
        & (lot_events["item_id"] == PRODUCT_ITEM)
    ]
    produced_first_week = float(first_week_outputs["qty"].sum())

    demand = pd.read_excel(source_file("demand_PF.xlsx"), sheet_name="Demande")
    demand = demand[demand["product"].astype(str).str.strip() == PRODUCT_CODE].copy()
    source_week1_demand = float(demand.sort_values("step").iloc[0]["real demand"])
    service = pd.read_csv(run_dir / "data" / "production_demand_service_daily.csv")
    service = service[(service["node_id"] == "C-XXXXX") & (service["item_id"] == PRODUCT_ITEM)].copy()
    sim_demand_d0_d4 = float(service[service["day"].between(0, 4)]["demand_qty"].sum())
    sim_demand_d0_d5 = float(service[service["day"].between(0, 5)]["demand_qty"].sum())
    sim_demand_d0_d6 = float(service[service["day"].between(0, 6)]["demand_qty"].sum())

    return {
        "source_opening_component_value": source_opening_value,
        "sim_day0_end_component_value": sim_day0_end_value,
        "sim_day5_component_value": day5_value,
        "first_real_component_value": first_real_value,
        "produced_first_week_qty": produced_first_week,
        "source_week1_demand_qty": source_week1_demand,
        "source_week1_daily_uniform_qty": source_week1_demand / 7.0,
        "source_week1_to_photo_5d_qty": source_week1_demand * 5.0 / 7.0,
        "sim_smoothed_demand_d0_d4_qty": sim_demand_d0_d4,
        "sim_smoothed_demand_d0_d5_qty": sim_demand_d0_d5,
        "sim_smoothed_demand_d0_d6_qty": sim_demand_d0_d6,
        "sim_served_d0_d4_qty": float(service[service["day"].between(0, 4)]["served_qty"].sum()),
        "sim_backlog_end_d4_qty": float(service.loc[service["day"] == 4, "backlog_end_qty"].sum()),
        "bom_value_source_week1_demand": bom_value_for_pf_qty(source_week1_demand),
        "bom_value_source_week1_to_photo_5d": bom_value_for_pf_qty(source_week1_demand * 5.0 / 7.0),
        "bom_value_sim_smoothed_demand_d0_d4": bom_value_for_pf_qty(sim_demand_d0_d4),
        "bom_value_sim_first_week_production": bom_value_for_pf_qty(produced_first_week),
    }


def component_stock(run_dir: Path, components: set[str]) -> pd.DataFrame:
    path = run_dir / "data" / "component_immobilized_stock_components_daily.csv"
    usecols = [
        "day",
        "node_id",
        "product_code",
        "component_item_id",
        "threshold_mode",
        "stock_qty",
        "useful_qty",
        "immobilized_qty",
        "unit_value_eur",
        "stock_value_eur",
        "useful_value_eur",
        "immobilized_value_eur",
    ]
    df = pd.read_csv(path, usecols=usecols)
    df = df[
        (df["product_code"].astype(str) == PRODUCT_CODE)
        & (df["node_id"] == FACTORY)
        & (df["threshold_mode"] == "target_stock")
        & (df["component_item_id"].isin(components))
    ].copy()
    for col in [
        "stock_qty",
        "useful_qty",
        "immobilized_qty",
        "unit_value_eur",
        "stock_value_eur",
        "useful_value_eur",
        "immobilized_value_eur",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def component_consumption(run_dir: Path, components: set[str]) -> pd.DataFrame:
    path = run_dir / "data" / "production_lot_events.csv"
    usecols = ["day", "event_type", "node_id", "item_id", "qty"]
    df = pd.read_csv(path, usecols=usecols)
    df = df[
        (df["event_type"] == "production_consume")
        & (df["node_id"] == FACTORY)
        & (df["item_id"].isin(components))
    ].copy()
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.0)
    return df.groupby(["day", "item_id"], as_index=False)["qty"].sum()


def future_need_table(consumption: pd.DataFrame, components: set[str], max_day: int, horizon: int) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    day_index = pd.RangeIndex(0, max_day + horizon + 2, name="day")
    for component in sorted(components):
        series = (
            consumption[consumption["item_id"] == component]
            .set_index("day")["qty"]
            .reindex(day_index, fill_value=0.0)
            .astype(float)
        )
        csum = series.cumsum()
        end_idx = (pd.Series(day_index, index=day_index) + horizon).clip(upper=day_index[-1]).astype(int)
        future = csum.loc[end_idx.to_numpy()].to_numpy() - csum.to_numpy()
        rows.append(
            pd.DataFrame(
                {
                    "day": day_index.to_numpy(),
                    "component_item_id": component,
                    f"need_next_{horizon}d_qty": future,
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def future_need_by_item_horizon(
    consumption: pd.DataFrame,
    components: set[str],
    max_day: int,
    horizons_by_item: dict[str, int],
    column_name: str,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    day_index = pd.RangeIndex(0, max_day + max(horizons_by_item.values(), default=0) + 2, name="day")
    for component in sorted(components):
        horizon = int(max(0, horizons_by_item.get(component, 0)))
        series = (
            consumption[consumption["item_id"] == component]
            .set_index("day")["qty"]
            .reindex(day_index, fill_value=0.0)
            .astype(float)
        )
        csum = series.cumsum()
        end_idx = (pd.Series(day_index, index=day_index) + horizon).clip(upper=day_index[-1]).astype(int)
        future = csum.loc[end_idx.to_numpy()].to_numpy() - csum.to_numpy()
        rows.append(pd.DataFrame({"day": day_index.to_numpy(), "component_item_id": component, column_name: future}))
    return pd.concat(rows, ignore_index=True)


def metric(real: pd.Series, sim: pd.Series) -> dict[str, float]:
    diff = sim - real
    corr = real.corr(sim) if len(real) > 1 and sim.std() > 0 else float("nan")
    denom = float((sim * sim).sum())
    calibrated_scale = float((real * sim).sum() / denom) if denom else float("nan")
    calibrated = sim * calibrated_scale if not math.isnan(calibrated_scale) else sim * 0.0
    calibrated_diff = calibrated - real
    return {
        "real_mean": float(real.mean()),
        "sim_mean": float(sim.mean()),
        "bias": float(diff.mean()),
        "mae": float(diff.abs().mean()),
        "corr": float(corr),
        "sim_over_real": float(sim.mean() / real.mean()) if real.mean() else float("nan"),
        "calibrated_scale": calibrated_scale,
        "calibrated_sim_mean": float(calibrated.mean()),
        "calibrated_bias": float(calibrated_diff.mean()),
        "calibrated_mae": float(calibrated_diff.abs().mean()),
    }


def evaluate_component_rules(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snapshots = real_component_snapshots()
    components = set(bom_components())
    max_day = int(max(snapshots["sim_day"].max(), 1824))
    stock = component_stock(run_dir, components)
    consumption = component_consumption(run_dir, components)

    policy = source_policy()
    leads = fia_leads()
    lead_policy = pd.merge(leads, policy, on="item_id", how="outer").fillna(0.0)
    lead_policy["lead_only_horizon"] = lead_policy["lead_days"].round().clip(lower=0).astype(int)
    lead_policy["safety_only_horizon"] = lead_policy["safety_time_days"].round().clip(lower=0).astype(int)
    lead_policy["lead_plus_safety_horizon"] = (
        lead_policy["lead_days"] + lead_policy["safety_time_days"]
    ).round().clip(lower=0).astype(int)

    enriched = stock.copy()
    for horizon in (7, 14, 21, 30, 45, 60, 90, 120, 180, 270, 365, 540, 730):
        needs = future_need_table(consumption, components, max_day=max_day, horizon=horizon)
        enriched = enriched.merge(needs, on=["day", "component_item_id"], how="left")
        need_col = f"need_next_{horizon}d_qty"
        enriched[f"physical_minus_future_need_{horizon}d_eur"] = (
            (enriched["stock_qty"] - enriched[need_col].fillna(0.0)).clip(lower=0.0)
            * enriched["unit_value_eur"]
        )
        enriched[f"useful_for_future_need_{horizon}d_eur"] = (
            enriched[["stock_qty", need_col]].min(axis=1).clip(lower=0.0) * enriched["unit_value_eur"]
        )

    horizon_maps = {
        "lead_only": dict(zip(lead_policy["item_id"], lead_policy["lead_only_horizon"])),
        "safety_only": dict(zip(lead_policy["item_id"], lead_policy["safety_only_horizon"])),
        "lead_plus_safety": dict(zip(lead_policy["item_id"], lead_policy["lead_plus_safety_horizon"])),
    }
    for label, horizons in horizon_maps.items():
        needs = future_need_by_item_horizon(
            consumption,
            components,
            max_day=max_day,
            horizons_by_item=horizons,
            column_name=f"need_{label}_qty",
        )
        enriched = enriched.merge(needs, on=["day", "component_item_id"], how="left")
        need_col = f"need_{label}_qty"
        enriched[f"physical_minus_future_need_{label}_eur"] = (
            (enriched["stock_qty"] - enriched[need_col].fillna(0.0)).clip(lower=0.0)
            * enriched["unit_value_eur"]
        )
        enriched[f"useful_for_future_need_{label}_eur"] = (
            enriched[["stock_qty", need_col]].min(axis=1).clip(lower=0.0) * enriched["unit_value_eur"]
        )

    enriched["physical_stock_value_eur"] = enriched["stock_value_eur"]
    enriched["mrp_target_excess_eur"] = enriched["immobilized_value_eur"]

    value_cols = [
        "physical_stock_value_eur",
        "mrp_target_excess_eur",
    ] + [
        col
        for col in enriched.columns
        if col.startswith("physical_minus_future_need_") or col.startswith("useful_for_future_need_")
    ]

    by_day = enriched.groupby("day", as_index=False)[value_cols].sum()
    joined = snapshots.merge(by_day, left_on="sim_day", right_on="day", how="left", suffixes=("", "_sim"))

    metrics = []
    for col in value_cols:
        valid = joined[["real_value_eur", col]].dropna()
        m = metric(valid["real_value_eur"], valid[col])
        m["rule"] = col
        metrics.append(m)
    metrics_df = pd.DataFrame(metrics).sort_values(["mae", "rule"])

    component_weekly = snapshots[["snapshot_dt", "sim_day", "real_value_eur"]].merge(
        enriched[enriched["day"].isin(snapshots["sim_day"])],
        left_on="sim_day",
        right_on="day",
        how="left",
    )
    return metrics_df, joined, component_weekly


def evaluate_pf_rules(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshots = real_pf_snapshots()
    output = pd.read_csv(run_dir / "data" / "production_output_products_daily.csv")
    dc = pd.read_csv(run_dir / "data" / "production_dc_stocks_daily.csv")
    output = output[(output["item_id"] == PRODUCT_ITEM) & (output["node_id"] == FACTORY)].copy()
    dc = dc[(dc["item_id"] == PRODUCT_ITEM) & (dc["node_id"] == DC)].copy()
    output = output[["day", "stock_end_of_day"]].rename(columns={"stock_end_of_day": "factory_pf_stock_qty"})
    dc = dc[["day", "stock_end_of_day"]].rename(columns={"stock_end_of_day": "dc_pf_stock_qty"})
    stock = pd.merge(output, dc, on="day", how="outer").fillna(0.0)
    stock["total_pf_stock_qty"] = stock["factory_pf_stock_qty"] + stock["dc_pf_stock_qty"]

    service = pd.read_csv(run_dir / "data" / "production_demand_service_daily.csv")
    service = service[(service["item_id"] == PRODUCT_ITEM) & (service["node_id"] == "C-XXXXX")].copy()
    service = service[["day", "demand_qty", "served_qty", "backlog_end_qty"]]
    stock = stock.merge(service, on="day", how="left").fillna(0.0)

    joined = snapshots.merge(stock, left_on="sim_day", right_on="day", how="left", suffixes=("", "_sim"))
    joined["implied_pf_unit_value_eur"] = joined["real_value_eur"] / joined["total_pf_stock_qty"].replace(0.0, pd.NA)
    median_unit = float(joined["implied_pf_unit_value_eur"].median())
    joined["physical_pf_value_at_median_unit_eur"] = joined["total_pf_stock_qty"] * median_unit

    metrics = pd.DataFrame(
        [
            {
                "rule": "physical_pf_stock_at_median_implied_unit_value",
                **metric(joined["real_value_eur"], joined["physical_pf_value_at_median_unit_eur"]),
                "median_unit_value_eur": median_unit,
                "implied_unit_value_min": float(joined["implied_pf_unit_value_eur"].min()),
                "implied_unit_value_max": float(joined["implied_pf_unit_value_eur"].max()),
                "implied_unit_value_cv": float(
                    joined["implied_pf_unit_value_eur"].std() / joined["implied_pf_unit_value_eur"].mean()
                ),
            }
        ]
    )
    return metrics, joined


def evaluate_safety_delay_view(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snapshots = real_component_snapshots()
    components = set(bom_components())
    stock = component_stock(run_dir, components)
    stock = stock[stock["day"].isin(set(snapshots["sim_day"].astype(int)))].copy()

    safety = pd.read_csv(run_dir / "reports" / "mrp_safety_stock_reference.csv")
    safety = safety[(safety["scope"] == "input_material") & (safety["node_id"] == FACTORY)].copy()
    ref = safety[
        [
            "item_id",
            "uom",
            "safety_time_days",
            "planned_avg_daily_demand_qty",
            "observed_avg_daily_flow_qty",
            "stock_equiv_safety_time_qty",
            "explicit_safety_stock_qty",
            "effective_reference_stock_qty",
        ]
    ].rename(columns={"item_id": "component_item_id"})
    stock = stock.merge(ref, on="component_item_id", how="left")
    for col in [
        "safety_time_days",
        "planned_avg_daily_demand_qty",
        "observed_avg_daily_flow_qty",
        "stock_equiv_safety_time_qty",
        "explicit_safety_stock_qty",
        "effective_reference_stock_qty",
        "unit_value_eur",
        "stock_qty",
        "stock_value_eur",
    ]:
        stock[col] = pd.to_numeric(stock[col], errors="coerce").fillna(0.0)
    stock["safety_delay_value_eur"] = stock["stock_equiv_safety_time_qty"] * stock["unit_value_eur"]
    stock["effective_reference_value_eur"] = stock["effective_reference_stock_qty"] * stock["unit_value_eur"]
    stock["excess_above_safety_delay_eur"] = (
        stock["stock_qty"] - stock["stock_equiv_safety_time_qty"]
    ).clip(lower=0.0) * stock["unit_value_eur"]
    stock["excess_above_effective_reference_eur"] = (
        stock["stock_qty"] - stock["effective_reference_stock_qty"]
    ).clip(lower=0.0) * stock["unit_value_eur"]

    summary = (
        stock.groupby("component_item_id", as_index=False)
        .agg(
            safety_days=("safety_time_days", "median"),
            planned_avg_daily_demand_qty=("planned_avg_daily_demand_qty", "median"),
            observed_avg_daily_flow_qty=("observed_avg_daily_flow_qty", "median"),
            stock_equiv_safety_time_qty=("stock_equiv_safety_time_qty", "median"),
            explicit_safety_stock_qty=("explicit_safety_stock_qty", "median"),
            effective_reference_stock_qty=("effective_reference_stock_qty", "median"),
            unit_value_eur=("unit_value_eur", "median"),
            avg_stock_value_eur=("stock_value_eur", "mean"),
            safety_delay_value_eur=("safety_delay_value_eur", "mean"),
            effective_reference_value_eur=("effective_reference_value_eur", "mean"),
            excess_above_safety_delay_eur=("excess_above_safety_delay_eur", "mean"),
            excess_above_effective_reference_eur=("excess_above_effective_reference_eur", "mean"),
        )
        .sort_values("avg_stock_value_eur", ascending=False)
    )
    summary["share_above_safety_pct"] = (
        summary["excess_above_safety_delay_eur"] / summary["avg_stock_value_eur"].replace(0.0, pd.NA) * 100.0
    )

    by_day = stock.groupby("day", as_index=False).agg(
        stock_value_eur=("stock_value_eur", "sum"),
        safety_delay_value_eur=("safety_delay_value_eur", "sum"),
        effective_reference_value_eur=("effective_reference_value_eur", "sum"),
        excess_above_safety_delay_eur=("excess_above_safety_delay_eur", "sum"),
        excess_above_effective_reference_eur=("excess_above_effective_reference_eur", "sum"),
    )
    joined = snapshots.merge(by_day, left_on="sim_day", right_on="day", how="left")
    metrics = []
    for col in [
        "stock_value_eur",
        "safety_delay_value_eur",
        "effective_reference_value_eur",
        "excess_above_safety_delay_eur",
        "excess_above_effective_reference_eur",
    ]:
        m = metric(joined["real_value_eur"], joined[col])
        m["rule"] = col
        metrics.append(m)
    return summary, joined, pd.DataFrame(metrics).sort_values("mae")


def write_report(
    component_metrics: pd.DataFrame,
    component_joined: pd.DataFrame,
    component_weekly: pd.DataFrame,
    pf_metrics: pd.DataFrame,
    pf_joined: pd.DataFrame,
    safety_summary: pd.DataFrame,
    safety_joined: pd.DataFrame,
    safety_metrics: pd.DataFrame,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    component_metrics.to_csv(OUTPUT_DIR / "component_rule_metrics.csv", index=False)
    component_joined.to_csv(OUTPUT_DIR / "component_rule_snapshot_comparison.csv", index=False)
    component_weekly.to_csv(OUTPUT_DIR / "component_rule_snapshot_by_component.csv", index=False)
    pf_metrics.to_csv(OUTPUT_DIR / "pf_rule_metrics.csv", index=False)
    pf_joined.to_csv(OUTPUT_DIR / "pf_rule_snapshot_comparison.csv", index=False)
    safety_summary.to_csv(OUTPUT_DIR / "component_safety_delay_summary.csv", index=False)
    safety_joined.to_csv(OUTPUT_DIR / "component_safety_delay_snapshot_comparison.csv", index=False)
    safety_metrics.to_csv(OUTPUT_DIR / "component_safety_delay_metrics.csv", index=False)

    best = component_metrics.iloc[0].to_dict()
    first_week = first_week_check(DEFAULT_RUN_DIR)
    best_calibrated = component_metrics.sort_values(["calibrated_mae", "rule"]).iloc[0].to_dict()
    physical = component_metrics[component_metrics["rule"] == "physical_stock_value_eur"].iloc[0].to_dict()
    mrp = component_metrics[component_metrics["rule"] == "mrp_target_excess_eur"].iloc[0].to_dict()
    best_useful = component_metrics[
        component_metrics["rule"].astype(str).str.startswith("useful_for_future_need_")
    ].iloc[0].to_dict()
    best_excess = component_metrics[
        component_metrics["rule"].astype(str).str.startswith("physical_minus_future_need_")
    ].iloc[0].to_dict()
    pf = pf_metrics.iloc[0].to_dict()

    top_components = (
        component_weekly.groupby("component_item_id", as_index=False)
        .agg(
            avg_stock_value_eur=("stock_value_eur", "mean"),
            avg_mrp_excess_eur=("mrp_target_excess_eur", "mean"),
            avg_stock_qty=("stock_qty", "mean"),
            unit_value_eur=("unit_value_eur", "median"),
        )
        .sort_values("avg_stock_value_eur", ascending=False)
        .head(8)
    )
    lead_policy = pd.merge(fia_leads(), source_policy(), on="item_id", how="outer").fillna(0.0)
    top_components_with_policy = top_components.merge(
        lead_policy,
        left_on="component_item_id",
        right_on="item_id",
        how="left",
    ).fillna(0.0)
    safety_lookup = {row["rule"]: row for _, row in safety_metrics.iterrows()}
    safety_value = safety_lookup["safety_delay_value_eur"]
    safety_excess = safety_lookup["excess_above_safety_delay_eur"]
    effective_ref = safety_lookup["effective_reference_value_eur"]

    lines = [
        "# Inference regle stock immobilise - 268091",
        "",
        "## Conclusion",
        "",
        (
            "- La regle qui colle le mieux aux photos reelles n'est pas le stock physique total. "
            "Le stock physique simule moyen reste au-dessus du reel, mais dans le meme ordre de grandeur."
        ),
        (
            f"- Stock physique composants simule: {euro(physical['sim_mean'])} vs reel "
            f"{euro(physical['real_mean'])}, soit x{physical['sim_over_real']:.1f}."
        ),
        (
            f"- Excedent au-dessus cible MRP: {euro(mrp['sim_mean'])}, encore x{mrp['sim_over_real']:.1f}."
        ),
        (
            f"- Meilleur exces teste: `{best_excess['rule']}` -> {euro(best_excess['sim_mean'])}, "
            f"MAE {euro(best_excess['mae'])}."
        ),
        (
            f"- Meilleur stock utile teste: `{best_useful['rule']}` -> {euro(best_useful['sim_mean'])}, "
            f"MAE {euro(best_useful['mae'])}."
        ),
        (
            f"- Meilleure regle avec facteur de perimetre: `{best_calibrated['rule']}` x "
            f"{best_calibrated['calibrated_scale']:.2f} -> MAE {euro(best_calibrated['calibrated_mae'])}."
        ),
        (
            f"- Controle temporel premiere semaine: stock composant source 01/01 {euro(first_week['source_opening_component_value'])}; "
            f"stock simule fin J5 {euro(first_week['sim_day5_component_value'])}; "
            f"premiere photo reelle 06/01 {euro(first_week['first_real_component_value'])}."
        ),
        "",
        "Lecture metier: avec les donnees disponibles, le KPI reel Cos ne ressemble ni a tout le stock physique, "
        "ni a un simple excedent au-dessus du delai fournisseur + delai securite. Il ressemble davantage a un "
        "sous-ensemble finance/statut du stock, ou a un stock utile limite a un horizon court. Le CSV reel etant "
        "agrege, la vraie regle SAP/finance ne peut pas etre prouvee sans detail article/statut/lot.",
        "",
        (
            "Point important sur l'hypothese `besoin pendant delai previsionnel + delai de securite`: "
            f"elle ne donne que {euro(best_useful['sim_mean']) if best_useful['rule'] == 'useful_for_future_need_lead_plus_safety_eur' else euro(component_metrics[component_metrics['rule'] == 'useful_for_future_need_lead_plus_safety_eur'].iloc[0]['sim_mean'])} "
            "en moyenne si on ne garde que le stock utile pendant cet horizon. Elle est donc trop basse pour expliquer "
            "directement le KPI reel observe."
        ),
        (
            f"Point sur le delai de securite seul: la couverture des delais de securite composants vaut "
            f"{euro(safety_value['sim_mean'])} en moyenne, alors que le reel vaut {euro(safety_value['real_mean'])}. "
            f"Le stock au-dessus de cette couverture vaut {euro(safety_excess['sim_mean'])}, donc trop haut."
        ),
        "",
        "## Meilleures regles candidates composants",
        "",
        "| Rang | Regle | Reel moyen | Simulation moyenne | Ratio sim/reel | MAE | Correlation |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for idx, row in component_metrics.head(12).reset_index(drop=True).iterrows():
        lines.append(
            f"| {idx + 1} | `{row['rule']}` | {euro(row['real_mean'])} | {euro(row['sim_mean'])} | "
            f"{row['sim_over_real']:.2f} | {euro(row['mae'])} | {row['corr']:.2f} |"
        )

    lines += [
        "",
        "## Controle temporel premiere semaine",
        "",
        "Cette section corrige un point de lecture important: le stock MRP est photographie le 01/01, "
        "alors que le premier KPI reel immobilise est photographie le lundi 06/01 vers 00:06. "
        "Si J0 = 01/01, la photo est surtout comparable a la fin de J4; J5 n'a quasiment pas commence.",
        "",
        "| Lecture | Valeur / quantite |",
        "| --- | ---: |",
        f"| Stock composant source 01/01 | {euro(first_week['source_opening_component_value'])} |",
        f"| Stock composant simule fin J0 | {euro(first_week['sim_day0_end_component_value'])} |",
        f"| Stock composant simule fin J5, juste avant photo 06/01 | {euro(first_week['sim_day5_component_value'])} |",
        f"| KPI reel composants immobilises 06/01 | {euro(first_week['first_real_component_value'])} |",
        f"| Production simulee J0-J5 | {first_week['produced_first_week_qty']:,.0f} PF |".replace(",", " "),
        f"| Valeur BOM consommee par cette production | {euro(first_week['bom_value_sim_first_week_production'])} |",
        f"| Demande source semaine 1, ligne Excel | {first_week['source_week1_demand_qty']:,.0f} PF |".replace(",", " "),
        f"| Demande source uniformisee | {first_week['source_week1_daily_uniform_qty']:,.0f} PF/j |".replace(",", " "),
        f"| Demande source proratee J0-J4 avant photo 06/01 | {first_week['source_week1_to_photo_5d_qty']:,.0f} PF |".replace(",", " "),
        f"| Demande service simulee lissee J0-J4 | {first_week['sim_smoothed_demand_d0_d4_qty']:,.0f} PF |".replace(",", " "),
        f"| Demande service simulee lissee J0-J5 | {first_week['sim_smoothed_demand_d0_d5_qty']:,.0f} PF |".replace(",", " "),
        f"| Demande service simulee lissee J0-J6 | {first_week['sim_smoothed_demand_d0_d6_qty']:,.0f} PF |".replace(",", " "),
        f"| Servi simule J0-J4 | {first_week['sim_served_d0_d4_qty']:,.0f} PF |".replace(",", " "),
        f"| Backlog simule fin J4 | {first_week['sim_backlog_end_d4_qty']:,.0f} PF |".replace(",", " "),
        f"| Valeur BOM equivalente demande source J0-J4 | {euro(first_week['bom_value_source_week1_to_photo_5d'])} |",
        f"| Valeur BOM equivalente demande simulee lissee J0-J4 | {euro(first_week['bom_value_sim_smoothed_demand_d0_d4'])} |",
        "",
        "Conclusion temporelle: la premiere semaine existe bien, mais il faut distinguer la ligne hebdo source "
        "et la demande lissee utilisee par le simulateur. Meme avec la demande lissee J0-J4, la consommation BOM "
        "reste de quelques milliers d'euros; elle ne peut pas expliquer seule "
        "le passage de 727 kEUR a 221 kEUR. L'ecart pointe donc surtout vers une difference de definition du KPI immobilise "
        "ou de perimetre/statut du stock, pas seulement vers un decalage de date.",
    ]

    lines += [
        "",
        "## Lecture par delai de securite composants",
        "",
        "Cette lecture teste explicitement si le KPI reel peut correspondre a la couverture des delais de securite MRP composants.",
        "",
        "| Lecture | Reel moyen | Simulation moyenne | Ratio sim/reel | MAE |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, row in safety_metrics.iterrows():
        lines.append(
            f"| `{row['rule']}` | {euro(row['real_mean'])} | {euro(row['sim_mean'])} | "
            f"{row['sim_over_real']:.2f} | {euro(row['mae'])} |"
        )
    lines += [
        "",
        "Conclusion: le delai de securite composant seul est trop faible pour expliquer le stock immobilise reel; "
        "l'excedent au-dessus du delai de securite est trop eleve. Le KPI reel semble donc filtrer une partie du "
        "stock excedentaire, plutot que prendre toute la couverture de securite ou tout le surplus.",
        "",
        "| Composant | Delai securite | Besoin moyen/j | Stock equiv. securite | Stock physique moyen | Couverture securite | Excedent au-dessus securite |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in safety_summary.head(10).iterrows():
        lines.append(
            f"| {str(row['component_item_id']).replace('item:', '')} | "
            f"{row['safety_days']:.0f} j | "
            f"{row['planned_avg_daily_demand_qty']:,.1f} | "
            f"{row['stock_equiv_safety_time_qty']:,.1f} | "
            f"{euro(row['avg_stock_value_eur'])} | "
            f"{euro(row['safety_delay_value_eur'])} | "
            f"{euro(row['excess_above_safety_delay_eur'])} |".replace(",", " ")
        )

    lines += [
        "",
        "## Regles candidates avec facteur de perimetre",
        "",
        "Lecture: ce test repond a la question `la source reelle couvre-t-elle une fraction stable de cette famille de stock ?`.",
        "",
        "| Rang | Regle | Facteur | Simulation calibree | MAE calibree | Correlation brute |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    calibrated_rank = component_metrics.sort_values(["calibrated_mae", "rule"]).head(12).reset_index(drop=True)
    for idx, row in calibrated_rank.iterrows():
        lines.append(
            f"| {idx + 1} | `{row['rule']}` | {row['calibrated_scale']:.2f} | "
            f"{euro(row['calibrated_sim_mean'])} | {euro(row['calibrated_mae'])} | {row['corr']:.2f} |"
        )

    lines += [
        "",
        "## Composants qui portent le stock physique simule",
        "",
        "| Composant | Valeur physique moyenne | Excedent MRP moyen | Qte moyenne | Prix unitaire |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, row in top_components.iterrows():
        lines.append(
            f"| {str(row['component_item_id']).replace('item:', '')} | {euro(row['avg_stock_value_eur'])} | "
            f"{euro(row['avg_mrp_excess_eur'])} | {row['avg_stock_qty']:,.1f} | "
            f"{row['unit_value_eur']:.4g} |".replace(",", " ")
        )

    lines += [
        "",
        "## Delais source sur les principaux composants",
        "",
        "| Composant | Lead FIA median | Lead min-max | Delai securite MRP | Valeur physique moyenne |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, row in top_components_with_policy.iterrows():
        lines.append(
            f"| {str(row['component_item_id']).replace('item:', '')} | "
            f"{parse_float(row.get('lead_days')):.0f} j | "
            f"{parse_float(row.get('min_lead_days')):.0f}-{parse_float(row.get('max_lead_days')):.0f} j | "
            f"{parse_float(row.get('safety_time_days')):.0f} j | "
            f"{euro(row['avg_stock_value_eur'])} |"
        )

    lines += [
        "",
        "## Produit fini 268091",
        "",
        (
            "Pour le PF, le CSV reel donne une valeur mais pas la quantite. J'ai donc compare la valeur reelle "
            "au stock PF simule en usine + DC via un cout unitaire implicite median."
        ),
        "",
        "| Lecture PF | Reel moyen | Simulation moyenne | MAE | Cout unitaire implicite median | Stabilite cout implicite |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| stock PF physique x cout implicite | {euro(pf['real_mean'])} | {euro(pf['sim_mean'])} | "
            f"{euro(pf['mae'])} | {pf['median_unit_value_eur']:.4f} EUR/UN | "
            f"CV {pct(pf['implied_unit_value_cv'])} |"
        ),
        "",
        "Si ce cout implicite est stable, le stock PF immobilise est probablement une valorisation simple du stock PF "
        "physique. S'il varie fortement, le KPI PF applique aussi une regle d'immobilisation ou de valorisation que "
        "nous n'avons pas dans les CSV.",
        "",
        "## Ce qu'il manque pour conclure sans ambiguite",
        "",
        "- Detail du `Stock_Composants_Immobilise_Cos.csv` par article, magasin/statut, lot, age et prix.",
        "- Quantite projetee disponible PF, pas seulement le compteur de semaines de rupture du fichier `Dispo_PF_Projete.csv`.",
        "- Regle finance/SAP exacte: stock libre seulement, stock qualite/bloque, stock lent, stock au-dessus couverture, ou autre filtre.",
        "",
        "## Sorties generees",
        "",
        "- `component_rule_metrics.csv`",
        "- `component_rule_snapshot_comparison.csv`",
        "- `component_rule_snapshot_by_component.csv`",
        "- `pf_rule_metrics.csv`",
        "- `pf_rule_snapshot_comparison.csv`",
        "- `component_safety_delay_summary.csv`",
        "- `component_safety_delay_snapshot_comparison.csv`",
        "- `component_safety_delay_metrics.csv`",
    ]

    path = OUTPUT_DIR / "infer_268091_immobilized_stock_rule.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    run_dir = DEFAULT_RUN_DIR
    component_metrics, component_joined, component_weekly = evaluate_component_rules(run_dir)
    pf_metrics, pf_joined = evaluate_pf_rules(run_dir)
    safety_summary, safety_joined, safety_metrics = evaluate_safety_delay_view(run_dir)
    report = write_report(
        component_metrics,
        component_joined,
        component_weekly,
        pf_metrics,
        pf_joined,
        safety_summary,
        safety_joined,
        safety_metrics,
    )
    print(report)
    print(component_metrics.head(8).to_string(index=False))
    print(pf_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
