from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_network_priority_boundary_audit as audit,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _base_profiles() -> dict[str, dict[str, float]]:
    profiles: dict[str, dict[str, float]] = {}
    for index in range(16):
        harm = max(0.0, 0.40 - index * 0.10)
        profiles[f"SUP-{index:02d}"] = {
            "service": -harm,
            "rolling": -harm,
            "backlog": harm * 10.0,
            "production": harm,
        }
    return profiles


def _fixture(
    *,
    profiles: dict[str, dict[str, float]] | None = None,
    all_zero: bool = False,
    service_by_seed: dict[str, list[float]] | None = None,
    service_by_failure_mode_supplier: dict[tuple[str, str], float] | None = None,
) -> tuple[
    list[dict],
    tuple[str, ...],
    dict[str, audit.ScenarioMeta],
    list[dict],
    list[dict],
]:
    profiles = profiles or _base_profiles()
    if all_zero:
        profiles = {
            supplier: {
                "service": 0.0,
                "rolling": 0.0,
                "backlog": 0.0,
                "production": 0.0,
            }
            for supplier in profiles
        }
    lane_suppliers = [f"SUP-{index:02d}" for index in range(16)] + [
        "SUP-00",
        "SUP-01",
    ]
    scenario_meta: dict[str, audit.ScenarioMeta] = {}
    scenario_design: list[dict] = []
    for lane_index, supplier in enumerate(lane_suppliers):
        product = "268091" if lane_index % 2 == 0 else "268967"
        for mode in sorted(audit.CONFIRMED_FAILURE_MODES):
            scenario_id = f"chain_{lane_index:02d}__{mode}__severe"
            meta = audit.ScenarioMeta(
                scenario_id=scenario_id,
                chain_id=f"chain_{lane_index:02d}",
                supplier_id=supplier,
                item_id=f"item:{lane_index:06d}",
                dst_node_id="M-1810" if product == "268091" else "M-1430",
                target_product_id=product,
                failure_mode=mode,
                level_code="severe",
                mechanism_value=(120.0 if mode == "transport_delay" else 0.50),
                mechanism_unit=(
                    "jours_ajoutes"
                    if mode == "transport_delay"
                    else "part_disponible"
                ),
                stress_start_day=45,
                stress_end_day=224,
            )
            scenario_meta[scenario_id] = meta
            scenario_design.append(
                {
                    "scenario_id": scenario_id,
                    "chain_id": meta.chain_id,
                    "supplier_id": supplier,
                    "item_id": meta.item_id,
                    "dst_node_id": meta.dst_node_id,
                    "target_product_id": product,
                    "failure_mode": mode,
                    "level_code": "severe",
                    "mechanism_value": meta.mechanism_value,
                    "mechanism_unit": meta.mechanism_unit,
                    "stress_start_day": meta.stress_start_day,
                    "stress_end_day": meta.stress_end_day,
                }
            )
    selected = tuple(sorted(scenario_meta))
    rows: list[dict] = []
    for seed in range(1001, 1031):
        baseline_row = {
            "stage": "confirmation",
            "scenario_id": audit.BASELINE_SCENARIO_ID,
            "seed": seed,
            "valid": True,
            "j0_state_sha256": f"j0-{seed}",
            "input_sha256": "graph",
            "resolved_common_random_numbers": True,
            "resolved_random_seed": seed,
            "summary_sim_days": 720,
            "summary_timeline_days": 720,
            "demand_qty_268091": 1_000.0,
            "demand_qty_268967": 1_000.0,
            "on_due_volume_proxy_268091": 0.99,
            "on_due_volume_proxy_268967": 0.99,
            "worst_rolling_28d_on_due_proxy_268091": 0.99,
            "worst_rolling_28d_on_due_proxy_268967": 0.99,
            "backlog_qty_days_268091": 0.0,
            "backlog_qty_days_268967": 0.0,
        }
        for lane_index in range(18):
            prefix = f"baseline_chain__chain_{lane_index:02d}"
            baseline_row[f"{prefix}__ops__target_released_qty"] = 1_000.0
            baseline_row[f"{prefix}__active_window_pulled_qty"] = 1.0
            baseline_row[f"{prefix}__active_window_shipped_qty"] = 1.0
        rows.append(baseline_row)
        for scenario_id in selected:
            meta = scenario_meta[scenario_id]
            profile = profiles[meta.supplier_id]
            service = profile["service"]
            if service_by_failure_mode_supplier:
                service = service_by_failure_mode_supplier.get(
                    (meta.failure_mode, meta.supplier_id), service
                )
            if service_by_seed and meta.supplier_id in service_by_seed:
                service = service_by_seed[meta.supplier_id][seed - 1001]
            # Availability is deliberately milder. The per-supplier envelope
            # must therefore select transport_delay without using its ID.
            factor = 0.9 if meta.failure_mode == "supply_availability" else 1.0
            service *= factor
            rolling = profile["rolling"] * factor
            backlog = profile["backlog"] * factor
            production = profile["production"] * factor
            rows.append(
                {
                    "stage": "confirmation",
                    "scenario_id": scenario_id,
                    "chain_id": meta.chain_id,
                    "target_product_id": meta.target_product_id,
                    "mechanism": meta.failure_mode,
                    "level_code": meta.level_code,
                    "mechanism_value": meta.mechanism_value,
                    "mechanism_unit": meta.mechanism_unit,
                    "stress_start_day": meta.stress_start_day,
                    "stress_end_day": meta.stress_end_day,
                    "seed": seed,
                    "valid": True,
                    "j0_state_sha256": f"j0-{seed}",
                    "input_sha256": "graph",
                    "resolved_common_random_numbers": True,
                    "resolved_random_seed": seed,
                    "summary_sim_days": 720,
                    "summary_timeline_days": 720,
                    "demand_qty_268091": 1_000.0,
                    "demand_qty_268967": 1_000.0,
                    "target_demand_qty": 1_000.0,
                    "product_on_due_date_proxy": 0.99 + service,
                    "paired_baseline_product_on_due_date_proxy": 0.99,
                    "paired_baseline_active_window_pulled_qty": 1.0,
                    "paired_baseline_active_window_shipped_qty": 1.0,
                    "target_on_due_date_proxy_delta_vs_paired_baseline": service,
                    "target_worst_rolling_28d_on_due_proxy": 0.99 + rolling,
                    "paired_baseline_target_worst_rolling_28d_on_due_proxy": 0.99,
                    "target_worst_rolling_28d_on_due_delta_vs_paired_baseline": rolling,
                    "target_backlog_qty_days": backlog * 1_000.0,
                    "paired_baseline_target_backlog_qty_days": 0.0,
                    "incremental_target_backlog_qty_days": backlog * 1_000.0,
                    "target_released_qty": 1_000.0 * (1.0 - production),
                    "paired_baseline_target_released_qty": 1_000.0,
                    "target_released_qty_delta_vs_paired_baseline": (
                        -1_000.0 * production
                    ),
                    "target_production_shortfall_vs_paired_baseline": (
                        1_000.0 * production
                    ),
                    "target_production_shortfall_ratio_vs_paired_baseline": production,
                    "component_days_below_safety_delta_vs_paired_baseline": (
                        production * 100.0
                    ),
                    "effect_status": (
                        "effet_mesure_sur_le_service_client"
                        if service < -1e-8
                        else "stress_applique_sans_effet_mesurable"
                    ),
                }
            )

    by_scenario: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["scenario_id"] != audit.BASELINE_SCENARIO_ID:
            by_scenario[row["scenario_id"]].append(row)
    scenario_keys: dict[str, tuple[float, float, float, str]] = {}
    for scenario_id, scenario_rows in by_scenario.items():
        service = sum(
            row["target_on_due_date_proxy_delta_vs_paired_baseline"]
            for row in scenario_rows
        ) / len(scenario_rows)
        production = sum(
            row["target_production_shortfall_ratio_vs_paired_baseline"]
            for row in scenario_rows
        ) / len(scenario_rows)
        safety = sum(
            row["component_days_below_safety_delta_vs_paired_baseline"]
            for row in scenario_rows
        ) / len(scenario_rows)
        scenario_keys[scenario_id] = (service, -production, -safety, scenario_id)
    supplier_worst: dict[str, tuple[float, float, float, str]] = {}
    for scenario_id, meta in scenario_meta.items():
        candidate = scenario_keys[scenario_id]
        if meta.supplier_id not in supplier_worst:
            supplier_worst[meta.supplier_id] = candidate
        else:
            supplier_worst[meta.supplier_id] = min(
                supplier_worst[meta.supplier_id], candidate
            )
    order = sorted(
        supplier_worst,
        key=lambda supplier: (*supplier_worst[supplier], supplier),
    )
    ranking = [
        {
            "supplier_sensitivity_rank": rank,
            "supplier_id": supplier,
            "worst_service_delta": supplier_worst[supplier][0],
            "evidence_stage": "confirmation_30_realisations",
        }
        for rank, supplier in enumerate(order, 1)
    ]
    return rows, selected, scenario_meta, ranking, scenario_design


