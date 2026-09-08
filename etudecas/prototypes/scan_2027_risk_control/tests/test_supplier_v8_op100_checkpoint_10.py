from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_op100_checkpoint_10 as subject,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _complete_metadata(root: Path) -> None:
    lanes = [{"lane_id": f"lane_{index:02d}"} for index in range(18)]
    shards = [
        {"shard_id": shard_id, "seed_ids": list(seeds)}
        for shard_id, seeds in zip(
            subject.TARGET_SHARDS,
            (
                subject.EXPECTED_SEEDS[:5],
                subject.EXPECTED_SEEDS[5:],
            ),
            strict=True,
        )
    ]
    campaign_signature = "a" * 64
    manifest = {
        "campaign_signature": campaign_signature,
        "lanes": lanes,
        "shards": shards,
    }
    _write_json(root / "campaign_manifest.json", manifest)
    for block, (shard_id, seeds) in enumerate(
        zip(
            subject.TARGET_SHARDS,
            (subject.EXPECTED_SEEDS[:5], subject.EXPECTED_SEEDS[5:]),
            strict=True,
        ),
        start=1,
    ):
        shard_root = root / "shards" / shard_id
        progress = {
            "schema_version": subject.campaign_v4.PROGRESS_SCHEMA_VERSION,
            "campaign_signature": campaign_signature,
            "shard_id": shard_id,
            "operating_point_id": "op_100",
            "seed_block": block,
            "seed_ids": list(seeds),
            "status": "complete",
            "planned_case_count": 185,
            "completed_case_count": 185,
            "failed_case_count": 0,
            "running_case_keys": [],
            "errors": [],
        }
        contract = {
            "schema_version": f"{subject.campaign_v4.SCHEMA_VERSION}.shard.v1",
            "campaign_signature": campaign_signature,
            "shard_id": shard_id,
            "shard_index": block,
            "shard_count": 18,
            "operating_point_id": "op_100",
            "operating_point_service_pct": 100.0,
            "seed_block": block,
            "seed_ids": list(seeds),
            "lane_ids": [row["lane_id"] for row in lanes],
            "mechanisms": list(subject.MECHANISMS),
            "target_registry_signature": "b" * 64,
            "v4_holdout_signature": "c" * 64,
            "v4_trace_index_signature": "d" * 64,
            "state_validation_binding_signature": "e" * 64,
            "execution_scope": "campaign_shard",
            "adaptive_horizon": True,
            "planned_case_count": 185,
            "status": "planned",
        }
        contract["shard_signature"] = subject.campaign_v4._stable_sha256(contract)
        completed = {
            **contract,
            "status": "complete",
            "completed_case_count": 185,
            "valid_case_count": 185,
            "invalid_or_not_applicable_case_count": 0,
            "runtime_failure_count": 0,
            "completed_at_utc": f"2026-09-06T0{block}:00:00+00:00",
        }
        _write_json(shard_root / "progress.json", progress)
        _write_json(shard_root / "shard_manifest.json", completed)


def _runner_process(
    root: Path, *, block: int = 1, pid: int = 123
) -> subject.supervisor.ObservedProcess:
    return subject.supervisor.ObservedProcess(
        pid=pid,
        create_time=1.0,
        executable="python.exe",
        command_line=(
            "python.exe",
            str(Path(subject.campaign_v8.__file__).resolve()),
            "--mode",
            "run-shard",
            "--output-dir",
            str(root),
            "--operating-point-id",
            "op_100",
            "--seed-block",
            str(block),
            "--workers",
            "2",
        ),
    )


def test_readiness_uses_process_table_only_while_target_is_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_read(path: Path):  # noqa: ARG001
        raise AssertionError("campaign file read while a target shard is active")

    monkeypatch.setattr(subject, "_read_json_shared", forbidden_read)
    result = subject.evaluate_readiness(
        tmp_path, scanner=lambda: [_runner_process(tmp_path)]
    )
    assert result["status"] == "running_target_shards"
    assert result["campaign_files_read"] is False
    assert result["active_processes"] == [
        {"pid": 123, "shard_id": subject.TARGET_SHARDS[0], "role": "runner"}
    ]


