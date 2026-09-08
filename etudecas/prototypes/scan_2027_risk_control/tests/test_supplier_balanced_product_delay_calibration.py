from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_calibration as calibration,
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture_sources(tmp_path: Path) -> dict[str, Path]:
    graph_path = tmp_path / "source_graph.json"
    graph = {
        "edges": [
            {
                "id": "edge:left_a",
                "from": "SUP-A",
                "to": "M-1810",
                "items": ["item:A"],
                "lead_time": {"mean": 10.0},
                "delay_step_limit": {"value": 20},
                "service_level": {"otif": 1.0},
            },
            {
                "id": "edge:left_b",
                "from": "SUP-B",
                "to": "M-1810",
                "items": ["item:B"],
                "lead_time": {"mean": 20.0},
                "delay_step_limit": {"value": 40},
                "service_level": {"otif": 1.0},
            },
            {
                "id": "edge:right_a",
                "from": "SUP-C",
                "to": "M-1430",
                "items": ["item:C"],
                "lead_time": {"mean": 30.0},
                "delay_step_limit": {"value": 60},
                "service_level": {"otif": 1.0},
            },
            {
                "id": "edge:unrelated",
                "from": "OTHER",
                "to": "OTHER-DST",
                "items": ["item:OTHER"],
                "lead_time": {"mean": 5.0},
                "delay_step_limit": {"value": 10},
                "service_level": {"otif": 0.8},
            },
        ],
        "nodes": [],
        "scenarios": [],
    }
    _write_json(graph_path, graph)
    lanes_path = tmp_path / "active_lanes.csv"
    fields = (
        "chain_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
    )
    rows = [
        {
            "chain_id": "left_a",
            "supplier_id": "SUP-A",
            "item_id": "item:A",
            "dst_node_id": "M-1810",
            "edge_id": "edge:left_a",
            "target_product_id": "268091",
        },
        {
            "chain_id": "left_b",
            "supplier_id": "SUP-B",
            "item_id": "item:B",
            "dst_node_id": "M-1810",
            "edge_id": "edge:left_b",
            "target_product_id": "268091",
        },
        {
            "chain_id": "right_a",
            "supplier_id": "SUP-C",
            "item_id": "item:C",
            "dst_node_id": "M-1430",
            "edge_id": "edge:right_a",
            "target_product_id": "268967",
        },
    ]
    with lanes_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
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


def _prepare_test_plan(tmp_path: Path, offsets: tuple[float, ...] = (0.0, 10.0)) -> Path:
    sources = _fixture_sources(tmp_path)
    plan_dir = tmp_path / "plan"
    calibration.prepare_plan(
        plan_dir,
        active_lanes_path=sources["lanes"],
        graph_path=sources["graph"],
        engine_path=sources["engine"],
        profile_path=sources["profile"],
        offsets_268091=offsets,
        offsets_268967=offsets,
    )
    return plan_dir


def _evidence(
    candidate: calibration.Candidate,
    plan: calibration.ValidatedPlan,
    seed: int,
) -> dict[str, Any]:
    service_left = {0.0: 1.0, 10.0: 0.932, 20.0: 0.802}[
        candidate.offset_days_268091
    ]
    service_right = {0.0: 1.0, 10.0: 0.928, 20.0: 0.798}[
        candidate.offset_days_268967
    ]
    metrics = {
        "system_on_due_service": (service_left + service_right) / 2.0,
        "on_due_service_268091": service_left,
        "on_due_service_268967": service_right,
        "minimum_product_on_due_service": min(service_left, service_right),
        "demand_qty_268091": 100.0,
        "demand_qty_268967": 100.0,
    }
    payload: dict[str, Any] = {
        "schema_version": calibration.EVIDENCE_SCHEMA_VERSION,
        **asdict(candidate),
        "seed": seed,
        "valid": True,
        "validation_errors": [],
        "status": "synthetic_test",
        "metrics": metrics,
        "graph_sha256": plan.inventory[candidate.candidate_id]["graph_sha256"],
        "summary_sha256": "test-summary",
        "service_daily_sha256": "test-service",
        "engine_sha256": calibration._sha256(plan.engine),
        "command_sha256": "test-command",
        "run_dir": "synthetic",
        "created_at_utc": "2026-09-04T00:00:00+00:00",
    }
    payload["evidence_signature"] = calibration._stable_sha256(payload)
    return payload


