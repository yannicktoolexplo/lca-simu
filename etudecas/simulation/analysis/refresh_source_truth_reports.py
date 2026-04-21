#!/usr/bin/env python3
"""Refresh source-truth reconciliation reports from the current simulation outputs."""

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
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def classify_1y_row(row: dict[str, str]) -> str:
    source_opening = to_float(row["initial_stock_in_sim_unit"])
    graph_seed = to_float(row["graph_seed_initial"])
    sim_opening = to_float(row["sim_opening_stock"])
    theoretical_gap = to_float(row["theoretical_gap_after_source_stock"])
    delivered = to_float(row["sim_delivered_qty"])
    ending = to_float(row["sim_ending_stock"])

    flags: list[str] = []
    if abs(graph_seed - source_opening) <= max(1e-6, abs(source_opening) * 1e-6):
        flags.append("graph seed matches source stock")
    else:
        flags.append("graph seed diverges from source stock")

    if abs(sim_opening - graph_seed) > max(1e-6, max(abs(sim_opening), abs(graph_seed)) * 1e-6):
        flags.append("sim opening diverges from graph seed")

    if theoretical_gap <= 1e-9 and delivered <= 1e-9:
        flags.append("coherent dormant: source stock covers annual need")
        return "; ".join(flags)

    if theoretical_gap > 1e-9 and delivered <= 1e-9:
        flags.append("under-delivered vs source gap")
        return "; ".join(flags)

    if theoretical_gap > 1e-9:
        ratio = delivered / theoretical_gap if theoretical_gap > 1e-9 else 0.0
        if ratio > 1.10:
            flags.append("over-delivered vs source gap")
        elif ratio < 0.90:
            flags.append("under-delivered vs source gap")
        else:
            flags.append("roughly coherent vs source gap")
    else:
        flags.append("delivered despite zero theoretical gap")

    if ending > max(1e-6, 0.10 * max(delivered, theoretical_gap, 1.0)):
        flags.append("ending stock builds up")

    return "; ".join(flags)


def classify_5y_row(row: dict[str, str]) -> str:
    coverage_5y = to_float(row.get("coverage_5y_source"))
    bb_qty = to_float(row.get("sim5y_bb_qty"))
    bn_qty = to_float(row.get("sim5y_bn_qty"))
    shipped_qty = to_float(row.get("sim5y_supplier_ship_qty"))
    active_supplier_count = int(round(to_float(row.get("sim5y_active_supplier_count"))))

    if coverage_5y >= 1.0 and active_supplier_count == 0 and shipped_qty <= 1e-9:
        return "coherent dormant: source stock still covers 5y"
    if active_supplier_count > 1:
        return "active multi-source on 5y"
    if active_supplier_count == 1 or shipped_qty > 1e-9:
        return "active on 5y"
    if bn_qty > 1e-9 or bb_qty > 1e-9:
        return "inactive despite 5y source gap"
    return "inactive on 5y"


