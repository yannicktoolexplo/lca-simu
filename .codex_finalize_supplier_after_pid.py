#!/usr/bin/env python3
"""Finish the additive supplier-risk preliminary delivery after campaign PID 33444.

This one-shot local relay never writes inside an existing delivery.  It waits
for the active campaign to publish its signed 15/30 checkpoint, builds and
validates the compact three-view package, then runs only the separately scoped
three-seed old/new dynamic-reference smoke diagnostic.
"""

from __future__ import annotations

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


REPO = Path(r"C:\dev\lca-simu-pr40")
ARTIFACTS = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
CAMPAIGN_PID = 33444
CAMPAIGN = ARTIFACTS / "supplier_network_post_priority_extensions_20260903_v1"
PLAN = ARTIFACTS / "supplier_network_post_priority_extensions_plan_20260903_v3"
BOUNDARY = ARTIFACTS / "supplier_network_priority_boundary_audit_20260903_v1"
PRELIMINARY = ARTIFACTS / "supplier_network_preliminary_15_of_30_20260904_v1"
DELIVERY = ARTIFACTS / "industrial_supply_preliminary_delivery_15_of_30_20260904_v1"
PROTOCOL = ARTIFACTS / "supplier_dynamic_requirement_reference_protocol_20260903_v2"
SMOKE = ARTIFACTS / "supplier_dynamic_requirement_reference_smoke3_20260904_v2"
SUPERVISION = ARTIFACTS / "supplier_overnight_finalizer_20260904_v1"
STATUS = SUPERVISION / "status.json"
LOG = SUPERVISION / "finalizer.log"
CAMPAIGN_MANIFEST = CAMPAIGN / "post_priority_extension_runner_manifest.json"
CHECKPOINT = CAMPAIGN / "preliminary_checkpoint_15_manifest.json"
LEDGER = CAMPAIGN / "execution_ledger.json"
EXPECTED_CHECKPOINT_EVIDENCE = 634
POLL_SECONDS = 30
MAX_WAIT_SECONDS = 12 * 60 * 60

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Objet JSON attendu: {path}")
    return payload


def write_status(stage: str, **extra: Any) -> None:
    SUPERVISION.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "updated_at_utc": now(),
        "relay_pid": os.getpid(),
        "campaign_pid": CAMPAIGN_PID,
        **extra,
    }
    temporary = STATUS.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(STATUS)


def log(message: str) -> None:
    SUPERVISION.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write(f"[{now()}] {message}\n")


def prevent_sleep(enabled: bool) -> None:
    if os.name != "nt":
        return
    flags = ES_CONTINUOUS
    if enabled:
        flags |= ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
    if not result:
        raise OSError("SetThreadExecutionState failed")


def process_running(process_id: int) -> bool:
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


def ledger_count() -> int | None:
    try:
        values = read_json(LEDGER).get("case_file_sha256")
        return len(values) if isinstance(values, dict) else None
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError):
        return None


