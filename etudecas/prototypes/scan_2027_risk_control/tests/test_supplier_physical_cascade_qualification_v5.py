from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as qualification,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as replay_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_protocol as service_protocol,
)


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _lanes() -> list[dict]:
    result = [
        {
            "lane_id": "lane-dynamic-338929",
            "supplier_id": "SUP-A",
            "item_id": "item:338929",
            "dst_node_id": "M-1810",
            "edge_id": "EDGE-A",
            "target_product_id": "268091",
        },
        {
            "lane_id": "lane-dynamic-344135",
            "supplier_id": "SUP-B",
            "item_id": "item:344135",
            "dst_node_id": "M-1430",
            "edge_id": "EDGE-B",
            "target_product_id": "268967",
        },
    ]
    for index in range(16):
        result.append(
            {
                "lane_id": f"lane-static-{index:02d}",
                "supplier_id": f"SUP-{index:02d}",
                "item_id": f"item:{100000 + index}",
                "dst_node_id": "M-1810" if index % 2 == 0 else "M-1430",
                "edge_id": f"EDGE-{index:02d}",
                "target_product_id": "268091" if index % 2 == 0 else "268967",
            }
        )
    return result


def _mode_args(lanes: list[dict]) -> tuple[list[str], list[str]]:
    profile: list[str] = []
    for lane in lanes:
        profile.extend(
            [
                "--mrp-static-requirement-pair",
                f"{lane['dst_node_id']},{lane['item_id']}",
            ]
        )
    managed = [
        "--mrp-dynamic-requirement-pair",
        "M-1810,item:338929",
        "--mrp-dynamic-requirement-pair",
        "M-1430,item:344135",
        "--mrp-dynamic-requirement-pair",
        "SDC-1450,item:021081",
    ]
    return profile, managed


def test_requirement_scope_is_exactly_two_dynamic_and_sixteen_static() -> None:
    lanes = _lanes()
    profile, managed = _mode_args(lanes)
    modes, static_pairs, dynamic_pairs = qualification.resolve_lane_requirement_modes(
        lanes=lanes,
        profile_args=profile,
        managed_args=managed,
    )
    assert Counter(modes.values()) == Counter(
        {"dynamic_explicit": 2, "static_explicit": 16}
    )
    assert modes["lane-dynamic-338929"] == "dynamic_explicit"
    assert modes["lane-dynamic-344135"] == "dynamic_explicit"
    assert len(static_pairs) == 16
    assert set(dynamic_pairs) == set(qualification.EXPECTED_CONFIGURED_DYNAMIC_PAIRS)


def test_requirement_scope_fails_closed_if_dynamic_scope_changes() -> None:
    lanes = _lanes()
    profile, managed = _mode_args(lanes)
    managed.extend(["--mrp-dynamic-requirement-pair", "M-1810,item:100000"])
    with pytest.raises(
        qualification.PhysicalCascadeQualificationError,
        match="three-pair dynamic MRP scope",
    ):
        qualification.resolve_lane_requirement_modes(
            lanes=lanes,
            profile_args=profile,
            managed_args=managed,
        )


