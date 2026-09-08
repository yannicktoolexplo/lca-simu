from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as actions_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_full_incident_lot_registry as registry_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_pipeline as legacy_pipeline,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_watcher as legacy_watcher,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_pipeline as pipeline,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_watcher as watcher,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _paths(tmp_path: Path) -> common.Stage2Paths:
    repo = tmp_path / "repo"
    repo.mkdir()
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    return common.Stage2Paths(
        repo=repo,
        v7_plan_dir=upstream / "v7_plan",
        v7_run_dir=upstream / "v7_run",
        trace_package_dir=upstream / "traces",
        bridge_json=upstream / "bridge.json",
        campaign_root=upstream / "campaign_v8",
        results_dir=upstream / "results_v8",
        stage1_supervision_dir=upstream / "campaign_v8",
        observed_2025_dir=None,
        lot_replay_root=tmp_path / "out" / "lots_v8",
        qualification_dir=tmp_path / "out" / "qualification_v8",
        action_replay_root=tmp_path / "out" / "actions_v8",
        curves_dir=tmp_path / "out" / "curves_v8",
        registry_dir=tmp_path / "out" / "registry_v8",
        final_html=tmp_path / "out" / "OUVRIR_RESILIENCE_SCAN_V8.html",
        supervision_dir=tmp_path / "out" / "supervision_v8",
    ).resolved()


def _launch_evidence(paths: common.Stage2Paths, *, status: str = "complete") -> None:
    signature = "c" * 64
    manifest = {
        "campaign_signature": signature,
        "target_exposure_comparability_status": "accepted_30_of_30",
        **{flag: False for flag in common.FORBIDDEN_INCIDENT_FLAGS},
    }
    contract = common.signed(
        {
            "schema_version": "test.launch.v1",
            "campaign_signature": signature,
            "shard_ids": [f"s{i:02d}" for i in range(18)],
        },
        "launch_contract_signature",
    )
    progress = {
        "campaign_signature": signature,
        "launch_contract_signature": contract["launch_contract_signature"],
        "status": status,
        "target_discovery_status": "complete",
        "planned_shard_count": 18,
        "completed_shard_count": 18 if status == "complete" else 0,
        "failed_shard_count": 0,
        "active_shard_count": 0,
        "queued_shard_count": 0 if status == "complete" else 18,
        "completed_shard_ids": (
            [f"s{i:02d}" for i in range(18)] if status == "complete" else []
        ),
    }
    _write_json(paths.campaign_root / "campaign_manifest.json", manifest)
    _write_json(paths.campaign_root / "launch_contract.json", contract)
    _write_json(paths.campaign_root / "launch_progress.json", progress)