def _analyze(
    rows: list[dict],
    selected: tuple[str, ...],
    meta: dict[str, audit.ScenarioMeta],
    ranking: list[dict],
    *,
    resamples: int = 200,
) -> tuple[dict, list[dict], list[dict]]:
    return audit.analyze_priority_boundary(
        confirmation_rows=rows,
        selected_scenario_ids=selected,
        scenario_meta=meta,
        ranking_rows=ranking,
        resamples=resamples,
        enforce_industrial_scope=True,
    )


def _write_complete_network_source(
    source: Path,
    *,
    rows: list[dict],
    selected: tuple[str, ...],
    ranking: list[dict],
    design: list[dict],
) -> None:
    source.mkdir()
    campaign_manifest = {
        "schema_version": "etudecas.supplier_network_risk_screen_campaign.v1",
        "mode": "full",
        "campaign_script_sha256": "1" * 64,
        "v4_extraction_core_sha256": "2" * 64,
        "graph_sha256": "3" * 64,
        "engine_sha256": "4" * 64,
        "reference_shipments_sha256": "5" * 64,
        "scope_audit_path": "synthetic-scope-audit",
        "scope_audit_csv_sha256": "6" * 64,
        "scope_audit_manifest_sha256": "7" * 64,
        "reference_summary_sha256": "8" * 64,
        "supplier_floor_source_sha256": "9" * 64,
        "prepared_supplier_floor_content_sha256": "a" * 64,
        "profile_sha256": "b" * 64,
        "days": 720,
        "screening_seed": 1_000,
        "smoke_components_requested": [],
        "smoke_all_levels_requested": False,
        "confirmation_seeds": list(range(1001, 1031)),
        "confirmation_top_lanes": 18,
        "confirmation_scope_requirement": "all_18_active_lanes",
        "confirmation_mathematical_families": {
            "date_shift": "transport_delay",
            "usable_quantity_loss": "supply_availability",
        },
        "planned_run_counts": {"synthetic_fixture": 1_110},
        "common_window_start_day": 45,
        "common_window_end_day": 224,
        "lane_specific_stress_duration_days": 180,
        "lane_specific_window_method": (
            "maximum_reference_shipped_quantity_in_180d_"
            "tie_nearest_J45_then_earliest"
        ),
        "active_chain_ids": [f"chain_{index:02d}" for index in range(18)],
        "scenario_ids": [audit.BASELINE_SCENARIO_ID, *selected],
        "reference_open_orders_disabled": True,
        "network_lot_trace_opt_in": True,
        "status": "complete",
        "confirmation_seed_count": 30,
        "active_lane_count": 18,
        "distinct_supplier_count": 16,
    }
    campaign_manifest["campaign_signature"] = audit._canonical_sha256(
        {
            key: campaign_manifest[key]
            for key in audit.CAMPAIGN_SIGNATURE_FIELDS
        }
    )
    _write_json(source / "campaign_manifest.json", campaign_manifest)
    _write_csv(source / "confirmation_metrics.csv", rows)
    _write_json(
        source / "confirmation_selection.json",
        {
            "selected_scenario_ids": list(selected),
            "confirmed_unique_chain_ids": [
                f"chain_{index:02d}" for index in range(18)
            ],
            "mathematical_families": {
                "date_shift": "transport_delay",
                "usable_quantity_loss": "supply_availability",
            },
        },
    )
    _write_csv(source / "confirmation_supplier_sensitivity_ranking.csv", ranking)
    _write_csv(source / "scenario_design.csv", design)


