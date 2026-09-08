from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_runner as runner,
)


PLAN_DIR = protocol.DEFAULT_OUTPUT_DIR


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


def test_frozen_v2_plan_validates_and_is_pinned(tmp_path: Path) -> None:
    validated = runner.validate_plan_artifact(PLAN_DIR)

    assert validated.plan_artifact_sha256 == runner.EXPECTED_PLAN_ARTIFACT_SHA256
    assert len(validated.candidates) == 36
    assert validated.manifest["plan_signature"] == (
        "5167e4bbae9059b71d6101168401ee137831816548fd0476b78483c7482fa879"
    )

    forged = tmp_path / "forged_plan"
    shutil.copytree(PLAN_DIR, forged)
    report = forged / "AUDIT_ET_PROTOCOLE.md"
    report.write_text(report.read_text(encoding="utf-8") + "\nforged\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory/digest"):
        runner.validate_plan_artifact(forged)


def test_engine_command_has_no_incident_and_uses_candidate_input() -> None:
    plan = runner.validate_plan_artifact(PLAN_DIR)
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


def test_smoke_executes_one_nonreusable_case(tmp_path: Path) -> None:
    calls: list[tuple[str, int, str]] = []
    output = tmp_path / "smoke"

    manifest = runner.run_calibration(
        plan_dir=PLAN_DIR,
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
            plan_dir=PLAN_DIR,
            output_dir=output,
            mode="screening",
            case_executor=_fake_executor([]),
        )


def test_screen_checkpoint_and_resume_adds_only_seeds_16_to_30(
    tmp_path: Path,
) -> None:
    output = tmp_path / "staged"
    screening_calls: list[tuple[str, int, str]] = []
    screening = runner.run_calibration(
        plan_dir=PLAN_DIR,
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
            plan_dir=PLAN_DIR,
            output_dir=output,
            mode="confirmation",
            workers=4,
            case_executor=_fake_executor([]),
        )

    preliminary_calls: list[tuple[str, int, str]] = []
    preliminary = runner.run_calibration(
        plan_dir=PLAN_DIR,
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
        plan_dir=PLAN_DIR,
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
        plan_dir=PLAN_DIR,
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


def test_resume_rejects_checkpoint_ledger_mismatch(tmp_path: Path) -> None:
    output = tmp_path / "tamper"
    runner.run_calibration(
        plan_dir=PLAN_DIR,
        output_dir=output,
        mode="screening",
        case_executor=_fake_executor([]),
    )
    runner.run_calibration(
        plan_dir=PLAN_DIR,
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
            plan_dir=PLAN_DIR,
            output_dir=output,
            mode="confirmation",
            case_executor=_fake_executor([]),
        )


def test_invalid_checkpoint_count_and_existing_lock_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly 15"):
        runner.run_calibration(
            plan_dir=PLAN_DIR,
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
            plan_dir=PLAN_DIR,
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
