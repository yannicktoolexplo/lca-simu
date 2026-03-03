#!/usr/bin/env python3
"""
Analyze supply chain behavior using simulation outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze supply chain from simulation outputs.")
    parser.add_argument(
        "--sim-summary",
        default="etudecas/simulation/result/first_simulation_summary.json",
        help="Simulation summary JSON.",
    )
    parser.add_argument(
        "--sim-daily",
        default="etudecas/simulation/result/first_simulation_daily.csv",
        help="Simulation daily CSV.",
    )
    parser.add_argument(
        "--prep-report",
        default="etudecas/simulation_prep/result/simulation_prep_report.json",
        help="Simulation preparation report JSON (optional context).",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/SC_analysis/result",
        help="Output directory for analysis artifacts.",
    )
    return parser.parse_args()


def to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def pct(n: float, d: float) -> float:
    if d == 0:
        return 0.0
    return 100.0 * n / d


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    w = pos - lo
    return xs[lo] * (1 - w) + xs[hi] * w


def read_daily_csv(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                {
                    "day": to_float(r.get("day"), 0.0),
                    "demand": to_float(r.get("demand"), 0.0),
                    "served": to_float(r.get("served"), 0.0),
                    "backlog_end": to_float(r.get("backlog_end"), 0.0),
                    "arrivals_qty": to_float(r.get("arrivals_qty"), 0.0),
                    "produced_qty": to_float(r.get("produced_qty"), 0.0),
                    "shipped_qty": to_float(r.get("shipped_qty"), 0.0),
                    "inventory_total": to_float(r.get("inventory_total"), 0.0),
                    "holding_cost_day": to_float(r.get("holding_cost_day"), 0.0),
                    "transport_cost_day": to_float(r.get("transport_cost_day"), 0.0),
                }
            )
    return rows


def analyze(summary: dict[str, Any], daily: list[dict[str, float]], prep: dict[str, Any] | None) -> dict[str, Any]:
    kpi = summary.get("kpis", {})

    total_demand = to_float(kpi.get("total_demand"), sum(r["demand"] for r in daily))
    total_served = to_float(kpi.get("total_served"), sum(r["served"] for r in daily))
    fill_rate = to_float(kpi.get("fill_rate"), 0.0)
    ending_backlog = to_float(kpi.get("ending_backlog"), 0.0)
    total_cost = to_float(kpi.get("total_cost"), 0.0)
    holding_cost = to_float(kpi.get("total_holding_cost"), 0.0)
    transport_cost = to_float(kpi.get("total_transport_cost"), 0.0)

    days = len(daily)
    backlog_days = [int(r["day"]) for r in daily if r["backlog_end"] > 0]
    max_backlog_row = max(daily, key=lambda x: x["backlog_end"]) if daily else {"day": 0.0, "backlog_end": 0.0}
    stockout_days = [int(r["day"]) for r in daily if r["served"] + 1e-9 < r["demand"]]

    backlog_clear_day = None
    seen_backlog = False
    for r in daily:
        if r["backlog_end"] > 0:
            seen_backlog = True
        if seen_backlog and r["backlog_end"] == 0:
            backlog_clear_day = int(r["day"])
            break

    inv_series = [r["inventory_total"] for r in daily]
    inv_avg = mean(inv_series) if inv_series else 0.0
    inv_p10 = quantile(inv_series, 0.10)
    inv_p90 = quantile(inv_series, 0.90)

    daily_demand = [r["demand"] for r in daily]
    daily_served = [r["served"] for r in daily]
    daily_shipped = [r["shipped_qty"] for r in daily]
    daily_arrivals = [r["arrivals_qty"] for r in daily]
    demand_volatility = pstdev(daily_demand) if len(daily_demand) > 1 else 0.0
    shipped_volatility = pstdev(daily_shipped) if len(daily_shipped) > 1 else 0.0
    bullwhip_proxy = None
    if demand_volatility > 1e-9:
        bullwhip_proxy = shipped_volatility / demand_volatility

    avg_daily_cost = total_cost / days if days > 0 else 0.0
    unit_cost_served = total_cost / total_served if total_served > 0 else 0.0
    transport_share = pct(transport_cost, total_cost)
    holding_share = pct(holding_cost, total_cost)
    throughput_balance = {
        "arrivals_vs_shipped_ratio": (sum(daily_arrivals) / sum(daily_shipped)) if sum(daily_shipped) > 0 else 0.0,
        "produced_vs_served_ratio": (to_float(kpi.get("total_produced"), 0.0) / total_served) if total_served > 0 else 0.0,
    }

    spike_threshold = (mean(daily_shipped) + 2 * pstdev(daily_shipped)) if len(daily_shipped) > 1 else float("inf")
    shipped_spike_days = [int(r["day"]) for r in daily if r["shipped_qty"] > spike_threshold]

    demand_unique = sorted({round(v, 6) for v in daily_demand})

    warnings: list[str] = []
    recommendations: list[str] = []
    if fill_rate >= 0.99 and total_served > 0:
        recommendations.append("Le niveau de service est bon. Passer à des scénarios stress (retard fournisseur, hausse demande).")
    if stockout_days:
        warnings.append(f"Ruptures observées sur {len(stockout_days)} jour(s): {stockout_days}.")
        recommendations.append("Augmenter le stock de sécurité sur les couples critiques pour absorber le démarrage.")
    if holding_share > 70:
        warnings.append("Le coût de stockage domine le coût total.")
        recommendations.append("Réduire les stocks initiaux et calibrer les politiques de réapprovisionnement.")
    if demand_unique and len(demand_unique) == 1:
        warnings.append("Demande entièrement constante: la simulation ne teste pas la variabilité.")
        recommendations.append("Ajouter une demande variable (step/seasonality) pour tester la robustesse.")
    if days < 30:
        warnings.append("Horizon court (<30 jours): vision partielle de la dynamique.")
        recommendations.append("Allonger l'horizon (60-120 jours) pour observer les régimes stabilisés.")
    if bullwhip_proxy is not None and bullwhip_proxy > 1.3:
        warnings.append(f"Signal bullwhip potentiel (proxy={bullwhip_proxy:.2f}).")
        recommendations.append("Limiter la variabilité des expéditions via politique de lissage.")
    if not warnings:
        warnings.append("Aucun signal d'alerte majeur détecté sur ce run.")
    if not recommendations:
        recommendations.append("Lancer un scénario de référence alternatif pour comparaison.")

    prep_context = {}
    if prep:
        prep_context = {
            "prep_changed_edges": (prep.get("changed_entities") or {}).get("edge_count", 0),
            "prep_changed_nodes": (prep.get("changed_entities") or {}).get("node_count", 0),
            "prep_zero_demand_after_prep": (prep.get("validation_after_prep") or {}).get("zero_demand_rows_count", 0),
            "prep_missing_geo_after_prep": (prep.get("validation_after_prep") or {}).get("missing_geo_nodes_count", 0),
        }

    return {
        "run_context": {
            "scenario_id": summary.get("scenario_id"),
            "sim_days": summary.get("sim_days"),
            "input_file": summary.get("input_file"),
            "counts": summary.get("counts", {}),
        },
        "service_level": {
            "total_demand": total_demand,
            "total_served": total_served,
            "fill_rate": fill_rate,
            "ending_backlog": ending_backlog,
            "backlog_days_count": len(backlog_days),
            "stockout_days_count": len(stockout_days),
            "stockout_days": stockout_days,
            "max_backlog": max_backlog_row["backlog_end"],
            "max_backlog_day": int(max_backlog_row["day"]),
            "backlog_clear_day": backlog_clear_day,
        },
        "flow_dynamics": {
            "total_shipped": to_float(kpi.get("total_shipped"), sum(daily_shipped)),
            "total_arrived": to_float(kpi.get("total_arrived"), sum(daily_arrivals)),
            "total_produced": to_float(kpi.get("total_produced"), 0.0),
            "shipped_spike_days": shipped_spike_days,
            "demand_volatility_std": demand_volatility,
            "shipped_volatility_std": shipped_volatility,
            "bullwhip_proxy": bullwhip_proxy,
            **throughput_balance,
        },
        "inventory_costs": {
            "avg_inventory": inv_avg,
            "inventory_p10": inv_p10,
            "inventory_p90": inv_p90,
            "ending_inventory": to_float(kpi.get("ending_inventory"), daily[-1]["inventory_total"] if daily else 0.0),
            "total_cost": total_cost,
            "holding_cost": holding_cost,
            "transport_cost": transport_cost,
            "holding_cost_share_pct": holding_share,
            "transport_cost_share_pct": transport_share,
            "avg_daily_cost": avg_daily_cost,
            "cost_per_served_unit": unit_cost_served,
        },
        "model_inputs_signal": {
            "demand_unique_values": demand_unique,
            "days_simulated": days,
        },
        "prep_context": prep_context,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def write_outputs(analysis: dict[str, Any], daily: list[dict[str, float]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "sc_analysis_summary.json"
    report_path = output_dir / "sc_analysis_report.md"
    enriched_daily_path = output_dir / "sc_analysis_daily_enriched.csv"

    summary_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")

    # Enrich daily table with cumulative demand/served and cumulative fill rate.
    cum_demand = 0.0
    cum_served = 0.0
    rows_out: list[dict[str, Any]] = []
    for r in daily:
        cum_demand += r["demand"]
        cum_served += r["served"]
        cum_fill = (cum_served / cum_demand) if cum_demand > 0 else 1.0
        row = dict(r)
        row["cum_demand"] = round(cum_demand, 4)
        row["cum_served"] = round(cum_served, 4)
        row["cum_fill_rate"] = round(cum_fill, 6)
        rows_out.append(row)

    with enriched_daily_path.open("w", encoding="utf-8", newline="") as f:
        if rows_out:
            writer = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            writer.writeheader()
            writer.writerows(rows_out)

    sl = analysis["service_level"]
    fd = analysis["flow_dynamics"]
    ic = analysis["inventory_costs"]
    mis = analysis["model_inputs_signal"]
    warnings_block = "\n".join(f"- {w}" for w in analysis["warnings"])
    recos_block = "\n".join(f"- {r}" for r in analysis["recommendations"])

    report = f"""# SC analysis from simulation results

