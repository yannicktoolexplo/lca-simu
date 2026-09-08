from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    DEFAULT_CONFIG,
    build_excel_runtime_comparison,
    build_sdd_site_map_payload,
    build_supply_geo_case,
    indicator_summary_rows,
    load_brightway_component_impacts,
    load_stelia_raw_climate_reference,
    supplier_context_payload,
)


@pytest.fixture(scope="module")
def supply_case_result(tmp_path_factory: pytest.TempPathFactory):
    return build_supply_geo_case(output_dir=tmp_path_factory.mktemp("supply_geo_case") / "supply_case")


def test_brightway_component_summary_does_not_add_one_year_and_lifetime_use(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Master"
    sheet.append([
        "Type",
        "Production",
        "Utilisation 1 an",
        "Utilisation 7 ans",
        "Fin de vie",
        "Fin de vie",
    ])
    sheet.append(["Systeme", "Siege", "Usage", "Usage", "Enfouissement", "Recyclage"])
    sheet.append(["Composant", "Production", "Kerosene", "Kerosene", "Decharge", "Credit"])
    sheet.append(["EF 3.0 Climate Change - total [kg CO2 eq.]", 10.0, 2.0, 14.0, 1.0, -4.0])
    path = tmp_path / "lca.xlsx"
    workbook.save(path)

    impacts, climate = load_brightway_component_impacts(path)
    summary = indicator_summary_rows(impacts)

    assert len(impacts) == 3
    assert len(climate) == 3
    assert {row["family"] for row in impacts} == {
        "Production",
        "Utilisation 7 ans",
        "Fin de vie",
    }
    assert {row["system"] for row in impacts if row["family"] == "Fin de vie"} == {"Enfouissement"}
    assert summary[0]["sum_value"] == 25.0
    assert load_stelia_raw_climate_reference(path) == {
        "impact_total_kgco2e": 25.0,
        "impact_without_use_kgco2e": 11.0,
        "use_phase_kgco2e": 14.0,
    }


def test_excel_comparison_excludes_imported_recycling_credit_from_corrected_cycle() -> None:
    reference = [{
        "short_label": "Climate Change - total",
        "impact_total_person_equivalent": 310.0,
        "impact_without_use_person_equivalent": 110.0,
        "use_phase_person_equivalent": 200.0,
    }]
    exact = [
        {"scenario_id": "current_export", "root_activity_id": "production", "score_kgco2e": 100.0},
        {"scenario_id": "current_export", "root_activity_id": "lifecycle", "score_kgco2e": 1000.0},
        {
            "scenario_id": "current_export",
            "root_activity_id": "lifecycle_excel_aligned",
            "score_kgco2e": 250.0,
            "excel_use_phase_kgco2e_added": 200.0,
        },
    ]

    rows = build_excel_runtime_comparison(
        reference,
        exact,
        normalization_factor=1.0,
        raw_climate_reference={
            "impact_total_kgco2e": 310.0,
            "impact_without_use_kgco2e": 110.0,
            "use_phase_kgco2e": 200.0,
        },
    )
    by_scope = {row["scope_id"]: row for row in rows}

    assert by_scope["lifecycle_without_use"]["runtime_kgco2e"] == 50.0
    assert by_scope["lifecycle_without_use"]["alignment_status"] == (
        "ecarte_credit_recyclage_incompatible_cutoff"
    )
    assert by_scope["lifecycle_excel_aligned"]["runtime_kgco2e"] == 300.0
    assert by_scope["lifecycle_excel_aligned"]["alignment_status"] == "ecart_modere_2_20_pct"


def test_supply_geo_case_builds_primary_run_package(supply_case_result) -> None:
    result = supply_case_result
    summary = result.summary

    assert summary["schema_version"] == "poc2026.supply_geo_case.v1"
    assert summary["counts"]["source_records"] == 175
    assert summary["counts"]["usable_records"] == 170
    assert summary["counts"]["excluded_records"] == 5
    assert summary["excluded_record_indexes"] == [127, 156, 157, 174, 175]
    assert summary["counts"]["primary_paths"] == 172
    assert summary["counts"]["primary_lane_rows"] == 172 * 4
    assert summary["sdd_brightway_coupling"]["available"] is True
    assert abs(summary["mass"]["allocation_gap_kg"]) <= 1e-6

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "poc2026.supply_geo_case.v1"
    assert manifest["capabilities"]["primary_supply_paths"] is True
    assert manifest["capabilities"]["allocated_path_mass"] is True
    assert manifest["capabilities"]["transport_weather_risk"] is True
    assert manifest["capabilities"]["node_operational_state"] is True
    assert manifest["capabilities"]["operational_event_lineage"] is True
    assert manifest["capabilities"]["sdd_stateful_supply_engine"] is True
    assert manifest["capabilities"]["sdd_constrained_resilience"] is True
    assert manifest["capabilities"]["sdd_supply_regimes"] is True
    assert manifest["capabilities"]["sdd_brightway_inventory_delta"] is True
    assert manifest["capabilities"]["sdd_brightway_exchange_delta"] is True
    assert manifest["capabilities"]["sdd_brightway_exchange_lcia"] is True
    assert manifest["capabilities"]["sdd_supply_calibration"] is True
    assert manifest["capabilities"]["sdd_climate_robustness"] is True
    assert manifest["capabilities"]["brightway_supply_lca_source"] is True
    assert manifest["entrypoints"]["dashboard"] == "../maps/supply_geo_base_results_map.html"
    assert manifest["entrypoints"]["transport_weather"] == "../data/transport_weather_risk.csv"
    assert manifest["entrypoints"]["node_operational_state"] == "../data/node_operational_state.csv"
    assert manifest["entrypoints"]["operational_events"] == "../data/operational_event_seed.csv"
    assert manifest["entrypoints"]["sdd_monthly_impacts"] == "../data/sdd_monthly_impacts.csv"
    assert manifest["entrypoints"]["sdd_resilience_resources"] == "../data/sdd_resilience_resources.csv"
    assert manifest["entrypoints"]["sdd_regime_month"] == "../data/sdd_regime_month.csv"
    assert manifest["entrypoints"]["sdd_brightway_inventory_delta"] == "../data/sdd_brightway_inventory_delta.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_delta"] == "../data/sdd_brightway_exchange_delta.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_category_totals"] == "../data/sdd_brightway_exchange_category_totals.csv"
    assert manifest["entrypoints"]["sdd_brightway_top_exchanges"] == "../data/sdd_brightway_top_exchanges.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_lcia"] == "../data/sdd_brightway_exchange_lcia.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_lcia_factors"] == "../data/sdd_brightway_exchange_lcia_factors.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_lcia_category_totals"] == "../data/sdd_brightway_exchange_lcia_category_totals.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_lcia_monthly"] == "../data/sdd_brightway_exchange_lcia_monthly.csv"
    assert manifest["entrypoints"]["sdd_brightway_exchange_lcia_top"] == "../data/sdd_brightway_exchange_lcia_top.csv"
    assert manifest["entrypoints"]["sdd_brightway_monthly"] == "../data/sdd_brightway_monthly.csv"
    assert manifest["entrypoints"]["sdd_brightway_cumulative"] == "../data/sdd_brightway_cumulative.csv"
    assert manifest["entrypoints"]["sdd_aircraft_use_profile"] == "../data/sdd_aircraft_use_profile.csv"
    assert manifest["entrypoints"]["sdd_aircraft_use_components"] == "../data/sdd_aircraft_use_components.csv"
    assert manifest["entrypoints"]["sdd_aircraft_use_monthly"] == "../data/sdd_aircraft_use_monthly.csv"
    assert manifest["entrypoints"]["sdd_aircraft_use_cumulative"] == "../data/sdd_aircraft_use_cumulative.csv"
    assert manifest["entrypoints"]["sdd_brightway_mechanism_totals"] == "../data/sdd_brightway_mechanism_totals.csv"
    assert manifest["entrypoints"]["sdd_brightway_top_sites"] == "../data/sdd_brightway_top_sites.csv"
    assert manifest["entrypoints"]["sdd_brightway_top_components"] == "../data/sdd_brightway_top_components.csv"
    assert manifest["entrypoints"]["sdd_supply_calibration"] == "../data/sdd_supply_calibration.csv"
    assert manifest["entrypoints"]["sdd_climate_robustness_scenarios"] == "../data/sdd_climate_robustness_scenarios.csv"
    assert manifest["entrypoints"]["sdd_climate_robustness_monthly"] == "../data/sdd_climate_robustness_monthly.csv"
    assert manifest["entrypoints"]["scenario_suite"] == "../summaries/scenario_suite.json"
    assert manifest["entrypoints"]["scenario_outputs"] == "../scenarios"
    assert manifest["entrypoints"]["base_results_map"] == "../maps/supply_geo_base_results_map.html"
    assert manifest["entrypoints"]["brightway_component_impacts"] == "../data/brightway_component_impacts.csv"
    assert manifest["entrypoints"]["brightway_supply_alignment"] == "../data/brightway_supply_alignment.csv"
    assert manifest["entrypoints"]["brightway_indicator_unit_views"] == "../data/brightway_indicator_unit_views.csv"
    assert manifest["entrypoints"]["brightway_reference_person_equivalent_results"] == "../data/brightway_reference_person_equivalent_results.csv"
    assert manifest["entrypoints"]["brightway_reference_scenarios"] == "../data/brightway_reference_scenarios.csv"
    assert manifest["entrypoints"]["brightway_parametric_levers"] == "../data/brightway_parametric_levers.csv"
    assert manifest["entrypoints"]["brightway_parametric_sensitivity"] == "../data/brightway_parametric_sensitivity.csv"
    assert manifest["entrypoints"]["brightway_parametric_regional_scenarios"] == "../data/brightway_parametric_regional_scenarios.csv"
    assert manifest["entrypoints"]["brightway_exact_scenario_lcia"] == "../data/brightway_exact_scenario_lcia.csv"
    assert manifest["entrypoints"]["brightway_excel_runtime_comparison"] == "../data/brightway_excel_runtime_comparison.csv"
    assert manifest["entrypoints"]["brightway_excel_original_indicator_comparison"] == "../data/brightway_excel_original_indicator_comparison.csv"
    assert manifest["entrypoints"]["brightway_usage_calibration"] == "../data/brightway_usage_calibration.csv"
    assert manifest["entrypoints"]["brightway_model_summary"] == "../summaries/brightway_model_summary.json"
    assert manifest["entrypoints"]["supplier_context_evidence"] == "../data/supplier_context_evidence.csv"
    assert manifest["entrypoints"]["supplier_context_search_attempts"] == "../data/supplier_context_search_attempts.csv"
    assert manifest["entrypoints"]["supplier_context_search_attempt_history"] == "../data/supplier_context_search_attempt_history.csv"


