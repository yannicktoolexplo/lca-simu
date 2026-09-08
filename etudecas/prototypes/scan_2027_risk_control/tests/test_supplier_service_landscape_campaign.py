from __future__ import annotations

import math
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.supplier_service_landscape_campaign import (
    CAMPAIGN_PROTOCOL_ARGS,
    CAPACITY_LEVELS_338929,
    CAPACITY_LEVELS_344135,
    CHAINS,
    DEFAULT_PROFILE,
    INCIDENT_START_DAY,
    RECOVERY_STABILITY_DAYS,
    RunConfig,
    Scenario,
    baseline_chain_incident_flow_audit,
    build_engine_command,
    build_prepared_physical_floor_rows,
    build_risk_event_rows,
    build_scenario_design,
    compute_service_metrics,
    compute_supplier_shipment_metrics,
    engine_profile_args,
    executable_scenarios,
    grouped_delay_windows,
    parse_args,
    physical_capacity_by_lane,
    prune_case_artifacts,
    select_confirmation_scenarios,
    summarize_scenarios,
    validation_errors,
)


def _scenario(
    chain_id: str, mechanism: str, level_index: int
) -> Scenario:
    return next(
        item
        for item in build_scenario_design()
        if item.chain_id == chain_id
        and item.mechanism_key == mechanism
        and item.level_index == level_index
    )


def test_design_is_complete_and_capacity_is_chain_specific() -> None:
    design = build_scenario_design()
    assert len(design) == 1 + 3 * 7 * 7
    assert len(executable_scenarios(design)) == 121
    assert [
        _scenario("338929_m1810_268091", "capacity", index).value
        for index in range(7)
    ] == list(CAPACITY_LEVELS_338929)
    assert [
        _scenario("344135_m1430_268967", "capacity", index).value
        for index in range(7)
    ] == list(CAPACITY_LEVELS_344135)
    unavailable = [
        item
        for item in design
        if item.chain_id == "021081_sdc1450_268967"
        and item.mechanism_key == "capacity"
    ]
    assert len(unavailable) == 7
    assert all(item.is_not_applicable for item in unavailable)
    assert not any(item in executable_scenarios(design) for item in unavailable)


def test_all_events_are_temporary_and_healthy_multisource_lane_is_untouched() -> None:
    days = 720
    scenario = _scenario("021081_sdc1450_268967", "reliability", 6)
    rows = build_risk_event_rows(scenario, days)
    assert len(rows) == 3
    assert {(int(row["start_day"]), int(row["end_day"])) for row in rows} == {
        (45, 224)
    }
    assert {row["supplier_id"] for row in rows} == {
        "SDC-VD0949099A",
        "SDC-VD0960508A",
        "SDC-VD0972460A",
    }
    assert "SDC-VD0975221A" not in {row["supplier_id"] for row in rows}


def test_intermittent_delay_has_declared_temporal_mean() -> None:
    days = 720
    scenario = _scenario("338929_m1810_268091", "intermittent_delay", 4)
    rows = build_risk_event_rows(scenario, days)
    windows = grouped_delay_windows(days)
    covered_days = sum(end - start + 1 for start, end in windows)
    assert covered_days == 90
    assert all(float(row["multiplier"]) == 2.0 * scenario.value for row in rows)
    assert covered_days * (2.0 * scenario.value) / 180.0 == pytest.approx(
        scenario.value
    )
    assert min(start for start, _ in windows) == INCIDENT_START_DAY
    assert max(end for _, end in windows) <= 224


def _floor_source_rows() -> list[dict[str, object]]:
    values = {
        ("SDC-VD0914360C", "item:338929", "M-1810"): (275000, 687500),
        ("SDC-VD0993480A", "item:344135", "M-1430"): (240000, 600000),
        ("SDC-VD0949099A", "item:021081", "SDC-1450"): (0, 0),
        ("SDC-VD0960508A", "item:021081", "SDC-1450"): (0, 0),
        ("SDC-VD0972460A", "item:021081", "SDC-1450"): (0, 0),
        ("SDC-VD0975221A", "item:021081", "SDC-1450"): (0, 0),
    }
    return [
        {
            "supplier_id": supplier,
            "item_id": item,
            "dst_node_id": destination,
            "neutral_capacity_floor_qty_per_day": neutral,
            "tested_capacity_floor_qty_per_day": tested,
            "neutral_opening_stock_floor_qty": 999,
            "input_initial_stock_qty": 999,
        }
        for (supplier, item, destination), (neutral, tested) in values.items()
    ]


