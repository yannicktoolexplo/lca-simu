#!/usr/bin/env python3
"""Arm a detached, fail-closed watcher for the additive V7 delivery stage."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_pipeline as pipeline,
)


SCHEMA_VERSION = "etudecas.supplier_v7_stage2_watcher.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservation.v1"
RECEIPT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.ready.v1"
MODULE_NAME = "etudecas.prototypes.scan_2027_risk_control.supplier_v7_stage2_watcher"
DEFAULT_POLL_SECONDS = 30.0
DEFAULT_MAX_WAIT_HOURS = 240.0
DEFAULT_STARTUP_TIMEOUT_SECONDS = 600.0


class Stage2WatcherError(common.Stage2Error):
    """The detached watcher cannot prove exclusive, fail-closed ownership."""


class Stage2WatcherTimeout(Stage2WatcherError):
    """Stage 1 did not finish within the explicitly configured wait."""


class KeepAwake:
    """Keep the Windows system awake for the complete watcher lifetime."""

    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self) -> None:
        self.active = False
        self.method = "not_started"
        self.started_at_utc = ""
        self.stopped_at_utc = ""

    def start(self) -> None:
        if self.active:
            raise Stage2WatcherError("Le maintien en éveil est déjà actif")
        self.started_at_utc = common.utc_now()
        if os.name != "nt":  # pragma: no cover - official campaign is Windows
            self.method = "not_available_non_windows"
            return
        result = ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
            self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
        )
        if not result:
            raise Stage2WatcherError("Windows a refusé le maintien en éveil")
        self.method = "windows_SetThreadExecutionState"
        self.active = True

    def stop(self) -> None:
        if self.active and os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(  # type: ignore[attr-defined]
                self.ES_CONTINUOUS
            )
        self.active = False
        self.stopped_at_utc = common.utc_now()

    def payload(self) -> dict[str, Any]:
        return {
            "requested": True,
            "active": self.active,
            "method": self.method,
            "started_at_utc": self.started_at_utc,
            "stopped_at_utc": self.stopped_at_utc,
            "coverage": "de_la_prise_du_verrou_jusqu_au_statut_terminal",
        }


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            process_query_limited_information, False, pid
        )
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(  # type: ignore[attr-defined]
                handle, ctypes.byref(code)
            ):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
    try:  # pragma: no cover - official campaign is Windows
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _attempt_dirs(root: Path) -> tuple[Path, Path]:
    return root / "detached_reservations", root / "detached_receipts"


def _read_signed(path: Path, signature_field: str, label: str) -> dict[str, Any]:
    payload = common.read_json(path)
    common.verify_signature(payload, signature_field, label)
    return payload


def _receipt_paths(root: Path) -> list[Path]:
    _reservations, receipts = _attempt_dirs(root)
    return sorted(receipts.glob("attempt_*_ready.json")) if receipts.is_dir() else []


def _latest_receipt(root: Path, contract_signature: str) -> dict[str, Any] | None:
    paths = _receipt_paths(root)
    if not paths:
        return None
    receipt = _read_signed(paths[-1], "receipt_signature", "reçu détaché étape 2")
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or receipt.get("contract_signature") != contract_signature
        or receipt.get("lock_acquired_before_ready") is not True
    ):
        raise Stage2WatcherError(
            "Le dernier reçu détaché appartient à un autre contrat"
        )
    return receipt


def _reserve_attempt(root: Path, contract_signature: str) -> tuple[int, str, Path]:
    reservations, receipts = _attempt_dirs(root)
    reservations.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)
    existing = [
        int(path.stem.removeprefix("attempt_"))
        for path in reservations.glob("attempt_*.json")
        if path.stem.removeprefix("attempt_").isdigit()
    ]
    attempt = max(existing, default=0) + 1
    token = os.urandom(24).hex()
    path = reservations / f"attempt_{attempt:04d}.json"
    unsigned = {
        "schema_version": RESERVATION_SCHEMA_VERSION,
        "contract_signature": contract_signature,
        "attempt": attempt,
        "token": token,
        "parent_pid": os.getpid(),
        "reserved_at_utc": common.utc_now(),
    }
    payload = common.signed(unsigned, "reservation_signature")
    try:
        with path.open("xb") as stream:
            stream.write(
                (
                    json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n"
                ).encode("utf-8")
            )
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:  # pragma: no cover - guarded by detach lock
        raise Stage2WatcherError("Réservation détachée concurrente") from exc
    return attempt, token, path


def _receipt_path(root: Path, attempt: int) -> Path:
    return _attempt_dirs(root)[1] / f"attempt_{attempt:04d}_ready.json"


def _validate_reservation(
    path: Path, *, attempt: int, token: str, contract_signature: str
) -> dict[str, Any]:
    payload = _read_signed(path, "reservation_signature", "réservation détachée")
    if (
        payload.get("schema_version") != RESERVATION_SCHEMA_VERSION
        or payload.get("attempt") != attempt
        or payload.get("token") != token
        or payload.get("contract_signature") != contract_signature
    ):
        raise Stage2WatcherError("Réservation détachée invalide")
    return payload


def _publish_ready(
    paths: common.Stage2Paths,
    *,
    attempt: int,
    token: str,
    contract_signature: str,
    keep_awake: Mapping[str, Any],
) -> dict[str, Any]:
    unsigned = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "contract_signature": contract_signature,
        "attempt": attempt,
        "token": token,
        "child_pid": os.getpid(),
        "ready_at_utc": common.utc_now(),
        "lock_acquired_before_ready": True,
        "source_inventory_verified_before_ready": True,
        "keep_awake": dict(keep_awake),
        "official_engine_started_before_ready": False,
    }
    receipt = common.signed(unsigned, "receipt_signature")
    common.publish_new_or_identical(
        _receipt_path(paths.supervision_dir, attempt),
        (
            json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8"),
    )
    return receipt


def _stop_unready_child(child: subprocess.Popen[Any]) -> None:
    """Stop only the child spawned by this parent before readiness."""

    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=10)


def _path_cli(paths: common.Stage2Paths) -> list[str]:
    mapping = (
        ("--repo", paths.repo),
        ("--v7-plan-dir", paths.v7_plan_dir),
        ("--v7-run-dir", paths.v7_run_dir),
        ("--trace-package-dir", paths.trace_package_dir),
        ("--bridge-json", paths.bridge_json),
        ("--campaign-root", paths.campaign_root),
        ("--results-dir", paths.results_dir),
        ("--stage1-supervision-dir", paths.stage1_supervision_dir),
        ("--lot-replay-root", paths.lot_replay_root),
        ("--qualification-dir", paths.qualification_dir),
        ("--action-replay-root", paths.action_replay_root),
        ("--curves-dir", paths.curves_dir),
        ("--registry-dir", paths.registry_dir),
        ("--final-html", paths.final_html),
        ("--supervision-dir", paths.supervision_dir),
    )
    arguments = [value for flag, path in mapping for value in (flag, str(path))]
    if paths.observed_2025_dir is not None:
        arguments.extend(["--observed-2025-dir", str(paths.observed_2025_dir)])
    return arguments


def _child_main(
    paths: common.Stage2Paths,
    *,
    attempt: int,
    token: str,
    poll_seconds: float,
    max_wait_hours: float,
) -> int:
    contract = pipeline.prepare_supervision(paths)
    if attempt > 0:
        reservation_path = (
            _attempt_dirs(paths.supervision_dir)[0] / f"attempt_{attempt:04d}.json"
        )
        _validate_reservation(
            reservation_path,
            attempt=attempt,
            token=token,
            contract_signature=str(contract["contract_signature"]),
        )
    relay: pipeline.Stage2Pipeline | None = None
    keeper = KeepAwake()
    try:
        with common.exclusive_lock(paths.supervision_dir / ".stage2.lock"):
            relay = pipeline.Stage2Pipeline(paths)
            relay.guard()
            keeper.start()
            if attempt > 0:
                _publish_ready(
                    paths,
                    attempt=attempt,
                    token=token,
                    contract_signature=str(contract["contract_signature"]),
                    keep_awake=keeper.payload(),
                )
            deadline = time.monotonic() + max_wait_hours * 3600.0
            poll_count = 0
            while True:
                relay.guard()
                state = common.probe_stage1(paths)
                if state == "accepted_stage1_complete":
                    relay.update(
                        "running",
                        "demarrage_apres_etape_1",
                        "Étape 1 signée et complète; exécution additive de l'étape 2.",
                        keep_awake=keeper.payload(),
                        detached_attempt=attempt,
                    )
                    code = relay.execute()
                    results = relay.status.get("results")
                    keeper.stop()
                    relay.update(
                        "complete",
                        "termine",
                        "Étape 2 terminée; maintien en éveil libéré.",
                        results=results,
                        keep_awake=keeper.payload(),
                        detached_attempt=attempt,
                    )
                    return code
                poll_count += 1
                if time.monotonic() >= deadline:
                    raise Stage2WatcherTimeout(
                        "L'étape 1 n'est pas complète avant la limite d'attente"
                    )
                relay.update(
                    "waiting",
                    "attente_etape_1",
                    "Watcher armé; aucune sortie aval créée avant l'étape 1 signée.",
                    stage1_state=state,
                    poll_count=poll_count,
                    keep_awake=keeper.payload(),
                    detached_attempt=attempt,
                )
                time.sleep(poll_seconds)
    except common.Stage2ScientificNoGo as exc:
        keeper.stop()
        if relay is not None:
            relay.update(
                "scientific_no_go",
                "arret_scientifique",
                "Étape 1 rejetée; aucune sortie étape 2 créée.",
                error={"type": type(exc).__name__, "message": str(exc)},
                keep_awake=keeper.payload(),
                detached_attempt=attempt,
            )
        return 3
    except Stage2WatcherTimeout as exc:
        keeper.stop()
        if relay is not None:
            relay.update(
                "waiting_timeout",
                "delai_attente_depasse",
                str(exc),
                error={"type": type(exc).__name__, "message": str(exc)},
                keep_awake=keeper.payload(),
                detached_attempt=attempt,
            )
        return 4
    except KeyboardInterrupt:
        keeper.stop()
        if relay is not None:
            relay.update(
                "interrupted_resumable",
                "interrompu",
                "Watcher interrompu; reprise possible avec le même contrat.",
                keep_awake=keeper.payload(),
                detached_attempt=attempt,
            )
        return 130
    except Exception as exc:
        keeper.stop()
        if relay is not None:
            relay.update(
                "failed_closed_resumable",
                "echec",
                "Échec fail-closed; reprise auditée possible.",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
                keep_awake=keeper.payload(),
                detached_attempt=attempt,
            )
        return 1
    finally:
        keeper.stop()


def _detach(
    paths: common.Stage2Paths,
    *,
    poll_seconds: float,
    max_wait_hours: float,
    startup_timeout_seconds: float,
) -> dict[str, Any]:
    contract = pipeline.prepare_supervision(paths)
    detach_lock = paths.supervision_dir / ".detach.lock"
    with common.exclusive_lock(detach_lock):
        latest = _latest_receipt(
            paths.supervision_dir, str(contract["contract_signature"])
        )
        if latest is not None and _pid_alive(int(latest.get("child_pid") or -1)):
            raise Stage2WatcherError(
                f"Un watcher étape 2 est déjà actif (PID {latest['child_pid']})"
            )
        status = pipeline._verify_status(  # noqa: SLF001
            paths.supervision_dir / pipeline.STATUS_NAME,
            str(contract["contract_signature"]),
        )
        if status.get("status") == "scientific_no_go":
            raise Stage2WatcherError(
                "L'étape 1 a déjà rejeté la campagne; relance interdite"
            )
        if status.get("status") == "complete":
            from etudecas.prototypes.scan_2027_risk_control import (
                supplier_v7_stage2_delivery as delivery,
            )

            proof = delivery.validate_delivery(paths)
            return {
                "status": "already_complete",
                "supervision": str(paths.supervision_dir),
                "final_html": str(paths.final_html),
                "delivery": proof,
            }
        attempt, token, _reservation = _reserve_attempt(
            paths.supervision_dir, str(contract["contract_signature"])
        )
        command = [
            sys.executable,
            "-m",
            MODULE_NAME,
            *_path_cli(paths),
            "--poll-seconds",
            str(poll_seconds),
            "--max-wait-hours",
            str(max_wait_hours),
            "--child-token",
            token,
            "--attempt",
            str(attempt),
        ]
        log_path = paths.supervision_dir / "detached_watcher.log"
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        with log_path.open("ab") as log:
            child = subprocess.Popen(  # noqa: S603
                command,
                cwd=paths.repo,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                close_fds=True,
                creationflags=creationflags,
            )
        ready_path = _receipt_path(paths.supervision_dir, attempt)
        deadline = time.monotonic() + startup_timeout_seconds
        try:
            while time.monotonic() < deadline:
                if ready_path.is_file():
                    receipt = _read_signed(
                        ready_path, "receipt_signature", "reçu de démarrage détaché"
                    )
                    if (
                        receipt.get("attempt") != attempt
                        or receipt.get("token") != token
                        or receipt.get("child_pid") != child.pid
                        or receipt.get("contract_signature")
                        != contract["contract_signature"]
                        or receipt.get("lock_acquired_before_ready") is not True
                        or receipt.get("source_inventory_verified_before_ready")
                        is not True
                        or receipt.get("keep_awake", {}).get("requested") is not True
                        or receipt.get("keep_awake", {}).get("active") is not True
                        or receipt.get("official_engine_started_before_ready")
                        is not False
                        or child.poll() is not None
                        or not _pid_alive(child.pid)
                    ):
                        raise Stage2WatcherError(
                            "Le reçu de démarrage ne correspond pas à un fils vivant et protégé"
                        )
                    return {
                        "status": "detached_ready",
                        "pid": child.pid,
                        "attempt": attempt,
                        "receipt": str(ready_path),
                        "receipt_signature": receipt["receipt_signature"],
                        "supervision": str(paths.supervision_dir),
                        "log": str(log_path),
                        "final_html": str(paths.final_html),
                        "keep_awake": receipt["keep_awake"],
                    }
                returncode = child.poll()
                if returncode is not None:
                    raise Stage2WatcherError(
                        f"Le watcher détaché s'est arrêté avant le reçu (code {returncode})"
                    )
                time.sleep(0.1)
            raise Stage2WatcherError("Délai dépassé avant le reçu de démarrage détaché")
        except BaseException:
            _stop_unready_child(child)
            raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    pipeline.add_path_arguments(parser)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--max-wait-hours", type=float, default=DEFAULT_MAX_WAIT_HOURS)
    parser.add_argument(
        "--startup-timeout-seconds",
        type=float,
        default=DEFAULT_STARTUP_TIMEOUT_SECONDS,
    )
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--child-token", default="", help=argparse.SUPPRESS)
    parser.add_argument("--attempt", type=int, default=0, help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = pipeline.paths_from_args(args)
    if not 0.1 <= args.poll_seconds <= 60.0:
        print("poll-seconds doit être compris entre 0,1 et 60", file=sys.stderr)
        return 2
    if args.max_wait_hours <= 0 or args.startup_timeout_seconds <= 0:
        print("Les délais doivent être strictement positifs", file=sys.stderr)
        return 2
    if args.detach and args.child_token:
        print("--detach et --child-token sont incompatibles", file=sys.stderr)
        return 2
    try:
        if args.detach:
            result = _detach(
                paths,
                poll_seconds=args.poll_seconds,
                max_wait_hours=args.max_wait_hours,
                startup_timeout_seconds=args.startup_timeout_seconds,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.child_token:
            if args.attempt < 1:
                raise Stage2WatcherError("Numéro de tentative enfant invalide")
            return _child_main(
                paths,
                attempt=args.attempt,
                token=args.child_token,
                poll_seconds=args.poll_seconds,
                max_wait_hours=args.max_wait_hours,
            )
        pipeline.prepare_supervision(paths)
        return _child_main(
            paths,
            attempt=0,
            token="foreground",
            poll_seconds=args.poll_seconds,
            max_wait_hours=args.max_wait_hours,
        )
    except Exception as exc:
        print(f"WATCHER ÉTAPE 2 REFUSÉ : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
