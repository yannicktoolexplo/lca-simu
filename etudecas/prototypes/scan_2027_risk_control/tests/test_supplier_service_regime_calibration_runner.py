from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from etudecas import atomic_io

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_runner as runner,
)
from etudecas.prototypes.scan_2027_risk_control.tests.calibration_fixture import (
    build_synthetic_plan,
)
@pytest.fixture
def synthetic_plan(tmp_path, monkeypatch):
    plan = build_synthetic_plan(tmp_path / "synthetic")
    digest, files = runner._directory_digest(plan)
    assert len(files) == runner.EXPECTED_PLAN_FILE_COUNT
    # Only this test process accepts the synthetic artifact; all validators stay active.
    monkeypatch.setattr(runner, "EXPECTED_PLAN_ARTIFACT_SHA256", digest)
    return plan


def _fake_executor(calls: list[tuple[str, int, str]]):
    services = {
        1: 0.98,
        2: 0.93,
        3: 0.86,
        4: 0.80,
        5: 0.72,
        6: 0.65,
        7: 0.55,
        8: 0.45,
    }

    def execute(
        case: runner.PlannedCase,
        plan: runner.ValidatedPlan,
        output_dir: Path,
    ) -> dict[str, object]:
        del output_dir
        candidate = next(
            item for item in plan.candidates if item.scenario_id == case.scenario_id
        )
        calls.append((case.scenario_id, case.seed, case.stage))
        service = services[candidate.severity_index]
        demand_268091 = 1000.0
        demand_268967 = 500.0
        metrics = {
            "demand_qty_268091": demand_268091,
            "on_due_qty_268091": demand_268091 * service,
            "on_due_service_268091": service,
            "backlog_qty_days_268091": (1.0 - service) * 10_000.0,
            "ending_backlog_qty_268091": (1.0 - service) * 100.0,
            "demand_qty_268967": demand_268967,
            "on_due_qty_268967": demand_268967 * service,
            "on_due_service_268967": service,
            "backlog_qty_days_268967": (1.0 - service) * 5_000.0,
            "ending_backlog_qty_268967": (1.0 - service) * 50.0,
            "system_on_due_service": service,
            "minimum_product_on_due_service": service,
            "service_metric_definition": "test fixture",
        }
        evidence: dict[str, object] = {
            "schema_version": runner.EVIDENCE_SCHEMA_VERSION,
            "contract_revision": runner.CONTRACT_REVISION,
            "case_key": case.key,
            "scenario_id": case.scenario_id,
            "family": candidate.family,
            "severity_index": candidate.severity_index,
            "parameter_value": candidate.value,
            "parameter_unit": candidate.unit,
            "seed": case.seed,
            "stage": case.stage,
            "status": "synthetic_test_only",
            "valid": True,
            "validation_errors": [],
            "metrics": metrics,
            "candidate_input_sha256": plan.inventory[case.scenario_id][
                "input_sha256"
            ],
            "execution_input_hashes": {},
            "summary_sha256": "1" * 64,
            "service_daily_sha256": "2" * 64,
            "warmup_core_state_sha256": "3" * 64,
            "command_sha256": "4" * 64,
            "run_dir": "",
            "acute_incident_event_count": 0,
            "supplier_state_dependent_risks_enabled": False,
            "created_at_utc": "2026-09-03T00:00:00+00:00",
        }
        evidence["evidence_signature"] = runner._stable_sha256(evidence)
        return evidence

    return execute


def test_frozen_v2_plan_validates_and_is_pinned(tmp_path: Path, historical_artifact) -> None:
    plan_dir = historical_artifact("supplier_service_regime_calibration_plan_20260903_v2")
    validated = runner.validate_plan_artifact(plan_dir)

    assert validated.plan_artifact_sha256 == runner.EXPECTED_PLAN_ARTIFACT_SHA256
    assert len(validated.candidates) == 36
    assert validated.manifest["plan_signature"] == (
        "5167e4bbae9059b71d6101168401ee137831816548fd0476b78483c7482fa879"
    )

    forged = tmp_path / "forged_plan"
    shutil.copytree(plan_dir, forged)
    report = forged / "AUDIT_ET_PROTOCOLE.md"
    report.write_text(report.read_text(encoding="utf-8") + "\nforged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory/digest"):
        runner.validate_plan_artifact(forged)


