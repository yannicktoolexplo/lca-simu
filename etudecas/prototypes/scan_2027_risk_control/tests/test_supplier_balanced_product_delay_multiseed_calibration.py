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
    supplier_balanced_product_delay_fine_prevalidation as previous,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_calibration as calibration,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_fine_prevalidation import (
    _executor,
    _source_points,
)


def _prepare_previous_run(
    tmp_path: Path,
    response: Any,
) -> tuple[Path, Path]:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "previous_plan"
    run_dir = tmp_path / "previous_run"
    previous.prepare_plan(plan_dir, source_points_path=source)
    previous.run(plan_dir, run_dir, executor=_executor(response, []))
    return plan_dir, run_dir


def test_plan_reclassifies_five_seeds_and_seals_fresh_holdout(
    tmp_path: Path,
) -> None:
    def response(point_id: str, _seed: int) -> tuple[float, float]:
        return {
            "op_100": (1.0, 1.0),
            "op_93": (0.945, 1.0),
            "op_80": (0.82, 0.69),
        }[point_id]

    source_plan, source_run = _prepare_previous_run(tmp_path, response)
    plan_dir = tmp_path / "multiseed_plan"
    calibration.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )
    plan = calibration.validate_plan(plan_dir)

    assert plan.manifest["cohorts"] == {
        "design": [340281],
        "calibration": [340282, 340283, 340284, 340285, 340286],
        "holdout_sealed": list(range(340287, 340317)),
    }
    assert plan.manifest["source"]["reclassification"] == (
        "calibration_after_single_seed_generalisation_failure"
    )
    assert plan.manifest["adaptive_decision"]["selected_branch"] == (
        "initial_low_state_too_low"
    )
    assert plan.manifest["new_case_count"] == 20
    assert plan.manifest["reused_case_count"] == 15
    assert {row["key"] for row in plan.manifest["candidates"]} == {
        "op100_reference",
        "op93_previous",
        "op80_initial",
        "op93_wave_7_90",
        "op93_wave_10_90",
        "op80_low_14_96",
        "op80_low_16_95",
    }
    assert plan.manifest["execution_contract"]["quality_incident"] is False
    assert plan.manifest["execution_contract"]["capacity_override"] is False
    assert plan.manifest["holdout_contract"]["baseline_case_count"] == 90
    assert plan.manifest["holdout_contract"][
        "same_seed_joint_strict_order_required"
    ] == 24


def test_adaptive_decision_is_covered_by_plan_signature(tmp_path: Path) -> None:
    def response(point_id: str, _seed: int) -> tuple[float, float]:
        return {
            "op_100": (1.0, 1.0),
            "op_93": (0.945, 1.0),
            "op_80": (0.82, 0.69),
        }[point_id]

    source_plan, source_run = _prepare_previous_run(tmp_path, response)
    plan_dir = tmp_path / "multiseed_plan"
    calibration.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )
    path = plan_dir / "calibration_plan.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["adaptive_decision"]["selected_branch"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="plan/signature"):
        calibration.validate_plan(plan_dir)


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


def test_candidate_requires_pooled_and_median_global_target() -> None:
    spec = calibration.CandidateSpec("candidate", 7.0, 90.0, "op_93", "execute")
    rows = [
        _row(340282, 0.88, 0.88),
        _row(340283, 0.88, 0.88),
        _row(340284, 0.88, 0.88),
        _row(340285, 0.99, 0.99),
        _row(340286, 0.99, 0.99),
    ]
    # Pooled service is 92.4%, but a typical (median) run is only 88%.
    summary = calibration._candidate_summary(spec, rows)

    assert summary["pooled_ratio_of_sums"]["system_on_due_service"] == pytest.approx(
        0.924
    )
    assert summary["individual_seed_metrics"]["system_on_due_service"][
        "median"
    ] == pytest.approx(0.88)
    assert summary["admissible_individually"] is False
    assert "median_global_service_outside_target_band" in summary["exclusion_reasons"]


def test_candidate_uses_ratio_of_sums_not_average_of_product_percentages() -> None:
    spec = calibration.CandidateSpec("candidate", 7.0, 90.0, "op_93", "execute")
    rows = [_row(seed, 0.90, 0.99) for seed in calibration.CALIBRATION_SEEDS]

    summary = calibration._candidate_summary(spec, rows)

    assert summary["pooled_ratio_of_sums"]["system_on_due_service"] == pytest.approx(
        0.927
    )
    assert summary["pooled_ratio_of_sums"]["system_on_due_service"] != pytest.approx(
        (0.90 + 0.99) / 2.0
    )


def test_low_branch_boundary_is_fixed_before_new_runs() -> None:
    evidence: dict[str, dict[str, float]] = {}
    for seed in calibration.CALIBRATION_SEEDS:
        evidence[previous._case_key("op_80", seed)] = _row(seed, 0.82, 0.69)

    branch, candidates, service = calibration._branch_from_initial(evidence)

    assert service == pytest.approx(0.781)
    assert branch == "initial_low_state_too_low"
    assert [candidate.key for candidate in candidates] == [
        "op80_low_14_96",
        "op80_low_16_95",
    ]


