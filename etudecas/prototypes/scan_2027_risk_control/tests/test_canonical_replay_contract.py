from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from etudecas.prototypes.scan_2027_risk_control.canonical_replay import (
    _append_canonical_oracle_rows,
    _attach_canonical_rci,
    _attach_mrp_reference_deltas,
    _paired_canonical_summary,
    _validate_canonical_result,
    duration_weighted_action,
    expand_action_schedule,
    extract_canonical_kpis,
    load_canonical_engine_profile,
    run_canonical_replays,
)
from etudecas.prototypes.scan_2027_risk_control.core import DEFAULT_ACTIONS
from etudecas.prototypes.scan_2027_risk_control.rci_validation import (
    REDUCED_RCI_SCOPE,
)


def _write_daily_result(
    root: Path,
    *,
    backlog: list[float],
    service: list[float],
) -> None:
    data = root / "data"
    data.mkdir(parents=True)
    demand = [100.0] * len(backlog)
    pd.DataFrame(
        {
            "day": range(len(backlog)),
            "demand": demand,
            "served": [
                demand_qty * service_value
                for demand_qty, service_value in zip(demand, service)
            ],
            "backlog_end": backlog,
            "inventory_total": [100.0] * len(backlog),
            "total_economic_exposure_day": [0.0] * len(backlog),
        }
    ).to_csv(data / "first_simulation_daily.csv", index=False)


def test_global_reduced_schedule_keeps_ineffective_priority_neutral() -> None:
    decisions = pd.DataFrame(
        [{"day": 0, "selected_policy": "supplier_relief"}]
    )
    schedule = expand_action_schedule(
        decisions,
        DEFAULT_ACTIONS,
        days=4,
    )

    assert set(schedule["priority_weight"]) == {1.0}
    assert (
        "global_supplier_relief_has_no_priority_allocation_effect"
        in schedule.attrs["mapping_limitations"]
    )
    weighted = duration_weighted_action(schedule)
    source = next(
        action
        for action in DEFAULT_ACTIONS
        if action.name == "supplier_relief"
    )
    assert weighted.smoothing == source.smoothing
    assert weighted.supplier_relief == source.supplier_relief


def test_canonical_engine_profile_is_audited_and_cannot_override_run_identity(
    tmp_path: Path,
) -> None:
    valid = tmp_path / "valid.json"
    valid.write_text(
        '{"schema_version":"test.v1","name":"fixture",'
        '"args":["--initial-state-scale","1"]}',
        encoding="utf-8",
    )
    args, metadata = load_canonical_engine_profile(tmp_path, valid.name)
    assert args == ("--initial-state-scale", "1")
    assert metadata["enabled"] is True
    assert metadata["name"] == "fixture"
    assert len(str(metadata["sha256"])) == 64

    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        '["--days","999"]',
        encoding="utf-8",
    )
    try:
        load_canonical_engine_profile(tmp_path, invalid.name)
    except ValueError as exc:
        assert "cannot override managed flag --days" in str(exc)
    else:
        raise AssertionError("managed canonical flags must be rejected")


