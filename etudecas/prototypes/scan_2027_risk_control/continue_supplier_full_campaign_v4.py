#!/usr/bin/env python3
"""Resume the complete, additive V4 supplier campaign after calibration.

This process-level relay contains no simulation logic.  It waits for the
official V4 calibration relay, validates every hand-off, and invokes the
already separated V4 command-line tools in their scientific order.  It is
restartable, records every command and refuses to continue from a rejected or
structurally inconsistent artifact.

The relay deliberately never introduces quality, availability, capacity or
stock incidents.  It also never executes the 90 operating-point holdout cases:
the validated bridge imports their signed compact traces.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, MutableMapping, Sequence


MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v4"
)
SCHEMA_VERSION = "etudecas.supplier_full_campaign_relay.v4"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservations.v1"
RECOVERY_INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.recovery_inventory.v1"

CALIBRATION_RELAY_SCHEMA = "etudecas.v4_calibration_relay.status.v1"
CALIBRATION_ACCEPTED_STAGE = "calibration_accepted"
CALIBRATION_HOLDOUT_STATUS = "holdout_validated_30_fresh_seeds"

EXPECTED_STATE_IDS = ("op_100", "op_93", "op_80")
EXPECTED_MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
EXPECTED_HOLDOUT_CASES = 90
EXPECTED_DISCOVERY_RUNS = 3
EXPECTED_SMOKE_ROWS = 3
EXPECTED_SHARDS = 18
EXPECTED_CAMPAIGN_ROWS = 3_330
EXPECTED_REPETITIONS = 30
MAX_LOT_DOSSIERS = 3

BRIDGE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v4"
)
SIDECAR_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v4"
)
AGGREGATOR_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_aggregator_v4"
)
CAMPAIGN_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v4"
)
LAUNCHER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v4"
)
FINALIZER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "finalize_supplier_operating_point_full_campaign_v4"
)
DASHBOARD_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v4_dashboard"
)
LOT_REPLAY_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_priority_lot_replay_v4"
)
FINAL_DELIVERY_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_v4_final_standalone_delivery"
)
ACTION_REPLAY_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_priority_action_replay_v4"
)

PINNED_MODULES = (
    BRIDGE_MODULE,
    SIDECAR_MODULE,
    AGGREGATOR_MODULE,
    CAMPAIGN_MODULE,
    LAUNCHER_MODULE,
    FINALIZER_MODULE,
    DASHBOARD_MODULE,
    LOT_REPLAY_MODULE,
)

TERMINAL_CALIBRATION_NO_GO = {
    "scientific_no_go_after_development",
    "scientific_no_go_after_holdout",
}
TERMINAL_FAILURE_STAGES = {"failed"}
RUNNING_LAUNCH_STATUSES = {
    "running",
    "running_target_discovery",
    "running_smoke",
    "failed_draining",
}

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102


class FullCampaignRelayError(RuntimeError):
    """The relay cannot continue without weakening an evidence contract."""


class ScientificNoGo(FullCampaignRelayError):
    """The frozen operating-point calibration was scientifically rejected."""


class RelayTimeout(FullCampaignRelayError):
    """A required upstream artifact did not become ready in time."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FullCampaignRelayError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise FullCampaignRelayError(f"Objet JSON attendu : {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _verify_signed_json(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise FullCampaignRelayError(f"Signature absente ou invalide : {label}")
    if signature != stable_sha256(unsigned):
        raise FullCampaignRelayError(f"Signature incohérente : {label}")
    return signature


def _module_path(repo: Path, module: str) -> Path:
    return repo / (module.replace(".", os.sep) + ".py")


def _module_inventory(
    repo: Path, *, include_delivery: bool, include_actions: bool = False
) -> list[dict[str, Any]]:
    modules = [*PINNED_MODULES, MODULE_NAME]
    if include_delivery:
        modules.append(FINAL_DELIVERY_MODULE)
    if include_actions:
        modules.append(ACTION_REPLAY_MODULE)
    rows: list[dict[str, Any]] = []
    for module in modules:
        path = _module_path(repo, module).resolve()
        if not path.is_file():
            raise FullCampaignRelayError(
                f"Module requis absent avant démarrage : {module} ({path})"
            )
        rows.append({"module": module, "path": str(path), "sha256": sha256_file(path)})
    return rows


def _legacy_html_inventory(config: "RelayConfig") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, path in (
        ("legacy_risk_html", config.legacy_risk_html),
        ("legacy_control_html", config.legacy_control_html),
    ):
        if path is None:
            continue
        resolved = path.resolve()
        if not resolved.is_file():
            raise FullCampaignRelayError(f"Ancien HTML optionnel absent : {resolved}")
        rows.append(
            {
                "role": role,
                "path": str(resolved),
                "size_bytes": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
            }
        )
    return rows


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _process_running(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if os.name != "nt":  # pragma: no cover - production host is Windows.
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    kernel32.WaitForSingleObject.restype = ctypes.c_ulong
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, process_id)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel32.CloseHandle(handle)


def _prevent_sleep(enabled: bool) -> None:
    if os.name != "nt":  # pragma: no cover - production host is Windows.
        return
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enabled else 0)
    if not ctypes.windll.kernel32.SetThreadExecutionState(flags):
        raise OSError("SetThreadExecutionState failed")


@dataclass(frozen=True)
class RelayConfig:
    repo: Path
    calibration_plan_dir: Path
    calibration_run_dir: Path
    calibration_supervision_dir: Path
    sidecar_dir: Path
    bridge_json: Path
    campaign_root: Path
    results_dir: Path
    lot_replay_root: Path
    dashboard_html: Path
    final_html: Path | None
    supervision_dir: Path
    action_replay_root: Path | None = None
    legacy_risk_html: Path | None = None
    legacy_control_html: Path | None = None
    action_replay_mode: str = "auto"
    sidecar_watcher_pid: int = 0
    parallel_shards: int = 2
    workers_per_shard: int = 2
    launcher_poll_seconds: float = 5.0
    relay_poll_seconds: float = 30.0
    max_wait_hours: float = 120.0

    def resolved(self) -> "RelayConfig":
        def resolve_optional(path: Path | None) -> Path | None:
            return path.resolve() if path is not None else None

        return RelayConfig(
            repo=self.repo.resolve(),
            calibration_plan_dir=self.calibration_plan_dir.resolve(),
            calibration_run_dir=self.calibration_run_dir.resolve(),
            calibration_supervision_dir=self.calibration_supervision_dir.resolve(),
            sidecar_dir=self.sidecar_dir.resolve(),
            bridge_json=self.bridge_json.resolve(),
            campaign_root=self.campaign_root.resolve(),
            results_dir=self.results_dir.resolve(),
            lot_replay_root=self.lot_replay_root.resolve(),
            dashboard_html=self.dashboard_html.resolve(),
            final_html=resolve_optional(self.final_html),
            supervision_dir=self.supervision_dir.resolve(),
            action_replay_root=resolve_optional(self.action_replay_root),
            legacy_risk_html=resolve_optional(self.legacy_risk_html),
            legacy_control_html=resolve_optional(self.legacy_control_html),
            action_replay_mode=self.action_replay_mode,
            sidecar_watcher_pid=self.sidecar_watcher_pid,
            parallel_shards=self.parallel_shards,
            workers_per_shard=self.workers_per_shard,
            launcher_poll_seconds=self.launcher_poll_seconds,
            relay_poll_seconds=self.relay_poll_seconds,
            max_wait_hours=self.max_wait_hours,
        )

    def validate(self) -> None:
        if not self.repo.is_dir():
            raise FullCampaignRelayError(f"Dépôt absent : {self.repo}")
        for label, path in (
            ("plan de calibration", self.calibration_plan_dir),
            ("exécution de calibration", self.calibration_run_dir),
            ("supervision de calibration", self.calibration_supervision_dir),
        ):
            if not path.is_dir():
                raise FullCampaignRelayError(f"Dossier {label} absent : {path}")
        if self.sidecar_dir.exists() and not self.sidecar_dir.is_dir():
            raise FullCampaignRelayError(
                f"Le chemin de capture sidecar n'est pas un dossier : {self.sidecar_dir}"
            )
        if self.parallel_shards not in (1, 2):
            raise FullCampaignRelayError("parallel_shards doit valoir 1 ou 2")
        if self.workers_per_shard not in (1, 2):
            raise FullCampaignRelayError("workers_per_shard doit valoir 1 ou 2")
        if not 0.0 <= self.launcher_poll_seconds <= 60.0:
            raise FullCampaignRelayError("launcher_poll_seconds doit être dans [0, 60]")
        if not 0.1 <= self.relay_poll_seconds <= 60.0:
            raise FullCampaignRelayError("relay_poll_seconds doit être dans [0.1, 60]")
        if self.max_wait_hours <= 0:
            raise FullCampaignRelayError("max_wait_hours doit être strictement positif")
        if self.action_replay_mode not in {"off", "auto", "required"}:
            raise FullCampaignRelayError(
                "action_replay_mode doit valoir off, auto ou required"
            )
        if self.action_replay_mode == "required" and self.action_replay_root is None:
            raise FullCampaignRelayError(
                "--action-replay-root est obligatoire en mode actions required"
            )
        if (
            self.action_replay_mode == "required"
            and not _module_path(self.repo, ACTION_REPLAY_MODULE).is_file()
        ):
            raise FullCampaignRelayError(
                "Le module actions obligatoire est absent avant démarrage"
            )
        if self.action_replay_mode == "off" and self.action_replay_root is not None:
            raise FullCampaignRelayError(
                "Une racine actions ne doit pas être fournie quand la phase est off"
            )
        if self.sidecar_watcher_pid < 0:
            raise FullCampaignRelayError("sidecar_watcher_pid ne peut pas être négatif")

        immutable_roots = (
            self.calibration_plan_dir,
            self.calibration_run_dir,
            self.calibration_supervision_dir,
            self.sidecar_dir,
            self.repo,
        )
        write_targets = (
            self.bridge_json,
            self.campaign_root,
            self.results_dir,
            self.lot_replay_root,
            self.dashboard_html,
            self.final_html,
            self.supervision_dir,
            self.action_replay_root,
        )
        concrete_targets = [path for path in write_targets if path is not None]
        if len(set(concrete_targets)) != len(concrete_targets):
            raise FullCampaignRelayError(
                "Deux sorties du relais désignent le même chemin"
            )
        for target in concrete_targets:
            for protected in immutable_roots[:-1]:
                if target == protected or _is_relative_to(target, protected):
                    raise FullCampaignRelayError(
                        f"Une sortie empiète sur une preuve amont protégée : {target}"
                    )
        output_directories = (
            self.campaign_root,
            self.results_dir,
            self.lot_replay_root,
            self.supervision_dir,
            *(() if self.action_replay_root is None else (self.action_replay_root,)),
        )
        for index, left in enumerate(output_directories):
            for right in output_directories[index + 1 :]:
                if _is_relative_to(left, right) or _is_relative_to(right, left):
                    raise FullCampaignRelayError(
                        "Les racines campagne/résultats/rejeux/supervision doivent "
                        "être séparées"
                    )
        for output_file in (
            self.bridge_json,
            self.dashboard_html,
            self.final_html,
        ):
            if output_file is None:
                continue
            protected_packages = (
                self.campaign_root,
                self.results_dir,
                self.lot_replay_root,
                *(
                    ()
                    if self.action_replay_root is None
                    else (self.action_replay_root,)
                ),
            )
            for output_directory in protected_packages:
                if _is_relative_to(output_file, output_directory):
                    raise FullCampaignRelayError(
                        "Les HTML et le pont ne doivent pas modifier un paquet de "
                        f"preuves : {output_file}"
                    )
        for source in (self.legacy_risk_html, self.legacy_control_html):
            if source is not None and not source.is_file():
                raise FullCampaignRelayError(f"Ancien HTML optionnel absent : {source}")

    def public_mapping(self) -> dict[str, Any]:
        return {
            "repo": str(self.repo),
            "calibration_plan_dir": str(self.calibration_plan_dir),
            "calibration_run_dir": str(self.calibration_run_dir),
            "calibration_supervision_dir": str(self.calibration_supervision_dir),
            "sidecar_dir": str(self.sidecar_dir),
            "bridge_json": str(self.bridge_json),
            "campaign_root": str(self.campaign_root),
            "results_dir": str(self.results_dir),
            "lot_replay_root": str(self.lot_replay_root),
            "dashboard_html": str(self.dashboard_html),
            "final_html": str(self.final_html) if self.final_html else "",
            "supervision_dir": str(self.supervision_dir),
            "action_replay_root": (
                str(self.action_replay_root) if self.action_replay_root else ""
            ),
            "legacy_risk_html": (
                str(self.legacy_risk_html) if self.legacy_risk_html else ""
            ),
            "legacy_control_html": (
                str(self.legacy_control_html) if self.legacy_control_html else ""
            ),
            "action_replay_mode": self.action_replay_mode,
            "sidecar_watcher_pid": self.sidecar_watcher_pid,
            "parallel_shards": self.parallel_shards,
            "workers_per_shard": self.workers_per_shard,
            "launcher_poll_seconds": self.launcher_poll_seconds,
            "relay_poll_seconds": self.relay_poll_seconds,
            "max_wait_hours": self.max_wait_hours,
        }


CommandExecutor = Callable[[Sequence[str], Path, Path], int]
CompletionCheck = Callable[[], bool]
ProgressReader = Callable[[], Mapping[str, Any]]


class FullCampaignRelay:
    """Strict, sequential process orchestrator with crash checkpoints."""

    def __init__(
        self,
        config: RelayConfig,
        *,
        command_executor: CommandExecutor | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config.resolved()
        self.command_executor = command_executor
        self.sleep = sleep
        self.monotonic = monotonic
        self.status_path = self.config.supervision_dir / "status.json"
        self.contract_path = self.config.supervision_dir / "relay_contract.json"
        self.reservations_path = self.config.supervision_dir / "reservations.json"
        self.log_dir = self.config.supervision_dir / "logs"
        self.status: dict[str, Any] = {}
        self.contract: dict[str, Any] = {}

    def _build_contract(self) -> dict[str, Any]:
        unsigned: dict[str, Any] = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "configuration": self.config.public_mapping(),
            "source_inventory": _module_inventory(
                self.config.repo,
                include_delivery=self.config.final_html is not None,
                include_actions=(
                    self.config.action_replay_root is not None
                    and self.config.action_replay_mode != "off"
                    and _module_path(self.config.repo, ACTION_REPLAY_MODULE).is_file()
                ),
            ),
            "legacy_html_inventory": _legacy_html_inventory(self.config),
            "scientific_contract": {
                "accepted_holdout_case_count": EXPECTED_HOLDOUT_CASES,
                "operating_point_ids": list(EXPECTED_STATE_IDS),
                "operating_point_holdout_reruns_in_campaign": 0,
                "target_discovery_engine_runs": EXPECTED_DISCOVERY_RUNS,
                "mandatory_non_reusable_op93_smoke_rows": EXPECTED_SMOKE_ROWS,
                "isolated_shard_count": EXPECTED_SHARDS,
                "reported_campaign_row_count": EXPECTED_CAMPAIGN_ROWS,
                "paired_repetitions_per_cell": EXPECTED_REPETITIONS,
                "supplier_incident_mechanisms": list(EXPECTED_MECHANISMS),
                "quality_incident_included": False,
                "availability_incident_included": False,
                "capacity_incident_included": False,
                "stock_incident_included": False,
                "historical_incident_probability_estimated": False,
                "maximum_signed_lot_replays": MAX_LOT_DOSSIERS,
                "forced_top_three": False,
            },
            "execution_contract": {
                "shell": False,
                "old_results_overwritten": False,
                "resume_from_signed_artifacts": True,
                "one_foreground_child_step_at_a_time": True,
                "launcher_owns_discovery_smoke_and_shards": True,
            },
        }
        return {**unsigned, "contract_signature": stable_sha256(unsigned)}

    def prepare(self) -> None:
        self.config.validate()
        self.config.supervision_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        expected = self._build_contract()
        if self.contract_path.is_file():
            actual = _read_json(self.contract_path)
            _verify_signed_json(actual, "contract_signature", "contrat du relais")
            if actual != expected:
                raise FullCampaignRelayError(
                    "Le contrat existant diffère (chemins, options ou code source); "
                    "refus de mélanger deux campagnes"
                )
            self.contract = actual
        else:
            if any(
                path.name not in {"logs", ".relay.lock"}
                for path in self.config.supervision_dir.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Dossier de supervision non enregistré et non vide"
                )
            self.contract = expected
            _atomic_json(self.contract_path, expected)
        self._load_or_create_status()
        self._reserve_outputs()

    def _load_or_create_status(self) -> None:
        contract_signature = self.contract["contract_signature"]
        if self.status_path.is_file():
            payload = _read_json(self.status_path)
            _verify_signed_json(payload, "status_signature", "statut du relais")
            if (
                payload.get("schema_version") != STATUS_SCHEMA_VERSION
                or payload.get("contract_signature") != contract_signature
            ):
                raise FullCampaignRelayError("Statut existant étranger au contrat")
            self.status = payload
            return
        self.status = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "contract_signature": contract_signature,
            "status": "running",
            "stage": "initialisation",
            "message_fr": "Le relais vérifie les preuves amont.",
            "relay_pid": os.getpid(),
            "started_at_utc": _now(),
            "updated_at_utc": _now(),
            "completed_at_utc": "",
            "active_command": {},
            "steps": {},
            "artifacts": {},
            "scientific_guardrails": self.contract["scientific_contract"],
        }
        self._write_status()

    def _write_status(self) -> None:
        self.status["relay_pid"] = os.getpid()
        self.status["updated_at_utc"] = _now()
        unsigned = dict(self.status)
        unsigned.pop("status_signature", None)
        payload = {**unsigned, "status_signature": stable_sha256(unsigned)}
        self.status = payload
        _atomic_json(self.status_path, payload)

    def update_status(
        self,
        stage: str,
        message_fr: str,
        *,
        status: str = "running",
        progress: Mapping[str, Any] | None = None,
    ) -> None:
        self.status.update({"status": status, "stage": stage, "message_fr": message_fr})
        if progress is not None:
            self.status["progress"] = dict(progress)
        self._write_status()

    def _reserve_outputs(self) -> None:
        unsigned = {
            "schema_version": RESERVATION_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "paths": {
                "bridge_json": str(self.config.bridge_json),
                "campaign_root": str(self.config.campaign_root),
                "results_dir": str(self.config.results_dir),
                "lot_replay_root": str(self.config.lot_replay_root),
                "dashboard_html": str(self.config.dashboard_html),
                "final_html": str(self.config.final_html or ""),
                "action_replay_root": str(self.config.action_replay_root or ""),
            },
        }
        expected = {**unsigned, "reservation_signature": stable_sha256(unsigned)}
        if self.reservations_path.is_file():
            actual = _read_json(self.reservations_path)
            _verify_signed_json(
                actual, "reservation_signature", "réservation des sorties"
            )
            if actual != expected:
                raise FullCampaignRelayError("Réservation des sorties incohérente")
        else:
            _atomic_json(self.reservations_path, expected)

    def observe_sidecar_watcher(self) -> None:
        """Record the external curve watcher without owning or restarting it.

        The official watcher is intentionally a distinct process: it may have
        started before this relay and it must never be duplicated here.  Its
        health is informative for the optional curve product only and cannot
        prevent the incident campaign from starting after holdout acceptance.
        """

        process_id = self.config.sidecar_watcher_pid
        inventory_path = self.config.sidecar_dir / "capture_inventory.json"
        running = False
        process_check_error = ""
        if process_id > 0 and not inventory_path.is_file():
            try:
                running = _process_running(process_id)
            except Exception as exc:  # pragma: no cover - defensive OS boundary.
                process_check_error = f"{type(exc).__name__}: {exc}"
        if inventory_path.is_file():
            watcher_status = "inventory_present_pending_validation"
        elif process_id <= 0:
            watcher_status = "not_registered"
        elif running:
            watcher_status = "watching"
        else:
            watcher_status = "not_running_before_inventory"
        self.status["sidecar_watcher"] = {
            "status": watcher_status,
            "pid": process_id,
            "process_running": running,
            "inventory_path": str(inventory_path),
            "inventory_present": inventory_path.is_file(),
            "process_check_error": process_check_error,
            "owned_or_restarted_by_relay": False,
            "incident_campaign_blocked": False,
            "observed_at_utc": _now(),
        }
        self._write_status()

    def _record_artifact(self, label: str, path: Path) -> None:
        resolved = path.resolve()
        entry: dict[str, Any] = {"path": str(resolved)}
        if resolved.is_file():
            entry.update(
                {
                    "type": "file",
                    "size_bytes": resolved.stat().st_size,
                    "sha256": sha256_file(resolved),
                }
            )
        elif resolved.is_dir():
            entry["type"] = "directory"
        else:
            raise FullCampaignRelayError(f"Artefact annoncé mais absent : {resolved}")
        self.status.setdefault("artifacts", {})[label] = entry
        self._write_status()

    def _validate_legacy_html_inventory(self) -> None:
        expected = self.contract.get("legacy_html_inventory")
        if expected != _legacy_html_inventory(self.config):
            raise FullCampaignRelayError(
                "Un ancien HTML lié comme archive a changé depuis le démarrage"
            )

    def _step_entry(self, step: str) -> MutableMapping[str, Any]:
        steps = self.status.setdefault("steps", {})
        value = steps.setdefault(step, {"attempts": []})
        if not isinstance(value, MutableMapping):
            raise FullCampaignRelayError("Historique d'étape invalide")
        return value

    def _step_was_attempted(self, step: str) -> bool:
        entry = (self.status.get("steps") or {}).get(step)
        return isinstance(entry, Mapping) and bool(entry.get("attempts"))

    def _step_child_running(self, step: str) -> bool:
        active = self.status.get("active_command") or {}
        if not isinstance(active, Mapping) or active.get("step") != step:
            return False
        return _process_running(int(active.get("pid") or 0))

    def _wait_for_existing_child(
        self,
        *,
        step: str,
        command_sha256: str,
        progress_reader: ProgressReader | None,
    ) -> None:
        active = self.status.get("active_command")
        if not isinstance(active, Mapping) or not active:
            return
        pid = int(active.get("pid") or 0)
        if active.get("step") != step or active.get("command_sha256") != command_sha256:
            if _process_running(pid):
                raise FullCampaignRelayError(
                    "Un autre sous-processus enregistré est encore actif"
                )
            self.status["active_command"] = {}
            self._write_status()
            return
        if not _process_running(pid):
            self.status["active_command"] = {}
            self._write_status()
            return
        started = self.monotonic()
        while _process_running(pid):
            if self.monotonic() - started > self.config.max_wait_hours * 3600:
                raise RelayTimeout(
                    f"Sous-processus toujours actif : {step} / PID {pid}"
                )
            progress = dict(progress_reader() if progress_reader else {})
            progress.update({"existing_child_pid": pid})
            self.update_status(
                f"attente_{step}",
                "Une commande déjà lancée continue; le relais attend sa fin sans la dupliquer.",
                progress=progress,
            )
            self.sleep(self.config.relay_poll_seconds)
        self.status["active_command"] = {}
        self._write_status()

    def run_step(
        self,
        *,
        step: str,
        command: Sequence[str],
        completion_check: CompletionCheck,
        message_fr: str,
        progress_reader: ProgressReader | None = None,
        run_even_if_complete: bool = False,
    ) -> None:
        command_list = [str(value) for value in command]
        command_digest = stable_sha256(command_list)
        entry = self._step_entry(step)
        try:
            if completion_check() and not run_even_if_complete:
                entry.update(
                    {
                        "status": "validated_reuse",
                        "command": command_list,
                        "command_sha256": command_digest,
                        "validated_at_utc": _now(),
                    }
                )
                self._write_status()
                return
        except FileNotFoundError:
            pass
        self._wait_for_existing_child(
            step=step,
            command_sha256=command_digest,
            progress_reader=progress_reader,
        )
        if completion_check() and not run_even_if_complete:
            entry.update(
                {
                    "status": "validated_after_existing_child",
                    "command": command_list,
                    "command_sha256": command_digest,
                    "validated_at_utc": _now(),
                }
            )
            self._write_status()
            return

        log_path = self.log_dir / f"{step}.log"
        attempt: dict[str, Any] = {
            "started_at_utc": _now(),
            "command": command_list,
            "command_sha256": command_digest,
            "log_path": str(log_path),
        }
        attempts = entry.setdefault("attempts", [])
        if not isinstance(attempts, list):
            raise FullCampaignRelayError("Historique de commandes invalide")
        attempts.append(attempt)
        entry.update(
            {
                "status": "running",
                "command": command_list,
                "command_sha256": command_digest,
                "log_path": str(log_path),
            }
        )
        self.update_status(step, message_fr)

        if self.command_executor is not None:
            return_code = int(
                self.command_executor(command_list, self.config.repo, log_path)
            )
            pid = 0
        else:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as stream:
                stream.write(
                    (
                        f"\n[{_now()}] START "
                        + json.dumps(command_list, ensure_ascii=False)
                        + "\n"
                    ).encode("utf-8")
                )
                stream.flush()
                process = subprocess.Popen(
                    command_list,
                    cwd=self.config.repo,
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
                pid = process.pid
                self.status["active_command"] = {
                    "step": step,
                    "pid": pid,
                    "command": command_list,
                    "command_sha256": command_digest,
                    "log_path": str(log_path),
                    "started_at_utc": attempt["started_at_utc"],
                }
                self._write_status()
                try:
                    while True:
                        return_code = process.poll()
                        if return_code is not None:
                            break
                        progress = dict(progress_reader() if progress_reader else {})
                        progress.update({"child_pid": pid})
                        self.update_status(step, message_fr, progress=progress)
                        self.sleep(self.config.relay_poll_seconds)
                except KeyboardInterrupt:
                    entry["status"] = "interrupted_child_left_running"
                    self.update_status(
                        step,
                        "Le relais a été interrompu; la commande enfant reste suivie dans status.json.",
                        status="interrupted",
                    )
                    raise
                finally:
                    stream.flush()

        attempt.update(
            {
                "finished_at_utc": _now(),
                "return_code": return_code,
                "pid": pid,
            }
        )
        self.status["active_command"] = {}
        if return_code != 0:
            entry["status"] = "failed"
            self._write_status()
            raise FullCampaignRelayError(
                f"Commande en échec ({return_code}) : {step}; voir {log_path}"
            )
        if not completion_check():
            entry["status"] = "failed_validation"
            self._write_status()
            raise FullCampaignRelayError(
                f"La commande {step} s'est terminée sans preuve finale valide"
            )
        entry.update({"status": "complete_validated", "completed_at_utc": _now()})
        self._write_status()

    def _python_module(self, module: str, *arguments: str) -> list[str]:
        return [sys.executable, "-m", module, *arguments]

    def wait_for_calibration(self) -> dict[str, Any]:
        status_path = self.config.calibration_supervision_dir / "status.json"
        result_path = self.config.calibration_run_dir / "holdout_result.json"
        started = self.monotonic()
        while True:
            upstream_progress: dict[str, Any] = {}
            if status_path.is_file():
                status = _read_json(status_path)
                if status.get("schema_version") != CALIBRATION_RELAY_SCHEMA:
                    raise FullCampaignRelayError(
                        "Le statut de calibration n'est pas celui du relais V4 officiel"
                    )
                stage = str(status.get("stage") or "")
                if stage in TERMINAL_CALIBRATION_NO_GO:
                    raise ScientificNoGo(
                        "Les trois points de fonctionnement n'ont pas passé la validation "
                        f"figée ({stage}); aucune campagne incident n'est lancée"
                    )
                if stage in TERMINAL_FAILURE_STAGES:
                    raise FullCampaignRelayError(
                        "Le relais de calibration officiel s'est terminé en échec"
                    )
                if stage == CALIBRATION_ACCEPTED_STAGE:
                    if status.get("accepted") is not True:
                        raise FullCampaignRelayError(
                            "Le statut final de calibration n'atteste pas accepted=true"
                        )
                    if not result_path.is_file():
                        raise FullCampaignRelayError(
                            "Le résultat holdout accepté annoncé est absent"
                        )
                    result = _read_json(result_path)
                    if (
                        result.get("accepted") is not True
                        or result.get("status") != CALIBRATION_HOLDOUT_STATUS
                    ):
                        raise FullCampaignRelayError(
                            "Le résultat holdout ne confirme pas les 30 graines fraîches"
                        )
                    summaries = result.get("state_summaries")
                    if not isinstance(summaries, Mapping) or set(summaries) != set(
                        EXPECTED_STATE_IDS
                    ):
                        raise FullCampaignRelayError(
                            "Le holdout accepté ne contient pas exactement les trois états"
                        )
                    self.update_status(
                        "calibration_validée",
                        "Les trois états ont passé le holdout officiel de 30 simulations.",
                        progress={"states": 3, "holdout_cases": 90},
                    )
                    self._record_artifact("calibration_holdout", result_path)
                    return result
                upstream_progress = {
                    "calibration_stage": stage,
                    "development_completed_cases": status.get(
                        "development_completed_case_count"
                    ),
                    "development_expected_cases": status.get(
                        "development_expected_case_count"
                    ),
                }
            elapsed = self.monotonic() - started
            if elapsed > self.config.max_wait_hours * 3600:
                raise RelayTimeout("Délai dépassé en attente de la calibration V4")
            self.update_status(
                "attente_calibration",
                "La calibration officielle continue; aucune simulation incident n'est lancée.",
                progress={
                    "elapsed_seconds": round(elapsed, 1),
                    **upstream_progress,
                },
            )
            self.sleep(self.config.relay_poll_seconds)

    def _sidecar_inventory_ready(self) -> bool:
        path = self.config.sidecar_dir / "capture_inventory.json"
        if not path.is_file():
            return False
        payload = _read_json(path)
        _verify_signed_json(payload, "inventory_signature", "inventaire sidecar")
        if (
            payload.get("status") != "complete"
            or int(payload.get("case_count") or -1) != EXPECTED_HOLDOUT_CASES
        ):
            raise FullCampaignRelayError("Inventaire sidecar final incohérent")
        cases = payload.get("cases")
        if not isinstance(cases, list) or len(cases) != EXPECTED_HOLDOUT_CASES:
            raise FullCampaignRelayError(
                "Les 90 captures nominales ne sont pas prouvées"
            )
        return True

    def wait_for_sidecar_inventory(self) -> None:
        started = self.monotonic()
        progress_path = self.config.sidecar_dir / "capture_progress.json"
        while not self._sidecar_inventory_ready():
            elapsed = self.monotonic() - started
            if elapsed > self.config.max_wait_hours * 3600:
                raise RelayTimeout("Délai dépassé en attente des courbes nominales")
            progress: dict[str, Any] = {"elapsed_seconds": round(elapsed, 1)}
            if progress_path.is_file():
                source = _read_json(progress_path)
                progress.update(
                    {
                        "captured_cases": source.get("completed_cases"),
                        "expected_cases": source.get("expected_cases"),
                    }
                )
            self.update_status(
                "attente_courbes_nominales",
                "Le relais attend la copie sûre des courbes des 90 simulations déjà exécutées.",
                progress=progress,
            )
            self.sleep(self.config.relay_poll_seconds)
        self._record_artifact(
            "sidecar_inventory", self.config.sidecar_dir / "capture_inventory.json"
        )

    def validate_and_aggregate_curves(self) -> None:
        self.run_step(
            step="validation_sidecar",
            command=self._python_module(
                SIDECAR_MODULE, "finalize", "--output-dir", str(self.config.sidecar_dir)
            ),
            completion_check=self._sidecar_inventory_ready,
            message_fr="Validation fichier par fichier des courbes nominales capturées.",
            run_even_if_complete=True,
        )
        aggregate_manifest = (
            self.config.sidecar_dir / "curve_aggregates_v1" / "aggregate_manifest.json"
        )

        def aggregate_ready() -> bool:
            if not aggregate_manifest.is_file():
                return False
            payload = _read_json(aggregate_manifest)
            _verify_signed_json(payload, "manifest_signature", "agrégats de courbes")
            return (
                payload.get("status") == "complete"
                and int(payload.get("case_count") or -1) == EXPECTED_HOLDOUT_CASES
                and int(payload.get("state_count") or -1) == len(EXPECTED_STATE_IDS)
                and len(payload.get("files") or []) == 4
            )

        self.run_step(
            step="agrégation_courbes_nominales",
            command=self._python_module(
                AGGREGATOR_MODULE,
                "aggregate",
                "--output-dir",
                str(self.config.sidecar_dir),
            ),
            completion_check=aggregate_ready,
            message_fr="Calcul des courbes descriptives compactes par état simulé.",
        )
        # The validator reopens every aggregate and every registered capture.
        self.run_step(
            step="validation_agrégats_courbes",
            command=self._python_module(
                AGGREGATOR_MODULE,
                "validate",
                "--output-dir",
                str(self.config.sidecar_dir),
            ),
            completion_check=aggregate_ready,
            message_fr="Contrôle final des courbes compactes et de leur inventaire.",
            run_even_if_complete=True,
        )
        self._record_artifact("nominal_curve_aggregates", aggregate_manifest)

    def _bridge_ready(self) -> bool:
        if not self.config.bridge_json.is_file():
            return False
        payload = _read_json(self.config.bridge_json)
        if payload.get("status") != "accepted_v4_operating_points":
            # Keep the exact producer as the authoritative validator; tolerate a
            # future spelling only when the structural safety fields remain exact.
            if not str(payload.get("status") or "").startswith("accepted"):
                raise FullCampaignRelayError("Le pont V4 existant n'est pas accepté")
        if (
            payload.get("quality_branch_included") is not False
            or payload.get("supplier_state_dependent_risks_enabled") is not False
            or payload.get("acute_incident_included_in_operating_point") is not False
            or payload.get("retuning_after_holdout") is not False
        ):
            raise FullCampaignRelayError("Le pont V4 enfreint les garde-fous incidents")
        points = payload.get("operating_points")
        traces = payload.get("trace_index")
        if (
            not isinstance(points, list)
            or [row.get("operating_point_id") for row in points]
            != list(EXPECTED_STATE_IDS)
            or not isinstance(traces, list)
            or len(traces) != EXPECTED_HOLDOUT_CASES
        ):
            raise FullCampaignRelayError("Pont V4 incomplet (3 états / 90 traces)")
        return True

    def build_and_validate_bridge(self) -> None:
        self.run_step(
            step="construction_pont_v4",
            command=self._python_module(
                BRIDGE_MODULE,
                "build",
                "--plan-dir",
                str(self.config.calibration_plan_dir),
                "--run-dir",
                str(self.config.calibration_run_dir),
                "--output",
                str(self.config.bridge_json),
            ),
            completion_check=self._bridge_ready,
            message_fr="Référencement signé des trois états et des 90 traces, sans recalcul.",
        )
        self.run_step(
            step="validation_pont_v4",
            command=self._python_module(
                BRIDGE_MODULE, "validate", "--path", str(self.config.bridge_json)
            ),
            completion_check=self._bridge_ready,
            message_fr="Relecture complète du pont V4 et de ses preuves amont.",
            run_even_if_complete=True,
        )
        self._record_artifact(
            "validated_operating_points_bridge", self.config.bridge_json
        )

    def _campaign_plan_ready(self) -> bool:
        manifest_path = self.config.campaign_root / "campaign_manifest.json"
        shard_plan_path = self.config.campaign_root / "shard_plan.csv"
        if not manifest_path.is_file() and not shard_plan_path.is_file():
            if self.config.campaign_root.exists() and any(
                self.config.campaign_root.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Racine campagne non vide mais sans plan V4 enregistré"
                )
            return False
        if not manifest_path.is_file():
            raise FullCampaignRelayError(
                "Plan de blocs présent sans manifeste de campagne V4"
            )
        manifest = _read_json(manifest_path)
        counts = manifest.get("expected_counts")
        if (
            manifest.get("status") not in {"planned", "running", "complete"}
            or not isinstance(counts, Mapping)
            or int(counts.get("auxiliary_discovery_runs") or -1)
            != EXPECTED_DISCOVERY_RUNS
            or int(counts.get("total_rows") or -1) != EXPECTED_CAMPAIGN_ROWS
            or int(counts.get("shard_count") or -1) != EXPECTED_SHARDS
        ):
            raise FullCampaignRelayError("Contrat quantitatif du plan V4 incohérent")
        for field in (
            "quality_branch_included",
            "quality_incident_included",
            "availability_incident_included",
            "capacity_incident_included",
            "stock_incident_included",
            "supplier_state_dependent_risks_enabled",
            "historical_incident_probability_estimated",
        ):
            if manifest.get(field) is not False:
                raise FullCampaignRelayError(f"Le plan V4 doit déclarer {field}=false")
        mechanisms = [row.get("key") for row in manifest.get("mechanisms") or []]
        if mechanisms != list(EXPECTED_MECHANISMS):
            raise FullCampaignRelayError("Les deux mécanismes fournisseurs ont changé")
        if not shard_plan_path.is_file():
            # The planner publishes the manifest before the shard CSV.  A crash
            # in that narrow interval is safely repairable by the idempotent
            # planner because the signed manifest already matches.
            return False
        with shard_plan_path.open("r", encoding="utf-8-sig", newline="") as stream:
            shards = list(csv.DictReader(stream))
        if len(shards) != EXPECTED_SHARDS:
            raise FullCampaignRelayError("Le plan ne contient pas exactement 18 shards")
        return True

    def plan_campaign(self) -> None:
        self.run_step(
            step="planification_campagne",
            command=self._python_module(
                CAMPAIGN_MODULE,
                "--mode",
                "plan",
                "--output-dir",
                str(self.config.campaign_root),
                "--operating-points",
                str(self.config.bridge_json),
            ),
            completion_check=self._campaign_plan_ready,
            message_fr="Création du plan figé : 3 états, 18 voies et 30 répétitions.",
            run_even_if_complete=True,
        )
        self._record_artifact(
            "campaign_manifest", self.config.campaign_root / "campaign_manifest.json"
        )

    def _launch_progress(self) -> dict[str, Any]:
        path = self.config.campaign_root / "launch_progress.json"
        if not path.is_file():
            return {}
        payload = _read_json(path)
        return {
            "launcher_status": payload.get("status"),
            "phase": payload.get("phase"),
            "discovery_status": payload.get("target_discovery_status"),
            "completed_shards": payload.get("completed_shard_count"),
            "planned_shards": payload.get("planned_shard_count"),
            "active_shards": payload.get("active_shard_count"),
            "failed_shards": payload.get("failed_shard_count"),
            "eta_seconds": payload.get("eta_seconds"),
        }

    def _campaign_launch_ready(self) -> bool:
        path = self.config.campaign_root / "launch_progress.json"
        if not path.is_file():
            return False
        payload = _read_json(path)
        status = str(payload.get("status") or "")
        if status in RUNNING_LAUNCH_STATUSES or status.startswith("interrupted"):
            return False
        if status != "complete":
            raise FullCampaignRelayError(
                f"Le lanceur V4 a publié un statut terminal non valide : {status}"
            )
        if (
            payload.get("phase") != "shards"
            or payload.get("target_discovery_status") != "complete"
            or int(payload.get("planned_shard_count") or -1) != EXPECTED_SHARDS
            or int(payload.get("completed_shard_count") or -1) != EXPECTED_SHARDS
            or int(payload.get("failed_shard_count") or -1) != 0
            or int(payload.get("active_shard_count") or -1) != 0
            or int(payload.get("queued_shard_count") or -1) != 0
        ):
            raise FullCampaignRelayError("Progression finale du lanceur V4 incohérente")
        # Reuse the pinned launcher's fail-closed readers. This reopens the
        # three discovery cases, the non-reusable three-case op_93 smoke and
        # every 185-row shard instead of trusting mutable progress counters.
        from etudecas.prototypes.scan_2027_risk_control import (
            launch_supplier_operating_point_full_campaign_v4 as launcher,
        )

        runner = _module_path(self.config.repo, CAMPAIGN_MODULE).resolve()
        manifest, shards = launcher.load_campaign_plan(
            self.config.campaign_root, runner
        )
        expected_contract = launcher._launch_contract(
            manifest=manifest,
            runner=runner,
            shards=shards,
        )
        contract_path = self.config.campaign_root / "launch_contract.json"
        if (
            not contract_path.is_file()
            or _read_json(contract_path) != expected_contract
        ):
            raise FullCampaignRelayError("Contrat signé du lanceur V4 incohérent")
        if (
            payload.get("schema_version") != launcher.PROGRESS_SCHEMA_VERSION
            or payload.get("campaign_signature") != manifest.get("campaign_signature")
            or payload.get("launch_contract_signature")
            != expected_contract.get("launch_contract_signature")
        ):
            raise FullCampaignRelayError("Progression du lanceur non liée au plan")

        discovery_state, discovery_detail = launcher._discovery_completion_state(
            self.config.campaign_root, manifest=manifest
        )
        if discovery_state != "complete":
            raise FullCampaignRelayError(
                "Les trois simulations de choix de fenêtre ne sont pas validées : "
                + discovery_detail
            )
        smoke_state, smoke_detail = launcher._smoke_completion_state(
            self.config.campaign_root, manifest=manifest
        )
        if smoke_state != "complete":
            raise FullCampaignRelayError(
                "Le contrôle obligatoire op_93 de trois cas n'est pas validé : "
                + smoke_detail
            )
        for shard in shards:
            shard_state, shard_detail = launcher._completion_state(
                self.config.campaign_root,
                campaign_signature=str(manifest["campaign_signature"]),
                shard=shard,
            )
            if shard_state != "complete":
                raise FullCampaignRelayError(
                    f"Bloc {shard.shard_id} non validé : {shard_detail}"
                )
        return True

    def _wait_for_orphaned_launcher_children(self) -> None:
        """Wait for shard children left alive by a crashed relay, if any."""

        path = self.config.campaign_root / "launch_progress.json"
        if not path.is_file():
            return
        started = self.monotonic()
        empty_running_observations = 0
        while path.is_file():
            payload = _read_json(path)
            status = str(payload.get("status") or "")
            if status == "complete":
                return
            if status not in RUNNING_LAUNCH_STATUSES and not status.startswith(
                "interrupted"
            ):
                return
            pids: list[int] = []
            discovery_pid = int(payload.get("target_discovery_pid") or 0)
            if discovery_pid > 0:
                pids.append(discovery_pid)
            for row in payload.get("active_shards") or []:
                if isinstance(row, Mapping):
                    pid = int(row.get("pid") or 0)
                    if pid > 0:
                        pids.append(pid)
            running = sorted({pid for pid in pids if _process_running(pid)})
            if not running:
                empty_running_observations += 1
                if empty_running_observations >= 2:
                    return
            else:
                empty_running_observations = 0
            if self.monotonic() - started > self.config.max_wait_hours * 3600:
                raise RelayTimeout(
                    "Délai dépassé en attente des processus de campagne existants"
                )
            progress = self._launch_progress()
            progress["existing_engine_pids"] = running
            self.update_status(
                "attente_processus_campagne_existants",
                (
                    "Des calculs déjà lancés continuent après une reprise; le relais "
                    "les laisse finir avant de relancer le planificateur."
                ),
                progress=progress,
            )
            self.sleep(
                max(
                    self.config.relay_poll_seconds,
                    min(60.0, self.config.launcher_poll_seconds * 2),
                )
            )

    def launch_campaign(self) -> None:
        self._wait_for_orphaned_launcher_children()
        self.run_step(
            step="campagne_incidents",
            command=self._python_module(
                LAUNCHER_MODULE,
                "--campaign-root",
                str(self.config.campaign_root),
                "--parallel-shards",
                str(self.config.parallel_shards),
                "--workers-per-shard",
                str(self.config.workers_per_shard),
                "--poll-seconds",
                str(self.config.launcher_poll_seconds),
            ),
            completion_check=self._campaign_launch_ready,
            message_fr=(
                "Le lanceur exécute successivement 3 essais de choix de fenêtre, "
                "le contrôle op_93 obligatoire, puis les 18 blocs incidents."
            ),
            progress_reader=self._launch_progress,
        )
        self._record_artifact(
            "campaign_launch_progress",
            self.config.campaign_root / "launch_progress.json",
        )

    def _results_ready(self) -> bool:
        validation_path = self.config.results_dir / "campaign_validation.json"
        if not validation_path.is_file():
            if self.config.results_dir.exists() and any(
                self.config.results_dir.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Dossier de résultats non vide sans validation finale"
                )
            return False
        payload = _read_json(validation_path)
        if payload.get("status") != "complete_validated":
            raise FullCampaignRelayError("Résultats V4 non libérés")
        expected = payload.get("expected_contract") or {}
        comparisons = payload.get("comparability_checks") or {}
        evidence = payload.get("signed_case_evidence") or {}
        if (
            int(expected.get("lane_count") or -1) != 18
            or int(expected.get("paired_repetition_count") or -1) != 30
            or expected.get("quality_branch_included") is not False
            or comparisons.get("complete_3x18x2x30_matrix") is not True
            or comparisons.get(
                "all_3330_metrics_reconstructed_from_signed_case_evidence"
            )
            is not True
            or comparisons.get("mandatory_non_reusable_op93_smoke_validated")
            is not True
            or int(evidence.get("case_count") or -1) != EXPECTED_CAMPAIGN_ROWS
        ):
            raise FullCampaignRelayError("Validation finale 3×18×2×30 incomplète")
        lot_plan = self.config.results_dir / "lot_replay_plan.json"
        if not lot_plan.is_file():
            raise FullCampaignRelayError("Sélection signée des rejeux de lots absente")
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_operating_point_full_campaign_v4_dashboard as dashboard,
        )

        # Presentation loader is also the public, exhaustive compact-package
        # validator (declared output hashes, state binding and target registry).
        dashboard.load_dashboard_data(results_dir=self.config.results_dir)
        return True

    def finalize_campaign(self) -> None:
        self.run_step(
            step="consolidation_3330_lignes",
            command=self._python_module(
                FINALIZER_MODULE,
                "--campaign-root",
                str(self.config.campaign_root),
                "--output-dir",
                str(self.config.results_dir),
            ),
            completion_check=self._results_ready,
            message_fr=(
                "Reconstruction des 3 330 preuves, calcul de sensibilité, dispersion "
                "et signaux de priorité fournisseurs."
            ),
        )
        self._record_artifact(
            "campaign_validation", self.config.results_dir / "campaign_validation.json"
        )

    @staticmethod
    def _embedded_dashboard_payload(path: Path) -> dict[str, Any]:
        try:
            document = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise FullCampaignRelayError(f"HTML illisible : {path}") from exc
        match = re.search(
            r'<script id="campaign-data" type="application/json">(.*?)</script>',
            document,
            flags=re.DOTALL,
        )
        if not match:
            raise FullCampaignRelayError("Données embarquées absentes du dashboard")
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise FullCampaignRelayError("Données embarquées invalides") from exc
        if not isinstance(payload, dict):
            raise FullCampaignRelayError("Objet embarqué attendu dans le dashboard")
        if re.search(
            r"<(?:script|link)[^>]+(?:src|href)=[\"']https?://", document, re.I
        ):
            raise FullCampaignRelayError("Le dashboard dépend d'une ressource distante")
        for view_id in ("view-priority", "view-causes", "view-lots"):
            if f'id="{view_id}"' not in document:
                raise FullCampaignRelayError("Le dashboard n'a pas ses trois vues")
        return payload

    def _dashboard_path_ready(self, path: Path) -> bool:
        if not path.is_file():
            return False
        payload = self._embedded_dashboard_payload(path)
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_operating_point_full_campaign_v4_dashboard as dashboard,
        )

        expected_payload = dashboard.load_dashboard_data(
            results_dir=self.config.results_dir
        )
        if (
            int(payload.get("repetitions") or -1) != EXPECTED_REPETITIONS
            or int(payload.get("laneCount") or -1) != 18
            or [row.get("id") for row in payload.get("states") or []]
            != list(EXPECTED_STATE_IDS)
            or [row.get("id") for row in payload.get("mechanisms") or []]
            != list(EXPECTED_MECHANISMS)
        ):
            raise FullCampaignRelayError("Contenu du dashboard V4 incomplet")
        comparable_payload = dict(payload)
        comparable_expected = dict(expected_payload)
        comparable_payload.pop("generatedAtUtc", None)
        comparable_expected.pop("generatedAtUtc", None)
        if comparable_payload != comparable_expected:
            raise FullCampaignRelayError(
                "Le dashboard ne correspond plus aux résultats V4 validés"
            )
        return True

    def _dashboard_ready(self) -> bool:
        return self._dashboard_path_ready(self.config.dashboard_html)

    def build_dashboard(self) -> None:
        if self._dashboard_ready():
            self._record_artifact("campaign_dashboard_html", self.config.dashboard_html)
            return
        candidate = self.config.supervision_dir / "work" / "dashboard_candidate.html"
        if candidate.exists():
            try:
                candidate_valid = self._dashboard_path_ready(candidate)
            except FullCampaignRelayError:
                recovery = self.config.supervision_dir / "recovery"
                recovery.mkdir(parents=True, exist_ok=True)
                preserved = (
                    recovery / f"dashboard_candidate.invalid.{_safe_stamp()}.html"
                )
                candidate.replace(preserved)
                self.status.setdefault("recovery_archives", []).append(
                    {
                        "reason": "dashboard_partiel",
                        "source": str(candidate),
                        "preserved_at": str(preserved),
                    }
                )
                self._write_status()
                candidate_valid = False
            if candidate_valid:
                self.config.dashboard_html.parent.mkdir(parents=True, exist_ok=True)
                if self.config.dashboard_html.exists():
                    raise FullCampaignRelayError(
                        "Le dashboard final est apparu pendant la reprise"
                    )
                os.replace(candidate, self.config.dashboard_html)
                if not self._dashboard_ready():
                    raise FullCampaignRelayError("Dashboard publié non valide")
                self._record_artifact(
                    "campaign_dashboard_html", self.config.dashboard_html
                )
                return
        self.run_step(
            step="dashboard_autonome",
            command=self._python_module(
                DASHBOARD_MODULE,
                "--results-dir",
                str(self.config.results_dir),
                "--output-html",
                str(candidate),
            ),
            completion_check=lambda: self._dashboard_path_ready(candidate),
            message_fr="Création de la synthèse française autonome en trois vues.",
        )
        if self.config.dashboard_html.exists():
            raise FullCampaignRelayError(
                "Refus d'écraser un dashboard apparu pendant sa construction"
            )
        self.config.dashboard_html.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, self.config.dashboard_html)
        if not self._dashboard_ready():
            raise FullCampaignRelayError("Dashboard publié non valide")
        self._record_artifact("campaign_dashboard_html", self.config.dashboard_html)

    def _lot_selection(self) -> list[dict[str, Any]]:
        path = self.config.results_dir / "lot_replay_plan.json"
        payload = _read_json(path)
        if payload.get("status") != "complete_selected":
            raise FullCampaignRelayError("Plan final de sélection des lots non validé")
        _verify_signed_json(payload, "selection_signature", "sélection des lots")
        dossiers = payload.get("selected_dossiers")
        if not isinstance(dossiers, list) or len(dossiers) > MAX_LOT_DOSSIERS:
            raise FullCampaignRelayError("Sélection de rejeux hors limite 0..3")
        if len(
            {
                (
                    row.get("operating_point_id"),
                    row.get("mechanism"),
                    row.get("lane_id"),
                )
                for row in dossiers
                if isinstance(row, Mapping)
            }
        ) != len(dossiers):
            raise FullCampaignRelayError("Sélection de rejeux dupliquée ou mal formée")
        return [dict(row) for row in dossiers]

    def _replay_plan_ready(self, expected_count: int) -> bool:
        path = self.config.lot_replay_root / "replay_plan.json"
        if not path.is_file():
            if self.config.lot_replay_root.exists() and any(
                self.config.lot_replay_root.iterdir()
            ):
                if not self._step_was_attempted("planification_rejeux_lots"):
                    raise FullCampaignRelayError(
                        "Racine de rejeu préexistante non enregistrée; refus de la "
                        "déplacer ou de l'écraser"
                    )
                self._archive_incomplete_replay_root("plan_incomplet")
            return False
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_priority_lot_replay_v4 as replay,
        )

        plan = replay.load_and_validate_plan(self.config.lot_replay_root)
        if len(plan.get("dossiers") or []) != expected_count:
            raise FullCampaignRelayError(
                "Nombre de rejeux différent de la sélection signée"
            )
        return True

    def _archive_incomplete_replay_root(self, reason: str) -> Path:
        root = self.config.lot_replay_root
        if not root.exists():
            raise FullCampaignRelayError("Aucune racine de rejeu à préserver")
        if root == Path(root.anchor) or len(root.parts) < 3:
            raise FullCampaignRelayError("Racine de rejeu trop large pour récupération")
        reservations = _read_json(self.reservations_path)
        if str((reservations.get("paths") or {}).get("lot_replay_root")) != str(root):
            raise FullCampaignRelayError("Racine de rejeu non réservée par ce relais")
        destination = root.with_name(f".{root.name}.{reason}.{_safe_stamp()}")
        suffix = 1
        while destination.exists():
            destination = root.with_name(
                f".{root.name}.{reason}.{_safe_stamp()}.{suffix}"
            )
            suffix += 1
        root.replace(destination)
        self.status.setdefault("recovery_archives", []).append(
            {"reason": reason, "source": str(root), "preserved_at": str(destination)}
        )
        self._write_status()
        return destination

    def _archive_incomplete_action_root(self, reason: str) -> Path:
        """Preserve a relay-owned orphan action tree, with a pre-move inventory."""

        root = self.config.action_replay_root
        if root is None or not root.exists():
            raise FullCampaignRelayError("Aucune racine actions à préserver")
        if root == Path(root.anchor) or len(root.parts) < 3:
            raise FullCampaignRelayError("Racine actions trop large pour récupération")
        if not self._step_was_attempted("planification_actions"):
            raise FullCampaignRelayError(
                "Racine actions préexistante non enregistrée; refus de la déplacer"
            )
        if self._step_child_running("planification_actions"):
            raise FullCampaignRelayError(
                "Le processus de planification actions est encore actif"
            )
        reservations = _read_json(self.reservations_path)
        if str((reservations.get("paths") or {}).get("action_replay_root")) != str(
            root
        ):
            raise FullCampaignRelayError("Racine actions non réservée par ce relais")

        stamp = _safe_stamp()
        destination = root.with_name(f".{root.name}.{reason}.{stamp}")
        suffix = 1
        while destination.exists():
            destination = root.with_name(f".{root.name}.{reason}.{stamp}.{suffix}")
            suffix += 1
        files: list[dict[str, Any]] = []
        directories: list[str] = []
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(root).as_posix()
            is_junction = bool(getattr(path, "is_junction", lambda: False)())
            if path.is_symlink() or is_junction:
                raise FullCampaignRelayError(
                    f"Lien ou jonction interdit dans la récupération actions : {relative}"
                )
            if path.is_dir():
                directories.append(relative)
            elif path.is_file():
                files.append(
                    {
                        "relative_path": relative,
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
            else:
                raise FullCampaignRelayError(
                    f"Entrée non régulière dans la racine actions : {relative}"
                )
        unsigned: dict[str, Any] = {
            "schema_version": RECOVERY_INVENTORY_SCHEMA_VERSION,
            "reason": reason,
            "source": str(root),
            "preserved_at": str(destination),
            "inventoried_at_utc": _now(),
            "file_count": len(files),
            "directory_count": len(directories),
            "files": files,
            "directories": directories,
            "tree_sha256": stable_sha256(files),
        }
        manifest = {
            **unsigned,
            "inventory_signature": stable_sha256(unsigned),
        }
        manifest_dir = self.config.supervision_dir / "recovery_manifests"
        manifest_path = manifest_dir / f"action_root.{reason}.{stamp}.json"
        manifest_suffix = 1
        while manifest_path.exists():
            manifest_path = manifest_dir / (
                f"action_root.{reason}.{stamp}.{manifest_suffix}.json"
            )
            manifest_suffix += 1
        _atomic_json(manifest_path, manifest)

        root.replace(destination)
        for row in files:
            preserved = destination / str(row["relative_path"])
            if (
                not preserved.is_file()
                or preserved.stat().st_size != int(row["size_bytes"])
                or sha256_file(preserved) != row["sha256"]
            ):
                raise FullCampaignRelayError(
                    "La racine actions a été préservée mais son inventaire ne se revalide pas"
                )
        self.status.setdefault("recovery_archives", []).append(
            {
                "reason": reason,
                "source": str(root),
                "preserved_at": str(destination),
                "inventory_path": str(manifest_path),
                "inventory_sha256": sha256_file(manifest_path),
                "file_count": len(files),
                "tree_sha256": manifest["tree_sha256"],
            }
        )
        self._write_status()
        return destination

    def _action_plan_publication_ready(self, actions: Any, root: Path) -> bool:
        """Recognize the producer's two-file publication and recover crash gaps."""

        plan_path = root / "action_replay_plan.json"
        commands_path = root / "action_replay_commands.json"
        if plan_path.is_file() and commands_path.is_file():
            return True
        if not root.exists() or not any(root.iterdir()):
            return False
        if self._step_child_running("planification_actions"):
            return False
        if plan_path.is_file():
            # The producer writes the signed plan atomically before its signed
            # commands document. Only that exact crash window is repairable.
            plan = _read_json(plan_path)
            actions._verify_signed(plan, "plan_signature", "plan d'actions partiel")
            if (
                plan.get("schema_version") != actions.PLAN_SCHEMA_VERSION
                or Path(str(plan.get("replay_root") or "")).resolve() != root
            ):
                raise FullCampaignRelayError(
                    "Le fragment de plan actions n'appartient pas à cette racine"
                )
        self._archive_incomplete_action_root("publication_plan_incomplète")
        return False

    def _validate_replay_receipt(self, plan: Mapping[str, Any]) -> bool:
        path = self.config.lot_replay_root / "replay_run_receipt.json"
        if not path.is_file():
            return False
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_priority_lot_replay_v4 as replay,
        )

        receipt = _read_json(path)
        replay._verify_signed_payload(receipt, "run_receipt_signature", "run receipt")
        if (
            receipt.get("schema_version") != replay.RUN_RECEIPT_SCHEMA_VERSION
            or receipt.get("status") != "complete_validated"
            or receipt.get("plan_signature") != plan.get("plan_signature")
        ):
            raise FullCampaignRelayError("Reçu d'exécution des rejeux incohérent")
        proofs: list[dict[str, Any]] = []
        for dossier in plan["dossiers"]:
            for arm in ("baseline", "incident"):
                proof = replay.validate_arm(
                    Path(dossier["arms"][arm]["run_dir"]), dossier=dossier, arm=arm
                )
                proofs.append({"dossier_id": dossier["dossier_id"], **proof})
            replay._validate_pair(dossier)
        if receipt.get("arms") != proofs:
            raise FullCampaignRelayError("Le reçu ne correspond plus aux bras validés")
        return True

    def _archive_partial_replay_arm(self, path: Path, label: str) -> None:
        root = self.config.lot_replay_root.resolve()
        resolved = path.resolve()
        if not _is_relative_to(resolved, root) or resolved == root:
            raise FullCampaignRelayError("Bras partiel hors racine de rejeu")
        recovery = root / "recovery" / "partial_arms"
        recovery.mkdir(parents=True, exist_ok=True)
        destination = recovery / f"{label}.{_safe_stamp()}"
        suffix = 1
        while destination.exists():
            destination = recovery / f"{label}.{_safe_stamp()}.{suffix}"
            suffix += 1
        resolved.replace(destination)
        self.status.setdefault("recovery_archives", []).append(
            {
                "reason": "bras_rejeu_incomplet",
                "source": str(resolved),
                "preserved_at": str(destination),
            }
        )
        self._write_status()

    def _execute_lot_arms_restartably(self) -> None:
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_priority_lot_replay_v4 as replay,
        )

        plan = replay.load_and_validate_plan(self.config.lot_replay_root)
        if self._validate_replay_receipt(plan):
            return
        results: list[dict[str, Any]] = []
        for dossier in plan["dossiers"]:
            dossier_id = str(dossier["dossier_id"])
            for arm in ("baseline", "incident"):
                arm_plan = dossier["arms"][arm]
                run_dir = Path(str(arm_plan["run_dir"])).resolve()

                def arm_ready(
                    run_dir: Path = run_dir,
                    dossier: Mapping[str, Any] = dossier,
                    arm: str = arm,
                ) -> bool:
                    if not run_dir.exists():
                        return False
                    try:
                        replay.validate_arm(run_dir, dossier=dossier, arm=arm)
                    except replay.ReplayContractError:
                        self._archive_partial_replay_arm(
                            run_dir, f"{dossier_id}__{arm}"
                        )
                        return False
                    return True

                self.run_step(
                    step=f"rejeu_{dossier_id}_{arm}",
                    command=list(arm_plan["command"]),
                    completion_check=arm_ready,
                    message_fr=(
                        f"Rejeu détaillé des lots {dossier_id}, scénario "
                        f"{'sans incident' if arm == 'baseline' else 'avec incident'}."
                    ),
                )
                proof = replay.validate_arm(run_dir, dossier=dossier, arm=arm)
                results.append({"dossier_id": dossier_id, **proof})
            replay._validate_pair(dossier)
        receipt: dict[str, Any] = {
            "schema_version": replay.RUN_RECEIPT_SCHEMA_VERSION,
            "status": "complete_validated",
            "created_at_utc": _now(),
            "plan_signature": plan["plan_signature"],
            "arms": results,
        }
        receipt["run_receipt_signature"] = replay.stable_sha256(receipt)
        receipt_path = self.config.lot_replay_root / "replay_run_receipt.json"
        if receipt_path.exists():
            raise FullCampaignRelayError("Un reçu de rejeu non validé existe déjà")
        _atomic_json(receipt_path, receipt)
        if not self._validate_replay_receipt(plan):
            raise FullCampaignRelayError("Le reçu de rejeu publié ne se revalide pas")

    def _replay_final_ready(self) -> bool:
        path = self.config.lot_replay_root / "finalized" / "replay_validation.json"
        if not path.is_file():
            return False
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_priority_lot_replay_v4 as replay,
        )

        payload = _read_json(path)
        replay._verify_signed_payload(
            payload, "validation_signature", "replay validation"
        )
        plan = replay.load_and_validate_plan(self.config.lot_replay_root)
        if not self._validate_replay_receipt(plan):
            raise FullCampaignRelayError("Reçu final des rejeux absent")
        receipt = _read_json(self.config.lot_replay_root / "replay_run_receipt.json")
        html = Path(str(payload.get("standalone_html") or "")).resolve()
        inventory = Path(str(payload.get("artifact_inventory") or "")).resolve()
        dossiers = payload.get("dossiers") or []
        if (
            payload.get("status") != "complete_validated"
            or payload.get("plan_signature") != plan.get("plan_signature")
            or payload.get("run_receipt_signature")
            != receipt.get("run_receipt_signature")
            or not html.is_file()
            or sha256_file(html) != payload.get("standalone_html_sha256")
            or not inventory.is_file()
            or sha256_file(inventory) != payload.get("artifact_inventory_sha256")
            or not _is_relative_to(html, self.config.lot_replay_root)
            or inventory
            != self.config.lot_replay_root / "finalized" / "artifact_inventory.csv"
            or not isinstance(dossiers, list)
            or len(dossiers) != len(plan.get("dossiers") or [])
            or len(dossiers) > MAX_LOT_DOSSIERS
            or {
                str(row.get("dossier_id") or "")
                for row in dossiers
                if isinstance(row, Mapping)
            }
            != {str(row.get("dossier_id") or "") for row in plan.get("dossiers") or []}
            or any(
                not isinstance(row, Mapping)
                or row.get("quality_incident_included") is not False
                or row.get("state_dependent_supplier_risks_enabled") is not False
                or row.get("cross_arm_lot_matching_used") is not False
                for row in dossiers
            )
        ):
            raise FullCampaignRelayError("Résultat final des rejeux de lots incohérent")
        with inventory.open("r", encoding="utf-8-sig", newline="") as stream:
            inventory_rows = list(csv.DictReader(stream))
        if not inventory_rows:
            raise FullCampaignRelayError("Inventaire final des rejeux vide")
        for row in inventory_rows:
            artifact = (
                self.config.lot_replay_root / str(row.get("relative_path") or "")
            ).resolve()
            if (
                artifact == self.config.lot_replay_root
                or not _is_relative_to(artifact, self.config.lot_replay_root)
                or not artifact.is_file()
                or artifact.stat().st_size != int(row.get("size_bytes") or -1)
                or sha256_file(artifact) != row.get("sha256")
            ):
                raise FullCampaignRelayError(
                    "Un artefact inventorié du rejeu est absent ou modifié"
                )
        return True

    def _preserve_partial_replay_finalization(self) -> None:
        root = self.config.lot_replay_root
        final_root = root / "finalized"
        html = root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html"
        if not final_root.exists() and not html.exists():
            return
        recovery = root / "recovery" / f"partial_finalization.{_safe_stamp()}"
        recovery.mkdir(parents=True, exist_ok=False)
        if final_root.exists():
            final_root.replace(recovery / "finalized")
        if html.exists():
            html.replace(recovery / html.name)
        self.status.setdefault("recovery_archives", []).append(
            {
                "reason": "finalisation_rejeu_incomplète",
                "source": str(root),
                "preserved_at": str(recovery),
            }
        )
        self._write_status()

    def run_lot_replays(self, selection: Sequence[Mapping[str, Any]]) -> None:
        if not selection:
            self.status["lot_replays"] = {
                "status": "not_run_no_qualified_dossier",
                "dossier_count": 0,
                "forced_top_three": False,
            }
            self._write_status()
            return
        expected_count = len(selection)
        self.run_step(
            step="planification_rejeux_lots",
            command=self._python_module(
                LOT_REPLAY_MODULE,
                "plan",
                "--campaign-root",
                str(self.config.campaign_root),
                "--results-dir",
                str(self.config.results_dir),
                "--output-root",
                str(self.config.lot_replay_root),
                "--max-dossiers",
                str(MAX_LOT_DOSSIERS),
            ),
            completion_check=lambda: self._replay_plan_ready(expected_count),
            message_fr=f"Préparation signée de {expected_count} dossier(s) de lots.",
        )
        # Validate commands without executing them before any engine arm starts.
        self.run_step(
            step="validation_commandes_rejeux",
            command=self._python_module(
                LOT_REPLAY_MODULE,
                "run",
                "--replay-root",
                str(self.config.lot_replay_root),
            ),
            completion_check=lambda: self._replay_plan_ready(expected_count),
            message_fr="Contrôle des commandes des rejeux avant exécution.",
            run_even_if_complete=True,
        )
        self._execute_lot_arms_restartably()
        if not self._replay_final_ready():
            self._preserve_partial_replay_finalization()
        self.run_step(
            step="finalisation_rejeux_lots",
            command=self._python_module(
                LOT_REPLAY_MODULE,
                "finalize",
                "--replay-root",
                str(self.config.lot_replay_root),
            ),
            completion_check=self._replay_final_ready,
            message_fr="Construction de la généalogie lots–production–client agrégé.",
        )
        self._record_artifact(
            "lot_replay_validation",
            self.config.lot_replay_root / "finalized" / "replay_validation.json",
        )
        self.status["lot_replays"] = {
            "status": "complete_validated",
            "dossier_count": expected_count,
            "forced_top_three": False,
            "root": str(self.config.lot_replay_root),
        }
        self._write_status()

    def process_optional_action_replay(self) -> None:
        """Run the optional, open-loop action comparison with a separate verdict."""

        mode = self.config.action_replay_mode
        module_path = _module_path(self.config.repo, ACTION_REPLAY_MODULE).resolve()
        pinned_modules = {
            str(row.get("module") or "")
            for row in self.contract.get("source_inventory") or []
            if isinstance(row, Mapping)
        }
        module_pinned = ACTION_REPLAY_MODULE in pinned_modules
        root = self.config.action_replay_root
        if mode == "off":
            self.status["action_replay"] = {
                "status": "disabled_by_contract",
                "module_detected": module_path.is_file(),
                "module_hash_pinned": module_pinned,
            }
            self._write_status()
            return
        if root is None:
            self.status["action_replay"] = {
                "status": "not_configured",
                "module_detected": module_path.is_file(),
                "module_hash_pinned": module_pinned,
                "incident_results_remain_valid": True,
                "message_fr": (
                    "Aucune racine de sortie actions n'a été demandée; la campagne "
                    "incidents et les rejeux de lots restent valides."
                ),
            }
            self._write_status()
            if mode == "required":  # Also enforced by RelayConfig.validate.
                raise FullCampaignRelayError("Racine actions obligatoire absente")
            return
        if not module_path.is_file() or not module_pinned:
            self.status["action_replay"] = {
                "status": "module_not_available",
                "module": ACTION_REPLAY_MODULE,
                "module_detected": module_path.is_file(),
                "module_hash_pinned": module_pinned,
                "requested_mode": mode,
                "incident_results_remain_valid": True,
            }
            self._write_status()
            if mode == "required":
                raise FullCampaignRelayError(
                    "Le rejeu d'actions a été rendu obligatoire mais son module est absent"
                )
            return
        if not self._lot_selection():
            self.status["action_replay"] = {
                "status": "not_run_no_qualified_dossier",
                "incident_results_remain_valid": True,
                "forced_top_three": False,
            }
            self._write_status()
            return

        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_priority_action_replay_v4 as actions,
        )

        def plan_ready() -> bool:
            if not self._action_plan_publication_ready(actions, root):
                return False
            plan = actions.load_and_validate_plan(root)
            contract = plan.get("scientific_contract") or {}
            if (
                contract.get("reference_mode") not in {None, "signed_reference"}
                and (plan.get("requested_parameters") or {}).get("reference_mode")
                != "signed_reference"
            ):
                raise FullCampaignRelayError("Le mode de référence actions a changé")
            if (plan.get("requested_parameters") or {}).get("reference_mode") != (
                "signed_reference"
            ):
                raise FullCampaignRelayError(
                    "Les actions doivent réutiliser les références signées"
                )
            if (
                contract.get("reference_engine_reruns") != 0
                or contract.get("only_action_arms_execute_the_engine") is not True
                or contract.get("quality_incident_or_action_included") is not False
                or contract.get("availability_or_capacity_invented") is not False
                or contract.get("closed_loop_claimed") is not False
            ):
                raise FullCampaignRelayError("Garde-fous du plan d'actions incohérents")
            return True

        def run_ready() -> bool:
            path = root / "action_replay_run_receipt.json"
            if not path.is_file():
                return False
            payload = _read_json(path)
            actions._verify_signed(payload, "run_signature", "reçu actions")
            status = str(payload.get("status") or "")
            if status == "validated_not_executed":
                return False
            if status not in {
                "complete_validated",
                "complete_no_representable_action",
            }:
                raise FullCampaignRelayError(
                    f"Statut d'exécution actions invalide : {status}"
                )
            return True

        def final_ready() -> bool:
            path = root / "action_replay_validation.json"
            if not path.is_file():
                return False
            _summary, validation = actions.validate_action_results(root)
            if validation.get("status") not in {
                "complete_validated",
                "complete_no_representable_action",
            }:
                raise FullCampaignRelayError("Validation finale actions invalide")
            return True

        def action_progress() -> dict[str, Any]:
            evidence = root / "case_evidence"
            completed = (
                sum(1 for _ in evidence.rglob("*.json")) if evidence.is_dir() else 0
            )
            return {"validated_action_arms": completed}

        try:
            command = self._python_module(
                ACTION_REPLAY_MODULE,
                "plan",
                "--campaign-root",
                str(self.config.campaign_root),
                "--results-dir",
                str(self.config.results_dir),
                "--output-root",
                str(root),
                "--lot-replay-root",
                str(self.config.lot_replay_root),
                "--max-dossiers",
                str(MAX_LOT_DOSSIERS),
                "--reference-mode",
                "signed_reference",
            )
            self.run_step(
                step="planification_actions",
                command=command,
                completion_check=plan_ready,
                message_fr=(
                    "Préparation des actions réellement représentables, séparées "
                    "des actions refusées par le moteur."
                ),
                run_even_if_complete=True,
            )
            self.run_step(
                step="validation_commandes_actions",
                command=self._python_module(
                    ACTION_REPLAY_MODULE,
                    "run",
                    "--output-root",
                    str(root),
                ),
                completion_check=plan_ready,
                message_fr="Contrôle des commandes actions sans lancer le moteur.",
                run_even_if_complete=True,
            )
            self.run_step(
                step="exécution_actions",
                command=self._python_module(
                    ACTION_REPLAY_MODULE,
                    "run",
                    "--output-root",
                    str(root),
                    "--execute",
                    "--workers",
                    "2",
                ),
                completion_check=run_ready,
                message_fr=(
                    "Comparaison appariée des actions à l'incident sans action; "
                    "les références signées ne sont pas recalculées."
                ),
                progress_reader=action_progress,
            )
            self.run_step(
                step="consolidation_actions",
                command=self._python_module(
                    ACTION_REPLAY_MODULE,
                    "finalize",
                    "--output-root",
                    str(root),
                ),
                completion_check=final_ready,
                message_fr="Consolidation séparée des gains et refus d'actions.",
            )
            self.run_step(
                step="validation_actions",
                command=self._python_module(
                    ACTION_REPLAY_MODULE,
                    "validate",
                    "--output-root",
                    str(root),
                ),
                completion_check=final_ready,
                message_fr="Validation finale du paquet d'actions en boucle ouverte.",
                run_even_if_complete=True,
            )
            _summary, validation = actions.validate_action_results(root)
            self.status["action_replay"] = {
                "status": validation["status"],
                "root": str(root),
                "validation_sha256": sha256_file(
                    root / "action_replay_validation.json"
                ),
                "incident_results_remain_valid": True,
                "reference_engine_reruns": 0,
                "closed_loop_claimed": False,
            }
            self._write_status()
            self._record_artifact(
                "action_replay_validation",
                root / "action_replay_validation.json",
            )
        except Exception as exc:
            self.status["action_replay"] = {
                "status": "failed_visible_separate_phase",
                "root": str(root),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "incident_results_remain_valid": True,
                "message_fr": (
                    "La phase actions n'est pas publiée. Les résultats incidents et "
                    "lots déjà validés restent disponibles."
                ),
            }
            self._write_status()
            if mode == "required":
                raise

    def process_optional_curves(self) -> bool:
        """Validate curves when present, without invalidating incident results."""

        progress_path = self.config.sidecar_dir / "capture_progress.json"
        try:
            if not self._sidecar_inventory_ready():
                progress: dict[str, Any] = {}
                if progress_path.is_file():
                    source = _read_json(progress_path)
                    progress = {
                        "captured_cases": source.get("completed_cases"),
                        "expected_cases": source.get("expected_cases"),
                        "last_transient_errors": source.get("last_transient_errors"),
                    }
                self.status["nominal_curves"] = {
                    "status": "curve_capture_failed_or_incomplete",
                    "campaign_incident_results_remain_valid": True,
                    "progress": progress,
                    "message_fr": (
                        "La capture journalière n'est pas complète; aucune courbe "
                        "nominale n'est publiée ni reconstruite artificiellement."
                    ),
                }
                self._write_status()
                return False
            self.validate_and_aggregate_curves()
            self.status["nominal_curves"] = {
                "status": "complete_validated",
                "case_count": EXPECTED_HOLDOUT_CASES,
                "state_count": len(EXPECTED_STATE_IDS),
                "campaign_incident_results_remain_valid": True,
            }
            self._write_status()
            return True
        except Exception as exc:  # Curves are an explicitly non-blocking side product.
            self.status["nominal_curves"] = {
                "status": "curve_capture_failed_or_incomplete",
                "campaign_incident_results_remain_valid": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "message_fr": (
                    "Les preuves de courbes n'ont pas passé leur validation stricte. "
                    "Elles sont exclues; les 3 330 résultats incidents sont conservés."
                ),
            }
            self._write_status()
            return False

    def revalidate_published_optional_products(self) -> None:
        """Reopen optional products that the immutable delivery actually used."""

        curves = self.status.get("nominal_curves") or {}
        if isinstance(curves, Mapping) and curves.get("status") == "complete_validated":
            from etudecas.prototypes.scan_2027_risk_control import (
                supplier_holdout_curve_aggregator_v4 as aggregator,
            )

            aggregator.validate_aggregates(self.config.sidecar_dir)
            recorded = (self.status.get("artifacts") or {}).get(
                "nominal_curve_aggregates"
            )
            aggregate_manifest = (
                self.config.sidecar_dir
                / "curve_aggregates_v1"
                / "aggregate_manifest.json"
            )
            if not isinstance(recorded, Mapping) or recorded.get(
                "sha256"
            ) != sha256_file(aggregate_manifest):
                raise FullCampaignRelayError(
                    "Les courbes publiées diffèrent du paquet final du relais"
                )

        action = self.status.get("action_replay") or {}
        action_status = str(action.get("status") if isinstance(action, Mapping) else "")
        if action_status in {
            "complete_validated",
            "complete_no_representable_action",
        }:
            if self.config.action_replay_root is None:
                raise FullCampaignRelayError(
                    "Le statut annonce des actions sans racine enregistrée"
                )
            from etudecas.prototypes.scan_2027_risk_control import (
                supplier_priority_action_replay_v4 as actions,
            )

            _summary, validation = actions.validate_action_results(
                self.config.action_replay_root
            )
            validation_path = (
                self.config.action_replay_root / "action_replay_validation.json"
            )
            if (
                validation.get("status") != action_status
                or not isinstance(action, Mapping)
                or action.get("validation_sha256") != sha256_file(validation_path)
            ):
                raise FullCampaignRelayError(
                    "Le paquet d'actions publié a changé depuis la livraison"
                )

    def _archive_partial_final_delivery(self) -> Path:
        output = self.config.final_html
        if output is None:
            raise FullCampaignRelayError("Aucun livrable final configuré")
        manifest_path = Path(str(output) + ".manifest.json")
        fragments = [path for path in (output, manifest_path) if path.is_file()]
        if len(fragments) != 1:
            raise FullCampaignRelayError(
                "La récupération finale exige exactement un fragment régulier"
            )
        if not self._step_was_attempted("livrable_final_autonome"):
            raise FullCampaignRelayError(
                "Fragment de livraison préexistant non enregistré; refus de le déplacer"
            )
        if self._step_child_running("livrable_final_autonome"):
            raise FullCampaignRelayError(
                "Le processus de livraison finale est encore actif"
            )
        reservations = _read_json(self.reservations_path)
        if str((reservations.get("paths") or {}).get("final_html")) != str(output):
            raise FullCampaignRelayError("Livrable final non réservé par ce relais")
        fragment = fragments[0]
        if fragment.is_symlink():
            raise FullCampaignRelayError("Fragment final symbolique interdit")
        inventory_row = {
            "source_path": str(fragment),
            "name": fragment.name,
            "size_bytes": fragment.stat().st_size,
            "sha256": sha256_file(fragment),
        }
        stamp = _safe_stamp()
        recovery_parent = self.config.supervision_dir / "recovery"
        destination = recovery_parent / f"final_delivery.partial.{stamp}"
        suffix = 1
        while destination.exists():
            destination = recovery_parent / (f"final_delivery.partial.{stamp}.{suffix}")
            suffix += 1
        destination.mkdir(parents=True, exist_ok=False)
        unsigned = {
            "schema_version": RECOVERY_INVENTORY_SCHEMA_VERSION,
            "reason": "publication_html_manifeste_interrompue",
            "inventoried_at_utc": _now(),
            "reserved_output_html": str(output),
            "reserved_manifest": str(manifest_path),
            "preserved_at": str(destination),
            "fragments": [inventory_row],
            "tree_sha256": stable_sha256([inventory_row]),
        }
        inventory = {
            **unsigned,
            "inventory_signature": stable_sha256(unsigned),
        }
        inventory_path = destination / "recovery_inventory.json"
        _atomic_json(inventory_path, inventory)
        preserved = destination / fragment.name
        fragment.replace(preserved)
        if (
            not preserved.is_file()
            or preserved.stat().st_size != inventory_row["size_bytes"]
            or sha256_file(preserved) != inventory_row["sha256"]
        ):
            raise FullCampaignRelayError(
                "Le fragment final a été préservé mais son SHA ne se revalide pas"
            )
        self.status.setdefault("recovery_archives", []).append(
            {
                "reason": "publication_html_manifeste_interrompue",
                "source": str(fragment),
                "preserved_at": str(preserved),
                "inventory_path": str(inventory_path),
                "inventory_sha256": sha256_file(inventory_path),
                "fragment_sha256": inventory_row["sha256"],
            }
        )
        self._write_status()
        return destination

    def _final_delivery_ready(self, *, recover_owned_partial: bool = False) -> bool:
        if self.config.final_html is None:
            return True
        self._validate_legacy_html_inventory()
        manifest_path = Path(str(self.config.final_html) + ".manifest.json")
        for candidate in (self.config.final_html, manifest_path):
            if candidate.exists() and not candidate.is_file():
                raise FullCampaignRelayError(
                    f"Chemin de livraison final non régulier : {candidate}"
                )
        html_exists = self.config.final_html.is_file()
        manifest_exists = manifest_path.is_file()
        if not html_exists and not manifest_exists:
            return False
        if html_exists != manifest_exists:
            if recover_owned_partial:
                if self._step_child_running("livrable_final_autonome"):
                    return False
                self._archive_partial_final_delivery()
                return False
            raise FullCampaignRelayError("Livrable autonome final partiel")
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_v4_final_standalone_delivery as delivery,
        )

        delivery.validate_delivery(self.config.final_html)
        payload = _read_json(manifest_path)
        if (
            payload.get("status") != "complete_validated"
            or payload.get("offline_single_file") is not True
            or int(payload.get("view_count") or -1) != 3
        ):
            raise FullCampaignRelayError("Manifeste du livrable autonome non valide")
        # Accept either field name only until the optional composer is present;
        # its own `validate` CLI remains authoritative and is always called.
        expected_hash = payload.get("html_sha256") or payload.get("output_html_sha256")
        if expected_hash and sha256_file(self.config.final_html) != expected_hash:
            raise FullCampaignRelayError(
                "Le HTML final ne correspond plus à son manifeste"
            )
        return True

    def build_final_delivery(self, lot_count: int) -> None:
        if self.config.final_html is None:
            return
        command = self._python_module(
            FINAL_DELIVERY_MODULE,
            "build",
            "--campaign-root",
            str(self.config.campaign_root),
            "--results-dir",
            str(self.config.results_dir),
            "--dashboard-html",
            str(self.config.dashboard_html),
            "--target-registry",
            str(self.config.results_dir / "cross_state_target_registry.json"),
            "--output-html",
            str(self.config.final_html),
        )
        curves = self.status.get("nominal_curves") or {}
        if isinstance(curves, Mapping) and curves.get("status") == "complete_validated":
            command.extend(["--curves-dir", str(self.config.sidecar_dir)])
        if lot_count:
            command.extend(["--lot-replay-root", str(self.config.lot_replay_root)])
        action = self.status.get("action_replay") or {}
        if (
            self.config.action_replay_root is not None
            and isinstance(action, Mapping)
            and action.get("status")
            in {"complete_validated", "complete_no_representable_action"}
        ):
            command.extend(
                ["--action-results-root", str(self.config.action_replay_root)]
            )
        if self.config.legacy_risk_html is not None:
            command.extend(["--legacy-risk-html", str(self.config.legacy_risk_html)])
        if self.config.legacy_control_html is not None:
            command.extend(
                ["--legacy-control-html", str(self.config.legacy_control_html)]
            )
        self.run_step(
            step="livrable_final_autonome",
            command=command,
            completion_check=lambda: self._final_delivery_ready(
                recover_owned_partial=True
            ),
            message_fr="Assemblage du livrable autonome final sans remplacer les pages existantes.",
        )
        self.run_step(
            step="validation_livrable_final",
            command=self._python_module(
                FINAL_DELIVERY_MODULE,
                "validate",
                "--path",
                str(self.config.final_html),
            ),
            completion_check=self._final_delivery_ready,
            message_fr="Validation hors ligne du livrable final en trois vues.",
            run_even_if_complete=True,
        )
        self._record_artifact("final_standalone_html", self.config.final_html)
        self._record_artifact(
            "final_standalone_manifest",
            Path(str(self.config.final_html) + ".manifest.json"),
        )

    def execute(self) -> int:
        self.prepare()
        self.observe_sidecar_watcher()
        if self.status.get("status") in {"complete", "complete_with_limits"}:
            # Revalidate, rather than merely trusting a previous mutable status.
            self._results_ready()
            self._dashboard_ready()
            selection = self._lot_selection()
            if selection and not self._replay_final_ready():
                raise FullCampaignRelayError("Statut complet mais rejeux non validés")
            self.revalidate_published_optional_products()
            if not self._final_delivery_ready():
                raise FullCampaignRelayError(
                    "Statut complet mais livrable final invalide"
                )
            return 0
        self.wait_for_calibration()
        self.build_and_validate_bridge()
        self.plan_campaign()
        self.launch_campaign()
        self.finalize_campaign()
        self.build_dashboard()
        selection = self._lot_selection()
        self.run_lot_replays(selection)
        self.process_optional_action_replay()
        self.process_optional_curves()
        self.build_final_delivery(len(selection))
        self.status["active_command"] = {}
        self.status["completed_at_utc"] = _now()
        curves_ok = (self.status.get("nominal_curves") or {}).get(
            "status"
        ) == "complete_validated"
        action_status = str(
            (self.status.get("action_replay") or {}).get("status") or "not_configured"
        )
        action_limited = (
            self.config.action_replay_root is not None
            and action_status
            not in {
                "complete_validated",
                "complete_no_representable_action",
                "not_run_no_qualified_dossier",
            }
        )
        curve_message = (
            "courbes nominales validées"
            if curves_ok
            else "courbes nominales exclues car capture incomplète"
        )
        self.update_status(
            "terminé",
            (
                f"Campagne V4 validée : {curve_message}, 3 330 lignes incidents, "
                f"dashboard autonome et {len(selection)} rejeu(x) de lots signé(s)."
            ),
            status=(
                "complete"
                if curves_ok and not action_limited
                else "complete_with_limits"
            ),
            progress={
                "holdout_cases_reused": 90,
                "holdout_cases_rerun": 0,
                "campaign_rows": 3330,
                "lot_replay_dossiers": len(selection),
                "nominal_curves_available": curves_ok,
                "action_replay_status": action_status,
                "optional_inputs_frozen_at_completion": True,
                "later_optional_artifacts_require_a_new_delivery_path": True,
            },
        )
        return 0