def test_prepared_floor_prefers_tested_capacity_and_omits_stock() -> None:
    prepared, audit = build_prepared_physical_floor_rows(_floor_source_rows())
    assert len(prepared) == 2
    assert audit["override_row_count"] == 2
    assert audit["stock_columns_included"] is False
    assert all(not any("stock" in key for key in row) for row in prepared)
    row_338929 = next(row for row in prepared if row["item_id"] == "item:338929")
    assert float(row_338929["neutral_capacity_floor_qty_per_day"]) == 687500
    assert float(row_338929["tested_capacity_floor_qty_per_day"]) == 687500
    assert float(row_338929["effective_capacity_qty_per_day"]) == 687500
    capacities = physical_capacity_by_lane(prepared)
    assert capacities[("SDC-VD0993480A", "item:344135", "M-1430")] == 600000
    assert len(capacities) == 2
    assert not any(key[1] == "item:021081" for key in capacities)
    audited_021081 = [
        row for row in audit["relevant_lanes"] if row["item_id"] == "item:021081"
    ]
    assert len(audited_021081) == 4
    assert all(row["source_tested_capacity_qty_per_day"] == 0 for row in audited_021081)
    assert all(row["override_applied"] is False for row in audited_021081)


def test_managed_protocol_is_after_profile_and_defaults_are_separate(tmp_path: Path) -> None:
    config = RunConfig(
        repo_root=tmp_path,
        output_dir=tmp_path,
        engine=tmp_path / "engine.py",
        graph=tmp_path / "graph.json",
        supplier_floors=tmp_path / "floors.csv",
        factory_capacities=tmp_path / "factory.csv",
        profile_args=("--warmup-days", "1", "--mrp-multisource-policy", "cost"),
        scenario_id="scn:BASE",
        days=720,
        retention="summary",
        physical_capacity_by_lane={},
    )
    command = build_engine_command(
        config, case_dir=tmp_path / "case", seed=330281, risk_csv=None
    )
    assert tuple(command[-len(CAMPAIGN_PROTOCOL_ARGS) :]) == CAMPAIGN_PROTOCOL_ARGS
    assert command.index("--warmup-days") < len(command) - len(CAMPAIGN_PROTOCOL_ARGS)
    args = parse_args([])
    assert args.days == 720
    assert args.screening_seed == 330281
    assert args.confirmation_seeds == "330282-330291"
    assert args.factory_capacities is None
    assert args.engine_profile == DEFAULT_PROFILE
    profile_args = engine_profile_args(DEFAULT_PROFILE)
    assert "--mrp-static-requirement-pair" in profile_args
    assert command.count("--mrp-dynamic-requirement-pair") == 3
    assert command.count("--mrp-smoothed-cover-requirement-pair") == 1
    assert "--no-supplier-risk-loss-gross-up" in CAMPAIGN_PROTOCOL_ARGS
    assert "--external-procurement-proactive-replenishment" in CAMPAIGN_PROTOCOL_ARGS


def test_engine_command_uses_reference_graph_factory_capacity_by_default(
    tmp_path: Path,
) -> None:
    config = RunConfig(
        repo_root=tmp_path,
        output_dir=tmp_path,
        engine=tmp_path / "engine.py",
        graph=tmp_path / "graph.json",
        supplier_floors=tmp_path / "floors.csv",
        factory_capacities=None,
        profile_args=(),
        scenario_id="scn:BASE",
        days=720,
        retention="summary",
        physical_capacity_by_lane={},
    )
    command = build_engine_command(
        config, case_dir=tmp_path / "case", seed=330281, risk_csv=None
    )
    assert "--factory-nominal-capacities-csv" not in command


