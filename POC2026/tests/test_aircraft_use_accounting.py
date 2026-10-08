"""Memory-only accounting oracles; no runtime, file fixtures or output writes."""

from copy import deepcopy
from decimal import Decimal

import pytest

from POC2026.supply_geo_case.aircraft_use_accounting import (
    aircraft_use_signature,
    build_article_use_profile,
    refresh_production_use_rows,
)


def _model(mass="109.967"):
    fuel = Decimal(mass) * 700 * 7 * Decimal(".18224")
    activity = "kerosene, production et combustion, 1tkm eq"
    exchanges = [
        {"activity_name": activity, "type": kind, "name": name, "amount": amount}
        for kind, name, amount in (
            ("technosphere", "market for kerosene", .4),
            ("technosphere", "market for kerosene", .6),
            ("biosphere", "Carbon dioxide, fossil", 1.2),
            ("biosphere", "Carbon dioxide, fossil", 1.95),
            ("technosphere", "Carbon dioxide, fossil", 900),
            ("biosphere", "market for kerosene", 900),
        )
    ]
    exchanges.append({"activity_name": "unrelated activity", "type": "biosphere",
                      "name": "Carbon dioxide, fossil", "amount": 900})
    return {
        "lightweight_seat": {
            "mission": {
                "baseline_fuel_kg": float(fuel), "target_fuel_kg": float(fuel / 2),
                "baseline_mass_kg": float(mass), "lifetime_years": 7,
                "average_flight_distance_km": 5556, "annual_flight_cycles": 700,
                "status": "extrapolated_not_validated", "warning": "Not validated",
            },
            "indicator_results": [
                {"indicator_id": "Acidification", "baseline_use_raw": -900},
                {"indicator_id": "Climate Change - total",
                 "baseline_use_raw": float(fuel * Decimal("4.25")),
                 "baseline_production_raw": 250,
                 "normalization_factor_per_person_year": 1000},
            ],
        },
        "exchanges": exchanges,
        "usage_calibration": {"historical_stelia_use": 999999999},
    }


def test_opera_decomposition_conserves_lcia_without_adding_icao():
    model = _model()
    original = deepcopy(model)
    profile = build_article_use_profile(model)
    fuel = Decimal("98197.891792")
    expected_total = float(fuel * Decimal("4.25"))
    expected_combustion = float(fuel * Decimal("3.15"))
    expected_remainder = float(fuel * Decimal("1.10"))
    components = {row["mechanism"]: row for row in profile["components"]}
    assert set(components) == {"fuel_upstream", "inflight_mass_burden"}
    assert profile["full_lifetime_use_kgco2e_per_seat"] == pytest.approx(expected_total)
    assert profile["direct_co2_opera_kg_per_seat"] == pytest.approx(expected_combustion)
    assert profile["direct_co2_icao_kg_per_seat"] == pytest.approx(float(fuel * Decimal("3.16")))
    assert profile["target_direct_co2_icao_kg_per_seat"] == pytest.approx(float(fuel * Decimal("1.58")))
    assert components["fuel_upstream"]["full_lifetime_kgco2e"] == pytest.approx(expected_remainder)
    assert components["inflight_mass_burden"]["full_lifetime_kgco2e"] == pytest.approx(expected_combustion)
    assert sum(row["full_lifetime_kgco2e"] for row in components.values()) == pytest.approx(expected_total)
    assert sum(row["monthly_per_active_seat_kgco2e"] for row in components.values()) * 84 == pytest.approx(expected_total)
    assert sum(row["full_lifetime_person_equivalent"] for row in components.values()) == pytest.approx(expected_total / 1000)
    assert profile["aligned_lifecycle_kgco2e_per_seat"] == pytest.approx(expected_total + 250)
    assert profile["lifetime_months"] == 84
    assert profile["mission_status"] == "extrapolated_not_validated"
    assert profile["mission_warning"] == "Not validated"
    assert profile["cleaning_status"] == "excluded_not_zero_impact"
    assert profile["other_lifecycle_status"] == "excluded_not_zero_impact"
    assert model == original


