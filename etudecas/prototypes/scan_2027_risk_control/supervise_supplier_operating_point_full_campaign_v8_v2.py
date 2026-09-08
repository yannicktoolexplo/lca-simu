#!/usr/bin/env python3
"""Wait for orphan V8-v2 shards, then resume through the resilient launcher.

This additive supervisor never polls campaign JSON.  While shard processes are
alive it consults the Windows process table only.  Once no exact shard process
remains, it reads each shard progress file at most once to respect the frozen
launcher's 30-minute freshness guard, then starts exactly one validated V8
launcher with an explicit PYTHONPATH and a persistent stdout/stderr log.

The module is inert when imported.  It does not create or register a scheduled
task; execution must be explicitly authorized by the operator.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import psutil

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v8 as launcher_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v8_resilient as resilient_launcher,
)


SCHEMA_VERSION = "etudecas.supplier_campaign_v8_v2.recovery_supervisor.v1"
BUSINESS_STATUS = {
    "waiting": "waiting_orphans",
    "waiting_exact_run_shards": "waiting_orphans",
    "waiting_fresh_orphan_progress": "waiting_orphans",
    "launcher_running": "running_launcher",
    "complete": "complete",
    "launcher_failed": "failed",
    "failed_closed": "failed",
}
BUSINESS_MESSAGE_FR = {
    "waiting_orphans": (
        "Attente de la fin des calculs orphelins ou de l'expiration de leur "
        "dernier signal d'activité."
    ),
    "running_launcher": (
        "La reprise V8 est lancée et le superviseur reste actif jusqu'à sa fin."
    ),
    "complete": "La reprise V8 s'est terminée correctement.",
    "failed": "La reprise V8 ou sa supervision s'est arrêtée en erreur.",
}
REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_CAMPAIGN_ROOT = ARTIFACT_ROOT / (
    "supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
)
DEFAULT_SUPERVISION_DIR = ARTIFACT_ROOT / (
    "supplier_operating_point_full_campaign_v8_v2_recovery_supervision_20260906_v1"
)
DEFAULT_RUNNER = REPO_ROOT / (
    "etudecas/prototypes/scan_2027_risk_control/"
    "supplier_operating_point_full_campaign_v8.py"
)
DEFAULT_PYTHON = Path(sys.executable).resolve()
EXPECTED_RUNNER_SHA256 = (
    "3dd8835992c9d97093fc6eaa0ba52dabfd0574fb775bbf8c62c2a26c9950bd39"
)
DEFAULT_PROCESS_POLL_SECONDS = 30.0
DEFAULT_MAX_WAIT_HOURS = 240.0
DEFAULT_STALE_MARGIN_SECONDS = 2.0
FROZEN_ACTIVE_PROGRESS_SECONDS = float(
    launcher_v8.implementation_v4.DEFAULT_ACTIVE_PROGRESS_SECONDS
)
ORIGINAL_LAUNCHER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v8"
)
LAUNCHER_MODULES = frozenset({ORIGINAL_LAUNCHER_MODULE, resilient_launcher.MODULE_NAME})
LAUNCHER_PATHS = frozenset(
    {
        str(Path(launcher_v8.__file__).resolve()),
        str(Path(resilient_launcher.__file__).resolve()),
    }
)


class RecoverySupervisorError(RuntimeError):
    """The recovery supervisor cannot prove a safe single-launch hand-off."""


class ProcessScanner(Protocol):
    def __call__(self) -> Sequence["ObservedProcess"]: ...


class LauncherProcess(Protocol):
    pid: int

    def wait(self) -> int: ...


@dataclass(frozen=True)
class ObservedProcess:
    pid: int
    create_time: float
    executable: str
    command_line: tuple[str, ...]


@dataclass(frozen=True)
class ExactShardProcess:
    process: ObservedProcess
    shard_id: str


@dataclass(frozen=True)
class ProgressGate:
    delay_seconds: float
    running_progress: tuple[str, ...]
    statuses: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class WaitResult:
    observed_shard_ids: tuple[str, ...]
    process_poll_count: int
    stale_wait_seconds: float


@dataclass(frozen=True)
class SupervisorConfig:
    repo: Path = REPO_ROOT
    campaign_root: Path = DEFAULT_CAMPAIGN_ROOT
    runner: Path = DEFAULT_RUNNER
    python: Path = DEFAULT_PYTHON
    supervision_dir: Path = DEFAULT_SUPERVISION_DIR
    process_poll_seconds: float = DEFAULT_PROCESS_POLL_SECONDS
    max_wait_hours: float = DEFAULT_MAX_WAIT_HOURS
    parallel_shards: int = 2
    workers_per_shard: int = 2
    launcher_poll_seconds: float = 5.0
    stale_margin_seconds: float = DEFAULT_STALE_MARGIN_SECONDS
    expected_runner_sha256: str | None = EXPECTED_RUNNER_SHA256

    def resolved(self) -> "SupervisorConfig":
        return SupervisorConfig(
            repo=self.repo.resolve(),
            campaign_root=self.campaign_root.resolve(),
            runner=self.runner.resolve(),
            python=self.python.resolve(),
            supervision_dir=self.supervision_dir.resolve(),
            process_poll_seconds=self.process_poll_seconds,
            max_wait_hours=self.max_wait_hours,
            parallel_shards=self.parallel_shards,
            workers_per_shard=self.workers_per_shard,
            launcher_poll_seconds=self.launcher_poll_seconds,
            stale_margin_seconds=self.stale_margin_seconds,
            expected_runner_sha256=self.expected_runner_sha256,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_path(value: str | Path) -> str:
    return os.path.normcase(str(Path(value).resolve(strict=False)))


def _single_option(command: Sequence[str], flag: str) -> str | None:
    indexes = [index for index, value in enumerate(command) if value == flag]
    if len(indexes) != 1 or indexes[0] + 1 >= len(command):
        return None
    return str(command[indexes[0] + 1])


def identify_exact_run_shard(
    process: ObservedProcess,
    *,
    runner: Path,
    campaign_root: Path,
) -> ExactShardProcess | None:
    """Match only the signed runner's exact ``run-shard`` command and root."""

    command = process.command_line
    if len(command) < 2 or _normalized_path(command[1]) != _normalized_path(runner):
        return None
    if _single_option(command, "--mode") != "run-shard":
        return None
    output_dir = _single_option(command, "--output-dir")
    if output_dir is None or _normalized_path(output_dir) != _normalized_path(
        campaign_root
    ):
        return None
    operating_point = _single_option(command, "--operating-point-id")
    seed_block_text = _single_option(command, "--seed-block")
    workers_text = _single_option(command, "--workers")
    try:
        seed_block = int(seed_block_text or "")
        workers = int(workers_text or "")
    except ValueError:
        return None
    if operating_point not in {"op_100", "op_93", "op_80"}:
        return None
    if seed_block not in range(1, 7) or workers not in {1, 2}:
        return None
    return ExactShardProcess(
        process=process,
        shard_id=f"{operating_point}__seed_block_{seed_block:02d}",
    )


