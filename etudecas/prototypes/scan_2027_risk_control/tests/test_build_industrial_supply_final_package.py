from __future__ import annotations

import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_industrial_supply_final_package as final,
)


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _component_fixture(root: Path) -> Path:
    root.mkdir()
    payload = root / "future_autonomous_page_payload.json"
    audit = root / "observed_order_book_audit.json"
    index = root / "index.html"
    named = root / "supplier_021081_final_v3.html"
    _json(
        payload,
        {
            "schema_version": "supplier-021081-final-dashboard.v2",
            "service_metric": {
                "metric_id": "product_on_due_volume_proxy",
                "product_id": "268967",
                "horizon_days": 720,
                "label_fr": "part simulée du volume demandé",
                "interpretation_boundary": (
                    "indicateur conditionnel ; ni l’OTIF d’un fournisseur ni une performance observée"
                ),
            },
            "evidence_dictionary": {
                "observed": "Une date planifiée dans le fichier.",
                "simulated": "Ce n’est pas une performance fournisseur.",
                "priority_signal": "Ce n’est pas une recommandation automatique.",
                "hypothesis": "Paramètre à valider.",
            },
            "scientific_conclusions": {
                "target_80": "Ce n’est ni une cible ni une action.",
                "target_93": "Aucun niveau de stock n’est recommandé.",
                "lots": "Aucun effet client, coût ou action n’est démontré.",
            },
        },
    )
    _json(audit, {"validated": True, "order_count": 23})
    page = """<!doctype html><html lang="fr"><head><meta charset="utf-8"></head><body>
    <h1>Commandes planifiées et effets simulés d’incidents</h1>
    <h2>Calibrage diagnostique de l’état de stock 773474</h2>
    <h3>Unité de nomenclature : l’essai n’arbitre pas</h3>
    <p>Retenue qualité hypothétique de 180 jours.</p>
    <p>Sur 10 simulations appariées testées.</p>
    <p>Ces parts ne sont ni une fréquence historique ni une probabilité fournisseur.</p>
    <p>Ni l’OTIF d’un fournisseur ni une performance observée.</p>
    </body></html>"""
    index.write_text(page, encoding="utf-8")
    named.write_text(page, encoding="utf-8")
    manifest = {
        "schema_version": final.COMPONENT_SCHEMA,
        "reporting_revision": final.COMPONENT_REPORTING_REVISION,
        "status": "complete",
        "mode": "audited_v2_reporting_consolidation",
        "all_execution_packages_audited": True,
        "reproducibility_wording_allowed": True,
        "simulation_rerun_by_builder": False,
        "previous_outputs_modified": False,
        "source_packages": [
            {"role": role, "status": "complete", "directory": f"source/{role}"}
            for role in sorted(final.EXPECTED_COMPONENT_ROLES)
        ],
        "input_manifest_statuses": {
            "demasking": "complete",
            "unit": "complete",
            "calibration": "complete",
            "orderbook_snapshot": "complete",
            "orderbook_prospective": "complete",
            "orderbook_confirmation": "complete",
        },
        "outputs": {
            "dashboard_payload": payload.name,
            "observed_order_audit": audit.name,
            "autonomous_html": index.name,
            "autonomous_html_named_copy": named.name,
        },
        "output_sha256": {
            path.name: final._sha256(path) for path in (payload, audit, index, named)
        },
    }
    _json(root / "campaign_manifest.json", manifest)
    return root


def _network_consolidation_fixture(root: Path) -> Path:
    root.mkdir()
    source_file = root / "supplier_sensitivity_ranking.csv"
    extension_file = root / "temporal_robustness_summary.csv"
    source_file.write_text("supplier_id\nSDC-A\n", encoding="utf-8")
    extension_file.write_text("case_id\ncase-1\n", encoding="utf-8")
    extension_names = {
        key: values[2] for key, values in final.network_dashboard.EXTENSIONS.items()
    }
    extension_names["causal_lot_attribution"] = "causal_lot_attribution_manifest.json"
    extension_hashes = {}
    for key, name in extension_names.items():
        path = root / name
        _json(path, {"extension": key, "status": "complete"})
        extension_hashes[key] = final._sha256(path)
    campaign = {
        "status": "complete",
        "mode": "full",
        "consolidated_additive_artifact": True,
        "consolidation_signature": "signed-consolidation",
        "source_campaign_complete": True,
        "extension_runner_complete": True,
        "previous_artifacts_mutated": False,
        "large_case_directories_copied": False,
    }
    _json(root / "campaign_manifest.json", campaign)
    _json(
        root / "consolidation_manifest.json",
        {
            "schema_version": final.NETWORK_CONSOLIDATION_SCHEMA,
            "status": "complete",
            "consolidation_signature": "signed-consolidation",
            "large_case_directories_copied": False,
            "source_artifacts_mutated": False,
            "source_small_file_hashes": {source_file.name: final._sha256(source_file)},
            "extension_small_file_hashes": {
                extension_file.name: final._sha256(extension_file)
            },
            "extension_manifest_hashes": extension_hashes,
        },
    )
    return root


def _scientific_group_four_lineage() -> dict:
    suppliers = ["SDC-A", "SDC-B", "SDC-C", "SDC-D"]
    chains = ["chain-a", "chain-b", "chain-c", "chain-d"]
    universal = sorted(
        [
            *suppliers,
            "SDC-E",
            "SDC-F",
            "SDC-G",
            "SDC-H",
            "SDC-I",
            "SDC-J",
            "SDC-K",
            "SDC-L",
            "SDC-M",
            "SDC-N",
            "SDC-VD0519670A",
            "SDC-VD0520132A",
        ]
    )
    lane_counts = {supplier: 1 for supplier in universal}
    lane_counts["SDC-VD0519670A"] = 2
    lane_counts["SDC-VD0520132A"] = 2
    mappings = [
        {
            "selection_slot": index,
            "supplier_id": supplier,
            "driver_chain_id": chain,
            "driver_scenario_id": f"{chain}__transport_delay__120",
            "driver_failure_mode": "transport_delay",
            "driver_lane_uniqueness_claimed": False,
            "driver_selection_rule": (
                "worst_mean_service_scenario_then_identifier_tie_break"
            ),
        }
        for index, (supplier, chain) in enumerate(
            zip(suppliers, chains, strict=True), 1
        )
    ]
    lineage = {
        "schema_version": "etudecas.supplier_network_priority_selection_lineage.v1",
        "contract_revision": "setwise_descriptive_postselection_lineage_2026_09",
        "priority_selection_status": (
            "complete_service_nonseparation_group_follow_up"
        ),
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "envelope_service_priority_set_release_pass": False,
        "selection_candidate_pool_supplier_ids": suppliers,
        "service_nonseparation_group_supplier_ids": suppliers,
        "follow_up_supplier_ids": suppliers,
        "priority_supplier_ids": suppliers,
        "boundary_universal_nonseparation_group_supplier_ids": universal,
        "follow_up_chain_ids": chains,
        "priority_chain_ids": chains,
        "follow_up_driver_mappings": mappings,
        "priority_driver_mappings": mappings,
        "follow_up_group_is_unordered": True,
        "priority_fields_are_legacy_compatibility_aliases": True,
        "selected_subset_covers_candidate_pool": True,
        "selected_subset_covers_service_nonseparation_group": True,
        "service_nonseparation_group_fully_followed_up": True,
        "extension_is_post_selection_characterization_not_confirmation": True,
        "independent_confirmation_required_for_confirmatory_top3": True,
        "lane_specific_peak_flow_window_selection": True,
        "integrity_digest_not_authenticated_signature": True,
        "internal_consistency_recomputed_from_source": True,
        "slot_order_has_scientific_meaning": False,
        "scientific_order_claimed": False,
        "selected_subset_covers_boundary_universal_group": False,
        "driver_lane_uniqueness_claimed": False,
        "selection_and_assessment_seed_blocks_independent": False,
        "post_selection_confirmatory_inference_evaluable": False,
        "population_or_out_of_sample_top3_claimed": False,
        "extension_seed_blocks_independent_of_priority_selection": False,
        "cross_baseline_service_level_priority_robustness_evaluable": False,
        "cross_lane_same_calendar_comparison": False,
        "intrinsic_supplier_reliability_claimed": False,
        "lane_count_normalization_applied": False,
        "cryptographic_authentication_present": False,
        "broad_supply_uncertainty_monte_carlo_claimed": False,
        "historical_recurrence_evaluable": False,
        "global_variance_based_sensitivity_evaluable": False,
        "action_lever_influence_ranking_evaluable": False,
        "risk_to_risk_cascade_evaluable": False,
        "network_contagion_probability_evaluable": False,
        "individual_customer_or_order_attribution_evaluable": False,
        "revenue_or_penalty_loss_evaluable": False,
        "counterfactual_entity_identity_validated": False,
        "network_wide_lot_effect_evaluable": False,
        "multi_lane_common_cause_lot_effect_evaluable": False,
        "four_cause_lot_effect_evaluable": False,
        "temporal_lot_effect_variability_evaluable": False,
        "lot_effect_recurrence_evaluable": False,
        "quality_hold_event_anchor": "shipment_decision_day",
        "opening_or_preexisting_in_transit_receipts_affected": False,
        "native_quarantine_inventory_modeled": False,
        "laboratory_release_process_modeled": False,
        "causal_lot_pair_count": 4,
        "paired_seed_count_per_causal_lot_lane": 1,
        "supplier_lane_count_by_id": lane_counts,
        "all_multi_lane_supplier_ids": [
            "SDC-VD0519670A",
            "SDC-VD0520132A",
        ],
        "all_multi_lane_supplier_active_chain_ids_by_id": {
            "SDC-VD0519670A": ["multi-a", "multi-b"],
            "SDC-VD0520132A": ["multi-c", "multi-d"],
        },
        "multi_lane_common_cause_scope_complete": True,
        "priority_boundary_package_signature": "1" * 64,
        "priority_boundary_manifest_sha256": "2" * 64,
        "priority_boundary_result_sha256": "3" * 64,
        "priority_boundary_ranking_sha256": "4" * 64,
        "priority_boundary_builder_sha256": "5" * 64,
        "source_campaign_manifest_sha256": "6" * 64,
        "source_campaign_signature": "7" * 64,
    }
    lineage["priority_selection_lineage_sha256"] = final._canonical_sha256(lineage)
    return lineage


