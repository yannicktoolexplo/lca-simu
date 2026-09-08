from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    aircraft_use_profile,
    build_aircraft_use_trajectory,
    build_excel_original_indicator_comparison,
    build_excel_runtime_comparison,
    build_sdd_brightway_coupling,
    build_sdd_risk_cascade_payload,
    full_scenario_summary,
    safe_float,
    simulate_sdd_supply,
)
from POC2026.tests.test_constrained_sdd_engine import constrained_policy, synthetic_supply


def stelia_use_brightway_model() -> dict:
    return {
        "exact_scenario_lcia": [
            {
                "scenario_id": "current_export",
                "root_activity_id": "production",
                "score_kgco2e": 2449.945068,
            },
            {
                "scenario_id": "current_export",
                "root_activity_id": "lifecycle_excel_aligned",
                "score_kgco2e": 462846.896821,
                "excel_use_phase_kgco2e_added": 460797.367595,
            },
        ],
        "parameters": [
            {"name": "fauteuil_duree_vie", "amount": 7.0},
            {"name": "fauteuil_masse_totale", "amount": 109.967},
            {"name": "fauteuil_distance_moyenne_vol", "amount": 5556.0},
            {"name": "fauteuil_AR_an", "amount": 700.0},
            {"name": "fauteuil_kero_conso_passive", "amount": 82723.023014},
        ],
        "usage_calibration": [
            {
                "system": "Consommation passive",
                "component": "EU-28: Kerosene / Jet A1 at refinery Sphera",
                "business_component": "Production du carburant imputable au siege",
                "excel_kgco2e": 57802.048956561,
            },
            {
                "system": "Consommation passive",
                "component": "GLO: Cargo plane, 65 t payload Sphera",
                "business_component": "Emissions en vol imputables a la masse du siege",
                "excel_kgco2e": 402914.282432496,
            },
            {
                "system": "Entretien",
                "component": "Nettoyage et desinfection",
                "business_component": "Nettoyage et desinfection",
                "excel_kgco2e": 81.03620589,
            },
        ],
        "indicator_unit_views": [],
    }


def test_aircraft_use_profile_reconciles_stelia_lifecycle() -> None:
    profile = aircraft_use_profile(stelia_use_brightway_model())

    assert profile["lifetime_months"] == 84
    assert profile["full_lifetime_use_kgco2e_per_seat"] == pytest.approx(
        460797.367595
    )
    assert (
        profile["fuel_upstream_kgco2e_per_seat"]
        + profile["inflight_mass_burden_kgco2e_per_seat"]
        + profile["cleaning_kgco2e_per_seat"]
    ) == pytest.approx(profile["full_lifetime_use_kgco2e_per_seat"])
    assert (
        profile["production_kgco2e_per_seat"]
        + profile["other_lifecycle_kgco2e_per_seat"]
        + profile["full_lifetime_use_kgco2e_per_seat"]
    ) == pytest.approx(profile["aligned_lifecycle_kgco2e_per_seat"])


def test_aircraft_use_cohorts_expire_and_keep_accounting_views_separate() -> None:
    profile = aircraft_use_profile(stelia_use_brightway_model())
    sdd_rows = [
        {
            "month_index": month,
            "avg_oem_service_level": 1.0,
            "avg_oem_service_level_without_adaptation": 0.5,
        }
        for month in range(1, 91)
    ]
    production_rows = [
        {
            "month_index": month,
            "seat_equivalent_volume": 1.0,
            "production_dynamic_kgco2e": 2500.0,
        }
        for month in range(1, 91)
    ]

    monthly, cumulative = build_aircraft_use_trajectory(
        scenario_id="test",
        sdd_monthly_rows=sdd_rows,
        production_monthly_rows=production_rows,
        profile=profile,
        max_month=90,
    )

    assert monthly[0]["active_seat_equivalent"] == pytest.approx(1.0)
    assert monthly[83]["active_seat_equivalent"] == pytest.approx(84.0)
    assert monthly[84]["active_seat_equivalent"] == pytest.approx(84.0)
    assert monthly[84]["retired_seat_equivalent"] == pytest.approx(1.0)
    assert monthly[84]["active_without_adaptation_seat_equivalent"] == pytest.approx(42.0)
    assert monthly[0]["calendar_use_kgco2e"] == pytest.approx(
        profile["full_lifetime_use_kgco2e_per_seat"] / 84.0
    )
    assert monthly[0]["full_lifetime_use_attributed_kgco2e"] == pytest.approx(
        profile["full_lifetime_use_kgco2e_per_seat"]
    )
    assert cumulative[-1]["calendar_use_cumulative_kgco2e"] < cumulative[-1][
        "full_lifetime_use_attributed_cumulative_kgco2e"
    ]


