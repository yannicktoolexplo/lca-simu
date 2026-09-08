from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    industrial_supply_bilan_dashboard as dashboard,
    supplier_network_post_priority_extension_runner as extension_runner,
)
from etudecas.prototypes.scan_2027_risk_control.industrial_supply_bilan_dashboard import (
    MAX_HTML_BYTES,
    NETWORK_PRESELECTION_STATE,
    NETWORK_STABILIZED_STATE,
    _component_has_exploratory_provenance,
    _component_masking_evidence,
    _meeting_opening_block,
    _regime_svg,
    build_industrial_supply_bilan_dashboard,
)


def _json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _inputs(
    root: Path,
    *,
    complete_optional: bool,
    include_action_audit: bool = True,
    include_source_audit: bool = True,
) -> dict[str, Path]:
    observed = root / "observed"
    scope = root / "supplier_network_scope_audit_20260901_v8"
    service = root / "service"
    component = root / "component"
    network = root / "network"
    action = root / "action"
    source_audit = root / "source_audit"
    directories = [observed, scope, service, component, network]
    if include_action_audit:
        directories.append(action)
    if include_source_audit:
        directories.append(source_audit)
    for directory in directories:
        directory.mkdir(parents=True)

    _json(observed / "manifest.json", {"all_validation_checks_pass": True})
    _csv(
        observed / "observed_ca_product_summary_2025.csv",
        [
            {
                "product_code": "268091",
                "ca_delivered_source_value": 21_000_000,
                "ca_lost_positive_only_source_value": 1_600_000,
                "delivered_share_of_raw_potential": 0.929,
                "days_with_lost_signal": 179,
            },
            {
                "product_code": "268967",
                "ca_delivered_source_value": 22_400_000,
                "ca_lost_positive_only_source_value": 1_080_000,
                "delivered_share_of_raw_potential": 0.954,
                "days_with_lost_signal": 76,
            },
        ],
    )
    monthly = []
    for product, offset in (("268091", 0.0), ("268967", 0.02)):
        for month in range(1, 13):
            monthly.append(
                {
                    "product_code": product,
                    "month": f"2025-{month:02d}",
                    "delivered_share_of_raw_potential": 0.80 + offset + month / 100,
                }
            )
    _csv(observed / "observed_ca_monthly_2025.csv", monthly)
    _csv(
        observed / "observed_stock_value_summary_2025.csv",
        [
            {
                "series_id": series,
                "minimum_stock_value_source": 100_000 * index,
                "mean_stock_value_source": 150_000 * index,
                "maximum_stock_value_source": 210_000 * index,
                "last_stock_value_source": 170_000 * index,
            }
            for index, series in enumerate(
                (
                    "component_stock_cos",
                    "component_stock_pharma",
                    "finished_goods_stock_268091",
                    "finished_goods_stock_268967",
                ),
                1,
            )
        ],
    )
    _csv(
        observed / "projected_finished_goods_shortage_summary.csv",
        [
            {"product_code": "268091", "snapshot_year": 2025, "snapshot_count": 12, "nonzero_snapshot_count": 4, "maximum_projected_shortage_weeks": 3, "first_nonzero_year_week": "2025|05", "last_nonzero_year_week": "2025|18"},
            {"product_code": "268091", "snapshot_year": 2026, "snapshot_count": 20, "nonzero_snapshot_count": 0, "maximum_projected_shortage_weeks": 0},
            {"product_code": "268967", "snapshot_year": 2025, "snapshot_count": 12, "nonzero_snapshot_count": 0, "maximum_projected_shortage_weeks": 0},
            {"product_code": "268967", "snapshot_year": 2026, "snapshot_count": 20, "nonzero_snapshot_count": 18, "maximum_projected_shortage_weeks": 11, "first_nonzero_year_week": "2026|09", "last_nonzero_year_week": "2026|26"},
        ],
    )
    _csv(
        observed / "supplier_risk_prediction_readiness.csv",
        [
            {"minimum_field": "purchase_order_id", "availability_in_current_2025_bundle": "MISSING_OR_NOT_LINKED"},
            {"minimum_field": "actual_receipt_date", "availability_in_current_2025_bundle": "MISSING_OR_NOT_LINKED"},
        ],
    )

    scope_manifest = {
        "status": "complete",
        "lane_count": 33,
        "priority_lane_count": 24,
        "item_site_count": 22,
        "single_source_item_site_count": 16,
        "multisource_item_site_count": 6,
        "multisource_only_one_supplier_evidenced_count": 3,
        "multisource_no_supplier_evidenced_count": 1,
        "observed_order_row_count": 52,
        "purchase_order_rows_excluded_from_exact_lanes": 30,
        "purchase_order_suppliers_excluded_from_exact_lanes": 11,
        "purchase_order_items_excluded_from_exact_lanes": 10,
        "purchase_order_rows_with_unmapped_division": 16,
        "purchase_order_rows_uom_normalized": 14,
        "counts_by_evidence_status": {
            "simulated_and_orderbook": 8,
            "simulated_only": 10,
            "orderbook_only": 6,
            "unexercised": 9,
        },
    }
    _json(scope / "manifest.json", scope_manifest)
    lanes = []
    for index in range(18):
        product = "268091" if index < 11 else "268967"
        item = ("001848", "001893", "055703")[index - 15] if index >= 15 else f"A{index:03d}"
        lanes.append(
            {
                "supplier_id": f"SDC-V{index % 16:03d}",
                "evidence_status": "simulated_and_orderbook" if index < 8 else "simulated_only",
                "baseline_positive_flow": True,
                "is_sole_structural_source": index < 15,
                "item_id": f"item:{item}",
                "downstream_products": product,
            }
        )
    for index in range(15):
        lanes.append(
            {
                "supplier_id": f"SDC-X{index:03d}",
                "evidence_status": "orderbook_only" if index < 6 else "unexercised",
                "baseline_positive_flow": False,
                "is_sole_structural_source": False,
                "item_id": f"item:X{index}",
                "downstream_products": "268091",
            }
        )
    _csv(scope / "supplier_lane_scope.csv", lanes)
    _csv(scope / "supplier_item_source_coverage.csv", [{"item_id": "item:A000", "source_coverage_status": "sole_source_evidenced"}])

    _json(service / "campaign_manifest.json", {"status": "complete"})
    _csv(
        service / "worst_cases.csv",
        [
            {
                "chain_id": "338929_m1810_268091",
                "mechanism": "intermittent_delay",
                "mechanism_value": 180,
                "target_product_id": "268091",
                "n_seeds": 10,
                "product_on_due_date_proxy_mean": 0.51,
                "product_on_due_date_proxy_p05": 0.46,
                "worst_rank_within_chain": 1,
            },
            {
                "chain_id": "344135_m1430_268967",
                "mechanism": "lead_extra",
                "mechanism_value": 180,
                "target_product_id": "268967",
                "n_seeds": 10,
                "product_on_due_date_proxy_mean": 0.65,
                "product_on_due_date_proxy_p05": 0.59,
                "worst_rank_within_chain": 1,
            },
        ],
    )
    _csv(service / "scenario_summary.csv", [{"scenario_id": "baseline_nominal"}])

    order_audit = {
        "order_count": 23,
        "quantity_kg": 1_320_000,
        "physical_delivery_day_min": 6,
        "physical_delivery_day_max": 139,
        "usable_day_min": 112,
        "usable_day_max": 261,
        "supplier_rows": [
            {"supplier_id": "SDC-VD0960508A", "order_count": 9, "quantity_kg": 820_000},
            {"supplier_id": "SDC-VD0949099A", "order_count": 8, "quantity_kg": 300_000},
            {"supplier_id": "SDC-VD0972460A", "order_count": 3, "quantity_kg": 100_000},
            {"supplier_id": "SDC-VD0975221A", "order_count": 3, "quantity_kg": 100_000},
        ],
    }
    _json(component / "observed_order_book_audit.json", order_audit)
    if complete_optional:
        _json(
            component / "campaign_manifest.json",
            {
                "status": "exploratory_complete",
                "claim_status": "exploratory",
                "orchestrator_sha_at_launch": "orchestrator_sha_at_launch_unknown",
                "unit_validation": "unit_validation_pending",
                "artifact_provenance": "consolidated_multi_provenance",
            },
        )
        _json(
            component / "future_autonomous_page_payload.json",
            {
                "observed_stock_masking_audit": {
                    "physical_cover_days_at_simulated_average_consumption": 3194,
                    "observed_stock_multiple_of_horizon_consumption": 4.4,
                },
                "intermediate_773474_masking_audit": {
                    "released_268967_lot_count": 29,
                    "approx_horizon_need_g": 30_182_579.4,
                    "opening_stock_total_g": 24_193_000,
                    "horizon_773474_production_g": 28_800_000,
                    "stock_multiple_of_horizon_need": 0.8015550851164166,
                    "stock_plus_production_multiple_of_horizon_need": 1.7557478868091705,
                    "021081_stock_multiple_of_horizon_intermediate_consumption": 4.436,
                    "021081_order_book_multiple_of_horizon_intermediate_consumption": 5.127,
                },
                "state_regime_effects": [
                    {
                        "state_regime": "observed_2025",
                        "target_cover_days": "",
                        "tested_stress_configurations": 90,
                        "configurations_with_simulated_downstream_product_effect": 0,
                    },
                    {
                        "state_regime": "prospective_90d_cover",
                        "target_cover_days": 90,
                        "tested_stress_configurations": 20,
                        "configurations_with_simulated_downstream_product_effect": 7,
                    },
                ],
            },
        )
        _json(
            network / "campaign_manifest.json",
            {
                "status": "complete",
                "mode": "full",
                "final_top3_conclusion_status": "top3_final_confirme",
                "confirmation_seed_count": 10,
                "failure_mode_summary_evidence_stage": "screening_1_realisation",
            },
        )
        ranking = []
        for rank, supplier in enumerate(
            ("SDC-AAA", "SDC-BBB", "SDC-CCC", "SDC-DDD", "SDC-EEE"), 1
        ):
            ranking.append(
                {
                    "supplier_id": supplier,
                    "supplier_sensitivity_rank": rank,
                    "worst_item_id": f"item:I{rank}",
                    "worst_target_product_id": "268091",
                    "worst_failure_mode": "transport_delay",
                    "worst_service_delta": -0.1 * rank,
                }
            )
        _csv(network / "supplier_sensitivity_ranking.csv", ranking)
        _csv(
            network / "confirmed_top3_stability.csv",
            [
                {
                    "supplier_id": row["supplier_id"],
                    "aggregate_confirmation_rank": row["supplier_sensitivity_rank"],
                    "confirmation_seed_count": 10,
                    "top3_presence_seed_count": 10,
                }
                for row in ranking[:3]
            ],
        )
        _csv(
            network / "failure_mode_sensitivity_summary.csv",
            [
                {"failure_mode": "transport_delay", "failure_mode_sensitivity_rank": 1, "worst_service_delta": -0.3},
                {"failure_mode": "quality_hold", "failure_mode_sensitivity_rank": 2, "worst_service_delta": -0.2},
            ],
        )
    else:
        _json(component / "campaign_manifest.json", {"status": "running"})
        _json(network / "campaign_manifest.json", {"status": "running", "mode": "full"})

    if include_action_audit:
        _json(action / "manifest.json", {"status": "complete"})
        _csv(
            action / "controllable_action_lever_audit.csv",
            [
                {
                    "record_type": "tested_lever",
                    "failure_mode": "transport_delay",
                    "lever_id": "expedited_transport",
                    "customer_exposure_seeds": 2,
                    "total_seeds": 10,
                    "mean_days_recovered_exposed": 16,
                    "mean_remaining_impact_pct_exposed": 0,
                    "mean_incremental_cost_model_units": 33531.95,
                    "result_class": "recommended_if_physical_transport",
                },
                {
                    "record_type": "tested_lever",
                    "failure_mode": "transport_delay",
                    "lever_id": "replanning",
                    "customer_exposure_seeds": 2,
                    "total_seeds": 10,
                    "mean_days_recovered_exposed": -11.5,
                    "mean_remaining_impact_pct_exposed": 442.3,
                    "mean_incremental_cost_model_units": 2741.91,
                    "result_class": "counterproductive_proxy",
                },
                {
                    "record_type": "tested_lever",
                    "failure_mode": "quality_hold",
                    "lever_id": "expedited_transport",
                    "customer_exposure_seeds": 9,
                    "total_seeds": 10,
                    "mean_days_recovered_exposed": 94.1,
                    "mean_remaining_impact_pct_exposed": 28.8,
                    "mean_incremental_cost_model_units": 402351.78,
                    "result_class": "useful_post_release_not_quality_solution",
                },
                {
                    "record_type": "tested_lever",
                    "failure_mode": "quality_hold",
                    "lever_id": "combined_response",
                    "customer_exposure_seeds": 9,
                    "total_seeds": 10,
                    "mean_days_recovered_exposed": 129,
                    "mean_remaining_impact_pct_exposed": 16.9,
                    "mean_incremental_cost_model_units": 4880627.32,
                    "result_class": "promising_bundle_not_ready",
                },
                {
                    "record_type": "tested_lever",
                    "failure_mode": "quality_hold",
                    "lever_id": "targeted_stock",
                    "result_class": "ineffective_response_configuration",
                },
                {
                    "record_type": "tested_lever",
                    "failure_mode": "transport_delay",
                    "lever_id": "second_supplier_proxy",
                    "result_class": "invalid_as_real_second_supplier",
                },
                *[
                    {
                        "record_type": "mode_recommendation",
                        "failure_mode": mode,
                        "lever_id": "mode_recommendation",
                        "result_class": "conditional_recommendation",
                    }
                    for mode in (
                        "transport_delay",
                        "supply_unavailability",
                        "quality_hold",
                        "quality_yield_loss",
                    )
                ],
            ],
        )

    if include_source_audit:
        _json(
            source_audit / "manifest.json",
            {
                "status": "complete",
                "summary": {
                    "location_external_account_count": 27,
                    "direct_product_fia_external_supplier_count": 23,
                    "upstream_021081_fia_external_supplier_count": 4,
                    "all_fia_external_supplier_count": 27,
                    "all_fia_external_with_location_count": 26,
                },
            },
        )

    return {
        "observed": observed,
        "scope": scope,
        "service": service,
        "component": component,
        "network": network,
        "action": action,
        "source_audit": source_audit,
    }


