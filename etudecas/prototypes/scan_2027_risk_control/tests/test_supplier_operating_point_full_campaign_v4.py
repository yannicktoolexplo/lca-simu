from __future__ import annotations

from dataclasses import asdict

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4 as subject,
)


def _lane(index: int) -> subject.Lane:
    return subject.Lane(
        lane_id=f"lane_{index:02d}",
        supplier_id=f"SUP-{index:02d}",
        item_id=f"item:{index:06d}",
        dst_node_id="M-1810" if index % 2 else "M-1430",
        edge_id=f"edge:{index:02d}",
        target_product_id="268091" if index % 2 else "268967",
        planned_lead_days=10.0,
    )


def _shipment(lane: subject.Lane, *, seed: int, quantity: float = 100.0) -> dict[str, object]:
    return {
        "day": 100,
        "shipment_id": f"{lane.lane_id}-{seed}",
        "risk_decision_day": 100,
        "risk_event_ids": "",
        "src_node_id": lane.supplier_id,
        "dst_node_id": lane.dst_node_id,
        "item_id": lane.item_id,
        "edge_id": lane.edge_id,
        "shipped_qty": quantity,
        "pulled_qty": quantity,
        "lead_days": 10,
        "arrival_day": 110,
        "reliability": 1.0,
        "uom": "UN",
    }


def test_v4_design_reuses_fresh_holdout_and_keeps_eighteen_shards() -> None:
    assert subject.SCHEMA_VERSION.endswith(".v4")
    assert subject.CASE_SCHEMA_VERSION.endswith(".case.v1")
    assert subject.TARGET_DESIGN_SEED == 900659036
    assert len(subject.SEEDS) == 30
    assert subject.TARGET_DESIGN_SEED not in subject.SEEDS
    assert len(subject.SEED_BLOCKS) == 6
    assert subject._planned_case_count(5, 18) == 185
    assert 3 * subject._planned_case_count(30, 18) == 3330


def test_state_binding_is_a_zero_run_exact_v4_reference() -> None:
    states = {
        point: {"pooled": {"system_on_due_service": value}}
        for point, value in (("op_100", 0.99), ("op_93", 0.93), ("op_80", 0.80))
    }
    bridge = {
        "status": subject.v4_contract.BRIDGE_ACCEPTED_STATUS,
        "artifact_signature": "a" * 64,
        "trace_index_signature": "b" * 64,
        "source": {
            "plan_signature": "c" * 64,
            "development_selection_signature": "d" * 64,
            "holdout_signature": "e" * 64,
        },
        "holdout_contract": {
            "accepted": True,
            "publishable": True,
            "retuning_after_holdout": False,
            "evidence_case_count": 90,
            "state_summaries": states,
            "paired_bootstrap_global_descriptive_only": {
                "intervals": {
                    point: {"ci95_low": value - 0.01, "ci95_high": value + 0.01}
                    for point, value in (
                        ("op_100", 0.99),
                        ("op_93", 0.93),
                        ("op_80", 0.80),
                    )
                }
            },
        },
    }
    manifest = {
        "campaign_signature": "f" * 64,
        "operating_points_input_status": subject.v4_contract.BRIDGE_ACCEPTED_STATUS,
        "operating_points_artifact_signature": "a" * 64,
    }

    binding = subject._build_v4_state_validation_binding(
        manifest=manifest, bridge=bridge
    )

    assert binding["state_validation_engine_runs_in_campaign"] == 0
    assert binding["imported_official_service_proof_count"] == 90
    assert binding["imported_official_shipment_trace_count"] == 90
    assert binding["design_seed_in_acceptance_statistics"] is False
    assert binding["retuning_after_holdout"] is False
    unsigned = dict(binding)
    signature = unsigned.pop("binding_signature")
    assert signature == subject._stable_sha256(unsigned)


def test_target_registry_uses_three_design_runs_and_ninety_imported_traces() -> None:
    lanes = [_lane(index) for index in range(1, 19)]
    points = [
        {"operating_point_id": point}
        for point in subject.OPERATING_POINT_IDS
    ]
    rows = {
        (point, seed): [
            _shipment(lane, seed=seed, quantity=100.0 + point_index)
            for lane in lanes
        ]
        for point_index, point in enumerate(subject.OPERATING_POINT_IDS)
        for seed in (subject.TARGET_DESIGN_SEED, *subject.SEEDS)
    }
    manifest = {
        "campaign_signature": "a" * 64,
        "engine_sha256": "b" * 64,
    }

    registry = subject.build_cross_state_target_registry(
        manifest=manifest,
        points=points,
        lanes=lanes,
        shipment_rows_by_state_seed=rows,
    )

    assert registry["schema_version"].endswith(".target_registry.v1")
    assert registry["design_seed"] == subject.TARGET_DESIGN_SEED
    assert registry["campaign_seeds"] == list(subject.SEEDS)
    assert len(registry["targets"]) == 3 * 30 * 18
    assert registry["campaign_exposure_gate_passed"] is True


