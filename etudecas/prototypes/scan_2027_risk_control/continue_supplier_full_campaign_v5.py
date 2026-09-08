#!/usr/bin/env python3
"""Run the downstream-only V5 supplier delivery handoff.

Calibration is an immutable input to this process.  Before creating any relay
or downstream output, the handoff reopens and validates the signed V5 plan,
the complete 210-case development matrix and selection, the accepted 90-case
holdout without retuning, and both finalized curve-capture inventories.  It
never plans, executes, resumes, or finalizes development or holdout.

Only after that fail-closed read-only preflight may the relay build the bridge
and 3,330-row incident campaign, replay selected lots, qualify the physical
cascade evidence, run required actions and curves, and invoke the strict V5
three-view renderer.  No V4 source, calibration result, or legacy HTML is
overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v5 as bridge_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v4 as relay_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v5 as launcher_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v5 as campaign_v5,
)


MODULE_NAME = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v5"
)
SCHEMA_VERSION = "etudecas.supplier_full_campaign_relay.v5"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
STATUS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.status.v1"
RESERVATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.reservations.v1"

CORE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_balanced_product_delay_multiseed_refinement_v5"
)
BRIDGE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.build_validated_operating_points_v5"
)
SIDECAR_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v5"
)
CAMPAIGN_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_full_campaign_v5"
)
LAUNCHER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "launch_supplier_operating_point_full_campaign_v5"
)
FINALIZER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "finalize_supplier_operating_point_full_campaign_v5"
)
QUALIFICATION_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_physical_cascade_qualification_v5"
)
DELIVERY_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_v5_final_standalone_delivery"
)

EXPECTED_STATE_IDS = ("op_100", "op_93", "op_80")
EXPECTED_DEVELOPMENT_CASES = 210
EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS = 180
EXPECTED_HOLDOUT_CASES = 90
EXPECTED_CAMPAIGN_ROWS = 3_330
EXPECTED_SHARDS = 18
EXPECTED_CORRIDORS = 18
EXPECTED_UNIQUE_SUPPLIERS = 16
ACCEPTED_REQUIRED_ACTION_STATUSES = frozenset(
    {
        "complete_validated",
        "complete_no_representable_action",
        "not_run_no_qualified_dossier",
    }
)

# These files are reused as immutable implementations.  The V5 relay refuses
# to start if any byte changes; the adapters also enforce the three hashes that
# are directly security/science critical to their invocation.
FROZEN_V4_SHA256 = {
    relay_v4.CAMPAIGN_MODULE: (
        "3bc8795490c6ef9ac1fef25d5dedb22811306ae869477df57e70d483881a5d9d"
    ),
    relay_v4.LAUNCHER_MODULE: (
        "ee79cfc4d61ca98e7030217bdbf52886402e68074b66f7c7380d5e9890838e4c"
    ),
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_full_campaign_v4": (
        "102dc0d8505e184b89e614258ad843a4c02c2e4c0e5a5aea8f060c3e7ae1d14e"
    ),
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_operating_point_campaign_v4_contract": (
        "1612af4f3a82fc886ced62c61e7b511c9564693a9bb965f1b2896b3ffc3ba554"
    ),
    relay_v4.SIDECAR_MODULE: (
        "f6198f12f8d81b8280df781155a31173a90f6344d1f47878aaebbc4321290f3b"
    ),
    relay_v4.AGGREGATOR_MODULE: (
        "959ad4a448755eec8fa188c0135d31c041f34846a0278616066e2b2790caffcc"
    ),
    relay_v4.FINALIZER_MODULE: (
        "0a71a62a3ede37df18024ee9349e6f96e0fbfe80e6dd371f253215bac13e5984"
    ),
    relay_v4.DASHBOARD_MODULE: (
        "7f159384e1609465469ff0263d635600d4dd06d71e7e3df90c8cedf9bebec601"
    ),
    relay_v4.LOT_REPLAY_MODULE: (
        "3491b3868921948b6a5c22f05a3e5cec2eab1a65093ec4eb36bfbbc039337c78"
    ),
    relay_v4.ACTION_REPLAY_MODULE: (
        "80f3e46764a30715b0ccedc683ed4da297cc013bcdc1b05a97de1d9f5d619c20"
    ),
}

FROZEN_V5_SHA256 = {
    CORE_MODULE: ("46bc479466edfe9e1610abbf84aa3f0a6ff039b9066c9a395599494d0b4ed922"),
    SIDECAR_MODULE: (
        "cdb5c110c847e39a189d87b93a2aca08295913b593c039307b7006b1341ded8a"
    ),
    QUALIFICATION_MODULE: (
        "0bba07f024d1d3f29774bea6945be5d61a85153422c3dd6fac3c86b16fb739e9"
    ),
    DELIVERY_MODULE: (
        "19174dc30c28ddfd4143f573414cc76279d1d5b384022b3c2d62d8962fa903be"
    ),
}

V5_PINNED_MODULES = (
    MODULE_NAME,
    CORE_MODULE,
    BRIDGE_MODULE,
    SIDECAR_MODULE,
    CAMPAIGN_MODULE,
    LAUNCHER_MODULE,
    FINALIZER_MODULE,
    QUALIFICATION_MODULE,
    DELIVERY_MODULE,
    *FROZEN_V4_SHA256,
)

FullCampaignRelayError = relay_v4.FullCampaignRelayError
ScientificNoGo = relay_v4.ScientificNoGo
RelayTimeout = relay_v4.RelayTimeout
SidecarLauncher = Callable[[Sequence[str], Path, Path], int]


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return (
        left == right
        or relay_v4._is_relative_to(  # noqa: SLF001
            left, right
        )
        or relay_v4._is_relative_to(right, left)
    )  # noqa: SLF001


def _is_empty_or_absent(path: Path) -> bool:
    return not path.exists() or (path.is_dir() and not any(path.iterdir()))


def _is_exact_int(value: Any, expected: int) -> bool:
    """Accept a JSON integer only when it has the exact expected value."""

    return type(value) is int and value == expected


def _validated_corridor_projection(
    rows: Any, *, source_label: str
) -> list[dict[str, Any]]:
    """Return the frozen trace projection after the V5 18/16 scope checks."""

    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise FullCampaignRelayError(
            f"Le périmètre corridors {source_label} n'est pas une liste exploitable"
        )
    if len(rows) != EXPECTED_CORRIDORS:
        raise FullCampaignRelayError(
            f"Le périmètre {source_label} doit contenir exactement "
            f"{EXPECTED_CORRIDORS} corridors; trouvé: {len(rows)}"
        )
    try:
        projected = bridge_v5.campaign_contract.lane_contract_payload(rows)
    except bridge_v5.campaign_contract.V4CampaignContractError as exc:
        raise FullCampaignRelayError(
            f"Le périmètre corridors {source_label} est invalide: {exc}"
        ) from exc
    supplier_ids = {str(row["supplier_id"]) for row in projected}
    if len(supplier_ids) != EXPECTED_UNIQUE_SUPPLIERS:
        raise FullCampaignRelayError(
            f"Le périmètre {source_label} doit contenir exactement "
            f"{EXPECTED_UNIQUE_SUPPLIERS} supplier_id uniques; "
            f"trouvé: {len(supplier_ids)}"
        )
    return projected


@dataclass(frozen=True)
class V5RelayConfig:
    repo: Path
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
    dashboard_html: Path
    final_html: Path | None
    supervision_dir: Path
    action_replay_root: Path | None = None
    legacy_risk_html: Path | None = None
    legacy_control_html: Path | None = None
    action_replay_mode: str = "required"
    sidecar_watcher_pid: int = 0
    calibration_workers: int = 2
    parallel_shards: int = 2
    workers_per_shard: int = 2
    launcher_poll_seconds: float = 5.0
    relay_poll_seconds: float = 30.0
    watcher_ready_timeout_seconds: float = 300.0
    sidecar_poll_ms: float = 25.0
    sidecar_stability_ms: float = 12.0
    max_wait_hours: float = 240.0

    def resolved(self) -> "V5RelayConfig":
        def optional(path: Path | None) -> Path | None:
            return path.resolve() if path is not None else None

        return V5RelayConfig(
            repo=self.repo.resolve(),
            v4_plan_dir=self.v4_plan_dir.resolve(),
            v4_run_dir=self.v4_run_dir.resolve(),
            v4_sidecar_root=self.v4_sidecar_root.resolve(),
            calibration_plan_dir=self.calibration_plan_dir.resolve(),
            calibration_run_dir=self.calibration_run_dir.resolve(),
            sidecar_dir=self.sidecar_dir.resolve(),
            bridge_json=self.bridge_json.resolve(),
            campaign_root=self.campaign_root.resolve(),
            results_dir=self.results_dir.resolve(),
            lot_replay_root=self.lot_replay_root.resolve(),
            qualification_dir=self.qualification_dir.resolve(),
            dashboard_html=self.dashboard_html.resolve(),
            final_html=optional(self.final_html),
            supervision_dir=self.supervision_dir.resolve(),
            action_replay_root=optional(self.action_replay_root),
            legacy_risk_html=optional(self.legacy_risk_html),
            legacy_control_html=optional(self.legacy_control_html),
            action_replay_mode=self.action_replay_mode,
            sidecar_watcher_pid=self.sidecar_watcher_pid,
            calibration_workers=self.calibration_workers,
            parallel_shards=self.parallel_shards,
            workers_per_shard=self.workers_per_shard,
            launcher_poll_seconds=self.launcher_poll_seconds,
            relay_poll_seconds=self.relay_poll_seconds,
            watcher_ready_timeout_seconds=self.watcher_ready_timeout_seconds,
            sidecar_poll_ms=self.sidecar_poll_ms,
            sidecar_stability_ms=self.sidecar_stability_ms,
            max_wait_hours=self.max_wait_hours,
        )

    def public_mapping(self) -> dict[str, Any]:
        return {
            key: (str(value) if isinstance(value, Path) else value)
            for key, value in self.__dict__.items()
        }

    def validate(self) -> None:
        if not self.repo.is_dir():
            raise FullCampaignRelayError(f"Dépôt absent : {self.repo}")
        for label, path in (
            ("plan V4", self.v4_plan_dir),
            ("run V4", self.v4_run_dir),
        ):
            if not path.is_dir():
                raise FullCampaignRelayError(f"{label} absent : {path}")
        if not _is_empty_or_absent(self.v4_sidecar_root):
            raise FullCampaignRelayError(
                "La cohorte V4 n'est plus inédite : sidecar V4 non vide"
            )
        for label, path in (
            ("plan V5", self.calibration_plan_dir),
            ("run V5", self.calibration_run_dir),
            ("sidecar V5", self.sidecar_dir),
            ("supervision", self.supervision_dir),
        ):
            if path.exists() and not path.is_dir():
                raise FullCampaignRelayError(f"{label} n'est pas un dossier : {path}")
        if self.calibration_workers not in (1, 2):
            raise FullCampaignRelayError("calibration_workers doit valoir 1 ou 2")
        if self.parallel_shards not in (1, 2) or self.workers_per_shard not in (1, 2):
            raise FullCampaignRelayError(
                "Les parallélismes campagne doivent valoir 1 ou 2"
            )
        if not 0.0 <= self.launcher_poll_seconds <= 60.0:
            raise FullCampaignRelayError("launcher_poll_seconds doit être dans [0, 60]")
        if not 0.1 <= self.relay_poll_seconds <= 60.0:
            raise FullCampaignRelayError("relay_poll_seconds doit être dans [0.1, 60]")
        if self.watcher_ready_timeout_seconds <= 0 or self.max_wait_hours <= 0:
            raise FullCampaignRelayError("Les délais doivent être strictement positifs")
        if self.sidecar_poll_ms <= 0 or self.sidecar_stability_ms <= 0:
            raise FullCampaignRelayError(
                "Les temporisations sidecar doivent être positives"
            )
        if self.sidecar_watcher_pid < 0:
            raise FullCampaignRelayError("sidecar_watcher_pid ne peut pas être négatif")
        if self.final_html is None:
            raise FullCampaignRelayError(
                "Le parcours complet V5 exige un HTML final autonome"
            )
        if self.action_replay_root is None:
            raise FullCampaignRelayError(
                "Le parcours complet V5 exige une racine de résultats actions"
            )
        if self.action_replay_mode != "required":
            raise FullCampaignRelayError(
                "Le parcours complet V5 exige explicitement le mode actions required"
            )
        for source in (self.legacy_risk_html, self.legacy_control_html):
            if source is not None and not source.is_file():
                raise FullCampaignRelayError(f"HTML historique absent : {source}")

        protected = (
            self.v4_plan_dir,
            self.v4_run_dir,
            self.v4_sidecar_root,
            *(
                source
                for source in (self.legacy_risk_html, self.legacy_control_html)
                if source is not None
            ),
        )
        output_dirs = tuple(
            path
            for path in (
                self.calibration_plan_dir,
                self.calibration_run_dir,
                self.sidecar_dir,
                self.campaign_root,
                self.results_dir,
                self.lot_replay_root,
                self.qualification_dir,
                self.supervision_dir,
                self.action_replay_root,
            )
            if path is not None
        )
        for output in output_dirs:
            if any(_paths_overlap(output, source) for source in protected):
                raise FullCampaignRelayError(
                    f"Une sortie V5 chevauche une source V4 protégée : {output}"
                )
        for index, left in enumerate(output_dirs):
            for right in output_dirs[index + 1 :]:
                if _paths_overlap(left, right):
                    raise FullCampaignRelayError(
                        "Les racines V5 de preuves et de livraison doivent être séparées"
                    )
        output_files = (
            self.bridge_json,
            self.dashboard_html,
            self.final_html,
            Path(str(self.final_html) + ".manifest.json"),
        )
        for index, left in enumerate(output_files):
            for right in output_files[index + 1 :]:
                if _paths_overlap(left, right):
                    raise FullCampaignRelayError(
                        "Les fichiers de sortie V5 ne doivent pas se chevaucher"
                    )
        for output in output_files:
            if any(_paths_overlap(output, source) for source in protected):
                raise FullCampaignRelayError(
                    f"Un fichier V5 chevauche une source ou sortie V4 : {output}"
                )
            if any(_paths_overlap(output, root) for root in output_dirs):
                raise FullCampaignRelayError(
                    "Un HTML/pont ne doit pas chevaucher un paquet de preuves : "
                    f"{output}"
                )


class FullCampaignRelayV5(relay_v4.FullCampaignRelay):
    """Crash-resumable downstream campaign from immutable V5 calibration."""

    def __init__(
        self,
        config: V5RelayConfig,
        *,
        command_executor: relay_v4.CommandExecutor | None = None,
        sidecar_launcher: SidecarLauncher | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            config,  # type: ignore[arg-type] -- deliberate compatible superset
            command_executor=command_executor,
            sleep=sleep,
            monotonic=monotonic,
        )
        self.config: V5RelayConfig
        self.sidecar_launcher = sidecar_launcher

    def _module_inventory_v5(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for module in V5_PINNED_MODULES:
            if module in seen:
                continue
            seen.add(module)
            path = relay_v4._module_path(self.config.repo, module).resolve()  # noqa: SLF001
            if not path.is_file():
                raise FullCampaignRelayError(f"Module V5 requis absent : {module}")
            digest = relay_v4.sha256_file(path)
            frozen = FROZEN_V4_SHA256.get(module) or FROZEN_V5_SHA256.get(module)
            if frozen is not None and digest != frozen:
                raise FullCampaignRelayError(
                    f"Dépendance figée modifiée : {module} ({digest})"
                )
            rows.append({"module": module, "path": str(path), "sha256": digest})
        return rows

    def _v4_source_inventory(self) -> dict[str, Any]:
        paths = (
            self.config.v4_plan_dir / "refinement_plan.json",
            self.config.v4_run_dir / "run_manifest.json",
            self.config.v4_run_dir / "development_progress.json",
            self.config.v4_run_dir / "development_selection.json",
        )
        rows = []
        for path in paths:
            if not path.is_file():
                raise FullCampaignRelayError(f"Preuve V4 source absente : {path}")
            rows.append(
                {
                    "path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                    "sha256": relay_v4.sha256_file(path),
                }
            )
        return {
            "files": rows,
            "v4_sidecar_root": str(self.config.v4_sidecar_root),
            "v4_sidecar_absent_or_empty": _is_empty_or_absent(
                self.config.v4_sidecar_root
            ),
        }

    def _build_contract(
        self, calibration_handoff: Mapping[str, Any]
    ) -> dict[str, Any]:
        unsigned: dict[str, Any] = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "configuration": self.config.public_mapping(),
            "source_inventory": self._module_inventory_v5(),
            "v4_no_go_source_inventory": self._v4_source_inventory(),
            "calibration_handoff": dict(calibration_handoff),
            "legacy_html_inventory": relay_v4._legacy_html_inventory(self.config),  # noqa: SLF001
            "scientific_contract": {
                "v4_source_status": "development_failed_no_holdout",
                "v4_artifacts_modified": False,
                "calibration_is_read_only_input": True,
                "development_evidence_cases_required": EXPECTED_DEVELOPMENT_CASES,
                "source_new_development_engine_runs_required": (
                    EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS
                ),
                "development_engine_runs_by_relay": 0,
                "v4_development_engine_reruns": 0,
                "holdout_evidence_cases_required": EXPECTED_HOLDOUT_CASES,
                "holdout_engine_runs_by_relay": 0,
                "holdout_retuning": False,
                "campaign_only_after_accepted_holdout": True,
                "campaign_rows": EXPECTED_CAMPAIGN_ROWS,
                "corridor_count": EXPECTED_CORRIDORS,
                "unique_supplier_count": EXPECTED_UNIQUE_SUPPLIERS,
                "physical_qualification_required": True,
                "full_dynamic_cascade_claimed": False,
                "incident_mechanisms": list(relay_v4.EXPECTED_MECHANISMS),
                "quality_incident_included": False,
                "availability_incident_included": False,
                "capacity_incident_included": False,
                "stock_incident_included": False,
                "historical_incident_probability_estimated": False,
                "curve_capture_strictly_lossless": False,
                "curve_failure_invalidates_holdout_or_campaign": False,
                "sidecar_inventory_required_before_relay_start": True,
                "final_standalone_html_required": True,
                "action_replay_mode": "required",
                "no_representable_action_is_scientific_outcome": True,
            },
            "execution_contract": {
                "shell": False,
                "old_results_overwritten": False,
                "resume_from_signed_artifacts": True,
                "one_foreground_child_step_at_a_time": True,
                "scope": "downstream_handoff_only",
                "calibration_commands_constructed": False,
                "calibration_plan_or_run_artifacts_written": False,
                "source_sidecar_inventories_rewritten": False,
                "derived_curve_aggregates_appended": True,
                "relay_owns_sidecar_start": False,
                "launcher_owns_discovery_smoke_and_shards": True,
            },
        }
        return {**unsigned, "contract_signature": relay_v4.stable_sha256(unsigned)}

    def prepare(self) -> None:
        self.config.validate()
        # This must remain before mkdir/contract/status/reservation writes.  A
        # missing, incomplete, rejected, or altered calibration therefore
        # leaves every downstream destination untouched.
        calibration_handoff = self.validate_calibration_handoff()
        self.config.supervision_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        expected = self._build_contract(calibration_handoff)
        if self.contract_path.is_file():
            actual = relay_v4._read_json(self.contract_path)  # noqa: SLF001
            relay_v4._verify_signed_json(  # noqa: SLF001
                actual, "contract_signature", "contrat relais V5"
            )
            if actual != expected:
                raise FullCampaignRelayError(
                    "Le contrat V5 existant diffère; refus de mélanger deux campagnes"
                )
            self.contract = actual
        else:
            allowed = {"logs", ".relay.lock", "detached.json", "detached_relay.log"}
            if any(
                path.name not in allowed
                for path in self.config.supervision_dir.iterdir()
            ):
                raise FullCampaignRelayError(
                    "Dossier de supervision V5 non enregistré et non vide"
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
                payload, "status_signature", "statut relais V5"
            )
            if (
                payload.get("schema_version") != STATUS_SCHEMA_VERSION
                or payload.get("contract_signature") != signature
            ):
                raise FullCampaignRelayError("Statut V5 étranger au contrat")
            self.status = payload
            return
        self.status = {
            "schema_version": STATUS_SCHEMA_VERSION,
            "contract_signature": signature,
            "status": "running",
            "stage": "initialisation",
            "message_fr": (
                "Le relais aval V5 a validé la calibration acceptée sans la modifier."
            ),
            "relay_pid": os.getpid(),
            "started_at_utc": relay_v4._now(),  # noqa: SLF001
            "updated_at_utc": relay_v4._now(),  # noqa: SLF001
            "completed_at_utc": "",
            "active_command": {},
            "steps": {},
            "artifacts": {},
            "scientific_guardrails": self.contract["scientific_contract"],
            "calibration_handoff": self.contract["calibration_handoff"],
        }
        self._write_status()

    def _reserve_outputs(self) -> None:
        unsigned = {
            "schema_version": RESERVATION_SCHEMA_VERSION,
            "contract_signature": self.contract["contract_signature"],
            "paths": {
                "calibration_plan_dir": str(self.config.calibration_plan_dir),
                "calibration_run_dir": str(self.config.calibration_run_dir),
                "sidecar_dir": str(self.config.sidecar_dir),
                "bridge_json": str(self.config.bridge_json),
                "campaign_root": str(self.config.campaign_root),
                "results_dir": str(self.config.results_dir),
                "lot_replay_root": str(self.config.lot_replay_root),
                "qualification_dir": str(self.config.qualification_dir),
                "dashboard_html": str(self.config.dashboard_html),
                "final_html": str(self.config.final_html or ""),
                "action_replay_root": str(self.config.action_replay_root or ""),
            },
        }
        expected = {
            **unsigned,
            "reservation_signature": relay_v4.stable_sha256(unsigned),
        }
        if self.reservations_path.is_file():
            actual = relay_v4._read_json(self.reservations_path)  # noqa: SLF001
            relay_v4._verify_signed_json(  # noqa: SLF001
                actual, "reservation_signature", "réservations V5"
            )
            if actual != expected:
                raise FullCampaignRelayError("Réservations V5 incohérentes")
        else:
            relay_v4._atomic_json(self.reservations_path, expected)  # noqa: SLF001

    def _validated_plan(self) -> Any:
        return refinement_v5.validate_plan(
            self.config.calibration_plan_dir,
            verify_runtime_dependencies=True,
        )

    def _validate_sidecar_snapshots_read_only(
        self,
        *,
        capture: Any,
        contract: Mapping[str, Any],
        base_inventory: Mapping[str, Any],
    ) -> None:
        """Reopen every registered gzip and metadata file without finalizing."""

        contract_signature = capture._verify_signature(  # noqa: SLF001
            contract, "contract_signature", "contrat sidecar V5"
        )
        try:
            cases = tuple(capture.ExpectedCase(**item) for item in contract["cases"])
            csv_specs = tuple(contract["csv_specs"])
            expected_csv_specs = tuple(
                {
                    **asdict(spec),
                    "columns": list(spec.columns),
                    "key_columns": list(spec.key_columns),
                    "numeric_columns": list(spec.numeric_columns),
                }
                for spec in capture.CSV_SPECS
            )
            allowed_filenames = {
                str(spec["filename"]) for spec in csv_specs if isinstance(spec, Mapping)
            }
            specs_by_filename = {
                str(spec["filename"]): spec
                for spec in csv_specs
                if isinstance(spec, Mapping)
            }
            required_filenames = {
                str(spec["filename"])
                for spec in csv_specs
                if isinstance(spec, Mapping) and spec.get("required") is True
            }
            rows = {
                (str(item["candidate_id"]), int(item["seed"])): item
                for item in base_inventory["cases"]
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise FullCampaignRelayError(
                "Cas ou inventaire sidecar V5 illisible"
            ) from exc
        if (
            len(rows) != len(cases)
            or not required_filenames
            or csv_specs != expected_csv_specs
            or len(allowed_filenames) != len(csv_specs)
            or int(contract.get("required_file_count_per_case") or -1)
            != len(required_filenames)
        ):
            raise FullCampaignRelayError(
                "Contrat ou inventaire sidecar V5 dupliqué ou incomplet"
            )

        for case in cases:
            manifest_path = capture._case_manifest_path(  # noqa: SLF001
                self.config.sidecar_dir, case
            ).resolve()
            row = rows.get(case.identity)
            if not isinstance(row, Mapping):
                raise FullCampaignRelayError(
                    f"Cas sidecar absent : {case.candidate_id}/seed_{case.seed}"
                )
            if (
                Path(str(row.get("case_manifest_path") or "")).resolve()
                != manifest_path
                or row.get("case_manifest_sha256")
                != relay_v4.sha256_file(manifest_path)
            ):
                raise FullCampaignRelayError(
                    f"Manifeste sidecar altéré : {manifest_path}"
                )
            manifest = capture._validate_existing_case_manifest(  # noqa: SLF001
                manifest_path,
                contract_signature=contract_signature,
                case=case,
            )
            files = manifest.get("files")
            if not isinstance(files, list) or any(
                not isinstance(file_row, Mapping) for file_row in files
            ):
                raise FullCampaignRelayError(
                    f"Liste de fichiers sidecar invalide : {manifest_path}"
                )
            filenames = [str(file_row.get("filename") or "") for file_row in files]
            if (
                row.get("case_signature") != manifest.get("case_signature")
                or int(row.get("captured_csv_count") or -1)
                != len(files)
                or len(set(filenames)) != len(filenames)
                or not required_filenames.issubset(filenames)
                or not set(filenames).issubset(allowed_filenames)
            ):
                raise FullCampaignRelayError(
                    f"Inventaire et manifeste sidecar divergent : {manifest_path}"
                )
            summary_data, summary_meta = capture._summary_paths(  # noqa: SLF001
                self.config.sidecar_dir, case
            )
            summary_metadata = capture._validate_stored_snapshot(  # noqa: SLF001
                summary_data, summary_meta
            )
            summary_binding = manifest.get("summary")
            if (
                not isinstance(summary_binding, Mapping)
                or Path(str(summary_binding.get("snapshot_path") or "")).resolve()
                != summary_data.resolve()
                or summary_metadata.get("snapshot_gzip_sha256")
                != summary_binding.get("snapshot_gzip_sha256")
                or summary_metadata.get("source_sha256")
                != summary_binding.get("source_sha256")
            ):
                raise FullCampaignRelayError(
                    f"Résumé et manifeste sidecar divergent : {summary_data}"
                )
            for file_row in files:
                data_path, meta_path = capture._snapshot_paths(  # noqa: SLF001
                    self.config.sidecar_dir,
                    case,
                    str(file_row.get("filename") or ""),
                )
                metadata = capture._validate_stored_snapshot(  # noqa: SLF001
                    data_path, meta_path
                )
                spec = specs_by_filename[str(file_row.get("filename") or "")]
                if (
                    Path(str(file_row.get("snapshot_path") or "")).resolve()
                    != data_path.resolve()
                    or file_row.get("required") is not spec.get("required")
                    or metadata.get("snapshot_gzip_sha256")
                    != file_row.get("snapshot_gzip_sha256")
                    or metadata.get("source_sha256") != file_row.get("source_sha256")
                ):
                    raise FullCampaignRelayError(
                        f"Instantané et manifeste sidecar divergent : {data_path}"
                    )

    def validate_finalized_sidecar_handoff(self) -> dict[str, Any]:
        """Validate the completed, source-bound V5 curve inventory read-only."""

        if not self._sidecar_inventory_ready():
            raise FullCampaignRelayError(
                "Le relais aval V5 exige avant lancement le sidecar finalisé "
                "et son inventaire complet de 90 cas"
            )
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_holdout_curve_sidecar_v5 as sidecar_v5,
        )

        contract_path = self.config.sidecar_dir / "capture_contract.json"
        ready_path = self.config.sidecar_dir / "watcher_ready.json"
        base_path = self.config.sidecar_dir / "capture_inventory.json"
        v5_path = self.config.sidecar_dir / "capture_inventory_v5.json"
        for path in (contract_path, ready_path, base_path, v5_path):
            if not path.is_file():
                raise FullCampaignRelayError(
                    f"Preuve sidecar V5 finalisée absente : {path}"
                )

        contract = sidecar_v5.validate_contract(
            relay_v4._read_json(contract_path)  # noqa: SLF001
        )
        ready = sidecar_v5.validate_ready(
            ready_path,
            expected_output_dir=self.config.sidecar_dir,
        )
        base = relay_v4._read_json(base_path)  # noqa: SLF001
        v5 = relay_v4._read_json(v5_path)  # noqa: SLF001
        relay_v4._verify_signed_json(  # noqa: SLF001
            base, "inventory_signature", "inventaire sidecar de base V5"
        )
        relay_v4._verify_signed_json(  # noqa: SLF001
            v5, "inventory_signature", "inventaire sidecar V5"
        )

        plan_path = self.config.calibration_plan_dir / "refinement_plan.json"
        run_manifest_path = self.config.calibration_run_dir / "run_manifest.json"
        plan_binding = contract.get("plan") or {}
        run_binding = contract.get("run") or {}
        expected_cases = [
            asdict(case)
            for case in sidecar_v5.load_official_cases(
                self.config.calibration_plan_dir,
                self.config.calibration_run_dir,
            )
        ]
        base_cases = base.get("cases")
        if not isinstance(base_cases, list) or any(
            not isinstance(row, Mapping) for row in base_cases
        ):
            raise FullCampaignRelayError("Inventaire sidecar de base sans liste de cas")
        expected_identities = sorted(
            (
                str(case["target_group"]),
                str(case["candidate_key"]),
                str(case["candidate_id"]),
                int(case["seed"]),
            )
            for case in expected_cases
        )
        try:
            captured_identities = sorted(
                (
                    str(case["target_group"]),
                    str(case["candidate_key"]),
                    str(case["candidate_id"]),
                    int(case["seed"]),
                )
                for case in base_cases
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FullCampaignRelayError(
                "Identités de cas invalides dans l'inventaire sidecar"
            ) from exc

        case_manifests_valid = True
        for row in base_cases:
            manifest_path = Path(str(row.get("case_manifest_path") or "")).resolve()
            if (
                not manifest_path.is_file()
                or not relay_v4._is_relative_to(  # noqa: SLF001
                    manifest_path, self.config.sidecar_dir
                )
                or row.get("case_manifest_sha256")
                != relay_v4.sha256_file(manifest_path)
            ):
                case_manifests_valid = False
                break

        if (
            Path(str(plan_binding.get("directory") or "")).resolve()
            != self.config.calibration_plan_dir
            or Path(str(plan_binding.get("manifest_path") or "")).resolve()
            != plan_path.resolve()
            or plan_binding.get("manifest_sha256") != relay_v4.sha256_file(plan_path)
            or Path(str(run_binding.get("directory") or "")).resolve()
            != self.config.calibration_run_dir
            or Path(str(run_binding.get("manifest_path") or "")).resolve()
            != run_manifest_path.resolve()
            or run_binding.get("manifest_sha256")
            != relay_v4.sha256_file(run_manifest_path)
            or Path(str(contract.get("output_directory") or "")).resolve()
            != self.config.sidecar_dir
            or contract.get("cases") != expected_cases
            or ready.get("contract_signature") != contract.get("contract_signature")
            or base.get("contract_signature") != contract.get("contract_signature")
            or captured_identities != expected_identities
            or not case_manifests_valid
            or v5.get("contract_signature") != contract.get("contract_signature")
            or v5.get("base_inventory_signature") != base.get("inventory_signature")
            or v5.get("base_inventory_sha256") != relay_v4.sha256_file(base_path)
        ):
            raise FullCampaignRelayError(
                "Le sidecar V5 finalisé n'est pas lié exactement au plan/run de calibration"
            )
        try:
            self._validate_sidecar_snapshots_read_only(
                capture=sidecar_v5.capture_v4,
                contract=contract,
                base_inventory=base,
            )
        except FullCampaignRelayError:
            raise
        except Exception as exc:
            raise FullCampaignRelayError(
                "Un instantané du sidecar V5 finalisé est absent ou altéré"
            ) from exc
        return {
            "status": "complete",
            "case_count": EXPECTED_HOLDOUT_CASES,
            "contract": str(contract_path),
            "contract_sha256": relay_v4.sha256_file(contract_path),
            "contract_signature": contract["contract_signature"],
            "watcher_ready": str(ready_path),
            "watcher_ready_sha256": relay_v4.sha256_file(ready_path),
            "watcher_ready_signature": ready["ready_signature"],
            "base_inventory": str(base_path),
            "base_inventory_sha256": relay_v4.sha256_file(base_path),
            "base_inventory_signature": base["inventory_signature"],
            "v5_inventory": str(v5_path),
            "v5_inventory_sha256": relay_v4.sha256_file(v5_path),
            "v5_inventory_signature": v5["inventory_signature"],
        }

    def validate_calibration_handoff(self) -> dict[str, Any]:
        """Reopen all upstream V5 proofs without creating or rewriting any of them."""

        if not self._plan_ready():
            raise FullCampaignRelayError("Plan V5 finalisé absent avant le relais aval")
        if not self._stage_complete("development", EXPECTED_DEVELOPMENT_CASES):
            raise FullCampaignRelayError(
                "Le relais aval exige les 210 preuves de développement V5 complètes"
            )
        selection = self._development_selection()
        if selection is None:
            raise FullCampaignRelayError(
                "Sélection de développement V5 finalisée absente"
            )
        if selection.get("status") == "development_failed_no_holdout":
            raise ScientificNoGo(
                "La calibration V5 s'est arrêtée après le développement; "
                "le relais aval ne produit aucune sortie"
            )
        if (
            selection.get("status")
            != "development_selected_pending_fresh_holdout"
            or set(selection.get("selected_candidate_keys") or {})
            != set(EXPECTED_STATE_IDS)
            or selection.get("holdout_cases_read") != 0
        ):
            raise FullCampaignRelayError(
                "La sélection V5 ne respecte pas le contrat pré-holdout figé"
            )
        if not self._stage_complete("holdout", EXPECTED_HOLDOUT_CASES):
            raise FullCampaignRelayError(
                "Le relais aval exige les 90 preuves de holdout V5 complètes"
            )
        holdout = self._holdout_result()
        if holdout is None:
            raise FullCampaignRelayError("Décision holdout V5 finalisée absente")
        if holdout.get("accepted") is not True:
            raise ScientificNoGo(
                "Le holdout V5 est rejeté; le relais aval ne produit aucune sortie"
            )
        if (
            holdout.get("status") != bridge_v5.ACCEPTED_HOLDOUT_STATUS
            or holdout.get("publishable") is not True
            or holdout.get("retuning_after_holdout") is not False
            or int(holdout.get("holdout_evidence_case_count") or -1)
            != EXPECTED_HOLDOUT_CASES
            or set(holdout.get("state_summaries") or {}) != set(EXPECTED_STATE_IDS)
        ):
            raise FullCampaignRelayError(
                "Le holdout V5 n'est pas une acceptation publiable de 90 cas sans retuning"
            )

        sidecar = self.validate_finalized_sidecar_handoff()
        plan_path = self.config.calibration_plan_dir / "refinement_plan.json"
        development_path = self.config.calibration_run_dir / "development_progress.json"
        selection_path = self.config.calibration_run_dir / "development_selection.json"
        holdout_progress_path = self.config.calibration_run_dir / "holdout_progress.json"
        holdout_result_path = self.config.calibration_run_dir / "holdout_result.json"
        return {
            "status": "accepted_read_only_handoff",
            "plan": str(plan_path),
            "plan_sha256": relay_v4.sha256_file(plan_path),
            "development_progress": str(development_path),
            "development_progress_sha256": relay_v4.sha256_file(development_path),
            "development_evidence_case_count": EXPECTED_DEVELOPMENT_CASES,
            "source_new_development_engine_run_count": (
                EXPECTED_NEW_DEVELOPMENT_ENGINE_RUNS
            ),
            "development_selection": str(selection_path),
            "development_selection_sha256": relay_v4.sha256_file(selection_path),
            "development_selection_signature": selection["selection_signature"],
            "holdout_progress": str(holdout_progress_path),
            "holdout_progress_sha256": relay_v4.sha256_file(holdout_progress_path),
            "holdout_evidence_case_count": EXPECTED_HOLDOUT_CASES,
            "holdout_result": str(holdout_result_path),
            "holdout_result_sha256": relay_v4.sha256_file(holdout_result_path),
            "holdout_signature": holdout["holdout_signature"],
            "holdout_status": holdout["status"],
            "holdout_accepted": True,
            "retuning_after_holdout": False,
            "sidecar": sidecar,
            "relay_development_engine_runs": 0,
            "relay_holdout_engine_runs": 0,
            "calibration_plan_or_run_artifacts_written": False,
            "source_sidecar_inventories_rewritten": False,
        }

    def validate_downstream_corridor_preflight(self) -> dict[str, Any]:
        """Bind the V5 plan to the real 18-corridor / 16-supplier reference."""

        plan = self._validated_plan()
        source_manifest_path = Path(
            str(plan.manifest["source"]["campaign_manifest"]["path"])
        ).resolve()
        if not source_manifest_path.is_file():
            raise FullCampaignRelayError(
                f"Manifeste source des corridors absent: {source_manifest_path}"
            )
        source_manifest = relay_v4._read_json(source_manifest_path)  # noqa: SLF001
        manifest_projection = _validated_corridor_projection(
            source_manifest.get("lanes"), source_label="du plan V5"
        )

        lane_reference_raw = str(source_manifest.get("lane_reference_source") or "")
        if not lane_reference_raw:
            raise FullCampaignRelayError(
                "Le manifeste source ne référence aucun fichier réel de corridors"
            )
        lane_reference = Path(lane_reference_raw).resolve()
        campaign_v5.validate_frozen_implementation()
        expected_reference = (
            campaign_v5.implementation_v4.DEFAULT_LANE_REFERENCE.resolve()
        )
        if lane_reference != expected_reference:
            raise FullCampaignRelayError(
                "Le plan V5 et le planificateur aval ne ciblent pas le même "
                f"fichier corridors: {lane_reference} != {expected_reference}"
            )
        if not lane_reference.is_file():
            raise FullCampaignRelayError(
                f"Fichier réel des corridors absent: {lane_reference}"
            )
        actual_reference_sha256 = relay_v4.sha256_file(lane_reference)
        if (
            str(source_manifest.get("lane_reference_source_sha256") or "")
            != actual_reference_sha256
        ):
            raise FullCampaignRelayError(
                "Le fichier réel des corridors ne correspond plus au manifeste source"
            )
        try:
            reference_lanes = campaign_v5.implementation_v4.load_lanes(lane_reference)
        except (OSError, ValueError) as exc:
            raise FullCampaignRelayError(
                f"Le fichier réel des corridors est invalide: {exc}"
            ) from exc
        reference_projection = _validated_corridor_projection(
            [asdict(lane) for lane in reference_lanes],
            source_label="du fichier réel",
        )
        if reference_projection != manifest_projection:
            raise FullCampaignRelayError(
                "Les corridors du plan V5 diffèrent du fichier réel utilisé en aval"
            )

        unsigned = {
            "status": "validated",
            "plan_signature": plan.manifest["plan_signature"],
            "source_manifest": str(source_manifest_path),
            "source_manifest_sha256": relay_v4.sha256_file(source_manifest_path),
            "lane_reference": str(lane_reference),
            "lane_reference_sha256": actual_reference_sha256,
            "corridor_count": len(reference_projection),
            "unique_supplier_count": len(
                {str(row["supplier_id"]) for row in reference_projection}
            ),
            "lane_contract_sha256": (
                bridge_v5.campaign_contract.lane_contract_sha256(reference_projection)
            ),
        }
        result = {
            **unsigned,
            "preflight_signature": relay_v4.stable_sha256(unsigned),
        }
        self.status["downstream_corridor_preflight"] = result
        self._write_status()
        return result

    def _campaign_plan_ready(self) -> bool:
        if not super()._campaign_plan_ready():
            return False
        preflight = self.validate_downstream_corridor_preflight()
        manifest_path = self.config.campaign_root / "campaign_manifest.json"
        manifest = relay_v4._read_json(manifest_path)  # noqa: SLF001
        campaign_projection = _validated_corridor_projection(
            manifest.get("lanes"), source_label="du manifeste de campagne V5"
        )
        expected_sha = str(preflight["lane_contract_sha256"])
        actual_sha = bridge_v5.campaign_contract.lane_contract_sha256(
            campaign_projection
        )
        if actual_sha != expected_sha:
            raise FullCampaignRelayError(
                "Le manifeste de campagne V5 diffère du périmètre corridors prévalidé"
            )
        return True

    def _plan_ready(self) -> bool:
        path = self.config.calibration_plan_dir / "refinement_plan.json"
        if not path.is_file():
            if self.config.calibration_plan_dir.exists() and any(
                self.config.calibration_plan_dir.iterdir()
            ):
                raise FullCampaignRelayError("Plan V5 partiel ou étranger")
            return False
        plan = self._validated_plan()
        source = plan.manifest.get("v4_no_go_source") or {}
        if (
            Path(str(source.get("plan_dir") or "")).resolve() != self.config.v4_plan_dir
            or Path(str(source.get("run_dir") or "")).resolve()
            != self.config.v4_run_dir
            or Path(
                str(
                    (source.get("holdout_non_use_audit") or {}).get("sidecar_root")
                    or ""
                )
            ).resolve()
            != self.config.v4_sidecar_root
        ):
            raise FullCampaignRelayError("Le plan V5 référence une autre source V4")
        return True

    def prepare_v5_plan(self) -> None:
        raise FullCampaignRelayError(
            "Relais V5 aval uniquement : préparation de calibration interdite"
        )
        self.run_step(
            step="preparation_plan_v5",
            command=self._python_module(
                CORE_MODULE,
                "plan",
                "--output-dir",
                str(self.config.calibration_plan_dir),
                "--v4-plan-dir",
                str(self.config.v4_plan_dir),
                "--v4-run-dir",
                str(self.config.v4_run_dir),
                "--v4-sidecar-root",
                str(self.config.v4_sidecar_root),
            ),
            completion_check=self._plan_ready,
            message_fr="Création additive du plan V5; aucune preuve V4 n'est modifiée.",
        )
        self.run_step(
            step="validation_plan_v5",
            command=self._python_module(
                CORE_MODULE,
                "validate",
                "--plan-dir",
                str(self.config.calibration_plan_dir),
            ),
            completion_check=self._plan_ready,
            message_fr="Relecture du plan V5 et de sa source V4 signée.",
            run_even_if_complete=True,
        )
        self._record_artifact(
            "v5_refinement_plan",
            self.config.calibration_plan_dir / "refinement_plan.json",
        )

    def _progress_view(self, stage: str) -> dict[str, Any]:
        path = self.config.calibration_run_dir / f"{stage}_progress.json"
        if not path.is_file():
            return {}
        try:
            payload = relay_v4._read_json(path)  # noqa: SLF001
        except Exception:
            return {}
        return {
            "v5_stage": stage,
            "completed_cases": payload.get("completed_case_count"),
            "expected_cases": payload.get("expected_case_count"),
            "producer_status": payload.get("status"),
        }

    def _stage_complete(self, stage: str, expected_count: int) -> bool:
        progress_path = self.config.calibration_run_dir / f"{stage}_progress.json"
        if not progress_path.is_file():
            if not self.config.calibration_run_dir.exists():
                return False
            unexpected = [
                path
                for path in self.config.calibration_run_dir.iterdir()
                if path.name
                not in {
                    "run_manifest.json",
                    "evidence",
                    "shipment_traces",
                    "engine_attempts",
                    "development_progress.json",
                    "development_selection.json",
                    "holdout_progress.json",
                    "holdout_result.json",
                }
            ]
            if unexpected:
                raise FullCampaignRelayError(
                    f"Run V5 sans progression {stage} mais avec artefacts inattendus"
                )
            return False
        payload = relay_v4._read_json(progress_path)  # noqa: SLF001
        relay_v4._verify_signed_json(  # noqa: SLF001
            payload, "progress_signature", f"progression V5 {stage}"
        )
        completed = payload.get("completed_case_count")
        if (
            payload.get("schema_version")
            != f"{refinement_v5.SCHEMA_VERSION}.{stage}.progress"
            or payload.get("stage") != stage
            or type(completed) is not int
            or not 0 <= completed <= expected_count
            or payload.get("expected_case_count") != expected_count
            or payload.get("execution_mode") != refinement_v5.OFFICIAL_EXECUTION_MODE
            or payload.get("publishable") is not True
            or payload.get("error") not in {"", None}
        ):
            raise FullCampaignRelayError(f"Progression V5 {stage} incohérente")
        if payload.get("status") != "complete" or completed != expected_count:
            return False
        plan = self._validated_plan()
        evidence = refinement_v5._load_stage_evidence(  # noqa: SLF001
            plan, self.config.calibration_run_dir, stage
        )
        if len(evidence) != expected_count:
            raise FullCampaignRelayError(f"Matrice V5 {stage} incomplète")
        return True

    def run_development(self) -> None:
        raise FullCampaignRelayError(
            "Relais V5 aval uniquement : développement de calibration interdit"
        )
        self.run_step(
            step="developpement_v5_210_preuves",
            command=self._python_module(
                CORE_MODULE,
                "run",
                "--plan-dir",
                str(self.config.calibration_plan_dir),
                "--run-dir",
                str(self.config.calibration_run_dir),
                "--stage",
                "development",
                "--workers",
                str(self.config.calibration_workers),
            ),
            completion_check=lambda: self._stage_complete(
                "development", EXPECTED_DEVELOPMENT_CASES
            ),
            message_fr=(
                "Évaluation des six réglages pré-enregistrés sur 30 graines; "
                "les 30 preuves de référence V4 sont seulement relues."
            ),
            progress_reader=lambda: self._progress_view("development"),
        )
        self._record_artifact(
            "v5_development_progress",
            self.config.calibration_run_dir / "development_progress.json",
        )

    def _development_selection(self) -> dict[str, Any] | None:
        path = self.config.calibration_run_dir / "development_selection.json"
        if not path.is_file():
            return None
        plan = self._validated_plan()
        evidence = refinement_v5._load_stage_evidence(  # noqa: SLF001
            plan, self.config.calibration_run_dir, "development"
        )
        mode = refinement_v5._registered_execution_mode(  # noqa: SLF001
            plan, self.config.calibration_run_dir
        )
        expected = refinement_v5._build_development_selection(  # noqa: SLF001
            plan, evidence, execution_mode=mode
        )
        actual = relay_v4._read_json(path)  # noqa: SLF001
        relay_v4._verify_signed_json(  # noqa: SLF001
            actual, "selection_signature", "sélection développement V5"
        )
        if actual != expected or actual.get("publishable") is not True:
            raise FullCampaignRelayError("Sélection V5 non reproductible")
        return actual

    def finalize_development(self) -> dict[str, Any]:
        raise FullCampaignRelayError(
            "Relais V5 aval uniquement : finalisation du développement interdite"
        )
        self.run_step(
            step="selection_developpement_v5",
            command=self._python_module(
                CORE_MODULE,
                "finalize",
                "--plan-dir",
                str(self.config.calibration_plan_dir),
                "--run-dir",
                str(self.config.calibration_run_dir),
                "--stage",
                "development",
            ),
            completion_check=lambda: self._development_selection() is not None,
            message_fr="Application des critères figés avant toute lecture du holdout.",
            run_even_if_complete=True,
        )
        selection = self._development_selection()
        if selection is None:  # pragma: no cover - guarded by run_step
            raise FullCampaignRelayError("Sélection développement V5 absente")
        self._record_artifact(
            "v5_development_selection",
            self.config.calibration_run_dir / "development_selection.json",
        )
        if selection.get("status") == "development_failed_no_holdout":
            raise ScientificNoGo(
                "Aucun triplet V5 n'a satisfait les critères de développement; "
                "watcher, holdout et campagne incidents non lancés"
            )
        if (
            selection.get("status") != "development_selected_pending_fresh_holdout"
            or set(selection.get("selected_candidate_keys") or {})
            != set(EXPECTED_STATE_IDS)
            or selection.get("holdout_cases_read") != 0
        ):
            raise FullCampaignRelayError("Sélection V5 n'autorise pas le holdout")
        return selection

    def _sidecar_command(self) -> list[str]:
        return self._python_module(
            SIDECAR_MODULE,
            "watch",
            "--plan-dir",
            str(self.config.calibration_plan_dir),
            "--run-dir",
            str(self.config.calibration_run_dir),
            "--output-dir",
            str(self.config.sidecar_dir),
            "--poll-ms",
            str(self.config.sidecar_poll_ms),
            "--stability-ms",
            str(self.config.sidecar_stability_ms),
            "--timeout-seconds",
            str(self.config.max_wait_hours * 3600.0),
        )

    def _sidecar_inventory_ready(self) -> bool:
        """Require both the base inventory and its signed V5 binding."""

        if not super()._sidecar_inventory_ready():
            return False
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_holdout_curve_sidecar_v5 as sidecar_v5,
        )

        v5_path = self.config.sidecar_dir / "capture_inventory_v5.json"
        if not v5_path.is_file():
            return False
        contract_path = self.config.sidecar_dir / "capture_contract.json"
        base_path = self.config.sidecar_dir / "capture_inventory.json"
        if not contract_path.is_file() or not base_path.is_file():
            return False
        contract = sidecar_v5.validate_contract(
            relay_v4._read_json(contract_path)  # noqa: SLF001
        )
        base = relay_v4._read_json(base_path)  # noqa: SLF001
        payload = relay_v4._read_json(v5_path)  # noqa: SLF001
        relay_v4._verify_signed_json(  # noqa: SLF001
            payload, "inventory_signature", "inventaire sidecar V5"
        )
        if (
            payload.get("schema_version") != sidecar_v5.INVENTORY_SCHEMA_VERSION
            or payload.get("status") != "complete"
            or int(payload.get("case_count") or -1) != EXPECTED_HOLDOUT_CASES
            or payload.get("contract_signature") != contract.get("contract_signature")
            or Path(str(payload.get("base_inventory_path") or "")).resolve()
            != base_path.resolve()
            or payload.get("base_inventory_sha256")
            != relay_v4.sha256_file(base_path)
            or payload.get("base_inventory_signature")
            != base.get("inventory_signature")
        ):
            raise FullCampaignRelayError("Inventaire sidecar V5 final incohérent")
        return True

    def validate_and_aggregate_curves(self) -> None:
        """Finalize through the V5 wrapper, then reuse the compatible aggregator."""

        self.run_step(
            step="validation_sidecar_v5",
            command=self._python_module(
                SIDECAR_MODULE,
                "finalize",
                "--output-dir",
                str(self.config.sidecar_dir),
            ),
            completion_check=self._sidecar_inventory_ready,
            message_fr="Revalidation des deux inventaires des 90 courbes V5.",
            run_even_if_complete=True,
        )
        aggregate_manifest = (
            self.config.sidecar_dir
            / "curve_aggregates_v1"
            / "aggregate_manifest.json"
        )

        def aggregate_ready() -> bool:
            if not aggregate_manifest.is_file():
                return False
            payload = relay_v4._read_json(aggregate_manifest)  # noqa: SLF001
            relay_v4._verify_signed_json(  # noqa: SLF001
                payload, "manifest_signature", "agrégats de courbes V5"
            )
            return (
                payload.get("status") == "complete"
                and int(payload.get("case_count") or -1) == EXPECTED_HOLDOUT_CASES
                and int(payload.get("state_count") or -1) == len(EXPECTED_STATE_IDS)
                and len(payload.get("files") or []) == 4
            )

        self.run_step(
            step="agregation_courbes_nominales_v5",
            command=self._python_module(
                relay_v4.AGGREGATOR_MODULE,
                "aggregate",
                "--output-dir",
                str(self.config.sidecar_dir),
            ),
            completion_check=aggregate_ready,
            message_fr="Calcul des courbes descriptives compactes par état simulé.",
        )
        self.run_step(
            step="validation_agregats_courbes_v5",
            command=self._python_module(
                relay_v4.AGGREGATOR_MODULE,
                "validate",
                "--output-dir",
                str(self.config.sidecar_dir),
            ),
            completion_check=aggregate_ready,
            message_fr="Contrôle final des courbes compactes et de leur inventaire.",
            run_even_if_complete=True,
        )
        self._record_artifact("nominal_curve_aggregates", aggregate_manifest)

    @staticmethod
    def _default_sidecar_launcher(
        command: Sequence[str], cwd: Path, log_path: Path
    ) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as stream:
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
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NO_WINDOW
                )
            else:  # pragma: no cover - deployment is Windows
                kwargs["start_new_session"] = True
            process = subprocess.Popen(list(command), **kwargs)
        return int(process.pid)

    def _validate_sidecar_ack(
        self, *, expected_pid: int | None, require_running: bool
    ) -> dict[str, Any]:
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_holdout_curve_sidecar_v5 as sidecar_v5,
        )

        ready_path = self.config.sidecar_dir / "watcher_ready.json"
        contract_path = self.config.sidecar_dir / "capture_contract.json"
        if not ready_path.is_file() or not contract_path.is_file():
            raise FileNotFoundError("Accusé ou contrat sidecar V5 absent")
        ready = sidecar_v5.validate_ready(
            ready_path,
            expected_output_dir=self.config.sidecar_dir,
            expected_watcher_pid=expected_pid,
        )
        contract = sidecar_v5.validate_contract(
            relay_v4._read_json(contract_path)  # noqa: SLF001
        )
        pid = int(ready.get("watcher_pid") or 0)
        if (
            contract.get("schema_version") != sidecar_v5.CONTRACT_SCHEMA_VERSION
            or contract.get("producer_protocol") != refinement_v5.SCHEMA_VERSION
            or int(contract.get("expected_case_count") or -1) != EXPECTED_HOLDOUT_CASES
            or ready.get("contract_signature") != contract.get("contract_signature")
            or pid <= 0
        ):
            raise FullCampaignRelayError("Accusé/contrat sidecar V5 incohérent")
        if require_running and not relay_v4._process_running(pid):  # noqa: SLF001
            raise FullCampaignRelayError("Watcher V5 arrêté avant le holdout")
        return ready

    def _historical_sidecar_ack(self) -> dict[str, Any] | None:
        holdout_progress = self.config.calibration_run_dir / "holdout_progress.json"
        if not holdout_progress.is_file():
            return None
        try:
            ready = self._validate_sidecar_ack(expected_pid=None, require_running=False)
        except FileNotFoundError as exc:
            raise FullCampaignRelayError(
                "Un holdout V5 existe sans preuve d'un watcher accusé avant son départ"
            ) from exc
        progress = relay_v4._read_json(holdout_progress)  # noqa: SLF001
        relay_v4._verify_signed_json(  # noqa: SLF001
            progress, "progress_signature", "progression holdout V5"
        )
        completed = progress.get("completed_case_count")
        if (
            progress.get("schema_version")
            != f"{refinement_v5.SCHEMA_VERSION}.holdout.progress"
            or progress.get("stage") != "holdout"
            or progress.get("status") not in {"running", "failed", "complete"}
            or type(completed) is not int
            or not 0 <= completed <= EXPECTED_HOLDOUT_CASES
            or progress.get("expected_case_count") != EXPECTED_HOLDOUT_CASES
            or progress.get("execution_mode") != refinement_v5.OFFICIAL_EXECUTION_MODE
            or progress.get("publishable") is not True
        ):
            raise FullCampaignRelayError(
                "Progression holdout V5 historique incohérente"
            )
        if str(ready.get("created_at_utc") or "") > str(
            progress.get("updated_at_utc") or ""
        ):
            raise FullCampaignRelayError(
                "L'accusé watcher est postérieur à la première preuve du holdout"
            )
        return ready

    def ensure_sidecar_watcher(self) -> int:
        raise FullCampaignRelayError(
            "Relais V5 aval uniquement : démarrage du watcher de calibration interdit"
        )
        historical = self._historical_sidecar_ack()
        if historical is not None:
            pid = int(historical["watcher_pid"])
            running = relay_v4._process_running(pid)  # noqa: SLF001
            progress = relay_v4._read_json(  # noqa: SLF001
                self.config.calibration_run_dir / "holdout_progress.json"
            )
            if running or progress.get("status") == "complete":
                self.status["sidecar_watcher"] = {
                    "status": (
                        "watching"
                        if running
                        else "acknowledged_before_holdout_not_running_now"
                    ),
                    "pid": pid,
                    "owned_by_relay": bool(
                        (self.status.get("sidecar_watcher") or {}).get("owned_by_relay")
                    ),
                    "ready_signature": historical["ready_signature"],
                    "holdout_start_authorized": True,
                }
                self._write_status()
                return pid

        ready_path = self.config.sidecar_dir / "watcher_ready.json"
        candidates: list[int] = []
        if self.config.sidecar_watcher_pid:
            candidates.append(self.config.sidecar_watcher_pid)
        recorded = self.status.get("sidecar_watcher") or {}
        if isinstance(recorded, Mapping) and int(recorded.get("pid") or 0) > 0:
            candidates.append(int(recorded["pid"]))
        if ready_path.is_file():
            try:
                existing_ready = self._validate_sidecar_ack(
                    expected_pid=None, require_running=False
                )
                candidates.append(int(existing_ready["watcher_pid"]))
            except Exception:
                # The authoritative validator below will expose the exact error;
                # do not silently trust or delete a stale acknowledgement.
                pass
        pid = next(
            (
                candidate
                for candidate in dict.fromkeys(candidates)
                if relay_v4._process_running(candidate)  # noqa: SLF001
            ),
            0,
        )
        owned = (
            bool(recorded.get("owned_by_relay"))
            if isinstance(recorded, Mapping)
            else False
        )
        command = self._sidecar_command()
        log_path = self.log_dir / "watcher_courbes_v5.log"
        if pid <= 0:
            launcher = self.sidecar_launcher or self._default_sidecar_launcher
            pid = int(launcher(command, self.config.repo, log_path))
            if pid <= 0:
                raise FullCampaignRelayError(
                    "Le lancement du watcher V5 n'a pas fourni de PID"
                )
            owned = True
        self.status["sidecar_watcher"] = {
            "status": "starting",
            "pid": pid,
            "owned_by_relay": owned,
            "command": command,
            "command_sha256": relay_v4.stable_sha256(command),
            "log_path": str(log_path),
            "holdout_start_authorized": False,
        }
        self.update_status(
            "attente_accuse_watcher_v5",
            "Le watcher doit enregistrer ses 90 cas et rester vivant avant le holdout.",
        )
        started = self.monotonic()
        last_error = ""
        while True:
            try:
                ready = self._validate_sidecar_ack(
                    expected_pid=pid, require_running=True
                )
                break
            except Exception as exc:
                # A live watcher can atomically replace an acknowledgement from
                # an earlier crashed attempt.  Keep waiting, but never accept
                # an invalid document.
                last_error = f"{type(exc).__name__}: {exc}"
            if not relay_v4._process_running(pid):  # noqa: SLF001
                raise FullCampaignRelayError(
                    f"Watcher V5 arrêté avant accusé; voir {log_path} ({last_error})"
                )
            elapsed = self.monotonic() - started
            if elapsed > self.config.watcher_ready_timeout_seconds:
                raise RelayTimeout(
                    f"Délai dépassé pour l'accusé watcher V5 (PID {pid})"
                )
            self.update_status(
                "attente_accuse_watcher_v5",
                "Le watcher prépare le contrat de capture avant le holdout.",
                progress={"watcher_pid": pid, "elapsed_seconds": round(elapsed, 1)},
            )
            self.sleep(min(1.0, self.config.relay_poll_seconds))
        self.status["sidecar_watcher"] = {
            "status": "ready_before_holdout",
            "pid": pid,
            "owned_by_relay": owned,
            "process_running": True,
            "ready_signature": ready["ready_signature"],
            "contract_signature": ready["contract_signature"],
            "holdout_start_authorized": True,
            "log_path": str(log_path),
        }
        self._write_status()
        self._record_artifact(
            "v5_sidecar_contract", self.config.sidecar_dir / "capture_contract.json"
        )
        self._record_artifact("v5_sidecar_ready", ready_path)
        return pid

    def run_holdout(self, watcher_pid: int) -> None:
        raise FullCampaignRelayError(
            "Relais V5 aval uniquement : exécution du holdout interdite"
        )
        progress_path = self.config.calibration_run_dir / "holdout_progress.json"
        progress = (
            relay_v4._read_json(progress_path)  # noqa: SLF001
            if progress_path.is_file()
            else {}
        )
        if progress.get("status") != "complete":
            self._validate_sidecar_ack(expected_pid=watcher_pid, require_running=True)
        self.run_step(
            step="holdout_v5_90_preuves",
            command=self._python_module(
                CORE_MODULE,
                "run",
                "--plan-dir",
                str(self.config.calibration_plan_dir),
                "--run-dir",
                str(self.config.calibration_run_dir),
                "--stage",
                "holdout",
                "--workers",
                str(self.config.calibration_workers),
            ),
            completion_check=lambda: self._stage_complete(
                "holdout", EXPECTED_HOLDOUT_CASES
            ),
            message_fr="Exécution unique des trois états sur les 30 graines restées inédites.",
            progress_reader=lambda: {
                **self._progress_view("holdout"),
                "curve_watcher_pid": watcher_pid,
                "curve_watcher_running": relay_v4._process_running(watcher_pid),  # noqa: SLF001
            },
        )
        self._record_artifact(
            "v5_holdout_progress",
            self.config.calibration_run_dir / "holdout_progress.json",
        )

    def _holdout_result(self) -> dict[str, Any] | None:
        path = self.config.calibration_run_dir / "holdout_result.json"
        if not path.is_file():
            return None
        plan = self._validated_plan()
        selection = refinement_v5._load_development_selection(  # noqa: SLF001
            plan, self.config.calibration_run_dir
        )
        evidence = refinement_v5._load_stage_evidence(  # noqa: SLF001
            plan, self.config.calibration_run_dir, "holdout"
        )
        mode = refinement_v5._registered_execution_mode(  # noqa: SLF001
            plan, self.config.calibration_run_dir
        )
        expected = refinement_v5._build_holdout_result(  # noqa: SLF001
            plan, evidence, selection, execution_mode=mode
        )
        actual = relay_v4._read_json(path)  # noqa: SLF001
        relay_v4._verify_signed_json(  # noqa: SLF001
            actual, "holdout_signature", "résultat holdout V5"
        )
        if (
            actual != expected
            or actual.get("publishable") is not True
            or actual.get("retuning_after_holdout") is not False
            or int(actual.get("holdout_evidence_case_count") or -1)
            != EXPECTED_HOLDOUT_CASES
        ):
            raise FullCampaignRelayError("Résultat holdout V5 non reproductible")
        return actual

    def finalize_holdout(self) -> dict[str, Any]:
        raise FullCampaignRelayError(
            "Relais V5 aval uniquement : finalisation du holdout interdite"
        )
        self.run_step(
            step="decision_holdout_v5",
            command=self._python_module(
                CORE_MODULE,
                "finalize",
                "--plan-dir",
                str(self.config.calibration_plan_dir),
                "--run-dir",
                str(self.config.calibration_run_dir),
                "--stage",
                "holdout",
            ),
            completion_check=lambda: self._holdout_result() is not None,
            message_fr="Décision figée sur les 90 preuves V5, sans nouveau réglage.",
            run_even_if_complete=True,
        )
        result = self._holdout_result()
        if result is None:  # pragma: no cover - guarded by run_step
            raise FullCampaignRelayError("Résultat holdout V5 absent")
        self._record_artifact(
            "v5_holdout_result",
            self.config.calibration_run_dir / "holdout_result.json",
        )
        if result.get("accepted") is not True:
            raise ScientificNoGo(
                "Le holdout V5 a rejeté au moins un état; aucune campagne incident "
                "n'est lancée et aucun réglage post-holdout n'est autorisé"
            )
        if result.get("status") != bridge_v5.ACCEPTED_HOLDOUT_STATUS:
            raise FullCampaignRelayError("Statut accepté V5 inattendu")
        self.update_status(
            "holdout_v5_accepte",
            "Les trois états ont passé la validation indépendante de 30 simulations.",
            progress={"holdout_cases": 90, "retuning_after_holdout": False},
        )
        return result

    def _bridge_ready(self) -> bool:
        if not self.config.bridge_json.is_file():
            return False
        payload = bridge_v5.validate_bridge(
            self.config.bridge_json, revalidate_source=True
        )
        if len(payload.get("trace_index") or []) != EXPECTED_HOLDOUT_CASES or [
            row.get("operating_point_id")
            for row in payload.get("operating_points") or []
        ] != list(EXPECTED_STATE_IDS):
            raise FullCampaignRelayError("Pont V5 incomplet")
        return True

    def build_and_validate_bridge(self) -> None:
        self.run_step(
            step="construction_pont_v5",
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
            message_fr="Référencement signé des trois états et 90 traces V5, sans recalcul.",
        )
        self.run_step(
            step="validation_pont_v5",
            command=self._python_module(
                BRIDGE_MODULE, "validate", "--path", str(self.config.bridge_json)
            ),
            completion_check=self._bridge_ready,
            message_fr="Relecture complète du pont V5 et de ses preuves.",
            run_even_if_complete=True,
        )
        self._record_artifact(
            "validated_operating_points_bridge", self.config.bridge_json
        )

    def plan_campaign(self) -> None:
        self.run_step(
            step="planification_campagne_v5",
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
            message_fr="Plan figé: 3 états, 18 voies et 30 répétitions appariées.",
            run_even_if_complete=True,
        )
        self._record_artifact(
            "campaign_manifest", self.config.campaign_root / "campaign_manifest.json"
        )

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
                f"Le lanceur de campagne a publié un statut terminal invalide : {status}"
            )
        if (
            payload.get("phase") != "shards"
            or payload.get("target_discovery_status") != "complete"
            or int(payload.get("planned_shard_count") or -1) != EXPECTED_SHARDS
            or int(payload.get("completed_shard_count") or -1) != EXPECTED_SHARDS
            or not _is_exact_int(payload.get("failed_shard_count"), 0)
            or not _is_exact_int(payload.get("active_shard_count"), 0)
            or not _is_exact_int(payload.get("queued_shard_count"), 0)
        ):
            raise FullCampaignRelayError("Progression finale du lanceur incohérente")
        runner = relay_v4._module_path(  # noqa: SLF001
            self.config.repo, CAMPAIGN_MODULE
        ).resolve()
        with launcher_v5.patched_v5_context():
            launcher = launcher_v5.implementation_v4
            manifest, shards = launcher.load_campaign_plan(
                self.config.campaign_root, runner
            )
            expected_contract = launcher._launch_contract(  # noqa: SLF001
                manifest=manifest, runner=runner, shards=shards
            )
            contract_path = self.config.campaign_root / "launch_contract.json"
            if (
                not contract_path.is_file()
                or relay_v4._read_json(contract_path) != expected_contract  # noqa: SLF001
            ):
                raise FullCampaignRelayError("Contrat signé du lanceur V5 incohérent")
            if (
                payload.get("schema_version") != launcher.PROGRESS_SCHEMA_VERSION
                or payload.get("campaign_signature")
                != manifest.get("campaign_signature")
                or payload.get("launch_contract_signature")
                != expected_contract.get("launch_contract_signature")
            ):
                raise FullCampaignRelayError("Progression non liée au plan V5")
            discovery_state, discovery_detail = launcher._discovery_completion_state(  # noqa: SLF001
                self.config.campaign_root, manifest=manifest
            )
            if discovery_state != "complete":
                raise FullCampaignRelayError(
                    "Choix de fenêtre incomplet : " + discovery_detail
                )
            smoke_state, smoke_detail = launcher._smoke_completion_state(  # noqa: SLF001
                self.config.campaign_root, manifest=manifest
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
        return True

    def launch_campaign(self) -> None:
        self._wait_for_orphaned_launcher_children()
        runner = relay_v4._module_path(  # noqa: SLF001
            self.config.repo, CAMPAIGN_MODULE
        ).resolve()
        self.run_step(
            step="campagne_incidents_v5",
            command=self._python_module(
                LAUNCHER_MODULE,
                "--campaign-root",
                str(self.config.campaign_root),
                "--runner",
                str(runner),
                "--parallel-shards",
                str(self.config.parallel_shards),
                "--workers-per-shard",
                str(self.config.workers_per_shard),
                "--poll-seconds",
                str(self.config.launcher_poll_seconds),
            ),
            completion_check=self._campaign_launch_ready,
            message_fr=(
                "Exécution de 3 choix de fenêtre, du contrôle op_93 puis des 18 blocs incidents."
            ),
            progress_reader=self._launch_progress,
        )
        self._record_artifact(
            "campaign_launch_progress",
            self.config.campaign_root / "launch_progress.json",
        )

    def finalize_campaign(self) -> None:
        self.run_step(
            step="consolidation_3330_lignes_v5",
            command=self._python_module(
                FINALIZER_MODULE,
                "--campaign-root",
                str(self.config.campaign_root),
                "--output-dir",
                str(self.config.results_dir),
            ),
            completion_check=self._results_ready,
            message_fr=(
                "Reconstruction des 3 330 preuves, sensibilités, dispersion et priorités."
            ),
        )
        self._record_artifact(
            "campaign_validation", self.config.results_dir / "campaign_validation.json"
        )

    def _selected_dossiers_physically_exercised(self) -> bool:
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_physical_cascade_qualification_v5 as qualification,
        )

        proof = qualification.validate_selected_dossiers_physically_exercised(
            campaign_root=self.config.campaign_root,
            results_dir=self.config.results_dir,
        )
        selected = self._lot_selection()
        if not _is_exact_int(proof.get("selected_dossier_count"), len(selected)):
            raise FullCampaignRelayError(
                "La sélection lots n'est pas physiquement exercée dans la campagne"
            )
        return True

    def _qualification_ready(self) -> bool:
        if not self.config.qualification_dir.is_dir():
            return False
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_physical_cascade_qualification_v5 as qualification,
        )

        payload = qualification.validate_qualification_sidecar(
            campaign_root=self.config.campaign_root,
            results_dir=self.config.results_dir,
            replay_root=self.config.lot_replay_root,
            output_dir=self.config.qualification_dir,
        )
        counts = payload.get("counts") or {}
        selection_guard = payload.get("selection_guard") or {}
        if (
            payload.get("status") != "complete_qualified"
            or int(counts.get("lane_count") or -1) != EXPECTED_CORRIDORS
            or int(counts.get("dynamic_mrp_lane_count") or -1) != 2
            or int(counts.get("static_mrp_lane_count") or -1) != 16
            or not _is_exact_int(
                counts.get("full_dynamic_cascade_proven_count"), 0
            )
            or not _is_exact_int(
                counts.get("selected_dossier_count"), len(self._lot_selection())
            )
            or selection_guard.get(
                "all_selected_campaign_dossiers_shipment_exercised"
            )
            is not True
            or selection_guard.get(
                "all_replayed_dossiers_shipment_to_receipt_exercised"
            )
            is not True
            or selection_guard.get("selection_proves_full_dynamic_cascade") is not False
        ):
            raise FullCampaignRelayError(
                "La qualification physique V5 ne respecte pas son périmètre scientifique"
            )
        return True

    def qualify_physical_cascades(self) -> None:
        """Qualify selected incidents and lot traces before any client rendering."""

        common = (
            "--campaign-root",
            str(self.config.campaign_root),
            "--results-dir",
            str(self.config.results_dir),
        )
        self.run_step(
            step="validation_selection_physiquement_exercee_v5",
            command=self._python_module(
                QUALIFICATION_MODULE,
                "validate-selection",
                *common,
            ),
            completion_check=self._selected_dossiers_physically_exercised,
            message_fr=(
                "Vérification que chaque dossier retenu correspond à un incident "
                "effectivement exercé dans la simulation."
            ),
            run_even_if_complete=True,
        )
        qualification_arguments = (
            *common,
            "--replay-root",
            str(self.config.lot_replay_root),
            "--output-dir",
            str(self.config.qualification_dir),
        )
        self.run_step(
            step="construction_qualification_physique_v5",
            command=self._python_module(
                QUALIFICATION_MODULE,
                "build",
                *qualification_arguments,
            ),
            completion_check=self._qualification_ready,
            message_fr=(
                "Qualification des traces disponibles : exposition fournisseur, "
                "réception, consommation, production et contact client agrégé."
            ),
        )
        self.run_step(
            step="validation_qualification_physique_v5",
            command=self._python_module(
                QUALIFICATION_MODULE,
                "validate",
                *qualification_arguments,
            ),
            completion_check=self._qualification_ready,
            message_fr="Validation finale de la portée physique réellement démontrée.",
            run_even_if_complete=True,
        )
        for label, name in (
            ("physical_qualification", "physical_cascade_qualification_v5.json"),
            ("physical_qualification_table", "physical_cascade_qualification_v5.csv"),
            (
                "physical_qualification_manifest",
                "physical_cascade_qualification_v5.manifest.json",
            ),
        ):
            self._record_artifact(label, self.config.qualification_dir / name)

    def _no_action_execute_attempt_ready(self) -> bool:
        entry = (self.status.get("steps") or {}).get(
            "confirmation_execution_actions_v5"
        )
        if not isinstance(entry, Mapping):
            return False
        attempts = entry.get("attempts") or []
        return any(
            isinstance(attempt, Mapping)
            and attempt.get("return_code") == 0
            and "--execute" in list(attempt.get("command") or [])
            for attempt in attempts
        )

    def process_optional_action_replay(self) -> None:
        """Run required actions and prove an execute attempt even for a zero-arm plan."""

        super().process_optional_action_replay()
        action = self.status.get("action_replay") or {}
        if not isinstance(action, Mapping) or action.get("status") != (
            "complete_no_representable_action"
        ):
            return
        root = self.config.action_replay_root
        if root is None:  # pragma: no cover - rejected by configuration preflight
            raise FullCampaignRelayError("Racine actions obligatoire absente")
        self.run_step(
            step="confirmation_execution_actions_v5",
            command=self._python_module(
                relay_v4.ACTION_REPLAY_MODULE,
                "run",
                "--output-root",
                str(root),
                "--execute",
                "--workers",
                "2",
            ),
            completion_check=self._no_action_execute_attempt_ready,
            message_fr=(
                "Confirmation explicite du mode exécution; le moteur ne lance aucun "
                "bras lorsqu'aucune action n'est représentable."
            ),
        )

    def validate_required_action_outcome(self) -> str:
        """Refuse final publication unless the required action phase is conclusive."""

        action = self.status.get("action_replay") or {}
        status = str(action.get("status") if isinstance(action, Mapping) else "")
        if status not in ACCEPTED_REQUIRED_ACTION_STATUSES:
            raise FullCampaignRelayError(
                "La phase actions obligatoire n'a pas de conclusion scientifique "
                f"publiable: {status or 'statut absent'}"
            )
        if status == "not_run_no_qualified_dossier":
            if self._lot_selection():
                raise FullCampaignRelayError(
                    "Des dossiers lots existent mais la phase actions n'a pas été tentée"
                )
            return status

        root = self.config.action_replay_root
        if root is None:  # pragma: no cover - rejected by configuration preflight
            raise FullCampaignRelayError("Racine actions obligatoire absente")
        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_priority_action_replay_v4 as actions,
        )

        _summary, validation = actions.validate_action_results(root)
        validation_path = root / "action_replay_validation.json"
        if (
            validation.get("status") != status
            or not validation_path.is_file()
            or not isinstance(action, Mapping)
            or action.get("validation_sha256")
            != relay_v4.sha256_file(validation_path)
        ):
            raise FullCampaignRelayError(
                "La conclusion actions obligatoire ne correspond pas aux preuves"
            )
        if status == "complete_no_representable_action" and not (
            self._no_action_execute_attempt_ready()
        ):
            raise FullCampaignRelayError(
                "L'absence d'action représentable n'est valide qu'après une tentative "
                "explicite en mode exécution"
            )
        return status

    def validate_required_curves_outcome(self) -> None:
        """Make the validated nominal curves mandatory for the complete delivery."""

        curves = self.status.get("nominal_curves") or {}
        status = str(curves.get("status") if isinstance(curves, Mapping) else "")
        if status != "complete_validated":
            raise FullCampaignRelayError(
                "Les courbes nominales obligatoires ne sont pas publiables: "
                f"{status or 'statut absent'}"
            )

    def _final_delivery_ready(self, *, recover_owned_partial: bool = False) -> bool:
        output = self.config.final_html
        if output is None:  # pragma: no cover - rejected by configuration preflight
            raise FullCampaignRelayError("HTML final V5 obligatoire absent")
        self._validate_legacy_html_inventory()
        manifest_path = Path(str(output) + ".manifest.json")
        for candidate in (output, manifest_path):
            if candidate.exists() and not candidate.is_file():
                raise FullCampaignRelayError(
                    f"Chemin de livraison final non régulier : {candidate}"
                )
        html_exists = output.is_file()
        manifest_exists = manifest_path.is_file()
        if not html_exists and not manifest_exists:
            return False
        if html_exists != manifest_exists:
            if recover_owned_partial:
                if self._step_child_running("livrable_final_autonome"):
                    return False
                self._archive_partial_final_delivery()
                return False
            raise FullCampaignRelayError("Livrable autonome final V5 partiel")

        from etudecas.prototypes.scan_2027_risk_control import (
            supplier_v5_final_standalone_delivery as delivery,
        )

        delivery.validate_delivery(output)
        action_status = self.validate_required_action_outcome()
        self.validate_required_curves_outcome()
        self.revalidate_published_optional_products()
        if not self._qualification_ready():
            raise FullCampaignRelayError("Qualification physique V5 absente")
        replay_root = self.config.lot_replay_root if self._lot_selection() else None
        action_root = (
            self.config.action_replay_root
            if action_status
            in {"complete_validated", "complete_no_representable_action"}
            else None
        )
        _payload, expected_bindings = delivery.build_delivery_payload(
            campaign_root=self.config.campaign_root,
            results_dir=self.config.results_dir,
            curves_dir=self.config.sidecar_dir,
            replay_root=replay_root,
            qualification_dir=self.config.qualification_dir,
            output_html=output,
            target_registry_path=(
                self.config.results_dir / "cross_state_target_registry.json"
            ),
            dashboard_html=None,
            action_results_root=action_root,
            legacy_risk_html=None,
            legacy_control_html=None,
        )
        manifest = relay_v4._read_json(manifest_path)  # noqa: SLF001
        if (
            Path(str(manifest.get("generator") or "")).resolve()
            != Path(delivery.__file__).resolve()
            or manifest.get("generator_sha256")
            != relay_v4.sha256_file(Path(delivery.__file__).resolve())
            or manifest.get("source_bindings") != expected_bindings
        ):
            raise FullCampaignRelayError(
                "Le livrable V5 n'est pas lié à toutes les sources aval courantes"
            )
        return True

    def build_final_delivery(self, lot_count: int) -> None:
        """Build the client-facing three-view HTML through the strict V5 renderer."""

        output = self.config.final_html
        if output is None:  # pragma: no cover - rejected by configuration preflight
            raise FullCampaignRelayError("HTML final V5 obligatoire absent")
        if not self._qualification_ready():
            raise FullCampaignRelayError("Qualification physique V5 obligatoire absente")
        action_status = self.validate_required_action_outcome()
        self.validate_required_curves_outcome()
        command = self._python_module(
            DELIVERY_MODULE,
            "build",
            "--campaign-root",
            str(self.config.campaign_root),
            "--results-dir",
            str(self.config.results_dir),
            "--curves-dir",
            str(self.config.sidecar_dir),
            "--qualification-dir",
            str(self.config.qualification_dir),
            "--target-registry",
            str(self.config.results_dir / "cross_state_target_registry.json"),
            "--output-html",
            str(output),
        )
        if lot_count:
            command.extend(["--lot-replay-root", str(self.config.lot_replay_root)])
        if action_status in {
            "complete_validated",
            "complete_no_representable_action",
        }:
            command.extend(
                ["--action-results-root", str(self.config.action_replay_root)]
            )
        self.run_step(
            step="livrable_final_autonome",
            command=command,
            completion_check=lambda: self._final_delivery_ready(
                recover_owned_partial=True
            ),
            message_fr=(
                "Construction des trois vues client à partir des preuves V5 qualifiées."
            ),
        )
        self.run_step(
            step="validation_livrable_final_v5",
            command=self._python_module(
                DELIVERY_MODULE,
                "validate",
                "--path",
                str(output),
            ),
            completion_check=self._final_delivery_ready,
            message_fr="Validation hors ligne du livrable client V5.",
            run_even_if_complete=True,
        )
        self._record_artifact("final_standalone_html", output)
        self._record_artifact(
            "final_standalone_manifest",
            Path(str(output) + ".manifest.json"),
        )

    def execute(self) -> int:
        self.prepare()
        self.validate_downstream_corridor_preflight()
        self.build_and_validate_bridge()
        self.plan_campaign()
        self.launch_campaign()
        self.finalize_campaign()
        selection = self._lot_selection()
        self.run_lot_replays(selection)
        self.qualify_physical_cascades()
        self.process_optional_action_replay()
        self.validate_required_action_outcome()
        self.process_optional_curves()
        self.validate_required_curves_outcome()
        self.build_dashboard()
        self.build_final_delivery(len(selection))
        self.status["active_command"] = {}
        self.status["completed_at_utc"] = relay_v4._now()  # noqa: SLF001
        curves_ok = (self.status.get("nominal_curves") or {}).get(
            "status"
        ) == "complete_validated"
        action_status = str(
            (self.status.get("action_replay") or {}).get("status") or "not_configured"
        )
        action_limited = (
            self.config.action_replay_root is not None
            and action_status not in ACCEPTED_REQUIRED_ACTION_STATUSES
        )
        self.update_status(
            "traitement_v5_termine",
            (
                "Relais aval V5 terminé : calibration relue, 3 330 résultats incidents, "
                f"{len(selection)} dossier(s) lots qualifiés et HTML autonome; "
                + (
                    "courbes incluses."
                    if curves_ok
                    else "courbes exclues car incomplètes."
                )
            ),
            status=(
                "complete"
                if curves_ok and not action_limited
                else "complete_with_limits"
            ),
            progress={
                "validated_upstream_development_cases": EXPECTED_DEVELOPMENT_CASES,
                "development_engine_runs_by_relay": 0,
                "validated_upstream_holdout_cases": EXPECTED_HOLDOUT_CASES,
                "holdout_engine_runs_by_relay": 0,
                "holdout_cases_rerun_in_campaign": 0,
                "campaign_rows": EXPECTED_CAMPAIGN_ROWS,
                "lot_replay_dossiers": len(selection),
                "physical_qualification": "complete_validated",
                "nominal_curves_available": curves_ok,
                "action_replay_status": action_status,
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
                "Un autre relais de campagne V5 est déjà actif"
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


def _config_from_args(args: argparse.Namespace) -> V5RelayConfig:
    return V5RelayConfig(
        repo=args.repo,
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
        dashboard_html=args.dashboard_html,
        final_html=args.final_html,
        supervision_dir=args.supervision_dir,
        action_replay_root=args.action_replay_root,
        legacy_risk_html=args.legacy_risk_html,
        legacy_control_html=args.legacy_control_html,
        action_replay_mode=args.action_replay_mode,
        sidecar_watcher_pid=args.sidecar_watcher_pid,
        calibration_workers=args.calibration_workers,
        parallel_shards=args.parallel_shards,
        workers_per_shard=args.workers_per_shard,
        launcher_poll_seconds=args.launcher_poll_seconds,
        relay_poll_seconds=args.relay_poll_seconds,
        watcher_ready_timeout_seconds=args.watcher_ready_timeout_seconds,
        sidecar_poll_ms=args.sidecar_poll_ms,
        sidecar_stability_ms=args.sidecar_stability_ms,
        max_wait_hours=args.max_wait_hours,
    ).resolved()


def _child_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        "-m",
        MODULE_NAME,
        "--repo",
        str(args.repo.resolve()),
        "--v4-plan-dir",
        str(args.v4_plan_dir.resolve()),
        "--v4-run-dir",
        str(args.v4_run_dir.resolve()),
        "--v4-sidecar-root",
        str(args.v4_sidecar_root.resolve()),
        "--calibration-plan-dir",
        str(args.calibration_plan_dir.resolve()),
        "--calibration-run-dir",
        str(args.calibration_run_dir.resolve()),
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
        "--qualification-dir",
        str(args.qualification_dir.resolve()),
        "--dashboard-html",
        str(args.dashboard_html.resolve()),
        "--supervision-dir",
        str(args.supervision_dir.resolve()),
        "--calibration-workers",
        str(args.calibration_workers),
        "--parallel-shards",
        str(args.parallel_shards),
        "--workers-per-shard",
        str(args.workers_per_shard),
        "--launcher-poll-seconds",
        str(args.launcher_poll_seconds),
        "--relay-poll-seconds",
        str(args.relay_poll_seconds),
        "--watcher-ready-timeout-seconds",
        str(args.watcher_ready_timeout_seconds),
        "--sidecar-poll-ms",
        str(args.sidecar_poll_ms),
        "--sidecar-stability-ms",
        str(args.sidecar_stability_ms),
        "--max-wait-hours",
        str(args.max_wait_hours),
        "--action-replay-mode",
        args.action_replay_mode,
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
    relay = FullCampaignRelayV5(config)
    relay.prepare()
    receipt_path = config.supervision_dir / "detached.json"
    if receipt_path.is_file():
        previous = relay_v4._read_json(receipt_path)  # noqa: SLF001
        previous_pid = int(previous.get("pid") or 0)
        if relay_v4._process_running(previous_pid):  # noqa: SLF001
            raise FullCampaignRelayError(
                f"Un relais V5 détaché est déjà actif (PID {previous_pid})"
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
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.detached.v1",
        "status": "detached_relay_started",
        "pid": process.pid,
        "command": command,
        "command_sha256": relay_v4.stable_sha256(command),
        "log_path": str(log_path),
        "status_path": str(relay.status_path),
        "started_at_utc": relay_v4._now(),  # noqa: SLF001
    }
    payload = {**unsigned, "receipt_signature": relay_v4.stable_sha256(unsigned)}
    relay_v4._atomic_json(receipt_path, payload)  # noqa: SLF001
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--v4-plan-dir", type=Path, required=True)
    parser.add_argument("--v4-run-dir", type=Path, required=True)
    parser.add_argument("--v4-sidecar-root", type=Path, required=True)
    parser.add_argument("--calibration-plan-dir", type=Path, required=True)
    parser.add_argument("--calibration-run-dir", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument("--sidecar-watcher-pid", type=int, default=0)
    parser.add_argument("--bridge-json", type=Path, required=True)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--lot-replay-root", type=Path, required=True)
    parser.add_argument("--qualification-dir", type=Path, required=True)
    parser.add_argument("--dashboard-html", type=Path, required=True)
    parser.add_argument("--final-html", type=Path, required=True)
    parser.add_argument("--action-replay-root", type=Path, required=True)
    parser.add_argument("--legacy-risk-html", type=Path)
    parser.add_argument("--legacy-control-html", type=Path)
    parser.add_argument(
        "--action-replay-mode", choices=("required",), required=True
    )
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--calibration-workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=2)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--launcher-poll-seconds", type=float, default=5.0)
    parser.add_argument("--relay-poll-seconds", type=float, default=30.0)
    parser.add_argument("--watcher-ready-timeout-seconds", type=float, default=300.0)
    parser.add_argument("--sidecar-poll-ms", type=float, default=25.0)
    parser.add_argument("--sidecar-stability-ms", type=float, default=12.0)
    parser.add_argument("--max-wait-hours", type=float, default=240.0)
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
            print(f"RELAIS V5 NON LANCÉ : {exc}", file=sys.stderr)
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    config = _config_from_args(args)
    relay = FullCampaignRelayV5(config)
    relay_v4._prevent_sleep(True)  # noqa: SLF001
    try:
        # The lock lives under the downstream supervision root.  Validate the
        # immutable calibration first so even that lock file is not created for
        # an incomplete or rejected handoff.  execute()/prepare() revalidates
        # under the lock before publishing the signed relay contract.
        config.validate()
        relay.validate_calibration_handoff()
        with _relay_lock(config.supervision_dir / ".relay.lock"):
            return relay.execute()
    except ScientificNoGo as exc:
        if relay.contract:
            relay.update_status(
                "arret_scientifique_v5", str(exc), status="scientific_no_go"
            )
        print(f"RELAIS V5 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("RELAIS V5 INTERROMPU; consulter status.json", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - process boundary diagnostics
        if relay.contract:
            relay.status["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc)),
            }
            relay.update_status("echec_v5", str(exc), status="failed")
        print(f"RELAIS V5 EN ÉCHEC : {exc}", file=sys.stderr)
        return 1
    finally:
        relay_v4._prevent_sleep(False)  # noqa: SLF001


if __name__ == "__main__":
    raise SystemExit(main())
