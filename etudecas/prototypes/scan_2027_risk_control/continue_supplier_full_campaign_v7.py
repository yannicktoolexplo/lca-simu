#!/usr/bin/env python3
"""Resume the V7-authorized 3,330-row incident campaign, fail closed.

This downstream-only relay first revalidates the finalized official V7 result.
Only an accepted 150-seed / 450-case result can unlock creation of the separate
30-seed trace package, bridge, incident campaign and consolidated results.  It
never runs, finalizes or modifies the V7 validation itself.  The relay can be
restarted, or detached, without silently overwriting an existing artifact.

Lots, actions, nominal curves and the standalone HTML remain a separate second
delivery stage until their V7 projections are wired and tested.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as bridge_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v4 as relay_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v5 as relay_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v7 as finalizer_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v7 as launcher_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7 as campaign_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as campaign_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


SCHEMA_VERSION = "etudecas.supplier_full_campaign_relay.v7"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservations.v1"
DETACHED_RECEIPT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.detached.v2"
DETACHED_STARTUP_TIMEOUT_SECONDS = 600.0
DETACHED_STARTUP_POLL_SECONDS = 0.1
MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v7"
)
TRACE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_v7_campaign_trace_package"
)
BRIDGE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v7"
)
CAMPAIGN_MODULE = "etudecas.prototypes.scan_2027_risk_control.supplier_operating_point_full_campaign_v7"
LAUNCHER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v7"
)
FINALIZER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "finalize_supplier_operating_point_full_campaign_v7"
)
DASHBOARD_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v7_dashboard"
)
FROZEN_ORCHESTRATOR_SHA256 = {
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v4": (
        "102dc0d8505e184b89e614258ad843a4c02c2e4c0e5a5aea8f060c3e7ae1d14e"
    ),
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v5": (
        "4a42e97e20233c7907a1cd5e6b202aa4f3a24b56e5da3b029d2ab4bc11cb21cd"
    ),
}
V7_MODULES = (
    MODULE_NAME,
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_fresh_development_holdout_protocol_v7",
    TRACE_MODULE,
    BRIDGE_MODULE,
    CAMPAIGN_MODULE,
    LAUNCHER_MODULE,
    FINALIZER_MODULE,
    DASHBOARD_MODULE,
    # The V7 adapters deliberately reuse the mature implementation.  Record the
    # complete local semantic chain, not only the thin V7 entry points, so a
    # restart cannot silently accept a changed compatibility dependency.
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_balanced_product_delay_multiseed_refinement_v6",
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_campaign_v4_contract",
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v4",
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v5",
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v6",
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v4",
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v5",
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v6",
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v4",
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v5",
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v6",
    "etudecas.prototypes.scan_2027_risk_control."
    "finalize_supplier_operating_point_full_campaign_v4",
    "etudecas.prototypes.scan_2027_risk_control."
    "finalize_supplier_operating_point_full_campaign_v5",
    "etudecas.prototypes.scan_2027_risk_control."
    "finalize_supplier_operating_point_full_campaign_v6",
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v4_dashboard",
    "etudecas.prototypes.scan_2027_risk_control.supplier_service_landscape_campaign",
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_service_regime_calibration_protocol",
    "etudecas.simulation.engine.run_first_simulation",
    *FROZEN_ORCHESTRATOR_SHA256,
)
EXPECTED_VALIDATION_SEEDS = 150
EXPECTED_VALIDATION_CASES = 450
EXPECTED_CAMPAIGN_SEEDS = 30
EXPECTED_BASELINE_TRACES = 90
EXPECTED_INCIDENT_ROWS = 3_240
EXPECTED_CAMPAIGN_ROWS = 3_330
EXPECTED_SHARDS = 18

FullCampaignRelayError = relay_v4.FullCampaignRelayError
RelayTimeout = relay_v4.RelayTimeout


class ScientificNoGo(FullCampaignRelayError):
    """The complete official V7 result exists but rejected the fixed triplet."""


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


@dataclass(frozen=True)
class V7CampaignRelayConfig:
    repo: Path
    v7_plan_dir: Path
    v7_run_dir: Path
    trace_package_dir: Path
    bridge_json: Path
    campaign_root: Path
    results_dir: Path
    supervision_dir: Path
    parallel_shards: int = 2
    workers_per_shard: int = 2
    launcher_poll_seconds: float = 5.0
    relay_poll_seconds: float = 30.0
    max_wait_hours: float = 240.0

    def resolved(self) -> "V7CampaignRelayConfig":
        return V7CampaignRelayConfig(
            repo=self.repo.resolve(),
            v7_plan_dir=self.v7_plan_dir.resolve(),
            v7_run_dir=self.v7_run_dir.resolve(),
            trace_package_dir=self.trace_package_dir.resolve(),
            bridge_json=self.bridge_json.resolve(),
            campaign_root=self.campaign_root.resolve(),
            results_dir=self.results_dir.resolve(),
            supervision_dir=self.supervision_dir.resolve(),
            parallel_shards=self.parallel_shards,
            workers_per_shard=self.workers_per_shard,
            launcher_poll_seconds=self.launcher_poll_seconds,
            relay_poll_seconds=self.relay_poll_seconds,
            max_wait_hours=self.max_wait_hours,
        )

    def public_mapping(self) -> dict[str, Any]:
        return {
            key: str(value) if isinstance(value, Path) else value
            for key, value in self.__dict__.items()
        }

    def validate(self) -> None:
        expected_repo = Path(__file__).resolve().parents[3]
        if not self.repo.is_dir() or self.repo != expected_repo:
            raise FullCampaignRelayError(
                f"Le dépôt configuré n'est pas celui du relais V7 : {self.repo}"
            )
        for label, source in (
            ("plan V7", self.v7_plan_dir),
            ("run V7", self.v7_run_dir),
        ):
            if not source.is_dir():
                raise FullCampaignRelayError(f"{label} absent : {source}")
        if self.v7_plan_dir == self.v7_run_dir:
            raise FullCampaignRelayError("Le plan et le run V7 doivent être distincts")
        if self.parallel_shards not in (1, 2) or self.workers_per_shard not in (1, 2):
            raise FullCampaignRelayError(
                "Les parallélismes de campagne doivent valoir 1 ou 2"
            )
        if not 0.0 <= self.launcher_poll_seconds <= 60.0:
            raise FullCampaignRelayError(
                "launcher_poll_seconds doit être compris entre 0 et 60"
            )
        if not 0.1 <= self.relay_poll_seconds <= 60.0:
            raise FullCampaignRelayError(
                "relay_poll_seconds doit être compris entre 0,1 et 60"
            )
        if self.max_wait_hours <= 0:
            raise FullCampaignRelayError("max_wait_hours doit être strictement positif")

        output_dirs = (
            self.trace_package_dir,
            self.campaign_root,
            self.results_dir,
            self.supervision_dir,
        )
        for label, output in (
            ("package de traces", self.trace_package_dir),
            ("campagne", self.campaign_root),
            ("résultats", self.results_dir),
            ("supervision", self.supervision_dir),
        ):
            if output.exists() and not output.is_dir():
                raise FullCampaignRelayError(f"La sortie {label} n'est pas un dossier")
        if self.bridge_json.exists() and not self.bridge_json.is_file():
            raise FullCampaignRelayError("Le chemin du pont V7 n'est pas un fichier")

        protected = (self.repo, self.v7_plan_dir, self.v7_run_dir)
        for output in (*output_dirs, self.bridge_json):
            if any(_paths_overlap(output, source) for source in protected):
                raise FullCampaignRelayError(
                    f"Une sortie aval chevauche une source protégée : {output}"
                )
        for index, left in enumerate(output_dirs):
            for right in output_dirs[index + 1 :]:
                if _paths_overlap(left, right):
                    raise FullCampaignRelayError(
                        "Les racines traces/campagne/résultats/supervision doivent "
                        "être séparées"
                    )
        if any(_paths_overlap(self.bridge_json, root) for root in output_dirs):
            raise FullCampaignRelayError(
                "Le pont V7 doit être séparé de tous les dossiers de preuves"
            )


class FullCampaignRelayV7(relay_v4.FullCampaignRelay):
    """Crash-resumable V7 handoff through consolidated incident results."""

    def __init__(
        self,
        config: V7CampaignRelayConfig,
        *,
        command_executor: relay_v4.CommandExecutor | None = None,
        sleep: Any = None,
        monotonic: Any = None,
    ) -> None:
        kwargs: dict[str, Any] = {"command_executor": command_executor}
        if sleep is not None:
            kwargs["sleep"] = sleep
        if monotonic is not None:
            kwargs["monotonic"] = monotonic
        super().__init__(config, **kwargs)  # type: ignore[arg-type]
        self.config: V7CampaignRelayConfig

    def _module_inventory_v7(self) -> list[dict[str, str]]:
        trace_package.validate_frozen_v7_protocol()
        campaign_v7.validate_frozen_implementation()
        launcher_v7.validate_frozen_implementation()
        finalizer_v7.validate_frozen_implementation()
        dashboard_v7.validate_frozen_implementation()
        rows: list[dict[str, str]] = []
        for module in V7_MODULES:
            path = relay_v4._module_path(self.config.repo, module).resolve()  # noqa: SLF001
            if not path.is_file():
                raise FullCampaignRelayError(f"Module V7 requis absent : {module}")
            digest = relay_v4.sha256_file(path)
            frozen = FROZEN_ORCHESTRATOR_SHA256.get(module)
            if frozen is not None and digest != frozen:
                raise FullCampaignRelayError(
                    f"Orchestrateur mature réutilisé modifié : {module} ({digest})"
                )
            rows.append(
                {
                    "module": module,
                    "path": str(path),
                    "sha256": digest,
                }
            )
        return rows

    def _assert_source_inventory_unchanged(self) -> None:
        """Reject resume/reuse when any signed semantic dependency drifted."""

        current = self._module_inventory_v7()
        if not self.contract or current != self.contract.get("source_inventory"):
            raise FullCampaignRelayError(
                "Le code V7 ou une d\u00e9pendance mature a chang\u00e9; "
                "nouvelle supervision audit\u00e9e requise"
            )

    def run_step(
        self,
        *,
        step: str,
        command: Sequence[str],
        completion_check: relay_v4.CompletionCheck,
        message_fr: str,
        progress_reader: relay_v4.ProgressReader | None = None,
        run_even_if_complete: bool = False,
    ) -> None:
        """Recheck the transitive signed inventory at every step boundary."""

        self._assert_source_inventory_unchanged()
        super().run_step(
            step=step,
            command=command,
            completion_check=completion_check,
            message_fr=message_fr,
            progress_reader=progress_reader,
            run_even_if_complete=run_even_if_complete,
        )
        self._assert_source_inventory_unchanged()

    def validate_v7_handoff(self) -> dict[str, Any]:
        """Reopen all 450 proofs before any downstream destination is touched."""

        try:
            trace_package.validate_frozen_v7_protocol()
            plan = protocol_v7.validate_plan(
                self.config.v7_plan_dir,
                allow_test_source=False,
                verify_runtime=True,
            )
            result = protocol_v7.validate_result(
                plan.plan_dir,
                self.config.v7_run_dir,
                test_only=False,
            )
        except Exception as exc:
            raise FullCampaignRelayError(
                "Le résultat V7 officiel est absent, incomplet ou non reproductible"
            ) from exc
        if result.get("accepted") is not True:
            raise ScientificNoGo(
                "Le triplet fixe a été rejeté par V7; aucune campagne incidents"
            )
        try:
            evidence = protocol_v7.validated_evidence(
                plan.plan_dir,
                self.config.v7_run_dir,
                test_only=False,
            )
        except Exception as exc:
            raise FullCampaignRelayError(
                "Les 450 preuves physiques V7 ne sont pas toutes relisibles"
            ) from exc
        expected_subset = {
            (candidate.key, seed)
            for candidate in protocol_v7.FIXED_TRIPLET
            for seed in trace_package.CAMPAIGN_SEEDS
        }
        if (
            result.get("status") != protocol_v7.ACCEPTED_STATUS
            or result.get("publishable") is not True
            or result.get("execution_mode") != protocol_v7.OFFICIAL_EXECUTION_MODE
            or result.get("plan_signature") != plan.manifest["plan_signature"]
            or result.get("validation_seed_count") != EXPECTED_VALIDATION_SEEDS
            or result.get("fresh_physical_evidence_case_count")
            != EXPECTED_VALIDATION_CASES
            or result.get("v5_v6_acceptance_evidence_reused") is not False
            or result.get("v6_holdout_reused_as_v7_acceptance_evidence") is not False
            or result.get("retuning_after_any_v7_result") is not False
            or len(evidence) != EXPECTED_VALIDATION_CASES
            or not expected_subset.issubset(evidence)
            or tuple(protocol_v7.V7_VALIDATION_SEEDS[:EXPECTED_CAMPAIGN_SEEDS])
            != trace_package.CAMPAIGN_SEEDS
        ):
            raise FullCampaignRelayError("Le contrat scientifique V7 a changé")
        plan_path = plan.plan_dir / "protocol_manifest.json"
        run_manifest_path = self.config.v7_run_dir / "run_manifest.json"
        result_path = self.config.v7_run_dir / "validation_result.json"
        return {
            "status": "accepted_read_only_v7_handoff",
            "plan": str(plan_path.resolve()),
            "plan_sha256": relay_v4.sha256_file(plan_path),
            "plan_signature": plan.manifest["plan_signature"],
            "run_manifest": str(run_manifest_path.resolve()),
            "run_manifest_sha256": relay_v4.sha256_file(run_manifest_path),
            "result": str(result_path.resolve()),
            "result_sha256": relay_v4.sha256_file(result_path),
            "result_signature": result["result_signature"],
            "validation_seed_count": EXPECTED_VALIDATION_SEEDS,
            "fresh_physical_evidence_case_count": EXPECTED_VALIDATION_CASES,
            "campaign_seed_count": EXPECTED_CAMPAIGN_SEEDS,
            "campaign_baseline_case_count": EXPECTED_BASELINE_TRACES,
            "campaign_seed_selection": "first_30_v7_seed_blocks_fixed_before_run",
            "campaign_subset_is_acceptance_gate": False,
            "retuning_after_v7": False,
            "v7_files_modified": False,
        }

    def _build_contract(
        self, handoff: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if handoff is None:
            handoff = self.validate_v7_handoff()
        unsigned = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "configuration": self.config.public_mapping(),
            "source_inventory": self._module_inventory_v7(),
            "v7_handoff": dict(handoff),
            "scientific_contract": {
                "sole_operating_point_authorization": "accepted_official_v7",
                "validation_seed_count": EXPECTED_VALIDATION_SEEDS,
                "fresh_validation_case_count": EXPECTED_VALIDATION_CASES,
                "campaign_seed_count": EXPECTED_CAMPAIGN_SEEDS,
                "derived_baseline_trace_count": EXPECTED_BASELINE_TRACES,
                "baseline_rows": EXPECTED_BASELINE_TRACES,
                "incident_rows": EXPECTED_INCIDENT_ROWS,
                "campaign_rows": EXPECTED_CAMPAIGN_ROWS,
                "campaign_shards": EXPECTED_SHARDS,
                "same_30_seeds_for_baseline_and_incidents": True,
                "campaign_subset_used_for_v7_acceptance": False,
                "prior_version_simulation_evidence_reused": False,
                "quality_incident_included": False,
                "availability_incident_included": False,
                "capacity_incident_included": False,
                "stock_incident_included": False,
                "supplier_state_dependent_risks_enabled": False,
                "incident_mechanisms": [
                    "transport_delay",
                    "planned_delivery_shortfall",
                ],
                "historical_incident_probability_estimated": False,
            },
            "execution_contract": {
                "scope": "v7_downstream_campaign_only",
                "v7_engine_runs_started_by_relay": 0,
                "v7_plan_run_or_result_modified": False,
                "trace_derivation_engine_runs": 0,
                "shell": False,
                "resume_from_validated_artifacts": True,
                "old_results_overwritten": False,
                "launcher_owns_discovery_smoke_and_shards": True,
                "post_campaign_lots_curves_actions_html_in_this_stage": False,
            },
        }
        return {
            **unsigned,
            "contract_signature": relay_v4.stable_sha256(unsigned),
        }

    def prepare(self) -> None:
        self.config.validate()
        # This is intentionally before mkdir/status/receipt creation.
        handoff = self.validate_v7_handoff()
        self.config.supervision_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        expected = self._build_contract(handoff)
        if self.contract_path.is_file():
            actual = relay_v4._read_json(self.contract_path)  # noqa: SLF001
            relay_v4._verify_signed_json(  # noqa: SLF001
                actual, "contract_signature", "contrat relais V7"
            )
            if actual != expected:
                raise FullCampaignRelayError(
                    "Le contrat relais V7 existant diffère; nouvelle supervision requise"
                )
            self.contract = actual
        else:
            allowed = {"logs", ".relay.lock", "detached.json", "detached_relay.log"}
            if any(
                path.name not in allowed
                for path in self.config.supervision_dir.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Le dossier de supervision V7 non enregistré n'est pas vide"
                )
            self.contract = expected
            relay_v4._atomic_json(self.contract_path, expected)  # noqa: SLF001
        self._load_or_create_status()
        self._reserve_outputs()

    def _load_or_create_status(self) -> None:
        signature = self.contract["contract_signature"]
        if self.status_path.is_file():
            payload = relay_v4._read_json(self.status_path)  # noqa: SLF001
            relay_v4._verify_signed_json(  # noqa: SLF001
                payload, "status_signature", "statut relais V7"
            )
            if (
                payload.get("schema_version") != STATUS_SCHEMA_VERSION
                or payload.get("contract_signature") != signature
            ):
                raise FullCampaignRelayError("Statut V7 étranger au contrat")
            self.status = payload
            return
        self.status = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "contract_signature": signature,
            "status": "running",
            "stage": "validation_v7_acceptee",
            "message_fr": (
                "Les 450 preuves V7 sont acceptées; la campagne aval peut commencer."
            ),
            "relay_pid": os.getpid(),
            "started_at_utc": relay_v4._now(),  # noqa: SLF001
            "updated_at_utc": relay_v4._now(),  # noqa: SLF001
            "completed_at_utc": "",
            "active_command": {},
            "steps": {},
            "artifacts": {},
            "scientific_guardrails": self.contract["scientific_contract"],
            "v7_handoff": self.contract["v7_handoff"],
        }
        self._write_status()

    def _reserve_outputs(self) -> None:
        unsigned = {
            "schema_version": RESERVATION_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "paths": {
                "trace_package_dir": str(self.config.trace_package_dir),
                "bridge_json": str(self.config.bridge_json),
                "campaign_root": str(self.config.campaign_root),
                "results_dir": str(self.config.results_dir),
            },
        }
        expected = {
            **unsigned,
            "reservation_signature": relay_v4.stable_sha256(unsigned),
        }
        if self.reservations_path.is_file():
            actual = relay_v4._read_json(self.reservations_path)  # noqa: SLF001
            relay_v4._verify_signed_json(  # noqa: SLF001
                actual, "reservation_signature", "réservations relais V7"
            )
            if actual != expected:
                raise FullCampaignRelayError("Réservations V7 incohérentes")
        else:
            relay_v4._atomic_json(self.reservations_path, expected)  # noqa: SLF001

    def _trace_package_ready(self) -> bool:
        manifest = self.config.trace_package_dir / "trace_package_manifest.json"
        if not manifest.is_file():
            if self.config.trace_package_dir.exists() and any(
                self.config.trace_package_dir.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Package de traces V7 non vide mais sans manifeste valide"
                )
            return False
        payload = trace_package.validate_package(
            self.config.trace_package_dir,
            plan_dir=self.config.v7_plan_dir,
            run_dir=self.config.v7_run_dir,
        )
        if (
            payload.get("campaign_cohort", {}).get("seeds")
            != list(trace_package.CAMPAIGN_SEEDS)
            or len(payload.get("trace_index") or []) != EXPECTED_BASELINE_TRACES
            or payload.get("engine_runs_performed") != 0
            or payload.get("v4_v5_v6_simulation_evidence_reused") is not False
        ):
            raise FullCampaignRelayError("Package de traces V7 incompatible")
        return True

    def build_trace_package(self) -> None:
        self.run_step(
            step="derivation_90_traces_v7",
            command=self._python_module(
                TRACE_MODULE,
                "build",
                "--plan-dir",
                str(self.config.v7_plan_dir),
                "--run-dir",
                str(self.config.v7_run_dir),
                "--output-dir",
                str(self.config.trace_package_dir),
            ),
            completion_check=self._trace_package_ready,
            message_fr=(
                "Dérivation sans moteur des 90 traces appariées depuis les CSV V7."
            ),
        )
        self._record_artifact(
            "v7_campaign_trace_package",
            self.config.trace_package_dir / "trace_package_manifest.json",
        )

    def _bridge_ready(self) -> bool:
        if not self.config.bridge_json.is_file():
            return False
        payload = bridge_v7.validate_bridge(
            self.config.bridge_json,
            revalidate_source=True,
        )
        if (
            payload.get("holdout_contract", {})
            .get("validation_protocol", {})
            .get("fresh_physical_evidence_case_count")
            != EXPECTED_VALIDATION_CASES
            or payload.get("holdout_contract", {})
            .get("campaign_baseline_contract", {})
            .get("acceptance_gate")
            is not False
            or len(payload.get("trace_index") or []) != EXPECTED_BASELINE_TRACES
        ):
            raise FullCampaignRelayError("Pont V7 incomplet ou ambigu")
        return True

    def build_and_validate_bridge(self) -> None:
        self.run_step(
            step="construction_pont_v7",
            command=self._python_module(
                BRIDGE_MODULE,
                "build",
                "--v7-plan-dir",
                str(self.config.v7_plan_dir),
                "--v7-run-dir",
                str(self.config.v7_run_dir),
                "--trace-package-dir",
                str(self.config.trace_package_dir),
                "--output",
                str(self.config.bridge_json),
            ),
            completion_check=self._bridge_ready,
            message_fr=(
                "Construction du pont V7 séparant validation 150 graines et campagne 30 graines."
            ),
        )
        self._record_artifact(
            "validated_operating_points_bridge", self.config.bridge_json
        )

    def _campaign_plan_ready(self) -> bool:
        manifest_path = self.config.campaign_root / "campaign_manifest.json"
        shard_path = self.config.campaign_root / "shard_plan.csv"
        if not manifest_path.is_file() and not shard_path.is_file():
            if self.config.campaign_root.exists() and any(
                self.config.campaign_root.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Racine campagne V7 non vide mais sans plan enregistré"
                )
            return False
        if not manifest_path.is_file() or not shard_path.is_file():
            return False
        with launcher_v7.patched_v7_context():
            launcher = launcher_v7.implementation_v4
            manifest, shards = launcher.load_campaign_plan(
                self.config.campaign_root,
                campaign_v7.ADAPTER_PATH,
            )
        counts = manifest.get("expected_counts") or {}
        if (
            len(shards) != EXPECTED_SHARDS
            or tuple(manifest.get("seeds") or ()) != trace_package.CAMPAIGN_SEEDS
            or counts.get("baseline_rows") != EXPECTED_BASELINE_TRACES
            or counts.get("incident_rows") != EXPECTED_INCIDENT_ROWS
            or counts.get("total_rows") != EXPECTED_CAMPAIGN_ROWS
            or any(
                manifest.get(flag) is not False
                for flag in (
                    "quality_branch_included",
                    "quality_incident_included",
                    "availability_incident_included",
                    "capacity_incident_included",
                    "stock_incident_included",
                    "supplier_state_dependent_risks_enabled",
                )
            )
        ):
            raise FullCampaignRelayError("Plan campagne V7 incomplet")
        return True

    def plan_campaign(self) -> None:
        self.run_step(
            step="planification_campagne_v7",
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
            message_fr="Plan figé : 3 états, 18 voies, 2 incidents et 30 graines.",
        )
        self._record_artifact(
            "campaign_manifest", self.config.campaign_root / "campaign_manifest.json"
        )

    def _launch_progress(self) -> dict[str, Any]:
        path = self.config.campaign_root / "launch_progress.json"
        if not path.is_file():
            return {}
        payload = relay_v4._read_json(path)  # noqa: SLF001
        return {
            "launcher_status": payload.get("status"),
            "phase": payload.get("phase"),
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
        payload = relay_v4._read_json(path)  # noqa: SLF001
        status = str(payload.get("status") or "")
        if status in relay_v4.RUNNING_LAUNCH_STATUSES or status.startswith(
            "interrupted"
        ):
            return False
        if status != "complete":
            raise FullCampaignRelayError(
                f"Le lanceur V7 a publié un statut terminal invalide : {status}"
            )
        with launcher_v7.patched_v7_context():
            launcher = launcher_v7.implementation_v4
            manifest, shards = launcher.load_campaign_plan(
                self.config.campaign_root,
                campaign_v7.ADAPTER_PATH,
            )
            expected_contract = launcher._launch_contract(  # noqa: SLF001
                manifest=manifest,
                runner=campaign_v7.ADAPTER_PATH,
                shards=shards,
            )
            contract_path = self.config.campaign_root / "launch_contract.json"
            if (
                not contract_path.is_file()
                or relay_v4._read_json(contract_path) != expected_contract  # noqa: SLF001
                or payload.get("schema_version") != launcher.PROGRESS_SCHEMA_VERSION
                or payload.get("campaign_signature")
                != manifest.get("campaign_signature")
                or payload.get("launch_contract_signature")
                != expected_contract.get("launch_contract_signature")
            ):
                raise FullCampaignRelayError(
                    "Contrat/progression du lanceur V7 incohérent"
                )
            discovery_state, discovery_detail = launcher._discovery_completion_state(  # noqa: SLF001
                self.config.campaign_root,
                manifest=manifest,
            )
            smoke_state, smoke_detail = launcher._smoke_completion_state(  # noqa: SLF001
                self.config.campaign_root,
                manifest=manifest,
            )
            if discovery_state != "complete":
                raise FullCampaignRelayError(
                    "Choix des fenêtres incomplet : " + discovery_detail
                )
            if smoke_state != "complete":
                raise FullCampaignRelayError(
                    "Contrôle op_93 incomplet : " + smoke_detail
                )
            for shard in shards:
                shard_state, shard_detail = launcher._completion_state(  # noqa: SLF001
                    self.config.campaign_root,
                    campaign_signature=str(manifest["campaign_signature"]),
                    shard=shard,
                )
                if shard_state != "complete":
                    raise FullCampaignRelayError(
                        f"Bloc {shard.shard_id} non validé : {shard_detail}"
                    )
        if (
            payload.get("phase") != "shards"
            or payload.get("target_discovery_status") != "complete"
            or payload.get("planned_shard_count") != EXPECTED_SHARDS
            or payload.get("completed_shard_count") != EXPECTED_SHARDS
            or payload.get("failed_shard_count") != 0
            or payload.get("active_shard_count") != 0
            or payload.get("queued_shard_count") != 0
        ):
            raise FullCampaignRelayError("Progression finale du lanceur V7 incohérente")
        return True

    def launch_campaign(self) -> None:
        self._wait_for_orphaned_launcher_children()
        self.run_step(
            step="campagne_incidents_v7",
            command=self._python_module(
                LAUNCHER_MODULE,
                "--campaign-root",
                str(self.config.campaign_root),
                "--runner",
                str(campaign_v7.ADAPTER_PATH),
                "--parallel-shards",
                str(self.config.parallel_shards),
                "--workers-per-shard",
                str(self.config.workers_per_shard),
                "--poll-seconds",
                str(self.config.launcher_poll_seconds),
            ),
            completion_check=self._campaign_launch_ready,
            progress_reader=self._launch_progress,
            message_fr=(
                "Exécution relançable des 3 choix de fenêtre, du contrôle op_93 et des 18 blocs."
            ),
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
                    "Dossier de résultats V7 non vide sans validation finale"
                )
            return False
        payload = relay_v4._read_json(validation_path)  # noqa: SLF001
        expected = payload.get("expected_contract") or {}
        comparisons = payload.get("comparability_checks") or {}
        signed = payload.get("signed_case_evidence") or {}
        if (
            payload.get("status") != "complete_validated"
            or expected.get("repetition_ids") != list(trace_package.CAMPAIGN_SEEDS)
            or expected.get("paired_repetition_count") != EXPECTED_CAMPAIGN_SEEDS
            or expected.get("lane_count") != 18
            or expected.get("baseline_row_count") != EXPECTED_BASELINE_TRACES
            or expected.get("incident_row_count") != EXPECTED_INCIDENT_ROWS
            or expected.get("mechanisms")
            != ["transport_delay", "planned_delivery_shortfall"]
            or expected.get("quality_branch_included") is not False
            or expected.get("availability_incident_included") is not False
            or comparisons.get("complete_3x18x2x30_matrix") is not True
            or comparisons.get(
                "all_3330_metrics_reconstructed_from_signed_case_evidence"
            )
            is not True
            or comparisons.get("mandatory_non_reusable_op93_smoke_validated")
            is not True
            or comparisons.get("quality_or_availability_incident_count") != 0
            or signed.get("case_count") != EXPECTED_CAMPAIGN_ROWS
        ):
            raise FullCampaignRelayError("Résultats V7 non libérables")
        overlay = finalizer_v7.validate_v7_overlay(
            self.config.campaign_root, self.config.results_dir
        )
        overlay_checks = overlay.get("v7_comparability_checks") or {}
        if (
            overlay.get("status") != "complete_validated_v7_overlay"
            or overlay_checks.get(
                "v7_confirmation_150_seeds_450_cases_signed_and_accepted"
            )
            is not True
            or overlay_checks.get(
                "v7_first30_90_shipment_traces_used_for_pairing_without_rerun"
            )
            is not True
            or overlay_checks.get("campaign_subset_used_as_v7_acceptance_gate")
            is not False
        ):
            raise FullCampaignRelayError("Surcouche scientifique V7 non libérable")
        if not self._campaign_plan_ready():
            raise FullCampaignRelayError("V7 campaign plan is no longer readable")
        dashboard_v7.load_dashboard_data(results_dir=self.config.results_dir)
        return True

    def finalize_campaign(self) -> None:
        self.run_step(
            step="consolidation_3330_lignes_v7",
            command=self._python_module(
                FINALIZER_MODULE,
                "--campaign-root",
                str(self.config.campaign_root),
                "--output-dir",
                str(self.config.results_dir),
            ),
            completion_check=self._results_ready,
            message_fr=(
                "Reconstruction des 3 330 preuves, sensibilités et priorités fournisseurs."
            ),
        )
        self._record_artifact(
            "campaign_validation", self.config.results_dir / "campaign_validation.json"
        )
        self._record_artifact(
            "campaign_validation_v7",
            self.config.results_dir / finalizer_v7.V7_RESULT_OVERLAY_NAME,
        )

    def execute(self, *, prepared: bool = False) -> int:
        if not prepared:
            self.prepare()
        self._assert_source_inventory_unchanged()
        self.build_trace_package()
        self.build_and_validate_bridge()
        self.plan_campaign()
        self.launch_campaign()
        self.finalize_campaign()
        self.status["active_command"] = {}
        self.status["completed_at_utc"] = relay_v4._now()  # noqa: SLF001
        self.update_status(
            "campagne_v7_consolidee",
            (
                "Campagne V7 terminée : 3 330 cas consolidés. "
                "Lots, actions, courbes et HTML restent l'étape aval suivante."
            ),
            status="complete_campaign_results_pending_delivery_stage",
            progress={
                "validated_v7_cases": EXPECTED_VALIDATION_CASES,
                "derived_baseline_traces": EXPECTED_BASELINE_TRACES,
                "campaign_rows": EXPECTED_CAMPAIGN_ROWS,
                "v7_engine_runs_by_relay": 0,
            },
        )
        return 0


def _config_from_args(args: argparse.Namespace) -> V7CampaignRelayConfig:
    return V7CampaignRelayConfig(
        repo=args.repo,
        v7_plan_dir=args.v7_plan_dir,
        v7_run_dir=args.v7_run_dir,
        trace_package_dir=args.trace_package_dir,
        bridge_json=args.bridge_json,
        campaign_root=args.campaign_root,
        results_dir=args.results_dir,
        supervision_dir=args.supervision_dir,
        parallel_shards=args.parallel_shards,
        workers_per_shard=args.workers_per_shard,
        launcher_poll_seconds=args.launcher_poll_seconds,
        relay_poll_seconds=args.relay_poll_seconds,
        max_wait_hours=args.max_wait_hours,
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
        "--detached-child-token",
        token,
    ]


def _stop_detached_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
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
    else:  # pragma: no cover
        import signal

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=30.0)
    except subprocess.TimeoutExpired:
        process.kill()


@contextmanager
def _relay_lock_with_retry(path: Path, *, wait_seconds: float = 0.0) -> Iterator[None]:
    """Acquire the mature lock, optionally retrying a short reservation race."""

    deadline = time.monotonic() + max(0.0, wait_seconds)
    manager: Any = None
    while True:
        candidate = relay_v5._relay_lock(path)  # noqa: SLF001
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


def _read_detached_receipt(path: Path) -> dict[str, Any]:
    payload = relay_v4._read_json(path)  # noqa: SLF001
    relay_v4._verify_signed_json(  # noqa: SLF001
        payload, "receipt_signature", "reçu détaché V7"
    )
    if payload.get("schema_version") != DETACHED_RECEIPT_SCHEMA_VERSION:
        raise FullCampaignRelayError("Schéma du reçu détaché V7 incohérent")
    return payload


def _publish_detached_failure(
    path: Path,
    *,
    token: str,
    status: str,
    error: BaseException,
) -> dict[str, Any]:
    current = _read_detached_receipt(path)
    if current.get("launch_token") != token:
        raise FullCampaignRelayError("Refus de modifier le reçu d'un autre lancement")
    unsigned = {
        **{key: value for key, value in current.items() if key != "receipt_signature"},
        "status": status,
        "error_type": type(error).__name__,
        "error": str(error),
        "failed_at_utc": relay_v4._now(),  # noqa: SLF001
    }
    payload = {
        **unsigned,
        "receipt_signature": relay_v4.stable_sha256(unsigned),
    }
    relay_v4._atomic_json(path, payload)  # noqa: SLF001
    return payload


def _validate_detached_child_token(relay: FullCampaignRelayV7, token: str) -> None:
    receipt = _read_detached_receipt(relay.config.supervision_dir / "detached.json")
    if (
        not token
        or receipt.get("launch_token") != token
        or receipt.get("status") != "detached_start_reserved"
        or receipt.get("configuration_sha256")
        != relay_v4.stable_sha256(relay.config.public_mapping())
    ):
        raise FullCampaignRelayError("Jeton ou réservation du relais détaché invalide")


def _publish_detached_ready(
    relay: FullCampaignRelayV7, *, token: str
) -> dict[str, Any]:
    """Publish readiness only while the caller owns the relay lock."""

    path = relay.config.supervision_dir / "detached.json"
    current = _read_detached_receipt(path)
    if current.get("launch_token") != token or current.get("status") != (
        "detached_start_reserved"
    ):
        raise FullCampaignRelayError("Réservation détachée remplacée avant readiness")
    if not relay.contract or not relay.status:
        raise FullCampaignRelayError("Relais détaché non préparé sous verrou")
    unsigned = {
        **{key: value for key, value in current.items() if key != "receipt_signature"},
        "status": "detached_relay_ready",
        "pid": os.getpid(),
        "ready_at_utc": relay_v4._now(),  # noqa: SLF001
        "lock_acquired": True,
        "contract_signature": relay.contract["contract_signature"],
    }
    payload = {
        **unsigned,
        "receipt_signature": relay_v4.stable_sha256(unsigned),
    }
    relay_v4._atomic_json(path, payload)  # noqa: SLF001
    return payload


def _wait_for_detached_ready(
    process: subprocess.Popen[Any],
    *,
    receipt_path: Path,
    token: str,
    timeout_seconds: float = DETACHED_STARTUP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        receipt = _read_detached_receipt(receipt_path)
        if (
            receipt.get("status") == "detached_relay_ready"
            and receipt.get("launch_token") == token
            and receipt.get("pid") == process.pid
            and receipt.get("lock_acquired") is True
            and campaign_contract.is_sha256(receipt.get("contract_signature"))
        ):
            ready_exit_code = process.poll()
            if ready_exit_code not in (None, 0):
                error = FullCampaignRelayError(
                    "Le relais détaché a échoué après readiness "
                    f"(code {ready_exit_code})"
                )
                _publish_detached_failure(
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
                f"Le relais détaché est mort avant readiness (code {return_code})"
            )
            _publish_detached_failure(
                receipt_path,
                token=token,
                status="detached_child_exited_before_ready",
                error=error,
            )
            raise error
        if time.monotonic() >= deadline:
            _stop_detached_tree(process)
            error = FullCampaignRelayError(
                "Le relais détaché n'a pas confirmé son verrou avant la limite"
            )
            _publish_detached_failure(
                receipt_path,
                token=token,
                status="detached_start_timeout",
                error=error,
            )
            raise error
        time.sleep(DETACHED_STARTUP_POLL_SECONDS)


def detach(args: argparse.Namespace) -> dict[str, Any]:
    """Preflight V7 and return only after the child owns the relay lock."""

    config = _config_from_args(args)
    relay = FullCampaignRelayV7(config)
    config.validate()
    handoff = relay.validate_v7_handoff()
    config.supervision_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = config.supervision_dir / "detached.json"
    if receipt_path.exists():
        raise FullCampaignRelayError(
            "Un reçu détaché V7 existe déjà; utiliser une nouvelle supervision"
        )
    token = uuid4().hex
    command = _child_command(args, token)
    log_path = config.supervision_dir / "detached_relay.log"
    reserved_unsigned = {
        "schema_version": DETACHED_RECEIPT_SCHEMA_VERSION,
        "status": "detached_start_reserved",
        "pid": 0,
        "launch_token": token,
        "command": command,
        "command_sha256": relay_v4.stable_sha256(command),
        "configuration_sha256": relay_v4.stable_sha256(config.public_mapping()),
        "v7_result_signature": handoff["result_signature"],
        "log_path": str(log_path),
        "status_path": str(relay.status_path),
        "started_at_utc": relay_v4._now(),  # noqa: SLF001
        "preflight_completed_before_process_start": True,
        "parent_success_requires_child_lock_readiness": True,
    }
    reserved = {
        **reserved_unsigned,
        "receipt_signature": relay_v4.stable_sha256(reserved_unsigned),
    }
    try:
        with receipt_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(reserved, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise FullCampaignRelayError(
            "Un autre relais détaché V7 a réservé cette supervision"
        ) from exc
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
        _publish_detached_failure(
            receipt_path,
            token=token,
            status="detached_start_failed",
            error=exc,
        )
        raise
    try:
        return _wait_for_detached_ready(
            process,
            receipt_path=receipt_path,
            token=token,
        )
    except BaseException:
        _stop_detached_tree(process)
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
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--launcher-poll-seconds", type=float, default=5.0)
    parser.add_argument("--relay-poll-seconds", type=float, default=30.0)
    parser.add_argument("--max-wait-hours", type=float, default=240.0)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--detach", action="store_true")
    mode.add_argument("--detached-child-token", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.detach:
        try:
            print(json.dumps(detach(args), ensure_ascii=False, indent=2))
            return 0
        except ScientificNoGo as exc:
            print(f"RELAIS V7 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
            return 3
        except Exception as exc:
            print(f"RELAIS V7 NON LANCÉ : {exc}", file=sys.stderr)
            return 2
    config = _config_from_args(args)
    relay = FullCampaignRelayV7(config)
    relay_v4._prevent_sleep(True)  # noqa: SLF001
    try:
        # No lock or status directory is created before the accepted V7 readback.
        config.validate()
        token = str(args.detached_child_token or "")
        if not token:
            relay.validate_v7_handoff()
        with _relay_lock_with_retry(
            config.supervision_dir / ".relay.lock",
            wait_seconds=60.0 if token else 0.0,
        ):
            if token:
                _validate_detached_child_token(relay, token)
                relay.prepare()
                _publish_detached_ready(relay, token=token)
                return relay.execute(prepared=True)
            return relay.execute()
    except ScientificNoGo as exc:
        print(f"RELAIS V7 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("RELAIS V7 INTERROMPU; consulter status.json", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - process boundary diagnostics
        if relay.contract:
            relay.status["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc)),
            }
            relay.update_status("echec_v7", str(exc), status="failed")
        print(f"RELAIS V7 EN ÉCHEC : {exc}", file=sys.stderr)
        return 1
    finally:
        relay_v4._prevent_sleep(False)  # noqa: SLF001


if __name__ == "__main__":
    raise SystemExit(main())