def _build(
    root: Path,
    *,
    complete_optional: bool,
    include_action_audit: bool = True,
    include_source_audit: bool = True,
    include_component_html: bool = False,
    include_network_risk_html: bool = False,
) -> tuple[Path, dict[str, object]]:
    inputs = _inputs(
        root / "inputs",
        complete_optional=complete_optional,
        include_action_audit=include_action_audit,
        include_source_audit=include_source_audit,
    )
    detail = root / "pages" / "detail.html"
    lots = root / "pages" / "lots.html"
    network_map = root / "pages" / "map.html"
    component_html = root / "pages" / "component_021081.html"
    network_risk_html = root / "pages" / "network_risk.html"
    page_paths = [detail, lots, network_map]
    if include_component_html:
        page_paths.append(component_html)
    if include_network_risk_html:
        page_paths.append(network_risk_html)
    for path in page_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<!doctype html>", encoding="utf-8")
    output = root / "artifact" / "BILAN_SUPPLY.html"
    result = build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=inputs["network"],
        action_audit_dir=inputs["action"] if include_action_audit else None,
        supplier_source_audit_dir=(
            inputs["source_audit"] if include_source_audit else None
        ),
        sensitivity_html=detail,
        component_021081_html=component_html if include_component_html else None,
        network_risk_html=(
            network_risk_html if include_network_risk_html else None
        ),
        three_views_html=lots,
        network_map_html=network_map,
        output_html=output,
    )
    return output, result


