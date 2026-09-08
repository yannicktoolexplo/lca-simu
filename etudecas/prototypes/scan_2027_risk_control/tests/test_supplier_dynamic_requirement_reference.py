from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_dynamic_requirement_reference_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_dynamic_requirement_reference_runner as runner,
)


@pytest.fixture(autouse=True)
def _replace_deep_v3_checkpoint_validation_for_unit_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep fixtures small; production still uses V3's 634-file validator."""

    def validate_fixture_checkpoint(**kwargs: Any) -> dict[str, Any] | None:
        path = Path(kwargs["output_dir"]) / runner.V3_CHECKPOINT_FILE
        return protocol.read_json(path) if path.is_file() else None

    monkeypatch.setattr(
        runner,
        "_authoritative_v3_checkpoint_validation",
        validate_fixture_checkpoint,
    )


def _build_protocol(tmp_path: Path) -> tuple[Path, protocol.ValidatedProtocol]:
    output = tmp_path / "protocol"
    active_campaign = _stopped_v3(tmp_path)
    protocol.build_protocol(
        graph=protocol.DEFAULT_GRAPH,
        engine=protocol.DEFAULT_ENGINE,
        supplier_floors=protocol.DEFAULT_FLOORS,
        old_profile=protocol.DEFAULT_OLD_PROFILE,
        new_profile=protocol.DEFAULT_NEW_PROFILE,
        output_dir=output,
        active_campaign_dir=active_campaign,
        capacity_audit_dir=protocol.DEFAULT_CAPACITY_AUDIT_DIR,
    )
    return output, protocol.validate_protocol(output)


def _v3_manifest(status: str, active_process_id: int) -> dict[str, Any]:
    return {
        "schema_version": "etudecas.supplier_network_post_priority_extension_runner.v1",
        "runner_signature": "test-runner-signature",
        "plan_signature": "test-plan-signature",
        "runner_script_sha256": "test-runner-sha256",
        "planner_script_sha256": "test-planner-sha256",
        "plan_manifest_sha256": "test-plan-manifest-sha256",
        "source_campaign_manifest_sha256": "test-source-manifest-sha256",
        "priority_selection_lineage_sha256": "test-priority-lineage-sha256",
        "seed_scheduling_policy": "cumulative_signed_seed_prefix_v1",
        "signed_full_seed_ids": list(range(340282, 340312)),
        "checkpoint_after_repetitions": 15,
        "mode": "full",
        "scenario_id": "scn:BASE",
        "contract_revision": "test-contract",
        "source_dir": str(Path("C:/test/source")),
        "plan_dir": str(Path("C:/test/plan")),
        "status": status,
        "active_process_id": active_process_id,
    }


def _stopped_v3(tmp_path: Path, *, status: str = "paused_preliminary") -> Path:
    directory = tmp_path / "v3"
    directory.mkdir(exist_ok=True)
    manifest = _v3_manifest(status, 0)
    ledger = {
        "runner_signature": manifest["runner_signature"],
        "case_files": {
            f"case::{index}": f"ledger_cases/case_{index}.json" for index in range(634)
        },
        "case_file_sha256": {
            f"case::{index}": f"sha256-{index}" for index in range(634)
        },
    }
    ledger_path = directory / runner.LEDGER_FILE
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    ledger_sha256 = protocol.sha256_file(ledger_path)
    completed_seed_ids = manifest["signed_full_seed_ids"][:15]
    checkpoint: dict[str, Any] = {
        "schema_version": "etudecas.supplier_network_post_priority_extension_runner_checkpoint.v1",
        "status": "paused_preliminary",
        "checkpoint_at_utc": "2026-09-04T00:00:00+00:00",
        "runner_signature": manifest["runner_signature"],
        "runner_builder_sha256": manifest["runner_script_sha256"],
        "planner_builder_sha256": manifest["planner_script_sha256"],
        "plan_signature": manifest["plan_signature"],
        "plan_manifest_sha256": manifest["plan_manifest_sha256"],
        "priority_selection_lineage_sha256": manifest[
            "priority_selection_lineage_sha256"
        ],
        "seed_scheduling_policy": manifest["seed_scheduling_policy"],
        "signed_full_seed_count": 30,
        "signed_full_seed_ids": manifest["signed_full_seed_ids"],
        "completed_seed_count": 15,
        "completed_seed_ids": completed_seed_ids,
        "logical_baseline_reference_count": 31,
        "physical_baseline_owner_count": 30,
        "logical_stress_case_count": 604,
        "logical_stress_case_count_by_extension": {
            "multi_lane_supplier_common_cause": 120,
            "temporal_robustness": 240,
            "priority_four_business_causes": 240,
            "causal_lot_attribution_subset": 4,
        },
        "reused_source_stress_case_count": 124,
        "executed_engine_physical_run_count": 510,
        "full_expected_engine_physical_run_count": 1020,
        "remaining_engine_physical_run_count": 510,
        "ledger_evidence_case_count": 634,
        "case_evidence_file_sha256": {
            key: {"relative_path": ledger["case_files"][key], "sha256": value}
            for key, value in ledger["case_file_sha256"].items()
        },
        "execution_ledger_sha256_at_checkpoint": ledger_sha256,
        "all_target_seed_jobs_complete": True,
        "no_future_seed_job_active": True,
        "full_universe_complete": False,
        "canonical_results_written": False,
        "consolidation_written": False,
        "preliminary_not_final": True,
        "finalization_eligible": False,
        "publishable_execution_contract_pass": False,
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "promotion_allowed": False,
    }
    checkpoint["checkpoint_signature"] = protocol.stable_sha256(checkpoint)
    checkpoint_path = directory / runner.V3_CHECKPOINT_FILE
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    manifest.update(
        {
            "preliminary_checkpoint_manifest": runner.V3_CHECKPOINT_FILE,
            "preliminary_checkpoint_manifest_sha256": protocol.sha256_file(
                checkpoint_path
            ),
            "checkpoint_history": [
                {
                    "completed_seed_count": 15,
                    "completed_seed_ids": completed_seed_ids,
                    "checkpoint_manifest": runner.V3_CHECKPOINT_FILE,
                    "checkpoint_signature": checkpoint["checkpoint_signature"],
                }
            ],
            "completed_seed_count": 15,
            "completed_seed_ids": completed_seed_ids,
            "ledger_case_count": 634,
            "ledger_case_file_sha256_count": 634,
            "execution_ledger_sha256": ledger_sha256,
            "executed_engine_case_count": 510,
            "remaining_engine_physical_run_count": 510,
        }
    )
    (directory / runner.V3_MANIFEST_FILE).write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return directory


