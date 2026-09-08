#!/usr/bin/env python3
"""Wait for the signed V6 holdout decision, then detach the downstream relay once.

This module is deliberately outside the audited V6 chain.  It never imports or
executes a simulation engine.  Its only authorised process boundary is the
public ``continue_supplier_full_campaign_v6 --detach`` command, whose own
fail-closed preflight remains authoritative.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from uuid import uuid4


SCHEMA_VERSION = "etudecas.supplier_v6_holdout_campaign_once_relay.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
JOURNAL_SCHEMA_VERSION = f"{SCHEMA_VERSION}.journal.v1"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.launch_reservation.v1"
BACKGROUND_SCHEMA_VERSION = f"{SCHEMA_VERSION}.background.v1"
CALIBRATION_STATUS_SCHEMA_VERSION = (
    "etudecas.supplier_v6_calibration_orchestrator.v1.status.v1"
)
CALIBRATION_CONTRACT_SCHEMA_VERSION = (
    "etudecas.supplier_v6_calibration_orchestrator.v1.contract.v1"
)
EXPECTED_CALIBRATION_CONTRACT_SIGNATURE = (
    "42524db76476096c176d02ac9766ca18516b71f62f043e00e73a2aa92e27dad5"
)
HOLDOUT_RESULT_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_holdout.v6.holdout_result"
)
ACCEPTED_HOLDOUT_STATUS = "holdout_validated_30_fresh_reserved_seeds"
OFFICIAL_HOLDOUT_EXECUTION_MODE = "official_v6_fresh_holdout"
SIDECAR_INVENTORY_SCHEMA_VERSION = (
    "etudecas.supplier_holdout_curve_sidecar.v6.inventory.v1"
)
SIDECAR_INVENTORY_FILENAME = "capture_inventory_v5.json"
DOWNSTREAM_RECEIPT_SCHEMA_VERSION = (
    "etudecas.supplier_full_campaign_relay.v6.detached.v1"
)
EXPECTED_HOLDOUT_CASES = 90
DOWNSTREAM_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v6"
)
THIS_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_v6_holdout_campaign_once_relay"
)
ACCEPTED_CALIBRATION_STAGE = "calibration_accepted_ready_for_downstream_handoff"
TERMINAL_REJECTION_STATUSES = frozenset(
    {"scientific_no_go", "failed", "rejected", "no_go"}
)

# Exact audit table published on 2026-09-05.  The test is intentionally part of
# the protected scientific surface: changing it also requires a new audit.
AUDITED_V6_SHA256: dict[str, str] = {
    "etudecas/prototypes/scan_2027_risk_control/supplier_fresh_holdout_v6.py": "bae2589fa99f18cc1237aece1e5db9ae22a25882203b280d41f800c8fab181f2",
    "etudecas/prototypes/scan_2027_risk_control/supplier_holdout_curve_sidecar_v6.py": "b2424ddb272a1601b60d60f7716e8dd23b64916d0a15a4e4f6a60ad60c513016",
    "etudecas/prototypes/scan_2027_risk_control/continue_supplier_v6_calibration.py": "9af8432e26435aa4b2fb99157a944fa270c1427247087af133b2d9eb8adaa047",
    "etudecas/prototypes/scan_2027_risk_control/build_validated_operating_points_v6.py": "8943209948f19979b3f448c65ca364f9e18b98aac34aaecec21d4fc6f5a123a4",
    "etudecas/prototypes/scan_2027_risk_control/supplier_operating_point_full_campaign_v6.py": "ac251c2f7fec97d770ae43e21247e07a2d1eda09ebed5dbf0a113f035e9c8564",
    "etudecas/prototypes/scan_2027_risk_control/launch_supplier_operating_point_full_campaign_v6.py": "5b6f166d753c6a8e25b7da3156fe6815ec80457d09e41f7f051939a4b9873cec",
    "etudecas/prototypes/scan_2027_risk_control/finalize_supplier_operating_point_full_campaign_v6.py": "a4d523d0817464074ae4089b660de2db992de950cad8566e9efd2b68dd08715b",
    "etudecas/prototypes/scan_2027_risk_control/supplier_v6_final_standalone_delivery.py": "3b52c8b85d9eff7f8e15a6b256276ca05da0144b2d1b53fa9ae7850d7b8c74dd",
    "etudecas/prototypes/scan_2027_risk_control/continue_supplier_full_campaign_v6.py": "b087250de5ccc483e08668b9074a943cf978a6589f3d9e74e733b38bd83512ad",
    "etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_v6_completion_path.py": "3b43186935c27debbfbe7ea0220fbb312c07f41f8cc1333103f36bd4b61326a2",
}

HISTORICAL_HTML_SHA256 = {
    "legacy_risk_html": "09cb1a0ade28a8adf782d57025b234cab1051de8f53f7876af24491142ddbe76",
    "legacy_control_html": "7aab17a0fae413f2ec6f36f975617feeadf98a1e09a1c6c660a31807108323cd",
}


class HandoffRelayError(RuntimeError):
    """The one-shot relay cannot proceed safely."""


class CalibrationRejected(HandoffRelayError):
    """The signed calibration decision explicitly forbids downstream work."""


class HandoffTimeout(HandoffRelayError):
    """No accepted signed decision arrived inside the waiting budget."""


class DownstreamLaunchRejected(HandoffRelayError):
    """The pinned downstream public preflight rejected before detaching."""


class DownstreamReceiptError(HandoffRelayError):
    """The downstream process returned no trustworthy detached receipt."""


@dataclass(frozen=True)
class RelayConfig:
    repo: Path
    calibration_status: Path
    handoff_supervision_dir: Path
    v4_plan_dir: Path
    v4_run_dir: Path
    v4_sidecar_root: Path
    calibration_plan_dir: Path
    calibration_run_dir: Path
    sidecar_dir: Path
    bridge_json: Path
    campaign_root: Path
    results_dir: Path
    lot_replay_root: Path
    qualification_dir: Path
    action_replay_root: Path
    dashboard_html: Path
    final_html: Path
    downstream_supervision_dir: Path
    legacy_risk_html: Path
    legacy_control_html: Path
    calibration_workers: int = 2
    parallel_shards: int = 2
    workers_per_shard: int = 2
    launcher_poll_seconds: float = 5.0
    relay_poll_seconds: float = 30.0
    watcher_ready_timeout_seconds: float = 300.0
    sidecar_poll_ms: float = 25.0
    sidecar_stability_ms: float = 12.0
    downstream_max_wait_hours: float = 240.0
    wait_timeout_hours: float = 12.0
    poll_seconds: float = 15.0
    detach_invocation_timeout_seconds: float = 600.0

    def resolved(self) -> "RelayConfig":
        values: dict[str, Any] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            values[field.name] = value.resolve() if isinstance(value, Path) else value
        return RelayConfig(**values)

    def public_mapping(self) -> dict[str, Any]:
        return {
            field.name: (
                str(value)
                if isinstance(value := getattr(self, field.name), Path)
                else value
            )
            for field in fields(self)
        }


@dataclass(frozen=True)
class LaunchResult:
    returncode: int
    stdout: str
    stderr: str


Launcher = Callable[[Sequence[str], RelayConfig], LaunchResult]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_aware_iso_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _signed(unsigned: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**unsigned, field: stable_sha256(unsigned)}


def _verify_signature(payload: Mapping[str, Any], field: str, label: str) -> str:
    unsigned = dict(payload)
    signature = unsigned.pop(field, None)
    if not _is_sha256(signature) or signature != stable_sha256(unsigned):
        raise HandoffRelayError(f"Signature invalide : {label}")
    return signature


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffRelayError(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise HandoffRelayError(f"Objet JSON attendu : {path}")
    return payload


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _destination_paths(config: RelayConfig) -> tuple[Path, ...]:
    return (
        config.bridge_json,
        config.campaign_root,
        config.results_dir,
        config.lot_replay_root,
        config.qualification_dir,
        config.action_replay_root,
        config.dashboard_html,
        config.final_html,
        Path(str(config.final_html) + ".manifest.json"),
        config.downstream_supervision_dir,
    )


def _protected_source_paths(config: RelayConfig) -> tuple[Path, ...]:
    return (
        config.repo,
        config.v4_plan_dir,
        config.v4_run_dir,
        config.v4_sidecar_root,
        config.calibration_plan_dir,
        config.calibration_run_dir,
        config.sidecar_dir,
        config.calibration_status.parent,
        config.legacy_risk_html,
        config.legacy_control_html,
    )


def _module_inventory(config: RelayConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative, expected in AUDITED_V6_SHA256.items():
        path = (config.repo / Path(relative)).resolve()
        if not path.is_file():
            raise HandoffRelayError(f"Fichier V6 audité absent : {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise HandoffRelayError(
                f"Empreinte V6 auditée différente : {relative} ({actual})"
            )
        rows.append({"path": str(path), "relative_path": relative, "sha256": actual})
    if len(rows) != 10:
        raise HandoffRelayError("Le contrat doit protéger exactement 10 SHA V6")
    return rows


def _historical_html_inventory(config: RelayConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in ("legacy_risk_html", "legacy_control_html"):
        path = getattr(config, role)
        expected = HISTORICAL_HTML_SHA256[role]
        if not path.is_file():
            raise HandoffRelayError(f"HTML historique absent : {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise HandoffRelayError(
                f"Empreinte de l'HTML historique différente : {role} ({actual})"
            )
        rows.append(
            {
                "role": role,
                "path": str(path),
                "sha256": actual,
                "size": path.stat().st_size,
            }
        )
    if len(rows) != 2:
        raise HandoffRelayError(
            "Le contrat doit protéger exactement deux HTML historiques"
        )
    return rows


def _assert_destinations_absent(config: RelayConfig) -> None:
    existing = [str(path) for path in _destination_paths(config) if path.exists()]
    if existing:
        raise HandoffRelayError(
            "Destination aval déjà présente; aucun écrasement ni reprise : "
            + ", ".join(existing)
        )


def _validate_structure(config: RelayConfig) -> None:
    if not config.repo.is_dir():
        raise HandoffRelayError(f"Dépôt absent : {config.repo}")
    strictly_positive = (
        config.wait_timeout_hours,
        config.poll_seconds,
        config.detach_invocation_timeout_seconds,
        config.watcher_ready_timeout_seconds,
        config.sidecar_poll_ms,
        config.sidecar_stability_ms,
        config.downstream_max_wait_hours,
    )
    if any(not math.isfinite(value) or value <= 0 for value in strictly_positive):
        raise HandoffRelayError(
            "Les délais d'attente doivent être strictement positifs"
        )
    if (
        not math.isfinite(config.launcher_poll_seconds)
        or not 0 <= config.launcher_poll_seconds <= 60
        or not math.isfinite(config.relay_poll_seconds)
        or not 0.1 <= config.relay_poll_seconds <= 60
    ):
        raise HandoffRelayError("Les fréquences de suivi aval sont hors contrat")
    if config.calibration_workers not in (1, 2):
        raise HandoffRelayError("calibration_workers doit valoir 1 ou 2")
    if config.parallel_shards not in (1, 2) or config.workers_per_shard not in (1, 2):
        raise HandoffRelayError("Les parallélismes aval doivent valoir 1 ou 2")
    destinations = _destination_paths(config)
    protected = _protected_source_paths(config)
    for index, left in enumerate(destinations):
        if any(_paths_overlap(left, right) for right in protected):
            raise HandoffRelayError(f"Une destination chevauche une source : {left}")
        if _paths_overlap(left, config.handoff_supervision_dir):
            raise HandoffRelayError(
                f"Une destination chevauche la supervision du relais : {left}"
            )
        for right in destinations[index + 1 :]:
            if _paths_overlap(left, right):
                raise HandoffRelayError(
                    f"Deux destinations aval se chevauchent : {left} / {right}"
                )
    if any(
        _paths_overlap(config.handoff_supervision_dir, source) for source in protected
    ):
        raise HandoffRelayError(
            "La supervision du relais chevauche une source protégée"
        )


def _assert_integrity(config: RelayConfig) -> dict[str, Any]:
    _validate_structure(config)
    _assert_destinations_absent(config)
    return {
        "audited_v6": _module_inventory(config),
        "historical_html": _historical_html_inventory(config),
    }


def downstream_command(config: RelayConfig) -> list[str]:
    command = [
        sys.executable,
        "-m",
        DOWNSTREAM_MODULE,
        "--repo",
        str(config.repo),
        "--v4-plan-dir",
        str(config.v4_plan_dir),
        "--v4-run-dir",
        str(config.v4_run_dir),
        "--v4-sidecar-root",
        str(config.v4_sidecar_root),
        "--calibration-plan-dir",
        str(config.calibration_plan_dir),
        "--calibration-run-dir",
        str(config.calibration_run_dir),
        "--sidecar-dir",
        str(config.sidecar_dir),
        "--bridge-json",
        str(config.bridge_json),
        "--campaign-root",
        str(config.campaign_root),
        "--results-dir",
        str(config.results_dir),
        "--lot-replay-root",
        str(config.lot_replay_root),
        "--qualification-dir",
        str(config.qualification_dir),
        "--action-replay-root",
        str(config.action_replay_root),
        "--action-replay-mode",
        "required",
        "--dashboard-html",
        str(config.dashboard_html),
        "--final-html",
        str(config.final_html),
        "--legacy-risk-html",
        str(config.legacy_risk_html),
        "--legacy-control-html",
        str(config.legacy_control_html),
        "--supervision-dir",
        str(config.downstream_supervision_dir),
        "--calibration-workers",
        str(config.calibration_workers),
        "--parallel-shards",
        str(config.parallel_shards),
        "--workers-per-shard",
        str(config.workers_per_shard),
        "--launcher-poll-seconds",
        str(config.launcher_poll_seconds),
        "--relay-poll-seconds",
        str(config.relay_poll_seconds),
        "--watcher-ready-timeout-seconds",
        str(config.watcher_ready_timeout_seconds),
        "--sidecar-poll-ms",
        str(config.sidecar_poll_ms),
        "--sidecar-stability-ms",
        str(config.sidecar_stability_ms),
        "--max-wait-hours",
        str(config.downstream_max_wait_hours),
        "--detach",
    ]
    if command.count("--detach") != 1 or "--detached-child" in command:
        raise HandoffRelayError(
            "Commande aval non conforme au point d'entrée public V6"
        )
    return command


def _expected_downstream_child_command(config: RelayConfig) -> list[str]:
    """Mirror the pinned V6 detach receipt contract, including parser defaults."""

    return [
        sys.executable,
        "-m",
        DOWNSTREAM_MODULE,
        "--repo",
        str(config.repo),
        "--v4-plan-dir",
        str(config.v4_plan_dir),
        "--v4-run-dir",
        str(config.v4_run_dir),
        "--v4-sidecar-root",
        str(config.v4_sidecar_root),
        "--calibration-plan-dir",
        str(config.calibration_plan_dir),
        "--calibration-run-dir",
        str(config.calibration_run_dir),
        "--sidecar-dir",
        str(config.sidecar_dir),
        "--sidecar-watcher-pid",
        "0",
        "--bridge-json",
        str(config.bridge_json),
        "--campaign-root",
        str(config.campaign_root),
        "--results-dir",
        str(config.results_dir),
        "--lot-replay-root",
        str(config.lot_replay_root),
        "--qualification-dir",
        str(config.qualification_dir),
        "--dashboard-html",
        str(config.dashboard_html),
        "--supervision-dir",
        str(config.downstream_supervision_dir),
        "--calibration-workers",
        str(config.calibration_workers),
        "--parallel-shards",
        str(config.parallel_shards),
        "--workers-per-shard",
        str(config.workers_per_shard),
        "--launcher-poll-seconds",
        str(config.launcher_poll_seconds),
        "--relay-poll-seconds",
        str(config.relay_poll_seconds),
        "--watcher-ready-timeout-seconds",
        str(config.watcher_ready_timeout_seconds),
        "--sidecar-poll-ms",
        str(config.sidecar_poll_ms),
        "--sidecar-stability-ms",
        str(config.sidecar_stability_ms),
        "--max-wait-hours",
        str(config.downstream_max_wait_hours),
        "--action-replay-mode",
        "required",
        "--detached-child",
        "--final-html",
        str(config.final_html),
        "--action-replay-root",
        str(config.action_replay_root),
        "--legacy-risk-html",
        str(config.legacy_risk_html),
        "--legacy-control-html",
        str(config.legacy_control_html),
    ]


def _contract_payload(
    config: RelayConfig, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    unsigned = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "config": config.public_mapping(),
        "command": downstream_command(config),
        "command_sha256": stable_sha256(downstream_command(config)),
        "protected_inventory": inventory,
        "downstream_prevalidation_remains_authoritative": True,
        "launch_attempt_limit": 1,
    }
    return _signed(unsigned, "contract_signature")


def _require_bound_path(value: Any, expected: Path, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise HandoffRelayError(f"Chemin absent du contrat calibration : {label}")
    try:
        actual = Path(value).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HandoffRelayError(
            f"Chemin invalide du contrat calibration : {label}"
        ) from exc
    if actual != expected.resolve():
        raise HandoffRelayError(
            f"Le contrat calibration ne référence pas le {label} attendu"
        )


def _validate_calibration_contract(
    config: RelayConfig, status: Mapping[str, Any]
) -> str:
    if config.calibration_status.name != "status.json":
        raise HandoffRelayError(
            "Le statut calibration doit être le status.json canonique de sa supervision"
        )
    contract_path = config.calibration_status.with_name("contract.json")
    if not contract_path.is_file():
        raise HandoffRelayError(f"Contrat calibration signé absent : {contract_path}")
    contract = _read_json(contract_path)
    contract_signature = _verify_signature(
        contract, "contract_signature", "contrat calibration V6"
    )
    if contract.get("schema_version") != CALIBRATION_CONTRACT_SCHEMA_VERSION:
        raise HandoffRelayError("Schéma inattendu du contrat calibration V6")
    if contract_signature != EXPECTED_CALIBRATION_CONTRACT_SIGNATURE:
        raise HandoffRelayError(
            "Le contrat calibration ne porte pas la signature figée de cette campagne"
        )
    if status.get("contract_signature") != contract_signature:
        raise HandoffRelayError(
            "Le status calibration n'est pas lié à son contrat signé réel"
        )

    configuration = contract.get("configuration")
    if not isinstance(configuration, Mapping):
        raise HandoffRelayError("Configuration absente du contrat calibration V6")
    for key, expected, label in (
        ("repo", config.repo, "dépôt"),
        ("development_plan_dir", config.v4_plan_dir, "plan de développement V6"),
        ("development_run_dir", config.v4_run_dir, "run de développement V6"),
        ("holdout_plan_dir", config.calibration_plan_dir, "plan holdout V6"),
        ("holdout_run_dir", config.calibration_run_dir, "run holdout V6"),
        ("sidecar_dir", config.sidecar_dir, "sidecar holdout V6"),
        (
            "supervision_dir",
            config.calibration_status.parent,
            "dossier de supervision calibration V6",
        ),
    ):
        _require_bound_path(configuration.get(key), expected, label)
    if configuration.get("workers") != config.calibration_workers:
        raise HandoffRelayError(
            "Le nombre de workers ne correspond pas au contrat calibration V6"
        )

    module_hashes = contract.get("module_hashes")
    expected_module_hashes = {
        "orchestrator_sha256": AUDITED_V6_SHA256[
            "etudecas/prototypes/scan_2027_risk_control/continue_supplier_v6_calibration.py"
        ],
        "holdout_driver_sha256": AUDITED_V6_SHA256[
            "etudecas/prototypes/scan_2027_risk_control/supplier_fresh_holdout_v6.py"
        ],
        "sidecar_driver_sha256": AUDITED_V6_SHA256[
            "etudecas/prototypes/scan_2027_risk_control/supplier_holdout_curve_sidecar_v6.py"
        ],
    }
    if not isinstance(module_hashes, Mapping) or any(
        module_hashes.get(key) != expected
        for key, expected in expected_module_hashes.items()
    ):
        raise HandoffRelayError(
            "Le contrat calibration n'est pas lié aux producteurs V6 audités"
        )

    scientific = contract.get("scientific_contract")
    expected_scientific = {
        "development_evidence_cases": 150,
        "new_development_engine_runs": 60,
        "fresh_holdout_engine_runs_if_selected": EXPECTED_HOLDOUT_CASES,
        "holdout_matrix": "3x30_fresh_reserved",
        "watcher_ready_required_before_first_holdout_engine": True,
        "retuning_after_holdout": False,
        "quality_incident_included": False,
        "capacity_incident_included": False,
        "availability_incident_included": False,
        "downstream_execution_supported": False,
    }
    if not isinstance(scientific, Mapping) or any(
        scientific.get(key) != expected for key, expected in expected_scientific.items()
    ):
        raise HandoffRelayError("Contrat scientifique calibration V6 inattendu")
    return contract_signature


def _validate_terminal_calibration_proofs(
    config: RelayConfig, status: Mapping[str, Any]
) -> None:
    holdout_path = config.calibration_run_dir / "holdout_result.json"
    if not holdout_path.is_file():
        raise HandoffRelayError(f"Résultat holdout terminal absent : {holdout_path}")
    holdout = _read_json(holdout_path)
    holdout_signature = _verify_signature(
        holdout, "holdout_signature", "résultat holdout V6"
    )
    if (
        holdout.get("schema_version") != HOLDOUT_RESULT_SCHEMA_VERSION
        or holdout.get("status") != ACCEPTED_HOLDOUT_STATUS
        or holdout.get("accepted") is not True
        or holdout.get("publishable") is not True
        or holdout.get("retuning_after_holdout") is not False
        or holdout.get("execution_mode") != OFFICIAL_HOLDOUT_EXECUTION_MODE
        or holdout.get("holdout_evidence_case_count") != EXPECTED_HOLDOUT_CASES
        or status.get("holdout_signature") != holdout_signature
    ):
        raise HandoffRelayError("Preuve terminale holdout V6 incohérente")

    inventory_path = config.sidecar_dir / SIDECAR_INVENTORY_FILENAME
    if not inventory_path.is_file():
        raise HandoffRelayError(
            f"Inventaire terminal des courbes holdout absent : {inventory_path}"
        )
    inventory = _read_json(inventory_path)
    inventory_signature = _verify_signature(
        inventory, "inventory_signature", "inventaire des courbes holdout V6"
    )
    if (
        inventory.get("schema_version") != SIDECAR_INVENTORY_SCHEMA_VERSION
        or inventory.get("status") != "complete"
        or inventory.get("case_count") != EXPECTED_HOLDOUT_CASES
        or inventory.get("compatibility_filename") != SIDECAR_INVENTORY_FILENAME
        or status.get("inventory_signature") != inventory_signature
    ):
        raise HandoffRelayError("Preuve terminale sidecar V6 incohérente")


def _validate_calibration_status(
    payload: Mapping[str, Any], config: RelayConfig
) -> str:
    signature = _verify_signature(payload, "status_signature", "status calibration V6")
    if payload.get("schema_version") != CALIBRATION_STATUS_SCHEMA_VERSION:
        raise HandoffRelayError("Schéma inattendu du status calibration V6")
    _validate_calibration_contract(config, payload)
    status = payload.get("status")
    stage = str(payload.get("stage") or "")
    if status == "complete":
        if (
            payload.get("downstream_authorized") is not True
            or stage != ACCEPTED_CALIBRATION_STAGE
            or not _is_aware_iso_timestamp(payload.get("completed_at_utc"))
            or not _is_sha256(payload.get("holdout_signature"))
            or not _is_sha256(payload.get("inventory_signature"))
        ):
            raise CalibrationRejected(
                "Status complet mais autorisation/preuve terminale incohérente"
            )
        _validate_terminal_calibration_proofs(config, payload)
        return signature
    if status in TERMINAL_REJECTION_STATUSES or stage.startswith("scientific_no_go"):
        if payload.get("downstream_authorized") is not False:
            raise HandoffRelayError(
                "Décision calibration terminale avec autorisation incohérente"
            )
        raise CalibrationRejected(
            f"Décision calibration terminale sans autorisation : {status}/{stage}"
        )
    if status != "running" or payload.get("downstream_authorized") is not False:
        raise HandoffRelayError(
            f"État calibration inconnu ou incohérent : {status}/{stage}"
        )
    return ""


def _default_launcher(command: Sequence[str], config: RelayConfig) -> LaunchResult:
    kwargs: dict[str, Any] = {
        "cwd": config.repo,
        "stdin": subprocess.DEVNULL,
        "capture_output": True,
        "text": True,
        "shell": False,
        "check": False,
        "timeout": config.detach_invocation_timeout_seconds,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    completed = subprocess.run(list(command), **kwargs)
    return LaunchResult(completed.returncode, completed.stdout, completed.stderr)


def _validate_downstream_receipt(
    result: LaunchResult, config: RelayConfig
) -> dict[str, Any]:
    if result.returncode != 0:
        raise DownstreamLaunchRejected(
            "Le relais aval a refusé son propre préflight : "
            f"exit={result.returncode}; stderr={result.stderr[-2000:]}"
        )
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise TypeError("objet JSON attendu")
        _verify_signature(payload, "receipt_signature", "reçu détaché aval")
    except (json.JSONDecodeError, TypeError, HandoffRelayError) as exc:
        raise DownstreamReceiptError(
            "Reçu JSON signé du relais aval absent ou illisible"
        ) from exc
    expected_command = _expected_downstream_child_command(config)
    expected_log = config.downstream_supervision_dir / "detached_relay.log"
    expected_status = config.downstream_supervision_dir / "status.json"
    pid = payload.get("pid")
    if (
        payload.get("schema_version") != DOWNSTREAM_RECEIPT_SCHEMA_VERSION
        or payload.get("status") != "detached_relay_started"
        or not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or payload.get("command") != expected_command
        or payload.get("command_sha256") != stable_sha256(expected_command)
        or payload.get("log_path") != str(expected_log)
        or payload.get("status_path") != str(expected_status)
        or payload.get("preflight_completed_before_process_start") is not True
        or not _is_aware_iso_timestamp(payload.get("started_at_utc"))
    ):
        raise DownstreamReceiptError(
            "Le reçu aval ne prouve pas le démarrage de la commande attendue"
        )
    return payload


def _prevent_sleep(enabled: bool) -> None:
    if os.name != "nt":
        return
    es_continuous = 0x80000000
    es_system_required = 0x00000001
    es_awaymode_required = 0x00000040
    flags = es_continuous
    if enabled:
        flags |= es_system_required | es_awaymode_required
    if not ctypes.windll.kernel32.SetThreadExecutionState(flags):  # type: ignore[attr-defined]
        raise OSError("SetThreadExecutionState a échoué")


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.touch(exist_ok=True)
    handle = path.open("r+b")
    locked = False
    try:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - exercised on POSIX CI only
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise HandoffRelayError("Un relais handoff V6 est déjà actif") from exc
        yield
    finally:
        if locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


class HoldoutCampaignOnceRelay:
    def __init__(
        self,
        config: RelayConfig,
        *,
        launcher: Launcher = _default_launcher,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        prevent_sleep: Callable[[bool], None] = _prevent_sleep,
        background_reservation_token: str = "",
    ) -> None:
        self.config = config.resolved()
        self.launcher = launcher
        self.sleep = sleep
        self.monotonic = monotonic
        self.prevent_sleep = prevent_sleep
        self.background_reservation_token = background_reservation_token
        self.contract: dict[str, Any] = {}
        self.status_path = self.config.handoff_supervision_dir / "status.json"
        self.journal_path = self.config.handoff_supervision_dir / "journal.json"
        self.contract_path = self.config.handoff_supervision_dir / "contract.json"
        self.reservation_path = (
            self.config.handoff_supervision_dir / "launch_reservation.json"
        )

    def _prepare(self, inventory: Mapping[str, Any]) -> None:
        root = self.config.handoff_supervision_dir
        root.mkdir(parents=True, exist_ok=True)
        expected = _contract_payload(self.config, inventory)
        if self.contract_path.exists():
            actual = _read_json(self.contract_path)
            _verify_signature(actual, "contract_signature", "contrat du relais")
            if actual != expected:
                raise HandoffRelayError("Supervision existante liée à un autre contrat")
            self.contract = actual
        else:
            unknown = [
                item.name
                for item in root.iterdir()
                if item.name
                not in {".handoff.lock", "watcher_detached.json", "watcher.log"}
            ]
            if unknown:
                raise HandoffRelayError(
                    "Supervision non enregistrée non vide : " + ", ".join(unknown)
                )
            self.contract = expected
            _atomic_json(self.contract_path, expected)
        self._validate_background_handoff()
        if self.reservation_path.exists():
            reservation = _read_json(self.reservation_path)
            _verify_signature(
                reservation, "reservation_signature", "réservation de lancement"
            )
            raise HandoffRelayError(
                "L'unique tentative de lancement aval a déjà été réservée"
            )
        if self.status_path.exists():
            status = _read_json(self.status_path)
            _verify_signature(status, "status_signature", "status du relais")
            if status.get("contract_signature") != self.contract["contract_signature"]:
                raise HandoffRelayError("Status existant lié à un autre contrat")
            if status.get("status") not in {"waiting", "initialized"}:
                raise HandoffRelayError(
                    f"Relais déjà terminal : {status.get('status')}"
                )
        self._ensure_journal()

    def _validate_background_handoff(self) -> None:
        receipt_path = self.config.handoff_supervision_dir / "watcher_detached.json"
        if not receipt_path.exists():
            if self.background_reservation_token:
                raise HandoffRelayError(
                    "Réservation du parent --background absente pour cet enfant"
                )
            return
        receipt = _read_json(receipt_path)
        _verify_signature(receipt, "background_signature", "reçu du parent background")
        token = self.background_reservation_token
        if not token:
            raise HandoffRelayError(
                "Un parent --background a réservé cette supervision"
            )
        expected_command = _foreground_command(self.config, token)
        background_status = receipt.get("status")
        expected_pid = (
            0 if background_status == "watcher_start_reserved" else os.getpid()
        )
        if (
            not _is_sha256(token)
            or receipt.get("schema_version") != BACKGROUND_SCHEMA_VERSION
            or receipt.get("contract_signature") != self.contract["contract_signature"]
            or receipt.get("reservation_token") != token
            or background_status not in {"watcher_start_reserved", "watcher_started"}
            or receipt.get("pid") != expected_pid
            or receipt.get("command") != expected_command
            or receipt.get("command_sha256") != stable_sha256(expected_command)
            or receipt.get("log_path")
            != str(self.config.handoff_supervision_dir / "watcher.log")
            or receipt.get("status_path") != str(self.status_path)
            or not _is_aware_iso_timestamp(receipt.get("created_at_utc"))
        ):
            raise HandoffRelayError("Réservation parent-enfant --background invalide")

    def _ensure_journal(self) -> None:
        if self.journal_path.exists():
            journal = _read_json(self.journal_path)
            _verify_signature(journal, "journal_signature", "journal du relais")
            if journal.get("contract_signature") != self.contract["contract_signature"]:
                raise HandoffRelayError("Journal existant lié à un autre contrat")
            return
        unsigned = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "events": [],
        }
        _atomic_json(self.journal_path, _signed(unsigned, "journal_signature"))

    def _record(self, event: str, **details: Any) -> None:
        journal = _read_json(self.journal_path)
        _verify_signature(journal, "journal_signature", "journal du relais")
        events = journal.get("events")
        if not isinstance(events, list):
            raise HandoffRelayError("Journal du relais invalide")
        unsigned = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "events": [
                *events,
                {"at_utc": _now(), "event": event, "details": details},
            ],
        }
        _atomic_json(self.journal_path, _signed(unsigned, "journal_signature"))

    def _write_status(
        self, status: str, message: str, **details: Any
    ) -> dict[str, Any]:
        unsigned = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "status": status,
            "message": message,
            "relay_pid": os.getpid(),
            "updated_at_utc": _now(),
            **details,
        }
        payload = _signed(unsigned, "status_signature")
        _atomic_json(self.status_path, payload)
        self._record(status, message=message, **details)
        return payload

    def _stop(
        self, status: str, message: str, exc_type: type[HandoffRelayError]
    ) -> None:
        self._write_status(status, message, downstream_started=False)
        raise exc_type(message)

    def _read_calibration_decision(self) -> str:
        if not self.config.calibration_status.is_file():
            return ""
        payload = _read_json(self.config.calibration_status)
        return _validate_calibration_status(payload, self.config)

    def _reserve_launch(
        self,
        command: Sequence[str],
        calibration_signature: str,
        inventory: Mapping[str, Any],
    ) -> dict[str, Any]:
        unsigned = {
            "schema_version": RESERVATION_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "status": "launch_reserved",
            "attempt": 1,
            "reserved_at_utc": _now(),
            "calibration_status_signature": calibration_signature,
            "command": list(command),
            "command_sha256": stable_sha256(list(command)),
            "protected_inventory": inventory,
        }
        payload = _signed(unsigned, "reservation_signature")
        try:
            with self.reservation_path.open(
                "x", encoding="utf-8", newline="\n"
            ) as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise HandoffRelayError(
                "Tentative aval déjà réservée par un autre relais"
            ) from exc
        return payload

    def execute(self) -> dict[str, Any]:
        inventory = _assert_integrity(self.config)
        self.config.handoff_supervision_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_lock(self.config.handoff_supervision_dir / ".handoff.lock"):
            self._prepare(inventory)
            self._write_status(
                "initialized",
                "Intégrité initiale validée; attente de la décision holdout signée.",
                downstream_started=False,
            )
            started = self.monotonic()
            sleep_enabled = False
            try:
                try:
                    self.prevent_sleep(True)
                except Exception as exc:
                    self._write_status(
                        "stopped_sleep_inhibitor_unavailable",
                        str(exc),
                        downstream_started=False,
                    )
                    raise
                sleep_enabled = True
                while True:
                    try:
                        calibration_signature = self._read_calibration_decision()
                    except CalibrationRejected as exc:
                        self._stop(
                            "stopped_calibration_rejected",
                            str(exc),
                            CalibrationRejected,
                        )
                    except HandoffRelayError as exc:
                        self._stop(
                            "stopped_invalid_calibration_status",
                            str(exc),
                            HandoffRelayError,
                        )
                    if calibration_signature:
                        break
                    elapsed = self.monotonic() - started
                    if elapsed >= self.config.wait_timeout_hours * 3600:
                        self._stop(
                            "stopped_timeout",
                            "Délai expiré sans autorisation calibration signée.",
                            HandoffTimeout,
                        )
                    self._write_status(
                        "waiting",
                        "Calibration V6 en cours; aucune campagne aval lancée.",
                        elapsed_seconds=round(elapsed, 3),
                        downstream_started=False,
                    )
                    self.sleep(
                        min(
                            self.config.poll_seconds,
                            self.config.wait_timeout_hours * 3600 - elapsed,
                        )
                    )

                # Full second gate immediately before the irreversible one-shot call.
                try:
                    final_inventory = _assert_integrity(self.config)
                except HandoffRelayError as exc:
                    self._stop(
                        "stopped_prelaunch_integrity_or_destination_changed",
                        str(exc),
                        HandoffRelayError,
                    )
                try:
                    second_signature = self._read_calibration_decision()
                except HandoffRelayError as exc:
                    self._stop(
                        "stopped_calibration_changed_before_launch",
                        str(exc),
                        type(exc),
                    )
                if second_signature != calibration_signature:
                    self._stop(
                        "stopped_calibration_changed_before_launch",
                        "Le status calibration a changé entre les deux validations.",
                        HandoffRelayError,
                    )
                command = downstream_command(self.config)
                self._reserve_launch(command, calibration_signature, final_inventory)
                self._write_status(
                    "launch_reserved",
                    "Tentative unique réservée; appel du préflight public aval.",
                    downstream_started=False,
                    calibration_status_signature=calibration_signature,
                    command_sha256=stable_sha256(command),
                )
                try:
                    result = self.launcher(command, self.config)
                    receipt = _validate_downstream_receipt(result, self.config)
                except DownstreamLaunchRejected as exc:
                    self._write_status(
                        "downstream_preflight_rejected_no_retry",
                        str(exc),
                        downstream_started=False,
                        downstream_start_confirmed=False,
                        launch_attempt_consumed=True,
                    )
                    raise HandoffRelayError(
                        "Tentative aval consommée et non renouvelable; diagnostic requis"
                    ) from exc
                except subprocess.TimeoutExpired as exc:
                    self._write_status(
                        "downstream_detach_timeout_outcome_unknown_no_retry",
                        str(exc),
                        downstream_started=None,
                        downstream_start_confirmed=False,
                        launch_attempt_consumed=True,
                    )
                    raise HandoffRelayError(
                        "Tentative aval expirée; démarrage non prouvé et aucun nouvel essai autorisé"
                    ) from exc
                except DownstreamReceiptError as exc:
                    self._write_status(
                        "downstream_receipt_invalid_outcome_unknown_no_retry",
                        str(exc),
                        downstream_started=None,
                        downstream_start_confirmed=False,
                        launch_attempt_consumed=True,
                    )
                    raise HandoffRelayError(
                        "Tentative aval consommée sans reçu fiable; aucun nouvel essai autorisé"
                    ) from exc
                except Exception as exc:
                    self._write_status(
                        "downstream_detach_failed_outcome_unknown_no_retry",
                        str(exc),
                        downstream_started=None,
                        downstream_start_confirmed=False,
                        launch_attempt_consumed=True,
                    )
                    raise HandoffRelayError(
                        "Tentative aval consommée; résultat inconnu et aucun nouvel essai autorisé"
                    ) from exc
                return self._write_status(
                    "downstream_detach_started",
                    "Le relais aval V6 a refait son préflight et démarré en mode détaché.",
                    downstream_started=True,
                    downstream_start_confirmed=True,
                    launch_attempt_consumed=True,
                    downstream_pid=int(receipt["pid"]),
                    downstream_receipt=receipt,
                )
            finally:
                if sleep_enabled:
                    self.prevent_sleep(False)


def _config_from_args(args: argparse.Namespace) -> RelayConfig:
    return RelayConfig(
        repo=args.repo,
        calibration_status=args.calibration_status,
        handoff_supervision_dir=args.handoff_supervision_dir,
        v4_plan_dir=args.v4_plan_dir,
        v4_run_dir=args.v4_run_dir,
        v4_sidecar_root=args.v4_sidecar_root,
        calibration_plan_dir=args.calibration_plan_dir,
        calibration_run_dir=args.calibration_run_dir,
        sidecar_dir=args.sidecar_dir,
        bridge_json=args.bridge_json,
        campaign_root=args.campaign_root,
        results_dir=args.results_dir,
        lot_replay_root=args.lot_replay_root,
        qualification_dir=args.qualification_dir,
        action_replay_root=args.action_replay_root,
        dashboard_html=args.dashboard_html,
        final_html=args.final_html,
        downstream_supervision_dir=args.downstream_supervision_dir,
        legacy_risk_html=args.legacy_risk_html,
        legacy_control_html=args.legacy_control_html,
        calibration_workers=args.calibration_workers,
        parallel_shards=args.parallel_shards,
        workers_per_shard=args.workers_per_shard,
        launcher_poll_seconds=args.launcher_poll_seconds,
        relay_poll_seconds=args.relay_poll_seconds,
        watcher_ready_timeout_seconds=args.watcher_ready_timeout_seconds,
        sidecar_poll_ms=args.sidecar_poll_ms,
        sidecar_stability_ms=args.sidecar_stability_ms,
        downstream_max_wait_hours=args.downstream_max_wait_hours,
        wait_timeout_hours=args.wait_timeout_hours,
        poll_seconds=args.poll_seconds,
        detach_invocation_timeout_seconds=args.detach_invocation_timeout_seconds,
    ).resolved()


def _foreground_command(config: RelayConfig, reservation_token: str) -> list[str]:
    command = [sys.executable, "-m", THIS_MODULE]
    for field in fields(config):
        value = getattr(config, field.name)
        command.extend([f"--{field.name.replace('_', '-')}", str(value)])
    command.extend(
        [
            "--foreground-child",
            "--background-reservation-token",
            reservation_token,
        ]
    )
    return command


def start_background(args: argparse.Namespace) -> dict[str, Any]:
    config = _config_from_args(args)
    inventory = _assert_integrity(config)
    config.handoff_supervision_dir.mkdir(parents=True, exist_ok=True)
    relay = HoldoutCampaignOnceRelay(config)
    with _exclusive_lock(config.handoff_supervision_dir / ".handoff.lock"):
        relay._prepare(inventory)  # noqa: SLF001 - same module handoff boundary
        receipt_path = config.handoff_supervision_dir / "watcher_detached.json"
        if receipt_path.exists():
            raise HandoffRelayError("Un reçu de watcher détaché existe déjà")
        reservation_token = stable_sha256(
            {
                "contract_signature": relay.contract["contract_signature"],
                "nonce": uuid4().hex,
                "created_at_utc": _now(),
            }
        )
        command = _foreground_command(config, reservation_token)
        log_path = config.handoff_supervision_dir / "watcher.log"
        reserved_unsigned = {
            "schema_version": BACKGROUND_SCHEMA_VERSION,
            "status": "watcher_start_reserved",
            "pid": 0,
            "contract_signature": relay.contract["contract_signature"],
            "reservation_token": reservation_token,
            "command": command,
            "command_sha256": stable_sha256(command),
            "log_path": str(log_path),
            "status_path": str(relay.status_path),
            "created_at_utc": _now(),
        }
        _atomic_json(receipt_path, _signed(reserved_unsigned, "background_signature"))
    # The child needs the same OS lock for its whole lifetime.  Release the
    # short parent reservation lock before spawning it; the signed receipt now
    # prevents a second background parent from reaching this point.
    try:
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
    except BaseException as exc:
        failed = {
            **reserved_unsigned,
            "status": "watcher_start_failed_no_retry",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _atomic_json(receipt_path, _signed(failed, "background_signature"))
        raise
    started = {
        **reserved_unsigned,
        "status": "watcher_started",
        "pid": process.pid,
        "log_path": str(log_path),
    }
    payload = _signed(started, "background_signature")
    _atomic_json(receipt_path, payload)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--calibration-status", type=Path, required=True)
    parser.add_argument("--handoff-supervision-dir", type=Path, required=True)
    parser.add_argument("--v4-plan-dir", type=Path, required=True)
    parser.add_argument("--v4-run-dir", type=Path, required=True)
    parser.add_argument("--v4-sidecar-root", type=Path, required=True)
    parser.add_argument("--calibration-plan-dir", type=Path, required=True)
    parser.add_argument("--calibration-run-dir", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument("--bridge-json", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--lot-replay-root", type=Path, required=True)
    parser.add_argument("--qualification-dir", type=Path, required=True)
    parser.add_argument("--action-replay-root", type=Path, required=True)
    parser.add_argument("--dashboard-html", type=Path, required=True)
    parser.add_argument("--final-html", type=Path, required=True)
    parser.add_argument("--downstream-supervision-dir", type=Path, required=True)
    parser.add_argument("--legacy-risk-html", type=Path, required=True)
    parser.add_argument("--legacy-control-html", type=Path, required=True)
    parser.add_argument("--calibration-workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--launcher-poll-seconds", type=float, default=5.0)
    parser.add_argument("--relay-poll-seconds", type=float, default=30.0)
    parser.add_argument("--watcher-ready-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--sidecar-poll-ms", type=float, default=25.0)
    parser.add_argument("--sidecar-stability-ms", type=float, default=12.0)
    parser.add_argument("--downstream-max-wait-hours", type=float, default=240.0)
    parser.add_argument("--wait-timeout-hours", type=float, default=12.0)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument(
        "--detach-invocation-timeout-seconds", type=float, default=600.0
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--background", action="store_true")
    mode.add_argument("--foreground-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--background-reservation-token", default="", help=argparse.SUPPRESS
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    args = _parser().parse_args(raw)
    try:
        if args.background:
            if args.background_reservation_token:
                raise HandoffRelayError(
                    "Le jeton --background est généré exclusivement par le parent"
                )
            payload = start_background(args)
        else:
            if bool(args.foreground_child) != bool(args.background_reservation_token):
                raise HandoffRelayError(
                    "Le marqueur enfant et sa réservation --background sont indissociables"
                )
            payload = HoldoutCampaignOnceRelay(
                _config_from_args(args),
                background_reservation_token=args.background_reservation_token,
            ).execute()
    except CalibrationRejected as exc:
        print(f"RELAIS HANDOFF V6 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except HandoffTimeout as exc:
        print(f"RELAIS HANDOFF V6 TIMEOUT : {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"RELAIS HANDOFF V6 NON LANCÉ : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
