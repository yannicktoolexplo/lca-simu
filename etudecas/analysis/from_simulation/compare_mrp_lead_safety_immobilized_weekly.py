"""Compare real component immobilized stock with a lead+safety MRP rule.

The source KPI is weekly and aggregated by product family.  This script
recomputes, on the simulation state at each real snapshot, an interpretable
component-by-component estimate:

    immobilized = max(physical component stock
                      - component need over supplier lead + safety delay
                      - explicit safety stock,
                      0)

Two variants are produced:
* gross: demand over the component horizon is not reduced by finished-goods
  stock already available at the DC.
* net: demand over the component horizon is first absorbed by the simulated
  finished-goods stock at the DC.

PFI/internal rollups are excluded from the component scope.
"""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "etudecas" / "data" / "source"
DEFAULT_RUN_DIR = (
    ROOT
    / "etudecas"
    / "simulation"
    / "result"
    / "_reruns"
    / "_codex_mrp_dynamic_targets_open_orders_5y"
)
OUTPUT_DIR = (
    ROOT
    / "etudecas"
    / "analysis"
    / "from_simulation"
    / "result"
    / "source_week1_stock_audit"
)

PRODUCTS = {
    "268091": {
        "label": "Cos",
        "site": "1810",
        "factory_node": "M-1810",
        "pf_item_id": "item:268091",
        "real_pattern": "Stock_Composants*Cos.csv",
        "excluded_components": set(),
    },
    "268967": {
        "label": "Pharma",
        "site": "1430",
        "factory_node": "M-1430",
        "pf_item_id": "item:268967",
        "real_pattern": "Stock_Composants*Pharma.csv",
        # Internal PFI; the user explicitly wants component valuation hors PFI.
        "excluded_components": {"item:773474"},
    },
}


def euro(value: float) -> str:
    return f"{value:,.0f} EUR".replace(",", " ")