def test_service_metrics_use_ending_backlog_and_on_due_proxy() -> None:
    days = 260
    rows: list[dict[str, object]] = []
    for day in range(days):
        backlog = 100.0 if 45 <= day <= 230 else 0.0
        if day == days - 1:
            backlog = 100.0
        rows.append(
            {
                "day": day,
                "node_id": "C-XXXXX",
                "item_id": "item:268091",
                "demand_qty": 10,
                "served_qty": 10,
                "required_with_backlog_qty": 15 if day == 0 else 10,
                "backlog_end_qty": backlog,
            }
        )
    metrics = compute_service_metrics(
        rows, client_node_id="C-XXXXX", products=("268091",), days=days
    )["268091"]
    assert metrics["fill_rate"] == pytest.approx((2600 - 100) / 2600)
    assert metrics["served_qty"] == 2600
    assert metrics["starting_backlog_qty"] == 5
    assert metrics["on_due_volume_proxy"] == pytest.approx(2595 / 2600)
    assert metrics["first_backlog_day"] == 45
    assert metrics["backlog_peak_day"] == 45
    assert metrics["recovered_within_horizon"] is True
    assert metrics["recovery_day_after_incident"] == 231
    assert RECOVERY_STABILITY_DAYS == 28


def test_supplier_proxies_distinguish_quantity_and_lead() -> None:
    lane = CHAINS[0].affected_lanes[0]
    rows = [
        {
            "day": 45,
            "src_node_id": lane.supplier_id,
            "item_id": lane.item_id,
            "dst_node_id": lane.dst_node_id,
            "shipped_qty": 60,
            "pulled_qty": 100,
            "lead_days": 40,
            "reliability": 0.9,
            "arrival_day": 85,
        },
        {
            "day": 46,
            "src_node_id": lane.supplier_id,
            "item_id": lane.item_id,
            "dst_node_id": lane.dst_node_id,
            "shipped_qty": 20,
            "pulled_qty": 0,
            "lead_days": 50,
            "reliability": 0.8,
            "arrival_day": 96,
        },
    ]
    metrics = compute_supplier_shipment_metrics(rows, lanes=(lane,), days=720)
    assert metrics["service_horizon"] == pytest.approx(0.8)
    assert metrics["on_due_date_proxy"] == pytest.approx(0.6)
    assert metrics["incident_shipped_qty"] == 80
    assert metrics["incident_pulled_qty"] == 100


def _valid_protocol_row() -> dict[str, object]:
    return {
        "summary_sim_days": 720,
        "summary_timeline_days": 720,
        "summary_warmup_days": 240,
        "summary_total_simulated_timeline_days": 960,
        "resolved_mrp_demand_signal_smoothing_days": 7,
        "resolved_mrp_static_requirement_pairs": "M-1810|item:001757",
        "resolved_mrp_dynamic_requirement_pairs": (
            "M-1430|item:344135;M-1810|item:338929;SDC-1450|item:021081"
        ),
        "resolved_mrp_smoothed_cover_requirement_pairs": "M-1430|item:344135",
        "resolved_mrp_multisource_policy": "legacy",
        "resolved_initial_state_scale": 0.1,
        "resolved_opening_observed_stock_scale_enabled": True,
        "resolved_opening_observed_stock_scale_factor": 1.0,
        "resolved_opening_observed_stock_scale_source_csv": "",
        "resolved_warmup_profile_mode": "preperiod",
        "resolved_restore_opening_stock_after_warmup": False,
        "resolved_seed_open_orders_from_january_snapshot": False,
        "resolved_external_procurement_enabled": True,
        "resolved_external_procurement_proactive_replenishment": True,
        "resolved_external_procurement_lead_mode": "supplier_material",
        "resolved_external_procurement_capacity_mode": "supplier_nominal",
        "resolved_external_procurement_nominal_capacity_scale": 1.0,
        "resolved_supplier_risk_loss_gross_up": False,
        "resolved_supplier_state_dependent_risks_enabled": False,
        "all_product_horizons_complete": True,
        "j0_state_sha256": "same-j0",
        "input_sha256": "same-graph",
        "applied_physical_capacity_matches_expected": True,
    }


