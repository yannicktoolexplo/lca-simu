from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as coarse,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_fine_calibration as fine,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_fine_prevalidation as prevalidation,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v2 as campaign_v2,
)
from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_fine_calibration import (
    _prepare_fine_plan,
    _signed_executor,
)


def _source_points(tmp_path: Path) -> Path:
    _coarse_plan, fine_plan = _prepare_fine_plan(tmp_path)

    def left(offset: float) -> float:
        return {0.0: 1.0, 7.0: 0.93, 15.0: 0.83, 16.0: 0.805}[offset]

    def right(offset: float) -> float:
        return {0.0: 1.0, 50.0: 0.96, 55.0: 0.94, 105.0: 0.80}[offset]

    fine.run_adaptive(
        fine_plan,
        tmp_path / "fine_run",
        executor=_signed_executor(left, right, []),
    )
    return tmp_path / "fine_run" / "campaign_operating_points.json"


def _executor(
    response: Callable[[str, int], tuple[float, float]],
    calls: list[tuple[str, int]],
    *,
    fail_once: tuple[str, int] | None = None,
) -> prevalidation.BaselineExecutor:
    failed = False

    def execute(
        point_id: str,
        point: dict[str, Any],
        plan: prevalidation.PrevalidationPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        nonlocal failed
        calls.append((point_id, seed))
        if fail_once == (point_id, seed) and not failed:
            failed = True
            raise RuntimeError("synthetic prevalidation interruption")
        candidate, adapter = prevalidation._adapter(point, plan)
        left, right = response(point_id, seed)
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
            "graph_sha256": adapter.inventory[candidate.candidate_id][
                "graph_sha256"
            ],
            "summary_sha256": "test-summary",
            "service_daily_sha256": "test-service",
            "engine_sha256": coarse._sha256(adapter.engine),
            "command_sha256": "test-command",
            "run_dir": "synthetic",
            "created_at_utc": "2026-09-04T00:00:00+00:00",
        }
        payload["evidence_signature"] = coarse._stable_sha256(payload)
        return payload

    return execute


def _passing_response(point_id: str, seed: int) -> tuple[float, float]:
    target = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}[point_id]
    index = prevalidation.CAMPAIGN_SEEDS.index(seed)
    deltas = (-0.01, -0.005, 0.0, 0.005, 0.01)
    if point_id == "op_100":
        values = (0.98, 0.99, 1.0, 1.0, 1.0)
        return values[index], values[4 - index]
    return target + deltas[index], target - deltas[index]


def test_plan_contains_exact_15_baselines_and_disjoint_seed_sets(
    tmp_path: Path,
) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"

    prevalidation.prepare_plan(plan_dir, source_points_path=source)
    plan = prevalidation.validate_plan(plan_dir)

    assert plan.manifest["expected_case_count"] == 15
    assert plan.manifest["seeds"] == [340282, 340283, 340284, 340285, 340286]
    assert plan.manifest["calibration_seed_excluded"] == 340281
    assert 340281 not in plan.manifest["seeds"]
    assert len({row["case_key"] for row in plan.manifest["cases"]}) == 15
    contract = plan.manifest["execution_contract"]
    assert contract["stage"] == "baseline_only"
    assert contract["quality_incident"] is False
    assert contract["supplier_availability_incident"] is False
    assert contract["acute_incident"] is False
    assert contract["acceptance_statistic"] == "pooled_global_ratio_of_sums"
    assert contract["pooled_state_order"] == "op_100 > op_93 > op_80"
    assert contract["per_seed_strict_state_order_required"] == 4


