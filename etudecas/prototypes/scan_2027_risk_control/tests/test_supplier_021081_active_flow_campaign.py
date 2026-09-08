from __future__ import annotations

import math
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as campaign,
)


def _actual_graph() -> dict[str, object]:
    return campaign.read_json(campaign.DEFAULT_GRAPH)


def _scenario(scope: str, mechanism: str, value: float) -> campaign.Scenario:
    return next(
        scenario
        for scenario in campaign.build_scenarios()
        if scenario.scope_id == scope
        and scenario.mechanism == mechanism
        and math.isclose(scenario.value, value)
    )


def test_real_2025_order_book_is_audited_and_not_called_actual_otif() -> None:
    rows = campaign.observed_orders(_actual_graph())
    audit = campaign.audit_observed_order_book(rows)
    assert audit["validated"] is True
    assert audit["order_count"] == 23
    assert audit["quantity_kg"] == 1_320_000
    assert (
        audit["physical_delivery_day_min"], audit["physical_delivery_day_max"]
    ) == (6, 139)
    assert (audit["usable_day_min"], audit["usable_day_max"]) == (112, 261)
    by_supplier = {
        row["supplier_id"]: row for row in audit["supplier_rows"]
    }
    assert by_supplier["SDC-VD0960508A"]["quantity_kg"] == 820_000
    assert by_supplier["SDC-VD0949099A"]["quantity_kg"] == 300_000
    assert by_supplier["SDC-VD0972460A"]["quantity_kg"] == 100_000
    assert by_supplier["SDC-VD0975221A"]["quantity_kg"] == 100_000
    assert by_supplier["SDC-VD0960508A"]["observed_order_book_share"] == pytest.approx(
        820_000 / 1_320_000
    )
    export = campaign.observed_order_export_rows(rows)
    assert {row["evidence_class"] for row in export} == {"observed_2025"}


def test_design_separates_four_suppliers_and_common_causes() -> None:
    scenarios = campaign.build_scenarios()
    assert len(scenarios) == 1 + 5 * 6 * 3
    isolated = [
        scenario
        for scenario in scenarios
        if not scenario.is_baseline and scenario.scope_id in campaign.SUPPLIER_IDS
    ]
    common = [
        scenario
        for scenario in scenarios
        if not scenario.is_baseline and scenario.scope_id == "all_021081"
    ]
    assert len(isolated) == 4 * 6 * 3
    assert len(common) == 6 * 3
    assert {scenario.scope_id for scenario in isolated} == set(campaign.SUPPLIER_IDS)


def test_state_envelope_keeps_observed_state_separate_from_hypotheses() -> None:
    regimes = campaign.build_state_regimes(_actual_graph())
    assert [regime.regime_id for regime in regimes] == [
        "observed_2025",
        "prospective_365d_cover",
        "prospective_180d_cover",
        "prospective_90d_cover",
        "prospective_30d_cover",
    ]
    observed = regimes[0]
    assert observed.opening_stock_qty_kg == 1_142_100
    assert observed.stock_scale == 1
    assert observed.evidence_class == "observed_2025_snapshot_state"
    prospective = regimes[1:]
    assert all(
        regime.evidence_class
        == "simulated_reduced_cover_hypothesis_not_observed"
        for regime in prospective
    )
    assert prospective[0].opening_stock_qty_kg == pytest.approx(357.6 * 365)
    assert prospective[-1].opening_stock_qty_kg == pytest.approx(357.6 * 30)
    assert all("021081 seule" in regime.label for regime in prospective)


def test_intermediate_masking_audit_uses_29_released_lots() -> None:
    assert campaign.INTERMEDIATE_268967_RELEASED_LOT_COUNT == 29
    assert campaign.INTERMEDIATE_773474_HORIZON_NEED_G == pytest.approx(
        30_182_579.4
    )
    assert campaign.INTERMEDIATE_773474_STOCK_COVER_LOTS == pytest.approx(
        23.2450974684
    )
    assert campaign.INTERMEDIATE_773474_STOCK_TO_HORIZON_NEED == pytest.approx(
        0.8015550851
    )
    assert (
        campaign.INTERMEDIATE_773474_STOCK_PLUS_PRODUCTION_TO_NEED
        == pytest.approx(1.7557478868)
    )