def _resign_campaign_manifest(source: Path) -> None:
    manifest_path = source / "campaign_manifest.json"
    manifest = audit._read_json(manifest_path)
    manifest["campaign_signature"] = audit._canonical_sha256(
        {key: manifest[key] for key in audit.CAMPAIGN_SIGNATURE_FIELDS}
    )
    _write_json(manifest_path, manifest)


def test_all_zero_effects_are_an_unordered_group_not_a_stable_top3():
    rows, selected, meta, ranking, _design = _fixture(all_zero=True)
    result, metric_rows, effect_rows = _analyze(
        rows, selected, meta, ranking
    )
    service = result["metric_priority_audits"][0]
    assert service["top3_presence_seed_counts"] == {
        "SUP-00": 0,
        "SUP-01": 0,
        "SUP-02": 0,
    }
    assert service["boundary_gap_resampling95_low"] == 0
    assert not service["selected_set_numerical_effect_resampling_pass"]
    assert not service["boundary_statistical_separation_pass"]
    assert not service["scoped_descriptive_set_display_allowed"]
    assert not result["scoped_descriptive_priority_set_display_allowed"]
    assert not result["service_priority_set_release_pass"]
    assert not result["universal_supplier_top3_release_pass"]
    assert result["universal_supplier_top3_ids"] == []
    assert len(result["priority_group_supplier_ids_if_no_universal_top3"]) == 16
    assert metric_rows and effect_rows


def test_clear_adverse_gap_displays_scoped_three_without_releasing_priority():
    rows, selected, meta, ranking, _design = _fixture()
    result, _metric_rows, effect_rows = _analyze(
        rows, selected, meta, ranking
    )
    service = result["metric_priority_audits"][0]
    assert service["rank3_supplier_id"] == "SUP-02"
    assert service["rank4_supplier_id"] == "SUP-03"
    assert service["boundary_gap_point"] == pytest.approx(0.1)
    assert service[
        "fixed_selected_set_vs_all_outsiders_resampling_gap_rule_pass"
    ]
    assert service["boundary_reporting_resolution_pass"]
    assert service[
        "selected_set_all_above_predeclared_reporting_threshold_pass"
    ]
    assert service["scoped_descriptive_set_display_allowed"]
    assert result["scoped_descriptive_priority_set_display_allowed"]
    assert result["displayed_scoped_priority_supplier_ids"] == [
        "SUP-00",
        "SUP-01",
        "SUP-02",
    ]
    assert result["cause_independent_service_descriptive_display_allowed"]
    assert result["separate_metric_top3_sets_identical"]
    assert result["all_four_metric_scoped_descriptive_sets_display_allowed"]
    assert result["all_scope_descriptive_set_convergence"]
    assert not result["service_priority_set_release_pass"]
    assert not result["universal_supplier_top3_release_pass"]
    assert not result["confirmatory_priority_set_release_allowed"]
    assert not result["global_priority_release_allowed"]
    assert not result["action_promotion_allowed"]
    assert result["universal_supplier_top3_ids"] == []
    assert len(result["envelope_service_driver_mappings"]) == 16
    assert [
        row["selection_slot"]
        for row in result["displayed_scoped_priority_driver_mappings"]
    ] == [1, 2, 3]
    assert all(
        row["driver_lane_uniqueness_claimed"] is False
        for row in result["envelope_service_driver_mappings"]
    )
    assert result["supplier_lane_count_by_id"]["SUP-00"] == 2
    assert not result["supplier_lane_exposure_balanced"]
    assert not result["lane_count_normalization_applied"]
    assert not result["broad_supply_uncertainty_monte_carlo_claimed"]
    assert not result["baseline_80_and_93_percent_configurations_evaluated"]
    assert not result["selection_and_assessment_seed_blocks_independent"]
    assert not result["confirmatory_population_priority_inference_claimed"]
    supplier_zero = next(
        row
        for row in effect_rows
        if row["aggregation_level"] == "supplier_any_confirmed_scenario"
        and row["supplier_id"] == "SUP-00"
    )
    assert (
        supplier_zero[
            "display_threshold_exceedance_client_effect_seed_count"
        ]
        == 30
    )
    assert not supplier_zero[
        "supplier_any_effect_seed_count_cross_supplier_comparable"
    ]
    assert not supplier_zero["business_materiality_threshold_validated"]
    assert supplier_zero["historical_occurrence_probability"] == "not_estimated"