## Run context
- Scenario: {analysis['run_context'].get('scenario_id')}
- Horizon: {analysis['run_context'].get('sim_days')} days
- Input graph: {analysis['run_context'].get('input_file')}

## Service performance
- Fill rate: {sl['fill_rate']:.4f}
- Total demand: {sl['total_demand']:.2f}
- Total served: {sl['total_served']:.2f}
- Ending backlog: {sl['ending_backlog']:.2f}
- Backlog days: {sl['backlog_days_count']}
- Stockout days: {sl['stockout_days_count']} ({sl['stockout_days']})
- Max backlog: {sl['max_backlog']:.2f} (day {sl['max_backlog_day']})
- Backlog clear day: {sl['backlog_clear_day']}

## Flow dynamics
- Total shipped: {fd['total_shipped']:.2f}
- Total arrived: {fd['total_arrived']:.2f}
- Total produced: {fd['total_produced']:.2f}
- Shipped spike days: {fd['shipped_spike_days']}
- Demand volatility (std): {fd['demand_volatility_std']:.4f}
- Shipped volatility (std): {fd['shipped_volatility_std']:.4f}
- Bullwhip proxy: {fd['bullwhip_proxy']}
- Arrivals/Shipped ratio: {fd['arrivals_vs_shipped_ratio']:.4f}
- Produced/Served ratio: {fd['produced_vs_served_ratio']:.4f}

