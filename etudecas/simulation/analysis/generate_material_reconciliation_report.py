#!/usr/bin/env python3
"""Refresh the 1y material reconciliation report from the current simulation outputs.

This script updates the simulation-dependent columns of the existing reconciliation CSV
while preserving the source-truth quantities already derived from the XLSX data.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def to_float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def classify_row(row: dict[str, str]) -> str:
    source_opening = to_float(row["initial_stock_in_sim_unit"])
    graph_seed = to_float(row["graph_seed_initial"])
    sim_opening = to_float(row["sim_opening_stock"])
    theoretical_gap = to_float(row["theoretical_gap_after_source_stock"])
    delivered = to_float(row["sim_delivered_qty"])
    ending = to_float(row["sim_ending_stock"])

    prefixes: list[str] = []
    if abs(graph_seed - source_opening) <= max(1e-6, abs(source_opening) * 1e-6):
        prefixes.append("graph seed matches source stock")
    else:
        prefixes.append("graph seed diverges from source stock")

    if abs(sim_opening - graph_seed) > max(1e-6, max(abs(sim_opening), abs(graph_seed)) * 1e-6):
        prefixes.append("sim opening diverges from graph seed")

    if theoretical_gap <= 1e-9 and delivered <= 1e-9:
        prefixes.append("coherent dormant: source stock covers annual need")
        return "; ".join(prefixes)

    if theoretical_gap > 1e-9 and delivered <= 1e-9:
        prefixes.append("under-delivered vs source gap")
        return "; ".join(prefixes)

    if theoretical_gap > 1e-9:
        ratio = delivered / theoretical_gap if theoretical_gap > 1e-9 else 0.0
        if ratio > 1.10:
            prefixes.append("over-delivered vs source gap")
        elif ratio < 0.90:
            prefixes.append("under-delivered vs source gap")
        else:
            prefixes.append("roughly coherent vs source gap")
    else:
        prefixes.append("delivered despite zero theoretical gap")

    if ending > max(1e-6, 0.10 * max(delivered, theoretical_gap, 1.0)):
        prefixes.append("ending stock builds up")

    return "; ".join(prefixes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh material reconciliation from current simulation outputs.")
    parser.add_argument(
        "--base-csv",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/source_truth_vs_1y_material_reconciliation.csv",
    )
    parser.add_argument(
        "--input-stocks-csv",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_input_stocks_daily.csv",
    )
    parser.add_argument(
        "--shipments-csv",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/production_supplier_shipments_daily.csv",
    )
    parser.add_argument(
        "--output-csv",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/data/source_truth_vs_1y_material_reconciliation.csv",
    )
    parser.add_argument(
        "--output-md",
        default="etudecas/simulation/result/reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated/reports/source_truth_vs_1y_material_reconciliation.md",
    )
    args = parser.parse_args()

    base_rows = load_csv_rows(Path(args.base_csv))
    input_rows = load_csv_rows(Path(args.input_stocks_csv))
    shipment_rows = load_csv_rows(Path(args.shipments_csv))

    opening_by_pair: dict[tuple[str, str], float] = {}
    ending_by_pair: dict[tuple[str, str], float] = {}
    for row in input_rows:
        key = (str(row.get("node_id") or ""), str(row.get("item_id") or ""))
        opening_by_pair.setdefault(key, to_float(row.get("stock_before_production")))
        ending_by_pair[key] = to_float(row.get("stock_end_of_day"))

    delivered_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in shipment_rows:
        key = (str(row.get("dst_node_id") or ""), str(row.get("item_id") or ""))
        delivered_by_pair[key] += to_float(row.get("shipped_qty"))

    refreshed_rows: list[dict[str, str]] = []
    strong_issues: list[dict[str, str]] = []
    for row in base_rows:
        node_id = str(row.get("consuming_node") or "")
        item_id = f"item:{str(row.get('component') or '')}"
        key = (node_id, item_id)
        row["sim_opening_stock"] = f"{opening_by_pair.get(key, 0.0):.6f}"
        row["sim_delivered_qty"] = f"{delivered_by_pair.get(key, 0.0):.6f}"
        row["sim_ending_stock"] = f"{ending_by_pair.get(key, 0.0):.6f}"
        row["diagnostic"] = classify_row(row)
        refreshed_rows.append(row)
        if any(flag in row["diagnostic"] for flag in ("over-delivered", "under-delivered", "diverges")):
            strong_issues.append(row)

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(refreshed_rows[0].keys()))
        writer.writeheader()
        writer.writerows(refreshed_rows)

    lines = [
        "# Source Truth vs 1Y Material Reconciliation",
        "",
        "This report keeps the XLSX-derived annual requirement and source opening quantities,",
        "then refreshes the simulation-dependent columns from the current baseline outputs.",
        "",
        f"- Families audited: `{len(refreshed_rows)}`",
        f"- Strong reconciliation issues: `{len(strong_issues)}`",
        "",
        "## Strong Issues",
    ]
    if not strong_issues:
        lines.append("- None")
    else:
        for row in strong_issues:
            lines.append(
                f"- `{row['component']}` @ `{row['consuming_node']}`: annual req `{row['annual_requirement_in_sim_unit']}`, "
                f"source opening `{row['initial_stock_in_sim_unit']}`, sim delivered `{row['sim_delivered_qty']}`, "
                f"sim ending `{row['sim_ending_stock']}` -> {row['diagnostic']}"
            )
    lines.extend(
        [
            "",
            "## Reference Files",
            f"- Base reconciliation CSV: `{args.base_csv}`",
            f"- Simulation input stocks: `{args.input_stocks_csv}`",
            f"- Simulation supplier shipments: `{args.shipments_csv}`",
        ]
    )

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