def test_supplier_context_payload_feeds_site_criticality() -> None:
    site_rows = [
        {
            "site_uid": "supplier-a@@site",
            "name": "Supplier A",
            "roles": "T2",
            "country_code": "FR",
            "lat": 48.0,
            "lon": 2.0,
            "allocated_mass_kg": 10.0,
            "path_count": 1,
        }
    ]
    sdd_node_state = [
        {
            "site_uid": "supplier-a@@site",
            "service_level": 0.92,
            "disruption_index": 0.35,
            "supply_regime_score": 0.5,
            "path_mass_kg": 10.0,
            "month_index": 1,
        }
    ]
    context_summary = [
        {
            "site_uid": "supplier-a@@site",
            "supplier": "Supplier A",
            "documentary_criticality_score": 0.8,
            "observed_fragility_score": 0.8,
            "resilience_evidence_score": 0.1,
            "structural_importance_score": 0.6,
            "weak_signal_score": 0.9,
            "weak_signal_categories": "rupture_approvisionnement|incident_industriel",
            "result_count": 3,
            "source_count": 2,
            "data_confidence_score": 0.7,
            "aerospace_relevance_score": 0.6,
            "top_title": "Supplier A production disruption",
            "top_url": "https://example.com/supplier-a",
            "top_domain": "example.com",
            "context_short_summary": "Signaux faibles: rupture_approvisionnement",
            "context_search_status": "ok",
        }
    ]
    context_results = [
        {
            "site_uid": "supplier-a@@site",
            "result_rank": 1,
            "title": "Supplier A production disruption",
            "domain": "example.com",
            "signal_categories": "rupture_approvisionnement",
        }
    ]
    context_evidence = [
        {
            "site_uid": "supplier-a@@site",
            "supplier": "Supplier A",
            "evidence_category": "incident_industriel",
            "fact_summary": "Arret temporaire de production",
            "publication_date_hint": "2024",
            "source_url": "https://example.com/supplier-a",
            "source_domain": "example.com",
            "source_type": "presse_ou_source_metier",
            "source_quality_score": 0.7,
            "identity_match_score": 0.9,
            "evidence_strength_score": 0.6,
            "verification_status": "indice_fort_a_verifier",
            "potential_sdd_effects": "capacite|delai",
        }
    ]

    context = supplier_context_payload(context_summary, context_results, context_evidence)
    sites = build_sdd_site_map_payload(
        site_rows,
        sdd_node_state,
        event_exposure_rows=[{"label": "Supplier A", "meta": "FR", "value": 2.0, "events": 1}],
        sdd_brightway_site_impacts=[{"site_uid": "supplier-a@@site", "value": 25.0, "row_count": 2}],
        supplier_context_rows=context["summary_rows"],
    )

    assert context["available"] is True
    assert context["signal_counts"][0]["label"] == "rupture_approvisionnement"
    assert len(sites) == 1
    site = sites[0]
    assert site["context_available"] == 1
    assert site["documentary_criticality_score"] == 0.8
    assert site["weak_signal_categories"] == "rupture_approvisionnement|incident_industriel"
    assert site["supplier_criticality_score"] == site["simulation_criticality_score"]
    assert site["exploratory_supplier_criticality_score"] > site["simulation_criticality_score"]
    assert "rupture ou retard" in site["context_signal_label"]
    assert site["criticality_formula_version"] == "supplier_criticality_v3_verified_context_only"
    assert "importance supply" in site["criticality_formula"]
    assert "fragilite documentee" not in site["criticality_contributors"]
    assert site["context_affects_official_score"] == 0
    assert "Facteurs ponderes:" in site["criticality_explanation"]
    assert context["evidence_by_site"]["supplier-a@@site"][0]["publication_date_label"] == "2024"
    expected_hazard = 0.70 * 2.0 / 320.0 + 0.30 * 1.0 / 500.0
    expected_operational_fragility = 0.40 * 0.08 + 0.25 * 0.5 + 0.20 * 0.35
    expected_simulation = 0.30 * 0.6 + 0.25 * expected_hazard + 0.35 * expected_operational_fragility
    expected_exploratory = (expected_simulation + 0.10 * 0.8) * (1.0 - 0.10 * 0.1)
    assert site["hazard_exposure_score"] == pytest.approx(expected_hazard, abs=1e-4)
    assert site["operational_fragility_score"] == pytest.approx(expected_operational_fragility, abs=1e-4)
    assert site["simulation_criticality_score"] == pytest.approx(expected_simulation, abs=1e-4)
    assert site["supplier_criticality_score"] == pytest.approx(expected_simulation, abs=1e-4)
    assert site["exploratory_supplier_criticality_score"] == pytest.approx(expected_exploratory, abs=1e-4)

    high_acv_site = build_sdd_site_map_payload(
        site_rows,
        sdd_node_state,
        event_exposure_rows=[{"label": "Supplier A", "meta": "FR", "value": 2.0, "events": 1}],
        sdd_brightway_site_impacts=[{"site_uid": "supplier-a@@site", "value": 999999.0, "row_count": 2}],
        supplier_context_rows=context["summary_rows"],
    )[0]
    assert high_acv_site["supplier_criticality_score"] == site["supplier_criticality_score"]
    assert high_acv_site["sdd_acv_delta_kgco2e"] != site["sdd_acv_delta_kgco2e"]

    no_resilience_summary = [{**context_summary[0], "resilience_evidence_score": 0.0}]
    no_resilience_site = build_sdd_site_map_payload(
        site_rows,
        sdd_node_state,
        event_exposure_rows=[{"label": "Supplier A", "meta": "FR", "value": 2.0, "events": 1}],
        supplier_context_rows=supplier_context_payload(no_resilience_summary, context_results)["summary_rows"],
    )[0]
    assert no_resilience_site["supplier_criticality_score"] == site["supplier_criticality_score"]
    assert no_resilience_site["exploratory_supplier_criticality_score"] > site["exploratory_supplier_criticality_score"]

    approved_summary = [
        {
            **context_summary[0],
            "verified_evidence_count": 1,
            "model_activation_status": "approved",
        }
    ]
    approved_site = build_sdd_site_map_payload(
        site_rows,
        sdd_node_state,
        event_exposure_rows=[{"label": "Supplier A", "meta": "FR", "value": 2.0, "events": 1}],
        supplier_context_rows=supplier_context_payload(approved_summary, context_results)["summary_rows"],
    )[0]
    assert approved_site["context_affects_official_score"] == 1
    assert approved_site["supplier_criticality_score"] == pytest.approx(expected_exploratory, abs=1e-4)


