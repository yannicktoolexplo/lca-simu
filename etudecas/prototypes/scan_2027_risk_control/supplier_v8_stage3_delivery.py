#!/usr/bin/env python3
"""Build the corrected V8 Stage2 V3 standalone client delivery.

The delivery uses a native V8 exposure-registry reader and makes two scopes
unmissable: how the 42-day test window was selected, and whether the signed lot
or action evidence actually belongs to the visual focus 338929.  It never forces
338929 into the statistical selection and never attributes another dossier's
lots or actions to it.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_delivery as delivery_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_delivery as predecessor_delivery,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_dashboard as dashboard_v8,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage3_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
FOCUS_LANE_ID = predecessor_delivery.FOCUS_LANE_ID
FOCUS_ITEM_ID = predecessor_delivery.FOCUS_ITEM_ID
EXPECTED_MECHANISMS = predecessor_delivery.EXPECTED_MECHANISMS


class Stage2DeliveryError(common.Stage2Error):
    """A source or client-facing claim does not satisfy Stage2 V3."""


@contextmanager
def _v3_reducer_binding(paths: common.Stage2Paths) -> Iterator[None]:
    """Bind mature reducers to V3 and the native V8 reader, then restore all."""

    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline_v7,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage3_pipeline as pipeline_v3,
    )

    previous_delivery = {
        "common": delivery_v7.common,
        "dashboard_v7": delivery_v7.dashboard_v7,
        "finalizer_v7": delivery_v7.finalizer_v7,
    }
    previous_pipeline = {
        "common": pipeline_v7.common,
        "SCHEMA_VERSION": pipeline_v7.SCHEMA_VERSION,
        "UPSTREAM_NAME": pipeline_v7.UPSTREAM_NAME,
        "_contract_payload": pipeline_v7._contract_payload,  # noqa: SLF001
    }
    delivery_v7.common = common
    delivery_v7.dashboard_v7 = dashboard_v8.NativeV8DashboardReader(paths.campaign_root)
    delivery_v7.finalizer_v7 = SimpleNamespace(
        V7_RESULT_OVERLAY_NAME=finalizer_v8.V8_RESULT_OVERLAY_NAME
    )
    pipeline_v7.common = common
    pipeline_v7.SCHEMA_VERSION = pipeline_v3.SCHEMA_VERSION
    pipeline_v7.UPSTREAM_NAME = pipeline_v3.UPSTREAM_NAME
    pipeline_v7._contract_payload = pipeline_v3._contract_payload_v3  # noqa: SLF001
    try:
        yield
    finally:
        for name, value in previous_pipeline.items():
            setattr(pipeline_v7, name, value)
        for name, value in previous_delivery.items():
            setattr(delivery_v7, name, value)


def _identity_matches_focus(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("lane_id") or "") == FOCUS_LANE_ID
        and str(row.get("item_id") or "").removeprefix("item:") == FOCUS_ITEM_ID
    )


def _focus_scope(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    focus = payload.get("focus") or {}
    cascade = payload.get("cascade") or {}
    actions = payload.get("actions") or {}
    if not all(isinstance(value, Mapping) for value in (focus, cascade, actions)):
        raise Stage2DeliveryError("Périmètre focus/lots/actions V3 absent.")
    details = cascade.get("detailed_replays") or []
    action_rows = actions.get("actions") or []
    if not isinstance(details, list) or not isinstance(action_rows, list):
        raise Stage2DeliveryError("Listes de preuves lots/actions V3 invalides.")
    if any(not isinstance(row, Mapping) for row in [*details, *action_rows]):
        raise Stage2DeliveryError("Preuve lots/action V3 non structurée.")
    focus_details = [row for row in details if _identity_matches_focus(row)]
    focus_actions = [row for row in action_rows if _identity_matches_focus(row)]
    selected_id = str(focus.get("selected_dossier_id") or "")
    detail_ids = [str(row.get("dossier_id") or "") for row in focus_details]
    if "" in detail_ids or len(set(detail_ids)) != len(detail_ids):
        raise Stage2DeliveryError(
            "Identifiant de généalogie 338929 absent ou dupliqué."
        )
    action_dossier_ids = {str(row.get("dossier_id") or "") for row in focus_actions}
    if (
        bool(focus.get("selected_for_detailed_replay")) != bool(focus_details)
        or (focus_details and selected_id not in detail_ids)
        or (not focus_details and selected_id)
        or (focus_actions and not focus_details)
        or not action_dossier_ids.issubset(set(detail_ids))
    ):
        raise Stage2DeliveryError(
            "Le lien entre 338929, ses lots détaillés et ses actions est incohérent."
        )
    has_detail = bool(focus_details)
    has_action = bool(focus_actions)
    other_detail_count = len(details) - len(focus_details)
    other_action_count = len(action_rows) - len(focus_actions)
    if has_detail and has_action:
        notice = (
            f"338929 dispose de {len(focus_details)} généalogie(s) détaillée(s) "
            "signée(s) et d'au moins une action simulée sur le ou les mêmes dossiers. "
            "Les deux mécanismes restent séparés et chaque dossier est identifié."
        )
    elif has_detail and other_action_count:
        notice = (
            "338929 dispose d'une généalogie détaillée signée, mais aucune action "
            "affichée ne porte sur 338929. Les actions concernent d'autres dossiers "
            "signés, nommés avant chaque résultat."
        )
    elif has_detail:
        notice = (
            "338929 dispose d'une généalogie détaillée signée, mais aucune action "
            "représentable n'est publiée pour ce dossier. Aucun gain n'est inventé."
        )
    elif other_detail_count or other_action_count:
        notice = (
            "338929 est le point d'entrée agrégé, mais ne fait pas partie des dossiers "
            "retenus pour le détail. Les lots et actions présentés concernent d'autres "
            "dossiers signés, toujours identifiés par fournisseur, article et dossier."
        )
    else:
        notice = (
            "338929 est présenté uniquement au niveau agrégé : aucune généalogie ni "
            "action détaillée n'est attribuée à cet article. Aucun résultat n'est forcé."
        )
    scope = {
        "focus_has_detailed_replay": has_detail,
        "focus_has_action": has_action,
        "focus_dossier_id": selected_id or None,
        "focus_dossier_ids": detail_ids,
        "focus_detailed_replay_count": len(focus_details),
        "focus_action_count": len(focus_actions),
        "other_detailed_dossier_count": other_detail_count,
        "other_action_count": other_action_count,
        "selection_forced": False,
        "notice_fr": notice,
    }
    return scope, notice


def _window_contract(overlay: Mapping[str, Any]) -> dict[str, Any]:
    source = overlay.get("target_selection_v8") or {}
    statistics = overlay.get("statistical_semantics") or {}
    if (
        source.get("window_days") != 42
        or source.get("earliest_candidate_day") != 180
        or source.get("required_comparable_seed_count_per_lane") != 30
        or source.get("campaign_seed_count") != 30
        or source.get("operating_state_count") != 3
        or source.get("lane_count") != 18
        or source.get("target_cell_count") != 1_620
        or float(source.get("maximum_within_seed_cross_state_quantity_ratio") or -1)
        != 1.5
        or source.get("positive_normally_deliverable_quantity_required") is not True
        or source.get("same_lane_window_across_all_states_and_seeds") is not True
        or source.get("incident_outcomes_used") is not False
        or source.get("additional_simulation_engine_runs") != 0
        or source.get("historical_incident_probability_estimated") is not False
        or statistics.get("exposure_comparability_gate")
        != "30_of_30_seeds_for_every_lane"
        or "at least 24 of 30 positive paired effects"
        not in str(statistics.get("effect_detection_rule") or "")
        or statistics.get("the_24_of_30_rule_is_an_exposure_gate") is not False
        or statistics.get("the_30_of_30_exposure_rule_is_an_incident_probability")
        is not False
    ):
        raise Stage2DeliveryError(
            "Le contrat signé de sélection des fenêtres V8 a changé."
        )
    return {
        "title_fr": "Ce que représente la fenêtre fournisseur testée",
        "selection_fr": (
            "Pour chaque voie, le moteur retient la première fenêtre de 42 jours à "
            "partir de J180 où un flux normalement livrable est positif dans les "
            "trois niveaux et les 30 répétitions, avec un rapport de quantité entre "
            "niveaux inférieur ou égal à 1,5."
        ),
        "interpretation_fr": (
            "La fenêtre est choisie sur les situations normales signées, sans lire "
            "les résultats d'incident et sans nouvelle simulation. Ce n'est ni la "
            "pire période, ni une saison moyenne, ni une fréquence ou une probabilité "
            "d'incident fournisseur. Aucun résultat n'est forcé pour la démonstration "
            "et aucun dossier n'est ajouté pour servir le récit."
        ),
        "statistics_rule_fr": (
            "Les règles 30/30 et 24/30 ne répondent pas à la même question : 30/30 "
            "garantit que la fenêtre contient un flux comparable dans chaque "
            "simulation ; ensuite, 24/30 signifie qu'au moins 24 effets appariés "
            "vont dans le même sens, avec une borne basse de l'intervalle de confiance "
            "à 95 % supérieure à zéro, pour qualifier un signal récurrent."
        ),
        "window_days": 42,
        "earliest_candidate_day": 180,
        "required_comparable_seed_count": 30,
        "operating_state_count": 3,
        "maximum_cross_state_quantity_ratio": 1.5,
        "positive_normally_deliverable_quantity_required": True,
        "same_lane_window_across_all_states_and_seeds": True,
        "incident_outcomes_used": False,
        "additional_simulation_engine_runs": 0,
        "worst_period_claimed": False,
        "average_season_claimed": False,
        "historical_frequency_or_probability_claimed": False,
        "effect_detection_positive_pair_count": 24,
        "effect_detection_requires_positive_ci95_lower_bound": True,
        "effect_detection_rule_is_exposure_gate": False,
    }


def _actions_with_attributed_refusals(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach every refused action to its signed dossier identity."""

    cascade = payload.get("cascade") or {}
    actions = payload.get("actions") or {}
    if not isinstance(cascade, Mapping) or not isinstance(actions, Mapping):
        raise Stage2DeliveryError("Structure lots/actions V3 absente.")
    details = cascade.get("detailed_replays") or []
    refusals = actions.get("refusals") or []
    if not isinstance(details, list) or not isinstance(refusals, list):
        raise Stage2DeliveryError("Listes lots/refus d'action V3 invalides.")
    detail_by_dossier: dict[str, Mapping[str, Any]] = {}
    for detail in details:
        if not isinstance(detail, Mapping):
            raise Stage2DeliveryError("Généalogie V3 non structurée.")
        dossier_id = str(detail.get("dossier_id") or "")
        if dossier_id:
            if dossier_id in detail_by_dossier:
                raise Stage2DeliveryError(
                    "Dossier de généalogie dupliqué pour l'attribution des refus."
                )
            detail_by_dossier[dossier_id] = detail

    attributed = []
    for refusal in refusals:
        if not isinstance(refusal, Mapping):
            raise Stage2DeliveryError("Refus d'action V3 non structuré.")
        dossier_id = str(refusal.get("dossier_id") or "")
        detail = detail_by_dossier.get(dossier_id)
        if detail is None:
            raise Stage2DeliveryError(
                "Un refus d'action n'est pas rattachable à un dossier détaillé signé."
            )
        identity = {
            "dossier_id": dossier_id,
            "lane_id": str(detail.get("lane_id") or ""),
            "supplier_id": str(detail.get("supplier_id") or ""),
            "item_id": str(detail.get("item_id") or "").removeprefix("item:"),
            "mechanism": str(detail.get("mechanism") or ""),
        }
        if (
            not all(identity.values())
            or identity["mechanism"] not in EXPECTED_MECHANISMS
        ):
            raise Stage2DeliveryError(
                "L'identité dossier/fournisseur/article d'un refus est incomplète."
            )
        attributed.append({**dict(refusal), **identity})
    return {**dict(actions), "refusals": attributed}


