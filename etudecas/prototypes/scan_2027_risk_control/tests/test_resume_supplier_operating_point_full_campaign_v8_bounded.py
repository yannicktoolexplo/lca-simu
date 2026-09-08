from __future__ import annotations

import json
import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    resume_supplier_operating_point_full_campaign_v8_bounded as bounded,
)


def test_child_working_directory_is_repository_root() -> None:
    assert (bounded.REPO_ROOT / "etudecas").is_dir()
    assert bounded.REPO_ROOT.name == "lca-simu-pr40"


def test_child_environment_exposes_repository_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "existing-python-path")
    environment = bounded._child_environment()  # noqa: SLF001
    assert environment["PYTHONPATH"].split(os.pathsep) == [
        str(bounded.REPO_ROOT),
        "existing-python-path",
    ]


def _shards() -> list[Any]:
    return [
        bounded.implementation.Shard(
            shard_id=f"op_100__seed_block_{block:02d}",
            shard_index=block,
            operating_point_id="op_100",
            seed_block=block,
            seed_ids=(block,),
        )
        for block in range(1, 4)
    ]


def _install_fake_campaign(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    states: dict[str, str] | None = None,
    discovery_state: str = "complete",
    smoke_state: str = "complete",
) -> tuple[Path, Path, dict[str, str]]:
    campaign_root = tmp_path / "campaign"
    campaign_root.mkdir()
    runner = tmp_path / "runner.py"
    runner.write_text("# fake signed runner\n", encoding="utf-8")
    mutable_states = states or {
        shard.shard_id: "missing" for shard in _shards()
    }
    manifest = {"campaign_signature": bounded.EXPECTED_CAMPAIGN_SIGNATURE}

    monkeypatch.setattr(bounded, "_validate_frozen_orchestration", lambda: None)
    monkeypatch.setattr(
        bounded.launcher_v8,
        "patched_v8_context",
        lambda: nullcontext(),
    )
    monkeypatch.setattr(
        bounded.implementation,
        "load_campaign_plan",
        lambda _root, _runner: (manifest, _shards()),
    )
    monkeypatch.setattr(
        bounded.implementation,
        "_discovery_completion_state",
        lambda _root, manifest: (discovery_state, "discovery detail"),
    )
    monkeypatch.setattr(
        bounded.implementation,
        "_smoke_completion_state",
        lambda _root, manifest: (smoke_state, "smoke detail"),
    )

    def completion_state(
        _root: Path, *, campaign_signature: str, shard: Any
    ) -> tuple[str, str]:
        assert campaign_signature == bounded.EXPECTED_CAMPAIGN_SIGNATURE
        return mutable_states[shard.shard_id], "state detail"

    monkeypatch.setattr(
        bounded.implementation, "_completion_state", completion_state
    )
    monkeypatch.setattr(
        bounded,
        "_validate_existing_launch_contract",
        lambda *_args, **_kwargs: None,
    )

    def command_builder(
        *,
        runner: Path,
        campaign_root: Path,
        manifest: dict[str, Any],
        shard: Any,
        workers_per_shard: int,
        reuse_evidence_dirs: tuple[Path, ...],
    ) -> list[str]:
        assert manifest["campaign_signature"] == bounded.EXPECTED_CAMPAIGN_SIGNATURE
        assert workers_per_shard == 1
        command = [
            "python.exe",
            str(runner),
            "--mode",
            "run-shard",
            "--output-dir",
            str(campaign_root),
            "--operating-point-id",
            shard.operating_point_id,
            "--seed-block",
            str(shard.seed_block),
            "--workers",
            str(workers_per_shard),
        ]
        for source in reuse_evidence_dirs:
            command.extend(["--reuse-evidence-dir", str(source)])
        return command

    monkeypatch.setattr(
        bounded.implementation, "build_shard_command", command_builder
    )
    return campaign_root, runner, mutable_states


def test_validate_only_is_default_and_requires_no_execute_flag() -> None:
    args = bounded.parse_args(["--shard-id", "op_100__seed_block_03"])
    assert args.execute is False