def _patch_complete_stage1(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    result = {
        "accepted": True,
        "publishable": True,
        "status": common.protocol_v7.ACCEPTED_STATUS,
        "validation_seed_count": 150,
        "fresh_physical_evidence_case_count": 450,
        "retuning_after_any_v7_result": False,
        "result_signature": "1" * 64,
    }
    trace = {
        "campaign_cohort": {"seeds": list(common.traces_v7.CAMPAIGN_SEEDS)},
        "run_signature": "2" * 64,
    }
    bridge = {
        "holdout_contract": {
            "campaign_baseline_contract": {
                "seeds": list(common.traces_v7.CAMPAIGN_SEEDS)
            }
        },
        "artifact_signature": "3" * 64,
    }
    overlay = {
        "overlay_signature": "4" * 64,
        "counts": {
            "validation_seed_count": 150,
            "validation_case_count": 450,
            "campaign_seed_count": 30,
            "baseline_row_count": 90,
            "incident_row_count": 3_240,
            "campaign_row_count": 3_330,
        },
        "v8_comparability_checks": {
            "accepted_v7_confirmation_150_seeds_450_cases": True,
            "same_30_seeds_for_baseline_and_incidents": True,
            "all_18_lanes_comparable_on_all_30_seeds": True,
            "selection_uses_incident_outcomes": False,
            "selection_engine_run_count": 0,
            "complete_3330_case_matrix_reconstructed": True,
            "quality_capacity_availability_stock_or_state_risk_incident_count": 0,
        },
        "target_selection_v8": {
            "revision": common.campaign_v8.TARGET_SELECTION_REVISION,
            "required_comparable_seed_count_per_lane": 30,
            "same_lane_window_across_all_states_and_seeds": True,
            "incident_outcomes_used": False,
            "additional_simulation_engine_runs": 0,
        },
    }
    dashboard = {
        "repetitions": 30,
        "laneCount": 18,
        "states": [{"id": value} for value in common.EXPECTED_STATES],
        "mechanisms": [{"id": value} for value in common.EXPECTED_MECHANISMS],
    }
    monkeypatch.setattr(common.protocol_v7, "validate_result", lambda *_a, **_k: result)
    monkeypatch.setattr(common.traces_v7, "validate_package", lambda *_a, **_k: trace)
    monkeypatch.setattr(common.bridge_v7, "validate_bridge", lambda *_a, **_k: bridge)
    monkeypatch.setattr(
        common.finalizer_v8, "validate_v8_overlay", lambda *_a, **_k: overlay
    )
    monkeypatch.setattr(
        common.dashboard_v7, "load_dashboard_data", lambda *_a, **_k: dashboard
    )
    return overlay


def test_validate_complete_stage1_requires_native_v8_30_of_30(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    _launch_evidence(paths)
    _patch_complete_stage1(monkeypatch)

    receipt = common.validate_complete_stage1(paths)

    assert receipt["status"] == "complete_validated_v8"
    assert receipt["counts"]["campaign_rows"] == 3_330
    assert receipt["target_selection_contract"] == {
        "revision": common.campaign_v8.TARGET_SELECTION_REVISION,
        "source_trace_count": 90,
        "required_comparable_seed_count_per_lane": 30,
        "lane_count": 18,
        "same_lane_window_across_all_states_and_seeds": True,
        "incident_outcomes_used": False,
        "engine_runs": 0,
        "historical_incident_probability_estimated": False,
    }
    common.verify_signature(receipt, "validation_signature", "test receipt")


def test_validate_complete_stage1_rejects_weakened_v8_exposure_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    _launch_evidence(paths)
    overlay = _patch_complete_stage1(monkeypatch)
    overlay["v8_comparability_checks"]["all_18_lanes_comparable_on_all_30_seeds"] = (
        False
    )

    with pytest.raises(common.Stage2Error, match="matrice V8 30/30"):
        common.validate_complete_stage1(paths)


def test_launch_completion_is_required(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _launch_evidence(paths, status="running")
    manifest = common.read_json(paths.campaign_root / "campaign_manifest.json")

    with pytest.raises(common.Stage2NotReady, match="18 blocs"):
        common._check_launch_completion(paths.campaign_root, manifest)  # noqa: SLF001


def test_v8_consumer_bindings_patch_and_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_campaign = actions_v4.campaign_v4
    previous_seeds = registry_v6.EXPECTED_SEED_IDS
    entered: list[bool] = []

    @contextmanager
    def fake_finalizer_context():
        entered.append(True)
        yield

    monkeypatch.setattr(
        common.finalizer_v8, "patched_v8_context", fake_finalizer_context
    )
    with common.v8_consumer_bindings():
        assert actions_v4.campaign_v4 is common.campaign_v8
        assert registry_v6.EXPECTED_SEED_IDS == tuple(common.traces_v7.CAMPAIGN_SEEDS)
    assert entered == [True]
    assert actions_v4.campaign_v4 is previous_campaign
    assert registry_v6.EXPECTED_SEED_IDS == previous_seeds


def test_pipeline_context_is_v8_scoped_and_restored() -> None:
    previous_common = legacy_pipeline.common
    previous_schema = legacy_pipeline.SCHEMA_VERSION
    previous_delivery = legacy_pipeline._delivery  # noqa: SLF001
    previous_contract_payload = legacy_pipeline._contract_payload  # noqa: SLF001

    with pipeline.patched_v8_pipeline_context():
        assert legacy_pipeline.common is common
        assert legacy_pipeline.SCHEMA_VERSION == pipeline.SCHEMA_VERSION
        assert legacy_pipeline.UPSTREAM_NAME == common.STAGE1_RECEIPT_NAME
        assert legacy_pipeline._delivery is pipeline._delivery_v8  # noqa: SLF001
        assert (
            legacy_pipeline._contract_payload is pipeline._contract_payload_v8  # noqa: SLF001
        )

    assert legacy_pipeline.common is previous_common
    assert legacy_pipeline.SCHEMA_VERSION == previous_schema
    assert legacy_pipeline._delivery is previous_delivery  # noqa: SLF001
    assert legacy_pipeline._contract_payload is previous_contract_payload  # noqa: SLF001


def test_prepare_supervision_creates_only_v8_supervision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    inventory = common.signed(
        {
            "schema_version": common.SOURCE_INVENTORY_SCHEMA_VERSION,
            "repo": str(paths.repo),
            "entry_count": 0,
            "entries": [],
            "critical_protocol_sha256": common.EXPECTED_PROTOCOL_SHA256,
            "v8_campaign_runner_sha256": "a" * 64,
            "v8_finalizer_sha256": "b" * 64,
        },
        "inventory_signature",
    )
    monkeypatch.setattr(common, "build_source_inventory", lambda _repo: inventory)
    monkeypatch.setattr(common, "verify_source_inventory", lambda _inventory: None)

    contract = pipeline.prepare_supervision(paths)

    assert contract["schema_version"] == f"{pipeline.SCHEMA_VERSION}.contract.v1"
    assert contract["scientific_contract"]["v8_result_overlay_required"] is True
    assert (
        contract["scientific_contract"]["target_exposure_gate"]
        == "18_lanes_each_comparable_on_30_of_30_seeds"
    )
    assert (
        contract["scientific_contract"]["target_selection_uses_incident_outcomes"]
        is False
    )
    assert (paths.supervision_dir / pipeline.CONTRACT_NAME).is_file()
    assert (paths.supervision_dir / pipeline.STATUS_NAME).is_file()
    status = common.read_json(paths.supervision_dir / pipeline.STATUS_NAME)
    assert status["schema_version"] == f"{pipeline.SCHEMA_VERSION}.status.v1"
    assert status["status"] == "armed_waiting_for_stage1"
    assert all(not path.exists() for path in paths.output_roots[:-1])
    assert all(not path.exists() for path in paths.output_files)


def test_watcher_context_targets_v8_child_and_restores() -> None:
    previous_common = legacy_watcher.common
    previous_pipeline = legacy_watcher.pipeline
    previous_module = legacy_watcher.MODULE_NAME

    with watcher.patched_v8_watcher_context():
        assert legacy_watcher.common is common
        assert legacy_watcher.pipeline is pipeline
        assert legacy_watcher.MODULE_NAME == watcher.MODULE_NAME
        assert legacy_watcher.RESERVATION_SCHEMA_VERSION.startswith(
            watcher.SCHEMA_VERSION
        )

    assert legacy_watcher.common is previous_common
    assert legacy_watcher.pipeline is previous_pipeline
    assert legacy_watcher.MODULE_NAME == previous_module
