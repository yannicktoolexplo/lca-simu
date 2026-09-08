from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_cross_state_business_readout as readout,
)


STATES = ("op_100", "op_93", "op_80")
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")


def _campaign() -> dict:
    services = {
        "op_100": (99.2, 99.3, 99.1, 0.0, 0.0),
        "op_93": (93.1, 94.0, 92.2, 8.3, 80.6),
        "op_80": (80.2, 81.8, 78.6, 17.0, 96.6),
    }
    states = []
    for state, (global_value, pf091, pf967, offset091, offset967) in services.items():
        states.append(
            {
                "id": state,
                "label": f"État {state}",
                "targetServicePct": float(state.removeprefix("op_")),
                "globalServicePct": global_value,
                "pf091ServicePct": pf091,
                "pf967ServicePct": pf967,
                "globalCiLowPct": global_value - 0.4,
                "globalCiHighPct": global_value + 0.4,
                "degradationFamily": "balanced_product_supplier_planned_lead",
                "degradationUnit": "jour",
                "offsetDays268091": offset091,
                "offsetDays268967": offset967,
            }
        )
    return {
        "states": states,
        "supplierCount": 2,
        "matrix": {
            "baselineRows": 90,
            "incidentRows": 3240,
            "totalRows": 3330,
            "states": 3,
            "lanes": 18,
            "mechanisms": 2,
            "repetitionsPerCombination": 30,
        },
    }


