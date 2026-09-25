from __future__ import annotations

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_stage_runtime as stage_runtime,
)

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as predecessor_common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)

legacy_pipeline = stage_runtime.for_profile("v7-stage2")
legacy_watcher = stage_runtime.for_profile("v7-stage2")
pipeline = stage_runtime.for_profile("v8-stage3")
watcher = pipeline


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


def test_historical_stage3_inventory_stays_frozen(historical_artifact):
    path = historical_artifact(
        "supplier_v8_stage2_supervision_20260906_v2/stage2_source_inventory.json"
    )
    inventory = predecessor_common.read_json(path)
    predecessor_common.verify_signature(
        inventory, "inventory_signature", "historical predecessor"
    )
    assert inventory["inventory_signature"] == common.PREDECESSOR_INVENTORY_SIGNATURE
    with pytest.raises(common.Stage2Error, match="Historical"):
        pipeline.verify_source_inventory(inventory)


def test_stage3_source_discovery_is_explicit():
    repo = Path(__file__).resolve().parents[4]
    names = {path.name for path in pipeline.source_paths(repo)}
    assert {
        "supplier_stage_runtime.py",
        "supplier_v8_stage3_common.py",
        "supplier_v8_stage3_delivery.py",
    } <= names
    assert not names.intersection(
        {
            f"supplier_{version}_{kind}.py"
            for version in ("v7_stage2", "v8_stage2", "v8_stage3")
            for kind in ("pipeline", "watcher")
        }
    )


def test_current_inventory_rejects_changed_source_cross_profile_and_old_schema(
    tmp_path, monkeypatch
):
    runtime = stage_runtime.for_profile("v8-stage3")
    source = tmp_path / "worker.py"
    source.write_bytes(b"value = 1\n")
    monkeypatch.setattr(runtime, "source_paths", lambda repo: [source])
    inventory = runtime.build_source_inventory(tmp_path)
    runtime.verify_source_inventory(inventory)
    source.write_bytes(b"value = 2\n")
    with pytest.raises(common.Stage2Error, match="changed"):
        runtime.verify_source_inventory(inventory)
    with pytest.raises(common.Stage2Error, match="other-profile"):
        stage_runtime.for_profile("v7-stage2").verify_source_inventory(inventory)
    old = dict(inventory)
    old.pop("inventory_signature")
    old["schema_version"] = common.SOURCE_INVENTORY_SCHEMA_VERSION
    with pytest.raises(common.Stage2Error, match="Historical"):
        runtime.verify_source_inventory(common.signed(old, "inventory_signature"))


def test_inventory_cli_is_new_or_identical_and_never_overwrites_another_identity(
    tmp_path, monkeypatch
):
    import json

    runtime = stage_runtime.for_profile("v8-stage3")
    source = tmp_path / "worker.py"
    source.write_bytes(b"value = 1\n")
    monkeypatch.setattr(runtime, "source_paths", lambda repo: [source])
    monkeypatch.setattr(stage_runtime, "for_profile", lambda profile: runtime)
    target = tmp_path / "inventory.json"
    args = [
        "--profile",
        "v8-stage3",
        "--mode",
        "inventory",
        "--repo",
        str(tmp_path),
        "--output",
        str(target),
    ]
    assert stage_runtime.main(args) == 0
    first = target.read_bytes()
    assert stage_runtime.main(args) == 0
    assert target.read_bytes() == first
    assert json.loads(first)["profile"] == "v8-stage3"
    source.write_bytes(b"value = 2\n")
    assert stage_runtime.main(args) == 1
    assert target.read_bytes() == first


@pytest.mark.parametrize(
    "fault", [None, "checksum", "source", "traversal", "signature"]
)
def test_archive_verification_is_read_only_and_never_authorizes_resume(tmp_path, fault):
    import hashlib
    import json
    import zipfile

    content = b"raise RuntimeError('archive must never execute')\n"
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("worker.py", content)
    inventory = common.signed(
        {
            "schema_version": "etudecas.supplier_v7_stage2.v1.source_inventory.v1",
            "entry_count": 1,
            "entries": [
                {
                    "relative_path": "../worker.py"
                    if fault == "traversal"
                    else "worker.py",
                    "size_bytes": len(content),
                    "sha256": "0" * 64
                    if fault == "source"
                    else hashlib.sha256(content).hexdigest(),
                }
            ],
        },
        "inventory_signature",
    )
    if fault == "signature":
        inventory["inventory_signature"] = "0" * 64
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    digest = (
        "0" * 64
        if fault == "checksum"
        else hashlib.sha256(archive_path.read_bytes()).hexdigest()
    )
    if fault:
        with pytest.raises((ValueError, common.Stage2Error)):
            stage_runtime.verify_archived_inventory(
                inventory_path, archive_path, digest
            )
    else:
        result = stage_runtime.verify_archived_inventory(
            inventory_path, archive_path, digest
        )
        assert result["ok"] is True
        assert result["current_runtime_verified"] is False
        assert result["resume_authorized"] is False
    assert {path.name for path in tmp_path.iterdir()} == {
        "source.zip",
        "inventory.json",
    }


