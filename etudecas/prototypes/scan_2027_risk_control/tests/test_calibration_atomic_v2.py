"""Fault injection at the actual publication boundary, without the simulator."""
import hashlib
import json
from pathlib import Path

import pytest

from etudecas import atomic_io
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_runner as legacy,
    supplier_service_regime_calibration_runner_v2 as runner,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_service_regime_calibration_runner as scenarios,
)
from etudecas.prototypes.scan_2027_risk_control.tests.calibration_fixture import build_synthetic_plan


@pytest.fixture
def plan(tmp_path, monkeypatch):
    path = build_synthetic_plan(tmp_path / "plan")
    digest, _ = runner._directory_digest(path)
    monkeypatch.setattr(runner, "EXPECTED_PLAN_ARTIFACT_SHA256", digest)
    monkeypatch.setattr(legacy, "EXPECTED_PLAN_ARTIFACT_SHA256", digest)
    return path


def test_v2_refuses_v1_output_without_changing_it(tmp_path, monkeypatch, plan):
    output = tmp_path / "out"
    monkeypatch.setattr(scenarios, "runner", legacy)
    legacy.run_calibration(plan_dir=plan, output_dir=output, mode="smoke",
                           case_executor=scenarios._fake_executor([]))
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="another campaign signature"):
        runner.run_calibration(plan_dir=plan, output_dir=output, mode="smoke",
                               case_executor=scenarios._fake_executor([]))
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}


def test_io_source_is_bound_to_signature_and_manifest(plan, tmp_path, monkeypatch):
    validated = runner.validate_plan_artifact(plan)
    signature = runner._campaign_signature(validated, smoke_only=True)
    manifest = runner._base_manifest(plan=validated, signature=signature,
        output_dir=tmp_path, workers=1, retention="summary", custom_executor_used=True, smoke_only=True)
    assert manifest["atomic_io_policy"] == atomic_io.POLICY_VERSION
    assert manifest["atomic_io_sha256"] == hashlib.sha256(Path(atomic_io.__file__).read_bytes()).hexdigest()
    original_hash = runner._sha256
    monkeypatch.setattr(runner, "_sha256", lambda p: "0" * 64 if p == Path(atomic_io.__file__).resolve() else original_hash(p))
    assert runner._campaign_signature(validated, smoke_only=True) != signature


def test_transient_ledger_refusal_and_resume_do_not_repeat_cases(tmp_path, monkeypatch, plan):
    output = tmp_path / "out"
    monkeypatch.setattr(scenarios, "runner", runner)
    replace = atomic_io.os.replace
    refused = []
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _: None)

    def replace_with_one_refusal(source, target):
        if Path(target).name == runner.LEDGER_FILE and not refused:
            refused.append(True)
            error = PermissionError("injected ledger lock")
            error.winerror = 5
            raise error
        replace(source, target)

    monkeypatch.setattr(atomic_io.os, "replace", replace_with_one_refusal)
    calls = []
    result = runner.run_calibration(plan_dir=plan, output_dir=output, mode="smoke",
                                   case_executor=scenarios._fake_executor(calls))
    assert refused == [True]
    assert len(calls) == 1
    assert result["status"] == "smoke_complete_nonreusable"
    assert result["atomic_io_source_unchanged_during_invocation"] is True
    calls.clear()
    runner.run_calibration(plan_dir=plan, output_dir=output, mode="smoke",
                           case_executor=scenarios._fake_executor(calls))
    assert calls == []
    assert not list(output.rglob("*.tmp"))


def test_failed_ledger_commit_cannot_be_silently_resumed(tmp_path, monkeypatch, plan):
    output = tmp_path / "out"
    monkeypatch.setattr(scenarios, "runner", runner)
    replace = atomic_io.os.replace
    attempts = []
    monkeypatch.setattr(atomic_io.time, "sleep", lambda _: None)

    def refuse_ledger(source, target):
        if Path(target).name == runner.LEDGER_FILE:
            attempts.append(True)
            error = PermissionError("persistent ledger lock")
            error.winerror = 32
            raise error
        replace(source, target)

    monkeypatch.setattr(atomic_io.os, "replace", refuse_ledger)
    with pytest.raises(PermissionError, match="persistent ledger lock"):
        runner.run_calibration(plan_dir=plan, output_dir=output, mode="smoke",
                               case_executor=scenarios._fake_executor([]))
    assert len(attempts) == 6
    assert json.loads((output / runner.RUNNER_MANIFEST).read_text())["status"] == "failed"
    assert not (output / runner.LOCK_FILE).exists()
    assert not list(output.rglob("*.tmp"))
    monkeypatch.setattr(atomic_io.os, "replace", replace)
    calls = []
    with pytest.raises(ValueError, match="Evidence files exist without a ledger"):
        runner.run_calibration(plan_dir=plan, output_dir=output, mode="smoke",
                               case_executor=scenarios._fake_executor(calls))
    assert calls == []
