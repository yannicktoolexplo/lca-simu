from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import (
    ROLE_SEQUENCE,
    build_sdd_brightway_exchange_delta,
    compact_sdd_brightway_inventory_delta,
    regionalize_operational_energy_exchange,
    selected_brightway_exchanges_for_mechanism,
    simulate_sdd_supply,
)


def synthetic_supply() -> tuple[list[dict], list[dict], list[dict]]:
    paths: list[dict] = []
    lanes: list[dict] = []
    node_rows: list[dict] = []
    edges = list(zip(ROLE_SEQUENCE[:-1], ROLE_SEQUENCE[1:]))
    for path_index in range(2):
        path_id = f"path-{path_index + 1}"
        path = {
            "path_id": path_id,
            "record_index": path_index + 1,
            "path_mass_kg": 10.0,
            "family": "metal",
            "system": "structure",
            "component": f"component-{path_index + 1}",
        }
        for role_index, role in enumerate(ROLE_SEQUENCE):
            role_key = role.lower()
            if role == "T4":
                site_uid = f"supplier-{path_index + 1}@@48.0,2.0"
            else:
                site_uid = (
                    f"{role_key}-supplier-{path_index + 1}"
                    f"@@{48.0 + role_index},{2.0 + path_index}"
                )
            path[role_key] = f"{role} Supplier {path_index + 1}"
            path[f"{role_key}_site_uid"] = site_uid
            path[f"{role_key}_country_code"] = "FR"
            for month in range(1, 5):
                disrupted = role == "T4"
                node_rows.append(
                    {
                        "scenario_id": "test",
                        "site_uid": site_uid,
                        "month_index": month,
                        "capacity_applied": 0.4 if disrupted else 1.0,
                        "lead_time_multiplier": 1.2 if disrupted else 1.0,
                        "scrap_multiplier": 1.05 if disrupted else 1.0,
                        "disruption_index": 0.6 if disrupted else 0.0,
                        "operational_event_labels": (
                            "perte_capacite" if disrupted else "nominal"
                        ),
                        "source_driver_types": (
                            "canicule" if disrupted else "none"
                        ),
                        "source_environmental_event_ids": (
                            f"env:test:{month}" if disrupted else ""
                        ),
                        "source_transport_flow_uids": "",
                    }
                )
        for edge_index, (from_role, to_role) in enumerate(edges):
            distance = 100.0 + 10.0 * edge_index
            lanes.append(
                {
                    "path_id": path_id,
                    "edge": f"{from_role}->{to_role}",
                    "from_site_uid": path[f"{from_role.lower()}_site_uid"],
                    "to_site_uid": path[f"{to_role.lower()}_site_uid"],
                    "from_name": path[from_role.lower()],
                    "to_name": path[to_role.lower()],
                    "modes": "route",
                    "distance_km": distance,
                    "path_mass_kg": 10.0,
                    "allocated_kg_km": 10.0 * distance,
                }
            )
        paths.append(path)
    return paths, lanes, node_rows


def constrained_policy() -> dict:
    return {
        "capacity_boost": {
            "site_month_capacity_share": 0.10,
            "path_month_capacity_share": 0.30,
            "activation_delay_months": 0,
            "ramp_months": 1,
        },
        "backup_supplier": {
            "site_month_capacity_share": 0.10,
            "path_month_capacity_share": 0.30,
            "oem_path_month_capacity_share": 0.30,
            "qualification_delay_months": 2,
            "ramp_months": 2,
        },
        "premium_transport": {
            "global_month_budget_share_of_baseline_kg_km": 0.0,
            "site_month_mass_share": 0.0,
            "path_month_mass_share": 0.0,
        },
    }