def _adapt_payload(
    base: Mapping[str, Any], overlay: Mapping[str, Any]
) -> dict[str, Any]:
    unsigned = {key: value for key, value in base.items() if key != "payload_signature"}
    payload = dict(unsigned)
    payload["schema_version"] = SCHEMA_VERSION
    payload["title"] = "338929 d'abord, puis les décisions réellement prouvées"
    campaign = payload.get("campaign")
    focus = payload.get("focus")
    limits = payload.get("limits")
    bindings = payload.get("bindings")
    terminology = payload.get("terminology")
    if not all(
        isinstance(value, Mapping)
        for value in (campaign, focus, limits, bindings, terminology)
    ):
        raise Stage2DeliveryError("Structure de présentation V3 incomplète.")
    mechanisms = {str(row.get("id") or "") for row in campaign.get("mechanisms") or []}
    if mechanisms != EXPECTED_MECHANISMS:
        raise Stage2DeliveryError("Les deux hypothèses fournisseurs V8 ont changé.")
    if (
        focus.get("lane_id") != FOCUS_LANE_ID
        or focus.get("item_id") != FOCUS_ITEM_ID
        or focus.get("requested_338929_present") is not True
    ):
        raise Stage2DeliveryError("La voie agrégée 338929 n'est pas disponible.")
    if (
        limits.get("quality_incident_included") is not False
        or limits.get("capacity_or_availability_modified") is not False
        or limits.get("automatic_regulation") is not False
        or campaign.get("multiple_incidents_combined") is not False
    ):
        raise Stage2DeliveryError("La portée des incidents/actions V3 a changé.")
    expected_terms = {"OBSERVÉ", "SIMULÉ", "SIGNAL DE PRIORITÉ", "HYPOTHÈSE"}
    if set(terminology) != expected_terms:
        raise Stage2DeliveryError("Le vocabulaire client V3 est incomplet.")

    payload["actions"] = _actions_with_attributed_refusals(payload)
    focus_scope, _ = _focus_scope(payload)
    window_contract = _window_contract(overlay)
    payload["nominal_curves"] = {
        **dict(payload.get("nominal_curves") or {}),
        "population": (
            "30 simulations indépendantes du fonctionnement normal, avec les mêmes "
            "identifiants pour comparer chaque incident à sa référence"
        ),
    }
    payload["target_window_contract"] = window_contract
    payload["presentation"] = {
        "view_order": ["focus_338929", "network_cascades", "decisions"],
        "focus_item_id": FOCUS_ITEM_ID,
        "focus_lane_id": FOCUS_LANE_ID,
        **focus_scope,
        "numbers_are_loaded_from_signed_results": True,
        "future_or_placeholder_results_displayed": False,
    }
    payload["bindings"] = {
        **dict(bindings),
        "v8_result_overlay_signature": overlay["overlay_signature"],
        "native_v8_registry_schema": dashboard_v8.campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION,
        "obsolete_v4_seed_projection_used": False,
    }
    return common.signed(payload, "payload_signature")


