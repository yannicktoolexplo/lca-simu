from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_post_priority_extensions as extensions,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _source_artifact(tmp_path: Path) -> Path:
    source = tmp_path / "network_complete"
    source.mkdir()
    gates = {
        "baseline_both_products_on_due_at_least_95_all_seeds_pass": True,
        "all_metric_rows_valid_pass": True,
        "j0_state_hash_pairing_100pct_pass": True,
        "input_graph_hash_pairing_100pct_pass": True,
        "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": True,
        "all_release_gates_pass": True,
    }
    _write_json(
        source / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "campaign_signature": "source-signature",
            "graph_sha256": "graph-hash",
            "profile_sha256": "profile-hash",
            "engine_sha256": "engine-hash",
            "v4_extraction_core_sha256": "extraction-hash",
            "confirmation_seed_count": 30,
            "priority_set_stabilized": True,
            "rank3_rank4_interval_separated": True,
            "scientific_release_gates": gates,
        },
    )
    lane_specs = (
        ("chain_a", "SDC-VD0519670A", "item:001848", "M-1810", "268091", 45),
        ("chain_b", "SDC-VD0519670A", "item:029313", "M-1810", "268091", 90),
        ("chain_c", "SDC-VD0520132A", "item:038005", "M-1430", "268967", 190),
        ("chain_d", "SDC-VD0520132A", "item:049371", "M-1810", "268091", 270),
    )
    active_rows = []
    for chain_id, supplier, item, destination, product, start in lane_specs:
        active_rows.append(
            {
                "chain_id": chain_id,
                "supplier_id": supplier,
                "item_id": item,
                "dst_node_id": destination,
                "edge_id": f"edge:{chain_id}",
                "target_product_id": product,
                "planned_lead_days": 21,
                "active_window_start_day": start,
                "active_window_end_day": start + 179,
                "reference_total_shipped_qty": 1000,
                "reference_total_pulled_qty": 1000,
                "reference_active_window_shipped_qty": 500,
                "reference_active_window_pulled_qty": 500,
                "reference_first_shipment_day": start,
                "reference_last_shipment_day": start + 179,
                "reference_shipment_day_count": 10,
            }
        )
    _write_csv(source / "active_lane_reference.csv", active_rows)
    modes = tuple(sorted(extensions.network.MECHANISM_BY_KEY))
    scenario_rows = []
    scenario_by_chain_mode: dict[tuple[str, str], str] = {}
    for lane in active_rows:
        for mode in modes:
            scenario_id = f"{lane['chain_id']}__{mode}__severe"
            scenario_by_chain_mode[(lane["chain_id"], mode)] = scenario_id
            mechanism = extensions.network.MECHANISM_BY_KEY[mode]
            scenario_rows.append(
                {
                    "scenario_id": scenario_id,
                    "chain_id": lane["chain_id"],
                    "supplier_id": lane["supplier_id"],
                    "item_id": lane["item_id"],
                    "dst_node_id": lane["dst_node_id"],
                    "target_product_id": lane["target_product_id"],
                    "failure_mode": mode,
                    "level_code": "severe",
                    "mechanism_value": mechanism.values[1],
                    "mechanism_unit": mechanism.unit,
                }
            )
    _write_csv(source / "scenario_design.csv", scenario_rows)
    retained_modes = (
        "transport_delay",
        "supply_availability",
        "transport_delay",
        "supply_availability",
    )
    ranking_rows = []
    for rank, (lane, retained_mode) in enumerate(
        zip(active_rows, retained_modes, strict=True), 1
    ):
        ranking_rows.append(
            {
                "lane_sensitivity_rank": rank,
                "chain_id": lane["chain_id"],
                "supplier_id": lane["supplier_id"],
                "item_id": lane["item_id"],
                "dst_node_id": lane["dst_node_id"],
                "target_product_id": lane["target_product_id"],
                "worst_scenario_id": scenario_by_chain_mode[
                    (lane["chain_id"], retained_mode)
                ],
                "worst_failure_mode": retained_mode,
                "evidence_stage": "confirmation_30_realisations",
            }
        )
    _write_csv(
        source / "confirmation_lane_sensitivity_ranking.csv", ranking_rows
    )
    confirmation_rows: list[dict] = []
    confirmed_modes = ("transport_delay", "supply_availability")
    first_seed = 1001
    baseline_first_run = source / "cases" / "baseline_nominal" / f"seed_{first_seed}"
    for seed in range(1001, 1031):
        traced = seed == first_seed
        baseline_run = source / "cases" / "baseline_nominal" / f"seed_{seed}"
        confirmation_rows.append(
            {
                "scenario_id": "baseline_nominal",
                "seed": seed,
                "valid": True,
                "j0_state_sha256": f"j0-{seed}",
                "input_sha256": "graph-hash",
                "lot_trace_required_for_paired_seed_block": traced,
                "run_dir": baseline_run,
            }
        )
        for lane in active_rows:
            for mode in confirmed_modes:
                scenario_id = scenario_by_chain_mode[(lane["chain_id"], mode)]
                stress_run = source / "cases" / scenario_id / f"seed_{seed}"
                confirmation_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "chain_id": lane["chain_id"],
                        "seed": seed,
                        "valid": True,
                        "j0_state_sha256": f"j0-{seed}",
                        "input_sha256": "graph-hash",
                        "lot_trace_required_for_paired_seed_block": traced,
                        "stress_start_day": lane["active_window_start_day"],
                        "stress_end_day": lane["active_window_end_day"],
                        "run_dir": stress_run,
                    }
                )
    _write_csv(source / "confirmation_metrics.csv", confirmation_rows)
    _write_csv(
        baseline_first_run / "data" / "production_lot_events.csv",
        [{"event_id": "baseline-event", "lot_id": "B"}],
    )
    _write_csv(
        baseline_first_run / "data" / "production_lot_genealogy.csv",
        [{"parent_lot_id": "B", "child_lot_id": "BP"}],
    )
    for lane, retained_mode in zip(active_rows[:3], retained_modes[:3], strict=True):
        scenario_id = scenario_by_chain_mode[(lane["chain_id"], retained_mode)]
        stress_run = source / "cases" / scenario_id / f"seed_{first_seed}"
        _write_csv(
            stress_run / "data" / "production_lot_events.csv",
            [{"event_id": f"stress-{lane['chain_id']}", "lot_id": "S"}],
        )
        _write_csv(
            stress_run / "data" / "production_lot_genealogy.csv",
            [{"parent_lot_id": "S", "child_lot_id": "SP"}],
        )
    common_rows = []
    supplier_windows = {
        "SDC-VD0519670A": (10, 189),
        "SDC-VD0520132A": (200, 379),
    }
    for supplier, (start, end) in supplier_windows.items():
        supplier_lanes = [
            lane for lane in active_rows if lane["supplier_id"] == supplier
        ]
        for mode in modes:
            mechanism = extensions.network.MECHANISM_BY_KEY[mode]
            common_rows.append(
                {
                    "scenario_id": f"common__{supplier}__{mode}",
                    "supplier_id": supplier,
                    "affected_lane_count": 2,
                    "affected_chain_ids": "|".join(
                        lane["chain_id"] for lane in supplier_lanes
                    ),
                    "failure_mode": mode,
                    "level_code": "severe",
                    "mechanism_value": mechanism.values[1],
                    "mechanism_unit": mechanism.unit,
                    "stress_start_day": start,
                    "stress_end_day": end,
                }
            )
    _write_csv(
        source / "multi_lane_supplier_common_cause_design.csv", common_rows
    )
    # These three source files are provenance contracts from the main campaign.
    # The additive module derives and validates its own complete 30-seed designs.
    _write_csv(
        source / "temporal_robustness_extension_design.csv",
        [{"execution_status": "planned_not_executed"}],
    )
    _write_csv(
        source / "priority_severe_mode_extension_design.csv",
        [{"execution_status": "planned_not_executed"}],
    )
    _write_json(
        source / "post_priority_extensions_manifest.json",
        {"status": "planned_not_executed"},
    )
    return source