def run_step(name: str, arguments: Sequence[str]) -> None:
    command = [sys.executable, *arguments]
    write_status(name, campaign_evidence_count=ledger_count())
    log(f"START {name}: {json.dumps(command, ensure_ascii=False)}")
    with LOG.open("a", encoding="utf-8") as stream:
        completed = subprocess.run(
            command,
            cwd=REPO,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    log(f"END {name}: exit={completed.returncode}")
    if completed.returncode != 0:
        raise RuntimeError(f"Étape en échec: {name}; voir {LOG}")


def assert_new_targets() -> None:
    existing = [str(path) for path in (PRELIMINARY, DELIVERY, SMOKE) if path.exists()]
    if existing:
        raise RuntimeError(
            "Le relais refuse d'écraser ou de reprendre une sortie existante: "
            + ", ".join(existing)
        )


def wait_for_campaign() -> None:
    started = time.monotonic()
    while True:
        try:
            live_manifest = read_json(CAMPAIGN_MANIFEST)
            checkpoint_published = (
                live_manifest.get("status") == "paused_preliminary"
                and live_manifest.get("active_process_id") == 0
                and CHECKPOINT.is_file()
            )
        except (OSError, ValueError, json.JSONDecodeError, RuntimeError):
            checkpoint_published = False
        if checkpoint_published or not process_running(CAMPAIGN_PID):
            break
        elapsed = time.monotonic() - started
        if elapsed > MAX_WAIT_SECONDS:
            raise TimeoutError("La campagne principale tourne encore après 12 heures")
        write_status(
            "waiting_for_main_campaign",
            elapsed_seconds=round(elapsed, 1),
            campaign_evidence_count=ledger_count(),
        )
        time.sleep(POLL_SECONDS)
    # Let the parent finish its final atomic manifest/checkpoint writes.
    time.sleep(5)
    manifest = read_json(CAMPAIGN_MANIFEST)
    checkpoint = read_json(CHECKPOINT)
    evidence_count = ledger_count()
    if (
        manifest.get("status") != "paused_preliminary"
        or manifest.get("active_process_id") != 0
        or checkpoint.get("status") != "paused_preliminary"
        or checkpoint.get("ledger_evidence_case_count")
        != EXPECTED_CHECKPOINT_EVIDENCE
        or evidence_count != EXPECTED_CHECKPOINT_EVIDENCE
    ):
        raise RuntimeError(
            "La campagne ne s'est pas arrêtée sur le jalon 15/30 attendu: "
            f"status={manifest.get('status')}, preuves={evidence_count}"
        )
    write_status(
        "main_campaign_checkpoint_ready",
        campaign_evidence_count=evidence_count,
    )


def main() -> int:
    SUPERVISION.mkdir(parents=True, exist_ok=False)
    log("Relais de finalisation démarré")
    prevent_sleep(True)
    try:
        assert_new_targets()
        wait_for_campaign()
        run_step(
            "building_preliminary_audit",
            (
                "-m",
                "etudecas.prototypes.scan_2027_risk_control.supplier_network_preliminary_15_audit",
                "--runner-dir",
                str(CAMPAIGN),
                "--plan-dir",
                str(PLAN),
                "--boundary-dir",
                str(BOUNDARY),
                "--output-dir",
                str(PRELIMINARY),
            ),
        )
        run_step(
            "validating_preliminary_audit",
            (
                "-m",
                "etudecas.prototypes.scan_2027_risk_control.supplier_network_preliminary_15_audit",
                "--validate-only",
                "--output-dir",
                str(PRELIMINARY),
            ),
        )
        run_step(
            "building_three_view_delivery",
            (
                "-m",
                "etudecas.prototypes.scan_2027_risk_control.build_industrial_supply_preliminary_delivery",
                "--preliminary-dir",
                str(PRELIMINARY),
                "--observed-dir",
                str(ARTIFACTS / "observed_2025_supply_bilan_20260901_v1"),
                "--quality-dir",
                str(ARTIFACTS / "supplier_021081_final_dashboard_20260902_v3"),
                "--network-map-html",
                str(
                    ARTIFACTS
                    / "DEMONSTRATION_SUPPLY_CHAIN_AUTONOME_FICHIER_UNIQUE_20260831.html"
                ),
                "--regime-plan-dir",
                str(ARTIFACTS / "supplier_service_regime_calibration_plan_20260903_v2"),
                "--action-plan-dir",
                str(ARTIFACTS / "supplier_network_exploratory_action_protocol_20260903_v5"),
                "--stock-calibration-audit-dir",
                str(ARTIFACTS / "supplier_stock_signal_calibration_audit_20260903_v2"),
                "--output-dir",
                str(DELIVERY),
            ),
        )
        run_step(
            "validating_three_view_delivery",
            (
                "-m",
                "etudecas.prototypes.scan_2027_risk_control.build_industrial_supply_preliminary_delivery",
                "--validate-only",
                "--output-dir",
                str(DELIVERY),
            ),
        )
        run_step(
            "validating_dynamic_protocol",
            (
                "-m",
                "etudecas.prototypes.scan_2027_risk_control.supplier_dynamic_requirement_reference_runner",
                "--mode",
                "validate",
                "--protocol-dir",
                str(PROTOCOL),
            ),
        )
        run_step(
            "running_dynamic_smoke_three_seeds",
            (
                "-m",
                "etudecas.prototypes.scan_2027_risk_control.supplier_dynamic_requirement_reference_runner",
                "--mode",
                "smoke",
                "--protocol-dir",
                str(PROTOCOL),
                "--active-campaign-dir",
                str(CAMPAIGN),
                "--output-dir",
                str(SMOKE),
                "--workers",
                "2",
            ),
        )
        smoke_manifest = read_json(SMOKE / "comparison_runner_manifest.json")
        if (
            smoke_manifest.get("status") != "smoke_complete_nonreusable"
            or smoke_manifest.get("completed_engine_run_count") != 6
            or smoke_manifest.get("publishable_results") is not False
        ):
            raise RuntimeError("Le petit comparatif dynamique n'a pas son état final attendu")
        write_status(
            "complete",
            campaign_evidence_count=EXPECTED_CHECKPOINT_EVIDENCE,
            preliminary_dir=str(PRELIMINARY),
            delivery_entry=str(DELIVERY / "OUVRIR_PRELIMINAIRE_15_SUR_30.html"),
            dynamic_smoke_dir=str(SMOKE),
        )
        log("Relais terminé avec succès")
        return 0
    except Exception as exc:
        log("FAILED " + "".join(traceback.format_exception(exc)))
        write_status(
            "failed",
            error_type=type(exc).__name__,
            error=str(exc),
            campaign_evidence_count=ledger_count(),
        )
        return 1
    finally:
        prevent_sleep(False)


if __name__ == "__main__":
    raise SystemExit(main())
