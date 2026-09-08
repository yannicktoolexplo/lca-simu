#!/usr/bin/env python3
"""Wait for the official V7 decision, then resume the downstream campaign.

This outer watcher may be armed while the 450-case V7 validation is running.
Once the signed progress is exactly ``complete_pending_finalization``, it uses
the frozen V7 finalizer under the V7 run lock, then reconstructs the complete
decision.  Before an accepted result is fully reconstructed, it may write only
its own watcher supervision and protocol-owned finalization files confined to
the V7 run (the decision and any already-due descriptive checkpoint).
It never runs an engine and never creates trace, bridge, campaign, result, or
downstream-relay supervision paths before acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v5 as relay_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v7 as relay_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


SCHEMA_VERSION = "etudecas.supplier_v7_acceptance_watcher.v1"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
RECEIPT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.detached.v2"
DETACHED_STARTUP_TIMEOUT_SECONDS = 600.0
DETACHED_STARTUP_POLL_SECONDS = 0.1
MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control."
    "watch_then_continue_supplier_full_campaign_v7"
)
PRE_ACCEPTANCE_STAGES = frozenset(
    {
        "armed_waiting_for_v7",
        "waiting_for_v7_result",
        "waiting_timeout",
        "scientific_no_go",
        "invalid_final_v7_result",
        "watcher_failed_before_acceptance",
    }
)

FullCampaignRelayError = relay_v7.FullCampaignRelayError
ScientificNoGo = relay_v7.ScientificNoGo


class WatcherTimeout(FullCampaignRelayError):
    """The configured wait elapsed without a finalized V7 decision."""


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


@dataclass(frozen=True)
class V7AcceptanceWatcherConfig:
    relay: relay_v7.V7CampaignRelayConfig
    watcher_supervision_dir: Path
    acceptance_poll_seconds: float = 30.0
    acceptance_max_wait_hours: float = 240.0

    def resolved(self) -> "V7AcceptanceWatcherConfig":
        return V7AcceptanceWatcherConfig(
            relay=self.relay.resolved(),
            watcher_supervision_dir=self.watcher_supervision_dir.resolve(),
            acceptance_poll_seconds=self.acceptance_poll_seconds,
            acceptance_max_wait_hours=self.acceptance_max_wait_hours,
        )

    def public_mapping(self) -> dict[str, Any]:
        return {
            "relay": self.relay.public_mapping(),
            "watcher_supervision_dir": str(self.watcher_supervision_dir),
            "acceptance_poll_seconds": self.acceptance_poll_seconds,
            "acceptance_max_wait_hours": self.acceptance_max_wait_hours,
        }

    def validate(self) -> None:
        self.relay.validate()
        watcher = self.watcher_supervision_dir
        if watcher.exists() and not watcher.is_dir():
            raise FullCampaignRelayError(
                f"La supervision du watcher n'est pas un dossier : {watcher}"
            )
        if not 0.1 <= self.acceptance_poll_seconds <= 300.0:
            raise FullCampaignRelayError(
                "acceptance_poll_seconds doit être compris entre 0,1 et 300"
            )
        if self.acceptance_max_wait_hours <= 0:
            raise FullCampaignRelayError(
                "acceptance_max_wait_hours doit être strictement positif"
            )
        protected = (
            self.relay.repo,
            self.relay.v7_plan_dir,
            self.relay.v7_run_dir,
            self.relay.trace_package_dir,
            self.relay.bridge_json,
            self.relay.campaign_root,
            self.relay.results_dir,
            self.relay.supervision_dir,
        )
        if any(_paths_overlap(watcher, path) for path in protected):
            raise FullCampaignRelayError(
                "La supervision du watcher doit être séparée de toutes les sources "
                "et sorties V7"
            )


class V7AcceptanceWatcher:
    """Signed, crash-resumable handoff from a V7 result to the V7 relay."""

    def __init__(
        self,
        config: V7AcceptanceWatcherConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config.resolved()
        self.sleep = sleep
        self.monotonic = monotonic
        root = self.config.watcher_supervision_dir
        self.contract_path = root / "watcher_contract.json"
        self.status_path = root / "status.json"
        self.receipt_path = root / "detached.json"
        self.log_path = root / "detached_watcher.log"
        self.lock_path = root / ".watcher.lock"
        self.contract: dict[str, Any] = {}
        self.status: dict[str, Any] = {}

    def _downstream_paths(self) -> tuple[Path, ...]:
        relay = self.config.relay
        return (
            relay.trace_package_dir,
            relay.bridge_json,
            relay.campaign_root,
            relay.results_dir,
            relay.supervision_dir,
        )

    def _assert_downstream_absent(self) -> None:
        present = [str(path) for path in self._downstream_paths() if path.exists()]
        if present:
            raise FullCampaignRelayError(
                "Une sortie aval existe avant l'acceptation V7 : " + ", ".join(present)
            )

    def _source_inventory(self) -> list[dict[str, str]]:
        relay = relay_v7.FullCampaignRelayV7(self.config.relay)
        rows = relay._module_inventory_v7()  # noqa: SLF001
        path = Path(__file__).resolve()
        rows.append(
            {
                "module": MODULE_NAME,
                "path": str(path),
                "sha256": relay_v7.relay_v4.sha256_file(path),
            }
        )
        return rows

    def _build_contract(self) -> dict[str, Any]:
        trace_package.validate_frozen_v7_protocol()
        plan = protocol_v7.validate_plan(
            self.config.relay.v7_plan_dir,
            allow_test_source=False,
            verify_runtime=True,
        )
        plan_path = plan.plan_dir / "protocol_manifest.json"
        unsigned = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "configuration": self.config.public_mapping(),
            "source_inventory": self._source_inventory(),
            "v7_plan": {
                "path": str(plan_path.resolve()),
                "sha256": relay_v7.relay_v4.sha256_file(plan_path),
                "plan_signature": plan.manifest["plan_signature"],
                "protocol_sha256": trace_package.EXPECTED_V7_PROTOCOL_SHA256,
            },
            "handoff_contract": {
                "waiter_runs_v7_engine": False,
                "waiter_finalizes_v7": True,
                "finalization_only_after_signed_450_case_progress": True,
                "v7_run_lock_required_for_finalization": True,
                "full_validation_required_after_result_appears": True,
                "accepted_result_required_before_relay": True,
                "downstream_writes_before_acceptance": False,
                "preacceptance_writes": [
                    "watcher_supervision",
                    (
                        "protocol_owned_finalization_files_inside_v7_run_only_"
                        "after_signed_450_of_450"
                    ),
                ],
                "relay_runs_in_foreground_child_context": True,
                "same_30_first_v7_seeds_for_baseline_and_incidents": True,
                "validation_seed_count": relay_v7.EXPECTED_VALIDATION_SEEDS,
                "validation_case_count": relay_v7.EXPECTED_VALIDATION_CASES,
                "campaign_seed_count": relay_v7.EXPECTED_CAMPAIGN_SEEDS,
                "campaign_baseline_trace_count": relay_v7.EXPECTED_BASELINE_TRACES,
                "campaign_total_row_count": relay_v7.EXPECTED_CAMPAIGN_ROWS,
            },
        }
        return {
            **unsigned,
            "contract_signature": relay_v7.relay_v4.stable_sha256(unsigned),
        }

    def _assert_source_inventory_unchanged(self) -> None:
        if not self.contract or self._source_inventory() != self.contract.get(
            "source_inventory"
        ):
            raise FullCampaignRelayError(
                "Le code aval V7 a changé pendant l'attente; reprise auditée requise"
            )

    @staticmethod
    def _write_exclusive_json(path: Path, payload: Mapping[str, Any]) -> None:
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise FullCampaignRelayError(
                f"Un autre watcher a publié simultanément : {path}"
            ) from exc

    def _write_status(self) -> None:
        self.status["watcher_pid"] = os.getpid()
        self.status["updated_at_utc"] = relay_v7.relay_v4._now()  # noqa: SLF001
        unsigned = dict(self.status)
        unsigned.pop("status_signature", None)
        payload = {
            **unsigned,
            "status_signature": relay_v7.relay_v4.stable_sha256(unsigned),
        }
        self.status = payload
        relay_v7.relay_v4._atomic_json(self.status_path, payload)  # noqa: SLF001

    def update_status(
        self,
        stage: str,
        message_fr: str,
        *,
        status: str = "running",
        progress: Mapping[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.status.update({"status": status, "stage": stage, "message_fr": message_fr})
        if progress is not None:
            self.status["progress"] = dict(progress)
        if error is not None:
            self.status["error"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
        else:
            self.status.pop("error", None)
        self._write_status()

    def prepare(self) -> None:
        self.config.validate()
        is_new = not self.contract_path.exists()
        if is_new:
            self._assert_downstream_absent()
        expected = self._build_contract()
        root = self.config.watcher_supervision_dir
        root.mkdir(parents=True, exist_ok=True)
        if self.contract_path.is_file():
            actual = relay_v7.relay_v4._read_json(self.contract_path)  # noqa: SLF001
            relay_v7.relay_v4._verify_signed_json(  # noqa: SLF001
                actual, "contract_signature", "contrat du watcher V7"
            )
            if actual != expected:
                raise FullCampaignRelayError(
                    "Le contrat du watcher a changé; nouvelle supervision requise"
                )
            self.contract = actual
        else:
            allowed = {self.lock_path.name}
            if any(path.name not in allowed for path in root.iterdir()):
                raise FullCampaignRelayError(
                    "La supervision neuve du watcher n'est pas vide"
                )
            self.contract = expected
            self._write_exclusive_json(self.contract_path, expected)

        if self.status_path.is_file():
            payload = relay_v7.relay_v4._read_json(self.status_path)  # noqa: SLF001
            relay_v7.relay_v4._verify_signed_json(  # noqa: SLF001
                payload, "status_signature", "statut du watcher V7"
            )
            if (
                payload.get("schema_version") != STATUS_SCHEMA_VERSION
                or payload.get("contract_signature")
                != self.contract["contract_signature"]
            ):
                raise FullCampaignRelayError("Statut du watcher étranger au contrat")
            self.status = payload
        else:
            self._assert_downstream_absent()
            self.status = {
                "schema_version": STATUS_SCHEMA_VERSION,
                "contract_signature": self.contract["contract_signature"],
                "status": "waiting",
                "stage": "armed_waiting_for_v7",
                "message_fr": (
                    "Watcher armé; aucune sortie aval avant une acceptation V7 "
                    "entièrement revalidée."
                ),
                "started_at_utc": relay_v7.relay_v4._now(),  # noqa: SLF001
                "completed_at_utc": "",
                "progress": {"poll_count": 0, "result_present": False},
            }
            self._write_status()

        if self.status.get("stage") in PRE_ACCEPTANCE_STAGES:
            self._assert_downstream_absent()

    def _progress_snapshot(self) -> dict[str, Any]:
        path = self.config.relay.v7_run_dir / "progress.json"
        if not path.is_file():
            return {}
        payload = relay_v7.relay_v4._read_json(path)  # noqa: SLF001
        unsigned = dict(payload)
        signature = str(unsigned.pop("progress_signature", ""))
        if signature != protocol_v7.stable_sha256(unsigned):
            raise FullCampaignRelayError("Signature de progression V7 incohérente")
        plan_signature = self.contract["v7_plan"]["plan_signature"]
        completed = payload.get("completed_case_count")
        complete_blocks = payload.get("completed_seed_block_count")
        if (
            payload.get("schema_version") != protocol_v7.PROGRESS_SCHEMA_VERSION
            or payload.get("plan_signature") != plan_signature
            or payload.get("execution_mode") != protocol_v7.OFFICIAL_EXECUTION_MODE
            or payload.get("publishable") is not True
            or payload.get("expected_case_count") != relay_v7.EXPECTED_VALIDATION_CASES
            or payload.get("expected_seed_block_count")
            != relay_v7.EXPECTED_VALIDATION_SEEDS
            or not isinstance(completed, int)
            or not 0 <= completed <= relay_v7.EXPECTED_VALIDATION_CASES
            or not isinstance(complete_blocks, int)
            or not 0 <= complete_blocks <= relay_v7.EXPECTED_VALIDATION_SEEDS
        ):
            raise FullCampaignRelayError("Contrat de progression V7 incohérent")
        return payload

    def _try_finalize_v7_if_eligible(self) -> bool:
        """Finalize under V7's own lock, never before its signed 450/450 state."""

        progress = self._progress_snapshot()
        if not progress or (
            progress.get("status") != "complete_pending_finalization"
            or progress.get("completed_case_count")
            != relay_v7.EXPECTED_VALIDATION_CASES
            or progress.get("completed_seed_block_count")
            != relay_v7.EXPECTED_VALIDATION_SEEDS
            or progress.get("decision_status") != "eligible_for_finalization_only"
        ):
            return False
        self._assert_source_inventory_unchanged()
        status = protocol_v7.validation_status(
            self.config.relay.v7_plan_dir,
            self.config.relay.v7_run_dir,
            test_only=False,
        )
        result_path = self.config.relay.v7_run_dir / "validation_result.json"
        if (
            status.get("status") == "finalized"
            and status.get("acceptance_decision_available") is True
            and result_path.is_file()
        ):
            return True
        if (
            status.get("status") != "complete_pending_finalization"
            or status.get("completed_case_count") != relay_v7.EXPECTED_VALIDATION_CASES
            or status.get("missing_case_count") != 0
            or status.get("completed_seed_block_count")
            != relay_v7.EXPECTED_VALIDATION_SEEDS
            or status.get("acceptance_decision_available") is not False
            or status.get("engine_runs_started_by_monitor") != 0
        ):
            raise FullCampaignRelayError(
                "Le contrôle lecture seule V7 n'autorise pas la finalisation"
            )
        try:
            protocol_v7.finalize_validation(
                self.config.relay.v7_plan_dir,
                self.config.relay.v7_run_dir,
                test_only=False,
            )
        except protocol_v7.V7ProtocolError as exc:
            if "Another V7 process holds the run lock" in str(exc):
                return False
            raise
        if not result_path.is_file():
            raise FullCampaignRelayError(
                "Le finaliseur V7 n'a pas publié sa décision attendue"
            )
        return True

    def wait_for_acceptance(self) -> dict[str, Any]:
        """Wait, finalize an eligible run, then perform the complete V7 readback."""

        result_path = self.config.relay.v7_run_dir / "validation_result.json"
        deadline = self.monotonic() + self.config.acceptance_max_wait_hours * 3600.0
        poll_count = int((self.status.get("progress") or {}).get("poll_count") or 0)
        while True:
            if self.status.get("stage") in PRE_ACCEPTANCE_STAGES:
                self._assert_downstream_absent()
            if result_path.is_file():
                self._assert_source_inventory_unchanged()
                relay = relay_v7.FullCampaignRelayV7(self.config.relay)
                try:
                    handoff = relay.validate_v7_handoff()
                except ScientificNoGo as exc:
                    self._assert_downstream_absent()
                    self.update_status(
                        "scientific_no_go",
                        "V7 a rejeté le triplet; aucune campagne aval n'est créée.",
                        status="scientific_no_go",
                        progress={
                            "poll_count": poll_count,
                            "result_present": True,
                            "downstream_started": False,
                        },
                        error=exc,
                    )
                    raise
                except Exception as exc:
                    self._assert_downstream_absent()
                    self.update_status(
                        "invalid_final_v7_result",
                        (
                            "Le fichier final V7 existe mais sa reconstruction "
                            "intégrale échoue; arrêt sans sortie aval."
                        ),
                        status="failed_closed",
                        progress={
                            "poll_count": poll_count,
                            "result_present": True,
                            "downstream_started": False,
                        },
                        error=exc,
                    )
                    raise
                self.update_status(
                    "v7_accepted_and_revalidated",
                    (
                        "Les 450 preuves V7 et la décision acceptée sont revalidées; "
                        "le relais aval est maintenant autorisé."
                    ),
                    progress={
                        "poll_count": poll_count,
                        "result_present": True,
                        "accepted": True,
                        "validation_case_count": relay_v7.EXPECTED_VALIDATION_CASES,
                        "result_signature": handoff["result_signature"],
                        "downstream_started": False,
                    },
                )
                return handoff

            if self._try_finalize_v7_if_eligible():
                continue

            poll_count += 1
            if self.monotonic() >= deadline:
                self._assert_downstream_absent()
                exc = WatcherTimeout(
                    "Le résultat V7 n'est pas finalisé avant la limite d'attente"
                )
                self.update_status(
                    "waiting_timeout",
                    (
                        "Temps d'attente écoulé; le watcher peut être repris avec "
                        "le même contrat. Aucune sortie aval n'a été créée."
                    ),
                    status="waiting_timeout",
                    progress={
                        "poll_count": poll_count,
                        "result_present": False,
                        "downstream_started": False,
                    },
                    error=exc,
                )
                raise exc
            self.update_status(
                "waiting_for_v7_result",
                (
                    "Validation V7 en cours, ou attente de libération du verrou "
                    "avant décision; aucune sortie aval n'est créée."
                ),
                status="waiting",
                progress={
                    "poll_count": poll_count,
                    "result_present": False,
                    "downstream_started": False,
                },
            )
            self.sleep(self.config.acceptance_poll_seconds)

    def execute(self, *, prepared: bool = False) -> int:
        if not prepared:
            self.prepare()
        handoff = self.wait_for_acceptance()
        self._assert_source_inventory_unchanged()
        self.update_status(
            "relay_v7_running",
            "Acceptation acquise; exécution ou reprise du relais campagne V7.",
            progress={
                "result_signature": handoff["result_signature"],
                "downstream_started": True,
            },
        )
        relay = relay_v7.FullCampaignRelayV7(self.config.relay)
        with relay_v5._relay_lock(  # noqa: SLF001
            self.config.relay.supervision_dir / ".relay.lock"
        ):
            return_code = relay.execute()
        if return_code != 0:
            raise FullCampaignRelayError(
                f"Le relais campagne V7 retourne le code {return_code}"
            )
        self.status["completed_at_utc"] = relay_v7.relay_v4._now()  # noqa: SLF001
        self.update_status(
            "campaign_v7_complete",
            "Campagne V7 consolidée : 3 330 cas; livraison détaillée encore séparée.",
            status="complete_campaign_results_pending_delivery_stage",
            progress={
                "result_signature": handoff["result_signature"],
                "downstream_started": True,
                "baseline_traces": relay_v7.EXPECTED_BASELINE_TRACES,
                "incident_rows": relay_v7.EXPECTED_INCIDENT_ROWS,
                "campaign_rows": relay_v7.EXPECTED_CAMPAIGN_ROWS,
            },
        )
        return 0

    def validate_detached_token(self, token: str) -> None:
        if not token:
            raise FullCampaignRelayError("Jeton du watcher détaché absent")
        receipt = relay_v7.relay_v4._read_json(self.receipt_path)  # noqa: SLF001
        relay_v7.relay_v4._verify_signed_json(  # noqa: SLF001
            receipt, "receipt_signature", "reçu du watcher V7"
        )
        if (
            receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
            or receipt.get("launch_token") != token
            or receipt.get("status") != "detached_start_reserved"
            or receipt.get("configuration_sha256")
            != relay_v7.relay_v4.stable_sha256(self.config.public_mapping())
        ):
            raise FullCampaignRelayError("Jeton ou reçu du watcher détaché invalide")

    def publish_detached_ready(self, token: str) -> dict[str, Any]:
        """Publish readiness only after prepare, while owning the watcher lock."""

        self.validate_detached_token(token)
        if not self.contract or not self.status:
            raise FullCampaignRelayError("Watcher détaché non préparé sous verrou")
        receipt = relay_v7.relay_v4._read_json(self.receipt_path)  # noqa: SLF001
        unsigned = {
            **{
                key: value
                for key, value in receipt.items()
                if key != "receipt_signature"
            },
            "status": "detached_watcher_ready",
            "pid": os.getpid(),
            "ready_at_utc": relay_v7.relay_v4._now(),  # noqa: SLF001
            "lock_acquired": True,
            "contract_signature": self.contract["contract_signature"],
        }
        payload = {
            **unsigned,
            "receipt_signature": relay_v7.relay_v4.stable_sha256(unsigned),
        }
        relay_v7.relay_v4._atomic_json(self.receipt_path, payload)  # noqa: SLF001
        return payload


