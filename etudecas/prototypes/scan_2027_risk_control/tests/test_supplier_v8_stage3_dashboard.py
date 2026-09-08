from __future__ import annotations

import copy
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_dashboard as subject,
)


REAL_V8_V2_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
    r"\supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
)
REAL_V8_V2_REGISTRY = REAL_V8_V2_ROOT / "target_discovery" / "target_registry.json"


@pytest.fixture(scope="module")
def real_registry() -> tuple[dict, dict]:
    if not REAL_V8_V2_REGISTRY.is_file():
        pytest.skip("Le registre V8 V2 réel n'est pas monté dans cet environnement.")
    evidence = subject.validate_registry_file(REAL_V8_V2_ROOT, REAL_V8_V2_REGISTRY)
    registry = subject._read_json(REAL_V8_V2_REGISTRY)  # noqa: SLF001
    return registry, evidence


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
    real_registry: tuple[dict, dict],
) -> None:
    registry, evidence = real_registry
    with pytest.raises(subject.dashboard_v7.DashboardInputError, match="registre V4"):
        subject.implementation_v4._target_registry_summary(  # noqa: SLF001
            registry,
            campaign_signature=evidence["campaign_signature"],
            engine_sha256=evidence["engine_sha256"],
            lane_ids=set(registry["lanes"]),
        )


def test_native_reader_rejects_design_seed_alias(
    real_registry: tuple[dict, dict],
) -> None:
    registry, evidence = real_registry
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
    real_registry: tuple[dict, dict],
) -> None:
    registry, evidence = real_registry
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