def test_imported_holdout_traces_use_exact_dynamic_filter_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lanes = [_lane(index) for index in range(1, 19)]
    points = [
        {"operating_point_id": point, "graph_sha256": str(index + 1) * 64}
        for index, point in enumerate(subject.OPERATING_POINT_IDS)
    ]
    trace_index = [
        {
            "operating_point_id": point["operating_point_id"],
            "seed": seed,
            "candidate_key": f"candidate-{point['operating_point_id']}",
            "candidate_id": f"id-{point['operating_point_id']}",
            "shipment_trace": {"fixture": True},
        }
        for point in points
        for seed in subject.SEEDS
    ]
    bridge = {
        "source": {"run_dir": ".", "plan_signature": "a" * 64},
        "source_hashes": {"engine_sha256": "b" * 64},
        "trace_index": trace_index,
    }
    exact_filter = subject.v4_contract.trace_filter_contract(
        [asdict(lane) for lane in lanes]
    )
    seen = 0

    def validate_trace_reference(reference, *, run_dir, expected, allowed_lane_ids):
        nonlocal seen
        seen += 1
        assert expected["filter_contract"] == exact_filter
        assert set(allowed_lane_ids) == {lane.lane_id for lane in lanes}
        return dict(reference), {"rows": []}

    monkeypatch.setattr(
        subject.v4_contract,
        "validate_trace_reference",
        validate_trace_reference,
    )

    imported = subject._import_v4_holdout_shipment_rows(
        bridge_path=subject.Path("unused.json"),
        bridge=bridge,
        points=points,
        lanes=lanes,
    )

    assert seen == 90
    assert set(imported) == {
        (point, seed) for point in subject.OPERATING_POINT_IDS for seed in subject.SEEDS
    }


def test_transport_effective_dose_uses_physically_shipped_not_pulled_quantity() -> None:
    row = subject._flatten_metric_row(
        {
            "stage": "incident",
            "mechanism": {"key": "transport_delay"},
            "lane": {"target_product_id": "268091"},
            "target": {"target_expected_delivered_qty": 80.0},
            "incident_proof": {
                "incident_affected_pulled_qty": 100.0,
                "incident_affected_shipped_qty": 70.0,
            },
        },
        baseline_by_signature={},
    )

    assert row["incident_effective_dose_qty_days"] == 120.0 * 70.0
    assert row["incident_reference_dose_qty_days"] == 120.0 * 80.0


def test_shortfall_wording_uses_normally_deliverable_quantity() -> None:
    mechanism = next(
        value
        for value in subject.MECHANISMS
        if value.key == "planned_delivery_shortfall"
    )
    assert "normalement livrable" in mechanism.label_fr
    assert "quantité planifiée reçue" not in mechanism.label_fr


def test_smoke_selects_first_comparable_positive_op93_case() -> None:
    registry = {
        "lanes": ["lane_01", "lane_02"],
        "targets": [
            {
                "operating_point_id": "op_93",
                "seed": subject.SEEDS[1],
                "lane_id": "lane_01",
                "seed_cross_state_exposure_comparable": True,
                "target_status": "identified_grouped_reference_shipments",
                "target_planned_qty": 10.0,
            },
            {
                "operating_point_id": "op_93",
                "seed": subject.SEEDS[0],
                "lane_id": "lane_02",
                "seed_cross_state_exposure_comparable": True,
                "target_status": "identified_grouped_reference_shipments",
                "target_planned_qty": 10.0,
            },
        ],
    }

    assert subject.select_smoke_case(registry) == (subject.SEEDS[1], "lane_01")