@contextmanager
def _watcher_lock_once(path: Path) -> Iterator[None]:
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
            raise FullCampaignRelayError("Un autre watcher V7 est déjà actif") from exc
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


@contextmanager
def _watcher_lock(path: Path, *, wait_seconds: float = 0.0) -> Iterator[None]:
    """Retry only the short parent/child lock handoff when requested."""

    deadline = time.monotonic() + max(0.0, wait_seconds)
    manager: Any = None
    while True:
        candidate = _watcher_lock_once(path)
        try:
            candidate.__enter__()
        except FullCampaignRelayError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(DETACHED_STARTUP_POLL_SECONDS)
            continue
        manager = candidate
        break
    try:
        yield
    finally:
        manager.__exit__(None, None, None)


def _config_from_args(args: argparse.Namespace) -> V7AcceptanceWatcherConfig:
    relay = relay_v7.V7CampaignRelayConfig(
        repo=args.repo,
        v7_plan_dir=args.v7_plan_dir,
        v7_run_dir=args.v7_run_dir,
        trace_package_dir=args.trace_package_dir,
        bridge_json=args.bridge_json,
        campaign_root=args.campaign_root,
        results_dir=args.results_dir,
        supervision_dir=args.relay_supervision_dir,
        parallel_shards=args.parallel_shards,
        workers_per_shard=args.workers_per_shard,
        launcher_poll_seconds=args.launcher_poll_seconds,
        relay_poll_seconds=args.relay_poll_seconds,
        max_wait_hours=args.relay_max_wait_hours,
    )
    return V7AcceptanceWatcherConfig(
        relay=relay,
        watcher_supervision_dir=args.watcher_supervision_dir,
        acceptance_poll_seconds=args.acceptance_poll_seconds,
        acceptance_max_wait_hours=args.acceptance_max_wait_hours,
    ).resolved()


