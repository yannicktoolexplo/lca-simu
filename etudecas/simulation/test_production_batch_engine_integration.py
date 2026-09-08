from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json"
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_multi_day_batch_crosses_day_zero_and_releases_once(tmp_path: Path) -> None:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    factory = next(node for node in graph["nodes"] if node.get("id") == "M-1810")
    process = next(
        process
        for process in factory.get("processes", [])
        if any(output.get("item_id") == "item:268091" for output in process.get("outputs", []))
    )
    process["capacity"]["max_rate"] = 5_000.0
    fixture = tmp_path / "capacity_limited_graph.json"
    fixture.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "run"

    result = subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--input",
            str(fixture),
            "--output-dir",
            str(output_dir),
            "--scenario-id",
            "scn:BASE",
            "--days",
            "3",
            "--warmup-days",
            "1",
            "--seed",
            "9102",
            "--output-profile",
            "compact",
            "--skip-map",
            "--skip-plots",
            "--use-bom-demand-signal-for-mrp",
            "--mrp-demand-signal-smoothing-days",
            "7",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    plan_rows = _read_rows(output_dir / "data" / "production_plan_events.csv")
    carry_in_rows = [
        row
        for row in plan_rows
        if row["node_id"] == "M-1810"
        and row["output_item_id"] == "item:268091"
        and row["day"] == "0"
        and row["is_day_zero_carry_in"] == "1"
    ]
    assert len(carry_in_rows) == 1
    carry_in = carry_in_rows[0]
    assert float(carry_in["batch_target_qty"]) == 14_400.0
    assert float(carry_in["wip_start_qty"]) == 5_000.0
    assert float(carry_in["batch_executed_today_qty"]) == 5_000.0
    assert float(carry_in["released_qty"]) == 0.0
    assert float(carry_in["wip_end_qty"]) == 10_000.0
    assert float(carry_in["process_tau_days"]) == 3.0
    assert carry_in["release_gate_mode"] == "execution_complete_tau_planning_only"
    assert not carry_in["released_lot_id"]

    completion_rows = [
        row
        for row in plan_rows
        if row["campaign_id"] == carry_in["campaign_id"] and row["day"] == "1"
    ]
    assert len(completion_rows) == 1
    completion = completion_rows[0]
    assert completion["event_type"] == "run_campaign_complete"
    assert float(completion["batch_executed_today_qty"]) == 4_400.0
    assert float(completion["released_qty"]) == 14_400.0
    assert float(completion["wip_end_qty"]) == 0.0
    assert completion["released_lot_id"]

    campaign_id = carry_in["campaign_id"]
    lot_rows = _read_rows(output_dir / "data" / "production_lot_events.csv")
    output_rows = [
        row
        for row in lot_rows
        if row["event_type"] == "production_output"
        and row["production_campaign_id"] == campaign_id
    ]
    assert len(output_rows) == 1
    assert output_rows[0]["day"] == "1"
    assert float(output_rows[0]["qty"]) == 14_400.0

    output_daily = _read_rows(output_dir / "data" / "production_output_products_daily.csv")
    target_daily = [
        row
        for row in output_daily
        if row["node_id"] == "M-1810" and row["item_id"] == "item:268091"
    ]
    day_zero = next(row for row in target_daily if row["day"] == "0")
    day_one = next(row for row in target_daily if row["day"] == "1")
    assert float(day_zero["executed_qty"]) == 5_000.0
    assert float(day_zero["released_qty"]) == 0.0
    assert float(day_zero["wip_end_qty"]) == 10_000.0
    assert float(day_one["executed_qty"]) == 4_400.0
    assert float(day_one["released_qty"]) == 14_400.0

    campaign_rows = _read_rows(output_dir / "data" / "production_campaigns.csv")
    campaign = next(row for row in campaign_rows if row["campaign_id"] == campaign_id)
    assert campaign["campaign_started_day"] == "-1"
    assert campaign["completed_day"] == "1"
    assert campaign["last_release_day"] == "1"
    assert campaign["status"] == "completed_after_delay"

    audit_issues = _read_rows(output_dir / "data" / "lot_path_audit_issues.csv")
    assert not [row for row in audit_issues if row.get("severity") == "error"]


if __name__ == "__main__":
    raise SystemExit("Run with pytest.")
