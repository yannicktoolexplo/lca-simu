from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4_dashboard as dashboard,
)


CAMPAIGN_SIGNATURE = "campaign-v4-fixture"
ENGINE_SHA256 = "a" * 64


def _stable_sha(payload: object) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _signed(payload: dict[str, object], field: str) -> dict[str, object]:
    return {**payload, field: _stable_sha(payload)}


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metric_fields(value: float) -> dict[str, float]:
    return {
        "impact_service_loss_fed_product_pp_mean": value,
        "impact_service_loss_fed_product_pp_median": value,
        "impact_service_loss_fed_product_pp_p10": max(0.0, value - 0.2),
        "impact_service_loss_fed_product_pp_ci95_low": max(0.0, value - 0.1),
        "impact_service_loss_fed_product_pp_ci95_high": value + 0.1,
        "impact_service_loss_fed_product_pp_p90": value + 0.2,
        "impact_service_loss_fed_product_pp_positive_effect_rate": 1.0,
        "global_service_loss_pp_mean": value,
        "global_service_loss_pp_median": value,
        "global_service_loss_pp_p10": max(0.0, value - 0.2),
        "global_service_loss_pp_ci95_low": max(0.0, value - 0.1),
        "global_service_loss_pp_ci95_high": value + 0.1,
        "global_service_loss_pp_p90": value + 0.2,
        "global_service_loss_pp_positive_effect_rate": 1.0,
        "backlog_qty_days_per_demand_unit_mean": value / 10.0,
        "backlog_qty_days_per_demand_unit_median": value / 10.0,
        "backlog_qty_days_per_demand_unit_p10": value / 12.0,
        "backlog_qty_days_per_demand_unit_ci95_low": value / 11.0,
        "backlog_qty_days_per_demand_unit_ci95_high": value / 9.0,
        "backlog_qty_days_per_demand_unit_p90": value / 8.0,
        "backlog_qty_days_per_demand_unit_positive_effect_rate": 1.0,
        "fed_product_production_loss_share_of_demand_mean": value / 100.0,
        "fed_product_production_loss_share_of_demand_median": value / 100.0,
        "fed_product_production_loss_share_of_demand_p10": value / 120.0,
        "fed_product_production_loss_share_of_demand_ci95_low": value / 110.0,
        "fed_product_production_loss_share_of_demand_ci95_high": value / 90.0,
        "fed_product_production_loss_share_of_demand_p90": value / 80.0,
        "fed_product_production_loss_share_of_demand_positive_effect_rate": 1.0,
        "impact_service_loss_fed_product_pp_per_1000_effective_dose": value / 2.0,
        "impact_service_loss_fed_product_pp_per_1000_effective_dose_ci95_low": value / 2.2,
        "impact_service_loss_fed_product_pp_per_1000_effective_dose_ci95_high": value / 1.8,
        "effective_exposure_dose_sum": 2000.0,
        "effective_exposure_dose_unit": "unite_non_livree",
    }


