from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_delivery as subject,
)


def _base_payload() -> dict[str, Any]:
    return {
        "schema_version": "legacy",
        "status": "complete_validated",
        "payload_signature": "old",
        "title": "old",
        "view_count": 3,
        "terminology": {
            "OBSERVÉ": "donnée industrielle",
            "SIMULÉ": "résultat du modèle",
            "SIGNAL DE PRIORITÉ": "dossier à examiner",
            "HYPOTHÈSE": "condition imposée",
        },
        "campaign": {
            "mechanisms": [
                {"id": "transport_delay"},
                {"id": "planned_delivery_shortfall"},
            ],
            "multiple_incidents_combined": False,
        },
        "focus": {
            "lane_id": subject.FOCUS_LANE_ID,
            "item_id": subject.FOCUS_ITEM_ID,
            "requested_338929_present": True,
            "selected_for_detailed_replay": False,
            "selected_dossier_id": None,
        },
        "nominal_curves": {"population": "old", "series": []},
        "cascade": {"detailed_replays": []},
        "actions": {"actions": [], "refusals": []},
        "limits": {
            "quality_incident_included": False,
            "capacity_or_availability_modified": False,
            "automatic_regulation": False,
        },
        "bindings": {"v7_result_signature": "a" * 64},
    }


def _overlay() -> dict[str, Any]:
    return {
        "status": "complete_validated_v8_overlay",
        "overlay_signature": "b" * 64,
        "target_selection_v8": {
            "window_days": 42,
            "earliest_candidate_day": 180,
            "required_comparable_seed_count_per_lane": 30,
            "campaign_seed_count": 30,
            "operating_state_count": 3,
            "lane_count": 18,
            "target_cell_count": 1_620,
            "maximum_within_seed_cross_state_quantity_ratio": 1.5,
            "positive_normally_deliverable_quantity_required": True,
            "same_lane_window_across_all_states_and_seeds": True,
            "incident_outcomes_used": False,
            "additional_simulation_engine_runs": 0,
            "historical_incident_probability_estimated": False,
        },
        "statistical_semantics": {
            "exposure_comparability_gate": "30_of_30_seeds_for_every_lane",
            "effect_detection_rule": (
                "paired CI95 lower bound > 0 and at least 24 of 30 positive paired effects"
            ),
            "the_24_of_30_rule_is_an_exposure_gate": False,
            "the_30_of_30_exposure_rule_is_an_incident_probability": False,
        },
    }


def _dossier(dossier_id: str, lane_id: str, item_id: str) -> dict[str, Any]:
    return {"dossier_id": dossier_id, "lane_id": lane_id, "item_id": item_id}


def test_adaptation_is_additive_and_does_not_force_focus() -> None:
    source = _base_payload()
    before = copy.deepcopy(source)
    payload = subject._adapt_payload(source, _overlay())  # noqa: SLF001

    assert source == before
    assert payload["schema_version"] == subject.SCHEMA_VERSION
    assert payload["presentation"]["focus_has_detailed_replay"] is False
    assert payload["presentation"]["focus_has_action"] is False
    assert payload["presentation"]["selection_forced"] is False
    assert "aucune généalogie ni action" in payload["presentation"]["notice_fr"]
    assert payload["target_window_contract"]["worst_period_claimed"] is False
    assert payload["target_window_contract"]["average_season_claimed"] is False
    assert payload["bindings"]["obsolete_v4_seed_projection_used"] is False
    subject.common.verify_signature(payload, "payload_signature", "payload V3")


def test_other_dossiers_are_explicitly_not_attributed_to_338929() -> None:
    source = _base_payload()
    source["cascade"]["detailed_replays"] = [
        _dossier("D-OTHER", "lane-other", "099439")
    ]
    source["actions"]["actions"] = [_dossier("D-OTHER", "lane-other", "099439")]
    payload = subject._adapt_payload(source, _overlay())  # noqa: SLF001

    presentation = payload["presentation"]
    assert presentation["focus_has_detailed_replay"] is False
    assert presentation["focus_has_action"] is False
    assert presentation["other_detailed_dossier_count"] == 1
    assert presentation["other_action_count"] == 1
    assert "concernent d'autres dossiers signés" in presentation["notice_fr"]


def test_focus_action_requires_same_signed_focus_dossier() -> None:
    source = _base_payload()
    source["actions"]["actions"] = [
        _dossier("D-FOCUS", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID)
    ]
    with pytest.raises(subject.Stage2DeliveryError, match="lien entre 338929"):
        subject._adapt_payload(source, _overlay())  # noqa: SLF001


def test_focus_replay_and_action_are_linked_only_by_same_dossier() -> None:
    source = _base_payload()
    source["focus"]["selected_for_detailed_replay"] = True
    source["focus"]["selected_dossier_id"] = "D-FOCUS"
    source["cascade"]["detailed_replays"] = [
        _dossier("D-FOCUS", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID)
    ]
    source["actions"]["actions"] = [
        _dossier("D-FOCUS", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID)
    ]
    payload = subject._adapt_payload(source, _overlay())  # noqa: SLF001
    assert payload["presentation"]["focus_has_detailed_replay"] is True
    assert payload["presentation"]["focus_has_action"] is True
    assert payload["presentation"]["focus_dossier_id"] == "D-FOCUS"