@contextmanager
def _relay_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    acquired = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise FullCampaignRelayError(
                "Un autre relais de campagne V4 est déjà actif"
            ) from exc
        yield
    finally:
        try:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _config_from_args(args: argparse.Namespace) -> RelayConfig:
    return RelayConfig(
        repo=args.repo,
        calibration_plan_dir=args.calibration_plan_dir,
        calibration_run_dir=args.calibration_run_dir,
        calibration_supervision_dir=args.calibration_supervision_dir,
        sidecar_dir=args.sidecar_dir,
        bridge_json=args.bridge_json,
        campaign_root=args.campaign_root,
        results_dir=args.results_dir,
        lot_replay_root=args.lot_replay_root,
        dashboard_html=args.dashboard_html,
        final_html=args.final_html,
        supervision_dir=args.supervision_dir,
        action_replay_root=args.action_replay_root,
        legacy_risk_html=args.legacy_risk_html,
        legacy_control_html=args.legacy_control_html,
        action_replay_mode=args.action_replay_mode,
        sidecar_watcher_pid=args.sidecar_watcher_pid,
        parallel_shards=args.parallel_shards,
        workers_per_shard=args.workers_per_shard,
        launcher_poll_seconds=args.launcher_poll_seconds,
        relay_poll_seconds=args.relay_poll_seconds,
        max_wait_hours=args.max_wait_hours,
    ).resolved()


