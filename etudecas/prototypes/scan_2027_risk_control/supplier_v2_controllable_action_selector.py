#!/usr/bin/env python3
"""Build a fail-closed action catalogue from the signed network V2 boundary.

The selector is deliberately additive and never runs the simulation. It keeps
only allow-listed native engine representations and evaluates every
operational prerequisite, but it never releases an action while the supplier
priority is scoped to the service envelope rather than globally established.
Every candidate is written to the blocked catalogue with both its scientific
and operational reasons.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_risk_results_dashboard as network_dashboard,
)


SCHEMA_VERSION = "etudecas.supplier_v2_controllable_action_selector.v2"
SELECTED_FILE = "selected_controllable_action_tests.csv"
BLOCKED_FILE = "blocked_action_candidates.csv"
MANIFEST_FILE = "action_selector_manifest.json"
ACTION_INPUT_SCHEMA_VERSION = "etudecas.supplier_v2_action_input_generator.v2"
ACTION_INPUT_MANIFEST_FILE = "action_input_manifest.json"
ACTION_INPUT_CATALOG_FILE = "action_eligibility_catalog.csv"
ACTION_INPUT_PREREQUISITE_FILE = "operational_prerequisites.csv"

SCIENTIFIC_OVERLAY_FILES = (
    "scientific_overlay_manifest.json",
    "scientific_promotion_controls.json",
)
PRIORITY_BOUNDARY_FILES = (
    "priority_boundary_audit_manifest.json",
    "scientific_priority_boundary_audit.json",
)
SCIENTIFIC_BLOCKING_REASON = "scientific_global_priority_not_released"
SCOPED_CANDIDATE_SCOPE = "boundary_envelope_service_priority"
GROUP_CANDIDATE_SCOPE = "unseparated_priority_group"
SERVICE_NONSEPARATION_GROUP_CANDIDATE_SCOPE = (
    "boundary_envelope_service_nonseparation_group"
)

VERIFIED_PREREQUISITE_STATUSES = {"verified", "confirme", "confirmé", "pass"}


ACTION_POLICIES: dict[str, dict[str, Any]] = {
    "targeted_transport_after_observed_delay": {
        "failure_modes": {"transport_delay"},
        "incident_family": "retard_transport",
        "action_phase": "reaction",
        "native_engine_actuator": "expedite_level|lead_time_adjustment_days",
        "required_prerequisites": (
            "shipment_identified_not_delivered",
            "route_change_feasible",
            "carrier_capacity_confirmed",
            "transit_gain_committed",
            "dated_cost_basis",
            "lane_scoped_detection_signal_available",
        ),
        "positive_value_prerequisites": {"transit_gain_committed"},
        "audit_key": ("transport_delay", "expedited_transport"),
        "audit_allowed_result_classes": {"recommended_if_physical_transport"},
        "interpretation": (
            "Réaction à un retard logistique observé sur une expédition existante; "
            "ne crée ni matière ni capacité fournisseur."
        ),
    },
    "prepositioned_free_stock": {
        "failure_modes": {
            "transport_delay",
            "quality_hold",
            "supply_availability",
            "quality_yield",
        },
        "incident_family_by_mode": {
            "transport_delay": "retard_transport",
            "quality_hold": "qualite",
            "quality_yield": "qualite",
            "supply_availability": "indisponibilite_fournisseur",
        },
        "action_phase": "prevention",
        "native_engine_actuator": "measurement_start_stock_scale_csv",
        "required_prerequisites": (
            "stock_build_source_identified",
            "available_before_incident",
            "released_free_stock_confirmed",
            "quantity_and_uom_confirmed",
            "shelf_life_storage_finance_approved",
            "initial_state_parameterization_audited",
        ),
        "positive_value_prerequisites": {"quantity_and_uom_confirmed"},
        "audit_key_by_mode": {
            "transport_delay": ("transport_delay", "targeted_stock"),
            "quality_hold": ("quality_hold", "targeted_stock"),
        },
        "audit_allowed_result_classes": {
            "ineffective_response_configuration",
            "ineffective_reactive_configuration",
        },
        "interpretation": (
            "Stock libre physiquement constitué et libéré avant J0; la simulation "
            "modifie seulement l'état initial et n'injecte rien pendant l'incident."
        ),
    },
    "post_release_transport_for_identified_lot": {
        "failure_modes": {"quality_hold"},
        "incident_family": "qualite",
        "action_phase": "reaction",
        "native_engine_actuator": "expedite_level|lead_time_adjustment_days",
        "required_prerequisites": (
            "released_lot_identified",
            "quality_release_observed",
            "shipment_not_delivered",
            "route_change_feasible",
            "carrier_capacity_confirmed",
            "transit_gain_committed",
            "dated_cost_basis",
            "lane_scoped_detection_signal_available",
        ),
        "positive_value_prerequisites": {"transit_gain_committed"},
        "audit_key": ("quality_hold", "expedited_transport"),
        "audit_allowed_result_classes": {"useful_post_release_not_quality_solution"},
        "interpretation": (
            "Récupération logistique après libération observée d'un lot identifié; "
            "la durée qualité reste entièrement inchangée."
        ),
    },
    "prepared_qualified_alternative_source": {
        "failure_modes": {"supply_availability", "quality_yield"},
        "incident_family_by_mode": {
            "quality_yield": "qualite",
            "supply_availability": "indisponibilite_fournisseur",
        },
        "action_phase": "prevention",
        "native_engine_actuator": "priority_weight_on_existing_active_lane",
        "required_prerequisites": (
            "supplier_material_qualification_valid",
            "alternative_lane_positive_v2_flow",
            "capacity_quantity_committed",
            "lead_time_moq_contract_confirmed",
            "quality_and_transport_route_approved",
            "existing_lane_weight_parameterization_audited",
        ),
        "positive_value_prerequisites": {"capacity_quantity_committed"},
        "interpretation": (
            "Préparation d'une voie déjà présente, active, qualifiée et capacitaire; "
            "aucun fournisseur ou volume n'est créé par le sélecteur."
        ),
    },
}


FORBIDDEN_ACTION_IDS = {
    "alternate_released_lot": "aucun_actionneur_natif_de_lot_alternatif",
    "post_receipt_transport_expedite": "transport_termine_et_levier_inadapte_a_la_qualite",
    "closed_loop_allocation_to_prepared_source": (
        "allocation_proxy_non_causale_sans_observation_de_voie"
    ),
    "replanning": "replanification_proxy_non_causale",
    "replanning_proxy": "replanification_proxy_non_causale",
    "emergency_purchase": "achat_exceptionnel_proxy_sans_flux_physique_qualifie",
    "second_supplier_proxy": "source_alternative_non_qualifiee",
    "combined_response": "paquet_melangeant_des_proxies_non_valides",
    "laboratory_acceleration": "acceleration_qualite_ou_laboratoire_supposee",
    "quality_release_acceleration": "acceleration_qualite_ou_laboratoire_supposee",
}


LEGACY_SCIENTIFIC_VERDICT = {
    "conclusion_allowed": (
        "Le trio de l'enveloppe service, ou le groupe non tranché de repli, sert "
        "uniquement à constituer un catalogue de candidats bloqués. Aucun levier "
        "n'est libéré tant qu'une priorité globale n'est pas démontrée."
    ),
    "claims_forbidden": (
        "Ce résultat n'est ni une probabilité d'incident, ni une prévision de "
        "performance fournisseur, ni une criticité industrielle observée, ni une "
        "recommandation opérationnelle."
    ),
    "scientific_boundary": [
        "priorité limitée à l'enveloppe du service client",
        "aucun top 3 universel fournisseur publié",
        "toutes les actions restent des essais futurs hypothétiques",
    ],
}

SCIENTIFIC_VERDICT = {
    "conclusion_allowed": (
        "Le groupe service non separe de quatre fournisseurs sert uniquement a "
        "constituer un catalogue de candidats bloques. Aucun levier n'est libere "
        "et aucun levier n'a ete teste par la campagne reseau finale."
    ),
    "claims_forbidden": (
        "Ce resultat n'est ni une probabilite d'incident, ni une prevision de "
        "performance fournisseur, ni une criticite industrielle observee, ni une "
        "recommandation operationnelle."
    ),
    "scientific_boundary": [
        "groupe service non ordonne et non separe",
        "aucun classement universel des fournisseurs",
        "toutes les actions restent des essais futurs hypothetiques",
    ],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = math.nan) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    if not fields:
        fields = [
            "lane_key",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "failure_mode",
            "action_id",
            "selector_status",
            "blocking_reasons",
        ]
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
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


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _source_hashes(directory: Path, names: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        path = directory / name
        if not path.is_file():
            raise FileNotFoundError(f"Source requise absente: {path}")
        result[name] = _sha256(path)
    return result


def _scientific_source_hashes(
    network_dir: Path,
    priority_boundary_audit_dir: Path,
) -> dict[str, dict[str, str]]:
    return {
        "network_overlay": _source_hashes(
            network_dir,
            SCIENTIFIC_OVERLAY_FILES,
        ),
        "priority_boundary_audit": _source_hashes(
            priority_boundary_audit_dir,
            PRIORITY_BOUNDARY_FILES,
        ),
    }


def _scientific_candidate_suppliers(
    network_dir: Path,
    priority_boundary_audit_dir: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Read candidates only from the signed service-envelope boundary.

    The legacy aggregate rank and its inherited ``top3`` flags are never used.
    A released service-envelope trio remains scoped and therefore cannot
    release an action. If that boundary is unresolved, the signed unranked
    priority group is retained, also fail-closed.
    """

    controls = _read_json(network_dir / "scientific_promotion_controls.json")
    lineage = controls.get("priority_selection_lineage")
    if isinstance(lineage, Mapping):
        # The V3 path follows the complete four-supplier service
        # nonseparation group. It must never fall back to the 16-supplier
        # universal ambiguity group.
        network_dashboard.extension_contract.validate_scientific_overlay(network_dir)
        network_dashboard.boundary_contract.validate_audit_package(
            priority_boundary_audit_dir
        )
        audit = _read_json(
            priority_boundary_audit_dir / "scientific_priority_boundary_audit.json"
        )
        boundary_manifest_path = (
            priority_boundary_audit_dir / "priority_boundary_audit_manifest.json"
        )
        boundary_result_path = (
            priority_boundary_audit_dir / "scientific_priority_boundary_audit.json"
        )
        boundary_ranking_path = (
            priority_boundary_audit_dir / "supplier_metric_rankings.csv"
        )
        if not boundary_ranking_path.is_file():
            raise FileNotFoundError(
                "Le classement physique de la frontiere fournisseur est absent."
            )
        boundary_manifest = _read_json(boundary_manifest_path)
        if (
            _sha256(boundary_manifest_path)
            != str(lineage.get("priority_boundary_manifest_sha256") or "")
            or _sha256(boundary_result_path)
            != str(lineage.get("priority_boundary_result_sha256") or "")
            or _sha256(boundary_ranking_path)
            != str(lineage.get("priority_boundary_ranking_sha256") or "")
            or str(boundary_manifest.get("package_signature") or "")
            != str(lineage.get("priority_boundary_package_signature") or "")
        ):
            raise ValueError(
                "La frontiere vivante ne correspond pas a la lignee V3 auditee."
            )

        follow_up_ids = [
            str(value).strip()
            for value in (lineage.get("follow_up_supplier_ids") or [])
            if str(value).strip()
        ]
        service_ids = [
            str(value).strip()
            for value in (lineage.get("service_nonseparation_group_supplier_ids") or [])
            if str(value).strip()
        ]
        candidate_ids = [
            str(value).strip()
            for value in (lineage.get("selection_candidate_pool_supplier_ids") or [])
            if str(value).strip()
        ]
        boundary_service_ids = [
            str(value).strip()
            for value in (
                audit.get("envelope_service_nonseparation_group_supplier_ids") or []
            )
            if str(value).strip()
        ]
        universal_ids = [
            str(value).strip()
            for value in (
                audit.get("priority_group_supplier_ids_if_no_universal_top3") or []
            )
            if str(value).strip()
        ]
        follow_up_chain_ids = [
            str(value).strip()
            for value in (lineage.get("follow_up_chain_ids") or [])
            if str(value).strip()
        ]
        raw_driver_mappings = lineage.get("follow_up_driver_mappings")
        driver_mappings = (
            [dict(row) for row in raw_driver_mappings]
            if isinstance(raw_driver_mappings, list)
            and all(isinstance(row, Mapping) for row in raw_driver_mappings)
            else []
        )
        mapped_suppliers = [
            str(row.get("supplier_id") or "").strip() for row in driver_mappings
        ]
        mapped_chains = [
            str(row.get("driver_chain_id") or "").strip() for row in driver_mappings
        ]
        false_control_fields = (
            "global_network_priority_robustness_evaluable",
            "promotion_allowed",
            "confirmatory_priority_set_release_allowed",
            "global_priority_release_allowed",
            "action_promotion_allowed",
            "slot_order_has_scientific_meaning",
        )
        false_lineage_fields = (
            "scientific_order_claimed",
            "confirmatory_priority_set_release_allowed",
            "global_priority_release_allowed",
            "action_promotion_allowed",
            "slot_order_has_scientific_meaning",
        )
        if (
            str(controls.get("status") or "") != "scientific_controls_complete"
            or controls.get("execution_integrity_pass") is not True
            or controls.get("priority_boundary_lineage_integrity_pass") is not True
            or controls.get("follow_up_group_supplier_count") != 4
            or controls.get("follow_up_group_is_unordered") is not True
            or any(controls.get(field) is not False for field in false_control_fields)
            or str(lineage.get("priority_selection_status") or "")
            != "complete_service_nonseparation_group_follow_up"
            or lineage.get("service_nonseparation_group_fully_followed_up") is not True
            or lineage.get("follow_up_group_is_unordered") is not True
            or any(lineage.get(field) is not False for field in false_lineage_fields)
            or not (
                follow_up_ids
                == service_ids
                == candidate_ids
                == boundary_service_ids
                == sorted(follow_up_ids)
            )
            or len(follow_up_ids) != 4
            or len(set(follow_up_ids)) != 4
            or len(follow_up_chain_ids) != 4
            or len(set(follow_up_chain_ids)) != 4
            or len(driver_mappings) != 4
            or sorted(mapped_suppliers) != follow_up_ids
            or mapped_chains != follow_up_chain_ids
            or any(
                not str(row.get("driver_scenario_id") or "").strip()
                or not str(row.get("driver_failure_mode") or "").strip()
                for row in driver_mappings
            )
            or not set(follow_up_ids) < set(universal_ids)
            or audit.get("scoped_descriptive_priority_set_display_allowed") is not False
            or audit.get("confirmatory_priority_set_release_allowed") is not False
            or audit.get("global_priority_release_allowed") is not False
            or audit.get("action_promotion_allowed") is not False
            or audit.get("envelope_service_priority_set_release_pass") is not False
            or audit.get("envelope_service_priority_supplier_ids") not in ([], None)
            or audit.get("universal_supplier_top3_release_pass") is not False
            or audit.get("industrial_supplier_criticality_claimed") is not False
            or str(audit.get("historical_occurrence_probability") or "")
            != "not_estimated"
        ):
            raise ValueError(
                "Le groupe service V3 ou ses garde-fous scientifiques sont incoherents."
            )
        return follow_up_ids, {
            "selection_status": ("service_nonseparation_group_action_candidates_only"),
            "selection_reason": SCIENTIFIC_BLOCKING_REASON,
            "status": "blocked_service_nonseparation_group_follow_up",
            "candidate_scope": SERVICE_NONSEPARATION_GROUP_CANDIDATE_SCOPE,
            "priority_selection_lineage_sha256": str(
                controls.get("priority_selection_lineage_sha256") or ""
            ),
            "follow_up_group_supplier_count": 4,
            "follow_up_group_is_unordered": True,
            "follow_up_chain_ids": follow_up_chain_ids,
            "follow_up_driver_mappings": driver_mappings,
        }

    data = network_dashboard.load_network_results(
        network_dir,
        priority_boundary_audit_dir=priority_boundary_audit_dir,
    )
    if str(data.get("input_status") or "") != (
        "signed_scientific_overlay_and_audits_valid"
    ):
        raise ValueError(
            "La surcouche et la frontière scientifiques ne sont pas validées."
        )
    audit = _read_json(
        priority_boundary_audit_dir / "scientific_priority_boundary_audit.json"
    )
    if (
        str(audit.get("service_priority_scope") or "")
        != network_dashboard.boundary_contract.SUPPLIER_ENVELOPE_SCOPE
        or audit.get("universal_supplier_top3_release_pass") is not False
        or audit.get("industrial_supplier_criticality_claimed") is not False
        or str(audit.get("historical_occurrence_probability") or "") != "not_estimated"
    ):
        raise ValueError(
            "La portée scientifique de la frontière fournisseur est invalide."
        )

    envelope_released = audit.get("envelope_service_priority_set_release_pass") is True
    envelope_ids = [
        str(value).strip()
        for value in (audit.get("envelope_service_priority_supplier_ids") or [])
        if str(value).strip()
    ]
    group_ids = [
        str(value).strip()
        for value in (
            audit.get("priority_group_supplier_ids_if_no_universal_top3") or []
        )
        if str(value).strip()
    ]
    if envelope_released:
        loaded_ids = [
            str(row.get("supplier_id") or "").strip()
            for row in (data.get("stable_priorities") or [])
        ]
        if (
            len(envelope_ids) != 3
            or len(set(envelope_ids)) != 3
            or loaded_ids != envelope_ids
            or str(data.get("priority_reporting_status") or "")
            != "envelope_service_top3_released"
        ):
            raise ValueError("Le trio signé de l'enveloppe service est incohérent.")
        return envelope_ids, {
            "selection_status": "scoped_envelope_action_candidates_only",
            "selection_reason": SCIENTIFIC_BLOCKING_REASON,
            "status": "blocked_scoped_priority_not_globally_released",
            "candidate_scope": SCOPED_CANDIDATE_SCOPE,
        }

    loaded_group = [
        str(value) for value in data.get("priority_group_supplier_ids") or []
    ]
    if (
        envelope_ids
        or len(group_ids) < 3
        or len(set(group_ids)) != len(group_ids)
        or loaded_group != group_ids
        or data.get("stable_priorities")
        or str(data.get("priority_reporting_status") or "") != "priority_group_only"
    ):
        raise ValueError("Le groupe fournisseur non tranché est incohérent.")
    return group_ids, {
        "selection_status": "unseparated_priority_group_action_candidates_only",
        "selection_reason": SCIENTIFIC_BLOCKING_REASON,
        "status": "blocked_priority_boundary_unresolved",
        "candidate_scope": GROUP_CANDIDATE_SCOPE,
    }