def test_selection_is_exact_distinct_and_limited_to_two() -> None:
    shards = _shards()
    selected = bounded._select_shards(  # noqa: SLF001
        ["op_100__seed_block_03", "op_100__seed_block_01"], shards
    )
    assert [shard.shard_id for shard in selected] == [
        "op_100__seed_block_03",
        "op_100__seed_block_01",
    ]
    with pytest.raises(bounded.BoundedResumeError, match="un ou deux"):
        bounded._select_shards([], shards)  # noqa: SLF001
    with pytest.raises(bounded.BoundedResumeError, match="un ou deux"):
        bounded._select_shards(  # noqa: SLF001
            [shard.shard_id for shard in shards], shards
        )
    with pytest.raises(bounded.BoundedResumeError, match="deux fois"):
        bounded._select_shards(  # noqa: SLF001
            [shards[0].shard_id, shards[0].shard_id], shards
        )
    with pytest.raises(bounded.BoundedResumeError, match="absent du plan signé"):
        bounded._select_shards(["op_80__seed_block_06"], shards)  # noqa: SLF001


def test_validate_only_writes_nothing_and_exposes_exact_bounded_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign_root, runner, _states = _install_fake_campaign(monkeypatch, tmp_path)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    payload = bounded.inspect_bounded_resume(
        campaign_root=campaign_root,
        runner=runner,
        requested_ids=[
            "op_100__seed_block_01",
            "op_100__seed_block_02",
        ],
        scanner=lambda: [],
        task_scanner=lambda: {},
    )

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert payload["mode"] == "validate_only"
    assert payload["validation_is_read_only"] is True
    assert payload["selected_shard_ids"] == [
        "op_100__seed_block_01",
        "op_100__seed_block_02",
    ]
    assert payload["would_launch_shard_ids"] == payload["selected_shard_ids"]
    assert len(payload["exact_commands_if_executed"]) == 2
    assert all(
            command[command.index("--workers") + 1] == "1"
        for command in payload["exact_commands_if_executed"]
    )
    assert payload["maximum_engine_processes"] == 2
    assert payload["unselected_shards_never_scheduled"] is True
    assert payload["target_discovery_never_scheduled"] is True
    assert payload["smoke_never_scheduled"] is True
    assert payload["downstream_steps_never_scheduled"] is True


@pytest.mark.parametrize(
    ("discovery_state", "smoke_state", "message"),
    [
        ("resumable", "complete", "découverte V8 signée"),
        ("complete", "resumable", "preuve préalable V8"),
    ],
)
def test_prerequisites_are_never_created_implicitly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    discovery_state: str,
    smoke_state: str,
    message: str,
) -> None:
    campaign_root, runner, _states = _install_fake_campaign(
        monkeypatch,
        tmp_path,
        discovery_state=discovery_state,
        smoke_state=smoke_state,
    )
    with pytest.raises(bounded.BoundedResumeError, match=message):
        bounded.inspect_bounded_resume(
            campaign_root=campaign_root,
            runner=runner,
            requested_ids=["op_100__seed_block_01"],
            scanner=lambda: [],
            task_scanner=lambda: {},
        )


def test_any_fresh_active_shard_blocks_the_bounded_resume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    states = {
        "op_100__seed_block_01": "missing",
        "op_100__seed_block_02": "missing",
        "op_100__seed_block_03": "active",
    }
    campaign_root, runner, _states = _install_fake_campaign(
        monkeypatch, tmp_path, states=states
    )
    with pytest.raises(bounded.BoundedResumeError, match="block_03.*active"):
        bounded.inspect_bounded_resume(
            campaign_root=campaign_root,
            runner=runner,
            requested_ids=["op_100__seed_block_01"],
            scanner=lambda: [],
            task_scanner=lambda: {},
        )


def test_visible_runner_process_for_same_campaign_is_rejected(tmp_path: Path) -> None:
    campaign_root = tmp_path / "campaign"
    runner = tmp_path / "runner.py"
    process = bounded.ObservedProcess(
        pid=8123,
        name="python.exe",
        command_line=(
            "python.exe",
            str(runner),
            "--mode",
            "run-shard",
            "--output-dir",
            str(campaign_root),
            "--operating-point-id",
            "op_100",
            "--seed-block",
            "3",
            "--workers",
            "2",
        ),
    )
    with pytest.raises(bounded.BoundedResumeError, match="PID 8123"):
        bounded._assert_no_process_conflicts(  # noqa: SLF001
            [process],
            campaign_root=campaign_root,
            runner=runner,
            current_pid=99,
        )