def test_two_focus_genealogies_for_two_mechanisms_are_supported() -> None:
    source = _base_payload()
    source["focus"]["selected_for_detailed_replay"] = True
    source["focus"]["selected_dossier_id"] = "D-TRANSPORT"
    source["cascade"]["detailed_replays"] = [
        {
            **_dossier("D-TRANSPORT", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID),
            "mechanism": "transport_delay",
        },
        {
            **_dossier("D-SHORTFALL", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID),
            "mechanism": "planned_delivery_shortfall",
        },
    ]
    source["actions"]["actions"] = [
        {
            **_dossier("D-TRANSPORT", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID),
            "mechanism": "transport_delay",
        },
        {
            **_dossier("D-SHORTFALL", subject.FOCUS_LANE_ID, subject.FOCUS_ITEM_ID),
            "mechanism": "planned_delivery_shortfall",
        },
    ]
    payload = subject._adapt_payload(source, _overlay())  # noqa: SLF001

    presentation = payload["presentation"]
    assert presentation["focus_detailed_replay_count"] == 2
    assert presentation["focus_dossier_ids"] == ["D-TRANSPORT", "D-SHORTFALL"]
    assert presentation["focus_action_count"] == 2
    assert "deux mécanismes restent séparés" in presentation["notice_fr"]
    document = subject.render_html(payload)
    assert "Aucun résultat n'est forcé" in document


def test_refused_action_is_attributed_to_its_signed_dossier() -> None:
    source = _base_payload()
    source["cascade"]["detailed_replays"] = [
        {
            **_dossier("D-OTHER", "lane-other", "099439"),
            "supplier_id": "supplier:42",
            "mechanism": "transport_delay",
        }
    ]
    source["actions"]["refusals"] = [
        {
            "dossier_id": "D-OTHER",
            "action_id": "unsupported",
            "label_fr": "Action non ciblable",
            "reason": "périmètre physique absent",
            "simulated": False,
        }
    ]
    payload = subject._adapt_payload(source, _overlay())  # noqa: SLF001

    refusal = payload["actions"]["refusals"][0]
    assert refusal["dossier_id"] == "D-OTHER"
    assert refusal["supplier_id"] == "supplier:42"
    assert refusal["item_id"] == "099439"
    assert refusal["mechanism"] == "transport_delay"
    document = subject.render_html(payload)
    assert "Dossier ${esc(r.dossier_id)}" in document
    assert "${esc(r.supplier_id)} · article ${esc(r.item_id)}" in document


def test_refused_action_without_signed_dossier_identity_is_rejected() -> None:
    source = _base_payload()
    source["actions"]["refusals"] = [
        {
            "dossier_id": "D-UNKNOWN",
            "action_id": "unsupported",
            "label_fr": "Action non ciblable",
            "reason": "périmètre physique absent",
            "simulated": False,
        }
    ]
    with pytest.raises(subject.Stage2DeliveryError, match="pas rattachable"):
        subject._adapt_payload(source, _overlay())  # noqa: SLF001


def test_html_exposes_native_window_and_focus_scope_without_v4_language() -> None:
    payload = subject._adapt_payload(_base_payload(), _overlay())  # noqa: SLF001
    document = subject.render_html(payload)

    assert document.count('class="view') == 3
    assert "première fenêtre de 42 jours" in document
    assert "à partir de J180" in document
    assert "flux normalement livrable" in document
    assert "inférieur ou égal à 1,5" in document
    assert "ni la pire période" in document
    assert "ni une saison moyenne" in document
    assert "ni une fréquence ou une probabilité" in document
    assert "Les règles 30/30 et 24/30 ne répondent pas à la même question" in document
    assert "24 effets appariés" in document
    assert "elle ne sélectionne pas la fenêtre" in document
    assert payload["presentation"]["notice_fr"] in document
    folded = document.casefold()
    visible = document.split("<script>", 1)[0]
    assert "V7" not in visible
    assert "V8 V3" not in visible
    assert "30 simulations indépendantes" in visible
    assert "traçabilité détaillée des lots" in document
    assert "design_seed" not in folded
    assert "graine de conception" not in folded
    assert "fenêtre de forte exposition" not in folded
    assert "quantité planifiée médiane" not in folded


def test_manifest_carries_focus_window_and_operational_limits(tmp_path: Path) -> None:
    payload = subject._adapt_payload(_base_payload(), _overlay())  # noqa: SLF001
    document = subject.render_html(payload)
    paths = SimpleNamespace(final_html=tmp_path / "v3.html")
    manifest = subject._manifest_payload(paths, payload, [], document)  # noqa: SLF001
    contract = manifest["scientific_contract"]

    assert contract["native_v8_registry_reader"] is True
    assert contract["obsolete_v4_seed_projection_used"] is False
    assert contract["focus_has_detailed_replay"] is False
    assert contract["focus_has_action"] is False
    assert contract["multiple_incidents_combined"] is False
    assert contract["full_dynamic_cascade_claimed"] is False
    assert contract["action_lot_trace_available"] is False
    assert contract["days_recovered_cost_or_roi_claimed"] is False
    assert contract["window_is_worst_period"] is False
    assert contract["window_is_average_season"] is False


def test_reducer_binding_uses_v3_contract_and_native_reader(tmp_path: Path) -> None:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline_v7,
    )
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v8_stage3_pipeline as pipeline_v3,
    )

    original_contract = pipeline_v7._contract_payload  # noqa: SLF001
    original_dashboard = subject.delivery_v7.dashboard_v7
    paths = SimpleNamespace(campaign_root=tmp_path)
    with subject._v3_reducer_binding(paths):  # noqa: SLF001
        assert pipeline_v7._contract_payload is pipeline_v3._contract_payload_v3  # noqa: SLF001
        assert isinstance(
            subject.delivery_v7.dashboard_v7,
            subject.dashboard_v8.NativeV8DashboardReader,
        )
    assert pipeline_v7._contract_payload is original_contract  # noqa: SLF001
    assert subject.delivery_v7.dashboard_v7 is original_dashboard
