#!/usr/bin/env python3
"""Prepare a causal, cause-matched action protocol after the network top 3.

This module never runs the simulation.  It turns the final V8 network scope
into an auditable action-eligibility catalogue and, only when the network
campaign has produced a stable confirmed top 3, selects the rows that may be
tested next.  The protocol is deliberately conservative:

* no action is proposed on a lane without positive V10 reference flow;
* a second source must already be structural, active in the reference and
  explicitly qualified before it can be used;
* a closed-loop transport or allocation action needs a lane-scoped observable
  signal and may not read a future incident realization;
* quality hold is never "solved" by faster transport after receipt;
* an alternative released lot needs real released-lot evidence;
* an action the current engine/data cannot represent is labelled exactly
  ``non_simulable_avec_les_donnees_actuelles``.

The script is additive: it reads existing evidence and writes a new protocol
directory.  It does not edit the graph, cold-start logic or prior artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ARTIFACT_PARENT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_SCOPE_AUDIT = ARTIFACT_PARENT / "supplier_network_scope_audit_20260901_v8"
DEFAULT_NETWORK_PLAN = ARTIFACT_PARENT / "supplier_network_risk_screen_plan_20260901_v3"
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_CONTROL_PROVIDER = REPO_ROOT / "etudecas" / "simulation" / "engine" / "control_provider.py"
DEFAULT_CONTROL_SCHEDULE = REPO_ROOT / "etudecas" / "simulation" / "engine" / "control_schedule.py"

SCHEMA_VERSION = "etudecas.supplier_post_top3_action_protocol.v1"
EXPECTED_ACTIVE_LANES = 18
EXPECTED_ACTIVE_SUPPLIERS = 16
BUFFER_COVER_DAY_GRID = (7, 14, 28)
REFERENCE_ACTIVE_WINDOW_DAYS = 180
FAILURE_MODES = (
    "transport_delay",
    "quality_hold",
    "supply_availability",
    "quality_yield",
)

# The current canonical observation is network-wide.  It exposes aggregate
# service/backlog/material cover and an aggregate supplier-event score, but no
# supplier/item/destination key.  A fixed targeted actuator is native; an
# honest targeted feedback trigger is not yet available.
CURRENT_CONTROLLER_OBSERVATION_SCOPE = "aggregate_network_no_lane_key"
REQUIRED_TARGETED_OBSERVATION_SCOPE = "supplier_item_destination_lane"


ACTION_FIELDS = (
    "lane_key",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "downstream_products",
    "failure_mode",
    "action_id",
    "action_label",
    "timing_class",
    "physical_intent",
    "observable_trigger",
    "observation_scope_required",
    "current_observation_scope",
    "future_realisation_access",
    "detection_delay_days",
    "decision_delay_days",
    "earliest_effective_lag_days",
    "prepared_before_incident_required",
    "native_engine_actuator",
    "native_actuator_available",
    "baseline_positive_flow",
    "baseline_shipped_qty",
    "inventory_state_available",
    "initial_free_stock_qty",
    "inventory_uom",
    "structural_alternative_count",
    "active_alternative_count",
    "qualified_active_alternative_count",
    "structural_alternative_suppliers",
    "active_alternative_suppliers",
    "qualified_active_alternative_suppliers",
    "simulation_execution_allowed",
    "eligibility_status",
    "refusal_reason",
    "parameterization_rule",
    "evidence_stage",
    "not_a_recommendation",
    "evidence_notes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "oui"}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> None:
    fields = list(fieldnames or ())
    if not fields:
        seen: set[str] = set()
        for row in rows:
            for field in row:
                if field not in seen:
                    fields.append(field)
                    seen.add(field)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} absent: {resolved}")
    return resolved


def lane_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("supplier_id") or "").strip(),
        str(row.get("item_id") or "").strip(),
        str(row.get("dst_node_id") or "").strip(),
    )


def pair_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("dst_node_id") or "").strip(),
        str(row.get("item_id") or "").strip(),
    )


def active_scope_rows(scope_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in scope_rows if _as_bool(row.get("baseline_positive_flow"))]
    rows.sort(key=lambda row: lane_key(row))
    return rows


def inventory_state_index(graph: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    states: dict[tuple[str, str], dict[str, Any]] = {}
    for node in graph.get("nodes") or []:
        node_id = str(node.get("id") or "")
        inventory = node.get("inventory") or {}
        for state in inventory.get("states") or []:
            item_id = str(state.get("item_id") or "")
            if node_id and item_id:
                states[(node_id, item_id)] = dict(state)
    return states


def load_qualified_sources(path: Path | None) -> set[tuple[str, str, str]]:
    """Read an optional operational qualification register.

    Baseline flow proves that the model exercised a lane; it does not prove
    supplier qualification.  Therefore no alternative is called qualified
    without this separate register.
    """

    if path is None:
        return set()
    rows = _read_csv(_required_file(path, "registre des sources qualifiées"))
    required = {"supplier_id", "item_id", "dst_node_id", "qualification_status"}
    if rows and not required.issubset(rows[0]):
        raise ValueError(
            "Le registre de qualification doit contenir supplier_id, item_id, "
            "dst_node_id et qualification_status."
        )
    return {
        lane_key(row)
        for row in rows
        if str(row.get("qualification_status") or "").strip().lower()
        in {"qualified", "qualifie", "qualifiée", "active_qualified"}
    }


def _alternative_evidence(
    lane: Mapping[str, Any],
    all_scope_rows: Sequence[Mapping[str, Any]],
    qualified_sources: set[tuple[str, str, str]],
) -> dict[str, tuple[str, ...]]:
    supplier, item, destination = lane_key(lane)
    structural = sorted(
        {
            str(row.get("supplier_id") or "")
            for row in all_scope_rows
            if pair_key(row) == (destination, item)
            and str(row.get("supplier_id") or "") != supplier
        }
    )
    active = sorted(
        {
            str(row.get("supplier_id") or "")
            for row in all_scope_rows
            if pair_key(row) == (destination, item)
            and str(row.get("supplier_id") or "") != supplier
            and _as_bool(row.get("baseline_positive_flow"))
        }
    )
    qualified_active = tuple(
        candidate
        for candidate in active
        if (candidate, item, destination) in qualified_sources
    )
    return {
        "structural": tuple(structural),
        "active": tuple(active),
        "qualified_active": qualified_active,
    }


def _action_templates() -> tuple[dict[str, Any], ...]:
    templates: list[dict[str, Any]] = [
        {
            "failure_mode": "transport_delay",
            "action_id": "targeted_transport_after_observed_delay",
            "action_label": "Expédition ciblée ou réduction de délai après retard observé",
            "timing_class": "boucle_fermee",
            "physical_intent": (
                "Réduire le délai des seules expéditions identifiées après un signal réel."
            ),
            "observable_trigger": (
                "retard confirmé de la voie, ou baisse observée du stock composant avec backlog"
            ),
            "native_engine_actuator": "expedite_level|lead_time_adjustment_days",
            "native_actuator_available": True,
            "needs_lane_signal": True,
            "parameterization_rule": (
                "jours gagnés à renseigner depuis une promesse transporteur; aucune valeur inventée"
            ),
        },
        {
            "failure_mode": "transport_delay",
            "action_id": "prepositioned_free_stock",
            "action_label": "Stock libre prépositionné avant l'incident",
            "timing_class": "preventif",
            "physical_intent": (
                "Constituer avant la période à risque un tampon physique, libre et libéré."
            ),
            "observable_trigger": "sans objet: décision et approvisionnement avant incident",
            "native_engine_actuator": "measurement_start_stock_scale_csv",
            "native_actuator_available": True,
            "needs_inventory": True,
            "parameterization_rule": (
                "grille +7, +14 et +28 jours; seulement si l'origine physique du stock "
                "et sa disponibilité avant J0 sont prouvées"
            ),
        },
        {
            "failure_mode": "quality_hold",
            "action_id": "prepositioned_free_stock",
            "action_label": "Stock libre prépositionné avant l'incident",
            "timing_class": "preventif",
            "physical_intent": (
                "Disposer avant l'incident d'un stock utilisable, distinct des lots en quarantaine."
            ),
            "observable_trigger": "sans objet: décision et approvisionnement avant incident",
            "native_engine_actuator": "measurement_start_stock_scale_csv",
            "native_actuator_available": True,
            "needs_inventory": True,
            "parameterization_rule": "grille séparée +7, +14 et +28 jours de tirage V10",
        },
        {
            "failure_mode": "quality_hold",
            "action_id": "alternate_released_lot",
            "action_label": "Lot alternatif déjà libéré",
            "timing_class": "preventif",
            "physical_intent": "Basculer sur un vrai lot de remplacement déjà libéré.",
            "observable_trigger": "lot bloqué identifié et lot alternatif libéré vérifié",
            "native_engine_actuator": "none",
            "native_actuator_available": False,
            "needs_explicit_lot": True,
            "parameterization_rule": "identifiant batch, quantité libre, date de libération et généalogie requis",
        },
        {
            "failure_mode": "quality_hold",
            "action_id": "post_receipt_transport_expedite",
            "action_label": "Transport accéléré après réception",
            "timing_class": "boucle_fermee",
            "physical_intent": "Accélérer un transport déjà terminé.",
            "observable_trigger": "matière reçue mais non libérée",
            "native_engine_actuator": "expedite_level",
            "native_actuator_available": True,
            "cause_mismatch": True,
            "parameterization_rule": "action refusée: le transport ne raccourcit pas la quarantaine",
        },
        {
            "failure_mode": "quality_hold",
            "action_id": "post_release_transport_for_identified_lot",
            "action_label": "Transport accélé d'un lot identifié après sa libération",
            "timing_class": "boucle_fermee",
            "physical_intent": (
                "Réduire seulement le transport restant après une libération qualité observée."
            ),
            "observable_trigger": (
                "lot libéré identifié, encore expédiable, avec option transport confirmée"
            ),
            "native_engine_actuator": "expedite_level|lead_time_adjustment_days",
            "native_actuator_available": True,
            "needs_explicit_lot": True,
            "needs_lane_signal": True,
            "explicit_lot_refusal_reason": (
                "aucun_lot_identifie_avec_liberation_observee_et_transport_restant"
            ),
            "parameterization_rule": (
                "date de libération observée puis gain transport engagé; aucun "
                "raccourcissement de l'analyse ou de la quarantaine"
            ),
        },
    ]
    for failure_mode in ("supply_availability", "quality_yield"):
        templates.extend(
            [
                {
                    "failure_mode": failure_mode,
                    "action_id": "prepositioned_free_stock",
                    "action_label": "Stock libre prépositionné avant l'incident",
                    "timing_class": "preventif",
                    "physical_intent": (
                        "Créer avant l'incident un tampon physique du composant ciblé."
                    ),
                    "observable_trigger": "sans objet: décision et approvisionnement avant incident",
                    "native_engine_actuator": "measurement_start_stock_scale_csv",
                    "native_actuator_available": True,
                    "needs_inventory": True,
                    "parameterization_rule": "grille séparée +7, +14 et +28 jours de tirage V10",
                },
                {
                    "failure_mode": failure_mode,
                    "action_id": "prepared_qualified_alternative_source",
                    "action_label": "Source de repli déjà qualifiée, préparée avant incident",
                    "timing_class": "preventif",
                    "physical_intent": (
                        "Préparer contractuellement une source déjà présente, exercée et qualifiée."
                    ),
                    "observable_trigger": "sans objet: qualification et contrat avant incident",
                    "native_engine_actuator": "priority_weight_on_existing_active_lane",
                    "native_actuator_available": True,
                    "needs_active_qualified_alternative": True,
                    "parameterization_rule": (
                        "part de repli à valider; jamais external_procurement comme proxy de nouveau fournisseur"
                    ),
                },
                {
                    "failure_mode": failure_mode,
                    "action_id": "closed_loop_allocation_to_prepared_source",
                    "action_label": "Allocation vers une source préparée après signal observé",
                    "timing_class": "boucle_fermee",
                    "physical_intent": (
                        "Réallouer les commandes entre des voies déjà actives sans créer de fournisseur fictif."
                    ),
                    "observable_trigger": (
                        "réception manquante ou stock composant/backlog observé sur la voie"
                    ),
                    "native_engine_actuator": "priority_weight",
                    "native_actuator_available": True,
                    "needs_active_qualified_alternative": True,
                    "needs_lane_signal": True,
                    "parameterization_rule": "poids d'allocation à valider sur deux flux réellement actifs",
                },
            ]
        )
    return tuple(templates)


def _eligibility(
    *,
    baseline_positive_flow: bool,
    inventory_available: bool,
    inventory_initial_positive: bool,
    alternative: Mapping[str, tuple[str, ...]],
    template: Mapping[str, Any],
    lane_signal_available: bool,
    explicit_lot_available: bool,
) -> tuple[bool, str, str]:
    if not baseline_positive_flow:
        return False, "refuse", "aucun_flux_positif_dans_la_reference_v10"
    if template.get("cause_mismatch"):
        return False, "refuse", "levier_inadapte_a_la_cause"
    if template.get("needs_explicit_lot") and not explicit_lot_available:
        return (
            False,
            "non_simulable_avec_les_donnees_actuelles",
            str(
                template.get("explicit_lot_refusal_reason")
                or "aucun_registre_de_lots_alternatifs_liberes_avec_quantite_date_et_genealogie"
            ),
        )
    if template.get("needs_inventory") and not inventory_available:
        return (
            False,
            "non_simulable_avec_les_donnees_actuelles",
            "etat_de_stock_cible_absent_du_graphe",
        )
    if template.get("needs_inventory") and not inventory_initial_positive:
        return (
            False,
            "non_simulable_avec_les_donnees_actuelles",
            "actionneur_d_echelle_inapplicable_a_un_stock_initial_nul",
        )
    if template.get("needs_active_qualified_alternative"):
        if not alternative["structural"]:
            return False, "refuse", "aucune_seconde_source_structurelle"
        if not alternative["active"]:
            return (
                False,
                "refuse",
                "seconde_source_structurelle_sans_flux_positif_dans_la_reference_v10",
            )
        if not alternative["qualified_active"]:
            return (
                False,
                "refuse",
                "aucune_source_alternative_active_et_qualifiee_dans_un_registre_operationnel",
            )
    if template.get("needs_lane_signal") and not lane_signal_available:
        return (
            False,
            "non_simulable_avec_les_donnees_actuelles",
            "observation_courante_agregee_sans_cle_fournisseur_article_destination",
        )
    if not _as_bool(template.get("native_actuator_available")):
        return (
            False,
            "non_simulable_avec_les_donnees_actuelles",
            "aucun_actionneur_natif_pour_ce_levier",
        )
    return True, "simulable_sous_prerequis", ""


def build_action_catalog(
    *,
    active_lanes: Sequence[Mapping[str, Any]],
    all_scope_rows: Sequence[Mapping[str, Any]],
    inventory_states: Mapping[tuple[str, str], Mapping[str, Any]],
    qualified_sources: set[tuple[str, str, str]] | None = None,
    lane_signal_available: bool = False,
    explicit_lot_available: bool = False,
    detection_delay_days: int = 1,
    decision_delay_days: int = 1,
) -> list[dict[str, Any]]:
    if detection_delay_days < 0 or decision_delay_days < 1:
        raise ValueError("Le délai de détection doit être >=0 et celui de décision >=1.")
    qualified_sources = qualified_sources or set()
    rows: list[dict[str, Any]] = []
    for lane in active_lanes:
        supplier, item, destination = lane_key(lane)
        state = inventory_states.get((destination, item))
        alternative = _alternative_evidence(lane, all_scope_rows, qualified_sources)
        positive_flow = _as_bool(lane.get("baseline_positive_flow"))
        for template in _action_templates():
            timing = str(template["timing_class"])
            allowed, status, reason = _eligibility(
                baseline_positive_flow=positive_flow,
                inventory_available=state is not None,
                inventory_initial_positive=(
                    state is not None and _to_float(state.get("initial")) > 1e-12
                ),
                alternative=alternative,
                template=template,
                lane_signal_available=lane_signal_available,
                explicit_lot_available=explicit_lot_available,
            )
            closed_loop = timing == "boucle_fermee"
            rows.append(
                {
                    "lane_key": "|".join((supplier, item, destination)),
                    "supplier_id": supplier,
                    "item_id": item,
                    "dst_node_id": destination,
                    "downstream_products": str(lane.get("downstream_products") or ""),
                    "failure_mode": template["failure_mode"],
                    "action_id": template["action_id"],
                    "action_label": template["action_label"],
                    "timing_class": timing,
                    "physical_intent": template["physical_intent"],
                    "observable_trigger": template["observable_trigger"],
                    "observation_scope_required": (
                        REQUIRED_TARGETED_OBSERVATION_SCOPE if closed_loop else "not_applicable"
                    ),
                    "current_observation_scope": CURRENT_CONTROLLER_OBSERVATION_SCOPE,
                    "future_realisation_access": False,
                    "detection_delay_days": detection_delay_days if closed_loop else "",
                    "decision_delay_days": decision_delay_days if closed_loop else "",
                    "earliest_effective_lag_days": (
                        detection_delay_days + decision_delay_days if closed_loop else ""
                    ),
                    "prepared_before_incident_required": timing == "preventif",
                    "native_engine_actuator": template["native_engine_actuator"],
                    "native_actuator_available": template["native_actuator_available"],
                    "baseline_positive_flow": positive_flow,
                    "baseline_shipped_qty": _to_float(lane.get("baseline_shipped_qty")),
                    "inventory_state_available": state is not None,
                    "initial_free_stock_qty": _to_float((state or {}).get("initial")),
                    "inventory_uom": str((state or {}).get("uom") or lane.get("uom") or ""),
                    "structural_alternative_count": len(alternative["structural"]),
                    "active_alternative_count": len(alternative["active"]),
                    "qualified_active_alternative_count": len(
                        alternative["qualified_active"]
                    ),
                    "structural_alternative_suppliers": "|".join(alternative["structural"]),
                    "active_alternative_suppliers": "|".join(alternative["active"]),
                    "qualified_active_alternative_suppliers": "|".join(
                        alternative["qualified_active"]
                    ),
                    "simulation_execution_allowed": allowed,
                    "eligibility_status": status,
                    "refusal_reason": reason,
                    "parameterization_rule": template["parameterization_rule"],
                    "evidence_stage": "protocol_before_action_runs",
                    "not_a_recommendation": True,
                    "evidence_notes": (
                        "Éligibilité technique et physique seulement; coût, contrat, qualification "
                        "et faisabilité opérationnelle restent à valider."
                    ),
                }
            )
    rows.sort(
        key=lambda row: (
            str(row["supplier_id"]),
            str(row["item_id"]),
            str(row["dst_node_id"]),
            FAILURE_MODES.index(str(row["failure_mode"])),
            str(row["action_id"]),
        )
    )
    return rows


def _holding_cost_fields(state: Mapping[str, Any]) -> tuple[float, float]:
    holding = state.get("holding_cost") or {}
    return (
        _to_float(holding.get("value")),
        _to_float(holding.get("unit_value_basis")),
    )


def build_buffer_grid(
    *,
    active_lanes: Sequence[Mapping[str, Any]],
    active_reference_rows: Sequence[Mapping[str, Any]],
    inventory_states: Mapping[tuple[str, str], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    reference_by_lane = {lane_key(row): row for row in active_reference_rows}
    output: list[dict[str, Any]] = []
    for lane in active_lanes:
        key = lane_key(lane)
        reference = reference_by_lane.get(key)
        state = inventory_states.get(pair_key(lane))
        initial = _to_float((state or {}).get("initial"))
        pulled = _to_float((reference or {}).get("reference_active_window_pulled_qty"))
        average_daily_pull = pulled / REFERENCE_ACTIVE_WINDOW_DAYS
        holding_cost, unit_value = _holding_cost_fields(state or {})
        for cover_days in BUFFER_COVER_DAY_GRID:
            additional_qty = average_daily_pull * cover_days
            scale = (initial + additional_qty) / initial if initial > 1e-12 else None
            status = (
                "parametre_natif_prepare_non_recommande_avant_top3"
                if scale is not None and additional_qty > 1e-12
                else "non_simulable_avec_les_donnees_actuelles"
            )
            reason = ""
            if reference is None:
                status = "non_simulable_avec_les_donnees_actuelles"
                reason = "reference_de_fenetre_active_absente"
            elif pulled <= 1e-12:
                status = "non_simulable_avec_les_donnees_actuelles"
                reason = "aucun_tirage_dans_la_fenetre_active"
            elif initial <= 1e-12:
                status = "non_simulable_avec_les_donnees_actuelles"
                reason = "echelle_multiplicative_inapplicable_a_un_stock_initial_nul"
            output.append(
                {
                    "lane_key": "|".join(key),
                    "supplier_id": key[0],
                    "item_id": key[1],
                    "dst_node_id": key[2],
                    "downstream_products": str(lane.get("downstream_products") or ""),
                    "applicable_failure_modes": (
                        "transport_delay|quality_hold|supply_availability|quality_yield"
                    ),
                    "buffer_cover_days": cover_days,
                    "active_window_start_day": (reference or {}).get(
                        "active_window_start_day", ""
                    ),
                    "active_window_end_day": (reference or {}).get(
                        "active_window_end_day", ""
                    ),
                    "reference_active_window_pulled_qty": pulled,
                    "reference_average_daily_pull_qty": average_daily_pull,
                    "initial_free_stock_qty": initial,
                    "additional_free_stock_qty": additional_qty,
                    "measurement_start_stock_scale": scale if scale is not None else "",
                    "uom": str((state or {}).get("uom") or lane.get("uom") or ""),
                    "holding_cost_per_unit_day_model": holding_cost,
                    "incremental_holding_cost_over_180d_model": (
                        additional_qty * holding_cost * REFERENCE_ACTIVE_WINDOW_DAYS
                    ),
                    "incremental_inventory_value_model_basis": additional_qty * unit_value,
                    "parameter_status": status,
                    "refusal_reason": reason,
                    "not_a_recommendation": True,
                    "interpretation": (
                        "Grille de test dérivée du tirage de la référence simulée V10; "
                        "ni stock observé recommandé ni engagement d'achat."
                    ),
                }
            )
    return output


def validate_scope_contract(
    *,
    scope_manifest: Mapping[str, Any],
    active_lanes: Sequence[Mapping[str, Any]],
    active_reference_rows: Sequence[Mapping[str, Any]],
    expected_active_lanes: int,
) -> dict[str, Any]:
    if str(scope_manifest.get("status") or "") != "complete":
        raise ValueError("L'audit de périmètre V8 doit être complet.")
    if int(scope_manifest.get("lane_count") or 0) != 33:
        raise ValueError("L'audit final attendu doit contenir 33 voies structurelles.")
    if len(active_lanes) != expected_active_lanes:
        raise ValueError(
            f"{expected_active_lanes} voies actives attendues, {len(active_lanes)} trouvées."
        )
    active_keys = {lane_key(row) for row in active_lanes}
    reference_keys = {lane_key(row) for row in active_reference_rows}
    if active_keys != reference_keys:
        raise ValueError(
            "La référence de fenêtre active ne correspond pas exactement aux voies V8 actives."
        )
    return {
        "structural_lane_count": int(scope_manifest.get("lane_count") or 0),
        "active_lane_count": len(active_lanes),
        "active_supplier_count": len({key[0] for key in active_keys}),
        "active_reference_exact_match": True,
    }


def select_confirmed_top3(network_results: Path) -> tuple[list[str], dict[str, Any]]:
    """Return only a top 3 passing the consolidated V2 scientific gates.

    The historical 10-realisation fields are deliberately ignored.  The
    authoritative implementation lives in the additive V2 selector so both
    entry points enforce the same 30-realisation and extension gates.
    """

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v2_controllable_action_selector as v2_selector,
    )

    supplier_ids, evidence = v2_selector._stable_v2_suppliers(network_results)
    if not supplier_ids:
        return [], {
            "selection_status": "selection_refused_v2_not_stabilized",
            "selection_reason": str(evidence.get("selection_reason") or ""),
        }
    return supplier_ids, {
        "selection_status": "stabilized_v2_top3_selected",
        "selection_reason": "",
    }


def _report_text(
    *,
    mode: str,
    scope_contract: Mapping[str, Any],
    catalog: Sequence[Mapping[str, Any]],
    buffer_grid: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    selected_suppliers: Sequence[str],
) -> str:
    status_counts = Counter(str(row.get("eligibility_status") or "") for row in catalog)
    executable = sum(_as_bool(row.get("simulation_execution_allowed")) for row in catalog)
    return f"""# Protocole d'actions après les trois priorités réseau