def test_excel_climate_comparison_marks_calibration_and_rejected_raw_usage() -> None:
    normalization = 8095.525063944057
    reference = [
        {
            "short_label": "Climate Change - total",
            "impact_total_person_equivalent": 57.269114716,
            "impact_without_use_person_equivalent": 0.349104716,
            "use_phase_person_equivalent": 56.92001,
        }
    ]
    exact = [
        {
            "scenario_id": "current_export",
            "root_activity_id": "production",
            "score_kgco2e": 2449.945068,
        },
        {
            "scenario_id": "current_export",
            "root_activity_id": "lifecycle",
            "score_kgco2e": 2662108.871703,
        },
        {
            "scenario_id": "current_export",
            "root_activity_id": "lifecycle_excel_aligned",
            "score_kgco2e": 462846.896821,
            "excel_use_phase_kgco2e_added": 460797.367595,
        },
    ]

    rows = build_excel_runtime_comparison(reference, exact, normalization)
    by_scope = {row["scope_id"]: row for row in rows}

    assert len(rows) == 5
    assert by_scope["use_phase_calibrated"]["delta_kgco2e"] == pytest.approx(0.0, abs=1e-3)
    assert by_scope["use_phase_calibrated"]["alignment_status"] == "identique_par_construction"
    assert by_scope["use_phase_calibrated"]["independent_validation"] is False
    assert by_scope["lifecycle_total"]["alignment_status"] == "ecarte_inventaire_usage_incompatible"
    assert by_scope["lifecycle_without_use"]["runtime_kgco2e"] == pytest.approx(2049.529226)
    assert by_scope["lifecycle_excel_aligned"]["relative_delta_pct"] == pytest.approx(-0.167519, abs=1e-6)


