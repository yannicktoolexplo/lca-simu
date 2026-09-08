from __future__ import annotations

import copy
import hashlib
from collections import defaultdict
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_full_incident_lot_registry as registry,
)


def _lanes() -> list[dict[str, str]]:
    return [
        {
            "lane_id": f"L{index:02d}",
            "supplier_id": f"SUP-{index:02d}",
            "item_id": f"item:{330000 + index}",
            "dst_node_id": "M-1810" if index % 2 else "M-1430",
            "edge_id": f"EDGE-{index:02d}",
            "target_product_id": "268091" if index % 2 else "268967",
        }
        for index in range(1, 19)
    ]


def _metric_row(
    *,
    state: str,
    lane: dict[str, str],
    mechanism: str,
    seed: int,
    effect: float,
) -> dict[str, object]:
    row: dict[str, object] = {field: "" for field in registry.EXPOSURE_SOURCE_FIELDS}
    case_key = f"{state}-{lane['lane_id']}-{mechanism}-{seed}"
    row.update(
        {
            "schema_version": registry.finalizer_v4.INPUT_METRIC_SCHEMA_VERSION,
            "campaign_signature": "a" * 64,
            "engine_sha256": "b" * 64,
            "shard_id": f"shard-{lane['lane_id']}",
            "case_key": case_key,
            "case_signature": hashlib.sha256(case_key.encode()).hexdigest(),
            "baseline_case_signature": hashlib.sha256(
                f"baseline-{state}-{seed}".encode()
            ).hexdigest(),
            "warmup_core_state_sha256": hashlib.sha256(
                f"warmup-{state}-{seed}".encode()
            ).hexdigest(),
            "summary_sha256": hashlib.sha256(
                f"summary-{case_key}".encode()
            ).hexdigest(),
            "operating_point_id": state,
            "operating_point_service_pct": float(state.removeprefix("op_")),
            "simulation_days": 720,
            "state_evaluation_days": 720,
            "stage": "incident",
            "mechanism": mechanism,
            "seed": seed,
            "status": "valid",
            "valid": True,
            **lane,
            "target_status": "identified_registered_window_positive_flow",
            "target_reference_kind": (
                "paired_simulated_baseline_shipment_not_observed_supplier_performance"
            ),
            "target_shipment_count": 1,
            "target_window_start_day": 100,
            "target_window_end_day": 141,
            "target_window_days": 42,
            "target_planned_qty": 100.0,
            "target_expected_delivered_qty": 100.0,
            "target_uom": "UN",
            "state_comparison_valid": True,
            "seed_cross_state_exposure_comparable": True,
            "comparable_campaign_seed_count": 30,
            "required_comparable_seed_count": 24,
            "impact_window_start_day": 100,
            "impact_window_end_day": 459,
            "impact_window_days": 360,
            "causal_window_start_day": 100,
            "causal_window_end_day": 459,
            "causal_window_days": 360,
            "causal_window_defined": True,
            "risk_type": (
                "lead_time_extra_days"
                if mechanism == "transport_delay"
                else "reliability"
            ),
            "risk_value": 120.0 if mechanism == "transport_delay" else 0.5,
            "risk_start_day": 100,
            "risk_end_day": 141,
            "risk_applied_row_count": 1,
            "risk_applied_event_count": 1,
            "incident_physically_exercised": True,
            "incident_shipment_count": 1,
            "incident_affected_pulled_qty": 100.0,
            "incident_affected_shipped_qty": (
                100.0 if mechanism == "transport_delay" else 50.0
            ),
            "quantity_shortfall_qty": (0.0 if mechanism == "transport_delay" else 50.0),
            "arrival_delay_days": 120 if mechanism == "transport_delay" else 0,
            "incident_effective_dose_qty": (
                "" if mechanism == "transport_delay" else 50.0
            ),
            "incident_effective_dose_qty_days": (
                12000.0 if mechanism == "transport_delay" else ""
            ),
            "baseline_impact_service_268091_pct": 95.0,
            "baseline_impact_service_268967_pct": 95.0,
            "baseline_impact_service_global_pct": 95.0,
            "impact_service_268091_pct": 95.0 - effect,
            "impact_service_268967_pct": 95.0 - effect,
            "impact_service_global_pct": 95.0 - effect,
            "impact_service_loss_268091_pp": effect,
            "impact_service_loss_268967_pp": effect,
            "impact_service_loss_global_pp": effect,
            "impact_service_loss_fed_product_pp": effect,
            "impact_on_due_loss_fed_product_qty": 10.0,
            "impact_on_due_loss_global_qty": 20.0,
            "impact_backlog_qty_days_delta": 20.0,
            "impact_backlog_qty_days_per_demand_unit": 0.02,
            "impact_max_backlog_qty_delta": 5.0,
            "impact_production_loss_fed_product_qty": 10.0,
            "impact_production_loss_fed_product_share_of_demand": 0.01,
            "causal_service_loss_fed_product_pp": effect,
            "causal_service_loss_global_pp": effect,
            "causal_on_due_loss_fed_product_qty": 10.0,
            "causal_backlog_qty_days_delta": 20.0,
            "causal_backlog_qty_days_per_demand_unit": 0.02,
            "causal_max_backlog_qty_delta": 5.0,
            "causal_production_loss_fed_product_qty": 10.0,
            "causal_production_loss_fed_product_share_of_demand": 0.01,
        }
    )
    return row