def test_failure_mode_divergence_keeps_envelope_but_blocks_universal_wording():
    rows, selected, meta, ranking, _design = _fixture(
        service_by_failure_mode_supplier={
            ("transport_delay", "SUP-03"): -0.35,
        }
    )
    result, metric_rows, _effect_rows = _analyze(rows, selected, meta, ranking)
    assert result["scoped_descriptive_priority_set_display_allowed"]
    assert result["service_priority_scope"] == audit.SUPPLIER_ENVELOPE_SCOPE
    assert not result["family_service_top3_sets_identical"]
    assert result[
        "family_service_divergence_blocks_cause_independent_wording"
    ]
    assert not result[
        "cause_independent_service_descriptive_display_allowed"
    ]
    assert not result["universal_supplier_top3_release_pass"]
    assert result["universal_supplier_top3_ids"] == []
    family_top3 = result[
        "family_service_descriptive_first_three_supplier_ids"
    ]
    assert set(family_top3["transport_delay"]) != set(
        family_top3["supply_availability"]
    )
    assert {row["aggregation_scope"] for row in metric_rows} == {
        audit.SUPPLIER_ENVELOPE_SCOPE,
        "failure_mode_specific",
    }


def test_small_but_deterministic_gap_fails_publication_resolution():
    profiles = _base_profiles()
    profiles["SUP-02"].update(
        service=-0.1005, rolling=-0.1005, backlog=1.005, production=0.1005
    )
    profiles["SUP-03"].update(
        service=-0.1000, rolling=-0.1000, backlog=1.000, production=0.1000
    )
    rows, selected, meta, ranking, _design = _fixture(profiles=profiles)
    result, _metric_rows, _effect_rows = _analyze(
        rows, selected, meta, ranking
    )
    service = result["metric_priority_audits"][0]
    assert service["boundary_gap_point"] == pytest.approx(0.0005)
    assert service[
        "fixed_selected_set_vs_all_outsiders_resampling_gap_rule_pass"
    ]
    assert not service["boundary_reporting_resolution_pass"]
    assert not result["scoped_descriptive_priority_set_display_allowed"]


def test_overlapping_paired_gap_interval_fails_even_when_mean_order_exists():
    service_by_seed = {
        "SUP-02": [-0.25 if index % 2 == 0 else -0.05 for index in range(30)],
        "SUP-03": [-0.05 if index % 2 == 0 else -0.24 for index in range(30)],
    }
    rows, selected, meta, ranking, _design = _fixture(
        service_by_seed=service_by_seed
    )
    result, _metric_rows, _effect_rows = _analyze(
        rows, selected, meta, ranking, resamples=1_000
    )
    service = result["metric_priority_audits"][0]
    assert service["boundary_gap_point"] > 0
    assert service["boundary_gap_resampling95_low"] < 0
    assert not service["boundary_statistical_separation_pass"]
    assert not service["top3_membership_stability_pass"]
    assert not service["fixed_selected_set_presence_rule_pass"]
    assert not result["scoped_descriptive_priority_set_display_allowed"]


def test_seed_level_rank3_ties_never_gain_lexical_membership_credit():
    service_by_seed = {
        "SUP-02": [-0.10] * 25 + [-0.40] * 5,
        "SUP-03": [-0.10] * 30,
    }
    rows, selected, meta, ranking, _design = _fixture(
        service_by_seed=service_by_seed
    )
    result, _metric_rows, _effect_rows = _analyze(
        rows, selected, meta, ranking, resamples=1_000
    )
    service = result["metric_priority_audits"][0]
    assert service["rank3_supplier_id"] == "SUP-02"
    assert service["top3_presence_seed_counts"]["SUP-02"] == 5
    assert not service["top3_membership_stability_pass"]
    assert not service["fixed_selected_set_presence_rule_pass"]
    assert not result["scoped_descriptive_priority_set_display_allowed"]


def test_fixed_selected_set_is_compared_with_every_outsider_not_only_rank4():
    profiles = _base_profiles()
    profiles["SUP-02"]["service"] = -0.10
    profiles["SUP-03"]["service"] = -0.09
    service_by_seed = {
        "SUP-04": [-0.95] + [-0.05] * 29,
    }
    rows, selected, meta, ranking, _design = _fixture(
        profiles=profiles,
        service_by_seed=service_by_seed,
    )
    result, _metric_rows, _effect_rows = _analyze(
        rows, selected, meta, ranking, resamples=2_000
    )
    service = result["metric_priority_audits"][0]
    assert service["rank3_supplier_id"] == "SUP-02"
    assert service["rank4_supplier_id"] == "SUP-03"
    assert service["boundary_gap_point"] == pytest.approx(0.01)
    assert service["top3_presence_seed_counts"]["SUP-02"] == 29
    assert service["fixed_selected_set_presence_rule_pass"]
    assert service["boundary_gap_resampling95_low"] < 0
    assert not service[
        "fixed_selected_set_vs_all_outsiders_resampling_gap_rule_pass"
    ]
    assert "SUP-04" in service["nonseparation_group_supplier_ids"]
    assert not result["scoped_descriptive_priority_set_display_allowed"]


def test_selected_set_must_clear_display_threshold_not_only_outsider_gap():
    profiles = _base_profiles()
    for supplier in profiles:
        profiles[supplier]["service"] = 0.01
    profiles["SUP-00"]["service"] = -0.0009
    profiles["SUP-01"]["service"] = -0.0008
    profiles["SUP-02"]["service"] = -0.0007
    rows, selected, meta, ranking, _design = _fixture(profiles=profiles)
    result, _metric_rows, _effect_rows = _analyze(
        rows, selected, meta, ranking
    )
    service = result["metric_priority_audits"][0]
    assert service["boundary_reporting_resolution_pass"]
    assert service[
        "fixed_selected_set_vs_all_outsiders_resampling_gap_rule_pass"
    ]
    assert service["selected_set_minimum_adverse_magnitude_point"] == (
        pytest.approx(0.0007)
    )
    assert not service[
        "selected_set_all_above_predeclared_reporting_threshold_pass"
    ]
    assert not service["scoped_descriptive_set_display_allowed"]