def test_child_writer_is_detected_without_reading_campaign(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = subject.supervisor.ObservedProcess(
        pid=456,
        create_time=1.0,
        executable="python.exe",
        command_line=(
            "python.exe",
            "engine.py",
            "--output-dir",
            str(tmp_path / "shards" / subject.TARGET_SHARDS[1] / "_attempts" / "x"),
        ),
    )
    monkeypatch.setattr(
        subject,
        "_read_json_shared",
        lambda path: (_ for _ in ()).throw(AssertionError(path)),
    )
    result = subject.evaluate_readiness(tmp_path, scanner=lambda: [child])
    assert result["campaign_files_read"] is False
    assert result["active_processes"] == [
        {
            "pid": 456,
            "shard_id": subject.TARGET_SHARDS[1],
            "role": "child_or_writer",
        }
    ]


def test_readiness_requires_exact_complete_185_plus_185(tmp_path: Path) -> None:
    _complete_metadata(tmp_path)
    result = subject.evaluate_readiness(tmp_path, scanner=lambda: [])
    assert result["status"] == "ready_two_complete_shards"
    assert result["completed_case_count"] == 370
    assert result["failed_case_count"] == 0
    assert result["seed_ids"] == list(subject.EXPECTED_SEEDS)

    progress_path = tmp_path / "shards" / subject.TARGET_SHARDS[1] / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    progress["completed_case_count"] = 184
    _write_json(progress_path, progress)
    rejected = subject.evaluate_readiness(tmp_path, scanner=lambda: [])
    assert rejected["status"] == "not_ready"
    assert rejected["ready"] is False
    assert subject.TARGET_SHARDS[1] in rejected["message_fr"]


def _evidence_fixture(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, object], dict[str, tuple[int, ...]], Path]:
    fields = ("case_key", "shard_id", "case_signature", "value")
    monkeypatch.setattr(subject.campaign_v4, "METRIC_FIELDS", fields)
    monkeypatch.setattr(
        subject.campaign_v4,
        "_validate_evidence",
        lambda payload, *, manifest, case_key, case_signature: None,
    )
    monkeypatch.setattr(
        subject.campaign_v4,
        "_flatten_metric_row",
        lambda payload, *, baseline_by_signature: payload["rebuilt"],
    )
    lanes = [{"lane_id": f"lane_{index:02d}"} for index in range(18)]
    manifest: dict[str, object] = {
        "campaign_signature": "a" * 64,
        "lanes": lanes,
    }
    seed_map = {
        subject.TARGET_SHARDS[0]: subject.EXPECTED_SEEDS[:5],
        subject.TARGET_SHARDS[1]: subject.EXPECTED_SEEDS[5:],
    }
    first_risk_path: Path | None = None
    for shard_id in subject.TARGET_SHARDS:
        rows: list[dict[str, str]] = []
        evidence_dir = root / "shards" / shard_id / "case_evidence"
        risk_dir = root / "shards" / shard_id / "inputs" / "risk_events"
        evidence_dir.mkdir(parents=True)
        risk_dir.mkdir(parents=True)
        for seed in seed_map[shard_id]:
            case_key = f"op_100__baseline__seed_{seed}"
            signature = hashlib.sha256(case_key.encode()).hexdigest()
            row = {
                "case_key": case_key,
                "shard_id": shard_id,
                "case_signature": signature,
                "value": "0",
            }
            evidence = {
                "contract_revision": subject.campaign_v4.CONTRACT_REVISION,
                "shard_id": shard_id,
                "valid": True,
                "status": "valid",
                "validation_errors": [],
                "stage": "baseline",
                "case_key": case_key,
                "case_signature": signature,
                "metrics": {
                    "warmup_core_state_sha256": "b" * 64,
                    "summary_sha256": "c" * 64,
                },
                "rebuilt": row,
            }
            rows.append(row)
            _write_json(evidence_dir / f"{case_key}.json", evidence)
        for seed in seed_map[shard_id]:
            for lane in lanes:
                for mechanism in subject.MECHANISMS:
                    case_key = f"op_100__{lane['lane_id']}__{mechanism}__seed_{seed}"
                    signature = hashlib.sha256(case_key.encode()).hexdigest()
                    row = {
                        "case_key": case_key,
                        "shard_id": shard_id,
                        "case_signature": signature,
                        "value": "1",
                    }
                    risk_path = risk_dir / f"{case_key}.csv"
                    risk_path.write_text("event_id\nincident\n", encoding="utf-8")
                    if first_risk_path is None:
                        first_risk_path = risk_path
                    evidence = {
                        "contract_revision": subject.campaign_v4.CONTRACT_REVISION,
                        "shard_id": shard_id,
                        "valid": True,
                        "status": "valid",
                        "validation_errors": [],
                        "stage": "incident",
                        "case_key": case_key,
                        "case_signature": signature,
                        "risk_csv_sha256": subject._sha256_file(risk_path),
                        "metrics": {
                            "warmup_core_state_sha256": "b" * 64,
                            "summary_sha256": "c" * 64,
                        },
                        "rebuilt": row,
                    }
                    rows.append(row)
                    _write_json(evidence_dir / f"{case_key}.json", evidence)
        metrics_path = root / "shards" / shard_id / "campaign_metrics.csv"
        with metrics_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    assert first_risk_path is not None
    return manifest, seed_map, first_risk_path


