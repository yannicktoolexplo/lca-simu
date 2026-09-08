from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v8_resilient as resilient,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supervise_supplier_operating_point_full_campaign_v8_v2 as supervisor,
)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class SnapshotScanner:
    def __init__(self, snapshots: list[list[supervisor.ObservedProcess]]) -> None:
        self.snapshots = snapshots
        self.calls = 0

    def __call__(self) -> list[supervisor.ObservedProcess]:
        index = min(self.calls, len(self.snapshots) - 1)
        self.calls += 1
        return self.snapshots[index]


def _process(pid: int, command: list[str]) -> supervisor.ObservedProcess:
    return supervisor.ObservedProcess(
        pid=pid,
        create_time=float(pid),
        executable=command[0],
        command_line=tuple(command),
    )


def _shard_process(
    pid: int,
    *,
    runner: Path,
    campaign_root: Path,
    shard: int,
) -> supervisor.ObservedProcess:
    operating_point = "op_100" if shard <= 6 else "op_93"
    seed_block = shard if shard <= 6 else shard - 6
    return _process(
        pid,
        [
            "python.exe",
            str(runner),
            "--mode",
            "run-shard",
            "--output-dir",
            str(campaign_root),
            "--operating-point-id",
            operating_point,
            "--seed-block",
            str(seed_block),
            "--workers",
            "2",
        ],
    )


def test_atomic_writer_retries_windows_collision_with_unique_temp(
    tmp_path: Path,
) -> None:
    target = tmp_path / "progress.json"
    target.write_text('{"old": true}', encoding="utf-8")
    replace_sources: list[Path] = []
    sleeps: list[float] = []

    def colliding_replace(
        source: os.PathLike[str], destination: os.PathLike[str]
    ) -> None:
        replace_sources.append(Path(source))
        if len(replace_sources) < 3:
            error = PermissionError("simulated Windows sharing violation")
            error.winerror = 32
            raise error
        os.replace(source, destination)

    resilient.resilient_write_json_atomic(
        target,
        {"status": "running"},
        replace=colliding_replace,
        sleep=sleeps.append,
        token_factory=lambda: "collision-test-token",
        platform_name="nt",
        attempts=4,
        base_delay_seconds=0.05,
        max_delay_seconds=1.0,
    )

    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "running"}
    assert sleeps == [0.05, 0.1]
    assert len(set(replace_sources)) == 1
    assert replace_sources[0].name.endswith("collision-test-token")
    assert not replace_sources[0].exists()


def test_atomic_writer_cleans_unique_temp_after_persistent_collision(
    tmp_path: Path,
) -> None:
    target = tmp_path / "progress.json"
    replace_sources: list[Path] = []

    def always_collides(
        source: os.PathLike[str], _destination: os.PathLike[str]
    ) -> None:
        replace_sources.append(Path(source))
        error = PermissionError("persistent collision")
        error.winerror = 32
        raise error

    with pytest.raises(PermissionError, match="persistent collision"):
        resilient.resilient_write_json_atomic(
            target,
            {"status": "running"},
            replace=always_collides,
            sleep=lambda _seconds: None,
            token_factory=lambda: "persistent-test-token",
            platform_name="nt",
            attempts=3,
        )

    assert len(replace_sources) == 3
    assert not replace_sources[0].exists()
    assert not target.exists()


def test_resilient_patch_is_installed_after_validation_and_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation = resilient.implementation_v4
    original_writer = implementation._write_json_atomic  # noqa: SLF001
    original_detached = implementation._detached_command  # noqa: SLF001
    events: list[str] = []

    @contextmanager
    def validated_context():
        assert implementation._write_json_atomic is original_writer  # noqa: SLF001
        events.append("validated")
        yield

    monkeypatch.setattr(resilient.launcher_v8, "patched_v8_context", validated_context)

    with resilient.patched_resilient_v8_context():
        assert events == ["validated"]
        assert implementation._write_json_atomic is resilient._write_json_atomic  # noqa: SLF001
        assert implementation._detached_command is resilient._resilient_detached_command  # noqa: SLF001

    assert implementation._write_json_atomic is original_writer  # noqa: SLF001
    assert implementation._detached_command is original_detached  # noqa: SLF001