def test_effect_status_cannot_forge_display_threshold_exceedance_counts():
    profiles = {
        supplier: {
            "service": 0.0,
            "rolling": 0.0,
            "backlog": 0.0,
            "production": 0.0,
        }
        for supplier in _base_profiles()
    }
    profiles["SUP-00"].update(
        service=-1e-6,
        rolling=-1e-6,
        production=1e-6,
    )
    rows, selected, meta, ranking, _design = _fixture(profiles=profiles)
    for row in rows:
        if row["scenario_id"] != audit.BASELINE_SCENARIO_ID:
            row["effect_status"] = "effet_mesure_sur_le_service_client"
    _result, _metric_rows, effect_rows = _analyze(
        rows, selected, meta, ranking
    )
    supplier = next(
        row
        for row in effect_rows
        if row["aggregation_level"] == "supplier_any_confirmed_scenario"
        and row["supplier_id"] == "SUP-00"
    )
    assert supplier[
        "display_threshold_exceedance_client_effect_seed_count"
    ] == 0
    assert supplier[
        "display_threshold_exceedance_production_effect_seed_count"
    ] == 0
    assert supplier["any_numerical_propagation_seed_count"] == 30
    assert supplier["source_effect_status_client_seed_count"] == 30
    assert not supplier["source_effect_status_used_for_display_threshold_counts"]
    assert supplier["thresholds_are_model_reporting_conventions"]
    assert not supplier["business_materiality_threshold_validated"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_incomplete_or_duplicate_confirmation_matrix_fails_closed(mutation: str):
    rows, selected, meta, ranking, _design = _fixture()
    stress_index = next(
        index
        for index, row in enumerate(rows)
        if row["scenario_id"] != audit.BASELINE_SCENARIO_ID
    )
    if mutation == "missing":
        rows.pop(stress_index)
    else:
        rows.append(dict(rows[stress_index]))
    with pytest.raises(ValueError, match="matrice|Matrice|dupliqu"):
        _analyze(rows, selected, meta, ranking)


def test_demand_denominator_mismatch_fails_pairing_gate():
    rows, selected, meta, ranking, _design = _fixture()
    stress = next(
        row for row in rows if row["scenario_id"] != audit.BASELINE_SCENARIO_ID
    )
    stress["target_demand_qty"] = 999
    with pytest.raises(ValueError, match="demande non apparié"):
        _analyze(rows, selected, meta, ranking)


@pytest.mark.parametrize("failed_prerequisite", ["baseline_service", "active_flow"])
def test_interpretation_prerequisite_blocks_publication_separately(
    failed_prerequisite: str,
):
    rows, selected, meta, ranking, _design = _fixture()
    if failed_prerequisite == "baseline_service":
        baseline = next(
            row for row in rows if row["scenario_id"] == audit.BASELINE_SCENARIO_ID
        )
        baseline["on_due_volume_proxy_268091"] = 0.94
        for row in rows:
            if (
                row["scenario_id"] != audit.BASELINE_SCENARIO_ID
                and row["seed"] == baseline["seed"]
                and row["target_product_id"] == "268091"
            ):
                row["paired_baseline_product_on_due_date_proxy"] = 0.94
                row["product_on_due_date_proxy"] = (
                    0.94
                    + row["target_on_due_date_proxy_delta_vs_paired_baseline"]
                )
    else:
        for row in rows:
            scenario_id = str(row["scenario_id"])
            if (
                scenario_id == audit.BASELINE_SCENARIO_ID
                and row["seed"] in {1001, 1002}
            ):
                row[
                    "baseline_chain__chain_00__active_window_pulled_qty"
                ] = 0.0
                row[
                    "baseline_chain__chain_00__active_window_shipped_qty"
                ] = 0.0
            if (
                scenario_id != audit.BASELINE_SCENARIO_ID
                and meta[scenario_id].chain_id == "chain_00"
                and row["seed"] in {1001, 1002}
            ):
                row["paired_baseline_active_window_pulled_qty"] = 0.0
                row["paired_baseline_active_window_shipped_qty"] = 0.0
    result, metric_rows, _effect_rows = _analyze(rows, selected, meta, ranking)
    assert result["execution_integrity_pass"]
    assert not result["interpretation_prerequisites_pass"]
    assert not result["scoped_descriptive_priority_set_display_allowed"]
    assert not result["service_priority_set_release_pass"]
    assert not result["universal_supplier_top3_release_pass"]
    assert all(
        not row["scoped_descriptive_set_display_allowed"]
        for row in result["metric_priority_audits"]
    )
    assert all(
        not audit_row["scoped_descriptive_set_display_allowed"]
        for family in result[
            "failure_mode_specific_metric_priority_audits"
        ].values()
        for audit_row in family["metric_priority_audits"]
    )
    assert all(
        not row["metric_priority_set_release_pass"] for row in metric_rows
    )


def test_source_service_rank_inversion_fails_closed():
    rows, selected, meta, ranking, _design = _fixture()
    ranking[0]["supplier_sensitivity_rank"] = 16
    ranking[-1]["supplier_sensitivity_rank"] = 1
    with pytest.raises(ValueError, match="rangs service.*pas monotones"):
        _analyze(rows, selected, meta, ranking)


def test_active_flow_reference_must_match_between_failure_modes():
    rows, selected, meta, ranking, _design = _fixture()
    contradictory = next(
        row
        for row in rows
        if row["scenario_id"] != audit.BASELINE_SCENARIO_ID
        and meta[str(row["scenario_id"])].chain_id == "chain_00"
        and meta[str(row["scenario_id"])].failure_mode == "transport_delay"
        and row["seed"] == 1001
    )
    contradictory["paired_baseline_active_window_pulled_qty"] = 0.0
    contradictory["paired_baseline_active_window_shipped_qty"] = 0.0
    with pytest.raises(ValueError, match="Flux de référence apparié incohérent"):
        _analyze(rows, selected, meta, ranking)


def test_physical_lane_identity_must_match_between_failure_modes():
    rows, selected, meta, ranking, _design = _fixture()
    first = "chain_00__transport_delay__severe"
    second = "chain_01__transport_delay__severe"
    first_supplier = meta[first].supplier_id
    second_supplier = meta[second].supplier_id
    meta[first] = replace(meta[first], supplier_id=second_supplier)
    meta[second] = replace(meta[second], supplier_id=first_supplier)
    with pytest.raises(ValueError, match="identité physique.*diffère"):
        _analyze(rows, selected, meta, ranking)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("level_code", "modere", "Niveau non sévère"),
        ("mechanism_value", 60.0, "Amplitude sévère incohérente"),
        ("stress_end_day", 223, "Fenêtre de stress non conforme"),
    ],
)
def test_severe_hypothesis_contract_is_not_inferred_from_scenario_id(
    field: str, value: object, message: str
):
    rows, selected, meta, ranking, _design = _fixture()
    scenario_id = next(
        key
        for key, scenario in meta.items()
        if scenario.failure_mode == "transport_delay"
    )
    meta[scenario_id] = replace(meta[scenario_id], **{field: value})
    with pytest.raises(ValueError, match=message):
        _analyze(rows, selected, meta, ranking)


