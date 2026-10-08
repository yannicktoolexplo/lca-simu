from decimal import Decimal

import pytest

from POC2026.supply_geo_case.aircraft_mission import build_mission


def mission_config(distance=5556, allow=True):
    return {"baseline_mass_kg": 109.967, "target_mass_kg": 54.9835,
            "flight_use": {"calculation_method": "steinegger_a322_2017",
                           "average_flight_distance_km": distance,
                           "annual_flight_cycles": 700, "lifetime_years": 7,
                           "allow_extrapolation": allow}}


def test_article_decimal_oracle():
    mission = build_mission(mission_config())
    coefficient = Decimal(".16") + Decimal(556) * Decimal(".04") / Decimal(1000)
    fuel = Decimal("109.967") * 4900 * coefficient
    assert mission["coefficient_kg_fuel_per_kg_per_flight"] == pytest.approx(float(coefficient))
    assert mission["baseline_fuel_kg"] == pytest.approx(float(fuel))
    assert mission["target_fuel_kg"] == pytest.approx(float(fuel / 2))
    assert mission["avoided_fuel_kg"] == pytest.approx(float(fuel / 2))
    assert mission["baseline_direct_co2_kg"] == pytest.approx(float(fuel * Decimal("3.16")))
    assert mission["status"] == "extrapolated_not_validated"
    assert mission["valid_distance_domain_km"] == [2000, 5000]
    assert mission["source"]["page"] == 11
    assert mission["average_flight_distance_km"] == 5556
    assert mission["annual_flight_cycles"] == 700
    assert mission["lifetime_years"] == 7
    assert mission["lifetime_distance_km"] == 27224400
    assert mission["baseline_mass_kg"] == 109.967
    assert mission["target_mass_kg"] == 54.9835
    assert mission["fuel_coefficient_kg_per_kg_per_flight"] == pytest.approx(.18224)
    assert mission["warning"]
    assert mission["scope"] == "mass_transport_only"
    assert mission["excluded_use"] == ["ife", "cleaning", "non_co2_altitude_effects"]


@pytest.mark.parametrize("distance, coefficient", [(2000, .07), (3000, .095),
    (4000, .12), (4500, .14), (5000, .16)])
def test_article_interpolation(distance, coefficient):
    mission = build_mission(mission_config(distance, False))
    assert mission["coefficient_kg_fuel_per_kg_per_flight"] == pytest.approx(coefficient)
    expected_status = "interpolated" if distance in (3000, 4500) else "source_point"
    assert mission["status"] == expected_status
    assert mission["warning"] == ""


@pytest.mark.parametrize("distance", [1999, 5556])
@pytest.mark.parametrize("allow", [False, "true", 1, None])
def test_article_blocks_unapproved_extrapolation(distance, allow):
    with pytest.raises(ValueError, match="allow_extrapolation"):
        build_mission(mission_config(distance, allow))


@pytest.mark.parametrize("key, value", [("average_flight_distance_km", 0),
    ("annual_flight_cycles", -1), ("lifetime_years", float("nan"))])
def test_article_invalid_inputs(key, value):
    config = mission_config()
    config["flight_use"][key] = value
    with pytest.raises(ValueError):
        build_mission(config)


def test_legacy_and_unknown_method():
    assert build_mission({}) is None
    config = mission_config()
    config["flight_use"]["calculation_method"] = "unknown"
    with pytest.raises(ValueError):
        build_mission(config)


def test_lower_extrapolation_and_zero_service():
    config = mission_config(1000)
    mission = build_mission(config)
    assert mission["fuel_coefficient_kg_per_kg_per_flight"] == pytest.approx(.045)
    assert mission["status"] == "extrapolated_not_validated"
    config["flight_use"]["annual_flight_cycles"] = 0
    mission = build_mission(config)
    assert mission["baseline_fuel_kg"] == mission["target_fuel_kg"] == 0
