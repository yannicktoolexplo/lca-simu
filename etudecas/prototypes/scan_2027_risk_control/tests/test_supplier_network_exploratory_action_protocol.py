from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_exploratory_action_protocol as protocol,
)


def _context(tmp_path: Path, *, alternatives=None) -> protocol.ProtocolContext:
    tmp_path.mkdir(parents=True, exist_ok=True)
    graph_path = tmp_path / "graph.json"
    engine_path = tmp_path / "engine.py"
    profile_path = tmp_path / "profile.json"
    graph_path.write_text("{}\n", encoding="utf-8")
    engine_path.write_text("# engine\n", encoding="utf-8")
    profile_path.write_text("{}\n", encoding="utf-8")
    start = datetime(2026, 9, 2, 12, 41, tzinfo=timezone.utc)
    end = start + timedelta(hours=19.55)
    lanes = tuple(
        protocol.Lane(
            selection_slot=index,
            chain_id=f"chain_{index}",
            supplier_id=f"supplier_{index}",
            item_id=f"item:{index}",
            dst_node_id=f"M-{index}",
            edge_id=f"edge:{index}",
            target_product_id="268091" if index < 4 else "268967",
            active_window_start_day=40 + index,
            active_window_end_day=219 + index,
            active_window_pulled_qty=1800.0 * index,
            inventory_initial_qty=0.0 if index == 4 else 100.0,
            inventory_uom="KG" if index < 3 else "UN",
            holding_cost_model_per_unit_day=0.01,
            graph_transport_cost_model_per_unit=0.2,
            graph_lead_time_mean_days=40.0,
            procurement_standard_order_qty=50.0,
            procurement_standard_order_uom="KG" if index < 3 else "UN",
            procurement_standard_order_source="edge.attrs.standard_order_qty",
            procurement_min_order_qty=None,
            procurement_min_order_source="",
            procurement_lot_multiple_qty=None,
            procurement_lot_multiple_source="",
            procurement_max_order_qty=None,
            procurement_max_order_source="",
        )
        for index in range(1, 5)
    )
    severe = {}
    source = {}
    for lane in lanes:
        for mode, risk_type, value, unit in (
            ("transport_delay", "lead_time_extra_days", 120.0, "jours_ajoutes"),
            ("supply_availability", "availability", 0.5, "ratio"),
            ("quality_hold", "quality_delay", 90.0, "jours_ajoutes"),
        ):
            severe[(lane.chain_id, mode)] = {
                "case_id": f"v3__{lane.chain_id}__{mode}",
                "risk_type": risk_type,
                "mechanism_value": str(value),
                "mechanism_unit": unit,
                "stress_start_day": str(lane.active_window_start_day),
                "stress_end_day": str(lane.active_window_end_day),
            }
            source[(lane.chain_id, mode)] = {
                "scenario_id": f"source__{lane.chain_id}__{mode}"
            }
    return protocol.ProtocolContext(
        plan_dir=tmp_path,
        source_dir=tmp_path,
        plan_manifest={"plan_signature": "plan-signature"},
        source_manifest={
            "campaign_signature": "campaign-signature",
            "created_or_resumed_at_utc": start.isoformat(),
            "completed_at_utc": end.isoformat(),
            "planned_run_counts": {"full": 1255},
        },
        lanes=lanes,
        seeds=tuple(range(340282, 340312)),
        severe_cases=severe,
        source_severe_cases=source,
        graph={},
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
        alternative_by_chain=alternatives or {},
    )


