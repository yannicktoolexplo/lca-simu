#!/usr/bin/env python3
"""Calibrate the baseline simulation-ready graph to a target annual service level."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis_batch_common import apply_scales, load_json, write_json


TARGET_FACTORS = {
    # Rebalanced baseline:
    # enough degradation to settle near 90% annual service,
    # but without over-protecting suppliers so sensitivity remains visible.
    "supplier_reliability_scale": 0.96,
    "supplier_stock_scale": 0.95,
    "external_procurement_daily_cap_days_scale": 0.8,
    "external_procurement_lead_days_scale": 1.25,
}

TARGET_CAPACITY_NODES: dict[str, float] = {}
TARGET_SUPPLIER_NODE_SCALE: dict[str, float] = {}
TARGET_SUPPLIER_CAPACITY_SCALE: dict[str, float] = {}
TARGET_EDGE_RELIABILITY_SCALE: dict[str, float] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate baseline to ~90% annual service level.")
    parser.add_argument(
        "--source",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready_pre_target90.json",
        help="Source simulation-ready graph JSON used as clean pre-calibration baseline.",
    )
    parser.add_argument(
        "--output",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Simulation-ready graph JSON to overwrite.",
    )
    parser.add_argument(
        "--backup",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready_pre_supplier_sensitivity_rebalance.json",
        help="Backup path for the previous baseline JSON.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id to calibrate.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    output_path = Path(args.output)
    backup_path = Path(args.backup)

    base_data = load_json(source_path)
    if not backup_path.exists():
        backup_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")

    calibrated = apply_scales(
        base_data,
        args.scenario_id,
        TARGET_FACTORS,
        capacity_node_scale=TARGET_CAPACITY_NODES,
        supplier_node_scale=TARGET_SUPPLIER_NODE_SCALE,
        supplier_capacity_node_scale=TARGET_SUPPLIER_CAPACITY_SCALE,
        edge_src_reliability_scale=TARGET_EDGE_RELIABILITY_SCALE,
    )

    meta = calibrated.get("meta") or {}
    calib = meta.get("baseline_calibration") or {}
    calib.update(
        {
            "target": "annual_fill_rate_around_0.90",
            "applied_on_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "factors": TARGET_FACTORS,
            "capacity_node_scale": TARGET_CAPACITY_NODES,
            "supplier_node_scale": TARGET_SUPPLIER_NODE_SCALE,
            "supplier_capacity_node_scale": TARGET_SUPPLIER_CAPACITY_SCALE,
            "edge_src_reliability_scale": TARGET_EDGE_RELIABILITY_SCALE,
            "backup_file": str(backup_path),
            "source_file": str(source_path),
        }
    )
    meta["baseline_calibration"] = calib
    calibrated["meta"] = meta
    write_json(output_path, calibrated)
    print(json.dumps(meta["baseline_calibration"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
