from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v2 as v2,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v3 as v3,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_multiseed_refinement_v2 import (
    _raw_evidence,
)


def _prepare_v2_no_go(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    if not v2.DEFAULT_PLAN_OUTPUT.is_dir() or not v3.DEFAULT_V2_RUN.is_dir():
        pytest.skip("Signed complete V1/V2 campaign artifacts are unavailable")
    v1_plan = v2.DEFAULT_SOURCE_PLAN
    v1_run = v2.DEFAULT_SOURCE_RUN
    plan = tmp_path / "v2_plan"
    run = tmp_path / "v2_run"
    shutil.copytree(v2.DEFAULT_PLAN_OUTPUT, plan)
    shutil.copytree(v3.DEFAULT_V2_RUN, run)
    return v1_plan, v1_run, plan, run


def _prepare_v3(tmp_path: Path) -> tuple[Path, Path]:
    v1_plan, v1_run, v2_plan, v2_run = _prepare_v2_no_go(tmp_path)
    plan = tmp_path / "v3_plan"
    v3.prepare_plan(
        plan,
        v1_plan_dir=v1_plan,
        v1_run_dir=v1_run,
        v2_plan_dir=v2_plan,
        v2_run_dir=v2_run,
    )
    return plan, v2_run


def _v3_executor(calls: list[tuple[float, float, int]], v2_run: Path):
    def executor(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        _output: Path,
        seed: int,
    ) -> dict[str, Any]:
        calls.append((candidate.offset_days_268091, candidate.offset_days_268967, seed))
        # 94.5 is the closest admissible op80 candidate; all remain non-saturated.
        service = {94.0: 0.805, 94.5: 0.800, 95.0: 0.795}[candidate.offset_days_268967]
        payload = _raw_evidence(candidate, adapter, seed, service, service)
        reference = json.loads(
            v2._evidence_path(v2_run, v2._case_key("op100_reference", seed)).read_text(
                encoding="utf-8"
            )
        )["metrics"]
        for product in ("268091", "268967"):
            demand = reference[f"demand_qty_{product}"]
            payload["metrics"][f"demand_qty_{product}"] = demand
            payload["metrics"][f"on_due_qty_{product}"] = demand * service
        payload.pop("evidence_signature")
        payload["evidence_signature"] = coarse._stable_sha256(payload)
        return payload

    return executor


def test_plan_revalidates_65_proofs_and_registers_exactly_15_new(
    tmp_path: Path,
) -> None:
    plan_dir, v2_run = _prepare_v3(tmp_path)
    plan = v3.validate_plan(plan_dir)

    assert plan.manifest["expected_case_count"] == 80
    assert plan.manifest["reused_case_count"] == 65
    assert plan.manifest["new_case_count"] == 15
    assert plan.manifest["source"]["v2_no_go_status"] == (
        "five_seed_loo_screen_failed_no_holdout"
    )
    assert len(plan.manifest["source"]["artifact_hashes"]["v2_evidence_sha256"]) == 65
    assert {
        (row["offset_days_268091"], row["offset_days_268967"])
        for row in plan.manifest["candidate_design"]["new_op80_candidates"]
    } == {(16.5, 94.0), (16.5, 94.5), (16.5, 95.0)}
    assert plan.manifest["candidate_design"]["fixed_op93_candidate_key"] == (
        "op93_refine_7_81"
    )
    assert plan.manifest["holdout_contract"]["cases_in_this_plan"] == 0


def test_run_resumes_without_reexecuting_and_validates_80_proofs(
    tmp_path: Path,
) -> None:
    plan_dir, v2_run = _prepare_v3(tmp_path)
    run_dir = tmp_path / "v3_run"
    calls: list[tuple[float, float, int]] = []
    executor = _v3_executor(calls, v2_run)

    first = v3.run(plan_dir, run_dir, executor=executor)
    first_calls = list(calls)
    second = v3.run(plan_dir, run_dir, executor=executor)

    assert first == second
    assert len(first_calls) == 15
    assert calls == first_calls
    assert {seed for _, _, seed in calls} == set(v3.CALIBRATION_SEEDS)
    assert not ({seed for _, _, seed in calls} & set(v3.HOLDOUT_SEEDS))
    assert first["selection"]["status"] == v3.SELECTION_PASS_STATUS
    assert first["selection"]["selected_pair"]["op80_candidate_key"] == (
        "op80_refine_v3_16p5_94p5"
    )
    assert (run_dir / "selected_operating_points.json").is_file()
    assert (
        v3.validate_selected_operating_points(
            run_dir / "selected_operating_points.json"
        )["status"]
        == v3.POINTS_STATUS
    )
    validated = v3.validate_run(plan_dir, run_dir)
    assert validated == first


def test_interrupted_run_imports_once_and_executes_only_missing(tmp_path: Path) -> None:
    plan_dir, v2_run = _prepare_v3(tmp_path)
    run_dir = tmp_path / "v3_run"
    failed = False
    successful: list[tuple[float, float, int]] = []

    def flaky(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        output: Path,
        seed: int,
    ) -> dict[str, Any]:
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("synthetic interruption")
        successful.append(
            (candidate.offset_days_268091, candidate.offset_days_268967, seed)
        )
        return _v3_executor([], v2_run)(candidate, adapter, output, seed)

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        v3.run(plan_dir, run_dir, executor=flaky, max_workers=1)
    completed_after_failure = json.loads(
        (run_dir / "progress.json").read_text(encoding="utf-8")
    )["completed_case_count"]
    assert completed_after_failure >= 65

    calls: list[tuple[float, float, int]] = []
    v3.run(plan_dir, run_dir, executor=_v3_executor(calls, v2_run), max_workers=1)
    assert len(calls) == 15 - (completed_after_failure - 65)
    assert len(list((run_dir / "evidence").glob("*.json"))) == 80


def test_tamper_in_v2_source_or_imported_evidence_fails_closed(tmp_path: Path) -> None:
    plan_dir, v2_run = _prepare_v3(tmp_path)
    source_path = next((v2_run / "evidence").glob("*.json"))
    source_original = source_path.read_text(encoding="utf-8")
    source_payload = json.loads(source_original)
    source_payload["metrics"]["system_on_due_service"] = 0.123
    source_path.write_text(json.dumps(source_payload), encoding="utf-8")
    with pytest.raises(ValueError):
        v3.validate_plan(plan_dir)
    source_path.write_text(source_original, encoding="utf-8")

    run_dir = tmp_path / "v3_run"
    v3.run(plan_dir, run_dir, executor=_v3_executor([], v2_run))
    imported = next((run_dir / "evidence").glob("*.json"))
    payload = json.loads(imported.read_text(encoding="utf-8"))
    payload["candidate_id"] = "re_signed_but_wrong"
    payload.pop("evidence_signature")
    payload["evidence_signature"] = coarse._stable_sha256(payload)
    imported.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        v3.validate_run(plan_dir, run_dir)


def test_resigned_plan_proposal_graph_and_extra_evidence_fail_closed(
    tmp_path: Path,
) -> None:
    plan_dir, v2_run = _prepare_v3(tmp_path)
    plan_path = plan_dir / "refinement_plan.json"
    original_plan = json.loads(plan_path.read_text(encoding="utf-8"))

    changed = json.loads(json.dumps(original_plan))
    changed["status"] = "re_signed_wrong_status"
    changed["plan_signature"] = v3._stable(v3._manifest_unsigned(changed))
    plan_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="contracts are not canonical"):
        v3.validate_plan(plan_dir)
    plan_path.write_text(json.dumps(original_plan), encoding="utf-8")

    proposal_path = plan_dir / "op80_refinement_candidates.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["status"] = "re_signed_wrong_status"
    proposal.pop("artifact_signature")
    proposal["artifact_signature"] = v3._stable(proposal)
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    changed = json.loads(json.dumps(original_plan))
    changed["candidate_design"]["proposal_sha256"] = v3._sha(proposal_path)
    changed["plan_signature"] = v3._stable(v3._manifest_unsigned(changed))
    plan_path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate design changed"):
        v3.validate_plan(plan_dir)

    # Restore, then alter and re-register a graph: semantic reconstruction rejects it.
    proposal = {
        "schema_version": f"{v3.SCHEMA_VERSION}.candidate_design",
        "status": "pre_registered_before_v3_execution",
        "candidates": [v3._spec_payload(s) for s in v3.OP80_REFINEMENT_WAVE],
        "calibration_seeds": list(v3.CALIBRATION_SEEDS),
        "holdout_cases_read": 0,
    }
    proposal["artifact_signature"] = v3._stable(proposal)
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    original_plan["candidate_design"]["proposal_sha256"] = v3._sha(proposal_path)
    graph_path = (
        plan_dir / original_plan["inventory"][v3.FIXED_REFERENCE_KEY]["graph_path"]
    )
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["re_signed_tamper"] = True
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    original_plan["inventory"][v3.FIXED_REFERENCE_KEY]["graph_sha256"] = v3._sha(
        graph_path
    )
    original_plan["plan_signature"] = v3._stable(v3._manifest_unsigned(original_plan))
    plan_path.write_text(json.dumps(original_plan), encoding="utf-8")
    with pytest.raises(ValueError, match="graph changed"):
        v3.validate_plan(plan_dir)

    # A valid plan/run also rejects an unregistered JSON proof.
    fresh_plan, fresh_v2_run = _prepare_v3(tmp_path / "fresh")
    run_dir = tmp_path / "fresh_run"
    v3.run(fresh_plan, run_dir, executor=_v3_executor([], fresh_v2_run))
    (run_dir / "evidence" / "extra.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="outside the V3 inventory"):
        v3.validate_run(fresh_plan, run_dir)


def test_import_has_no_plan_side_effect() -> None:
    assert v3.DEFAULT_PLAN_OUTPUT.name.endswith("refinement_plan_20260904_v3")
    assert v3.DEFAULT_RUN_OUTPUT.name.endswith("refinement_run_20260904_v3")


def test_autonomous_selection_and_destination_disjunction(tmp_path: Path) -> None:
    specs = (
        v3.CandidateSpec("op100_reference", 0.0, 0.0, "op_100", "reuse_v2"),
        v3.CandidateSpec("op93_refine_7_81", 7.0, 81.0, "op_93", "reuse_v2"),
        *v3.OP80_REFINEMENT_WAVE,
    )
    inventory: dict[str, dict[str, Any]] = {}
    for spec in specs:
        graph = tmp_path / f"{spec.key}.json"
        graph.write_text("{}", encoding="utf-8")
        inventory[spec.key] = {
            "graph_path": graph.name,
            "graph_sha256": v3._sha(graph),
        }
    plan = v3.RefinementPlan(
        tmp_path,
        {
            "plan_signature": "synthetic",
            "selection_contract": v3._selection_contract(),
            "holdout_contract": v3._holdout_contract(),
            "source_hashes": {},
            "cohorts": {},
        },
        None,  # type: ignore[arg-type]
        specs,
        inventory,
    )
    services = {
        "op100_reference": 1.0,
        "op93_refine_7_81": 0.93,
        "op80_refine_v3_16p5_94": 0.805,
        "op80_refine_v3_16p5_94p5": 0.800,
        "op80_refine_v3_16p5_95": 0.795,
    }
    evidence = {}
    for spec in specs:
        for seed in v3.CALIBRATION_SEEDS:
            service = services[spec.key]
            evidence[v3._case_key(spec.key, seed)] = {
                "seed": seed,
                "metrics": {
                    "system_on_due_service": service,
                    "on_due_service_268091": service,
                    "on_due_service_268967": service,
                    "minimum_product_on_due_service": service,
                    "on_due_qty_268091": 700.0 * service,
                    "demand_qty_268091": 700.0,
                    "on_due_qty_268967": 300.0 * service,
                    "demand_qty_268967": 300.0,
                },
            }
    selection, points = v3._select(plan, evidence)
    assert selection["selected_pair"]["op80_candidate_key"] == (
        "op80_refine_v3_16p5_94p5"
    )
    assert points is not None
    assert selection["status"] == v3.SELECTION_PASS_STATUS
    assert points["status"] == v3.POINTS_STATUS
    with pytest.raises(ValueError, match="overlaps immutable source"):
        v3._assert_disjoint(tmp_path / "source" / "child", tmp_path / "source")
