from __future__ import annotations

import json
from datetime import datetime, timezone

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v2_monitor as subject,
)


def _write_progress(root, shard_id: str, payload: dict[str, object]) -> None:
    directory = root / "shards" / shard_id
    directory.mkdir(parents=True)
    (directory / "progress.json").write_text(
        json.dumps({"shard_id": shard_id, **payload}), encoding="utf-8"
    )


def test_aggregate_progress_is_read_only_and_projects_eta(tmp_path) -> None:
    common = {
        "campaign_signature": "same-campaign",
        "planned_case_count": 185,
        "failed_case_count": 0,
        "running_case_keys": [],
        "updated_at_utc": "2026-09-04T14:00:00+00:00",
        "started_at_utc": "2026-09-04T12:00:00+00:00",
        "mean_completed_case_seconds": 240.0,
    }
    _write_progress(
        tmp_path,
        "op_100__seed_block_1",
        {**common, "status": "complete", "completed_case_count": 185, "eta_seconds": 0},
    )
    _write_progress(
        tmp_path,
        "op_93__seed_block_1",
        {
            **common,
            "status": "running",
            "completed_case_count": 100,
            "running_case_keys": ["a", "b"],
            "eta_seconds": 10_200,
        },
    )
    before = sorted(path.read_bytes() for path in tmp_path.rglob("progress.json"))

    summary = subject.aggregate_progress(
        tmp_path,
        expected_shards=2,
        parallel_workers=4,
        now=datetime(2026, 9, 4, 14, 5, tzinfo=timezone.utc),
    )

    assert summary["planned_case_count"] == 370
    assert summary["completed_case_count"] == 285
    assert summary["remaining_case_count"] == 85
    assert summary["running_case_count"] == 2
    assert summary["projected_campaign_eta_seconds"] == 5_100
    assert summary["runner_reported_wave_eta_seconds"] == 10_200
    assert not summary["complete"]
    assert before == sorted(path.read_bytes() for path in tmp_path.rglob("progress.json"))


def test_aliases_stale_detection_and_mixed_signatures(tmp_path) -> None:
    _write_progress(
        tmp_path,
        "one",
        {
            "campaign_signature": "A",
            "status": "running",
            "planned": 10,
            "completed": 2,
            "failed": 0,
            "running": 1,
            "updated_at": "2026-09-04T12:00:00Z",
            "elapsed": 100,
            "ETA": 400,
        },
    )
    _write_progress(
        tmp_path,
        "two",
        {
            "campaign_signature": "B",
            "status": "planned",
            "planned": 10,
            "completed": 0,
            "failed": 0,
        },
    )

    summary = subject.aggregate_progress(
        tmp_path,
        expected_shards=2,
        now=datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc),
        stale_after_seconds=60,
    )

    assert summary["mixed_campaign_signatures"]
    assert summary["stale_running_shard_count"] == 1
    assert summary["running_case_count"] == 1
    assert "plusieurs signatures" in subject.render_text(summary)


def test_complete_requires_every_expected_shard_and_no_failure(tmp_path) -> None:
    for shard in ("one", "two"):
        _write_progress(
            tmp_path,
            shard,
            {
                "campaign_signature": "A",
                "status": "complete",
                "planned_case_count": 185,
                "completed_case_count": 185,
                "failed_case_count": 0,
                "running_case_keys": [],
            },
        )

    summary = subject.aggregate_progress(tmp_path, expected_shards=2)

    assert summary["complete"]
    assert summary["completion_ratio"] == 1.0


def test_invalid_progress_is_reported_without_stopping_other_shards(tmp_path) -> None:
    _write_progress(
        tmp_path,
        "good",
        {
            "status": "planned",
            "planned_case_count": 185,
            "completed_case_count": 0,
            "failed_case_count": 0,
        },
    )
    bad = tmp_path / "shards" / "bad"
    bad.mkdir(parents=True)
    (bad / "progress.json").write_text("{not-json", encoding="utf-8")

    summary = subject.aggregate_progress(tmp_path, expected_shards=2)

    assert summary["discovered_shard_count"] == 1
    assert summary["read_error_count"] == 1
    assert not summary["complete"]