def test_reconstructs_370_rows_and_checks_every_risk_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, seed_map, first_risk_path = _evidence_fixture(tmp_path, monkeypatch)
    rows, evidence, sources = subject._reconstruct_signed_metrics(
        campaign_root=tmp_path,
        manifest=manifest,
        seed_map=seed_map,
    )
    assert len(rows) == 370
    assert len(evidence) == 370
    assert sum("risk_sha256" in row for row in evidence) == 360
    assert len(sources) == 2

    first_risk_path.write_text("event_id\ntampered\n", encoding="utf-8")
    with pytest.raises(subject.CheckpointError, match="altéré"):
        subject._reconstruct_signed_metrics(
            campaign_root=tmp_path,
            manifest=manifest,
            seed_map=seed_map,
        )


def test_statistics_are_descriptive_and_use_exactly_ten_paired_values() -> None:
    rows: list[dict[str, object]] = []
    for mechanism_index, mechanism in enumerate(subject.MECHANISMS):
        for lane_index in range(18):
            for seed_index, seed in enumerate(subject.EXPECTED_SEEDS):
                value = float(lane_index + mechanism_index + seed_index / 10)
                rows.append(
                    {
                        "mechanism": mechanism,
                        "lane_id": f"lane_{lane_index:02d}",
                        "seed": seed,
                        "supplier_id": f"SUP-{lane_index:02d}",
                        "item_id": f"item:{lane_index:06d}",
                        "dst_node_id": "M-1810",
                        "target_product_id": "268091",
                        "incident_physically_exercised": True,
                        "impact_service_loss_fed_product_pp": value,
                        "impact_on_due_loss_fed_product_qty": 10 * value,
                        "impact_backlog_qty_days_per_demand_unit": value / 10,
                        "impact_production_loss_fed_product_qty": 5 * value,
                        "causal_service_loss_fed_product_pp": value / 2,
                        "effective_exposure_dose": 100.0,
                        "effective_exposure_dose_unit": "unite_jour_de_retard",
                    }
                )
    lane_rows, supplier_rows = subject._descriptive_statistics(pd.DataFrame(rows))
    assert len(lane_rows) == 36
    assert len(supplier_rows) == 36
    assert all(row["simulation_count"] == 10 for row in lane_rows)
    assert all(
        "ci95" not in key and "bootstrap" not in key for row in lane_rows for key in row
    )
    for mechanism in subject.MECHANISMS:
        selected = [row for row in supplier_rows if row["mechanism"] == mechanism]
        assert [row["descriptive_order"] for row in selected] == list(range(1, 19))
        assert selected[0]["supplier_id"] == "SUP-17"