def _make_results_fixture(root: Path) -> tuple[Path, Path]:
    results = root / "results"
    results.mkdir()

    binding = _signed(
        {
            "schema_version": (
                "etudecas.supplier_operating_point_full_campaign.v4."
                "state_validation_binding.v1"
            ),
            "status": dashboard.SIGNED_OPERATING_POINT_STATUS,
            "campaign_signature": CAMPAIGN_SIGNATURE,
            "campaign_seed_count": 30,
            "campaign_seeds": list(dashboard.v4_contract.CAMPAIGN_SEEDS),
            "design_seed": 900659036,
            "state_validation_engine_runs_in_campaign": 0,
            "imported_official_service_proof_count": 90,
            "imported_official_shipment_trace_count": 90,
            "retuning_after_holdout": False,
            "states": {
                "op_100": {
                    "pooled": {
                        "system_on_due_service": 0.998,
                        "on_due_service_268091": 0.997,
                        "on_due_service_268967": 0.999,
                    }
                },
                "op_93": {
                    "pooled": {
                        "system_on_due_service": 0.931,
                        "on_due_service_268091": 0.928,
                        "on_due_service_268967": 0.935,
                    }
                },
                "op_80": {
                    "pooled": {
                        "system_on_due_service": 0.802,
                        "on_due_service_268091": 0.796,
                        "on_due_service_268967": 0.808,
                    }
                },
            },
        },
        "binding_signature",
    )
    _write_json(results / "state_validation_binding.json", binding)

    achieved_by_state = {
        "op_100": (100.0, 99.8, 99.7, 99.9, 99.6, 99.9, "baseline", 0.0, 0.0),
        "op_93": (
            93.0,
            93.1,
            92.8,
            93.5,
            92.6,
            93.6,
            "balanced_product_supplier_planned_lead",
            12.0,
            14.0,
        ),
        "op_80": (
            80.0,
            80.2,
            79.6,
            80.8,
            79.5,
            80.9,
            "balanced_product_supplier_planned_lead",
            28.0,
            32.0,
        ),
    }
    _write_csv(
        results / "operating_point_achieved_services.csv",
        [
            {
                "operating_point_id": state,
                "target_service_pct": values[0],
                "achieved_global_service_pct": values[1],
                "achieved_service_268091_pct": values[2],
                "achieved_service_268967_pct": values[3],
                "global_service_bootstrap_ci95_low_pct": values[4],
                "global_service_bootstrap_ci95_high_pct": values[5],
                "degradation_family": values[6],
                "degradation_unit": "planned_lead_days_added_by_finished_product_feed",
                "offset_days_268091": values[7],
                "offset_days_268967": values[8],
                "campaign_seed_count": 30,
            }
            for state, values in achieved_by_state.items()
        ],
    )

    supplier_rows: list[dict[str, object]] = []
    lane_rows: list[dict[str, object]] = []
    priority_rows: list[dict[str, object]] = []
    registry_lanes = ["lane-338", *[f"lane-{index:02d}" for index in range(2, 19)]]
    for state_index, state in enumerate(dashboard.STATE_IDS):
        for mechanism_index, mechanism in enumerate(dashboard.MECHANISMS):
            effect = float(state_index + mechanism_index + 1)
            common = {
                "operating_point_id": state,
                "operating_point_service_pct": {"op_100": 99.8, "op_93": 93.1, "op_80": 80.2}[state],
                "mechanism": mechanism,
                "supplier_id": "S-338",
                "item_id": "338929",
                "dst_node_id": "M-1810",
                "target_product_id": "268091",
                "target_uom": "UN",
                "paired_repetition_count": 30,
                "physical_exercise_rate": 1.0,
                "target_planned_qty_mean": 2400.0,
                "target_shipment_count_mean": 4.0,
                **_metric_fields(effect),
            }
            supplier_rows.append({**common, "exposed_lane_id": "lane-338"})
            lane_rows.extend(
                {**common, "lane_id": lane_id} for lane_id in registry_lanes
            )
            priority_rows.append(
                {
                    "position": 1,
                    "operating_point_id": state,
                    "mechanism": mechanism,
                    "supplier_id": "S-338",
                    "exposed_lane_id": "lane-338",
                    "priority_status": "robust_priority",
                    "model_effect_detected": True,
                    "state_comparison_valid": True,
                    "fixed360_effect_mean_pp": effect,
                    "bootstrap_top3_inclusion_probability": 0.95,
                    "bootstrap_unambiguous_top3_probability": 0.9,
                }
            )
    _write_csv(results / "supplier_statistics.csv", supplier_rows)
    _write_csv(results / "lane_statistics.csv", lane_rows)
    _write_csv(results / "priority_suppliers_by_cause_state.csv", priority_rows)
    _write_csv(
        results / "supplier_priority_stability_by_cause.csv",
        [
            {
                "mechanism": mechanism,
                "supplier_id": "S-338",
                "in_top3_op_100": True,
                "in_top3_op_93": True,
                "in_top3_op_80": True,
                "state_comparison_valid": True,
                "insufficient_comparable_exposure": False,
                "same_exposed_lane_across_states": True,
                "same_target_product_for_exposed_lane_across_states": True,
                "comparison_lane_id": "lane-338",
                "target_product_id_for_comparison_lane": "268091",
                "comparable_seed_count": 30,
                "required_comparable_seed_count": 24,
                "fixed360_effect_mean_pp_op_100": 1.0 + mechanism_index,
                "fixed360_effect_mean_pp_op_93": 2.0 + mechanism_index,
                "fixed360_effect_mean_pp_op_80": 3.0 + mechanism_index,
            }
            for mechanism_index, mechanism in enumerate(dashboard.MECHANISMS)
        ],
    )

    registry_unsigned: dict[str, object] = {
        "campaign_signature": CAMPAIGN_SIGNATURE,
        "engine_sha256": ENGINE_SHA256,
        "schema_version": (
            "etudecas.supplier_operating_point_full_campaign.v4.target_registry.v1"
        ),
        "design_seed": dashboard.v4_contract.INCIDENT_DESIGN_SEED,
        "disruption_window_days": 42,
        "campaign_seeds": list(dashboard.v4_contract.CAMPAIGN_SEEDS),
        "seeds": list(dashboard.v4_contract.CAMPAIGN_SEEDS),
        "states": list(dashboard.STATE_IDS),
        "lanes": registry_lanes,
        "campaign_exposure_gate_passed": True,
        "lane_contracts": [
            {
                "lane_id": lane_id,
                "state_comparison_valid": True,
                "comparable_campaign_seed_count": 30,
                "required_comparable_seed_count": 24,
            }
            for lane_id in registry_lanes
        ],
        "targets": [
            {
                "operating_point_id": state,
                "seed": seed,
                "lane_id": lane_id,
                "item_id": "338929",
                "dst_node_id": "M-1810",
                "target_window_days": 42,
                "target_window_start_day": 120,
                "target_window_end_day": 161,
                "target_planned_qty": 2400.0,
                "target_shipment_count": 4,
                "target_uom": "UN",
            }
            for state in dashboard.STATE_IDS
            for seed in dashboard.v4_contract.CAMPAIGN_SEEDS
            for lane_id in registry_lanes
        ],
    }
    registry = _signed(registry_unsigned, "registry_signature")
    registry_path = results / "cross_state_target_registry.json"
    _write_json(registry_path, registry)

    lot_plan = _signed(
        {
            "schema_version": (
                "etudecas.supplier_operating_point_full_campaign.v4."
                "lot_replay_selection.v1"
            ),
            "status": "complete_selected",
            "campaign_signature": CAMPAIGN_SIGNATURE,
            "engine_sha256": ENGINE_SHA256,
            "selection_contract": {
                "forced_top3": False,
                "one_dossier_per_cause_if_available": True,
                "mechanisms_kept_separate": True,
                "risk_paths_relative_to_campaign_root": True,
                "replay_executes_simulation": False,
                "quality_included": False,
            },
            "selected_dossiers": [
                {
                    "dossier_id": "dossier_01_fixture",
                    "operating_point_id": "op_93",
                    "mechanism": "transport_delay",
                    "lane_id": "lane-338",
                    "supplier_id": "S-338",
                    "item_id": "338929",
                    "dst_node_id": "M-1810",
                    "target_product_id": "268091",
                    "priority_status": "robust_priority",
                    "representative_seed": 7,
                    "representative_effect_pp": 2.4,
                    "cell_median_effect_pp": 2.1,
                    "valid_exercised_seed_count": 27,
                    "incident_evidence_path": (
                        "shards/shard_001/case_evidence/incident_fixture.json"
                    ),
                    "incident_evidence_sha256": "b" * 64,
                    "baseline_evidence_path": (
                        "shards/shard_001/case_evidence/baseline_fixture.json"
                    ),
                    "baseline_evidence_sha256": "c" * 64,
                    "risk_csv_path": (
                        "shards/shard_001/inputs/risk_events/incident_fixture.csv"
                    ),
                    "risk_csv_sha256": "d" * 64,
                }
            ],
        },
        "selection_signature",
    )
    lot_path = results / "lot_replay_plan.json"
    _write_json(lot_path, lot_plan)

    output_names = (
        "state_validation_binding.json",
        "operating_point_achieved_services.csv",
        "cross_state_target_registry.json",
        "supplier_statistics.csv",
        "lane_statistics.csv",
        "priority_suppliers_by_cause_state.csv",
        "supplier_priority_stability_by_cause.csv",
        "lot_replay_plan.json",
    )
    outputs = {
        name: {"sha256": _sha256_file(results / name)} for name in output_names
    }
    outputs["lot_replay_plan.json"].update(
        {"row_count": 1, "selection_signature": lot_plan["selection_signature"]}
    )
    validation = {
        "schema_version": dashboard.FINALIZER_SCHEMA_VERSION,
        "status": "complete_validated",
        "campaign_signature": CAMPAIGN_SIGNATURE,
        "engine_sha256": ENGINE_SHA256,
        "evidence_class": "conditional_reproducible_simulation_hypothesis",
        "historical_incident_probability_estimated": False,
        "expected_contract": {
            "mechanisms": list(dashboard.MECHANISMS),
            "paired_repetition_count": 30,
            "quality_branch_included": False,
            "availability_incident_included": False,
        },
        "comparability_checks": {
            "complete_3x18x2x30_matrix": True,
            "same_repetitions_in_every_cell": True,
            "same_engine_sha256": True,
            "same_campaign_signature": True,
            "lane_identity_invariant": True,
            "baseline_pairing_complete": True,
            "paired_warmup_state_identical": True,
            "shipment_set_and_incident_trace_proven": True,
            "v4_holdout_state_binding_signed_and_accepted": True,
            "v4_holdout_shipment_traces_reused_without_rerun": True,
            "mandatory_non_reusable_op93_smoke_validated": True,
            "operating_point_validation_engine_runs_in_campaign": 0,
        },
        "lot_replay_plan": {
            "path": lot_path.name,
            "sha256": _sha256_file(lot_path),
            "row_count": 1,
            "selection_signature": lot_plan["selection_signature"],
        },
        "inputs": {
            "state_validation_binding_sha256": _sha256_file(
                results / "state_validation_binding.json"
            ),
            "target_registry_sha256": _sha256_file(registry_path),
        },
        "outputs": outputs,
    }
    _write_json(results / "campaign_validation.json", validation)
    return results, registry_path


