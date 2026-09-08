from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
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
    supplier_operating_point_full_campaign_v2 as campaign_v2,
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture_sources(tmp_path: Path) -> dict[str, Path]:
    graph_path = tmp_path / "source_graph.json"
    _write_json(
        graph_path,
        {
            "edges": [
                {
                    "id": "edge:left",
                    "from": "SUP-A",
                    "to": "M-1810",
                    "items": ["item:A"],
                    "lead_time": {"mean": 10.0},
                    "delay_step_limit": {"value": 20},
                    "service_level": {"otif": 1.0},
                },
                {
                    "id": "edge:right",
                    "from": "SUP-B",
                    "to": "M-1430",
                    "items": ["item:B"],
                    "lead_time": {"mean": 20.0},
                    "delay_step_limit": {"value": 40},
                    "service_level": {"otif": 1.0},
                },
            ],
            "nodes": [],
            "scenarios": [],
        },
    )
    lanes_path = tmp_path / "active_lanes.csv"
    fields = (
        "chain_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
    )
    with lanes_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "chain_id": "left",
                    "supplier_id": "SUP-A",
                    "item_id": "item:A",
                    "dst_node_id": "M-1810",
                    "edge_id": "edge:left",
                    "target_product_id": "268091",
                },
                {
                    "chain_id": "right",
                    "supplier_id": "SUP-B",
                    "item_id": "item:B",
                    "dst_node_id": "M-1430",
                    "edge_id": "edge:right",
                    "target_product_id": "268967",
                },
            ]
        )
    engine_path = tmp_path / "engine.py"
    engine_path.write_text("# test engine identity\n", encoding="utf-8")
    profile_path = tmp_path / "profile.json"
    _write_json(profile_path, {"args": []})
    return {
        "graph": graph_path,
        "lanes": lanes_path,
        "engine": engine_path,
        "profile": profile_path,
    }


def _prepare_fine_plan(tmp_path: Path) -> tuple[Path, Path]:
    sources = _fixture_sources(tmp_path)
    coarse_plan = tmp_path / "coarse_plan"
    coarse.prepare_plan(
        coarse_plan,
        active_lanes_path=sources["lanes"],
        graph_path=sources["graph"],
        engine_path=sources["engine"],
        profile_path=sources["profile"],
        offsets_268091=(0.0, 7.0),
        offsets_268967=(0.0, 45.0),
    )
    fine_plan = tmp_path / "fine_plan"
    fine.prepare_plan(
        fine_plan,
        coarse_plan_dir=coarse_plan,
        coarse_run_dir=None,
    )
    return coarse_plan, fine_plan


def _axis_payload(
    *,
    left: float = 0.0,
    right: float = 0.0,
    left_service: float = 1.0,
    right_service: float = 1.0,
) -> dict[str, Any]:
    return {
        "offset_days_268091": left,
        "offset_days_268967": right,
        "metrics": {
            "on_due_service_268091": left_service,
            "on_due_service_268967": right_service,
            "system_on_due_service": (left_service + right_service) / 2.0,
            "minimum_product_on_due_service": min(left_service, right_service),
        },
    }


def _joint_payload(
    *,
    left_service: float,
    right_service: float,
    left_demand: float,
    right_demand: float,
) -> dict[str, Any]:
    left_on_due = left_service * left_demand
    right_on_due = right_service * right_demand
    return {
        "metrics": {
            "system_on_due_service": (left_on_due + right_on_due)
            / (left_demand + right_demand),
            "on_due_service_268091": left_service,
            "on_due_service_268967": right_service,
            "minimum_product_on_due_service": min(left_service, right_service),
            "on_due_qty_268091": left_on_due,
            "demand_qty_268091": left_demand,
            "on_due_qty_268967": right_on_due,
            "demand_qty_268967": right_demand,
        },
        "evidence_signature": "synthetic-joint-evidence",
    }