def _fixture_inputs() -> dict[str, object]:
    lanes = _lanes()
    metrics: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []
    for state_index, state in enumerate(registry.STATES):
        for lane_index, lane in enumerate(lanes, start=1):
            for mechanism_index, mechanism in enumerate(registry.MECHANISMS):
                effect = float(state_index + lane_index / 100 + mechanism_index / 10)
                group = [
                    _metric_row(
                        state=state,
                        lane=lane,
                        mechanism=mechanism,
                        seed=seed,
                        effect=effect,
                    )
                    for seed in registry.EXPECTED_SEED_IDS
                ]
                metrics.extend(group)
                cells.append(
                    {
                        "operating_point_id": state,
                        "operating_point_service_pct": float(state.removeprefix("op_")),
                        "operating_point_service_268091_pct": float(
                            state.removeprefix("op_")
                        ),
                        "operating_point_service_268967_pct": float(
                            state.removeprefix("op_")
                        ),
                        "mechanism": mechanism,
                        "target_product_id": lane["target_product_id"],
                        "lane_id": lane["lane_id"],
                        "supplier_id": lane["supplier_id"],
                        "item_id": lane["item_id"],
                        "dst_node_id": lane["dst_node_id"],
                        "edge_id": lane["edge_id"],
                        "paired_repetition_count": 30,
                        "physical_exercise_count": 30,
                        "physical_exercise_rate": 1.0,
                        "zero_exposure_repetition_count": 0,
                        "target_planned_qty_mean": 100.0,
                        "target_shipment_count_mean": 1.0,
                        "impact_service_loss_fed_product_pp_mean": effect,
                        "impact_service_loss_fed_product_pp_median": effect,
                        "impact_service_loss_fed_product_pp_p10": effect,
                        "impact_service_loss_fed_product_pp_p90": effect,
                        "impact_service_loss_fed_product_pp_ci95_low": effect,
                        "impact_service_loss_fed_product_pp_ci95_high": effect,
                        "impact_service_loss_fed_product_pp_positive_effect_count": 30,
                        "impact_service_loss_fed_product_pp_positive_effect_rate": 1.0,
                        "impact_service_loss_global_pp_mean": effect,
                        "impact_production_loss_fed_product_qty_mean": 10.0,
                        "impact_backlog_qty_days_delta_mean": 20.0,
                        "impact_backlog_qty_days_per_demand_unit_mean": 0.02,
                    }
                )
    selected = {
        "dossier_id": "D01",
        "operating_point_id": "op_100",
        "mechanism": "transport_delay",
        "lane_id": "L01",
        "representative_seed": registry.EXPECTED_SEED_IDS[0],
    }
    replay_metadata = {
        **selected,
        "supplier_id": "SUP-01",
        "item_id": "item:330001",
        "dst_node_id": "M-1810",
        "target_product_id": "268091",
    }
    source_tables = {
        "shipment_to_material_receipt": [
            {
                "incident_event_id": "R1",
                "shipment_id": "SHIP-1",
                "risk_decision_day": "100",
                "source_lot_id": "incident::SRC-1",
                "source_node_id": "SUP-01",
                "source_item_id": "item:330001",
                "receipt_lot_id": "incident::MP-1",
                "receipt_node_id": "M-1810",
                "receipt_item_id": "item:330001",
                "parent_qty": "12",
                "child_qty": "12",
            }
        ],
        "consumption_and_wip": [
            {
                "incident_event_id": "R1",
                "shipment_ids": "SHIP-1",
                "material_lot_id": "incident::MP-1",
                "day": "101",
                "consumed_qty": "5",
                "campaign_id": "CAMP-1",
                "batch_id": "BATCH-1",
                "wip_start_qty": "8",
                "wip_end_qty": "3",
                "released_lot_id_same_day": "incident::PF-1",
                "released_qty_same_day": "4",
            }
        ],
        "finished_lot_release": [
            {
                "incident_event_id": "R1",
                "shipment_ids": "SHIP-1",
                "day": "102",
                "finished_lot_id": "incident::PF-1",
                "released_qty": "4",
                "campaign_id": "CAMP-1",
                "claim": "native_genealogical_contact_not_cross_arm_identity",
            }
        ],
        "aggregated_client_contact": [
            {
                "incident_event_id": "R1",
                "shipment_ids": "SHIP-1",
                "day": "103",
                "client_lot_id": "incident::PF-1",
                "client_node_id": "C-XXXXX",
                "service_event_qty_on_contacted_lot": "2",
                "claim": "native_genealogical_contact_not_incremental_service_loss",
            }
        ],
    }
    source_paths = {
        stage: f"finalized/dossiers/D01/{filename}"
        for stage, filename in registry.TRACE_FILES.items()
    }
    genealogy = registry.normalise_genealogy_rows(
        dossier=replay_metadata,
        source_tables=source_tables,
        source_paths=source_paths,
        incident_j0_day=100,
    )
    j0_rows = [
        {
            "dossier_id": "D01",
            "operating_point_id": "op_100",
            "mechanism": "transport_delay",
            "lane_id": "L01",
            "representative_seed": registry.EXPECTED_SEED_IDS[0],
            "incident_j0_day": 100,
            "metric": metric,
            "measurement_kind": registry.J0_MEASUREMENT_KINDS[metric],
            "observation_convention": registry.J0_OBSERVATION_CONVENTION,
            "is_pre_incident_snapshot": False,
            "baseline_value_at_incident_j0": 10.0,
            "incident_value_at_incident_j0": 10.0,
            "delta_incident_minus_baseline_at_incident_j0": 0.0,
        }
        for metric in sorted(registry.EXPECTED_J0_METRICS)
    ]
    trace_counts = registry._trace_counts_from_source_tables(source_tables)
    replay = {
        **replay_metadata,
        "incidentJ0Day": 100,
        "proofLevel": "complete",
        "proofScope": "native_lot_contact_trace_to_aggregated_client",
        "mrpRequirementMode": "dynamic_explicit",
        "traceCounts": trace_counts,
        "missingNativeTraceStages": [],
        "fullDynamicCascadeProven": False,
        "signedMrpResponseTraceAvailable": False,
        "kpis": {},
        "j0Context": j0_rows,
        "sourceTables": source_tables,
        "sourceRowCount": len(genealogy),
        "normalisedRowCount": len(genealogy),
        "sourceRowsTruncated": False,
    }
    return {
        "lanes": lanes,
        "metrics": metrics,
        "cells": cells,
        "selection": {
            "selected_dossier_count": 1,
            "selected_dossiers": [selected],
        },
        "replay_data": {
            "dossiers": [replay],
            "genealogyRows": genealogy,
            "j0Rows": j0_rows,
        },
    }