def _frozen_network_api_payload(*, envelope_released: bool) -> dict[str, object]:
    suppliers = ("SDC-AAA", "SDC-BBB", "SDC-CCC", "SDC-DDD", "SDC-EEE")
    metrics = (
        "horizon_on_due_service_delta",
        "worst_rolling_28d_on_due_delta",
        "incremental_backlog_days_per_requested_unit",
        "released_production_shortfall_ratio",
    )

    def metric_audit(metric_key: str) -> dict[str, object]:
        return {
            "metric_key": metric_key,
            "metric_priority_set_release_pass": envelope_released,
            "released_priority_supplier_ids": (
                list(suppliers[:3]) if envelope_released else []
            ),
        }

    metric_audits = [metric_audit(metric_key) for metric_key in metrics]
    family_audits = {
        failure_mode: {
            "metric_priority_audits": [
                metric_audit(metric_key) for metric_key in metrics
            ]
        }
        for failure_mode in ("transport_delay", "supply_availability")
    }
    scope = dashboard.network_results.boundary_contract.SUPPLIER_ENVELOPE_SCOPE
    rankings: list[dict[str, object]] = []
    base_values = {
        "horizon_on_due_service_delta": -0.34,
        "worst_rolling_28d_on_due_delta": -0.48,
        "incremental_backlog_days_per_requested_unit": 2.4,
        "released_production_shortfall_ratio": 0.17,
    }
    for metric_key in metrics:
        for index, supplier in enumerate(suppliers):
            base = base_values[metric_key]
            value = (
                base + index * 0.025
                if base < 0
                else max(0.0, base - index * 0.11)
            )
            rankings.append(
                {
                    "aggregation_scope": scope,
                    "metric_key": metric_key,
                    "descriptive_metric_rank": index + 1,
                    "supplier_id": supplier,
                    "metric_value": value,
                    "driver_chain_id": f"voie-{index + 1:02d}",
                    "driver_failure_mode": (
                        "transport_delay" if index % 2 == 0 else "supply_availability"
                    ),
                    "top3_presence_seed_count": 30 - index,
                }
            )
    effects = [
        {
            "aggregation_level": "supplier_any_confirmed_scenario",
            "supplier_id": supplier,
            "client_effect_seed_count": 24 - index,
            "production_only_effect_seed_count": 8 + index,
            "upstream_absorbed_seed_count": 4 + index,
            "no_measurable_effect_seed_count": 6 + index,
            "inactive_window_seed_count": index,
        }
        for index, supplier in enumerate(suppliers)
    ]
    stable = (
        [
            row
            for row in rankings
            if row["metric_key"] == "horizon_on_due_service_delta"
            and row["supplier_id"] in suppliers[:3]
        ]
        if envelope_released
        else []
    )
    controls = {
        "execution_integrity_pass": True,
        "multi_lane_common_cause_execution_integrity_pass": True,
        "temporal_execution_integrity_pass": True,
        "four_cause_execution_integrity_pass": True,
        "causal_lot_pairing_integrity_pass": True,
        "global_priority_temporal_robustness_evaluable": False,
        "global_four_cause_priority_robustness_evaluable": False,
        "global_network_priority_robustness_evaluable": False,
        "network_recovery_metric_used_in_any_gate_or_ranking": False,
        "promotion_allowed": False,
        "network_recovery_metric_status": "excluded_invalid_common_window",
    }
    return {
        "manifest": {"days": 720},
        "ranking": [],
        "lanes": [],
        "modes": [],
        "stable_priorities": stable,
        "priority_group_supplier_ids": (
            [] if envelope_released else list(suppliers)
        ),
        "priority_reporting_status": (
            "envelope_service_top3_released"
            if envelope_released
            else "priority_group_only"
        ),
        "input_status": "signed_scientific_overlay_and_audits_valid",
        "legacy_priority_flags_ignored": True,
        "legacy_extension_release_aliases_ignored": True,
        "boundary": {
            "audit": {
                "metric_priority_audits": metric_audits,
                "failure_mode_specific_metric_priority_audits": family_audits,
            },
            "rankings": rankings,
            "effects": effects,
        },
        "extension": {"controls": controls},
        "causal_released": True,
        "lot_exposure": [
            {
                "case_id": "case-1",
                "root_lot_count": 3,
                "exposed_descendant_lot_count": 12,
            },
            {
                "case_id": "case-2",
                "root_lot_count": 2,
                "exposed_descendant_lot_count": 7,
            },
        ],
        "causal_pairs": [
            {
                "case_id": "case-1",
                "unique_matched_technical_key_count": 11,
                "actual_difference_row_count": 4,
            },
            {
                "case_id": "case-2",
                "unique_matched_technical_key_count": 9,
                "actual_difference_row_count": 2,
            },
        ],
        "causal_detail": [],
        "actions": {
            "manifest": {},
            "released": False,
            "selected": [],
            "blocked": [],
            "forced_not_promoted": True,
            "input_was_supplied_but_ignored": True,
        },
    }


def _build_frozen_meeting(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    envelope_released: bool,
    payload: dict[str, object] | None = None,
) -> tuple[Path, dict[str, object], dict[str, Path]]:
    inputs = _inputs(root / "inputs", complete_optional=True)
    overlay = root / "frozen-overlay"
    boundary = root / "frozen-boundary"
    actions = root / "frozen-actions"
    for directory in (overlay, boundary, actions):
        directory.mkdir(parents=True)
    supplied_payload = payload or _frozen_network_api_payload(
        envelope_released=envelope_released
    )
    called: dict[str, object] = {}

    def fake_load(
        artifact_dir: Path,
        *,
        priority_boundary_audit_dir: Path,
        action_selection_dir: Path | None = None,
    ) -> dict[str, object]:
        called.update(
            {
                "artifact_dir": artifact_dir,
                "priority_boundary_audit_dir": priority_boundary_audit_dir,
                "action_selection_dir": action_selection_dir,
            }
        )
        return supplied_payload

    monkeypatch.setattr(dashboard.network_results, "load_network_results", fake_load)
    output = root / "artifact" / "meeting-frozen.html"
    result = dashboard.build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=overlay,
        network_priority_boundary_audit_dir=boundary,
        network_action_selection_dir=actions,
        action_audit_dir=inputs["action"],
        supplier_source_audit_dir=inputs["source_audit"],
        output_html=output,
        presentation_profile="meeting",
    )
    assert called == {
        "artifact_dir": overlay,
        "priority_boundary_audit_dir": boundary,
        "action_selection_dir": actions,
    }
    return output, result, inputs