def test_validation_rejects_missing_events_and_hash_drift_without_assuming_impact() -> None:
    baseline = _valid_protocol_row()
    scenario = _scenario("338929_m1810_268091", "capacity", 5)
    row = {
        **_valid_protocol_row(),
        "configured_event_count": 0,
        "loaded_event_count": 0,
        "risk_applied_rows": 0,
        "healthy_risk_applied_rows": 0,
        "supplier_incident_capacity_binding_days": 0,
        "supplier_incident_flow_coverage_vs_paired_baseline": 1.0,
        "j0_state_sha256": "drifted",
    }
    errors = validation_errors(
        row, scenario=scenario, days=720, baseline_row=baseline
    )
    assert any("no configured risk event" in error for error in errors)
    assert any("no applied event row" in error for error in errors)
    assert any("J0 core-state" in error for error in errors)
    assert not any("neither binding" in error for error in errors)


def test_validation_rejects_static_mrp_and_perfect_incident_gross_up() -> None:
    scenario = _scenario("338929_m1810_268091", "reliability", 4)
    baseline = _valid_protocol_row()
    row = {
        **_valid_protocol_row(),
        "configured_event_count": 1,
        "loaded_event_count": 1,
        "risk_applied_rows": 1,
        "healthy_risk_applied_rows": 0,
        "resolved_mrp_static_requirement_pairs": "M-1810|item:338929",
        "resolved_supplier_risk_loss_gross_up": True,
    }
    errors = validation_errors(
        row, scenario=scenario, days=720, baseline_row=baseline
    )
    assert any("static MRP" in error for error in errors)
    assert any("perfectly grossed up" in error for error in errors)


def test_baseline_quality_guard_aborts_before_stress_scenarios() -> None:
    baseline_scenario = build_scenario_design()[0]
    row = {
        **_valid_protocol_row(),
        "fill_rate_268091": 0.949,
        "on_due_volume_proxy_268091": 0.99,
        "fill_rate_268967": 0.99,
        "on_due_volume_proxy_268967": 0.949,
    }
    errors = validation_errors(
        row, scenario=baseline_scenario, days=720, baseline_row=None
    )
    assert any("268091 horizon service" in error for error in errors)
    assert any("268967 on-due proxy" in error for error in errors)


def test_selection_uses_product_on_due_and_is_deterministic() -> None:
    design = build_scenario_design()
    candidates = [
        _scenario("338929_m1810_268091", "lead_extra", index)
        for index in (1, 2, 3, 4)
    ]
    baseline = {
        "scenario_id": "baseline_nominal",
        "fill_rate_268091": 1.0,
        "on_due_volume_proxy_268091": 1.0,
        "backlog_qty_days_268091": 0.0,
        "baseline_chain__338929_m1810_268091__incident_pulled_qty": 1000.0,
        "baseline_chain__338929_m1810_268091__incident_shipped_qty": 1000.0,
    }
    on_due = (0.98, 0.94, 0.90, 0.79)
    rows = [baseline]
    for scenario, value in zip(candidates, on_due):
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "product_on_due_date_proxy": value,
                # Horizon service deliberately ties: selection must not be fill-only.
                "product_service_horizon": 1.0,
                "incremental_target_backlog_qty_days": (1.0 - value) * 10000,
                "target_backlog_qty_days": (1.0 - value) * 10000,
                "target_worst_rolling_28d_on_due_proxy": value - 0.05,
                "target_recovered_within_horizon": value > 0.8,
                "target_recovery_day_after_incident": 250,
            }
        )
    first = select_confirmation_scenarios(rows, [design[0], *candidates])
    second = select_confirmation_scenarios(list(reversed(rows)), [design[0], *candidates])
    assert first == second
    assert candidates[-1].scenario_id in first
    assert any(
        "closest_product_on_due_93pct" in reasons for reasons in first.values()
    )
    assert any("neighbor_product_on_due_93pct" in reasons for reasons in first.values())


