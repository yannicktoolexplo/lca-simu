#!/usr/bin/env python3
"""Execute the additive, resumable V7 lot/action/delivery stage after stage 1."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as actions_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lots_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_full_incident_lot_registry as registry_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_curves as curves_v7,
)


SCHEMA_VERSION = "etudecas.supplier_v7_stage2_pipeline.v1"
CONTRACT_NAME = "stage2_contract.json"
INVENTORY_NAME = "stage2_source_inventory.json"
STATUS_NAME = "status.json"
UPSTREAM_NAME = common.STAGE1_RECEIPT_NAME


class Stage2PipelineError(common.Stage2Error):
    """The resumable stage-2 pipeline cannot preserve its evidence contract."""


def _status_payload(
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
            "at_utc": common.utc_now(),
            "status": status,
            "step": step,
            "message_fr": message_fr,
        }
    )
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.status.v1",
        "contract_signature": contract_signature,
        "status": status,
        "step": step,
        "message_fr": message_fr,
        "pid": os.getpid(),
        "updated_at_utc": common.utc_now(),
        "history": history,
        **dict(extra or {}),
    }
    return common.signed(unsigned, "status_signature")


def _verify_status(path: Path, contract_signature: str) -> dict[str, Any]:
    payload = common.read_json(path)
    common.verify_signature(payload, "status_signature", "statut étape 2")
    if (
        payload.get("schema_version") != f"{SCHEMA_VERSION}.status.v1"
        or payload.get("contract_signature") != contract_signature
    ):
        raise Stage2PipelineError("Le statut appartient à un autre contrat étape 2")
    return payload


def _contract_payload(
    paths: common.Stage2Paths, inventory: Mapping[str, Any]
) -> dict[str, Any]:
    observed = common.validate_observed_2025_pack(paths.observed_2025_dir)
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.contract.v1",
        "paths": paths.mapping(),
        "source_inventory_signature": inventory["inventory_signature"],
        "scientific_contract": {
            "stage1_required_status": "accepted_450_then_complete_3330",
            "detailed_dossier_maximum": 3,
            "detailed_replay_arms": ["baseline", "incident_without_action"],
            "incident_mechanisms": list(common.EXPECTED_MECHANISMS),
            "quality_incident_included": False,
            "capacity_or_availability_invented": False,
            "state_dependent_consequences": True,
            "incident_generation": "exogenous_conditional_hypothesis",
            "action_ids": list(common.ALLOWED_ACTIONS),
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
    return common.signed(unsigned, "contract_signature")


def validate_bound_contract(
    paths: common.Stage2Paths,
    *,
    expected_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Revalidate code, observed context, paths, and their immutable contract."""

    paths = paths.resolved()
    paths.validate_separation()
    inventory = common.read_json(paths.supervision_dir / INVENTORY_NAME)
    common.verify_source_inventory(inventory)
    contract = common.read_json(paths.supervision_dir / CONTRACT_NAME)
    common.verify_signature(contract, "contract_signature", "contrat étape 2")
    if expected_contract is not None and contract != dict(expected_contract):
        raise Stage2PipelineError("Le contrat étape 2 a été remplacé")
    if contract != _contract_payload(paths, inventory):
        raise Stage2PipelineError(
            "Une source liée au contrat étape 2 a changé depuis l'armement"
        )
    return contract


