from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_v5_calibration as launcher,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)


def _paths(tmp_path: Path) -> launcher.LaunchPaths:
    repo = tmp_path / "repo"
    v4_plan = tmp_path / "v4_plan"
    v4_run = tmp_path / "v4_run"
    for path in (repo, v4_plan, v4_run):
        path.mkdir()
    (v4_plan / "refinement_plan.json").write_text("{}\n", encoding="utf-8")
    (v4_run / "development_selection.json").write_text("{}\n", encoding="utf-8")
    return launcher.LaunchPaths(
        repo=repo,
        v4_plan_dir=v4_plan,
        v4_run_dir=v4_run,
        v4_sidecar_root=tmp_path / "v4_sidecar_absent",
        plan_dir=tmp_path / "v5_plan",
        run_dir=tmp_path / "v5_run",
        supervision_dir=tmp_path / "v5_supervision",
        sidecar_dir=tmp_path / "v5_sidecar",
    )


def test_commands_freeze_three_plus_three_two_workers_and_fresh_holdout(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    launcher._assert_contract_constants()  # noqa: SLF001
    commands = launcher.build_commands(paths, max_wait_hours=12)
    development = commands["development"]
    assert development[development.index("--workers") + 1] == "2"
    assert development[development.index("--stage") + 1] == "development"
    assert commands["watcher"][2] == launcher.WATCHER_MODULE
    assert tuple(refinement.DEVELOPMENT_SEEDS) == tuple(range(340287, 340317))
    assert refinement.EXPECTED_NEW_DEVELOPMENT_CASES == 180
    assert refinement.EXPECTED_HOLDOUT_CASES == 90

    relay = launcher.build_relay_command(
        paths, development_pid=123, watcher_pid=456, max_wait_hours=12
    )
    assert relay[relay.index("--development-pid") + 1] == "123"
    assert relay[relay.index("--watcher-pid") + 1] == "456"
    assert relay[:4] == [sys.executable, "-m", launcher.RELAY_MODULE, "relay"]


def test_fresh_path_validation_refuses_v4_overlap_and_existing_outputs(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    launcher.validate_fresh_paths(paths)

    overlap = launcher.LaunchPaths(
        **{**paths.__dict__, "run_dir": paths.v4_run_dir / "v5"}
    )
    with pytest.raises(launcher.LaunchError, match="chevauche"):
        launcher.validate_fresh_paths(overlap)

    paths.sidecar_dir.mkdir()
    with pytest.raises(launcher.LaunchError, match="déjà existante"):
        launcher.validate_fresh_paths(paths)


def test_launch_order_and_signed_receipt_without_real_processes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    events: list[str] = []

    def fake_run(command, *, cwd, log_path) -> None:
        del cwd, log_path
        events.append("plan" if "plan" in command else "validate")
        if "plan" in command:
            paths.plan_dir.mkdir()
            (paths.plan_dir / "refinement_plan.json").write_text(
                "{}\n", encoding="utf-8"
            )

    class FakeProcess:
        next_pid = 700

        def __init__(self):
            self.pid = FakeProcess.next_pid
            FakeProcess.next_pid += 1

        def poll(self):
            return None

        def terminate(self):
            events.append(f"terminate-{self.pid}")

    def fake_spawn(command, *, cwd, log_path):
        del cwd, log_path
        events.append(command[2])
        return FakeProcess()

    monkeypatch.setattr(launcher, "_run_checked", fake_run)
    monkeypatch.setattr(launcher, "_spawn", fake_spawn)
    receipt = launcher.launch(paths, max_wait_hours=8)
    assert events == [
        "plan",
        "validate",
        launcher.WATCHER_MODULE,
        launcher.CORE_MODULE,
        launcher.RELAY_MODULE,
    ]
    assert receipt["execution_contract"] == {
        "workers": 2,
        "development_seeds": list(range(340287, 340317)),
        "op93_candidate_count": 3,
        "op80_candidate_count": 3,
        "new_development_engine_runs": 180,
        "reused_op100_proofs": 30,
        "fresh_holdout_engine_runs_if_selected": 90,
    }
    capture_v4._verify_signature(  # noqa: SLF001
        receipt, "receipt_signature", "receipt"
    )
    assert (paths.supervision_dir / "launch_receipt.json").is_file()
    assert receipt["provenance"]["relay_module_sha256"] == hashlib.sha256(
        Path(launcher.__file__).read_bytes()
    ).hexdigest()


def test_generated_relay_command_dispatches_with_same_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    command = launcher.build_relay_command(
        paths, development_pid=123, watcher_pid=456, max_wait_hours=12
    )
    relays = []
    wakefulness = []

    def execute(self):
        relays.append(self)
        return 23

    monkeypatch.setattr(launcher.Relay, "execute", execute)
    monkeypatch.setattr(launcher, "_prevent_sleep", wakefulness.append)
    assert launcher.main(command[3:]) == 23
    assert len(relays) == 1
    relay = relays[0]
    assert relay.repo == paths.repo.resolve()
    assert relay.plan_dir == paths.plan_dir.resolve()
    assert relay.run_dir == paths.run_dir.resolve()
    assert relay.sidecar_dir == paths.sidecar_dir.resolve()
    assert relay.supervision_dir == paths.supervision_dir.resolve()
    assert (relay.development_pid, relay.watcher_pid) == (123, 456)
    assert relay.max_wait_seconds == 12 * 3600
    assert wakefulness == [True, False]


def test_relay_failure_keeps_signed_status_and_restores_wakefulness(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    command = launcher.build_relay_command(
        paths, development_pid=123, watcher_pid=456, max_wait_hours=12
    )
    wakefulness = []

    def fail(_self):
        raise RuntimeError("injected relay failure")

    monkeypatch.setattr(launcher.Relay, "execute", fail)
    monkeypatch.setattr(launcher, "_prevent_sleep", wakefulness.append)
    assert launcher.main(command[3:]) == 1
    assert wakefulness == [True, False]
    status = json.loads((paths.supervision_dir / "relay_status.json").read_text(encoding="utf-8"))
    capture_v4._verify_signature(status, "status_signature", "status")  # noqa: SLF001
    assert status["stage"] == "failed"
    assert status["error"] == "injected relay failure"


def test_launch_cli_without_mode_keeps_existing_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _paths(tmp_path)
    calls = []

    def launch(actual_paths, *, max_wait_hours):
        calls.append((actual_paths, max_wait_hours))
        return {"status": "captured"}

    monkeypatch.setattr(launcher, "launch", launch)
    arguments = []
    for field, value in paths.__dict__.items():
        arguments.extend(["--" + field.replace("_", "-"), str(value)])
    assert launcher.main([*arguments, "--max-wait-hours", "12"]) == 0
    assert calls == [(paths, 12.0)]
    assert json.loads(capsys.readouterr().out) == {"status": "captured"}


@pytest.mark.parametrize("failing_child", [2, 3])
def test_launch_failure_stops_only_started_children_in_reverse_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failing_child: int
) -> None:
    paths = _paths(tmp_path)
    children = []
    stopped = []

    class Child:
        def __init__(self, pid):
            self.pid = pid

        def poll(self):
            return None

        def terminate(self):
            stopped.append(self.pid)

    def spawn(*_args, **_kwargs):
        if len(children) + 1 == failing_child:
            raise RuntimeError("injected child failure")
        child = Child(101 + len(children))
        children.append(child)
        return child

    monkeypatch.setattr(launcher, "_run_checked", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(launcher, "_spawn", spawn)
    with pytest.raises(RuntimeError, match="injected child failure"):
        launcher.launch(paths)
    assert stopped == [child.pid for child in reversed(children)]
    assert not (paths.supervision_dir / "launch_receipt.json").exists()


def _relay(tmp_path: Path) -> launcher.Relay:
    repo = tmp_path / "repo"
    plan = tmp_path / "plan"
    run = tmp_path / "run"
    supervision = tmp_path / "supervision"
    sidecar = tmp_path / "sidecar"
    for path in (repo, plan, run, supervision):
        path.mkdir()
    (plan / "refinement_plan.json").write_text(
        json.dumps({"plan_signature": "p" * 64}), encoding="utf-8"
    )
    return launcher.Relay(
        repo=repo,
        plan_dir=plan,
        run_dir=run,
        supervision_dir=supervision,
        development_pid=101,
        watcher_pid=102,
        sidecar_dir=sidecar,
        max_wait_hours=1,
        poll_seconds=0.001,
    )


def _progress(stage: str, expected: int, *, completed: int | None = None):
    unsigned = {
        "schema_version": f"{refinement.SCHEMA_VERSION}.{stage}.progress",
        "plan_signature": "p" * 64,
        "stage": stage,
        "status": "complete",
        "completed_case_count": expected if completed is None else completed,
        "expected_case_count": expected,
        "execution_mode": refinement.OFFICIAL_EXECUTION_MODE,
        "publishable": True,
        "error": "",
    }
    return {**unsigned, "progress_signature": refinement.stable_sha256(unsigned)}


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_progress_requires_signed_complete_exact_counts(tmp_path: Path) -> None:
    path = tmp_path / "development_progress.json"
    payload = _progress("development", 210)
    _write_json(path, payload)
    checked = launcher._verify_progress(  # noqa: SLF001
        path, stage="development", expected=210, require_complete=True
    )
    assert checked["completed_case_count"] == 210

    payload["completed_case_count"] = 209
    _write_json(path, payload)
    with pytest.raises(Exception, match="Signature invalide"):
        launcher._verify_progress(  # noqa: SLF001
            path, stage="development", expected=210, require_complete=True
        )


def test_no_go_never_calls_watcher_or_holdout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    relay = _relay(tmp_path)
    _write_json(
        relay.run_dir / "development_selection.json",
        {
            "status": "development_failed_no_holdout",
            "selected_candidate_keys": None,
        },
    )
    stages: list[str] = []
    monkeypatch.setattr(
        relay, "run_step", lambda stage, arguments: stages.append(stage)
    )
    monkeypatch.setattr(relay, "wait_for_development", lambda: None)
    monkeypatch.setattr(
        relay,
        "wait_for_watcher_ready",
        lambda: pytest.fail("watcher must not gate a no-go"),
    )
    assert relay.execute() == 0
    assert stages == ["validate_plan_before_wait", "finalize_development"]
    status = json.loads(relay.status_path.read_text(encoding="utf-8"))
    assert status["stage"] == "scientific_no_go_after_development"
    assert status["holdout_engine_runs"] == 0
    capture_v4._verify_signature(status, "status_signature", "status")  # noqa: SLF001


def test_holdout_runs_only_after_watcher_barrier_and_uses_two_workers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    relay = _relay(tmp_path)
    _write_json(
        relay.run_dir / "development_selection.json",
        {
            "status": launcher.SELECTION_STATUS,
            "selected_candidate_keys": {
                "op_100": "op100_source",
                "op_93": "op93",
                "op_80": "op80",
            },
        },
    )
    _write_json(
        relay.run_dir / "holdout_progress.json",
        _progress("holdout", launcher.EXPECTED_HOLDOUT_CASES),
    )
    _write_json(
        relay.run_dir / "holdout_result.json",
        {
            "accepted": True,
            "status": "holdout_validated_30_carried_unseen_seeds",
            "holdout_evidence_case_count": 90,
        },
    )
    events: list[tuple[str, tuple[str, ...]]] = []

    def run_step(stage: str, arguments) -> None:
        events.append((stage, tuple(arguments)))

    monkeypatch.setattr(relay, "run_step", run_step)
    monkeypatch.setattr(relay, "wait_for_development", lambda: None)
    monkeypatch.setattr(
        relay,
        "wait_for_watcher_ready",
        lambda: events.append(("watcher_ready", ())) or {},
    )
    monkeypatch.setattr(
        relay,
        "wait_for_curve_capture",
        lambda: {"curve_capture_complete": True},
    )
    assert relay.execute() == 0
    names = [name for name, _args in events]
    assert names.index("watcher_ready") < names.index("run_fresh_holdout_90_cases")
    holdout_args = dict(
        (arg, events[names.index("run_fresh_holdout_90_cases")][1][index + 1])
        for index, arg in enumerate(
            events[names.index("run_fresh_holdout_90_cases")][1][:-1]
        )
        if arg.startswith("--")
    )
    assert holdout_args["--stage"] == "holdout"
    assert holdout_args["--workers"] == "2"
    status = json.loads(relay.status_path.read_text(encoding="utf-8"))
    assert status["stage"] == "calibration_accepted"
    assert status["expected_fresh_holdout_engine_runs"] == 90


def test_watcher_ready_fails_closed_when_process_is_dead(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    relay = _relay(tmp_path)
    monkeypatch.setattr(launcher, "_process_running", lambda _pid: False)
    with pytest.raises(RuntimeError, match="arrêté avant le holdout"):
        relay.wait_for_watcher_ready()