def test_selection_excludes_chain_without_paired_baseline_incident_flow() -> None:
    active = _scenario("338929_m1810_268091", "lead_extra", 4)
    inactive = _scenario("021081_sdc1450_268967", "lead_extra", 4)
    baseline = {
        "scenario_id": "baseline_nominal",
        "fill_rate_268091": 1.0,
        "on_due_volume_proxy_268091": 1.0,
        "backlog_qty_days_268091": 0.0,
        "fill_rate_268967": 1.0,
        "on_due_volume_proxy_268967": 1.0,
        "backlog_qty_days_268967": 0.0,
        "baseline_chain__338929_m1810_268091__incident_pulled_qty": 1000.0,
        "baseline_chain__338929_m1810_268091__incident_shipped_qty": 1000.0,
        "baseline_chain__344135_m1430_268967__incident_pulled_qty": 800.0,
        "baseline_chain__344135_m1430_268967__incident_shipped_qty": 800.0,
        "baseline_chain__021081_sdc1450_268967__incident_pulled_qty": 0.0,
        "baseline_chain__021081_sdc1450_268967__incident_shipped_qty": 0.0,
    }
    rows = [
        baseline,
        {
            "scenario_id": active.scenario_id,
            "product_on_due_date_proxy": 0.90,
            "product_service_horizon": 1.0,
            "incremental_target_backlog_qty_days": 1000.0,
            "target_backlog_qty_days": 1000.0,
            "target_worst_rolling_28d_on_due_proxy": 0.80,
            "target_recovered_within_horizon": True,
            "target_recovery_day_after_incident": 250,
        },
        {
            "scenario_id": inactive.scenario_id,
            "product_on_due_date_proxy": 0.10,
            "product_service_horizon": 0.20,
            "incremental_target_backlog_qty_days": 1_000_000.0,
            "target_backlog_qty_days": 1_000_000.0,
            "target_worst_rolling_28d_on_due_proxy": 0.0,
            "target_recovered_within_horizon": False,
            "target_recovery_day_after_incident": -1,
        },
    ]

    audit = baseline_chain_incident_flow_audit([baseline])
    assert audit["338929_m1810_268091"]["exercised"] is True
    assert audit["021081_sdc1450_268967"]["exercised"] is False
    assert audit["021081_sdc1450_268967"]["reason"] == (
        "zero_baseline_incident_flow"
    )

    selected = select_confirmation_scenarios(
        rows,
        [build_scenario_design()[0], active, inactive],
    )
    assert active.scenario_id in selected
    assert inactive.scenario_id not in selected


def test_baseline_chain_flow_audit_treats_missing_evidence_as_not_exercised() -> None:
    audit = baseline_chain_incident_flow_audit(
        [{"scenario_id": "baseline_nominal"}]
    )
    assert all(item["exercised"] is False for item in audit.values())
    assert all(
        item["reason"] == "missing_baseline_incident_flow"
        for item in audit.values()
    )


def test_not_applicable_capacity_is_visible_but_has_no_metrics() -> None:
    baseline_scenario = build_scenario_design()[0]
    not_applicable = _scenario("021081_sdc1450_268967", "capacity", 5)
    baseline_row = {
        "scenario_id": "baseline_nominal",
        "seed": 1,
        "valid": True,
        "fill_rate_268091": 1,
        "fill_rate_268967": 1,
        "on_due_volume_proxy_268091": 1,
        "on_due_volume_proxy_268967": 1,
        "backlog_qty_days_268091": 0,
        "backlog_qty_days_268967": 0,
    }
    summary = summarize_scenarios(
        [baseline_row], [], [baseline_scenario, not_applicable], {}
    )
    row = next(item for item in summary if item["scenario_id"] == not_applicable.scenario_id)
    assert row["is_not_applicable"] is True
    assert row["evidence_stage"] == "not_applicable"
    assert row["n_seeds"] == 0
    assert math.isnan(row["product_on_due_date_proxy"])


def test_retention_only_removes_allowlisted_generated_directories(tmp_path: Path) -> None:
    for name in ("data", "plots", "maps", "run", "summaries", "reports", "custom"):
        (tmp_path / name).mkdir()
    removed = prune_case_artifacts(tmp_path)
    assert removed == ["data", "maps", "plots", "run"]
    assert (tmp_path / "summaries").is_dir()
    assert (tmp_path / "reports").is_dir()
    assert (tmp_path / "custom").is_dir()