def run_case(paths: list[dict] | None = None) -> dict[str, list[dict]]:
    source_paths, lanes, node_rows = synthetic_supply()
    return simulate_sdd_supply(
        path_rows=paths or source_paths,
        lane_rows=lanes,
        node_operational_rows=node_rows,
        transport_weather_rows=[],
        horizon_months=4,
        scenario_id="test",
        resilience_policy=constrained_policy(),
    )


def test_constrained_engine_conserves_stock_process_and_output_flows() -> None:
    result = run_case()
    for row in result["sdd_node_state"]:
        inbound = row["path_mass_kg"] * row["inbound_service"]
        available_balance = (
            row["stock_start_kg"]
            + inbound
            + row["premium_input_kg"]
            - row["process_input_kg"]
        )
        assert available_balance == pytest.approx(
            row["stock_end_kg"] + row["unallocated_excess_input_kg"],
            abs=2e-3,
        )
        assert row["process_input_kg"] == pytest.approx(
            row["good_output_kg"] + row["scrap_mass_kg"],
            abs=2e-6,
        )
        assert row["final_output_kg"] == pytest.approx(
            row["good_output_kg"] + row["backup_output_kg"],
            abs=2e-6,
        )


def test_shared_pools_are_finite_and_backup_respects_qualification() -> None:
    result = run_case()
    assert all(
        0.0 <= row["avg_supply_regime_score"] <= 1.0
        for row in result["sdd_monthly_impacts"]
    )
    rows = [
        row
        for row in result["sdd_resilience_resources"]
        if row["resilience_pool_key"] == "geo:48.0,2.0"
    ]
    assert len(rows) == 4
    for row in rows:
        assert row["capacity_boost_used_kg"] <= row["capacity_boost_capacity_kg"]
        assert row["backup_used_kg"] <= row["backup_capacity_kg"]
    assert rows[0]["backup_used_kg"] == 0.0
    assert rows[1]["backup_used_kg"] == 0.0
    assert rows[2]["backup_qualified"] is True
    assert rows[2]["backup_capacity_kg"] == pytest.approx(1.0)
    assert rows[3]["backup_capacity_kg"] == pytest.approx(2.0)


def test_zero_resilience_policy_matches_counterfactual() -> None:
    paths, lanes, node_rows = synthetic_supply()
    zero_policy = {
        "capacity_boost": {
            "site_month_capacity_share": 0.0,
            "path_month_capacity_share": 0.0,
        },
        "backup_supplier": {
            "site_month_capacity_share": 0.0,
            "path_month_capacity_share": 0.0,
            "oem_path_month_capacity_share": 0.0,
        },
        "premium_transport": {
            "global_month_budget_share_of_baseline_kg_km": 0.0,
            "site_month_mass_share": 0.0,
            "path_month_mass_share": 0.0,
        },
    }
    result = simulate_sdd_supply(
        path_rows=paths,
        lane_rows=lanes,
        node_operational_rows=node_rows,
        transport_weather_rows=[],
        horizon_months=4,
        scenario_id="test-zero",
        resilience_policy=zero_policy,
    )
    for row in result["sdd_node_state"]:
        assert row["service_level"] == row["service_level_without_adaptation"]
        assert row["backlog_end_kg"] == row["backlog_end_without_adaptation_kg"]
        assert row["adaptation_cost_eur"] == 0.0
        assert row["adaptation_co2_proxy_kgco2e"] == 0.0


def test_shared_pool_allocation_is_independent_from_path_order() -> None:
    paths, _, _ = synthetic_supply()
    forward = run_case(paths)
    reverse = run_case(list(reversed(paths)))

    def node_values(result: dict[str, list[dict]]) -> list[tuple]:
        return sorted(
            (
                row["path_id"],
                row["role"],
                row["month_index"],
                row["service_level"],
                row["capacity_boost_process_kg"],
                row["backup_output_kg"],
            )
            for row in result["sdd_node_state"]
        )

    assert node_values(forward) == node_values(reverse)


