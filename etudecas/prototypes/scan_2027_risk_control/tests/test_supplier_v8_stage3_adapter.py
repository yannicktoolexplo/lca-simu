from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_pipeline as legacy_pipeline,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_watcher as legacy_watcher,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as predecessor_common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_pipeline as pipeline,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_watcher as watcher,
)


def _paths(tmp_path: Path) -> common.Stage2Paths:
    root = tmp_path / "repo"
    root.mkdir()
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    return common.Stage2Paths(
        repo=root,
        v7_plan_dir=upstream / "v7_plan",
        v7_run_dir=upstream / "v7_run",
        trace_package_dir=upstream / "traces",
        bridge_json=upstream / "bridge.json",
        campaign_root=upstream / "campaign_v8",
        results_dir=upstream / "results_v8",
        stage1_supervision_dir=upstream / "campaign_v8",
        observed_2025_dir=None,
        lot_replay_root=tmp_path / "out" / "lots_v3",
        qualification_dir=tmp_path / "out" / "qualification_v3",
        action_replay_root=tmp_path / "out" / "actions_v3",
        curves_dir=tmp_path / "out" / "curves_v3",
        registry_dir=tmp_path / "out" / "registry_v3",
        final_html=tmp_path / "out" / "DEMONSTRATION_V3.html",
        supervision_dir=tmp_path / "out" / "supervision_v3",
    ).resolved()


def _native_evidence() -> dict[str, Any]:
    return {
        "registry_schema_version": (
            "etudecas.supplier_operating_point_full_campaign.v4.target_registry.v8"
        ),
        "registry_signature": "b" * 64,
        "registry_sha256": "c" * 64,
        "target_cell_count": 1_620,
        "lane_count": 18,
        "seed_count": 30,
        "required_comparable_seed_count": 30,
        "incident_outcomes_used": False,
        "target_selection_engine_runs": 0,
    }


def test_stage3_inventory_is_explicit_and_v2_signature_stays_frozen() -> None:
    repo = Path(__file__).resolve().parents[4]
    v2 = predecessor_common.build_source_inventory(repo)
    predecessor_common.verify_source_inventory(v2)
    v3 = common.build_source_inventory(repo)
    common.verify_source_inventory(v3)

    assert v2["inventory_signature"] == common.PREDECESSOR_INVENTORY_SIGNATURE
    assert v3["predecessor_inventory_signature"] == v2["inventory_signature"]
    explicit = {
        row["relative_path"].rsplit("/", 1)[-1]
        for row in v3["entries"]
        if "supplier_v8_stage3_" in row["relative_path"]
    }
    assert explicit == set(common.EXPLICIT_SOURCE_FILENAMES)


def test_native_dashboard_binding_is_scoped_and_receipt_is_v3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    original = predecessor_common.dashboard_v7

    class FakeReader:
        def __init__(self, campaign_root: Path) -> None:
            assert campaign_root == paths.campaign_root
            self.last_evidence: dict[str, Any] | None = None

        def load_dashboard_data(self, **_kwargs: Any) -> dict[str, Any]:
            self.last_evidence = _native_evidence()
            return {"repetitions": 30, "laneCount": 18}

    def fake_predecessor_validate(_paths: common.Stage2Paths) -> dict[str, Any]:
        predecessor_common.dashboard_v7.load_dashboard_data(
            results_dir=paths.results_dir
        )
        return predecessor_common.signed(
            {
                "schema_version": predecessor_common.UPSTREAM_SCHEMA_VERSION,
                "status": "complete_validated_v8",
                "campaign_signature": "a" * 64,
            },
            "validation_signature",
        )

    monkeypatch.setattr(common.dashboard_v8, "NativeV8DashboardReader", FakeReader)
    monkeypatch.setattr(
        predecessor_common, "validate_complete_stage1", fake_predecessor_validate
    )
    receipt = common.validate_complete_stage1(paths)

    assert predecessor_common.dashboard_v7 is original
    assert receipt["schema_version"] == common.UPSTREAM_SCHEMA_VERSION
    assert receipt["status"] == "complete_validated_v8_native_registry"
    native = receipt["native_dashboard_contract"]
    assert native["target_cell_count"] == 1_620
    assert native["obsolete_design_seed_projection_used"] is False
    common.verify_signature(receipt, "validation_signature", "reçu test V3")