def test_loads_hash_bound_v4_package_without_running_engine(tmp_path: Path) -> None:
    results, registry = _make_results_fixture(tmp_path)

    payload = dashboard.load_dashboard_data(
        results_dir=results,
        target_registry_path=registry,
    )

    assert payload["schemaVersion"] == dashboard.SCHEMA_VERSION
    assert [row["globalServicePct"] for row in payload["states"]] == pytest.approx(
        [99.8, 93.1, 80.2]
    )
    assert payload["states"][0]["label"] == "État de référence proche de 100 %"
    assert payload["states"][0]["degradationFamily"] == "baseline"
    assert payload["states"][1]["degradationFamily"] == (
        "balanced_product_supplier_planned_lead"
    )
    assert payload["states"][1]["offsetDays268091"] == pytest.approx(12.0)
    assert payload["states"][2]["globalCiLowPct"] == pytest.approx(79.5)
    assert payload["repetitions"] == 30
    assert payload["targetRegistry"]["allLanesComparable"] is True
    assert payload["lotReplay"]["status"] == "selected_not_executed"
    assert payload["lotReplay"]["dossiers"][0]["exercisedSeedCount"] == 27
    assert len(payload["priorities"]) == 6
    assert all(
        row["service"]["source"] == "impact_service_loss_fed_product_pp"
        for row in payload["priorities"]
    )
    assert all(row["service"]["p10"] is not None for row in payload["priorities"])
    assert payload["supplierStatistics"][0]["doseNormalisedService"]["value"] == (
        pytest.approx(0.5)
    )
    assert all(row["sameExposedLaneAcrossStates"] for row in payload["stability"])
    assert all(row["sameTargetProductAcrossStates"] for row in payload["stability"])