def _signed_fake_evidence(
    case: runner.PlannedCase, validated: protocol.ValidatedProtocol, _output: Path
) -> dict[str, Any]:
    materials = []
    offset = 1.0 if case.variant_id == protocol.NEW_VARIANT_ID else 0.0
    for index, material in enumerate(validated.materials, 1):
        base = float(index)
        materials.append(
            {
                "node_id": material.node_id,
                "item_id": material.item_id,
                "pair_key": material.pair_key,
                "uom": material.uom,
                "safety_time_days": material.safety_time_days,
                "requirement_mode_in_variant": runner._variant_requirement_mode(
                    case.variant_id, material.pair_key
                ),
                "stock_J0_before_production_qty": base + offset,
                "stock_before_day0_arrival_qty": base + offset,
                "stock_end_min_qty": base + offset,
                "stock_end_mean_qty": base + offset,
                "zero_stock_day_count": 0,
                "consumption_total_qty": 720.0 * base,
                "consumption_daily_mean_qty": base,
                "bom_expected_consumption_total_qty": 720.0 * base,
                "bom_consumption_max_abs_residual_qty": 0.0,
                "bom_consumption_balance_valid": True,
                "bom_consumption_balance_basis": (
                    "daily_executed_output_qty_times_graph_ratio_per_batch_"
                    "converted_to_material_inventory_uom"
                ),
                "arrival_total_qty": 720.0 * base,
                "arrival_positive_day_count": 720,
                "day0_boundary_arrival_qty": base,
                "day0_boundary_arrival_included_in_stock_J0": True,
                "stock_balance_max_abs_residual_qty_J1_J719": 0.0,
                "stock_balance_valid_J1_J719": True,
                "stock_balance_equation": (
                    "stock_end_day_minus_1_plus_arrival_day_minus_"
                    "bom_consumption_day_equals_stock_end_day"
                ),
                "mrp_order_row_count": 10,
                "mrp_order_J0_row_count": 1,
                "mrp_order_J0_release_qty": base,
                "mrp_order_J0_planned_receipt_qty": base,
                "mrp_release_total_qty": 720.0 * base,
                "mrp_planned_receipt_total_qty": 720.0 * base,
                "mrp_target_stock_J0_qty": 20.0 * base + offset,
                "mrp_target_stock_mean_qty": 20.0 * base + offset,
                "mrp_target_stock_median_qty": 20.0 * base + offset,
                "mrp_target_stock_p95_qty": 20.0 * base + offset,
                "mrp_target_stock_max_qty": 20.0 * base + offset,
                "mrp_target_demand_signal_daily_mean_qty": base,
                "mrp_target_demand_signal_median_qty": base,
                "mrp_target_demand_signal_p95_qty": base,
                "mrp_target_demand_signal_max_qty": base,
                "mrp_backlog_J0_qty": 0.0,
                "mrp_backlog_max_qty": 0.0,
                "target_stock_mean_to_consumption_daily_mean_days": 20.0 + offset,
                "consumption_observation_status": "positive_consumption_observed",
                "mrp_demand_signal_status": "positive_signal_observed",
                "stock_J0_cover_days": (base + offset) / base,
                "stock_J0_cover_status": "evaluable_positive_consumption",
                "stock_J0_covers_measured_horizon": False,
                "requirement_signal_to_consumption_ratio": 1.0,
                "requirement_signal_to_consumption_diagnostic": (
                    "within_diagnostic_band_0p5_2"
                ),
                "j0_pipeline_qty": None,
                "j0_pipeline_cover_days": None,
                "j0_pipeline_quantification_status": (
                    "not_evaluable_engine_exports_boundary_digest_only"
                ),
                "future_supplier_lane_shipment_row_count": 1,
                "future_supplier_lane_positive_shipment_count": 1,
                "future_supplier_lane_shipped_qty": base,
                "supplier_shipment_arriving_J0_J719_row_count": 1,
                "supplier_shipment_arriving_J0_J719_qty": base,
                "supplier_arrival_minus_recorded_shipment_qty": 719.0 * base,
                "supplier_arrival_reconciliation_status": (
                    "bounded_not_exact_opening_pipeline_quantities_not_exported"
                ),
                "supplier_arrival_reconciliation_scope": (
                    "recorded shipments are a lower bound; opening pipeline is unknown"
                ),
                "supplier_risk_scope": "external_supplier_lane",
                "supplier_risk_flow_evaluable": True,
                "supplier_risk_flow_evaluability_reason": (
                    "positive_future_supplier_shipment_observed_J0_J719"
                ),
                "supplier_parameter_row_count": 1,
                "supplier_parameter_status": "available_external_supplier_rows",
                "supplier_ids": f"supplier-{index}",
                "supplier_capacity_bases": "propagated_dynamic_demand",
                "supplier_direct_nominal_capacity_total_qty_per_day": base * 2.0,
                "supplier_direct_effective_capacity_total_qty_per_day": base * 2.0,
                "supplier_applied_capacity_scale_min": 1.0,
                "supplier_applied_capacity_scale_max": 1.0,
                "supplier_explicit_capacity_total_qty_per_day": 0.0,
                "supplier_process_capacity_total_qty_per_day": 0.0,
                "supplier_downstream_requirement_lane_row_sum_qty_per_day": base,
                "supplier_downstream_requirement_pair_qty_per_day": base,
                "supplier_downstream_requirement_pair_min_qty_per_day": base,
                "supplier_downstream_requirement_pair_max_qty_per_day": base,
                "supplier_downstream_requirement_pair_values_all_equal": True,
                "supplier_downstream_signal_lane_row_sum_qty_per_day": base,
                "supplier_downstream_signal_pair_qty_per_day": base,
                "supplier_downstream_signal_pair_min_qty_per_day": base,
                "supplier_downstream_signal_pair_max_qty_per_day": base,
                "supplier_downstream_signal_pair_values_all_equal": True,
                "external_procurement_daily_need_total_qty": base,
                "external_procurement_nominal_capacity_total_qty_per_day": base / 0.7,
                "external_procurement_target_utilization_min": 0.7,
                "external_procurement_target_utilization_max": 0.7,
                "external_procurement_capacity_bases": "max_downstream_pull",
                "external_procurement_capacity_profiles": "qualified_pharma",
                "external_procurement_pipeline_target_total_qty": base * 20.0,
                "external_procurement_initial_pipeline_seed_total_qty": 0.0,
                "supplier_capacity_dynamic_signal_basis_row_count": (
                    1 if case.variant_id == protocol.NEW_VARIANT_ID else 0
                ),
                "supplier_capacity_explicit_override_row_count": 0,
                "supplier_capacity_zero_signal_fallback_row_count": 0,
                "supplier_capacity_unexpected_static_basis_row_count": (
                    0 if case.variant_id == protocol.NEW_VARIANT_ID else 1
                ),
            }
        )
    service = []
    for product in runner.PRODUCTS:
        service.append(
            {
                "product_id": product,
                "demand_qty": 1000.0,
                "daily_demand_signature": protocol.stable_sha256(
                    {"seed": case.seed, "product": product, "demand": 1000.0}
                ),
                "daily_demand_positive_day_count": 720,
                "daily_demand_min_qty": 1.0,
                "daily_demand_max_qty": 2.0,
                "fill_rate": 0.9 + 0.01 * offset,
                "on_due_service": 0.8 + 0.01 * offset,
                "backlog_qty_days": 100.0 - offset,
                "backlog_end_qty": 0.0,
            }
        )
    production = [
        {
            "node_id": "M-1810" if product == "268091" else "M-1430",
            "product_id": product,
            "released_production_qty": 900.0 + offset,
            "executed_production_qty": 900.0 + offset,
        }
        for product in runner.PRODUCTS
    ]
    lot_required = case.seed == protocol.LOT_TRACE_SEED
    lot_report_relative = (
        Path("cases")
        / case.variant_id
        / f"seed_{case.seed}"
        / "reports"
        / "lot_path_audit.md"
    )
    lot_report_path = _output / lot_report_relative
    if lot_required:
        lot_report_path.parent.mkdir(parents=True, exist_ok=True)
        lot_report_path.write_text("# Valid fake lot audit\n", encoding="utf-8")
    evidence: dict[str, Any] = {
        "schema_version": runner.EVIDENCE_SCHEMA_VERSION,
        "case_key": case.key,
        "variant_id": case.variant_id,
        "seed": case.seed,
        "valid": True,
        "executed_at_utc": "2026-09-03T00:00:00+00:00",
        "graph_sha256": protocol.sha256_file(validated.graph),
        "engine_sha256": protocol.sha256_file(validated.engine),
        "profile_sha256": protocol.sha256_file(
            validated.old_profile
            if case.variant_id == protocol.OLD_VARIANT_ID
            else validated.new_profile
        ),
        "supplier_floors_sha256": protocol.sha256_file(validated.supplier_floors),
        "command_sha256": "fake",
        "summary_sha256": "fake",
        "engine_process_launched": False,
        "complete_case_output_recovered_without_rerun": False,
        "quarantined_incomplete_directory": "",
        "j0_core_state_sha256": f"fake-{case.variant_id}-{case.seed}",
        "j0_pipeline_state_sha256": f"fake-pipeline-{case.variant_id}-{case.seed}",
        "j0_open_campaign_state_sha256": f"fake-campaign-{case.variant_id}-{case.seed}",
        "j0_campaign_quantity_status": (
            "not_evaluable_engine_exports_boundary_digest_only"
        ),
        "lot_trace_required": lot_required,
        "lot_trace_scope": (
            "one_paired_seed_structural_check_not_15_seed_lot_statistics"
            if lot_required
            else "not_requested_for_this_seed"
        ),
        "lot_event_row_count": 10 if lot_required else 0,
        "lot_genealogy_row_count": 5 if lot_required else 0,
        "lot_events_sha256": "fake-lots" if lot_required else "",
        "lot_genealogy_sha256": ("fake-genealogy" if lot_required else ""),
        "lot_unique_id_count": 5 if lot_required else 0,
        "lot_event_type_counts": ({"production_output": 10} if lot_required else {}),
        "lot_audit_required": lot_required,
        "lot_audit_report_sha256": (
            protocol.sha256_file(lot_report_path) if lot_required else ""
        ),
        "retained_lot_audit_report_relative_path": (
            lot_report_relative.as_posix() if lot_required else ""
        ),
        "lot_audit_issue_row_count": 0,
        "lot_audit_severity_counts": {},
        "lot_audit_error_row_count": 0,
        "lot_audit_warning_row_count": 0,
        "lot_audit_issues_sha256": ("fake-lot-audit-issues" if lot_required else ""),
        "lot_trace_lightweight_evidence_preserved": (lot_required),
        "lot_audit_report_retained_after_prune": lot_required,
        "lot_audit_warnings_exposed": 0,
        "daily_demand_signature": protocol.stable_sha256(
            [
                {
                    "product_id": row["product_id"],
                    "daily_demand_signature": row["daily_demand_signature"],
                }
                for row in sorted(service, key=lambda item: item["product_id"])
            ]
        ),
        "service": service,
        "production": production,
        "materials": materials,
        "probability_interpretation_allowed": False,
    }
    evidence["evidence_signature"] = protocol.stable_sha256(evidence)
    return evidence


