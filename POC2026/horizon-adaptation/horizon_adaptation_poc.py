import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "outputs"
CSV_DIR = OUT_DIR / "csv"
IMG_DIR = OUT_DIR / "images"
CSV_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

MONTHS = list(range(1, 241))
START_YEAR = 2026

MAIN_LEAD = 3
BACKUP_LEAD = 1
RAW_STORAGE_EF = 0.012
FG_STORAGE_EF = 0.018
SOLAR_EF = 0.035
BIOMASS_EF = 0.16
BATTERY_USE_EF = 0.025
BACKUP_MATERIAL_PREMIUM_EF = 5.5
BACKUP_INBOUND_PREMIUM_EF = 2.8
AIR_PREMIUM_EF = 6.8

SOLAR_LCOE = 0.04
BIOMASS_LCOE = 0.085
BATTERY_CYCLE_COST = 0.03
STORAGE_FIXED_COST = 0.35
BACKLOG_PENALTY_COST = 25.0
BATTERY_CAPEX_MONTHLY = 2.8
SOLAR_CAPEX_MONTHLY = 0.9
BIOMASS_CAPEX_MONTHLY = 1.1


@dataclass(frozen=True)
class AdaptationPolicy:
    name: str
    label: str
    raw_target: float
    reorder_threshold: float
    fg_target: float
    backup_order_qty: float
    air_start_threshold: float
    air_end_threshold: float
    solar_scale: float
    battery_capacity: float
    biomass_capacity: float
    insulation_factor: float
    cooling_upgrade: float


POLICIES = [
    AdaptationPolicy(
        name="reference_2045",
        label="Reference 2045",
        raw_target=55.0,
        reorder_threshold=24.0,
        fg_target=14.0,
        backup_order_qty=12.0,
        air_start_threshold=14.0,
        air_end_threshold=24.0,
        solar_scale=10.0,
        battery_capacity=18.0,
        biomass_capacity=4.0,
        insulation_factor=1.0,
        cooling_upgrade=1.0,
    ),
    AdaptationPolicy(
        name="resilience_inventory",
        label="Stock de resilience",
        raw_target=78.0,
        reorder_threshold=34.0,
        fg_target=22.0,
        backup_order_qty=14.0,
        air_start_threshold=16.0,
        air_end_threshold=28.0,
        solar_scale=10.0,
        battery_capacity=18.0,
        biomass_capacity=4.0,
        insulation_factor=0.95,
        cooling_upgrade=1.05,
    ),
    AdaptationPolicy(
        name="energy_autonomy",
        label="Autonomie energetique",
        raw_target=55.0,
        reorder_threshold=24.0,
        fg_target=14.0,
        backup_order_qty=12.0,
        air_start_threshold=14.0,
        air_end_threshold=24.0,
        solar_scale=18.0,
        battery_capacity=42.0,
        biomass_capacity=9.0,
        insulation_factor=0.82,
        cooling_upgrade=0.86,
    ),
    AdaptationPolicy(
        name="integrated_adaptation",
        label="Adaptation integree",
        raw_target=82.0,
        reorder_threshold=34.0,
        fg_target=22.0,
        backup_order_qty=16.0,
        air_start_threshold=18.0,
        air_end_threshold=30.0,
        solar_scale=20.0,
        battery_capacity=48.0,
        biomass_capacity=10.0,
        insulation_factor=0.74,
        cooling_upgrade=0.78,
    ),
    AdaptationPolicy(
        name="lean_exposed",
        label="Lean expose",
        raw_target=40.0,
        reorder_threshold=18.0,
        fg_target=8.0,
        backup_order_qty=10.0,
        air_start_threshold=10.0,
        air_end_threshold=18.0,
        solar_scale=6.0,
        battery_capacity=8.0,
        biomass_capacity=0.0,
        insulation_factor=1.14,
        cooling_upgrade=1.12,
    ),
]

TIMELINE_POLICY_NAME = "lean_exposed"


