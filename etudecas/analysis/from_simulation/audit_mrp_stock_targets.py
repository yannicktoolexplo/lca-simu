"""Audit MRP stock targets against source data and simulation outputs.

This is a post-run diagnostic. It keeps separate:

* source physical stocks from Extract_Donnees_Complementaires.xlsx;
* source MRP policy parameters: safety time and explicit safety stock;
* scenario-level coverage assumptions used by the simulator;
* day-by-day MRP targets computed by the simulation;
* actual simulated stock / inventory positions / planned orders.

The goal is to decide whether the stock targets shown in the map are
traceable, technically coherent, and meaningful from a supply-planning
point of view.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import defaultdict
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
    / "active_mrp_physical_nominal100_20260709_134334"
)
OUTPUT_DIR = (
    REPO_ROOT
    / "etudecas"
    / "analysis"
    / "from_simulation"
    / "result"
    / "mrp_stock_target_audit"
)

DIVISION_TO_NODE = {
    "1430": "M-1430",
    "1810": "M-1810",
    "1450": "SDC-1450",
    "1920": "DC-1920",
}

PRODUCT_LABELS = {
    "item:268091": "Cos / PF 268091 / M-1810",
    "item:268967": "Pharma / PF 268967 / M-1430",
}


def norm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def col(df: pd.DataFrame, *candidates: str) -> str:
    normalized = {norm_text(name): name for name in df.columns}
    for candidate in candidates:
        key = norm_text(candidate)
        if key in normalized:
            return normalized[key]
    for candidate in candidates:
        key = norm_text(candidate)
        for norm_name, original in normalized.items():
            if key and (key in norm_name or norm_name in key):
                return original
    raise KeyError(f"Missing column {candidates}; available={list(df.columns)}")


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    try:
        text = str(value).strip().replace("\u202f", "").replace(" ", "").replace(",", ".")
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def fmt(value: Any, digits: int = 0) -> str:
    number = to_float(value, float("nan"))
    if math.isnan(number):
        return "n/a"
    if abs(number) >= 1000:
        return f"{number:,.{digits}f}".replace(",", " ")
    return f"{number:.{digits}f}"


def pct(value: Any) -> str:
    number = to_float(value, float("nan"))
    if math.isnan(number):
        return "n/a"
    return f"{100.0 * number:.1f}%"


def canonical_code(value: Any) -> str:
    text = str(value or "").strip().replace("item:", "")
    if text.endswith(".0"):
        text = text[:-2]
    if not text:
        return ""
    return text.zfill(6) if text.isdigit() and len(text) < 6 else text


def item_id(value: Any) -> str:
    code = canonical_code(value)
    return f"item:{code}" if code else ""


def division_to_node(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return DIVISION_TO_NODE.get(text, "")


def norm_uom(value: Any) -> str:
    text = str(value or "").strip().upper().replace(".", "")
    aliases = {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITES": "UN",
        "UNITS": "UN",
        "ZUN": "UN",
        "GRAMME": "G",
        "GRAMMES": "G",
        "KILOGRAMME": "KG",
        "KILOGRAMMES": "KG",
        "METRE": "M",
        "METRES": "M",
    }
    return aliases.get(text, text)


def convert_qty(value: float, from_uom: Any, to_uom: Any) -> float | None:
    src = norm_uom(from_uom)
    dst = norm_uom(to_uom)
    if not src or not dst or src == dst:
        return value
    factors = {"G": 1.0, "KG": 1000.0}
    if src in factors and dst in factors:
        return value * factors[src] / factors[dst]
    return None


def find_one(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one source file for {pattern}, found {matches}")
    return matches[0]


def read_source_csv(pattern: str) -> pd.DataFrame:
    path = find_one(pattern)
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, sep=";", encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path, sep=";")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_graph(run_dir: Path, graph_arg: Path | None) -> tuple[Path, dict[str, Any]]:
    if graph_arg:
        return graph_arg, read_json(graph_arg)
    manifest_path = run_dir / "run_manifest.json"
    manifest = read_json(manifest_path)
    graph_path = REPO_ROOT / str(manifest["input_graph"])
    return graph_path, read_json(graph_path)


def source_stock_rows() -> pd.DataFrame:
    xlsx = find_one("Extract_Donn*Compl*.xlsx")
    raw = pd.read_excel(xlsx, sheet_name="Stocks")
    article = col(raw, "Numero d'article", "Numéro d'article")
    division = col(raw, "Division")
    qty = col(raw, "Stock Total")
    uom = col(raw, "Unite de quantite de base", "Unité de quantité de base")
    typ = col(raw, "Type d'article", "Type article")
    out = pd.DataFrame(
        {
            "source_article": raw[article].map(canonical_code),
            "item_id": raw[article].map(item_id),
            "source_type": raw[typ].astype(str),
            "source_division": raw[division].astype(str).str.replace(".0", "", regex=False),
            "node_id": raw[division].map(division_to_node),
            "source_stock_qty": raw[qty].map(to_float),
            "source_stock_uom": raw[uom].map(norm_uom),
        }
    )
    out["source_stock_row"] = range(2, len(out) + 2)
    return out


def source_policy_rows() -> pd.DataFrame:
    xlsx = find_one("Extract_Donn*Compl*.xlsx")
    raw = pd.read_excel(xlsx, sheet_name="Politique de Stock MRP")
    article = col(raw, "Numero d'article", "Numéro d'article")
    division = col(raw, "Division")
    safety_time = col(raw, "Delai de securite", "Délai de sécurité")
    safety_stock = col(raw, "Stock de securite", "Stock de sécurité")
    uom = col(raw, "Unite de quantite de base", "Unité de quantité de base")
    typ = col(raw, "Type d'article", "Type article")
    out = pd.DataFrame(
        {
            "item_id": raw[article].map(item_id),
            "source_type_policy": raw[typ].astype(str),
            "source_policy_division": raw[division].astype(str).str.replace(".0", "", regex=False),
            "node_id": raw[division].map(division_to_node),
            "source_safety_time_workdays": raw[safety_time].map(to_float),
            "source_explicit_safety_stock_qty": raw[safety_stock].map(to_float),
            "source_policy_uom": raw[uom].map(norm_uom),
        }
    )
    out["source_policy_row"] = range(2, len(out) + 2)
    return out


def source_lot_rows() -> pd.DataFrame:
    xlsx = find_one("Extract_Donn*Compl*.xlsx")
    raw = pd.read_excel(xlsx, sheet_name="Taille de Lots")
    article = col(raw, "Numero d'article", "Numéro d'article")
    division = col(raw, "Division")
    fixed = col(raw, "Taille de lot fixe")
    max_lot = col(raw, "Taille de lot maximum", "Taille de lot maximale")
    min_lot = col(raw, "Taille de lot minimum", "Taille de lot minimale")
    out = pd.DataFrame(
        {
            "item_id": raw[article].map(item_id),
            "node_id": raw[division].map(division_to_node),
            "source_fixed_lot_qty": raw[fixed].map(to_float),
            "source_min_lot_qty": raw[min_lot].map(to_float),
            "source_max_lot_qty": raw[max_lot].map(to_float),
        }
    )
    return out


def source_open_orders_from_graph(graph: dict[str, Any]) -> pd.DataFrame:
    rows = ((graph.get("meta") or {}).get("opening_open_orders") or {}).get("rows") or []
    if not rows:
        return pd.DataFrame(
            columns=[
                "node_id",
                "item_id",
                "source_open_order_count",
                "source_open_order_qty",
                "source_open_order_first_usable_day",
                "source_open_order_last_usable_day",
                "source_open_order_types",
            ]
        )
    df = pd.DataFrame(rows)
    df["node_id"] = df["dst_node_id"].astype(str)
    df["item_id"] = df["item_id"].astype(str)
    df["quantity"] = df["quantity"].map(to_float)
    df["usable_day"] = df["usable_day"].map(to_float)
    grouped = (
        df.groupby(["node_id", "item_id"], as_index=False)
        .agg(
            source_open_order_count=("quantity", "size"),
            source_open_order_qty=("quantity", "sum"),
            source_open_order_first_usable_day=("usable_day", "min"),
            source_open_order_last_usable_day=("usable_day", "max"),
            source_open_order_types=("planning_element", lambda s: ",".join(sorted(set(map(str, s))))),
        )
    )
    return grouped


def unresolved_open_orders_from_graph(graph: dict[str, Any]) -> pd.DataFrame:
    rows = ((graph.get("meta") or {}).get("opening_open_orders") or {}).get("unresolved_rows") or []
    return pd.DataFrame(rows)


def graph_inventory_rows(graph: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        for state in ((node.get("inventory") or {}).get("states") or []):
            policy = state.get("mrp_policy") or {}
            rows.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "item_id": str(state.get("item_id") or ""),
                    "graph_initial_qty": to_float(state.get("initial")),
                    "graph_uom": norm_uom(state.get("uom")),
                    "graph_initial_source": state.get("initial_source") or "",
                    "graph_policy_source": policy.get("source") or "",
                    "graph_safety_time_days": to_float(policy.get("safety_time_days")),
                    "graph_safety_stock_qty": to_float(policy.get("safety_stock_qty")),
                    "graph_safety_stock_uom": norm_uom(policy.get("safety_stock_uom") or state.get("uom")),
                }
            )
    return pd.DataFrame(rows)


def graph_scenario_policy(graph: dict[str, Any]) -> dict[str, Any]:
    scenario = (graph.get("scenarios") or [{}])[0]
    return {
        "scenario_id": scenario.get("id", ""),
        "safety_stock_days": to_float(scenario.get("safety_stock_days")),
        "demand_stock_target_days": to_float(scenario.get("demand_stock_target_days")),
        "fg_target_days": to_float(scenario.get("fg_target_days")),
        "review_period_days": to_float(scenario.get("review_period_days")),
    }


def read_run_csv(run_dir: Path, relative: str) -> pd.DataFrame:
    path = run_dir / relative
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def aggregate_mrp_reference(run_dir: Path) -> pd.DataFrame:
    df = read_run_csv(run_dir, "reports/mrp_safety_stock_reference.csv")
    if df.empty:
        return df
    keep = [
        "scope",
        "node_id",
        "item_id",
        "uom",
        "safety_time_days",
        "planned_avg_daily_demand_qty",
        "observed_avg_daily_flow_qty",
        "stock_equiv_safety_time_qty",
        "explicit_safety_stock_qty",
        "effective_reference_stock_qty",
        "soft_simulated_target_qty",
        "max_mrp_demand_signal_qty",
        "max_mrp_safety_floor_qty",
        "max_soft_simulated_target_qty",
        "safety_reference_basis",
        "soft_safety_factor",
        "served_avg_daily_qty",
    ]
    return df[[c for c in keep if c in df.columns]].copy()


def aggregate_mrp_trace(run_dir: Path) -> pd.DataFrame:
    df = read_run_csv(run_dir, "data/mrp_trace_daily.csv")
    if df.empty:
        return df
    for c in [
        "target_stock_qty",
        "target_stock_display_qty",
        "target_with_backlog_qty",
        "safety_floor_qty",
        "soft_safety_target_qty",
        "coverage_target_qty",
        "inventory_position_qty",
        "stock_proj_qty",
        "planned_receipt_qty",
        "planned_order_count",
    ]:
        if c in df.columns:
            df[c] = df[c].map(to_float)
    df["under_target"] = df["inventory_position_qty"] + 1e-9 < df["target_stock_qty"]
    df["under_safety_floor"] = df["inventory_position_qty"] + 1e-9 < df["safety_floor_qty"]
    df["positive_target"] = df["target_stock_qty"] > 1e-9
    day0 = df[df["day"] == 0][
        ["node_id", "item_id", "target_stock_qty", "target_stock_display_qty", "inventory_position_qty"]
    ].rename(
        columns={
            "target_stock_qty": "day0_target_stock_qty",
            "target_stock_display_qty": "day0_target_stock_display_qty",
            "inventory_position_qty": "day0_inventory_position_qty",
        }
    )
    final_day = int(df["day"].max())
    final = df[df["day"] == final_day][["node_id", "item_id", "inventory_position_qty"]].rename(
        columns={"inventory_position_qty": "final_inventory_position_qty"}
    )
    grouped = (
        df.groupby(["node_id", "item_id"], as_index=False)
        .agg(
            trace_days=("day", "nunique"),
            target_positive_days=("positive_target", "sum"),
            mean_target_stock_qty=("target_stock_qty", "mean"),
            max_target_stock_qty=("target_stock_qty", "max"),
            mean_target_display_qty=("target_stock_display_qty", "mean"),
            max_target_display_qty=("target_stock_display_qty", "max"),
            mean_target_with_backlog_qty=("target_with_backlog_qty", "mean"),
            max_target_with_backlog_qty=("target_with_backlog_qty", "max"),
            mean_safety_floor_qty=("safety_floor_qty", "mean"),
            max_safety_floor_qty=("safety_floor_qty", "max"),
            mean_soft_safety_target_qty=("soft_safety_target_qty", "mean"),
            max_soft_safety_target_qty=("soft_safety_target_qty", "max"),
            mean_coverage_target_qty=("coverage_target_qty", "mean"),
            max_coverage_target_qty=("coverage_target_qty", "max"),
            mean_inventory_position_qty=("inventory_position_qty", "mean"),
            min_inventory_position_qty=("inventory_position_qty", "min"),
            max_inventory_position_qty=("inventory_position_qty", "max"),
            days_under_target=("under_target", "sum"),
            days_under_safety_floor=("under_safety_floor", "sum"),
            trace_planned_order_count=("planned_order_count", "sum"),
            trace_planned_receipt_qty=("planned_receipt_qty", "sum"),
        )
    )
    grouped["share_days_under_target"] = grouped["days_under_target"] / grouped["trace_days"].clip(lower=1)
    grouped["share_days_under_safety_floor"] = grouped["days_under_safety_floor"] / grouped["trace_days"].clip(lower=1)
    grouped = grouped.merge(day0, on=["node_id", "item_id"], how="left")
    grouped = grouped.merge(final, on=["node_id", "item_id"], how="left")
    return grouped


def aggregate_stock_series(run_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    specs = [
        ("data/production_input_stocks_daily.csv", "factory_input_stock"),
        ("data/production_supplier_stocks_daily.csv", "supplier_stock"),
        ("data/production_dc_stocks_daily.csv", "dc_stock"),
        ("data/production_output_products_daily.csv", "factory_output_stock"),
    ]
    for relative, source_name in specs:
        df = read_run_csv(run_dir, relative)
        if df.empty or "stock_end_of_day" not in df.columns:
            continue
        work = df[["day", "node_id", "item_id", "stock_end_of_day"]].copy()
        work["stock_source"] = source_name
        work["stock_end_of_day"] = work["stock_end_of_day"].map(to_float)
        frames.append(work)
    if not frames:
        return pd.DataFrame()
    all_stock = pd.concat(frames, ignore_index=True)
    day0 = all_stock[all_stock["day"] == 0][["node_id", "item_id", "stock_end_of_day"]].rename(
        columns={"stock_end_of_day": "day0_physical_stock_qty"}
    )
    final_day = int(all_stock["day"].max())
    final = all_stock[all_stock["day"] == final_day][["node_id", "item_id", "stock_end_of_day"]].rename(
        columns={"stock_end_of_day": "final_physical_stock_qty"}
    )
    grouped = (
        all_stock.groupby(["node_id", "item_id"], as_index=False)
        .agg(
            stock_series_sources=("stock_source", lambda s: ",".join(sorted(set(map(str, s))))),
            mean_physical_stock_qty=("stock_end_of_day", "mean"),
            min_physical_stock_qty=("stock_end_of_day", "min"),
            max_physical_stock_qty=("stock_end_of_day", "max"),
        )
    )
    grouped = grouped.merge(day0, on=["node_id", "item_id"], how="left")
    grouped = grouped.merge(final, on=["node_id", "item_id"], how="left")
    return grouped


def aggregate_orders(run_dir: Path) -> pd.DataFrame:
    df = read_run_csv(run_dir, "data/mrp_orders_daily.csv")
    if df.empty:
        return df
    for c in ["planned_receipt_qty", "release_qty", "arrival_day", "actual_receipt_day", "release_day"]:
        if c in df.columns:
            df[c] = df[c].map(to_float)
    dst = (
        df.groupby(["dst_node_id", "item_id"], as_index=False)
        .agg(
            mrp_order_count=("planned_receipt_qty", "size"),
            mrp_order_planned_receipt_qty=("planned_receipt_qty", "sum"),
            mrp_order_release_qty=("release_qty", "sum"),
            first_arrival_day=("arrival_day", "min"),
            last_arrival_day=("arrival_day", "max"),
            order_types=("order_type", lambda s: ",".join(sorted(set(map(str, s))))),
        )
        .rename(columns={"dst_node_id": "node_id"})
    )
    return dst


def aggregate_immobilized_summary(run_dir: Path) -> pd.DataFrame:
    df = read_run_csv(run_dir, "data/component_immobilized_stock_summary.csv")
    if df.empty:
        return df
    grouped = (
        df.groupby(["node_id", "component_item_id"], as_index=False)
        .agg(
            product_scopes=("product_item_id", lambda s: ",".join(sorted(set(map(str, s))))),
            mean_stock_value_eur=("mean_stock_value_eur", "sum"),
            mean_useful_stock_value_eur=("mean_useful_stock_value_eur", "sum"),
            mean_immobilized_stock_value_eur=("mean_immobilized_stock_value_eur", "sum"),
            max_immobilized_stock_value_eur=("max_immobilized_stock_value_eur", "max"),
        )
        .rename(columns={"component_item_id": "item_id"})
    )
    return grouped


def product_level_real_vs_sim(run_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    mapping = [
        ("item:268091", "Cos", "Stock_Composants*Cos.csv"),
        ("item:268967", "Pharma", "Stock_Composants*Pharma.csv"),
    ]
    sim = aggregate_immobilized_summary(run_dir)
    sim_by_product: dict[str, float] = defaultdict(float)
    raw = read_run_csv(run_dir, "data/component_immobilized_stock_summary.csv")
    if not raw.empty:
        for product_item, value in raw.groupby("product_item_id")["mean_immobilized_stock_value_eur"].sum().items():
            sim_by_product[str(product_item)] = float(value)
    for product_item, label, pattern in mapping:
        observed = read_source_csv(pattern)
        value_col = col(observed, "Sum_Valeur totale du stock", "Valeur totale du stock")
        values = observed[value_col].map(to_float)
        rows.append(
            {
                "product_item_id": product_item,
                "label": label,
                "real_mean_component_immobilized_eur": float(values.mean()),
                "real_first_component_immobilized_eur": float(values.iloc[0]),
                "real_min_component_immobilized_eur": float(values.min()),
                "real_max_component_immobilized_eur": float(values.max()),
                "sim_mean_component_immobilized_eur": sim_by_product.get(product_item, 0.0),
                "sim_minus_real_mean_eur": sim_by_product.get(product_item, 0.0) - float(values.mean()),
            }
        )
    return pd.DataFrame(rows)


def build_audit(run_dir: Path, graph_path: Path | None) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    resolved_graph_path, graph = load_graph(run_dir, graph_path)
    graph_inventory = graph_inventory_rows(graph)
    stocks = source_stock_rows()
    policy = source_policy_rows()
    lots = source_lot_rows()
    mrp_ref = aggregate_mrp_reference(run_dir)
    mrp_trace = aggregate_mrp_trace(run_dir)
    physical = aggregate_stock_series(run_dir)
    orders = aggregate_orders(run_dir)
    open_orders = source_open_orders_from_graph(graph)
    immobilized = aggregate_immobilized_summary(run_dir)

    keys = pd.concat(
        [
            graph_inventory[["node_id", "item_id"]],
            stocks[["node_id", "item_id"]],
            policy[["node_id", "item_id"]],
            mrp_ref[["node_id", "item_id"]] if not mrp_ref.empty else pd.DataFrame(columns=["node_id", "item_id"]),
            mrp_trace[["node_id", "item_id"]] if not mrp_trace.empty else pd.DataFrame(columns=["node_id", "item_id"]),
            physical[["node_id", "item_id"]] if not physical.empty else pd.DataFrame(columns=["node_id", "item_id"]),
            orders[["node_id", "item_id"]] if not orders.empty else pd.DataFrame(columns=["node_id", "item_id"]),
            open_orders[["node_id", "item_id"]] if not open_orders.empty else pd.DataFrame(columns=["node_id", "item_id"]),
        ],
        ignore_index=True,
    ).drop_duplicates()
    keys = keys[(keys["node_id"].astype(str) != "") & (keys["item_id"].astype(str) != "")]

    # Aggregate source rows before joining; this also exposes duplicates.
    stocks_agg = (
        stocks.groupby(["node_id", "item_id"], as_index=False)
        .agg(
            source_stock_qty=("source_stock_qty", "sum"),
            source_stock_uom=("source_stock_uom", "first"),
            source_stock_rows=("source_stock_row", lambda s: ",".join(map(str, s))),
            source_stock_row_count=("source_stock_row", "size"),
            source_type=("source_type", "first"),
            source_division=("source_division", "first"),
        )
    )
    policy_agg = (
        policy.groupby(["node_id", "item_id"], as_index=False)
        .agg(
            source_safety_time_workdays=("source_safety_time_workdays", "max"),
            source_explicit_safety_stock_qty=("source_explicit_safety_stock_qty", "max"),
            source_policy_uom=("source_policy_uom", "first"),
            source_policy_rows=("source_policy_row", lambda s: ",".join(map(str, s))),
            source_policy_row_count=("source_policy_row", "size"),
            source_type_policy=("source_type_policy", "first"),
            source_policy_division=("source_policy_division", "first"),
        )
    )
    lot_agg = (
        lots.groupby(["node_id", "item_id"], as_index=False)
        .agg(
            source_fixed_lot_qty=("source_fixed_lot_qty", "max"),
            source_min_lot_qty=("source_min_lot_qty", "max"),
            source_max_lot_qty=("source_max_lot_qty", "max"),
        )
    )

    audit = keys.copy()
    for frame in [
        graph_inventory,
        stocks_agg,
        policy_agg,
        lot_agg,
        mrp_ref,
        mrp_trace,
        physical,
        orders,
        open_orders,
        immobilized,
    ]:
        if frame is not None and not frame.empty:
            audit = audit.merge(frame, on=["node_id", "item_id"], how="left")

    # Classify source and target semantics.
    audit["has_source_stock"] = audit["source_stock_qty"].notna()
    audit["has_source_policy"] = audit["source_safety_time_workdays"].notna()
    audit["has_graph_policy"] = audit["graph_policy_source"].fillna("").astype(str) != ""
    audit["has_positive_target"] = audit["max_target_stock_qty"].fillna(0.0) > 1e-9
    audit["has_orders"] = audit["mrp_order_count"].fillna(0.0) > 0.0
    audit["target_minus_source_initial_qty"] = audit["day0_target_stock_qty"].fillna(0.0) - audit[
        "graph_initial_qty"
    ].fillna(0.0)
    audit["mean_stock_minus_mean_target_qty"] = audit["mean_physical_stock_qty"].fillna(
        audit["mean_inventory_position_qty"]
    ).fillna(0.0) - audit["mean_target_stock_qty"].fillna(0.0)

    def classify(row: pd.Series) -> str:
        scope = str(row.get("scope") or "")
        if scope == "supply_pair":
            return "approvisionnement fournisseur: cible stock nulle, commandes amont"
        if row.get("has_source_policy") and to_float(row.get("source_explicit_safety_stock_qty")) > 0:
            return "stock securite explicite source + delai securite"
        if row.get("has_source_policy") and to_float(row.get("source_safety_time_workdays")) > 0:
            return "delai securite source converti en couverture dynamique"
        if scope == "finished_good":
            return "couverture demande PF/DC/client calculee par scenario"
        if row.get("has_positive_target"):
            return "cible calculee par simulation sans politique source directe"
        return "pas de cible stock positive dans le run"

    audit["target_semantics"] = audit.apply(classify, axis=1)

    def alerts(row: pd.Series) -> str:
        out: list[str] = []
        node = str(row.get("node_id") or "")
        item = str(row.get("item_id") or "")
        if row.get("has_source_stock") and not row.get("has_graph_policy") and node.startswith("SDC-1450"):
            out.append("stock source SDC-1450 sans politique MRP source")
        if row.get("has_source_stock") and not row.get("has_source_policy") and node.startswith("M-"):
            out.append("stock source usine sans ligne politique MRP")
        if to_float(row.get("source_stock_row_count")) > 1:
            out.append("plusieurs lignes source stock agregees")
        if to_float(row.get("source_policy_row_count")) > 1:
            out.append("plusieurs lignes politique MRP agregees")
        if row.get("has_positive_target") and to_float(row.get("share_days_under_target")) >= 0.8:
            out.append("stock/position sous cible plus de 80% du run")
        if row.get("has_positive_target") and to_float(row.get("share_days_under_safety_floor")) >= 0.8:
            out.append("position sous safety floor plus de 80% du run")
        if row.get("has_orders") and not row.get("has_positive_target"):
            out.append("ordres sans cible stock positive: politique d'appro, pas stock cible")
        if to_float(row.get("mrp_order_count")) > 10000:
            out.append("nervosite MRP tres elevee: trop d'ordres")
        if row.get("has_source_policy") and to_float(row.get("source_safety_time_workdays")) > 0:
            if abs(to_float(row.get("source_safety_time_workdays")) - to_float(row.get("graph_safety_time_days"))) > 1e-6:
                out.append("delai securite source different du graphe")
        if item == "item:344135" and to_float(row.get("graph_initial_qty")) == 0 and to_float(row.get("source_open_order_count")) == 0:
            out.append("344135: zero stock initial et aucun en-cours source")
        return " | ".join(out)

    audit["alerts"] = audit.apply(alerts, axis=1)
    alert_rows = audit[audit["alerts"].fillna("").astype(str) != ""].copy()

    metadata = {
        "run_dir": str(run_dir),
        "graph_path": str(resolved_graph_path),
        "scenario_policy": graph_scenario_policy(graph),
        "mrp_seed": (graph.get("meta") or {}).get("mrp_seed") or {},
        "source_stock_rows": int(len(stocks)),
        "source_policy_rows": int(len(policy)),
        "source_lot_rows": int(len(lots)),
        "graph_inventory_rows": int(len(graph_inventory)),
        "mrp_trace_pairs": int(len(mrp_trace)) if not mrp_trace.empty else 0,
        "unresolved_open_orders": unresolved_open_orders_from_graph(graph).to_dict(orient="records"),
        "product_real_vs_sim": product_level_real_vs_sim(run_dir).to_dict(orient="records"),
    }
    return audit, alert_rows, metadata


def report_lines(audit: pd.DataFrame, alerts: pd.DataFrame, metadata: dict[str, Any]) -> list[str]:
    scenario = metadata["scenario_policy"]
    product_real = pd.DataFrame(metadata["product_real_vs_sim"])

    source_stock_ignored = audit[(audit["has_source_stock"]) & (audit["graph_initial_qty"].isna())]
    source_policy_without_stock = audit[(audit["has_source_policy"]) & (~audit["has_source_stock"])]

    positive_targets = audit[audit["has_positive_target"]].copy()
    under = positive_targets.sort_values(["share_days_under_target", "mean_stock_minus_mean_target_qty"], ascending=[False, True])
    over = positive_targets.sort_values("mean_stock_minus_mean_target_qty", ascending=False)

    lines = [
        "# Audit des cibles MRP de stock",
        "",
        f"- Run: `{metadata['run_dir']}`",
        f"- Graphe d'entree: `{metadata['graph_path']}`",
        f"- Lignes stock source: `{metadata['source_stock_rows']}`",
        f"- Lignes politique MRP source: `{metadata['source_policy_rows']}`",
        f"- Couples suivis dans `mrp_trace_daily`: `{metadata['mrp_trace_pairs']}`",
        "",
        "## Lecture cle",
        "",
        "La source MRP ne donne pas une cible unique de stock. Elle donne principalement un stock physique J0, un delai de securite et parfois un stock de securite explicite. La simulation transforme ensuite ces parametres en cibles journalieres (`target_stock_qty`, `safety_floor_qty`, `soft_safety_target_qty`) en fonction du signal de demande, des flux et de la position inventaire.",
        "",
        "Parametres de scenario qui ne viennent pas directement du classeur MRP:",
        f"- `demand_stock_target_days`: `{fmt(scenario.get('demand_stock_target_days'), 1)}` jours",
        f"- `safety_stock_days`: `{fmt(scenario.get('safety_stock_days'), 1)}` jours",
        f"- `fg_target_days`: `{fmt(scenario.get('fg_target_days'), 1)}` jours",
        f"- `review_period_days`: `{fmt(scenario.get('review_period_days'), 1)}` jour(s)",
        "",
        "## Statut global",
        "",
        f"- Couples avec cible positive: `{len(positive_targets)}`",
        f"- Couples avec stock source: `{int(audit['has_source_stock'].sum())}`",
        f"- Couples avec politique MRP source: `{int(audit['has_source_policy'].sum())}`",
        f"- Couples avec ordres MRP simules: `{int(audit['has_orders'].sum())}`",
        f"- Lignes d'alertes: `{len(alerts)}`",
        "",
        "## Points de decision",
        "",
        "1. Les cibles fournisseurs `supply_pair` ne sont pas des stocks cibles a tenir: elles peuvent etre a zero tout en generant des commandes d'approvisionnement.",
        "2. Plusieurs composants usine sont pilotes par un delai de securite source, mais la cible effective est souvent une cible molle inferieure au safety floor. Il faut decider si le metier veut tenir le safety floor complet ou une couverture reduite.",
        "3. Les PF/DC/client sont surtout pilotes par couverture de demande et service cible, pas par un stock de securite explicite du fichier MRP.",
        "4. Les stocks J0 viennent bien du snapshot ERP/MRP; ils ne prouvent pas a eux seuls que le stock est immobilise au sens KPI industriel.",
        "",
        "## Cas metier a corriger ou confirmer",
        "",
        "- `M-1430 / item:344135`: stock J0 nul, aucun en-cours source, mais besoin critique pour `268967`. La simulation commande ensuite, mais ce n'est pas un nominal propre si le composant est cense etre disponible.",
        "- `division 1820`: 16 lignes d'en-cours source ne sont pas mappees. Il faut statuer si 1820 doit alimenter 1810, rester hors perimetre, ou devenir un noeud explicite.",
        "- `SDC-1450 / item:021081`: stock et en-cours importants, mais aucune politique MRP source. C'est acceptable court terme, fragile pour une simulation longue.",
        "- `SDC-1450 / item:773474`: PFI interne avec stock et ordre de production, mais pas de cible positive dans le run. Il faut le lire comme flux interne/PFI, pas comme stock fournisseur.",
        "- `M-1430 / item:730384`: cible explicite faible par rapport a la cible dynamique; a valider avec conditionnement/lot fournisseur.",
        "- Delais source: le fichier parle de jours ouvres; le run les manipule comme jours numeriques. A valider si l'ecart ouvre/calendaire est important.",
        "",
    ]

    if not product_real.empty:
        lines += [
            "## Comparaison stock composants immobilise reel vs simulation",
            "",
            "| Produit | Reel moyen EUR | Simulation moyenne EUR | Ecart EUR |",
            "|---|---:|---:|---:|",
        ]
        for _, row in product_real.iterrows():
            lines.append(
                f"| {row['label']} | {fmt(row['real_mean_component_immobilized_eur'])} | "
                f"{fmt(row['sim_mean_component_immobilized_eur'])} | {fmt(row['sim_minus_real_mean_eur'])} |"
            )
        lines.append("")

    lines += [
        "## Top couples sous cible",
        "",
        "| Couple | Semantique | Jours sous cible | Ecart moyen stock-cible | Ordres | Alertes |",
        "|---|---|---:|---:|---:|---|",
    ]
    for _, row in under.head(15).iterrows():
        lines.append(
            f"| `{row['node_id']} / {row['item_id']}` | {row.get('target_semantics','')} | "
            f"{pct(row.get('share_days_under_target'))} | {fmt(row.get('mean_stock_minus_mean_target_qty'), 1)} | "
            f"{fmt(row.get('mrp_order_count'), 0)} | {row.get('alerts','')} |"
        )
    lines.append("")

    lines += [
        "## Top couples au-dessus de cible",
        "",
        "| Couple | Semantique | Ecart moyen stock-cible | Stock moyen | Cible moyenne | Alertes |",
        "|---|---|---:|---:|---:|---|",
    ]
    for _, row in over.head(15).iterrows():
        lines.append(
            f"| `{row['node_id']} / {row['item_id']}` | {row.get('target_semantics','')} | "
            f"{fmt(row.get('mean_stock_minus_mean_target_qty'), 1)} | {fmt(row.get('mean_physical_stock_qty'), 1)} | "
            f"{fmt(row.get('mean_target_stock_qty'), 1)} | {row.get('alerts','')} |"
        )
    lines.append("")

    if not source_stock_ignored.empty:
        lines += [
            "## Stocks source non retrouves comme etats graphe",
            "",
            "| Source | Article | Division | Quantite | Commentaire |",
            "|---|---|---:|---:|---|",
        ]
        for _, row in source_stock_ignored.iterrows():
            lines.append(
                f"| ligne(s) {row.get('source_stock_rows','')} | `{row['item_id']}` | "
                f"{row.get('source_division','')} | {fmt(row.get('source_stock_qty'), 1)} {row.get('source_stock_uom','')} | "
                "stock source present mais couple site/article non modele dans la cible run |"
            )
        lines.append("")

    if not source_policy_without_stock.empty:
        lines += [
            "## Politiques MRP sans stock source correspondant",
            "",
            "| Couple | Delai securite | Stock securite |",
            "|---|---:|---:|",
        ]
        for _, row in source_policy_without_stock.iterrows():
            lines.append(
                f"| `{row['node_id']} / {row['item_id']}` | "
                f"{fmt(row.get('source_safety_time_workdays'), 1)} j | "
                f"{fmt(row.get('source_explicit_safety_stock_qty'), 1)} {row.get('source_policy_uom','')} |"
            )
        lines.append("")

    unresolved = metadata.get("unresolved_open_orders") or []
    if unresolved:
        by_reason: dict[str, int] = defaultdict(int)
        for row in unresolved:
            for reason in row.get("reasons") or ["unknown"]:
                by_reason[str(reason)] += 1
        lines += [
            "## En-cours source non resolus",
            "",
            "| Raison | Lignes |",
            "|---|---:|",
        ]
        for reason, count in sorted(by_reason.items()):
            lines.append(f"| `{reason}` | {count} |")
        lines.append("")

    lines += [
        "## Verdict",
        "",
        "Techniquement, le run est coherent avec le graphe d'entree: les stocks J0 et politiques injectees sont exploitables et tracables. Metierement, il ne faut pas appeler toutes les courbes `cible MRP` de la meme facon. Il y a au moins quatre objets differents: stock physique J0, safety floor de reference, cible de commande effective, et politique d'approvisionnement fournisseur.",
        "",
        "Priorites recommandees:",
        "",
        "1. Renommer dans l'interface les cibles fournisseurs a zero en `politique d'approvisionnement`, pas `cible stock`.",
        "2. Afficher simultanement `safety floor` et `cible effective` pour les composants usine, avec une legende metier claire.",
        "3. Valider avec l'industriel si la cible effective doit etre le safety floor complet ou la cible molle actuelle.",
        "4. Traiter separement le KPI `stock immobilise`: ce n'est pas le stock physique brut; c'est un stock valorise au-dessus d'une regle de couverture utile.",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    audit, alerts, metadata = build_audit(args.run_dir, args.graph)
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    audit_path = out_dir / "mrp_stock_target_audit.csv"
    alerts_path = out_dir / "mrp_stock_target_alerts.csv"
    meta_path = out_dir / "mrp_stock_target_metadata.json"
    report_path = out_dir / "mrp_stock_target_report.md"

    audit.sort_values(["node_id", "item_id"]).to_csv(audit_path, index=False, encoding="utf-8")
    alerts.sort_values(["node_id", "item_id"]).to_csv(alerts_path, index=False, encoding="utf-8")
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text("\n".join(report_lines(audit, alerts, metadata)) + "\n", encoding="utf-8")

    print(f"Wrote {audit_path}")
    print(f"Wrote {alerts_path}")
    print(f"Wrote {report_path}")
    print(f"Rows: audit={len(audit)} alerts={len(alerts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