def test_supply_geo_case_primary_path_invariants(supply_case_result) -> None:
    result = supply_case_result
    data_dir = result.output_root / "data"
    paths = pd.read_csv(data_dir / "primary_supply_paths.csv")
    nodes = pd.read_csv(data_dir / "primary_supply_nodes.csv")
    lanes = pd.read_csv(data_dir / "primary_supply_lanes.csv")

    assert set(paths["path_type"]) == {"primary"}
    assert paths["path_id"].is_unique
    assert (paths["path_mass_kg"] >= 0.0).all()
    assert (paths["total_route_km"] >= 0.0).all()
    assert not paths["modes"].isna().any()

    role_counts = nodes.groupby("path_id")["role"].nunique()
    assert (role_counts == 5).all()
    assert set(nodes["role"]) == {"T4", "T3", "T2", "T1", "OEM"}

    lane_counts = lanes.groupby("path_id")["edge"].nunique()
    assert (lane_counts == 4).all()
    assert set(lanes["edge"]) == {"T4->T3", "T3->T2", "T2->T1", "T1->OEM"}
    assert (lanes["distance_km"] >= 0.0).all()
    assert not lanes["modes"].isna().any()

    allocated_by_record = paths.groupby("record_index")["path_mass_kg"].sum().round(6)
    component_by_record = paths.groupby("record_index")["component_mass_kg"].first().round(6)
    pd.testing.assert_series_equal(allocated_by_record, component_by_record, check_names=False)