def _consolidated_network_fixture(
    root: Path,
    *,
    failed_gate: str | None,
) -> tuple[dict[str, Path], Path, dict[str, str]]:
    inputs = _inputs(root / "inputs", complete_optional=True)
    source = inputs["network"]
    scientific_gates = {
        "baseline_both_products_on_due_at_least_95_all_seeds_pass": True,
        "all_metric_rows_valid_pass": True,
        "j0_state_hash_pairing_100pct_pass": True,
        "input_graph_hash_pairing_100pct_pass": True,
        "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": True,
        "all_release_gates_pass": True,
    }
    if failed_gate == "source_active_flow":
        scientific_gates[
            "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass"
        ] = False
        scientific_gates["all_release_gates_pass"] = False
    _json(
        source / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "campaign_signature": "network-v2-fixture",
            "confirmation_seed_count": 30,
            "rank3_rank4_interval_separated": True,
            "failure_mode_summary_evidence_stage": "screening_1_realisation",
            "scientific_release_gates": scientific_gates,
        },
    )
    _csv(
        source / "confirmed_top3_stability.csv",
        [
            {
                "supplier_id": f"SDC-{name}",
                "aggregate_confirmation_rank": rank,
                "confirmation_seed_count": 30,
                "top3_presence_seed_count": 29,
            }
            for rank, name in enumerate(("AAA", "BBB", "CCC"), 1)
        ],
    )
    source_hashes_before = {
        path.relative_to(source).as_posix(): extension_runner._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }
    source_manifest_sha256 = extension_runner._sha256(
        source / "campaign_manifest.json"
    )
    runner_dir = root / "extension-results"
    runner_dir.mkdir()
    runner_signature = "extension-runner-v2-fixture"
    plan_signature = "extension-plan-v2-fixture"
    _json(
        runner_dir / extension_runner.RUNNER_MANIFEST,
        {
            "status": "complete",
            "mode": "full",
            "runner_signature": runner_signature,
            "plan_signature": plan_signature,
            "source_dir": str(source.resolve()),
            "source_campaign_manifest_sha256": source_manifest_sha256,
        },
    )
    extension_files = {
        "multi_lane_supplier_common_cause": (
            "multi_lane_supplier_common_cause_manifest.json"
        ),
        "temporal_robustness": "temporal_robustness_manifest.json",
        "four_business_cause_confirmation": (
            "priority_four_business_causes_manifest.json"
        ),
        "causal_lot_attribution": "causal_lot_attribution_manifest.json",
    }
    for gate, filename in extension_files.items():
        _json(
            runner_dir / filename,
            {
                "status": "complete",
                "release_gate_pass": failed_gate != gate,
                "runner_signature": runner_signature,
                "plan_signature": plan_signature,
                "source_campaign_manifest_sha256": source_manifest_sha256,
            },
        )
    for filename in (
        "multi_lane_supplier_common_cause_summary.csv",
        "temporal_robustness_summary.csv",
        "priority_four_business_causes_summary.csv",
        "causal_lot_attribution_summary.csv",
        "causal_lot_attribution_detail.csv",
    ):
        _csv(runner_dir / filename, [{"fixture_status": "complete"}])
    _csv(
        runner_dir / "lot_genealogical_exposure_summary.csv",
        [
            {
                "case_id": "case-lot-fixture",
                "seed": 340282,
                "failure_mode": "transport_delay",
                "root_lot_count": 1,
                "exposed_descendant_lot_count": 1,
                "exposed_row_count": 2,
                "missing_genealogy_lot_count": 0,
                "descendant_quantity_is_upper_bound": True,
                "causal_delay_or_loss_claimed_from_genealogy": False,
            }
        ],
    )
    _csv(
        runner_dir / "lot_genealogical_exposure_detail.csv",
        [
            {
                "case_id": "case-lot-fixture",
                "seed": 340282,
                "failure_mode": "transport_delay",
                "lot_id": "simulated-root-lot",
                "exposure_role": "risk_tagged_usable_receipt_root",
                "event_id": "receipt-event",
                "event_type": "usable_receipt",
                "node_id": "M-1810",
                "item_id": "item:338929",
                "day": 45,
                "qty": 100,
                "uom": "UN",
                "shipment_id": "shipment-1",
                "production_campaign_id": "",
                "source_id": "supplier-fixture",
                "descendant_quantity_is_exposure_upper_bound": True,
                "causal_delay_or_loss_claimed": False,
                "counterfactual_entity_identity_validated": False,
                "industrial_lot_number_claimed": False,
                "lot_identifier_semantics": (
                    "identifiant_technique_simule_pas_numero_lot_industriel"
                ),
            },
            {
                "case_id": "case-lot-fixture",
                "seed": 340282,
                "failure_mode": "transport_delay",
                "lot_id": "simulated-descendant-lot",
                "exposure_role": "genealogical_descendant",
                "event_id": "production-event",
                "event_type": "production_release",
                "node_id": "M-1810",
                "item_id": "268091",
                "day": 80,
                "qty": 80,
                "uom": "UN",
                "shipment_id": "",
                "production_campaign_id": "campaign-1",
                "source_id": "simulated-root-lot",
                "descendant_quantity_is_exposure_upper_bound": True,
                "causal_delay_or_loss_claimed": False,
                "counterfactual_entity_identity_validated": False,
                "industrial_lot_number_claimed": False,
                "lot_identifier_semantics": (
                    "identifiant_technique_simule_pas_numero_lot_industriel"
                ),
            },
        ],
    )
    runner_hashes_before = {
        path.relative_to(runner_dir).as_posix(): extension_runner._sha256(path)
        for path in runner_dir.rglob("*")
        if path.is_file()
    }
    consolidated = extension_runner.consolidate_dashboard_network_artifact(
        source_dir=source,
        runner_dir=runner_dir,
        output_dir=root / "consolidated-network",
    )
    assert not (consolidated / "cases").exists()
    assert source_hashes_before == {
        path.relative_to(source).as_posix(): extension_runner._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }
    assert runner_hashes_before == {
        path.relative_to(runner_dir).as_posix(): extension_runner._sha256(path)
        for path in runner_dir.rglob("*")
        if path.is_file()
    }
    return inputs, consolidated, source_hashes_before


def test_compact_offline_three_view_dashboard_masks_partial_results(tmp_path: Path) -> None:
    output, result = _build(tmp_path, complete_optional=False)
    document = output.read_text(encoding="utf-8")

    assert result["view_count"] == 3
    assert result["external_resources"] == 0
    assert result["input_status"]["component_021081"] == "in_progress"
    assert result["input_status"]["network_screen"] == "in_progress"
    assert result["input_status"]["action_audit"] == "complete"
    assert result["input_status"]["supplier_source_audit"] == "complete"
    assert len(re.findall(r'<section id="view-[^"]+"', document)) == 3
    assert document.count("<svg") >= 5
    assert output.stat().st_size < MAX_HTML_BYTES
    assert "En cours" in document
    assert "cette page ne publie pas de « top 3 »" in document
    assert "Deux protocoles, pas une contradiction" in document
    assert "30 autres lignes sur les 82" in document
    assert "11 fournisseurs et 10 articles" in document
    assert "division 1820" in document
    assert "14 ont été converties" in document
    assert "15/18 sont structurellement mono-source" in document
    assert "L'annuaire localise 27 comptes externes" in document
    assert "Les FIA de 268091/268967 en décrivent 23" in document
    assert "celle de 773474 ajoute 4 sources de 021081" in document
    assert "La jointure exacte avec la localisation couvre 26/27 fournisseurs" in document
    assert "aucun OTIF" in document
    assert "Les délais FIA sont prévisionnels" in document
    assert 'title="Audit de couverture réseau v8"' in document
    assert "ne calibrent pas exactement un niveau de service à 80 % ou 93 %" in document
    assert "des courbes identiques ne sont pas des confirmations indépendantes" in document
    assert "demande servie à la date attendue dans le modèle" in document
    assert "5e percentile" not in document
    assert "46,0 %" not in document
    assert "59,0 %" not in document
    assert "aucun cas défavorable chiffré" in document
    assert "les risques endogènes dépendant de l'état" in document
    assert "le pilotage automatique en boucle fermée" in document
    assert "ne constitue pas une prévision fournisseur" in document
    assert "state-dependent" not in document
    assert "closed-loop" not in document
    assert "Alertes du planning disponibles" in document
    assert all(pair in document for pair in ("268091 · 2025", "268091 · 2026", "268967 · 2025", "268967 · 2026"))
    assert "18 photos sur 20 portent une alerte" in document
    assert "11 semaines projetées" in document
    assert "de 2026|09 à 2026|26" in document
    assert "elles ne sont donc pas sommables" in document
    assert "pas non plus attribuées à un fournisseur" in document
    assert "ANCIENS ESSAIS SIMULÉS — AUCUNE ACTION VALIDÉE" in document
    assert "FAMILLES D'ACTIONS À VÉRIFIER AVEC LES ÉQUIPES" in document
    assert "deux anciens scénarios de cascade" in document
    assert "pas de l'analyse réseau finale ni du rejeu des 23 lignes planifiées 021081" in document
    assert "33\u202f532" in document
    assert "indice de coût du modèle, sans unité monétaire" in document
    assert "ne sont ni des devis, ni comparables aux valeurs livrées ou non réalisées de 2025" in document
    assert "11,5 jours perdus" in document
    assert "−11,5 jours gagnés" not in document
    assert "ce n'est pas une fréquence industrielle" in document
    assert "Aucun levier n'est déclaré disponible ou validé opérationnellement" in document
    assert "Aucune action dédiée" in document
    assert "Famille d'action potentiellement pilotable" in document
    assert "Décision réellement pilotable" not in document
    assert "ce décalage physique-vers-disponible est un paramètre du modèle à valider" in document
    assert "pas un délai qualité observé" in document
    assert "€" not in document
    assert "source_row" not in document  # public wording stays plain French
    assert "ligne technique" in document
    lowered = document.lower()
    assert "<script src=" not in lowered
    assert "<link " not in lowered
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "fetch(" not in lowered
    assert "xmlhttprequest" not in lowered
    assert 'href="../pages/detail.html"' in document
    assert 'href="../pages/lots.html"' in document
    assert 'href="../pages/map.html"' in document
    assert "Rejeu détaillé des 23 lignes planifiées 021081" not in document
    assert "Ouvrir l&#x27;analyse détaillée des 18 voies actives" not in document
    assert "network_risk.html" not in document
    assert "des signaux calculés par le modèle, pas la cotation achats ou qualité interne" in document
    assert "demander sa grille réelle" in document
    assert "Grille interne fournisseur" in document
    assert "PPM ou rejets" in document
    assert "OTIF avec sa définition" in document
    assert "historique daté et règles de calcul" in document
    assert "Masquage à rechiffrer" in document
    assert "29 lots simulés" not in document
    assert "exposition généalogique" in document
    assert "Un lot exposé n'est pas nécessairement modifié par l'incident" in document
    assert "Pour conclure à un effet causal" in document
    assert "borne haute d'exposition" in document
    assert "La période de quarantaine est reconstruite" in document
    assert "statut natif du lot" in document
    assert "facteur 1 000" in document
    assert "ratio divisé par 1 000" in document
    assert "récurrence" not in document.lower()
    assert "probabilité" not in document.lower()