def test_builds_one_offline_v4_html_without_overwrite(tmp_path: Path) -> None:
    results, registry = _make_results_fixture(tmp_path)
    output = tmp_path / "supplier_campaign_v4.html"

    manifest = dashboard.build_dashboard(
        results_dir=results,
        target_registry_path=registry,
        output_html=output,
    )

    document = output.read_text(encoding="utf-8")
    assert manifest["offline_single_file"] is True
    assert manifest["view_count"] == 3
    assert "Campagne fournisseurs V4" in document
    assert "selected_not_executed" in document
    assert document.count('class="chart"') == 3
    assert all(
        f'id="{chart_id}"' in document
        for chart_id in ("service-chart", "slope-chart", "forest-chart")
    )
    assert "État de référence proche de 100 %" in document
    assert "quantité normalement livrable" in document
    assert "plan × fiabilité" in document
    assert "DOSES NON IDENTIQUES" in document
    assert "3 couples matière–site sur 24" in document
    assert "C-XXXXX" in document
    assert "priority_weight" in document
    assert "pilotage ciblé en boucle fermée n'est pas disponible" in document
    assert "Voie ${esc(row.lane)} · article ${esc(row.item)}" in document
    assert "COMPARAISON INTER-ÉTATS VALIDÉE" not in document
    assert "reçue à 50 %" not in document.casefold()
    assert "retenue qualité" not in document.casefold()
    assert "qualité" not in document.casefold()
    with pytest.raises(FileExistsError, match="écraser"):
        dashboard.build_dashboard(
            results_dir=results,
            target_registry_path=registry,
            output_html=output,
        )