def test_recovery_requires_seven_complete_consecutive_days(
    tmp_path: Path,
) -> None:
    censored = tmp_path / "censored"
    _write_daily_result(
        censored,
        backlog=[10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        service=[0.5, 1.0, 1.0, 1.0, 1.0, 1.0],
    )
    censored_kpis = extract_canonical_kpis(censored)
    assert math.isnan(censored_kpis["recovery_time_days"])
    assert censored_kpis["recovery_time_lower_bound_days"] == 5.0
    assert censored_kpis["recovery_followup_days"] == 5.0
    assert censored_kpis["recovery_status"] == "right_censored"

    observed = tmp_path / "observed"
    _write_daily_result(
        observed,
        backlog=[10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        service=[0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    )
    observed_kpis = extract_canonical_kpis(observed)
    assert observed_kpis["recovery_time_days"] == 1.0
    assert observed_kpis["recovery_time_lower_bound_days"] == 1.0
    assert observed_kpis["recovery_followup_days"] == 7.0
    assert observed_kpis["recovery_status"] == "observed"


def test_canonical_recovery_distinguishes_no_disruption_and_service_only(
    tmp_path: Path,
) -> None:
    nominal = tmp_path / "nominal"
    _write_daily_result(
        nominal,
        backlog=[0.0] * 8,
        service=[1.0] * 8,
    )
    nominal_kpis = extract_canonical_kpis(nominal)
    assert math.isnan(nominal_kpis["recovery_time_days"])
    assert math.isnan(nominal_kpis["recovery_time_lower_bound_days"])
    assert math.isnan(nominal_kpis["recovery_followup_days"])
    assert math.isnan(nominal_kpis["recovery_observed"])
    assert nominal_kpis["recovery_status"] == (
        "not_applicable_no_disruption"
    )
    assert nominal_kpis["recovery_episode_detected"] == 0.0
    assert nominal_kpis["recovery_episode_basis"] == "none"

    service_only = tmp_path / "service_only"
    _write_daily_result(
        service_only,
        backlog=[0.0] * 9,
        service=[1.0, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    )
    service_kpis = extract_canonical_kpis(service_only)
    assert service_kpis["recovery_time_days"] == 1.0
    assert service_kpis["recovery_time_lower_bound_days"] == 1.0
    assert service_kpis["recovery_followup_days"] == 7.0
    assert service_kpis["recovery_observed"] == 1.0
    assert service_kpis["recovery_status"] == "observed"
    assert service_kpis["recovery_episode_detected"] == 1.0
    assert service_kpis["recovery_episode_basis"] == "service_minimum"


def test_expedite_and_supplier_risk_kpis_use_executed_physical_rows(
    tmp_path: Path,
) -> None:
    result = tmp_path / "result"
    _write_daily_result(
        result,
        backlog=[0.0],
        service=[1.0],
    )
    data = result / "data"
    pd.DataFrame(
        [
            {
                "day": 0,
                "action": "expedite_level",
                "status": "applied",
                "action_stage": "supplier_lane_execution",
                "effective": 0.5,
                "executed_control_volume_qty": 10.0,
            },
            {
                "day": 0,
                "action": "expedite_level",
                "status": "scheduled_not_resolved",
                "action_stage": "schedule_audit",
                "effective": 1.0,
                "executed_control_volume_qty": "",
            },
        ]
    ).to_csv(data / "canonical_action_ledger.csv", index=False)
    pd.DataFrame(
        [
            {
                "day": 0,
                "supplier_id": "S1",
                "dst_node_id": "F1",
                "item_id": "I1",
                "edge_id": "E1",
                "event_ids": "exogenous_1",
                "capacity_multiplier": 0.5,
                "availability_multiplier": 1.0,
            },
            {
                "day": 0,
                "supplier_id": "S2",
                "dst_node_id": "F1",
                "item_id": "I2",
                "edge_id": "E2",
                "event_ids": "state_capacity_S2_d0",
                "capacity_multiplier": 0.8,
                "availability_multiplier": 1.0,
            },
        ]
    ).to_csv(
        data / "supplier_risk_events_applied_daily.csv",
        index=False,
    )

    kpis = extract_canonical_kpis(result)
    assert kpis["expedite_area"] == 0.5
    assert kpis["expedited_qty"] == 5.0
    assert kpis["supplier_risk_area"] > 0.0
    assert kpis["exogenous_supplier_risk_area"] > 0.0
    assert kpis["endogenous_state_supplier_risk_area"] > 0.0
    assert math.isclose(
        kpis["supplier_risk_area"],
        kpis["exogenous_supplier_risk_area"]
        + kpis["endogenous_state_supplier_risk_area"],
    )


def test_paired_summary_uses_seed_intersection_and_safe_paired_effect() -> None:
    rows = [
        {
            "policy": "mrp_reference",
            "seed": 1,
            "status": "ok",
            "service_loss": 0.2,
        },
        {
            "policy": "mrp_reference",
            "seed": 2,
            "status": "ok",
            "service_loss": 0.3,
        },
        {
            "policy": "balanced_robust",
            "seed": 2,
            "status": "ok",
            "service_loss": 0.1,
        },
        {
            "policy": "balanced_robust",
            "seed": 3,
            "status": "ok",
            "service_loss": 0.0,
        },
    ]
    summary = _paired_canonical_summary(pd.DataFrame(rows))

    reference = summary.loc[
        summary["policy"].eq("mrp_reference")
    ].iloc[0]
    controlled = summary.loc[
        summary["policy"].eq("balanced_robust")
    ].iloc[0]
    assert int(reference["paired_seed_count"]) == 2
    assert float(reference["mean_delta_service_loss"]) == 0.0
    assert float(reference["ci95_low_delta_service_loss"]) == 0.0
    assert float(reference["ci95_high_delta_service_loss"]) == 0.0
    assert float(reference["standardized_effect_service_loss"]) == 0.0
    assert int(controlled["paired_seed_count"]) == 1
    assert math.isnan(float(controlled["ci95_low_delta_service_loss"]))
    assert math.isnan(float(controlled["ci95_high_delta_service_loss"]))
    assert (
        controlled["ci95_status_delta_service_loss"]
        == "not_estimable_single_pair"
    )
    assert math.isnan(float(controlled["standardized_effect_service_loss"]))
    assert (
        controlled["standardized_effect_status_service_loss"]
        == "not_estimable_single_pair"
    )


def test_paired_summary_uses_student_interval_for_three_pairs() -> None:
    rows = []
    for seed, controlled_value in enumerate((9.0, 10.0, 11.0), start=1):
        rows.extend(
            [
                {
                    "policy": "mrp_reference",
                    "seed": seed,
                    "status": "ok",
                    "service_loss": 10.0,
                },
                {
                    "policy": "balanced_robust",
                    "seed": seed,
                    "status": "ok",
                    "service_loss": controlled_value,
                },
            ]
        )

    summary = _paired_canonical_summary(pd.DataFrame(rows))
    controlled = summary.loc[
        summary["policy"].eq("balanced_robust")
    ].iloc[0]
    expected_half_width = 4.30265272975 / math.sqrt(3.0)

    assert controlled["ci95_status_delta_service_loss"] == "student_t_95"
    assert math.isclose(
        float(controlled["ci95_low_delta_service_loss"]),
        -expected_half_width,
    )
    assert math.isclose(
        float(controlled["ci95_high_delta_service_loss"]),
        expected_half_width,
    )


def test_canonical_runs_export_per_seed_mrp_deltas_and_censor_recovery() -> None:
    runs = pd.DataFrame(
        [
            {
                "policy": "mrp_reference",
                "seed": 1,
                "status": "ok",
                "service_loss": 0.30,
                "recovery_time_days": math.nan,
                "recovery_time_lower_bound_days": 9.0,
                "recovery_followup_days": 9.0,
                "recovery_observed": 0.0,
                "recovery_status": "right_censored",
            },
            {
                "policy": "balanced_robust",
                "seed": 1,
                "status": "ok",
                "service_loss": 0.20,
                "recovery_time_days": 5.0,
                "recovery_time_lower_bound_days": 5.0,
                "recovery_followup_days": 9.0,
                "recovery_observed": 1.0,
                "recovery_status": "observed",
            },
            {
                "policy": "mrp_reference",
                "seed": 2,
                "status": "ok",
                "service_loss": 0.25,
                "recovery_time_days": 4.0,
                "recovery_time_lower_bound_days": 4.0,
                "recovery_followup_days": 9.0,
                "recovery_observed": 1.0,
                "recovery_status": "observed",
            },
            {
                "policy": "balanced_robust",
                "seed": 2,
                "status": "ok",
                "service_loss": 0.10,
                "recovery_time_days": 2.0,
                "recovery_time_lower_bound_days": 2.0,
                "recovery_followup_days": 9.0,
                "recovery_observed": 1.0,
                "recovery_status": "observed",
            },
        ]
    )

    paired_runs = _attach_mrp_reference_deltas(runs)
    reference = paired_runs.loc[
        paired_runs["policy"].eq("mrp_reference")
    ]
    assert (reference["delta_vs_mrp_service_loss"] == 0.0).all()
    assert (reference["delta_vs_mrp_recovery_time_days"] == 0.0).all()

    controlled_seed_1 = paired_runs.loc[
        paired_runs["policy"].eq("balanced_robust")
        & paired_runs["seed"].eq(1)
    ].iloc[0]
    controlled_seed_2 = paired_runs.loc[
        paired_runs["policy"].eq("balanced_robust")
        & paired_runs["seed"].eq(2)
    ].iloc[0]
    assert controlled_seed_1["mrp_reference_service_loss"] == 0.30
    assert math.isclose(
        controlled_seed_1["delta_vs_mrp_service_loss"],
        -0.10,
    )
    assert math.isnan(
        controlled_seed_1["delta_vs_mrp_recovery_time_days"]
    )
    assert (
        controlled_seed_1["delta_vs_mrp_recovery_time_status"]
        == "not_comparable_censored"
    )
    assert controlled_seed_2["delta_vs_mrp_recovery_time_days"] == -2.0
    assert (
        controlled_seed_2["delta_vs_mrp_recovery_time_status"]
        == "observed_pair"
    )

    summary = _paired_canonical_summary(paired_runs)
    controlled_summary = summary.loc[
        summary["policy"].eq("balanced_robust")
    ].iloc[0]
    assert (
        int(controlled_summary["paired_observed_count_recovery_time_days"])
        == 1
    )
    assert controlled_summary["mean_delta_recovery_time_days"] == -2.0
    assert math.isnan(
        controlled_summary["ci95_low_delta_recovery_time_days"]
    )
    assert (
        controlled_summary["ci95_status_delta_recovery_time_days"]
        == "not_estimable_single_pair"
    )


def test_canonical_oracle_is_derived_from_best_fixed_policy() -> None:
    runs = pd.DataFrame(
        [
            {
                "policy": "mrp_reference",
                "seed": 7,
                "status": "ok",
                "run_kind": "physical_replay",
                "is_derived": 0,
                "service_loss": 0.2,
                "constraint_violations": 0.0,
                "backlog_area_days": 2.0,
                "recovery_time_days": 4.0,
                "risk_creation_index": 0.0,
                "total_economic_exposure": 10.0,
                "result_dir": "mrp",
            },
            {
                "policy": "balanced_robust",
                "seed": 7,
                "status": "ok",
                "run_kind": "physical_replay",
                "is_derived": 0,
                "service_loss": 0.1,
                "constraint_violations": 1.0,
                "backlog_area_days": 1.0,
                "recovery_time_days": 2.0,
                "risk_creation_index": 0.1,
                "total_economic_exposure": 12.0,
                "result_dir": "balanced",
            },
            {
                "policy": "adaptive_daily",
                "seed": 7,
                "status": "ok",
                "run_kind": "physical_replay",
                "is_derived": 0,
                "service_loss": 0.0,
                "constraint_violations": 0.0,
                "backlog_area_days": 0.0,
                "recovery_time_days": 0.0,
                "risk_creation_index": 0.0,
                "total_economic_exposure": 1.0,
                "result_dir": "adaptive",
            },
        ]
    )
    with_oracle = _append_canonical_oracle_rows(
        runs,
        fixed_policy_names=("mrp_reference", "balanced_robust"),
    )
    oracle = with_oracle.loc[with_oracle["policy"].eq("oracle")].iloc[0]

    assert oracle["run_kind"] == "derived_oracle"
    assert int(oracle["is_derived"]) == 1
    assert oracle["oracle_fixed_policy"] == "balanced_robust"
    assert oracle["derived_from_result_dir"] == "balanced"
    assert len(with_oracle.loc[with_oracle["run_kind"].eq("physical_replay")]) == 3


def test_canonical_rci_proxy_is_scoped_separately_from_business_review() -> None:
    runs = pd.DataFrame(
        [
            {
                "policy": "mrp_reference",
                "seed": 7,
                "status": "ok",
                "order_nervousness": 1.0,
                "production_nervousness": 1.0,
                "constraint_violations": 0.0,
                "expedite_area": 0.0,
                "external_procurement_qty": 0.0,
                "post_crisis_overstock_days": 1.0,
            },
            {
                "policy": "balanced_robust",
                "seed": 7,
                "status": "ok",
                "order_nervousness": 2.0,
                "production_nervousness": 1.5,
                "constraint_violations": 1.0,
                "expedite_area": 1.0,
                "external_procurement_qty": 1.0,
                "post_crisis_overstock_days": 2.0,
            },
        ]
    )
    scoped = _attach_canonical_rci(runs)
    assert (
        scoped["canonical_risk_creation_proxy_scope"]
        == "canonical_multi_product_engine_replay"
    ).all()
    assert (
        scoped["canonical_risk_creation_proxy_scope"] != REDUCED_RCI_SCOPE
    ).all()
    assert (
        scoped["canonical_risk_creation_proxy"]
        == scoped["risk_creation_index"]
    ).all()
    assert (
        scoped["canonical_risk_creation_proxy_business_validation"]
        == "not_covered_by_reduced_model_business_review"
    ).all()


def test_zero_return_with_missing_outputs_is_visible_and_clears_stale_ledger(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    graph.write_text('{"nodes": [], "edges": [], "scenarios": []}\n')
    engine = tmp_path / "fake_engine.py"
    engine.write_text("raise SystemExit(0)\n")
    output = tmp_path / "canonical"
    output.mkdir()
    (output / "canonical_action_ledger.csv").write_text(
        "day,stale\n0,previous_campaign\n"
    )

    runs, summary, _ = run_canonical_replays(
        graph_path=graph,
        output_root=output,
        decisions=pd.DataFrame(),
        actions=DEFAULT_ACTIONS,
        days=2,
        seeds=(17,),
        repo_root=tmp_path,
        engine_script=engine,
        selected_policy_names=("mrp_reference",),
        enable_state_dependent_risks=False,
    )

    assert set(runs["status"]) == {"invalid_output"}
    assert (runs["run_kind"] == "physical_replay").all()
    assert (runs["is_derived"] == 0).all()
    assert runs["error"].str.contains("missing summaries/").all()
    assert summary.empty
    cleared = pd.read_csv(output / "canonical_action_ledger.csv")
    assert cleared.empty
    assert "stale" not in cleared.columns


def test_canonical_result_requires_expected_risk_events_to_be_applied(
    tmp_path: Path,
) -> None:
    result = tmp_path / "result"
    data = result / "data"
    summaries = result / "summaries"
    data.mkdir(parents=True)
    summaries.mkdir(parents=True)
    input_path = tmp_path / "input.json"
    input_path.write_text('{"nodes": [], "edges": []}\n', encoding="utf-8")
    risk_path = tmp_path / "risk.csv"
    risk_events = pd.DataFrame(
        [
            {
                "event_id": "EVENT-1",
                "risk_type": "purchase_cost",
                "supplier_id": "SUP-A",
                "item_id": "item:A",
                "dst_node_id": "FAC-A",
                "start_day": 0,
                "end_day": 0,
                "multiplier": 1.2,
            }
        ]
    )
    risk_events.to_csv(risk_path, index=False)
    summary = {
        "input_file": str(input_path),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "scenario_id": "scn:BASE",
        "sim_days": 1,
        "policy": {
            "seed": 17,
            "common_random_numbers": True,
            "control_schedule": {
                "enabled": False,
                "sha256": "",
            },
            "supplier_risk": {
                "enabled": True,
                "events_csv": str(risk_path),
                "events_csv_sha256": hashlib.sha256(
                    risk_path.read_bytes()
                ).hexdigest(),
                "event_count": 1,
            },
        },
    }
    (summaries / "first_simulation_summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    pd.DataFrame([{"day": 0}]).to_csv(
        data / "first_simulation_daily.csv",
        index=False,
    )
    pd.DataFrame(columns=["day", "action", "status"]).to_csv(
        data / "canonical_action_ledger.csv",
        index=False,
    )
    for name in (
        "production_output_products_daily.csv",
        "production_constraint_daily.csv",
    ):
        pd.DataFrame(columns=["diagnostic"]).to_csv(
            data / name,
            index=False,
        )
    pd.DataFrame(
        columns=[
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "release_qty",
            "planned_receipt_qty",
            "order_type",
        ]
    ).to_csv(data / "mrp_orders_daily.csv", index=False)
    pd.DataFrame(
        columns=[
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "pulled_qty",
            "shipped_qty",
        ]
    ).to_csv(
        data / "production_supplier_shipments_daily.csv",
        index=False,
    )
    applied_path = data / "supplier_risk_events_applied_daily.csv"
    pd.DataFrame(
        columns=[
            "day",
            "event_ids",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "purchase_cost_multiplier",
        ]
    ).to_csv(applied_path, index=False)

    errors = _validate_canonical_result(
        result,
        expect_schedule=False,
        expected_schedule_sha256="",
        expected_days=1,
        expected_seed=17,
        expected_scenario_id="scn:BASE",
        expected_input_path=input_path,
        expected_risk_events=risk_events,
        expected_risk_csv_path=risk_path,
    )
    assert "expected supplier risk events produced no applied rows" in errors

    pd.DataFrame(
        [
            {
                "day": 0,
                "event_ids": "EVENT-1",
                "supplier_id": "SUP-A",
                "item_id": "item:A",
                "dst_node_id": "FAC-A",
                "purchase_cost_multiplier": 1.0,
            }
        ]
    ).to_csv(applied_path, index=False)
    neutral_errors = _validate_canonical_result(
        result,
        expect_schedule=False,
        expected_schedule_sha256="",
        expected_days=1,
        expected_seed=17,
        expected_scenario_id="scn:BASE",
        expected_input_path=input_path,
        expected_risk_events=risk_events,
        expected_risk_csv_path=risk_path,
    )
    assert any(
        "status=matched_not_applied" in error
        and "appropriate_effect_remained_neutral" in error
        for error in neutral_errors
    )

    applied_cost_only = pd.read_csv(applied_path)
    applied_cost_only["purchase_cost_multiplier"] = 1.2
    applied_cost_only.to_csv(applied_path, index=False)
    cost_only_errors = _validate_canonical_result(
        result,
        expect_schedule=False,
        expected_schedule_sha256="",
        expected_days=1,
        expected_seed=17,
        expected_scenario_id="scn:BASE",
        expected_input_path=input_path,
        expected_risk_events=risk_events,
        expected_risk_csv_path=risk_path,
    )
    assert any(
        "status=applied_no_nonzero_flow" in error
        and "no_nonzero_shipments_or_orders_on_event_lane" in error
        for error in cost_only_errors
    )
    validation = pd.read_csv(
        data / "canonical_supplier_risk_event_validation.csv"
    )
    assert validation.loc[0, "matched"]
    assert validation.loc[0, "applied"]
    assert not validation.loc[0, "affected_nonzero_flow"]

    pd.DataFrame(
        [
            {
                "day": 0,
                "src_node_id": "SUP-A",
                "dst_node_id": "FAC-A",
                "item_id": "item:A",
                "pulled_qty": 10.0,
                "shipped_qty": 10.0,
            }
        ]
    ).to_csv(
        data / "production_supplier_shipments_daily.csv",
        index=False,
    )
    assert _validate_canonical_result(
        result,
        expect_schedule=False,
        expected_schedule_sha256="",
        expected_days=1,
        expected_seed=17,
        expected_scenario_id="scn:BASE",
        expected_input_path=input_path,
        expected_risk_events=risk_events,
        expected_risk_csv_path=risk_path,
    ) == []
    validation = pd.read_csv(
        data / "canonical_supplier_risk_event_validation.csv"
    )
    assert validation.loc[0, "status"] == "affected_nonzero_flow"


def test_nonzero_engine_return_is_recorded_and_not_masked(
    tmp_path: Path,
) -> None:
    graph = tmp_path / "graph.json"
    graph.write_text(
        '{"nodes": [], "edges": [], "scenarios": []}\n',
        encoding="utf-8",
    )
    engine = tmp_path / "failing_engine.py"
    engine.write_text(
        "import sys\nprint('intentional replay failure', file=sys.stderr)\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )

    runs, summary, _ = run_canonical_replays(
        graph_path=graph,
        output_root=tmp_path / "canonical",
        decisions=pd.DataFrame(),
        actions=DEFAULT_ACTIONS,
        days=2,
        seeds=(19,),
        repo_root=tmp_path,
        engine_script=engine,
        selected_policy_names=("mrp_reference",),
        enable_state_dependent_risks=False,
    )

    assert set(runs["status"]) == {"failed"}
    assert set(runs["returncode"]) == {7}
    assert runs["error"].str.contains("intentional replay failure").all()
    assert (runs["run_kind"] == "physical_replay").all()
    assert (runs["is_derived"] == 0).all()
    assert summary.empty