def test_plan_cli_default_targets_remain_93_then_80(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_prepare(output_dir: Path, **kwargs: Any) -> Path:
        captured["output_dir"] = output_dir
        captured.update(kwargs)
        return output_dir

    monkeypatch.setattr(calibration, "prepare_plan", fake_prepare)
    output = tmp_path / "no_simulation_plan"

    assert calibration.main(["--mode", "plan", "--plan-dir", str(output)]) == 0
    assert captured["targets"] == (0.93, 0.80)


def test_real_scope_has_actual_11_and_7_lanes() -> None:
    groups = calibration.load_lane_scope(calibration.DEFAULT_ACTIVE_LANES)
    assert {product: len(rows) for product, rows in groups.items()} == {
        "268091": 11,
        "268967": 7,
    }
    graph = calibration._read_json(calibration.protocol.DEFAULT_GRAPH)
    calibration.validate_lanes_against_graph(graph, groups)


def test_apply_product_delays_changes_only_scoped_edges(tmp_path: Path) -> None:
    sources = _fixture_sources(tmp_path)
    source = calibration._read_json(sources["graph"])
    original = json.loads(json.dumps(source))
    groups = calibration.load_lane_scope(sources["lanes"])

    changed, ledger = calibration.apply_product_delays(
        source,
        groups,
        offset_days_268091=3.0,
        offset_days_268967=7.0,
    )

    assert source == original
    edges = calibration._edge_index(changed)
    assert edges["edge:left_a"]["lead_time"]["mean"] == 13.0
    assert edges["edge:left_a"]["delay_step_limit"]["value"] == 26
    assert edges["edge:left_b"]["lead_time"]["mean"] == 23.0
    assert edges["edge:right_a"]["lead_time"]["mean"] == 37.0
    assert edges["edge:unrelated"] == calibration._edge_index(source)["edge:unrelated"]
    assert len(ledger) == 3
    assert {row["offset_days"] for row in ledger if row["target_product_id"] == "268091"} == {3.0}
    assert {row["offset_days"] for row in ledger if row["target_product_id"] == "268967"} == {7.0}


def test_plan_is_signed_dynamic_and_contains_no_forbidden_inputs(tmp_path: Path) -> None:
    plan_dir = _prepare_test_plan(tmp_path)
    plan = calibration.validate_plan(plan_dir)

    assert len(plan.candidates) == 4
    assert plan.manifest["lane_counts_by_product"] == {"268091": 2, "268967": 1}
    assert plan.manifest["excluded_degradation_dimensions"] == [
        "supplier_capacity",
        "factory_capacity",
        "supplier_availability",
        "quality_hold",
        "quality_yield",
        "acute_incident",
        "state_dependent_risk",
    ]
    candidate = next(item for item in plan.candidates if item.offset_days_268091 == 10.0)
    command = calibration.build_engine_command(candidate, plan, tmp_path / "case", 123)
    assert not calibration.FORBIDDEN_ENGINE_FLAGS.intersection(command)
    assert "--no-supplier-state-dependent-risks" in command
    assert "--common-random-numbers" in command

    with pytest.raises(FileExistsError):
        calibration.prepare_plan(plan_dir)


def test_selection_hits_both_products_and_enforces_more_severe_80_point() -> None:
    candidates = calibration.build_candidates((0.0, 10.0, 20.0), (0.0, 10.0, 20.0))
    rows = []
    for candidate in candidates:
        left = {0.0: 1.0, 10.0: 0.932, 20.0: 0.802}[
            candidate.offset_days_268091
        ]
        right = {0.0: 1.0, 10.0: 0.928, 20.0: 0.798}[
            candidate.offset_days_268967
        ]
        rows.append(
            {
                **asdict(candidate),
                "valid": True,
                "system_on_due_service": (left + right) / 2.0,
                "on_due_service_268091": left,
                "on_due_service_268967": right,
            }
        )

    selection = calibration.select_balanced_targets(rows, candidates=candidates)

    assert selection["all_targets_attained"] is True
    target_93, target_80 = selection["records"]
    assert (target_93["offset_days_268091"], target_93["offset_days_268967"]) == (
        10.0,
        10.0,
    )
    assert (target_80["offset_days_268091"], target_80["offset_days_268967"]) == (
        20.0,
        20.0,
    )
    assert target_80["offset_days_268091"] >= target_93["offset_days_268091"]
    assert target_80["offset_days_268967"] >= target_93["offset_days_268967"]


def test_run_grid_is_resumable_with_injected_short_executor(tmp_path: Path) -> None:
    plan_dir = _prepare_test_plan(tmp_path, offsets=(0.0, 10.0, 20.0))
    output_dir = tmp_path / "results"
    calls: list[str] = []

    def fake_executor(
        candidate: calibration.Candidate,
        plan: calibration.ValidatedPlan,
        _output: Path,
        seed: int,
    ) -> dict[str, Any]:
        calls.append(candidate.candidate_id)
        return _evidence(candidate, plan, seed)

    first = calibration.run_grid(
        plan_dir,
        output_dir,
        workers=2,
        executor=fake_executor,
    )
    assert first["all_targets_attained"] is True
    assert len(calls) == 9
    assert calibration._read_json(output_dir / "progress.json")["status"] == "complete"
    campaign_points_path = output_dir / "campaign_operating_points.json"
    campaign_points = calibration._read_json(campaign_points_path)
    assert campaign_points["quality_branch_included"] is False
    assert campaign_points["supplier_state_dependent_risks_enabled"] is False
    assert campaign_points["supplier_capacity_override_included"] is False
    assert [
        point["operating_point_id"] for point in campaign_points["operating_points"]
    ] == ["op_100", "op_93", "op_80"]
    for point in campaign_points["operating_points"]:
        assert point["degradation_family"] == (
            "balanced_product_supplier_planned_lead"
        )
        assert Path(point["graph"]).is_absolute()
        assert calibration._sha256(Path(point["graph"])) == point["graph_sha256"]
        assert point["supplier_floors"] == ""
        assert point["supplier_floors_sha256"] == ""
        assert point["factory_capacities"] == ""
    plan = calibration.validate_plan(plan_dir)
    rows = calibration._read_csv(output_dir / "screening_metrics.csv")
    calibration.validate_campaign_operating_points(
        campaign_points_path,
        plan=plan,
        rows=rows,
        selection=first,
        seed=calibration.DEFAULT_SEED,
        evidence_signatures=[
            calibration._read_json(
                calibration._evidence_path(output_dir, candidate.candidate_id)
            )["evidence_signature"]
            for candidate in plan.candidates
        ],
    )
    campaign_points_path.unlink()
    exported = calibration.export_completed_run(plan_dir, output_dir)
    assert exported == campaign_points
    assert calibration.export_completed_run(plan_dir, output_dir) == exported
    calls.clear()

    second = calibration.run_grid(
        plan_dir,
        output_dir,
        workers=2,
        executor=fake_executor,
    )
    assert second == first
    assert calls == []


def test_campaign_point_validation_rejects_tampering(tmp_path: Path) -> None:
    plan_dir = _prepare_test_plan(tmp_path, offsets=(0.0, 10.0, 20.0))
    plan = calibration.validate_plan(plan_dir)
    evidence = [
        _evidence(candidate, plan, calibration.DEFAULT_SEED)
        for candidate in plan.candidates
    ]
    rows = [calibration._result_row(item) for item in evidence]
    selection = calibration.select_balanced_targets(rows, candidates=plan.candidates)
    payload = calibration.build_campaign_operating_points(
        plan,
        rows,
        selection,
        seed=calibration.DEFAULT_SEED,
        evidence_signatures=[item["evidence_signature"] for item in evidence],
    )
    payload["operating_points"][1]["screening_product_268091_service"] = 0.5

    with pytest.raises(ValueError, match="contract mismatch"):
        calibration.validate_campaign_operating_points(
            payload,
            plan=plan,
            rows=rows,
            selection=selection,
            seed=calibration.DEFAULT_SEED,
            evidence_signatures=[item["evidence_signature"] for item in evidence],
        )


def test_selection_rejects_an_incomplete_grid() -> None:
    candidates = calibration.build_candidates((0.0, 10.0), (0.0, 10.0))
    rows = [
        {
            **asdict(candidate),
            "valid": True,
            "system_on_due_service": 0.9,
            "on_due_service_268091": 0.9,
            "on_due_service_268967": 0.9,
        }
        for candidate in candidates[:-1]
    ]
    with pytest.raises(ValueError, match="Result grid mismatch"):
        calibration.select_balanced_targets(rows, candidates=candidates)


def test_plan_requires_zero_zero_candidate_for_op100(tmp_path: Path) -> None:
    sources = _fixture_sources(tmp_path)
    with pytest.raises(ValueError, match="contain zero"):
        calibration.prepare_plan(
            tmp_path / "plan_without_zero",
            active_lanes_path=sources["lanes"],
            graph_path=sources["graph"],
            engine_path=sources["engine"],
            profile_path=sources["profile"],
            offsets_268091=(1.0, 2.0),
            offsets_268967=(0.0, 2.0),
        )
