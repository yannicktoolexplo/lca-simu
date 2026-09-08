from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_calibration as v1,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v2 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_fine_prevalidation import (
    _executor as previous_executor,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_fine_prevalidation import (
    _source_points,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_fine_prevalidation as previous,
)


def _row(seed: int, left: float, right: float) -> dict[str, float | int]:
    return {
        "seed": seed,
        "system_on_due_service": (7.0 * left + 3.0 * right) / 10.0,
        "on_due_service_268091": left,
        "on_due_service_268967": right,
        "minimum_product_on_due_service": min(left, right),
        "on_due_qty_268091": 700.0 * left,
        "demand_qty_268091": 700.0,
        "on_due_qty_268967": 300.0 * right,
        "demand_qty_268967": 300.0,
    }


def _raw_evidence(
    candidate: coarse.Candidate,
    adapter: coarse.ValidatedPlan,
    seed: int,
    left: float,
    right: float,
) -> dict[str, Any]:
    metrics = {
        "system_on_due_service": (left + right) / 2.0,
        "on_due_service_268091": left,
        "on_due_service_268967": right,
        "minimum_product_on_due_service": min(left, right),
        "on_due_qty_268091": 100.0 * left,
        "demand_qty_268091": 100.0,
        "on_due_qty_268967": 100.0 * right,
        "demand_qty_268967": 100.0,
    }
    payload: dict[str, Any] = {
        "schema_version": coarse.EVIDENCE_SCHEMA_VERSION,
        **asdict(candidate),
        "seed": seed,
        "valid": True,
        "validation_errors": [],
        "status": "synthetic_test",
        "metrics": metrics,
        "graph_sha256": adapter.inventory[candidate.candidate_id]["graph_sha256"],
        "summary_sha256": "summary",
        "service_daily_sha256": "service",
        "engine_sha256": coarse._sha256(adapter.engine),
        "command_sha256": "command",
        "run_dir": "synthetic",
        "created_at_utc": "2026-09-04T00:00:00+00:00",
    }
    payload["evidence_signature"] = coarse._stable_sha256(payload)
    return payload


def _prepare_v1(tmp_path: Path) -> tuple[Path, Path]:
    source_points = _source_points(tmp_path)
    previous_plan = tmp_path / "previous_plan"
    previous_run = tmp_path / "previous_run"
    previous.prepare_plan(previous_plan, source_points_path=source_points)

    def previous_response(point_id: str, _seed: int) -> tuple[float, float]:
        return {
            "op_100": (1.0, 1.0),
            "op_93": (0.945, 1.0),
            "op_80": (0.82, 0.69),
        }[point_id]

    previous.run(
        previous_plan,
        previous_run,
        executor=previous_executor(previous_response, []),
    )
    plan_dir = tmp_path / "v1_plan"
    run_dir = tmp_path / "v1_run"
    v1.prepare_plan(
        plan_dir,
        source_plan_dir=previous_plan,
        source_run_dir=previous_run,
    )

    def executor(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        values = {
            (7.0, 90.0): (0.92, 0.94),
            (10.0, 90.0): (0.89, 0.93),
            (14.0, 96.0): (0.79, 0.82),
            (16.0, 95.0): (0.75, 0.82),
        }
        left, right = values[
            (candidate.offset_days_268091, candidate.offset_days_268967)
        ]
        return _raw_evidence(candidate, adapter, seed, left, right)

    v1.run(plan_dir, run_dir, executor=executor)
    return plan_dir, run_dir


def test_plan_reuses_every_v1_case_and_excludes_holdout(tmp_path: Path) -> None:
    source_plan, source_run = _prepare_v1(tmp_path)
    plan_dir = tmp_path / "refinement_plan"
    refinement.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )
    plan = refinement.validate_plan(plan_dir)

    assert plan.manifest["cohorts"] == {
        "design": [340281],
        "calibration": [340282, 340283, 340284, 340285, 340286],
        "holdout_sealed": list(range(340287, 340317)),
    }
    assert plan.manifest["reused_case_count"] == 35
    assert plan.manifest["new_case_count"] == 30
    assert plan.manifest["expected_case_count"] == 65
    assert plan.manifest["holdout_contract"]["cases_in_this_plan"] == 0
    assert {
        (row["offset_days_268091"], row["offset_days_268967"])
        for row in plan.manifest["candidate_design"]["fixed_op93_candidates"]
    } == {(7.0, 75.0), (7.0, 81.0), (7.0, 86.0)}
    assert {
        (row["offset_days_268091"], row["offset_days_268967"])
        for row in plan.manifest["candidate_design"]["fixed_op80_candidates"]
    } == {(17.0, 95.0), (17.0, 94.0), (18.0, 94.0)}
    assert len(plan.manifest["source"]["reused_evidence_sha256"]) == 35


def test_plan_signature_covers_low_state_proposals(tmp_path: Path) -> None:
    source_plan, source_run = _prepare_v1(tmp_path)
    plan_dir = tmp_path / "refinement_plan"
    refinement.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )
    proposal = plan_dir / "op80_refinement_candidates.json"
    payload = json.loads(proposal.read_text(encoding="utf-8"))
    payload["candidates"][0]["offset_days_268967"] = 94.0
    proposal.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="candidate design changed"):
        refinement.validate_plan(plan_dir)