def test_excel_indicator_version_comparison_keeps_weighting_traceable() -> None:
    rows = build_excel_original_indicator_comparison(
        [
            {
                "indicator": "EF 3.0 Climate Change - total",
                "short_label": "Climate Change - total",
                "impact_total_person_equivalent": 57.269114716,
                "impact_without_use_person_equivalent": 0.349104716,
                "use_phase_person_equivalent": 56.92001,
            }
        ],
        [
            {
                "short_label": "Climate Change - total",
                "impact_total_weighted_score": 192.974008949,
            }
        ],
        [
            {
                "short_label": "Climate Change - total",
                "person_equivalent_value": 65.316293331,
                "raw_sum_value": 528769.689741673,
                "raw_unit": "kg CO2 eq.",
                "normalization_factor_per_person_year": 8095.525063944057,
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["relative_delta_pct"] == pytest.approx(14.051516, abs=1e-6)
    assert rows[0]["weighting_factor_vs_equal_weight"] == pytest.approx(3.3696)
    assert rows[0]["independent_brightway_validation"] is False
    assert rows[0]["comparison_status"] == "ecart_modere_2_20_pct"


def scenario_nodes(level: str) -> list[dict]:
    _, _, rows = synthetic_supply()
    capacities = {
        "climat_stationnaire": 1.0,
        "climat_2026_2046_modere": 0.4,
        "climat_degrade": 0.2,
    }
    capacity = capacities[level]
    out = []
    for row in (item for item in rows if item["month_index"] == 1):
        for month in range(1, 13):
            copy = dict(row)
            copy["month_index"] = month
            if "canicule" in str(copy.get("source_driver_types")):
                copy["capacity_applied"] = capacity
                copy["disruption_index"] = 1.0 - capacity
                copy["lead_time_multiplier"] = 1.0 + 0.4 * (1.0 - capacity)
                copy["scrap_multiplier"] = 1.0 + 0.10 * (1.0 - capacity)
                copy["source_environmental_event_ids"] = f"env:{level}:{month}"
                if level == "climat_stationnaire":
                    copy["operational_event_labels"] = "nominal"
                    copy["source_driver_types"] = "none"
                    copy["source_environmental_event_ids"] = ""
            copy["scenario_id"] = level
            out.append(copy)
    return out


def test_scenario_id_reaches_sdd_brightway_and_cascades_with_ordered_stress() -> None:
    paths, lanes, _ = synthetic_supply()
    brightway_model = {
        "exact_scenario_lcia": [
            {
                "scenario_id": "current_export",
                "root_activity_id": "production",
                "score_kgco2e": 1000.0,
            }
        ],
        "component_impacts": [],
        "supply_alignment": [],
        "exchanges": [],
        "activities": [],
        "indicator_unit_views": [],
        "runtime": {"can_execute_brightway": False},
    }
    service_without_adaptation = []
    acv_deltas = []
    for scenario_id in (
        "climat_stationnaire",
        "climat_2026_2046_modere",
        "climat_degrade",
    ):
        sdd = simulate_sdd_supply(
            path_rows=paths,
            lane_rows=lanes,
            node_operational_rows=scenario_nodes(scenario_id),
            transport_weather_rows=[],
            horizon_months=12,
            scenario_id=scenario_id,
            resilience_policy=constrained_policy(),
        )
        bw = build_sdd_brightway_coupling(
            path_rows=paths,
            sdd_results=sdd,
            brightway_model=brightway_model,
        )
        cascade = build_sdd_risk_cascade_payload(sdd, bw)
        for key in (
            "sdd_node_state",
            "sdd_lane_state",
            "sdd_flow_state",
            "sdd_event_ledger",
            "sdd_resilience_resources",
            "sdd_monthly_impacts",
        ):
            assert all(row["scenario_id"] == scenario_id for row in sdd[key])
        for key in (
            "inventory_delta",
            "exchange_delta",
            "monthly",
            "cumulative",
            "mechanism_totals",
        ):
            assert all(row["scenario_id"] == scenario_id for row in bw[key])
        assert cascade["stats"]["scenario_ids"] in ([], [scenario_id])
        assert all(row["scenario_id"] == scenario_id for row in cascade["cascades"])
        service_without_adaptation.append(
            sum(
                safe_float(row.get("avg_oem_service_level_without_adaptation"))
                for row in sdd["sdd_monthly_impacts"]
            )
        )
        acv_deltas.append(
            sum(safe_float(row.get("sdd_inventory_delta_kgco2e")) for row in bw["monthly"])
        )

    assert (
        service_without_adaptation[0]
        >= service_without_adaptation[1]
        >= service_without_adaptation[2]
    )
    assert acv_deltas[0] <= acv_deltas[1] <= acv_deltas[2]


def test_resumed_resource_flags_keep_false_csv_values_false() -> None:
    summary, monthly = full_scenario_summary(
        {
            "scenario_id": "climat_stationnaire",
            "label": "Stationnaire",
            "description": "",
        },
        event_rows=[],
        node_rows=[{"month_index": "1", "disruption_index": "0.1"}],
        sdd_results={
            "sdd_monthly_impacts": [
                {
                    "month_index": "1",
                    "avg_oem_service_level_without_adaptation": "0.8",
                    "avg_oem_service_level": "0.9",
                }
            ],
            "sdd_resilience_resources": [
                {
                    "month_index": "1",
                    "capacity_boost_saturated": "False",
                    "backup_saturated": "False",
                    "premium_global_saturated": "False",
                }
            ],
        },
        sdd_brightway={"monthly": [{"month_index": "1"}]},
    )

    assert monthly[0]["capacity_boost_saturated_pool_count"] == 0
    assert monthly[0]["backup_saturated_pool_count"] == 0
    assert monthly[0]["premium_global_saturated"] is False
    assert summary["premium_saturated_months"] == 0
