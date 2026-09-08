from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v2 as subject,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_completed_discovery(campaign_root: Path, manifest: dict[str, Any]) -> None:
    seeds = list(range(340287, 340317))
    discovery_dir = campaign_root / "target_discovery"
    registry_unsigned = {
        "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.target_registry.v4",
        "campaign_signature": manifest["campaign_signature"],
        "engine_sha256": manifest["engine_sha256"],
        "states": list(subject.EXPECTED_OPERATING_POINTS),
        "seeds": seeds,
        "lanes": [f"lane_{number:02d}" for number in range(1, 19)],
        "disruption_window_days": 42,
        "all_lane_design_windows_comparable": True,
        "all_lane_holdout_exposures_comparable": True,
        "campaign_exposure_gate_passed": True,
        "exposure_gate_failures": [],
        "lane_contracts": [
            {
                "lane_id": f"lane_{number:02d}",
                "design_status": "calibration_design_comparable_42d_window",
                "comparable_campaign_seed_count": 30,
            }
            for number in range(1, 19)
        ],
        "targets": [
            {
                "operating_point_id": point_id,
                "seed": seed,
                "lane_id": f"lane_{number:02d}",
            }
            for point_id in subject.EXPECTED_OPERATING_POINTS
            for seed in seeds
            for number in range(1, 19)
        ],
    }
    registry = {
        **registry_unsigned,
        "registry_signature": subject._stable_sha256(registry_unsigned),
    }
    registry_path = discovery_dir / "target_registry.json"
    _write_json(registry_path, registry)
    preflight_unsigned = {
        "schema_version": subject.EXPECTED_PREFLIGHT_SCHEMA_VERSION,
        "contract_revision": subject.EXPECTED_CONTRACT_REVISION,
        "campaign_signature": manifest["campaign_signature"],
        "status": subject.EXPECTED_PREFLIGHT_STATUS,
        "operating_points_input_status": manifest["operating_points_input_status"],
        "operating_points_artifact_signature": manifest[
            "operating_points_artifact_signature"
        ],
        "operating_points_calibration_plan_signature": manifest[
            "operating_points_calibration_plan_signature"
        ],
        "operating_points_selection_signature": manifest[
            "operating_points_selection_signature"
        ],
        "no_incident_probe_before_holdout_acceptance": True,
        "campaign_seed_count": 30,
        "campaign_seeds": seeds,
        "holdout_used_once_without_retuning": True,
        "ordering_valid": True,
        "seed_ordering_valid": True,
        "joint_seed_order_count": 30,
        "states": [
            {"operating_point_id": point_id, "accepted": True}
            for point_id in subject.EXPECTED_OPERATING_POINTS
        ],
    }
    preflight = {
        **preflight_unsigned,
        "preflight_signature": subject._stable_sha256(preflight_unsigned),
    }
    preflight_path = discovery_dir / "operating_point_preflight.json"
    _write_json(preflight_path, preflight)
    manifest.update(
        {
            "target_discovery_status": "complete",
            "target_registry": str(registry_path.resolve()),
            "target_registry_sha256": subject._sha256_file(registry_path),
            "target_registry_signature": registry["registry_signature"],
            "target_exposure_comparability_status": "accepted",
            "operating_point_preflight": str(preflight_path.resolve()),
            "operating_point_preflight_sha256": subject._sha256_file(preflight_path),
            "operating_point_preflight_signature": preflight["preflight_signature"],
            "operating_point_preflight_status": subject.EXPECTED_PREFLIGHT_STATUS,
            "target_discovery_completed_at_utc": "2026-09-04T12:01:00+00:00",
        }
    )
    _write_json(campaign_root / "campaign_manifest.json", manifest)