@pytest.fixture(scope="module")
def payload_bundle() -> tuple[dict, list[str]]:
    source = _fixture_inputs()
    cells = source["cells"]
    assert isinstance(cells, list)
    return registry.build_payload(
        incident_rows=source["metrics"],
        official_cell_rows=cells,
        official_cell_fields=list(cells[0]),
        lanes=source["lanes"],
        requirement_modes={
            lane["lane_id"]: (
                "dynamic_explicit"
                if lane["lane_id"] in {"L01", "L02"}
                else "static_explicit"
            )
            for lane in source["lanes"]
        },
        selection=source["selection"],
        replay_data=source["replay_data"],
        generated_at_utc="2026-09-05T12:00:00+00:00",
    )


def test_complete_matrix_marks_only_exact_replayed_seed(
    payload_bundle: tuple[dict, list[str]],
) -> None:
    payload, _fields = payload_bundle
    assert len(payload["exposures"]) == 3240
    assert len(payload["cells"]) == 108
    replayed = [row for row in payload["exposures"] if row["genealogy_available"]]
    assert len(replayed) == 1
    assert (
        replayed[0]["operating_point_id"],
        replayed[0]["mechanism"],
        replayed[0]["lane_id"],
        replayed[0]["seed"],
    ) == ("op_100", "transport_delay", "L01", registry.EXPECTED_SEED_IDS[0])
    replay_cell = next(
        row
        for row in payload["cells"]
        if (row["operating_point_id"], row["mechanism"], row["lane_id"])
        == ("op_100", "transport_delay", "L01")
    )
    assert replay_cell["genealogy_available_repetition_count"] == 1
    assert replay_cell["genealogy_coverage_of_30_repetitions"] == pytest.approx(1 / 30)
    assert payload["scope"]["incidentRowsWithoutGenealogy"] == 3239
    assert payload["scope"]["signedCaseEvidenceRowCount"] == 3330
    assert payload["scope"]["baselineReferenceRowCount"] == 90
    assert payload["actions"]["lotTraceAvailable"] is False
    coverage_counts = {
        row["genealogy_available_repetition_count"] for row in payload["cells"]
    }
    assert coverage_counts == {0, 1}


