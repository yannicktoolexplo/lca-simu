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
    assert abs(summary["mass"]["allocation_gap_kg"]) <= 1e-6

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "poc2026.supply_geo_case.v1"
    assert manifest["capabilities"]["primary_supply_paths"] is True
    assert manifest["capabilities"]["allocated_path_mass"] is True
    assert manifest["capabilities"]["transport_weather_risk"] is True
    assert manifest["capabilities"]["node_operational_state"] is True
    assert manifest["capabilities"]["operational_event_lineage"] is True
    assert manifest["capabilities"]["sdd_stateful_supply_engine"] is True
    assert manifest["entrypoints"]["dashboard"] == "../maps/supply_geo_base_results_map.html"
    assert manifest["entrypoints"]["transport_weather"] == "../data/transport_weather_risk.csv"
    assert manifest["entrypoints"]["node_operational_state"] == "../data/node_operational_state.csv"
    assert manifest["entrypoints"]["operational_events"] == "../data/operational_event_seed.csv"
    assert manifest["entrypoints"]["sdd_monthly_impacts"] == "../data/sdd_monthly_impacts.csv"
    assert manifest["entrypoints"]["base_results_map"] == "../maps/supply_geo_base_results_map.html"


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
    for column in ["world_region", "weather_profile", "temp_c", "humidity_pct", "precip_mm", "wind_ms", "heat_index_c", "hurricane"]:
        assert column in weather.columns
    assert weather["humidity_pct"].between(0.0, 100.0).all()
    assert (weather["precip_mm"] >= 0.0).all()
    assert (weather["wind_ms"] >= 0.0).all()
    assert weather["world_region"].nunique() >= 3
    assert weather["weather_profile"].nunique() >= 3

    assert set(events["source_weather_column"]).issubset({"temp_c", "precip_mm", "wind_ms"})
    assert set(events["event_type"]).issubset({"heatwave", "drought", "storm", "hurricane", "cold"})
    assert (events["intensity"] > 0.0).all()
    assert events["capacity_multiplier"].between(0.0, 1.0).all()
    assert (events["lead_time_multiplier"] >= 1.0).all()
    assert set(["route_region", "maritime_risk_index", "delay_multiplier", "capacity_multiplier"]).issubset(transport_weather.columns)
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
    assert "data-sdd-view=\"source\"" in map_html
    assert "data-sdd-view=\"dashboard\"" in map_html
    assert "baseMapKpiCumulativePlot" in map_html
    assert "baseMapKpiWeatherPlot" in map_html
    assert "baseMapKpiOpsPlot" in map_html
    assert "baseMapKpiMaritimePlot" in map_html
    assert "baseMapKpiEventPlot" in map_html
    assert "L.circleMarker" not in map_html

    payload = json.loads(kpis.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "poc2026.supply_geo_case.kpi_dashboard.v1"
    assert payload["cards"]
    assert payload["readiness"]
    assert len(payload["weather_month"]) == 240
    assert len(payload["ops_month"]) == 240
    assert {"avg_temp_c", "avg_humidity_pct", "avg_precip_mm", "avg_wind_ms", "avg_hurricane"}.issubset(payload["weather_month"][0])
    assert {"event_count", "capacity_multiplier_min", "lead_time_multiplier_max"}.issubset(payload["ops_month"][0])
    assert payload["weather_region"]
    assert payload["weather_profile"]
    assert payload["weather_region_month"]
    assert payload["maritime_month"]
    assert payload["maritime_region"]
    assert payload["node_ops_month"]
    assert payload["node_ops_region"]
    assert payload["node_ops_lineage"]
    assert len(payload["sdd_monthly"]) == 240
    assert len(payload["sdd_cumulative"]) == 240
    assert payload["sdd_method_comparison"]
    assert payload["sdd_tier_month"]
    assert payload["horizon_adaptation"]["available"] is True
    assert payload["horizon_adaptation"]["weather_driver"]
    assert payload["horizon_adaptation"]["reference_cumulative"]
    assert payload["horizon_adaptation"]["event_impact"]
    assert payload["event_month"]
    assert payload["map_src"].endswith("supply_geo_base_results_map.html")
    assert not payload["map_src"].startswith("C:")


def test_supply_geo_case_default_config_exists() -> None:
    assert DEFAULT_CONFIG.exists()