def test_optional_component_021081_page_is_linked_before_legacy_lot_views(tmp_path: Path) -> None:
    output, _ = _build(
        tmp_path,
        complete_optional=True,
        include_component_html=True,
    )
    document = output.read_text(encoding="utf-8")

    component_label = "Rejeu détaillé des 23 lignes planifiées 021081"
    legacy_label = "Parcours incidents et lots"
    assert 'href="../pages/component_021081.html"' in document
    assert component_label in document
    assert document.index(component_label) < document.index(legacy_label)


def test_optional_network_risk_page_is_linked_only_when_file_exists(tmp_path: Path) -> None:
    output, _ = _build(
        tmp_path,
        complete_optional=True,
        include_network_risk_html=True,
    )
    document = output.read_text(encoding="utf-8")

    assert 'href="../pages/network_risk.html"' in document
    assert "Ouvrir l&#x27;analyse détaillée des 18 voies actives" in document
    assert "sensibilité des 16 fournisseurs du réseau actif" in document


def test_source_audit_is_optional_and_incomplete_numbers_are_masked(tmp_path: Path) -> None:
    output, result = _build(
        tmp_path,
        complete_optional=False,
        include_source_audit=False,
    )
    document = output.read_text(encoding="utf-8")

    assert result["input_status"]["supplier_source_audit"] == "unavailable"
    assert "Limite des données fournisseur" in document
    assert "L'annuaire localise 27 comptes externes" not in document
    assert "26/27 fournisseurs" not in document

    inputs = _inputs(
        tmp_path / "running-inputs",
        complete_optional=False,
        include_source_audit=True,
    )
    _json(
        inputs["source_audit"] / "manifest.json",
        {
            "status": "running",
            "summary": {
                "location_external_account_count": 999,
                "direct_product_fia_external_supplier_count": 998,
                "upstream_021081_fia_external_supplier_count": 997,
                "all_fia_external_supplier_count": 996,
                "all_fia_external_with_location_count": 995,
            },
        },
    )
    running_output = tmp_path / "artifact" / "running-source-audit.html"
    running_result = build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=inputs["network"],
        action_audit_dir=inputs["action"],
        supplier_source_audit_dir=inputs["source_audit"],
        output_html=running_output,
    )
    running_document = running_output.read_text(encoding="utf-8")
    assert running_result["input_status"]["supplier_source_audit"] == "in_progress"
    assert "999 comptes externes" not in running_document
    assert "Limite des données fournisseur" in running_document


def test_completed_optional_campaigns_expose_only_interpretable_results(tmp_path: Path) -> None:
    output, result = _build(tmp_path, complete_optional=True)
    document = output.read_text(encoding="utf-8")

    assert result["input_status"]["component_021081"] == "complete"
    assert result["input_status"]["network_screen"] == NETWORK_PRESELECTION_STATE
    assert "Groupe prioritaire à approfondir" in document
    assert "Trois priorités simulées stabilisées" not in document
    assert all(name in document for name in ("AAA", "BBB", "CCC", "DDD", "EEE"))
    assert "Dix répétitions ne forment qu&#x27;une présélection" in document
    assert "18 voies × 4 modes × 2 intensités" in document
    assert "ni un classement confirmé des causes, ni une mesure de leur fréquence historique" in document
    assert "récurrence" not in document.lower()
    assert "probabilité" not in document.lower()
    assert "3\u202f194 jours de consommation du modèle" not in document
    assert "29 lots simulés" in document
    assert "30,182579 M G" in document
    assert "24,193 M G · 80,16 %" in document
    assert "28,8 M G" in document
    assert "1,756×" in document
    assert "4,436× · 5,127×" in document
    assert "Masquage à rechiffrer" not in document
    assert "Étude exploratoire complète" in document
    assert "les calculs et chiffres auditables restent visibles" in document
    assert "validation industrielle définitive" in document
    assert "conclusion industrielle définitive" not in document
    assert "7 sur 20" in document
    assert "chacune devient une réception technique simulée" in document
    assert "Aucun numéro de commande ou de lot industriel n&#x27;est reconstitué" in document
    assert "7 configurations sur 110" in document
    assert "jamais sur un score unique" in document


def test_completed_component_with_zero_effects_reports_masking_not_propagation(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path / "inputs", complete_optional=True)
    payload_path = inputs["component"] / "future_autonomous_page_payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    for row in payload["state_regime_effects"]:
        row["configurations_with_simulated_downstream_product_effect"] = 0
    _json(payload_path, payload)
    output = tmp_path / "artifact" / "zero-downstream-effect.html"

    build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=inputs["network"],
        action_audit_dir=inputs["action"],
        supplier_source_audit_dir=inputs["source_audit"],
        output_html=output,
    )
    document = output.read_text(encoding="utf-8")

    assert "Aucun effet aval démontré de 021081 vers 268967" in document
    assert "Dans les 110 configurations testées" in document
    assert "Les stocks, le carnet et la production intermédiaire du modèle ont masqué" in document
    assert "Cela ne prouve pas une résilience industrielle générale" in document
    assert "aucun effet client, coût ou action" in document
    assert "commence à laisser passer un incident" not in document