def test_both_target_products_must_be_present_in_design():
    rows, selected, meta, ranking, _design = _fixture()
    for scenario_id, scenario in list(meta.items()):
        if scenario.target_product_id == "268967":
            meta[scenario_id] = replace(scenario, target_product_id="268091")
    with pytest.raises(ValueError, match="exactement les deux produits"):
        _analyze(rows, selected, meta, ranking)


@pytest.mark.parametrize("paired_field", ["backlog", "production"])
def test_declared_paired_metric_must_match_physical_baseline(paired_field: str):
    rows, selected, meta, ranking, _design = _fixture()
    stress = next(
        row for row in rows if row["scenario_id"] != audit.BASELINE_SCENARIO_ID
    )
    if paired_field == "backlog":
        delta = stress["incremental_target_backlog_qty_days"]
        stress["paired_baseline_target_backlog_qty_days"] = 10.0
        stress["target_backlog_qty_days"] = 10.0 + delta
    else:
        shortfall = stress["target_production_shortfall_vs_paired_baseline"]
        stress["paired_baseline_target_released_qty"] = 1_100.0
        stress["target_released_qty"] = 1_100.0 - shortfall
        stress["target_released_qty_delta_vs_paired_baseline"] = -shortfall
        stress["target_production_shortfall_ratio_vs_paired_baseline"] = (
            shortfall / 1_100.0
        )
    with pytest.raises(ValueError, match="Référence .* appariée incohérente"):
        _analyze(rows, selected, meta, ranking)


@pytest.mark.parametrize(
    "field",
    [
        "target_worst_rolling_28d_on_due_delta_vs_paired_baseline",
        "incremental_target_backlog_qty_days",
        "target_production_shortfall_ratio_vs_paired_baseline",
    ],
)
def test_paired_metric_arithmetic_is_recomputed_not_trusted(field: str):
    rows, selected, meta, ranking, _design = _fixture()
    stress = next(
        row for row in rows if row["scenario_id"] != audit.BASELINE_SCENARIO_ID
    )
    stress[field] += 0.01
    with pytest.raises(ValueError, match="incohérent"):
        _analyze(rows, selected, meta, ranking)


def test_metric_divergence_returns_group_not_universal_criticality():
    profiles = _base_profiles()
    profiles["SUP-03"]["rolling"] = -0.25
    profiles["SUP-04"]["backlog"] = 5.0
    rows, selected, meta, ranking, _design = _fixture(profiles=profiles)
    result, metric_rows, _effect_rows = _analyze(
        rows, selected, meta, ranking
    )
    assert result["scoped_descriptive_priority_set_display_allowed"]
    assert not result["separate_metric_top3_sets_identical"]
    assert not result["universal_supplier_top3_release_pass"]
    assert result["universal_supplier_top3_ids"] == []
    assert {"SUP-03", "SUP-04"} <= set(
        result["priority_group_supplier_ids_if_no_universal_top3"]
    )
    assert all(
        row["universal_supplier_criticality_claimed"] is False
        for row in metric_rows
    )


