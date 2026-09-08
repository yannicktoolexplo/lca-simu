#!/usr/bin/env python3
"""Build the three-view, client-facing V5 supplier-risk delivery.

This is a presentation-only adapter.  It reuses the frozen V4 evidence loaders,
requires the additive V5 physical-scope qualification, and never starts the
simulation engine.  V4 sources and artifacts remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_qualification,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v4_final_standalone_delivery as delivery_v4,
)


SCHEMA_VERSION = "etudecas.supplier_v5_final_standalone_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
EXPECTED_V4_DELIVERY_SHA256 = (
    "b245096492835a97ab79651d6c3aded2edc6c51da5d52756e33f59bef3a18e50"
)
EXPECTED_MECHANISMS = frozenset({"transport_delay", "planned_delivery_shortfall"})
EXPECTED_REPETITIONS = 30
EXPECTED_LANES = 18
EXPECTED_DYNAMIC_LANES = 2
EXPECTED_STATIC_LANES = 16


class V5FinalDeliveryError(RuntimeError):
    """The V5 delivery cannot be supported by its signed inputs."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_frozen_v4_delivery() -> Path:
    """Refuse reuse if the evidence-loading implementation has changed."""

    path = Path(delivery_v4.__file__).resolve()
    if _sha256_file(path) != EXPECTED_V4_DELIVERY_SHA256:
        raise V5FinalDeliveryError(
            "Le chargeur de preuves réutilisé a changé ; livraison V5 refusée."
        )
    return path


