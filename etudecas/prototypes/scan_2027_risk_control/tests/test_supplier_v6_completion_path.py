from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v6 as bridge_v6,
)
from etudecas.prototypes.scan_2027_risk_control.supplier_campaign_adapters import finalize_v6 as finalizer_v6
from etudecas.prototypes.scan_2027_risk_control.supplier_campaign_adapters import launch_v6 as launcher_v6
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v6 as development_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_holdout_v6 as holdout_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v5 as sidecar_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v6 as sidecar_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v6 as campaign_v6,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_balanced_product_delay_multiseed_refinement_v4 as v4_fixture,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_balanced_product_delay_multiseed_refinement_v6 as v6_fixture,
)


def _successful_development(tmp_path: Path) -> tuple[Path, Path]:
    plan, run, *_unused = v6_fixture._v6_plan(tmp_path)  # noqa: SLF001

    def executor(**kwargs: Any) -> dict[str, Any]:
        return {"metrics": v4_fixture._metrics(0.80)}  # noqa: SLF001

    development_v6.run_development(
        plan, run, executor=executor, max_workers=2, test_only=True
    )
    result = development_v6.finalize_development(plan, run, test_only=True)
    assert result["status"] == development_v6.SUCCESS_STATUS
    return plan, run


def test_fresh_holdout_is_exact_locked_and_does_not_modify_development(
    tmp_path: Path,
) -> None:
    development_plan, development_run = _successful_development(tmp_path)
    source_before = {
        path.relative_to(development_run).as_posix(): holdout_v6.sha256_file(path)
        for path in development_run.rglob("*")
        if path.is_file()
    }
    plan_dir = tmp_path / "holdout_plan"
    holdout_v6.prepare_plan(
        plan_dir,
        development_plan_dir=development_plan,
        development_run_dir=development_run,
        allow_test_source=True,
    )
    plan = holdout_v6.validate_plan(
        plan_dir, verify_runtime_dependencies=False, allow_test_source=True
    )
    assert len(plan.candidates) == 3
    assert plan.manifest["expected_holdout_case_count"] == 90
    assert len(plan.manifest["holdout_cases"]) == 90
    assert {
        (row["target_group"], row["seed"])
        for row in plan.manifest["holdout_cases"]
    } == {
        (group, seed)
        for group in holdout_v6.TARGETS
        for seed in holdout_v6.EXPECTED_HOLDOUT_SEEDS
    }
    assert plan.manifest["holdout_contract"]["retuning_after_holdout"] is False
    development = development_v6.validate_plan(
        development_plan,
        verify_runtime_dependencies=False,
        allow_test_source=True,
    )
    assert plan.manifest["source_hashes"]["v5_driver_sha256"] == (
        development.manifest["source_hashes"]["v5_driver_sha256"]
    )
    assert plan.manifest["source_hashes"]["v6_holdout_driver_sha256"] == (
        holdout_v6.sha256_file(Path(holdout_v6.__file__).resolve())
    )

    run_dir = tmp_path / "holdout_run"
    registration = holdout_v6.prepare_holdout_run(
        plan_dir, run_dir, test_only=True
    )
    assert registration["new_engine_runs_by_registration"] == 0
    assert registration["completed_evidence_case_count"] == 0
    assert {path.name for path in run_dir.iterdir()} == {
        ".v6-holdout.lock",
        "run_manifest.json",
        "development_selection.json",
    }

    calls: list[tuple[str, int]] = []

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        service = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}[
            candidate.target_group
        ]
        calls.append((candidate.target_group, int(kwargs["seed"])))
        return {"metrics": v4_fixture._metrics(service)}  # noqa: SLF001

    progress = holdout_v6.run_holdout(
        plan_dir,
        run_dir,
        executor=executor,
        max_workers=2,
        test_only=True,
    )
    assert progress["completed_case_count"] == 90
    assert len(calls) == 90
    assert len(set(calls)) == 90
    assert not (run_dir / "shipment_traces").exists()
    result = holdout_v6.finalize_holdout(plan_dir, run_dir, test_only=True)
    assert result["accepted"] is True
    assert result["retuning_after_holdout"] is False
    assert result["selected_candidate_keys"] == (
        plan.manifest["development_authorization_source"]["selected_candidate_keys"]
    )
    source_after = {
        path.relative_to(development_run).as_posix(): holdout_v6.sha256_file(path)
        for path in development_run.rglob("*")
        if path.is_file()
    }
    assert source_after == source_before


def test_holdout_protocol_refuses_any_exposed_source_holdout(tmp_path: Path) -> None:
    leaked = tmp_path / "v6_run" / "evidence" / "holdout"
    leaked.mkdir(parents=True)
    with pytest.raises(holdout_v6.V6HoldoutError, match="exposed holdout"):
        holdout_v6._assert_source_holdout_unseen(tmp_path / "v6_run")  # noqa: SLF001


def test_v6_sidecar_and_bridge_bindings_restore_the_frozen_modules() -> None:
    original_refinement = sidecar_v5.refinement
    with sidecar_v6._v6_binding():  # noqa: SLF001
        assert sidecar_v5.refinement is holdout_v6
        assert sidecar_v5.CONTRACT_SCHEMA_VERSION == sidecar_v6.CONTRACT_SCHEMA_VERSION
    assert sidecar_v5.refinement is original_refinement

    original_bridge_refinement = bridge_v6.implementation_v5.refinement_v5
    with bridge_v6._v6_binding():  # noqa: SLF001
        assert bridge_v6.implementation_v5.refinement_v5 is holdout_v6
        assert (
            bridge_v6.implementation_v5.ACCEPTED_HOLDOUT_STATUS
            == holdout_v6.ACCEPTED_HOLDOUT_STATUS
        )
    assert bridge_v6.implementation_v5.refinement_v5 is original_bridge_refinement


