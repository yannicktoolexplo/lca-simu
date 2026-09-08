from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v2 as subject,
)


def _lane(index: int = 1) -> subject.Lane:
    return subject.Lane(
        lane_id=f"lane_{index:02d}",
        supplier_id=f"SUP-{index:02d}",
        item_id=f"item:{index:06d}",
        dst_node_id="M-1810",
        edge_id=f"edge:{index:02d}",
        target_product_id="268091",
        planned_lead_days=10.0,
    )


def _shipment(
    lane: subject.Lane,
    *,
    shipment_id: str,
    decision_day: int,
    release_day: int | None = None,
    arrival_day: int | None = None,
    pulled_qty: float = 100.0,
    shipped_qty: float = 100.0,
    risk_event_ids: str = "",
    reliability: float = 1.0,
    lead_days: int = 10,
) -> dict[str, object]:
    release = decision_day if release_day is None else release_day
    arrival = decision_day + 10 if arrival_day is None else arrival_day
    return {
        "day": release,
        "shipment_id": shipment_id,
        "risk_decision_day": decision_day,
        "risk_event_ids": risk_event_ids,
        "src_node_id": lane.supplier_id,
        "dst_node_id": lane.dst_node_id,
        "item_id": lane.item_id,
        "edge_id": lane.edge_id,
        "shipped_qty": shipped_qty,
        "pulled_qty": pulled_qty,
        "lead_days": lead_days,
        "arrival_day": arrival,
        "reliability": reliability,
        "uom": "UN",
    }


def test_full_design_counts_and_seed_blocks_are_frozen() -> None:
    assert subject.SIMULATION_DAYS == 1080
    assert subject.STATE_EVALUATION_DAYS == 720
    assert subject.IMPACT_WINDOW_DAYS == 360
    assert subject.INCIDENT_DISRUPTION_DAYS == 42
    assert subject.MIN_RECOVERY_OBSERVATION_DAYS == 90
    assert subject.SEEDS == tuple(range(340287, 340317))
    assert len(subject.SEED_BLOCKS) == 6
    assert subject.seed_block(1) == tuple(range(340287, 340292))
    assert subject.seed_block(6) == tuple(range(340312, 340317))
    assert subject._planned_case_count(5, 18) == 185
    assert 3 * subject._planned_case_count(30, 18) == 3330


def test_late_338929_style_target_has_complete_360_day_envelope() -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [
            _shipment(
                lane,
                shipment_id="338929-J687",
                decision_day=687,
                arrival_day=792,
                shipped_qty=3350.0,
            )
        ],
        lane=lane,
    )

    assert target["target_status"] == "identified_unique_reference_shipment"
    assert target["impact_window_start_day"] == 687
    assert target["impact_window_end_day"] == 1046
    assert target["impact_window_days"] == 360
    assert target["target_latest_stressed_arrival_day"] == 912
    assert target["recovery_observation_days_after_latest_stressed_arrival"] == 168
    assert target["recovery_observation_days_within_impact_window"] == 135
    assert target["recovery_fully_observed_within_360"] is True
    assert target["causal_window_start_day"] == 792
    assert target["causal_window_end_day"] == 1001
    assert target["causal_window_days"] == 210
    assert target["causal_window_fully_observed"] is True


def test_degraded_long_lead_target_is_not_filtered_by_fixed_360_day_envelope() -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [
            _shipment(
                lane,
                shipment_id="long-lead-but-observable",
                decision_day=131,
                arrival_day=336,
                shipped_qty=500.0,
            ),
            _shipment(
                lane,
                shipment_id="shorter-smaller",
                decision_day=140,
                arrival_day=213,
                shipped_qty=100.0,
            ),
        ],
        lane=lane,
    )

    assert target["target_shipment_id"] == "long-lead-but-observable"
    assert target["impact_window_end_day"] == 490
    assert target["target_latest_stressed_arrival_day"] == 456
    assert target["recovery_observation_days_within_impact_window"] == 35
    assert target["recovery_fully_observed_within_360"] is False
    assert target["causal_window_end_day"] == 545
    assert target["causal_window_fully_observed"] is True


def test_target_selection_fails_closed_when_delayed_arrival_lacks_90_day_followup() -> (
    None
):
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [
            _shipment(
                lane,
                shipment_id="censored",
                decision_day=719,
                arrival_day=1000,
            ),
            _shipment(
                lane,
                shipment_id="outside-state-window",
                decision_day=720,
                arrival_day=730,
            ),
        ],
        lane=lane,
    )

    assert (
        target["target_status"] == "not_applicable_selected_reference_horizon_censored"
    )
    assert target["candidate_day_count"] == 1
    assert target["eligible_candidate_day_count"] == 0
    assert target["required_simulation_days"] == 1210
    assert "must fail rather than substitute" in target["reason"]


def test_mechanisms_exclude_quality_availability_capacity_and_stock() -> None:
    mechanisms = subject._mechanism_contract()
    assert {row["key"] for row in mechanisms} == {
        "transport_delay",
        "planned_delivery_shortfall",
    }
    assert {row["risk_type"] for row in mechanisms} == {
        "lead_time_extra_days",
        "reliability",
    }
    assert not (
        {row["risk_type"] for row in mechanisms} & subject.FORBIDDEN_INCIDENT_RISK_TYPES
    )
    shortfall = next(
        row for row in mechanisms if row["key"] == "planned_delivery_shortfall"
    )
    assert shortfall["value"] == 0.5


def test_balanced_product_delay_points_allow_no_capacity_floor(tmp_path: Path) -> None:
    points = []
    for point_id, target, service, offsets in (
        ("op_100", 1.0, 0.999, (0.0, 0.0)),
        ("op_93", 0.93, 0.931, (10.0, 60.0)),
        ("op_80", 0.80, 0.802, (22.0, 120.0)),
    ):
        graph = tmp_path / f"{point_id}.json"
        graph.write_text("{}", encoding="utf-8")
        points.append(
            {
                "operating_point_id": point_id,
                "target_service": target,
                "screening_system_service": service,
                "degradation_family": (
                    "baseline"
                    if point_id == "op_100"
                    else "balanced_product_supplier_planned_lead"
                ),
                "degradation_value": {
                    "offset_days_268091": offsets[0],
                    "offset_days_268967": offsets[1],
                },
                "graph": str(graph),
                "supplier_floors": "",
                "factory_capacities": "",
            }
        )
    source = tmp_path / "operating_points.json"
    source.write_text(
        json.dumps(
            {
                "quality_branch_included": False,
                "supplier_state_dependent_risks_enabled": False,
                "acute_incident_included_in_operating_point": False,
                "operating_points": points,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="five-seed multi-seed"):
        subject.load_operating_points(source)
    loaded = subject.load_operating_points(source, require_prevalidated=False)

    assert [row["operating_point_id"] for row in loaded] == list(
        subject.OPERATING_POINT_IDS
    )
    assert all(row["supplier_floors"] == "" for row in loaded)
    assert loaded[1]["operating_point_service_pct"] == pytest.approx(93.1)


def test_loader_accepts_only_signed_multiseed_selection_with_sealed_holdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    points = []
    for point_id, target, calibrated, offsets in (
        ("op_100", 1.0, 0.995, (0.0, 0.0)),
        ("op_93", 0.93, 0.932, (7.0, 90.0)),
        ("op_80", 0.80, 0.804, (22.0, 120.0)),
    ):
        graph = tmp_path / f"{point_id}.json"
        graph.write_text("{}", encoding="utf-8")
        points.append(
            {
                "operating_point_id": point_id,
                "operating_point_label": point_id,
                "target_service": target,
                "calibration_pooled_service": calibrated,
                "calibration_product_268091_service": calibrated - 0.01,
                "calibration_product_268967_service": calibrated + 0.01,
                "offset_days_268091": offsets[0],
                "offset_days_268967": offsets[1],
                "candidate_key": {
                    "op_100": "op100_reference",
                    "op_93": "op93_wave_7_90",
                    "op_80": "op80_high_22_97",
                }[point_id],
                "graph": str(graph),
                "graph_sha256": subject._sha256_file(graph),
            }
        )
    plan_dir = tmp_path / "calibration_plan"
    plan_dir.mkdir()
    source_hashes = {
        "engine_sha256": "e" * 64,
        "profile_sha256": "p" * 64,
    }
    cohorts = {
        "design": [subject.TARGET_DESIGN_SEED],
        "calibration": list(range(340282, 340287)),
        "holdout_sealed": list(subject.SEEDS),
    }
    service_window = {"start_day": 0, "end_day": 719, "day_count": 720}
    plan_manifest = {
        "plan_signature": "plan-signature",
        "source_hashes": source_hashes,
        "cohorts": cohorts,
        "selection_contract": {
            "no_holdout_retuning": True,
            "global_median_must_also_be_in_target_band": True,
        },
        "holdout_contract": {
            "status_only_if_passed": subject.HOLDOUT_ACCEPTED_STATUS,
            "fixed_point_count": 3,
            "seed_count": 30,
            "baseline_case_count": 90,
            "seeds": list(subject.SEEDS),
            "service_window": service_window,
            "op100_minimum_global_and_each_product": 0.985,
            "op93_global_pooled_and_median_band": [0.915, 0.945],
            "op80_global_pooled_and_median_band": [0.785, 0.815],
            "degraded_product_strictly_below": 0.995,
            "pooled_strict_order_required_for": [
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            ],
            "same_seed_joint_strict_order_required": 24,
            "bootstrap_repetitions_descriptive": 10_000,
            "retuning_after_holdout": False,
        },
    }
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_calibration as multiseed_calibration,
    )

    monkeypatch.setattr(
        multiseed_calibration,
        "validate_plan",
        lambda _path: SimpleNamespace(plan_dir=plan_dir, manifest=plan_manifest),
    )
    selection_unsigned = {
        "schema_version": multiseed_calibration.SELECTION_SCHEMA_VERSION,
        "status": "calibration_selected",
        "plan_signature": "plan-signature",
        "calibration_seeds": list(range(340282, 340287)),
        "holdout_seeds_sealed_and_unread": list(subject.SEEDS),
        "selection_contract": plan_manifest["selection_contract"],
        "fallback_required": False,
        "selected_pair": {
            "op93_candidate_key": "op93_wave_7_90",
            "op80_candidate_key": "op80_high_22_97",
        },
    }
    selection = {
        **selection_unsigned,
        "selection_signature": subject._stable_sha256(selection_unsigned),
    }
    (tmp_path / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    payload = {
        "schema_version": (
            "etudecas.multiseed_operating_point_calibration.v1.selected_operating_points"
        ),
        "status": "selected_on_five_seed_calibration_pending_holdout",
        "plan": {"path": str(plan_dir), "plan_signature": "plan-signature"},
        "selection_signature": selection["selection_signature"],
        "source_hashes": source_hashes,
        "service_evaluation_window": service_window,
        "cohorts": cohorts,
        "holdout_validated": False,
        "simulation_hypotheses_not_observed_performance": True,
        "operating_points": points,
    }
    payload["artifact_signature"] = subject._stable_sha256(payload)
    source = tmp_path / "selected_operating_points.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    loaded = subject.load_operating_points(source)

    low = next(row for row in loaded if row["operating_point_id"] == "op_80")
    assert low["target_service"] == pytest.approx(0.80)
    assert low["operating_point_service_pct"] == pytest.approx(80.4)
    assert low["degradation_family"] == "balanced_product_supplier_planned_lead"

    tampered = dict(payload)
    tampered["cohorts"] = {
        **payload["cohorts"],
        "holdout_sealed": list(subject.SEEDS[:-1]),
    }
    tampered["artifact_signature"] = subject._stable_sha256(
        {key: value for key, value in tampered.items() if key != "artifact_signature"}
    )
    source.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="cohorts fail closed"):
        subject.load_operating_points(source)

    plan_manifest["holdout_contract"] = {
        **plan_manifest["holdout_contract"],
        "same_seed_joint_strict_order_required": 23,
    }
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="holdout contract is incompatible"):
        subject.load_operating_points(source)