def _child_command(args: argparse.Namespace, token: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        MODULE_NAME,
        "--repo",
        str(args.repo.resolve()),
        "--v7-plan-dir",
        str(args.v7_plan_dir.resolve()),
        "--v7-run-dir",
        str(args.v7_run_dir.resolve()),
        "--trace-package-dir",
        str(args.trace_package_dir.resolve()),
        "--bridge-json",
        str(args.bridge_json.resolve()),
        "--campaign-root",
        str(args.campaign_root.resolve()),
        "--results-dir",
        str(args.results_dir.resolve()),
        "--relay-supervision-dir",
        str(args.relay_supervision_dir.resolve()),
        "--watcher-supervision-dir",
        str(args.watcher_supervision_dir.resolve()),
        "--parallel-shards",
        str(args.parallel_shards),
        "--workers-per-shard",
        str(args.workers_per_shard),
        "--launcher-poll-seconds",
        str(args.launcher_poll_seconds),
        "--relay-poll-seconds",
        str(args.relay_poll_seconds),
        "--relay-max-wait-hours",
        str(args.relay_max_wait_hours),
        "--acceptance-poll-seconds",
        str(args.acceptance_poll_seconds),
        "--acceptance-max-wait-hours",
        str(args.acceptance_max_wait_hours),
        "--detached-child-token",
        token,
    ]