def test_supply_geo_case_weather_events_are_generated_from_weather_curves(supply_case_result) -> None:
    result = supply_case_result
    data_dir = result.output_root / "data"
    weather = pd.read_csv(data_dir / "site_weather_driver.csv")
    events = pd.read_csv(data_dir / "supplier_risk_event_seed.csv")
    transport_weather = pd.read_csv(data_dir / "transport_weather_risk.csv")
    node_ops = pd.read_csv(data_dir / "node_operational_state.csv")
    op_events = pd.read_csv(data_dir / "operational_event_seed.csv")
    sdd_node = pd.read_csv(data_dir / "sdd_node_state.csv")
    sdd_lane = pd.read_csv(data_dir / "sdd_lane_state.csv")
    sdd_flow = pd.read_csv(data_dir / "sdd_flow_state.csv")
    sdd_monthly = pd.read_csv(data_dir / "sdd_monthly_impacts.csv")
    sdd_cumulative = pd.read_csv(data_dir / "sdd_cumulative_impacts.csv")
    sdd_resilience = pd.read_csv(data_dir / "sdd_resilience_resources.csv")
    sdd_regime_month = pd.read_csv(data_dir / "sdd_regime_month.csv")
    sdd_bw_inventory = pd.read_csv(data_dir / "sdd_brightway_inventory_delta.csv")
    sdd_bw_exchange = pd.read_csv(data_dir / "sdd_brightway_exchange_delta.csv")
    sdd_bw_exchange_categories = pd.read_csv(data_dir / "sdd_brightway_exchange_category_totals.csv")
    sdd_bw_top_exchanges = pd.read_csv(data_dir / "sdd_brightway_top_exchanges.csv")
    sdd_bw_exchange_lcia = pd.read_csv(data_dir / "sdd_brightway_exchange_lcia.csv")
    sdd_bw_exchange_lcia_factors = pd.read_csv(data_dir / "sdd_brightway_exchange_lcia_factors.csv")
    sdd_bw_exchange_lcia_categories = pd.read_csv(data_dir / "sdd_brightway_exchange_lcia_category_totals.csv")
    sdd_bw_exchange_lcia_monthly = pd.read_csv(data_dir / "sdd_brightway_exchange_lcia_monthly.csv")
    sdd_bw_exchange_lcia_top = pd.read_csv(data_dir / "sdd_brightway_exchange_lcia_top.csv")
    sdd_bw_exchange_lcia_status = pd.read_csv(data_dir / "sdd_brightway_exchange_lcia_status.csv")
    sdd_bw_monthly = pd.read_csv(data_dir / "sdd_brightway_monthly.csv")
    sdd_bw_cumulative = pd.read_csv(data_dir / "sdd_brightway_cumulative.csv")
    sdd_aircraft_use_profile = pd.read_csv(data_dir / "sdd_aircraft_use_profile.csv")
    sdd_aircraft_use_components = pd.read_csv(data_dir / "sdd_aircraft_use_components.csv")
    sdd_aircraft_use_monthly = pd.read_csv(data_dir / "sdd_aircraft_use_monthly.csv")
    sdd_aircraft_use_cumulative = pd.read_csv(data_dir / "sdd_aircraft_use_cumulative.csv")
    sdd_bw_mechanisms = pd.read_csv(data_dir / "sdd_brightway_mechanism_totals.csv")
    sdd_bw_sites = pd.read_csv(data_dir / "sdd_brightway_top_sites.csv")
    sdd_bw_components = pd.read_csv(data_dir / "sdd_brightway_top_components.csv")
    sdd_supply_calibration = pd.read_csv(data_dir / "sdd_supply_calibration.csv")
    sdd_robustness = pd.read_csv(data_dir / "sdd_climate_robustness_scenarios.csv")
    sdd_robustness_monthly = pd.read_csv(data_dir / "sdd_climate_robustness_monthly.csv")
    bw_impacts = pd.read_csv(data_dir / "brightway_component_impacts.csv")
    bw_params = pd.read_csv(data_dir / "brightway_parameters.csv")
    bw_alignment = pd.read_csv(data_dir / "brightway_supply_alignment.csv")
    bw_units = pd.read_csv(data_dir / "brightway_indicator_unit_views.csv")
    bw_ref_pe = pd.read_csv(data_dir / "brightway_reference_person_equivalent_results.csv")
    bw_ref_weighted = pd.read_csv(data_dir / "brightway_reference_weighted_results.csv")
    bw_ref_scenarios = pd.read_csv(data_dir / "brightway_reference_scenarios.csv")
    bw_bom_materials = pd.read_csv(data_dir / "brightway_masterboard_material_summary.csv")
    bw_levers = pd.read_csv(data_dir / "brightway_parametric_levers.csv")
    bw_sensitivity = pd.read_csv(data_dir / "brightway_parametric_sensitivity.csv")
    bw_regional = pd.read_csv(data_dir / "brightway_parametric_regional_scenarios.csv")
    bw_exact = pd.read_csv(data_dir / "brightway_exact_scenario_lcia.csv")
    bw_excel_compare = pd.read_csv(data_dir / "brightway_excel_runtime_comparison.csv")
    bw_excel_indicator_compare = pd.read_csv(data_dir / "brightway_excel_original_indicator_comparison.csv")
    bw_usage = pd.read_csv(data_dir / "brightway_usage_calibration.csv")

    assert not weather.empty
    assert not events.empty
    assert not transport_weather.empty
    assert not node_ops.empty
    assert not op_events.empty
    assert not sdd_node.empty
    assert not sdd_lane.empty
    assert not sdd_flow.empty
    assert len(sdd_monthly) == 240
    assert len(sdd_cumulative) == 240
    assert not sdd_resilience.empty
    assert not sdd_regime_month.empty
    for column in [
        "world_region",
        "weather_profile",
        "climate_progress",
        "warming_delta_c",
        "hazard_intensification_factor",
        "temp_c",
        "humidity_pct",
        "precip_mm",
        "wind_ms",
        "heat_index_c",
        "hurricane",
    ]:
        assert column in weather.columns
    assert weather["humidity_pct"].between(0.0, 100.0).all()
    assert (weather["precip_mm"] >= 0.0).all()
    assert (weather["wind_ms"] >= 0.0).all()
    assert weather["world_region"].nunique() >= 3
    assert weather["weather_profile"].nunique() >= 3
    first_weather_window = weather.loc[weather["month_index"].between(1, 12)]
    last_weather_window = weather.loc[weather["month_index"].between(229, 240)]
    assert last_weather_window["warming_delta_c"].mean() > first_weather_window["warming_delta_c"].mean()
    assert last_weather_window["hazard_intensification_factor"].mean() > first_weather_window["hazard_intensification_factor"].mean()

    assert set(events["source_weather_column"]).issubset({"temp_c", "precip_mm", "wind_ms"})
    assert {
        "climate_progress",
        "warming_delta_c",
        "hazard_intensification_factor",
        "capacity_loss_coeff",
        "lead_time_gain_coeff",
        "scrap_gain_coeff",
        "effective_capacity_loss_pct",
        "effective_lead_time_gain_pct",
        "effective_scrap_gain_pct",
        "capacity_calibration_status",
        "lead_time_calibration_status",
        "scrap_calibration_status",
        "calibration_status",
        "calibration_profile_id",
    }.issubset(events.columns)
    assert {"dans_plage", "a_revoir_haut", "a_revoir_bas"}.intersection(set(events["calibration_status"]))
    assert set(events["event_type"]).issubset({"heatwave", "drought", "storm", "hurricane", "cold"})
    assert (events["intensity"] > 0.0).all()
    assert events["capacity_multiplier"].between(0.0, 1.0).all()
    assert (events["lead_time_multiplier"] >= 1.0).all()
    assert set(
        [
            "route_region",
            "climate_progress",
            "warming_delta_c",
            "maritime_hazard_intensification_factor",
            "maritime_risk_index",
            "delay_multiplier",
            "capacity_multiplier",
        ]
    ).issubset(transport_weather.columns)
    assert (transport_weather["maritime_risk_index"] >= 0.0).all()
    assert (transport_weather["delay_multiplier"] >= 1.0).all()
    assert set(
        [
            "source_driver_types",
            "source_environmental_event_ids",
            "source_transport_flow_uids",
            "operational_event_labels",
            "raw_capacity_applied",
            "raw_lead_time_multiplier",
            "raw_scrap_multiplier",
            "climate_service_loss_pressure",
            "climate_service_capacity_penalty",
            "climate_service_lead_penalty",
            "climate_service_scrap_penalty",
            "service_loss_calibration_profile",
            "capacity_applied",
            "capacity_degraded_threshold",
            "capacity_support_threshold",
            "lead_delay_threshold",
            "scrap_quality_threshold",
            "logistics_risk_threshold",
            "lead_time_multiplier",
            "service_proxy_pct",
            "supply_regime",
            "supply_regime_label",
            "supply_regime_score",
        ]
    ).issubset(node_ops.columns)
    assert node_ops["climate_service_loss_pressure"].between(0.0, 0.16).all()
    late_nodes = node_ops.loc[node_ops["month_index"].between(181, 240)]
    early_nodes = node_ops.loc[node_ops["month_index"].between(1, 60)]
    assert late_nodes["climate_service_loss_pressure"].mean() > early_nodes["climate_service_loss_pressure"].mean()
    assert set(["operational_event_type", "source_driver_types", "disruption_index", "supply_regime", "supply_regime_score"]).issubset(op_events.columns)
    assert op_events["source_driver_types"].ne("none").all()
    assert op_events["disruption_index"].between(0.0, 1.0).all()
    assert {
        "scenario_id",
        "stock_end_kg",
        "backlog_end_kg",
        "service_level_without_adaptation",
        "service_level",
        "service_gain_from_adaptation_pp",
        "adaptation_cost_eur",
        "adaptation_co2_proxy_kgco2e",
        "decisions",
        "supply_regime",
        "supply_regime_label",
        "supply_regime_score",
        "parent_sdd_event_ids",
        "root_sdd_event_ids",
        "root_environmental_event_ids",
        "root_transport_flow_uids",
    }.issubset(sdd_node.columns)
    assert sdd_node["parent_sdd_event_ids"].fillna("").ne("").any()
    assert set(sdd_node["scenario_id"]) == {"climat_2026_2046_modere"}
    assert set(sdd_resilience["scenario_id"]) == {"climat_2026_2046_modere"}
    assert (
        sdd_resilience["capacity_boost_used_kg"]
        <= sdd_resilience["capacity_boost_capacity_kg"] + 2e-6
    ).all()
    assert (
        sdd_resilience["backup_used_kg"]
        <= sdd_resilience["backup_capacity_kg"] + 2e-6
    ).all()
    assert (
        sdd_resilience["premium_global_used_kg_km"]
        <= sdd_resilience["premium_global_budget_kg_km"] + 2e-6
    ).all()
    assert (sdd_resilience["backup_qualified"].astype(str).str.lower() == "false").any()
    assert {"transport_risk_index", "delay_multiplier", "capacity_multiplier"}.issubset(sdd_lane.columns)
    assert {"oem_service_level", "sdd_kgCO2e", "surimpact_kgCO2e"}.issubset(sdd_flow.columns)
    assert {"avg_supply_regime_score", "dominant_supply_regime", "dominant_supply_regime_label", "supply_regime_crise_count"}.issubset(sdd_monthly.columns)
    assert {
        "month_index",
        "supply_regime",
        "supply_regime_label",
        "node_count",
        "path_mass_kg",
        "avg_service_level",
        "avg_disruption_index",
        "backlog_kg",
    }.issubset(sdd_regime_month.columns)
    assert node_ops["supply_regime_score"].between(0.0, 1.0).all()
    assert sdd_node["supply_regime_score"].between(0.0, 1.0).all()
    assert sdd_monthly["avg_supply_regime_score"].between(0.0, 1.0).all()
    assert sdd_regime_month["supply_regime"].nunique() >= 3
    assert (sdd_regime_month["node_count"] > 0).all()
    assert (sdd_monthly["sdd_kgCO2e"] >= sdd_monthly["td_dlca_kgCO2e"]).all()
    assert sdd_cumulative["sdd_cumulative"].iloc[-1] >= sdd_cumulative["td_dlca_cumulative"].iloc[-1]
    assert not sdd_bw_inventory.empty
    assert not sdd_bw_exchange.empty
    assert not sdd_bw_exchange_categories.empty
    assert not sdd_bw_top_exchanges.empty
    assert not sdd_bw_exchange_lcia.empty
    assert not sdd_bw_exchange_lcia_factors.empty
    assert not sdd_bw_exchange_lcia_categories.empty
    assert len(sdd_bw_exchange_lcia_monthly) == 240
    assert not sdd_bw_exchange_lcia_top.empty
    assert not sdd_bw_exchange_lcia_status.empty
    assert len(sdd_bw_monthly) == 240
    assert len(sdd_bw_cumulative) == 240
    assert len(sdd_aircraft_use_profile) == 1
    assert len(sdd_aircraft_use_components) == 3
    assert len(sdd_aircraft_use_monthly) == 240
    assert len(sdd_aircraft_use_cumulative) == 240
    assert sdd_aircraft_use_profile.iloc[0]["lifetime_months"] == 84
    assert sdd_aircraft_use_profile.iloc[0]["full_lifetime_use_kgco2e_per_seat"] == pytest.approx(460797.367595)
    assert sdd_aircraft_use_monthly.iloc[-1]["active_seat_equivalent"] <= 84.0
    assert sdd_aircraft_use_monthly.iloc[-1]["calendar_use_kgco2e"] > 0.0
    assert not sdd_bw_mechanisms.empty
    assert not sdd_bw_sites.empty
    assert not sdd_bw_components.empty
    assert not sdd_supply_calibration.empty
    assert {
        "event_type",
        "weather_profile",
        "world_region",
        "event_count",
        "out_of_range_share_pct",
        "dominant_calibration_status",
    }.issubset(sdd_supply_calibration.columns)
    assert sdd_supply_calibration["event_count"].gt(0).all()
    assert {
        "scenario_id",
        "month_index",
        "path_id_sample",
        "sdd_event_join_key_sample",
        "role",
        "site_uid",
        "mechanism",
        "inventory_delta_type",
        "amount_delta",
        "amount_unit",
        "role_scope_share_avg",
        "delta_kgco2e",
        "include_in_dynamic_acv",
        "source_environmental_event_count",
        "source_environmental_event_sample",
        "calibration_source",
        "confidence",
    }.issubset(sdd_bw_inventory.columns)
    assert sdd_bw_inventory["role_scope_share_avg"].between(0.0, 1.0).all()
    assert {
        "scenario_id",
        "month_index",
        "site_uid",
        "role",
        "mechanism",
        "activity_name",
        "exchange_name",
        "exchange_reference_product",
        "exchange_category",
        "exchange_unit",
        "delta_amount",
        "delta_kgco2e",
        "mapping_status",
        "lcia_allocation_method",
    }.issubset(sdd_bw_exchange.columns)
    assert set(sdd_bw_inventory["scenario_id"]) == {"climat_2026_2046_modere"}
    assert set(sdd_bw_exchange["scenario_id"]) == {"climat_2026_2046_modere"}
    assert {"mapped_exchange", "virtual_exchange_proxy"}.intersection(set(sdd_bw_exchange["mapping_status"]))
    assert {"material", "energy", "transport"}.intersection(set(sdd_bw_exchange["exchange_category"]))
    assert {"exchange_category", "mapping_status", "delta_kgco2e"}.issubset(sdd_bw_exchange_categories.columns)
    assert {"activity_name", "exchange_name", "delta_kgco2e"}.issubset(sdd_bw_top_exchanges.columns)
    assert {
        "quantity_delta_amount",
        "allocated_delta_kgco2e",
        "exact_unit_score_kgco2e_per_exchange_unit",
        "exact_delta_kgco2e",
        "lcia_status",
    }.issubset(sdd_bw_exchange_lcia.columns)
    assert (sdd_bw_exchange_lcia["exact_delta_kgco2e"].fillna(0).abs().sum() > 0)
    assert {"exact_lcia_factor"}.issubset(set(sdd_bw_exchange_lcia_factors["lcia_status"]))
    assert {"calibrated_sdd_proxy_not_exact"}.issubset(set(sdd_bw_exchange_lcia_factors["lcia_status"]))
    assert {"exchange_category", "allocated_delta_kgco2e", "exact_delta_kgco2e"}.issubset(sdd_bw_exchange_lcia_categories.columns)
    assert {"month_index", "allocated_delta_kgco2e", "exact_delta_kgco2e"}.issubset(sdd_bw_exchange_lcia_monthly.columns)
    assert {"activity_name", "exchange_name", "exact_delta_kgco2e"}.issubset(sdd_bw_exchange_lcia_top.columns)
    assert sdd_bw_exchange_lcia_status["status"].iloc[0] == "ok"
    assert {
        "backup_material",
        "scrap_rework",
        "scrap_treatment",
        "recycling_credit",
        "capacity_energy",
        "quality_rework",
        "maintenance",
    }.issubset(set(sdd_bw_mechanisms["mechanism"]))
    recycling_credit = sdd_bw_mechanisms.loc[sdd_bw_mechanisms["mechanism"].eq("recycling_credit")].iloc[0]
    assert recycling_credit["delta_kgco2e"] < 0
    included_mask = sdd_bw_inventory["include_in_dynamic_acv"].astype(str).str.lower().isin({"true", "1"})
    ledger_by_month = sdd_bw_inventory.loc[included_mask].groupby("month_index")["delta_kgco2e"].sum()
    monthly_by_month = sdd_bw_monthly.set_index("month_index")["sdd_inventory_delta_kgco2e"]
    reconciliation_gap = (monthly_by_month - ledger_by_month.reindex(monthly_by_month.index, fill_value=0.0)).abs().max()
    assert reconciliation_gap < 1e-4
    exchange_by_month = sdd_bw_exchange.groupby("month_index")["delta_kgco2e"].sum()
    exchange_reconciliation_gap = (monthly_by_month - exchange_by_month.reindex(monthly_by_month.index, fill_value=0.0)).abs().max()
    assert exchange_reconciliation_gap < 1e-4
    assert (sdd_bw_monthly["production_dynamic_kgco2e"] >= sdd_bw_monthly["production_static_kgco2e"]).all()
    assert not sdd_robustness.empty
    assert len(sdd_robustness_monthly) == 720
    assert {"climat_stationnaire", "climat_2026_2046_modere", "climat_degrade"}.issubset(set(sdd_robustness["scenario_id"]))
    assert {
        "scenario_comparison_status",
        "service_without_adaptation_last60_pct",
        "service_after_adaptation_last60_pct",
        "service_gain_last60_pp",
        "unmet_demand_cumulative_without_adaptation_kg",
        "unmet_demand_cumulative_after_adaptation_kg",
        "adaptation_cost_cumulative_eur",
        "adaptation_co2_proxy_cumulative_kgco2e",
        "capacity_boost_saturated_pool_months",
        "backup_saturated_pool_months",
        "premium_saturated_months",
        "service_loss_vs_stationary_last60_pp",
    }.issubset(sdd_robustness.columns)
    assert set(sdd_robustness["scenario_comparison_status"]) == {"ordre_sdd_coherent"}
    ordered = sdd_robustness.sort_values("scenario_order_index")
    assert ordered["service_without_adaptation_last60_pct"].is_monotonic_decreasing
    assert ordered["service_after_adaptation_last60_pct"].is_monotonic_decreasing
    assert ordered["unmet_demand_cumulative_without_adaptation_kg"].is_monotonic_increasing
    assert ordered["estimated_acv_delta_cumulative_kgco2e"].is_monotonic_increasing
    assert (
        ordered["unmet_demand_cumulative_after_adaptation_kg"]
        <= ordered["unmet_demand_cumulative_without_adaptation_kg"]
    ).all()
    assert (ordered["service_gain_last60_pp"] > 0).all()
    moderate = sdd_robustness.loc[sdd_robustness["scenario_id"].eq("climat_2026_2046_modere")].iloc[0]
    degraded = sdd_robustness.loc[sdd_robustness["scenario_id"].eq("climat_degrade")].iloc[0]
    assert moderate["ops_disruption_last60"] > moderate["ops_disruption_first60"]
    assert degraded["estimated_acv_delta_cumulative_kgco2e"] > moderate["estimated_acv_delta_cumulative_kgco2e"]
    assert degraded["service_loss_vs_stationary_last60_pp"] > moderate["service_loss_vs_stationary_last60_pp"]
    assert "proxy_unmapped" not in set(sdd_bw_exchange["mapping_status"])
    assert not bw_impacts.empty
    assert not bw_params.empty
    assert not bw_alignment.empty
    assert {"system", "component", "climate_kgco2e"}.issubset(bw_impacts.columns)
    assert {"name", "amount", "parameter_family"}.issubset(bw_params.columns)
    assert {"path_id", "match_level", "brightway_climate_kgco2e"}.issubset(bw_alignment.columns)
    assert not bw_units.empty
    assert {"raw_unit", "person_equivalent_value", "normalization_status"}.issubset(bw_units.columns)
    assert (bw_units["normalization_status"] == "normalized_ef30_person_equivalent").any()
    assert not bw_ref_pe.empty
    assert not bw_ref_weighted.empty
    assert not bw_ref_scenarios.empty
    assert not bw_bom_materials.empty
    climate_ref = bw_ref_pe.loc[bw_ref_pe["short_label"].eq("Climate Change - total")].iloc[0]
    assert abs(climate_ref["impact_total_person_equivalent"] - 57.2691147164561) < 1e-6
    assert {"without_ife", "all_fr"}.issubset(set(bw_ref_scenarios["scenario_id"]))
    assert not bw_levers.empty
    assert not bw_sensitivity.empty
    assert not bw_regional.empty
    assert not bw_exact.empty
    assert not bw_excel_compare.empty
    assert len(bw_excel_indicator_compare) == 16
    assert not bw_usage.empty
    assert {"lever_id", "parameter_count", "affected_exchange_count", "abs_delta_amount_sum"}.issubset(bw_levers.columns)
    assert {"lever_id", "activity_name", "exchange_name", "delta_amount"}.issubset(bw_sensitivity.columns)
    assert {"scenario_id", "elec_switch_param", "al_switch_param", "foreground_amount_index"}.issubset(bw_regional.columns)
    assert {"france_first", "europe_first", "fully_globalized"}.issubset(set(bw_regional["scenario_id"]))
    assert {"current_export", "france_first", "europe_first", "fully_globalized"}.issubset(set(bw_exact["scenario_id"]))
    production_exact = bw_exact.loc[(bw_exact["scenario_id"].eq("current_export")) & (bw_exact["root_activity_id"].eq("production"))].iloc[0]
    assert abs(production_exact["score_kgco2e"] - 2449.945067684) < 1e-6
    aligned_exact = bw_exact.loc[(bw_exact["scenario_id"].eq("current_export")) & (bw_exact["root_activity_id"].eq("lifecycle_excel_aligned"))].iloc[0]
    assert abs(aligned_exact["score_kgco2e"] - 462846.896821319) < 1e-6
    assert {"production_without_use", "lifecycle_total", "lifecycle_excel_aligned"}.issubset(set(bw_excel_compare["scope_id"]))
    lifecycle_compare = bw_excel_compare.loc[bw_excel_compare["scope_id"].eq("lifecycle_total")].iloc[0]
    assert lifecycle_compare["alignment_status"] == "ecarte_inventaire_usage_incompatible"
    aligned_compare = bw_excel_compare.loc[bw_excel_compare["scope_id"].eq("lifecycle_excel_aligned")].iloc[0]
    assert aligned_compare["alignment_status"] == "aligne_moins_2_pct"
    usage_compare = bw_excel_compare.loc[bw_excel_compare["scope_id"].eq("use_phase_calibrated")].iloc[0]
    assert usage_compare["alignment_status"] == "identique_par_construction"
    assert not bool(usage_compare["independent_validation"])
    assert {"EU-28: Kerosene / Jet A1 at refinery Sphera", "GLO: Cargo plane, 65 t payload Sphera <u-so>"}.issubset(set(bw_usage["component"]))