def test_baseline_overlay_replays_exact_orders_and_preserves_everything_else() -> None:
    graph = _actual_graph()
    baseline = campaign.build_scenarios()[0]
    overlay, ledger, audit = campaign.build_graph_overlay(
        graph, baseline, seed=campaign.SCREENING_SEED
    )
    assert audit["non_target_graph_and_order_book_preserved"] is True
    assert len(ledger) == 23
    assert len(campaign.observed_orders(overlay)) == 23
    assert sum(float(row["simulated_usable_quantity_kg"]) for row in ledger) == 1_320_000
    assert not any(row["affected_by_hypothesis"] for row in ledger)
    source_non_target = [
        row
        for row in campaign.opening_order_payload(graph)["rows"]
        if not campaign.is_target_order(row)
    ]
    overlay_non_target = [
        row
        for row in campaign.opening_order_payload(overlay)["rows"]
        if not campaign.is_target_order(row)
    ]
    assert campaign.json_sha256(source_non_target) == campaign.json_sha256(
        overlay_non_target
    )


def test_engine_mode_keeps_raw_orders_and_capacity_uses_declared_fallback() -> None:
    graph = _actual_graph()
    delay = _scenario("SDC-VD0960508A", "delivery_delay", 90.0)
    overlay, ledger, audit = campaign.build_graph_overlay(
        graph,
        delay,
        seed=8,
        opening_order_risk_mode="engine",
    )
    assert audit["order_risk_application_layer"] == "engine_native_at_seed"
    assert audit["engine_native_opening_order_risk_enabled"] is True
    assert campaign.observed_orders(overlay) == campaign.observed_orders(graph)
    assert all(not row["pre_engine_overlay_transformed"] for row in ledger)

    capacity = _scenario("SDC-VD0960508A", "capacity_rationing", 0.25)
    capacity_overlay, _ledger, capacity_audit = campaign.build_graph_overlay(
        graph,
        capacity,
        seed=8,
        opening_order_risk_mode="engine",
    )
    assert (
        capacity_audit["order_risk_application_layer"]
        == "campaign_overlay_capacity_fallback"
    )
    assert capacity_audit["engine_native_opening_order_risk_enabled"] is False
    assert campaign.observed_orders(capacity_overlay) != campaign.observed_orders(
        graph
    )


def test_isolated_supplier_delay_does_not_touch_other_sources() -> None:
    rows = campaign.observed_orders(_actual_graph())
    scenario = _scenario("SDC-VD0949099A", "delivery_delay", 90.0)
    _transformed, ledger = campaign.transform_order_book(rows, scenario, seed=77)
    assert all(
        row["planned_usable_date_shift_days"] == 90
        for row in ledger
        if row["supplier_id"] == "SDC-VD0949099A"
    )
    assert all(
        row["planned_usable_date_shift_days"] == 0
        for row in ledger
        if row["supplier_id"] != "SDC-VD0949099A"
    )
    assert all(row["simulated_quantity_loss_kg"] == 0 for row in ledger)


def test_quantity_and_availability_hypotheses_have_a_reproducible_ledger() -> None:
    rows = campaign.observed_orders(_actual_graph())
    yield_scenario = _scenario("all_021081", "usable_yield", 0.5)
    _transformed, yield_ledger = campaign.transform_order_book(
        rows, yield_scenario, seed=11
    )
    assert sum(float(row["simulated_usable_quantity_kg"]) for row in yield_ledger) == 660_000
    assert sum(float(row["simulated_quantity_loss_kg"]) for row in yield_ledger) == 660_000

    availability = _scenario(
        "SDC-VD0960508A", "delivery_availability", 0.5
    )
    first_rows, first_ledger = campaign.transform_order_book(
        rows, availability, seed=123
    )
    second_rows, second_ledger = campaign.transform_order_book(
        rows, availability, seed=123
    )
    assert first_rows == second_rows
    assert first_ledger == second_ledger
    assert all(
        row["stable_random_score"] == ""
        for row in first_ledger
        if row["supplier_id"] != "SDC-VD0960508A"
    )


def test_capacity_rationing_is_fifo_and_never_advances_a_planned_date() -> None:
    rows = campaign.observed_orders(_actual_graph())
    scenario = _scenario("all_021081", "capacity_rationing", 0.25)
    _transformed, ledger = campaign.transform_order_book(rows, scenario, seed=4)
    assert all(
        int(row["simulated_physical_delivery_day"])
        >= int(row["source_planned_physical_delivery_day"])
        for row in ledger
    )
    assert any(row["planned_physical_date_shift_days"] > 0 for row in ledger)
    assert all(row["reference_observed_peak_daily_qty_kg"] for row in ledger)