def test_pipeline_contract_adds_native_registry_and_window_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        pipeline,
        "_ORIGINAL_CONTRACT_PAYLOAD",
        lambda _paths, _inventory: common.signed(
            {
                "schema_version": "legacy",
                "scientific_contract": {},
            },
            "contract_signature",
        ),
    )
    contract = pipeline._contract_payload_v3(paths, {})  # noqa: SLF001
    science = contract["scientific_contract"]
    assert science["native_v8_target_registry_reader_required"] is True
    assert science["obsolete_design_seed_projection_used"] is False
    assert science["target_window_is_worst_period"] is False
    assert science["target_window_is_average_season"] is False
    assert science["target_selection_uses_incident_outcomes"] is False


def test_pipeline_context_is_v3_scoped_and_restored() -> None:
    previous = (
        legacy_pipeline.common,
        legacy_pipeline.SCHEMA_VERSION,
        legacy_pipeline._delivery,  # noqa: SLF001
        legacy_pipeline._contract_payload,  # noqa: SLF001
    )
    with pipeline.patched_v3_pipeline_context():
        assert legacy_pipeline.common is common
        assert legacy_pipeline.SCHEMA_VERSION == pipeline.SCHEMA_VERSION
        assert legacy_pipeline._delivery is pipeline._delivery_v3  # noqa: SLF001
        assert legacy_pipeline._contract_payload is pipeline._contract_payload_v3  # noqa: SLF001
    assert legacy_pipeline.common is previous[0]
    assert legacy_pipeline.SCHEMA_VERSION == previous[1]
    assert legacy_pipeline._delivery is previous[2]  # noqa: SLF001
    assert legacy_pipeline._contract_payload is previous[3]  # noqa: SLF001


def test_consumer_binding_delegates_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    @contextmanager
    def binding():
        events.append("enter")
        yield
        events.append("exit")

    monkeypatch.setattr(predecessor_common, "v8_consumer_bindings", binding)
    with common.v8_consumer_bindings():
        events.append("inside")
    assert events == ["enter", "inside", "exit"]


def test_shared_reader_binding_restores_predecessor_reader() -> None:
    original = predecessor_common.read_json
    with common._shared_json_binding():  # noqa: SLF001
        assert predecessor_common.read_json is common.read_json
    assert predecessor_common.read_json is original


def test_watcher_does_not_read_campaign_progress_before_final_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = SimpleNamespace(results_dir=tmp_path / "results")
    paths.results_dir.mkdir()

    class Parser:
        @staticmethod
        def parse_args(_argv: object) -> object:
            return object()

    monkeypatch.setattr(legacy_watcher, "_parser", lambda: Parser())
    monkeypatch.setattr(pipeline, "paths_from_args", lambda _args: paths)
    monkeypatch.setattr(
        legacy_watcher,
        "main",
        lambda _argv: pytest.fail("Le watcher mature ne doit pas démarrer."),
    )
    monkeypatch.setattr(
        common,
        "probe_stage1",
        lambda _paths: pytest.fail("Aucun progress JSON ne doit être sondé."),
    )

    assert watcher.main([]) == 4


def test_watcher_context_targets_v3_child_and_restores() -> None:
    previous = (
        legacy_watcher.common,
        legacy_watcher.pipeline,
        legacy_watcher.MODULE_NAME,
    )
    with watcher.patched_v3_watcher_context():
        assert legacy_watcher.common is common
        assert legacy_watcher.pipeline is pipeline
        assert legacy_watcher.MODULE_NAME == watcher.MODULE_NAME
        assert legacy_watcher.DEFAULT_POLL_SECONDS == 60.0
        assert legacy_watcher.RESERVATION_SCHEMA_VERSION.startswith(
            watcher.SCHEMA_VERSION
        )
    assert legacy_watcher.common is previous[0]
    assert legacy_watcher.pipeline is previous[1]
    assert legacy_watcher.MODULE_NAME == previous[2]