def prepare_supervision(paths: common.Stage2Paths) -> dict[str, Any]:
    """Create/validate only the supervision directory; never touch stage outputs."""

    paths = paths.resolved()
    paths.validate_separation()
    root = paths.supervision_dir
    contract_path = root / CONTRACT_NAME
    status_path = root / STATUS_NAME
    if contract_path.is_file():
        contract = validate_bound_contract(paths)
        _verify_status(status_path, contract["contract_signature"])
        return contract
    if root.exists() and any(root.iterdir()):
        raise Stage2PipelineError("Supervision étape 2 préexistante non reconnue")
    for output in (*paths.output_roots[:-1], *paths.output_files):
        if output.exists():
            raise Stage2PipelineError(
                f"Une sortie étape 2 existe avant son contrat : {output}"
            )
    inventory = common.build_source_inventory(paths.repo)
    contract = _contract_payload(paths, inventory)
    stage = root.with_name(f".{root.name}.stage2-{os.getpid()}-{os.urandom(8).hex()}")
    try:
        stage.mkdir(parents=True, exist_ok=False)
        (stage / INVENTORY_NAME).write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        (stage / CONTRACT_NAME).write_text(
            json.dumps(contract, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        initial = _status_payload(
            contract["contract_signature"],
            status="armed_waiting_for_stage1",
            step="attente_etape_1",
            message_fr="Watcher étape 2 armé; aucune sortie aval créée.",
        )
        (stage / STATUS_NAME).write_text(
            json.dumps(initial, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(stage, root)
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    return contract


def _selection(results_dir: Path) -> list[dict[str, Any]]:
    path = results_dir.resolve() / "lot_replay_plan.json"
    payload = common.read_json(path)
    lots_v4._verify_signed_payload(  # noqa: SLF001
        payload, "selection_signature", "sélection signée des dossiers lots"
    )
    rows = payload.get("selected_dossiers")
    if (
        payload.get("status") != "complete_selected"
        or not isinstance(rows, list)
        or len(rows) > common.MAX_DETAILED_DOSSIERS
        or int(payload.get("selection_contract", {}).get("maximum_dossiers") or -1)
        != common.MAX_DETAILED_DOSSIERS
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


def _archive_owned_partial(root: Path, candidate: Path, label: str) -> Path:
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
        recovery / f"{label}.{common.utc_now().replace(':', '').replace('+', '_')}"
    )
    suffix = 1
    while destination.exists():
        destination = recovery / f"{destination.name}.{suffix}"
        suffix += 1
    candidate.replace(destination)
    return destination


def _archive_owned_unplanned_root(
    paths: common.Stage2Paths, candidate: Path, label: str
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
        raise Stage2PipelineError("Racine partielle non vide hors sorties possédées")
    recovery = paths.supervision_dir.resolve() / "recovery" / "partial_plans"
    if common.paths_overlap(recovery, candidate) or any(
        common.paths_overlap(recovery, source) for source in paths.upstream_paths
    ):
        raise Stage2PipelineError("Archive de reprise hors périmètre étape 2")
    recovery.mkdir(parents=True, exist_ok=True)
    timestamp = common.utc_now().replace(":", "").replace("+", "_")
    destination = recovery / f"{label}.{timestamp}"
    suffix = 1
    while destination.exists():
        destination = recovery / f"{label}.{timestamp}.{suffix}"
        suffix += 1
    candidate.replace(destination)
    return destination


def _lot_receipt_valid(root: Path, plan: Mapping[str, Any]) -> dict[str, Any] | None:
    path = root / "replay_run_receipt.json"
    if not path.is_file():
        return None
    receipt = common.read_json(path)
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
        raise Stage2PipelineError("Le reçu des rejeux lots ne correspond plus aux bras")
    return receipt


def _run_lot_replays(
    paths: common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
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
                _archive_owned_unplanned_root(
                    paths, paths.lot_replay_root, "lot_replay_plan"
                )
        plan = lots_v4.create_replay_plan(
            campaign_root=paths.campaign_root,
            results_dir=paths.results_dir,
            output_root=paths.lot_replay_root,
            max_dossiers=common.MAX_DETAILED_DOSSIERS,
            selection_csv=None,
        )
    dossiers = plan.get("dossiers") or []
    if len(dossiers) != len(selection) or len(dossiers) > common.MAX_DETAILED_DOSSIERS:
        raise Stage2PipelineError(
            "Le plan de rejeu ne conserve pas la sélection signée"
        )
    receipt = _lot_receipt_valid(paths.lot_replay_root, plan)
    if receipt is None:
        results = []
        for dossier in dossiers:
            dossier_id = str(dossier["dossier_id"])
            for arm in ("baseline", "incident"):
                run_dir = Path(str(dossier["arms"][arm]["run_dir"])).resolve()
                proof = None
                if run_dir.exists():
                    try:
                        proof = lots_v4.validate_arm(run_dir, dossier=dossier, arm=arm)
                    except lots_v4.ReplayContractError:
                        _archive_owned_partial(
                            paths.lot_replay_root, run_dir, f"{dossier_id}__{arm}"
                        )
                if proof is None:
                    log = paths.lot_replay_root / "logs" / f"{dossier_id}__{arm}.log"
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
            "created_at_utc": common.utc_now(),
            "plan_signature": plan["plan_signature"],
            "arms": results,
        }
        receipt = {
            **unsigned,
            "run_receipt_signature": lots_v4.stable_sha256(unsigned),
        }
        common.publish_new_or_identical(
            paths.lot_replay_root / "replay_run_receipt.json",
            (
                json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8"),
        )
        receipt = _lot_receipt_valid(paths.lot_replay_root, plan)
    assert receipt is not None
    validation_path = paths.lot_replay_root / "finalized" / "replay_validation.json"
    if validation_path.is_file():
        validation = _validate_finalized_lots(paths.lot_replay_root, plan)
    else:
        final_root = paths.lot_replay_root / "finalized"
        standalone = paths.lot_replay_root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html"
        if final_root.exists() or standalone.exists():
            if final_root.exists():
                _archive_owned_partial(paths.lot_replay_root, final_root, "finalized")
            if standalone.exists():
                _archive_owned_partial(paths.lot_replay_root, standalone, "standalone")
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
    replay_root: Path, plan: Mapping[str, Any]
) -> dict[str, Any]:
    """Revalidate an immutable V4 finalization without asking V4 to overwrite it."""

    final_root = replay_root / "finalized"
    validation_path = final_root / "replay_validation.json"
    validation = common.read_json(validation_path)
    lots_v4._verify_signed_payload(  # noqa: SLF001
        validation, "validation_signature", "validation finale des lots"
    )
    receipt = common.read_json(replay_root / "replay_run_receipt.json")
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
        or common.sha256_file(inventory_path)
        != str(validation.get("artifact_inventory_sha256") or "")
        or not html_path.is_relative_to(replay_root.resolve())
        or not html_path.is_file()
        or common.sha256_file(html_path)
        != str(validation.get("standalone_html_sha256") or "")
    ):
        raise Stage2PipelineError("La finalisation existante des lots est invalide")
    inventory = common._read_csv(inventory_path)  # noqa: SLF001
    for row in inventory:
        artifact = (replay_root / str(row.get("relative_path") or "")).resolve()
        if (
            not artifact.is_relative_to(replay_root.resolve())
            or not artifact.is_file()
            or artifact.stat().st_size != int(row.get("size_bytes") or -1)
            or common.sha256_file(artifact) != str(row.get("sha256") or "")
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
        raise Stage2PipelineError("La finalisation ne couvre pas les dossiers signés")
    for dossier in plan.get("dossiers") or []:
        for arm in ("baseline", "incident"):
            lots_v4.validate_arm(
                Path(str(dossier["arms"][arm]["run_dir"])), dossier=dossier, arm=arm
            )
        lots_v4._validate_pair(dossier)  # noqa: SLF001
    return validation


def _qualify(
    paths: common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
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
        raise Stage2PipelineError("La portée physique des cascades n'est pas qualifiée")
    return {
        "status": payload["status"],
        "qualification_signature": payload["qualification_signature"],
        "selected_dossier_count": len(selection),
        "full_dynamic_cascade_claimed": False,
    }


def _run_actions(
    paths: common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
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
            _archive_owned_unplanned_root(
                paths, paths.action_replay_root, "action_replay_plan"
            )
    plan = actions_v4.create_action_plan(
        campaign_root=paths.campaign_root,
        results_dir=paths.results_dir,
        output_root=paths.action_replay_root,
        lot_replay_root=paths.lot_replay_root,
        max_dossiers=common.MAX_DETAILED_DOSSIERS,
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
        not set(eligible).issubset(common.ALLOWED_ACTIONS)
        or plan.get("scientific_contract", {}).get("closed_loop_claimed") is not False
        or plan.get("scientific_contract", {}).get("reference_engine_reruns") != 0
        or plan.get("scientific_contract", {}).get("availability_or_capacity_invented")
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
    summary, validation = actions_v4.finalize_action_replay(paths.action_replay_root)
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
    paths: common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
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
        != common.EXPECTED_INCIDENTS
        or int(result.get("availableDetailedReplayCount") or 0) != len(selection)
    ):
        raise Stage2PipelineError("Le registre 3 240 incidents + lots est incomplet")
    return dict(result)


def _delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_delivery as delivery,
    )

    return delivery.build_delivery(paths)


class Stage2Pipeline:
    def __init__(self, paths: common.Stage2Paths):
        self.paths = paths.resolved()
        self.contract = prepare_supervision(self.paths)
        self.inventory = common.read_json(self.paths.supervision_dir / INVENTORY_NAME)
        self.status_path = self.paths.supervision_dir / STATUS_NAME
        self.status = _verify_status(
            self.status_path, str(self.contract["contract_signature"])
        )

    def update(self, status: str, step: str, message_fr: str, **extra: Any) -> None:
        self.status = _status_payload(
            str(self.contract["contract_signature"]),
            status=status,
            step=step,
            message_fr=message_fr,
            previous=self.status,
            extra=extra,
        )
        common.atomic_write_json(self.status_path, self.status)

    def guard(self) -> None:
        validate_bound_contract(self.paths, expected_contract=self.contract)
        upstream_receipt = self.paths.supervision_dir / UPSTREAM_NAME
        if upstream_receipt.is_file():
            common.validate_bound_stage1_receipt(self.paths, upstream_receipt)

    def execute(self) -> int:
        self.guard()
        if common.probe_stage1(self.paths) != "accepted_stage1_complete":
            raise common.Stage2NotReady("L'étape 1 n'est pas encore complète")
        upstream = common.validate_complete_stage1(self.paths)
        common.publish_new_or_identical(
            self.paths.supervision_dir / UPSTREAM_NAME,
            (
                json.dumps(upstream, ensure_ascii=False, indent=2, allow_nan=False)
                + "\n"
            ).encode("utf-8"),
        )
        self.guard()
        self.update(
            "running",
            "validation_etape_1",
            (
                "450 cas de validation et la matrice de campagne "
                "(90 références + 3 240 incidents) revalidés."
            ),
            upstream_validation_signature=upstream["validation_signature"],
        )
        selection = _selection(self.paths.results_dir)

        self.guard()
        self.update(
            "running", "courbes", "Construction des courbes nominales 28 j / 7 j."
        )
        curve_result = curves_v7.build_curve_package(
            self.paths.v7_plan_dir, self.paths.v7_run_dir, self.paths.curves_dir
        )

        self.guard()
        self.update(
            "running",
            "lots",
            "Rejeux détaillés baseline + incident, au plus trois dossiers.",
        )
        with common.v7_consumer_bindings():
            lot_result = _run_lot_replays(self.paths, selection)

        self.guard()
        self.update(
            "running",
            "qualification",
            "Qualification honnête de la propagation physique.",
        )
        with common.v7_consumer_bindings():
            qualification = _qualify(self.paths, selection)

        self.guard()
        self.update(
            "running", "actions", "Test des seuls leviers pilotables en boucle ouverte."
        )
        with common.v7_consumer_bindings():
            action_result = _run_actions(self.paths, selection)

        self.guard()
        self.update(
            "running",
            "registre",
            "Consolidation des 3 240 incidents et des lots disponibles.",
        )
        with common.v7_consumer_bindings():
            registry = _registry(self.paths, selection)

        self.guard()
        self.update(
            "running", "html", "Construction du parcours client autonome en trois vues."
        )
        delivery = _delivery(self.paths)
        self.guard()
        self.update(
            "complete",
            "termine",
            "Étape 2 V7 terminée et revalidée.",
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


def add_path_arguments(parser: argparse.ArgumentParser) -> None:
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


def paths_from_args(args: argparse.Namespace) -> common.Stage2Paths:
    return common.Stage2Paths(
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_path_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    paths = paths_from_args(args)
    relay = None
    try:
        # The immutable contract must exist before the lock file is created inside
        # the supervision directory; otherwise a first invocation would mistake
        # its own lock for an unknown pre-existing artifact.
        prepare_supervision(paths)
        with common.exclusive_lock(paths.supervision_dir / ".stage2.lock"):
            relay = Stage2Pipeline(paths)
            return relay.execute()
    except common.Stage2ScientificNoGo as exc:
        if relay is not None:
            relay.update("scientific_no_go", "arret", str(exc))
        print(f"ÉTAPE 2 ARRÊT SCIENTIFIQUE : {exc}", file=sys.stderr)
        return 3
    except common.Stage2NotReady as exc:
        if relay is not None:
            relay.update("waiting", "attente_etape_1", str(exc))
        print(f"ÉTAPE 2 EN ATTENTE : {exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        if relay is not None:
            relay.update(
                "interrupted_resumable",
                "interrompu",
                "Reprise possible avec le même contrat.",
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
        print(f"ÉTAPE 2 EN ÉCHEC : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