def test_run_resumes_and_exports_only_when_pooled_global_contract_passes(
    tmp_path: Path,
) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"
    output = tmp_path / "prevalidation_run"
    prevalidation.prepare_plan(plan_dir, source_points_path=source)
    calls: list[tuple[str, int]] = []
    executor = _executor(
        _passing_response,
        calls,
        fail_once=("op_93", 340284),
    )

    with pytest.raises(RuntimeError, match="synthetic prevalidation interruption"):
        prevalidation.run(plan_dir, output, executor=executor)
    calls_after_failure = list(calls)
    result = prevalidation.run(plan_dir, output, executor=executor)
    calls_after_completion = list(calls)
    repeated = prevalidation.run(plan_dir, output, executor=executor)

    assert result == repeated
    assert calls == calls_after_completion
    assert len(calls_after_failure) > len(set(calls_after_failure)) - 1
    assert set(seed for _point, seed in calls) == set(prevalidation.CAMPAIGN_SEEDS)
    assert all(seed != fine.DEFAULT_SEED for _point, seed in calls)
    summary = result["summary"]
    assert summary["all_targets_attained"] is True
    assert summary["case_count"] == 15
    op93 = next(
        row for row in summary["state_records"] if row["operating_point_id"] == "op_93"
    )
    assert op93["metrics"]["on_due_service_268091"] == {
        "mean": pytest.approx(0.93),
        "median": 0.93,
        "p10": pytest.approx(0.922),
        "p90": pytest.approx(0.938),
        "q1": 0.925,
        "q3": 0.935,
        "iqr": pytest.approx(0.01),
        "minimum": 0.92,
        "maximum": 0.9400000000000001,
        "range": pytest.approx(0.02),
    }
    assert op93["pooled_ratio_of_sums"]["system_on_due_service"] == pytest.approx(
        0.93
    )
    assert summary["acceptance_statistic"] == "pooled_global_ratio_of_sums"
    assert summary["per_seed_strict_state_order_count"] == 5
    validated = output / "validated_campaign_operating_points.json"
    assert validated.is_file()
    assert not (output / "observed_operating_points.json").exists()
    assert [
        point["operating_point_id"]
        for point in campaign_v2.load_operating_points(
            validated, require_prevalidated=False
        )
    ] == list(prevalidation.POINT_IDS)


def test_failed_pooled_contract_is_renamed_with_both_product_services(
    tmp_path: Path,
) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"
    output = tmp_path / "prevalidation_run"
    prevalidation.prepare_plan(plan_dir, source_points_path=source)

    def response(point_id: str, seed: int) -> tuple[float, float]:
        if point_id == "op_80":
            return 0.92, 0.80
        return _passing_response(point_id, seed)

    result = prevalidation.run(
        plan_dir,
        output,
        executor=_executor(response, []),
    )

    assert result["validated_campaign_operating_points"] is None
    assert not (output / "validated_campaign_operating_points.json").exists()
    observed_path = output / "observed_operating_points.json"
    assert observed_path.is_file()
    observed = result["observed_operating_points"]
    failed = next(
        point
        for point in observed["operating_points"]
        if point["target_service"] == 0.80
    )
    assert (
        failed["operating_point_id"]
        == "op_observed_pf268091_92p0pct__pf268967_80p0pct"
    )
    assert failed["prevalidation_target_attained"] is False
    assert observed["strict_v2_campaign_compatible"] is False
    with pytest.raises(ValueError, match="five-seed multi-seed"):
        campaign_v2.load_operating_points(observed_path)


def test_low_state_fallback_keeps_configuration_and_publishes_observed_label(
    tmp_path: Path,
) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"
    output = tmp_path / "prevalidation_run"
    prevalidation.prepare_plan(plan_dir, source_points_path=source)

    def response(point_id: str, seed: int) -> tuple[float, float]:
        if point_id == "op_80":
            return 0.84, 0.80
        return _passing_response(point_id, seed)

    result = prevalidation.run(
        plan_dir,
        output,
        executor=_executor(response, []),
    )

    summary = result["summary"]
    assert summary["all_targets_attained"] is False
    assert summary["all_campaign_states_accepted"] is True
    assert summary["fallback_low_state_used"] is True
    assert (
        summary["status"]
        == "prevalidated_3_states_with_observed_low_state_5_seeds"
    )
    validated = result["validated_campaign_operating_points"]
    assert validated is not None
    low = next(
        point for point in validated["operating_points"] if point["operating_point_id"] == "op_80"
    )
    assert low["original_target_service"] == 0.80
    assert low["target_service"] == pytest.approx(0.82)
    assert "82.0%" in low["operating_point_label"]
    assert low["prevalidation_target_attained"] is False
    assert low["prevalidation_state_accepted"] is True