def _validated_action_audit(audit_dir: Path) -> dict[tuple[str, str], dict[str, str]]:
    manifest_path = audit_dir / "manifest.json"
    rows_path = audit_dir / "controllable_action_lever_audit.csv"
    if not manifest_path.is_file() or not rows_path.is_file():
        raise FileNotFoundError("Audit des leviers v1 incomplet.")
    manifest = _read_json(manifest_path)
    validation = manifest.get("validation") or {}
    if (
        str(manifest.get("status") or "") != "complete"
        or _to_int(validation.get("new_simulation_run_count"), -1) != 0
        or validation.get("previous_artifacts_mutated") is not False
    ):
        raise ValueError("Audit des leviers v1 non publiable ou non préservant.")
    rows = _read_csv(rows_path)
    tested = [
        row for row in rows if str(row.get("record_type") or "") == "tested_lever"
    ]
    if len(tested) != 14:
        raise ValueError("L'audit attendu doit contenir exactement 14 leviers testés.")
    index: dict[tuple[str, str], dict[str, str]] = {}
    for row in tested:
        key = (str(row.get("failure_mode") or ""), str(row.get("lever_id") or ""))
        if key in index:
            raise ValueError(f"Levier audité dupliqué: {key}")
        index[key] = row
    return index


def _prerequisite_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    index: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    required_fields = {
        "lane_key",
        "action_id",
        "prerequisite_id",
        "status",
        "evidence_reference",
    }
    for row in rows:
        if not required_fields <= set(row):
            raise ValueError(
                "Chaque preuve doit contenir lane_key, action_id, prerequisite_id, "
                "status et evidence_reference."
            )
        key = (
            str(row.get("lane_key") or ""),
            str(row.get("action_id") or ""),
            str(row.get("prerequisite_id") or ""),
        )
        if not all(key):
            raise ValueError("Clé de preuve opérationnelle incomplète.")
        if key in index:
            raise ValueError(f"Preuve opérationnelle dupliquée: {key}")
        index[key] = row
    return index