def test_repository_frozen_command_qualifies_the_actual_eighteen_lanes() -> None:
    identities = (
        ("sdc_vd0505677a_099439_m_1810", "M-1810", "item:099439"),
        ("sdc_vd0508918a_730384_m_1430", "M-1430", "item:730384"),
        ("sdc_vd0514881a_016332_m_1810", "M-1810", "item:016332"),
        ("sdc_vd0519670a_001848_m_1810", "M-1810", "item:001848"),
        ("sdc_vd0519670a_029313_m_1810", "M-1810", "item:029313"),
        ("sdc_vd0520115a_708073_m_1430", "M-1430", "item:708073"),
        ("sdc_vd0520132a_038005_m_1430", "M-1430", "item:038005"),
        ("sdc_vd0520132a_049371_m_1810", "M-1810", "item:049371"),
        ("sdc_vd0525412a_333362_m_1430", "M-1430", "item:333362"),
        ("sdc_vd0901566a_338928_m_1810", "M-1810", "item:338928"),
        ("sdc_vd0910216a_001893_m_1810", "M-1810", "item:001893"),
        ("sdc_vd0914320a_055703_m_1810", "M-1810", "item:055703"),
        ("sdc_vd0914360c_338929_m_1810", "M-1810", "item:338929"),
        ("sdc_vd0914690a_042342_m_1430", "M-1430", "item:042342"),
        ("sdc_vd0951020a_001757_m_1810", "M-1810", "item:001757"),
        ("sdc_vd0989480a_426331_m_1810", "M-1810", "item:426331"),
        ("sdc_vd0993480a_344135_m_1430", "M-1430", "item:344135"),
        ("sdc_vd1095770a_734545_m_1430", "M-1430", "item:734545"),
    )
    lanes = [
        {"lane_id": lane_id, "dst_node_id": node_id, "item_id": item_id}
        for lane_id, node_id, item_id in identities
    ]
    profile_path = (
        Path(qualification.__file__).resolve().parent
        / "config"
        / "canonical_real_baseline_engine_profile.json"
    )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    modes, _static, _dynamic = qualification.resolve_lane_requirement_modes(
        lanes=lanes,
        profile_args=profile["args"],
        managed_args=list(service_protocol.MANAGED_REFERENCE_PROTOCOL_ARGS),
    )
    assert {
        lane_id for lane_id, mode in modes.items() if mode == "dynamic_explicit"
    } == {
        "sdc_vd0914360c_338929_m_1810",
        "sdc_vd0993480a_344135_m_1430",
    }


def test_trace_levels_are_complete_partial_or_not_exercised() -> None:
    complete = {field: 1 for field in qualification.REQUIRED_TRACE_COUNT_FIELDS}
    assert qualification._qualify_trace_counts(complete) == ("complete", [])
    partial = {**complete, "client_events": 0}
    assert qualification._qualify_trace_counts(partial) == (
        "partial",
        ["client_events"],
    )
    not_exercised = {**complete, "shipments": 0}
    assert qualification._qualify_trace_counts(not_exercised)[0] == "not_exercised"


def _trace_inventory(
    root: Path, dossier_id: str, *, client: bool = True
) -> dict[str, Path]:
    dossier = root / "finalized" / "dossiers" / dossier_id
    shipment = dossier / "shipment_to_mp_lots.csv"
    consumption = dossier / "exposed_consumption_wip.csv"
    finished = dossier / "exposed_finished_lots.csv"
    clients = dossier / "exposed_client_events.csv"
    kpis = dossier / "dossier_kpis.json"
    _write_csv(
        shipment,
        (
            "shipment_id",
            "receipt_lot_id",
            "parent_qty",
            "child_qty",
            "incident_event_id",
        ),
        [
            {
                "shipment_id": "SHIP-1",
                "receipt_lot_id": "incident::MP-1",
                "parent_qty": "10",
                "child_qty": "10",
                "incident_event_id": "RISK-1",
            }
        ],
    )
    _write_csv(
        consumption,
        ("shipment_ids", "material_lot_id", "consumed_qty", "campaign_id", "batch_id"),
        [
            {
                "shipment_ids": "SHIP-1",
                "material_lot_id": "incident::MP-1",
                "consumed_qty": "4",
                "campaign_id": "CAMPAIGN-1",
                "batch_id": "BATCH-1",
            }
        ],
    )
    _write_csv(
        finished,
        ("shipment_ids", "finished_lot_id", "released_qty", "campaign_id", "claim"),
        [
            {
                "shipment_ids": "SHIP-1",
                "finished_lot_id": "incident::PF-1",
                "released_qty": "2",
                "campaign_id": "CAMPAIGN-1",
                "claim": "native_genealogical_contact_not_cross_arm_identity",
            }
        ],
    )
    _write_csv(
        clients,
        (
            "shipment_ids",
            "client_lot_id",
            "client_node_id",
            "service_event_qty_on_contacted_lot",
            "claim",
        ),
        (
            [
                {
                    "shipment_ids": "SHIP-1",
                    "client_lot_id": "incident::CLIENT-1",
                    "client_node_id": "C-XXXXX",
                    "service_event_qty_on_contacted_lot": "1",
                    "claim": "native_genealogical_contact_not_incremental_service_loss",
                }
            ]
            if client
            else []
        ),
    )
    kpis.write_text(
        json.dumps(
            {
                "first_component_stock_divergence_day": 12,
                "first_production_divergence_day": 20,
                "first_service_divergence_day": 24,
                "service_loss_pp": 1.2,
                "production_released_loss_qty": 2.0,
                "cross_arm_lot_matching_used": False,
            }
        ),
        encoding="utf-8",
    )
    return {
        path.relative_to(root).as_posix(): path
        for path in (shipment, consumption, finished, clients, kpis)
    }


