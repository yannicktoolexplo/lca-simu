#!/usr/bin/env python3
"""Rebuild critical input material analysis and deep supply synthesis."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild critical input analysis from simulation outputs.")
    parser.add_argument(
        "--graph-json",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
    )
    parser.add_argument(
        "--stocks-csv",
        default="etudecas/simulation/result/production_input_stocks_daily.csv",
    )
    parser.add_argument(
        "--consumption-csv",
        default="etudecas/simulation/result/production_input_consumption_daily.csv",
    )
    parser.add_argument(
        "--arrivals-csv",
        default="etudecas/simulation/result/production_input_replenishment_arrivals_daily.csv",
    )
    parser.add_argument(
        "--shipments-csv",
        default="etudecas/simulation/result/production_input_replenishment_shipments_daily.csv",
    )
    parser.add_argument(
        "--baseline-summary",
        default="etudecas/simulation/result/first_simulation_summary.json",
    )
    parser.add_argument(
        "--baseline-daily-csv",
        default="etudecas/simulation/result/first_simulation_daily.csv",
    )
    parser.add_argument(
        "--sensitivity-summary",
        default="etudecas/simulation/sensibility/result/sensitivity_summary.json",
    )
    parser.add_argument(
        "--montecarlo-summary",
        default="etudecas/simulation/montecarlo/result/montecarlo_summary.json",
    )
    parser.add_argument(
        "--montecarlo-samples-csv",
        default="etudecas/simulation/montecarlo/result/montecarlo_samples.csv",
    )
    parser.add_argument(
        "--full-exploration-summary",
        default="etudecas/simulation/result/full_system_exploration_summary.json",
    )
    parser.add_argument(
        "--shock-summary",
        default="etudecas/simulation/sensibility/shock_campaign_result/shock_campaign_summary.json",
    )
    parser.add_argument(
        "--output-csv",
        default="etudecas/simulation/result/critical_input_materials_analysis.csv",
    )
    parser.add_argument(
        "--output-summary-json",
        default="etudecas/simulation/result/deep_supply_analysis_summary.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="etudecas/simulation/result/deep_supply_analysis.md",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def round_row(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, float):
            out[key] = round(value, 6)
        else:
            out[key] = value
    return out


def normalize(values: dict[tuple[str, str], float], *, inverse: bool = False) -> dict[tuple[str, str], float]:
    if not values:
        return {}
    lo = min(values.values())
    hi = max(values.values())
    if hi - lo <= 1e-12:
        return {key: 0.5 for key in values}
    norm = {key: (value - lo) / (hi - lo) for key, value in values.items()}
    if not inverse:
        return norm
    return {key: 1.0 - value for key, value in norm.items()}


def extract_baseline_kpis(summary: dict[str, Any]) -> dict[str, float]:
    kpis = summary.get("kpis") or {}
    return {
        "fill_rate": to_float(kpis.get("fill_rate")),
        "total_served": to_float(kpis.get("total_served")),
        "total_demand": to_float(kpis.get("total_demand")),
        "ending_backlog": to_float(kpis.get("ending_backlog")),
        "total_cost": to_float(kpis.get("total_cost")),
        "cost_share_holding": to_float(kpis.get("cost_share_holding")),
        "cost_share_transport": to_float(kpis.get("cost_share_transport")),
        "cost_share_purchase": to_float(kpis.get("cost_share_purchase")),
        "avg_inventory": to_float(kpis.get("avg_inventory")),
        "ending_inventory": to_float(kpis.get("ending_inventory")),
    }


def top_driver_lines(summary: dict[str, Any], kpi: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = ((summary.get("top_drivers") or {}).get(kpi) or [])[:limit]
    out = []
    for row in rows:
        out.append(
            {
                "parameter": row.get("parameter"),
                "normalized_sensitivity": to_float(row.get("normalized_sensitivity")),
                "slope_dy_dx": to_float(row.get("slope_dy_dx")),
            }
        )
    return out


def build_analysis(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    graph = load_json(Path(args.graph_json))
    baseline_summary = load_json(Path(args.baseline_summary))
    baseline_daily_rows = load_csv(Path(args.baseline_daily_csv))
    sensitivity_summary = load_json(Path(args.sensitivity_summary))
    montecarlo_summary = load_json(Path(args.montecarlo_summary))
    montecarlo_samples = load_csv(Path(args.montecarlo_samples_csv))
    full_exploration_summary = load_json(Path(args.full_exploration_summary))
    shock_summary = load_json(Path(args.shock_summary))

    stocks_rows = load_csv(Path(args.stocks_csv))
    consumption_rows = load_csv(Path(args.consumption_csv))
    arrivals_rows = load_csv(Path(args.arrivals_csv))
    shipments_rows = load_csv(Path(args.shipments_csv))

    factory_input_pairs: set[tuple[str, str]] = set()
    supplier_counts: dict[tuple[str, str], int] = {}
    lead_by_pair: dict[tuple[str, str], float] = {}

    node_type = {str(node.get("id")): str(node.get("type")) for node in graph.get("nodes") or []}
    for node in graph.get("nodes") or []:
        if str(node.get("type")) != "factory":
            continue
        node_id = str(node.get("id"))
        for process in node.get("processes") or []:
            for inp in process.get("inputs") or []:
                item_id = str(inp.get("item_id"))
                if item_id:
                    factory_input_pairs.add((node_id, item_id))

    inbound_suppliers: dict[tuple[str, str], set[str]] = defaultdict(set)
    inbound_leads: dict[tuple[str, str], list[float]] = defaultdict(list)
    for edge in graph.get("edges") or []:
        dst = str(edge.get("to"))
        src = str(edge.get("from"))
        if node_type.get(dst) != "factory":
            continue
        for item_id in edge.get("items") or []:
            key = (dst, str(item_id))
            inbound_suppliers[key].add(src)
            inbound_leads[key].append(to_float(((edge.get("lead_time") or {}).get("mean")), 0.0))
    supplier_counts = {key: len(value) for key, value in inbound_suppliers.items()}
    lead_by_pair = {key: max(values) if values else 0.0 for key, values in inbound_leads.items()}

    stock_metrics: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"min_stock": None, "sum_stock": 0.0, "day_count": 0, "stockout_days": 0}
    )
    for row in stocks_rows:
        key = (str(row["node_id"]), str(row["item_id"]))
        if key not in factory_input_pairs:
            continue
        stock = to_float(row.get("stock_before_production"))
        metrics = stock_metrics[key]
        metrics["sum_stock"] += stock
        metrics["day_count"] += 1
        metrics["stockout_days"] += 1 if stock <= 1e-9 else 0
        metrics["min_stock"] = stock if metrics["min_stock"] is None else min(metrics["min_stock"], stock)

    consumption_metrics: dict[tuple[str, str], float] = defaultdict(float)
    for row in consumption_rows:
        key = (str(row["node_id"]), str(row["item_id"]))
        if key in factory_input_pairs:
            consumption_metrics[key] += to_float(row.get("consumed_qty"))

    arrivals_metrics: dict[tuple[str, str], float] = defaultdict(float)
    for row in arrivals_rows:
        key = (str(row["node_id"]), str(row["item_id"]))
        if key in factory_input_pairs:
            arrivals_metrics[key] += to_float(row.get("arrived_qty"))

    shipments_metrics: dict[tuple[str, str], float] = defaultdict(float)
    for row in shipments_rows:
        key = (str(row["node_id"]), str(row["item_id"]))
        if key in factory_input_pairs:
            shipments_metrics[key] += to_float(row.get("shipped_to_node_qty"))

    rows: list[dict[str, Any]] = []
    cover_values: dict[tuple[str, str], float] = {}
    lead_values: dict[tuple[str, str], float] = {}
    volume_values: dict[tuple[str, str], float] = {}

    for key in sorted(factory_input_pairs):
        node_id, item_id = key
        stock = stock_metrics.get(key, {})
        total_consumed = consumption_metrics.get(key, 0.0)
        total_arrivals = arrivals_metrics.get(key, 0.0)
        total_shipments = shipments_metrics.get(key, 0.0)
        day_count = int(stock.get("day_count") or 0)
        avg_stock = to_float(stock.get("sum_stock")) / day_count if day_count else 0.0
        avg_cons_per_day = total_consumed / day_count if day_count else 0.0
        min_stock = to_float(stock.get("min_stock"), 0.0)
        cover_days = (avg_stock / avg_cons_per_day) if avg_cons_per_day > 1e-12 else 999999.0
        nearout_days = 0
        if avg_cons_per_day > 1e-12:
            nearout_days = sum(
                1
                for row in stocks_rows
                if (str(row["node_id"]), str(row["item_id"])) == key
                and to_float(row.get("stock_before_production")) <= avg_cons_per_day
            )
        row = {
            "node": node_id,
            "item": item_id,
            "suppliers": int(supplier_counts.get(key, 0)),
            "stockout_days": int(stock.get("stockout_days") or 0),
            "nearout_days": nearout_days,
            "min_stock": min_stock,
            "avg_stock": avg_stock,
            "avg_cons_per_day": avg_cons_per_day,
            "cover_days": cover_days,
            "total_consumed": total_consumed,
            "total_arrivals": total_arrivals,
            "total_shipments": total_shipments,
            "criticality_score": 0.0,
        }
        rows.append(row)
        cover_values[key] = min(cover_days, 365.0)
        lead_values[key] = lead_by_pair.get(key, 0.0)
        volume_values[key] = total_consumed

    volume_norm = normalize(volume_values)
    lead_norm = normalize(lead_values)
    cover_risk = normalize(cover_values, inverse=True)
    for row in rows:
        key = (str(row["node"]), str(row["item"]))
        supplier_count = max(1, int(row["suppliers"]))
        supplier_risk = 1.0 / supplier_count
        stockout_risk = 1.0 if int(row["stockout_days"]) > 0 else 0.0
        row["criticality_score"] = (
            0.40 * volume_norm.get(key, 0.0)
            + 0.25 * supplier_risk
            + 0.15 * lead_norm.get(key, 0.0)
            + 0.15 * cover_risk.get(key, 0.0)
            + 0.05 * stockout_risk
        )

    rows.sort(key=lambda row: (-to_float(row["criticality_score"]), -to_float(row["total_consumed"]), row["node"], row["item"]))
    rows = [round_row(row) for row in rows]

    baseline_kpis = round_row(extract_baseline_kpis(baseline_summary))
    shortfall_days = [row for row in baseline_daily_rows if to_float(row.get("served")) + 1e-9 < to_float(row.get("demand"))]
    max_backlog_row = max(baseline_daily_rows, key=lambda row: to_float(row.get("backlog_end")), default={})
    service_daily = {
        "days_with_shortfall": len(shortfall_days),
        "max_backlog": round(to_float(max_backlog_row.get("backlog_end")), 6),
        "day_of_max_backlog": int(to_float(max_backlog_row.get("day"))),
        "ending_backlog": baseline_kpis["ending_backlog"],
    }
    critical_materials_high_volume = [
        {
            "node_id": row["node"],
            "item_id": row["item"],
            "score": round(to_float(row["criticality_score"]), 3),
            "consumed_total": round(to_float(row["total_consumed"]), 3),
            "supplier_count": int(row["suppliers"]),
            "cover_days": round(to_float(row["cover_days"]), 3),
        }
        for row in rows[:10]
    ]
    sensitivity = {
        "fill_rate_top_drivers": top_driver_lines(sensitivity_summary, "kpi::fill_rate"),
        "backlog_top_drivers": top_driver_lines(sensitivity_summary, "kpi::ending_backlog"),
        "cost_top_drivers": top_driver_lines(sensitivity_summary, "kpi::total_cost"),
    }
    monte_fill = [to_float(row.get("kpi::fill_rate")) for row in montecarlo_samples if row.get("status") == "ok"]
    monte_backlog = [to_float(row.get("kpi::ending_backlog")) for row in montecarlo_samples if row.get("status") == "ok"]
    montecarlo = {
        "risk_probabilities": {
            "p_fill_lt_0_90": round(sum(1 for value in monte_fill if value < 0.90) / len(monte_fill), 6) if monte_fill else 0.0,
            "p_fill_lt_0_85": round(sum(1 for value in monte_fill if value < 0.85) / len(monte_fill), 6) if monte_fill else 0.0,
            "p_backlog_gt_100": round(sum(1 for value in monte_backlog if value > 100.0) / len(monte_backlog), 6) if monte_backlog else 0.0,
            "p_backlog_gt_200": round(sum(1 for value in monte_backlog if value > 200.0) / len(monte_backlog), 6) if monte_backlog else 0.0,
        },
        "top_runs": montecarlo_summary.get("top_runs") or {},
    }
    full_exploration = {
        "risk_probabilities": full_exploration_summary.get("risk_probabilities") or {},
        "top_runs": full_exploration_summary.get("top_runs") or {},
    }
    shocks = {
        "baseline_kpis": shock_summary.get("baseline_kpis") or {},
        "top_scenarios": shock_summary.get("top_scenarios") or {},
    }
    fill_driver_line = ", ".join(
        f"{row['parameter']} ({to_float(row['normalized_sensitivity']):+.3f})"
        for row in sensitivity["fill_rate_top_drivers"][:5]
    )
    backlog_driver_line = ", ".join(
        f"{row['parameter']} ({to_float(row['normalized_sensitivity']):+.3f})"
        for row in sensitivity["backlog_top_drivers"][:5]
    )
    cost_driver_line = ", ".join(
        f"{row['parameter']} ({to_float(row['normalized_sensitivity']):+.3f})"
        for row in sensitivity["cost_top_drivers"][:5]
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_kpis": baseline_kpis,
        "service_daily": service_daily,
        "critical_materials_high_volume": critical_materials_high_volume,
        "sensitivity": sensitivity,
        "montecarlo": montecarlo,
        "full_exploration": full_exploration,
        "shocks": shocks,
    }

    markdown_lines = [
        "# Analyse globale supply (synthese consolidee)",
        "",
        f"Date: {datetime.now(timezone.utc).date().isoformat()} (UTC)",
        "",
        "## 1) Baseline actuelle",
        f"- Fill rate: **{baseline_kpis['fill_rate']:.6f}** ({baseline_kpis['total_served']:.4f}/{baseline_kpis['total_demand']:.1f})",
        f"- Backlog final: **{baseline_kpis['ending_backlog']:.4f}**",
        f"- Cout total: **{baseline_kpis['total_cost']:.4f}**",
        f"- Inventaire moyen: **{baseline_kpis['avg_inventory']:.4f}** | inventaire final: **{baseline_kpis['ending_inventory']:.4f}**",
        f"- Service journalier: **{service_daily['days_with_shortfall']}** jours en sous-service, backlog max **{service_daily['max_backlog']:.4f}** au jour **{service_daily['day_of_max_backlog']}**",
        "",
        "## 2) Matieres d'entree les plus critiques",
        "Definition pratique: criticite structurelle = consommation + mono-sourcing + delai + couverture.",
        "",
        "| Rang | Factory | Item | Score | Conso totale | Nb fournisseurs | Couverture (jours) |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for idx, row in enumerate(critical_materials_high_volume[:10], start=1):
        markdown_lines.append(
            f"| {idx} | {row['node_id']} | {row['item_id']} | {row['score']:.3f} | "
            f"{row['consumed_total']:.3f} | {row['supplier_count']} | {row['cover_days']:.3f} |"
        )
    markdown_lines.extend(
        [
            "",
            "## 3) Sensibilite (top drivers normalises)",
            f"- Fill rate: {fill_driver_line}",
            f"- Backlog: {backlog_driver_line}",
            f"- Cout total: {cost_driver_line}",
            "",
            "## 4) Monte Carlo",
            f"- P(fill < 0.90): **{to_float(montecarlo['risk_probabilities']['p_fill_lt_0_90']):.4f}**",
            f"- P(fill < 0.85): **{to_float(montecarlo['risk_probabilities']['p_fill_lt_0_85']):.4f}**",
            f"- P(backlog > 100): **{to_float(montecarlo['risk_probabilities']['p_backlog_gt_100']):.4f}**",
            f"- P(backlog > 200): **{to_float(montecarlo['risk_probabilities']['p_backlog_gt_200']):.4f}**",
            "",
            "## 5) Exploration systeme large",
            f"- Probabilites de risque: `{json.dumps(full_exploration['risk_probabilities'], ensure_ascii=False)}`",
            "",
            "## 6) Campagne de chocs",
        ]
    )
    worst_fill = ((shocks["top_scenarios"] or {}).get("worst_fill_rate") or [])[:5]
    if worst_fill:
        for row in worst_fill:
            markdown_lines.append(
                f"- `{row.get('scenario_id')}`: fill={to_float(row.get('kpi::fill_rate')):.6f}, "
                f"backlog={to_float(row.get('kpi::ending_backlog')):.4f}, cost={to_float(row.get('kpi::total_cost')):.4f}"
            )
    else:
        markdown_lines.append("- Aucun scenario de choc disponible.")
    markdown_lines.extend(
        [
            "",
            "## 7) Points de vigilance",
            "1. Les intrants critiques mono-source restent prioritaires.",
            "2. `item:007923` est bien traite comme composant special de `M-1810`.",
            "3. Le service reste fortement sensible a la demande et au pilotage de `M-1810`.",
            "",
        ]
    )
    return rows, summary, "\n".join(markdown_lines)


def main() -> None:
    args = parse_args()
    rows, summary, markdown = build_analysis(args)

    output_csv = Path(args.output_csv)
    output_summary_json = Path(args.output_summary_json)
    output_markdown = Path(args.output_markdown)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    output_summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    output_markdown.write_text(markdown, encoding="utf-8")

    print(f"[OK] Critical CSV: {output_csv.resolve()}")
    print(f"[OK] Deep analysis summary: {output_summary_json.resolve()}")
    print(f"[OK] Deep analysis report: {output_markdown.resolve()}")


if __name__ == "__main__":
    main()