def _scientific_network_fixture(
    root: Path,
    boundary_root: Path,
    *,
    scoped_top3: bool = True,
) -> tuple[Path, Path]:
    """Create a compact, fully signed overlay + boundary package."""

    del scoped_top3
    root.mkdir()
    boundary_root.mkdir()
    lineage = _scientific_group_four_lineage()
    lineage_digest = lineage["priority_selection_lineage_sha256"]
    (root / "supplier_sensitivity_ranking.csv").write_text(
        "supplier_id,supplier_sensitivity_rank\nSDC-A,1\nSDC-B,2\nSDC-C,3\n",
        encoding="utf-8",
    )
    (root / "confirmed_top3_stability.csv").write_text(
        "supplier_id,aggregate_confirmation_rank\nSDC-A,1\nSDC-B,2\nSDC-C,3\n",
        encoding="utf-8",
    )
    (root / "failure_mode_sensitivity_summary.csv").write_text(
        "failure_mode,effect\ntransport_delay,0\n", encoding="utf-8"
    )
    (root / "confirmation_supplier_sensitivity_ranking.csv").write_text(
        "supplier_id,supplier_sensitivity_rank\nSDC-A,1\nSDC-B,2\nSDC-C,3\n",
        encoding="utf-8",
    )
    (root / "confirmation_metrics.csv").write_text(
        "scenario_id,seed\nbaseline_nominal,1\n", encoding="utf-8"
    )
    _json(root / "confirmation_selection.json", {"status": "complete"})
    (root / "scenario_design.csv").write_text(
        "scenario_id\nbaseline_nominal\n", encoding="utf-8"
    )
    original_campaign = root.parent / f"{root.name}-original-campaign.json"
    _json(original_campaign, {"status": "complete", "mode": "full"})
    original_campaign_hash = final._sha256(original_campaign)
    lineage["source_campaign_manifest_sha256"] = original_campaign_hash
    lineage["priority_selection_lineage_sha256"] = final._canonical_sha256(
        {
            key: value
            for key, value in lineage.items()
            if key != "priority_selection_lineage_sha256"
        }
    )
    lineage_digest = lineage["priority_selection_lineage_sha256"]
    consolidated_campaign = root.parent / f"{root.name}-consolidated-campaign.json"
    _json(
        consolidated_campaign,
        {
            "status": "complete",
            "mode": "full",
            "priority_set_stabilized": True,
            "scientific_release_gates": {"all_release_gates_pass": True},
        },
    )
    consolidated_campaign_hash = final._sha256(consolidated_campaign)
    legacy = {
        "schema_version": final.NETWORK_CONSOLIDATION_SCHEMA,
        "status": "complete",
        "source_campaign_manifest_sha256": original_campaign_hash,
        "consolidated_campaign_manifest_sha256": consolidated_campaign_hash,
        "large_case_directories_copied": False,
        "source_artifacts_mutated": False,
    }
    _json(root / "legacy_consolidation_manifest.json", legacy)
    campaign = {
        "status": "complete",
        "mode": "full",
        "confirmation_seed_count": 30,
        "priority_set_stabilized": True,
        "scientific_release_gates": {"all_release_gates_pass": True},
        "scientific_interpretation_overlay_applied": True,
        "legacy_runner_promotion_aliases_neutralized": True,
        "promotion_allowed": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "priority_selection_lineage": lineage,
        "priority_selection_lineage_sha256": lineage_digest,
        "extension_runner_signature": "a" * 64,
        "legacy_source_artifacts_not_scientifically_released": list(
            final.extension_audit.CONSOLIDATED_SMALL_SOURCE_FILES
        ),
        "legacy_ranking_artifacts_not_scientifically_released": list(
            final.extension_audit.LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
        ),
        "legacy_ranking_display_allowed": False,
        "legacy_ranking_used_for_extension_interpretation": False,
        "extensions_required": {
            name: {"pass": False}
            for name in (
                "multi_lane_supplier_common_cause",
                "temporal_robustness",
                "priority_four_business_causes",
                "causal_lot_attribution",
            )
        },
    }
    _json(root / "campaign_manifest.json", campaign)
    controls = {
        "schema_version": final.EXTENSION_AUDIT_RESULT_SCHEMA,
        "status": "scientific_controls_complete",
        "execution_integrity_pass": True,
        "multi_lane_common_cause_execution_integrity_pass": True,
        "temporal_execution_integrity_pass": True,
        "four_cause_execution_integrity_pass": True,
        "causal_lot_pairing_integrity_pass": True,
        "causal_lot_attribution_available": False,
        "global_priority_temporal_robustness_evaluable": False,
        "global_four_cause_priority_robustness_evaluable": False,
        "global_network_priority_robustness_evaluable": False,
        "promotion_allowed": False,
        "legacy_completion_or_flow_alias_accepted_as_robustness": False,
        "multi_lane_common_cause_merged_into_one_lane_ranking": False,
        "multi_lane_common_cause_probability_or_frequency_estimated": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
        "priority_selection_lineage": lineage,
        "priority_selection_lineage_sha256": lineage_digest,
        "priority_boundary_lineage_integrity_pass": True,
        "follow_up_group_supplier_count": 4,
        "follow_up_group_is_unordered": True,
        "slot_order_has_scientific_meaning": False,
        "counterfactual_entity_identity_validated": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "legacy_source_artifacts_not_scientifically_released": list(
            final.extension_audit.CONSOLIDATED_SMALL_SOURCE_FILES
        ),
        "legacy_ranking_artifacts_not_scientifically_released": list(
            final.extension_audit.LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
        ),
        "legacy_ranking_display_allowed": False,
        "legacy_ranking_used_for_extension_interpretation": False,
    }
    _json(root / "scientific_promotion_controls.json", controls)
    _json(
        root / "scientific_extension_interpretation_audit.json",
        {
            "schema_version": final.EXTENSION_AUDIT_RESULT_SCHEMA,
            "status": "complete",
            "bootstrap": {"resample_count": 10_000},
            "network_recovery_metric": {"used_in_any_gate_or_ranking": False},
            "priority_selection_lineage": lineage,
            "priority_selection_lineage_sha256": lineage_digest,
            "priority_boundary_lineage_integrity_pass": True,
            "source_runner_signature": "a" * 64,
            "source_plan_signature": "b" * 64,
        },
    )
    for name in (
        "temporal_effect_by_lane_window.csv",
        "temporal_pairwise_difference_audit.csv",
        "four_cause_effect_by_lane_cause.csv",
        "four_cause_pairwise_difference_audit.csv",
        "common_cause_effect_by_supplier_cause.csv",
    ):
        (root / name).write_text("metric,value\nservice,0\n", encoding="utf-8")
    extension_hashes = {
        name: final._sha256(root / name) for name in final.extension_audit.OUTPUT_FILES
    }
    extension_signature_payload = {
        "schema_version": final.EXTENSION_AUDIT_PACKAGE_SCHEMA,
        "builder_sha256": final.EXTENSION_AUDIT_BUILDER_SHA256.lower(),
        "source_file_sha256": {"runner": "1" * 64},
        "ledger_case_registry_sha256": "2" * 64,
        "artifact_file_sha256": extension_hashes,
        "bootstrap_resample_count": 10_000,
    }
    extension_manifest = {
        **extension_signature_payload,
        "status": "complete",
        "package_signature": final._canonical_sha256(extension_signature_payload),
        "previous_artifacts_mutated": False,
        "source_artifacts_mutated": False,
        "large_case_directories_copied": False,
        "promotion_allowed": False,
    }
    _json(root / "extension_interpretation_audit_manifest.json", extension_manifest)
    for name in (
        "multi_lane_supplier_common_cause_manifest.json",
        "temporal_robustness_manifest.json",
        "priority_four_business_causes_manifest.json",
        "causal_lot_attribution_manifest.json",
    ):
        _json(
            root / name,
            {
                "release_gate_pass": False,
                "legacy_runner_release_gate_value": True,
                "release_gate_semantics": (
                    "completion_and_flow_only_not_scientific_robustness"
                ),
            },
        )
    _json(
        root / "post_priority_extension_runner_manifest.json",
        {
            "promotion_allowed": False,
            "priority_selection_lineage": lineage,
            "priority_selection_lineage_sha256": lineage_digest,
            "runner_signature": "a" * 64,
            "plan_signature": "b" * 64,
            "plan_manifest_sha256": "c" * 64,
            "source_campaign_manifest_sha256": original_campaign_hash,
            "causal_lot_release_gate_pass": False,
            "extension_release_gates": {
                "common": False,
                "temporal": False,
                "four": False,
                "causal": False,
            },
        },
    )
    for name in final.extension_audit.CONSOLIDATED_SMALL_EXTENSION_FILES:
        path = root / name
        if not path.exists():
            path.write_text("case_id\n", encoding="utf-8")
    legacy_source_small_names = (
        "supplier_sensitivity_ranking.csv",
        "failure_mode_sensitivity_summary.csv",
        "confirmed_top3_stability.csv",
        "confirmation_supplier_sensitivity_ranking.csv",
    )
    legacy_source_small_hashes = {
        name: final._sha256(root / name) for name in legacy_source_small_names
    }
    legacy_extension_small_hashes = {
        name: final._sha256(root / name)
        for name in final.extension_audit.CONSOLIDATED_SMALL_EXTENSION_FILES
    }
    legacy_extension_manifest_hashes = {
        extension: final._sha256(root / name)
        for extension, name in (
            final.extension_audit.CONSOLIDATED_EXTENSION_MANIFEST_FILES.items()
        )
    }
    runner_manifest_hash = legacy_extension_small_hashes[
        "post_priority_extension_runner_manifest.json"
    ]
    extension_source_hashes = {
        "runner/post_priority_extension_runner_manifest.json": runner_manifest_hash,
        "plan/post_priority_extensions_plan_manifest.json": "c" * 64,
    }
    extension_audit_payload = json.loads(
        (root / "scientific_extension_interpretation_audit.json").read_text(
            encoding="utf-8"
        )
    )
    extension_audit_payload.update(
        {
            "source_file_sha256": extension_source_hashes,
            "ledger_case_registry_sha256": "2" * 64,
            "scientific_promotion_controls": controls,
        }
    )
    _json(
        root / "scientific_extension_interpretation_audit.json",
        extension_audit_payload,
    )
    extension_hashes = {
        name: final._sha256(root / name) for name in final.extension_audit.OUTPUT_FILES
    }
    extension_signature_payload = {
        "schema_version": final.EXTENSION_AUDIT_PACKAGE_SCHEMA,
        "builder_sha256": final.EXTENSION_AUDIT_BUILDER_SHA256.lower(),
        "source_file_sha256": extension_source_hashes,
        "ledger_case_registry_sha256": "2" * 64,
        "artifact_file_sha256": extension_hashes,
        "bootstrap_resample_count": 10_000,
    }
    extension_manifest = {
        **extension_signature_payload,
        "status": "complete",
        "package_signature": final._canonical_sha256(extension_signature_payload),
        "previous_artifacts_mutated": False,
        "source_artifacts_mutated": False,
        "large_case_directories_copied": False,
        "promotion_allowed": False,
    }
    _json(root / "extension_interpretation_audit_manifest.json", extension_manifest)
    legacy.update(
        {
            "source_small_file_hashes": legacy_source_small_hashes,
            "extension_small_file_hashes": legacy_extension_small_hashes,
            "runner_manifest_sha256": runner_manifest_hash,
            "extension_manifest_hashes": legacy_extension_manifest_hashes,
            "confirmatory_priority_set_release_allowed": False,
            "global_priority_release_allowed": False,
            "action_promotion_allowed": False,
            "priority_selection_lineage_sha256": lineage_digest,
        }
    )
    legacy_signature_payload = {
        key: legacy.get(key)
        for key in (
            "schema_version",
            "source_campaign_manifest_sha256",
            "source_small_file_hashes",
            "extension_small_file_hashes",
            "runner_manifest_sha256",
            "extension_manifest_hashes",
        )
    }
    legacy["consolidation_signature"] = final._canonical_sha256(
        legacy_signature_payload
    )
    _json(root / "legacy_consolidation_manifest.json", legacy)
    source_hashes = {
        "campaign_manifest.json": consolidated_campaign_hash,
        "consolidation_manifest.json": final._sha256(
            root / "legacy_consolidation_manifest.json"
        ),
        **legacy_source_small_hashes,
        **legacy_extension_small_hashes,
    }
    artifact_hashes = {
        path.name: final._sha256(path) for path in root.iterdir() if path.is_file()
    }
    overlay_signature_payload = {
        "schema_version": final.NETWORK_SCIENTIFIC_OVERLAY_SCHEMA,
        "builder_sha256": final.EXTENSION_AUDIT_BUILDER_SHA256.lower(),
        "source_consolidated_file_sha256": source_hashes,
        "source_audit_package_signature": extension_manifest["package_signature"],
        "artifact_file_sha256": artifact_hashes,
        "legacy_source_artifacts_not_scientifically_released": list(
            final.extension_audit.CONSOLIDATED_SMALL_SOURCE_FILES
        ),
        "legacy_ranking_artifacts_not_scientifically_released": list(
            final.extension_audit.LEGACY_RANKING_ARTIFACTS_NOT_SCIENTIFICALLY_RELEASED
        ),
        "legacy_ranking_display_allowed": False,
    }
    _json(
        root / "scientific_overlay_manifest.json",
        {
            **overlay_signature_payload,
            "status": "complete",
            "overlay_signature": final._canonical_sha256(overlay_signature_payload),
            "source_consolidated_mutated": False,
            "source_audit_mutated": False,
            "legacy_promotion_aliases_neutralized": True,
            "promotion_allowed": False,
            "large_files_copied": False,
        },
    )

    service_group_ids = ["SDC-A", "SDC-B", "SDC-C", "SDC-D"]
    universal_group_ids = list(
        lineage["boundary_universal_nonseparation_group_supplier_ids"]
    )
    boundary_result = {
        "schema_version": final.PRIORITY_BOUNDARY_RESULT_SCHEMA,
        "status": "complete",
        "bootstrap": {"paired_seed_count": 30, "resample_count": 10_000},
        "execution_integrity_pass": True,
        "interpretation_prerequisites_pass": True,
        "descriptive_priority_display_inputs_pass": True,
        "scientific_priority_release_inputs_pass": False,
        "industrial_supplier_criticality_claimed": False,
        "historical_occurrence_probability": "not_estimated",
        "service_priority_scope": final.boundary_audit.SUPPLIER_ENVELOPE_SCOPE,
        "scoped_descriptive_priority_set_display_allowed": False,
        "confirmatory_priority_set_release_allowed": False,
        "global_priority_release_allowed": False,
        "action_promotion_allowed": False,
        "envelope_service_priority_set_release_pass": False,
        "service_priority_set_release_pass": False,
        "envelope_service_priority_supplier_ids": [],
        "envelope_service_nonseparation_group_supplier_ids": service_group_ids,
        "priority_group_supplier_ids_if_no_universal_top3": universal_group_ids,
        "universal_supplier_top3_release_pass": False,
        "common_random_numbers_provenance": {"registry_row_count": 1_110},
        "raw_network_recovery_metric": {"used_in_any_ranking_or_gate": False},
    }
    _json(
        boundary_root / "scientific_priority_boundary_audit.json",
        boundary_result,
    )
    (boundary_root / "supplier_metric_rankings.csv").write_text(
        "supplier_id,metric\nSDC-A,service\n", encoding="utf-8"
    )
    (boundary_root / "conditional_effect_seed_counts.csv").write_text(
        "supplier_id,seed_count\nSDC-A,30\n", encoding="utf-8"
    )
    provenance = [
        "scenario_id,seed,provenance_source,resolved_common_random_numbers,summary_policy_seed"
    ]
    provenance.extend(
        f"scenario-{scenario},{seed},confirmation_metrics_embedded_field,true,{seed}"
        for scenario in range(37)
        for seed in range(1, 31)
    )
    (boundary_root / "common_random_numbers_provenance.csv").write_text(
        "\n".join(provenance) + "\n", encoding="utf-8"
    )
    boundary_artifact_hashes = {
        name: final._sha256(boundary_root / name)
        for name in final.boundary_audit.OUTPUT_FILES
    }
    boundary_source_hashes = {
        "campaign_manifest.json": original_campaign_hash,
        **{
            name: final._sha256(root / name)
            for name in final.boundary_audit.REQUIRED_SOURCE_FILES
            if name != "campaign_manifest.json"
        },
    }
    boundary_signature_payload = {
        "schema_version": final.PRIORITY_BOUNDARY_PACKAGE_SCHEMA,
        "builder_sha256": final.PRIORITY_BOUNDARY_BUILDER_SHA256.lower(),
        "source_file_sha256": boundary_source_hashes,
        "artifact_file_sha256": boundary_artifact_hashes,
        "bootstrap_resample_count": 10_000,
    }
    boundary_manifest = {
        **boundary_signature_payload,
        "status": "complete",
        "package_signature": final._canonical_sha256(boundary_signature_payload),
        "previous_artifacts_mutated": False,
        "source_artifacts_mutated": False,
        "large_case_directories_copied": False,
        "service_priority_set_release_pass": False,
        "universal_supplier_top3_release_pass": False,
    }
    _json(
        boundary_root / "priority_boundary_audit_manifest.json",
        boundary_manifest,
    )
    lineage.update(
        {
            "priority_boundary_package_signature": boundary_manifest[
                "package_signature"
            ],
            "priority_boundary_manifest_sha256": final._sha256(
                boundary_root / "priority_boundary_audit_manifest.json"
            ),
            "priority_boundary_result_sha256": final._sha256(
                boundary_root / "scientific_priority_boundary_audit.json"
            ),
            "priority_boundary_ranking_sha256": final._sha256(
                boundary_root / "supplier_metric_rankings.csv"
            ),
            "priority_boundary_builder_sha256": (
                final.PRIORITY_BOUNDARY_BUILDER_SHA256.lower()
            ),
            "source_campaign_manifest_sha256": original_campaign_hash,
        }
    )
    lineage["priority_selection_lineage_sha256"] = final._canonical_sha256(
        {
            key: value
            for key, value in lineage.items()
            if key != "priority_selection_lineage_sha256"
        }
    )
    controls = json.loads(
        (root / "scientific_promotion_controls.json").read_text(encoding="utf-8")
    )
    controls["priority_selection_lineage"] = lineage
    controls["priority_selection_lineage_sha256"] = lineage[
        "priority_selection_lineage_sha256"
    ]
    _json(root / "scientific_promotion_controls.json", controls)
    extension_audit_payload = json.loads(
        (root / "scientific_extension_interpretation_audit.json").read_text(
            encoding="utf-8"
        )
    )
    extension_audit_payload["priority_selection_lineage"] = lineage
    extension_audit_payload["priority_selection_lineage_sha256"] = lineage[
        "priority_selection_lineage_sha256"
    ]
    extension_audit_payload["scientific_promotion_controls"] = controls
    _json(
        root / "scientific_extension_interpretation_audit.json",
        extension_audit_payload,
    )
    extension_manifest = json.loads(
        (root / "extension_interpretation_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    extension_manifest["artifact_file_sha256"] = {
        name: final._sha256(root / name) for name in final.extension_audit.OUTPUT_FILES
    }
    extension_signature_payload = {
        key: extension_manifest[key]
        for key in (
            "schema_version",
            "builder_sha256",
            "source_file_sha256",
            "ledger_case_registry_sha256",
            "artifact_file_sha256",
            "bootstrap_resample_count",
        )
    }
    extension_manifest["package_signature"] = final._canonical_sha256(
        extension_signature_payload
    )
    _json(
        root / "extension_interpretation_audit_manifest.json",
        extension_manifest,
    )
    overlay_manifest = json.loads(
        (root / "scientific_overlay_manifest.json").read_text(encoding="utf-8")
    )
    overlay_manifest["source_audit_package_signature"] = extension_manifest[
        "package_signature"
    ]
    overlay_manifest["artifact_file_sha256"] = {
        name: final._sha256(root / name)
        for name in overlay_manifest["artifact_file_sha256"]
    }
    overlay_signature_payload = {
        key: overlay_manifest[key]
        for key in (
            "schema_version",
            "builder_sha256",
            "source_consolidated_file_sha256",
            "source_audit_package_signature",
            "artifact_file_sha256",
            "legacy_source_artifacts_not_scientifically_released",
            "legacy_ranking_artifacts_not_scientifically_released",
            "legacy_ranking_display_allowed",
        )
    }
    overlay_manifest["overlay_signature"] = final._canonical_sha256(
        overlay_signature_payload
    )
    _json(root / "scientific_overlay_manifest.json", overlay_manifest)
    return root, boundary_root


def test_component_contract_accepts_only_the_audited_v2_roles(tmp_path: Path) -> None:
    source = _component_fixture(tmp_path / "component-final-v2")
    manifest, component_html = final._validate_component_package(source)
    assert manifest["schema_version"] == final.COMPONENT_SCHEMA
    assert component_html == source / "index.html"

    manifest = json.loads(
        (source / "campaign_manifest.json").read_text(encoding="utf-8")
    )
    reporting_revision = manifest.pop("reporting_revision")
    _json(source / "campaign_manifest.json", manifest)
    with pytest.raises(final.FinalAssemblyError, match="révision métier V3"):
        final._validate_component_package(source)

    manifest["reporting_revision"] = reporting_revision
    manifest["source_packages"][0]["directory"] = (
        "supplier_021081_active_flow_20260901_v1"
    )
    _json(source / "campaign_manifest.json", manifest)
    with pytest.raises(final.FinalAssemblyError, match="ancienne campagne"):
        final._validate_component_package(source)


def _legacy_network_consolidation_checks_copied_file_hashes(tmp_path: Path) -> None:
    source = _network_consolidation_fixture(tmp_path / "network-final")
    assert final._validate_network_consolidation(source)["status"] == "complete"
    (source / "temporal_robustness_summary.csv").write_text(
        "case_id\ntampered\n", encoding="utf-8"
    )
    with pytest.raises(final.FinalAssemblyError, match="SHA-256 incohérente"):
        final._validate_network_consolidation(source)


def test_network_requires_signed_overlay_and_boundary_but_not_global_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        final.extension_audit, "validate_scientific_overlay", lambda _root: {"valid": True}
    )
    monkeypatch.setattr(
        final.boundary_audit, "validate_audit_package", lambda _root: {"valid": True}
    )
    source, boundary = _scientific_network_fixture(
        tmp_path / "network-final",
        tmp_path / "network-boundary",
    )
    campaign, controls, result, conclusion = final._validate_network_consolidation(
        source, boundary
    )
    assert campaign["priority_set_stabilized"] is True  # legacy, deliberately ignored
    assert controls["global_network_priority_robustness_evaluable"] is False
    assert controls["promotion_allowed"] is False
    assert result["envelope_service_priority_set_release_pass"] is False
    assert result["envelope_service_nonseparation_group_supplier_ids"] == [
        "SDC-A",
        "SDC-B",
        "SDC-C",
        "SDC-D",
    ]
    assert conclusion == "service_nonseparation_group_four_follow_up"

    controls["promotion_allowed"] = True
    _json(source / "scientific_promotion_controls.json", controls)
    with pytest.raises(final.FinalAssemblyError, match="Empreinte SHA-256 incoh"):
        final._validate_network_consolidation(source, boundary)