def test_use_profile_scales_with_mission_mass_not_historical_stelia():
    baseline = build_article_use_profile(_model())
    half_model = _model("54.9835")
    half_model["usage_calibration"] = {"historical_stelia_use": -123456789}
    half = build_article_use_profile(half_model)
    for key in ("seat_mass_kg", "fuel_kg_per_seat", "target_fuel_kg_per_seat",
                "direct_co2_opera_kg_per_seat", "direct_co2_icao_kg_per_seat",
                "target_direct_co2_icao_kg_per_seat", "full_lifetime_use_kgco2e_per_seat",
                "monthly_use_kgco2e_per_active_seat", "fuel_upstream_kgco2e_per_seat",
                "inflight_mass_burden_kgco2e_per_seat"):
        assert half[key] == pytest.approx(baseline[key] / 2), key
    assert half["production_kgco2e_per_seat"] == baseline["production_kgco2e_per_seat"] == 250
    assert half["lifetime_months"] == baseline["lifetime_months"]


@pytest.mark.parametrize("total", [None, float("nan"), float("inf"), -float("inf")])
def test_missing_or_nonfinite_lcia_refuses_stelia_fallback(total):
    model = _model()
    model["lightweight_seat"]["indicator_results"][1]["baseline_use_raw"] = total
    with pytest.raises(ValueError, match="finite climate LCIA factor; no STELIA fallback"):
        build_article_use_profile(model)


@pytest.mark.parametrize("missing", ["all", "market for kerosene", "Carbon dioxide, fossil"])
def test_absent_combustion_inventory_refuses_fabricated_decomposition(missing):
    model = _model()
    model["exchanges"] = [] if missing == "all" else [
        row for row in model["exchanges"] if row["name"] != missing]
    with pytest.raises(ValueError, match="Combustion inventory unavailable"):
        build_article_use_profile(model)


def test_negative_lcia_remainder_is_not_clipped_or_replaced_by_icao():
    model = _model()
    model["lightweight_seat"]["indicator_results"][1]["baseline_use_raw"] = 100
    profile = build_article_use_profile(model)
    assert profile["fuel_upstream_kgco2e_per_seat"] < 0
    assert sum(row["full_lifetime_kgco2e"] for row in profile["components"]) == pytest.approx(100)


@pytest.mark.parametrize("years", [0, -1, .1])
def test_lifetime_requires_positive_whole_months(years):
    model = _model()
    model["lightweight_seat"]["mission"]["lifetime_years"] = years
    with pytest.raises(ValueError, match="positive whole number of months"):
        build_article_use_profile(model)


def test_no_mission_leaves_legacy_profile_to_caller():
    assert build_article_use_profile({}) is None
    model = _model()
    model["lightweight_seat"]["mission"] = None
    assert build_article_use_profile(model) is None


