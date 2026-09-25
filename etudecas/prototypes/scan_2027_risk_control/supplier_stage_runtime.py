#!/usr/bin/env python3
"""One resumable delivery workflow, with explicit V7/V8 scientific profiles.

Profiles select existing business validators; they never relax acceptance rules.
Current execution and read-only verification of archived sources are separate.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
from importlib import import_module
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
import traceback
from collections.abc import Mapping, Sequence
from typing import Any
import zipfile

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_v5,
    supplier_priority_action_replay_v4 as actions_v4,
    supplier_priority_lot_replay_v4 as lots_v4,
    supplier_v6_full_incident_lot_registry as registry_v6,
    supplier_v7_stage2_common as base_common,
    supplier_v7_stage2_curves as curves_v7,
)

PACKAGE = "etudecas.prototypes.scan_2027_risk_control"
MODULE_NAME = PACKAGE + ".supplier_stage_runtime"
RUNTIME_REVISION = "etudecas.supplier_stage_runtime.v1"
INVENTORY_SCHEMA = RUNTIME_REVISION + ".source_inventory.v1"
CONTRACT_NAME = "stage2_contract.json"
INVENTORY_NAME = "stage2_source_inventory.json"
STATUS_NAME = "status.json"

PROFILES = {
    "v7-stage2": {
        "common_name": "supplier_v7_stage2_common",
        "suffix": "v7_stage2",
        "progress": [
            (
                "running",
                "validation_etape_1",
                "450 cas de validation et la matrice de campagne (90 "
                "références + 3 240 incidents) revalidés.",
            ),
            ("running", "courbes", "Construction des courbes nominales 28 j / 7 j."),
            (
                "running",
                "lots",
                "Rejeux détaillés baseline + incident, au plus trois dossiers.",
            ),
            (
                "running",
                "qualification",
                "Qualification honnête de la propagation physique.",
            ),
            (
                "running",
                "actions",
                "Test des seuls leviers pilotables en boucle ouverte.",
            ),
            (
                "running",
                "registre",
                "Consolidation des 3 240 incidents et des lots disponibles.",
            ),
            (
                "running",
                "html",
                "Construction du parcours client autonome en trois vues.",
            ),
            ("complete", "termine", "Étape 2 V7 terminée et revalidée."),
        ],
        "scientific": {},
        "poll_seconds": 30.0,
        "require_final_overlay": False,
    },
    "v8-stage2": {
        "common_name": "supplier_v8_stage2_common",
        "suffix": "v8_stage2",
        "progress": [
            (
                "running",
                "validation_etape_1_v8",
                "Validation scientifique V7 (450 cas), registre "
                "d'exposition V8 30/30 et matrice de campagne (90 "
                "références + 3 240 incidents) revalidés.",
            ),
            (
                "running",
                "courbes",
                "Construction des courbes nominales signées MM28 / MM7.",
            ),
            (
                "running",
                "lots",
                "Rejeux détaillés sans incident + incident, au plus trois dossiers.",
            ),
            (
                "running",
                "qualification",
                "Qualification de la propagation physique réellement tracée.",
            ),
            (
                "running",
                "actions",
                "Test des seuls leviers représentables, décidés en boucle ouverte.",
            ),
            (
                "running",
                "registre",
                "Consolidation des 3 240 incidents et des lots réellement disponibles.",
            ),
            (
                "running",
                "html",
                "Construction du parcours autonome en français, trois vues maximum.",
            ),
            ("complete", "termine", "Étape 2 V8 terminée et revalidée."),
        ],
        "scientific": {
            "stage1_required_status": "accepted_v7_450_plus_v8_complete_3330_and_30_of_30_exposure",
            "v8_result_overlay_required": True,
            "target_exposure_gate": "18_lanes_each_comparable_on_30_of_30_seeds",
            "target_window_shared_across_three_states_and_30_seeds": True,
            "target_selection_uses_incident_outcomes": False,
            "target_selection_engine_runs": 0,
        },
        "poll_seconds": 30.0,
        "require_final_overlay": False,
    },
    "v8-stage3": {
        "common_name": "supplier_v8_stage3_common",
        "suffix": "v8_stage3",
        "progress": [
            (
                "running",
                "validation_etape_1_v8_native",
                "Validation V7 (450 cas), registre V8 natif 30/30 et "
                "matrice de campagne (90 références + 3 240 incidents) "
                "revalidés.",
            ),
            ("running", "courbes", "Construction des courbes nominales MM28 / MM7."),
            (
                "running",
                "lots",
                "Rejeux détaillés sans incident + incident, au plus trois dossiers.",
            ),
            (
                "running",
                "qualification",
                "Qualification de la propagation physique réellement tracée.",
            ),
            (
                "running",
                "actions",
                "Test des seuls leviers représentables, décidés en boucle ouverte.",
            ),
            (
                "running",
                "registre",
                "Consolidation des 3 240 incidents et des lots réellement disponibles.",
            ),
            (
                "running",
                "html",
                "Construction du parcours autonome V3, trois vues maximum.",
            ),
            (
                "complete",
                "termine",
                "Étape 2 V3 terminée et revalidée avec le registre V8 natif.",
            ),
        ],
        "scientific": {
            "stage1_required_status": "accepted_v7_450_plus_v8_complete_3330_native_registry_30_of_30",
            "v8_result_overlay_required": True,
            "native_v8_target_registry_reader_required": True,
            "obsolete_design_seed_projection_used": False,
            "target_exposure_gate": "18_lanes_each_comparable_on_30_of_30_seeds",
            "target_window_shared_across_three_states_and_30_seeds": True,
            "target_window_selection": "earliest_positive_comparable_42d_window_from_J180_ratio_le_1_5",
            "target_window_is_worst_period": False,
            "target_window_is_average_season": False,
            "target_selection_uses_incident_outcomes": False,
            "target_selection_engine_runs": 0,
        },
        "poll_seconds": 60.0,
        "require_final_overlay": True,
    },
}


class Stage2PipelineError(base_common.Stage2Error):
    """The resumable stage-2 pipeline cannot preserve its evidence contract."""


class Stage2WatcherError(base_common.Stage2Error):
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
        self.started_at_utc = base_common.utc_now()
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
        self.stopped_at_utc = base_common.utc_now()

    def payload(self) -> dict[str, Any]:
        return {
            "requested": True,
            "active": self.active,
            "method": self.method,
            "started_at_utc": self.started_at_utc,
            "stopped_at_utc": self.stopped_at_utc,
            "coverage": "de_la_prise_du_verrou_jusqu_au_statut_terminal",
        }


class StageRuntime:
    """Profile-bound orchestration; no mutation of another pipeline's globals."""

    CONTRACT_NAME = CONTRACT_NAME
    INVENTORY_NAME = INVENTORY_NAME
    STATUS_NAME = STATUS_NAME
    DEFAULT_MAX_WAIT_HOURS = 240.0
    DEFAULT_STARTUP_TIMEOUT_SECONDS = 600.0
    Stage2PipelineError = Stage2PipelineError
    Stage2WatcherError = Stage2WatcherError
    Stage2WatcherTimeout = Stage2WatcherTimeout
    KeepAwake = KeepAwake

    def __init__(self, profile: str, common: Any):
        if (
            profile not in PROFILES
            or common.__name__.rsplit(".", 1)[-1] != PROFILES[profile]["common_name"]
        ):
            raise ValueError("Runtime profile and business contract module differ")
        self.profile = profile
        self.spec = PROFILES[profile]
        self.common = common
        self.SCHEMA_VERSION = f"etudecas.supplier_{self.spec['suffix']}_pipeline.v1"
        self.WATCHER_SCHEMA_VERSION = (
            f"etudecas.supplier_{self.spec['suffix']}_watcher.v1"
        )
        self.RESERVATION_SCHEMA_VERSION = (
            f"{self.WATCHER_SCHEMA_VERSION}.reservation.v1"
        )
        self.RECEIPT_SCHEMA_VERSION = f"{self.WATCHER_SCHEMA_VERSION}.ready.v1"
        self.UPSTREAM_NAME = common.STAGE1_RECEIPT_NAME
        self.DEFAULT_POLL_SECONDS = self.spec["poll_seconds"]
        self.progress = self.spec["progress"]
        labels = {
            "v7-stage2": (
                "ÉTAPE 2",
                "ÉTAPE 2 ARRÊT SCIENTIFIQUE",
                "attente_etape_1",
                "Reprise possible avec le même contrat.",
            ),
            "v8-stage2": (
                "ÉTAPE 2 V8",
                "ÉTAPE 2 V8 — ARRÊT SCIENTIFIQUE",
                "attente_etape_1_v8",
                "Reprise V8 possible avec le même contrat.",
            ),
            "v8-stage3": (
                "ÉTAPE 2 V3",
                "ÉTAPE 2 V3 — ARRÊT SCIENTIFIQUE",
                "attente_campagne_v8",
                "Reprise V3 possible avec le même contrat.",
            ),
        }
        label, self.no_go_label, self.waiting_step, self.resume_message = labels[
            profile
        ]
        self.waiting_label = label + " EN ATTENTE"
        self.failure_label = label + " EN ÉCHEC"
        self.not_ready_message = {
            "v7-stage2": "L'étape 1 n'est pas encore complète",
            "v8-stage2": "L'étape 1 V8 n'est pas encore complète",
            "v8-stage3": "La campagne V8 n'est pas encore complète.",
        }[profile]

    def source_paths(self, repo: Path) -> list[Path]:
        repo = repo.resolve()
        directory = Path(__file__).resolve().parent
        # Explicit runtime root replaces historical wildcard discovery. The
        # shared AST walker also includes every local imported dependency.
        roots = {
            Path(__file__).resolve(),
            Path(self.common.__file__).resolve(),
            directory / f"supplier_{self.spec['suffix']}_delivery.py",
        }
        if self.profile == "v8-stage3":
            roots.add(directory / "verify_supplier_v8_stage3_closure.py")
        if any(not path.is_relative_to(repo) or not path.is_file() for path in roots):
            raise self.common.Stage2Error(
                "Runtime sources are missing or outside the declared repository"
            )
        paths = base_common._transitive_source_paths(roots, repo)
        if self.profile == "v8-stage3":
            # These explicit operational consumers carry the runtime handoff and
            # GO checks; bind their bytes as well as the Python dependency graph.
            paths.extend(
                directory / name
                for name in (
                    "run_supplier_v8_v2_to_stage3_v3_chain_task.ps1",
                    "run_supplier_v8_v2_to_stage3_v4_chain_task.ps1",
                    "run_supplier_v8_stage3_closure_v1_task.ps1",
                )
            )
        return sorted(set(paths), key=lambda path: path.relative_to(repo).as_posix())

    def build_source_inventory(self, repo: Path) -> dict[str, Any]:
        repo = repo.resolve()
        protocol = Path(base_common.protocol_v7.__file__).resolve()
        if self.common.sha256_file(protocol) != self.common.EXPECTED_PROTOCOL_SHA256:
            raise self.common.Stage2Error("The frozen scientific V7 protocol changed")
        scientific = {"critical_protocol_sha256": self.common.EXPECTED_PROTOCOL_SHA256}
        if self.profile != "v7-stage2":
            from etudecas.prototypes.scan_2027_risk_control import (
                finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
                supplier_operating_point_full_campaign_v8 as campaign_v8,
            )

            finalizer_v8.validate_frozen_implementation()
            scientific.update(
                v8_campaign_runner_sha256=self.common.sha256_file(
                    Path(campaign_v8.__file__).resolve()
                ),
                v8_finalizer_sha256=self.common.sha256_file(
                    Path(finalizer_v8.__file__).resolve()
                ),
            )
        entries = [
            {
                "relative_path": path.relative_to(repo).as_posix(),
                "sha256": self.common.sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in self.source_paths(repo)
        ]
        unsigned = {
            "schema_version": INVENTORY_SCHEMA,
            "runtime_revision": RUNTIME_REVISION,
            "profile": self.profile,
            "runtime_module": MODULE_NAME,
            "repo": str(repo),
            "entries": entries,
            "entry_count": len(entries),
            **scientific,
        }
        return self.common.signed(unsigned, "inventory_signature")

    def verify_source_inventory(self, inventory: Mapping[str, Any]) -> None:
        self.common.verify_signature(
            inventory, "inventory_signature", "runtime source inventory"
        )
        if (
            inventory.get("schema_version") != INVENTORY_SCHEMA
            or inventory.get("profile") != self.profile
        ):
            raise self.common.Stage2Error(
                "Historical or other-profile inventory cannot authorize this runtime; use read-only archive verification"
            )
        if dict(inventory) != self.build_source_inventory(
            Path(str(inventory.get("repo") or ""))
        ):
            raise self.common.Stage2Error(
                "Runtime source inventory changed; resume refused"
            )

    def create_pipeline(self, paths):
        return Stage2Pipeline(paths, self)

    def consumer_bindings(self):
        return (
            self.common.v7_consumer_bindings()
            if self.profile == "v7-stage2"
            else self.common.v8_consumer_bindings()
        )

    def delivery_module(self):
        return import_module(f"{PACKAGE}.supplier_{self.spec['suffix']}_delivery")

    def _delivery(self, paths):
        return self.delivery_module().build_delivery(paths)

    def _status_payload(
        self,
        contract_signature: str,
        *,
        status: str,
        step: str,
        message_fr: str,
        previous: Mapping[str, Any] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        history = list((previous or {}).get("history") or [])
        history.append(
            {
                "at_utc": self.common.utc_now(),
                "status": status,
                "step": step,
                "message_fr": message_fr,
            }
        )
        unsigned = {
            "schema_version": f"{self.SCHEMA_VERSION}.status.v1",
            "contract_signature": contract_signature,
            "status": status,
            "step": step,
            "message_fr": message_fr,
            "pid": os.getpid(),
            "updated_at_utc": self.common.utc_now(),
            "history": history,
            **dict(extra or {}),
        }
        return self.common.signed(unsigned, "status_signature")

    def _verify_status(self, path: Path, contract_signature: str) -> dict[str, Any]:
        payload = self.common.read_json(path)
        self.common.verify_signature(payload, "status_signature", "statut étape 2")
        if (
            payload.get("schema_version") != f"{self.SCHEMA_VERSION}.status.v1"
            or payload.get("contract_signature") != contract_signature
        ):
            raise Stage2PipelineError("Le statut appartient à un autre contrat étape 2")
        return payload

    def _contract_payload(
        self, paths: base_common.Stage2Paths, inventory: Mapping[str, Any]
    ) -> dict[str, Any]:
        observed = self.common.validate_observed_2025_pack(paths.observed_2025_dir)
        unsigned = {
            "schema_version": f"{self.SCHEMA_VERSION}.contract.v1",
            "paths": paths.mapping(),
            "source_inventory_signature": inventory["inventory_signature"],
            "scientific_contract": {
                "stage1_required_status": "accepted_450_then_complete_3330",
                "detailed_dossier_maximum": 3,
                "detailed_replay_arms": ["baseline", "incident_without_action"],
                "incident_mechanisms": list(self.common.EXPECTED_MECHANISMS),
                "quality_incident_included": False,
                "capacity_or_availability_invented": False,
                "state_dependent_consequences": True,
                "incident_generation": "exogenous_conditional_hypothesis",
                "action_ids": list(self.common.ALLOWED_ACTIONS),
                "action_mode": "open_loop_not_automatic_regulation",
                "action_lot_trace_claimed": False,
                "clients": "aggregated_only",
                "historical_incident_probability_estimated": False,
                "roi_without_complete_cost_proof": False,
                "signed_selection_preserved_without_override": True,
            },
            "curve_contract": {
                "campaign_pairing_seed_count": 30,
                "service_and_flow_window_days": 28,
                "stock_wip_backlog_window_days": 7,
                "lot_plan_gap_window_days": 28,
                "input_shortage_signal_window_days": 7,
                "scientific_acceptance_population": False,
            },
            "observed_2025": (
                {
                    "provided": True,
                    "manifest": observed["manifest"],
                    "manifest_sha256": observed["manifest_sha256"],
                    "supplier_causality_available": False,
                }
                if observed is not None
                else {"provided": False}
            ),
        }
        unsigned["scientific_contract"].update(self.spec["scientific"])
        unsigned["orchestration"] = {
            "revision": RUNTIME_REVISION,
            "profile": self.profile,
            "module": MODULE_NAME,
        }
        return self.common.signed(unsigned, "contract_signature")

    def validate_bound_contract(
        self,
        paths: base_common.Stage2Paths,
        *,
        expected_contract: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Revalidate code, observed context, paths, and their immutable contract."""

        paths = paths.resolved()
        paths.validate_separation()
        inventory = self.common.read_json(paths.supervision_dir / INVENTORY_NAME)
        self.verify_source_inventory(inventory)
        contract = self.common.read_json(paths.supervision_dir / CONTRACT_NAME)
        self.common.verify_signature(contract, "contract_signature", "contrat étape 2")
        if expected_contract is not None and contract != dict(expected_contract):
            raise Stage2PipelineError("Le contrat étape 2 a été remplacé")
        if contract != self._contract_payload(paths, inventory):
            raise Stage2PipelineError(
                "Une source liée au contrat étape 2 a changé depuis l'armement"
            )
        return contract

    def prepare_supervision(self, paths: base_common.Stage2Paths) -> dict[str, Any]:
        """Create/validate only the supervision directory; never touch stage outputs."""

        paths = paths.resolved()
        paths.validate_separation()
        root = paths.supervision_dir
        contract_path = root / CONTRACT_NAME
        status_path = root / STATUS_NAME
        if contract_path.is_file():
            contract = self.validate_bound_contract(paths)
            self._verify_status(status_path, contract["contract_signature"])
            return contract
        if root.exists() and any(root.iterdir()):
            raise Stage2PipelineError("Supervision étape 2 préexistante non reconnue")
        for output in (*paths.output_roots[:-1], *paths.output_files):
            if output.exists():
                raise Stage2PipelineError(
                    f"Une sortie étape 2 existe avant son contrat : {output}"
                )
        inventory = self.build_source_inventory(paths.repo)
        contract = self._contract_payload(paths, inventory)
        stage = root.with_name(
            f".{root.name}.stage2-{os.getpid()}-{os.urandom(8).hex()}"
        )
        try:
            stage.mkdir(parents=True, exist_ok=False)
            (stage / INVENTORY_NAME).write_text(
                json.dumps(inventory, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
            (stage / CONTRACT_NAME).write_text(
                json.dumps(contract, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
            initial = self._status_payload(
                contract["contract_signature"],
                status="armed_waiting_for_stage1",
                step="attente_etape_1",
                message_fr="Watcher étape 2 armé; aucune sortie aval créée.",
            )
            (stage / STATUS_NAME).write_text(
                json.dumps(initial, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n",
                encoding="utf-8",
            )
            os.replace(stage, root)
        except BaseException:
            if stage.exists():
                shutil.rmtree(stage)
            raise
        return contract

    def _selection(self, results_dir: Path) -> list[dict[str, Any]]:
        path = results_dir.resolve() / "lot_replay_plan.json"
        payload = self.common.read_json(path)
        lots_v4._verify_signed_payload(  # noqa: SLF001
            payload, "selection_signature", "sélection signée des dossiers lots"
        )
        rows = payload.get("selected_dossiers")
        if (
            payload.get("status") != "complete_selected"
            or not isinstance(rows, list)
            or len(rows) > self.common.MAX_DETAILED_DOSSIERS
            or int(payload.get("selection_contract", {}).get("maximum_dossiers") or -1)
            != self.common.MAX_DETAILED_DOSSIERS
            or payload.get("selection_contract", {}).get("forced_top3") is not False
        ):
            raise Stage2PipelineError("La sélection signée des dossiers est invalide")
        identities = [
            (
                str(row.get("operating_point_id") or ""),
                str(row.get("mechanism") or ""),
                str(row.get("lane_id") or ""),
            )
            for row in rows
            if isinstance(row, Mapping)
        ]
        if (
            len(identities) != len(rows)
            or any(not all(key) for key in identities)
            or len(set(identities)) != len(rows)
        ):
            raise Stage2PipelineError("Identités de dossiers signés invalides")
        return [dict(row) for row in rows]

    def _archive_owned_partial(self, root: Path, candidate: Path, label: str) -> Path:
        root = root.resolve()
        candidate = candidate.resolve()
        if (
            candidate == root
            or not candidate.is_relative_to(root)
            or not candidate.exists()
        ):
            raise Stage2PipelineError("Sortie partielle hors racine étape 2")
        recovery = root / "recovery" / "partial_lot_arms"
        recovery.mkdir(parents=True, exist_ok=True)
        destination = (
            recovery
            / f"{label}.{self.common.utc_now().replace(':', '').replace('+', '_')}"
        )
        suffix = 1
        while destination.exists():
            destination = recovery / f"{destination.name}.{suffix}"
            suffix += 1
        candidate.replace(destination)
        return destination

    def _archive_owned_unplanned_root(
        self, paths: base_common.Stage2Paths, candidate: Path, label: str
    ) -> Path:
        """Move a crash-left plan root aside before asking V4 to create it again."""

        candidate = candidate.resolve()
        allowed = {
            paths.lot_replay_root.resolve(),
            paths.action_replay_root.resolve(),
        }
        if (
            candidate not in allowed
            or not candidate.is_dir()
            or not any(candidate.iterdir())
        ):
            raise Stage2PipelineError(
                "Racine partielle non vide hors sorties possédées"
            )
        recovery = paths.supervision_dir.resolve() / "recovery" / "partial_plans"
        if self.common.paths_overlap(recovery, candidate) or any(
            self.common.paths_overlap(recovery, source)
            for source in paths.upstream_paths
        ):
            raise Stage2PipelineError("Archive de reprise hors périmètre étape 2")
        recovery.mkdir(parents=True, exist_ok=True)
        timestamp = self.common.utc_now().replace(":", "").replace("+", "_")
        destination = recovery / f"{label}.{timestamp}"
        suffix = 1
        while destination.exists():
            destination = recovery / f"{label}.{timestamp}.{suffix}"
            suffix += 1
        candidate.replace(destination)
        return destination

    def _lot_receipt_valid(
        self, root: Path, plan: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        path = root / "replay_run_receipt.json"
        if not path.is_file():
            return None
        receipt = self.common.read_json(path)
        lots_v4._verify_signed_payload(  # noqa: SLF001
            receipt, "run_receipt_signature", "reçu des rejeux lots"
        )
        proofs = []
        for dossier in plan.get("dossiers") or []:
            for arm in ("baseline", "incident"):
                proof = lots_v4.validate_arm(
                    Path(str(dossier["arms"][arm]["run_dir"])), dossier=dossier, arm=arm
                )
                proofs.append({"dossier_id": dossier["dossier_id"], **proof})
            lots_v4._validate_pair(dossier)  # noqa: SLF001
        if (
            receipt.get("status") != "complete_validated"
            or receipt.get("plan_signature") != plan.get("plan_signature")
            or receipt.get("arms") != proofs
        ):
            raise Stage2PipelineError(
                "Le reçu des rejeux lots ne correspond plus aux bras"
            )
        return receipt

    def _run_lot_replays(
        self, paths: base_common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        if not selection:
            return {
                "status": "not_run_no_signed_dossier",
                "dossier_count": 0,
                "engine_run_count": 0,
                "forced_top3": False,
            }
        plan_path = paths.lot_replay_root / "replay_plan.json"
        if plan_path.is_file():
            plan = lots_v4.load_and_validate_plan(paths.lot_replay_root)
        else:
            if paths.lot_replay_root.exists():
                if not paths.lot_replay_root.is_dir():
                    raise Stage2PipelineError("La racine des lots n'est pas un dossier")
                if any(paths.lot_replay_root.iterdir()):
                    self._archive_owned_unplanned_root(
                        paths, paths.lot_replay_root, "lot_replay_plan"
                    )
            plan = lots_v4.create_replay_plan(
                campaign_root=paths.campaign_root,
                results_dir=paths.results_dir,
                output_root=paths.lot_replay_root,
                max_dossiers=self.common.MAX_DETAILED_DOSSIERS,
                selection_csv=None,
            )
        dossiers = plan.get("dossiers") or []
        if (
            len(dossiers) != len(selection)
            or len(dossiers) > self.common.MAX_DETAILED_DOSSIERS
        ):
            raise Stage2PipelineError(
                "Le plan de rejeu ne conserve pas la sélection signée"
            )
        receipt = self._lot_receipt_valid(paths.lot_replay_root, plan)
        if receipt is None:
            results = []
            for dossier in dossiers:
                dossier_id = str(dossier["dossier_id"])
                for arm in ("baseline", "incident"):
                    run_dir = Path(str(dossier["arms"][arm]["run_dir"])).resolve()
                    proof = None
                    if run_dir.exists():
                        try:
                            proof = lots_v4.validate_arm(
                                run_dir, dossier=dossier, arm=arm
                            )
                        except lots_v4.ReplayContractError:
                            self._archive_owned_partial(
                                paths.lot_replay_root, run_dir, f"{dossier_id}__{arm}"
                            )
                    if proof is None:
                        log = (
                            paths.lot_replay_root / "logs" / f"{dossier_id}__{arm}.log"
                        )
                        log.parent.mkdir(parents=True, exist_ok=True)
                        with log.open("a", encoding="utf-8") as stream:
                            completed = subprocess.run(
                                list(dossier["arms"][arm]["command"]),
                                cwd=paths.repo,
                                stdout=stream,
                                stderr=subprocess.STDOUT,
                                text=True,
                                check=False,
                            )
                        if completed.returncode != 0:
                            raise Stage2PipelineError(
                                f"Échec du rejeu lots {dossier_id}/{arm}: {completed.returncode}"
                            )
                        proof = lots_v4.validate_arm(run_dir, dossier=dossier, arm=arm)
                    results.append({"dossier_id": dossier_id, **proof})
                lots_v4._validate_pair(dossier)  # noqa: SLF001
            unsigned = {
                "schema_version": lots_v4.RUN_RECEIPT_SCHEMA_VERSION,
                "status": "complete_validated",
                "created_at_utc": self.common.utc_now(),
                "plan_signature": plan["plan_signature"],
                "arms": results,
            }
            receipt = {
                **unsigned,
                "run_receipt_signature": lots_v4.stable_sha256(unsigned),
            }
            self.common.publish_new_or_identical(
                paths.lot_replay_root / "replay_run_receipt.json",
                (
                    json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n"
                ).encode("utf-8"),
            )
            receipt = self._lot_receipt_valid(paths.lot_replay_root, plan)
        assert receipt is not None
        validation_path = paths.lot_replay_root / "finalized" / "replay_validation.json"
        if validation_path.is_file():
            validation = self._validate_finalized_lots(paths.lot_replay_root, plan)
        else:
            final_root = paths.lot_replay_root / "finalized"
            standalone = (
                paths.lot_replay_root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html"
            )
            if final_root.exists() or standalone.exists():
                if final_root.exists():
                    self._archive_owned_partial(
                        paths.lot_replay_root, final_root, "finalized"
                    )
                if standalone.exists():
                    self._archive_owned_partial(
                        paths.lot_replay_root, standalone, "standalone"
                    )
            validation = lots_v4.finalize_replay(paths.lot_replay_root)
        if validation.get("status") != "complete_validated" or len(
            validation.get("dossiers") or []
        ) != len(selection):
            raise Stage2PipelineError("Le rejeu détaillé des lots n'est pas validé")
        return {
            "status": "complete_validated",
            "dossier_count": len(selection),
            "engine_run_count": 2 * len(selection),
            "forced_top3": False,
            "plan_signature": plan["plan_signature"],
            "validation_signature": validation["validation_signature"],
        }

    def _validate_finalized_lots(
        self, replay_root: Path, plan: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Revalidate an immutable V4 finalization without asking V4 to overwrite it."""

        final_root = replay_root / "finalized"
        validation_path = final_root / "replay_validation.json"
        validation = self.common.read_json(validation_path)
        lots_v4._verify_signed_payload(  # noqa: SLF001
            validation, "validation_signature", "validation finale des lots"
        )
        receipt = self.common.read_json(replay_root / "replay_run_receipt.json")
        lots_v4._verify_signed_payload(  # noqa: SLF001
            receipt, "run_receipt_signature", "reçu des rejeux lots"
        )
        inventory_path = Path(str(validation.get("artifact_inventory") or "")).resolve()
        html_path = Path(str(validation.get("standalone_html") or "")).resolve()
        if (
            validation.get("status") != "complete_validated"
            or validation.get("plan_signature") != plan.get("plan_signature")
            or validation.get("run_receipt_signature")
            != receipt.get("run_receipt_signature")
            or not inventory_path.is_relative_to(final_root.resolve())
            or not inventory_path.is_file()
            or self.common.sha256_file(inventory_path)
            != str(validation.get("artifact_inventory_sha256") or "")
            or not html_path.is_relative_to(replay_root.resolve())
            or not html_path.is_file()
            or self.common.sha256_file(html_path)
            != str(validation.get("standalone_html_sha256") or "")
        ):
            raise Stage2PipelineError("La finalisation existante des lots est invalide")
        inventory = self.common._read_csv(inventory_path)  # noqa: SLF001
        for row in inventory:
            artifact = (replay_root / str(row.get("relative_path") or "")).resolve()
            if (
                not artifact.is_relative_to(replay_root.resolve())
                or not artifact.is_file()
                or artifact.stat().st_size != int(row.get("size_bytes") or -1)
                or self.common.sha256_file(artifact) != str(row.get("sha256") or "")
            ):
                raise Stage2PipelineError("Un artefact finalisé des lots a changé")
        declared_ids = {
            str(row.get("dossier_id") or "") for row in validation.get("dossiers") or []
        }
        expected_ids = {
            str(row.get("dossier_id") or "") for row in plan.get("dossiers") or []
        }
        if declared_ids != expected_ids or len(declared_ids) != len(
            plan.get("dossiers") or []
        ):
            raise Stage2PipelineError(
                "La finalisation ne couvre pas les dossiers signés"
            )
        for dossier in plan.get("dossiers") or []:
            for arm in ("baseline", "incident"):
                lots_v4.validate_arm(
                    Path(str(dossier["arms"][arm]["run_dir"])), dossier=dossier, arm=arm
                )
            lots_v4._validate_pair(dossier)  # noqa: SLF001
        return validation

    def _qualify(
        self, paths: base_common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        replay_root = paths.lot_replay_root if selection else None
        if paths.qualification_dir.exists():
            payload = physical_v5.validate_qualification_sidecar(
                campaign_root=paths.campaign_root,
                results_dir=paths.results_dir,
                replay_root=replay_root,
                output_dir=paths.qualification_dir,
            )
        else:
            payload = physical_v5.build_qualification_sidecar(
                campaign_root=paths.campaign_root,
                results_dir=paths.results_dir,
                replay_root=replay_root,
                output_dir=paths.qualification_dir,
            )
        if (
            payload.get("status") != "complete_qualified"
            or int(payload.get("counts", {}).get("selected_dossier_count") or 0)
            != len(selection)
            or payload.get("selection_guard", {}).get(
                "selection_proves_full_dynamic_cascade"
            )
            is not False
        ):
            raise Stage2PipelineError(
                "La portée physique des cascades n'est pas qualifiée"
            )
        return {
            "status": payload["status"],
            "qualification_signature": payload["qualification_signature"],
            "selected_dossier_count": len(selection),
            "full_dynamic_cascade_claimed": False,
        }

    def _run_actions(
        self, paths: base_common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        if not selection:
            return {
                "status": "not_run_no_signed_dossier",
                "eligible_action_ids": [],
                "open_loop": True,
                "engine_arm_count": 0,
            }
        action_plan_path = paths.action_replay_root / "action_replay_plan.json"
        if not action_plan_path.is_file() and paths.action_replay_root.exists():
            if not paths.action_replay_root.is_dir():
                raise Stage2PipelineError("La racine des actions n'est pas un dossier")
            if any(paths.action_replay_root.iterdir()):
                self._archive_owned_unplanned_root(
                    paths, paths.action_replay_root, "action_replay_plan"
                )
        plan = actions_v4.create_action_plan(
            campaign_root=paths.campaign_root,
            results_dir=paths.results_dir,
            output_root=paths.action_replay_root,
            lot_replay_root=paths.lot_replay_root,
            max_dossiers=self.common.MAX_DETAILED_DOSSIERS,
            reference_mode="signed_reference",
        )
        eligible = sorted(
            {
                str(action_id)
                for dossier in plan.get("dossiers") or []
                for action_id in dossier.get("eligible_action_ids") or []
            }
        )
        if (
            not set(eligible).issubset(self.common.ALLOWED_ACTIONS)
            or plan.get("scientific_contract", {}).get("closed_loop_claimed")
            is not False
            or plan.get("scientific_contract", {}).get("reference_engine_reruns") != 0
            or plan.get("scientific_contract", {}).get(
                "availability_or_capacity_invented"
            )
            is not False
        ):
            raise Stage2PipelineError("Le plan contient un levier non autorisé")
        receipt = actions_v4.run_action_replay(
            paths.action_replay_root, execute=True, workers=2
        )
        if receipt.get("status") not in {
            "complete_validated",
            "complete_no_representable_action",
        }:
            raise Stage2PipelineError(
                "Les bras d'actions en boucle ouverte sont incomplets"
            )
        summary, validation = actions_v4.finalize_action_replay(
            paths.action_replay_root
        )
        checked_summary, checked_validation = actions_v4.validate_action_results(
            paths.action_replay_root
        )
        if summary != checked_summary or validation != checked_validation:
            raise Stage2PipelineError("La consolidation des actions ne se revalide pas")
        return {
            "status": validation["status"],
            "eligible_action_ids": eligible,
            "open_loop": True,
            "engine_arm_count": int(receipt.get("planned_action_arm_count") or 0),
            "reference_engine_rerun_count": 0,
            "summary_signature": summary["summary_signature"],
            "validation_signature": validation["validation_signature"],
        }

    def _registry(
        self, paths: base_common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        replay_root = paths.lot_replay_root if selection else None
        if paths.registry_dir.exists():
            result = registry_v6.validate_delivery(paths.registry_dir)
        else:
            result = registry_v6.build_from_official_sources(
                campaign_root=paths.campaign_root,
                results_dir=paths.results_dir,
                replay_root=replay_root,
                output_dir=paths.registry_dir,
            )
        if (
            result.get("valid") is not True
            or int(result.get("incidentExposureRowCount") or -1)
            != self.common.EXPECTED_INCIDENTS
            or int(result.get("availableDetailedReplayCount") or 0) != len(selection)
        ):
            raise Stage2PipelineError(
                "Le registre 3 240 incidents + lots est incomplet"
            )
        return dict(result)

    def add_path_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--repo", type=Path, required=True)
        parser.add_argument("--v7-plan-dir", type=Path, required=True)
        parser.add_argument("--v7-run-dir", type=Path, required=True)
        parser.add_argument("--trace-package-dir", type=Path, required=True)
        parser.add_argument("--bridge-json", type=Path, required=True)
        parser.add_argument("--campaign-root", type=Path, required=True)
        parser.add_argument("--results-dir", type=Path, required=True)
        parser.add_argument("--stage1-supervision-dir", type=Path, required=True)
        parser.add_argument("--observed-2025-dir", type=Path)
        parser.add_argument("--lot-replay-root", type=Path, required=True)
        parser.add_argument("--qualification-dir", type=Path, required=True)
        parser.add_argument("--action-replay-root", type=Path, required=True)
        parser.add_argument("--curves-dir", type=Path, required=True)
        parser.add_argument("--registry-dir", type=Path, required=True)
        parser.add_argument("--final-html", type=Path, required=True)
        parser.add_argument("--supervision-dir", type=Path, required=True)

    def paths_from_args(self, args: argparse.Namespace) -> base_common.Stage2Paths:
        return base_common.Stage2Paths(
            repo=args.repo,
            v7_plan_dir=args.v7_plan_dir,
            v7_run_dir=args.v7_run_dir,
            trace_package_dir=args.trace_package_dir,
            bridge_json=args.bridge_json,
            campaign_root=args.campaign_root,
            results_dir=args.results_dir,
            stage1_supervision_dir=args.stage1_supervision_dir,
            observed_2025_dir=args.observed_2025_dir,
            lot_replay_root=args.lot_replay_root,
            qualification_dir=args.qualification_dir,
            action_replay_root=args.action_replay_root,
            curves_dir=args.curves_dir,
            registry_dir=args.registry_dir,
            final_html=args.final_html,
            supervision_dir=args.supervision_dir,
        ).resolved()

    def _run_parser(
        self,
    ) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=__doc__)
        self.add_path_arguments(parser)
        return parser

    def run(self, argv: Sequence[str] | None = None) -> int:
        args = self._run_parser().parse_args(argv)
        paths = self.paths_from_args(args)
        relay = None
        try:
            # The immutable contract must exist before the lock file is created inside
            # the supervision directory; otherwise a first invocation would mistake
            # its own lock for an unknown pre-existing artifact.
            self.prepare_supervision(paths)
            with self.common.exclusive_lock(paths.supervision_dir / ".stage2.lock"):
                relay = self.create_pipeline(paths)
                return relay.execute()
        except self.common.Stage2ScientificNoGo as exc:
            if relay is not None:
                relay.update("scientific_no_go", "arret", str(exc))
            print(f"{self.no_go_label} : {exc}", file=sys.stderr)
            return 3
        except self.common.Stage2NotReady as exc:
            if relay is not None:
                relay.update("waiting", self.waiting_step, str(exc))
            print(f"{self.waiting_label} : {exc}", file=sys.stderr)
            return 4
        except KeyboardInterrupt:
            if relay is not None:
                relay.update(
                    "interrupted_resumable",
                    "interrompu",
                    self.resume_message,
                )
            return 130
        except Exception as exc:
            if relay is not None:
                relay.update(
                    "failed_resumable",
                    "echec",
                    str(exc),
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            print(f"{self.failure_label} : {exc}", file=sys.stderr)
            return 1

    def _pid_alive(self, pid: int) -> bool:
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

    def _attempt_dirs(self, root: Path) -> tuple[Path, Path]:
        return root / "detached_reservations", root / "detached_receipts"

    def _read_signed(
        self, path: Path, signature_field: str, label: str
    ) -> dict[str, Any]:
        payload = self.common.read_json(path)
        self.common.verify_signature(payload, signature_field, label)
        return payload

    def _receipt_paths(self, root: Path) -> list[Path]:
        _reservations, receipts = self._attempt_dirs(root)
        return (
            sorted(receipts.glob("attempt_*_ready.json")) if receipts.is_dir() else []
        )

    def _latest_receipt(
        self, root: Path, contract_signature: str
    ) -> dict[str, Any] | None:
        paths = self._receipt_paths(root)
        if not paths:
            return None
        receipt = self._read_signed(
            paths[-1], "receipt_signature", "reçu détaché étape 2"
        )
        if (
            receipt.get("schema_version") != self.RECEIPT_SCHEMA_VERSION
            or receipt.get("contract_signature") != contract_signature
            or receipt.get("lock_acquired_before_ready") is not True
        ):
            raise Stage2WatcherError(
                "Le dernier reçu détaché appartient à un autre contrat"
            )
        return receipt

    def _reserve_attempt(
        self, root: Path, contract_signature: str
    ) -> tuple[int, str, Path]:
        reservations, receipts = self._attempt_dirs(root)
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
            "schema_version": self.RESERVATION_SCHEMA_VERSION,
            "contract_signature": contract_signature,
            "attempt": attempt,
            "token": token,
            "parent_pid": os.getpid(),
            "reserved_at_utc": self.common.utc_now(),
        }
        payload = self.common.signed(unsigned, "reservation_signature")
        try:
            with path.open("xb") as stream:
                stream.write(
                    (
                        json.dumps(
                            payload, ensure_ascii=False, indent=2, allow_nan=False
                        )
                        + "\n"
                    ).encode("utf-8")
                )
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:  # pragma: no cover - guarded by detach lock
            raise Stage2WatcherError("Réservation détachée concurrente") from exc
        return attempt, token, path

    def _receipt_path(self, root: Path, attempt: int) -> Path:
        return self._attempt_dirs(root)[1] / f"attempt_{attempt:04d}_ready.json"

    def _validate_reservation(
        self, path: Path, *, attempt: int, token: str, contract_signature: str
    ) -> dict[str, Any]:
        payload = self._read_signed(
            path, "reservation_signature", "réservation détachée"
        )
        if (
            payload.get("schema_version") != self.RESERVATION_SCHEMA_VERSION
            or payload.get("attempt") != attempt
            or payload.get("token") != token
            or payload.get("contract_signature") != contract_signature
        ):
            raise Stage2WatcherError("Réservation détachée invalide")
        return payload

    def _publish_ready(
        self,
        paths: base_common.Stage2Paths,
        *,
        attempt: int,
        token: str,
        contract_signature: str,
        keep_awake: Mapping[str, Any],
    ) -> dict[str, Any]:
        unsigned = {
            "schema_version": self.RECEIPT_SCHEMA_VERSION,
            "contract_signature": contract_signature,
            "attempt": attempt,
            "token": token,
            "child_pid": os.getpid(),
            "ready_at_utc": self.common.utc_now(),
            "lock_acquired_before_ready": True,
            "source_inventory_verified_before_ready": True,
            "keep_awake": dict(keep_awake),
            "official_engine_started_before_ready": False,
        }
        receipt = self.common.signed(unsigned, "receipt_signature")
        self.common.publish_new_or_identical(
            self._receipt_path(paths.supervision_dir, attempt),
            (
                json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8"),
        )
        return receipt

    def _stop_unready_child(self, child: subprocess.Popen[Any]) -> None:
        """Stop only the child spawned by this parent before readiness."""

        if child.poll() is not None:
            return
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=10)

    def _path_cli(self, paths: base_common.Stage2Paths) -> list[str]:
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
        self,
        paths: base_common.Stage2Paths,
        *,
        attempt: int,
        token: str,
        poll_seconds: float,
        max_wait_hours: float,
    ) -> int:
        contract = self.prepare_supervision(paths)
        if attempt > 0:
            reservation_path = (
                self._attempt_dirs(paths.supervision_dir)[0]
                / f"attempt_{attempt:04d}.json"
            )
            self._validate_reservation(
                reservation_path,
                attempt=attempt,
                token=token,
                contract_signature=str(contract["contract_signature"]),
            )
        relay: Stage2Pipeline | None = None
        keeper = self.KeepAwake()
        try:
            with self.common.exclusive_lock(paths.supervision_dir / ".stage2.lock"):
                relay = self.create_pipeline(paths)
                relay.guard()
                keeper.start()
                if attempt > 0:
                    self._publish_ready(
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
                    state = self.common.probe_stage1(paths)
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
        except self.common.Stage2ScientificNoGo as exc:
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
        self,
        paths: base_common.Stage2Paths,
        *,
        poll_seconds: float,
        max_wait_hours: float,
        startup_timeout_seconds: float,
    ) -> dict[str, Any]:
        contract = self.prepare_supervision(paths)
        detach_lock = paths.supervision_dir / ".detach.lock"
        with self.common.exclusive_lock(detach_lock):
            latest = self._latest_receipt(
                paths.supervision_dir, str(contract["contract_signature"])
            )
            if latest is not None and self._pid_alive(
                int(latest.get("child_pid") or -1)
            ):
                raise Stage2WatcherError(
                    f"Un watcher étape 2 est déjà actif (PID {latest['child_pid']})"
                )
            status = self._verify_status(  # noqa: SLF001
                paths.supervision_dir / self.STATUS_NAME,
                str(contract["contract_signature"]),
            )
            if status.get("status") == "scientific_no_go":
                raise Stage2WatcherError(
                    "L'étape 1 a déjà rejeté la campagne; relance interdite"
                )
            if status.get("status") == "complete":
                proof = self.delivery_module().validate_delivery(paths)
                return {
                    "status": "already_complete",
                    "supervision": str(paths.supervision_dir),
                    "final_html": str(paths.final_html),
                    "delivery": proof,
                }
            attempt, token, _reservation = self._reserve_attempt(
                paths.supervision_dir, str(contract["contract_signature"])
            )
            command = [
                sys.executable,
                "-m",
                MODULE_NAME,
                "--profile",
                self.profile,
                "--mode",
                "watch",
                *self._path_cli(paths),
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
            ready_path = self._receipt_path(paths.supervision_dir, attempt)
            deadline = time.monotonic() + startup_timeout_seconds
            try:
                while time.monotonic() < deadline:
                    if ready_path.is_file():
                        receipt = self._read_signed(
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
                            or receipt.get("keep_awake", {}).get("requested")
                            is not True
                            or receipt.get("keep_awake", {}).get("active") is not True
                            or receipt.get("official_engine_started_before_ready")
                            is not False
                            or child.poll() is not None
                            or not self._pid_alive(child.pid)
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
                raise Stage2WatcherError(
                    "Délai dépassé avant le reçu de démarrage détaché"
                )
            except BaseException:
                self._stop_unready_child(child)
                raise

    def _watch_parser(
        self,
    ) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=__doc__)
        self.add_path_arguments(parser)
        parser.add_argument(
            "--poll-seconds", type=float, default=self.DEFAULT_POLL_SECONDS
        )
        parser.add_argument(
            "--max-wait-hours", type=float, default=self.DEFAULT_MAX_WAIT_HOURS
        )
        parser.add_argument(
            "--startup-timeout-seconds",
            type=float,
            default=self.DEFAULT_STARTUP_TIMEOUT_SECONDS,
        )
        parser.add_argument("--detach", action="store_true")
        parser.add_argument("--child-token", default="", help=argparse.SUPPRESS)
        parser.add_argument("--attempt", type=int, default=0, help=argparse.SUPPRESS)
        return parser

    def watch(self, argv: Sequence[str] | None = None) -> int:
        args = self._watch_parser().parse_args(argv)
        paths = self.paths_from_args(args)
        if self.spec["require_final_overlay"]:
            from etudecas.prototypes.scan_2027_risk_control import (
                finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
            )

            if not (paths.results_dir / finalizer_v8.V8_RESULT_OVERLAY_NAME).is_file():
                print(
                    "ÉTAPE 2 V3 EN ATTENTE : la surcouche finale V8 est absente; aucun fichier de progression de campagne n'a été ouvert.",
                    file=sys.stderr,
                )
                return 4
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
                result = self._detach(
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
                return self._child_main(
                    paths,
                    attempt=args.attempt,
                    token=args.child_token,
                    poll_seconds=args.poll_seconds,
                    max_wait_hours=args.max_wait_hours,
                )
            self.prepare_supervision(paths)
            return self._child_main(
                paths,
                attempt=0,
                token="foreground",
                poll_seconds=args.poll_seconds,
                max_wait_hours=args.max_wait_hours,
            )
        except Exception as exc:
            print(f"WATCHER ÉTAPE 2 REFUSÉ : {exc}", file=sys.stderr)
            return 1


class Stage2Pipeline:
    def __init__(self, paths: base_common.Stage2Paths, runtime: StageRuntime):
        self.runtime = runtime
        self.paths = paths.resolved()
        self.contract = self.runtime.prepare_supervision(self.paths)
        self.inventory = self.runtime.common.read_json(
            self.paths.supervision_dir / INVENTORY_NAME
        )
        self.status_path = self.paths.supervision_dir / STATUS_NAME
        self.status = self.runtime._verify_status(
            self.status_path, str(self.contract["contract_signature"])
        )

    def update(self, status: str, step: str, message_fr: str, **extra: Any) -> None:
        self.status = self.runtime._status_payload(
            str(self.contract["contract_signature"]),
            status=status,
            step=step,
            message_fr=message_fr,
            previous=self.status,
            extra=extra,
        )
        self.runtime.common.atomic_write_json(self.status_path, self.status)

    def guard(self) -> None:
        self.runtime.validate_bound_contract(
            self.paths, expected_contract=self.contract
        )
        upstream_receipt = self.paths.supervision_dir / self.runtime.UPSTREAM_NAME
        if upstream_receipt.is_file():
            self.runtime.common.validate_bound_stage1_receipt(
                self.paths, upstream_receipt
            )

    def execute(self) -> int:
        self.guard()
        if self.runtime.common.probe_stage1(self.paths) != "accepted_stage1_complete":
            raise self.runtime.common.Stage2NotReady(self.runtime.not_ready_message)
        upstream = self.runtime.common.validate_complete_stage1(self.paths)
        self.runtime.common.publish_new_or_identical(
            self.paths.supervision_dir / self.runtime.UPSTREAM_NAME,
            (
                json.dumps(upstream, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8"),
        )
        self.guard()
        self.update(
            *self.runtime.progress[0],
            upstream_validation_signature=upstream["validation_signature"],
        )
        selection = self.runtime._selection(self.paths.results_dir)

        self.guard()
        self.update(*self.runtime.progress[1])
        curve_result = curves_v7.build_curve_package(
            self.paths.v7_plan_dir, self.paths.v7_run_dir, self.paths.curves_dir
        )

        self.guard()
        self.update(
            *self.runtime.progress[2],
        )
        with self.runtime.consumer_bindings():
            lot_result = self.runtime._run_lot_replays(self.paths, selection)

        self.guard()
        self.update(
            *self.runtime.progress[3],
        )
        with self.runtime.consumer_bindings():
            qualification = self.runtime._qualify(self.paths, selection)

        self.guard()
        self.update(*self.runtime.progress[4])
        with self.runtime.consumer_bindings():
            action_result = self.runtime._run_actions(self.paths, selection)

        self.guard()
        self.update(
            *self.runtime.progress[5],
        )
        with self.runtime.consumer_bindings():
            registry = self.runtime._registry(self.paths, selection)

        self.guard()
        self.update(*self.runtime.progress[6])
        delivery = self.runtime._delivery(self.paths)
        self.guard()
        self.update(
            *self.runtime.progress[7],
            results={
                "curves": curve_result,
                "lots": lot_result,
                "qualification": qualification,
                "actions": action_result,
                "registry": registry,
                "delivery": delivery,
            },
        )
        return 0


def for_profile(profile: str) -> StageRuntime:
    """Create independent orchestration state for one explicit business profile."""
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_common,
        supplier_v8_stage2_common,
        supplier_v8_stage3_common,
    )

    policies = {
        "v7-stage2": supplier_v7_stage2_common,
        "v8-stage2": supplier_v8_stage2_common,
        "v8-stage3": supplier_v8_stage3_common,
    }
    if profile not in policies:
        raise ValueError(f"Unknown delivery profile: {profile}")
    return StageRuntime(profile, policies[profile])


def for_common(common: Any) -> StageRuntime:
    """Resolve existing delivery consumers without modifying pipeline globals."""
    for profile, spec in PROFILES.items():
        if common.__name__.rsplit(".", 1)[-1] == spec["common_name"]:
            return StageRuntime(profile, common)
    raise ValueError("Unknown business contract module")


def verify_archived_inventory(
    inventory_path: Path, archive_path: Path, archive_sha256: str
) -> dict[str, Any]:
    """Verify archived source bytes; never execute them or authorize live resume."""
    with archive_path.open("rb") as stream:
        actual_archive_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_archive_sha != archive_sha256:
        raise ValueError("Source capsule checksum differs")
    inventory = base_common.read_json(inventory_path)
    base_common.verify_signature(inventory, "inventory_signature", "archived inventory")
    schemas = {
        "etudecas.supplier_v7_stage2.v1.source_inventory.v1",
        "etudecas.supplier_v8_stage2.v1.source_inventory.v1",
        "etudecas.supplier_v8_stage3.v1.source_inventory.v1",
        INVENTORY_SCHEMA,
    }
    entries = inventory.get("entries")
    if (
        inventory.get("schema_version") not in schemas
        or not isinstance(entries, list)
        or not entries
        or type(inventory.get("entry_count")) is not int
        or inventory["entry_count"] != len(entries)
    ):
        raise ValueError("Unsupported or incomplete archived source inventory")
    if (
        inventory["schema_version"]
        == "etudecas.supplier_v8_stage3.v1.source_inventory.v1"
    ):
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_v8_stage3_common as historical,
        )

        if inventory.get(
            "predecessor_inventory_signature"
        ) != historical.PREDECESSOR_INVENTORY_SIGNATURE or inventory.get(
            "explicit_stage3_source_filenames"
        ) != list(historical.HISTORICAL_EXPLICIT_SOURCE_FILENAMES):
            raise ValueError("Historical Stage3 predecessor identity differs")
    seen = set()
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate names in source capsule")
        for row in entries:
            if not isinstance(row, Mapping):
                raise ValueError("Malformed archived source row")
            relative = row.get("relative_path", "")
            if not isinstance(relative, str):
                raise ValueError("Malformed archived source name")
            path = PurePosixPath(relative)
            if (
                not relative
                or "\\" in relative
                or ":" in relative
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or relative in seen
            ):
                raise ValueError("Unsafe or repeated archived source name")
            seen.add(relative)
            info = archive.getinfo(relative)
            if (
                info.is_dir()
                or type(row.get("size_bytes")) is not int
                or info.file_size != row["size_bytes"]
            ):
                raise ValueError(f"Archived source size differs: {relative}")
            with archive.open(info) as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != row.get("sha256"):
                raise ValueError(f"Archived source checksum differs: {relative}")
    return {
        "ok": True,
        "status": "archived_sources_verified",
        "source_count": len(seen),
        "inventory_signature": inventory["inventory_signature"],
        "archive_sha256": actual_archive_sha,
        "current_runtime_verified": False,
        "resume_authorized": False,
        "scope": "Signed source inventory and capsule bytes only; campaign results and industrial validity are not certified.",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--profile", choices=tuple(PROFILES))
    parser.add_argument(
        "--mode", choices=("run", "watch", "inventory", "verify-archive")
    )
    options, remaining = parser.parse_known_args(argv)
    if options.mode is None and remaining == ["--help"]:
        parser.print_help()
        return 0
    if options.mode == "verify-archive":
        archive_parser = argparse.ArgumentParser(
            description="Read-only archived source verification; never authorizes resume"
        )
        archive_parser.add_argument("--inventory", type=Path, required=True)
        archive_parser.add_argument("--source-archive", type=Path, required=True)
        archive_parser.add_argument("--archive-sha256", required=True)
        args = archive_parser.parse_args(remaining)
        try:
            print(
                json.dumps(
                    verify_archived_inventory(
                        args.inventory, args.source_archive, args.archive_sha256
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            print(f"Archive verification refused: {exc}", file=sys.stderr)
            return 1
    if options.profile is None or options.mode is None:
        parser.error("--profile and --mode are required for execution")
    runtime = for_profile(options.profile)
    if options.mode == "inventory":
        inventory_parser = argparse.ArgumentParser(
            description="Prepare the current signed source inventory without a campaign"
        )
        inventory_parser.add_argument("--repo", type=Path, required=True)
        inventory_parser.add_argument("--output", type=Path, required=True)
        args = inventory_parser.parse_args(remaining)
        try:
            inventory = runtime.build_source_inventory(args.repo)
            raw = (
                json.dumps(inventory, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8")
            runtime.common.publish_new_or_identical(args.output, raw)
            print(
                json.dumps(
                    {
                        "status": "inventory_prepared",
                        "path": str(args.output.resolve()),
                        "profile": options.profile,
                        "inventory_signature": inventory["inventory_signature"],
                    }
                )
            )
            return 0
        except (OSError, ValueError, runtime.common.Stage2Error) as exc:
            print(f"Inventory preparation refused: {exc}", file=sys.stderr)
            return 1
    return runtime.run(remaining) if options.mode == "run" else runtime.watch(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