def test_v8_comparability_is_projected_only_on_validation_copy() -> None:
    source = pd.DataFrame(
        [
            {
                "stage": "incident",
                "operating_point_id": "op_100",
                "seed": str(subject.EXPECTED_SEEDS[0]),
                "lane_id": "lane_00",
                "required_comparable_seed_count": "",
                "comparable_campaign_seed_count": "",
                "seed_cross_state_exposure_comparable": "",
            },
            {
                "stage": "baseline",
                "operating_point_id": "op_100",
                "seed": str(subject.EXPECTED_SEEDS[0]),
                "lane_id": "",
                "required_comparable_seed_count": "",
                "comparable_campaign_seed_count": "",
                "seed_cross_state_exposure_comparable": "",
            },
        ]
    )
    context = SimpleNamespace(
        registry={
            "required_comparable_seed_count": 30,
            "targets": [
                {
                    "operating_point_id": "op_100",
                    "seed": subject.EXPECTED_SEEDS[0],
                    "lane_id": "lane_00",
                    "required_comparable_seed_count": 30,
                    "comparable_campaign_seed_count": 30,
                    "seed_cross_state_exposure_comparable": True,
                }
            ],
        }
    )

    projected = subject._v8_compatibility_validation_frame(source, context=context)

    assert source.loc[0, "required_comparable_seed_count"] == ""
    assert source.loc[0, "comparable_campaign_seed_count"] == ""
    assert source.loc[0, "seed_cross_state_exposure_comparable"] == ""
    assert projected.loc[0, "required_comparable_seed_count"] == 30
    assert projected.loc[0, "comparable_campaign_seed_count"] == 30
    assert projected.loc[0, "seed_cross_state_exposure_comparable"] is True
    assert projected.loc[1, "required_comparable_seed_count"] == ""
    assert projected.loc[1, "comparable_campaign_seed_count"] == ""
    assert projected.loc[1, "seed_cross_state_exposure_comparable"] == ""


def test_v8_comparability_projection_rejects_source_registry_conflict() -> None:
    source = pd.DataFrame(
        [
            {
                "stage": "incident",
                "operating_point_id": "op_100",
                "seed": str(subject.EXPECTED_SEEDS[0]),
                "lane_id": "lane_00",
                "required_comparable_seed_count": "24",
                "comparable_campaign_seed_count": "",
                "seed_cross_state_exposure_comparable": "",
            }
        ]
    )
    context = SimpleNamespace(
        registry={
            "required_comparable_seed_count": 30,
            "targets": [
                {
                    "operating_point_id": "op_100",
                    "seed": subject.EXPECTED_SEEDS[0],
                    "lane_id": "lane_00",
                    "required_comparable_seed_count": 30,
                    "comparable_campaign_seed_count": 30,
                    "seed_cross_state_exposure_comparable": True,
                }
            ],
        }
    )

    with pytest.raises(subject.CheckpointError, match="Mesure/registre V8"):
        subject._v8_compatibility_validation_frame(source, context=context)


