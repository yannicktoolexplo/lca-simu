from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    orchestrate_supplier_v8_bounded_tranche as subject,
)


def _request(
    tmp_path: Path,
    *,
    point: str = "op_100",
    count: int = 20,
    shards: tuple[str, ...] = (
        "op_100__seed_block_03",
        "op_100__seed_block_04",
    ),
) -> subject.TrancheRequest:
    campaign = tmp_path / "campaign"
    campaign.mkdir(exist_ok=True)
    runner = tmp_path / "runner.py"
    runner.write_text("# runner\n", encoding="utf-8")
    return subject.make_request(
        campaign_root=campaign,
        runner=runner,
        output_dir=tmp_path / "new_checkpoint",
        operating_point_id=point,
        simulation_count=count,
        shard_ids=shards,
    )


def _bounded_payload(
    request: subject.TrancheRequest, state: str = "resumable"
) -> dict[str, Any]:
    return {
        "status": "ready_for_explicit_execution",
        "mode": "validate_only",
        "selected_states": [
            {"shard_id": shard_id, "state": state}
            for shard_id in request.shard_ids
        ],
        "would_launch_shard_ids": list(request.shard_ids),
    }


def _checkpoint_states(
    request: subject.TrancheRequest, selected_state: str = "resumable"
) -> dict[str, str]:
    selected = set(request.shard_ids)
    return {
        shard_id: selected_state if shard_id in selected else "complete"
        for shard_id in request.config.target_shards
    }


def test_cli_is_read_only_unless_execute_is_explicit() -> None:
    common = [
        "--checkpoint-output-dir",
        "new",
        "--operating-point-id",
        "op_100",
        "--simulation-count",
        "20",
        "--shard-id",
        "op_100__seed_block_03",
        "--shard-id",
        "op_100__seed_block_04",
    ]
    assert subject._parser().parse_args(common).execute is False  # noqa: SLF001
    assert subject._parser().parse_args([*common, "--execute"]).execute is True  # noqa: SLF001


@pytest.mark.parametrize(
    ("point", "count", "shards"),
    [
        ("op_100", 10, ("op_100__seed_block_01", "op_100__seed_block_02")),
        ("op_93", 20, ("op_93__seed_block_03", "op_93__seed_block_04")),
        ("op_80", 30, ("op_80__seed_block_05", "op_80__seed_block_06")),
        ("op_80", 30, ("op_80__seed_block_06",)),
    ],
)
def test_request_accepts_only_the_suffix_that_closes_one_checkpoint(
    tmp_path: Path, point: str, count: int, shards: tuple[str, ...]
) -> None:
    request = _request(tmp_path, point=point, count=count, shards=shards)
    assert request.shard_ids == shards
    assert request.config.operating_point_id == point
    assert request.config.simulation_count == count


@pytest.mark.parametrize(
    "shards",
    [
        ("op_100__seed_block_02", "op_100__seed_block_03"),
        ("op_93__seed_block_03", "op_93__seed_block_04"),
        ("op_100__seed_block_04", "op_100__seed_block_03"),
        ("op_100__seed_block_03",) * 2,
    ],
)
def test_request_rejects_nonclosing_cross_state_reordered_or_duplicate_shards(
    tmp_path: Path, shards: tuple[str, ...]
) -> None:
    with pytest.raises(subject.TrancheOrchestrationError):
        _request(tmp_path, shards=shards)