def test_transactional_compact_package_is_hashed_and_excludes_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_complete"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    source_hashes = {
        path.name: audit._sha256(path) for path in source.iterdir()
    }
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 100)
    output = tmp_path / "priority_boundary_audit"
    built = audit.build_audit_package(
        network_dir=source,
        output_dir=output,
        resamples=100,
    )
    assert built == output.resolve()
    validation = audit.validate_audit_package(output)
    assert validation["valid"]
    assert validation["scoped_descriptive_priority_set_display_allowed"]
    assert validation["displayed_scoped_priority_supplier_ids"] == [
        "SUP-00",
        "SUP-01",
        "SUP-02",
    ]
    assert not validation["confirmatory_priority_set_release_allowed"]
    assert not validation["global_priority_release_allowed"]
    assert source_hashes == {
        path.name: audit._sha256(path) for path in source.iterdir()
    }
    manifest = json.loads(
        (output / "priority_boundary_audit_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["large_case_directories_copied"] is False
    assert manifest["previous_artifacts_mutated"] is False
    result = json.loads(
        (output / "scientific_priority_boundary_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["raw_network_recovery_metric"][
        "used_in_any_ranking_or_gate"
    ] is False
    provenance = audit._read_csv(
        output / "common_random_numbers_provenance.csv"
    )
    assert len(provenance) == audit.EXPECTED_TOTAL_ROW_COUNT
    assert {
        row["provenance_source"] for row in provenance
    } == {"confirmation_metrics_embedded_field"}
    assert not any(path.is_dir() for path in output.iterdir())
    ranking_path = output / "supplier_metric_rankings.csv"
    original_ranking_bytes = ranking_path.read_bytes()
    ranking_path.write_bytes(original_ranking_bytes + b"\n")
    with pytest.raises(ValueError, match="Empreinte invalide"):
        audit.validate_audit_package(output)
    ranking_path.write_bytes(original_ranking_bytes)
    assert audit.validate_audit_package(output)["valid"]
    with pytest.raises(FileExistsError):
        audit.build_audit_package(
            network_dir=source,
            output_dir=output,
            resamples=100,
        )
    (output / "promotion_controls.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Inventaire disque"):
        audit.validate_audit_package(output)


def test_rehashed_displayed_set_tamper_is_rejected_by_semantic_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_complete"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 50)
    output = tmp_path / "boundary"
    audit.build_audit_package(
        network_dir=source,
        output_dir=output,
        resamples=50,
    )
    result_path = output / "scientific_priority_boundary_audit.json"
    result = audit._read_json(result_path)
    forged_ids = ["SUP-00", "SUP-01", "SUP-03"]
    result["displayed_scoped_priority_supplier_ids"] = forged_ids
    audit._write_json(result_path, result)
    manifest_path = output / "priority_boundary_audit_manifest.json"
    manifest = audit._read_json(manifest_path)
    manifest["displayed_scoped_priority_supplier_ids"] = forged_ids
    manifest["artifact_file_sha256"][result_path.name] = audit._sha256(
        result_path
    )
    manifest["package_signature"] = audit._canonical_sha256(
        audit._manifest_signature_payload(manifest)
    )
    audit._write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="résultat service.*divergent"):
        audit.validate_audit_package(output)


def test_unseparated_package_validates_as_group_without_legacy_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture(all_zero=True)
    source = tmp_path / "network_complete"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 40)
    output = tmp_path / "boundary_group"
    audit.build_audit_package(
        network_dir=source,
        output_dir=output,
        resamples=40,
    )
    validation = audit.validate_audit_package(output)
    result = audit._read_json(
        output / "scientific_priority_boundary_audit.json"
    )
    assert not validation["scoped_descriptive_priority_set_display_allowed"]
    assert validation["displayed_scoped_priority_supplier_ids"] == []
    assert len(result["envelope_service_nonseparation_group_supplier_ids"]) == 16
    assert not result["service_priority_set_release_pass"]
    assert not result["universal_supplier_top3_release_pass"]


def test_campaign_signature_is_recomputed_from_exact_upstream_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_bad_campaign_signature"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    manifest = audit._read_json(source / "campaign_manifest.json")
    manifest["campaign_signature"] = "0" * 64
    _write_json(source / "campaign_manifest.json", manifest)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    with pytest.raises(ValueError, match="Signature canonique"):
        audit.build_audit_package(
            network_dir=source,
            output_dir=tmp_path / "must_not_exist",
            resamples=20,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "unknown.incompatible.v999", "Version de campagne"),
        ("confirmation_top_lanes", 1, "pré-déclaration"),
        ("confirmation_scope_requirement", "only_one_lane", "pré-déclaration"),
        (
            "confirmation_mathematical_families",
            {"wrong": "wrong"},
            "pré-déclaration",
        ),
        ("reference_open_orders_disabled", False, "options scientifiques"),
        ("network_lot_trace_opt_in", False, "options scientifiques"),
    ],
)
def test_campaign_scientific_predeclaration_is_enforced_after_resigning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / f"network_bad_{field}"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    manifest = audit._read_json(source / "campaign_manifest.json")
    manifest[field] = value
    _write_json(source / "campaign_manifest.json", manifest)
    _resign_campaign_manifest(source)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    with pytest.raises(ValueError, match=message):
        audit.build_audit_package(
            network_dir=source,
            output_dir=tmp_path / "must_not_exist",
            resamples=20,
        )


def test_selected_confirmation_must_belong_to_signed_campaign_design(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_unpredeclared_confirmation"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    manifest = audit._read_json(source / "campaign_manifest.json")
    scenario_ids = list(manifest["scenario_ids"])
    scenario_ids[scenario_ids.index(selected[0])] = "dummy_unrelated_scenario"
    manifest["scenario_ids"] = scenario_ids
    _write_json(source / "campaign_manifest.json", manifest)
    _resign_campaign_manifest(source)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    with pytest.raises(ValueError, match="pas tous pré-déclarés"):
        audit.build_audit_package(
            network_dir=source,
            output_dir=tmp_path / "must_not_exist",
            resamples=20,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("days", 720.9, "J0–J719"),
        ("confirmation_seed_count", 30.9, "30 graines"),
        ("active_lane_count", 18.9, "18 voies"),
        ("distinct_supplier_count", 16.9, "16 fournisseurs"),
        ("confirmation_top_lanes", 18.9, "pré-déclaration"),
        ("lane_specific_stress_duration_days", 180.9, "fenêtre propre"),
    ],
)
def test_fractional_campaign_integer_contracts_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: float,
    message: str,
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / f"network_fractional_{field}"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    manifest = audit._read_json(source / "campaign_manifest.json")
    manifest[field] = value
    _write_json(source / "campaign_manifest.json", manifest)
    _resign_campaign_manifest(source)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    with pytest.raises(ValueError, match=message):
        audit.build_audit_package(
            network_dir=source,
            output_dir=tmp_path / "must_not_exist",
            resamples=20,
        )


@pytest.mark.parametrize("value", [1.9, "1.9", True, "nan", None])
def test_non_integer_tokens_never_get_silently_truncated(value: object):
    assert audit._to_int(value) == -1


def test_fractional_confirmation_seed_list_is_rejected_after_resigning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_fractional_seeds"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    manifest = audit._read_json(source / "campaign_manifest.json")
    manifest["confirmation_seeds"] = [
        float(seed) + 0.9 for seed in range(1001, 1031)
    ]
    _write_json(source / "campaign_manifest.json", manifest)
    _resign_campaign_manifest(source)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    with pytest.raises(ValueError, match="graines physiques"):
        audit.build_audit_package(
            network_dir=source,
            output_dir=tmp_path / "must_not_exist",
            resamples=20,
        )


