from __future__ import annotations

import csv

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v4 as subject,
)


def _write_smoke_fixture(tmp_path):
    seed = subject.EXPECTED_CAMPAIGN_SEEDS[0]
    lane_id = "lane_01"
    campaign_signature = "a" * 64
    engine_sha = "b" * 64
    manifest = {
        "campaign_signature": campaign_signature,
        "engine_sha256": engine_sha,
        "lanes": [{"lane_id": lane_id}],
        "operating_points_source": str(tmp_path / "bridge.json"),
        "lane_reference_source": str(tmp_path / "lanes.csv"),
        "engine": str(tmp_path / "engine.py"),
        "engine_profile": str(tmp_path / "profile.json"),
        "operating_points_holdout_signature": "c" * 64,
        "operating_points_trace_index_signature": "d" * 64,
        "state_validation_binding_signature": "e" * 64,
    }
    registry_dir = tmp_path / "target_discovery"
    registry_dir.mkdir()
    subject._write_json_atomic(
        registry_dir / "target_registry.json",
        {
            "targets": [
                {
                    "operating_point_id": "op_93",
                    "seed": seed,
                    "lane_id": lane_id,
                    "seed_cross_state_exposure_comparable": True,
                    "target_status": "identified_reference_lane_window_shipment_group",
                    "target_planned_qty": 10.0,
                }
            ]
        },
    )
    shard_id = f"smoke__op_93__seed_{seed}"
    smoke_dir = tmp_path / "smoke" / shard_id
    smoke_dir.mkdir(parents=True)
    progress = {
        "schema_version": subject.SHARD_PROGRESS_SCHEMA_VERSION,
        "campaign_signature": campaign_signature,
        "shard_id": shard_id,
        "operating_point_id": "op_93",
        "seed_ids": [seed],
        "status": "complete",
        "planned_case_count": 3,
        "completed_case_count": 3,
        "failed_case_count": 0,
        "running_case_keys": [],
        "errors": [],
    }
    subject._write_json_atomic(smoke_dir / "progress.json", progress)
    shard_unsigned = {
        "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.shard.v1",
        "campaign_signature": campaign_signature,
        "shard_id": shard_id,
        "shard_index": 1,
        "shard_count": 1,
        "operating_point_id": "op_93",
        "operating_point_service_pct": 93.0,
        "seed_block": 1,
        "seed_ids": [seed],
        "lane_ids": [lane_id],
        "mechanisms": ["transport_delay", "planned_delivery_shortfall"],
        "target_registry_signature": "f" * 64,
        "v4_holdout_signature": manifest["operating_points_holdout_signature"],
        "v4_trace_index_signature": manifest[
            "operating_points_trace_index_signature"
        ],
        "state_validation_binding_signature": manifest[
            "state_validation_binding_signature"
        ],
        "execution_scope": "smoke_non_reusable",
        "adaptive_horizon": True,
        "planned_case_count": 3,
        "status": "planned",
    }
    shard_manifest = {
        **shard_unsigned,
        "shard_signature": subject._stable_sha256(shard_unsigned),
        "status": "complete",
        "completed_case_count": 3,
        "valid_case_count": 3,
        "invalid_or_not_applicable_case_count": 0,
        "runtime_failure_count": 0,
        "completed_at_utc": "2026-09-05T12:00:00+00:00",
    }
    subject._write_json_atomic(smoke_dir / "shard_manifest.json", shard_manifest)

    baseline_key = f"op_93__baseline__seed_{seed}"
    baseline_signature = "1" * 64
    rows = [
        {
            "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.case.v1",
            "campaign_signature": campaign_signature,
            "engine_sha256": engine_sha,
            "shard_id": shard_id,
            "operating_point_id": "op_93",
            "seed": seed,
            "stage": "baseline",
            "mechanism": "baseline",
            "lane_id": "",
            "case_key": baseline_key,
            "case_signature": baseline_signature,
            "baseline_case_signature": baseline_signature,
            "warmup_core_state_sha256": "2" * 64,
            "valid": True,
            "validation_errors": "",
            "incident_physically_exercised": "",
        }
    ]
    for index, mechanism in enumerate(subject.EXPECTED_MECHANISMS, 3):
        rows.append(
            {
                "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.case.v1",
                "campaign_signature": campaign_signature,
                "engine_sha256": engine_sha,
                "shard_id": shard_id,
                "operating_point_id": "op_93",
                "seed": seed,
                "stage": "incident",
                "mechanism": mechanism,
                "lane_id": lane_id,
                "case_key": f"op_93__{lane_id}__{mechanism}__seed_{seed}",
                "case_signature": str(index) * 64,
                "baseline_case_signature": baseline_signature,
                "warmup_core_state_sha256": "2" * 64,
                "valid": True,
                "validation_errors": "",
                "incident_physically_exercised": True,
            }
        )
    with (smoke_dir / "campaign_metrics.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    evidence_dir = smoke_dir / "case_evidence"
    risk_dir = smoke_dir / "inputs" / "risk_events"
    evidence_dir.mkdir()
    risk_dir.mkdir(parents=True)
    for row in rows:
        evidence = {
            "schema_version": row["schema_version"],
            "contract_revision": subject.EXPECTED_CONTRACT_REVISION,
            "campaign_signature": campaign_signature,
            "engine_sha256": engine_sha,
            "shard_id": shard_id,
            "operating_point_id": "op_93",
            "seed": seed,
            "stage": row["stage"],
            "case_key": row["case_key"],
            "case_signature": row["case_signature"],
            "status": "valid",
            "valid": True,
            "validation_errors": [],
            "quality_branch_included": False,
            "availability_incident_included": False,
            "supplier_state_dependent_risks_enabled": False,
            "metrics": {"warmup_core_state_sha256": "2" * 64},
        }
        if row["stage"] == "incident":
            risk_path = risk_dir / f"{row['case_key']}.csv"
            risk_path.write_text("event_id\nsmoke\n", encoding="utf-8")
            evidence.update(
                {
                    "lane": {"lane_id": lane_id},
                    "mechanism": {"key": row["mechanism"]},
                    "incident_proof": {"incident_physically_exercised": True},
                    "baseline_case_signature": baseline_signature,
                    "risk_csv_sha256": subject._sha256_file(risk_path),
                }
            )
        evidence["evidence_signature"] = subject._stable_sha256(evidence)
        subject._write_json_atomic(
            evidence_dir / f"{row['case_key']}.json", evidence
        )
    return manifest, smoke_dir


def _write_complete_shard_fixture(tmp_path):
    shard = subject.Shard(
        shard_id="op_100__seed_block_01",
        shard_index=1,
        operating_point_id="op_100",
        seed_block=1,
        seed_ids=tuple(subject.EXPECTED_CAMPAIGN_SEEDS[:5]),
    )
    campaign_signature = "a" * 64
    lane_ids = [f"lane_{index:02d}" for index in range(1, 19)]
    shard_dir = tmp_path / "shards" / shard.shard_id
    shard_dir.mkdir(parents=True)
    subject._write_json_atomic(
        shard_dir / "progress.json",
        {
            "schema_version": subject.SHARD_PROGRESS_SCHEMA_VERSION,
            "campaign_signature": campaign_signature,
            "shard_id": shard.shard_id,
            "status": "complete",
            "planned_case_count": subject.EXPECTED_CASES_PER_SHARD,
            "completed_case_count": subject.EXPECTED_CASES_PER_SHARD,
            "failed_case_count": 0,
        },
    )
    unsigned = {
        "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.shard.v1",
        "campaign_signature": campaign_signature,
        "shard_id": shard.shard_id,
        "shard_index": shard.shard_index,
        "shard_count": subject.EXPECTED_SHARD_COUNT,
        "operating_point_id": shard.operating_point_id,
        "operating_point_service_pct": 100.0,
        "seed_block": shard.seed_block,
        "seed_ids": list(shard.seed_ids),
        "lane_ids": lane_ids,
        "mechanisms": sorted(subject.EXPECTED_MECHANISMS),
        "target_registry_signature": "b" * 64,
        "v4_holdout_signature": "c" * 64,
        "v4_trace_index_signature": "d" * 64,
        "state_validation_binding_signature": "e" * 64,
        "execution_scope": "campaign_shard",
        "adaptive_horizon": True,
        "planned_case_count": subject.EXPECTED_CASES_PER_SHARD,
        "status": "planned",
    }
    shard_manifest = {
        **unsigned,
        "shard_signature": subject._stable_sha256(unsigned),
        "status": "complete",
        "completed_case_count": subject.EXPECTED_CASES_PER_SHARD,
        "valid_case_count": subject.EXPECTED_CASES_PER_SHARD,
        "invalid_or_not_applicable_case_count": 0,
        "runtime_failure_count": 0,
        "completed_at_utc": "2026-09-05T12:00:00+00:00",
    }
    subject._write_json_atomic(shard_dir / "shard_manifest.json", shard_manifest)
    rows = []
    for seed in shard.seed_ids:
        baseline_key = f"{shard.operating_point_id}__baseline__seed_{seed}"
        rows.append(
            {
                "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.case.v1",
                "campaign_signature": campaign_signature,
                "shard_id": shard.shard_id,
                "operating_point_id": shard.operating_point_id,
                "seed": seed,
                "stage": "baseline",
                "mechanism": "baseline",
                "lane_id": "",
                "case_key": baseline_key,
                "case_signature": subject._stable_sha256({"case": baseline_key}),
                "warmup_core_state_sha256": "f" * 64,
                "summary_sha256": subject._stable_sha256({"summary": baseline_key}),
                "valid": True,
                "validation_errors": "",
            }
        )
        for lane_id in lane_ids:
            for mechanism in subject.EXPECTED_MECHANISMS:
                key = f"{shard.operating_point_id}__{lane_id}__{mechanism}__seed_{seed}"
                rows.append(
                    {
                        "schema_version": f"{subject.INPUT_SCHEMA_VERSION}.case.v1",
                        "campaign_signature": campaign_signature,
                        "shard_id": shard.shard_id,
                        "operating_point_id": shard.operating_point_id,
                        "seed": seed,
                        "stage": "incident",
                        "mechanism": mechanism,
                        "lane_id": lane_id,
                        "case_key": key,
                        "case_signature": subject._stable_sha256({"case": key}),
                        "warmup_core_state_sha256": "f" * 64,
                        "summary_sha256": subject._stable_sha256({"summary": key}),
                        "valid": True,
                        "validation_errors": "",
                    }
                )
    with (shard_dir / "campaign_metrics.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return campaign_signature, shard, shard_dir, rows


def test_v4_seed_and_shard_contract_is_frozen() -> None:
    assert len(subject.EXPECTED_CAMPAIGN_SEEDS) == 30
    assert 900659036 not in subject.EXPECTED_CAMPAIGN_SEEDS
    assert subject.EXPECTED_DISCOVERY_RUNS == 3
    assert subject.EXPECTED_SHARD_COUNT == 18
    assert subject.EXPECTED_CASES_PER_SHARD == 185
    assert subject.EXPECTED_TOTAL_CASES == 3330


def test_smoke_completion_revalidates_three_signed_non_reusable_cases(tmp_path) -> None:
    manifest, smoke_dir = _write_smoke_fixture(tmp_path)

    assert subject._smoke_completion_state(tmp_path, manifest=manifest) == (
        "complete",
        "",
    )

    risk_path = next((smoke_dir / "inputs" / "risk_events").glob("*.csv"))
    risk_path.write_text("tampered", encoding="utf-8")
    status, detail = subject._smoke_completion_state(tmp_path, manifest=manifest)
    assert status == "invalid"
    assert "risk CSV" in detail


def test_smoke_rejects_empty_warmup_hashes(tmp_path) -> None:
    manifest, smoke_dir = _write_smoke_fixture(tmp_path)
    metrics_path = smoke_dir / "campaign_metrics.csv"
    with metrics_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["warmup_core_state_sha256"] = ""
    with metrics_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    status, detail = subject._smoke_completion_state(tmp_path, manifest=manifest)

    assert status == "invalid"
    assert "pairing" in detail


def test_smoke_command_is_one_worker_and_explicit_identity(tmp_path) -> None:
    manifest, _ = _write_smoke_fixture(tmp_path)
    runner = tmp_path / "runner.py"
    runner.write_text("# fixture", encoding="utf-8")

    command = subject.build_smoke_command(
        runner=runner, campaign_root=tmp_path, manifest=manifest
    )

    assert command[command.index("--operating-point-id") + 1] == "op_93"
    assert command[command.index("--smoke-seed") + 1] == str(
        subject.EXPECTED_CAMPAIGN_SEEDS[0]
    )
    assert command[command.index("--smoke-lane-id") + 1] == "lane_01"
    assert command[command.index("--workers") + 1] == "1"


def test_complete_shard_is_revalidated_before_resume_skip(tmp_path) -> None:
    signature, shard, shard_dir, rows = _write_complete_shard_fixture(tmp_path)

    assert subject._completion_state(
        tmp_path, campaign_signature=signature, shard=shard
    ) == ("complete", "")

    with (shard_dir / "campaign_metrics.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[:-1])
    status, detail = subject._completion_state(
        tmp_path, campaign_signature=signature, shard=shard
    )
    assert status == "invalid"
    assert "metric matrix" in detail