def test_risk_csv_is_only_the_dynamic_mrp_layer() -> None:
    scenario = _scenario("SDC-VD0972460A", "quality_hold", 90.0)
    rows = campaign.risk_event_rows(scenario, 720)
    assert len(rows) == 1
    assert rows[0]["supplier_id"] == "SDC-VD0972460A"
    assert rows[0]["risk_type"] == "quality_delay"
    assert rows[0]["start_day"] == 0
    assert rows[0]["end_day"] == 261
    assert "Dynamic MRP orders only" in rows[0]["notes"]


def test_snapshot_replay_has_no_prospective_warmup_and_smooths_021081() -> None:
    args = campaign.ACTIVE_021081_PROTOCOL_ARGS
    assert campaign.WARMUP_DAYS == 0
    assert args[args.index("--warmup-days") + 1] == "0"
    assert args[args.index("--initial-state-scale") + 1] == "1"
    assert "--initial-seed-open-orders-from-january-snapshot" in args
    assert "--initial-seed-estimated-source-pipeline" in args
    index = args.index("--mrp-smoothed-cover-requirement-pair")
    assert args[index + 1] == "SDC-1450,item:021081"
    assert "--no-supplier-risk-loss-gross-up" in args


def test_managed_protocol_is_after_profile_and_lot_trace_is_enabled(
    tmp_path: Path,
) -> None:
    command = campaign.build_engine_command(
        engine=tmp_path / "engine.py",
        graph=tmp_path / "graph.json",
        output_dir=tmp_path / "out",
        profile_args=("--warmup-days", "240", "--no-initial-seed-open-orders-from-january-snapshot"),
        days=720,
        seed=1,
        risk_csv=tmp_path / "risk.csv",
        apply_risk_to_opening_orders=True,
    )
    assert command.index("--lot-trace") < command.index("--warmup-days")
    warmup_indices = [index for index, value in enumerate(command) if value == "--warmup-days"]
    assert command[warmup_indices[-1] + 1] == "0"
    assert "--supplier-risk-events-apply-to-opening-purchase-orders" in command
    assert "--no-supplier-risk-events-apply-to-opening-purchase-orders" not in command
    assert command[-2:] == ["--supplier-risk-events-csv", str(tmp_path / "risk.csv")]
    normalized = campaign.normalized_engine_command(command)
    assert str(tmp_path / "graph.json") not in normalized
    assert str(tmp_path / "out") not in normalized
    assert "<CASE_GRAPH_OVERLAY>" in normalized
    assert "<CASE_OUTPUT_DIR>" in normalized
    assert "<CASE_RISK_CSV>" in normalized


def test_reference_gate_uses_replayed_and_dynamic_flows_separately() -> None:
    baseline = {
        "observed_order_count": 23,
        "observed_order_qty_kg": 1_320_000,
        "replayed_pulled_qty_kg": 1_320_000,
        "replayed_shipped_qty_kg": 1_320_000,
        "replayed_received_reconciled_qty_kg": 1_320_000,
        "measured_received_qty_kg": 1_420_000,
        "dynamic_or_other_received_qty_kg": 100_000,
        "opening_pipeline_proof_rows": 23,
        "opening_pipeline_seeded_qty_kg": 1_320_000,
        "dynamic_pulled_qty_kg": 100_000,
        "dynamic_shipped_qty_kg": 100_000,
        "non_target_graph_and_order_book_preserved": True,
        "resolved_warmup_days": 0,
        "resolved_initial_state_scale": 1,
        "resolved_seed_open_orders_from_snapshot": True,
        "resolved_opening_open_order_source": "Extract_En_cours.xlsx",
        "resolved_seed_estimated_source_pipeline": True,
        "resolved_mrp_dynamic_requirement_pairs": "SDC-1450|item:021081",
        "resolved_mrp_smoothed_cover_requirement_pairs": "SDC-1450|item:021081",
        "resolved_external_procurement_seed_upstream_pipeline": True,
        "resolved_external_procurement_pipeline_fill_ratio": 1,
        "resolved_lot_trace_enabled": True,
    }
    gate = campaign.reference_flow_gate(baseline)
    assert gate["validated"] is True
    assert gate["replayed_pulled_qty_kg"] == 1_320_000
    assert gate["dynamic_pulled_qty_kg"] == 100_000
    assert gate["dynamic_or_other_received_qty_kg"] == 100_000
    baseline["replayed_pulled_qty_kg"] = 0
    assert campaign.reference_flow_gate(baseline)["validated"] is False