def _child_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        MODULE_NAME,
        "--repo",
        str(args.repo.resolve()),
        "--calibration-plan-dir",
        str(args.calibration_plan_dir.resolve()),
        "--calibration-run-dir",
        str(args.calibration_run_dir.resolve()),
        "--calibration-supervision-dir",
        str(args.calibration_supervision_dir.resolve()),
        "--sidecar-dir",
        str(args.sidecar_dir.resolve()),
        "--sidecar-watcher-pid",
        str(args.sidecar_watcher_pid),
        "--bridge-json",
        str(args.bridge_json.resolve()),
        "--campaign-root",
        str(args.campaign_root.resolve()),
        "--results-dir",
        str(args.results_dir.resolve()),
        "--lot-replay-root",
        str(args.lot_replay_root.resolve()),
        "--dashboard-html",
        str(args.dashboard_html.resolve()),
        "--supervision-dir",
        str(args.supervision_dir.resolve()),
        "--parallel-shards",
        str(args.parallel_shards),
        "--workers-per-shard",
        str(args.workers_per_shard),
        "--launcher-poll-seconds",
        str(args.launcher_poll_seconds),
        "--relay-poll-seconds",
        str(args.relay_poll_seconds),
        "--max-wait-hours",
        str(args.max_wait_hours),
        "--action-replay-mode",
        str(args.action_replay_mode),
        "--detached-child",
    ]
    for option, value in (
        ("--final-html", args.final_html),
        ("--action-replay-root", args.action_replay_root),
        ("--legacy-risk-html", args.legacy_risk_html),
        ("--legacy-control-html", args.legacy_control_html),
    ):
        if value is not None:
            command.extend([option, str(value.resolve())])
    return command


