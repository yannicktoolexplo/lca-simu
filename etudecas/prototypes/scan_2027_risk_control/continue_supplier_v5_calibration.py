#!/usr/bin/env python3
"""Relais fail-closed entre le développement et le holdout V5.

Ce processus n'ajuste aucun paramètre. Il attend le développement pré-enregistré,
le finalise, puis n'autorise les 90 nouvelles exécutions de holdout que si un
couple est sélectionné et si le watcher de courbes a publié un accusé signé.
Deux moteurs, exactement, sont utilisés pour le holdout.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v5 as capture_v5,
)
from etudecas.prototypes.scan_2027_risk_control.continue_supplier_v4_calibration import (
    _prevent_sleep,
    _process_running,
)


MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_balanced_product_delay_multiseed_refinement_v5"
)
SELECTION_STATUS = "development_selected_pending_fresh_holdout"
EXPECTED_DEVELOPMENT_CASES = refinement.EXPECTED_DEVELOPMENT_CASES
EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS = refinement.EXPECTED_NEW_DEVELOPMENT_CASES
EXPECTED_HOLDOUT_CASES = refinement.EXPECTED_HOLDOUT_CASES
WORKERS = 2
DEFAULT_POLL_SECONDS = 10.0
STATUS_SCHEMA_VERSION = "etudecas.v5_calibration_relay.status.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Objet JSON attendu : {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    capture_v4._atomic_write_json(path, payload)  # noqa: SLF001


def _verify_progress(
    path: Path,
    *,
    stage: str,
    expected: int,
    require_complete: bool,
    expected_plan_signature: str | None = None,
) -> dict[str, Any]:
    payload = _read_json(path)
    capture_v4._verify_signature(  # noqa: SLF001
        payload, "progress_signature", f"progression V5 {stage}"
    )
    completed = payload.get("completed_case_count")
    if (
        payload.get("schema_version") != f"{refinement.SCHEMA_VERSION}.{stage}.progress"
        or payload.get("stage") != stage
        or type(completed) is not int
        or payload.get("expected_case_count") != expected
        or not 0 <= completed <= expected
        or payload.get("publishable") is not True
        or (
            expected_plan_signature is not None
            and payload.get("plan_signature") != expected_plan_signature
        )
    ):
        raise RuntimeError(f"Progression V5 {stage} incohérente")
    if require_complete and (
        payload.get("status") != "complete"
        or completed != expected
        or payload.get("error")
    ):
        raise RuntimeError(f"Étape V5 {stage} incomplète : {payload}")
    return payload


class Relay:
    def __init__(
        self,
        *,
        repo: Path,
        plan_dir: Path,
        run_dir: Path,
        supervision_dir: Path,
        development_pid: int,
        watcher_pid: int,
        sidecar_dir: Path,
        max_wait_hours: float,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
    ) -> None:
        self.repo = repo.resolve()
        self.plan_dir = plan_dir.resolve()
        self.run_dir = run_dir.resolve()
        self.supervision_dir = supervision_dir.resolve()
        self.development_pid = int(development_pid)
        self.watcher_pid = int(watcher_pid)
        self.sidecar_dir = sidecar_dir.resolve()
        self.max_wait_seconds = float(max_wait_hours) * 3600.0
        self.poll_seconds = float(poll_seconds)
        if self.max_wait_seconds <= 0 or self.poll_seconds <= 0:
            raise ValueError("Durées de supervision V5 invalides")
        self.status_path = self.supervision_dir / "relay_status.json"
        self.log_path = self.supervision_dir / "relay.log"

    def plan_signature(self) -> str:
        payload = _read_json(self.plan_dir / "refinement_plan.json")
        signature = str(payload.get("plan_signature") or "")
        if len(signature) != 64:
            raise RuntimeError("Signature du plan V5 absente")
        return signature

    def log(self, message: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now()}] {message}\n")

    def _progress_view(self, stage: str) -> dict[str, Any]:
        path = self.run_dir / f"{stage}_progress.json"
        if not path.is_file():
            return {}
        try:
            payload = _read_json(path)
        except RuntimeError:
            return {}
        return {
            f"{stage}_completed_case_count": payload.get("completed_case_count"),
            f"{stage}_expected_case_count": payload.get("expected_case_count"),
            f"{stage}_producer_status": payload.get("status"),
        }

    def write_status(self, stage: str, **extra: Any) -> None:
        unsigned = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "stage": stage,
            "updated_at_utc": _now(),
            "relay_pid": os.getpid(),
            "development_pid": self.development_pid,
            "watcher_pid": self.watcher_pid,
            "workers_per_simulation_stage": WORKERS,
            "expected_development_evidence_cases": EXPECTED_DEVELOPMENT_CASES,
            "expected_new_development_engine_runs": (
                EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS
            ),
            "expected_fresh_holdout_engine_runs": EXPECTED_HOLDOUT_CASES,
            **self._progress_view("development"),
            **self._progress_view("holdout"),
            **extra,
        }
        _atomic_json(
            self.status_path,
            {**unsigned, "status_signature": refinement.stable_sha256(unsigned)},
        )

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
                raise TimeoutError("Le développement V5 dépasse la durée maximale")
            self.write_status(
                "waiting_for_development", elapsed_seconds=round(elapsed, 1)
            )
            time.sleep(self.poll_seconds)
        time.sleep(min(self.poll_seconds, 1.0))
        _verify_progress(
            self.run_dir / "development_progress.json",
            stage="development",
            expected=EXPECTED_DEVELOPMENT_CASES,
            require_complete=True,
            expected_plan_signature=self.plan_signature(),
        )

    def wait_for_watcher_ready(self) -> dict[str, Any]:
        started = time.monotonic()
        path = self.sidecar_dir / "watcher_ready.json"
        while not path.is_file():
            elapsed = time.monotonic() - started
            if elapsed > min(self.max_wait_seconds, 1800.0):
                raise TimeoutError("Le watcher V5 n'a pas publié son accusé")
            if not _process_running(self.watcher_pid):
                raise RuntimeError("Le watcher V5 s'est arrêté avant le holdout")
            self.write_status(
                "waiting_for_curve_watcher_ready",
                elapsed_seconds=round(elapsed, 1),
            )
            time.sleep(min(self.poll_seconds, 2.0))
        ready = capture_v5.validate_ready(
            path,
            expected_output_dir=self.sidecar_dir,
            expected_watcher_pid=self.watcher_pid,
        )
        contract = capture_v5.validate_contract(
            _read_json(self.sidecar_dir / "capture_contract.json")
        )
        if (
            contract.get("schema_version") != capture_v5.CONTRACT_SCHEMA_VERSION
            or contract.get("producer_protocol") != refinement.SCHEMA_VERSION
            or int(contract.get("expected_case_count") or -1) != EXPECTED_HOLDOUT_CASES
            or Path(str((contract.get("plan") or {}).get("directory") or "")).resolve()
            != self.plan_dir
            or Path(str((contract.get("run") or {}).get("directory") or "")).resolve()
            != self.run_dir
            or ready.get("contract_signature") != contract.get("contract_signature")
            or not _process_running(self.watcher_pid)
        ):
            raise RuntimeError("Watcher ou contrat sidecar V5 incohérent")
        return ready

    def _curve_capture_status(self) -> dict[str, Any]:
        inventory_path = self.sidecar_dir / "capture_inventory_v5.json"
        if inventory_path.is_file():
            inventory = _read_json(inventory_path)
            capture_v4._verify_signature(  # noqa: SLF001
                inventory, "inventory_signature", "inventaire sidecar V5"
            )
            if (
                inventory.get("schema_version") == capture_v5.INVENTORY_SCHEMA_VERSION
                and inventory.get("status") == "complete"
                and int(inventory.get("case_count") or -1) == EXPECTED_HOLDOUT_CASES
            ):
                return {
                    "curve_capture_complete": True,
                    "curve_inventory_file": str(inventory_path),
                }
        progress_path = self.sidecar_dir / "capture_progress.json"
        progress = _read_json(progress_path) if progress_path.is_file() else {}
        return {
            "curve_capture_complete": False,
            "curve_capture_completed_cases": progress.get("completed_cases"),
            "curve_capture_expected_cases": progress.get("expected_cases"),
            "curve_capture_watcher_running": _process_running(self.watcher_pid),
        }

    def wait_for_curve_capture(self) -> dict[str, Any]:
        started = time.monotonic()
        while time.monotonic() - started <= 900.0:
            status = self._curve_capture_status()
            if status.get("curve_capture_complete"):
                return status
            if not _process_running(self.watcher_pid):
                return status
            time.sleep(min(self.poll_seconds, 2.0))
        return self._curve_capture_status()

    def execute(self) -> int:
        self.log("Relais V5 démarré")
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
        if (
            selection.get("status") != SELECTION_STATUS
            or selection.get("selected_candidate_keys") is None
        ):
            self.write_status(
                "scientific_no_go_after_development",
                selection_status=selection.get("status"),
                holdout_engine_runs=0,
                selection_file=str(self.run_dir / "development_selection.json"),
            )
            self.log("Aucun couple admissible : aucun holdout n'est lancé")
            return 0

        self.wait_for_watcher_ready()
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
                str(WORKERS),
            ),
        )
        _verify_progress(
            self.run_dir / "holdout_progress.json",
            stage="holdout",
            expected=EXPECTED_HOLDOUT_CASES,
            require_complete=True,
            expected_plan_signature=self.plan_signature(),
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
        accepted = bool(result.get("accepted"))
        if (
            int(result.get("holdout_evidence_case_count") or -1)
            != EXPECTED_HOLDOUT_CASES
        ):
            raise RuntimeError("Le résultat holdout V5 ne prouve pas 90 cas frais")
        curve_status = self.wait_for_curve_capture()
        terminal = (
            "calibration_accepted" if accepted else "scientific_no_go_after_holdout"
        )
        if accepted and not curve_status.get("curve_capture_complete"):
            terminal = "calibration_accepted_curve_capture_incomplete"
        self.write_status(
            terminal,
            accepted=accepted,
            holdout_status=result.get("status"),
            holdout_result_file=str(self.run_dir / "holdout_result.json"),
            **curve_status,
        )
        self.log(
            f"Relais V5 terminé : accepted={accepted}, "
            f"curve_capture={curve_status.get('curve_capture_complete')}"
        )
        return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--development-pid", type=int, required=True)
    parser.add_argument("--watcher-pid", type=int, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument("--max-wait-hours", type=float, default=16.0)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    supervision_dir = args.supervision_dir.resolve()
    supervision_dir.mkdir(parents=True, exist_ok=True)
    relay = Relay(
        repo=args.repo,
        plan_dir=args.plan_dir,
        run_dir=args.run_dir,
        supervision_dir=supervision_dir,
        development_pid=args.development_pid,
        watcher_pid=args.watcher_pid,
        sidecar_dir=args.sidecar_dir,
        max_wait_hours=args.max_wait_hours,
        poll_seconds=args.poll_seconds,
    )
    _prevent_sleep(True)
    try:
        return relay.execute()
    except Exception as exc:  # pragma: no cover - frontière processus
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