def test_genealogy_normalisation_keeps_every_row_and_business_stage() -> None:
    dossier = {
        "dossier_id": "D01",
        "operating_point_id": "op_80",
        "mechanism": "planned_delivery_shortfall",
        "lane_id": "L01",
        "supplier_id": "SUP-01",
        "item_id": "item:330001",
        "dst_node_id": "M-1810",
        "target_product_id": "268091",
        "representative_seed": 7,
    }
    tables = defaultdict(list)
    tables["shipment_to_material_receipt"].append(
        {
            "incident_event_id": "R1",
            "shipment_id": "SHIP-1",
            "risk_decision_day": "99",
            "source_lot_id": "incident::SRC-1",
            "receipt_lot_id": "incident::MP-1",
            "parent_qty": "12",
            "child_qty": "12",
        }
    )
    tables["consumption_and_wip"].append(
        {
            "shipment_ids": "SHIP-1",
            "material_lot_id": "incident::MP-1",
            "day": "100",
            "consumed_qty": "5",
            "campaign_id": "CAMP-1",
            "batch_id": "BATCH-1",
            "wip_start_qty": "8",
            "wip_end_qty": "3",
        }
    )
    tables["finished_lot_release"].append(
        {
            "shipment_ids": "SHIP-1",
            "day": "101",
            "finished_lot_id": "incident::PF-1",
            "released_qty": "4",
            "campaign_id": "CAMP-1",
        }
    )
    tables["aggregated_client_contact"].append(
        {
            "shipment_ids": "SHIP-1",
            "day": "102",
            "client_lot_id": "incident::PF-1",
            "client_node_id": "C-XXXXX",
            "service_event_qty_on_contacted_lot": "2",
        }
    )
    rows = registry.normalise_genealogy_rows(
        dossier=dossier,
        source_tables=tables,
        source_paths={
            stage: f"d/{filename}" for stage, filename in registry.TRACE_FILES.items()
        },
        incident_j0_day=100,
    )
    assert len(rows) == 4
    assert {row["genealogy_stage"] for row in rows} == set(registry.TRACE_FILES)
    consumption = next(
        row for row in rows if row["genealogy_stage"] == "consumption_and_wip"
    )
    assert consumption["campaign_id"] == "CAMP-1"
    assert consumption["batch_id"] == "BATCH-1"
    assert consumption["is_incident_j0"] is True
    client = next(
        row for row in rows if row["genealogy_stage"] == "aggregated_client_contact"
    )
    assert client["days_from_incident_j0"] == 2
    assert "client_node_id" in client["raw_record_json"]


def test_writes_valid_immutable_three_view_package(
    tmp_path: Path, payload_bundle: tuple[dict, list[str]]
) -> None:
    payload, fields = payload_bundle
    output = tmp_path / "registry_v6"
    result = registry.write_delivery(
        output_dir=output,
        payload=payload,
        cell_fields=fields,
        source_bindings={"fixture": {"sha256": "f" * 64}},
    )
    assert result["valid"] is True
    assert result["incidentExposureRowCount"] == 3240
    assert result["cellRowCount"] == 108
    document = (output / registry.HTML_FILE).read_text(encoding="utf-8")
    assert document.count('class="view') == 3
    assert "Les lots descendants" in document
    assert "lot_trace_enabled=false" in document
    assert "<script src=" not in document
    assert "<link " not in document
    assert document == registry.render_html(payload)
    with pytest.raises(FileExistsError):
        registry.write_delivery(
            output_dir=output,
            payload=payload,
            cell_fields=fields,
            source_bindings={},
        )


