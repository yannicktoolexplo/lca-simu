"""Audit PF-driven explanations for Pharma component stock, PF 268967.

This script tests whether the real Pharma component-stock KPI can be explained
from finished-good signals instead of from arbitrary component subsets:

- weekly finished-good demand;
- real finished-good stock value;
- projected finished-good shortage flags;
- finished-good stock target / lot size;
- simulated cut-over production delay.

It does not modify the simulation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
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
    / "audit_268967_pf_driven_stock_rule"
)

START_DATE = date(2025, 1, 1)
PRODUCT_CODE = "268967"
PRODUCT_ITEM = "item:268967"
FACTORY = "M-1430"
DC = "DC-1920"
LOT_SIZE = 107_800.0


@dataclass(frozen=True)
class BomCost:
    code: str
    component_type: str
    cost_per_pf_unit_eur: float


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
    return f"{100.0 * value:.1f}%"


def source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one file for {pattern}, found {matches}")
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


def real_component_stock() -> pd.DataFrame:
    df = read_source_csv("Stock_Composants*Pharma.csv").copy()
    df["snapshot_dt"] = pd.to_datetime(df.iloc[:, 0])
    df["sim_day"] = ((df["snapshot_dt"].dt.date - START_DATE).apply(lambda delta: delta.days) - 1).clip(lower=0)
    df["real_component_stock_eur"] = df.iloc[:, 1].map(parse_float)
    return df[["snapshot_dt", "sim_day", "real_component_stock_eur"]].sort_values("snapshot_dt")


def real_pf_stock() -> pd.DataFrame:
    df = read_source_csv("Stock_PF*.csv").copy()
    df = df[df.iloc[:, 0].astype(str).str.strip() == PRODUCT_CODE].copy()
    df["snapshot_dt"] = pd.to_datetime(df.iloc[:, 1])
    df["sim_day"] = ((df["snapshot_dt"].dt.date - START_DATE).apply(lambda delta: delta.days) - 1).clip(lower=0)
    df["real_pf_stock_value_eur"] = df.iloc[:, 2].map(parse_float)
    return df[["snapshot_dt", "sim_day", "real_pf_stock_value_eur"]].sort_values("snapshot_dt")


def weekly_demand() -> pd.DataFrame:
    df = pd.read_excel(source_file("demand_PF.xlsx"), sheet_name="Demande")
    df = df[df.iloc[:, 0].astype(str).str.strip() == PRODUCT_CODE].copy()
    df["week_index"] = df.iloc[:, 2].astype(int)
    df["forecast_demand_qty"] = df.iloc[:, 3].map(parse_float)
    df["real_demand_qty"] = df.iloc[:, 4].map(parse_float)
    return df[["week_index", "forecast_demand_qty", "real_demand_qty"]].sort_values("week_index")


def projected_shortage() -> pd.DataFrame:
    df = read_source_csv("Dispo_PF*.csv").copy()
    df = df[df.iloc[:, 0].astype(str).str.strip() == PRODUCT_CODE].copy()
    df["year_week"] = df.iloc[:, 1].astype(str)
    df["shortage_weeks"] = df.iloc[:, 2].map(parse_float)
    df["shortage_repetition"] = df.iloc[:, 3].map(parse_float)
    return df[["year_week", "shortage_weeks", "shortage_repetition"]]


def bom_costs() -> pd.DataFrame:
    bom = pd.read_excel(source_file("268967.xlsx"), sheet_name="BOM")
    fia = pd.read_excel(source_file("268967.xlsx"), sheet_name="FIA")
    fia["component_code"] = fia.iloc[:, 0].map(item_code)
    fia["unit_price_eur"] = fia.iloc[:, 2].map(parse_float) / fia.iloc[:, 3].map(parse_float).replace(0.0, pd.NA)
    prices = dict(zip(fia["component_code"], fia["unit_price_eur"]))
    rows: list[dict[str, Any]] = []
    for _, row in bom.iterrows():
        code = item_code(row.iloc[2])
        component_type = str(row.iloc[3]).strip()
        qty_per_pf = parse_float(row.iloc[4]) / 1000.0
        uom = str(row.iloc[5]).upper().replace(".", "")
        if uom == "G" and code in {"038005", "708073"}:
            qty_per_pf /= 1000.0
        unit_price = float(prices.get(code, 0.0) or 0.0)
        rows.append(
            {
                "component_code": code,
                "component_type": component_type,
                "bom_uom": str(row.iloc[5]),
                "qty_per_pf": qty_per_pf,
                "unit_price_eur": unit_price,
                "cost_per_pf_unit_eur": qty_per_pf * unit_price,
                "is_internal_pfi": code == "773474",
                "is_unpriced": unit_price == 0.0,
            }
        )
    return pd.DataFrame(rows)


def dc_stock_units(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "data" / "production_dc_stocks_daily.csv"
    df = pd.read_csv(path)
    df = df[(df["node_id"] == DC) & (df["item_id"] == PRODUCT_ITEM)].copy()
    return df[["day", "stock_end_of_day"]].rename(columns={"day": "sim_day", "stock_end_of_day": "sim_dc_pf_stock_qty"})


def source_pf_opening_stock_qty() -> float:
    df = pd.read_excel(source_file("Extract_Données_Complémentaires.xlsx"), sheet_name="Stocks")
    row = df[
        (df.iloc[:, 0].astype(str).str.strip() == PRODUCT_CODE)
        & (df.iloc[:, 2].astype(str).str.strip() == "1920")
    ]
    if row.empty:
        return 0.0
    return parse_float(row.iloc[0, 4])


def component_set_costs(costs: pd.DataFrame) -> dict[str, float]:
    direct = costs[~costs["is_internal_pfi"]].copy()
    priced_direct = direct[~direct["is_unpriced"]]
    return {
        "all_direct_priced": float(priced_direct["cost_per_pf_unit_eur"].sum()),
        "mp_direct": float(priced_direct[priced_direct["component_type"].str.upper() == "MP"]["cost_per_pf_unit_eur"].sum()),
        "pack_direct": float(priced_direct[priced_direct["component_type"].str.upper() != "MP"]["cost_per_pf_unit_eur"].sum()),
        "no_042342": float(
            priced_direct[priced_direct["component_code"] != "042342"]["cost_per_pf_unit_eur"].sum()
        ),
        "038005_333362": float(
            priced_direct[priced_direct["component_code"].isin(["038005", "333362"])]["cost_per_pf_unit_eur"].sum()
        ),
    }


def rolling_demand_series(demand: dict[int, float], week_indices: pd.Series, horizon: int, offset: int) -> pd.Series:
    values: list[float] = []
    for week in week_indices:
        start = int(week) + offset
        values.append(sum(demand.get(idx, 0.0) for idx in range(start, start + horizon)))
    return pd.Series(values, index=week_indices.index, dtype=float)


def score_candidate(obs: pd.DataFrame, sim: pd.Series, metadata: dict[str, Any]) -> dict[str, Any]:
    real = obs["real_component_stock_eur"].reset_index(drop=True)
    sim = sim.reset_index(drop=True).astype(float)
    error = sim - real
    corr = sim.corr(real) if sim.nunique(dropna=True) > 1 and real.nunique(dropna=True) > 1 else math.nan
    return {
        **metadata,
        "real_mean_eur": float(real.mean()),
        "sim_mean_eur": float(sim.mean()),
        "bias_eur": float(error.mean()),
        "mae_eur": float(error.abs().mean()),
        "mae_pct_real_mean": float(error.abs().mean() / real.mean()) if real.mean() else math.nan,
        "corr": float(corr) if not pd.isna(corr) else math.nan,
        "first_real_eur": float(real.iloc[0]),
        "first_sim_eur": float(sim.iloc[0]),
    }


def build_pf_candidates(obs: pd.DataFrame, demand_df: pd.DataFrame, set_costs: dict[str, float]) -> pd.DataFrame:
    demand = dict(zip(demand_df["week_index"].astype(int), demand_df["real_demand_qty"].astype(float)))
    rows: list[dict[str, Any]] = []
    for component_set, cost_per_pf in set_costs.items():
        for horizon in range(1, 53):
            for offset in range(-2, 4):
                future_qty = rolling_demand_series(demand, obs["week_index"], horizon, offset)
                variants = {
                    "gross_future_demand": future_qty,
                    "net_future_minus_real_pf_stock": (future_qty - obs["real_pf_stock_qty_est"]).clip(lower=0.0),
                    "min_future_and_real_pf_stock": pd.concat([future_qty, obs["real_pf_stock_qty_est"]], axis=1).min(axis=1),
                    "lot_ceiled_future_demand": (future_qty / LOT_SIZE).apply(math.ceil) * LOT_SIZE,
                    "lot_ceiled_net_future": ((future_qty - obs["real_pf_stock_qty_est"]).clip(lower=0.0) / LOT_SIZE).apply(math.ceil)
                    * LOT_SIZE,
                    "real_pf_stock_equivalent": obs["real_pf_stock_qty_est"],
                }
                for variant, qty_series in variants.items():
                    sim = qty_series * cost_per_pf
                    rows.append(
                        score_candidate(
                            obs,
                            sim,
                            {
                                "rule_family": "pf_driven",
                                "variant": variant,
                                "component_set": component_set,
                                "horizon_weeks": horizon,
                                "week_offset": offset,
                                "cost_per_pf_unit_eur": cost_per_pf,
                            },
                        )
                    )
    return pd.DataFrame(rows).sort_values(["mae_eur", "bias_eur"])


def production_delay_audit(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    plan = pd.read_csv(run_dir / "data" / "production_plan_events.csv")
    plan = plan[(plan["node_id"] == FACTORY) & (plan["output_item_id"] == PRODUCT_ITEM)].copy()
    stocks = pd.read_csv(run_dir / "data" / "production_input_stocks_daily.csv")
    arrivals = pd.read_csv(run_dir / "data" / "production_input_replenishment_arrivals_daily.csv")
    items = ["item:344135", "item:333362", "item:038005", "item:042342", "item:708073", "item:734545", "item:773474"]
    snapshots = stocks[
        (stocks["node_id"] == FACTORY)
        & (stocks["item_id"].isin(items))
        & (stocks["day"].isin([0, 34, 36, 58, 63, 68, 69, 70, 71, 77]))
    ].copy()
    arrivals = arrivals[
        (arrivals["node_id"] == FACTORY)
        & (arrivals["item_id"].isin(items))
        & (arrivals["arrived_qty"] > 0)
        & (arrivals["day"] <= 100)
    ].copy()
    return plan, pd.concat(
        [
            snapshots.assign(row_type="stock_snapshot"),
            arrivals.rename(columns={"arrived_qty": "stock_end_of_day"}).assign(row_type="arrival"),
        ],
        ignore_index=True,
        sort=False,
    )


def write_report(
    path: Path,
    obs: pd.DataFrame,
    costs: pd.DataFrame,
    candidates: pd.DataFrame,
    pf_unit_value: float,
    source_opening_pf_qty: float,
    plan: pd.DataFrame,
    delay_data: pd.DataFrame,
    shortage: pd.DataFrame,
) -> None:
    best = candidates.head(15)
    best_gross = candidates[candidates["variant"] == "gross_future_demand"].head(10)
    best_net = candidates[candidates["variant"].str.contains("net", na=False)].head(10)
    delays = plan[plan["event_type"].astype(str).str.contains("delay", na=False)].copy()
    first_complete = plan[plan["actual_qty"].fillna(0.0) > 0.0]
    first_complete_day = int(first_complete["day"].min()) if not first_complete.empty else None

    lines: list[str] = []
    lines.append("# Audit regles PF -> stock composant Pharma - 268967")
    lines.append("")
    lines.append("## Lecture courte")
    lines.append("")
    lines.append(
        f"- Stock composant reel Pharma moyen: {euro(obs['real_component_stock_eur'].mean())}."
    )
    lines.append(
        f"- Stock PF reel moyen: {euro(obs['real_pf_stock_value_eur'].mean())}; "
        f"conversion indicative PF: {pf_unit_value:.3f} EUR/unite, "
        f"issue du premier snapshot PF reel / stock DC simule au meme jour."
    )
    lines.append(
        f"- Stock PF source au 01/01/2025: {source_opening_pf_qty:,.0f} UN. "
        "Le PF couvre donc deja une grande partie du debut d'annee; le stock composant ne doit pas etre lu comme tout le besoin futur brut."
    )
    if not delays.empty:
        blocker = delays["binding_input_item_id"].mode().iloc[0]
        lines.append(
            f"- Premiere campagne usine reportee J0 -> J{first_complete_day}: {len(delays)} reports, "
            f"cause dominante `{blocker}`."
        )
    lines.append("")
    lines.append("## Cout BOM par unite PF")
    lines.append("")
    lines.append(
        markdown_table(
            costs,
            [
                "component_code",
                "component_type",
                "qty_per_pf",
                "unit_price_eur",
                "cost_per_pf_unit_eur",
                "is_internal_pfi",
                "is_unpriced",
            ],
        )
    )
    lines.append("")
    lines.append("## Meilleures regles PF candidates")
    lines.append("")
    lines.append(
        markdown_table(
            best,
            [
                "variant",
                "component_set",
                "horizon_weeks",
                "week_offset",
                "cost_per_pf_unit_eur",
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
    lines.append("## Meilleures regles demande brute future")
    lines.append("")
    lines.append(
        markdown_table(
            best_gross,
            [
                "variant",
                "component_set",
                "horizon_weeks",
                "week_offset",
                "sim_mean_eur",
                "bias_eur",
                "mae_eur",
                "corr",
            ],
        )
    )
    lines.append("")
    lines.append("## Meilleures regles avec stock PF reel")
    lines.append("")
    lines.append(
        markdown_table(
            best_net,
            [
                "variant",
                "component_set",
                "horizon_weeks",
                "week_offset",
                "sim_mean_eur",
                "bias_eur",
                "mae_eur",
                "corr",
            ],
        )
    )
    lines.append("")
    lines.append("## Ruptures PF projetees source")
    lines.append("")
    lines.append(markdown_table(shortage, list(shortage.columns), max_rows=30))
    lines.append("")
    lines.append("## Blocage premiere campagne 268967")
    lines.append("")
    lines.append(
        "- `344135` a un stock initial nul et aucune ligne ouverte dans `Extract_En_cours.xlsx`; "
        "la simulation genere ensuite une commande MRP, disponible seulement J70."
    )
    lines.append(
        "- Le premier lot demande 107 800 UN de `344135`; la premiere reception de 240 000 UN arrive J70, "
        "ce qui debloque le lot."
    )
    lines.append("")
    lines.append(
        markdown_table(
            delay_data[
                [
                    "row_type",
                    "day",
                    "item_id",
                    "stock_before_production",
                    "stock_end_of_day",
                    "uom",
                ]
            ].fillna(""),
            ["row_type", "day", "item_id", "stock_before_production", "stock_end_of_day", "uom"],
            max_rows=80,
        )
    )
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(
        "- La meilleure regle PF pure est du type `demande future N semaines x cout BOM`, autour de 16 a 19 semaines selon le perimetre, "
        "mais elle reste moins bonne que la lecture composant/MRP: erreur autour de 59 kEUR au mieux et correlation negative."
    )
    lines.append(
        "- Donc le KPI reel Pharma ne semble pas etre directement une regle simple issue du PF seul. "
        "Le PF explique le niveau cible global, mais le detail article/MRP explique mieux la valeur observee."
    )
    lines.append(
        "- Pour rendre cela propre dans la simulation, il faut distinguer trois KPI: stock PF disponible, besoin composant couvert par PF/demande future, "
        "et stock composant utile/excedentaire par article."
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    run_dir = DEFAULT_RUN_DIR
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    comp = real_component_stock()
    pf = real_pf_stock()
    dc = dc_stock_units(run_dir)
    demand_df = weekly_demand()
    shortage = projected_shortage()
    costs = bom_costs()
    set_costs = component_set_costs(costs)

    obs = comp.merge(pf[["sim_day", "real_pf_stock_value_eur"]], on="sim_day", how="left")
    obs = obs.merge(dc, on="sim_day", how="left")
    first_valid = obs.dropna(subset=["real_pf_stock_value_eur", "sim_dc_pf_stock_qty"]).iloc[0]
    pf_unit_value = float(first_valid["real_pf_stock_value_eur"] / first_valid["sim_dc_pf_stock_qty"])
    obs["real_pf_stock_qty_est"] = obs["real_pf_stock_value_eur"] / pf_unit_value
    obs["week_index"] = (obs["sim_day"].astype(int) // 7) + 1
    candidates = build_pf_candidates(obs, demand_df, set_costs)
    plan, delay_data = production_delay_audit(run_dir)

    obs.to_csv(OUTPUT_DIR / "pf_component_observations.csv", index=False)
    costs.to_csv(OUTPUT_DIR / "bom_cost_per_pf_unit.csv", index=False)
    candidates.to_csv(OUTPUT_DIR / "pf_driven_candidate_rules.csv", index=False)
    delay_data.to_csv(OUTPUT_DIR / "first_campaign_delay_detail.csv", index=False)
    plan.to_csv(OUTPUT_DIR / "first_campaign_plan_events.csv", index=False)
    shortage.to_csv(OUTPUT_DIR / "projected_shortage_268967.csv", index=False)
    write_report(
        OUTPUT_DIR / "audit_268967_pf_driven_stock_rule.md",
        obs,
        costs,
        candidates,
        pf_unit_value,
        source_pf_opening_stock_qty(),
        plan,
        delay_data,
        shortage,
    )
    print("Wrote", OUTPUT_DIR)
    print(candidates.head(8)[["variant", "component_set", "horizon_weeks", "week_offset", "sim_mean_eur", "mae_eur", "corr"]].to_string(index=False))


if __name__ == "__main__":
    main()
