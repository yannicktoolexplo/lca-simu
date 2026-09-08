from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v6 as bridge_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v5 as relay_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v6 as relay_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_v6_calibration as calibration_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v6 as finalizer_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v6 as launcher_v6,
)
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
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_final_standalone_delivery as delivery_v6,
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


def test_v6_relay_is_downstream_only_and_restores_bindings() -> None:
    original = relay_v5.refinement_v5
    with relay_v6._v6_downstream_binding():  # noqa: SLF001
        assert relay_v5.refinement_v5 is holdout_v6
        assert relay_v5.BRIDGE_MODULE == relay_v6.BRIDGE_MODULE
        assert relay_v5.SIDECAR_MODULE == relay_v6.SIDECAR_MODULE
        assert relay_v5.CAMPAIGN_MODULE == relay_v6.CAMPAIGN_MODULE
    assert relay_v5.refinement_v5 is original
    instance = object.__new__(relay_v6.FullCampaignRelayV6)
    with pytest.raises(relay_v6.FullCampaignRelayError, match="aval uniquement"):
        instance.run_holdout(0)
    with pytest.raises(relay_v6.FullCampaignRelayError, match="aval uniquement"):
        instance.run_development()


def test_v6_relay_execute_is_downstream_only_and_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = object.__new__(relay_v6.FullCampaignRelayV6)
    instance.status = {
        "nominal_curves": {"status": "complete_validated"},
        "action_replay": {"status": "complete_validated"},
    }
    events: list[str] = []

    def step(name: str, result: Any = None) -> Any:
        def call(_self: Any, *_args: Any, **_kwargs: Any) -> Any:
            events.append(name)
            return result

        return call

    ordered = (
        ("prepare", None),
        ("validate_downstream_corridor_preflight", {}),
        ("build_and_validate_bridge", None),
        ("plan_campaign", None),
        ("launch_campaign", None),
        ("finalize_campaign", None),
        ("_lot_selection", ["lot"]),
        ("run_lot_replays", None),
        ("qualify_physical_cascades", None),
        ("process_optional_action_replay", None),
        ("validate_required_action_outcome", "complete_validated"),
        ("process_optional_curves", None),
        ("validate_required_curves_outcome", None),
        ("build_dashboard", None),
        ("build_final_delivery", None),
        ("update_status", None),
    )
    for name, result in ordered:
        monkeypatch.setattr(instance, name, MethodType(step(name, result), instance))
    for forbidden in (
        "prepare_v5_plan",
        "run_development",
        "finalize_development",
        "ensure_sidecar_watcher",
        "run_holdout",
        "finalize_holdout",
    ):
        monkeypatch.setattr(
            instance,
            forbidden,
            MethodType(
                lambda _self, *_a, _name=forbidden, **_k: pytest.fail(
                    f"calibration method called: {_name}"
                ),
                instance,
            ),
        )
    assert instance.execute() == 0
    assert events == [name for name, _result in ordered]


def test_v6_relay_rejects_nonempty_forbidden_source_sidecar(tmp_path: Path) -> None:
    source_plan = tmp_path / "development_plan"
    source_run = tmp_path / "development_run"
    source_plan.mkdir()
    source_run.mkdir()
    (source_plan / "refinement_plan.json").write_text("{}", encoding="utf-8")
    for name in (
        "run_manifest.json",
        "development_progress.json",
        "development_selection.json",
    ):
        (source_run / name).write_text("{}", encoding="utf-8")
    forbidden = tmp_path / "forbidden_sidecar"
    forbidden.mkdir()
    (forbidden / "leak.json").write_text("{}", encoding="utf-8")
    instance = object.__new__(relay_v6.FullCampaignRelayV6)
    instance.config = SimpleNamespace(
        v4_plan_dir=source_plan,
        v4_run_dir=source_run,
        v4_sidecar_root=forbidden,
    )
    with pytest.raises(relay_v6.FullCampaignRelayError, match="absent ou vide"):
        instance._v4_source_inventory()  # noqa: SLF001


