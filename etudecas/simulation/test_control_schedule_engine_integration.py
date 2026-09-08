from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

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
FEEDBACK_CONFIG = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_closed_loop_config.json"
)
V3_FEEDBACK_CONFIG = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_closed_loop_v3_continuous_config.json"
)


def _run_engine(
    output_dir: Path,
    schedule: Path | None = None,
    *,
    graph: Path = GRAPH,
    days: int = 2,
    control_probe: Path | None = None,
    control_policy: Path | None = None,
    control_policy_v2: Path | None = None,
    control_policy_v3: Path | None = None,
    supplier_risk_events_csv: Path | None = None,
    prime_controller_during_warmup: bool = False,
    warmup_boundary_audit: bool = False,
    common_random_numbers: bool = False,
    stochastic_lead_times: bool | None = None,
    demand_signal_smoothing_days: int = 1,
    warmup_days: int = 0,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ENGINE),
        "--input",
        str(graph),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(days),
        "--warmup-days",
        str(warmup_days),
        "--seed",
        "9102",
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--use-bom-demand-signal-for-mrp",
        "--mrp-demand-signal-smoothing-days",
        str(demand_signal_smoothing_days),
    ]
    if schedule is not None:
        command.extend(
            [
                "--control-schedule-csv",
                str(schedule),
            ]
        )
    if control_probe is not None:
        command.extend(
            [
                "--control-probe-schedule-csv",
                str(control_probe),
            ]
        )
    if control_policy is not None:
        command.extend(
            [
                "--control-policy-json",
                str(control_policy),
            ]
        )
    if control_policy_v2 is not None:
        command.extend(
            [
                "--control-policy-v2-json",
                str(control_policy_v2),
            ]
        )
    if control_policy_v3 is not None:
        command.extend(
            [
                "--control-policy-v3-json",
                str(control_policy_v3),
            ]
        )
    if supplier_risk_events_csv is not None:
        command.extend(
            [
                "--supplier-risk-events-csv",
                str(supplier_risk_events_csv),
            ]
        )
    if prime_controller_during_warmup:
        command.append("--controller-prime-during-warmup")
    if warmup_boundary_audit:
        command.append("--warmup-boundary-audit")
    if common_random_numbers:
        command.append("--common-random-numbers")
    if stochastic_lead_times is not None:
        command.append(
            "--stochastic-lead-times"
            if stochastic_lead_times
            else "--no-stochastic-lead-times"
        )
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _write_feedback_policy(
    tmp_path: Path,
    *,
    force_active: bool,
) -> Path:
    policy = json.loads(FEEDBACK_CONFIG.read_text(encoding="utf-8"))
    policy["review_period_days"] = 1
    policy["confirmation_days"] = 1
    policy["minimum_dwell_days"] = 0
    if force_active:
        policy["playbooks"]["forced_active"] = {
            "commands": [
                {
                    "scope": {},
                    "actions": {"order_multiplier": 1.2},
                }
            ]
        }
        policy["regime_policy"] = {
            regime: "forced_active"
            for regime in policy["regime_policy"]
        }
        policy["slew_limits"]["order_multiplier"] = 1.0
    else:
        policy["regime_policy"] = {
            regime: "mrp_reference"
            for regime in policy["regime_policy"]
        }
    path = tmp_path / (
        "forced_active_feedback.json"
        if force_active
        else "neutral_feedback.json"
    )
    path.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _write_v2_feedback_policy(tmp_path: Path) -> Path:
    policy = json.loads(FEEDBACK_CONFIG.read_text(encoding="utf-8"))
    policy["schema_version"] = "scan.canonical_state_feedback.v2"
    policy["name"] = "engine_integration_forced_active_v2"
    policy["review_period_days"] = 1
    policy["confirmation_days"] = 1
    policy["minimum_dwell_days"] = 0
    policy["playbooks"]["forced_active"] = {
        "commands": [
            {
                "scope": {},
                "actions": {"order_multiplier": 1.2},
            }
        ]
    }
    policy["regime_policy"] = {
        regime: "forced_active"
        for regime in policy["regime_policy"]
    }
    policy["slew_limits"]["order_multiplier"] = 1.0
    always_open = {
        "require_any": [
            {"signal": "backlog_days", "operator": "ge", "threshold": 0.0}
        ]
    }
    policy["gates"] = {
        "service_recovery_gate": always_open,
        "exceptional_cost_gate": always_open,
    }
    policy["action_gate_map"] = {
        "order_multiplier": {
            "gate": "service_recovery_gate",
            "direction": "above_neutral",
        },
        "safety_stock_multiplier": {
            "gate": "service_recovery_gate",
            "direction": "above_neutral",
        },
        "production_target_multiplier": {
            "gate": "service_recovery_gate",
            "direction": "above_neutral",
        },
        "external_procurement_multiplier": {
            "gate": "exceptional_cost_gate",
            "direction": "above_neutral",
        },
        "expedite_level": {
            "gate": "exceptional_cost_gate",
            "direction": "above_neutral",
        },
    }
    path = tmp_path / "forced_active_feedback_v2.json"
    path.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _write_v3_feedback_policy(tmp_path: Path) -> Path:
    policy = json.loads(V3_FEEDBACK_CONFIG.read_text(encoding="utf-8"))
    policy["name"] = "engine_integration_continuous_supplier_relief_v3"
    policy["review_period_days"] = 1
    policy["confirmation_days"] = 1
    policy["minimum_dwell_days"] = 0
    policy["thresholds"].update(
        {
            "supplier_disruption": 0.01,
            "supplier_stress": 0.01,
            "crisis_backlog_days": 365.0,
        }
    )
    policy["dynamics"].update(
        {
            "stress_memory": 0.0,
            "nervousness_gain": 0.0,
            "pressure_gain": 0.0,
            "disruption_gain": 1.0,
        }
    )
    policy["continuous_relief"].update(
        {
            "stress_start": 0.10,
            "stress_span": 0.40,
            "backlog_guard_days": 365.0,
            "service_guard_level": 0.0,
            "finished_cover_guard_days": 0.0,
            "material_cover_guard_days": 0.0,
        }
    )
    path = tmp_path / "continuous_supplier_relief_v3.json"
    path.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _write_v3_supplier_stress_event(tmp_path: Path) -> Path:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    supplier_id = next(
        str(node["id"])
        for node in graph["nodes"]
        if str(node.get("type") or "") == "supplier_dc"
    )
    path = tmp_path / "continuous_v3_supplier_stress.csv"
    path.write_text(
        "event_id,risk_type,supplier_id,start_day,end_day,multiplier\n"
        f"v3_supplier_stress,capacity,{supplier_id},-2,1,0.2\n",
        encoding="utf-8",
    )
    return path