def _prepare_v2_selected_points(tmp_path: Path) -> Path:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v2 as refinement,
    )
    from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_balanced_product_delay_multiseed_refinement_v2 import (
        _prepare_v1,
        _raw_evidence,
    )

    source_plan, source_run = _prepare_v1(tmp_path)
    plan_dir = tmp_path / "v2_refinement_plan"
    run_dir = tmp_path / "v2_refinement_run"
    refinement.prepare_plan(
        plan_dir,
        source_plan_dir=source_plan,
        source_run_dir=source_run,
    )

    def executor(candidate, adapter, _output_dir, seed):
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

    result = refinement.run(plan_dir, run_dir, workers=2, executor=executor)
    assert result["selection"]["status"] == (
        "five_seed_loo_screen_passed_pending_holdout"
    )
    return run_dir / "selected_operating_points.json"


def test_loader_dispatches_strict_v2_source_and_rejects_alterations(
    tmp_path: Path,
) -> None:
    source = _prepare_v2_selected_points(tmp_path)
    original = source.read_text(encoding="utf-8")

    loaded = subject.load_operating_points(source)
    chain = subject._validate_pending_multiseed_source(source, json.loads(original))

    assert [point["operating_point_id"] for point in loaded] == list(
        subject.OPERATING_POINT_IDS
    )
    assert chain["producer"] == "v2_refinement"
    assert Path(chain["plan_manifest_path"]).name == "refinement_plan.json"
    assert loaded[1]["degradation_family"] == ("balanced_product_supplier_planned_lead")

    wrong_status = json.loads(original)
    wrong_status["status"] = subject.V1_POINTS_PENDING_STATUS
    wrong_status["artifact_signature"] = subject._stable_sha256(
        {
            key: value
            for key, value in wrong_status.items()
            if key != "artifact_signature"
        }
    )
    source.write_text(json.dumps(wrong_status), encoding="utf-8")
    with pytest.raises(ValueError, match="exact signed V1, V2, or V3"):
        subject.load_operating_points(source)

    wrong_schema = json.loads(original)
    wrong_schema["schema_version"] = f"{subject.V2_POINTS_SCHEMA_VERSION}.altered"
    wrong_schema["artifact_signature"] = subject._stable_sha256(
        {
            key: value
            for key, value in wrong_schema.items()
            if key != "artifact_signature"
        }
    )
    source.write_text(json.dumps(wrong_schema), encoding="utf-8")
    with pytest.raises(ValueError, match="exact signed V1, V2, or V3"):
        subject.load_operating_points(source)

    tampered = json.loads(original)
    tampered["operating_points"][1]["calibration_pooled_service"] += 0.001
    tampered["artifact_signature"] = subject._stable_sha256(
        {key: value for key, value in tampered.items() if key != "artifact_signature"}
    )
    source.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="not reproducible from evidence"):
        subject.load_operating_points(source)

    source.write_text(original, encoding="utf-8")
    selection = source.parent / "selection.json"
    hidden_selection = source.parent / "selection.hidden-for-test.json"
    selection.rename(hidden_selection)
    try:
        with pytest.raises(ValueError, match="sibling selection.json"):
            subject.load_operating_points(source)
    finally:
        hidden_selection.rename(selection)


def _prepare_mocked_v3_selected_points(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    engine_sha256: str = "e" * 64,
    profile_sha256: str = "p" * 64,
) -> tuple[Path, dict[str, object]]:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v3 as refinement,
    )

    plan_dir = tmp_path / "v3_refinement_plan"
    run_dir = tmp_path / "v3_refinement_run"
    plan_dir.mkdir()
    run_dir.mkdir()
    source_hashes = {
        "engine_sha256": engine_sha256,
        "profile_sha256": profile_sha256,
        "v3_driver_sha256": subject.V3_REFINEMENT_MODULE_SHA256,
    }
    cohorts = {
        "design": [subject.TARGET_DESIGN_SEED],
        "calibration": list(subject.CALIBRATION_SEEDS),
        "holdout_sealed": list(subject.SEEDS),
    }
    selection_contract = refinement._selection_contract()
    holdout_contract = refinement._holdout_contract()
    plan_manifest = {
        "plan_signature": "v3-plan-signature",
        "source_hashes": source_hashes,
        "cohorts": cohorts,
        "selection_contract": selection_contract,
        "holdout_contract": holdout_contract,
    }
    (plan_dir / "refinement_plan.json").write_text(
        json.dumps(plan_manifest), encoding="utf-8"
    )

    selected_pair = {
        "op93_candidate_key": refinement.FIXED_OP93_KEY,
        "op80_candidate_key": refinement.OP80_REFINEMENT_WAVE[0].key,
        "same_seed_joint_strict_order_count": 5,
        "score": [0.0],
    }
    selection_unsigned = {
        "schema_version": refinement.SELECTION_SCHEMA_VERSION,
        "status": refinement.SELECTION_PASS_STATUS,
        "plan_signature": plan_manifest["plan_signature"],
        "calibration_seeds": list(subject.CALIBRATION_SEEDS),
        "holdout_seeds_sealed_and_unread": list(subject.SEEDS),
        "holdout_cases_read": 0,
        "selection_contract": selection_contract,
        "holdout_contract": holdout_contract,
        "candidate_summaries": {},
        "eligible_pairs": [selected_pair],
        "selected_pair": selected_pair,
        "holdout_launch_permitted": True,
        "fallback_required": False,
    }
    selection = {
        **selection_unsigned,
        "selection_signature": subject._stable_sha256(selection_unsigned),
    }
    selection_path = run_dir / "selection.json"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")

    points = []
    for point_id, target, service, key, offsets in (
        ("op_100", 1.0, 0.999, refinement.FIXED_REFERENCE_KEY, (0.0, 0.0)),
        ("op_93", 0.93, 0.931, refinement.FIXED_OP93_KEY, (7.0, 81.0)),
        (
            "op_80",
            0.80,
            0.801,
            refinement.OP80_REFINEMENT_WAVE[0].key,
            (16.5, 94.0),
        ),
    ):
        graph = plan_dir / f"{point_id}.json"
        graph.write_text("{}", encoding="utf-8")
        points.append(
            {
                "operating_point_id": point_id,
                "target_service": target,
                "candidate_key": key,
                "candidate_id": key,
                "offset_days_268091": offsets[0],
                "offset_days_268967": offsets[1],
                "graph": str(graph.resolve()),
                "graph_sha256": subject._sha256_file(graph),
                "calibration_pooled_service": service,
                "calibration_median_service": service,
                "calibration_product_268091_service": service - 0.01,
                "calibration_product_268967_service": service + 0.01,
                "maximum_global_target_error_over_pool_median_and_leave_one_out": (  # noqa: E501
                    0.001
                ),
            }
        )
    payload: dict[str, object] = {
        "schema_version": refinement.POINTS_SCHEMA_VERSION,
        "status": refinement.POINTS_STATUS,
        "simulation_hypotheses_not_observed_performance": True,
        "target_labels_apply_to_global_service_only": True,
        "holdout_validated": False,
        "holdout_cases_read": 0,
        "plan": {
            "path": str(plan_dir.resolve()),
            "plan_signature": plan_manifest["plan_signature"],
        },
        "selection": {
            "relative_path": "selection.json",
            "schema_version": refinement.SELECTION_SCHEMA_VERSION,
            "selection_signature": selection["selection_signature"],
        },
        "selection_signature": selection["selection_signature"],
        "source_hashes": source_hashes,
        "cohorts": cohorts,
        "holdout_contract": holdout_contract,
        "service_evaluation_window": dict(refinement.SERVICE_WINDOW),
        "operating_points": points,
    }
    payload["artifact_signature"] = subject._stable_sha256(payload)
    source = run_dir / "selected_operating_points.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    calls: dict[str, object] = {"selected": 0, "plans": []}

    def validate_selected(path: Path) -> dict[str, object]:
        calls["selected"] = int(calls["selected"]) + 1
        return json.loads(path.read_text(encoding="utf-8"))

    def validate_plan(path: Path) -> SimpleNamespace:
        plans = calls["plans"]
        assert isinstance(plans, list)
        plans.append(path.resolve())
        return SimpleNamespace(plan_dir=plan_dir.resolve(), manifest=plan_manifest)

    monkeypatch.setattr(
        refinement, "validate_selected_operating_points", validate_selected
    )
    monkeypatch.setattr(refinement, "validate_plan", validate_plan)
    return source, calls


def test_loader_dispatches_frozen_v3_and_records_complete_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = tmp_path / "engine.py"
    profile = tmp_path / "profile.json"
    lanes = tmp_path / "lanes.csv"
    engine.write_text("# engine fixture\n", encoding="utf-8")
    profile.write_text("{}", encoding="utf-8")
    lanes.write_text("fixture\n", encoding="utf-8")
    source, calls = _prepare_mocked_v3_selected_points(
        tmp_path,
        monkeypatch,
        engine_sha256=subject._sha256_file(engine),
        profile_sha256=subject._sha256_file(profile),
    )

    loaded = subject.load_operating_points(source)
    chain = subject._validate_pending_multiseed_source(
        source, json.loads(source.read_text(encoding="utf-8"))
    )
    design = subject._design_payload(
        operating_points_path=source,
        lane_reference_path=lanes,
        engine=engine,
        profile=profile,
        points=loaded,
        lanes=[_lane(index) for index in range(1, 19)],
    )

    assert int(calls["selected"]) == 3
    assert chain["producer"] == "v3_refinement"
    assert design["operating_points_producer"] == "v3_refinement"
    assert design["operating_points_schema_version"] == subject.V3_POINTS_SCHEMA_VERSION
    assert design["operating_points_input_status"] == subject.V3_POINTS_PENDING_STATUS
    assert design["operating_points_source_sha256"] == subject._sha256_file(source)
    assert (
        design["operating_points_cohorts"]
        == json.loads(source.read_text(encoding="utf-8"))["cohorts"]
    )
    assert Path(design["operating_points_calibration_plan"]).name == (
        "refinement_plan.json"
    )
    assert design["operating_points_calibration_plan_sha256"] == subject._sha256_file(
        Path(design["operating_points_calibration_plan"])
    )
    assert Path(design["operating_points_selection"]).name == "selection.json"
    assert design["operating_points_selection_sha256"] == subject._sha256_file(
        Path(design["operating_points_selection"])
    )
    assert design["operating_points_holdout_contract"]["selected_output_status"] == (
        subject.V3_POINTS_PENDING_STATUS
    )
    assert [point["operating_point_id"] for point in loaded] == list(
        subject.OPERATING_POINT_IDS
    )