def test_rejects_tampered_hash_bound_output(tmp_path: Path) -> None:
    results, registry = _make_results_fixture(tmp_path)
    with (results / "supplier_statistics.csv").open("a", encoding="utf-8") as handle:
        handle.write("tamper\n")

    with pytest.raises(dashboard.DashboardInputError, match="a chang"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_false_operating_point_family_even_if_inventory_hash_is_rewritten(
    tmp_path: Path,
) -> None:
    results, registry = _make_results_fixture(tmp_path)
    achieved_path = results / "operating_point_achieved_services.csv"
    rows = list(csv.DictReader(achieved_path.open(encoding="utf-8")))
    rows[1]["degradation_family"] = "invented_capacity"
    _write_csv(achieved_path, rows)
    validation_path = results / "campaign_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["outputs"][achieved_path.name]["sha256"] = _sha256_file(achieved_path)
    _write_json(validation_path, validation)

    with pytest.raises(dashboard.DashboardInputError, match="Contrat du point"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_priority_alias_that_contradicts_product_metric(tmp_path: Path) -> None:
    results, registry = _make_results_fixture(tmp_path)
    priority_path = results / "priority_suppliers_by_cause_state.csv"
    rows = list(csv.DictReader(priority_path.open(encoding="utf-8")))
    rows[0]["fixed360_effect_mean_pp"] = "999"
    _write_csv(priority_path, rows)
    validation_path = results / "campaign_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    validation["outputs"][priority_path.name]["sha256"] = _sha256_file(priority_path)
    _write_json(validation_path, validation)

    with pytest.raises(dashboard.DashboardInputError, match="métrique produit"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_unsigned_target_registry_even_if_inventory_hash_is_rewritten(
    tmp_path: Path,
) -> None:
    results, registry = _make_results_fixture(tmp_path)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    payload.pop("registry_signature")
    _write_json(registry, payload)
    validation_path = results / "campaign_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    changed_sha = _sha256_file(registry)
    validation["inputs"]["target_registry_sha256"] = changed_sha
    validation["outputs"][registry.name]["sha256"] = changed_sha
    _write_json(validation_path, validation)

    with pytest.raises(dashboard.DashboardInputError, match="signature"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_v4_binding_that_claims_a_campaign_rerun(tmp_path: Path) -> None:
    results, registry = _make_results_fixture(tmp_path)
    binding_path = results / "state_validation_binding.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding.pop("binding_signature")
    binding["state_validation_engine_runs_in_campaign"] = 90
    _write_json(binding_path, _signed(binding, "binding_signature"))
    validation_path = results / "campaign_validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    changed_sha = _sha256_file(binding_path)
    validation["inputs"]["state_validation_binding_sha256"] = changed_sha
    validation["outputs"][binding_path.name]["sha256"] = changed_sha
    _write_json(validation_path, validation)

    with pytest.raises(dashboard.DashboardInputError, match="zéro rejeu|import exact"):
        dashboard.load_dashboard_data(
            results_dir=results,
            target_registry_path=registry,
        )


def test_rejects_nonportable_lot_replay_proof_path(tmp_path: Path) -> None:
    plan_path = tmp_path / "lot_replay_plan.json"
    dossier = {
        "dossier_id": "dossier_01_fixture",
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": "lane-338",
        "supplier_id": "S-338",
        "item_id": "338929",
        "dst_node_id": "M-1810",
        "target_product_id": "268091",
        "priority_status": "robust_priority",
        "representative_seed": 1,
        "representative_effect_pp": 1.0,
        "cell_median_effect_pp": 1.0,
        "valid_exercised_seed_count": 27,
        "incident_evidence_path": "../escape.json",
        "incident_evidence_sha256": "b" * 64,
        "baseline_evidence_path": "evidence/baseline.json",
        "baseline_evidence_sha256": "c" * 64,
        "risk_csv_path": "inputs/risk.csv",
        "risk_csv_sha256": "d" * 64,
    }
    plan = _signed(
        {
            "schema_version": (
                "etudecas.supplier_operating_point_full_campaign.v4."
                "lot_replay_selection.v1"
            ),
            "status": "complete_selected",
            "campaign_signature": CAMPAIGN_SIGNATURE,
            "engine_sha256": ENGINE_SHA256,
            "selection_contract": {
                "forced_top3": False,
                "one_dossier_per_cause_if_available": True,
                "mechanisms_kept_separate": True,
                "risk_paths_relative_to_campaign_root": True,
                "replay_executes_simulation": False,
                "quality_included": False,
            },
            "selected_dossiers": [dossier],
        },
        "selection_signature",
    )
    _write_json(plan_path, plan)
    actual_sha = _sha256_file(plan_path)
    link = {
        "path": plan_path.name,
        "sha256": actual_sha,
        "row_count": 1,
        "selection_signature": plan["selection_signature"],
    }
    validation = {
        "campaign_signature": CAMPAIGN_SIGNATURE,
        "engine_sha256": ENGINE_SHA256,
        "lot_replay_plan": link,
        "outputs": {plan_path.name: link},
    }

    with pytest.raises(dashboard.DashboardInputError, match="non portable"):
        dashboard._lot_replay_payload(
            plan,
            validation=validation,
            plan_path=plan_path,
        )
