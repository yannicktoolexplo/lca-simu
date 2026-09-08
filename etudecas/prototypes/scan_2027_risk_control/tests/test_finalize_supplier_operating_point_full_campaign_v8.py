from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as subject,
)


def _signed(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return {
        **payload,
        key: subject.implementation_v4._stable_sha256(payload),  # noqa: SLF001
    }


def test_finalizer_constants_are_bound_to_native_v8_runner() -> None:
    assert subject.TARGET_SELECTION_REVISION == subject.campaign_v8.TARGET_SELECTION_REVISION
    assert (
        subject.TARGET_REGISTRY_SCHEMA_VERSION
        == subject.campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION
    )
    assert (
        subject.TARGET_PROGRESS_SCHEMA_VERSION
        == subject.campaign_v8.TARGET_DISCOVERY_PROGRESS_SCHEMA_VERSION
    )
    assert subject.REQUIRED_COMPARABLE_SEED_COUNT == 30
    assert subject.MIN_FIXED_WINDOW_START_DAY == 180
    assert subject.MAX_FIXED_WINDOW_START_DAY == 678


def test_selection_proofs_reject_design_seed_aliases() -> None:
    with pytest.raises(subject.V8FinalizerAdapterError, match="design-seed"):
        subject._assert_no_design_seed_aliases(  # noqa: SLF001
            {"nested": {"design_seed": 900659036}},
            label="test",
        )


def _progress_manifest() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = {
        "campaign_signature": "a" * 64,
        "target_discovery_status": "complete",
        "target_exposure_comparability_status": "accepted_30_of_30",
    }
    progress = {
        "schema_version": subject.TARGET_PROGRESS_SCHEMA_VERSION,
        "target_selection_revision": subject.TARGET_SELECTION_REVISION,
        "campaign_signature": manifest["campaign_signature"],
        "status": "complete",
        "engine_runs_planned": 0,
        "engine_runs_completed": 0,
        "engine_runs_failed": 0,
        "target_selection_engine_runs": 0,
        "signed_v7_service_proofs_imported": 90,
        "signed_v7_shipment_traces_imported": 90,
        "state_validation_engine_runs": 0,
        "state_validation_binding_status": subject.implementation_v4.PREFLIGHT_ACCEPTED_STATUS,
        "required_comparable_seed_count": 30,
        "incident_outcomes_used": False,
        "incident_probes_started": False,
    }
    return manifest, progress


def test_progress_requires_zero_runs_and_30_of_30() -> None:
    manifest, progress = _progress_manifest()
    assert subject._validate_v8_progress(progress, manifest=manifest) == progress  # noqa: SLF001

    progress["engine_runs_completed"] = 3
    with pytest.raises(subject.V8FinalizerAdapterError, match="zero-run"):
        subject._validate_v8_progress(progress, manifest=manifest)  # noqa: SLF001

    progress["engine_runs_completed"] = 0
    progress["required_comparable_seed_count"] = 24
    with pytest.raises(subject.V8FinalizerAdapterError, match="zero-run"):
        subject._validate_v8_progress(progress, manifest=manifest)  # noqa: SLF001


def test_registry_validation_replays_the_90_signed_traces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane_path = tmp_path / "lanes.csv"
    lane_path.write_text("signed lane fixture\n", encoding="utf-8")
    lanes = [
        SimpleNamespace(
            lane_id=f"lane_{index:02d}",
            supplier_id=f"supplier_{index:02d}",
            item_id=f"item_{index:02d}",
            dst_node_id=f"node_{index:02d}",
            edge_id=f"edge_{index:02d}",
            target_product_id="268091" if index % 2 else "268967",
        )
        for index in range(18)
    ]
    lane_identity = {
        lane.lane_id: (
            lane.supplier_id,
            lane.item_id,
            lane.dst_node_id,
            lane.edge_id,
            lane.target_product_id,
        )
        for lane in lanes
    }
    registry = _signed(
        {
            "target_selection_revision": subject.TARGET_SELECTION_REVISION,
            "target_cell_count": 1_620,
            "required_comparable_seed_count": 30,
            "target_selection_engine_runs": 0,
            "incident_outcomes_used": False,
        },
        "registry_signature",
    )
    manifest = {
        "target_registry_signature": registry["registry_signature"],
        "lane_reference_source": str(lane_path),
        "lane_reference_source_sha256": subject.implementation_v4._sha256(  # noqa: SLF001
            lane_path
        ),
        "operating_points_source": str(tmp_path / "bridge.json"),
        "states": [{"operating_point_id": point} for point in subject.implementation_v4.OPERATING_POINTS],
    }
    observed: dict[str, Any] = {}
    runner = subject.campaign_v8.implementation_v4
    monkeypatch.setattr(subject.campaign_v8, "patched_v8_context", nullcontext)
    monkeypatch.setattr(runner, "load_lanes", lambda _path: lanes)
    monkeypatch.setattr(
        runner.v4_bridge,
        "validate_bridge",
        lambda *_args, **_kwargs: {"bridge": "validated"},
    )
    monkeypatch.setattr(
        runner,
        "_import_v4_holdout_shipment_rows",
        lambda **_kwargs: {"90": "signed traces"},
    )

    def validate(
        payload: dict[str, Any],
        *,
        manifest: dict[str, Any],
        lanes: list[Any],
        shipment_rows_by_state_seed: dict[str, Any],
    ) -> dict[str, Any]:
        observed.update(
            payload=payload,
            manifest=manifest,
            lanes=lanes,
            traces=shipment_rows_by_state_seed,
        )
        return payload

    monkeypatch.setattr(subject.campaign_v8, "validate_v8_target_registry_payload", validate)
    assert subject._validate_v8_registry(  # noqa: SLF001
        registry,
        manifest=manifest,
        lane_identity=lane_identity,
    ) == registry
    assert observed["traces"] == {"90": "signed traces"}
    assert observed["lanes"] == lanes


def test_patched_context_replaces_and_restores_only_finalizer_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(subject, "validate_frozen_implementation", lambda: Path())
    implementation = subject.implementation_v4
    before = (
        implementation.v4_bridge,
        implementation.SOURCE_RUNNER_SHA256,
        implementation.EXPECTED_SEEDS,
        implementation._validate_operating_point_provenance,  # noqa: SLF001
        implementation._validate_signed_context,  # noqa: SLF001
        implementation._business_limits,  # noqa: SLF001
    )
    with subject.patched_v8_context():
        assert implementation.v4_bridge is subject.v7_bridge
        assert implementation.EXPECTED_SEEDS == subject.trace_package.CAMPAIGN_SEEDS
        assert implementation._validate_signed_context is subject._validate_v8_signed_context  # noqa: SLF001
        assert implementation._business_limits is subject._v8_business_limits  # noqa: SLF001
    after = (
        implementation.v4_bridge,
        implementation.SOURCE_RUNNER_SHA256,
        implementation.EXPECTED_SEEDS,
        implementation._validate_operating_point_provenance,  # noqa: SLF001
        implementation._validate_signed_context,  # noqa: SLF001
        implementation._business_limits,  # noqa: SLF001
    )
    assert after == before


def test_business_limit_states_outcome_blind_exposure_stratification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subject,
        "_ORIGINAL_BUSINESS_LIMITS",
        lambda _days: [
            {"topic": "fenetre_fournisseur", "limit": "obsolete"},
            {"topic": "signal_fournisseur", "limit": "obsolete"},
        ],
    )
    limits = subject._v8_business_limits(42)  # noqa: SLF001
    by_topic = {row["topic"]: row["limit"] for row in limits}
    assert "première fenêtre à partir de J180" in by_topic["fenetre_fournisseur"]
    assert "sans résultat d'incident" in by_topic["fenetre_fournisseur"]
    assert "30 répétitions" in by_topic["fenetre_fournisseur"]
    assert "performance observée" in by_topic["signal_fournisseur"]