def _make_plan(
    tmp_path: Path, *, discovery_complete: bool = True, source_version: str = "v1"
) -> tuple[Path, Path, dict[str, Any]]:
    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    sources = {
        "operating_points_source": tmp_path / "operating_points.json",
        "operating_points_calibration_plan": tmp_path / "calibration_plan.json",
        "operating_points_selection": tmp_path / "selection.json",
        "lane_reference_source": tmp_path / "lanes.csv",
        "engine": tmp_path / "engine.py",
        "engine_profile": tmp_path / "profile.json",
    }
    if source_version == "v1":
        producer = subject.V1_POINTS_PRODUCER
        points_schema = subject.V1_POINTS_SCHEMA_VERSION
        points_status = subject.V1_POINTS_PENDING_STATUS
        selection_schema = subject.V1_SELECTION_SCHEMA_VERSION
        selection_status = subject.V1_SELECTION_STATUS
        tracks_holdout_cases = False
    elif source_version == "v2":
        producer = subject.V2_POINTS_PRODUCER
        points_schema = subject.V2_POINTS_SCHEMA_VERSION
        points_status = subject.V2_POINTS_PENDING_STATUS
        selection_schema = subject.V2_SELECTION_SCHEMA_VERSION
        selection_status = subject.V2_SELECTION_STATUS
        tracks_holdout_cases = True
    elif source_version == "v3":
        producer = subject.V3_POINTS_PRODUCER
        points_schema = subject.V3_POINTS_SCHEMA_VERSION
        points_status = subject.V3_POINTS_PENDING_STATUS
        selection_schema = subject.V3_SELECTION_SCHEMA_VERSION
        selection_status = subject.V3_SELECTION_STATUS
        tracks_holdout_cases = True
    else:
        raise ValueError(f"Unsupported test source version: {source_version}")

    seeds = list(range(340287, 340317))
    cohorts = {
        "design": [340281],
        "calibration": list(range(340282, 340287)),
        "holdout_sealed": seeds,
    }
    plan_signature = "p" * 64
    holdout_contract = dict(subject.EXPECTED_HOLDOUT_CONTRACT_FIELDS)
    if tracks_holdout_cases:
        holdout_contract.update(
            {
                "status": "sealed_unread",
                "cases_in_this_plan": 0,
                "selected_output_status": points_status,
            }
        )
    selection_contract = {"no_holdout_retuning": True}
    source_hashes = {"fixture_source_sha256": "f" * 64}
    if source_version == "v3":
        source_hashes["v3_driver_sha256"] = subject.V3_REFINEMENT_MODULE_SHA256
    _write_json(
        sources["operating_points_calibration_plan"],
        {
            "plan_signature": plan_signature,
            "source_hashes": source_hashes,
            "cohorts": cohorts,
            "holdout_contract": holdout_contract,
            "selection_contract": selection_contract,
        },
    )
    selection_unsigned = {
        "schema_version": selection_schema,
        "status": selection_status,
        "plan_signature": plan_signature,
        "calibration_seeds": cohorts["calibration"],
        "holdout_seeds_sealed_and_unread": cohorts["holdout_sealed"],
        "selection_contract": selection_contract,
        "fallback_required": False,
    }
    if tracks_holdout_cases:
        selection_unsigned.update(
            {
                "holdout_cases_read": 0,
                "holdout_contract": holdout_contract,
                "holdout_launch_permitted": True,
            }
        )
    selection_signature = subject._stable_sha256(selection_unsigned)
    _write_json(
        sources["operating_points_selection"],
        {
            **selection_unsigned,
            "selection_signature": selection_signature,
        },
    )
    operating_points_unsigned = {
        "schema_version": points_schema,
        "status": points_status,
        "plan": {
            "path": str(sources["operating_points_calibration_plan"].parent),
            "plan_signature": plan_signature,
        },
        "selection_signature": selection_signature,
        "source_hashes": source_hashes,
        "cohorts": cohorts,
        "holdout_validated": False,
        "simulation_hypotheses_not_observed_performance": True,
        "operating_points": [],
    }
    if tracks_holdout_cases:
        operating_points_unsigned.update(
            {
                "holdout_cases_read": 0,
                "holdout_contract": holdout_contract,
                "selection": {
                    "relative_path": "selection.json",
                    "schema_version": selection_schema,
                    "selection_signature": selection_signature,
                },
            }
        )
    operating_points_artifact_signature = subject._stable_sha256(
        operating_points_unsigned
    )
    _write_json(
        sources["operating_points_source"],
        {
            **operating_points_unsigned,
            "artifact_signature": operating_points_artifact_signature,
        },
    )
    sources["lane_reference_source"].write_text("lane_id\nL1\n", encoding="utf-8")
    sources["engine"].write_text("# engine fixture\n", encoding="utf-8")
    sources["engine_profile"].write_text("[]", encoding="utf-8")
    runner = tmp_path / "runner.py"
    runner.write_text("# runner fixture\n", encoding="utf-8")

    shards: list[dict[str, Any]] = []
    index = 0
    for point_id in subject.EXPECTED_OPERATING_POINTS:
        for block_number in range(1, 7):
            index += 1
            start = (block_number - 1) * 5
            shards.append(
                {
                    "shard_id": f"{point_id}__seed_block_{block_number:02d}",
                    "shard_index": index,
                    "shard_count": 18,
                    "operating_point_id": point_id,
                    "seed_block": block_number,
                    "seed_ids": seeds[start : start + 5],
                    "baseline_rows": 5,
                    "incident_rows": 180,
                    "total_rows": 185,
                }
            )
    design: dict[str, Any] = {
        "schema_version": subject.INPUT_SCHEMA_VERSION,
        "contract_revision": subject.EXPECTED_CONTRACT_REVISION,
        "scope": "full_3_states_18_lanes_2_incidents_30_repetitions",
        "runner": str(runner.resolve()),
        "runner_sha256": subject._sha256_file(runner),
        "operating_points_source": str(sources["operating_points_source"].resolve()),
        "operating_points_source_sha256": subject._sha256_file(
            sources["operating_points_source"]
        ),
        "operating_points_producer": producer,
        "operating_points_schema_version": points_schema,
        "operating_points_input_status": points_status,
        "operating_points_artifact_signature": operating_points_artifact_signature,
        "operating_points_calibration_plan_signature": plan_signature,
        "operating_points_selection_signature": selection_signature,
        "operating_points_cohorts": cohorts,
        "operating_points_holdout_contract": holdout_contract,
        "operating_points_calibration_plan": str(
            sources["operating_points_calibration_plan"].resolve()
        ),
        "operating_points_calibration_plan_sha256": subject._sha256_file(
            sources["operating_points_calibration_plan"]
        ),
        "operating_points_selection": str(
            sources["operating_points_selection"].resolve()
        ),
        "operating_points_selection_sha256": subject._sha256_file(
            sources["operating_points_selection"]
        ),
        "lane_reference_source": str(sources["lane_reference_source"].resolve()),
        "lane_reference_source_sha256": subject._sha256_file(
            sources["lane_reference_source"]
        ),
        "engine": str(sources["engine"].resolve()),
        "engine_sha256": subject._sha256_file(sources["engine"]),
        "engine_profile": str(sources["engine_profile"].resolve()),
        "engine_profile_sha256": subject._sha256_file(sources["engine_profile"]),
        "states": [
            {"operating_point_id": point_id}
            for point_id in subject.EXPECTED_OPERATING_POINTS
        ],
        "lanes": [{"lane_id": f"lane_{number:02d}"} for number in range(1, 19)],
        "mechanisms": [
            {"key": "transport_delay", "risk_type": "transport_delay"},
            {"key": "planned_delivery_shortfall", "risk_type": "reliability"},
        ],
        "seeds": seeds,
        "seed_blocks": [seeds[start : start + 5] for start in range(0, 30, 5)],
        "shards": shards,
        "expected_counts": {
            "auxiliary_discovery_runs": 93,
            "baseline_rows": 90,
            "incident_rows": 3240,
            "total_rows": 3330,
            "shard_count": 18,
            "rows_per_shard": 185,
        },
        "quality_branch_included": False,
        "availability_incident_included": False,
    }
    manifest = {
        **design,
        "campaign_signature": subject._stable_sha256(design),
        "status": "planned",
        "created_at_utc": "2026-09-04T12:00:00+00:00",
        "completed_at_utc": "",
    }
    _write_json(campaign_root / "campaign_manifest.json", manifest)
    with (campaign_root / "shard_plan.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(shards[0]))
        writer.writeheader()
        writer.writerows(shards)
    if discovery_complete:
        _write_completed_discovery(campaign_root, manifest)
    return campaign_root, runner, manifest


def _resign_campaign_manifest(campaign_root: Path, manifest: dict[str, Any]) -> None:
    unsigned_fields = {
        "campaign_signature",
        "status",
        "created_at_utc",
        "completed_at_utc",
        "target_discovery_status",
        "target_registry",
        "target_registry_sha256",
        "target_registry_signature",
        "target_exposure_comparability_status",
        "operating_point_preflight",
        "operating_point_preflight_sha256",
        "operating_point_preflight_signature",
        "operating_point_preflight_status",
        "target_discovery_completed_at_utc",
    }
    signed_design = {
        key: value for key, value in manifest.items() if key not in unsigned_fields
    }
    manifest["campaign_signature"] = subject._stable_sha256(signed_design)
    _write_json(campaign_root / "campaign_manifest.json", manifest)


def _write_completed_shard(
    campaign_root: Path,
    manifest: dict[str, Any],
    shard_id: str,
) -> None:
    shard_dir = campaign_root / "shards" / shard_id
    shard_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        shard_dir / "progress.json",
        {
            "schema_version": subject.SHARD_PROGRESS_SCHEMA_VERSION,
            "campaign_signature": manifest["campaign_signature"],
            "shard_id": shard_id,
            "status": "complete",
            "planned_case_count": 185,
            "completed_case_count": 185,
            "failed_case_count": 0,
            "updated_at_utc": subject.utc_now(),
        },
    )
    (shard_dir / "campaign_metrics.csv").write_text("case_key\n", encoding="utf-8")
    _write_json(shard_dir / "shard_manifest.json", {"status": "complete"})