## Ce que ce dossier est

Ce dossier prépare les essais d'actions; il ne contient **aucune nouvelle simulation** et ne recommande aucune décision industrielle. Il couvre {scope_contract['active_lane_count']} voies actives et {scope_contract['active_supplier_count']} fournisseurs de la référence V10 sans commandes initiales.

Mode : `{mode}`. Sélection : `{selection.get('selection_status')}`. Fournisseurs sélectionnés : `{', '.join(selected_suppliers) if selected_suppliers else 'aucun avant confirmation stable'}`.

## Règles physiques

- retard transport : tampon libre constitué avant la période à risque, ou réduction de délai ciblée après un retard réellement observable ;
- attente qualité : stock libre préparé avant l'incident ou vrai lot alternatif déjà libéré ; un transport ne peut intervenir qu'après libération et ne réduit jamais la quarantaine ;
- disponibilité/rendement : tampon préventif ou source de repli déjà active et qualifiée ; aucun achat externe ne sert de faux nouveau fournisseur ;
- aucune action sur une voie sans flux positif ;
- une voie structurelle sans flux n'est pas une source de repli exercée ;
- une action non représentable est marquée `non_simulable_avec_les_donnees_actuelles`.

## Préventif et boucle fermée

Le stock libre et la source de repli doivent être préparés **avant** l'incident. Les actions de transport ou d'allocation sont, elles, déclenchées uniquement après un signal observable. Le protocole impose {catalog[0]['detection_delay_days'] if catalog else 1} jour de détection/confirmation et {catalog[0]['decision_delay_days'] if catalog else 1} jour de décision pour les lignes en boucle fermée, soit un effet au plus tôt deux jours après le premier signal. L'accès à la réalisation future est interdit.

