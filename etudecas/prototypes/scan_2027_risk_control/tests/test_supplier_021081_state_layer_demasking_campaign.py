from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as base,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_state_layer_demasking_campaign as campaign,
)


def test_design_separates_component_intermediate_and_joint_layers() -> None:
    graph = base.read_json(base.DEFAULT_GRAPH)
    states = campaign.build_layer_states(graph)
    assert len(states) == 9
    assert states[0].regime_id == "observed_all_layers"
    assert {
        state.regime_id for state in states if state.cover_days == 30
    } == {
        "component_only_30d",
        "intermediate_stock_only_30d",
        "intermediate_production_only_30d",
        "joint_30d",
    }
    joint = next(state for state in states if state.regime_id == "joint_90d")
    assert joint.component_target_qty_kg == pytest.approx(357.6 * 90)
    assert joint.intermediate_target_total_g == pytest.approx(
        base.INTERMEDIATE_773474_HORIZON_NEED_G / 720 * 90
    )
    assert joint.intermediate_target_sdc_g / joint.intermediate_target_total_g == pytest.approx(
        9_600_000 / 24_193_000
    )
    assert set(joint.reduced_layers) == {
        base.ITEM_ID,
        "stock:" + base.INTERMEDIATE_ITEM_ID,
        "production:" + base.INTERMEDIATE_ITEM_ID,
    }
    assert joint.production_open_order_removed is True
    assert joint.production_target_qty_g == pytest.approx(
        base.INTERMEDIATE_773474_HORIZON_NEED_G / 720 * 90
    )
    assert all(
        row["global_lean_claim_allowed"] is False
        for row in campaign.state_rows(states)
    )


def test_joint_scale_file_contains_three_explicit_pairs(tmp_path: Path) -> None:
    states = campaign.build_layer_states(base.read_json(base.DEFAULT_GRAPH))
    joint = next(state for state in states if state.regime_id == "joint_30d")
    path = campaign.write_scale_input(tmp_path, joint)
    assert path is not None
    rows = base.read_csv_rows(path)
    assert {(row["node_id"], row["item_id"]) for row in rows} == {
        ("SDC-1450", "item:021081"),
        ("SDC-1450", "item:773474"),
        ("M-1430", "item:773474"),
    }


def test_production_overlay_removes_open_order_and_sets_finite_budget() -> None:
    source = base.read_json(base.DEFAULT_GRAPH)
    state = next(
        state
        for state in campaign.build_layer_states(source)
        if state.regime_id == "intermediate_production_only_30d"
    )
    graph, audit = campaign.graph_for_state(source, state, days=720)
    opening = [
        row
        for row in base.opening_order_payload(graph)["rows"]
        if row.get("order_type") == "production_open_order"
        and row.get("item_id") == base.INTERMEDIATE_ITEM_ID
        and row.get("dst_node_id") == base.DESTINATION_ID
    ]
    assert len(opening) == 1
    assert opening[0]["quantity"] == 0
    process = next(
        process
        for node in graph["nodes"]
        if node.get("id") == base.DESTINATION_ID
        for process in node.get("processes", [])
        if process.get("id") == "proc:MAKE_773474"
    )
    assert process["capacity"]["max_rate"] == pytest.approx(
        state.production_target_qty_g / 720
    )
    assert audit["opening_773474_production_order_original_qty_g"] == 3_200_000
    original_opening = [
        row
        for row in base.opening_order_payload(source)["rows"]
        if row.get("order_type") == "production_open_order"
        and row.get("item_id") == base.INTERMEDIATE_ITEM_ID
    ]
    assert original_opening[0]["quantity"] == 3_200_000


def test_optional_180_adds_four_separate_states() -> None:
    states = campaign.build_layer_states(
        base.read_json(base.DEFAULT_GRAPH),
        (*campaign.PRIORITY_COVER_LEVELS_DAYS, campaign.OPTIONAL_COVER_LEVEL_DAYS),
    )
    assert len([state for state in states if state.cover_days == 180]) == 4


def test_confirmation_trigger_requires_a_downstream_difference() -> None:
    no_effect = {
        "product_on_due_delta_vs_paired_baseline": 0,
        "product_backlog_qty_days_delta_vs_paired_baseline": 0,
        "product_268967_released_qty_delta_vs_paired_baseline": 0,
    }
    assert campaign.downstream_effect(no_effect) is False
    assert campaign.downstream_effect(
        {**no_effect, "product_268967_released_qty_delta_vs_paired_baseline": -107_800}
    ) is True


def test_paired_layer_metrics_adds_release_and_intermediate_deltas() -> None:
    common = {
        "state_regime": "joint_30d",
        "seed": 1,
        "product_on_due_volume_proxy": 1,
        "product_backlog_qty_days": 0,
        "component_stock_min_qty_kg": 0,
        "intermediate_773474_min_total_qty_g": 100,
        "intermediate_773474_final_total_qty_g": 200,
        "intermediate_773474_produced_qty_g": 300,
        "intermediate_773474_released_qty_g": 300,
        "product_268967_produced_qty": 1_000,
        "product_268967_released_qty": 1_000,
    }
    rows = campaign.paired_layer_metrics(
        [
            {**common, "scenario_id": "baseline_observed_order_book"},
            {
                **common,
                "scenario_id": "all_021081__quality_hold__180",
                "product_268967_released_qty": 900,
            },
        ]
    )
    stress = next(
        row for row in rows if row["scenario_id"] != "baseline_observed_order_book"
    )
    assert stress["product_268967_released_qty_delta_vs_paired_baseline"] == -100
    assert campaign.downstream_effect(stress) is True