def _campaign_validation() -> dict:
    return {
        "schema_version": readout.delivery_v4.campaign_dashboard.FINALIZER_SCHEMA_VERSION,
        "status": "complete_validated",
        "campaign_signature": "a" * 64,
        "historical_incident_probability_estimated": False,
        "industrial_supplier_criticality_claimed": False,
        "expected_contract": {
            "operating_point_count": 3,
            "operating_point_degradation_family": (
                "balanced_product_supplier_planned_lead"
            ),
            "operating_point_degradation_scope": (
                "planned_supplier_lead_offsets_by_finished_product_feed"
            ),
            "lane_count": 18,
            "mechanisms": list(MECHANISMS),
            "paired_repetition_count": 30,
            "baseline_row_count": 90,
            "incident_row_count": 3240,
            "supplier_disruption_window_days": 42,
            "business_window_days": 360,
            "lot_replay_dossier_maximum": 3,
            "lot_replay_forced_top3": False,
            "quality_branch_included": False,
            "availability_incident_included": False,
            "all_lots_traced_claimed": False,
        },
        "comparability_checks": {
            key: True
            for key in {
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
        },
        "statistics": {
            "primary_ranking_metric": "impact_service_loss_fed_product_pp",
            "primary_window": "fixed_360_day_business_envelope",
            "confidence_interval": (
                "paired non-parametric bootstrap percentile interval"
            ),
            "bootstrap_replicates": 10_000,
            "bootstrap_pairing": (
                "one common paired-seed resample for every campaign cell"
            ),
            "effect_detection": (
                "CI95 lower bound > 0 and at least 24 of 30 paired effects > 0"
            ),
            "supplier_aggregation": (
                "maximum tested lane, labelled voie la plus exposée"
            ),
            "robust_priority": (
                "P(bootstrap rank_max <= 3) >= 0.80 after effect detection"
            ),
            "dossier_to_investigate": (
                "P(bootstrap rank_min <= 3) >= 0.20 after effect detection; "
                "descriptive review signal, not a forced top-three label"
            ),
            "forced_top3": False,
        },
    }


def _priority_row(
    *, state: str, mechanism: str, supplier: str, lane: str, status: str, mean: float
) -> dict[str, object]:
    detected = status in readout.SIGNAL_STATUSES
    return {
        "operating_point_id": state,
        "mechanism": mechanism,
        "supplier_id": supplier,
        "exposed_lane_id": lane,
        "item_id": "item:338929" if supplier == "SUP-A" else "item:344135",
        "dst_node_id": "M-1810" if supplier == "SUP-A" else "M-1430",
        "target_product_id": "item:268091" if supplier == "SUP-A" else "item:268967",
        "paired_repetition_count": 30,
        "physical_exercise_rate": 0.9,
        "priority_status": status,
        "model_effect_detected": detected,
        "horizon_dependent": False,
        "position": 1 if supplier == "SUP-A" else 2,
        "rank_min": 1 if supplier == "SUP-A" else 2,
        "rank_max": 2,
        "rank_median": 1.5 if supplier == "SUP-A" else 2.0,
        "bootstrap_rank_ci95_low": 1,
        "bootstrap_rank_ci95_high": 2,
        "bootstrap_top3_inclusion_probability": 0.96 if detected else 0.05,
        "bootstrap_unambiguous_top3_probability": 0.88
        if status == "robust_priority"
        else 0.02,
        "impact_service_loss_fed_product_pp_mean": mean,
        "impact_service_loss_fed_product_pp_median": mean,
        "impact_service_loss_fed_product_pp_p10": mean - 0.5,
        "impact_service_loss_fed_product_pp_p90": mean + 0.5,
        "impact_service_loss_fed_product_pp_ci95_low": mean - 0.2,
        "impact_service_loss_fed_product_pp_ci95_high": mean + 0.2,
        "impact_service_loss_fed_product_pp_positive_effect_rate": 0.9
        if detected
        else 0.1,
        "impact_service_loss_fed_product_pp_positive_effect_count": 27
        if detected
        else 3,
    }


def _priorities() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for state_index, state in enumerate(STATES):
        rows.append(
            _priority_row(
                state=state,
                mechanism="transport_delay",
                supplier="SUP-A",
                lane="L01",
                status="robust_priority",
                mean=5.0 + state_index,
            )
        )
        rows.append(
            _priority_row(
                state=state,
                mechanism="transport_delay",
                supplier="SUP-B",
                lane="L02",
                status="dossier_to_investigate"
                if state == "op_80"
                else "no_detected_effect",
                mean=1.0 + state_index,
            )
        )
        rows.append(
            _priority_row(
                state=state,
                mechanism="planned_delivery_shortfall",
                supplier="SUP-A",
                lane="L01",
                status="no_detected_effect",
                mean=0.5,
            )
        )
        rows.append(
            _priority_row(
                state=state,
                mechanism="planned_delivery_shortfall",
                supplier="SUP-B",
                lane="L02",
                status="dossier_to_investigate",
                mean=3.0 + state_index,
            )
        )
    return rows


def _stability_row(
    *, mechanism: str, supplier: str, priority_count: int, robust_count: int
) -> dict[str, object]:
    all_priority = priority_count == 3
    return {
        "mechanism": mechanism,
        "supplier_id": supplier,
        "state_comparison_valid": True,
        "same_exposed_lane_across_states": True,
        "same_target_product_for_exposed_lane_across_states": True,
        "priority_state_count": priority_count,
        "robust_priority_state_count": robust_count,
        "priority_in_all_three_states": all_priority,
        "robust_priority_in_all_three_states": robust_count == 3,
        "comparison_lane_id": "L01" if supplier == "SUP-A" else "L02",
        "target_product_id_for_comparison_lane": "268091"
        if supplier == "SUP-A"
        else "268967",
        "comparable_seed_count": 27,
        "required_comparable_seed_count": 24,
        "horizon_dependent": False,
    }


def _stability() -> list[dict[str, object]]:
    return [
        _stability_row(
            mechanism="transport_delay",
            supplier="SUP-A",
            priority_count=3,
            robust_count=3,
        ),
        _stability_row(
            mechanism="transport_delay",
            supplier="SUP-B",
            priority_count=1,
            robust_count=0,
        ),
        _stability_row(
            mechanism="planned_delivery_shortfall",
            supplier="SUP-A",
            priority_count=0,
            robust_count=0,
        ),
        _stability_row(
            mechanism="planned_delivery_shortfall",
            supplier="SUP-B",
            priority_count=3,
            robust_count=0,
        ),
    ]


def _qualification() -> dict:
    lanes = []
    for index in range(1, 19):
        lane = f"L{index:02d}"
        lanes.append(
            {
                "lane_id": lane,
                "supplier_id": "SUP-A" if index == 1 else "SUP-B",
                "item_id": "item:338929" if index == 1 else "item:344135",
                "dst_node_id": "M-1810" if index == 1 else "M-1430",
                "target_product_id": ("item:268091" if index == 1 else "item:268967"),
                "proof_level": "complete" if index == 1 else "partial",
                "display_label_fr": (
                    "Trace native complète jusqu'au client agrégé — hors preuve de réponse MRP"
                    if index == 1
                    else "Exposition fournisseur exercée — sans rejeu généalogique détaillé"
                ),
                "mrp_requirement_mode": "dynamic_explicit"
                if index <= 2
                else "static_explicit",
                "selected_dossier_ids": ["D01"] if index == 1 else [],
                "full_dynamic_stock_mrp_production_service_cascade_proven": False,
                "complete_cascade_label_allowed": False,
            }
        )
    return {
        "counts": {
            "dynamic_mrp_lane_count": 2,
            "static_mrp_lane_count": 16,
            "full_dynamic_cascade_proven_count": 0,
        },
        "lanes": lanes,
        "dossiers": [
            {
                "dossier_id": "D01",
                "operating_point_id": "op_80",
                "mechanism": "transport_delay",
                "lane_id": "L01",
                "proof_level": "complete",
                "display_label_fr": "Trace native complète — réponse MRP non tracée",
                "mrp_requirement_mode": "dynamic_explicit",
                "missing_native_trace_stages": [],
                "trace_counts": {
                    "shipments": 2,
                    "material_receipts": 2,
                    "consumptions": 3,
                    "campaigns": 1,
                    "batches": 1,
                    "finished_lots": 2,
                    "client_events": 2,
                },
                "full_dynamic_stock_mrp_production_service_cascade_proven": False,
                "complete_cascade_label_allowed": False,
            }
        ],
    }


def _actions() -> dict:
    return {
        "status": "complete_validated",
        "message": "Comparaison appariée avec le même incident sans action.",
        "results": [
            {
                "dossierId": "D01",
                "state": "op_80",
                "supplier": "SUP-A",
                "lane": "L01",
                "item": "338929",
                "destination": "M-1810",
                "targetProduct": "268091",
                "mechanism": "transport_delay",
                "actionId": "future_departures_lead_reduction",
                "label": "Réduction contractuelle du délai des futurs départs",
                "parameters": {"lead_time_adjustment_days": -14},
                "physicalScope": {"supplier_id": "SUP-A"},
                "status": "estimated_on_physically_exercised_seeds",
                "pairedCount": 30,
                "exercisedCount": 26,
                "nonExercisedCount": 4,
                "gains": [
                    {
                        "label": "Service récupéré sur 360 jours",
                        "unit": "point",
                        "count": 26,
                        "mean": 1.2,
                        "p10": 0.2,
                        "p90": 2.3,
                    }
                ],
                "limits": "Action sur les futurs départs, pas sur un shipment_id en transit.",
            }
        ],
        "refusals": [
            {
                "dossierId": "D01",
                "actionId": "targeted_closed_loop_regulation",
                "label": "Régulation ciblée",
                "reason": "Observation de voie absente.",
                "limits": "Action non simulée.",
            }
        ],
    }


def _payload() -> dict:
    return readout.build_business_payload(
        campaign=_campaign(),
        priority_rows=_priorities(),
        stability_rows=_stability(),
        qualification=_qualification(),
        actions=_actions(),
        generated_at_utc="2026-09-05T12:00:00+00:00",
    )


def test_answers_cross_state_question_without_forcing_top_three() -> None:
    payload = _payload()
    summaries = {row["id"]: row for row in payload["campaign"]["mechanisms"]}
    groups = {
        (row["mechanism"], row["supplier"]): row
        for row in payload["campaign"]["suppliers"]
    }

    assert payload["campaign"]["top3Forced"] is False
    assert payload["campaign"]["bootstrapIsPhysicalSimulation"] is False
    assert summaries["transport_delay"]["stableSuppliers"] == ["SUP-A"]
    assert summaries["planned_delivery_shortfall"]["stableSuppliers"] == ["SUP-B"]
    assert groups[("transport_delay", "SUP-A")]["classification"] == (
        "priorite_robuste_dans_les_3_etats"
    )
    assert groups[("transport_delay", "SUP-B")]["classification"] == (
        "priorite_dependante_de_l_etat"
    )
    assert (
        groups[("transport_delay", "SUP-A")]["states"]["op_80"]["physicalEvidence"][
            "mrpRequirementMode"
        ]
        == "dynamic_explicit"
    )
    assert (
        groups[("transport_delay", "SUP-A")]["states"]["op_80"]["physicalEvidence"][
            "detailedLotReplayAvailable"
        ]
        is True
    )
    assert (
        groups[("transport_delay", "SUP-A")]["states"]["op_100"]["physicalEvidence"][
            "detailedLotReplayAvailable"
        ]
        is False
    )
    assert (
        groups[("planned_delivery_shortfall", "SUP-A")]["states"]["op_80"][
            "physicalEvidence"
        ]["selectedDossierIds"]
        == []
    )


def test_keeps_product_services_rank_uncertainty_and_action_parameters() -> None:
    payload = _payload()
    state_80 = next(
        row for row in payload["campaign"]["states"] if row["id"] == "op_80"
    )
    supplier = next(
        row
        for row in payload["campaign"]["suppliers"]
        if row["mechanism"] == "transport_delay" and row["supplier"] == "SUP-A"
    )
    action = payload["actions"]["results"][0]

    assert state_80["service268091Pct"] == 81.8
    assert state_80["service268967Pct"] == 78.6
    assert supplier["states"]["op_100"]["impact"]["ci95Low"] == 4.8
    assert supplier["states"]["op_100"]["impact"]["p10"] == 4.5
    assert supplier["states"]["op_100"]["impact"]["p90"] == 5.5
    assert supplier["states"]["op_100"]["impact"]["positiveEffectRate"] == 0.9
    assert supplier["states"]["op_100"]["rank"]["top3InclusionProbability"] == 0.96
    assert supplier["states"]["op_100"]["rank"]["unambiguousTop3Probability"] == 0.88
    assert action["parameters"] == {"lead_time_adjustment_days": -14}
    assert "shipment_id" in action["limits"]
    assert payload["actions"]["closedLoopClaimed"] is False
    assert payload["actions"]["completeCostValidated"] is False


def test_renders_and_validates_additive_three_view_package(tmp_path: Path) -> None:
    payload = _payload()
    document = readout.render_html(payload)
    output = tmp_path / "new_readout"

    assert document.count('class="view') == 3
    assert "aucun top 3 forcé" in document
    assert "10 000 rééchantillonnages" in document
    assert "boucle ouverte" in document
    assert "http://" not in document.casefold()
    assert "https://" not in document.casefold()
    assert "<script src=" not in document.casefold()
    assert "<link " not in document.casefold()

    receipt = readout.write_delivery(
        output_dir=output,
        payload=payload,
        source_bindings={"fixture": {"sha256": "0" * 64}},
    )
    assert receipt["valid"] is True
    assert receipt["supplier_mechanism_row_count"] == 4
    assert Path(receipt["html"]).is_file()
    assert readout.validate_delivery(output)["view_count"] == 3
    with pytest.raises(FileExistsError):
        readout.write_delivery(
            output_dir=output,
            payload=payload,
            source_bindings={},
        )


def test_rejects_incomplete_three_state_matrix() -> None:
    priorities = _priorities()
    priorities.pop()
    with pytest.raises(readout.CrossStateReadoutError, match="trois états"):
        readout.build_business_payload(
            campaign=_campaign(),
            priority_rows=priorities,
            stability_rows=_stability(),
            qualification=_qualification(),
            actions=_actions(),
        )


def test_non_comparable_signal_is_not_called_state_dependent() -> None:
    stability = _stability()
    row = next(
        item
        for item in stability
        if item["mechanism"] == "transport_delay" and item["supplier_id"] == "SUP-B"
    )
    row["state_comparison_valid"] = False
    payload = readout.build_business_payload(
        campaign=_campaign(),
        priority_rows=_priorities(),
        stability_rows=stability,
        qualification=_qualification(),
        actions=_actions(),
    )
    supplier = next(
        item
        for item in payload["campaign"]["suppliers"]
        if item["mechanism"] == "transport_delay" and item["supplier"] == "SUP-B"
    )
    assert supplier["classification"] == "signal_inter_etats_non_comparable"
    mechanism = next(
        item
        for item in payload["campaign"]["mechanisms"]
        if item["id"] == "transport_delay"
    )
    assert mechanism["stateSpecificSupplierCount"] == 0
    assert mechanism["nonComparableSupplierCount"] == 1


def test_validates_the_official_statistical_contract_and_rejects_forced_top3() -> None:
    contract = readout._validate_campaign_contract(_campaign_validation())
    assert contract["bootstrap_replicates"] == 10_000
    assert contract["forced_top3"] is False

    altered = _campaign_validation()
    altered["expected_contract"]["lot_replay_forced_top3"] = True
    with pytest.raises(readout.CrossStateReadoutError, match="campagne officiel"):
        readout._validate_campaign_contract(altered)

    altered = _campaign_validation()
    altered["statistics"]["bootstrap_replicates"] = 1_000
    with pytest.raises(readout.CrossStateReadoutError, match="statistique officiel"):
        readout._validate_campaign_contract(altered)


def test_rejects_output_nested_in_an_official_source(tmp_path: Path) -> None:
    source = tmp_path / "campaign"
    source.mkdir()
    with pytest.raises(readout.CrossStateReadoutError, match="séparé"):
        readout._validate_output_separation(
            output_dir=source / "new_readout",
            source_paths=(source,),
        )


def test_windows_runbook_uses_quoted_variables_instead_of_angle_placeholders() -> None:
    runbook = (
        Path(readout.__file__).with_name(
            "RUNBOOK_SUPPLIER_V6_CROSS_STATE_BUSINESS_READOUT.md"
        )
    ).read_text(encoding="utf-8")
    assert "$campaignRoot = 'C:\\chemin\\vers\\campagne-v6'" in runbook
    assert "--campaign-root $campaignRoot" in runbook
    assert "<racine-campagne-v6>" not in runbook