def test_supply_geo_case_dashboard_exports_plotly_tabs(supply_case_result) -> None:
    result = supply_case_result
    base_results_map = result.output_root / "maps" / "supply_geo_base_results_map.html"
    stale_dashboard = result.output_root / "maps" / "supply_geo_results_dashboard.html"
    stale_sdd_map = result.output_root / "maps" / "supply_geo_sdd_results_map.html"
    kpis = result.output_root / "summaries" / "general_kpis.json"

    assert base_results_map.exists()
    assert not stale_dashboard.exists()
    assert not stale_sdd_map.exists()
    assert kpis.exists()
    map_html = base_results_map.read_text(encoding="utf-8")
    assert "const DATA_RAW" in map_html
    assert "SDD_MAP_PAYLOAD" in map_html
    assert "poc2026.supply_geo_case.base_map_sdd_overlay.v2" in map_html
    assert "poc2026.supply_geo_case.click_details.v2" in map_html
    assert "BASE_DASHBOARD_PAYLOAD" in map_html
    assert "renderSddSites" in map_html
    assert "renderBaseDashboard" in map_html
    assert "renderSddLanes" in map_html
    assert "renderWeatherMap" in map_html
    assert "renderOperationsMap" in map_html
    assert "renderAcvMap" in map_html
    assert "renderCriticalityMap" in map_html
    assert "renderSddCascades" in map_html
    assert "data-sdd-view=\"source\"" in map_html
    assert "data-sdd-view=\"weather\"" in map_html
    assert "data-sdd-view=\"operations\"" in map_html
    assert "data-sdd-view=\"acv\"" in map_html
    assert "data-sdd-view=\"criticality\"" in map_html
    assert "data-sdd-view=\"cascades\"" in map_html
    assert "data-sdd-view=\"resilience\"" in map_html
    assert "data-sdd-view=\"aircraft_use\"" in map_html
    assert "data-sdd-view=\"dashboard\"" in map_html
    assert "sddCascadePanel" in map_html
    assert "sddCascadeSankeyPlot" in map_html
    assert "sddCascadeTimelinePlot" in map_html
    assert "renderSelectedCascadeMap" in map_html
    assert "Scenarios et resilience" in map_html
    assert "Utilisation du siege dans l'avion" in map_html
    assert "sddResiliencePanel" in map_html
    assert "sddResilienceServicePlot" in map_html
    assert "sddResilienceBacklogPlot" in map_html
    assert "sddResilienceResourcesPlot" in map_html
    assert "sddResilienceCostCo2Plot" in map_html
    assert "sddResilienceScenarioComparisonPlot" in map_html
    assert "sddResilienceSaturationPlot" in map_html
    assert "renderScenarioResilience" in map_html
    assert "baseMapKpiCumulativePlot" in map_html
    assert "baseMapKpiWeatherPlot" in map_html
    assert "baseMapKpiOpsPlot" in map_html
    assert "baseMapKpiMaritimePlot" in map_html
    assert "baseMapKpiEventPlot" in map_html
    assert "baseMapKpiSddTierPlot" in map_html
    assert "baseMapKpiSddRegimePlot" in map_html
    assert "baseMapKpiSddImpactPlot" in map_html
    assert "baseMapKpiSddAcvStaticDynamicPlot" in map_html
    assert "baseMapKpiSddAcvDeltaMechanismPlot" in map_html
    assert "baseMapKpiSddAcvExchangeCategoryPlot" in map_html
    assert "baseMapKpiSddAcvTopExchangesPlot" in map_html
    assert "baseMapKpiSddAcvExchangeExactMonthlyPlot" in map_html
    assert "baseMapKpiSddAcvExchangeExactTopPlot" in map_html
    assert "baseMapKpiSddAcvSeatEquivalentPlot" in map_html
    assert "baseMapKpiSddAcvTopComponentsPlot" in map_html
    assert "baseMapKpiSddAcvTopSitesPlot" in map_html
    assert "baseMapKpiLedgerMappingPlot" in map_html
    assert "baseMapKpiLedgerCausePlot" in map_html
    assert "baseMapKpiLedgerTable" in map_html
    assert "baseMapKpiClimateRobustnessPlot" in map_html
    assert "baseMapKpiClimateRobustnessMonthlyPlot" in map_html
    assert "baseMapKpiCalibrationPlot" in map_html
    assert "sddClickPanel" in map_html
    assert "renderSiteClickPanel" in map_html
    assert "Faits et preuves" in map_html
    assert "Date de publication reperee" in map_html
    assert "Type de source" in map_html
    assert "Importance supply" in map_html
    assert "Exposition aux aleas" in map_html
    assert "Fragilite operationnelle" in map_html
    assert "Fragilite documentee" in map_html
    assert "Resilience documentee" in map_html
    assert "Confiance des preuves" in map_html
    assert "safeExternalLink" in map_html
    assert '["http:", "https:"].includes(parsed.protocol)' in map_html
    assert 'rel="noopener noreferrer"' in map_html
    assert "clickedSddObject" in map_html
    assert "nearestSiteFromPoint" in map_html
    assert "sddClickHandlersBound" not in map_html
    assert "Journal de tracabilite SDD -> ACV" in map_html
    assert "Perte service vs stationnaire" in map_html
    assert "Service operationnel climat" in map_html
    assert "Service SDD apres adaptation" in map_html
    assert "renderLedgerTable" in map_html
    assert "baseMapKpiBwClimatePlot" in map_html
    assert "baseMapKpiBwIndicatorPlot" in map_html
    assert "baseMapKpiBwRawIndicatorPlot" in map_html
    assert "baseMapKpiBwUnitCoveragePlot" in map_html
    assert "baseMapKpiBwReferenceWeightedPlot" in map_html
    assert "baseMapKpiBwReferencePhasePlot" in map_html
    assert "baseMapKpiBwReferenceScenarioPlot" in map_html
    assert "baseMapKpiBwReferenceClimateContributorPlot" in map_html
    assert "baseMapKpiBwAlignmentPlot" in map_html
    assert "baseMapKpiBwLeverPlot" in map_html
    assert "baseMapKpiBwSensitivityPlot" in map_html
    assert "baseMapKpiBwSwitchPlot" in map_html
    assert "baseMapKpiBwRegionalScenarioPlot" in map_html
    assert "baseMapKpiBwUsageBreakdownPlot" in map_html
    assert "baseMapKpiBwExactScenarioPlot" in map_html
    assert "baseMapKpiBwAlignedLifecyclePlot" in map_html
    assert "baseMapKpiBwExcelRuntimePlot" in map_html
    assert "Validation Excel" in map_html
    assert "renderExcelValidation" in map_html
    assert "sddExcelIndicatorPePlot" in map_html
    assert "sddExcelValidationTable" in map_html
    assert "L.circleMarker" not in map_html
    embedded_marker = "const BASE_DASHBOARD_PAYLOAD = "
    embedded_start = map_html.index(embedded_marker) + len(embedded_marker)
    embedded_end = map_html.index(";\n(function()", embedded_start)
    embedded_payload = json.loads(map_html[embedded_start:embedded_end])
    assert len(embedded_payload["sdd_brightway"]["monthly"]) == 240
    assert embedded_payload["sdd_regime_month"]
    assert any(row["supply_regime"] == "crise" for row in embedded_payload["sdd_regime_month"])
    assert embedded_payload["sdd_brightway"]["mechanism_totals"]
    assert embedded_payload["sdd_brightway"]["exchange_category_totals"]
    assert embedded_payload["sdd_brightway"]["top_exchanges"]
    assert embedded_payload["sdd_brightway"]["exchange_lcia_monthly"]
    assert embedded_payload["sdd_brightway"]["exchange_lcia_top"]
    assert embedded_payload["sdd_ledger"]["row_counts"]["exchange_delta"] > 0
    assert embedded_payload["sdd_ledger"]["exchange_rows_top"]
    assert embedded_payload["supply_calibration"]
    assert {"cause_meteo_transport", "decision_operationnelle", "effet_physique", "poste_acv", "statut_brightway"}.issubset(
        embedded_payload["sdd_ledger"]["exchange_rows_top"][0]
    )
    assert len(embedded_payload["climate_robustness"]["summary"]) == 3
    assert len(embedded_payload["climate_robustness"]["monthly"]) == 720
    assert len(embedded_payload["scenario_resilience"]["summary"]) == 3
    assert len(embedded_payload["scenario_resilience"]["monthly"]) == 720
    assert embedded_payload["scenario_resilience"]["order_ok"] is True
    sdd_marker = "const SDD_MAP_PAYLOAD = "
    sdd_start = map_html.index(sdd_marker) + len(sdd_marker)
    sdd_end = map_html.index(";\nconst BASE_DASHBOARD_PAYLOAD", sdd_start)
    sdd_payload = json.loads(map_html[sdd_start:sdd_end])
    assert sdd_payload["sites"]
    assert sdd_payload["risk_cascades"]["schema_version"] == "poc2026.supply_geo_case.risk_cascades.v1"
    assert sdd_payload["risk_cascades"]["cascades"]
    assert set(sdd_payload["risk_cascades_by_scenario"]) == {
        "climat_stationnaire",
        "climat_2026_2046_modere",
        "climat_degrade",
    }
    assert sdd_payload["risk_cascades"]["causality_scope"] == "site_month_local_exact_parent_sdd_lineage_and_allocated_acv"
    first_cascade = sdd_payload["risk_cascades"]["cascades"][0]
    assert {"trigger_labels", "operational_event_labels", "decision_labels", "physical_effect_labels", "acv_mechanism_labels"}.issubset(first_cascade)
    assert first_cascade["timeline_steps"]
    assert first_cascade["route_nodes"]
    assert sdd_payload["click_details"]["sites"]
    first_detail = next(iter(sdd_payload["click_details"]["sites"].values()))
    assert first_detail["month_series"]
    assert any("operational_service_proxy_pct" in row for row in first_detail["month_series"])
    assert any("climate_service_loss_pressure_pct" in row for row in first_detail["month_series"])
    assert {"top_causes", "top_decisions", "event_rows", "inventory_rows", "exchange_rows"}.issubset(first_detail)
    assert {
        "weather_exposure_index",
        "weather_event_count",
        "sdd_acv_delta_kgco2e",
        "sdd_acv_row_count",
        "dominant_supply_regime",
        "dominant_supply_regime_label",
        "max_supply_regime_score",
        "tense_or_worse_month_count",
        "crisis_month_count",
    }.issubset(sdd_payload["sites"][0])
    assert any(site["weather_exposure_index"] > 0 for site in sdd_payload["sites"])
    assert any(site["sdd_acv_delta_kgco2e"] > 0 for site in sdd_payload["sites"])

    payload = json.loads(kpis.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "poc2026.supply_geo_case.kpi_dashboard.v1"
    assert payload["cards"]
    assert payload["readiness"]
    assert len(payload["weather_month"]) == 240
    assert len(payload["ops_month"]) == 240
    assert {
        "avg_climate_progress",
        "avg_warming_delta_c",
        "avg_hazard_intensification_factor",
        "avg_temp_c",
        "avg_humidity_pct",
        "avg_precip_mm",
        "avg_wind_ms",
        "avg_hurricane",
    }.issubset(payload["weather_month"][0])
    assert payload["weather_month"][-1]["avg_warming_delta_c"] > payload["weather_month"][0]["avg_warming_delta_c"]
    assert payload["weather_month"][-1]["avg_hazard_intensification_factor"] > payload["weather_month"][0]["avg_hazard_intensification_factor"]
    assert {"event_count", "capacity_multiplier_min", "lead_time_multiplier_max"}.issubset(payload["ops_month"][0])
    assert payload["weather_region"]
    assert payload["weather_profile"]
    assert payload["weather_region_month"]
    assert payload["maritime_month"]
    assert payload["maritime_region"]
    assert payload["node_ops_month"]
    assert payload["node_ops_region"]
    assert payload["node_ops_lineage"]
    assert {"source", "target", "label", "value", "weight", "count"}.issubset(payload["node_ops_lineage"][0])
    assert payload["node_ops_lineage"][0]["value"] > 0
    assert payload["supply_calibration"]
    assert len(payload["sdd_monthly"]) == 240
    assert len(payload["sdd_cumulative"]) == 240
    assert payload["sdd_regime_month"]
    assert payload["sdd_method_comparison"]
    assert payload["sdd_tier_month"]
    assert payload["sdd_brightway"]["summary"]
    assert len(payload["sdd_brightway"]["monthly"]) == 240
    assert len(payload["sdd_brightway"]["cumulative"]) == 240
    assert payload["sdd_brightway"]["mechanism_totals"]
    assert payload["sdd_brightway"]["exchange_category_totals"]
    assert payload["sdd_brightway"]["top_exchanges"]
    assert payload["sdd_brightway"]["exchange_lcia_category_totals"]
    assert payload["sdd_brightway"]["exchange_lcia_monthly"]
    assert payload["sdd_brightway"]["exchange_lcia_top"]
    assert payload["sdd_brightway"]["exchange_lcia_status"]
    assert payload["sdd_brightway"]["site_impacts"]
    assert payload["sdd_brightway"]["top_sites"]
    assert payload["sdd_brightway"]["top_components"]
    assert payload["sdd_ledger"]["row_counts"]["events"] > 0
    assert payload["sdd_ledger"]["event_rows_top"]
    assert payload["sdd_ledger"]["inventory_rows_top"]
    assert payload["sdd_ledger"]["exchange_rows_top"]
    assert payload["climate_robustness"]["summary"]
    assert len(payload["climate_robustness"]["monthly"]) == 720
    assert len(payload["scenario_resilience"]["summary"]) == 3
    assert len(payload["scenario_resilience"]["monthly"]) == 720
    assert payload["scenario_resilience"]["order_ok"] is True
    assert payload["horizon_adaptation"]["available"] is True
    assert payload["horizon_adaptation"]["weather_driver"]
    assert payload["horizon_adaptation"]["reference_cumulative"]
    assert payload["horizon_adaptation"]["event_impact"]
    assert payload["event_month"]
    assert payload["brightway_model"]["available"] is True
    assert payload["brightway_model"]["counts"]["climate_component_rows"] > 0
    assert payload["brightway_model"]["counts"]["parameters"] > 0
    assert payload["brightway_model"]["component_impacts"]
    assert payload["brightway_model"]["indicator_unit_views"]
    assert payload["brightway_model"]["reference_person_equivalent_results"]
    assert payload["brightway_model"]["reference_weighted_results"]
    assert payload["brightway_model"]["reference_scenarios"]
    assert payload["brightway_model"]["supply_alignment"]
    assert payload["brightway_model"]["parametric_levers"]
    assert payload["brightway_model"]["parametric_sensitivity"]
    assert payload["brightway_model"]["parametric_switches"]
    assert payload["brightway_model"]["parametric_regional_scenarios"]
    assert payload["brightway_model"]["exact_scenario_lcia"]
    assert payload["brightway_model"]["excel_runtime_comparison"]
    assert len(payload["brightway_model"]["excel_original_indicator_comparison"]) == 16
    assert payload["brightway_model"]["usage_calibration"]
    assert payload["brightway_model"]["counts"]["parametric_formulas_evaluated"] > 0
    assert payload["brightway_model"]["counts"]["person_equivalent_indicators"] > 0
    assert payload["map_src"].endswith("supply_geo_base_results_map.html")
    assert not payload["map_src"].startswith("C:")


def test_supply_geo_case_default_config_exists() -> None:
    assert DEFAULT_CONFIG.exists()