def detach(args: argparse.Namespace) -> dict[str, Any]:
    config = _config_from_args(args)
    # Validate and pin the complete contract before returning a PID.
    relay = FullCampaignRelay(config)
    relay.prepare()
    existing_detached = config.supervision_dir / "detached.json"
    if existing_detached.is_file():
        previous = _read_json(existing_detached)
        previous_pid = int(previous.get("pid") or 0)
        if _process_running(previous_pid):
            raise FullCampaignRelayError(
                f"Un relais détaché est déjà actif (PID {previous_pid})"
            )
    relay.update_status(
        "démarrage_relais_détaché",
        "Le processus autonome caché est en cours de démarrage.",
        status="detaching",
    )
    command = _child_command(args)
    log_path = config.supervision_dir / "detached_relay.log"
    with log_path.open("ab") as stream:
        kwargs: dict[str, Any] = {
            "cwd": config.repo,
            "stdin": subprocess.DEVNULL,
            "stdout": stream,
            "stderr": subprocess.STDOUT,
            "shell": False,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
        else:  # pragma: no cover
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
    payload = {
        "schema_version": f"{SCHEMA_VERSION}.detached.v1",
        "status": "detached_relay_started",
        "pid": process.pid,
        "command": command,
        "command_sha256": stable_sha256(command),
        "log_path": str(log_path),
        "status_path": str(relay.status_path),
        "started_at_utc": _now(),
    }
    _atomic_json(config.supervision_dir / "detached.json", payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--calibration-plan-dir", type=Path, required=True)
    parser.add_argument("--calibration-run-dir", type=Path, required=True)
    parser.add_argument("--calibration-supervision-dir", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument(
        "--sidecar-watcher-pid",
        type=int,
        default=0,
        help=(
            "PID informatif du watcher sidecar d\u00e9j\u00e0 lanc\u00e9; le relais ne le "
            "lance ni ne le relance"
        ),
    )
    parser.add_argument("--bridge-json", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--lot-replay-root", type=Path, required=True)
    parser.add_argument("--dashboard-html", type=Path, required=True)
    parser.add_argument("--final-html", type=Path)
    parser.add_argument("--action-replay-root", type=Path)
    parser.add_argument("--legacy-risk-html", type=Path)
    parser.add_argument("--legacy-control-html", type=Path)
    parser.add_argument(
        "--action-replay-mode",
        choices=("off", "auto", "required"),
        default="auto",
        help=(
            "off: désactivé; auto: utiliser uniquement une API gelée reconnue; "
            "required: échouer si cette phase ne peut pas être validée"
        ),
    )
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--launcher-poll-seconds", type=float, default=5.0)
    parser.add_argument("--relay-poll-seconds", type=float, default=30.0)
    parser.add_argument("--max-wait-hours", type=float, default=120.0)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--detach", action="store_true")
    mode.add_argument("--detached-child", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.detach:
        try:
            payload = detach(args)
        except Exception as exc:
            print(f"RELAIS V4 NON LANCÉ : {exc}", file=sys.stderr)
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    config = _config_from_args(args)
    relay = FullCampaignRelay(config)
    _prevent_sleep(True)
    try:
        with _relay_lock(config.supervision_dir / ".relay.lock"):
            return relay.execute()
    except ScientificNoGo as exc:
        if relay.contract:
            relay.update_status(
                "arrêt_scientifique",
                str(exc),
                status="scientific_no_go",
            )
        print(f"RELAIS V4 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("RELAIS V4 INTERROMPU; consulter status.json", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - process boundary diagnostics.
        if relay.contract:
            relay.status["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc)),
            }
            relay.update_status("échec", str(exc), status="failed")
        print(f"RELAIS V4 EN ÉCHEC : {exc}", file=sys.stderr)
        return 1
    finally:
        _prevent_sleep(False)


if __name__ == "__main__":
    raise SystemExit(main())