def build_exogenous_context() -> pd.DataFrame:
    rows = []
    for t in MONTHS:
        year = START_YEAR + (t - 1) // 12
        month = ((t - 1) % 12) + 1
        season_angle = 2 * math.pi * (month - 1) / 12
        warming = 2.0 * (t - 1) / (len(MONTHS) - 1)
        transition_progress = (t - 1) / (len(MONTHS) - 1)
        seasonal_temperature = 13.0 * math.sin(season_angle - math.pi / 2)

        heatwave = 0.0
        storm = 0.0
        drought = 0.0

        # Climate shocks become more frequent and more severe over time.
        if month in [7, 8] and (year >= 2029 and ((year - 2029) % 3 == 0 or year >= 2038)):
            heatwave = 0.65 + 0.70 * transition_progress
        if month in [6, 7, 8] and year >= 2040:
            heatwave = max(heatwave, 0.85 + 0.55 * transition_progress)

        if month in [5, 6, 7] and (year >= 2031 and ((year - 2031) % 5 in [0, 1] or year >= 2041)):
            drought = 0.55 + 0.60 * transition_progress
        if month in [4, 5, 6, 7] and year >= 2042:
            drought = max(drought, 0.75 + 0.45 * transition_progress)

        if month in [10, 11] and (year >= 2030 and ((year - 2030) % 4 == 0 or year >= 2038)):
            storm = 0.60 + 0.70 * transition_progress
        if month in [1, 2] and year >= 2036 and ((year - 2036) % 5 in [0, 1] or year >= 2043):
            storm = max(storm, 0.45 + 0.55 * transition_progress)

        chronic_heat = 0.22 * warming + max(0.0, seasonal_temperature - 7.0) / 18.0
        heat_stress = max(0.0, chronic_heat + 1.05 * heatwave)
        cold_stress = max(0.0, -seasonal_temperature / 12.0)
        storm_stress = storm
        scarcity = min(1.25, 0.10 + 0.14 * warming + 0.55 * drought + 0.18 * storm_stress)

        grid_factor = max(0.08, 0.52 - 0.28 * transition_progress + 0.06 * heatwave + 0.04 * storm_stress + 0.02 * cold_stress)
        grid_price = 0.14 + 0.035 * heat_stress + 0.02 * scarcity + 0.015 * cold_stress
        main_material_ef = 18.0 + 2.8 * scarcity - 0.8 * (t - 1) / (len(MONTHS) - 1)
        main_material_cost = 44.0 + 18.0 * scarcity + 6.0 * warming
        inbound_main_ef = 0.75 + 0.18 * storm_stress + 0.06 * scarcity
        inbound_main_cost = 2.4 + 1.5 * storm_stress + 0.9 * scarcity
        truck_ef = max(1.15, 1.75 - 0.35 * (t - 1) / (len(MONTHS) - 1) + 0.24 * storm_stress)
        truck_cost = 6.0 + 2.5 * storm_stress + 0.75 * scarcity
        air_ef = max(6.4, 9.6 - 1.1 * (t - 1) / (len(MONTHS) - 1) + 0.4 * storm_stress)
        air_cost = 24.0 + 7.0 * storm_stress + 1.2 * scarcity

        solar_factor = max(0.06, 0.65 + 0.30 * math.sin(season_angle - math.pi / 2) - 0.08 * heatwave - 0.04 * storm_stress)
        biomass_factor = max(0.0, 0.85 - 0.32 * drought)

        demand = 18.0 + 0.028 * t + 1.6 * math.sin(season_angle) + 0.32 * heat_stress + 0.28 * cold_stress
        main_supply_availability = min(1.0, max(0.35, 0.985 - 0.08 * warming - 0.28 * drought - 0.34 * storm_stress))
        backup_supply_availability = min(1.0, max(0.55, 0.965 - 0.04 * warming - 0.14 * drought - 0.18 * storm_stress))
        tech_progress = 4.5 * (t - 1) / (len(MONTHS) - 1)
        base_capacity = max(
            12.0,
            34.5
            + tech_progress
            - 0.90 * warming
            - 3.10 * heatwave
            - 1.20 * drought
            - 2.50 * storm_stress,
        )

        climate_event = "aucun"
        if heatwave > 0 and drought > 0:
            climate_event = "canicule + secheresse"
        elif heatwave > 0:
            climate_event = "canicule"
        elif drought > 0:
            climate_event = "secheresse"
        elif storm_stress > 0:
            climate_event = "tempete / inondation"

        rows.append({
            "month_index": t,
            "year": year,
            "month": month,
            "warming": warming,
            "heat_stress": heat_stress,
            "cold_stress": cold_stress,
            "storm_stress": storm_stress,
            "scarcity": scarcity,
            "climate_event": climate_event,
            "demand": demand,
            "grid_factor": grid_factor,
            "grid_price": grid_price,
            "main_material_ef": main_material_ef,
            "main_material_cost": main_material_cost,
            "inbound_main_ef": inbound_main_ef,
            "inbound_main_cost": inbound_main_cost,
            "truck_ef": truck_ef,
            "truck_cost": truck_cost,
            "air_ef": air_ef,
            "air_cost": air_cost,
            "solar_factor": solar_factor,
            "biomass_factor": biomass_factor,
            "main_supply_availability": main_supply_availability,
            "backup_supply_availability": backup_supply_availability,
            "base_capacity": base_capacity,
        })
    return pd.DataFrame(rows)


EXOGENOUS = build_exogenous_context()


def consume_fifo(inventory: list[dict], qty: float) -> dict[str, float]:
    remaining = float(qty)
    consumed = {"main": 0.0, "backup": 0.0}
    while remaining > 1e-9 and inventory:
        batch = inventory[0]
        take = min(batch["qty"], remaining)
        consumed[batch["source"]] += take
        batch["qty"] -= take
        remaining -= take
        if batch["qty"] <= 1e-9:
            inventory.pop(0)
    if remaining > 1e-9:
        raise ValueError("Insufficient inventory")
    return consumed


def add_batch(inventory: list[dict], qty: float, source: str) -> None:
    if qty > 1e-9:
        inventory.append({"source": source, "qty": float(qty)})


def inventory_total(inventory: list[dict]) -> float:
    return sum(batch["qty"] for batch in inventory)


def safe_ratio(a: float, b: float) -> float:
    return 0.0 if b <= 0 else a / b


def process_kwh_per_unit(utilization: float, heat_stress: float, cooling_upgrade: float) -> float:
    base = 5.8 + 1.3 * heat_stress * cooling_upgrade
    if utilization > 0.92:
        base += 2.2
    elif utilization > 0.80:
        base += 0.8
    return base


def scrap_rate(utilization: float, heat_stress: float) -> float:
    base = 0.015 * heat_stress
    if utilization > 0.95:
        base += 0.085
    elif utilization > 0.85:
        base += 0.035
    return min(0.18, base)


def hvac_kwh(raw_stock: float, fg_stock: float, heat_stress: float, cold_stress: float, insulation_factor: float) -> float:
    base_load = raw_stock * 0.05 + fg_stock * 0.08
    thermal_multiplier = 1.0 + 1.5 * heat_stress + 1.0 * cold_stress
    return base_load * thermal_multiplier * insulation_factor