def _finite(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise V5FinalDeliveryError(f"Valeur numérique absente : {label}") from exc
    if not math.isfinite(number):
        raise V5FinalDeliveryError(f"Valeur numérique non finie : {label}")
    return number


def _business_trace_label(proof: Mapping[str, Any]) -> str:
    level = str(proof.get("proof_level") or "")
    label = str(proof.get("display_label_fr") or "").strip()
    if level not in {"partial", "complete"} or not label:
        raise V5FinalDeliveryError("Niveau de traçabilité dossier inattendu")
    if "cascade complète" in label.casefold():
        raise V5FinalDeliveryError("Libellé de cascade complète interdit")
    return label


def _priority_for_dossier(
    priorities: Sequence[Mapping[str, Any]], dossier: Mapping[str, Any]
) -> Mapping[str, Any]:
    matches = [
        row
        for row in priorities
        if str(row.get("state") or "") == str(dossier.get("state") or "")
        and str(row.get("mechanism") or "") == str(dossier.get("mechanism") or "")
        and str(row.get("lane") or "") == str(dossier.get("lane") or "")
        and str(row.get("supplier") or "") == str(dossier.get("supplier") or "")
    ]
    if len(matches) != 1:
        raise V5FinalDeliveryError(
            f"Signal agrégé introuvable pour le dossier {dossier.get('id')!s}"
        )
    service = matches[0].get("service")
    if not isinstance(service, Mapping):
        raise V5FinalDeliveryError("Dispersion du signal fournisseur absente")
    for field in ("mean", "p10", "p90"):
        _finite(service.get(field), label=f"impact {field}")
    return matches[0]


def _attach_qualification(
    *, base: Mapping[str, Any], qualification: Mapping[str, Any]
) -> list[dict[str, Any]]:
    if qualification.get("status") != "complete_qualified":
        raise V5FinalDeliveryError("Qualification physique V5 incomplète")
    counts = qualification.get("counts")
    if not isinstance(counts, Mapping):
        raise V5FinalDeliveryError("Comptes de qualification physique absents")
    if (
        int(counts.get("dynamic_mrp_lane_count", -1)) != EXPECTED_DYNAMIC_LANES
        or int(counts.get("static_mrp_lane_count", -1)) != EXPECTED_STATIC_LANES
        or int(counts.get("full_dynamic_cascade_proven_count", -1)) != 0
    ):
        raise V5FinalDeliveryError("Périmètre dynamique V5 inattendu")

    lots = (base.get("lots") or {}).get("dossiers") or []
    selected = ((base.get("campaign") or {}).get("lotSelection") or {}).get(
        "dossiers"
    ) or []
    qualified = qualification.get("dossiers")
    if (
        not isinstance(lots, list)
        or not isinstance(selected, list)
        or not isinstance(qualified, list)
    ):
        raise V5FinalDeliveryError("Dossiers de lots ou qualification invalides")
    lot_by_id = {str(row.get("id") or ""): row for row in lots}
    selected_ids = {str(row.get("dossierId") or "") for row in selected}
    proof_by_id = {str(row.get("dossier_id") or ""): row for row in qualified}
    if (
        "" in lot_by_id
        or "" in selected_ids
        or "" in proof_by_id
        or set(lot_by_id) != selected_ids
        or set(lot_by_id) != set(proof_by_id)
    ):
        raise V5FinalDeliveryError(
            "Les dossiers qualifiés diffèrent de la sélection et des rejeux validés"
        )

    priorities = (base.get("campaign") or {}).get("priorities") or []
    if not isinstance(priorities, list):
        raise V5FinalDeliveryError("Signaux fournisseurs absents")
    result: list[dict[str, Any]] = []
    for dossier_id in sorted(lot_by_id):
        source = lot_by_id[dossier_id]
        proof = proof_by_id[dossier_id]
        level = str(proof.get("proof_level") or "")
        trace_counts = proof.get("trace_counts")
        if (
            proof.get("campaign_shipment_exercised") is not True
            or proof.get("replay_shipment_to_receipt_exercised") is not True
            or proof.get("complete_cascade_label_allowed") is not False
            or proof.get("full_dynamic_stock_mrp_production_service_cascade_proven")
            is not False
            or level not in {"partial", "complete"}
            or not isinstance(trace_counts, Mapping)
        ):
            raise V5FinalDeliveryError(
                f"Qualification physique non publiable : {dossier_id}"
            )
        required_counts = {
            field: int(trace_counts.get(field) or 0)
            for field in (
                "shipments",
                "material_receipts",
                "consumptions",
                "campaigns",
                "batches",
                "finished_lots",
                "client_events",
                "clients",
            )
        }
        all_stages = all(value > 0 for value in required_counts.values())
        if (level == "complete") != all_stages:
            raise V5FinalDeliveryError(
                f"Libellé de traçabilité contraire aux preuves : {dossier_id}"
            )
        source_counts = source.get("traceCounts")
        if not isinstance(source_counts, Mapping) or any(
            int(source_counts.get(field) or 0) != value
            for field, value in required_counts.items()
        ):
            raise V5FinalDeliveryError(
                f"Comptes de traçabilité contradictoires : {dossier_id}"
            )
        priority = _priority_for_dossier(priorities, source)
        result.append(
            {
                "id": dossier_id,
                "state": source["state"],
                "mechanism": source["mechanism"],
                "supplier": source["supplier"],
                "lane": source["lane"],
                "item": source["item"],
                "destination": source["destination"],
                "targetProduct": source["targetProduct"],
                "exercisedCount": source["exercisedCount"],
                "traceCounts": dict(source["traceCounts"]),
                "chain": source["chain"],
                "chainRowsTotal": source["chainRowsTotal"],
                "chainRowsShown": source["chainRowsShown"],
                "kpis": source["kpis"],
                "lags": source["lags"],
                "impact": dict(priority["service"]),
                "traceProof": {
                    "level": level,
                    "label": _business_trace_label(proof),
                    "requirementMode": proof["mrp_requirement_mode"],
                    "missingStages": list(
                        proof.get("missing_native_trace_stages") or []
                    ),
                },
            }
        )
    return result


def _qualified_priorities(
    *, campaign: Mapping[str, Any], qualification: Mapping[str, Any]
) -> list[dict[str, Any]]:
    lanes = qualification.get("lanes")
    if not isinstance(lanes, list) or len(lanes) != EXPECTED_LANES:
        raise V5FinalDeliveryError("Qualification des 18 voies absente")
    by_lane = {
        str(row.get("lane_id") or ""): row for row in lanes if isinstance(row, Mapping)
    }
    if len(by_lane) != EXPECTED_LANES or "" in by_lane:
        raise V5FinalDeliveryError("Identités des voies qualifiées incomplètes")
    result: list[dict[str, Any]] = []
    for raw in campaign.get("priorities") or []:
        if not isinstance(raw, Mapping):
            raise V5FinalDeliveryError("Signal fournisseur invalide")
        lane = by_lane.get(str(raw.get("lane") or ""))
        if lane is None:
            raise V5FinalDeliveryError("Signal sans qualification physique de voie")
        level = str(lane.get("proof_level") or "")
        label = str(lane.get("display_label_fr") or "").strip()
        if (
            level not in {"not_exercised", "partial", "complete"}
            or not label
            or lane.get("complete_cascade_label_allowed") is not False
            or lane.get("full_dynamic_stock_mrp_production_service_cascade_proven")
            is not False
            or "cascade complète" in label.casefold()
        ):
            raise V5FinalDeliveryError("Qualification physique de voie non publiable")
        result.append(
            {
                "state": raw["state"],
                "mechanism": raw["mechanism"],
                "supplier": raw["supplier"],
                "lane": raw["lane"],
                "item": raw["item"],
                "destination": raw["destination"],
                "targetProduct": raw["targetProduct"],
                "position": raw["position"],
                "supplementaryBacklogSignal": raw["supplementaryBacklogSignal"],
                "service": raw["service"],
                "backlog": raw["backlog"],
                "physicalProofLevel": level,
                "physicalEvidenceLabel": label,
            }
        )
    return result


def _clean_actions(actions: Mapping[str, Any]) -> dict[str, Any]:
    status = str(actions.get("status") or "not_provided")
    if status == "complete_validated":
        message = (
            "Les gains comparent, simulation par simulation, le même incident avec "
            "et sans levier. Seuls les cas où le levier agit réellement entrent dans "
            "la moyenne et la dispersion."
        )
    elif status == "complete_no_representable_action":
        message = (
            "Aucun levier prévu n’a pu agir sur les dossiers retenus. Aucun gain "
            "n’est donc annoncé ; cela ne signifie pas qu’aucune solution "
            "opérationnelle n’existe."
        )
    else:
        message = "Aucun résultat de levier validé n’est disponible dans ce livrable."
    results = []
    for row in actions.get("results") or []:
        results.append(
            {
                "dossierId": row["dossierId"],
                "supplier": row["supplier"],
                "item": row["item"],
                "destination": row["destination"],
                "mechanism": row["mechanism"],
                "label": row["label"],
                "status": row["status"],
                "pairedCount": row["pairedCount"],
                "exercisedCount": row["exercisedCount"],
                "gains": row["gains"],
            }
        )
    refusals = [
        {"label": row.get("label", "Levier non simulé")}
        for row in actions.get("refusals") or []
    ]
    return {
        "status": status,
        "message": message,
        "results": results,
        "refusals": refusals,
    }


def build_delivery_payload(
    *,
    campaign_root: Path,
    results_dir: Path,
    curves_dir: Path | None,
    replay_root: Path | None,
    qualification_dir: Path,
    output_html: Path,
    target_registry_path: Path | None = None,
    dashboard_html: Path | None = None,
    action_results_root: Path | None = None,
    legacy_risk_html: Path | None = None,
    legacy_control_html: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a compact V5 business payload from validated, existing evidence."""

    validate_frozen_v4_delivery()
    try:
        base, bindings = delivery_v4.build_delivery_payload(
            campaign_root=campaign_root,
            results_dir=results_dir,
            curves_dir=curves_dir,
            replay_root=replay_root,
            output_html=output_html,
            target_registry_path=target_registry_path,
            # Companion V4 pages remain technical artifacts.  They are deliberately
            # not exposed as extra client views or copied into the V5 payload.
            dashboard_html=None,
            action_results_root=action_results_root,
            legacy_risk_html=None,
            legacy_control_html=None,
        )
        qualification = physical_qualification.validate_qualification_sidecar(
            campaign_root=campaign_root,
            results_dir=results_dir,
            replay_root=replay_root,
            output_dir=qualification_dir,
        )
    except Exception as exc:
        if isinstance(exc, V5FinalDeliveryError):
            raise
        raise V5FinalDeliveryError(f"Entrée V5 refusée : {exc}") from exc

    campaign = base.get("campaign")
    if not isinstance(campaign, Mapping):
        raise V5FinalDeliveryError("Résultats de campagne absents")
    mechanisms = campaign.get("mechanisms") or []
    if (
        {str(row.get("id") or "") for row in mechanisms} != EXPECTED_MECHANISMS
        or int(campaign.get("repetitions") or -1) != EXPECTED_REPETITIONS
        or int(campaign.get("laneCount") or -1) != EXPECTED_LANES
    ):
        raise V5FinalDeliveryError("La campagne ne contient pas les deux incidents V5")
    dossiers = _attach_qualification(base=base, qualification=qualification)
    priorities = _qualified_priorities(campaign=campaign, qualification=qualification)

    definitions = [
        {
            "term": "OBSERVÉ",
            "meaning": (
                "Valeur provenant d’une donnée industrielle datée, par exemple une "
                "commande ou une réception réelle. Aucune performance historique "
                "fournisseur n’est affichée ici."
            ),
        },
        {
            "term": "SIMULÉ",
            "meaning": (
                "Valeur calculée par le modèle après une règle « et si ? », par exemple "
                "+120 jours de transport. Ce n’est ni une mesure réelle ni une prévision."
            ),
        },
        {
            "term": "SIGNAL DE PRIORITÉ",
            "meaning": (
                "Couple fournisseur–article–site à examiner d’abord parce que son impact "
                "simulé ressort. Ce n’est ni une note fournisseur ni une probabilité."
            ),
        },
        {
            "term": "HYPOTHÈSE",
            "meaning": (
                "Règle imposée pour le test : transport retardé de 120 jours ou quantité "
                "livrable divisée par deux. Elle ne dit pas que l’incident a eu lieu."
            ),
        },
    ]
    client_campaign = {
        "states": campaign["states"],
        "mechanisms": mechanisms,
        "repetitions": campaign["repetitions"],
        "laneCount": campaign["laneCount"],
        "priorities": priorities,
        "matrix": campaign["matrix"],
    }
    complete_dossier_count = sum(
        row["traceProof"]["level"] == "complete" for row in dossiers
    )
    if complete_dossier_count:
        lot_status = "complete_trace_available"
        lot_message = (
            f"{complete_dossier_count} dossier(s) disposent d’une trace native jusqu’au "
            "nœud client agrégé, sans preuve complète de la réaction du calcul des besoins."
        )
    elif dossiers:
        lot_status = "partial_trace_only"
        lot_message = (
            "Aucun dossier n’atteint le nœud client agrégé dans la trace disponible. "
            "Le livrable reste publiable avec une démonstration physique partielle."
        )
    else:
        lot_status = "no_replayed_dossier"
        lot_message = (
            "Aucun dossier de lots n’est disponible ; les signaux restent des impacts "
            "simulés agrégés et aucune propagation détaillée n’est revendiquée."
        )
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAtUtc": delivery_v4.utc_now(),
        "viewCount": 3,
        "definitions": definitions,
        "campaign": client_campaign,
        "lots": {
            "status": (base.get("lots") or {}).get("status"),
            "demonstrationStatus": lot_status,
            "demonstrationMessage": lot_message,
            "dossiers": dossiers,
            "message": (base.get("lots") or {}).get("message", ""),
        },
        "actions": _clean_actions(base.get("actions") or {}),
        "remainingRisk": {
            "status": "not_quantified_at_portfolio_level",
            "message": (
                "Le risque restant n’est pas chiffré à l’échelle du portefeuille. "
                "Un gain de levier, lorsqu’il existe, ne vaut que pour les simulations "
                "où ce levier a agi ; il n’est pas converti en exposition annuelle."
            ),
            "historicalProbabilityEstimated": False,
            "completeResidualExposureEstimated": False,
            "roiAvailable": False,
        },
        "limits": [
            (
                "Deux incidents seulement sont testés, séparément et une voie à la "
                "fois : +120 jours de transport ou quantité livrable divisée par deux."
            ),
            (
                "Les moyennes et les plages P10–P90 décrivent 30 simulations sous "
                "hypothèse ; elles ne donnent pas une fréquence d’incident historique."
            ),
            (
                "Parmi les 18 voies testées, 2 recalculent le besoin à partir de la "
                "demande et 16 utilisent un besoin fixé à l’avance. La réaction de ce "
                "calcul n’est pas tracée dans les dossiers de lots."
            ),
            (
                "Une trace jusqu’au nœud client prouve un contact généalogique dans une "
                "simulation, pas tout l’enchaînement dynamique ni une perte attribuée à "
                "un client réel."
            ),
            (
                "Les clients restent agrégés sous C-XXXXX : aucun client réel ni aucune "
                "commande réelle ne sont identifiés."
            ),
            (
                "Le coût complet, l’exposition résiduelle annuelle et le retour sur "
                "investissement ne sont pas calculés."
            ),
        ],
        "package": {
            "campaignResultCount": int(base["package"]["campaignResultCount"]),
            "lotDossierCount": len(dossiers),
            "actionResultCount": len((base.get("actions") or {}).get("results") or []),
        },
    }
    bindings = {
        **bindings,
        "physical_qualification": {
            "directory": str(qualification_dir.resolve()),
            "qualification_signature": qualification["qualification_signature"],
            "scope_signature": qualification["scope_signature"],
        },
        "linked_pages_present_but_not_exposed_as_views": bool(
            dashboard_html or legacy_risk_html or legacy_control_html
        ),
    }
    return payload, bindings


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>RESILIENCE-SCAN V5 — incidents fournisseurs et décisions</title>
  <style>
  :root{--navy:#092947;--blue:#1769e0;--teal:#087e72;--green:#16835c;--amber:#b66c00;--red:#bd3c35;--ink:#142a40;--muted:#5d7186;--line:#d6e1eb;--paper:#eef3f8;--card:#fff;--shadow:0 10px 30px #17395512}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.48 Inter,Segoe UI,Arial,sans-serif}button,select{font:inherit}header{padding:27px clamp(18px,4vw,58px);color:#fff;background:linear-gradient(118deg,#061b31,#124e80 64%,#08786c)}.overline{font-size:11px;font-weight:900;letter-spacing:.14em;color:#93ead8}h1{margin:6px 0 9px;font-size:clamp(29px,4.5vw,50px);line-height:1.05}header p{max-width:1000px;margin:0;color:#dceaf7;font-size:17px}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.chip,.badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:850}.chip{border:1px solid #ffffff42;background:#ffffff12}.badge.sim{background:#e7f0ff;color:#1456ae}.badge.hyp{background:#fff1dd;color:#8d5200}.badge.signal{background:#fff0ee;color:#a52e28}.badge.ok{background:#e5f6ee;color:#116844}.definitions{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#c9d8e6}.definition{padding:12px clamp(10px,2vw,22px);background:#fff;min-height:104px}.definition b{display:block;color:var(--blue);font-size:11px;letter-spacing:.07em}.definition span{display:block;margin-top:4px;color:#52697f;font-size:12.5px}.tabs{position:sticky;top:0;z-index:20;display:flex;justify-content:center;gap:8px;padding:10px;background:#f8fbffed;border-bottom:1px solid var(--line)}.tabs button,.lot-tabs button{border:1px solid #b9cadb;border-radius:999px;background:#fff;color:#24445f;padding:8px 13px;font-weight:820;cursor:pointer}.tabs button.active{background:var(--navy);border-color:var(--navy);color:#fff}main{max-width:1260px;margin:auto;padding:20px clamp(13px,3vw,32px) 54px}.view{display:none}.view.active{display:block}.intro,.panel,.card,.limit,.remaining{background:#fff;border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}.intro{padding:16px 18px;border-left:6px solid var(--blue);margin-bottom:14px}.intro h2,.panel h3{margin:0 0 4px}.intro p,.panel>p,.muted{color:var(--muted)}.panel{padding:17px;margin:13px 0}.grid{display:grid;gap:10px}.states{grid-template-columns:repeat(3,1fr)}.state,.metric,.priority,.action,.trace-step{padding:13px;border:1px solid var(--line);border-radius:12px;background:#fff}.state strong,.metric strong{display:block;font-size:24px;color:var(--navy)}.state small,.metric small{display:block;color:var(--muted)}.toolbar{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin:12px 0}.field{display:grid;gap:3px}.field label{font-size:10px;font-weight:900;letter-spacing:.07em;color:var(--muted)}select{padding:8px 10px;border:1px solid #b9cadb;border-radius:9px;background:#fff;max-width:min(520px,92vw)}.reading,.remaining{padding:12px 14px;background:#edf5ff;color:#31516e}.priority-list,.actions,.limits{display:grid;gap:9px}.priority{display:grid;grid-template-columns:1fr auto;gap:12px}.priority .value{text-align:right;color:var(--red);font-weight:900}.priority small{display:block;color:var(--muted)}.lot-tabs{display:flex;gap:7px;flex-wrap:wrap}.lot-tabs button.active{background:var(--teal);border-color:var(--teal);color:#fff}.kpis{grid-template-columns:repeat(4,1fr)}.trace{grid-template-columns:repeat(5,1fr);margin:12px 0}.trace-step{text-align:center}.trace-step.present{border-top:5px solid var(--green)}.trace-step.missing{border-top:5px solid var(--amber);background:#fff9ef}.trace-step b{display:block;font-size:22px}.trace-step small{color:var(--muted)}.notice{padding:11px;border-left:5px solid var(--amber);background:#fff8e9;border-radius:9px}.action{border-left:5px solid var(--green)}.action h4{margin:0 0 4px}.gains{grid-template-columns:repeat(3,1fr)}.limit{padding:12px;color:var(--muted);box-shadow:none}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:7px;border-bottom:1px solid #e1e9f0;vertical-align:top}th{color:#52697e;font-size:10px}.scroll{overflow:auto}.empty{padding:20px;text-align:center;color:var(--muted);border:1px dashed #bdccda;border-radius:12px;background:#f8fafc}footer{text-align:center;padding:18px;color:#687c90;font-size:12px}@media(max-width:900px){.definitions,.states,.kpis,.trace,.gains{grid-template-columns:1fr 1fr}}@media(max-width:590px){.definitions,.states,.kpis,.trace,.gains{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}.priority{grid-template-columns:1fr}.priority .value{text-align:left}}
  </style>
</head>
<body>
  <header>
    <div class="overline">RESILIENCE-SCAN · RÉSULTATS V5</div>
    <h1>De l’incident fournisseur aux décisions, sans dépasser les preuves</h1>
    <p>Trois vues suivent le même fil : incident imposé, lots et client agrégé touchés, impact simulé, leviers testés, puis risque restant.</p>
    <div class="chips"><span class="chip">2 incidents simulés seulement</span><span class="chip">18 voies fournisseur–article–site</span><span class="chip">30 simulations par test</span><span class="chip">aucune probabilité historique</span></div>
  </header>
  <section class="definitions" id="definitions"></section>
  <nav class="tabs" aria-label="Trois vues">
    <button class="active" data-view="incidents">1. Incident fournisseur</button>
    <button data-view="lots">2. Lots, client et impact</button>
    <button data-view="actions">3. Leviers et risque restant</button>
  </nav>
  <main>
    <section class="view active" id="view-incidents">
      <div class="intro"><h2>Quel dossier examiner sous chacun des deux incidents ?</h2><p>Chaque incident est imposé seul, sur une seule voie, dans une période de 42 jours choisie parce que le flux y est fortement exposé. Les deux incidents ne sont ni additionnés ni comparés comme s’ils avaient la même gravité.</p></div>
      <div class="grid states" id="state-cards"></div>
      <article class="panel">
        <h3>Signaux et variation entre simulations</h3>
        <p>La moyenne résume les 30 comparaisons avec/sans incident. P10–P90 est la plage allant du 10e au 90e centile : environ 80 % des résultats simulés se trouvent entre ces deux bornes.</p>
        <div class="toolbar"><div class="field"><label>SITUATION DE DÉPART SIMULÉE</label><select id="risk-state"></select></div><div class="field"><label>INCIDENT IMPOSÉ</label><select id="risk-mechanism"></select></div></div>
        <p class="reading" id="incident-reading"></p>
        <div class="priority-list" id="priority-list"></div>
      </article>
    </section>

    <section class="view" id="view-lots">
      <div class="intro"><h2>Quels lots et quel nœud client sont touchés, et avec quel impact ?</h2><p>Chaque dossier détaille une seule simulation représentative. Ce cas illustre le chemin des lots ; la moyenne et la variation P10–P90 viennent, elles, des 30 simulations du même test.</p></div>
      <div id="lot-content"></div>
    </section>

    <section class="view" id="view-actions">
      <div class="intro"><h2>Quels leviers ont agi, et que reste-t-il à couvrir ?</h2><p>Un gain n’est affiché que lorsque le levier a effectivement agi dans les simulations comparées. Il ne constitue ni une recommandation automatique ni une promesse économique.</p></div>
      <article class="panel"><h3>Leviers testés</h3><p id="action-intro"></p><div class="actions" id="action-results"></div><div id="action-refusals"></div></article>
      <article class="remaining"><h3>Risque restant</h3><p id="remaining-risk"></p><p><b>Non calculés :</b> probabilité annuelle d’incident, exposition résiduelle complète, coût complet et retour sur investissement.</p></article>
      <article class="panel"><h3>Limites à conserver dans toute décision</h3><div class="grid limits" id="limits"></div></article>
    </section>
  </main>
  <footer>Résultats conditionnels d’un modèle · aucune performance fournisseur historique affichée</footer>
  <script id="delivery-data" type="application/json">__DATA__</script>
  <script>
  (()=>{
    "use strict";
    const D=JSON.parse(document.getElementById("delivery-data").textContent),$=id=>document.getElementById(id);
    const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
    const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null},fmt=(v,d=1)=>num(v)===null?"—":new Intl.NumberFormat("fr-FR",{maximumFractionDigits:d}).format(Number(v)),pt=v=>`${fmt(v,2)} point${Math.abs(Number(v))>1?"s":""}`;
    const mechanism=id=>D.campaign.mechanisms.find(r=>r.id===id)||{label:id,hypothesis:""},state=id=>D.campaign.states.find(r=>r.id===id)||{label:id};
    $("definitions").innerHTML=D.definitions.map(r=>`<div class="definition"><b>${esc(r.term)}</b><span>${esc(r.meaning)}</span></div>`).join("");
    document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tabs button").forEach(x=>x.classList.toggle("active",x===b));document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===`view-${b.dataset.view}`))});
    $("state-cards").innerHTML=D.campaign.states.map(r=>`<article class="state"><span class="badge sim">SIMULÉ</span><strong>${fmt(r.globalServicePct,2)} %</strong><small>${esc(r.label)} · service global à l’heure obtenu</small></article>`).join("");
    const riskState=$("risk-state"),riskMechanism=$("risk-mechanism");riskState.innerHTML=D.campaign.states.map(r=>`<option value="${esc(r.id)}">${esc(r.label)}</option>`).join("");riskMechanism.innerHTML=D.campaign.mechanisms.map(r=>`<option value="${esc(r.id)}">${esc(r.label)}</option>`).join("");
    function drawPriorities(){const m=mechanism(riskMechanism.value),rows=D.campaign.priorities.filter(r=>r.state===riskState.value&&r.mechanism===riskMechanism.value).sort((a,b)=>(Number(a.position)||999)-(Number(b.position)||999));$("incident-reading").innerHTML=`<b>Hypothèse :</b> ${esc(m.hypothesis)} Ce test ne dit pas à quelle fréquence cet incident arrive.`;$("priority-list").innerHTML=rows.length?rows.map(r=>`<article class="priority"><div><span class="badge signal">SIGNAL DE PRIORITÉ</span><h3>${esc(r.supplier)} · article ${esc(r.item)} → ${esc(r.destination)}</h3><small>Voie ${esc(r.lane)} · produit alimenté ${esc(r.targetProduct)} · ${r.supplementaryBacklogSignal?"signal de retard complémentaire, sans perte de service démontrée":"perte de service simulée"}</small><small><b>Preuve physique disponible :</b> ${esc(r.physicalEvidenceLabel)}</small></div><div class="value">${r.supplementaryBacklogSignal?`${fmt(r.backlog.mean,2)} jours de demande en retard`:`moyenne ${pt(r.service.mean)}`}<small>${r.supplementaryBacklogSignal?"hors classement du service":`P10–P90 : ${pt(r.service.p10)} à ${pt(r.service.p90)}`}</small></div></article>`).join(""):'<div class="empty">Aucun signal retenu pour ce test. Aucun dossier n’est ajouté pour compléter artificiellement la liste.</div>'}
    riskState.onchange=drawPriorities;riskMechanism.onchange=drawPriorities;drawPriorities();
    const missingLabel=id=>({shipments:"expédition",material_receipts:"réception matière",consumptions:"consommation / fabrication",campaigns:"campagne de fabrication",batches:"lot de fabrication",finished_lots:"lot fini",client_events:"contact client agrégé"}[id]||id);
    function renderLot(d,i){const t=d.traceCounts,k=d.kpis,p=d.traceProof,stages=[["Expédition",t.shipments],["Réception matière",t.material_receipts],["Consommation / fabrication",t.consumptions],["Lot fini",t.finished_lots],["Client agrégé",t.client_events]],m=mechanism(d.mechanism);return `<p class="notice">${esc(D.lots.demonstrationMessage)}</p><div class="lot-tabs">${D.lots.dossiers.map((r,j)=>`<button class="${i===j?"active":""}" data-lot="${j}">${esc(r.supplier)} · ${esc(mechanism(r.mechanism).label)}</button>`).join("")}</div><article class="panel"><span class="badge ${p.level==="complete"?"ok":"hyp"}">${esc(p.label)}</span><h3>${esc(d.supplier)} · article ${esc(d.item)} → ${esc(d.destination)}</h3><p><b>Incident simulé :</b> ${esc(m.label)}. Le cas montré est une simulation représentative choisie parmi ${fmt(d.exercisedCount,0)}/30 où l’expédition a été touchée ; ce n’est pas la moyenne.</p><div class="grid kpis"><div class="metric"><strong>${pt(d.impact.mean)}</strong><small>perte de service moyenne · 30 simulations</small></div><div class="metric"><strong>${pt(d.impact.p10)} à ${pt(d.impact.p90)}</strong><small>variation P10–P90 · 30 simulations</small></div><div class="metric"><strong>${pt(k.service_loss_pp)}</strong><small>perte de service · cas représentatif</small></div><div class="metric"><strong>${fmt(k.on_due_units_lost,0)}</strong><small>unités à l’heure perdues · cas représentatif</small></div></div></article><article class="panel"><h3>Traçabilité disponible dans le cas représentatif</h3><div class="grid trace">${stages.map(([name,count])=>`<div class="trace-step ${Number(count)>0?"present":"missing"}"><b>${fmt(count,0)}</b><small>${esc(name)}</small></div>`).join("")}</div><p class="notice">${p.level==="complete"?"Les cinq étapes de généalogie ont des traces. Cela prouve un contact jusqu’au nœud client agrégé dans ce calcul, pas tout l’enchaînement dynamique ni une perte attribuée à un client réel.":`La trace s’arrête avant le client agrégé. Étapes absentes : ${p.missingStages.map(missingLabel).map(esc).join(", ")||"aval non démontré"}.`}</p>${d.chain.length?`<details><summary>Voir l’extrait des identifiants simulés</summary><div class="scroll"><table><thead><tr><th>Expédition / jour</th><th>Lot entrant</th><th>Fabrication</th><th>Lot fini</th><th>Client agrégé</th></tr></thead><tbody>${d.chain.map(r=>`<tr><td>${esc(r.shipment)} · J${r.decisionDay}</td><td>${esc(r.materialLot)}</td><td>${r.campaigns.length?r.campaigns.map(esc).join("<br>"):"—"}</td><td>${r.finishedLots.length?r.finishedLots.map(x=>esc(x.id)).join("<br>"):"—"}</td><td>${r.clientLots.length?r.clientLots.map(x=>`${esc(x.node)} · ${esc(x.id)}`).join("<br>"):"—"}</td></tr>`).join("")}</tbody></table></div><p class="muted">${fmt(d.chainRowsShown,0)}/${fmt(d.chainRowsTotal,0)} relations expédition–réception affichées.</p></details>`:""}</article>`}
    function bindLot(i){const d=D.lots.dossiers[i];$("lot-content").innerHTML=renderLot(d,i);document.querySelectorAll("[data-lot]").forEach(b=>b.onclick=()=>bindLot(Number(b.dataset.lot)))}
    if(D.lots.dossiers.length)bindLot(0);else $("lot-content").innerHTML=`<div class="empty"><b>Aucun dossier de lots retenu.</b><br>${esc(D.lots.demonstrationMessage)}</div>`;
    $("action-intro").textContent=D.actions.message;
    const gain=g=>g.mean==null?"—":`<strong>${fmt(g.mean,g.unit==="point"?2:0)} ${esc(g.unit)}</strong><small>moyenne · P10–P90 ${fmt(g.p10,g.unit==="point"?2:0)} à ${fmt(g.p90,g.unit==="point"?2:0)} · ${fmt(g.count,0)} simulations</small>`;
    $("action-results").innerHTML=D.actions.results.length?D.actions.results.map(r=>`<article class="action"><span class="badge ${r.status==="estimated_on_physically_exercised_seeds"?"ok":"hyp"}">${r.status==="estimated_on_physically_exercised_seeds"?"LEVIER EXERCÉ":"NON TESTABLE DANS CE CAS"}</span><h4>${esc(r.label)}</h4><p>${esc(r.supplier)} · article ${esc(r.item)} → ${esc(r.destination)} · levier actif dans ${fmt(r.exercisedCount,0)}/${fmt(r.pairedCount,0)} simulations comparées.</p>${r.gains.length?`<div class="grid gains">${r.gains.map(g=>`<div class="metric">${gain(g)}<small>${esc(g.label)}</small></div>`).join("")}</div>`:'<p>Aucun gain estimé.</p>'}</article>`).join(""):'<div class="empty">Aucun gain de levier chiffré.</div>';
    $("action-refusals").innerHTML=D.actions.refusals.length?`<p class="notice"><b>Leviers non simulés dans ces cas :</b> ${D.actions.refusals.map(r=>esc(r.label)).join(" · ")}</p>`:"";
    $("remaining-risk").textContent=D.remainingRisk.message;$("limits").innerHTML=D.limits.map(x=>`<div class="limit">${esc(x)}</div>`).join("");
  })();
  </script>
</body>
</html>
"""


def _safe_json(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return raw.replace("</", "<\\/").replace("<!--", "<\\!--")


def render_html(payload: Mapping[str, Any]) -> str:
    document = HTML_TEMPLATE.replace("__DATA__", _safe_json(payload))
    if document.count('class="view') != 3:
        raise V5FinalDeliveryError("Le livrable ne contient pas exactement trois vues")
    visible_template = re.sub(
        r'<script id="delivery-data".*?</script>', "", document, flags=re.DOTALL
    ).casefold()
    forbidden = (
        "campagne fournisseurs v4",
        "prioritaires v4",
        "sweep",
        " gate ",
        "hash",
    )
    if any(term in visible_template for term in forbidden):
        raise V5FinalDeliveryError("Vocabulaire technique ou branding ancien affiché")
    return document


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def manifest_path_for(output_html: Path) -> Path:
    return output_html.with_suffix(output_html.suffix + ".manifest.json")


def build_delivery(
    *,
    campaign_root: Path,
    results_dir: Path,
    curves_dir: Path | None,
    qualification_dir: Path,
    output_html: Path,
    replay_root: Path | None = None,
    target_registry_path: Path | None = None,
    dashboard_html: Path | None = None,
    action_results_root: Path | None = None,
    legacy_risk_html: Path | None = None,
    legacy_control_html: Path | None = None,
) -> dict[str, Any]:
    output = output_html.resolve()
    manifest_path = manifest_path_for(output)
    if output.exists() or manifest_path.exists():
        raise FileExistsError(f"Refus d’écraser une livraison existante : {output}")
    payload, bindings = build_delivery_payload(
        campaign_root=campaign_root,
        results_dir=results_dir,
        curves_dir=curves_dir,
        replay_root=replay_root,
        qualification_dir=qualification_dir,
        output_html=output,
        target_registry_path=target_registry_path,
        dashboard_html=dashboard_html,
        action_results_root=action_results_root,
        legacy_risk_html=legacy_risk_html,
        legacy_control_html=legacy_control_html,
    )
    document = render_html(payload)
    encoded = document.encode("utf-8")
    unsigned = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "generated_at_utc": delivery_v4.utc_now(),
        "offline_single_file": True,
        "view_count": 3,
        "output_html": output.name,
        "output_html_sha256": hashlib.sha256(encoded).hexdigest(),
        "output_html_bytes": len(encoded),
        "payload_sha256": delivery_v4.stable_sha256(payload),
        "generator": str(Path(__file__).resolve()),
        "generator_sha256": _sha256_file(Path(__file__).resolve()),
        "source_bindings": bindings,
        "scientific_scope": {
            "mechanisms": sorted(EXPECTED_MECHANISMS),
            "mechanisms_kept_separate": True,
            "simulations_per_test": EXPECTED_REPETITIONS,
            "historical_incident_probability_estimated": False,
            "observed_supplier_performance_displayed": False,
            "full_dynamic_cascade_claimed": False,
            "portfolio_remaining_risk_estimated": False,
            "complete_cost_or_roi_claimed": False,
            "physical_qualification_required": True,
        },
    }
    manifest = {**unsigned, "delivery_signature": delivery_v4.stable_sha256(unsigned)}
    _atomic_write_text(output, document)
    try:
        _atomic_write_text(
            manifest_path,
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    validate_delivery(output)
    return manifest


def _embedded_payload(document: str) -> dict[str, Any]:
    matches = re.findall(
        r'<script id="delivery-data" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        raise V5FinalDeliveryError("Données autonomes absentes ou dupliquées")
    try:
        payload = json.loads(html.unescape(matches[0]))
    except json.JSONDecodeError as exc:
        raise V5FinalDeliveryError("Données autonomes illisibles") from exc
    if not isinstance(payload, dict):
        raise V5FinalDeliveryError("Objet de données autonome attendu")
    return payload


def validate_delivery(path: Path) -> dict[str, Any]:
    output = path.resolve()
    manifest_path = manifest_path_for(output)
    if not output.is_file() or not manifest_path.is_file():
        raise V5FinalDeliveryError("HTML ou manifeste de livraison absent")
    manifest = delivery_v4.read_json(manifest_path)
    signature = delivery_v4.verify_signature(
        manifest, "delivery_signature", label="manifeste de livraison V5"
    )
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "complete_validated"
        or manifest.get("offline_single_file") is not True
        or int(manifest.get("view_count") or -1) != 3
        or manifest.get("output_html") != output.name
        or int(manifest.get("output_html_bytes") or -1) != output.stat().st_size
        or manifest.get("output_html_sha256") != _sha256_file(output)
    ):
        raise V5FinalDeliveryError("Manifeste de livraison V5 incohérent")
    document = output.read_text(encoding="utf-8")
    payload = _embedded_payload(document)
    scope = manifest.get("scientific_scope")
    if (
        payload.get("schemaVersion") != SCHEMA_VERSION
        or int(payload.get("viewCount") or -1) != 3
        or document.count('class="view') != 3
        or delivery_v4.stable_sha256(payload) != manifest.get("payload_sha256")
        or not isinstance(scope, Mapping)
        or set(scope.get("mechanisms") or []) != EXPECTED_MECHANISMS
        or scope.get("historical_incident_probability_estimated") is not False
        or scope.get("observed_supplier_performance_displayed") is not False
        or scope.get("full_dynamic_cascade_claimed") is not False
        or scope.get("portfolio_remaining_risk_estimated") is not False
        or scope.get("complete_cost_or_roi_claimed") is not False
        or scope.get("physical_qualification_required") is not True
        or payload.get("remainingRisk", {}).get("roiAvailable") is not False
    ):
        raise V5FinalDeliveryError("Contenu scientifique V5 incohérent")
    return {
        "valid": True,
        "path": str(output),
        "manifest_path": str(manifest_path),
        "delivery_signature": signature,
        "sha256": manifest["output_html_sha256"],
        "bytes": manifest["output_html_bytes"],
        "view_count": 3,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--campaign-root", type=Path, required=True)
    build.add_argument("--results-dir", type=Path, required=True)
    build.add_argument("--curves-dir", type=Path)
    build.add_argument("--lot-replay-root", type=Path)
    build.add_argument("--qualification-dir", type=Path, required=True)
    build.add_argument("--dashboard-html", type=Path)
    build.add_argument("--target-registry", type=Path)
    build.add_argument("--action-results-root", type=Path)
    build.add_argument("--legacy-risk-html", type=Path)
    build.add_argument("--legacy-control-html", type=Path)
    build.add_argument("--output-html", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--path", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "build":
            result = build_delivery(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                curves_dir=args.curves_dir,
                replay_root=args.lot_replay_root,
                qualification_dir=args.qualification_dir,
                output_html=args.output_html,
                target_registry_path=args.target_registry,
                dashboard_html=args.dashboard_html,
                action_results_root=args.action_results_root,
                legacy_risk_html=args.legacy_risk_html,
                legacy_control_html=args.legacy_control_html,
            )
        else:
            result = validate_delivery(args.path)
    except (V5FinalDeliveryError, FileExistsError) as exc:
        print(f"LIVRAISON V5 REFUSÉE : {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