def test_loads_exact_signed_18_shard_plan_and_builds_runner_command(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path)

    loaded, shards = subject.load_campaign_plan(campaign_root, runner)
    command = subject.build_shard_command(
        runner=runner,
        campaign_root=campaign_root,
        manifest=loaded,
        shard=shards[7],
        workers_per_shard=2,
        reuse_evidence_dirs=(tmp_path / "prior",),
    )

    assert len(shards) == 18
    assert command[command.index("--operating-point-id") + 1] == "op_93"
    assert command[command.index("--seed-block") + 1] == "2"
    assert command[command.index("--workers") + 1] == "2"
    assert "--reuse-evidence-dir" in command
    assert "availability" not in " ".join(command).casefold()
    assert loaded["operating_points_producer"] == subject.V1_POINTS_PRODUCER
    assert loaded["operating_points_schema_version"] == subject.V1_POINTS_SCHEMA_VERSION
    assert loaded["operating_points_input_status"] == subject.V1_POINTS_PENDING_STATUS
    assert manifest["campaign_signature"] == loaded["campaign_signature"]


def test_loads_real_v2_plan_created_by_current_runner(tmp_path: Path) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_operating_point_full_campaign_v2 as campaign_runner,
    )
    from etudecas.prototypes.scan_2027_risk_control.tests.test_supplier_operating_point_full_campaign_v2 import (
        _prepare_v2_selected_points,
    )

    selected_points = _prepare_v2_selected_points(tmp_path)
    lane_reference = tmp_path / "campaign_lanes.csv"
    lane_fields = (
        "scope_status",
        "chain_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
        "planned_lead_days",
    )
    with lane_reference.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=lane_fields)
        writer.writeheader()
        writer.writerows(
            {
                "scope_status": "active_simulated_reference_v10",
                "chain_id": f"lane_{index:02d}",
                "supplier_id": f"supplier_{index:02d}",
                "item_id": f"item:{index:02d}",
                "dst_node_id": f"factory_{index:02d}",
                "edge_id": f"edge:{index:02d}",
                "target_product_id": "268091" if index <= 9 else "268967",
                "planned_lead_days": 10 + index,
            }
            for index in range(1, 19)
        )

    campaign_root = tmp_path / "real_v2_campaign"
    planned, _points, _lanes = campaign_runner.prepare_manifest(
        output_dir=campaign_root,
        operating_points_path=selected_points,
        lane_reference_path=lane_reference,
        engine=tmp_path / "engine.py",
        profile=tmp_path / "profile.json",
    )

    loaded, shards = subject.load_campaign_plan(
        campaign_root, Path(campaign_runner.__file__)
    )

    assert len(shards) == subject.EXPECTED_SHARD_COUNT
    assert planned["operating_points_producer"] == subject.V2_POINTS_PRODUCER
    assert loaded["operating_points_schema_version"] == subject.V2_POINTS_SCHEMA_VERSION
    assert loaded["operating_points_input_status"] == subject.V2_POINTS_PENDING_STATUS