def _signed_executor(
    service_left: Callable[[float], float],
    service_right: Callable[[float], float],
    calls: list[str],
    *,
    fail_once_candidate: str = "",
) -> fine.RawExecutor:
    failed = False

    def execute(
        candidate: coarse.Candidate,
        plan: coarse.ValidatedPlan,
        _output_dir: Path,
        seed: int,
    ) -> dict[str, Any]:
        nonlocal failed
        calls.append(candidate.candidate_id)
        if candidate.candidate_id == fail_once_candidate and not failed:
            failed = True
            raise RuntimeError("synthetic interruption")
        left = service_left(candidate.offset_days_268091)
        right = service_right(candidate.offset_days_268967)
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
            "graph_sha256": plan.inventory[candidate.candidate_id]["graph_sha256"],
            "summary_sha256": "test-summary",
            "service_daily_sha256": "test-service",
            "engine_sha256": coarse._sha256(plan.engine),
            "command_sha256": "test-command",
            "run_dir": "synthetic",
            "created_at_utc": "2026-09-04T00:00:00+00:00",
        }
        payload["evidence_signature"] = coarse._stable_sha256(payload)
        return payload

    return execute


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_plan_is_explicit_non_cartesian_and_does_not_mutate_coarse(
    tmp_path: Path,
) -> None:
    coarse_plan, fine_plan = _prepare_fine_plan(tmp_path)
    before = _tree_hashes(coarse_plan)
    plan = fine.validate_plan(fine_plan)

    assert _tree_hashes(coarse_plan) == before
    assert plan.manifest["explicit_candidate_pair_count"] == 70
    pairs = plan.manifest["explicit_candidate_pairs"]
    assert len({row["candidate_id"] for row in pairs}) == 70
    assert all(
        not (
            float(row["offset_days_268091"]) > 0
            and float(row["offset_days_268967"]) > 0
        )
        for row in pairs
    )
    axis = next(axis for axis in fine.AXES if axis.search_id == "pf268091_target_80")
    assert axis.initial_offset_days == 15.0
    assert axis.mode == "explicit_nonmonotone_local_search"
    assert plan.manifest["execution_contract"]["interpolation_used"] is False
    assert plan.manifest["execution_contract"]["service_evaluation_window"] == {
        "start_day": 0,
        "end_day": 719,
        "day_count": 720,
    }


def test_pf268091_tests_15_first_and_always_tests_16_after_a_miss() -> None:
    axis = next(axis for axis in fine.AXES if axis.search_id == "pf268091_target_80")
    assert fine.decide_axis(axis, {})["next_offset_days"] == 15.0

    high = {"15": _axis_payload(left=15.0, left_service=0.83)}
    assert fine.decide_axis(axis, high)["next_offset_days"] == 16.0

    attained = {"15": _axis_payload(left=15.0, left_service=0.805)}
    decision = fine.decide_axis(axis, attained)
    assert decision["status"] == "within_tolerance"
    assert decision["selected_offset_days"] == 15.0

    low = {"15": _axis_payload(left=15.0, left_service=0.77)}
    decision = fine.decide_axis(axis, low)
    assert decision["next_offset_days"] == 16.0
    assert 16.0 in decision["scheduled_offsets_days"]


def test_pf268091_reports_nonmonotonicity_and_nearest_observed_service() -> None:
    axis = next(axis for axis in fine.AXES if axis.search_id == "pf268091_target_80")
    services = {float(day): 0.84 for day in range(10, 31)}
    services[14.0] = 0.8236
    services[20.0] = 0.82
    services[22.0] = 0.8381
    evidence = {
        str(day): _axis_payload(left=day, left_service=service)
        for day, service in services.items()
    }

    decision = fine.decide_axis(axis, evidence)

    assert decision["status"] == "target_not_attained_after_local_search"
    assert decision["selected_offset_days"] == 20.0
    assert decision["selected_service"] == 0.82
    assert decision["target_attained"] is False
    assert decision["interpolation_used"] is False
    assert decision["non_monotone_response_observed"] is True


def test_pf268091_completes_10_to_22_before_outer_probe_30() -> None:
    axis = next(axis for axis in fine.AXES if axis.search_id == "pf268091_target_80")
    offsets = (10.0, 12.0, 13.0, 14.0, 15.0, 16.0, 22.0)
    evidence = {
        str(offset): _axis_payload(left=offset, left_service=0.84)
        for offset in offsets
    }
    assert fine.decide_axis(axis, evidence)["next_offset_days"] == 11.0
    for offset in fine.PF268091_80_COMPLETION:
        evidence[str(offset)] = _axis_payload(left=offset, left_service=0.84)
    assert fine.decide_axis(axis, evidence)["next_offset_days"] == 30.0