def test_four_levers_are_physically_separated_and_fail_closed(tmp_path: Path) -> None:
    context = _context(tmp_path)
    rows = protocol.build_lever_parameters(context)
    assert len(rows) == 16
    assert {row["lever_id"] for row in rows} == set(protocol.EXPECTED_LEVERS)
    assert all(not row["priority_weight_used"] for row in rows)
    assert all(not row["closed_loop_claimed"] for row in rows)
    assert all(row["not_a_recommendation"] is not False for row in rows)

    transport = next(
        row for row in rows if row["lever_id"] == "future_lane_transport_reduction"
    )
    assert transport["lead_time_adjustment_days"] == -7
    assert transport["identified_shipment_claimed"] is False
    stock = next(row for row in rows if row["lever_id"] == "prepositioned_free_stock_14d")
    assert stock["buffer_raw_qty"] == 140.0
    assert stock["buffer_additional_qty"] == 150.0
    assert stock["buffer_rounded_qty"] == 150.0
    assert stock["buffer_procurement_lot_count"] == 3
    assert stock["buffer_uom"] == "KG"
    assert stock["stock_present_at_j0_hypothesis"] is True
    assert stock["stock_acquisition_simulated"] is False
    assert stock["model_cost_value"] == ""
    assert stock["static_720_day_holding_cost_published"] is False
    assert "zero_J0_is_blocked" in stock["paired_j0_stock_requirement"]
    quality = next(
        row
        for row in rows
        if row["lever_id"]
        == "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
    )
    assert "open-loop" in quality["lever_label_fr"]
    assert "toute la voie" in quality["lever_label_fr"]
    assert quality["lead_time_adjustment_days"] == -7
    assert quality["action_timing"] == (
        "fixed_calendar_open_loop_whole_lane_in_quality_scenario"
    )
    assert quality["quality_hold_reduction_claimed"] is False
    assert quality["identified_lot_claimed"] is False
    assert "dated_post_quality_release_transport_reduction" not in {
        row["lever_id"] for row in rows
    }
    alternatives = [
        row
        for row in rows
        if row["lever_id"] == "explicit_counterfactual_alternative_source"
    ]
    assert all(row["graph_counterfactual_required"] for row in alternatives)
    assert all(row["new_action_run_status"].startswith("blocked_") for row in alternatives)