def test_engine_command_has_no_incident_and_uses_candidate_input(synthetic_plan) -> None:
    plan = runner.validate_plan_artifact(synthetic_plan)
    candidate = next(
        item for item in plan.candidates if item.kind == "graph_reliability"
    )
    case = runner.PlannedCase(
        candidate.scenario_id,
        protocol.SCREENING_SEED,
        "screening",
    )

    command = runner.build_engine_command(case, plan, Path("case"))

    assert "--supplier-risk-events-csv" not in command
    assert "--no-supplier-state-dependent-risks" in command
    assert "--no-lot-trace" in command
    assert command[-len(protocol.MANAGED_REFERENCE_PROTOCOL_ARGS) :] == list(
        protocol.MANAGED_REFERENCE_PROTOCOL_ARGS
    )
    graph_index = command.index("--input") + 1
    assert Path(command[graph_index]).resolve() == Path(
        plan.inventory[candidate.scenario_id]["execution_inputs"]["graph"]
    ).resolve()


def test_smoke_executes_one_nonreusable_case(tmp_path: Path, synthetic_plan) -> None:
    calls: list[tuple[str, int, str]] = []
    output = tmp_path / "smoke"

    manifest = runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="smoke",
        workers=2,
        case_executor=_fake_executor(calls),
    )

    assert manifest["status"] == "smoke_complete_nonreusable"
    assert manifest["completed_case_count"] == 1
    assert manifest["smoke_only"] is True
    assert manifest["confirmatory_release_allowed"] is False
    assert manifest["action_promotion_allowed"] is False
    assert calls == [
        (
            protocol.build_candidates()[0].scenario_id,
            protocol.SCREENING_SEED,
            "smoke",
        )
    ]
    assert not (output / runner.SELECTION_FILE).exists()
    with pytest.raises(ValueError, match="another campaign signature"):
        runner.run_calibration(
            plan_dir=synthetic_plan,
            output_dir=output,
            mode="screening",
            case_executor=_fake_executor([]),
        )


def test_screen_checkpoint_and_resume_adds_only_seeds_16_to_30(
    tmp_path: Path, synthetic_plan,
) -> None:
    output = tmp_path / "staged"
    screening_calls: list[tuple[str, int, str]] = []
    screening = runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="screening",
        workers=4,
        case_executor=_fake_executor(screening_calls),
    )
    assert screening["status"] == "screening_complete_selection_frozen"
    assert len(screening_calls) == 36
    assert screening["selected_scenario_count"] == 10

    with pytest.raises(ValueError, match="requires the signed 15-seed checkpoint"):
        runner.run_calibration(
            plan_dir=synthetic_plan,
            output_dir=output,
            mode="confirmation",
            workers=4,
            case_executor=_fake_executor([]),
        )

    preliminary_calls: list[tuple[str, int, str]] = []
    preliminary = runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="confirmation",
        workers=4,
        checkpoint_after_repetitions=15,
        case_executor=_fake_executor(preliminary_calls),
    )
    assert preliminary["status"] == "paused_preliminary_15_of_30"
    assert len(preliminary_calls) == 150
    assert {seed for _, seed, _ in preliminary_calls} == set(
        protocol.PRELIMINARY_CONFIRMATION_SEEDS
    )
    checkpoint_path = output / runner.CHECKPOINT_FILE
    checkpoint_text = checkpoint_path.read_text(encoding="utf-8")
    checkpoint = json.loads(checkpoint_text)
    assert len(checkpoint["case_evidence_file_sha256"]) == 186
    prefix_hashes = dict(checkpoint["case_evidence_file_sha256"])

    repeated_calls: list[tuple[str, int, str]] = []
    repeated = runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="confirmation",
        workers=4,
        checkpoint_after_repetitions=15,
        case_executor=_fake_executor(repeated_calls),
    )
    assert repeated["status"] == "paused_preliminary_15_of_30"
    assert repeated_calls == []
    assert checkpoint_path.read_text(encoding="utf-8") == checkpoint_text

    final_calls: list[tuple[str, int, str]] = []
    final = runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="confirmation",
        workers=4,
        case_executor=_fake_executor(final_calls),
    )
    assert final["status"] == "complete_30_of_30"
    assert final["checkpoint_history_present"] is True
    assert final["calibration_characterization_complete"] is False
    assert final["final_regime_claim_allowed"] is False
    assert final["confirmatory_release_allowed"] is False
    assert len(final_calls) == 150
    assert {seed for _, seed, _ in final_calls} == set(
        protocol.FINAL_CONFIRMATION_SEEDS[15:]
    )
    ledger = json.loads((output / runner.LEDGER_FILE).read_text(encoding="utf-8"))
    assert len(ledger["case_files"]) == 336
    for case_key, item in prefix_hashes.items():
        assert ledger["case_files"][case_key] == item["relative_path"]
        assert ledger["case_file_sha256"][case_key] == item["sha256"]