def test_pf268967_uses_explicit_wave_then_integer_neighbors() -> None:
    axis = next(axis for axis in fine.AXES if axis.search_id == "pf268967_target_93")
    evidence: dict[str, dict[str, Any]] = {}
    for offset, service in ((50.0, 0.97), (55.0, 0.96), (58.0, 0.955)):
        decision = fine.decide_axis(axis, evidence)
        assert decision["next_offset_days"] == offset
        evidence[str(offset)] = _axis_payload(right=offset, right_service=service)
    assert fine.decide_axis(axis, evidence)["next_offset_days"] == 57.0
    evidence["57"] = _axis_payload(right=57.0, right_service=0.945)

    decision = fine.decide_axis(axis, evidence)
    assert decision["status"] == "within_tolerance"
    assert decision["selected_offset_days"] == 57.0
    assert decision["selected_service"] == 0.945


def test_joint_contract_uses_demand_weighted_global_service() -> None:
    op93 = coarse.Candidate(coarse._candidate_id(7.0, 60.0), 7.0, 60.0)
    op80 = coarse.Candidate(coarse._candidate_id(16.0, 97.0), 16.0, 97.0)
    rows = fine._joint_records(
        {"op_93": op93, "op_80": op80},
        {
            op93.candidate_id: _joint_payload(
                left_service=0.94,
                right_service=0.90,
                left_demand=9.0,
                right_demand=1.0,
            ),
            op80.candidate_id: _joint_payload(
                left_service=0.81,
                right_service=0.79,
                left_demand=1.0,
                right_demand=1.0,
            ),
        },
    )

    first = rows[0]
    assert first["system_on_due_service"] == pytest.approx(0.936)
    assert first["product_service_gap_pp"] == pytest.approx(4.0)
    assert first["within_operating_point_contract"] is True


def test_joint_contract_rejects_product_gap_and_saturation() -> None:
    op93 = coarse.Candidate(coarse._candidate_id(7.0, 60.0), 7.0, 60.0)
    op80 = coarse.Candidate(coarse._candidate_id(16.0, 97.0), 16.0, 97.0)
    rows = fine._joint_records(
        {"op_93": op93, "op_80": op80},
        {
            op93.candidate_id: _joint_payload(
                left_service=1.0,
                right_service=0.93,
                left_demand=0.01,
                right_demand=1.0,
            ),
            op80.candidate_id: _joint_payload(
                left_service=0.80,
                right_service=0.80,
                left_demand=1.0,
                right_demand=1.0,
            ),
        },
    )

    first = rows[0]
    assert first["global_target_within_tolerance"] is True
    assert first["products_balanced_within_5pp"] is False
    assert first["no_degraded_product_saturated_at_100pct"] is False
    assert first["within_operating_point_contract"] is False


def test_fine_run_refuses_to_compete_with_active_coarse_engine(
    tmp_path: Path,
) -> None:
    coarse_plan, _unused_fine_plan = _prepare_fine_plan(tmp_path)
    coarse_validated = coarse.validate_plan(coarse_plan)
    coarse_run = tmp_path / "coarse_run"
    _write_json(
        coarse_run / "run_manifest.json",
        {
            "plan_signature": coarse_validated.manifest["plan_signature"],
            "seed": fine.DEFAULT_SEED,
        },
    )
    (coarse_run / ".balanced_delay_calibration.lock").write_text(
        "active", encoding="utf-8"
    )
    fine_plan = tmp_path / "fine_plan_with_active_coarse"
    fine.prepare_plan(
        fine_plan,
        coarse_plan_dir=coarse_plan,
        coarse_run_dir=coarse_run,
    )

    with pytest.raises(RuntimeError, match="still active"):
        fine.run_adaptive(
            fine_plan,
            tmp_path / "must_not_exist",
            executor=lambda *_args: pytest.fail("executor must not be called"),
        )
    assert not (tmp_path / "must_not_exist").exists()