def test_v3_dispatch_rejects_mixes_cohorts_and_resigned_failed_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_balanced_product_delay_multiseed_refinement_v3 as refinement,
    )

    source, _calls = _prepare_mocked_v3_selected_points(tmp_path, monkeypatch)
    original = json.loads(source.read_text(encoding="utf-8"))

    mixed = {**original, "status": subject.V2_POINTS_PENDING_STATUS}
    mixed["artifact_signature"] = subject._stable_sha256(
        {key: value for key, value in mixed.items() if key != "artifact_signature"}
    )
    source.write_text(json.dumps(mixed), encoding="utf-8")
    with pytest.raises(ValueError, match="exact signed V1, V2, or V3"):
        subject.load_operating_points(source)

    changed_cohorts = {
        **original,
        "cohorts": {
            **original["cohorts"],
            "holdout_sealed": list(subject.SEEDS[:-1]),
        },
    }
    changed_cohorts["artifact_signature"] = subject._stable_sha256(
        {
            key: value
            for key, value in changed_cohorts.items()
            if key != "artifact_signature"
        }
    )
    source.write_text(json.dumps(changed_cohorts), encoding="utf-8")
    with pytest.raises(ValueError, match="cohorts fail closed"):
        subject.load_operating_points(source)

    source.write_text(json.dumps(original), encoding="utf-8")
    selection_path = source.parent / "selection.json"
    failed_selection = json.loads(selection_path.read_text(encoding="utf-8"))
    failed_selection["status"] = refinement.SELECTION_FAIL_STATUS
    failed_selection["selection_signature"] = subject._stable_sha256(
        {
            key: value
            for key, value in failed_selection.items()
            if key != "selection_signature"
        }
    )
    selection_path.write_text(json.dumps(failed_selection), encoding="utf-8")
    resigned_source = {
        **original,
        "selection_signature": failed_selection["selection_signature"],
        "selection": {
            **original["selection"],
            "selection_signature": failed_selection["selection_signature"],
        },
    }
    resigned_source["artifact_signature"] = subject._stable_sha256(
        {
            key: value
            for key, value in resigned_source.items()
            if key != "artifact_signature"
        }
    )
    source.write_text(json.dumps(resigned_source), encoding="utf-8")
    with pytest.raises(ValueError, match="selection evidence/status/signature"):
        subject.load_operating_points(source)


def test_v3_dispatch_rejects_missing_selection_and_changed_producer_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _calls = _prepare_mocked_v3_selected_points(tmp_path, monkeypatch)
    selection = source.parent / "selection.json"
    hidden = source.parent / "selection.hidden-for-test.json"
    selection.rename(hidden)
    try:
        with pytest.raises(FileNotFoundError, match="selection disappeared"):
            subject.load_operating_points(source)
    finally:
        hidden.rename(selection)

    monkeypatch.setattr(subject, "V3_REFINEMENT_MODULE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="producer hash changed"):
        subject.load_operating_points(source)


def test_engine_command_does_not_invent_supplier_floor_for_balanced_points(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"args": []}), encoding="utf-8")
    command = subject._build_engine_command(
        manifest={
            "engine": str(tmp_path / "engine.py"),
            "engine_profile": str(profile),
        },
        point={
            "graph": str(tmp_path / "graph.json"),
            "supplier_floors": "",
            "factory_capacities": "",
        },
        case_dir=tmp_path / "case",
        seed=subject.SEEDS[0],
        risk_csv=None,
    )
    assert "--supplier-neutral-floors-csv" not in command
    assert "--factory-nominal-capacities-csv" not in command


def test_target_selection_prioritizes_aggregate_quantity_not_single_row() -> None:
    lane = _lane()
    rows = [
        # Two chunks created by one decision day are a valid aggregate exposure.
        _shipment(lane, shipment_id="split-a", decision_day=20, shipped_qty=500.0),
        _shipment(lane, shipment_id="split-b", decision_day=20, shipped_qty=500.0),
        _shipment(lane, shipment_id="unique-small", decision_day=30, shipped_qty=100.0),
        _shipment(lane, shipment_id="unique-large", decision_day=40, shipped_qty=400.0),
        # Late arrivals remain valid anchors: the risk still applies and the
        # horizon truncation is an explicit consequence of the delay.
        _shipment(
            lane,
            shipment_id="too-late",
            decision_day=650,
            arrival_day=700,
            shipped_qty=1000.0,
        ),
    ]

    target = subject.select_unique_reference_shipment(rows, lane=lane)

    assert target["target_status"] == "identified_reference_lane_day_shipment_group"
    assert target["target_shipment_ids"] == "split-a|split-b"
    assert target["target_decision_day"] == 20
    assert target["target_shipment_count"] == 2
    assert target["unique_candidate_day_count"] == 3
    assert target["reference_kind"].startswith("paired_simulated_baseline")


def test_split_lane_day_is_aggregated_when_no_unique_day_exists() -> None:
    lane = _lane()
    rows = [
        _shipment(lane, shipment_id="a", decision_day=20),
        _shipment(lane, shipment_id="b", decision_day=20),
    ]
    target = subject.select_unique_reference_shipment(rows, lane=lane)
    assert target["target_status"] == "identified_reference_lane_day_shipment_group"
    assert target["target_shipment_count"] == 2
    assert target["target_shipment_ids"] == "a|b"
    assert target["target_planned_qty"] == 200.0
    assert target["target_expected_delivered_qty"] == 200.0
    assert target["unique_candidate_day_count"] == 0


def test_zero_positive_flow_is_explicitly_non_applicable() -> None:
    lane = _lane()
    row = _shipment(lane, shipment_id="zero", decision_day=20)
    row["pulled_qty"] = 0.0
    row["shipped_qty"] = 0.0
    target = subject.select_unique_reference_shipment([row], lane=lane)
    assert target["target_status"] == "not_applicable_no_positive_reference_flow"
    assert target["target_shipment_count"] == 0
    assert "No positive baseline shipment" in target["reason"]


@pytest.mark.parametrize(
    ("mechanism_key", "risk_type", "value"),
    [
        ("transport_delay", "lead_time_extra_days", 120.0),
        ("planned_delivery_shortfall", "reliability", 0.5),
    ],
)
def test_risk_row_targets_one_lane_and_one_fixed_42_day_window(
    mechanism_key: str, risk_type: str, value: float
) -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [_shipment(lane, shipment_id="SHIP-42", decision_day=42)],
        lane=lane,
        forced_decision_day=42,
        target_window_days=42,
    )
    mechanism = next(item for item in subject.MECHANISMS if item.key == mechanism_key)
    row = subject.build_risk_row(
        point_id="op_93",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    assert row["risk_type"] == risk_type
    assert row["multiplier"] == value
    assert row["start_day"] == 42
    assert row["end_day"] == 83
    assert row["edge_id"] == lane.edge_id
    assert row["item_id"] == lane.item_id
    assert "42" in row["notes"] and "83" in row["notes"]
    assert "__window_42_83" in row["event_id"]
    assert row["risk_type"] not in subject.FORBIDDEN_INCIDENT_RISK_TYPES


def _application_row(
    event_id: str, day: int, *, reliability: float = 1.0, delay: float = 0.0
) -> dict[str, object]:
    return {
        "day": day,
        "event_ids": event_id,
        "reliability_multiplier": reliability,
        "lead_time_extra_days": delay,
        "availability_multiplier": 1.0,
        "capacity_multiplier": 1.0,
        "quality_yield_multiplier": 1.0,
        "quality_delay_days": 0.0,
    }


def test_shortfall_trace_accepts_replanned_id_and_proves_effective_reliability() -> (
    None
):
    lane = _lane()
    baseline = _shipment(
        lane,
        shipment_id="BASE-42",
        decision_day=42,
        arrival_day=52,
        pulled_qty=200.0,
        shipped_qty=180.0,
        reliability=0.9,
    )
    target = subject.select_unique_reference_shipment([baseline], lane=lane)
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "planned_delivery_shortfall"
    )
    risk = subject.build_risk_row(
        point_id="op_80",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    incident = _shipment(
        lane,
        shipment_id="REPLANNED-42",
        decision_day=42,
        arrival_day=52,
        pulled_qty=200.0,
        shipped_qty=90.0,
        risk_event_ids=str(risk["event_id"]),
        reliability=0.45,
    )
    proof, errors = subject.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=target,
        risk_row=risk,
        shipment_rows=[incident],
        applied_rows=[_application_row(str(risk["event_id"]), 42, reliability=0.5)],
    )
    assert errors == []
    assert proof["incident_physically_exercised"] is True
    assert proof["baseline_shipment_ids"] == ["BASE-42"]
    assert proof["stressed_shipment_ids"] == ["REPLANNED-42"]
    assert proof["quantity_shortfall_qty"] == pytest.approx(90.0)


def test_delay_trace_accepts_replanned_id_and_proves_effective_lead() -> None:
    lane = _lane()
    baseline = _shipment(
        lane,
        shipment_id="BASE-42",
        decision_day=42,
        arrival_day=52,
        pulled_qty=200.0,
        shipped_qty=180.0,
        reliability=0.9,
    )
    target = subject.select_unique_reference_shipment([baseline], lane=lane)
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "transport_delay"
    )
    risk = subject.build_risk_row(
        point_id="op_100",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    incident = _shipment(
        lane,
        shipment_id="REPLANNED-42",
        decision_day=42,
        arrival_day=172,
        pulled_qty=200.0,
        shipped_qty=180.0,
        risk_event_ids=str(risk["event_id"]),
        reliability=0.9,
        lead_days=130,
    )
    proof, errors = subject.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=target,
        risk_row=risk,
        shipment_rows=[incident],
        applied_rows=[_application_row(str(risk["event_id"]), 42, delay=120.0)],
    )
    assert errors == []
    assert proof["incident_physically_exercised"] is True
    assert proof["stressed_shipment_ids"] == ["REPLANNED-42"]