def test_resume_rejects_checkpoint_ledger_mismatch(tmp_path: Path, synthetic_plan) -> None:
    output = tmp_path / "tamper"
    runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="screening",
        case_executor=_fake_executor([]),
    )
    runner.run_calibration(
        plan_dir=synthetic_plan,
        output_dir=output,
        mode="confirmation",
        checkpoint_after_repetitions=15,
        case_executor=_fake_executor([]),
    )
    ledger_path = output / runner.LEDGER_FILE
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    case_key = next(iter(ledger["case_files"]))
    ledger["case_file_sha256"][case_key] = "0" * 64
    runner._write_json(ledger_path, ledger)

    with pytest.raises(ValueError, match="evidence mismatch"):
        runner.run_calibration(
            plan_dir=synthetic_plan,
            output_dir=output,
            mode="confirmation",
            case_executor=_fake_executor([]),
        )


def test_invalid_checkpoint_count_and_existing_lock_fail_closed(tmp_path: Path, synthetic_plan) -> None:
    with pytest.raises(ValueError, match="exactly 15"):
        runner.run_calibration(
            plan_dir=synthetic_plan,
            output_dir=tmp_path / "bad_checkpoint",
            mode="confirmation",
            checkpoint_after_repetitions=14,
            case_executor=_fake_executor([]),
        )

    output = tmp_path / "locked"
    output.mkdir()
    (output / runner.LOCK_FILE).write_text("999999\n", encoding="ascii")
    with pytest.raises(RuntimeError, match="lock exists"):
        runner.run_calibration(
            plan_dir=synthetic_plan,
            output_dir=output,
            mode="smoke",
            case_executor=_fake_executor([]),
        )


def test_daily_service_matrix_rejects_duplicate_rows() -> None:
    duplicate = {
        "day": "0",
        "node_id": protocol.CLIENT_NODE_ID,
        "item_id": "item:268091",
        "demand_qty": "1",
        "required_with_backlog_qty": "1",
        "served_qty": "1",
        "backlog_end_qty": "0",
    }
    with pytest.raises(ValueError, match="Duplicate product/day"):
        runner._validate_daily_service_rows([duplicate, duplicate])


def test_production_pin_rejects_synthetic_plan(tmp_path):
    plan = build_synthetic_plan(tmp_path / "untrusted")
    with pytest.raises(ValueError, match="inventory/digest"):
        runner.validate_plan_artifact(plan)


@pytest.mark.parametrize("damage", ["missing_graph", "changed_graph", "changed_plan"])
def test_synthetic_plan_keeps_integrity_checks(synthetic_plan, damage):
    runner.validate_plan_artifact(synthetic_plan)
    if damage == "changed_plan":
        report = synthetic_plan / "AUDIT_ET_PROTOCOLE.md"
        report.write_text("tampered", encoding="utf-8")
        message = "inventory/digest"
    else:
        graph = synthetic_plan.parent / "graph.json"
        if damage == "missing_graph":
            graph.unlink()
        else:
            graph.write_text("{}", encoding="utf-8")
        message = "Execution input hash mismatch"
    with pytest.raises(ValueError, match=message):
        runner.validate_plan_artifact(synthetic_plan)