def simulate_policy(policy: AdaptationPolicy) -> pd.DataFrame:
    raw_inventory = [{"source": "main", "qty": 72.0}]
    fg_inventory = [{"source": "main", "qty": 24.0}]
    # A pipeline of length L means an order placed now arrives after L periods.
    main_pipeline = [0.0] * MAIN_LEAD
    backup_pipeline = [0.0] * BACKUP_LEAD
    backlog = 0.0
    battery_soc = 0.45 * policy.battery_capacity
    battery_soh = 1.0
    biomass_transition_level = 0.0
    next_capacity_multiplier = 1.0
    next_grid_bonus = 0.0
    next_main_supply_multiplier = 1.0
    next_backup_supply_multiplier = 1.0
    next_quality_penalty = 0.0
    next_hvac_bonus = 0.0
    next_operational_event = "aucun"
    rows = []

    for row in EXOGENOUS.to_dict(orient="records"):
        month_index = int(row["month_index"])

        main_inbound = main_pipeline.pop(0)
        backup_inbound = backup_pipeline.pop(0)
        main_pipeline.append(0.0)
        backup_pipeline.append(0.0)
        add_batch(raw_inventory, main_inbound, "main")
        add_batch(raw_inventory, backup_inbound, "backup")

        raw_stock_start = inventory_total(raw_inventory)
        fg_stock_start = inventory_total(fg_inventory)
        main_supply_position = raw_stock_start + sum(main_pipeline)
        backup_supply_position = raw_stock_start + sum(main_pipeline) + sum(backup_pipeline)
        climate_event = row["climate_event"]

        climate_capacity_multiplier = 1.0
        climate_main_supply_multiplier = 1.0
        climate_backup_supply_multiplier = 1.0
        climate_grid_bonus = 0.0
        climate_hvac_bonus = 0.0
        climate_quality_penalty = 0.0
        climate_outbound_multiplier = 1.0
        climate_labels = []

        if "canicule" in climate_event:
            climate_capacity_multiplier *= 0.86
            climate_grid_bonus += 0.04
            climate_hvac_bonus += 0.24 + 0.08 * row["heat_stress"]
            climate_quality_penalty += 0.014
            climate_outbound_multiplier *= 0.94
            climate_labels.append("site en surchauffe")
        if "secheresse" in climate_event:
            climate_capacity_multiplier *= 0.90
            climate_main_supply_multiplier *= 0.78
            climate_backup_supply_multiplier *= 0.88
            climate_grid_bonus += 0.02
            climate_quality_penalty += 0.010
            climate_outbound_multiplier *= 0.92
            climate_labels.append("stress matiere / eau")
        if "tempete" in climate_event:
            climate_capacity_multiplier *= 0.82
            climate_main_supply_multiplier *= 0.58
            climate_backup_supply_multiplier *= 0.76
            climate_grid_bonus += 0.05
            climate_hvac_bonus += 0.10
            climate_outbound_multiplier *= 0.68
            climate_labels.append("desorganisation logistique")

        demand_t = row["demand"]
        lead_cover_target = demand_t * (MAIN_LEAD + 0.75) + 0.55 * backlog + 0.60 * policy.fg_target
        adaptive_raw_target = max(policy.raw_target, lead_cover_target)
        requested_main = max(0.0, adaptive_raw_target - main_supply_position)
        requested_backup = 0.0
        main_availability = min(
            1.0,
            row["main_supply_availability"] * climate_main_supply_multiplier * next_main_supply_multiplier,
        )
        backup_availability = min(
            1.0,
            row["backup_supply_availability"] * climate_backup_supply_multiplier * next_backup_supply_multiplier,
        )
        if (
            raw_stock_start < policy.reorder_threshold
            or backup_supply_position < policy.reorder_threshold
            or backlog > policy.air_start_threshold
            or main_availability < 0.88
        ):
            requested_backup = (
                policy.backup_order_qty
                + 0.22 * backlog
                + 0.35 * max(0.0, policy.reorder_threshold - raw_stock_start)
                + 18.0 * max(0.0, 0.90 - main_availability)
            )
        main_order = requested_main * main_availability
        backup_order = requested_backup * backup_availability
        main_pipeline[-1] += main_order
        backup_pipeline[-1] += backup_order

        capacity_bonus = (
            0.05 * (policy.solar_scale / 10.0)
            + 0.06 * (policy.battery_capacity / 40.0)
            + 0.05 * (policy.biomass_capacity / 10.0)
            + 0.14 * max(0.0, 1.0 - policy.insulation_factor)
            + 0.10 * max(0.0, 1.0 - policy.cooling_upgrade)
        )
        backlog_relief_capacity = 0.0
        if backlog > 0:
            backlog_relief_capacity = min(
                backlog * 0.11,
                0.18 * row["base_capacity"] + 0.05 * policy.battery_capacity + 0.12 * policy.biomass_capacity,
            )
        capacity_applied = max(
            8.0,
            row["base_capacity"] * climate_capacity_multiplier * (1.0 + capacity_bonus) * next_capacity_multiplier
            + backlog_relief_capacity,
        )
        service_pressure = demand_t + backlog
        fg_replenishment = max(0.0, policy.fg_target - fg_stock_start)
        planned_input = min(capacity_applied, raw_stock_start, service_pressure + fg_replenishment)
        utilization = safe_ratio(planned_input, capacity_applied)

        consumed = consume_fifo(raw_inventory, planned_input)
        sr = min(0.22, scrap_rate(utilization, row["heat_stress"]) + climate_quality_penalty + next_quality_penalty)
        scrap_main = consumed["main"] * sr
        scrap_backup = consumed["backup"] * sr
        good_output_main = consumed["main"] - scrap_main
        good_output_backup = consumed["backup"] - scrap_backup
        good_output = good_output_main + good_output_backup
        add_batch(fg_inventory, good_output_main, "main")
        add_batch(fg_inventory, good_output_backup, "backup")

        shipment_request = demand_t + backlog
        shipment_capacity = shipment_request * climate_outbound_multiplier
        shipments = min(inventory_total(fg_inventory), shipment_capacity)
        shipped = consume_fifo(fg_inventory, shipments)
        backlog_end = max(0.0, backlog + demand_t - shipments)

        backlog_growth = max(0.0, backlog_end - backlog)
        service_gap = max(0.0, demand_t + backlog - shipments)
        climate_pressure = row["heat_stress"] + row["storm_stress"] + 0.55 * row["scarcity"]
        outbound_mode = "truck"
        if (
            backlog_end > policy.air_end_threshold
            and (
                backlog_growth > 3.0
                or service_gap > 0.25 * max(demand_t, 1.0)
                or climate_pressure > 1.45
                or backlog_end > 1.55 * policy.air_end_threshold
            )
        ):
            outbound_mode = "air"
        elif (
            backlog > policy.air_start_threshold
            and climate_pressure > 1.7
            and service_gap > 0.18 * max(demand_t, 1.0)
        ):
            outbound_mode = "air"

        process_kwh = good_output * process_kwh_per_unit(utilization, row["heat_stress"], policy.cooling_upgrade)
        if backlog_relief_capacity > 0:
            process_kwh += backlog_relief_capacity * (0.35 + 0.22 * row["heat_stress"])
        process_kwh *= 1.0 + 0.05 * len(climate_labels)
        hvac_energy = hvac_kwh(
            inventory_total(raw_inventory),
            inventory_total(fg_inventory),
            row["heat_stress"],
            row["cold_stress"],
            policy.insulation_factor,
        )
        hvac_energy *= 1.0 + climate_hvac_bonus + next_hvac_bonus
        total_energy_demand = process_kwh + hvac_energy

        solar_generation = policy.solar_scale * row["solar_factor"]
        base_biomass_generation = policy.biomass_capacity * row["biomass_factor"]

        solar_used = min(total_energy_demand, solar_generation)
        residual_after_solar = max(0.0, total_energy_demand - solar_used)

        available_battery = policy.battery_capacity * battery_soh
        prospective_battery_discharge = min(residual_after_solar, battery_soc, 0.42 * available_battery)
        prospective_grid_need = max(0.0, residual_after_solar - prospective_battery_discharge - base_biomass_generation)
        prospective_grid_share = safe_ratio(prospective_grid_need, total_energy_demand)

        biomass_ramp_target = min(
            0.9,
            0.70 * prospective_grid_share
            + 0.22 * max(0.0, row["grid_factor"] - 0.24)
            + 0.16 * max(0.0, row["grid_price"] - 0.17)
            + 0.12 * row["scarcity"],
        )
        biomass_transition_cap = min(
            0.65,
            max(
                0.18,
                0.18
                + 0.038 * policy.biomass_capacity
                + 0.06 * max(0.0, 1.0 - row["scarcity"])
                - 0.05 * row["storm_stress"],
            ),
        )
        biomass_transition_level = min(
            biomass_transition_cap,
            max(
                0.0,
                0.92 * biomass_transition_level
                + 0.10 * biomass_ramp_target
                + 0.04 * min(1.0, safe_ratio(backlog, 20.0)),
            ),
        )
        biomass_multiplier = 1.0 + 2.0 * biomass_transition_level
        biomass_generation = base_biomass_generation * biomass_multiplier

        direct_clean_supply = min(total_energy_demand, solar_generation + biomass_generation)
        residual_demand = max(0.0, total_energy_demand - direct_clean_supply)

        battery_discharge = min(residual_demand, battery_soc, 0.42 * available_battery)
        battery_soc -= battery_discharge
        residual_demand -= battery_discharge
        grid_energy = residual_demand

        excess_solar = max(0.0, solar_generation + biomass_generation - direct_clean_supply)
        if available_battery > 0:
            charge_room = max(0.0, available_battery - battery_soc)
            battery_charge = min(excess_solar, charge_room, 0.35 * available_battery)
        else:
            battery_charge = 0.0
        battery_soc += battery_charge
        battery_throughput = battery_discharge + battery_charge
        battery_soh = max(0.58, battery_soh - 0.00028 * battery_throughput - 0.00018 * row["heat_stress"])

        biomass_used = min(max(0.0, total_energy_demand - solar_used), biomass_generation)
        solar_share = safe_ratio(solar_used, total_energy_demand)
        biomass_share = safe_ratio(biomass_used, total_energy_demand)
        grid_share = safe_ratio(grid_energy, total_energy_demand)

        operational_labels = []
        next_capacity_multiplier = 1.0
        next_grid_bonus = 0.0
        next_main_supply_multiplier = 1.0
        next_backup_supply_multiplier = 1.0
        next_quality_penalty = 0.0
        next_hvac_bonus = 0.0

        if climate_labels:
            next_capacity_multiplier *= max(0.74, climate_capacity_multiplier + 0.02)
            next_main_supply_multiplier *= max(0.56, climate_main_supply_multiplier + 0.03)
            next_backup_supply_multiplier *= max(0.70, climate_backup_supply_multiplier + 0.03)
            next_grid_bonus += 0.70 * climate_grid_bonus
            next_quality_penalty += 0.60 * climate_quality_penalty
            next_hvac_bonus += 0.50 * climate_hvac_bonus
            operational_labels.extend(climate_labels)

        if utilization > 0.94:
            next_capacity_multiplier *= 0.92
            operational_labels.append("maintenance corrective")
        if outbound_mode == "air":
            next_main_supply_multiplier *= 0.96
            next_backup_supply_multiplier *= 0.97
            next_grid_bonus += 0.03
            operational_labels.append("congestion logistique")
        if backlog_end > 16.0:
            next_capacity_multiplier *= 0.95
            next_grid_bonus += 0.02
            operational_labels.append("overtime energetique")
        elif backlog_relief_capacity > 0:
            operational_labels.append("capacite d'appoint")
        if scrap_main + scrap_backup > 1.0:
            next_capacity_multiplier *= 0.96
            operational_labels.append("recalage qualite")
        next_operational_event = " + ".join(operational_labels) if operational_labels else "aucun"

        effective_grid_factor = row["grid_factor"] + next_grid_bonus
        energy_mix_ef = (
            grid_energy * effective_grid_factor
            + min(total_energy_demand, solar_generation) * SOLAR_EF
            + min(max(0.0, total_energy_demand - solar_generation), biomass_generation) * BIOMASS_EF
            + battery_discharge * BATTERY_USE_EF
        ) / max(total_energy_demand, 1e-9)

        rows.append({
            "policy_name": policy.name,
            "policy_label": policy.label,
            **row,
            "capacity_applied": capacity_applied,
            "backlog_relief_capacity": backlog_relief_capacity,
            "main_supply_availability_applied": main_availability,
            "backup_supply_availability_applied": backup_availability,
            "main_inbound": main_inbound,
            "backup_inbound": backup_inbound,
            "main_order_requested": requested_main,
            "backup_order_requested": requested_backup,
            "main_order": main_order,
            "backup_order": backup_order,
            "raw_stock_end": inventory_total(raw_inventory),
            "fg_stock_end": inventory_total(fg_inventory),
            "backlog_start": backlog,
            "backlog_end": backlog_end,
            "planned_input_units": planned_input,
            "capacity_utilization": utilization,
            "good_output_main_units": good_output_main,
            "good_output_backup_units": good_output_backup,
            "good_output_units": good_output,
            "scrap_main_units": scrap_main,
            "scrap_backup_units": scrap_backup,
            "scrap_units": scrap_main + scrap_backup,
            "outbound_shipments": shipments,
            "shipped_main_units": shipped["main"],
            "shipped_backup_units": shipped["backup"],
            "outbound_mode": outbound_mode,
            "process_kwh": process_kwh,
            "hvac_kwh": hvac_energy,
            "total_energy_demand": total_energy_demand,
            "solar_generation_kwh": solar_generation,
            "solar_used_kwh": solar_used,
            "solar_share": solar_share,
            "biomass_generation_base_kwh": base_biomass_generation,
            "biomass_generation_kwh": biomass_generation,
            "biomass_used_kwh": biomass_used,
            "biomass_share": biomass_share,
            "biomass_transition_level": biomass_transition_level,
            "biomass_transition_cap": biomass_transition_cap,
            "battery_discharge_kwh": battery_discharge,
            "battery_charge_kwh": battery_charge,
            "grid_energy_kwh": grid_energy,
            "grid_share": grid_share,
            "battery_soc_kwh": battery_soc,
            "battery_soh": battery_soh,
            "effective_grid_factor": effective_grid_factor,
            "energy_mix_ef": energy_mix_ef,
            "climate_operational_impact": " + ".join(climate_labels) if climate_labels else "aucun",
            "operational_feedback_event": next_operational_event,
        })
        backlog = backlog_end

    return pd.DataFrame(rows)