def test_live_profiles_have_exact_semantic_delta_and_24_materials() -> None:
    source = protocol.validate_source_contract(
        graph=protocol.DEFAULT_GRAPH,
        engine=protocol.DEFAULT_ENGINE,
        supplier_floors=protocol.DEFAULT_FLOORS,
        old_profile=protocol.DEFAULT_OLD_PROFILE,
        new_profile=protocol.DEFAULT_NEW_PROFILE,
    )
    assert len(source["removed_static_pairs"]) == 23
    assert len(source["added_dynamic_pairs"]) == 24
    assert len(source["materials"]) == 24
    assert {row.pair_key for row in source["materials"]} == set(
        source["added_dynamic_pairs"]
    )
    assert "SDC-1450|item:021081" in source["added_dynamic_pairs"]


def test_protocol_is_plan_only_and_validates_without_results(tmp_path: Path) -> None:
    old_hash = protocol.sha256_file(protocol.DEFAULT_OLD_PROFILE)
    graph_hash = protocol.sha256_file(protocol.DEFAULT_GRAPH)
    output, validated = _build_protocol(tmp_path)
    assert len(validated.materials) == 24
    assert {path.name for path in output.iterdir()} == {
        protocol.PROTOCOL_FILE,
        protocol.MATERIAL_SCOPE_FILE,
        protocol.PROFILE_AUDIT_FILE,
    }
    assert validated.manifest["status"] == "planned_not_executed"
    assert validated.manifest["interpretation_limits"]["result_files_present"] is False
    assert validated.manifest["execution"]["isolates_mrp_only"] is False
    assert (
        validated.manifest["interpretation_limits"]["scientifically_reviewable"]
        is False
    )
    assert validated.manifest["interpretation_limits"]["publishable_results"] is False
    assert (
        validated.manifest["capacity_coupling_audit"]["counts"][
            "estimated_changed_direct_capacities"
        ]
        > 0
    )
    capacity_source = validated.manifest["capacity_coupling_audit"][
        "supplier_parameters_source"
    ]
    assert capacity_source["internal_snapshot"] is True
    assert Path(capacity_source["path"]).parent == protocol.DEFAULT_CAPACITY_AUDIT_DIR
    assert (
        sum(
            row.old_variant_requirement_mode
            == "explicit_static_capacity_based_requirement"
            for row in validated.materials
        )
        == 21
    )
    assert all(
        row.candidate_variant_requirement_mode == "explicit_dynamic_mps_bom"
        for row in validated.materials
    )
    assert protocol.sha256_file(protocol.DEFAULT_OLD_PROFILE) == old_hash
    assert protocol.sha256_file(protocol.DEFAULT_GRAPH) == graph_hash