def test_multiday_trace_tags_all_replanned_dispatches_and_allows_application_superset() -> (
    None
):
    lane = _lane()
    baseline_rows = [
        _shipment(
            lane,
            shipment_id="SHIP-A",
            decision_day=42,
            arrival_day=52,
            pulled_qty=200.0,
            shipped_qty=180.0,
            reliability=0.9,
        ),
        _shipment(
            lane,
            shipment_id="SHIP-B",
            decision_day=42,
            release_day=45,
            arrival_day=55,
            pulled_qty=100.0,
            shipped_qty=90.0,
            reliability=0.9,
        ),
    ]
    target = subject.select_unique_reference_shipment(
        baseline_rows,
        lane=lane,
        forced_decision_day=42,
        target_window_days=42,
    )
    assert target["target_status"] == "identified_reference_lane_window_shipment_group"
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "planned_delivery_shortfall"
    )
    risk = subject.build_risk_row(
        point_id="op_93",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    stressed = [
        _shipment(
            lane,
            shipment_id="REPLAN-A",
            decision_day=42,
            arrival_day=52,
            pulled_qty=200.0,
            shipped_qty=90.0,
            risk_event_ids=str(risk["event_id"]),
            reliability=0.45,
        ),
        _shipment(
            lane,
            shipment_id="REPLAN-B",
            decision_day=50,
            release_day=53,
            arrival_day=63,
            pulled_qty=100.0,
            shipped_qty=45.0,
            risk_event_ids=str(risk["event_id"]),
            reliability=0.45,
        ),
    ]
    proof, errors = subject.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=target,
        risk_row=risk,
        shipment_rows=stressed,
        applied_rows=[
            _application_row(str(risk["event_id"]), 42, reliability=0.5),
            _application_row(str(risk["event_id"]), 43, reliability=0.5),
            _application_row(str(risk["event_id"]), 50, reliability=0.5),
        ],
    )
    assert errors == []
    assert proof["baseline_shipment_count"] == 2
    assert proof["stressed_shipment_ids"] == ["REPLAN-A", "REPLAN-B"]
    assert proof["stressed_pulled_qty"] == 300.0
    assert proof["stressed_shipped_qty"] == 135.0
    assert proof["quantity_shortfall_qty"] == 135.0


def test_fixed_window_without_flow_is_valid_and_not_physically_exercised() -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [],
        lane=lane,
        days=None,
        forced_decision_day=100,
        target_window_days=42,
    )
    assert target["target_status"] == "identified_registered_window_no_positive_flow"
    target.update(subject._incident_horizon_from_trace(target=target, tagged_rows=[]))
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "transport_delay"
    )
    risk = subject.build_risk_row(
        point_id="op_93",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )

    proof, errors = subject.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=target,
        risk_row=risk,
        shipment_rows=[],
        applied_rows=[],
        simulation_days=int(target["required_simulation_days"]),
    )

    assert errors == []
    assert proof["incident_physically_exercised"] is False
    assert proof["incident_shipment_count"] == 0


def test_trace_rejects_untagged_dispatch_inside_fixed_window() -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [_shipment(lane, shipment_id="BASE", decision_day=42)],
        lane=lane,
        forced_decision_day=42,
        target_window_days=42,
    )
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "planned_delivery_shortfall"
    )
    risk = subject.build_risk_row(
        point_id="op_93",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    untagged = _shipment(
        lane,
        shipment_id="REPLAN-UNTAGGED",
        decision_day=50,
        pulled_qty=100.0,
        shipped_qty=45.0,
        reliability=0.45,
    )

    _proof, errors = subject.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=target,
        risk_row=risk,
        shipment_rows=[untagged],
        applied_rows=[_application_row(str(risk["event_id"]), 50, reliability=0.5)],
    )

    assert any(
        "not every incident-window shipment is tagged" in error for error in errors
    )


def test_actual_tagged_arrival_extends_adaptive_causal_horizon() -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [_shipment(lane, shipment_id="BASE", decision_day=100, arrival_day=150)],
        lane=lane,
        days=None,
        forced_decision_day=100,
        target_window_days=42,
    )
    tagged = _shipment(
        lane,
        shipment_id="REPLAN-LATE",
        decision_day=120,
        arrival_day=900,
        risk_event_ids="event",
        lead_days=780,
    )

    window = subject._incident_horizon_from_trace(target=target, tagged_rows=[tagged])

    assert window["target_latest_stressed_arrival_day"] == 900
    assert window["causal_window_end_day"] == 989
    assert window["required_simulation_days"] == 990


def test_incident_probe_extends_horizon_and_resumes_after_promoted_case_prune(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [_shipment(lane, shipment_id="BASE", decision_day=100, arrival_day=150)],
        lane=lane,
        days=None,
        forced_decision_day=100,
        target_window_days=subject.INCIDENT_DISRUPTION_DAYS,
    )
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "transport_delay"
    )
    risk = subject.build_risk_row(
        point_id="op_100",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    tagged = _shipment(
        lane,
        shipment_id="REPLANNED-LATE",
        decision_day=110,
        arrival_day=900,
        risk_event_ids=str(risk["event_id"]),
        lead_days=790,
    )
    run_horizons: list[int] = []

    def fake_run_engine(**kwargs: object) -> Path:
        horizon = int(kwargs["simulation_days"])
        run_horizons.append(horizon)
        case_dir = Path(kwargs["shard_dir"]) / "cases" / str(kwargs["case_key"])
        case_dir.mkdir(parents=True)
        return case_dir

    monkeypatch.setattr(subject, "_run_engine", fake_run_engine)
    monkeypatch.setattr(subject.protocol, "read_csv_rows", lambda _path: [tagged])
    monkeypatch.setattr(
        subject,
        "_extract_metrics",
        lambda **_kwargs: (
            {"warmup_core_state_sha256": "warmup"},
            [tagged],
            [],
            [],
            {"service_rows": [], "production_rows": []},
        ),
    )
    monkeypatch.setattr(
        subject,
        "_window_metrics",
        lambda **kwargs: {
            "start_day": kwargs["start_day"],
            "end_day": kwargs["end_day"],
            "day_count": kwargs["end_day"] - kwargs["start_day"] + 1,
        },
    )
    monkeypatch.setattr(
        subject,
        "validate_incident_trace",
        lambda **_kwargs: ({"incident_physically_exercised": True}, []),
    )
    monkeypatch.setattr(
        subject.campaign_core,
        "prune_case_artifacts",
        lambda path: Path(path).rmdir(),
    )
    shard_dir = tmp_path / "shard"
    manifest = {
        "campaign_signature": "campaign",
        "target_registry_signature": "registry",
    }
    point = {"operating_point_id": "op_100"}

    prepared = subject._prepare_incident_probe(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        lane=lane,
        mechanism=mechanism,
        seed=subject.SEEDS[0],
        registered_target=target,
    )

    assert prepared["attempted_horizons"] == [720, 990]
    assert prepared["final_simulation_days"] == 990
    assert prepared["incident_window"]["causal_window_end_day"] == 989
    assert prepared["incident_window"]["minimum_required_simulation_days"] == 990
    assert prepared["case_artifacts_pruned"] is True

    # The compact signed probe survives after its engine directory was pruned,
    # even before a paired baseline/final evidence record exists.
    assert not Path(prepared["case_dir"]).exists()
    resumed = subject._prepare_incident_probe(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        lane=lane,
        mechanism=mechanism,
        seed=subject.SEEDS[0],
        registered_target=target,
    )

    assert resumed["probe_evidence_signature"] == prepared["probe_evidence_signature"]
    assert run_horizons == [720, 990]


def test_incident_probe_resumes_from_signed_intermediate_checkpoint_after_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane = _lane()
    target = subject.select_unique_reference_shipment(
        [_shipment(lane, shipment_id="BASE", decision_day=100, arrival_day=150)],
        lane=lane,
        days=None,
        forced_decision_day=100,
        target_window_days=subject.INCIDENT_DISRUPTION_DAYS,
    )
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "transport_delay"
    )
    risk = subject.build_risk_row(
        point_id="op_100",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    tagged = _shipment(
        lane,
        shipment_id="REPLANNED-LATE",
        decision_day=110,
        arrival_day=900,
        risk_event_ids=str(risk["event_id"]),
        lead_days=790,
    )
    run_horizons: list[int] = []

    def fake_run_engine(**kwargs: object) -> Path:
        horizon = int(kwargs["simulation_days"])
        run_horizons.append(horizon)
        case_dir = Path(kwargs["shard_dir"]) / "cases" / str(kwargs["case_key"])
        case_dir.mkdir(parents=True)
        return case_dir

    monkeypatch.setattr(subject, "_run_engine", fake_run_engine)
    monkeypatch.setattr(subject.protocol, "read_csv_rows", lambda _path: [tagged])
    monkeypatch.setattr(
        subject,
        "_extract_metrics",
        lambda **_kwargs: (
            {"warmup_core_state_sha256": "warmup"},
            [tagged],
            [],
            [],
            {"service_rows": [], "production_rows": []},
        ),
    )
    monkeypatch.setattr(
        subject,
        "_window_metrics",
        lambda **kwargs: {
            "start_day": kwargs["start_day"],
            "end_day": kwargs["end_day"],
            "day_count": kwargs["end_day"] - kwargs["start_day"] + 1,
        },
    )
    monkeypatch.setattr(
        subject,
        "validate_incident_trace",
        lambda **_kwargs: ({"incident_physically_exercised": True}, []),
    )
    prune_calls = 0

    def interrupt_after_first_prune(path: Path) -> list[str]:
        nonlocal prune_calls
        prune_calls += 1
        Path(path).rmdir()
        if prune_calls == 1:
            raise RuntimeError("simulated interruption after checkpoint")
        return []

    monkeypatch.setattr(
        subject.campaign_core,
        "prune_case_artifacts",
        interrupt_after_first_prune,
    )
    shard_dir = tmp_path / "shard"
    manifest = {
        "campaign_signature": "campaign",
        "target_registry_signature": "registry",
    }
    point = {"operating_point_id": "op_100"}

    with pytest.raises(RuntimeError, match="simulated interruption"):
        subject._prepare_incident_probe(
            shard_dir=shard_dir,
            manifest=manifest,
            point=point,
            lane=lane,
            mechanism=mechanism,
            seed=subject.SEEDS[0],
            registered_target=target,
        )

    checkpoints = list((shard_dir / "incident_probe_checkpoints").glob("*.json"))
    assert len(checkpoints) == 1
    interrupted = json.loads(checkpoints[0].read_text(encoding="utf-8"))
    unsigned = dict(interrupted)
    signature = unsigned.pop("checkpoint_signature")
    assert signature == subject._stable_sha256(unsigned)
    assert interrupted["attempted_horizons"] == [720]
    assert interrupted["next_required_simulation_days"] == 990
    assert interrupted["case_artifacts_pruned"] is False

    resumed = subject._prepare_incident_probe(
        shard_dir=shard_dir,
        manifest=manifest,
        point=point,
        lane=lane,
        mechanism=mechanism,
        seed=subject.SEEDS[0],
        registered_target=target,
    )

    assert resumed["attempted_horizons"] == [720, 990]
    assert resumed["case_artifacts_pruned"] is True
    assert run_horizons == [720, 990]
    recovered = json.loads(checkpoints[0].read_text(encoding="utf-8"))
    assert recovered["case_artifacts_pruned"] is True


def test_failed_engine_attempt_is_removed_after_bounded_signed_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subject, "_build_engine_command", lambda **_kwargs: ["fake"])

    def fail_engine(
        _command: list[str], *, stdout: object, **_kwargs: object
    ) -> SimpleNamespace:
        stream = stdout
        stream.write("X" * (subject.FAILED_ATTEMPT_LOG_TAIL_BYTES * 2))
        attempt = Path(stream.name).parent
        data = attempt / "data"
        data.mkdir()
        for index in range(subject.FAILED_ATTEMPT_INVENTORY_LIMIT + 6):
            (data / f"bulk_{index:03d}.csv").write_text("payload", encoding="utf-8")
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(subject.subprocess, "run", fail_engine)
    manifest = {"campaign_signature": "campaign", "engine_sha256": "engine"}
    point = {"operating_point_id": "op_100"}
    shard_dir = tmp_path / "shard"

    for _index in range(subject.FAILED_ATTEMPT_DIAGNOSTICS_PER_CASE + 2):
        with pytest.raises(RuntimeError, match="compact diagnostic"):
            subject._run_engine(
                shard_dir=shard_dir,
                manifest=manifest,
                point=point,
                case_key="failed_case",
                seed=subject.SEEDS[0],
                risk_csv=None,
                simulation_days=720,
            )

    attempts = shard_dir / "_attempts"
    assert attempts.is_dir()
    assert not list(attempts.iterdir())
    diagnostics = list((shard_dir / "attempt_diagnostics").glob("*.json"))
    assert len(diagnostics) == subject.FAILED_ATTEMPT_DIAGNOSTICS_PER_CASE
    for path in diagnostics:
        payload = json.loads(path.read_text(encoding="utf-8"))
        unsigned = dict(payload)
        signature = unsigned.pop("diagnostic_signature")
        assert signature == subject._stable_sha256(unsigned)
        assert payload["attempt_directory_removed"] is True
        inventory = payload["inventory_before_cleanup"]
        assert len(inventory["entries"]) == subject.FAILED_ATTEMPT_INVENTORY_LIMIT
        assert inventory["truncated"] is True
        assert (
            len(payload["engine_log"]["tail_utf8"].encode("utf-8"))
            <= subject.FAILED_ATTEMPT_LOG_TAIL_BYTES
        )