def _write_control_probe(
    tmp_path: Path,
    *,
    name: str,
    order_multiplier: float,
) -> Path:
    path = tmp_path / name
    path.write_text(
        "day,policy,order_multiplier\n"
        f"0,closed_loop_frequency_probe,{order_multiplier}\n"
        f"1,closed_loop_frequency_probe,{order_multiplier}\n",
        encoding="utf-8",
    )
    return path


def _write_quality_hold_lane_graph(tmp_path: Path) -> Path:
    """Create deterministic stock/need for the 120-day 021081 supplier lane."""

    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    supplier_id = "SDC-VD0949099A"
    destination_id = "SDC-1450"
    item_id = "item:021081"
    for node in graph["nodes"]:
        node_id = str(node.get("id") or "")
        for state in (node.get("inventory") or {}).get("states", []):
            if str(state.get("item_id") or "") != item_id:
                continue
            if node_id == supplier_id:
                state["initial"] = 2_000_000.0
            elif node_id == destination_id:
                state["initial"] = 0.0
    scenario = next(
        scenario
        for scenario in graph["scenarios"]
        if scenario["id"] == "scn:BASE"
    )
    initialization = scenario["initialization_policy"]
    initialization["state_scale"] = 1.0
    initialization["seed_in_transit"] = False
    initialization["seed_estimated_source_pipeline"] = False
    path = tmp_path / "quality_hold_lane_graph.json"
    path.write_text(
        json.dumps(graph, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _write_quality_hold_event(tmp_path: Path) -> Path:
    path = tmp_path / "quality_hold_45_days.csv"
    path.write_text(
        (
            "event_id,risk_type,supplier_id,item_id,dst_node_id,edge_id,"
            "start_day,end_day,multiplier\n"
            "quality_hold_45,quality_delay,SDC-VD0949099A,item:021081,"
            "SDC-1450,edge:SDC-VD0949099A_TO_SDC-1450_021081,0,0,45\n"
        ),
        encoding="utf-8",
    )
    return path


def _write_transport_control_for_quality_hold(tmp_path: Path) -> Path:
    path = tmp_path / "quality_hold_transport_control.csv"
    path.write_text(
        (
            "day,policy,node_id,supplier_id,item_id,dst_node_id,"
            "expedite_level,lead_time_adjustment_days\n"
            "0,quality_hold_transport_only,SDC-1450,SDC-VD0949099A,"
            "item:021081,SDC-1450,0.2,-7\n"
        ),
        encoding="utf-8",
    )
    return path


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


def test_transport_control_does_not_shorten_quality_release_hold(
    tmp_path: Path,
) -> None:
    graph = _write_quality_hold_lane_graph(tmp_path)
    risk_events = _write_quality_hold_event(tmp_path)
    schedule = _write_transport_control_for_quality_hold(tmp_path)
    neutral_dir = tmp_path / "quality_hold_neutral"
    controlled_dir = tmp_path / "quality_hold_controlled"

    neutral = _run_engine(
        neutral_dir,
        graph=graph,
        days=1,
        supplier_risk_events_csv=risk_events,
        stochastic_lead_times=False,
    )
    controlled = _run_engine(
        controlled_dir,
        schedule,
        graph=graph,
        days=1,
        supplier_risk_events_csv=risk_events,
        stochastic_lead_times=False,
    )

    assert neutral.returncode == 0, neutral.stderr or neutral.stdout
    assert controlled.returncode == 0, controlled.stderr or controlled.stdout

    edge_id = "edge:SDC-VD0949099A_TO_SDC-1450_021081"

    def lane_shipments(output_dir: Path) -> list[dict[str, str]]:
        with (
            output_dir / "data" / "production_supplier_shipments_daily.csv"
        ).open(encoding="utf-8", newline="") as handle:
            return [
                row
                for row in csv.DictReader(handle)
                if row["edge_id"] == edge_id and int(row["day"]) == 0
            ]

    neutral_shipments = lane_shipments(neutral_dir)
    controlled_shipments = lane_shipments(controlled_dir)
    assert neutral_shipments
    assert controlled_shipments
    assert {int(row["lead_days"]) for row in neutral_shipments} == {165}
    # Transport: 120 - floor(0.2 * (120 - 1)) - 7 = 90 days.
    # The independent quality-release hold then remains exactly 45 days.
    assert {int(row["lead_days"]) for row in controlled_shipments} == {135}

    with (
        controlled_dir / "data" / "canonical_action_ledger.csv"
    ).open(encoding="utf-8", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    executed_delay_controls = [
        row
        for row in ledger
        if row.get("edge_id") == edge_id
        and row["action_stage"] == "supplier_lane_execution"
        and row["action"] in {"expedite_level", "lead_time_adjustment_days"}
        and row["status"] == "applied"
    ]
    assert {row["action"] for row in executed_delay_controls} == {
        "expedite_level",
        "lead_time_adjustment_days",
    }
    assert all(
        float(row["executed_control_volume_qty"]) > 0.0
        and int(float(row["lead_reference_days"])) == 120
        and int(float(row["lead_effective_days"])) == 135
        for row in executed_delay_controls
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


def test_neutral_state_feedback_is_physically_identical_and_audited(
    tmp_path: Path,
) -> None:
    reference_output = tmp_path / "feedback_neutral_reference"
    reference = _run_engine(
        reference_output,
        common_random_numbers=True,
    )
    assert reference.returncode == 0, reference.stderr or reference.stdout

    policy_path = _write_feedback_policy(tmp_path, force_active=False)
    feedback_output = tmp_path / "feedback_neutral"
    feedback = _run_engine(
        feedback_output,
        control_policy=policy_path,
        common_random_numbers=True,
    )
    assert feedback.returncode == 0, feedback.stderr or feedback.stdout

    physical_outputs = (
        "data/first_simulation_daily.csv",
        "data/mrp_orders_daily.csv",
        "data/mrp_trace_daily.csv",
        "data/production_dc_stocks_daily.csv",
        "data/production_input_stocks_daily.csv",
        "data/production_output_products_daily.csv",
        "data/production_constraint_daily.csv",
        "data/production_supplier_shipments_daily.csv",
        "data/production_supplier_stocks_daily.csv",
    )
    for relative_path in physical_outputs:
        assert (reference_output / relative_path).read_bytes() == (
            feedback_output / relative_path
        ).read_bytes(), relative_path

    summary = json.loads(
        (
            feedback_output
            / "summaries"
            / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    provider = summary["policy"]["control_provider"]
    assert summary["policy"]["control_schedule"]["enabled"] is False
    assert provider["enabled"] is True
    # The provider ran causally, but a neutral policy must not claim that a
    # physical feedback action was applied.
    assert provider["closed_loop_claimed"] is False
    assert provider["provider_causal_contract_satisfied"] is True
    assert provider["physical_action_applied"] is False
    assert provider["causal_lag_days"] == 1
    assert provider["observation_count"] == 2
    assert provider["decision_count"] == 2
    assert provider["active_command_row_count"] == 0
    assert provider["action_ledger_rows"] == 0

    data_dir = feedback_output / "data"
    with (data_dir / "canonical_closed_loop_observations.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        observations = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_decisions.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        decisions = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_commands.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        commands = list(csv.DictReader(handle))
    with (data_dir / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        action_ledger = list(csv.DictReader(handle))

    assert [row["day"] for row in observations] == ["0", "1"]
    assert all(row["observation_valid"] == "1" for row in observations)
    assert [row["decision_day"] for row in decisions] == ["0", "1"]
    assert all(row["causal_lag_days"] == "1" for row in decisions)
    assert decisions[0]["observation_hash"] == observations[0]["observation_hash"]
    assert len(commands) == 1
    assert commands[0]["decision_day"] == "0"
    assert commands[0]["effective_day"] == "1"
    assert commands[0]["active"] == "0"
    assert json.loads(commands[0]["effective_json"]) == {}
    assert action_ledger == []


def test_forced_state_feedback_is_causal_and_applies_only_on_next_day(
    tmp_path: Path,
) -> None:
    policy_path = _write_feedback_policy(tmp_path, force_active=True)
    output_dir = tmp_path / "feedback_forced_active"
    result = _run_engine(
        output_dir,
        control_policy=policy_path,
        common_random_numbers=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    summary = json.loads(
        (
            output_dir / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    provider = summary["policy"]["control_provider"]
    assert summary["policy"]["control_schedule"]["enabled"] is False
    assert provider["enabled"] is True
    assert provider["closed_loop_claimed"] is True
    assert provider["future_realization_access"] is False
    assert provider["observation_causal_contract_satisfied"] is True
    assert provider["controller_observation_max_future_day_offset"] == 0
    assert provider["demand_realization_window_days_effective"] == 1
    assert provider["closed_loop_claim_reasons"] == []
    assert provider["causal_lag_days"] == 1
    assert provider["observation_count"] == 2
    assert provider["decision_count"] == 2
    assert provider["generated_command_count"] == 1
    assert provider["active_command_row_count"] == 1
    assert provider["matched_active_command_rows"] == 1

    data_dir = output_dir / "data"
    with (data_dir / "canonical_closed_loop_observations.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        observations = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_decisions.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        decisions = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_commands.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        commands = list(csv.DictReader(handle))
    with (data_dir / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        action_ledger = list(csv.DictReader(handle))

    assert [row["day"] for row in observations] == ["0", "1"]
    assert [row["decision_day"] for row in decisions] == ["0", "1"]
    day_zero_decision = decisions[0]
    assert day_zero_decision["effective_day"] == "1"
    assert day_zero_decision["causal_lag_days"] == "1"
    assert day_zero_decision["observation_hash"] == observations[0]["observation_hash"]
    assert day_zero_decision["selected_policy"] == "forced_active"
    assert day_zero_decision["generated_command_count"] == "1"
    assert day_zero_decision["active_command_row_count"] == "1"

    assert len(commands) == 1
    command = commands[0]
    assert command["decision_day"] == "0"
    assert command["effective_day"] == "1"
    assert command["causal_lag_days"] == "1"
    assert command["policy"] == "forced_active"
    assert command["active"] == "1"
    assert json.loads(command["requested_json"]) == {
        "order_multiplier": 1.2,
    }
    assert json.loads(command["effective_json"]) == {
        "order_multiplier": 1.2,
    }

    assert action_ledger
    assert "0" not in {row["day"] for row in action_ledger}
    assert {row["day"] for row in action_ledger} == {"1"}
    assert {row["action"] for row in action_ledger} == {
        "order_multiplier",
    }
    assert all(
        row["control_source_kind"] == "state_feedback_generated_online"
        and row["decision_day"] == "0"
        and row["effective_day"] == "1"
        and row["causal_lag_days"] == "1"
        for row in action_ledger
    )


def test_forward_smoothed_realized_demand_disables_strict_closed_loop_claim(
    tmp_path: Path,
) -> None:
    policy_path = _write_feedback_policy(tmp_path, force_active=True)
    output_dir = tmp_path / "feedback_noncausal_demand_window"

    result = _run_engine(
        output_dir,
        control_policy=policy_path,
        common_random_numbers=True,
        demand_signal_smoothing_days=7,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    summary = json.loads(
        (
            output_dir / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    provider = summary["policy"]["control_provider"]
    assert provider["provider_causal_contract_satisfied"] is True
    assert provider["physical_action_applied"] is True
    assert provider["closed_loop_claimed"] is False
    assert provider["direct_future_realization_access"] is False
    assert provider["future_realization_access"] is True
    assert provider["observation_causal_contract_satisfied"] is False
    assert provider["controller_observation_max_future_day_offset"] == 6
    assert provider["demand_realization_window_days_effective"] == 7
    assert provider["closed_loop_claim_reasons"] == [
        "observation_causal_contract_satisfied"
    ]


def test_unprimed_physical_warmup_disables_strict_closed_loop_claim(
    tmp_path: Path,
) -> None:
    policy_path = _write_feedback_policy(tmp_path, force_active=True)
    output_dir = tmp_path / "feedback_unprimed_warmup"

    result = _run_engine(
        output_dir,
        control_policy=policy_path,
        common_random_numbers=True,
        warmup_days=2,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    summary = json.loads(
        (
            output_dir / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    provider = summary["policy"]["control_provider"]
    assert provider["provider_causal_contract_satisfied"] is True
    assert provider["physical_action_applied"] is True
    assert provider["physical_warmup_days"] == 2
    assert provider["controller_dynamic_warmup_days"] == 0
    assert provider["controller_warmup_matches_physical_warmup"] is False
    assert provider["closed_loop_claimed"] is False
    assert provider["closed_loop_claim_reasons"] == [
        "controller_warmup_matches_physical_warmup"
    ]


def test_v2_primes_during_warmup_without_actions_and_matches_pair_boundary(
    tmp_path: Path,
) -> None:
    policy_path = _write_v2_feedback_policy(tmp_path)
    reference_output = tmp_path / "v2_warmup_reference"
    reference = _run_engine(
        reference_output,
        common_random_numbers=True,
        warmup_days=2,
        warmup_boundary_audit=True,
    )
    assert reference.returncode == 0, reference.stderr or reference.stdout

    feedback_output = tmp_path / "v2_warmup_feedback"
    feedback = _run_engine(
        feedback_output,
        control_policy_v2=policy_path,
        prime_controller_during_warmup=True,
        warmup_boundary_audit=True,
        common_random_numbers=True,
        warmup_days=2,
    )
    assert feedback.returncode == 0, feedback.stderr or feedback.stdout

    reference_summary = json.loads(
        (
            reference_output / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    feedback_summary = json.loads(
        (
            feedback_output / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    reference_boundary = reference_summary["policy"]["warmup_boundary_audit"]
    feedback_boundary = feedback_summary["policy"]["warmup_boundary_audit"]
    assert reference_boundary["restart_checkpoint_available"] is False
    assert reference_boundary["method"] == "deterministic_paired_burn_in_replay"
    assert reference_boundary["core_state_sha256"] == feedback_boundary[
        "core_state_sha256"
    ]
    assert reference_boundary["component_sha256"] == feedback_boundary[
        "component_sha256"
    ]

    provider = feedback_summary["policy"]["control_provider"]
    assert provider["schema_version"] == "scan.canonical_state_feedback.v2"
    assert provider["physical_warmup_days"] == 2
    assert provider["controller_dynamic_warmup_days"] == 2
    assert provider["controller_warmup_matches_physical_warmup"] is True
    assert provider["warmup_control_action_count"] == 0
    assert provider["closed_loop_claimed"] is True
    assert provider["closed_loop_claim_reasons"] == []

    data_dir = feedback_output / "data"
    with (data_dir / "canonical_controller_priming.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        priming = list(csv.DictReader(handle))
    assert [row["day"] for row in priming] == ["-2", "-1"]
    assert {row["generated_command_count"] for row in priming} == {"0"}
    assert {row["active_command_row_count"] for row in priming} == {"0"}

    with (data_dir / "canonical_closed_loop_observations.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        observations = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_commands.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        commands = list(csv.DictReader(handle))
    with (data_dir / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        action_ledger = list(csv.DictReader(handle))
    assert [row["day"] for row in observations] == ["0", "1"]
    assert commands
    assert min(int(row["effective_day"]) for row in commands) == 1
    assert all(row["control_gate_observation_hash"] for row in commands)
    assert "0" not in {row["day"] for row in action_ledger}


def test_v3_loads_exports_causal_rows_and_primes_without_warmup_actions(
    tmp_path: Path,
) -> None:
    policy_path = _write_v3_feedback_policy(tmp_path)
    risk_events_path = _write_v3_supplier_stress_event(tmp_path)
    reference_output = tmp_path / "v3_warmup_reference"
    reference = _run_engine(
        reference_output,
        supplier_risk_events_csv=risk_events_path,
        common_random_numbers=True,
        warmup_days=2,
        warmup_boundary_audit=True,
    )
    assert reference.returncode == 0, reference.stderr or reference.stdout

    feedback_output = tmp_path / "v3_warmup_feedback"
    feedback = _run_engine(
        feedback_output,
        control_policy_v3=policy_path,
        supplier_risk_events_csv=risk_events_path,
        prime_controller_during_warmup=True,
        warmup_boundary_audit=True,
        common_random_numbers=True,
        warmup_days=2,
    )
    assert feedback.returncode == 0, feedback.stderr or feedback.stdout

    reference_summary = json.loads(
        (
            reference_output / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    feedback_summary = json.loads(
        (
            feedback_output / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    reference_boundary = reference_summary["policy"]["warmup_boundary_audit"]
    feedback_boundary = feedback_summary["policy"]["warmup_boundary_audit"]
    assert reference_boundary["core_state_sha256"] == feedback_boundary[
        "core_state_sha256"
    ]
    assert reference_boundary["component_sha256"] == feedback_boundary[
        "component_sha256"
    ]

    provider = feedback_summary["policy"]["control_provider"]
    assert provider["schema_version"] == "scan.canonical_state_feedback.v3"
    assert provider["mode"] == "canonical_state_feedback_v3_continuous_t_plus_1"
    assert provider["continuous_relief_enabled"] is True
    assert provider["continuous_relief_decision_count"] >= 1
    assert provider["continuous_relief_integral_action"] is False
    assert provider["continuous_relief_future_information_access"] is False
    assert provider["physical_warmup_days"] == 2
    assert provider["controller_dynamic_warmup_days"] == 2
    assert provider["controller_warmup_matches_physical_warmup"] is True
    assert provider["warmup_control_action_count"] == 0
    assert provider["artifacts"]["priming"] == (
        "data/canonical_controller_priming.csv"
    )

    data_dir = feedback_output / "data"
    with (data_dir / "canonical_controller_priming.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        priming = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_observations.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        observations = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_decisions.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        decisions = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_commands.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        commands = list(csv.DictReader(handle))
    with (data_dir / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        action_ledger = list(csv.DictReader(handle))

    assert [row["day"] for row in priming] == ["-2", "-1"]
    assert {row["generated_command_count"] for row in priming} == {"0"}
    assert {row["active_command_row_count"] for row in priming} == {"0"}
    assert [row["day"] for row in observations] == ["0", "1"]
    assert [row["decision_day"] for row in decisions] == ["0", "1"]
    assert all(
        int(row["effective_day"]) == int(row["decision_day"]) + 1
        for row in decisions
    )
    assert decisions[0]["observation_hash"] == observations[0]["observation_hash"]
    assert decisions[0]["control_continuous_relief_active"] == "1"
    assert float(decisions[0]["control_continuous_relief_intensity"]) > 0.0

    assert commands
    assert min(int(row["effective_day"]) for row in commands) == 1
    assert all(
        int(row["effective_day"]) == int(row["decision_day"]) + 1
        for row in commands
    )
    assert commands[0]["control_continuous_relief_active"] == "1"
    assert commands[0]["control_continuous_relief_observation_valid"] == "1"
    assert "0" not in {row["day"] for row in action_ledger}


def test_v3_accepts_post_feedback_probe_and_preserves_controller_causality(
    tmp_path: Path,
) -> None:
    policy_path = _write_v3_feedback_policy(tmp_path)
    risk_events_path = _write_v3_supplier_stress_event(tmp_path)
    probe_path = _write_control_probe(
        tmp_path,
        name="active_closed_loop_probe.csv",
        order_multiplier=1.005,
    )
    output_dir = tmp_path / "v3_with_closed_loop_probe"

    result = _run_engine(
        output_dir,
        control_probe=probe_path,
        control_policy_v3=policy_path,
        supplier_risk_events_csv=risk_events_path,
        prime_controller_during_warmup=True,
        warmup_boundary_audit=True,
        common_random_numbers=True,
        warmup_days=2,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    summary = json.loads(
        (
            output_dir / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    provider = summary["policy"]["control_provider"]
    probe = summary["policy"]["control_probe"]
    assert provider["schema_version"] == "scan.canonical_state_feedback.v3"
    assert provider["closed_loop_claimed"] is True
    assert provider["causal_lag_days"] == 1
    assert provider["controller_dynamic_warmup_days"] == 2
    assert provider["warmup_control_action_count"] == 0
    assert probe["enabled"] is True
    assert probe["composition_mode"] == "post_feedback_additive"
    assert probe["schedule_rows"] == 2
    assert probe["scheduled_actions"] == 2
    assert probe["resolved_actions"] == 2
    assert probe["warmup_application_count"] == 0
    assert probe["feedback_command_export_modified"] is False
    assert probe["clipped_action_count"] == 0

    data_dir = output_dir / "data"
    with (data_dir / "canonical_control_probe_composition.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        composition = list(csv.DictReader(handle))
    with (data_dir / "canonical_closed_loop_commands.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        commands = list(csv.DictReader(handle))
    with (data_dir / "canonical_controller_priming.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        priming = list(csv.DictReader(handle))

    assert composition
    assert {int(row["day"]) for row in composition} == {0, 1}
    assert all(int(row["day"]) >= 0 for row in composition)
    assert {row["action"] for row in composition} == {"order_multiplier"}
    assert all(
        float(row["probe_delta"]) == pytest.approx(0.005)
        for row in composition
    )
    assert all(row["composition_clipped"] == "0" for row in composition)
    assert [row["day"] for row in priming] == ["-2", "-1"]
    assert {row["generated_command_count"] for row in priming} == {"0"}

    day_one_command = next(
        row for row in commands if int(row["effective_day"]) == 1
    )
    feedback_order = float(
        json.loads(day_one_command["effective_json"])["order_multiplier"]
    )
    day_one_composition = next(
        row
        for row in composition
        if int(row["day"]) == 1
        and row["feedback_source_line"]
    )
    assert float(day_one_composition["feedback_effective"]) == pytest.approx(
        feedback_order
    )
    assert float(day_one_composition["composed_effective"]) == pytest.approx(
        feedback_order + 0.005
    )
    assert float(
        json.loads(day_one_command["effective_json"])["order_multiplier"]
    ) == pytest.approx(feedback_order)


def test_neutral_v3_probe_preserves_physical_and_controller_outputs(
    tmp_path: Path,
) -> None:
    policy_path = _write_v3_feedback_policy(tmp_path)
    risk_events_path = _write_v3_supplier_stress_event(tmp_path)
    neutral_probe = _write_control_probe(
        tmp_path,
        name="neutral_closed_loop_probe.csv",
        order_multiplier=1.0,
    )
    baseline_dir = tmp_path / "v3_probe_neutral_baseline"
    probe_dir = tmp_path / "v3_probe_neutral_excited"
    common = {
        "control_policy_v3": policy_path,
        "supplier_risk_events_csv": risk_events_path,
        "prime_controller_during_warmup": True,
        "warmup_boundary_audit": True,
        "common_random_numbers": True,
        "warmup_days": 2,
    }

    baseline = _run_engine(baseline_dir, **common)
    excited = _run_engine(
        probe_dir,
        control_probe=neutral_probe,
        **common,
    )

    assert baseline.returncode == 0, baseline.stderr or baseline.stdout
    assert excited.returncode == 0, excited.stderr or excited.stdout
    for filename in (
        "first_simulation_daily.csv",
        "mrp_trace_daily.csv",
        "production_constraint_daily.csv",
        "canonical_closed_loop_observations.csv",
        "canonical_closed_loop_decisions.csv",
        "canonical_closed_loop_commands.csv",
    ):
        assert (baseline_dir / "data" / filename).read_bytes() == (
            probe_dir / "data" / filename
        ).read_bytes()

    probe_summary = json.loads(
        (
            probe_dir / "summaries" / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )
    assert probe_summary["policy"]["control_provider"][
        "closed_loop_claimed"
    ] is True
    assert probe_summary["policy"]["control_probe"][
        "clipped_action_count"
    ] == 0
    with (
        probe_dir / "data" / "canonical_control_probe_composition.csv"
    ).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert {float(row["probe_delta"]) for row in rows} == {0.0}
    assert all(int(row["day"]) >= 0 for row in rows)


def test_control_probe_requires_v2_or_v3_without_changing_old_exclusivity(
    tmp_path: Path,
) -> None:
    probe = _write_control_probe(
        tmp_path,
        name="requires_feedback.csv",
        order_multiplier=1.01,
    )
    v1_policy = _write_feedback_policy(tmp_path, force_active=False)
    result = _run_engine(
        tmp_path / "probe_with_v1",
        control_probe=probe,
        control_policy=v1_policy,
    )
    assert result.returncode != 0, result.stdout
    assert result.stderr.strip() == (
        "--control-probe-schedule-csv requires "
        "--control-policy-v2-json or --control-policy-v3-json."
    )


def test_control_policy_v3_exclusivity_preserves_historical_messages(
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "exclusive_schedule.csv"
    schedule.write_text("day,order_multiplier\n0,1.0\n", encoding="utf-8")
    v1_policy = _write_feedback_policy(tmp_path, force_active=False)
    v2_policy = _write_v2_feedback_policy(tmp_path)
    v3_policy = _write_v3_feedback_policy(tmp_path)
    historical_pair_message = (
        "--control-schedule-csv and --control-policy-json are mutually exclusive."
    )
    historical_v2_message = (
        "--control-schedule-csv, --control-policy-json and "
        "--control-policy-v2-json are mutually exclusive."
    )
    v3_message = (
        "--control-schedule-csv, --control-policy-json, "
        "--control-policy-v2-json and --control-policy-v3-json are mutually "
        "exclusive."
    )
    cases = (
        (
            "historical_schedule_v1",
            {"schedule": schedule, "control_policy": v1_policy},
            historical_pair_message,
        ),
        (
            "historical_schedule_v2",
            {"schedule": schedule, "control_policy_v2": v2_policy},
            historical_v2_message,
        ),
        (
            "historical_v1_v2",
            {"control_policy": v1_policy, "control_policy_v2": v2_policy},
            historical_v2_message,
        ),
        (
            "v3_schedule",
            {"schedule": schedule, "control_policy_v3": v3_policy},
            v3_message,
        ),
        (
            "v3_v1",
            {"control_policy": v1_policy, "control_policy_v3": v3_policy},
            v3_message,
        ),
        (
            "v3_v2",
            {"control_policy_v2": v2_policy, "control_policy_v3": v3_policy},
            v3_message,
        ),
    )

    for name, kwargs, expected_message in cases:
        result = _run_engine(tmp_path / name, **kwargs)
        assert result.returncode != 0, result.stdout
        assert result.stderr.strip() == expected_message


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
        reader = csv.DictReader(handle)
        ledger = list(reader)
    assert {
        "action_stage",
        "edge_id",
        "quantity_uom",
        "executed_control_volume_qty",
    }.issubset(set(reader.fieldnames or ()))
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


def test_fully_unresolved_action_keeps_physical_evidence_schema_empty(
    tmp_path: Path,
) -> None:
    schedule = tmp_path / "unresolved_priority.csv"
    schedule.write_text(
        "day,policy,priority_weight\n"
        "7,priority_outside_simulated_horizon,1.5\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "unresolved_priority"

    result = _run_engine(output_dir, schedule, days=2)

    assert result.returncode == 0, result.stderr or result.stdout
    with (output_dir / "data" / "canonical_action_ledger.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)
        ledger = list(reader)

    assert {
        "action_stage",
        "edge_id",
        "quantity_uom",
        "executed_control_volume_qty",
    }.issubset(set(reader.fieldnames or ()))
    assert len(ledger) == 1
    row = ledger[0]
    assert row["action"] == "priority_weight"
    assert row["status"] == "scheduled_not_resolved"
    assert row["action_stage"] == "schedule_audit"
    assert row["edge_id"] == ""
    assert row["quantity_uom"] == ""
    assert row["executed_control_volume_qty"] == ""