Le contrôleur actuel observe le réseau de façon agrégée, sans clé fournisseur–article–destination. Les actionneurs ciblés existent, mais leur déclenchement ciblé en boucle fermée n'est donc pas encore revendiqué comme simulable. Il faudra d'abord ajouter et tester une observation de voie causale.

## État de préparation

- actions simulables sous prérequis : {executable} ;
- statuts : {dict(sorted(status_counts.items()))} ;
- paramètres de tampon préparés : {len(buffer_grid)} lignes ({len(BUFFER_COVER_DAY_GRID)} niveaux par voie) ;
- simulations exécutées : 0.

La grille +7/+14/+28 jours est un plan d'essais dérivé du tirage **simulé** V10, pas un niveau de stock observé ni une recommandation. Après confirmation stable des trois priorités, seuls les leviers compatibles avec la cause et ayant passé ces gardes pourront être exécutés.
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("plan", "post-top3"), default="plan")
    parser.add_argument("--scope-audit", type=Path, default=DEFAULT_SCOPE_AUDIT)
    parser.add_argument("--network-plan", type=Path, default=DEFAULT_NETWORK_PLAN)
    parser.add_argument(
        "--network-results",
        type=Path,
        help="Dossier réseau V2 consolidé; obligatoire en mode post-top3.",
    )
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--qualified-source-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-active-lanes", type=int, default=EXPECTED_ACTIVE_LANES)
    parser.add_argument("--detection-delay-days", type=int, default=1)
    parser.add_argument("--decision-delay-days", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Le dossier de protocole existe déjà et n'est pas vide: {output_dir}"
        )

    scope_dir = args.scope_audit.resolve()
    plan_dir = args.network_plan.resolve()
    scope_manifest_path = _required_file(scope_dir / "manifest.json", "manifeste V8")
    scope_csv_path = _required_file(
        scope_dir / "supplier_lane_scope.csv", "périmètre fournisseur V8"
    )
    network_plan_manifest_path = _required_file(
        plan_dir / "campaign_manifest.json", "manifeste du plan réseau"
    )
    active_reference_path = _required_file(
        plan_dir / "active_lane_reference.csv", "fenêtres actives réseau"
    )
    graph_path = _required_file(args.graph, "graphe")
    scope_manifest = _read_json(scope_manifest_path)
    network_plan_manifest = _read_json(network_plan_manifest_path)
    if int(network_plan_manifest.get("active_lane_count") or 0) != EXPECTED_ACTIVE_LANES:
        raise ValueError("Le plan réseau doit annoncer 18 voies actives.")
    scope_rows = _read_csv(scope_csv_path)
    active_lanes = active_scope_rows(scope_rows)
    active_reference_rows = _read_csv(active_reference_path)
    scope_contract = validate_scope_contract(
        scope_manifest=scope_manifest,
        active_lanes=active_lanes,
        active_reference_rows=active_reference_rows,
        expected_active_lanes=args.expected_active_lanes,
    )
    if scope_contract["active_supplier_count"] != EXPECTED_ACTIVE_SUPPLIERS:
        raise ValueError("Le périmètre final doit contenir 16 fournisseurs actifs.")
    graph = _read_json(graph_path)
    inventory_states = inventory_state_index(graph)
    qualified_sources = load_qualified_sources(args.qualified_source_csv)
    catalog = build_action_catalog(
        active_lanes=active_lanes,
        all_scope_rows=scope_rows,
        inventory_states=inventory_states,
        qualified_sources=qualified_sources,
        lane_signal_available=False,
        explicit_lot_available=False,
        detection_delay_days=args.detection_delay_days,
        decision_delay_days=args.decision_delay_days,
    )
    buffer_grid = build_buffer_grid(
        active_lanes=active_lanes,
        active_reference_rows=active_reference_rows,
        inventory_states=inventory_states,
    )
    if args.mode == "post-top3":
        if args.network_results is None:
            raise ValueError("--network-results est obligatoire en mode post-top3.")
        selected_suppliers, selection = select_confirmed_top3(args.network_results.resolve())
    else:
        selected_suppliers = []
        selection = {
            "selection_status": "prepared_waiting_for_confirmed_top3",
            "selection_reason": "network_full_campaign_not_consumed_in_plan_mode",
        }
    selected_catalog = [
        row for row in catalog if str(row.get("supplier_id")) in set(selected_suppliers)
    ]
    rejected = [
        row for row in catalog if not _as_bool(row.get("simulation_execution_allowed"))
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "action_eligibility_catalog.csv", catalog, fieldnames=ACTION_FIELDS)
    _write_csv(output_dir / "rejected_actions.csv", rejected, fieldnames=ACTION_FIELDS)
    _write_csv(
        output_dir / "selected_top3_action_protocol.csv",
        selected_catalog,
        fieldnames=ACTION_FIELDS,
    )
    _write_csv(output_dir / "buffer_level_grid.csv", buffer_grid)
    report = _report_text(
        mode=args.mode,
        scope_contract=scope_contract,
        catalog=catalog,
        buffer_grid=buffer_grid,
        selection=selection,
        selected_suppliers=selected_suppliers,
    )
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")

    status_counts = Counter(str(row["eligibility_status"]) for row in catalog)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "prepared",
        "mode": args.mode,
        "created_at_utc": utc_now(),
        "selection_status": selection["selection_status"],
        "selection_reason": selection["selection_reason"],
        "selected_supplier_ids": selected_suppliers,
        "scope_contract": scope_contract,
        "action_row_count": len(catalog),
        "rejected_or_not_currently_simulable_action_row_count": len(rejected),
        "currently_executable_action_row_count": len(catalog) - len(rejected),
        "eligibility_status_counts": dict(sorted(status_counts.items())),
        "buffer_grid_row_count": len(buffer_grid),
        "simulation_run_count": 0,
        "future_realisation_access": False,
        "closed_loop_timing": {
            "detection_delay_days": args.detection_delay_days,
            "decision_delay_days": args.decision_delay_days,
            "earliest_effective_lag_days": (
                args.detection_delay_days + args.decision_delay_days
            ),
            "contract": "first_observable_signal_then_detection_then_decision_no_future_read",
        },
        "controller_observation_contract": {
            "current_scope": CURRENT_CONTROLLER_OBSERVATION_SCOPE,
            "required_scope": REQUIRED_TARGETED_OBSERVATION_SCOPE,
            "targeted_closed_loop_currently_claimable": False,
        },
        "source_switch_contract": {
            "requires_structural_alternative": True,
            "requires_positive_v10_flow_on_alternative": True,
            "requires_explicit_operational_qualification_register": True,
            "external_procurement_is_not_a_new_supplier_proxy": True,
        },
        "quality_contract": {
            "post_receipt_transport_cannot_reduce_quality_hold": True,
            "alternate_lot_requires_real_released_lot_register": True,
        },
        "provenance": {
            "scope_audit_v8": str(scope_dir),
            "scope_manifest_sha256": _sha256(scope_manifest_path),
            "scope_csv_sha256": _sha256(scope_csv_path),
            "network_plan": str(plan_dir),
            "network_plan_manifest_sha256": _sha256(network_plan_manifest_path),
            "active_lane_reference_sha256": _sha256(active_reference_path),
            "graph": str(graph_path),
            "graph_sha256": _sha256(graph_path),
            "qualified_source_register": str(args.qualified_source_csv or ""),
            "qualified_source_register_sha256": (
                _sha256(args.qualified_source_csv.resolve())
                if args.qualified_source_csv
                else ""
            ),
            "control_provider": str(DEFAULT_CONTROL_PROVIDER),
            "control_provider_sha256": _sha256(DEFAULT_CONTROL_PROVIDER),
            "control_schedule": str(DEFAULT_CONTROL_SCHEDULE),
            "control_schedule_sha256": _sha256(DEFAULT_CONTROL_SCHEDULE),
            "script": str(Path(__file__).resolve()),
            "script_sha256": _sha256(Path(__file__).resolve()),
        },
        "preservation": {
            "cold_start_modified": False,
            "graph_modified": False,
            "previous_artifacts_modified": False,
            "additive_output_only": True,
        },
        "outputs": [
            "action_eligibility_catalog.csv",
            "rejected_actions.csv",
            "selected_top3_action_protocol.csv",
            "buffer_level_grid.csv",
            "REPORT.md",
        ],
    }
    _write_json(output_dir / "protocol_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
