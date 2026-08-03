from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

from etudecas.simulation.engine.run_first_simulation import (
    _paired_lead_time_identity,
    _paired_lead_time_seed,
    _supplier_controlled_need_qty,
)


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


def _run_engine(
    output_dir: Path,
    schedule: Path | None = None,
    *,
    common_random_numbers: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ENGINE),
        "--input",
        str(GRAPH),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        "2",
        "--warmup-days",
        "0",
        "--seed",
        "9102",
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
    ]
    if schedule is not None:
        command.extend(
            [
                "--control-schedule-csv",
                str(schedule),
            ]
        )
    if common_random_numbers:
        command.append("--common-random-numbers")
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_common_random_number_key_includes_invocation_ordinal() -> None:
    lane = {
        "edge_id": "edge:1",
        "src": "supplier:A",
        "dst": "factory:A",
        "item_id": "item:A",
    }
    identity = _paired_lead_time_identity(
        seed=42,
        measured_day=3,
        lane=lane,
        source_mode="lane_release",
    )

    assert _paired_lead_time_seed(identity, 0) == _paired_lead_time_seed(
        identity,
        0,
    )
    assert _paired_lead_time_seed(identity, 0) != _paired_lead_time_seed(
        identity,
        1,
    )


def test_supplier_targeted_order_multiplier_controls_aggregate_need() -> None:
    assert _supplier_controlled_need_qty(
        100.0,
        {1: 1.0},
        {1: 2.0},
    ) == 200.0
    assert _supplier_controlled_need_qty(
        100.0,
        {1: 3.0, 2: 1.0},
        {1: 2.0, 2: 0.5},
    ) == 162.5