def test_raw_legacy_consolidation_is_never_accepted_as_scientific_evidence(
    tmp_path: Path,
) -> None:
    source = _network_consolidation_fixture(tmp_path / "legacy-network-final")
    with pytest.raises(final.FinalAssemblyError, match="surcouche scientifique"):
        final._validate_network_consolidation(source, tmp_path / "missing-boundary")


def test_boundary_must_share_lineage_and_exact_signed_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        final.extension_audit, "validate_scientific_overlay", lambda _root: {"valid": True}
    )
    monkeypatch.setattr(
        final.boundary_audit, "validate_audit_package", lambda _root: {"valid": True}
    )
    source, boundary = _scientific_network_fixture(
        tmp_path / "network-final", tmp_path / "network-boundary"
    )
    manifest_path = boundary / "priority_boundary_audit_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_file_sha256"]["campaign_manifest.json"] = "0" * 64
    signature_payload = {
        key: manifest[key]
        for key in (
            "schema_version",
            "builder_sha256",
            "source_file_sha256",
            "artifact_file_sha256",
            "bootstrap_resample_count",
        )
    }
    manifest["package_signature"] = final._canonical_sha256(signature_payload)
    _json(manifest_path, manifest)
    with pytest.raises(final.FinalAssemblyError, match="campagne source"):
        final._validate_network_consolidation(source, boundary)

    source, boundary = _scientific_network_fixture(
        tmp_path / "network-final-extra", tmp_path / "network-boundary-extra"
    )
    _json(boundary / "unsigned_priority_claim.json", {"top3": True})
    with pytest.raises(final.FinalAssemblyError, match="fichier non signé"):
        final._validate_network_consolidation(source, boundary)


