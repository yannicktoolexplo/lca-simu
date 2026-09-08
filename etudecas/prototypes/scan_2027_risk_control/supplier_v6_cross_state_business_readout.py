#!/usr/bin/env python3
"""Build an additive cross-state supplier-risk business readout.

This post-processor starts no simulation.  It reopens the validated campaign,
physical-qualification and optional action aggregates, then answers one narrow
question: do the same supplier/lane signals remain priorities under the same
stress mechanism at the approximately 100 %, 93 % and 80 % service states?

The output is deliberately separate from every V6 campaign artifact.  It
creates a CSV, a JSON and one standalone three-view French HTML document in a
new directory and refuses to overwrite an existing directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import shutil
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_qualification,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v4_final_standalone_delivery as delivery_v4,
)


SCHEMA_VERSION = "etudecas.supplier_v6_cross_state_business_readout.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"

CSV_FILE = "comparaison_fournisseurs_3_etats.csv"
JSON_FILE = "comparaison_fournisseurs_3_etats.json"
HTML_FILE = "OUVRIR_COMPARAISON_FOURNISSEURS_3_ETATS.html"
MANIFEST_FILE = "comparaison_fournisseurs_3_etats.manifest.json"

STATE_IDS = ("op_100", "op_93", "op_80")
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
SIGNAL_STATUSES = frozenset({"robust_priority", "dossier_to_investigate"})
ALLOWED_PRIORITY_STATUSES = frozenset(
    {
        *SIGNAL_STATUSES,
        "supplementary_backlog_signal",
        "detected_lower_priority",
        "global_only_not_confirmed_within_target_product",
        "no_detected_effect",
    }
)
EXPECTED_REPETITIONS = 30
EXPECTED_LANES = 18
EXPECTED_BOOTSTRAP_REPLICATES = 10_000
EXPECTED_DISRUPTION_WINDOW_DAYS = 42
EXPECTED_BUSINESS_WINDOW_DAYS = 360
EXPECTED_DEGRADATION_FAMILY = "balanced_product_supplier_planned_lead"
EXPECTED_DEGRADATION_SCOPE = "planned_supplier_lead_offsets_by_finished_product_feed"
EXPECTED_PRIMARY_METRIC = "impact_service_loss_fed_product_pp"
NUMERIC_TOLERANCE = 1e-9

PRIORITY_FILE = "priority_suppliers_by_cause_state.csv"
STABILITY_FILE = "supplier_priority_stability_by_cause.csv"


class CrossStateReadoutError(ValueError):
    """The official aggregates cannot support the requested business claim."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CrossStateReadoutError(f"JSON officiel illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise CrossStateReadoutError(f"Objet JSON attendu : {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise CrossStateReadoutError(f"CSV sans en-tête : {path}")
            return list(reader)
    except OSError as exc:
        raise CrossStateReadoutError(f"CSV officiel illisible : {path}") from exc


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, *, label: str, optional: bool = False) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if optional:
            return None
        raise CrossStateReadoutError(f"Valeur numérique absente : {label}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CrossStateReadoutError(f"Valeur numérique invalide : {label}") from exc
    if not math.isfinite(result):
        raise CrossStateReadoutError(f"Valeur non finie : {label}")
    return result


def _integer(value: Any, *, label: str, optional: bool = False) -> int | None:
    number = _number(value, label=label, optional=optional)
    if number is None:
        return None
    rounded = round(number)
    if not math.isclose(number, rounded, rel_tol=0.0, abs_tol=1e-9):
        raise CrossStateReadoutError(f"Entier attendu : {label}")
    return int(rounded)


def _boolean(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    normalised = _text(value).casefold()
    if normalised in {"1", "true", "yes", "oui"}:
        return True
    if normalised in {"0", "false", "no", "non"}:
        return False
    raise CrossStateReadoutError(f"Booléen officiel invalide : {label}")


def _require_fields(row: Mapping[str, Any], fields: set[str], *, label: str) -> None:
    missing = sorted(field for field in fields if field not in row)
    if missing:
        raise CrossStateReadoutError(
            f"Colonnes absentes dans {label} : {', '.join(missing)}"
        )


def _validate_campaign_contract(validation: Mapping[str, Any]) -> dict[str, Any]:
    """Validate every official rule repeated in the business wording."""

    # The V6 runner/finalizer adapters deliberately reuse the byte-pinned V4
    # result schema.  V6 identity is carried by the already validated campaign
    # source chain, while the final aggregate contract therefore remains V4.
    contract = validation.get("expected_contract")
    statistics = validation.get("statistics")
    checks = validation.get("comparability_checks")
    if not all(isinstance(value, Mapping) for value in (contract, statistics, checks)):
        raise CrossStateReadoutError("Contrat scientifique officiel incomplet")
    if (
        validation.get("schema_version")
        != delivery_v4.campaign_dashboard.FINALIZER_SCHEMA_VERSION
        or validation.get("status") != "complete_validated"
        or not re.fullmatch(
            r"[0-9a-f]{64}", _text(validation.get("campaign_signature"))
        )
        or tuple(contract.get("mechanisms") or ()) != MECHANISMS
        or _integer(contract.get("operating_point_count"), label="points officiels")
        != len(STATE_IDS)
        or _integer(contract.get("lane_count"), label="voies officielles")
        != EXPECTED_LANES
        or _integer(
            contract.get("paired_repetition_count"), label="répétitions officielles"
        )
        != EXPECTED_REPETITIONS
        or _integer(contract.get("baseline_row_count"), label="références officielles")
        != 90
        or _integer(contract.get("incident_row_count"), label="incidents officiels")
        != 3240
        or contract.get("operating_point_degradation_family")
        != EXPECTED_DEGRADATION_FAMILY
        or contract.get("operating_point_degradation_scope")
        != EXPECTED_DEGRADATION_SCOPE
        or _integer(
            contract.get("supplier_disruption_window_days"),
            label="fenêtre fournisseur officielle",
        )
        != EXPECTED_DISRUPTION_WINDOW_DAYS
        or _integer(
            contract.get("business_window_days"), label="fenêtre métier officielle"
        )
        != EXPECTED_BUSINESS_WINDOW_DAYS
        or _integer(
            contract.get("lot_replay_dossier_maximum"),
            label="maximum de dossiers lots",
        )
        != 3
        or contract.get("lot_replay_forced_top3") is not False
        or contract.get("quality_branch_included") is not False
        or contract.get("availability_incident_included") is not False
        or contract.get("all_lots_traced_claimed") is not False
    ):
        raise CrossStateReadoutError("Contrat de campagne officiel différent")
    required_checks = {
        "complete_3x18x2x30_matrix",
        "same_repetitions_in_every_cell",
        "same_engine_sha256",
        "same_campaign_signature",
        "lane_identity_invariant",
        "baseline_pairing_complete",
        "paired_warmup_state_identical",
        "shipment_set_and_incident_trace_proven",
        "business_360_and_causal_windows_fully_observed",
        "all_3330_metrics_reconstructed_from_signed_case_evidence",
    }
    if any(checks.get(field) is not True for field in required_checks):
        raise CrossStateReadoutError("Preuves de comparabilité officielles incomplètes")
    if (
        statistics.get("primary_ranking_metric") != EXPECTED_PRIMARY_METRIC
        or statistics.get("primary_window") != "fixed_360_day_business_envelope"
        or statistics.get("confidence_interval")
        != "paired non-parametric bootstrap percentile interval"
        or _integer(
            statistics.get("bootstrap_replicates"),
            label="rééchantillonnages bootstrap",
        )
        != EXPECTED_BOOTSTRAP_REPLICATES
        or statistics.get("bootstrap_pairing")
        != "one common paired-seed resample for every campaign cell"
        or statistics.get("effect_detection")
        != "CI95 lower bound > 0 and at least 24 of 30 paired effects > 0"
        or statistics.get("supplier_aggregation")
        != "maximum tested lane, labelled voie la plus exposée"
        or statistics.get("robust_priority")
        != "P(bootstrap rank_max <= 3) >= 0.80 after effect detection"
        or statistics.get("dossier_to_investigate")
        != (
            "P(bootstrap rank_min <= 3) >= 0.20 after effect detection; "
            "descriptive review signal, not a forced top-three label"
        )
        or statistics.get("forced_top3") is not False
        or validation.get("historical_incident_probability_estimated") is not False
        or validation.get("industrial_supplier_criticality_claimed") is not False
    ):
        raise CrossStateReadoutError("Contrat statistique officiel différent")
    return {
        "campaign_signature": _text(validation.get("campaign_signature")),
        "degradation_family": contract.get("operating_point_degradation_family"),
        "disruption_window_days": EXPECTED_DISRUPTION_WINDOW_DAYS,
        "business_window_days": EXPECTED_BUSINESS_WINDOW_DAYS,
        "primary_metric": EXPECTED_PRIMARY_METRIC,
        "bootstrap_replicates": EXPECTED_BOOTSTRAP_REPLICATES,
        "forced_top3": False,
    }


def _validated_output_csv(
    *, results_dir: Path, validation: Mapping[str, Any], filename: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    outputs = validation.get("outputs")
    declared = outputs.get(filename) if isinstance(outputs, Mapping) else None
    path = (results_dir / filename).resolve()
    if not isinstance(declared, Mapping) or not path.is_file():
        raise CrossStateReadoutError(f"Agrégat officiel absent : {filename}")
    actual_sha = sha256_file(path)
    if _text(declared.get("sha256")) != actual_sha:
        raise CrossStateReadoutError(f"Empreinte officielle différente : {filename}")
    rows = _read_csv(path)
    declared_count = _integer(
        declared.get("row_count"), label=f"nombre de lignes {filename}"
    )
    if declared_count != len(rows):
        raise CrossStateReadoutError(f"Nombre de lignes différent : {filename}")
    return rows, {
        "path": str(path),
        "sha256": actual_sha,
        "row_count": len(rows),
    }


def load_official_inputs(
    *,
    campaign_root: Path,
    results_dir: Path,
    qualification_dir: Path,
    lot_replay_root: Path,
    action_results_root: Path | None,
    target_registry_path: Path | None,
) -> tuple[
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """Reopen only finalized, source-bound aggregates; never call the engine."""

    try:
        campaign, campaign_binding = delivery_v4.load_campaign_payload(
            campaign_root=campaign_root.resolve(),
            results_dir=results_dir.resolve(),
            target_registry_path=(
                target_registry_path.resolve() if target_registry_path else None
            ),
        )
    except Exception as exc:
        raise CrossStateReadoutError(f"Campagne officielle refusée : {exc}") from exc

    validation_path = (results_dir / "campaign_validation.json").resolve()
    validation = _read_json(validation_path)
    official_contract = _validate_campaign_contract(validation)
    priority_rows, priority_binding = _validated_output_csv(
        results_dir=results_dir.resolve(),
        validation=validation,
        filename=PRIORITY_FILE,
    )
    stability_rows, stability_binding = _validated_output_csv(
        results_dir=results_dir.resolve(),
        validation=validation,
        filename=STABILITY_FILE,
    )
    try:
        qualification = physical_qualification.validate_qualification_sidecar(
            campaign_root=campaign_root.resolve(),
            results_dir=results_dir.resolve(),
            replay_root=lot_replay_root.resolve(),
            output_dir=qualification_dir.resolve(),
        )
    except Exception as exc:
        raise CrossStateReadoutError(
            f"Qualification physique officielle refusée : {exc}"
        ) from exc
    try:
        actions, action_binding = delivery_v4.load_action_payload(
            action_results_root=(
                action_results_root.resolve() if action_results_root else None
            ),
            campaign=campaign,
            campaign_binding=campaign_binding,
        )
    except Exception as exc:
        raise CrossStateReadoutError(f"Résultats d'actions refusés : {exc}") from exc

    bindings = {
        "campaign": campaign_binding,
        "campaign_validation": {
            "path": str(validation_path),
            "sha256": sha256_file(validation_path),
            "campaign_signature": validation.get("campaign_signature"),
            "official_contract": official_contract,
        },
        "supplier_priority": priority_binding,
        "supplier_stability": stability_binding,
        "physical_qualification": {
            "path": str(qualification_dir.resolve()),
            "qualification_signature": qualification.get("qualification_signature"),
            "scope_signature": qualification.get("scope_signature"),
        },
        "actions": action_binding,
    }
    return campaign, priority_rows, stability_rows, qualification, actions, bindings


def _metric_from_priority(row: Mapping[str, Any]) -> dict[str, Any]:
    stem = EXPECTED_PRIMARY_METRIC
    result = {
        "mean": _number(row.get(f"{stem}_mean"), label="impact moyen"),
        "median": _number(row.get(f"{stem}_median"), label="impact médian"),
        "p10": _number(row.get(f"{stem}_p10"), label="impact P10"),
        "p90": _number(row.get(f"{stem}_p90"), label="impact P90"),
        "ci95Low": _number(row.get(f"{stem}_ci95_low"), label="impact IC95 bas"),
        "ci95High": _number(row.get(f"{stem}_ci95_high"), label="impact IC95 haut"),
        "positiveEffectRate": _number(
            row.get(f"{stem}_positive_effect_rate"), label="fréquence d'effet"
        ),
        "positiveEffectCount": _integer(
            row.get(f"{stem}_positive_effect_count"), label="nombre d'effets positifs"
        ),
    }
    if not (
        result["p10"] <= result["median"] + NUMERIC_TOLERANCE
        and result["median"] <= result["p90"] + NUMERIC_TOLERANCE
        and result["ci95Low"] <= result["ci95High"] + NUMERIC_TOLERANCE
        and 0.0 <= result["positiveEffectRate"] <= 1.0
        and 0 <= result["positiveEffectCount"] <= EXPECTED_REPETITIONS
        and math.isclose(
            result["positiveEffectRate"],
            result["positiveEffectCount"] / EXPECTED_REPETITIONS,
            rel_tol=0.0,
            abs_tol=NUMERIC_TOLERANCE,
        )
    ):
        raise CrossStateReadoutError("Dispersion d'impact fournisseur incohérente")
    return result


def _rank_from_priority(
    row: Mapping[str, Any], *, expected_supplier_count: int
) -> dict[str, Any]:
    result = {
        "position": _integer(row.get("position"), label="position"),
        "rankMin": _integer(row.get("rank_min"), label="rang minimal"),
        "rankMax": _integer(row.get("rank_max"), label="rang maximal"),
        "rankMedian": _number(row.get("rank_median"), label="rang médian"),
        "rankCi95Low": _number(
            row.get("bootstrap_rank_ci95_low"), label="IC95 de rang bas"
        ),
        "rankCi95High": _number(
            row.get("bootstrap_rank_ci95_high"), label="IC95 de rang haut"
        ),
        "top3InclusionProbability": _number(
            row.get("bootstrap_top3_inclusion_probability"),
            label="fréquence bootstrap groupe de tête",
        ),
        "unambiguousTop3Probability": _number(
            row.get("bootstrap_unambiguous_top3_probability"),
            label="fréquence bootstrap groupe de tête sans ambiguïté",
        ),
    }
    probabilities = (
        result["top3InclusionProbability"],
        result["unambiguousTop3Probability"],
    )
    if (
        any(value < 0.0 or value > 1.0 for value in probabilities)
        or result["unambiguousTop3Probability"]
        > result["top3InclusionProbability"] + NUMERIC_TOLERANCE
        or result["position"] != result["rankMin"]
        or not 1 <= result["rankMin"] <= expected_supplier_count
        or not 1 <= result["rankMax"] <= expected_supplier_count
        or result["rankMin"] > result["rankMax"]
        or not 1.0 <= result["rankMedian"] <= float(expected_supplier_count)
        or not 1.0 <= result["rankCi95Low"] <= float(expected_supplier_count)
        or not 1.0 <= result["rankCi95High"] <= float(expected_supplier_count)
        or result["rankCi95Low"] > result["rankCi95High"] + NUMERIC_TOLERANCE
    ):
        raise CrossStateReadoutError("Robustesse de rang incohérente")
    return result


def _state_result(
    row: Mapping[str, Any],
    qualification_by_lane: Mapping[str, Mapping[str, Any]],
    qualification_by_cell: Mapping[tuple[str, str, str], Mapping[str, Any]],
    *,
    expected_supplier_count: int,
) -> dict[str, Any]:
    required = {
        "operating_point_id",
        "mechanism",
        "supplier_id",
        "exposed_lane_id",
        "item_id",
        "dst_node_id",
        "target_product_id",
        "paired_repetition_count",
        "physical_exercise_rate",
        "priority_status",
        "model_effect_detected",
        "horizon_dependent",
    }
    _require_fields(row, required, label=PRIORITY_FILE)
    state = _text(row.get("operating_point_id"))
    mechanism = _text(row.get("mechanism"))
    lane = _text(row.get("exposed_lane_id"))
    supplier = _text(row.get("supplier_id"))
    item = _text(row.get("item_id"))
    destination = _text(row.get("dst_node_id"))
    target_product = _text(row.get("target_product_id"))
    priority_status = _text(row.get("priority_status"))
    if (
        state not in STATE_IDS
        or mechanism not in MECHANISMS
        or not all((supplier, lane, item, destination, target_product))
        or priority_status not in ALLOWED_PRIORITY_STATUSES
    ):
        raise CrossStateReadoutError("Identité état/mécanisme/voie invalide")
    proof = qualification_by_lane.get(lane)
    if proof is None:
        raise CrossStateReadoutError(f"Qualification physique absente pour {lane}")
    if (
        proof.get("full_dynamic_stock_mrp_production_service_cascade_proven")
        is not False
        or proof.get("complete_cascade_label_allowed") is not False
        or _text(proof.get("proof_level"))
        not in {"not_exercised", "partial", "complete"}
        or _text(proof.get("mrp_requirement_mode"))
        not in {"dynamic_explicit", "static_explicit"}
        or not _text(proof.get("display_label_fr"))
        or _text(proof.get("supplier_id")) != supplier
        or _text(proof.get("item_id")).removeprefix("item:")
        != item.removeprefix("item:")
        or _text(proof.get("dst_node_id")) != destination
        or _text(proof.get("target_product_id")).removeprefix("item:")
        != target_product.removeprefix("item:")
    ):
        raise CrossStateReadoutError("Revendication de cascade dynamique interdite")
    paired_count = _integer(
        row.get("paired_repetition_count"), label="simulations appariées"
    )
    exercise_rate = _number(
        row.get("physical_exercise_rate"), label="taux d'exercice physique"
    )
    if paired_count != EXPECTED_REPETITIONS or not 0.0 <= exercise_rate <= 1.0:
        raise CrossStateReadoutError("Cohorte fournisseur inattendue")
    impact = _metric_from_priority(row)
    rank = _rank_from_priority(row, expected_supplier_count=expected_supplier_count)
    model_effect_detected = _boolean(
        row.get("model_effect_detected"), label="détection d'effet"
    )
    computed_effect_detected = bool(
        impact["ci95Low"] > NUMERIC_TOLERANCE and impact["positiveEffectCount"] >= 24
    )
    if model_effect_detected != computed_effect_detected:
        raise CrossStateReadoutError("Détection d'effet incohérente avec l'IC95")
    if model_effect_detected:
        if rank["unambiguousTop3Probability"] >= 0.80:
            computed_status = "robust_priority"
        elif rank["top3InclusionProbability"] >= 0.20:
            computed_status = "dossier_to_investigate"
        else:
            computed_status = "detected_lower_priority"
    else:
        computed_status = "no_detected_effect"
    status_valid = priority_status == computed_status
    if priority_status == "global_only_not_confirmed_within_target_product":
        status_valid = computed_status in SIGNAL_STATUSES
    elif priority_status == "supplementary_backlog_signal":
        status_valid = computed_status == "no_detected_effect"
    if not status_valid:
        raise CrossStateReadoutError(
            "Statut de priorité incohérent avec le rang bootstrap"
        )

    dossier = qualification_by_cell.get((state, mechanism, lane))
    if dossier is not None:
        dossier_level = _text(dossier.get("proof_level"))
        dossier_label = _text(dossier.get("display_label_fr"))
        dossier_mrp = _text(dossier.get("mrp_requirement_mode"))
        dossier_id = _text(dossier.get("dossier_id"))
        if (
            dossier_level not in {"partial", "complete"}
            or not dossier_label
            or not dossier_id
            or dossier_mrp != _text(proof.get("mrp_requirement_mode"))
            or exercise_rate <= 0.0
            or dossier.get("full_dynamic_stock_mrp_production_service_cascade_proven")
            is not False
            or dossier.get("complete_cascade_label_allowed") is not False
        ):
            raise CrossStateReadoutError("Dossier lot incompatible avec sa cellule")
        physical_level = dossier_level
        physical_label = dossier_label
        detailed_replay = True
        selected_dossier_ids = [dossier_id]
        missing_stages = list(dossier.get("missing_native_trace_stages") or [])
    else:
        detailed_replay = False
        selected_dossier_ids = []
        missing_stages = []
        if exercise_rate > 0.0:
            physical_level = "partial"
            physical_label = (
                "Exposition fournisseur exercée dans cette cellule — "
                "sans rejeu généalogique détaillé"
            )
        else:
            physical_level = "not_exercised"
            physical_label = "Incident non exercé physiquement dans cette cellule"
    return {
        "state": state,
        "mechanism": mechanism,
        "supplier": supplier,
        "lane": lane,
        "item": item.removeprefix("item:"),
        "destination": destination,
        "targetProduct": target_product.removeprefix("item:"),
        "priorityStatus": priority_status,
        "modelEffectDetected": model_effect_detected,
        "horizonDependent": _boolean(
            row.get("horizon_dependent"), label="dépendance à l'horizon"
        ),
        "pairedCount": paired_count,
        "physicalExerciseRate": exercise_rate,
        "impact": impact,
        "rank": rank,
        "physicalEvidence": {
            "level": physical_level,
            "label": physical_label,
            "mrpRequirementMode": _text(proof.get("mrp_requirement_mode")),
            "detailedLotReplayAvailable": detailed_replay,
            "selectedDossierIds": selected_dossier_ids,
            "missingStages": missing_stages,
            "fullDynamicCascadeProven": False,
        },
    }


def _classification(stability: Mapping[str, Any]) -> str:
    comparable = (
        _boolean(
            stability.get("state_comparison_valid"), label="comparaison inter-états"
        )
        and _boolean(
            stability.get("same_exposed_lane_across_states"),
            label="même voie inter-états",
        )
        and _boolean(
            stability.get("same_target_product_for_exposed_lane_across_states"),
            label="même produit inter-états",
        )
    )
    count = _integer(
        stability.get("priority_state_count"),
        label="nombre d'états prioritaires",
    )
    if not comparable:
        return (
            "signal_inter_etats_non_comparable"
            if count and count > 0
            else "aucun_signal_de_priorite_service"
        )
    if _boolean(
        stability.get("robust_priority_in_all_three_states"),
        label="priorité robuste dans les trois états",
    ):
        return "priorite_robuste_dans_les_3_etats"
    if _boolean(
        stability.get("priority_in_all_three_states"),
        label="priorité dans les trois états",
    ):
        return "priorite_dans_les_3_etats"
    if count and count > 0:
        return "priorite_dependante_de_l_etat"
    return "aucun_signal_de_priorite_service"


def _group_suppliers(
    *,
    priority_rows: Sequence[Mapping[str, Any]],
    stability_rows: Sequence[Mapping[str, Any]],
    qualification: Mapping[str, Any],
    expected_supplier_count: int,
) -> list[dict[str, Any]]:
    raw_lanes = qualification.get("lanes")
    if not isinstance(raw_lanes, list) or len(raw_lanes) != EXPECTED_LANES:
        raise CrossStateReadoutError("Qualification des 18 voies absente")
    qualification_by_lane = {
        _text(row.get("lane_id")): row for row in raw_lanes if isinstance(row, Mapping)
    }
    if len(qualification_by_lane) != EXPECTED_LANES or "" in qualification_by_lane:
        raise CrossStateReadoutError("Identités des voies qualifiées incomplètes")
    raw_dossiers = qualification.get("dossiers")
    if not isinstance(raw_dossiers, list) or len(raw_dossiers) > 3:
        raise CrossStateReadoutError("Sélection de dossiers lots invalide")
    qualification_by_cell: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    dossier_ids: set[str] = set()
    for dossier in raw_dossiers:
        if not isinstance(dossier, Mapping):
            raise CrossStateReadoutError("Dossier lot officiel invalide")
        key = (
            _text(dossier.get("operating_point_id")),
            _text(dossier.get("mechanism")),
            _text(dossier.get("lane_id")),
        )
        dossier_id = _text(dossier.get("dossier_id"))
        if (
            not dossier_id
            or dossier_id in dossier_ids
            or key[0] not in STATE_IDS
            or key[1] not in MECHANISMS
            or key[2] not in qualification_by_lane
            or key in qualification_by_cell
        ):
            raise CrossStateReadoutError("Cellule de dossier lot invalide ou dupliquée")
        dossier_ids.add(dossier_id)
        qualification_by_cell[key] = dossier

    grouped: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw in priority_rows:
        result = _state_result(
            raw,
            qualification_by_lane,
            qualification_by_cell,
            expected_supplier_count=expected_supplier_count,
        )
        key = (result["mechanism"], result["supplier"])
        if not result["supplier"] or result["state"] in grouped[key]:
            raise CrossStateReadoutError(
                "Cellule fournisseur/état absente ou dupliquée"
            )
        grouped[key][result["state"]] = result
    if len(grouped) != len(MECHANISMS) * expected_supplier_count:
        raise CrossStateReadoutError("Matrice fournisseur/mécanisme incomplète")
    if any(set(states) != set(STATE_IDS) for states in grouped.values()):
        raise CrossStateReadoutError("Chaque fournisseur exige les trois états")

    stability_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in stability_rows:
        key = (_text(row.get("mechanism")), _text(row.get("supplier_id")))
        if key in stability_by_key or key not in grouped:
            raise CrossStateReadoutError("Stabilité fournisseur absente ou dupliquée")
        stability_by_key[key] = row
    if set(stability_by_key) != set(grouped):
        raise CrossStateReadoutError("Table de stabilité fournisseur incomplète")

    suppliers: list[dict[str, Any]] = []
    for key, by_state in grouped.items():
        stability = stability_by_key[key]
        required = {
            "state_comparison_valid",
            "same_exposed_lane_across_states",
            "same_target_product_for_exposed_lane_across_states",
            "priority_state_count",
            "robust_priority_state_count",
            "priority_in_all_three_states",
            "robust_priority_in_all_three_states",
            "comparison_lane_id",
            "target_product_id_for_comparison_lane",
            "comparable_seed_count",
            "required_comparable_seed_count",
            "horizon_dependent",
        }
        _require_fields(stability, required, label=STABILITY_FILE)
        ordered_states = {state: by_state[state] for state in STATE_IDS}
        priority_state_count = _integer(
            stability.get("priority_state_count"), label="états prioritaires"
        )
        robust_state_count = _integer(
            stability.get("robust_priority_state_count"), label="états robustes"
        )
        if not 0 <= priority_state_count <= 3 or not 0 <= robust_state_count <= 3:
            raise CrossStateReadoutError("Compte de stabilité hors limites")
        computed_priority_count = sum(
            row["priorityStatus"] in SIGNAL_STATUSES for row in ordered_states.values()
        )
        computed_robust_count = sum(
            row["priorityStatus"] == "robust_priority"
            for row in ordered_states.values()
        )
        same_lane = len({row["lane"] for row in ordered_states.values()}) == 1
        same_product = (
            len({row["targetProduct"] for row in ordered_states.values()}) == 1
        )
        comparable_count = _integer(
            stability.get("comparable_seed_count"),
            label="simulations comparables",
        )
        required_comparable = _integer(
            stability.get("required_comparable_seed_count"),
            label="seuil de comparaison",
        )
        comparison_valid = _boolean(
            stability.get("state_comparison_valid"), label="comparaison inter-états"
        )
        declared_same_lane = _boolean(
            stability.get("same_exposed_lane_across_states"),
            label="même voie inter-états",
        )
        declared_same_product = _boolean(
            stability.get("same_target_product_for_exposed_lane_across_states"),
            label="même produit inter-états",
        )
        declared_all_priority = _boolean(
            stability.get("priority_in_all_three_states"),
            label="priorité dans les trois états",
        )
        declared_all_robust = _boolean(
            stability.get("robust_priority_in_all_three_states"),
            label="priorité robuste dans les trois états",
        )
        horizon_dependent = _boolean(
            stability.get("horizon_dependent"), label="dépendance à l'horizon"
        )
        comparison_lane = _text(stability.get("comparison_lane_id"))
        comparison_product = _text(
            stability.get("target_product_id_for_comparison_lane")
        ).removeprefix("item:")
        comparison_identity = qualification_by_lane.get(comparison_lane)
        if (
            priority_state_count != computed_priority_count
            or robust_state_count != computed_robust_count
            or declared_all_priority is not (computed_priority_count == 3)
            or declared_all_robust is not (computed_robust_count == 3)
            or declared_same_lane is not same_lane
            or declared_same_product is not same_product
            or required_comparable != 24
            or not 0 <= comparable_count <= EXPECTED_REPETITIONS
            or (comparison_valid and comparable_count < required_comparable)
            or not isinstance(comparison_identity, Mapping)
            or _text(comparison_identity.get("supplier_id")) != key[1]
            or _text(comparison_identity.get("target_product_id")).removeprefix("item:")
            != comparison_product
            or (
                same_lane
                and comparison_lane != next(iter(ordered_states.values()))["lane"]
            )
            or (
                same_product
                and comparison_product
                != next(iter(ordered_states.values()))["targetProduct"]
            )
        ):
            raise CrossStateReadoutError("Stabilité incohérente avec les trois états")
        classification = _classification(stability)
        same_reason = classification in {
            "priorite_robuste_dans_les_3_etats",
            "priorite_dans_les_3_etats",
        }
        suppliers.append(
            {
                "mechanism": key[0],
                "supplier": key[1],
                "classification": classification,
                "sameSupplierLaneAndTestedReasonAcrossStates": same_reason,
                "stateComparisonValid": comparison_valid,
                "sameExposedLaneAcrossStates": declared_same_lane,
                "sameTargetProductAcrossStates": declared_same_product,
                "comparisonLane": comparison_lane,
                "targetProduct": comparison_product,
                "comparableSeedCount": comparable_count,
                "requiredComparableSeedCount": required_comparable,
                "priorityStateCount": priority_state_count,
                "robustPriorityStateCount": robust_state_count,
                "priorityInAllThreeStates": declared_all_priority,
                "robustPriorityInAllThreeStates": declared_all_robust,
                "horizonDependent": horizon_dependent,
                "states": ordered_states,
            }
        )
    order = {
        "priorite_robuste_dans_les_3_etats": 0,
        "priorite_dans_les_3_etats": 1,
        "signal_inter_etats_non_comparable": 2,
        "priorite_dependante_de_l_etat": 3,
        "aucun_signal_de_priorite_service": 4,
    }
    suppliers.sort(
        key=lambda row: (
            MECHANISMS.index(row["mechanism"]),
            order[row["classification"]],
            -max(state["impact"]["mean"] for state in row["states"].values()),
            row["supplier"],
        )
    )
    return suppliers


def _state_summaries(campaign: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = campaign.get("states")
    if (
        not isinstance(rows, list)
        or len(rows) != len(STATE_IDS)
        or any(not isinstance(row, Mapping) for row in rows)
        or {row.get("id") for row in rows} != set(STATE_IDS)
    ):
        raise CrossStateReadoutError(
            "Les trois états de service officiels sont absents"
        )
    by_id = {str(row["id"]): row for row in rows}
    result: list[dict[str, Any]] = []
    for state in STATE_IDS:
        row = by_id[state]
        global_service = _number(
            row.get("globalServicePct"), label=f"service global {state}"
        )
        pf091 = _number(row.get("pf091ServicePct"), label=f"service 268091 {state}")
        pf967 = _number(row.get("pf967ServicePct"), label=f"service 268967 {state}")
        ci_low = _number(row.get("globalCiLowPct"), label=f"IC95 bas {state}")
        ci_high = _number(row.get("globalCiHighPct"), label=f"IC95 haut {state}")
        target = _number(row.get("targetServicePct"), label=f"cible {state}")
        offset_091 = _number(
            row.get("offsetDays268091"), label=f"décalage 268091 {state}"
        )
        offset_967 = _number(
            row.get("offsetDays268967"), label=f"décalage 268967 {state}"
        )
        if not (
            0.0 <= global_service <= 100.0
            and 0.0 <= pf091 <= 100.0
            and 0.0 <= pf967 <= 100.0
            and 0.0 <= ci_low <= ci_high <= 100.0
            and 0.0 <= target <= 100.0
            and offset_091 >= 0.0
            and offset_967 >= 0.0
            and row.get("degradationFamily") == EXPECTED_DEGRADATION_FAMILY
            and row.get("degradationUnit") == "jour"
        ):
            raise CrossStateReadoutError("Service de point de fonctionnement invalide")
        product_gap = abs(pf091 - pf967)
        result.append(
            {
                "id": state,
                "label": _text(row.get("label")) or state,
                "targetServicePct": target,
                "globalServicePct": global_service,
                "globalCi95LowPct": ci_low,
                "globalCi95HighPct": ci_high,
                "service268091Pct": pf091,
                "service268967Pct": pf967,
                "productGapPp": product_gap,
                "productGapWarning": product_gap > 5.0 + NUMERIC_TOLERANCE,
                "degradationFamily": _text(row.get("degradationFamily")),
                "degradationUnit": _text(row.get("degradationUnit")),
                "offsetDays268091": offset_091,
                "offsetDays268967": offset_967,
            }
        )
    return result


def _mechanism_summaries(
    suppliers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    labels = {
        "transport_delay": {
            "label": "Retard de transport de 120 jours",
            "hypothesis": (
                "Pendant une fenêtre ciblée de 42 jours, les expéditions décidées "
                "sur la voie arrivent 120 jours plus tard."
            ),
        },
        "planned_delivery_shortfall": {
            "label": "Quantité normalement livrable divisée par deux",
            "hypothesis": (
                "Pendant la fenêtre ciblée, la quantité normalement livrable est "
                "multipliée par 0,5."
            ),
        },
    }
    result: list[dict[str, Any]] = []
    for mechanism in MECHANISMS:
        rows = [row for row in suppliers if row["mechanism"] == mechanism]
        stable = [
            row for row in rows if row["sameSupplierLaneAndTestedReasonAcrossStates"]
        ]
        robust = [row for row in stable if row["robustPriorityInAllThreeStates"]]
        state_specific = [
            row
            for row in rows
            if row["classification"] == "priorite_dependante_de_l_etat"
        ]
        non_comparable = [
            row
            for row in rows
            if row["classification"] == "signal_inter_etats_non_comparable"
        ]
        names = [str(row["supplier"]) for row in stable]
        if names:
            conclusion = (
                f"Oui, {len(names)} fournisseur(s) gardent un signal sur la même voie "
                "et le même produit dans les trois états : " + ", ".join(names) + "."
            )
        else:
            conclusion = (
                "Non démontré : aucun fournisseur ne satisfait simultanément le signal "
                "dans les trois états, la même voie, le même produit et l'exposition "
                "comparable."
            )
        result.append(
            {
                "id": mechanism,
                **labels[mechanism],
                "stablePrioritySupplierCount": len(stable),
                "stableRobustSupplierCount": len(robust),
                "stateSpecificSupplierCount": len(state_specific),
                "nonComparableSupplierCount": len(non_comparable),
                "stableSuppliers": names,
                "conclusion": conclusion,
            }
        )
    return result


def _lot_summary(qualification: Mapping[str, Any]) -> dict[str, Any]:
    counts = qualification.get("counts")
    dossiers = qualification.get("dossiers")
    lanes = qualification.get("lanes")
    if (
        not isinstance(counts, Mapping)
        or not isinstance(dossiers, list)
        or not isinstance(lanes, list)
    ):
        raise CrossStateReadoutError("Résumé de qualification physique absent")
    lane_by_id = {
        _text(row.get("lane_id")): row
        for row in lanes
        if isinstance(row, Mapping) and _text(row.get("lane_id"))
    }
    if (
        _integer(counts.get("dynamic_mrp_lane_count"), label="voies MRP dynamiques")
        != 2
        or _integer(counts.get("static_mrp_lane_count"), label="voies MRP statiques")
        != 16
        or _integer(
            counts.get("full_dynamic_cascade_proven_count"),
            label="cascades dynamiques prouvées",
        )
        != 0
    ):
        raise CrossStateReadoutError("Portée MRP physique inattendue")
    reduced: list[dict[str, Any]] = []
    for raw in dossiers:
        if not isinstance(raw, Mapping):
            raise CrossStateReadoutError("Dossier physique invalide")
        trace_counts = raw.get("trace_counts")
        if not isinstance(trace_counts, Mapping):
            raise CrossStateReadoutError("Comptes de trace physique absents")
        lane = _text(raw.get("lane_id"))
        identity = lane_by_id.get(lane, {})
        reduced.append(
            {
                "dossierId": _text(raw.get("dossier_id")),
                "supplier": _text(raw.get("supplier_id"))
                or _text(identity.get("supplier_id")),
                "lane": lane,
                "mechanism": _text(raw.get("mechanism")),
                "state": _text(raw.get("operating_point_id")),
                "proofLevel": _text(raw.get("proof_level")),
                "proofLabel": _text(raw.get("display_label_fr")),
                "mrpRequirementMode": _text(raw.get("mrp_requirement_mode")),
                "missingStages": list(raw.get("missing_native_trace_stages") or []),
                "traceCounts": dict(trace_counts),
                "fullDynamicCascadeProven": False,
            }
        )
    return {
        "selectedDossierCount": len(reduced),
        "allLotsTraced": False,
        "dynamicMrpLaneCount": 2,
        "staticMrpLaneCount": 16,
        "signedMrpResponseTraceAvailable": False,
        "fullDynamicCascadeProvenCount": 0,
        "dossiers": reduced,
    }


def _action_summary(actions: Mapping[str, Any]) -> dict[str, Any]:
    status = _text(actions.get("status")) or "not_provided"
    results_raw = actions.get("results") or []
    refusals_raw = actions.get("refusals") or []
    if not isinstance(results_raw, list) or not isinstance(refusals_raw, list):
        raise CrossStateReadoutError("Résultats d'actions invalides")
    results: list[dict[str, Any]] = []
    for raw in results_raw:
        if not isinstance(raw, Mapping):
            raise CrossStateReadoutError("Résultat d'action invalide")
        result = {
            "dossierId": _text(raw.get("dossierId")),
            "state": _text(raw.get("state")),
            "supplier": _text(raw.get("supplier")),
            "lane": _text(raw.get("lane")),
            "item": _text(raw.get("item")),
            "destination": _text(raw.get("destination")),
            "targetProduct": _text(raw.get("targetProduct")),
            "mechanism": _text(raw.get("mechanism")),
            "actionId": _text(raw.get("actionId")),
            "label": _text(raw.get("label")),
            "parameters": dict(raw.get("parameters") or {}),
            "physicalScope": dict(raw.get("physicalScope") or {}),
            "status": _text(raw.get("status")),
            "pairedCount": _integer(
                raw.get("pairedCount"), label="simulations d'action"
            ),
            "exercisedCount": _integer(
                raw.get("exercisedCount"), label="actions exercées"
            ),
            "nonExercisedCount": _integer(
                raw.get("nonExercisedCount"),
                label="actions non exercées",
            ),
            "gains": list(raw.get("gains") or []),
            "limits": _text(raw.get("limits")),
            "lotTraceAvailable": False,
        }
        if (
            result["state"] not in STATE_IDS
            or result["mechanism"] not in MECHANISMS
            or not all(
                result[field]
                for field in (
                    "dossierId",
                    "supplier",
                    "lane",
                    "item",
                    "destination",
                    "targetProduct",
                    "actionId",
                    "label",
                    "status",
                )
            )
            or not 1 <= result["pairedCount"] <= EXPECTED_REPETITIONS
            or not 0 <= result["exercisedCount"] <= result["pairedCount"]
            or result["nonExercisedCount"]
            != result["pairedCount"] - result["exercisedCount"]
        ):
            raise CrossStateReadoutError("Identité ou cohorte d'action invalide")
        results.append(result)
    refusals = [
        {
            "dossierId": _text(raw.get("dossierId")),
            "actionId": _text(raw.get("actionId")),
            "label": _text(raw.get("label")),
            "reason": _text(raw.get("reason")),
            "limits": _text(raw.get("limits")),
        }
        for raw in refusals_raw
        if isinstance(raw, Mapping)
    ]
    return {
        "status": status,
        "message": _text(actions.get("message")),
        "controlMode": "hypotheses_de_scenarios_en_boucle_ouverte",
        "closedLoopClaimed": False,
        "completeCostValidated": False,
        "roiAvailable": False,
        "lotTraceAvailable": False,
        "results": results,
        "refusals": refusals,
    }


def build_business_payload(
    *,
    campaign: Mapping[str, Any],
    priority_rows: Sequence[Mapping[str, Any]],
    stability_rows: Sequence[Mapping[str, Any]],
    qualification: Mapping[str, Any],
    actions: Mapping[str, Any],
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Create the client-safe projection from already validated aggregates."""

    matrix = campaign.get("matrix")
    if (
        not isinstance(matrix, Mapping)
        or _integer(matrix.get("totalRows"), label="résultats de campagne") != 3330
        or _integer(matrix.get("incidentRows"), label="incidents de campagne") != 3240
        or _integer(matrix.get("baselineRows"), label="références de campagne") != 90
        or _integer(
            matrix.get("repetitionsPerCombination"), label="simulations par test"
        )
        != EXPECTED_REPETITIONS
        or _integer(matrix.get("lanes"), label="voies testées") != EXPECTED_LANES
        or _integer(matrix.get("states"), label="états testés") != len(STATE_IDS)
        or _integer(matrix.get("mechanisms"), label="mécanismes testés") != 2
    ):
        raise CrossStateReadoutError("Matrice officielle 3×18×2×30 incomplète")
    expected_supplier_count = _integer(
        campaign.get("supplierCount"), label="fournisseurs testés"
    )
    if expected_supplier_count is None or expected_supplier_count <= 0:
        raise CrossStateReadoutError("Nombre de fournisseurs invalide")
    states = _state_summaries(campaign)
    suppliers = _group_suppliers(
        priority_rows=priority_rows,
        stability_rows=stability_rows,
        qualification=qualification,
        expected_supplier_count=expected_supplier_count,
    )
    classifications = Counter(row["classification"] for row in suppliers)
    mechanisms = _mechanism_summaries(suppliers)
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "complete_validated_post_processing",
        "generatedAtUtc": generated_at_utc or utc_now(),
        "viewCount": 3,
        "question": (
            "Retrouve-t-on les mêmes signaux de priorité fournisseur aux états "
            "proches de 100 %, 93 % et 80 %, pour les mêmes raisons testées ?"
        ),
        "definitions": [
            {
                "term": "OBSERVÉ",
                "meaning": (
                    "Donnée industrielle datée. Aucune performance fournisseur "
                    "historique n'est calculée dans cette page."
                ),
            },
            {
                "term": "SIMULÉ",
                "meaning": (
                    "Conséquence calculée après un incident imposé. Ce n'est ni une "
                    "mesure réelle ni une probabilité future."
                ),
            },
            {
                "term": "SIGNAL DE PRIORITÉ",
                "meaning": (
                    "Voie fournisseur–article–site à instruire parce que l'impact "
                    "simulé ressort ; ce n'est pas une note fournisseur."
                ),
            },
            {
                "term": "HYPOTHÈSE",
                "meaning": (
                    "Règle du test : retard +120 jours ou quantité normalement "
                    "livrable ×0,5 pendant 42 jours."
                ),
            },
        ],
        "campaign": {
            "states": states,
            "mechanisms": mechanisms,
            "supplierCount": expected_supplier_count,
            "laneCount": EXPECTED_LANES,
            "physicalSimulationCountPerTest": EXPECTED_REPETITIONS,
            "bootstrapResampleCount": EXPECTED_BOOTSTRAP_REPLICATES,
            "bootstrapIsPhysicalSimulation": False,
            "top3Forced": False,
            "selectionRule": (
                "Un signal n'est affiché comme stable que s'il reste prioritaire pour "
                "le même mécanisme, la même voie et le même produit dans les trois états, "
                "avec une comparaison d'exposition validée."
            ),
            "classificationCounts": dict(classifications),
            "suppliers": suppliers,
        },
        "lots": _lot_summary(qualification),
        "actions": _action_summary(actions),
        "limits": [
            (
                "Les incidents sont des hypothèses sur une fenêtre de forte exposition, "
                "pas des événements observés, moyens ou des pires cas mathématiques."
            ),
            (
                "Les 30 simulations décrivent la variabilité de l'impact sachant que "
                "l'incident est imposé. Les 10 000 bootstrap sont des rééchantillonnages "
                "de ces 30 résultats, pas 10 000 simulations physiques."
            ),
            (
                "Le rang mesure l'exposition du réseau et de la voie testée. Il ne mesure "
                "ni la fréquence réelle d'incident, ni la qualité intrinsèque du fournisseur."
            ),
            (
                "Les deux mécanismes sont testés séparément, une voie à la fois. Aucun "
                "enchaînement d'incidents fournisseurs corrélés ou risque secondaire "
                "endogène n'est simulé."
            ),
            (
                "Deux voies ont un besoin MRP dynamique configuré et seize un besoin "
                "statique. Aucune réponse MRP signée n'est tracée : aucune cascade "
                "dynamique complète stock–MRP–production–service n'est revendiquée."
            ),
            (
                "Les dossiers lots sont représentatifs et limités aux dossiers sélectionnés. "
                "Les clients C-XXXXX sont agrégés ; aucun client ou ordre réel n'est attribué."
            ),
            (
                "Les leviers sont des scénarios en boucle ouverte. Leur faisabilité réelle, "
                "les capacités disponibles, les qualifications, les coûts complets, la "
                "perte de chiffre d'affaires et le ROI ne sont pas validés. Les simulations "
                "d'action n'ont pas de généalogie lot : aucun « lot sauvé » n'est identifié."
            ),
            (
                "Les états 100/93/80 proviennent d'une seule famille de dégradation par "
                "délai fournisseur planifié. Ce n'est pas une analyse globale de tous les "
                "facteurs de sensibilité de la supply chain."
            ),
        ],
    }
    payload["payloadSignature"] = stable_sha256(payload)
    return payload


def flatten_supplier_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return one wide CSV row per supplier and tested incident mechanism."""

    output: list[dict[str, Any]] = []
    campaign = payload.get("campaign")
    suppliers = campaign.get("suppliers") if isinstance(campaign, Mapping) else None
    if not isinstance(suppliers, list):
        raise CrossStateReadoutError("Fournisseurs absents du payload")
    for supplier in suppliers:
        row: dict[str, Any] = {
            "mechanism": supplier["mechanism"],
            "supplier_id": supplier["supplier"],
            "classification": supplier["classification"],
            "same_supplier_lane_reason_across_states": supplier[
                "sameSupplierLaneAndTestedReasonAcrossStates"
            ],
            "state_comparison_valid": supplier["stateComparisonValid"],
            "same_exposed_lane_across_states": supplier["sameExposedLaneAcrossStates"],
            "same_target_product_across_states": supplier[
                "sameTargetProductAcrossStates"
            ],
            "comparison_lane_id": supplier["comparisonLane"],
            "target_product_id": supplier["targetProduct"],
            "comparable_seed_count": supplier["comparableSeedCount"],
            "required_comparable_seed_count": supplier["requiredComparableSeedCount"],
            "priority_state_count": supplier["priorityStateCount"],
            "robust_priority_state_count": supplier["robustPriorityStateCount"],
            "top3_forced": False,
        }
        for state in STATE_IDS:
            result = supplier["states"][state]
            metric = result["impact"]
            rank = result["rank"]
            proof = result["physicalEvidence"]
            prefix = state.removeprefix("op_")
            values = {
                "priority_status": result["priorityStatus"],
                "lane_id": result["lane"],
                "item_id": result["item"],
                "destination": result["destination"],
                "target_product": result["targetProduct"],
                "impact_mean_pp": metric["mean"],
                "impact_median_pp": metric["median"],
                "impact_p10_pp": metric["p10"],
                "impact_p90_pp": metric["p90"],
                "impact_ci95_low_pp": metric["ci95Low"],
                "impact_ci95_high_pp": metric["ci95High"],
                "positive_effect_rate": metric["positiveEffectRate"],
                "positive_effect_count": metric["positiveEffectCount"],
                "rank_median": rank["rankMedian"],
                "rank_ci95_low": rank["rankCi95Low"],
                "rank_ci95_high": rank["rankCi95High"],
                "bootstrap_top3_inclusion_probability": rank[
                    "top3InclusionProbability"
                ],
                "bootstrap_unambiguous_top3_probability": rank[
                    "unambiguousTop3Probability"
                ],
                "physical_exercise_rate": result["physicalExerciseRate"],
                "physical_proof_level": proof["level"],
                "physical_proof_label": proof["label"],
                "mrp_requirement_mode": proof["mrpRequirementMode"],
            }
            row.update({f"{prefix}_{name}": value for name, value in values.items()})
        output.append(row)
    return output


def _safe_json(payload: Mapping[str, Any]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>RESILIENCE-SCAN V6 — comparaison fournisseurs sur trois états</title>
  <style>
  :root{--navy:#092844;--blue:#1769df;--teal:#087d72;--green:#187b55;--amber:#a86100;--red:#b93a34;--ink:#142a40;--muted:#5e7185;--line:#d4e0ea;--paper:#eff4f8;--card:#fff;--shadow:0 9px 28px #193b5714}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.46 Inter,Segoe UI,Arial,sans-serif}button,select{font:inherit}header{padding:26px clamp(18px,4vw,58px);color:white;background:linear-gradient(120deg,#071d33,#145486 66%,#087c70)}header h1{margin:6px 0 8px;font-size:clamp(28px,4vw,48px);line-height:1.06}.overline{font-size:11px;font-weight:900;letter-spacing:.14em;color:#96ebd8}header p{max-width:1050px;margin:0;color:#dcebf7;font-size:17px}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.chip,.badge{display:inline-block;padding:5px 9px;border-radius:999px;font-size:11px;font-weight:850}.chip{border:1px solid #ffffff45;background:#ffffff12}.badge.sim{background:#e8f1ff;color:#1457ad}.badge.signal{background:#fff0ee;color:#a12e29}.badge.ok{background:#e5f5ed;color:#126643}.badge.warn{background:#fff2df;color:#875000}.definitions{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#c9d7e3}.definition{min-height:102px;padding:12px 18px;background:white}.definition b{display:block;color:var(--blue);font-size:11px;letter-spacing:.07em}.definition span{display:block;margin-top:4px;color:#50687d;font-size:12.5px}.tabs{position:sticky;top:0;z-index:20;display:flex;justify-content:center;gap:8px;padding:10px;background:#f9fbfdef;border-bottom:1px solid var(--line)}.tabs button,.lot-tabs button{padding:8px 13px;border:1px solid #b7c9da;border-radius:999px;background:white;color:#24455f;font-weight:800;cursor:pointer}.tabs button.active,.lot-tabs button.active{color:white;background:var(--navy);border-color:var(--navy)}main{max-width:1320px;margin:auto;padding:20px clamp(13px,3vw,32px) 52px}.view{display:none}.view.active{display:block}.intro,.panel,.card,.limit{padding:16px;border:1px solid var(--line);border-radius:15px;background:white;box-shadow:var(--shadow)}.intro{margin-bottom:13px;border-left:6px solid var(--blue)}.intro h2,.panel h3{margin:0 0 4px}.intro p,.panel>p,.muted{color:var(--muted)}.grid{display:grid;gap:10px}.states{grid-template-columns:repeat(3,1fr)}.state{border-top:5px solid var(--blue)}.state strong{display:block;font-size:28px;color:var(--navy)}.products{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:9px}.product{padding:8px;border:1px solid var(--line);border-radius:9px}.product b{display:block;font-size:18px}.warning{margin-top:8px;padding:8px;border-radius:8px;background:#fff4e5;color:#7d4b00;font-size:12px}.panel{margin:13px 0}.toolbar{display:flex;gap:9px;align-items:end;flex-wrap:wrap;margin:11px 0}.field{display:grid;gap:3px}.field label{font-size:10px;font-weight:900;letter-spacing:.06em;color:var(--muted)}select{max-width:min(620px,92vw);padding:8px 10px;border:1px solid #b7c9da;border-radius:9px;background:white}.answer{padding:13px;border-left:5px solid var(--teal);border-radius:10px;background:#eef9f6}.answer b{font-size:18px}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:8px;border-bottom:1px solid #e2eaf1;text-align:left;vertical-align:top}th{color:#50677d;font-size:10px;letter-spacing:.04em}.status{font-weight:850}.stable{color:var(--green)}.variable{color:var(--amber)}.none{color:var(--muted)}.detail-states{grid-template-columns:repeat(3,1fr)}.detail{border-top:5px solid var(--blue)}.detail h3{margin:4px 0}.big{font-size:27px;font-weight:900;color:var(--navy)}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:10px 0}.metric{padding:8px;border-radius:9px;background:#f5f8fb}.metric b{display:block}.proof{padding:9px;border-radius:9px;background:#fff7e9;color:#6f4a16;font-size:12px}.explain{padding:12px;border-radius:10px;background:#edf5ff;color:#31516c}.lots,.actions{grid-template-columns:repeat(2,1fr)}.trace-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.trace{padding:8px;border:1px solid var(--line);border-radius:9px;text-align:center}.trace b{display:block;font-size:20px}.action{border-left:5px solid var(--green)}.action h4{margin:3px 0}.params{padding:8px;border-radius:8px;background:#f4f8fb;font-family:ui-monospace,Consolas,monospace;font-size:12px}.limits{grid-template-columns:repeat(2,1fr)}.limit{box-shadow:none;color:var(--muted)}.empty{padding:18px;border:1px dashed #b9cad9;border-radius:11px;text-align:center;color:var(--muted);background:#f9fbfc}footer{text-align:center;padding:17px;color:#65798d;font-size:12px}@media(max-width:900px){.definitions,.states,.detail-states,.lots,.actions,.limits{grid-template-columns:1fr 1fr}}@media(max-width:600px){.definitions,.states,.detail-states,.lots,.actions,.limits,.metric-grid{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}}
  </style>
</head>
<body>
  <header>
    <div class="overline">RESILIENCE-SCAN · POST-TRAITEMENT MÉTIER V6</div>
    <h1>Les mêmes signaux fournisseurs ressortent-ils quand la supply se dégrade&nbsp;?</h1>
    <p id="question"></p>
    <div class="chips"><span class="chip">3 états simulés</span><span class="chip">18 voies</span><span class="chip">30 simulations physiques par test</span><span class="chip">10 000 rééchantillonnages statistiques</span><span class="chip">aucun top 3 forcé</span></div>
  </header>
  <section class="definitions" id="definitions"></section>
  <nav class="tabs" aria-label="Trois vues">
    <button class="active" data-view="answer">1. Réponse directe</button>
    <button data-view="evidence">2. Preuves et dispersion</button>
    <button data-view="decisions">3. Lots, leviers et limites</button>
  </nav>
  <main>
    <section class="view active" id="view-answer">
      <div class="intro"><h2>Une réponse séparée pour chaque incident testé</h2><p>« Même raison » signifie ici le même mécanisme imposé, la même voie physique et le même produit alimenté. Cela ne prouve pas la cause historique d'une défaillance fournisseur.</p></div>
      <div class="grid states" id="state-cards"></div>
      <article class="panel">
        <div class="toolbar"><div class="field"><label>INCIDENT TESTÉ</label><select id="answer-mechanism"></select></div></div>
        <div class="answer" id="answer-reading"></div>
        <p class="muted">La liste ci-dessous conserve les signaux tels qu'ils ressortent. Aucun fournisseur n'est ajouté pour obtenir artificiellement trois noms.</p>
        <div class="scroll"><table><thead><tr><th>Fournisseur / voie comparable</th><th>Lecture</th><th>État ~100</th><th>État ~93</th><th>État ~80</th><th>Exposition comparable</th></tr></thead><tbody id="answer-table"></tbody></table></div>
      </article>
    </section>

    <section class="view" id="view-evidence">
      <div class="intro"><h2>Pourquoi ce signal est-il — ou non — stable&nbsp;?</h2><p>Les trois colonnes montrent séparément l'impact, sa dispersion, la répétabilité conditionnelle, la robustesse du rang et la preuve physique disponible.</p></div>
      <div class="toolbar"><div class="field"><label>INCIDENT TESTÉ</label><select id="detail-mechanism"></select></div><div class="field"><label>FOURNISSEUR</label><select id="detail-supplier"></select></div></div>
      <p class="explain" id="detail-reading"></p>
      <div class="grid detail-states" id="detail-states"></div>
      <article class="panel"><h3>Comment lire les statistiques</h3><p><b>P10–P90</b> contient environ 80 % des 30 conséquences simulées. <b>IC95</b> encadre la moyenne estimée par bootstrap. Un effet de service est détecté si la borne basse de cet IC95 est supérieure à zéro et si au moins 24/30 effets sont positifs. « Priorité robuste » exige au moins 80 % de classements sans ambiguïté dans le groupe de tête ; « dossier à instruire » exige au moins 20 % de présence possible. Ces fréquences sont calculées sur 10 000 rééchantillonnages des mêmes 30 simulations : elles ne sont jamais la probabilité de l'incident.</p></article>
    </section>

    <section class="view" id="view-decisions">
      <div class="intro"><h2>Ce que les lots prouvent et ce que les leviers testent réellement</h2><p>Les traces et gains restent attachés aux dossiers simulés. Les actions sont des scénarios en boucle ouverte, pas une régulation automatique ni une recommandation.</p></div>
      <article class="panel"><h3>Preuve physique et lots</h3><p id="lot-summary"></p><div class="grid lots" id="lot-cards"></div></article>
      <article class="panel"><h3>Leviers simulés avec leurs paramètres</h3><p id="action-summary"></p><div class="grid actions" id="action-cards"></div><div id="action-refusals"></div></article>
      <article class="panel"><h3>Limites à conserver dans la décision</h3><div class="grid limits" id="limits"></div></article>
    </section>
  </main>
  <footer>Stress-test conditionnel · aucune performance fournisseur historique ni probabilité annuelle d'incident</footer>
  <script id="business-data" type="application/json">__DATA__</script>
  <script>
  (()=>{
    "use strict";
    const D=JSON.parse(document.getElementById("business-data").textContent),$=id=>document.getElementById(id);
    const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null},fmt=(v,d=2)=>n(v)===null?"—":new Intl.NumberFormat("fr-FR",{maximumFractionDigits:d}).format(Number(v));
    const pp=v=>`${fmt(v)} pt`,pct=v=>n(v)===null?"—":`${fmt(100*Number(v),0)} %`,stateLabel=id=>({op_100:"~100 %",op_93:"~93 %",op_80:"~80 %"}[id]||id);
    const mechanism=id=>D.campaign.mechanisms.find(x=>x.id===id),groups=id=>D.campaign.suppliers.filter(x=>x.mechanism===id);
    const classInfo=id=>({priorite_robuste_dans_les_3_etats:["Priorité robuste dans les 3 états","stable"],priorite_dans_les_3_etats:["Priorité dans les 3 états","stable"],signal_inter_etats_non_comparable:["Signal présent, comparaison inter-états non admissible","variable"],priorite_dependante_de_l_etat:["Priorité dépendante de l'état","variable"],aucun_signal_de_priorite_service:["Aucun signal de priorité service","none"]}[id]||[id,"none"]);
    $("question").textContent=D.question;$("definitions").innerHTML=D.definitions.map(x=>`<div class="definition"><b>${esc(x.term)}</b><span>${esc(x.meaning)}</span></div>`).join("");
    document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tabs button").forEach(x=>x.classList.toggle("active",x===b));document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===`view-${b.dataset.view}`))});
    $("state-cards").innerHTML=D.campaign.states.map(s=>`<article class="card state"><span class="badge sim">SIMULÉ · ${stateLabel(s.id)}</span><strong>${fmt(s.globalServicePct)} %</strong><small>service global · IC95 ${fmt(s.globalCi95LowPct)} à ${fmt(s.globalCi95HighPct)} %</small><div class="products"><div class="product"><small>Produit 268091</small><b>${fmt(s.service268091Pct)} %</b></div><div class="product"><small>Produit 268967</small><b>${fmt(s.service268967Pct)} %</b></div></div><p class="muted">Décalages planifiés : 268091 +${fmt(s.offsetDays268091,1)} j · 268967 +${fmt(s.offsetDays268967,1)} j.</p>${s.productGapWarning?`<div class="warning"><b>Écart produits ${fmt(s.productGapPp)} points.</b> Le service global masque une différence supérieure à 5 points.</div>`:""}</article>`).join("");
    const mechanismOptions=()=>D.campaign.mechanisms.map(m=>`<option value="${esc(m.id)}">${esc(m.label)}</option>`).join("");
    const answerMechanism=$("answer-mechanism");answerMechanism.innerHTML=mechanismOptions();
    const impactCell=(g,id)=>{const s=g.states[id];return `${pp(s.impact.mean)}<br><small>P10–P90 ${pp(s.impact.p10)} à ${pp(s.impact.p90)}</small>`};
    function renderAnswer(){const m=mechanism(answerMechanism.value),rows=groups(m.id).filter(x=>x.priorityStateCount>0);$("answer-reading").innerHTML=`<b>${esc(m.conclusion)}</b><br><span class="muted">${esc(m.hypothesis)} ${m.stableRobustSupplierCount} signal(aux) robuste(s) dans les trois états ; ${m.stateSpecificSupplierCount} dépendant(s) de l'état après comparaison valide ; ${m.nonComparableSupplierCount} non comparable(s).</span>`;$("answer-table").innerHTML=rows.length?rows.map(g=>{const c=classInfo(g.classification);return `<tr><td><b>${esc(g.supplier)}</b><br><small>${esc(g.comparisonLane||"voie variable")} · produit ${esc(g.targetProduct||"variable")}</small></td><td><span class="status ${c[1]}">${esc(c[0])}</span></td><td>${impactCell(g,"op_100")}</td><td>${impactCell(g,"op_93")}</td><td>${impactCell(g,"op_80")}</td><td>${g.stateComparisonValid&&g.sameExposedLaneAcrossStates&&g.sameTargetProductAcrossStates?`Oui · ${g.comparableSeedCount}/${g.states.op_100.pairedCount}`:"Non"}</td></tr>`}).join(""):'<tr><td colspan="6"><div class="empty">Aucun signal de priorité service retenu ; aucun nom n'est forcé.</div></td></tr>'}
    answerMechanism.onchange=renderAnswer;renderAnswer();
    const detailMechanism=$("detail-mechanism"),detailSupplier=$("detail-supplier");detailMechanism.innerHTML=mechanismOptions();
    function fillSuppliers(){detailSupplier.innerHTML=groups(detailMechanism.value).map(g=>`<option value="${esc(g.supplier)}">${esc(g.supplier)} · ${esc(classInfo(g.classification)[0])}</option>`).join("");renderDetail()}
    const priorityLabel=id=>({robust_priority:"Priorité robuste",dossier_to_investigate:"Dossier à instruire",supplementary_backlog_signal:"Signal backlog complémentaire",detected_lower_priority:"Effet détecté, priorité plus faible",global_only_not_confirmed_within_target_product:"Signal global non confirmé dans le produit",no_detected_effect:"Aucun effet démontré"}[id]||id);
    function renderDetail(){const g=groups(detailMechanism.value).find(x=>x.supplier===detailSupplier.value);if(!g){$("detail-states").innerHTML='<div class="empty">Fournisseur absent.</div>';return}const ci=classInfo(g.classification);$("detail-reading").innerHTML=`<b>${esc(g.supplier)} — ${esc(ci[0])}.</b> Même raison testée dans les trois états : <b>${g.sameSupplierLaneAndTestedReasonAcrossStates?"oui":"non démontré"}</b>. ${g.horizonDependent?"Le rang ou la voie dépend de la durée observée.":""}`;$("detail-states").innerHTML=Object.values(g.states).map(s=>`<article class="card detail"><span class="badge ${s.priorityStatus==="robust_priority"?"ok":s.priorityStatus==="dossier_to_investigate"?"signal":"warn"}">${esc(priorityLabel(s.priorityStatus))}</span><h3>État ${stateLabel(s.state)}</h3><p><b>${esc(s.supplier)}</b> · article ${esc(s.item)} → ${esc(s.destination)}<br><small>voie ${esc(s.lane)} · produit ${esc(s.targetProduct)}</small></p><div class="big">${pp(s.impact.mean)}</div><small>perte moyenne de service du produit alimenté · fenêtre 360 jours</small><div class="metric-grid"><div class="metric"><b>${pp(s.impact.p10)} à ${pp(s.impact.p90)}</b><small>P10–P90 · 30 simulations</small></div><div class="metric"><b>${pp(s.impact.ci95Low)} à ${pp(s.impact.ci95High)}</b><small>IC95 de la moyenne</small></div><div class="metric"><b>${pct(s.impact.positiveEffectRate)}</b><small>effet positif · ${s.impact.positiveEffectCount}/30</small></div><div class="metric"><b>${fmt(s.rank.rankMedian,1)}</b><small>rang médian bootstrap · IC95 ${fmt(s.rank.rankCi95Low,0)}–${fmt(s.rank.rankCi95High,0)}</small></div><div class="metric"><b>${pct(s.rank.top3InclusionProbability)}</b><small>présence possible groupe de tête</small></div><div class="metric"><b>${pct(s.rank.unambiguousTop3Probability)}</b><small>présence sans ambiguïté</small></div></div><div class="proof"><b>Preuve physique : ${esc(s.physicalEvidence.label)}</b><br>MRP : ${s.physicalEvidence.mrpRequirementMode==="dynamic_explicit"?"besoin dynamique configuré, réponse non tracée":"besoin statique explicite"} · incident exercé dans ${pct(s.physicalExerciseRate)} des simulations.</div></article>`).join("")}
    detailMechanism.onchange=fillSuppliers;detailSupplier.onchange=renderDetail;fillSuppliers();
    const traceLabels={shipments:"expéditions",material_receipts:"réceptions",consumptions:"consommations",campaigns:"campagnes",batches:"batches",finished_lots:"lots finis",client_events:"contacts clients agrégés"};
    $("lot-summary").innerHTML=`<b>${D.lots.selectedDossierCount} dossier(s) représentatif(s).</b> ${D.lots.dynamicMrpLaneCount} voies à besoin dynamique configuré, ${D.lots.staticMrpLaneCount} à besoin statique ; aucune réponse MRP signée et aucune cascade dynamique complète revendiquée.`;
    $("lot-cards").innerHTML=D.lots.dossiers.length?D.lots.dossiers.map(d=>`<article class="card"><span class="badge ${d.proofLevel==="complete"?"ok":"warn"}">${esc(d.proofLabel)}</span><h3>${esc(d.supplier||"Fournisseur")} · ${esc(d.lane)}</h3><p>${esc(mechanism(d.mechanism)?.label||d.mechanism)} · état ${stateLabel(d.state)}</p><div class="trace-grid">${Object.entries(d.traceCounts).filter(([k])=>traceLabels[k]).map(([k,v])=>`<div class="trace"><b>${fmt(v,0)}</b><small>${esc(traceLabels[k])}</small></div>`).join("")}</div><p class="muted">Contact généalogique simulé ; aucun client réel ni perte incrémentale attribuée à un lot réel.</p></article>`).join(""):'<div class="empty">Aucun dossier de lots sélectionné : aucune trace n'est inventée.</div>';
    const parameterText=p=>Object.entries(p||{}).map(([k,v])=>`${k} = ${fmt(v,3)}`).join(" · ")||"paramètre absent";
    const gainText=g=>g.mean==null?"gain non estimé":`${esc(g.label)} : moyenne ${fmt(g.mean,g.unit==="point"?2:0)} ${esc(g.unit)} · P10–P90 ${fmt(g.p10,g.unit==="point"?2:0)} à ${fmt(g.p90,g.unit==="point"?2:0)} · ${fmt(g.count,0)} simulations`;
    $("action-summary").innerHTML=`<b>Aucune régulation automatique.</b> ${esc(D.actions.message)} Les gains sont conditionnels aux simulations où le levier agit ; coûts complets et ROI non validés. Les bras d'action ne tracent pas les lots : aucun « lot sauvé » n'est identifié.`;
    $("action-cards").innerHTML=D.actions.results.length?D.actions.results.map(a=>`<article class="card action"><span class="badge sim">HYPOTHÈSE EN BOUCLE OUVERTE</span><h4>${esc(a.label)}</h4><p>${esc(a.supplier)} · article ${esc(a.item)} → ${esc(a.destination)}<br><small>${esc(mechanism(a.mechanism)?.label||a.mechanism)} · état ${stateLabel(a.state)} · voie ${esc(a.lane)} · produit ${esc(a.targetProduct)}</small></p><div class="params">${esc(parameterText(a.parameters))}</div><p>Levier exercé dans <b>${fmt(a.exercisedCount,0)}/${fmt(a.pairedCount,0)}</b> simulations.</p>${a.gains.map(g=>`<p>${gainText(g)}</p>`).join("")}<p class="warning"><b>Limite :</b> ${esc(a.limits||"Faisabilité et coûts réels non validés.")} Aucune généalogie lot n'est disponible pour ce bras d'action.</p></article>`).join(""):'<div class="empty">Aucun gain d'action validé dans les dossiers retenus.</div>';
    $("action-refusals").innerHTML=D.actions.refusals.length?`<div class="warning"><b>Leviers refusés et non simulés :</b><ul>${D.actions.refusals.map(a=>`<li><b>${esc(a.label)}</b> — ${esc(a.reason)} ${esc(a.limits)}</li>`).join("")}</ul></div>`:"";
    $("limits").innerHTML=D.limits.map(x=>`<div class="limit">${esc(x)}</div>`).join("");
  })();
  </script>
</body>
</html>
"""


def render_html(payload: Mapping[str, Any]) -> str:
    document = HTML_TEMPLATE.replace("__DATA__", _safe_json(payload))
    if document.count('class="view') != 3:
        raise CrossStateReadoutError("Le HTML doit contenir exactement trois vues")
    if (
        "__DATA__" in document
        or re.search(r"https?://", document, flags=re.I)
        or re.search(r"<(?:script|img|iframe)\b[^>]*\bsrc\s*=", document, flags=re.I)
        or re.search(r"<link\b[^>]*\bhref\s*=", document, flags=re.I)
    ):
        raise CrossStateReadoutError("Le HTML n'est pas autonome")
    required_phrases = (
        "aucun top 3 forcé",
        "10 000 rééchantillonnages",
        "boucle ouverte",
        "aucune performance fournisseur historique",
    )
    visible = re.sub(
        r'<script id="business-data".*?</script>', "", document, flags=re.DOTALL
    ).casefold()
    if any(phrase.casefold() not in visible for phrase in required_phrases):
        raise CrossStateReadoutError("Une limite métier obligatoire manque au HTML")
    return document


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise CrossStateReadoutError("Le CSV fournisseur ne peut pas être vide")
    fields = list(rows[0])
    if any(list(row) != fields for row in rows):
        raise CrossStateReadoutError("Schéma CSV fournisseur non déterministe")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _remove_owned_stage(stage: Path) -> None:
    if not stage.name.startswith(".supplier-v6-cross-state-stage-"):
        raise CrossStateReadoutError("Nettoyage d'un répertoire non possédé refusé")
    if stage.exists():
        shutil.rmtree(stage)


def write_delivery(
    *,
    output_dir: Path,
    payload: Mapping[str, Any],
    source_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish a new immutable four-file package beside all source artifacts."""

    _verify_signed(payload, "payloadSignature", label="payload métier à publier")
    if (
        payload.get("schemaVersion") != SCHEMA_VERSION
        or payload.get("status") != "complete_validated_post_processing"
        or payload.get("viewCount") != 3
        or not isinstance(source_bindings, Mapping)
    ):
        raise CrossStateReadoutError("Payload ou liaisons source non publiables")
    destination = output_dir.resolve()
    if destination.exists():
        raise FileExistsError(
            f"Refus d'écraser une livraison existante : {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=".supplier-v6-cross-state-stage-", dir=destination.parent
        )
    ).resolve()
    try:
        rows = flatten_supplier_rows(payload)
        csv_path = stage / CSV_FILE
        json_path = stage / JSON_FILE
        html_path = stage / HTML_FILE
        _write_csv(csv_path, rows)
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        html_path.write_text(render_html(payload), encoding="utf-8")
        files = {
            name: {
                "sha256": sha256_file(stage / name),
                "bytes": (stage / name).stat().st_size,
            }
            for name in (CSV_FILE, JSON_FILE, HTML_FILE)
        }
        files[CSV_FILE]["row_count"] = len(rows)
        unsigned = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "status": "complete_validated",
            "generated_at_utc": payload.get("generatedAtUtc"),
            "producer": str(Path(__file__).resolve()),
            "producer_sha256": sha256_file(Path(__file__).resolve()),
            "offline_single_file_html": True,
            "view_count": 3,
            "payload_signature": payload.get("payloadSignature"),
            "source_bindings": dict(source_bindings),
            "outputs": files,
            "scientific_scope": {
                "top3_forced": False,
                "bootstrap_replicates": EXPECTED_BOOTSTRAP_REPLICATES,
                "bootstrap_is_physical_simulation": False,
                "closed_loop_claimed": False,
                "full_dynamic_cascade_claimed": False,
                "historical_incident_probability_estimated": False,
                "complete_cost_or_roi_claimed": False,
            },
        }
        manifest = {**unsigned, "manifest_signature": stable_sha256(unsigned)}
        (stage / MANIFEST_FILE).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validate_delivery(stage)
        stage.replace(destination)
    except BaseException:
        _remove_owned_stage(stage)
        raise
    return validate_delivery(destination)


def _verify_signed(payload: Mapping[str, Any], field: str, *, label: str) -> str:
    signature = _text(payload.get(field))
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if not re.fullmatch(r"[0-9a-f]{64}", signature) or signature != stable_sha256(
        unsigned
    ):
        raise CrossStateReadoutError(f"Signature invalide : {label}")
    return signature


def validate_delivery(output_dir: Path) -> dict[str, Any]:
    root = output_dir.resolve()
    paths = {
        name: root / name for name in (CSV_FILE, JSON_FILE, HTML_FILE, MANIFEST_FILE)
    }
    if not root.is_dir() or any(not path.is_file() for path in paths.values()):
        raise CrossStateReadoutError("Livraison métier absente ou incomplète")
    manifest = _read_json(paths[MANIFEST_FILE])
    signature = _verify_signed(manifest, "manifest_signature", label="manifeste")
    scope = manifest.get("scientific_scope")
    outputs = manifest.get("outputs")
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "complete_validated"
        or manifest.get("offline_single_file_html") is not True
        or manifest.get("view_count") != 3
        or not isinstance(scope, Mapping)
        or not isinstance(outputs, Mapping)
        or scope.get("top3_forced") is not False
        or scope.get("bootstrap_replicates") != EXPECTED_BOOTSTRAP_REPLICATES
        or scope.get("bootstrap_is_physical_simulation") is not False
        or scope.get("closed_loop_claimed") is not False
        or scope.get("full_dynamic_cascade_claimed") is not False
        or scope.get("historical_incident_probability_estimated") is not False
        or scope.get("complete_cost_or_roi_claimed") is not False
    ):
        raise CrossStateReadoutError("Périmètre scientifique du manifeste invalide")
    for name in (CSV_FILE, JSON_FILE, HTML_FILE):
        declared = outputs.get(name)
        path = paths[name]
        if (
            not isinstance(declared, Mapping)
            or declared.get("sha256") != sha256_file(path)
            or declared.get("bytes") != path.stat().st_size
        ):
            raise CrossStateReadoutError(f"Sortie altérée : {name}")
    payload = _read_json(paths[JSON_FILE])
    payload_signature = _verify_signed(
        payload, "payloadSignature", label="payload métier"
    )
    if (
        payload.get("schemaVersion") != SCHEMA_VERSION
        or payload.get("status") != "complete_validated_post_processing"
        or payload.get("viewCount") != 3
        or payload_signature != manifest.get("payload_signature")
        or payload.get("campaign", {}).get("top3Forced") is not False
        or payload.get("campaign", {}).get("bootstrapResampleCount")
        != EXPECTED_BOOTSTRAP_REPLICATES
        or payload.get("campaign", {}).get("bootstrapIsPhysicalSimulation") is not False
        or payload.get("actions", {}).get("closedLoopClaimed") is not False
        or payload.get("actions", {}).get("lotTraceAvailable") is not False
        or payload.get("lots", {}).get("allLotsTraced") is not False
    ):
        raise CrossStateReadoutError("Payload métier incohérent")
    document = paths[HTML_FILE].read_text(encoding="utf-8")
    matches = re.findall(
        r'<script id="business-data" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        raise CrossStateReadoutError("Payload autonome HTML absent ou dupliqué")
    try:
        embedded = json.loads(html.unescape(matches[0]))
    except json.JSONDecodeError as exc:
        raise CrossStateReadoutError("Payload HTML illisible") from exc
    if stable_sha256(embedded) != stable_sha256(payload):
        raise CrossStateReadoutError("Payload HTML différent du JSON contrôlé")
    if document != render_html(embedded):
        raise CrossStateReadoutError("HTML différent du rendu autonome déterministe")
    with paths[CSV_FILE].open("r", encoding="utf-8-sig", newline="") as stream:
        csv_count = sum(1 for _ in csv.DictReader(stream))
    if csv_count != outputs[CSV_FILE].get("row_count"):
        raise CrossStateReadoutError("Nombre de lignes CSV altéré")
    return {
        "valid": True,
        "output_dir": str(root),
        "html": str(paths[HTML_FILE]),
        "json": str(paths[JSON_FILE]),
        "csv": str(paths[CSV_FILE]),
        "manifest": str(paths[MANIFEST_FILE]),
        "manifest_signature": signature,
        "supplier_mechanism_row_count": csv_count,
        "view_count": 3,
    }


def _paths_overlap(left: Path, right: Path) -> bool:
    first = left.resolve()
    second = right.resolve()
    return first == second or first in second.parents or second in first.parents


def _validate_output_separation(
    *, output_dir: Path, source_paths: Sequence[Path | None]
) -> None:
    destination = output_dir.resolve()
    overlaps = [
        str(source.resolve())
        for source in source_paths
        if source is not None and _paths_overlap(destination, source)
    ]
    if overlaps:
        raise CrossStateReadoutError(
            "Le dossier de sortie doit rester séparé des sources officielles : "
            + ", ".join(overlaps)
        )


def build_from_official_inputs(
    *,
    campaign_root: Path,
    results_dir: Path,
    qualification_dir: Path,
    lot_replay_root: Path,
    action_results_root: Path | None,
    target_registry_path: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    _validate_output_separation(
        output_dir=output_dir,
        source_paths=(
            campaign_root,
            results_dir,
            qualification_dir,
            lot_replay_root,
            action_results_root,
            target_registry_path,
        ),
    )
    campaign, priorities, stability, qualification, actions, bindings = (
        load_official_inputs(
            campaign_root=campaign_root,
            results_dir=results_dir,
            qualification_dir=qualification_dir,
            lot_replay_root=lot_replay_root,
            action_results_root=action_results_root,
            target_registry_path=target_registry_path,
        )
    )
    payload = build_business_payload(
        campaign=campaign,
        priority_rows=priorities,
        stability_rows=stability,
        qualification=qualification,
        actions=actions,
    )
    return write_delivery(
        output_dir=output_dir,
        payload=payload,
        source_bindings=bindings,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--campaign-root", type=Path, required=True)
    build.add_argument("--results-dir", type=Path, required=True)
    build.add_argument("--qualification-dir", type=Path, required=True)
    build.add_argument("--lot-replay-root", type=Path, required=True)
    build.add_argument("--action-results-root", type=Path)
    build.add_argument("--target-registry", type=Path)
    build.add_argument("--output-dir", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = build_from_official_inputs(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                qualification_dir=args.qualification_dir,
                lot_replay_root=args.lot_replay_root,
                action_results_root=args.action_results_root,
                target_registry_path=args.target_registry,
                output_dir=args.output_dir,
            )
        else:
            result = validate_delivery(args.output_dir)
    except (CrossStateReadoutError, FileExistsError) as exc:
        print(f"POST-TRAITEMENT V6 REFUSÉ : {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