def collect_payload(
    paths: common.Stage2Paths,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    paths = paths.resolved()
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage3_pipeline as pipeline_v3,
    )

    pipeline_v3.validate_bound_contract(paths)
    try:
        overlay = finalizer_v8.validate_v8_overlay(
            paths.campaign_root, paths.results_dir
        )
    except Exception as exc:
        raise Stage2DeliveryError("La surcouche finale V8 est invalide.") from exc
    with _v3_reducer_binding(paths):
        base, sources = delivery_v7.collect_payload(paths)
    payload = _adapt_payload(base, overlay)
    updated_sources = []
    for source in sources:
        row = dict(source)
        if row.get("role") == "surcouche_resultats_v7":
            row["role"] = "surcouche_resultats_v8"
            row["signature"] = overlay["overlay_signature"]
        updated_sources.append(row)
    overlay_path = paths.results_dir / finalizer_v8.V8_RESULT_OVERLAY_NAME
    if not any(
        Path(str(row.get("path") or "")).resolve() == overlay_path.resolve()
        for row in updated_sources
    ):
        raise Stage2DeliveryError("La preuve V8 n'est pas liée au livrable V3.")
    return payload, updated_sources


def _v3_html_template() -> str:
    template = predecessor_delivery.HTML_TEMPLATE
    replacements = {
        "<title>338929 et risques fournisseurs — démonstration V8</title>": (
            "<title>338929 puis décisions prouvées — risques fournisseurs</title>"
        ),
        "DÉMONSTRATION AUTONOME V8 · RISQUES FOURNISSEURS": (
            "DÉMONSTRATION AUTONOME · RISQUES FOURNISSEURS"
        ),
        "<h1>338929 : du risque fournisseur aux décisions</h1>": (
            "<h1>338929 d'abord, puis les décisions réellement prouvées</h1>"
        ),
        "<main>": "<main>\n__WINDOW_SCOPE__\n__FOCUS_SCOPE__",
        "Fonctionnement sans incident — 30 répétitions V7": (
            "Fonctionnement sans incident — 30 simulations indépendantes"
        ),
        (
            "Quand au moins 24 scénarios sont comparables, le graphique montre les "
            "écarts appariés par rapport à la référence avec leur IC95. Sinon, il "
            "montre trois points descriptifs non reliés et n'interprète pas de pente."
        ): (
            "Les 30 simulations ont une fenêtre de flux comparable. La règle 24/30 "
            "est distincte : elle sert, avec une borne basse de l'IC95 positive, à "
            "qualifier la récurrence d'un effet; elle ne sélectionne pas la fenêtre."
        ),
        "Pas de généalogie V8 détaillée disponible.": (
            "Pas de traçabilité détaillée des lots disponible."
        ),
        (
            '<option value="${i}">${esc(a.label_fr)} · ${esc(a.item_id)} · '
            "${esc(mech(a.mechanism).label)}</option>"
        ): (
            '<option value="${i}">${esc(a.dossier_id)} · ${esc(a.supplier_id)} · '
            "article ${esc(a.item_id)} · ${esc(a.label_fr)} · "
            "${esc(mech(a.mechanism).label)}</option>"
        ),
        (
            "<p>${esc(a.supplier_id)} · ${esc(a.item_id)} · "
            "${esc(stateLabel(a.state))}. L'action a été simulée"
        ): (
            "<p>Dossier ${esc(a.dossier_id)} · ${esc(a.supplier_id)} · article "
            "${esc(a.item_id)} · ${esc(stateLabel(a.state))}. L'action a été simulée"
        ),
        (
            "<p>${esc(a.supplier_id)} · article ${esc(a.item_id)} · "
            "${esc(stateLabel(a.state))}. L'action a réellement agi"
        ): (
            "<p>Dossier ${esc(a.dossier_id)} · ${esc(a.supplier_id)} · article "
            "${esc(a.item_id)} · ${esc(stateLabel(a.state))}. L'action a réellement agi"
        ),
        (
            "${D.actions.refusals.map(r=>`<li><b>${esc(r.label_fr)}</b> — non "
            "simulé : ${esc(r.reason)}</li>`).join('')}"
        ): (
            "${D.actions.refusals.map(r=>`<li><b>Dossier ${esc(r.dossier_id)} · "
            "${esc(r.supplier_id)} · article ${esc(r.item_id)}</b><br>"
            "${esc(r.label_fr)} · ${esc(mech(r.mechanism).label)} — non simulé : "
            "${esc(r.reason)}</li>`).join('')}"
        ),
    }
    for source, replacement in replacements.items():
        if template.count(source) != 1:
            raise Stage2DeliveryError(
                "Le gabarit V8 V2 figé a changé ; adaptation V3 refusée."
            )
        template = template.replace(source, replacement)
    return template


