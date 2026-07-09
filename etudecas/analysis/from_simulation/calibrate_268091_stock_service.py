"""Run targeted 268091 stock calibration scenarios.

The experiment asks a narrow business question: if the Cos component stock
around PF 268091 is closer to the observed immobilized value, does the simulated
product availability degrade like the real snapshots?

Runs are isolated under ``simulation/result/_experiments`` and skip map/lot
trace generation to keep the calibration lightweight.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT = REPO_ROOT / "etudecas"
SOURCE_DIR = ROOT / "data" / "source"
BASE_GRAPH = (
    ROOT
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
ENGINE = ROOT / "simulation" / "engine" / "run_first_simulation.py"
EXPERIMENT_ROOT = ROOT / "simulation" / "result" / "_experiments" / "stock_target_268091"
START_DATE = date(2025, 1, 1)
PRODUCT_ITEM = "item:268091"
PRODUCT_CODE = "268091"
FACTORY = "M-1810"
REAL_SERVICE_TARGETS = {
    "268091": 0.93,  # Cosmetique - user-provided business service target.
    "268967": 0.80,  # Pharma - user-provided business service target.
}

M1430_BASE_FLOOR_PAIRS = (
    ("M-1430", "item:038005"),
    ("M-1430", "item:042342"),
    ("M-1430", "item:333362"),
    ("M-1430", "item:344135"),
    ("M-1430", "item:708073"),
    ("M-1430", "item:730384"),
    ("M-1430", "item:734545"),
    ("M-1430", "item:773474"),
)

INITIAL_STATE_ARGS = (
    "--initial-state-scale",
    "1",
    "--initial-factory-input-on-hand-days",
    "0",
    "--initial-supplier-output-on-hand-days",
    "0",
    "--initial-distribution-center-on-hand-days",
    "0",
    "--initial-customer-on-hand-days",
    "0",
    "--no-initial-seed-safety-time-on-hand",
    "--no-initial-seed-estimated-source-on-hand",
    "--no-initial-seed-in-transit",
    "--no-initial-seed-estimated-source-pipeline",
    "--mrp-base-stock-floor-factor",
    "0",
)

VARIANTS = (
    {"name": "baseline_current_floor", "initial_scale": 1.0, "floor_factor": 1.0},
    {"name": "no_base_floor", "initial_scale": 1.0, "floor_factor": 0.0},
    {"name": "stock_scale_050", "initial_scale": 0.50, "floor_factor": 0.0},
    {"name": "stock_scale_035", "initial_scale": 0.35, "floor_factor": 0.0},
    {"name": "stock_scale_025", "initial_scale": 0.25, "floor_factor": 0.0},
    {"name": "stock_scale_015", "initial_scale": 0.15, "floor_factor": 0.0},
    {
        "name": "low_stock_tight_policy",
        "initial_scale": 0.35,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.35,
        "external_capacity_scale": 0.75,
    },
    {
        "name": "low_stock_supplier_slow",
        "initial_scale": 0.35,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.35,
        "external_capacity_scale": 0.50,
        "external_lead_days": 56,
    },
    {
        "name": "low_stock_supplier_constrained",
        "initial_scale": 0.35,
        "floor_factor": 0.0,
        "safety_stock_days": 2.0,
        "soft_safety_factor": 0.25,
        "external_capacity_scale": 0.25,
        "external_lead_days": 70,
    },
    {
        "name": "low_stock_no_proactive_supplier",
        "initial_scale": 0.35,
        "floor_factor": 0.0,
        "safety_stock_days": 2.0,
        "soft_safety_factor": 0.25,
        "external_proactive": False,
    },
    {
        "name": "target_026_no_proactive_020",
        "initial_scale": 0.20,
        "floor_factor": 0.0,
        "safety_stock_days": 1.0,
        "soft_safety_factor": 0.10,
        "external_proactive": False,
    },
    {
        "name": "target_026_no_proactive_010",
        "initial_scale": 0.10,
        "floor_factor": 0.0,
        "safety_stock_days": 1.0,
        "soft_safety_factor": 0.05,
        "external_proactive": False,
    },
    {
        "name": "target_026_no_proactive_005",
        "initial_scale": 0.05,
        "floor_factor": 0.0,
        "safety_stock_days": 0.0,
        "soft_safety_factor": 0.0,
        "external_proactive": False,
    },
    {
        "name": "target_026_external_disabled_035",
        "initial_scale": 0.35,
        "floor_factor": 0.0,
        "safety_stock_days": 1.0,
        "soft_safety_factor": 0.05,
        "external_enabled": False,
    },
    {
        "name": "target_026_external_disabled_020",
        "initial_scale": 0.20,
        "floor_factor": 0.0,
        "safety_stock_days": 1.0,
        "soft_safety_factor": 0.05,
        "external_enabled": False,
    },
    {
        "name": "mc_tuned_030_s3_soft035_cap075",
        "initial_scale": 0.30,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.35,
        "external_capacity_scale": 0.75,
    },
    {
        "name": "mc_tuned_030_s2_soft025_cap075",
        "initial_scale": 0.30,
        "floor_factor": 0.0,
        "safety_stock_days": 2.0,
        "soft_safety_factor": 0.25,
        "external_capacity_scale": 0.75,
    },
    {
        "name": "mc_tuned_030_s2_soft025_cap050",
        "initial_scale": 0.30,
        "floor_factor": 0.0,
        "safety_stock_days": 2.0,
        "soft_safety_factor": 0.25,
        "external_capacity_scale": 0.50,
    },
    {
        "name": "mc_tuned_025_s3_soft035_cap075",
        "initial_scale": 0.25,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.35,
        "external_capacity_scale": 0.75,
    },
    {
        "name": "mc_tuned_025_s4_soft040_cap075",
        "initial_scale": 0.25,
        "floor_factor": 0.0,
        "safety_stock_days": 4.0,
        "soft_safety_factor": 0.40,
        "external_capacity_scale": 0.75,
    },
    {
        "name": "mc_tuned_028_s3_soft030_cap060_lead",
        "initial_scale": 0.28,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.30,
        "external_capacity_scale": 0.60,
        "external_lead_days": 56,
    },
    {
        "name": "mc_refine_027_s2_soft025_cap050",
        "initial_scale": 0.27,
        "floor_factor": 0.0,
        "safety_stock_days": 2.0,
        "soft_safety_factor": 0.25,
        "external_capacity_scale": 0.50,
    },
    {
        "name": "mc_refine_027_s3_soft030_cap050",
        "initial_scale": 0.27,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.30,
        "external_capacity_scale": 0.50,
    },
    {
        "name": "mc_refine_026_s3_soft035_cap075",
        "initial_scale": 0.26,
        "floor_factor": 0.0,
        "safety_stock_days": 3.0,
        "soft_safety_factor": 0.35,
        "external_capacity_scale": 0.75,
    },
    {
        "name": "mc_refine_028_s2_soft025_cap050",
        "initial_scale": 0.28,
        "floor_factor": 0.0,
        "safety_stock_days": 2.0,
        "soft_safety_factor": 0.25,
        "external_capacity_scale": 0.50,
    },
)


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip().replace(",", ".")
        return float(text) if text else default
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv_dicts(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle, delimiter=delimiter))
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def source_file(pattern: str) -> Path:
    matches = sorted(SOURCE_DIR.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected one file for {pattern}, found {matches}")
    return matches[0]


def component_items(graph: dict[str, Any]) -> list[str]:
    for node in graph.get("nodes", []):
        if node.get("id") != FACTORY:
            continue
        states = (node.get("inventory") or {}).get("states") or []
        return sorted(
            str(state.get("item_id"))
            for state in states
            if state.get("item_id") and str(state.get("item_id")) != PRODUCT_ITEM
        )
    raise ValueError(f"Factory node not found: {FACTORY}")


def price_map(graph: dict[str, Any], items: list[str]) -> dict[str, dict[str, Any]]:
    item_set = set(items)
    product_rows: dict[str, list[dict[str, Any]]] = {}
    fallback_rows: dict[str, list[dict[str, Any]]] = {}

    for edge in graph.get("edges", []):
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        if edge.get("type") != "transport" or edge.get("to") != FACTORY:
            continue
        item_id = (edge.get("items") or [None])[0]
        if item_id not in item_set:
            continue
        sell_price = parse_float(terms.get("sell_price"), default=float("nan"))
        price_base = parse_float(terms.get("price_base"), default=1.0) or 1.0
        unit_price = None if sell_price != sell_price else sell_price / price_base
        row = {
            "supplier": edge.get("from"),
            "unit_price": unit_price,
            "sell_price": None if sell_price != sell_price else sell_price,
            "price_base": price_base,
        }
        if attrs.get("product_code") == PRODUCT_CODE:
            product_rows.setdefault(item_id, []).append(row)
        elif not attrs.get("product_code"):
            fallback_rows.setdefault(item_id, []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for item_id in items:
        scope = "product_code" if item_id in product_rows else "factory_item_fallback"
        rows = product_rows.get(item_id) or fallback_rows.get(item_id, [])
        values = [float(row["unit_price"]) for row in rows if row.get("unit_price") and float(row["unit_price"]) > 0]
        out[item_id] = {
            "unit_price": statistics.median(values) if values else None,
            "price_scope": scope if rows else "missing",
            "source_count": len(rows),
        }
    return out


def graph_initial_value(graph: dict[str, Any], items: list[str], prices: dict[str, dict[str, Any]]) -> float:
    total = 0.0
    item_set = set(items)
    for node in graph.get("nodes", []):
        if node.get("id") != FACTORY:
            continue
        for state in (node.get("inventory") or {}).get("states") or []:
            item_id = str(state.get("item_id"))
            unit_price = prices.get(item_id, {}).get("unit_price")
            if item_id in item_set and unit_price is not None:
                total += parse_float(state.get("initial")) * float(unit_price)
    return total


def scaled_graph(graph: dict[str, Any], items: list[str], variant: dict[str, Any]) -> dict[str, Any]:
    mutated = json.loads(json.dumps(graph))
    scale = float(variant["initial_scale"])
    item_set = set(items)
    for node in mutated.get("nodes", []):
        if node.get("id") != FACTORY:
            continue
        for state in (node.get("inventory") or {}).get("states") or []:
            item_id = str(state.get("item_id"))
            if item_id in item_set:
                state["initial"] = round(max(0.0, parse_float(state.get("initial")) * scale), 6)
                state["initial_source"] = f"{state.get('initial_source', 'graph_inventory_initial')}|scaled_{scale:g}"
    for scenario in mutated.get("scenarios", []) or []:
        if "safety_stock_days" in variant:
            scenario["safety_stock_days"] = float(variant["safety_stock_days"])
        if "demand_stock_target_days" in variant:
            scenario["demand_stock_target_days"] = float(variant["demand_stock_target_days"])
    meta = mutated.get("meta") if isinstance(mutated.get("meta"), dict) else {}
    meta["stock_target_268091_experiment"] = {"factory": FACTORY, **variant}
    mutated["meta"] = meta
    return mutated


def engine_command(graph_path: Path, output_dir: Path, days: int, items: list[str], variant: dict[str, Any]) -> list[str]:
    floor_factor = float(variant["floor_factor"])
    cmd = [
        sys.executable,
        str(ENGINE),
        "--input",
        str(graph_path),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(days),
        "--output-profile",
        "compact",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--skip-map",
        "--skip-plots",
        *INITIAL_STATE_ARGS,
    ]
    if "soft_safety_factor" in variant:
        cmd.extend(["--soft-safety-time-stock-target-factor", f"{float(variant['soft_safety_factor']):g}"])
    if "external_capacity_scale" in variant:
        cmd.extend(["--external-procurement-nominal-capacity-scale", f"{float(variant['external_capacity_scale']):g}"])
    if "external_lead_days" in variant:
        cmd.extend(["--external-procurement-lead-days", str(int(variant["external_lead_days"]))])
    if "external_proactive" in variant and not bool(variant["external_proactive"]):
        cmd.append("--no-external-procurement-proactive-replenishment")
    if "external_enabled" in variant and not bool(variant["external_enabled"]):
        cmd.append("--no-external-procurement-enabled")
    if "external_pipeline_fill" in variant:
        cmd.extend(
            [
                "--external-procurement-upstream-pipeline-fill-ratio",
                f"{float(variant['external_pipeline_fill']):g}",
            ]
        )
    for node_id, item_id in M1430_BASE_FLOOR_PAIRS:
        cmd.extend(["--mrp-base-stock-floor-factor-pair", f"{node_id},{item_id},1"])
    for item_id in items:
        cmd.extend(["--mrp-base-stock-floor-factor-pair", f"{FACTORY},{item_id},{floor_factor:g}"])
    return cmd


def run_variant(root: Path, variant: dict[str, Any], days: int, graph: dict[str, Any], items: list[str]) -> Path:
    variant_dir = root / str(variant["name"])
    graph_path = variant_dir / "input_graph.json"
    output_dir = variant_dir / "run"
    summary_path = output_dir / "summaries" / "first_simulation_summary.json"
    if summary_path.exists():
        return output_dir
    variant_dir.mkdir(parents=True, exist_ok=True)
    write_json(graph_path, scaled_graph(graph, items, variant))
    cmd = engine_command(graph_path, output_dir, days, items, variant)
    (variant_dir / "command.txt").write_text(" ".join(cmd), encoding="utf-8")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    return output_dir


def read_real_component_stock(days: int) -> list[dict[str, Any]]:
    path = source_file("Stock_Composants*_Cos.csv")
    rows: list[dict[str, Any]] = []
    for row in read_csv_dicts(path, delimiter=";"):
        snapshot_date = datetime.fromisoformat(row["Date de photo DMP"]).date()
        day = (snapshot_date - START_DATE).days
        if 0 <= day < days:
            rows.append(
                {
                    "date": snapshot_date.isoformat(),
                    "day": day,
                    "observed_value": parse_float(row["Sum_Valeur totale du stock"]),
                }
            )
    return rows


def read_real_availability() -> dict[str, Any]:
    path = source_file("Dispo_PF_Projet*.csv")
    rows = [
        row
        for row in read_csv_dicts(path, delimiter=";")
        if str(row.get("SKU Code", "")).strip() == PRODUCT_CODE
        and str(row.get("Year Week Snapshot", "")).startswith("2025|")
    ]
    rupture_weeks = [parse_float(row.get("Nb_Semaine_Rupture_Produit")) for row in rows]
    repetitions = [parse_float(row.get("Répétition_Rupture_Produit")) for row in rows]
    return {
        "snapshots": len(rows),
        "sum_rupture_weeks_snapshot": sum(rupture_weeks),
        "max_rupture_weeks_snapshot": max(rupture_weeks) if rupture_weeks else 0.0,
        "max_repetition_snapshot": max(repetitions) if repetitions else 0.0,
        "rows": rows,
    }


def load_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    return read_csv_dicts(path)


def simulated_stock_value(
    output_dir: Path,
    real_rows: list[dict[str, Any]],
    items: list[str],
    prices: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    stocks = {
        (int(row["day"]), row["item_id"]): parse_float(row["stock_end_of_day"])
        for row in load_table(output_dir / "data" / "production_input_stocks_daily.csv")
        if row.get("node_id") == FACTORY
    }
    mrp = {
        (int(row["day"]), row["item_id"]): parse_float(row["target_stock_qty"])
        for row in load_table(output_dir / "data" / "mrp_trace_daily.csv")
        if row.get("node_id") == FACTORY
    }
    stock_values: list[float] = []
    immobilized_values: list[float] = []
    for real in real_rows:
        day = int(real["day"])
        total_stock = 0.0
        total_immobilized = 0.0
        for item_id in items:
            unit_price = prices.get(item_id, {}).get("unit_price")
            if unit_price is None:
                continue
            stock_qty = stocks.get((day, item_id), 0.0)
            target_qty = mrp.get((day, item_id), 0.0)
            total_stock += stock_qty * float(unit_price)
            total_immobilized += max(0.0, stock_qty - target_qty) * float(unit_price)
        stock_values.append(total_stock)
        immobilized_values.append(total_immobilized)
    observed = [float(row["observed_value"]) for row in real_rows]
    return {
        "observed_mean": statistics.mean(observed) if observed else 0.0,
        "sim_stock_value_mean": statistics.mean(stock_values) if stock_values else 0.0,
        "sim_stock_value_min": min(stock_values) if stock_values else 0.0,
        "sim_stock_value_max": max(stock_values) if stock_values else 0.0,
        "sim_immobilized_value_mean": statistics.mean(immobilized_values) if immobilized_values else 0.0,
        "sim_immobilized_value_min": min(immobilized_values) if immobilized_values else 0.0,
        "sim_immobilized_value_max": max(immobilized_values) if immobilized_values else 0.0,
    }


def simulated_service(output_dir: Path) -> dict[str, Any]:
    rows = [
        row
        for row in load_table(output_dir / "data" / "production_demand_service_daily.csv")
        if row.get("item_id") == PRODUCT_ITEM
    ]
    demand = sum(parse_float(row.get("demand_qty")) for row in rows)
    served = sum(parse_float(row.get("served_qty")) for row in rows)
    backlog_values = [parse_float(row.get("backlog_end_qty")) for row in rows]
    shortfall_days = [
        int(row["day"])
        for row in rows
        if parse_float(row.get("served_qty")) + 1e-9 < parse_float(row.get("demand_qty"))
        or parse_float(row.get("backlog_end_qty")) > 1e-9
    ]
    shortfall_weeks = sorted({day // 7 for day in shortfall_days})
    return {
        "demand_268091": demand,
        "served_268091": served,
        "fill_rate_268091": served / demand if demand else 1.0,
        "backlog_days_268091": sum(1 for val in backlog_values if val > 1e-9),
        "max_backlog_268091": max(backlog_values) if backlog_values else 0.0,
        "shortfall_weeks_268091": len(shortfall_weeks),
    }


def simulated_production(output_dir: Path) -> dict[str, Any]:
    rows = [
        row
        for row in load_table(output_dir / "data" / "production_campaigns.csv")
        if row.get("node_id") == FACTORY and row.get("output_item_id") == PRODUCT_ITEM
    ]
    delayed = [row for row in rows if row.get("status") != "completed_without_delay"]
    return {
        "campaigns_268091": len(rows),
        "delayed_campaigns_268091": len(delayed),
        "delay_days_268091": sum(parse_float(row.get("delay_day_count")) for row in delayed),
        "blocked_lot_qty_268091": sum(parse_float(row.get("blocked_lot_qty")) for row in delayed),
        "actual_produced_268091": sum(parse_float(row.get("actual_qty")) for row in rows),
    }


def read_summary(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "summaries" / "first_simulation_summary.json"
    return read_json(path) if path.exists() else {}


def eur(value: float) -> str:
    return f"{value / 1_000_000:.2f} MEUR"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def markdown_report(payload: dict[str, Any]) -> str:
    observed_stock = float(payload["observed_component_stock_mean"])
    service_target = float(payload.get("real_service_target", 0.0) or 0.0)
    observed_shortfall_weeks = float(payload["real_availability"]["sum_rupture_weeks_snapshot"])
    best_stock = min(
        payload["variants"],
        key=lambda row: abs(float(row["sim_immobilized_value_mean"]) - observed_stock),
    )
    best_service = min(
        payload["variants"],
        key=lambda row: abs(float(row["fill_rate_268091"]) - service_target),
    )
    best_shortfall = min(
        payload["variants"],
        key=lambda row: abs(float(row["shortfall_weeks_268091"]) - observed_shortfall_weeks),
    )
    best_balanced = min(
        payload["variants"],
        key=lambda row: (
            abs(float(row["sim_immobilized_value_mean"]) / observed_stock - 1.0)
            + abs(float(row["shortfall_weeks_268091"]) - observed_shortfall_weeks)
            / max(1.0, observed_shortfall_weeks)
            + (abs(float(row["fill_rate_268091"]) - service_target) if service_target > 0.0 else 0.0)
        ),
    )
    lines = [
        "# Calibration stock/service 268091",
        "",
        f"Cible observee stock composants immobilise Cos: {eur(observed_stock)}.",
        f"Cible metier taux de service Cos: {pct(service_target)}.",
        (
            "Disponibilite reelle 2025: "
            f"{observed_shortfall_weeks:.0f} semaines de rupture cumulees "
            "sur les snapshots disponibles."
        ),
        "",
        "## Synthese",
        "",
        (
            f"- Plus proche du stock observe: `{best_stock['name']}` "
            f"({eur(best_stock['sim_immobilized_value_mean'])}, "
            f"fill rate {pct(best_stock['fill_rate_268091'])}, "
            f"{best_stock['shortfall_weeks_268091']:.0f} semaines shortfall)."
        ),
        (
            f"- Plus proche du taux de service cible: `{best_service['name']}` "
            f"(fill rate {pct(best_service['fill_rate_268091'])}, "
            f"{eur(best_service['sim_immobilized_value_mean'])} immobilises, "
            f"{best_service['shortfall_weeks_268091']:.0f} semaines shortfall)."
        ),
        (
            f"- Plus proche des ruptures observees: `{best_shortfall['name']}` "
            f"({best_shortfall['shortfall_weeks_268091']:.0f} semaines shortfall, "
            f"{eur(best_shortfall['sim_immobilized_value_mean'])} immobilises)."
        ),
        (
            f"- Meilleur compromis stock/service de cette grille: `{best_balanced['name']}` "
            f"({eur(best_balanced['sim_immobilized_value_mean'])}, "
            f"fill rate {pct(best_balanced['fill_rate_268091'])}, "
            f"{best_balanced['shortfall_weeks_268091']:.0f} semaines shortfall)."
        ),
        (
            "- Lecture: la cible 0.26 MEUR n'est pas atteinte avec un service plausible dans cette grille. "
            "Le modele maintient encore un stock plancher via commandes MRP, lots et flux fournisseurs; "
            "il faut donc calibrer par composant/fournisseur, pas seulement sur le total euros."
        ),
        "",
        "| Variante | Stock initial scale | Floor MRP | Stock moyen sim | Immobilise moyen sim | Ratio vs observe | Fill rate 268091 | Jours backlog | Semaines shortfall | Campagnes reportees |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["variants"]:
        ratio = row["sim_immobilized_value_mean"] / payload["observed_component_stock_mean"]
        lines.append(
            "| "
            + " | ".join(
                [
                    row["name"],
                    f"{row['initial_scale']:.2f}",
                    f"{row['floor_factor']:.2f}",
                    eur(row["sim_stock_value_mean"]),
                    eur(row["sim_immobilized_value_mean"]),
                    f"{ratio:.2f}",
                    pct(row["fill_rate_268091"]),
                    f"{row['backlog_days_268091']:.0f}",
                    f"{row['shortfall_weeks_268091']:.0f}",
                    f"{row['delayed_campaigns_268091']:.0f}",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Parametres des variantes",
            "",
            "| Variante | Safety stock j | Soft safety | Cap appro amont | Delai appro amont | Appro proactive |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in payload["variants"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["name"],
                    f"{row.get('safety_stock_days', '')}",
                    f"{row.get('soft_safety_factor', '')}",
                    f"{row.get('external_capacity_scale', '')}",
                    f"{row.get('external_lead_days', '')}",
                    (
                        "appro amont off"
                        if row.get("external_enabled") is False
                        else (
                            "non"
                            if row.get("external_proactive") is False
                            else ("" if row.get("external_proactive", "") == "" else str(row.get("external_proactive")))
                        )
                    ),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Lecture",
            "",
            (
                "- Les variantes qui approchent le stock observe degradent fortement la disponibilite produit; "
                "les variantes qui gardent un niveau de rupture proche du reel restent encore a 3-4x le stock observe."
            ),
            "- Le contributeur residuel principal dans les variantes basses est item:049371; il faut verifier son perimetre reel, son prix, son lead time et ses commandes en cours.",
            "- Ces runs sont des tests 2025 sans lot trace ni map; la variante retenue devra etre rejouee sur 5 ans avec la lotification complete.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--output-root", type=Path, default=EXPERIMENT_ROOT)
    parser.add_argument("--skip-runs", action="store_true")
    args = parser.parse_args()

    graph = read_json(BASE_GRAPH)
    items = component_items(graph)
    prices = price_map(graph, items)
    real_rows = read_real_component_stock(args.days)
    real_availability = read_real_availability()
    observed_mean = statistics.mean(float(row["observed_value"]) for row in real_rows)
    base_initial_value = graph_initial_value(graph, items, prices)

    run_root = args.output_root / f"{args.days}d"
    variant_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        if args.skip_runs:
            output_dir = run_root / str(variant["name"]) / "run"
        else:
            output_dir = run_variant(run_root, variant, args.days, graph, items)
        summary = read_summary(output_dir)
        row = {
            "name": variant["name"],
            "initial_scale": float(variant["initial_scale"]),
            "floor_factor": float(variant["floor_factor"]),
            "safety_stock_days": variant.get("safety_stock_days", ""),
            "soft_safety_factor": variant.get("soft_safety_factor", ""),
            "external_capacity_scale": variant.get("external_capacity_scale", ""),
            "external_lead_days": variant.get("external_lead_days", ""),
            "external_proactive": variant.get("external_proactive", ""),
            "external_enabled": variant.get("external_enabled", ""),
            "opening_stock_value_estimated": base_initial_value * float(variant["initial_scale"]),
            "run_dir": str(output_dir),
            **simulated_stock_value(output_dir, real_rows, items, prices),
            **simulated_service(output_dir),
            **simulated_production(output_dir),
            "global_fill_rate": (summary.get("kpis") or {}).get("fill_rate"),
            "global_total_cost": (summary.get("kpis") or {}).get("total_cost"),
        }
        variant_rows.append(row)

    payload = {
        "schema_version": "etudecas.stock_target_268091_calibration.v1",
        "days": args.days,
        "product_code": PRODUCT_CODE,
        "factory": FACTORY,
        "component_items": items,
        "components_without_price": [item for item in items if prices.get(item, {}).get("unit_price") is None],
        "base_opening_stock_value_estimated": base_initial_value,
        "observed_component_stock_mean": observed_mean,
        "real_service_target": REAL_SERVICE_TARGETS.get(PRODUCT_CODE),
        "real_availability": real_availability,
        "variants": variant_rows,
    }
    report_dir = run_root / "report"
    write_json(report_dir / "stock_service_calibration_summary.json", payload)
    write_csv(report_dir / "stock_service_calibration_variants.csv", variant_rows)
    (report_dir / "stock_service_calibration_report.md").write_text(markdown_report(payload), encoding="utf-8")
    best = min(variant_rows, key=lambda row: abs(row["sim_immobilized_value_mean"] - observed_mean))
    print(
        f"[OK] best={best['name']} sim_immob={best['sim_immobilized_value_mean']:.1f} "
        f"observed={observed_mean:.1f} fill_268091={best['fill_rate_268091']:.4f} report={report_dir}"
    )


if __name__ == "__main__":
    main()