def test_loads_exact_signed_v3_source_contract(tmp_path: Path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path, source_version="v3")

    loaded, shards = subject.load_campaign_plan(campaign_root, runner)

    assert len(shards) == subject.EXPECTED_SHARD_COUNT
    assert manifest["operating_points_producer"] == subject.V3_POINTS_PRODUCER
    assert loaded["operating_points_schema_version"] == subject.V3_POINTS_SCHEMA_VERSION
    assert loaded["operating_points_input_status"] == subject.V3_POINTS_PENDING_STATUS


@pytest.mark.parametrize(
    ("producer", "schema", "status"),
    [
        (
            subject.V1_POINTS_PRODUCER,
            subject.V2_POINTS_SCHEMA_VERSION,
            subject.V2_POINTS_PENDING_STATUS,
        ),
        (
            subject.V2_POINTS_PRODUCER,
            subject.V1_POINTS_SCHEMA_VERSION,
            subject.V1_POINTS_PENDING_STATUS,
        ),
        (
            subject.V1_POINTS_PRODUCER,
            subject.V1_POINTS_SCHEMA_VERSION,
            subject.V2_POINTS_PENDING_STATUS,
        ),
        (
            subject.V2_POINTS_PRODUCER,
            subject.V2_POINTS_SCHEMA_VERSION,
            "holdout_already_consumed",
        ),
        (
            subject.V3_POINTS_PRODUCER,
            subject.V2_POINTS_SCHEMA_VERSION,
            subject.V2_POINTS_PENDING_STATUS,
        ),
        (
            subject.V2_POINTS_PRODUCER,
            subject.V3_POINTS_SCHEMA_VERSION,
            subject.V3_POINTS_PENDING_STATUS,
        ),
        (
            subject.V3_POINTS_PRODUCER,
            subject.V3_POINTS_SCHEMA_VERSION,
            "selected_on_unregistered_v3_status",
        ),
    ],
)
def test_plan_rejects_mixed_or_unknown_operating_point_contracts(
    tmp_path: Path, producer: str, schema: str, status: str
) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path, discovery_complete=False)
    manifest.update(
        {
            "operating_points_producer": producer,
            "operating_points_schema_version": schema,
            "operating_points_input_status": status,
        }
    )
    _resign_campaign_manifest(campaign_root, manifest)

    with pytest.raises(ValueError, match="exact signed V1, V2 or V3"):
        subject.load_campaign_plan(campaign_root, runner)