HTML_TEMPLATE = _v3_html_template()


def _callout(title: str, *paragraphs: str, good: bool = False) -> str:
    css = "callout good" if good else "callout"
    body = "".join(f"<p>{html.escape(text)}</p>" for text in paragraphs)
    return f'<div class="{css}"><b>{html.escape(title)}</b>{body}</div>'


def render_html(payload: Mapping[str, Any]) -> str:
    presentation = payload.get("presentation") or {}
    window = payload.get("target_window_contract") or {}
    if not isinstance(presentation, Mapping) or not isinstance(window, Mapping):
        raise Stage2DeliveryError("Portées focus/fenêtre V3 absentes.")
    document = HTML_TEMPLATE.replace(
        "__WINDOW_SCOPE__",
        _callout(
            str(window.get("title_fr") or ""),
            str(window.get("selection_fr") or ""),
            str(window.get("interpretation_fr") or ""),
            str(window.get("statistics_rule_fr") or ""),
            good=True,
        ),
    ).replace(
        "__FOCUS_SCOPE__",
        _callout(
            "Ce qui est — ou n'est pas — prouvé pour 338929",
            str(presentation.get("notice_fr") or ""),
            good=bool(presentation.get("focus_has_detailed_replay"))
            and bool(presentation.get("focus_has_action")),
        ),
    )
    document = document.replace("__DATA__", delivery_v7._safe_json(payload))  # noqa: SLF001
    if (
        document.count('class="view') != 3
        or "__WINDOW_SCOPE__" in document
        or "__FOCUS_SCOPE__" in document
        or "__DATA__" in document
    ):
        raise Stage2DeliveryError("Le livrable V3 doit contenir exactement trois vues.")
    visible = html.unescape(document.split("<script>", 1)[0])
    required_visible = (
        "338929 d'abord",
        "première fenêtre de 42 jours",
        "à partir de J180",
        "flux normalement livrable",
        "30 répétitions",
        "inférieur ou égal à 1,5",
        "ni la pire période",
        "ni une saison moyenne",
        "ni une fréquence ou une probabilité",
        "Les règles 30/30 et 24/30 ne répondent pas à la même question",
        "24 effets appariés",
        str(presentation.get("notice_fr") or ""),
    )
    if any(text not in visible for text in required_visible):
        raise Stage2DeliveryError("Une limite focus/fenêtre V8 n'est pas visible.")
    forbidden = (
        '"design_seed"',
        "graine de conception",
        "fenêtre de forte exposition",
        "quantité planifiée médiane",
    )
    if any(text in document.casefold() for text in forbidden):
        raise Stage2DeliveryError(
            "Le livrable V3 contient encore un libellé de fenêtre V4 obsolète."
        )
    return document