def test_v6_detach_preflights_before_output_and_targets_v6_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    supervision = tmp_path / "supervision"

    class Config:
        repo = tmp_path
        supervision_dir = supervision

        def validate(self) -> None:
            assert not supervision.exists()
            events.append("config")

    class Relay:
        status_path = supervision / "status.json"

        def validate_calibration_handoff(self) -> None:
            assert not supervision.exists()
            events.append("handoff")

        def prepare(self) -> None:
            assert events == ["config", "handoff"]
            supervision.mkdir()
            events.append("prepare")

    config = Config()
    monkeypatch.setattr(relay_v6.implementation_v5, "_config_from_args", lambda _a: config)
    monkeypatch.setattr(relay_v6, "FullCampaignRelayV6", lambda _c: Relay())

    def child(_args: object) -> list[str]:
        assert events == ["config", "handoff", "prepare"]
        return ["python", "-m", relay_v6.MODULE_NAME, "--detached-child"]

    monkeypatch.setattr(relay_v6, "_child_command", child)
    monkeypatch.setattr(
        relay_v6.subprocess,
        "Popen",
        lambda command, **_kwargs: (
            pytest.fail("reservation missing before Popen")
            if not (supervision / "detached.json").is_file()
            else SimpleNamespace(pid=4242, command=command)
        ),
    )
    receipt = relay_v6.detach(object())
    assert receipt["pid"] == 4242
    assert receipt["command"][2] == relay_v6.MODULE_NAME
    assert receipt["preflight_completed_before_process_start"] is True
    assert events == ["config", "handoff", "prepare"]


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


def test_v6_delivery_identity_and_binding_restore() -> None:
    original_schema = delivery_v6.implementation_v5.SCHEMA_VERSION
    original_file = delivery_v6.implementation_v5.__file__
    with delivery_v6._v6_binding():  # noqa: SLF001
        assert delivery_v6.implementation_v5.SCHEMA_VERSION == delivery_v6.SCHEMA_VERSION
        assert Path(delivery_v6.implementation_v5.__file__).resolve() == Path(
            delivery_v6.__file__
        ).resolve()
    assert delivery_v6.implementation_v5.SCHEMA_VERSION == original_schema
    assert delivery_v6.implementation_v5.__file__ == original_file
    html = delivery_v6.render_html({"test": True})
    visible = html.split('<script id="delivery-data"', 1)[0]
    assert "RESILIENCE-SCAN V6" in visible
    assert "RÉSULTATS V6" in visible
    assert "RESILIENCE-SCAN V5" not in visible