def refresh_1y_reconciliation(output_root: Path) -> None:
    base_csv = output_root / "data" / "source_truth_vs_1y_material_reconciliation.csv"
    output_md = output_root / "reports" / "source_truth_vs_1y_material_reconciliation.md"
    if not base_csv.exists():
        return

    input_rows = load_csv_rows(output_root / "data" / "production_input_stocks_daily.csv")
    shipment_rows = load_csv_rows(output_root / "data" / "production_supplier_shipments_daily.csv")
    base_rows = load_csv_rows(base_csv)
    if not base_rows:
        return

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

    strong_issues: list[dict[str, str]] = []
    for row in base_rows:
        node_id = str(row.get("consuming_node") or "")
        item_id = f"item:{str(row.get('component') or '')}"
        key = (node_id, item_id)
        row["sim_opening_stock"] = f"{opening_by_pair.get(key, 0.0):.6f}"
        row["sim_delivered_qty"] = f"{delivered_by_pair.get(key, 0.0):.6f}"
        row["sim_ending_stock"] = f"{ending_by_pair.get(key, 0.0):.6f}"
        row["diagnostic"] = classify_1y_row(row)
        if any(flag in row["diagnostic"] for flag in ("over-delivered", "under-delivered", "diverges")):
            strong_issues.append(row)

    write_csv_rows(base_csv, base_rows)

    lines = [
        "# Source Truth vs 1Y Material Reconciliation",
        "",
        "This report keeps the XLSX-derived annual requirement and source opening quantities,",
        "then refreshes the simulation-dependent columns from the current baseline outputs.",
        "",
        f"- Families audited: `{len(base_rows)}`",
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
            f"- Reconciliation CSV: `{base_csv}`",
            f"- Simulation input stocks: `{output_root / 'data' / 'production_input_stocks_daily.csv'}`",
            f"- Simulation supplier shipments: `{output_root / 'data' / 'production_supplier_shipments_daily.csv'}`",
        ]
    )
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_5y_coverage(output_root: Path) -> None:
    base_csv = output_root / "data" / "source_truth_vs_5y_material_coverage.csv"
    output_md = output_root / "reports" / "source_truth_vs_5y_material_coverage.md"
    if not base_csv.exists():
        return

    base_rows = load_csv_rows(base_csv)
    mrp_rows = load_csv_rows(output_root / "data" / "mrp_trace_daily.csv")
    shipment_rows = load_csv_rows(output_root / "data" / "production_supplier_shipments_daily.csv")
    if not base_rows:
        return

    latest_trace_by_pair: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
    for row in mrp_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")))
        key = (node_id, item_id)
        prev = latest_trace_by_pair.get(key)
        if prev is None or day >= prev[0]:
            latest_trace_by_pair[key] = (day, row)

    shipped_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    suppliers_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in shipment_rows:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not src or not dst or not item_id:
            continue
        key = (dst, item_id)
        shipped_qty = max(0.0, to_float(row.get("shipped_qty")))
        if shipped_qty <= 1e-9:
            continue
        shipped_by_pair[key] += shipped_qty
        suppliers_by_pair[key].add(src)

    suspect_rows: list[dict[str, str]] = []
    for row in base_rows:
        node_id = str(row.get("consuming_node") or "")
        item_id = f"item:{str(row.get('component') or '')}"
        key = (node_id, item_id)
        latest_trace = latest_trace_by_pair.get(key, (0, {}))[1]
        row["sim5y_bb_qty"] = f"{to_float(latest_trace.get('bb_qty')):.6f}"
        row["sim5y_bn_qty"] = f"{to_float(latest_trace.get('bn_qty')):.6f}"
        row["sim5y_supplier_ship_qty"] = f"{shipped_by_pair.get(key, 0.0):.6f}"
        row["sim5y_active_supplier_count"] = str(len(suppliers_by_pair.get(key, set())))
        row["diagnostic"] = classify_5y_row(row)
        if "inactive despite" in row["diagnostic"]:
            suspect_rows.append(row)

    write_csv_rows(base_csv, base_rows)

    active_rows = [row for row in base_rows if "active" in str(row.get("diagnostic") or "")]
    lines = [
        "# Source Truth vs 5Y Material Coverage",
        "",
        "This report links workbook-derived demand and BOM requirements to the 5-year simulation outputs.",
        "",
        "Reference data:",
        "- `demand_PF.xlsx` for annual finished-goods demand",
        "- `268967.xlsx`, `268191.xlsx`, `021081.xlsx` for BOM/FIA",
        "- `Stocks_MRP.xlsx` for initial stock snapshot",
        "",
        "Simulation data:",
        "- `production_supplier_shipments_daily.csv`",
        "- `mrp_trace_daily.csv`",
        "",
        "Formula:",
        "- `coverage_5y_source = initial_stock_xlsx / (annual_requirement_xlsx * 5)`",
        "",
        f"- Total families audited: `{len(base_rows)}`",
        f"- Active on 5y: `{len(active_rows)}`",
        f"- Suspect under source-truth 5y test: `{len(suspect_rows)}`",
        "",
        "## Suspect Rows",
    ]
    if not suspect_rows:
        lines.append("- None")
    else:
        for row in suspect_rows:
            lines.append(
                f"- `{row['component']}` @ `{row['consuming_node']}`: coverage 5y `{row['coverage_5y_source']}`, "
                f"bb `{row['sim5y_bb_qty']}`, bn `{row['sim5y_bn_qty']}`, shipped `{row['sim5y_supplier_ship_qty']}` "
                f"-> {row['diagnostic']}"
            )
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh source-truth reports from current simulation outputs.")
    parser.add_argument("--output-root", required=True, help="Simulation output root containing data/ and reports/.")
    args = parser.parse_args()

    output_root = Path(args.output_root)
    refresh_1y_reconciliation(output_root)
    refresh_5y_coverage(output_root)


if __name__ == "__main__":
    main()