def test_pooled_ratio_rejects_two_bad_runs_hidden_by_the_median(
    tmp_path: Path,
) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"
    output = tmp_path / "prevalidation_run"
    prevalidation.prepare_plan(plan_dir, source_points_path=source)

    def response(point_id: str, seed: int) -> tuple[float, float]:
        if point_id != "op_80":
            return _passing_response(point_id, seed)
        index = prevalidation.CAMPAIGN_SEEDS.index(seed)
        service = (0.80, 0.80, 0.80, 0.20, 0.20)[index]
        return service, service

    result = prevalidation.run(
        plan_dir,
        output,
        executor=_executor(response, []),
    )

    op80 = next(
        row
        for row in result["summary"]["state_records"]
        if row["operating_point_id"] == "op_80"
    )
    assert op80["metrics"]["system_on_due_service"]["median"] == 0.80
    assert op80["pooled_ratio_of_sums"]["system_on_due_service"] == pytest.approx(
        0.56
    )
    assert op80["target_attained"] is False
    assert result["validated_campaign_operating_points"] is None


def test_global_target_reports_product_gap_without_relabeling_state(
    tmp_path: Path,
) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"
    output = tmp_path / "prevalidation_run"
    prevalidation.prepare_plan(plan_dir, source_points_path=source)

    def response(point_id: str, seed: int) -> tuple[float, float]:
        if point_id == "op_80":
            return 0.83, 0.77
        return _passing_response(point_id, seed)

    result = prevalidation.run(
        plan_dir,
        output,
        executor=_executor(response, []),
    )
    op80 = next(
        row
        for row in result["summary"]["state_records"]
        if row["operating_point_id"] == "op_80"
    )

    assert op80["pooled_ratio_of_sums"]["system_on_due_service"] == pytest.approx(
        0.80
    )
    assert op80["products_balanced_within_5pp"] is False
    assert op80["target_attained"] is True
    assert result["validated_campaign_operating_points"] is not None


def test_inconsistent_service_quantities_are_rejected() -> None:
    payload = {
        "metrics": {
            "on_due_qty_268091": 101.0,
            "demand_qty_268091": 100.0,
            "on_due_qty_268967": 80.0,
            "demand_qty_268967": 100.0,
            "on_due_service_268091": 1.0,
            "on_due_service_268967": 0.8,
            "system_on_due_service": 0.9,
            "minimum_product_on_due_service": 0.8,
        }
    }

    with pytest.raises(ValueError, match="cannot exceed"):
        prevalidation._validate_service_quantities(payload)


def test_run_supports_two_bounded_workers(tmp_path: Path) -> None:
    source = _source_points(tmp_path)
    plan_dir = tmp_path / "prevalidation_plan"
    output = tmp_path / "prevalidation_run_parallel"
    prevalidation.prepare_plan(plan_dir, source_points_path=source)
    calls: list[tuple[str, int]] = []

    result = prevalidation.run(
        plan_dir,
        output,
        workers=2,
        executor=_executor(_passing_response, calls),
    )

    assert result["summary"]["case_count"] == 15
    assert len(calls) == 15
    assert (output / "validated_campaign_operating_points.json").is_file()
    with pytest.raises(ValueError, match="one or two workers"):
        prevalidation.run(
            plan_dir,
            tmp_path / "invalid_workers",
            workers=3,
            executor=_executor(_passing_response, []),
        )