def test_existing_or_campaign_internal_output_is_refused_before_any_work(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    campaign.mkdir()
    runner = tmp_path / "runner.py"
    runner.write_text("# runner\n", encoding="utf-8")
    existing = tmp_path / "existing"
    existing.mkdir()
    common = {
        "campaign_root": campaign,
        "runner": runner,
        "operating_point_id": "op_100",
        "simulation_count": 20,
        "shard_ids": (
            "op_100__seed_block_03",
            "op_100__seed_block_04",
        ),
    }
    with pytest.raises(subject.TrancheOrchestrationError, match="existe déjà"):
        subject.make_request(output_dir=existing, **common)
    with pytest.raises(subject.TrancheOrchestrationError, match="extérieur"):
        subject.make_request(output_dir=campaign / "checkpoint", **common)


def test_default_preflight_is_read_only_and_never_calls_execution_or_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = _request(tmp_path)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(
        subject,
        "_completion_states_for_checkpoint",
        lambda _request: _checkpoint_states(_request),
    )
    calls: list[str] = []

    def inspect(**_kwargs: Any) -> dict[str, Any]:
        calls.append("bounded_inspect")
        return _bounded_payload(request)

    def readiness(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("checkpoint_readiness")
        return {"status": "not_ready", "ready": False, "message_fr": "bloc 3"}

    payload = subject.inspect_tranche(
        request,
        scanner=lambda: [],
        task_scanner=lambda: {},
        bounded_inspector=inspect,
        checkpoint_readiness=readiness,
    )
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert calls == ["bounded_inspect", "checkpoint_readiness"]
    assert payload["status"] == "ready_for_explicit_execution"
    assert payload["filesystem_mutation_performed"] is False
    assert payload["engine_runs_started"] == 0
    assert payload["would_launch_shard_ids"] == list(request.shard_ids)
    assert payload["scheduled_tasks_modified"] is False
    assert payload["downstream_steps_started"] is False


def test_checkpoint_closure_rejects_an_incomplete_unselected_prerequisite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = _request(tmp_path)
    shards = [
        SimpleNamespace(shard_id=shard_id)
        for shard_id in request.config.target_shards
    ]
    states = {shard.shard_id: "complete" for shard in shards}
    states[request.config.target_shards[0]] = "missing"
    monkeypatch.setattr(
        subject.bounded.launcher_v8,
        "patched_v8_context",
        lambda: nullcontext(),
    )
    monkeypatch.setattr(
        subject.bounded.implementation,
        "load_campaign_plan",
        lambda _root, _runner: (
            {"campaign_signature": request.config.expected_campaign_signature},
            shards,
        ),
    )
    monkeypatch.setattr(
        subject.bounded.implementation,
        "_completion_state",
        lambda _root, campaign_signature, shard: (
            states[shard.shard_id],
            "test detail",
        ),
    )
    with pytest.raises(subject.TrancheOrchestrationError, match="antérieur"):
        subject._completion_states_for_checkpoint(request)  # noqa: SLF001


def test_execute_orders_tranche_then_readiness_build_and_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        subject,
        "_completion_states_for_checkpoint",
        lambda _request: _checkpoint_states(_request),
    )
    calls: list[str] = []
    readiness_calls = 0
    signature = "a" * 64

    def inspect(**_kwargs: Any) -> dict[str, Any]:
        calls.append("bounded_inspect")
        return _bounded_payload(request)

    def readiness(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal readiness_calls
        readiness_calls += 1
        calls.append(f"checkpoint_readiness_{readiness_calls}")
        if readiness_calls == 1:
            return {"status": "not_ready", "ready": False, "message_fr": "bloc 3"}
        return {"status": "ready_complete_selected_shards", "ready": True}

    def execute(**kwargs: Any) -> dict[str, Any]:
        calls.append("bounded_execute")
        assert tuple(kwargs["requested_ids"]) == request.shard_ids
        return {
            "status": "complete_selected_shards",
            "launched_shard_ids": list(request.shard_ids),
        }

    def build(**kwargs: Any) -> dict[str, Any]:
        calls.append("checkpoint_build")
        output = Path(kwargs["output_dir"])
        output.mkdir()
        entrypoint = output / request.config.html_name
        entrypoint.write_text("<!doctype html>", encoding="utf-8")
        return {
            "status": "created",
            "entrypoint": str(entrypoint),
            "package_signature": signature,
        }

    def validate(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("checkpoint_validate")
        return {"package_signature": signature}

    result = subject.execute_tranche(
        request,
        scanner=lambda: [],
        task_scanner=lambda: {},
        bounded_inspector=inspect,
        bounded_executor=execute,
        checkpoint_readiness=readiness,
        checkpoint_builder=build,
        checkpoint_validator=validate,
    )
    assert calls == [
        "bounded_inspect",
        "checkpoint_readiness_1",
        "bounded_execute",
        "checkpoint_readiness_2",
        "checkpoint_build",
        "checkpoint_validate",
    ]
    assert result["status"] == "checkpoint_created_and_validated"
    assert result["selected_shard_ids"] == list(request.shard_ids)
    assert result["package_signature"] == signature
    assert Path(result["entrypoint"]).is_file()
    assert result["scheduled_tasks_modified"] is False
    assert result["downstream_steps_started"] is False


def test_no_checkpoint_is_built_when_bounded_execution_does_not_finish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        subject,
        "_completion_states_for_checkpoint",
        lambda _request: _checkpoint_states(_request),
    )
    built = False

    def build(**_kwargs: Any) -> dict[str, Any]:
        nonlocal built
        built = True
        return {}

    with pytest.raises(subject.TrancheOrchestrationError, match="pas terminée"):
        subject.execute_tranche(
            request,
            scanner=lambda: [],
            task_scanner=lambda: {},
            bounded_inspector=lambda **_kwargs: _bounded_payload(request),
            bounded_executor=lambda **_kwargs: {"status": "failed"},
            checkpoint_readiness=lambda *_args, **_kwargs: {
                "status": "not_ready",
                "ready": False,
            },
            checkpoint_builder=build,
        )
    assert built is False
    assert not request.output_dir.exists()


def test_no_checkpoint_is_built_if_post_execution_evidence_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        subject,
        "_completion_states_for_checkpoint",
        lambda _request: _checkpoint_states(_request),
    )
    readiness_calls = 0

    def readiness(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal readiness_calls
        readiness_calls += 1
        return {
            "status": "not_ready",
            "ready": False,
            "message_fr": f"contrôle {readiness_calls}",
        }

    with pytest.raises(subject.TrancheOrchestrationError, match="reste incomplète"):
        subject.execute_tranche(
            request,
            scanner=lambda: [],
            task_scanner=lambda: {},
            bounded_inspector=lambda **_kwargs: _bounded_payload(request),
            bounded_executor=lambda **_kwargs: {
                "status": "complete_selected_shards"
            },
            checkpoint_readiness=readiness,
            checkpoint_builder=lambda **_kwargs: pytest.fail("unexpected build"),
        )
    assert readiness_calls == 2
    assert not request.output_dir.exists()


def test_complete_selected_shards_require_a_valid_checkpoint_before_publication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    request = _request(tmp_path)
    monkeypatch.setattr(
        subject,
        "_completion_states_for_checkpoint",
        lambda _request: _checkpoint_states(_request, "complete"),
    )
    with pytest.raises(subject.TrancheOrchestrationError, match="reste invalide"):
        subject.inspect_tranche(
            request,
            scanner=lambda: [],
            task_scanner=lambda: {},
            bounded_inspector=lambda **_kwargs: _bounded_payload(request, "complete"),
            checkpoint_readiness=lambda *_args, **_kwargs: {
                "status": "not_ready",
                "ready": False,
                "message_fr": "preuve stricte invalide",
            },
        )