def test_candidate_missing_one_dynamic_pair_is_rejected(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    payload = json.loads(protocol.DEFAULT_NEW_PROFILE.read_text(encoding="utf-8"))
    args = payload["args"]
    index = args.index("SDC-1450,item:021081")
    del args[index - 1 : index + 1]
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exact 24 dynamic"):
        protocol.validate_source_contract(
            graph=protocol.DEFAULT_GRAPH,
            engine=protocol.DEFAULT_ENGINE,
            supplier_floors=protocol.DEFAULT_FLOORS,
            old_profile=protocol.DEFAULT_OLD_PROFILE,
            new_profile=candidate,
        )


def test_protocol_detects_file_tampering(tmp_path: Path) -> None:
    output, _ = _build_protocol(tmp_path)
    with (output / protocol.MATERIAL_SCOPE_FILE).open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(ValueError, match="changed"):
        protocol.validate_protocol(output)


def test_v3_guard_blocks_running_and_accepts_checkpoint(tmp_path: Path) -> None:
    running = tmp_path / "running"
    running.mkdir()
    (running / runner.V3_MANIFEST_FILE).write_text(
        json.dumps(_v3_manifest("running", 123)), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="blocked"):
        runner.validate_v3_stopped(running)
    stopped = _stopped_v3(tmp_path)
    guard = runner.validate_v3_stopped(stopped)
    assert guard["status"] == "paused_preliminary"
    assert guard["active_process_id"] == 0
    assert guard["checkpoint_sha256"]
    assert guard["checkpoint_semantic_membership_validated"] is True


def test_v3_guard_rejects_status_only_checkpoint(tmp_path: Path) -> None:
    stopped = _stopped_v3(tmp_path)
    checkpoint_path = stopped / runner.V3_CHECKPOINT_FILE
    checkpoint_path.write_text(
        json.dumps({"status": "paused_preliminary"}), encoding="utf-8"
    )
    manifest_path = stopped / runner.V3_MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["preliminary_checkpoint_manifest_sha256"] = protocol.sha256_file(
        checkpoint_path
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="does not belong"):
        runner.validate_v3_stopped(stopped)


def test_v3_guard_rejects_campaign_outside_protocol_binding(tmp_path: Path) -> None:
    _output, validated = _build_protocol(tmp_path)
    other = tmp_path / "other-v3"
    other.mkdir()
    other_manifest = _v3_manifest("paused_preliminary", 0)
    other_manifest["runner_signature"] = "another-runner-signature"
    (other / runner.V3_MANIFEST_FILE).write_text(
        json.dumps(other_manifest), encoding="utf-8"
    )
    (other / runner.V3_CHECKPOINT_FILE).write_text(
        json.dumps({"status": "paused_preliminary"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="protocol binding"):
        runner.validate_v3_stopped(
            other,
            validated.manifest["active_campaign_binding"],
        )


def test_commands_keep_old_hybrid_and_make_new_all_dynamic(tmp_path: Path) -> None:
    _output, validated = _build_protocol(tmp_path)
    old = runner.build_engine_command(
        runner.PlannedCase(protocol.OLD_VARIANT_ID, 340282),
        validated,
        tmp_path / "old",
    )
    new = runner.build_engine_command(
        runner.PlannedCase(protocol.NEW_VARIANT_ID, 340282),
        validated,
        tmp_path / "new",
    )
    assert old.count("--mrp-static-requirement-pair") == 23
    assert old.count("--mrp-dynamic-requirement-pair") == 3
    assert new.count("--mrp-static-requirement-pair") == 0
    # Three managed declarations are harmless duplicates resolved as a set by the engine.
    assert new.count("--mrp-dynamic-requirement-pair") == 27
    assert "--supplier-risk-events-csv" not in old
    assert "--supplier-risk-events-csv" not in new
    assert "--lot-trace" in old
    assert "--skip-lot-audit" not in old
    non_trace = runner.build_engine_command(
        runner.PlannedCase(protocol.OLD_VARIANT_ID, 340283),
        validated,
        tmp_path / "non-trace",
    )
    assert "--no-lot-trace" in non_trace
    assert "--skip-lot-audit" in non_trace
    assert old[-1] == "--no-supplier-state-dependent-risks"
    assert new[-1] == "--no-supplier-state-dependent-risks"


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_metric_extraction_covers_every_material_and_product(tmp_path: Path) -> None:
    _output, validated = _build_protocol(tmp_path)
    data = tmp_path / "case" / "data"
    bom_requirements = runner._bom_requirements(validated)
    executed_output_qty = 10.0
    stocks: list[dict[str, Any]] = []
    arrivals: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    for material in validated.materials:
        consumed_qty = sum(
            executed_output_qty * requirement_per_output_unit
            for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                material.pair_key
            ]
        )
        for day in range(protocol.MEASURED_DAYS):
            stocks.append(
                {
                    "day": day,
                    "node_id": material.node_id,
                    "item_id": material.item_id,
                    "stock_before_production": 100.0 + consumed_qty,
                    "stock_end_of_day": 100.0,
                }
            )
            arrivals.append(
                {
                    "day": day,
                    "node_id": material.node_id,
                    "item_id": material.item_id,
                    "arrived_qty": consumed_qty,
                    "uom": material.uom,
                }
            )
            traces.append(
                {
                    "day": day,
                    "node_id": material.node_id,
                    "item_id": material.item_id,
                    "target_stock_qty": 20.0 * consumed_qty,
                    "target_demand_signal_qty": consumed_qty,
                    "bb_backlog_qty": 0.0,
                }
            )
        orders.append(
            {
                "day": 0,
                "node_id": material.node_id,
                "item_id": material.item_id,
                "release_qty": consumed_qty,
                "planned_receipt_qty": consumed_qty,
            }
        )
    _write_csv(
        data / "production_input_stocks_daily.csv",
        ["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
        stocks,
    )
    _write_csv(
        data / "production_input_replenishment_arrivals_daily.csv",
        ["day", "node_id", "item_id", "arrived_qty", "uom"],
        arrivals,
    )
    _write_csv(
        data / "mrp_trace_daily.csv",
        [
            "day",
            "node_id",
            "item_id",
            "target_stock_qty",
            "target_demand_signal_qty",
            "bb_backlog_qty",
        ],
        traces,
    )
    _write_csv(
        data / "mrp_orders_daily.csv",
        ["day", "node_id", "item_id", "release_qty", "planned_receipt_qty"],
        orders,
    )
    shipments = []
    for index, material in enumerate(validated.materials):
        consumed_qty = sum(
            executed_output_qty * requirement_per_output_unit
            for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                material.pair_key
            ]
        )
        for day in range(protocol.MEASURED_DAYS):
            shipments.append(
                {
                    "day": day,
                    "risk_decision_day": day,
                    "arrival_day": day,
                    "src_node_id": f"supplier-{index}",
                    "dst_node_id": material.node_id,
                    "item_id": material.item_id,
                    "shipped_qty": consumed_qty,
                    "uom": material.uom,
                }
            )
    _write_csv(
        data / "production_supplier_shipments_daily.csv",
        [
            "day",
            "risk_decision_day",
            "arrival_day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "shipped_qty",
            "uom",
        ],
        shipments,
    )
    supplier_parameters = [
        {
            "supplier_id": f"supplier-{index}",
            "dst_node_id": material.node_id,
            "item_id": material.item_id,
            "capacity_basis": "propagated_dynamic_demand",
            "nominal_capacity_qty_per_day": sum(
                executed_output_qty * requirement_per_output_unit
                for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                    material.pair_key
                ]
            ),
            "effective_capacity_qty_per_day": sum(
                executed_output_qty * requirement_per_output_unit
                for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                    material.pair_key
                ]
            ),
            "applied_capacity_scale": 1.0,
            "downstream_signal_qty_per_day": sum(
                executed_output_qty * requirement_per_output_unit
                for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                    material.pair_key
                ]
            ),
            "explicit_capacity_qty_per_day": 0.0,
            "process_capacity_qty_per_day": 0.0,
            "downstream_requirement_qty_per_day": sum(
                executed_output_qty * requirement_per_output_unit
                for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                    material.pair_key
                ]
            ),
            "external_procurement_daily_need_qty": sum(
                executed_output_qty * requirement_per_output_unit
                for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                    material.pair_key
                ]
            ),
            "external_procurement_nominal_capacity_qty_per_day": sum(
                executed_output_qty * requirement_per_output_unit
                for _node_id, _output_item_id, requirement_per_output_unit in bom_requirements[
                    material.pair_key
                ]
            )
            / 0.7,
            "external_procurement_target_utilization": 0.7,
            "external_procurement_capacity_profile": "qualified_pharma",
            "external_procurement_capacity_basis": "max_downstream_pull",
            "external_procurement_pipeline_target_qty": 0.0,
            "external_procurement_initial_pipeline_seed_qty": 0.0,
        }
        for index, material in enumerate(validated.materials)
    ]
    duplicate_lane = dict(supplier_parameters[0])
    duplicate_lane["supplier_id"] = "supplier-duplicate-lane"
    supplier_parameters.append(duplicate_lane)
    _write_csv(
        data / "supplier_nominal_parameters.csv",
        [
            "supplier_id",
            "dst_node_id",
            "item_id",
            "capacity_basis",
            "nominal_capacity_qty_per_day",
            "effective_capacity_qty_per_day",
            "applied_capacity_scale",
            "downstream_signal_qty_per_day",
            "explicit_capacity_qty_per_day",
            "process_capacity_qty_per_day",
            "downstream_requirement_qty_per_day",
            "external_procurement_daily_need_qty",
            "external_procurement_nominal_capacity_qty_per_day",
            "external_procurement_target_utilization",
            "external_procurement_capacity_profile",
            "external_procurement_capacity_basis",
            "external_procurement_pipeline_target_qty",
            "external_procurement_initial_pipeline_seed_qty",
        ],
        supplier_parameters,
    )
    service_rows = []
    production_rows = []
    output_pairs = sorted(
        {
            (node_id, output_item_id)
            for requirements in bom_requirements.values()
            for node_id, output_item_id, _ratio in requirements
        }
    )
    for day in range(protocol.MEASURED_DAYS):
        for product in runner.PRODUCTS:
            service_rows.append(
                {
                    "day": day,
                    "node_id": "C-XXXXX",
                    "item_id": f"item:{product}",
                    "demand_qty": 10.0,
                    "required_with_backlog_qty": 10.0,
                    "served_qty": 10.0,
                    "backlog_end_qty": 0.0,
                }
            )
        for node_id, output_item_id in output_pairs:
            production_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "item_id": output_item_id,
                    "executed_qty": executed_output_qty,
                    "released_qty": executed_output_qty,
                }
            )
    _write_csv(
        data / "production_demand_service_daily.csv",
        [
            "day",
            "node_id",
            "item_id",
            "demand_qty",
            "required_with_backlog_qty",
            "served_qty",
            "backlog_end_qty",
        ],
        service_rows,
    )
    _write_csv(
        data / "production_output_products_daily.csv",
        ["day", "node_id", "item_id", "executed_qty", "released_qty"],
        production_rows,
    )
    material_metrics = runner._material_metrics(
        tmp_path / "case", validated, protocol.NEW_VARIANT_ID
    )
    service, production = runner._system_metrics(tmp_path / "case")
    assert len(material_metrics) == 24
    assert all(row["zero_stock_day_count"] == 0 for row in material_metrics)
    assert all(row["stock_balance_valid_J1_J719"] for row in material_metrics)
    assert all(row["bom_consumption_balance_valid"] for row in material_metrics)
    assert all(
        row["supplier_direct_nominal_capacity_total_qty_per_day"] > 0.0
        for row in material_metrics
    )
    assert all(
        row["external_procurement_nominal_capacity_total_qty_per_day"] > 0.0
        for row in material_metrics
    )
    multi_lane_metric = next(
        row
        for row in material_metrics
        if row["pair_key"]
        == f"{supplier_parameters[0]['dst_node_id']}|{supplier_parameters[0]['item_id']}"
    )
    assert multi_lane_metric[
        "supplier_downstream_requirement_lane_row_sum_qty_per_day"
    ] == pytest.approx(
        2.0 * multi_lane_metric["supplier_downstream_requirement_pair_qty_per_day"]
    )
    assert (
        multi_lane_metric["supplier_downstream_requirement_pair_values_all_equal"]
        is True
    )
    assert all(
        math.isclose(
            row["arrival_total_qty"], row["bom_expected_consumption_total_qty"]
        )
        for row in material_metrics
    )
    assert all(
        row["requirement_mode_in_variant"] == "explicit_dynamic_mps_bom"
        for row in material_metrics
    )
    old_material_metrics = runner._material_metrics(
        tmp_path / "case", validated, protocol.OLD_VARIANT_ID
    )
    assert (
        sum(
            row["requirement_mode_in_variant"]
            == "explicit_static_capacity_based_requirement"
            for row in old_material_metrics
        )
        == 21
    )
    assert (
        sum(
            row["requirement_mode_in_variant"] == "explicit_dynamic_mps_bom"
            for row in old_material_metrics
        )
        == 3
    )
    assert {row["product_id"] for row in service} == set(runner.PRODUCTS)
    assert {row["product_id"] for row in production} == set(runner.PRODUCTS)

    stocks[1]["stock_before_production"] = (
        float(stocks[1]["stock_before_production"]) + 1.0
    )
    _write_csv(
        data / "production_input_stocks_daily.csv",
        ["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
        stocks,
    )
    with pytest.raises(ValueError, match="stock balance failed"):
        runner._material_metrics(tmp_path / "case", validated, protocol.NEW_VARIANT_ID)
    stocks[1]["stock_before_production"] = (
        float(stocks[1]["stock_before_production"]) - 1.0
    )
    _write_csv(
        data / "production_input_stocks_daily.csv",
        ["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
        stocks,
    )
    production_rows[0]["executed_qty"] = float(production_rows[0]["executed_qty"]) + 1.0
    _write_csv(
        data / "production_output_products_daily.csv",
        ["day", "node_id", "item_id", "executed_qty", "released_qty"],
        production_rows,
    )
    with pytest.raises(ValueError, match="BOM consumption balance failed"):
        runner._material_metrics(tmp_path / "case", validated, protocol.NEW_VARIANT_ID)


def test_smoke_custom_executor_builds_exact_paired_tables(tmp_path: Path) -> None:
    protocol_dir, _validated = _build_protocol(tmp_path)
    v3 = _stopped_v3(tmp_path)
    output = tmp_path / "smoke"
    manifest = runner.run_comparison(
        protocol_dir=protocol_dir,
        active_campaign_dir=v3,
        output_dir=output,
        mode="smoke",
        workers=2,
        case_executor=_signed_fake_evidence,
    )
    assert manifest["status"] == "smoke_complete_nonreusable"
    assert manifest["completed_engine_run_count"] == 6
    assert manifest["paired_seed_count"] == 3
    assert manifest["publishable_results"] is False
    assert manifest["scientifically_reviewable"] is False
    assert manifest["isolates_mrp_only"] is False
    assert manifest["source_v3_unchanged_during_comparison"] is True
    assert manifest["lot_path_audit_reports_retained_and_hash_verified"] is True
    assert len(protocol.read_csv(output / "material_seed_metrics.csv")) == 144
    assert len(protocol.read_csv(output / "paired_material_metrics.csv")) == 72
    assert len(protocol.read_csv(output / "material_comparison_summary.csv")) == 24
    assert len(protocol.read_csv(output / "system_comparison_summary.csv")) == 2


def test_smoke_directory_cannot_be_reused_for_compare15(tmp_path: Path) -> None:
    protocol_dir, _validated = _build_protocol(tmp_path)
    v3 = _stopped_v3(tmp_path)
    output = tmp_path / "output"
    runner.run_comparison(
        protocol_dir=protocol_dir,
        active_campaign_dir=v3,
        output_dir=output,
        mode="smoke",
        case_executor=_signed_fake_evidence,
    )
    with pytest.raises(ValueError, match="another comparison scope"):
        runner.run_comparison(
            protocol_dir=protocol_dir,
            active_campaign_dir=v3,
            output_dir=output,
            mode="compare15",
            case_executor=_signed_fake_evidence,
        )


def test_paired_daily_demand_mismatch_is_rejected(tmp_path: Path) -> None:
    _protocol_dir, validated = _build_protocol(tmp_path)
    seed = protocol.SMOKE_SEEDS[0]
    old_case = runner.PlannedCase(protocol.OLD_VARIANT_ID, seed)
    new_case = runner.PlannedCase(protocol.NEW_VARIANT_ID, seed)
    old = _signed_fake_evidence(old_case, validated, tmp_path)
    new = _signed_fake_evidence(new_case, validated, tmp_path)
    new["service"][0]["daily_demand_signature"] = "different-daily-demand"
    new["daily_demand_signature"] = protocol.stable_sha256(
        [
            {
                "product_id": row["product_id"],
                "daily_demand_signature": row["daily_demand_signature"],
            }
            for row in sorted(new["service"], key=lambda item: item["product_id"])
        ]
    )
    unsigned = dict(new)
    unsigned.pop("evidence_signature")
    new["evidence_signature"] = protocol.stable_sha256(unsigned)
    with pytest.raises(ValueError, match="daily client demand differs"):
        runner._flatten_results(
            {old_case.key: old, new_case.key: new},
            [seed],
        )


def test_summary_includes_distribution_statistics() -> None:
    rows = [
        {
            "product_id": "268091",
            "old_service": float(value + 10),
            "new_service": float(value + 11),
            "delta_service": float(value),
        }
        for value in (1, 2, 3, 4, 5)
    ]
    summary = runner._summary_rows(rows, "product_id")[0]
    assert summary["mean_delta_service"] == 3.0
    assert summary["median_delta_service"] == 3.0
    assert summary["p10_delta_service"] == pytest.approx(1.4)
    assert summary["p90_delta_service"] == pytest.approx(4.6)
    assert summary["stddev_delta_service"] == pytest.approx(math.sqrt(2.0))
    assert summary["median_old_service"] == 13.0
    assert summary["median_new_service"] == 14.0


def test_evidence_rejects_unbounded_service_and_impossible_supplier_flow(
    tmp_path: Path,
) -> None:
    _protocol_dir, validated = _build_protocol(tmp_path)
    case = runner.PlannedCase(protocol.NEW_VARIANT_ID, protocol.SMOKE_SEEDS[1])
    evidence = _signed_fake_evidence(case, validated, tmp_path)
    evidence["service"][0]["fill_rate"] = 1.01
    unsigned = dict(evidence)
    unsigned.pop("evidence_signature")
    evidence["evidence_signature"] = protocol.stable_sha256(unsigned)
    with pytest.raises(ValueError, match="finite/bounded service"):
        runner._validate_evidence(evidence, case, validated)

    evidence = _signed_fake_evidence(case, validated, tmp_path)
    evidence["materials"][0]["supplier_shipment_arriving_J0_J719_qty"] = (
        evidence["materials"][0]["arrival_total_qty"] + 1.0
    )
    unsigned = dict(evidence)
    unsigned.pop("evidence_signature")
    evidence["evidence_signature"] = protocol.stable_sha256(unsigned)
    with pytest.raises(ValueError, match="lower-bound violation"):
        runner._validate_evidence(evidence, case, validated)


def test_lot_audit_error_is_fatal_and_retained_report_hash_is_checked(
    tmp_path: Path,
) -> None:
    _protocol_dir, validated = _build_protocol(tmp_path)
    case = runner.PlannedCase(protocol.NEW_VARIANT_ID, protocol.LOT_TRACE_SEED)
    evidence = _signed_fake_evidence(case, validated, tmp_path)
    evidence["lot_audit_issue_row_count"] = 1
    evidence["lot_audit_severity_counts"] = {"error": 1}
    evidence["lot_audit_error_row_count"] = 1
    unsigned = dict(evidence)
    unsigned.pop("evidence_signature")
    evidence["evidence_signature"] = protocol.stable_sha256(unsigned)
    with pytest.raises(ValueError, match="Lot trace evidence scope mismatch"):
        runner._validate_evidence(evidence, case, validated, tmp_path)

    evidence = _signed_fake_evidence(case, validated, tmp_path)
    report = tmp_path / evidence["retained_lot_audit_report_relative_path"]
    report.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Retained lot audit report changed"):
        runner._validate_evidence(evidence, case, validated, tmp_path)


def test_campaign_manifest_change_during_comparison_fails_closed(
    tmp_path: Path,
) -> None:
    protocol_dir, _validated = _build_protocol(tmp_path)
    v3 = _stopped_v3(tmp_path)
    output = tmp_path / "comparison-mutated-source"
    changed = False

    def mutating_executor(
        case: runner.PlannedCase,
        validated: protocol.ValidatedProtocol,
        output_dir: Path,
    ) -> dict[str, Any]:
        nonlocal changed
        evidence = _signed_fake_evidence(case, validated, output_dir)
        if not changed:
            manifest_path = v3 / runner.V3_MANIFEST_FILE
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["mutable_test_marker"] = "changed-during-comparison"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            changed = True
        return evidence

    with pytest.raises(ValueError, match="changed during comparison"):
        runner.run_comparison(
            protocol_dir=protocol_dir,
            active_campaign_dir=v3,
            output_dir=output,
            mode="smoke",
            workers=1,
            case_executor=mutating_executor,
        )
    failed = json.loads((output / runner.MANIFEST_FILE).read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["publishable_results"] is False
    assert failed["scientifically_reviewable"] is False
    assert "source_v3_mutated" not in failed


def test_incomplete_case_directory_is_preserved_then_recreated(tmp_path: Path) -> None:
    output = tmp_path / "comparison"
    case = runner.PlannedCase(protocol.OLD_VARIANT_ID, protocol.SMOKE_SEEDS[0])
    partial = output / "cases" / case.variant_id / f"seed_{case.seed}"
    partial.mkdir(parents=True)
    (partial / "partial.log").write_text("interrupted", encoding="utf-8")
    case_dir, reused, quarantine = runner._prepare_case_directory(output, case)
    assert reused is False
    assert case_dir.is_dir()
    assert not any(case_dir.iterdir())
    quarantined = Path(quarantine)
    assert quarantined.is_dir()
    assert (quarantined / "partial.log").read_text(encoding="utf-8") == "interrupted"


def test_valid_orphan_evidence_is_reconciled_into_ledger(tmp_path: Path) -> None:
    _protocol_dir, validated = _build_protocol(tmp_path)
    output = tmp_path / "orphan-recovery"
    output.mkdir()
    signature = "test-campaign-signature"
    ledger = runner._new_ledger(signature)
    runner._write_json(output / runner.LEDGER_FILE, ledger)
    case = runner.PlannedCase(protocol.NEW_VARIANT_ID, protocol.SMOKE_SEEDS[1])
    planned = {case.key: case}
    evidence = _signed_fake_evidence(case, validated, output)
    orphan_path = runner._evidence_path(output, case)
    orphan_path.parent.mkdir(parents=True)
    runner._write_json(orphan_path, evidence)
    orphan_hash = protocol.sha256_file(orphan_path)

    recovered = runner._load_evidence(output, ledger, planned, validated)

    assert set(recovered) == {case.key}
    assert orphan_path.is_file()
    assert protocol.sha256_file(orphan_path) == orphan_hash
    assert ledger["case_files"][case.key] == orphan_path.relative_to(output).as_posix()
    assert len(ledger["reconciled_orphan_evidence"]) == 1
    persisted = protocol.read_json(output / runner.LEDGER_FILE)
    assert persisted["case_file_sha256"][case.key] == orphan_hash


def test_invalid_orphan_evidence_is_archived_without_deletion(
    tmp_path: Path,
) -> None:
    _protocol_dir, validated = _build_protocol(tmp_path)
    output = tmp_path / "invalid-orphan-recovery"
    output.mkdir()
    ledger = runner._new_ledger("test-campaign-signature")
    runner._write_json(output / runner.LEDGER_FILE, ledger)
    case = runner.PlannedCase(protocol.NEW_VARIANT_ID, protocol.SMOKE_SEEDS[1])
    orphan_path = runner._evidence_path(output, case)
    orphan_path.parent.mkdir(parents=True)
    original = '{"case_key":"incomplete"}\n'
    orphan_path.write_text(original, encoding="utf-8")

    recovered = runner._load_evidence(
        output,
        ledger,
        {case.key: case},
        validated,
    )

    assert recovered == {}
    assert not orphan_path.exists()
    records = ledger["quarantined_invalid_orphan_evidence"]
    assert len(records) == 1
    archived = output / records[0]["quarantine_relative_path"]
    assert archived.is_file()
    assert archived.read_text(encoding="utf-8") == original


def test_lock_recovery_archives_dead_pid_and_never_breaks_active_pid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_dir = tmp_path / "active-lock"
    active_dir.mkdir()
    active_lock = active_dir / runner.LOCK_FILE
    active_lock.write_text(f"{os.getpid()}\n", encoding="ascii")
    monkeypatch.setattr(runner, "_process_is_running", lambda _pid: True)
    with pytest.raises(RuntimeError, match="active PID"):
        with runner._lock(active_dir):
            pass
    assert active_lock.read_text(encoding="ascii").strip() == str(os.getpid())
    assert not (active_dir / "abandoned_locks").exists()

    unknown_dir = tmp_path / "unknown-lock"
    unknown_dir.mkdir()
    unknown_lock = unknown_dir / runner.LOCK_FILE
    unknown_lock.write_text("not-a-pid\n", encoding="ascii")
    with pytest.raises(RuntimeError, match="no valid recorded PID"):
        with runner._lock(unknown_dir):
            pass
    assert unknown_lock.read_text(encoding="ascii") == "not-a-pid\n"
    assert not (unknown_dir / runner.ABANDONED_LOCK_DIR).exists()

    dead_dir = tmp_path / "dead-lock"
    dead_dir.mkdir()
    dead_lock = dead_dir / runner.LOCK_FILE
    dead_pid = 2147483647
    dead_lock.write_text(f"{dead_pid}\n", encoding="ascii")
    monkeypatch.setattr(runner, "_process_is_running", lambda _pid: False)
    with runner._lock(dead_dir):
        assert dead_lock.read_text(encoding="ascii").strip() == str(os.getpid())
    assert not dead_lock.exists()
    archives = list((dead_dir / runner.ABANDONED_LOCK_DIR).iterdir())
    assert len(archives) == 1
    assert archives[0].read_text(encoding="ascii").strip() == str(dead_pid)


def test_runner_supports_direct_file_execution_from_outside_repo(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, str(Path(runner.__file__).resolve()), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--protocol-dir" in completed.stdout