def test_holdout_registry_freezes_same_42_day_dates_and_prefers_lower_ratio_tie() -> (
    None
):
    lane = _lane()
    points = [
        {"operating_point_id": point_id} for point_id in subject.OPERATING_POINT_IDS
    ]
    rows: dict[tuple[str, int], list[dict[str, object]]] = {}
    design_quantities = {
        "op_100": (200.0, 160.0),
        "op_93": (200.0, 155.0),
        "op_80": (150.0, 150.0),
    }
    for point_id in subject.OPERATING_POINT_IDS:
        early_qty, balanced_qty = design_quantities[point_id]
        rows[(point_id, subject.TARGET_DESIGN_SEED)] = [
            _shipment(
                lane,
                shipment_id=f"design-{point_id}-early",
                decision_day=100,
                shipped_qty=early_qty,
                pulled_qty=early_qty,
            ),
            _shipment(
                lane,
                shipment_id=f"design-{point_id}-balanced",
                decision_day=300,
                shipped_qty=balanced_qty,
                pulled_qty=balanced_qty,
            ),
        ]
        for seed in subject.SEEDS:
            # Campaign outcomes must not move the date selected on seed 340281.
            rows[(point_id, seed)] = [
                _shipment(
                    lane,
                    shipment_id=f"campaign-{point_id}-{seed}-large",
                    decision_day=50,
                    shipped_qty=9999.0,
                    pulled_qty=9999.0,
                ),
                _shipment(
                    lane,
                    shipment_id=f"campaign-{point_id}-{seed}-fixed",
                    decision_day=300,
                    shipped_qty=100.0,
                    pulled_qty=100.0,
                ),
            ]

    registry = subject.build_cross_state_target_registry(
        manifest={"campaign_signature": "campaign", "engine_sha256": "engine"},
        points=points,
        lanes=[lane],
        shipment_rows_by_state_seed=rows,
    )

    contract = registry["lane_contracts"][0]
    assert contract["fixed_window_start_day"] == 259
    assert contract["design_quantity_ratio"] == pytest.approx(160.0 / 150.0)
    assert contract["comparable_campaign_seed_count"] == 30
    assert contract["state_comparison_valid"] is True
    assert registry["all_lane_design_windows_comparable"] is True
    assert registry["all_lane_holdout_exposures_comparable"] is True
    assert registry["campaign_exposure_gate_passed"] is True
    assert registry["exposure_gate_failures"] == []
    assert len(registry["targets"]) == 3 * 30
    assert {row["target_window_start_day"] for row in registry["targets"]} == {259}
    assert {
        row["state_exposure_max_window_start_day"] for row in registry["targets"]
    } == {9}


def test_target_registry_blocks_fewer_than_24_comparable_holdout_exposures() -> None:
    lane = _lane()
    points = [
        {"operating_point_id": point_id} for point_id in subject.OPERATING_POINT_IDS
    ]
    rows: dict[tuple[str, int], list[dict[str, object]]] = {}
    for point_id in subject.OPERATING_POINT_IDS:
        rows[(point_id, subject.TARGET_DESIGN_SEED)] = [
            _shipment(
                lane,
                shipment_id=f"design-{point_id}",
                decision_day=100,
                pulled_qty=100.0,
                shipped_qty=100.0,
            )
        ]
        for index, seed in enumerate(subject.SEEDS):
            exposed = not (point_id == "op_80" and index < 7)
            rows[(point_id, seed)] = (
                [
                    _shipment(
                        lane,
                        shipment_id=f"holdout-{point_id}-{seed}",
                        decision_day=100,
                        pulled_qty=100.0,
                        shipped_qty=100.0,
                    )
                ]
                if exposed
                else []
            )

    registry = subject.build_cross_state_target_registry(
        manifest={"campaign_signature": "campaign", "engine_sha256": "engine"},
        points=points,
        lanes=[lane],
        shipment_rows_by_state_seed=rows,
    )

    assert registry["lane_contracts"][0]["comparable_campaign_seed_count"] == 23
    assert registry["all_lane_design_windows_comparable"] is True
    assert registry["all_lane_holdout_exposures_comparable"] is False
    assert registry["campaign_exposure_gate_passed"] is False
    assert registry["exposure_gate_failures"] == [
        {
            "lane_id": lane.lane_id,
            "reasons": ["fewer_than_24_of_30_holdout_seeds_have_comparable_exposure"],
        }
    ]


def test_operating_point_preflight_uses_30_seed_ratio_of_sums_and_reports_dispersion() -> (
    None
):
    rates = {
        "op_100": (1.0, 1.0),
        "op_93": (0.94, 0.90),
        "op_80": (0.81, 0.79),
    }
    evidence: dict[tuple[str, int], dict[str, object]] = {}
    for point_id, (left, right) in rates.items():
        for seed in (subject.TARGET_DESIGN_SEED, *subject.SEEDS):
            evidence[(point_id, seed)] = {
                "state_service_metrics": {
                    "demand_qty_268091": 1000.0,
                    "on_due_qty_268091": 1000.0 * left,
                    "demand_qty_268967": 1000.0,
                    "on_due_qty_268967": 1000.0 * right,
                    "demand_qty_global": 2000.0,
                    "on_due_qty_global": 1000.0 * (left + right),
                }
            }
    points = [
        {"operating_point_id": "op_100", "target_service": 1.0},
        {"operating_point_id": "op_93", "target_service": 0.93},
        {"operating_point_id": "op_80", "target_service": 0.80},
    ]

    report = subject.build_operating_point_preflight(
        manifest={"campaign_signature": "campaign"},
        points=points,
        discovery_evidence=evidence,
        bootstrap_replicates=100,
    )

    assert report["status"] == subject.HOLDOUT_ACCEPTED_STATUS
    assert report["seed_order_counts"] == {
        "global": 30,
        "268091": 30,
        "268967": 30,
    }
    op93 = next(row for row in report["states"] if row["operating_point_id"] == "op_93")
    assert op93["service_global_ratio_of_sums_pct"] == pytest.approx(92.0)
    assert op93["product_service_gap_pp"] == pytest.approx(4.0)
    assert op93["seed_level_service_dispersion_pct"]["global"]["iqr"] == 0.0
    assert op93["seed_level_service_dispersion_pct"]["global"]["min"] == pytest.approx(
        92.0
    )
    assert op93["seed_level_service_dispersion_pct"]["global"]["max"] == pytest.approx(
        92.0
    )
    assert op93["saturated_seed_count_by_product"] == {
        "268091": 0,
        "268967": 0,
    }
    assert op93["transition_zone_observed"] is False


def test_operating_point_preflight_rejects_product_specific_order_crossing() -> None:
    # The operating-point contract is aggregate.  A product may cross between
    # op_93 and op_80 and must remain visible without silently redefining the
    # calibrated state as a per-product target.
    rates = {
        "op_100": (0.99, 0.99),
        "op_93": (0.79, 0.9344444444444444),
        "op_80": (0.80, 0.80),
    }
    evidence: dict[tuple[str, int], dict[str, object]] = {}
    for point_id, (left, right) in rates.items():
        for seed in (subject.TARGET_DESIGN_SEED, *subject.SEEDS):
            evidence[(point_id, seed)] = {
                "state_service_metrics": {
                    "demand_qty_268091": 10.0,
                    "on_due_qty_268091": 10.0 * left,
                    "demand_qty_268967": 90.0,
                    "on_due_qty_268967": 90.0 * right,
                    "demand_qty_global": 100.0,
                    "on_due_qty_global": 10.0 * left + 90.0 * right,
                }
            }
    points = [
        {"operating_point_id": "op_100", "target_service": 1.0},
        {"operating_point_id": "op_93", "target_service": 0.93},
        {"operating_point_id": "op_80", "target_service": 0.80},
    ]

    report = subject.build_operating_point_preflight(
        manifest={"campaign_signature": "campaign"},
        points=points,
        discovery_evidence=evidence,
        bootstrap_replicates=100,
    )

    assert report["status"] == subject.HOLDOUT_REJECTED_STATUS
    assert report["seed_order_counts"]["global"] == 30
    assert report["seed_order_counts"]["268091"] == 0
    assert report["seed_ordering_valid"] is False
    check = report["product_seed_ordering_checks"]["268091"]
    assert check["ordering_observed_in_at_least_24_of_30_seeds"] is False
    assert check["acceptance_gate"] is True