@pytest.mark.parametrize("targets", [[], "duplicate"])
def test_v8_comparability_projection_rejects_missing_or_duplicate_target(
    targets: list[dict[str, object]] | str,
) -> None:
    source = pd.DataFrame(
        [
            {
                "stage": "incident",
                "operating_point_id": "op_100",
                "seed": str(subject.EXPECTED_SEEDS[0]),
                "lane_id": "lane_00",
                "required_comparable_seed_count": "",
                "comparable_campaign_seed_count": "",
                "seed_cross_state_exposure_comparable": "",
            }
        ]
    )
    target = {
        "operating_point_id": "op_100",
        "seed": subject.EXPECTED_SEEDS[0],
        "lane_id": "lane_00",
        "required_comparable_seed_count": 30,
        "comparable_campaign_seed_count": 30,
        "seed_cross_state_exposure_comparable": True,
    }
    registry_targets = [target, dict(target)] if targets == "duplicate" else targets
    context = SimpleNamespace(
        registry={
            "required_comparable_seed_count": 30,
            "targets": registry_targets,
        }
    )

    expected = "dupliquée" if targets == "duplicate" else "absente"
    with pytest.raises(subject.CheckpointError, match=expected):
        subject._v8_compatibility_validation_frame(source, context=context)


def test_v8_comparability_projection_accepts_matching_source_values() -> None:
    source = pd.DataFrame(
        [
            {
                "stage": "incident",
                "operating_point_id": "op_100",
                "seed": str(subject.EXPECTED_SEEDS[0]),
                "lane_id": "lane_00",
                "required_comparable_seed_count": "30",
                "comparable_campaign_seed_count": "30.0",
                "seed_cross_state_exposure_comparable": "true",
            }
        ]
    )
    context = SimpleNamespace(
        registry={
            "required_comparable_seed_count": 30,
            "targets": [
                {
                    "operating_point_id": "op_100",
                    "seed": subject.EXPECTED_SEEDS[0],
                    "lane_id": "lane_00",
                    "required_comparable_seed_count": 30,
                    "comparable_campaign_seed_count": 30,
                    "seed_cross_state_exposure_comparable": True,
                }
            ],
        }
    )

    projected = subject._v8_compatibility_validation_frame(source, context=context)

    assert projected.loc[0, "required_comparable_seed_count"] == 30
    assert projected.loc[0, "comparable_campaign_seed_count"] == 30
    assert projected.loc[0, "seed_cross_state_exposure_comparable"] is True


def test_html_is_standalone_and_explicitly_provisional() -> None:
    supplier_rows = []
    for index, mechanism in enumerate(subject.MECHANISMS, start=1):
        supplier_rows.append(
            {
                "mechanism": mechanism,
                "descriptive_order": index,
                "supplier_id": "SDC-TEST",
                "item_id": "item:338929",
                "dst_node_id": "M-1810",
                "target_product_id": "268091",
                "service_loss_mean_pp": 1.2,
                "service_loss_min_pp": 0.0,
                "service_loss_max_pp": 2.4,
                "physical_exercise_count": 10,
                "on_due_units_lost_mean": 100.0,
                "production_not_released_mean_qty": 50.0,
            }
        )
    page = subject.render_html({"supplier_view": supplier_rows})
    subject._validate_html(page)
    assert "RÉSULTAT PROVISOIRE" in page
    assert "répétitions stochastiques appariées" in page
    assert "protocole de nombres aléatoires communs" in page
    assert "mêmes aléas internes" not in page
    assert "http://" not in page
    assert "https://" not in page


def test_atomic_publication_is_new_or_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subject, "validate_package", lambda path: {})
    destination = tmp_path / "checkpoint"
    first, identical = subject._publish_new_or_identical(
        output_dir=destination, files={"proof.txt": b"same"}
    )
    assert first == destination.resolve()
    assert identical is False
    second, identical = subject._publish_new_or_identical(
        output_dir=destination, files={"proof.txt": b"same"}
    )
    assert second == first
    assert identical is True
    with pytest.raises(subject.CheckpointError, match="aucun écrasement"):
        subject._publish_new_or_identical(
            output_dir=destination, files={"proof.txt": b"different"}
        )
    assert (destination / "proof.txt").read_bytes() == b"same"