def is_relevant_campaign_runner_process(
    process: ObservedProcess,
    *,
    runner: Path,
    campaign_root: Path,
) -> bool:
    """Detect any process that visibly targets this campaign with this runner."""

    command = process.command_line
    if len(command) < 2 or _normalized_path(command[1]) != _normalized_path(runner):
        return False
    output_values = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--output-dir"
    ]
    return any(
        _normalized_path(value) == _normalized_path(campaign_root)
        for value in output_values
    )


def is_exact_launcher_process(
    process: ObservedProcess,
    *,
    campaign_root: Path,
) -> bool:
    """Identify an existing original or resilient V8 launcher for this root."""

    command = process.command_line
    if len(command) < 2:
        return False
    module_match = (
        len(command) >= 3 and command[1] == "-m" and command[2] in LAUNCHER_MODULES
    )
    script_match = _normalized_path(command[1]) in {
        _normalized_path(path) for path in LAUNCHER_PATHS
    }
    if not module_match and not script_match:
        return False
    root = _single_option(command, "--campaign-root")
    return root is not None and _normalized_path(root) == _normalized_path(
        campaign_root
    )


def scan_processes() -> list[ObservedProcess]:
    """Take one process-table snapshot; no campaign file is read here."""

    observed: list[ObservedProcess] = []
    inaccessible_python: list[int] = []
    for process in psutil.process_iter(
        attrs=("pid", "create_time", "exe", "name", "cmdline")
    ):
        try:
            info = process.info
            name = str(info.get("name") or "")
            command = info.get("cmdline")
            if command is None:
                if name.casefold().startswith("python"):
                    inaccessible_python.append(int(info["pid"]))
                continue
            observed.append(
                ObservedProcess(
                    pid=int(info["pid"]),
                    create_time=float(info.get("create_time") or 0.0),
                    executable=str(info.get("exe") or ""),
                    command_line=tuple(str(value) for value in command),
                )
            )
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            try:
                if process.name().casefold().startswith("python"):
                    inaccessible_python.append(process.pid)
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
    if inaccessible_python:
        raise RecoverySupervisorError(
            "Impossible de vérifier la commande des processus Python : "
            + ", ".join(str(pid) for pid in sorted(set(inaccessible_python)))
        )
    return observed


