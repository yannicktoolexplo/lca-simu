#!/usr/bin/env python3
"""Vérification additive de clôture de la campagne fournisseurs V8 / Stage3 V3.

Ce programme ne lance aucun calcul et ne produit aucun livrable métier. Il ne
peut être utilisé qu'après la fin signée de Stage3 V3. Il revalide les preuves
amont et aval, puis publie un constat JSON immuable avec deux verdicts distincts :
conformité technique et exploitabilité métier des dossiers lots.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as actions_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_full_incident_lot_registry as registry_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_curves as curves_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_dashboard as dashboard_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_delivery as delivery_v3,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_pipeline as pipeline_v3,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage3_closure.v1"
EXPECTED_COUNTS = {
    "campaign_seeds": 30,
    "baseline_rows": 90,
    "incident_rows": 3_240,
    "campaign_rows": 3_330,
    "operating_states": 3,
    "lanes": 18,
}
EXPECTED_STATES = ("op_100", "op_93", "op_80")
EXPECTED_MECHANISMS = (
    "transport_delay",
    "planned_delivery_shortfall",
)
PROTECTED_HTML = (
    (
        Path(
            r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
            r"\DEMONSTRATION_REUNION_1500_20260904_v1"
            r"\OUVRIR_DEMONSTRATION_RESILIENCE_SCAN.html"
        ),
        "09cb1a0ade28a8adf782d57025b234cab1051de8f53f7876af24491142ddbe76",
    ),
    (
        Path(
            r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
            r"\industrial_supply_preliminary_consolidated_20260904_v4"
            r"\assets\carte_reseau_existante_hors_ligne.html"
        ),
        "7aab17a0fae413f2ec6f36f975617feeadf98a1e09a1c6c660a31807108323cd",
    ),
)
_EXTERNAL_URL_RE = re.compile(
    r"(?is)(?:\b(?:src|href|action)\s*=\s*['\"]\s*(?:https?:|//))"
    r"|(?:\burl\(\s*['\"]?\s*(?:https?:|//))"
    r"|(?:\b@import\s+(?:url\()?\s*['\"]?\s*(?:https?:|//))"
)


class ClosureVerificationError(RuntimeError):
    """Une preuve de clôture est absente, incohérente ou modifiée."""


class ClosureNotFinal(ClosureVerificationError):
    """Stage3 V3 n'a pas encore publié son état final signé."""


@dataclass(frozen=True)
class FinalContext:
    paths: common.Stage2Paths
    contract: dict[str, Any]
    status: dict[str, Any]


@dataclass(frozen=True)
class CheckEvidence:
    details: dict[str, Any]
    value: Any = None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClosureVerificationError(f"JSON illisible : {path.resolve()}") from exc
    if not isinstance(payload, dict):
        raise ClosureVerificationError(f"Objet JSON attendu : {path.resolve()}")
    return payload