def test_receipt_reconciliation_does_not_credit_dynamic_excess_to_replay() -> None:
    initialized = [
        {"usable_day": 10, "seeded_pipeline_qty": 100},
        {"usable_day": 20, "seeded_pipeline_qty": 200},
    ]
    arrivals = [
        {"day": 10, "arrived_qty": 150},
        {"day": 20, "arrived_qty": 200},
    ]
    rows, replayed = campaign.reconcile_replayed_receipts(initialized, arrivals)
    assert replayed == 300
    assert sum(float(row["dynamic_or_other_arrival_qty_kg"]) for row in rows) == 50


def test_supplier_ranking_does_not_call_zero_product_effect_resilience() -> None:
    summaries = [
        {
            "scenario_id": f"{supplier}-case",
            "scope_id": supplier,
            "mechanism": "delivery_delay",
            "product_on_due_delta_vs_paired_baseline_mean": 0.0,
            "product_backlog_qty_days_delta_vs_paired_baseline_mean": 0.0,
            "overlay_quantity_loss_kg_mean": 0.0,
            "overlay_weighted_usable_delay_days_mean": 90.0,
        }
        for supplier in campaign.SUPPLIER_IDS
    ]
    audit = campaign.audit_observed_order_book(
        campaign.observed_orders(_actual_graph())
    )
    ranking = campaign.supplier_criticality_rows(summaries, audit)
    assert ranking[0]["supplier_id"] == "SDC-VD0960508A"
    assert all(
        row["interpretation_status"]
        == "order_book_exposure_only_downstream_effect_masked_by_state"
        for row in ranking
    )


def test_confirmation_selection_prefers_distinct_mechanisms_and_outcomes() -> None:
    scenarios = campaign.build_scenarios()
    scope = "SDC-VD0960508A"
    rows = []
    for index, scenario in enumerate(
        item for item in scenarios if item.scope_id == scope and not item.is_baseline
    ):
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "product_on_due_delta_vs_paired_baseline": -0.1 + index / 10_000,
                "product_backlog_qty_days_delta_vs_paired_baseline": 1000 - index,
                "overlay_quantity_loss_kg": 100 - index,
                "overlay_weighted_usable_delay_days": 0,
                "simulation_outcome_sha256": f"outcome-{scenario.mechanism}",
            }
        )
    selected = campaign.select_confirmation_scenarios(
        rows, scenarios, top_per_scope=3
    )
    selected_scope = [item for item in selected if item.scope_id == scope]
    assert len(selected_scope) == 3
    assert len({item.mechanism for item in selected_scope}) == 3


def test_required_quality_anchors_bypass_outcome_deduplication() -> None:
    scenarios = campaign.build_scenarios()
    selected = [
        _scenario("all_021081", "delivery_delay", 180.0),
        _scenario("SDC-VD0960508A", "delivery_delay", 180.0),
    ]
    anchored, added = campaign.add_required_scenarios(selected, scenarios)
    ids = {scenario.scenario_id for scenario in anchored}
    assert set(campaign.REQUIRED_QUALITY_ANCHOR_IDS) <= ids
    assert added == 2
    anchored_again, added_again = campaign.add_required_scenarios(
        anchored, scenarios
    )
    assert anchored_again == anchored
    assert added_again == 0