def test_physically_dimensioned_transport_and_opera_energy_are_mapped() -> None:
    exchanges = [
        {
            "name": "market for electricity, low voltage",
            "amount": 2.0,
            "unit": "kilowatt hour",
            "type": "technosphere",
        },
        {
            "name": "market for transport, freight, aircraft, medium haul",
            "amount": 3.0,
            "unit": "ton kilometer",
            "type": "technosphere",
        },
    ]
    transport, transport_rule = selected_brightway_exchanges_for_mechanism(
        exchanges,
        "premium_transport",
    )
    energy, energy_rule = selected_brightway_exchanges_for_mechanism(
        exchanges,
        "capacity_energy",
    )

    assert len(transport) == 1
    assert "transport" in transport_rule
    assert len(energy) == 1
    assert energy[0]["unit"] == "kilowatt hour"
    assert energy_rule == "opera_foreground_energy_scaled_by_supported_output"

    french = regionalize_operational_energy_exchange(energy[0], "FR")
    american = regionalize_operational_energy_exchange(energy[0], "US")
    assert french["name"] == "market for electricity, low voltage"
    assert french["location"] == "FR"
    assert american["name"] == "market group for electricity, low voltage"
    assert american["location"] == "US"

    truck_only, fallback_rule = selected_brightway_exchanges_for_mechanism(
        [
            {
                "name": "market for transport, freight, lorry 16-32 metric ton, EURO6",
                "amount": 4.0,
                "unit": "ton kilometer",
                "type": "technosphere",
            }
        ],
        "premium_transport",
    )
    assert len(truck_only) == 1
    assert "aircraft" in truck_only[0]["name"]
    assert "lorry" not in truck_only[0]["name"]
    assert fallback_rule == "virtual_air_freight_market_fallback"


def test_compact_inventory_keeps_activity_and_site_for_exact_energy_mapping() -> None:
    inventory = compact_sdd_brightway_inventory_delta(
        [
            {
                "scenario_id": "test",
                "month_index": 1,
                "role": "T2",
                "site_uid": "site-us",
                "supplier": "Supplier US",
                "country_code": "US",
                "world_region": "North America",
                "family": "aluminium",
                "mechanism": "capacity_energy",
                "inventory_delta_type": "auxiliary_capacity_energy",
                "amount_delta": 2.0,
                "amount_unit": "kg output supported by capacity boost",
                "delta_kgco2e": 1.0,
                "include_in_dynamic_acv": True,
                "path_mass_kg": 10.0,
                "model_physical_activity_share": 0.2,
                "brightway_system": "Structure",
                "brightway_component": "Component",
                "brightway_activity_proxy": "production du siege",
                "brightway_exchange_proxy": "site energy",
                "brightway_match_level": "system_only",
                "calibration_source": "test",
                "confidence": "medium",
            }
        ]
    )
    assert inventory[0]["country_code"] == "US"
    assert inventory[0]["brightway_system"] == "Structure"
    assert inventory[0]["model_physical_activity_share_sum"] == pytest.approx(0.2)

    exchange_rows, _, _ = build_sdd_brightway_exchange_delta(
        inventory,
        {
            "exchanges": [
                {
                    "activity_name": "Structure",
                    "name": "market for electricity, low voltage",
                    "amount": 2.0,
                    "unit": "kilowatt hour",
                    "type": "technosphere",
                    "database": "ecoinvent-3.10-cutoff",
                    "location": "FR",
                    "reference_product": "electricity, low voltage",
                }
            ]
        },
    )
    assert len(exchange_rows) == 1
    row = exchange_rows[0]
    assert row["exchange_name"] == "market group for electricity, low voltage"
    assert row["exchange_location"] == "US"
    assert row["exchange_unit"] == "kilowatt hour"
    assert row["delta_amount"] == pytest.approx(0.4)
    assert row["physical_quantity_status"] == "estimated_from_opera_foreground_energy_inventory"
    assert row["brightway_exact_eligible"] is True
