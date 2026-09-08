#!/usr/bin/env python3
"""Build conservative action-selector inputs from a stabilized network V2.

The generator is additive.  It does not run the selector or the simulation,
does not modify its source audits, and never upgrades missing operational data
to evidence.  The output is a technical action catalogue plus an explicit
prerequisite-evidence snapshot ready for review by the industrial teams.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_v2_controllable_action_selector as selector,
)


SCHEMA_VERSION = "etudecas.supplier_v2_action_input_generator.v2"
CATALOG_FILE = "action_eligibility_catalog.csv"
PREREQUISITE_FILE = "operational_prerequisites.csv"
MANIFEST_FILE = "action_input_manifest.json"

ALLOWED_ACTION_IDS = tuple(selector.ACTION_POLICIES)

ACTION_LABELS = {
    "targeted_transport_after_observed_delay": ("Transport ciblé après retard observé"),
    "prepositioned_free_stock": "Stock libre prépositionné avant l'incident",
    "post_release_transport_for_identified_lot": (
        "Transport après libération qualité d'un lot identifié"
    ),
    "prepared_qualified_alternative_source": (
        "Source alternative existante à préparer et qualifier"
    ),
}

TECHNICAL_REPRESENTATIONS = {
    "targeted_transport_after_observed_delay": (
        "calendrier_exogene_cible; aucun pilotage automatique en boucle fermée"
    ),
    "prepositioned_free_stock": (
        "état_initial_au_début_de_mesure; aucune injection de stock pendant l'incident"
    ),
    "post_release_transport_for_identified_lot": (
        "réduction_du_transport_restant; aucune réduction de la retenue qualité"
    ),
    "prepared_qualified_alternative_source": (
        "pondération_d'une_voie_existante_active; aucune création de fournisseur"
    ),
}

PREREQUISITE_DESCRIPTIONS = {
    "shipment_identified_not_delivered": (
        "Expédition nommée, partie ou réservée, et non encore livrée."
    ),
    "route_change_feasible": "Itinéraire de remplacement physiquement faisable.",
    "carrier_capacity_confirmed": "Capacité transport datée et confirmée.",
    "transit_gain_committed": "Gain de transit positif, chiffré et engagé.",
    "dated_cost_basis": "Coût daté et applicable à l'expédition visée.",
    "lane_scoped_detection_signal_available": (
        "Signal causal fournisseur–article–site disponible sans connaissance du futur."
    ),
    "stock_build_source_identified": (
        "Origine physique et financement de la constitution du stock identifiés."
    ),
    "available_before_incident": "Stock disponible avant la période de risque.",
    "released_free_stock_confirmed": (
        "Quantité réellement libre, libérée, non allouée et non périmée."
    ),
    "quantity_and_uom_confirmed": "Quantité physique et unité confirmées.",
    "shelf_life_storage_finance_approved": (
        "Durée de vie, stockage et financement approuvés."
    ),
    "initial_state_parameterization_audited": (
        "Correspondance auditée entre le stock physique et l'état initial simulé."
    ),
    "released_lot_identified": "Lot identifié et libéré par la qualité.",
    "quality_release_observed": "Décision de libération qualité observée et datée.",
    "shipment_not_delivered": "Transport aval du lot non encore terminé.",
    "supplier_material_qualification_valid": (
        "Qualification fournisseur–matière–site valide à la date de décision."
    ),
    "alternative_lane_positive_v2_flow": (
        "Voie alternative existante avec flux positif dans le périmètre réseau V2."
    ),
    "capacity_quantity_committed": (
        "Capacité alternative positive, datée, engagée et exprimée avec son unité."
    ),
    "lead_time_moq_contract_confirmed": (
        "Délai réel, minimum de commande et conditions contractuelles confirmés."
    ),
    "quality_and_transport_route_approved": (
        "Équivalence qualité et route logistique approuvées."
    ),
    "existing_lane_weight_parameterization_audited": (
        "Paramétrage de répartition sur la voie existante audité."
    ),
}

CATALOG_FIELDS = (
    "lane_key",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "downstream_products",
    "network_chain_ids",
    "supplier_priority_rank",
    "lane_sensitivity_rank",
    "failure_mode",
    "action_id",
    "action_label",
    "incident_family",
    "action_phase",
    "native_engine_actuator",
    "native_actuator_available",
    "technical_representation",
    "technical_contract_reference",
    "baseline_positive_flow",
    "baseline_shipped_qty",
    "structural_alternative_count",
    "active_alternative_count",
    "qualified_active_alternative_count",
    "structural_alternative_suppliers",
    "active_alternative_suppliers",
    "qualified_active_alternative_suppliers",
    "simulation_execution_allowed",
    "eligibility_status",
    "refusal_reason",
    "operational_prerequisites_verified",
    "evidence_stage",
    "not_a_recommendation",
)

PREREQUISITE_FIELDS = (
    "lane_key",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "action_id",
    "prerequisite_id",
    "status",
    "evidence_reference",
    "value",
    "uom",
    "required_evidence_description",
    "assessment_reason",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui"}


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(
    path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]
) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_hashes(directory: Path, names: Sequence[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in names:
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"Source requise absente: {path}")
        hashes[name] = _sha256(path)
    return hashes


def _lane_key(row: Mapping[str, object]) -> str:
    return "|".join(
        (
            str(row.get("supplier_id") or "").strip(),
            str(row.get("item_id") or "").strip(),
            str(row.get("dst_node_id") or "").strip(),
        )
    )


def _validate_audits(
    *, scope_manifest: Mapping[str, object], source_manifest: Mapping[str, object]
) -> None:
    if str(scope_manifest.get("status") or "") != "complete":
        raise ValueError("L'audit de périmètre fournisseur doit être complet.")
    if str(source_manifest.get("status") or "") != "complete":
        raise ValueError("L'audit des champs source doit être complet.")
    if str(source_manifest.get("audit_mode") or "") != "read_only_no_simulation":
        raise ValueError(
            "L'audit des champs source doit être explicitement en lecture seule."
        )


def _priority_lanes(
    *,
    network_dir: Path,
    priority_supplier_ids: Sequence[str],
    priority_chain_ids: Sequence[str] = (),
    scope_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, object]], set[str]]:
    lane_rows = _read_csv(network_dir / "lane_sensitivity_ranking.csv")
    for row in lane_rows:
        if any(
            not str(row.get(field) or "").strip()
            for field in ("supplier_id", "item_id", "dst_node_id")
        ):
            raise ValueError("Le classement V2 contient une voie incomplète.")
    all_network_lane_keys = {_lane_key(row) for row in lane_rows}
    required_chain_ids = {str(value).strip() for value in priority_chain_ids} - {""}
    if required_chain_ids:
        available_chain_ids = {
            str(row.get("chain_id") or "").strip() for row in lane_rows
        } - {""}
        if not required_chain_ids <= available_chain_ids:
            missing = sorted(required_chain_ids - available_chain_ids)
            raise ValueError(
                "Voies V3 signees absentes du classement reseau: " + ", ".join(missing)
            )
        lane_rows = [
            row
            for row in lane_rows
            if str(row.get("chain_id") or "").strip() in required_chain_ids
        ]
    scope_by_key: dict[str, Mapping[str, str]] = {}
    for row in scope_rows:
        key = _lane_key(row)
        incomplete = any(
            not str(row.get(field) or "").strip()
            for field in ("supplier_id", "item_id", "dst_node_id")
        )
        if incomplete or key in scope_by_key:
            raise ValueError(
                f"Voie absente, incomplète ou dupliquée dans l'audit: {key}"
            )
        scope_by_key[key] = row

    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    priority_set = set(priority_supplier_ids)
    for row in lane_rows:
        if str(row.get("supplier_id") or "") in priority_set:
            grouped[_lane_key(row)].append(row)
    if not grouped:
        raise ValueError("Aucune voie du classement ne correspond aux priorités V2.")

    output: list[dict[str, object]] = []
    suppliers_with_lanes: set[str] = set()
    for key, rows in sorted(grouped.items()):
        scope = scope_by_key.get(key)
        if scope is None:
            raise ValueError(f"Voie prioritaire absente de l'audit de périmètre: {key}")
        if not _truthy(scope.get("baseline_positive_flow")):
            raise ValueError(f"Voie prioritaire sans flux positif audité: {key}")
        suppliers_with_lanes.add(str(scope.get("supplier_id") or ""))
        output.append(
            {
                **scope,
                "lane_key": key,
                "network_chain_ids": "|".join(
                    sorted({str(row.get("chain_id") or "") for row in rows})
                ),
                "lane_sensitivity_rank": (
                    ""
                    if required_chain_ids
                    else min(
                        _integer(row.get("lane_sensitivity_rank"), 999) for row in rows
                    )
                ),
            }
        )
    if suppliers_with_lanes != priority_set:
        missing = sorted(priority_set - suppliers_with_lanes)
        raise ValueError("Priorités sans voie réseau: " + ", ".join(missing))
    selected_chain_ids = {
        chain_id
        for row in output
        for chain_id in str(row.get("network_chain_ids") or "").split("|")
        if chain_id
    }
    if required_chain_ids and selected_chain_ids != required_chain_ids:
        raise ValueError("La selection de voies ne reproduit pas les quatre voies V3.")
    return output, all_network_lane_keys


def _alternatives(
    *,
    lane: Mapping[str, object],
    scope_rows: Sequence[Mapping[str, str]],
    all_network_lane_keys: set[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    supplier = str(lane.get("supplier_id") or "")
    item = str(lane.get("item_id") or "")
    destination = str(lane.get("dst_node_id") or "")
    candidates = [
        row
        for row in scope_rows
        if str(row.get("supplier_id") or "") != supplier
        and str(row.get("item_id") or "") == item
        and str(row.get("dst_node_id") or "") == destination
    ]
    structural = tuple(
        sorted({str(row.get("supplier_id") or "") for row in candidates})
    )
    active = tuple(
        sorted(
            {
                str(row.get("supplier_id") or "")
                for row in candidates
                if _truthy(row.get("baseline_positive_flow"))
                and _lane_key(row) in all_network_lane_keys
            }
        )
    )
    return structural, active


def _incident_family(policy: Mapping[str, object], failure_mode: str) -> str:
    by_mode = policy.get("incident_family_by_mode")
    if isinstance(by_mode, Mapping):
        return str(by_mode.get(failure_mode) or "")
    return str(policy.get("incident_family") or "")


def _build_catalog(
    *,
    lanes: Sequence[Mapping[str, object]],
    scope_rows: Sequence[Mapping[str, str]],
    all_network_lane_keys: set[str],
    supplier_ranks: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, tuple[str, ...]]]:
    rows: list[dict[str, object]] = []
    active_alternatives_by_lane: dict[str, tuple[str, ...]] = {}
    for lane in lanes:
        key = str(lane.get("lane_key") or "")
        structural, active = _alternatives(
            lane=lane,
            scope_rows=scope_rows,
            all_network_lane_keys=all_network_lane_keys,
        )
        active_alternatives_by_lane[key] = active
        supplier = str(lane.get("supplier_id") or "")
        for action_id in ALLOWED_ACTION_IDS:
            policy = selector.ACTION_POLICIES[action_id]
            for failure_mode in sorted(policy["failure_modes"]):
                alternative_ready = (
                    action_id != "prepared_qualified_alternative_source" or bool(active)
                )
                technically_allowed = bool(
                    _truthy(lane.get("baseline_positive_flow")) and alternative_ready
                )
                rows.append(
                    {
                        "lane_key": key,
                        "supplier_id": supplier,
                        "item_id": lane.get("item_id"),
                        "dst_node_id": lane.get("dst_node_id"),
                        "downstream_products": lane.get("downstream_products", ""),
                        "network_chain_ids": lane.get("network_chain_ids", ""),
                        "supplier_priority_rank": supplier_ranks[supplier],
                        "lane_sensitivity_rank": lane.get("lane_sensitivity_rank"),
                        "failure_mode": failure_mode,
                        "action_id": action_id,
                        "action_label": ACTION_LABELS[action_id],
                        "incident_family": _incident_family(policy, failure_mode),
                        "action_phase": policy["action_phase"],
                        "native_engine_actuator": policy["native_engine_actuator"],
                        "native_actuator_available": True,
                        "technical_representation": TECHNICAL_REPRESENTATIONS[
                            action_id
                        ],
                        "technical_contract_reference": (
                            "supplier_v2_controllable_action_selector.py#ACTION_POLICIES"
                        ),
                        "baseline_positive_flow": True,
                        "baseline_shipped_qty": lane.get("baseline_shipped_qty", ""),
                        "structural_alternative_count": len(structural),
                        "active_alternative_count": len(active),
                        # Neither source audit identifies a qualified alternative
                        # supplier with committed capacity at lane granularity.
                        "qualified_active_alternative_count": 0,
                        "structural_alternative_suppliers": "|".join(structural),
                        "active_alternative_suppliers": "|".join(active),
                        "qualified_active_alternative_suppliers": "",
                        "simulation_execution_allowed": technically_allowed,
                        "eligibility_status": (
                            "technical_candidate_operational_evidence_pending"
                            if technically_allowed
                            else "blocked_no_existing_active_alternative"
                        ),
                        "refusal_reason": (
                            ""
                            if technically_allowed
                            else "aucune_voie_alternative_active_v2"
                        ),
                        "operational_prerequisites_verified": False,
                        "evidence_stage": "stabilized_network_v2_input_preparation",
                        "not_a_recommendation": True,
                    }
                )
    return rows, active_alternatives_by_lane


def _default_evidence_reference(prerequisite_id: str) -> str:
    if prerequisite_id in {
        "supplier_material_qualification_valid",
        "released_lot_identified",
        "quality_release_observed",
        "quality_and_transport_route_approved",
    }:
        return "source-field-audit:supplier_source_field_inventory.csv#audit_id=missing_quality"
    if prerequisite_id in {
        "capacity_quantity_committed",
        "carrier_capacity_confirmed",
    }:
        return "source-field-audit:supplier_source_field_inventory.csv#audit_id=missing_capacity"
    if prerequisite_id == "lead_time_moq_contract_confirmed":
        return (
            "source-field-audit:manifest.json#summary."
            "fia_lead_time_is_forecast_not_actual=true"
        )
    return "source-field-audit:manifest.json#operational_lane_evidence_not_available"


def _build_prerequisites(
    *,
    lanes: Sequence[Mapping[str, object]],
    active_alternatives_by_lane: Mapping[str, tuple[str, ...]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for lane in lanes:
        key = str(lane.get("lane_key") or "")
        for action_id in ALLOWED_ACTION_IDS:
            policy = selector.ACTION_POLICIES[action_id]
            for prerequisite_id in policy["required_prerequisites"]:
                alternatives = active_alternatives_by_lane.get(key, ())
                verified = bool(
                    prerequisite_id == "alternative_lane_positive_v2_flow"
                    and alternatives
                )
                rows.append(
                    {
                        "lane_key": key,
                        "supplier_id": lane.get("supplier_id"),
                        "item_id": lane.get("item_id"),
                        "dst_node_id": lane.get("dst_node_id"),
                        "action_id": action_id,
                        "prerequisite_id": prerequisite_id,
                        "status": "verified" if verified else "not_verified",
                        "evidence_reference": (
                            "scope-audit:supplier_lane_scope.csv+"
                            "network-results:lane_sensitivity_ranking.csv#"
                            + "|".join(alternatives)
                            if verified
                            else _default_evidence_reference(prerequisite_id)
                        ),
                        "value": len(alternatives) if verified else "",
                        "uom": "active_lane_count" if verified else "",
                        "required_evidence_description": PREREQUISITE_DESCRIPTIONS[
                            prerequisite_id
                        ],
                        "assessment_reason": (
                            "Une voie alternative structurelle présente un flux positif V2."
                            if verified
                            else "Information absente ou insuffisamment précise dans les audits fournis."
                        ),
                    }
                )
    return rows


def generate_action_inputs(
    *,
    network_dir: Path,
    priority_boundary_audit_dir: Path,
    scope_audit_dir: Path,
    source_field_audit_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    network_dir = network_dir.resolve()
    priority_boundary_audit_dir = priority_boundary_audit_dir.resolve()
    scope_audit_dir = scope_audit_dir.resolve()
    source_field_audit_dir = source_field_audit_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Dossier de sortie déjà existant: {output_dir}")

    network_names = ("lane_sensitivity_ranking.csv",)
    scope_names = (
        "manifest.json",
        "supplier_lane_scope.csv",
        "supplier_item_source_coverage.csv",
    )
    source_names = ("manifest.json", "supplier_source_field_inventory.csv")
    network_hashes = _required_hashes(network_dir, network_names)
    scope_hashes = _required_hashes(scope_audit_dir, scope_names)
    source_hashes = _required_hashes(source_field_audit_dir, source_names)
    generator_module_path = Path(__file__).resolve()
    selector_module_path = Path(selector.__file__).resolve()
    top3_reader_module_path = Path(selector.network_dashboard.__file__).resolve()
    boundary_contract_path = Path(
        selector.network_dashboard.boundary_contract.__file__
    ).resolve()
    extension_contract_path = Path(
        selector.network_dashboard.extension_contract.__file__
    ).resolve()
    generator_module_sha256 = _sha256(generator_module_path)
    selector_module_sha256 = _sha256(selector_module_path)
    top3_reader_module_sha256 = _sha256(top3_reader_module_path)
    boundary_contract_sha256 = _sha256(boundary_contract_path)
    extension_contract_sha256 = _sha256(extension_contract_path)
    scientific_hashes = selector._scientific_source_hashes(
        network_dir,
        priority_boundary_audit_dir,
    )

    supplier_ids, selection = selector._scientific_candidate_suppliers(
        network_dir,
        priority_boundary_audit_dir,
    )
    if not supplier_ids:
        raise ValueError("La frontière signée ne contient aucun candidat fournisseur.")
    scope_manifest = _read_json(scope_audit_dir / "manifest.json")
    source_manifest = _read_json(source_field_audit_dir / "manifest.json")
    _validate_audits(
        scope_manifest=scope_manifest,
        source_manifest=source_manifest,
    )
    source_inventory = _read_csv(
        source_field_audit_dir / "supplier_source_field_inventory.csv"
    )
    if not source_inventory:
        raise ValueError("L'inventaire des champs source est vide.")
    audit_ids = {str(row.get("audit_id") or "") for row in source_inventory}
    required_absence_audits = {"missing_quality", "missing_capacity"}
    if not required_absence_audits <= audit_ids:
        raise ValueError(
            "L'audit source ne documente pas explicitement les absences qualité et capacité."
        )
    scope_rows = _read_csv(scope_audit_dir / "supplier_lane_scope.csv")
    if not scope_rows:
        raise ValueError("L'audit de périmètre ne contient aucune voie.")
    declared_lane_count = _integer(scope_manifest.get("lane_count"), len(scope_rows))
    if declared_lane_count != len(scope_rows):
        raise ValueError("Le nombre de voies de l'audit de périmètre est incohérent.")

    # The boundary releases a set, never a scientifically established order
    # within that set. Do not reuse the legacy aggregate rank here.
    supplier_ranks = {supplier_id: "" for supplier_id in supplier_ids}
    lanes, all_network_lane_keys = _priority_lanes(
        network_dir=network_dir,
        priority_supplier_ids=supplier_ids,
        priority_chain_ids=tuple(selection.get("follow_up_chain_ids") or ()),
        scope_rows=scope_rows,
    )
    catalog, active_alternatives = _build_catalog(
        lanes=lanes,
        scope_rows=scope_rows,
        all_network_lane_keys=all_network_lane_keys,
        supplier_ranks=supplier_ranks,
    )
    prerequisites = _build_prerequisites(
        lanes=lanes,
        active_alternatives_by_lane=active_alternatives,
    )

    statuses_by_action: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in prerequisites:
        statuses_by_action[(str(row["lane_key"]), str(row["action_id"]))].append(
            str(row["status"])
        )
    ready_action_keys = {
        key
        for key, statuses in statuses_by_action.items()
        if statuses and all(status == "verified" for status in statuses)
    }
    status_counts = Counter(str(row["status"]) for row in prerequisites)

    signature_payload = {
        "schema_version": SCHEMA_VERSION,
        "network_hashes": network_hashes,
        "scientific_hashes": scientific_hashes,
        "scope_hashes": scope_hashes,
        "source_field_hashes": source_hashes,
        "generator_module_sha256": generator_module_sha256,
        "selector_module_sha256": selector_module_sha256,
        "top3_reader_module_sha256": top3_reader_module_sha256,
        "boundary_contract_module_sha256": boundary_contract_sha256,
        "extension_contract_module_sha256": extension_contract_sha256,
        "allowed_action_ids": ALLOWED_ACTION_IDS,
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / CATALOG_FILE, catalog, CATALOG_FIELDS)
    _write_csv(
        output_dir / PREREQUISITE_FILE,
        prerequisites,
        PREREQUISITE_FIELDS,
    )
    artifact_file_sha256 = {
        CATALOG_FILE: _sha256(output_dir / CATALOG_FILE),
        PREREQUISITE_FILE: _sha256(output_dir / PREREQUISITE_FILE),
    }
    signature_payload["artifact_file_sha256"] = artifact_file_sha256
    signature = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    source_summary = (
        source_manifest.get("summary")
        if isinstance(source_manifest.get("summary"), Mapping)
        else {}
    )
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared_scientific_candidates_fail_closed",
        "created_at_utc": _utc_now(),
        "generation_signature": signature,
        "signature_payload": signature_payload,
        "artifact_file_sha256": artifact_file_sha256,
        "network_selection_status": selection.get("selection_status"),
        "candidate_scope": selection.get("candidate_scope"),
        "priority_selection_lineage_sha256": selection.get(
            "priority_selection_lineage_sha256", ""
        ),
        "follow_up_group_supplier_count": selection.get(
            "follow_up_group_supplier_count", len(supplier_ids)
        ),
        "follow_up_group_is_unordered": selection.get(
            "follow_up_group_is_unordered", True
        ),
        "follow_up_chain_ids": list(selection.get("follow_up_chain_ids") or []),
        "follow_up_driver_mappings": list(
            selection.get("follow_up_driver_mappings") or []
        ),
        "candidate_supplier_ids": supplier_ids,
        "candidate_supplier_count": len(supplier_ids),
        "candidate_lane_count": len(lanes),
        "allowed_action_ids": list(ALLOWED_ACTION_IDS),
        "catalog_row_count": len(catalog),
        "prerequisite_row_count": len(prerequisites),
        "prerequisite_status_counts": dict(sorted(status_counts.items())),
        "operationally_verified_lane_action_count": len(ready_action_keys),
        "fully_verified_lane_action_count": 0,
        "selector_ready": False,
        "action_readiness_pass": False,
        "scientific_global_priority_release_pass": False,
        "selector_executed": False,
        "simulation_run_count": 0,
        "industrial_recommendation_claimed": False,
        "historical_incident_probability_estimated": False,
        "missing_data_never_promoted_to_verified": True,
        "qualified_active_alternative_count_forced_to_zero_without_register": True,
        "source_limitations": {
            "industrial_supplier_score_available": _truthy(
                source_summary.get("industrial_supplier_score_available")
            ),
            "historical_supplier_performance_available": _truthy(
                source_summary.get("historical_supplier_performance_available")
            ),
            "supplier_quality_history_available": _truthy(
                source_summary.get("supplier_quality_history_available")
            ),
            "observed_supplier_capacity_available": _truthy(
                source_summary.get("observed_supplier_capacity_available")
            ),
            "fia_lead_time_is_forecast_not_actual": _truthy(
                source_summary.get("fia_lead_time_is_forecast_not_actual")
            ),
            "fia_standard_order_quantity_is_capacity": _truthy(
                source_summary.get("fia_standard_order_quantity_is_capacity")
            ),
        },
        "source_directories": {
            "network_results": str(network_dir),
            "priority_boundary_audit": str(priority_boundary_audit_dir),
            "scope_audit": str(scope_audit_dir),
            "source_field_audit": str(source_field_audit_dir),
        },
        "source_hashes": {
            "scientific": scientific_hashes,
            "network_overlay_data": network_hashes,
            "scope_audit": scope_hashes,
            "source_field_audit": source_hashes,
            "generator_module_sha256": generator_module_sha256,
            "selector_module_sha256": selector_module_sha256,
            "top3_reader_module_sha256": top3_reader_module_sha256,
            "boundary_contract_module_sha256": boundary_contract_sha256,
            "extension_contract_module_sha256": extension_contract_sha256,
        },
        "source_artifacts_mutated": False,
        "outputs": [CATALOG_FILE, PREREQUISITE_FILE],
    }
    _write_json(output_dir / MANIFEST_FILE, manifest)

    if _required_hashes(network_dir, network_names) != network_hashes:
        raise RuntimeError("Le paquet réseau a changé pendant la génération.")
    if (
        selector._scientific_source_hashes(
            network_dir,
            priority_boundary_audit_dir,
        )
        != scientific_hashes
    ):
        raise RuntimeError("Une preuve scientifique a changé pendant la génération.")
    if _required_hashes(scope_audit_dir, scope_names) != scope_hashes:
        raise RuntimeError("L'audit de périmètre a changé pendant la génération.")
    if _required_hashes(source_field_audit_dir, source_names) != source_hashes:
        raise RuntimeError("L'audit des champs source a changé pendant la génération.")
    code_hashes_after = {
        "generator": _sha256(generator_module_path),
        "selector": _sha256(selector_module_path),
        "top3_reader": _sha256(top3_reader_module_path),
        "boundary_contract": _sha256(boundary_contract_path),
        "extension_contract": _sha256(extension_contract_path),
    }
    code_hashes_before = {
        "generator": generator_module_sha256,
        "selector": selector_module_sha256,
        "top3_reader": top3_reader_module_sha256,
        "boundary_contract": boundary_contract_sha256,
        "extension_contract": extension_contract_sha256,
    }
    if code_hashes_after != code_hashes_before:
        raise RuntimeError(
            "Le générateur ou un module de sélection a changé pendant la génération."
        )
    expected_output_files = {CATALOG_FILE, PREREQUISITE_FILE, MANIFEST_FILE}
    actual_output_files = {path.name for path in output_dir.iterdir() if path.is_file()}
    if actual_output_files != expected_output_files or any(
        path.is_dir() for path in output_dir.iterdir()
    ):
        raise RuntimeError("Inventaire du paquet d'entree action incoherent.")
    if {
        name: _sha256(output_dir / name) for name in artifact_file_sha256
    } != artifact_file_sha256:
        raise RuntimeError("Empreinte d'une entree action modifiee apres generation.")
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-results", type=Path, required=True)
    parser.add_argument("--priority-boundary-audit", type=Path, required=True)
    parser.add_argument("--scope-audit", type=Path, required=True)
    parser.add_argument("--source-field-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = generate_action_inputs(
        network_dir=args.network_results,
        priority_boundary_audit_dir=args.priority_boundary_audit,
        scope_audit_dir=args.scope_audit,
        source_field_audit_dir=args.source_field_audit,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