def _incident_family(policy: Mapping[str, Any], failure_mode: str) -> str:
    by_mode = policy.get("incident_family_by_mode") or {}
    return str(by_mode.get(failure_mode) or policy.get("incident_family") or "")


def _audit_gate(
    *,
    policy: Mapping[str, Any],
    failure_mode: str,
    audit_index: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[bool, str, str]:
    key_by_mode = policy.get("audit_key_by_mode") or {}
    key = key_by_mode.get(failure_mode) or policy.get("audit_key")
    if not key:
        return True, "not_previously_tested_as_this_preventive_configuration", ""
    audited = audit_index.get(tuple(key))
    if audited is None:
        return False, "prior_audit_row_missing", "prior_audit_row_missing"
    result_class = str(audited.get("result_class") or "")
    allowed = set(policy.get("audit_allowed_result_classes") or ())
    if result_class not in allowed:
        return False, result_class, "prior_audit_result_not_compatible"
    if tuple(key) == ("transport_delay", "expedited_transport") and not _as_bool(
        audited.get("execution_verified_all_seeds")
    ):
        return False, result_class, "prior_audit_execution_not_verified"
    return True, result_class, ""


def _blocking_reasons(
    *,
    row: Mapping[str, Any],
    policy: Mapping[str, Any] | None,
    prerequisite_index: Mapping[tuple[str, str, str], Mapping[str, Any]],
    audit_index: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[list[str], str]:
    action_id = str(row.get("action_id") or "")
    failure_mode = str(row.get("failure_mode") or "")
    lane = str(row.get("lane_key") or "")
    reasons: list[str] = []
    audit_result = ""
    if action_id in FORBIDDEN_ACTION_IDS:
        return [FORBIDDEN_ACTION_IDS[action_id]], audit_result
    if policy is None:
        return ["action_non_inscrite_dans_la_liste_blanche"], audit_result
    if failure_mode not in set(policy["failure_modes"]):
        reasons.append("action_non_adaptee_a_la_famille_d_incident")
    if not _as_bool(row.get("baseline_positive_flow")):
        reasons.append("voie_sans_flux_positif_v2")
    if not _as_bool(row.get("native_actuator_available")):
        reasons.append("actionneur_moteur_natif_absent")
    if str(row.get("native_engine_actuator") or "") != str(
        policy["native_engine_actuator"]
    ):
        reasons.append("actionneur_moteur_different_du_contrat")
    if not _as_bool(row.get("simulation_execution_allowed")):
        detail = str(row.get("refusal_reason") or "catalogue_non_eligible")
        reasons.append(f"catalogue_non_eligible:{detail}")
    if action_id == "prepared_qualified_alternative_source":
        if _to_int(row.get("structural_alternative_count"), 0) < 1:
            reasons.append("aucune_source_alternative_structurelle")
        if _to_int(row.get("active_alternative_count"), 0) < 1:
            reasons.append("aucune_source_alternative_active_dans_v2")
        if _to_int(row.get("qualified_active_alternative_count"), 0) < 1:
            reasons.append("aucune_source_alternative_active_et_qualifiee")
    audit_pass, audit_result, audit_reason = _audit_gate(
        policy=policy,
        failure_mode=failure_mode,
        audit_index=audit_index,
    )
    if not audit_pass:
        reasons.append(audit_reason)
    positive = set(policy.get("positive_value_prerequisites") or ())
    for prerequisite_id in policy["required_prerequisites"]:
        evidence = prerequisite_index.get((lane, action_id, prerequisite_id))
        if evidence is None:
            reasons.append(f"prerequis_absent:{prerequisite_id}")
            continue
        status = str(evidence.get("status") or "").strip().lower()
        if status not in VERIFIED_PREREQUISITE_STATUSES:
            reasons.append(f"prerequis_non_verifie:{prerequisite_id}")
        if not str(evidence.get("evidence_reference") or "").strip():
            reasons.append(f"preuve_absente:{prerequisite_id}")
        if prerequisite_id in positive:
            value = _to_float(evidence.get("value"))
            if not math.isfinite(value) or value <= 0:
                reasons.append(f"valeur_positive_absente:{prerequisite_id}")
            if not str(evidence.get("uom") or "").strip():
                reasons.append(f"unite_absente:{prerequisite_id}")
    return sorted(set(reasons)), audit_result


def select_actions(
    *,
    selected_supplier_ids: Sequence[str],
    catalog_rows: Sequence[Mapping[str, Any]],
    prerequisite_rows: Sequence[Mapping[str, Any]],
    audit_index: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected_suppliers = set(selected_supplier_ids)
    prerequisites = _prerequisite_index(prerequisite_rows)
    selected: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in catalog_rows:
        if str(source.get("supplier_id") or "") not in selected_suppliers:
            continue
        row = dict(source)
        key = (
            str(row.get("lane_key") or ""),
            str(row.get("failure_mode") or ""),
            str(row.get("action_id") or ""),
        )
        if not all(key) or key in seen:
            raise ValueError(f"Ligne d'action invalide ou dupliquée: {key}")
        seen.add(key)
        action_id = key[2]
        policy = ACTION_POLICIES.get(action_id)
        reasons, audit_result = _blocking_reasons(
            row=row,
            policy=policy,
            prerequisite_index=prerequisites,
            audit_index=audit_index,
        )
        row.update(
            {
                "incident_family": (_incident_family(policy, key[1]) if policy else ""),
                "action_phase": str((policy or {}).get("action_phase") or ""),
                "selector_status": "selected_for_paired_test"
                if not reasons
                else "blocked",
                "blocking_reasons": "|".join(reasons),
                "prior_audit_result_class": audit_result,
                "future_test_only_not_recommendation": True,
                "in_horizon_stock_injection_allowed": False,
                "unqualified_source_creation_allowed": False,
                "quality_or_laboratory_acceleration_assumed": False,
                "proxy_replanning_allowed": False,
                "policy_interpretation": str(
                    (policy or {}).get("interpretation") or ""
                ),
            }
        )
        (selected if not reasons else blocked).append(row)

    def ordering(row: Mapping[str, Any]) -> tuple[str, ...]:
        return (
            str(row.get("supplier_id") or ""),
            str(row.get("lane_key") or ""),
            str(row.get("incident_family") or ""),
            str(row.get("action_phase") or ""),
            str(row.get("action_id") or ""),
        )

    return sorted(selected, key=ordering), sorted(blocked, key=ordering)


def _validate_action_input_package(
    *,
    manifest_path: Path,
    catalog_path: Path,
    prerequisite_path: Path,
    scientific_hashes: Mapping[str, Any],
    candidate_suppliers: Sequence[str],
    scientific_selection: Mapping[str, Any],
) -> dict[str, Any]:
    root = manifest_path.parent.resolve()
    if (
        manifest_path.name != ACTION_INPUT_MANIFEST_FILE
        or catalog_path.parent.resolve() != root
        or prerequisite_path.parent.resolve() != root
        or catalog_path.name != ACTION_INPUT_CATALOG_FILE
        or prerequisite_path.name != ACTION_INPUT_PREREQUISITE_FILE
    ):
        raise ValueError(
            "Le paquet d'entree action doit rester dans un dossier unique."
        )
    expected_inventory = {
        ACTION_INPUT_MANIFEST_FILE,
        ACTION_INPUT_CATALOG_FILE,
        ACTION_INPUT_PREREQUISITE_FILE,
    }
    actual_inventory = {path.name for path in root.iterdir() if path.is_file()}
    if actual_inventory != expected_inventory or any(
        path.is_dir() for path in root.iterdir()
    ):
        raise ValueError("Inventaire du paquet d'entree action invalide.")

    manifest = _read_json(manifest_path)
    artifact_hashes = manifest.get("artifact_file_sha256")
    signature_payload = manifest.get("signature_payload")
    source_hashes = manifest.get("source_hashes")
    if (
        str(manifest.get("schema_version") or "") != ACTION_INPUT_SCHEMA_VERSION
        or str(manifest.get("status") or "")
        != "prepared_scientific_candidates_fail_closed"
        or not isinstance(artifact_hashes, Mapping)
        or set(artifact_hashes)
        != {ACTION_INPUT_CATALOG_FILE, ACTION_INPUT_PREREQUISITE_FILE}
        or not isinstance(signature_payload, Mapping)
        or not isinstance(source_hashes, Mapping)
        or manifest.get("outputs")
        != [ACTION_INPUT_CATALOG_FILE, ACTION_INPUT_PREREQUISITE_FILE]
        or manifest.get("selector_executed") is not False
        or manifest.get("selector_ready") is not False
        or manifest.get("action_readiness_pass") is not False
        or manifest.get("industrial_recommendation_claimed") is not False
        or manifest.get("simulation_run_count") != 0
        or manifest.get("missing_data_never_promoted_to_verified") is not True
        or manifest.get(
            "qualified_active_alternative_count_forced_to_zero_without_register"
        )
        is not True
    ):
        raise ValueError("Manifeste du paquet d'entree action invalide.")
    live_artifact_hashes = {
        ACTION_INPUT_CATALOG_FILE: _sha256(catalog_path),
        ACTION_INPUT_PREREQUISITE_FILE: _sha256(prerequisite_path),
    }
    if dict(artifact_hashes) != live_artifact_hashes:
        raise ValueError("Empreinte du catalogue ou des prerequis invalide.")
    if signature_payload.get("artifact_file_sha256") != live_artifact_hashes or str(
        manifest.get("generation_signature") or ""
    ) != _canonical_sha256(signature_payload):
        raise ValueError("Signature interne du paquet d'entree action invalide.")

    expected_signature_fields = {
        "schema_version",
        "network_hashes",
        "scientific_hashes",
        "scope_hashes",
        "source_field_hashes",
        "generator_module_sha256",
        "selector_module_sha256",
        "top3_reader_module_sha256",
        "boundary_contract_module_sha256",
        "extension_contract_module_sha256",
        "allowed_action_ids",
        "artifact_file_sha256",
    }
    if set(signature_payload) != expected_signature_fields:
        raise ValueError("Contrat signe du paquet d'entree action incomplet.")
    generator_path = (
        Path(__file__).resolve().with_name("supplier_v2_action_input_generator.py")
    )
    module_hashes = {
        "generator_module_sha256": _sha256(generator_path),
        "selector_module_sha256": _sha256(Path(__file__).resolve()),
        "top3_reader_module_sha256": _sha256(
            Path(network_dashboard.__file__).resolve()
        ),
        "boundary_contract_module_sha256": _sha256(
            Path(network_dashboard.boundary_contract.__file__).resolve()
        ),
        "extension_contract_module_sha256": _sha256(
            Path(network_dashboard.extension_contract.__file__).resolve()
        ),
    }
    if (
        signature_payload.get("schema_version") != ACTION_INPUT_SCHEMA_VERSION
        or signature_payload.get("scientific_hashes") != scientific_hashes
        or list(signature_payload.get("allowed_action_ids") or [])
        != list(ACTION_POLICIES)
        or any(
            str(signature_payload.get(field) or "") != digest
            for field, digest in module_hashes.items()
        )
        or source_hashes.get("scientific") != scientific_hashes
        or source_hashes.get("network_overlay_data")
        != signature_payload.get("network_hashes")
        or source_hashes.get("scope_audit") != signature_payload.get("scope_hashes")
        or source_hashes.get("source_field_audit")
        != signature_payload.get("source_field_hashes")
        or any(
            str(source_hashes.get(field) or "") != digest
            for field, digest in module_hashes.items()
        )
    ):
        raise ValueError("Sources ou code du paquet d'entree action incoherents.")

    expected_chains = list(scientific_selection.get("follow_up_chain_ids") or [])
    expected_mappings = list(
        scientific_selection.get("follow_up_driver_mappings") or []
    )
    if (
        list(manifest.get("candidate_supplier_ids") or []) != list(candidate_suppliers)
        or manifest.get("candidate_supplier_count") != len(candidate_suppliers)
        or (
            expected_chains
            and manifest.get("candidate_lane_count") != len(expected_chains)
        )
        or manifest.get("network_selection_status")
        != scientific_selection.get("selection_status")
        or manifest.get("candidate_scope")
        != scientific_selection.get("candidate_scope")
        or str(manifest.get("priority_selection_lineage_sha256") or "")
        != str(scientific_selection.get("priority_selection_lineage_sha256") or "")
        or list(manifest.get("follow_up_chain_ids") or []) != expected_chains
        or list(manifest.get("follow_up_driver_mappings") or []) != expected_mappings
        or manifest.get("follow_up_group_supplier_count")
        != scientific_selection.get("follow_up_group_supplier_count")
        or manifest.get("follow_up_group_is_unordered") is not True
    ):
        raise ValueError("Portee V3 divergente dans le paquet d'entree action.")
    catalog_rows = _read_csv(catalog_path)
    prerequisite_rows = _read_csv(prerequisite_path)
    if (
        manifest.get("allowed_action_ids") != list(ACTION_POLICIES)
        or manifest.get("catalog_row_count") != len(catalog_rows)
        or manifest.get("prerequisite_row_count") != len(prerequisite_rows)
    ):
        raise ValueError("Comptages du paquet d'entree action incoherents.")
    if expected_chains:
        mapping_by_supplier = {
            str(row.get("supplier_id") or ""): str(row.get("driver_chain_id") or "")
            for row in expected_mappings
            if isinstance(row, Mapping)
        }
        observed_chains: set[str] = set()
        for row in catalog_rows:
            supplier = str(row.get("supplier_id") or "")
            row_chains = {
                value
                for value in str(row.get("network_chain_ids") or "").split("|")
                if value
            }
            observed_chains.update(row_chains)
            if row_chains != {mapping_by_supplier.get(supplier, "")}:
                raise ValueError(
                    "Le catalogue ne reste pas limite a la voie V3 du fournisseur."
                )
        if observed_chains != set(expected_chains):
            raise ValueError("Les voies V3 du catalogue action sont incompletes.")
    return manifest


def run_selector(
    *,
    network_dir: Path,
    priority_boundary_audit_dir: Path,
    action_input_manifest_path: Path,
    action_catalog_path: Path,
    prerequisite_path: Path,
    action_audit_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    network_dir = network_dir.resolve()
    priority_boundary_audit_dir = priority_boundary_audit_dir.resolve()
    action_input_manifest_path = action_input_manifest_path.resolve()
    action_catalog_path = action_catalog_path.resolve()
    prerequisite_path = prerequisite_path.resolve()
    action_audit_dir = action_audit_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Dossier de sélection déjà existant: {output_dir}")
    selector_module_path = Path(__file__).resolve()
    top3_reader_module_path = Path(network_dashboard.__file__).resolve()
    boundary_contract_path = Path(
        network_dashboard.boundary_contract.__file__
    ).resolve()
    extension_contract_path = Path(
        network_dashboard.extension_contract.__file__
    ).resolve()
    selector_module_sha256 = _sha256(selector_module_path)
    top3_reader_module_sha256 = _sha256(top3_reader_module_path)
    boundary_contract_sha256 = _sha256(boundary_contract_path)
    extension_contract_sha256 = _sha256(extension_contract_path)
    scientific_hashes = _scientific_source_hashes(
        network_dir,
        priority_boundary_audit_dir,
    )
    candidate_suppliers, scientific_selection = _scientific_candidate_suppliers(
        network_dir,
        priority_boundary_audit_dir,
    )
    if (
        not action_input_manifest_path.is_file()
        or not action_catalog_path.is_file()
        or not prerequisite_path.is_file()
    ):
        raise FileNotFoundError("Catalogue d'actions ou preuves de prérequis absent.")
    action_input_manifest = _validate_action_input_package(
        manifest_path=action_input_manifest_path,
        catalog_path=action_catalog_path,
        prerequisite_path=prerequisite_path,
        scientific_hashes=scientific_hashes,
        candidate_suppliers=candidate_suppliers,
        scientific_selection=scientific_selection,
    )
    action_input_manifest_sha256 = _sha256(action_input_manifest_path)
    catalog_sha256 = _sha256(action_catalog_path)
    prerequisites_sha256 = _sha256(prerequisite_path)
    audit_hashes = _source_hashes(
        action_audit_dir,
        ("manifest.json", "controllable_action_lever_audit.csv"),
    )
    audit_index = _validated_action_audit(action_audit_dir)
    catalog_rows = _read_csv(action_catalog_path)
    prerequisite_rows = _read_csv(prerequisite_path)
    catalog_supplier_ids = {
        str(row.get("supplier_id") or "").strip() for row in catalog_rows
    } - {""}
    if catalog_supplier_ids != set(candidate_suppliers):
        raise ValueError(
            "Le catalogue ne couvre pas exactement les candidats de la frontière signée."
        )
    operationally_ready, operationally_blocked = select_actions(
        selected_supplier_ids=candidate_suppliers,
        catalog_rows=catalog_rows,
        prerequisite_rows=prerequisite_rows,
        audit_index=audit_index,
    )
    blocked: list[dict[str, Any]] = []
    operationally_ready_count = 0
    for source in [*operationally_ready, *operationally_blocked]:
        row = dict(source)
        operational_reasons = sorted(
            {
                reason.strip()
                for reason in str(row.get("blocking_reasons") or "").split("|")
                if reason.strip()
            }
        )
        operational_pass = not operational_reasons
        operationally_ready_count += int(operational_pass)
        all_reasons = sorted({*operational_reasons, SCIENTIFIC_BLOCKING_REASON})
        row.update(
            {
                "selector_status": "blocked",
                "candidate_scope": scientific_selection["candidate_scope"],
                "scientific_release_gate_pass": False,
                "scientific_blocking_reason": SCIENTIFIC_BLOCKING_REASON,
                "operational_prerequisite_gate_pass": operational_pass,
                "operational_prerequisite_blocking_reasons": "|".join(
                    operational_reasons
                ),
                "blocking_reasons": "|".join(all_reasons),
                "future_test_only_not_recommendation": True,
            }
        )
        blocked.append(row)
    blocked.sort(
        key=lambda row: (
            str(row.get("supplier_id") or ""),
            str(row.get("lane_key") or ""),
            str(row.get("incident_family") or ""),
            str(row.get("action_phase") or ""),
            str(row.get("action_id") or ""),
        )
    )
    if not blocked:
        raise ValueError("Aucun candidat d'action réel n'a été produit.")
    selected: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(output_dir / SELECTED_FILE, selected)
    _write_csv(output_dir / BLOCKED_FILE, blocked)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": scientific_selection["status"],
        "created_at_utc": _utc_now(),
        **scientific_selection,
        "candidate_supplier_ids": candidate_suppliers,
        "selected_supplier_ids": [],
        "selected_action_test_count": 0,
        "blocked_action_candidate_count": len(blocked),
        "scientific_blocked_candidate_count": len(blocked),
        "operationally_ready_but_scientifically_blocked_count": (
            operationally_ready_count
        ),
        "selected_counts_by_phase": {},
        "selected_counts_by_incident_family": {},
        "action_readiness_pass": False,
        "scientific_global_priority_release_pass": False,
        "simulation_run_count": 0,
        "industrial_recommendation_claimed": False,
        "prevention_and_reaction_separated": True,
        "incident_families_separated": [
            "retard_transport",
            "indisponibilite_fournisseur",
            "qualite",
        ],
        "hard_exclusions": {
            "unqualified_alternative_source": True,
            "in_horizon_magic_stock_injection": True,
            "assumed_quality_or_laboratory_acceleration": True,
            "noncausal_replanning_proxy": True,
        },
        "scientific_verdict": SCIENTIFIC_VERDICT,
        "source_hashes": {
            "scientific": scientific_hashes,
            "action_catalog_sha256": catalog_sha256,
            "prerequisites_sha256": prerequisites_sha256,
            "action_input_manifest_sha256": action_input_manifest_sha256,
            "action_input_generation_signature": action_input_manifest[
                "generation_signature"
            ],
            "prior_action_audit": audit_hashes,
            "selector_module_sha256": selector_module_sha256,
            "top3_reader_module_sha256": top3_reader_module_sha256,
            "boundary_contract_module_sha256": boundary_contract_sha256,
            "extension_contract_module_sha256": extension_contract_sha256,
        },
        "sources_mutated": False,
        "main_network_ranking_mutated": False,
        "outputs": [SELECTED_FILE, BLOCKED_FILE],
    }
    _write_json(output_dir / MANIFEST_FILE, manifest)
    current_audit_hashes = _source_hashes(action_audit_dir, tuple(audit_hashes))
    if (
        _scientific_source_hashes(network_dir, priority_boundary_audit_dir)
        != scientific_hashes
        or current_audit_hashes != audit_hashes
    ):
        raise RuntimeError("Une source a changé pendant la sélection additive.")
    if (
        _sha256(action_catalog_path) != catalog_sha256
        or _sha256(prerequisite_path) != prerequisites_sha256
    ):
        raise RuntimeError("Catalogue ou preuves modifiés pendant la sélection.")
    if _sha256(action_input_manifest_path) != action_input_manifest_sha256:
        raise RuntimeError("Manifeste d'entree action modifie pendant la selection.")
    if (
        _sha256(selector_module_path) != selector_module_sha256
        or _sha256(top3_reader_module_path) != top3_reader_module_sha256
        or _sha256(boundary_contract_path) != boundary_contract_sha256
        or _sha256(extension_contract_path) != extension_contract_sha256
    ):
        raise RuntimeError(
            "Le sélecteur ou le module de stabilisation du top 3 a changé "
            "pendant la sélection."
        )
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network-results", type=Path, required=True)
    parser.add_argument("--priority-boundary-audit", type=Path, required=True)
    parser.add_argument("--action-input-manifest", type=Path, required=True)
    parser.add_argument("--action-catalog", type=Path, required=True)
    parser.add_argument("--prerequisite-evidence", type=Path, required=True)
    parser.add_argument("--action-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = run_selector(
        network_dir=args.network_results,
        priority_boundary_audit_dir=args.priority_boundary_audit,
        action_input_manifest_path=args.action_input_manifest,
        action_catalog_path=args.action_catalog,
        prerequisite_path=args.prerequisite_evidence,
        action_audit_dir=args.action_audit,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
