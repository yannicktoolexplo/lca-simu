from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_state_checkpoint as subject,
)


@pytest.mark.parametrize("point", subject.OPERATING_POINTS)
@pytest.mark.parametrize("count", subject.SIMULATION_COUNTS)
def test_config_covers_every_state_and_cumulative_checkpoint(
    point: str, count: int
) -> None:
    config = subject.make_config(point, count)
    assert config.target_blocks == tuple(range(1, count // 5 + 1))
    assert config.target_shards == tuple(
        f"{point}__seed_block_{block:02d}" for block in config.target_blocks
    )
    assert config.expected_seeds == tuple(
        subject.legacy.trace_package.CAMPAIGN_SEEDS[:count]
    )
    assert config.baseline_count == count
    assert config.incident_count == 36 * count
    assert config.total_count == 37 * count
    assert config.risk_file_count == 36 * count
    assert len(config.source_metadata_paths) == 1 + 2 * (count // 5)
    assert str(count) in config.html_name
    assert point.upper() in config.html_name


def test_cli_defaults_to_read_only_readiness() -> None:
    args = subject._parser().parse_args(  # noqa: SLF001
        [
            "--operating-point-id",
            "op_100",
            "--simulation-count",
            "20",
        ]
    )
    assert args.mode == "readiness"
    assert args.output_dir is None


def test_frozen_legacy_is_pinned_and_context_restores_every_patch() -> None:
    path = subject.validate_frozen_legacy()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        subject.EXPECTED_LEGACY_SHA256
    )
    config = subject.make_config("op_93", 20)
    original_targets = subject.legacy.TARGET_SHARDS
    original_render = subject.legacy.render_html
    original_validator = subject.legacy.validate_package
    with subject.patched_checkpoint_context(config):
        assert subject.legacy.TARGET_SHARDS == config.target_shards
        assert subject.legacy.EXPECTED_SEEDS == config.expected_seeds
        assert subject.legacy.EXPECTED_TOTAL_COUNT == 740
        assert subject.legacy.render_html is not original_render
        assert subject.legacy.validate_package is not original_validator
        assert subject.legacy.campaign_v8.REQUIRED_COMPARABLE_SEED_COUNT == 30
        with subject.legacy._partial_validation_constants():  # noqa: SLF001
            assert subject.legacy.finalizer_v4.OPERATING_POINTS == ("op_93",)
            assert subject.legacy.finalizer_v4.EXPECTED_REPETITION_COUNT == 20
    assert subject.legacy.TARGET_SHARDS is original_targets
    assert subject.legacy.render_html is original_render
    assert subject.legacy.validate_package is original_validator


def test_v8_comparability_remains_a_signed_30_seed_contract() -> None:
    config = subject.make_config("op_93", 20)
    seed = config.expected_seeds[0]
    frame = pd.DataFrame(
        [
            {
                "stage": "incident",
                "operating_point_id": "op_93",
                "seed": str(seed),
                "lane_id": "lane_00",
                "required_comparable_seed_count": "",
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
                    "operating_point_id": "op_93",
                    "seed": seed,
                    "lane_id": "lane_00",
                    "required_comparable_seed_count": 30,
                    "comparable_campaign_seed_count": 30,
                    "seed_cross_state_exposure_comparable": True,
                }
            ],
        }
    )
    with subject.patched_checkpoint_context(config):
        projected = subject.legacy._v8_compatibility_validation_frame(  # noqa: SLF001
            frame, context=context
        )
    assert projected.loc[0, "required_comparable_seed_count"] == 30
    assert projected.loc[0, "comparable_campaign_seed_count"] == 30
    assert projected.loc[0, "seed_cross_state_exposure_comparable"] is True


def test_expected_case_keys_are_bound_to_selected_state() -> None:
    config = subject.make_config("op_80", 10)
    keys = subject._expected_case_keys(  # noqa: SLF001
        config,
        shard_id=config.target_shards[0],
        seeds=config.expected_seeds[:5],
        lane_ids=["lane_a", "lane_b"],
    )
    assert len(keys) == 5 * (1 + 2 * 2)
    assert all(key.startswith("op_80__") for key in keys)
    assert not any(key.startswith("op_100__") for key in keys)


def test_seed_map_rejects_wrong_state_block_or_seed_order() -> None:
    config = subject.make_config("op_80", 20)
    rows = []
    for block, shard_id in zip(config.target_blocks, config.target_shards, strict=True):
        rows.append(
            {
                "shard_id": shard_id,
                "operating_point_id": "op_80",
                "seed_block": block,
                "seed_ids": list(
                    config.expected_seeds[(block - 1) * 5 : block * 5]
                ),
            }
        )
    manifest = {"shards": rows}
    assert tuple(
        seed
        for shard_id in config.target_shards
        for seed in subject._expected_seed_map(manifest, config)[shard_id]  # noqa: SLF001
    ) == config.expected_seeds

    wrong_state = {"shards": [dict(row) for row in rows]}
    wrong_state["shards"][2]["operating_point_id"] = "op_93"
    with pytest.raises(subject.StateCheckpointError, match="incohérent"):
        subject._expected_seed_map(wrong_state, config)  # noqa: SLF001

    wrong_block = {"shards": [dict(row) for row in rows]}
    wrong_block["shards"][1]["seed_block"] = 6
    with pytest.raises(subject.StateCheckpointError, match="incohérent"):
        subject._expected_seed_map(wrong_block, config)  # noqa: SLF001

    wrong_seed = {"shards": [dict(row) for row in rows]}
    wrong_seed["shards"][0] = {
        **wrong_seed["shards"][0],
        "seed_ids": list(reversed(wrong_seed["shards"][0]["seed_ids"])),
    }
    with pytest.raises(subject.StateCheckpointError, match="premières graines"):
        subject._expected_seed_map(wrong_seed, config)  # noqa: SLF001


def _complete_shard_documents(
    config: subject.CheckpointConfig, block: int
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    shard_id = config.target_shards[block - 1]
    seeds = list(config.expected_seeds[(block - 1) * 5 : block * 5])
    shard_index = subject.OPERATING_POINTS.index(config.operating_point_id) * 6 + block
    lanes = [{"lane_id": f"lane_{index:02d}"} for index in range(18)]
    manifest: dict[str, object] = {
        "campaign_signature": config.expected_campaign_signature,
        "lanes": lanes,
    }
    progress: dict[str, object] = {
        "schema_version": subject.legacy.campaign_v4.PROGRESS_SCHEMA_VERSION,
        "campaign_signature": config.expected_campaign_signature,
        "shard_id": shard_id,
        "shard_index": shard_index,
        "operating_point_id": config.operating_point_id,
        "seed_block": block,
        "seed_ids": seeds,
        "status": "complete",
        "planned_case_count": 185,
        "completed_case_count": 185,
        "failed_case_count": 0,
        "running_case_keys": [],
        "errors": [],
    }
    planned: dict[str, object] = {
        "schema_version": f"{subject.legacy.campaign_v4.SCHEMA_VERSION}.shard.v1",
        "campaign_signature": config.expected_campaign_signature,
        "shard_id": shard_id,
        "shard_index": shard_index,
        "operating_point_id": config.operating_point_id,
        "seed_block": block,
        "seed_ids": seeds,
        "lane_ids": [row["lane_id"] for row in lanes],
        "mechanisms": list(subject.MECHANISMS),
        "execution_scope": "campaign_shard",
        "adaptive_horizon": True,
        "planned_case_count": 185,
        "status": "planned",
    }
    signature = subject.legacy.campaign_v4._stable_sha256(planned)  # noqa: SLF001
    shard_manifest = {
        **planned,
        "status": "complete",
        "shard_signature": signature,
        "completed_case_count": 185,
        "valid_case_count": 185,
        "invalid_or_not_applicable_case_count": 0,
        "runtime_failure_count": 0,
        "completed_at_utc": "2026-09-06T20:00:00+00:00",
    }
    return manifest, progress, shard_manifest


def test_complete_shard_contract_is_state_dependent_and_signed() -> None:
    config = subject.make_config("op_93", 20)
    manifest, progress, shard_manifest = _complete_shard_documents(config, 3)
    subject._validate_complete_shard_metadata(  # noqa: SLF001
        config,
        manifest=manifest,
        shard_id=config.target_shards[2],
        block_number=3,
        seeds=config.expected_seeds[10:15],
        progress=progress,
        shard_manifest=shard_manifest,
    )
    progress["operating_point_id"] = "op_100"
    with pytest.raises(subject.StateCheckpointNotReady, match="incomplet"):
        subject._validate_complete_shard_metadata(  # noqa: SLF001
            config,
            manifest=manifest,
            shard_id=config.target_shards[2],
            block_number=3,
            seeds=config.expected_seeds[10:15],
            progress=progress,
            shard_manifest=shard_manifest,
        )


def test_readiness_reads_no_campaign_file_while_target_is_active(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = subject.make_config("op_100", 20)
    monkeypatch.setattr(
        subject.legacy,
        "_active_targets",
        lambda _root, scanner: [
            {"pid": 321, "shard_id": config.target_shards[2], "role": "runner"}
        ],
    )
    monkeypatch.setattr(
        subject.legacy,
        "_read_json_shared",
        lambda _path: (_ for _ in ()).throw(AssertionError("campaign read")),
    )
    payload = subject.evaluate_readiness(
        tmp_path, config=config, scanner=lambda: []
    )
    assert payload["ready"] is False
    assert payload["status"] == "running_target_shards"
    assert payload["campaign_files_read"] is False
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize(
    ("point", "count"),
    [
        ("op_100", 20),
        ("op_93", 10),
        ("op_93", 20),
        ("op_80", 20),
        ("op_100", 30),
        ("op_93", 30),
        ("op_80", 30),
    ],
)
def test_requested_milestones_render_dynamic_denominators(
    point: str, count: int
) -> None:
    config = subject.make_config(point, count)
    row = {
        field: (
            "transport_delay"
            if field == "mechanism"
            else "SUP"
            if field == "supplier_id"
            else "lane"
            if field == "representative_lane_id"
            else "item:338929"
            if field == "item_id"
            else "M-1810"
            if field == "dst_node_id"
            else "268091"
            if field == "target_product_id"
            else count
            if field in {"simulation_count", "physical_exercise_count"}
            else 1
        )
        for field in subject.SUPPLIER_STAT_FIELDS
    }
    page = subject._render_html({"supplier_view": [row]}, config)  # noqa: SLF001
    subject._validate_html(page, config)  # noqa: SLF001
    assert f"{count}/30" in page
    assert f"Effet positif x/{count}" in page
    assert f"Incident exercé x/{count}" in page
    assert point in page


def _paired_rows(config: subject.CheckpointConfig) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for mechanism_index, mechanism in enumerate(subject.MECHANISMS):
        for lane_index in range(18):
            for seed_index, seed in enumerate(config.expected_seeds):
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
                        "incident_physically_exercised": seed_index % 2 == 0,
                        "impact_service_loss_fed_product_pp": value,
                        "impact_on_due_loss_fed_product_qty": 10 * value,
                        "impact_backlog_qty_days_per_demand_unit": value / 10,
                        "impact_production_loss_fed_product_qty": 5 * value,
                        "causal_service_loss_fed_product_pp": value / 2,
                        "effective_exposure_dose": 100.0,
                        "effective_exposure_dose_unit": "unite_jour_de_retard",
                    }
                )
    return rows


def _metric_and_evidence_rows(
    config: subject.CheckpointConfig,
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    metrics: list[dict[str, str]] = []
    evidence: list[dict[str, object]] = []
    for seed_index, seed in enumerate(config.expected_seeds):
        shard_id = config.target_shards[seed_index // 5]
        cases = [(f"{config.operating_point_id}__baseline__seed_{seed}", "baseline", "baseline")]
        cases.extend(
            (
                f"{config.operating_point_id}__lane_{lane:02d}__{mechanism}__seed_{seed}",
                "incident",
                mechanism,
            )
            for lane in range(18)
            for mechanism in subject.MECHANISMS
        )
        for case_key, stage, mechanism in cases:
            row = {field: "" for field in subject.legacy.campaign_v4.METRIC_FIELDS}
            row.update(
                {
                    "case_key": case_key,
                    "shard_id": shard_id,
                    "operating_point_id": config.operating_point_id,
                    "seed": str(seed),
                    "stage": stage,
                    "mechanism": mechanism,
                }
            )
            metrics.append(row)
            entry: dict[str, object] = {
                "case_key": case_key,
                "shard_id": shard_id,
                "stage": stage,
                "mechanism": mechanism,
                "evidence_relative_path": f"proof/{case_key}.json",
                "evidence_sha256": hashlib.sha256(case_key.encode()).hexdigest(),
            }
            if stage == "incident":
                entry.update(
                    {
                        "risk_relative_path": f"risk/{case_key}.csv",
                        "risk_sha256": hashlib.sha256(
                            ("risk-" + case_key).encode()
                        ).hexdigest(),
                    }
                )
            evidence.append(entry)
    return metrics, evidence


def test_op93_20_checkpoint_package_round_trip_is_descriptive(
    tmp_path: Path,
) -> None:
    config = subject.make_config("op_93", 20)
    metrics, evidence = _metric_and_evidence_rows(config)
    snapshot = subject.legacy.SourceSnapshot(
        campaign_root=tmp_path / "source",
        manifest={"campaign_signature": config.expected_campaign_signature},
        context=SimpleNamespace(disruption_window_days=42),
        seeds=config.expected_seeds,
        metric_rows=tuple(metrics),
        paired=pd.DataFrame(_paired_rows(config)),
        evidence_index=tuple(evidence),
        source_files={},
        completed_at_utc="2026-09-06T20:00:00+00:00",
    )
    with subject.patched_checkpoint_context(config):
        files = subject.legacy._files_for_package(snapshot)  # noqa: SLF001
        output, identical = subject.legacy._publish_new_or_identical(  # noqa: SLF001
            output_dir=tmp_path / "delivery", files=files
        )
    assert identical is False
    manifest = subject.validate_package(output, config=config)
    assert manifest["source_case_count"] == 740
    result = subject.legacy._decode_json(  # noqa: SLF001
        (output / config.result_name).read_bytes(), label=config.result_name
    )
    assert result["scope"]["operating_point_id"] == "op_93"
    assert result["scope"]["completed_simulation_count"] == 20
    assert result["interpretation"]["full_three_state_campaign_complete"] is False
    assert result["interpretation"]["sensitivity_available"] is False
    assert result["interpretation"]["lot_trace_available"] is False
    page = (output / config.html_name).read_text(encoding="utf-8")
    assert "20/30" in page
    assert "Médiane" in page
    assert "P10 – P90" in page
    assert "Effet positif x/20" in page
    assert "Incident exercé x/20" in page
    assert "top 3" not in page.casefold()
    assert "criticité" not in page.casefold()
    assert "http://" not in page
    assert "https://" not in page

    # Even a self-consistently re-signed package cannot mix another state.
    metrics_path = output / config.metrics_name
    metric_rows = subject.legacy._csv_rows(  # noqa: SLF001
        metrics_path.read_bytes(),
        expected_fields=subject.legacy.campaign_v4.METRIC_FIELDS,
        label=config.metrics_name,
    )
    metric_rows[0]["operating_point_id"] = "op_100"
    metrics_raw = subject.legacy._csv_bytes(  # noqa: SLF001
        metric_rows, subject.legacy.campaign_v4.METRIC_FIELDS
    )
    metrics_path.write_bytes(metrics_raw)
    package_manifest = subject.legacy._decode_json(  # noqa: SLF001
        (output / config.manifest_name).read_bytes(), label=config.manifest_name
    )
    package_manifest["outputs"][config.metrics_name].update(
        {
            "sha256": hashlib.sha256(metrics_raw).hexdigest(),
            "size_bytes": len(metrics_raw),
        }
    )
    package_manifest.pop("package_signature")
    package_manifest = subject.legacy._signed(  # noqa: SLF001
        package_manifest, "package_signature"
    )
    (output / config.manifest_name).write_bytes(
        subject.legacy._json_bytes(package_manifest)  # noqa: SLF001
    )
    with pytest.raises(subject.StateCheckpointError, match="identité"):
        subject.validate_package(output, config=config)


def test_30_of_30_is_complete_only_for_selected_state() -> None:
    config = subject.make_config("op_80", 30)
    supplier = {
        field: (
            "transport_delay"
            if field == "mechanism"
            else "SUP"
            if field == "supplier_id"
            else "lane"
            if field == "representative_lane_id"
            else "item:338929"
            if field == "item_id"
            else "M-1810"
            if field == "dst_node_id"
            else "268091"
            if field == "target_product_id"
            else 1
        )
        for field in subject.SUPPLIER_STAT_FIELDS
    }
    page = subject._render_html({"supplier_view": [supplier]}, config)  # noqa: SLF001
    subject._validate_html(page, config)  # noqa: SLF001
    assert "Les 30 répétitions prévues sont disponibles pour cet état" in page
    assert "campagne inter-états reste incomplète" in page


def test_build_refuses_protected_historical_destination(tmp_path: Path) -> None:
    config = subject.make_config("op_100", 10)
    with pytest.raises(subject.StateCheckpointError, match="historique 10/30"):
        subject.build_checkpoint(
            campaign_root=tmp_path / "campaign",
            output_dir=subject.PROTECTED_LEGACY_OUTPUT,
            config=config,
            scanner=lambda: [],
        )
    assert not (tmp_path / "campaign").exists()