def test_resume_reuses_completed_metric_without_engine_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = campaign.build_scenarios()[0]
    metric_path = tmp_path / "metrics.csv"
    campaign.write_csv(
        metric_path,
        [
            {
                "state_regime": "observed_2025",
                "scenario_id": baseline.scenario_id,
                "seed": 421081,
                "valid": True,
            }
        ],
    )

    def fail_if_called(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("resume should not rerun a completed case")

    monkeypatch.setattr(campaign, "run_case", fail_if_called)
    rows = campaign._run_cases(
        source_graph={},
        source_graph_path=tmp_path / "graph.json",
        engine=tmp_path / "engine.py",
        profile_args=(),
        output_root=tmp_path,
        scenarios=[baseline],
        seeds=[421081],
        stage="resume_test",
        days=720,
        workers=1,
        retention="summary",
        metric_path=metric_path,
        opening_order_risk_mode="engine",
        state_regime=campaign.StateRegime(
            regime_id="observed_2025",
            label="observed",
            evidence_class="observed_2025_snapshot_state",
            opening_stock_qty_kg=1_142_100,
            stock_scale=1.0,
        ),
        measurement_start_stock_scale_csv=None,
        resume=True,
    )
    assert len(rows) == 1
    assert rows[0]["scenario_id"] == baseline.scenario_id


def test_cli_refuses_horizon_that_omits_planned_usable_receipts() -> None:
    args = campaign.parse_args(["--days", "262", "--prepare-only"])
    assert args.days == 262
    with pytest.raises(ValueError, match="--days must be"):
        campaign.main(["--days", "261", "--prepare-only"])
    assert campaign.parse_args([]).opening_order_risk_mode == "engine"
    assert campaign.parse_args(["--resume"]).resume is True
    assert (
        campaign.parse_args(["--quality-anchors-only"]).quality_anchors_only
        is True
    )


def test_intermediate_measurement_uses_opening_output_lot_at_sdc() -> None:
    events = [
        {
            "event_type": "opening_stock",
            "node_id": "SDC-1450",
            "item_id": "item:773474",
            "qty": 9_600_000,
        },
        {
            "event_type": "opening_stock",
            "node_id": "M-1430",
            "item_id": "item:773474",
            "qty": 14_593_000,
        },
    ]
    assert campaign.intermediate_measurement_start_qty(
        node_id="SDC-1450",
        adjustment_rows=[],
        opening_lot_events=events,
        input_stock_rows=[],
    ) == 9_600_000
    assert campaign.intermediate_measurement_start_qty(
        node_id="M-1430",
        adjustment_rows=[],
        opening_lot_events=events,
        input_stock_rows=[],
    ) == 14_593_000


def test_intermediate_measurement_adjustment_is_authoritative() -> None:
    assert campaign.intermediate_measurement_start_qty(
        node_id="SDC-1450",
        adjustment_rows=[
            {"node_id": "SDC-1450", "stock_after_qty": 1234}
        ],
        opening_lot_events=[
            {
                "event_type": "opening_stock",
                "node_id": "SDC-1450",
                "item_id": "item:773474",
                "qty": 9_600_000,
            }
        ],
        input_stock_rows=[],
    ) == 1234


def test_773474_production_separates_dynamic_and_already_open_order() -> None:
    events = [
        *(
            {
                "event_type": "production_output",
                "node_id": "SDC-1450",
                "item_id": "item:773474",
                "qty": 3_200_000,
            }
            for _ in range(9)
        ),
        {
            "event_type": "opening_production_order",
            "node_id": "SDC-1450",
            "item_id": "item:773474",
            "qty": 3_200_000,
        },
    ]
    quantities = campaign.intermediate_production_supply_quantities(events)
    assert quantities["dynamic_production_qty_g"] == 28_800_000
    assert quantities["opening_production_order_receipt_qty_g"] == 3_200_000
    assert quantities["total_production_supply_qty_g"] == 32_000_000


def test_extract_case_loads_filtered_lot_events_before_using_them(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case"
    summary = case_dir / "summaries" / "first_simulation_summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text("{}", encoding="utf-8")
    data_dir = case_dir / "data"
    data_dir.mkdir()
    campaign.write_csv(
        data_dir / "production_lot_events.csv",
        [
            {
                "event_type": "opening_stock",
                "node_id": "SDC-1450",
                "item_id": "item:773474",
                "qty": 9_600_000,
            },
            {
                "event_type": "opening_stock",
                "node_id": "M-1430",
                "item_id": "item:773474",
                "qty": 14_593_000,
            },
            {
                "event_type": "production_output",
                "node_id": "SDC-1450",
                "item_id": "item:773474",
                "qty": 3_200_000,
            },
            {
                "event_type": "opening_production_order",
                "node_id": "SDC-1450",
                "item_id": "item:773474",
                "qty": 3_200_000,
            },
        ],
    )
    row = campaign.extract_case(
        case_dir=case_dir,
        scenario=campaign.build_scenarios()[0],
        seed=1,
        stage="extract_regression",
        days=720,
        overlay_ledger=[],
        overlay_audit={},
    )
    assert row["intermediate_773474_measurement_start_total_qty_g"] == 24_193_000
    assert row["intermediate_773474_dynamic_production_qty_g"] == 3_200_000
    assert (
        row["intermediate_773474_opening_production_order_receipt_qty_g"]
        == 3_200_000
    )
    assert row["intermediate_773474_total_production_supply_qty_g"] == 6_400_000