def test_plan_rejects_source_tampering_even_if_outer_hash_is_resigned(
    tmp_path: Path,
) -> None:
    campaign_root, runner, manifest = _make_plan(
        tmp_path, discovery_complete=False, source_version="v2"
    )
    source_path = Path(manifest["operating_points_source"])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["tampered_after_selection"] = True
    _write_json(source_path, source)
    manifest["operating_points_source_sha256"] = subject._sha256_file(source_path)
    _resign_campaign_manifest(campaign_root, manifest)

    with pytest.raises(ValueError, match="artifact signature is invalid"):
        subject.load_campaign_plan(campaign_root, runner)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", subject.V2_SELECTION_SCHEMA_VERSION),
        ("status", subject.V2_SELECTION_STATUS),
    ],
)
def test_v3_rejects_re_signed_mixed_selection_schema_or_status(
    tmp_path: Path, field: str, value: str
) -> None:
    campaign_root, runner, manifest = _make_plan(
        tmp_path, discovery_complete=False, source_version="v3"
    )
    selection_path = Path(manifest["operating_points_selection"])
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection[field] = value
    selection.pop("selection_signature")
    selection_signature = subject._stable_sha256(selection)
    selection["selection_signature"] = selection_signature
    _write_json(selection_path, selection)

    source_path = Path(manifest["operating_points_source"])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["selection_signature"] = selection_signature
    source["selection"]["selection_signature"] = selection_signature
    source.pop("artifact_signature")
    source_artifact_signature = subject._stable_sha256(source)
    source["artifact_signature"] = source_artifact_signature
    _write_json(source_path, source)

    manifest.update(
        {
            "operating_points_selection_signature": selection_signature,
            "operating_points_selection_sha256": subject._sha256_file(selection_path),
            "operating_points_artifact_signature": source_artifact_signature,
            "operating_points_source_sha256": subject._sha256_file(source_path),
        }
    )
    _resign_campaign_manifest(campaign_root, manifest)

    with pytest.raises(ValueError, match="selection signature chain is invalid"):
        subject.load_campaign_plan(campaign_root, runner)


