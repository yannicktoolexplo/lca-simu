"""Audit the Pharma component-stock KPI rule for PF 268967.

The real KPI file ``Stock_Composants*_Pharma.csv`` is an aggregate financial
snapshot. This script compares it with several simulation-derived readings for
PF 268967 / D1430:

- physical component stock value;
- direct supplier component stock excluding internal PFI rollups;
- useful stock vs MRP/coverage thresholds;
- immobilized/excess stock;
- component-family and component-subset candidates.

The goal is diagnostic: identify whether the real KPI behaves like physical
stock, useful stock, excess stock, or a narrower finance perimeter.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

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
    / "audit_268967_pharma_stock_rule"
)

START_DATE = date(2025, 1, 1)
PRODUCT_CODE = "268967"
PRODUCT_ITEM_ID = f"item:{PRODUCT_CODE}"
FACTORY = "M-1430"

INTERNAL_VALUE_SOURCES = {"internal_bom_rollup", "internal_transfer_bom_rollup"}
VALUE_COLUMNS = {
    "stock": "stock_value_eur",
    "useful": "useful_value_eur",
    "immobilized": "immobilized_value_eur",
}


@dataclass(frozen=True)
class Candidate:
    rule: str
    threshold_mode: str
    value_kind: str
    item_filter: str
    include_internal_rollup: bool
    series: pd.DataFrame


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(" ", "").replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one source file for {pattern}, found {matches}")
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


def markdown_table(df: pd.DataFrame, columns: list[str], *, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "_aucune donnee_"
    rows = df[columns].copy()
    for col in rows.columns:
        if pd.api.types.is_float_dtype(rows[col]):
            rows[col] = rows[col].map(lambda value: f"{float(value):.2f}" if pd.notna(value) else "")
        else:
            rows[col] = rows[col].fillna("").astype(str)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(row[col]) for col in columns) + " |" for _, row in rows.iterrows()]
    return "\n".join([header, sep, *body])


def read_real_pharma_snapshots() -> pd.DataFrame:
    df = read_source_csv("Stock_Composants*Pharma.csv").copy()
    date_col = next((col for col in df.columns if "date" in col.lower()), df.columns[0])
    value_col = next((col for col in df.columns if "valeur" in col.lower() or "stock" in col.lower()), df.columns[1])
    df["snapshot_dt"] = pd.to_datetime(df[date_col])
    df["day"] = (df["snapshot_dt"].dt.date - START_DATE).apply(lambda delta: delta.days)
    # Real snapshots are around Monday 00:05. Compare them with previous
    # simulated end-of-day stocks.
    df["sim_day"] = (df["day"] - 1).clip(lower=0).astype(int)
    df["real_value_eur"] = df[value_col].map(parse_float)
    return df[["snapshot_dt", "day", "sim_day", "real_value_eur"]].sort_values("snapshot_dt")


def read_bom_metadata() -> pd.DataFrame:
    bom = pd.read_excel(source_file("268967.xlsx"), sheet_name="BOM")
    product_col = "Produit Fini"
    comp_col = next(col for col in bom.columns if "composante" in col.lower())
    type_col = next(
        (
            col
            for col in bom.columns
            if "type composant" in col.lower()
            or col.strip().lower() in {"type", "type composant", "type de composant"}
        ),
        None,
    )
    qty_col = next((col for col in bom.columns if "qt" in col.lower() and "compos" in col.lower()), None)
    uom_col = next((col for col in bom.columns if "unite" in col.lower() or "unit" in col.lower()), None)

    bom = bom[bom[product_col].astype(str).str.strip() == PRODUCT_CODE].copy()
    bom["component_item_id"] = bom[comp_col].map(item_id)
    bom["component_code"] = bom["component_item_id"].str.replace("item:", "", regex=False)
    bom["component_type"] = bom[type_col].astype(str).str.strip() if type_col else ""
    bom["bom_qty_per_1000"] = bom[qty_col].map(parse_float) if qty_col else 0.0
    bom["bom_uom"] = bom[uom_col].astype(str).str.strip() if uom_col else ""

    fia = pd.read_excel(source_file("268967.xlsx"), sheet_name="FIA")
    item_col = next(col for col in fia.columns if "article" in col.lower())
    supplier_col = next((col for col in fia.columns if "fournisseur" in col.lower()), None)
    amount_col = next((col for col in fia.columns if "montant" in col.lower()), None)
    base_col = next((col for col in fia.columns if "base" in col.lower() and "prix" in col.lower()), None)
    lead_col = next((col for col in fia.columns if "previsionnel" in col.lower() or "visionnel" in col.lower()), None)
    std_col = next((col for col in fia.columns if "standard" in col.lower()), None)
    fia["component_item_id"] = fia[item_col].map(item_id)
    if amount_col and base_col:
        fia["unit_price_eur"] = fia[amount_col].map(parse_float) / fia[base_col].map(parse_float).replace(0.0, pd.NA)
    else:
        fia["unit_price_eur"] = 0.0
    fia["lead_days"] = fia[lead_col].map(parse_float) if lead_col else 0.0
    fia["standard_lot_qty"] = fia[std_col].map(parse_float) if std_col else 0.0
    agg = (
        fia.groupby("component_item_id", as_index=False)
        .agg(
            supplier_count=(supplier_col, "nunique") if supplier_col else ("component_item_id", "size"),
            source_unit_price_eur=("unit_price_eur", "median"),
            lead_days=("lead_days", "median"),
            standard_lot_qty=("standard_lot_qty", "median"),
        )
    )
    return bom.merge(agg, on="component_item_id", how="left")


def read_component_daily(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "data" / "component_immobilized_stock_components_daily.csv"
    if not path.exists():
        raise FileNotFoundError(path)
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
        "value_source",
    ]
    df = pd.read_csv(path, usecols=usecols)
    df = df[
        (df["product_code"].astype(str) == PRODUCT_CODE)
        & (df["node_id"].astype(str) == FACTORY)
    ].copy()
    numeric_cols = [
        "day",
        "stock_qty",
        "useful_qty",
        "immobilized_qty",
        "unit_value_eur",
        "stock_value_eur",
        "useful_value_eur",
        "immobilized_value_eur",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["day"] = df["day"].astype(int)
    return df


def read_plan_events(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "data" / "production_plan_events.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[
        (df["node_id"].astype(str) == FACTORY)
        & (df["output_item_id"].astype(str) == PRODUCT_ITEM_ID)
    ].copy()


def read_input_stock_flows(run_dir: Path, components: Iterable[str]) -> pd.DataFrame:
    stock_path = run_dir / "data" / "production_input_stocks_daily.csv"
    arrivals_path = run_dir / "data" / "production_input_replenishment_arrivals_daily.csv"
    stock = pd.read_csv(stock_path)
    stock = stock[
        (stock["node_id"].astype(str) == FACTORY)
        & (stock["item_id"].astype(str).isin(set(components)))
    ].copy()
    for col in ["stock_before_production", "stock_end_of_day"]:
        stock[col] = pd.to_numeric(stock[col], errors="coerce").fillna(0.0)

    arrivals = pd.read_csv(arrivals_path)
    arrivals = arrivals[
        (arrivals["node_id"].astype(str) == FACTORY)
        & (arrivals["item_id"].astype(str).isin(set(components)))
    ].copy()
    arrivals["arrived_qty"] = pd.to_numeric(arrivals["arrived_qty"], errors="coerce").fillna(0.0)
    arrivals_by_item = arrivals.groupby("item_id", as_index=False).agg(total_arrivals_qty=("arrived_qty", "sum"))

    first = stock.sort_values("day").groupby("item_id", as_index=False).first()
    last = stock.sort_values("day").groupby("item_id", as_index=False).last()
    out = first[["item_id", "stock_before_production"]].rename(columns={"stock_before_production": "initial_qty"})
    out = out.merge(last[["item_id", "stock_end_of_day"]].rename(columns={"stock_end_of_day": "final_qty"}), on="item_id")
    out = out.merge(arrivals_by_item, on="item_id", how="left").fillna({"total_arrivals_qty": 0.0})
    out["implied_consumption_qty"] = out["initial_qty"] + out["total_arrivals_qty"] - out["final_qty"]
    return out


def series_for(
    df: pd.DataFrame,
    *,
    threshold_mode: str,
    value_kind: str,
    items: set[str] | None,
    include_internal_rollup: bool,
) -> pd.DataFrame:
    value_col = VALUE_COLUMNS[value_kind]
    data = df[df["threshold_mode"] == threshold_mode].copy()
    if not include_internal_rollup:
        data = data[~data["value_source"].astype(str).isin(INTERNAL_VALUE_SOURCES)]
    if items is not None:
        data = data[data["component_item_id"].isin(items)]
    return (
        data.groupby("day", as_index=False)
        .agg(sim_value_eur=(value_col, "sum"))
        .sort_values("day")
    )


def candidate_metrics(real: pd.DataFrame, candidate: Candidate) -> dict[str, Any]:
    merged = real.merge(candidate.series, left_on="sim_day", right_on="day", how="inner")
    if merged.empty:
        return {
            "rule": candidate.rule,
            "threshold_mode": candidate.threshold_mode,
            "value_kind": candidate.value_kind,
            "item_filter": candidate.item_filter,
            "include_internal_rollup": candidate.include_internal_rollup,
            "snapshot_count": 0,
        }
    error = merged["sim_value_eur"] - merged["real_value_eur"]
    real_mean = float(merged["real_value_eur"].mean())
    sim_mean = float(merged["sim_value_eur"].mean())
    corr = merged["sim_value_eur"].corr(merged["real_value_eur"])
    return {
        "rule": candidate.rule,
        "threshold_mode": candidate.threshold_mode,
        "value_kind": candidate.value_kind,
        "item_filter": candidate.item_filter,
        "include_internal_rollup": candidate.include_internal_rollup,
        "snapshot_count": int(len(merged)),
        "real_mean_eur": real_mean,
        "sim_mean_eur": sim_mean,
        "bias_eur": float(error.mean()),
        "bias_pct_real_mean": float(error.mean() / real_mean) if real_mean else math.nan,
        "mae_eur": float(error.abs().mean()),
        "mae_pct_real_mean": float(error.abs().mean() / real_mean) if real_mean else math.nan,
        "corr": float(corr) if not pd.isna(corr) else math.nan,
        "first_real_eur": float(merged.iloc[0]["real_value_eur"]),
        "first_sim_eur": float(merged.iloc[0]["sim_value_eur"]),
        "first_error_eur": float(merged.iloc[0]["sim_value_eur"] - merged.iloc[0]["real_value_eur"]),
        "min_sim_eur": float(merged["sim_value_eur"].min()),
        "max_sim_eur": float(merged["sim_value_eur"].max()),
    }


def build_candidates(component_daily: pd.DataFrame, bom: pd.DataFrame) -> list[Candidate]:
    all_items = set(bom["component_item_id"])
    mp_items = set(bom[bom["component_type"].str.upper().str.contains("MP", na=False)]["component_item_id"])
    pack_items = all_items - mp_items
    nonzero_items = set(
        component_daily[
            (component_daily["threshold_mode"] == "target_stock")
            & (~component_daily["value_source"].isin(INTERNAL_VALUE_SOURCES))
            & (component_daily["stock_value_eur"].abs() > 0.0001)
        ]["component_item_id"].unique()
    )

    filters: dict[str, set[str] | None] = {
        "all_components": all_items,
        "mp_only": mp_items,
        "packaging_only": pack_items,
        "nonzero_direct_items": nonzero_items,
    }
    for item in sorted(nonzero_items):
        filters[f"only_{item.replace('item:', '')}"] = {item}
    for item in sorted(nonzero_items):
        filters[f"exclude_{item.replace('item:', '')}"] = nonzero_items - {item}

    candidates: list[Candidate] = []
    for threshold_mode in sorted(component_daily["threshold_mode"].dropna().unique()):
        for value_kind in VALUE_COLUMNS:
            for filter_name, items in filters.items():
                for include_internal in (False, True):
                    if include_internal and filter_name not in {"all_components", "nonzero_direct_items"}:
                        continue
                    label = (
                        f"{threshold_mode}/{value_kind}/{filter_name}/"
                        f"{'with_internal' if include_internal else 'direct_only'}"
                    )
                    candidates.append(
                        Candidate(
                            rule=label,
                            threshold_mode=str(threshold_mode),
                            value_kind=value_kind,
                            item_filter=filter_name,
                            include_internal_rollup=include_internal,
                            series=series_for(
                                component_daily,
                                threshold_mode=str(threshold_mode),
                                value_kind=value_kind,
                                items=items,
                                include_internal_rollup=include_internal,
                            ),
                        )
                    )

    # Exhaustive direct component subsets are useful to detect a hidden finance
    # perimeter. Keep them limited to priced/nonzero direct items.
    direct_items = sorted(nonzero_items)
    for threshold_mode in sorted(component_daily["threshold_mode"].dropna().unique()):
        for value_kind in ("stock", "useful", "immobilized"):
            for size in range(1, len(direct_items) + 1):
                for subset in itertools.combinations(direct_items, size):
                    subset_items = set(subset)
                    code = "+".join(item.replace("item:", "") for item in subset)
                    label = f"subset/{threshold_mode}/{value_kind}/{code}"
                    candidates.append(
                        Candidate(
                            rule=label,
                            threshold_mode=str(threshold_mode),
                            value_kind=value_kind,
                            item_filter=f"subset_{code}",
                            include_internal_rollup=False,
                            series=series_for(
                                component_daily,
                                threshold_mode=str(threshold_mode),
                                value_kind=value_kind,
                                items=subset_items,
                                include_internal_rollup=False,
                            ),
                        )
                    )
    return candidates


def first_snapshot_breakdown(real: pd.DataFrame, component_daily: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    first_sim_day = int(real.iloc[0]["sim_day"])
    breakdown = component_daily[
        (component_daily["day"] == first_sim_day)
        & (component_daily["threshold_mode"].isin(["coverage", "target_stock"]))
        & (~component_daily["value_source"].isin(INTERNAL_VALUE_SOURCES))
    ].copy()
    breakdown = breakdown.merge(
        bom[
            [
                "component_item_id",
                "component_code",
                "component_type",
                "bom_qty_per_1000",
                "bom_uom",
                "lead_days",
                "standard_lot_qty",
            ]
        ],
        on="component_item_id",
        how="left",
    )
    return breakdown.sort_values(["threshold_mode", "stock_value_eur"], ascending=[True, False])


def component_contributors(component_daily: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    direct = component_daily[
        (component_daily["threshold_mode"] == "target_stock")
        & (~component_daily["value_source"].isin(INTERNAL_VALUE_SOURCES))
    ].copy()
    agg = (
        direct.groupby("component_item_id", as_index=False)
        .agg(
            mean_stock_value_eur=("stock_value_eur", "mean"),
            max_stock_value_eur=("stock_value_eur", "max"),
            first_stock_value_eur=("stock_value_eur", "first"),
            mean_useful_value_eur=("useful_value_eur", "mean"),
            mean_immobilized_value_eur=("immobilized_value_eur", "mean"),
            unit_value_eur=("unit_value_eur", "median"),
            mean_stock_qty=("stock_qty", "mean"),
            first_stock_qty=("stock_qty", "first"),
        )
        .sort_values("mean_stock_value_eur", ascending=False)
    )
    return agg.merge(
        bom[
            [
                "component_item_id",
                "component_code",
                "component_type",
                "bom_qty_per_1000",
                "bom_uom",
                "supplier_count",
                "lead_days",
                "standard_lot_qty",
            ]
        ],
        on="component_item_id",
        how="left",
    )


def plan_summary(plan_events: pd.DataFrame) -> dict[str, Any]:
    if plan_events.empty:
        return {}
    delayed = plan_events[plan_events["event_type"].astype(str).str.contains("delay", na=False)]
    started = plan_events[plan_events["actual_qty"].fillna(0.0) > 0.0]
    first_started_day = int(started["day"].min()) if not started.empty else None
    top_blockers = (
        delayed.groupby("binding_input_item_id", dropna=False)
        .agg(
            delay_events=("day", "count"),
            first_delay_day=("day", "min"),
            last_delay_day=("day", "max"),
            delayed_qty=("shortfall_vs_lot_plan_qty", "sum"),
        )
        .sort_values(["delay_events", "delayed_qty"], ascending=False)
        .reset_index()
    )
    return {
        "delay_event_count": int(len(delayed)),
        "first_started_day": first_started_day,
        "first_delay_day": int(delayed["day"].min()) if not delayed.empty else None,
        "last_delay_day": int(delayed["day"].max()) if not delayed.empty else None,
        "top_blockers": top_blockers,
    }


def write_markdown(
    path: Path,
    real: pd.DataFrame,
    metrics: pd.DataFrame,
    first_breakdown: pd.DataFrame,
    contributors: pd.DataFrame,
    flows: pd.DataFrame,
    plan: dict[str, Any],
) -> None:
    best = metrics.sort_values(["mae_eur", "bias_eur"], key=lambda s: s.abs() if s.name == "bias_eur" else s).head(12)
    direct_stock = metrics[
        (metrics["threshold_mode"] == "target_stock")
        & (metrics["value_kind"] == "stock")
        & (metrics["item_filter"] == "all_components")
        & (~metrics["include_internal_rollup"])
    ].head(1)
    target_useful = metrics[
        (metrics["threshold_mode"] == "target_stock")
        & (metrics["value_kind"] == "useful")
        & (metrics["item_filter"] == "all_components")
        & (~metrics["include_internal_rollup"])
    ].head(1)
    coverage_useful = metrics[
        (metrics["threshold_mode"] == "coverage")
        & (metrics["value_kind"] == "useful")
        & (metrics["item_filter"] == "all_components")
        & (~metrics["include_internal_rollup"])
    ].head(1)

    lines: list[str] = []
    lines.append("# Audit stock composant Pharma - PF 268967 / D1430")
    lines.append("")
    lines.append("## Lecture courte")
    lines.append("")
    lines.append(
        "- Mapping corrige: `268967` correspond a `Stock_Composants*_Pharma.csv` et a l'usine `M-1430`."
    )
    lines.append(
        "- Le KPI reel Pharma n'est pas comparable au stock brut simule PFI inclus. Les PFI internes doivent etre exclus du KPI composant fournisseur."
    )
    if not direct_stock.empty:
        row = direct_stock.iloc[0]
        lines.append(
            f"- Stock composant direct simule: moyenne {euro(row['sim_mean_eur'])} vs reel {euro(row['real_mean_eur'])}, "
            f"ecart {euro(row['bias_eur'])} ({pct(row['bias_pct_real_mean'])})."
        )
    if not target_useful.empty:
        row = target_useful.iloc[0]
        lines.append(
            f"- Stock utile selon cible MRP: moyenne {euro(row['sim_mean_eur'])}, MAE {euro(row['mae_eur'])}."
        )
    if not coverage_useful.empty:
        row = coverage_useful.iloc[0]
        lines.append(
            f"- Couverture utile courte: premier snapshot {euro(row['first_sim_eur'])} vs reel {euro(row['first_real_eur'])}, "
            f"mais moyenne annuelle {euro(row['sim_mean_eur'])}; ce n'est donc pas une regle stable seule."
        )
    if plan:
        blocker = ""
        top_blockers = plan.get("top_blockers")
        if isinstance(top_blockers, pd.DataFrame) and not top_blockers.empty:
            first = top_blockers.iloc[0]
            blocker = f" Blocage principal: `{first['binding_input_item_id']}` ({int(first['delay_events'])} evenements)."
        lines.append(
            f"- La premiere campagne 268967 est reportee jusqu'au J{plan.get('first_started_day')} "
            f"apres {plan.get('delay_event_count', 0)} reports.{blocker}"
        )
    lines.append("")
    lines.append("## Meilleures regles candidates")
    lines.append("")
    lines.append(
        markdown_table(
            best,
            [
                "rule",
                "real_mean_eur",
                "sim_mean_eur",
                "bias_eur",
                "mae_eur",
                "corr",
                "first_real_eur",
                "first_sim_eur",
            ],
        )
    )
    lines.append("")
    lines.append("## Premier snapshot reel")
    lines.append("")
    first_real = real.iloc[0]
    lines.append(
        f"- Photo reelle: {first_real['snapshot_dt'].date()} -> jour source {int(first_real['day'])}, "
        f"compare au stock fin J{int(first_real['sim_day'])}: {euro(first_real['real_value_eur'])}."
    )
    lines.append("")
    cols = [
        "threshold_mode",
        "component_code",
        "component_type",
        "stock_value_eur",
        "useful_value_eur",
        "immobilized_value_eur",
        "stock_qty",
        "useful_qty",
        "lead_days",
        "standard_lot_qty",
    ]
    lines.append(markdown_table(first_breakdown, cols))
    lines.append("")
    lines.append("## Contributeurs du stock direct")
    lines.append("")
    lines.append(
        markdown_table(
            contributors,
            [
                "component_code",
                "component_type",
                "mean_stock_value_eur",
                "first_stock_value_eur",
                "mean_useful_value_eur",
                "mean_immobilized_value_eur",
                "unit_value_eur",
                "lead_days",
                "standard_lot_qty",
            ],
        )
    )
    lines.append("")
    if not flows.empty:
        lines.append("## Flux physiques simules sur 5 ans")
        lines.append("")
        lines.append(markdown_table(flows, list(flows.columns)))
        lines.append("")
    if plan and isinstance(plan.get("top_blockers"), pd.DataFrame):
        lines.append("## Reports de production 268967")
        lines.append("")
        lines.append(markdown_table(plan["top_blockers"], list(plan["top_blockers"].columns), max_rows=10))
        lines.append("")
    lines.append("## Conclusion diagnostic")
    lines.append("")
    lines.append(
        "- L'ecart Pharma residuel vient surtout du perimetre de valorisation et de la dynamique de reapprovisionnement: "
        "les gros composants directs `038005`, `042342` et `333362` portent l'essentiel de la valeur simulee."
    )
    lines.append(
        "- Le premier point reel est proche d'une lecture 'stock utile de couverture', mais cette lecture ne reproduit pas toute l'annee."
    )
    lines.append(
        "- Pour fermer l'ecart sans regle arbitraire, il faut soit le detail article du KPI reel Pharma, soit aligner explicitement "
        "la simulation sur la meme definition finance: stock physique, stock disponible utile, stock bloque/qualite, ou stock net des besoins engages."
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    run_dir = DEFAULT_RUN_DIR
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    real = read_real_pharma_snapshots()
    bom = read_bom_metadata()
    component_daily = read_component_daily(run_dir)

    candidates = build_candidates(component_daily, bom)
    metric_rows = [candidate_metrics(real, candidate) for candidate in candidates]
    metrics = pd.DataFrame(metric_rows)
    metrics = metrics[metrics["snapshot_count"].fillna(0).astype(int) > 0].copy()
    metrics = metrics.sort_values(["mae_eur", "bias_eur"], key=lambda s: s.abs() if s.name == "bias_eur" else s)

    first_breakdown = first_snapshot_breakdown(real, component_daily, bom)
    contributors = component_contributors(component_daily, bom)
    flows = read_input_stock_flows(run_dir, bom["component_item_id"].tolist()).merge(
        bom[["component_item_id", "component_code", "component_type", "bom_qty_per_1000", "bom_uom"]],
        left_on="item_id",
        right_on="component_item_id",
        how="left",
    )
    plan = plan_summary(read_plan_events(run_dir))

    real.to_csv(OUTPUT_DIR / "real_pharma_snapshots.csv", index=False)
    metrics.to_csv(OUTPUT_DIR / "candidate_rules.csv", index=False)
    first_breakdown.to_csv(OUTPUT_DIR / "first_snapshot_breakdown.csv", index=False)
    contributors.to_csv(OUTPUT_DIR / "component_contributors.csv", index=False)
    flows.to_csv(OUTPUT_DIR / "component_physical_flows.csv", index=False)
    if plan and isinstance(plan.get("top_blockers"), pd.DataFrame):
        plan["top_blockers"].to_csv(OUTPUT_DIR / "production_delay_blockers.csv", index=False)

    write_markdown(
        OUTPUT_DIR / "audit_268967_pharma_stock_rule.md",
        real,
        metrics,
        first_breakdown,
        contributors,
        flows,
        plan,
    )

    best = metrics.head(5)[["rule", "sim_mean_eur", "bias_eur", "mae_eur", "corr"]]
    print("Wrote", OUTPUT_DIR)
    print(best.to_string(index=False))


if __name__ == "__main__":
    main()
