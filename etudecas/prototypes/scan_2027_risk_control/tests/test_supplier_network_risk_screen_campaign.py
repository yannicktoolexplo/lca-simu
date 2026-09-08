from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    industrial_supply_bilan_dashboard as industrial_dashboard,
    supplier_network_risk_screen_campaign as network,
)


REFERENCE = network.DEFAULT_REFERENCE_RUN


@pytest.fixture(scope="module")
def scope():
    if not REFERENCE.exists():
        pytest.skip("local V10 reference artifact is unavailable")
    graph = json.loads(network.DEFAULT_GRAPH.read_text(encoding="utf-8"))
    with (REFERENCE / "data" / "production_supplier_shipments_daily.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        shipments = list(csv.DictReader(stream))
    lanes = network.discover_active_lanes(
        graph=graph, shipment_rows=shipments, days=720
    )
    core = network.campaign_core
    original = {
        "CHAINS": core.CHAINS,
        "CHAIN_BY_ID": core.CHAIN_BY_ID,
        "MECHANISMS": core.MECHANISMS,
        "MECHANISM_BY_KEY": core.MECHANISM_BY_KEY,
        "INCIDENT_START_DAY": core.INCIDENT_START_DAY,
        "INCIDENT_DURATION_DAYS": core.INCIDENT_DURATION_DAYS,
    }
    network.configure_campaign_core(lanes)
    try:
        yield graph, lanes
    finally:
        for name, value in original.items():
            setattr(core, name, value)


def test_v10_scope_has_18_active_lanes_and_four_common_window_gaps(scope):
    _graph, lanes = scope
    assert len(lanes) == 18
    assert len({lane.chain.affected_lanes[0].supplier_id for lane in lanes}) == 16
    assert all(lane.chain.component_label != "021081" for lane in lanes)
    assert sum(lane.common_window_shipped_qty <= 0 for lane in lanes) == 4
    assert all(lane.active_window_shipped_qty > 0 for lane in lanes)
    assert all(lane.active_window_pulled_qty > 0 for lane in lanes)
    assert all(
        lane.active_window_end_day - lane.active_window_start_day + 1 == 180
        for lane in lanes
    )


def test_v10_active_scope_exactly_matches_final_v8_audit(scope):
    _graph, lanes = scope
    path = network.DEFAULT_SCOPE_AUDIT / "supplier_lane_scope.csv"
    if not path.exists():
        pytest.skip("final v8 scope audit is unavailable")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        audit = network.validate_scope_audit_crosscheck(
            lanes, list(csv.DictReader(stream))
        )
    assert audit["audit_lane_count"] == 33
    assert audit["audited_active_lane_count"] == 18
    assert audit["exact_active_scope_match"]


def test_complete_design_is_145_unique_scenarios(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    assert len(scenarios) == 145
    assert len({scenario.scenario_id for scenario in scenarios}) == 145
    stressed = [scenario for scenario in scenarios if not scenario.is_campaign_baseline]
    assert {scenario.mechanism_key for scenario in stressed} == {
        "transport_delay",
        "supply_availability",
        "quality_hold",
        "quality_yield",
    }
    assert all(
        sum(scenario.chain_id == lane.chain.chain_id for scenario in stressed) == 8
        for lane in lanes
    )


def test_v4_main_run_budget_is_exactly_145_1110_1255(scope):
    _graph, lanes = scope
    seeds = network.campaign_core.parse_seeds(network.DEFAULT_CONFIRMATION_SEEDS)
    counts = network.planned_run_counts(
        active_lane_count=len(lanes), confirmation_seed_count=len(seeds)
    )
    assert len(seeds) == 30
    assert counts == {
        "smoke": 5,
        "screening": 145,
        "confirmation_baseline": 30,
        "confirmation_stress": 1080,
        "confirmation": 1110,
        "full": 1255,
    }


def test_multi_lane_supplier_common_cause_is_separate_16_case_design(scope):
    _graph, lanes = scope
    with (REFERENCE / "data" / "production_supplier_shipments_daily.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        shipments = list(csv.DictReader(stream))
    rows, manifest = network.multi_lane_common_cause_design(
        lanes=lanes,
        shipment_rows=shipments,
        days=720,
        screening_seed=network.DEFAULT_SCREENING_SEED,
    )
    assert len(rows) == 16
    assert manifest["supplier_count"] == 2
    assert set(manifest["supplier_ids"]) == {"SDC-VD0519670A", "SDC-VD0520132A"}
    assert all(row["execution_status"] == "planned_separate_not_executed" for row in rows)


def test_smoke_is_one_baseline_plus_two_modes_on_two_largest_lanes(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    smoke = network.select_smoke_scenarios(lanes, scenarios, lane_count=2)
    assert len(smoke) == 5
    assert sum(scenario.is_campaign_baseline for scenario in smoke) == 1
    stressed = [scenario for scenario in smoke if not scenario.is_campaign_baseline]
    assert {scenario.mechanism_key for scenario in stressed} == {
        "transport_delay",
        "supply_availability",
    }
    assert {scenario.level_code for scenario in stressed} == {"severe"}
    assert {
        network.campaign_core.CHAIN_BY_ID[scenario.chain_id].component_label
        for scenario in stressed
    } == {"042342", "338929"}


def test_targeted_smoke_can_select_338929_and_344135(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    smoke = network.select_smoke_scenarios(
        lanes,
        scenarios,
        lane_count=2,
        component_labels=("338929", "344135"),
    )
    assert len(smoke) == 5
    stressed = [item for item in smoke if not item.is_campaign_baseline]
    assert {
        network.campaign_core.CHAIN_BY_ID[item.chain_id].component_label
        for item in stressed
    } == {"338929", "344135"}
    assert {item.mechanism_key for item in stressed} == {
        "transport_delay",
        "supply_availability",
    }
    assert {item.level_code for item in stressed} == {"severe"}

    all_levels = network.select_smoke_scenarios(
        lanes,
        scenarios,
        lane_count=2,
        component_labels=("338929", "344135"),
        include_all_levels=True,
    )
    assert len(all_levels) == 9
    assert {item.level_code for item in all_levels[1:]} == {"modere", "severe"}
    assert {
        item.value
        for item in all_levels[1:]
        if item.mechanism_key == "supply_availability"
    } == {0.8, 0.5}


def test_risk_input_uses_each_lane_specific_180_day_window(scope, tmp_path: Path):
    _graph, lanes = scope
    reference_by_chain = {lane.chain.chain_id: lane for lane in lanes}
    scenarios = network.build_scenarios(lanes)
    scenario = next(
        item
        for item in scenarios
        if not item.is_campaign_baseline
        and item.chain_id == lanes[3].chain.chain_id
    )
    inputs = network._risk_inputs(
        tmp_path, [scenarios[0], scenario], 720, reference_by_chain
    )
    path, count = inputs[scenario.scenario_id]
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    reference = reference_by_chain[scenario.chain_id]
    assert count == 1
    assert int(rows[0]["start_day"]) == reference.active_window_start_day
    assert int(rows[0]["end_day"]) == reference.active_window_end_day
    assert int(rows[0]["end_day"]) - int(rows[0]["start_day"]) + 1 == 180


def test_network_command_forces_lot_trace_last_without_changing_v4(tmp_path: Path):
    core = network.campaign_core
    config = core.RunConfig(
        repo_root=tmp_path,
        output_dir=tmp_path / "out",
        engine=tmp_path / "engine.py",
        graph=tmp_path / "graph.json",
        supplier_floors=tmp_path / "floors.csv",
        factory_capacities=None,
        profile_args=("--no-lot-trace",),
        scenario_id="scn:BASE",
        days=720,
        retention="summary",
        physical_capacity_by_lane={},
    )
    command = network.build_network_engine_command(
        config,
        case_dir=tmp_path / "case",
        seed=7,
        risk_csv=tmp_path / "risk.csv",
    )
    assert "--no-lot-trace" in command
    assert command[-1] == "--lot-trace"
    assert command.index("--no-lot-trace") < len(command) - 1
    # The reusable V4 builder remains untouched and still ends without the
    # network-only opt-in.
    v4_command = core.build_engine_command(
        config,
        case_dir=tmp_path / "case",
        seed=7,
        risk_csv=tmp_path / "risk.csv",
    )
    assert v4_command[-1] == str(tmp_path / "risk.csv")
    assert v4_command[-1] != "--lot-trace"


def test_lot_trace_mode_is_identical_inside_each_paired_seed_block():
    screening_seeds = (340281,)
    assert network.lot_trace_required_for_pair(
        stage="screening", seed=340281, seeds=screening_seeds
    )
    assert network.lot_trace_required_for_pair(
        stage="smoke", seed=340281, seeds=screening_seeds
    )

    confirmation_seeds = (340282, 340283, 340284)
    assert network.lot_trace_required_for_pair(
        stage="confirmation", seed=340282, seeds=confirmation_seeds
    )
    assert not network.lot_trace_required_for_pair(
        stage="confirmation", seed=340283, seeds=confirmation_seeds
    )
    assert not network.lot_trace_required_for_pair(
        stage="confirmation", seed=340284, seeds=confirmation_seeds
    )


def test_reference_lot_proof_audits_resolved_trace_mode(tmp_path: Path):
    scenario = network.campaign_core.Scenario(
        scenario_id="baseline_nominal",
        execution_scenario_id="scn:BASE",
        chain_id="campaign",
        mechanism_key="baseline",
        level_index=0,
        level_code="reference",
        level_label="reference",
        value=0.0,
        unit="none",
        target_product_id="268091",
        client_node_id="C-XXXXX",
        is_campaign_baseline=True,
    )
    summary = tmp_path / "summaries" / "first_simulation_summary.json"
    summary.parent.mkdir(parents=True)
    summary.write_text(
        json.dumps({"policy": {"lot_trace_enabled": True}}), encoding="utf-8"
    )
    proof = network.extract_lot_impact_proof(
        case_dir=tmp_path,
        scenario=scenario,
        graph={},
        stage="smoke",
        lot_trace_required=True,
    )
    assert proof["lot_proof_status"] == "not_applicable_simulated_reference"
    assert proof["resolved_lot_trace_enabled"] is True
    assert proof["lot_trace_runtime_gate_pass"] is True


def _write_lot_csv(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_capacity_profile(
    path: Path,
    *,
    supplier_id: str,
    item_id: str,
    active_start: int,
    active_end: int,
    nominal: float,
    stressed: float,
) -> None:
    _write_lot_csv(
        path,
        [
            {
                "day": day,
                "node_id": supplier_id,
                "item_id": item_id,
                "capacity_qty_per_day": (
                    stressed if active_start <= day <= active_end else nominal
                ),
            }
            for day in range(720)
        ],
    )


def test_344135_capacity_gate_uses_j131_j310_and_alias(scope, tmp_path: Path):
    _graph, lanes = scope
    reference = next(
        item for item in lanes if item.chain.component_label == "344135"
    )
    assert (reference.active_window_start_day, reference.active_window_end_day) == (
        131,
        310,
    )
    scenario = next(
        item
        for item in network.build_scenarios(lanes)
        if item.chain_id == reference.chain.chain_id
        and item.mechanism_key == "supply_availability"
        and item.level_code == "modere"
    )
    assert scenario.value == pytest.approx(0.8)
    lane = reference.chain.affected_lanes[0]
    _write_capacity_profile(
        tmp_path / "data" / "production_supplier_capacity_daily.csv",
        supplier_id=lane.supplier_id,
        item_id=lane.item_id,
        active_start=131,
        active_end=310,
        nominal=300_000.0,
        stressed=240_000.0,
    )
    row = {"applied_physical_capacity_matches_expected": False}
    network.attach_lane_specific_capacity_validation(
        row,
        case_dir=tmp_path,
        scenario=scenario,
        reference_by_chain={item.chain.chain_id: item for item in lanes},
        physical_capacity_by_lane_map={lane.key: 300_000.0},
        days=720,
    )
    assert row["network_capacity_validation_start_day"] == 131
    assert row["network_capacity_validation_end_day"] == 310
    assert row["network_expected_active_capacity_min_qty_per_day"] == 240_000.0
    assert row["network_observed_active_capacity_min_qty_per_day"] == 240_000.0
    assert row["network_observed_active_capacity_max_qty_per_day"] == 240_000.0
    assert row["network_outside_active_window_capacity_matches_nominal"]
    assert row["applied_physical_capacity_matches_expected"]


def test_338929_capacity_gate_exercises_window_outside_common_calendar(
    scope, tmp_path: Path
):
    _graph, lanes = scope
    reference = next(
        item for item in lanes if item.chain.component_label == "338929"
    )
    assert (reference.active_window_start_day, reference.active_window_end_day) == (
        228,
        407,
    )
    scenario = next(
        item
        for item in network.build_scenarios(lanes)
        if item.chain_id == reference.chain.chain_id
        and item.mechanism_key == "supply_availability"
        and item.level_code == "severe"
    )
    assert scenario.value == pytest.approx(0.5)
    lane = reference.chain.affected_lanes[0]
    capacity_path = tmp_path / "data" / "production_supplier_capacity_daily.csv"
    _write_capacity_profile(
        capacity_path,
        supplier_id=lane.supplier_id,
        item_id=lane.item_id,
        active_start=228,
        active_end=407,
        nominal=75_000.0,
        stressed=37_500.0,
    )
    row = {"applied_physical_capacity_matches_expected": True}
    network.attach_lane_specific_capacity_validation(
        row,
        case_dir=tmp_path,
        scenario=scenario,
        reference_by_chain={item.chain.chain_id: item for item in lanes},
        physical_capacity_by_lane_map={lane.key: 75_000.0},
        days=720,
    )
    assert row["network_expected_active_capacity_min_qty_per_day"] == 37_500.0
    assert row["network_observed_active_capacity_min_qty_per_day"] == 37_500.0
    assert row["applied_physical_capacity_matches_expected"]

    # Regression: the old J45-J224 audit would see only the nominal 75k and
    # could pass.  The network gate must reject a non-degraded active window.
    _write_capacity_profile(
        capacity_path,
        supplier_id=lane.supplier_id,
        item_id=lane.item_id,
        active_start=228,
        active_end=407,
        nominal=75_000.0,
        stressed=75_000.0,
    )
    network.attach_lane_specific_capacity_validation(
        row,
        case_dir=tmp_path,
        scenario=scenario,
        reference_by_chain={item.chain.chain_id: item for item in lanes},
        physical_capacity_by_lane_map={lane.key: 75_000.0},
        days=720,
    )
    assert not row["applied_physical_capacity_matches_expected"]


def test_lot_proof_starts_from_tagged_receipt_and_traverses_untagged_children(
    scope, tmp_path: Path
):
    graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario = next(
        item
        for item in scenarios
        if not item.is_campaign_baseline
        and item.mechanism_key == "transport_delay"
        and item.level_code == "severe"
    )
    chain = network.campaign_core.CHAIN_BY_ID[scenario.chain_id]
    lane = chain.affected_lanes[0]
    case_dir = tmp_path / "cases" / scenario.scenario_id / "seed_1"
    risk_id = f"{scenario.scenario_id}__lane1"
    events = [
        {
            "event_id": "E-R",
            "day": 10,
            "event_type": "lane_receipt",
            "lot_id": "R",
            "node_id": lane.dst_node_id,
            "item_id": lane.item_id,
            "qty": 100,
            "uom": "KG",
            "source_type": "lane_receipt",
            "risk_event_ids": risk_id,
        },
        {
            "event_id": "E-I",
            "day": 11,
            "event_type": "production_output",
            "lot_id": "I",
            "node_id": lane.dst_node_id,
            "item_id": "item:INTERMEDIATE",
            "qty": 80,
            "uom": "KG",
            "source_type": "production_output",
            "risk_event_ids": "",
        },
        {
            "event_id": "E-F",
            "day": 12,
            "event_type": "production_output",
            "lot_id": "F",
            "node_id": lane.dst_node_id,
            "item_id": f"item:{chain.target_product_id}",
            "qty": 50,
            "uom": "UN",
            "source_type": "production_output",
            "risk_event_ids": "",
        },
        {
            "event_id": "E-C",
            "day": 13,
            "event_type": "lane_receipt",
            "lot_id": "C",
            "node_id": chain.client_node_id,
            "item_id": f"item:{chain.target_product_id}",
            "qty": 50,
            "uom": "UN",
            "source_type": "lane_receipt",
            "risk_event_ids": "",
        },
        {
            "event_id": "E-D",
            "day": 14,
            "event_type": "demand_service",
            "lot_id": "C",
            "node_id": chain.client_node_id,
            "item_id": f"item:{chain.target_product_id}",
            "qty": 40,
            "uom": "UN",
            "source_type": "lane_receipt",
            "risk_event_ids": "",
        },
    ]
    genealogy = [
        {"day": 11, "link_type": "production", "parent_lot_id": "R", "child_lot_id": "I"},
        {"day": 12, "link_type": "production", "parent_lot_id": "I", "child_lot_id": "F"},
        {"day": 13, "link_type": "transport", "parent_lot_id": "F", "child_lot_id": "C"},
    ]
    _write_lot_csv(case_dir / "data" / "production_lot_events.csv", events)
    _write_lot_csv(case_dir / "data" / "production_lot_genealogy.csv", genealogy)
    proof = network.extract_lot_impact_proof(
        case_dir=case_dir,
        scenario=scenario,
        graph=graph,
        stage="confirmation",
    )
    assert proof["lot_proof_status"] == "valid_genealogy_traversal"
    assert proof["impacted_receipt_lot_count"] == 1
    assert proof["impacted_receipt_qty"] == pytest.approx(100)
    assert proof["impacted_intermediate_descendant_lot_count"] == 1
    assert proof["impacted_finished_descendant_lot_count"] == 2
    assert proof["impacted_finished_descendant_qty_touched_upper"] == pytest.approx(100)
    assert proof["impacted_client_delivery_descendant_lot_count"] == 1
    assert proof["impacted_client_delivery_qty_touched_upper"] == pytest.approx(40)
    assert proof["impacted_genealogy_max_depth"] == 3
    assert proof["lot_lineage_horizon_status"] == "genealogy_reaches_client_delivery"
    assert proof["lot_proof_detail_retained"] is True
    assert (case_dir / "proofs" / "impacted_genealogy.csv").is_file()
    assert (case_dir / "proofs" / "impacted_client_deliveries.csv").is_file()


def test_screening_lot_proof_keeps_only_compact_summary(scope, tmp_path: Path):
    graph, lanes = scope
    scenario = next(
        item for item in network.build_scenarios(lanes) if not item.is_campaign_baseline
    )
    chain = network.campaign_core.CHAIN_BY_ID[scenario.chain_id]
    lane = chain.affected_lanes[0]
    case_dir = tmp_path / "cases" / scenario.scenario_id / "seed_1"
    _write_lot_csv(
        case_dir / "data" / "production_lot_events.csv",
        [
            {
                "day": 1,
                "event_type": "lane_receipt",
                "source_type": "lane_receipt",
                "lot_id": "ROOT",
                "node_id": lane.dst_node_id,
                "item_id": lane.item_id,
                "qty": 1,
                "uom": "KG",
                "risk_event_ids": f"{scenario.scenario_id}__lane1",
            }
        ],
    )
    _write_lot_csv(
        case_dir / "data" / "production_lot_genealogy.csv",
        [{"day": 1, "parent_lot_id": "OTHER", "child_lot_id": "OTHER-2"}],
    )
    proof = network.extract_lot_impact_proof(
        case_dir=case_dir,
        scenario=scenario,
        graph=graph,
        stage="screening",
    )
    assert proof["impacted_receipt_lot_count"] == 1
    assert proof["lot_proof_detail_retained"] is False
    assert (case_dir / "proofs" / "lot_impact_summary.json").is_file()
    assert not (case_dir / "proofs" / "impacted_genealogy.csv").exists()


def _write_lot_runtime_audits(
    *,
    case_dir: Path,
    scenario,
    lane,
    arrival_day: int,
) -> str:
    risk_id = f"{scenario.scenario_id}__lane1"
    (case_dir / "summaries").mkdir(parents=True, exist_ok=True)
    (case_dir / "summaries" / "first_simulation_summary.json").write_text(
        json.dumps({"policy": {"lot_trace_enabled": True}}), encoding="utf-8"
    )
    _write_lot_csv(
        case_dir / "data" / "supplier_risk_events_applied_daily.csv",
        [
            {
                "day": 1,
                "supplier_id": lane.supplier_id,
                "dst_node_id": lane.dst_node_id,
                "item_id": lane.item_id,
                "event_ids": risk_id,
            }
        ],
    )
    _write_lot_csv(
        case_dir / "data" / "production_supplier_shipments_daily.csv",
        [
            {
                "day": 1,
                "shipment_id": "SHIP-1",
                "risk_event_ids": risk_id,
                "src_node_id": lane.supplier_id,
                "dst_node_id": lane.dst_node_id,
                "item_id": lane.item_id,
                "shipped_qty": 10,
                "pulled_qty": 10,
                "arrival_day": arrival_day,
                "uom": "KG",
            }
        ],
    )
    return risk_id


def test_lot_root_gate_rejects_missing_tagged_usable_receipt(scope, tmp_path: Path):
    graph, lanes = scope
    scenario = next(
        item
        for item in network.build_scenarios(lanes)
        if not item.is_campaign_baseline
        and item.mechanism_key == "transport_delay"
        and item.level_code == "severe"
    )
    lane = network.campaign_core.CHAIN_BY_ID[scenario.chain_id].affected_lanes[0]
    case_dir = tmp_path / "cases" / scenario.scenario_id / "seed_1"
    _write_lot_runtime_audits(
        case_dir=case_dir, scenario=scenario, lane=lane, arrival_day=20
    )
    _write_lot_csv(
        case_dir / "data" / "production_lot_events.csv",
        [
            {
                "day": 1,
                "event_type": "opening_stock",
                "lot_id": "UNRELATED",
                "node_id": lane.dst_node_id,
                "item_id": lane.item_id,
                "qty": 1,
                "risk_event_ids": "",
            }
        ],
    )
    _write_lot_csv(
        case_dir / "data" / "production_lot_genealogy.csv",
        [{"day": 1, "parent_lot_id": "OTHER", "child_lot_id": "OTHER-2"}],
    )
    proof = network.extract_lot_impact_proof(
        case_dir=case_dir,
        scenario=scenario,
        graph=graph,
        stage="screening",
        days=720,
    )
    assert proof["resolved_lot_trace_enabled"] is True
    assert proof["lot_root_gate_required"] is True
    assert proof["lot_root_gate_pass"] is False
    assert proof["lot_proof_valid"] is False
    assert proof["lot_proof_status"] == "invalid_missing_tagged_usable_receipt_root"


def test_quality_hold_proof_reconstructs_wait_without_claiming_native_quarantine(
    scope, tmp_path: Path
):
    graph, lanes = scope
    scenario = next(
        item
        for item in network.build_scenarios(lanes)
        if not item.is_campaign_baseline
        and item.mechanism_key == "quality_hold"
        and item.level_code == "severe"
    )
    lane = network.campaign_core.CHAIN_BY_ID[scenario.chain_id].affected_lanes[0]
    case_dir = tmp_path / "cases" / scenario.scenario_id / "seed_1"
    risk_id = _write_lot_runtime_audits(
        case_dir=case_dir, scenario=scenario, lane=lane, arrival_day=140
    )
    _write_lot_csv(
        case_dir / "data" / "production_lot_events.csv",
        [
            {
                "day": 140,
                "event_type": "lane_receipt",
                "source_type": "lane_receipt",
                "lot_id": "ROOT",
                "shipment_id": "SHIP-1",
                "node_id": lane.dst_node_id,
                "item_id": lane.item_id,
                "qty": 10,
                "uom": "KG",
                "risk_event_ids": risk_id,
            }
        ],
    )
    _write_lot_csv(
        case_dir / "data" / "production_lot_genealogy.csv",
        [{"day": 1, "parent_lot_id": "OTHER", "child_lot_id": "OTHER-2"}],
    )
    proof = network.extract_lot_impact_proof(
        case_dir=case_dir,
        scenario=scenario,
        graph=graph,
        stage="screening",
        days=720,
    )
    assert proof["lot_proof_valid"] is True
    assert proof["impacted_receipt_semantics"].startswith("risk-tagged usable receipt")
    assert proof["quality_hold_reconstructed_interval_count"] == 1
    assert proof["quality_hold_interval_status"] == (
        "reconstructed_interval_not_native_quarantine_stock_state"
    )
    wait_path = case_dir / "proofs" / "quality_hold_wait_intervals.csv"
    assert wait_path.is_file()
    with wait_path.open(newline="", encoding="utf-8-sig") as stream:
        wait = next(csv.DictReader(stream))
    assert int(wait["usable_receipt_day"]) == 140
    assert int(wait["estimated_physical_arrival_day"]) == 140 - int(scenario.value)


def test_global_severity_tie_break_does_not_use_raw_stock_units():
    base = {
        "target_on_due_date_proxy_delta_vs_paired_baseline_mean": 0,
        "incremental_target_backlog_qty_days_mean": 0,
        "target_production_shortfall_vs_paired_baseline_mean": 0,
        "component_days_at_zero_delta_vs_paired_baseline_mean": 0,
        "component_days_below_safety_delta_vs_paired_baseline_mean": 0,
        "active_window_flow_coverage_vs_paired_baseline_mean": 1,
    }
    kilograms = {**base, "scenario_id": "same", "component_input_stock_min_delta_vs_paired_baseline_mean": -1}
    units = {**base, "scenario_id": "same", "component_input_stock_min_delta_vs_paired_baseline_mean": -1_000_000}
    assert network._severity_key(kilograms) == network._severity_key(units)


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        (
            {"target_on_due_date_proxy_delta_vs_paired_baseline": -0.01},
            "effet_mesure_sur_le_service_client",
        ),
        (
            {"target_production_shortfall_vs_paired_baseline": 100.0},
            "effet_mesure_sur_la_production_mais_pas_sur_le_service_client",
        ),
        (
            {"active_window_flow_coverage_vs_paired_baseline": 0.8},
            "effet_amont_absorbe_avant_le_client",
        ),
        ({}, "stress_applique_sans_effet_mesurable"),
    ],
)
def test_effect_status_is_explicit_and_keeps_customer_production_stock_levels(
    updates, expected
):
    row = {
        "paired_baseline_active_window_flow_exercised": True,
        "target_on_due_date_proxy_delta_vs_paired_baseline": 0.0,
        "incremental_target_backlog_qty_days": 0.0,
        "target_backlog_end_qty": 0.0,
        "paired_baseline_target_backlog_end_qty": 0.0,
        "target_production_shortfall_vs_paired_baseline": 0.0,
        "paired_baseline_target_released_qty": 1_000.0,
        "active_window_flow_coverage_vs_paired_baseline": 1.0,
        "supplier_on_due_delta_vs_paired_baseline": 0.0,
        "component_arrived_qty_delta_vs_paired_baseline": 0.0,
        "paired_baseline_component_arrived_qty": 1_000.0,
        "component_input_stock_end_delta_vs_paired_baseline": 0.0,
        "paired_baseline_component_input_stock_end": 100.0,
    }
    row.update(updates)
    assert network.classify_effect(row) == expected


def test_supplier_and_failure_mode_rankings_are_separate():
    rows = [
        {
            "scenario_id": "a_delay",
            "chain_id": "a",
            "supplier_id": "SUP-A",
            "item_id": "item:A",
            "dst_node_id": "M-1",
            "target_product_id": "268091",
            "failure_mode": "transport_delay",
            "target_on_due_date_proxy_delta_vs_paired_baseline_mean": -0.2,
            "incremental_target_backlog_qty_days_mean": 100.0,
            "target_production_shortfall_vs_paired_baseline_mean": 10.0,
            "effect_status": "effet_mesure_sur_le_service_client",
        },
        {
            "scenario_id": "b_quality",
            "chain_id": "b",
            "supplier_id": "SUP-B",
            "item_id": "item:B",
            "dst_node_id": "M-2",
            "target_product_id": "268967",
            "failure_mode": "quality_yield",
            "target_on_due_date_proxy_delta_vs_paired_baseline_mean": -0.1,
            "incremental_target_backlog_qty_days_mean": 50.0,
            "target_production_shortfall_vs_paired_baseline_mean": 5.0,
            "effect_status": "effet_mesure_sur_le_service_client",
        },
    ]
    suppliers = network.rank_suppliers(rows)
    modes = network.summarize_failure_modes(rows)
    assert [row["supplier_id"] for row in suppliers] == ["SUP-A", "SUP-B"]
    assert {row["failure_mode"] for row in modes} == {
        "transport_delay",
        "quality_yield",
    }
    assert all("pas_une_probabilite" in row["ranking_meaning"] for row in suppliers)


def test_ten_seeds_remains_preselection_even_with_ten_of_ten_presence(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    chain_by_id = {lane.chain.chain_id: lane.chain for lane in lanes}
    chosen = []
    seen_suppliers = set()
    for scenario in scenarios:
        if scenario.is_campaign_baseline or scenario.level_code != "severe":
            continue
        supplier = chain_by_id[scenario.chain_id].affected_lanes[0].supplier_id
        if supplier in seen_suppliers:
            continue
        seen_suppliers.add(supplier)
        chosen.append(scenario)
        if len(chosen) == 4:
            break
    rows = []
    for seed in range(10):
        for index, scenario in enumerate(chosen):
            rows.append(
                {
                    "seed": seed,
                    "scenario_id": scenario.scenario_id,
                    "target_on_due_date_proxy_delta_vs_paired_baseline": -0.4 + index * 0.1,
                    "incremental_target_backlog_qty_days": 400.0 - index * 100.0,
                    "target_production_shortfall_vs_paired_baseline": 40.0 - index * 10.0,
                    "component_input_stock_min_delta_vs_paired_baseline": -40.0 + index * 10.0,
                    "effect_status": "effet_mesure_sur_le_service_client",
                }
            )
    summaries = [
        network._raw_row_as_summary(
            row, scenario_by_id=scenario_by_id, chain_by_id=chain_by_id
        )
        for row in rows[:4]
    ]
    aggregate = network.rank_suppliers(
        summaries, evidence_stage="confirmation_10_realisations"
    )
    stability = network.confirmed_top3_stability(
        rows,
        scenario_by_id=scenario_by_id,
        chain_by_id=chain_by_id,
        aggregate_ranking=aggregate,
    )
    assert [row["top3_presence_seed_count"] for row in stability[:3]] == [10, 10, 10]
    assert not any(row["stable_confirmed_top3"] for row in stability)
    assert not any(row["top3_set_validated"] for row in stability)
    assert all(
        row["top3_status"] == "preselection_a_approfondir_30_graines"
        for row in stability[:3]
    )
    assert all(row["top3_presence_wilson95_lower"] < 0.90 for row in stability[:3])
    assert stability[3]["final_top3_rank"] == ""


def test_unstable_ten_seed_membership_is_still_only_a_preselection(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    chain_by_id = {lane.chain.chain_id: lane.chain for lane in lanes}
    chosen = []
    seen_suppliers = set()
    for scenario in scenarios:
        if scenario.is_campaign_baseline or scenario.level_code != "severe":
            continue
        supplier = chain_by_id[scenario.chain_id].affected_lanes[0].supplier_id
        if supplier not in seen_suppliers:
            seen_suppliers.add(supplier)
            chosen.append(scenario)
        if len(chosen) == 4:
            break
    rows = []
    for seed in range(10):
        for index, scenario in enumerate(chosen):
            severity_index = index
            if seed >= 7 and index == 2:
                severity_index = 4
            elif seed >= 7 and index == 3:
                severity_index = 2
            rows.append(
                {
                    "seed": seed,
                    "scenario_id": scenario.scenario_id,
                    "target_on_due_date_proxy_delta_vs_paired_baseline": -0.4 + severity_index * 0.1,
                    "incremental_target_backlog_qty_days": 400.0 - severity_index * 100.0,
                    "target_production_shortfall_vs_paired_baseline": 40.0 - severity_index * 10.0,
                    "component_input_stock_min_delta_vs_paired_baseline": -40.0 + severity_index * 10.0,
                    "effect_status": "effet_mesure_sur_le_service_client",
                }
            )
    aggregate = network.rank_suppliers(
        [
            network._raw_row_as_summary(
                row, scenario_by_id=scenario_by_id, chain_by_id=chain_by_id
            )
            for row in rows[:4]
        ],
        evidence_stage="confirmation_10_realisations",
    )
    stability = network.confirmed_top3_stability(
        rows,
        scenario_by_id=scenario_by_id,
        chain_by_id=chain_by_id,
        aggregate_ranking=aggregate,
    )
    assert not any(row["top3_set_validated"] for row in stability)
    assert all(row["final_top3_rank"] == "" for row in stability)
    assert all(
        row["top3_status"] == "preselection_a_approfondir_30_graines"
        for row in stability
        if row["aggregate_top3"]
    )


def test_partial_selection_would_keep_unselected_lanes_explicitly_screening_only(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    selected = []
    for lane in lanes[:12]:
        selected.append(
            next(
                scenario.scenario_id
                for scenario in scenarios
                if scenario.chain_id == lane.chain.chain_id
                and scenario.level_code == "severe"
            )
        )
    rows = network.lane_evidence_status_rows(
        lanes,
        selected_scenario_ids=selected,
        scenario_by_id=scenario_by_id,
        confirmation_seed_count=10,
    )
    assert sum(row["selected_for_confirmation"] for row in rows) == 12
    assert sum(row["evidence_stage"] == "screening_1_realisation" for row in rows) == 6
    assert all(
        row["eligible_for_final_top3"] == row["selected_for_confirmation"]
        for row in rows
    )


def test_final_confirmation_selection_covers_two_families_on_all_18_lanes(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    selected = network.select_predeclared_family_confirmation_scenarios(
        scenarios, lanes
    )
    assert network.DEFAULT_CONFIRMATION_TOP_LANES == 18
    assert len(selected) == 36
    assert {scenario_by_id[scenario_id].chain_id for scenario_id in selected} == {
        lane.chain.chain_id for lane in lanes
    }
    assert {scenario_by_id[scenario_id].mechanism_key for scenario_id in selected} == {
        "transport_delay",
        "supply_availability",
    }
    evidence = network.lane_evidence_status_rows(
        lanes,
        selected_scenario_ids=selected,
        scenario_by_id=scenario_by_id,
        confirmation_seed_count=10,
    )
    assert all(row["selected_for_confirmation"] for row in evidence)
    assert all(row["evidence_stage"] == "confirmation_10_realisations" for row in evidence)
    assert all(row["confirmed_mathematical_family_count"] == 2 for row in evidence)


def test_n30_summary_hides_p05_and_reports_std_bootstrap_and_units(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario = next(
        item
        for item in scenarios
        if not item.is_campaign_baseline
        and item.mechanism_key == "transport_delay"
        and item.level_code == "severe"
    )
    rows = [
        {
            "seed": seed,
            "stage": "confirmation",
            "scenario_id": scenario.scenario_id,
            "valid": True,
            "effect_status": "effet_mesure_sur_le_service_client",
            "target_on_due_date_proxy_delta_vs_paired_baseline": -seed / 10_000,
            "target_product_uom": "UN",
            "component_stock_uom": "KG",
        }
        for seed in range(30)
    ]
    summary = network.aggregate_scenarios(
        rows,
        [scenario],
        {lane.chain.chain_id: lane.chain for lane in lanes},
    )[0]
    field = "target_on_due_date_proxy_delta_vs_paired_baseline"
    assert summary["n_seeds"] == 30
    assert summary["empirical_p05_reporting_status"] == "not_reported_insufficient_n"
    assert f"{field}_p05" not in summary
    assert summary[f"{field}_sample_std"] > 0
    assert summary[f"{field}_bootstrap95_low"] <= summary[f"{field}_mean"]
    assert summary[f"{field}_bootstrap95_high"] >= summary[f"{field}_mean"]
    assert summary["target_product_uom"] == "UN"
    assert summary["component_stock_uom"] == "KG"
    assert summary["target_backlog_qty_days_unit"] == "UN_day"
    assert summary["cross_uom_aggregation_allowed"] is False


def test_n30_supplier_rank_bootstrap_is_deterministic_and_can_release_stable_priorities(
    scope,
):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    chain_by_id = {lane.chain.chain_id: lane.chain for lane in lanes}
    chosen = []
    seen_suppliers = set()
    for scenario in scenarios:
        if scenario.is_campaign_baseline or scenario.level_code != "severe":
            continue
        supplier = chain_by_id[scenario.chain_id].affected_lanes[0].supplier_id
        if supplier not in seen_suppliers:
            seen_suppliers.add(supplier)
            chosen.append(scenario)
        if len(chosen) == 4:
            break
    rows = []
    for seed in range(30):
        for index, scenario in enumerate(chosen):
            rows.append(
                {
                    "seed": seed,
                    "scenario_id": scenario.scenario_id,
                    "target_on_due_date_proxy_delta_vs_paired_baseline": -0.40 + index * 0.10,
                    "incremental_target_backlog_qty_days": 400.0 - index * 100.0,
                    "target_production_shortfall_ratio_vs_paired_baseline": 0.40 - index * 0.10,
                    "component_days_below_safety_delta_vs_paired_baseline": 40.0 - index * 10.0,
                    "effect_status": "effet_mesure_sur_le_service_client",
                }
            )
    aggregate = network.rank_suppliers(
        [
            network._raw_row_as_summary(
                row, scenario_by_id=scenario_by_id, chain_by_id=chain_by_id
            )
            for row in rows[:4]
        ],
        evidence_stage="confirmation_30_realisations",
    )
    first, first_separated = network.paired_seed_block_bootstrap_supplier_rank_intervals(
        rows,
        scenario_by_id=scenario_by_id,
        chain_by_id=chain_by_id,
        aggregate_ranking=aggregate,
        resamples=200,
    )
    second, second_separated = network.paired_seed_block_bootstrap_supplier_rank_intervals(
        rows,
        scenario_by_id=scenario_by_id,
        chain_by_id=chain_by_id,
        aggregate_ranking=aggregate,
        resamples=200,
    )
    assert first == second
    assert first_separated and second_separated
    assert first[2]["bootstrap_rank_ci95_high"] < first[3]["bootstrap_rank_ci95_low"]


def test_scientific_release_gates_require_30_good_baselines_pairing_and_29_flows(scope):
    _graph, lanes = scope
    scenarios = network.build_scenarios(lanes)
    scenario_by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    selected = network.select_predeclared_family_confirmation_scenarios(
        scenarios, lanes
    )
    rows = []
    for seed in range(30):
        rows.append(
            {
                "seed": seed,
                "scenario_id": "baseline_nominal",
                "valid": True,
                "j0_state_sha256": f"j0-{seed}",
                "input_sha256": "graph",
                "on_due_volume_proxy_268091": 0.96,
                "on_due_volume_proxy_268967": 0.97,
            }
        )
        for scenario_id in selected:
            rows.append(
                {
                    "seed": seed,
                    "scenario_id": scenario_id,
                    "valid": True,
                    "j0_state_sha256": f"j0-{seed}",
                    "input_sha256": "graph",
                    "paired_baseline_active_window_pulled_qty": 1.0,
                    "paired_baseline_active_window_shipped_qty": 1.0,
                }
            )
    audit = network.scientific_release_gate_audit(
        rows,
        selected_scenario_ids=selected,
        scenario_by_id=scenario_by_id,
    )
    assert audit["baseline_both_products_on_due_at_least_95_all_seeds_pass"]
    assert audit["all_metric_rows_valid_pass"]
    assert audit["j0_state_hash_pairing_100pct_pass"]
    assert audit["input_graph_hash_pairing_100pct_pass"]
    assert audit["active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass"]
    assert audit["all_release_gates_pass"]
    rows[0]["on_due_volume_proxy_268091"] = 0.94
    failed = network.scientific_release_gate_audit(
        rows,
        selected_scenario_ids=selected,
        scenario_by_id=scenario_by_id,
    )
    assert not failed["baseline_both_products_on_due_at_least_95_all_seeds_pass"]
    assert not failed["all_release_gates_pass"]


def test_summary_retention_has_no_heavy_case_csv_directory():
    smoke = (
        network.ARTIFACT_PARENT / "supplier_network_risk_screen_smoke_20260901_v1"
    )
    if not smoke.exists():
        pytest.skip("network smoke artifact is unavailable")
    audit = network.retention_audit(smoke, "summary")
    assert audit["summary_retention_pass"]
    assert audit["forbidden_heavy_directory_count"] == 0
    assert audit["retained_case_total_bytes"] < 5 * 1024 * 1024


def test_final_output_contract_is_compatible_with_industrial_dashboard(tmp_path: Path):
    manifest = {
        "status": "complete",
        "mode": "full",
        "final_top3_conclusion_status": "top3_final_confirme",
        "confirmation_seed_count": 10,
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    supplier_rows = network.rank_suppliers(
        [
            {
                "scenario_id": "a",
                "chain_id": "a",
                "supplier_id": "SUP-A",
                "item_id": "item:A",
                "dst_node_id": "M-1",
                "target_product_id": "268091",
                "failure_mode": "transport_delay",
                "target_on_due_date_proxy_delta_vs_paired_baseline_mean": -0.2,
                "incremental_target_backlog_qty_days_mean": 10.0,
                "target_production_shortfall_vs_paired_baseline_mean": 1.0,
                "effect_status": "effet_mesure_sur_le_service_client",
            }
        ],
        evidence_stage="confirmation_10_realisations",
    )
    mode_rows = network.summarize_failure_modes(
        [
            {
                "scenario_id": "a",
                "chain_id": "a",
                "supplier_id": "SUP-A",
                "failure_mode": "transport_delay",
                "target_on_due_date_proxy_delta_vs_paired_baseline_mean": -0.2,
                "incremental_target_backlog_qty_days_mean": 10.0,
                "target_production_shortfall_vs_paired_baseline_mean": 1.0,
                "effect_status": "effet_mesure_sur_le_service_client",
            }
        ],
        evidence_stage="confirmation_10_realisations",
    )
    network._write_csv(tmp_path / "supplier_sensitivity_ranking.csv", supplier_rows)
    network._write_csv(tmp_path / "failure_mode_sensitivity_summary.csv", mode_rows)
    assert {
        "supplier_sensitivity_rank",
        "supplier_id",
        "worst_item_id",
        "worst_target_product_id",
        "worst_failure_mode",
        "worst_service_delta",
    } <= set(supplier_rows[0])
    assert {
        "failure_mode_sensitivity_rank",
        "failure_mode",
        "worst_service_delta",
    } <= set(mode_rows[0])
    state = industrial_dashboard._campaign_state(tmp_path, kind="network")
    assert state["state"] == industrial_dashboard.NETWORK_PRESELECTION_STATE
    manifest["final_top3_conclusion_status"] = "conclusion_top3_refusee"
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    state = industrial_dashboard._campaign_state(tmp_path, kind="network")
    assert state["state"] == industrial_dashboard.NETWORK_PRESELECTION_STATE
