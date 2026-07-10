from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
SHORT_CSV = ROOT / "outputs_sddlca_poc" / "csv"
HA_ROOT = ROOT / "horizon-adaptation"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict)
    return data


def assert_non_negative(df: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        assert column in df.columns
        assert (df[column] >= -1e-9).all(), column


def assert_close_series(left: pd.Series, right: pd.Series, name: str, tol: float = 1e-6) -> None:
    diff = (left - right).abs().max()
    assert diff <= tol, f"{name} max diff={diff}"


def test_short_config_policy_contract() -> None:
    config = load_yaml(ROOT / "config" / "sddlca_parameters.yml")

    for section in [
        "study",
        "lead_times",
        "initial_state",
        "environmental_factors",
        "economic_factors",
        "policies",
        "counterfactual_policy_order",
    ]:
        assert section in config

    assert config["study"]["horizon_weeks"] == 52
    assert config["lead_times"]["main_weeks"] >= config["lead_times"]["backup_weeks"]

    policies = config["policies"]
    names = [policy["name"] for policy in policies.values()]
    assert len(names) == len(set(names))
    for policy_key in config["counterfactual_policy_order"]:
        assert policy_key in policies
        policy = policies[policy_key]
        assert policy["raw_target"] >= policy["raw_reorder_threshold"]
        assert policy["air_backlog_end_threshold"] >= policy["air_backlog_start_threshold"]
        assert 0 < policy["carbon_aware_capacity_cap"] <= 1


def test_short_state_flow_invariants() -> None:
    states = pd.read_csv(SHORT_CSV / "poc_supply_chain_states.csv")
    assert len(states) == 52

    assert_non_negative(
        states,
        [
            "demand",
            "capacity",
            "main_order",
            "backup_order",
            "raw_stock_end",
            "fg_stock_end",
            "backlog_end",
            "planned_input_units",
            "good_output_units",
            "scrap_units",
            "outbound_shipments",
        ],
    )

    assert (states["capacity_utilization"] <= 1.0 + 1e-9).all()
    assert (states["same_week_service_level"] <= 1.0 + 1e-9).all()
    assert_close_series(
        states["raw_stock_end"],
        states["raw_stock_main_end"] + states["raw_stock_backup_end"],
        "raw stock source split",
    )
    assert_close_series(
        states["fg_stock_end"],
        states["fg_stock_main_end"] + states["fg_stock_backup_end"],
        "finished goods source split",
    )
    assert_close_series(
        states["good_output_units"],
        states["good_output_main_units"] + states["good_output_backup_units"],
        "good output source split",
    )
    assert_close_series(
        states["scrap_units"],
        states["scrap_main_units"] + states["scrap_backup_units"],
        "scrap source split",
    )

    air_rows = states.loc[states["outbound_mode"] == "air"]
    assert not air_rows.empty
    assert (air_rows["air_trigger_reason"] != "none").all()


def test_short_state_space_pipeline_invariants() -> None:
    trajectory = pd.read_csv(SHORT_CSV / "poc_state_space_trajectory.csv")

    main_cols = [column for column in trajectory.columns if column.startswith("state_end_main_pipeline_eta_")]
    backup_cols = [column for column in trajectory.columns if column.startswith("state_end_backup_pipeline_eta_")]
    assert main_cols
    assert backup_cols

    assert_close_series(
        trajectory["state_end_main_pipeline_total"],
        trajectory[main_cols].sum(axis=1),
        "main pipeline total",
    )
    assert_close_series(
        trajectory["state_end_backup_pipeline_total"],
        trajectory[backup_cols].sum(axis=1),
        "backup pipeline total",
    )
    assert_close_series(
        trajectory["state_end_total_pipeline"],
        trajectory["state_end_main_pipeline_total"] + trajectory["state_end_backup_pipeline_total"],
        "total pipeline",
    )


def test_short_lca_method_invariants() -> None:
    checks = pd.read_csv(SHORT_CSV / "poc_method_sanity_checks.csv")
    assert checks["status"].astype(str).str.lower().eq("true").all()

    comparison = pd.read_csv(SHORT_CSV / "poc_lca_method_comparison.csv")
    totals = comparison.set_index("method")["total_kgCO2e"]
    assert totals["State-Dependent Dynamic LCA"] >= totals["Time-Dependent DLCA"]

    breakdown = pd.read_csv(SHORT_CSV / "poc_lca_breakdown.csv")
    components = [
        "material",
        "inbound_transport",
        "production_energy",
        "outbound_transport",
        "storage",
        "scrap",
    ]
    for _, row in breakdown.iterrows():
        total = sum(float(row[column]) for column in components)
        assert abs(total - float(row["total"])) <= 1e-6


def test_horizon_config_policy_contract() -> None:
    config = load_yaml(HA_ROOT / "config" / "ha_parameters.yml")

    for section in [
        "study",
        "lead_times",
        "environmental_factors",
        "economic_factors",
        "weather_driver",
        "weather_event_thresholds",
        "timeline_policy_name",
        "policies",
        "scenario_overrides",
    ]:
        assert section in config

    assert config["study"]["horizon_months"] == 240
    policy_names = [policy["name"] for policy in config["policies"]]
    assert len(policy_names) == len(set(policy_names))
    assert config["timeline_policy_name"] in policy_names
    for policy in config["policies"]:
        assert policy["raw_target"] >= policy["reorder_threshold"]
        assert policy["air_end_threshold"] >= policy["air_start_threshold"]
        assert policy["battery_capacity"] >= 0

    thresholds = config["weather_event_thresholds"]
    assert thresholds["heatwave_temp_c"] > thresholds["drought_temp_c"]
    assert thresholds["storm_precip_mm"] > thresholds["drought_precip_mm"]


def test_horizon_state_and_energy_invariants() -> None:
    state_files = [
        HA_ROOT / "outputs" / "csv" / "ha_monthly_states.csv",
        HA_ROOT / "baseline" / "csv" / "ha_monthly_states.csv",
        HA_ROOT / "biomass" / "csv" / "ha_monthly_states.csv",
        HA_ROOT / "biosourced_material" / "csv" / "ha_monthly_states.csv",
    ]

    for state_file in state_files:
        states = pd.read_csv(state_file)
        assert not states.empty
        assert set(states["month_index"]) == set(range(1, 241))
        assert_non_negative(
            states,
            [
                "raw_stock_end",
                "fg_stock_end",
                "backlog_end",
                "good_output_units",
                "scrap_units",
                "outbound_shipments",
                "temp_c",
                "humidity_pct",
                "precip_mm",
                "wind_ms",
                "heat_index_c",
                "process_kwh",
                "hvac_kwh",
                "total_energy_demand",
                "solar_used_kwh",
                "biomass_used_kwh",
                "battery_discharge_kwh",
                "grid_energy_kwh",
            ],
        )
        assert (states["capacity_utilization"] <= 1.0 + 1e-9).all()
        assert (states["battery_soh"].between(0.58 - 1e-9, 1.0 + 1e-9)).all()
        assert states["humidity_pct"].between(0.0, 100.0).all()
        assert (states["precip_mm"] >= 0.0).all()
        assert (states["wind_ms"] >= 0.0).all()

        energy_supply = (
            states["solar_used_kwh"]
            + states["biomass_used_kwh"]
            + states["battery_discharge_kwh"]
            + states["grid_energy_kwh"]
        )
        assert_close_series(states["total_energy_demand"], energy_supply, f"energy balance {state_file}")


def test_horizon_weather_driver_event_generation() -> None:
    weather_files = [
        HA_ROOT / "outputs" / "csv" / "ha_weather_driver.csv",
        HA_ROOT / "baseline" / "csv" / "ha_weather_driver.csv",
        HA_ROOT / "biomass" / "csv" / "ha_weather_driver.csv",
        HA_ROOT / "biosourced_material" / "csv" / "ha_weather_driver.csv",
    ]

    for weather_file in weather_files:
        weather = pd.read_csv(weather_file)
        assert len(weather) == 240
        for column in ["temp_c", "humidity_pct", "precip_mm", "wind_ms", "heat_index_c"]:
            assert column in weather.columns
        assert weather["humidity_pct"].between(0.0, 100.0).all()
        assert (weather["precip_mm"] >= 0.0).all()
        assert (weather["wind_ms"] >= 0.0).all()

        heat_rows = weather["climate_event"].str.contains("canicule")
        drought_rows = weather["climate_event"].str.contains("secheresse")
        storm_rows = weather["climate_event"].str.contains("tempete")
        assert heat_rows.any()
        assert drought_rows.any()
        assert storm_rows.any()
        assert (weather.loc[heat_rows, "heatwave"] > 0.0).all()
        assert (weather.loc[drought_rows, "drought"] > 0.0).all()
        assert (weather.loc[storm_rows, "storm_stress"] > 0.0).all()


def test_horizon_lca_method_invariants() -> None:
    comparison_files = [
        HA_ROOT / "outputs" / "csv" / "ha_method_comparison.csv",
        HA_ROOT / "baseline" / "csv" / "ha_method_comparison.csv",
        HA_ROOT / "biomass" / "csv" / "ha_method_comparison.csv",
        HA_ROOT / "biosourced_material" / "csv" / "ha_method_comparison.csv",
    ]

    for comparison_file in comparison_files:
        comparison = pd.read_csv(comparison_file)
        methods_by_policy = comparison.groupby("policy_label")["method"].nunique()
        assert (methods_by_policy == 3).all()
        pivot = comparison.pivot(index="policy_label", columns="method", values="total_kgCO2e")
        assert (pivot["State-Dependent Dynamic LCA"] >= pivot["Time-Dependent DLCA"]).all()