def test_engine_without_schedule_is_explicitly_neutral(tmp_path: Path) -> None:
    output_dir = tmp_path / "neutral"
    result = _run_engine(output_dir)
    assert result.returncode == 0, result.stderr or result.stdout

    summary = json.loads(
        (output_dir / "summaries" / "first_simulation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    control = summary["policy"]["control_schedule"]
    assert control["enabled"] is False
    assert control["schedule_rows"] == 0
    assert control["action_ledger_rows"] == 0

    with (output_dir / "data" / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        assert list(csv.DictReader(handle)) == []

    with (output_dir / "data" / "mrp_trace_daily.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        trace_rows = list(csv.DictReader(handle))
    assert trace_rows
    assert {row["control_order_multiplier"] for row in trace_rows} == {"1.0"}
    assert {row["control_safety_stock_multiplier"] for row in trace_rows} == {
        "1.0"
    }

    neutral_schedule = tmp_path / "strictly_neutral.csv"
    neutral_schedule.write_text(
        "\n".join(
            [
                (
                    "day,policy,node_id,supplier_id,item_id,dst_node_id,"
                    "order_multiplier,safety_stock_multiplier,"
                    "production_target_multiplier,capacity_multiplier,"
                    "external_procurement_multiplier,expedite_level,"
                    "lead_time_adjustment_days,priority_weight"
                ),
                "0,mrp_reference,,,,,1,1,1,1,1,0,0,1",
                "1,mrp_reference,,,,,1,1,1,1,1,0,0,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    scheduled_output = tmp_path / "strictly_neutral_output"
    scheduled_result = _run_engine(scheduled_output, neutral_schedule)
    assert scheduled_result.returncode == 0, (
        scheduled_result.stderr or scheduled_result.stdout
    )
    # Schedule parsing and audit metadata may differ, but a strictly neutral
    # schedule must not alter any physical or economic result.
    for relative_path in (
        "data/first_simulation_daily.csv",
        "data/mrp_orders_daily.csv",
        "data/mrp_trace_daily.csv",
        "data/production_dc_stocks_daily.csv",
        "data/production_input_stocks_daily.csv",
        "data/production_output_products_daily.csv",
        "data/production_constraint_daily.csv",
        "data/production_supplier_shipments_daily.csv",
        "data/production_supplier_stocks_daily.csv",
    ):
        assert (output_dir / relative_path).read_bytes() == (
            scheduled_output / relative_path
        ).read_bytes(), relative_path


def test_engine_applies_daily_schedule_and_writes_action_ledger(
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "control.csv"
    schedule.write_text(
        "\n".join(
            [
                (
                    "day,policy,node_id,supplier_id,item_id,dst_node_id,"
                    "order_multiplier,safety_stock_multiplier,"
                    "production_target_multiplier,capacity_multiplier,"
                    "external_procurement_multiplier,expedite_level,"
                    "lead_time_adjustment_days,priority_weight"
                ),
                "0,balanced_robust,,,,,1.2,1.3,1.1,1.1,1.5,0.5,-1,1.2",
                "1,balanced_robust,,,,,1.2,1.3,1.1,1.1,1.5,0.5,-1,1.2",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "controlled"
    result = _run_engine(
        output_dir,
        schedule,
        common_random_numbers=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    summary = json.loads(
        (output_dir / "summaries" / "first_simulation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    control = summary["policy"]["control_schedule"]
    assert control["enabled"] is True
    assert control["schedule_rows"] == 2
    assert control["matched_schedule_rows"] == 2
    assert control["unmatched_schedule_rows"] == 0
    assert control["scheduled_actions"] == 16
    assert 0 < control["resolved_actions"] < control["scheduled_actions"]
    assert (
        control["resolved_actions"] + control["unresolved_actions"]
        == control["scheduled_actions"]
    )
    assert summary["policy"]["common_random_numbers"] is True

    with (output_dir / "data" / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        ledger = list(csv.DictReader(handle))
    assert ledger
    assert {row["day"] for row in ledger} == {"0", "1"}
    assert {row["action"] for row in ledger} == {
        "order_multiplier",
        "safety_stock_multiplier",
        "production_target_multiplier",
        "capacity_multiplier",
        "external_procurement_multiplier",
        "expedite_level",
        "lead_time_adjustment_days",
        "priority_weight",
    }
    assert all(row["requested"] and row["effective"] for row in ledger)
    assert any(
        row["action_stage"] == "mrp_order_control_before_constraints"
        for row in ledger
    )
    assert any(row["action_stage"] == "production_execution" for row in ledger)
    stage_actions = {
        stage: {
            row["action"]
            for row in ledger
            if row["action_stage"] == stage
        }
        for stage in {
            row["action_stage"]
            for row in ledger
        }
    }
    assert stage_actions["mrp_order_control_before_constraints"] == {
        "order_multiplier",
        "safety_stock_multiplier",
    }
    assert stage_actions["production_execution"] == {
        "production_target_multiplier",
        "capacity_multiplier",
    }
    assert stage_actions["supplier_capacity"] == {"capacity_multiplier"}
    assert stage_actions["external_procurement_reactive"] == {
        "external_procurement_multiplier",
        "expedite_level",
        "lead_time_adjustment_days",
    }
    executed_expedite = [
        row
        for row in ledger
        if row["action"] == "expedite_level"
        and row["status"] == "applied"
    ]
    assert executed_expedite
    assert all(
        float(row["executed_control_volume_qty"]) > 0.0
        for row in executed_expedite
    )
    unresolved_expedite = [
        row
        for row in ledger
        if row["action"] == "expedite_level"
        and row["status"] == "scheduled_not_resolved"
    ]
    assert unresolved_expedite
    assert all(
        row["action_stage"] == "schedule_audit"
        and not row["executed_control_volume_qty"]
        for row in unresolved_expedite
    )
    lane_capacity_rows = [
        row
        for row in ledger
        if row["action"] == "capacity_multiplier"
        and row["action_stage"] == "supplier_lane_execution"
    ]
    assert lane_capacity_rows
    assert all(
        row["capacity_controlled_remaining_qty"]
        for row in lane_capacity_rows
    )

    applied_order_rows = [
        row
        for row in ledger
        if row["action"] == "order_multiplier"
        and row["action_stage"] == "mrp_order_control_before_constraints"
        and row["status"] == "applied"
    ]
    assert applied_order_rows
    quantity_chain = (
        "q_mrp_base_qty",
        "q_after_safety_stock_control_qty",
        "q_after_control_qty",
        "q_after_supplier_control_qty",
        "q_after_constraints_qty",
        "q_after_lotification_qty",
        "q_executable_qty",
    )
    assert all(
        all(row[column] for column in quantity_chain)
        for row in applied_order_rows
    )
    assert all(
        abs(
            float(row["q_after_control_qty"])
            - 1.2 * float(row["q_after_safety_stock_control_qty"])
        )
        < 1e-5
        for row in applied_order_rows
    )
    assert all(
        float(row["q_after_supplier_control_qty"])
        == float(row["q_after_control_qty"])
        for row in applied_order_rows
    )
    assert any(
        float(row["q_after_lotification_qty"])
        > float(row["q_after_constraints_qty"])
        for row in applied_order_rows
    )

    with (output_dir / "data" / "mrp_trace_daily.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        trace_rows = list(csv.DictReader(handle))
    assert trace_rows
    assert {row["control_order_multiplier"] for row in trace_rows} == {"1.2"}
    assert {row["control_safety_stock_multiplier"] for row in trace_rows} == {
        "1.3"
    }


def test_post_constraint_quantity_survives_zero_lotification_in_pair_ledger(
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "sub_lot_control.csv"
    schedule.write_text(
        "\n".join(
            [
                (
                    "day,policy,node_id,supplier_id,item_id,dst_node_id,"
                    "order_multiplier,safety_stock_multiplier,"
                    "production_target_multiplier,capacity_multiplier,"
                    "external_procurement_multiplier,expedite_level,"
                    "lead_time_adjustment_days,priority_weight"
                ),
                "0,reactive_buffer,,,,,1.22,1.55,1.1,1.1,1.59,0.32,-1,1",
                "1,reactive_buffer,,,,,1.22,1.55,1.1,1.1,1.59,0.32,-1,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "sub_lot_control"
    result = _run_engine(output_dir, schedule)
    assert result.returncode == 0, result.stderr or result.stdout

    with (output_dir / "data" / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        ledger = list(csv.DictReader(handle))

    zero_lot_constraint_by_pair: dict[tuple[str, str, str], float] = {}
    for row in ledger:
        if (
            row["action"] != "capacity_multiplier"
            or row["action_stage"] != "supplier_lane_execution"
            or float(row["q_after_constraints_qty"] or 0.0) <= 0.0
            or float(row["q_after_lotification_qty"] or 0.0) != 0.0
        ):
            continue
        key = (
            row["day"],
            row["resolved_node_id"],
            row["resolved_item_id"],
        )
        zero_lot_constraint_by_pair[key] = (
            zero_lot_constraint_by_pair.get(key, 0.0)
            + float(row["q_after_constraints_qty"])
        )
    assert zero_lot_constraint_by_pair

    order_by_pair = {
        (
            row["day"],
            row["resolved_node_id"],
            row["resolved_item_id"],
        ): row
        for row in ledger
        if row["action"] == "order_multiplier"
        and row["action_stage"] == "mrp_order_control_before_constraints"
    }
    zero_lot_pairs = [
        (constrained_qty, order_by_pair[key])
        for key, constrained_qty in zero_lot_constraint_by_pair.items()
        if key in order_by_pair
        and float(
            order_by_pair[key]["q_after_lotification_qty"] or 0.0
        )
        == 0.0
    ]
    assert zero_lot_pairs
    assert all(
        float(order_row["q_after_constraints_qty"])
        >= constrained_qty - 1e-5
        for constrained_qty, order_row in zero_lot_pairs
    )


def test_zero_global_order_control_is_resolved_without_executable_order(
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "zero_order.csv"
    schedule.write_text(
        "\n".join(
            [
                "day,policy,order_multiplier",
                "0,stop_orders,0",
                "1,stop_orders,0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "zero_order"
    result = _run_engine(output_dir, schedule)
    assert result.returncode == 0, result.stderr or result.stdout

    summary = json.loads(
        (output_dir / "summaries" / "first_simulation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    control = summary["policy"]["control_schedule"]
    assert control["scheduled_actions"] == 2
    assert control["resolved_actions"] == 2
    assert control["unresolved_actions"] == 0

    with (output_dir / "data" / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        ledger = list(csv.DictReader(handle))
    order_rows = [
        row for row in ledger if row["action"] == "order_multiplier"
    ]
    assert order_rows
    assert all(
        row["action_stage"] == "mrp_order_control_before_constraints"
        and row["status"] == "no_executable_order"
        for row in order_rows
    )
    assert not any(
        row["status"] == "scheduled_not_resolved"
        for row in order_rows
    )
    assert all(
        float(row["q_after_control_qty"]) == 0.0
        and float(row["q_after_supplier_control_qty"]) == 0.0
        and float(row["q_after_constraints_qty"]) == 0.0
        and float(row["q_after_lotification_qty"]) == 0.0
        and float(row["q_executable_qty"]) == 0.0
        for row in order_rows
    )