def test_smoke_and_campaign_case_signatures_cannot_be_reused() -> None:
    point = {
        "operating_point_id": "op_93",
        "graph_sha256": "1" * 64,
        "supplier_floors_sha256": "",
        "factory_capacities_sha256": "",
    }
    common = {
        "campaign_signature": "2" * 64,
        "engine_sha256": "3" * 64,
        "target_registry_signature": "4" * 64,
        "operating_points_holdout_signature": "5" * 64,
        "operating_points_trace_index_signature": "6" * 64,
        "state_validation_binding_signature": "7" * 64,
    }
    campaign = subject._case_signature(
        manifest={**common, "execution_scope": "campaign_shard"},
        point=point,
        seed=subject.SEEDS[0],
        stage="baseline",
        simulation_days=720,
    )
    smoke = subject._case_signature(
        manifest={**common, "execution_scope": "smoke_non_reusable"},
        point=point,
        seed=subject.SEEDS[0],
        stage="baseline",
        simulation_days=720,
    )

    assert campaign != smoke


def test_target_registry_loader_recomputes_every_state_seed_lane_cell(tmp_path) -> None:
    lanes = [_lane(index) for index in range(1, 19)]
    points = [
        {"operating_point_id": point}
        for point in subject.OPERATING_POINT_IDS
    ]
    rows = {
        (point, seed): [
            _shipment(lane, seed=seed, quantity=100.0 + point_index)
            for lane in lanes
        ]
        for point_index, point in enumerate(subject.OPERATING_POINT_IDS)
        for seed in (subject.TARGET_DESIGN_SEED, *subject.SEEDS)
    }
    campaign_signature = "a" * 64
    manifest = {
        "campaign_signature": campaign_signature,
        "engine_sha256": "b" * 64,
        "operating_points_input_status": subject.v4_contract.BRIDGE_ACCEPTED_STATUS,
        "operating_points_artifact_signature": "c" * 64,
        "operating_points_calibration_plan_signature": "d" * 64,
        "operating_points_selection_signature": "e" * 64,
        "operating_points_holdout_signature": "f" * 64,
        "operating_points_trace_index_signature": "1" * 64,
        "state_validation_binding_status": subject.HOLDOUT_ACCEPTED_STATUS,
        "target_discovery_status": "complete",
    }
    registry = subject.build_cross_state_target_registry(
        manifest=manifest,
        points=points,
        lanes=lanes,
        shipment_rows_by_state_seed=rows,
    )
    discovery = tmp_path / "target_discovery"
    discovery.mkdir()
    registry_path = discovery / "target_registry.json"
    subject._write_json_atomic(registry_path, registry)
    manifest.update(
        {
            "target_registry_sha256": subject._sha256_file(registry_path),
            "target_registry_signature": registry["registry_signature"],
        }
    )
    binding_unsigned = {
        "schema_version": subject.PREFLIGHT_SCHEMA_VERSION,
        "contract_revision": subject.CONTRACT_REVISION,
        "campaign_signature": campaign_signature,
        "status": subject.HOLDOUT_ACCEPTED_STATUS,
        "operating_points_input_status": manifest["operating_points_input_status"],
        "operating_points_artifact_signature": manifest[
            "operating_points_artifact_signature"
        ],
        "v4_plan_signature": manifest[
            "operating_points_calibration_plan_signature"
        ],
        "v4_development_selection_signature": manifest[
            "operating_points_selection_signature"
        ],
        "v4_holdout_signature": manifest["operating_points_holdout_signature"],
        "v4_trace_index_signature": manifest[
            "operating_points_trace_index_signature"
        ],
        "state_validation_engine_runs_in_campaign": 0,
        "imported_official_service_proof_count": 90,
        "imported_official_shipment_trace_count": 90,
        "retuning_after_holdout": False,
    }
    binding = {
        **binding_unsigned,
        "binding_signature": subject._stable_sha256(binding_unsigned),
    }
    binding_path = discovery / "state_validation_binding.json"
    subject._write_json_atomic(binding_path, binding)
    manifest.update(
        {
            "state_validation_binding": str(binding_path),
            "state_validation_binding_sha256": subject._sha256_file(binding_path),
            "state_validation_binding_signature": binding["binding_signature"],
        }
    )

    assert subject.load_target_registry(
        output_dir=tmp_path, manifest=manifest, lanes=lanes
    ) == registry

    tampered = dict(registry)
    tampered["targets"] = [dict(row) for row in registry["targets"]]
    tampered["targets"][0]["target_window_start_day"] += 1
    unsigned = dict(tampered)
    unsigned.pop("registry_signature")
    tampered["registry_signature"] = subject._stable_sha256(unsigned)
    subject._write_json_atomic(registry_path, tampered)
    manifest["target_registry_sha256"] = subject._sha256_file(registry_path)
    manifest["target_registry_signature"] = tampered["registry_signature"]

    with pytest.raises(ValueError, match="target cell"):
        subject.load_target_registry(
            output_dir=tmp_path, manifest=manifest, lanes=lanes
        )