def _legacy_action_selection_is_bound_to_the_exact_network_hashes(
    tmp_path: Path,
) -> None:
    network = tmp_path / "network"
    action = tmp_path / "actions"
    network.mkdir()
    action.mkdir()
    for name in (
        "campaign_manifest.json",
        "supplier_sensitivity_ranking.csv",
        "confirmed_top3_stability.csv",
    ):
        (network / name).write_text(f"content-{name}", encoding="utf-8")
    (action / "selected_controllable_action_tests.csv").write_text(
        "action_id\ntargeted_transport_after_observed_delay\n", encoding="utf-8"
    )
    (action / "blocked_action_candidates.csv").write_text(
        "action_id\nprepared_qualified_alternative_source\n", encoding="utf-8"
    )
    _json(
        action / "action_selector_manifest.json",
        {
            "schema_version": final.ACTION_SCHEMA,
            "status": "prepared",
            "selection_status": "stabilized_v2_top3_consumed",
            "industrial_recommendation_claimed": False,
            "prevention_and_reaction_separated": True,
            "sources_mutated": False,
            "main_network_ranking_mutated": False,
            "selected_action_test_count": 1,
            "blocked_action_candidate_count": 1,
            "hard_exclusions": {
                "unqualified_alternative_source": True,
                "in_horizon_magic_stock_injection": True,
                "assumed_quality_or_laboratory_acceleration": True,
                "noncausal_replanning_proxy": True,
            },
            "source_hashes": {
                "network": {
                    name: final._sha256(network / name)
                    for name in (
                        "campaign_manifest.json",
                        "supplier_sensitivity_ranking.csv",
                        "confirmed_top3_stability.csv",
                    )
                }
            },
            "outputs": sorted(final.ACTION_OUTPUT_FILES),
        },
    )
    assert final._validate_action_selection(action, network)["status"] == "prepared"
    (network / "confirmed_top3_stability.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(final.FinalAssemblyError, match="SHA-256 incohérente"):
        final._validate_action_selection(action, network)


def test_prepared_actions_are_rejected_even_when_legacy_hashes_match(
    tmp_path: Path,
) -> None:
    network = tmp_path / "network"
    action = tmp_path / "actions"
    network.mkdir()
    action.mkdir()
    for name in final.ACTION_NETWORK_FILES:
        (network / name).write_text(f"content-{name}", encoding="utf-8")
    (action / "selected_controllable_action_tests.csv").write_text(
        "action_id\nready_action\n", encoding="utf-8"
    )
    (action / "blocked_action_candidates.csv").write_text(
        "action_id\nblocked_protocol\n", encoding="utf-8"
    )
    source_hashes = {
        name: final._sha256(network / name) for name in final.ACTION_NETWORK_FILES
    }
    _json(
        action / "action_selector_manifest.json",
        {
            "schema_version": final.ACTION_SCHEMA,
            "status": "prepared",
            "selection_status": "stabilized_v2_top3_consumed",
            "industrial_recommendation_claimed": False,
            "prevention_and_reaction_separated": True,
            "sources_mutated": False,
            "main_network_ranking_mutated": False,
            "selected_action_test_count": 1,
            "blocked_action_candidate_count": 1,
            "hard_exclusions": {"magic": True},
            "source_hashes": {"network": source_hashes},
            "outputs": sorted(final.ACTION_OUTPUT_FILES),
        },
    )
    with pytest.raises(final.FinalAssemblyError, match="leviers"):
        final._validate_action_selection(
            action, network, source_network_hashes=source_hashes
        )


def test_v2_action_catalogue_is_scoped_hashed_and_fully_blocked(
    tmp_path: Path,
) -> None:
    network, boundary_root = _scientific_network_fixture(
        tmp_path / "overlay", tmp_path / "boundary", scoped_top3=True
    )
    boundary = json.loads(
        (boundary_root / "scientific_priority_boundary_audit.json").read_text(
            encoding="utf-8"
        )
    )
    action = tmp_path / "actions-v2"
    action.mkdir()
    (action / "selected_controllable_action_tests.csv").write_text(
        "action_id\n", encoding="utf-8"
    )
    (action / "blocked_action_candidates.csv").write_text(
        "action_id,selector_status,candidate_scope,scientific_release_gate_pass,"
        "scientific_blocking_reason,operational_prerequisite_gate_pass,"
        "operational_prerequisite_blocking_reasons,blocking_reasons,"
        "future_test_only_not_recommendation\n"
        "targeted_transport,blocked,boundary_envelope_service_priority,false,"
        "scientific_global_priority_not_released,true,,"
        "scientific_global_priority_not_released,true\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": final.ACTION_SCHEMA_V2,
        "status": "blocked_scoped_priority_not_globally_released",
        "selection_status": "scoped_envelope_action_candidates_only",
        "candidate_supplier_ids": boundary["envelope_service_priority_supplier_ids"],
        "selected_supplier_ids": [],
        "selected_action_test_count": 0,
        "blocked_action_candidate_count": 1,
        "scientific_blocked_candidate_count": 1,
        "operationally_ready_but_scientifically_blocked_count": 1,
        "action_readiness_pass": False,
        "industrial_recommendation_claimed": False,
        "prevention_and_reaction_separated": True,
        "sources_mutated": False,
        "main_network_ranking_mutated": False,
        "hard_exclusions": {"magic_stock": True},
        "source_hashes": {
            "scientific": {
                "network_overlay": {
                    name: final._sha256(network / name)
                    for name in (
                        "scientific_overlay_manifest.json",
                        "scientific_promotion_controls.json",
                    )
                },
                "priority_boundary_audit": {
                    name: final._sha256(boundary_root / name)
                    for name in (
                        "priority_boundary_audit_manifest.json",
                        "scientific_priority_boundary_audit.json",
                    )
                },
            }
        },
        "outputs": sorted(final.ACTION_OUTPUT_FILES),
    }
    _json(action / "action_selector_manifest.json", manifest)
    validated = final._validate_scientific_action_selection(
        action,
        network_root=network,
        boundary_root=boundary_root,
        boundary=boundary,
        network_conclusion="envelope_service_top3_scoped",
        source_network_hashes=None,
    )
    assert validated["action_readiness_pass"] is False

    blocked_path = action / "blocked_action_candidates.csv"
    valid_blocked_document = blocked_path.read_text(encoding="utf-8")
    blocked_path.write_text(
        valid_blocked_document.replace(
            "scientific_global_priority_not_released,true,,",
            "missing_scientific_reason,true,,",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(final.FinalAssemblyError, match="blocage scientifique"):
        final._validate_scientific_action_selection(
            action,
            network_root=network,
            boundary_root=boundary_root,
            boundary=boundary,
            network_conclusion="envelope_service_top3_scoped",
            source_network_hashes=None,
        )
    blocked_path.write_text(valid_blocked_document, encoding="utf-8")

    manifest["source_hashes"]["scientific"]["network_overlay"][
        "scientific_promotion_controls.json"
    ] = "0" * 64
    _json(action / "action_selector_manifest.json", manifest)
    with pytest.raises(final.FinalAssemblyError, match="SHA-256 incoh"):
        final._validate_scientific_action_selection(
            action,
            network_root=network,
            boundary_root=boundary_root,
            boundary=boundary,
            network_conclusion="envelope_service_top3_scoped",
            source_network_hashes=None,
        )


def test_v3_action_catalogue_is_bound_to_exact_unordered_service_group(
    tmp_path: Path,
) -> None:
    network = tmp_path / "overlay-v3"
    boundary_root = tmp_path / "boundary-v3"
    action = tmp_path / "actions-v3"
    network.mkdir()
    boundary_root.mkdir()
    action.mkdir()
    suppliers = ["SUP-1", "SUP-2", "SUP-3", "SUP-4"]
    chains = ["chain-1", "chain-2", "chain-3", "chain-4"]
    mappings = [
        {
            "supplier_id": supplier,
            "driver_chain_id": chain,
            "driver_scenario_id": f"scenario-{index}",
            "driver_failure_mode": "transport_delay",
        }
        for index, (supplier, chain) in enumerate(
            zip(suppliers, chains, strict=True), 1
        )
    ]
    lineage = {
        "follow_up_supplier_ids": suppliers,
        "service_nonseparation_group_supplier_ids": suppliers,
        "selection_candidate_pool_supplier_ids": suppliers,
        "follow_up_chain_ids": chains,
        "follow_up_driver_mappings": mappings,
        "follow_up_group_is_unordered": True,
        "service_nonseparation_group_fully_followed_up": True,
    }
    _json(network / "scientific_overlay_manifest.json", {"status": "complete"})
    _json(
        network / "scientific_promotion_controls.json",
        {
            "execution_integrity_pass": True,
            "promotion_allowed": False,
            "action_promotion_allowed": False,
            "global_network_priority_robustness_evaluable": False,
            "priority_selection_lineage_sha256": "a" * 64,
            "priority_selection_lineage": lineage,
        },
    )
    _json(
        boundary_root / "priority_boundary_audit_manifest.json", {"status": "complete"}
    )
    boundary = {
        "envelope_service_nonseparation_group_supplier_ids": suppliers,
    }
    _json(boundary_root / "scientific_priority_boundary_audit.json", boundary)
    (action / "selected_controllable_action_tests.csv").write_text(
        "action_id\n", encoding="utf-8"
    )
    header = (
        "supplier_id,network_chain_ids,selector_status,candidate_scope,"
        "scientific_release_gate_pass,scientific_blocking_reason,"
        "operational_prerequisite_gate_pass,"
        "operational_prerequisite_blocking_reasons,blocking_reasons,"
        "future_test_only_not_recommendation\n"
    )
    rows = "".join(
        f"{supplier},{chain},blocked,"
        "boundary_envelope_service_nonseparation_group,false,"
        "scientific_global_priority_not_released,false,missing_evidence,"
        "missing_evidence|scientific_global_priority_not_released,true\n"
        for supplier, chain in zip(suppliers, chains, strict=True)
    )
    (action / "blocked_action_candidates.csv").write_text(
        header + rows, encoding="utf-8"
    )
    manifest = {
        "schema_version": final.ACTION_SCHEMA_V2,
        "status": "blocked_service_nonseparation_group_follow_up",
        "selection_status": "service_nonseparation_group_action_candidates_only",
        "candidate_supplier_ids": suppliers,
        "follow_up_chain_ids": chains,
        "follow_up_driver_mappings": mappings,
        "follow_up_group_supplier_count": 4,
        "follow_up_group_is_unordered": True,
        "priority_selection_lineage_sha256": "a" * 64,
        "selected_supplier_ids": [],
        "selected_action_test_count": 0,
        "blocked_action_candidate_count": 4,
        "scientific_blocked_candidate_count": 4,
        "operationally_ready_but_scientifically_blocked_count": 0,
        "action_readiness_pass": False,
        "industrial_recommendation_claimed": False,
        "prevention_and_reaction_separated": True,
        "sources_mutated": False,
        "main_network_ranking_mutated": False,
        "hard_exclusions": {"magic_stock": True},
        "source_hashes": {
            "scientific": {
                "network_overlay": {
                    name: final._sha256(network / name)
                    for name in (
                        "scientific_overlay_manifest.json",
                        "scientific_promotion_controls.json",
                    )
                },
                "priority_boundary_audit": {
                    name: final._sha256(boundary_root / name)
                    for name in (
                        "priority_boundary_audit_manifest.json",
                        "scientific_priority_boundary_audit.json",
                    )
                },
            },
            "action_input_manifest_sha256": "b" * 64,
            "action_input_generation_signature": "c" * 64,
        },
        "outputs": sorted(final.ACTION_OUTPUT_FILES),
    }
    _json(action / "action_selector_manifest.json", manifest)

    validated = final._validate_scientific_action_selection(
        action,
        network_root=network,
        boundary_root=boundary_root,
        boundary=boundary,
        network_conclusion="priority_group_not_separated",
        source_network_hashes=None,
    )
    assert validated["candidate_supplier_ids"] == suppliers
    assert validated["selected_action_test_count"] == 0

    bad = json.loads(
        (action / "action_selector_manifest.json").read_text(encoding="utf-8")
    )
    bad["candidate_supplier_ids"] = suppliers[:3]
    _json(action / "action_selector_manifest.json", bad)
    with pytest.raises(final.FinalAssemblyError, match="fail-closed"):
        final._validate_scientific_action_selection(
            action,
            network_root=network,
            boundary_root=boundary_root,
            boundary=boundary,
            network_conclusion="priority_group_not_separated",
            source_network_hashes=None,
        )


def test_blocked_action_selection_is_accepted_only_with_no_ready_row(
    tmp_path: Path,
) -> None:
    network = tmp_path / "network"
    action = tmp_path / "actions"
    network.mkdir()
    action.mkdir()
    network_names = (
        "campaign_manifest.json",
        "supplier_sensitivity_ranking.csv",
        "confirmed_top3_stability.csv",
    )
    for name in network_names:
        (network / name).write_text(f"content-{name}", encoding="utf-8")
    (action / "selected_controllable_action_tests.csv").write_text(
        "action_id\n", encoding="utf-8"
    )
    (action / "blocked_action_candidates.csv").write_text(
        "action_id\nprepared_qualified_alternative_source\n", encoding="utf-8"
    )
    manifest = {
        "schema_version": final.ACTION_SCHEMA,
        "status": "blocked_network_v2_not_stabilized",
        "selection_status": "blocked_network_v2_not_stabilized",
        "industrial_recommendation_claimed": False,
        "prevention_and_reaction_separated": True,
        "sources_mutated": False,
        "main_network_ranking_mutated": False,
        "selected_action_test_count": 0,
        "blocked_action_candidate_count": 1,
        "hard_exclusions": {
            "unqualified_alternative_source": True,
            "in_horizon_magic_stock_injection": True,
            "assumed_quality_or_laboratory_acceleration": True,
            "noncausal_replanning_proxy": True,
        },
        "source_hashes": {
            "network": {name: final._sha256(network / name) for name in network_names}
        },
        "outputs": sorted(final.ACTION_OUTPUT_FILES),
    }
    _json(action / "action_selector_manifest.json", manifest)
    assert final._validate_action_selection(
        action,
        network,
        source_network_hashes=manifest["source_hashes"]["network"],
    )["status"].startswith("blocked_")

    (action / "selected_controllable_action_tests.csv").write_text(
        "action_id\ntargeted_transport_after_observed_delay\n", encoding="utf-8"
    )
    manifest["selected_action_test_count"] = 1
    _json(action / "action_selector_manifest.json", manifest)
    with pytest.raises(final.FinalAssemblyError, match="aucune ligne comme prête"):
        final._validate_action_selection(
            action,
            network,
            source_network_hashes=manifest["source_hashes"]["network"],
        )


def _legacy_complete_unseparated_network_is_a_deliverable_priority_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    network = tmp_path / "network"
    actions = tmp_path / "actions"
    network.mkdir()
    actions.mkdir()
    campaign = {
        "confirmation_seed_count": 30,
        "scientific_release_gates": {
            key: True
            for key in (
                "baseline_both_products_on_due_at_least_95_all_seeds_pass",
                "all_metric_rows_valid_pass",
                "j0_state_hash_pairing_100pct_pass",
                "input_graph_hash_pairing_100pct_pass",
                "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass",
                "all_release_gates_pass",
            )
        },
    }
    action_manifest = {
        "status": "blocked_network_v2_not_stabilized",
        "selected_action_test_count": 0,
    }
    monkeypatch.setattr(final, "_validate_network_consolidation", lambda root: campaign)
    monkeypatch.setattr(
        final, "_validate_action_selection", lambda root, network_root: action_manifest
    )
    monkeypatch.setattr(
        final.network_dashboard,
        "load_network_results",
        lambda *args, **kwargs: {
            "ranking": [{"supplier_id": "SDC-A"}],
            "stable_priorities": [],
            "extension_passes": {
                key: True for key in final.network_dashboard.EXTENSIONS
            },
            "causal_released": True,
            "actions": {"released": False, "selected": [], "blocked": []},
        },
    )
    _, _, conclusion = final._validate_network_release(network, actions)
    assert conclusion == "priority_group_not_separated"


@pytest.mark.parametrize(
    ("conclusion", "stable_priorities"),
    [
        (
            "envelope_service_top3_scoped",
            [
                {"supplier_id": "SDC-A"},
                {"supplier_id": "SDC-B"},
                {"supplier_id": "SDC-C"},
            ],
        ),
        ("priority_group_not_separated", []),
    ],
)
def test_network_release_accepts_scoped_trio_or_group_with_actions_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    conclusion: str,
    stable_priorities: list[dict[str, str]],
) -> None:
    controls = {
        "global_network_priority_robustness_evaluable": False,
        "promotion_allowed": False,
    }
    priority_group = ["SDC-A", "SDC-B", "SDC-C", "SDC-D"]
    boundary = {
        "bootstrap": {"paired_seed_count": 30},
        "envelope_service_nonseparation_group_supplier_ids": priority_group,
    }
    monkeypatch.setattr(
        final,
        "_validate_network_consolidation",
        lambda root, boundary_root: ({}, controls, boundary, conclusion),
    )
    monkeypatch.setattr(
        final,
        "_validate_scientific_action_selection",
        lambda *args, **kwargs: {"status": "blocked_network_v2_not_stabilized"},
    )
    monkeypatch.setattr(
        final,
        "_read_json",
        lambda path: {"source_consolidated_file_sha256": {}},
    )
    monkeypatch.setattr(
        final.network_dashboard,
        "load_network_results",
        lambda *args, **kwargs: {
            "ranking": [{"supplier_id": "SDC-A"}],
            "stable_priorities": stable_priorities,
            "priority_reporting_status": (
                "envelope_service_top3_released"
                if conclusion == "envelope_service_top3_scoped"
                else "priority_group_only"
            ),
            "input_status": "signed_scientific_overlay_and_audits_valid",
            "legacy_priority_flags_ignored": True,
            "legacy_extension_release_aliases_ignored": True,
            "priority_group_supplier_ids": priority_group,
            "lot_genealogical_detail": [{"lot_id": "LOT-1"}],
            "actions": {"released": False, "selected": [], "blocked": ["catalogue"]},
        },
    )
    _, _, action, observed_conclusion = final._validate_network_release(
        tmp_path / "overlay",
        tmp_path / "boundary",
        tmp_path / "actions",
    )
    assert observed_conclusion == conclusion
    assert action["status"].startswith("blocked_")


def test_html_audit_requires_utf8_offline_resources_and_valid_links(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.html"
    source = tmp_path / "source.html"
    target.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body><section id="detail">Détail</section></body></html>',
        encoding="utf-8",
    )
    source.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body><a href="target.html#detail">Ouvrir</a></body></html>',
        encoding="utf-8",
    )
    result = final._validate_html(source, validate_navigation=True)
    assert result["external_resource_count"] == 0
    assert result["checked_local_navigation_link_count"] == 1

    source.write_text(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<script src="https://example.invalid/x.js"></script></head></html>',
        encoding="utf-8",
    )
    with pytest.raises(final.FinalAssemblyError, match="Ressource distante"):
        final._validate_html(source, validate_navigation=True)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (
            "<!doctype html><html><body>Sans déclaration</body></html>",
            "charset",
        ),
        (
            '<!doctype html><html><head><meta charset="utf-8"></head>'
            '<body><img src="image-locale.png"></body></html>',
            "non embarquée",
        ),
        (
            '<!doctype html><html><head><meta charset="utf-8"></head>'
            "<body>caf\u00c3\u00a9</body></html>",
            "corrompu",
        ),
    ],
)
def test_html_audit_rejects_missing_charset_nonembedded_media_and_mojibake(
    tmp_path: Path,
    document: str,
    message: str,
) -> None:
    page = tmp_path / "page.html"
    page.write_text(document, encoding="utf-8")
    with pytest.raises(final.FinalAssemblyError, match=message):
        final._validate_html(page, validate_navigation=False)