def test_component_regime_chart_names_each_modified_state_layer() -> None:
    rows = [
        {
            "state_regime": state,
            "target_cover_days": cover,
            "tested_stress_configurations": 3,
            "configurations_with_simulated_downstream_product_effect": 0,
        }
        for state, cover in (
            ("observed_2025", None),
            ("component_only_90d", 90),
            ("intermediate_stock_only_90d", 90),
            ("intermediate_production_only_90d", 90),
            ("joint_90d", 90),
        )
    ]

    chart = _regime_svg(rows)

    assert "Référence simulée · état du snapshot 2025" in chart
    assert "stock 021081 seul réduit à 90 j" in chart
    assert "stock 773474 seul réduit à 90 j" in chart
    assert "production 773474 seule limitée à 90 j" in chart
    assert "021081 + stock et production 773474 à 90 j" in chart
    assert "Hypothèse : 90 jours de couverture" not in chart


@pytest.mark.parametrize(
    "signal",
    [
        {"claim_status": "exploratory"},
        {"orchestrator_sha_at_launch": "orchestrator_sha_at_launch_unknown"},
        {"unit_validation": "unit_validation_pending"},
        {"artifact_provenance": "consolidated_multi_provenance"},
    ],
)
def test_component_provenance_signals_are_recognised(signal: dict[str, str]) -> None:
    assert _component_has_exploratory_provenance(
        {"manifest": {"status": "complete", **signal}, "payload": {}}
    )
    assert not _component_has_exploratory_provenance(
        {"manifest": {"status": "complete"}, "payload": {}}
    )


def test_component_masking_values_are_read_only_from_the_payload() -> None:
    fabricated_manifest_values = {
        "released_268967_lot_count": 999,
        "approx_horizon_need_g": 1,
    }
    assert not _component_masking_evidence(
        {
            "manifest": {
                "intermediate_773474_masking_audit": fabricated_manifest_values
            },
            "payload": {},
        }
    )
    assert _component_masking_evidence(
        {
            "manifest": {},
            "payload": {
                "intermediate_773474_masking_audit": fabricated_manifest_values
            },
        }
    ) == fabricated_manifest_values


def test_network_stabilized_state_requires_all_scientific_gates(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path / "inputs", complete_optional=True)
    network = inputs["network"]
    manifest = {
        "status": "complete",
        "mode": "full",
        "confirmation_seed_count": 30,
        "minimum_top3_presence_seed_count": 29,
        "rank3_rank4_interval_separated": True,
        "failure_mode_summary_evidence_stage": "screening_1_realisation",
        "scientific_release_gates": {
            "baseline_both_products_on_due_at_least_95_all_seeds_pass": True,
            "all_metric_rows_valid_pass": True,
            "j0_state_hash_pairing_100pct_pass": True,
            "input_graph_hash_pairing_100pct_pass": True,
            "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": True,
            "all_release_gates_pass": True,
        },
        "extensions_required": {
            "multi_lane_supplier_common_cause": {"pass": True, "complete": True},
            "temporal_robustness": {"pass": True, "complete": True},
            "four_business_cause_confirmation": {"pass": True, "complete": True},
            "causal_lot_attribution": {"pass": True, "complete": True},
        },
    }
    _json(network / "campaign_manifest.json", manifest)
    stability = [
        {
            "supplier_id": f"SDC-{name}",
            "aggregate_confirmation_rank": rank,
            "confirmation_seed_count": 30,
            "top3_presence_seed_count": 29,
            "rank3_rank4_interval_separated": True,
        }
        for rank, name in enumerate(("AAA", "BBB", "CCC"), 1)
    ]
    _csv(network / "confirmed_top3_stability.csv", stability)

    def render(name: str) -> tuple[dict[str, object], str]:
        output = tmp_path / "artifact" / name
        result = build_industrial_supply_bilan_dashboard(
            observed_dir=inputs["observed"],
            scope_dir=inputs["scope"],
            service_landscape_dir=inputs["service"],
            component_021081_dir=inputs["component"],
            network_screen_dir=network,
            action_audit_dir=inputs["action"],
            supplier_source_audit_dir=inputs["source_audit"],
            output_html=output,
        )
        return result, output.read_text(encoding="utf-8")

    stable_result, stable_document = render("stable.html")
    assert stable_result["input_status"]["network_screen"] == NETWORK_STABILIZED_STATE
    assert "Trois priorités simulées stabilisées" in stable_document
    assert "extensions multi-voies, temporelles et causales sur les lots" in stable_document
    assert "DDD" not in stable_document

    manifest["extensions_required"]["temporal_robustness"] = {
        "pass": True,
        "complete": False,
    }
    _json(network / "campaign_manifest.json", manifest)
    incomplete_result, incomplete_document = render("extension-not-complete.html")
    assert incomplete_result["input_status"]["network_screen"] == "groupe_prioritaire"
    assert "Priorités du test voie-par-voie à confirmer" in incomplete_document
    assert "Trois priorités simulées stabilisées" not in incomplete_document
    manifest["extensions_required"]["temporal_robustness"] = {
        "pass": True,
        "complete": True,
    }

    manifest["extensions_required"]["causal_lot_attribution"] = {
        "pass": False,
        "complete": False,
        "status": "required_not_available_genealogy_only",
    }
    _json(network / "campaign_manifest.json", manifest)
    extension_result, extension_document = render("missing-causal-lots.html")
    assert extension_result["input_status"]["network_screen"] == "groupe_prioritaire"
    assert "Priorités du test voie-par-voie à confirmer" in extension_document
    assert "preuve causale des lots touchés" in extension_document
    assert "Trois priorités simulées stabilisées" not in extension_document

    manifest["extensions_required"]["causal_lot_attribution"] = {
        "pass": True,
        "complete": True,
    }
    _json(network / "campaign_manifest.json", manifest)
    stability[2]["top3_presence_seed_count"] = 28
    _csv(network / "confirmed_top3_stability.csv", stability)
    presence_result, presence_document = render("insufficient-presence.html")
    assert presence_result["input_status"]["network_screen"] == "groupe_prioritaire"
    assert "Priorités du test voie-par-voie à confirmer" in presence_document

    stability[2]["top3_presence_seed_count"] = 29
    stability[2]["supplier_id"] = "SDC-BBB"
    _csv(network / "confirmed_top3_stability.csv", stability)
    duplicate_result, duplicate_document = render("duplicate-top3.html")
    assert duplicate_result["input_status"]["network_screen"] == "groupe_prioritaire"
    assert "Trois priorités simulées stabilisées" not in duplicate_document

    stability[2]["supplier_id"] = "SDC-ZZZ"
    _csv(network / "confirmed_top3_stability.csv", stability)
    mismatch_result, mismatch_document = render("mismatched-top3.html")
    assert mismatch_result["input_status"]["network_screen"] == "groupe_prioritaire"
    assert "Trois priorités simulées stabilisées" not in mismatch_document

    (network / "confirmed_top3_stability.csv").unlink()
    manifest["observed_minimum_top3_presence_seed_count"] = 29
    _json(network / "campaign_manifest.json", manifest)
    legacy_result, legacy_document = render("legacy-declared-presence.html")
    assert legacy_result["input_status"]["network_screen"] == "groupe_prioritaire"
    assert "Trois priorités simulées stabilisées" not in legacy_document


@pytest.mark.parametrize(
    ("failed_gate", "expected_state"),
    [
        (None, "groupe_prioritaire"),
        ("source_active_flow", "groupe_prioritaire"),
        ("multi_lane_supplier_common_cause", "groupe_prioritaire"),
        ("temporal_robustness", "groupe_prioritaire"),
        ("four_business_cause_confirmation", "groupe_prioritaire"),
        ("causal_lot_attribution", "groupe_prioritaire"),
    ],
)
def test_consolidated_network_artifact_is_the_real_dashboard_input_and_all_gates_apply(
    tmp_path: Path,
    failed_gate: str | None,
    expected_state: str,
) -> None:
    inputs, consolidated, source_hashes_before = _consolidated_network_fixture(
        tmp_path,
        failed_gate=failed_gate,
    )
    output = tmp_path / "rendered-fixture.html"
    result = build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=consolidated,
        action_audit_dir=inputs["action"],
        supplier_source_audit_dir=inputs["source_audit"],
        output_html=output,
    )
    document = output.read_text(encoding="utf-8")
    assert result["input_status"]["network_screen"] == expected_state
    if expected_state == NETWORK_STABILIZED_STATE:
        assert "Trois priorités simulées stabilisées" in document
        assert "Groupe prioritaire à approfondir" not in document
    else:
        assert "Priorités du test voie-par-voie à confirmer" in document
        assert "Trois priorités simulées stabilisées" not in document
    if failed_gate == "four_business_cause_confirmation":
        assert "confirmation des quatre causes métier" in document
    source = inputs["network"]
    assert source_hashes_before == {
        path.relative_to(source).as_posix(): extension_runner._sha256(path)
        for path in source.rglob("*")
        if path.is_file()
    }


