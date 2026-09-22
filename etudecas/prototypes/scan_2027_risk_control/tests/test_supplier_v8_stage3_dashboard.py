from __future__ import annotations

import copy
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_dashboard as subject,
)


@pytest.fixture(scope="module")
def real_registry(historical_artifact) -> tuple[dict, dict]:
    root = historical_artifact("supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2")
    path = historical_artifact("supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2/target_discovery/target_registry.json")
    evidence = subject.validate_registry_file(root, path)
    return subject._read_json(path), evidence


@pytest.fixture
def synthetic_registry() -> tuple[dict, dict]:
    """Small in-memory evidence for the native reader, not a historical replay."""
    lanes = [f"synthetic-lane-{index:02d}" for index in range(18)]
    states = list(subject.EXPECTED_STATES)
    seeds = list(subject.EXPECTED_SEEDS)
    registry = {
        "schema_version": subject.campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION,
        "target_selection_revision": subject.campaign_v8.TARGET_SELECTION_REVISION,
        "campaign_signature": "a" * 64, "engine_sha256": "b" * 64,
        "states": states, "seeds": seeds, "campaign_seeds": seeds,
        "lanes": lanes, "target_cell_count": 1620,
        "required_comparable_seed_count": 30, "all_lane_windows_comparable": True,
        "campaign_exposure_gate_passed": True, "exposure_gate_failures": [],
        "incident_outcomes_used": False, "incident_probes_started": False,
        "target_selection_engine_runs": 0, "disruption_window_days": 42,
        "lane_contracts": [
            {"lane_id": lane, "fixed_window_start_day": 180, "fixed_window_end_day": 221,
             "disruption_window_days": 42, "comparable_campaign_seed_count": 30,
             "required_comparable_seed_count": 30, "state_comparison_valid": True,
             "selected_start_is_earliest_eligible": True, "target_selection_engine_runs": 0,
             "incident_outcomes_used": False} for lane in lanes
        ],
        "targets": [
            {"lane_id": lane, "operating_point_id": state, "seed": seed,
             "target_window_start_day": 180, "target_window_end_day": 221,
             "target_window_days": 42, "required_comparable_seed_count": 30,
             "comparable_campaign_seed_count": 30, "state_comparison_valid": True,
             "seed_cross_state_exposure_comparable": True,
             "target_expected_delivered_qty": index + 1, "target_shipment_count": 2,
             "target_uom": "unit"}
            for lane in lanes for state in states for index, seed in enumerate(seeds)
        ],
    }
    registry["registry_signature"] = subject._canonical_signature(registry, "registry_signature")
    return registry, {key: registry[key] for key in ("campaign_signature", "engine_sha256", "registry_signature")}


def test_native_reader_reduces_synthetic_matrix(synthetic_registry):
    registry, evidence = synthetic_registry
    summaries, status = subject._native_registry_summary(
        registry, campaign_signature=evidence["campaign_signature"],
        engine_sha256=evidence["engine_sha256"], lane_ids=set(registry["lanes"]),
        expected_registry_signature=evidence["registry_signature"],
    )
    assert len(summaries) == 18
    assert status["targetCellCount"] == 1620
    for summary in summaries.values():
        assert summary["fixedWindowStartDay"] == 180
        assert summary["fixedWindowEndDay"] == 221
        for state in summary["states"].values():
            assert state["targetCount"] == 30
            assert state["quantityMedian"] == 15.5
            assert state["shipmentCountMedian"] == 2


def test_real_v8_v2_registry_is_read_natively(real_registry: tuple[dict, dict]) -> None:
    registry, evidence = real_registry
    summaries, status = subject._native_registry_summary(  # noqa: SLF001
        registry,
        campaign_signature=evidence["campaign_signature"],
        engine_sha256=evidence["engine_sha256"],
        lane_ids=set(registry["lanes"]),
        expected_registry_signature=evidence["registry_signature"],
    )

    assert evidence["registry_schema_version"].endswith(".target_registry.v8")
    assert evidence["registry_signature"] == (
        "b915022909d125c86ed46a302f46e9acd98be7f3b788ccca417dda0fca2fd2e5"
    )
    assert evidence["target_cell_count"] == 1_620
    assert evidence["source_trace_replay_performed"] is False
    assert len(summaries) == 18
    assert status["requiredComparableSeedCount"] == 30
    assert status["incidentOutcomesUsed"] is False
    assert status["targetSelectionEngineRuns"] == 0
    focus = summaries["sdc_vd0914360c_338929_m_1810"]
    assert focus["comparisonValid"] is True
    assert focus["fixedWindowStartDay"] == 214
    assert focus["fixedWindowEndDay"] == 255
    assert all(
        row["quantityMeaning"] == "normally_deliverable_quantity"
        for row in focus["states"].values()
    )


def test_legacy_v4_registry_reader_reproduces_original_no_go(
    synthetic_registry: tuple[dict, dict],
) -> None:
    registry, evidence = synthetic_registry
    with pytest.raises(subject.dashboard_v7.DashboardInputError, match="registre V4"):
        subject.implementation_v4._target_registry_summary(  # noqa: SLF001
            registry,
            campaign_signature=evidence["campaign_signature"],
            engine_sha256=evidence["engine_sha256"],
            lane_ids=set(registry["lanes"]),
        )


def test_native_reader_rejects_design_seed_alias(
    synthetic_registry: tuple[dict, dict],
) -> None:
    registry, evidence = synthetic_registry
    tampered = dict(registry)
    tampered["design_seed"] = 123
    with pytest.raises(subject.V8DashboardInputError, match="graine de conception"):
        subject._native_registry_summary(  # noqa: SLF001
            tampered,
            campaign_signature=evidence["campaign_signature"],
            engine_sha256=evidence["engine_sha256"],
            lane_ids=set(registry["lanes"]),
            expected_registry_signature=evidence["registry_signature"],
        )


def test_native_reader_rejects_non_shared_lane_window(
    synthetic_registry: tuple[dict, dict],
) -> None:
    registry, evidence = synthetic_registry
    tampered = dict(registry)
    tampered["targets"] = list(registry["targets"])
    changed = copy.deepcopy(tampered["targets"][0])
    changed["target_window_start_day"] += 1
    tampered["targets"][0] = changed
    tampered["registry_signature"] = subject._canonical_signature(  # noqa: SLF001
        tampered, "registry_signature"
    )
    with pytest.raises(subject.V8DashboardInputError, match="Cellule V8"):
        subject._native_registry_summary(  # noqa: SLF001
            tampered,
            campaign_signature=evidence["campaign_signature"],
            engine_sha256=evidence["engine_sha256"],
            lane_ids=set(registry["lanes"]),
            expected_registry_signature=tampered["registry_signature"],
        )


def test_native_summary_patch_is_scoped_and_restored() -> None:
    original = subject.implementation_v4._target_registry_summary  # noqa: SLF001
    with subject._patched_native_registry_summary("a" * 64):  # noqa: SLF001
        assert subject.implementation_v4._target_registry_summary is not original  # noqa: SLF001
    assert subject.implementation_v4._target_registry_summary is original  # noqa: SLF001