def test_calibration_orchestrator_stops_before_holdout_on_development_no_go(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(
        max_wait_hours=1.0,
        holdout_plan_dir=tmp_path / "holdout-plan",
        holdout_run_dir=tmp_path / "holdout-run",
        sidecar_dir=tmp_path / "sidecar",
    )
    instance.monotonic = lambda: 1.0
    instance.status = {}
    events: list[str] = []
    monkeypatch.setattr(instance, "prepare", lambda: events.append("prepare"))
    monkeypatch.setattr(
        instance, "log", lambda _message: events.append("log")
    )
    monkeypatch.setattr(
        instance,
        "_ensure_development_plan",
        lambda: events.append("development_plan"),
    )
    monkeypatch.setattr(
        instance,
        "_finalize_development",
        lambda: {
            "status": development_v6.FAIL_STATUS,
            "holdout_cases_read": 0,
        },
    )
    monkeypatch.setattr(
        instance,
        "_ensure_holdout_plan_and_registration",
        lambda: pytest.fail("holdout planned after development no-go"),
    )
    monkeypatch.setattr(
        instance,
        "update_status",
        lambda stage, _message, **_values: events.append(stage),
    )
    assert instance.execute() == 3
    assert events[-1] == "scientific_no_go_after_development"


def test_calibration_reuses_terminal_development_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(development_run_dir=tmp_path / "run")
    expected = {"status": development_v6.SUCCESS_STATUS}
    events: list[str] = []
    monkeypatch.setattr(
        instance,
        "_development_commands",
        lambda: {"run": ["forbidden-run"], "finalize": ["forbidden-finalize"]},
    )
    monkeypatch.setattr(
        instance,
        "_wait_for_external_development",
        lambda: events.append("wait"),
    )
    monkeypatch.setattr(
        instance, "_existing_development_selection", lambda: expected
    )
    monkeypatch.setattr(
        instance,
        "_complete_development_state",
        lambda: pytest.fail("terminal state was needlessly reopened"),
    )
    monkeypatch.setattr(
        instance,
        "run_step",
        lambda *_a, **_k: pytest.fail("terminal development was rewritten"),
    )
    monkeypatch.setattr(
        instance,
        "update_status",
        lambda stage, _message: events.append(stage),
    )
    assert instance._finalize_development() is expected  # noqa: SLF001
    assert events == ["wait", "reuse_terminal_development_selection"]


def test_calibration_waits_for_external_development_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = run_dir / ".v6.lock"
    lock.write_text("32432", encoding="ascii")
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(
        development_run_dir=run_dir,
        poll_seconds=0.1,
    )
    instance.deadline = 10.0
    instance.monotonic = lambda: 0.0
    instance.status = {}
    events: list[str] = []
    monkeypatch.setattr(calibration_v6, "_process_running", lambda pid: pid == 32432)
    monkeypatch.setattr(
        instance,
        "update_status",
        lambda stage, _message, **_values: events.append(stage),
    )
    instance.sleep = lambda _seconds: lock.unlink()
    instance._wait_for_external_development()  # noqa: SLF001
    assert events == ["waiting_for_existing_development"]
    assert not lock.exists()


def test_calibration_never_unlinks_stale_development_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    lock = run_dir / ".v6.lock"
    lock.write_text("987654", encoding="ascii")
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(
        development_run_dir=run_dir,
        poll_seconds=0.1,
    )
    instance.deadline = 10.0
    instance.monotonic = lambda: 0.0
    instance.status = {}
    monkeypatch.setattr(calibration_v6, "_process_running", lambda _pid: False)
    monkeypatch.setattr(instance, "update_status", lambda *_a, **_k: None)
    with pytest.raises(calibration_v6.V6CalibrationOrchestratorError, match="Stale"):
        instance._wait_for_external_development()  # noqa: SLF001
    assert lock.read_text(encoding="ascii") == "987654"


def test_calibration_refuses_duplicate_live_sidecar_watcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    (sidecar / "watcher_ready.json").write_text("{}", encoding="utf-8")
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(
        sidecar_dir=sidecar,
        holdout_run_dir=tmp_path / "holdout-run",
    )
    monkeypatch.setattr(
        sidecar_v6,
        "assert_watcher_lease_active",
        lambda _path: sidecar / ".lease",
    )
    monkeypatch.setattr(
        sidecar_v6,
        "validate_ready",
        lambda *_a, **_k: {"watcher_pid": 4242},
    )
    monkeypatch.setattr(
        holdout_v6,
        "_validate_sidecar_authorization",
        lambda *_a, **_k: {},
    )
    monkeypatch.setattr(
        instance,
        "_spawn",
        lambda *_a, **_k: pytest.fail("duplicate watcher process spawned"),
    )
    with pytest.raises(
        calibration_v6.V6CalibrationOrchestratorError, match="duplicate"
    ):
        instance._start_watcher(object())  # noqa: SLF001


def test_calibration_success_orders_selection_freeze_ready_then_holdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(
        max_wait_hours=1.0,
        holdout_plan_dir=tmp_path / "holdout-plan",
        holdout_run_dir=tmp_path / "holdout-run",
        sidecar_dir=tmp_path / "sidecar",
    )
    instance.monotonic = lambda: 1.0
    instance.status = {}
    instance.watcher = None
    events: list[str] = []
    watcher = SimpleNamespace(pid=4242)
    plan = object()
    monkeypatch.setattr(instance, "prepare", lambda: events.append("prepare"))
    monkeypatch.setattr(instance, "log", lambda _message: events.append("log"))
    monkeypatch.setattr(
        instance,
        "_ensure_development_plan",
        lambda: events.append("development_plan"),
    )
    monkeypatch.setattr(
        instance,
        "_finalize_development",
        lambda: (
            events.append("selection_signed")
            or {"status": development_v6.SUCCESS_STATUS}
        ),
    )
    monkeypatch.setattr(
        instance,
        "_ensure_holdout_plan_and_registration",
        lambda: events.append("freeze_and_register") or plan,
    )
    monkeypatch.setattr(
        instance,
        "_start_watcher",
        lambda _plan: events.append("watcher_started") or watcher,
    )
    monkeypatch.setattr(
        instance,
        "_wait_watcher_ready",
        lambda _plan, _watcher: events.append("watcher_ready_validated"),
    )
    monkeypatch.setattr(
        instance,
        "_holdout_commands",
        lambda pid=0: (
            pytest.fail("holdout command built before watcher ready")
            if "watcher_ready_validated" not in events
            else {"run": ["run", str(pid)], "finalize": ["finalize"]}
        ),
    )
    monkeypatch.setattr(
        instance,
        "run_step",
        lambda stage, _command, **_kwargs: events.append(stage),
    )
    monkeypatch.setattr(
        holdout_v6,
        "finalize_holdout",
        lambda *_a, **_k: (
            events.append("holdout_result_revalidated")
            or {
                "accepted": True,
                "publishable": True,
                "retuning_after_holdout": False,
                "holdout_evidence_case_count": 90,
                "holdout_signature": "holdout-signature",
            }
        ),
    )
    monkeypatch.setattr(
        instance,
        "_finalize_sidecar",
        lambda: events.append("sidecar_finalized")
        or {"case_count": 90, "inventory_signature": "inventory-signature"},
    )
    monkeypatch.setattr(instance, "_stop_owned", lambda _process: None)
    monkeypatch.setattr(
        instance,
        "update_status",
        lambda stage, _message, **_values: events.append(stage),
    )
    assert instance.execute() == 0
    assert events.index("selection_signed") < events.index("freeze_and_register")
    assert events.index("freeze_and_register") < events.index("watcher_started")
    assert events.index("watcher_ready_validated") < events.index(
        "run_fresh_holdout_3x30"
    )


def test_calibration_terminal_holdout_fast_path_is_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    holdout_run = tmp_path / "holdout-run"
    sidecar = tmp_path / "sidecar"
    holdout_run.mkdir()
    sidecar.mkdir()
    protected_files = (
        holdout_run / "holdout_progress.json",
        holdout_run / "holdout_result.json",
        sidecar / sidecar_v6.COMPATIBILITY_INVENTORY_FILENAME,
        sidecar / "watcher_ready.json",
    )
    for index, path in enumerate(protected_files):
        path.write_text(f"immutable-{index}", encoding="utf-8")
    before = {path: holdout_v6.sha256_file(path) for path in protected_files}
    instance = object.__new__(calibration_v6.V6CalibrationOrchestrator)
    instance.config = SimpleNamespace(
        max_wait_hours=1.0,
        holdout_plan_dir=tmp_path / "holdout-plan",
        holdout_run_dir=holdout_run,
        sidecar_dir=sidecar,
    )
    instance.monotonic = lambda: 1.0
    instance.status = {}
    instance.watcher = None
    result = {
        "accepted": True,
        "publishable": True,
        "retuning_after_holdout": False,
        "holdout_evidence_case_count": 90,
        "holdout_signature": "holdout-signature",
    }
    inventory = {"case_count": 90, "inventory_signature": "inventory-signature"}
    monkeypatch.setattr(instance, "prepare", lambda: None)
    monkeypatch.setattr(instance, "log", lambda _message: None)
    monkeypatch.setattr(instance, "_ensure_development_plan", lambda: None)
    monkeypatch.setattr(
        instance,
        "_finalize_development",
        lambda: {"status": development_v6.SUCCESS_STATUS},
    )
    monkeypatch.setattr(
        instance, "_ensure_holdout_plan_and_registration", lambda: object()
    )
    monkeypatch.setattr(instance, "_existing_holdout_result", lambda _plan: result)
    monkeypatch.setattr(instance, "_existing_sidecar_inventory", lambda: inventory)
    monkeypatch.setattr(
        instance,
        "_start_watcher",
        lambda _plan: pytest.fail("watcher started for terminal calibration"),
    )
    monkeypatch.setattr(
        instance,
        "run_step",
        lambda *_a, **_k: pytest.fail("producer command run for terminal calibration"),
    )
    monkeypatch.setattr(instance, "update_status", lambda *_a, **_k: None)
    assert instance.execute() == 0
    assert {path: holdout_v6.sha256_file(path) for path in protected_files} == before


def test_v6_relay_rejects_output_inside_transitive_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protected = tmp_path / "immutable-v4-run"
    instance = object.__new__(relay_v6.FullCampaignRelayV6)
    instance.config = SimpleNamespace(
        v4_sidecar_root=tmp_path / "development-sidecar-sentinel",
        calibration_run_dir=tmp_path / "holdout-run",
        sidecar_dir=tmp_path / "sidecar",
        campaign_root=protected / "campaign-output",
        results_dir=tmp_path / "results",
        lot_replay_root=tmp_path / "lots",
        qualification_dir=tmp_path / "qualification",
        supervision_dir=tmp_path / "supervision",
        action_replay_root=tmp_path / "actions",
        bridge_json=tmp_path / "bridge.json",
        dashboard_html=tmp_path / "dashboard.html",
        final_html=tmp_path / "final.html",
    )
    monkeypatch.setattr(
        holdout_v6,
        "_protected_holdout_sources",
        lambda *_a, **_k: (protected,),
    )
    with pytest.raises(relay_v6.FullCampaignRelayError, match="transitive"):
        instance._validate_transitive_output_separation(object())  # noqa: SLF001


def test_v6_relay_binds_holdout_to_configured_development_before_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    instance = object.__new__(relay_v6.FullCampaignRelayV6)
    instance.config = SimpleNamespace(
        v4_plan_dir=(tmp_path / "wrong-plan").resolve(),
        v4_run_dir=(tmp_path / "wrong-run").resolve(),
        calibration_run_dir=tmp_path / "holdout-run",
    )
    plan = SimpleNamespace(
        manifest={
            "v6_development_source": {
                "plan_dir": str(tmp_path / "actual-plan"),
                "run_dir": str(tmp_path / "actual-run"),
            }
        }
    )
    monkeypatch.setattr(instance, "_validated_plan", lambda: plan)
    monkeypatch.setattr(
        instance, "_validate_transitive_output_separation", lambda _plan: None
    )
    monkeypatch.setattr(
        holdout_v6,
        "_registered_execution_mode",
        lambda *_a: pytest.fail("holdout evidence read before source binding"),
    )
    with pytest.raises(relay_v6.FullCampaignRelayError, match="figé le holdout"):
        instance.validate_calibration_handoff()


def test_calibration_commands_enforce_watcher_gate(tmp_path: Path) -> None:
    config = calibration_v6.V6CalibrationConfig(
        repo=tmp_path,
        v5_plan_dir=tmp_path / "v5-plan",
        v5_run_dir=tmp_path / "v5-run",
        v5_sidecar_root=tmp_path / "v5-sidecar",
        development_plan_dir=tmp_path / "dev-plan",
        development_run_dir=tmp_path / "dev-run",
        holdout_plan_dir=tmp_path / "holdout-plan",
        holdout_run_dir=tmp_path / "holdout-run",
        sidecar_dir=tmp_path / "sidecar",
        supervision_dir=tmp_path / "supervision",
    )
    instance = calibration_v6.V6CalibrationOrchestrator(config)
    commands = instance._holdout_commands(4242)  # noqa: SLF001
    assert "prepare-run" in commands["prepare_run"]
    assert commands["run"][commands["run"].index("--watcher-pid") + 1] == "4242"
    assert "--sidecar-dir" in commands["run"]
    joined = " ".join(" ".join(command) for command in commands.values())
    for forbidden in ("bridge", "campaign", "qualification", "delivery", "html"):
        assert forbidden not in joined.casefold()


def test_v6_relay_detached_command_keeps_required_cli_contract(tmp_path: Path) -> None:
    values = {
        "--repo": tmp_path,
        "--v4-plan-dir": tmp_path / "development-plan",
        "--v4-run-dir": tmp_path / "development-run",
        "--v4-sidecar-root": tmp_path / "forbidden-sidecar",
        "--calibration-plan-dir": tmp_path / "holdout-plan",
        "--calibration-run-dir": tmp_path / "holdout-run",
        "--sidecar-dir": tmp_path / "sidecar",
        "--bridge-json": tmp_path / "bridge.json",
        "--campaign-root": tmp_path / "campaign",
        "--results-dir": tmp_path / "results",
        "--lot-replay-root": tmp_path / "lots",
        "--qualification-dir": tmp_path / "qualification",
        "--dashboard-html": tmp_path / "dashboard.html",
        "--final-html": tmp_path / "final.html",
        "--action-replay-root": tmp_path / "actions",
        "--supervision-dir": tmp_path / "supervision",
    }
    argv: list[str] = []
    for flag, value in values.items():
        argv.extend((flag, str(value)))
    argv.extend(
        ("--action-replay-mode", "required", "--max-wait-hours", "240", "--detach")
    )
    args = relay_v6.implementation_v5._parser().parse_args(argv)  # noqa: SLF001
    command = relay_v6._child_command(args)  # noqa: SLF001
    assert command[:3] == [
        relay_v6.sys.executable,
        "-m",
        relay_v6.MODULE_NAME,
    ]
    assert command[command.index("--qualification-dir") + 1] == str(
        values["--qualification-dir"].resolve()
    )
    assert command[command.index("--action-replay-mode") + 1] == "required"
    assert command[command.index("--max-wait-hours") + 1] == "240.0"
    assert "--detached-child" in command
    assert "--detach" not in command


def test_v6_relay_help_and_detached_scientific_no_go_are_v6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with relay_v6._v6_downstream_binding():  # noqa: SLF001
        help_text = relay_v6.implementation_v5._parser().format_help()  # noqa: SLF001
    assert "Fail-closed V6 relay" in help_text
    assert "210-case development" not in help_text

    parser = SimpleNamespace(
        parse_args=lambda _argv: SimpleNamespace(detach=True)
    )
    monkeypatch.setattr(relay_v6.implementation_v5, "_parser", lambda: parser)
    monkeypatch.setattr(
        relay_v6,
        "detach",
        lambda _args: (_ for _ in ()).throw(relay_v6.ScientificNoGo("rejected")),
    )
    assert relay_v6.main([]) == 3


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