def test_cli_contract_exposes_all_final_inputs() -> None:
    args = final.parse_args(
        [
            "--network-final-dir",
            "network",
            "--network-boundary-audit-dir",
            "network-boundary",
            "--component-021081-final-dir",
            "component",
            "--action-selection-final-dir",
            "actions",
            "--observed-dir",
            "observed",
            "--scope-dir",
            "scope",
            "--action-audit-dir",
            "action-audit",
            "--supplier-source-audit-dir",
            "source-audit",
            "--network-map-html",
            "map.html",
            "--service-landscape-dir",
            "service",
            "--output-dir",
            "new-package",
        ]
    )
    assert args.service_landscape_dir == Path("service")
    assert args.network_boundary_audit_dir == Path("network-boundary")
    assert args.output_dir == Path("new-package")


def test_output_directory_cannot_be_nested_in_a_source(tmp_path: Path) -> None:
    component = tmp_path / "component"
    component.mkdir()
    with pytest.raises(final.FinalAssemblyError, match="dossier source"):
        final.build_final_package(
            network_final_dir=tmp_path / "network",
            network_boundary_audit_dir=tmp_path / "network-boundary",
            component_021081_final_dir=component,
            action_selection_final_dir=tmp_path / "actions",
            observed_dir=tmp_path / "observed",
            scope_dir=tmp_path / "scope",
            action_audit_dir=tmp_path / "action-audit",
            supplier_source_audit_dir=tmp_path / "source-audit",
            network_map_html=tmp_path / "map.html",
            output_dir=component / "new-package",
        )