def _manifest_payload(
    paths: common.Stage2Paths,
    payload: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    document: str,
) -> dict[str, Any]:
    raw = document.encode("utf-8")
    presentation = payload["presentation"]
    unsigned = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "output_html": str(paths.final_html),
        "html_sha256": hashlib.sha256(raw).hexdigest(),
        "html_bytes": len(raw),
        "payload_signature": payload["payload_signature"],
        "view_count": 3,
        "standalone": True,
        "external_dependency_count": 0,
        "source_bindings": list(sources),
        "scientific_contract": {
            "state_validation_source": "accepted_official_v7_fixed_triplet",
            "campaign_result_overlay": "complete_validated_v8_overlay",
            "native_v8_registry_reader": True,
            "obsolete_v4_seed_projection_used": False,
            "validation_cases": 450,
            "campaign_rows": 3330,
            "incident_rows": 3240,
            "focus_lane": FOCUS_LANE_ID,
            "focus_has_detailed_replay": presentation["focus_has_detailed_replay"],
            "focus_has_action": presentation["focus_has_action"],
            "maximum_detailed_dossiers": 3,
            "forced_top3": False,
            "quality": False,
            "capacity_or_availability_invented": False,
            "historical_probability": False,
            "actions_open_loop": True,
            "automatic_regulation": False,
            "multiple_incidents_combined": False,
            "full_dynamic_cascade_claimed": False,
            "clients_aggregated": True,
            "action_lot_trace_available": False,
            "days_recovered_cost_or_roi_claimed": False,
            "future_or_placeholder_results_displayed": False,
            "window_is_worst_period": False,
            "window_is_average_season": False,
        },
    }
    return common.signed(unsigned, "manifest_signature")