@pytest.mark.parametrize("manifest_field", ["active_chain_ids", "confirmation_seeds"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_manifest_scope_must_match_physical_confirmation_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_field: str,
    mutation: str,
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_scope_mismatch"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    manifest = audit._read_json(source / "campaign_manifest.json")
    values = list(manifest[manifest_field])
    if mutation == "missing":
        values = values[:-1]
    else:
        values[-1] = values[0]
    manifest[manifest_field] = values
    _write_json(source / "campaign_manifest.json", manifest)
    _resign_campaign_manifest(source)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    with pytest.raises(ValueError, match="voies confirmées|graines physiques"):
        audit.build_audit_package(
            network_dir=source,
            output_dir=tmp_path / "must_not_exist",
            resamples=20,
        )


def test_fully_rehashed_scientific_value_forgery_fails_reconstruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_complete"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    output = tmp_path / "boundary_forged"
    audit.build_audit_package(
        network_dir=source,
        output_dir=output,
        resamples=20,
    )
    result_path = output / "scientific_priority_boundary_audit.json"
    result = audit._read_json(result_path)
    result["metric_priority_audits"][0]["boundary_gap_point"] = 999.0
    audit._write_json(result_path, result)
    manifest_path = output / "priority_boundary_audit_manifest.json"
    manifest = audit._read_json(manifest_path)
    manifest["artifact_file_sha256"][result_path.name] = audit._sha256(
        result_path
    )
    manifest["package_signature"] = audit._canonical_sha256(
        audit._manifest_signature_payload(manifest)
    )
    audit._write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="reconstruction déterministe"):
        audit.validate_audit_package(output)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("package_signature_semantics", "cryptographically_authenticated"),
        ("legacy_priority_release_aliases_neutralized", False),
    ],
)
def test_rehashed_manifest_cannot_upgrade_digest_or_legacy_release_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / f"network_{field}"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    output = tmp_path / f"boundary_{field}"
    audit.build_audit_package(
        network_dir=source,
        output_dir=output,
        resamples=20,
    )
    manifest_path = output / "priority_boundary_audit_manifest.json"
    manifest = audit._read_json(manifest_path)
    manifest[field] = value
    manifest["package_signature"] = audit._canonical_sha256(
        audit._manifest_signature_payload(manifest)
    )
    audit._write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="Sémantique de l'empreinte"):
        audit.validate_audit_package(output)


def test_source_change_between_initial_hash_and_reconstruction_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    source = tmp_path / "network_toctou"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    output = tmp_path / "boundary_toctou"
    audit.build_audit_package(
        network_dir=source,
        output_dir=output,
        resamples=20,
    )
    original_reconstruct = audit._reconstructed_artifact_hashes

    def mutate_ignored_source_then_reconstruct(**kwargs):
        design_path = source / "scenario_design.csv"
        source_rows = audit._read_csv(design_path)
        for row in source_rows:
            row["ignored_after_initial_hash"] = "same_scientific_content"
        audit._write_csv(design_path, source_rows)
        return original_reconstruct(**kwargs)

    monkeypatch.setattr(
        audit,
        "_reconstructed_artifact_hashes",
        mutate_ignored_source_then_reconstruct,
    )
    with pytest.raises(ValueError, match="changé entre.*reconstruction"):
        audit.validate_audit_package(output)


def test_external_crn_summary_mutation_during_audit_aborts_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    rows, selected, _meta, ranking, design = _fixture()
    summaries: dict[int, Path] = {}
    run_dirs: dict[int, Path] = {}
    for seed in range(1001, 1031):
        run_dir = tmp_path / f"retained_seed_{seed}"
        summary = run_dir / "summaries" / "first_simulation_summary.json"
        _write_json(
            summary,
            {"policy": {"common_random_numbers": True, "seed": seed}},
        )
        summaries[seed] = summary
        run_dirs[seed] = run_dir
    for row in rows:
        row.pop("resolved_common_random_numbers")
        row.pop("resolved_random_seed")
        row["run_dir"] = str(run_dirs[int(row["seed"])])
    source = tmp_path / "network_external_crn"
    _write_complete_network_source(
        source,
        rows=rows,
        selected=selected,
        ranking=ranking,
        design=design,
    )
    original_analyze = audit.analyze_priority_boundary

    def analyze_then_mutate(**kwargs):
        result = original_analyze(**kwargs)
        _write_json(
            summaries[1001],
            {"policy": {"common_random_numbers": False, "seed": 1001}},
        )
        return result

    monkeypatch.setattr(audit, "analyze_priority_boundary", analyze_then_mutate)
    monkeypatch.setattr(audit, "BOOTSTRAP_RESAMPLE_COUNT", 20)
    output = tmp_path / "must_not_be_published"
    with pytest.raises(RuntimeError, match="preuve CRN externe a changé"):
        audit.build_audit_package(
            network_dir=source,
            output_dir=output,
            resamples=20,
        )
    assert not output.exists()
    assert not list(tmp_path.glob(f".{output.name}.staging-*"))


def test_external_crn_summary_seed_must_match_metric_row(
    tmp_path: Path,
):
    rows, _selected, _meta, _ranking, _design = _fixture()
    row = rows[0]
    row.pop("resolved_common_random_numbers")
    row.pop("resolved_random_seed")
    run_dir = tmp_path / "wrong_seed_run"
    _write_json(
        run_dir / "summaries" / "first_simulation_summary.json",
        {"policy": {"common_random_numbers": True, "seed": 999}},
    )
    row["run_dir"] = str(run_dir)
    resolved, provenance = audit._resolve_common_random_numbers(row)
    assert not resolved
    assert provenance["summary_policy_seed"] == 999
    assert provenance["summary_policy_seed"] != provenance["seed"]