def test_run_is_resumable_and_exports_downstream_compatible_points(
    tmp_path: Path,
) -> None:
    coarse_plan, fine_plan = _prepare_fine_plan(tmp_path)
    before = _tree_hashes(coarse_plan)
    output = tmp_path / "fine_run"
    calls: list[str] = []

    def left(offset: float) -> float:
        return {0.0: 1.0, 7.0: 0.93, 15.0: 0.83, 16.0: 0.805}[offset]

    def right(offset: float) -> float:
        return {0.0: 1.0, 50.0: 0.96, 55.0: 0.94, 105.0: 0.80}[offset]

    fail_id = coarse._candidate_id(16.0, 0.0)
    executor = _signed_executor(left, right, calls, fail_once_candidate=fail_id)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        fine.run_adaptive(fine_plan, output, executor=executor)
    counts_after_failure = Counter(calls)
    assert json.loads((output / "progress.json").read_text())["status"] == "interrupted"

    result = fine.run_adaptive(fine_plan, output, executor=executor)
    calls_after_completion = list(calls)
    repeated = fine.run_adaptive(fine_plan, output, executor=executor)

    assert result == repeated
    assert calls == calls_after_completion
    assert counts_after_failure[coarse._candidate_id(0.0, 0.0)] == 1
    assert Counter(calls)[coarse._candidate_id(0.0, 0.0)] == 1
    assert result["campaign_operating_points"] is not None
    loaded = campaign_v2.load_operating_points(
        output / "campaign_operating_points.json",
        require_prevalidated=False,
    )
    assert [row["operating_point_id"] for row in loaded] == [
        "op_100",
        "op_93",
        "op_80",
    ]
    assert loaded[1]["offset_days_268091"] == 7.0
    assert loaded[1]["offset_days_268967"] == 55.0
    assert loaded[2]["offset_days_268091"] == 16.0
    assert loaded[2]["offset_days_268967"] == 105.0
    assert _tree_hashes(coarse_plan) == before


def test_product_axis_miss_can_export_an_observed_balanced_global_state(
    tmp_path: Path,
) -> None:
    _coarse_plan, fine_plan = _prepare_fine_plan(tmp_path)
    output = tmp_path / "fine_run"
    calls: list[str] = []

    def left(offset: float) -> float:
        if offset == 0.0:
            return 1.0
        if offset == 7.0:
            return 0.93
        if offset == 14.0:
            return 0.8236
        if offset == 20.0:
            return 0.82
        if offset == 22.0:
            return 0.8381
        return 0.84

    def right(offset: float) -> float:
        return {0.0: 1.0, 50.0: 0.93, 105.0: 0.80}[offset]

    result = fine.run_adaptive(
        fine_plan,
        output,
        executor=_signed_executor(left, right, calls),
    )

    assert result["campaign_operating_points"] is not None
    assert (output / "campaign_operating_points.json").is_file()
    selection = result["selection"]
    assert (
        selection["status"]
        == "joint_global_targets_attained_product_gap_reported"
    )
    failed = next(
        row
        for row in selection["axis_records"]
        if row["search_id"] == "pf268091_target_80"
    )
    assert failed["selected_service"] == 0.82
    assert failed["target_attained"] is False
    assert failed["non_monotone_response_observed"] is True
    assert coarse._candidate_id(16.0, 0.0) in calls


def test_no_false_global_op80_is_exported_when_balanced_contract_misses(
    tmp_path: Path,
) -> None:
    _coarse_plan, fine_plan = _prepare_fine_plan(tmp_path)
    output = tmp_path / "fine_run"
    calls: list[str] = []

    def left(offset: float) -> float:
        if offset == 0.0:
            return 1.0
        if offset == 7.0:
            return 0.93
        return 0.86

    def right(offset: float) -> float:
        return {0.0: 1.0, 50.0: 0.93, 105.0: 0.80}[offset]

    result = fine.run_adaptive(
        fine_plan,
        output,
        executor=_signed_executor(left, right, calls),
    )

    assert result["campaign_operating_points"] is None
    assert not (output / "campaign_operating_points.json").exists()
    selection = result["selection"]
    assert (
        selection["status"]
        == "global_balanced_target_not_attained_no_campaign_export"
    )
    op80 = next(
        row
        for row in selection["joint_records"]
        if row["operating_point_id"] == "op_80"
    )
    assert op80["global_target_within_tolerance"] is False
    assert op80["within_operating_point_contract"] is False