def test_wait_tracks_only_exact_shards_and_does_not_duplicate_launcher(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "runner.py"
    campaign = tmp_path / "campaign"
    exact_one = _shard_process(101, runner=runner, campaign_root=campaign, shard=1)
    exact_two = _shard_process(102, runner=runner, campaign_root=campaign, shard=2)
    wrong_root = _shard_process(
        999,
        runner=runner,
        campaign_root=tmp_path / "another-campaign",
        shard=3,
    )
    scanner = SnapshotScanner(
        [[exact_one, wrong_root], [exact_two, wrong_root], [wrong_root], [wrong_root]]
    )
    inspections: list[tuple[str, ...]] = []
    clock = FakeClock()

    def inspect(shard_ids: tuple[str, ...]) -> supervisor.ProgressGate:
        inspections.append(shard_ids)
        return supervisor.ProgressGate(0.0, (), ())

    result = supervisor.wait_until_safe_to_resume(
        runner=runner,
        campaign_root=campaign,
        scanner=scanner,
        progress_inspector=inspect,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        process_poll_seconds=10.0,
        max_wait_seconds=100.0,
    )

    assert result.observed_shard_ids == (
        "op_100__seed_block_01",
        "op_100__seed_block_02",
    )
    assert result.process_poll_count == 4
    assert clock.sleeps == [10.0, 10.0]
    assert inspections == [result.observed_shard_ids]


def test_wait_refuses_existing_launcher_before_progress_inspection(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    launcher = _process(
        777,
        [
            "python.exe",
            "-m",
            resilient.MODULE_NAME,
            "--campaign-root",
            str(campaign),
        ],
    )
    scanner = SnapshotScanner([[launcher]])

    def must_not_inspect(_shard_ids: tuple[str, ...]) -> supervisor.ProgressGate:
        raise AssertionError("progress must not be read while a launcher exists")

    with pytest.raises(supervisor.RecoverySupervisorError, match="PID 777"):
        supervisor.wait_until_safe_to_resume(
            runner=tmp_path / "runner.py",
            campaign_root=campaign,
            scanner=scanner,
            progress_inspector=must_not_inspect,
            process_poll_seconds=10.0,
            max_wait_seconds=100.0,
        )


@pytest.mark.parametrize(
    "mode_and_options",
    [
        [
            "--mode",
            "run-shard",
            "--operating-point-id",
            "op_100",
            "--seed-block",
            "1",
            "--workers",
            "99",
        ],
        ["--mode", "discover-targets", "--workers", "2"],
        [
            "--mode",
            "run-shard",
            "--operating-point-id",
            "op_100",
            "--seed-block",
            "1",
            "--workers",
            "2",
            "--workers",
            "1",
        ],
    ],
)
def test_wait_fails_closed_for_ambiguous_campaign_runner_process(
    tmp_path: Path,
    mode_and_options: list[str],
) -> None:
    runner = tmp_path / "runner.py"
    campaign = tmp_path / "campaign"
    ambiguous = _process(
        888,
        [
            "python.exe",
            str(runner),
            *mode_and_options,
            "--output-dir",
            str(campaign),
        ],
    )
    scanner = SnapshotScanner([[ambiguous]])

    def must_not_inspect(_shard_ids: tuple[str, ...]) -> supervisor.ProgressGate:
        raise AssertionError("ambiguous runner must fail before progress inspection")

    with pytest.raises(supervisor.RecoverySupervisorError, match="PID 888"):
        supervisor.wait_until_safe_to_resume(
            runner=runner,
            campaign_root=campaign,
            scanner=scanner,
            progress_inspector=must_not_inspect,
            process_poll_seconds=10.0,
            max_wait_seconds=100.0,
        )


def test_dead_child_with_fresh_running_progress_waits_until_stale() -> None:
    scanner = SnapshotScanner([[], [], [], [], []])
    clock = FakeClock()
    inspections = 0

    def inspect(_shard_ids: tuple[str, ...]) -> supervisor.ProgressGate:
        nonlocal inspections
        inspections += 1
        return supervisor.ProgressGate(
            65.0,
            ("op_100__seed_block_01",),
            (("op_100__seed_block_01", "running"),),
        )

    result = supervisor.wait_until_safe_to_resume(
        runner=Path("runner.py"),
        campaign_root=Path("campaign"),
        scanner=scanner,
        progress_inspector=inspect,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        process_poll_seconds=30.0,
        max_wait_seconds=100.0,
    )

    assert clock.sleeps == [30.0, 30.0, 5.0]
    assert result.stale_wait_seconds == 65.0
    assert result.process_poll_count == 5
    assert inspections == 1


@pytest.mark.parametrize("terminal_status", ["complete", "failed"])
def test_dead_child_with_terminal_progress_resumes_immediately(
    terminal_status: str,
) -> None:
    scanner = SnapshotScanner([[], []])
    clock = FakeClock()

    result = supervisor.wait_until_safe_to_resume(
        runner=Path("runner.py"),
        campaign_root=Path("campaign"),
        scanner=scanner,
        progress_inspector=lambda _shard_ids: supervisor.ProgressGate(
            0.0,
            (),
            (("op_100__seed_block_01", terminal_status),),
        ),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        process_poll_seconds=30.0,
        max_wait_seconds=100.0,
    )

    assert clock.sleeps == []
    assert result.stale_wait_seconds == 0.0
    assert result.process_poll_count == 2


def test_progress_inspection_computes_fresh_running_delay_once(
    tmp_path: Path,
) -> None:
    progress_path = tmp_path / "shards" / "op_100__seed_block_01" / "progress.json"
    progress_path.parent.mkdir(parents=True)
    progress_path.write_text(
        json.dumps(
            {
                "shard_id": "op_100__seed_block_01",
                "status": "running",
                "updated_at_utc": "2026-09-06T11:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    gate = supervisor.inspect_shard_progress_once(
        tmp_path,
        (),
        now_utc=datetime(2026, 9, 6, 11, 10, tzinfo=timezone.utc),
        active_seconds=1_800.0,
        stale_margin_seconds=2.0,
    )

    assert gate.delay_seconds == 1_202.0
    assert gate.running_progress == ("op_100__seed_block_01",)
    assert gate.statuses == (("op_100__seed_block_01", "running"),)


def test_supervise_keeps_awake_and_launches_once_with_pythonpath_and_log(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    campaign = tmp_path / "campaign"
    runner = repo / "etudecas" / "runner.py"
    supervision_dir = tmp_path / "new-supervision"
    runner.parent.mkdir(parents=True)
    runner.write_text("# signed-runner fixture\n", encoding="utf-8")
    campaign.mkdir()
    clock = FakeClock()
    scanner = SnapshotScanner([[], []])
    awake_events: list[str] = []

    class FakeAwake:
        def __init__(self) -> None:
            self.active = False

        def __enter__(self):
            self.active = True
            awake_events.append("entered")
            return self

        def __exit__(self, *_args):
            self.active = False
            awake_events.append("released")

        def payload(self):
            return {
                "requested": True,
                "active": self.active,
                "method": "test",
            }

    keeper = FakeAwake()
    popen_calls: list[dict[str, object]] = []

    class FakeLauncher:
        pid = 4242

        def wait(self) -> int:
            assert keeper.active
            awake_events.append("launcher_waited")
            return 0

    def fake_popen(command, **kwargs):
        assert keeper.active
        popen_calls.append(
            {
                "command": command,
                "cwd": kwargs["cwd"],
                "env": kwargs["env"],
                "stdout_name": Path(kwargs["stdout"].name),
                "stderr": kwargs["stderr"],
            }
        )
        return FakeLauncher()

    result = supervisor.supervise(
        supervisor.SupervisorConfig(
            repo=repo,
            campaign_root=campaign,
            runner=runner,
            python=supervisor.DEFAULT_PYTHON,
            supervision_dir=supervision_dir,
            process_poll_seconds=10.0,
            max_wait_hours=1.0,
            expected_runner_sha256=None,
        ),
        scanner=scanner,
        popen_factory=fake_popen,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        keep_awake_factory=lambda: keeper,
    )

    assert result == 0
    assert awake_events == ["entered", "launcher_waited", "released"]
    assert len(popen_calls) == 1
    call = popen_calls[0]
    assert call["command"][0:3] == [
        str(supervisor.DEFAULT_PYTHON),
        "-m",
        resilient.MODULE_NAME,
    ]
    assert call["cwd"] == repo.resolve()
    assert call["env"]["PYTHONPATH"] == str(repo.resolve())
    assert call["env"]["PYTHONUTF8"] == "1"
    assert call["env"]["PYTHONIOENCODING"] == "utf-8"
    assert (
        call["stdout_name"]
        == (supervision_dir / "resumed_launcher_stdout_stderr.log").resolve()
    )
    assert call["stderr"] == supervisor.subprocess.STDOUT
    assert "RESUME" in (
        supervision_dir / "resumed_launcher_stdout_stderr.log"
    ).read_text(encoding="utf-8")
    status = json.loads((supervision_dir / "status.json").read_text("utf-8"))
    assert status["status"] == "complete"
    assert status["business_status"] == "complete"
    assert status["keep_awake"]["active"] is False


def test_business_text_and_sources_contain_no_mojibake() -> None:
    bad_markers = (
        chr(0x00C3),
        chr(0x00C2),
        chr(0x00E2) + chr(0x20AC),
    )
    paths = (
        Path(supervisor.__file__),
        Path(resilient.__file__),
        Path(__file__),
    )
    source_and_output = "\n".join(
        [path.read_text(encoding="utf-8") for path in paths]
        + list(supervisor.BUSINESS_MESSAGE_FR.values())
    )

    assert not any(marker in source_and_output for marker in bad_markers)