def test_stage3_rejects_a_different_archived_predecessor_even_when_self_consistent(
    tmp_path,
):
    import hashlib
    import json
    import zipfile

    capsule = tmp_path / "sources.zip"
    content = b"SOURCE = 1\n"
    with zipfile.ZipFile(capsule, "w") as archive:
        archive.writestr("example.py", content)
    inventory = common.signed(
        {
            "schema_version": common.SOURCE_INVENTORY_SCHEMA_VERSION,
            "entry_count": 1,
            "entries": [
                {
                    "relative_path": "example.py",
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            ],
            "predecessor_inventory_signature": "0" * 64,
            "explicit_stage3_source_filenames": list(
                common.HISTORICAL_EXPLICIT_SOURCE_FILENAMES
            ),
        },
        "inventory_signature",
    )
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    with pytest.raises(ValueError, match="predecessor identity"):
        stage_runtime.verify_archived_inventory(
            inventory_path, capsule, hashlib.sha256(capsule.read_bytes()).hexdigest()
        )


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


def test_pipeline_contract_adds_native_registry_and_window_semantics(tmp_path):
    contract = pipeline._contract_payload(
        _paths(tmp_path), {"inventory_signature": "a" * 64}
    )
    science = contract["scientific_contract"]
    assert science["native_v8_target_registry_reader_required"] is True
    assert science["obsolete_design_seed_projection_used"] is False
    assert science["target_window_is_worst_period"] is False
    assert science["target_window_is_average_season"] is False
    assert science["target_selection_uses_incident_outcomes"] is False
    assert contract["orchestration"]["profile"] == "v8-stage3"


def test_pipeline_profile_is_v3_scoped_without_mutating_v7(tmp_path):
    previous = (
        legacy_pipeline.common,
        legacy_pipeline.SCHEMA_VERSION,
        legacy_pipeline._delivery,
        legacy_pipeline._contract_payload,
    )
    pipeline._contract_payload(_paths(tmp_path), {"inventory_signature": "a" * 64})
    assert pipeline.common is common
    assert pipeline.profile == "v8-stage3"
    assert (
        legacy_pipeline.common,
        legacy_pipeline.SCHEMA_VERSION,
        legacy_pipeline._delivery,
        legacy_pipeline._contract_payload,
    ) == previous


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
    tmp_path, monkeypatch
):
    paths = SimpleNamespace(results_dir=tmp_path / "results")
    paths.results_dir.mkdir()

    class Parser:
        @staticmethod
        def parse_args(_argv):
            return object()

    monkeypatch.setattr(watcher, "_watch_parser", lambda: Parser())
    monkeypatch.setattr(watcher, "paths_from_args", lambda _args: paths)
    monkeypatch.setattr(
        watcher,
        "prepare_supervision",
        lambda _paths: pytest.fail("No supervision before final overlay"),
    )
    monkeypatch.setattr(
        common,
        "probe_stage1",
        lambda _paths: pytest.fail("No progress JSON before final overlay"),
    )
    assert watcher.watch([]) == 4


def test_watcher_profile_targets_v3_without_mutating_v7():
    previous = (
        legacy_watcher.common,
        legacy_watcher.profile,
        legacy_watcher.DEFAULT_POLL_SECONDS,
    )
    assert watcher is pipeline
    assert watcher.common is common
    assert watcher.profile == "v8-stage3"
    assert watcher.DEFAULT_POLL_SECONDS == 60.0
    assert watcher.RESERVATION_SCHEMA_VERSION.startswith(watcher.WATCHER_SCHEMA_VERSION)
    assert (
        legacy_watcher.common,
        legacy_watcher.profile,
        legacy_watcher.DEFAULT_POLL_SECONDS,
    ) == previous
