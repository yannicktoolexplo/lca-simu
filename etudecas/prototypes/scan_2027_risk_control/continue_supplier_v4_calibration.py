#!/usr/bin/env python3
"""Relay the signed V4 calibration from development to fresh holdout.

This helper is deliberately outside the signed refinement runtime closure.  It
does not interpret simulation metrics and cannot retune a candidate.  It only
waits for an already running official development stage, calls the signed V4
finalizer, and starts the sealed holdout when (and only when) development has
selected an admissible pair.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_balanced_product_delay_multiseed_refinement_v4"
)
SELECTION_STATUS = "development_selected_pending_fresh_holdout"
HOLDOUT_ACCEPTED_STATUS = "holdout_validated_30_fresh_seeds"
POLL_SECONDS = 30

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Objet JSON attendu : {path}")
    return payload


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _process_running(process_id: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, process_id)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _prevent_sleep(enabled: bool) -> None:
    if os.name != "nt":
        return
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enabled else 0)
    if not ctypes.windll.kernel32.SetThreadExecutionState(flags):
        raise OSError("SetThreadExecutionState failed")


class Relay:
    def __init__(
        self,
        *,
        repo: Path,
        plan_dir: Path,
        run_dir: Path,
        supervision_dir: Path,
        development_pid: int,
        max_wait_hours: float,
    ) -> None:
        self.repo = repo.resolve()
        self.plan_dir = plan_dir.resolve()
        self.run_dir = run_dir.resolve()
        self.supervision_dir = supervision_dir.resolve()
        self.development_pid = development_pid
        self.max_wait_seconds = max_wait_hours * 3600
        self.status_path = self.supervision_dir / "status.json"
        self.log_path = self.supervision_dir / "relay.log"

    def write_status(self, stage: str, **extra: Any) -> None:
        progress: dict[str, Any] = {}
        progress_path = self.run_dir / "development_progress.json"
        if progress_path.is_file():
            try:
                progress = _read_json(progress_path)
            except (OSError, ValueError, json.JSONDecodeError, RuntimeError):
                progress = {}
        _atomic_json(
            self.status_path,
            {
                "schema_version": "etudecas.v4_calibration_relay.status.v1",
                "stage": stage,
                "updated_at_utc": _now(),
                "relay_pid": os.getpid(),
                "development_pid": self.development_pid,
                "development_completed_case_count": progress.get(
                    "completed_case_count"
                ),
                "development_expected_case_count": progress.get("expected_case_count"),
                **extra,
            },
        )

    def log(self, message: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now()}] {message}\n")

    def run_step(self, stage: str, arguments: Sequence[str]) -> None:
        command = [sys.executable, "-m", MODULE, *arguments]
        self.write_status(stage, command=command)
        self.log("START " + json.dumps(command, ensure_ascii=False))
        with self.log_path.open("a", encoding="utf-8") as stream:
            completed = subprocess.run(
                command,
                cwd=self.repo,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        self.log(f"END {stage}: exit={completed.returncode}")
        if completed.returncode != 0:
            raise RuntimeError(f"Étape en échec : {stage}; voir {self.log_path}")

    def wait_for_development(self) -> None:
        started = time.monotonic()
        while _process_running(self.development_pid):
            elapsed = time.monotonic() - started
            if elapsed > self.max_wait_seconds:
                raise TimeoutError(
                    "La calibration de développement dépasse la durée maximale"
                )
            self.write_status(
                "waiting_for_development",
                elapsed_seconds=round(elapsed, 1),
            )
            time.sleep(POLL_SECONDS)
        time.sleep(3)
        progress = _read_json(self.run_dir / "development_progress.json")
        if (
            progress.get("status") != "complete"
            or progress.get("completed_case_count")
            != progress.get("expected_case_count")
            or progress.get("error")
        ):
            raise RuntimeError(
                "Le processus de développement s'est arrêté sans campagne complète : "
                f"{progress}"
            )

    def execute(self) -> int:
        self.log("Relais V4 démarré")
        self.run_step(
            "validate_plan_before_wait", ("validate", "--plan-dir", str(self.plan_dir))
        )
        self.wait_for_development()
        self.run_step(
            "finalize_development",
            (
                "finalize",
                "--plan-dir",
                str(self.plan_dir),
                "--run-dir",
                str(self.run_dir),
                "--stage",
                "development",
            ),
        )
        selection = _read_json(self.run_dir / "development_selection.json")
        if selection.get("status") != SELECTION_STATUS:
            self.write_status(
                "scientific_no_go_after_development",
                selection_status=selection.get("status"),
                selection_file=str(self.run_dir / "development_selection.json"),
            )
            self.log("Aucun couple admissible : le holdout n'est pas lancé")
            return 0
        self.run_step(
            "run_fresh_holdout_90_cases",
            (
                "run",
                "--plan-dir",
                str(self.plan_dir),
                "--run-dir",
                str(self.run_dir),
                "--stage",
                "holdout",
                "--workers",
                "2",
            ),
        )
        self.run_step(
            "finalize_fresh_holdout",
            (
                "finalize",
                "--plan-dir",
                str(self.plan_dir),
                "--run-dir",
                str(self.run_dir),
                "--stage",
                "holdout",
            ),
        )
        result = _read_json(self.run_dir / "holdout_result.json")
        accepted = (
            bool(result.get("accepted"))
            and result.get("status") == HOLDOUT_ACCEPTED_STATUS
        )
        self.write_status(
            "calibration_accepted" if accepted else "scientific_no_go_after_holdout",
            holdout_status=result.get("status"),
            accepted=accepted,
            holdout_result_file=str(self.run_dir / "holdout_result.json"),
        )
        self.log(f"Relais V4 terminé : accepted={accepted}")
        return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--development-pid", type=int, required=True)
    parser.add_argument("--max-wait-hours", type=float, default=16.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    supervision_dir = args.supervision_dir.resolve()
    supervision_dir.mkdir(parents=True, exist_ok=False)
    relay = Relay(
        repo=args.repo,
        plan_dir=args.plan_dir,
        run_dir=args.run_dir,
        supervision_dir=supervision_dir,
        development_pid=args.development_pid,
        max_wait_hours=args.max_wait_hours,
    )
    _prevent_sleep(True)
    try:
        return relay.execute()
    except Exception as exc:  # pragma: no cover - process boundary diagnostics
        relay.log("FAILED " + "".join(traceback.format_exception(exc)))
        relay.write_status(
            "failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 1
    finally:
        _prevent_sleep(False)


if __name__ == "__main__":
    raise SystemExit(main())