def test_plan_signature_covers_candidates_rules_and_counts(tmp_path: Path) -> None:
    source_plan, source_run = _prepare_v1(tmp_path)
    plan_dir = tmp_path / "refinement_plan"
    refinement.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )
    manifest_path = plan_dir / "refinement_plan.json"
    original = manifest_path.read_text(encoding="utf-8")

    def candidate_tamper(payload: dict[str, Any]) -> None:
        payload["candidates"][-1]["offset_days_268967"] = 93.0

    def rule_tamper(payload: dict[str, Any]) -> None:
        payload["selection_contract"]["same_seed_joint_strict_order_required"] = 3

    def count_tamper(payload: dict[str, Any]) -> None:
        payload["new_case_count"] = 29

    for tamper in (candidate_tamper, rule_tamper, count_tamper):
        payload = json.loads(original)
        tamper(payload)
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="plan/signature"):
            refinement.validate_plan(plan_dir)
    manifest_path.write_text(original, encoding="utf-8")
    refinement.validate_plan(plan_dir)

    resigned = json.loads(original)
    rule_tamper(resigned)
    resigned["plan_signature"] = refinement._stable_sha256(
        refinement._manifest_signature_payload(resigned)
    )
    manifest_path.write_text(json.dumps(resigned), encoding="utf-8")
    with pytest.raises(ValueError, match="scientific contracts are not canonical"):
        refinement.validate_plan(plan_dir)


def test_candidate_requires_every_leave_one_seed_out_check() -> None:
    spec = refinement.CandidateSpec("op93_refine_test", 7.0, 81.0, "op_93", "execute")
    values = (0.84, 0.93, 0.93, 0.97, 0.97)
    rows = [
        _row(seed, value, value)
        for seed, value in zip(refinement.CALIBRATION_SEEDS, values, strict=True)
    ]

    summary = refinement._candidate_summary(spec, rows)

    assert summary["pooled_ratio_of_sums"]["system_on_due_service"] == pytest.approx(
        0.928
    )
    assert summary["individual_seed_metrics"]["system_on_due_service"][
        "median"
    ] == pytest.approx(0.93)
    assert summary["admissible_individually"] is False
    assert (
        "leave_one_seed_out_global_service_outside_outer_band"
        in summary["exclusion_reasons"]
    )


def test_candidate_passes_inner_outer_and_non_saturation_checks() -> None:
    spec = refinement.CandidateSpec("op93_refine_test", 7.0, 81.0, "op_93", "execute")
    values = (0.92, 0.925, 0.93, 0.935, 0.94)
    rows = [
        _row(seed, value, value)
        for seed, value in zip(refinement.CALIBRATION_SEEDS, values, strict=True)
    ]
    accepted = refinement._candidate_summary(spec, rows)
    saturated = refinement._candidate_summary(
        spec, [_row(seed, 0.90, 1.0) for seed in refinement.CALIBRATION_SEEDS]
    )

    assert accepted["admissible_individually"] is True
    assert accepted["maximum_absolute_global_target_error"] == pytest.approx(0.0025)
    assert saturated["admissible_individually"] is False
    assert "degraded_product_pooled_saturated" in saturated["exclusion_reasons"]


