"""Rebuild a scenario cascade payload from compressed SDD outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    build_progress,
    build_sdd_risk_cascade_payload,
    read_csv_gzip,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario_dir", type=Path)
    parser.add_argument("--max-cascades", type=int, default=260)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenario_dir = args.scenario_dir.resolve(strict=False)
    data_dir = scenario_dir / "data"
    build_progress(f"Lecture du scenario {scenario_dir.name}")
    sdd_results = {
        "sdd_event_ledger": read_csv_gzip(data_dir / "sdd_event_ledger.csv.gz"),
        "sdd_node_state": read_csv_gzip(data_dir / "sdd_node_state.csv.gz"),
        "sdd_lane_state": read_csv_gzip(data_dir / "sdd_lane_state.csv.gz"),
    }
    sdd_brightway = {
        "inventory_delta": read_csv_gzip(
            data_dir / "sdd_brightway_inventory_delta.csv.gz"
        ),
        "exchange_delta": read_csv_gzip(
            data_dir / "sdd_brightway_exchange_delta.csv.gz"
        ),
    }
    environmental_events = read_csv_gzip(
        data_dir / "supplier_risk_event_seed.csv.gz"
    )
    build_progress("Construction et reconciliation des cascades")
    payload = build_sdd_risk_cascade_payload(
        sdd_results,
        sdd_brightway,
        environmental_event_rows=environmental_events,
        max_cascades=max(1, args.max_cascades),
    )
    write_json(scenario_dir / "risk_cascades.json", payload)
    manifest_path = scenario_dir / "scenario_manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {}
    )
    manifest["cascade_algorithm_version"] = "root_normalized_v2"
    manifest["cascade_stats"] = payload.get("stats", {})
    write_json(manifest_path, manifest)
    build_progress(
        "Cascades terminees: "
        f"{payload.get('stats', {}).get('detailed_cascade_count', 0)} detaillees"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