def _read_watcher_receipt(path: Path) -> dict[str, Any]:
    payload = relay_v7.relay_v4._read_json(path)  # noqa: SLF001
    relay_v7.relay_v4._verify_signed_json(  # noqa: SLF001
        payload, "receipt_signature", "reçu détaché du watcher V7"
    )
    if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise FullCampaignRelayError("Schéma du reçu watcher incohérent")
    return payload


def _publish_watcher_failure(
    path: Path,
    *,
    token: str,
    status: str,
    error: BaseException,
) -> dict[str, Any]:
    current = _read_watcher_receipt(path)
    if current.get("launch_token") != token:
        raise FullCampaignRelayError("Refus de modifier le reçu d'un autre watcher")
    unsigned = {
        **{key: value for key, value in current.items() if key != "receipt_signature"},
        "status": status,
        "error_type": type(error).__name__,
        "error": str(error),
        "failed_at_utc": relay_v7.relay_v4._now(),  # noqa: SLF001
    }
    payload = {
        **unsigned,
        "receipt_signature": relay_v7.relay_v4.stable_sha256(unsigned),
    }
    relay_v7.relay_v4._atomic_json(path, payload)  # noqa: SLF001
    return payload


def _wait_for_watcher_ready(
    process: subprocess.Popen[Any],
    *,
    receipt_path: Path,
    token: str,
    timeout_seconds: float = DETACHED_STARTUP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        receipt = _read_watcher_receipt(receipt_path)
        if (
            receipt.get("status") == "detached_watcher_ready"
            and receipt.get("launch_token") == token
            and receipt.get("pid") == process.pid
            and receipt.get("lock_acquired") is True
            and trace_package.campaign_contract.is_sha256(
                receipt.get("contract_signature")
            )
        ):
            ready_exit_code = process.poll()
            if ready_exit_code not in (None, 0):
                error = FullCampaignRelayError(
                    f"Le watcher a échoué après readiness (code {ready_exit_code})"
                )
                _publish_watcher_failure(
                    receipt_path,
                    token=token,
                    status="detached_child_exited_after_ready",
                    error=error,
                )
                raise error
            return receipt
        return_code = process.poll()
        if return_code is not None:
            error = FullCampaignRelayError(
                f"Le watcher est mort avant readiness (code {return_code})"
            )
            _publish_watcher_failure(
                receipt_path,
                token=token,
                status="detached_child_exited_before_ready",
                error=error,
            )
            raise error
        if time.monotonic() >= deadline:
            relay_v7._stop_detached_tree(process)  # noqa: SLF001
            error = FullCampaignRelayError(
                "Le watcher n'a pas confirmé son verrou avant la limite"
            )
            _publish_watcher_failure(
                receipt_path,
                token=token,
                status="detached_start_timeout",
                error=error,
            )
            raise error
        time.sleep(DETACHED_STARTUP_POLL_SECONDS)


def detach(args: argparse.Namespace) -> dict[str, Any]:
    config = _config_from_args(args)
    config.validate()
    watcher = V7AcceptanceWatcher(config)
    token = uuid4().hex
    with _watcher_lock(watcher.lock_path):
        watcher.prepare()
        if watcher.receipt_path.exists():
            raise FullCampaignRelayError(
                "Un reçu watcher existe déjà; reprendre sans --detach si son PID est arrêté"
            )
        command = _child_command(args, token)
        reserved_unsigned = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "status": "detached_start_reserved",
            "pid": 0,
            "launch_token": token,
            "command": command,
            "command_sha256": relay_v7.relay_v4.stable_sha256(command),
            "configuration_sha256": relay_v7.relay_v4.stable_sha256(
                config.public_mapping()
            ),
            "log_path": str(watcher.log_path),
            "status_path": str(watcher.status_path),
            "started_at_utc": relay_v7.relay_v4._now(),  # noqa: SLF001
            "v7_acceptance_required_before_downstream": True,
            "parent_success_requires_child_lock_readiness": True,
        }
        reserved = {
            **reserved_unsigned,
            "receipt_signature": relay_v7.relay_v4.stable_sha256(reserved_unsigned),
        }
        watcher._write_exclusive_json(watcher.receipt_path, reserved)  # noqa: SLF001

    try:
        with watcher.log_path.open("ab") as stream:
            kwargs: dict[str, Any] = {
                "cwd": config.relay.repo,
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
        _publish_watcher_failure(
            watcher.receipt_path,
            token=token,
            status="detached_start_failed",
            error=exc,
        )
        raise
    try:
        return _wait_for_watcher_ready(
            process,
            receipt_path=watcher.receipt_path,
            token=token,
        )
    except BaseException:
        relay_v7._stop_detached_tree(process)  # noqa: SLF001
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--v7-plan-dir", type=Path, required=True)
    parser.add_argument("--v7-run-dir", type=Path, required=True)
    parser.add_argument("--trace-package-dir", type=Path, required=True)
    parser.add_argument("--bridge-json", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--relay-supervision-dir", type=Path, required=True)
    parser.add_argument("--watcher-supervision-dir", type=Path, required=True)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--launcher-poll-seconds", type=float, default=5.0)
    parser.add_argument("--relay-poll-seconds", type=float, default=30.0)
    parser.add_argument("--relay-max-wait-hours", type=float, default=240.0)
    parser.add_argument("--acceptance-poll-seconds", type=float, default=30.0)
    parser.add_argument("--acceptance-max-wait-hours", type=float, default=240.0)
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--detached-child-token", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.detach:
        if args.detached_child_token:
            print("WATCHER V7 : modes détachés incompatibles", file=sys.stderr)
            return 2
        try:
            print(json.dumps(detach(args), ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(f"WATCHER V7 NON LANCÉ : {exc}", file=sys.stderr)
            return 2

    config = _config_from_args(args)
    try:
        config.validate()
    except Exception as exc:
        print(f"WATCHER V7 CONFIGURATION REFUSÉE : {exc}", file=sys.stderr)
        return 2
    watcher = V7AcceptanceWatcher(config)
    relay_v7.relay_v4._prevent_sleep(True)  # noqa: SLF001
    try:
        token = str(args.detached_child_token or "")
        with _watcher_lock(
            watcher.lock_path,
            wait_seconds=60.0 if token else 0.0,
        ):
            if token:
                watcher.validate_detached_token(token)
                watcher.prepare()
                watcher.publish_detached_ready(token)
                return watcher.execute(prepared=True)
            return watcher.execute()
    except ScientificNoGo as exc:
        print(f"WATCHER V7 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except WatcherTimeout as exc:
        print(f"WATCHER V7 EN ATTENTE : {exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        print("WATCHER V7 INTERROMPU; consulter status.json", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - process boundary diagnostics
        if watcher.contract and watcher.status:
            stage = str(watcher.status.get("stage") or "")
            if stage not in {"scientific_no_go", "invalid_final_v7_result"}:
                downstream_started = stage not in PRE_ACCEPTANCE_STAGES
                watcher.update_status(
                    (
                        "relay_failed_after_acceptance"
                        if downstream_started
                        else "watcher_failed_before_acceptance"
                    ),
                    "Le watcher s'est arrêté en sécurité.",
                    status="failed_closed",
                    error=exc,
                )
                watcher.status["traceback"] = "".join(traceback.format_exception(exc))
                watcher._write_status()  # noqa: SLF001
        print(f"WATCHER V7 EN ÉCHEC : {exc}", file=sys.stderr)
        return 1
    finally:
        relay_v7.relay_v4._prevent_sleep(False)  # noqa: SLF001


if __name__ == "__main__":
    raise SystemExit(main())