def _fake_plan(tmp_path: Path) -> calibration.CalibrationPlan:
    specs = (
        calibration.CandidateSpec("op100_reference", 0.0, 0.0, "op_100", "reuse"),
        calibration.CandidateSpec("high", 7.0, 90.0, "op_93", "execute"),
        calibration.CandidateSpec("low", 14.0, 96.0, "op_80", "execute"),
    )
    return calibration.CalibrationPlan(
        plan_dir=tmp_path,
        manifest={
            "plan_signature": "test-plan",
            "selection_contract": {},
            "execution_contract": {"fallback_if_no_selection": "axial"},
            "cohorts": {
                "design": [340281],
                "calibration": list(calibration.CALIBRATION_SEEDS),
                "holdout_sealed": list(calibration.HOLDOUT_SEEDS),
            },
            "source_hashes": {},
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
        for seed, (left, right) in zip(calibration.CALIBRATION_SEEDS, rows, strict=True):
            evidence[calibration._case_key(key, seed)] = _row(seed, left, right)
    return evidence


def test_selection_requires_same_four_seeds_ordered_for_both_products(
    tmp_path: Path,
) -> None:
    plan = _fake_plan(tmp_path)
    evidence = _selection_evidence(
        {
            "op100_reference": [(1.0, 1.0)] * 5,
            "high": [
                (0.795, 0.99),
                (0.99, 0.795),
                (0.94, 0.94),
                (0.94, 0.94),
                (0.94, 0.94),
            ],
            "low": [
                (0.805, 0.79),
                (0.79, 0.805),
                (0.79, 0.81),
                (0.79, 0.81),
                (0.79, 0.81),
            ],
        }
    )

    selection, selected = calibration._select(plan, evidence)

    assert selection["status"] == "target_not_attained"
    assert selected is None
    assert selection["eligible_pairs"] == []


def test_selection_accepts_only_jointly_simulated_non_saturated_states(
    tmp_path: Path,
) -> None:
    plan = _fake_plan(tmp_path)
    evidence = _selection_evidence(
        {
            "op100_reference": [(1.0, 1.0)] * 5,
            "high": [(0.92, 0.94)] * 5,
            "low": [(0.79, 0.82)] * 5,
        }
    )

    selection, selected = calibration._select(plan, evidence)

    assert selection["status"] == "calibration_selected"
    assert selected is not None
    assert selection["selected_pair"]["same_seed_joint_strict_order_count"] == 5
    assert [point["operating_point_id"] for point in selected["operating_points"]] == [
        "op_100",
        "op_93",
        "op_80",
    ]

    for seed in calibration.CALIBRATION_SEEDS:
        row = evidence[calibration._case_key("high", seed)]
        row.update(_row(seed, 0.92, 1.0))
    rejected, no_points = calibration._select(plan, evidence)
    high = next(
        row for row in rejected["candidate_summaries"] if row["key"] == "high"
    )
    assert high["admissible_individually"] is False
    assert "degraded_product_saturated" in high["exclusion_reasons"]
    assert no_points is None


def test_run_resumes_without_reexecuting_completed_candidates(
    tmp_path: Path,
) -> None:
    def previous_response(point_id: str, _seed: int) -> tuple[float, float]:
        return {
            "op_100": (1.0, 1.0),
            "op_93": (0.945, 1.0),
            "op_80": (0.82, 0.69),
        }[point_id]

    source_plan, source_run = _prepare_previous_run(tmp_path, previous_response)
    plan_dir = tmp_path / "multiseed_plan"
    output_dir = tmp_path / "multiseed_run"
    calibration.prepare_plan(
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
        calls.append(
            (candidate.offset_days_268091, candidate.offset_days_268967, seed)
        )
        values = {
            (7.0, 90.0): (0.92, 0.94),
            (10.0, 90.0): (0.89, 0.93),
            (14.0, 96.0): (0.79, 0.82),
            (16.0, 95.0): (0.75, 0.82),
        }
        left, right = values[
            (candidate.offset_days_268091, candidate.offset_days_268967)
        ]
        metrics = _row(seed, left, right)
        metrics.pop("seed")
        payload: dict[str, Any] = {
            "schema_version": coarse.EVIDENCE_SCHEMA_VERSION,
            **asdict(candidate),
            "seed": seed,
            "valid": True,
            "validation_errors": [],
            "status": "synthetic_test",
            "metrics": metrics,
            "graph_sha256": adapter.inventory[candidate.candidate_id][
                "graph_sha256"
            ],
            "summary_sha256": "summary",
            "service_daily_sha256": "service",
            "engine_sha256": coarse._sha256(adapter.engine),
            "command_sha256": "command",
            "run_dir": "synthetic",
            "created_at_utc": "2026-09-04T00:00:00+00:00",
        }
        payload["evidence_signature"] = coarse._stable_sha256(payload)
        return payload

    first = calibration.run(plan_dir, output_dir, workers=2, executor=executor)
    first_calls = list(calls)
    second = calibration.run(plan_dir, output_dir, workers=2, executor=executor)

    assert first == second
    assert len(first_calls) == 20
    assert calls == first_calls
    assert first["selection"]["status"] == "calibration_selected"
    assert (output_dir / "selected_operating_points.json").is_file()