def test_explicit_invalid_service_input_is_not_silently_omitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = {
        name: tmp_path / name
        for name in (
            "network",
            "component",
            "actions",
            "observed",
            "scope",
            "action-audit",
            "source-audit",
            "service",
        )
    }
    for root in roots.values():
        root.mkdir()
    monkeypatch.setattr(
        final,
        "_validate_component_package",
        lambda root: ({"schema_version": final.COMPONENT_SCHEMA}, root / "index.html"),
    )
    monkeypatch.setattr(
        final,
        "_validate_network_release",
        lambda *args: ({}, {}, {}, "envelope_service_top3_scoped"),
    )
    monkeypatch.setattr(
        final, "_validate_observed", lambda root: {"all_validation_checks_pass": True}
    )
    monkeypatch.setattr(final, "_validate_scope", lambda root: {"status": "complete"})
    monkeypatch.setattr(
        final,
        "_validate_manifest_outputs",
        lambda *args, **kwargs: {"status": "complete"},
    )
    monkeypatch.setattr(
        final, "_validate_html", lambda *args, **kwargs: {"sha256": "0" * 64}
    )
    with pytest.raises(final.FinalAssemblyError, match="Fichier JSON requis absent"):
        final.build_final_package(
            network_final_dir=roots["network"],
            network_boundary_audit_dir=tmp_path / "network-boundary",
            component_021081_final_dir=roots["component"],
            action_selection_final_dir=roots["actions"],
            observed_dir=roots["observed"],
            scope_dir=roots["scope"],
            action_audit_dir=roots["action-audit"],
            supplier_source_audit_dir=roots["source-audit"],
            network_map_html=tmp_path / "map.html",
            service_landscape_dir=roots["service"],
            output_dir=tmp_path / "new-package",
        )