def test_stock_rounding_preserves_raw_moq_multiple_max_and_cost_limits(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    constrained_lane = replace(
        context.lanes[0],
        procurement_standard_order_qty=50.0,
        procurement_min_order_qty=175.0,
        procurement_min_order_source="edge.order_terms.min_order_qty",
        procurement_lot_multiple_qty=40.0,
        procurement_lot_multiple_source="edge.order_terms.lot_multiple_qty",
        procurement_max_order_qty=240.0,
        procurement_max_order_source="edge.order_terms.max_order_qty",
    )
    context = replace(context, lanes=(constrained_lane, *context.lanes[1:]))
    stock = next(
        row
        for row in protocol.build_lever_parameters(context)
        if row["chain_id"] == constrained_lane.chain_id
        and row["lever_id"] == "prepositioned_free_stock_14d"
    )
    assert stock["buffer_raw_qty"] == 140.0
    assert stock["procurement_standard_lot_qty"] == 50.0
    assert stock["procurement_moq_qty"] == 175.0
    assert stock["procurement_explicit_multiple_qty"] == 40.0
    assert stock["procurement_max_order_qty"] == 240.0
    assert stock["procurement_effective_rounding_lot_qty"] == 40.0
    assert stock["buffer_rounded_qty"] == 200.0
    assert stock["buffer_procurement_lot_count"] == 5
    assert stock["procurement_max_constraint_satisfied"] is True
    assert stock["model_cost_value"] == ""
    assert stock["industrial_action_cost_available"] is False
    assert stock["incremental_holding_cost_status"].startswith(
        "not_computed_requires_future_incremental_inventory_trajectory"
    )


def test_real_standard_lot_sizes_produce_the_expected_four_j0_buffers(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    # These are the four quantities standard and active-window pulls read from
    # the locked industrial graph/V3 inputs.  Keep them here as a regression
    # test so a future schema change cannot silently replace the real lot
    # multiple by an invented MOQ or by the unrounded 14-day target.
    standard_lots = (1100.0, 300.0, 5000.0, 120000.0)
    active_window_pulls = (1100.0, 300.0, 1915000.0, 1080000.0)
    expected_raw = (
        85.555555556,
        23.333333333,
        148944.444444444,
        84000.0,
    )
    expected_rounded = (1100.0, 300.0, 150000.0, 120000.0)
    expected_lot_counts = (1, 1, 30, 1)
    lanes = tuple(
        replace(
            lane,
            active_window_pulled_qty=pull,
            procurement_standard_order_qty=standard,
            procurement_min_order_qty=None,
            procurement_min_order_source="",
            procurement_lot_multiple_qty=None,
            procurement_lot_multiple_source="",
            procurement_max_order_qty=None,
            procurement_max_order_source="",
        )
        for lane, pull, standard in zip(
            context.lanes,
            active_window_pulls,
            standard_lots,
            strict=True,
        )
    )
    stock_rows = [
        row
        for row in protocol.build_lever_parameters(replace(context, lanes=lanes))
        if row["lever_id"] == "prepositioned_free_stock_14d"
    ]

    assert [row["procurement_standard_lot_qty"] for row in stock_rows] == list(
        standard_lots
    )
    assert [row["buffer_raw_qty"] for row in stock_rows] == pytest.approx(
        expected_raw,
        abs=1e-9,
    )
    assert [row["buffer_rounded_qty"] for row in stock_rows] == list(
        expected_rounded
    )
    assert [row["buffer_procurement_lot_count"] for row in stock_rows] == list(
        expected_lot_counts
    )
    assert all(row["procurement_moq_qty"] == "" for row in stock_rows)
    assert all(row["procurement_explicit_multiple_qty"] == "" for row in stock_rows)
    assert all(row["procurement_max_order_qty"] == "" for row in stock_rows)
    assert all(
        row["procurement_constraints_not_in_graph"]
        == "moq;explicit_multiple;max_order"
        for row in stock_rows
    )


def test_stock_above_graph_max_is_blocked_instead_of_inventing_split_orders(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    constrained_lane = replace(
        context.lanes[0],
        procurement_min_order_qty=175.0,
        procurement_min_order_source="edge.order_terms.min_order_qty",
        procurement_lot_multiple_qty=40.0,
        procurement_lot_multiple_source="edge.order_terms.lot_multiple_qty",
        procurement_max_order_qty=180.0,
        procurement_max_order_source="edge.order_terms.max_order_qty",
    )
    context = replace(context, lanes=(constrained_lane, *context.lanes[1:]))
    rows = protocol.build_lever_parameters(context)
    stock = next(
        row
        for row in rows
        if row["chain_id"] == constrained_lane.chain_id
        and row["lever_id"] == "prepositioned_free_stock_14d"
    )
    assert stock["buffer_rounded_qty"] == 200.0
    assert stock["procurement_max_constraint_satisfied"] is False
    assert stock["new_action_run_status"].startswith("blocked_")
    design = protocol.build_experiment_design(context, rows)
    assert not any(
        row["chain_id"] == constrained_lane.chain_id
        and row["lever_id"] == "prepositioned_free_stock_14d"
        and row["arm"] == "incident_with_action"
        and row["new_engine_run_count"]
        for row in design
    )


def test_15_is_exact_prefix_of_30_and_triplets_are_complete(tmp_path: Path) -> None:
    context = _context(tmp_path)
    parameters = protocol.build_lever_parameters(context)
    design = protocol.build_experiment_design(context, parameters)
    assert len(design) == 4 * 4 * 30 * 3
    preliminary = [row for row in design if row["included_in_preliminary_15"]]
    assert len(preliminary) == 4 * 4 * 15 * 3
    assert {row["seed"] for row in preliminary} == set(context.seeds[:15])
    assert {row["seed"] for row in design} == set(context.seeds)
    grouped = {}
    for row in design:
        grouped.setdefault(row["pairing_id"], set()).add(row["arm"])
    assert all(
        arms == {"normal", "incident_no_action", "incident_with_action"}
        for arms in grouped.values()
    )
    assert sum(row["new_engine_run_count"] for row in design) == 360
    assert all(not row["priority_weight_used"] for row in design)


def test_budget_counts_only_new_action_runs_and_uses_observed_rate(tmp_path: Path) -> None:
    context = _context(tmp_path)
    design = protocol.build_experiment_design(
        context, protocol.build_lever_parameters(context)
    )
    budget = protocol.build_execution_budget(context, design)
    assert budget["logical_triplet_row_count_preliminary"] == 720
    assert budget["logical_triplet_row_count_final"] == 1440
    assert budget["preliminary"]["parameterized_transport_new_action_runs"] == 60
    assert budget["preliminary"]["quality_new_action_runs_waiting_for_V3_pair"] == 60
    assert budget["preliminary"]["conditional_stock_new_action_runs_max"] == 60
    assert budget["preliminary"]["alternative_new_action_runs_currently_executable"] == 0
    assert budget["preliminary"]["potential_alternative_new_action_runs_after_valid_register"] == 60
    assert budget["preliminary"]["maximum_new_action_runs_without_alternative"] == 180
    assert budget["final"]["maximum_new_action_runs_without_alternative"] == 360
    assert budget["physical_evidence_after_alias_reuse"][
        "preliminary_unique_reused_normal_or_incident_cases"
    ] == 195
    assert budget["physical_evidence_after_alias_reuse"][
        "preliminary_total_unique_physical_cases_without_alternative"
    ] == 375
    assert budget["eta_basis"]["observed_main_campaign_runs_per_hour"] == pytest.approx(
        1255 / 19.55, abs=1e-6
    )
    assert budget["eta_basis"]["planning_rate_runs_per_hour"] == pytest.approx(
        1255 / 19.55, abs=1e-6
    )
    assert budget["eta_basis"]["small_smoke_rate_used_for_eta"] is False


def test_completed_five_run_smoke_is_disclosed_but_excluded_from_eta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke_dir = tmp_path / "smoke_v2"
    smoke_dir.mkdir()
    start = datetime(2026, 9, 3, 13, 53, 34, tzinfo=timezone.utc)
    end = start + timedelta(minutes=13, seconds=53)
    (smoke_dir / "post_priority_extension_runner_manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "mode": "smoke",
                "created_or_resumed_at_utc": start.isoformat(),
                "completed_at_utc": end.isoformat(),
                "expected_engine_physical_run_count": 5,
                "executed_engine_case_count": 5,
                "remaining_engine_physical_run_count": 0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(protocol, "DEFAULT_OBSERVED_POST_PRIORITY_SMOKE", smoke_dir)
    context = _context(tmp_path / "context")
    design = protocol.build_experiment_design(
        context, protocol.build_lever_parameters(context)
    )
    budget = protocol.build_execution_budget(context, design)
    smoke = next(
        row
        for row in budget["eta_basis"]["throughput_observations"]
        if row["kind"] == "completed_post_priority_smoke_v2_small_sample"
    )
    assert smoke["completed_physical_run_count"] == 5
    assert smoke["small_sample_warning"] is True
    assert smoke["included_in_planning_rate"] is False
    assert budget["eta_basis"]["planning_rate_runs_per_hour"] == pytest.approx(
        1255 / 19.55, abs=1e-6
    )


def test_alternative_register_requires_explicit_graph_and_qualification(
    tmp_path: Path,
) -> None:
    graph = {
        "nodes": [{"id": "ALT-1"}],
        "edges": [{"id": "existing-edge", "from": "SRC", "to": "M-1", "items": ["item:1"]}],
    }
    register = tmp_path / "alternatives.csv"
    fields = [
        "chain_id",
        "alternative_supplier_id",
        "qualification_evidence_ref",
        "counterfactual_edge_id",
        "lead_time_mean_days",
        "lead_time_stages",
        "distance_km",
        "transport_cost_model_per_unit",
        "quantity_uom",
        "allocation_contract",
    ]
    with register.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "chain_id": "chain_1",
                "alternative_supplier_id": "ALT-1",
                "qualification_evidence_ref": "QUAL-2026-001",
                "counterfactual_edge_id": "edge:ALT-1_TO_M-1_1",
                "lead_time_mean_days": "20",
                "lead_time_stages": "4",
                "distance_km": "100",
                "transport_cost_model_per_unit": "0.4",
                "quantity_uom": "KG",
                "allocation_contract": "legacy_capacity_weighted_after_graph_addition",
            }
        )
    loaded = protocol._load_alternative_register(  # noqa: SLF001
        register, graph=graph, chain_ids={"chain_1"}
    )
    assert loaded["chain_1"]["alternative_supplier_id"] == "ALT-1"

    rows = list(csv.DictReader(register.open(encoding="utf-8")))
    rows[0]["qualification_evidence_ref"] = ""
    with register.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="qualification"):
        protocol._load_alternative_register(  # noqa: SLF001
            register, graph=graph, chain_ids={"chain_1"}
        )


def test_created_protocol_has_exact_inventory_and_detects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path / "source")
    context.plan_dir.mkdir(parents=True, exist_ok=True)
    # The synthetic context uses one directory for both sources.  These two
    # files are needed only for the signed lineage fields in create_protocol.
    (context.plan_dir / "post_priority_extensions_plan_manifest.json").write_text(
        json.dumps({"plan_signature": "plan-signature"}), encoding="utf-8"
    )
    (context.source_dir / "campaign_manifest.json").write_text(
        json.dumps(context.source_manifest), encoding="utf-8"
    )
    monkeypatch.setattr(protocol, "load_context", lambda **_kwargs: context)
    output = tmp_path / "protocol_v5"
    protocol.create_protocol(
        post_priority_plan=tmp_path / "unused",
        graph=tmp_path / "unused_graph",
        engine=tmp_path / "unused_engine",
        profile=tmp_path / "unused_profile",
        output_dir=output,
    )
    validation = protocol.validate_protocol_artifact(output)
    assert validation["valid"] is True
    assert validation["paired_design_row_count"] == 1440
    assert validation["stock_lotified_lane_count"] == 4
    assert validation["industrial_action_cost_published"] is False
    assert {path.name for path in output.iterdir()} == set(protocol.PLAN_FILES)

    with (output / "PROTOCOL.md").open("a", encoding="utf-8") as stream:
        stream.write("tamper")
    with pytest.raises(ValueError, match="modifié"):
        protocol.validate_protocol_artifact(output)