def test_v6_sidecar_binding_restores_every_name_after_exception() -> None:
    names = (
        "refinement",
        "SCHEMA_VERSION",
        "CONTRACT_SCHEMA_VERSION",
        "READY_SCHEMA_VERSION",
        "INVENTORY_SCHEMA_VERSION",
        "build_contract",
        "validate_contract",
        "_write_v5_inventory",
    )
    previous = {name: getattr(sidecar_v5, name) for name in names}
    with pytest.raises(RuntimeError, match="injected"):
        with sidecar_v6._v6_binding():  # noqa: SLF001
            raise RuntimeError("injected")
    assert {name: getattr(sidecar_v5, name) for name in names} == previous


def test_v6_watcher_never_publishes_ready_when_initialization_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "sidecar"
    output.mkdir()
    contract = {"contract_signature": "test-contract"}
    monkeypatch.setattr(sidecar_v6, "load_official_cases", lambda *_a: ())
    monkeypatch.setattr(sidecar_v6, "build_contract", lambda **_k: contract)
    monkeypatch.setattr(sidecar_v6, "_watcher_lock", lambda *_a: nullcontext())
    monkeypatch.setattr(sidecar_v6, "validate_contract", lambda *_a: contract)
    monkeypatch.setattr(sidecar_v6.capture_v4, "register_contract", lambda *_a: None)
    monkeypatch.setattr(sidecar_v6.capture_v4, "_read_json", lambda *_a: contract)

    class BrokenWatcher:
        def __init__(self, **_kwargs: Any) -> None:
            raise RuntimeError("watcher initialization failed")

    monkeypatch.setattr(sidecar_v6.implementation_v5, "V5CurveCaptureWatcher", BrokenWatcher)
    with pytest.raises(RuntimeError, match="initialization failed"):
        sidecar_v6.run_watcher(
            plan_dir=tmp_path / "plan",
            run_dir=tmp_path / "run",
            output_dir=output,
            poll_seconds=0.1,
            stability_seconds=0.1,
            timeout_seconds=1.0,
        )
    assert not (output / "watcher_ready.json").exists()


def test_v6_watcher_lease_proves_live_owner_and_releases(tmp_path: Path) -> None:
    output = tmp_path / "sidecar"
    with sidecar_v6._watcher_lock(output):  # noqa: SLF001
        assert sidecar_v6.assert_watcher_lease_active(output).is_file()
    with pytest.raises(sidecar_v6.CurveSidecarError, match="No active"):
        sidecar_v6.assert_watcher_lease_active(output)


def test_official_holdout_refuses_missing_watcher_before_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = SimpleNamespace(
        plan_dir=tmp_path / "plan",
        manifest={
            "v6_development_source": {
                "plan_dir": str(tmp_path / "development-plan"),
                "run_dir": str(tmp_path / "development-run"),
            }
        },
        candidates=(),
    )
    called = False

    def executor(**_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(holdout_v6, "validate_plan", lambda *_a, **_k: plan)
    monkeypatch.setattr(holdout_v6, "_paths_overlap", lambda *_a: False)
    monkeypatch.setattr(
        holdout_v6,
        "_protected_holdout_sources",
        lambda *_a, **_k: (),
    )
    monkeypatch.setattr(holdout_v6, "_run_lock", lambda *_a: nullcontext())
    monkeypatch.setattr(holdout_v6, "_register_run", lambda *_a: None)
    monkeypatch.setattr(holdout_v6.v4, "ValidatedPlan", lambda *_a: object())
    monkeypatch.setattr(holdout_v6.v4, "_real_executor", executor)
    with pytest.raises(holdout_v6.V6HoldoutError, match="sidecar-dir"):
        holdout_v6.run_holdout(
            tmp_path / "plan",
            tmp_path / "run",
            test_only=False,
        )
    assert called is False


def test_v6_campaign_adapters_patch_and_restore_frozen_v4_implementations() -> None:
    campaign_previous = campaign_v6.implementation_v4.v4_bridge
    with campaign_v6.patched_v6_context():
        assert campaign_v6.implementation_v4.v4_bridge is bridge_v6
        assert Path(campaign_v6.implementation_v4.__file__).resolve() == (
            campaign_v6.ADAPTER_PATH
        )
    assert campaign_v6.implementation_v4.v4_bridge is campaign_previous

    launcher_previous = launcher_v6.implementation_v4.v4_bridge
    with launcher_v6.patched_v6_context():
        assert launcher_v6.implementation_v4.v4_bridge is bridge_v6
        assert launcher_v6.implementation_v4.RUNNER == launcher_v6.RUNNER
    assert launcher_v6.implementation_v4.v4_bridge is launcher_previous

    finalizer_previous = finalizer_v6.implementation_v4.v4_bridge
    with finalizer_v6.patched_v6_context():
        assert finalizer_v6.implementation_v4.v4_bridge is bridge_v6
    assert finalizer_v6.implementation_v4.v4_bridge is finalizer_previous