def test_rejects_one_missing_exposure() -> None:
    source = _fixture_inputs()
    with pytest.raises(registry.IncidentLotRegistryError, match="3 états"):
        registry.build_exposure_registry(
            incident_rows=source["metrics"][:-1],
            lanes=source["lanes"],
            requirement_modes={
                lane["lane_id"]: (
                    "dynamic_explicit"
                    if lane["lane_id"] in {"L01", "L02"}
                    else "static_explicit"
                )
                for lane in source["lanes"]
            },
            selected_dossiers=[],
            replay_dossiers=[],
        )


def test_rejects_malformed_boolean_and_duplicate_signed_case() -> None:
    with pytest.raises(registry.IncidentLotRegistryError, match="Booléen"):
        registry._typed_exposure_value("valid", "peut-être")

    source = _fixture_inputs()
    metrics = source["metrics"]
    assert isinstance(metrics, list)
    metrics[0]["case_signature"] = metrics[1]["case_signature"]
    with pytest.raises(registry.IncidentLotRegistryError, match="Preuves incomplètes"):
        registry.build_exposure_registry(
            incident_rows=metrics,
            lanes=source["lanes"],
            requirement_modes={
                lane["lane_id"]: (
                    "dynamic_explicit"
                    if lane["lane_id"] in {"L01", "L02"}
                    else "static_explicit"
                )
                for lane in source["lanes"]
            },
            selected_dossiers=[],
            replay_dossiers=[],
        )


def test_official_campaign_contract_keeps_3330_cases_and_no_forced_top3() -> None:
    checks = {
        field: True
        for field in {
            "complete_3x18x2x30_matrix",
            "same_repetitions_in_every_cell",
            "same_engine_sha256",
            "same_campaign_signature",
            "lane_identity_invariant",
            "baseline_pairing_complete",
            "paired_warmup_state_identical",
            "shipment_set_and_incident_trace_proven",
            "business_360_and_causal_windows_fully_observed",
            "all_3330_metrics_reconstructed_from_signed_case_evidence",
        }
    }
    checks.update(
        {
            "all_lots_traced": False,
            "quality_or_availability_incident_count": 0,
        }
    )
    validation = {
        "schema_version": registry.finalizer_v4.SCHEMA_VERSION,
        "status": "complete_validated",
        "campaign_signature": "a" * 64,
        "expected_contract": {
            "operating_point_count": 3,
            "incident_row_count": 3240,
            "baseline_row_count": 90,
            "lane_count": 18,
            "paired_repetition_count": 30,
            "repetition_ids": list(registry.EXPECTED_SEED_IDS),
            "mechanisms": list(registry.MECHANISMS),
            "operating_point_degradation_family": (
                "balanced_product_supplier_planned_lead"
            ),
            "operating_point_degradation_scope": (
                "planned_supplier_lead_offsets_by_finished_product_feed"
            ),
            "supplier_disruption_window_days": 42,
            "business_window_days": 360,
            "adaptive_horizons": True,
            "lot_replay_dossier_maximum": 3,
            "lot_replay_forced_top3": False,
            "all_lots_traced_claimed": False,
            "quality_branch_included": False,
            "availability_incident_included": False,
        },
        "comparability_checks": checks,
        "signed_case_evidence": {
            "status": "complete_reconstructed",
            "case_count": 3330,
            "baseline_case_count": 90,
            "incident_case_count": 3240,
        },
        "statistics": {
            "primary_ranking_metric": "impact_service_loss_fed_product_pp",
            "primary_window": "fixed_360_day_business_envelope",
            "confidence_interval": (
                "paired non-parametric bootstrap percentile interval"
            ),
            "bootstrap_replicates": 10_000,
            "forced_top3": False,
        },
        "historical_incident_probability_estimated": False,
        "industrial_supplier_criticality_claimed": False,
    }
    registry._validate_campaign_finalization_contract(validation)
    invalid = copy.deepcopy(validation)
    invalid["expected_contract"]["lot_replay_forced_top3"] = True
    with pytest.raises(registry.IncidentLotRegistryError, match="matrice"):
        registry._validate_campaign_finalization_contract(invalid)