def compute_classical_lca(states: pd.DataFrame) -> dict:
    avg_material_ef = float(states["main_material_ef"].mean())
    avg_inbound_ef = float(states["inbound_main_ef"].mean())
    avg_truck_ef = float(states["truck_ef"].mean())
    avg_energy_mix_ef = float(states["energy_mix_ef"].mean())
    total_good = float(states["good_output_units"].sum())
    total_ship = float(states["outbound_shipments"].sum())
    total_process_kwh = float(states["process_kwh"].sum())
    total_hvac_kwh = float(states["hvac_kwh"].sum())
    avg_storage = float((states["raw_stock_end"] * RAW_STORAGE_EF + states["fg_stock_end"] * FG_STORAGE_EF).mean())
    return {
        "material": total_good * avg_material_ef,
        "inbound_transport": total_good * avg_inbound_ef,
        "production_energy": total_process_kwh * avg_energy_mix_ef,
        "outbound_transport": total_ship * avg_truck_ef,
        "storage": total_hvac_kwh * avg_energy_mix_ef + avg_storage * len(states),
        "scrap": 0.0,
        "total": 0.0,
    }


def compute_time_dependent_dlca(states: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for _, r in states.iterrows():
        rows.append({
            "month_index": int(r["month_index"]),
            "material": r["good_output_units"] * r["main_material_ef"],
            "inbound_transport": r["good_output_units"] * r["inbound_main_ef"],
            "production_energy": r["process_kwh"] * r["energy_mix_ef"],
            "outbound_transport": r["outbound_shipments"] * r["truck_ef"],
            "storage": r["hvac_kwh"] * r["energy_mix_ef"] + r["raw_stock_end"] * RAW_STORAGE_EF + r["fg_stock_end"] * FG_STORAGE_EF,
            "scrap": 0.0,
        })
    df = pd.DataFrame(rows)
    df["total"] = df.sum(axis=1, numeric_only=True)
    return df, df[["material", "inbound_transport", "production_energy", "outbound_transport", "storage", "scrap", "total"]].sum().to_dict()


def compute_sdd(states: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for _, r in states.iterrows():
        backup_material_ef = r["main_material_ef"] + BACKUP_MATERIAL_PREMIUM_EF
        material = (
            r["good_output_main_units"] * r["main_material_ef"]
            + r["good_output_backup_units"] * backup_material_ef
        )
        inbound = (
            r["good_output_main_units"] * r["inbound_main_ef"]
            + r["good_output_backup_units"] * (r["inbound_main_ef"] + BACKUP_INBOUND_PREMIUM_EF)
        )
        outbound_factor = r["air_ef"] if r["outbound_mode"] == "air" else r["truck_ef"]
        outbound = r["outbound_shipments"] * outbound_factor
        scrap = (
            r["scrap_main_units"] * (r["main_material_ef"] + r["inbound_main_ef"] + r["energy_mix_ef"] * process_kwh_per_unit(r["capacity_utilization"], r["heat_stress"], 1.0))
            + r["scrap_backup_units"] * (backup_material_ef + r["inbound_main_ef"] + BACKUP_INBOUND_PREMIUM_EF + r["energy_mix_ef"] * process_kwh_per_unit(r["capacity_utilization"], r["heat_stress"], 1.0))
        )
        rows.append({
            "month_index": int(r["month_index"]),
            "material": material,
            "inbound_transport": inbound,
            "production_energy": r["process_kwh"] * r["energy_mix_ef"],
            "outbound_transport": outbound,
            "storage": r["hvac_kwh"] * r["energy_mix_ef"] + r["raw_stock_end"] * RAW_STORAGE_EF + r["fg_stock_end"] * FG_STORAGE_EF,
            "scrap": scrap,
        })
    df = pd.DataFrame(rows)
    df["total"] = df.sum(axis=1, numeric_only=True)
    return df, df[["material", "inbound_transport", "production_energy", "outbound_transport", "storage", "scrap", "total"]].sum().to_dict()


def compute_costs(states: pd.DataFrame, policy: AdaptationPolicy) -> tuple[pd.DataFrame, dict]:
    rows = []
    for _, r in states.iterrows():
        outbound_cost = r["air_cost"] if r["outbound_mode"] == "air" else r["truck_cost"]
        backup_material_cost = r["main_material_cost"] * 1.28
        grid_cost = r["grid_energy_kwh"] * r["grid_price"]
        solar_cost = r["solar_used_kwh"] * SOLAR_LCOE
        biomass_cost = r["biomass_used_kwh"] * BIOMASS_LCOE
        battery_cost = r["battery_discharge_kwh"] * BATTERY_CYCLE_COST
        rows.append({
            "month_index": int(r["month_index"]),
            "material": r["good_output_main_units"] * r["main_material_cost"] + r["good_output_backup_units"] * backup_material_cost,
            "inbound_transport": r["good_output_main_units"] * r["inbound_main_cost"] + r["good_output_backup_units"] * (r["inbound_main_cost"] + 1.5),
            "energy": grid_cost + solar_cost + biomass_cost + battery_cost,
            "storage": r["hvac_kwh"] * (r["grid_price"] * 0.55 + SOLAR_LCOE * 0.15) + STORAGE_FIXED_COST * (r["raw_stock_end"] + r["fg_stock_end"]),
            "outbound_transport": r["outbound_shipments"] * outbound_cost,
            "backlog_penalty": r["backlog_end"] * BACKLOG_PENALTY_COST,
            "adaptation_capex": policy.solar_scale * SOLAR_CAPEX_MONTHLY + policy.battery_capacity * BATTERY_CAPEX_MONTHLY + policy.biomass_capacity * BIOMASS_CAPEX_MONTHLY,
        })
    df = pd.DataFrame(rows)
    df["total"] = df.sum(axis=1, numeric_only=True)
    return df, df[["material", "inbound_transport", "energy", "storage", "outbound_transport", "backlog_penalty", "adaptation_capex", "total"]].sum().to_dict()


def evaluate_policy(policy: AdaptationPolicy) -> dict:
    states = simulate_policy(policy)
    classical = compute_classical_lca(states)
    time_dependent, td_breakdown = compute_time_dependent_dlca(states)
    sdd, sdd_breakdown = compute_sdd(states)
    cost_df, cost_breakdown = compute_costs(states, policy)
    classical["total"] = sum(value for key, value in classical.items() if key != "total")
    summary = {
        "policy_name": policy.name,
        "policy_label": policy.label,
        "service_pct": round(100 * safe_ratio(states["outbound_shipments"].sum(), states["demand"].sum()), 2),
        "same_period_service_pct": round(100 * safe_ratio(np.minimum(states["outbound_shipments"], states["demand"]).sum(), states["demand"].sum()), 2),
        "final_backlog": round(float(states["backlog_end"].iloc[-1]), 2),
        "peak_backlog": round(float(states["backlog_end"].max()), 2),
        "battery_soh_final": round(float(states["battery_soh"].iloc[-1]), 3),
        "classical_total_kgCO2e": round(classical["total"], 2),
        "time_dependent_dlca_total_kgCO2e": round(td_breakdown["total"], 2),
        "sdd_total_kgCO2e": round(sdd_breakdown["total"], 2),
        "hidden_carbon_vs_td_dlca": round(sdd_breakdown["total"] - td_breakdown["total"], 2),
        "hidden_carbon_vs_classical": round(sdd_breakdown["total"] - classical["total"], 2),
        "total_cost": round(cost_breakdown["total"], 2),
    }
    return {
        "states": states,
        "classical": classical,
        "time_dependent_dlca": time_dependent,
        "time_dependent_breakdown": td_breakdown,
        "sdd": sdd,
        "sdd_breakdown": sdd_breakdown,
        "costs": cost_df,
        "cost_breakdown": cost_breakdown,
        "summary": summary,
    }


def classify_environmental_regime(row: pd.Series) -> str:
    climate_shock = row["climate_event"] != "aucun"
    operational_stress = row["backlog_end"] > 10.0 or row["capacity_utilization"] > 0.93 or row["outbound_mode"] == "air"
    if (
        row["backlog_end"] > 24.0
        or (row["outbound_mode"] == "air" and row["backlog_end"] > 10.0)
        or (climate_shock and operational_stress)
        or (row["capacity_utilization"] > 0.97 and row["scrap_units"] > 0.8)
    ):
        return "crise"
    if (
        climate_shock
        or row["backlog_end"] > 4.0
        or row["capacity_utilization"] > 0.82
        or (row["grid_share"] > 0.90 and row["heat_stress"] > 0.75)
        or row["scarcity"] > 0.78
    ):
        return "tendu"
    return "nominal"


def build_event_timeline(states: pd.DataFrame) -> pd.DataFrame:
    timeline = states[[
        "month_index",
        "year",
        "month",
        "climate_event",
        "operational_feedback_event",
        "backlog_end",
        "capacity_utilization",
        "grid_share",
        "scarcity",
        "outbound_mode",
    ]].copy()
    timeline["regime_environnemental"] = states.apply(classify_environmental_regime, axis=1)
    timeline["evt_canicule"] = timeline["climate_event"].str.contains("canicule").astype(int)
    timeline["evt_secheresse"] = timeline["climate_event"].str.contains("secheresse").astype(int)
    timeline["evt_tempete_inondation"] = timeline["climate_event"].str.contains("tempete").astype(int)
    timeline["evt_maintenance_corrective"] = timeline["operational_feedback_event"].str.contains("maintenance corrective").astype(int)
    timeline["evt_congestion_logistique"] = timeline["operational_feedback_event"].str.contains("congestion logistique").astype(int)
    timeline["evt_overtime_energetique"] = timeline["operational_feedback_event"].str.contains("overtime energetique").astype(int)
    timeline["evt_capacite_appoint"] = timeline["operational_feedback_event"].str.contains("capacite d'appoint").astype(int)
    timeline["evt_recalage_qualite"] = timeline["operational_feedback_event"].str.contains("recalage qualite").astype(int)
    return timeline


def build_event_impact_breakdown(td: pd.DataFrame, sdd: pd.DataFrame) -> pd.DataFrame:
    event_impact = pd.DataFrame({
        "month_index": td["month_index"],
        "surimpact_matiere": sdd["material"] - td["material"],
        "surimpact_inbound": sdd["inbound_transport"] - td["inbound_transport"],
        "surimpact_transport_aval": sdd["outbound_transport"] - td["outbound_transport"],
        "surimpact_rebut": sdd["scrap"] - td["scrap"],
    })
    event_impact["surimpact_total"] = event_impact[
        [
            "surimpact_matiere",
            "surimpact_inbound",
            "surimpact_transport_aval",
            "surimpact_rebut",
        ]
    ].sum(axis=1)
    event_impact["surimpact_cumule"] = event_impact["surimpact_total"].cumsum()
    return event_impact


def build_outputs() -> None:
    results = [evaluate_policy(policy) for policy in POLICIES]
    results_by_name = {result["summary"]["policy_name"]: result for result in results}
    summary = pd.DataFrame([result["summary"] for result in results])
    method_comparison = pd.concat([
        pd.DataFrame([
            {"policy_label": result["summary"]["policy_label"], "method": "Classical LCA", "total_kgCO2e": result["classical"]["total"]},
            {"policy_label": result["summary"]["policy_label"], "method": "Time-Dependent DLCA", "total_kgCO2e": result["time_dependent_breakdown"]["total"]},
            {"policy_label": result["summary"]["policy_label"], "method": "State-Dependent Dynamic LCA", "total_kgCO2e": result["sdd_breakdown"]["total"]},
        ])
        for result in results
    ], ignore_index=True)
    cost_breakdown = pd.DataFrame([
        {"policy_label": result["summary"]["policy_label"], **result["cost_breakdown"]}
        for result in results
    ])
    states_all = pd.concat([result["states"] for result in results], ignore_index=True)
    costs_all = pd.concat([
        result["costs"].assign(policy_label=result["summary"]["policy_label"])
        for result in results
    ], ignore_index=True)
    exogenous = EXOGENOUS.copy()

    summary.to_csv(CSV_DIR / "ha_strategy_summary.csv", index=False)
    method_comparison.to_csv(CSV_DIR / "ha_method_comparison.csv", index=False)
    cost_breakdown.to_csv(CSV_DIR / "ha_cost_breakdown.csv", index=False)
    states_all.to_csv(CSV_DIR / "ha_monthly_states.csv", index=False)
    costs_all.to_csv(CSV_DIR / "ha_monthly_costs.csv", index=False)
    exogenous.to_csv(CSV_DIR / "ha_exogenous_context.csv", index=False)

    reference = results_by_name.get(TIMELINE_POLICY_NAME, results[0])
    ref_states = reference["states"]
    ref_td = reference["time_dependent_dlca"]
    ref_sdd = reference["sdd"]
    reference_label = reference["summary"]["policy_label"]
    event_timeline = build_event_timeline(ref_states)
    event_impact = build_event_impact_breakdown(ref_td, ref_sdd)
    cumulative = pd.DataFrame({
        "month_index": ref_states["month_index"],
        "classical_weekly_total": (
            ref_states["good_output_units"] * ref_states["main_material_ef"].mean()
            + ref_states["good_output_units"] * ref_states["inbound_main_ef"].mean()
            + ref_states["process_kwh"] * ref_states["energy_mix_ef"].mean()
            + ref_states["outbound_shipments"] * ref_states["truck_ef"].mean()
            + ref_states["hvac_kwh"] * ref_states["energy_mix_ef"].mean()
        ),
        "td_total": ref_td["total"],
        "sdd_total": ref_sdd["total"],
    })
    cumulative["classical_cumulative"] = cumulative["classical_weekly_total"].cumsum()
    cumulative["td_cumulative"] = cumulative["td_total"].cumsum()
    cumulative["sdd_cumulative"] = cumulative["sdd_total"].cumsum()
    cumulative.to_csv(CSV_DIR / "ha_reference_cumulative.csv", index=False)
    event_timeline.to_csv(CSV_DIR / "ha_event_timeline.csv", index=False)
    event_impact.to_csv(CSV_DIR / "ha_event_impact_breakdown.csv", index=False)

    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(exogenous["month_index"], exogenous["warming"], color="#d7301f", label="Rechauffement cumule")
    axes[0].plot(exogenous["month_index"], 10 * exogenous["grid_factor"], color="#3182bd", label="Facteur reseau x10")
    axes[0].plot(exogenous["month_index"], 100 * exogenous["main_supply_availability"], color="#31a354", label="Disponibilite matiere (%)")
    axes[0].set_ylabel("Signal climatique")
    axes[0].set_title("Horizon 20 ans : climat, reseau et rarefaction")
    axes[0].legend(loc="upper right")
    axes[0].grid(alpha=0.2)

    axes[1].plot(ref_states["month_index"], ref_states["backlog_end"], color="black", label="Backlog")
    axes[1].plot(ref_states["month_index"], ref_states["capacity_applied"], color="#31a354", label="Capacite appliquee")
    axes[1].plot(ref_states["month_index"], ref_states["good_output_backup_units"], color="#756bb1", label="Production backup")
    axes[1].bar(ref_states["month_index"], ref_states["outbound_shipments"].where(ref_states["outbound_mode"] == "air", 0.0), color="#fd8d3c", alpha=0.45, label="Expeditions aeriennes")
    axes[1].set_ylabel("Reponse operationnelle")
    axes[1].set_title("Supply chain adaptee : regimes operationnels sur 20 ans")
    axes[1].legend(loc="upper right")
    axes[1].grid(alpha=0.2)

    axes[2].plot(cumulative["month_index"], cumulative["classical_cumulative"], color="#9ecae1", label="LCA classique")
    axes[2].plot(cumulative["month_index"], cumulative["td_cumulative"], color="#3182bd", label="Time-Dependent DLCA")
    axes[2].plot(cumulative["month_index"], cumulative["sdd_cumulative"], color="#e6550d", label="SDD")
    axes[2].set_xlabel("Mois")
    axes[2].set_ylabel("Impact cumule (kgCO2e)")
    axes[2].set_title(f"Impacts cumules sur la strategie {reference_label}")
    axes[2].legend(loc="upper left")
    axes[2].grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(IMG_DIR / "ha_system_overview.png", dpi=160, bbox_inches="tight")
    plt.close()

    method_pivot = method_comparison.pivot(index="policy_label", columns="method", values="total_kgCO2e").loc[[p.label for p in POLICIES]]
    x = np.arange(len(method_pivot.index))
    width = 0.24
    plt.figure(figsize=(13, 5.6))
    for idx, method in enumerate(method_pivot.columns):
        plt.bar(x + (idx - 1) * width, method_pivot[method], width=width, label=method)
    plt.xticks(x, method_pivot.index, rotation=15, ha="right")
    plt.ylabel("Impact total (kgCO2e)")
    plt.title("Strategies d'adaptation : comparaison des methodes")
    plt.legend()
    plt.tight_layout()
    plt.savefig(IMG_DIR / "ha_strategy_method_comparison.png", dpi=160)
    plt.close()

    cost_components = ["material", "inbound_transport", "energy", "storage", "outbound_transport", "backlog_penalty", "adaptation_capex"]
    fig, ax = plt.subplots(figsize=(13, 5.8))
    bottom = np.zeros(len(cost_breakdown))
    colors = {
        "material": "#9ecae1",
        "inbound_transport": "#6baed6",
        "energy": "#3182bd",
        "storage": "#fd8d3c",
        "outbound_transport": "#f16913",
        "backlog_penalty": "#756bb1",
        "adaptation_capex": "#31a354",
    }
    for component in cost_components:
        ax.bar(cost_breakdown["policy_label"], cost_breakdown[component], bottom=bottom, label=component, color=colors[component])
        bottom += cost_breakdown[component].to_numpy()
    ax.set_ylabel("Cout total")
    ax.set_title("Decomposition economique des strategies d'adaptation")
    ax.tick_params(axis="x", rotation=15)
    ax.legend(ncol=4, fontsize=8)
    ax.grid(axis="y", alpha=0.2)
    plt.tight_layout()
    plt.savefig(IMG_DIR / "ha_cost_breakdown.png", dpi=160)
    plt.close()

    fig, axes = plt.subplots(2, 1, figsize=(14, 8.5), sharex=True)
    axes[0].plot(ref_states["month_index"], ref_states["solar_used_kwh"], label="Solaire utilise")
    axes[0].plot(ref_states["month_index"], ref_states["biomass_used_kwh"], label="Biomasse utilisee")
    axes[0].plot(ref_states["month_index"], ref_states["battery_discharge_kwh"], label="Decharge batterie")
    axes[0].plot(ref_states["month_index"], ref_states["grid_energy_kwh"], label="Energie reseau")
    axes[0].set_ylabel("kWh")
    axes[0].set_title("Systeme energetique adapte : production et usage")
    axes[0].legend(loc="upper right")
    axes[0].grid(alpha=0.2)

    axes[1].plot(ref_states["month_index"], ref_states["battery_soh"], color="#756bb1", label="SOH batterie")
    axes[1].plot(ref_states["month_index"], ref_states["battery_soc_kwh"], color="#3182bd", label="SOC batterie (kWh)")
    axes[1].plot(ref_states["month_index"], ref_states["hvac_kwh"], color="#d7301f", label="Charge HVAC")
    axes[1].plot(ref_states["month_index"], 100 * ref_states["biomass_transition_level"], color="#31a354", label="Activation biomasse (%)")
    axes[1].plot(ref_states["month_index"], 100 * ref_states["biomass_transition_cap"], color="#74c476", linestyle="--", label="Plafond biomasse (%)")
    axes[1].set_xlabel("Mois")
    axes[1].set_ylabel("Etat / kWh / %")
    axes[1].set_title("Degradation batterie, cout thermique et activation biomasse")
    axes[1].legend(loc="upper right")
    axes[1].grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(IMG_DIR / "ha_energy_adaptation.png", dpi=160)
    plt.close()

    frontier = summary.copy()
    bubble = 60 + 0.0012 * frontier["total_cost"]
    plt.figure(figsize=(12.5, 5.4))
    plt.scatter(frontier["service_pct"], frontier["sdd_total_kgCO2e"], s=bubble, c=range(len(frontier)), cmap="tab10", alpha=0.85)
    offsets = {
        "Reference 2045": (0.06, 220),
        "Stock de resilience": (0.06, -260),
        "Autonomie energetique": (0.05, 180),
        "Adaptation integree": (0.05, -220),
        "Lean expose": (0.06, 220),
    }
    for _, r in frontier.iterrows():
        dx, dy = offsets.get(r["policy_label"], (0.05, 180))
        plt.annotate(
            r["policy_label"],
            xy=(r["service_pct"], r["sdd_total_kgCO2e"]),
            xytext=(r["service_pct"] + dx, r["sdd_total_kgCO2e"] + dy),
            textcoords="data",
            fontsize=8,
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.75},
            arrowprops={"arrowstyle": "-", "color": "#666666", "lw": 0.7, "alpha": 0.7},
        )
    plt.xlabel("Service (%)")
    plt.ylabel("Impact SDD total (kgCO2e)")
    plt.title("Frontiere adaptation : service, carbone et cout")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(IMG_DIR / "ha_strategy_frontier.png", dpi=160)
    plt.close()

    fig, axes = plt.subplots(5, 1, figsize=(15, 12.6), sharex=True, gridspec_kw={"height_ratios": [1.0, 1.4, 0.7, 1.0, 1.15]})
    climate_rows = [
        ("evt_canicule", "Canicule", "#d7301f"),
        ("evt_secheresse", "Secheresse", "#e6550d"),
        ("evt_tempete_inondation", "Tempete / inondation", "#3182bd"),
    ]
    for ypos, (col, label, color) in enumerate(climate_rows, start=1):
        months = event_timeline.loc[event_timeline[col] == 1, "month_index"]
        axes[0].scatter(months, [ypos] * len(months), marker="s", s=48, color=color, label=label)
    axes[0].set_yticks([1, 2, 3], [item[1] for item in climate_rows])
    axes[0].set_title(f"Calendrier des evenements climatiques, operationnels et des regimes - {reference_label}")
    axes[0].set_ylabel("Climat")
    axes[0].grid(axis="x", alpha=0.2)
    axes[0].legend(loc="upper right", ncol=3, fontsize=8)

    operational_rows = [
        ("evt_congestion_logistique", "Congestion logistique", "#fd8d3c"),
        ("evt_overtime_energetique", "Overtime energetique", "#756bb1"),
        ("evt_maintenance_corrective", "Maintenance corrective", "#31a354"),
        ("evt_recalage_qualite", "Recalage qualite", "#636363"),
        ("evt_capacite_appoint", "Capacite d'appoint", "#e377c2"),
    ]
    for ypos, (col, label, color) in enumerate(operational_rows, start=1):
        months = event_timeline.loc[event_timeline[col] == 1, "month_index"]
        axes[1].scatter(months, [ypos] * len(months), marker="o", s=28, color=color, label=label)
    axes[1].set_yticks([1, 2, 3, 4, 5], [item[1] for item in operational_rows])
    axes[1].set_ylabel("Operations")
    axes[1].grid(axis="x", alpha=0.2)
    axes[1].legend(loc="upper right", ncol=2, fontsize=8)

    regime_colors = {"nominal": "#74c476", "tendu": "#fd8d3c", "crise": "#d7301f"}
    for regime, color in regime_colors.items():
        regime_months = event_timeline.loc[event_timeline["regime_environnemental"] == regime, "month_index"]
        axes[2].bar(regime_months, [1.0] * len(regime_months), width=1.0, color=color, align="center", label=f"Regime {regime}")
    axes[2].set_ylim(0, 1.2)
    axes[2].set_yticks([])
    axes[2].set_ylabel("Regime")
    axes[2].grid(axis="x", alpha=0.2)
    axes[2].legend(loc="upper right", ncol=3, fontsize=8)

    axes[3].plot(cumulative["month_index"], cumulative["classical_weekly_total"], color="#9ecae1", linewidth=1.4, label="LCA classique")
    axes[3].plot(cumulative["month_index"], cumulative["td_total"], color="#3182bd", linewidth=1.4, label="TD-DLCA")
    axes[3].plot(cumulative["month_index"], cumulative["sdd_total"], color="#e6550d", linewidth=1.5, label="SDD")
    axes[3].set_ylabel("Impact mensuel")
    axes[3].set_title("Courbes temporelles des methodes LCA")
    axes[3].grid(axis="x", alpha=0.2)
    axes[3].legend(loc="upper left", ncol=3, fontsize=8)

    impact_components = [
        ("surimpact_matiere", "Backup matiere", "#9ecae1"),
        ("surimpact_inbound", "Inbound premium", "#6baed6"),
        ("surimpact_transport_aval", "Transport aval air", "#fd8d3c"),
        ("surimpact_rebut", "Rebut / recalage", "#756bb1"),
    ]
    bottom = np.zeros(len(event_impact))
    for col, label, color in impact_components:
        axes[4].bar(
            event_impact["month_index"],
            event_impact[col],
            bottom=bottom,
            width=0.9,
            color=color,
            label=label,
        )
        bottom += event_impact[col].to_numpy()
    ax4_line = axes[4].twinx()
    ax4_line.plot(
        event_impact["month_index"],
        event_impact["surimpact_cumule"],
        color="#d7301f",
        linewidth=2.0,
        label="Surimpact cumule",
    )
    axes[4].set_ylabel("Surimpact mensuel")
    ax4_line.set_ylabel("Surimpact cumule")
    axes[4].set_xlabel("Mois")
    axes[4].set_title("Impact attribue aux evenements (surimpact SDD vs TD-DLCA)")
    axes[4].grid(axis="x", alpha=0.2)
    handles_left, labels_left = axes[4].get_legend_handles_labels()
    handles_right, labels_right = ax4_line.get_legend_handles_labels()
    axes[4].legend(handles_left + handles_right, labels_left + labels_right, loc="upper left", ncol=3, fontsize=8)
    plt.tight_layout()
    plt.savefig(IMG_DIR / "ha_event_timeline.png", dpi=160)
    plt.close()

    print("Horizon adaptation outputs written to:")
    print("  CSV:", CSV_DIR.resolve())
    print("  Images:", IMG_DIR.resolve())
    print("\nStrategy summary:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    build_outputs()