def test_pool_and_leave_one_out_are_quantity_weighted() -> None:
    spec = refinement.CandidateSpec("op93_refine_test", 7.0, 81.0, "op_93", "execute")
    values = (0.90, 0.93, 0.93, 0.93, 0.93)
    weights = (1.0, 1.0, 1.0, 1.0, 10.0)
    rows: list[dict[str, float | int]] = []
    for seed, value, weight in zip(
        refinement.CALIBRATION_SEEDS, values, weights, strict=True
    ):
        row = _row(seed, value, value)
        for field in (
            "on_due_qty_268091",
            "demand_qty_268091",
            "on_due_qty_268967",
            "demand_qty_268967",
        ):
            row[field] = float(row[field]) * weight
        rows.append(row)

    summary = refinement._candidate_summary(spec, rows)

    pooled = summary["pooled_ratio_of_sums"]["system_on_due_service"]
    assert pooled == pytest.approx((0.90 + 3.0 * 0.93 + 10.0 * 0.93) / 14.0)
    assert pooled != pytest.approx(sum(values) / len(values))
    assert summary["individual_seed_metrics"]["system_on_due_service"][
        "median"
    ] == pytest.approx(0.93)
    assert len(summary["leave_one_seed_out_ratio_of_sums"]) == 5
    assert summary["leave_one_seed_out_ratio_of_sums"]["340286"][
        "system_on_due_service"
    ] == pytest.approx(0.9225)
    assert summary["admissible_individually"] is True


def _fake_plan(
    tmp_path: Path, specs: tuple[refinement.CandidateSpec, ...]
) -> refinement.RefinementPlan:
    return refinement.RefinementPlan(
        plan_dir=tmp_path,
        manifest={
            "plan_signature": "test-plan",
            "selection_contract": {},
            "source_hashes": {},
            "cohorts": {
                "design": list(refinement.DESIGN_SEEDS),
                "calibration": list(refinement.CALIBRATION_SEEDS),
                "holdout_sealed": list(refinement.HOLDOUT_SEEDS),
            },
            "holdout_contract": {
                "status": "sealed_unread",
                "baseline_case_count": 90,
                "cases_in_this_plan": 0,
            },
        },
        source_plan=None,  # type: ignore[arg-type]
        specs=specs,
        inventory={
            spec.key: {"graph_path": f"{spec.key}.json", "graph_sha256": "test"}
            for spec in specs
        },
    )


def _selection_evidence(
    values: dict[str, list[tuple[float, float]]],
) -> dict[str, dict[str, float | int]]:
    evidence: dict[str, dict[str, float | int]] = {}
    for key, rows in values.items():
        for seed, (left, right) in zip(refinement.CALIBRATION_SEEDS, rows, strict=True):
            evidence[refinement._case_key(key, seed)] = _row(seed, left, right)
    return evidence


def test_joint_selection_uses_robust_error_then_iqr(tmp_path: Path) -> None:
    specs = (
        refinement.CandidateSpec("reference", 0.0, 0.0, "op_100", "reuse_v1"),
        refinement.CandidateSpec("high_variable", 7.0, 75.0, "op_93", "execute"),
        refinement.CandidateSpec("high_stable", 7.0, 81.0, "op_93", "execute"),
        refinement.CandidateSpec("low", 14.0, 96.0, "op_80", "reuse_v1"),
    )
    evidence = _selection_evidence(
        {
            "reference": [(1.0, 1.0)] * 5,
            "high_variable": [
                (value, value) for value in (0.92, 0.925, 0.93, 0.935, 0.94)
            ],
            "high_stable": [(0.9275, 0.9275)] * 5,
            "low": [(0.80, 0.80)] * 5,
        }
    )

    selection, selected = refinement._select(_fake_plan(tmp_path, specs), evidence)

    assert selection["status"] == "five_seed_loo_screen_passed_pending_holdout"
    assert selection["selected_pair"]["op93_candidate_key"] == "high_stable"
    assert selection["selected_pair"]["same_seed_joint_strict_order_count"] == 5
    assert selected is not None
    assert selected["status"] == (
        "selected_on_five_seed_refinement_pending_30_seed_holdout"
    )
    assert selected["holdout_validated"] is False
    assert selected["holdout_contract"]["baseline_case_count"] == 90
    assert selected["holdout_contract"]["cases_in_this_plan"] == 0
    assert selected["source_hashes"] == {}


