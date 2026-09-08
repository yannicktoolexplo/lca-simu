from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_extension_interpretation_audit as extension_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_priority_boundary_audit as boundary_contract,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_risk_results_dashboard as dashboard,
)


SUPPLIERS = tuple(f"SUP-{index:02d}" for index in range(16))
LANE_SUPPLIERS = (*SUPPLIERS, SUPPLIERS[0], SUPPLIERS[1])
SEEDS = tuple(range(1001, 1031))
PLAN_SIGNATURE = "signed-plan-v1"
RUNNER_SIGNATURE = "signed-runner-v1"
CAMPAIGN_SIGNATURE = "signed-network-campaign-v1"


@pytest.fixture(autouse=True)
def _isolate_dashboard_contract_consumption(monkeypatch: pytest.MonkeyPatch) -> None:
    """The producer contracts have their own exhaustive package-validation tests."""

    def validate_overlay(root: str | Path) -> dict[str, object]:
        directory = Path(root)
        manifest = json.loads(
            (directory / "scientific_overlay_manifest.json").read_text(encoding="utf-8")
        )
        hashes = dict(manifest["artifact_file_sha256"])
        observed = {path.name for path in directory.iterdir() if path.is_file()}
        if observed != set(hashes) | {"scientific_overlay_manifest.json"}:
            raise ValueError("Inventaire disque de la surcouche invalide")
        for name, expected in hashes.items():
            if dashboard._sha256(directory / name) != expected:
                raise ValueError(f"Empreinte de surcouche invalide: {name}")
        for name in (
            "temporal_robustness_manifest.json",
            "priority_four_business_causes_manifest.json",
            "multi_lane_supplier_common_cause_manifest.json",
        ):
            payload = json.loads((directory / name).read_text(encoding="utf-8"))
            if payload.get("release_gate_pass") is not False:
                raise ValueError("Alias release_gate_pass non neutralise")
        return {"status": "complete"}

    def validate_boundary(root: str | Path) -> dict[str, object]:
        directory = Path(root)
        manifest = json.loads(
            (directory / "priority_boundary_audit_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        for name, expected in dict(manifest["artifact_file_sha256"]).items():
            if dashboard._sha256(directory / name) != expected:
                raise ValueError(f"Empreinte invalide: {name}")
        return {"status": "complete"}

    monkeypatch.setattr(
        extension_contract,
        "validate_scientific_overlay",
        validate_overlay,
    )
    monkeypatch.setattr(
        boundary_contract,
        "validate_audit_package",
        validate_boundary,
    )


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    if not rows:
        raise AssertionError(f"Fixture CSV vide interdite: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _metric_value(metric_key: str, supplier_index: int) -> float:
    adverse = max(0.0, 0.40 - supplier_index * 0.025)
    if metric_key in {
        "horizon_on_due_service_delta",
        "worst_rolling_28d_on_due_delta",
    }:
        return -adverse
    if metric_key == "incremental_backlog_days_per_requested_unit":
        return adverse * 8.0
    return adverse


def _priority_lineage() -> dict[str, object]:
    return {
        "follow_up_supplier_ids": list(SUPPLIERS[:4]),
        "follow_up_chain_ids": [f"chain_{index:02d}" for index in range(1, 5)],
        "follow_up_group_is_unordered": True,
        "slot_order_has_scientific_meaning": False,
        "service_nonseparation_group_fully_followed_up": True,
    }


def _write_extension_audit(overlay: Path) -> str:
    temporal_rows: list[dict[str, object]] = []
    cause_rows: list[dict[str, object]] = []
    extension_metrics = tuple(extension_contract.METRIC_BY_KEY)
    for window_index, start, end in extension_contract.CALENDAR_WINDOWS:
        for priority_index in range(
            1, extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT + 1
        ):
            for metric_index, metric_key in enumerate(extension_metrics):
                mean = (
                    -0.02 * priority_index
                    if metric_key == "horizon_on_due_service_delta"
                    else 0.02 * priority_index
                )
                temporal_rows.append(
                    {
                        "extension": "temporal_robustness",
                        "context_kind": "temporal",
                        "window_index": window_index,
                        "stress_start_day": start,
                        "stress_end_day": end,
                        "failure_mode": "transport_delay",
                        "mathematical_family": "date_shift",
                        "mechanism_value": 120,
                        "mechanism_unit": "jours_ajoutes",
                        "selection_slot": priority_index,
                        "chain_id": f"chain_{priority_index:02d}",
                        "supplier_id": SUPPLIERS[priority_index - 1],
                        "item_id": f"item:{priority_index:06d}",
                        "dst_node_id": "M-1810",
                        "product_id": "268091",
                        "metric": metric_key,
                        "metric_label": extension_contract.METRIC_BY_KEY[
                            metric_key
                        ].label,
                        "metric_unit": extension_contract.METRIC_BY_KEY[
                            metric_key
                        ].unit,
                        "paired_seed_count": 30,
                        "effect_mean": mean,
                        "effect_ci95_low": mean - 0.001,
                        "effect_ci95_high": mean + 0.001,
                        "effect_class": "adverse",
                        "conditional_client_effect_seed_count": 30 - metric_index,
                        "conditional_production_effect_seed_count": 28,
                        "count_denominator": 30,
                        "count_is_probability_or_frequency": False,
                        "historical_occurrence_probability_estimated": False,
                    }
                )
    for cause_index, failure_mode in enumerate(extension_contract.FOUR_CAUSES):
        for priority_index in range(
            1, extension_contract.EXPECTED_FOLLOW_UP_LANE_COUNT + 1
        ):
            for metric_index, metric_key in enumerate(extension_metrics):
                mean = (
                    -0.01 * (cause_index + priority_index)
                    if metric_key == "horizon_on_due_service_delta"
                    else 0.01 * (cause_index + priority_index)
                )
                cause_rows.append(
                    {
                        "extension": "priority_four_business_causes",
                        "context_kind": "four_cause",
                        "window_index": "",
                        "stress_start_day": 45,
                        "stress_end_day": 224,
                        "failure_mode": failure_mode,
                        "mathematical_family": extension_contract.CAUSE_FAMILY[
                            failure_mode
                        ],
                        "mechanism_value": extension_contract.SEVERE_CAUSE[
                            failure_mode
                        ][0],
                        "mechanism_unit": extension_contract.SEVERE_CAUSE[failure_mode][
                            1
                        ],
                        "selection_slot": priority_index,
                        "chain_id": f"chain_{priority_index:02d}",
                        "supplier_id": SUPPLIERS[priority_index - 1],
                        "item_id": f"item:{priority_index:06d}",
                        "dst_node_id": "M-1810",
                        "product_id": "268091",
                        "metric": metric_key,
                        "metric_label": extension_contract.METRIC_BY_KEY[
                            metric_key
                        ].label,
                        "metric_unit": extension_contract.METRIC_BY_KEY[
                            metric_key
                        ].unit,
                        "paired_seed_count": 30,
                        "effect_mean": mean,
                        "effect_ci95_low": mean - 0.001,
                        "effect_ci95_high": mean + 0.001,
                        "effect_class": "adverse",
                        "conditional_client_effect_seed_count": 29,
                        "conditional_production_effect_seed_count": 27 - metric_index,
                        "count_denominator": 30,
                        "count_is_probability_or_frequency": False,
                        "historical_occurrence_probability_estimated": False,
                    }
                )
    _csv(overlay / "temporal_effect_by_lane_window.csv", temporal_rows)
    _csv(
        overlay / "temporal_pairwise_difference_audit.csv",
        [
            {"pair_id": f"temporal-{index:02d}", "paired_seed_count": 30}
            for index in range(72)
        ],
    )
    _csv(overlay / "four_cause_effect_by_lane_cause.csv", cause_rows)
    _csv(
        overlay / "four_cause_pairwise_difference_audit.csv",
        [
            {"pair_id": f"cause-{index:02d}", "paired_seed_count": 30}
            for index in range(72)
        ],
    )
    _csv(
        overlay / "common_cause_effect_by_supplier_cause.csv",
        [
            {
                "supplier_id": supplier,
                "failure_mode": failure_mode,
                "paired_seed_count": 30,
            }
            for supplier in SUPPLIERS[:2]
            for failure_mode in extension_contract.FOUR_CAUSES
        ],
    )
    controls: dict[str, object] = {
        "schema_version": extension_contract.SCHEMA_VERSION,
        "status": "scientific_controls_complete",
        "priority_selection_lineage": _priority_lineage(),
        "follow_up_group_supplier_count": 4,
        "follow_up_group_is_unordered": True,
        "slot_order_has_scientific_meaning": False,
        "execution_integrity_pass": True,
        "multi_lane_common_cause_execution_integrity_pass": True,
        "temporal_execution_integrity_pass": True,
        "global_priority_temporal_robustness_evaluable": False,
        "four_cause_execution_integrity_pass": True,
        "global_four_cause_priority_robustness_evaluable": False,
        "causal_lot_execution_integrity_pass": True,
        "causal_lot_pairing_integrity_pass": False,
        "causal_lot_attribution_available": False,
        "causal_genealogy_quantity_status": "upper_bound_only",
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "network_recovery_metric_used_in_any_gate_or_ranking": False,
        "legacy_completion_or_flow_alias_accepted_as_robustness": False,
        "legacy_aliases_neutralized_in_scientific_controls": True,
        "global_network_priority_robustness_evaluable": False,
        "promotion_allowed": False,
        "industrial_criticality_claimed": False,
        "historical_supplier_probability_estimated": False,
    }
    _json(overlay / "scientific_promotion_controls.json", controls)
    interpretation = {
        "follow_up_lane_count": 4,
        "network_lane_count": 18,
        "follow_up_group_status": "complete_nonseparated_service_group_nonordered",
        "service_nonseparation_group_fully_followed_up": True,
        "follow_up_group_order_evaluable": False,
        "scientific_order_claimed": False,
        "slot_order_has_scientific_meaning": False,
        "within_lane_context_difference_detected": True,
        "global_network_priority_robustness_evaluable": False,
        "global_reason": "only_4_follow_up_lanes_tested_out_of_18_active_network_lanes",
        "no_universal_supplier_or_lane_priority_claimed": True,
    }
    causal = {
        "causal_lot_execution_integrity_pass": True,
        "causal_lot_pairing_integrity_pass": False,
        "causal_lot_attribution_available": False,
        "genealogical_exposure_is_upper_bound": True,
    }
    audit_payload: dict[str, object] = {
        "schema_version": extension_contract.SCHEMA_VERSION,
        "status": "complete",
        "source_runner_signature": RUNNER_SIGNATURE,
        "source_plan_signature": PLAN_SIGNATURE,
        "priority_selection_lineage": _priority_lineage(),
        "bootstrap": {
            "paired_seed_count": 30,
            "resample_count": extension_contract.BOOTSTRAP_RESAMPLE_COUNT,
        },
        "temporal_interpretation": interpretation,
        "four_business_cause_interpretation": interpretation,
        "causal_lot_interpretation": causal,
        "scientific_promotion_controls": controls,
        "no_opaque_composite_score": True,
        "network_recovery_metric": {
            "status": "excluded_invalid_common_window",
            "used_in_any_gate_or_ranking": False,
        },
    }
    _json(
        overlay / "scientific_extension_interpretation_audit.json",
        audit_payload,
    )
    artifact_hashes = {
        name: dashboard._sha256(overlay / name)
        for name in extension_contract.OUTPUT_FILES
    }
    signature_payload: dict[str, object] = {
        "schema_version": extension_contract.MANIFEST_SCHEMA_VERSION,
        "builder_sha256": dashboard.EXPECTED_EXTENSION_BUILDER_SHA256,
        "source_file_sha256": {"fixture": "signed-source"},
        "ledger_case_registry_sha256": "signed-ledger",
        "artifact_file_sha256": artifact_hashes,
        "bootstrap_resample_count": extension_contract.BOOTSTRAP_RESAMPLE_COUNT,
    }
    package_signature = extension_contract._canonical_sha256(signature_payload)
    _json(
        overlay / "extension_interpretation_audit_manifest.json",
        {
            **signature_payload,
            "status": "complete",
            "package_signature": package_signature,
            "promotion_allowed": False,
            "global_network_priority_robustness_evaluable": False,
        },
    )
    return package_signature


def _neutralized_extension_manifest(
    extension: str, *, causal: bool = False
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "etudecas.supplier_network_post_priority_extension_runner.v1",
        "extension": extension,
        "status": "complete",
        "mode": "full",
        "release_gate_pass": False,
        "legacy_runner_release_gate_value": True,
        "release_gate_semantics": "completion_and_flow_only_not_scientific_robustness",
        "scientific_execution_integrity_pass": True,
        "main_ranking_mutated": False,
        "industrial_probability_estimated": False,
        "runner_signature": RUNNER_SIGNATURE,
        "plan_signature": PLAN_SIGNATURE,
    }
    if causal:
        payload.update(
            {
                "logical_pair_count": 4,
                "evaluated_pair_count": 4,
                "unique_matched_technical_key_count": 4,
                "all_root_gates_pass": True,
                "all_genealogy_integrity_gates_pass": True,
                "all_pairs_counterfactually_evaluated": False,
                "genealogical_exposure_is_upper_bound": True,
                "quality_hold_quarantine_is_reconstructed_not_native": True,
                "causal_lot_attribution_available": False,
            }
        )
    return payload


def _resign_overlay(overlay: Path, audit_signature: str) -> None:
    manifest_path = overlay / "scientific_overlay_manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()
    artifact_hashes = {
        path.name: dashboard._sha256(path)
        for path in sorted(overlay.iterdir())
        if path.is_file()
    }
    signature_payload: dict[str, object] = {
        "schema_version": extension_contract.OVERLAY_SCHEMA_VERSION,
        "builder_sha256": dashboard.EXPECTED_EXTENSION_BUILDER_SHA256,
        "source_consolidated_file_sha256": {"fixture": "signed-consolidated"},
        "source_audit_package_signature": audit_signature,
        "artifact_file_sha256": artifact_hashes,
    }
    _json(
        manifest_path,
        {
            **signature_payload,
            "status": "complete",
            "overlay_signature": extension_contract._canonical_sha256(
                signature_payload
            ),
            "promotion_allowed": False,
        },
    )


def _write_overlay(root: Path) -> Path:
    overlay = root / "overlay"
    overlay.mkdir(parents=True)
    campaign: dict[str, object] = {
        "status": "complete",
        "mode": "full",
        "campaign_signature": CAMPAIGN_SIGNATURE,
        "source_campaign_signature": CAMPAIGN_SIGNATURE,
        "days": 720,
        "confirmation_seed_count": 30,
        "distinct_supplier_count": 16,
        "active_lane_count": 18,
        "evidence_class": "conditional_simulation_hypothesis",
        "historical_occurrence_probability": "not_estimated",
        "supplier_ranking_meaning": (
            "conditional_model_sensitivity_priority_not_observed_criticality"
        ),
        "priority_set_stabilized": True,
        "rank3_rank4_interval_separated": True,
        "extension_runner_signature": RUNNER_SIGNATURE,
        "scientific_interpretation_overlay_applied": True,
        "legacy_runner_promotion_aliases_neutralized": True,
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "global_priority_temporal_robustness_evaluable": False,
        "global_four_cause_priority_robustness_evaluable": False,
        "global_network_priority_robustness_evaluable": False,
        "promotion_allowed": False,
        "extensions_required": {
            name: {
                "pass": False,
                "legacy_runner_release_gate_value": True,
                "pass_semantics": "neutralized_completion_or_flow_alias",
            }
            for name in (
                "multi_lane_supplier_common_cause",
                "temporal_robustness",
                "four_business_cause_confirmation",
                "priority_four_business_causes",
                "causal_lot_attribution",
            )
        },
    }
    _json(overlay / "campaign_manifest.json", campaign)
    ranking = [
        {
            "supplier_id": supplier,
            "supplier_sensitivity_rank": index + 1,
            "worst_item_id": f"item:{index:06d}",
            "worst_dst_node_id": "M-1810",
            "worst_target_product_id": "268091",
            "worst_failure_mode": "transport_delay",
            "worst_service_delta": -max(0.0, 0.40 - index * 0.025),
            "service_metric_unit": "ratio_and_percentage_points",
            "client_effect_scenario_count": 2,
            "evidence_stage": "confirmation_30_realisations",
        }
        for index, supplier in enumerate(SUPPLIERS)
    ]
    _csv(overlay / "supplier_sensitivity_ranking.csv", ranking)
    _csv(overlay / "confirmation_supplier_sensitivity_ranking.csv", ranking)
    _csv(
        overlay / "lane_sensitivity_ranking.csv",
        [
            {
                "chain_id": f"chain_{index:02d}",
                "lane_sensitivity_rank": index + 1,
                "supplier_id": supplier,
                "item_id": f"item:{338929 + index}",
                "dst_node_id": "M-1810" if index % 2 == 0 else "M-1430",
                "target_product_id": "268091" if index % 2 == 0 else "268967",
                "worst_failure_mode": "transport_delay",
                "worst_service_delta": -max(0.0, 0.40 - index * 0.02),
                "service_metric_unit": "ratio_and_percentage_points",
                "evidence_stage": "confirmation_30_realisations",
            }
            for index, supplier in enumerate(LANE_SUPPLIERS)
        ],
    )
    _csv(
        overlay / "failure_mode_sensitivity_summary.csv",
        [
            {
                "failure_mode": failure_mode,
                "failure_mode_sensitivity_rank": index + 1,
                "worst_service_delta": -0.1,
                "tested_lane_count": 18,
                "client_effect_scenario_count": 1,
                "evidence_stage": "screening_1_realisation",
            }
            for index, failure_mode in enumerate(dashboard.MECHANISMS)
        ],
    )
    for name, extension in (
        (
            "multi_lane_supplier_common_cause_manifest.json",
            "multi_lane_supplier_common_cause",
        ),
        ("temporal_robustness_manifest.json", "temporal_robustness"),
        (
            "priority_four_business_causes_manifest.json",
            "priority_four_business_causes",
        ),
    ):
        _json(overlay / name, _neutralized_extension_manifest(extension))
    _json(
        overlay / "causal_lot_attribution_manifest.json",
        _neutralized_extension_manifest("causal_lot_attribution", causal=True),
    )
    _json(
        overlay / "post_priority_extension_runner_manifest.json",
        {
            "status": "complete",
            "promotion_allowed": False,
            "legacy_promotion_allowed_value": True,
            "causal_lot_release_gate_pass": False,
            "legacy_causal_lot_release_gate_value": True,
            "extension_release_gates": {
                "multi_lane_supplier_common_cause": False,
                "temporal_robustness": False,
                "priority_four_business_causes": False,
            },
            "scientific_execution_integrity_pass": True,
            "global_network_priority_robustness_evaluable": False,
        },
    )
    exposure_rows: list[dict[str, object]] = []
    genealogy_detail_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    for index in range(4):
        case_id = f"causal-case-{index + 1}"
        case_key = f"causal-key-{index + 1}"
        descendant_count = 2 + index
        exposure_rows.append(
            {
                "case_key": case_key,
                "case_id": case_id,
                "seed": 1001,
                "failure_mode": "quality_hold",
                "root_lot_count": 1,
                "exposed_descendant_lot_count": descendant_count,
                "exposed_row_count": 1 + descendant_count,
                "missing_genealogy_lot_count": 0,
                "root_gate_pass": True,
                "genealogy_integrity_pass": True,
                "descendant_quantity_is_upper_bound": True,
                "causal_delay_or_loss_claimed_from_genealogy": False,
            }
        )
        for descendant_index in range(descendant_count + 1):
            is_root = descendant_index == 0
            genealogy_detail_rows.append(
                {
                    "extension": "causal_lot_attribution_subset",
                    "case_key": case_key,
                    "case_id": case_id,
                    "seed": 1001,
                    "failure_mode": "quality_hold",
                    "stress_start_day": 45,
                    "stress_end_day": 224,
                    "chain_ids": f"chain_{index + 1:02d}",
                    "supplier_ids": SUPPLIERS[index],
                    "lot_id": (
                        f"LOT-ROOT-{index + 1:02d}"
                        if is_root
                        else f"LOT-DESC-{index + 1:02d}-{descendant_index:02d}"
                    ),
                    "exposure_role": (
                        "risk_tagged_usable_receipt_root"
                        if is_root
                        else "genealogical_descendant"
                    ),
                    "genealogy_depth": "" if is_root else descendant_index,
                    "node_id": "M-1810" if is_root else "DC-1920",
                    "item_id": "item:338929" if is_root else "item:268091",
                    "event_id": f"LEVT-{index + 1:02d}-{descendant_index:02d}",
                    "event_type": "lane_receipt" if is_root else "production_output",
                    "day": 80 + descendant_index,
                    "qty": 100 + descendant_index,
                    "uom": "UN",
                    "risk_event_ids": "risk-1" if is_root else "",
                    "shipment_id": f"SHIP-{index + 1:02d}" if is_root else "",
                    "production_campaign_id": (
                        "" if is_root else f"CMP-{index + 1:02d}-{descendant_index:02d}"
                    ),
                    "source_type": "lane_receipt" if is_root else "production_output",
                    "source_id": "edge:test" if is_root else "M-1810|item:268091",
                    "descendant_quantity_is_exposure_upper_bound": True,
                    "causal_delay_or_loss_claimed": False,
                    "counterfactual_entity_identity_validated": False,
                    "industrial_lot_number_claimed": False,
                    "lot_identifier_semantics": (
                        "identifiant_technique_simule_pas_numero_lot_industriel"
                    ),
                }
            )
        pair_rows.append(
            {
                "case_id": case_id,
                "unique_matched_technical_key_count": 1,
                "actual_difference_row_count": 1,
                "root_gate_pass": True,
                "genealogy_integrity_pass": True,
                "paired_counterfactual_evaluated": False,
                "industrial_lot_number_claimed": False,
            }
        )
        detail_rows.append(
            {
                "case_id": case_id,
                "seed": 1001,
                "failure_mode": "quality_hold",
                "technical_key_type": "shipment",
                "technical_key_id": f"SHIP-338929-{index + 1:03d}",
                "node_id": "M-1810",
                "item_id": "item:338929",
                "event_type": "lane_receipt",
                "baseline_day": 80 + index,
                "stress_day": 92 + index,
                "day_delta": 12,
                "baseline_qty": 100,
                "stress_qty": 90,
                "qty_delta": -10,
                "uom": "UN",
                "actual_difference_measured": True,
                "pairing_input_sha256_pass": True,
                "pairing_j0_state_sha256_pass": True,
                "genealogical_exposure_only": False,
                "causal_scope": "technical_event_heuristic_not_causal_lot_identity",
            }
        )
    _csv(overlay / "lot_genealogical_exposure_summary.csv", exposure_rows)
    _csv(overlay / "lot_genealogical_exposure_detail.csv", genealogy_detail_rows)
    _csv(overlay / "causal_lot_attribution_summary.csv", pair_rows)
    _csv(overlay / "causal_lot_attribution_detail.csv", detail_rows)
    audit_signature = _write_extension_audit(overlay)
    _resign_overlay(overlay, audit_signature)
    return overlay


def _metric_audit(metric_key: str, *, released: bool) -> dict[str, object]:
    top = list(SUPPLIERS[:3])
    return {
        "metric_key": metric_key,
        "metric_label": boundary_contract.METRIC_BY_KEY[metric_key].label,
        "unit": boundary_contract.METRIC_BY_KEY[metric_key].unit,
        "direction": boundary_contract.METRIC_BY_KEY[metric_key].direction,
        "descriptive_first_three_supplier_ids": top,
        "rank3_supplier_id": SUPPLIERS[2],
        "rank4_supplier_id": SUPPLIERS[3],
        "top3_presence_seed_counts": {supplier: 30 for supplier in top},
        "metric_priority_set_release_pass": released,
        "released_priority_supplier_ids": top if released else [],
        "identifier_tie_break_used_as_scientific_evidence": False,
    }


def _write_boundary(root: Path, *, overlay: Path, envelope_released: bool) -> Path:
    boundary = root / "boundary"
    boundary.mkdir(parents=True)
    metric_audits = [
        _metric_audit(metric_key, released=envelope_released)
        for metric_key in BOUNDARY_METRIC_ORDER_FOR_TEST
    ]
    family_audits = {
        failure_mode: {
            "hypothesis_family": boundary_contract.HYPOTHESIS_FAMILY_BY_FAILURE_MODE[
                failure_mode
            ],
            "metric_priority_audits": [
                _metric_audit(metric_key, released=envelope_released)
                for metric_key in BOUNDARY_METRIC_ORDER_FOR_TEST
            ],
        }
        for failure_mode in sorted(boundary_contract.CONFIRMED_FAILURE_MODES)
    }
    audit_payload: dict[str, object] = {
        "schema_version": boundary_contract.SCHEMA_VERSION,
        "status": "complete",
        "source_campaign_signature": CAMPAIGN_SIGNATURE,
        "historical_occurrence_probability": "not_estimated",
        "industrial_supplier_criticality_claimed": False,
        "causal_fusion_performed_or_claimed": False,
        "supplier_wide_common_cause_included_in_ranking": False,
        "bootstrap": {
            "paired_seed_count": 30,
            "resample_count": boundary_contract.BOOTSTRAP_RESAMPLE_COUNT,
        },
        "common_random_numbers_provenance": {"registry_row_count": 1110},
        "metric_priority_audits": metric_audits,
        "failure_mode_specific_metric_priority_audits": family_audits,
        "service_priority_set_release_pass": envelope_released,
        "envelope_service_priority_set_release_pass": envelope_released,
        "envelope_service_priority_supplier_ids": (
            list(SUPPLIERS[:3]) if envelope_released else []
        ),
        "envelope_service_nonseparation_group_supplier_ids": list(SUPPLIERS[:4]),
        "universal_supplier_top3_release_pass": envelope_released,
        "universal_supplier_top3_ids": (
            list(SUPPLIERS[:3]) if envelope_released else []
        ),
        "priority_group_supplier_ids_if_no_universal_top3": (
            [] if envelope_released else list(SUPPLIERS)
        ),
        "raw_network_recovery_metric": {
            "status": "excluded_invalid_common_J45_J224_for_lane_specific_windows",
            "used_in_any_ranking_or_gate": False,
        },
        "no_opaque_composite_score": True,
    }
    _json(boundary / "scientific_priority_boundary_audit.json", audit_payload)
    ranking_rows: list[dict[str, object]] = []
    for scope, failure_mode in (
        (boundary_contract.SUPPLIER_ENVELOPE_SCOPE, ""),
        ("failure_mode_specific", "transport_delay"),
        ("failure_mode_specific", "supply_availability"),
    ):
        for metric_key in BOUNDARY_METRIC_ORDER_FOR_TEST:
            for index, supplier in enumerate(SUPPLIERS):
                ranking_rows.append(
                    {
                        "aggregation_scope": scope,
                        "failure_mode": failure_mode,
                        "hypothesis_family": (
                            "worst_single_lane_scenario_across_date_shift_and_usable_quantity_loss"
                            if not failure_mode
                            else boundary_contract.HYPOTHESIS_FAMILY_BY_FAILURE_MODE[
                                failure_mode
                            ]
                        ),
                        "metric_key": metric_key,
                        "metric_label": boundary_contract.METRIC_BY_KEY[
                            metric_key
                        ].label,
                        "metric_unit": boundary_contract.METRIC_BY_KEY[metric_key].unit,
                        "direction": boundary_contract.METRIC_BY_KEY[
                            metric_key
                        ].direction,
                        "descriptive_metric_rank": index + 1,
                        "supplier_id": supplier,
                        "supplier_lane_count": 1,
                        "tested_scenario_count": 2,
                        "driver_scenario_id": (
                            f"chain_{index:02d}__{failure_mode or 'transport_delay'}__severe"
                        ),
                        "driver_chain_id": f"chain_{index:02d}",
                        "driver_failure_mode": failure_mode or "transport_delay",
                        "metric_value": _metric_value(metric_key, index),
                        "top3_presence_seed_count": 30 if index < 3 else 0,
                        "paired_seed_count": 30,
                        "metric_priority_set_release_pass": envelope_released,
                        "rank_is_descriptive_identifier_tie_break_not_evidence": True,
                        "universal_supplier_criticality_claimed": False,
                        "evidence_class": "conditional_simulation_hypothesis",
                        "historical_occurrence_probability": "not_estimated",
                    }
                )
    _csv(boundary / "supplier_metric_rankings.csv", ranking_rows)
    effect_rows: list[dict[str, object]] = []
    for index in range(36):
        effect_rows.append(
            {
                "aggregation_level": "scenario",
                "aggregation_scope": "single_scenario_single_failure_mode",
                "supplier_id": LANE_SUPPLIERS[index // 2],
                "scenario_id": f"scenario-{index:02d}",
                "chain_id": f"chain_{index // 2:02d}",
                "failure_mode": (
                    "transport_delay" if index % 2 == 0 else "supply_availability"
                ),
                "paired_seed_count": 30,
                "client_effect_seed_count": 30 if index < 6 else 0,
                "production_only_effect_seed_count": 0,
                "upstream_absorbed_seed_count": 0,
                "no_measurable_effect_seed_count": 0 if index < 6 else 30,
                "inactive_window_seed_count": 0,
                "interpretation": "part_des_simulations_conditionnelles_pas_une_probabilite",
                "historical_occurrence_probability": "not_estimated",
            }
        )
    for supplier_index, supplier in enumerate(SUPPLIERS):
        for failure_mode in sorted(boundary_contract.CONFIRMED_FAILURE_MODES):
            effect_rows.append(
                {
                    "aggregation_level": "supplier_failure_mode_specific",
                    "aggregation_scope": "failure_mode_specific",
                    "supplier_id": supplier,
                    "scenario_id": "",
                    "chain_id": f"chain_{supplier_index:02d}",
                    "failure_mode": failure_mode,
                    "paired_seed_count": 30,
                    "client_effect_seed_count": max(0, 30 - supplier_index),
                    "production_only_effect_seed_count": supplier_index % 3,
                    "upstream_absorbed_seed_count": supplier_index % 2,
                    "no_measurable_effect_seed_count": min(30, supplier_index),
                    "inactive_window_seed_count": 0,
                    "interpretation": "part_des_simulations_conditionnelles_pas_une_probabilite",
                    "historical_occurrence_probability": "not_estimated",
                }
            )
        effect_rows.append(
            {
                "aggregation_level": "supplier_any_confirmed_scenario",
                "aggregation_scope": "any_of_two_predeclared_hypotheses",
                "supplier_id": supplier,
                "scenario_id": "",
                "chain_id": f"chain_{supplier_index:02d}",
                "failure_mode": "supply_availability|transport_delay",
                "paired_seed_count": 30,
                "client_effect_seed_count": max(0, 30 - supplier_index),
                "production_only_effect_seed_count": supplier_index % 3,
                "upstream_absorbed_seed_count": supplier_index % 2,
                "no_measurable_effect_seed_count": min(30, supplier_index),
                "inactive_window_seed_count": supplier_index % 4,
                "interpretation": "part_des_simulations_conditionnelles_pas_une_probabilite",
                "historical_occurrence_probability": "not_estimated",
            }
        )
    _csv(boundary / "conditional_effect_seed_counts.csv", effect_rows)
    provenance_rows = [
        {
            "scenario_id": scenario_id,
            "seed": seed,
            "provenance_source": "confirmation_metrics_embedded_field",
            "resolved_common_random_numbers": True,
            "summary_policy_seed": seed,
        }
        for scenario_id in (
            "baseline_nominal",
            *(f"scenario-{i:02d}" for i in range(36)),
        )
        for seed in SEEDS
    ]
    _csv(boundary / "common_random_numbers_provenance.csv", provenance_rows)
    artifact_hashes = {
        name: dashboard._sha256(boundary / name)
        for name in boundary_contract.OUTPUT_FILES
    }
    source_hashes = {
        "confirmation_supplier_sensitivity_ranking.csv": dashboard._sha256(
            overlay / "confirmation_supplier_sensitivity_ranking.csv"
        )
    }
    signature_payload: dict[str, object] = {
        "schema_version": boundary_contract.MANIFEST_SCHEMA_VERSION,
        "builder_sha256": dashboard.EXPECTED_BOUNDARY_BUILDER_SHA256,
        "source_file_sha256": source_hashes,
        "artifact_file_sha256": artifact_hashes,
        "bootstrap_resample_count": boundary_contract.BOOTSTRAP_RESAMPLE_COUNT,
    }
    _json(
        boundary / "priority_boundary_audit_manifest.json",
        {
            **signature_payload,
            "status": "complete",
            "package_signature": boundary_contract._canonical_sha256(signature_payload),
            "service_priority_set_release_pass": envelope_released,
            "universal_supplier_top3_release_pass": envelope_released,
        },
    )
    return boundary


BOUNDARY_METRIC_ORDER_FOR_TEST = tuple(boundary_contract.METRIC_BY_KEY)


def _fixture(tmp_path: Path, *, envelope_released: bool = False) -> tuple[Path, Path]:
    overlay = _write_overlay(tmp_path)
    boundary = _write_boundary(
        tmp_path,
        overlay=overlay,
        envelope_released=envelope_released,
    )
    return overlay, boundary


def test_builds_signed_autonomous_page_with_scientific_scope(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path)
    output = tmp_path / "network-results.html"
    result = dashboard.build_network_dashboard(
        artifact_dir=overlay,
        priority_boundary_audit_dir=boundary,
        output_html=output,
    )
    document = output.read_text(encoding="utf-8")

    assert result["stable_priority_count"] == 0
    assert result["priority_group_supplier_count"] == 4
    assert result["priority_reporting_status"] == "priority_group_only"
    assert result["input_status"] == "signed_scientific_overlay_and_audits_valid"
    assert result["global_network_priority_robustness_evaluable"] is False
    assert result["actions_promoted"] is False
    assert result["genealogical_lot_detail_count"] == 18
    assert "Voir les 4 configurations avec des lots exposés" in document
    assert "Explorer les 18 événements de lots simulés exposés" in document
    assert "LOT-ROOT-01" in document
    assert "aucun retard ni perte attribué à ce lot" in document
    assert "Borne haute d'exposition, pas une perte attribuée" in document
    assert "Groupe à instruire, sans trio publié" in document
    assert "QUATRE LECTURES SÉPARÉES" in document
    assert "DEUX FAMILLES PRÉ-DÉCLARÉES" in document
    assert "Les 18 voies sont confirmées avec 30 comparaisons appariées" in document
    assert "Les quatre causes et les quatre périodes sont approfondies sur les quatre voies" in document
    assert "Les niveaux intermédiaires du premier tri reposent sur une seule simulation" in document
    assert "Dans combien des 30 simulations appariées" in document
    assert "La conséquence change selon la période ou la cause testée" in document
    assert "les 4 voies du groupe service non séparé" in document
    assert "Lots potentiellement exposés et effet réellement attribuable" in document
    assert "Une comparaison appariée est réalisée pour chacune des quatre voies" in document
    assert "ne fournit pas encore la variabilité statistique des effets lot par lot" in document
    assert "Aucune action n’est sélectionnée ni recommandée" in document
    assert "Aucun des quatre leviers ci-dessous n’a encore été comparé" in document
    assert "ne mesurent pas l’efficacité de ces leviers sur les dossiers affichés" in document
    assert "La mesure brute de récupération du réseau est exclue" in document
    assert "OTIF" not in document
    assert "<script src=" not in document
    assert "https://" not in document


def test_boundary_failure_publishes_only_an_unranked_group(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path, envelope_released=False)
    data = dashboard.load_network_results(
        overlay,
        priority_boundary_audit_dir=boundary,
    )
    document = dashboard.render_network_dashboard(
        data,
        links={},
        generated_label="test",
    )

    assert data["stable_priorities"] == []
    assert data["priority_reporting_status"] == "priority_group_only"
    assert data["priority_group_supplier_ids"] == list(SUPPLIERS[:4])
    assert "Groupe à instruire, sans trio publié" in document
    assert "Membre du trio publié" not in document
    assert "<th>Rang" not in document
    assert "Position agrégée" not in document


def test_inherited_priority_flags_cannot_override_signed_boundary(
    tmp_path: Path,
) -> None:
    overlay, boundary = _fixture(tmp_path, envelope_released=False)
    campaign_path = overlay / "campaign_manifest.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    campaign["priority_set_stabilized"] = True
    campaign["rank3_rank4_interval_separated"] = True
    _json(campaign_path, campaign)
    audit_signature = json.loads(
        (overlay / "extension_interpretation_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )["package_signature"]
    _resign_overlay(overlay, audit_signature)

    data = dashboard.load_network_results(
        overlay,
        priority_boundary_audit_dir=boundary,
    )

    assert data["legacy_priority_flags_ignored"] is True
    assert data["stable_priorities"] == []
    assert data["priority_reporting_status"] == "priority_group_only"


def test_tampered_overlay_is_rejected_before_rendering(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path)
    path = overlay / "temporal_effect_by_lane_window.csv"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Empreinte de surcouche invalide"):
        dashboard.load_network_results(
            overlay,
            priority_boundary_audit_dir=boundary,
        )


def test_overlay_inventory_is_exact(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path)
    (overlay / "unsigned_legacy_alias.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Inventaire disque de la surcouche"):
        dashboard.load_network_results(
            overlay,
            priority_boundary_audit_dir=boundary,
        )


def test_resigned_legacy_extension_release_alias_cannot_be_reactivated(
    tmp_path: Path,
) -> None:
    overlay, boundary = _fixture(tmp_path)
    manifest_path = overlay / "temporal_robustness_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["release_gate_pass"] = True
    _json(manifest_path, manifest)
    audit_signature = json.loads(
        (overlay / "extension_interpretation_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )["package_signature"]
    _resign_overlay(overlay, audit_signature)

    with pytest.raises(ValueError, match="Alias release_gate_pass non neutralise"):
        dashboard.load_network_results(
            overlay,
            priority_boundary_audit_dir=boundary,
        )


def test_tampered_boundary_is_rejected_before_rendering(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path)
    path = boundary / "conditional_effect_seed_counts.csv"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Empreinte invalide"):
        dashboard.load_network_results(
            overlay,
            priority_boundary_audit_dir=boundary,
        )


def test_unsigned_boundary_is_mandatory(tmp_path: Path) -> None:
    overlay = _write_overlay(tmp_path)

    with pytest.raises(ValueError, match="audit de frontière est requis"):
        dashboard.load_network_results(overlay)


def test_action_selector_input_is_never_promoted(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path)
    inherited_actions = tmp_path / "inherited-actions"
    inherited_actions.mkdir()
    _json(
        inherited_actions / "action_selector_manifest.json",
        {"promotion_allowed": True, "industrial_recommendation_claimed": True},
    )

    data = dashboard.load_network_results(
        overlay,
        priority_boundary_audit_dir=boundary,
        action_selection_dir=inherited_actions,
    )

    assert data["actions"] == {
        "manifest": {},
        "released": False,
        "selected": [],
        "blocked": [],
        "forced_not_promoted": True,
        "input_was_supplied_but_ignored": True,
    }


def test_relative_navigation_links_remain_local_and_optional(tmp_path: Path) -> None:
    overlay, boundary = _fixture(tmp_path)
    pages = tmp_path / "pages"
    pages.mkdir()
    meeting = pages / "meeting.html"
    component = pages / "component.html"
    map_page = pages / "map.html"
    for path in (meeting, component, map_page):
        path.write_text("<!doctype html>", encoding="utf-8")
    output = pages / "network" / "results.html"

    dashboard.build_network_dashboard(
        artifact_dir=overlay,
        priority_boundary_audit_dir=boundary,
        output_html=output,
        meeting_html=meeting,
        component_html=component,
        map_html=map_page,
    )
    document = output.read_text(encoding="utf-8")

    assert 'href="../meeting.html"' in document
    assert 'href="../component.html"' in document
    assert 'href="../map.html"' in document