def test_refresh_preserves_production_deltas_order_and_matches_monthly_oracle():
    monthly = [
        {"month_index": str(month), "seat_equivalent_volume": volume,
         "production_dynamic_kgco2e": production, "production_reference_kgco2e": 999,
         "sdd_delta_kgco2e": -17, "production_delta_pct": 12,
         "use_full_lifetime_kgco2e": -1, "cycle_dynamic_with_stelia_usage_kgco2e": -1}
        for month, volume, production in ((3, 3, 300), (1, 1, 100), (2, 0, 200))
    ]
    cumulative = [{"month_index": month, "production_dynamic_cumulative": month * 100,
                   "sdd_delta_cumulative": -month, "cycle_dynamic_with_stelia_usage_cumulative": -1}
                  for month in (2, 3, 1)]
    original_monthly, original_cumulative = deepcopy(monthly), deepcopy(cumulative)
    profile = {"full_lifetime_use_kgco2e_per_seat": 420,
               "other_lifecycle_kgco2e_per_seat": -20, "accounting_method": "memory_article"}
    original_profile = deepcopy(profile)
    refresh_production_use_rows(monthly, cumulative, profile)
    assert [row["month_index"] for row in monthly] == ["3", "1", "2"]
    assert [row["month_index"] for row in cumulative] == [2, 3, 1]
    expected_totals = {1: 500, 2: 200, 3: 1500}
    expected_cumulative = {1: 500, 2: 700, 3: 2200}
    for row, original in zip(monthly, original_monthly):
        for key, value in original.items():
            if key not in {"use_full_lifetime_kgco2e", "cycle_dynamic_with_stelia_usage_kgco2e"}:
                assert row[key] == value
        assert row["use_full_lifetime_kgco2e"] == row["seat_equivalent_volume"] * 420
        assert row["other_lifecycle_net_kgco2e"] == row["seat_equivalent_volume"] * -20
        assert row["lifecycle_attributed_kgco2e"] == expected_totals[int(row["month_index"])]
        assert row["cycle_dynamic_with_stelia_usage_kgco2e"] == row["lifecycle_attributed_kgco2e"]
        assert row["legacy_cycle_field_status"] == "name_only_alias_to_current_use_method"
        assert row["use_accounting_method"] == "memory_article"
    for row, original in zip(cumulative, original_cumulative):
        for key, value in original.items():
            if key != "cycle_dynamic_with_stelia_usage_cumulative":
                assert row[key] == value
        assert row["lifecycle_attributed_cumulative"] == expected_cumulative[row["month_index"]]
        assert row["cycle_dynamic_with_stelia_usage_cumulative"] == row["lifecycle_attributed_cumulative"]
        assert row["use_accounting_method"] == "memory_article"
    refreshed = deepcopy((monthly, cumulative))
    refresh_production_use_rows(monthly, cumulative, profile)
    assert (monthly, cumulative) == refreshed
    assert profile == original_profile


def test_signature_is_deterministic_and_independent_of_dictionary_order():
    model = _model()
    original = deepcopy(model)
    reordered = deepcopy(model)
    mission = reordered["lightweight_seat"]["mission"]
    reordered["lightweight_seat"]["mission"] = dict(reversed(list(mission.items())))
    signature = aircraft_use_signature(model)
    assert len(signature) == 64
    assert int(signature, 16) >= 0
    assert aircraft_use_signature(reordered) == signature
    assert aircraft_use_signature(deepcopy(model)) == signature
    assert model == original


@pytest.mark.parametrize("changed", ["mission", "indicator", "combustion", "legacy_without_mission"])
def test_signature_changes_with_accounting_inputs(changed):
    model = _model()
    if changed == "legacy_without_mission":
        model["lightweight_seat"]["mission"] = None
    original_signature = aircraft_use_signature(model)
    if changed == "mission":
        model["lightweight_seat"]["mission"]["baseline_fuel_kg"] += 1
    elif changed == "indicator":
        model["lightweight_seat"]["indicator_results"][1]["baseline_use_raw"] += 1
    elif changed == "combustion":
        model['exchanges'][2]['amount'] += .01
    else:
        model["usage_calibration"]["historical_stelia_use"] += 1
    assert aircraft_use_signature(model) != original_signature


def test_article_signature_ignores_legacy_calibration_and_unrelated_display():
    model = _model()
    signature = aircraft_use_signature(model)
    model["usage_calibration"] = {"historical_stelia_use": 1}
    model["display"] = {"title": "Changed"}
    assert aircraft_use_signature(model) == signature


@pytest.mark.parametrize('volume, service, expected', [(2, 1, 1880), (2, .5, 1040), (2, 0, 200), (0, 1, 0)])
def test_cohorts_do_not_multiply_total_production_by_delivered_volume(volume, service, expected):
    from POC2026.supply_geo_case.adapter import build_aircraft_use_trajectory

    monthly, cumulative = build_aircraft_use_trajectory(
        scenario_id='memory', max_month=1,
        sdd_monthly_rows=[{'month_index': 1, 'avg_oem_service_level': service}],
        production_monthly_rows=[{'month_index': 1, 'seat_equivalent_volume': volume,
                                 'production_dynamic_kgco2e': volume * 100}],
        profile={'lifetime_months': 84, 'full_lifetime_use_kgco2e_per_seat': 840,
                 'monthly_use_kgco2e_per_active_seat': 10})
    assert monthly[0]['full_lifecycle_attributed_kgco2e'] == expected
    assert cumulative[0]['full_lifecycle_attributed_cumulative_kgco2e'] == expected