def test_direct_script_help_works_from_repository_root():
    script = Path(extensions.__file__).resolve()
    repo_root = script.parents[3]
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--network-artifact" in completed.stdout
    assert "--validate-plan" in completed.stdout


def test_plan_is_exact_signed_additive_and_non_executable(tmp_path: Path):
    source = _source_artifact(tmp_path)
    source_hashes_before = {
        path.relative_to(source).as_posix(): extensions._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "extension_plan"
    )
    validation = extensions.validate_plan_artifact(output)
    assert validation["valid"] is True
    manifest = json.loads(
        (output / "post_priority_extensions_plan_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["status"] == "planned_not_executed"
    assert manifest["execution_enabled"] is False
    assert manifest["subprocess_or_engine_call_present"] is False
    assert manifest["main_lane_ranking_mutated"] is False
    assert manifest["planned_case_counts"] == {
        "paired_metric_baseline_references": 30,
        "multi_lane_common_cause_stress_cases": 240,
        "temporal_robustness_stress_cases": 360,
        "priority_four_business_causes_stress_cases": 360,
        "causal_lot_stress_cases": 3,
        "follow_up_lane_count": 3,
        "dedicated_lot_trace_baseline_new_runs": 0,
        "dedicated_lot_trace_baseline_logical_reference_count": 0,
        "logical_stress_comparison_count": 963,
        "logical_case_reference_count": 993,
        "reused_case_count": 210,
        "reused_case_reference_link_count": 216,
        "source_referenced_unique_case_count": 210,
        "source_referenced_case_link_count": 216,
        "source_baseline_reference_count": 30,
        "source_stress_reused_unique_case_count": 180,
        "source_evidence_alias_link_count": 6,
        "design_declared_new_run_flag_reference_count": 810,
        "design_declared_new_baseline_reference_count": 30,
        "design_declared_new_stress_run_count": 780,
        "new_baseline_engine_run_count": 30,
        "new_stress_engine_run_count": 780,
        "new_run_count": 810,
        "runner_materialized_baseline_physical_run_count": 30,
        "expected_engine_physical_run_count": 810,
        "unique_physical_case_count_after_reuse": 810,
        "logical_comparison_and_baseline_reference_count": 993,
        "double_counted_evidence_case_count": 0,
    }
    assert not any("ranking" in path.name for path in output.iterdir())
    source_hashes_after = {
        path.relative_to(source).as_posix(): extensions._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }
    assert source_hashes_after == source_hashes_before


def test_common_temporal_and_four_cause_designs_are_separate_and_balanced(
    tmp_path: Path,
):
    source = _source_artifact(tmp_path)
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    common = _read_csv(output / "multi_lane_supplier_common_cause_design.csv")
    assert len(common) == 240
    assert {row["supplier_id"] for row in common} == set(
        extensions.EXPECTED_MULTI_LANE_SUPPLIERS
    )
    assert {row["failure_mode"] for row in common} == set(
        extensions.network.MECHANISM_BY_KEY
    )
    assert {int(row["affected_lane_count"]) for row in common} == {2}
    assert all(len(row["affected_lanes"].split(";")) == 2 for row in common)
    assert all("ranking_effect" not in row for row in common)
    assert {row["case_action"] for row in common} == {"new_run_required"}


def test_common_cause_scope_rejects_an_unreported_third_multi_lane_supplier(
    tmp_path: Path,
):
    source = _source_artifact(tmp_path)
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan_with_exact_common_scope"
    )
    active_lanes = _read_csv(source / "active_lane_reference.csv")
    active_lanes.extend(
        [
            {
                **active_lanes[0],
                "chain_id": f"third_multi_{index}",
                "supplier_id": "SDC-THIRD-MULTI",
            }
            for index in (1, 2)
        ]
    )
    with pytest.raises(ValueError, match="common-cause incomplet"):
        extensions.build_common_cause_design(
            SimpleNamespace(active_lanes=active_lanes)
        )

    temporal = _read_csv(output / "temporal_robustness_design.csv")
    assert len(temporal) == 360
    assert {
        (int(row["stress_start_day"]), int(row["stress_end_day"]))
        for row in temporal
    } == set(extensions.CALENDAR_WINDOWS)
    assert {int(row["selection_slot"]) for row in temporal} == {
        1,
        2,
        3,
    }
    assert all(row["slot_order_has_scientific_meaning"] == "False" for row in temporal)
    assert all("priority_rank_from_main_lane_test" not in row for row in temporal)
    assert all("ranking_effect" not in row for row in temporal)

    four_causes = _read_csv(
        output / "priority_four_business_causes_design.csv"
    )
    assert len(four_causes) == 360
    assert {row["failure_mode"] for row in four_causes} == set(
        extensions.network.MECHANISM_BY_KEY
    )
    for slot in (1, 2, 3):
        slot_rows = [
            row
            for row in four_causes
            if int(row["selection_slot"]) == slot
        ]
        assert len(slot_rows) == 120
        assert len({int(row["seed"]) for row in slot_rows}) == 30
        assert all(
            row["slot_order_has_scientific_meaning"] == "False"
            for row in slot_rows
        )
    reused = [
        row
        for row in four_causes
        if row["case_action"] == "reuse_existing_confirmation_case"
    ]
    new = [row for row in four_causes if row["case_action"] == "new_run_required"]
    assert len(reused) == 180
    assert len(new) == 180
    assert {row["failure_mode"] for row in reused} == {
        "transport_delay",
        "supply_availability",
    }
    assert {row["failure_mode"] for row in new} == {
        "quality_hold",
        "quality_yield",
    }


def test_boundary_nonseparation_group_is_followed_up_in_full_without_rank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    suppliers = [f"SUP-{index}" for index in range(1, 5)]
    lanes = []
    severe = {}
    rankings = []
    driver_mappings = []
    for index, supplier in enumerate(suppliers, 1):
        chain = f"chain_{index}"
        scenario = f"{chain}__transport_delay__120"
        lane = {
            "chain_id": chain,
            "supplier_id": supplier,
            "item_id": f"item:{index}",
            "dst_node_id": "M-1810",
            "edge_id": f"edge:{index}",
            "target_product_id": "268091",
            "active_window_start_day": "45",
            "active_window_end_day": "224",
        }
        lanes.append(lane)
        severe[(chain, "transport_delay")] = {
            **lane,
            "scenario_id": scenario,
            "failure_mode": "transport_delay",
        }
        rankings.append(
            {
                "aggregation_scope": extensions.boundary.SUPPLIER_ENVELOPE_SCOPE,
                "metric_key": "horizon_on_due_service_delta",
                "supplier_id": supplier,
                "driver_chain_id": chain,
                "driver_scenario_id": scenario,
                "driver_failure_mode": "transport_delay",
            }
        )
        driver_mappings.append(
            {
                "supplier_id": supplier,
                "driver_chain_id": chain,
                "driver_scenario_id": scenario,
                "driver_failure_mode": "transport_delay",
                "driver_lane_uniqueness_claimed": False,
                "driver_selection_rule": (
                    "worst_mean_service_scenario_then_identifier_tie_break"
                ),
            }
        )
    lanes.extend(
        [
            {
                **lanes[0],
                "chain_id": "chain_1_secondary",
                "item_id": "item:secondary_1",
                "edge_id": "edge:secondary_1",
            },
            {
                **lanes[1],
                "chain_id": "chain_2_secondary",
                "item_id": "item:secondary_2",
                "edge_id": "edge:secondary_2",
            },
        ]
    )
    audit = {
        "schema_version": extensions.boundary.SCHEMA_VERSION,
        "scoped_descriptive_priority_set_display_allowed": False,
        "displayed_scoped_priority_supplier_ids": [],
        "envelope_service_nonseparation_group_supplier_ids": suppliers,
        "priority_group_supplier_ids_if_no_universal_top3": [*suppliers, "SUP-5"],
        "supplier_lane_count_by_id": {supplier: 1 for supplier in suppliers},
        "envelope_service_driver_mappings": driver_mappings,
    }
    monkeypatch.setattr(
        extensions,
        "_validate_and_recompute_boundary",
        lambda **_kwargs: (
            {
                "package_signature": "boundary-package",
                "builder_sha256": extensions.EXPECTED_PRIORITY_BOUNDARY_BUILDER_SHA256,
                "schema_version": extensions.boundary.MANIFEST_SCHEMA_VERSION,
            },
            audit,
            rankings,
        ),
    )
    monkeypatch.setattr(extensions, "_sha256", lambda _path: "fixture-hash")
    priorities, lineage = extensions._boundary_priority_selection(
        artifact_dir=tmp_path / "source",
        boundary_dir=tmp_path / "boundary",
        source_manifest={
            "distinct_supplier_count": 4,
            "campaign_signature": "campaign",
        },
        active_lanes=lanes,
        severe_scenarios=severe,
    )
    assert [row["supplier_id"] for row in priorities] == suppliers
    assert {int(row["selection_slot"]) for row in priorities} == {1, 2, 3, 4}
    assert lineage["priority_selection_status"] == (
        "complete_service_nonseparation_group_follow_up"
    )
    assert lineage["follow_up_supplier_ids"] == suppliers
    assert lineage["selected_subset_covers_service_nonseparation_group"] is True
    assert lineage["service_nonseparation_group_fully_followed_up"] is True
    assert lineage["selected_subset_covers_boundary_universal_group"] is False
    assert lineage["slot_order_has_scientific_meaning"] is False
    assert lineage["scientific_order_claimed"] is False
    assert lineage["all_multi_lane_supplier_ids"] == ["SUP-1", "SUP-2"]
    assert lineage["all_multi_lane_supplier_active_chain_ids_by_id"] == {
        "SUP-1": ["chain_1", "chain_1_secondary"],
        "SUP-2": ["chain_2", "chain_2_secondary"],
    }
    assert lineage["multi_lane_common_cause_scope_complete"] is False


def test_lot_plan_uses_a_dedicated_identically_traced_pairing_block(tmp_path: Path):
    source = _source_artifact(tmp_path)
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    baselines = _read_csv(output / "paired_baseline_design.csv")
    causal = _read_csv(output / "causal_lot_attribution_design.csv")
    traced_baselines = [
        row for row in baselines if row["lot_trace_required"].lower() == "true"
    ]
    assert len(traced_baselines) == 1
    assert len(causal) == 3
    assert all(row["lot_trace_required"].lower() == "true" for row in causal)
    assert all(
        row["baseline_lot_trace_required"].lower() == "true" for row in causal
    )
    assert {
        row["pairing_block_id"] for row in causal
    } == {traced_baselines[0]["pairing_block_id"]}
    assert {row["case_action"] for row in causal} == {
        "reuse_existing_traced_pair"
    }
    assert sum(int(row["new_run_count"]) for row in causal) == 0
    assert all("borne haute" in row["genealogical_quantity_meaning"] for row in causal)
    assert all("baseline_day" in row["causal_fields_required"] for row in causal)
    assert all("qty" in row["causal_fields_required"] for row in causal)
    assert all("aucun total inter-unités" in row["quantity_aggregation_rule"] for row in causal)


def test_plan_never_promotes_before_separate_execution_manifests(tmp_path: Path):
    source = _source_artifact(tmp_path)
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    controls = json.loads(
        (output / "promotion_controls.json").read_text(encoding="utf-8")
    )
    assert controls["source_controls_pass"] is True
    assert controls["all_required_controls_pass"] is False
    assert controls["status"] == "not_promotable_from_plan"
    pending = [
        row
        for row in controls["controls"]
        if row["state"] == "planned_not_executed"
    ]
    assert {row["control_id"] for row in pending} == {
        "multi_lane_common_cause_execution",
        "temporal_robustness_execution",
        "four_business_causes_execution",
        "causal_lot_attribution_execution",
    }


def test_missing_raw_lot_files_adds_only_one_shared_baseline_and_three_stresses(
    tmp_path: Path,
):
    source = _source_artifact(tmp_path)
    for path in (source / "cases").rglob("production_lot_*.csv"):
        path.unlink()
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    manifest = json.loads(
        (output / "post_priority_extensions_plan_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    counts = manifest["planned_case_counts"]
    assert counts["dedicated_lot_trace_baseline_new_runs"] == 0
    assert counts["dedicated_lot_trace_baseline_logical_reference_count"] == 1
    assert counts["new_run_count"] == 813
    causal = _read_csv(output / "causal_lot_attribution_design.csv")
    assert {row["case_action"] for row in causal} == {
        "new_traced_stress_with_new_shared_baseline"
    }
    baselines = _read_csv(output / "paired_baseline_design.csv")
    assert len(baselines) == 31
    assert sum(int(row["new_run_count"]) for row in baselines) == 31
    assert {
        row["case_action"]
        for row in baselines
        if row["paired_scope"] != "causal_lot_attribution_subset"
    } == {"new_baseline_run_required"}
    assert all(
        row.get("source_reference_reused_as_physical_run") == "False"
        for row in baselines
        if row["paired_scope"] != "causal_lot_attribution_subset"
    )


def test_retained_full_genealogy_is_reused_before_planning_lot_stress_reruns(
    tmp_path: Path,
):
    source = _source_artifact(tmp_path)
    for path in (source / "cases").rglob("production_lot_*.csv"):
        path.unlink()
    priorities = _read_csv(source / "confirmation_lane_sensitivity_ranking.csv")[:3]
    for priority in priorities:
        proof_dir = (
            source
            / "cases"
            / priority["worst_scenario_id"]
            / "seed_1001"
            / "proofs"
        )
        _write_csv(
            proof_dir / "impacted_receipt_lots.csv",
            [{"shipment_id": priority["chain_id"], "day": 10, "qty": 1, "uom": "KG"}],
        )
        _write_csv(
            proof_dir / "impacted_descendant_lots.csv",
            [{"production_campaign_id": priority["chain_id"], "day": 20, "qty": 1, "uom": "UN"}],
        )
        _write_csv(
            proof_dir / "impacted_genealogy.csv",
            [
                {
                    "parent_lot_id": f"root-{priority['chain_id']}",
                    "child_lot_id": f"child-{priority['chain_id']}",
                }
            ],
        )
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    manifest = json.loads(
        (output / "post_priority_extensions_plan_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["planned_case_counts"]["new_run_count"] == 810
    causal = _read_csv(output / "causal_lot_attribution_design.csv")
    assert {row["case_action"] for row in causal} == {
        "reuse_existing_stress_with_new_traced_baseline"
    }
    assert {row["source_incident_evidence_format"] for row in causal} == {
        "retained_genealogical_proof_exports"
    }
    assert all(row["source_incident_impacted_receipts_sha256"] for row in causal)


def test_existing_output_is_never_overwritten(tmp_path: Path):
    source = _source_artifact(tmp_path)
    output = tmp_path / "plan"
    extensions.create_plan(network_artifact=source, output_dir=output)
    with pytest.raises(FileExistsError):
        extensions.create_plan(network_artifact=source, output_dir=output)


def test_incomplete_source_is_rejected_before_output_is_created(tmp_path: Path):
    source = _source_artifact(tmp_path)
    manifest_path = source / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "running"
    _write_json(manifest_path, manifest)
    output = tmp_path / "plan"
    with pytest.raises(ValueError, match="pas complète"):
        extensions.create_plan(network_artifact=source, output_dir=output)
    assert not output.exists()


def test_plan_validation_detects_a_modified_design(tmp_path: Path):
    source = _source_artifact(tmp_path)
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    design_path = output / "temporal_robustness_design.csv"
    design_path.write_text(
        design_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Empreinte"):
        extensions.validate_plan_artifact(output)


def test_plan_rejects_self_consistent_wrong_planner_builder_hash(tmp_path: Path):
    source = _source_artifact(tmp_path)
    output = extensions.create_plan(
        network_artifact=source, output_dir=tmp_path / "plan"
    )
    manifest_path = output / "post_priority_extensions_plan_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["planner_builder_sha256"] = "0" * 64
    manifest["signature_payload"]["planner_builder_sha256"] = "0" * 64
    manifest["plan_signature"] = extensions._canonical_signature(
        manifest["signature_payload"]
    )
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="planner courant"):
        extensions.validate_plan_artifact(output)