def _read_bytes_shared_delete(path: Path) -> bytes:
    """Read once while explicitly allowing an atomic Windows replacement."""

    if os.name != "nt":  # pragma: no cover - official recovery is Windows
        return path.read_bytes()
    import msvcrt

    generic_read = 0x80000000
    file_share_read_write_delete = 0x00000007
    open_existing = 3
    file_attribute_normal = 0x00000080
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        generic_read,
        file_share_read_write_delete,
        None,
        open_existing,
        file_attribute_normal,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError()
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY)
    except Exception:
        kernel32.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb", closefd=True) as stream:
        return stream.read()


def _read_json_once(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read_bytes_shared_delete(path).decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoverySupervisorError(f"Progression illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise RecoverySupervisorError(f"Progression non objet : {path}")
    return payload


def _parse_utc(value: Any, *, path: Path) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoverySupervisorError(
            f"Horodatage de progression invalide : {path}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def inspect_shard_progress_once(
    campaign_root: Path,
    observed_shard_ids: Sequence[str],
    *,
    now_utc: datetime | None = None,
    active_seconds: float = FROZEN_ACTIVE_PROGRESS_SECONDS,
    stale_margin_seconds: float = DEFAULT_STALE_MARGIN_SECONDS,
) -> ProgressGate:
    """Read each candidate progress once and compute the frozen stale delay."""

    root = campaign_root.resolve()
    paths = {
        root / "shards" / shard_id / "progress.json" for shard_id in observed_shard_ids
    }
    shards_root = root / "shards"
    if shards_root.is_dir():
        paths.update(shards_root.glob("*/progress.json"))
    current = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    running: list[str] = []
    statuses: list[tuple[str, str]] = []
    maximum_delay = 0.0
    for path in sorted(paths):
        if not path.is_file():
            continue
        payload = _read_json_once(path)
        status = str(payload.get("status") or "").casefold()
        shard_id = str(payload.get("shard_id") or path.parent.name)
        statuses.append((shard_id, status))
        if status != "running":
            continue
        updated = _parse_utc(payload.get("updated_at_utc"), path=path)
        age = max(0.0, (current - updated).total_seconds())
        delay = max(0.0, active_seconds - age + stale_margin_seconds)
        maximum_delay = max(maximum_delay, delay)
        running.append(shard_id)
    return ProgressGate(
        delay_seconds=maximum_delay,
        running_progress=tuple(sorted(running)),
        statuses=tuple(sorted(statuses)),
    )


def _exact_processes(
    records: Sequence[ObservedProcess],
    *,
    runner: Path,
    campaign_root: Path,
) -> tuple[
    list[ExactShardProcess],
    list[ObservedProcess],
    list[ObservedProcess],
]:
    shards = [
        match
        for process in records
        if (
            match := identify_exact_run_shard(
                process,
                runner=runner,
                campaign_root=campaign_root,
            )
        )
        is not None
    ]
    launchers = [
        process
        for process in records
        if is_exact_launcher_process(process, campaign_root=campaign_root)
    ]
    exact_pids = {row.process.pid for row in shards}
    ambiguous = [
        process
        for process in records
        if process.pid not in exact_pids
        and is_relevant_campaign_runner_process(
            process,
            runner=runner,
            campaign_root=campaign_root,
        )
    ]
    return shards, launchers, ambiguous


def wait_until_safe_to_resume(
    *,
    runner: Path,
    campaign_root: Path,
    scanner: ProcessScanner,
    progress_inspector: Callable[[Sequence[str]], ProgressGate],
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    process_poll_seconds: float = DEFAULT_PROCESS_POLL_SECONDS,
    max_wait_seconds: float = DEFAULT_MAX_WAIT_HOURS * 3600.0,
    on_state: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> WaitResult:
    """Wait for exact shards and any fresh orphan heartbeat without duplicates."""

    if process_poll_seconds <= 0 or max_wait_seconds <= 0:
        raise ValueError("wait durations must be strictly positive")
    deadline = monotonic() + max_wait_seconds
    observed_shard_ids: set[str] = set()
    process_poll_count = 0
    stale_wait_total = 0.0

    def snapshot() -> tuple[list[ExactShardProcess], list[ObservedProcess]]:
        nonlocal process_poll_count
        records = scanner()
        process_poll_count += 1
        shards, launchers, ambiguous = _exact_processes(
            records,
            runner=runner,
            campaign_root=campaign_root,
        )
        if launchers:
            pids = ", ".join(str(row.pid) for row in launchers)
            raise RecoverySupervisorError(
                f"Un launcher V8 existe déjà pour cette campagne : PID {pids}"
            )
        if ambiguous:
            pids = ", ".join(str(row.pid) for row in ambiguous)
            raise RecoverySupervisorError(
                "Processus du runner visant cette campagne mais hors contrat "
                f"run-shard exact : PID {pids}"
            )
        return shards, launchers

    while True:
        shards, _launchers = snapshot()
        if shards:
            observed_shard_ids.update(row.shard_id for row in shards)
            if on_state is not None:
                on_state(
                    "waiting_exact_run_shards",
                    {
                        "pids": [row.process.pid for row in shards],
                        "shard_ids": sorted(row.shard_id for row in shards),
                    },
                )
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise RecoverySupervisorError(
                    "Délai dépassé en attendant les processus run-shard exacts"
                )
            sleep(min(process_poll_seconds, remaining))
            continue

        gate = progress_inspector(tuple(sorted(observed_shard_ids)))
        delay = max(0.0, gate.delay_seconds)
        if delay > 0:
            if on_state is not None:
                on_state(
                    "waiting_fresh_orphan_progress",
                    {
                        "delay_seconds": delay,
                        "running_progress": list(gate.running_progress),
                        "statuses": [list(row) for row in gate.statuses],
                    },
                )
            stale_wait_started = monotonic()
            stale_deadline = monotonic() + delay
            while monotonic() < stale_deadline:
                remaining_global = deadline - monotonic()
                if remaining_global <= 0:
                    raise RecoverySupervisorError(
                        "Délai dépassé avant expiration de la progression orpheline"
                    )
                sleep(
                    min(
                        process_poll_seconds,
                        stale_deadline - monotonic(),
                        remaining_global,
                    )
                )
                shards, _launchers = snapshot()
                if shards:
                    observed_shard_ids.update(row.shard_id for row in shards)
                    break
            stale_wait_total += max(0.0, monotonic() - stale_wait_started)
            if shards:
                continue

        # One final process-only snapshot closes the ordinary race immediately
        # before the single launcher hand-off.  The launcher's OS lock remains
        # the authoritative guard against an external simultaneous starter.
        final_shards, _launchers = snapshot()
        if final_shards:
            observed_shard_ids.update(row.shard_id for row in final_shards)
            continue
        return WaitResult(
            observed_shard_ids=tuple(sorted(observed_shard_ids)),
            process_poll_count=process_poll_count,
            stale_wait_seconds=stale_wait_total,
        )


class WindowsKeepAwake:
    """Fail closed unless Windows confirms the system-awake request."""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self, setter: Callable[[int], int] | None = None) -> None:
        self.setter = setter
        self.active = False
        self.started_at_utc = ""
        self.stopped_at_utc = ""

    def _setter(self) -> Callable[[int], int]:
        if self.setter is not None:
            return self.setter
        function = ctypes.windll.kernel32.SetThreadExecutionState  # type: ignore[attr-defined]
        function.argtypes = [ctypes.c_uint]
        function.restype = ctypes.c_uint
        self.setter = function
        return function

    def __enter__(self) -> "WindowsKeepAwake":
        if os.name != "nt":
            raise RecoverySupervisorError("Le superviseur officiel V8-v2 exige Windows")
        self.started_at_utc = utc_now()
        if not int(self._setter()(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED)):
            raise RecoverySupervisorError("Windows a refusé le maintien en éveil")
        self.active = True
        return self

    def __exit__(self, *_args: Any) -> None:
        if self.active:
            setter = self._setter()
            setter(self.ES_CONTINUOUS)
        self.active = False
        self.stopped_at_utc = utc_now()

    def payload(self) -> dict[str, Any]:
        return {
            "requested": True,
            "active": self.active,
            "method": "windows_SetThreadExecutionState",
            "started_at_utc": self.started_at_utc,
            "stopped_at_utc": self.stopped_at_utc,
            "coverage": "wait_for_orphans_then_complete_resumed_launcher",
        }


@contextmanager
def exclusive_supervisor_lock(path: Path) -> Iterator[None]:
    """Prevent two recovery supervisors from launching the same campaign."""

    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise RecoverySupervisorError(
                "Un superviseur V8-v2 détient déjà le verrou"
            ) from exc
        yield
    finally:
        try:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def _validate_config(config: SupervisorConfig) -> SupervisorConfig:
    config = config.resolved()
    if not config.repo.is_dir() or not (config.repo / "etudecas").is_dir():
        raise RecoverySupervisorError(f"Dépôt etudecas absent : {config.repo}")
    if not config.campaign_root.is_dir():
        raise RecoverySupervisorError(
            f"Campagne V8-v2 absente : {config.campaign_root}"
        )
    if not config.runner.is_file() or not config.python.is_file():
        raise RecoverySupervisorError("Runner V8 ou interpréteur Python absent")
    if config.expected_runner_sha256 is not None:
        actual = _sha256_file(config.runner)
        if actual != config.expected_runner_sha256:
            raise RecoverySupervisorError(f"Empreinte runner V8 différente : {actual}")
    if config.process_poll_seconds <= 0 or config.max_wait_hours <= 0:
        raise RecoverySupervisorError("Délais de supervision invalides")
    if config.parallel_shards not in {1, 2} or config.workers_per_shard not in {
        1,
        2,
    }:
        raise RecoverySupervisorError("Parallélisme hors contrat V8")
    if not 0 <= config.launcher_poll_seconds <= 60:
        raise RecoverySupervisorError("Poll du launcher hors contrat")
    return config


def build_resumed_launcher_command(config: SupervisorConfig) -> list[str]:
    return [
        str(config.python),
        "-m",
        resilient_launcher.MODULE_NAME,
        "--campaign-root",
        str(config.campaign_root),
        "--runner",
        str(config.runner),
        "--parallel-shards",
        str(config.parallel_shards),
        "--workers-per-shard",
        str(config.workers_per_shard),
        "--poll-seconds",
        str(config.launcher_poll_seconds),
        "--detached-child",
    ]


def _status_payload(
    status: str,
    *,
    config: SupervisorConfig,
    keep_awake: Mapping[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    business_status = BUSINESS_STATUS[status]
    return {
        "schema_version": f"{SCHEMA_VERSION}.status.v1",
        "status": status,
        "business_status": business_status,
        "business_message_fr": BUSINESS_MESSAGE_FR[business_status],
        "updated_at_utc": utc_now(),
        "campaign_root": str(config.campaign_root),
        "supervision_dir": str(config.supervision_dir),
        "keep_awake": dict(keep_awake),
        **extra,
    }


def supervise(
    config: SupervisorConfig,
    *,
    scanner: ProcessScanner = scan_processes,
    popen_factory: Callable[..., LauncherProcess] = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    keep_awake_factory: Callable[[], WindowsKeepAwake] = WindowsKeepAwake,
) -> int:
    """Wait safely and synchronously own exactly one resumed V8 launcher."""

    config = _validate_config(config)
    config.supervision_dir.mkdir(parents=True, exist_ok=True)
    status_path = config.supervision_dir / "status.json"
    log_path = config.supervision_dir / "resumed_launcher_stdout_stderr.log"
    command_path = config.supervision_dir / "resume_command.json"

    def write_status(status: str, keep_awake: Mapping[str, Any], **extra: Any) -> None:
        resilient_launcher.resilient_write_json_atomic(
            status_path,
            _status_payload(
                status,
                config=config,
                keep_awake=keep_awake,
                **extra,
            ),
        )

    with exclusive_supervisor_lock(config.supervision_dir / ".supervisor.lock"):
        keeper = keep_awake_factory()
        try:
            with keeper:
                write_status("waiting", keeper.payload())

                def record_wait_state(state: str, detail: Mapping[str, Any]) -> None:
                    write_status(state, keeper.payload(), wait=dict(detail))

                result = wait_until_safe_to_resume(
                    runner=config.runner,
                    campaign_root=config.campaign_root,
                    scanner=scanner,
                    progress_inspector=lambda shard_ids: inspect_shard_progress_once(
                        config.campaign_root,
                        shard_ids,
                        stale_margin_seconds=config.stale_margin_seconds,
                    ),
                    sleep=sleep,
                    monotonic=monotonic,
                    process_poll_seconds=config.process_poll_seconds,
                    max_wait_seconds=config.max_wait_hours * 3600.0,
                    on_state=record_wait_state,
                )
                command = build_resumed_launcher_command(config)
                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(config.repo)
                environment["PYTHONUTF8"] = "1"
                environment["PYTHONIOENCODING"] = "utf-8"
                command_payload = {
                    "schema_version": f"{SCHEMA_VERSION}.command.v1",
                    "created_at_utc": utc_now(),
                    "command": command,
                    "cwd": str(config.repo),
                    "pythonpath": str(config.repo),
                    "python_utf8": True,
                    "stdout_stderr_log": str(log_path),
                    "logging": {
                        "stdout": str(log_path),
                        "stderr": "merged_into_stdout",
                    },
                    "observed_shard_ids": list(result.observed_shard_ids),
                    "process_poll_count": result.process_poll_count,
                    "stale_wait_seconds": result.stale_wait_seconds,
                }
                resilient_launcher.resilient_write_json_atomic(
                    command_path, command_payload
                )
                with log_path.open("ab") as log:
                    header = (
                        f"\n[{utc_now()}] RESUME "
                        + json.dumps(command, ensure_ascii=False)
                        + "\n"
                    )
                    log.write(header.encode("utf-8"))
                    log.flush()
                    process = popen_factory(
                        command,
                        cwd=config.repo,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        shell=False,
                        close_fds=True,
                    )
                    write_status(
                        "launcher_running",
                        keeper.payload(),
                        launcher_pid=process.pid,
                        log_path=str(log_path),
                        stdout_log=str(log_path),
                        stderr_log="merged_into_stdout",
                        command_path=str(command_path),
                        wait_result={
                            "observed_shard_ids": list(result.observed_shard_ids),
                            "process_poll_count": result.process_poll_count,
                            "stale_wait_seconds": result.stale_wait_seconds,
                        },
                    )
                    return_code = int(process.wait())
            write_status(
                "complete" if return_code == 0 else "launcher_failed",
                keeper.payload(),
                launcher_pid=process.pid,
                launcher_return_code=return_code,
                log_path=str(log_path),
                stdout_log=str(log_path),
                stderr_log="merged_into_stdout",
                command_path=str(command_path),
            )
        except Exception as exc:
            try:
                write_status(
                    "failed_closed",
                    keeper.payload(),
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            except OSError:
                pass
            raise
        return return_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--supervision-dir", type=Path, default=DEFAULT_SUPERVISION_DIR)
    parser.add_argument(
        "--process-poll-seconds",
        type=float,
        default=DEFAULT_PROCESS_POLL_SECONDS,
    )
    parser.add_argument("--max-wait-hours", type=float, default=DEFAULT_MAX_WAIT_HOURS)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--launcher-poll-seconds", type=float, default=5.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = SupervisorConfig(
        repo=args.repo,
        campaign_root=args.campaign_root,
        runner=args.runner,
        python=args.python,
        supervision_dir=args.supervision_dir,
        process_poll_seconds=args.process_poll_seconds,
        max_wait_hours=args.max_wait_hours,
        parallel_shards=args.parallel_shards,
        workers_per_shard=args.workers_per_shard,
        launcher_poll_seconds=args.launcher_poll_seconds,
    )
    try:
        return supervise(config)
    except Exception as exc:
        print(f"SUPERVISEUR V8-V2 REFUSÉ : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