def test_current_runner_refuses_v1_output_without_changing_it(tmp_path, synthetic_plan):
    # Historical V1 manifest projection: no legacy executor is kept or run.
    validated = runner.validate_plan_artifact(synthetic_plan)
    legacy_signature_payload = {
        "schema_version": "etudecas.supplier_service_regime_calibration_runner.v1",
        "contract_revision": "isolated_regime_screen_select_checkpoint_resume_2026_09",
        "plan_signature": validated.manifest["plan_signature"],
        "plan_artifact_sha256": validated.plan_artifact_sha256,
        "runner_builder_sha256": "54e22075796f6899b43361fe548ffa42c7e5f6983ba216c0ed8c8c676a125fed",
        "protocol_builder_sha256": hashlib.sha256(Path(runner.protocol.__file__).read_bytes()).hexdigest(),
        "screening_seed": runner.protocol.SCREENING_SEED,
        "confirmation_seeds": list(runner.protocol.FINAL_CONFIRMATION_SEEDS),
        "seed_scheduling_policy": runner.SEED_SCHEDULING_POLICY,
        "candidate_ids": [candidate.scenario_id for candidate in validated.candidates],
        "scope": "smoke_one_case_nonreusable",
    }
    legacy_signature = runner._stable_sha256(legacy_signature_payload)
    output = tmp_path / "v1-output"
    output.mkdir()
    (output / runner.RUNNER_MANIFEST).write_text(json.dumps({
        "schema_version": legacy_signature_payload["schema_version"],
        "contract_revision": legacy_signature_payload["contract_revision"],
        "campaign_signature": legacy_signature,
        "smoke_only": True,
        "custom_executor_used": True,
        "status": "smoke_complete_nonreusable",
    }), encoding="utf-8")
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    calls = []
    with pytest.raises(ValueError, match="another campaign signature"):
        runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                               case_executor=_fake_executor(calls))
    assert calls == []
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}


def test_changed_v2_source_cannot_resume_existing_output(tmp_path, monkeypatch, synthetic_plan):
    output = tmp_path / "out"
    runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                           case_executor=_fake_executor([]))
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    original_hash = runner._sha256
    runner_path = Path(runner.__file__).resolve()
    monkeypatch.setattr(runner, "_sha256", lambda p: "0" * 64 if p == runner_path else original_hash(p))
    calls = []
    with pytest.raises(ValueError, match="another campaign signature"):
        runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                               case_executor=_fake_executor(calls))
    assert calls == []
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}


def test_v1_ledger_rejected_even_with_current_campaign_signature(tmp_path):
    # A renamed V1 ledger cannot pass the independent ledger schema check.
    (tmp_path / runner.LEDGER_FILE).write_text(json.dumps({
        "schema_version": "etudecas.supplier_service_regime_calibration_runner.v1.ledger",
        "campaign_signature": "current-signature",
        "case_files": {},
        "case_file_sha256": {},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="ledger signature/inventory mismatch"):
        runner._load_ledger(tmp_path, "current-signature")


def test_io_source_is_bound_to_signature_and_manifest(synthetic_plan, tmp_path, monkeypatch):
    validated = runner.validate_plan_artifact(synthetic_plan)
    signature = runner._campaign_signature(validated, smoke_only=True)
    manifest = runner._base_manifest(plan=validated, signature=signature,
        output_dir=tmp_path, workers=1, retention="summary", custom_executor_used=True, smoke_only=True)
    assert manifest["atomic_io_policy"] == atomic_io.POLICY_VERSION
    assert manifest["atomic_io_sha256"] == hashlib.sha256(Path(atomic_io.__file__).read_bytes()).hexdigest()
    original_hash = runner._sha256
    monkeypatch.setattr(runner, "_sha256", lambda p: "0" * 64 if p == Path(atomic_io.__file__).resolve() else original_hash(p))
    assert runner._campaign_signature(validated, smoke_only=True) != signature


def test_transient_ledger_refusal_and_resume_do_not_repeat_cases(tmp_path, monkeypatch, synthetic_plan):
    output = tmp_path / "out"
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
    result = runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                                   case_executor=_fake_executor(calls))
    assert refused == [True]
    assert len(calls) == 1
    assert result["status"] == "smoke_complete_nonreusable"
    assert result["atomic_io_source_unchanged_during_invocation"] is True
    calls.clear()
    runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                           case_executor=_fake_executor(calls))
    assert calls == []
    assert not list(output.rglob("*.tmp"))


def test_failed_ledger_commit_cannot_be_silently_resumed(tmp_path, monkeypatch, synthetic_plan):
    output = tmp_path / "out"
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
        runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                               case_executor=_fake_executor([]))
    assert len(attempts) == 6
    assert json.loads((output / runner.RUNNER_MANIFEST).read_text())["status"] == "failed"
    assert not (output / runner.LOCK_FILE).exists()
    assert not list(output.rglob("*.tmp"))
    monkeypatch.setattr(atomic_io.os, "replace", replace)
    calls = []
    with pytest.raises(ValueError, match="Evidence files exist without a ledger"):
        runner.run_calibration(plan_dir=synthetic_plan, output_dir=output, mode="smoke",
                               case_executor=_fake_executor(calls))
    assert calls == []