## Inventory and costs
- Avg inventory: {ic['avg_inventory']:.2f}
- Inventory p10 / p90: {ic['inventory_p10']:.2f} / {ic['inventory_p90']:.2f}
- Ending inventory: {ic['ending_inventory']:.2f}
- Total cost: {ic['total_cost']:.2f}
- Holding cost: {ic['holding_cost']:.2f} ({ic['holding_cost_share_pct']:.2f}%)
- Transport cost: {ic['transport_cost']:.2f} ({ic['transport_cost_share_pct']:.2f}%)
- Avg daily cost: {ic['avg_daily_cost']:.2f}
- Cost per served unit: {ic['cost_per_served_unit']:.4f}

## Model input signal
- Demand unique values observed: {mis['demand_unique_values']}
- Days simulated: {mis['days_simulated']}

## Alerts
{warnings_block}

## Recommendations
{recos_block}

## Files
- sc_analysis_summary.json
- sc_analysis_report.md
- sc_analysis_daily_enriched.csv
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    args = parse_args()
    summary = json.loads(Path(args.sim_summary).read_text(encoding="utf-8"))
    daily = read_daily_csv(Path(args.sim_daily))

    prep = None
    prep_path = Path(args.prep_report)
    if prep_path.exists():
        prep = json.loads(prep_path.read_text(encoding="utf-8"))

    analysis = analyze(summary, daily, prep)
    write_outputs(analysis, daily, Path(args.output_dir))
    print(f"[OK] Analysis written to: {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
