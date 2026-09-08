#!/usr/bin/env python3
"""Validate or run one strictly bounded V8 supplier-campaign tranche.

The mature V8 launcher intentionally resumes every incomplete shard.  This
additive command serves a different operational need: it accepts one or two
explicit, signed shard identifiers, runs exactly those shards with two workers
each, waits for them, validates their final evidence and exits.  Validation is
read-only by default; ``--execute`` is required before a child process can be
created.

Target discovery and the mandatory smoke proof must already be complete.  This
module never creates or repairs either prerequisite, never schedules an
unselected shard, never detaches and never invokes downstream consolidation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterator, Mapping, Protocol, Sequence

import psutil

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v8 as launcher_v8,
)


implementation = launcher_v8.implementation_v4
REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = launcher_v8.RUNNER.resolve()
DEFAULT_CAMPAIGN_ROOT = (
    Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
    / "supplier_operating_point_full_campaign_v8_exposure_stratified_20260906_v2"
)
SCHEMA_VERSION = "etudecas.supplier_v8.bounded_resume.v1"
EXPECTED_V8_LAUNCHER_SHA256 = (
    "bd8f39d03f97766e193a683076884739bdb72dabcc51fe06b2eadd4e9a146405"
)
EXPECTED_CAMPAIGN_SIGNATURE = (
    "fae9219a5cc59bcf9efd07b50b19009a1c7fd36b68fa81774c976b40a68c3598"
)
MAX_SELECTED_SHARDS = 2
# The frozen shard runner uses one shared ``progress.json.tmp`` path.  Two
# workers can race on Windows while replacing that file (WinError 5).  Keep
# the two shards parallel, but serialize cases inside each shard.
WORKERS_PER_SHARD = 1
DEFAULT_POLL_SECONDS = 5.0
REQUIRED_DISABLED_TASKS = (
    "Codex-Supplier-V8-Op100-Checkpoint10",
    "Codex-Supplier-V8-Post-Stage3-Final-V4",
    "Codex-Supplier-V8-Stage3-Closure-V1",
    "Codex-Supplier-V8-V2-To-Stage3-V3",
    "Codex-Supplier-V8-V3-To-V4-Guardian-V1",
    "LCA_RESILIENCE_SCAN_V8_V2_CAMPAIGN_20260906",
    "LCA_RESILIENCE_SCAN_V8_V2_STAGE2_20260906",
)


class BoundedResumeError(RuntimeError):
    """Raised when the bounded-resume contract cannot be proved."""


class ProcessLike(Protocol):
    pid: int

    def poll(self) -> int | None: ...


PopenFactory = Callable[..., ProcessLike]
ProcessScanner = Callable[[], Sequence["ObservedProcess"]]
TaskScanner = Callable[[], Mapping[str, str]]


@dataclass(frozen=True)
class ObservedProcess:
    pid: int
    name: str
    command_line: tuple[str, ...]


@dataclass(frozen=True)
class BoundedPlan:
    campaign_root: Path
    runner: Path
    campaign_signature: str
    selected_shards: tuple[Any, ...]
    selected_states: tuple[tuple[str, str], ...]
    commands: tuple[tuple[str, ...], ...]
    reuse_evidence_dirs: tuple[Path, ...]

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(shard.shard_id for shard in self.selected_shards)

    @property
    def launch_ids(self) -> tuple[str, ...]:
        return tuple(
            shard_id
            for shard_id, state in self.selected_states
            if state != "complete"
        )


@dataclass
class ActiveChild:
    shard_id: str
    process: ProcessLike
    log_handle: BinaryIO
    log_path: Path
    command: tuple[str, ...]


def _normalized_path(value: str | Path) -> str:
    return os.path.normcase(str(Path(value).resolve(strict=False)))


def _option_values(command: Sequence[str], option: str) -> list[str]:
    return [
        str(command[index + 1])
        for index, value in enumerate(command[:-1])
        if value == option
    ]


def scan_processes() -> list[ObservedProcess]:
    """Read the process table and fail if a Python command cannot be inspected."""

    observed: list[ObservedProcess] = []
    inaccessible_python: list[int] = []
    for process in psutil.process_iter(attrs=("pid", "name", "cmdline")):
        try:
            name = str(process.info.get("name") or "")
            command = process.info.get("cmdline")
            if command is None:
                if name.casefold().startswith("python"):
                    inaccessible_python.append(int(process.info["pid"]))
                continue
            observed.append(
                ObservedProcess(
                    pid=int(process.info["pid"]),
                    name=name,
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
        raise BoundedResumeError(
            "Impossible de vérifier la commande des processus Python : "
            + ", ".join(str(pid) for pid in sorted(set(inaccessible_python)))
        )
    return observed


def _is_within(value: str | Path, root: Path) -> bool:
    candidate = Path(value).resolve(strict=False)
    expected = root.resolve(strict=False)
    return candidate == expected or candidate.is_relative_to(expected)


def _targets_campaign(command: Sequence[str], campaign_root: Path) -> bool:
    expected = _normalized_path(campaign_root)
    campaign_roots = _option_values(command, "--campaign-root")
    output_roots = _option_values(command, "--output-dir")
    return any(_normalized_path(value) == expected for value in campaign_roots) or any(
        _is_within(value, campaign_root) for value in output_roots
    )


def _is_campaign_orchestrator(command: Sequence[str]) -> bool:
    known_scripts = {
        "launch_supplier_operating_point_full_campaign_v8.py",
        "launch_supplier_operating_point_full_campaign_v8_resilient.py",
        "supervise_supplier_operating_point_full_campaign_v8_v2.py",
        Path(__file__).name.casefold(),
    }
    known_modules = {
        "etudecas.prototypes.scan_2027_risk_control."
        "launch_supplier_operating_point_full_campaign_v8",
        "etudecas.prototypes.scan_2027_risk_control."
        "launch_supplier_operating_point_full_campaign_v8_resilient",
        "etudecas.prototypes.scan_2027_risk_control."
        "supervise_supplier_operating_point_full_campaign_v8_v2",
        "etudecas.prototypes.scan_2027_risk_control."
        "resume_supplier_operating_point_full_campaign_v8_bounded",
    }
    return any(
        Path(value).name.casefold() in known_scripts or value in known_modules
        for value in command
    )


def _assert_no_process_conflicts(
    records: Sequence[ObservedProcess],
    *,
    campaign_root: Path,
    runner: Path,
    current_pid: int | None = None,
) -> None:
    """Reject every visible runner or orchestrator targeting this campaign."""

    own_pid = os.getpid() if current_pid is None else current_pid
    runner_path = _normalized_path(runner)
    conflicts: list[int] = []
    for record in records:
        if record.pid == own_pid or not _targets_campaign(
            record.command_line, campaign_root
        ):
            continue
        runner_seen = any(
            _normalized_path(value) == runner_path for value in record.command_line
        )
        engine_or_runner_output = any(
            _is_within(value, campaign_root)
            for value in _option_values(record.command_line, "--output-dir")
        )
        if (
            engine_or_runner_output
            or runner_seen
            or _is_campaign_orchestrator(record.command_line)
        ):
            conflicts.append(record.pid)
    if conflicts:
        raise BoundedResumeError(
            "Un calcul ou orchestrateur vise déjà cette campagne : PID "
            + ", ".join(str(pid) for pid in sorted(set(conflicts)))
        )


def _validate_frozen_orchestration() -> None:
    launcher_v8.validate_frozen_implementation()
    path = Path(launcher_v8.__file__).resolve()
    digest = implementation._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V8_LAUNCHER_SHA256:
        raise BoundedResumeError(
            "Le launcher V8 validé a changé; reprise bornée refusée : " + digest
        )


def scan_v8_scheduled_tasks() -> dict[str, str]:
    """Return the state of known campaign tasks; absence is safe and explicit."""

    if os.name != "nt":
        return {}
    quoted_names = ",".join(f"'{name}'" for name in REQUIRED_DISABLED_TASKS)
    script = (
        "$OutputEncoding=[Console]::OutputEncoding="
        "[System.Text.UTF8Encoding]::new();"
        f"$names=@({quoted_names});"
        "@(Get-ScheduledTask -ErrorAction Stop | "
        "Where-Object { $names -contains $_.TaskName } | "
        "Select-Object TaskName,@{Name='State';Expression={$_.State.ToString()}}) "
        "| ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise BoundedResumeError(
            "Impossible de vérifier les tâches planifiées V8 : "
            + completed.stderr.strip()
        )
    try:
        rows = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise BoundedResumeError("État des tâches planifiées V8 illisible") from exc
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list):
        raise BoundedResumeError("État des tâches planifiées V8 hors contrat")
    states: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise BoundedResumeError("Ligne de tâche planifiée V8 hors contrat")
        name = str(row.get("TaskName") or "")
        state = str(row.get("State") or "")
        if name not in REQUIRED_DISABLED_TASKS or not state or name in states:
            raise BoundedResumeError("Inventaire des tâches planifiées V8 ambigu")
        states[name] = state
    return states


def _validate_task_states(states: Mapping[str, str]) -> None:
    active = {
        name: state
        for name, state in states.items()
        if state.casefold() != "disabled"
    }
    if active:
        raise BoundedResumeError(
            "Une tâche planifiée V8 n'est pas désactivée : "
            + ", ".join(f"{name}={state}" for name, state in sorted(active.items()))
        )


def _validate_reuse_roots(values: Sequence[Path]) -> tuple[Path, ...]:
    resolved = tuple(path.resolve() for path in values)
    if len(set(resolved)) != len(resolved):
        raise BoundedResumeError("Un dossier de preuves réutilisables est dupliqué")
    missing = [str(path) for path in resolved if not path.exists()]
    if missing:
        raise BoundedResumeError(
            "Dossier de preuves réutilisables absent : " + ", ".join(missing)
        )
    return resolved


def _select_shards(
    requested_ids: Sequence[str], all_shards: Sequence[Any]
) -> tuple[Any, ...]:
    if not 1 <= len(requested_ids) <= MAX_SELECTED_SHARDS:
        raise BoundedResumeError("Il faut sélectionner exactement un ou deux blocs")
    if len(set(requested_ids)) != len(requested_ids):
        raise BoundedResumeError("Un bloc ne peut pas être sélectionné deux fois")
    by_id = {str(shard.shard_id): shard for shard in all_shards}
    if len(by_id) != len(all_shards):
        raise BoundedResumeError("Le plan signé contient des identifiants de bloc dupliqués")
    unknown = [shard_id for shard_id in requested_ids if shard_id not in by_id]
    if unknown:
        raise BoundedResumeError(
            "Bloc absent du plan signé : " + ", ".join(unknown)
        )
    return tuple(by_id[shard_id] for shard_id in requested_ids)


def _validate_existing_launch_contract(
    campaign_root: Path,
    *,
    manifest: Mapping[str, Any],
    runner: Path,
    shards: Sequence[Any],
) -> None:
    """Read and compare the mature contract without creating or repairing it."""

    path = campaign_root / "launch_contract.json"
    if not path.is_file():
        raise BoundedResumeError(
            "Contrat de lancement absent; la reprise bornée ne le crée pas"
        )
    expected = implementation._launch_contract(  # noqa: SLF001
        manifest=manifest,
        runner=runner,
        shards=shards,
    )
    if implementation._read_json(path) != expected:  # noqa: SLF001
        raise BoundedResumeError("Le contrat de lancement existant a changé")


def _build_plan_in_context(
    *,
    campaign_root: Path,
    runner: Path,
    requested_ids: Sequence[str],
    reuse_evidence_dirs: Sequence[Path],
    expected_campaign_signature: str,
) -> BoundedPlan:
    manifest, shards = implementation.load_campaign_plan(campaign_root, runner)
    actual_signature = str(manifest.get("campaign_signature") or "")
    if (
        len(expected_campaign_signature) != 64
        or actual_signature != expected_campaign_signature
    ):
        raise BoundedResumeError(
            "La signature de campagne diffère de celle explicitement attendue : "
            + actual_signature
        )
    discovery_state, discovery_detail = implementation._discovery_completion_state(  # noqa: SLF001
        campaign_root, manifest=manifest
    )
    if discovery_state != "complete":
        raise BoundedResumeError(
            "La découverte V8 signée doit déjà être complète : "
            + (discovery_detail or discovery_state)
        )
    smoke_state, smoke_detail = implementation._smoke_completion_state(  # noqa: SLF001
        campaign_root, manifest=manifest
    )
    if smoke_state != "complete":
        raise BoundedResumeError(
            "La preuve préalable V8 doit déjà être complète : "
            + (smoke_detail or smoke_state)
        )
    _validate_existing_launch_contract(
        campaign_root,
        manifest=manifest,
        runner=runner,
        shards=shards,
    )
    selected = _select_shards(requested_ids, shards)
    selected_id_set = {shard.shard_id for shard in selected}
    states: dict[str, str] = {}
    for shard in shards:
        state, detail = implementation._completion_state(  # noqa: SLF001
            campaign_root,
            campaign_signature=str(manifest["campaign_signature"]),
            shard=shard,
        )
        if state == "invalid":
            raise BoundedResumeError(
                f"Preuve de bloc invalide pour {shard.shard_id} : {detail}"
            )
        if state == "active":
            raise BoundedResumeError(
                f"Le bloc {shard.shard_id} a une progression encore active : {detail}"
            )
        if shard.shard_id in selected_id_set:
            if state not in {"complete", "missing", "resumable"}:
                raise BoundedResumeError(
                    f"État non reprenable pour {shard.shard_id} : {state}"
                )
            states[shard.shard_id] = state
    commands = tuple(
        tuple(
            implementation.build_shard_command(
                runner=runner,
                campaign_root=campaign_root,
                manifest=manifest,
                shard=shard,
                workers_per_shard=WORKERS_PER_SHARD,
                reuse_evidence_dirs=reuse_evidence_dirs,
            )
        )
        for shard in selected
        if states[shard.shard_id] != "complete"
    )
    return BoundedPlan(
        campaign_root=campaign_root,
        runner=runner,
        campaign_signature=str(manifest["campaign_signature"]),
        selected_shards=selected,
        selected_states=tuple(
            (shard.shard_id, states[shard.shard_id]) for shard in selected
        ),
        commands=commands,
        reuse_evidence_dirs=tuple(reuse_evidence_dirs),
    )


def _plan_payload(plan: BoundedPlan, *, mode: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "already_complete" if not plan.commands else "ready_for_explicit_execution"
        ),
        "mode": mode,
        "campaign_root": str(plan.campaign_root),
        "campaign_signature": plan.campaign_signature,
        "runner": str(plan.runner),
        "selected_shard_ids": list(plan.selected_ids),
        "selected_states": [
            {"shard_id": shard_id, "state": state}
            for shard_id, state in plan.selected_states
        ],
        "would_launch_shard_ids": list(plan.launch_ids),
        "exact_commands_if_executed": [list(command) for command in plan.commands],
        "selected_shard_count": len(plan.selected_ids),
        "maximum_simultaneous_shards": MAX_SELECTED_SHARDS,
        "workers_per_shard": WORKERS_PER_SHARD,
        "maximum_engine_processes": len(plan.launch_ids) * WORKERS_PER_SHARD,
        "validation_is_read_only": mode == "validate_only",
        "explicit_execute_required": True,
        "unselected_shards_never_scheduled": True,
        "target_discovery_never_scheduled": True,
        "smoke_never_scheduled": True,
        "downstream_steps_never_scheduled": True,
        "detached_execution_supported": False,
    }


def inspect_bounded_resume(
    *,
    campaign_root: Path,
    requested_ids: Sequence[str],
    runner: Path = RUNNER,
    reuse_evidence_dirs: Sequence[Path] = (),
    expected_campaign_signature: str = EXPECTED_CAMPAIGN_SIGNATURE,
    scanner: ProcessScanner = scan_processes,
    task_scanner: TaskScanner = scan_v8_scheduled_tasks,
) -> dict[str, Any]:
    """Perform the default read-only validation; never acquire or write a lock."""

    campaign_root = campaign_root.resolve()
    runner = runner.resolve()
    reuse_roots = _validate_reuse_roots(reuse_evidence_dirs)
    _validate_frozen_orchestration()
    with launcher_v8.patched_v8_context():
        plan = _build_plan_in_context(
            campaign_root=campaign_root,
            runner=runner,
            requested_ids=requested_ids,
            reuse_evidence_dirs=reuse_roots,
            expected_campaign_signature=expected_campaign_signature,
        )
    _assert_no_process_conflicts(
        scanner(), campaign_root=campaign_root, runner=runner
    )
    task_states = dict(task_scanner())
    _validate_task_states(task_states)
    payload = _plan_payload(plan, mode="validate_only")
    payload["known_v8_scheduled_task_states"] = task_states
    payload["all_known_v8_scheduled_tasks_disabled_or_absent"] = True
    return payload


@contextmanager
def keep_system_awake() -> Iterator[dict[str, Any]]:
    """Keep Windows system sleep off without writing a shared campaign file."""

    state = {"status": "not_applicable_non_windows", "acquired": False}
    if os.name != "nt":
        yield state
        return
    import ctypes

    es_system_required = 0x00000001
    es_continuous = 0x80000000
    setter = ctypes.windll.kernel32.SetThreadExecutionState  # type: ignore[attr-defined]
    setter.argtypes = [ctypes.c_uint]
    setter.restype = ctypes.c_uint
    previous = int(setter(es_continuous | es_system_required))
    if previous == 0:
        raise BoundedResumeError("Windows refuse le maintien d'éveil système")
    state = {"status": "active", "acquired": True}
    try:
        yield state
    finally:
        setter(es_continuous)


def _new_run_dir(campaign_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = campaign_root / "bounded_resume_runs" / f"{stamp}_{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_run_status(path: Path, payload: Mapping[str, Any]) -> None:
    implementation._write_json_atomic(path, dict(payload))  # noqa: SLF001


def _child_environment() -> dict[str, str]:
    """Expose the repository package when Python executes the runner by path."""

    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH", "")
    entries = [str(REPO_ROOT)]
    if existing:
        entries.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(entries)
    return environment


def _execute_plan(
    plan: BoundedPlan,
    *,
    poll_seconds: float,
    popen_factory: PopenFactory,
    sleep: Callable[[float], None],
    awake_factory: Callable[[], Any],
) -> dict[str, Any]:
    if not 0.0 <= poll_seconds <= 60.0:
        raise BoundedResumeError("Le délai de contrôle doit être compris entre 0 et 60 s")
    if not plan.commands:
        payload = _plan_payload(plan, mode="execute")
        payload["status"] = "complete_selected_shards"
        payload["launched_shard_ids"] = []
        return payload

    run_dir = _new_run_dir(plan.campaign_root)
    status_path = run_dir / "status.json"
    base = _plan_payload(plan, mode="execute")
    base.update(
        {
            "run_dir": str(run_dir),
            "status": "starting_selected_shards",
            "launched_shard_ids": [],
            "completed_shard_ids": [
                shard_id
                for shard_id, state in plan.selected_states
                if state == "complete"
            ],
            "failures": [],
            "updated_at_utc": implementation.utc_now(),
        }
    )
    _write_run_status(status_path, base)
    active: dict[str, ActiveChild] = {}
    launched: list[str] = []
    completed = list(base["completed_shard_ids"])
    failures: list[dict[str, Any]] = []

    with awake_factory() as awake:
        for shard_id, command in zip(plan.launch_ids, plan.commands, strict=True):
            log_path = run_dir / f"{shard_id}.log"
            log_handle = log_path.open("xb")
            log_handle.write(
                (
                    "["
                    + implementation.utc_now()
                    + "] LAUNCH "
                    + json.dumps(command, ensure_ascii=False)
                    + "\n"
                ).encode("utf-8")
            )
            log_handle.flush()
            try:
                process = popen_factory(
                    list(command),
                    cwd=REPO_ROOT,
                    env=_child_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
            except Exception as exc:  # noqa: BLE001 - preserve launch evidence
                log_handle.close()
                failures.append(
                    {
                        "shard_id": shard_id,
                        "stage": "process_start",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                break
            launched.append(shard_id)
            active[shard_id] = ActiveChild(
                shard_id=shard_id,
                process=process,
                log_handle=log_handle,
                log_path=log_path,
                command=command,
            )

        while active:
            finished_any = False
            for shard_id, child in list(active.items()):
                return_code = child.process.poll()
                if return_code is None:
                    continue
                finished_any = True
                child.log_handle.flush()
                child.log_handle.close()
                del active[shard_id]
                shard = next(
                    item for item in plan.selected_shards if item.shard_id == shard_id
                )
                state, detail = implementation._completion_state(  # noqa: SLF001
                    plan.campaign_root,
                    campaign_signature=plan.campaign_signature,
                    shard=shard,
                )
                if return_code == 0 and state == "complete":
                    completed.append(shard_id)
                else:
                    failures.append(
                        {
                            "shard_id": shard_id,
                            "stage": "final_evidence",
                            "return_code": return_code,
                            "completion_state": state,
                            "detail": detail,
                        }
                    )
            base.update(
                {
                    "status": "running_selected_shards" if active else "validating",
                    "launched_shard_ids": list(launched),
                    "active_shard_ids": sorted(active),
                    "completed_shard_ids": sorted(set(completed)),
                    "failures": list(failures),
                    "keep_awake": dict(awake),
                    "updated_at_utc": implementation.utc_now(),
                }
            )
            _write_run_status(status_path, base)
            if active and not finished_any:
                sleep(poll_seconds)

    success = not failures and set(completed) == set(plan.selected_ids)
    base.update(
        {
            "status": "complete_selected_shards" if success else "failed",
            "active_shard_ids": [],
            "launched_shard_ids": list(launched),
            "completed_shard_ids": sorted(set(completed)),
            "failures": failures,
            "updated_at_utc": implementation.utc_now(),
        }
    )
    _write_run_status(status_path, base)
    return base


def execute_bounded_resume(
    *,
    campaign_root: Path,
    requested_ids: Sequence[str],
    runner: Path = RUNNER,
    reuse_evidence_dirs: Sequence[Path] = (),
    expected_campaign_signature: str = EXPECTED_CAMPAIGN_SIGNATURE,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    scanner: ProcessScanner = scan_processes,
    task_scanner: TaskScanner = scan_v8_scheduled_tasks,
    popen_factory: PopenFactory = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    awake_factory: Callable[[], Any] = keep_system_awake,
) -> dict[str, Any]:
    """Run only the explicitly selected shard subset and wait until it ends."""

    campaign_root = campaign_root.resolve()
    runner = runner.resolve()
    reuse_roots = _validate_reuse_roots(reuse_evidence_dirs)
    _validate_frozen_orchestration()
    with launcher_v8.patched_v8_context():
        lock_path = campaign_root / ".full_campaign_v4_launcher.lock"
        with implementation._launcher_lock(lock_path):  # noqa: SLF001
            plan = _build_plan_in_context(
                campaign_root=campaign_root,
                runner=runner,
                requested_ids=requested_ids,
                reuse_evidence_dirs=reuse_roots,
                expected_campaign_signature=expected_campaign_signature,
            )
            _assert_no_process_conflicts(
                scanner(), campaign_root=campaign_root, runner=runner
            )
            task_states = dict(task_scanner())
            _validate_task_states(task_states)
            result = _execute_plan(
                plan,
                poll_seconds=poll_seconds,
                popen_factory=popen_factory,
                sleep=sleep,
                awake_factory=awake_factory,
            )
            result["known_v8_scheduled_task_states"] = task_states
            result["all_known_v8_scheduled_tasks_disabled_or_absent"] = True
            if result.get("run_dir"):
                _write_run_status(Path(str(result["run_dir"])) / "status.json", result)
            if result["status"] == "complete_selected_shards":
                final_plan = _build_plan_in_context(
                    campaign_root=campaign_root,
                    runner=runner,
                    requested_ids=requested_ids,
                    reuse_evidence_dirs=reuse_roots,
                    expected_campaign_signature=expected_campaign_signature,
                )
                if final_plan.commands:
                    raise BoundedResumeError(
                        "La preuve finale signée reste incomplète pour un bloc sélectionné"
                    )
            return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument(
        "--expected-campaign-signature",
        default=EXPECTED_CAMPAIGN_SIGNATURE,
        help="Empreinte SHA-256 exacte de la campagne autorisée.",
    )
    parser.add_argument(
        "--shard-id",
        action="append",
        required=True,
        help=(
            "Identifiant exact du plan signé, par exemple "
            "op_100__seed_block_03. Répéter au maximum deux fois."
        ),
    )
    parser.add_argument("--reuse-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument(
        "--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Autorise explicitement le lancement des seuls blocs sélectionnés. "
            "Sans ce drapeau, le contrôle est strictement en lecture seule."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.execute:
            result = execute_bounded_resume(
                campaign_root=args.campaign_root,
                runner=args.runner,
                requested_ids=args.shard_id,
                reuse_evidence_dirs=args.reuse_evidence_dir,
                expected_campaign_signature=args.expected_campaign_signature,
                poll_seconds=args.poll_seconds,
            )
        else:
            result = inspect_bounded_resume(
                campaign_root=args.campaign_root,
                runner=args.runner,
                requested_ids=args.shard_id,
                reuse_evidence_dirs=args.reuse_evidence_dir,
                expected_campaign_signature=args.expected_campaign_signature,
            )
    except (BoundedResumeError, FileNotFoundError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "refused",
                    "mode": "execute" if args.execute else "validate_only",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
