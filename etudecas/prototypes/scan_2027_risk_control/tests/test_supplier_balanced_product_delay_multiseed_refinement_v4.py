from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as v4,
)


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_shipment_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "day",
        "shipment_id",
        "risk_decision_day",
        "edge_id",
        "pulled_qty",
        "shipped_qty",
        "lead_days",
        "arrival_day",
        "reliability",
        "uom",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _signed(
    path: Path, unsigned: dict[str, Any], signature_field: str
) -> dict[str, Any]:
    payload = {**unsigned, signature_field: v4.stable_sha256(unsigned)}
    _write(path, payload)
    return payload


def _metrics(service: float, demand: float = 100.0) -> dict[str, float]:
    return {
        "system_on_due_service": service,
        "on_due_service_268091": service,
        "on_due_service_268967": service,
        "demand_qty_268091": demand,
        "on_due_qty_268091": demand * service,
        "demand_qty_268967": demand,
        "on_due_qty_268967": demand * service,
    }


def _op80_grid_rows() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "offset_days_268091": left,
            "offset_days_268967": right,
        }
        for key, left, right in v4.OP80_GRID
    ]


def _changes(left: float, right: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for product, factory, offset in (
        ("268091", "M-1810", left),
        ("268967", "M-1430", right),
    ):
        for index in range(1, 10):
            rows.append(
                {
                    "target_product_id": product,
                    "factory_id": factory,
                    "edge_id": f"edge-{product}-{index:02d}",
                    "supplier_id": f"S-{product}-{index:02d}",
                    "item_id": f"item:{product}:{index:02d}",
                    "offset_days": offset,
                }
            )
    return rows


def _synthetic_campaign_lanes() -> list[dict[str, Any]]:
    return [
        {
            "lane_id": f"lane_{row['target_product_id']}_{index:02d}",
            "supplier_id": row["supplier_id"],
            "item_id": row["item_id"],
            "dst_node_id": row["factory_id"],
            "edge_id": row["edge_id"],
            "target_product_id": row["target_product_id"],
            "planned_lead_days": (
                10.0 if row["target_product_id"] == "268091" else 20.0
            ),
        }
        for index, row in enumerate(_changes(0.0, 0.0), start=1)
    ]


def _source_campaign(tmp_path: Path, *, op80_service: float = 0.80) -> Path:
    source_dir = tmp_path / "source_campaign"
    v3_plan_dir = tmp_path / "v3_plan"
    inputs = tmp_path / "inputs"
    for name in ("engine.py", "profile.json", "runner.py"):
        path = inputs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic {name}\n", encoding="utf-8")

    base_graph = {
        "edges": [
            {
                "id": row["edge_id"],
                "from": row["supplier_id"],
                "to": row["factory_id"],
                "items": [row["item_id"]],
                "lead_time": {
                    "mean": 10.0 if row["target_product_id"] == "268091" else 20.0
                },
                "delay_step_limit": {
                    "value": 20 if row["target_product_id"] == "268091" else 40
                },
            }
            for row in _changes(0.0, 0.0)
        ]
    }
    state_graphs: dict[str, Path] = {}
    for point_id in v4.TARGETS:
        path = source_dir / "graphs" / f"{point_id}.json"
        _write(path, base_graph)
        state_graphs[point_id] = path

    v3_plan_unsigned = {field: None for field in v4.V3_PLAN_SIGNED_FIELDS}
    v3_plan_unsigned.update(
        {
            "schema_version": v4.V3_PLAN_SCHEMA_VERSION,
            "status": "frozen_before_v3_execution",
            "interpretation": "synthetic test source",
            "source": {},
            "source_hashes": {},
            "cohorts": {},
            "candidates": [],
            "candidate_design": {},
            "inventory": {
                "op100_reference": {"changes": _changes(0.0, 0.0)},
                "op93_refine_7_81": {"changes": _changes(7.0, 81.0)},
                "op80_refine_v3_16p5_94": {"changes": _changes(16.5, 94.0)},
            },
            "cases": [],
            "expected_case_count": 0,
            "new_case_count": 0,
            "reused_case_count": 0,
            "selection_contract": {},
            "holdout_contract": {},
            "execution_contract": {},
        }
    )
    v3_plan = {
        **v3_plan_unsigned,
        "plan_signature": v4.stable_sha256(v3_plan_unsigned),
    }
    v3_plan_path = v3_plan_dir / "refinement_plan.json"
    _write(v3_plan_path, v3_plan)

    points = _signed(
        v3_plan_dir / "selected_operating_points.json",
        {
            "schema_version": v4.V3_POINTS_SCHEMA_VERSION,
            "status": v4.V3_POINTS_STATUS,
            "operating_points": [],
        },
        "artifact_signature",
    )
    selection = _signed(
        v3_plan_dir / "selection.json",
        {"schema_version": "synthetic.selection", "status": "selected"},
        "selection_signature",
    )

    states = [
        {
            "operating_point_id": point_id,
            "graph": str(state_graphs[point_id]),
            "graph_sha256": v4.sha256_file(state_graphs[point_id]),
        }
        for point_id in v4.TARGETS
    ]
    design = {
        "schema_version": v4.V3_CAMPAIGN_SCHEMA_VERSION,
        "operating_points_producer": "v3_refinement",
        "operating_points_schema_version": v4.V3_POINTS_SCHEMA_VERSION,
        "operating_points_input_status": v4.V3_POINTS_STATUS,
        "operating_points_cohorts": {
            "design": list(v4.SOURCE_DESIGN_SEEDS),
            "calibration": list(v4.SOURCE_CALIBRATION_SEEDS),
            "holdout_sealed": list(v4.DEVELOPMENT_SEEDS),
        },
        "seeds": list(v4.DEVELOPMENT_SEEDS),
        "operating_points_source": str(v3_plan_dir / "selected_operating_points.json"),
        "operating_points_source_sha256": v4.sha256_file(
            v3_plan_dir / "selected_operating_points.json"
        ),
        "operating_points_artifact_signature": points["artifact_signature"],
        "operating_points_selection": str(v3_plan_dir / "selection.json"),
        "operating_points_selection_sha256": v4.sha256_file(
            v3_plan_dir / "selection.json"
        ),
        "operating_points_selection_signature": selection["selection_signature"],
        "operating_points_calibration_plan": str(v3_plan_path),
        "operating_points_calibration_plan_sha256": v4.sha256_file(v3_plan_path),
        "operating_points_calibration_plan_signature": v3_plan["plan_signature"],
        "engine": str(inputs / "engine.py"),
        "engine_sha256": v4.sha256_file(inputs / "engine.py"),
        "engine_profile": str(inputs / "profile.json"),
        "engine_profile_sha256": v4.sha256_file(inputs / "profile.json"),
        "runner": str(inputs / "runner.py"),
        "runner_sha256": v4.sha256_file(inputs / "runner.py"),
        "lanes": _synthetic_campaign_lanes(),
        "states": states,
    }
    campaign_signature = v4.stable_sha256(design)
    services = {"op_100": 1.0, "op_93": 0.95, "op_80": op80_service}
    evidence_dir = source_dir / "target_discovery" / "evidence"
    for point_id, service in services.items():
        state = next(row for row in states if row["operating_point_id"] == point_id)
        for seed in (*v4.SOURCE_DESIGN_SEEDS, *v4.DEVELOPMENT_SEEDS):
            discovery_signature = v4.stable_sha256(
                {
                    "campaign_signature": campaign_signature,
                    "engine_sha256": design["engine_sha256"],
                    "engine_profile_sha256": design["engine_profile_sha256"],
                    "point_id": point_id,
                    "graph_sha256": state["graph_sha256"],
                    "seed": seed,
                    "simulation_days": v4.SERVICE_DAYS,
                    "purpose": "cross_state_42d_target_discovery",
                }
            )
            unsigned = {
                "schema_version": (
                    f"{v4.V3_CAMPAIGN_SCHEMA_VERSION}.target_discovery.case.v1"
                ),
                "campaign_signature": campaign_signature,
                "engine_sha256": design["engine_sha256"],
                "operating_point_id": point_id,
                "seed": seed,
                "simulation_days": v4.SERVICE_DAYS,
                "discovery_signature": discovery_signature,
                "state_service_metrics": _metrics(service),
            }
            _signed(
                evidence_dir / f"{point_id}__target_discovery__seed_{seed}.json",
                unsigned,
                "evidence_signature",
            )

    ordering = {"global": True, "268091": True, "268967": True}
    state_rows = []
    for point_id, service in services.items():
        if point_id == "op_100":
            individually_accepted = service >= v4.REFERENCE_MINIMUM
        else:
            low, high = v4.OUTER_BANDS[point_id]
            individually_accepted = low <= service <= high and service < 0.995
        state_rows.append(
            {
                "operating_point_id": point_id,
                "service_global_ratio_of_sums_pct": 100.0 * service,
                "service_global_seed_median_pct": 100.0 * service,
                "service_268091_ratio_of_sums_pct": 100.0 * service,
                "service_268967_ratio_of_sums_pct": 100.0 * service,
                "accepted": individually_accepted,
            }
        )
    preflight = _signed(
        source_dir / "target_discovery" / "operating_point_preflight.json",
        {
            "schema_version": v4.V3_PREFLIGHT_SCHEMA_VERSION,
            "campaign_signature": campaign_signature,
            "status": v4.V3_REJECTED_STATUS,
            "campaign_seeds": list(v4.DEVELOPMENT_SEEDS),
            "holdout_used_once_without_retuning": True,
            "no_incident_probe_before_holdout_acceptance": True,
            "bootstrap": {
                "method": "paired_common_seed_resampling",
                "replicates": 10_000,
                "seed": v4.SOURCE_PREFLIGHT_BOOTSTRAP_SEED,
            },
            "ordering_valid": True,
            "pooled_ordering_by_measure": ordering,
            "seed_ordering_valid": True,
            "joint_seed_order_count": 30,
            "joint_seed_order_required": 24,
            "states": state_rows,
        },
        "preflight_signature",
    )
    progress = {
        "schema_version": (
            f"{v4.V3_CAMPAIGN_SCHEMA_VERSION}.target_discovery.progress.v1"
        ),
        "campaign_signature": campaign_signature,
        "status": "failed_operating_point_preflight",
        "planned": 93,
        "completed": 93,
        "failed": 0,
        "running": 0,
        "design_baselines_completed": 3,
        "holdout_baselines_completed": 90,
        "incident_probes_started": False,
    }
    _write(source_dir / "target_discovery" / "progress.json", progress)
    manifest = {
        **design,
        "campaign_signature": campaign_signature,
        "target_discovery_status": "rejected",
        "operating_point_preflight": str(
            source_dir / "target_discovery" / "operating_point_preflight.json"
        ),
        "operating_point_preflight_sha256": v4.sha256_file(
            source_dir / "target_discovery" / "operating_point_preflight.json"
        ),
        "operating_point_preflight_signature": preflight["preflight_signature"],
        "operating_point_preflight_status": v4.V3_REJECTED_STATUS,
        "target_registry": "",
        "target_registry_sha256": "",
        "target_registry_signature": "",
    }
    manifest_path = source_dir / "campaign_manifest.json"
    _write(manifest_path, manifest)
    return manifest_path


def _prepared_keep_plan(tmp_path: Path) -> tuple[Path, Path]:
    source = _source_campaign(tmp_path)
    decision = tmp_path / "op80_decision.json"
    v4.write_op80_decision(
        decision,
        source_campaign_manifest=source,
        mode="keep",
        rationale="The 30 development seeds satisfy the complete V4 inner contract.",
    )
    plan = tmp_path / "v4_plan"
    v4.prepare_plan(plan, source_campaign_manifest=source, op80_decision_path=decision)
    return plan, source


def _rewrite_source_with_op80_loo_failure(source: Path) -> None:
    first, second = v4.DEVELOPMENT_SEEDS[:2]
    for point_id in v4.TARGETS:
        for seed in v4.DEVELOPMENT_SEEDS:
            path = (
                source.parent
                / "target_discovery"
                / "evidence"
                / f"{point_id}__target_discovery__seed_{seed}.json"
            )
            payload = json.loads(path.read_text(encoding="utf-8"))
            demand = 100.0 if seed in {first, second} else 1.0
            service = {"op_100": 1.0, "op_93": 0.95, "op_80": 0.80}[point_id]
            if point_id == "op_80" and seed == first:
                service = 0.60
            elif point_id == "op_80" and seed == second:
                service = 1.0
            payload["state_service_metrics"] = _metrics(service, demand)
            unsigned = dict(payload)
            unsigned.pop("evidence_signature")
            payload["evidence_signature"] = v4.stable_sha256(unsigned)
            _write(path, payload)
    preflight_path = (
        source.parent / "target_discovery" / "operating_point_preflight.json"
    )
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight["joint_seed_order_count"] = 29
    unsigned_preflight = dict(preflight)
    unsigned_preflight.pop("preflight_signature")
    preflight["preflight_signature"] = v4.stable_sha256(unsigned_preflight)
    _write(preflight_path, preflight)
    manifest = json.loads(source.read_text(encoding="utf-8"))
    manifest["operating_point_preflight_sha256"] = v4.sha256_file(preflight_path)
    manifest["operating_point_preflight_signature"] = preflight["preflight_signature"]
    _write(source, manifest)


def test_seed_generation_is_reproducible_disjoint_and_lazy() -> None:
    assert v4.generate_holdout_seeds() == v4.EXPECTED_HOLDOUT_SEEDS
    assert v4.seed_csv_sha256(v4.EXPECTED_HOLDOUT_SEEDS) == (v4.HOLDOUT_SEED_CSV_SHA256)
    incident, digest = v4.derive_domain_seed(v4.INCIDENT_DESIGN_SEED_DOMAIN, 1)
    assert (incident, digest) == (
        v4.INCIDENT_DESIGN_SEED,
        v4.INCIDENT_DESIGN_MESSAGE_SHA256,
    )
    all_known = set(
        v4.SOURCE_DESIGN_SEEDS + v4.SOURCE_CALIBRATION_SEEDS + v4.DEVELOPMENT_SEEDS
    )
    assert len(v4.EXPECTED_HOLDOUT_SEEDS) == len(set(v4.EXPECTED_HOLDOUT_SEEDS)) == 30
    assert not all_known.intersection(v4.EXPECTED_HOLDOUT_SEEDS)
    assert v4.INCIDENT_DESIGN_SEED not in all_known | set(v4.EXPECTED_HOLDOUT_SEEDS)

    code = (
        "import sys; "
        "import etudecas.prototypes.scan_2027_risk_control."
        "supplier_balanced_product_delay_multiseed_refinement_v4; "
        "assert 'etudecas.prototypes.scan_2027_risk_control."
        "supplier_balanced_product_delay_calibration' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_write_json_retries_transient_windows_replace_with_unique_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "atomic.json"
    real_replace = os.replace
    replace_calls: list[tuple[Path, Path]] = []
    sleeps: list[float] = []

    def transient_replace(source: str | bytes, destination: str | bytes) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        replace_calls.append((source_path, destination_path))
        if len(replace_calls) < 3:
            raise PermissionError("synthetic transient Windows contention")
        real_replace(source, destination)

    monkeypatch.setattr(v4, "_IS_WINDOWS", True)
    monkeypatch.setattr(v4.os, "replace", transient_replace)
    monkeypatch.setattr(v4.time, "sleep", sleeps.append)

    v4._write_json(target, {"generation": 1})
    first_temporary = replace_calls[0][0]
    assert [source for source, _destination in replace_calls[:3]] == [
        first_temporary,
        first_temporary,
        first_temporary,
    ]
    assert sleeps == [
        v4._JSON_REPLACE_BACKOFF_SECONDS,
        v4._JSON_REPLACE_BACKOFF_SECONDS * 2,
    ]
    assert json.loads(target.read_text(encoding="utf-8")) == {"generation": 1}
    assert not first_temporary.exists()

    v4._write_json(target, {"generation": 2})
    second_temporary = replace_calls[3][0]
    assert second_temporary != first_temporary
    assert json.loads(target.read_text(encoding="utf-8")) == {"generation": 2}
    assert not list(tmp_path.glob(".atomic.json.tmp-*"))


def test_write_json_persistent_windows_replace_failure_preserves_target_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "atomic.json"
    target.write_text('{"generation": "old"}\n', encoding="utf-8")
    replace_calls: list[tuple[Path, Path]] = []
    sleeps: list[float] = []

    def persistent_replace(source: str | bytes, destination: str | bytes) -> None:
        replace_calls.append((Path(source), Path(destination)))
        raise PermissionError("synthetic persistent Windows contention")

    monkeypatch.setattr(v4, "_IS_WINDOWS", True)
    monkeypatch.setattr(v4.os, "replace", persistent_replace)
    monkeypatch.setattr(v4.time, "sleep", sleeps.append)

    with pytest.raises(PermissionError, match="persistent Windows contention"):
        v4._write_json(target, {"generation": "new"})

    assert len(replace_calls) == v4._JSON_REPLACE_MAX_ATTEMPTS
    assert sleeps == [
        v4._JSON_REPLACE_BACKOFF_SECONDS * (2**attempt)
        for attempt in range(v4._JSON_REPLACE_MAX_ATTEMPTS - 1)
    ]
    assert len({source for source, _destination in replace_calls}) == 1
    assert json.loads(target.read_text(encoding="utf-8")) == {"generation": "old"}
    assert not list(tmp_path.glob(".atomic.json.tmp-*"))


def test_source_validation_recomputes_all_proofs_and_detects_tamper(
    tmp_path: Path,
) -> None:
    source = _source_campaign(tmp_path)
    validated = v4.validate_rejected_v3_campaign(source)
    assert validated["target_discovery_evidence"]["case_count"] == 93
    assert validated["target_discovery_evidence"]["acceptance_case_count"] == 90
    assert validated["preflight_state_acceptance"]["development_inner"]["op_80"]

    evidence = (
        source.parent
        / "target_discovery"
        / "evidence"
        / f"op_93__target_discovery__seed_{v4.DEVELOPMENT_SEEDS[0]}.json"
    )
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["state_service_metrics"]["on_due_qty_268091"] -= 1.0
    _write(evidence, payload)
    with pytest.raises(v4.V4ProtocolError):
        v4.validate_rejected_v3_campaign(source)


def test_decision_plan_and_canonical_validation_without_execution(
    tmp_path: Path,
) -> None:
    source = _source_campaign(tmp_path)
    absent_plan = tmp_path / "absent_plan"
    with pytest.raises(v4.V4ProtocolError, match="decision"):
        v4.prepare_plan(absent_plan, source_campaign_manifest=source)
    assert not absent_plan.exists()

    decision = tmp_path / "decision.json"
    v4.write_op80_decision(
        decision,
        source_campaign_manifest=source,
        mode="keep",
        rationale="Complete inner-band pass on 30 development seeds.",
    )
    plan = tmp_path / "plan"
    v4.prepare_plan(plan, source_campaign_manifest=source, op80_decision_path=decision)
    validated = v4.validate_plan(plan)
    assert [
        (row["offset_days_268091"], row["offset_days_268967"])
        for row in validated.manifest["candidate_design"]["op93_exact_grid"]
    ] == [(7.0, 81.0), (8.0, 80.5), (8.0, 81.5), (8.5, 80.5), (8.5, 81.5)]
    assert validated.manifest["expected_development_case_count"] == 210
    assert validated.manifest["reused_development_case_count"] == 90
    assert validated.manifest["new_development_case_count"] == 120
    assert not (tmp_path / "run").exists()
    runtime = validated.manifest["runtime_dependencies"]
    assert runtime["file_count"] == len(runtime["files"]) == 44
    assert [row["path"] for row in runtime["files"]] == list(
        v4.RUNTIME_DEPENDENCY_RELATIVE_PATHS
    )
    assert runtime["aggregate_sha256"] == v4.stable_sha256(
        {
            "schema_version": v4.RUNTIME_DEPENDENCY_SCHEMA_VERSION,
            "file_count": 44,
            "files": runtime["files"],
        }
    )
    decision_provenance = validated.manifest["candidate_design"]["op80_decision"]
    assert set(decision_provenance) == {
        "artifact_signature",
        "payload",
        "sha256",
    }
    assert decision_provenance["sha256"] == v4.sha256_file(plan / "op80_decision.json")
    decision.unlink()
    validated = v4.validate_plan(plan)
    assert validated.manifest["candidate_design"]["op80_decision"] == (
        decision_provenance
    )
    assert validated.manifest["selection_contract"]["pair_tie_break_v4"][1:3] == [
        "maximum_joint_strict_order_count_global_pf091_pf967",
        "maximum_strict_order_count_pf967",
    ]

    high = {
        "candidate": {
            "offset_days_268091": 8.0,
            "offset_days_268967": 80.5,
        },
        "maximum_absolute_global_target_error": 0.01,
        "product_service_gap_pp": 1.0,
        "global_service_iqr": 0.02,
    }
    low = {
        "candidate": {
            "offset_days_268091": 17.0,
            "offset_days_268967": 95.0,
        },
        "maximum_absolute_global_target_error": 0.01,
        "product_service_gap_pp": 1.0,
        "global_service_iqr": 0.02,
    }
    assert v4._pair_score(
        high, low, joint_order_count=25, pf967_order_count=25
    ) < v4._pair_score(high, low, joint_order_count=24, pf967_order_count=30)
    assert v4._pair_score(
        high, low, joint_order_count=25, pf967_order_count=26
    ) < v4._pair_score(high, low, joint_order_count=25, pf967_order_count=25)

    manifest_path = plan / "refinement_plan.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["execution_contract"]["quality_incident"] = True
    unsigned = dict(manifest)
    unsigned.pop("plan_signature")
    manifest["plan_signature"] = v4.stable_sha256(unsigned)
    _write(manifest_path, manifest)
    with pytest.raises(v4.V4ProtocolError, match="contract"):
        v4.validate_plan(plan)


def test_runtime_dependency_change_fails_closed_but_fixture_validation_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _source = _prepared_keep_plan(tmp_path)
    frozen = json.loads((plan / "refinement_plan.json").read_text(encoding="utf-8"))[
        "runtime_dependencies"
    ]
    changed = json.loads(json.dumps(frozen))
    changed["files"][0]["sha256"] = "0" * 64
    changed_unsigned = {
        "schema_version": changed["schema_version"],
        "file_count": changed["file_count"],
        "files": changed["files"],
    }
    changed["aggregate_sha256"] = v4.stable_sha256(changed_unsigned)
    monkeypatch.setattr(
        v4,
        "_runtime_dependency_inventory_from_worktree",
        lambda: changed,
    )

    with pytest.raises(v4.V4ProtocolError, match="runtime dependency changed"):
        v4.validate_plan(plan)
    isolated = v4.validate_plan(plan, verify_runtime_dependencies=False)
    assert isolated.manifest["runtime_dependencies"] == frozen


def test_official_holdout_shipment_trace_is_filtered_signed_and_recoverable(
    tmp_path: Path,
) -> None:
    plan_dir, _source = _prepared_keep_plan(tmp_path)
    plan = v4.validate_plan(plan_dir)
    candidate = next(item for item in plan.candidates if item.key == "op100_source")
    seed = v4.EXPECTED_HOLDOUT_SEEDS[0]
    run_dir = tmp_path / "trace_run"
    source_csv = tmp_path / "engine_case" / v4.SHIPMENT_TRACE_SOURCE_RELATIVE_PATH
    lane_contract = v4._shipment_lane_contract(plan)
    assert len(lane_contract["lanes"]) == 18
    first_lane, second_lane = lane_contract["lanes"][:2]
    assert first_lane["lane_id"] != first_lane["edge_id"]

    def row(
        lane: dict[str, Any],
        shipment_id: str,
        decision: int,
        release: int,
        lead: int,
        pulled: float = 10.0,
        shipped: float = 9.0,
        uom: str = "UN",
    ) -> dict[str, Any]:
        return {
            "day": release,
            "shipment_id": shipment_id,
            "risk_decision_day": decision,
            "edge_id": lane["edge_id"],
            "pulled_qty": pulled,
            "shipped_qty": shipped,
            "lead_days": lead,
            "arrival_day": release + lead,
            "reliability": 0.9,
            "uom": uom,
        }

    source_rows = [
        row(first_lane, "shipment-z", 12, 20, 5),
        row(second_lane, "shipment-b", 4, 7, 3),
        row(first_lane, "shipment-a", 4, 6, 2),
        {**row(first_lane, "before-window", -1, 0, 2)},
        {**row(first_lane, "after-window", v4.SERVICE_DAYS, 0, 2)},
        row(first_lane, "zero-pull", 10, 10, 2, pulled=0.0, shipped=0.0),
        {
            **row(first_lane, "outside-lane", 10, 10, 2),
            "edge_id": "edge:not-in-the-18-lane-contract",
        },
    ]
    _write_shipment_csv(source_csv, source_rows)
    reference = v4._write_holdout_shipment_trace(
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
        source_csv=source_csv,
    )
    trace_path = run_dir / reference["relative_path"]
    first_gzip = trace_path.read_bytes()
    payload = v4._validate_shipment_trace_reference(
        reference,
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
    )
    assert set(reference) == v4.SHIPMENT_TRACE_REFERENCE_FIELDS
    assert payload["schema_version"] == v4.SHIPMENT_TRACE_SCHEMA_VERSION
    assert payload["source_csv_sha256"] == reference["source_csv_sha256"]
    assert payload["row_count"] == reference["row_count"] == 3
    assert payload["fields"] == list(v4.SHIPMENT_TRACE_FIELDS)
    lane_ids = {lane["lane_id"] for lane in lane_contract["lanes"]}
    edge_ids = {lane["edge_id"] for lane in lane_contract["lanes"]}
    assert all(row_payload[0] in lane_ids for row_payload in payload["rows"])
    assert all(row_payload[0] not in edge_ids for row_payload in payload["rows"])
    assert payload["filter_contract"]["canonical_sort_fields"] == [
        "lane_id",
        "risk_decision_day",
        "shipment_id",
        "arrival_day",
        "release_day",
    ]
    assert payload["rows"] == sorted(
        payload["rows"],
        key=lambda item: (item[0], item[2], item[1], item[4], item[3]),
    )
    assert first_gzip[4:8] == b"\0\0\0\0"
    assert first_gzip[3] & 0x08 == 0

    repeated = v4._write_holdout_shipment_trace(
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
        source_csv=source_csv,
    )
    assert repeated == reference
    assert trace_path.read_bytes() == first_gzip

    metrics = _metrics(1.0)
    raw_unsigned = {
        "schema_version": v4.COARSE_EVIDENCE_SCHEMA_VERSION,
        "candidate_id": candidate.candidate_id,
        "offset_days_268091": candidate.offset_days_268091,
        "offset_days_268967": candidate.offset_days_268967,
        "seed": seed,
        "valid": True,
        "validation_errors": [],
        "graph_sha256": plan.manifest["inventory"][candidate.key]["graph_sha256"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "status": "executed",
        "summary_sha256": "1" * 64,
        "service_daily_sha256": "2" * 64,
        "command_sha256": "3" * 64,
        "run_dir": str(tmp_path / "synthetic_engine_case"),
        "metrics": metrics,
    }
    raw_evidence = {
        **raw_unsigned,
        "evidence_signature": v4.stable_sha256(raw_unsigned),
    }
    outer_unsigned = {
        "schema_version": v4.EVIDENCE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "stage": "holdout",
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "seed": seed,
        "evidence_mode": "execute_fresh_holdout",
        "graph_sha256": plan.manifest["inventory"][candidate.key]["graph_sha256"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "metrics": metrics,
        "source_evidence": None,
        "executor_proof": {
            "kind": "coarse_execute_candidate",
            "raw_evidence": raw_evidence,
        },
        "shipment_trace": reference,
        "valid": True,
        "created_at_utc": "2026-09-05T00:00:00+00:00",
    }
    outer = {
        **outer_unsigned,
        "evidence_signature": v4.stable_sha256(outer_unsigned),
    }
    v4._validate_v4_evidence(
        outer,
        plan=plan,
        run_dir=run_dir,
        stage="holdout",
        candidate=candidate,
        seed=seed,
        execution_mode=v4.OFFICIAL_EXECUTION_MODE,
    )
    without_trace_unsigned = {**outer_unsigned, "shipment_trace": None}
    without_trace = {
        **without_trace_unsigned,
        "evidence_signature": v4.stable_sha256(without_trace_unsigned),
    }
    with pytest.raises(v4.V4ProtocolError, match="trace reference"):
        v4._validate_v4_evidence(
            without_trace,
            plan=plan,
            run_dir=run_dir,
            stage="holdout",
            candidate=candidate,
            seed=seed,
            execution_mode=v4.OFFICIAL_EXECUTION_MODE,
        )

    jobs = ((candidate, seed),)
    v4._validate_shipment_trace_inventory(
        plan,
        run_dir,
        "holdout",
        jobs,
        v4.OFFICIAL_EXECUTION_MODE,
        require_complete=False,
    )
    with pytest.raises(v4.V4ProtocolError, match="incomplete"):
        v4._validate_shipment_trace_inventory(
            plan,
            run_dir,
            "holdout",
            jobs,
            v4.OFFICIAL_EXECUTION_MODE,
            require_complete=True,
        )

    changed_rows = list(source_rows)
    changed_rows[0] = row(first_lane, "shipment-z", 12, 20, 5, pulled=11.0)
    _write_shipment_csv(source_csv, changed_rows)
    with pytest.raises(v4.V4ProtocolError, match="differs"):
        v4._write_holdout_shipment_trace(
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
            source_csv=source_csv,
        )
    _write_shipment_csv(source_csv, source_rows)

    trace_path.write_bytes(b"corrupt")
    with pytest.raises(v4.V4ProtocolError, match="corrupt"):
        v4._validate_shipment_trace_reference(
            reference,
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
        )
    trace_path.write_bytes(first_gzip)
    trace_path.unlink()
    with pytest.raises(v4.V4ProtocolError, match="missing"):
        v4._validate_shipment_trace_reference(
            reference,
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
        )

    metric_rows = [{"metrics": v4._normalize_metrics(_metrics(1.0))} for _ in range(30)]
    traced_metric_rows = [
        {**metric_row, "shipment_trace": reference} for metric_row in metric_rows
    ]
    assert v4._candidate_summary(candidate, metric_rows, True) == (
        v4._candidate_summary(candidate, traced_metric_rows, True)
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("arrival_day", -1, "arrival/lead"),
        ("shipment_id", "", "shipment id"),
        ("uom", "", "uom"),
    ],
)
def test_official_holdout_shipment_trace_rejects_invalid_rows(
    tmp_path: Path, field: str, value: Any, message: str
) -> None:
    plan_dir, _source = _prepared_keep_plan(tmp_path)
    plan = v4.validate_plan(plan_dir)
    candidate = next(item for item in plan.candidates if item.key == "op100_source")
    lane = v4._shipment_lane_contract(plan)["lanes"][0]
    source_csv = tmp_path / field / v4.SHIPMENT_TRACE_SOURCE_RELATIVE_PATH
    row = {
        "day": 0,
        "shipment_id": "shipment-invalid",
        "risk_decision_day": 0,
        "edge_id": lane["edge_id"],
        "pulled_qty": 10.0,
        "shipped_qty": 9.0,
        "lead_days": 2,
        "arrival_day": 2,
        "reliability": 0.9,
        "uom": "UN",
    }
    row[field] = value
    _write_shipment_csv(source_csv, [row])
    with pytest.raises(v4.V4ProtocolError, match=message):
        v4._write_holdout_shipment_trace(
            plan=plan,
            run_dir=tmp_path / f"run_{field}",
            candidate=candidate,
            seed=v4.EXPECTED_HOLDOUT_SEEDS[0],
            source_csv=source_csv,
        )


def test_op80_failed_requires_safe_explicit_candidates(tmp_path: Path) -> None:
    source = _source_campaign(tmp_path, op80_service=0.82)
    grid = tmp_path / "grid.json"
    _write(
        grid,
        {"candidates": _op80_grid_rows()},
    )
    decision = tmp_path / "decision.json"
    v4.write_op80_decision(
        decision,
        source_campaign_manifest=source,
        mode="candidates",
        rationale="The source anchor misses the V4 inner band.",
        candidates_json=grid,
    )
    plan = tmp_path / "plan"
    v4.prepare_plan(plan, source_campaign_manifest=source, op80_decision_path=decision)
    validated = v4.validate_plan(plan)
    assert {
        candidate.key
        for candidate in validated.candidates
        if candidate.target_group == "op_80"
    } == {
        "op80_source_16p5_94",
        "op80_v4_17_95",
        "op80_v4_17_96",
        "op80_v4_17p5_95",
        "op80_v4_17p5_96",
    }
    assert validated.manifest["expected_development_case_count"] == 330
    assert validated.manifest["reused_development_case_count"] == 90
    assert validated.manifest["new_development_case_count"] == 240
    assert (
        validated.manifest["candidate_design"]["op80_exact_grid_if_source_inner_fails"]
        == _op80_grid_rows()
    )

    traversal = tmp_path / "traversal.json"
    _write(
        traversal,
        {
            "candidates": [
                {
                    "key": "../../escape",
                    "offset_days_268091": 18,
                    "offset_days_268967": 100,
                }
            ]
        },
    )
    with pytest.raises(v4.V4ProtocolError):
        v4.write_op80_decision(
            tmp_path / "bad.json",
            source_campaign_manifest=source,
            mode="candidates",
            rationale="Invalid path must be rejected.",
            candidates_json=traversal,
        )
    assert not (tmp_path / "bad.json").exists()

    duplicate = tmp_path / "duplicate.json"
    _write(
        duplicate,
        {
            "candidates": [
                {
                    "key": "op80_v4_a",
                    "offset_days_268091": 18,
                    "offset_days_268967": 100,
                },
                {
                    "key": "op80_v4_b",
                    "offset_days_268091": 18,
                    "offset_days_268967": 100,
                },
            ]
        },
    )
    with pytest.raises(v4.V4ProtocolError, match="four frozen"):
        v4.write_op80_decision(
            tmp_path / "duplicate_decision.json",
            source_campaign_manifest=source,
            mode="candidates",
            rationale="Duplicate coordinates must be rejected.",
            candidates_json=duplicate,
        )


def test_op80_keep_requires_every_leave_one_out_check(tmp_path: Path) -> None:
    source = _source_campaign(tmp_path)
    _rewrite_source_with_op80_loo_failure(source)
    validated = v4.validate_rejected_v3_campaign(source)
    acceptance = validated["preflight_state_acceptance"]
    assert acceptance["individual_outer"]["op_80"] is True
    assert acceptance["development_inner"]["op_80"] is False
    with pytest.raises(v4.V4ProtocolError, match="inner"):
        v4.write_op80_decision(
            tmp_path / "keep.json",
            source_campaign_manifest=source,
            mode="keep",
            rationale="This must fail because one leave-one-out estimate is outside.",
        )

    grid = tmp_path / "loo_grid.json"
    _write(
        grid,
        {"candidates": _op80_grid_rows()},
    )
    decision = v4.write_op80_decision(
        tmp_path / "candidates.json",
        source_campaign_manifest=source,
        mode="candidates",
        rationale="At least one source leave-one-out estimate misses the outer band.",
        candidates_json=grid,
    )
    assert decision.is_file()


def test_mock_run_resume_selection_holdout_and_closed_inventories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _source = _prepared_keep_plan(tmp_path)
    run = tmp_path / "run"
    calls: list[tuple[str, str, int]] = []

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        calls.append((kwargs["stage"], candidate.key, kwargs["seed"]))
        service = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}[candidate.target_group]
        return {"metrics": _metrics(service)}

    with pytest.raises(v4.V4ProtocolError, match="explicit test_only"):
        v4.run_stage(plan, run, stage="development", executor=executor, max_workers=1)
    assert not run.exists()

    def unexpected_worktree_inventory() -> dict[str, Any]:
        raise AssertionError("test-only fixture consulted the real worktree")

    with monkeypatch.context() as isolated_runtime:
        isolated_runtime.setattr(
            v4,
            "_runtime_dependency_inventory_from_worktree",
            unexpected_worktree_inventory,
        )
        progress = v4.run_stage(
            plan,
            run,
            stage="development",
            executor=executor,
            max_workers=1,
            test_only=True,
        )
        assert progress["completed_case_count"] == 210
        assert progress["execution_mode"] == v4.TEST_ONLY_EXECUTION_MODE
        assert progress["publishable"] is False
        assert len(calls) == 120
        assert all(
            json.loads(path.read_text(encoding="utf-8"))["shipment_trace"] is None
            for path in (run / "evidence" / "development").glob("*.json")
        )
        assert not (run / "shipment_traces").exists()
        v4.run_stage(
            plan,
            run,
            stage="development",
            executor=executor,
            max_workers=1,
            test_only=True,
        )
    assert len(calls) == 120

    with pytest.raises(v4.V4ProtocolError, match="authorized"):
        v4.run_stage(
            plan,
            run,
            stage="holdout",
            executor=executor,
            max_workers=1,
            test_only=True,
        )
    assert len(calls) == 120

    with pytest.raises(v4.V4ProtocolError, match="distinct run registrations"):
        v4.finalize_stage(plan, run, stage="development")

    test_manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    test_progress = json.loads(
        (run / "development_progress.json").read_text(encoding="utf-8")
    )
    validated_plan = v4.validate_plan(plan)
    _write(
        run / "run_manifest.json",
        v4._run_manifest(validated_plan, v4.OFFICIAL_EXECUTION_MODE),
    )
    official_progress = dict(test_progress)
    official_progress["execution_mode"] = v4.OFFICIAL_EXECUTION_MODE
    official_progress["publishable"] = True
    official_progress.pop("progress_signature")
    official_progress["progress_signature"] = v4.stable_sha256(official_progress)
    _write(run / "development_progress.json", official_progress)
    with pytest.raises(v4.V4ProtocolError, match="incompatible"):
        v4.finalize_stage(plan, run, stage="development")
    _write(run / "run_manifest.json", test_manifest)
    _write(run / "development_progress.json", test_progress)

    selection = v4.finalize_stage(plan, run, stage="development", test_only=True)
    assert selection["selected_candidate_keys"]["op_93"] == "op93_v4_8_80p5"
    assert selection["holdout_cases_read"] == 0
    assert selection["execution_mode"] == v4.TEST_ONLY_EXECUTION_MODE
    assert selection["publishable"] is False

    selection_path = run / "development_selection.json"
    altered = json.loads(json.dumps(selection))
    altered["selected_candidate_keys"]["op_93"] = "op93_v4_8_81p5"
    altered_unsigned = dict(altered)
    altered_unsigned.pop("selection_signature")
    altered["selection_signature"] = v4.stable_sha256(altered_unsigned)
    _write(selection_path, altered)
    with pytest.raises(v4.V4ProtocolError, match="reproducible"):
        v4.run_stage(
            plan,
            run,
            stage="holdout",
            executor=executor,
            max_workers=1,
            test_only=True,
        )
    assert len(calls) == 120
    _write(selection_path, selection)

    holdout_progress = v4.run_stage(
        plan,
        run,
        stage="holdout",
        executor=executor,
        max_workers=1,
        test_only=True,
    )
    assert holdout_progress["completed_case_count"] == 90
    assert len(calls) == 210
    assert all(
        json.loads(path.read_text(encoding="utf-8"))["shipment_trace"] is None
        for path in (run / "evidence" / "holdout").glob("*.json")
    )
    assert not (run / "shipment_traces").exists()
    v4.run_stage(
        plan,
        run,
        stage="holdout",
        executor=executor,
        max_workers=1,
        test_only=True,
    )
    assert len(calls) == 210
    result = v4.finalize_stage(plan, run, stage="holdout", test_only=True)
    assert result["accepted"] is True
    assert result["holdout_evidence_case_count"] == 90
    assert result["execution_mode"] == v4.TEST_ONLY_EXECUTION_MODE
    assert result["publishable"] is False
    assert (
        result["paired_bootstrap_global_descriptive_only"]["contract"][
            "acceptance_gate"
        ]
        is False
    )

    extra = run / "evidence" / "holdout" / "extra.json"
    _write(extra, {"unexpected": True})
    with pytest.raises(v4.V4ProtocolError, match="exactly 90"):
        v4.finalize_stage(plan, run, stage="holdout", test_only=True)


def test_tamper_demand_mismatch_median_and_holdout_leak_fail_closed(
    tmp_path: Path,
) -> None:
    plan, _source = _prepared_keep_plan(tmp_path)
    leaked_run = tmp_path / "leaked_run"
    (leaked_run / "evidence" / "holdout").mkdir(parents=True)
    called = False

    def never(**_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"metrics": _metrics(0.93)}

    with pytest.raises(v4.V4ProtocolError, match="holdout"):
        v4.run_stage(
            plan,
            leaked_run,
            stage="development",
            executor=never,
            test_only=True,
        )
    assert called is False
    assert not (leaked_run / "run_manifest.json").exists()

    run = tmp_path / "tamper_run"

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        service = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}[candidate.target_group]
        return {"metrics": _metrics(service)}

    v4.run_stage(
        plan,
        run,
        stage="development",
        executor=executor,
        max_workers=1,
        test_only=True,
    )
    validated = v4.validate_plan(plan)
    candidate = next(
        item for item in validated.candidates if item.key == "op93_v4_8_80p5"
    )
    path = v4._evidence_path(run, "development", candidate.key, v4.DEVELOPMENT_SEEDS[0])
    original = json.loads(path.read_text(encoding="utf-8"))
    tampered = json.loads(json.dumps(original))
    tampered["candidate_id"] = "tampered"
    _write(path, tampered)
    with pytest.raises(v4.V4ProtocolError):
        v4.run_stage(
            plan,
            run,
            stage="development",
            executor=executor,
            max_workers=1,
            test_only=True,
        )
    _write(path, original)

    mismatched = json.loads(json.dumps(original))
    mismatched["metrics"]["demand_qty_268091"] = 101.0
    mismatched["metrics"]["on_due_qty_268091"] = 101.0 * 0.93
    mismatched["metrics"]["demand_qty_global"] = 201.0
    mismatched["metrics"]["on_due_qty_global"] = 101.0 * 0.93 + 100.0 * 0.93
    mismatched["executor_proof"]["raw_payload"]["metrics"] = {
        key: value
        for key, value in mismatched["metrics"].items()
        if not key.endswith("_global")
    }
    unsigned = dict(mismatched)
    unsigned.pop("evidence_signature")
    mismatched["evidence_signature"] = v4.stable_sha256(unsigned)
    _write(path, mismatched)
    with pytest.raises(v4.V4ProtocolError, match="Demand mismatch"):
        v4.finalize_stage(plan, run, stage="development", test_only=True)

    reference = v4.Candidate("r", "r", "op_100", 0.0, 0.0, "execute")
    rows = [
        {"metrics": v4._normalize_metrics(_metrics(0.98, 1.0))} for _ in range(16)
    ] + [{"metrics": v4._normalize_metrics(_metrics(1.0, 100.0))} for _ in range(14)]
    summary = v4._candidate_summary(reference, rows, True)
    assert summary["pooled"]["system_on_due_service"] >= 0.985
    assert summary["median"]["system_on_due_service"] < 0.985
    assert summary["admissible_individually"] is False


def test_interrupted_development_resumes_only_missing_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_dir = tmp_path / "lock_contract"
    lock_dir.mkdir()
    lock_path = lock_dir / ".v4.lock"
    lock_path.write_text("pid=stale\n", encoding="utf-8")
    with v4._run_lock(lock_dir):
        with pytest.raises(v4.V4ProtocolError, match="already locked"):
            with v4._run_lock(lock_dir):
                pass
    assert lock_path.is_file()
    assert lock_path.read_text(encoding="utf-8") == f"pid={os.getpid()}\n"
    lock_path.write_text("pid=another-stale-owner\n", encoding="utf-8")
    with v4._run_lock(lock_dir):
        pass
    assert lock_path.read_text(encoding="utf-8") == f"pid={os.getpid()}\n"

    plan, _source = _prepared_keep_plan(tmp_path)
    run = tmp_path / "interrupted_run"
    first_calls: list[tuple[str, int]] = []
    progress_writes: list[tuple[int, dict[str, Any]]] = []
    orchestrator_thread = threading.get_ident()
    original_write_progress = v4._write_progress

    def recording_write_progress(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload = original_write_progress(*args, **kwargs)
        progress_writes.append((threading.get_ident(), dict(payload)))
        return payload

    monkeypatch.setattr(v4, "_write_progress", recording_write_progress)

    def interrupted(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        first_calls.append((candidate.key, kwargs["seed"]))
        if len(first_calls) == 5:
            raise RuntimeError("synthetic interruption")
        return {"metrics": _metrics(0.93)}

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        v4.run_stage(
            plan,
            run,
            stage="development",
            executor=interrupted,
            max_workers=1,
            test_only=True,
        )
    assert len(first_calls) == 5
    failed_progress = json.loads(
        (run / "development_progress.json").read_text(encoding="utf-8")
    )
    assert failed_progress["status"] == "failed"
    assert failed_progress["completed_case_count"] == 64
    running = [
        payload
        for _thread_id, payload in progress_writes
        if payload["status"] == "running"
    ]
    assert [payload["completed_case_count"] for payload in running] == list(range(65))
    assert all(thread_id == orchestrator_thread for thread_id, _ in progress_writes)
    for _thread_id, payload in progress_writes:
        v4._verify_self_signature(
            payload, "progress_signature", "test progress checkpoint"
        )

    lagging_progress = dict(failed_progress)
    lagging_progress["completed_case_count"] = 0
    lagging_progress.pop("progress_signature")
    lagging_progress["progress_signature"] = v4.stable_sha256(lagging_progress)
    _write(run / "development_progress.json", lagging_progress)
    progress_writes.clear()

    resumed_calls: list[tuple[str, int]] = []

    def resumed(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        resumed_calls.append((candidate.key, kwargs["seed"]))
        service = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}[candidate.target_group]
        return {"metrics": _metrics(service)}

    complete = v4.run_stage(
        plan,
        run,
        stage="development",
        executor=resumed,
        max_workers=1,
        test_only=True,
    )
    assert complete["completed_case_count"] == 210
    assert len(resumed_calls) == 116
    resumed_running = [
        payload["completed_case_count"]
        for _thread_id, payload in progress_writes
        if payload["status"] == "running"
    ]
    assert resumed_running == list(range(64, 211))
    assert all(thread_id == orchestrator_thread for thread_id, _ in progress_writes)
    selection = v4.finalize_stage(plan, run, stage="development", test_only=True)
    assert selection["status"] == "development_selected_pending_fresh_holdout"