def test_operating_point_preflight_reports_product_saturation_transition() -> None:
    evidence: dict[tuple[str, int], dict[str, object]] = {}
    for point_id, rate in (("op_100", 0.99), ("op_93", 0.93), ("op_80", 0.80)):
        for seed in (subject.TARGET_DESIGN_SEED, *subject.SEEDS):
            right = rate
            if point_id == "op_93":
                right = 1.0 if seed == subject.SEEDS[0] else 0.92
            evidence[(point_id, seed)] = {
                "state_service_metrics": {
                    "demand_qty_268091": 100.0,
                    "on_due_qty_268091": 100.0 * rate,
                    "demand_qty_268967": 100.0,
                    "on_due_qty_268967": 100.0 * right,
                    "demand_qty_global": 200.0,
                    "on_due_qty_global": 100.0 * (rate + right),
                }
            }
    report = subject.build_operating_point_preflight(
        manifest={"campaign_signature": "campaign"},
        points=[
            {"operating_point_id": "op_100", "target_service": 1.0},
            {"operating_point_id": "op_93", "target_service": 0.93},
            {"operating_point_id": "op_80", "target_service": 0.80},
        ],
        discovery_evidence=evidence,
        bootstrap_replicates=100,
    )

    assert report["status"] == subject.HOLDOUT_ACCEPTED_STATUS
    op93 = next(row for row in report["states"] if row["operating_point_id"] == "op_93")
    assert op93["saturated_seed_count_by_product"]["268967"] == 1
    assert op93["transition_zone_by_product"]["268967"] is True
    assert op93["transition_zone_observed"] is True
    assert op93["seed_level_service_dispersion_pct"]["268967"]["max"] == 100.0


def test_operating_point_preflight_rejects_weighted_target_with_off_band_median() -> (
    None
):
    evidence: dict[tuple[str, int], dict[str, object]] = {}
    for index, seed in enumerate((subject.TARGET_DESIGN_SEED, *subject.SEEDS)):
        demand = 1.0 if 1 <= index <= 16 else 1000.0
        for point_id, rate in (
            ("op_100", 0.99),
            ("op_93", 0.90 if 1 <= index <= 16 else 0.93),
            ("op_80", 0.80),
        ):
            evidence[(point_id, seed)] = {
                "state_service_metrics": {
                    "demand_qty_268091": demand,
                    "on_due_qty_268091": demand * rate,
                    "demand_qty_268967": demand,
                    "on_due_qty_268967": demand * rate,
                    "demand_qty_global": 2.0 * demand,
                    "on_due_qty_global": 2.0 * demand * rate,
                }
            }
    report = subject.build_operating_point_preflight(
        manifest={"campaign_signature": "campaign"},
        points=[
            {"operating_point_id": "op_100", "target_service": 1.0},
            {"operating_point_id": "op_93", "target_service": 0.93},
            {"operating_point_id": "op_80", "target_service": 0.80},
        ],
        discovery_evidence=evidence,
        bootstrap_replicates=100,
    )

    op93 = next(row for row in report["states"] if row["operating_point_id"] == "op_93")
    assert op93["service_global_ratio_of_sums_pct"] == pytest.approx(93.0, abs=0.02)
    assert op93["service_global_seed_median_pct"] == pytest.approx(90.0)
    assert any("median seed-level" in failure for failure in op93["failures"])
    assert report["status"] == subject.HOLDOUT_REJECTED_STATUS


def test_operating_point_preflight_requires_joint_order_on_same_24_seeds() -> None:
    evidence: dict[tuple[str, int], dict[str, object]] = {}
    all_seeds = (subject.TARGET_DESIGN_SEED, *subject.SEEDS)
    for index, seed in enumerate(all_seeds):
        campaign_index = index - 1
        for point_id in subject.OPERATING_POINT_IDS:
            if point_id == "op_100":
                left = right = 0.99
            elif point_id == "op_80":
                left = right = 0.80
            else:
                left = 0.799 if 0 <= campaign_index < 4 else 0.934
                right = 0.799 if 4 <= campaign_index < 8 else 0.934
            evidence[(point_id, seed)] = {
                "state_service_metrics": {
                    "demand_qty_268091": 100.0,
                    "on_due_qty_268091": 100.0 * left,
                    "demand_qty_268967": 100.0,
                    "on_due_qty_268967": 100.0 * right,
                    "demand_qty_global": 200.0,
                    "on_due_qty_global": 100.0 * (left + right),
                }
            }
    report = subject.build_operating_point_preflight(
        manifest={"campaign_signature": "campaign"},
        points=[
            {"operating_point_id": "op_100", "target_service": 1.0},
            {"operating_point_id": "op_93", "target_service": 0.93},
            {"operating_point_id": "op_80", "target_service": 0.80},
        ],
        discovery_evidence=evidence,
        bootstrap_replicates=100,
    )

    assert report["seed_order_counts"] == {
        "global": 30,
        "268091": 26,
        "268967": 26,
    }
    assert report["joint_seed_order_count"] == 22
    assert report["seed_ordering_valid"] is False
    assert report["status"] == subject.HOLDOUT_REJECTED_STATUS


