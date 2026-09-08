#!/usr/bin/env python3
"""Supervise the strict V6 development-to-holdout calibration sequence.

The process is resumable, can detach without an interactive terminal, and owns
every child it starts.  It stops at an accepted/rejected calibration decision;
bridge, incident campaign and delivery are deliberately outside this module.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v6 as development_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_holdout_v6 as holdout_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v6 as sidecar_v6,
)
from etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v5 import (
    _relay_lock,
)
from etudecas.prototypes.scan_2027_risk_control.continue_supplier_v4_calibration import (
    _prevent_sleep,
    _process_running,
)


SCHEMA_VERSION = "etudecas.supplier_v6_calibration_orchestrator.v1"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
DETACHED_SCHEMA_VERSION = f"{SCHEMA_VERSION}.detached.v1"
MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_v6_calibration"
)
DEVELOPMENT_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_balanced_product_delay_multiseed_refinement_v6"
)
HOLDOUT_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_fresh_holdout_v6"
)
SIDECAR_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v6"
)
WORKERS = 2
DEFAULT_MAX_WAIT_HOURS = 8.0
DEFAULT_POLL_SECONDS = 5.0
SIDECAR_FINALIZATION_GRACE_SECONDS = 900.0


class V6CalibrationOrchestratorError(RuntimeError):
    """The supervised V6 calibration cannot continue safely."""


class V6ScientificNoGo(RuntimeError):
    """A signed V6 scientific decision forbids holdout or downstream work."""


@dataclass(frozen=True)
class V6CalibrationConfig:
    repo: Path
    v5_plan_dir: Path
    v5_run_dir: Path
    v5_sidecar_root: Path
    development_plan_dir: Path
    development_run_dir: Path
    holdout_plan_dir: Path
    holdout_run_dir: Path
    sidecar_dir: Path
    supervision_dir: Path
    workers: int = WORKERS
    max_wait_hours: float = DEFAULT_MAX_WAIT_HOURS
    poll_seconds: float = DEFAULT_POLL_SECONDS

    def resolved(self) -> "V6CalibrationConfig":
        values = asdict(self)
        for name in (
            "repo",
            "v5_plan_dir",
            "v5_run_dir",
            "v5_sidecar_root",
            "development_plan_dir",
            "development_run_dir",
            "holdout_plan_dir",
            "holdout_run_dir",
            "sidecar_dir",
            "supervision_dir",
        ):
            values[name] = values[name].resolve()
        return V6CalibrationConfig(**values)

    def public_mapping(self) -> dict[str, Any]:
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(self).items()
        }

    def validate_paths(self) -> None:
        if not self.repo.is_dir():
            raise V6CalibrationOrchestratorError(f"Repository missing: {self.repo}")
        if self.workers != WORKERS:
            raise V6CalibrationOrchestratorError("V6 calibration requires two workers")
        if self.max_wait_hours <= 0 or not 0.1 <= self.poll_seconds <= 60.0:
            raise V6CalibrationOrchestratorError("Invalid V6 supervision duration")
        for label, path in (
            ("V5 plan", self.v5_plan_dir),
            ("V5 run", self.v5_run_dir),
        ):
            if not path.is_dir():
                raise V6CalibrationOrchestratorError(f"{label} missing: {path}")
        outputs = (
            self.development_plan_dir,
            self.development_run_dir,
            self.holdout_plan_dir,
            self.holdout_run_dir,
            self.sidecar_dir,
            self.supervision_dir,
        )
        protected = (self.v5_plan_dir, self.v5_run_dir, self.v5_sidecar_root)
        for path in outputs:
            if path.exists() and not path.is_dir():
                raise V6CalibrationOrchestratorError(
                    f"V6 output is not a directory: {path}"
                )
            if any(development_v6._paths_overlap(path, item) for item in protected):  # noqa: SLF001
                raise V6CalibrationOrchestratorError(
                    f"V6 output overlaps a protected V5 source: {path}"
                )
        for index, left in enumerate(outputs):
            for right in outputs[index + 1 :]:
                if development_v6._paths_overlap(left, right):  # noqa: SLF001
                    raise V6CalibrationOrchestratorError(
                        "All V6 evidence and supervision roots must be distinct"
                    )

    def validate_v5_no_go(self) -> dict[str, Any]:
        self.validate_paths()
        source, plan, _evidence = development_v6._source_reference(  # noqa: SLF001
            v5_plan_dir=self.v5_plan_dir,
            v5_run_dir=self.v5_run_dir,
            v5_sidecar_root=self.v5_sidecar_root,
            allow_test_source=False,
        )
        transitive_sources = development_v6.v5._protected_source_directories(  # noqa: SLF001
            plan, source
        )
        outputs = (
            self.development_plan_dir,
            self.development_run_dir,
            self.holdout_plan_dir,
            self.holdout_run_dir,
            self.sidecar_dir,
            self.supervision_dir,
        )
        if any(
            development_v6._paths_overlap(output, protected)  # noqa: SLF001
            for output in outputs
            for protected in transitive_sources
        ):
            raise V6CalibrationOrchestratorError(
                "A V6 output overlaps a transitive immutable V4/V5 source"
            )
        if (
            source.get("development_status") != development_v6.SOURCE_TERMINAL_STATUS
            or source.get("development_evidence_case_count") != 210
            or source.get("execution_mode")
            != development_v6.v5.OFFICIAL_EXECUTION_MODE
            or (source.get("holdout_non_use_audit") or {}).get("all_absent") is not True
            or (source.get("holdout_non_use_audit") or {}).get(
                "sidecar_absent_or_empty"
            )
            is not True
        ):
            raise V6CalibrationOrchestratorError(
                "Only the terminal official V5 210-case no-go can start V6"
            )
        return source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V6CalibrationOrchestratorError(f"Unreadable JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise V6CalibrationOrchestratorError(f"JSON object expected: {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    sidecar_v6.capture_v4._atomic_write_json(path, payload)  # noqa: SLF001


def _signed(unsigned: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**unsigned, field: development_v6.stable_sha256(unsigned)}


def _module_hashes() -> dict[str, str]:
    return {
        "orchestrator_sha256": development_v6.sha256_file(Path(__file__).resolve()),
        "development_driver_sha256": development_v6.sha256_file(
            Path(development_v6.__file__).resolve()
        ),
        "holdout_driver_sha256": development_v6.sha256_file(
            Path(holdout_v6.__file__).resolve()
        ),
        "sidecar_driver_sha256": development_v6.sha256_file(
            Path(sidecar_v6.__file__).resolve()
        ),
    }


class V6CalibrationOrchestrator:
    def __init__(
        self,
        config: V6CalibrationConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config.resolved()
        self.sleep = sleep
        self.monotonic = monotonic
        self.contract_path = self.config.supervision_dir / "contract.json"
        self.status_path = self.config.supervision_dir / "status.json"
        self.log_path = self.config.supervision_dir / "orchestrator.log"
        self.contract: dict[str, Any] = {}
        self.status: dict[str, Any] = {}
        self.deadline = 0.0
        self.watcher: subprocess.Popen[Any] | None = None

    def _expected_contract(self, source: Mapping[str, Any]) -> dict[str, Any]:
        unsigned = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "configuration": self.config.public_mapping(),
            "v5_no_go_source": dict(source),
            "module_hashes": _module_hashes(),
            "scientific_contract": {
                "strict_v5_terminal_no_go_required": True,
                "v5_holdout_cases_read": 0,
                "development_evidence_cases": 150,
                "imported_development_proofs": 90,
                "new_development_engine_runs": 60,
                "fresh_holdout_engine_runs_if_selected": 90,
                "holdout_matrix": "3x30_fresh_reserved",
                "workers": WORKERS,
                "watcher_ready_required_before_first_holdout_engine": True,
                "retuning_after_holdout": False,
                "quality_incident_included": False,
                "capacity_incident_included": False,
                "availability_incident_included": False,
                "downstream_execution_supported": False,
            },
        }
        return _signed(unsigned, "contract_signature")

    def prepare(self) -> None:
        source = self.config.validate_v5_no_go()
        self.config.supervision_dir.mkdir(parents=True, exist_ok=True)
        expected = self._expected_contract(source)
        if self.contract_path.exists():
            actual = _read_json(self.contract_path)
            development_v6._verify_signature(  # noqa: SLF001
                actual, "contract_signature", "V6 calibration contract"
            )
            if actual != expected:
                raise V6CalibrationOrchestratorError(
                    "Existing V6 supervision belongs to another immutable contract"
                )
            self.contract = actual
        else:
            allowed = {"detached.json", "detached.log", ".calibration.lock"}
            if any(item.name not in allowed for item in self.config.supervision_dir.iterdir()):
                raise V6CalibrationOrchestratorError(
                    "Unregistered V6 supervision directory is not empty"
                )
            self.contract = expected
            _atomic_json(self.contract_path, expected)
        if self.status_path.exists():
            status = _read_json(self.status_path)
            development_v6._verify_signature(  # noqa: SLF001
                status, "status_signature", "V6 calibration status"
            )
            if (
                status.get("schema_version") != STATUS_SCHEMA_VERSION
                or status.get("contract_signature")
                != self.contract["contract_signature"]
            ):
                raise V6CalibrationOrchestratorError("Foreign V6 calibration status")
            self.status = status
        else:
            self.status = {
                "schema_version": STATUS_SCHEMA_VERSION,
                "contract_signature": self.contract["contract_signature"],
                "status": "running",
                "stage": "initialized",
                "message": "V5 no-go revalidated; no V6 holdout material has been read.",
                "started_at_utc": _now(),
                "completed_at_utc": "",
                "active_command": {},
                "downstream_authorized": False,
            }
        self._write_status()

    def _progress_view(self) -> dict[str, Any]:
        view: dict[str, Any] = {}
        for prefix, path in (
            ("development", self.config.development_run_dir / "development_progress.json"),
            ("holdout", self.config.holdout_run_dir / "holdout_progress.json"),
        ):
            if path.is_file():
                try:
                    payload = _read_json(path)
                except V6CalibrationOrchestratorError:
                    continue
                view[f"{prefix}_completed_case_count"] = payload.get(
                    "completed_case_count"
                )
                view[f"{prefix}_expected_case_count"] = payload.get(
                    "expected_case_count"
                )
                view[f"{prefix}_producer_status"] = payload.get("status")
        return view

    def _write_status(self) -> None:
        unsigned = dict(self.status)
        unsigned.pop("status_signature", None)
        unsigned.update(
            {
                "relay_pid": os.getpid(),
                "updated_at_utc": _now(),
                "progress": self._progress_view(),
            }
        )
        self.status = _signed(unsigned, "status_signature")
        _atomic_json(self.status_path, self.status)

    def update_status(self, stage: str, message: str, **values: Any) -> None:
        self.status.update({"stage": stage, "message": message, **values})
        self._write_status()

    def log(self, message: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now()}] {message}\n")

    def _remaining_seconds(self) -> float:
        remaining = self.deadline - self.monotonic()
        if remaining <= 0:
            raise TimeoutError("V6 calibration exceeded its global deadline")
        return remaining

    @staticmethod
    def _spawn(
        command: Sequence[str],
        *,
        cwd: Path,
        log_path: Path,
        detached: bool = False,
    ) -> subprocess.Popen[Any]:
        stream = log_path.open("ab")
        kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stdin": subprocess.DEVNULL,
            "stdout": stream,
            "stderr": subprocess.STDOUT,
            "shell": False,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            )
            if detached:
                kwargs["creationflags"] |= subprocess.DETACHED_PROCESS
        else:  # pragma: no cover
            kwargs["start_new_session"] = True
        try:
            return subprocess.Popen(list(command), **kwargs)
        finally:
            stream.close()

    @staticmethod
    def _stop_owned(process: subprocess.Popen[Any] | None) -> None:
        if process is None or process.poll() is not None:
            return
        if os.name == "nt":
            try:
                stopped = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=30.0,
                )
                if stopped.returncode != 0:
                    process.terminate()
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
        else:  # pragma: no cover
            import signal

            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=30.0)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:  # pragma: no cover
                import signal

                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=30.0)

    def run_step(
        self,
        stage: str,
        command: Sequence[str],
        *,
        guard: Callable[[], bool] | None = None,
    ) -> None:
        command = list(command)
        process = self._spawn(
            command,
            cwd=self.config.repo,
            log_path=self.config.supervision_dir / f"{stage}.log",
        )
        self.update_status(
            stage,
            f"Running {stage}",
            status="running",
            active_command={
                "argv": command,
                "sha256": development_v6.stable_sha256(command),
                "pid": process.pid,
            },
        )
        self.log(f"START {stage} pid={process.pid} {json.dumps(command)}")
        try:
            while process.poll() is None:
                self._remaining_seconds()
                if guard is not None and not guard():
                    raise V6CalibrationOrchestratorError(
                        f"Safety guard failed while {stage} was running"
                    )
                self._write_status()
                self.sleep(min(self.config.poll_seconds, self._remaining_seconds()))
            if process.returncode != 0:
                raise V6CalibrationOrchestratorError(
                    f"V6 stage failed ({process.returncode}): {stage}"
                )
        except BaseException:
            self._stop_owned(process)
            raise
        finally:
            self.status["active_command"] = {}
            self._write_status()
        self.log(f"END {stage} exit=0")

    def _python(self, module: str, *arguments: str) -> list[str]:
        return [sys.executable, "-m", module, *arguments]

    def _wait_for_external_development(self) -> None:
        lock = self.config.development_run_dir / ".v6.lock"
        while lock.exists():
            try:
                pid = int(lock.read_text(encoding="ascii").strip())
            except (OSError, ValueError) as exc:
                try:
                    age_seconds = max(0.0, time.time() - lock.stat().st_mtime)
                except OSError:
                    continue
                if age_seconds < 30.0:
                    self.update_status(
                        "waiting_for_development_lock_registration",
                        "Waiting for the external V6 development lock PID.",
                    )
                    self.sleep(
                        min(self.config.poll_seconds, self._remaining_seconds())
                    )
                    continue
                raise V6CalibrationOrchestratorError(
                    "Unreadable external V6 development lock"
                ) from exc
            if not _process_running(pid):
                self.update_status(
                    "stale_development_lock_requires_audit",
                    f"Refusing automatic removal of V6 lock from dead PID {pid}",
                )
                raise V6CalibrationOrchestratorError(
                    "Stale V6 development lock requires read-only operator audit"
                )
            self.update_status(
                "waiting_for_existing_development",
                f"Waiting for existing V6 development PID {pid}",
                active_command={"pid": pid, "owned": False},
            )
            self.sleep(min(self.config.poll_seconds, self._remaining_seconds()))
        self.status["active_command"] = {}

    def _development_commands(self) -> dict[str, list[str]]:
        return {
            "plan": self._python(
                DEVELOPMENT_MODULE,
                "plan",
                "--output-dir",
                str(self.config.development_plan_dir),
                "--v5-plan-dir",
                str(self.config.v5_plan_dir),
                "--v5-run-dir",
                str(self.config.v5_run_dir),
                "--v5-sidecar-root",
                str(self.config.v5_sidecar_root),
            ),
            "validate": self._python(
                DEVELOPMENT_MODULE,
                "validate",
                "--plan-dir",
                str(self.config.development_plan_dir),
            ),
            "run": self._python(
                DEVELOPMENT_MODULE,
                "run-development",
                "--plan-dir",
                str(self.config.development_plan_dir),
                "--run-dir",
                str(self.config.development_run_dir),
                "--workers",
                str(WORKERS),
            ),
            "finalize": self._python(
                DEVELOPMENT_MODULE,
                "finalize-development",
                "--plan-dir",
                str(self.config.development_plan_dir),
                "--run-dir",
                str(self.config.development_run_dir),
            ),
        }

    def _holdout_commands(self, watcher_pid: int = 0) -> dict[str, list[str]]:
        return {
            "plan": self._python(
                HOLDOUT_MODULE,
                "plan",
                "--output-dir",
                str(self.config.holdout_plan_dir),
                "--development-plan-dir",
                str(self.config.development_plan_dir),
                "--development-run-dir",
                str(self.config.development_run_dir),
            ),
            "validate": self._python(
                HOLDOUT_MODULE,
                "validate",
                "--plan-dir",
                str(self.config.holdout_plan_dir),
            ),
            "prepare_run": self._python(
                HOLDOUT_MODULE,
                "prepare-run",
                "--plan-dir",
                str(self.config.holdout_plan_dir),
                "--run-dir",
                str(self.config.holdout_run_dir),
            ),
            "watcher": self._python(
                SIDECAR_MODULE,
                "watch",
                "--plan-dir",
                str(self.config.holdout_plan_dir),
                "--run-dir",
                str(self.config.holdout_run_dir),
                "--output-dir",
                str(self.config.sidecar_dir),
                "--poll-ms",
                "25",
                "--stability-ms",
                "12",
                "--timeout-seconds",
                str(self.config.max_wait_hours * 3600.0),
            ),
            "run": self._python(
                HOLDOUT_MODULE,
                "run-holdout",
                "--plan-dir",
                str(self.config.holdout_plan_dir),
                "--run-dir",
                str(self.config.holdout_run_dir),
                "--workers",
                str(WORKERS),
                "--sidecar-dir",
                str(self.config.sidecar_dir),
                "--watcher-pid",
                str(watcher_pid),
            ),
            "finalize": self._python(
                HOLDOUT_MODULE,
                "finalize-holdout",
                "--plan-dir",
                str(self.config.holdout_plan_dir),
                "--run-dir",
                str(self.config.holdout_run_dir),
            ),
            "finalize_sidecar": self._python(
                SIDECAR_MODULE,
                "finalize",
                "--output-dir",
                str(self.config.sidecar_dir),
            ),
        }

    def _ensure_development_plan(self) -> None:
        commands = self._development_commands()
        if not (self.config.development_plan_dir / "refinement_plan.json").is_file():
            if self.config.development_plan_dir.exists() and any(
                self.config.development_plan_dir.iterdir()
            ):
                raise V6CalibrationOrchestratorError("Partial V6 development plan")
            self.run_step("plan_development_v6", commands["plan"])
        self.run_step("validate_development_plan_v6", commands["validate"])
        plan = development_v6.validate_plan(
            self.config.development_plan_dir, verify_runtime_dependencies=True
        )
        source = plan.manifest["v5_no_go_source"]
        if (
            Path(source["plan_dir"]).resolve() != self.config.v5_plan_dir
            or Path(source["run_dir"]).resolve() != self.config.v5_run_dir
            or Path(source["holdout_non_use_audit"]["sidecar_root"]).resolve()
            != self.config.v5_sidecar_root
        ):
            raise V6CalibrationOrchestratorError("V6 plan binds another V5 source")

    def _complete_development_state(
        self,
    ) -> tuple[Any, str, dict[tuple[str, int], dict[str, Any]]] | None:
        """Return a fully reproducible run without modifying any producer file."""

        manifest_path = self.config.development_run_dir / "run_manifest.json"
        if not manifest_path.is_file():
            return None
        plan = development_v6.validate_plan(
            self.config.development_plan_dir, verify_runtime_dependencies=True
        )
        mode = development_v6._registered_execution_mode(  # noqa: SLF001
            plan, self.config.development_run_dir
        )
        evidence, missing = development_v6._collect(  # noqa: SLF001
            plan,
            self.config.development_run_dir,
            development_v6._jobs(plan),  # noqa: SLF001
            mode,
        )
        if missing:
            return None
        progress_path = (
            self.config.development_run_dir / "development_progress.json"
        )
        if not progress_path.is_file():
            return None
        progress = _read_json(progress_path)
        development_v6._verify_signature(  # noqa: SLF001
            progress, "progress_signature", "V6 development progress"
        )
        if (
            progress.get("schema_version")
            != f"{development_v6.SCHEMA_VERSION}.development.progress"
            or progress.get("plan_signature") != plan.manifest["plan_signature"]
            or progress.get("stage") != "development"
            or progress.get("status") != "complete"
            or progress.get("completed_case_count")
            != development_v6.EXPECTED_DEVELOPMENT_CASES
            or progress.get("expected_case_count")
            != development_v6.EXPECTED_DEVELOPMENT_CASES
            or progress.get("execution_mode") != mode
            or progress.get("publishable") is not True
            or progress.get("error")
        ):
            raise V6CalibrationOrchestratorError(
                "Existing complete V6 development progress is inconsistent"
            )
        if (
            mode != development_v6.OFFICIAL_EXECUTION_MODE
            or len(evidence) != development_v6.EXPECTED_DEVELOPMENT_CASES
        ):
            raise V6CalibrationOrchestratorError(
                "V6 development evidence is not an official complete matrix"
            )
        return plan, mode, evidence

    def _existing_development_selection(self) -> dict[str, Any] | None:
        selection_path = (
            self.config.development_run_dir / "development_selection.json"
        )
        if not selection_path.is_file():
            return None
        state = self._complete_development_state()
        if state is None:
            raise V6CalibrationOrchestratorError(
                "A V6 selection exists without a complete immutable development"
            )
        plan, mode, evidence = state
        selection = _read_json(
            selection_path
        )
        rebuilt = development_v6._build_development_selection(  # noqa: SLF001
            plan, evidence, execution_mode=mode
        )
        if (
            selection != rebuilt
            or selection.get("holdout_cases_read") != 0
            or selection.get("retuning_after_development") is not False
            or selection.get("publishable") is not True
        ):
            raise V6CalibrationOrchestratorError(
                "V6 development finalization is not reproducible"
            )
        return selection

    def _finalize_development(self) -> dict[str, Any]:
        commands = self._development_commands()
        self._wait_for_external_development()
        existing = self._existing_development_selection()
        if existing is not None:
            self.update_status(
                "reuse_terminal_development_selection",
                "Revalidated terminal V6 development without rewriting it.",
            )
            return existing
        if self._complete_development_state() is None:
            self.run_step("run_or_resume_development_150", commands["run"])
        self.run_step("finalize_development_150", commands["finalize"])
        result = self._existing_development_selection()
        if result is None:  # pragma: no cover - defensive process-boundary check
            raise V6CalibrationOrchestratorError(
                "V6 development finalizer did not publish a selection"
            )
        return result

    def _ensure_holdout_plan_and_registration(self) -> Any:
        commands = self._holdout_commands()
        if not (self.config.holdout_plan_dir / "refinement_plan.json").is_file():
            if self.config.holdout_plan_dir.exists() and any(
                self.config.holdout_plan_dir.iterdir()
            ):
                raise V6CalibrationOrchestratorError("Partial V6 holdout plan")
            self.run_step("freeze_separate_holdout_plan", commands["plan"])
        self.run_step("validate_separate_holdout_plan", commands["validate"])
        plan = holdout_v6.validate_plan(
            self.config.holdout_plan_dir, verify_runtime_dependencies=True
        )
        if not (self.config.holdout_run_dir / "holdout_result.json").is_file():
            self.run_step("register_holdout_before_watcher", commands["prepare_run"])
        return plan

    def _rebuild_complete_holdout(self, plan: Any) -> dict[str, Any] | None:
        progress_path = self.config.holdout_run_dir / "holdout_progress.json"
        if not progress_path.is_file():
            return None
        progress = _read_json(progress_path)
        holdout_v6._verify_signature(  # noqa: SLF001
            progress, "progress_signature", "V6 holdout progress"
        )
        if progress.get("status") != "complete":
            return None
        mode = holdout_v6._registered_execution_mode(  # noqa: SLF001
            plan, self.config.holdout_run_dir
        )
        if mode != holdout_v6.OFFICIAL_EXECUTION_MODE:
            raise V6CalibrationOrchestratorError(
                "Existing terminal V6 holdout is not official"
            )
        selection = holdout_v6._load_development_selection(  # noqa: SLF001
            plan, self.config.holdout_run_dir
        )
        evidence = holdout_v6._load_stage_evidence(  # noqa: SLF001
            plan, self.config.holdout_run_dir, "holdout"
        )
        rebuilt = holdout_v6._build_holdout_result(  # noqa: SLF001
            plan, evidence, selection, execution_mode=mode
        )
        if (
            rebuilt.get("holdout_evidence_case_count")
            != holdout_v6.EXPECTED_HOLDOUT_CASES
            or rebuilt.get("retuning_after_holdout") is not False
            or rebuilt.get("publishable") is not True
        ):
            raise V6CalibrationOrchestratorError(
                "Complete V6 holdout evidence is not publishable"
            )
        return rebuilt

    def _existing_holdout_result(self, plan: Any) -> dict[str, Any] | None:
        """Rebuild an existing terminal holdout without touching producer files."""

        result_path = self.config.holdout_run_dir / "holdout_result.json"
        if not result_path.is_file():
            return None
        rebuilt = self._rebuild_complete_holdout(plan)
        if rebuilt is None:
            raise V6CalibrationOrchestratorError(
                "A V6 holdout result exists without complete evidence"
            )
        actual = _read_json(result_path)
        if (
            actual != rebuilt
            or actual.get("holdout_evidence_case_count")
            != holdout_v6.EXPECTED_HOLDOUT_CASES
            or actual.get("retuning_after_holdout") is not False
            or actual.get("publishable") is not True
        ):
            raise V6CalibrationOrchestratorError(
                "Existing terminal V6 holdout is not reproducible"
            )
        return actual

    def _existing_sidecar_inventory(self) -> dict[str, Any] | None:
        path = (
            self.config.sidecar_dir
            / sidecar_v6.COMPATIBILITY_INVENTORY_FILENAME
        )
        if not path.is_file():
            return None
        return sidecar_v6.validate_inventory(self.config.sidecar_dir)

    def _publish_terminal_calibration(
        self,
        result: Mapping[str, Any],
        inventory: Mapping[str, Any],
        *,
        reused: bool,
    ) -> int:
        if (
            result.get("holdout_evidence_case_count")
            != holdout_v6.EXPECTED_HOLDOUT_CASES
            or result.get("retuning_after_holdout") is not False
            or result.get("publishable") is not True
            or inventory.get("case_count")
            != holdout_v6.EXPECTED_HOLDOUT_CASES
        ):
            raise V6CalibrationOrchestratorError(
                "V6 holdout or sidecar terminal proof is incomplete"
            )
        if result.get("accepted") is not True:
            self.update_status(
                "scientific_no_go_after_holdout",
                "Fresh V6 holdout rejected; no downstream campaign is authorized.",
                status="scientific_no_go",
                completed_at_utc=_now(),
                downstream_authorized=False,
                holdout_signature=result.get("holdout_signature"),
                terminal_calibration_reused_read_only=reused,
            )
            return 3
        self.update_status(
            "calibration_accepted_ready_for_downstream_handoff",
            "V6 calibration accepted with complete sidecar; orchestrator stops here.",
            status="complete",
            completed_at_utc=_now(),
            downstream_authorized=True,
            holdout_signature=result["holdout_signature"],
            inventory_signature=inventory["inventory_signature"],
            development_engine_runs=60,
            holdout_engine_runs=90,
            terminal_calibration_reused_read_only=reused,
        )
        return 0

    def _start_watcher(self, plan: Any) -> subprocess.Popen[Any]:
        try:
            sidecar_v6.assert_watcher_lease_active(self.config.sidecar_dir)
        except sidecar_v6.CurveSidecarError:
            pass
        else:
            ready_path = self.config.sidecar_dir / "watcher_ready.json"
            if ready_path.is_file():
                ready = sidecar_v6.validate_ready(
                    ready_path, expected_output_dir=self.config.sidecar_dir
                )
                existing_pid = int(ready["watcher_pid"])
                holdout_v6._validate_sidecar_authorization(  # noqa: SLF001
                    plan,
                    self.config.holdout_run_dir,
                    sidecar_dir=self.config.sidecar_dir,
                    watcher_pid=existing_pid,
                )
                detail = f" (signed PID {existing_pid})"
            else:
                detail = " without a signed ready acknowledgement"
            raise V6CalibrationOrchestratorError(
                "An existing V6 watcher owns the sidecar lease"
                f"{detail}; refusing to start a duplicate"
            )
        command = self._holdout_commands()["watcher"]
        watcher = self._spawn(
            command,
            cwd=self.config.repo,
            log_path=self.config.supervision_dir / "sidecar_watcher.log",
        )
        self.watcher = watcher
        self.update_status(
            "waiting_for_sidecar_ready",
            "V6 sidecar started; no holdout engine is authorized yet.",
            watcher_pid=watcher.pid,
            active_command={
                "argv": command,
                "sha256": development_v6.stable_sha256(command),
                "pid": watcher.pid,
                "kind": "watcher",
            },
        )
        return watcher

    def _wait_watcher_ready(self, plan: Any, watcher: subprocess.Popen[Any]) -> None:
        ready_path = self.config.sidecar_dir / "watcher_ready.json"
        last_error: Exception | None = None
        while True:
            self._remaining_seconds()
            if watcher.poll() is not None:
                raise V6CalibrationOrchestratorError(
                    "V6 sidecar stopped before its signed ready acknowledgement"
                ) from last_error
            if ready_path.is_file():
                try:
                    holdout_v6._validate_sidecar_authorization(  # noqa: SLF001
                        plan,
                        self.config.holdout_run_dir,
                        sidecar_dir=self.config.sidecar_dir,
                        watcher_pid=watcher.pid,
                    )
                    break
                except Exception as exc:
                    # A prior crashed watcher may have left a signed receipt.
                    # No engine is running yet; wait for this process to replace it.
                    last_error = exc
            self._write_status()
            self.sleep(min(self.config.poll_seconds, self._remaining_seconds()))
        self.update_status(
            "sidecar_ready_before_holdout",
            "Signed V6 watcher acknowledgement validated before first engine.",
            active_command={},
            watcher_ready_before_first_holdout_engine=True,
        )

    def _watcher_guard(self) -> bool:
        if self.watcher is None:
            return False
        if self.watcher.poll() is None:
            return True
        inventory = self.config.sidecar_dir / sidecar_v6.COMPATIBILITY_INVENTORY_FILENAME
        return self.watcher.returncode == 0 and inventory.is_file()

    def _finalize_sidecar(self) -> dict[str, Any]:
        started = self.monotonic()
        inventory_path = (
            self.config.sidecar_dir / sidecar_v6.COMPATIBILITY_INVENTORY_FILENAME
        )
        while (
            not inventory_path.is_file()
            and self.watcher is not None
            and self.watcher.poll() is None
            and self.monotonic() - started
            < min(SIDECAR_FINALIZATION_GRACE_SECONDS, self._remaining_seconds())
        ):
            self.update_status(
                "waiting_for_sidecar_inventory",
                "Waiting for the complete 90-case curve inventory.",
            )
            self.sleep(min(self.config.poll_seconds, self._remaining_seconds()))
        self._stop_owned(self.watcher)
        self.watcher = None
        self.run_step(
            "finalize_sidecar_inventory",
            self._holdout_commands()["finalize_sidecar"],
        )
        return sidecar_v6.validate_inventory(self.config.sidecar_dir)

    def execute(self) -> int:
        self.deadline = self.monotonic() + self.config.max_wait_hours * 3600.0
        self.prepare()
        self.log("Strict V6 calibration orchestration started")
        self._ensure_development_plan()
        selection = self._finalize_development()
        if selection.get("status") == development_v6.FAIL_STATUS:
            for path in (
                self.config.holdout_plan_dir,
                self.config.holdout_run_dir,
                self.config.sidecar_dir,
            ):
                if path.exists():
                    raise V6CalibrationOrchestratorError(
                        "Holdout output exists despite a development no-go"
                    )
            self.update_status(
                "scientific_no_go_after_development",
                "No admissible V6 triplet; holdout was not planned or run.",
                status="scientific_no_go",
                completed_at_utc=_now(),
                downstream_authorized=False,
                holdout_engine_runs=0,
            )
            return 3
        if selection.get("status") != development_v6.SUCCESS_STATUS:
            raise V6CalibrationOrchestratorError(
                "Unknown V6 development terminal status"
            )
        plan = self._ensure_holdout_plan_and_registration()
        existing_result = self._existing_holdout_result(plan)
        existing_inventory = self._existing_sidecar_inventory()
        if existing_result is None and self._rebuild_complete_holdout(plan) is not None:
            self.run_step(
                "finalize_existing_fresh_holdout_90",
                self._holdout_commands()["finalize"],
            )
            existing_result = self._existing_holdout_result(plan)
        if existing_result is not None and existing_inventory is not None:
            return self._publish_terminal_calibration(
                existing_result, existing_inventory, reused=True
            )
        watcher = self._start_watcher(plan)
        try:
            if existing_result is None:
                self._wait_watcher_ready(plan, watcher)
                commands = self._holdout_commands(watcher.pid)
                self.run_step(
                    "run_fresh_holdout_3x30",
                    commands["run"],
                    guard=self._watcher_guard,
                )
                self.run_step("finalize_fresh_holdout_90", commands["finalize"])
                result = holdout_v6.finalize_holdout(
                    self.config.holdout_plan_dir, self.config.holdout_run_dir
                )
            else:
                result = existing_result
            inventory = self._finalize_sidecar()
        finally:
            self._stop_owned(self.watcher)
            self.watcher = None
        return self._publish_terminal_calibration(result, inventory, reused=False)


def _config_from_args(args: argparse.Namespace) -> V6CalibrationConfig:
    return V6CalibrationConfig(
        repo=args.repo,
        v5_plan_dir=args.v5_plan_dir,
        v5_run_dir=args.v5_run_dir,
        v5_sidecar_root=args.v5_sidecar_root,
        development_plan_dir=args.development_plan_dir,
        development_run_dir=args.development_run_dir,
        holdout_plan_dir=args.holdout_plan_dir,
        holdout_run_dir=args.holdout_run_dir,
        sidecar_dir=args.sidecar_dir,
        supervision_dir=args.supervision_dir,
        workers=args.workers,
        max_wait_hours=args.max_wait_hours,
        poll_seconds=args.poll_seconds,
    ).resolved()


def _child_command(args: argparse.Namespace) -> list[str]:
    values = (
        ("--repo", args.repo),
        ("--v5-plan-dir", args.v5_plan_dir),
        ("--v5-run-dir", args.v5_run_dir),
        ("--v5-sidecar-root", args.v5_sidecar_root),
        ("--development-plan-dir", args.development_plan_dir),
        ("--development-run-dir", args.development_run_dir),
        ("--holdout-plan-dir", args.holdout_plan_dir),
        ("--holdout-run-dir", args.holdout_run_dir),
        ("--sidecar-dir", args.sidecar_dir),
        ("--supervision-dir", args.supervision_dir),
        ("--workers", args.workers),
        ("--max-wait-hours", args.max_wait_hours),
        ("--poll-seconds", args.poll_seconds),
    )
    command = [sys.executable, "-m", MODULE_NAME]
    for flag, value in values:
        command.extend((flag, str(Path(value).resolve()) if isinstance(value, Path) else str(value)))
    command.append("--detached-child")
    return command


def detach(args: argparse.Namespace) -> dict[str, Any]:
    config = _config_from_args(args)
    # Strict read-only preflight precedes every directory, log, receipt or process.
    source = config.validate_v5_no_go()
    if config.supervision_dir.exists():
        raise V6CalibrationOrchestratorError(
            "Detached V6 launch requires a fresh supervision directory"
        )
    config.supervision_dir.mkdir(parents=True, exist_ok=False)
    relay = V6CalibrationOrchestrator(config)
    relay.contract = relay._expected_contract(source)
    _atomic_json(relay.contract_path, relay.contract)
    command = _child_command(args)
    log_path = config.supervision_dir / "detached.log"
    receipt_path = config.supervision_dir / "detached.json"
    reserved_unsigned = {
        "schema_version": DETACHED_SCHEMA_VERSION,
        "status": "detached_start_reserved",
        "pid": 0,
        "command": command,
        "command_sha256": development_v6.stable_sha256(command),
        "log_path": str(log_path),
        "status_path": str(relay.status_path),
        "preflight_v5_selection_signature": source[
            "development_selection_signature"
        ],
        "preflight_completed_before_any_output": True,
        "started_at_utc": _now(),
    }
    _atomic_json(receipt_path, _signed(reserved_unsigned, "receipt_signature"))
    try:
        process = relay._spawn(
            command, cwd=config.repo, log_path=log_path, detached=True
        )
    except BaseException as exc:
        failed = {
            **reserved_unsigned,
            "status": "detached_start_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _atomic_json(receipt_path, _signed(failed, "receipt_signature"))
        raise
    started = {
        **reserved_unsigned,
        "status": "detached_orchestrator_started",
        "pid": process.pid,
    }
    payload = _signed(started, "receipt_signature")
    try:
        _atomic_json(receipt_path, payload)
    except BaseException:
        relay._stop_owned(process)
        raise
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--v5-plan-dir", type=Path, required=True)
    parser.add_argument("--v5-run-dir", type=Path, required=True)
    parser.add_argument("--v5-sidecar-root", type=Path, required=True)
    parser.add_argument("--development-plan-dir", type=Path, required=True)
    parser.add_argument("--development-run-dir", type=Path, required=True)
    parser.add_argument("--holdout-plan-dir", type=Path, required=True)
    parser.add_argument("--holdout-run-dir", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=(WORKERS,), default=WORKERS)
    parser.add_argument("--max-wait-hours", type=float, default=DEFAULT_MAX_WAIT_HOURS)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--detach", action="store_true")
    mode.add_argument("--detached-child", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.detach:
        try:
            print(json.dumps(detach(args), ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(f"V6 CALIBRATION NOT STARTED: {exc}", file=sys.stderr)
            return 2
    config = _config_from_args(args)
    relay = V6CalibrationOrchestrator(config)
    _prevent_sleep(True)
    try:
        config.validate_v5_no_go()
        with _relay_lock(config.supervision_dir / ".calibration.lock"):
            return relay.execute()
    except KeyboardInterrupt:
        relay._stop_owned(relay.watcher)
        print("V6 CALIBRATION INTERRUPTED", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - process boundary diagnostics
        relay._stop_owned(relay.watcher)
        if relay.contract:
            relay.status["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc)),
            }
            relay.update_status(
                "failed",
                str(exc),
                status="failed",
                downstream_authorized=False,
                active_command={},
            )
        print(f"V6 CALIBRATION FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        _prevent_sleep(False)


if __name__ == "__main__":
    raise SystemExit(main())
