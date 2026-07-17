from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import DEFAULT_CONFIG, build_supply_geo_case


def test_supply_geo_case_builds_primary_run_package(tmp_path: Path) -> None:
    result = build_supply_geo_case(output_dir=tmp_path / "supply_case")
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
    assert manifest["capabilities"]["sdd_brightway_inventory_delta"] is True
    assert manifest["capabilities"]["sdd_brightway_exchange_delta"] is True
    assert manifest["capabilities"]["sdd_brightway_exchange_lcia"] is True
    assert manifest["capabilities"]["brightway_supply_lca_source"] is True
    assert manifest["entrypoints"]["dashboard"] == "../maps/supply_geo_base_results_map.html"
    assert manifest["entrypoints"]["transport_weather"] == "../data/transport_weather_risk.csv"
    assert manifest["entrypoints"]["node_operational_state"] == "../data/node_operational_state.csv"
    assert manifest["entrypoints"]["operational_events"] == "../data/operational_event_seed.csv"
    assert manifest["entrypoints"]["sdd_monthly_impacts"] == "../data/sdd_monthly_impacts.csv"
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
    assert manifest["entrypoints"]["sdd_brightway_mechanism_totals"] == "../data/sdd_brightway_mechanism_totals.csv"
    assert manifest["entrypoints"]["sdd_brightway_top_sites"] == "../data/sdd_brightway_top_sites.csv"
    assert manifest["entrypoints"]["sdd_brightway_top_components"] == "../data/sdd_brightway_top_components.csv"
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
    assert manifest["entrypoints"]["brightway_usage_calibration"] == "../data/brightway_usage_calibration.csv"
    assert manifest["entrypoints"]["brightway_model_summary"] == "../summaries/brightway_model_summary.json"


def test_supply_geo_case_primary_path_invariants(tmp_path: Path) -> None:
    result = build_supply_geo_case(output_dir=tmp_path / "supply_case")
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


def test_supply_geo_case_weather_events_are_generated_from_weather_curves(tmp_path: Path) -> None:
    result = build_supply_geo_case(output_dir=tmp_path / "supply_case")
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
    sdd_bw_mechanisms = pd.read_csv(data_dir / "sdd_brightway_mechanism_totals.csv")
    sdd_bw_sites = pd.read_csv(data_dir / "sdd_brightway_top_sites.csv")
    sdd_bw_components = pd.read_csv(data_dir / "sdd_brightway_top_components.csv")
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
    assert {"climate_progress", "warming_delta_c", "hazard_intensification_factor"}.issubset(events.columns)
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
            "capacity_applied",
            "lead_time_multiplier",
            "service_proxy_pct",
        ]
    ).issubset(node_ops.columns)
    assert set(["operational_event_type", "source_driver_types", "disruption_index"]).issubset(op_events.columns)
    assert op_events["source_driver_types"].ne("none").all()
    assert op_events["disruption_index"].between(0.0, 1.0).all()
    assert {"stock_end_kg", "backlog_end_kg", "service_level", "decisions"}.issubset(sdd_node.columns)
    assert {"transport_risk_index", "delay_multiplier", "capacity_multiplier"}.issubset(sdd_lane.columns)
    assert {"oem_service_level", "sdd_kgCO2e", "surimpact_kgCO2e"}.issubset(sdd_flow.columns)
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
    assert not sdd_bw_mechanisms.empty
    assert not sdd_bw_sites.empty
    assert not sdd_bw_components.empty
    assert {
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
    assert lifecycle_compare["alignment_status"] == "not_aligned"
    aligned_compare = bw_excel_compare.loc[bw_excel_compare["scope_id"].eq("lifecycle_excel_aligned")].iloc[0]
    assert aligned_compare["alignment_status"] == "aligned"
    assert {"EU-28: Kerosene / Jet A1 at refinery Sphera", "GLO: Cargo plane, 65 t payload Sphera <u-so>"}.issubset(set(bw_usage["component"]))


def test_supply_geo_case_dashboard_exports_plotly_tabs(tmp_path: Path) -> None:
    result = build_supply_geo_case(output_dir=tmp_path / "supply_case")
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
    assert "BASE_DASHBOARD_PAYLOAD" in map_html
    assert "renderSddSites" in map_html
    assert "renderBaseDashboard" in map_html
    assert "renderSddLanes" in map_html
    assert "renderWeatherMap" in map_html
    assert "renderOperationsMap" in map_html
    assert "renderAcvMap" in map_html
    assert "renderCriticalityMap" in map_html
    assert "data-sdd-view=\"source\"" in map_html
    assert "data-sdd-view=\"weather\"" in map_html
    assert "data-sdd-view=\"operations\"" in map_html
    assert "data-sdd-view=\"acv\"" in map_html
    assert "data-sdd-view=\"criticality\"" in map_html
    assert "data-sdd-view=\"dashboard\"" in map_html
    assert "baseMapKpiCumulativePlot" in map_html
    assert "baseMapKpiWeatherPlot" in map_html
    assert "baseMapKpiOpsPlot" in map_html
    assert "baseMapKpiMaritimePlot" in map_html
    assert "baseMapKpiEventPlot" in map_html
    assert "baseMapKpiSddTierPlot" in map_html
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
    assert "L.circleMarker" not in map_html
    embedded_marker = "const BASE_DASHBOARD_PAYLOAD = "
    embedded_start = map_html.index(embedded_marker) + len(embedded_marker)
    embedded_end = map_html.index(";\n(function()", embedded_start)
    embedded_payload = json.loads(map_html[embedded_start:embedded_end])
    assert len(embedded_payload["sdd_brightway"]["monthly"]) == 240
    assert embedded_payload["sdd_brightway"]["mechanism_totals"]
    assert embedded_payload["sdd_brightway"]["exchange_category_totals"]
    assert embedded_payload["sdd_brightway"]["top_exchanges"]
    assert embedded_payload["sdd_brightway"]["exchange_lcia_monthly"]
    assert embedded_payload["sdd_brightway"]["exchange_lcia_top"]
    sdd_marker = "const SDD_MAP_PAYLOAD = "
    sdd_start = map_html.index(sdd_marker) + len(sdd_marker)
    sdd_end = map_html.index(";\nconst BASE_DASHBOARD_PAYLOAD", sdd_start)
    sdd_payload = json.loads(map_html[sdd_start:sdd_end])
    assert sdd_payload["sites"]
    assert {
        "weather_exposure_index",
        "weather_event_count",
        "sdd_acv_delta_kgco2e",
        "sdd_acv_row_count",
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
    assert len(payload["sdd_monthly"]) == 240
    assert len(payload["sdd_cumulative"]) == 240
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
    assert payload["brightway_model"]["usage_calibration"]
    assert payload["brightway_model"]["counts"]["parametric_formulas_evaluated"] > 0
    assert payload["brightway_model"]["counts"]["person_equivalent_indicators"] > 0
    assert payload["map_src"].endswith("supply_geo_base_results_map.html")
    assert not payload["map_src"].startswith("C:")


def test_supply_geo_case_default_config_exists() -> None:
    assert DEFAULT_CONFIG.exists()