def _replay_inputs(dossier_id: str, *, client: bool = True) -> tuple[dict, dict, dict]:
    selected = {
        "dossier_id": dossier_id,
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": "lane-dynamic-338929",
        "representative_seed": 123,
        "valid_exercised_seed_count": 28,
    }
    plan = {
        "dossier_id": dossier_id,
        "priority": {
            "operating_point_id": selected["operating_point_id"],
            "mechanism": selected["mechanism"],
            "lane_id": selected["lane_id"],
        },
        "incident_metric": {
            "incident_physically_exercised": "true",
            "status": "valid",
            "representative_valid_exercised_seed_count": "28",
        },
    }
    counts = {
        "shipments": 1,
        "material_receipts": 1,
        "consumptions": 1,
        "campaigns": 1,
        "batches": 1,
        "finished_lots": 1,
        "client_events": int(client),
        "clients": int(client),
    }
    validation = {
        "dossier_id": dossier_id,
        "status": "native_trace_to_client"
        if client
        else "native_trace_to_finished_product",
        "pair_proof": {"incident": {"tagged_shipment_count": 1}},
        "trace_counts": counts,
        "cross_arm_lot_matching_used": False,
        "quality_incident_included": False,
        "state_dependent_supplier_risks_enabled": False,
    }
    return plan, validation, selected


def test_replay_dossier_complete_is_only_a_native_client_trace(tmp_path: Path) -> None:
    dossier_id = "dossier-1"
    inventory = _trace_inventory(tmp_path, dossier_id)
    plan, validation, selected = _replay_inputs(dossier_id)
    result = qualification._validated_replay_dossier(
        plan_dossier=plan,
        replay_validation=validation,
        inventory=inventory,
        selected=selected,
        requirement_mode="dynamic_explicit",
    )
    assert result["proof_level"] == "complete"
    assert result["trace_counts"]["client_events"] == 1
    assert result["signed_mrp_response_trace_available"] is False
    assert result["full_dynamic_stock_mrp_production_service_cascade_proven"] is False
    assert result["complete_cascade_label_allowed"] is False
    assert (
        "signed_mrp_response_trace_absent"
        in result["full_dynamic_cascade_missing_proofs"]
    )


def test_replay_dossier_without_client_is_partial(tmp_path: Path) -> None:
    dossier_id = "dossier-1"
    inventory = _trace_inventory(tmp_path, dossier_id, client=False)
    plan, validation, selected = _replay_inputs(dossier_id, client=False)
    result = qualification._validated_replay_dossier(
        plan_dossier=plan,
        replay_validation=validation,
        inventory=inventory,
        selected=selected,
        requirement_mode="static_explicit",
    )
    assert result["proof_level"] == "partial"
    assert result["missing_native_trace_stages"] == ["client_events"]
    assert (
        "dynamic_mrp_requirement_not_configured"
        in result["full_dynamic_cascade_missing_proofs"]
    )