def test_v3_rejects_re_signed_producer_identity_tampering(tmp_path: Path) -> None:
    campaign_root, runner, manifest = _make_plan(
        tmp_path, discovery_complete=False, source_version="v3"
    )
    plan_path = Path(manifest["operating_points_calibration_plan"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["source_hashes"]["v3_driver_sha256"] = "0" * 64
    _write_json(plan_path, plan)

    source_path = Path(manifest["operating_points_source"])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["source_hashes"]["v3_driver_sha256"] = "0" * 64
    source.pop("artifact_signature")
    source_artifact_signature = subject._stable_sha256(source)
    source["artifact_signature"] = source_artifact_signature
    _write_json(source_path, source)
    manifest.update(
        {
            "operating_points_calibration_plan_sha256": subject._sha256_file(plan_path),
            "operating_points_artifact_signature": source_artifact_signature,
            "operating_points_source_sha256": subject._sha256_file(source_path),
        }
    )
    _resign_campaign_manifest(campaign_root, manifest)

    with pytest.raises(ValueError, match="V3 operating-point producer identity"):
        subject.load_campaign_plan(campaign_root, runner)


def test_v3_rejects_re_signed_consumed_holdout(tmp_path: Path) -> None:
    campaign_root, runner, manifest = _make_plan(
        tmp_path, discovery_complete=False, source_version="v3"
    )
    source_path = Path(manifest["operating_points_source"])
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["holdout_cases_read"] = 1
    source.pop("artifact_signature")
    source_artifact_signature = subject._stable_sha256(source)
    source["artifact_signature"] = source_artifact_signature
    _write_json(source_path, source)
    manifest.update(
        {
            "operating_points_artifact_signature": source_artifact_signature,
            "operating_points_source_sha256": subject._sha256_file(source_path),
        }
    )
    _resign_campaign_manifest(campaign_root, manifest)

    with pytest.raises(ValueError, match="does not preserve its sealed holdout"):
        subject.load_campaign_plan(campaign_root, runner)


def test_plan_validation_fails_closed_when_a_signed_source_changes(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path)
    Path(manifest["engine"]).write_text("# changed engine\n", encoding="utf-8")

    with pytest.raises(ValueError, match="engine changed"):
        subject.load_campaign_plan(campaign_root, runner)


def test_completed_campaign_resume_is_idempotent_and_launches_nothing(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path)
    for shard in manifest["shards"]:
        _write_completed_shard(campaign_root, manifest, shard["shard_id"])

    def forbidden_popen(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("No completed shard may be relaunched")

    result = subject.launch_campaign(
        campaign_root=campaign_root,
        runner=runner,
        parallel_shards=2,
        workers_per_shard=2,
        poll_seconds=0,
        popen_factory=forbidden_popen,
        sleep=lambda _seconds: None,
    )

    assert result["status"] == "complete"
    assert result["completed_shard_count"] == 18
    assert result["active_shard_count"] == 0
    assert result["maximum_engine_processes"] == 4
    assert not (campaign_root / "launch_progress.json.tmp").exists()


def test_missing_discovery_is_completed_and_validated_before_any_shard(
    tmp_path,
) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path, discovery_complete=False)
    for shard in manifest["shards"]:
        _write_completed_shard(campaign_root, manifest, shard["shard_id"])
    commands: list[list[str]] = []

    class DiscoveryProcess:
        pid = 7654

        @staticmethod
        def poll() -> int:
            _write_completed_discovery(campaign_root, manifest)
            return 0

    def discovery_popen(command: list[str], **_kwargs: Any) -> DiscoveryProcess:
        commands.append(command)
        return DiscoveryProcess()

    result = subject.launch_campaign(
        campaign_root=campaign_root,
        runner=runner,
        parallel_shards=2,
        workers_per_shard=2,
        poll_seconds=0,
        popen_factory=discovery_popen,
        sleep=lambda _seconds: None,
    )

    assert len(commands) == 1
    assert commands[0][commands[0].index("--mode") + 1] == "discover-targets"
    assert result["status"] == "complete"
    assert result["target_discovery_status"] == "complete"
    assert result["phase"] == "shards"
    assert (campaign_root / "launcher_logs" / "target_discovery.log").is_file()


def test_rejected_holdout_never_launches_an_incident_shard(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path, discovery_complete=False)
    manifest.update(
        {
            "target_discovery_status": "rejected",
            "operating_point_preflight_status": "holdout_rejected_30_seed",
        }
    )
    _write_json(campaign_root / "campaign_manifest.json", manifest)

    with pytest.raises(ValueError, match="scientific preflight rejected"):
        subject.launch_campaign(
            campaign_root=campaign_root,
            runner=runner,
            parallel_shards=2,
            workers_per_shard=2,
            poll_seconds=0,
            popen_factory=lambda *_args, **_kwargs: pytest.fail(
                "neither discovery nor an incident shard may launch after rejection"
            ),
            sleep=lambda _seconds: None,
        )

    assert not (campaign_root / "launcher_logs").exists()


def test_scheduler_never_exceeds_two_shards_and_writes_separate_logs(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path)
    counters = {"active": 0, "maximum": 0, "launched": 0}

    class SuccessfulProcess:
        def __init__(self, shard_id: str) -> None:
            counters["active"] += 1
            counters["maximum"] = max(counters["maximum"], counters["active"])
            counters["launched"] += 1
            self.pid = 10_000 + counters["launched"]
            self.shard_id = shard_id
            self.polled = False

        def poll(self) -> int:
            if not self.polled:
                self.polled = True
                counters["active"] -= 1
            return 0

    def successful_popen(command: list[str], **_kwargs: Any) -> SuccessfulProcess:
        point_id = command[command.index("--operating-point-id") + 1]
        block = int(command[command.index("--seed-block") + 1])
        shard_id = f"{point_id}__seed_block_{block:02d}"
        _write_completed_shard(campaign_root, manifest, shard_id)
        return SuccessfulProcess(shard_id)

    result = subject.launch_campaign(
        campaign_root=campaign_root,
        runner=runner,
        parallel_shards=2,
        workers_per_shard=2,
        poll_seconds=0,
        popen_factory=successful_popen,
        sleep=lambda _seconds: None,
    )

    assert result["status"] == "complete"
    assert counters == {"active": 0, "maximum": 2, "launched": 18}
    assert len(list((campaign_root / "launcher_logs").glob("*.log"))) == 18


def test_first_failed_shard_stops_new_scheduling_and_records_failure(tmp_path) -> None:
    campaign_root, runner, _manifest = _make_plan(tmp_path)
    launches: list[list[str]] = []

    class FailedProcess:
        pid = 444

        @staticmethod
        def poll() -> int:
            return 7

    def failed_popen(command: list[str], **_kwargs: Any) -> FailedProcess:
        launches.append(command)
        return FailedProcess()

    result = subject.launch_campaign(
        campaign_root=campaign_root,
        runner=runner,
        parallel_shards=1,
        workers_per_shard=2,
        poll_seconds=0,
        popen_factory=failed_popen,
        sleep=lambda _seconds: None,
    )

    assert result["status"] == "failed"
    assert result["failed_shard_count"] == 1
    assert result["queued_shard_count"] == 17
    assert len(launches) == 1
    assert result["failures"][0]["return_code"] == 7


def test_fresh_running_shard_blocks_a_second_launcher(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path)
    first = manifest["shards"][0]["shard_id"]
    shard_dir = campaign_root / "shards" / first
    shard_dir.mkdir(parents=True)
    _write_json(
        shard_dir / "progress.json",
        {
            "schema_version": subject.SHARD_PROGRESS_SCHEMA_VERSION,
            "campaign_signature": manifest["campaign_signature"],
            "shard_id": first,
            "status": "running",
            "planned_case_count": 185,
            "completed_case_count": 4,
            "failed_case_count": 0,
            "updated_at_utc": subject.utc_now(),
        },
    )

    with pytest.raises(RuntimeError, match="Fresh running shard progress"):
        subject.launch_campaign(
            campaign_root=campaign_root,
            runner=runner,
            poll_seconds=0,
            popen_factory=lambda *_args, **_kwargs: pytest.fail("must not launch"),
            sleep=lambda _seconds: None,
        )


def test_windows_detach_restarts_hidden_child_with_same_limits(tmp_path) -> None:
    campaign_root, runner, _manifest = _make_plan(tmp_path)
    args = subject.parse_args(
        [
            "--campaign-root",
            str(campaign_root),
            "--runner",
            str(runner),
            "--parallel-shards",
            "2",
            "--workers-per-shard",
            "2",
            "--detach",
        ]
    )
    captured: dict[str, Any] = {}

    class DetachedProcess:
        pid = 9876

    def fake_popen(command: list[str], **kwargs: Any) -> DetachedProcess:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return DetachedProcess()

    result = subject.detach_launcher(args, popen_factory=fake_popen)

    assert result["status"] == "detached_launcher_started"
    assert result["pid"] == 9876
    assert "--detached-child" in captured["command"]
    assert "--detach" not in captured["command"]
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    if subject.os.name == "nt":
        assert captured["kwargs"]["creationflags"] & subprocess.DETACHED_PROCESS
        assert captured["kwargs"]["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_detached_child_holds_and_resets_windows_system_awake_state(tmp_path) -> None:
    campaign_root, runner, manifest = _make_plan(tmp_path)
    for shard in manifest["shards"]:
        _write_completed_shard(campaign_root, manifest, shard["shard_id"])
    args = subject.parse_args(
        [
            "--campaign-root",
            str(campaign_root),
            "--runner",
            str(runner),
            "--detached-child",
        ]
    )
    calls: list[int] = []

    def setter(flags: int) -> int:
        calls.append(flags)
        return 1

    result = subject.run_detached_child(
        args,
        execution_state_setter=setter,
        platform_name="nt",
        popen_factory=lambda *_args, **_kwargs: pytest.fail("must not launch"),
        sleep=lambda _seconds: None,
    )

    assert result["status"] == "complete"
    assert calls == [
        subject.ES_CONTINUOUS | subject.ES_SYSTEM_REQUIRED,
        subject.ES_CONTINUOUS,
    ]
    assert result["wakefulness"]["status"] == "released"
    assert result["wakefulness"]["scope"] == "system_sleep_only_display_sleep_allowed"
    progress = json.loads((campaign_root / "launch_progress.json").read_text())
    assert progress["wakefulness"]["released"] is True
    persisted = json.loads((campaign_root / "launcher_wakefulness.json").read_text())
    assert persisted["status"] == "released"


def test_windows_awake_api_failure_is_recorded_and_does_not_raise(tmp_path) -> None:
    def unavailable(_flags: int) -> int:
        return 0

    with subject.WindowsSystemAwake(
        tmp_path,
        execution_state_setter=unavailable,
        platform_name="nt",
    ) as state:
        assert state["status"] == "unavailable"
        assert state["acquired"] is False

    persisted = json.loads((tmp_path / "launcher_wakefulness.json").read_text())
    assert persisted["status"] == "unavailable"
    assert "returned 0" in persisted["error"]


def test_detached_child_resets_awake_state_when_launcher_raises(tmp_path) -> None:
    campaign_root, runner, _manifest = _make_plan(tmp_path)
    runner.unlink()
    args = subject.parse_args(
        [
            "--campaign-root",
            str(campaign_root),
            "--runner",
            str(runner),
            "--detached-child",
        ]
    )
    calls: list[int] = []

    def setter(flags: int) -> int:
        calls.append(flags)
        return 1

    with pytest.raises(FileNotFoundError, match="Missing V2 shard runner"):
        subject.run_detached_child(
            args,
            execution_state_setter=setter,
            platform_name="nt",
            popen_factory=lambda *_args, **_kwargs: pytest.fail("must not launch"),
            sleep=lambda _seconds: None,
        )

    assert calls[-1] == subject.ES_CONTINUOUS
    persisted = json.loads((campaign_root / "launcher_wakefulness.json").read_text())
    assert persisted["status"] == "released"