def test_orphan_engine_writing_below_campaign_is_rejected(tmp_path: Path) -> None:
    campaign_root = tmp_path / "campaign"
    runner = tmp_path / "runner.py"
    orphan = bounded.ObservedProcess(
        pid=8124,
        name="python.exe",
        command_line=(
            "python.exe",
            str(tmp_path / "engine.py"),
            "--output-dir",
            str(campaign_root / "shards" / "block" / "_attempts" / "case"),
        ),
    )

    with pytest.raises(bounded.BoundedResumeError, match="PID 8124"):
        bounded._assert_no_process_conflicts(  # noqa: SLF001
            [orphan],
            campaign_root=campaign_root,
            runner=runner,
            current_pid=99,
        )


def test_enabled_or_running_v8_task_is_rejected() -> None:
    with pytest.raises(bounded.BoundedResumeError, match="n'est pas désactivée"):
        bounded._validate_task_states(  # noqa: SLF001
            {"LCA_RESILIENCE_SCAN_V8_V2_CAMPAIGN_20260906": "Ready"}
        )


def test_unexpected_campaign_signature_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign_root, runner, _states = _install_fake_campaign(monkeypatch, tmp_path)

    with pytest.raises(bounded.BoundedResumeError, match="signature de campagne"):
        bounded.inspect_bounded_resume(
            campaign_root=campaign_root,
            runner=runner,
            requested_ids=["op_100__seed_block_01"],
            expected_campaign_signature="0" * 64,
            scanner=lambda: [],
            task_scanner=lambda: {},
        )


def test_execute_runs_only_selected_shards_and_stops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign_root, runner, states = _install_fake_campaign(monkeypatch, tmp_path)
    commands: list[list[str]] = []

    class FinishedProcess:
        def __init__(self, command: list[str], pid: int) -> None:
            self.command = command
            self.pid = pid

        def poll(self) -> int:
            point = self.command[self.command.index("--operating-point-id") + 1]
            block = int(self.command[self.command.index("--seed-block") + 1])
            states[f"{point}__seed_block_{block:02d}"] = "complete"
            return 0

    def popen(command: list[str], **_kwargs: Any) -> FinishedProcess:
        commands.append(command)
        return FinishedProcess(command, 9000 + len(commands))

    payload = bounded.execute_bounded_resume(
        campaign_root=campaign_root,
        runner=runner,
        requested_ids=[
            "op_100__seed_block_01",
            "op_100__seed_block_02",
        ],
        scanner=lambda: [],
        task_scanner=lambda: {},
        popen_factory=popen,
        sleep=lambda _seconds: None,
        awake_factory=lambda: nullcontext({"status": "test", "acquired": True}),
        poll_seconds=0,
    )

    assert payload["status"] == "complete_selected_shards"
    assert payload["launched_shard_ids"] == [
        "op_100__seed_block_01",
        "op_100__seed_block_02",
    ]
    assert len(commands) == 2
    assert all(command[command.index("--workers") + 1] == "1" for command in commands)
    assert all(command[command.index("--seed-block") + 1] in {"1", "2"} for command in commands)
    assert states["op_100__seed_block_03"] == "missing"
    status_path = Path(payload["run_dir"]) / "status.json"
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == (
        "complete_selected_shards"
    )


def test_already_complete_selected_shard_is_not_relaunched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    states = {
        "op_100__seed_block_01": "complete",
        "op_100__seed_block_02": "missing",
        "op_100__seed_block_03": "missing",
    }
    campaign_root, runner, states = _install_fake_campaign(
        monkeypatch, tmp_path, states=states
    )
    commands: list[list[str]] = []

    class FinishedProcess:
        pid = 9444

        def __init__(self, command: list[str]) -> None:
            self.command = command

        def poll(self) -> int:
            states["op_100__seed_block_02"] = "complete"
            return 0

    def popen(command: list[str], **_kwargs: Any) -> FinishedProcess:
        commands.append(command)
        return FinishedProcess(command)

    payload = bounded.execute_bounded_resume(
        campaign_root=campaign_root,
        runner=runner,
        requested_ids=[
            "op_100__seed_block_01",
            "op_100__seed_block_02",
        ],
        scanner=lambda: [],
        task_scanner=lambda: {},
        popen_factory=popen,
        sleep=lambda _seconds: None,
        awake_factory=lambda: nullcontext({}),
        poll_seconds=0,
    )

    assert payload["status"] == "complete_selected_shards"
    assert len(commands) == 1
    assert commands[0][commands[0].index("--seed-block") + 1] == "2"


def test_current_v8_launcher_hash_matches_bounded_contract() -> None:
    path = Path(bounded.launcher_v8.__file__).resolve()
    assert bounded.implementation._sha256_file(path) == (  # noqa: SLF001
        bounded.EXPECTED_V8_LAUNCHER_SHA256
    )