def _raw_report(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def publish_new_or_identical(path: Path, payload: Mapping[str, Any]) -> None:
    """Publier atomiquement une fois, ou accepter les octets strictement identiques."""

    destination = path.resolve()
    raw = _raw_report(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != raw:
            raise ClosureVerificationError(
                f"Rapport existant différent ; écrasement refusé : {destination}"
            )
        return
    temporary = destination.with_name(
        f".{destination.name}.closure-{os.getpid()}-{os.urandom(8).hex()}"
    )
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if not destination.is_file() or destination.read_bytes() != raw:
                raise ClosureVerificationError(
                    "Une publication concurrente diffère ; écrasement refusé : "
                    f"{destination}"
                )
    finally:
        temporary.unlink(missing_ok=True)


def _mapping_to_paths(mapping: Mapping[str, Any]) -> common.Stage2Paths:
    expected = set(common.Stage2Paths.__dataclass_fields__)
    if set(mapping) != expected:
        raise ClosureNotFinal("Le contrat Stage3 V3 ne déclare pas tous ses chemins.")
    values: dict[str, Path | None] = {}
    for name in sorted(expected):
        value = mapping.get(name)
        if name == "observed_2025_dir" and value is None:
            values[name] = None
            continue
        if not isinstance(value, str) or not value.strip():
            raise ClosureNotFinal(f"Chemin Stage3 V3 absent : {name}")
        values[name] = Path(value)
    return common.Stage2Paths(**values).resolved()


def load_final_context(supervision_dir: Path) -> FinalContext:
    """Refuser toute exécution avant le marqueur final signé de Stage3 V3."""

    supervision = supervision_dir.resolve()
    contract_path = supervision / pipeline_v3.CONTRACT_NAME
    status_path = supervision / pipeline_v3.STATUS_NAME
    if not contract_path.is_file() or not status_path.is_file():
        raise ClosureNotFinal("Contrat ou statut Stage3 V3 final absent.")
    contract = common.read_json(contract_path)
    common.verify_signature(contract, "contract_signature", "contrat Stage3 V3")
    if contract.get("schema_version") != f"{pipeline_v3.SCHEMA_VERSION}.contract.v1":
        raise ClosureNotFinal("Le contrat fourni n'est pas celui de Stage3 V3.")
    mapping = contract.get("paths")
    if not isinstance(mapping, Mapping):
        raise ClosureNotFinal("Le contrat Stage3 V3 ne porte pas ses chemins.")
    paths = _mapping_to_paths(mapping)
    if paths.supervision_dir != supervision:
        raise ClosureNotFinal("Le statut demandé appartient à une autre supervision.")
    status = common.read_json(status_path)
    common.verify_signature(status, "status_signature", "statut final Stage3 V3")
    if (
        status.get("schema_version") != f"{pipeline_v3.SCHEMA_VERSION}.status.v1"
        or status.get("contract_signature") != contract.get("contract_signature")
        or status.get("status") != "complete"
        or status.get("step") != "termine"
        or not isinstance(status.get("results"), Mapping)
        or not paths.final_html.is_file()
        or not Path(str(paths.final_html) + ".manifest.json").is_file()
    ):
        raise ClosureNotFinal(
            "Stage3 V3 n'est pas encore terminé et publié ; aucun audit n'est produit."
        )
    return FinalContext(paths=paths, contract=contract, status=status)


def _assert_output_separation(output_json: Path, paths: common.Stage2Paths) -> None:
    output = output_json.resolve()
    protected_roots = tuple(
        path
        for path in (
            paths.repo,
            paths.v7_plan_dir,
            paths.v7_run_dir,
            paths.trace_package_dir,
            paths.campaign_root,
            paths.results_dir,
            paths.stage1_supervision_dir,
            paths.observed_2025_dir,
            paths.lot_replay_root,
            paths.qualification_dir,
            paths.action_replay_root,
            paths.curves_dir,
            paths.registry_dir,
            paths.supervision_dir,
        )
        if path is not None
    )
    if any(output == root or root in output.parents for root in protected_roots):
        raise ClosureVerificationError(
            "Le rapport de clôture doit être publié dans un nouveau dossier séparé."
        )
    if output in {paths.bridge_json, paths.final_html}:
        raise ClosureVerificationError("Le rapport de clôture chevauche une preuve.")


def _assert_campaign_contract(
    *,
    receipt: Mapping[str, Any],
    overlay: Mapping[str, Any],
    validation: Mapping[str, Any],
    dashboard: Mapping[str, Any],
    launch: Mapping[str, Any],
) -> None:
    counts = receipt.get("counts") or {}
    overlay_counts = overlay.get("counts") or {}
    expected = validation.get("expected_contract") or {}
    reconstructed = validation.get("signed_case_evidence") or {}
    progress = validation.get("shard_progress") or {}
    comparisons = validation.get("comparability_checks") or {}
    mechanisms = {str(row.get("id") or "") for row in dashboard.get("mechanisms") or []}
    states = {str(row.get("id") or "") for row in dashboard.get("states") or []}
    if (
        counts
        != {
            "validation_seeds": 150,
            "validation_cases": 450,
            "campaign_seeds": EXPECTED_COUNTS["campaign_seeds"],
            "baseline_rows": EXPECTED_COUNTS["baseline_rows"],
            "incident_rows": EXPECTED_COUNTS["incident_rows"],
            "campaign_rows": EXPECTED_COUNTS["campaign_rows"],
        }
        or overlay_counts.get("campaign_seed_count")
        != EXPECTED_COUNTS["campaign_seeds"]
        or overlay_counts.get("baseline_row_count") != EXPECTED_COUNTS["baseline_rows"]
        or overlay_counts.get("incident_row_count") != EXPECTED_COUNTS["incident_rows"]
        or overlay_counts.get("campaign_row_count") != EXPECTED_COUNTS["campaign_rows"]
        or expected.get("paired_repetition_count") != EXPECTED_COUNTS["campaign_seeds"]
        or len(expected.get("repetition_ids") or [])
        != EXPECTED_COUNTS["campaign_seeds"]
        or len(set(expected.get("repetition_ids") or []))
        != EXPECTED_COUNTS["campaign_seeds"]
        or expected.get("baseline_row_count") != EXPECTED_COUNTS["baseline_rows"]
        or expected.get("incident_row_count") != EXPECTED_COUNTS["incident_rows"]
        or tuple(expected.get("mechanisms") or ()) != EXPECTED_MECHANISMS
        or reconstructed.get("status") != "complete_reconstructed"
        or reconstructed.get("case_count") != EXPECTED_COUNTS["campaign_rows"]
        or reconstructed.get("baseline_case_count") != EXPECTED_COUNTS["baseline_rows"]
        or reconstructed.get("incident_case_count") != EXPECTED_COUNTS["incident_rows"]
        or progress.get("status") != "complete"
        or progress.get("planned_case_count") != EXPECTED_COUNTS["campaign_rows"]
        or progress.get("completed_case_count") != EXPECTED_COUNTS["campaign_rows"]
        or progress.get("failed_case_count") != 0
        or comparisons.get("complete_3x18x2x30_matrix") is not True
        or comparisons.get("all_18_shard_progress_documents_complete") is not True
        or comparisons.get("all_3330_metrics_reconstructed_from_signed_case_evidence")
        is not True
        or comparisons.get("shipment_set_and_incident_trace_proven") is not True
        or comparisons.get("quality_or_availability_incident_count") != 0
        or launch.get("status") != "complete"
        or launch.get("completed_shard_count") != EXPECTED_COUNTS["lanes"]
        or launch.get("failed_shard_count") != 0
        or launch.get("active_shard_count") != 0
        or launch.get("queued_shard_count") != 0
        or states != set(EXPECTED_STATES)
        or mechanisms != set(EXPECTED_MECHANISMS)
        or dashboard.get("repetitions") != EXPECTED_COUNTS["campaign_seeds"]
        or dashboard.get("laneCount") != EXPECTED_COUNTS["lanes"]
    ):
        raise ClosureVerificationError(
            "La matrice 3 niveaux × 30 simulations, 90 références + 3 240 "
            "incidents, ses mécanismes séparés ou ses preuves physiques ont changé."
        )


def _campaign_evidence(paths: common.Stage2Paths) -> CheckEvidence:
    receipt = common.validate_bound_stage1_receipt(
        paths, paths.supervision_dir / common.STAGE1_RECEIPT_NAME
    )
    overlay = finalizer_v8.validate_v8_overlay(paths.campaign_root, paths.results_dir)
    validation = _read_json(paths.results_dir / "campaign_validation.json")
    dashboard = dashboard_v8.load_dashboard_data(
        campaign_root=paths.campaign_root,
        results_dir=paths.results_dir,
        target_registry_path=paths.results_dir / "cross_state_target_registry.json",
    )
    launch = common.read_json(paths.campaign_root / "launch_progress.json")
    _assert_campaign_contract(
        receipt=receipt,
        overlay=overlay,
        validation=validation,
        dashboard=dashboard,
        launch=launch,
    )
    return CheckEvidence(
        details={
            "campaign_rows": EXPECTED_COUNTS["campaign_rows"],
            "failed_rows": 0,
            "baseline_rows": EXPECTED_COUNTS["baseline_rows"],
            "incident_rows": EXPECTED_COUNTS["incident_rows"],
            "states": list(EXPECTED_STATES),
            "seed_count_per_state": EXPECTED_COUNTS["campaign_seeds"],
            "mechanisms_kept_separate": list(EXPECTED_MECHANISMS),
            "signed_case_evidence_reconstructed": EXPECTED_COUNTS["campaign_rows"],
            "physical_incident_trace_check": True,
            "overlay_signature": overlay["overlay_signature"],
            "campaign_signature": receipt["campaign_signature"],
        },
        value={
            "receipt": receipt,
            "overlay": overlay,
            "validation": validation,
            "dashboard": dashboard,
        },
    )


def _declared_result(status: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    results = status.get("results") or {}
    value = results.get(key) if isinstance(results, Mapping) else None
    if not isinstance(value, Mapping):
        raise ClosureVerificationError(f"Résultat final Stage3 V3 absent : {key}")
    return value


def _contract_evidence(context: FinalContext) -> CheckEvidence:
    actual = pipeline_v3.validate_bound_contract(
        context.paths, expected_contract=context.contract
    )
    status = pipeline_v3._verify_status(  # noqa: SLF001
        context.paths.supervision_dir / pipeline_v3.STATUS_NAME,
        str(actual["contract_signature"]),
    )
    if status != context.status:
        raise ClosureVerificationError("Le statut final a changé pendant l'audit.")
    return CheckEvidence(
        details={
            "status": "complete",
            "step": "termine",
            "contract_signature": actual["contract_signature"],
            "status_signature": status["status_signature"],
            "source_inventory_signature": actual["source_inventory_signature"],
        },
        value=actual,
    )


def _curve_evidence(context: FinalContext) -> CheckEvidence:
    proof = curves_v7.validate_curve_package(
        context.paths.curves_dir,
        plan_dir=context.paths.v7_plan_dir,
        run_dir=context.paths.v7_run_dir,
    )
    if dict(_declared_result(context.status, "curves")) != proof:
        raise ClosureVerificationError("Les courbes diffèrent du résultat final signé.")
    return CheckEvidence(
        details={
            "manifest": proof["manifest"],
            "manifest_signature": proof["manifest_signature"],
            "engine_runs_performed": 0,
        },
        value=proof,
    )


def _selection(paths: common.Stage2Paths) -> list[dict[str, Any]]:
    rows = pipeline_v3._selection(paths.results_dir)  # noqa: SLF001
    if len(rows) > common.MAX_DETAILED_DOSSIERS:
        raise ClosureVerificationError("Plus de trois dossiers ont été sélectionnés.")
    return rows


def _lot_and_qualification_evidence(context: FinalContext) -> CheckEvidence:
    selected = _selection(context.paths)
    replay_root = context.paths.lot_replay_root if selected else None
    with common.v8_consumer_bindings():
        replay = physical_v5.validate_replay_dossiers_physically_exercised(
            campaign_root=context.paths.campaign_root,
            results_dir=context.paths.results_dir,
            replay_root=replay_root,
        )
        qualification = physical_v5.validate_qualification_sidecar(
            campaign_root=context.paths.campaign_root,
            results_dir=context.paths.results_dir,
            replay_root=replay_root,
            output_dir=context.paths.qualification_dir,
        )
    declared_lots = _declared_result(context.status, "lots")
    declared_qualification = _declared_result(context.status, "qualification")
    if selected:
        expected_lots = {
            "status": "complete_validated",
            "dossier_count": len(selected),
            "engine_run_count": 2 * len(selected),
            "forced_top3": False,
            "plan_signature": replay["plan_signature"],
            "validation_signature": replay["replay_validation_signature"],
        }
    else:
        expected_lots = {
            "status": "not_run_no_signed_dossier",
            "dossier_count": 0,
            "engine_run_count": 0,
            "forced_top3": False,
        }
    expected_qualification = {
        "status": qualification["status"],
        "qualification_signature": qualification["qualification_signature"],
        "selected_dossier_count": len(selected),
        "full_dynamic_cascade_claimed": False,
    }
    semantics = qualification.get("evidence_semantics") or {}
    guard = qualification.get("selection_guard") or {}
    counts = qualification.get("counts") or {}
    if (
        dict(declared_lots) != expected_lots
        or dict(declared_qualification) != expected_qualification
        or replay.get("dossier_count") != len(selected)
        or counts.get("selected_dossier_count") != len(selected)
        or counts.get("full_dynamic_cascade_proven_count") != 0
        or semantics.get("complete_scope")
        != "native_lot_contact_trace_to_aggregated_client_only"
        or semantics.get("mrp_response_evidence_in_v4_replay_contract") is not False
        or guard.get("selection_proves_full_dynamic_cascade") is not False
        or guard.get("forced_top_three") is not False
    ):
        raise ClosureVerificationError(
            "Les rejeux lots, leur manifeste de qualification ou leur profondeur "
            "déclarée ont changé."
        )
    return CheckEvidence(
        details={
            "selected_dossier_count": len(selected),
            "replayed_dossier_count": replay["dossier_count"],
            "qualification_signature": qualification["qualification_signature"],
            "proof_scope": semantics["complete_scope"],
            "full_dynamic_cascade_proven": False,
            "forced_top3": False,
        },
        value={
            "selection": selected,
            "replay": replay,
            "qualification": qualification,
        },
    )


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().casefold() in {"1", "true", "yes", "oui"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError as exc:
        raise ClosureVerificationError(f"CSV illisible : {path.resolve()}") from exc


def _assert_action_gain_contract(
    summary: Mapping[str, Any],
    application_rows: Sequence[Mapping[str, Any]],
    presentation_actions: Sequence[Mapping[str, Any]],
) -> None:
    for row in application_rows:
        included = _truthy(row.get("included_in_gain_statistics"))
        exercised = _truthy(row.get("physically_exercised"))
        if included and not exercised:
            raise ClosureVerificationError(
                "Un gain d'action inclut une simulation où l'action n'a pas agi."
            )
    summary_by_key = {
        (str(row.get("dossier_id") or ""), str(row.get("action_id") or "")): row
        for row in summary.get("action_results") or []
        if isinstance(row, Mapping)
    }
    if len(summary_by_key) != len(summary.get("action_results") or []):
        raise ClosureVerificationError("Résultat d'action dupliqué ou sans identité.")
    for action in presentation_actions:
        key = (
            str(action.get("dossier_id") or ""),
            str(action.get("action_id") or ""),
        )
        source = summary_by_key.get(key)
        if source is None:
            raise ClosureVerificationError("Action affichée absente du résumé signé.")
        exercised_count = int(source.get("physically_exercised_seed_count") or 0)
        available_metrics = [
            row
            for row in action.get("metrics") or []
            if isinstance(row, Mapping) and row.get("available") is True
        ]
        signed_gains = source.get("gain_statistics") or {}
        if available_metrics and (
            exercised_count <= 0
            or source.get("status") != "estimated_on_physically_exercised_seeds"
        ):
            raise ClosureVerificationError(
                "Un gain est affiché avant preuve d'exercice physique de l'action."
            )
        if exercised_count == 0 and (available_metrics or signed_gains):
            raise ClosureVerificationError(
                "Une action non exercée porte encore un gain affichable."
            )
        for metric in signed_gains.values():
            if not isinstance(metric, Mapping):
                raise ClosureVerificationError("Statistique de gain d'action invalide.")
            count = int(metric.get("count") or 0)
            if count <= 0 or count > exercised_count:
                raise ClosureVerificationError(
                    "La population d'un gain dépasse les actions physiquement exercées."
                )


def _action_evidence(context: FinalContext) -> CheckEvidence:
    selected = _selection(context.paths)
    declared = _declared_result(context.status, "actions")
    if not selected:
        forbidden = (
            "action_replay_plan.json",
            "action_replay_run_receipt.json",
            "action_replay_summary.json",
            "action_replay_validation.json",
        )
        if any(
            (context.paths.action_replay_root / name).exists() for name in forbidden
        ):
            raise ClosureVerificationError(
                "Des sorties action existent sans dossier signé à analyser."
            )
        expected = {
            "status": "not_run_no_signed_dossier",
            "eligible_action_ids": [],
            "open_loop": True,
            "engine_arm_count": 0,
        }
        if dict(declared) != expected:
            raise ClosureVerificationError("Le statut sans action ne se revalide pas.")
        return CheckEvidence(
            details={
                "status": expected["status"],
                "open_loop": True,
                "physically_exercised_gain_count": 0,
            },
            value={"summary": None, "validation": None},
        )

    with common.v8_consumer_bindings():
        summary, validation = actions_v4.validate_action_results(
            context.paths.action_replay_root
        )
    presentation, _sources = delivery_v3.collect_payload(context.paths)
    presentation_actions = (presentation.get("actions") or {}).get("actions") or []
    applications = _read_csv(
        context.paths.action_replay_root / "action_replay_application_ledger.csv"
    )
    _assert_action_gain_contract(summary, applications, presentation_actions)
    with common.v8_consumer_bindings():
        plan = actions_v4.load_and_validate_plan(context.paths.action_replay_root)
    receipt = _read_json(
        context.paths.action_replay_root / "action_replay_run_receipt.json"
    )
    actions_v4._verify_signed(  # noqa: SLF001
        receipt, "run_signature", "reçu d'actions de la clôture"
    )
    eligible = sorted(
        {
            str(action_id)
            for dossier in plan.get("dossiers") or []
            for action_id in dossier.get("eligible_action_ids") or []
        }
    )
    expected = {
        "status": validation["status"],
        "eligible_action_ids": eligible,
        "open_loop": True,
        "engine_arm_count": int(receipt.get("planned_action_arm_count") or 0),
        "reference_engine_rerun_count": 0,
        "summary_signature": summary["summary_signature"],
        "validation_signature": validation["validation_signature"],
    }
    if dict(declared) != expected:
        raise ClosureVerificationError(
            "Les sorties actions diffèrent du résultat final Stage3 V3."
        )
    exercised = sum(
        int(row.get("physically_exercised_seed_count") or 0)
        for row in summary.get("action_results") or []
    )
    return CheckEvidence(
        details={
            "status": validation["status"],
            "open_loop": True,
            "eligible_action_ids": eligible,
            "physically_exercised_seed_action_pairs": exercised,
            "displayed_action_count": len(presentation_actions),
            "gain_population_restricted_to_exercised_actions": True,
            "summary_signature": summary["summary_signature"],
            "validation_signature": validation["validation_signature"],
        },
        value={"summary": summary, "validation": validation},
    )


def _registry_evidence(context: FinalContext) -> CheckEvidence:
    with common.v8_consumer_bindings():
        proof = registry_v6.validate_delivery(context.paths.registry_dir)
    if dict(_declared_result(context.status, "registry")) != proof:
        raise ClosureVerificationError(
            "Le registre incidents/lots diffère du résultat final signé."
        )
    if (
        proof.get("incidentExposureRowCount") != EXPECTED_COUNTS["incident_rows"]
        or int(proof.get("availableDetailedReplayCount") or 0) > 3
    ):
        raise ClosureVerificationError("Le registre incidents/lots est incomplet.")
    return CheckEvidence(
        details={
            "incident_rows": proof["incidentExposureRowCount"],
            "detailed_replay_count": proof["availableDetailedReplayCount"],
            "genealogy_source_row_count": proof["genealogySourceRowCount"],
            "manifest_sha256": proof["manifestSha256"],
        },
        value=proof,
    )


def _assert_html_contract(
    document: str, manifest: Mapping[str, Any], payload: Mapping[str, Any]
) -> None:
    contract = manifest.get("scientific_contract") or {}
    cascade = payload.get("cascade") or {}
    limits = payload.get("limits") or {}
    presentation = payload.get("presentation") or {}
    if (
        '<html lang="fr"' not in document.casefold()
        or document.count('class="view') < 1
        or document.count('class="view') > 3
        or manifest.get("standalone") is not True
        or manifest.get("external_dependency_count") != 0
        or int(manifest.get("view_count") or 0) > 3
        or _EXTERNAL_URL_RE.search(document)
        or "http://" in document.casefold()
        or "https://" in document.casefold()
        or contract.get("campaign_rows") != EXPECTED_COUNTS["campaign_rows"]
        or contract.get("incident_rows") != EXPECTED_COUNTS["incident_rows"]
        or contract.get("maximum_detailed_dossiers") != 3
        or contract.get("quality") is not False
        or contract.get("capacity_or_availability_invented") is not False
        or contract.get("actions_open_loop") is not True
        or contract.get("automatic_regulation") is not False
        or contract.get("multiple_incidents_combined") is not False
        or contract.get("full_dynamic_cascade_claimed") is not False
        or contract.get("clients_aggregated") is not True
        or contract.get("action_lot_trace_available") is not False
        or contract.get("days_recovered_cost_or_roi_claimed") is not False
        or cascade.get("all_incidents_have_lot_trace") is not False
        or cascade.get("full_dynamic_stock_mrp_production_service_cascade_proven")
        is not False
        or limits.get("consequences_depend_on_evolving_network_state") is not True
        or limits.get("automatic_regulation") is not False
        or limits.get("action_control_mode") != "boucle ouverte"
        or limits.get("customers") != "clients agrégés uniquement"
        or limits.get("lots") != "lots simulés uniquement"
        or presentation.get("future_or_placeholder_results_displayed") is not False
    ):
        raise ClosureVerificationError(
            "Le HTML autonome, sa langue, ses trois vues ou ses limites scientifiques "
            "ne respectent plus le contrat final."
        )


def _delivery_evidence(context: FinalContext) -> CheckEvidence:
    proof = delivery_v3.validate_delivery(context.paths)
    if dict(_declared_result(context.status, "delivery")) != proof:
        raise ClosureVerificationError("Le HTML diffère du résultat final signé.")
    payload, _sources = delivery_v3.collect_payload(context.paths)
    manifest_path = Path(str(context.paths.final_html) + ".manifest.json")
    manifest = common.read_json(manifest_path)
    document = context.paths.final_html.read_text(encoding="utf-8")
    _assert_html_contract(document, manifest, payload)
    return CheckEvidence(
        details={
            "html": str(context.paths.final_html),
            "html_sha256": proof["html_sha256"],
            "manifest_signature": proof["manifest_signature"],
            "language": "fr",
            "standalone": True,
            "external_url_count": 0,
            "view_count": proof["view_count"],
            "limits_declared": True,
        },
        value={"proof": proof, "payload": payload, "manifest": manifest},
    )


def _protected_evidence(
    protected: Sequence[tuple[Path, str]],
) -> CheckEvidence:
    rows = []
    for path, expected in protected:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ClosureVerificationError(f"Ancien HTML protégé absent : {resolved}")
        actual = _sha256_file(resolved)
        if actual != expected:
            raise ClosureVerificationError(
                f"Ancien HTML protégé modifié : {resolved} ({actual})"
            )
        rows.append({"path": str(resolved), "sha256": actual, "unchanged": True})
    if len(rows) != 2:
        raise ClosureVerificationError("Deux anciens HTML protégés sont requis.")
    return CheckEvidence(details={"artifacts": rows})


def _business_verdict(
    *,
    technical_ok: bool,
    lots: Mapping[str, Any] | None,
    delivery: Mapping[str, Any] | None,
    registry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    limits = [
        "Clients uniquement agrégés.",
        "La trace de contact lot ne prouve pas une cascade causale complète stock–MRP–production–service.",
        "Les actions sont en boucle ouverte et leur propre généalogie lot n'est pas tracée.",
    ]
    if not technical_ok or lots is None or delivery is None or registry is None:
        return {
            "code": "NON_EVALUABLE_METIER",
            "exploitable": False,
            "dossier_lot_exploitable_count": 0,
            "reason_fr": "La conformité technique doit être rétablie avant lecture métier.",
            "limits_fr": limits,
        }
    qualification = lots.get("qualification") or {}
    payload = delivery.get("payload") or {}
    detailed = {
        str(row.get("dossier_id") or ""): row
        for row in (payload.get("cascade") or {}).get("detailed_replays") or []
        if isinstance(row, Mapping)
    }
    exploitable = []
    for dossier in qualification.get("dossiers") or []:
        if not isinstance(dossier, Mapping):
            continue
        dossier_id = str(dossier.get("dossier_id") or "")
        trace = dossier.get("trace_counts") or {}
        detail = detailed.get(dossier_id) or {}
        identity = (
            dossier.get("supplier_id"),
            dossier.get("item_id"),
            dossier.get("dst_node_id"),
            dossier.get("target_product_id"),
            dossier.get("mechanism"),
        )
        if (
            dossier.get("proof_level") in {"partial", "complete"}
            and int(trace.get("shipments") or 0) > 0
            and int(trace.get("material_receipts") or 0) > 0
            and all(str(value or "").strip() for value in identity)
            and isinstance(detail.get("genealogy_rows"), list)
            and len(detail["genealogy_rows"]) > 0
        ):
            exploitable.append(
                {
                    "dossier_id": dossier_id,
                    "supplier_id": str(dossier["supplier_id"]),
                    "item_id": str(dossier["item_id"]),
                    "mechanism": str(dossier["mechanism"]),
                    "proof_level": str(dossier["proof_level"]),
                    "trace_counts": dict(trace),
                    "genealogy_row_count": len(detail["genealogy_rows"]),
                }
            )
    declared = int(registry.get("availableDetailedReplayCount") or 0)
    if declared != len(detailed):
        return {
            "code": "INSUFFISANT_METIER",
            "exploitable": False,
            "dossier_lot_exploitable_count": 0,
            "reason_fr": "Le nombre de dossiers détaillés du registre et du HTML diffère.",
            "limits_fr": limits,
        }
    if not exploitable:
        return {
            "code": "INSUFFISANT_METIER",
            "exploitable": False,
            "dossier_lot_exploitable_count": 0,
            "reason_fr": (
                "Aucun dossier ne permet encore de suivre une expédition touchée "
                "jusqu'à un lot matière dans la généalogie embarquée."
            ),
            "limits_fr": limits,
        }
    return {
        "code": "EXPLOITABLE_METIER_AVEC_LIMITES",
        "exploitable": True,
        "dossier_lot_exploitable_count": len(exploitable),
        "dossiers": exploitable,
        "reason_fr": (
            "Au moins un dossier signé relie un incident fournisseur exercé à des "
            "lots simulés consultables ; la profondeur exacte reste affichée dossier par dossier."
        ),
        "limits_fr": limits,
    }


def build_closure_report(
    context: FinalContext,
    *,
    protected: Sequence[tuple[Path, str]] = PROTECTED_HTML,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    values: dict[str, Any] = {}

    def run(
        check_id: str, label_fr: str, operation: Callable[[], CheckEvidence]
    ) -> None:
        try:
            evidence = operation()
        except Exception as exc:  # fail-closed report, sans masquer l'échec
            checks.append(
                {
                    "id": check_id,
                    "label_fr": label_fr,
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "error_fr": str(exc),
                }
            )
            return
        checks.append(
            {
                "id": check_id,
                "label_fr": label_fr,
                "passed": True,
                "evidence": evidence.details,
            }
        )
        values[check_id] = evidence.value

    run(
        "contract",
        "Contrat et état final Stage3 V3",
        lambda: _contract_evidence(context),
    )
    run(
        "campaign",
        "Matrice 3 330 cas et preuves physiques signées",
        lambda: _campaign_evidence(context.paths),
    )
    run("curves", "Courbes nominales et manifeste", lambda: _curve_evidence(context))
    run(
        "lots",
        "Rejeux lots et qualification de profondeur",
        lambda: _lot_and_qualification_evidence(context),
    )
    run(
        "actions",
        "Actions en boucle ouverte et gains exercés",
        lambda: _action_evidence(context),
    )
    run(
        "registry",
        "Registre incidents, lots et artefacts",
        lambda: _registry_evidence(context),
    )
    run(
        "delivery",
        "HTML autonome français, trois vues maximum",
        lambda: _delivery_evidence(context),
    )
    run("legacy", "Anciens HTML inchangés", lambda: _protected_evidence(protected))

    technical_ok = all(row["passed"] for row in checks)
    technical = {
        "code": "CONFORME_TECHNIQUE" if technical_ok else "NON_CONFORME_TECHNIQUE",
        "conforme": technical_ok,
        "check_count": len(checks),
        "passed_check_count": sum(row["passed"] for row in checks),
        "checks": checks,
    }
    business = _business_verdict(
        technical_ok=technical_ok,
        lots=values.get("lots"),
        delivery=values.get("delivery"),
        registry=values.get("registry"),
    )
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_audited",
        "scope": "supplier_v8_v2_and_stage3_v3_final_outputs_only",
        "no_simulation_engine_started": True,
        "source": {
            "supervision_dir": str(context.paths.supervision_dir),
            "contract_signature": context.contract["contract_signature"],
            "status_signature": context.status["status_signature"],
            "final_html": str(context.paths.final_html),
        },
        "technical_verdict": technical,
        "business_verdict": business,
    }
    return {**unsigned, "closure_signature": _stable_sha256(unsigned)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--supervision-dir",
        type=Path,
        required=True,
        help="Supervision Stage3 V3 terminée contenant le contrat et le statut signés.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Nouveau fichier JSON dans un dossier d'audit séparé.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        context = load_final_context(args.supervision_dir)
        _assert_output_separation(args.output_json, context.paths)
        report = build_closure_report(context)
        publish_new_or_identical(args.output_json, report)
    except ClosureNotFinal as exc:
        print(f"CLÔTURE NON EXÉCUTÉE : {exc}", file=sys.stderr)
        return 4
    except Exception as exc:
        print(f"ÉCHEC DU VÉRIFICATEUR DE CLÔTURE : {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "technical_verdict": report["technical_verdict"]["code"],
                "business_verdict": report["business_verdict"]["code"],
                "output_json": str(args.output_json.resolve()),
                "closure_signature": report["closure_signature"],
            },
            ensure_ascii=False,
        )
    )
    if not report["technical_verdict"]["conforme"]:
        return 2
    return 0 if report["business_verdict"]["exploitable"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