def test_complete_provisional_package_round_trip(tmp_path: Path) -> None:
    paired_rows: list[dict[str, object]] = []
    for mechanism_index, mechanism in enumerate(subject.MECHANISMS):
        for lane_index in range(18):
            for seed_index, seed in enumerate(subject.EXPECTED_SEEDS):
                value = float(lane_index + mechanism_index + seed_index / 10)
                paired_rows.append(
                    {
                        "mechanism": mechanism,
                        "lane_id": f"lane_{lane_index:02d}",
                        "seed": seed,
                        "supplier_id": f"SUP-{lane_index:02d}",
                        "item_id": f"item:{lane_index:06d}",
                        "dst_node_id": "M-1810",
                        "target_product_id": "268091",
                        "incident_physically_exercised": True,
                        "impact_service_loss_fed_product_pp": value,
                        "impact_on_due_loss_fed_product_qty": 10 * value,
                        "impact_backlog_qty_days_per_demand_unit": value / 10,
                        "impact_production_loss_fed_product_qty": 5 * value,
                        "causal_service_loss_fed_product_pp": value / 2,
                        "effective_exposure_dose": 100.0,
                        "effective_exposure_dose_unit": "unite_jour_de_retard",
                    }
                )
    metric_rows = []
    for index in range(subject.EXPECTED_TOTAL_COUNT):
        metric_rows.append(
            {
                field: (
                    f"case-{index}"
                    if field == "case_key"
                    else subject.TARGET_SHARDS[index % 2]
                    if field == "shard_id"
                    else ""
                )
                for field in subject.campaign_v4.METRIC_FIELDS
            }
        )
    evidence_rows = []
    for index in range(subject.EXPECTED_TOTAL_COUNT):
        evidence_rows.append(
            {
                "case_key": f"case-{index}",
                "shard_id": subject.TARGET_SHARDS[index % 2],
                "stage": "baseline"
                if index < subject.EXPECTED_BASELINE_COUNT
                else "incident",
                "mechanism": (
                    "baseline"
                    if index < subject.EXPECTED_BASELINE_COUNT
                    else subject.MECHANISMS[index % 2]
                ),
                "evidence_relative_path": f"proof/{index}.json",
                "evidence_sha256": hashlib.sha256(
                    f"proof-{index}".encode()
                ).hexdigest(),
                **(
                    {}
                    if index < subject.EXPECTED_BASELINE_COUNT
                    else {
                        "risk_relative_path": f"risk/{index}.csv",
                        "risk_sha256": hashlib.sha256(
                            f"risk-{index}".encode()
                        ).hexdigest(),
                    }
                ),
            }
        )
    snapshot = subject.SourceSnapshot(
        campaign_root=tmp_path / "source",
        manifest={"campaign_signature": "a" * 64},
        context=SimpleNamespace(disruption_window_days=42),
        seeds=subject.EXPECTED_SEEDS,
        metric_rows=tuple(metric_rows),
        paired=pd.DataFrame(paired_rows),
        evidence_index=tuple(evidence_rows),
        source_files={},
        completed_at_utc="2026-09-06T02:00:00+00:00",
    )
    files = subject._files_for_package(snapshot)
    output, identical = subject._publish_new_or_identical(
        output_dir=tmp_path / "delivery", files=files
    )
    assert identical is False
    manifest = subject.validate_package(output)
    assert manifest["source_case_count"] == 370
    assert set(path.name for path in output.iterdir()) == subject.PACKAGE_FILES


def test_build_refuses_before_any_source_load_when_shards_are_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subject,
        "_load_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("source load")),
    )
    with pytest.raises(subject.CheckpointNotReady):
        subject.build_checkpoint(
            campaign_root=tmp_path,
            output_dir=tmp_path.parent / "outside",
            scanner=lambda: [_runner_process(tmp_path)],
        )
    assert not (tmp_path.parent / "outside").exists()