def validate_delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    paths = paths.resolved()
    manifest_path = Path(str(paths.final_html) + ".manifest.json")
    manifest = common.read_json(manifest_path)
    common.verify_signature(manifest, "manifest_signature", "manifeste HTML V3")
    payload, sources = collect_payload(paths)
    document = render_html(payload)
    expected = _manifest_payload(paths, payload, sources, document)
    actual = paths.final_html.read_text(encoding="utf-8")
    contract = manifest.get("scientific_contract") or {}
    if (
        manifest != expected
        or actual != document
        or actual.count('class="view') != 3
        or "https://" in actual
        or "http://" in actual
        or "€" in actual
        or contract.get("native_v8_registry_reader") is not True
        or contract.get("obsolete_v4_seed_projection_used") is not False
        or contract.get("quality") is not False
        or contract.get("automatic_regulation") is not False
        or contract.get("multiple_incidents_combined") is not False
        or contract.get("action_lot_trace_available") is not False
        or contract.get("days_recovered_cost_or_roi_claimed") is not False
        or contract.get("window_is_worst_period") is not False
        or contract.get("window_is_average_season") is not False
    ):
        raise Stage2DeliveryError("Le livrable V3 ne reproduit plus ses preuves.")
    folded = actual.casefold()
    for text in (
        "aucune probabilité historique",
        "boucle ouverte",
        "aucun incident qualité",
        "aucune capacité/disponibilité modifiée",
        "clients agrégés",
        "lots simulés",
        "devise non renseignée",
        "aucun résultat n'est forcé",
    ):
        if text not in folded:
            raise Stage2DeliveryError(f"Limite métier V3 non visible : {text}")
    return {
        "valid": True,
        "html": str(paths.final_html),
        "html_sha256": manifest["html_sha256"],
        "html_bytes": manifest["html_bytes"],
        "manifest": str(manifest_path),
        "manifest_signature": manifest["manifest_signature"],
        "view_count": 3,
        "focus_lane": FOCUS_LANE_ID,
        "focus_has_detailed_replay": payload["presentation"][
            "focus_has_detailed_replay"
        ],
        "focus_has_action": payload["presentation"]["focus_has_action"],
        "detailed_dossier_count": len(payload["cascade"]["detailed_replays"]),
        "action_result_count": len(payload["actions"]["actions"]),
    }


def build_delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    paths = paths.resolved()
    paths.validate_separation()
    manifest_path = Path(str(paths.final_html) + ".manifest.json")
    if paths.final_html.exists() and manifest_path.exists():
        return validate_delivery(paths)
    if manifest_path.exists():
        raise Stage2DeliveryError("Manifeste HTML V3 orphelin ; écrasement refusé.")
    payload, sources = collect_payload(paths)
    document = render_html(payload)
    manifest = _manifest_payload(paths, payload, sources, document)
    common.publish_new_or_identical(paths.final_html, document.encode("utf-8"))
    common.publish_new_or_identical(
        manifest_path,
        (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return validate_delivery(paths)


def _parser() -> argparse.ArgumentParser:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage3_pipeline as pipeline_v3,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    pipeline_v3.add_path_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage3_pipeline as pipeline_v3,
    )

    args = _parser().parse_args(argv)
    try:
        result = build_delivery(pipeline_v3.paths_from_args(args))
    except Exception as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