def _selection_fixture(
    tmp_path: Path,
) -> tuple[qualification.CampaignContext, dict, dict, dict]:
    campaign = tmp_path / "campaign"
    evidence_path = campaign / "shards" / "s1" / "case_evidence" / "incident.json"
    risk_path = campaign / "shards" / "s1" / "inputs" / "risk_events" / "incident.csv"
    risk_path.parent.mkdir(parents=True, exist_ok=True)
    risk_path.write_text("event_id\nRISK-1\n", encoding="utf-8")
    lane = {
        "lane_id": "lane-dynamic-338929",
        "supplier_id": "SUP-A",
        "item_id": "item:338929",
        "dst_node_id": "M-1810",
        "edge_id": "EDGE-A",
        "target_product_id": "268091",
    }
    metric = {
        "campaign_signature": "a" * 64,
        "engine_sha256": "b" * 64,
        "case_key": "incident",
        "case_signature": "c" * 64,
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": lane["lane_id"],
        "seed": "123",
        "stage": "incident",
        "simulation_days": "720",
        "valid": "true",
        "status": "valid",
        "incident_physically_exercised": "true",
        "risk_applied_row_count": "1",
        "risk_applied_event_count": "1",
    }
    evidence_unsigned = {
        "schema_version": replay_v4.CASE_SCHEMA_VERSION,
        "campaign_signature": metric["campaign_signature"],
        "engine_sha256": metric["engine_sha256"],
        "case_key": metric["case_key"],
        "case_signature": metric["case_signature"],
        "operating_point_id": metric["operating_point_id"],
        "stage": "incident",
        "seed": 123,
        "simulation_days": 720,
        "valid": True,
        "status": "valid",
        "quality_branch_included": False,
        "availability_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "lane": lane,
        "incident_proof": {
            "incident_physically_exercised": True,
            "tagged_shipment_row_count": 1,
            "incident_shipment_count": 1,
            "applied_rows": [{"event_ids": "RISK-1"}],
            "stressed_shipment_ids": ["SHIP-1"],
            "incident_affected_shipped_qty": 10.0,
            "arrival_delay_days": 120,
            "quantity_shortfall_qty": 0.0,
        },
        "metrics": {
            "risk_applied_row_count": 1,
            "risk_applied_event_count": 1,
        },
        "risk_csv_sha256": qualification.sha256_file(risk_path),
    }
    evidence = {
        **evidence_unsigned,
        "evidence_signature": replay_v4.stable_sha256(evidence_unsigned),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    selected = {
        "dossier_id": "dossier-1",
        "operating_point_id": "op_93",
        "mechanism": "transport_delay",
        "lane_id": lane["lane_id"],
        "supplier_id": lane["supplier_id"],
        "item_id": lane["item_id"],
        "dst_node_id": lane["dst_node_id"],
        "edge_id": lane["edge_id"],
        "target_product_id": lane["target_product_id"],
        "priority_status": "robust_priority",
        "representative_seed": 123,
        "valid_exercised_seed_count": 28,
        "incident_case_key": metric["case_key"],
        "incident_case_signature": metric["case_signature"],
        "incident_evidence_path": evidence_path.relative_to(campaign).as_posix(),
        "incident_evidence_sha256": qualification.sha256_file(evidence_path),
        "risk_csv_path": risk_path.relative_to(campaign).as_posix(),
        "risk_csv_sha256": qualification.sha256_file(risk_path),
    }
    context = qualification.CampaignContext(
        campaign_root=campaign,
        results_dir=tmp_path / "results",
        manifest_path=campaign / "campaign_manifest.json",
        manifest={
            "campaign_signature": metric["campaign_signature"],
            "engine_sha256": metric["engine_sha256"],
        },
        validation_path=tmp_path / "results" / "campaign_validation.json",
        validation={},
        selection_path=tmp_path / "results" / "lot_replay_plan.json",
        selection={},
        metric_paths=(),
        metrics=(metric,),
        lanes=(lane,),
        requirement_modes={lane["lane_id"]: "dynamic_explicit"},
        configured_static_pairs=(),
        configured_dynamic_pairs=(),
    )
    return context, selected, metric, evidence


def test_selected_dossier_validator_requires_risk_applied_shipment(
    tmp_path: Path,
) -> None:
    context, selected, metric, _evidence = _selection_fixture(tmp_path)
    valid = qualification._validated_selected_dossier(
        context=context,
        selected=selected,
        metric_index={metric["case_key"]: metric},
        lane_by_id={context.lanes[0]["lane_id"]: context.lanes[0]},
    )
    assert valid["campaign_shipment_exercised"] is True
    assert valid["tagged_shipment_count"] == 1

    invalid_metric = {**metric, "incident_physically_exercised": "false"}
    with pytest.raises(
        qualification.PhysicalCascadeQualificationError,
        match="not physically exercised",
    ):
        qualification._validated_selected_dossier(
            context=context,
            selected=selected,
            metric_index={metric["case_key"]: invalid_metric},
            lane_by_id={context.lanes[0]["lane_id"]: context.lanes[0]},
        )


def _sidecar_payload() -> dict:
    lanes = []
    for index, lane in enumerate(_lanes()):
        mode = "dynamic_explicit" if index < 2 else "static_explicit"
        lanes.append(
            {
                **lane,
                "site_item_pair": f"{lane['dst_node_id']}|{lane['item_id']}",
                "mrp_requirement_mode": mode,
                "physical_interpretation": "test",
                "campaign_incident_run_count": 180,
                "campaign_shipment_exercised_run_count": 1,
                "campaign_shipment_not_exercised_run_count": 179,
                "campaign_shipment_exercise_rate": 1 / 180,
                "campaign_cells": [],
                "selected_dossier_ids": [],
                "selected_dossier_proof_levels": [],
                "proof_level": "partial",
                "proof_scope": "campaign_supplier_shipment_exercise_only",
                "display_label_fr": "Exposition fournisseur exercée",
                "signed_mrp_response_trace_available": False,
                "full_dynamic_stock_mrp_production_service_cascade_proven": False,
                "complete_cascade_label_allowed": False,
            }
        )
    unsigned = {
        "schema_version": qualification.PAYLOAD_SCHEMA_VERSION,
        "status": "complete_qualified",
        "producer": "test",
        "producer_sha256": qualification.sha256_file(Path(qualification.__file__)),
        "source": {
            "campaign_signature": "a" * 64,
            "selection_signature": "b" * 64,
            "replay_validation_signature": "",
        },
        "requirement_scope": {},
        "evidence_semantics": {"mrp_response_evidence_in_v4_replay_contract": False},
        "selection_guard": {},
        "counts": {
            "lane_count": 18,
            "dynamic_mrp_lane_count": 2,
            "static_mrp_lane_count": 16,
            "selected_dossier_count": 0,
            "lane_proof_level_counts": {
                "complete": 0,
                "not_exercised": 0,
                "partial": 18,
            },
            "dossier_proof_level_counts": {
                "complete": 0,
                "not_exercised": 0,
                "partial": 0,
            },
            "full_dynamic_cascade_proven_count": 0,
        },
        "lanes": lanes,
        "dossiers": [],
    }
    unsigned["scope_signature"] = qualification.stable_sha256(
        {
            "lanes": lanes,
            "dossiers": [],
            "requirement_scope": unsigned["requirement_scope"],
            "evidence_semantics": unsigned["evidence_semantics"],
        }
    )
    return {
        **unsigned,
        "qualification_signature": qualification.stable_sha256(unsigned),
    }


def test_sidecar_is_signed_idempotent_and_refuses_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _sidecar_payload()
    monkeypatch.setattr(
        qualification,
        "build_qualification_payload",
        lambda **_kwargs: payload,
    )
    output = tmp_path / "qualification"
    kwargs = {
        "campaign_root": tmp_path / "campaign",
        "results_dir": tmp_path / "results",
        "replay_root": None,
        "output_dir": output,
    }
    first = qualification.build_qualification_sidecar(**kwargs)
    first_bytes = {path.name: path.read_bytes() for path in sorted(output.iterdir())}
    second = qualification.build_qualification_sidecar(**kwargs)
    second_bytes = {path.name: path.read_bytes() for path in sorted(output.iterdir())}
    assert first == second == payload
    assert first_bytes == second_bytes

    table = output / qualification.LANE_TABLE_FILE
    table.write_bytes(table.read_bytes() + b"tamper")
    with pytest.raises(
        qualification.PhysicalCascadeQualificationError,
        match="SHA-256 mismatch",
    ):
        qualification.validate_qualification_sidecar(**kwargs)