def test_build_is_transactional_and_keeps_only_new_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = (
        "network",
        "network-boundary",
        "component",
        "actions",
        "observed",
        "scope",
        "action-audit",
        "source-audit",
    )
    roots = {name: tmp_path / name for name in names}
    for root in roots.values():
        root.mkdir()
    for name, filename in (
        ("network", "campaign_manifest.json"),
        ("network", "extension_interpretation_audit_manifest.json"),
        ("network", "scientific_promotion_controls.json"),
        ("network-boundary", "scientific_priority_boundary_audit.json"),
        ("component", "campaign_manifest.json"),
        ("actions", "action_selector_manifest.json"),
        ("observed", "manifest.json"),
        ("scope", "manifest.json"),
        ("action-audit", "manifest.json"),
        ("source-audit", "manifest.json"),
    ):
        _json(roots[name] / filename, {})
    network_artifact_hashes = {
        path.name: final._sha256(path)
        for path in roots["network"].iterdir()
        if path.is_file()
    }
    _json(
        roots["network"] / "scientific_overlay_manifest.json",
        {"artifact_file_sha256": network_artifact_hashes},
    )
    boundary_artifact_hashes = {
        path.name: final._sha256(path)
        for path in roots["network-boundary"].iterdir()
        if path.is_file()
    }
    _json(
        roots["network-boundary"] / "priority_boundary_audit_manifest.json",
        {"artifact_file_sha256": boundary_artifact_hashes},
    )
    component_html = roots["component"] / "index.html"
    component_html.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body id="component">Composant</body></html>',
        encoding="utf-8",
    )
    map_html = tmp_path / "map.html"
    map_html.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body id="map">Carte</body></html>',
        encoding="utf-8",
    )
    source_hashes_before = {
        path: final._sha256(path)
        for root in (*roots.values(),)
        for path in root.rglob("*")
        if path.is_file()
    }
    source_hashes_before[map_html] = final._sha256(map_html)

    monkeypatch.setattr(
        final,
        "_validate_component_package",
        lambda root: ({"schema_version": final.COMPONENT_SCHEMA}, component_html),
    )
    monkeypatch.setattr(
        final,
        "_validate_network_release",
        lambda root, boundary, actions: (
            {"status": "complete"},
            {
                "execution_integrity_pass": True,
                "causal_lot_pairing_integrity_pass": True,
                "causal_lot_attribution_available": False,
                "network_recovery_metric_status": "excluded_invalid_common_window",
            },
            {
                "selection_status": (
                    "service_nonseparation_group_action_candidates_only"
                )
            },
            "service_nonseparation_group_four_follow_up",
        ),
    )
    monkeypatch.setattr(
        final,
        "_validate_observed",
        lambda root: {"all_validation_checks_pass": True},
    )
    monkeypatch.setattr(final, "_validate_scope", lambda root: {"status": "complete"})
    monkeypatch.setattr(
        final,
        "_validate_manifest_outputs",
        lambda root, **kwargs: {"status": "complete"},
    )

    def fake_network_builder(**kwargs: object) -> dict[str, object]:
        output = Path(str(kwargs["output_html"]))
        links = (
            Path(str(kwargs["meeting_html"])),
            Path(str(kwargs["component_html"])),
            Path(str(kwargs["map_html"])),
        )
        output.write_text(
            '<!doctype html><html><head><meta charset="utf-8"></head><body>'
            + "".join(
                f'<a href="{final._relative_href(output, target)}">ouvrir</a>'
                for target in links
            )
            + "</body></html>",
            encoding="utf-8",
        )
        return {
            "stable_priority_count": 0,
            "priority_reporting_status": "priority_group_only",
            "input_status": "signed_scientific_overlay_and_audits_valid",
            "global_network_priority_robustness_evaluable": False,
            "actions_promoted": False,
            "genealogical_lot_detail_count": 1,
        }

    def fake_meeting_builder(**kwargs: object) -> dict[str, object]:
        assert Path(str(kwargs["network_screen_dir"])) == roots["network"]
        assert (
            Path(str(kwargs["network_priority_boundary_audit_dir"]))
            == roots["network-boundary"]
        )
        assert Path(str(kwargs["network_action_selection_dir"])) == roots["actions"]
        output = Path(str(kwargs["output_html"]))
        links = (
            Path(str(kwargs["network_risk_html"])),
            Path(str(kwargs["component_021081_html"])),
            Path(str(kwargs["network_map_html"])),
        )
        output.write_text(
            '<!doctype html><html><head><meta charset="utf-8"></head><body>'
            + "".join(
                f'<a href="{final._relative_href(output, target)}">ouvrir</a>'
                for target in links
            )
            + "</body></html>",
            encoding="utf-8",
        )
        return {
            "input_status": {
                "network_screen": final.meeting_dashboard.NETWORK_FROZEN_GROUP_STATE,
                "network_input_status": (
                    final.meeting_dashboard.FROZEN_NETWORK_INPUT_STATUS
                ),
                "network_priority_reporting_status": (
                    final.meeting_dashboard.NETWORK_FROZEN_GROUP_STATE
                ),
                "global_network_priority_robustness_evaluable": False,
                "network_recovery_metric_status": ("excluded_invalid_common_window"),
                "actions_ready_count": 0,
                "component_021081": "complete",
            },
            "presentation_profile": "meeting",
            "view_count": 3,
        }

    monkeypatch.setattr(
        final.network_dashboard, "build_network_dashboard", fake_network_builder
    )
    monkeypatch.setattr(
        final.meeting_dashboard,
        "build_industrial_supply_bilan_dashboard",
        fake_meeting_builder,
    )
    output = tmp_path / "new-final-package"
    result = final.build_final_package(
        network_final_dir=roots["network"],
        network_boundary_audit_dir=roots["network-boundary"],
        component_021081_final_dir=roots["component"],
        action_selection_final_dir=roots["actions"],
        observed_dir=roots["observed"],
        scope_dir=roots["scope"],
        action_audit_dir=roots["action-audit"],
        supplier_source_audit_dir=roots["source-audit"],
        network_map_html=map_html,
        output_dir=output,
    )
    assert Path(result["entrypoint_path"]).is_file()
    assert {path.name for path in output.iterdir()} == {
        final.MEETING_FILE,
        final.NETWORK_FILE,
        final.LAUNCHER_FILE,
        final.MANIFEST_FILE,
        final.MANIFEST_DIGEST_FILE,
    }
    package_manifest = json.loads(
        (output / final.MANIFEST_FILE).read_text(encoding="utf-8")
    )
    launcher = (output / final.LAUNCHER_FILE).read_text(encoding="utf-8")
    assert launcher.index("Commencer le rendez-vous") < launcher.index(
        "Approfondir seulement si nécessaire"
    )
    assert launcher.index("Approfondir seulement si nécessaire") < launcher.index(
        "Voir tous les résultats réseau"
    )
    for boundary in (
        "Sensibilité conditionnelle aux incidents fournisseurs",
        "exposition généalogique et écarts causaux appariés",
        "Lignes planifiées, masquage et limites de traçabilité",
        "ne sont attribuées à aucun fournisseur",
        "audit exploratoire séparé, pas la sélection finale de leviers",
        "sans unité monétaire et non comparables aux montants 2025",
        "n’est pas nécessairement causalement modifié",
        "aucun effet aval, client, coût ou action n’est démontré",
    ):
        assert boundary in launcher
    assert (
        package_manifest["release_checks"][
            "legacy_exploratory_component_or_network_embedded"
        ]
        is False
    )
    assert (
        package_manifest["release_checks"]["source_inputs_unchanged_during_build"]
        is True
    )
    assert "network_map/html" in package_manifest["consumed_input_files"]
    assert all(
        audit["utf8_declared"] for audit in package_manifest["html_audits"].values()
    )
    assert all(
        audit["path"] in {final.MEETING_FILE, final.NETWORK_FILE, final.LAUNCHER_FILE}
        for audit in package_manifest["html_audits"].values()
    )
    assert source_hashes_before == {
        path: final._sha256(path) for path in source_hashes_before
    }
    assert not list(tmp_path.glob(".new-final-package.staging-*"))

    def mutating_meeting_builder(**kwargs: object) -> dict[str, object]:
        built = fake_meeting_builder(**kwargs)
        map_html.write_text(
            map_html.read_text(encoding="utf-8") + "\n<!-- mutation -->",
            encoding="utf-8",
        )
        return built

    monkeypatch.setattr(
        final.meeting_dashboard,
        "build_industrial_supply_bilan_dashboard",
        mutating_meeting_builder,
    )
    failed_output = tmp_path / "failed-final-package"
    with pytest.raises(final.FinalAssemblyError, match="entrée a changé"):
        final.build_final_package(
            network_final_dir=roots["network"],
            network_boundary_audit_dir=roots["network-boundary"],
            component_021081_final_dir=roots["component"],
            action_selection_final_dir=roots["actions"],
            observed_dir=roots["observed"],
            scope_dir=roots["scope"],
            action_audit_dir=roots["action-audit"],
            supplier_source_audit_dir=roots["source-audit"],
            network_map_html=map_html,
            output_dir=failed_output,
        )
    assert not failed_output.exists()
    assert not list(tmp_path.glob(".failed-final-package.staging-*"))

    with pytest.raises(final.FinalAssemblyError, match="ne sera pas remplacé"):
        final.build_final_package(
            network_final_dir=roots["network"],
            network_boundary_audit_dir=roots["network-boundary"],
            component_021081_final_dir=roots["component"],
            action_selection_final_dir=roots["actions"],
            observed_dir=roots["observed"],
            scope_dir=roots["scope"],
            action_audit_dir=roots["action-audit"],
            supplier_source_audit_dir=roots["source-audit"],
            network_map_html=map_html,
            output_dir=output,
        )