def test_joint_selection_accepts_exactly_four_jointly_ordered_seeds(
    tmp_path: Path,
) -> None:
    specs = (
        refinement.CandidateSpec("reference", 0.0, 0.0, "op_100", "reuse_v1"),
        refinement.CandidateSpec("high", 7.0, 81.0, "op_93", "execute"),
        refinement.CandidateSpec("low", 17.0, 95.0, "op_80", "execute"),
    )
    fifth_right = (0.80 - 0.7 * 0.94) / 0.3
    evidence = _selection_evidence(
        {
            "reference": [(1.0, 1.0)] * 5,
            "high": [(0.93, 0.93)] * 5,
            "low": [(0.80, 0.80)] * 4 + [(0.94, fifth_right)],
        }
    )

    selection, selected = refinement._select(_fake_plan(tmp_path, specs), evidence)

    assert selection["status"] == "five_seed_loo_screen_passed_pending_holdout"
    assert selection["selected_pair"]["same_seed_joint_strict_order_count"] == 4
    assert selected is not None


def test_joint_selection_requires_four_same_seeds_ordered(tmp_path: Path) -> None:
    specs = (
        refinement.CandidateSpec("reference", 0.0, 0.0, "op_100", "reuse_v1"),
        refinement.CandidateSpec("high", 7.0, 81.0, "op_93", "execute"),
        refinement.CandidateSpec("low", 14.0, 96.0, "op_80", "reuse_v1"),
    )
    evidence = _selection_evidence(
        {
            "reference": [(1.0, 1.0)] * 5,
            "high": [(0.93, 0.93)] * 5,
            "low": [(0.95, 0.45)] * 2 + [(0.705, 1.0)] * 3,
        }
    )

    selection, selected = refinement._select(_fake_plan(tmp_path, specs), evidence)

    assert selection["status"] == "five_seed_loo_screen_failed_no_holdout"
    assert selection["eligible_pairs"] == []
    assert selected is None


def test_joint_selection_rejects_demand_mismatch_between_candidates(
    tmp_path: Path,
) -> None:
    specs = (
        refinement.CandidateSpec("reference", 0.0, 0.0, "op_100", "reuse_v1"),
        refinement.CandidateSpec("high", 7.0, 81.0, "op_93", "execute"),
        refinement.CandidateSpec("low", 17.0, 95.0, "op_80", "execute"),
    )
    evidence = _selection_evidence(
        {
            "reference": [(1.0, 1.0)] * 5,
            "high": [(0.93, 0.93)] * 5,
            "low": [(0.80, 0.80)] * 5,
        }
    )
    evidence[refinement._case_key("low", 340284)]["demand_qty_268091"] = 701.0

    with pytest.raises(ValueError, match="Demand mismatch across candidates"):
        refinement._select(_fake_plan(tmp_path, specs), evidence)


def test_run_resumes_and_never_executes_a_holdout_seed(tmp_path: Path) -> None:
    source_plan, source_run = _prepare_v1(tmp_path)
    plan_dir = tmp_path / "refinement_plan"
    run_dir = tmp_path / "refinement_run"
    refinement.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )
    calls: list[tuple[float, float, int]] = []

    def executor(
        candidate: coarse.Candidate,
        adapter: coarse.ValidatedPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        calls.append((candidate.offset_days_268091, candidate.offset_days_268967, seed))
        values = {
            (7.0, 75.0): (0.92, 0.94),
            (7.0, 81.0): (0.93, 0.93),
            (7.0, 86.0): (0.94, 0.92),
            (17.0, 95.0): (0.79, 0.82),
            (17.0, 94.0): (0.80, 0.80),
            (18.0, 94.0): (0.81, 0.78),
        }
        left, right = values[
            (candidate.offset_days_268091, candidate.offset_days_268967)
        ]
        return _raw_evidence(candidate, adapter, seed, left, right)

    first = refinement.run(plan_dir, run_dir, workers=2, executor=executor)
    first_calls = list(calls)
    second = refinement.run(plan_dir, run_dir, workers=2, executor=executor)

    assert first == second
    assert len(first_calls) == 30
    assert calls == first_calls
    assert {seed for _, _, seed in calls} == set(refinement.CALIBRATION_SEEDS)
    assert not ({seed for _, _, seed in calls} & set(refinement.HOLDOUT_SEEDS))
    assert first["selection"]["status"] == (
        "five_seed_loo_screen_passed_pending_holdout"
    )
    selected_path = run_dir / "selected_operating_points.json"
    assert selected_path.is_file()
    validated = refinement.validate_selected_operating_points(selected_path)
    assert validated["schema_version"] == refinement.POINTS_SCHEMA_VERSION
    assert validated["selection"]["schema_version"] == (
        refinement.SELECTION_SCHEMA_VERSION
    )