def test_refuses_to_replace_existing_dashboard_without_force(tmp_path: Path) -> None:
    output, _ = _build(tmp_path, complete_optional=False)
    original = output.read_bytes()
    inputs = {
        key: tmp_path / "inputs" / key
        for key in ("observed", "scope", "service", "component", "network")
    }
    with pytest.raises(FileExistsError):
        build_industrial_supply_bilan_dashboard(
            observed_dir=inputs["observed"],
            scope_dir=inputs["scope"],
            service_landscape_dir=inputs["service"],
            component_021081_dir=inputs["component"],
            network_screen_dir=inputs["network"],
            output_html=output,
        )
    assert output.read_bytes() == original


def test_action_audit_is_optional_and_incomplete_data_is_not_rendered(tmp_path: Path) -> None:
    output, result = _build(
        tmp_path, complete_optional=False, include_action_audit=False
    )
    document = output.read_text(encoding="utf-8")

    assert result["input_status"]["action_audit"] == "unavailable"
    assert "ANCIENS ESSAIS SIMULÉS — AUCUNE ACTION VALIDÉE" not in document
    assert "FAMILLES D'ACTIONS À VÉRIFIER AVEC LES ÉQUIPES" not in document
    assert "CONDITIONS DE DÉCISION" in document


def test_running_action_audit_never_exposes_partial_rows(tmp_path: Path) -> None:
    inputs = _inputs(
        tmp_path / "inputs", complete_optional=False, include_action_audit=True
    )
    _json(inputs["action"] / "manifest.json", {"status": "running"})
    output = tmp_path / "artifact" / "running-action-audit.html"

    result = build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=inputs["network"],
        action_audit_dir=inputs["action"],
        output_html=output,
    )
    document = output.read_text(encoding="utf-8")

    assert result["input_status"]["action_audit"] == "in_progress"
    assert "ANCIENS ESSAIS SIMULÉS — AUCUNE ACTION VALIDÉE" not in document
    assert "33\u202f532" not in document


def test_frozen_meeting_profile_presents_scoped_network_lots_and_actions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, result, _ = _build_frozen_meeting(
        tmp_path,
        monkeypatch,
        envelope_released=True,
    )
    document = output.read_text(encoding="utf-8")

    assert len(re.findall(r'<section id="view-[^"]+"', document)) == 3
    assert result["view_count"] == 3
    assert result["presentation_profile"] == "meeting"
    assert result["input_status"]["network_screen"] == (
        "envelope_service_top3_released"
    )
    assert result["input_status"]["network_input_status"] == (
        "signed_scientific_overlay_and_audits_valid"
    )
    assert result["input_status"]["network_priority_reporting_status"] == (
        "envelope_service_top3_released"
    )
    assert result["input_status"]["global_network_priority_robustness_evaluable"] is False
    assert result["input_status"]["network_recovery_metric_status"] == (
        "excluded_invalid_common_window"
    )
    assert result["input_status"]["actions_ready_count"] == 0
    assert re.fullmatch(r"[0-9a-f]{64}", str(result["sha256"]))

    first = document.index("1 · Priorités réseau conditionnelles")
    second = document.index("2 · Lots et cascade qualité")
    third = document.index("3 · Actions et bilan 2025")
    assert first < second < third
    assert '<section id="view-vulnerability" class="view active"' in document
    assert "Trio de priorités simulées sous enveloppe du pire des deux tests voie-par-voie" in document
    assert all(name in document for name in ("SDC-AAA", "SDC-BBB", "SDC-CCC"))
    assert document.count("Membre du trio non ordonné") == 3
    assert "Aucun ordre interne n&#x27;est affirmé" in document
    assert "ni une probabilité d'incident, ni une note de criticité observée" in document
    assert "top 3 universel" not in document.lower()

    assert "Quatre conséquences séparées — aucun score unique" in document
    assert all(
        label in document
        for label in (
            "Service sur tout l&#x27;horizon",
            "Pire période glissante de 28 jours",
            "Retard cumulé rapporté à la demande",
            "Production libérée manquante",
        )
    )
    assert "UN·j/UN" in document
    assert "Un retard de 120 jours est imposé" in document
    assert "La quantité utilisable est limitée à 50 %" in document
    assert "Les 18 voies sont confirmées avec 30 comparaisons appariées" in document
    assert "Les quatre causes et les quatre périodes ne sont approfondies que sur trois voies" in document
    assert "Les niveaux intermédiaires du premier tri reposent sur une seule simulation" in document
    assert "Robustesse sur les 18 voies : non évaluable" in document
    assert "ne portent que sur 3 voies présélectionnées" in document
    assert "Aucun délai de récupération du réseau n'est affiché ni utilisé" in document
    assert "« x/30 » est un comptage de simulations" in document
    assert "Ce n'est ni une probabilité, ni une fréquence historique, ni une prévision fournisseur" in document
    assert "Ancien cas 338929 — étude ciblée séparée" in document
    assert "ni pour former le trio ou le groupe réseau, ni pour choisir une action" in document

    view_two = document.split('<section id="view-lots"', 1)[1].split(
        '<section id="view-observed"', 1
    )[0]
    assert "Exposition et effet causal : deux informations différentes" in view_two
    assert "occurrences aval exposées, borne haute" in view_two
    assert "6/20" in view_two
    assert "être exposé ne signifie pas avoir été retardé, perdu ou causé" in view_two
    assert "Une ligne technique reste un identifiant du modèle" in view_two
    assert "jamais un numéro de lot ou de commande industriel" in view_two
    assert "une seule comparaison appariée pour chacune des trois voies approfondies" in view_two
    assert "pas la variabilité statistique des effets lot par lot" in view_two
    assert "La retenue qualité est un scénario reconstruit" in view_two
    assert "Aucun délai de récupération du réseau" in view_two
    assert "ANCIENS ESSAIS SIMULÉS" not in view_two
    assert "CONDITIONS DE DÉCISION" not in view_two

    view_three = document.split('<section id="view-observed"', 1)[1]
    assert "0</span> action prête à recommander" in view_three
    assert "4 candidates bloquées" in view_three
    assert view_three.count("Bloquée pour recommandation") == 4
    assert "« Bloquée » ne veut pas dire impossible" in view_three
    assert "Aucun des quatre leviers ci-dessous n'a été simulé dans la campagne réseau finale" in view_three
    assert "ne mesurent pas l'efficacité de ces leviers sur les dossiers affichés" in view_three
    assert "aucune sélection ni recommandation n'est publiée" in view_three
    assert "Ancien audit simulé — séparé du choix final" in view_three
    assert "ANCIENS ESSAIS SIMULÉS — AUCUNE ACTION VALIDÉE" in view_three
    assert "indices sans unité monétaire, non comparables aux valeurs 2025" in view_three
    assert "ils ne sont attribués ni à un fournisseur, ni à une cause, ni à un lot" in view_three

    client_copy = re.sub(
        r"<(style|script)[^>]*>.*?</\1>",
        " ",
        document,
        flags=re.DOTALL | re.IGNORECASE,
    )
    client_copy = re.sub(r"<[^>]+>", " ", client_copy)
    assert re.search(r"\b(gate|hash|sweep)\b", client_copy.lower()) is None
    assert "<script src=" not in document.lower()
    assert "fetch(" not in document.lower()
    assert "http://" not in document.lower()
    assert "https://" not in document.lower()