def test_rejected_holdout_stops_before_window_registry_or_incident_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "campaign"
    output_dir.mkdir()
    manifest = {"campaign_signature": "campaign"}
    (output_dir / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    points = [
        {"operating_point_id": point_id, "target_service": target}
        for point_id, target in zip(
            subject.OPERATING_POINT_IDS, (1.0, 0.93, 0.80), strict=True
        )
    ]
    execution_count = 0

    def fake_discovery_case(**_kwargs: object) -> dict[str, object]:
        nonlocal execution_count
        execution_count += 1
        return {"shipment_rows": [], "state_service_metrics": {}}

    preflight_unsigned = {
        "schema_version": subject.PREFLIGHT_SCHEMA_VERSION,
        "campaign_signature": "campaign",
        "status": subject.HOLDOUT_REJECTED_STATUS,
        "campaign_seed_count": len(subject.SEEDS),
        "campaign_seeds": list(subject.SEEDS),
        "states": [],
    }
    rejected_preflight = {
        **preflight_unsigned,
        "preflight_signature": subject._stable_sha256(preflight_unsigned),
    }
    monkeypatch.setattr(subject, "_execute_target_discovery_case", fake_discovery_case)
    monkeypatch.setattr(
        subject,
        "build_operating_point_preflight",
        lambda **_kwargs: rejected_preflight,
    )
    monkeypatch.setattr(
        subject,
        "build_cross_state_target_registry",
        lambda **_kwargs: pytest.fail(
            "window registry must not be built after rejection"
        ),
    )

    with pytest.raises(
        RuntimeError, match="no 42-day target registry or incident probe"
    ):
        subject.run_target_discovery(
            output_dir=output_dir,
            manifest=manifest,
            points=points,
            lanes=[_lane()],
            workers=2,
        )

    assert execution_count == 3 * (1 + len(subject.SEEDS)) == 93
    persisted = json.loads(
        (output_dir / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    assert persisted["target_discovery_status"] == "rejected"
    assert persisted["operating_point_preflight_status"] == (
        subject.HOLDOUT_REJECTED_STATUS
    )
    assert persisted["target_registry"] == ""
    assert not (output_dir / "target_discovery" / "target_registry.json").exists()


def test_holdout_validation_precedes_42_day_registry_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_dir = tmp_path / "campaign"
    output_dir.mkdir()
    manifest = {"campaign_signature": "campaign", "engine_sha256": "engine"}
    (output_dir / "campaign_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    points = [
        {"operating_point_id": point_id, "target_service": target}
        for point_id, target in zip(
            subject.OPERATING_POINT_IDS, (1.0, 0.93, 0.80), strict=True
        )
    ]
    events: list[str] = []

    def fake_discovery_case(**_kwargs: object) -> dict[str, object]:
        events.append("baseline")
        return {"shipment_rows": [], "state_service_metrics": {}}

    preflight_unsigned = {
        "schema_version": subject.PREFLIGHT_SCHEMA_VERSION,
        "campaign_signature": "campaign",
        "status": subject.HOLDOUT_ACCEPTED_STATUS,
        "campaign_seed_count": len(subject.SEEDS),
        "campaign_seeds": list(subject.SEEDS),
        "states": [],
    }
    accepted_preflight = {
        **preflight_unsigned,
        "preflight_signature": subject._stable_sha256(preflight_unsigned),
    }

    def fake_preflight(**_kwargs: object) -> dict[str, object]:
        assert events == ["baseline"] * 93
        events.append("signed_holdout_preflight")
        return accepted_preflight

    def fake_registry(**_kwargs: object) -> dict[str, object]:
        assert events[-1] == "signed_holdout_preflight"
        events.append("fixed_42_day_registry")
        unsigned = {
            "schema_version": f"{subject.SCHEMA_VERSION}.target_registry.v4",
            "campaign_signature": "campaign",
            "engine_sha256": "engine",
            "states": list(subject.OPERATING_POINT_IDS),
            "seeds": list(subject.SEEDS),
            "lanes": ["lane_01"],
            "targets": [],
            "all_lane_design_windows_comparable": True,
            "all_lane_holdout_exposures_comparable": True,
            "campaign_exposure_gate_passed": True,
            "exposure_gate_failures": [],
        }
        return {**unsigned, "registry_signature": subject._stable_sha256(unsigned)}

    monkeypatch.setattr(subject, "_execute_target_discovery_case", fake_discovery_case)
    monkeypatch.setattr(subject, "build_operating_point_preflight", fake_preflight)
    monkeypatch.setattr(subject, "build_cross_state_target_registry", fake_registry)

    result = subject.run_target_discovery(
        output_dir=output_dir,
        manifest=manifest,
        points=points,
        lanes=[_lane()],
        workers=2,
    )

    assert events[-2:] == ["signed_holdout_preflight", "fixed_42_day_registry"]
    assert result["schema_version"].endswith("target_registry.v4")
    persisted = json.loads(
        (output_dir / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    assert persisted["target_discovery_status"] == "complete"
    assert persisted["operating_point_preflight_status"] == (
        subject.HOLDOUT_ACCEPTED_STATUS
    )
    assert persisted["target_exposure_comparability_status"] == "accepted"


def test_operating_point_preflight_rejects_zero_demand_in_any_seed() -> None:
    evidence: dict[tuple[str, int], dict[str, object]] = {}
    for point_id, rate in (("op_100", 0.99), ("op_93", 0.93), ("op_80", 0.80)):
        for seed in (subject.TARGET_DESIGN_SEED, *subject.SEEDS):
            demand_091 = 0.0 if seed == subject.TARGET_DESIGN_SEED else 100.0
            evidence[(point_id, seed)] = {
                "state_service_metrics": {
                    "demand_qty_268091": demand_091,
                    "on_due_qty_268091": demand_091 * rate,
                    "demand_qty_268967": 100.0,
                    "on_due_qty_268967": 100.0 * rate,
                    "demand_qty_global": demand_091 + 100.0,
                    "on_due_qty_global": (demand_091 + 100.0) * rate,
                }
            }

    with pytest.raises(ValueError, match="Zero seed-level demand"):
        subject.build_operating_point_preflight(
            manifest={"campaign_signature": "campaign"},
            points=[
                {"operating_point_id": "op_100", "target_service": 1.0},
                {"operating_point_id": "op_93", "target_service": 0.93},
                {"operating_point_id": "op_80", "target_service": 0.80},
            ],
            discovery_evidence=evidence,
            bootstrap_replicates=10,
        )


def test_extract_metrics_keeps_state_service_on_first_720_of_1080_days(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "case"
    data = case_dir / "data"
    summaries = case_dir / "summaries"
    data.mkdir(parents=True)
    summaries.mkdir()
    service_rows = []
    production_rows = []
    for product, factory in subject.PRODUCT_FACTORY.items():
        for day in range(subject.SIMULATION_DAYS):
            service_rows.append(
                {
                    "node_id": subject.protocol.CLIENT_NODE_ID,
                    "item_id": f"item:{product}",
                    "day": day,
                    "demand_qty": 10.0,
                    "required_with_backlog_qty": 10.0,
                    "served_qty": 10.0 if day < subject.STATE_EVALUATION_DAYS else 0.0,
                    "backlog_end_qty": 0.0
                    if day < subject.STATE_EVALUATION_DAYS
                    else 10.0,
                }
            )
            production_rows.append(
                {
                    "node_id": factory,
                    "item_id": f"item:{product}",
                    "day": day,
                    "released_qty": 5.0,
                }
            )

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(data / "production_demand_service_daily.csv", service_rows)
    write_csv(data / "production_output_products_daily.csv", production_rows)
    (data / "production_supplier_shipments_daily.csv").write_text(
        "shipment_id,risk_decision_day\n", encoding="utf-8"
    )
    graph_sha = "a" * 64
    (summaries / "first_simulation_summary.json").write_text(
        json.dumps(
            {
                "input_sha256": graph_sha,
                "sim_days": subject.SIMULATION_DAYS,
                "policy": {
                    "warmup_days": subject.protocol.WARMUP_DAYS,
                    "warmup_boundary_audit": {"core_state_sha256": "b" * 64},
                    "supplier_risk": {
                        "enabled": False,
                        "event_count": 0,
                        "warnings": [],
                    },
                    "supplier_state_dependent_risk": {"enabled": False},
                    "economic_policy": {"supplier_risk_loss_gross_up": False},
                    "initialization_policy": {
                        "seed_open_orders_from_january_snapshot": False
                    },
                },
                "kpis": {},
            }
        ),
        encoding="utf-8",
    )

    metrics, _shipments, _applied, errors, context = subject._extract_metrics(
        case_dir=case_dir,
        manifest={},
        point={"graph_sha256": graph_sha},
        risk_csv=None,
        expected_event_id=None,
    )

    assert errors == []
    assert metrics["service_global_pct"] == pytest.approx(100.0)
    assert metrics["service_output_product_268091_pct"] == pytest.approx(100.0)
    assert metrics["state_evaluation_days"] == 720
    assert metrics["simulation_days"] == 1080
    assert len(context["service_rows"]) == 2160


def test_flatten_populates_absolute_normalized_dose_and_causal_metrics() -> None:
    lane = _lane()
    baseline_window = {
        "day_count": 360,
        "service_268091_pct": 90.0,
        "service_268967_pct": 95.0,
        "service_global_pct": 92.0,
        "demand_qty_268091": 1000.0,
        "demand_qty_268967": 500.0,
        "demand_qty_global": 1500.0,
        "on_due_qty_268091": 900.0,
        "on_due_qty_268967": 475.0,
        "on_due_qty_global": 1375.0,
        "backlog_qty_days_global": 100.0,
        "backlog_qty_days_268091": 80.0,
        "backlog_qty_days_268967": 20.0,
        "max_backlog_qty_global": 20.0,
        "production_released_268091_qty": 800.0,
        "production_released_268967_qty": 400.0,
    }
    incident_window = {
        **baseline_window,
        "service_268091_pct": 80.0,
        "service_global_pct": 85.33333333333333,
        "on_due_qty_268091": 800.0,
        "on_due_qty_global": 1275.0,
        "backlog_qty_days_global": 250.0,
        "backlog_qty_days_268091": 230.0,
        "max_backlog_qty_global": 60.0,
        "production_released_268091_qty": 750.0,
    }
    target = {
        "target_status": "identified_unique_reference_shipment",
        "selection_mode": "single_shipment_day_preferred",
        "reference_kind": "paired_simulated_baseline_shipment_not_observed_supplier_performance",
        "target_expected_delivered_qty": 100.0,
        "baseline_lane_shipped_qty_state_window": 1000.0,
        "target_qty_share_of_lane_state_window": 0.1,
        "target_group_qty_percentile_lane_state_window": 0.8,
        "target_exposure_concentration_flag": "distributed_across_multiple_dispatch_days",
        "impact_window_start_day": 100,
        "impact_window_end_day": 459,
        "impact_window_days": 360,
        "impact_window_fully_observed": True,
        "causal_window_start_day": 130,
        "causal_window_end_day": 339,
        "causal_window_days": 210,
        "causal_window_fully_observed": True,
        "target_selected_independently_by_operating_point": True,
        "baseline_impact_metrics": baseline_window,
        "baseline_causal_metrics": baseline_window,
    }
    evidence = {
        "schema_version": subject.CASE_SCHEMA_VERSION,
        "stage": "incident",
        "baseline_case_signature": "baseline",
        "operating_point_id": "op_93",
        "seed": subject.SEEDS[0],
        "valid": True,
        "lane": vars(lane),
        "mechanism": vars(subject.MECHANISMS[1]),
        "target": target,
        "metrics": {
            "service_output_product_268091_pct": 93.0,
            "service_output_product_268967_pct": 93.0,
            "service_global_pct": 93.0,
            "impact_window_metrics": incident_window,
            "causal_window_metrics": incident_window,
        },
        "incident_proof": {
            "incident_physically_exercised": True,
            "quantity_shortfall_qty": 50.0,
        },
    }

    row = subject._flatten_metric_row(evidence, baseline_by_signature={"baseline": {}})

    assert row["causal_service_loss_fed_product_pp"] == pytest.approx(10.0)
    assert row["causal_on_due_loss_fed_product_qty"] == pytest.approx(100.0)
    assert row["causal_on_due_loss_fed_product_share_of_demand"] == pytest.approx(0.1)
    assert row["causal_backlog_qty_days_delta"] == pytest.approx(150.0)
    assert row["causal_backlog_qty_days_per_demand_unit"] == pytest.approx(0.1)
    assert row["causal_backlog_qty_days_fed_product_delta"] == pytest.approx(150.0)
    assert row["causal_backlog_relative_load_fed_product"] == pytest.approx(
        150.0 / (1000.0 * 360.0)
    )
    assert row["causal_production_loss_fed_product_qty"] == pytest.approx(50.0)
    assert row["target_qty_share_of_lane_state_window"] == pytest.approx(0.1)
    assert row["quantity_shortfall_share_of_target"] == pytest.approx(0.5)


def test_trace_rejects_any_non_neutral_availability_effect() -> None:
    lane = _lane()
    baseline = _shipment(lane, shipment_id="SHIP", decision_day=10)
    target = subject.select_unique_reference_shipment([baseline], lane=lane)
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "planned_delivery_shortfall"
    )
    risk = subject.build_risk_row(
        point_id="op_93",
        seed=subject.SEEDS[0],
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    incident = _shipment(
        lane,
        shipment_id="SHIP",
        decision_day=10,
        shipped_qty=50.0,
        risk_event_ids=str(risk["event_id"]),
    )
    applied = _application_row(str(risk["event_id"]), 10, reliability=0.5)
    applied["availability_multiplier"] = 0.5
    proof, errors = subject.validate_incident_trace(
        mechanism=mechanism,
        lane=lane,
        target=target,
        risk_row=risk,
        shipment_rows=[incident],
        applied_rows=[applied],
    )
    assert not proof["incident_physically_exercised"]
    assert "availability multiplier is not neutral" in errors


def test_incident_finalization_consumes_compact_pruned_probe_without_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane = _lane()
    seed = subject.SEEDS[0]
    target = subject.select_unique_reference_shipment(
        [_shipment(lane, shipment_id="BASE", decision_day=100, arrival_day=150)],
        lane=lane,
        days=None,
        forced_decision_day=100,
        target_window_days=subject.INCIDENT_DISRUPTION_DAYS,
    )
    target.update(
        subject._incident_horizon_from_trace(
            target=target,
            tagged_rows=[
                _shipment(
                    lane,
                    shipment_id="AFFECTED",
                    decision_day=100,
                    arrival_day=150,
                )
            ],
        )
    )

    def window(start: int, end: int) -> dict[str, float | int | bool]:
        return {
            "start_day": start,
            "end_day": end,
            "day_count": end - start + 1,
            "fully_observed": True,
            "demand_qty_268091": 1000.0,
            "demand_qty_268967": 500.0,
            "demand_qty_global": 1500.0,
            "on_due_qty_268091": 900.0,
            "on_due_qty_268967": 450.0,
            "on_due_qty_global": 1350.0,
            "service_268091_pct": 90.0,
            "service_268967_pct": 90.0,
            "service_global_pct": 90.0,
            "backlog_qty_days_268091": 10.0,
            "backlog_qty_days_268967": 5.0,
            "backlog_qty_days_global": 15.0,
            "max_backlog_qty_global": 2.0,
            "production_released_268091_qty": 800.0,
            "production_released_268967_qty": 400.0,
        }

    impact = window(
        int(target["impact_window_start_day"]),
        int(target["impact_window_end_day"]),
    )
    causal = window(
        int(target["causal_window_start_day"]),
        int(target["causal_window_end_day"]),
    )
    empty_prefix = subject._shipment_trace_signature(
        [], end_day_exclusive=int(target["target_window_start_day"])
    )
    target["baseline_pre_incident_shipment_trace_sha256"] = empty_prefix
    target["baseline_impact_metrics"] = impact
    target["baseline_causal_metrics"] = causal
    mechanism = next(
        item for item in subject.MECHANISMS if item.key == "planned_delivery_shortfall"
    )
    point = {
        "operating_point_id": "op_93",
        "operating_point_service_pct": 93.0,
        "graph_sha256": "graph",
        "supplier_floors_sha256": "",
        "factory_capacities_sha256": "",
    }
    manifest = {
        "campaign_signature": "campaign",
        "engine_sha256": "engine",
        "target_registry_signature": "registry",
        "active_shard_id": "shard",
    }
    risk_row = subject.build_risk_row(
        point_id="op_93",
        seed=seed,
        lane=lane,
        mechanism=mechanism,
        target=target,
    )
    key = subject._case_key(
        point_id="op_93",
        seed=seed,
        stage="incident",
        lane_id=lane.lane_id,
        mechanism=mechanism.key,
    )
    risk_path = tmp_path / "inputs" / "risk_events" / f"{key}.csv"
    subject.campaign_core.write_risk_csv(risk_path, [risk_row])
    simulation_days = int(target["required_simulation_days"])
    prepared = {
        "campaign_signature": "campaign",
        "operating_point_id": "op_93",
        "seed": seed,
        "lane_id": lane.lane_id,
        "mechanism": mechanism.key,
        "final_simulation_days": simulation_days,
        "risk_csv_sha256": subject._sha256_file(risk_path),
        "risk_row": risk_row,
        "case_artifacts_pruned": True,
        "metrics": {
            "simulation_days": simulation_days,
            "warmup_core_state_sha256": "warmup",
            "impact_window_metrics": impact,
            "causal_window_metrics": causal,
        },
        "validation_errors": [],
        "incident_proof": {"incident_physically_exercised": True},
        "incident_pre_incident_shipment_trace_sha256": empty_prefix,
        "probe_evidence_signature": "probe",
    }
    baseline = {
        "case_signature": "baseline",
        "metrics": {"warmup_core_state_sha256": "warmup"},
    }
    monkeypatch.setattr(
        subject,
        "_run_engine",
        lambda **_kwargs: pytest.fail("compact probe must not rerun the engine"),
    )

    evidence = subject._execute_incident(
        shard_dir=tmp_path,
        manifest=manifest,
        point=point,
        lane=lane,
        mechanism=mechanism,
        seed=seed,
        target=target,
        baseline_evidence=baseline,
        reuse_roots=(),
        prepared_probe=prepared,
    )

    assert evidence["valid"] is True
    assert evidence["run_dir"] == ""
    assert evidence["prepared_probe_evidence_signature"] == "probe"
    assert evidence["incident_proof"]["pre_incident_shipment_trace_match"] is True


def test_evidence_reuse_rejects_tampering_and_wrong_schema(tmp_path: Path) -> None:
    manifest = {
        "campaign_signature": "campaign",
        "engine_sha256": "engine",
    }
    evidence = {
        "schema_version": subject.CASE_SCHEMA_VERSION,
        "campaign_signature": "campaign",
        "engine_sha256": "engine",
        "case_key": "case",
        "case_signature": "case-signature",
        "status": "valid",
        "valid": True,
        "quality_branch_included": False,
        "availability_incident_included": False,
        "supplier_state_dependent_risks_enabled": False,
    }
    evidence["evidence_signature"] = subject._evidence_signature(evidence)
    subject._validate_evidence(
        evidence,
        manifest=manifest,
        case_key="case",
        case_signature="case-signature",
    )

    evidence["valid"] = False
    with pytest.raises(ValueError, match="evidence_signature"):
        subject._validate_evidence(
            evidence,
            manifest=manifest,
            case_key="case",
            case_signature="case-signature",
        )

    old = dict(evidence)
    old["schema_version"] = "historical.v1"
    old["evidence_signature"] = subject._evidence_signature(old)
    with pytest.raises(ValueError, match="schema_version"):
        subject._validate_evidence(
            old,
            manifest=manifest,
            case_key="case",
            case_signature="case-signature",
        )


def test_progress_schema_matches_monitor_contract(tmp_path: Path) -> None:
    tracker = subject.ProgressTracker(
        shard_dir=tmp_path,
        manifest={"campaign_signature": "signature"},
        shard_id="op_100__seed_block_01",
        point_id="op_100",
        block_number=1,
        seeds=subject.seed_block(1),
        planned_count=185,
    )
    tracker.initialize([])
    tracker.start_case("case")
    tracker.finish_case("case", valid=True)
    tracker.close("running")

    payload = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert {
        "planned_case_count",
        "completed_case_count",
        "failed_case_count",
        "running_case_keys",
        "updated_at_utc",
        "elapsed_seconds",
        "eta_seconds",
    } <= set(payload)
    assert payload["planned_case_count"] == 185
    assert payload["completed_case_count"] == 1


def test_smoke_shard_wires_probes_max_baseline_horizon_and_idempotent_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lanes = [_lane(1), _lane(2)]
    selected_lane = lanes[0]
    seed = subject.SEEDS[0]
    engine = tmp_path / "engine.py"
    profile = tmp_path / "profile.json"
    graph = tmp_path / "graph.json"
    engine.write_text("# engine\n", encoding="utf-8")
    profile.write_text("{}", encoding="utf-8")
    graph.write_text("{}", encoding="utf-8")
    point = {
        "operating_point_id": "op_100",
        "operating_point_service_pct": 99.0,
        "graph": str(graph),
        "graph_sha256": subject._sha256_file(graph),
        "supplier_floors": "",
        "supplier_floors_sha256": "",
        "factory_capacities": "",
        "factory_capacities_sha256": "",
    }
    manifest = {
        "campaign_signature": "campaign",
        "engine": str(engine),
        "engine_sha256": subject._sha256_file(engine),
        "engine_profile": str(profile),
        "engine_profile_sha256": subject._sha256_file(profile),
    }
    registry_targets = []
    for lane in lanes:
        target = subject.select_unique_reference_shipment(
            [_shipment(lane, shipment_id=f"BASE-{lane.lane_id}", decision_day=100)],
            lane=lane,
            days=None,
            forced_decision_day=100,
            target_window_days=subject.INCIDENT_DISRUPTION_DAYS,
        )
        registry_targets.append(
            {
                "operating_point_id": "op_100",
                "seed": seed,
                "lane_id": lane.lane_id,
                **target,
            }
        )
    registry = {
        "registry_signature": "registry",
        # A real smoke consumes the full signed registry.  The selected-lane
        # projection must ignore rather than reject the other lane rows.
        "targets": registry_targets,
    }
    monkeypatch.setattr(subject, "load_target_registry", lambda **_kwargs: registry)

    store: dict[str, dict[str, object]] = {}
    probe_calls: list[tuple[str, int]] = []
    baseline_horizons: list[int] = []
    incident_calls: list[tuple[str, int]] = []

    def fake_load_or_reuse(**kwargs: object) -> dict[str, object] | None:
        return store.get(str(kwargs["case_key"]))

    def fake_refresh_shard_outputs(
        **_kwargs: object,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        rows = list(store.values())
        return rows, [{"case_key": row["case_key"]} for row in rows]

    def fake_prepare_probe(**kwargs: object) -> dict[str, object]:
        mechanism = kwargs["mechanism"]
        assert isinstance(mechanism, subject.Mechanism)
        horizon = 900 if mechanism.key == "transport_delay" else 850
        probe_calls.append((mechanism.key, horizon))
        registered = dict(kwargs["registered_target"])
        return {
            "final_simulation_days": horizon,
            "case_dir": str(tmp_path / f"pruned-{mechanism.key}"),
            "incident_window": {
                "impact_window_start_day": registered["impact_window_start_day"],
                "impact_window_end_day": registered["impact_window_end_day"],
                "impact_window_days": subject.IMPACT_WINDOW_DAYS,
                "impact_window_fully_observed": True,
                "causal_window_start_day": 110,
                "causal_window_end_day": horizon - 1,
                "causal_window_days": horizon - 110,
                "causal_window_defined": True,
                "causal_window_fully_observed": True,
                "required_simulation_days": horizon,
            },
        }

    def fake_execute_baseline(**kwargs: object) -> dict[str, object]:
        horizon = int(kwargs["simulation_days"])
        baseline_horizons.append(horizon)
        targets = []
        for registered in kwargs["registered_targets"]:
            target = dict(registered)
            target["baseline_pre_incident_shipment_trace_sha256"] = "trace"
            target["baseline_causal_metrics_by_mechanism"] = {
                key: {"start_day": window["causal_window_start_day"]}
                for key, window in target["incident_windows"].items()
            }
            targets.append(target)
        key = subject._case_key(point_id="op_100", seed=seed, stage="baseline")
        evidence: dict[str, object] = {
            "case_key": key,
            "case_signature": "baseline-signature",
            "seed": seed,
            "stage": "baseline",
            "valid": True,
            "shipment_targets": targets,
        }
        store[key] = evidence
        return evidence

    def fake_execute_incident(**kwargs: object) -> dict[str, object]:
        mechanism = kwargs["mechanism"]
        target = kwargs["target"]
        prepared = kwargs["prepared_probe"]
        assert isinstance(mechanism, subject.Mechanism)
        assert int(target["required_simulation_days"]) == int(
            prepared["final_simulation_days"]
        )
        incident_calls.append((mechanism.key, int(target["required_simulation_days"])))
        key = subject._case_key(
            point_id="op_100",
            seed=seed,
            stage="incident",
            lane_id=selected_lane.lane_id,
            mechanism=mechanism.key,
        )
        evidence: dict[str, object] = {
            "case_key": key,
            "case_signature": f"incident-{mechanism.key}",
            "seed": seed,
            "stage": "incident",
            "valid": True,
        }
        store[key] = evidence
        return evidence

    monkeypatch.setattr(subject, "_load_or_reuse_evidence", fake_load_or_reuse)
    monkeypatch.setattr(subject, "refresh_shard_outputs", fake_refresh_shard_outputs)
    monkeypatch.setattr(subject, "_prepare_incident_probe", fake_prepare_probe)
    monkeypatch.setattr(subject, "_execute_baseline", fake_execute_baseline)
    monkeypatch.setattr(subject, "_execute_incident", fake_execute_incident)

    kwargs = {
        "output_dir": tmp_path / "campaign",
        "manifest": manifest,
        "points": [point],
        "lanes": lanes,
        "point_id": "op_100",
        "block_number": 1,
        "workers": 1,
        "smoke_seed": seed,
        "smoke_lane_id": selected_lane.lane_id,
    }
    first = subject.run_shard(**kwargs)
    second = subject.run_shard(**kwargs)

    assert first["status"] == second["status"] == "complete"
    assert baseline_horizons == [900]
    assert sorted(incident_calls) == [
        ("planned_delivery_shortfall", 850),
        ("transport_delay", 900),
    ]
    assert len(probe_calls) == 4
    assert len(store) == 3