def pct(value: float) -> str:
    if math.isnan(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def real_component_immobilized() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for product_code, info in PRODUCTS.items():
        path = next(SOURCE_DIR.glob(str(info["real_pattern"])))
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
        df.columns = ["snapshot", "real_immobilized_value_eur"]
        df["snapshot_dt"] = pd.to_datetime(df["snapshot"])
        df["product_code"] = product_code
        df["family"] = info["label"]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def source_policy() -> pd.DataFrame:
    path = next(SOURCE_DIR.glob("Extract_Donn*.xlsx"))
    df = pd.read_excel(path, sheet_name="Politique de Stock MRP")
    out = pd.DataFrame(
        {
            "component_code": df.iloc[:, 0].astype(int).astype(str).str.zfill(6),
            "site": df.iloc[:, 2].astype(int).astype(str),
            "safety_days": pd.to_numeric(df.iloc[:, 4], errors="coerce").fillna(0.0),
            "safety_stock_qty": pd.to_numeric(df.iloc[:, 5], errors="coerce").fillna(0.0),
        }
    )
    return out


def source_leads() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for product_code in PRODUCTS:
        fia = pd.read_excel(SOURCE_DIR / f"{product_code}.xlsx", sheet_name="FIA")
        for _, row in fia.iterrows():
            rows.append(
                {
                    "product_code": product_code,
                    "component_code": str(int(row.iloc[0])).zfill(6),
                    "supplier": str(row.iloc[1]),
                    "lead_days": float(pd.to_numeric(row.iloc[5], errors="coerce") or 0.0),
                }
            )
    return (
        pd.DataFrame(rows)
        .groupby(["product_code", "component_code"], as_index=False)
        .agg({"supplier": "first", "lead_days": "min"})
    )


def component_scope(run_dir: Path) -> pd.DataFrame:
    """Return component metadata with value-per-PF and unit value from sim output."""
    components = pd.read_csv(run_dir / "data" / "component_immobilized_stock_components_daily.csv")
    target_day0 = components[
        (components["day"] == 0)
        & (components["threshold_mode"] == "target_stock")
    ].copy()
    target_day0["product_code"] = target_day0["product_code"].astype(str)
    rows: list[pd.DataFrame] = []
    source_detail = pd.read_csv(
        ROOT
        / "etudecas"
        / "analysis"
        / "from_simulation"
        / "result"
        / "component_stock_useful_rules"
        / "source_opening_minus_week_consumption_components.csv"
    )
    source_detail["component_item_id"] = "item:" + source_detail["component_code"].astype(str).str.zfill(6)
    source_detail["product_code"] = source_detail["product_code"].astype(str)
    source_detail["value_per_pf_eur"] = (
        source_detail["week1_consumption_value_eur"]
        / source_detail["week1_demand_pf"]
    )
    for product_code, info in PRODUCTS.items():
        product_components = target_day0[
            target_day0["product_code"] == product_code
        ].copy()
        product_components = product_components[
            ~product_components["component_item_id"].isin(info["excluded_components"])
        ]
        product_components["component_code"] = (
            product_components["component_item_id"].astype(str).str.replace("item:", "", regex=False)
        )
        product_components = product_components.merge(
            source_detail[["product_code", "component_item_id", "value_per_pf_eur"]],
            on=["product_code", "component_item_id"],
            how="left",
        )
        rows.append(product_components)
    scope = pd.concat(rows, ignore_index=True)
    scope = scope.merge(source_leads(), on=["product_code", "component_code"], how="left")
    pol = source_policy()
    scope["site"] = scope["product_code"].map(lambda code: PRODUCTS[str(code)]["site"])
    scope = scope.merge(pol, on=["component_code", "site"], how="left")
    scope["lead_days"] = scope["lead_days"].fillna(0.0)
    scope["safety_days"] = scope["safety_days"].fillna(0.0)
    scope["safety_stock_qty"] = scope["safety_stock_qty"].fillna(0.0)
    return scope[
        [
            "product_code",
            "component_item_id",
            "component_code",
            "unit_value_eur",
            "value_per_pf_eur",
            "lead_days",
            "safety_days",
            "safety_stock_qty",
        ]
    ].drop_duplicates()


def future_demand_by_item(run_dir: Path) -> dict[str, list[float]]:
    demand = pd.read_csv(run_dir / "data" / "production_demand_service_daily.csv")
    out: dict[str, list[float]] = {}
    for item_id, group in demand.groupby("item_id"):
        ordered = group.sort_values("day")
        max_day = int(ordered["day"].max())
        values = [0.0] * (max_day + 1)
        for _, row in ordered.iterrows():
            values[int(row["day"])] += float(row["demand_qty"])
        out[str(item_id)] = values
    return out


def demand_window(values: list[float], start_day: int, horizon_calendar_days: int) -> float:
    if horizon_calendar_days <= 0:
        return 0.0
    first = max(0, start_day + 1)
    last = min(len(values), start_day + 1 + horizon_calendar_days)
    if first >= last:
        return 0.0
    return float(sum(values[first:last]))


def build_weekly_comparison(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    real = real_component_immobilized()
    scope = component_scope(run_dir)
    component_daily = pd.read_csv(run_dir / "data" / "component_immobilized_stock_components_daily.csv")
    component_daily = component_daily[component_daily["threshold_mode"] == "target_stock"].copy()
    component_daily["product_code"] = component_daily["product_code"].astype(str)
    dc_stock = pd.read_csv(run_dir / "data" / "production_dc_stocks_daily.csv")
    demand_by_item = future_demand_by_item(run_dir)

    rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    start = pd.Timestamp("2025-01-01")
    for _, snapshot in real.iterrows():
        product_code = str(snapshot["product_code"])
        info = PRODUCTS[product_code]
        item_id = str(info["pf_item_id"])
        # The source snapshots are at about 00:05. We compare them with the
        # simulated end state of the previous day.
        day_offset = int((snapshot["snapshot_dt"].normalize() - start).days)
        sim_day = max(0, day_offset - 1)

        product_scope = scope[scope["product_code"].astype(str) == product_code]
        product_daily = component_daily[
            (component_daily["day"] == sim_day)
            & (component_daily["product_code"].astype(str) == product_code)
            & (~component_daily["component_item_id"].isin(info["excluded_components"]))
        ]
        product_daily = product_daily.merge(
            product_scope,
            on=["product_code", "component_item_id"],
            how="inner",
            suffixes=("_daily", ""),
        )
        dc = dc_stock[
            (dc_stock["day"] == sim_day)
            & (dc_stock["node_id"] == "DC-1920")
            & (dc_stock["item_id"] == item_id)
        ]
        dc_qty = float(dc["stock_end_of_day"].iloc[0]) if len(dc) else 0.0

        gross_immobilized = 0.0
        net_immobilized = 0.0
        gross_useful = 0.0
        net_useful = 0.0
        stock_value = 0.0
        existing_target_stock = 0.0

        for _, comp in product_daily.iterrows():
            stock_component_value = float(comp["stock_value_eur"])
            stock_value += stock_component_value
            existing_target_stock += float(comp["immobilized_value_eur"])

            horizon_working_days = float(comp["lead_days"]) + float(comp["safety_days"])
            # Keep the same convention as the source weekly calculation:
            # business-day horizon converted to calendar days.
            horizon_calendar_days = int(math.ceil(horizon_working_days / 5.0 * 7.0))
            future_pf_demand = demand_window(
                demand_by_item.get(item_id, []),
                sim_day,
                horizon_calendar_days,
            )
            net_pf_demand = max(0.0, future_pf_demand - dc_qty)
            gross_need_value = future_pf_demand * float(comp["value_per_pf_eur"])
            net_need_value = net_pf_demand * float(comp["value_per_pf_eur"])
            safety_value = float(comp["safety_stock_qty"]) * float(comp["unit_value_eur"])

            useful_gross = min(stock_component_value, gross_need_value + safety_value)
            useful_net = min(stock_component_value, net_need_value + safety_value)
            immob_gross = max(0.0, stock_component_value - gross_need_value - safety_value)
            immob_net = max(0.0, stock_component_value - net_need_value - safety_value)
            gross_useful += useful_gross
            net_useful += useful_net
            gross_immobilized += immob_gross
            net_immobilized += immob_net
            detail_rows.append(
                {
                    "snapshot": snapshot["snapshot_dt"].date().isoformat(),
                    "sim_day": sim_day,
                    "product_code": product_code,
                    "component_item_id": comp["component_item_id"],
                    "stock_value_eur": stock_component_value,
                    "future_pf_demand_qty": future_pf_demand,
                    "dc_stock_qty": dc_qty,
                    "net_pf_demand_qty": net_pf_demand,
                    "horizon_working_days": horizon_working_days,
                    "horizon_calendar_days": horizon_calendar_days,
                    "gross_need_value_eur": gross_need_value,
                    "net_need_value_eur": net_need_value,
                    "safety_value_eur": safety_value,
                    "immobilized_gross_rule_eur": immob_gross,
                    "immobilized_net_rule_eur": immob_net,
                }
            )

        real_value = float(snapshot["real_immobilized_value_eur"])
        rows.append(
            {
                "snapshot": snapshot["snapshot_dt"].date().isoformat(),
                "sim_day": sim_day,
                "product_code": product_code,
                "family": snapshot["family"],
                "real_immobilized_value_eur": real_value,
                "sim_stock_value_eur": stock_value,
                "sim_useful_gross_lead_safety_eur": gross_useful,
                "sim_immobilized_gross_lead_safety_eur": gross_immobilized,
                "sim_useful_net_lead_safety_eur": net_useful,
                "sim_immobilized_net_lead_safety_eur": net_immobilized,
                "sim_existing_target_stock_immobilized_eur": existing_target_stock,
                "gap_net_eur": net_immobilized - real_value,
                "gap_gross_eur": gross_immobilized - real_value,
                "gap_existing_target_stock_eur": existing_target_stock - real_value,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(detail_rows)


def corr(xs: Iterable[float], ys: Iterable[float]) -> float:
    x = list(xs)
    y = list(ys)
    if len(x) < 2 or len(y) < 2:
        return math.nan
    sx = statistics.pstdev(x)
    sy = statistics.pstdev(y)
    if sx == 0 or sy == 0:
        return math.nan
    mx = statistics.mean(x)
    my = statistics.mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (len(x) * sx * sy)


def summarize(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    variants = {
        "net_lead_safety": "sim_immobilized_net_lead_safety_eur",
        "gross_lead_safety": "sim_immobilized_gross_lead_safety_eur",
        "existing_target_stock": "sim_existing_target_stock_immobilized_eur",
    }
    for product_code, group in comparison.groupby("product_code"):
        real = group["real_immobilized_value_eur"].astype(float)
        for variant, col in variants.items():
            sim = group[col].astype(float)
            gap = sim - real
            rows.append(
                {
                    "product_code": product_code,
                    "family": group["family"].iloc[0],
                    "variant": variant,
                    "weeks": int(len(group)),
                    "real_mean_eur": float(real.mean()),
                    "sim_mean_eur": float(sim.mean()),
                    "bias_eur": float(gap.mean()),
                    "mae_eur": float(gap.abs().mean()),
                    "max_abs_error_eur": float(gap.abs().max()),
                    "corr": corr(real, sim),
                }
            )
    return pd.DataFrame(rows)


def write_report(comparison: pd.DataFrame, summary: pd.DataFrame, output_dir: Path) -> None:
    lines: list[str] = [
        "# Comparaison hebdomadaire stock composants immobilise",
        "",
        "Regle estimee: composant par composant, stock immobilise = max(stock physique - besoin sur lead fournisseur + delai securite - stock de securite, 0).",
        "La variante nette absorbe d'abord la demande future par le stock PF simule au DC-1920. Les snapshots reels a 00:05 sont compares a la fin simulee du jour precedent.",
        "PFI/internal rollups exclus.",
        "",
        "## Synthese",
        "| PF | Famille | Variante | Semaines | Reel moyen | Sim moyen | Biais | MAE | Erreur max | Corr |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| {row['product_code']} | {row['family']} | {row['variant']} | {int(row['weeks'])} | "
            f"{euro(float(row['real_mean_eur']))} | {euro(float(row['sim_mean_eur']))} | "
            f"{euro(float(row['bias_eur']))} | {euro(float(row['mae_eur']))} | "
            f"{euro(float(row['max_abs_error_eur']))} | {float(row['corr']):.2f} |"
        )
    lines.extend(
        [
            "",
            "## Premieres semaines",
            "| Date | PF | Reel | Sim net lead+secu | Gap net | Sim brut lead+secu | Gap brut | Sim cible actuelle | Gap cible actuelle |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    head = comparison.sort_values(["product_code", "snapshot"]).groupby("product_code").head(8)
    for _, row in head.iterrows():
        lines.append(
            f"| {row['snapshot']} | {row['product_code']} | "
            f"{euro(float(row['real_immobilized_value_eur']))} | "
            f"{euro(float(row['sim_immobilized_net_lead_safety_eur']))} | "
            f"{euro(float(row['gap_net_eur']))} | "
            f"{euro(float(row['sim_immobilized_gross_lead_safety_eur']))} | "
            f"{euro(float(row['gap_gross_eur']))} | "
            f"{euro(float(row['sim_existing_target_stock_immobilized_eur']))} | "
            f"{euro(float(row['gap_existing_target_stock_eur']))} |"
        )
    (output_dir / "weekly_mrp_lead_safety_sim_vs_real.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison, details = build_weekly_comparison(args.run_dir)
    summary = summarize(comparison)
    comparison.to_csv(output_dir / "weekly_mrp_lead_safety_sim_vs_real.csv", index=False)
    details.to_csv(output_dir / "weekly_mrp_lead_safety_sim_vs_real_detail.csv", index=False)
    summary.to_csv(output_dir / "weekly_mrp_lead_safety_sim_vs_real_summary.csv", index=False)
    write_report(comparison, summary, output_dir)
    print(output_dir / "weekly_mrp_lead_safety_sim_vs_real.md")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