def test_frozen_meeting_profile_keeps_an_unordered_priority_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, result, _ = _build_frozen_meeting(
        tmp_path,
        monkeypatch,
        envelope_released=False,
    )
    document = output.read_text(encoding="utf-8")

    assert result["input_status"]["network_screen"] == "priority_group_only"
    assert "Groupe de priorités simulées sous enveloppe du pire des deux tests voie-par-voie" in document
    assert "Groupe non ordonné à instruire" in document
    assert all(
        supplier in document
        for supplier in ("SDC-AAA", "SDC-BBB", "SDC-CCC", "SDC-DDD", "SDC-EEE")
    )
    assert "Aucun rang artificiel n&#x27;est affiché" in document
    assert "Membre du trio non ordonné" not in document


@pytest.mark.parametrize("invalid_part", ("promotion", "actions"))
def test_frozen_network_contract_fails_closed_before_rendering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_part: str,
) -> None:
    payload = _frozen_network_api_payload(envelope_released=True)
    if invalid_part == "promotion":
        payload["extension"]["controls"]["promotion_allowed"] = True
        expected = "limites scientifiques"
    else:
        payload["actions"]["released"] = True
        expected = "action réseau"
    overlay = tmp_path / "overlay"
    boundary = tmp_path / "boundary"
    actions = tmp_path / "actions"
    for directory in (overlay, boundary, actions):
        directory.mkdir()
    monkeypatch.setattr(
        dashboard.network_results,
        "load_network_results",
        lambda *args, **kwargs: payload,
    )

    with pytest.raises(ValueError, match=expected):
        dashboard._load_frozen_network_state(
            overlay_dir=overlay,
            priority_boundary_audit_dir=boundary,
            action_selection_dir=actions,
        )


def test_action_selection_requires_the_frozen_boundary_contract(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path / "inputs", complete_optional=False)
    with pytest.raises(ValueError, match="exige la surcouche"):
        dashboard.load_industrial_supply_bilan_inputs(
            observed_dir=inputs["observed"],
            scope_dir=inputs["scope"],
            service_landscape_dir=inputs["service"],
            network_action_selection_dir=tmp_path / "actions",
        )


def test_meeting_profile_opens_on_338929_then_quality_then_2025(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path / "inputs", complete_optional=True)
    network_detail = tmp_path / "pages" / "network.html"
    network_detail.parent.mkdir(parents=True)
    network_detail.write_text("<!doctype html>", encoding="utf-8")
    output = tmp_path / "artifact" / "meeting.html"

    result = build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=inputs["network"],
        action_audit_dir=inputs["action"],
        supplier_source_audit_dir=inputs["source_audit"],
        network_risk_html=network_detail,
        output_html=output,
        presentation_profile="meeting",
    )
    document = output.read_text(encoding="utf-8")

    assert result["presentation_profile"] == "meeting"
    first = document.index("1 · Retard 338929 et réseau")
    second = document.index("2 · Cascade qualité simulée et lots")
    third = document.index("3 · Décisions et bilan 2025")
    assert first < second < third
    first_section = document.index('<section id="view-vulnerability"')
    second_section = document.index('<section id="view-lots"')
    third_section = document.index('<section id="view-observed"')
    assert first_section < second_section < third_section
    assert '<section id="view-vulnerability" class="view active"' in document
    assert '<section id="view-lots" class="view"' in document
    assert '<section id="view-observed" class="view" hidden' in document
    assert "338929 : un retard fournisseur atteint-il 268091 ?" in document
    assert "sensibilité conditionnelle au retard 338929" in document
    assert "cascade qualité 021081 simulée" in document
    assert "Cela montre une sensibilité physique" in document
    assert "il ne prédit pas un incident" in document
    assert "Ouvrir le détail 338929 : exposition et effets causaux" in document
    assert "Quatre familles d'actions à vérifier" in document
    assert "aucune action validée ici" in document
    assert "Transport après libération qualité" in document
    assert "Quatre décisions possibles" not in document
    assert "Lot qualité libéré" not in document
    assert "ce ne sont pas des recommandations" in document


def test_meeting_opening_uses_only_closed_evidence_and_exact_chain() -> None:
    exact_network_row = {
        "supplier_id": "SDC-VD0914360C",
        "supplier_sensitivity_rank": 1,
        "worst_item_id": "item:338929",
        "worst_dst_node_id": "M-1810",
        "worst_target_product_id": "268091",
        "worst_service_delta": -0.20,
    }
    service_row = {
        "chain_id": "338929_m1810_268091",
        "product_on_due_date_proxy_mean": 0.51,
        "n_seeds": 10,
    }
    data = {
        "network": {
            "state": "groupe_prioritaire",
            "manifest": {"confirmation_seed_count": 30},
            "ranking": [exact_network_row],
        },
        "service": {"state": "not_concluded", "worst_cases": [service_row]},
    }
    masked = _meeting_opening_block(data, {})
    assert "calcul en cours — résultat chiffré masqué" in masked
    assert "20,0 points" not in masked
    assert "51,0 %" not in masked
    assert "résultat simulé stabilisé" not in masked

    data["service"]["state"] = "complete"
    exploratory = _meeting_opening_block(data, {})
    assert "51,0 %" in exploratory
    assert "ancienne étude ciblée exploratoire, distincte du classement réseau final" in exploratory
    assert "10 répétitions simulées" in exploratory
    assert "20,0 points" not in exploratory

    data["network"]["state"] = NETWORK_STABILIZED_STATE
    stabilized = _meeting_opening_block(data, {})
    assert "baisse moyenne de 20,0 points" in stabilized
    assert "résultat simulé stabilisé dans le protocole réseau" in stabilized
    assert "30 répétitions simulées comparables" in stabilized
    assert "51,0 %" not in stabilized

    data["network"]["ranking"] = [
        {
            **exact_network_row,
            "supplier_id": "SDC-AUTRE",
            "worst_target_product_id": "268967",
        }
    ]
    data["service"]["state"] = "not_concluded"
    mismatch = _meeting_opening_block(data, {})
    assert "calcul en cours — résultat chiffré masqué" in mismatch
    assert "20,0 points" not in mismatch


def test_meeting_profile_never_invents_observed_021081_orderbook(
    tmp_path: Path,
) -> None:
    inputs = _inputs(tmp_path / "inputs", complete_optional=False)
    (inputs["component"] / "observed_order_book_audit.json").unlink()
    output = tmp_path / "artifact" / "meeting-without-orderbook.html"
    build_industrial_supply_bilan_dashboard(
        observed_dir=inputs["observed"],
        scope_dir=inputs["scope"],
        service_landscape_dir=inputs["service"],
        component_021081_dir=inputs["component"],
        network_screen_dir=inputs["network"],
        output_html=output,
        presentation_profile="meeting",
    )
    document = output.read_text(encoding="utf-8")
    assert "Carnet 021081 non fourni à cette page ; aucun nombre observé n'est affiché." in document
    assert "23 lignes représentent" not in document
    assert "les 23 lignes planifiées" not in document
    assert "ses 23 réceptions" not in document
    assert "non disponible fournisseurs" in document


def test_unknown_presentation_profile_is_rejected(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path / "inputs", complete_optional=False)
    with pytest.raises(ValueError, match="Unknown presentation profile"):
        build_industrial_supply_bilan_dashboard(
            observed_dir=inputs["observed"],
            scope_dir=inputs["scope"],
            service_landscape_dir=inputs["service"],
            output_html=tmp_path / "artifact" / "invalid.html",
            presentation_profile="unknown",
        )
