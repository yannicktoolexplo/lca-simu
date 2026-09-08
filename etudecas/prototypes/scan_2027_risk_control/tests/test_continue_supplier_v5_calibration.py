from __future__ import annotations

import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_v5_calibration as relay_module,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)


def _relay(tmp_path: Path) -> relay_module.Relay:
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
    return relay_module.Relay(
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
    checked = relay_module._verify_progress(  # noqa: SLF001
        path, stage="development", expected=210, require_complete=True
    )
    assert checked["completed_case_count"] == 210

    payload["completed_case_count"] = 209
    _write_json(path, payload)
    with pytest.raises(Exception, match="Signature invalide"):
        relay_module._verify_progress(  # noqa: SLF001
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
            "status": relay_module.SELECTION_STATUS,
            "selected_candidate_keys": {
                "op_100": "op100_source",
                "op_93": "op93",
                "op_80": "op80",
            },
        },
    )
    _write_json(
        relay.run_dir / "holdout_progress.json",
        _progress("holdout", relay_module.EXPECTED_HOLDOUT_CASES),
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
    monkeypatch.setattr(relay_module, "_process_running", lambda _pid: False)
    with pytest.raises(RuntimeError, match="arrêté avant le holdout"):
        relay.wait_for_watcher_ready()