def test_payload_rejects_genealogy_or_j0_attached_to_wrong_proof(
    payload_bundle: tuple[dict, list[str]],
) -> None:
    payload, _fields = payload_bundle
    wrong_genealogy = copy.deepcopy(payload)
    wrong_genealogy["detailedReplays"]["genealogyRows"][0]["operating_point_id"] = (
        "op_80"
    )
    with pytest.raises(registry.IncidentLotRegistryError, match="mauvais état"):
        registry._validate_payload_contract(wrong_genealogy)

    wrong_j0 = copy.deepcopy(payload)
    wrong_j0["detailedReplays"]["j0Rows"][0][
        "delta_incident_minus_baseline_at_incident_j0"
    ] = 1.0
    with pytest.raises(registry.IncidentLotRegistryError, match="J0"):
        registry._validate_payload_contract(wrong_j0)


def test_payload_retains_every_native_stage_and_unambiguous_j0(
    payload_bundle: tuple[dict, list[str]],
) -> None:
    payload, _fields = payload_bundle
    genealogy = payload["detailedReplays"]["genealogyRows"]
    assert len(genealogy) == 4
    assert {row["genealogy_stage"] for row in genealogy} == set(registry.TRACE_FILES)
    assert all(row["raw_record_json"] for row in genealogy)
    shipment = next(
        row
        for row in genealogy
        if row["genealogy_stage"] == "shipment_to_material_receipt"
    )
    assert shipment["event_day"] == 100
    assert "jour de décision" in shipment["event_day_kind"]
    consumption = next(
        row for row in genealogy if row["genealogy_stage"] == "consumption_and_wip"
    )
    assert (consumption["campaign_id"], consumption["batch_id"]) == (
        "CAMP-1",
        "BATCH-1",
    )
    assert (consumption["wip_start_qty"], consumption["wip_end_qty"]) == (8.0, 3.0)
    assert consumption["released_lot_id_same_day"] == "incident::PF-1"
    finished = next(
        row for row in genealogy if row["genealogy_stage"] == "finished_lot_release"
    )
    assert (finished["finished_lot_id"], finished["release_day"]) == (
        "incident::PF-1",
        102,
    )
    assert payload["scope"]["genealogySourceRowCount"] == 4
    j0_rows = payload["detailedReplays"]["j0Rows"]
    assert len(j0_rows) == 6
    assert all(row["is_pre_incident_snapshot"] is False for row in j0_rows)
    assert all(
        row["observation_convention"] == registry.J0_OBSERVATION_CONVENTION
        for row in j0_rows
    )


def test_refuses_output_overlapping_any_source(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    results = tmp_path / "results"
    replay = tmp_path / "replay"
    for source in (campaign, results, replay):
        source.mkdir()
    with pytest.raises(registry.IncidentLotRegistryError, match="séparé"):
        registry._validate_output_separation(
            output_dir=results / "registry",
            source_paths=(campaign, results, replay),
        )
    registry._validate_output_separation(
        output_dir=tmp_path / "delivery" / "registry",
        source_paths=(campaign, results, replay),
    )


def test_write_refuses_action_to_lot_claim_before_creating_output(
    tmp_path: Path, payload_bundle: tuple[dict, list[str]]
) -> None:
    payload, fields = payload_bundle
    tampered = copy.deepcopy(payload)
    tampered["actions"]["explanation"] = "Cette action sauve le lot PF-1."
    output = tmp_path / "must_not_exist"
    with pytest.raises(registry.IncidentLotRegistryError, match="exclusions"):
        registry.write_delivery(
            output_dir=output,
            payload=tampered,
            cell_fields=fields,
            source_bindings={"fixture": {"sha256": "f" * 64}},
        )
    assert not output.exists()


def test_runbook_uses_valid_quoted_powershell_examples() -> None:
    runbook = (
        Path(registry.__file__).with_name(
            "RUNBOOK_SUPPLIER_V6_FULL_INCIDENT_LOT_REGISTRY.md"
        )
    ).read_text(encoding="utf-8")
    assert "<DOSSIER_" not in runbook
    assert "$CampaignRoot" in runbook
    assert "dossier neuf" in runbook.casefold()
